# ZW-009 产物系统与浮窗系统

## Purpose / Big Picture

ZW-009 将此前分散的“立项书预览”升级为通用 Artifact 系统和统一浮窗管理器。所有后续 Agent 产物都需要通过可版本化、可追踪依赖、可标记过期的 Artifact 边界进入 UI；完整查看必须使用右侧栏或浮窗，中央主对话保持常驻。

## Scope

- ArtifactDefinition、ArtifactVersion、ArtifactDependency、ArtifactPreview 和 FloatingWindow contracts。
- SQLite v7 产物与浮窗状态迁移。
- Sidecar Artifact Repository 与 HTTP API。
- 立项书生成、修订、确认、退回和过期时同步 Artifact。
- 右侧“产物”Tab 使用真实 Artifact API，支持状态、来源、依赖、版本切换与完整查看。
- 通用浮窗管理器支持最多 3 个浮窗、`singletonKey`、层级、位置、尺寸、最小化、最大化和关闭后状态保持。

## Non-goals

- Spec/Code/CAD/Lesson/Device Agent 的真实生成。
- 直接编辑产物正文。
- ZIP 导出导入和公开分享。
- 真实文件系统写入、Shell、串口、固件或 CAD 执行。

## Repository Orientation

| 模块 | 当前状态 | ZW-009 动作 |
|---|---|---|
| `packages/contracts` | 仅有 `ArtifactStatus` 枚举 | 新增 Artifact/FloatingWindow contracts 和 `ProjectPersistenceVersion.V7` |
| `services/local-api/zhangwen/artifacts/` | 不存在 | 新增 models、repository、router |
| `services/local-api/zhangwen/proposals/` | 立项书独立表 | 写入/更新对应 Artifact 版本 |
| `apps/desktop/src/components/right-panel/ArtifactsTab.tsx` | 直接读取 proposals | 改为读取通用 Artifact API |
| `apps/desktop/src/components/floating/FloatingWindow.tsx` | 单个 overlay | 升级为 Window Manager 可管理的浮窗实例 |
| `apps/desktop/src/components/layout/AppShell.tsx` | 单浮窗状态 | 改为最多 3 个浮窗并保留关闭状态 |

## Interfaces and Data Contracts

- `ArtifactKind`: `DOCUMENT | CODE | IMAGE | MODEL_3D | DEVICE_LOG | PACKAGE | REPORT`
- `ArtifactDependency`: `artifactId/versionId/kind/label/status`
- `ArtifactPreview`: 文档章节、代码文本、图片 URL、3D 占位、文本摘要。
- `ArtifactDefinition`: 稳定产物 ID、项目 ID、标题、类型、状态、来源 Agent、当前版本和所有版本。
- `ArtifactVersion`: 版本号、状态、MIME、校验和、依赖、预览、创建/确认时间和过期原因。
- `FloatingWindowSpec`: `id/kind/title/artifactId/versionId/singletonKey/bounds/zIndex/minimized/maximized`。

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python models、SQLite v7 migration 和 Artifact Repository。

### M2 Artifact API and Proposal Sync

实现 Artifact 列表/详情/内部 upsert API；立项书生命周期同步 Artifact 版本和状态。

### M3 Floating Window Manager UI

升级 AppShell/FloatingWindow/ArtifactsTab，支持最多 3 个浮窗、版本切换、状态保持和多类型预览。

### M4 Validation and Stage Close

运行受影响 Python tests、contracts build/typecheck、desktop typecheck/test/build 和 ZW-009 全量回归节点；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Artifact API and Proposal Sync
- [x] M3 Floating Window Manager UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- 前端 workspace 包依赖 contracts `dist`，新增 shared exports 后需要先运行 `pnpm --filter @zhangwen/contracts build`，否则 desktop typecheck 会看到旧导出。
- Proposal 同步 Artifact 时需要避免旧版本回写顶层 `currentVersionId` 和状态。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | 产物内容存储 | MVP 将预览内容存入 SQLite JSON/text，真实文件写入留给后续 Agent | 避免本阶段引入文件沙箱和路径权限，仍满足版本和预览追踪 |
| A-02 | 浮窗状态持久性 | 前端保存关闭前状态，Sidecar 提供 schema 预留 | 符合关闭/重开状态保持，不提前引入跨进程窗口恢复复杂度 |
| A-03 | 立项书迁移 | 立项书继续保留原表，同时同步为 Artifact | 避免破坏 ZW-006 API，同时为后续统一产物栏打基础 |

## Validation

- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `.\.venv\Scripts\python.exe -m py_compile services\local-api\zhangwen\artifacts\models.py services\local-api\zhangwen\artifacts\repository.py services\local-api\zhangwen\artifacts\router.py services\local-api\zhangwen\proposals\repository.py services\local-api\zhangwen\main.py services\local-api\zhangwen\projects\migrations.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw009_artifacts_windows.py -v --rootdir services/local-api`：3 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py services/local-api/tests/test_zw006_proposals.py services/local-api/tests/test_zw008_skills_model_router.py services/local-api/tests/test_zw009_artifacts_windows.py -v --rootdir services/local-api`：16 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- RightPanel.test.tsx ProjectWorkspace.test.tsx`：6 files / 40 tests passed。
- `pnpm --filter @zhangwen/desktop test`：6 files / 40 tests passed。
- `pnpm --filter @zhangwen/desktop build`：通过，Vite 输出 `apps/desktop/dist/`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api`：67 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe scripts/check_ai_assets.py`：通过，Shared Skills are in sync。
- `rg -n "sk-[A-Za-z0-9]|DEEPSEEK_API_KEY|apiKey|api_key" --glob '!node_modules/**' --glob '!apps/desktop/dist/**' --glob '!services/local-api/.pytest_cache/**'`：无命中。

## Outcomes & Retrospective

- 已新增 Artifact/FloatingWindow shared contracts。
- SQLite schema 升级到 v7，新增 `artifacts`、`artifact_versions` 和 `floating_window_states`。
- 已实现 Artifact Repository 和 API。
- 立项书生成、修订、确认、退回、过期会同步 Artifact 版本和状态。
- 右侧“产物”Tab 改为读取通用 Artifact API，支持状态、依赖、版本切换和导出入口。
- AppShell 管理最多 3 个浮窗，同一 singletonKey 不重复打开；浮窗操作不卸载中央主对话。

## Handoff

自动验收已通过。下一步：提交 `feat: complete ZW-009 artifact and window system` 并创建 `zw-009-complete` 标签，然后进入 ZW-010。
