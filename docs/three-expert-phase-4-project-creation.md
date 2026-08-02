# Three Expert Phase 4: Project Creation Flow

## 1. 修改摘要

本阶段把现有左侧项目创建入口改为三师系统创建流程：

用户输入一句创意 -> `/api/projects/suggest` 调用 EntryRouter -> 返回项目名、初始专家和推荐专家 -> 用户可修改项目名和专家选择 -> 点击“开始项目” -> `/api/projects` 通过单一应用服务创建 Project、ExpertWorkspace、ConversationThread、SharedFact、Coordinator、Task 和 PendingItem -> 成功后进入初始专家独立对话线程。

前台创建入口只显示三位用户可见专家：

- `problem_guide`: 问题引导师
- `smart_engineer`: 智能工程师
- `structure_engineer`: 结构工程师

创建页不显示旧四专家、EntryRouter、ProjectCoordinator、Skill、模型路由或内部 JSON。

## 2. 修改文件清单

Phase 4 直接修改或补充的文件：

- `packages/contracts/src/api.ts`
- `packages/contracts/src/index.ts`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/router.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/tests/test_project_repository.py`
- `services/local-api/tests/test_project_chat_stream.py`
- `services/local-api/tests/test_project_coordinator.py`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`
- `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`

注意：工作区还包含 Phase 1-3 的未提交文件和无关 `.codex/config.toml` 本地改动；本阶段没有整理或提交这些文件。

## 3. 项目创建事务实现方式

后端统一入口为 `ProjectRepository.create_project_from_idea()`，由 `services/local-api/zhangwen/projects/router.py` 的 `POST /api/projects` 调用。

一次数据库事务内完成：

- 校验创意、项目名、参与专家和初始专家。
- 归一化旧专家类型到三师类型。
- 创建 `projects`。
- 创建 `project_shared_contexts`。
- 创建 `project_coordinator_states`。
- 只为用户选择的专家创建 `project_experts`、`expert_private_memories`、`expert_drafts` 和独立 `conversations`。
- 设置 `projects.active_expert_id`。
- 写入初始专家线程中的第一条用户消息。
- 写入 proposed `project_shared_facts`：`initial_idea`、`entry_router_result`、可选 `creation_idempotency_key`。
- 写入第一条 highlighted `project_pending_items`。
- 写入第一条 `project_tasks`，状态为 `running`。
- 同步 coordinator current item。

创建请求支持 `idempotencyKey`。相同 key 再次提交会返回已创建项目，避免网络重试或重复点击产生重复项目。

## 4. 路由结果如何应用

前端调用 `suggestProject({ text })`。返回结构使用 `RouterOutput`：

- `projectName` 默认填入项目名称。
- `initialExpert` 作为默认进入的专家。
- `recommendedExperts` 默认勾选。
- `confidence < 0.5`、`requiresClarification=true` 或无效结果时降级到 `problem_guide`。

降级提示固定为：

`当前想法还比较宽泛，建议先由问题引导师帮助你进一步梳理。`

前端只处理输入、防抖、loading、请求过期、错误和降级展示，不重新实现完整关键词路由。

## 5. 用户手动修改如何保护

`LeftSidebar` 维护 `ProjectCreationState`：

- 用户修改项目名后设置 `projectNameEditedByUser=true`，后续路由结果不覆盖名称。
- 用户调整专家后设置 `expertSelectionMode="manual"`，后续路由结果不覆盖专家选择。
- 请求序号 `routeRequestSeq` 防止旧路由响应覆盖新输入。
- 创建中 `status="creating"`，按钮禁用，避免重复点击。
- 创建失败后保留创意、项目名、专家选择、初始专家和手动状态。

## 6. 专家工作区和线程创建方式

后端只为 `participatingExperts` 中的三师专家创建可见工作区。

- 每个专家拥有独立 `conversation_id`。
- 初始专家状态为 `working`，`workspace_status` 为 `in_progress`。
- 其他已选专家状态为 `idle`，`workspace_status` 为 `not_started`。
- 未选择专家不会预创建可见工作区。
- 创建成功后 `AppShell` 设置 `centerMode="expert"`，并选中初始专家对应的 `projectExpertId`。

旧项目仍按既有兼容映射打开，不要求重新执行路由，也不要求补齐 RouterResult。

## 7. 创建失败回滚方式

`create_project_from_idea()` 使用 SQLite connection context 执行事务。事务中任一步抛错时不会留下半成品：

- 不留下孤立 `projects`。
- 不留下孤立 `conversations`。
- 不留下孤立 `project_experts`。
- 不留下孤立 `project_shared_contexts` 或 `project_coordinator_states`。
- 不留下孤立 `project_pending_items` 或 `project_tasks`。

`test_create_project_from_idea_rolls_back_when_seed_records_fail` 覆盖了种子记录写入失败时的完整回滚。

## 8. 旧项目兼容方式

旧项目打开流程没有改为强制重建：

- 缺失 RouterResult 的旧项目仍可打开。
- 旧专家通过 Phase 1 的兼容映射读入三师。
- 历史工作区、线程、消息、草稿、私有记忆和产物版本保留。
- 旧聊天流测试已更新为接受“创建时已有初始用户消息”的新语义。

## 9. 测试命令和结果

已通过：

- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen`
- `pnpm --filter @zhangwen/desktop typecheck`
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation`，55 passed
- `pnpm --filter @zhangwen/desktop test`，55 passed
- `pnpm --filter @zhangwen/desktop build`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -q --rootdir services/local-api`，14 passed
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_chat_stream.py services/local-api/tests/test_project_coordinator.py -q --rootdir services/local-api`，10 passed
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`，123 passed
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
- `git diff --check`

已知输出：

- 仍有既有 Starlette TestClient deprecation warning。
- Windows pytest 结束后仍可能出现既有 temp cleanup `PermissionError`。
- 桌面测试仍有既有 WorkTab React `act(...)` warning。
- root、contracts、desktop 当前没有 `lint` script，本阶段未运行 lint。

## 10. 尚未完成项

- 创建成功后已持久化初始用户消息并进入初始专家线程，但尚未由创建接口自动触发第一条助手回复；现有聊天流可在该线程继续生成。
- 未实现新的创建页面或多步向导。
- 未实现主路由/协调器的大规模 UI 展示。
- 未调用真实付费 LLM、真实串口或真实硬件。
