# 掌问 PRD v0.1

**产品名称：** 掌问  
**产品副标题：** AI 创客工程工作台  
**文档版本：** v0.1  
**文档状态：** 基线草案，可进入原型与技术验证  
**日期：** 2026-07-07  
**目标读者：** 产品、设计、前端、桌面端、后端、AI Agent、嵌入式、测试与内容团队  
**开发工具协作目标：** 本文档及配套仓库规范应同时被 Codex 与 Qoder 读取、执行和持续维护。

---

## 1. 执行摘要

掌问是一款面向教师、学生、工程师和创客的本地桌面应用。用户通过主对话窗口描述一个创意，系统以对话和选项补全需求，基于用户画像、硬件库存、项目约束和安全规则生成一套唯一的“推荐实现方案”。用户可以持续通过对话修正方案，直至确认。系统随后生成项目立项书，由用户确认后，总控 Agent 根据立项书、用户画像和当前项目上下文选择需要参与的专业 Agent、Skill 与模型，形成可追踪的执行计划，完成 Spec、代码、结构件、教案、测试、串口上传和分享等任务。

掌问的中央区域始终保持主对话，不因查看产物而切换。项目状态、Agent 状态、产物和设备操作集中在右侧栏，通过“工作 / 产物 / 设备”三个分栏呈现；完整文档、代码、3D 模型、串口终端等通过可拖动、可缩放的浮窗查看。这样既保持对话连续性，也避免把产品做成传统 IDE。

MVP 聚焦 ESP32 + MicroPython 创客项目，首选通过 USB 串口烧录 MicroPython 固件和上传代码。系统采用“云端 LLM 负责理解与规划、本地工具负责受控执行”的混合架构。不同 Agent 可以共用同一个云端 LLM，也可由模型路由器按任务质量、速度、成本、视觉能力和隐私要求选择不同模型；同一个 Agent 的不同步骤也可使用不同模型。

---

## 2. 产品背景与机会

### 2.1 当前问题

中小学创客、个人创客和非专业开发者从创意走到可运行作品，通常需要跨越需求分析、硬件选型、电气兼容、程序开发、结构设计、固件烧录、调试、文档和分享等多个领域。现有 AI 编程工具擅长代码生成，但通常缺少硬件库、结构件、设备执行和教育场景支持；传统创客工具又要求用户掌握 IDE、串口、驱动、固件和文件管理。

### 2.2 产品机会

掌问通过一个持续存在的主对话入口，把复杂工程流程转换成少量用户确认动作；通过结构化硬件库与确定性规则避免大模型“猜硬件”；通过 Spec 和立项书把多个 Agent 的工作约束在同一个项目契约中；通过本地设备服务完成串口识别、固件烧录、文件上传与日志诊断；通过用户画像适配教师、学生、工程师和创客的表达深度与默认任务。

### 2.3 核心价值

1. **把一句想法变成可运行的实体作品。**
2. **让普通用户不必理解 Agent、Skill、串口工具链和项目目录。**
3. **让专业用户仍可查看和控制 Spec、代码、模型、日志和权限。**
4. **让所有产物、决策和执行状态可追踪、可回滚、可交接。**

---

## 3. 产品目标、非目标与成功标准

### 3.1 v0.1 产品目标

- 建立从创意到 ESP32/MicroPython 项目上传的完整闭环。
- 通过对话生成并迭代一套唯一的推荐实现方案。
- 在用户确认立项书后，由总控 Agent 自动选择和调度专业 Agent。
- 支持可扩展 Agent、Skill 与模型路由机制。
- 中央区域永久保留主对话，右侧栏管理状态、产物与设备。
- 支持本地项目、版本快照、产物确认和失败恢复。
- 形成 Codex 与 Qoder 可交替开发、无聊天上下文依赖的仓库规范。

### 3.2 v0.1 非目标

- 不支持任意复杂机械系统或自由曲面工业设计。
- 不支持 PCB 自动布线和直接下单制造。
- 不支持 STM32、树莓派等多平台完整工具链。
- 不承诺无人工确认的全自主硬件操作。
- 不在 MVP 中建设公开第三方 Agent/Skill 商店。
- 不在 MVP 中实现多人实时协同编辑。
- 不要求所有 LLM 均可离线运行；本地模型为后续扩展。

### 3.3 关键成功指标

| 指标 | MVP 目标 |
|---|---|
| 新用户完成首个实现方案确认率 | ≥ 60% |
| 从创建项目到确认实现方案的中位时长 | ≤ 10 分钟 |
| 硬件规则校验后仍发生明显电气冲突的比例 | < 1% |
| 支持开发板的串口识别成功率 | ≥ 95% |
| 在设备正常、线缆正常情况下的首次代码上传成功率 | ≥ 90% |
| Agent 任务状态可解释率 | 100% 任务显示状态、当前动作和下一步 |
| 产物可追踪率 | 100% 产物具有版本、来源 Agent、依赖版本和状态 |
| Codex/Qoder 交接后无需重新口述上下文的任务比例 | ≥ 95% |

---

## 4. 核心术语

| 术语 | 定义 |
|---|---|
| 项目 | 用户围绕一个创意创建的完整工作空间，包含对话、方案、立项书、Spec、代码、结构、设备和分享产物。 |
| 推荐实现方案 | 系统给出的唯一当前方案，包含功能逻辑、硬件、软件、结构、实施步骤、成本、难度、风险和 Agent 工作范围。 |
| 立项书 | 用户确认实现方案后生成的正式项目基线，是总控 Agent 规划工作的主要输入。 |
| Spec | 面向实现的机器可读与人可读规范，包括需求、架构、接口、IO、BOM、验收标准等。 |
| Agent | 具备角色、上下文、权限、模型策略和 Skill 集合的任务执行单元。 |
| Skill | 可复用的专业工作流，包含触发描述、步骤、输入输出、脚本、权限和验证方式。 |
| 总控 Agent | 读取立项书与项目状态，生成任务图并调度专业 Agent 的协调者。 |
| Model Router | 根据任务、能力、成本、速度和隐私策略选择 LLM 的路由服务。 |
| Artifact / 产物 | Agent 或用户产生的文档、代码、模型、报告、图片、固件信息等可版本化对象。 |
| Tool Runner | 在本地受控执行文件、命令、串口、CAD、测试等工具的服务。 |
| 确认点 | 必须由用户批准后才能进入下一阶段的节点。 |

---

## 5. 用户与画像

### 5.1 教师

目标是快速形成可授课、可复现、风险可控的创客项目。默认关注年级、课时、教学目标、材料数量、课堂稳定性、安全和评价方式。系统可默认建议教案 Agent、学生任务单 Agent 与评价 Agent。

### 5.2 学生

目标是在低技术门槛下理解并完成作品。默认使用简洁语言、分步任务、选择式问题和知识点解释；限制危险命令、Flash 擦除和高风险执行器参数。未成年人账号的高风险设备操作可要求教师授权。

### 5.3 工程师

目标是提高原型开发效率。默认展示技术参数、架构、接口、版本差异、完整日志和高级配置，允许直接编辑 Spec、代码、模型策略和 Skill。

### 5.4 创客

目标是在成本、易用性和可扩展性之间平衡。默认关注硬件可采购性、库存利用、结构可打印性、改造空间和分享效果。

### 5.5 画像规则

- 画像决定默认表达、默认 Agent 建议、默认安全级别和默认产物，不永久限制功能。
- 用户可在项目级临时覆盖画像，例如工程师以“教师模式”制作课程。
- 系统不得将画像用于与项目无关的差别对待。

---

## 6. 产品设计原则

1. **对话始终是主线。** 中央主对话不可被产物、编辑器或设备界面替换。
2. **每次只展示一个当前推荐实现方案。** 用户通过对话迭代，不同时比较多套卡片。
3. **确认后再执行。** 实现方案、立项书、关键 Spec、擦除 Flash、烧录固件和公开发布具有明确确认点。
4. **后台复杂，前台简单。** 普通用户不需要选择 Agent、Skill、模型或命令。
5. **规则先于生成。** 电压、电流、IO、固件和库存等确定性约束由规则引擎判断，LLM 负责解释与补全。
6. **产物可追踪。** 每个产物必须记录版本、来源、依赖、状态和验证结果。
7. **本地执行受控。** 云端 LLM 不直接访问串口和文件系统，所有本地操作由权限引擎和 Tool Runner 执行。
8. **失败必须可恢复。** 失败提示包括原因、影响、可执行修复选项和回滚入口。
9. **工具无关的仓库事实。** Codex、Qoder 或人工开发者都以仓库文档与代码为唯一事实来源。

---

## 7. 端到端用户流程

### 7.1 首次进入

1. 用户选择游客体验或注册登录。
2. 选择主要画像：教师、学生、工程师、创客、其他。
3. 完成最少画像设置：技术水平、常用开发板、是否需要教学内容、默认预算倾向。
4. 进入项目首页，看到“描述你想做的作品”。

### 7.2 创意澄清

1. 用户在中央对话输入想法。
2. 总控 Agent 提取目标、场景、对象、约束和缺失信息。
3. 每轮最多询问 1 至 3 个关键问题，可用单选、多选、数值和自由输入卡片。
4. 用户可选择“由掌问推荐”接受默认答案。
5. 需求完整度达到阈值后进入方案生成。

### 7.3 唯一推荐实现方案

推荐方案必须同时说明：项目目标、工作逻辑、硬件组成、软件模块、结构实现、实施步骤、成本与工期、适用对象、风险与限制、预计调用的 Agent 类型。

用户可以点击“确认方案”，或直接在对话中提出修改。每次修改生成新的方案版本，界面只展示最新有效版本；历史版本在产物栏可查看。

### 7.4 立项书确认

1. 确认实现方案后生成立项书草稿。
2. 立项书通过右侧产物栏或浮窗查看，中央对话保持不变。
3. 用户可选中文段并“引用到对话”，或直接用自然语言要求修改。
4. 用户点击“确认立项”后形成只读基线版本；后续重大变更生成新版本和变更记录。

### 7.5 Agent 规划与执行

1. 总控 Agent读取立项书、画像、硬件方案、可用 Agent、Skill、设备环境和项目配置。
2. 生成任务依赖图，决定需要哪些 Agent、顺序、并行关系、确认点和验证方式。
3. 用户在简洁摘要中确认工作计划。
4. 右侧“工作”栏显示每个 Agent 状态、当前动作、进度和阻塞原因。
5. 产物产生后进入“产物”栏；待确认产物集中提醒。

### 7.6 串口上传

1. 用户连接 ESP32 设备。
2. 右侧“设备”栏自动列出端口、芯片、固件状态和可执行操作。
3. 默认操作为“上传并运行”；系统优先通过串口上传 MicroPython 文件。
4. 仅在未安装、损坏或版本不兼容时建议烧录固件。
5. 上传后读取日志并执行冒烟验证；失败时提供自动重试、接线检查、重新烧录和高级诊断。

### 7.7 分享

用户可生成作品展示页、可复现项目包或教学项目包。发布前扫描 Wi-Fi 密码、API Key、个人信息和不应公开的文件。公开发布必须确认可见范围和许可证。

---

## 8. 信息架构与界面规范

### 8.1 主布局

```text
┌──────────────────────────────────────────────────────────────┐
│ 掌问   当前项目名称                当前阶段         用户头像 │
├──────────┬──────────────────────────────┬────────────────────┤
│          │                              │ 工作｜产物｜设备    │
│ 项目列表 │          主对话区域           │                    │
│ 模板入口 │                              │      右侧栏        │
│ 硬件库   │                              │                    │
└──────────┴──────────────────────────────┴────────────────────┘
```

### 8.2 不可变界面约束

- 中央区域始终为主对话，不因查看任何产物而路由到其他页面。
- 产物完整查看使用右侧展开或浮窗。
- 右侧一级分栏固定为“工作、产物、设备”，不得在 MVP 中增加更多同级分栏。
- 左侧默认不展示源码文件树；专业模式可在独立浮窗提供文件浏览。
- 所有重要状态必须同时具有文本，不只依赖颜色。

### 8.3 左侧栏

包含新建项目、项目搜索、最近项目、模板、硬件库。宽度可折叠。默认展示项目名称、阶段和最后更新时间，不展示复杂目录。

### 8.4 中央主对话

支持文本、语音转文字（后续）、图片/文件附件、结构化选择卡、方案摘要卡、确认卡和错误修复卡。输入区固定在底部。滚动查看历史时，新消息提示不得强制跳到底部。

### 8.5 右侧“工作”栏

展示项目阶段、总体进度、需要用户处理的事项和 Agent 列表。Agent 卡片默认只显示名称、状态、当前动作和进度；模型、Skill、工具调用和 Token 仅在高级详情展示。

Agent 状态：未启用、等待中、规划中、工作中、等待确认、已暂停、已阻塞、已完成、执行失败、已取消。

### 8.6 右侧“产物”栏

按待确认、生成中、已确认、历史版本分组。条目显示名称、版本、状态、来源 Agent、更新时间。点击条目在右侧预览；点击“完整查看”打开浮窗。

### 8.7 右侧“设备”栏

展示端口、芯片、板型、固件、连接状态、上传状态和最近日志。完整串口终端、设备文件系统和固件管理通过浮窗展开。

### 8.8 浮窗系统

浮窗支持拖动、缩放、最大化、贴边、最小化和恢复位置。可查看文档、代码、3D 模型、接线图、串口终端和发布预览。MVP 同时最多打开 3 个浮窗，避免遮挡和性能问题。

### 8.9 视觉原则

- 使用低饱和中性色和一个品牌强调色。
- 无大面积渐变和装饰性 3D 图标。
- 信息密度由画像和简洁/专业模式控制。
- 首屏主操作不超过 3 个。
- 关键按钮使用动词，如“确认方案”“上传并运行”，避免“下一步”一类含义不明的按钮。

---

## 9. 功能需求

### 9.1 账号与画像

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-ACT-001 | 支持游客模式进入并创建本地项目 | P0 | 未登录用户可创建、保存和重新打开本地项目 |
| FR-ACT-002 | 支持邮箱注册与登录 | P0 | 注册、验证、登录、退出和密码重置流程可完成 |
| FR-ACT-003 | 支持教师、学生、工程师、创客、其他画像 | P0 | 首次进入必须可选择，设置中可修改 |
| FR-ACT-004 | 画像包含技术水平、常用板卡、预算偏好和教学需求 | P0 | 总控 Agent 上下文中可读取结构化画像 |
| FR-ACT-005 | 支持项目级画像覆盖 | P1 | 单个项目可选择与账号默认不同的模式 |
| FR-ACT-006 | 游客注册后可合并本地项目 | P1 | 合并不丢失文件、版本和对话 |
| FR-ACT-007 | 学生模式支持高风险操作限制标记 | P1 | 擦除 Flash 等操作按策略要求授权 |

### 9.2 项目与对话

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-PRJ-001 | 创建、重命名、复制、归档和删除项目 | P0 | 删除进入回收区，可恢复 |
| FR-PRJ-002 | 每个项目具有唯一 ID、当前阶段和最后快照 | P0 | 重启应用后状态一致 |
| FR-CHAT-001 | 中央区域永久保持主对话 | P0 | 打开任意产物或设备详情后主对话不被替换 |
| FR-CHAT-002 | 支持流式响应和停止生成 | P0 | 用户可随时停止，已生成内容保留 |
| FR-CHAT-003 | 支持单选、多选、数值和自由输入澄清卡 | P0 | 卡片结果写入需求上下文 |
| FR-CHAT-004 | 每轮默认最多提出 3 个关键问题 | P0 | 超出时拆分为后续轮次 |
| FR-CHAT-005 | 支持引用产物段落到对话 | P1 | 引用包含产物 ID、版本和段落定位 |
| FR-CHAT-006 | 支持撤销最近一次需求修改 | P1 | 撤销后恢复对应方案版本 |

### 9.3 推荐实现方案

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-SOL-001 | 系统仅显示一套当前推荐实现方案 | P0 | 主界面不存在并列 2~3 套方案卡 |
| FR-SOL-002 | 方案包含目标、逻辑、硬件、软件、结构、步骤、成本、难度、风险 | P0 | 任一必填部分缺失时不可进入确认状态 |
| FR-SOL-003 | 方案硬件必须经过结构化规则校验 | P0 | 电压、IO、供电、驱动和固件校验有记录 |
| FR-SOL-004 | 用户可通过自然语言持续修改方案 | P0 | 每次修改生成新版本并保留差异 |
| FR-SOL-005 | 修改方案时同步更新成本、难度和任务范围 | P0 | 变更摘要明确列出影响 |
| FR-SOL-006 | 确认方案后生成不可覆盖的确认版本 | P0 | 后续修改必须创建新版本 |

### 9.4 立项书与 Spec

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-PRO-001 | 根据确认方案生成立项书 | P0 | 立项书包含背景、场景、功能、架构、BOM、风险和验收 |
| FR-PRO-002 | 立项书可在右侧或浮窗查看 | P0 | 查看时中央对话保持原位 |
| FR-PRO-003 | 支持对话修改和版本差异 | P0 | 修改记录可定位到版本 |
| FR-PRO-004 | 确认立项书形成项目基线 | P0 | 基线 ID 被执行计划与产物引用 |
| FR-SPEC-001 | Spec Agent 生成需求、系统、硬件、固件、结构和验收规范 | P0 | 输出具有固定目录和机器可读文件 |
| FR-SPEC-002 | IO Map 与 BOM 为结构化数据 | P0 | JSON/YAML 可被 Code、CAD 和 Deploy Agent 读取 |
| FR-SPEC-003 | 关键 Spec 可配置为用户确认点 | P0 | 未确认时受依赖任务不得开始 |

### 9.5 总控 Agent 与执行计划

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-ORC-001 | 总控 Agent 根据立项书确定所需 Agent | P0 | 不需要 CAD/教案时对应 Agent 标记未启用 |
| FR-ORC-002 | 规划同时考虑画像、硬件、设备和可用 Skill | P0 | 执行计划记录决策依据 |
| FR-ORC-003 | 生成有向无环任务依赖图 | P0 | 可计算等待、并行和阻塞状态 |
| FR-ORC-004 | 执行前向用户展示简化工作计划 | P0 | 用户可确认、删除非必要任务或补充任务 |
| FR-ORC-005 | 支持暂停、恢复、取消和重试任务 | P0 | 状态在重启后可恢复 |
| FR-ORC-006 | 前置产物变化时标记受影响任务 | P0 | 用户可选择重跑或保留旧产物 |
| FR-ORC-007 | 每个决策和调用具有审计记录 | P1 | 可查看时间、输入版本、Agent、Skill 与结果 |

### 9.6 Agent、Skill 与模型路由

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-AGT-001 | 支持注册内置与自定义 Agent | P0 | Agent 定义包含角色、描述、权限、Skill 和模型策略 |
| FR-AGT-002 | 支持扩展教案、测试、接线图等 Agent | P0 | 新 Agent 无需修改总控核心代码即可注册 |
| FR-AGT-003 | 支持项目级启用、禁用和覆盖 Agent | P1 | 设置立即影响新执行计划 |
| FR-SKL-001 | Skill 可自行定义 | P0 | Skill 具有名称、描述、输入、输出、权限、步骤和验证 |
| FR-SKL-002 | Skill 支持说明文件、脚本、参考资料和模板 | P0 | Tool Runner 可按清单加载受控资源 |
| FR-SKL-003 | Skill 调用前进行权限检查 | P0 | 未授权的串口、网络、命令和目录访问被阻止 |
| FR-MOD-001 | 多个 Agent 可共用同一云端 LLM | P0 | Agent 与模型配置解耦 |
| FR-MOD-002 | Model Router 可按任务选择不同模型 | P0 | 路由记录选择原因和回退模型 |
| FR-MOD-003 | 同一 Agent 不同步骤可使用不同模型 | P1 | 执行轨迹显示步骤级模型 |
| FR-MOD-004 | 用户可选择智能、质量优先、成本速度优先策略 | P1 | 策略影响路由评分 |
| FR-MOD-005 | 模型失败时支持回退与重试 | P0 | 不重复产生破坏性本地操作 |

### 9.7 Agent 状态与工作栏

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-WORK-001 | 展示所有已规划 Agent 的状态 | P0 | 状态至少覆盖十种定义状态 |
| FR-WORK-002 | 工作中 Agent 显示当前动作和进度 | P0 | 15 秒内至少更新一次心跳或状态 |
| FR-WORK-003 | 阻塞状态显示原因和可执行选项 | P0 | 用户无需查看原始日志即可理解下一步 |
| FR-WORK-004 | 普通模式隐藏 Token、原始 Prompt 和工具细节 | P0 | 专业模式可展开查看 |
| FR-WORK-005 | 任务完成后显示验证结果 | P0 | 未通过验证不得显示为已完成 |

### 9.8 产物管理

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-ART-001 | 所有产物在右侧产物栏统一查看 | P0 | 文档、代码、模型和报告均有条目 |
| FR-ART-002 | 完整内容通过浮窗查看 | P0 | 打开、关闭浮窗不改变对话位置和输入内容 |
| FR-ART-003 | 产物记录版本、来源、依赖、状态和校验值 | P0 | 可追踪到生成任务与输入版本 |
| FR-ART-004 | 支持确认、退回修改、下载和历史对比 | P0 | 退回时自动创建修订任务 |
| FR-ART-005 | 支持同时最多 3 个浮窗 | P1 | 超出时提示关闭或替换 |
| FR-ART-006 | 产物可标记草稿、待确认、已确认、过期、失败 | P0 | 前置基线更新后旧产物自动标记过期 |

### 9.9 硬件库与推荐规则

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-HW-001 | 管理主控、传感器、执行器、显示、供电和结构附件 | P0 | 可新增、编辑、归档和搜索 |
| FR-HW-002 | 硬件包含电气、软件、机械、库存和教育属性 | P0 | 缺少关键字段时不可进入正式推荐池 |
| FR-HW-003 | 支持用户库存数量和所在套件 | P0 | 推荐优先使用库存并显示缺少项 |
| FR-HW-004 | 规则引擎校验电压、电平、电流、IO、总线地址和固件 | P0 | 每项校验有通过/失败/警告状态 |
| FR-HW-005 | LLM 仅对规则通过的组合进行解释和排序 | P0 | 失败组合不得成为当前方案 |
| FR-HW-006 | 支持硬件替换并计算影响 | P0 | 软件、结构、成本和接线变化同时更新 |

### 9.10 代码、固件与设备

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-CODE-001 | 生成结构化 MicroPython 项目 | P0 | 至少包含 boot.py、main.py、config.py、drivers 和 README |
| FR-CODE-002 | 生成后执行语法、依赖和 Spec 一致性检查 | P0 | 检查失败自动修复或进入阻塞 |
| FR-DEV-001 | 默认通过 USB 串口连接 ESP32 | P0 | 自动列出可用端口并可刷新 |
| FR-DEV-002 | 识别芯片与板型，无法确认时请求用户选择 | P0 | 不在未知芯片上直接烧录 |
| FR-DEV-003 | 日常开发优先上传 MicroPython 文件 | P0 | 不无故擦除 Flash 或重刷固件 |
| FR-DEV-004 | 固件缺失或不兼容时提供烧录流程 | P0 | 擦除和烧录前强制确认 |
| FR-DEV-005 | 上传前备份设备文件 | P0 | 可一键回滚最近一次备份 |
| FR-DEV-006 | 上传后软重启、读取日志并执行冒烟测试 | P0 | 成功标准包含可观察运行结果 |
| FR-DEV-007 | 提供右侧简要日志和浮窗完整终端 | P0 | 两处日志来自同一会话流 |
| FR-DEV-008 | 支持端口占用、驱动缺失、下载模式和波特率诊断 | P0 | 每类错误至少有一个可执行修复入口 |

### 9.11 结构件、教案与分享

| 编号 | 需求 | 优先级 | 验收标准 |
|---|---|---|---|
| FR-CAD-001 | MVP 支持参数化支架、底座和简单外壳 | P1 | 输入尺寸后可生成 STL/STEP 与预览 |
| FR-CAD-002 | 结构产物经过实体、壁厚和安装孔校验 | P1 | 校验结果记录在报告中 |
| FR-LESSON-001 | 教案 Agent 可按画像和立项书生成教案 | P1 | 包含目标、课时、材料、流程、安全和评价 |
| FR-PUB-001 | 生成作品展示页、项目包和教学包 | P1 | 用户可选择包含哪些产物 |
| FR-PUB-002 | 发布前扫描密钥和隐私信息 | P0 | 检测到高风险内容时阻止公开发布 |
| FR-PUB-003 | 支持本地 ZIP 导出 | P0 | 包含清单和版本信息，可在另一台设备导入 |

---

## 10. 状态机

### 10.1 项目阶段

```text
IDEA
→ CLARIFYING
→ SOLUTION_DRAFT
→ SOLUTION_CONFIRMED
→ PROPOSAL_DRAFT
→ PROPOSAL_CONFIRMED
→ EXECUTION_PLANNED
→ IMPLEMENTING
→ VALIDATING
→ READY_TO_UPLOAD
→ DEVICE_VERIFIED
→ READY_TO_PUBLISH
→ PUBLISHED
```

允许从任何确认后阶段发起变更请求。重大变更创建新基线，并将受影响产物标记为过期；不得静默覆盖。

### 10.2 Agent 任务状态

```text
DISABLED / QUEUED / PLANNING / RUNNING / AWAITING_APPROVAL
PAUSED / BLOCKED / COMPLETED / FAILED / CANCELED
```

只有验证通过才能进入 COMPLETED。LLM 文本生成结束不等于任务完成。

### 10.3 产物状态

```text
DRAFT / GENERATING / NEEDS_REVIEW / APPROVED / REJECTED
STALE / FAILED / ARCHIVED
```

### 10.4 设备会话状态

```text
DISCONNECTED → DISCOVERED → CONNECTING → CONNECTED
→ UPLOADING → RESTARTING → VERIFYING → READY
```

任一执行错误进入 ERROR，并保留前一安全状态和恢复动作。

---

## 11. 核心数据模型

### 11.1 UserProfile

```json
{
  "id": "usr_xxx",
  "primaryPersona": "teacher",
  "technicalLevel": "beginner",
  "preferredBoards": ["esp32-s3"],
  "needsLessonContent": true,
  "budgetPreference": "balanced",
  "safetyPolicy": "education_strict",
  "modelStrategy": "smart"
}
```

### 11.2 Project

```json
{
  "id": "prj_xxx",
  "name": "自动浇花装置",
  "stage": "PROPOSAL_CONFIRMED",
  "personaOverride": null,
  "activeSolutionVersion": "sol_v3",
  "activeProposalVersion": "proposal_v1",
  "activeSpecVersion": null,
  "workspacePath": "...",
  "createdAt": "...",
  "updatedAt": "..."
}
```

### 11.3 AgentDefinition

```json
{
  "id": "agent_code",
  "name": "Code Agent",
  "description": "生成、检查和修复 MicroPython 代码",
  "skills": ["micropython-code", "spec-conformance", "test-runner"],
  "permissions": ["project.read", "project.write", "process.test"],
  "modelPolicy": {"profile": "coding", "fallback": "general"},
  "inputTypes": ["spec", "hardware_profile"],
  "outputTypes": ["source_code", "code_report"]
}
```

### 11.4 SkillDefinition

```json
{
  "id": "skill_serial_upload",
  "name": "MicroPython 串口上传",
  "description": "通过串口备份并上传 MicroPython 项目文件",
  "version": "1.0.0",
  "inputs": ["serial_port", "board_profile", "project_path"],
  "outputs": ["deployment_report", "serial_log"],
  "permissions": ["serial", "project.read", "device.write"],
  "approval": {"upload": "required", "erase_flash": "required"},
  "validator": "verify_device_boot"
}
```

### 11.5 TaskRun

必须包含 taskId、projectId、agentId、skillIds、inputArtifactVersions、status、progress、currentAction、modelTrace、toolTrace、startedAt、endedAt、error、retryCount 和 validationResult。

### 11.6 Artifact

必须包含 artifactId、type、title、version、status、filePath、mimeType、producerTaskId、inputDependencies、checksum、createdAt、approvedAt 和 supersedes。

### 11.7 HardwareComponent

关键字段包括工作电压、逻辑电平、峰值电流、通信方式、引脚、I2C 地址、支持主控、MicroPython 驱动、固件要求、尺寸、安装孔、库存、价格、年龄建议和安全标签。

---

## 12. 系统架构

### 12.1 推荐技术架构

```text
Tauri Desktop Shell
├─ React + TypeScript UI
├─ Right Panel & Floating Window Manager
├─ Local Project/Artifact Client
└─ Native bridge
       ↓
Python Local Service (sidecar)
├─ Project State Machine
├─ Orchestrator
├─ Agent Registry / Skill Registry
├─ Model Router / LLM Gateway
├─ Hardware Rule Engine
├─ Tool Runner & Permission Engine
├─ Device Service (pyserial/esptool/mpremote)
├─ CAD Service (CadQuery/OpenSCAD)
└─ FastAPI + WebSocket
       ↓
SQLite + Project Workspace + Secure Credential Store
```

### 12.2 选择理由

- Tauri 适合桌面文件、窗口、串口权限和轻量打包。
- React/TypeScript 适合实现对话、右侧栏和浮窗状态系统。
- Python 适合 LLM、结构化数据、MicroPython 工具链、CAD 与自动化测试生态。
- SQLite 保存账户本地映射、项目索引、任务、产物和审计；大文件保存在项目工作区。
- WebSocket 推送流式消息、Agent 状态、工具日志和设备事件。

### 12.3 进程边界

UI 不直接运行 shell、串口和 CAD。所有高权限操作经本地服务；本地服务对每次调用检查项目范围、用户权限和审批状态。云端 LLM 仅收到允许的上下文和脱敏内容。

### 12.4 项目目录建议

```text
project.zw/
├─ project.json
├─ conversation/
├─ solution/
├─ proposal/
├─ spec/
├─ firmware/
├─ app/
├─ cad/
├─ lesson/
├─ tests/
├─ deployment/
├─ publish/
└─ .zhangwen/
   ├─ state.json
   ├─ tasks/
   ├─ artifacts.json
   ├─ snapshots/
   ├─ backups/
   └─ logs/
```

---

## 13. API 与事件契约

### 13.1 本地 HTTP API 示例

| 方法 | 路径 | 用途 |
|---|---|---|
| POST | /api/projects | 创建项目 |
| GET | /api/projects/{id} | 获取项目聚合状态 |
| POST | /api/projects/{id}/messages | 发送对话消息 |
| POST | /api/projects/{id}/solution/confirm | 确认实现方案 |
| POST | /api/projects/{id}/proposal/confirm | 确认立项书 |
| POST | /api/projects/{id}/plan | 生成执行计划 |
| POST | /api/tasks/{id}/approve | 批准确认点 |
| POST | /api/tasks/{id}/pause | 暂停任务 |
| GET | /api/artifacts/{id} | 获取产物元数据与预览地址 |
| GET | /api/devices/ports | 获取串口列表 |
| POST | /api/devices/connect | 建立设备会话 |
| POST | /api/devices/upload | 上传 MicroPython 文件 |
| POST | /api/devices/flash | 烧录固件，高风险确认 |

### 13.2 WebSocket 统一事件结构

```json
{
  "eventId": "evt_xxx",
  "projectId": "prj_xxx",
  "type": "agent.status.changed",
  "timestamp": "2026-07-07T12:00:00Z",
  "payload": {}
}
```

核心事件类型：chat.delta、chat.completed、project.stage.changed、agent.status.changed、task.progress、task.approval.required、artifact.created、artifact.updated、device.discovered、device.log、device.upload.progress、device.error、security.warning。

### 13.3 错误结构

```json
{
  "code": "DEVICE_PORT_BUSY",
  "message": "串口正在被其他程序占用",
  "userActions": [
    {"id": "retry", "label": "关闭其他程序后重试"},
    {"id": "diagnose", "label": "打开设备诊断"}
  ],
  "technicalDetails": "...",
  "retryable": true
}
```

---

## 14. Agent 架构与调度规则

### 14.1 总控 Agent

输入包括确认立项书、用户画像、当前项目状态、硬件规则结果、可用 Agent/Skill、设备能力和发布需求。输出为任务依赖图和简化用户计划。

总控 Agent 不直接生成所有专业产物。它负责判断“谁来做、先后关系、是否并行、何时确认、如何验收”。

### 14.2 MVP 内置 Agent

| Agent | 责任 | 主要输出 |
|---|---|---|
| Spec Agent | 将立项书转成实现规范 | requirements、architecture、io_map、BOM、acceptance |
| Code Agent | 生成和修复 MicroPython 代码 | firmware、tests、code_report |
| CAD Agent | 参数化结构件 | source、STL、STEP、preview、validation |
| Deploy Agent | 串口上传与设备验证 | backup、deployment_report、logs |
| Publish Agent | 分享页和项目包 | HTML/ZIP、manifest、privacy_report |
| Lesson Agent | 教案与任务单 | lesson_plan、worksheet、rubric |
| Test Agent | 跨产物一致性和运行验证 | test_report、defects |

### 14.3 Model Router

路由输入包括任务类型、上下文长度、代码/视觉能力、用户策略、成本预算、延迟目标、数据敏感级别和供应商可用性。输出包含主模型、回退模型、理由和最大重试次数。

不得把模型名称写死在 Agent 业务逻辑中。Agent 仅引用能力档案，例如 planning、coding、vision、low_cost、private_local。

### 14.4 Tool Runner

工具调用采用“请求—授权—执行—验证—审计”流程。危险操作不得因 Agent 重试而自动重复。具有幂等键的调用必须防止重复上传、重复发布和重复擦除。

### 14.5 Skill 扩展

Skill 使用目录化定义，至少包含 SKILL.md；可选 scripts、references、assets 和 tests。Skill 描述必须明确何时使用、何时不使用。每个 Skill 需要单独的输入输出契约、权限列表和成功验证。

---

## 15. MicroPython 串口工作流

### 15.1 设备发现

- 周期性枚举串口，但不得频繁弹窗。
- 结合 VID/PID、描述符和 esptool 探测识别 ESP 芯片。
- 无法确定开发板变体时，由用户选择，记录到项目设备档案。

### 15.2 日常代码上传

```text
选择设备 → 连接 REPL → 读取版本 → 备份文件
→ 上传依赖与源码 → 校验文件 → 软重启
→ 读取日志 → 冒烟测试 → 生成报告
```

### 15.3 固件烧录

只有以下情况建议烧录：设备无 MicroPython、版本不满足 Spec、REPL 无法恢复、用户主动选择恢复。擦除 Flash 与烧录均需要明确显示板型、固件版本、影响和备份状态，并要求确认。

### 15.4 验收

上传成功必须至少证明：设备重新连接、main.py 启动、没有未处理异常、一个项目核心功能产生可观察结果。仅显示“文件复制完成”不得判定成功。

---

## 16. 安全、隐私与权限

- API Key 存入操作系统安全凭据存储，不写入项目文件和日志。
- 云端发送前根据项目策略脱敏 Wi-Fi、Token、邮箱和路径。
- Skill 默认只能访问当前项目工作区。
- shell 命令采用允许列表、阻止列表和用户审批组合。
- 删除文件进入项目回收区；危险设备操作具有二次确认。
- 学生模式限制任意命令、系统目录、持续电机输出和高风险 PWM。
- 公开分享前执行秘密扫描、个人信息扫描和许可证检查。
- 审计日志记录操作，不记录明文密钥。
- 本地服务只监听 loopback，使用每次启动生成的会话令牌。

---

## 17. 非功能需求

| 类别 | 要求 |
|---|---|
| 启动性能 | 已安装环境下冷启动目标 ≤ 5 秒，项目列表可交互 ≤ 3 秒 |
| 状态更新 | Agent 和设备状态事件到 UI 的延迟目标 ≤ 1 秒 |
| 稳定性 | Agent 或 Python sidecar 崩溃后，应用可恢复最后一致状态 |
| 可恢复性 | 所有长任务具有检查点；重启后可恢复或明确重跑 |
| 可访问性 | 关键功能可键盘操作，文本对比度达到 WCAG AA 目标 |
| 国际化 | MVP 中文优先，文案和枚举不得硬编码在组件中 |
| 可测试性 | 核心状态机、规则引擎和 API 契约具有自动测试 |
| 可观测性 | 本地结构化日志含 traceId、taskId、projectId，不含密钥 |
| 兼容性 | MVP 优先 Windows 10/11，随后 macOS；Linux 为开发支持 |
| 数据完整性 | SQLite 事务与产物原子写入，异常中断不产生半版本 |

---

## 18. 分析与产品指标

在获得用户同意后采集匿名事件：项目创建、画像选择、方案确认、立项确认、Agent 任务成功/失败、串口识别、上传成功、分享导出。不得上传对话正文、代码、设备日志或硬件库存明细作为默认分析数据。

核心漏斗：创建项目 → 完成澄清 → 确认方案 → 确认立项 → 生成 Spec → 生成代码 → 设备上传成功 → 导出/分享。

---

## 19. MVP 范围与迭代路线

### 19.1 MVP P0

- 游客、本地项目、基础注册与四类画像。
- 中央主对话、结构化澄清卡、唯一推荐实现方案。
- 立项书、Spec、Agent 工作计划和状态。
- Spec、Code、Deploy、Test Agent。
- 硬件库与基础电气规则。
- ESP32 串口识别、MicroPython 文件上传、必要时固件烧录。
- 右侧工作/产物/设备栏和文档/代码/终端浮窗。
- 产物版本、确认、退回、快照和 ZIP 导出。

### 19.2 v0.2

- CAD Agent 参数化支架和简单外壳。
- Lesson Agent、教学包和学生模式授权。
- 分享页和局域网预览。
- 更多硬件驱动与板型。

### 19.3 v0.3

- Agent/Skill 可视化管理。
- 本地模型与隐私项目模式。
- 班级、教师分发和作品收集。
- 第三方 Skill 审核与导入。

---

## 20. MVP 验收场景

### 场景 A：教师创建自动浇花项目

教师以游客模式进入，选择教师画像，描述自动浇花装置。系统询问年级、课时、是否联网和预算，生成一套完整实现方案。教师要求删除 OLED 并限制成本，系统生成新版本。确认后生成立项书和工作计划，包含 Spec、Code、Lesson、Test、Deploy。中央对话始终保留；教师通过右侧查看教案和代码浮窗。连接 ESP32 后点击上传并运行，系统备份、上传、重启并显示湿度读取日志。最终导出项目包。

### 场景 B：工程师修改硬件

工程师打开项目，在对话中要求把 ESP32-S3 换为 ESP32-C3。系统先运行规则，指出摄像头功能不兼容并要求选择删除摄像头或恢复主控。用户删除摄像头后，方案、BOM、IO Map、代码任务和结构任务同时更新，旧产物标记过期。用户确认新基线后只重跑受影响任务。

### 场景 C：串口失败恢复

设备端口被其他程序占用。右侧设备栏显示“连接失败”，提供关闭程序后重试和打开诊断。用户重试成功后继续原上传任务，不重新生成代码，不重复擦除 Flash。

### 场景 D：Codex 与 Qoder 交接

Qoder 完成右侧产物栏组件并更新任务执行计划、测试结果和 HANDOFF.md。用户随后使用 Codex 打开同一仓库。Codex读取 AGENTS.md、任务文件、HANDOFF.md 和代码差异，能够直接继续设备栏 API 对接，无需用户重新描述产品规则。

---

## 21. Codex 与 Qoder 无缝协作规范

### 21.1 单一事实来源

优先级从高到低：

1. 已通过测试的代码和数据库迁移。
2. 当前任务的 ExecPlan 与已批准变更。
3. docs/PRD.md、docs/ARCHITECTURE.md、docs/UI_CONTRACT.md、docs/API_EVENTS.md。
4. docs/DECISIONS.md 中的架构决策。
5. HANDOFF.md 当前交接状态。
6. 聊天记录仅作为临时信息，不是事实来源。

### 21.2 共同规则文件

仓库根目录 `AGENTS.md` 是 Codex 与 Qoder 的共同规则。Codex 会按目录层级读取 AGENTS.md；Qoder 可直接兼容项目根目录的 AGENTS.md。不要在两个工具中复制两套含义不同的项目规则。

### 21.3 每个复杂任务必须有任务文件

路径：`tasks/ZW-<编号>-<slug>.md`。任务文件必须包含目标、用户可见结果、范围、非范围、涉及文件、接口、里程碑、进度、决策、测试和交接。任务进行中持续更新，而不是结束后补写。

### 21.4 HANDOFF.md

每次切换工具、暂停工作或提交前更新：当前分支、任务 ID、已完成、未完成、改动文件、运行命令、测试结果、已知问题、下一步和禁止重复事项。接手工具首先读取该文件。

### 21.5 分支与并行规则

- 分支名：`feat/ZW-001-short-name`、`fix/ZW-002-short-name`。
- 同一任务不得让 Codex 和 Qoder同时修改同一工作树。
- 并行工作使用独立 Git worktree 和不同任务文件。
- 提交信息包含任务 ID，如 `feat(ZW-001): add persistent center chat layout`。
- 合并前必须通过格式化、类型检查、单元测试和对应验收场景。

### 21.6 建议分工

Qoder 优先承担 UI 原型、视觉迭代、组件实现、页面联调和基于 Spec 的前端任务；Codex 优先承担架构、跨模块重构、Python 服务、状态机、设备服务、测试和代码审查。该分工不是强制，任务文件和接口契约才是交接边界。

### 21.7 Skill 共享

仓库以 `ai/skills` 为 Skill 源文件，通过同步脚本复制到 Codex 的 `.agents/skills` 与 Qoder 的 `.qoder/skills`。两边 SKILL.md 保持相同语义。任何修改只编辑源目录，然后运行同步和一致性检查。

### 21.8 Agent 配置

Codex 项目 Agent 放在 `.codex/agents/*.toml`；Qoder 项目 Agent 放在 `.qoder/agents/*.md`。两者名称、职责和权限应对齐，但使用各自原生格式。模型默认继承工具当前设置，不在仓库中写死供应商密钥或个人模型 ID。

### 21.9 Definition of Ready

任务进入开发前必须具备：任务 ID、用户结果、范围、至少一个可验证验收标准、涉及模块、接口变更说明、依赖和风险。UI 任务还必须有交互状态；设备任务必须有无硬件模拟方案和安全确认点。

### 21.10 Definition of Done

- 行为满足任务验收。
- 自动测试通过，关键路径有手工验证记录。
- API/事件/数据结构变更已更新契约文档。
- UI 变化已更新 UI Contract 或截图基线。
- 新决策已写入 DECISIONS.md。
- HANDOFF.md 已更新。
- 不含密钥、临时文件和未解释的 TODO。

---

## 22. 风险与应对

| 风险 | 影响 | 应对 |
|---|---|---|
| LLM 对硬件产生幻觉 | 设备损坏或方案不可行 | 结构化硬件库、规则引擎、驱动白名单和人工确认 |
| Agent 任务漂移 | 产物互相矛盾 | 立项基线、Spec 依赖、输入版本锁定和一致性测试 |
| 串口环境差异 | 上传失败率高 | 设备诊断、板型档案、模拟器、可恢复上传和日志解释 |
| UI 功能堆积 | 普通用户难以使用 | 永久主对话、固定三栏、渐进式展示和画像模式 |
| Codex/Qoder 上下文不一致 | 重复开发或错误覆盖 | AGENTS.md、任务文件、HANDOFF、契约文档和独立分支 |
| Skill 权限过大 | 文件或设备风险 | 最小权限、审批、Tool Runner 沙箱和审计 |
| 云端模型供应商变化 | 成本或能力不稳定 | Model Router、能力档案、回退模型和供应商适配层 |

---

## 23. 待确认决策

1. MVP 首发仅 Windows，还是 Windows 与 macOS 同步。
2. 注册服务、自建账号系统与第三方登录的优先级。
3. Tauri 侧串口由 Rust 原生实现，还是全部由 Python pyserial 实现。
4. 硬件库首批支持的开发板和模块清单。
5. 是否在 MVP 提供云同步，或只提供本地导出导入。
6. CAD Agent 是否进入 v0.1 P1，还是完整推迟到 v0.2。
7. 教师/学生授权机制是否在 MVP 实现真实班级关系。

在上述决策未完成前，开发应使用本文默认假设：Windows 优先、Python 统一设备服务、本地项目优先、CAD 与教案为 P1 插拔模块。

---

## 24. 外部工具协作依据

- Codex 使用仓库级 `AGENTS.md` 获取持久项目指令，并支持目录层级覆盖。
- Codex Skill 使用带 `SKILL.md` 的目录，项目级默认可放在 `.agents/skills`。
- Codex 支持项目级 `.codex/agents/*.toml` 自定义 Agent 与 `.codex/config.toml`。
- Qoder 支持 Spec 驱动流程、右侧 Spec 审查、通过对话修改 Spec。
- Qoder 兼容项目根目录 `AGENTS.md`，并支持 `.qoder/skills` 与 `.qoder/agents`。
- 两者均可采用相同的 Skill 内容规范，再通过目录同步适配发现路径。

参考：

- https://developers.openai.com/codex/guides/agents-md
- https://developers.openai.com/codex/skills
- https://developers.openai.com/codex/subagents
- https://developers.openai.com/codex/config-basic
- https://developers.openai.com/codex/learn/best-practices
- https://developers.openai.com/cookbook/articles/codex_exec_plans
- https://docs.qoder.com/user-guide/quest/spec-driven
- https://docs.qoder.com/user-guide/rules
- https://docs.qoder.com/zh/extensions/skills
- https://docs.qoder.com/extensions/subagent
- https://docs.qoder.com/extensions/hooks

---

## 25. 版本变更记录

| 版本 | 日期 | 变化 |
|---|---|---|
| v0.1 | 2026-07-07 | 首次固化；明确永久主对话、唯一推荐实现方案、右侧三分栏、浮窗产物、可扩展 Agent/Skill、模型路由、串口优先和 Codex/Qoder 协作规范 |
