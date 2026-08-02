# ZW-012 设备管理与 MicroPython 部署

## Purpose / Big Picture

ZW-012 建立设备管理和 MicroPython 部署的软件闭环。MVP 需要能发现 Mock ESP32 串口、创建设备会话、基于已接受代码草稿生成上传计划、执行 Dry Run 上传、记录 REPL/上传日志，并为真实设备验收输出确认点。本阶段不执行真实串口访问、Flash 擦除、固件烧录或设备文件覆盖。

## Scope

- Device shared contracts 与 Python Pydantic models。
- SQLite v10 `device_sessions` 与 `device_operations`。
- Mock 串口发现与设备会话。
- MicroPython 文件上传 Dry Run，默认使用 `mpremote` 命令标签但不执行命令。
- 固件烧录 Dry Run，需要显式确认字段，永不自动擦除 Flash。
- 设备日志 Artifact 同步。
- 右侧“设备”Tab 显示端口、会话、上传计划、操作确认和日志。

## Non-goals

- 真实 pyserial 串口扫描。
- 真实 `mpremote`、`esptool` 执行。
- 真实 Flash 擦除、固件烧录或设备文件覆盖。
- 安装驱动、管理员权限、硬件自动验收。
- CAD、Lesson、Share 阶段实现。

## Repository Orientation

| 模块 | 当前状态 | ZW-012 动作 |
|---|---|---|
| `packages/contracts` | 有 `DeviceSessionStatus` 枚举，无设备 API contracts | 新增 DevicePort、DeviceSession、DeviceOperation、请求响应和 `ProjectPersistenceVersion.V10` |
| `services/local-api/zhangwen/devices/` | 不存在 | 新增 models、simulator、repository、router |
| `services/local-api/zhangwen/artifacts/` | 支持文本 Artifact | 复用通用 text artifact upsert 写入设备日志 |
| `apps/desktop/src/components/right-panel/DevicesTab.tsx` | 静态占位 | 改为读取 Mock 设备 API 并触发 Dry Run 操作 |

## Interfaces and Data Contracts

- `DevicePort`: `id/label/transport/chip/serialNumber/available`
- `DeviceSession`: `id/projectId/portId/board/status/connectedAt/lastSeenAt/logs`
- `DeviceOperation`: `id/projectId/sessionId/kind/status/dryRun/commandLabel/log/artifactId/artifactVersionId/createdAt/completedAt`
- `ListDevicePortsResponse`: `ports`
- `ConnectDeviceRequest`: `portId`
- `DeviceSessionResponse`: `session`
- `UploadCodeRequest`: `codeRunId/sessionId/dryRun`
- `FirmwareFlashRequest`: `sessionId/dryRun/confirmFlash`
- `DeviceOperationResponse`: `operation/session`

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python models、SQLite v10 migration。

### M2 Device Service and API

实现 Mock port discovery、connect、current session、upload dry run、firmware flash dry run API。

### M3 Device Artifact and UI

设备操作日志同步为 Artifact；右侧设备 Tab 显示状态、端口、上传和固件 Dry Run 确认。

### M4 Validation and Stage Close

运行 contracts、Sidecar、desktop 和 ZW-012 全量回归节点；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Device Service and API
- [x] M3 Device Artifact and UI
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- pytest 断言通过后仍会输出既有临时目录清理 `PermissionError: [WinError 5]`，不影响测试退出码。
- 右侧设备 Tab 测试最初有异步 act warning，等待 Mock 端口加载后已消除。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | 自动测试设备策略 | 只使用 Mock 串口和 Dry Run | 避免真实设备依赖和高风险写入 |
| A-02 | 上传默认工具 | 使用 `mpremote` 命令标签，不执行命令 | 符合 MicroPython 日常上传首选 USB 串口，同时遵守 Tool Runner 边界 |
| A-03 | 固件烧录 | 必须显式 `confirmFlash` 且保持 Dry Run | 保留确认点，禁止自动真实 Flash 擦除和固件烧录 |
| A-04 | 2026-07-12 连接恢复 | 完整入口启动 Sidecar、Vite 与 Tauri 的同一 capability token；设备探测只读取 MicroPython、平台、机型和固件信息 | 避免旧 Sidecar 会话漂移，并避免导入板载库导致 ESP32 重启 |

## Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen/devices services/local-api/zhangwen/main.py services/local-api/zhangwen/projects/migrations.py`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw012_devices.py -v --rootdir services/local-api`：5 passed，1 个 Starlette deprecation warning，退出后出现既有 pytest 临时目录清理 `PermissionError`。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api`：79 passed，1 个 Starlette deprecation warning，退出后出现既有 pytest 临时目录清理 `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test`：43 passed。
- `pnpm --filter @zhangwen/desktop build`：通过。
- `pnpm --filter @zhangwen/desktop test -- --run src/__tests__/RightPanel.test.tsx`：43 passed，无 act warning。
- 敏感信息扫描 `sk-*`、`DEEPSEEK_API_KEY/apiKey/api_key/Authorization`、真实串口模式 `COM[0-9]/ttyUSB/ttyACM`：无命中。
- 2026-07-12：在桌面应用内完成真实设备的只读扫描、连接和断开；未上传、复位、擦除或烧录 Flash，且未记录真实端口或序列号。
- 2026-07-12 剩余回归：Health/Web Host 8 passed，Device Service/设备路由 38 passed，设备前端聚焦 4 passed，API Client 3 passed；`pnpm typecheck`、Cargo check、Python `compileall`、启动器语法与 `git diff --check` 均通过。
- 2026-07-12 实机复测：从断开状态重新扫描，扫描时间成功刷新；随后连接显示 `ESP32 已连接` 与 `ESP32 · 就绪`，无红框或超时，最终断开并确认无残留设备工具进程。
- 2026-07-12 全量补充：Sidecar 255 passed；前端 109 passed、5 failed。5 个失败均属于并行 ZW-AGENT-006 的中央确认流，设备页相关用例无失败。

## Outcomes & Retrospective

- 完成 Device contracts、SQLite v10、Python models、Mock port discovery、device session、upload dry run、firmware flash dry run、DEVICE_LOG Artifact 和右侧设备 Tab。
- 自动测试只使用 Mock/Dry Run；未调用真实串口、真实 shell、真实 `mpremote`、真实 `esptool`、真实 Flash 或真实付费 LLM。
- 真实 ESP32 串口上传、真实固件烧录和真实设备文件覆盖保留为外部硬件验收待办。

## Handoff

ZW-012 软件实现与 Mock/Dry Run 自动验收已完成。下一步创建阶段提交并打 `zw-012-software-complete` 标签，然后自动进入 ZW-013 CAD Agent。
