---
name: serial-device-safety
description: Implement or review ESP32 serial discovery, MicroPython upload, esptool flashing, mpremote operations, device logs, or related tests.
---

Treat serial file upload as the default. Require explicit approval for flash erase and firmware flashing. Use backups, idempotency keys, timeouts, port locks, cancellation, and post-upload observable validation. Provide a simulator or mock transport for automated tests. Never include real user serial identifiers or credentials in fixtures.
