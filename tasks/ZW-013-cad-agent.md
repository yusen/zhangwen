# ZW-013 CAD Agent

## Purpose / Big Picture

ZW-013 建立 CAD Agent 的安全软件闭环。MVP 需要能从已确认 Spec 生成结构件参数、执行受控模板、输出 STEP/STL 预览内容、记录基础几何校验，并同步为 3D Artifact。当前阶段不执行任意用户 Python，不要求真实 CadQuery 运行时或真实文件导出。

## Scope

- CAD shared contracts 与 Python Pydantic models。
- SQLite v11 `cad_runs` 与 `cad_files`。
- 受控 CAD 模板：传感器支架、主控板支架、电机支架、舵机支架、简单外壳、面板开孔、盒体与盖板。
- 参数 Schema、尺寸范围校验和基础几何校验。
- 生成 STEP/STL 文本预览与 `MODEL_3D` Artifact。
- 右侧“工作”Tab 显示 CAD 生成状态和 3D 产物入口。

## Non-goals

- 执行任意用户 Python。
- 真实 CadQuery import、真实网格布尔运算或真实文件系统导出。
- 3D 渲染引擎、物理仿真、CNC/3D 打印切片。
- Lesson、Share 和 MVP 硬化阶段实现。

## Interfaces and Data Contracts

- `CadTemplateKind`: `SENSOR_BRACKET | MCU_MOUNT | MOTOR_MOUNT | SERVO_MOUNT | SIMPLE_ENCLOSURE | PANEL_CUTOUT | BOX_WITH_LID`
- `CadRunStatus`: `DRAFT | VALIDATED | READY_FOR_REVIEW | APPROVED | REJECTED | STALE | FAILED`
- `CadParameter`: `name/label/unit/value/min/max`
- `CadValidation`: `ok/checks`
- `CadFile`: `kind/path/mimeType/content/artifactId/artifactVersionId`
- `CadRun`: `id/projectId/specRunId/templateKind/version/status/parameters/validation/files/artifactId/artifactVersionId`
- `GenerateCadRequest`: `specRunId/templateKind?`
- `ConfirmCadRequest`: `cadRunId`
- `RejectCadRequest`: `cadRunId/reason?`

## Milestones

### M1 Contracts and Schema

新增 CAD contracts、Python models、SQLite v11 migration。

### M2 CAD Generator and API

实现受控模板生成、参数校验、current/generate/confirm/reject API。

### M3 CAD Artifact and UI

同步 `MODEL_3D` Artifact；右侧工作 Tab 显示 CAD 状态与操作。

### M4 Validation and Stage Close

运行 contracts、Sidecar、desktop 受影响验证；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 CAD Generator and API
- [x] M3 CAD Artifact and UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- CadQuery is intentionally not imported in this stage. The repository records a dry-run command label and deterministic STEP/STL previews so tests remain portable and safe.
- Project schema assertions and frontend fixtures needed to advance from v10 to v11 across historical test files.

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | CAD 执行策略 | 受控模板确定性生成，不执行任意用户 Python | 满足安全边界并保持自动测试可重复 |
| A-02 | CadQuery 运行时 | MVP 记录 `cadquery-template-dry-run` 命令标签，不要求真实 CadQuery | 当前环境不保证 CadQuery 安装，ZW-013 目标是安全执行框架和产物契约 |
| A-03 | 3D 预览 | 使用 `MODEL_3D` Artifact + `artifact://` modelUrl | 复用现有产物和浮窗系统，不替换中央主对话 |

## Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen/cad_agent services/local-api/zhangwen/main.py services/local-api/zhangwen/projects/migrations.py services/local-api/zhangwen/artifacts/repository.py`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw013_cad_agent.py -v --rootdir services/local-api`：4 passed；仅 Starlette/httpx deprecation warning 和 pytest 退出时临时目录清理 `PermissionError`。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -v --rootdir services/local-api`：83 passed；仅 Starlette/httpx deprecation warning 和 pytest 退出时临时目录清理 `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- --run src/__tests__/RightPanel.test.tsx`：44 passed（Vitest 实际运行桌面测试全套 6 files）。
- `pnpm --filter @zhangwen/desktop build`：通过。
- 敏感信息扫描：新增 CAD 代码和文档无真实凭据、真实串口或设备标识；全仓扫描仅命中既有安全文档/测试假密钥示例和 API Key 字段名。

## Outcomes & Retrospective

- 完成 CAD shared contracts、Python models、SQLite v11 migration、Sidecar CAD API、受控模板生成、参数/几何校验、`MODEL_3D` Artifact 同步和右侧“工作”Tab CAD 操作。
- 未引入真实 CadQuery、真实 shell、真实文件导出或任意用户 Python 执行。
- 中央主对话保持常驻；CAD 状态在右侧工作栏，3D 预览复用产物/浮窗系统。

## Handoff

ZW-013 软件能力已自动验收通过，下一步是创建阶段提交 `feat: complete ZW-013 CAD agent` 并打标签 `zw-013-complete`，随后进入 ZW-014 Lesson Agent。
