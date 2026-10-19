"""Integration checks against a running local PostgreSQL-backed server.
Run with: .venv/Scripts/python.exe -m pytest backend/test_flows.py -v
Creates synthetic customers; no database reset or external services.
"""
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import httpx

ROOT=Path(__file__).resolve().parent.parent
BASE=os.environ.get('TEST_BASE_URL','http://127.0.0.1:8000')

def client():
    return httpx.Client(base_url=BASE,timeout=30)

def signed(index):
    c=client()
    a=json.loads((ROOT/'.runtime/demo-accounts.json').read_text())[index]
    r=c.post('/api/auth/login',json={'email':a['email'],'password':a['password']})
    assert r.status_code==200,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf']
    return c

def test_complete_banking_baseline():
    with client() as anonymous:
        assert anonymous.get('/api/health').json()['database']=='postgresql'
        assert anonymous.get('/api/me').status_code==401
        assert anonymous.get('/api/admin').status_code==401
        assert anonymous.post('/api/auth/login',json={'email':'nobody@example.com','password':'WrongPassword123!'}).status_code==401
    alex,sam,admin=signed(0),signed(1),signed(2)
    assert alex.get('/api/admin').status_code==403
    assert admin.get('/api/admin').status_code==200
    a,s=alex.get('/api/me').json(),sam.get('/api/me').json()
    body={'recipient':s['account'],'amount':'12.34','memo':'Synthetic integration test','idempotency_key':str(uuid4())}
    token=alex.headers.pop('X-CSRF-Token')
    assert alex.post('/api/transfers',json=body).status_code==403
    alex.headers['X-CSRF-Token']=token
    assert alex.post('/api/transfers',json=body,headers={'Origin':'https://untrusted.example'}).status_code==403
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:alex.post('/api/transfers',json=body),range(2)))
    assert all(r.status_code==201 for r in results),[r.text for r in results]
    assert results[0].json()['id']==results[1].json()['id']
    assert alex.get('/api/me').json()['balance']==a['balance']-1234
    assert sam.get('/api/me').json()['balance']==s['balance']+1234
    assert sam.get('/api/transactions').json()[0]['amount']==1234
    assert alex.get('/api/transactions').json()[0]['amount']==-1234
    assert alex.post('/api/transfers',json={**body,'amount':'13.00'}).status_code==409
    for amount in ['-1','0','1.001','100000.01']:
        assert alex.post('/api/transfers',json={**body,'amount':amount,'idempotency_key':str(uuid4())}).status_code==422
    assert alex.post('/api/transfers',json={**body,'recipient':a['account'],'idempotency_key':str(uuid4())}).status_code==400
    assert alex.post('/api/transfers',json={**body,'recipient':'VB0000000000','idempotency_key':str(uuid4())}).status_code==404
    # Restore seeded balances with a second real transfer, retaining the audit trail.
    assert sam.post('/api/transfers',json={**body,'recipient':a['account'],'memo':'Return synthetic test funds','idempotency_key':str(uuid4())}).status_code==201
    exported=alex.get('/api/transactions/export')
    assert exported.status_code==200 and 'attachment' in exported.headers['content-disposition']
    assert 'Synthetic integration test' in exported.text
    upload=alex.post('/api/documents',files={'file':('practice.txt',b'Synthetic local banking document','text/plain')})
    assert upload.status_code==201,upload.text
    doc_id=upload.json()['id']
    assert any(d['id']==doc_id for d in alex.get('/api/documents').json())
    download=alex.get(f'/api/documents/{doc_id}/download')
    assert download.content==b'Synthetic local banking document'
    assert 'attachment' in download.headers['content-disposition']
    assert sam.get(f'/api/documents/{doc_id}/download').status_code==404
    assert sam.delete(f'/api/documents/{doc_id}').status_code==404
    assert admin.get(f'/api/documents/{doc_id}/download').status_code==404
    assert alex.post('/api/documents',files={'file':('bad.html',b'<script>alert(1)</script>','text/html')}).status_code==400
    assert alex.post('/api/documents',files={'file':('fake.png',b'not a PNG','image/png')}).status_code==400
    assert alex.post('/api/documents',files={'file':('large.txt',b'x'*(2*1024*1024+1),'text/plain')}).status_code==400
    assert alex.delete(f'/api/documents/{doc_id}').status_code==200
    assert alex.get(f'/api/documents/{doc_id}/download').status_code==404
    # Registration never accepts a client-supplied role or balance.
    c=client()
    email=f'lab-{uuid4().hex[:12]}@example.com'
    pwd='SyntheticPassword!123'
    r=c.post('/api/auth/register',json={'name':'Test Customer','email':email,'password':pwd,'role':'admin','balance':99999})
    assert r.status_code==201,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf']
    u=c.get('/api/me').json()
    assert u['role']=='customer' and u['balance']==0
    assert c.post('/api/auth/register',json={'name':'Duplicate','email':email,'password':pwd}).status_code==409
    assert c.post('/api/transfers',json={**body,'idempotency_key':str(uuid4())}).status_code==400
    assert c.patch('/api/profile',json={'name':'Updated Fictional Name','phone':'000-0000','address':'1 Fictional Lane','alerts':False}).status_code==200
    assert c.get('/api/me').json()['name']=='Updated Fictional Name'
    assert c.post('/api/password',json={'current_password':'incorrect','new_password':'NewSyntheticPass123!'}).status_code==400
    assert c.post('/api/password',json={'current_password':pwd,'new_password':'NewSyntheticPass123!'}).status_code==200
    assert c.get('/api/me').status_code==401
    r=c.post('/api/auth/login',json={'email':email,'password':'NewSyntheticPass123!'})
    assert r.status_code==200
    c.headers['X-CSRF-Token']=r.json()['csrf']
    assert admin.patch(f"/api/admin/users/{u['id']}",json={'active':False}).status_code==200
    assert c.get('/api/me').status_code==401
    assert c.post('/api/auth/login',json={'email':email,'password':'NewSyntheticPass123!'}).status_code==401
    assert admin.patch(f"/api/admin/users/{u['id']}",json={'active':True}).status_code==200
    assert admin.patch(f"/api/admin/users/{admin.get('/api/me').json()['id']}",json={'active':False}).status_code==400
    cookie=alex.cookies.get('vb_session')
    assert alex.post('/api/auth/logout').status_code==200
    assert alex.get('/api/me').status_code==401
    with client() as replay:
        replay.cookies.set('vb_session',cookie)
        assert replay.get('/api/me').status_code==401
    response=sam.get('/api/me')
    assert response.headers['X-Content-Type-Options']=='nosniff'
    assert response.headers['X-Frame-Options']=='DENY'
    assert 'no-store' in response.headers['Cache-Control']
    for c in [sam,admin]:
        assert c.post('/api/auth/logout').status_code==200
        c.close()
    alex.close()

def test_concurrent_transfers_cannot_overdraw():
    alex,sam=signed(0),signed(1)
    a,s=alex.get('/api/me').json(),sam.get('/api/me').json()
    c=client()
    r=c.post('/api/auth/register',json={'name':'Concurrent Test Customer','email':f'race-{uuid4().hex[:12]}@example.com','password':'SyntheticRacePass123!'})
    assert r.status_code==201,r.text
    c.headers['X-CSRF-Token']=r.json()['csrf']
    u=c.get('/api/me').json()
    def send(client,recipient,amount):
        return client.post('/api/transfers',json={'recipient':recipient,'amount':amount,'memo':'Concurrency verification','idempotency_key':str(uuid4())})
    assert send(alex,u['account'],'1.00').status_code==201
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:send(c,s['account'],'0.75'),range(2)))
    assert sorted(r.status_code for r in results)==[201,400]
    assert c.get('/api/me').json()['balance']==25
    assert send(c,a['account'],'0.25').status_code==201
    assert send(sam,a['account'],'0.75').status_code==201
    assert alex.get('/api/me').json()['balance']==a['balance']
    assert sam.get('/api/me').json()['balance']==s['balance']
    for session in [alex,sam,c]:
        assert session.post('/api/auth/logout').status_code==200
        session.close()


def test_vb003_sql_injection_prevention():
    """VB-003: SQL injection must not bypass transaction ownership."""
    alex, sam = signed(0), signed(1)
    try:
        endpoint = '/api/lab/transactions/search'

        # Authentication is required.
        with client() as anonymous:
            assert anonymous.get(endpoint, params={'q': 'test'}).status_code == 401

        # Normal searches must continue to work.
        normal = alex.get(endpoint, params={'q': 'test'})
        assert normal.status_code == 200, normal.text
        assert isinstance(normal.json(), list)
        assert all('test' in row['memo'].lower() for row in normal.json())

        # The original SQL injection must be treated as literal text.
        payload = "' OR 1=1 -- "
        injected = alex.get(endpoint, params={'q': payload})
        assert injected.status_code == 200, injected.text
        assert injected.json() == []

        # A search must return only transactions owned by the user.
        for user_client in (alex, sam):
            authorized = user_client.get('/api/transactions')
            assert authorized.status_code == 200, authorized.text

            search = user_client.get(endpoint, params={'q': ''})
            assert search.status_code == 200, search.text

            authorized_ids = {row['id'] for row in authorized.json()}
            assert all(row['id'] in authorized_ids for row in search.json())
            assert len(search.json()) <= 25
    finally:
        alex.close()
        sam.close()



def test_vb004_command_injection_prevention():
    """VB-004: Ping diagnostics must reject OS command injection."""
    endpoint = '/api/lab/diagnostics/ping'

    # The diagnostic endpoint requires authentication.
    with client() as anonymous:
        response = anonymous.get(
            endpoint,
            params={'host': '127.0.0.1'}
        )
        assert response.status_code == 401, response.text

    alex = signed(0)
    try:
        # Legitimate loopback diagnostics must continue to work.
        normal = alex.get(
            endpoint,
            params={'host': '127.0.0.1'}
        )
        assert normal.status_code == 200, normal.text

        data = normal.json()
        assert data['command'] == ['ping', '-n', '1', '127.0.0.1']
        assert data['returncode'] == 0
        assert '127.0.0.1' in data['output']

        # The original successful injection must be rejected.
        marker = 'VB004_INJECTION_CONFIRMED'
        payload = f'127.0.0.1 & echo {marker}'

        injected = alex.get(
            endpoint,
            params={'host': payload}
        )
        assert injected.status_code == 422, injected.text
        assert injected.json()['detail'] == (
            'Only the local loopback address is permitted'
        )

        # No injected command output should be returned.
        assert 'output' not in injected.json()

        # Other destinations must also be rejected.
        external = alex.get(
            endpoint,
            params={'host': '8.8.8.8'}
        )
        assert external.status_code == 422, external.text

    finally:
        alex.close()


def test_vb005_csrf_remediation():
    """VB-005: CSRF token and origin protections on synthetic profile updates."""
    customer = signed(0)
    try:
        endpoint = '/api/lab/csrf/profile-address'
        original_address = customer.get('/api/me').json()['address']
        test_address = 'VB-005 regression test address'

        def current_address():
            response = customer.get('/api/me')
            assert response.status_code == 200, response.text
            return response.json()['address']

        try:
            missing = customer.post(
                endpoint,
                data={'address': test_address},
                headers={'X-CSRF-Token': ''},
            )
            assert missing.status_code == 403, missing.text
            assert current_address() == original_address

            invalid = customer.post(
                endpoint,
                data={'address': test_address},
                headers={'X-CSRF-Token': 'invalid-vb005-token'},
            )
            assert invalid.status_code == 403, invalid.text
            assert current_address() == original_address

            untrusted = customer.post(
                endpoint,
                data={'address': test_address},
                headers={'Origin': 'https://untrusted.example'},
            )
            assert untrusted.status_code == 403, untrusted.text
            assert current_address() == original_address

            valid = customer.post(
                endpoint,
                data={'address': test_address},
            )
            assert valid.status_code == 200, valid.text
            assert valid.json()['address'] == test_address
            assert current_address() == test_address

        finally:
            restore = customer.post(
                endpoint,
                data={'address': original_address},
            )
            assert restore.status_code == 200, restore.text
            assert current_address() == original_address
    finally:
        customer.close()



def test_vb006_admin_authorization_remediation():
    """VB-006: Maintenance status requires the administrator role."""
    from contextlib import closing

    endpoint = '/api/lab/admin/maintenance-status'
    with client() as anonymous:
        response = anonymous.get(endpoint)
        assert response.status_code == 401, response.text

    with closing(signed(0)) as customer:
        response = customer.get(endpoint)
        assert response.status_code == 403, response.text

        # The real administrator endpoint must retain its role boundary.
        response = customer.get('/api/admin')
        assert response.status_code == 403, response.text

    with closing(signed(2)) as administrator:
        response = administrator.get(endpoint)
        assert response.status_code == 200, response.text
        assert response.json() == {
            'operation': 'synthetic-administrator-maintenance',
            'maintenance_mode': False,
            'authorized_role': 'admin',
            'lab_only': True,
        }
