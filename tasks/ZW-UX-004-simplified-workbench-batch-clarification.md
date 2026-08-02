# ZW-UX-004 — 批量澄清与工作台简化

状态：已完成（2026-07-10）

## 1. 目标

在三师系统最终架构上完成一次用户定向 UX 收敛：

1. 问题引导师一次返回的全部必答问题必须在本地完成后整组提交，只调用一次云端 LLM。
2. 保留 48px 顶栏、240px 左栏、永久中央主对话和 320px 右栏“工作 / 产物 / 设备”不变量。
3. 左侧只承担当前项目总览、三师导航和项目资源；新建/切换项目及低频工具移出常驻左栏。
4. 中央专家头部改为紧凑状态栏，详细共享事实和产物入口按需展开。
5. 普通模式的“工作”页只突出一个当前事项和少量任务摘要，不平铺全部后续工程能力。
6. 专业模式、模型、Skill、工程生成器、详细检查和日志入口下沉到设置、折叠详情或浮窗。

## 2. 非目标

- 不修改三师领域边界、EntryRouter 或 ProjectCoordinator 的核心职责。
- 不新增用户可见 Agent、Skill 或右侧一级 Tab。
- 不删除旧项目、旧消息、旧答案、旧产物、旧版本或 legacy 专家兼容数据。
- 不调用真实付费 LLM，不扫描或连接真实串口，不执行 `mpremote`、`esptool`、Flash 擦除或固件烧录。
- 不创建、规划或实现 `ZW-017`。

## 3. 当前问题与代码位置

- `ConversationResponseCard.tsx` 的单选点击立即调用 `onAnswer`；`CenterChat.tsx` 的 `handleAnswer` 立即发送一次聊天请求。
- `StructuredQuestionAnswer` 和后端 `_answer_fields()` 一次只支持一个 `questionId`。
- `LeftSidebar.tsx` 同时承载新建、当前项目、最近项目、模板、项目包和硬件库，超过 240px 常驻导航应承担的职责。
- `WorkTab.tsx` 在普通模式平铺当前事项、专家状态、冲突、流程、MVP 检查以及 Plan/Spec/Code/CAD/Lesson 生成器。
- `ExpertConversationHeader` 重复专家名称并长期占用中央首屏高度。
- 专业模式开关位于“工作”页，和项目当前事项混在同一信息层级。

## 4. 契约与行为设计

### 4.1 批量澄清答案

共享 contracts 新增 `ClarificationBatchAnswer`：

- `type = "clarification_batch_answer"`
- `projectId`
- `conversationId`
- `sourceMessageId`
- `clientTurnId`
- `answers[]`，每项包含 `questionId`、答案类型、选项 ID/标签或文本。

兼容规则：

- 保留旧单题 `single_choice_answer`、`multiple_choice_answer`、`text_question_answer` 读取能力。
- 新桌面客户端对 `questions[]` 使用批量答案；单问题也可走批量路径，避免两套新交互。
- 后端验证答案全部属于同一来源消息和当前会话，覆盖全部未回答必答项，且无重复或非法选项。
- 所有答案记录、用户消息和 confirmed SharedFact 在一次本地事务语义中落库；Provider 失败后答案不丢失，重试只重新生成助手回复。
- 完整答案集合以结构化内容传给问题引导师，只触发一次 Provider 调用和一次协调器更新。

### 4.2 界面职责

- 顶栏：产品、项目切换、新建项目、阶段、连接状态、设置和低频项目工具。
- 左栏：项目总览、已参与专家、项目资源。
- 中央：紧凑专家栏、永久对话、整组澄清卡、固定输入区。
- 工作：当前唯一事项、最多三条进行中/等待任务、最近完成摘要。
- 产物：当前推荐方案优先，其余按状态浏览；复杂预览使用浮窗。
- 设备：普通模式显示连接摘要和上下文动作；专业模式再显示日志、Dry Run 和高级信息。

## 5. 里程碑

### M1：整组澄清契约与一次性 LLM 调用

- 先更新 contracts 和前后端失败测试。
- 实现批量答案模型、验证、持久化、上下文组装和一次 Provider 调用。
- 将实际项目会话收敛为一个问题组组件；选择只更新本地结构化草稿。
- 全部必答问题完成前禁用提交；提交后锁定整组并显示答案摘要。
- 覆盖自定义文本、多选、幂等、缺项、重复项、非法项和 Provider 失败重试。

### M2：精简右侧“工作”

- 普通模式只保留当前事项、紧凑任务和最近完成。
- 将 MVP readiness、Plan/Spec/Code/CAD/Lesson 等高级工程能力放入专业模式折叠详情。
- 删除普通模式中的长期禁用生成器卡片和重复专家/冲突/流程展示。
- 保持唯一 PendingItem 领域来源，不在前端重算优先级。

### M3：整理左侧入口与中央头部

- 顶栏增加项目切换与新建项目入口。
- 新建项目使用不卸载中央对话的对话框/覆盖层；高级专家选择默认折叠。
- 左栏移除常驻新建、最近项目、模板、项目包和完整硬件库。
- 项目包、硬件库、重命名和归档移到低频项目工具对话框。
- 专家移除放入更多菜单；专家主行只显示名称、中文状态和必要徽标。
- 中央专家头部收敛为单行状态栏，详情按需展开。

### M4：普通/专业模式分层与 UI 契约验收

- 将专业模式开关移到设置。
- 普通模式隐藏模型、Skill、工具链、内部 ID 和高级工程控制。
- 专业模式保留现有受控能力，复杂内容通过折叠区或浮窗展示。
- 复核产物当前方案唯一、设备权限、右侧固定 Tab、草稿/滚动/附件/引用保持和响应式布局。
- 运行全量后端、contracts、desktop、构建、Cargo、敏感信息和 UI 验收。

## 6. 验收标准

- 三个必答问题完成前，前端不发送聊天请求；完成并点击提交后只发送一次请求。
- 批量请求包含全部答案；后端只调用一次 fake Provider，并保存全部答案。
- 缺少必答答案、重复 questionId、非法选项、陈旧消息或错误会话返回可识别的 4xx 错误。
- 切换右侧 Tab、专业模式、专家或浮窗后，未提交问题选择和文本草稿保持。
- 普通模式左栏只显示项目总览、三师和项目资源；低频入口不再常驻。
- 普通模式“工作”只突出一个当前事项，首屏不平铺 MVP/Plan/Spec/Code/CAD/Lesson 生成器。
- 中央对话保持同一挂载节点；输入草稿、滚动位置、附件和引用上下文不因右侧或浮层变化丢失。
- 右侧一级 Tab 仍严格为“工作 / 产物 / 设备”，所有状态均有中文文本。
- 当前推荐方案始终只有一套；旧版本保留在产物历史中。
- 1280x720 和窄窗口无文本溢出、无控件重叠、无不可达主要操作。

## 7. Progress

- 2026-07-10：用户确认按建议顺序完整实施。创建 `ZW-UX-004` ExecPlan，M1 开始；保留现有 `ZW-UX-003` 运行态交接记录和未提交文档修改。
- 2026-07-10：M1 完成。新增 `clarification_batch_answer` 共享契约、Python 判别联合模型和 schema v22；同一 `clientTurnId` 可保存多题答案，但每个 question record 仍只能回答一次。
- 2026-07-10：后端批量路径在插入消息前验证来源消息、会话、重复 questionId、必答覆盖和选项合法性；整组答案与 turn/消息同一 repository 事务写入，随后只调用一次 fake Provider，并为每题确认 SharedFact。
- 2026-07-10：桌面实际项目对话改为单个澄清问题组。单选、多选和自定义输入只更新按项目/线程/消息隔离的本地结构化草稿，完成全部必答项后才启用整组提交；主输入框在存在未完成问题组时禁用。
- 2026-07-10：M1 验证通过：contracts build/typecheck、Python compile、44 个 chat/repository/clarification/end-to-end 定向后端测试、8 个 DeepSeekChat/ProjectIsolation 桌面测试和 desktop typecheck。
- 2026-07-10：M2 开始，普通模式“工作”页将只保留唯一当前事项和紧凑任务摘要，高级工程能力保留在专业模式折叠详情。
- 2026-07-10：M2 完成。普通模式“工作”页移除方案/产物、专家状态、冲突、流程和工程生成器重复展示，只保留唯一 PendingItem、最多三条活动/等待任务和最近完成摘要；MVP readiness、Plan/Spec/Code/CAD/Lesson、Skill 与模型路由仅在专业模式“工程详情”中渲染并按需加载。
- 2026-07-10：M2 验证通过：`RightPanel` 25 个测试和 desktop typecheck 通过；既有 React `act(...)` 警告仍存在。M3 开始，整理顶栏项目入口、左侧常驻内容和中央专家头部。
- 2026-07-10：M3 完成。顶栏新增项目切换、新建项目和项目工具入口；创建、重命名、归档、项目包和硬件库改为覆盖层，左栏只保留项目总览、已参与三师和项目资源。专家移除进入更多菜单，中央专家头部收敛为单行状态栏和按需详情。
- 2026-07-10：M3 验证通过：`AppShell`、`ProjectWorkspace`、`ProjectIsolation`、`DeepSeekChat`、`RightPanel` 共 56 个桌面测试和 desktop typecheck 通过；覆盖层打开期间 `CenterChat` 保持同一挂载节点。M4 开始，迁移专业模式设置并收敛产物/设备普通模式及响应式 UI 契约。
- 2026-07-10：M4 第一轮实现完成。专业模式开关移入设置；普通产物页只突出唯一当前方案并隐藏筛选、来源、依赖和详细版本信息；普通设备页隐藏 VID/PID、序列号、日志和 Dry Run；项目阶段、路由策略、校验级别与设备日志状态补齐中文标签。
- 2026-07-10：左右栏均可折叠，`<=720px` 首次加载默认收起并作为覆盖层展开。新增右栏折叠/展开回归，确认 `CenterChat` 保持同一节点且未保存草稿不丢失；`RightPanel` 聚焦测试 31/31 通过。
- 2026-07-10：完成 `1280x720`、`720x720`、`390x844` 和 `320x568` 浏览器验收。修复手机端“新建项目”文字截断，将其改为保留无障碍名称/提示的“+”入口，并将项目总览双列改为单列。各视口无页面横向溢出，中央对话始终单实例，最终控制台无错误或警告。
- 2026-07-10：M4 UI 实现与契约验收完成，开始执行任务规定的全量后端、前端、构建、Cargo、敏感信息与 Git 收尾验证。
- 2026-07-10：M4 与 ZW-UX-004 自动验收完成。contracts build/typecheck、Python compile、desktop typecheck、根 typecheck、desktop build、Cargo 和 `git diff --check` 通过；定向后端 23 个、全量后端 132 个、定向桌面 62 个、全量桌面 66 个测试通过。
- 2026-07-10：已知输出仅为既有 Starlette TestClient 弃用警告、React `act(...)` 警告和 Windows LF/CRLF 转换提示。未调用真实付费 LLM，未扫描或操作真实设备，未推送。阶段提交/标签为 `feat(ZW-UX-004): simplify workbench and batch clarification` / `zw-ux-004-complete`。

## 8. Decision Log

- 2026-07-10：使用用户定向 UX 编号 `ZW-UX-004`，不创建禁止的 `ZW-017`。
- 2026-07-10：批量提交按全部 `required=true` 问题判断，不硬编码问题数量为 3。
- 2026-07-10：保留旧单题 API 兼容读取，新桌面主路径统一使用批量答案。
- 2026-07-10：普通模式以“下一件该做的事”为信息中心；高级工程能力不删除，只下沉到专业模式和浮窗。
- 2026-07-10：项目创建与低频工具使用覆盖层，覆盖层不得卸载中央 `CenterChat`。
- 2026-07-10：schema v22 仅移除 `clarification_answers(project_id, conversation_id, client_turn_id)` 的旧唯一约束，保留 `question_record_id` 唯一约束和全部旧答案；迁移前仍由 repository 自动备份并记录审计。
- 2026-07-10：`<=720px` 左右栏默认收起并使用覆盖层；`<=520px` 顶栏新建入口显示为“+”，但必须保留 `aria-label="新建项目"` 和 tooltip，项目总览改为单列。

## 9. 预计修改范围

- Contracts：`packages/contracts/src/api.ts`、`packages/contracts/src/index.ts`。
- Backend：`projects/models.py`、`projects/repository.py`、`chat/router.py`、`chat/idea_flow.py` 及测试。
- Desktop：`AppShell`、顶栏、左栏、中央对话、澄清卡、设置、右侧三个 Tab、CSS 和测试。
- Docs：`docs/API_EVENTS.md`、`docs/DECISIONS.md`、`docs/UI_CONTRACT.md`、本任务和 `HANDOFF.md`。

## 10. 验证命令

- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `.venv\Scripts\python.exe -m compileall -q services/local-api/zhangwen services/local-api/tests`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_chat_stream.py services/local-api/tests/test_zw004_clarification_solution.py -q --rootdir services/local-api`
- `pnpm --filter @zhangwen/desktop test -- DeepSeekChat ProjectWorkspace ProjectIsolation RightPanel SettingsDeepSeek AppShell`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`
- `pnpm --filter @zhangwen/desktop test`
- `pnpm typecheck`
- `pnpm --filter @zhangwen/desktop build`
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`
- `git diff --check`

## 11. 安全与回滚

- 不提交 `.codex/config.toml`，不读取或输出真实 API Key。
- 自动测试只使用 fake Provider、Mock 工具和模拟数据。
- 不执行真实串口扫描、连接、上传、Flash 或固件操作。
- 回滚以本任务独立提交为边界；数据库不新增破坏性 migration。
