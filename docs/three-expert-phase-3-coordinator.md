# Three Expert Phase 3: ProjectCoordinator

Date: 2026-07-10

## Scope

This phase implements the deterministic ProjectCoordinator domain layer for the three-teacher system. It does not change the main UI layout, does not add a user-visible agent, does not invoke real LLMs, and does not run hardware tooling.

Implemented:

- SharedFact lifecycle: `proposed -> confirmed -> superseded/rejected`.
- Experts can propose facts, but cannot directly overwrite a confirmed fact.
- Handoff state machine: `proposed -> accepted -> in_progress -> completed`, with rejected/cancelled terminal paths.
- Task state machine: `queued -> ready -> running -> completed`, with blocked/awaiting_user/failed/cancelled paths.
- PendingItem candidate queue with one highlighted open item per project.
- Highlight selection priority: `safety > blocking > conflict > confirmation > missing_input > normal`; ties use affected expert count, earlier creation time, then critical path.
- Artifact dependency index sync on artifact version upsert.
- Version-level outdated propagation from a newly confirmed upstream artifact version.

## Files Changed

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/index.ts`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/coordinator/__init__.py`
- `services/local-api/zhangwen/coordinator/service.py`
- `services/local-api/zhangwen/artifacts/repository.py`
- `services/local-api/tests/test_project_coordinator.py`
- `services/local-api/tests/test_project_repository.py`
- schema-version assertions in existing backend and desktop tests

## Schema v20

`services/local-api/zhangwen/projects/migrations.py` now sets `CURRENT_SCHEMA_VERSION = 20`.

Migration v20 adds:

- `project_shared_facts.key TEXT NULL`
- `project_pending_items.critical_path INTEGER NOT NULL DEFAULT 0`
- `project_tasks`
- `idx_project_tasks_project`
- `idx_project_shared_facts_key`
- `idx_artifact_dependencies_upstream_version`

Existing facts backfill `key = field` when no key exists. The migration is idempotent through `_add_column` and `CREATE TABLE/INDEX IF NOT EXISTS`.

## State Rules

Shared facts:

- `propose_shared_fact()` always creates a proposed fact.
- `confirm_shared_fact()` requires `confirmed_by`.
- A proposed fact with the same key does not affect existing confirmed facts.
- Confirming the replacement fact supersedes older confirmed facts with the same key.
- Rejected and superseded facts are not reopened by the coordinator service.

Pending items:

- All open items are re-ranked whenever the queue changes.
- The service clears project highlights before setting the selected one.
- The existing partial unique index remains the database guardrail for `is_highlighted = 1 AND status = 'open'`.

Artifacts:

- New dependencies must include upstream `artifactId` and `version`.
- `artifact_dependencies` is synchronized from every artifact version upsert.
- `propagate_outdated_from_confirmed_version()` marks downstream versions depending on older upstream versions as `STALE` and domain `outdated`.
- The artifact summary row is only marked outdated when its current version is affected.

## Data Examples

Before confirming a replacement fact:

```json
[
  {"id": "fact_a", "key": "target_user", "status": "confirmed", "value": "primary school students"},
  {"id": "fact_b", "key": "target_user", "status": "proposed", "value": "middle school students"}
]
```

After confirming `fact_b`:

```json
[
  {"id": "fact_a", "key": "target_user", "status": "superseded", "supersededBy": "fact_b"},
  {"id": "fact_b", "key": "target_user", "status": "confirmed", "confirmedBy": "user"}
]
```

Artifact dependency index:

```json
{
  "artifactId": "artifact_code_test",
  "artifactVersionId": "artifact_version_artifact_code_test_code_v1",
  "upstreamArtifactId": "artifact_spec_test",
  "upstreamVersionId": "artifact_version_artifact_spec_test_spec_v1",
  "upstreamVersion": 1
}
```

After upstream spec v2 is confirmed, the downstream code version depending on spec v1 becomes:

```json
{
  "status": "STALE",
  "domainStatus": "outdated",
  "staleReason": "Project Spec v2 confirmed"
}
```

## Rollback

There is no automatic down migration in the current handwritten migration system. To roll back this phase locally:

1. Restore a database backup from before opening it with schema v20.
2. Revert the code changes for schema v20, coordinator service, artifact dependency sync, tests, contracts and docs.
3. Do not manually set `PRAGMA user_version` downward on an already migrated database unless the new columns/tables and dependent data have been removed or the file is disposable.

## Validation

Passed:

- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen services/local-api/tests/test_project_coordinator.py`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_coordinator.py services/local-api/tests/test_project_repository.py -q --rootdir services/local-api` - 14 passed
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_three_expert_runtime.py services/local-api/tests/test_zw009_artifacts_windows.py services/local-api/tests/test_zw010_spec_agent.py services/local-api/tests/test_zw011_code_agent.py services/local-api/tests/test_zw013_cad_agent.py services/local-api/tests/test_zw014_lesson_agent.py services/local-api/tests/test_zw015_project_packages.py -q --rootdir services/local-api` - 31 passed
- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` - 119 passed
- `git diff --check` - no whitespace errors, LF/CRLF warnings only
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation RightPanel` - 53 passed

Known output remains unchanged:

- Starlette/FastAPI TestClient deprecation warning.
- Windows pytest temp cleanup `PermissionError` after successful test runs.
- WorkTab React `act(...)` warnings in existing desktop tests.
- No lint script exists in root, contracts, or desktop package scripts.
