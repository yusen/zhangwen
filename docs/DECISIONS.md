# Architecture Decision Log

## 2026-07-31 ZW-CREATOR-001 M0–M7 完成性加固

| Decision | Choice | Reason |
| --- | --- | --- |
| 持久任务 | 方案确认后的代码准备、数字原型和必要结构任务进入 `creator_jobs`，由可替换 runner 驱动正式状态机 | SSE 事件和前端定时器不能让刷新后的作品恢复真实进度，也不能证明自动生成已执行 |
| 显式动作幂等 | 仿真启动、参数保存、实物验收、交付导出/导入均使用稳定幂等键、请求 Hash 和持久响应；键换请求拒绝 | HTTP 模糊失败或刷新重试不能重复创建运行、参数修订、验收、交付或导入项目 |
| 客户端写入意图 | 未决写操作的稳定键持久化到本机；设备安装按会话、应用和动作生成语义指纹，不把一次性确认令牌写入指纹 | 刷新或重新准备确认令牌后仍需回放同一设备操作，避免响应丢失造成二次烧录 |
| 设备身份 | `ATTACHED_UNVERIFIED` 不属于 Creator 可接受连接证据；USB/ESP-Claw 均需精确板型身份完成 | 芯片相同或端口存在不能证明当前数字原型对应的受支持设备包 |
| 设备包真值 | 两个代理设备包及其 USB/ESP-Claw 连接、运行时、回读和能力由版本化注册表声明 | Creator UI 和路由不得各自拼装板型与通道能力，自研硬件可沿同一契约加入 |
| 可复现材料 | 导出前验证当前场景、代码 Artifact、参数、必要结构、仿真、连接、部署、真机与人类验收；导入恢复并重映射可复用材料 | 等级 6 只说明原作品完成，不能证明第二人获得了复现所需材料 |
| 独立身份 | 原验收、导入、副本验收和回执使用认证 subject；显示名不参与独立用户判断 | 可编辑字符串不能证明第二位用户，也不能阻止同一账户改名绕过 |
| 导入原子性 | 项目、Artifact、Creator 材料和导入记录作为带持久意图日志的可补偿操作；启动时恢复 `PREPARING`，保留 `RECOVERED` tombstone，并按幂等键与包 Hash 去重 | 进程中断或恢复失败不能留下可见孤立项目/文件，模糊重试不能复制项目或换包复用键 |
| 指标契约 | 使用 `creator-metric/v1` 判别事件和确定性事件 ID；载荷去标识化，指标不驱动生命周期 | 成功指标必须从真实业务事实稳定计算，同时不能成为第二套状态真值或泄露设备/账户信息 |
| 迁移验收 | 先把受支持旧形态规范化为 V29 基线，再对真实 V29 历史表做 V30 前后规范 Hash、重复打开和故障恢复；迁移指标按数据库记录且排除全新库 | 兼容 repair 不应被误报为 V30 数据损失，新建库和多项目库也不能扭曲历史迁移成功率 |
| 硬件测试隔离 | 注册 `hardware` marker，默认排除；真实入口要求环境开关和人工确认双门禁 | 自动回归不得意外触发串口、LAN、Flash 或执行器，真实动作留给 M8 |

## 2026-07-31 ZW-CREATOR-001 M7 证据、交付与复现

| Decision | Choice | Reason |
| --- | --- | --- |
| 最终验收 | 等级 5 后必须由明确的人类操作者接受；系统/AI 身份不能代签 | 真机行为通过不等于用户接受当前完整作品和限制 |
| 证据依赖 | 场景、代码、参数、结构修订由关系真值动态比对；变化后把适用下游证据标为 `STALE` | 避免旧仿真或真机结果继续证明已改变的作品，同时保留审计历史 |
| 交付内核 | 复用安全 Project Package 作为内层，Creator 外层只增加版本化 manifest、语义快照和指南 | 避免复制 ZIP、Artifact、隐私和项目导入边界 |
| 交付变体 | 固定 `SHARE / REPRODUCIBLE / TEMPLATE`；设备日志均排除，模板不含原证据 | 分离浏览、复现和再创作目的，减少设备与隐私信息扩散 |
| 导入等级 | 导入生成全新项目 ID 图，只恢复目标确认基线，等级重置为 1 | 他人的历史证据不能自动证明本机、本设备和当前操作者的结果 |
| 复现权威 | 不同于原验收者的第二用户，使用同一可复现包并在副本重新达到等级 6 后才记 `REPRODUCTION` | 把“包可打开”与“作品可复现”分离，并绑定不可变 Hash 与验收事实 |
| 能力成熟度 | 感知 `MVP`、响应执行 `CONTROLLED_BETA`、视觉/音频 `TECH_PREVIEW` 写入 manifest | 单个作品验收不能扩大为平台能力成熟度承诺 |
| Python 缓存 | Board Skill 清单校验只忽略 `__pycache__` 内 `.pyc`；源码 Hash、未知文件和符号链接仍严格拒绝 | 本地编译缓存不应让有效 K10 Skill 消失，也不能成为放宽包边界的入口 |

## 2026-07-30 ZW-DEVICE-LAB-001 双板项目实物仿真与代码部署

| Decision | Choice | Reason |
| --- | --- | --- |
| 主控范围 | 规范 ID 只允许 `dfrobot/dfrobot_k10` 与 `seeedstudio/xiao_esp32s3_sense`；旧 K10 ID 只作读取兼容 | 防止目录、推荐、串口和仿真各自维护不一致的板型集合 |
| 外围器件 | 传感器、执行器和供电器件不受双板主控限制，第三种 MCU 失败关闭 | 保留创客扩展能力，同时落实“只做两款硬件”的主控语义 |
| 仿真来源 | 立项确认后由已确认硬件、BOM、IO Map 和立项内容自动投影不可变实物场景；API 不接受手工板型覆盖 | 仿真必须代表当前项目，而不是另一套固定板卡演示 |
| ESP-Claw 语义 | 与 USB 串口同为 `UPLOAD_CODE` 通道，消费显式 ESP-Claw Lua CodeRun；运行时安装只用于初始化/恢复 | 避免把日常代码上传误建模成固件烧录 |
| ESP-Claw 信任 | 首版在专业模式采用 `TRUSTED_LAN_MANUAL`：Web/MCP 必须是同主机的私网或 `.local` 地址，用户三重确认后再做只读能力/板型握手；不宣称自动发现或设备认证 | 与上游双端点 LAN 控制面兼容，同时明确人工信任边界；板型/runtime/能力/回读任一不满足时零写入 |
| ESP-Claw 代码校验 | 本地只承诺受控路径、危险调用和 Lua block/括号的静态结构校验；设备运行结果仍是表达式级正确性的边界 | 不引入未固定的 Lua 工具链，也不把启发式检查冒充完整 parser |
| ESP-Claw 本机隐私 | 普通模式不挂载手动配对表单；项目包扫描阻止私网/`.local` URL、合成 session 和 port 标识 | 双地址只属于本机专业维护注册表，不能借设备日志或项目包外泄 |
| ESP-Claw managed job | 名称只按项目稳定生成；未知/孤儿状态失败关闭；正常退出有界等待 stop 与回滚，回滚还要逐文件回读 | 地址别名不能在同一设备留下两份脚本，HTTP 成功也不能冒充远端已停止或文件已恢复 |
| 应用维护 | 仅接受预构建、严格 manifest、固定 Hash 的双板包；逐段备份/写入/验证，不提供全擦除 | 保护 NVS/用户数据，并与日常部署状态机隔离 |
| Wokwi Elements | 仅负责显示和交互，本地引擎负责状态 | 上游组件不是硬件仿真器，不能把 UI 冒充固件或电气仿真 |
| QEMU | 运行器支持固定 Hash 的可选离线组件；当前仓库未随包分发，因此明确显示不可用并回退功能模型 | 避免在缺少二进制、许可证和兼容镜像时虚假声明固件级仿真 |
| 真机图形调参 | 参数版本与 staged 文件同步已实现；任意固件的实时 `zwdbg/1` 会话仍需显式握手，未实现时失败关闭 | 不把清单声明或文件写入等同于运行时协议能力 |
| 中央工作区 | 项目实物仿真可占用中央可见区，但 `CenterChat` 保持挂载隐藏，右 Tab 不变 | 满足用户授权的新工作区，同时保持对话状态不丢失 |

## 2026-07-28 ZW-AUTH-002 云认证未配置时的账号恢复

1. `CLOUD_AUTH_NOT_CONFIGURED` 是部署能力缺失，不是密码错误。存在活动
   `auth_kind=local` 账号时，桌面直接恢复既有本机登录入口；配置了云认证时继续以邮箱流程为正式入口。
2. 旧本机密码只保存派生值，不能查看或还原。恢复使用本机交互工具，不新增匿名 HTTP 重置端点，也不把临时密码写进聊天、命令参数或日志。
3. 重置前必须备份认证 SQLite；成功后撤销该账号全部旧会话。账号 ID、项目 owner 和项目数据不改变，云账号与设备/CAD 安全门禁不放宽。
4. 认证状态响应明确区分“任意账号存在”“活动本机账号存在”和“云认证已配置”。失效会话的恢复分支也必须保留这些能力，避免再次路由到不可用入口。

## 2026-07-28 ZW-UX-009 M7 对话流体化决策

| Date | Decision | Choice | Reason |
| --- | --- | --- | --- |
| 2026-07-28 | 普通模式主界面 | 默认“对话即首页”，左侧只保留对话、项目、连接、设置，右栏默认收起；工程工作区移入专业模式 | 普通用户不需要理解工程阶段与内部组织，先保证一句话即可开始 |
| 2026-07-28 | 澄清呈现 | 新响应最多一个阻塞问题，作为普通掌问消息由主输入框回答；历史多问题本地逐个收集后一次批量提交 | 去除问卷感，同时保持既有事务、SQLite 与历史数据兼容 |
| 2026-07-28 | 主动推进 | 可逆低风险细节采用推荐默认值，非阻塞缺口记为验证项，只询问改变方向的最高影响问题 | 让系统承担选择成本，不让用户替机器填表 |
| 2026-07-28 | 结果与反馈 | 普通模式只显示一个当前状态；结果卡只保留标题、两行摘要和一个主动作 | 让反馈指向下一步，而不是暴露 Agent、Job 和路由过程 |
| 2026-07-28 | 窄屏检查器 | `[hidden]` 必须强制 `display:none`，进入 `<=860px` 时自动收起已打开检查器 | 真实 744px 桌面复核发现作者样式覆盖原生 hidden，导致侧栏挤占主对话 |
| 2026-07-28 | 安全例外 | 串口扫描、连接、上传、复位、Flash 和固件烧录不适用主动默认值，继续明确确认 | 默认主动推进不能扩大本地设备权限或不可逆副作用 |

## 2026-07-26 ZW-V2-001 M0-M5 架构决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-26 | V2 产品入口 | 以项目的概览/工程/结构/交付工作区为主入口，同一 AI 面板携带页面上下文；三师保持责任域而非三个割裂聊天入口 | 保留自由表达，同时让真实 BOM、代码、3D、设备和交付结果成为主界面 |
| 2026-07-26 | 工程状态真值 | 现有关系表继续是事实源，Project State 只做确定性投影；正式修改走 Change Set、确认、事务提交和版本 | 避免聊天历史、页面局部状态或第二套巨大 JSON 与项目事实竞争 |
| 2026-07-26 | V1 导入基线 | 有既有工程事实且无 V2 版本时，在首次 V2 读取边界幂等建立 `version=1`、无 Change Set 的只读基线；空项目继续 V0 | 让 V2 版本轴与 V1 真实进度联动，同时不批量改写用户业务数据或制造第二套真值 |
| 2026-07-26 | 事实呈现 | Project State 保留机器值，同时派生 `label/displayValue`；展示文案排除在 projection hash 外 | 普通用户需要看到问题与答案，而不是 `q_1`/JSON；派生文案又不能改变工程版本语义 |
| 2026-07-26 | V2 对话兼容 | 保留单一 V1 聊天历史与 Runtime，在请求层增加 allowlist 页面上下文和默认主责路由；完整对话 Change Set 化另立迁移 | 先让切页真正影响协作焦点且不丢历史，同时不假装现有直接领域写入已经满足 V2 版本事务 |
| 2026-07-26 | CAD 融合 | 冻结 `ZW-CAD-intent` 的 149 文件来源快照和 hash，把可复用逻辑改造成无 HTTP 的 JSONL Worker；宿主拥有项目、凭据、能力和 Artifact | 吸收已验证 3D 工作流，又不把外部账号、模型源、数据库和旧 UI 并入产品 |
| 2026-07-26 | 设备附加与接管 | connect 不执行 identity；写入前或显式 takeover 才按 Ctrl-C → prompt → identity 接管，并由数据库保证单物理端口单 Runner 租约 | 旧程序繁忙时仍能先建立会话，且避免两个会话同时写同一串口 |
| 2026-07-26 | 硬件复位 | 只有合作式接管失败且用户输入精确短语后才能 reset；随后必须重枚举和启动窗口 break-in | reset 会改变设备运行态，不能由连接或自动重试隐式触发 |
| 2026-07-26 | Web 本地能力 | Web 通过 loopback Bridge 的桌面挑战、Origin allowlist、十分钟项目 lease 和一次性写 request id 使用 CAD/串口/上传 | 浏览器沙箱不能直接获得 Tauri/本机权限，短期最小授权可审计且可撤销 |
| 2026-07-26 | 验收声明 | M0-M5 的自动测试只证明软件与模拟边界；真实 CadQuery、Provider、实体设备、安装包和发布统一留在 M6/外部验收 | 不用缺失环境或模拟结果伪造真实工程闭环 |

## 2026-07-17 ZW-HW-004 外设电源轨校验决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-17 | 电气字段语义 | `voltage` 表示推荐点，`voltageMin/voltageMax` 表示连续允许范围，`supplyVoltages` 表示 MCU/POWER 实际暴露的离散外设电源轨 | 开发板输入电压、外设供电能力和器件工作范围不是同一事实，压成一个标量会误报不兼容 |
| 2026-07-17 | 供电匹配 | 在器件允许范围内选择最接近推荐点的真实电源轨；推荐点附近 PASS，范围内其他轨 WARNING，无可用轨 FAIL | 既允许 3–5V 器件使用 K10 的 3.3V/5V 轨，又保留推荐接法与风险提示 |
| 2026-07-17 | 信号安全 | `logicLevel`/ADC 信号电平继续独立校验，不能被供电通过短路 | 5V 供电可用不等于 5V 输出可直接进入 3.3V GPIO/ADC |
| 2026-07-17 | 兼容迁移 | 未声明新字段的旧 Skill 把工作范围和供电源均退化到原 `voltage` 单点 | 保持已有 Hardware Skill 的保守行为，不静默扩大允许范围 |

## 2026-07-17 ZW-LLM-004 生成失败恢复决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-17 | 自由结构输出范围 | `FREEFORM_STRUCTURE` 使用只含有界声明式 primitives 的专用 Schema，本地再封装通用专家/CAD 输出 | 真实失败中多数来自大 Schema 漏填 geometry；缩小生成职责能减少格式失败但不绕过真实 Provider 或本地验证 |
| 2026-07-17 | 错误分类 | Provider Schema、本地工程边界和启动中断分别使用 `LLM_OUTPUT_INVALID`、`LOCAL_OUTPUT_REJECTED`、`GENERATION_INTERRUPTED` | 三类原因和解决办法不同，统一“请重试”无法指导用户继续 |
| 2026-07-17 | 恢复事务 | 重试创建绑定原消息、原专家和原 conversation 的新 turn；不复活旧流，不重放结构化澄清事务 | 已终止流和已落库答案不能安全重复领取，但用户原需求与已确认上下文应继续复用 |
| 2026-07-17 | 中央交互 | 后端返回白名单 `userActions`，中央失败卡提供原因、建议和按钮；修改只回填草稿 | 后端原有动作没有被 UI 消费是对话卡住的直接原因，恢复不能形成第二套聊天界面 |

## 2026-07-16 ZW-AGENT-006 项目交互可靠性决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-16 | Streaming request ownership | 每个生成固定绑定 Project/Conversation/Request；专家切换只影响下一条，项目切换/退出先取消并等待流收敛 | 避免旧请求继续计费、迟到 chunk 写错项目或被可变专家引用丢弃 |
| 2026-07-16 | PendingItem authorization semantics | 从既有 v25 授权关联派生 `kind/actionType/authorizationId`，前端只按类型字段进入中央本地授权流 | 中文标题和原因是展示文案，不能承担安全授权类型识别 |
| 2026-07-16 | Draft durability | 草稿提供四态和重试；切换、新建、退出前刷新，失败需用户明确放弃 | 保存失败不能继续显示“已保存”或静默丢失输入 |
| 2026-07-16 | Engineering state projection | 中央确认与右侧工作共享单一快照，非 404 读取错误保留旧值并显式重试 | 消除重复请求造成的短暂不一致和“失败等于无待办”误判 |
| 2026-07-16 | Device and hardware gates | 设备权限与聊天专家解耦；选择硬件时即时本地校验，创建时再次服务端校验 | 专家路由不是权限模型，用户应在提交创建前看到真实当前选择的 WARNING/FAIL |

## 2026-07-15 ZW-AUTH-001 本机账号与访问门禁决策

1. 当前没有远程身份、邮件、短信或多租户基础，因此实现设备本地账号，不伪造云账号、找回密码或跨设备同步。
2. 前端 `AuthGate` 只负责进入体验；Sidecar 的 ASGI 中间件对全部业务 `/api` 强制 Bearer 验证，防止绕过界面直接调用。
3. 认证数据使用独立 schema v1，不提高项目数据库 v25，也不把账号私密字段写入项目包。密码以随机盐
   PBKDF2-HMAC-SHA256（600,000 次）派生；会话 token 仅在签发时返回，数据库只保存 SHA-256 摘要。
4. 会话默认 30 天，退出在服务端撤销；任意业务 401 会清除桌面本地 token 并卸载工作台。
5. 当前账号不拥有或隔离项目；多账号共享这台设备现有项目库。若要云端身份或账号级项目归属，必须另立
   身份服务、数据迁移和授权模型，不能从本门禁实现中推断。

## 2026-07-14 真实动作进度决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-14 | Progress event authority | 新增服务端拥有的 `PROGRESS / chat.progress`；`ChatProgress` 固定为 `id/action/label/status/sequence`，中文 `label` 只能由 Sidecar 白名单生成 | 模型推理、正文和客户端等待时长都不能证明本地动作真实发生 |
| 2026-07-14 | Runtime stream bridge | 项目聊天在进入 ExpertRuntime 前发送 `START`，Runtime 作为后台任务运行，并通过请求内异步队列实时转发回调事件 | 先等待 Runtime 完成再发送步骤无法表达真实时序，也会把事后描述误当进行中状态 |
| 2026-07-14 | Tool execution truth | `AWAITING_CONFIRMATION` 只显示“等待本地执行授权”；只有 ToolRunner 已持久化 `RUNNING` 记录后才显示“正在执行本地工具” | 授权等待不是执行，持久运行记录是可审计的最小事实边界 |
| 2026-07-14 | Resumable authorization identity | schema v25 新增私有 `skill_run_authorizations`，以 PendingItem 和 SkillRun 双唯一关系绑定 Project 与原对话消息；桌面 capability 通过后原子领取，旧事项和缺消息关联的运行不得执行 | 单靠 PendingItem 标题或前端状态无法证明用户授权的是哪一次本地运行，也不能安全防止重复确认 |
| 2026-07-14 | Ordinary-mode disclosure | 普通模式只显示白名单中文动作与状态；隐藏 action/id/sequence、Skill/Tool、命令、路径、端口、payload、原始错误、内部请求 ID、模型推理和硬件标识 | 让用户看见真实进度，同时保持普通模式和本地安全边界 |
| 2026-07-14 | Progress lifetime and fallback | 进度只存在于当前请求，不写历史消息；终态清理运行状态，旧服务端保留三点生成回退；CadJob/CAD Worker 和设备 Operation 继续使用各自界面 | 避免历史回放伪造已结束动作，也避免把独立异步系统重复投影成聊天动作 |

## 2026-07-14 云端 LLM 产品表达决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-14 | Product LLM presentation | 产品界面统一使用“云端 LLM”，不把 `standard`、`fake`、`paid` 映射为免费/付费产品模式；顶栏只显示本地服务健康，LLM 连通性只在设置中检查 | 避免把内部 QA 配置误解为产品能力、连接状态或计费方案 |
| 2026-07-14 | Internal provider modes | 保留 `dev:web:fake`、`dev:web:paid`、`llmTestMode` 和 `usesPaidLlm` 作为隔离测试与只读诊断边界，但不进入用户可见文案 | 保持自动测试确定性并避免测试误调用真实云端模型；本决策覆盖 2026-07-11 的 persistent UI cost labels 表达 |

## 2026-07-12 本地设备连接恢复决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-12 | 唯一完整启动入口 | `start-local.bat` 与同义命令 `pnpm start` 统一启动 contracts、FastAPI Sidecar、Vite 和 Tauri；不保留 `start:hardware` 或其他完整应用别名 | 防止分拆启动引入旧 Sidecar 与桌面 token 不一致 |
| 2026-07-12 | 桌面会话与设备探测 | 启动器持有跨进程单实例锁，启动前校验 Sidecar 与 Tauri 的同一 capability token；设备连接只执行最小只读 MicroPython 身份探测 | 消除旧窗口会话漂移，并避免导入板载库造成 ESP32 重启 |
| 2026-07-12 | Write confirmation | Require `UPLOAD` or `-ConfirmUpload` before Device Service receives `confirmWrite=true` | Keeps an explicit overwrite boundary for the independently invoked hardware task |
| 2026-07-12 | Target selection | Auto-select only one identity-verified K10; reject zero or multiple matches and revalidate identity on final connect | USB metadata and port order alone cannot prevent deployment to the wrong device |
| 2026-07-12 | Firmware boundary | Exclude erase and firmware flashing from the full-hardware start task | Ordinary MicroPython upload must remain separate from high-risk firmware operations |

## 2026-07-11 Project-scoped Conversation Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-11 | Project creation entry | Put new-project creation and the project list in the left sidebar; keep the form as an overlay | Matches frequent project navigation while preserving the permanent central conversation |
| 2026-07-11 | Visible conversation model | Render one project timeline and one project draft; aggregate persisted expert conversations and label every assistant reply | Users collaborate on one project instead of switching visible chat windows |
| 2026-07-11 | Expert routing | Show participating experts as pills above the composer and support `@智能体` for the next reply | Makes the required experts visible and routing explicit without exposing agent internals |
| 2026-07-11 | Provider isolation | Retain one `conversationId` and private memory per expert; send only that expert's latest 12 completed messages plus shared project context | Satisfies independent cloud conversations without losing project-wide facts and artifacts |
| 2026-07-11 | Editable expert skills | Register every Skill declared by the three expert configs and persist built-in description overrides beside SQLite without a schema migration | Gives users one discoverable edit surface while keeping v22 and existing data compatible |
| 2026-07-11 | Shared hardware knowledge | Let all three experts retrieve the same bounded editable hardware library content | Hardware dimensions, compatibility and safety facts must not diverge between experts |
| 2026-07-11 | Free Web interaction validation | Add an explicit `dev:web:fake` launcher using isolated `.data/web-fake`; keep real DeepSeek as the default and never auto-fallback | Allows real browser sends and conversation routing checks without cost, credentials or user-data mutation |
| 2026-07-11 | Paid Web interaction validation | Add explicit `dev:web:paid` with real DeepSeek, isolated `.data/web-paid`, backend-only credentials and persistent UI cost labels | Lets paid-model behavior be tested deliberately without confusing it with fake tests or formal project data |

## 2026-07-10 ZW-WEB-001 Web-first Development Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-10 | Historical ZW-WEB-001 development host | Use Web Development Mode (FastAPI + Vite Browser Host) as the stabilization-stage development and core-flow verification entry; the current default now starts the complete Tauri local application | Reduced Tauri packaging, native permissions and device concerns while the three-teacher product flow was being stabilized |
| 2026-07-10 | Final host | Retain Tauri as the final local desktop host; Browser and Tauri use the same React app, API Client, FastAPI, SQLite and domain layer | The hosts are two adapters for one product, not parallel products |
| 2026-07-10 | Platform differences | Centralize host detection and PlatformCapabilities; gate unsupported buttons and reject Web local-execution calls in FastAPI | Prevents scattered `isWeb` branches and makes unsupported behavior explicit rather than silently successful |
| 2026-07-10 | Web Provider credential | Browser UI cannot read, submit, clear or persist Provider Key; FastAPI may read `ZHANGWEN_DEEPSEEK_API_KEY` or existing secure backend credentials | Keeps DeepSeek secrets out of React, Vite, LocalStorage, request logs and Git |
| 2026-07-10 | Web limitation | Web mode does not claim real file-system, Shell, serial, Flash, local CAD or device completion | These local capabilities remain preserved for later desktop integration and explicit hardware verification |

## 2026-07-10 ZW-STABILIZE-001 Current Baseline Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-10 | Single product baseline | Freeze the supported minimum flow as project creation → problem-guide thread → one generated/confirmed solution → the same versioned Artifact → smart-engineer thread isolation → restart recovery | Gives implementation, tests and deprecation decisions one observable product path without adding features |
| 2026-07-10 | Persistence contract | SQLite, Python boundary models and TypeScript contracts all expose schema v22; v23 structured handoff is paused and absent | Fixes a real cross-end drift while preserving forward-only user-data compatibility |
| 2026-07-10 | Deprecation gate | Delete only code proven unreferenced, replaced and covered; retain registered APIs, legacy expert aliases and historical tables until external compatibility is established | Prevents filename-based cleanup from breaking old projects, clients or data |
| 2026-07-10 | Main-flow authority | Persisted central chat actions own clarification and solution UX; SolutionRepository and ArtifactRepository remain the single data authority | Prevents standalone form/card implementations from diverging from the permanent main conversation and right-side Artifact |

## 2026-07-10 ZW-MAINT-001 Project Cleanup Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-10 | Generated-output cleanup | Delete only an explicit workspace-validated allowlist; preserve `.venv`, `node_modules`, `.data` and local Codex configuration | Releases reproducible build/cache space without making the completed app or user data unrecoverable |
| 2026-07-10 | Test support ownership | Keep reusable credentials/providers in `tests/fakes.py` and fixture wiring in `conftest.py` | Removes repeated fake implementations while preserving module-level monkeypatch boundaries |
| 2026-07-10 | Entry routing boundary | Production EntryRouter remains Provider-only; deterministic routing is explicitly named `local_recovery_route` and is limited to repository fixtures/package recovery | Prevents obsolete sync model/fallback code from being mistaken for a production AI success path |
| 2026-07-10 | Documentation authority | `README.md`, `docs/PRD.md`, `docs/ARCHITECTURE.md` and the current `HANDOFF.md` are active entry points; the original PRD is archived and the stale bootstrap Manifest is removed | Separates current operating truth from historical source material and Git-restorable bootstrap metadata |

## 2026-07-10 ZW-LLM-001 Required Provider Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-10 | Production AI fallback | Every project-understanding, content-generation and revision path must call the configured DeepSeek Provider; local templates and keyword results cannot be returned as production success | A successful response must represent actual cloud-model work, not a silent approximation |
| 2026-07-10 | Structured output failure | Validate with Pydantic, allow one repair call, then return `LLM_OUTPUT_INVALID` without persisting a new business version | Keeps bounded retries and prevents malformed model output from becoming an Artifact |
| 2026-07-10 | Local authority | Keep permissions, approvals, state, persistence, hardware rules, static checks, CAD bounds and file/Shell/serial/device execution deterministic and local | Cloud models must not gain direct operational authority |
| 2026-07-10 | Provider verification | Automated tests use fake providers; paid DeepSeek calls are isolated smoke tests that never expose or persist the Key | Preserves repeatable tests and credential safety |

## 2026-07-15 ZW-LLM-002 Structured Runtime Reliability Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-15 | Clarification schema | Make `questions` the typed Provider field and derive legacy `question` from its first entry in the Sidecar | Removes a redundant exact-copy requirement while keeping current desktop compatibility |
| 2026-07-15 | Invalid-output diagnostics | Persist only validation type, field location and controlled local messages; never persist the Provider's rejected raw output | Makes repeated failures diagnosable without expanding privacy exposure or changing the public error |
| 2026-07-15 | MicroPython storage access | Permit `import os` for board APIs such as `os.listdir('/sd')`, while continuing to reject host execution, file writes/deletes/renames and dynamic execution by AST | Lets generated K10 code honor confirmed microSD requirements without weakening destructive-operation boundaries |
| 2026-07-16 | MicroPython false-positive boundary | Permit explicit non-secret credential placeholders and ordinary object methods such as string `replace()`; reject real literal credentials and destructive calls only when direct or resolved to `os`/`uos` | Fixes the observed NTP alarm generation failure while preserving credential and device-file mutation controls |

## 2026-07-16 ZW-LLM-003 Structure Output Resilience Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-16 | Hardware grounding trigger | Treat explicit selection/replacement/BOM/electrical-plan semantics, typed hardware selection and code drafts as hardware decisions; do not trigger on ordinary sensor/module/install/opening/structure words | Prevents normal structure-engineering prose from being rejected as an attempt to bypass the local library |
| 2026-07-16 | CAD grounding evidence | Prefer Sidecar-confirmed `hardwareId/profileId` pairs over repeated component names in prose | Structured identities are exact, locally controlled and independent of model wording |
| 2026-07-16 | Failure-source contract | Keep `LLM_OUTPUT_INVALID` only for Provider JSON/Schema failure and use `LOCAL_OUTPUT_REJECTED` for repeated deterministic local rejection | Stops local policy failures from being falsely reported as cloud structure failures while preserving one bounded repair attempt |

## 2026-07-10 ZW-UX-004 Simplified Workbench Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-10 | Clarification submission boundary | Treat all pending required questions from one source message as one local draft and one `clarification_batch_answer` turn | Prevents three option clicks from consuming three provider calls and gives the problem guide the complete answer set |
| 2026-07-10 | Batch persistence model | Schema v22 permits multiple answer rows per `clientTurnId` while preserving one answer per `question_record_id` | One user turn can atomically persist a complete group without weakening question idempotency or deleting legacy answers |
| 2026-07-10 | Work-tab information priority | Ordinary mode shows one PendingItem, at most three active/waiting tasks and one recent-completion summary | Keeps attention on the next user decision instead of exposing every downstream engineering generator at once |
| 2026-07-10 | Advanced capability disclosure | Move professional mode to Settings; load model, Skill, MVP and Plan/Spec/Code/CAD/Lesson controls only inside professional details | Ordinary users should not need to understand the internal agent/tool chain, while existing controlled engineering APIs remain available |
| 2026-07-10 | Navigation ownership | Top bar owns project switching, creation and low-frequency project tools; left bar owns only current overview, participating experts and resources | Separates global/project management from frequent expert navigation and removes an overloaded 240px sidebar |
| 2026-07-10 | Central expert header | Use a single status line with optional context details and artifact entry | Preserves first-screen conversation space while keeping shared context available on demand |
| 2026-07-10 | Ordinary artifact/device disclosure | Highlight one current recommendation; hide artifact internals and device identifiers/logs/Dry Run until professional mode | Enforces the singular-solution invariant and keeps operational or sensitive details out of the default workflow |
| 2026-07-10 | Narrow-window behavior | At `<=720px`, initialize both sidebars collapsed and open them as overlays without unmounting `CenterChat` | Maintains a usable conversation width and preserves draft/scroll/context across responsive navigation |
| 2026-07-10 | Phone create action | Render the top-bar create action as a `+` icon at `<=520px`, retaining `aria-label` and tooltip text | Removes the only observed mobile text overflow without hiding or weakening the primary action |
| 2026-07-14 | Requirement clarification channel | Keep ordinary coordinator `PendingItem` entries in the Work summary; collect missing requirements through grouped `uiPayload.type=clarification` cards. Reserve the central confirmation card for domain transitions and explicit local execution authorization. | Resolving a generic pending row only closes that row and cannot persist answers or start a new expert turn; structured questions already preserve source-message ownership, batch completeness and idempotency. |
| 2026-07-14 | Assistant response state | Render a semantic expert avatar and content-sized bubble; use sanitized server progress when available and retain the textual three-dot state only as a legacy/no-event fallback. Never expose reasoning or invent action progress. | Stable identity and an accessible fallback remain necessary, while the new server-owned event can now communicate verified actions without leaking model reasoning. |

## 2026-07-09 Post-ZW-016 Desktop Fix Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-09 | Conversation turn binding | Bind every chat request and SSE chunk with `projectId`, `conversationId`, `clientTurnId/requestTurnId`, and `responseTurnId` | Prevents option answers, old streams, and async reloads from being applied to the wrong project or question |
| 2026-07-09 | Structured answer authority | Persist clarification questions and answers in schema v16 before invoking orchestration/LLM paths | Option cards must be traceable, idempotent, and rejected when stale or mismatched instead of being treated as ordinary free text |
| 2026-07-09 | Frontend stale stream guard | Desktop writes stream chunks only when project, conversation, and request turn match the active pending request | Old responses from previous projects, old conversations, or aborted requests must not overwrite the current central conversation |
| 2026-07-09 | IDEA workflow entry | Remove central top "需求澄清" and "生成方案" buttons; drive clarification, solution, proposal actions through persisted chat messages | Keeps `MainConversation` permanent and makes the primary flow conversational instead of toolbar-driven |
| 2026-07-09 | Structured conversation persistence | Add message-level `structured_payload_json` and `ProjectPersistenceVersion.V14` | Clarification cards, action cards, selected answers and restart recovery need durable project-scoped state |
| 2026-07-09 | IDEA orchestration boundary | Gate project chat on saved API Key, then use Sidecar orchestration to restrict IDEA output to clarification/action payloads before full solution generation | Prevents first ideas from becoming code/HTML/full proposals and avoids frontend-only hiding |
| 2026-07-09 | Project switch isolation | Hydrate `CenterChat` from the selected workspace immediately and ignore stale reloads whose projectId no longer matches the active project | Prevents old project messages, drafts or stream results from appearing in a newly created/opened project |
| 2026-07-09 | Serial scan owner | Enumerate host serial ports in the Python Sidecar, with pyserial metadata when available and Windows registry fallback | React must not access serial APIs or shell; scan-only UI can show real COM ports without auto-connecting |
| 2026-07-09 | Solution revision model | Create a new draft solution version from the current version and record `solution_revisions.changed_sections_json` | Targeted user changes must preserve unrelated sections, keep version lineage, and avoid full-project regeneration |
| 2026-07-09 | Solution Artifact sync | Synchronize each generated/revised implementation solution into one stable project solution Artifact | Chat cards and the right "产物" tab must reference the same persisted solution/artifact version instead of diverging copies |
| 2026-07-09 | Solution display surface | Render generated/revised solutions as `solution_card` chat payloads with expandable sections and card actions | Keeps the main workflow conversational while avoiding unreadable long Markdown in chat |
| 2026-07-09 | Proposal dependency after revision | Mark downstream proposal records stale/outdated after solution revision, but require explicit user action before regenerating them | Prevents automatic proposal churn and keeps formal proposal updates gated on confirmed solutions |
| 2026-07-09 | Work tab overview | Show current stage, one current user need, current solution, and the latest three Artifacts in the Work tab | Users can inspect the fresh solution without repeatedly switching to the Artifacts tab while the top-level tabs remain unchanged |

## ADR-0001：中央区域永久保持主对话

**状态：** Accepted  
**决策：** 产物和设备详情使用右侧栏或浮窗，不使用中央路由替换。  
**原因：** 保持用户创作主线和上下文连续，避免产品退化成传统 IDE。

## ADR-0002：唯一推荐实现方案

**状态：** Accepted  
**决策：** 前台只展示一套当前方案，修改通过对话形成新版本。  
**原因：** 降低教师、学生和普通创客的选择负担，同时后台保留候选与排除原因。

## ADR-0003：云端 LLM + 本地受控工具

**状态：** Accepted  
**决策：** LLM 负责分析和生成，本地 Tool Runner 负责文件、串口、CAD 与命令。  
**原因：** 兼顾能力、设备访问、安全和审计。

## ADR-0004：Python Sidecar

**状态：** Proposed  
**决策：** MVP 使用 Python FastAPI/WebSocket 服务承载 Agent、硬件规则和设备工具。  
**待验证：** Windows 打包体积、启动速度、升级策略。

## ADR-0005：AGENTS.md 作为共同开发规则

**状态：** Accepted  
**决策：** Codex 与 Qoder 共享根 AGENTS.md；工具特定 Agent 配置分开，产品事实文档共享。

---

## ZW-001 Repository Bootstrap 决策

| 日期 | 决策 | 选择 | 理由 |
|---|---|---|---|
| 2026-07-08 | 包管理器 | pnpm | monorepo workspace，磁盘效率高 |
| 2026-07-08 | Tauri 版本 | v2 | 最新稳定版，支持 sidecar |
| 2026-07-08 | 前端样式 | 原生 CSS | MVP 保持轻量，不引入重框架 |
| 2026-07-08 | Sidecar 启动方式 | 初期独立启动 | 降低初始复杂度，后续集成 Tauri sidecar API |
| 2026-07-08 | 串口归属 | Python pyserial | PRD 23 条待确认决策的默认假设 |
| 2026-07-08 | 首发平台 | Windows 优先 | PRD 默认假设 |
| 2026-07-08 | 右侧面板宽度 | 320px | 适中信息密度 |
| 2026-07-08 | Sidecar 端口 | 8100 | 避免与 Vite 5173 冲突 |

---

## ZW-002 桌面应用 + DeepSeek 真实对话 决策

| 日期 | 决策 | 选择 | 理由 |
|---|---|---|---|
| 2026-07-08 | ZW-002 任务方向 | 桌面应用 + DeepSeek 真实对话 | 用户重新定义本阶段目标 |
| 2026-07-08 | 正式入口 | Tauri 桌面窗口 | PRD 与用户要求明确浏览器不是正式入口 |
| 2026-07-08 | LLM 调用位置 | Python Sidecar | 避免前端长期持有 Key；符合云端 LLM 不直接操作本地系统边界 |
| 2026-07-08 | 流式协议 | Sidecar 对 UI 使用 SSE | DeepSeek 上游为 SSE，本轮单向 token 流足够，复杂事件留给后续 WebSocket |
| 2026-07-08 | Key 存储方案 | Windows Credential Manager（ctypes CredWriteW/CredReadW） | 满足 API Key 不进项目文件/日志/Git 的安全要求；不引入 keyring 第三方依赖 |
| 2026-07-08 | DeepSeek 专属参数 | 隔离在 DeepSeekProvider | 保持 LLM Gateway 供应商无关 |
| 2026-07-08 | 自动测试网络策略 | Mock DeepSeek，不访问真实 API | 防止消耗额度和泄露真实密钥 |
| 2026-07-08 | Sidecar 生命周期 | Tauri Rust 管理（spawn on start, kill on close） | 开发模式脚本预启动时自动检测并跳过；关闭窗口时终止子进程 |
| 2026-07-08 | Windows 安装包打包 | 方案 B（开发阶段保留 Python 解释器启动） | PyInstaller 未安装；Tauri CLI 未安装；记录为环境阻塞项 |
| 2026-07-08 | 正式支持模型 | deepseek-v4-flash 和 deepseek-v4-pro | 用户明确要求；Provider 接口保持可扩展但不提前实现其他供应商 |

---

## ZW-003 Project Management and Local Persistence Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Project data owner | Python Sidecar | Keeps all local system/data access behind the established Sidecar boundary; frontend and Tauri do not read/write project files directly |
| 2026-07-08 | Project persistence store | SQLite via Python stdlib `sqlite3` | Streaming conversations need transactional append/update, schema versioning, and restart recovery without adding a new runtime dependency |
| 2026-07-08 | Schema version | SQLite `PRAGMA user_version = 1` plus shared `ProjectPersistenceVersion.V1` | Gives an explicit migration gate and allows future versions to reject unsupported newer databases |
| 2026-07-08 | API Key separation | Keep API Key only in Windows Credential Manager | Project DB stores messages, drafts, selected model, and metadata only; credentials and authorization headers are excluded |
| 2026-07-08 | Project-scoped chat | UI uses `/api/projects/{projectId}/chat/stream` | Real DeepSeek conversations are written into the active project history while preserving provider-neutral LLM Gateway boundaries |
| 2026-07-08 | Frontend workspace state | AppShell-owned React hook state, no new state library | Current workspace state is scoped and small; adding Redux/Zustand would increase baseline complexity without clear benefit |
| 2026-07-08 | MainConversation invariant | Keep `CenterChat` mounted and switch data only | Satisfies UI Contract: project switching, settings, right tabs, and floating windows must not replace the central conversation |

---

## ZW-005 Hardware Library and Rule Engine Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Hardware persistence | Store hardware components in the same SQLite project database, schema `user_version = 3` | Keeps MVP local and transactional without adding a second store |
| 2026-07-08 | Built-in hardware catalog | Seed an ESP32 MVP set with fixed IDs via `INSERT OR IGNORE` | Gives immediate usable defaults while preserving user edits |
| 2026-07-08 | Rule authority | Deterministic rule engine decides electrical compatibility before LLM generation | Prevents LLM output from overriding voltage, logic-level, current, I2C, MCU support, or firmware failures |
| 2026-07-08 | Solution generation gate | Optional `componentIds` are validated before LLM config/key lookup and before DeepSeek calls | Failed hardware combinations return `HARDWARE_VALIDATION_FAILED` without consuming API quota |
| 2026-07-08 | MVP thresholds | Voltage tolerance `0.5V`, logic-level tolerance `0.3V`, current by summed peak load versus maximum selected power source | Conservative MVP defaults that are easy to audit and test |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V3` and return `schemaVersion: 3` | Aligns API contracts with the ZW-005 SQLite migration |

---

## ZW-006 Project Proposal Workflow Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Proposal generation source | Only `CONFIRMED` solutions can generate proposals | Keeps the proposal as a formal baseline and prevents draft implementation ideas from entering downstream stages |
| 2026-07-08 | Proposal persistence | Store proposals in the project SQLite database, schema `user_version = 4` | Versions and status transitions need transactional local persistence next to projects and solutions |
| 2026-07-08 | Proposal export implementation | Use Python standard library renderers for Markdown, minimal DOCX, and minimal PDF | Avoids new dependencies in MVP while making export MIME/signatures testable |
| 2026-07-08 | Proposal stale policy | A newly generated solution marks existing DRAFT and APPROVED proposals as `STALE` | Downstream stages must not silently use a proposal tied to an older implementation baseline |
| 2026-07-08 | Proposal UI surface | Right "产物" tab lists real proposal versions and floating windows preview full sections | Maintains the product invariant that central `MainConversation` remains mounted and is not replaced by artifact views |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V4` and return `schemaVersion: 4` | Aligns API contracts with the ZW-006 proposals migration |

---

## ZW-007 Orchestrator and Agent Registry Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Agent execution | Use deterministic Mock Agent execution in ZW-007 | Validates orchestration, persistence, approval and UI without entering later real Agent/Skill stages |
| 2026-07-08 | Execution plan source | Require an `APPROVED` proposal | Keeps orchestration tied to a formal project baseline |
| 2026-07-08 | Permission boundary | Agent nodes record state and intent only, no direct local system permissions | Preserves the rule that Agent/LLM cannot directly execute shell, files, serial, firmware or CAD operations |
| 2026-07-08 | User confirmation | Use `AWAITING_APPROVAL` task nodes for confirmation gates | Makes manual control explicit and recoverable before downstream work |
| 2026-07-08 | Work UI | Right "工作" tab displays compact plan progress and actions | Keeps `MainConversation` mounted and hides Agent/model/tool details in normal mode |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V5` and return `schemaVersion: 5` | Aligns API contracts with the ZW-007 orchestrator migration |

---

## ZW-008 Skill Registry and Model Router Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Provider scope | Continue to formally support only `deepseek-v4-flash` and `deepseek-v4-pro` | Keeps provider abstraction extensible without prematurely implementing other suppliers |
| 2026-07-08 | User Skill safety default | User-defined Skills are created with no permissions unless explicitly declared | Prevents implicit Shell/device/CAD capabilities and keeps permission review auditable |
| 2026-07-08 | Model router tests | Use deterministic Mock routing and audit records, no real LLM calls | Avoids cost and credential exposure while testing routing behavior |
| 2026-07-08 | Professional mode | Skill and model router details appear only after enabling professional mode | Satisfies normal-mode requirement to hide Agent/Skill/model/toolchain details |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V6` and return `schemaVersion: 6` | Aligns API contracts with the ZW-008 skill/router migration |

---

## ZW-009 Artifact and Floating Window System Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Artifact storage | Store MVP artifact previews in SQLite JSON/text, schema `user_version = 7` | Provides version/dependency/state tracking without entering later file sandbox and Tool Runner stages |
| 2026-07-08 | Proposal compatibility | Keep proposal APIs and tables, synchronize proposal versions into Artifact records | Avoids breaking ZW-006 while making the right "产物" tab generic for later Agent outputs |
| 2026-07-08 | Window manager ownership | Manage floating windows in `AppShell` as overlay state, not route state | Preserves `MainConversation` mounting and avoids replacing the central conversation |
| 2026-07-08 | Window limits | Maximum 3 open windows and one instance per `singletonKey` | Matches UI Contract and prevents desktop clutter/performance issues |
| 2026-07-08 | Closed window state | Preserve the last frontend window spec by singleton key | Satisfies close/reopen state retention without adding cross-process persistence complexity |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V7` and return `schemaVersion: 7` | Aligns API contracts with the ZW-009 artifact/window migration |

---

## ZW-010 Spec Agent Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Spec generation | Use deterministic Mock Spec Agent | Validates contracts, YAML artifacts and lifecycle without real paid LLM calls |
| 2026-07-08 | Spec source gate | Require an `APPROVED` proposal | Keeps formal engineering specs tied to a confirmed project baseline |
| 2026-07-08 | Spec file storage | Store YAML text in SQLite and synchronize it into Artifact versions | Avoids entering Code Agent file-workspace scope while preserving preview, versioning and dependencies |
| 2026-07-08 | Hardware validation | Reuse the ZW-005 hardware rule boundary for Spec validation checks | Keeps deterministic electrical/IO constraints authoritative over generated content |
| 2026-07-08 | Downstream invalidation | Confirmed Spec changes stale Code/CAD/Deploy artifacts | Prevents later artifacts from silently using an outdated engineering baseline |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V8` and return `schemaVersion: 8` | Aligns API contracts with the ZW-010 Spec migration |

---

## ZW-011 Code Agent Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Code generation | Use deterministic Mock Code Agent | Validates code lifecycle, artifacts and UI without paid LLM calls |
| 2026-07-08 | Code source gate | Require an `APPROVED` Spec | Prevents draft specs from becoming deployable code |
| 2026-07-08 | Workspace model | Store code drafts in SQLite with a `workspace://` virtual root | Provides diff/preview/rollback while avoiding real file writes before Tool Runner boundaries are implemented |
| 2026-07-08 | Test execution | Record deterministic mock test results instead of running Shell | Preserves the rule that commands must go through controlled Tool Runner and avoids arbitrary command execution |
| 2026-07-08 | Code Artifact | Synchronize generated files and diff as a `CODE` Artifact from `code-agent` | Makes code visible through the existing Artifact/floating-window system and keeps downstream stages traceable |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V9` and return `schemaVersion: 9` | Aligns API contracts with the ZW-011 code migration |

The 2026-07-08 deterministic Mock Code Agent and recorded mock-test decisions are historical. The 2026-07-11 ZW-AGENT-002 Provider generation and controlled local validation decisions below supersede them for the current runtime.

## ZW-012 Device Management and MicroPython Deployment Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Automated device strategy | Use Mock USB serial discovery and Dry Run operations only | Avoids real hardware dependency, real serial identifiers, device file overwrite and high-risk Flash operations in automated tests |
| 2026-07-08 | Upload command boundary | Record `mpremote` as the command label but do not execute shell commands | Preserves the MicroPython daily-upload workflow while keeping Tool Runner and real device execution out of scope |
| 2026-07-08 | Firmware flashing boundary | Require `confirmFlash=true` and still block `dryRun=false` | Keeps the explicit confirmation point while preventing automatic Flash erase or firmware burning |
| 2026-07-08 | Device log storage | Synchronize deployment logs into `DEVICE_LOG` Artifacts from `deploy-agent` | Makes deployment evidence visible through the existing Artifact/floating-window system without replacing the central conversation |
| 2026-07-08 | Real device validation | Mark ZW-012 software complete with external hardware validation pending | The repository can validate Mock/Dry Run behavior automatically, but cannot safely claim real ESP32 upload or firmware flashing success |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V10` and return `schemaVersion: 10` | Aligns API contracts with the ZW-012 device migration |

## ZW-013 CAD Agent Decisions（历史实现）

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | CAD execution strategy | Use deterministic controlled templates only | Keeps CAD generation auditable, bounded and repeatable without executing arbitrary user Python |
| 2026-07-08 | CadQuery runtime boundary | Record `cadquery-template-dry-run` as the command label, but do not import or execute real CadQuery | Current automated environment cannot assume CadQuery availability; ZW-013 focuses on the safe execution contract and artifact lifecycle |
| 2026-07-08 | Parameter validation | Store generated CAD runs even when validation fails, but mark them `FAILED` and block confirmation | Preserves diagnostics while preventing invalid geometry from being approved |
| 2026-07-08 | 3D preview surface | Synchronize CAD output into a `MODEL_3D` Artifact with an `artifact://` STL preview URL | Reuses the existing Artifact/floating-window system and preserves the central conversation invariant |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V11` and return `schemaVersion: 11` | Aligns API contracts with the ZW-013 CAD migration |

以上 `cadquery-template-dry-run`、`artifact://` STL 预览和 schema v11 只描述 2026-07-08 的 ZW-013 历史路径。ZW-CAD-001 的受限真实 CadQuery Worker、ArtifactVersion 二进制文件 API、GLB 浮窗由 schema v24 引入；当前权威版本为在其上增加本地授权关联的 schema v25。旧 `/cad/generate` 仅保留无副作用 HTTP 410 迁移边界。

## ZW-CAD-001 结构工程师真实 CAD 决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-13 | 原型处置 | `references/local/ZW-CAD-intent` 只作为语义、几何和测试 oracle | 不迁移独立 Node HTTP、SPA、模型源或任意 Python 执行入口 |
| 2026-07-13 | CAD authority | 结构工程师只输出声明式 `cadDraft`；本地服务固化 `CadBuildSpec` | 云端 LLM 不直接获得文件、Shell、CAD 代码或本地路径权限 |
| 2026-07-13 | Direct CAD intake | 复用中央整组 clarification 收集松散/固定模式和内腔尺寸；固定安装再显示服务端受信档案选项，不使用 PendingItem 收集 | PendingItem 处理动作不携带答案；结构化问题已有归属、选项校验、批量提交和持久化能力 |
| 2026-07-13 | CAD routing priority | 结构工程师 CAD 在 solution/proposal 阶段优先进入 ExpertRuntime；当前文本、来源 `cad_*` 卡或最近 CAD 语境加继续/修订表达可延续 | 防止最终项目流程被通用方案路由截走，同时避免历史 CAD 卡把所有结构咨询永久误判成建模 |
| 2026-07-13 | Intake atomicity and recovery | 澄清答案、answered 状态与 CAD SharedFact 同一 SQLite 事务；重复 turn 复用原子结果，不重放旧 facts | 进程异常或非法尺寸不能留下“已回答但 facts 缺失”的不可恢复半状态，也不能用旧 turn 撤销新修订 |
| 2026-07-13 | CAD revision round | 明确修改、重做或新的三轴尺寸会 supersede 旧 intake；同事务 stale 旧 `DRAFT/VALIDATED/READY_FOR_REVIEW/FAILED/CANCELED/REJECTED` 及聊天/Artifact 投影，保留 `QUEUED/RUNNING/APPROVED`；每个 profile 只暴露当前 revision | 支持真实设计迭代，避免旧尺寸继续排队或确认，同时不隐式取消本地 Worker、不提前丢失最后确认基线 |
| 2026-07-13 | Current intake snapshot guard | Sidecar 以 confirmed fact ID/值生成 `intakeSnapshotSha256`，并在 create/retry/finalize/confirm 复核；失配统一 HTTP 409 `CAD_INTAKE_REVISED` | 相同数值的新一轮仍是不同设计授权；幂等键、失败重试和运行中旧 Job 都不能复活旧快照 |
| 2026-07-13 | Expert identity and CAD payload gate | Runtime 使用项目实际 ProjectExpert 类型；未识别为 CAD workflow 的结构回复不得持久 `cadDraft` 或 `cad_*` clarification | 防止陈旧/伪造请求类型越权和 Provider 绕过 intake 猜测结构参数 |
| 2026-07-13 | Loose storage | 用户明确松散存放且不开接口孔时允许 `components=[]`，即使描述出现 ESP32 | 泛称物品不应强迫用户提供不存在的精确机械档案；尺寸确认后即可确定性生成空盒 |
| 2026-07-13 | Project profile identity | 直接 CAD 用基于 `profileId + revision + SHA-256` 的服务端 option/虚拟 hardware ID，Job 入队再次读取当前项目选择 | 支持无 Spec/BOM 的直接结构项目，同时禁止把 XIAO、DevKitC 或泛称 ESP32 相互替代 |
| 2026-07-13 | Mechanical identity | `hardwareId -> profileId -> revision -> SHA-256` 显式映射并快照 | 禁止按名称猜尺寸，确保 Job 重试和模型复现使用同一机械事实 |
| 2026-07-13 | Worker boundary | 固定模板、stdin JSON、受限 cwd、单 Job 和资源上限 | 关闭 `runpy`、动态 import、Shell、凭据和路径穿越入口 |
| 2026-07-13 | CAD persistence | SQLite 只存 Job/Run/Artifact 文件元数据，二进制进入不可变 ArtifactVersion 文件目录 | 支持原子发布、SHA 校验、下载 capability 和重启恢复 |
| 2026-07-13 | Host policy | CAD 执行、取消、重试、确认和退回都要求桌面 capability；Web 只读 | 浏览器模式不应伪造本地 CAD 成功或改变工程基线 |
| 2026-07-13 | Template scope | 首期只支持 `BOX_WITH_LID -> box-with-lid.v1`；泛支架/安装座/结构件/打印件文本不进入盒体 intake | 原型是带盖长方盒规则系统；不允许把不支持的结构类型静默生成错误盒体 |
| 2026-07-16 | Component-derived structure | 新增 `COMPONENT_MOUNT -> component-mount.v1`，必须绑定一个已确认机械档案；安装座类请求进入该路径，模糊目标先确认 | 允许用户直接围绕电子器件创建结构，同时继续禁止把所有建模请求静默生成盒体 |
| 2026-07-16 | Component mount artifact compatibility | `base` 表示安装底座，`lid` 表示可拆压框，继续发布固定 11 文件 | 保持 Artifact、Worker manifest、Three.js 预览和现有 UI 契约稳定 |
| 2026-07-16 | Component model authority | 机械档案的包络、固定孔和受控 model kind 是尺寸权威；Hardware Skill `models/cadquery.py` 保持 `REFERENCE_ONLY` | 更新统一硬件库即可刷新结构事实，但不会把库编辑变成任意 Python 执行入口 |
| 2026-07-16 | Mechanical preview geometry | `mechanical.md` 自然描述中的已确认可见实体必须编译到受控 `preview_geometry`；预览读取该快照而非只画总包络 | 让统一硬件库更新后即可得到与 PCB、连接器和传感体描述一致的 3D 示意，同时不执行参考 Python |
| 2026-07-17 | Mechanical preview authority | `references/mechanical.md` 的 `## 自然语言描述` 是唯一几何真值；`preview_geometry` 改为带 `source_sha256` 的派生缓存，用户显式点击预览时校验、必要时生成并以新 Skill revision 回写 | 作者只维护一份自然描述；应用不会把旧缓存、参考 Python 或浏览器猜测冒充当前 3D 预览 |
| 2026-07-16 | No-hardware freeform structure | 新增 `FREEFORM_STRUCTURE -> freeform-structure.v1`；不引用器件，使用最多 32 个有界基本体的声明式 `add/cut`，最终单连通 | 用户可以仅用自然语言创建安装板/连接板/自定义零件，又不扩大为任意 CAD 代码执行 |
| 2026-07-20 | K10 electronic photo album template | 新增固定 `UNIHIKER_K10_PHOTO_ALBUM -> unihiker-k10-photo-album.v1`；Provider 不能提供参数、器件、geometry 或 revision | 已确认资料包含 60° 斜面、局部坐标和多阶段圆角，简单自由图元会失真；本地固定几何能复用模板且不扩大代码执行权限 |
| 2026-07-13 | Resource limit | Worker 内存 1 GiB、墙钟 180 秒、CPU 120 秒、输出 256 MiB | 256/512 MiB 实测无法运行 CadQuery；保留更严格的输出和文件限制 |
| 2026-07-13 | Mechanical profile product surface | 机械档案只在专业模式“设置 → 公共知识”的第三内部 Tab 按点击懒加载；普通模式零挂载、零请求，右侧一级 Tab 不变 | 让结构工程师使用的尺寸证据可审查，同时不向普通用户暴露内部工程档案 |
| 2026-07-13 | K10 lock boundary | UI 排除 K10 重映射、DELETE 拒绝解除、CAD 解析固定内置 K10；直接 PUT guard 作为残余风险公开记录 | 文档必须反映实际边界，不能在未改代码时声称 API 全层已锁定 |
| 2026-07-13 | Service-opening retainer clipping | 仅当同一硬件、同一侧墙且开孔投影与限位件实际相交时，裁低对应 `edge_retainer` 到开孔下缘；保留最小壁厚、机械间隙、`0.05 mm` 融合和五件完整性，无法留下有效挡高时失败关闭 | 解决 XIAO USB-C 跨面开孔冲突，同时避免 profile ID 特判或跳过碰撞校验 |

## ZW-014 Lesson Agent Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Lesson generation | Use deterministic Markdown templates | Avoids paid LLM calls and credential exposure while making teaching-material output testable |
| 2026-07-08 | Lesson source gate | Require an `APPROVED` Spec and load its linked approved proposal | Keeps classroom materials tied to the current confirmed engineering baseline |
| 2026-07-08 | Lesson artifact model | Store each lesson document as a separate `DOCUMENT` Artifact from `lesson-agent` | Lets the right "产物" tab and floating windows preview teacher guide, worksheet, rubric and safety notes independently |
| 2026-07-08 | Engineering-data boundary | Confirming or rejecting lessons does not mutate proposal, Spec, Code, CAD or device records | Lesson materials are teaching artifacts and must not rewrite engineering source-of-truth data |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V12` and return `schemaVersion: 12` | Aligns API contracts with the ZW-014 lesson migration |

## ZW-015 Sharing and Project Package Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | Package execution boundary | Export/import project packages only in the Python Sidecar | Keeps frontend away from raw SQLite, local files and filesystem paths |
| 2026-07-08 | Export format | Create a controlled ZIP with manifest, project summary, privacy report and selected Artifact previews | Gives a portable and auditable package while avoiding raw database and workspace exports |
| 2026-07-08 | Privacy gate | Block package creation when the privacy scanner detects credentials, authorization data, serial IDs or absolute paths | Prevents sensitive local data from entering ZIP payloads, logs, tests or Git |
| 2026-07-08 | ZIP path policy | Allow only fixed relative POSIX paths and reject absolute paths, drive letters, backslashes, `..`, directory entries and unknown paths | Provides deterministic path traversal protection during import |
| 2026-07-08 | Import conflict policy | Default to `CREATE_COPY` and generate a new local project ID | Avoids overwriting existing projects and keeps imports reversible |
| 2026-07-08 | Package artifact model | Synchronize export/import records as a `PACKAGE` Artifact from `publish-agent` | Makes project packages visible through the existing Artifact/floating-window surface without replacing the central conversation |
| 2026-07-08 | Project schema contract | Expose `ProjectPersistenceVersion.V13` and return `schemaVersion: 13` | Aligns API contracts with the ZW-015 package migration |

## ZW-UX-005 Explicit Routing and Shared Knowledge Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-14 | Project recommendation trigger | Call `/api/projects/suggest` only after the user clicks “分析并推荐”; invalidate the result when the idea changes | Users often refine the idea while typing, so a deliberate trigger produces a recommendation from the complete input and avoids premature paid requests |
| 2026-07-14 | Project expert membership | Reuse the existing project-scoped add/restore API and activate the newly added expert | “临时添加” means on-demand membership in the current project; persistence is required so reopening the project restores the independent thread |
| 2026-07-14 | Shared knowledge boundary | Keep one global component knowledge source for all three experts while retaining separate threads, private memory and Agent Skill files | Engineers need consistent facts without turning the product into a shared Provider group chat or leaking private context |
| 2026-07-14 | Knowledge product surface | Add complete component forms, searchable list and explicit detail view under Settings → 公共知识 | Users need to inspect exactly what the experts can read and maintain it without a new page, right-side tab or schema |

## ZW-UX-006 原型视觉迁移与设置分层决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-14 | 原型迁移边界 | 只迁移视觉 token、卡片层级、控件密度和状态表达；保留现有 `AppShell`、真实 API、领域状态与设置数据 | 获得统一视觉，同时避免复制原型假模型或形成平行工作台 |
| 2026-07-14 | 普通模式模型信息 | 只显示供应商无关的服务摘要、安全凭据状态/入口和连接状态；不显示服务商、Base URL、精确模型、思考模式或超时 | 保持普通模式安静，并避免暴露实现和高级调参细节 |
| 2026-07-14 | 专业模式模型信息 | 服务商、Base URL、精确模型、思考模式和请求超时只在专业模式显示 | 高级配置保持可用，但不扩大普通模式的信息面 |

## ZW-UX-007 项目硬件初选与器件项目编辑决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-14 | 硬件选择时机 | 放在项目创建覆盖层的可选“步骤 0”，位于显式分析之前；不作为第一张必答 LLM 澄清题 | EntryRouter 和自动 kickoff 必须从第一轮就看到硬件约束；动态库搜索与真实 component ID 不能由有限 Provider 选项承担 |
| 2026-07-14 | 选择语义 | `selectedHardwareIds` 固化为 confirmed `preferred_hardware`，表示优先复用并允许补缺，不冻结最终 BOM | 用户可能只拥有部分器件；模型应复用已选并补齐缺口，而不是重复推荐或强迫一次选全 |
| 2026-07-14 | 服务端权威 | suggest/create 均重新校验 ACTIVE 状态和 Rule Engine；Provider 只接收有界解析摘要 | 防止旧客户端、归档条目、虚构 ID 和不兼容组合进入首轮上下文或项目事务 |
| 2026-07-14 | 器件项目存储 | 固定四个 Markdown 文件，默认从结构化组件生成，用户内容写数据目录 overlay 并用整体 revision CAS | 提供完整可审查的器件说明项目，同时保持数据库字段为电气/安全规则真值且无需 schema migration |
| 2026-07-14 | 编辑器位置 | 复用现有最多三窗口浮窗，左树右编辑器；设置只保留入口 | 保持永久中央对话、固定右侧三 Tab和窄屏覆盖规则，不形成第二套工作台 |
| 2026-07-14 | 上下文选择与可见性 | confirmed 已选器件按 ID 精确水合并优先于关键词命中，相关组件去重后共享总计 16,000 字符预算；只有保存成功的有效 overlay 可见，未保存草稿不注入 | 让三师稳定复用用户已有器件，同时防止重复、无界或尚未确认的 Markdown 污染模型上下文 |
| 2026-07-14 | 浮窗草稿生命周期 | 最小化保留草稿；关闭或第四窗口淘汰未保存编辑器前确认；保存期间锁定，409 刷新失败可保稿重试 | 编辑完整器件说明时不能因窗口管理、并发保存或网络失败静默丢失工作 |

## ZW-UX-008 分析后项目硬件选择与缺件补充决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-15 | 硬件选择时机 | 用户先完成“分析并推荐”，成功后才显示可选项目硬件；新桌面 suggest 不携带预选硬件 | 入口分析应围绕完整创意决定项目名和参与智能体，器件确认是分析后的独立本地约束，不应反过来使入口路由失效 |
| 2026-07-15 | 项目内更新语义 | 使用完整选择快照，在一个 SQLite 事务中 supersede 所有旧 confirmed `preferred_hardware` 并插入新事实 | 用户既要能补充也要能纠正误选；保留 superseded 审计链同时保证三师只读取唯一当前选择 |
| 2026-07-15 | 缺件输出边界 | `hardware_selection` 只允许 summary 和 1-8 个能力名称；component ID、ACTIVE、库存、组合规则和写库均归本地 Sidecar | Provider 可以解释规划缺口，但不能伪造硬件库记录或绕过本地安全规则 |
| 2026-07-15 | 选择器入口 | 中央缺件卡与项目工具复用同一覆盖层选择器；中央按钮不发送额外聊天消息 | 保持单一 CenterChat、固定右侧三 Tab，并让用户既可按提醒补件也可主动管理 |
| 2026-07-15 | 卡片视觉资料 | 在没有受信图片字段时使用类别视觉标识，只显示库中真实名称、说明、电压、协议与库存 | 保留参考图的信息架构和浏览效率，但不引入网络图片、伪商品图或第二套素材真值 |

“没有受信图片字段”的阶段性限制已由 ZW-HW-002 取代；类别视觉标识继续作为无图或认证图片加载失败时的回退。

## ZW-016 MVP Integration and Hardening Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | MVP readiness model | Derive readiness from existing v13 SQLite tables without adding a new migration | ZW-016 is a hardening and integration stage; read-only aggregation avoids persistence churn |
| 2026-07-08 | Readiness surface | Show MVP delivery status in the right "工作" tab | Preserves the central conversation invariant and keeps delivery status near Agent/workflow controls |
| 2026-07-08 | End-to-end test boundary | Seed the confirmed solution via repository fixture, then run downstream stages through real Sidecar APIs | Avoids real paid LLM calls while still testing proposal, plan, Spec, Code, Device Dry Run, CAD, Lesson and Package integration |
| 2026-07-08 | External validation handling | Report real device, real API Key and firmware actions as manual validation items | Automated tests cannot safely claim real serial upload, real credentials or Flash operations succeeded |
| 2026-07-08 | Final stop boundary | End autonomous development at ZW-016 with report, checklist, build info, commit and tag | The workflow explicitly forbids creating, planning or implementing ZW-017 |

## ZW-HW-001 Hardware Skill Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-15 | Hardware truth source | Make the effective Hardware Skill Markdown revision authoritative; keep `hardware_components` as a rebuildable compatibility/query projection | Users can inspect and edit every parameter and rule in one project without maintaining a silent second truth in SQLite |
| 2026-07-15 | Rule execution | Let Skill Markdown declare typed data and allowlisted operators, then execute them with a local deterministic interpreter | This satisfies Skill-driven rules without allowing cloud output, Python, Shell or arbitrary expressions to decide PASS/FAIL |
| 2026-07-15 | Package layout | Use `SKILL.md + references + examples + tests` below `<data_dir>/hardware-skills/<skill-name>`; keep `manifest.json` system-managed and truth-free | Matches the supplied OpenClaw package's progressive-loading form while preserving local identity, revision and path controls |
| 2026-07-15 | Creation lifecycle | Treat uploads and dialogue as inputs to one `DRAFT → validate → user confirm → ACTIVE` workflow | Unverified extraction must not enter project selection, expert context or the Rule Engine |
| 2026-07-15 | Existing component migration | Export old rows and their saved Markdown into Hardware Skills idempotently; rebuild SQLite from the compiled Skill and fail closed on invalid packages | Preserves current component IDs/project references while explicitly reversing the ZW-UX-007 database-authority decision |
| 2026-07-15 | Legacy package compatibility | Keep old four-file GET as a read-only mapping of the current Skill revision and make old PUT return 410; retain legacy overlay directories only as migration/recovery evidence | Prevents a second writable Markdown truth and routes all current edits through the eight-file Skill project |
| 2026-07-15 | Engineer Skill editor | Keep the existing agent-package backend/overlay boundary and open each package in a `agent-package:{expertType}` tree/Monaco floating window | Gives all three engineers the same inspectable Markdown-project experience without exposing manifest permissions or replacing CenterChat |

The ZW-UX-007 decisions “database fields remain the electrical/safety rule truth”, “the four-file overlay is writable” and “`hardware-component:{componentId}` is the current editor” are superseded by this section. Its `selectedHardwareIds`, `preferred_hardware`, general floating-window and draft-preservation decisions remain in force; the earlier pre-analysis “project step 0” timing is superseded by ZW-UX-008.

## ZW-HW-003 Unified Hardware Skill Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-16 | Unified fact boundary | One Hardware Skill revision owns electrical facts, structural description, machine-readable mechanical profile, model reference, media, integration, safety and sources | Updating one package must update catalog, validation, expert context and CAD metadata without maintaining hidden copies |
| 2026-07-16 | Model execution boundary | Store `models/cadquery.py` as a SHA-bound `REFERENCE_ONLY` file; execute only the deterministic CAD engine against the compiled mechanical snapshot | Preserves the user's verified source for review without turning normal library editing into arbitrary Python execution |
| 2026-07-16 | Backward compatibility | Keep the original eight files valid; require `references/mechanical.md` and `models/cadquery.py` as an all-or-nothing optional capability | Existing user Skills remain readable while new structural knowledge gets a strict, testable shape |
| 2026-07-16 | Projection transaction | Derive mechanical revision from Hardware Skill revision and update electrical plus mechanical projections in the same save transaction | A failed structure/model edit cannot leave the hardware catalog and CAD metadata on different versions |
| 2026-07-16 | Board Skill role | Board Skill supplies MicroPython API/templates only; current Hardware Skill Markdown supplies electrical, structural, compatibility and safety facts | Prevents K10 programming guidance from becoming a stale second hardware catalog |

## ZW-HW-002 Hardware Catalog Media Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-15 | 默认目录 | 生产 seed 只保留行空板 K10；12 个旧系统样例从活动投影移除，已有生成包按明确 ID 与 `MIGRATED/BUNDLED` 来源移入恢复目录 | 用户要求从真实目录重新开始，同时不能误删用户自建包、项目事实或备份 |
| 2026-07-15 | 图片真值边界 | `manifest.media` 只保存展示元数据与已校验哈希；参数、兼容和安全继续只读 Markdown | 防止图片目录形成第二套硬件工程真值，也禁止从视觉内容推断电气事实 |
| 2026-07-15 | 真实图片获取 | K10 使用本地缓存的 DFRobot 官方产品图，记录来源、署名、使用边界和 SHA-256；不使用热链或生成图 | 页面离线稳定，来源可追溯，且不会用生成内容冒充实物 |
| 2026-07-15 | 访问与校验 | JPEG/PNG/WebP 必须通过安全路径、大小、magic/MIME、HTTPS 来源和 SHA 校验；桌面以登录态 Blob 请求读取 | 图片仍属于受保护的本机硬件知识，不能绕过账号门禁或暴露匿名静态目录 |
| 2026-07-15 | 扩展方式 | 提供与运行包同构的可复制模板，包含 `assets/references/examples/tests` 和中文字段说明 | 后续添加器件不需要修改第二套目录结构，也能完整记录来源和安全边界 |

## ZW-AGENT-001 Agent Skill Package Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-11 | Behavior configuration | Give each canonical visible agent one top-level `SKILL.md` plus allowlisted Markdown references | Matches the requested Skill-package model while keeping each agent's behavior discoverable and progressively loaded |
| 2026-07-11 | Capability separation | Keep the existing 34 Registry Skills as permission-controlled execution capabilities and label them separately in UI | Markdown behavior instructions must not be confused with tools, permissions or local execution authority |
| 2026-07-11 | Source of truth | Derive expert metadata, bindings, artifacts and boundaries from package manifests for runtime and workspace definitions | Removes the former config/SQLite drift, including the truncated structure-engineer Skill list |
| 2026-07-11 | Runtime coverage | Load the effective package in ExpertRuntime, central idea flow and clarification/solution generation | A saved edit must affect the next target-agent Provider prompt instead of being a settings-only description |
| 2026-07-11 | Storage | Keep bundled files read-only and write user changes to the active data directory overlay with atomic replace and revision checks | Preserves schema v22, isolates fake/paid/production data and avoids lost concurrent updates |
| 2026-07-11 | Safety | Allow only manifest-declared UTF-8 Markdown with path, frontmatter, link and size validation | Prevents traversal, broken package references and prompt files from expanding Tool Runner permissions |
| 2026-07-11 | UI placement | Put the editor in professional-mode Settings and preserve the fixed right tabs and mounted `CenterChat` | Maintains the permanent-conversation and ordinary-mode disclosure contracts |
| 2026-07-11 | Compatibility | Preserve `skill-description-overrides.json`, user Registry Skills and legacy expert aliases | Avoids breaking current user data while introducing the package model without a migration |

## ZW-AGENT-002 MicroPython Engineering Loop Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-11 | Board facts | Store each supported board as a bundled Markdown BoardProfile with strict frontmatter; ship `unihiker-k10` and load board facts from the effective profile | Keeps board facts reviewable and editable without a parallel database model or hard-coded Skill facts |
| 2026-07-11 | Board customization | Keep bundled profiles read-only and atomically write data-directory overlays guarded by content revision; reset deletes only the overlay | Preserves defaults, supports reversible customization and prevents silent lost updates without a schema migration |
| 2026-07-11 | Board editor placement | Put BoardProfile editing under professional-mode “设置 → 公共知识 → 开发板档案” | Keeps ordinary mode quiet and preserves the permanent central conversation and fixed right tabs |
| 2026-07-11 | User code storage | Save every user edit as a new CodeRun and ArtifactVersion with `baseSnapshotId`, summary and unified diff; never update prior file rows in place | Makes prior code and validation evidence immutable and reviewable using the existing v22 tables |
| 2026-07-11 | Code save concurrency | Use a `BEGIN IMMEDIATE` compare-and-swap against the latest `baseCodeRunId`; return retryable 409 `CODE_REVISION_CONFLICT` for a stale base | Concurrent editors cannot both claim the same next version, and the UI can preserve the losing draft for manual reapplication |
| 2026-07-11 | Validation concurrency | Validate only the current CodeRun and recheck it transactionally before storing results; return retryable 409 `CODE_VALIDATION_CONFLICT` when superseded | A slow validation result cannot overwrite the state of a newer user version |
| 2026-07-11 | Local validation | Run fixed static, syntax and mock-simulation workers in isolated temporary directories with bounded time, fixed argv and `shell=False` | Gives executable evidence while keeping the cloud model away from files/Shell and preventing real device or arbitrary host actions |
| 2026-07-11 | Validation authority | Derive every check and the overall result only from real process exit codes; skip simulation when static or syntax fails | Output text and model-provided status cannot create a false pass; failed/unrun code cannot become ready or accepted |
| 2026-07-11 | Code editor placement | Reuse the Code Artifact floating window with “代码 / 变更 / 验证” internal views | Provides the engineering loop without a new page, expert or right-side primary Tab and keeps `CenterChat` mounted |
| 2026-07-11 | Unsaved conflict handling | Keep code content and change summary in the browser on save conflict, and state that only saved changes reach the next expert reply | Prevents user data loss and makes the local-draft versus persisted-context boundary explicit |
| 2026-07-11 | Smart-engineer context | Reassemble the latest saved CodeRun, user-change metadata, diff and validation result for every smart-engineer call; include bounded file bodies only for code-related requests | The next Provider reply observes saved work and executable evidence without copying full code to unrelated experts or unbounded prompts |
| 2026-07-11 | Reusable MicroPython Skill | Provide a `SKILL.md` plus BoardProfile and validation references that require effective BoardProfile loading instead of embedded pin/memory facts | The workflow can support future boards and overlays without duplicating or drifting board-specific facts |
| 2026-07-11 | Hardware boundary | Keep static/mock validation separate from USB MicroPython upload, and keep upload separate from erase/firmware flashing | Automated checks must not imply real hardware success or bypass confirmation-gated device operations |

## ZW-AGENT-004 Device Upload Reliability Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-12 | Upload outcome | Treat verified file deployment, device restart and REPL management-channel recovery as three independent results | A post-restart REPL timeout cannot invalidate matching readback hashes or silently roll back a program that is already running |
| 2026-07-12 | Reconnect authority | Retry one non-zero reconnect once, do not repeat timeout/cancel, and use the final real exit code only for `managementChannelOk` | Keeps recovery bounded and prevents REPL availability from being reused as program-runtime evidence |
| 2026-07-12 | Restore boundary | Restore only failures before verified deployment/restart; always retain original and restore failure evidence | A failed rollback must leave the session unavailable and must not hide the cause that triggered restoration |
| 2026-07-12 | Legacy compatibility | Correct only old uploads whose immutable steps prove transfer/readback/restart success and a reconnect-stage failure without restore; append a corrected DEVICE_LOG version | Repairs the user-facing conclusion while preserving original failure and recovery evidence across device and artifact views |
| 2026-07-12 | Request recovery | Reserve operation ID and READY session atomically; retain only project-scoped operation/codeRun/session association IDs in session storage | Lost HTTP responses and remounts can resume or retry the same request safely without duplicate writes or storing ports, source code or device logs in the browser |
| 2026-07-12 | Device UI disclosure | Show one upload path and three result rows in normal mode; expose ports, IDs, exit codes, long logs and firmware only in professional mode | Repeated daily upload stays clear while local engineering evidence remains available without leaking advanced identifiers into ordinary UI |
| 2026-07-12 | Cloud device context | Send only board identity, coarse readiness and bounded timestamps to the target expert | The model can reason about saved project state without receiving serial identifiers, operation IDs, backup paths or raw device logs |

## ZW-AGENT-005 K10 Skill and Project Kickoff Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-12 | Board Skill placement | Mirror the user-supplied `references/source-packages/unihiker-k10-micropython-skill/` below the existing hardware module as a read-only `board-skills/unihiker-k10` package | Keeps the original input untouched, binds board facts to K10 without adding a parallel expert or database model, and preserves the package's references/templates/examples layout |
| 2026-07-12 | Package trust boundary | Validate manifest paths, byte sizes, SHA-256 records, UTF-8 text and symlink absence before loading; expose only bounded selected references/templates to the smart engineer | A Markdown Skill is generation guidance, not a grant of file, Shell, serial, upload or firmware authority |
| 2026-07-12 | Board matching | Match the current request first, then the project's initial idea when no other board is named; an explicit non-K10 board suppresses K10 Skill fallback | Follow-up requests such as “生成代码” continue to use the selected K10 facts without contaminating another board's context |
| 2026-07-12 | Upload file contract | Make `src/main.py` mandatory and default to the only file; permit only flat `src/*.py` dependencies and use the same complete set for Artifact, validation, backup, transfer and SHA-256 readback | `mpremote fs cp` does not create nested directories, and non-device README/test placeholders cannot be part of a runnable upload |
| 2026-07-12 | Simulation authority | Always smoke-run `src/main.py` before optional logic tests; derive each result solely from the child process exit code | A test file that omits the entry point must not hide an import or startup failure |
| 2026-07-12 | Project kickoff | Persist the idea once with a stable `conversation_turns` kickoff and empty assistant placeholder; atomically claim/replay/retry it through the existing project chat stream | The central conversation remains the only surface and refresh/retry cannot duplicate the user's idea or provider call |

## ZW-AGENT-006 Hardware Grounding and Device File Read Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-16 | 三师硬件优先级 | 把 confirmed 项目硬件、本地 ACTIVE Hardware Skill、能力缺口固化为同一上下文字段和 Runtime 输出校验；硬件相关回复必须显式引用已评估的最高优先级本地器件 | 仅把 K10 Markdown 放进 `publicKnowledge` 不能阻止模型直接推荐 ESP32-WROOM 等库外主控；三师需要同一个可测试边界 |
| 2026-07-16 | 未选硬件语义 | 空 `preferred_hardware` 仍表示用户未锁定器件，但模型必须先评估匹配的本地 ACTIVE 库，再声明无法覆盖的能力 | 保留用户可不预选硬件的流程，同时让“硬件库优先”在空选择项目中真实生效 |
| 2026-07-16 | MicroPython 文件读取 | 允许静态可证明的设备端只读 `open()`，继续拒绝动态/写入模式和删除、执行类调用；验证过程仍不运行用户代码 | TF 相册等正常固件必须读取设备文件，把所有 `open()` 当主机能力会导致模型连续修复失败和不可行的纯内存退化 |

## ZW-AGENT-006 Board API Reliability Decisions

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-19 | 掌控板 3.0 API 真值 | 使用按精确组件 ID/Spec BOM 绑定的只读代码契约，记录官方来源、固件族、对象、成员和调用签名；Provider 和可编辑 Hardware Skill 都不能修改门禁 | 提示词和长篇 Markdown 能提供知识，但不能确定性阻止旧版或虚构 API |
| 2026-07-19 | 静态检查分层 | 把板级 AST 语义检查归入既有 `STATIC` Worker；只对成员覆盖完整的对象失败关闭，继承或未完整展开的接口不猜测拒绝 | 在不执行用户代码或导入板载模块的前提下拦截高频错误，同时控制误报 |
| 2026-07-19 | DeepSeek 结构化输出 | 结构化请求启用官方 JSON Object 模式，仍保留一次修复和全部本地 Schema/安全/API 校验 | JSON 模式改善封装可解析性，但不能证明生成代码使用了真实板级 API |
| 2026-07-19 | 运行期修复边界 | M24 只在上传前阻断；串口继续只读观察，不增加自动补丁或自动重传 | 重新上传是新的设备写操作，必须保留用户确认、备份、幂等和有界重试 |

## ZW-STABILITY-002 启动、恢复与简洁 UI 收口决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-19 | 开发 Vite 所有权 | 仅在持久记录的仓库根、PID、启动时间和 5173 监听者全部匹配时回收残留 | 修复本项目陈旧 Vite 阻塞启动，同时不误杀其他 Node 服务 |
| 2026-07-19 | Sidecar 失败体验 | 初次失败仍打开桌面诊断界面；运行期连续失败最多六次，单次安装态冷启动就绪预算 120 秒 | 大型冻结包会被 Windows 首次扫描，但不能因此无界重启或让应用完全不可见 |
| 2026-07-19 | 自动恢复权威 | 用现有消息元数据、`BEGIN IMMEDIATE`、同源唯一认领和三次恢复链上限作为服务端门禁 | 多窗口和重复提交不能绕过费用上限；无需迁移数据库 schema |
| 2026-07-19 | 窄屏侧栏 | `<=720px` 左右覆盖层默认收起且互斥，`<=520px` 压缩顶栏但保留项目选择和侧栏开关 | 保住永久中央对话和主要导航，消除双抽屉遮挡与顶栏重叠 |
| 2026-07-19 | 模型设置分层 | 普通模式保持供应商无关；专业参数默认折叠 | 简化首屏，同时保留专业用户可达的真实配置能力 |
| 2026-07-19 | Windows 目录短锁 | Hardware Skill 原子目录替换只对 `PermissionError` 做八次有限退避，最终错误不吞掉 | 安全扫描会短暂占用新文件；保持原子性和失败关闭比非原子复制更安全 |

## ZW-CLOSURE-001 产品闭环决策

以下 2026-07-26 决策覆盖 2026-07-15 的本机账号与单 K10 目录等冲突历史决定；历史条目仅保留审计价值。

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-26 | 产品访问 | 独立 FastAPI 邮箱身份服务；验证邮箱并完成画像后使用，不恢复游客模式 | 形成可撤销的稳定账号 subject，同时避免把临时访客数据自动分配给错误账号 |
| 2026-07-26 | 数据范围 | 项目正文仍只保存在本机，按云端 subject 隔离；不做跨设备项目同步 | 满足账号隔离而不把本地设备数据扩大为云同步系统 |
| 2026-07-26 | 令牌边界 | access 15 分钟、refresh 30 天并轮换/检测复用；refresh 只进操作系统凭据库，React 使用本地短会话 | 限制长期凭据暴露面并支持离线可信租约与云端撤销 |
| 2026-07-26 | 旧项目迁移 | v25→v26 不自动分配 owner；首次云账号登录只允许认领全部或暂不处理 | 错误自动归属比延迟认领风险更高，旧数据先备份并保持不可跨账号访问 |
| 2026-07-26 | 进度权威 | 阶段、当前动作、五项就绪度、草稿/正式产物和诊断统一由 `ProjectProgressSnapshot` 派生 | 消除顶部、工作栏和产物事实分别推断造成的状态矛盾 |
| 2026-07-26 | 首个设备闭环 | K10 + SEN0193 + DFR0523 + 独立 5V/3A；泵不得由 K10/GPIO 供电且必须共地 | DFR0523 峰值电流超出 GPIO/板载安全供电能力，规则必须失败关闭 |
| 2026-07-26 | 设备完成判定 | 上传完成不等于业务完成；必须读取结构化日志并证明湿润关泵、干燥有限启动/三秒内停止、连续湿度样本和无未处理异常 | 文件回读只能证明部署，不能证明自动浇花核心功能安全运行 |
| 2026-07-26 | 删除与复制 | 复制重建全新 ID 图并排除设备/凭据；永久删除仅在归档区输入项目名且先备份 | 防止跨项目身份串线，并为高风险删除保留可恢复路径 |
| 2026-07-26 | 发布声明 | 缺少真实 SMTP、DeepSeek、实体硬件、独立电源或同提交安装包冷启动时只标记“软件完成、外部验收待办” | Mock、SQLite、Dry Run 和旧安装包都不能冒充真实产品闭环 |

## ZW-CREATOR-001 首轮实用反馈决策

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-31 | 三师模式 | Creator 保留工作台级“三师专业模式”；普通模式呈现统一掌问，专业模式展开三师路由、模型与工具链，两者共享同一作品状态 | 三师协作是产品专业能力，不应随旧壳删除；模式只控制信息层级，不能创建第二套数据 |
| 2026-08-01 | 方案与立项书 | 问题引导师只生成并确认工程方案；立项书改为确认方案后的可选文档投影，方案变更时标记旧立项书过期 | 方案和立项书重复确认会产生两套事实；文档应由方案派生而不是成为第二真相源 |
| 2026-07-31 | 代码可见性 | “代码”入口加载真实当前 `CodeRun` 并复用现有编辑器；没有代码时显示明确原因和生成路径 | 软件策略摘要不是代码，入口必须准确反映真实产物状态 |
| 2026-07-31 | 对话宽度 | 桌面工作区使用约 1:2 的对话/阶段比例，窄屏继续按断点自适应 | 对话是持续创作入口，需要足够空间阅读三师上下文，同时保留主要阶段画布 |
| 2026-08-01 | 数字原型输入与连线 | 输入控件和测试仅来自当前方案验收场景；画布显式显示传感器、主控、驱动、负载、供电和共地拓扑，未确认连接使用虚线 | 板载能力全集不是项目需求，隐藏连线也无法让用户检查电气与控制关系 |
| 2026-08-01 | 调试信息架构 | 传感器输入、执行器控制和参数版本合并为同一调试抽屉，一次只显示一个面板 | 三组控件同时占据底部会压缩画布并形成多重滚动，影响代码和仿真主任务 |
| 2026-08-01 | 本地 MQTT | 只有明确写明本地、本机、局域网、内网或离线 Broker 的方案才加入本地 MQTT 服务节点；通用或云端 MQTT 不自动本地化，场景生成不启动真实端口 | MQTT 是传输协议而不是默认本地基础设施；错误自动启动会改变网络与安全边界 |
| 2026-08-02 | Creator 唯一确认点 | 问题引导师信息齐全后自动生成方案；取消独立目标确认、对话内方案确认和对话内立项书询问，方案区一次确认同时确认目标基准 | 连续三次确认并不会增加事实可信度，反而让用户不清楚哪个版本才是当前方案 |
| 2026-08-02 | 产品经理式需求访谈 | 问题引导师承接上一条答案并直接提出下一个具体产品决策；禁止询问是否继续、怎么继续或是否还要补充，并隐藏历史 Creator 消息中的旧流程动作 | 用户应该回答产品问题，而不是替系统管理访谈状态；元问题会增加无意义轮次并打断思考连续性 |
| 2026-08-02 | 三师自动推进 | Creator 阶段状态变化后自动打开服务端当前阶段；移除同阶段泛化“继续”，三师只在方向性缺口或真实高风险动作前询问 | 普通生成、代码准备和阶段导航不需要用户逐步批准，真实设备安全确认仍必须保留 |
| 2026-08-02 | 仿真版本绑定 | 场景优先使用当前 Creator Solution，并将 Solution/CodeRun 绑定带入仿真启动与证据校验 | 历史 Proposal 与当前 Creator Solution 同时存在时，仅比较旧 `proposalId` 会产生虚假的方案不匹配 |
