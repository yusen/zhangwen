# ZW-004：需求澄清与唯一推荐实现方案

## 1. 背景

ZW-003 已完成项目管理、会话历史和 SQLite 持久化。当前中央主对话支持自由文本流式对话，但缺少结构化的需求澄清流程和方案生成能力。ZW-004 的目标是让用户通过结构化问答完善需求，并生成一套唯一推荐实现方案。

## 2. 目标

1. 用户在中央主对话中提出创意；
2. 掌问通过结构化问题识别需求信息缺口；
3. 通过少量问题逐步完善需求；
4. 用户手动触发生成一套唯一推荐实现方案；
5. 用户通过对话持续修改方案；
6. 用户确认当前方案版本。

## 3. 必须实现

- 需求澄清状态（CLARIFYING 阶段）；
- 单选问题卡片；
- 多选问题卡片；
- 文本补充问题卡片；
- "由掌问推荐"标记；
- 需求完整度评估；
- DeepSeek 结构化输出（system prompt + JSON）；
- 唯一推荐实现方案生成；
- 方案版本管理；
- 方案确认（→ SOLUTION_CONFIRMED）；
- 方案修改（生成新版本）。

## 4. 非范围

- 真实硬件规则引擎（ZW-005）；
- 立项书（ZW-006）；
- Agent/Skill/Orchestrator（ZW-007+）；
- 串口/固件（ZW-012）；
- 产物管理（ZW-009）；
- 用户画像/注册；
- 多套方案对比。

## 5. 现有能力复用

- `ProjectStage`：IDEA → CLARIFYING → SOLUTION_DRAFT → SOLUTION_CONFIRMED
- DeepSeek 流式对话（SSE + 取消 + 错误映射）
- 项目级聊天持久化（消息、草稿、模型）
- `CenterChat` 常驻 + 流式渲染 + 草稿自动保存
- `ConfirmDialog` 共享组件
- 项目管理 CRUD

## 6. 数据模型与 Contracts

新增共享类型：ClarificationQuestionType、ClarificationOption、ClarificationQuestion、ClarificationAnswer、ClarificationRound、SolutionSection、SolutionVersion、SolutionStatus、API 请求/响应类型。

## 7. 架构与边界

- 澄清卡片嵌入中央聊天消息流（A-01 方案一）；
- DeepSeek 结构化输出：system prompt + JSON 格式要求 + 流式完成后解析（A-02 方案一）；
- 方案存储在 SQLite 新表 solutions，user_version = 2 迁移（A-03 方案一）；
- 不设完整度阈值，用户手动点击"生成方案"（A-04 方案三）。

## 8. UI 与交互

- 澄清问题以卡片形式出现在聊天消息流中；
- 每个选项旁"✦ 掌问推荐"标记（B-04）；
- 每轮最多 3 个问题（B-01）；
- 完整度进度条 + 百分比文字（B-05）；
- 方案摘要卡片在聊天流中，完整方案通过浮窗查看；
- 确认方案后项目阶段变为 SOLUTION_CONFIRMED。

## 9. 实施里程碑

### M1 — Contracts 澄清与方案数据模型
### M2 — Sidecar 澄清服务与结构化输出
### M3 — 前端澄清卡片 UI
### M4 — 前端方案卡片与版本管理
### M5 — 阶段状态流转与集成

## 10. Decision Log

### A 类（必须用户确认）

| 编号 | 当前问题 | 方案对比 | 推荐 | 用户选择 | 影响 |
|------|---------|---------|------|---------|------|
| A-01 | 澄清卡片渲染位置 | 方案一：嵌入聊天流；方案二：右侧工作栏；方案三：独立浮窗 | 方案一 | **方案一** | CenterChat 消息渲染增加卡片类型分支 |
| A-02 | DeepSeek 结构化输出策略 | 方案一：system prompt + JSON + 流式完成解析；方案二：response_format json_object 非流式；方案三：普通流式 + 后处理 | 方案一 | **方案一** | Sidecar 流式完成后增加 JSON 解析步骤 |
| A-03 | 方案存储方式 | 方案一：SQLite 新表 user_version=2；方案二：JSON 文件；方案三：消息内容中 | 方案一 | **方案一** | SQLite schema 迁移到 v2 |
| A-04 | 完整度阈值 | 方案一：固定 70%；方案二：可配置 70%；方案三：不设阈值，手动触发 | 方案二 | **方案三** | 用户手动点击"生成方案"按钮 |

### B 类（建议确认，有推荐默认值）

| 编号 | 事项 | 推荐默认值 | 用户反馈 |
|------|------|-----------|---------|
| B-01 | 每轮最多问题数 | 3 | 接受 |
| B-02 | 方案章节清单 | 项目目标、工作逻辑、硬件组成、软件模块、结构实现、实施步骤、成本与工期、风险与限制 | 接受 |
| B-03 | 方案确认后可修改 | 是，生成新版本 | 接受 |
| B-04 | "由掌问推荐"标记 | 选项旁"✦ 掌问推荐"小标签 | 接受 |
| B-05 | 完整度展示 | 进度条 + 百分比文字 | 接受 |

### C 类（可自行决定）

| 编号 | 事项 | 决定 |
|------|------|------|
| C-01 | 澄清卡片 CSS 类名 | `.clarification-card` 系列 |
| C-02 | JSON 解析辅助函数 | `extract_json_from_text()` |
| C-03 | 测试 mock 数据 | 使用"智能浇花装置"作为示例 |

## 11. 需要 Codex 介入

当前不需要。以下条件满足时再考虑：

- 结构化 LLM 输出持续无法稳定校验；
- 需求状态机出现复杂恢复问题；
- 方案版本产生跨模块一致性问题；
- Qoder 连续两次修复失败。

## 12. Minimum Test Plan

| 里程碑 | 最小测试 |
|--------|---------|
| M1 | Contracts build + typecheck |
| M2 | 澄清问题生成 + 回答处理 + 方案生成 + 版本管理 + JSON 解析容错（Mock DeepSeek） |
| M3 | typecheck + 单选项/多选项/文本渲染 + 提交回答 + "由掌问推荐"标记 |
| M4 | typecheck + 方案摘要渲染 + 确认操作 + 版本切换 |
| M5 | typecheck + 阶段变化集成测试 |

## 13. Validation

```powershell
pnpm --filter @zhangwen/contracts build
pnpm --filter @zhangwen/contracts typecheck
pnpm --filter @zhangwen/desktop typecheck
pnpm --filter @zhangwen/desktop test
.\.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api
```

## 14. Progress

- [x] M1 Contracts：ClarificationQuestionType、SolutionStatus 枚举 + 13 个接口类型
- [x] M2 Sidecar：澄清服务（DeepSeek JSON 结构化输出）+ 方案仓库（SQLite v2）+ 4 个 API 端点
- [x] M3 前端澄清：ClarificationCard（单选/多选/文本 + 完整度进度条 + “✦ 掌问推荐”）
- [x] M4 前端方案：SolutionCard（摘要 + 确认/修改/查看完整方案）
- [x] M5 集成：IDEA → CLARIFYING → SOLUTION_DRAFT → SOLUTION_CONFIRMED 阶段流转
- [x] 聊天回复完成后自动触发需求澄清（IDEA/CLARIFYING 阶段）

## 15. Handoff
