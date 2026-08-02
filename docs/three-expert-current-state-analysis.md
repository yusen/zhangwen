# 三师系统代码现状分析

生成时间：2026-07-09
范围：只读扫描当前仓库，依据 `specs/three-expert-system/palmq_three_expert_framework_v1/` 中的需求框架输出现状、影响面和分阶段方案。本文档不包含代码改动方案的实施结果。

重点读取的需求文件：

- `specs/three-expert-system/palmq_three_expert_framework_v1/掌问_三师系统框架_v1.0.md`
- `specs/three-expert-system/palmq_three_expert_framework_v1/docs/01-architecture.md`
- `specs/three-expert-system/palmq_three_expert_framework_v1/docs/02-domain-and-state.md`
- `specs/three-expert-system/palmq_three_expert_framework_v1/docs/03-workflows.md`
- `specs/three-expert-system/palmq_three_expert_framework_v1/docs/04-migration.md`
- `specs/three-expert-system/palmq_three_expert_framework_v1/tests/acceptance.md`

## 1. 当前技术栈和运行方式

- 仓库是 pnpm monorepo，workspace 定义在 `pnpm-workspace.yaml`，包含 `packages/*` 和 `apps/*`。
- 根脚本在 `package.json`：
  - `pnpm start` 调用唯一完整入口 `start-local.bat`，由 `scripts-dev/start-local.ps1` 管理 Sidecar、Vite 与 Tauri 的同一桌面会话。
  - `pnpm dev:web` 系列只用于显式 Browser Host 开发，不能获得串口或设备操作能力。
  - `pnpm build:desktop` 先构建 contracts 再构建桌面前端。
  - `pnpm tauri:build` 调用 Cargo release build。
- 前端技术栈在 `apps/desktop/package.json`：React 18、TypeScript 5.7、Vite 6、Vitest、Testing Library。
- 共享契约包在 `packages/contracts/package.json`，只使用 TypeScript 构建。
- 桌面壳在 `apps/desktop/src-tauri/Cargo.toml`：Tauri 2、Rust 2021、serde。
- Python Sidecar 在 `services/local-api/pyproject.toml` 和 `services/local-api/requirements.txt`：FastAPI、uvicorn、Pydantic 2、httpx、pytest、pytest-asyncio。
- 默认 `scripts-dev/start-local.ps1` 构建 contracts、启动 Sidecar/Vite，并用 `cargo run` 打开 Tauri；它不隐式扫描或部署设备。设备流程在桌面应用的“设备”Tab 中明确发起。
- Tauri 配置在 `apps/desktop/src-tauri/tauri.conf.json`，窗口标题是“掌问 — AI 创客工程工作台”，devUrl 是 `http://localhost:5173`。
- Tauri Rust 入口在 `apps/desktop/src-tauri/src/main.rs` 和 `apps/desktop/src-tauri/src/lib.rs`；`lib.rs` 会检测 8100 端口，必要时从 `.venv\Scripts\python.exe` 启动 `zhangwen.main:app`。

## 2. 前端、Tauri 和后端目录结构

- 前端主目录：`apps/desktop/src/`
  - 应用入口：`apps/desktop/src/main.tsx`、`apps/desktop/src/App.tsx`。
  - 布局组件：`apps/desktop/src/components/layout/AppShell.tsx`、`LeftSidebar.tsx`、`CenterChat.tsx`、`RightPanel.tsx`、`TopBar.tsx`。
  - 右侧栏组件：`apps/desktop/src/components/right-panel/WorkTab.tsx`、`ArtifactsTab.tsx`、`DevicesTab.tsx`。
  - 聊天组件：`apps/desktop/src/components/chat/ChatInput.tsx`、`ConversationResponseCard.tsx`。
  - 浮窗：`apps/desktop/src/components/floating/FloatingWindow.tsx`。
  - hooks：`apps/desktop/src/hooks/useProjects.ts`、`useChatStream.ts`、`useLlmSettings.ts`、`useHealthCheck.ts`。
  - API 封装：`apps/desktop/src/services/api.ts`、`projectsApi.ts`、`llmApi.ts`、`hardwareApi.ts`。
  - 测试：`apps/desktop/src/__tests__/`。
- Tauri 主目录：`apps/desktop/src-tauri/`
  - Rust 入口：`apps/desktop/src-tauri/src/main.rs`、`apps/desktop/src-tauri/src/lib.rs`。
  - 配置：`apps/desktop/src-tauri/tauri.conf.json`。
- 共享契约：`packages/contracts/src/`
  - 枚举：`packages/contracts/src/enums.ts`。
  - API 类型：`packages/contracts/src/api.ts`。
  - 事件：`packages/contracts/src/events.ts`。
  - 导出：`packages/contracts/src/index.ts`。
- 后端主目录：`services/local-api/zhangwen/`
  - FastAPI 入口：`services/local-api/zhangwen/main.py`。
  - 项目与 DB：`services/local-api/zhangwen/projects/`。
  - 对话：`services/local-api/zhangwen/chat/`。
  - LLM：`services/local-api/zhangwen/llm/`。
  - 澄清/方案提示词：`services/local-api/zhangwen/clarification/`.
  - Agent 编排：`services/local-api/zhangwen/orchestrator/`。
  - Skill 和模型路由：`services/local-api/zhangwen/skills/`。
  - 产物：`services/local-api/zhangwen/artifacts/`。
  - 方案、立项书、Spec、Code、CAD、Lesson、Device、Package、MVP、Hardware：分别在 `solutions/`、`proposals/`、`specs/`、`code_agent/`、`cad_agent/`、`lesson_agent/`、`devices/`、`project_packages/`、`mvp/`、`hardware/`。

## 3. 当前专家枚举、专家配置和专家显示名称所在文件

- 共享前端/契约枚举在 `packages/contracts/src/enums.ts`：
  - 当前三师值是 `question_guide`、`intelligent_engineer`、`structure_engineer`。
  - 旧四专家兼容值仍保留：`ideator`、`open_hardware_designer`、`structure_designer`、`educator`。
- Python 后端枚举在 `services/local-api/zhangwen/projects/models.py`，同样使用 `question_guide`、`intelligent_engineer`、`structure_engineer`，并保留旧四专家值。
- 专家定义 seed 在 `services/local-api/zhangwen/projects/migrations.py` 的 `_seed_expert_definitions()`：
  - `expert_def_question_guide` / `question_guide` / “问题引导师”
  - `expert_def_intelligent_engineer` / `intelligent_engineer` / “智能工程师”
  - `expert_def_structure_engineer` / `structure_engineer` / “结构工程师”
- 后端推荐和默认任务在 `services/local-api/zhangwen/projects/repository.py`：
  - `_recommend_experts()`
  - `_default_expert_task()`
  - `_canonical_expert_type()`
  - `_normalize_expert_types()`
- 前端创建失败时的本地专家定义 fallback 在 `apps/desktop/src/components/layout/LeftSidebar.tsx` 的 `localSuggestProject()`。
- 前端专家显示名称散落在多个组件：
  - `apps/desktop/src/components/layout/CenterChat.tsx` 的 `EXPERT_TYPE_LABELS`
  - `apps/desktop/src/components/right-panel/WorkTab.tsx` 的 `EXPERT_TYPE_LABELS`
  - `apps/desktop/src/components/right-panel/ArtifactsTab.tsx` 的专家 label map
  - `apps/desktop/src/components/layout/LeftSidebar.tsx` 渲染后端 `expertDefinitions`，同时含本地 fallback 名称
- 与需求框架冲突：需求标准 ID 是 `problem_guide`、`smart_engineer`、`structure_engineer`，见 `specs/three-expert-system/palmq_three_expert_framework_v1/docs/02-domain-and-state.md` 和 `contracts/router-output.schema.json`；当前代码实际使用 `question_guide`、`intelligent_engineer`、`structure_engineer`。

## 4. Agent Registry、Skill Registry、Model Router 和 Tool Runner 所在位置

- Agent Registry 在 `services/local-api/zhangwen/orchestrator/registry.py`。
  - 当前注册的是任务 Agent：`orchestrator`、`spec-agent`、`code-agent`、`cad-agent`、`deploy-agent`、`publish-agent`、`lesson-agent`。
  - 边界模型在 `services/local-api/zhangwen/orchestrator/models.py`。
  - API 在 `services/local-api/zhangwen/orchestrator/router.py`。
  - 执行计划状态机在 `services/local-api/zhangwen/orchestrator/service.py`。
  - 执行计划持久化在 `services/local-api/zhangwen/orchestrator/repository.py`。
  - 与三师框架冲突：这里不是三位用户可见专家 + 两个不可见角色的 Runtime/Registry，而是 ZW-007 任务 Agent 编排。
- Skill Registry 在 `services/local-api/zhangwen/skills/registry.py`。
  - 当前内置 Skill 是 `skill_project_reader`、`skill_model_draft`、`skill_artifact_writer`、`skill_device_mock`、`skill_cad_template`。
  - 用户 Skill 存储在 `services/local-api/zhangwen/skills/repository.py`，对应 DB 表 `user_skills` 由 `services/local-api/zhangwen/projects/migrations.py` 创建。
  - API 在 `services/local-api/zhangwen/skills/router.py`。
  - 边界模型在 `services/local-api/zhangwen/skills/models.py`。
  - 与三师框架冲突：当前 SkillDefinition 没有 `ownerExpert`、`requiredTools`、`riskLevel`、`confirmationPolicy`、`timeoutPolicy`、`retryPolicy` 等字段；智能工程师的硬件、IoT、数据、AI 部署 Skill 还没有按框架落入正式 registry。
- Model Router 在 `services/local-api/zhangwen/skills/model_router.py`。
  - 当前是确定性 DeepSeek-only 路由，输出 `deepseek-v4-flash` 或 `deepseek-v4-pro`。
  - 审计表 `model_route_audit` 由 `services/local-api/zhangwen/projects/migrations.py` 创建。
  - 与三师框架差距：还没有被 EntryRouter、三师 Runtime、ProjectCoordinator 统一调用，也没有第二个真实 provider 验证抽象。
- Tool Runner：
  - 仓库中未发现集中式 `ToolRunner` / `SkillRuntime` 类。
  - 实际本地工具能力分散在专用模块：设备 dry-run 和日志在 `services/local-api/zhangwen/devices/repository.py`，串口扫描在 `services/local-api/zhangwen/devices/serial_discovery.py`，代码生成在 `services/local-api/zhangwen/code_agent/`，CAD 生成在 `services/local-api/zhangwen/cad_agent/`，项目包导出在 `services/local-api/zhangwen/project_packages/`，产物写入在 `services/local-api/zhangwen/artifacts/repository.py`。

## 5. 当前系统提示词的存储和加载方式

- 系统提示词当前以 Python 常量存储在 `services/local-api/zhangwen/clarification/prompts.py`：
  - `CLARIFY_SYSTEM_PROMPT`
  - `SOLUTION_SYSTEM_PROMPT`
  - `REVISE_SOLUTION_SYSTEM_PROMPT`
- 加载方式在 `services/local-api/zhangwen/clarification/service.py`：
  - `ClarificationService.clarify()` 创建 `ChatMessage(role=ChatRole.SYSTEM, content=CLARIFY_SYSTEM_PROMPT)`。
  - `ClarificationService.generate_solution()` 创建 `ChatMessage(role=ChatRole.SYSTEM, content=SOLUTION_SYSTEM_PROMPT)`。
  - LLM 调用走 `DeepSeekProvider.stream_chat()`。
- DeepSeek payload 组装在 `services/local-api/zhangwen/llm/deepseek.py`，只把 `system/user/assistant` 的 `role` 和 `content` 转为 provider messages。
- IDEA 阶段对话编排在 `services/local-api/zhangwen/chat/idea_flow.py`，会调用 `ClarificationService`，但也有本地 fallback 和硬编码方案内容。
- 当前没有按三师拆分的 prompt 文件加载机制；需求框架提供的 `prompts/problem-guide.md`、`prompts/smart-engineer.md`、`prompts/structure-engineer.md`、`prompts/entry-router.md`、`prompts/project-coordinator.md` 目前只是 `specs/` 下需求文件，没有接入 `services/local-api/zhangwen/`。

## 6. 当前项目创建流程及涉及文件

- 前端入口在 `apps/desktop/src/components/layout/LeftSidebar.tsx`：
  - 用户输入一句创意。
  - `suggestProject({ initialIdea })` 调用后端建议接口。
  - 后端失败时使用 `localSuggestProject()` 生成本地项目名、推荐专家和可选专家。
  - 用户可以通过专家 chip 调整 `selectedExpertTypes`。
- `apps/desktop/src/components/layout/AppShell.tsx` 的 `handleCreateProject()` 调用 `projects.create()`，创建成功后当前实现把中央区域设为 `overview`。
- `apps/desktop/src/hooks/useProjects.ts` 的 `create()` 调用 `createProject()`，写入 `activeWorkspace` 并刷新项目列表。
- `apps/desktop/src/services/projectsApi.ts`：
  - `POST /api/projects/suggest`
  - `POST /api/projects`
  - `POST /api/projects/{projectId}/experts/{projectExpertId}/activate`
- 后端 API 在 `services/local-api/zhangwen/projects/router.py`：
  - `suggest_project()` 调 `_repo().suggest_project()`
  - `create_project()` 调 `_repo().create_project()`
  - `activate_project_expert()` 调 `_repo().set_active_expert()`
- 核心创建逻辑在 `services/local-api/zhangwen/projects/repository.py`：
  - `create_project()` 先调用 `suggest_project()`。
  - `_recommend_experts()` 通过关键词推荐专家。
  - 创建 `projects`、`conversations`、`project_shared_contexts`、`project_coordinator_states`、`project_experts`、`expert_private_memories`、`expert_drafts`、`drafts`。
  - 第一个专家复用初始 conversation，后续专家各自创建 conversation。
  - `active_expert_id` 指向第一个创建的 project expert。
- 与需求框架冲突：
  - 需求要求主路由输出项目名、初始专家、推荐专家和原因，并符合 `contracts/router-output.schema.json`；当前是后端关键词规则 + 前端 fallback，没有 EntryRouter 结构化输出和 schema 校验。
  - 需求要求项目创建后自动进入初始专家对话；当前 `AppShell.tsx` 创建后进入 `overview`。

## 7. 当前对话线程、专家工作区和消息数据结构

- TypeScript 契约在 `packages/contracts/src/api.ts`：
  - `ChatMessage`
  - `Conversation`
  - `ProjectExpert`
  - `ExpertConversation`
  - `ProjectWorkspace`
  - `PersistedChatRequest`
  - `ProjectStreamChunk`
  - `ConversationTurnContext`
  - `ConversationResponse` / `ConversationResponseEnvelope`
- Python 模型在 `services/local-api/zhangwen/projects/models.py`：
  - `Conversation`
  - `Draft`
  - `ExpertDefinition`
  - `ProjectExpert`
  - `ExpertConversation`
  - `ProjectWorkspace`
  - `PersistedChatRequest`
- SQLite 表由 `services/local-api/zhangwen/projects/migrations.py` 创建或升级：
  - `conversations`
  - `messages`
  - `conversation_turns`
  - `clarification_questions`
  - `clarification_answers`
  - `project_experts`
  - `expert_private_memories`
  - `expert_drafts`
- 后端消息持久化在 `services/local-api/zhangwen/projects/repository.py`：
  - `append_user_and_assistant()` 根据 `projectExpertId` 或 active expert 解析 conversation。
  - `_insert_message()` 写入 `messages`，包含 `structured_payload_json` 和 `metadata_json`。
  - `resolve_conversation_id()` 按专家解析线程。
  - `find_turn_messages()` 用 `conversation_turns.client_turn_id` 做重复提交保护。
  - `_expert_conversations()` 为每个 ProjectExpert 组装独立消息和草稿。
- 流式接口在 `services/local-api/zhangwen/chat/router.py`：
  - `POST /api/projects/{project_id}/chat/stream`
  - 校验 `turnContext.projectId` 和 `turnContext.conversationId`
  - 通过 SSE 返回 `projectId`、`conversationId`、`requestTurnId`、`responseTurnId`。
- 前端中央对话在 `apps/desktop/src/components/layout/CenterChat.tsx`：
  - `activeExpertConversation` 从 `workspace.expertConversations` 选择。
  - 草稿缓存 key 是 `projectId:projectExpertId:conversationId`。
  - 发送时带 `projectExpertId`、`turnContext`、structured answer。
  - 接收流式 chunk 时校验 `projectId`、`conversationId`、`requestTurnId`。

## 8. 当前项目共享上下文实现

- 契约在 `packages/contracts/src/api.ts`：
  - `ProjectSharedContext`
  - `SharedFact`
  - `SharedDecision`
  - `ActiveArtifactVersion`
  - `SharedContextChange`
- Python 模型在 `services/local-api/zhangwen/projects/models.py`。
- DB 表在 `services/local-api/zhangwen/projects/migrations.py`：
  - `project_shared_contexts`：`goals_json`、`constraints_json`、`requirements_json`、`decisions_json`、`active_artifact_versions_json`
  - `shared_context_changes`
- 创建和读取在 `services/local-api/zhangwen/projects/repository.py`：
  - `_create_shared_context()` 创建 revision 1，并把 `initialIdea` 写入 `goals_json`，当前 `confirmed` 为 `True`。
  - `_shared_context()` 从 JSON 字段组装 `ProjectSharedContext`。
- 产物会读取共享上下文版本，在 `services/local-api/zhangwen/artifacts/repository.py` 的 `_assign_artifact_owner()` 中把 `project_shared_contexts.revision` 写入 `artifacts.shared_context_revision` 和 `artifact_versions.shared_context_revision`。
- 当前差距：
  - 没有独立的 `ContextAssembler` 服务。
  - 共享上下文没有 `confirmedFacts/openQuestions/currentPendingItem` 这种与需求完全一致的结构。
  - `initialIdea` 被直接标记为 confirmed，和 `docs/03-workflows.md` 中“保存原始创意为 proposed fact”的要求冲突。
  - `shared_context_changes` 已建表，但当前扫描到的主要流程中没有完整的事实提议、确认和 supersede 状态机。

## 9. 当前产物、任务、设备和项目状态模型

- 项目阶段：
  - TypeScript：`packages/contracts/src/enums.ts` 的 `ProjectStage`。
  - Python：`services/local-api/zhangwen/projects/models.py` 的 `ProjectStage`。
- 专家工作状态：
  - TypeScript：`ProjectExpertStatus` in `packages/contracts/src/enums.ts`。
  - Python：`ProjectExpertStatus` in `services/local-api/zhangwen/projects/models.py`。
- 产物状态：
  - `packages/contracts/src/enums.ts` 的 `ArtifactStatus`。
  - `services/local-api/zhangwen/artifacts/models.py` 的 `ArtifactStatus`。
  - 当前值包括 `DRAFT`、`GENERATING`、`NEEDS_REVIEW`、`APPROVED`、`REJECTED`、`STALE`、`FAILED`、`ARCHIVED`。
- 执行计划和任务：
  - `packages/contracts/src/enums.ts` 的 `TaskStatus`。
  - `services/local-api/zhangwen/orchestrator/models.py` 的 `TaskStatus`、`ExecutionPlan`、`TaskNode`。
  - 持久化在 `services/local-api/zhangwen/orchestrator/repository.py`。
- Spec：
  - `services/local-api/zhangwen/specs/models.py` 的 `SpecRunStatus`、`SpecRun`、`SpecFile`。
- Code：
  - `services/local-api/zhangwen/code_agent/models.py` 的 `CodeRunStatus`、`CodeRun`、`CodeFile`、`CodePatch`、`CodeTestResult`。
  - `CodeRun` 已有 `hardwareSolutionVersion`、`bomVersion`、`ioMapVersion`、`generatedByExpertId`、`staleReason`。
- CAD：
  - `services/local-api/zhangwen/cad_agent/models.py` 的 `CadRunStatus`、`CadRun`、`CadFile`。
- Lesson：
  - `services/local-api/zhangwen/lesson_agent/models.py` 的 `LessonRunStatus`、`LessonRun`、`LessonFile`。
- 方案和立项书：
  - `services/local-api/zhangwen/solutions/models.py` 的 `SolutionStatus`、`SolutionVersion`、`SolutionRevision`。
  - `services/local-api/zhangwen/proposals/models.py` 的 `ProposalStatus`、`ProposalVersion`。
- 设备：
  - `services/local-api/zhangwen/devices/models.py` 的 `DeviceSessionStatus`、`DeviceOperationStatus`、`DevicePort`、`DeviceSession`、`DeviceOperation`。
- 项目包：
  - `services/local-api/zhangwen/project_packages/models.py` 的 `ProjectPackageStatus`、`ProjectPackageManifest`、`ProjectPackageRecord`。
- MVP 就绪度：
  - `services/local-api/zhangwen/mvp/models.py` 的 `MvpReadinessStatus`、`MvpReadinessItemId`、`MvpReadinessReport`。
- 硬件库：
  - `services/local-api/zhangwen/hardware/models.py` 的 `HardwareCategory`、`HardwareComponentStatus`、`ValidationSeverity`。

## 10. 当前数据库、ORM 和迁移机制

- 当前数据库是 SQLite，没有 ORM。
- DB 路径由 `services/local-api/zhangwen/config.py` 的 `settings.data_dir` 决定，项目数据库路径在 `services/local-api/zhangwen/projects/repository.py` 中组装为 `data_dir / "projects" / "zhangwen.sqlite3"`。
- 所有主要仓库直接使用 `sqlite3`：
  - `services/local-api/zhangwen/projects/repository.py`
  - `services/local-api/zhangwen/artifacts/repository.py`
  - `services/local-api/zhangwen/orchestrator/repository.py`
  - `services/local-api/zhangwen/skills/repository.py`
  - `services/local-api/zhangwen/code_agent/repository.py`
  - 以及 specs、cad、lesson、devices、solutions、proposals、project_packages、mvp 等 repository。
- 迁移文件是 `services/local-api/zhangwen/projects/migrations.py`：
  - `CURRENT_SCHEMA_VERSION = 18`
  - `migrate(conn)` 读取 `PRAGMA user_version` 并顺序执行 `_migrate_vN()`。
  - 迁移是手写前进迁移，没有 down migration。
  - `ProjectRepository._ensure_database()` 调用 `migrate(conn)`，随后设置 `PRAGMA journal_mode=WAL` 和 `PRAGMA foreign_keys=ON`。
- v17 引入专家工作区相关表，v18 seed 三师定义并归一化旧专家：
  - `expert_definitions`
  - `project_experts`
  - `expert_private_memories`
  - `expert_drafts`
  - `project_shared_contexts`
  - `shared_context_changes`
  - `project_coordinator_states`
- 当前 FastAPI 路由大多是 `async def`，但直接调用同步 sqlite3 repository，例如 `services/local-api/zhangwen/projects/router.py` 的 `create_project()`、`suggest_project()`、`get_project()`。这会在事件循环中执行同步 DB 操作，对流式聊天路径 `services/local-api/zhangwen/chat/router.py` 有潜在阻塞风险。

## 11. 当前左侧、中央工作区和右侧工作台对应组件

- 顶层 Shell：`apps/desktop/src/components/layout/AppShell.tsx`
  - 管理右侧 tab、中央模式 `overview/expert`、active expert、浮窗和设置弹窗。
- 左侧：`apps/desktop/src/components/layout/LeftSidebar.tsx`
  - 项目创建、项目列表、项目总览入口、已参与专家导航、项目资源、硬件库入口。
  - 调用 `suggestProject()`，并内置 `localSuggestProject()` fallback。
- 中央：`apps/desktop/src/components/layout/CenterChat.tsx`
  - `centerMode === "overview"` 显示项目总览。
  - `centerMode === "expert"` 显示当前专家独立对话。
  - 对话卡片来自 `apps/desktop/src/components/chat/ConversationResponseCard.tsx`。
  - 输入框来自 `apps/desktop/src/components/chat/ChatInput.tsx`。
- 右侧容器：`apps/desktop/src/components/layout/RightPanel.tsx`
  - 一级 Tab 固定为 “工作” / “产物” / “设备”。
- 右侧工作：`apps/desktop/src/components/right-panel/WorkTab.tsx`
  - 显示项目概览、当前需求、当前方案、最新产物、MVP 就绪度、工作计划、Spec/Code/CAD/Lesson/Skills/Model Router 等后续工程能力。
  - 当前唯一事项读取自 `workspace.coordinator.currentItem`，但没有完整 PendingItem 队列和优先级状态机。
- 右侧产物：`apps/desktop/src/components/right-panel/ArtifactsTab.tsx`
  - 列出 Artifact 并可打开浮窗。
- 右侧设备：`apps/desktop/src/components/right-panel/DevicesTab.tsx`
  - 扫描串口、显示会话、执行 dry-run 上传/flash，不自动执行真实上传、mpremote、esptool 或烧录。
- 浮窗：`apps/desktop/src/components/floating/FloatingWindow.tsx`
  - 用于文档、代码、图片、3D 预览，不替代中央对话。

## 12. 四专家迁移为三师会影响的全部文件

以下是按影响面归类的文件清单。不是所有文件都必须在同一阶段修改，但都受三师 ID、路由、共享上下文、迁移兼容或 UI 显示影响。

共享契约：

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/index.ts`
- `packages/contracts/src/events.ts`

项目、专家和迁移：

- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/router.py`
- `services/local-api/zhangwen/projects/errors.py`

对话、提示词和 LLM：

- `services/local-api/zhangwen/chat/router.py`
- `services/local-api/zhangwen/chat/idea_flow.py`
- `services/local-api/zhangwen/chat/sessions.py`
- `services/local-api/zhangwen/clarification/prompts.py`
- `services/local-api/zhangwen/clarification/service.py`
- `services/local-api/zhangwen/clarification/router.py`
- `services/local-api/zhangwen/llm/contracts.py`
- `services/local-api/zhangwen/llm/gateway.py`
- `services/local-api/zhangwen/llm/deepseek.py`

Agent、Skill、Model Router、Tool Runner 相关：

- `services/local-api/zhangwen/orchestrator/registry.py`
- `services/local-api/zhangwen/orchestrator/models.py`
- `services/local-api/zhangwen/orchestrator/router.py`
- `services/local-api/zhangwen/orchestrator/service.py`
- `services/local-api/zhangwen/orchestrator/repository.py`
- `services/local-api/zhangwen/skills/registry.py`
- `services/local-api/zhangwen/skills/models.py`
- `services/local-api/zhangwen/skills/router.py`
- `services/local-api/zhangwen/skills/repository.py`
- `services/local-api/zhangwen/skills/model_router.py`

产物、依赖和下游生成：

- `services/local-api/zhangwen/artifacts/models.py`
- `services/local-api/zhangwen/artifacts/repository.py`
- `services/local-api/zhangwen/artifacts/router.py`
- `services/local-api/zhangwen/solutions/models.py`
- `services/local-api/zhangwen/solutions/repository.py`
- `services/local-api/zhangwen/solutions/router.py`
- `services/local-api/zhangwen/proposals/models.py`
- `services/local-api/zhangwen/proposals/repository.py`
- `services/local-api/zhangwen/proposals/router.py`
- `services/local-api/zhangwen/specs/models.py`
- `services/local-api/zhangwen/specs/repository.py`
- `services/local-api/zhangwen/specs/router.py`
- `services/local-api/zhangwen/code_agent/models.py`
- `services/local-api/zhangwen/code_agent/repository.py`
- `services/local-api/zhangwen/code_agent/router.py`
- `services/local-api/zhangwen/cad_agent/models.py`
- `services/local-api/zhangwen/cad_agent/repository.py`
- `services/local-api/zhangwen/cad_agent/router.py`
- `services/local-api/zhangwen/lesson_agent/models.py`
- `services/local-api/zhangwen/lesson_agent/repository.py`
- `services/local-api/zhangwen/lesson_agent/router.py`
- `services/local-api/zhangwen/project_packages/models.py`
- `services/local-api/zhangwen/project_packages/repository.py`
- `services/local-api/zhangwen/project_packages/router.py`
- `services/local-api/zhangwen/mvp/models.py`
- `services/local-api/zhangwen/mvp/repository.py`
- `services/local-api/zhangwen/mvp/router.py`

设备与硬件能力：

- `services/local-api/zhangwen/devices/models.py`
- `services/local-api/zhangwen/devices/repository.py`
- `services/local-api/zhangwen/devices/router.py`
- `services/local-api/zhangwen/devices/serial_discovery.py`
- `services/local-api/zhangwen/devices/simulator.py`
- `services/local-api/zhangwen/hardware/models.py`
- `services/local-api/zhangwen/hardware/repository.py`
- `services/local-api/zhangwen/hardware/router.py`
- `services/local-api/zhangwen/hardware/rule_engine.py`

前端 UI、hooks 和 API：

- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/layout/RightPanel.tsx`
- `apps/desktop/src/components/chat/ChatInput.tsx`
- `apps/desktop/src/components/chat/ConversationResponseCard.tsx`
- `apps/desktop/src/components/right-panel/WorkTab.tsx`
- `apps/desktop/src/components/right-panel/ArtifactsTab.tsx`
- `apps/desktop/src/components/right-panel/DevicesTab.tsx`
- `apps/desktop/src/components/floating/FloatingWindow.tsx`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/hooks/useChatStream.ts`
- `apps/desktop/src/services/projectsApi.ts`
- `apps/desktop/src/services/llmApi.ts`
- `apps/desktop/src/App.css`

测试：

- `services/local-api/tests/test_project_repository.py`
- `services/local-api/tests/test_project_chat_stream.py`
- `services/local-api/tests/test_zw010_spec_agent.py`
- `services/local-api/tests/test_zw011_code_agent.py`
- `services/local-api/tests/test_zw012_devices.py`
- `services/local-api/tests/test_zw013_cad_agent.py`
- `services/local-api/tests/test_zw014_lesson_agent.py`
- `services/local-api/tests/test_zw015_project_packages.py`
- `services/local-api/tests/test_zw016_mvp_integration.py`
- `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`
- `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`
- `apps/desktop/src/__tests__/DeepSeekChat.test.tsx`
- `apps/desktop/src/__tests__/RightPanel.test.tsx`
- `apps/desktop/src/__tests__/SettingsDeepSeek.test.tsx`
- `apps/desktop/src/__tests__/AppShell.test.tsx`

Tauri 本身：

- `apps/desktop/src-tauri/src/lib.rs` 和 `apps/desktop/src-tauri/src/main.rs` 当前主要负责 Sidecar 启停，三师领域迁移预计不直接影响；只有 API 端口、启动方式或 sidecar 打包策略变化时才需要修改。

## 13. 旧项目兼容风险

- Canonical ID 不一致风险：需求迁移目标是 `problem_guide`、`smart_engineer`、`structure_engineer`，当前 v18 迁移目标是 `question_guide`、`intelligent_engineer`、`structure_engineer`，见 `services/local-api/zhangwen/projects/migrations.py` 和 `services/local-api/zhangwen/projects/repository.py`。
- 旧角色名不完全一致：需求文档 `docs/04-migration.md` 使用 `three_d_structure_designer`，当前代码使用 `structure_designer`，见 `packages/contracts/src/enums.ts` 和 `services/local-api/zhangwen/projects/models.py`。如果历史库出现 `three_d_structure_designer`，当前迁移不会识别。
- 创想家和教育家合并风险：`services/local-api/zhangwen/projects/migrations.py` 的 `_normalize_legacy_project_experts()` 会把 `ideator` 和 `educator` 归一为 `question_guide`，并 soft-remove 重复 `project_experts`。需求要求旧线程不合并，应保留为问题引导师下的归档 legacy thread；当前没有 `legacyExpertType`、`archivedLegacyThread` 字段。
- 历史对话可发现性风险：`conversations` 表没有专家历史元数据；如果 `project_experts` 被 soft-remove，旧 conversation/messages 仍在，但 UI 主要从 active `project_experts` 组装 `expertConversations`，旧线程可能无法作为归档线程展示。
- 旧产物来源元数据风险：`_normalize_legacy_artifact_owners()` 会更新 `artifacts.owner_expert_type`，但没有 `creatorLegacyExpert` 字段；旧来源仍可从 `source_agent_id` 推断一部分，但不能完整表达旧四专家创建者。
- `UNIQUE(project_id, expert_type)` 风险：`project_experts` 表在 `services/local-api/zhangwen/projects/migrations.py` 中限制一个项目同一 expert_type 只能有一个工作区，这和“问题引导师下保留创想家/教育家两个归档线程”的需求存在结构冲突。
- 前端旧测试和 mocks 仍大量使用旧四专家，如 `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`、`ProjectIsolation.test.tsx`、`DeepSeekChat.test.tsx`、`RightPanel.test.tsx`、`SettingsDeepSeek.test.tsx`。
- 前端 label map 仍保留旧角色显示名，如 `apps/desktop/src/components/layout/CenterChat.tsx`、`apps/desktop/src/components/right-panel/WorkTab.tsx`、`apps/desktop/src/components/right-panel/ArtifactsTab.tsx`。
- 迁移不可回滚：`services/local-api/zhangwen/projects/migrations.py` 是 forward-only 手写迁移。需求要求“可回滚、可审计”，当前只有备份/隔离损坏 DB 的机制，没有 down migration 或 migration audit table。

## 14. 建议的分阶段修改顺序

1. 固化 canonical ID 和兼容策略。
2. 先改共享 contracts 和 Python 边界模型，再改迁移，不先动 UI。
3. 新增迁移版本，补 legacy 字段和归档线程表达，保证旧项目打开和重复迁移幂等。
4. 接入 EntryRouter 结构化输出和 schema 校验，替换关键词推荐为可校验路由结果，保留本地规则降级。
5. 建立三师 prompt registry 和加载器，接入问题引导师、智能工程师、结构工程师、entry_router、project_coordinator。
6. 抽出 ContextAssembler，保证专家只读取最小必要共享上下文，不注入完整无关聊天。
7. 改造 Agent Registry / Skill Registry：保留旧任务 Agent 作为内部工具能力，但用户可见专家统一到三师；智能工程师 Skills 增加 owner、风险和确认策略。
8. 建立 ToolRunner / SkillRuntime 的最小抽象，把现有 devices、code、cad、package 等执行能力收敛到可审计 ToolRun。
9. 改造 ProjectCoordinator：PendingItem 模型、唯一 highlighted item、冲突/依赖优先级、产物过期传播。
10. 改造项目创建和前端交互：创建后进入 initial expert；前台只显示三师；旧角色只作为归档兼容展示。
11. 补齐产物依赖和状态映射：draft/pending_confirmation/confirmed/outdated/archived 与现有 ArtifactStatus 的兼容层。
12. 最后升级测试：迁移、路由、独立工作区、共享上下文、唯一事项、产物依赖、UI 验收。

## 15. 每个阶段预计修改的文件

阶段 1：canonical ID 和边界模型

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/index.ts`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/tests/test_project_repository.py`

阶段 2：旧项目兼容和迁移审计

- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/artifacts/models.py`
- `services/local-api/zhangwen/artifacts/repository.py`
- `services/local-api/tests/test_project_repository.py`
- 可能新增迁移 fixture 测试文件：`services/local-api/tests/`

阶段 3：EntryRouter 和项目创建

- `services/local-api/zhangwen/projects/router.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/chat/idea_flow.py`
- `services/local-api/zhangwen/clarification/service.py`
- `services/local-api/zhangwen/llm/contracts.py`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/services/projectsApi.ts`
- `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`
- `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`

阶段 4：三师 prompt registry 和专家对话 Runtime

- `services/local-api/zhangwen/clarification/prompts.py`
- `services/local-api/zhangwen/clarification/service.py`
- `services/local-api/zhangwen/chat/idea_flow.py`
- `services/local-api/zhangwen/chat/router.py`
- 可能新增 prompt loader/runtime 模块：`services/local-api/zhangwen/`
- `services/local-api/tests/test_project_chat_stream.py`

阶段 5：ContextAssembler 和共享事实状态

- `packages/contracts/src/api.ts`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/artifacts/repository.py`
- `services/local-api/tests/test_project_repository.py`
- `services/local-api/tests/test_project_chat_stream.py`

阶段 6：Agent Registry、Skill Registry、Model Router、Tool Runner

- `services/local-api/zhangwen/orchestrator/registry.py`
- `services/local-api/zhangwen/orchestrator/models.py`
- `services/local-api/zhangwen/orchestrator/service.py`
- `services/local-api/zhangwen/skills/registry.py`
- `services/local-api/zhangwen/skills/models.py`
- `services/local-api/zhangwen/skills/repository.py`
- `services/local-api/zhangwen/skills/router.py`
- `services/local-api/zhangwen/skills/model_router.py`
- `services/local-api/zhangwen/devices/repository.py`
- `services/local-api/zhangwen/code_agent/repository.py`
- `services/local-api/zhangwen/cad_agent/repository.py`
- `services/local-api/zhangwen/project_packages/repository.py`

阶段 7：Coordinator、PendingItem、依赖和过期传播

- `packages/contracts/src/api.ts`
- `packages/contracts/src/enums.ts`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/artifacts/models.py`
- `services/local-api/zhangwen/artifacts/repository.py`
- `services/local-api/zhangwen/specs/repository.py`
- `services/local-api/zhangwen/code_agent/repository.py`
- `services/local-api/zhangwen/cad_agent/repository.py`
- `services/local-api/zhangwen/lesson_agent/repository.py`
- `services/local-api/zhangwen/mvp/repository.py`

阶段 8：前端三师 UI 和验收测试

- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/layout/RightPanel.tsx`
- `apps/desktop/src/components/right-panel/WorkTab.tsx`
- `apps/desktop/src/components/right-panel/ArtifactsTab.tsx`
- `apps/desktop/src/components/right-panel/DevicesTab.tsx`
- `apps/desktop/src/components/chat/ConversationResponseCard.tsx`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/hooks/useChatStream.ts`
- `apps/desktop/src/services/projectsApi.ts`
- `apps/desktop/src/App.css`
- `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`
- `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`
- `apps/desktop/src/__tests__/DeepSeekChat.test.tsx`
- `apps/desktop/src/__tests__/RightPanel.test.tsx`
- `apps/desktop/src/__tests__/SettingsDeepSeek.test.tsx`
- `apps/desktop/src/__tests__/AppShell.test.tsx`

## 16. 当前代码中与需求框架冲突的地方

- 专家 ID 冲突：需求使用 `problem_guide`、`smart_engineer`、`structure_engineer`；当前代码使用 `question_guide`、`intelligent_engineer`、`structure_engineer`，涉及 `packages/contracts/src/enums.ts`、`services/local-api/zhangwen/projects/models.py`、`services/local-api/zhangwen/projects/migrations.py`、`services/local-api/zhangwen/projects/repository.py` 和多个前端 label map。
- 主路由缺失：需求要求不可见 `entry_router` 输出符合 `specs/.../contracts/router-output.schema.json` 的 JSON；当前 `services/local-api/zhangwen/projects/repository.py` 的 `_recommend_experts()` 和 `apps/desktop/src/components/layout/LeftSidebar.tsx` 的 `localSuggestProject()` 是关键词规则。
- 创建后入口冲突：需求要求创建后打开初始专家对话；当前 `apps/desktop/src/components/layout/AppShell.tsx` 创建成功后设置 `centerMode` 为 `overview`。
- Prompt 架构冲突：需求提供三师和两个不可见角色的独立 prompt；当前只有 `services/local-api/zhangwen/clarification/prompts.py` 中澄清/方案/修订提示词，未按专家加载。
- Agent Registry 冲突：需求说智能工程师通过 Skill Registry 扩展能力，不使用子 Agent；当前 `services/local-api/zhangwen/orchestrator/registry.py` 注册 `spec-agent`、`code-agent`、`cad-agent`、`deploy-agent`、`lesson-agent` 等任务 Agent，和三师 Runtime 抽象不同。
- Skill Registry 冲突：需求 Skill 必须声明 owner、风险、确认、工具、超时、重试和产物类型；当前 `services/local-api/zhangwen/skills/models.py` 只有基础 schema 和 permissions。
- Tool Runner 缺失：需求要求 ToolRunner 统一执行本地工具/串口/文件系统；当前没有集中实现，能力分散在 `devices/`、`code_agent/`、`cad_agent/`、`project_packages/`、`artifacts/`。
- ContextAssembler 缺失：需求要求最小必要上下文组装；当前 `services/local-api/zhangwen/chat/idea_flow.py` 和 `services/local-api/zhangwen/chat/router.py` 主要基于 conversation messages，`ProjectSharedContext` 还未作为统一上下文组装器使用。
- 共享事实状态冲突：需求区分 proposed/confirmed/superseded/rejected；当前 `services/local-api/zhangwen/projects/repository.py` 的 `_create_shared_context()` 直接把 initial idea 写为 confirmed goal。
- PendingItem 模型不完整：需求要求最多一个 `isHighlighted=true` 的 PendingItem；当前只有 `ProjectCoordinatorState.currentItem`，定义在 `packages/contracts/src/api.ts` 和 `services/local-api/zhangwen/projects/models.py`，没有 PendingItem 队列、priority、status 或 highlighted 约束。
- 旧线程迁移冲突：需求要求创想家和教育家旧线程不合并，保留为归档 legacy threads；当前 `services/local-api/zhangwen/projects/migrations.py` 会归一化并 soft-remove duplicate project experts，没有 legacy thread 字段。
- 产物状态命名不一致：需求使用 `draft/pending_confirmation/confirmed/outdated/archived`；当前 `ArtifactStatus` 是 `DRAFT/NEEDS_REVIEW/APPROVED/STALE/ARCHIVED`，需要兼容映射。
- 产物 legacy creator 缺失：需求要求保留 `creatorLegacyExpert`；当前 `services/local-api/zhangwen/artifacts/models.py` 只有 `sourceAgentId`、`ownerExpertId`、`ownerExpertType`，没有 legacy creator 字段。
- 方案生成内容冲突：`services/local-api/zhangwen/chat/idea_flow.py` 的 `_generate_solution()` 仍硬编码“喝水提醒项目”，`_data_tracking_question()` 也包含饮水次数/饮水量选项；这与需求中“根据用户输入澄清，不套用示例主题”的规则冲突。
- LLM schema 校验不完整：`services/local-api/zhangwen/clarification/service.py` 对澄清和方案做 Pydantic 解析，但 EntryRouter、ProjectCoordinator、SkillRequest、PendingItem 等需求 schema 尚未接入。
- 数据库并发风险：`services/local-api/zhangwen/projects/router.py` 是 `async def`，但直接调用同步 `ProjectRepository` 的 sqlite3 方法；`services/local-api/zhangwen/chat/router.py` 流式输出也会穿插同步 repository 调用，单用户桌面可接受但会带来“AI 打字时 UI 卡顿”的风险。
- Repository 过大：`services/local-api/zhangwen/projects/repository.py` 同时管理项目、专家、会话、草稿、私有记忆、共享上下文、协调器、消息、澄清问题等，和需求中 Project/ExpertWorkspace/ConversationThread/SharedFact/PendingItem 等聚合分层不一致。
- 迁移缺少回滚和独立审计：`services/local-api/zhangwen/projects/migrations.py` 没有 down migration；需求要求可回滚、可审计。
- UI 测试仍以旧四专家为主：`apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`、`ProjectIsolation.test.tsx`、`DeepSeekChat.test.tsx`、`RightPanel.test.tsx`、`SettingsDeepSeek.test.tsx` 仍大量断言“创想家”“开源硬件设计师”和旧 expert id。
