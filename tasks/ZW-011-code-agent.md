# ZW-011 Code Agent

## Purpose / Big Picture

ZW-011 在已确认 Spec 之后生成可审查、可回滚的 MicroPython 工程代码草稿。Code Agent 输出代码文件、README、模拟测试结果和统一 diff，并同步为 Code Artifact。代码草稿只有通过确认后才成为后续设备部署输入；本阶段不写真实项目工作区、不执行任意 Shell、不连接串口。

## Scope

- Code shared contracts 与 Python Pydantic models。
- SQLite v9 `code_runs`、`code_files`、`code_patches`。
- Deterministic Mock Code Agent：从 approved Spec 生成 MicroPython 工程文件。
- Code API：生成、读取当前、接受、退回、回滚。
- Patch、diff、snapshot 标识、模拟测试结果和最大重试次数。
- Code 文件作为 Artifact 同步，支持右侧产物 Tab 和浮窗预览。

## Non-goals

- 真实 LLM prompt 调用。
- 真实文件系统工作区写入。
- 真实 Shell/test runner 执行。
- 串口、固件烧录、设备上传。
- CAD、Lesson、Share 阶段实现。

## Repository Orientation

| 模块 | 当前状态 | ZW-011 动作 |
|---|---|---|
| `packages/contracts` | 有 Spec/Artifact contracts，无 Code contracts | 新增 CodeRun、CodeFile、CodePatch、CodeTestResult 和 `ProjectPersistenceVersion.V9` |
| `services/local-api/zhangwen/code_agent/` | 不存在 | 新增 models、generator、repository、router |
| `services/local-api/zhangwen/artifacts/` | 支持文本 Artifact | 复用通用 text artifact upsert 写入代码预览 |
| `apps/desktop/src/components/right-panel/WorkTab.tsx` | 显示工作计划与 Spec | 增加代码草稿状态和操作入口 |
| `apps/desktop/src/components/right-panel/ArtifactsTab.tsx` | 通用 Artifact 列表 | 复用显示代码产物 |

## Interfaces and Data Contracts

- `CodeFileKind`: `MAIN | DRIVER | CONFIG | README | TEST`
- `CodeRunStatus`: `DRAFT | TESTING | READY_FOR_REVIEW | ACCEPTED | REJECTED | ROLLED_BACK | FAILED`
- `CodeFile`: `id/codeRunId/projectId/kind/path/language/content/createdAt`
- `CodePatch`: `id/codeRunId/projectId/baseSnapshotId/summary/diff/createdAt`
- `CodeTestResult`: `ok/command/output/createdAt`
- `CodeRun`: `id/projectId/specRunId/version/status/workspaceRoot/maxRetries/retries/files/patch/testResult/artifactId/artifactVersionId/staleReason/createdAt/updatedAt/acceptedAt`
- `GenerateCodeRequest`: `specRunId`
- `AcceptCodeRequest`: `codeRunId`
- `RejectCodeRequest`: `codeRunId/reason`
- `RollbackCodeRequest`: `codeRunId`

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python models、SQLite v9 migration。

### M2 Code Agent Service and API

实现确定性代码生成、模拟测试、读取当前、接受、退回和回滚 API。

### M3 Artifact Sync and UI

代码文件和 diff 同步为 Code Artifact；右侧工作栏增加代码草稿入口；产物栏复用通用 Artifact 显示。

### M4 Validation and Stage Close

运行 contracts、Sidecar、desktop 受影响测试和构建；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Code Agent Service and API
- [x] M3 Artifact Sync and UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- ZW-011 需要将所有历史 schema 当前版本断言推进到 v9；历史阶段测试名称仍可保留，但断言必须检查最新 schema。
- 本阶段不应执行真实测试命令，因此 CodeTestResult 使用 `mock-micropython-unit-tests` 并明确记录未执行 Shell/串口。
- Code Artifact 可复用 ZW-009 的 code preview，避免新增 UI 预览类型。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | Code 生成方式 | 确定性 Mock Code Agent | 自动测试不调用真实付费 LLM，仍可验证代码产物生命周期 |
| A-02 | 工作区策略 | 使用 `workspace://` 虚拟根和数据库草稿，不写真实文件 | 避免提前扩大文件权限；满足 diff、预览和回滚 |
| A-03 | 测试执行 | 记录模拟测试结果，不执行真实 Shell | 符合“命令通过受控 Tool Runner”且 ZW-011 不进入真实 Runner |

## Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.\.venv\Scripts\python.exe -m py_compile services\local-api\zhangwen\code_agent\models.py services\local-api\zhangwen\code_agent\generator.py services\local-api\zhangwen\code_agent\repository.py services\local-api\zhangwen\code_agent\router.py services\local-api\zhangwen\projects\migrations.py services\local-api\zhangwen\main.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest services\local-api\tests\test_zw011_code_agent.py -v --rootdir services/local-api`：3 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services\local-api\tests\test_project_repository.py services\local-api\tests\test_zw010_spec_agent.py services\local-api\tests\test_zw011_code_agent.py -v --rootdir services/local-api`：13 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services\local-api\tests\test_project_repository.py services\local-api\tests\test_zw006_proposals.py services\local-api\tests\test_zw009_artifacts_windows.py services\local-api\tests\test_zw010_spec_agent.py services\local-api\tests\test_zw011_code_agent.py -v --rootdir services/local-api`：20 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- RightPanel.test.tsx ProjectWorkspace.test.tsx DeepSeekChat.test.tsx`：6 files / 42 tests passed。
- `pnpm --filter @zhangwen/desktop build`：通过，Vite 输出 `apps/desktop/dist/`。
- `rg -n "sk-[A-Za-z0-9]|DEEPSEEK_API_KEY|apiKey|api_key" --glob "!node_modules/**" --glob "!apps/desktop/dist/**" --glob "!services/local-api/.pytest_cache/**"`：无命中。

## Outcomes & Retrospective

- 已新增 Code Agent shared contracts、Python Pydantic models 和 SQLite v9 `code_runs`/`code_files`/`code_patches`。
- 已实现确定性 Mock Code Agent，从 approved Spec 生成 MicroPython 主程序、驱动、配置、README 和模拟测试。
- 已实现读取当前、生成、接受、退回和回滚 Code API；未确认 Spec 会阻止生成。
- 代码草稿使用 `workspace://` 虚拟根和数据库存储，不写真实文件系统。
- Code 文件和 diff 已同步为 `CODE` Artifact，支持右侧产物 Tab 和浮窗预览。
- 右侧“工作”Tab 已增加代码草稿卡片；中央主对话常驻不变，普通模式不暴露模型/工具链细节。

## Handoff

自动验收已通过。下一步：提交 `feat: complete ZW-011 code agent` 并创建 `zw-011-complete` 标签，然后进入 ZW-012。
