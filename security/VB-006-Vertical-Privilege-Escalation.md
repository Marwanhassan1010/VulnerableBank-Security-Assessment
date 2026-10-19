# VB-006 ? Vertical Privilege Escalation / Incorrect Authorization

## Classification

- **Finding ID:** VB-006
- **Category:** Broken Access Control
- **CWE:** CWE-863 ? Incorrect Authorization
- **Affected endpoint:** `GET /api/lab/admin/maintenance-status`
- **Environment:** VulnerableBank isolated security laboratory
- **Scope:** Synthetic, read-only administrator maintenance status

## Summary

A deliberately vulnerable laboratory endpoint required an authenticated
session but failed to enforce administrator-level authorization.

As a result, a regular customer could access a synthetic operation
designated for administrators.

This finding demonstrates an authorization bypass, not a compromise
of real banking administration functionality.

## Root Cause

The vulnerable endpoint used:

```python
user=Depends(current)
```

The `current` dependency validated the user's session but did not
require the `admin` role.

Authentication alone was therefore insufficient to protect the
administrator-designated endpoint.

## Reproduction Evidence

The following HTTP responses were observed before remediation:

| Identity | HTTP status |
|---|---|
| Anonymous visitor | 401 |
| Authenticated customer | 200 |
| Administrator | 200 |
| Customer accessing real `/api/admin` | 403 |

The customer response of HTTP 200 confirmed that a non-administrator
could access the synthetic administrator operation.

The real `/api/admin` endpoint remained protected.

## Vulnerable Git Checkpoint

- **Branch:** `security-lab`
- **Commit:** `1ecf554`
- **Commit message:** `lab(vb-006): demonstrate synthetic admin authorization bypass`

## Remediation

The endpoint was changed to use the existing administrator
authorization dependency:

```python
user=Depends(admin)
```

This dependency requires a valid authenticated session and verifies
that the user's role is `admin`.

The endpoint function was also renamed to
`secure_admin_maintenance_status`.

## Post-Remediation Verification

The following HTTP responses were observed after remediation:

| Identity | HTTP status | Expected |
|---|---|---|
| Anonymous visitor | 401 | 401 |
| Authenticated customer | 403 | 403 |
| Administrator | 200 | 200 |
| Customer accessing real `/api/admin` | 403 | 403 |

All four live authorization checks passed.

## Automated Regression Test

Test function:

`backend/test_flows.py::test_vb006_admin_authorization_remediation`

Command:

```powershell
.\.venv\Scripts\python.exe -m pytest backend/test_flows.py::test_vb006_admin_authorization_remediation -v
```

Observed result:

`1 passed in 0.65s`

The regression test covers anonymous, customer, and administrator
access, the expected synthetic response body, and continued
protection of the real administrator endpoint.

## Security Impact and Scope

The laboratory weakness illustrates how an application can correctly
authenticate a user while incorrectly authorizing access to a
privileged operation.

In this controlled demonstration, the endpoint was synthetic and
read-only. No actual banking administrator privileges, user management
operations, or account modifications were obtained.

## Status

- Vulnerability reproduced: PASS
- Vulnerable checkpoint committed: PASS
- Remediation implemented: PASS
- Live authorization verification: PASS
- Targeted regression test: PASS
- Full regression suite: PASS (6 passed in 16.99s)
- Final remediation commit: Pending
