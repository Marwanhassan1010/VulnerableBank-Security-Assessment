
# VB-004 — OS Command Injection

## Finding Summary

- **Finding ID:** VB-004
- **Vulnerability:** OS Command Injection
- **CWE:** CWE-78 — Improper Neutralization of Special Elements used in an OS Command
- **Application:** VulnerableBank
- **Environment:** Local Windows security lab
- **Affected endpoint:** `GET /api/lab/diagnostics/ping`
- **Authentication:** Required
- **Status:** Remediated and regression-tested

## Vulnerability Description

The diagnostic endpoint accepted a user-controlled `host` parameter and inserted it directly into a Windows shell command.

The backend executed the resulting command using Python's `subprocess.run()` with `shell=True`.

This allowed shell metacharacters in the input to alter the command executed by the operating system.

## Vulnerable Implementation

```python
command = f"ping -n 1 {host}"

result = subprocess.run(
    command,
    shell=True,
    capture_output=True,
    text=True,
    timeout=5
)
```

## Proof of Concept

### Legitimate Request

```http
GET /api/lab/diagnostics/ping?host=127.0.0.1
```

Observed result:

- HTTP 200
- Command: `ping -n 1 127.0.0.1`
- Return code: `0`
- Successful loopback ping

### Injection Payload

```text
127.0.0.1 & echo VB004_INJECTION_CONFIRMED
```

URL-encoded request:

```http
GET /api/lab/diagnostics/ping?host=127.0.0.1%20%26%20echo%20VB004_INJECTION_CONFIRMED
```

The vulnerable backend constructed:

```cmd
ping -n 1 127.0.0.1 & echo VB004_INJECTION_CONFIRMED
```

### Observed Evidence

The server returned the following command output:

```text
Ping statistics for 127.0.0.1:
    Packets: Sent = 1, Received = 1, Lost = 0 (0% loss)

VB004_INJECTION_CONFIRMED
```

The marker confirms that the operating system executed a second command supplied through the `host` parameter.

## Security Impact

An authenticated user could cause the backend to execute additional operating-system commands with the privileges of the application process.

Potential consequences depend on the operating-system permissions and deployment environment.

The demonstrated impact was limited to executing a harmless `echo` command in a localhost-only synthetic lab.

No destructive commands, privilege escalation, or access to sensitive files were tested.

## Root Cause

The application combined untrusted user input with a shell command string and executed it using `shell=True`.

On Windows, the `&` metacharacter separates commands when interpreted by the command shell.

## Remediation

The endpoint was updated to:

1. Accept only the loopback address `127.0.0.1`.
2. Reject all other input with HTTP 422.
3. Execute `ping` using a list of arguments.
4. Set `shell=False`.
5. Handle command timeouts.

Secure command execution:

```python
if host != '127.0.0.1':
    raise HTTPException(
        status_code=422,
        detail='Only the local loopback address is permitted'
    )

command = ['ping', '-n', '1', host]

result = subprocess.run(
    command,
    shell=False,
    capture_output=True,
    text=True,
    timeout=5
)
```

The complete implementation also handles `subprocess.TimeoutExpired`.

## Remediation Verification

### Legitimate Request

After remediation, the loopback request returned HTTP 200 with:

```json
{
  "command": ["ping", "-n", "1", "127.0.0.1"],
  "returncode": 0
}
```

The response also contained successful ping output.

### Original Injection Payload

The original injection payload was rejected.

Observed response:

```json
{
  "detail": "Only the local loopback address is permitted"
}
```

The injected command marker was not returned as executed command output.

### Automated Regression Testing

Test:

`backend/test_flows.py::test_vb004_command_injection_prevention`

Result:

```text
1 passed in 0.33s
```

The test covers:

- Authentication enforcement
- Successful legitimate loopback ping
- Safe command argument structure
- Rejection of the original injection payload
- Rejection of non-loopback destinations

### Banking Baseline

Test:

`backend/test_flows.py::test_complete_banking_baseline`

Result:

```text
1 passed in 1.58s
```

## Git Evidence

- **Vulnerable checkpoint:** `8168a6f`
- **Remediation and regression test:** `ffc2112`
- **Branch:** `security-lab`

## Conclusion

VB-004 demonstrated authenticated OS command injection through unsafe shell command construction.

The original payload successfully executed a second command in the vulnerable implementation.

The endpoint was subsequently remediated using strict input validation and shell-free subprocess execution.

Manual verification, the dedicated regression test, and the banking baseline passed.
