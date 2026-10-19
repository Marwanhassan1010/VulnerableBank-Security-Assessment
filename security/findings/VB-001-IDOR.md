# VB-001 — Insecure Direct Object Reference (IDOR)



## Finding Summary



- Application: VulnerableBank
- Finding ID: VB-001
- Vulnerability: Broken Access Control (IDOR)
- CWE: CWE-639
- Severity: High (provisional)
- Status: Remediated — Verified
- Environment: Local authorized security laboratory
- Affected endpoint: GET /api/documents/{doc\_id}/download



## Description



The document download endpoint authenticates the requesting user but does not verify ownership of the requested document.



Consequently, an authenticated customer who knows another customer's document ID can download that customer's private document.



## Root Cause



The vulnerable database query checks only the document ID:



&#x20;   select(Document).where(Document.id == doc\_id)



It does not verify that Document.user\_id matches the authenticated user's ID.



## Reproduction Steps



1\. Log in as fictional customer Alex.

2\. Upload a synthetic text document named alex-idor-test.txt.

3\. Record the document ID from GET /api/documents.

4\. Log out and authenticate as fictional customer Sam.

5\. Request Alex's document using:

&#x20;  GET /api/documents/{doc\_id}/download

6\. Observe that the server returns the document.



## Evidence



Automated integration test:



- Test: test\_complete\_banking\_baseline
- File: backend/test\_flows.py
- Assertion: Expected HTTP 404 for Sam's request.
- Actual result: HTTP 200 OK.
- Result: Test failed at line 66, confirming unauthorized access.



Manual browser verification:



- Authenticated account: Sam
- Document owner: Alex
- Document: alex-idor-test.txt
- Actual result: Download succeeded.
- Content: Synthetic test document matched the original.



## Security Impact



An authenticated user may access another customer's private documents when the document identifier is known.



Potential consequences include unauthorized disclosure of confidential customer information.



The exercise used fictional accounts and synthetic data only.



## Recommended Remediation



Enforce document ownership in the database lookup:



&#x20;   select(Document).where(

&#x20;       Document.id == doc\_id,

&#x20;       Document.user\_id == user.id

&#x20;   )



Return HTTP 404 when the document does not exist or does not belong to the authenticated user.



## Verification Criteria



After remediation:



- Alex can download Alex's document.
- Sam cannot download Alex's document.
- Sam receives HTTP 404.
- Document deletion remains ownership-protected.
- Existing integration tests pass.



## Git Evidence



- Branch: security-lab
- Vulnerable implementation commit: 4ebabbe







## Remediation Results



The document download endpoint was corrected to use the existing

owned\_document(db, user, doc\_id) authorization helper.



### Manual Retesting



- Sam attempted to download Alex's private document.

- Result: Document not found; unauthorized download blocked.

- Alex downloaded the same document using his own account.

- Result: Download succeeded and contents matched.



### Automated Regression Testing



- Command: .\\.venv\\Scripts\\python.exe -m pytest backend/test\_flows.py::test\_complete\_banking\_baseline -v

- Result: PASSED

- Tests: 1 passed

- Execution time: 1.48 seconds



### Final Assessment



VB-001 is remediated and verified in the local test environment.



The vulnerable implementation remains preserved in Git commit 4ebabbe

on the security-lab branch history.

```



Save with \*\*Ctrl + S\*\*, then close Notepad.



\*\*Reply `Done` when saved.\*\*



Next, we'll verify the report and commit the remediation to Git, completing the full discovery → exploitation → remediation → validation lifecycle for our first VulnerableBank finding.

