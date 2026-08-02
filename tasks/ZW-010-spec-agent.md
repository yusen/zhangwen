# ZW-010 Spec Agent

## Purpose / Big Picture

ZW-010 在已确认立项书之后生成可执行的工程规格基线。Spec Agent 输出 `project_spec.yaml`、`bom.yaml` 和 `io_map.yaml`，并通过 Schema 与硬件规则校验。确认后的 Spec 是后续 Code/CAD/Deploy 的输入；未确认 Spec 只能预览，不进入正式代码生成。

## Scope

- Spec shared contracts 与 Python Pydantic models。
- SQLite v8 `spec_runs` 与 `spec_files`。
- Deterministic Mock Spec Agent：从 approved proposal 生成规范、BOM 和 IO Map。
- Spec API：生成、读取当前、确认、退回。
- Spec 文件作为 Artifact 同步，支持右侧产物 Tab 和浮窗预览。
- Spec 变更时将下游 Code/CAD/Deploy 类型产物标记过期。

## Non-goals

- 真实 LLM prompt 调用。
- Code/CAD/Device/Lesson Agent 实现。
- 文件系统工作区写入。
- 真实串口、固件、CAD Python 或 Shell 执行。

## Repository Orientation

| 模块 | 当前状态 | ZW-010 动作 |
|---|---|---|
| `packages/contracts` | 有 Agent/Artifact contracts，无 Spec contracts | 新增 SpecRun、SpecFile、SpecValidation contracts 和 `ProjectPersistenceVersion.V8` |
| `services/local-api/zhangwen/specs/` | 不存在 | 新增 models、generator、repository、router |
| `services/local-api/zhangwen/artifacts/` | 支持 proposal artifact | 增加 generic artifact upsert 和 downstream stale helpers |
| `apps/desktop/src/components/right-panel/WorkTab.tsx` | 显示执行计划与专业信息 | 增加 Spec 生成/确认状态入口 |
| `apps/desktop/src/components/right-panel/ArtifactsTab.tsx` | 通用 Artifact 列表 | 复用显示 Spec YAML 产物 |

## Interfaces and Data Contracts

- `SpecFileKind`: `PROJECT_SPEC | BOM | IO_MAP`
- `SpecRunStatus`: `DRAFT | VALIDATED | APPROVED | REJECTED | STALE | FAILED`
- `SpecValidation`: `ok/checks`
- `SpecRun`: `id/projectId/proposalId/version/status/files/validation/createdAt/updatedAt/confirmedAt/staleReason`
- `GenerateSpecRequest`: `proposalId`
- `ConfirmSpecRequest`: `specRunId`

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python models、SQLite v8 migration。

### M2 Spec Agent Service and API

实现确定性 Spec 生成、Schema/IO 校验、读取当前、确认、退回 API。

### M3 Artifact Sync and UI

Spec 文件同步为 YAML Artifact；右侧工作栏增加 Spec 状态入口；产物栏复用通用 Artifact 显示。

### M4 Validation and Stage Close

运行 contracts、Sidecar、desktop 受影响测试和构建；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Spec Agent Service and API
- [x] M3 Artifact Sync and UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- Spec 文件读取不能按枚举字符串排序，否则 `BOM` 会排在 `PROJECT_SPEC` 前面；仓储层已显式固定 `project_spec.yaml`、`bom.yaml`、`io_map.yaml` 顺序。
- 前端 workspace 依赖 contracts `dist`，新增 Spec shared exports 后需要先运行 contracts build。
- pytest 退出时仍可能出现既有临时目录清理 `PermissionError`，但断言和进程退出码均通过。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | Spec 生成方式 | 确定性 Mock Spec Agent | 自动测试不调用真实付费 LLM，仍可验证接口、产物和状态 |
| A-02 | Spec 文件存储 | SQLite 记录 YAML 文本并同步 Artifact | 避免提前进入 Code Agent 文件沙箱，同时让产物可预览和版本化 |
| A-03 | 未确认 Spec | 阻断后续正式代码生成 | 符合“未确认 Spec 不进入正式代码生成”规则 |

## Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.\.venv\Scripts\python.exe -m py_compile services\local-api\zhangwen\specs\models.py services\local-api\zhangwen\specs\generator.py services\local-api\zhangwen\specs\repository.py services\local-api\zhangwen\specs\router.py services\local-api\zhangwen\artifacts\repository.py services\local-api\zhangwen\projects\migrations.py services\local-api\zhangwen\main.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest services\local-api\tests\test_zw010_spec_agent.py -v --rootdir services/local-api`：4 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services\local-api\tests\test_project_repository.py services\local-api\tests\test_zw006_proposals.py services\local-api\tests\test_zw009_artifacts_windows.py -v --rootdir services/local-api`：13 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- RightPanel.test.tsx ProjectWorkspace.test.tsx DeepSeekChat.test.tsx`：6 files / 41 tests passed。
- `pnpm --filter @zhangwen/desktop build`：通过，Vite 输出 `apps/desktop/dist/`。
- `rg -n "sk-[A-Za-z0-9]|DEEPSEEK_API_KEY|apiKey|api_key" --glob "!node_modules/**" --glob "!apps/desktop/dist/**" --glob "!services/local-api/.pytest_cache/**"`：无命中。

## Outcomes & Retrospective

- 已新增 Spec shared contracts、Python Pydantic models 和 SQLite v8 `spec_runs`/`spec_files`。
- 已实现确定性 Mock Spec Agent，从 approved proposal 生成 `project_spec.yaml`、`bom.yaml`、`io_map.yaml`。
- 已实现读取当前、生成、确认和退回 Spec API；未批准立项书会阻止生成。
- Spec YAML 已同步为 Artifact 系统中的 YAML 预览产物，依赖源立项书版本。
- 确认 Spec 会将 `code-agent`、`cad-agent`、`deploy-agent` 既有产物标记过期。
- 右侧“工作”Tab 已增加工程规格卡片；右侧“产物”Tab 和浮窗系统复用 ZW-009 预览能力。
- 中央主对话常驻不变；普通模式仅显示用户可理解的 Spec 状态和操作。

## Handoff

自动验收已通过。下一步：提交 `feat: complete ZW-010 spec agent` 并创建 `zw-010-complete` 标签，然后进入 ZW-011。
