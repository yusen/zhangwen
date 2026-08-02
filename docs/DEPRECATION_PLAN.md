# 掌问废弃与删除计划

版本：ZW-STABILIZE-001

日期：2026-07-10

本计划只处理已经被当前基线覆盖的实现。删除必须同时满足：仓库内无调用、仓库外兼容风险已处理、存在明确替代实现、替代路径有自动测试。数据库表、旧专家值和用户数据字段默认不删除。

## 已满足删除条件

| 文件或模块 | 当前调用方证据 | 替代实现 | 删除风险 | 删除前所需测试 | 结果 |
|---|---|---|---|---|---|
| `apps/desktop/src/components/clarification/ClarificationCard.tsx` | `rg` 无 import/JSX 调用 | `components/chat/ConversationResponseCard.tsx` 的 clarification card | 低；旧文件不在 bundle | DeepSeekChat 的结构化澄清、批量回答与 CenterChat 回归 | 已删除 |
| `apps/desktop/src/components/clarification/SolutionCard.tsx` | `rg` 无 import/JSX 调用 | `ConversationResponseCard.tsx` 内的 SolutionCard | 低；旧文件不在 bundle | DeepSeekChat 方案卡生成/确认/修订与 RightPanel 产物回归 | 已删除 |
| `services/local-api/zhangwen/stubs/__init__.py` | 全仓无 `zhangwen.stubs` import；文件只有预留注释 | `main.py` 已注册的真实模块 | 极低；不包含运行逻辑 | Python compileall、全量 pytest | 已删除 |

## 待废弃，当前禁止删除

| 文件或模块 | 当前调用方 | 替代实现 | 删除风险 | 删除前所需测试 |
|---|---|---|---|---|
| `apps/desktop/src/services/projectsApi.ts`：`clarifyProject`、`answerClarification` | 仓库内只有定义；仓库外调用未知 | `CenterChat/useChatStream` → `/api/projects/{id}/chat/stream` 的 structured answer | 旧安装或脚本编译/API 兼容破坏 | 建立 API 使用清单；证明所有桌面入口走 chat；至少一个旧客户端兼容/迁移测试 |
| 同文件：`listSolutions`、`getCurrentSolution`、`generateSolution`、`confirmSolution`、`reviseSolution`、`restorePreviousSolution` | 仓库内只有 wrapper 定义；测试 mock 仍认识 current URL；仓库外调用未知 | conversationAction + `ConversationResponseCard` + `ArtifactsTab` | 专业模式、旧客户端或第三方脚本可能依赖 | 删除 wrapper 前做 TypeScript 引用门禁、主流程 UI 测试和旧 API 调用审计 |
| `services/local-api/zhangwen/clarification/router.py` | `main.py` 注册；没有桌面调用；无端点行为测试 | `chat/router.py` + `chat/idea_flow.py` + 持久化 question/answer | API breaking；历史 `clarification_rounds` 读取/迁移可能丢失 | 外部调用审计；历史 v1/v14/v22 DB 回放；对话批量回答等价测试；先发布 deprecated 响应/文档 |
| `services/local-api/zhangwen/solutions/router.py` 的写路由 | `main.py` 注册；硬件校验/required-LLM 测试仍直接调用部分端点；外部调用未知 | `chat/idea_flow.py` 的 generate/confirm/revise/restore 动作 | API breaking；可能绕开硬件校验或影响旧自动化 | 把独立路由特有校验迁入共享 service；对两条入口做等价测试；完成兼容期后再删 |
| `clarification_rounds` 表与 migration 建表逻辑 | 独立 clarification router 写入；历史 DB 可能有数据 | messages、question records、clarification answers | 用户历史澄清数据不可逆丢失；违反 forward-only 兼容 | 读取/转换工具、迁移备份、历史 DB fixture、幂等数据迁移和回滚恢复演练；本轮禁止改表 |
| legacy ExpertType aliases 与旧线程字段 | migrations、ProjectRepository、experts config、前端显示映射直接调用 | canonical 三师类型 + legacy 映射 | 旧项目无法打开、线程合并或归属丢失 | 覆盖每个旧值的 v18/v19/v22 migration、项目包导入和线程不合并测试；没有数据保留策略前长期保留 |
| `docs/three-expert-current-state-analysis.md` 与早期 phase 文档的“current”表述 | 无运行时调用，但可能被人工误读 | `docs/CURRENT_BASELINE.md`、最新 PRD/DECISIONS | 直接删除会丢历史决策证据 | 先移入 archive、修复所有入站链接、文档链接检查；不与代码清理混做 |

## FIX 后再评估，不属于删除候选

| 模块 | 当前调用方 | 整改方向 | 风险 | 所需测试 |
|---|---|---|---|---|
| `components/right-panel/WorkTab.tsx` | RightPanel 在工作 Tab 直接挂载 | 只做内部按能力拆分，保持普通/专业模式和 DOM 契约 | 大范围拆分易改变主 UI | RightPanel 全量测试、UI Contract 验证、类型/构建 |
| `utils/experts.ts` 的状态 fallback | CenterChat、LeftSidebar | 后端 workspaceStatus 保持权威；fallback 只服务旧响应 | 移除过早会使旧项目无状态文本 | 新旧 workspace DTO fixtures 与中文状态测试 |
| `ArtifactsTab.tsx` 的双状态映射 | RightPanel 产物 Tab | 形成共享 selector/契约映射，不更改显示分组 | 可能把当前方案分到历史区 | Solution/Artifact 同版本、draft/confirmed/stale/outdated 矩阵测试 |
| Python models 与 TS contracts | 所有 API/桌面边界 | 建立 schema/fixture 自动对照，优先消除严格度漂移 | 单边修改会再次造成运行时漂移 | contracts build/typecheck + Python serialization fixture + desktop parse test |

## 删除执行门禁

任何后续删除任务必须在同一个变更中提供：

1. `rg` 引用结果、路由注册和桌面 API 调用证明。
2. 明确替代模块及其数据/错误语义对照。
3. 旧 SQLite 与项目包 fixture 的前向兼容测试。
4. 主流程闭环、contracts、desktop、backend、Cargo 和 `git diff --check` 通过。
5. 不删除 Project、Conversation、Draft、PrivateMemory、Artifact、ArtifactVersion 或 legacy thread 数据。
