---
name: verify-ui-contract
description: Review or test Zhangwen UI changes involving layout, right panel, artifacts, device views, or floating windows against docs/UI_CONTRACT.md.
---

Verify that MainConversation remains mounted and preserves draft, scroll, attachments, and references while right tabs and floating windows open. Verify right tabs remain Work/Artifacts/Device, all states have text labels, current solution is singular, and complex content uses floating windows. Add regression tests for every detected violation.
