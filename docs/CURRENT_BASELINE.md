# 掌问当前唯一基线

版本：ZW-CLOSURE-001

日期：2026-07-26

状态：当前唯一产品基线；正式部署采用邮箱账号，本机未配置云认证且保留旧本机账号时提供受控恢复入口；本地项目按账号 subject 隔离，Web Development Mode 仅作为显式浏览器开发入口

本文件把 `docs/PRD.md`、`docs/DECISIONS.md`、`docs/UI_CONTRACT.md` 与当前可运行代码收敛为一个最小基线。发生冲突时，产品不变量以 `AGENTS.md` 和 `docs/UI_CONTRACT.md` 为准，产品含义以最新 `docs/PRD.md` 和 `docs/DECISIONS.md` 为准；本文件决定当前主流程中哪些实现继续使用。历史任务、阶段分析和归档 PRD 不得重新定义当前产品。

## 1. 当前产品定义

产品名是“掌问”，副标题是“AI 创客工程工作台”。掌问是本地优先的 AI 创客工程工作台：用户从自然语言想法开始，在永久中央主对话中获得需求澄清和一套当前推荐实现方案，并在右侧查看同一份版本化产物；云端模型负责理解和内容生成，本地服务负责状态、数据、权限和外部执行边界。Tauri 是最终本地桌面宿主；默认入口直接启动完整本地应用，不隐式扫描、选择或部署任何开发板。

当前最小可验收价值不是完整的自动制造链，而是“一个项目、一条共享时间线、一套当前方案、多个按需参与的智能体、同一版本化产物和可重启恢复”。

## 2. 三师定义

| 用户可见专家 | canonical ID | 当前职责 | 当前边界 |
|---|---|---|---|
| 问题引导师 | `problem_guide` | 创意引导、需求澄清、目标/约束整理、形成推荐方案 | 不直接控制硬件，不绕过用户确认写入确定事实 |
| 智能工程师 | `smart_engineer` | 硬件、软件、IoT、数据与 AI 部署实现；通过 Skill 扩展能力 | Skill 不是新专家；外部效果必须进入本地受控执行 |
| 结构工程师 | `structure_engineer` | 外观、结构、装配、尺寸、公差和可打印性 | 只读取必要工程摘要，不执行烧录、串口控制或设备重启 |

`entry_router` 和 `project_coordinator` 是用户不可见系统角色。旧 `ideator`、`educator`、`open_hardware_designer`、`structure_designer`、`three_d_structure_designer`、`question_guide`、`intelligent_engineer` 只作为旧数据兼容值存在，不能重新出现在新项目前台或形成第四位专家。

## 3. UI 不可变规则

1. 中央区域始终是主对话，`CenterChat` 在项目工作区生命周期内保持同一挂载实例。
2. 右侧一级 Tab 固定为“工作 / 产物 / 设备”。产物和设备详情只进入右栏、浮窗或覆盖层，不替换中央对话。
3. 前台一次只突出一套当前推荐实现方案；旧版本只在产物历史中保留。
4. 当前方案必须同时包含实现逻辑和硬件方案。
5. 前台一个项目只有一条聚合时间线和一个项目级草稿；底层三师保留独立 `conversationId`、私有记忆和 Provider 历史，不互相注入完整聊天。
6. 普通模式隐藏 Agent、Skill、模型、内部 ID、工具链和高级设备信息；专业模式入口只在设置中。
7. 切换 Tab、专家、项目、侧栏或浮窗不能串线、丢草稿或把旧异步响应写入当前项目。
8. 工作页同一时间只突出一个当前待处理事项；普通 PendingItem 只作摘要，不抢占中央确认卡。所有状态必须显示中文，不只依赖颜色。
9. 助手回复显示专家头像、中文名称和内容气泡；缺少需求时直接显示整组澄清卡，不能以“确认处理” PendingItem 代替回答事务。
10. 新建项目入口位于左侧项目栏；用户先点击“分析并推荐”，成功后创建覆盖层才提供可跳过的项目硬件选择。项目所需智能体显示在输入框上方，下一条消息可通过胶囊或 `@智能体` 指定，缺失工程师可按当前项目临时加入。
11. BoardProfile 编辑只进入专业模式“设置 → 公共知识 → 开发板档案”；代码和器件项目编辑使用现有浮窗，内部文件视图不得扩展右侧一级 Tab。
12. 生成失败保留在中央时间线并显示分类原因与恢复动作；修改需求恢复原草稿，重试创建绑定原项目、原专家和原用户文本的新轮次。服务重启遗留生成不能只显示“可重试”而没有按钮。

## 4. 当前核心流程

当前唯一主流程限定为：

```text
首次使用注册邮箱账号、输入六位验证码并完成使用画像；已有账号登录或恢复有效会话；
未配置云认证且存在旧本机账号时使用本机账号恢复入口
→ 认证成功后挂载项目工作台
→ 处理一次旧项目认领决定（认领全部或暂不处理）
→ 按“描述创意 → 推荐方案与硬件 → 确认创建”创建项目
→ 普通模式自动选择参与专家，硬件/代码/设备项目必须包含智能工程师
→ 可选：从 ACTIVE 硬件库确认已有/优先使用器件
→ 进入项目唯一中央时间线并澄清需求
→ 三师按当前 confirmed 项目硬件规划；缺少能力时显示本地补件动作
→ 生成唯一推荐实现方案（包含实现逻辑和硬件方案）
→ 用户确认方案
→ 在右侧“产物”查看与方案卡相同 ArtifactVersion
→ 点击胶囊或输入 @智能工程师 指定回复
→ 多位智能体回复继续出现在同一项目时间线，并显示回复者名称
→ 重启本地服务/重建 Repository 后恢复项目、聚合消息、项目草稿和产物版本
```

正式实现链为：

`App.tsx` → `AuthGate.tsx` → `/api/auth/*` 与 `AuthSessionMiddleware` → `AppShell.tsx` → `ProjectCreationDialog / useProjects` → `CenterChat / useChatStream` → `/api/projects`、`/api/projects/{id}/chat/stream` → `ProjectRepository / idea_flow / ExpertRuntime` → `SolutionRepository / ArtifactRepository` → `RightPanel / ArtifactsTab / FloatingWindow`。

主流程动作以持久化中央对话及其 `structuredPayload` 为准。旧的独立澄清表单/方案按钮接口不是当前 UI 主流程。

当项目已有 MicroPython Code Artifact 时，智能工程师闭环为：

```text
从右侧“产物”打开代码浮窗
→ 在“代码”视图修改现有文件并填写变更摘要
→ 保存为不可变新 CodeRun/ArtifactVersion（旧版本保留）
→ 在“验证”视图运行本地静态检查和语法检查
→ 下一条发给智能工程师的代码相关消息读取最新已保存版本、变更摘要、验证退出码和有界代码正文
```

未保存浮窗草稿不进入本地持久化或 Provider 上下文。保存冲突保留草稿和摘要；保存后的版本在静态与语法两项检查退出码全部为 0 前保持未验证/失败状态，不能接受或进入上传流程。

已接受代码在桌面宿主中的设备闭环为：

```text
选择当前已接受版本
→ 扫描并连接设备
→ 确认覆盖同名 .py 文件
→ 备份、逐文件写入、SHA-256 回读、软重启并重新连接
→ 读取结构化运行日志，核对湿润时关泵、干燥时有限启动且三秒内关闭、无未处理异常
```

管理通道重连失败不会否定已经回读一致的文件部署；此时显示“部署完成 · 通道待恢复”，保留备份和恢复动作。传输、哈希、重启或恢复失败仍是真失败。Web 宿主只读显示摘要，不扫描、连接、上传或烧录。

## 5. 当前正式技术栈

| 层 | 正式基线 |
|---|---|
| 桌面宿主 | Tauri 2、Rust |
| 桌面 UI | React 18、TypeScript 5 strict、Vite 6、原生 CSS |
| 前端测试 | Vitest 3、Testing Library |
| 本地服务 | Python 3.11+、FastAPI、Pydantic 2、Uvicorn |
| 持久化 | SQLite，forward-only migration |
| 云端身份 | 独立 FastAPI、PostgreSQL、通用 SMTP；本地开发使用 Mailpit |
| 共享契约 | pnpm workspace 下的 `@zhangwen/contracts` |
| LLM | `LLMProvider` 抽象，当前唯一真实生产 Provider 为 DeepSeek |
| 自动测试外部依赖 | fake Provider、Mock/Dry Run 设备；不调用付费模型或真实硬件 |

Browser Host 与 Tauri Host 使用同一个 React 应用和同一个 API Client。默认 `pnpm start` 通过 `start-local.ps1` 启动 contracts、FastAPI、Vite 和 Tauri；显式 `pnpm dev:web` 只启动 FastAPI + Vite，用于无设备浏览器开发。串口扫描、连接和上传只从完整桌面应用的“设备”Tab 发起。

`pnpm dev:web:fake` 是内部交互 QA 入口：只在专用子进程启用本地 fake Provider，并使用 `.data/web-fake` 隔离数据。它不是产品的“免费模式”，也不作为生产错误回退；默认 `pnpm dev:web` 和所有生产路由仍要求真实 DeepSeek 配置。

`pnpm dev:web:paid` 是内部真实 DeepSeek 验收入口，使用 `.data/web-paid` 隔离测试项目，不是产品的“付费模式”。产品界面统一显示云端 LLM，顶栏只显示本地服务健康，设置页使用“测试云端连接”；`fake` 与 `paid` 仅作为内部启动配置互斥。该入口仍遵守后端凭据边界，浏览器不读取或提交 Key。

React 只调用本地 API，不直接访问 SQLite、Shell 或串口。Python Sidecar 是本地领域状态和执行权限的权威边界。

MicroPython 本地检查由 Sidecar 以固定参数、`shell=False`、超时和隔离临时目录启动静态、语法两个子进程；状态只由真实退出码推导。检查过程不导入或执行用户代码，不注入开发板 Mock，也不连接网络、串口或真实硬件。

Agent Skill 包中的 Markdown 只影响下一次目标智能体的 system prompt，不能授予工具、修改风险等级或绕过 Tool Runner。问题引导师、智能工程师和结构工程师继续使用各自独立的 Provider 对话历史；包内容不会跨智能体注入。专业模式从“设置 → 智能体 → 打开行为项目”进入 `agent-package:{expertType}` 浮窗确认和修改目录化 Markdown。

## 6. 已实现能力

- `LOCAL_OUTPUT_REJECTED`、`LLM_OUTPUT_INVALID` 与启动中断的分类恢复卡；支持修改原需求、按原需求重新/继续生成和打开模型设置，恢复轮次持久化来源消息且不重复显示整段需求。
- 自由结构 CAD 通过专用声明式几何 Schema 生成，再由本地封装 `FREEFORM_STRUCTURE` 草稿，降低通用专家输出遗漏 geometry 导致的连续结构失败。
- 邮箱注册、十分钟单次六位验证码、Argon2id 密码、登录/刷新轮换/退出/找回密码和用户画像；云端 refresh token 只进入操作系统凭据库，React 仅持有本地短会话。已验证设备支持 30 天离线租约；认证成功前不挂载项目工作台。
- 项目 SQLite v26 用 `owner_subject` 和账号级 workspace state 实施隔离；项目、对话、产物、设备、导入导出、复制和生命周期路由统一越权 404。v25 旧项目不自动归属，首次云账号登录必须明确认领或暂不处理。
- 项目阶段、顶部状态、工作栏当前动作和五项就绪度统一消费 `ProjectProgressSnapshot`，不再由 UI 分别推断。
- Sidecar 对除健康检查和认证入口外的全部业务 API 验证 Bearer 会话。密码以随机盐 PBKDF2 派生保存，会话库只保存 token 摘要。
- 项目创建、打开、归档兼容和重启恢复。
- 三师 canonical 类型、旧专家映射、前台项目单一时间线/草稿，以及底层独立 Conversation、私有记忆和 Provider 历史。
- 左侧新建项目和项目列表；创建时先由显式按钮分析完整创意，成功后才从 ACTIVE 库可选/清空项目硬件；硬件变化不使旧分析失效。create 与项目内硬件更新由 Sidecar 复核 ACTIVE 状态和 Rule Engine，WARNING 以 `selectedHardwareWarnings` 中文文本显示。输入框上方保留智能体胶囊、`@智能体` 路由和按项目增补其余工程师。
- 三师行为配置使用目录化 Agent Skill 包：每包以 `SKILL.md` 为入口，按需加载 manifest 白名单中的 `references/*.md`；内置包只读，用户修改写入当前数据目录 overlay。专业模式设置用“打开行为项目”进入文件树/Monaco 浮窗。
- 专业模式设置把可编辑的“行为项目”和 34 个受控 Registry Skill“执行能力”分开显示；后者的描述覆盖继续保存在 `skill-description-overrides.json`。
- 三师共享读取同一项目事实、决策、产物和 ACTIVE Hardware Skill revision；已选器件作为 confirmed 优先基线精确水合，只补推荐缺口。Hardware Skill 统一保存到 `<data_dir>/hardware-skills/<skill-name>`，电气、结构、规则和工程说明由受控内容编译；`hardware_components` 与机械档案表都只是可重建投影。声明结构能力的包成对包含 `references/mechanical.md + models/cadquery.py`，模型以 SHA-256 和 `REFERENCE_ONLY` 策略绑定，不因普通保存执行。只有保存并编译成功的 ACTIVE revision 进入规则与上下文。
- 电气兼容不再把开发板输入电压当成唯一供电能力：器件用 `voltageMin/voltageMax` 声明连续工作范围，用 `voltage` 声明推荐点；MCU/POWER 用 `supplyVoltages` 声明实际外设电源轨。K10 暴露 3.3V/5V 轨，Rule Engine 选择最接近推荐点的兼容轨，并继续独立校验 3.3V 信号/ADC 边界。
- 正式最小硬件目录包含行空板 K10、SEN0193、DFR0523、5V/3A 独立稳压电源要求，以及已有受信 SEN0388 超声波、DFR0486 OLED、DFR0029 按钮档案；历史演示 seed 不恢复。每个正式包包含来源、SHA-256、电气/结构/安全/接线和规则测试。自动浇花规则强制 SEN0193 接 K10 ADC、DFR0523 接受支持 PWM、泵独立供电且与 K10 共地，GPIO 供泵或电流不足直接失败。
- 自动浇花代码产物是 `src/boot.py`、`src/main.py`、`src/config.py`、两个驱动模块与 `README.md` 的结构化工程；上电/异常默认关泵，单次至多三秒、间隔至少六十秒、先标定阈值并记录每日累计运行时间。
- 桌面设备页提供已接受 MicroPython 代码的受控文件部署，以及严格分离、专业模式可见的固件流程；普通模式隐藏真实端口、内部 ID、退出码和长日志。
- 公共知识支持 Markdown BoardProfile：内置 `unihiker-k10`，专业模式可保存 revision 保护的 data-directory overlay、处理 409 冲突并恢复内置默认；匹配板型时三师上下文读取有效 revision 和有界 Markdown。
- Provider 驱动的 EntryRouter、问题澄清、推荐方案生成/修订和三师结构化回复。
- 三师回复使用语义头像、最大 640px 自适应气泡和可访问三点生成态；整组澄清显示进度并一次提交。Provider 的需求型/执行确认 PendingItem 在 ExpertRuntime 校验与写库边界被拒绝，普通协调事项只留在工作摘要。
- 一套当前 SolutionVersion 与稳定 Solution Artifact 的同步；生成、修订、确认和历史版本保留。
- 右侧固定工作/产物/设备 Tab，产物详情和浮窗不替换中央对话。
- Code Artifact 浮窗提供“代码 / 变更 / 验证”二级视图、文件切换、编辑、摘要、放弃、不可变新版本保存和本地验证；409 保存冲突保留未保存代码与摘要。
- 用户代码新版本复用 `code_runs`、`code_files`、`code_patches` 和 ArtifactVersion，旧版本及其验证结果保持可读；并发相同 base 只有一个保存成功。
- 本地 MicroPython 静态检查和语法检查返回每项真实 `exitCode`；非零即失败，未执行为 `null`，两项全零才进入 `READY_FOR_REVIEW`，失败版本不能接受。检查只解析或编译代码，不执行用户程序。
- 智能工程师下一次调用重新读取最新已保存 CodeRun、用户修改标记、摘要/diff 和验证结果；代码相关请求再注入总计最多 12,000 字符的当前文件正文，其他专家不接收 `currentCode`。
- 可复用 `micropython-board-project` Skill 模板使用 `SKILL.md` 与 BoardProfile/验证 references，所有板型事实从有效 BoardProfile 加载，不在模板中复制 K10 引脚或容量事实。
- SharedFact、Decision、PendingItem、Task、Handoff、ArtifactDependency 和过期传播的现有持久化能力。
- 专业模式中的既有 Proposal、Spec、Code、CAD、Lesson、Orchestrator、Skill、设备和项目包能力；它们有路由和测试，但不扩大本任务最小主流程。
- 结构工程师真实 CAD 使用 `cadDraft -> CadJob -> 受限 CadQuery Worker -> ArtifactVersion`；当前支持规则盒体 `BOX_WITH_LID -> box-with-lid.v1`、单器件安装结构 `COMPONENT_MOUNT -> component-mount.v1` 和受控无器件零件 `FREEFORM_STRUCTURE -> freeform-structure.v1`，不是通用 CAD。盒体/器件模板发布 11 个文件，自由结构单零件发布 9 个文件。
- 直接结构 CAD 先区分建模目标。器件安装结构单选一个服务端受信机械档案；盒体再确认松散/固定安装与内腔尺寸；明确不使用器件的安装板、连接板或自定义零件收集自然语言结构描述并进入 `FREEFORM_STRUCTURE`，不要求机械档案。Sidecar 以 confirmed fact ID/值固化 `intakeSnapshotSha256`，create/retry/finalize/confirm 均拒绝旧轮次；该项目选择不依赖 Spec/BOM。
- 当前机械档案包含由 K10 Hardware Skill 派生的 `unihiker_k10`、既有受信器件，以及用户新增的 DFR0026。Job 固化精确 `profileId + revision + SHA-256`，不按名称猜测尺寸；每个 profile 的活动列表只显示当前精确 revision。
- 专业模式“设置 → 公共知识 → 机械档案”是第三个内部 Tab，点击后懒加载；点击预览会把当前精确 revision 交给服务端，以该 Skill `mechanical.md` 的自然描述为唯一几何来源。`preview_geometry.source_sha256` 匹配时直接使用，否则生成受控几何并回写新 Skill revision；生成失败不打开旧缓存。没有 Skill 结构来源时才明确仅包络预览。普通模式不挂载组件、不请求机械档案 API，不新增右侧一级 Tab。
- XIAO ESP32S3 纵向基线覆盖自动 `80 x 50 x 28 mm`、LEFT USB-C 跨面开孔、五件 `edge_retainer`、真实 Worker、11 文件、单 Solid STEP、watertight STL 和非空 GLB。
- 缺凭据、无效结构化输出、跨项目/线程上下文错误和危险设备操作的失败/确认边界。
- 集中的 PlatformCapabilities / Host Adapter：Web 不支持的串口、上传、Flash、Shell、本地 CAD 和浏览器 Key 提交由前后端双重门禁阻止。

## 7. 暂不实现能力

- 除本基线已列出的 ZW-UX-005～ZW-UX-007 外，不新增 ZW-UX-008～ZW-UX-010 的未排期交互或工作流；ZW-UX-008A 的 schema v23 结构化交接不属于当前基线。
- 新页面、新一级 Tab、新领域系统或三师之外的新专家；v25 私有授权关联只服务现有本地执行安全闭环，不形成新产品领域。
- 游客模式与跨设备项目同步不在产品范围；邮箱账号后使用取代原始游客需求。项目内容仍只保存在本机。
- 自动接受跨专家交接、复制其他智能体完整 Provider 历史或共享私有记忆。
- 第二套工作台、复杂流程画布、多 Agent 可视化编排器。
- 完整在线训练平台、任意代码 CAD、无人工复核制造交付。
- 无确认的真实串口写入、上传、Flash 擦除、固件烧录或不可逆硬件操作。
- 把本地静态/语法检查表述为真实硬件验证，或在代码浮窗内提供上传、Flash 擦除和固件烧录捷径。
- 第二真实 Provider；当前只保留协议扩展点，不把本地模板伪装成生产 AI 成功。

## 8. 已废弃设计

- 旧四专家前台设计已废弃；旧值仅用于迁移和历史线程读取。
- 独立澄清页/独立方案页和替换中央对话的设计已废弃；当前由持久化对话卡驱动。
- 前端旧 `components/clarification/ClarificationCard.tsx`、`SolutionCard.tsx` 已由 `ConversationResponseCard.tsx` 覆盖并删除。
- 本地关键词或固定业务模板作为生产路由、澄清、方案和修订成功结果的设计已废弃。
- 原始 v0.1 PRD 与早期 current-state/phase 文档是历史证据，不是当前实施入口。
- 未完成的结构化 handoff accept/dismiss 设计已暂停，不得从残留任务记录恢复实现；schema v23 是允许无 Spec 的结构化代码回复和历史代码显式导入复用既有 CodeRun/Artifact 图的历史迁移，当前权威 schema 为 v26。

## 9. 当前 schema 版本

当前 SQLite `PRAGMA user_version` 是 **v26**：

- `services/local-api/zhangwen/projects/migrations.py`：`CURRENT_SCHEMA_VERSION = 26`。
- Python/TypeScript `ProjectPersistenceVersion` 均公开 `V26 = 26`，Workspace 返回 `schemaVersion: 26`。
- v24 增加 `cad_jobs`、`artifact_files`、机械档案快照/映射，并保留 v23 的 CodeRun nullable Spec 兼容。
- v25 增加私有 `skill_run_authorizations`，把明确本地执行授权绑定到唯一 PendingItem、SkillRun 和 Project；动作进度本身仍不持久化。
- v26 增加 `projects.owner_subject`、账号级当前项目状态、旧项目认领记录和进度快照迁移重算；升级前创建备份，失败停止启动而不是建立空库。
- v20-v22 旧库按 forward-only migration 升级，并在升级前创建备份和 migration audit；不允许手工下调 `user_version`。

本地身份门面使用独立 `<data_dir>/auth/zhangwen-auth.sqlite3`，其 `PRAGMA user_version` 为 **v2**。认证 schema
只缓存云端 subject、公开账号摘要、本地 session 哈希、离线租约和凭据引用；不保存云密码或 refresh token 明文，也不进入项目包。

## 10. Provider 与本地执行边界

生产中的项目路由、三师回复、澄清、方案、立项书、Spec、代码内容、结构对话语义和教案内容必须调用已配置的 DeepSeek Provider。结构化结果经 Pydantic 校验，最多修复重试一次；缺少配置返回 `CONFIG_MISSING`，Provider JSON/Schema 连续无效返回 `LLM_OUTPUT_INVALID`，结构有效但连续未通过本地工程或安全约束返回 `LOCAL_OUTPUT_REJECTED`，不得持久化伪造业务版本。

`local_recovery_route` 只用于 Repository fixture、历史项目包恢复和不经过生产 HTTP 创建路径的兼容调用；生产 `/api/projects` 在没有 `routerResult` 时仍要求 Provider。CAD 的白名单模板与范围校验是本地安全执行器；用户已确认的结构化 intake 是 target、mode、尺寸、档案或自由结构描述的权威输入，完整 intake 可由本地确定性规范化 `BOX_WITH_LID`、`COMPONENT_MOUNT` 或 `FREEFORM_STRUCTURE cadDraft`。目标不明时先确认，安装座和自由零件不再静默套盒体；这是受限 CAD 编排，不是通用内容 fallback。

SQLite 状态、权限、确认策略、硬件兼容/IO 规则、代码静态检查、CAD 参数边界、文件、Shell、串口和设备操作由本地 Sidecar/Tool Runner 决定。云端 LLM 不直接访问本地文件、Shell、串口、凭据或设备。

Web Development Mode 下，Provider Key 只允许来自 FastAPI 进程环境 `ZHANGWEN_DEEPSEEK_API_KEY` 或已有后端安全凭据；React/Vite 不持有或提交真实 Key。Web 不允许调用串口、上传、Flash、Shell 或本地 CAD 执行端点；已有设备摘要、Mock/Dry Run 结果和 Artifact 仍可读取。

CAD 真实闭环由结构工程师和本地 intake 共同形成声明式 `cadDraft`：Provider 给出结构对话回复，本地只使用用户已确认的目标、模式、内腔尺寸、受信档案或自由结构描述规范化安全字段；缺项必须返回中央 clarification，不使用 PendingItem 收集。`COMPONENT_MOUNT` 恰好固化一个档案并派生底座/可拆压框，`BOX_WITH_LID` 保持盒体自动尺寸与布局，`FREEFORM_STRUCTURE` 使用最多 32 个有界基本体的声明式 CSG 且最终必须单连通。结构 CAD 在 solution/proposal 阶段优先路由，回答与 CAD facts 同事务，明确修订重开 intake并封存旧非活动候选。经中央确认后进入 `CadJobCoordinator` 和受限 CadQuery Worker；Run/Job 固化的 `intakeSnapshotSha256` 必须仍与当前 intake 一致，否则返回 `CAD_INTAKE_REVISED` 并丢弃旧 Worker 发布。Worker 只接受服务端固化的 `CadBuildSpec`，按模板输出 STEP/STL/GLB 和校验报告；新 CAD 二进制存储在 Artifact 文件目录，SQLite 只存元数据。Web 产物页对 `MODEL_3D` 浮窗执行前端门禁，后端对所有 CAD 写操作执行 desktop capability 门禁。

## 11. 代码清单与证据

分类依据是当前入口、FastAPI 路由注册、桌面 API 调用、引用搜索和自动测试，不依据文件名猜测。

### KEEP

| 模块 | 证据 | 结论 |
|---|---|---|
| `apps/desktop/src/App.tsx`、`components/layout/AppShell.tsx`、`CenterChat.tsx`、`RightPanel.tsx` | React 入口直接挂载；AppShell 测试证明中央对话常驻和固定右 Tab | 当前唯一 UI 壳与主对话 |
| `ProjectCreationDialog.tsx`、`hooks/useProjects.ts`、`hooks/useChatStream.ts` | AppShell/CenterChat 直接调用；ProjectWorkspace/Isolation/DeepSeekChat 测试覆盖 | 创建、打开、独立线程、草稿和 SSE 主链 |
| `ConversationResponseCard.tsx` | CenterChat 直接渲染；方案卡和批量澄清测试覆盖 | 当前唯一结构化对话卡入口 |
| `ArtifactsTab.tsx`、`FloatingWindow.tsx` | RightPanel/AppShell 直接调用；RightPanel 测试覆盖同一产物版本和单例浮窗 | 当前产物查看入口 |
| `CodeArtifactEditor.tsx`、`code_agent/{router,repository,validation,validation_worker}.py` | Code Artifact 浮窗直接调用版本读取/保存/验证 API；前后端测试覆盖不可变版本、两个 409 边界、真实退出码和失败不可接受 | 当前 MicroPython 用户代码闭环与本地验证边界 |
| `BoardProfileLibrary.tsx`、`hardware/board_profiles.py` | 专业模式公共知识直接调用；API/UI/runtime 测试覆盖 K10、overlay、revision、reset 和按请求匹配 | 当前开发板 Markdown 事实源和编辑入口 |
| `ProjectCreationDialog.tsx`、`HardwareSkillEditor.tsx`、`hardware/hardware_skills.py`、`projects/router.py`、`experts/context_assembler.py` | 项目硬件 intake、Hardware Skill compiler/draft API、revision CAS、规则与上下文同源及前后端回归覆盖 | Hardware Skill 单一事实源与目录编辑权威链路 |
| `services/local-api/zhangwen/main.py` | 注册全部正式 Router | Sidecar HTTP 入口 |
| `projects/{models,migrations,repository,router}.py` | projects 路由和多个领域仓储直接依赖；repository/migration/API 测试覆盖 | 项目、线程、草稿、账号所有权和 v26 权威持久化 |
| `chat/router.py`、`chat/idea_flow.py` | CenterChat 调用 `/chat/stream`；结构化对话测试覆盖 | 当前澄清/方案会话编排 |
| `solutions/{models,repository}.py`、`artifacts/*` | idea_flow、Proposal 和右侧产物链直接依赖；方案/产物测试覆盖 | 同一 Solution/ArtifactVersion 权威数据 |
| `experts/*`、`coordinator/*` | chat runtime 直接调用；三师 runtime/coordinator 测试覆盖 | 三师最小上下文与本地协调 |
| `llm/*`、`settings/*`、`security/*` | 所有生产生成路由共享配置/Provider/凭据边界；required-real-llm 测试覆盖 | Provider 和凭据权威边界 |
| `packages/contracts` | Desktop 编译依赖；contracts build/typecheck | 跨端 TypeScript 契约；schema 已对齐 v26 |
| Proposal/Spec/Code/CAD/Lesson/Orchestrator/Skill/Hardware/Devices/Package/MVP 模块 | Router 在 `main.py` 注册，WorkTab/Devices/ProjectTools 有调用，均有对应 ZW-005～016 测试 | 保留的既有专业扩展；不是本轮主流程 |
| legacy expert alias 与 migration 映射 | repository、experts config、migration 直接引用；旧项目迁移测试覆盖 | 用户数据兼容，禁止删除 |

### FIX

| 模块 | 证据与问题 | 当前处置 |
|---|---|---|
| `packages/contracts/src/enums.ts` 与 Python persistence enum | 历史 contracts 曾落后于 backend migration/workspace | 当前已补 `V25` 并把授权关联迁移与 Workspace 对齐到 25 |
| `components/right-panel/WorkTab.tsx` | 单文件聚合 Proposal/Plan/Spec/Code/CAD/Lesson/Skill/MVP 大量状态和请求 | 保留行为；后续只能做有测试的内部拆分，不重做 UI |
| `utils/experts.ts` | 当前可在缺 `workspaceStatus` 时由 `ProjectExpertStatus` 再算一次；后端已返回权威 workspaceStatus | 保留兼容 fallback；后续收敛为只显示后端状态并加旧响应测试 |
| `ArtifactsTab.tsx` | UI 同时按 domainStatus 和通用 ArtifactStatus 分组，属于跨端状态映射 | 当前有测试且不阻断；后续把映射固化为共享 contract/selector |
| Python Pydantic 边界与 TypeScript contracts | 状态值和 DTO 是必要镜像，但 `Handoff.handoffType`、可选字段等严格度并非完全一致 | 当前持久化版本对齐 v26；后续建立自动契约对照测试 |
| 机械档案 K10 锁定 | UI 排除 K10 重映射，DELETE 返回 409，CAD 解析固定内置 K10；直接 PUT 尚无等价 guard | 当前作为已知残余风险记录；补服务端 guard 前不声称全 API 层不可重映射 |
| `ProjectRepository` 与 async FastAPI 路由 | 大型同步 SQLite repository 被 async 路由直接调用 | 不影响当前验收；后续以基准和回归测试驱动拆分/线程隔离 |
| `docs/API_EVENTS.md` | 仍残留早期“教案 deterministic template”表述，而实现和 PRD 已是 Provider 内容 + 本地校验 | 以本文件/PRD/DECISIONS 为准，后续单独校正文档 |

### DEPRECATE

| 模块 | 证据 | 当前处置 |
|---|---|---|
| `components/clarification/ClarificationCard.tsx`、`SolutionCard.tsx` | 全仓引用搜索无调用；CenterChat 使用 `ConversationResponseCard`；相关桌面测试覆盖替代入口 | 已删除 |
| `zhangwen/stubs/__init__.py` | 全仓无 import，仅含“后续预留”注释；真实模块均已注册并测试 | 已删除 |
| `projectsApi.ts` 的 `clarifyProject` / `answerClarification` | 只有定义，无桌面调用 | 保留到独立 HTTP API 兼容性确认后删除 |
| `projectsApi.ts` 的独立 Solution wrappers | 只有定义；当前 UI 通过 conversationAction 和 ArtifactsTab 工作 | 保留到独立 HTTP API 调用者与测试迁移完成后删除 |
| `clarification/router.py` 和 `clarification_rounds` 写路径 | Router 仍注册，但仓库内无 UI 调用、无端点行为测试；中央对话已有持久化 question/answer 记录 | 不删除 Router/表；先验证外部调用和历史数据迁移 |
| `solutions/router.py` 的 generate/confirm/revise/restore HTTP 写路径 | Router 仍注册，部分后端测试/潜在外部客户端调用；中央对话已有等价主动作 | 不删除；先建立兼容期和调用证明 |
| 旧专家名称/枚举 | 有 migration、repository、config 调用 | 仅前台设计废弃，兼容值长期保留 |

### UNKNOWN

| 模块/调用关系 | 未确认原因 | 处理规则 |
|---|---|---|
| 独立 `/clarify` 与 `/solution/*` API 的仓库外调用者 | Git 仓库无法证明已安装旧桌面、脚本或项目包是否仍调用 | 没有兼容期、访问审计或替代测试前不移除 |
| `floating_windows` 等历史 UI 状态表的仓库外/旧版本消费 | 当前 React 浮窗主要使用内存状态，但旧包/数据库可能保留记录 | 先做历史数据库回放和包导入测试，不改 schema |
| 真实 Tauri Sidecar 进程异常退出后的端到端恢复 | 持久化孤儿设备操作已自动收敛为可解释终态并有 Repository 测试；真实打包进程生命周期仍属于人工/系统级场景 | 当前不阻断；后续可增加无硬件、无付费 Provider 的桌面进程恢复测试 |

## 12. 专项问题记录

| 检查项 | 发现 |
|---|---|
| 重复领域模型 | Python Pydantic 与 TS contracts 是跨语言必要镜像；旧 `clarification_rounds` 与当前消息 question/answer 记录形成两条澄清持久化路径。未发现可在本轮安全合并的第二套 Project/Solution/Artifact 权威仓储。 |
| 重复 API | 中央 `/chat/stream` 已覆盖澄清与方案动作，同时仍注册独立 `/clarify` 和 `/solution/*` 写 API。 |
| 重复组件 | 两个旧 clarification 卡片无调用且由 ConversationResponseCard 替代，已删除。 |
| 无调用代码 | `zhangwen/stubs/__init__.py` 无 import，已删除；projectsApi 的独立澄清/方案 wrappers 无桌面调用但受 API 兼容风险保护。 |
| 旧四专家残留 | 枚举、迁移和显示名映射仍存在；这是用户数据兼容，不是当前前台专家。 |
| 生产模板 fallback | 项目理解和内容生成未发现生产本地成功 fallback；`local_recovery_route` 是 fixture/package recovery，CAD 白名单模板是受控本地执行器。 |
| contracts / Python 不一致 | schema v26 与账号、进度、设备/CAD/本地授权状态字段已对齐；Handoff 字段严格度和部分 optional 语义仍需自动对照。 |
| schema 漂移 | SQLite、Python 与 TypeScript 已统一为 v26；v24 CAD/Artifact/机械档案、v25 唯一 SkillRun 授权和 v26 账号所有权迁移继续保留。 |
| 前后端重复状态计算 | experts 状态 fallback、Artifact domain/generic 状态分组在前端重复映射；当前保留兼容行为。 |
| 无测试重要路径 | 独立 `/clarify` 端点没有行为测试；真实打包 Sidecar 崩溃恢复没有自动系统测试。当前主流程已新增一个跨 API/Repository 闭环测试。 |
