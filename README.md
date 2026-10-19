# VulnerableBank — Project 4

A fictional, functional banking lab with a reasonably secure starting point. The original baseline was developed without intentional vulnerabilities. On the separate `security-lab` branch, six controlled security findings were demonstrated and remediated. All funds and identities are synthetic. No payment integrations, email delivery, SMS, telemetry, or cloud hosting are configured.

## Open it

1. Double-click **Start VulnerableBank.cmd**.
2. Visit **http://127.0.0.1:8000**.
3. Read **.runtime/demo-accounts.json** for the generated local customer and administrator passwords and account numbers. Those credentials are unique to this installation.
4. Double-click **Stop VulnerableBank.cmd** when finished. Balances and uploads persist.

From PowerShell in the project folder:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/start.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop.ps1
```

The installer uses the available Codex Python and Node runtimes on this computer. Their paths are recorded in `.runtime/tools.json`. If those runtimes are removed, run setup with an installed Python 3.12+, Node 22+, and pnpm 11:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1 -Python python -Node node -Pnpm pnpm
```

## Demo accounts

| Identity | Role | Initial synthetic balance |
|---|---|---:|
| alex@vulnerablebank.test | Customer | $12,500.00 |
| sam@vulnerablebank.test | Customer | $8,750.00 |
| admin@vulnerablebank.test | Administrator | $0.00 |

The verified browser transfer moved $25 from Alex to Sam. All other integration transfer checks returned seeded funds. The history preserves test transfers. Test registration creates additional fictional $0 customers.

New registrations start at $0. Copy their account number and transfer funds from Alex or Sam to test receiving money. Customers cannot set their role, balance, or another user's details. Admins can freeze/enable customers and inspect account summaries and the audit log. Admins cannot download other users' documents.

## Features

- Registration, login, logout, revocable sessions, password changes.
- Dashboard with fictional USD checking balance and recent activity.
- Reviewed, atomic transfers with integer cents, row locks, nonnegative balances, and idempotency keys.
- Transaction history (latest 250), search, CSV export with spreadsheet formula escaping.
- Profile, address, phone, and stored confirmation preference. No outbound notifications.
- Upload, list, download, and delete owned PDF, PNG, JPEG, or UTF-8 text documents; 2 MB each, 20 per customer. Stored in PostgreSQL, served as attachments. Type checks do not constitute antivirus scanning.
- Administrator summaries, account freeze/unfreeze, session revocation, and audit events.
- Responsive React + JavaScript interface styled with Tailwind CSS and custom local CSS; no external fonts or assets.

## Architecture

```text
Browser -> http://127.0.0.1:8000
           FastAPI serves built React + /api
           SQLAlchemy -> PostgreSQL 18 at 127.0.0.1:55432
```

Portable PostgreSQL is downloaded through the `embedded-postgres` npm package and kept inside the project. No Windows database service is installed. The database and API bind to loopback only. No firewall rules or public tunnels are created. See the [portable PostgreSQL project](https://github.com/leinelissen/embedded-postgres) for its implementation.

Backend: `backend/main.py`. Frontend: `frontend/src/main.jsx` and `style.css`. Application data: `data/postgres`. Runtime settings, generated passwords, and logs: `.runtime`. Dependencies: `node_modules` and `.venv`.

### Development

Start the normal app first, then:

```powershell
node node_modules/vite/bin/vite.js --config frontend/vite.config.js
```

Visit http://127.0.0.1:5173. The dev server proxies `/api` to port 8000. Production uses the same origin with no CORS allowance. Build after frontend changes, then restart the app:

```powershell
node node_modules/vite/bin/vite.js build --config frontend/vite.config.js
```

### Docker Compose (provided, not executed here)

Docker Desktop was not installed on the inspected computer. The portable PostgreSQL path is the tested launch method. If Docker is installed later:

1. Stop the native app to free port 8000.
2. Create `.env` containing `POSTGRES_PASSWORD=` followed by a long random hexadecimal password.
3. Run `docker compose up --build -d`.
4. Read credentials with `docker compose exec app cat /app/.runtime/demo-accounts.json`.
5. Stop with `docker compose down`. Do not add `-v` unless discarding that separate lab database is intended.

Compose publishes only `127.0.0.1:8000`, keeps PostgreSQL unexposed on an internal network, and uses separate persistent volumes. It does not use the native Desktop database. Compose has not been runtime-verified in this environment.

## Baseline controls and limits

Passwords use Argon2 via `pwdlib`; see [FastAPI's password hashing guidance](https://fastapi.tiangolo.com/tutorial/security/oauth2-jwt/). Browser sessions use random opaque tokens stored hashed in PostgreSQL, expire after eight hours, and are revoked on logout, password change, or freezing an account. Cookies are HttpOnly and SameSite Strict. The Secure cookie flag is intentionally off for this HTTP loopback environment; this is not a deployment configuration.

Authenticated writes require a per-session CSRF token. Writes reject foreign origins and cross-site fetches. Host checks, a content security policy, frame blocking, no-sniff, and no-store headers are enabled. Login/registration rate limiting is local-process based (20 attempts per minute per client IP). Uploads are bounded, names sanitized, permissions checked on every download/delete, and SQL is built with parameterized ORM queries. Transfer limits are enforced by the backend, with concurrency checks against PostgreSQL.

This is a learning baseline, not a certified banking system. It has no MFA, production identity verification, antivirus scanning, high-availability deployment, or financial reconciliation service. Keep it on loopback and use fictional details. The Desktop is within OneDrive on this machine; any existing Windows/OneDrive synchronization settings remain under your control. Never store real personal or banking data here.

## Verification

With the app running:

```powershell
.venv/Scripts/python.exe -m pytest backend/test_flows.py -v
```

The integration suite uses the actual HTTP server and PostgreSQL. It covers authenticated flows, transfer accounting and retries, duplicate concurrent submissions, concurrent insufficient-funds protection, validation failures, customer/admin isolation, cross-origin/CSRF rejection, upload restrictions, document ownership, password/session revocation, freeze/unfreeze, and CSV export. It creates only synthetic test data.

See `TEST-RESULTS.md` for the recorded results and limitations.

## Completed security assessment

The `security-lab` branch contains six documented security exercises.
Each finding was investigated and remediated in the local laboratory.

| ID | Finding | Report |
|---|---|---|
| VB-001 | Insecure Direct Object Reference (IDOR) | `security/findings/VB-001-IDOR.md` |
| VB-002 | Stored HTML Injection | `security/findings/VB-002-Stored-HTML-Injection.md` |
| VB-003 | SQL Injection | `security/findings/VB-003-SQL-Injection.md` |
| VB-004 | OS Command Injection | `security/findings/VB-004-Command-Injection.md` |
| VB-005 | Cross-Site Request Forgery (CSRF) | `security/VB-005-CSRF.md` |
| VB-006 | Vertical Privilege Escalation / Incorrect Authorization | `security/VB-006-Vertical-Privilege-Escalation.md` |

Final verified regression command:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/test_flows.py -v
```

Observed result: **6 passed in 16.99 seconds**.

The security exercises used fictional accounts and controlled laboratory
endpoints. They do not constitute a comprehensive independent security
audit or certification. The application must remain restricted to the
local laboratory environment.

## Project status and next steps

The six planned VulnerableBank security findings (VB-001 through VB-006)
have been demonstrated, remediated, and documented on `security-lab`.

The final HTTP regression suite passed all six tests.

The project remains a local educational laboratory and must not be
exposed publicly or used with real banking information.

The remaining project-wide closeout work includes updating
`TEST-RESULTS.md`, reviewing the final documentation, and committing
the documentation changes.

Project 5 (Active Directory) can be considered after VulnerableBank's
final closeout review.
