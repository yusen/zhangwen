# 掌问 PRD

> **Legacy 平台基线（只读参考）**：自 2026-07-31 起，掌问创作端 V3 的权威需求为
> `docs/PRD_CREATOR_V3.md`。本文件继续记录教学端、历史三师能力、兼容迁移和安全约束，
> 但其中与 Creator V3 布局、阶段、导航或设备目录冲突的内容不再约束创作端。

版本：v1.1-closure
日期：2026-07-26
状态：ZW-CLOSURE-001 当前权威产品基线 + 三师系统需求总纲
产品名：掌问
副标题：AI 创客工程工作台

## 1. 文档目的

当前启动与验证阶段：`start-local.bat` 直接启动 contracts、FastAPI Sidecar、Vite 和 Tauri 组成的完整本地应用，并在同一启动会话中校验桌面 capability token。它不隐式扫描串口或上传代码；串口扫描、设备连接和部署操作均由用户在桌面应用的“设备”Tab 中明确触发。Browser Host 仍运行同一个 React 应用并访问同一个 FastAPI Sidecar、SQLite 和三师领域层；Web 模式继续禁用真实文件、Shell、串口、Flash、CAD 和设备副作用。

本文档整合当前仓库中的 README、架构文档、UI 契约、验收文档、三师系统规格、阶段说明、任务记录与交接记录，作为“掌问”当前最新、最全的产品需求文档。

2026-07-28 的 M7 普通模式体验以“对话即平台”为当前覆盖规则：普通用户只需描述想法，
系统自动决定可逆低风险细节，只在产品方向不明确时询问一个关键问题；历史多问题数据继续
兼容，但前台逐个自然呈现。普通模式只保留对话、项目、连接和设置，右栏按需展开；工程
工作区与完整诊断移入专业模式。设备扫描、连接、上传、复位和 Flash 的明确确认规则不变。

本 PRD 的基线来源包括：

- `README.md`
- `docs/archive/PRD-v0.1-original.md`
- `docs/ARCHITECTURE.md`
- `docs/UI_CONTRACT.md`
- `docs/ACCEPTANCE.md`
- `docs/three-expert-current-state-analysis.md`
- `docs/three-expert-phase-1-domain.md`
- `docs/three-expert-phase-2-runtime.md`
- `docs/three-expert-phase-3-coordinator.md`
- `docs/three-expert-phase-4-project-creation.md`
- `docs/three-expert-phase-5-workspace-ui.md`
- `tasks/ZW-UX-003-three-expert-system.md`
- `HANDOFF.md`
- `specs/three-expert-system/palmq_three_expert_framework_v1/`

## 2. 产品概述

掌问是一款面向创客教育、嵌入式原型开发和 AI 硬件项目实践的本地优先桌面工作台。用户用自然语言描述项目想法，系统通过三位用户可见专家协助完成需求澄清、方案设计、硬件选型、代码生成、结构设计、产物管理、设备调试和项目交付。

产品采用“三个用户可见专家 + 两个用户不可见系统角色”的结构：

用户可见专家：

- 问题引导师 `problem_guide`
- 智能工程师 `smart_engineer`
- 结构工程师 `structure_engineer`

用户不可见系统角色：

- 主路由 `entry_router`
- 项目协调器 `project_coordinator`

智能工程师通过 Skill Registry 扩展硬件、嵌入式、IoT、数据分析、视觉推理和 AI 部署能力。Skill 不是 Agent，不显示为专家，不拥有独立人格、长期对话或私有记忆。

三位可见专家各自拥有一个目录化 Agent Skill 包作为行为配置。包以标准 frontmatter 的 `SKILL.md` 为唯一运行入口，可按需加载声明过的 Markdown 参考文件；它与 Skill Registry 中受 Tool Runner 控制的执行能力是两层不同概念。

## 3. 产品目标

1. 让非专业用户可以从一句创意开始，逐步得到可执行的创客工程方案。
2. 将需求澄清、硬件实现、软件实现、结构设计和设备调试纳入同一个项目工作台。
3. 保持中央主对话为核心交互，不让产物、设备或内部流程替代主对话。
4. 用三师系统降低用户理解成本，隐藏主路由、协调器、模型、工具链和 Skill 参数。
5. 通过共享事实、项目决策、产物依赖、任务和待处理事项维护长期项目状态。
6. 保留旧项目、旧专家、旧线程和旧产物的兼容读取能力。
7. 对文件、shell、串口、Flash 擦除、固件烧录等外部效果保留本地 Tool Runner 和确认策略。

## 4. 非目标

当前阶段不承诺：

- 完整在线 GPU 模型训练平台。
- 全自动复杂 CAD 或无人工检查的制造交付。
- 通用 CAD、自由曲面、CAE、CNC、切片、任意插件或通用约束求解；当前真实建模只支持 `BOX_WITH_LID -> box-with-lid.v1`、单器件 `COMPONENT_MOUNT -> component-mount.v1`、受控声明式 `FREEFORM_STRUCTURE -> freeform-structure.v1` 和固定 `UNIHIKER_K10_PHOTO_ALBUM -> unihiker-k10-photo-album.v1`。
- 无用户确认的设备烧录、Flash 擦除或真实硬件写入。
- 复杂流程画布、专家群聊或多 Agent 可视化编排器。
- 将 EntryRouter、ProjectCoordinator、Model Router、Skill 参数或系统提示词暴露给普通用户。
- 新建第二套平行工作台或引入新的 UI 框架、全局状态管理框架。

## 5. 目标用户

主要用户：

- 中小学、职校、高校创客课程教师。
- 想做 ESP32、传感器、结构件和 AI 小项目的学生与创客。
- 需要快速完成原型验证的硬件/软件入门开发者。

典型需求：

- “我想做一个智能花盆。”
- “ESP32 读取 DHT22 并上传 MQTT。”
- “帮我设计一个外壳并导出 STL。”
- “把这个项目变成课堂活动和评价量规。”

## 6. 产品不可变规则

1. 产品名固定为“掌问”，副标题固定为“AI 创客工程工作台”。
2. 中央区域始终保持主对话；查看产物或设备详情只能使用右侧栏、浮窗、覆盖层或抽屉。
3. 右侧一级 Tab 固定为“工作 / 产物 / 设备”。
4. 前台一次只显示一套当前推荐实现方案；方案必须同时包含实现逻辑和硬件方案。
5. 前台只显示三位专家：问题引导师、智能工程师、结构工程师。
6. 主路由和项目协调器不可见。
7. 智能工程师 Skill 不显示成专家或子 Agent。
8. 前台一个项目只显示一条对话时间线；底层三位专家使用独立工作区、独立线程和私有记忆，不创建共享 Provider 会话。
9. 工作页同一时间只突出一个当前待处理事项。
10. 云端 LLM 不直接操作文件、shell 或串口；本地 Tool Runner 执行并检查权限。
11. MicroPython 日常代码上传首选 USB 串口；不得无故擦除 Flash 或重刷固件。
12. 普通模式隐藏 Agent、Skill、模型和工具链细节；专业模式才允许展开。

## 7. 当前技术栈

桌面端：

- Tauri 2
- Rust
- React
- TypeScript
- Vite
- Vitest / Testing Library

本地服务：

- Python
- FastAPI
- WebSocket / streaming chat path
- SQLite

共享契约：

- `packages/contracts`
- TypeScript 枚举和 API 类型

LLM 与运行时：

- `services/local-api/zhangwen/llm`
- 当前真实云端 Provider 为 DeepSeek。
- 自动测试使用 fake provider，不调用真实付费 LLM。

设备与工具：

- 本地 Tool Runner / sidecar 路径执行串口、文件和设备相关能力。
- 真实 `mpremote`、`esptool`、Flash 擦除、固件烧录必须保留确认点。

## 8. 总体架构

```text
用户
→ React/Tauri 工作台
→ 应用服务层
→ EntryRouter / AgentRuntime / ProjectCoordinator / ContextAssembler
→ Repository / ToolRunner / LLM Provider
→ SQLite / 本地文件 / 串口设备 / 受控云端服务
```

分层职责：

- UI 层负责项目创建、三栏工作台、专家对话、结构化卡片、右侧工作/产物/设备展示。
- 应用服务层负责用例编排、事务边界、API 请求和响应。
- 领域层负责 Project、ExpertWorkspace、ConversationThread、SharedFact、ProjectDecision、Artifact、Task、Handoff、PendingItem 等状态。
- Runtime 层负责 EntryRouter、AgentRuntime、SkillRuntime、ContextAssembler、ProjectCoordinator。
- Infrastructure 层负责 SQLite、文件存储、LLM Provider、ToolRunner 和设备适配。

关键实现位置：

- 三师运行时：`services/local-api/zhangwen/experts/`
- 项目领域和持久化：`services/local-api/zhangwen/projects/`
- 协调器：`services/local-api/zhangwen/coordinator/`
- Skill Registry：`services/local-api/zhangwen/skills/registry.py`
- 产物：`services/local-api/zhangwen/artifacts/`
- 方案流：`services/local-api/zhangwen/chat/idea_flow.py`、`services/local-api/zhangwen/clarification/`、`services/local-api/zhangwen/solutions/`
- 桌面工作台：`apps/desktop/src/components/layout/`
- 右侧面板：`apps/desktop/src/components/right-panel/`
- 三师显示工具：`apps/desktop/src/utils/experts.ts`

## 9. 三师系统

### 9.1 问题引导师

ID：`problem_guide`
显示名：问题引导师
定位：帮助用户把模糊想法变成可执行项目。

职责：

- 创意引导。
- 需求澄清。
- 问题定义。
- 项目目标、约束、使用场景整理。
- 实验方案。
- PBL、课程设计、教案、任务单和评价量规。
- 当前推荐方案形成后，显式提供“生成立项书 / 生成教案版本”两条产物路线；当前临时流程确认表格式实施基线后跳过 Spec，项目已有智能工程师时直接交接执行。底层教案/Spec 能力保留兼容，但不作为问题引导师前台继续条件。

主要产物：

- `project_brief`
- `project_proposal`
- `experiment_plan`
- `teaching_design`
- `lesson_plan`
- `learning_task`
- `assessment_rubric`

限制：

- 不直接执行硬件控制。
- 不直接生成最终烧录动作。
- 不绕过用户确认写入 confirmed fact。

### 9.2 智能工程师

ID：`smart_engineer`
显示名：智能工程师
定位：把方案转化为硬件、软件、IoT、数据和 AI 部署实现。

职责：

- 硬件选型。
- BOM。
- IO Map。
- 接线。
- 电气兼容检查。
- MicroPython / Arduino / STM32 等代码。
- 代码审查与 Mock 测试。
- MQTT / HTTP / IoT 数据流。
- 数据采集和数据分析。
- AI 模型部署和视觉推理。
- 项目打包。

主要产物：

- `hardware_plan`
- `bom`
- `io_map`
- `wiring_table`
- `electrical_check`
- `source_code`
- `iot_contract`
- `data_analysis`
- `ai_deployment`
- `mock_test_report`
- `project_package`

智能工程师 Skills：

- `hardware-selection`
- `bom-generation`
- `io-map`
- `wiring`
- `electrical-check`
- `micropython-generation`
- `arduino-generation`
- `code-review`
- `mock-test`
- `iot-mqtt`
- `iot-http`
- `data-acquisition`
- `data-analysis`
- `ai-deployment`
- `vision-inference`
- `project-packaging`

每个 Skill 必须声明：

- ID
- 所属专家
- 输入结构
- 输出结构
- 所需工具
- 风险等级
- 确认策略
- 产物类型

### 9.3 结构工程师

ID：`structure_engineer`
显示名：结构工程师
定位：把项目需求和硬件约束转化为外观、结构、装配和打印方案。

职责：

- 外观设计。
- 内部结构。
- 安装和装配。
- 尺寸、公差、可打印性。
- STL / STEP / 3MF。
- 打印参数建议。

主要产物：

- `appearance_concept`
- `structure_spec`
- `dimension_sheet`
- `assembly_plan`
- `stl_model`
- `step_model`
- `three_mf_model`
- `print_profile`
- `printability_report`

限制：

- 只能读取必要设备摘要、主控型号、元件尺寸、接口位置和安装信息。
- 不能执行烧录、串口控制或设备重启。
- 只能输出声明式 `cadDraft`，不能输出或执行 CadQuery/Python、Shell、主机路径或任意插件代码。

当前真实 CAD 交付边界：

- `cadDraft -> CadJob -> 受限 CadQuery Worker -> ArtifactVersion -> STEP/STL/GLB -> 中央确认` 是唯一生产链路；旧 `/cad/generate` 只返回 HTTP 410。
- 直接进入结构工程师请求建模时先区分目标：安装座、固定底座、托架、支架或压框进入单器件 `COMPONENT_MOUNT` 并单选一个服务端受信机械档案；外壳、保护壳、盒体或容器进入 `BOX_WITH_LID`；明确不使用任何器件、按尺寸创建安装板/连接板/自定义零件进入 `FREEFORM_STRUCTURE`，只收集自然语言结构描述，不要求机械档案；明确的行空板 K10 电子相册/相册支架请求进入固定 `UNIHIKER_K10_PHOTO_ALBUM`。目标不明确时先显示四选一目标卡，不要求用户先生成 Spec/BOM。
- 已处于方案草稿、方案确认或立项书草稿阶段时，结构工程师 CAD 请求仍优先进入 CAD Runtime，不被通用方案分支截走。当前消息、来源 `cad_*` 澄清卡或最近结构线程 CAD 语境加“继续/修改”等表达均可延续；普通结构咨询不触发 CAD 门禁。
- 整组答案、问题 answered 状态和 CAD SharedFact 必须同事务保存；非法尺寸或档案整体回滚并允许重新提交，重复 turn 不得重放旧 facts。明确修改或新的三轴尺寸开启新 intake，同时封存旧的非活动 CAD 候选、旧 pending CAD 卡和对应聊天/产物投影，不永久复用首版 mode、尺寸和档案。
- 本地服务必须为每个 CAD 草稿固化包含 confirmed fact ID/值的 `intakeSnapshotSha256`。创建 Job、重试旧 Job、Worker 最终化和确认 CAD 都必须与当前 intake 比较；失配返回 HTTP 409 `CAD_INTAKE_REVISED` 且不可重试。已有 `QUEUED/RUNNING` Job 不自动取消，但旧结果不得发布为待确认版本；最后一个 `APPROVED` 版本在新版本确认前继续保留。
- 专家身份以项目持久 `projectExpertId` 为准；请求字段不能把其他专家提升成结构工程师。未进入服务端 CAD workflow 时，Provider 返回的 `cadDraft` 或 `cad_*` 问题必须失败关闭。
- 缺输入时必须返回结构化澄清卡，不能只用纯文本或 PendingItem 追问；信息齐全后，即使 Provider 只返回说明文本，本地 intake 也会按已确认目标规范化为 `BOX_WITH_LID`、`COMPONENT_MOUNT`、`FREEFORM_STRUCTURE` 或固定 `UNIHIKER_K10_PHOTO_ALBUM` 草稿，避免对话完成但没有生成入口。
- `BOX_WITH_LID -> box-with-lid.v1` 生成规则外壳、底壳和上盖；`COMPONENT_MOUNT -> component-mount.v1` 基于恰好一个已确认机械档案生成安装底座、可拆压框和器件参考预览；`FREEFORM_STRUCTURE -> freeform-structure.v1` 把自然语言转换为最多 32 个有界 `box/rounded_box/cylinder` 的顺序 `add/cut`，最终必须得到一个连通实体；`UNIHIKER_K10_PHOTO_ALBUM -> unihiker-k10-photo-album.v1` 由本地固定尺寸和 16 阶段加/减法构造。盒体/器件类保持 11 文件导出，单零件类导出 9 文件；这不是通用 CAD 平台，未明确目标的结构请求不得静默规范化成盒体。
- 机械事实来自五个版本化受信档案：K10、行空板超声波传感器、XIAO ESP32S3、Grove OLED 0.96 英寸和 Grove Button。项目澄清选项由服务端生成不可伪造的虚拟硬件 ID；Job 固化并重验精确 `profileId + revision + SHA-256`，不按显示名猜测尺寸，也不把 XIAO 当作通用 ESP32 DevKitC。
- 缺失的外壳宽/高/深由本地使用档案包围盒、旋转、安装面、偏移、边缘间隙和器件间距确定性求解；显式尺寸不被覆盖，空盒内腔下限为 `80 x 50 x 28 mm`。
- 桌面端在中央主对话发起建模/确认，右侧“工作”只显示 Job 进度，右侧“产物”通过浮窗预览 GLB；Web 只读，不执行 CAD 写操作。
- 桌面端收到 `CAD_INTAKE_REVISED` 后刷新当前项目并提示使用最新草稿，不得在历史卡继续创建、重试或确认旧快照。

### 9.4 Agent Skill 包

三师各自对应一个固定包：`problem-guide`、`smart-engineer`、`structure-engineer`。每个包包含系统锁定的 `manifest.json`、必需的 `SKILL.md` 和 manifest 白名单内的 `references/*.md`。

- `manifest.json` 是身份、canonical ID、Registry Skill 绑定、产物类型和安全边界的权威来源，不允许通过设置修改。
- `SKILL.md` 定义该智能体的行为、职责和参考文件入口；参考文件只在当前请求命中其加载关键词时加入上下文。
- 内置包只读；用户保存写入当前数据目录的同路径 overlay，并用 revision 做乐观并发检查。恢复默认只删除对应 overlay。
- 只接受 UTF-8 Markdown；拒绝绝对路径、`..`、未声明文件、错误 frontmatter、断链和超限内容。
- 修改内容只进入下一次目标智能体的 Provider system prompt，不复制到另外两位智能体。
- Markdown 不授予工具、文件、Shell、串口、设备或 CAD 权限。任何外部效果仍必须经过 Registry Skill、SkillRuntime、Tool Runner 和确认策略。
- 普通模式不请求、不渲染包配置；专业模式设置明确区分“行为项目”和“执行能力”。“打开行为项目”关闭设置覆盖层并使用现有浮窗显示 `SKILL.md + references/` 文件树和 Monaco Markdown 编辑器。
- 行为项目使用 `agent-package:{expertType}` 单例 key；最小化保留多文件草稿，关闭或第四浮窗淘汰脏编辑器前确认，409 刷新服务端 revision 但保留本地草稿。

### 9.5 Hardware Skill 包

每个硬件器件对应 `<data_dir>/hardware-skills/<skill-name>/` 下的一个目录化 Skill。包采用 `README.md + SKILL.md + assets/ + references/ + models/ + examples/ + tests/`；电气、兼容和机械事实使用受控 Markdown 中带版本标记的 JSON fenced block，已验证建模源码以 manifest 白名单中的 `models/cadquery.py` 保存。

- `manifest.json` 只保存逻辑 ID、显示名、状态、来源、文件白名单和 revision，不承载电气真值。
- 电气事实必须区分四类语义：`voltage` 是推荐/标称工作点，`voltageMin/voltageMax` 是器件连续允许供电范围，`supplyVoltages` 是 MCU/POWER 实际对外提供的离散电源轨，`logicLevel` 是独立信号或 ADC 接入基线。K10 的板级输入为 5V，但外设供电轨为 3.3V/5V；二者不得混用。
- `references/specifications.md` 是类别、电气、库存、价格、适龄、安全标签和验证来源的唯一权威源；`references/compatibility-rules.md` 是器件规则声明的唯一权威源。
- 声明结构能力的包必须同时包含 `references/mechanical.md` 与 `models/cadquery.py`。前者的 `## 自然语言描述` 是 3D 预览几何的唯一编写来源；`profile.preview_geometry` 只是应用按需生成、带 `source_sha256` 且可重建的缓存，不要求作者维护第二份几何。后者保存与 SHA-256 绑定的已验证参考源码，固定为 `REFERENCE_ONLY`，普通 Skill 保存和预览都不能把它变成任意 Python 执行入口。
- SQLite `mechanical_profile_versions` 和 `hardware_mechanical_links` 与 `hardware_components` 一样只是当前 ACTIVE Skill revision 的可重建投影；机械档案 revision 由 Skill revision 派生并在同一保存事务内切换精确关联。
- SQLite `hardware_components` 只作为项目外键、查询和旧 API 的可重建投影；直接修改 `electrical_json` 不得改变规则结果。Skill 保存成功后由 Sidecar 同步投影。
- 规则操作符只允许 `range-overlap`、`sum-lte`、`unique`、`contains-any` 和 `required-if`；不支持 Python、Shell、动态表达式、任意函数或文件路径执行。
- 旧组件首次读取时幂等导出为 Hardware Skill；已有器件 Markdown 说明合并为 references。公共列表逐包校验并隔离迁移或编译失败包，仍返回其余有效 ACTIVE Skill；直接读取、编辑或选择该失败包时返回受控 422，并在调用 Provider 前失败关闭，不生成可被误认为 ACTIVE 的列表项。
- 三位工程师从同一 ACTIVE Skill revision 读取参数、规则摘要和工程说明；未保存编辑、DRAFT、ARCHIVED 或 INVALID 包不进入上下文。
- 客户可以上传受控 Markdown/TXT/JSON/CSV/PDF 或通过创建器内对话补充信息。Sidecar 先建立 DRAFT 会话、列出来源/缺项/诊断并执行本地编译；PDF 只在本地以 `pypdf` 提取有界文本，扫描件不做 OCR。只有无阻塞问题且用户明确确认后才原子发布 ACTIVE。
- 上传件视为不可信数据，只在本地提取有界文本；云端 LLM 可返回结构化候选，但不能直接读写目录、激活 Skill、执行规则或操作设备。

### 9.6 真实动作与本地执行授权

- 专家回复执行期间，中央气泡显示 Sidecar 通过 `chat.progress / PROGRESS` 发出的真实阶段；动作、状态和中文标签使用固定词表，禁止从模型正文、推理内容或客户端计时生成。
- 需要本地副作用时先显示“等待本地执行授权”。确认事项必须由服务端绑定到唯一 Project、PendingItem、SkillRun 和原对话消息；Web 模式不能领取，桌面 capability 通过后才可原子恢复。
- 只有 ToolRunner 已写入真实 `RUNNING` 记录才能显示“正在执行本地工具”。成功、失败、取消和用户停止都必须清理瞬态动作、刷新确认事项并保留原专家回复；历史消息不回放动作时间线。
- 普通模式只显示清洗后的中文动作，不显示 Skill/Tool ID、命令、路径、端口、payload、工具输出、原始错误、模型推理或真实硬件标识。

## 10. EntryRouter

EntryRouter 是用户不可见的主路由。它用于项目创建和输入归属判断，不作为专家显示。

结构化输出：

- `intent`
- `projectName`
- `initialExpert`
- `recommendedExperts`
- `confidence`
- `reason`
- `requiresClarification`

规则：

1. 使用 JSON Schema 或等价校验约束输出。
2. 校验失败后重试一次。
3. 仍失败时返回 `LLM_OUTPUT_INVALID`，不得用确定性关键词或本地模板伪装成生产 AI 成功结果。
4. 结构可解析但连续两次不满足本地工程或安全边界时返回 `LOCAL_OUTPUT_REJECTED`；应用或 Sidecar 重启遗留的生成返回 `GENERATION_INTERRUPTED`。三类错误必须附带不同的中文解决建议和可执行动作。
5. 用户明确指定专家时优先。
6. 模糊需求默认进入问题引导师。
7. 明确技术实现进入智能工程师。
8. 明确结构外壳进入结构工程师。
9. 创建页只展示项目名、推荐专家和用户可理解的提示，不展示内部路由置信度或原始 JSON。

## 11. 云端 LLM 决策边界

用户可见的澄清、方案生成和方案修改必须由云端 LLM 结构化输出驱动，不得退回到本地硬编码产品模板。

要求：

1. 问题引导师的引导问题应一次性从云端 LLM 获取 `questions[]`，而不是分三次用本地阶段规则喂给 LLM。
2. 推荐方案生成必须使用已澄清答案、最近对话、已确认事实、项目名称和初始想法作为上下文。
3. 点击“修改方案”后，修改范围判断和新版本内容必须通过云端 LLM 结构化输出完成。
4. 本地 repository 只负责持久化 LLM 输出、版本关系和状态，不拥有关键词式方案修改规则。
5. 云端 LLM 只能提出候选事实、候选冲突、方案草稿、修改建议和说明；不能直接覆盖 confirmed fact，不能直接执行 ToolRunner。
6. 确定性安全状态、数据库状态机、唯一高亮事项和产物过期传播由本地领域服务维护。

当前实现基线：

- `services/local-api/zhangwen/chat/idea_flow.py` 已移除三步本地澄清模板。
- `ClarificationService.generate_solution()` 负责 LLM 方案生成。
- `ClarificationService.revise_solution()` 负责 LLM 方案修改。
- `SolutionRepository.create_revision_from_llm()` 负责保存 LLM 修改版本。
- 桌面方案/澄清卡支持多问题渲染和按 `messageId:questionId` 记录回答状态。

## 12. ContextAssembler

ContextAssembler 为当前专家组装最小必要上下文。

允许注入：

- 项目摘要。
- 当前任务。
- 必要 confirmed facts。
- 必要 proposed facts。
- 项目决策。
- 必要上游产物和版本。
- 当前高亮 PendingItem。
- 当前设备摘要。
- 与当前任务相关且数量受限的本地公共硬件知识；只包含技术参数、安全标签和简短说明，不注入库存、价格或审计元数据。

禁止注入：

- 完整无关聊天历史。
- 其他专家私有草稿。
- 专家私有记忆。
- 设备完整日志。
- 系统提示词和内部 JSON。

优先级：

- 已确认事实优先于模型摘要。
- 当前任务和相关上游产物优先于历史闲聊。
- 专家只看到完成当前任务需要的信息。

## 13. ProjectCoordinator

ProjectCoordinator 是用户不可见的确定性状态协调器。

职责：

- SharedFact 生命周期管理。
- ProjectDecision 写入和引用。
- Task 状态机。
- Handoff 状态机。
- PendingItem 候选队列。
- 唯一高亮事项选择。
- ArtifactDependency 同步。
- 上游新版本确认后的下游过期传播。
- 专家状态计算。

ProjectCoordinator 不负责：

- 生成专业内容。
- 替用户确认事实。
- 覆盖专家产物。
- 暴露为聊天对象。

唯一高亮事项优先级：

1. `safety`
2. `blocking`
3. `conflict`
4. `confirmation`
5. `missing_input`
6. `normal`

同级排序：

- 影响专家更多者优先。
- 创建更早者优先。
- 位于关键路径者优先。

## 14. 核心领域模型

### 14.1 Project

项目是用户创客工程的顶层聚合，包含名称、目标、初始想法、当前专家、共享上下文、参与专家、任务、产物和设备摘要。

### 14.2 ExpertWorkspace

每个参与专家拥有独立工作区。

字段要求：

- `expertType`
- `projectExpertId`
- `conversationId`
- `workspaceStatus`
- `legacyExpertType`
- `archivedLegacyThread`
- `removedAt`

状态：

- `not_started`：未开始
- `waiting_dependency`：等待依赖
- `in_progress`：进行中
- `awaiting_user`：待用户确认
- `completed`：已完成
- `outdated`：产物已过期

### 14.3 ConversationThread

前台显示项目级聚合时间线，底层三位专家必须使用独立线程。

要求：

- 消息查询和写入必须按 `threadId`。
- 允许按项目加载各智能体已授权的持久化线程并按时间聚合展示，但消息写入和 Provider 历史读取必须按目标 `threadId`。
- 禁止三位专家共用同一个 `threadId`。
- 禁止用消息上的 expert 字段模拟线程。
- 禁止让三位专家共用一个 Provider 会话；前台聚合展示不等于多人群聊。

发送消息必须携带：

- `projectId`
- `expertWorkspaceId`
- `threadId`
- `expertType`

Agent 返回消息必须写入同一个线程。

### 14.4 SharedFact

共享事实用于保存跨专家可用的项目事实。

状态：

- `proposed`
- `confirmed`
- `superseded`
- `rejected`

规则：

- LLM 和专家只能提出 proposed fact。
- confirmed fact 不能被专家直接覆盖。
- 替代事实确认后，旧 confirmed fact 变为 superseded。
- confirmed fact 必须有确认来源。

### 14.5 ProjectDecision

项目决策用于记录用户或系统确认后的关键选择，例如主控型号、供电方案、通信协议、结构外形和教学目标。

规则：

- 决策需可追踪来源。
- 决策可引用 SharedFact、Artifact 或 PendingItem。
- 决策变更应触发协调器检查影响。

### 14.6 Artifact

产物是专家输出的版本化结果。

状态：

- `draft`：草稿
- `pending_confirmation`：待确认
- `confirmed`：已确认
- `outdated`：已过期
- `archived`：已归档

规则：

- 草稿可由所属专家更新。
- confirmed 产物必须有版本号。
- 旧版本不删除、不覆盖。
- 旧产物保留原创建专家信息。
- 其他专家不能直接编辑所属专家的产物。
- outdated 产物不能作为新任务的默认输入。

### 14.7 ArtifactDependency

产物依赖必须保存具体上游：

- `artifactId`
- `version`
- 可选 `versionId`

上游 confirmed 新版本出现后，依赖旧版本的下游产物应被标记为 `outdated`，并记录过期原因。

### 14.8 Handoff

交接用于 Agent 明确提出跨领域任务时转交给其他专家。

状态：

- `proposed`
- `accepted`
- `in_progress`
- `completed`
- `rejected`
- `cancelled`

规则：

- 手动切换专家不创建 Handoff。
- Handoff 不复制完整聊天。
- 接收专家只读取必要 confirmed facts、决策和相关产物。
- 交接包必须可审计。

### 14.9 Task

任务用于领域执行和协调。

状态：

- `queued`
- `ready`
- `running`
- `blocked`
- `awaiting_user`
- `completed`
- `failed`
- `cancelled`

### 14.10 PendingItem

待处理事项用于右侧“工作”页。

规则：

- 同一项目最多一个 `isHighlighted=true` 的 open PendingItem。
- 前端不得自行重新计算优先级。
- 处理后调用应用服务更新相关 SharedFact、ProjectDecision 或 Task，并触发协调器重新计算。
- 其他事项放入“后续事项”。

## 15. 项目创建流程

目标流程：

1. 用户输入一句创意。
2. 用户完成输入后显式点击“分析并推荐”，前端才调用 `/api/projects/suggest`；输入过程不自动请求模型。
3. EntryRouter 返回项目名、初始专家、推荐专家、原因和是否需要澄清。
4. 推荐成功后才显示“选择项目硬件”；用户可分类、搜索、多选或跳过，空选择表示可在智能体规划后再补充。
5. 用户可修改项目名、参与专家和硬件选择；修改创意会使旧推荐立即失效，必须重新分析，修改硬件选择不会使已完成分析失效。
6. 点击“开始项目”。
7. Sidecar 校验所选组件仍为 ACTIVE，并运行 Hardware Skill/Rule Engine；未知、归档或 FAIL 返回 `422 PROJECT_VALIDATION_FAILED`，WARNING 以中文文本返回后继续。
8. 后端在单一事务内创建 Project。
9. 只为用户选择的三师创建 ExpertWorkspace。
10. 每个专家创建独立 ConversationThread 和私有记忆；同时创建一份项目级输入草稿。
11. 写入原始创意作为初始专家线程的唯一首条用户消息；硬件摘要不得拼入可见消息正文。
12. 写入 proposed `initial_idea`，并写入 confirmed `preferred_hardware` SharedFact；空选择仍表示允许按需求推荐。
13. 初始化 ProjectCoordinator、Task 和第一个 highlighted PendingItem。
14. 前端进入项目唯一对话时间线，初始回复目标为 EntryRouter 选择的专家。

要求：

- 创建接口支持 `idempotencyKey`。
- 重复提交相同 key 返回已创建项目。
- 任一步失败时事务回滚，不留下半成品。
- 旧项目打开不重新路由、不强制重建。
- 硬件选择是分析后的可选本地确认，不是 LLM 澄清卡，也不参与入口路由。只有当前选择无法覆盖规划时，三师才返回受控缺件能力清单；用户可从中央消息或项目工具打开选择器补充器件。

## 16. 项目工作台

工作台固定为左、中、右三栏。

### 16.1 左侧

固定包含：

- 新建项目
- 项目列表
- 项目资源

项目列表：

- 可直接打开已有项目。
- “新建项目”固定在项目列表上方，具体创建表单使用覆盖层。
- 项目切换不得销毁中央对话组件。

添加专家：

- 只显示尚未加入的三师成员。
- 入口位于中央输入区已有工程师胶囊末尾的“＋ 添加工程师”，只影响当前项目。
- 添加时创建或恢复 ExpertWorkspace 和独立 ConversationThread。
- 添加成功后可直接把下一条回复目标切到该工程师。
- 不复制完整聊天。
- 不删除或修改已有专家数据。

移除专家：

- 软移除，不硬删除。
- 至少保留一位专家。
- 当前回复目标被移除前切换至其他智能体。
- 历史对话、产物和任务保留。
- 有阻塞任务或产物依赖时提示影响。
- 操作需要确认。

项目资源：

- 展示上传文件、图片、数据文件、数据集、器件资料、结构参考、设备资料、外部文档引用。
- 资源属于项目。
- 不自动成为 confirmed fact。
- 预览资源不能销毁当前对话。
- 上传复用现有 Tauri 文件能力。

### 16.2 中央

中央只有一种项目主状态：

```ts
type MainWorkspaceView =
  | { type: "project_conversation"; projectId: string }
```

要求：

- 中央主工作区始终常驻。
- 右侧页签不能替换中央对话。
- 不加入共享 Provider 群聊、流程画布、任务看板替代对话、产物页全屏替代对话或设备页全屏替代对话。

项目输入区至少显示：

- 当前项目参与智能体胶囊。
- 尚有缺失成员时显示“＋ 添加工程师”，展开后只列出当前项目未加入的三师成员。
- 当前默认回复智能体。
- `@智能体` 的明确路由入口。
- 每条智能体回复的智能体名称。

不得显示：

- 系统提示词。
- 内部 JSON。
- 主路由置信度。
- 项目协调器内部状态。
- 模型推理过程。
- 完整 Skill 参数。

### 16.3 右侧

右侧一级 Tab 固定：

- 工作
- 产物
- 设备

切换右侧页签不得改变：

- 当前项目。
- 当前回复目标。
- 中央滚动位置。
- 输入草稿。
- 未完成消息状态。
- 产物筛选条件。

## 17. 对话和消息

聊天消息类型应支持：

- `text`
- `choice_card`
- `proposal_card`
- `confirmation_card`
- `skill_run`
- `artifact_card`
- `handoff_notice`
- `error`
- `retry`
- `solution_card`

要求：

- 结构化内容不得全部拼成大段 Markdown。
- 卡片历史可回看。
- 用户提交选项后不可重复提交。
- 未确认答案不能直接覆盖共享事实。
- 提交后继续调用当前 Agent Runtime。

输入区保留：

- 文本输入。
- 发送。
- 停止生成。
- 按失败分类提供“重新/继续生成”“修改原需求”或“检查模型设置”，不能只有不可操作的“可重试”文字。
- 上传或引用项目资源。
- 项目参与智能体胶囊和当前回复目标标识。
- `@智能体` 指定下一位回复者。

禁止：

- 直接显示全部 Skill 列表。
- 让用户手工选择内部 Skill 执行链。

## 18. 智能体路由和状态保持

点击输入框上方智能体胶囊或输入 `@智能体` 后：

1. 更新下一条消息的目标专家。
2. 中央继续显示同一项目聚合时间线。
3. 消息写入目标专家独立线程。
4. Provider 只读取目标专家的有界历史和项目共享上下文。
5. 保持项目级输入草稿、滚动位置和右侧当前页签。
6. 不创建 Handoff。
7. 不复制其他专家聊天记录到目标线程。
8. 不改变项目共享事实。

草稿隔离键：

```ts
`${projectId}`
```

切换项目、回复目标和右侧页签时保持：

- 专家线程。
- 项目输入草稿。
- 滚动位置。
- 未完成消息状态。
- 右侧当前页签。
- 产物筛选条件。

## 19. 工作页

工作页读取领域层唯一高亮事项，并将其作为进度摘要：

```ts
pendingItem.isHighlighted === true
```

高亮事项显示：

- 标题。
- 描述。
- 原因。
- 影响专家。
- 可选方案（如有）。
- 当前状态和影响专家。
- 查看详情或进入原有领域操作（如有）。

需要用户补充需求、参数或偏好时，不创建“确认或处理” PendingItem；由专家回复中的结构化 `clarification` 整组收集，并沿用 `sourceMessageId`、`clientTurnId` 和一次批量提交事务。只有执行计划、产物版本或本地副作用授权等会推进状态的操作才进入中央确认卡。

真正的领域处理后：

1. 调用应用服务。
2. 更新 SharedFact、ProjectDecision 或 Task。
3. 将当前 PendingItem 置为 resolved 或 dismissed。
4. 调用 ProjectCoordinator 重新计算。
5. 刷新新的高亮事项。

任务列表可轻量展示：

- 当前任务。
- 等待任务。
- 阻塞任务。
- 最近完成任务。

不得建设复杂项目管理看板。

## 20. 产物页

产物页展示统一项目产物库。

支持：

- 当前专家。
- 全部专家。
- 类型筛选。
- 状态筛选。
- 版本查看。
- 依赖查看。
- 打开。
- 下载。
- 确认。
- 查看过期原因。

每项显示：

- 标题。
- 类型。
- 所属专家。
- 版本。
- 状态。
- 更新时间。
- 是否过期。

过期产物显示：

- 过期原因。
- 变化的上游事实或产物。
- 建议重新生成或检查。

禁止：

- 删除旧版本。
- 其他专家直接编辑。
- 将过期产物作为默认输入。

打开产物时优先使用右侧预览、中央覆盖层或抽屉，关闭后恢复原对话状态。

## 21. 设备页

设备页至少显示：

- 设备名称。
- 主控型号。
- 连接状态。
- 串口状态。
- 固件状态。
- 在线状态。
- 最近连接时间。
- 调试日志。

设备操作必须经过：

```text
Agent/Skill
→ SkillRuntime
→ ToolRunner
→ 用户确认策略
```

权限：

- 智能工程师可发起连接、日志读取、数据采集、串口发送、烧录、重启等符合权限的操作；涉及外部效果时必须按风险策略确认。
- 结构工程师只能读取必要主控型号、元件尺寸、接口位置和安装信息。
- 问题引导师通常只读取设备摘要，不显示控制操作。

禁止前端按钮绕过 ToolRunner 直接控制设备。

## 22. 方案卡

方案卡至少显示：

- 标题。
- 版本。
- 状态。
- 摘要。
- 分段内容。
- 修改。
- 确认。
- 生成产物。

方案内容必须同时包含：

- 实现逻辑。
- 硬件方案。
- 软件模块。
- 结构约束或结构建议。
- 成本、难度、时间。
- 风险和待确认项。

修改规则：

1. 基于当前版本。
2. 未修改部分保留。
3. 生成新草稿版本。
4. 不覆盖已确认版本。
5. 确认后创建正式产物或 ProjectDecision。
6. 触发 ProjectCoordinator 检查影响。
7. 下游受影响产物按现有规则标记过期。

## 23. 旧项目兼容

旧四专家映射：

| 旧角色 | 旧 ID | 新专家 |
|---|---|---|
| 创想家 | `ideator` | 问题引导师 `problem_guide` |
| 教育家 | `educator` | 问题引导师 `problem_guide` |
| 开源硬件设计师 | `open_hardware_designer` | 智能工程师 `smart_engineer` |
| 3D 结构设计师 | `structure_designer` / `three_d_structure_designer` | 结构工程师 `structure_engineer` |
| 过渡问题引导 | `question_guide` | 问题引导师 `problem_guide` |
| 过渡智能工程 | `intelligent_engineer` | 智能工程师 `smart_engineer` |

兼容规则：

- 旧项目可打开。
- 旧线程可查看。
- 旧产物可查看。
- 旧字段缺失时使用合理默认值。
- 创想家和教育家都映射到问题引导师，但保留为不同历史线程，不合并聊天内容。
- 旧产物保留 `legacyOwnerExpert`、`creatorLegacyExpert` 等来源字段。
- 不要求用户重新创建项目。
- 不因缺少 PendingItem、ExpertWorkspace 新字段或新领域状态崩溃。

数据库迁移要求：

- 迁移幂等。
- 不删除旧版本。
- 不硬删除旧专家、会话、草稿、私有记忆或产物。
- 当前手写 SQLite migration 为 forward-only；回滚依赖数据库备份。

## 24. 数据库和迁移

当前 schema 基线：v22。

持久化能力包括：

- 三师专家定义。
- `project_experts` 三师工作区和 legacy 字段。
- `conversations` 多线程和 owner expert。
- `expert_drafts` 专家草稿。
- `expert_private_memories` 专家私有记忆。
- `project_shared_facts`
- `project_decisions`
- `project_pending_items`
- `project_handoffs`
- `project_tasks`
- `artifacts`
- `artifact_versions`
- `artifact_dependencies`
- `project_coordinator_states`
- `expert_runs`
- `skill_runs`
- `tool_runs`
- `clarification_answers`

重要字段：

- `legacy_expert_type`
- `archived_legacy_thread`
- `legacy_owner_expert`
- `creator_legacy_expert`
- `domain_status`
- `critical_path`
- `is_highlighted`

风险：

- 当前迁移系统只有前进迁移，没有 down migration。
- 用户数据库回滚应通过备份文件，不建议手工降低 `PRAGMA user_version`。

## 25. API 和契约要求

共享契约位于 `packages/contracts`，状态枚举必须来自共享 contracts，不在 UI 和服务中复制字符串。

关键 API 能力：

- 邮箱账号注册、验证/重发、登录、刷新轮换、退出、密码重置、画像和 30 天离线租约；Sidecar 保持 `/api/auth/*` 本地门面。
- 旧项目认领、账号隔离、项目进度快照、复制、归档/恢复和永久删除前备份。
- 项目推荐：`POST /api/projects/suggest`
- 项目创建：`POST /api/projects`
- 项目详情 / 工作台数据读取。
- 专家添加 / 软移除。
- 当前线程消息读取和写入。
- PendingItem 处理 / 暂不处理。
- 方案生成 / 修改。
- 产物版本读取 / 确认。
- 设备扫描 / 连接 / dry-run / 受控操作。

跨前后端接口变化必须先更新契约和测试，再实现业务逻辑。

## 26. 安全和隐私

安全要求：

- 未登录时不得挂载工作台，除健康检查和认证入口外的业务 API 必须验证 Bearer 会话。
- 密码只保存随机盐 PBKDF2 派生值，会话库只保存 token 摘要；密码、原始 token 和认证私密字段不得进入项目、项目包、日志或 LLM 上下文。
- 永不提交 API Key、Wi-Fi 密码、真实串口标识和用户隐私数据。
- 不在自动化测试中调用真实付费 LLM。
- 不自动连接真实串口设备。
- 不自动运行 `mpremote`、`esptool`。
- 不自动执行 Flash 擦除、固件烧录或设备文件覆盖。
- 删除、Flash 擦除、固件烧录、公开发布等操作必须保留确认点。
- 云端 LLM 不直接操作本地文件、shell、串口或设备。

隐私要求：

- 专家私有草稿不得进入共享上下文。
- 完整聊天历史不得被无差别注入其他专家。
- 项目资源不自动成为 confirmed fact。

## 27. 验收标准

### 27.0 账号与平台访问

- 首次启动无有效邮箱账号会话时显示邮箱注册/登录；不提供游客模式。开发/迁移设备未配置云认证且检测到活动旧本机账号时，显示受控本机账号恢复入口，不把 `CLOUD_AUTH_NOT_CONFIGURED` 当作凭据错误。
- 注册后必须完成六位邮箱验证码验证和一次画像设置才进入平台；刷新或重启可恢复有效会话，退出和业务 401 都回到登录页并卸载工作台。
- 旧本机密码不可查看或还原；恢复工具必须本机交互隐藏输入、先备份认证库、成功后撤销旧会话，且不得改变账号 ID、项目归属或设备/CAD 安全门禁。
- 已验证设备可在离线租约内使用当前账号的本地项目最多 30 天；联网后刷新租约并响应云端撤销。
- 未登录直接请求项目、聊天、产物、硬件、设置或设备 API 返回 401，不能只依赖前端遮罩。
- 登录失败使用统一信息，不泄露账号是否存在；数据库不保存明文密码或原始 token。
- `390x844`、`720x720`、`1280x720` 下注册/登录主要操作可达且无页面级横向溢出；登录后仍只有一套工作台、一个中央主对话和固定“工作 / 产物 / 设备”三 Tab。

### 27.1 项目创建

- 新建项目只推荐/展示三师。
- 输入创意时不调用项目推荐；点击“分析并推荐”后才调用一次。修改已分析创意后旧推荐不可用于创建。
- 创建页只在分析成功后允许从真实 ACTIVE 硬件库选择最多 12 项；空选择可继续，修改选择不使旧推荐失效。
- 新桌面 suggest 不携带预选硬件，create 在写库前校验 `selectedHardwareIds`；未知、归档、INVALID 或从 ACTIVE Hardware Skill 执行本地 Rule Engine 后为 FAIL 的组合不能留下半个项目。
- 已选器件成为 confirmed 项目上下文，后续三师不重复询问或重复推荐相同 ID，只补齐能力缺口。
- 项目内可用完整快照更新选择；旧 confirmed 事实必须原子 supersede。三师缺件卡只能声明能力名称，由本地 ACTIVE 库完成稳定 ID 选择和校验。
- 用户可修改项目名和专家选择。
- 创建后进入项目唯一时间线，初始专家作为默认回复目标。
- 每个已选专家拥有不同 `threadId`。
- 创建失败不留下半成品。
- 重复 idempotency key 不创建重复项目。

### 27.2 问题引导和方案

- 模糊想法默认进入问题引导师。
- 引导问题由云端 LLM 一次性结构化生成。
- 方案生成使用已澄清内容、最近对话和 confirmed facts。
- 推荐方案不能忽略用户引导答案。
- 修改方案必须调用云端 LLM 重新判断并生成版本化结果。
- 旧方案版本保留。

### 27.3 专家工作区

- 前台只显示三位专家。
- 三师拥有不同线程。
- 中央聚合显示项目各线程消息，回复必须标明智能体名称。
- 新消息写入胶囊或 `@智能体` 指定的目标线程。
- 当前项目缺少 canonical 三师成员时可从胶囊末尾添加；成功后新增独立线程并成为下一条回复目标。
- 输入草稿按项目隔离，不随智能体切换。
- 手动指定回复智能体不创建 Handoff。
- Provider 历史只读取目标线程，不得读取其他专家完整聊天。
- 三师共享读取项目事实、决策、产物和公共硬件知识。
- 公共组件知识只有一份全局数据；添加或编辑后，三位工程师下一次相关回复读取同一最新内容。专家线程、私有草稿、私有记忆和 Agent Skill 行为文件仍保持隔离。
- 公共知识页按 Hardware Skill 显示可搜索的名称、类别、状态、验证来源和完整详情；主操作是“新建 Hardware Skill”与“打开 Skill 项目”。
- 正式内置最小目录包含 K10、SEN0193、DFR0523、5V/3A 独立稳压电源要求，以及受信 SEN0388 超声波、DFR0486 OLED、DFR0029 按钮；历史演示 seed 不得重新进入生产默认库。用户自建 Hardware Skill、项目选择历史和恢复归档不得因默认库收敛被删除。
- Hardware Skill 可登记本地真实产品图及来源、替代文本、署名、授权说明和 SHA-256。图片必须经过格式、大小、路径、MIME 与哈希校验，通过登录态 API 读取；不得热链、不得用生成图冒充实物，也不得从图片推断电气参数。
- 知识库详情与项目硬件选择器显示同一封面；无图或加载失败仍显示器件名称与文字类别。新增器件必须有可复制模板，目录包含 `manifest.json`、`README.md`、`SKILL.md`、`assets`、`references`、`models`、`examples` 和 `tests`。
- 每个 ACTIVE 器件至少保留原八文件项目；声明结构能力时增加 `references/mechanical.md` 和 `models/cadquery.py`，可再声明 `README.md/CHANGELOG.md`。浮窗以同一文件树编辑 Markdown 与 Python 参考模型，保存使用整体 revision，冲突保留草稿。
- 电气、结构、安全和兼容规则全部从有效 Hardware Skill 编译；SQLite 只保留可重建投影。Markdown 和参考模型均不能扩大工具或设备权限。
- `range-overlap(electrical.voltage)` 必须从主控离散电源轨中选择器件允许范围内且最接近推荐点的一项；允许范围内的非推荐轨只能给出可继续的中文 WARNING，范围外才 FAIL。供电通过后仍必须独立执行 `logic_level`，不得把 5V 输出直接视为对 3.3V GPIO/ADC 安全。
- 设置与项目工具中的器件入口必须打开同一个 `hardware-skill:{skillName}` 浮窗；只允许服务端白名单内 Markdown，不显示主机路径。
- 新建工作流支持资料上传、对话补充、目录预览、本地校验和明确确认。未确认 DRAFT 不出现在 ACTIVE 选择器，不进入三师上下文。
- Hardware Skill 单文件最多 80,000 UTF-8 bytes、manifest 声明文本整包最多 300,000 bytes；最多八个创建来源，文本单件最多 512 KiB、来源合计最多 1.5 MB，PDF 最多 2 MB/50 页/200,000 个提取字符。三师 Agent package 继续使用单文件 40,000 字符、整包 100,000 字符的独立边界。只有保存成功的有效 revision 进入三师上下文，浏览器中的未保存草稿不可见。
- 最小化浮窗保留草稿；关闭或第四窗口淘汰未保存编辑器前必须确认；保存期间编辑器只读，409 加载最新 revision 后仍保留草稿供重试。
- `390x844`、`720x720`、`1280x720` 下器件文件树、Markdown 编辑器和主要操作均可达，无页面级横向溢出；中央 `CenterChat` 单实例和右侧固定三 Tab 保持不变。
- `390x844`、`720x720`、`1280x720` 下正式最小硬件目录的封面/来源文字可读，无页面或对话框横向溢出；历史演示 seed 不出现在活动目录。

### 27.4 右侧工作

- 右侧页签切换不影响中央对话。
- 同一时间只有一个高亮事项。
- 事项处理后协调器重新计算下一项。
- 任务状态来自领域数据。

### 27.5 产物

- 产物显示版本和状态。
- 过期产物显示原因。
- 上游 confirmed 新版本会使依赖旧版本的下游产物 outdated。
- 旧版本仍可查看。
- 不删除旧产物版本。

### 27.6 设备

- 无设备时提供连接说明。
- 智能工程师设备操作经过权限和确认策略。
- 结构工程师只能读取必要设备信息。
- 问题引导师只显示摘要。
- 日常 MicroPython 上传不触发 Flash 擦除。
- 擦除和固件烧录需要确认。

### 27.7 旧项目

- 旧四专家项目可打开。
- 旧线程可查看。
- 旧产物可打开。
- 创想家和教育家历史线程不合并。
- 缺少新字段不崩溃。
- 迁移重复执行不会重复创建工作区或线程。

## 28. 当前实现状态

已完成：

- 云端邮箱账号注册、十分钟单次验证码、登录/refresh 轮换/退出/找回密码/画像，Sidecar 本地会话门面、系统凭据库存储 refresh token、30 天离线租约与全局业务 API 门禁；认证成功前不挂载工作台。
- 三师 canonical 专家类型和 legacy alias 兼容。
- SQLite 当前权威 schema 为 v26；v24 引入 CAD Job、Artifact 文件和版本化机械档案映射，v25 增加本地执行授权关联，v26 增加项目 owner、账号工作区状态和旧项目认领。
- 三师 ExpertWorkspace、ConversationThread、SharedFact、ProjectDecision、ArtifactDependency、Handoff、PendingItem、Task 等领域结构。
- EntryRouter、ContextAssembler、三师提示词加载和智能工程师 Skill Registry。
- ProjectCoordinator 的 SharedFact、Handoff、Task、PendingItem、ArtifactDependency 和过期传播。
- 三师项目创建事务和幂等保护。
- 项目创意完成后由用户显式点击“分析并推荐”；成功后才提供可跳过的 ACTIVE 项目硬件选择，只有修改创意会使旧推荐失效。
- create 与项目内更新校验硬件 ACTIVE 状态与 Rule Engine；WARNING 以结构化中文提醒显示，confirmed `preferred_hardware` 以最新快照为准并要求方案只补齐能力缺口。
- 三师可返回受控 `hardware_selection` 缺件卡，用户从中央消息或项目工具打开同一选择器把器件加入项目；Provider 不得生成 component ID。
- 公共知识与项目工具复用目录化 Hardware Skill 浮窗；全部参数和声明式规则由 Skill Markdown 编译，未确认草稿和未保存编辑不进入三师上下文。
- 三栏项目工作台：左侧新建项目/项目列表/项目资源，中央项目唯一对话，右侧工作/产物/设备。
- 项目智能体胶囊、`@智能体` 路由、按项目增补其余工程师、项目草稿隔离和右侧页签保持。
- 三师配置声明的全部 Skill Markdown 可在行为项目浮窗确认和修改；公共知识库支持上传/对话创建、搜索、完整详情和目录编辑，三师共享读取同一 ACTIVE Hardware Skill revision。
- 专业模式“设置 → 公共知识”包含第三个内部 Tab“机械档案”，按点击懒加载受信档案；每张卡点击预览时以当前精确 revision 请求服务端。服务端只读取该 Skill `mechanical.md` 的自然描述，命中同描述哈希缓存则直接返回，否则调用结构化模型生成受控几何、回写新 Skill revision 后返回；失败时不打开旧模型。没有 Skill 结构来源时才明确仅包络预览。全程不执行参考 Python，也不把示意伪装成项目 CAD 产物。普通模式不挂载组件、不请求机械档案 API，右侧一级 Tab 仍固定为“工作 / 产物 / 设备”。
- 专家添加和软移除。
- 产物版本、领域状态和过期信息展示。
- 设备页按专家权限展示受控入口。
- 问题引导的一次性批量澄清与单次提交。
- 生产 Provider 驱动的项目路由、三师回复、澄清、方案、立项书、Spec、代码、CAD 和教案。
- 结构工程师真实 CAD 闭环：声明式 `cadDraft`、服务端 intake 指纹、中央确认、受限本地 Worker、真实 STEP/STL/GLB、ArtifactVersion 和 Three.js 浮窗；当前模板范围为 `BOX_WITH_LID -> box-with-lid.v1`、单器件 `COMPONENT_MOUNT -> component-mount.v1`、无器件 `FREEFORM_STRUCTURE -> freeform-structure.v1` 与固定 `UNIHIKER_K10_PHOTO_ALBUM -> unihiker-k10-photo-album.v1`。
- 五个受信机械档案、精确 profile revision/SHA-256 快照、自动/混合/显式尺寸证据，以及 XIAO ESP32S3 的 USB-C 跨面开孔和 `edge_retainer` 安装结构。
- Web 模式对本地 CAD 执行、CAD 写操作和 3D 二进制浮窗执行前后端双重门禁。
- 结构化输出的 Pydantic 校验、一次修复重试和 `LLM_OUTPUT_INVALID` 失败边界。
- 既有真实 DeepSeek 隔离烟测只作为本轮修复前的 Provider 基线；直接 CAD intake、solution/proposal 路由延续、原子回答和 Provider 未返回 `cadDraft` 时的本地规范化，本轮未自动检测，待用户真人验收。

仍需人工验证：

- `390x844`、`720x720`、`1280x720` 下机械档案设置、CAD 工作进度、MODEL_3D 浮窗和中央确认流的真人交互与无重叠验收。
- 器件安装结构/盒体目标分流、单器件机械档案选择、松散存放、固定安装、方案/立项阶段启动 CAD、跨专家切换后提交源澄清卡、非法尺寸重提、明确修改尺寸重开 intake，以及 Provider 只返回文本时仍出现 CAD 草稿。
- 修订后旧草稿不能开始建模、旧失败 Job 不能重试、旧 READY 版本不能确认；运行中的 Job 不被隐式取消，但完成后旧结果不能重新成为待确认版本。
- 真实 ESP32 串口发现、连接、上传、重启日志和冒烟测试。
- 真实 Flash 擦除和固件烧录确认流程。
- 完整真实项目从想法到硬件、代码、结构和设备闭环体验。

已知技术债：

- K10 的专业 UI、DELETE 和 CAD 解析已锁定，但机械档案 PUT 路由尚未拒绝直接 HTTP 重映射；在补齐服务端 guard 前不得把 K10 描述为全 API 层不可重映射。
- `ProjectRepository` 仍是大型同步 repository，FastAPI async 路由直接调用同步 SQLite 逻辑，后续应评估 `asyncio.to_thread`、专用执行器或 repository 拆分。
- 手写 migration 只有前进路径，没有 down migration。
- DeepSeek 是当前唯一真实云端 provider，Provider 抽象仍需第二真实或本地 provider 验证。
- CI 工作流尚未完全固化。
- Desktop package 当前没有 lint script。
- 部分 React 测试仍有既有 `act(...)` warning。

## 29. 建议路线图

近期优先级：

1. 加入 CI：contracts build/typecheck、desktop typecheck/test/build、backend pytest/compileall、cargo check。
2. 为 migration 增加历史版本回放测试。
3. 处理同步 SQLite 阻塞事件循环风险。
4. 拆分大型 ProjectRepository。
5. 增加第二 provider 或本地 mock provider 以验证 LLMProvider Protocol。
6. 将架构约束转化为轻量静态检查。

暂不推进：

- ZW-017。
- 复杂 CAD 平台。
- 完整在线训练平台。
- 无确认真实硬件执行。

## 30. 启动和验证命令

常用验证：

```powershell
pnpm --filter @zhangwen/contracts build
pnpm --filter @zhangwen/contracts typecheck
pnpm --filter @zhangwen/desktop typecheck
pnpm --filter @zhangwen/desktop test
pnpm --filter @zhangwen/desktop build
.venv\Scripts\python.exe -m compileall services/local-api/zhangwen
.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
git diff --check
```

默认完整本地应用启动与脚本检查：

```powershell
pnpm start
pnpm start:check
```

显式无设备 Web 开发：

```powershell
pnpm dev:web
```

访问：

```text
http://localhost:5173/
```

注意：

- 自动测试不调用真实付费 LLM。
- 默认完整本地应用启动不执行设备操作；显式硬件任务的日常文件上传必须在写入前确认，Flash 擦除和固件烧录仍需独立高风险确认。
- `.codex/config.toml` 是本地配置改动，不应提交。

## 31. ZW-CLOSURE-001 权威范围变更

本节晚于此前章节并覆盖其中冲突的历史表述：

1. 原始游客需求已由“邮箱账号后使用”正式替代；项目、对话和产物不做跨设备云同步，只在本机按云端账号 subject 严格隔离。
2. 新建项目固定为“描述创意 → 推荐方案与硬件 → 确认创建”三步。普通模式自动选择参与专家且不暴露 Agent、Skill、DAG、内部 ID 或底层设备参数；专业模式才展开这些控制。
3. `ProjectProgressSnapshot` 是阶段、当前动作、硬件/规格/代码/测试/设备五项就绪度、草稿/正式产物摘要和一致性诊断的唯一前端来源。
4. 立项书确认后在中央对话显示简化执行摘要。硬件核验、工程规格、代码、测试和设备部署为必选，CAD 与教案为可选；教师画像且要求教学内容时默认启用教案。
5. 首个真实设备闭环固定为 K10 + SEN0193 + DFR0523 + 独立稳压 5V/3A。水泵不得由 K10 或 GPIO 供电，必须共地；缺少独立电源或电流预算不足直接失败。
6. 日常上传只部署已接受的结构化 MicroPython 工程，执行备份、逐文件写入、SHA-256 回读、软重启、重连和只读日志核验；不擦除 Flash、不烧录固件。自动浇花只有在湿润关泵、干燥有限启动并三秒内停止、连续湿度样本和无未处理异常都留下证据后，项目才进入设备已验证阶段。
7. 项目管理统一为重命名、复制、归档、恢复和永久删除。复制生成全新 ID 图并排除设备会话/凭据/真实串口；永久删除只在归档区提供，输入项目名确认且先生成可恢复备份。
8. 真实 SMTP、真实 DeepSeek、真实 K10/SEN0193/DFR0523/独立电源、公开部署和同一提交安装包冷启动是发布人工门槛。资源缺失时只能写“软件完成、外部验收待办”。
