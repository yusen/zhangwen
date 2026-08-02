# GitHub Upload Plan

Date: 2026-07-09

## Current State

- Branch: `codex/zw-005-016-autonomous`
- Active task: `tasks/ZW-UX-002-four-expert-project-workspace.md`
- Publish status: user confirmed target repository and branch-only upload. This plan is committed with the upload scope; check `git log -1`, `git status`, and remote branch state for the final commit/push result.
- GitHub remote: `origin` is configured as `https://github.com/yusen/ZW_V1.git`.
- GitHub CLI: `gh` is not installed or not on `PATH`.

## Proposed Upload Scope

The upload should include the Zhangwen product work completed through ZW-016 plus the UX-001/UX-002 follow-up work currently in the worktree:

- Contracts updates for schema v17 and four-expert project workspace models.
- Desktop UI updates for one-sentence project creation, expert navigation, central project overview/expert chat, right-panel work/artifact/device behavior, and related tests.
- Sidecar backend updates for migrations, project experts, expert conversations, shared context/coordinator state, artifacts, solution revision, devices, LLM error handling, and MVP readiness.
- Test updates covering desktop project isolation, project workspace behavior, right panel behavior, backend migration/project/chat/artifact/code/device flows, and historical ZW-004 through ZW-015 schema expectations.
- Documentation and task records: `CURRENT_TASK.md`, `HANDOFF.md`, `docs/API_EVENTS.md`, `docs/DECISIONS.md`, `tasks/ZW-016-mvp-integration-hardening.md`, `tasks/ZW-UX-001-conversation-driven-workflow.md`, and `tasks/ZW-UX-002-four-expert-project-workspace.md`.
- New source/test files:
  - `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`
  - `apps/desktop/src/components/chat/ConversationResponseCard.tsx`
  - `services/local-api/zhangwen/chat/idea_flow.py`
  - `services/local-api/zhangwen/devices/serial_discovery.py`

## Explicit Exclusions

Do not stage or upload:

- `.codex/config.toml` because it is local Codex configuration and unrelated to the product/task changes.
- `.venv/`, `venv/`, `node_modules/`, `.pnpm-store/`, `dist/`, `target/`, `apps/desktop/src-tauri/target/`, `.env`, `.env.local`, `*.env.local`, `.data/`, logs, coverage outputs, IDE files, and OS metadata. These are covered by `.gitignore` and are not currently tracked as upload candidates.
- Real API keys, Wi-Fi credentials, real serial identifiers, user private data, build caches, or hardware-generated files.

## Validation Already Available

Recent recorded validation for UX-002:

- `pnpm --filter @zhangwen/contracts build` passed.
- `pnpm --filter @zhangwen/contracts typecheck` passed.
- `pnpm --filter @zhangwen/desktop typecheck` passed.
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace RightPanel ProjectIsolation` passed: 7 files / 53 tests, with existing React `act(...)` warnings.
- `pnpm --filter @zhangwen/desktop test` passed: 7 files / 53 tests, with the same warnings.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` passed: 107 tests, with known Starlette and Windows pytest temp cleanup warnings.
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen` passed.
- `pnpm --filter @zhangwen/desktop build` passed.
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` passed.
- `git diff --check` passed with LF/CRLF warnings only.

## Required Before Push

1. Confirm the exact staged scope:
   - Stage all current product/task changes except `.codex/config.toml`, or
   - Narrow the upload to a smaller subset.
2. Run a final sensitive-data scan and `git diff --check` immediately before staging/commit.
3. Stage explicit paths only; do not stage `.codex/config.toml` while it remains dirty.

## Proposed Commit

- Branch: keep `codex/zw-005-016-autonomous`
- Commit message: `Prepare Zhangwen UX expert workspace`
- Push command after confirmation and remote setup: `git push -u origin codex/zw-005-016-autonomous`
- Pull request: not requested; branch push only.

## Push Attempts

- Local commit was created successfully; use `git log -1 --oneline` for the exact current commit hash.
- `git push -u origin codex/zw-005-016-autonomous` failed twice with `Recv failure: Connection was reset`.
- `git ls-remote origin` failed with `Failed to connect to github.com port 443 after 21038 ms`.
- `git -c http.version=HTTP/1.1 -c http.postBuffer=524288000 push -u origin codex/zw-005-016-autonomous` failed with `Failed to connect to github.com port 443 after 21082 ms`.
- Current blocker is network/proxy access to `github.com:443`, not staged content. Retry the push after network access is restored.

## Manual Validation Still Outside Upload

- Real DeepSeek paid model calls.
- Real serial hardware enumeration.
- ESP32 plug/unplug behavior, occupied-port behavior, upload logs, and hardware smoke tests.
- Real `mpremote`, `esptool`, Flash erase, firmware flashing, or device file overwrite. These must not be performed without explicit confirmation.
