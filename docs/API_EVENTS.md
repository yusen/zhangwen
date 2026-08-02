# API 与事件契约 v0.2

## 2026-07-28 ZW-AUTH-002 本机账号恢复

- `GET /api/auth/status` 保持匿名只读，响应扩展为
  `{ hasAccounts, hasLocalAccounts, cloudAuthConfigured }`。`hasLocalAccounts` 只统计活动的
  `auth_kind=local` 账号；`cloudAuthConfigured` 只表示 Sidecar 已配置云认证地址，不把服务可达性伪装成配置状态。
- 云认证未配置且存在本机账号时，桌面复用既有 `POST /api/auth/login`，不新增认证绕过或匿名密码重置 API。
- 密码恢复仅由仓库根目录交互工具执行；工具使用隐藏输入，修改前通过 SQLite backup API 建立备份，并在同一认证库中撤销该账号全部旧会话。云账号、项目 owner、设备与 CAD 门禁不变。

## 2026-07-28 ZW-UX-009 M7 对话流体化

- 不新增数据库迁移，不改变 `ConversationResponse` 判别联合、聊天 SSE 或 `clarification_batch_answer` 请求结构。
- 新产生的 clarification 响应最多包含一个最高影响阻塞问题；服务边界会对模型返回的多问题结果保守截取第一项。所有问题继续允许自然语言回答。
- 历史多问题消息保持兼容：桌面端按源消息逐个在本地收集答案，最后一次性发送既有批量结构化答案；Sidecar 仍在同一事务中校验必答项、记录 answered 状态并写入事实。
- 选择题允许非空 `textInput` 作为自然语言答案；仍保留选项 ID/值的兼容映射，不放宽来源消息、专家 conversation、项目或重复提交门禁。
- 普通模式的单状态、结果卡减法与恢复事件隐藏只属于呈现策略；专业模式继续消费完整 payload 和诊断字段。
- CAD Intent 在既有请求和 revision 协议内解析本轮明确盒体尺寸。明确尺寸优先于当前修订与项目默认值；未阻塞的盒体模式可采用 `80 × 50 × 28 mm` 推荐默认值，修改尺寸会在同一安全 intake 边界重开修订，不新增任意路径、Shell 或 Provider 权限。

## 2026-07-26 ZW-V2-001 M0-M5

- V2 Project Kernel 前缀为 `/api/v2/projects/{projectId}`：`GET /state`、`GET|POST /changesets`、`POST /changesets/{id}/confirm|commit`、`GET /versions`、`GET|POST /releases`、`GET /capabilities` 和 `GET /capability-coverage`。Change Set 提交使用基础版本做并发门禁，并把 Project Event、Project Version 和投影 hash 写入同一数据库事务。
- 已有 V1 事实但尚无 `project_versions` 的项目，首次读取 V2 state/versions 或创建 V2 Change Set/Release 时，Project Kernel 在 `BEGIN IMMEDIATE` 事务中幂等建立 `version=1`、`changeSetId=null` 的只读导入基线，并记录 `V1_BASELINE_IMPORTED` validation/event。基线只引用当时有效 ArtifactVersion 与能力快照，不复制方案、硬件、Artifact、设备或 CAD 真值；完全空白的新项目继续保持 V0。
- Project State fact 增加派生展示字段 `label/displayValue`。澄清答案通过 confirmed fact 的 `source_id`、回复消息的 `replyToMessageId` 和原 clarification payload 恢复问题/选项中文；展示字段不进入 `projectionHash`，不会因文案变化制造工程版本漂移。
- `ConversationTurnContext` 可选携带 `workspaceKind=overview|engineering|structure|delivery`、受各工作区 allowlist 限制的 `workspaceView` 和非负 `projectVersion`。问题引导师与 Expert Runtime 只把它作为聚焦提示，传入 Runtime 前会删除项目 ID、会话 ID等无关字段；它不进入 Host capability 或本地工具授权。
- V2 CAD 提供 `GET /cad/workspace`、`POST /cad/intent`、`POST /cad/revisions/{id}/confirm|undo`。写操作要求宿主 `local_cad` 能力；Worker 输入包含来源 hash、项目版本和能力/硬件快照，输出为修订、对象索引、预检、Tool Job 与 Artifact 源码版本，不接受 HTTP URL、调用方绝对路径、Provider 凭据或任意 Shell。
- 设备会话状态新增 `ATTACHED_UNVERIFIED / RUNTIME_BUSY / MANAGED`。`POST /api/projects/{projectId}/devices/connect` 只附加；`POST /devices/takeover` 执行合作式接管。只有 `confirmHardwareReset=true` 且 `confirmationPhrase="确认硬件复位"` 才允许在合作式接管失败后尝试硬件复位，之后必须重枚举、重连并在启动窗口 break-in。
- Local Bridge 前缀为 `/api/local-bridge`：`GET /status`、`POST /pairing/start`、`POST /pairing/claim`、`POST /revoke`、`GET /sessions` 和 `POST /sessions/{id}/revoke`。全部只允许 loopback；挑战由桌面宿主创建，Web claim 必须匹配精确 allowlist Origin、当前账号和项目。
- Bridge lease 通过 `X-Zhangwen-Bridge-Lease` 传递，修改型请求还必须携带一次性 `X-Zhangwen-Request-Id`。lease 只映射 `cad.local / device.serial / device.upload`；十分钟过期、撤销、跨 Origin/账号/项目、重复 request id 和能力越界均失败关闭。页面刷新会清除 React 内存中的 lease，但已落库 Tool Job 可继续查询。
- SQLite 当前 schema 为 v28：v27 增加 Project Kernel、Change Set、版本/Release 与 Bridge 数据；v28 增加 CAD intent revision 和 Tool Job 结果数据。迁移仍先备份，并保留 V1 读取路径。

## 2026-07-26 ZW-CLOSURE-001 邮箱身份、项目所有权与设备证据

- 云端身份服务提供 `POST /v1/auth/register|verify-email|resend|login|refresh|logout|password-reset/request|password-reset/confirm` 与 `GET/PATCH /v1/me/profile`。access token 为 15 分钟，refresh token 为 30 天且每次轮换；检测旧 refresh 复用时撤销整个 family。
- Sidecar 保持 `/api/auth/*` 门面：`register-email`、`verify-email`、`resend`、`login-email`、`password-reset/*`、`profile`、`session`、`logout`。React 只接收本地短会话 token；云端 refresh token 通过凭据引用保存，不进入响应、SQLite 项目库或浏览器存储。
- 项目 schema v26 的 `owner_subject` 是所有权事实。项目列表、详情、写操作、产物、设备、导入导出和生命周期端点统一按当前 subject 过滤；存在但不属于当前账号的项目返回 404。
- `GET /api/auth/legacy-projects` 返回未归属项目数与决定状态；`POST /api/auth/legacy-projects/claim` 接受 `{ claimAll }`。决定只记录一次，认领前旧数据不向其他账号开放。
- `GET /api/projects/{projectId}/progress` 返回 `ProjectProgressSnapshot`，包含阶段、当前动作、五项就绪度、草稿/正式产物摘要和一致性诊断；顶部、工作栏和就绪度不得再自行推断。
- `POST /api/projects/{projectId}/duplicate` 返回新项目与 `idMap`；实现复用项目包克隆，但排除设备会话、凭据和真实串口。`DELETE /api/projects/{projectId}/permanent` 只接受已归档项目、精确项目名确认，并先返回可恢复 `backupId`。
- `POST /api/projects/{projectId}/devices/watering-smoke/evaluate` 只读取当前终端输出，不写 GPIO。请求绑定已完成的真实非 Dry Run 上传；响应要求至少三条湿度样本、所有 `WET` 样本泵为 `OFF`、`DRY` 后出现 `ON` 并在 3000ms 内 `OFF`、且无 Traceback/unhandled/fatal。通过后证据写入设备操作元数据和新的设备日志 ArtifactVersion。
- 上传状态 `COMPLETED` 只证明部署；`ProjectProgressSnapshot.stage=DEVICE_VERIFIED` 还要求 `runtimeEvidence.ok=true`。Mock 与 Dry Run 永远不能写成真实设备验证。

## 2026-07-20 ZW-STABILITY-002 M11 Kimi/GLM 业务流与自定义模型

- `ModelConfig` 新增可选 `isCustom`；`LLMConfig` 与 `SaveLLMConfigRequest` 新增 `customModels`，上限 32 个。自定义模型 ID 为 1–128 位、以字母或数字开头且只含字母、数字、点、下划线、斜杠或连字符的 Provider 模型代码；必须绑定 Provider、标记为自定义、不得覆盖内置模型。API Key 仍不进入该数组或配置文件。
- 内置模型保留既有枚举语义；模型边界同时接受通过上述校验的自定义字符串。保存的 `defaultModel` 必须属于当前 Provider 的内置或自定义目录；`GET /api/settings/llm/models` 返回内置目录与已保存的自定义目录，项目创建、消息、流事件和项目持久化可往返自定义模型 ID。
- Kimi 内置目录固定包含 `kimi-k3`、`kimi-k2.7-code`、`kimi-k2.7-code-highspeed`。Kimi、GLM、千问和 DeepSeek 继续共享 OpenAI-compatible Chat Completions 传输，不新增 Provider 专用业务 API。
- 流式传输允许 usage-only 帧省略 `choices` 或返回 `choices: []`。Sidecar 必须先归并合法 `usage`，随后安全跳过无 delta 的帧；最终 `COMPLETED` 返回累计正文和最后一份 usage，不得把空 choices 归类为 `UNKNOWN`。
- GLM 启用思考时发送 `thinking: { type: "enabled" }`，`reasoning_effort` 保持顶层字段；Kimi 的 `reasoning_effort` 也保持顶层。禁用 GLM 思考使用 `thinking: { type: "disabled" }`。

## 2026-07-20 ZW-STABILITY-002 M10 千问设置与运行时链路

- 本轮不改变请求或响应 Schema。`PUT /api/settings/llm`、携内联 Key 的 `POST /api/settings/llm/test` 和凭据清除接口继续只允许桌面宿主；有效 capability 是桌面授权事实，开发态 Vite Origin 不再把真实 Tauri 误判为 Web。普通 Web 与伪造/缺失 capability 继续返回稳定的主机能力错误。
- 保存成功后，Provider 配置写入脱敏配置文件，API Key 写入该 Provider 独立的 Credential Store 条目；生产对话随后通过 `require_llm_config()` 读取同一已保存配置和凭据。保存失败不会改变运行时配置。
- 连接测试可以使用当前表单和内联 Key，因此测试成功不等于保存成功。桌面在测试配置与已保存配置不同时必须明确提示先保存；保存错误展示服务端原因并保留未保存的 Key。

## 2026-07-17 ZW-LLM-004 生成失败恢复

- `LLM_OUTPUT_INVALID` 表示 Provider 连续两次未给出完整 Schema，返回“重新生成 / 检查模型设置”；`LOCAL_OUTPUT_REJECTED` 表示结构虽然可解析但未通过当前工程上下文、代码、凭据、主机文件访问、专家权限或设备安全边界，明确原需求本身无需修改并只返回“按原需求重试”；`GENERATION_INTERRUPTED` 表示应用或 Sidecar 中断遗留生成，返回“继续生成 / 修改原需求”。当前智能工程师不因硬件机械尺寸、孔位或器件资料不完整返回 `LOCAL_OUTPUT_REJECTED`，这类事实留到后续工程验证。错误正文必须明确原需求是否已保留，不能只显示“请重试”。
- `PersistedChatRequest` 新增可选 `recoveryOfMessageId` 与 `recoveryLabel`。恢复必须创建新 turn，精确复用失败消息对应的用户文本、`projectExpertId` 和 `threadId`；不得复活旧流或重复提交已落库的结构化澄清事务。用户消息元数据持久化这两个字段，中央时间线用一条恢复事件代替重复显示整段需求。
- 桌面中央失败卡只执行白名单动作 `retry | revise_request | open_settings`。`revise_request` 只把原文放回项目草稿并聚焦输入框；`retry` 才发送请求。历史 `UNKNOWN + 上次生成被中断` 兼容映射为中断恢复界面。
- 智能工程师 `LOCAL_OUTPUT_REJECTED` 的桌面自动恢复继续复用既有 `retry` 白名单路径，发送 `recoveryOfMessageId=<失败消息>` 与固定 `recoveryLabel=已按原需求自动重试`；不增加新 API 字段。前端可采用更保守的自动次数，但服务端是费用与并发最终门禁。
- 服务端只有在 `recoveryLabel` 精确等于固定自动恢复标签时才进入门禁，并在创建新 turn 的同一 SQLite 连接上使用 `BEGIN IMMEDIATE` 原子认领。它验证来源助手消息、专家类型、原需求文本和恢复链；同一失败消息只能成功认领一次，跨窗口重复请求返回受控 `DUPLICATE_TURN`，恢复链达到三次返回 HTTP 429 `RATE_LIMITED`。次数从既有消息元数据计算，不增加数据库字段或 schema 版本。
- 启动恢复把遗留 `STREAMING` 消息归一化为 `FAILED + GENERATION_INTERRUPTED`。自由结构 CAD 使用专用 `DeclarativeGeometry` Schema 生成有界 primitives，再由本地 Runtime 封装 `FREEFORM_STRUCTURE cadDraft`，避免要求 Provider 同时填充整个通用专家输出而经常漏掉 `geometry`。

## 2026-07-16 ZW-LLM-003 结构化输出失败分层

- `complete_structured()` 分别记录 Provider 结构校验与本地工程/安全边界校验。无 JSON 或不满足 Pydantic Schema 的两次输出返回 `LLM_OUTPUT_INVALID`；结构有效但连续两次未通过本地确定性约束的输出返回 `LOCAL_OUTPUT_REJECTED`。两类失败都只保存脱敏诊断，不保存 Provider 原文。
- 普通“传感器、模块、安装、开孔、结构适配”等机械术语不构成硬件选型。只有明确推荐/替换器件、BOM、硬件/电气方案、`hardware_selection` 或代码草稿才启用自然语言硬件 grounding。
- `cadDraft.components` 不依赖自然语言重复器件名；其 grounding 证据是 Sidecar 已确认的 `hardwareId/profileId` 机械档案对。未知或未确认档案仍在本地边界拒绝。
- ExpertRuntime 中输出应用阶段的受控 `ValueError/RuntimeError` 归类为 `LOCAL_OUTPUT_REJECTED`，其他未预期异常归类为 `UNKNOWN`；只有 Provider JSON/Schema 失败可以显示云端结构无效文案。

## 2026-07-16 ZW-AGENT-006 Hardware-grounded Expert Output

- `ContextAssembler` 为三师和方案生成提供同一 `hardwareKnowledgePolicy`：优先级固定为 confirmed `preferred_project_hardware`、匹配的本地 ACTIVE `local_hardware_library`、最后才是 `missing_capability`。上下文同时保留受控组件摘要和 Hardware Skill Markdown；浏览器草稿、INVALID/ARCHIVED 包和库外模型猜测不能进入该优先级。
- 三师输出明确进行硬件选型、替换、BOM、电气方案或生成代码时，必须显式引用最高优先级中已评估的本地器件。若第一次结构化输出绕开项目已选/本地库，Sidecar 以受控校验错误触发既有一次修复重试；第二次仍不满足时返回 `LOCAL_OUTPUT_REJECTED`，不得把库外猜测持久化成回复或代码草稿。普通机械安装描述不按硬件选型处理。
- 用户已选器件不得被另一主控静默替换；本地库不足时保留已覆盖部分，并以 `uiPayload.type=hardware_selection` 只声明 `missingCapabilities`。Provider 仍不得决定 component ID、ACTIVE 状态、库存或兼容性结论。
- MicroPython 静态检查允许设备端只读 `open(path)`、`open(path, "r")` 与 `open(path, "rb")`（含等价文本/二进制只读模式）；动态 mode 和 `w/a/x/+` 等写入、追加、创建或更新模式继续失败。该代码只进入不可变草稿并由固定子进程做静态/语法检查，Sidecar 不导入或执行项目代码，因此这不授予云模型或代码对主机文件系统的访问权。

## 2026-07-15 ZW-AUTH-001 本机账号与访问门禁

认证数据使用独立 `<data_dir>/auth/zhangwen-auth.sqlite3`，其 `PRAGMA user_version=1`；项目数据库仍为
v25，账号门禁不改变项目包或项目 schema。

公开入口仅包括：

- `GET /api/health`
- `GET /api/health/desktop-capability`
- `GET /api/auth/status` → `{ hasAccounts: boolean }`
- `POST /api/auth/register` → `{ account, sessionToken, expiresAt }`（HTTP 201）
- `POST /api/auth/login` → `{ account, sessionToken, expiresAt }`

其余 `/api` 请求必须发送 `Authorization: Bearer <sessionToken>`；缺失会话返回
`401 AUTH_REQUIRED`，无效、已撤销或过期会话返回 `401 AUTH_SESSION_INVALID`。已登录接口为：

- `GET /api/auth/session` → `{ account, expiresAt }`
- `POST /api/auth/logout` → `{ loggedOut: true }`

`AuthAccount` 只包含 `id / username / displayName / createdAt`。注册用户名按不区分大小写唯一；密码和
会话 token 不得出现在账号响应、项目库、项目包、日志或 LLM 上下文。登录失败统一返回
`401 AUTH_CREDENTIALS_INVALID`，不暴露账号是否存在。`ZHANGWEN_AUTH_DISABLED=1` 只允许测试进程显式
使用，生产默认启用。

## 2026-07-15 ZW-UX-008 Analysis-first Project Hardware Update

本更新不增加数据库 schema；当前权威版本仍为 v25，项目硬件继续使用 `project_shared_facts`。

- `UpdateProjectHardwareRequest { selectedHardwareIds: string[] }`：最多 12 个非空、唯一组件 ID；空数组表示清空当前项目硬件选择。
- `PUT /api/projects/{projectId}/hardware`：加载最新 ACTIVE Hardware Skill 并执行 Rule Engine。未知、归档或 FAIL 返回 `422 PROJECT_VALIDATION_FAILED` 且不改变旧事实；成功返回 `{ workspace, selectedHardwareWarnings }`。
- 更新成功时，Repository 在单一事务中把旧 confirmed `field/key=preferred_hardware` 标为 `superseded` 并以 `supersededBy` 指向新 confirmed 事实；ContextAssembler 下一轮只读取最新事实。
- `ConversationResponseType.HARDWARE_SELECTION = "hardware_selection"`；payload 固定为 `{ type, summary, missingCapabilities }`。`missingCapabilities` 为 1-8 个非空、唯一能力名称，不接受 component ID、文件、命令、工具或任意附加字段。
- 中央 `hardware_selection` 卡片的操作只打开本地选择器，不追加用户消息。Provider 不选择器件；组件 ID、ACTIVE 状态、库存、Hardware Skill revision、Rule Engine 和事实写入均由本地链路决定。
- 新桌面 `POST /api/projects/suggest` 发送空 `selectedHardwareIds`，分析成功后才选择硬件；旧客户端字段仍兼容。`POST /api/projects` 继续携带最终选择并在写库前校验。

## 2026-07-14 ZW-UX-007 Hardware Intake and Component Package Update（历史兼容）

本更新不增加数据库 schema；当前权威版本仍为 v25。项目硬件初选复用 `project_shared_facts`，器件 Markdown 使用当前数据目录 overlay。

- `SuggestProjectRequest.selectedHardwareIds?: string[]` 与 `CreateProjectRequest.selectedHardwareIds?: string[]`：最多 12 个非空、唯一组件 ID；空数组表示由掌问按需求推荐，不等同于完整 BOM。
- `POST /api/projects/suggest` 和 `POST /api/projects` 都在 Provider/项目写入前重新加载 ACTIVE 组件并运行 Rule Engine。未知/归档或 `FAIL` 返回 `422 PROJECT_VALIDATION_FAILED`；`WARNING` 继续并作为服务端受控摘要进入路由、项目事实和后续上下文。
- 桌面硬件选择器在用户确认当前选择时调用 `POST /api/hardware/validate`，以返回的当前 `checks` 决定留在选择器、展示 WARNING 或允许继续；分析阶段发送空 `selectedHardwareIds`，其结果不得作为后来人工选择的校验结论。最终 `POST /api/projects` 仍再次校验，作为写入前权威边界。
- `SuggestProjectResponse.suggestion.selectedHardwareWarnings: string[]` 返回 Rule Engine 的中文非阻塞提醒；空数组表示没有 WARNING，桌面不得从 Provider `reason` 猜测硬件校验状态。
- 创建事务写 confirmed `preferred_hardware` SharedFact，值包含固定 policy、服务端解析的组件摘要和校验摘要。可见 kickoff 仍只包含原始创意，不增加隐藏硬件消息或第二条用户消息。
- EntryRouter、三师 ContextAssembler 和方案生成把已选器件作为优先复用基线；同一 component ID 不得作为新增项重复推荐，只补齐功能缺口。
- ZW-HW-001 已取代旧四文件写入模型。`GET /api/hardware/components/{componentId}/package` 仅把当前 ACTIVE Hardware Skill revision 映射为旧四文件响应；`PUT /api/hardware/components/{componentId}/package/files` 固定返回 `410 HARDWARE_COMPONENT_PACKAGE_READ_ONLY`。
- 旧 `<data_dir>/hardware-component-packages/` overlay 只在首次迁移时折叠进新 Skill，并保留为恢复证据；它不再是规则或三师上下文的写入入口。
- 桌面正式入口改为 `FloatingWindowKind.HARDWARE_SKILL` 和 `hardware-skill:{skillName}`。旧 `hardware-component` kind 只保留兼容，不再用于当前硬件知识编辑。

## 2026-07-14 ZW-UX-006 Real Chat Progress Update

项目专家对话新增服务端拥有的真实动作进度事件。`PROGRESS` 本身是请求内瞬态事件，不写入历史；为了让用户确认后的本地执行只能恢复到原回复和唯一 SkillRun，项目持久化版本升为 **v25**，新增私有 `skill_run_authorizations` 关联表：

- `StreamChunkType` 新增 `PROGRESS`；`StreamChunk` 新增可选 `progress?: ChatProgress`。
- 项目聊天 SSE 使用 `event: chat.progress` 承载 `type=PROGRESS` 的 chunk。服务端在进入 ExpertRuntime 前立即发送 `chat.started / START`，随后通过本地异步队列按实际执行顺序转发零到多个进度事件，最终仍以 `chat.completed`、`chat.error` 或 `chat.canceled` 结束。
- 进度只描述 Sidecar 已进入或已完成的真实阶段，不从 `reasoningContent`、模型正文或客户端计时推断，也不允许 Provider 自由生成动作或标签。
- `POST /api/projects/{projectId}/pending-items/{pendingItemId}/resolve/stream` 只接受通过桌面 capability 校验且存在 v25 授权关联的本地执行确认。旧 `/resolve` 对已绑定授权返回 `409 SKILL_AUTHORIZATION_STREAM_REQUIRED`；历史无关联 PendingItem 不能恢复或执行工具。
- `PendingItem` 对外新增稳定语义字段：普通事项返回 `kind=GENERAL`；存在 v25 授权关联时返回 `kind=LOCAL_EXECUTION_AUTHORIZATION`、`actionType=RESUME_SKILL_RUN` 和非空 `authorizationId`。这些字段由仓储联查关联表派生，标题与原因只作展示，客户端不得据此识别授权类型。
- `skill_run_authorizations` 以 `pending_item_id` 为主键、`skill_run_id` 为唯一键，并同时绑定 `project_id`。领取授权、把 SkillRun 切为 `RUNNING` 和关闭 PendingItem 在同一事务完成；重复确认不能执行第二次。缺少持久 request/response message 的 SkillRun 会失败关闭，不创建不可恢复的执行确认。

```ts
interface ChatProgress {
  id: string;
  action: ChatProgressAction;
  label: string;
  status: ChatProgressStatus;
  sequence: number;
}
```

`ChatProgressAction` 固定为：

- `CONTEXT_READ`
- `CLOUD_LLM_REQUEST`
- `OUTPUT_VALIDATE`
- `PROJECT_UPDATE`
- `CODE_DRAFT_SAVE`
- `CAD_DRAFT_SAVE`
- `LOCAL_EXECUTION_AUTHORIZATION`
- `LOCAL_TOOL_EXECUTION`

`ChatProgressStatus` 固定为 `RUNNING | COMPLETED | WAITING | FAILED`。`id` 是一次流内的稳定步骤标识，用于更新和去重；`sequence` 只用于排序。普通模式不得直接显示这两个字段或 `action` 枚举。`label` 必须由 Python Sidecar 根据 `action + status` 从固定中文白名单生成，TypeScript 客户端只能原样显示，不能接收或拼接模型自由文本、命令、路径、端口、payload、内部错误或硬件标识。

| `action` | `RUNNING` | `COMPLETED` | `WAITING` | `FAILED` |
|---|---|---|---|---|
| `CONTEXT_READ` | 正在读取项目上下文 | 已读取项目上下文 | 等待读取项目上下文 | 项目上下文读取受阻 |
| `CLOUD_LLM_REQUEST` | 正在请求云端 LLM | 已收到云端 LLM 回复 | 等待请求云端 LLM | 云端 LLM 请求受阻 |
| `OUTPUT_VALIDATE` | 正在校验模型输出 | 已校验模型输出 | 等待校验模型输出 | 模型输出校验受阻 |
| `PROJECT_UPDATE` | 正在更新项目状态 | 已更新项目状态 | 等待更新项目状态 | 项目状态更新受阻 |
| `CODE_DRAFT_SAVE` | 正在保存代码草稿 | 已保存代码草稿 | 等待保存代码草稿 | 代码草稿保存受阻 |
| `CAD_DRAFT_SAVE` | 正在保存结构草稿 | 已保存结构草稿 | 等待保存结构草稿 | 结构草稿保存受阻 |
| `LOCAL_EXECUTION_AUTHORIZATION` | 正在检查本地执行授权 | 已确认本地执行授权 | 等待本地执行授权 | 本地执行授权受阻 |
| `LOCAL_TOOL_EXECUTION` | 正在执行本地工具 | 已完成本地工具执行 | 等待本地工具执行 | 本地工具执行受阻 |

ExpertRuntime 只在真实进入上下文组装、云端请求、输出校验、项目状态更新、代码草稿保存或结构草稿保存时发出对应动作。SkillRuntime 返回 `AWAITING_CONFIRMATION` 时只发送 `LOCAL_EXECUTION_AUTHORIZATION + WAITING`，中文为“等待本地执行授权”；只有 ToolRunner 已把真实 `tool_run` 持久化为 `RUNNING` 后，才允许发送 `LOCAL_TOOL_EXECUTION + RUNNING`。终态可发送同一步骤的 `COMPLETED` 或清洗后的 `FAILED`，但 `label` 不得包含原始异常。

进度是当前请求的瞬态展示状态，不写入历史消息正文、`structuredPayload`、Artifact、PendingItem 或聊天持久化。v25 授权表只保存恢复与幂等关联，不保存动作时间线。终止、失败或取消时客户端必须停止运行态动画、清理当前动作并刷新授权事项；不支持 `chat.progress` 的旧服务端继续使用“{专家名}正在生成回复”三点动画。CAD Worker/CadJob 和设备异步操作继续使用各自的持久 Job/Operation 进度面，不得冒充 ExpertRuntime 当前对话动作。

## 2026-07-14 ZW-UX-006 Schema v25 Update

- SQLite `PRAGMA user_version` 是 `25`；Python 和 TypeScript `ProjectPersistenceVersion` 公开 `V25`，Workspace 返回 `schemaVersion: 25`。
- v25 只新增私有 `skill_run_authorizations` 授权恢复关联；不把 `ChatProgress`、命令、路径、payload、工具输出或原始错误写入该表。
- v24 的 CadJob、Artifact 文件和机械档案迁移保持不变，作为 v25 的前置版本继续向前迁移。

## 2026-07-13 ZW-CAD-001 Schema v24 Update

- This dated ZW-CAD-001 delta introduced SQLite v24 and `ProjectPersistenceVersion.V24`; the current authoritative workspace version is v25 as documented above.
- CAD uses a server-owned `CadDraft -> CadJob -> ArtifactVersion` flow. The old `/cad/generate` route is retained only as a side-effect-free HTTP 410 migration boundary.
- `/cad/jobs`, cancel, retry, confirm and reject require the desktop capability token. Web can read persisted summaries but cannot execute or approve local CAD.
- New CAD files are stored under `artifact_files` with SHA-256 metadata and streamed through the capability-protected Artifact file API. SQLite does not store CAD binary content.
- Mechanical profiles are immutable, revisioned records. The hardware API exposes their reviewed metadata and accepts only explicit `hardwareId -> profileId + revision` links. K10 unlink is locked, CAD resolution stays fixed to the built-in K10 profile, and the UI excludes K10 from remapping; the PUT route does not yet enforce the same remap guard and remains a documented residual risk.

## 2026-07-11 ZW-AGENT-003 Schema v23 Update

- SQLite `PRAGMA user_version` is `23`; Python and TypeScript `ProjectPersistenceVersion` expose `V23`, and workspace responses return `schemaVersion: 23`.
- Migration v23 rebuilds `code_runs` so `spec_run_id` is nullable. This lets a structured smart-engineer code reply or an explicit historical Python import create a CodeRun/ArtifactVersion before an approved Spec while preserving all existing rows, foreign keys, files, patches and indexes.
- No device, expert or parallel domain table is added. Device operations continue to use the existing v10 `device_sessions`/`device_operations` graph and `DEVICE_LOG` Artifact versions.

## 2026-07-19 ZW-AGENT-006 M25 Proposal/Spec/Code Flow Update

- Proposal persistence remains the fixed six `ProposalSection` rows. The UI and exports map them to a two-column “立项项 / 执行内容” table; no second proposal schema or table is introduced.
- Recommendation and proposal prompts have separate contracts: the recommendation records the selected direction and trade-offs; the proposal records delivery scope, implementation stages, schedule, risk and acceptance evidence and must not copy the recommendation prose.
- Confirming a formal project proposal generates the current Spec before returning the confirmation response. The response no longer instructs the desktop to synthesize a user-like smart-engineer handoff. Spec generation failure leaves the confirmed proposal auditable but does not create a fake Spec or code version.
- `ProjectSharedContext.deliveryTrack` is derived from the latest confirmed `delivery_track` SharedFact and is `project | lesson` (default `project`). Confirming a `VALIDATED` Spec from the central card calls `/code/generate` for `project`, or `/lesson/generate` for `lesson`, with that exact `specRunId`; the two outputs are mutually exclusive for that confirmation action.
- The code floating window has only “代码 / 变更” views. Its single “验证并接受代码” action calls `/code/validate`, inspects the returned `STATIC | SYNTAX` exit codes and calls `/code/accept` only when both are `0`. Validation failure never accepts code and never starts a device operation.
- `READY_FOR_REVIEW` code is no longer projected into the central confirmation card. Simple smart-engineer chat code without an approved proposal remains compatible with nullable `spec_run_id`; device upload still requires an accepted immutable CodeRun.

## 2026-07-20 ZW-AGENT-006 M28 Proposal/Floating/Handoff Update

- M28 supersedes the M25 automatic Proposal-to-Spec frontend flow: `confirm_project_proposal` confirms the current Proposal without calling Spec generation. Existing `/spec/*` APIs, tables and historical Artifact links remain readable and callable for compatibility.
- When the project already contains a non-removed `smart_engineer`, the `proposal_action` confirmation response includes an automatic handoff descriptor. The desktop switches to that existing expert and starts one new expert turn against the approved Proposal; the service does not silently add an expert.
- Smart-engineer structured `codeDraft` no longer has a formal-Project Spec gate. It may persist with nullable `spec_run_id`; local file, credential, host access, Board API, static/syntax and device-safety boundaries remain unchanged.
- `view_project_proposal` is a desktop-local Artifact action. The client opens `artifact_proposal_{projectId}` at `artifact_version_proposal_{proposalId}` in the existing floating layer and does not send another chat request, so no placeholder system notice is persisted in the central conversation.

## 2026-07-10 ZW-LLM-001 Required Provider Update

- `POST /api/projects/suggest` 始终调用配置的 DeepSeek Provider；`useModelRouting` 仅保留为旧客户端兼容字段，不能关闭模型路由。
- 桌面端只有在用户点击“分析并推荐”后才调用该接口；创意输入变化不得自动请求。成功结果只绑定当时的完整创意，后续编辑必须丢弃旧 `routerResult` 后重新调用。
- `POST /api/projects` 在请求缺少 `routerResult` 时由后端调用 EntryRouter；请求携带已有有效路由时可直接复用，用户手工选择的初始专家和参与专家仍优先。
- 所有结构化生成最多进行一次格式修复重试。两次输出均不满足 Pydantic Schema 时返回 `LLM_OUTPUT_INVALID`，不得生成本地模板结果。
- 缺少 Key 返回 `CONFIG_MISSING`；Provider 错误保留统一 `LLMError` 结构和可执行 `userActions`。
- `POST /api/projects/{projectId}/proposal/generate` 与 `/proposal/revise` 均调用 Provider，输出固定映射为 `project_overview`、`requirements`、`hardware_software_structure`、`implementation_plan`、`cost_difficulty_schedule`、`risks_acceptance` 六章节。
- 中央对话中的生成/修订立项书动作复用同一 Provider 服务；模型错误通过 `chat.error` 返回，不能创建新 Proposal 或 Proposal Artifact 版本。
- 方案卡同时提供 `confirm_solution_and_generate_project_proposal` 与 `confirm_solution_and_generate_lesson_version`；已确认方案对应 `generate_project_proposal` 与 `generate_lesson_version`。两条路线都在一次请求中确认方案、持久化 `delivery_track` 并调用同一 Proposal 生成服务；教案路线返回“教学实施基线”说明，后续仍需确认 Proposal 与 Spec。历史动作 `confirm_solution` 保持可解析并默认兼容为工程立项路线。
- `POST /api/projects/{projectId}/spec/generate` 调用 Provider 生成项目内容、硬件候选和 IO 建议；本地硬件库、Rule Engine 和 IO 引用检查决定验证结果，BOM 不由模型直接写入。
- `POST /api/projects/{projectId}/code/generate` 调用 Provider 生成以 `src/main.py` 为必需入口的动态 MicroPython 文件集；默认仅生成单文件，确需模块化时才允许平级 `src/*.py`。本地执行路径、敏感模式、Shell 能力和 Python AST 检查，不执行生成代码或 Shell。
- 当项目已选硬件或已确认 Spec BOM 精确包含掌控板 3.0 或行空板 K10 组件时，Code Agent 和智能工程师 `codeDraft` 注入对应的只读板级 API 契约。K10 契约同时描述 `unihiker_k10`、`k10_base`、构造对象、成员、调用签名、屏幕提交、按键/RGB 和 AI 初始化约束；`STATIC` 子进程据此拒绝跨板模块、旧版/虚构成员与错误签名，但不导入开发板模块、不执行用户代码，也不改变未匹配开发板的验证行为。
- Provider 结构化生成请求使用 DeepSeek `response_format={"type":"json_object"}`；JSON 可解析不等于工程有效，Pydantic Schema、代码文件边界、凭据/主机能力和板级 AST 仍在本地失败关闭。新结果继续只包含 `STATIC | SYNTAX`，不新增或恢复 `SIMULATION`。
- 旧的 `POST /api/projects/{projectId}/cad/generate` 仅作为历史客户端迁移边界，当前返回 HTTP 410 `CAD_LEGACY_ROUTE_DISABLED`，不调用 Provider、不创建 CAD 运行、也不执行本地文件操作。
- `POST /api/projects/{projectId}/lesson/generate` 调用 Provider 生成教师教案、学生任务单、评价量表和安全说明；本地固定四类 Markdown 路径并扫描凭据、真实串口标识和本机绝对路径。

## 2026-07-10 ZW-UX-004 Batch Clarification Update

### Project Conversation v22

- SQLite `PRAGMA user_version` is now `22`; `ProjectPersistenceVersion` exposes `V22` and workspace responses return `schemaVersion: 22`.
- `ConversationAnswerType` adds `BATCH = "batch"`.
- `StructuredQuestionAnswer` adds `ClarificationBatchAnswer`:

```ts
interface ClarificationBatchAnswer {
  type: "clarification_batch_answer";
  projectId: ProjectId;
  conversationId: ConversationId;
  sourceMessageId: MessageId;
  clientTurnId: string;
  answers: ClarificationAnswer[];
}
```

- Each `ClarificationAnswer` carries `questionId`, `selectedOptionIds`, optional `textInput`, and optional `usedRecommendation`.
- The desktop sends the batch through the existing `POST /api/projects/{projectId}/chat/stream` endpoint only after every pending `required=true` question from the source message is complete.
- The backend validates project, conversation, source message, turn id, duplicate question ids, required-question coverage, prior answers, answer mode, custom text and allowed options before inserting the turn or invoking a provider.
- Validation errors use `QUESTION_NOT_FOUND`, `QUESTION_ALREADY_ANSWERED`, `OPTION_NOT_ALLOWED`, `CLARIFICATION_INCOMPLETE`, `DUPLICATE_QUESTION_ANSWER`, `STALE_CONVERSATION_TURN`, `PROJECT_CONTEXT_MISMATCH`, and `DUPLICATE_TURN`.
- One batch creates one conversation turn and one user message, persists all answer records in the same repository transaction, and then invokes the problem-guide provider exactly once. Each answer can produce its own confirmed SharedFact, but coordinator update remains once per submitted turn.
- Provider failure does not remove committed answers. A retry regenerates only the assistant response and must not create duplicate answer records.
- Legacy `single_choice_answer`, `multiple_choice_answer`, `text_question_answer`, and legacy top-level answer fields remain readable for old clients and persisted history. The current desktop always uses the batch route for `questions[]`, including a one-question group.

### Schema v22 Migration

- Migration v22 rebuilds `clarification_answers` without the old unique constraint on `(project_id, conversation_id, client_turn_id)`, allowing one turn to own multiple answer rows.
- The unique constraint on `question_record_id` remains authoritative, so a question can still be answered only once.
- Existing answer rows are copied unchanged; repository migration backup and audit behavior remains required before mutation.

## 2026-07-09 ZW-UX-001 Conversation Context Binding Update

### Project Conversation v16

- SQLite `PRAGMA user_version` is now `16`.
- `ProjectPersistenceVersion` exposes `V16`.
- `messages` adds nullable `metadata_json` for persisted turn/question/action metadata.
- New persistence tables: `conversation_turns`, `clarification_questions`, and `clarification_answers`.
- `PersistedChatRequest` carries `clientTurnId`, `turnContext`, and `structuredAnswer` for every structured card answer or conversation action.
- `ConversationTurnContext` binds `projectId`, `conversationId`, `turnId`, optional parent/reply fields, current stage, current intent, active question, active solution, active proposal, and active Artifact.
- `ProjectStreamChunk` carries `requestTurnId` and `responseTurnId`; the desktop must ignore stream chunks whose `projectId`, `conversationId`, or `requestTurnId` does not match the active request.
- Structured clarification answers are persisted as `single_choice_answer`, `multiple_choice_answer`, or `text_question_answer`; the backend validates question ownership, option validity, duplicate answers, project/conversation mismatch, and duplicate `clientTurnId` before calling any LLM/provider path.
- Conversation context errors use `QUESTION_NOT_FOUND`, `QUESTION_ALREADY_ANSWERED`, `OPTION_NOT_ALLOWED`, `STALE_CONVERSATION_TURN`, `PROJECT_CONTEXT_MISMATCH`, and `DUPLICATE_TURN`.

### UX-001 Chat Flow Rules

- Option cards submit structured answers through the same project chat stream endpoint and also render a natural user message in history.
- Generated or revised implementation solutions insert a structured `solution_card` chat payload and synchronize the same solution version into the Artifact system.
- Natural-language solution changes in solution stages revise the current solution version incrementally and do not automatically generate or update proposals.
- The Work tab is a project overview: current stage, one current user item, current solution, latest three Artifacts, and simplified progress. It is not the full Artifact archive.
- At the ZW-UX-001 baseline, device discovery was Sidecar-owned and scan-only. ZW-AGENT-003 later adds confirmation-gated desktop operations; discovery itself still never auto-connects, uploads, flashes, or erases Flash.

## 2026-07-09 Solution Revision, Solution Card, and Artifact Sync Update

### Project Conversation v15

- SQLite `PRAGMA user_version` is now `15`.
- `ProjectPersistenceVersion` exposes `V15`.
- `ConversationResponse` adds `solution_card` for structured implementation-solution cards in normal chat messages.
- `SolutionVersion` adds `basedOnVersion`, `changeSummary`, `artifactId`, and `artifactVersionId`.
- New shared contracts: `SolutionCardMessage`, `SolutionCardSection`, `SolutionSectionChange`, `SolutionRevision`, `ReviseSolutionRequest`, `ReviseSolutionResponse`, and `RestoreSolutionResponse`.

### Solution Revision API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/projects/{projectId}/solution/revise` | Create a new draft solution version from the current solution and a targeted user instruction |
| `POST` | `/api/projects/{projectId}/solution/restore-previous` | Restore the previous base version while preserving the rejected revision history |

Revision responses include the revised solution, changed sections, preserved section IDs/titles, impact summary, and `requiresProposalUpdate`. Revision never overwrites the base solution and never generates or updates a proposal automatically.

### Chat and Artifact Rules

- Project chat routes natural-language solution changes in `SOLUTION_DRAFT` or `SOLUTION_CONFIRMED` through the solution revision path.
- Solution generation and revision insert a `solution_card` chat payload instead of plain long Markdown.
- Every generated or revised implementation solution is synchronized into the Artifact system as the stable `implementation_solution`/solution Artifact for the project.
- Chat solution cards and right-side Artifact records reference the same `solutionId`, `artifactId`, and `artifactVersionId`.
- Proposal generation remains explicitly user-triggered. Revising a solution marks dependent proposals stale/outdated but does not regenerate them.

## 2026-07-09 Post-ZW-016 Desktop Conversation and Serial Scan Update

### Project Conversation v14

- SQLite `PRAGMA user_version` is now `14`.
- `ProjectPersistenceVersion` exposes `V14`.
- `messages` adds nullable `structured_payload_json`.
- `ChatMessage.structuredPayload?: ConversationResponse | null`.
- `StreamChunk.structuredPayload?: ConversationResponse | null`.
- `PersistedChatRequest` adds optional `conversationAction`, `sourceMessageId`, `questionId`, `selectedOptionIds`, and `textInput`.

`ConversationResponse` is a discriminated union:

- `clarification`: short summary, one `ConversationClarificationQuestion`, completeness.
- `next_action`: message plus `ConversationAction[]`.
- `solution`: solution summary, solution id/version, follow-up actions.
- `proposal_action`: proposal summary or gate notice, proposal id/version, follow-up actions.
- `system_notice`: short info/warning/error notice and optional actions.

IDEA and early solution/proposal actions are now driven by `/api/projects/{projectId}/chat/stream`. The frontend renders structured payloads inside normal chat messages and persists clicks as user messages through the same project chat endpoint. Top-level central toolbar actions for clarification and solution generation are no longer part of the contract.

### Device Port Scan

`GET /api/projects/{projectId}/devices/ports` now scans host serial ports through the Python Sidecar. The frontend must not access serial APIs or shell directly.

`ListDevicePortsResponse` includes `ports`, `scannedAt`, and `count`.

`DevicePort` now includes real serial metadata while retaining existing dry-run compatibility fields: `portName`, `portType`, `description`, `manufacturer`, `product`, `vid`, `pid`, `serialNumber`, `likelyBoard`, `status`, plus existing `id`, `label`, `transport`, `chip`, and `available`.

Scan errors use HTTP error detail codes such as `SERIAL_SERVICE_UNAVAILABLE`, `SERIAL_SYSTEM_API_FAILED`, `SERIAL_PERMISSION_DENIED`, and `SERIAL_SCAN_UNKNOWN`.

## 原则

- 契约先于实现。
- 所有枚举在 `packages/contracts` 统一生成 TypeScript 与 Python 类型。
- 错误必须包含用户可执行动作。
- 长任务返回稳定的 task/operation ID。设备操作通过现有 `DeviceOperation.id` HTTP 轮询；其他采用事件流的领域继续遵循各自既有契约。

## ZW-003 Project and Conversation Persistence API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects` | List non-archived projects and return activeProjectId; `includeArchived=true` also returns archived projects |
| `POST` | `/api/projects` | Create a local project with conversation and draft records |
| `GET` | `/api/projects/{projectId}` | Load a project workspace: project, messages, draft |
| `POST` | `/api/projects/{projectId}/open` | Open a project and update recent project metadata |
| `POST` | `/api/projects/{projectId}/experts` | Add or restore one canonical expert workspace for this project; `activate=true` also selects it as the active reply target |
| `POST` | `/api/projects/{projectId}/experts/{projectExpertId}/remove` | Soft-remove a project expert while preserving its thread, memory and artifacts |
| `PATCH` | `/api/projects/{projectId}` | Update project name or selected model |
| `POST` | `/api/projects/{projectId}/archive` | Soft-archive a project, retaining its messages, draft and Artifacts |
| `POST` | `/api/projects/{projectId}/restore` | Restore a soft-archived project |
| `PUT` | `/api/projects/{projectId}/draft` | Save the project draft |
| `POST` | `/api/projects/{projectId}/chat/stream` | Send a project message and stream a persisted assistant reply |
| `POST` | `/api/projects/{projectId}/chat/cancel/{requestId}` | Cancel a project chat request |

### ProjectStreamChunk

ZW-003 reuses the ZW-002 SSE event names and adds project context to `StreamChunk`:

```ts
export interface ProjectStreamChunk extends StreamChunk {
  projectId: ProjectId;
  conversationId: ConversationId;
  userMessageId?: MessageId;
}
```

Events:

- `chat.started`
- `chat.delta`
- `chat.completed`
- `chat.error`
- `chat.canceled`

Each event must include `requestId`, `messageId`, `projectId`, and `conversationId`. The frontend must ignore chunks that do not match the active project/request.

### Project creation kickoff

- `POST /api/projects` persists the submitted `initialIdea` exactly once as the first user message and creates one stable `READY` kickoff turn plus an empty assistant placeholder in the selected expert conversation. `ProjectWorkspace.kickoff` identifies that turn; the create route does not synthesize an assistant answer.
- The desktop claims a `READY` kickoff through the existing project chat stream by sending `kickoffTurnId`. The request must match the persisted project, conversation, expert, user content and client turn ID; the backend reuses the existing user/assistant messages and must not append the idea again.
- A completed kickoff is replayable without another Provider call. A pending or streaming kickoff is not claimable twice. A failed or canceled kickoff is retried only with `retryKickoff: true`, still reusing the same persisted messages.
- Creation and kickoff idempotency are separate. Repeating a creation key returns the same project, while kickoff claims and retries use the stable persisted turn and never append the idea again.

### Project Events

Shared Contracts define these project events. ZW-003 uses HTTP responses as the authoritative state source and does not add a WebSocket event bus.

- `project.created`
- `project.updated`
- `project.archived`
- `project.opened`
- `conversation.message.created`
- `conversation.message.updated`
- `draft.updated`

### Project Error Codes

Project APIs return `ZwError` shaped responses with user-actionable Chinese messages. Current implementation covers:

- `PROJECT_NOT_FOUND`
- `PROJECT_ARCHIVED`
- `PROJECT_NAME_REQUIRED`
- `PROJECT_NAME_TOO_LONG`
- `PROJECT_VALIDATION_FAILED`
- `MESSAGE_EMPTY`
- `PROJECT_SCHEMA_UNSUPPORTED`
- `PROJECT_DATABASE_CORRUPT`
- `PERSISTENCE_READ_FAILED`
- `PERSISTENCE_WRITE_FAILED`

### Security

- Project SQLite data must not store API Key, masked API Key, Authorization headers, or provider secrets.
- API Key remains in Windows Credential Manager.
- Frontend does not read/write the project DB and does not call DeepSeek directly.

## ZW-005 Hardware Library and Rule Engine API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/hardware` | List active shared-knowledge components, optionally filtered by `category`; `search` matches name, notes, electrical/protocol JSON and safety tags |
| `GET` | `/api/hardware/{componentId}` | Load one hardware component |
| `POST` | `/api/hardware` | Create a shared component-knowledge entry used by all three experts |
| `PUT` | `/api/hardware/{componentId}` | Update a shared component-knowledge entry; subsequent relevant expert contexts read the latest row |
| `DELETE` | `/api/hardware/{componentId}` | Archive a hardware component without deleting history |
| `POST` | `/api/hardware/validate` | Run deterministic compatibility checks for selected component IDs |
| `GET` | `/api/hardware/components/{componentId}/package` | Read-only legacy mapping of the current ACTIVE Hardware Skill revision to four historical paths |
| `PUT` | `/api/hardware/components/{componentId}/package/files` | Always return 410 `HARDWARE_COMPONENT_PACKAGE_READ_ONLY` |
| `GET` | `/api/hardware/board-profiles` | List effective Markdown BoardProfile summaries without file-system paths |
| `GET` | `/api/hardware/board-profiles/{profileId}` | Load the effective bundled or overlaid BoardProfile Markdown |
| `PUT` | `/api/hardware/board-profiles/{profileId}` | Atomically save a data-directory overlay using `expectedRevision` |
| `POST` | `/api/hardware/board-profiles/{profileId}/reset` | Remove an overlay and restore the bundled profile using `expectedRevision` |

### Hardware Validation

`POST /api/hardware/validate` accepts `ValidateCombinationRequest` and returns `ValidateCombinationResponse`.
The rule engine reports `ValidationSeverity` values from shared contracts: `PASS`, `WARNING`, and `FAIL`.

Covered MVP dimensions:

- `component_exists`
- `component_status`
- `mcu`
- `voltage`
- `logic_level`
- `current`
- `i2c_address`
- `bus`
- `mcu_support`
- `firmware`

`HardwareElectricalProps` 中的供电字段具有固定且不同的语义：

- `voltage` 是推荐或标称工作点；`voltageMin/voltageMax` 是器件可接受的连续供电范围。旧 Skill 未声明范围时，范围退化为单点 `voltage`。
- `supplyVoltages` 是 MCU/POWER 对外提供的离散外设电源轨，例如 K10 的 `[3.3, 5.0]`；普通传感器不得用它表示连续工作范围。
- `range-overlap` 校验 `electrical.voltage` 时，从主控电源轨中选择落入器件范围且最接近推荐点的电源轨。范围内但偏离推荐点返回 `WARNING`；没有可用轨返回 `FAIL`。
- `logic_level` 始终独立校验。供电兼容不能证明数字输出或模拟输出对主控 3.3V GPIO/ADC 安全。

### Hardware Component Package Markdown

- This surface is read-only compatibility after ZW-HW-001. `HardwareComponentPackageResponse` maps the current Skill revision into `README.md`, `docs/specifications.md`, `docs/integration.md` and `docs/safety.md`; responses never expose host paths.
- `PUT` no longer accepts edits and always returns HTTP 410 `HARDWARE_COMPONENT_PACKAGE_READ_ONLY`. Clients must use `/api/hardware/skills/{skillName}/files` and the eight-file Hardware Skill project.
- Missing/archived components return `HARDWARE_COMPONENT_PACKAGE_NOT_FOUND`; an invalid active package fails closed with `HARDWARE_COMPONENT_PACKAGE_INVALID`.

### BoardProfile Markdown

- The bundled catalog currently contains `unihiker-k10`. List responses expose metadata and revision only; detail responses add the effective Markdown `content`. Neither response exposes an absolute host path.
- `BoardProfileSummary` contains `id`, `displayName`, `aliases`, `platform`, `language: "micropython"`, `overridden`, a content-derived `revision`, and an optional validated `skillPackage` summary. `BoardProfile` adds `content`.
- Markdown must be UTF-8, at most 60,000 characters, contain non-empty body text and begin with frontmatter containing exactly `id`, `name`, `aliases`, `platform` and `language`. The ID cannot change and the language must remain `micropython`.
- Bundled files remain read-only. `PUT` writes an atomic overlay below the active data directory; reset removes only that overlay. Both mutations use compare-and-swap semantics through `expectedRevision`.
- BoardProfile overlays are file-backed and add no database table or schema migration.
- Stale revisions return HTTP 409 `BOARD_PROFILE_CONFLICT` with `retryable: true`. Missing profiles return 404 `BOARD_PROFILE_NOT_FOUND`; invalid Markdown or identity changes return 422 `BOARD_PROFILE_INVALID`.
- Context assembly matches board aliases in the user request and injects the effective overlay revision plus bounded Markdown as `publicKnowledge`. A request for another board does not receive the K10 document.
- The bundled K10 profile is bound to the read-only `unihiker-k10-micropython-engineer` package under the hardware module. Loading validates every manifest path, byte size and SHA-256 before exposing only ID, version, target/runtime, reference/template/example counts, validation flags and a content revision; no host path is serialized.
- For a matched K10 smart-engineer request, context assembly adds bounded `boardSkill` instructions plus query-selected references and code templates from the validated package. Other boards and other experts receive no K10 Skill content. Package text is generation guidance only and cannot grant file, shell, serial, upload or firmware permissions.

### Solution Generation Gate

`GenerateSolutionRequest` accepts optional `componentIds`. When present, `/api/projects/{projectId}/solution/generate` runs hardware validation before reading LLM configuration or invoking DeepSeek.
If validation has any `FAIL`, the API returns HTTP 422 with code `HARDWARE_VALIDATION_FAILED` and does not call the LLM.

### Persistence

SQLite `PRAGMA user_version` is now `4`. `ProjectPersistenceVersion` exposes `V1`, `V2`, `V3`, and `V4`; project workspace responses return `schemaVersion: 4`.

## ZW-006 Proposal Workflow API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/proposal` | List proposal versions for a project, newest first |
| `GET` | `/api/projects/{projectId}/proposal/current` | Load the newest non-superseded proposal |
| `POST` | `/api/projects/{projectId}/proposal/generate` | Generate a proposal draft from a confirmed solution |
| `POST` | `/api/projects/{projectId}/proposal/revise` | Create a new proposal draft version from an existing proposal and revision note |
| `POST` | `/api/projects/{projectId}/proposal/confirm` | Mark a proposal as approved and move the project to `PROPOSAL_CONFIRMED` |
| `POST` | `/api/projects/{projectId}/proposal/reject` | Mark a proposal as rejected and return the project to `SOLUTION_CONFIRMED` |
| `GET` | `/api/projects/{projectId}/proposal/{proposalId}/export?format=MARKDOWN|DOCX|PDF` | Export proposal content |

### Proposal Contracts

- `ProposalStatus`: `DRAFT | APPROVED | REJECTED | STALE | SUPERSEDED`
- `ProposalExportFormat`: `MARKDOWN | DOCX | PDF`
- `ProposalVersion`: `id`, `projectId`, `solutionId`, `solutionVersion`, `version`, `status`, `sections`, `createdAt`, `updatedAt`, `confirmedAt`, `staleReason`
- `ProposalSection`: `id`, `title`, `content`

### Proposal Rules

- `/proposal/generate` requires the referenced solution to be `CONFIRMED`; otherwise it returns HTTP 422 with `PROPOSAL_REQUIRES_CONFIRMED_SOLUTION`.
- Proposal export is generated by the Sidecar and does not include API keys, tokens, local absolute paths, or credential material.
- Generating a new solution marks existing DRAFT and APPROVED proposals for that project as `STALE`.
- The frontend displays proposal artifacts in the right "产物" tab and previews full content in a floating window; it does not replace `MainConversation`.

### Persistence

SQLite v4 adds `proposals`. The table stores sections as JSON, version metadata, status, stale reason, timestamps, and the linked solution ID/version. It does not store provider credentials.

## ZW-007 Orchestrator and Agent Registry API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/agents` | List built-in Agent definitions and capabilities |
| `GET` | `/api/projects/{projectId}/execution-plan/current` | Load the latest execution plan for a project |
| `POST` | `/api/projects/{projectId}/execution-plan` | Create an execution plan from an approved proposal |
| `POST` | `/api/projects/{projectId}/execution-plan/{planId}/start` | Start deterministic Mock Agent execution |
| `POST` | `/api/projects/{projectId}/execution-plan/{planId}/pause` | Pause a running or waiting execution plan |
| `POST` | `/api/projects/{projectId}/execution-plan/{planId}/resume` | Resume a paused execution plan |
| `POST` | `/api/projects/{projectId}/execution-plan/{planId}/retry` | Retry a failed task node |
| `POST` | `/api/projects/{projectId}/execution-plan/{planId}/approve` | Approve or reject a user confirmation node |

### Orchestrator Contracts

- `AgentCapability`: `ORCHESTRATE | SPEC | CODE | CAD | DEPLOY | PUBLISH | LESSON | REVIEW`
- `AgentDefinition`: `id`, `name`, `description`, `capabilities`, `enabled`, `builtIn`
- `ExecutionPlan`: `id`, `projectId`, `proposalId`, `status`, `nodes`, timestamps
- `TaskNode`: `id`, `planId`, `projectId`, `agentId`, `title`, `description`, `status`, `dependencies`, retry counters, approval flag, logs, timestamps, `error`

### Orchestrator Rules

- Execution plans require an `APPROVED` proposal; drafts and stale proposals return HTTP 422.
- ZW-007 uses Mock Agent execution only. It does not execute shell, file writes, serial operations, firmware actions, CAD Python, or paid LLM calls.
- User confirmation nodes use `AWAITING_APPROVAL`; rejection marks the node and plan as `FAILED`, and retry re-enters approval.
- The frontend displays a compact work-plan summary in the right "工作" tab and does not replace the central conversation.

### Persistence

SQLite v5 adds `execution_plans` and `task_nodes`. Project workspace responses return `schemaVersion: 5`.

## ZW-008 Skill Registry and Model Router API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/skills` | List built-in and user-defined Skill definitions |
| `POST` | `/api/skills` | Create a user-defined Skill with explicit permissions |
| `PATCH` | `/api/skills/{skillId}` | Enable/disable a user Skill or update permissions |
| `POST` | `/api/model-router/route` | Preview deterministic provider-neutral model routing |

### Skill Contracts

- `SkillOrigin`: `BUILT_IN | USER`
- `SkillPermission`: `READ_PROJECT | WRITE_ARTIFACT | RUN_MODEL | USE_DEVICE | RUN_CAD | RUN_SHELL`
- `ModelRouteStrategy`: `BALANCED | COST_FIRST | QUALITY_FIRST | FAST_FIRST`
- `SkillDefinition`: `id`, `name`, `description`, `origin`, `enabled`, input/output schemas, `permissions`, timestamps
- `ModelRouteResult`: `provider`, `model`, `strategy`, `retryCount`, `fallbackModel`, `costTier`, `qualityTier`, `reasoning`

### Skill and Router Rules

- User-defined Skills default to no permissions; `RUN_SHELL` is never granted implicitly.
- ZW-008 routes only to the currently supported DeepSeek models: `deepseek-v4-flash` and `deepseek-v4-pro`.
- The route API records an audit row but does not call a real paid LLM.
- Normal mode hides Skill/model/tool details. Professional mode in the right "工作" tab shows Skill count, high-risk permission summary, and model route preview.

### Persistence

SQLite v6 adds `user_skills` and `model_route_audit`. Project workspace responses return `schemaVersion: 6`.

## ZW-AGENT-001 Agent Skill Package API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/agent-packages` | List summaries for the fixed three visible agents |
| `GET` | `/api/agent-packages/{expertType}` | Load the effective manifest summary and editable Markdown files |
| `PUT` | `/api/agent-packages/{expertType}/files` | Validate and atomically save one allowlisted Markdown overlay using the current revision |
| `POST` | `/api/agent-packages/{expertType}/files/reset` | Delete one file overlay and return the effective bundled default |

The detail response exposes only logical relative paths, never host absolute paths. Save/reset requests require the last observed package revision; stale revisions return a conflict response. Only manifest-declared Markdown is writable. Identity, Skill bindings, permissions, artifacts and capability boundaries remain system locked.

Agent package overlays live beside the active data directory and do not add SQLite tables. The nullable CodeRun Spec change entered at schema v23 and the CAD migration raised that historical baseline to v24; the current authoritative project workspace is schema v25. These behavior files are separate from `/api/skills` Registry Skill definitions and cannot grant execution permissions.

## ZW-HW-001 Hardware Skill API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/hardware/skills` | List ACTIVE Hardware Skill summaries and diagnostics |
| `POST` | `/api/hardware/catalog/refresh` | Explicitly perform a full validation scan and atomically replace the persisted ACTIVE catalog index |
| `GET` | `/api/hardware/skills/{skillName}` | Load the effective file tree, compiled electrical specification, declarative rules and optional derived mechanical profile |
| `GET` | `/api/hardware/skills/{skillName}/media/{assetName}` | Read one manifest-allowlisted local image through the authenticated Sidecar boundary |
| `PUT` | `/api/hardware/skills/{skillName}/files` | Validate and atomically save one allowlisted text file using package revision CAS |
| `PUT` | `/api/hardware/skills/{skillName}/files/batch` | Validate and atomically save allowlisted Markdown/Python reference files, then sync electrical and mechanical projections in one transaction |
| `POST` | `/api/hardware/skills/drafts` | Create a DRAFT from bounded uploaded/extracted text or initial dialogue |
| `POST` | `/api/hardware/skills/drafts/{draftId}/messages` | Add one bounded user answer and rebuild the draft revision |
| `POST` | `/api/hardware/skills/drafts/{draftId}/confirm` | Confirm a valid draft, atomically publish ACTIVE and sync the SQLite projection |
| `DELETE` | `/api/hardware/skills/drafts/{draftId}` | Discard an unpublished draft |

`HardwareSkillStatus` is `DRAFT | ACTIVE | ARCHIVED | INVALID`; source kind is `BUNDLED | MIGRATED | UPLOAD | DIALOGUE | MANUAL`. The public library lists only ACTIVE packages: DRAFT lives in the creation session and archived packages are omitted. `GET /api/hardware/skills` validates packages independently, omits an uncompilable package and continues returning the remaining valid catalog; directly opening, editing or selecting that package fails closed with a controlled 422. A revision mismatch is never auto-trusted or injected into rules or context.

The ACTIVE catalog is a versioned index under the Sidecar data directory. If the index is absent, the first catalog read performs one full validation scan and writes it atomically. Later list/context reads use the persisted summaries and media metadata; selecting one hardware item still validates and loads that package in full. Skill update events only mark the desktop catalog stale. No automatic rescan is allowed; the user explicitly invokes `POST /api/hardware/catalog/refresh` from the refresh button.

Machine-readable blocks are explicit and versioned:

- specification fence `zhangwen:hardware-spec:v1`, payload schema `zhangwen.hardware-skill/v1`;
- rules fence `zhangwen:hardware-rules:v1`, payload schema `zhangwen.hardware-rules/v1`;
- validation fence `zhangwen:hardware-validation:v1`, payload schema `zhangwen.hardware-validation/v1`.
- optional mechanical fence `zhangwen:hardware-mechanical:v1`, payload schema `zhangwen.hardware-mechanical/v1`; it must be paired with `models/cadquery.py`, whose normalized UTF-8 SHA-256 must match and whose execution policy is fixed to `REFERENCE_ONLY`.

Rule operators are limited to `range-overlap | sum-lte | unique | contains-any | required-if`. A saved Skill file is at most 80,000 UTF-8 bytes and all manifest-declared text at most 300,000 bytes. Draft creation accepts at most eight sources: each text source is at most 512 KiB and all sources together at most 1.5 MB; one PDF is at most 2 MB and 50 pages, with at most 200,000 extracted characters. PDF arrives as bounded base64 and is parsed locally with `pypdf`; scanned PDFs are not OCRed and produce a blocking diagnostic when no text can be extracted.

All paths are logical POSIX-relative paths. Requests never carry a host path. A draft is stored as `<data_dir>/.hardware-skill-drafts/{draftId}.json` session state plus an API file-tree preview; no formal Skill directory exists until confirmation. A draft is not visible to `/api/hardware`, project selection, Rule Engine or ContextAssembler until local compilation succeeds and the user confirms it. Existing `/api/hardware` and `/api/hardware/validate` remain compatibility APIs, but their response and validation input are projections compiled from ACTIVE Hardware Skill Markdown. Cloud model output never grants file or rule-execution authority.

Hardware Skill 项目编辑器必须使用批量保存接口提交当前所有脏文件；整包在内存中完成白名单、结构块、规则、模型 SHA/Python 语法和敏感内容校验后才原子替换目录，并在同一事务同步 `hardware_components` 与机械档案精确关联。任一文件失败时目录和两类投影一起回滚。成功响应中的 detail 是应用和下一轮三师上下文的新真值，已挂载的硬件知识库与机械档案面板必须立即刷新。

硬件列表和项目硬件校验必须一致地使用可验证的 ACTIVE Skill。损坏或旧格式目录只隔离自身，不能让整个列表请求失败，也不能让其他有效 Skill 在加入项目时误报 `PROJECT_VALIDATION_FAILED`；该包的直接读取仍返回可定位的校验错误，不能静默修补或伪装成 ACTIVE。

旧格式目录若仍包含全部当前白名单文件，且其资料版本更新或验证等级更高，可在完整安全校验后原子同步到同 componentId 的有效后继 Skill；旧目录及额外文件不得删除。导入内容中的扩展声明式规则若超出当前字段/参数白名单，必须从机器规则集中移除并保留为可见人工检查项，不能静默执行。

`manifest.json.media[]` contains `path / role / alt / contentType / sha256 / sourceUrl / attribution / license`. Images are display-only: engineering parameters and rules remain Markdown authority. Paths are limited to one filename below `assets/`; types are JPEG/PNG/WebP, at most 2 MiB each, 6 files and 8 MiB total. The compiler verifies extension, magic bytes, declared MIME, HTTPS source and SHA-256 before the asset enters revision. Media responses use `Cache-Control: private`, `ETag`, `nosniff` and the same Bearer session as other business APIs; clients fetch a Blob instead of anonymous `<img src>` hotlinking.

The production seed now creates only `hw_seed_unihiker_k10`. The explicitly retired 12 sample `hw_seed_*` rows are removed from the active projection; matching `MIGRATED/BUNDLED` directories are moved below `<data_dir>/retired-hardware-seeds` for recovery. User `UPLOAD/DIALOGUE/MANUAL` packages and project history are outside this cleanup boundary.

## ZW-009 Artifact and Floating Window System API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/artifacts` | List versioned artifacts for a project, newest first by artifact update time |
| `GET` | `/api/projects/{projectId}/artifacts/{artifactId}` | Load one artifact with all versions, dependencies and preview metadata |

### Artifact Contracts

- `ArtifactKind`: `DOCUMENT | CODE | IMAGE | MODEL_3D | DEVICE_LOG | PACKAGE | REPORT`
- `ArtifactPreviewKind`: `DOCUMENT | CODE | IMAGE | MODEL_3D | TEXT`
- `FloatingWindowKind`: `document | code | model3d | image | terminal | web-preview | hardware-component | hardware-skill | agent-package`
- `ArtifactDefinition`: stable artifact ID, project ID, title, kind, status, source Agent, current version ID, versions, timestamps.
- `ArtifactVersion`: version ID, version number, status, MIME type, preview, dependencies, producer task/source entity, checksum, stale reason and timestamps.
- `ArtifactDependency`: upstream artifact or source reference with label, version and status.
- `FloatingWindowSpec`: window ID, kind, title, artifact/version IDs, singleton key, initial bounds, z-index and minimized/maximized state.

### Artifact and Window Rules

- Proposal records remain in the ZW-006 proposal table, and each proposal version is also synchronized into the Artifact system as a `DOCUMENT` artifact.
- Proposal revision, confirmation, rejection and stale transitions update the corresponding artifact version and top-level artifact status.
- The frontend reads the right "产物" tab from `/artifacts`; proposal export links remain proposal-specific.
- Floating windows are frontend-managed with a maximum of 3 open windows. The same `singletonKey` opens only one instance.
- Opening, closing, minimizing or maximizing a floating window must not unmount `MainConversation` or clear the active draft.
- MVP stores artifact preview content in SQLite JSON/text. Real file-backed artifacts are left to later Agent/tool stages.

### Persistence

SQLite v7 adds `artifacts`, `artifact_versions` and `floating_window_states`. Project workspace responses return `schemaVersion: 7`.

## ZW-010 Spec Agent API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/spec/current` | Load the latest Spec run for a project |
| `POST` | `/api/projects/{projectId}/spec/generate` | Generate deterministic Spec YAML files from an approved proposal |
| `POST` | `/api/projects/{projectId}/spec/confirm` | Mark a validated Spec as approved and stale downstream Code/CAD/Deploy artifacts |
| `POST` | `/api/projects/{projectId}/spec/reject` | Reject a Spec with an optional reason |

### Spec Contracts

- `SpecFileKind`: `PROJECT_SPEC | BOM | IO_MAP`
- `SpecRunStatus`: `DRAFT | VALIDATED | APPROVED | REJECTED | STALE | FAILED`
- `SpecValidationCheck`: validation dimension, severity, message and details.
- `SpecValidation`: `ok` plus ordered checks.
- `SpecFile`: stable file ID, Spec run ID, project ID, kind, YAML path, MIME type, content and linked Artifact IDs.
- `SpecRun`: Spec run ID, project/proposal IDs, version, status, files, validation, stale reason and timestamps.
- `GenerateSpecRequest`: `proposalId`
- `ConfirmSpecRequest`: `specRunId`
- `RejectSpecRequest`: `specRunId`, optional `reason`

### Spec Rules

- `/spec/generate` requires an `APPROVED` proposal; otherwise it returns HTTP 422 with `SPEC_REQUIRES_APPROVED_PROPOSAL`.
- ZW-010 uses a deterministic Mock Spec Agent. It does not call a real paid LLM and does not write project workspace files.
- The generator emits `spec/project_spec.yaml`, `spec/bom.yaml` and `spec/io_map.yaml`.
- IO and hardware consistency is checked through the existing hardware rule boundary before the Spec is marked `VALIDATED`.
- Spec YAML files are synchronized as `DOCUMENT` artifacts with code-style YAML previews, dependencies on the source proposal, and source Agent `spec-agent`.
- Confirming a Spec marks existing downstream `code-agent`, `cad-agent` and `deploy-agent` artifacts as `STALE`.
- The frontend exposes Spec status/actions in the right "工作" tab and previews YAML through the existing "产物" tab/floating window system. It does not replace `MainConversation`.

### Persistence

SQLite v8 adds `spec_runs` and `spec_files`. Project workspace responses return `schemaVersion: 8`.

## ZW-011 Code Agent API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/code/current` | Load the latest Code Agent run for a project |
| `GET` | `/api/projects/{projectId}/code/{codeRunId}` | Load one retained CodeRun version and its immutable file contents |
| `PUT` | `/api/projects/{projectId}/code/{codeRunId}` | Save edited files and a change summary as a new CodeRun/ArtifactVersion |
| `POST` | `/api/projects/{projectId}/code/validate` | Run controlled local MicroPython static and syntax checks for the current version; user code is not executed |
| `POST` | `/api/projects/{projectId}/code/import-message` | Explicitly import fenced Python from one completed smart-engineer message as a draft Code Artifact |
| `POST` | `/api/projects/{projectId}/code/generate` | Generate Provider-backed MicroPython code from an approved Spec and validate it locally |
| `POST` | `/api/projects/{projectId}/code/accept` | Accept a ready-for-review code run and mark its Code Artifact approved |
| `POST` | `/api/projects/{projectId}/code/reject` | Reject a code run with an optional reason |
| `POST` | `/api/projects/{projectId}/code/rollback` | Mark a code run rolled back without writing real workspace files |

### Code Contracts

- `CodeFileKind`: `MAIN | DRIVER | CONFIG | README | TEST`
- `CodeRunStatus`: `DRAFT | TESTING | READY_FOR_REVIEW | ACCEPTED | STALE | REJECTED | ROLLED_BACK | FAILED`
- `CodeRevisionSource`: `MODEL | USER`
- `CodeValidationKind`: new validation results contain `STATIC | SYNTAX`; `SIMULATION` remains readable only for historical CodeRun payloads.
- `CodeValidationStatus`: `PASSED | FAILED | NOT_RUN`
- `CodeFile`: stable file ID, code run ID, project ID, kind, virtual path, language, content and timestamp.
- `CodePatch`: patch ID, code run ID, optional base snapshot ID, summary, unified diff and timestamp.
- `CodeValidationCheck`: kind, normalized status, fixed command label, real `exitCode` or `null`, and sanitized output.
- `CodeTestResult`: overall result, command label, summary output, timestamp and the two ordered current validation checks; historical payloads may also retain `SIMULATION`.
- `CodeRun`: code run ID, project ID, nullable Spec ID, version, status, `workspace://` root, retry counters, files, patch, test result, linked Artifact IDs, `revisionSource`, `requiresValidation` and timestamps.
- `GenerateCodeRequest`: `specRunId`
- `ImportCodeMessageRequest`: `messageId`
- `ReviseCodeRequest`: `baseCodeRunId`, the complete existing file set as `{path, content}`, and a non-blank change `summary`
- `ValidateCodeRequest`: `codeRunId`
- `AcceptCodeRequest`: `codeRunId`
- `RejectCodeRequest`: `codeRunId`, optional `reason`
- `RollbackCodeRequest`: `codeRunId`

### Code Rules

- `/code/generate` requires an `APPROVED` Spec; otherwise it returns HTTP 422 with `CODE_REQUIRES_APPROVED_SPEC`. This gate does not apply to a validated smart-engineer `codeDraft` or an explicit historical-message import.
- A smart-engineer structured `codeDraft` may create a local `DRAFT` CodeRun/ArtifactVersion in IDEA or another pre-Spec stage. The Provider supplies only allowlisted file candidates; the Sidecar owns all IDs, paths, persistence and payload links.
- `/code/import-message` accepts only a completed assistant message from the same project's smart engineer. It parses fenced Python with a Markdown parser, maps an unlabeled Python block to `src/main.py`, and retains only explicitly supplied safe upload files under `src/*.py`. It does not synthesize README, tests, configuration or driver placeholders. The corrected import scope is idempotent while allowing a retained legacy five-file import to be followed once by the immutable upload-only version.
- Production generation uses the configured Provider and a dynamic upload-only MicroPython contract. `src/main.py` is mandatory and is the only default file; when the implementation genuinely needs modules, every dependency must be a safe flat `src/*.py` file imported by `main.py`. README, tests, placeholders and nested module paths are rejected. The Sidecar validates paths, credentials, host capabilities and local results before persistence; automated tests use a fake Provider.
- Generated and user-edited files are stored in SQLite and exposed through Artifact previews. The Code Agent uses a `workspace://` virtual root and does not write real project workspace files.
- A user save never overwrites a CodeRun. It opens a `BEGIN IMMEDIATE` transaction, verifies that the route `codeRunId` and request `baseCodeRunId` are still the latest version, then creates the next CodeRun and ArtifactVersion with a base snapshot, change summary and unified diff. Older versions and their validation results remain readable.
- A stale save returns HTTP 409 `CODE_REVISION_CONFLICT` with `retryable: true`. A mismatched route/request base returns 422 `CODE_REVISION_BASE_MISMATCH`; unknown, duplicate, missing or unsafe paths and forbidden credential/host-capability content return 422 `CODE_REVISION_INVALID`.
- A saved user version starts as `DRAFT`, `revisionSource: USER`, `requiresValidation: true`, and has `STATIC` and `SYNTAX` at `NOT_RUN` with `exitCode: null`. It cannot be accepted until both checks succeed.
- `POST /code/validate` accepts only the latest CodeRun. A stale `codeRunId`, including a version superseded while validation is running, returns HTTP 409 `CODE_VALIDATION_CONFLICT` and does not replace the newer version's state.
- A new CodeRun reaches `READY_FOR_REVIEW` only when its `STATIC` and `SYNTAX` checks both ran with exit code `0`. Missing, null, or non-zero exit codes fail validation; `SIMULATION` is ignored for new acceptance decisions.
- Local validation launches only fixed-argument static and syntax child processes with `shell=False`, a timeout and an isolated temporary workspace. Static checking covers every upload file and rejects credentials and host capabilities; syntax checking compiles every `.py` without importing or executing project code. The worker exposes no simulation mode and does not materialize board mocks.
- A check is `PASSED` only when its real child-process `exitCode` is `0`; any other real exit code is `FAILED`, regardless of output text. `null` means `NOT_RUN`. The overall result succeeds only when both current checks have exit code zero; historical `SIMULATION` records are ignored and preserved when read.
- Generated code and user revisions become `READY_FOR_REVIEW` only after successful local validation; failures become `FAILED`. Accepting, rejecting and rolling back update the Code Artifact status while preserving version, diff and snapshot history.
- The code Artifact opens in the existing floating-window system with internal “代码 / 变更 / 验证” views. These are not right-side primary tabs and opening them does not replace `MainConversation`.
- Unsaved browser drafts are not persisted and are therefore invisible to an expert. On every smart-engineer Provider call, `ContextAssembler` reloads the latest saved CodeRun and serializes its ID/version, user-modified flag, base snapshot, change summary/diff, validation result and file metadata into the system context. Code-related requests additionally receive bounded current file content (12,000 characters total, with per-file limits); other experts receive no `currentCode` payload.

### Persistence

SQLite v9 adds `code_runs`, `code_files` and `code_patches`. Project workspace responses return `schemaVersion: 9`.

ZW-AGENT-002 reuses those tables plus existing Artifact versions and adds no table. ZW-AGENT-003 schema v23 makes only `code_runs.spec_run_id` nullable so pre-Spec structured replies and explicit historical imports can use the same CodeRun graph; existing rows, files, patches, Artifact versions, foreign keys and indexes are preserved.

## ZW-012 Device Management and MicroPython Deployment API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/devices/ports` | Scan current system serial ports after desktop capability authorization |
| `GET` | `/api/projects/{projectId}/devices/session/current` | Load the latest device session for a project |
| `POST` | `/api/projects/{projectId}/devices/connect` | Re-resolve the selected port and open a desktop-owned serial session |
| `POST` | `/api/projects/{projectId}/devices/disconnect` | Disconnect the current serial session |
| `POST` | `/api/projects/{projectId}/devices/upload` | Create a Dry Run or start a confirmed MicroPython file upload |
| `GET` | `/api/projects/{projectId}/devices/operations/latest` | Read the latest persisted device operation and resume UI polling after remount or reload |
| `GET` | `/api/projects/{projectId}/devices/operations/{operationId}` | Poll one asynchronous upload or firmware operation |
| `POST` | `/api/projects/{projectId}/devices/operations/{operationId}/cancel` | Cancel an operation while its current transport step is cancelable |
| `POST` | `/api/projects/{projectId}/devices/firmware/inspect` | Inspect a submitted `.bin`, compute SHA-256 and check ESP32-S3 compatibility |
| `POST` | `/api/projects/{projectId}/devices/firmware/prepare` | Validate the write address and issue a short-lived confirmation token |
| `POST` | `/api/projects/{projectId}/devices/flash` | Create a Dry Run or start backup, `write-flash` and post-write verification |

### Device Contracts

- `DevicePort`: local serial metadata including logical ID, port name/type, description, manufacturer/product, VID/PID, optional serial number, likely board and availability. Advanced identifiers stay local and are hidden in normal mode; they never enter cloud-model context or test fixtures.
- `DeviceSession`: project device session, board, status, timestamps and bounded log entries.
- `DeviceOperationStatus`: `QUEUED | RUNNING | DRY_RUN_COMPLETE | COMPLETED | BLOCKED | FAILED | CANCELED | TIMED_OUT`.
- `DeviceOperationPhase`: `QUEUED | INTERRUPT_RUNTIME | PREFLIGHT | BACKUP | TRANSFER | VERIFY_FILES | START_RUNTIME | RESTART | RECONNECT | VERIFY_RUNTIME | FIRMWARE_VALIDATE | FLASH_WRITE | RESTORE | COMPLETE`. `RESTART` remains for persisted legacy uploads.
- `DeviceOperation`: operation kind/status/phase, progress, dry-run flag, sanitized steps and log, error code, logical backup summary, verification hashes/exit codes, cancelability and linked `DEVICE_LOG` Artifact IDs. New uploads independently expose `runtimeInterruptedOk`, `deploymentOk`, `runtimeStartedOk` and `managementChannelOk`; legacy `restartOk` remains readable. `runtimeExitCode` is never inferred from a REPL reconnect.
- `UploadCodeRequest`: `codeRunId`, `sessionId`, `dryRun`, optional idempotent `operationId`, and `confirmWrite`.
- `FirmwareInspectRequest`: safe `.bin` file name and Base64 content.
- `FirmwarePrepareRequest`: `sessionId`, `candidateId`, and optional address.
- `FirmwareFlashRequest`: `sessionId`, `dryRun`, `confirmFlash`, candidate/token/operation IDs, address and confirmation phrase.

### Device Rules

- Mock discovery and Dry Run remain available to tests, but automated tests inject `DeviceTransport` and never enumerate real ports or execute `mpremote`/`esptool`.
- A real upload requires the latest `ACCEPTED` CodeRun, a connected session, `confirmWrite: true`, and an idempotent operation ID. It uses a fixed local staging directory, a per-port lock, fixed argv with `shell=False`, timeouts and cancellation.
- Before any backup or write, the runner stops the read-only terminal, opens `mpremote ... resume repl`, sends only bounded Ctrl-C bytes and requires a friendly REPL prompt. Failure returns `DEVICE_RUNTIME_INTERRUPT_FAILED` before any device file write and never escalates to RST/EN, power cycling, Flash erase or firmware flashing.
- After safe interruption, identity and filesystem commands use `mpremote resume` so one-shot command processes do not repeatedly auto-soft-reset the interpreter. The runner uploads only allowlisted `.py` paths, reads every uploaded file back and compares SHA-256.
- After readback succeeds, `START_RUNTIME` performs an interpreter-level `soft-reset` followed by fixed `exec --no-follow "import main"`. This clears the previous Python runtime and starts the deployed entry point without a hardware reset. No post-start management probe is performed; the bounded read-only terminal becomes the observable source for Traceback and execution output.
- Transfer, readback, hash or Python runtime start failure remains a failed deployment and attempts backup restoration. Restore non-zero, timeout or exception leaves a `RESTORE` failure step plus both the original and restore failure evidence; the session remains unavailable until explicitly reconnected.
- `operationId` is reserved atomically with a READY session claim. Repeating the same ID and fingerprint resumes the same operation; reusing it for a different request returns a conflict. Persisted orphan `QUEUED/RUNNING` operations are closed with restart evidence instead of remaining indefinitely active after a Sidecar restart.
- Legacy uploads that recorded successful transfer/readback/restart but failed only while restoring the management channel are presented as “deployment complete, management channel pending” only when no restore step exists. A missing `RECONNECT` step is accepted only for the strict old-runner shape `DEVICE_OPERATION_TIMEOUT` immediately after a zero-exit `RESTART`, with every prior upload phase at zero and no later step. The original failure evidence is retained and a corrected `DEVICE_LOG` Artifact version keeps the operation and artifact views consistent.
- Firmware inspection accepts only bounded `.bin` content and records size, SHA-256, image metadata and expiry. Preparation requires an ESP32-S3-compatible candidate and an explicit address within the known Flash boundary aligned to `0x1000`.
- Real firmware flashing is a separate high-risk flow. It requires `confirmFlash: true`, a matching short-lived token, the phrase “烧录固件”, and an idempotent operation ID. The runner backs up the covered Flash region, executes only `write-flash`, then verifies the written region; it never generates `erase-flash` or `erase-all`.
- Firmware verification is internal to the asynchronous flash operation and is observed through operation polling; there is no separate `/firmware/verify` endpoint.
- Failure, cancellation or timeout retains sanitized steps, a logical backup ID, verification summary and recovery evidence in the existing `DeviceOperation`/`DEVICE_LOG` graph. No parallel device model or table is added.
- The React frontend only invokes Sidecar HTTP contracts. Python's local `DeviceTransport` owns serial and subprocess work; the cloud LLM never receives a file, shell, serial or firmware capability.

### Desktop Host Capability Boundary

- Serial scan, connect/disconnect, upload/cancel and firmware inspect/prepare/flash require the desktop host boundary. Web mode renders the capability explanation and cannot trigger those local side effects.
- `X-Zhangwen-Host: tauri` is not authorization by itself. Requests must also carry the per-start `X-Zhangwen-Capability-Token` shared by the Tauri process and its Sidecar.
- A missing, forged or mismatched token, and requests from the Web origin, return HTTP 409 `HOST_CAPABILITY_UNAVAILABLE` before serial, subprocess or persistence side effects begin.
- Read-only current-session and operation-summary endpoints remain available for rendering previously persisted state.

### Persistence

SQLite v10 added `device_sessions` and `device_operations`. ZW-AGENT-003 reuses those rows and the existing `DEVICE_LOG` Artifact chain; it does not add a device table. The nullable CodeRun Spec migration used schema v23 at that stage, the later CAD baseline used v24, and current project workspace responses use schema v25.

## ZW-CAD-001 结构工程师真实 CAD API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/cad/current` | Load the latest CAD run for a project |
| `GET` | `/api/projects/{projectId}/cad/runs/{cadRunId}` | Load one server-owned CAD run |
| `POST` | `/api/projects/{projectId}/cad/jobs` | Queue the confirmed structure-engineer CAD draft |
| `GET` | `/api/projects/{projectId}/cad/jobs/{jobId}` | Read persistent Job status and result |
| `POST` | `/api/projects/{projectId}/cad/jobs/{jobId}/cancel` | Request cancellation of a local CAD Job |
| `POST` | `/api/projects/{projectId}/cad/jobs/{jobId}/retry` | Retry a retryable failed/interrupted Job |
| `POST` | `/api/projects/{projectId}/cad/confirm` | Mark a ready CAD run as approved |
| `POST` | `/api/projects/{projectId}/cad/reject` | Reject a CAD run with an optional reason |
| `POST` | `/api/projects/{projectId}/cad/generate` | Legacy boundary; always returns HTTP 410 |

### Mechanical Profile HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/hardware/mechanical-profiles` | List reviewed immutable profile revisions, dimensions, mounting data, evidence, SHA-256 and confirmed/locked hardware links |
| `POST` | `/api/hardware/mechanical-profiles/{profileId}/preview` | Validate the requested revision against its Hardware Skill `mechanical.md`; return a matching description-hash cache or compile and persist a new bounded preview cache |
| `PUT` | `/api/hardware/{componentId}/mechanical-profile-link` | Confirm the exact request `profileId + revision` for one hardware component |
| `DELETE` | `/api/hardware/{componentId}/mechanical-profile-link` | Remove a non-locked hardware/profile link; locked K10 returns HTTP 409 `MECHANICAL_PROFILE_LINK_LOCKED` |

These three hardware endpoints currently have no desktop capability guard. Product disclosure is enforced by the professional-mode UI, but callers with direct API access can reach them; K10 PUT remap protection remains the specific known gap described below.

### Artifact File HTTP API Used by CAD

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/artifacts/{artifactId}/versions/{versionId}/files` | List immutable ArtifactVersion file metadata; requires desktop `local_cad` capability |
| `GET` | `/api/projects/{projectId}/artifacts/{artifactId}/versions/{versionId}/files/{fileId}` | Stream one file with server metadata/ETag; requires desktop `local_cad` capability |

### CAD Contracts

- `CadTemplateKind`: `COMPONENT_MOUNT | SENSOR_BRACKET | MCU_MOUNT | MOTOR_MOUNT | SERVO_MOUNT | SIMPLE_ENCLOSURE | PANEL_CUTOUT | BOX_WITH_LID | FREEFORM_STRUCTURE`; current production allowlist is the three templates listed below.
- `CadFileKind`: `PARAMETERS | STEP | STL`
- `CadRunStatus`: `DRAFT | QUEUED | RUNNING | VALIDATED | READY_FOR_REVIEW | APPROVED | REJECTED | STALE | CANCELED | FAILED`
- `CadParameter`: bounded template parameter with `name`, `label`, `unit`, `value`, `min` and `max`.
- `CadValidation`: ordered geometry and parameter checks with `PASS | WARNING | FAIL`.
- `CadFile`: immutable output metadata with role, storage key, size, SHA-256 and optional bounds/triangle count.
- `CadRun`: project/spec IDs, template kind, version, status, parameters, validation, files, source expert and linked Artifact IDs.
- `CadDraft`: structure-engineer-only declaration; it cannot contain Python, paths, URLs, commands, Artifact IDs or Job IDs. The optional `intakeSnapshotSha256` is generated by the Sidecar from confirmed fact IDs/values and cannot be supplied by the Provider.
- `CadBuildSpec`: server-materialized immutable draft with the same `intakeSnapshotSha256` plus resolved mechanical profile revision and SHA-256 snapshots.
- `CadJob`: persistent queue state, phase, progress, request hash, worker result and retryable error.
- `CadJobStatus`: `QUEUED | RUNNING | CANCEL_REQUESTED | CANCELED | SUCCEEDED | FAILED | TIMED_OUT | INTERRUPTED`.
- `CadJobPhase`: `QUEUED | VALIDATING | RESOLVING_PROFILES | LAYOUT | BUILDING | EXPORTING | VALIDATING_OUTPUTS | STORING_ARTIFACTS | COMPLETED | CANCELED | FAILED`.
- `CadOutputRole`: `STEP_ASSEMBLY | STEP_PRINTABLE_PARTS | STL_PRINTABLE_PARTS | GLB_PREVIEW | PARAMETERS | PROFILE_SNAPSHOTS | VALIDATION_REPORT | GEOMETRY_SUMMARY | MANIFEST`.
- `CadSizingEvidence`: `mode: AUTO | MIXED | EXPLICIT`, required `width/height/depth` and the axes actually filled by the server.
- `CreateCadJobRequest`: `cadRunId` and optional idempotency `clientRequestId`; `RetryCadJobRequest` may provide a new `clientRequestId`.
- `MechanicalProfileSummary`: exact profile identity plus dimensions, mounting mode/strategy/surfaces, clearance, evidence, representation, optional validated `previewGeometry`, content SHA-256 and confirmed/locked hardware IDs.
- `GenerateMechanicalProfilePreviewRequest`: the exact currently displayed `revision`; stale or missing versions fail closed.
- `MechanicalProfilePreviewGenerationResponse`: updated profile plus `generationSource = DESCRIPTION_CACHE | DESCRIPTION_GENERATED | ENVELOPE_FALLBACK`. `DESCRIPTION_GENERATED` writes the new `preview_geometry.source_sha256` to the same Hardware Skill under revision CAS before returning.
- `ConfirmMechanicalProfileLinkRequest`: exact `profileId` and `revision`; names, categories and display labels are never accepted as identity.
- `ConfirmCadRequest`: `cadRunId`.
- `RejectCadRequest`: `cadRunId`, optional `reason`.

### CAD Rules

- Only `structure_engineer` may materialize a `cadDraft`. A direct CAD request first classifies or clarifies `cad_build_target`. `COMPONENT_MOUNT` then collects exactly one server-owned `cad_component_mount_profile`; `BOX_WITH_LID` collects `cad_component_mode` and explicit inner `length x width x height` millimetres; `FREEFORM_STRUCTURE` collects a natural-language part description and never requires a hardware/profile selection.
- A structure-engineer CAD turn takes precedence over the generic solution/proposal conversation branch, including at `SOLUTION_DRAFT`, `SOLUTION_CONFIRMED` and `PROPOSAL_DRAFT`. CAD intent may come from the current message, the source `cad_*` clarification, or recent CAD context plus an explicit continue/revise expression. 安装座、固定底座、托架、支架和压框进入单器件安装结构；外壳、保护壳、盒体和容器进入盒体；明确“不使用器件”或按尺寸做安装板/连接板进入自由结构；模糊三维结构请求不得默认成盒体。
- Persisting a clarification answer, marking its questions answered and materializing the CAD SharedFacts is one SQLite transaction. Invalid dimensions/profile answers roll back the whole submission and remain answerable; duplicate turns reuse the already atomic persisted result and never reapply older facts.
- Loose storage explicitly materializes `components=[]` after dimensions are confirmed. Fixed installation may reference either an approved-BOM hardware/profile mapping or a project-scoped virtual `cad_profile_<hash>` identity derived from a user-selected immutable profile revision and SHA-256.
- The option ID, virtual hardware ID, profile ID, revision and SHA-256 are generated and revalidated by the Sidecar. Only the current revision of each profile is offered, no profile may be selected twice, and at most 32 explicit selections are accepted. Project selections take priority over approved-BOM mappings in the bounded runtime context. Job creation re-reads the current project selection and rejects a stale or superseded draft with `CAD_PROJECT_PROFILE_SELECTION_STALE`; the client and Provider cannot submit trusted profile metadata.
- CAD target/dimensions/profile/description input is not collected through `PendingItem`. Missing input returns a structured clarification card; complete input is normalized into the selected `BOX_WITH_LID`, `COMPONENT_MOUNT` or `FREEFORM_STRUCTURE` draft, so a plain-text Provider response cannot leave the flow completed with `cadDraft=null`.
- An explicit CAD revision such as “改成/调整/重做” or a new `length x width x height` value (with or without the repeated millimetre suffix in an existing CAD context) supersedes the previous project intake and starts a new clarification round. In the same transaction, old non-active `DRAFT/VALIDATED/READY_FOR_REVIEW/FAILED/CANCELED/REJECTED` candidates and their chat/Artifact projections become `STALE`; old pending `cad_*` questions become superseded. `QUEUED/RUNNING` Jobs are not implicitly canceled and the last `APPROVED` baseline remains current until a new version is confirmed.
- Draft persistence hashes the current confirmed mode, dimensions and exact profile selection fact IDs/values into `intakeSnapshotSha256`. `POST /cad/jobs`, `POST /cad/jobs/{jobId}/retry`, worker finalization and `POST /cad/confirm` compare the persisted Run/Job snapshot with the current intake. A mismatch returns HTTP 409 `CAD_INTAKE_REVISED`, `retryable: false`, with “CAD 结构输入已更新，请使用最新 CAD 草稿。”; even an idempotent request cannot return an old Job. A Worker already running may finish computation, but its obsolete publish is discarded and the Run becomes `STALE`.
- The persisted `projectExpertId` owns expert identity. A request `expertType` cannot upgrade another project expert into `structure_engineer`; outside a recognized server-owned CAD workflow, Provider-supplied `cadDraft` or `cad_*` clarification payloads fail validation.
- The current deterministic engine allowlist is `BOX_WITH_LID -> box-with-lid.v1`, `COMPONENT_MOUNT -> component-mount.v1` and `FREEFORM_STRUCTURE -> freeform-structure.v1`; unknown template revisions fail closed. Component mount requires exactly one immutable mechanical profile. Freeform requires `components=[]`, `parameters={}` and at most 32 ordered, bounded `box/rounded_box/cylinder` primitives using only `add/cut`; the first primitive is `add` and the final B-Rep must be one connected solid. Neither path executes Hardware Skill or Provider Python.
- The reviewed built-in profile set is `unihiker_k10:measured-v1`, `unihiker_ultrasonic_distance_sensor:measured-v1`, `xiao_esp32s3:confirmed-v1`, `grove_oled_096:confirmed-v1` and `grove_button:confirmed-v1`. The K10 link is seeded, DELETE-protected and fixed in CAD resolution; the professional UI does not offer it as a remap candidate. Direct PUT remap protection is not yet implemented.
- Mechanical resolution is exact: one confirmed hardware ID resolves one `profileId + revision + contentSha256` snapshot. Job creation fails on missing, ambiguous or mismatched links and never searches profile names.
- Hardware preview geometry has one authoring source: the exact `## 自然语言描述` section in the active Skill's `references/mechanical.md`. `GET /mechanical-profiles` never calls a paid model. An explicit preview POST hashes the normalized description; a matching cache is returned without credentials, while a missing, legacy or stale cache sends only that section to the structured model, validates at most 32 bounded primitives locally, and writes the cache back as a new Skill revision. Invalid output, missing configuration and revision conflicts never fall back to stale geometry.
- Omitted enclosure `width/height/depth` values are resolved locally from immutable profile envelopes, rotation, mounting surface, explicit offsets, edge clearance and hardware gap. Explicit axes are preserved even when too small, so later geometry validation fails closed instead of silently enlarging them.
- The empty enclosure lower bound is `80 x 50 x 28 mm`; default `edge_clearance` is `8 mm`, default `hardware_gap` is `5 mm`, 90/270-degree placement swaps profile length/width, and the final required dimensions round upward to `0.1 mm`. Base/lid, front/back and left/right surfaces contribute to the corresponding two-dimensional envelope; components on both base and lid stack their height plus the hardware gap.
- The Sidecar invokes one fixed CAD Worker through `stdin`, a restricted working directory and bounded resources. It never executes LLM/user Python or `runpy`.
- A successful, still-current Job publishes the template-owned exact immutable file set atomically before the run becomes `READY_FOR_REVIEW`; `requestedOutputs` cannot reduce it. Box/component templates publish 11 files, while a one-part freeform build publishes 9:

| File | Role |
|---|---|
| `assembly.step` | `STEP_ASSEMBLY` |
| `base.step`, `lid.step` | `STEP_PRINTABLE_PARTS` |
| `base.stl`, `lid.stl` | `STL_PRINTABLE_PARTS` |
| `part.step` (freeform instead of base/lid) | `STEP_PRINTABLE_PARTS` |
| `part.stl` (freeform instead of base/lid) | `STL_PRINTABLE_PARTS` |
| `preview.glb` | `GLB_PREVIEW` |
| `parameters.json` | `PARAMETERS` |
| `profiles.json` | `PROFILE_SNAPSHOTS` |
| `validation.json` | `VALIDATION_REPORT` |
| `geometry-summary.json` | `GEOMETRY_SUMMARY` |
| `manifest.json` | `MANIFEST` |

The parent process requires an exact file set and verifies name, role, MIME type, size, SHA-256 and available bounds/triangle metadata before publication.
- `/cad/confirm` and `/cad/reject` require desktop capability. Web renders the reason and leaves the persisted run unchanged.
- The frontend exposes progress in the right `工作` tab, opens GLB through the `产物` floating window, and keeps the central conversation mounted.

### Persistence

SQLite v24 introduced `cad_jobs`, `artifact_files`, immutable mechanical profile snapshots/links and the real CAD run fields. Current project workspace responses return `schemaVersion: 25`; v25 adds only the private local-execution authorization relation described above.

## ZW-014 Lesson Agent API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/lesson/current` | Load the latest Lesson Agent run for a project |
| `POST` | `/api/projects/{projectId}/lesson/generate` | Generate deterministic lesson documents from an approved Spec |
| `POST` | `/api/projects/{projectId}/lesson/confirm` | Mark a ready lesson run as approved |
| `POST` | `/api/projects/{projectId}/lesson/reject` | Reject a lesson run with an optional reason |

### Lesson Contracts

- `LessonDocumentKind`: `TEACHER_GUIDE | STUDENT_WORKSHEET | RUBRIC | SAFETY_NOTES`
- `LessonRunStatus`: `DRAFT | READY_FOR_REVIEW | APPROVED | REJECTED | STALE | FAILED`
- `LessonFile`: generated Markdown document metadata, content and linked Artifact IDs.
- `LessonRun`: project/spec/proposal IDs, version, status, grade band, lesson hours, files and timestamps.
- `GenerateLessonRequest`: `specRunId`, optional `gradeBand`, optional `lessonHours`.
- `ConfirmLessonRequest`: `lessonRunId`.
- `RejectLessonRequest`: `lessonRunId`, optional `reason`.

### Lesson Rules

- `/lesson/generate` requires an `APPROVED` Spec; otherwise it returns HTTP 422 with `LESSON_REQUIRES_APPROVED_SPEC`.
- ZW-014 uses deterministic Markdown templates only. It does not call a real paid LLM and does not write project workspace files.
- Generated files are `lesson/teacher_guide.md`, `lesson/student_worksheet.md`, `lesson/rubric.md` and `lesson/safety_notes.md`.
- Lesson documents are synchronized as `DOCUMENT` Artifacts from `lesson-agent`, with dependencies on the source proposal and Spec.
- Generating a new lesson marks previous ready/approved lesson runs and their Artifact versions as `STALE`.
- Confirming or rejecting lessons updates Lesson Artifact status only; it does not modify proposal, Spec, Code, CAD or device core data.
- The frontend exposes Lesson status/actions in the right "工作" tab and previews documents through the existing "产物" tab/floating window system. It does not replace `MainConversation`.

### Persistence

SQLite v12 adds `lesson_runs` and `lesson_files`. Project workspace responses return `schemaVersion: 12`.

## ZW-015 Sharing and Project Package API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/projects/{projectId}/package/export` | Export a controlled base64 ZIP package for one local project |
| `POST` | `/api/projects/package/import` | Import a controlled project package ZIP and create a project copy by default |

### Project Package Contracts

- `ProjectPackageStatus`: `READY | EXPORTED | IMPORTED | BLOCKED | FAILED`
- `ProjectPackageItemKind`: `PROJECT | ARTIFACT | MANIFEST | PRIVACY_REPORT`
- `ProjectPackageConflictStrategy`: `CREATE_COPY | FAIL_IF_EXISTS`
- `ProjectPackageArtifactSelection`: include flags for documents, code, CAD, lessons and device logs.
- `ProjectPackageManifest`: package schema version, package/project IDs, source project metadata, selected artifacts, privacy report and timestamps.
- `ProjectPackagePrivacyReport`: `ok` plus ordered privacy checks.
- `ProjectPackageExportRecord`: persisted export status, manifest, privacy report, package artifact ID and optional ZIP payload.
- `ExportProjectPackageRequest`: optional artifact selection and display title.
- `ImportProjectPackageRequest`: base64 ZIP payload and conflict strategy.

### Package Rules

- Export and import are executed only by the Python Sidecar. The frontend does not read local SQLite files, raw project files or filesystem paths.
- Export writes a ZIP with fixed safe paths: `manifest.json`, `project/summary.json`, `privacy_report.json` and `artifacts/<safe-id>.json`.
- Raw project databases, Credential Manager data, temporary logs, build caches, absolute local paths and real device identifiers are not exported.
- Privacy scanning runs before package ZIP creation. Suspicious API key, token, authorization, Wi-Fi password, serial-port or absolute-path content blocks the export with `ProjectPackageStatus.BLOCKED`; blocked records persist with no ZIP payload.
- Import rejects absolute paths, Windows drive-letter paths, backslashes, `..`, directory entries and unknown package paths.
- Import defaults to `CREATE_COPY`; it creates a new project ID and does not overwrite local projects.
- Successful export/import synchronizes a `PACKAGE` Artifact from `publish-agent` so the package appears in the right "产物" tab.
- Package tests use in-memory/fake payloads only and must not contain real credentials or real serial IDs.

### Persistence

SQLite v13 adds `package_exports`. Project workspace responses return `schemaVersion: 13`.

## ZW-016 MVP Integration and Readiness API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects/{projectId}/mvp/readiness` | Build a read-only MVP readiness report from existing project records |

### MVP Readiness Contracts

- `MvpReadinessStatus`: `READY | NEEDS_ACTION | BLOCKED`
- `MvpReadinessItemId`: `PROJECT_BASELINE | SOLUTION | PROPOSAL | EXECUTION_PLAN | SPEC | CODE | DEVICE_DRY_RUN | CAD | LESSON | PACKAGE | ARTIFACTS | SECURITY`
- `MvpReadinessItem`: item ID, Chinese label, status, required flag, user-actionable message and evidence strings.
- `MvpReadinessReport`: project ID, overall status, ready/total count, generated timestamp, item list, external validation requirements and manual acceptance steps.

### Readiness Rules

- The readiness API is read-only and does not add a SQLite schema migration. It derives status from existing v13 tables.
- `READY` requires the software loop to contain an approved solution, approved proposal, completed execution plan, approved Spec, accepted code, upload Dry Run, approved CAD, approved lesson, exported project package, required Artifact kinds and no blocked package or real device operation records.
- Real ESP32 discovery/upload, real DeepSeek credential testing, Flash erase, firmware burn and device file overwrite remain external manual validation items.
- The desktop shows readiness only in the right "工作" tab. It does not replace or unmount the central conversation.
- Automated tests use deterministic fixtures and Mock/Dry Run APIs only; no real paid LLM, serial access, shell command or CadQuery runtime is invoked.

## TaskStatus

`DISABLED | QUEUED | PLANNING | RUNNING | AWAITING_APPROVAL | PAUSED | BLOCKED | COMPLETED | FAILED | CANCELED`

## ArtifactStatus

`DRAFT | GENERATING | NEEDS_REVIEW | APPROVED | REJECTED | STALE | FAILED | ARCHIVED`

## 必需事件

- `chat.started`
- `chat.delta`
- `chat.completed`
- `chat.error`
- `chat.canceled`
- `project.stage.changed`
- `agent.status.changed`
- `task.progress`
- `task.approval.required`
- `artifact.created`
- `artifact.updated`
- `device.discovered`
- `device.log`
- `device.upload.progress`
- `device.error`
- `security.warning`

任何新增事件必须更新本文件、JSON Schema 和前后端类型生成测试。

## 设备只读串口终端 API

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/projects/{projectId}/devices/terminal/start` | 为当前设备会话启动受控只读终端 |
| `POST` | `/api/projects/{projectId}/devices/terminal/stop` | 停止终端读取并释放端口 |
| `POST` | `/api/projects/{projectId}/devices/terminal/clear` | 清空当前会话的有界内存输出 |
| `GET` | `/api/projects/{projectId}/devices/terminal?sessionId=...` | 读取终端状态、revision 和当前有界文本快照 |

- `DeviceTerminalStatus`: `IDLE | STARTING | RUNNING | STOPPED | ERROR`。
- 终端请求只接受当前项目的 `sessionId`，且必须通过桌面 `serial_connection` capability 门禁。
- 终端为只读：API 不接受按键、脚本或 REPL 命令。生产 argv 由本地 Transport 固定组装，不能由请求提供。
- 输出仅保存在 Sidecar 内存并限制长度；不进入 SQLite、浏览器存储或 Artifact。返回内容不得附带真实端口、子进程 argv 或凭据。
- 终端和上传/固件操作使用同一端口锁。冲突返回稳定错误；断开设备必须停止终端并回收子进程。

## ZW-002 LLM 与聊天 API

### Sidecar HTTP API

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/settings/llm` | 获取非敏感 LLM 配置和 Key 保存状态 |
| `PUT` | `/api/settings/llm` | 保存 Base URL、默认模型、思考模式、超时和可选 API Key |
| `DELETE` | `/api/settings/llm/api-key` | 清除保存的 API Key |
| `POST` | `/api/settings/llm/test` | 使用当前或提交的配置测试连接 |
| `GET` | `/api/llm/models` | 返回可选模型与能力声明 |
| `POST` | `/api/chat/stream` | 发起真实 LLM 对话，返回 SSE |
| `POST` | `/api/chat/cancel/{requestId}` | 取消正在进行的生成 |

项目聊天客户端在 `chat.started` 后固定持有 `projectId + conversationId + requestId`。专家切换只影响下一次请求；切换项目或退出必须先调用取消并等待当前 SSE reader 收敛，旧作用域的迟到 chunk 不得写入新项目。

### SSE 流式事件

ZW-002 使用 SSE（Server-Sent Events）进行单向 token 流传输。

```text
event: chat.started
data: { StreamChunk START }

event: chat.progress
data: { StreamChunk PROGRESS with server-owned ChatProgress }

event: chat.delta
data: { StreamChunk CONTENT_DELTA | REASONING_DELTA }

event: chat.completed
data: { StreamChunk COMPLETED }

event: chat.error
data: { StreamChunk ERROR }

event: chat.canceled
data: { StreamChunk CANCELED }
```

### StreamChunk 类型

`START | PROGRESS | CONTENT_DELTA | REASONING_DELTA | COMPLETED | ERROR | CANCELED`

`chat.progress` 当前由项目专家对话的本地 Runtime 链路产生；其他聊天路径可以不发送该事件。客户端不得把缺少进度事件解释为执行失败，也不得从 `REASONING_DELTA` 补造动作。

### LLM 错误码

`CONFIG_MISSING | LLM_OUTPUT_INVALID | LOCAL_OUTPUT_REJECTED | GENERATION_INTERRUPTED | INVALID_REQUEST | AUTH_FAILED | INSUFFICIENT_BALANCE | INVALID_PARAMETERS | RATE_LIMITED | SERVER_ERROR | SERVICE_BUSY | NETWORK_UNAVAILABLE | TIMEOUT | CANCELED | SIDECAR_UNAVAILABLE | UNKNOWN`

### 安全规则

- API Key 不出现在 URL、query string、日志、错误信息或测试快照中。
- 前端不直接调用 DeepSeek API；所有 LLM 请求由 Python Sidecar 发起。
- API Key 使用 Windows Credential Manager 存储（ctypes CredWriteW/CredReadW）。
- 非敏感配置存储在应用数据目录的 `config/llm.json`，不含 API Key。
- 所有日志通过脱敏函数处理 headers、authorization、apiKey、token 字段。
