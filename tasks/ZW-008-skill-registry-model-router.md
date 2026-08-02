# ZW-008 Skill Registry 与模型路由

## Purpose / Big Picture

ZW-008 在 Orchestrator 之后建立可扩展能力目录和模型选择边界。Skill Registry 描述内置与用户自定义 Skill 的输入输出 Schema、权限声明和启用状态；Model Router 在 Provider 抽象层选择当前可用模型，记录成本、质量、重试和降级策略。本阶段只验证 Registry 与路由，不执行真实 Skill，不接入其他供应商。

## Scope

- SkillDefinition、SkillPermission、SkillRegistry、ModelRoute contracts。
- Sidecar Skill Registry、用户自定义 Skill 存储与默认无 Shell 权限策略。
- Provider-neutral Model Router，当前正式模型仍只支持 `deepseek-v4-flash` 和 `deepseek-v4-pro`。
- Mock 路由测试，不调用真实付费 LLM。
- 专业模式 UI 展示 Skill、模型路由和权限摘要；普通模式隐藏内部细节。

## Non-goals

- 真实 Skill 执行。
- Tool Runner。
- 其他真实 Provider。
- Agent/Spec/Code/CAD/Device/Lesson 实现。
- Shell、文件、串口、固件或 CAD 执行。

## Repository Orientation

| 模块 | 当前状态 | ZW-008 动作 |
|---|---|---|
| `packages/contracts` | 有 Agent/Plan 类型，无 Skill/Router 类型 | 新增 Skill 与 Model Router contracts |
| `services/local-api/zhangwen/skills/` | 不存在 | 新增 models、registry、repository、router、model_router |
| `services/local-api/zhangwen/projects/migrations.py` | v5 | 增加 v6 user skills 和 model route 表 |
| `apps/desktop/src/components/right-panel/WorkTab.tsx` | 显示工作计划 | 专业模式下显示 Skill/模型路由摘要 |
| `apps/desktop/src/services/projectsApi.ts` | 有 Orchestrator API | 新增 Skill/Router API |

## Interfaces and Data Contracts

- `SkillPermission`: `READ_PROJECT | WRITE_ARTIFACT | RUN_MODEL | USE_DEVICE | RUN_CAD | RUN_SHELL`
- `SkillOrigin`: `BUILT_IN | USER`
- `SkillDefinition`: `id/name/description/origin/enabled/inputSchema/outputSchema/permissions/createdAt/updatedAt`
- `ModelRouteStrategy`: `BALANCED | COST_FIRST | QUALITY_FIRST | FAST_FIRST`
- `ModelRouteRequest`: `agentId/taskKind/strategy`
- `ModelRouteResult`: `provider/model/strategy/retryCount/fallbackModel/costTier/qualityTier/reasoning`

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python models、SQLite v6 migration、Skill repository 和内置 registry。

### M2 Skill Registry and Model Router API

实现 Skill 列表、自定义 Skill 创建/启停、模型路由预览 API。自定义 Skill 默认无 Shell 权限，禁止隐式高危权限。

### M3 Professional Mode UI

右侧“工作”栏新增专业模式开关；开启后展示 Skill 数量、权限摘要和当前模型路由结果；普通模式隐藏内部细节。

### M4 Validation and Stage Close

运行受影响 Python tests、contracts build/typecheck、desktop typecheck/test/build；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Skill Registry and Model Router API
- [x] M3 Professional Mode UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- Pydantic v2 在 Python 3.13 下解析字符串自引用联合类型不稳定，`JsonSchemaObject` 改用 `typing.Self`。
- TypeScript 对字面量数组 `includes()` 会窄化参数类型，权限高危判断改为显式比较。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | Provider 范围 | 仍只正式支持 DeepSeek 两个模型 | 符合用户对 ZW-002 的强制要求，不提前实现其他供应商 |
| A-02 | 自定义 Skill 默认权限 | 默认无 Shell 权限，且高危权限需显式声明 | 满足安全边界并避免用户 Skill 获得隐式系统能力 |
| A-03 | 自动测试模型调用 | 使用 Mock 路由，不调用真实 LLM | 防止产生费用和泄露凭据 |

## Validation

- `.\.venv\Scripts\python.exe -m py_compile services\local-api\zhangwen\skills\models.py services\local-api\zhangwen\skills\registry.py services\local-api\zhangwen\skills\repository.py services\local-api\zhangwen\skills\model_router.py services\local-api\zhangwen\skills\router.py services\local-api\zhangwen\main.py services\local-api\zhangwen\projects\migrations.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw008_skills_model_router.py -v --rootdir services/local-api`：3 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py services/local-api/tests/test_zw007_orchestrator.py services/local-api/tests/test_zw008_skills_model_router.py -v --rootdir services/local-api`：13 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test`：6 files / 38 tests passed。
- `pnpm --filter @zhangwen/desktop build`：通过，Vite 输出 `apps/desktop/dist/`。

## Outcomes & Retrospective

- 已新增 Skill、权限、来源、模型路由策略与结果 shared contracts。
- SQLite schema 升级到 v6，新增 `user_skills` 和 `model_route_audit`。
- 已实现内置 Skill Registry、用户 Skill 创建/启停、权限更新 API。
- 自定义 Skill 默认权限为空，不会隐式获得 `RUN_SHELL`。
- 已实现 provider-neutral deterministic Model Router，只路由到 DeepSeek 当前正式支持模型，不调用真实 LLM。
- 右侧“工作”Tab 添加专业模式开关；普通模式隐藏 Skill/模型细节，专业模式显示摘要。

## Handoff

下一步：提交 `feat: complete ZW-008 skill registry and model router`，创建 `zw-008-complete` 标签，然后进入 ZW-009。
