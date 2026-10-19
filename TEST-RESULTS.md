# Verified baseline — October 19, 2026

Installation: `C:\Users\marwa\OneDrive\Desktop\VulnerableBank`

## Executed

- React production build: **PASS**, Vite 7.3.7, React 19, Tailwind 4.
- Real database: **PostgreSQL 18**, portable Windows binaries; no SQLite fallback.
- HTTP integration suite: **2 passed in 2.68s** against the Desktop app and real PostgreSQL.
- Stop/start cycle: **PASS**; database accounts and records persisted.
- Listener inspection: **127.0.0.1:8000** for FastAPI and **127.0.0.1:55432** for PostgreSQL. No wildcard listener for either service.

## Integration coverage

`test_complete_banking_baseline` verified:

- Health, unauthenticated rejection, invalid login, customer login, admin login and role boundary.
- CSRF and cross-origin write rejection.
- Two simultaneous submissions of the same transfer create exactly one transfer and debit.
- Correct sender/recipient balance and history changes; replay with altered payload rejected.
- Negative, zero, fractional-cent, over-limit, same-account, unknown-account and insufficient-funds requests rejected.
- CSV download.
- Document upload/list/download/delete; exact content round-trip; other customers and admin cannot read private documents.
- Unsupported extension, incorrect file signature, oversize upload rejection.
- Registration, duplicate email rejection, $0 opening balance, client-supplied role/balance ignored.
- Profile settings persistence.
- Wrong-current-password rejection, password change, session revocation and new-password login.
- Admin freeze invalidates sessions and prevents login; re-enable works; admin self-freeze rejected.
- Logout invalidates replayed session cookies.
- Security response headers.

`test_concurrent_transfers_cannot_overdraw` verified:

- A customer funded with $1 attempts two simultaneous $0.75 transfers with different request keys.
- Exactly one succeeds; the other returns insufficient funds.
- Remaining balance is $0.25 and total funds are conserved.
- Synthetic test funds are returned through normal transfers.

## Browser checks

- Customer sign-in and dashboard rendering: PASS.
- Transfer entry, review, confirmation, transaction history: PASS. Alex sent Sam $25 of fictional funds.
- Profile phone save: PASS.
- Logout and administrator login: PASS.
- Admin customer table, totals and audit trail: PASS.
- Dashboard screenshot delivered separately.

The browser checks complement API integration tests; upload/download and password change were verified through actual HTTP requests, not through the browser UI. Mobile styles are implemented but were not exhaustively tested across devices.

## Limitations

Docker Compose is supplied but **not executed** because Docker Desktop was absent. This is a local practice baseline, not an independent security audit or a production banking system. Test activity remains in the transaction/audit history, and synthetic $0 test customers remain visible to the administrator. No intentional vulnerabilities were added. No public exposure, real payments, real customer information or external messaging was used.

## Final security assessment - VB-001 through VB-006

The original baseline results above remain as historical evidence.
Subsequently, six controlled vulnerabilities were demonstrated and
remediated on the `security-lab` branch.

| Finding | Assessment result | Documentation |
|---|---|---|
| VB-001 - IDOR | Remediated | `security/findings/VB-001-IDOR.md` |
| VB-002 - Stored HTML Injection | Remediated | `security/findings/VB-002-Stored-HTML-Injection.md` |
| VB-003 - SQL Injection | Remediated | `security/findings/VB-003-SQL-Injection.md` |
| VB-004 - OS Command Injection | Remediated | `security/findings/VB-004-Command-Injection.md` |
| VB-005 - CSRF | Remediated | `security/VB-005-CSRF.md` |
| VB-006 - Vertical Privilege Escalation | Remediated | `security/VB-006-Vertical-Privilege-Escalation.md` |

### Final automated regression verification

Command executed against the running local application:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/test_flows.py -v
```

Observed result: **6 passed in 16.99 seconds**.

VB-006 additionally verified that its synthetic administrator
maintenance endpoint returns HTTP 401 for anonymous requests,
HTTP 403 for authenticated customers, and HTTP 200 for administrators.

The vulnerable VB-006 checkpoint was committed as `1ecf554`.
The verified remediation and regression test were committed as `d50fa9b`.

### Scope and limitations

All demonstrations used synthetic banking data in a local laboratory.
The regression suite provides evidence for the tested behaviors,
not proof that the application is free of every vulnerability.

Docker Compose was not runtime-verified in this environment.
The project is not a production banking application or a certified
security assessment.
