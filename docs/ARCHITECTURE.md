# 掌问技术架构

## Creator V3 聚合、证据与交付（V30）

Creator V3 是现有平台内核之上的聚合层，不是第二套项目系统。React `creator/` 模块提供“我的作品”、
持续对话和创意与方案/数字原型/3D 结构/实物运行四阶段；FastAPI `creator/` 服务从项目、方案、
Artifact、CAD、Device Lab、CodeRun 和设备操作的关系事实重建 `CreatorWorkspace`，服务端独占
生命周期、0–6 等级和唯一 `nextAction` 的投影权。

V30 保存 Goal/Solution 修订、AcceptanceScenario、Evidence、幂等命令、事件、不可变真机验收、
交付、导入和第二用户复现记录。Creator 证据绑定当前场景、代码、参数和结构修订；这些关系真值
变化时，读取/命令边界将受影响证据标为 `STALE` 并自动降低等级，历史记录不删除。

等级 6 只由真机行为之后的明确人类验收产生。交付服务在既有安全 Project Package 外包裹严格
`creator-delivery/v1` manifest、脱敏工作区/证据、隐私报告和复现指南，提供分享、可复现、模板三种
变体。导入创建新 ID 图并把验证重置到等级 1；不同于原验收者的第二用户在副本独立达到等级 6
后，才能用相同包 SHA-256 形成原作品复现证据。详细格式见 `docs/CREATOR_DELIVERY.md`。

旧 AppShell/V2AppShell 在 M8 真人、真实硬件和安装包验收前只作为教学/迁移回退入口保留，不能
继续决定 Creator 产品结构。

## 0.0 双板项目实物仿真与代码部署（V29）

详细契约、信任边界和能力矩阵见 `docs/DEVICE_LAB.md`。V29 只允许
`dfrobot/dfrobot_k10` 与 `seeedstudio/xiao_esp32s3_sense` 进入主控设备操作；硬件目录、
项目创建、AI 上下文、立项场景投影、串口、ESP-Claw、仿真、安装和参数同步共用同一白名单。

立项确认后，本地 Scene Projector 从已确认硬件、BOM、IO Map 和立项内容生成不可变项目
实物场景。仿真运行绑定场景 revision，不接受前端板型覆盖。USB 串口与 ESP-Claw 是同级
`UPLOAD_CODE` 通道：前者消费 MicroPython CodeRun，后者消费 ESP-Claw Lua CodeRun；
ESP-Claw 运行时安装仍是独立维护状态机。所有写入由本地 Device Runner 执行并实施受信
局域网人工配对、双端点握手、目标锁、幂等、取消、备份、超时和回读校验；云端模型与 Web Host 不获得设备
或 Flash 权限。

Creator V3 在此安全执行器之上增加聚合证据边界：设备连接必须引用就绪的串口会话或已配对
ESP-Claw 端点，部署必须引用完成且通过回读验证的非 dry-run `UPLOAD_CODE`。真机行为不从部署
状态推断，而由不可变 `creator_physical_runs` 记录当前方案、部署、目标、操作者、急停确认和逐项
场景观察；只有通过报告才能形成等级 5。没有 `zwdbg/1` 握手时，真机原始传感器保持只读且无伪造
遥测，执行器图形控制失败关闭。

版本：v2.0-implementation.1
日期：2026-07-26

## 0.1 M7 对话流体化与主动推进

M7 不建立第二套对话或工程状态。React 在普通模式增加“当前待回答问题”的本地呈现状态：
新问题只显示一个，历史多问题按顺序收集，收齐后复用现有批量提交事务。`CenterChat` 始终
单一挂载，查看代码、3D、成果和设备只改变右侧检查器或浮窗。

问题引导师、智能工程师、结构工程师共用主动推进策略：可逆低风险细节使用推荐默认值，
非阻塞缺口进入后续验证项，改变方向时最多提出一个最高影响阻塞问题。服务端 validator
对新 clarification 结果执行单问题上限；contracts、SQLite schema、SSE 与历史数据不变。

CAD intake 继续以当前请求优先于 revision 和 `ProjectStructureContext`。本轮自然语言中
明确给出的盒体尺寸会在 canonicalize 前写入受控 intent；仅缺少非方向性盒体尺寸时使用
推荐默认值，后续“改成 120×80×40”会创建新修订。自由结构不被尺寸文本误判为盒体。

设备 Runner、安全能力和 Web Local Bridge 边界不变。扫描、连接、上传、复位、Flash 与
固件烧录始终是显式用户动作；“默认主动推进”不授予任何本地设备权限。

## 0. V2 当前架构（覆盖下文 V1 UI 说明）

V2 保留 V1 的本地权威、安全门禁、账号/项目数据和三师领域能力，但用“项目工作区 + Project Kernel + 受控本地执行”替换中央对话常驻和固定右栏三 Tab。下文 V1 章节仍作为迁移基线；涉及 UI 布局、数据库版本和本地能力调用时，以本节、`docs/PRD_V2.md` 和 `docs/UI_CONTRACT.md` 为准。

```text
React V2：概览 / 工程 / 结构 / 交付 + 全局 AI 协作面板
                         │
                         ▼
FastAPI /api/v2 ── Project Kernel ── SQLite schema v28
       │             │   ├─ Project State projection
       │             │   ├─ Change Set / Version / Release
       │             │   └─ Capability Facade / Tool Job
       │             │
       │             ├─ CAD Intent Adapter ── JSONL Worker ── 受控 staging / Artifact
       │             └─ Device Runner ── attach / takeover / upload / recovery
       │
       └─ Local Bridge：loopback + Origin allowlist + 项目短租约 + 写请求防重放
```

- Project State 是现有关系数据的权威投影，不复制成第二套巨大 JSON 真值；正式改变必须先成为 Change Set，再确认、提交并产生版本。
- V1→V2 兼容由 Project Kernel 在读边界完成：已存在确认方案、已批准立项、有效 Artifact、硬件选择、设备操作或 CAD 运行记录且尚无 V2 版本时，事务性建立唯一的 V1 导入基线。后续 V2 页面继续直接读取关系表中的方案、`preferred_hardware`、Artifact、设备和 CAD 记录，因此基线不是第二套业务真值。
- V2 工程页的硬件、代码、设备和验证分别读取 Project State confirmed fact、Artifact API、既有安全设备工作区和 `ProjectProgressSnapshot`；交付页同时读取 V2 Version/Release 与全部实际 Artifact。页面不再用对话摘要、空 SharedContext 或硬编码占位推断工程完成度。
- V2 AI 面板复用 V1 项目历史、草稿和三师领域 Runtime，但增加页面上下文层：概览/工程子页/结构/交付决定默认主责工程师，`workspaceKind/workspaceView/projectVersion` 经固定 allowlist 后同时进入问题引导师与 Expert Runtime。切页不创建新聊天，导航上下文不授予工具权限。
- 当前是兼容过渡态：Chat/Expert Runtime 已理解 V2 页面，但其领域输出仍通过 V1 facts、Artifact、PendingItem 仓储落地；Project Kernel 随后投影这些事实。V2 目标中的“所有正式修改先成为 Change Set 再产生 Project Version”尚未覆盖全部对话输出，必须作为后续独立迁移完成，不能把上下文感知等同于 Change Set 化。
- CAD Worker 不提供独立 HTTP、账号、Provider 或项目库；它只接收 hash 绑定的声明式请求，使用宿主拥有的临时目录并返回可持久化结果。真实 CadQuery 构建环境属于 M6 外部验收。
- 设备 `connect` 只建立 `ATTACHED_UNVERIFIED` 附加，不执行 identity probe；首次写入或显式“安全接管”按 Ctrl-C、提示符、identity 的顺序建立 `MANAGED` 会话。硬件 reset 必须二次短语确认并在端口重枚举后重新接管。
- Web 本身仍不能执行本地 CAD/串口。只有已授权桌面创建的两分钟配对挑战，才能让 allowlist Origin 领取十分钟、项目绑定的 `cad.local / device.serial / device.upload` lease；Shell、凭据、任意路径和固件烧录永不进入 Bridge 能力集合。
- 默认自动测试仅使用临时数据库、CAD Worker、Fake transport 和模拟重枚举；真实 Provider、CadQuery 环境、串口、reset、上传、Flash、安装包和发布必须分开验收。

## 1. 架构目标

掌问是本地优先的 AI 创客工程桌面工作台。架构必须同时保证：

- 中央主对话常驻，工作/产物/设备使用右侧栏或浮窗。
- 三师拥有独立线程和最小必要上下文。
- 生产 AI 理解和生成经由用户选择的 DeepSeek、千问、GLM 或 Kimi OpenAI 兼容 Provider，失败不伪造本地模板结果。
- 权限、状态、持久化、硬件规则和外部效果保持本地权威。
- 云端 LLM 不直接访问文件、Shell、串口或设备。

## 2. 进程与数据流

```text
用户
→ React/Vite 桌面 UI
→ AuthGate（注册 / 登录 / 会话恢复）
→ Tauri 宿主
→ FastAPI 本地 Sidecar
→ AuthSessionMiddleware（Bearer 会话门禁）
→ 应用路由 / 三师 Runtime / ProjectCoordinator
→ Repository / LLM Gateway / ToolRunner
→ 认证 SQLite + 项目 SQLite / DeepSeek / 受控本地工具与设备
```

桌面端只调用本地 API，不直接读写 SQLite、执行 Shell 或操作串口。

### 本地启动、诊断与恢复

- `start-local.bat` 是唯一完整开发入口。启动器通过带仓库根、PID、进程启动时间和端口的所有权记录托管 Vite；只有四项均匹配时才回收上一轮残留，不按 Node/Python 进程名扫描或误杀其他服务。
- Tauri 首次拉起 Sidecar 失败时仍打开桌面，让健康状态和本地日志可见；运行期按 1–30 秒退避恢复，连续六次失败后停止。stdout/stderr 与脱敏状态码写入有界、可轮转日志。
- 安装态冻结 Sidecar 包含 CAD/VTK 与设备工具链。干净 Windows 首次安全扫描可能延迟导入，因此单次就绪预算为 120 秒；它仍是有限等待，不改变六次恢复上限。Hardware Skill 初次安装保持临时目录 + 原子替换，并仅对 Windows 扫描器造成的短暂 `PermissionError` 做最多八次、上限 1 秒的退避重试。
- React 健康检查保留最近成功状态：前两次连续失败显示“正在恢复连接”，第三次才显示“本地服务未连接”；成功立即清零。顶栏状态不代表 Provider 或硬件已连接。

### 多 Provider 模型配置与流式兼容

- DeepSeek、千问、GLM 和 Kimi 共用受控的 OpenAI-compatible Chat Completions 传输。配置保存到脱敏 JSON，Provider API Key 继续按服务商隔离在系统 Credential Store；生产业务只通过 `require_llm_config()` 读取已保存的同一份配置与凭据。
- Kimi 内置目录为 `kimi-k3`、`kimi-k2.7-code`、`kimi-k2.7-code-highspeed`。专业模式允许在默认折叠的高级参数中添加 Provider 绑定的自定义模型代码；它只扩展模型目录，不改变 Base URL、凭据、文件、Shell、串口或 ToolRunner 权限。
- 内置模型在 Python 边界保持枚举以兼容现有项目逻辑，自定义模型使用经过长度和字符集限制的字符串；二者在项目 SQLite 中继续按文本持久化，加载时内置值恢复为枚举、自定义值保持字符串。
- SSE 解析先处理 usage，再读取可选 choices；省略 choices 或 `choices: []` 的用量帧只更新最终 token 统计，不结束流也不产生正文。Kimi 与 GLM 使用同一回归边界，避免连接测试成功而结构化业务流因空数组失败。
- Provider 差异只在 payload 适配层处理：GLM 的 `thinking` 对象与顶层 `reasoning_effort`、Kimi 的顶层 `reasoning_effort`、千问的 `enable_thinking` 不向项目业务层扩散。

启动访问链路为：

```text
AuthGate → GET /api/auth/status
→ 首台账号注册，或已有账号登录 / 恢复本地 token
→ Sidecar 校验 Bearer token 摘要、撤销状态与 30 天有效期
→ 成功后才挂载 AppShell
→ 任意业务 401 清除本地 token 并卸载工作台
```

账号是设备本地访问门禁。密码使用随机盐 PBKDF2-HMAC-SHA256 派生；Sidecar 只保存派生值，认证库只
保存会话 token 的 SHA-256 摘要。认证库位于 `<data_dir>/auth/zhangwen-auth.sqlite3` 且独立版本为 v1；
项目库继续为 v25。当前账号不决定项目归属，多账号仍访问这台设备的同一项目库。

项目硬件选择在入口分析后复用本地 Hardware Skill 与项目事实链路：

```text
ProjectCreationDialog 创意 → POST /api/projects/suggest → EntryRouter
→ 分析成功后打开 HardwareSelectionDialog
→ GET /api/hardware（仅 ACTIVE）
→ POST /api/projects 时 Sidecar ACTIVE + Rule Engine 校验
→ confirmed preferred_hardware SharedFact
→ ContextAssembler 每轮精确水合
→ ExpertRuntime 可返回 hardware_selection（仅缺少能力名称）
→ 中央卡 / 项目工具打开同一选择器
→ PUT /api/projects/{projectId}/hardware
→ 原子 supersede 旧事实并让下一轮只读取最新选择
```

Hardware Skill 编辑复用现有浮窗体系：

```text
设置 / 项目工具的组件知识入口
→ FloatingWindow(kind=hardware-skill, singletonKey=hardware-skill:{skillName})
→ HardwareSkillEditor（目录树 + Monaco）
→ GET/PUT Hardware Skill 文件 API
→ <data_dir>/hardware-skills + 整体 revision CAS
→ 编译参数/规则 + 同步 SQLite 投影
→ 保存成功后由 Rule Engine 与 ContextAssembler 读取同一 revision
```

项目专家回复的瞬态动作链路由 Sidecar 驱动：

```text
POST /api/projects/{projectId}/chat/stream
→ chat.started / START（立即发送）
→ ExpertRuntime 后台任务
→ 服务端进度回调 → 请求内异步队列
→ chat.progress / PROGRESS（固定动作、状态与中文标签）
→ chat.completed | chat.error | chat.canceled
→ 桌面清理瞬态动作状态
```

该队列只桥接一次 HTTP/SSE 请求中的真实 Runtime 阶段；它不是第二套任务系统，也不写入聊天历史。

结构工程师 CAD 使用同一边界内的专用链路：

```text
structure_engineer CAD intent
→ CAD-first routing (including solution/proposal stages)
→ classify target: component mount / box / explicit target clarification
→ component mount: exactly one server-owned trusted profile
→ box only: loose/fixed + inner dimensions; fixed may select profiles
→ normalized cadDraft
→ Sidecar 权限与精确机械档案解析
→ CadJobCoordinator / 持久 CadJob
→ 受限 CadQuery Worker（stdin JSON、受控 staging cwd）
→ 11 个固定输出
→ ArtifactVersion + artifact_files
→ 右侧产物 MODEL_3D 浮窗 / 中央确认卡
```

## 3. 仓库模块

### 桌面端

- `apps/desktop/src`：React 交互、三栏工作台、结构化对话卡片和浮窗。
- `AuthGate` 在任何项目 Hook 或 `AppShell` 之前处理首次注册、登录、持久会话恢复与退出；认证成功前不挂载工作台。
- `HardwareSkillEditor` 通过现有 `FloatingWindow` 编辑目录化硬件 Skill；`AgentPackageEditor` 用相同文件树/Monaco 体验编辑三师行为包。设置与项目工具只提供入口，未保存草稿由桌面浮窗状态持有，不进入 Sidecar 上下文。
- `apps/desktop/src-tauri`：Tauri/Rust 宿主和本地进程边界。

### 共享契约

- `packages/contracts`：TypeScript 枚举、API 类型和事件数据结构，包括 `StreamChunkType.PROGRESS`、`ChatProgressAction`、`ChatProgressStatus` 和 `ChatProgress`。
- 状态值先在共享契约定义，UI 不重复创建字符串枚举。

### 本地 API

- `zhangwen/auth`：独立认证 schema、密码派生、会话签发/撤销、认证路由与覆盖全部业务 API 的 ASGI 门禁。
- `zhangwen/projects`：Project、Conversation、SharedFact、Decision、PendingItem、Task 和 schema v25 持久化。v24 新增 `cad_jobs`、`artifact_files`、`mechanical_profile_versions`、`hardware_mechanical_links` 并重建 `cad_runs/cad_files`；v25 新增私有 `skill_run_authorizations`，把一次本地执行确认绑定到唯一 PendingItem、SkillRun 和 Project。
- `zhangwen/experts`：EntryRouter、ContextAssembler 和三师 Runtime。ExpertRuntime 在真实进入上下文组装、云端请求、输出校验、项目更新和草稿保存边界时调用本地进度回调。
- `zhangwen/coordinator`：状态协调、Handoff、待办和过期传播。
- `zhangwen/llm`：Provider 协议、OpenAI 兼容 Gateway、按服务商隔离的安全配置读取和结构化输出校验。
- `zhangwen/skills`：Skill Registry、Model Router、SkillRuntime 和受控 ToolRunner。等待授权与真实执行严格分离；只有 ToolRunner 的运行记录已持久化为 `RUNNING` 后才允许上报本地工具执行。
- `zhangwen/artifacts`：Artifact/版本/依赖/预览，以及带 SHA-256、大小、MIME 和 capability 门禁的不可变二进制文件目录。
- `zhangwen/hardware`：Hardware Skill compiler/repository、声明式电气/IO Rule Engine、草稿创建 API、SQLite 兼容投影和机械档案 API。每包位于 `<data_dir>/hardware-skills/<skill-name>`，采用 `manifest.json + README/SKILL + assets + references + models + examples + tests`；旧八文件包继续兼容，结构能力必须成对声明 `references/mechanical.md + models/cadquery.py`。保存以整体 revision compare-and-swap 原子替换，并在同一数据库事务更新电气投影和精确机械档案关联。机械档案列表 API 只读当前快照且不调用模型；显式预览 API 提取 `mechanical.md` 唯一自然描述章节并计算 SHA-256，命中缓存直接返回，未命中则由结构化 LLM 编译有界声明式基本体，经 Pydantic 验证后用 revision CAS 回写同一 Skill。客户端只绘制返回快照。图片只承载经校验的展示资源；CadQuery 文件以 SHA-256 绑定、语法检查和 `REFERENCE_ONLY` 策略进入审计/上下文，不能被普通保存或预览直接执行。
- 项目创建页只在用户显式点击“分析并推荐”时调用 EntryRouter；新桌面 suggest 不携带预选硬件。分析成功后才显示 ACTIVE 项目硬件选择，只有创意变化会丢弃旧 `routerResult`。Sidecar 在 create 和项目内 update 时校验 Hardware Skill/Rule Engine；未知、归档或 FAIL 返回 `PROJECT_VALIDATION_FAILED`，WARNING 以 `selectedHardwareWarnings` 中文显示。
- `project_experts` 是按项目的成员关系；运行中增补工程师复用现有 add/restore 事务，为该项目创建或恢复独立 ConversationThread、私有草稿和私有记忆，不复制其他工程师聊天。
- Hardware Skill 当前 revision 是组件电气、结构、规则和工程说明的唯一真值；`hardware_components`、`mechanical_profile_versions` 与 `hardware_mechanical_links` 是可重建投影。项目创建事务把选择与 Skill revision 写为 confirmed `preferred_hardware` SharedFact；ContextAssembler 每轮从最新 confirmed 事实和 ACTIVE Skill 精确水合。Board Skill 只提供板级 MicroPython API/模板，机械档案由 Skill 编译，二者都不得复制为第二套器件事实。
- 智能工程师生成代码时，项目已选 Hardware Skill 获得优先 Markdown 预算并携带 `skillName/skillRevision` 进入 Provider 上下文；本地 ACTIVE 候选只使用紧凑预算。普通方案可把不完整机械资料标为后续核实，但 `codeDraft` 必须显式引用当前可信 Hardware Skill，否则在本地保存前进入结构化修复；板载调用仍由 Board API 机器契约和静态/语法 Worker 最终校验。
- K10 Board Skill 对当前需求执行多参考与最多两个模板的有界检索，并生成 `generationContract`（模板路径、关键导入/调用锚点、未验证能力）。所选参考代码以独立系统消息紧邻 Board API 契约发送；智能工程师 `codeDraft` 在 CodeRun 保存前通过 AST 核对模板骨架，缺失锚点或伪造未验证能力成功会进入既有结构化修复。该门禁不做逐行相似度比较，允许在参考骨架上增加业务状态机和界面逻辑。
- 电气模型把器件的连续工作范围、推荐工作点、主控可提供的离散外设电源轨和信号电平分开保存。Rule Engine 先选择范围内且最接近推荐点的电源轨，再独立校验逻辑/模拟信号电平；不得用开发板输入电压替代外设电源轨，也不得因供电通过而跳过 3.3V GPIO/ADC 安全检查。
- 正式默认目录只生成行空板 K10。历史占位 seed 由明确 ID 白名单从活动投影清除；已有 `MIGRATED/BUNDLED` 目录可逆移动到 `<data_dir>/retired-hardware-seeds`，用户创建包、项目事实和备份不参与清理。可复制模板位于源码 `zhangwen/hardware/hardware-skill-template`，与正式包使用同一目录形状。

Hardware Skill 创建链路：

```text
上传 Markdown/TXT/JSON/CSV/PDF 或创建器内对话补充
→ Sidecar 本地类型/大小/隐私检查与文本提取（PDF 使用 pypdf，扫描件不做 OCR）
→ 可选云端结构化候选（不可信数据）
→ <data_dir>/.hardware-skill-drafts DRAFT 会话状态 + 文件树预览 + 缺失问题 + diagnostics
→ HardwareSkillCompiler + validation cases
→ 用户明确确认
→ 首次创建正式 Skill 目录并原子发布 ACTIVE + SQLite 投影 reconciliation
```
- `zhangwen/cad_agent`：项目级 CAD intake、`cadDraft` 边界、精确机械档案快照、自动尺寸、CadJob 仓储/协调、Worker 客户端、Artifact 发布和确认状态。intake 复用现有 clarification 表和 SharedFact，不增加 schema；澄清答案、answered 状态和 CAD SharedFact 同事务写入。服务端把 confirmed fact ID/值固化为 `intakeSnapshotSha256`，明确修订会封存旧非活动候选及其聊天/Artifact 投影；项目虚拟硬件 ID 只代表用户显式选择的精确 profile revision/SHA。
- `zhangwen/cad_engine`：只接受服务端固化 `CadBuildSpec` 和由 Hardware Skill 编译的机械档案快照；负责确定性布局、开孔、安装结构、受控自由零件 CSG、几何校验和 STEP/STL/GLB/JSON/manifest 导出，不加载 LLM 或普通用户编辑的 `models/cadquery.py`。
- `zhangwen/specs`、`code_agent`、`lesson_agent`：其他 Provider 内容设计与本地验证/持久化边界。
- `code_agent.board_api_contracts` 根据项目已选组件或已确认 Spec BOM 解析板型。掌控板 3.0 与行空板 K10 使用各自机器可读契约；K10 契约支持 `unihiker_k10/k10_base` 多模块导出和构造实例别名。契约只参与 Prompt 与受限 AST 检查，不导入开发板模块或执行用户代码。
- 问题引导师在当前方案卡上持久化 `delivery_track=project|lesson` confirmed SharedFact，Workspace 将其投影为 `sharedContext.deliveryTrack`。当前前台流程以已确认 Proposal 为实施基线，不再自动创建或等待 Spec；项目已有智能工程师时由 `proposal_action.handoff` 触发一次现有专家会话。Spec、Code Agent 和 Lesson Agent 底层模块继续保留为显式兼容能力，不增加平行对话、一级 Tab 或教学数据库。
- `zhangwen/devices`：Mock 设备、Dry Run、串口发现和设备安全边界。
- 日常 MicroPython 上传由 `zhangwen/devices` 在端口锁内先执行有界 Ctrl-C 安全接管，再以 `mpremote resume` 完成备份、写入和回读，最后只重置 MicroPython 解释器并显式启动 `main.py`。安全接管失败不会升级为硬件复位、断电、Flash 擦除或固件烧录；旧 `RESTART` 记录只用于兼容读取。

## 4. LLM 边界

1. Windows Credential Store 保存 API Key，SQLite 和配置文件不保存明文 Key。
2. Provider 凭据保存、携 Key 测试和清除要求有效桌面 capability。开发态 Tauri 的 Vite 本地 Origin 不能覆盖有效 capability；普通 Web、伪造或缺失 capability 继续失败关闭。
3. `llm.runtime.require_llm_config()` 是生产对话配置和凭据读取的共享边界。连接测试可显式使用未保存表单，但不得改变运行时配置；只有保存成功后的配置和安全凭据才能被后续对话读取。
4. `llm.structured.complete_structured()` 执行 JSON 提取、Pydantic 校验和最多一次修复重试。
5. 缺 Key 返回 `CONFIG_MISSING`；两次 Provider JSON/Schema 无效返回 `LLM_OUTPUT_INVALID`；结构有效但
   两次未通过本地工程或安全约束返回 `LOCAL_OUTPUT_REJECTED`。失败运行只记录不含 Provider 原始输出的
   字段级脱敏诊断，前端只收到与失败来源匹配的稳定通用错误。
6. `FREEFORM_STRUCTURE` 不再要求 Provider 填充整个 `ExpertRuntimeOutput`；专用 `FreeformGeometryCompiler`
   只请求受控 `DeclarativeGeometry`，最多一次修复，然后由本地封装 CAD 草稿并继续经过 intake、几何和
   Worker 边界。其他三师输出仍使用公共契约，不能把这一专用路径扩大成本地内容 fallback。
7. 只有通过 Schema 和本地安全校验的输出可以持久化为业务版本。
8. ExpertRuntime 的三师公共输出契约要求缺少用户输入时返回 1-6 个类型化 `clarification` 问题；
   `questions` 是 Provider 权威字段，兼容字段 `question` 由 Sidecar 从首题规范化。Provider 生成的
   `missing_input` 或 `confirmation` PendingItem 会触发一次修复重试，并在写库前再次拒绝。执行授权
   只能来自本地 SkillRuntime。

## 5. 对话动作进度边界

1. `chat.progress` 是 Sidecar 拥有的事实事件。Provider、`reasoningContent`、模型正文和桌面计时均不能创建动作；中文 `label` 必须由 `action + status` 的服务端固定白名单生成。
2. `ChatProgress` 只包含稳定步骤 `id`、固定 `action`、白名单 `label`、固定 `status` 和流内 `sequence`。普通模式只呈现中文标签与状态语义，不显示 action/id/sequence、Skill/Tool 标识、命令、路径、端口、payload、内部请求 ID、原始错误或硬件标识。
3. ExpertRuntime 通过回调发出真实阶段，项目聊天路由用请求内异步队列在 Runtime 尚未结束时持续转为 SSE；不得先等待完整结果再伪造一批“进行中”事件。
4. SkillRuntime 的 `AWAITING_CONFIRMATION` 只产生“等待本地执行授权”；ToolRunner 真实 `tool_run` 落为 `RUNNING` 后才能产生“正在执行本地工具”。失败标签保持白名单化，原始异常仍走受控错误与日志边界。
5. 本地执行确认通过 v25 `skill_run_authorizations` 绑定原 PendingItem、唯一 SkillRun、Project 和原对话消息。桌面 capability 通过后原子领取；已绑定授权不能走旧 REST resolve，历史无关联事项不能执行，重复确认不能启动第二次工具运行。
6. 进度不持久化到 Message、Artifact、PendingItem、Project Task 或授权表。终止、失败和取消会关闭 Runtime 任务、清理当前动作并刷新授权事项；旧服务端或无进度路径继续使用三点生成状态。
7. CadJob/CAD Worker 和设备 Operation 是独立的持久异步流程，继续由右侧“工作 / 设备”和浮窗显示；它们不能冒充当前专家聊天动作。该链路不改变单一 `CenterChat` 或固定“工作 / 产物 / 设备”三 Tab。

## 5.1 桌面交互一致性边界

1. `useChatStream` 与 `CenterChat` 为每次生成持有不可变的 Project/Conversation/Request 作用域；专家胶囊只更新下一条消息的目标。项目切换和退出先 abort reader、调用 cancel 并等待流任务收敛，迟到事件不能跨项目落 UI。
2. `CenterChat` 向 `AppShell` 暴露草稿刷新控制，项目切换、新建和退出先完成持久化；失败进入显式放弃确认。草稿状态由项目 Hook 统一为未保存、保存中、已保存和保存失败。
3. `AppShell` 为当前项目创建单一工程状态快照，中央确认与右侧工作共同订阅计划、Spec、代码、CAD 和教案。404 表示该领域尚无状态，其他错误保留最后有效快照并提供重试。
4. PendingItem 的本地授权语义只由 v25 关联派生的 `kind/actionType/authorizationId` 决定。设备页不读取聊天专家作为权限；新建项目选择器在确认硬件时调用 Rule Engine，最终创建仍由服务端再次校验。
5. 普通失败消息保留在中央时间线并渲染受控恢复卡。恢复是绑定原 Project/Conversation/Expert/User Message
   的新 turn，不能复活终止流；修改动作只恢复项目草稿。启动时遗留 `STREAMING` 统一变为
   `GENERATION_INTERRUPTED`，因此服务重启后仍有“继续生成 / 修改原需求”入口。

## 6. 本地安全边界

- 除健康检查、认证状态、注册和登录外，所有 `/api` 业务入口都要求有效 Bearer 会话；桌面遮罩不是唯一安全边界。
- 密码、密码盐/派生值、原始会话 token 和认证库内容不得进入项目、项目包、聊天、日志或 Provider 上下文；服务端只持久化 token 摘要。
- 硬件兼容、IO 引用和 BOM 由本地 Rule Engine 确定。
- 代码仅能产生固定虚拟路径，持久化前执行凭据、Shell 能力和 Python AST 检查。未提供 Wi-Fi 配置时只允许显式非秘密占位符；普通字符串/容器同名方法不按主机文件调用误杀，直接危险调用及解析到 `os`/`uos` 的删除、重命名、替换和系统命令继续拒绝。
- CAD 仅允许 `BOX_WITH_LID -> box-with-lid.v1`、单器件 `COMPONENT_MOUNT -> component-mount.v1`、无器件 `FREEFORM_STRUCTURE -> freeform-structure.v1`、固定 `UNIHIKER_K10_PHOTO_ALBUM -> unihiker-k10-photo-album.v1` 和受信机械档案；当前不是通用 CAD。安装座类和自然语言自由零件请求不再进入盒体 intake，目标不明确时先确认目标。模板、声明式几何范围、自动尺寸、布局、孔位、几何验证和文件发布由本地边界保持权威。
- CAD 输入状态机由 Sidecar 保持权威：`COMPONENT_MOUNT` 必须单选一个受信机械档案且不收集盒体尺寸；`BOX_WITH_LID` 缺模式/内腔尺寸时返回中央结构化澄清；`FREEFORM_STRUCTURE` 收集自然语言结构描述，必须 `components=[]` 且不提供机械档案；`UNIHIKER_K10_PHOTO_ALBUM` 直接采用固定 16 阶段结构，不收集参数、器件或 Provider 几何；不再把 PendingItem 的“确认处理”当作输入答案。
- 结构工程师的 CAD 轮次在 solution/proposal 阶段也优先进入 ExpertRuntime；当前文本、来源 `cad_*` 卡或最近 CAD 语境与继续/修订表达构成延续依据。普通结构咨询不因历史 CAD 卡被永久锁入建模门禁。
- ProjectExpert 持久身份是 Runtime 权威，调用方 `expertType` 不能把其他专家提升成结构工程师；非 CAD 轮次中的 Provider `cadDraft`/`cad_*` payload 失败关闭。
- Provider 仍负责结构对话回复；用户确认的 target、mode、内腔尺寸、档案、自由零件描述或 K10 相册目标是本地规范化 `BOX_WITH_LID`、`COMPONENT_MOUNT`、`FREEFORM_STRUCTURE` 或 `UNIHIKER_K10_PHOTO_ALBUM cadDraft` 的权威输入。自由结构只允许最多 32 个有界 `box/rounded_box/cylinder` 的顺序 `add/cut`，第一项必须 add、最终必须单连通；K10 相册的尺寸和几何完全由本地模板拥有。完整 intake 时本地规范化是受限 CAD 编排，不是通用内容 fallback。
- Run/Job 固化的 intake 指纹是创建、重试、Worker 最终化和确认的本地授权依据。新 intake 同事务 stale 旧的 `DRAFT/VALIDATED/READY_FOR_REVIEW/FAILED/CANCELED/REJECTED`，保留 `QUEUED/RUNNING/APPROVED`；活动 Worker 的旧快照结果会被丢弃。入口失配统一为 HTTP 409 `CAD_INTAKE_REVISED`，幂等键不能绕过。
- CAD Worker 不读取项目 SQLite，不接收 capability token、API Key、调用方路径或任意代码；Sidecar 只通过 stdin 传入不可变构建规范，并从受控 staging 目录原子发布模板拥有的精确文件集（盒体/器件 11 个，自由结构与 K10 相册单零件 9 个）。
- CAD 执行/取消/重试/确认/退回与 Artifact 二进制读取要求桌面 capability。机械档案 GET/PUT/DELETE 当前没有同等后端 capability 门禁，普通/专业模式隔离由桌面 UI 控制；这不能被描述成安全权限边界。
- 串口、上传、Flash 擦除和固件烧录不得绕过 ToolRunner 和确认策略。
- 自动测试只使用 fake provider 和 Mock/Dry Run 设备。

## 7. 测试层级

- Python：pytest 覆盖仓储、迁移、状态、结构化 LLM 边界、硬件规则和设备模拟。
- TypeScript：Vitest/Testing Library 覆盖对话、布局不变量和工作/产物/设备表面。
- 契约：Contracts build/typecheck 与跨端回归。
- 桌面：Vite 生产构建和 Cargo check。
- 真实 LLM 与真实硬件是隔离的显式验收，不进入默认自动测试。
