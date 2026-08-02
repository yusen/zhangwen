# 掌问：对话驱动交互与上下文一致性改造任务

版本：v1.0
任务类型：交互架构重构 / 对话编排修复 / 产物与工作栏联动优化
建议任务编号：`ZW-UX-001`
建议任务文件：`tasks/ZW-UX-001-conversation-driven-workflow.md`
执行工具：Codex
最终验收：用户手工验收
适用范围：当前掌问桌面应用，重点覆盖 IDEA、需求澄清、推荐方案、方案修改、立项书、工作栏、产物栏、设备栏

---

# 1. 背景

当前掌问已经具备项目、对话、模型调用、方案、立项书、右侧工作/产物/设备栏等基础能力，但实际使用中仍存在明显的交互割裂与上下文错误：

1. 对话回复存在“答非所问”；
2. AI 提问与用户回答之间的上下文绑定不可靠；
3. 需求澄清虽然使用选项卡，但点击后可能只提交显示文本，未可靠绑定原问题；
4. 用户输入自然语言修改要求时，系统容易重新生成整篇方案，而不是基于当前版本做增量修改；
5. 方案、立项书、工作状态和产物之间缺少统一的数据引用；
6. 用户需要频繁切换右侧“工作”和“产物”；
7. 当前工作栏同时展示大量“待处理”事项，无法突出用户当前唯一需要处理的动作；
8. 对话中可能直接输出超长 Markdown、HTML 或完整立项书，缺少结构化卡片；
9. 关键参数缺失时，系统有时直接默认，有时直接生成，缺少明确的“阻塞—推荐—确认”机制；
10. 项目、对话、问题、回答、方案版本和 Artifact 的关联不够严格，容易出现旧请求、旧状态或旧缓存覆盖当前对话。

本次改造的核心目标是：

> 将掌问重构为“以中央主对话为唯一主流程、以结构化卡片为主要交互、以版本化产物为正式数据、以右侧栏为辅助工作台”的交互体系，并彻底修复对话答非所问和上下文串写问题。

---

# 2. 产品定位

掌问是一个“从创意对话到项目落地”的本地 AI 创客工程工作台。

目标用户：

- 老师；
- 学生；
- 工程师；
- 创客。

用户不应先理解以下技术概念，才能完成项目：

- Agent；
- Skill；
- Artifact；
- Spec；
- Provider；
- 状态机；
- Tool Runner；
- Schema；
- 版本依赖。

普通用户的理想心智模型是：

1. 我描述想法；
2. AI 帮我逐步澄清；
3. AI 给我合适选项；
4. AI 生成一套当前推荐方案；
5. 我通过对话继续修改；
6. AI 把方案、立项书、代码和其他成果自动整理；
7. 我只需要知道现在该做什么。

---

# 3. 本次改造目标

## 3.1 总体目标

建立以下统一交互闭环：

```text
创建项目
→ 输入创意
→ AI理解并澄清
→ 用户点击选项或输入文字
→ AI持续补齐需求
→ 需求达到基本完整
→ AI询问是否生成推荐方案
→ 生成唯一推荐方案
→ 对话中显示结构化方案卡
→ 用户修改 / 接受 / 恢复 / 确认
→ 生成立项书
→ 立项书卡与正式产物同步
→ 工作栏显示当前唯一待处理事项
→ 产物栏管理全部正式产物和版本
→ 设备栏独立处理设备扫描与部署
```

## 3.2 核心成功标准

完成后必须满足：

- 中央主对话始终是主流程；
- 所有关键操作都可通过对话触发；
- 选项卡点击后与原问题严格绑定；
- AI 回复始终针对当前问题和最新用户意图；
- 不再出现明显答非所问；
- 方案修改基于当前版本做增量修改；
- 方案卡在对话中可直接查看；
- 方案同时进入正式 Artifact 系统；
- 工作栏只突出一个当前事项；
- 用户无需频繁切换“工作”和“产物”；
- 关键默认值必须明确展示；
- 关键参数缺失时必须阻塞或请求确认；
- 历史消息、旧方案和旧产物不被覆盖；
- 应用重启后对话卡片、回答状态、方案版本和当前阶段可以恢复。

---

# 4. 不可违反的产品约束

## 4.1 主界面

- 中央区域始终属于 `MainConversation`；
- 项目创建只在左侧栏；
- 设置通过右上角齿轮打开浮窗；
- 设置、方案、立项书、产物、代码、3D、设备不得替换中央主对话；
- 右侧一级栏目固定为：
  - 工作；
  - 产物；
  - 设备。
- 打开浮窗或切换右侧 Tab 不得丢失对话草稿；
- 不允许通过刷新整个应用修复状态问题；
- 不允许通过卸载整个 MainConversation 解决项目切换。

## 4.2 对话

- 对话是主流程；
- 不保留顶部“需求澄清”“生成方案”等流程按钮；
- AI 提问使用聊天消息内部选项卡；
- 用户可点击选项，也可输入文字；
- 同一时刻只突出一个主问题或主操作；
- 已回答卡片不可重复提交；
- 不使用未经格式化的超长 Markdown 作为主要展示；
- 不允许首次创意直接生成代码、HTML、BOM 或立项书。

## 4.3 方案和产物

- 同一时刻前台只展示一套当前推荐方案；
- 旧版本仍可查看；
- 方案修改生成新版本；
- 旧方案不可被覆盖；
- 方案与 Artifact 引用同一份正式数据；
- 立项书只能基于已确认方案生成；
- 方案变化后，旧立项书应标记为过期；
- 不允许修改方案后自动重生成立项书。

## 4.4 Agent、Skill 和模型

- Agent、Skill、模型、Provider、Tool Runner 解耦；
- 普通模式隐藏 Agent、Skill 和内部执行细节；
- 专业模式可以展开；
- LLM 不得绕过确定性规则；
- LLM 不得直接执行串口、Shell 或固件操作。

---

# 5. 当前问题一：对话答非所问

## 5.1 现象

当前截图中，AI 提出问题：

```text
你希望它采用哪种形态？
```

用户选择：

```text
桌面实体设备
```

系统虽然显示选项已回答，但后续对话仍可能出现：

- 未继续围绕产品形态追问；
- 回复与选项无关；
- 重复提出已经回答的问题；
- 使用上一轮或上一项目的上下文；
- 将选项文本当成新的独立创意；
- 把用户选择错误解释为“生成方案”或其他动作；
- 继续执行旧请求。

## 5.2 可能根因

必须重点排查：

1. 选项点击只提交 `label`，没有提交 `questionId`；
2. 后端只收到“桌面实体设备”，不知道这是哪个问题的答案；
3. 消息记录没有 `replyToMessageId` 或 `replyToQuestionId`；
4. 当前流程状态只存在前端，没有持久化；
5. Prompt 没有注入当前未回答问题；
6. Prompt 注入了过多历史消息，但没有突出最新意图；
7. 新请求与旧流式请求并行，旧响应覆盖新响应；
8. 缓存 key 没有包含 `projectId / conversationId / turnId`；
9. 用户点击卡片时触发了重复提交；
10. 选择后前端立即标记“已回答”，但服务端处理失败；
11. LLM 返回结构化结果后，前端错误映射到其他问题；
12. 当前项目切换后仍复用旧 `conversationState`；
13. 对话编排通过关键词判断动作，未使用明确 `actionType`；
14. 系统 Prompt 未明确要求只回答当前问题；
15. 结构化输出缺少相关性校验。

---

# 6. 对话上下文一致性改造

## 6.1 每次交互必须绑定完整上下文

每个请求必须至少携带：

```ts
interface ConversationTurnContext {
  projectId: string;
  conversationId: string;
  turnId: string;
  parentTurnId?: string;
  replyToMessageId?: string;
  replyToQuestionId?: string;

  currentStage:
    | "idea"
    | "clarification"
    | "ready_for_solution"
    | "solution_draft"
    | "solution_confirmed"
    | "proposal_draft"
    | "proposal_confirmed"
    | "execution";

  currentIntent:
    | "describe_idea"
    | "answer_question"
    | "request_recommendation"
    | "generate_solution"
    | "revise_solution"
    | "confirm_solution"
    | "generate_proposal"
    | "revise_proposal"
    | "confirm_proposal"
    | "continue_project"
    | "device_request"
    | "general_chat";

  activeQuestionId?: string;
  activeSolutionId?: string;
  activeSolutionVersion?: number;
  activeProposalId?: string;
  activeArtifactId?: string;
}
```

不能只发送一段文本。

## 6.2 选项回答必须使用结构化提交

单选提交：

```ts
interface SingleChoiceAnswer {
  type: "single_choice_answer";
  projectId: string;
  conversationId: string;
  questionId: string;
  optionId: string;
  optionValue: string;
  optionLabel: string;
  clientTurnId: string;
}
```

多选提交：

```ts
interface MultipleChoiceAnswer {
  type: "multiple_choice_answer";
  projectId: string;
  conversationId: string;
  questionId: string;
  optionIds: string[];
  optionValues: string[];
  optionLabels: string[];
  clientTurnId: string;
}
```

自定义输入：

```ts
interface TextQuestionAnswer {
  type: "text_question_answer";
  projectId: string;
  conversationId: string;
  questionId: string;
  text: string;
  clientTurnId: string;
}
```

## 6.3 用户消息仍需自然显示

虽然内部使用结构化提交，聊天历史中仍显示自然语言，例如：

```text
桌面实体设备
```

但消息必须附带元数据：

```ts
interface ChatMessageMetadata {
  replyToQuestionId?: string;
  answerType?: "single" | "multiple" | "text";
  answerOptionIds?: string[];
  actionType?: string;
}
```

## 6.4 服务端必须验证回答归属

服务端收到回答后必须检查：

- questionId 是否属于当前 projectId；
- questionId 是否属于当前 conversationId；
- question 是否仍处于未回答状态；
- question 是否允许该 optionId；
- question 是否已被提交；
- 当前 turn 是否仍是最新有效 turn；
- 项目是否已经切换；
- 是否存在重复 clientTurnId。

验证失败时不得继续调用 LLM。

应返回明确错误：

- `QUESTION_NOT_FOUND`
- `QUESTION_ALREADY_ANSWERED`
- `OPTION_NOT_ALLOWED`
- `STALE_CONVERSATION_TURN`
- `PROJECT_CONTEXT_MISMATCH`
- `DUPLICATE_TURN`

## 6.5 问题回答持久化

建议增加或复用：

```ts
interface ClarificationAnswerRecord {
  id: string;
  projectId: string;
  conversationId: string;
  questionId: string;
  answerType: "single" | "multiple" | "text";
  values: string[];
  labels: string[];
  userMessageId: string;
  createdAt: string;
}
```

问题记录：

```ts
interface ClarificationQuestionRecord {
  id: string;
  projectId: string;
  conversationId: string;
  sourceMessageId: string;
  stage: string;
  text: string;
  mode: "single" | "multiple" | "text";
  options?: ClarificationOption[];
  required: boolean;
  status: "pending" | "answered" | "superseded" | "cancelled";
  answeredAt?: string;
}
```

## 6.6 LLM Prompt 上下文优先级

Prompt 应按以下顺序组织：

1. 系统产品规则；
2. 当前项目摘要；
3. 当前阶段；
4. 当前用户意图；
5. 当前未回答问题；
6. 用户最新回答；
7. 已确认的结构化需求；
8. 最近必要对话；
9. 历史摘要；
10. 可用工具和限制。

不要把完整历史原样放在最新意图之前。

建议明确加入：

```text
你必须只处理“当前用户意图”和“当前活动问题”。

当前活动问题：
{{activeQuestion.text}}

用户对该问题的回答：
{{latestAnswer}}

已经确认的需求：
{{confirmedRequirements}}

禁止：
- 回答其他旧问题；
- 重复已回答问题；
- 根据其他项目消息推断；
- 在信息不足时直接生成方案；
- 忽略当前回答；
```

## 6.7 回复相关性校验

LLM 返回后，编排层必须执行轻量校验。

至少检查：

- 返回类型是否符合当前阶段；
- 如果当前 intent 是 `answer_question`，返回是否：
  - 更新该问题对应需求字段；
  - 或提出下一个问题；
  - 或进入 ready_for_solution；
- 不允许返回代码、HTML、立项书；
- 不允许重复相同 questionId；
- 不允许返回与当前项目无关的实体；
- 不允许把旧方案当成当前方案。

建议返回：

```ts
interface ConversationResponseEnvelope {
  projectId: string;
  conversationId: string;
  requestTurnId: string;
  responseTurnId: string;
  responseType:
    | "clarification"
    | "next_action"
    | "solution_card"
    | "solution_revision"
    | "proposal_card"
    | "status"
    | "error";
  content: unknown;
  statePatch: ConversationStatePatch;
}
```

前端写入前必须验证：

```text
response.projectId === currentProjectId
response.conversationId === currentConversationId
response.requestTurnId === latestPendingTurnId
```

否则忽略为 stale response。

---

# 7. 需求澄清交互重构

## 7.1 首次创意

用户输入：

```text
自动浇花装置
```

AI 应先回复：

```text
很棒，这是一个可以根据土壤状态自动浇水的小项目。

为了确定更合适的实现方式，我先了解一个关键需求。
```

然后显示问题卡：

```text
你希望它主要用于什么场景？
```

选项：

- 室内花盆；
- 阳台植物；
- 小型种植箱；
- 由掌问推荐；
- 其他，我来补充。

不得直接生成：

- 完整方案；
- BOM；
- HTML；
- 代码；
- 立项书。

## 7.2 每轮只问 1 个关键问题

默认每轮只显示一个问题。

只有两个问题强关联且不会造成认知负担时，才允许同时显示两个。

不得一次展示大量固定问题。

## 7.3 选项文案必须是用户视角

错误示例：

```text
灯带接在哪个引脚？我帮你写代码
```

这是 AI 对用户说的话，不应作为用户选择。

正确示例：

```text
[ 使用推荐引脚 ]
[ 我知道具体引脚 ]
[ 稍后再确定 ]
```

## 7.4 推荐默认值必须显式展示

点击“由掌问推荐”后，不应直接静默采用默认值。

应回复：

```text
我建议采用以下默认设置：

- 使用场景：室内花盆；
- 供电方式：USB 5V；
- 主控：ESP32；
- 浇水方式：小型水泵；
- 触发方式：土壤湿度低于阈值。

你可以直接继续，也可以修改其中任意一项。
```

显示：

- 接受推荐；
- 修改默认设置；
- 继续补充。

## 7.5 需求完整度

完整度不应只是百分比装饰。

完整度应基于明确字段：

```ts
interface RequirementCompleteness {
  requiredFields: string[];
  completedFields: string[];
  missingFields: string[];
  blockingFields: string[];
  score: number;
  readyForSolution: boolean;
}
```

只有关键字段完成后才能进入“可以生成方案”。

---

# 8. 借鉴的交互机制

本次改造必须吸收以下优秀机制：

## 8.1 项目是统一容器

每个项目统一绑定：

- 对话；
- 需求；
- 当前问题；
- 推荐方案；
- 立项书；
- Artifact；
- Agent 执行；
- 代码；
- CAD；
- 设备；
- 日志。

禁止跨项目共享临时状态。

## 8.2 信息不足时显式阻塞

关键字段不足时：

- 显示“还需要你的协助”；
- 明确缺失内容；
- 提供选项；
- 支持推荐默认值；
- 不直接继续高风险执行。

## 8.3 表达不明确时主动澄清

例如用户输入：

```text
改成第二种和第三种混合
```

如果当前上下文无法唯一确定，应追问：

```text
你指的是“灯光提醒 + 屏幕显示”吗？
```

并提供确认卡。

## 8.4 关键决策在执行前锁定

正式生成方案前必须锁定：

- 项目形态；
- 核心功能；
- 主要硬件方向；
- 预算或难度；
- 关键供电；
- 必要安全限制。

## 8.5 成果必须产物化和版本化

正式结果必须进入 Artifact：

- 推荐实现方案；
- 立项书；
- Spec；
- 代码；
- CAD；
- 教案；
- 部署日志。

## 8.6 执行过程以内联步骤展示

中央对话可显示简洁执行状态：

```text
正在整理需求
正在检查硬件兼容性
正在生成方案
正在保存产物
```

专业模式可展开详细步骤。

普通用户不直接看到大量命令。

---

# 9. 中央对话消息体系

建议统一以下结构化消息：

```ts
type StructuredChatContent =
  | ClarificationCard
  | RecommendationDefaultsCard
  | NextActionCard
  | SolutionCard
  | SolutionRevisionCard
  | ProposalCard
  | ExecutionStatusCard
  | ErrorRecoveryCard
  | DeviceResultCard;
```

## 9.1 ClarificationCard

用途：

- 提出一个关键问题；
- 单选、多选或文字回答；
- 绑定 questionId；
- 显示已回答状态。

操作：

- 选择；
- 确认多选；
- 由掌问推荐；
- 其他补充。

## 9.2 RecommendationDefaultsCard

用途：

- 展示 AI 推荐默认值；
- 明确说明系统准备采用什么；
- 用户可接受或修改。

## 9.3 NextActionCard

需求基本完整后显示：

```text
接下来希望怎么继续？
```

操作：

- 生成推荐实现方案；
- 继续补充需求；
- 由掌问完善并生成。

## 9.4 SolutionCard

默认摘要：

- 名称；
- 版本；
- 状态；
- 核心功能；
- 主控与关键硬件；
- 成本；
- 难度；
- 时间；
- 本次变化。

操作：

- 展开完整方案；
- 修改方案；
- 确认方案；
- 打开浮窗。

## 9.5 SolutionRevisionCard

显示：

- 基础版本；
- 新版本；
- 修改内容；
- 保持不变内容；
- 影响范围；
- 是否导致旧立项书过期。

操作：

- 接受本次修改；
- 继续修改；
- 恢复上一版本；
- 查看完整方案。

## 9.6 ProposalCard

显示：

- 立项书版本；
- 基于哪个方案；
- 状态；
- 是否过期；
- 章节摘要。

操作：

- 查看；
- 修改；
- 确认；
- 导出。

## 9.7 ErrorRecoveryCard

用于：

- 回答过期；
- 网络失败；
- LLM 输出校验失败；
- 项目切换导致请求失效；
- 设备扫描失败。

必须提供：

- 重试；
- 返回当前项目；
- 重新发送；
- 查看详情。

---

# 10. 方案生成流程

## 10.1 生成前

需求完整后，AI 不自动生成。

显示：

```text
当前需求已经基本完整。

接下来你希望怎么继续？
```

选项：

- 生成推荐实现方案；
- 继续补充需求；
- 由掌问完善并生成。

## 10.2 生成后

聊天中显示 `SolutionCard`。

同时：

1. 保存 `ImplementationSolution`；
2. 创建 `Artifact`；
3. 创建 `ArtifactVersion`；
4. 插入 `SolutionCardMessage`；
5. 更新工作栏“当前方案”；
6. 更新工作栏“最新产物”；
7. 更新产物栏；
8. 不自动切换右侧 Tab。

## 10.3 完整方案卡章节

- 项目目标；
- 用户需求；
- 功能逻辑；
- 硬件清单；
- 软件模块；
- 结构建议；
- 实施步骤；
- 成本；
- 难度；
- 时间；
- 风险；
- 验收标准；
- 默认假设。

---

# 11. 方案修改流程

## 11.1 增量修改

用户输入：

```text
把声音提醒改成灯光提醒
```

系统必须：

1. 找到当前方案；
2. 识别修改范围；
3. 只修改相关章节；
4. 保留其他章节；
5. 生成新版本；
6. 返回变更摘要；
7. 不自动生成立项书。

## 11.2 数据模型

```ts
interface SolutionRevision {
  id: string;
  projectId: string;
  baseSolutionId: string;
  baseVersion: number;
  newSolutionId: string;
  newVersion: number;
  userRequest: string;
  changedSections: SolutionSectionChange[];
  preservedSections: string[];
  impactSummary: string[];
  createdAt: string;
}
```

## 11.3 立项书依赖

流程：

```text
修改方案
→ 生成新方案版本
→ 用户确认新方案
→ 旧立项书标记 outdated
→ 用户选择是否更新立项书
→ 创建新立项书版本
```

---

# 12. 右侧工作栏重构

## 12.1 定位

工作栏是“当前项目行动中心”，不是全部待办列表。

## 12.2 建议结构

```text
工作
├─ 当前阶段
├─ 当前唯一待处理事项
├─ 当前方案迷你卡
├─ 最新产物（最多3个）
└─ 简化步骤条
```

## 12.3 当前唯一事项

同一时刻只突出一个：

```text
需要回答：使用场景
```

或：

```text
需要确认方案 v2
```

或：

```text
需要更新立项书
```

## 12.4 简化步骤条

```text
创意 ✓
需求 ●
方案 ○
立项书 ○
Spec ○
代码 ○
设备 ○
```

## 12.5 删除或弱化

- 大量同权重待办卡片；
- 重复说明；
- 用户暂时无法操作的后续任务；
- 内部 Agent 名称；
- 技术状态枚举。

---

# 13. 右侧产物栏重构

产物栏只负责：

- 查看全部产物；
- 查看历史版本；
- 筛选类型；
- 查看过期关系；
- 导出；
- 归档；
- 查看依赖。

刚生成的方案无需用户先进入产物栏。

聊天卡和工作栏快捷入口应直接打开浮窗。

---

# 14. 设备栏

设备栏保持独立，不干扰对话主流程。

至少包括：

- 扫描设备；
- 串口列表；
- 端口名称；
- 描述；
- VID/PID；
- 推测开发板；
- 状态；
- 最近扫描时间；
- 空状态；
- 错误恢复。

设备扫描必须通过 Tauri 或 Sidecar。

前端不得直接访问串口。

---

# 15. 状态机

## 15.1 用户可见状态

- 正在了解需求；
- 等待你的回答；
- 可以生成方案；
- 方案待确认；
- 方案修改中；
- 立项书待确认；
- 工程实施中；
- 等待连接设备；
- 项目已完成。

## 15.2 内部状态

```ts
type ProjectWorkflowState =
  | "IDEA_EMPTY"
  | "IDEA_RECEIVED"
  | "CLARIFICATION_PENDING"
  | "CLARIFICATION_PROCESSING"
  | "READY_FOR_SOLUTION"
  | "SOLUTION_GENERATING"
  | "SOLUTION_DRAFT"
  | "SOLUTION_REVISING"
  | "SOLUTION_CONFIRMED"
  | "PROPOSAL_GENERATING"
  | "PROPOSAL_DRAFT"
  | "PROPOSAL_CONFIRMED"
  | "EXECUTION_PLANNING"
  | "EXECUTION_RUNNING"
  | "DEVICE_PENDING"
  | "COMPLETED";
```

禁止仅通过聊天文本判断阶段。

---

# 16. 数据与 API 改造

## 16.1 Contracts

需要检查和补充：

- ConversationTurnContext；
- ClarificationQuestion；
- ClarificationAnswer；
- StructuredChatContent；
- ConversationResponseEnvelope；
- RequirementCompleteness；
- ImplementationSolution；
- SolutionRevision；
- Artifact；
- ArtifactVersion；
- ProjectWorkflowState。

## 16.2 API

建议接口：

```text
POST /api/projects/{projectId}/conversations/{conversationId}/turns
POST /api/projects/{projectId}/questions/{questionId}/answers
POST /api/projects/{projectId}/solutions/generate
POST /api/projects/{projectId}/solutions/{solutionId}/revise
POST /api/projects/{projectId}/solutions/{solutionId}/confirm
POST /api/projects/{projectId}/proposals/generate
GET  /api/projects/{projectId}/workflow
GET  /api/projects/{projectId}/artifacts
```

按现有架构调整，不得重复建立两套接口。

## 16.3 幂等

每个请求带：

```text
clientTurnId
```

重复请求返回同一结果，不重复生成消息、方案或 Artifact。

---

# 17. 异步与并发控制

必须修复：

- 旧请求覆盖新请求；
- 项目切换后旧流式响应继续写入；
- 重复点击选项产生重复回答；
- 页面重载后重复生成。

建议：

- 每个请求绑定 projectId、conversationId、turnId；
- 使用 AbortController 或 request token；
- 服务端检查 stale turn；
- 前端 pending 状态禁用重复操作；
- 结构化卡片提交采用幂等键；
- 响应写入前校验上下文。

---

# 18. Prompt 改造

## 18.1 澄清阶段

必须包含：

- 当前只理解需求；
- 只处理当前活动问题；
- 每轮最多 1–2 个问题；
- 不生成代码；
- 不生成 HTML；
- 不生成完整 BOM；
- 不生成立项书；
- 不直接生成最终方案；
- 已回答问题不得重复；
- 回答必须与用户最新输入相关；
- 支持结构化选项；
- 支持“由掌问推荐”。

## 18.2 方案阶段

只有用户明确触发后：

- 生成唯一推荐方案；
- 返回结构化方案；
- 不返回未经解析的超长 Markdown；
- 明确默认假设；
- 使用硬件规则结果；
- 不生成代码。

## 18.3 修改阶段

必须输入：

- 当前方案；
- 基础版本；
- 用户修改指令；
- 已确认需求；
- 依赖产物状态。

必须输出：

- revisedSolution；
- changedSections；
- preservedSections；
- impactSummary；
- requiresProposalUpdate。

---

# 19. 实施批次

## 批次一：上下文一致性与答非所问修复

目标：

- questionId / turnId / projectId / conversationId 全链路绑定；
- 选项结构化提交；
- stale response 防护；
- 幂等；
- Prompt 最新意图优先；
- 相关性校验。

验收：

- 选择“桌面实体设备”后，AI 能正确记录并继续问下一相关问题；
- 不重复问题；
- 不跨项目；
- 不受旧响应覆盖。

## 批次二：结构化对话卡片

目标：

- ClarificationCard；
- RecommendationDefaultsCard；
- NextActionCard；
- 已回答状态；
- 历史恢复。

## 批次三：方案卡与增量修改

目标：

- SolutionCard；
- SolutionRevisionCard；
- 版本；
- 增量修改；
- 恢复上一版本；
- 立项书过期。

## 批次四：工作栏与产物联动

目标：

- 当前唯一事项；
- 当前方案；
- 最新产物；
- 简化步骤条；
- Artifact 同步；
- 点击直接浮窗。

## 批次五：设备栏与整体回归

目标：

- 串口扫描；
- 空状态；
- 错误状态；
- 不影响中央对话；
- 全流程回归。

---

# 20. 自动测试要求

## 20.1 上下文测试

覆盖：

1. questionId 正确绑定；
2. 回答错误 questionId 被拒绝；
3. 已回答问题重复提交被拒绝；
4. 项目不匹配被拒绝；
5. stale turn 被忽略；
6. 重复 clientTurnId 幂等；
7. 旧流式响应不写入新项目；
8. Prompt 包含当前问题和最新回答；
9. 返回类型符合当前阶段；
10. 不出现与当前问题无关的响应。

## 20.2 卡片测试

覆盖：

- 单选；
- 多选；
- 自定义输入；
- 由掌问推荐；
- 已回答状态；
- 重启恢复；
- 键盘操作；
- 不重复提交。

## 20.3 方案测试

覆盖：

- 生成唯一方案；
- 创建 Artifact；
- 方案卡和 Artifact 引用一致；
- 增量修改；
- 旧版本保留；
- 旧立项书过期；
- 不自动重生成立项书。

## 20.4 工作栏测试

覆盖：

- 同时只突出一个当前事项；
- 当前方案正确；
- 最新产物最多 3 个；
- 点击查看不强制切换 Tab；
- 草稿不丢失。

## 20.5 设备测试

覆盖：

- 多端口；
- 空列表；
- 字段缺失；
- 扫描失败；
- 刷新；
- 不影响对话。

## 20.6 验证命令

运行受影响范围：

- Contracts typecheck；
- 前端 typecheck；
- 前端测试；
- Sidecar 测试；
- 数据库迁移测试；
- Tauri cargo check；
- Desktop build；
- 阶段级回归。

自动测试不得调用真实付费 LLM。

---

# 21. 手工验收清单

## 21.1 答非所问

- [ ] 新建项目；
- [ ] 输入“自动浇花装置”；
- [ ] AI 提出与浇花相关的问题；
- [ ] 点击“室内花盆”；
- [ ] AI 正确记录并继续问相关问题；
- [ ] 不重复刚才的问题；
- [ ] 不突然生成代码；
- [ ] 不回复其他项目内容。

## 21.2 推荐默认值

- [ ] 点击“由掌问推荐”；
- [ ] 系统明确展示默认设置；
- [ ] 用户可接受或修改；
- [ ] 不静默采用高风险默认值。

## 21.3 方案

- [ ] 需求完整后显示下一步卡；
- [ ] 用户选择后才生成方案；
- [ ] 对话中出现方案卡；
- [ ] 右侧工作栏同步；
- [ ] 产物栏同步；
- [ ] 完整方案可展开；
- [ ] 不出现超长原始 Markdown。

## 21.4 修改方案

- [ ] 输入“把声音提醒改成灯光提醒”；
- [ ] 只显示变更摘要；
- [ ] 其他内容保持不变；
- [ ] 生成新版本；
- [ ] 可以恢复上一版本；
- [ ] 不自动生成新立项书。

## 21.5 工作栏

- [ ] 只突出一个当前事项；
- [ ] 当前方案可直接查看；
- [ ] 最新产物可直接打开；
- [ ] 无需频繁切换产物 Tab。

## 21.6 项目隔离

- [ ] 项目 A 与项目 B 的消息独立；
- [ ] 卡片回答独立；
- [ ] 方案独立；
- [ ] 旧请求不覆盖新项目；
- [ ] 草稿独立。

## 21.7 设备

- [ ] 进入设备 Tab 自动扫描一次；
- [ ] 可手动刷新；
- [ ] 显示 COM 端口；
- [ ] 空状态正确；
- [ ] 错误提示正确；
- [ ] 不影响主对话。

---

# 22. 非范围

本次不做：

- ZW-017；
- Windows 正式发布；
- 代码签名；
- 公共发布；
- 电商实时价格；
- 自动采购；
- 自动真实烧录；
- 自动真实设备连接；
- 全新视觉品牌重构；
- 替换现有主框架；
- 删除历史消息；
- 删除旧方案；
- 删除旧产物；
- 使用真实付费 LLM 自动测试。

---

# 23. Codex 执行要求

Codex 执行本任务时：

1. 先读取：
   - AGENTS.md
   - WORKFLOW.md
   - CURRENT_TASK.md
   - HANDOFF.md
   - 本任务文件
   - docs/PRD.md
   - docs/UI_CONTRACT.md
   - docs/ARCHITECTURE.md
   - docs/API_EVENTS.md
   - docs/DECISIONS.md
   - 最近两个 Git 提交
   - 当前 git status

2. 先输出：
   - 当前根因；
   - 可复用实现；
   - 修改文件；
   - Contracts/API/数据库影响；
   - 实施批次；
   - 测试计划。

3. 如无不可逆风险，直接按批次实施。

4. 每完成一个批次：
   - 更新本任务文件；
   - 更新 HANDOFF.md；
   - 运行最小测试；
   - 记录测试结果；
   - 不提前跳过当前批次验收。

5. 不得：
   - 重新盘点整个仓库；
   - 重写已通过模块；
   - 删除历史数据；
   - 创建重复协议；
   - 通过隐藏 UI 掩盖后端错误；
   - 通过关键词匹配替代明确动作类型；
   - 通过全局单例保存项目会话；
   - 自动提交 Git；
   - 进入 ZW-017。

6. 全部完成后输出：
   - 根因；
   - 实际修改；
   - 数据流；
   - 对话状态机；
   - 答非所问修复机制；
   - 卡片机制；
   - 方案与 Artifact 关系；
   - 工作栏变化；
   - 设备栏变化；
   - 测试；
   - 手工验收步骤；
   - git status；
   - git diff 摘要。

完成后停止，等待用户手工验收。

---

# 24. 执行结果（2026-07-09）

## 24.1 根因确认

本轮确认的主要根因是：

1. 选项卡回答原先可退化为普通文本，缺少 `questionId / turnId / projectId / conversationId` 的全链路绑定；
2. 旧流式响应和异步刷新缺少严格 `requestTurnId` 过滤，存在覆盖当前项目/当前对话的风险；
3. 方案生成、方案修改、聊天展示和 Artifact 系统之间存在多入口状态，导致普通用户需要在“工作 / 产物”之间频繁切换；
4. 方案修改缺少基于当前版本的修订模型，容易被当作重新生成完整方案；
5. 右侧工作栏信息层级过多，不能突出当前唯一需要处理的事项。

## 24.2 批次完成情况

| 批次 | 状态 | 完成内容 |
|---|---|---|
| 批次一：上下文一致性与答非所问修复 | 已完成 | 新增 v16 turn/question/answer 持久化；请求携带 `clientTurnId`、`turnContext`、`structuredAnswer`；服务端校验 question/project/conversation/option/idempotency；SSE 带 `requestTurnId/responseTurnId`；前端按 project/conversation/request turn 忽略旧流。 |
| 批次二：结构化对话卡片 | 已完成 | 澄清卡、下一步卡、方案卡通过 `structuredPayload` 持久化；点击选项会生成自然用户消息并提交结构化回答；已回答卡片不可重复提交；顶部“需求澄清 / 生成方案”流程按钮不再作为入口。 |
| 批次三：方案卡与增量修改 | 已完成 | 方案生成插入 `solution_card`；方案修改基于当前版本创建新 draft 版本，记录 `changedSections`、`preservedSections`、`impactSummary`；旧版本保留；立项书不自动重新生成。 |
| 批次四：工作栏与产物联动 | 已完成 | 方案生成/修订同步创建或更新正式 Artifact/ArtifactVersion；聊天方案卡和右侧产物引用同一 `solutionId/artifactId/artifactVersionId`；工作栏改为项目总览，只突出一个当前事项、当前方案和最近 3 个产物。 |
| 批次五：设备栏与整体回归 | 已完成 | 设备栏保持独立 scan-only 串口扫描；前端不访问串口或 Shell；支持空状态、错误状态、刷新状态；不自动连接、不运行 `mpremote/esptool`、不烧录。 |

## 24.3 修改范围

- Contracts：`packages/contracts/src/enums.ts`、`packages/contracts/src/api.ts`、`packages/contracts/src/index.ts`。
- Desktop：`CenterChat`、`ConversationResponseCard`、`ChatInput`、`AppShell`、`RightPanel`、`WorkTab`、`DevicesTab`、`useProjects`、`projectsApi`、相关 CSS 与测试。
- Sidecar：`chat/router.py`、`chat/idea_flow.py`、`projects` migrations/models/repository/errors、`solutions` models/repository/router、`artifacts/repository.py`、`devices` models/router/simulator/serial_discovery、LLM 错误契约、MVP readiness schema 检查。
- Tests：项目隔离、DeepSeek 主对话、右侧栏、项目仓库、项目聊天流、设备、迁移和阶段级 Sidecar 回归。
- Docs：`docs/API_EVENTS.md`、`docs/DECISIONS.md`、`HANDOFF.md`。

## 24.4 Contracts / API / 数据库影响

- `ProjectPersistenceVersion.V16` / SQLite `PRAGMA user_version=16`。
- `messages.metadata_json`。
- 新表：`conversation_turns`、`clarification_questions`、`clarification_answers`。
- `PersistedChatRequest` 新增/使用 `clientTurnId`、`turnContext`、`structuredAnswer`。
- `ProjectStreamChunk` 携带 `requestTurnId`、`responseTurnId`。
- 新增对话意图、工作流状态、结构化回答类型和上下文错误码。
- 方案版本新增 lineage/artifact 关联字段，方案修订记录 `SolutionRevision` / `SolutionSectionChange`。

## 24.5 验证结果

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- DeepSeekChat.test.tsx`：通过，7 files / 53 tests。
- `pnpm --filter @zhangwen/desktop test`：通过，7 files / 53 tests。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py services/local-api/tests/test_project_chat_stream.py -q --rootdir services/local-api`：通过，14 passed。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`：通过，106 passed，1 个已知 Starlette warning；Windows pytest 临时目录 cleanup `PermissionError` 仍为已知环境警告。
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`：通过。
- `pnpm build:desktop`：通过。
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen`：通过。
- `git diff --check`：通过，仅有 Windows LF/CRLF 提示。
- `pnpm tauri:build`：通过，release 桌面二进制重新生成。

## 24.6 外部手工验证待办

- 真实 DeepSeek API Key 连接和真实付费模型响应未在自动测试中调用。
- 真实本机串口枚举、ESP32 插拔刷新、端口占用状态仍需用户手工验收。
- 真实 `mpremote`、`esptool`、Flash 擦除、固件烧录和设备文件覆盖不在本任务自动范围内，且不得自动执行。
