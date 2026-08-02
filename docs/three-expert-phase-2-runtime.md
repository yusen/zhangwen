# Three Expert Phase 2: Runtime, Entry Router, and Skill Registry

Generated: 2026-07-10

Scope: implement the three-teacher runtime layer without large UI changes, without real paid LLM calls in tests, and without adding child agents.

## Implemented

- Added runtime expert config and prompt loading in `services/local-api/zhangwen/experts/config.py`.
- Added independent prompt assets under `services/local-api/zhangwen/experts/prompts/` for:
  - `entry-router`
  - `problem-guide`
  - `smart-engineer`
  - `structure-engineer`
  - `project-coordinator`
- Added invisible `EntryRouter` in `services/local-api/zhangwen/experts/entry_router.py`.
- Added `ContextAssembler` in `services/local-api/zhangwen/experts/context_assembler.py`.
- Exported the runtime APIs from `services/local-api/zhangwen/experts/__init__.py`.
- Connected `ProjectRepository.suggest_project()` to `EntryRouter`, while leaving project creation, workspaces, drafts, and layout unchanged.
- Extended Skill contracts and backend models with:
  - `ownerExpert`
  - `requiredTools`
  - `riskLevel`
  - `confirmationPolicy`
  - `artifactTypes`
- Registered the required `smart_engineer` skills in `services/local-api/zhangwen/skills/registry.py`.

## EntryRouter

The router returns:

- `intent`
- `projectName`
- `initialExpert`
- `recommendedExperts`
- `confidence`
- `reason`
- `requiresClarification`

Validation uses a local implementation of the `router-output.schema.json` contract because the backend currently has no `jsonschema` dependency. The runtime enforces required fields, no extra fields, canonical expert enums, unique recommended experts, length bounds, confidence bounds, and `initialExpert` inclusion.

Routing behavior:

- Explicit user-selected expert has priority.
- Explicit expert mentions in the text have priority.
- Model output is validated.
- On validation failure, the model path retries once.
- After two invalid outputs, deterministic rules are used.
- Ambiguous or multi-domain unclear requests default to `problem_guide`.
- Internal JSON, prompts, and routing reasoning are not exposed through project suggestion responses.

Automated tests inject fake router models; no real paid LLM call is made.

## Skill Registry

The following are Skills owned by `smart_engineer`, not Agents and not child Agents:

- `hardware-selection`
- `bom-generation`
- `io-map`
- `wiring`
- `electrical-check`
- `micropython-generation`
- `arduino-generation`
- `code-review`
- `mock-test`
- `iot-mqtt`
- `iot-http`
- `data-acquisition`
- `data-analysis`
- `ai-deployment`
- `vision-inference`
- `project-packaging`

Each declares input schema, output schema, required tools, risk level, confirmation policy, artifact types, and permissions.

The existing `services/local-api/zhangwen/orchestrator/registry.py` remains the internal task-agent registry. It does not register the three user-visible teachers or the smart-engineer Skills as Agents.

## ContextAssembler

`ContextAssembler` intentionally does not inject full chat history.

It reads only minimal shared state:

- `projects`
- `project_shared_facts`
- `project_shared_contexts`
- `project_decisions`
- `artifacts`
- `artifact_versions`
- `artifact_dependencies`
- `device_sessions`
- `project_coordinator_states`

It does not read:

- `messages`
- `expert_drafts`
- `expert_private_memories`

Confirmed facts are sorted ahead of proposed facts and model summaries. Device session logs are not injected; only minimal device identity/status metadata is included for `smart_engineer`.

### 2026-07-10 completion-repair addendum

The active `smart_engineer` runtime now also performs bounded retrieval from the existing local hardware library. The assembler idempotently ensures the built-in public component catalog exists, ranks entries against the current user message, and injects at most four matches. Each match contains only component identity, category, electrical/driver parameters, safety tags, and a short note; stock, price, timestamps, full device logs, private data, and unrelated chat remain excluded. If the local catalog cannot be read, context assembly degrades to an empty public-knowledge list instead of blocking the conversation.

## Tests Added

New test file:

- `services/local-api/tests/test_three_expert_runtime.py`

Coverage:

- Three expert configs load independent prompts and boundaries.
- Smart engineer capabilities are registered as Skills and not Agents.
- EntryRouter respects explicit expert selection.
- Ambiguous requests default to `problem_guide`.
- Invalid model output retries once.
- Two invalid model outputs fall back to deterministic rules.
- ContextAssembler includes shared facts, decisions, upstream artifacts, and devices without chat messages, private drafts, or device logs.
- ContextAssembler retrieves at most four relevant public hardware entries and excludes inventory/audit metadata.

## Validation

Passed:

- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen services/local-api/tests/test_three_expert_runtime.py`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_three_expert_runtime.py services/local-api/tests/test_zw008_skills_model_router.py -q --rootdir services/local-api`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -q --rootdir services/local-api`
- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` passed: 115 tests.
- `git diff --check`

No lint script exists in `package.json`, `packages/contracts/package.json`, or `apps/desktop/package.json`; `git diff --check`, TypeScript typecheck, Python compileall, and pytest were used as the available static/validation coverage.

Known existing test noise:

- FastAPI/Starlette `TestClient` deprecation warning.
- Windows pytest temp cleanup `PermissionError` after successful test completion.

## Not Implemented In This Phase

- No large desktop UI layout changes.
- No visible router JSON or prompt exposure.
- No real LLM router call wired into project creation.
- No ProjectCoordinator runtime workflow.
- No ToolRunner consolidation.
- No child Agent or sub-Agent implementation.
- No SQLite schema change beyond Phase 1 v19.
