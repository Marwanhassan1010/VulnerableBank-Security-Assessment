# VB-005 ? Cross-Site Request Forgery (CSRF)

## Finding summary

- **Category:** CWE-352 ? Cross-Site Request Forgery
- **Affected route:** `POST /api/lab/csrf/profile-address`
- **Environment:** Local, synthetic VulnerableBank security laboratory
- **Status:** Remediated; dedicated regression test passed
- **Impact:** Unauthorized modification of a synthetic customer's profile address would be possible if an authenticated request reached the vulnerable endpoint without effective cross-site restrictions.

## Root cause

The original endpoint manually authenticated requests using the `vb_session`
cookie but did not validate the application's `X-CSRF-Token` header.

The normal authentication dependency, `current()`, already implemented
CSRF-token verification for state-changing requests, but the laboratory
endpoint bypassed that dependency.

## Evidence and limitations

1. An authenticated HTTP client successfully submitted a profile-address
   update without a CSRF token before remediation.
2. The normal protected profile endpoint rejected a missing CSRF token.
3. The application's global middleware rejected an untrusted browser
   origin and requests marked `Sec-Fetch-Site: cross-site`.
4. The banking session cookie used `SameSite=Strict`.
5. Consequently, a successful browser-based cross-site CSRF attack
   against the actual banking endpoint was **not demonstrated**.
6. A separate, isolated synthetic HTTPS laboratory demonstrated a
   cross-site form POST with an automatically included synthetic cookie.
   Firefox reported `Sec-Fetch-Site: cross-site`, HTTP 200, and the
   synthetic `vb005_lab` cookie present.
7. The browser laboratory confirmed that the real banking cookie
   `vb_session` was absent from the synthetic request.

The synthetic HTTPS laboratory was not connected to the banking database
and did not establish a bypass of the real application's origin checks.

## Remediation

The affected route now uses `user: User = Depends(current)`.

This reuses the existing authentication and CSRF-token validation
instead of authenticating solely through the session cookie.

The existing global origin checks and session-cookie protections
remain unchanged.

## Regression verification

The test `test_vb005_csrf_remediation` verifies:

- Missing CSRF token: HTTP 403
- Invalid CSRF token: HTTP 403
- Untrusted Origin: HTTP 403
- Correct CSRF token: HTTP 200
- Rejected updates leave the synthetic address unchanged
- The original address is restored after the test

Observed results before the final function-name cleanup:

- Dedicated VB-005 test: **1 passed**
- Complete `backend/test_flows.py` suite: **5 passed**

The function-name cleanup subsequently passed Python syntax validation.
A final regression run is required before committing.

## Defensive lessons

- Apply CSRF protection consistently to every state-changing endpoint.
- Centralize session and CSRF checks in reusable dependencies.
- Keep origin validation and SameSite cookie restrictions as additional
  defenses rather than substitutes for CSRF-token verification.
- Distinguish a missing security control from a demonstrated exploitable
  browser attack.
- Keep all demonstrations isolated and use synthetic accounts and data.
