# ZW-UX-009 V2 对话中心 UI 全面重构（Studio 方向）

> **Legacy / 已冻结**：本任务的历史实现与验收记录保留用于教学端和迁移回归。自 2026-07-31
> 起不得在此任务或 V2 壳继续增加创作端产品功能；Creator V3 后续工作统一进入
> `tasks/ZW-CREATOR-001-creator-workbench-rebaseline.md`。

状态：M0-M7 全部完成（2026-07-28）。M7 已通过前端、后端、严格类型、生产构建与真实
桌面 1282px / 744px 宽窄屏复核；真实设备与高风险动作未执行。

## 背景与目标

V2 工作台（`apps/desktop/src/components/v2/`）当前是"三列工作台 + 右侧 AI 栏"布局，视觉与组件
结构存在三类问题：

1. **样式双轨**：`visual-system.css`（948 行正式 token）与 `v2-workspace.css`（82 行自定义
   `--v2-*` 变量）并存，`App.css` 还残留 7604 行单体式样式，设计 token 没有唯一事实源。
2. **组件巨型化**：`V2Workspace.tsx` 684 行承载四个工作区全部页面；共享的 `DevicesTab.tsx`
   2048 行、`CenterChat.tsx` 794 行；壳组件 `V2AppShell.tsx` 404 行混合导航、浮窗、桥接、
   变更集、Job 抽屉五种职责。
3. **对话边缘化**：产品灵魂是"一个项目、一条时间线、一个输入框"，但 V2 把对话压缩在
   390px 右栏，工作区与 AI 协作上下文割裂。

用户在 2026-07-27 确认：视觉 + 架构全面重构；**仅 V2 工作台**（V1 壳保留作 feature flag
回退，不做视觉改动）；**允许调整布局**（可突破"中央主对话 + 右侧 工作/产物/设备"的
V1 布局契约）；采用 **方向 B（对话即工作台）为基线，融合方向 A 的优点**；分阶段稳步推进。

## 设计定稿（B 为主，融合 A）

原型归档：`outputs/ui-redesign/direction-a-console.html`、`direction-b-studio.html`。

壳布局（B 基线）：

- **深色图标轨（72px）**：品牌、对话、项目（滑出面板）、概览/工程/结构/交付、底部
  Local Bridge / 设置 / 账号。继承现有 `#0f203b` 深海军蓝基因。
- **中央舞台**：默认是 AI 对话时间线（最大阅读宽 ~780px 居中），顶部为项目标题
  （名称 + 版本 + 阶段 pill）与页签行（对话 | 概览 | 工程 | 结构 | 交付）；底部为固定
  输入区（专家胶囊行 + 大输入框 + 模型选择 + 发送）。
- **右侧上下文检查器（380px）**：页签为 变更 / 事实 / 产物 / 任务；内容随舞台页签
  切换责任域（概览→问题引导师上下文，工程→智能工程师，结构→结构工程师）。
- **状态栏（30px）**：本地服务健康、云端 LLM、本地任务 pill、设备状态。

从方向 A 融合的元素：

1. 项目/版本导航采用 A 的列表形态：图标轨"项目"按钮打开左侧滑出面板，含项目列表、
   新建项目、版本列表（V1 导入基线标记保留）。
2. 概览页保留 A 的"下一步"入口条（工程/结构/交付三张入口卡）。
3. 四个工作区页面统一 A 的页头模式（eyebrow + 标题 + 副标题 + 操作区）。
4. 普通/专业模式切换放入舞台头部右侧，不降级到设置深层。
5. Change Set 除检查器"变更"页签外，在对话内以紧凑内联卡提示待确认数量。

Token 定稿：

- 新增 `apps/desktop/src/styles/v2-tokens.css`，以 `--zw-*` 前缀定义 V2 唯一事实源：
  色板（surface/border/text 三级）、品牌色、三位专家角色色（引导蓝/工程绿/结构紫）、
  状态色、深色轨配色、圆角/阴影/控件高/动效/字体与等宽字体。
- 数值以 `visual-system.css` 既有 token 为基础（保持 V1/V2 同族），补充深色轨与
  对话舞台所需新值；`visual-system.css` 不改动，继续服务 V1。

## 范围与边界

做：

- `components/v2/` 全部壳与工作区组件、其专用样式与测试。
- `CenterChat` 所在舞台容器与主题 token 化（不改其 DOM 结构与交互契约）。
- 共享 UI 原语（Button/Card/Pill/Segmented/Tabs）收敛到 `components/shared/ui/`。
- `docs/UI_CONTRACT.md`、PRD_V2 相关段落、HANDOFF/CURRENT_TASK/PLANS 同步。

不做：

- V1 `AppShell` 与 `App.css` 视觉不改；`VITE_ZHANGWEN_V2_UI=0` 回退路径保持可用。
- 不改共享 contracts、REST/SSE API、SQLite schema、Runtime/Kernel 行为。
- 不拆 `DevicesTab.tsx` 内部逻辑（仅容器适配；其 2048 行结构拆分留作后续独立任务，
  见 Decision Log）。
- 不调用真实 Provider、串口、上传、复位、Flash、安装或发布。
- 不使用 `git add -A`、stash/reset/clean；不覆盖共享工作树其他任务差异。

用户在 2026-07-27 追加 M5 范围，覆盖上面的“REST/共享 contracts 不改”默认边界：
只允许为 CAD Intent 增加受控 `ProjectStructureContext` 契约和服务端派生上下文，不允许
前端上传任意上下文、原始聊天记录、路径、凭据或全局硬件目录。

## 里程碑

- [x] M0：设计方向确认（B 为主融合 A）、双原型归档、ExecPlan 建立、HANDOFF/CURRENT_TASK 切换。
- [x] M1：Token 层与壳骨架。先补壳布局测试（图标轨存在、CenterChat 单挂载、页签切换、
  检查器页签、折叠/窄屏态），再实现 `v2-tokens.css`、新 `V2AppShell`（轨/舞台/检查器/
  状态栏/项目滑出面板）、Job 抽屉迁移为检查器"任务"页签 + 状态栏 pill。
  完成证据（2026-07-27）：新增 `styles/v2-tokens.css`（--zw-*）、`styles/v2-shell.css`、
  `components/v2/shell/{IconRail,StageHeader,Inspector,StatusBar,ProjectDrawer}.tsx` 与
  `labels.ts`；`V2AppShell.tsx` 重写为 Studio 布局（默认对话舞台、工作区页签、检查器
  变更/事实/产物/任务）；`v2-workspace.css` 只保留页面规则；`main.tsx` 引入新样式。
  `V2WorkspaceShell.test.tsx` 4 passed；desktop 全量 36 files / 223 passed 与基线一致；
  strict tsc 与 production Vite build 通过（仅既有 Monaco 大分块提示）。
  备注：本机默认 reporter 下 vitest 进程退出滞留（测试本身秒级完成且全绿），
  后续本地跑全量建议 `--reporter=basic` 或 CI 非交互模式。
- [x] M2：四工作区页面重构。概览（hero/能力覆盖/事实/待确认/下一步条）、工程
  （硬件/代码/设备/验证子页）、结构（对象树/视口/属性）、交付（版本/Release/产物），
  统一新视觉与页头模式；每页先补内容呈现测试。
  完成证据（2026-07-27）：`v2-workspace.css` 全量 token 化（卡片、列表、子导航、
  CAD 视口、产物工作台、Bridge 对话框均改用 --zw-*）；概览页新增"下一步"入口条
  （工程/结构/交付三卡，呈现真实进度：待确认代码数、结构修订状态、最新版本），
  经新 `onOpenWorkspace` 回调切换舞台页签；页头主按钮更名"返回对话"。
  新增概览入口导航测试；`V2WorkspaceShell.test.tsx` 5 passed；
  desktop 全量 36 files / 224 passed（基线 223 + 新增 1）；strict tsc 与
  production Vite build 通过（仅既有 Monaco 大分块提示）。
- [x] M3：组件架构整理。`V2Workspace` 拆为 `v2/pages/` 四个文件；壳拆为
  `v2/shell/{IconRail,StageHeader,Inspector,StatusBar,ProjectDrawer}.tsx`；样式按
  `v2-tokens/v2-shell/v2-stage/v2-inspector/v2-pages` 拆分；`App.css` 中 V2 残留清零；
  共享原语入 `components/shared/ui/`。
  完成证据（2026-07-27）：`V2Workspace.tsx`（约 740 行）拆为路由文件（约 190 行）+
  `v2/pages/{common,OverviewPage,EngineeringPage,StructurePage,DeliveryPage}.tsx`；
  `artifactKindLabel/artifactStatusLabel` 去重收敛到 `shell/labels.ts`；
  `App.css` 经检索确认无 `v2-`/`zw-` 残留（V2 样式本就不在 App.css）；
  desktop 全量 36 files / 224 passed、strict tsc 与 production build 通过。
- [x] M4：浮窗与对话框（FloatingWindow、Settings、ProjectCreation、LocalBridge）视觉
  统一；窄屏与折叠态完善；全量回归、文档更新、HANDOFF 收尾。
  完成证据（2026-07-27）：新增 `styles/v2-overlays.css`，浮窗/设置/新建项目对话框
  仅经 `.zw-shell` 作用域覆盖（V1 外观不变）；状态栏接入既有 `useHealthCheck` +
  `HealthIndicator`；检查器经舞台头部"上下文"按钮折叠/展开，窄屏转为右侧抽屉，
  页签行可横向滚动，560px 下图标轨收敛；`docs/UI_CONTRACT.md` 与 `docs/PRD_V2.md`
  增加 2026-07-27 Studio 布局修订。新增健康/检查器折叠测试；
  `V2WorkspaceShell.test.tsx` 6 passed；desktop 全量 36 files / 225 passed；
  strict tsc 与 production Vite build 通过（仅既有 Monaco 大分块提示；
  prepareOutDir 偶发 Windows dist 瞬时被占失败，复跑即过，与代码无关）。
- [x] M5：修复图标轨可读性，导航按钮必须常显中文标签并保持文本状态、键盘焦点和
  `aria-current`；新增 `ProjectStructureContext`，由 Sidecar 从当前项目版本、初始创意、
  推荐方案、已确认事实、当前项目硬件、已确认机械档案、上游产物和当前 CAD 修订派生。
  Worker 必须按“本轮明确输入 > 当前 CAD 修订 > 已确认项目上下文”消费；不得再把全局
  ACTIVE 硬件目录作为项目 `selectedHardwareIds`，冲突或信息不足时返回澄清/needs_input。
  完成证据（2026-07-27）：`IconRail` 为全部入口增加图标下中文短标签，并修正
  `.zw-shell button` 的选择器优先级覆盖；真实运行窗口确认非选中入口对比度清晰。
  Python Adapter 以当前 Project State/Workspace 和 `ContextAssembler` 派生 96 KiB 上限、
  Pydantic `extra=forbid` 的上下文，request hash 绑定 `contextSha256`，capability snapshot
  仅保留当前项目已验证能力。Worker 对上下文做项目/版本/hash 校验并只映射白名单字段，
  显式本轮产品意图先检测，再回退项目语义。验证：desktop 全量 36 files / 225 passed；
  M5 UI 定向 2 files / 18 passed；Worker 来源+协议 10 passed；CAD Intent 4 passed（含真实
  GLB/STEP/STL 生成与文件 hash 验证）；contracts build、strict tsc、production build
  通过。本地 API 重启后 `/api/health` 返回 `status=ok`。
- [x] M6：普通模式信息减法与术语收敛。取消顶部与左侧重复的工作区导航；右侧一级
  Tab 收敛为固定“工作 / 产物 / 设备”，其中设备页签懒加载真实设备工作区，折叠后
  不销毁已访问状态；普通模式隐藏版本号、hash、Change Set、CAD Intent、Worker、
  Job、Release、Artifact 等内部词和原始状态码，改为用户任务语言。结构页普通模式
  只保留模型部件、3D 预览、描述输入和当前动作，修订历史及工程字段仅在专业模式显示。
  `CenterChat` 继续单一挂载，所有设备动作仍保留原安全确认点。
- [x] M7：对话流体化与主动推进。普通模式删除固定澄清问卷和题号/进度/批量提交语言，
  让主输入框直接回答当前唯一问题；历史多问题消息在前端逐个自然呈现，最后仍复用
  `clarification_batch_answer` 批量提交。三师及 CAD 新响应最多产生一个改变产品方向的
  阻塞问题，可逆低风险细节默认推进，非阻塞缺口记为验证项。普通模式左侧只保留
  “对话 / 项目 / 连接 / 设置”，右栏默认收起；结果卡只保留标题、两行摘要和一个主动作，
  专业模式完整保留现有工作区、版本、文件及诊断字段。设备扫描、连接、上传、复位与
  Flash 门禁不变。
  完成证据（2026-07-28）：普通模式主输入框直接回答当前唯一问题，推荐/自由输入捷径
  可用；历史多问题逐个收集后仍一次提交。三师 Runtime、clarification service 与 CAD
  intake 执行单阻塞问题和主动默认策略，明确盒体尺寸可直接重开 revision。普通导航、
  单状态和代码/3D/方案结果卡完成减法，`CenterChat` 保持单挂载。真实桌面复核发现并
  修复 `.zw-inspector` 作者样式覆盖原生 `hidden` 的问题，1282×831 与 744×831 均确认
  右栏默认收起、主对话可用。验证为 desktop `36 files / 229 passed`，后端 `740 passed`，
  strict TypeScript 与 production build 通过；补充窄屏侧栏测试后定向 `8 passed`。

## 验收门禁（每里程碑）

1. 先补/改自动测试，再实现（AGENTS.md 契约先行）。
2. `pnpm typecheck`（strict）、desktop `vitest` 全量（当前基线 36 files / 223 passed）
   保持绿色且只增不减；production Vite build 通过。
3. 真人可回退：`VITE_ZHANGWEN_V2_UI=0` 启动后 V1 全功能可用。
4. 测试只用 Fake Provider / Mock 设备；不触真实外部副作用。

## Decision Log

- 2026-07-27：方向定为"B 为主融合 A"。理由：对话是产品主叙事，B 更贴合"一个项目、
  一条时间线、一个输入框"；A 的项目/版本列表、工作区页头和概览入口条经确认是高效
  元素，予以保留。
- 2026-07-27：`--zw-*` 新前缀而非复用 `--color-*`：避免 V2 重构期改动 V1 视觉，
  两壳 token 可独立演进；M4 收尾时评估是否回填统一。
- 2026-07-27：`DevicesTab.tsx`（2048 行）不在本任务拆分。它同时服务 V1 右栏与 V2
  工程页，逻辑含设备安全状态机；纯结构拆分需独立任务与专项回归，先只做容器适配。
- 2026-07-27：Job 抽屉从底部抽屉改为检查器"任务"页签 + 状态栏 pill。理由：底部
  40px 常驻抽屉在对话中心布局中侵占舞台纵向空间；运行中数量在状态栏保持可见。
- 2026-07-27（M1）：对话为默认舞台视图；工作区上下文在切到"对话"页签时保持为最后
  访问的工作区（backend allowlist 只接受四类 workspaceKind，"chat" 不下发）。
- 2026-07-27（M1）：壳拆分为 `components/v2/shell/` 五个组件提前在 M1 完成（原排 M3），
  避免 600 行单文件壳；M3 因此只剩 V2Workspace 页面拆分、样式模块化与共享原语收敛。
- 2026-07-27（M1）：状态栏暂不显示本地服务健康与设备状态——V2 壳当前没有健康/设备
  hook，新增数据依赖属于独立改动；M4 评估是否接入既有健康轮询。
- 2026-07-27（M2）：概览"下一步"入口卡直接呈现真实进度（待确认代码产物数、结构
  修订状态、最新版本号），不用静态占位文案；跳转经 `onOpenWorkspace` 单一回调，
  不在页面层复制壳的页签状态。
- 2026-07-27（M2）：页头主按钮由"打开 AI 协作"更名"返回对话"——对话在 Studio
  布局中是默认舞台而非被打开的对象；无测试依赖旧文案。
- 2026-07-27（M3）：跨壳共享原语库（`components/shared/ui/`）不建。V1 与 V2 使用
  不同 class 体系，当前没有真实共用组件；提前抽象只会制造死代码。V2 内部共用件
  （WorkspaceHeader/EngineeringPanel/CodeUploadGuide/ArtifactWorkspace）收敛于
  `v2/pages/common.tsx`；待 V1 迁移或第二调用点出现时再提升。
- 2026-07-27（M4）：共享浮窗/对话框（FloatingWindow、SettingsDialog、
  ProjectCreationDialog）不改组件、只在 `.zw-shell` 作用域做 CSS 覆盖——V1 视觉
  保持原样，符合"V1 壳不动"边界。
- 2026-07-27（M4）：状态栏健康接入既有 `useHealthCheck`（4s 超时、5s 轮询、
  失败分级），不新建数据通道；设备状态仍不进状态栏（设备 hook 属于 DevicesTab
  安全状态机，跨层读取需独立设计）。
- 2026-07-27（M5）：用户截图确认纯图标轨在实际桌面上不可辨认，改为图标 + 常显中文
  短标签；tooltip 只作补充，不能作为唯一识别方式。
- 2026-07-27（M5）：`ProjectStructureContext` 由 Sidecar 根据 `projectId` 生成并计算
  hash，前端仍只提交 prompt/mode/baseProjectVersion/currentRevisionId。上下文不携带
  原始完整对话、Provider 信息、任意路径或设备凭据；显式本轮需求始终优先于历史项目语义。
- 2026-07-28（M6）：默认采用“简洁模式”的任务语言，专业模式作为解释内部版本、来源、
  运行任务和结构修订的按需入口。左侧图标轨是唯一工作区主导航，顶部只保留项目名称、
  当前阶段和“专业视图 / 侧栏”动作；右侧三 Tab 是固定跨页辅助区，不再把同一层信息
  拆成“变更 / 事实 / 产物 / 任务”四个工程概念。
- 2026-07-28（M7）：普通模式的澄清状态由主对话输入框持有；旧多问题 payload 只逐个
  呈现，收齐后一次批量提交，避免破坏后端完整回答约束。推荐捷径优先使用题目中标记的
  推荐选项，否则采用第一个可用选项；自由回答始终可用。专业模式继续显示原始结构化
  问题，作为排障和迁移回退路径。
