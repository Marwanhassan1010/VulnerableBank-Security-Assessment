"""VulnerableBank: synthetic, local-only banking practice baseline."""
import hashlib
import io
import os
import re
import secrets
import subprocess
import time
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

from fastapi import FastAPI, Depends, HTTPException, Request, Response, UploadFile, File
from fastapi.responses import StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field, field_validator
from email_validator import validate_email, EmailNotValidError
from pwdlib import PasswordHash
from sqlalchemy import create_engine, String, Integer, BigInteger, Boolean, Text, DateTime, ForeignKey, LargeBinary, CheckConstraint, select, or_, func, delete, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session
from sqlalchemy.exc import IntegrityError

ROOT = Path(__file__).resolve().parent.parent
DATABASE_URL = os.environ.get('DATABASE_URL')
if not DATABASE_URL:
    import json
    config = ROOT / '.runtime' / 'local.json'
    if config.exists():
        DATABASE_URL = json.loads(config.read_text())['databaseUrl']
    else:
        raise RuntimeError('Start the local database first (scripts/start.ps1) or set DATABASE_URL.')
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(engine, expire_on_commit=False)
passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))

def now():
    return datetime.now(timezone.utc)

class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(16), default='customer')
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    phone: Mapped[str] = mapped_column(String(30), default='')
    address: Mapped[str] = mapped_column(String(240), default='')
    alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Account(Base):
    __tablename__ = 'accounts'
    __table_args__ = (CheckConstraint('balance >= 0'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), unique=True)
    number: Mapped[str] = mapped_column(String(20), unique=True)
    balance: Mapped[int] = mapped_column(BigInteger, default=0)

class LoginSession(Base):
    __tablename__ = 'sessions'
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    csrf: Mapped[str] = mapped_column(String(64))
    expires: Mapped[datetime] = mapped_column(DateTime(timezone=True))

class Transfer(Base):
    __tablename__ = 'transfers'
    __table_args__ = (CheckConstraint('amount > 0'),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    source_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'), index=True)
    target_id: Mapped[int] = mapped_column(ForeignKey('accounts.id'), index=True)
    amount: Mapped[int] = mapped_column(BigInteger)
    memo: Mapped[str] = mapped_column(String(140))
    key: Mapped[str] = mapped_column(String(100), unique=True)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Document(Base):
    __tablename__ = 'documents'
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(60))
    content: Mapped[bytes] = mapped_column(LargeBinary)
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

class Audit(Base):
    __tablename__ = 'audit'
    id: Mapped[int] = mapped_column(primary_key=True)
    actor: Mapped[int | None] = mapped_column(Integer, nullable=True)
    action: Mapped[str] = mapped_column(String(120))
    created: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)

def audit(db, user, action):
    db.add(Audit(actor=user.id if user else None, action=action))

def new_account(db, user, balance=0):
    db.add(user)
    db.flush()
    account = Account(user_id=user.id, number='VB' + secrets.token_hex(5).upper(), balance=balance)
    db.add(account)
    return account

def seed():
    import json
    path = ROOT / '.runtime' / 'demo-accounts.json'
    if os.environ.get('SEED_DEMO', '1') != '1':
        return
    with SessionLocal() as db:
        if db.scalar(select(func.count(User.id))) > 0:
            return
        demo = []
        for email, name, role, balance in [('alex@vulnerablebank.test','Alex Morgan','customer',1250000),('sam@vulnerablebank.test','Sam Rivera','customer',875000),('admin@vulnerablebank.test','Jordan Admin','admin',0)]:
            pwd = 'Lab!' + secrets.token_urlsafe(15)
            user = User(email=email,name=name,role=role,password_hash=passwords.hash(pwd))
            a = new_account(db,user,balance)
            db.flush()
            demo.append(dict(email=email,password=pwd,role=role,account=a.number))
        audit(db,None,'Synthetic demo accounts initialized')
        db.commit()
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps(demo,indent=2))

@asynccontextmanager
async def lifespan(app):
    Base.metadata.create_all(engine)
    seed()
    yield

app = FastAPI(title='VulnerableBank local laboratory', lifespan=lifespan, docs_url='/api/docs',openapi_url='/api/openapi.json',redoc_url=None)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=['127.0.0.1','localhost','testserver'])
ALLOWED_ORIGINS = {'http://127.0.0.1:8000','http://localhost:8000','http://127.0.0.1:5173','http://localhost:5173'}
attempts = defaultdict(deque)

@app.middleware('http')
async def boundaries(request, call_next):
    if request.method not in ('GET','HEAD','OPTIONS'):
        origin = request.headers.get('origin')
        if (origin and origin not in ALLOWED_ORIGINS) or request.headers.get('sec-fetch-site') == 'cross-site':
            return Response('Cross-origin requests are not accepted',status_code=403)
        length = request.headers.get('content-length','0')
        if not length.isdigit() or int(length) > 3 * 1024 * 1024:
            return Response('Request too large',status_code=413)
    response = await call_next(request)
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['Referrer-Policy'] = 'no-referrer'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    return response

def db_session():
    with SessionLocal() as db:
        yield db

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def current(request: Request, db: Session = Depends(db_session)):
    token = request.cookies.get('vb_session','')
    s = db.get(LoginSession,digest(token))
    if not s or s.expires <= now():
        raise HTTPException(401,'Please sign in')
    user = db.get(User,s.user_id)
    if not user or not user.active:
        raise HTTPException(401,'Please sign in')
    if request.method not in ('GET','HEAD','OPTIONS') and not secrets.compare_digest(s.csrf,request.headers.get('X-CSRF-Token','')):
        raise HTTPException(403,'Invalid CSRF token')
    request.state.login_session = s
    return user

def admin(user=Depends(current)):
    if user.role != 'admin':
        raise HTTPException(403,'Administrator access required')
    return user

def throttle(request):
    key = request.client.host if request.client else 'local'
    q = attempts[key]
    t = time.monotonic()
    while q and q[0] < t - 60:
        q.popleft()
    if len(q) >= 20:
        raise HTTPException(429,'Too many attempts. Wait one minute.')
    q.append(t)

class Credentials(BaseModel):
    email: str = Field(max_length=254)
    password: str = Field(min_length=12,max_length=128)
    @field_validator('email')
    @classmethod
    def synthetic_email(cls,value):
        try:
            return validate_email(value,check_deliverability=False,test_environment=True).normalized
        except EmailNotValidError as e:
            raise ValueError(str(e))

class Registration(Credentials):
    name: str = Field(min_length=2,max_length=80)
    @field_validator('name')
    @classmethod
    def clean_name(cls,v):
        if len(v.strip()) < 2: raise ValueError('Enter your name')
        return v.strip()

def issue_session(db,user,response):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    db.add(LoginSession(token_hash=digest(token),user_id=user.id,csrf=csrf,expires=now()+timedelta(hours=8)))
    response.set_cookie('vb_session',token,httponly=True,samesite='strict',secure=False,max_age=28800,path='/')
    db.commit()
    return {'csrf':csrf}

@app.post('/api/auth/register',status_code=201)
def register(data:Registration,request:Request,response:Response,db:Session=Depends(db_session)):
    throttle(request)
    user=User(email=str(data.email).lower(),name=data.name,password_hash=passwords.hash(data.password))
    try:
        new_account(db,user)
        audit(db,user,'Registered customer')
        return issue_session(db,user,response)
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,'Email is already registered')

@app.post('/api/auth/login')
def login(data:Credentials,request:Request,response:Response,db:Session=Depends(db_session)):
    throttle(request)
    user=db.scalar(select(User).where(User.email==str(data.email).lower()))
    valid=passwords.verify(data.password,user.password_hash if user else DUMMY_HASH)
    if not user or not valid or not user.active:
        raise HTTPException(401,'Invalid email or password')
    old=request.cookies.get('vb_session')
    if old: db.execute(delete(LoginSession).where(LoginSession.token_hash==digest(old)))
    audit(db,user,'Signed in')
    return issue_session(db,user,response)

@app.post('/api/auth/logout')
def logout(request:Request,response:Response,user=Depends(current),db:Session=Depends(db_session)):
    db.delete(request.state.login_session)
    audit(db,user,'Signed out')
    db.commit()
    response.delete_cookie('vb_session',path='/')
    return {'ok':True}

def user_json(user,account):
    return dict(id=user.id,email=user.email,name=user.name,role=user.role,phone=user.phone,address=user.address,alerts=user.alerts,account=account.number,balance=account.balance,created=user.created.isoformat())

@app.get('/api/me')
def me(request:Request,user=Depends(current),db:Session=Depends(db_session)):
    a=db.scalar(select(Account).where(Account.user_id==user.id))
    return {**user_json(user,a),'csrf':request.state.login_session.csrf}

class Profile(BaseModel):
    name:str=Field(min_length=2,max_length=80)
    phone:str=Field(max_length=30)
    address:str=Field(max_length=240)
    alerts:bool


@app.post('/api/lab/csrf/profile-address')
async def csrf_profile_address(
    request: Request,
    user: User = Depends(current),
    db: Session = Depends(db_session)
):
    """VB-005: Synthetic profile update protected by CSRF validation."""

    # Reuse the application's session and CSRF-token validation.

    # Accept a browser-compatible HTML form submission.
    body = (await request.body()).decode('utf-8')
    from urllib.parse import parse_qs
    fields = parse_qs(body)

    address = fields.get('address', [''])[0]

    if len(address) > 80:
        raise HTTPException(422, 'Address is too long')

    user.address = address
    audit(db, user, 'VB-005 synthetic profile address update')
    db.commit()

    return {'ok': True, 'address': user.address}


@app.patch('/api/profile')
def profile(data:Profile,user=Depends(current),db:Session=Depends(db_session)):
    for key,value in data.model_dump().items(): setattr(user,key,value)
    audit(db,user,'Updated profile')
    db.commit()
    return {'ok':True}

class PasswordChange(BaseModel):
    current_password:str=Field(max_length=128)
    new_password:str=Field(min_length=12,max_length=128)

@app.post('/api/password')
def change_password(data:PasswordChange,response:Response,user=Depends(current),db:Session=Depends(db_session)):
    if not passwords.verify(data.current_password,user.password_hash): raise HTTPException(400,'Current password is incorrect')
    user.password_hash=passwords.hash(data.new_password)
    db.execute(delete(LoginSession).where(LoginSession.user_id==user.id))
    audit(db,user,'Changed password; revoked all sessions')
    db.commit()
    response.delete_cookie('vb_session',path='/')
    return {'ok':True}

class TransferInput(BaseModel):
    recipient:str=Field(min_length=5,max_length=20,pattern=r'^VB[A-F0-9]{10}$')
    amount:Decimal=Field(gt=0,le=100000,max_digits=8,decimal_places=2)
    memo:str=Field(default='',max_length=140)
    idempotency_key:str=Field(min_length=16,max_length=64,pattern=r'^[a-zA-Z0-9-]+$')

@app.post('/api/transfers',status_code=201)
def transfer(data:TransferInput,user=Depends(current),db:Session=Depends(db_session)):
    # Account rows are locked in stable order to serialize money movement and avoid deadlocks.
    own=db.scalar(select(Account).where(Account.user_id==user.id))
    target=db.scalar(select(Account).where(Account.number==data.recipient))
    if not target: raise HTTPException(404,'Recipient account does not exist')
    if own.id==target.id: raise HTTPException(400,'Choose a different recipient')
    key=f'{user.id}:{data.idempotency_key}'
    cents=int(data.amount*100)
    locked=list(db.scalars(select(Account).where(Account.id.in_([own.id,target.id])).order_by(Account.id).with_for_update().execution_options(populate_existing=True)))
    prior=db.scalar(select(Transfer).where(Transfer.key==key))
    if prior:
        if prior.target_id!=target.id or prior.amount!=cents or prior.memo!=data.memo: raise HTTPException(409,'Transfer key was already used for a different request')
        return {'id':prior.id,'replayed':True}
    # Recheck both users while locked; admin freeze uses the same account lock.
    owners=list(db.scalars(select(User).where(User.id.in_([own.user_id,target.user_id])).execution_options(populate_existing=True)))
    if any(not u.active for u in owners): raise HTTPException(400,'Account is unavailable')
    if own.balance<cents: raise HTTPException(400,'Insufficient funds')
    own.balance-=cents
    target.balance+=cents
    t=Transfer(source_id=own.id,target_id=target.id,amount=cents,memo=data.memo,key=key)
    db.add(t)
    audit(db,user,'Completed synthetic transfer')
    db.commit()
    return {'id':t.id,'replayed':False}

def history_rows(db,user):
    a=db.scalar(select(Account).where(Account.user_id==user.id))
    rows=db.scalars(select(Transfer).where(or_(Transfer.source_id==a.id,Transfer.target_id==a.id)).order_by(Transfer.created.desc()).limit(250))
    result=[]
    for t in rows:
        outgoing=t.source_id==a.id
        other=db.get(Account,t.target_id if outgoing else t.source_id)
        owner=db.get(User,other.user_id)
        result.append(dict(id=t.id,created=t.created.isoformat(),amount=-t.amount if outgoing else t.amount,memo=t.memo,counterparty=owner.name,account=other.number,direction='Sent' if outgoing else 'Received'))
    return result

@app.get('/api/transactions')
def transactions(user=Depends(current),db:Session=Depends(db_session)):
    return history_rows(db,user)


@app.get('/api/lab/transactions/search')
def transaction_search(
    q: str,
    user=Depends(current),
    db: Session=Depends(db_session)
):
    """VB-003: Parameterized transaction search. Local lab only."""
    account = db.scalar(
        select(Account).where(Account.user_id == user.id)
    )

    if not account:
        raise HTTPException(404, 'Account not found')

    
    # VB-003 FIX: Parameterized SQL prevents SQL injection.
    query = text("""
        SELECT id, memo, amount
        FROM transfers
        WHERE (source_id = :account_id OR target_id = :account_id)
          AND memo ILIKE :pattern
        LIMIT 25
    """)

    rows = db.execute(
        query,
        {
            "account_id": account.id,
            "pattern": f"%{q}%"
        }
    ).mappings().all()


    return [
        {'id': row['id'], 'memo': row['memo'], 'amount': row['amount']}
        for row in rows
    ]


@app.get('/api/transactions/export')
def export(user=Depends(current),db:Session=Depends(db_session)):
    import csv
    stream=io.StringIO()
    writer=csv.writer(stream)
    writer.writerow(['Reference','Date','Amount USD','Counterparty','Account','Memo'])
    def safe(v):
        v=str(v)
        return "'"+v if v.lstrip().startswith(('=','+','-','@','\t','\r')) else v
    for t in history_rows(db,user): writer.writerow([t['id'],t['created'],f"{t['amount']/100:.2f}",safe(t['counterparty']),t['account'],safe(t['memo'])])
    return Response(stream.getvalue(),media_type='text/csv',headers={'Content-Disposition':'attachment; filename="transactions.csv"'})

@app.get('/api/documents')
def documents(user=Depends(current),db:Session=Depends(db_session)):
    rows=db.execute(select(Document.id,Document.name,Document.kind,Document.created,func.octet_length(Document.content)).where(Document.user_id==user.id).order_by(Document.created.desc())).all()
    return [dict(id=r[0],name=r[1],kind=r[2],created=r[3].isoformat(),size=r[4]) for r in rows]

@app.post('/api/documents',status_code=201)
async def upload(file:UploadFile=File(...),user=Depends(current),db:Session=Depends(db_session)):
    content=await file.read(2*1024*1024+1)
    if not content or len(content)>2*1024*1024: raise HTTPException(400,'Choose a nonempty file up to 2 MB')
    name=re.sub(r'[^a-zA-Z0-9._ -]','_', (file.filename or 'document').replace('\\','/').split('/')[-1])[:100]
    suffix=Path(name).suffix.lower()
    kind={'.pdf':'application/pdf','.txt':'text/plain','.png':'image/png','.jpg':'image/jpeg','.jpeg':'image/jpeg'}.get(suffix)
    valid=kind and ((suffix=='.pdf' and content.startswith(b'%PDF-')) or (suffix=='.png' and content.startswith(b'\x89PNG\r\n\x1a\n')) or (suffix in ('.jpg','.jpeg') and content.startswith(b'\xff\xd8\xff')) or (suffix=='.txt' and b'\x00' not in content))
    if not valid: raise HTTPException(400,'Upload PDF, PNG, JPEG, or plain text with matching content')
    if suffix=='.txt':
        try: content.decode('utf-8')
        except UnicodeDecodeError: raise HTTPException(400,'Text must be UTF-8')
    db.scalar(select(Account).where(Account.user_id==user.id).with_for_update())
    count=db.scalar(select(func.count(Document.id)).where(Document.user_id==user.id))
    if count>=20: raise HTTPException(400,'Document limit is 20. Delete a document first.')
    doc=Document(user_id=user.id,name=name,kind=kind,content=content)
    db.add(doc)
    audit(db,user,'Uploaded document')
    db.commit()
    return {'id':doc.id}

def owned_document(db,user,doc_id):
    doc=db.scalar(select(Document).where(Document.id==doc_id,Document.user_id==user.id))
    if not doc: raise HTTPException(404,'Document not found')
    return doc

@app.get('/api/documents/{doc_id}/download')
def download(doc_id:str,user=Depends(current),db:Session=Depends(db_session)):
    doc=owned_document(db,user,doc_id)
    return Response(doc.content,media_type='application/octet-stream',headers={'Content-Disposition':f'attachment; filename="{doc.name}"'})

@app.delete('/api/documents/{doc_id}')
def remove_document(doc_id:str,user=Depends(current),db:Session=Depends(db_session)):
    db.delete(owned_document(db,user,doc_id))
    audit(db,user,'Deleted document')
    db.commit()
    return {'ok':True}

@app.get('/api/admin')
def admin_dashboard(user=Depends(admin),db:Session=Depends(db_session)):
    users=[{**user_json(u,a),'active':u.active} for u,a in db.execute(select(User,Account).join(Account,Account.user_id==User.id).order_by(User.id))]
    events=[dict(id=e.id,actor=e.actor,action=e.action,created=e.created.isoformat()) for e in db.scalars(select(Audit).order_by(Audit.id.desc()).limit(100))]
    return dict(users=users,events=events,transfers=db.scalar(select(func.count(Transfer.id))),total_balance=sum(u['balance'] for u in users))

class StatusUpdate(BaseModel):
    active:bool

@app.patch('/api/admin/users/{user_id}')
def status(user_id:int,data:StatusUpdate,user=Depends(admin),db:Session=Depends(db_session)):
    a=db.scalar(select(Account).where(Account.user_id==user_id).with_for_update())
    target=db.get(User,user_id)
    if not a or not target: raise HTTPException(404,'Customer not found')
    if target.role=='admin': raise HTTPException(400,'Administrator status cannot be changed here')
    target.active=data.active
    if not data.active: db.execute(delete(LoginSession).where(LoginSession.user_id==target.id))
    audit(db,user,f"{'Enabled' if data.active else 'Froze'} customer {user_id}")
    db.commit()
    return {'ok':True}



@app.get('/api/lab/admin/maintenance-status')
def secure_admin_maintenance_status(user=Depends(admin)):
    """VB-006: Synthetic maintenance status restricted to administrators."""
    return {
        'operation': 'synthetic-administrator-maintenance',
        'maintenance_mode': False,
        'authorized_role': user.role,
        'lab_only': True,
    }


@app.get('/api/lab/diagnostics/ping')
def secure_ping(
    host: str,
    user=Depends(current)
):
    """VB-004: Secure local diagnostic endpoint."""

    # Restrict diagnostics to the local loopback address.
    if host != '127.0.0.1':
        raise HTTPException(
            status_code=422,
            detail='Only the local loopback address is permitted'
        )

    # Pass arguments separately; never invoke a shell.
    command = ['ping', '-n', '1', host]

    try:
        result = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=5
        )
    except subprocess.TimeoutExpired:
        raise HTTPException(
            status_code=504,
            detail='Diagnostic command timed out'
        )

    return {
        'command': command,
        'returncode': result.returncode,
        'output': (result.stdout + result.stderr)[:3000]
    }



@app.get('/api/health')
def health(db:Session=Depends(db_session)):
    db.execute(select(1))
    return {'status':'ok','database':'postgresql','mode':'synthetic-local-baseline'}

if (ROOT/'dist').exists():
    app.mount('/assets',StaticFiles(directory=ROOT/'dist'/'assets'),name='assets')
    @app.get('/')
    def index():
        return FileResponse(ROOT/'dist'/'index.html')
