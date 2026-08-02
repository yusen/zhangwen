# ZW-007 Orchestrator 与 Agent Registry

## Purpose / Big Picture

ZW-007 建立掌问后续自动化阶段的本地编排底座。Orchestrator 负责把已确认的项目基线转换为可恢复的执行计划，Agent Registry 声明可用 Agent 与能力，Mock Agent 让前端和后端先验证状态流转、重试、暂停、恢复和用户确认节点。真实 Spec、Code、CAD、Deploy、Lesson 能力在后续阶段分别实现。

## Scope

- AgentDefinition、AgentCapability、ExecutionPlan、TaskNode、状态和日志 contracts。
- Sidecar 中的 Agent Registry 与 Orchestrator repository/service/router。
- SQLite schema 迁移，执行计划和任务节点持久化。
- 初始 Agent：Orchestrator、Spec Agent、Code Agent、CAD Agent、Deploy Agent、Publish Agent、Lesson Agent。
- Mock Agent 执行、失败重试、暂停、恢复、用户确认节点和执行日志。
- 右侧“工作”栏显示执行计划摘要和当前任务状态。

## Non-goals

- Skill Registry 和模型路由。
- 真实 Spec、代码、CAD、设备、教案或发布执行。
- 文件、Shell、串口、固件、CAD Python 执行。
- 公开分享、项目包导入导出。

## Repository Orientation

| 模块 | 当前状态 | ZW-007 动作 |
|---|---|---|
| `packages/contracts` | 有通用 `TaskStatus`，无 Agent/Plan 类型 | 新增 Agent 与 Orchestrator contracts |
| `services/local-api/zhangwen/orchestrator/` | 不存在 | 新增 models、registry、repository、service、router |
| `services/local-api/zhangwen/projects/migrations.py` | v4 | 增加 v5 orchestrator 表 |
| `apps/desktop/src/components/right-panel/WorkTab.tsx` | 显示项目基础状态 | 加载执行计划并显示工作状态卡片 |
| `apps/desktop/src/services/projectsApi.ts` | 有项目/方案/立项书 API | 新增 Orchestrator API |

## Interfaces and Data Contracts

- `AgentCapability`: `SPEC | CODE | CAD | DEPLOY | PUBLISH | LESSON | ORCHESTRATE | REVIEW`
- `AgentDefinition`: `id/name/description/capabilities/enabled/builtIn`
- `TaskNode`: `id/planId/projectId/agentId/title/description/status/dependencies/attempts/maxAttempts/requiresApproval/logs/createdAt/updatedAt/startedAt/completedAt/error`
- `ExecutionPlan`: `id/projectId/status/nodes/createdAt/updatedAt/startedAt/completedAt`
- `CreateExecutionPlanRequest`: `proposalId`
- `PlanActionRequest`: optional `nodeId`
- `ApprovalRequest`: `nodeId/approved/comment`

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python models、SQLite v5 migration、Agent Registry 和 repository。

### M2 Orchestrator API and State Machine

实现 Agent 列表、创建计划、读取当前计划、启动、暂停、恢复、重试和用户确认 API；Mock Agent 执行写入日志。

### M3 Work Tab UI

右侧“工作”栏加载执行计划摘要，展示当前任务、状态、重试次数和确认按钮；普通模式只显示面向用户的工作状态，不暴露模型或工具链细节。

### M4 Validation and Stage Close

运行受影响 Python tests、contracts build/typecheck、desktop typecheck/test/build；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Orchestrator API and State Machine
- [x] M3 Work Tab UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- SQLite `with conn:` 事务中不能通过新连接读回未提交的 plan/node 状态；repository 创建和保存后改为同连接读回。
- TypeScript 对 `includes()` 的字面量数组会窄化参数类型；WorkTab 状态判断改为显式 `||`。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | 本阶段 Agent 执行方式 | 只实现 Mock Agent | 满足状态机和 UI 验证，避免提前进入真实 Agent/Skill 阶段 |
| A-02 | 执行计划来源 | 从已确认 proposal 创建 | 确保后续自动化只引用正式立项书基线 |
| A-03 | 权限边界 | Agent 只记录意图和状态，不执行本地系统操作 | 符合 LLM/Agent 不直接拥有系统权限的安全规则 |

## Validation

- `.\.venv\Scripts\python.exe -m py_compile services\local-api\zhangwen\orchestrator\models.py services\local-api\zhangwen\orchestrator\registry.py services\local-api\zhangwen\orchestrator\repository.py services\local-api\zhangwen\orchestrator\service.py services\local-api\zhangwen\orchestrator\router.py services\local-api\zhangwen\main.py services\local-api\zhangwen\projects\migrations.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw007_orchestrator.py -v --rootdir services/local-api`：4 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py services/local-api/tests/test_zw006_proposals.py services/local-api/tests/test_zw007_orchestrator.py -v --rootdir services/local-api`：14 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test`：6 files / 37 tests passed。
- `pnpm --filter @zhangwen/desktop build`：通过，Vite 输出 `apps/desktop/dist/`。

## Outcomes & Retrospective

- 已新增 Agent/ExecutionPlan shared contracts 和 Python Pydantic models。
- SQLite schema 升级到 v5，新增 `execution_plans` 与 `task_nodes`。
- 已实现内置 Agent Registry 和 `/api/agents`。
- 已实现执行计划创建、当前计划读取、启动、暂停、恢复、重试和确认节点 API。
- Mock Agent 可顺序执行无确认任务，确认节点进入 `AWAITING_APPROVAL`，退回进入 `FAILED`，重试可恢复。
- 右侧“工作”Tab 展示计划进度、当前任务、确认/暂停/恢复/重试动作；中央主对话保持常驻。
- 未引入真实 LLM、Shell、文件、串口、固件或 CAD 执行。

## Handoff

下一步：提交 `feat: complete ZW-007 orchestrator and agent registry`，创建 `zw-007-complete` 标签，然后进入 ZW-008。
