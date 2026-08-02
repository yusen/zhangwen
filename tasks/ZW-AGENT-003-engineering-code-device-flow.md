# ZW-AGENT-003 - 工程代码工作台与设备部署闭环

状态：已提交（ZW-AGENT-001 至 005 工程节点）

## 1. 目标

修复智能工程师代码只以原始 Markdown 出现在聊天、未形成 `.py` 产物的问题；将代码以结构化卡片和可打开的 Monaco 浮窗呈现；补齐清晰的项目添加、软删除和恢复入口；在保持 Web 安全边界的前提下，为桌面/Tauri 宿主实现真实串口扫描、设备连接、MicroPython 文件上传和独立固件烧录流程。

## 2. 不可变边界

- 中央区域仍是唯一项目主对话；代码编辑、设备详情和长日志只进入右栏或浮窗。
- 右侧一级 Tab 仍固定为“工作 / 产物 / 设备”，不新增代码或烧录一级 Tab。
- 云端 LLM 只返回文本和受限结构化代码候选；CodeRun、文件、Shell、串口和设备操作全部由本地 API/Runner 校验与执行。
- 项目“删除”使用可恢复的软归档；不实现硬删除数据库、工作区或历史产物。
- Monaco 使用本地依赖和本地 Worker，不从 CDN 加载；后端保存与真实退出码仍是代码状态唯一来源。
- Web Host 继续禁止串口扫描、连接、上传和烧录；真实设备控制只在桌面/Tauri 宿主开放。
- MicroPython 日常上传默认 USB 串口文件上传；上传与固件烧录严格分离，不提供 Flash 擦除操作。
- 自动测试只使用 Fake Provider、Fake DeviceTransport 和 Dry Run；不得扫描真实串口、运行真实 mpremote/esptool、连接设备或烧录固件。

## 3. 可观察验收

- 智能工程师消息中的标题、列表和 fenced code 不再挤成一段原始文本；Python 代码显示为结构化代码区或 Code Artifact 卡片。
- 智能工程师返回的受限结构化 `codeDraft` 可由本地服务在 IDEA/无 Spec 阶段创建不可变 CodeRun/ArtifactVersion；`/code/generate` 仍保持 approved Spec 门禁。右侧“产物”立即出现对应代码，聊天卡可直接打开编辑浮窗。
- 旧智能工程师消息中可解析的 Python fenced code 可以通过明确按钮导入当前项目 Code Artifact；导入不制造 Spec 依赖，并创建待验证的 DRAFT 版本。
- 顶栏和左栏都有清晰项目添加入口；每个项目有独立删除按钮，二次确认后进入归档；归档列表可恢复，消息、草稿和产物不丢。
- 代码浮窗使用 Monaco 编辑 Python/Markdown；切换文件、二级视图、保存、409 冲突和验证时保持原有草稿与版本语义。
- 桌面设备页可以扫描真实系统串口，连接前重新确认端口仍存在，并可断开会话；测试通过注入 Fake DeviceTransport 完成。
- 真实 MicroPython 上传只接受已确认 CodeRun，生成固定本地 staging，上传 `.py` 前备份同名设备文件；使用端口锁、固定 argv、`shell=False`、超时、取消和幂等 operation ID。
- 上传后回读设备文件并比对 SHA-256；只有真实退出码和内容校验都成功才标记 `COMPLETED`/设备就绪。
- 固件流程要求选择 `.bin`、校验大小与 SHA-256、填写地址、显示命令计划、勾选风险并输入确认短语；烧录前备份将被覆盖区域，烧录后执行 verify。流程不调用 `erase-flash`。
- 操作状态、失败原因、备份位置、验证摘要和日志同步到现有 DeviceOperation/DEVICE_LOG Artifact，不新增平行设备领域模型。
- 390x844、720x720、1280x720 下 Monaco、项目按钮和代码卡无页面横向溢出、遮挡或不可达主要操作；Web 设备页只显示安全说明并禁用本地副作用；`CenterChat` 始终单一挂载且草稿保留。

## 4. 实施步骤

- [x] M1：扩展共享 contracts 与测试，增加代码消息/导入契约、归档查询和真实设备操作状态。
- [x] M2：实现 Markdown/代码消息结构化、聊天代码本地产物化、产物刷新和项目添加/归档/恢复 UI。
- [x] M3：接入本地 Monaco Worker，保持现有不可变保存、409 保稿和验证测试。
- [x] M4：实现可注入 DeviceTransport、串口连接/断开、真实上传备份/锁/超时/取消/幂等/回读验证。
- [x] M5：实现独立固件 staging、哈希/地址/确认、覆盖区备份、烧录与 verify；Web Host 继续阻止真实执行。
- [x] M6：完成自动测试、390/720/1280 UI 验收、API/UI/安全文档和 HANDOFF。

## 5. Decision Log

- 2026-07-11：任务编号使用用户定向 `ZW-AGENT-003`，不是被工作流禁止的 `ZW-017`；它在 ZW-016 后由用户明确提出。
- 2026-07-11：聊天中的代码候选只在智能工程师边界内物化；Provider 不能提供数据库 ID、主机路径或命令，所有路径、版本和 Artifact 链接由本地服务生成。
- 2026-07-11：当前已有消息由前端安全 Markdown 渲染并提供显式“保存到产物”动作；结构化 `codeDraft` 可在无 Spec 阶段由本地服务物化，避免对 GET/页面加载引入隐式写入。`/code/generate` 的 approved Spec 门禁保持不变。
- 2026-07-11：项目删除沿用现有 `archived_at` 软归档，并新增归档列表与恢复；不新增硬删除 API。
- 2026-07-11：Monaco 直接使用本地 `monaco-editor` ESM API 和 Vite Worker，避免 `@monaco-editor/react` 默认 CDN loader；React 薄封装保持父组件 drafts 为唯一编辑状态。
- 2026-07-11：真实设备能力只在桌面/Tauri Host 开放。Web 正常模式仍可查看设备状态与安全说明，但不能通过 localhost Sidecar 绕过 Host Adapter。
- 2026-07-11：设备 operation ID 同时作为客户端提供的幂等键，复用现有 `device_operations.id` 主键，不为同一概念新增数据库表或 schema 迁移。
- 2026-07-11：不实现 Flash 擦除；固件烧录仅允许 `write-flash`，并强制覆盖区备份、确认短语和烧录后 verify。
- 2026-07-11：schema v23 仅把 `code_runs.spec_run_id` 改为 nullable，以便无 Spec 的结构化回复和历史导入复用同一 CodeRun/Artifact 版本图；旧行、外键、文件、补丁和索引完整迁移。
- 2026-07-11：真实设备副作用要求 Tauri 与 Sidecar 每次启动共享的临时 capability token；仅伪造 `X-Zhangwen-Host: tauri` 不能获得权限。异步上传/烧录复用 DeviceOperation ID 轮询，不新增事件总线。
- 2026-07-12：历史 fenced Python 导入只保留消息中实际提供且可上传的安全 `src/*.py`；不再生成 README、测试或配置/驱动占位文件。旧五文件导入仍不可变，新导入 scope 只创建一次上传用新版本。
- 2026-07-12：代码接受入口属于 Code Artifact 浮窗“验证”二级视图；仅 `READY_FOR_REVIEW` 且三项真实退出码全为 `0` 时可用。接受后复用现有刷新修订同步产物和设备页，不新增一级 Tab、接口或设备模型。
- 2026-07-12：真实上传的文件写入、逐文件 SHA-256 回读和设备重启，与重启后的 REPL 管理通道恢复是不同结论；后者失败不能否定已验证的文件部署，也不能充当用户程序业务效果验证。具体可靠性修复由 `ZW-AGENT-004` 收口。

## 6. Progress

- 2026-07-11：读取 AGENTS、HANDOFF、PLANS、ZW-009/011/012 和 UI Contract；执行位置、工作树状态、diff stat 与 `git diff --check` 基线检查，确认保留现有大规模未提交修改。
- 2026-07-11：截图与标准数据目录中的现有消息确认根因：`CenterChat` 用普通 `<p>` 渲染 Markdown；智能工程师输出只写 message content，未创建 CodeRun 或 structured payload。
- 2026-07-11：确认代码编辑器当前为 textarea，仓库无 Monaco；项目创建只在可折叠左栏，归档藏在项目工具且没有恢复入口。
- 2026-07-11：确认 ZW-012 已有真实串口枚举与 Mock/Dry Run UI，但 connect 固定走 Mock，真实 upload/flash 被 Router 阻止，且仓库尚未安装 pyserial/mpremote/esptool。
- 2026-07-11：完成安全 Markdown、结构化 `code_artifact`、历史 Python 显式导入和无 Spec CodeRun v23 迁移；Provider 不能伪造数据库 ID、路径或 Artifact 链接。
- 2026-07-11：完成本地 Monaco Worker、不可变编辑/409 保稿/真实退出码验证，以及顶栏/左栏新建、项目软删除、归档列表与恢复。
- 2026-07-11：完成可注入 DeviceTransport、桌面串口扫描/连接/断开、确认式 MicroPython 上传、备份/锁/超时/取消/幂等/回读 SHA-256，以及独立固件 inspect/prepare/write-flash/verify；Web Host 和伪造 Tauri header 均被临时令牌门禁阻止。
- 2026-07-11：全量门禁已通过：后端 208 tests、前端 95 tests、Contracts build、TypeScript typecheck、Cargo check、pip check 和 MicroPython Skill quick validation；刷新草稿测试的 React `act(...)` warning 已消除。M6 等待正常模式三档浏览器验收和最终交接更新。
- 2026-07-11：真实 K10 验收前发现两个闭环缺口：聊天 Python 导入错误补齐了非上传用 README/config/drivers/tests，且验证通过的 `NEEDS_REVIEW` Code Artifact 浮窗没有“接受代码”入口，导致设备页持续显示“等待已接受代码”。本里程碑先修复并回归这两处，再生成仅含实际 `.py` 上传文件的新版本并执行受控硬件上传。
- 2026-07-12：上述缺口已修复。真实项目保留旧五文件 v1，并创建只含 `src/main.py` 的不可变 v2；STATIC/SYNTAX/SIMULATION 三项退出码均为 `0`，v2 已接受。用户在明确授权的 K10 端口手动执行一次真实上传，持久化 DeviceOperation 为 `COMPLETED/COMPLETE`：PREFLIGHT、BACKUP、TRANSFER、VERIFY_FILES、RESTART、RECONNECT 六阶段退出码均为 `0`，备份和回读文件均只有 `main.py`，源文件与设备回读 SHA-256 一致，会话回到 `READY`。
- 2026-07-12：随后针对用户提供的 `main.py` 创建并接受单文件新版本；本地静态、语法、模拟验证均为退出码 `0`。真实记录中备份、传输、逐文件回读和设备重启均通过，重连管理通道超时；用户确认新程序在 K10 上实际运行。该证据触发 `ZW-AGENT-004` 修复“部署已成功但整体误报失败”的状态语义，本节点收尾不再重复扫描、连接或上传。
- 2026-07-12：`ZW-AGENT-004` 完成状态机、幂等恢复、最近操作读取、设备 UI、历史 DEVICE_LOG 一致性和 Provider 设备脱敏；最终后端 `235 passed`、前端 `111 passed` 及全部构建/静态门禁通过，标准模式 1280 浏览器与既有 390/720 响应式基线复核通过。M6 收尾完成，本轮未再次操作真实设备。

## 7. Safety

- 自动测试仍不执行真实串口、`mpremote` 或 `esptool`。仅在用户明确授权后，由用户通过 Tauri 桌面流程执行了一次 K10 MicroPython 日常上传；未把真实端口标识或设备序列号写入仓库。
- 不在测试、日志、任务文件或 Git 中写入真实串口号、设备序列号、API Key、Wi-Fi 密码或固件私有内容。
- 不把用户代码上传按钮与固件烧录按钮合并；固件操作必须始终保持独立风险说明和确认点。
- 不执行 `erase-flash`，不自动重刷固件，不因扫描到 ESP32 就推断用户同意操作。
- 不运行 `git reset --hard`、`git clean`，不覆盖或暂存 `tasks/ZW-UX-003-three-expert-system.md` 的用户自有差异。
