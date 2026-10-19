# VB-003 — SQL Injection with Cross-Account Transaction Disclosure

**Project:** VulnerableBank  
**Finding ID:** VB-003  
**Category:** SQL Injection / Broken Access Control  
**CWE:** CWE-89 — Improper Neutralization of Special Elements used in an SQL Command  
**OWASP Top 10 (2021):** A03 — Injection; A01 — Broken Access Control  
**Status:** Remediated and regression-tested  
**Environment:** Localhost-only FastAPI application with PostgreSQL and synthetic banking data

## 1. Executive Summary

An intentionally vulnerable transaction search endpoint was introduced into the local VulnerableBank security laboratory to demonstrate SQL injection and its impact on account-level authorization.

The endpoint interpolated user-controlled search input directly into a SQL query. An authenticated synthetic customer, Alex, could manipulate the SQL predicate to retrieve transactions belonging to other synthetic accounts.

The attack returned 29 transactions, including three confirmed transactions involving neither Alex nor Alex's account.

The vulnerability was remediated using SQLAlchemy parameterized SQL, preserving account ownership filtering and the 25-result limit.

## 2. Affected Endpoint

**Method:** GET  
**Path:** `/api/lab/transactions/search`  
**Parameter:** `q`  
**Authentication:** Required

The endpoint searches transaction memos belonging to the authenticated user's account.

## 3. Root Cause

The vulnerable implementation constructed SQL using Python f-strings:

```python
query = (
    f"SELECT id, memo, amount FROM transfers "
    f"WHERE (source_id = {account.id} OR target_id = {account.id}) "
    f"AND memo ILIKE '%{q}%' "
    f"LIMIT 25"
)

rows = db.execute(text(query)).mappings().all()
```

The user-controlled `q` value was inserted directly into the SQL command instead of being passed as a bound parameter.

Consequently, SQL operators and comment syntax supplied by the user could change the query's intended logic.

## 4. Proof of Concept

**Authenticated user:** Alex (synthetic customer)

**Normal search:**

`GET /api/lab/transactions/search?q=test`

**Observed result:** 16 transactions matching the search term.

**SQL injection payload:**

```text
' OR 1=1 --
```

**Encoded request:**

`GET /api/lab/transactions/search?q=%27%20OR%201%3D1%20--%20`

**Observed result:** 29 transactions.

The injected `OR 1=1` condition made the query predicate true for transactions outside Alex's account. The SQL comment also suppressed the trailing search syntax and `LIMIT 25`.

## 5. Confirmed Unauthorized Data Exposure

Alex's normal transaction history returned 26 records.

The injected search returned 29 records. Comparison of transaction IDs identified three additional records absent from Alex's authorized history.

Direct database ownership verification established that these three transactions belonged to other synthetic accounts:

| Transaction ID | Sender | Receiver |
|---|---|---|
| `55282ddd-1f4e-44b3-8501-97a950f08037` | `race-cf0fd649343a@example.com` | `sam@vulnerablebank.test` |
| `2842b9b6-0c19-4db4-b415-320170d6c199` | `race-fadd9e8cfea0@example.com` | `sam@vulnerablebank.test` |
| `4a3c2a93-aa95-4813-ab22-f5ef22f6015b` | `race-d8210e939796@example.com` | `sam@vulnerablebank.test` |

Neither the sender nor receiver of these transactions was Alex.

**Confirmed impact:** Authenticated cross-account transaction disclosure through SQL injection.

No evidence was collected of transaction modification, credential extraction, or database destruction. Those impacts are not claimed.

## 6. Remediation

The vulnerable SQL interpolation was replaced with parameterized SQL:

```python
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
```

Bound parameters ensure that the supplied search string is treated as data rather than SQL syntax.

The account ownership predicate and result limit remain part of the SQL statement.

## 7. Verification After Remediation

| Verification | Observed result |
|---|---|
| Python syntax validation | Passed |
| Backend startup and HTTP health check | HTTP 200 |
| Original SQL injection payload | Empty JSON array (`[]`) |
| Legitimate search `q=test` | 16 matching transactions |
| Banking baseline integration test | 1 passed |
| Dedicated VB-003 security regression test | 1 passed |

**Regression test:** `backend/test_flows.py::test_vb003_sql_injection_prevention`

The regression test checks authentication, legitimate searching, the original injection payload, transaction-history-based ownership comparison, and the 25-result limit.

The ownership comparison was validated against the current synthetic dataset; it is not a substitute for independent database ownership verification in larger datasets.

## 8. Git Evidence

**Vulnerable implementation:** `c783d2e`  
**Remediation and regression test:** `a47aa75`  
**Branch:** `security-lab`

## 9. Security Lessons

- Authentication alone does not prevent SQL injection.
- SQL injection can undermine authorization predicates, not just data integrity.
- User-controlled values must be passed as bound SQL parameters.
- Remediation should be validated with the original attack payload.
- Regression tests help prevent previously discovered vulnerabilities from reappearing.

## 10. Scope and Limitations

All testing was performed against a local-only VulnerableBank environment using synthetic users and transactions.

The proof of concept establishes unauthorized read access to three transaction records. It does not establish arbitrary database access, write access, or remote compromise.