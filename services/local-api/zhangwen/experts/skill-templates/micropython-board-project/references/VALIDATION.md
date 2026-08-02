# Validation And Device Boundaries

## Local Validation

Run these checks in controlled local subprocesses with fixed arguments, `shell=false`, bounded workspaces, timeouts, and no real device or network access:

1. Static safety: fixed paths, content limits, hardcoded credential patterns, forbidden host capabilities, and unsupported imports.
2. Syntax: compile every Python file without importing or executing project code.

For every executed check, derive `PASSED` only from exit code `0` and `FAILED` from any other real exit code. Output text such as `PASS` is diagnostic only. Mark skipped checks `NOT_RUN` with no exit code. Overall validation passes only when both checks ran and exited `0`. Do not import or execute user code and do not inject board mocks.

Saving a code edit creates a new version in an unvalidated state. Keep the prior version and its validation result unchanged. A failed version cannot be accepted or uploaded.

## Device Operations

Treat daily MicroPython upload and firmware flashing as separate workflows. USB serial file upload requires the local device flow, backup, port lock, timeout, cancellation, and observable post-upload validation. Flash erase and firmware flashing always require an explicit high-risk confirmation.

Automated tests must use mocks or dry runs. Do not scan serial ports, connect hardware, invoke `mpremote` or `esptool`, erase Flash, flash firmware, or claim hardware validation.
