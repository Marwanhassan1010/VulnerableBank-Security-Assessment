\# VB-002 — Stored HTML Injection / XSS Assessment



\## 1. Finding Summary



| Field | Details |

|---|---|

| Finding ID | VB-002 |

| Application | VulnerableBank |

| Category | Stored HTML Injection / Potential Stored XSS |

| CWE | CWE-79 — Improper Neutralization of Input During Web Page Generation |

| OWASP Mapping | A03:2021 — Injection |

| Affected Component | Authenticated dashboard greeting |

| Input Source | User-controlled profile name |

| Testing Environment | Localhost-only security laboratory with synthetic accounts |

| Status | Remediated — Manual Verification Completed |

| JavaScript Execution | Not demonstrated |

| Cross-User Impact | Not demonstrated |

| CVSS Score | Not assigned; exploitability and impact not sufficiently established |



\## 2. Executive Summary



During a controlled assessment of VulnerableBank, an intentionally unsafe React rendering pattern was introduced into the authenticated dashboard greeting.



The application stores a user-controlled profile name. When the dashboard rendered this value through React's `dangerouslySetInnerHTML`, HTML markup contained in the profile name was interpreted by the browser instead of being displayed as text.



A test payload caused the browser to create an SVG element, confirming HTML injection.



However, JavaScript execution was not demonstrated. The application's original Content Security Policy (CSP) blocked inline event handlers. JavaScript execution also remained unconfirmed during a temporary, controlled CSP relaxation.



The vulnerable rendering pattern was removed, and the dashboard was restored to React's standard text rendering.



\## 3. Affected Functionality



\*\*Input:\*\* Profile name updated through `PATCH /api/profile`.



\*\*Storage:\*\* The submitted profile name was persisted by the backend.



\*\*Output:\*\* Dashboard greeting on the Overview page.



\*\*Root cause:\*\* User-controlled data was passed to an HTML interpretation sink rather than rendered as ordinary React text.



\## 4. Controlled Reproduction



The following test was performed exclusively in the local VulnerableBank laboratory.



1\. An intentionally vulnerable dashboard greeting was introduced on the `security-lab` branch using `dangerouslySetInnerHTML`.

2\. The synthetic Alex account was used to update its profile name.

3\. The following test value was submitted:



&#x20;  `<svg/onload=alert(1)>`



4\. The dashboard was refreshed.

5\. The browser interpreted the supplied markup as an SVG element instead of displaying the literal characters.

6\. Browser inspection confirmed that the injected element existed in the DOM.



The observed element included:



`<svg onload="alert(1)">.</svg>`



\*\*Confirmed result:\*\* Stored HTML injection.



\*\*Not confirmed:\*\* Successful execution of the injected JavaScript, impact on another user, or a demonstrated session-compromise scenario.



\## 5. Content Security Policy Assessment



The original application CSP included:



`script-src 'self'`



During testing, the browser reported that the inline event handler was blocked by the CSP.



For controlled investigation, the script directive was temporarily changed to include `'unsafe-inline'`. JavaScript execution still was not demonstrated.



The original CSP was restored afterward, and the active HTTP response header was checked.



\*\*Conclusion:\*\* CSP provided an observed defense-in-depth barrier during the initial test. It should not be treated as a replacement for safe output rendering.



\## 6. Remediation



The unsafe `dangerouslySetInnerHTML` rendering pattern was removed.



The dashboard greeting was restored to standard React text rendering:



```jsx

<h1>{page==='Overview'?`Welcome back, ${user.name.split(' ')\[0]}.`:page}</h1>

```



This allows React to handle the profile name as text rather than HTML markup.



The original restrictive script CSP was also restored.



\## 7. Verification Evidence



The following results were observed:



\- Frontend production build completed successfully.

\- Source inspection found no `dangerouslySetInnerHTML` usage.

\- The browser displayed the test payload literally as text after remediation.

\- The synthetic Alex profile name was changed back to `Alex Morgan`.

\- The original CSP was restored and its live response header verified.

\- Automated banking integration test passed:



&#x20; `backend/test\_flows.py::test\_complete\_banking\_baseline PASSED`



&#x20; `1 passed in 1.48s`



\- Git working tree was verified clean on the `security-lab` branch.



\*\*Verification limitation:\*\* The automated banking integration test confirms existing banking functionality but is not a dedicated HTML-injection regression test. The injection-specific remediation was verified manually.



\## 8. Security Recommendations



1\. Continue rendering untrusted values using React's normal text interpolation.

2\. Avoid `dangerouslySetInnerHTML` for user-controlled content.

3\. If HTML rendering becomes necessary, apply an appropriately configured HTML sanitizer.

4\. Maintain a restrictive CSP as defense in depth.

5\. Add a dedicated automated regression test to verify that profile names containing HTML-like strings are displayed as text.

6\. Review other user-controlled fields for unsafe HTML rendering.



\## 9. Final Assessment



\*\*VB-002 is remediated and manually verified.\*\*



The assessment demonstrated that unsafe rendering of a stored profile name could produce HTML injection in the authenticated dashboard.



The available evidence does not establish successful JavaScript execution or cross-user exploitation. The finding is therefore documented as \*\*Stored HTML Injection / Potential Stored XSS\*\*, not as a confirmed exploitable stored-XSS attack.



This finding forms part of the VulnerableBank custom web application security assessment portfolio.

