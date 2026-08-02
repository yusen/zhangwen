# ZW-UX-003 — 三师系统迁移

## 1. 目标

将 UX-002 落地的四专家项目工作区增量迁移为用户可见的“三师系统”：

1. 问题引导师
2. 智能工程师
3. 结构工程师

主路由与项目协调器保持为用户不可见系统能力。嵌入式开发、IoT、数据分析、视觉 AI、AI 部署等能力归入智能工程师 Skill，不新增用户可见 Agent 或子 Agent。

## 2. 现状分析

### 2.1 当前技术栈

- 桌面端：Tauri + React + TypeScript + Vite + Vitest/Testing Library。
- 本地服务：Python FastAPI/WebSocket sidecar + SQLite。
- 共享契约：`packages/contracts` TypeScript 枚举和 API 类型。
- 数据库：`services/local-api/zhangwen/projects/migrations.py` 手写 SQLite migration，当前 UX-002 为 schema v17。
- Agent/Skill 基础：`services/local-api/zhangwen/orchestrator`、`services/local-api/zhangwen/skills`、`.codex/agents/*.toml`、`ai/skills/*`。
- LLM：`services/local-api/zhangwen/llm` 定义 Provider Protocol，目前 DeepSeek 为唯一真实 provider。

### 2.2 专家相关代码位置

- 共享枚举：`packages/contracts/src/enums.ts` 的 `ExpertType`。
- API 类型：`packages/contracts/src/api.ts` 中的 `ExpertDefinition`、`ProjectExpert`、`ProjectSharedContext`、`ProjectCoordinatorState`、`SuggestedProject`。
- 后端模型：`services/local-api/zhangwen/projects/models.py`。
- 数据库迁移和专家 seed：`services/local-api/zhangwen/projects/migrations.py`。
- 项目创建、推荐、专家会话和草稿：`services/local-api/zhangwen/projects/repository.py`。
- 产物 owner 映射：`services/local-api/zhangwen/artifacts/repository.py`。
- CodeRun 生成者专家映射：`services/local-api/zhangwen/code_agent/repository.py`。
- 桌面创建入口和 fallback 推荐：`apps/desktop/src/components/layout/LeftSidebar.tsx`。
- 桌面专家名称、三师默认定义和状态映射：`apps/desktop/src/utils/experts.ts`，由 `CenterChat.tsx`、`WorkTab.tsx`、`ArtifactsTab.tsx` 和 `LeftSidebar.tsx` 复用。
- 自动测试：`services/local-api/tests/test_project_repository.py`、桌面 `apps/desktop/src/__tests__/*`。

### 2.3 当前枚举、数据库字段和配置

- 当前 canonical `ExpertType` 为 `problem_guide`、`smart_engineer`、`structure_engineer`。
- `question_guide`、`intelligent_engineer` 和 UX-002 四专家字符串仅作为 legacy alias 保留，用于旧项目读取和迁移，不作为前台可见专家。
- SQLite 当前 schema 已推进到 v20，包含三师工作区、归档 legacy thread、SharedFact、ProjectDecision、PendingItem、Handoff、ProjectTask 和 ArtifactDependency 等领域结构。
- `expert_definitions.expert_type` 和 `project_experts.expert_type` 保存三师 canonical 字符串；旧来源保存在 `legacy_expert_type`、`archived_legacy_thread` 等兼容字段中。
- `artifacts.owner_expert_type` 保存三师 owner；旧 owner 保存在 `legacy_owner_expert` 和 `creator_legacy_expert`。
- `.codex/agents/*.toml` 是开发工具分工配置，不是产品内用户可见专家定义。

### 2.4 当前项目创建流程

- `LeftSidebar` 输入一句创意后调用 `/api/projects/suggest`。
- `ProjectRepository.suggest_project()` 通过 EntryRouter 生成项目名、初始专家、推荐专家和可用专家定义。
- `ProjectRepository.create_project_from_idea()` 按用户确认的三师选择创建项目、ExpertWorkspace、ConversationThread、初始消息、SharedFact、PendingItem 和 Task。
- 每个项目专家拥有独立 `conversation_id`、`expert_drafts` 和 `expert_private_memories`。
- 新建项目后进入初始专家独立线程；旧项目打开不重新路由。

### 2.5 当前对话、产物和共享上下文实现

- 对话：`conversations` 已移除 `project_id UNIQUE`，一个项目可有多个专家会话。
- 草稿：`expert_drafts` 按 `project_expert_id` 隔离；旧 `drafts` 仍保留兼容。
- 私有记忆：`expert_private_memories` 按项目专家保存。
- 共享上下文：`project_shared_contexts` 保存 goals、constraints、requirements、decisions、active artifact versions。
- 协调器：`project_coordinator_states` 保存当前唯一事项、冲突和依赖。
- 产物：`artifacts` 和 `artifact_versions` 记录 owner expert、source conversation、shared context revision 和版本状态。

### 2.6 四专家向三师迁移影响文件

- Contracts：`packages/contracts/src/enums.ts`、必要时 `api.ts`。
- Backend：`projects/models.py`、`projects/migrations.py`、`projects/repository.py`、`artifacts/repository.py`、`code_agent/repository.py`。
- Frontend：`LeftSidebar.tsx`、`CenterChat.tsx`、`WorkTab.tsx`、`ArtifactsTab.tsx` 以及测试 mock。
- Tests：后端 repository/migration 测试，桌面项目创建和专家导航测试。
- Docs/Handoff：本任务文件、`CURRENT_TASK.md`、`HANDOFF.md`。

### 2.7 数据兼容风险

- 旧 `ideator` 与 `educator` 都映射到 `problem_guide`，但必须保留为不同归档历史线程，不能合并聊天内容。
- 旧产物 owner 规范化为三师 owner，同时保留 `legacyOwnerExpert` / `creatorLegacyExpert`。
- legacy alias 仍是兼容入口，不能作为“无用枚举”删除；前台展示层必须统一映射为三师名称。
- 旧前端测试和 mock 已迁移到三师主路径，保留少量 legacy fixtures 用于旧项目兼容回归。

## 3. 迁移映射

| 旧专家 | 新专家 | 新 ExpertType |
|---|---|---|
| 创想家 | 问题引导师 | `problem_guide` |
| 教育家 | 问题引导师 | `problem_guide` |
| 开源硬件设计师 | 智能工程师 | `smart_engineer` |
| 3D结构设计师 | 结构工程师 | `structure_engineer` |

兼容策略：旧 `ExpertType` 字符串保留为 legacy alias。schema v19/v20 将活跃项目专家和产物 owner 规范化到三师；重复映射到同一三师的旧项目专家标记为 `archived_legacy_thread` 或 `removed_at`，不删除会话、消息、草稿、私有记忆和产物版本。

## 4. 分阶段修改方案

### 批次一：领域模型与兼容迁移

- Contracts/Python models 增加三师 `ExpertType`，旧四专家保留为 deprecated legacy。
- SQLite schema 升级到 v19/v20，seed 三师专家定义并保留 legacy 读取字段。
- migration 将 v17/v18 四专家和过渡专家项目专家、产物 owner 归并到三师。
- 新项目创建和推荐默认返回三师，不再强制必须包含问题引导师。
- 产物和 CodeRun owner 映射改为智能工程师/结构工程师/问题引导师。
- 桌面 fallback 和 label map 支持三师，同时保留旧标签兼容。
- 增加/更新后端迁移与推荐测试。

### 批次二：Agent/Skill 配置与提示词

- 为问题引导师、智能工程师、结构工程师分别维护系统提示词。
- 主路由和项目协调器拆出独立配置。
- 将硬件、软件、IoT、数据、AI 部署、视觉推理能力登记为智能工程师 Skills。
- 明确三师越界禁止项和交接规则。

### 批次三：业务流程和前端全面迁移

- 桌面创建、专家调整、专家导航、专家状态、右侧工作/产物全部使用三师。
- 支持从任意三师直接开始项目。
- 补充专家添加/移除流程中的三师约束。
- 强化项目协调器当前唯一事项和产物过期标记。

### 批次四：测试和验收

- 更新桌面全部 UX-002 测试 mock 到三师。
- 增加旧 v17/v18 数据库迁移到当前 schema 的回放测试。
- 增加旧项目打开、专家切换、共享上下文、产物 owner 和 CodeRun owner 测试。
- 全量运行 contracts、desktop、backend、cargo 验证。

## 5. 验收标准

- 新建项目只向用户推荐/展示三师。
- 旧四专家项目可打开，活跃专家被规范化为三师。
- 创想家和教育家数据合并到问题引导师，不删除旧会话和消息。
- 开源硬件设计师产物/代码归属智能工程师。
- 3D 结构产物归属结构工程师。
- 主路由和项目协调器不作为用户可见专家出现。
- 中央工作区和右侧“工作 / 产物 / 设备”不变量保持不变。
- 自动测试覆盖迁移与推荐。

## 6. Progress

- 2026-07-09：完成现状分析，确认四专家依赖点，创建本任务 ExecPlan。
- 2026-07-09：批次一实现完成：contracts/Python models 增加 canonical 三师枚举并保留 legacy 四专家值；SQLite schema 从 v18 继续升级到 v19；新项目推荐、创建、专家 seed、产物 owner、CodeRun owner、桌面 fallback 和标签映射切换到三师。
- 2026-07-09：补充 legacy 归并测试，验证旧 `ideator`/`educator` 行保留为 `problem_guide` 下的不同归档历史线程。
- 2026-07-09：修复 MVP readiness 项目基线不再硬编码 v17，改用 `CURRENT_SCHEMA_VERSION`。

## 7. Decision Log

- 2026-07-09：使用 `ZW-UX-003` 作为用户体验迁移任务编号；不创建、规划或实现 `ZW-017`。
- 2026-07-09：保留旧专家字符串为 legacy alias，并通过 v19/v20 数据迁移规范化活跃数据，避免旧项目无法打开。
- 2026-07-09：新项目不再强制加入问题引导师；用户明确选择智能工程师或结构工程师时允许直接开始。

## 8. Commands

- `git status --short --branch`
- `rg -n "ideator|open_hardware_designer|structure_designer|educator|创想家|开源硬件设计师|3D结构设计师|教育家" packages services apps docs tasks -g '!apps/desktop/dist/**' -g '!**/node_modules/**'`
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -q --rootdir services/local-api`：10 passed；仍有既有 Windows pytest 临时目录 cleanup `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw009_artifacts_windows.py services/local-api/tests/test_zw011_code_agent.py services/local-api/tests/test_zw015_project_packages.py -q --rootdir services/local-api`：12 passed，1 Starlette warning；仍有既有 Windows pytest 临时目录 cleanup `PermissionError`。
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen`：通过。
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation`：7 files / 53 tests passed；仍有既有 WorkTab React `act(...)` warnings。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw016_mvp_integration.py -q --rootdir services/local-api`：2 passed，1 Starlette warning；仍有既有 Windows pytest 临时目录 cleanup `PermissionError`。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`：108 passed，1 Starlette warning；仍有既有 Windows pytest 临时目录 cleanup `PermissionError`。
- `git diff --check`：通过，仅 LF/CRLF warning。

## 9. Phase 2 Runtime Progress

- 2026-07-10: Added three-teacher runtime config, prompt loader, invisible EntryRouter, ContextAssembler, smart_engineer Skill metadata, and runtime tests.
- EntryRouter now validates router-output-shaped data, retries one invalid model response, and falls back to deterministic rules without exposing internal JSON or prompts to users.
- `ProjectRepository.suggest_project()` now uses EntryRouter for project name and recommended experts.
- ContextAssembler reads shared facts, decisions, upstream artifacts, device status, and coordinator state without injecting full chat messages, private drafts, private memories, or device logs.
- Wrote `docs/three-expert-phase-2-runtime.md`.

Phase 2 validation run:

- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen services/local-api/tests/test_three_expert_runtime.py`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_three_expert_runtime.py services/local-api/tests/test_zw008_skills_model_router.py -q --rootdir services/local-api`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -q --rootdir services/local-api`
- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` (115 passed)
- `git diff --check`

Known output remains unchanged:

- Existing Starlette/FastAPI TestClient deprecation warning.
- Existing Windows pytest temp cleanup `PermissionError` after successful test runs.

## 10. Phase 3 Coordinator Progress

- 2026-07-10: Started ProjectCoordinator phase. Scope is backend/domain only: SharedFact lifecycle, Handoff and Task state machines, PendingItem candidate queue/highlight selection, concrete artifact dependency index sync and version-level outdated propagation. UI layout, main coordinator routing, real LLM calls and hardware operations remain out of scope.
- 2026-07-10: Completed Phase 3 backend slice. Added schema v20 with `project_shared_facts.key`, `project_pending_items.critical_path`, `project_tasks`, and coordinator/artifact dependency indexes.
- 2026-07-10: Added `ProjectCoordinatorService` for deterministic SharedFact confirmation/rejection/supersession, Handoff transitions, Task transitions, PendingItem creation/selection/resolution, and LLM candidate recording that only creates proposed facts/conflict items.
- 2026-07-10: Updated artifact writes to synchronize `artifact_dependencies` with concrete upstream `artifactId` and `version`, and added version-level downstream outdated propagation when a newer upstream version is confirmed.
- 2026-07-10: Wrote `docs/three-expert-phase-3-coordinator.md`.

Phase 3 decision log:

- 2026-07-10: PendingItem selection uses priority, affected expert count, earlier creation time, then critical path as the final tie-breaker, matching the requested order.
- 2026-07-10: Confirming a replacement SharedFact supersedes existing confirmed facts with the same key; proposing a replacement never changes the confirmed fact by itself.
- 2026-07-10: Artifact dependency sync rejects new dependency entries without a concrete upstream `version`; `versionId` is stored when available but remains optional for legacy lineage.

Phase 3 validation run:

- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen services/local-api/tests/test_project_coordinator.py`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_coordinator.py services/local-api/tests/test_project_repository.py -q --rootdir services/local-api` (14 passed)
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_three_expert_runtime.py services/local-api/tests/test_zw009_artifacts_windows.py services/local-api/tests/test_zw010_spec_agent.py services/local-api/tests/test_zw011_code_agent.py services/local-api/tests/test_zw013_cad_agent.py services/local-api/tests/test_zw014_lesson_agent.py services/local-api/tests/test_zw015_project_packages.py -q --rootdir services/local-api` (31 passed)
- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` (119 passed)
- `git diff --check` (no whitespace errors; LF/CRLF warnings only)
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation RightPanel` (53 passed)

Known output remains unchanged:

- Existing Starlette/FastAPI TestClient deprecation warning.
- Existing Windows pytest temp cleanup `PermissionError` after successful test runs.
- Existing WorkTab React `act(...)` warnings in desktop tests.
- No lint script exists in root, contracts, or desktop package scripts.

## 13. Phase 5 Workspace UI Progress

- 2026-07-10: Completed three-teacher project workspace UI phase on the existing desktop workspace. Scope was left/center/right project workbench behavior only; no new parallel workspace, no new UI framework, no visible EntryRouter/ProjectCoordinator UI, no complex flow canvas, no group chat.
- Left sidebar now shows Project Overview, participating three-teacher experts, and project resources. Participating experts are limited to `problem_guide`, `smart_engineer`, and `structure_engineer`, with labels, domain status text, pending markers, unread/stale markers, add expert and soft-remove actions.
- Center workspace now switches between project overview and one expert conversation. Expert switching loads that expert workspace and active thread, preserves per-thread draft/scroll state, keeps the right tab unchanged, and does not create Handoff or copy chat records.
- Chat send payload now includes the current project, expert workspace, thread, and expert type so messages are written to the active thread rather than project-wide filtering.
- Right panel keeps the fixed Work / Artifacts / Devices tabs. Work highlights one domain PendingItem, Artifacts shows project artifact versions/status/outdated metadata, and Devices exposes control operations only to `smart_engineer`.
- Backend added expert add/remove and pending item resolve/dismiss routes. Expert removal is soft removal and preserves conversations, artifacts, drafts and tasks.
- Wrote `docs/three-expert-phase-5-workspace-ui.md`.

Phase 5 decision log:

- 2026-07-10: Manual expert switching remains UI-only. Handoff creation is reserved for explicit Agent cross-domain requests handled by runtime/domain services.
- 2026-07-10: Device page scan/session summary remains visible to all experts, but deployment/control buttons are rendered only for `smart_engineer`.
- 2026-07-10: Real Agent message sending and real hardware actions were not used in manual validation to avoid unconfirmed paid LLM calls and external device effects.

Phase 5 validation run:

- `pnpm --filter @zhangwen/desktop typecheck`
- `pnpm --filter @zhangwen/desktop test -- RightPanel` (7 files / 59 tests passed; existing WorkTab React `act(...)` warnings remain)
- `pnpm typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` (125 passed; existing Starlette warning and Windows pytest temp cleanup `PermissionError` remain)
- `pnpm --filter @zhangwen/desktop build`
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
- `pnpm --filter @zhangwen/desktop run lint` (not available: no `lint` script in selected package)

Phase 5 manual validation:

- Started local API with `.venv\Scripts\python.exe -m uvicorn zhangwen.main:app --port 8100 --host 127.0.0.1 --app-dir services/local-api`.
- Started desktop web UI with `pnpm --filter @zhangwen/desktop dev -- --host 127.0.0.1` and opened `http://localhost:5173/`.
- Verified the rendered app title, nonblank workspace, left/center/right layout, fixed right tabs, participating experts, add expert flow, expert draft isolation, right-tab persistence, and device permission rendering.
- Did not send real Agent messages, call paid LLMs, connect real serial devices, run `mpremote`/`esptool`, erase Flash, burn firmware or write device files.

## 14. Cleanup Pass

- 2026-07-10: Audited old expert references after Phase 5. Kept legacy enum values, migration maps and old-project fixtures because they are required for backward compatibility and must not be treated as unused code.
- Extracted desktop three-teacher constants, display names, default expert definitions and workspace status labels into `apps/desktop/src/utils/experts.ts`.
- Removed duplicate expert label/status maps from `LeftSidebar.tsx`, `CenterChat.tsx`, `WorkTab.tsx` and `ArtifactsTab.tsx`.
- Updated display mapping so legacy expert IDs such as `ideator`, `educator`, `open_hardware_designer`, `question_guide` and `intelligent_engineer` render as the canonical three-teacher names instead of old role names.
- Cleaned this task file's outdated canonical ID notes from the early migration plan, replacing `question_guide` / `intelligent_engineer` targets with `problem_guide` / `smart_engineer` while preserving the historical decision context.

Cleanup validation:

- `pnpm --filter @zhangwen/desktop typecheck` passed after fixing the shared status map.
- `pnpm typecheck` passed.
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation RightPanel` passed: 7 files / 59 tests; existing WorkTab React `act(...)` warnings remain.
- `pnpm --filter @zhangwen/desktop build` passed.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` passed: 125 tests; existing Starlette warning and Windows pytest temp cleanup `PermissionError` remain.
- `git diff --check` passed with LF/CRLF warnings only.

## 15. Cloud LLM Solution Flow Fix

- 2026-07-10: Fixed the live project chat solution path after manual feedback that generated recommendations ignored clarified content, used local rules, requested clarification in several staged LLM calls, and did not use LLM when modifying a solution.
- Project chat clarification no longer uses local product-form/reminder/data-tracking templates or answered-count thresholds. It calls the configured cloud LLM and accepts a full `questions[]` structured response in one pass while preserving legacy `question` compatibility.
- Recommended solution generation now passes project initial idea, clarified answers, recent conversation and confirmed facts to `ClarificationService.generate_solution()` before persisting a Solution/Artifact. The hard-coded drinking-water solution was removed.
- Solution revision now uses `ClarificationService.revise_solution()` and persists LLM-provided revised sections, changed sections, preserved sections and impact summary through `SolutionRepository.create_revision_from_llm()`. The repository no longer owns keyword-based revision rules.
- Clicking “修改方案” now calls the LLM to ask for revision scope instead of returning a local static notice.
- Desktop clarification cards now render multi-question payloads and keep local answered state per `messageId:questionId`.

Validation:

- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen services/local-api/tests/test_project_chat_stream.py services/local-api/tests/test_zw004_clarification_solution.py`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_chat_stream.py services/local-api/tests/test_zw004_clarification_solution.py -q --rootdir services/local-api` (22 passed)
- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `pnpm --filter @zhangwen/desktop test -- DeepSeekChat` (7 files / 59 tests passed; existing WorkTab `act(...)` warnings remain)
- `pnpm --filter @zhangwen/desktop typecheck`
- `pnpm typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` (125 passed; existing Starlette warning and Windows pytest temp cleanup `PermissionError` remain)
- `pnpm --filter @zhangwen/desktop build`
- `git diff --check` (LF/CRLF warnings only)

## 16. End-to-End Framework Completion Repair

### Scope and acceptance

- Connect the active expert conversation path to the three-teacher prompt registry and `ContextAssembler` without injecting unrelated full-chat, private draft, private memory or raw device logs.
- Validate expert runtime output, retry invalid structured output once, and fall back safely without exposing internal prompts or JSON.
- Trigger deterministic coordinator updates after a completed expert response: proposed facts remain unconfirmed, conflicts become PendingItems, Handoffs and Tasks use their state machines, and at most one PendingItem remains highlighted.
- Add executable Skill Runtime / Tool Runner boundaries with timeout, retry, confirmation and audit records. Automated tests use mock tools only and never access real serial ports or firmware operations.
- Route project suggestions through the configured model provider when available while retaining deterministic offline fallback.
- Automatically propagate `outdated` through concrete artifact dependencies when a newer upstream version becomes confirmed.
- Hide internal Agent/model identifiers in ordinary mode while preserving the fixed Work / Artifacts / Devices tabs and the mounted central conversation.
- Make local `.codex/config.toml` untracked and ignored, provide a sanitized example, commit all project-owned three-teacher work, and finish with a clean `git status`.

### Progress

- 2026-07-10: Started the end-to-end completion repair after a read-only framework audit. Confirmed the existing domain, migration, project creation and workspace UI slices pass targeted tests, while the active chat, coordinator, Skill/Tool and dependency-propagation paths still require production wiring.
- 2026-07-10: Implemented the first repair pass and paused before final verification because the active session budget was nearly exhausted.
- Added schema v21 with `expert_runs`, `skill_runs`, `tool_runs` and `schema_migration_audit`. `ProjectRepository` now creates a timestamped SQLite backup before forward migration and records the backup path in a migration-session audit row.
- Added structured `ExpertRuntime` with current-expert prompt loading, `ContextAssembler` input, JSON validation, one retry, bounded side effects, run persistence and safe user-facing fallback.
- Wired smart/structure expert chat to `ExpertRuntime`; kept the problem-guide clarification/solution flow but prefixed it with the problem-guide prompt and a `ContextAssembler` system message. Structured user answers now become user-confirmed SharedFacts.
- Wired valid expert output to deterministic coordinator operations for proposed facts, conflicts, PendingItems, Tasks, Handoffs and Skill requests. Added coordinator-derived visible expert status refresh.
- Added `SkillRuntime` and `ToolRunner` with input/output schema checks, timeout/retry/confirmation policies and audit rows. No real serial, firmware or filesystem tool adapters are registered; tests use an explicit Mock handler only.
- Added optional provider-backed EntryRouter execution through ModelRouter when `useModelRouting=true`; desktop suggestions opt in, while missing credentials or invalid output fall back to deterministic routing.
- Changed artifact upsert paths so a newly confirmed upstream version automatically marks concrete downstream dependencies `outdated`.
- Lifted professional mode to `AppShell`, hid the central model selector outside professional mode, removed internal `sourceAgentId` from the ordinary artifact UI, and removed keyword routing from the desktop fallback.
- Added `test_three_expert_end_to_end.py` for provider-backed routing, ExpertRuntime/coordinator integration, Mock ToolRunner retry/audit and migration backup/audit. Updated the artifact dependency test to verify automatic propagation.
- 2026-07-10: Resumed the completion repair from the durable handoff. Milestone 1 is to rerun Python compilation plus the end-to-end/coordinator/runtime focused tests before making further implementation changes; `.codex/config.toml` remains protected from staging and all real provider/device operations remain disabled.
- 2026-07-10: Milestone 1 verification completed. Final Python sources compiled successfully and the end-to-end/coordinator/runtime focused selection passed 15 tests after creating the missing writable `.pytest-tmp` parent directory.
- 2026-07-10: Started milestone 2. The bounded knowledge slice will read the existing local hardware library, expose only relevant technical/safety fields with a strict result cap, and omit inventory/audit metadata; the provider route will be covered through FastAPI with fake credentials and a fake streaming provider only.
- 2026-07-10: Milestone 2 completed. `ContextAssembler` now retrieves at most four relevant public hardware-library entries for `smart_engineer`, the FastAPI `/projects/suggest` path is covered with fake credentials/provider plus ModelRouter audit verification, and the new Skill run contract types are exported from the package entry point.
- 2026-07-10: Started milestone 3 verification. The existing `RightPanel` coverage already asserts that professional-mode toggling preserves the same mounted center element and that ordinary artifact rendering hides `sourceAgentId`; these focused tests, desktop typecheck, and then full repository validation will be rerun on the completed repair.
- 2026-07-10: Focused desktop verification exposed and fixed a project-switch draft race: the new workspace could briefly render with the previous project's expert id, clearing or saving the wrong draft. Project opening now synchronizes the destination active expert, and `CenterChat` does not reset or persist drafts until a valid expert thread is mounted. Ordinary-mode model assertions were updated to match the hidden-internals contract.
- 2026-07-10: Milestone 3 verification completed. Full backend, desktop, typecheck, build, Cargo and whitespace checks passed. An isolated local UI run with credentials forced empty confirmed the UI contract dimensions, fixed right tabs, one mounted center conversation, draft preservation across tabs/professional mode, ordinary-mode model hiding, and zero browser console errors without invoking a real provider or device operation.
- 2026-07-10: Milestone 4 Git cleanup completed. The existing local `.codex/config.toml` remains unchanged on disk, is ignored and removed from the index; `.codex/config.example.toml` is sanitized. Generated pytest temp data was removed, the staged tree passed whitespace checks, and sensitive-pattern review found only documented fake keys and Mock COM identifiers. The final phase commit/tag are `feat(ZW-UX-003): complete three-expert system` and `zw-ux-003-complete`.
- 2026-07-10: Investigated a local runtime report where the Settings connection test passed but project chat returned `CONFIG_MISSING`. The mismatch came from the previous isolated UI-acceptance API process overriding only `chat.router.credential_store_factory` with an empty test credential store while Settings continued to use `WindowsCredentialStore`; no production code change was required.
- 2026-07-10: Restarted the local API on port 8100 with the same temporary data directory and normal credential wiring. `/api/health` returned 200 and `/api/settings/llm` returned `config.keySaved: true`. The Vite UI remained available on port 5173. A real chat request was intentionally not sent because it would invoke the paid provider.

### Current verification state

- `.venv\Scripts\python.exe -m compileall -q services/local-api/zhangwen services/local-api/tests/test_three_expert_end_to_end.py` passed after the final chat/UI/test patches.
- Targeted backend regression passed after schema v21 and chat routing fixes: 28 passed across `test_project_chat_stream.py`, `test_project_repository.py`, `test_zw008_skills_model_router.py` and `test_zw009_artifacts_windows.py`.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_three_expert_end_to_end.py services/local-api/tests/test_project_coordinator.py services/local-api/tests/test_three_expert_runtime.py -q --rootdir services/local-api --basetemp .pytest-tmp/zwux003-focused-rerun` passed: 15 tests. The first attempt used the same repository-local base-temp family before its parent existed and reported setup-only `FileNotFoundError`; creating `.pytest-tmp` resolved the environment issue without code changes.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_three_expert_runtime.py services/local-api/tests/test_three_expert_end_to_end.py -q --rootdir services/local-api --basetemp .pytest-tmp/zwux003-milestone2-green` passed: 13 tests with the existing Starlette TestClient deprecation warning. This includes bounded public-knowledge retrieval and the provider-backed HTTP suggestion route using fakes only.
- `pnpm --filter @zhangwen/contracts build` and `pnpm --filter @zhangwen/contracts typecheck` passed after exporting `SkillRunStatus`, `SkillRunRequest`, `SkillRunResult` and `SkillRunResponse`.
- `pnpm --filter @zhangwen/desktop typecheck` passed. `pnpm --filter @zhangwen/desktop test -- RightPanel ProjectWorkspace ProjectIsolation DeepSeekChat` passed: 4 files / 45 tests; the existing WorkTab React `act(...)` warnings remain. The professional-mode test confirms the same `center-chat` element remains mounted, and the artifact test confirms `proposal-agent` is hidden.
- `.venv\Scripts\python.exe -m compileall -q services/local-api/zhangwen services/local-api/tests` passed.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api --basetemp .pytest-tmp/zwux003-full-backend-rerun` passed: 131 tests with the existing Starlette TestClient deprecation warning.
- `pnpm typecheck` passed.
- `pnpm --filter @zhangwen/desktop test` passed: 7 files / 59 tests; the existing WorkTab React `act(...)` warnings remain.
- `pnpm --filter @zhangwen/desktop build` passed; Vite produced the desktop bundle successfully.
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` passed.
- `git diff --check` passed with LF/CRLF conversion warnings only.
- `git diff --cached --check` passed after removing trailing whitespace and extra EOF blank lines from newly added documentation/prompt files.
- Staged secret/serial review found only known test fixtures (`sk-test-secret-value`, `fake-test-key`, `COM3`, `COM9`); no real API key, credential, Wi-Fi secret or serial identifier was staged.
- Isolated manual UI acceptance passed at `http://localhost:5173/` against a temporary API data directory with credential factories forced empty. At 1280x720 the top/left/right dimensions were 48/240/320 px with no overlap; center count stayed 1, the draft remained `UI 契约草稿保留检查`, ordinary/professional model selector counts were 0/1, fixed right tabs were present, and browser error logs were empty. The Devices tab was not opened because real serial discovery is prohibited in this validation.

### Remaining work / next exact actions

No project-owned implementation or automated verification work remains. After the final commit, confirm `git status --short --branch` and `git log -1 --oneline --decorate`; do not push without explicit user authorization.

### Known incomplete/risk items

- ToolRunner intentionally has no real device/Flash/filesystem adapter; registering such adapters needs separate bounded integration and real external operations remain confirmation-only.
- Real paid provider calls and real serial/device/firmware operations remain external confirmation-only validation and were not run.

### Decision Log

- 2026-07-10: Reuse `ZW-UX-003`; do not create or plan `ZW-017`.
- 2026-07-10: Keep all real serial, `mpremote`, `esptool`, Flash erase and firmware burn operations outside automated validation. Tool Runtime tests use registered mock handlers only.
- 2026-07-10: Preserve the existing user-local `.codex/config.toml` on disk but remove it from Git tracking; commit only a sanitized `.codex/config.example.toml`.
- 2026-07-10: Public knowledge retrieval is limited to the existing local hardware catalog for `smart_engineer`, capped at four ranked entries, and excludes stock, price and audit timestamps. Built-in public catalog seeding is idempotent; catalog read failures degrade to no public knowledge.
- 2026-07-10: Project switches preserve the user's current center mode but synchronously select the destination project's active expert. Draft reset/save effects require a mounted expert conversation, preventing transient cross-project draft loss or writes.

## 11. Safety Notes

- 不提交 `.codex/config.toml`。
- 不调用真实付费 LLM。
- 不执行真实串口扫描、`mpremote`、`esptool`、Flash 擦除、固件烧录或设备文件覆盖。
- 不删除旧项目、旧会话、旧消息、旧草稿、旧私有记忆和旧产物版本。

## 12. Phase 4 Project Creation Progress

- 2026-07-10: Started three-teacher project creation flow implementation. Scope is existing creation UI/API/repository path only: EntryRouter-backed suggestion, manual name/expert protection, atomic project/workspace/thread/coordinator initialization, duplicate-create guard, and related tests. No new parallel creation page, no scaffold copy, no hidden Agent/Skill/Coordinator UI.
- 2026-07-10: Completed Phase 4 project creation flow. `POST /api/projects` now routes through `ProjectRepository.create_project_from_idea()` to validate the idea/name/expert selection, create only selected three-teacher workspaces, create distinct expert conversations, seed the initial user message into the initial expert thread, write creation SharedFacts, seed ProjectCoordinator/PendingItem/Task state, and apply an idempotency key.
- 2026-07-10: Desktop creation UI now uses EntryRouter suggestions, generated project names, editable names, adjustable three-teacher expert selection, stale route response protection, low-confidence fallback to `problem_guide`, duplicate-click disablement, and success navigation into the initial expert conversation.
- 2026-07-10: Updated creation, isolation, repository, chat-stream and coordinator tests for the Phase 4 semantics that every new project starts with a persisted initial user message and one seeded PendingItem/Task.
- 2026-07-10: Wrote `docs/three-expert-phase-4-project-creation.md`.

Phase 4 decision log:

- 2026-07-10: Project creation requires a non-empty idea. Older tests that created blank projects were updated to pass an explicit seed idea.
- 2026-07-10: Creation success enters `centerMode="expert"` and selects the initial expert thread, rather than stopping on project overview.
- 2026-07-10: The creation endpoint persists the initial user message and leaves automatic first assistant generation to the existing chat stream path; it does not call a paid LLM during creation.
- 2026-07-10: Router fallback/user guidance is exposed as normal status text, while actual create errors remain `role="alert"`.

Phase 4 validation run:

- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen`
- `pnpm --filter @zhangwen/desktop typecheck`
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation` (55 passed)
- `pnpm --filter @zhangwen/desktop test` (55 passed)
- `pnpm --filter @zhangwen/desktop build`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -q --rootdir services/local-api` (14 passed)
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_chat_stream.py services/local-api/tests/test_project_coordinator.py -q --rootdir services/local-api` (10 passed)
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api` (123 passed)
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
- `git diff --check` (no whitespace errors; LF/CRLF warnings only)

Known output remains unchanged:

- Existing Starlette/FastAPI TestClient deprecation warning.
- Existing Windows pytest temp cleanup `PermissionError` after successful test runs.
- Existing WorkTab React `act(...)` warnings in desktop tests.
- No lint script exists in root, contracts, or desktop package scripts.
