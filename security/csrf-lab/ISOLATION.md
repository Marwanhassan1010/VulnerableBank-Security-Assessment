# VB-005 HTTPS isolation

The bank remains at http://127.0.0.1:8000. Cookies do not isolate ports.
Use https://localhost:9443 for the synthetic HTTPS lab; never use its IP URL.
The lab binds only IPv4 loopback and rejects other Host headers. It never logs
requests or cookie values and refuses requests containing a vb_session cookie.
These checks are defense in depth: hostname separation prevents normal browser
cookie delivery; rejecting a request cannot undo a cookie already delivered.

Start from the project root: python security/csrf-lab/https_server.py
Use the existing certificate only if it is valid for localhost.

Firefox acceptance check:
1. Keep the banking tab on 127.0.0.1. Do not sign in to the bank on localhost.
2. Visit https://localhost:9443. Expected: PASS: banking session cookie absent.
3. In Firefox Network, verify the request hostname is localhost and that cookie
   names exclude vb_session. Do not copy headers or cookie values.
4. For a cross-site synthetic form test, serve a separate HTML form from
   http://127.0.0.1:9001 targeting https://localhost:9443 with method POST.
   Only the synthetic lab cookie should be eligible; browser privacy rules may
   still block it. Do not change bank cookie flags or CSRF validation to force it.
5. Stop the lab when finished. Do not change the existing attacker.html bank test.

A PASS is meaningful for the current browser request only. Automated synthetic
cookie checks do not establish the state of an existing Firefox profile.

## Verification recorded 2026-10-19

- User reported Firefox displayed: PASS: banking session cookie absent; HTTPS laboratory ready.
  This confirms the lab did not receive vb_session on that localhost request.
  An independent Firefox Network-panel inspection was not reported.
- Five handler checks and a synthetic hostname cookie-scope check passed.
- Automated live TLS verification disconnected and is not recorded as passed.
- After the user stopped the lab, no listener was found on port 9443.
- Banking API health remained ok with PostgreSQL.
- backend/main.py and the existing attacker.html match HEAD; backend CSRF protections were not changed.
- Cross-site synthetic POST verification in Firefox remains a separate, uncompleted exercise.
