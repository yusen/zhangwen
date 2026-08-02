# PLANS.md — 掌问自主开发阶段计划

## ExecPlan：ZW-CREATOR-001 掌问创作端 V3 重建

状态：M0–M7 软件实现与自动验收已完成，M8 外部验收待执行（2026-07-31）。新创作端以
`docs/PRD_CREATOR_V3.md` 为权威产品文档，采用“我的作品 → 双栏作品工作台 → 创意与方案 /
数字原型 / 3D 结构 / 实物运行 → 证据与交付”的完整路径。旧中央主对话、固定右侧三 Tab、
图标轨和全局普通/专业模式不再约束 V3；设备、凭据、Flash 和执行器安全边界继续有效。
详细范围、迁移、契约、里程碑、验收与 Decision Log 见
`tasks/ZW-CREATOR-001-creator-workbench-rebaseline.md`。

### 里程碑

- [x] M0：当前共享工作树恢复检查点、权威文档切换和 Legacy UI 冻结。
- [x] M1：Creator contracts、统一作品投影、生命周期、证据依赖和增量迁移。
- [x] M2：作品首页、双栏工作台、四阶段、抽屉和设备确认壳层。
- [x] M3：创意、目标和完整方案确认，自动物化数字原型与结构草案。
- [x] M4：数字原型、图形调试、参数版本、故障注入和仿真验收。
- [x] M5：3D 结构修订、制造检查和真实 STL/STEP 输出。
- [x] M6：设备包、USB/ESP-Claw、真机校准和统一安全执行。
- [x] M7：证据失效、用户验收、可复现交付、旧项目迁移和三类锚点作品。
- [ ] M8：真人响应式/硬件验收、默认入口切换和旧创作端壳清理。

### 风险边界

- M0 恢复点和逐里程碑提交/标签是恢复依据；不得 reset/clean/stash 或整库暂存。
- 新 UI 位于同一仓库的隔离 Creator 目录，复用平台内核，不复制数据库、设备执行器或凭据存储。
- K10/XIAO 仅作代理验证设备包；创作端不硬编码板型，自研硬件无真实握手前不得伪装已连接。
- 自动测试只使用 Fake Provider、Mock transport 和受控模拟器；真实设备、Flash 和发布保留确认点。

## ExecPlan：ZW-DEVICE-LAB-001 双板项目实物仿真与代码部署

状态：实现完成且真人验收待用户（2026-07-30）。只支持
`seeedstudio/xiao_esp32s3_sense` 与 `dfrobot/dfrobot_k10` 作为主控。项目立项确认后由
已确认硬件、BOM、IO 映射和项目描述自动生成整套实物仿真场景；USB 串口与 ESP-Claw 是
两个同级代码部署通道，ESP-Claw 固件安装只用于初始化/恢复。不创建 `ZW-017`。详细范围、
验收、风险与 Decision Log 见
`tasks/ZW-DEVICE-LAB-001-two-board-device-lab.md`。

### 里程碑

- [x] M0：冻结双板范围、风险边界和 ExecPlan。
- [x] M1：V29 双板 contracts、注册表、兼容迁移和板级档案。
- [x] M2：立项事实到不可变实物场景的自动投影、物化与运行绑定。
- [x] M3：CodeRun 运行时与 USB/ESP-Claw 同级部署后端及安全门禁。
- [x] M4：项目实物仿真画布、双通道部署 UI 和图形调参。
- [x] M5：迁移、自动验证、文档、Decision Log 与 HANDOFF。

### 风险边界

- 第三种主控板失败关闭；外接传感器、执行器和供电器件不受此限制。
- 不连接真实设备，不执行真实上传、复位、Flash、擦除、安装或发布。
- 场景只从已确认项目事实生成；不允许手工板型覆盖或编造 IO 连线。
- ESP-Claw 部署必须使用已配对端点、握手和回读校验，不复用固件安装或 `esptool`。
- 主对话保持挂载；运行时初始化/恢复延续备份、确认、锁、取消、幂等和回读验证边界。

本文件是 ZW-005 至 ZW-016 的阶段索引。每个阶段的详细 ExecPlan 位于 `tasks/ZW-<id>-<slug>.md`。状态取值：待开始、进行中、自动验收通过、实现完成且真人验收待用户、已提交、外部验证待完成、已完成；未运行自动检测时必须在状态中明示。

## ExecPlan：ZW-MAINT-004 共享工作树恢复检查点

状态：已完成（2026-07-29）。长期累积的 tracked/untracked 项目内容已保存为可审计 Git 恢复点，append-only 交接已压缩；完整快照为 `97da7fa092239fb440c91676fcba0d9eb16e29fe`，最终入口为 tag `zw-maint-004-complete`。详细纳入/排除边界、验证证据、Decision Log 与恢复方法见 `tasks/ZW-MAINT-004-recovery-checkpoint.md`。

### 里程碑

- [x] 完成工作树规模、文件类型、体积、敏感候选和运行数据边界审计。
- [x] 用显式路径创建恢复提交，不使用 `git add -A`。
- [x] 压缩 `HANDOFF.md` 与 `CURRENT_TASK.md`，创建收尾提交和 `zw-maint-004-complete` 标签。

### 风险边界

- 不删除或提交本机缓存、用户数据、运行数据库、`references/local/` 和未知本机资料。
- 不猜测拆分已经交织的历史差异；用两个诚实的恢复提交保存当前内容与最终交接状态。
- 不 stash/reset/clean/强推，不调用真实 Provider、串口、上传、复位、Flash、烧录、安装或发布。

## ExecPlan：ZW-V2-001 V1 基线上的 V2 产品与架构升级

状态：M0-M5.2 软件实现与自动验收已完成；旧“电子相册”项目已建立 V1 导入基线，事实可读化与页面上下文对话已接入，修复后桌面/Sidecar 已启动且健康。完整对话 Change Set 化、真人页面体验与 M6 纵向样板、真实运行时和发布验收待办。详细产品范围、架构、CAD 融合、设备接管、Web Local Bridge、迁移和验收要求见 `docs/PRD_V2.md` 与 `tasks/ZW-V2-001-product-architecture-upgrade.md`。

### 里程碑

- [x] 审计 V1 PRD、现有 CAD/设备/Web 边界和用户指定的 `ZW-CAD-intent`。
- [x] 完成 V2 产品、UI、Project Kernel、Capability Engine 和迁移规划。
- [x] M0：共享契约、CAD 来源快照与行为 golden。
- [x] M1：Project Kernel 与 Capability Facade。
- [x] M2：V2 UI Shell。
- [x] M3：CAD Intent Worker；真实 CadQuery 运行时构建留作 M6 外部验收。
- [x] M4：设备运行态接管与模拟器安全回归。
- [x] M5：Web Local Bridge 与能力矩阵。
- [x] M5.1：修复 V1 旧项目进入 V2 时的基线版本与工程事实联动，完成真实旧项目纵向回归。
- [x] M5.2：把已确认事实改为面向用户的中文呈现，并让单一 AI 对话感知 V2 工作区/工程子页上下文。
- [ ] M6：纵向样板与发布验收。

### 风险边界

- `CURRENT_TASK.md` 已切换并记录 M0-M5 的完成证据；V1 外部验收继续保留。
- 当前 CAD 拷贝的 `npm test` 为 0 tests，不能跳过 M0 直接进入生产融合。
- 不调用真实 Provider、串口、上传、硬件 reset、Flash 擦除、固件烧录或公开发布。
- V2 不使用 `ZW-017` 编号，不覆盖共享工作树既有业务差异。

## ExecPlan：ZW-UX-009 V2 对话中心 UI 全面重构（Studio 方向）

状态：M0-M5 全部完成（2026-07-27）；图标轨可读性与受控 ProjectStructureContext 已通过自动回归和真实桌面视觉复核。设计定稿、范围边界、验收门禁与 Decision Log 见 `tasks/ZW-UX-009-v2-studio-ui-overhaul.md`。

用户已确认：视觉 + 架构全面重构；仅 V2 工作台（V1 壳保留回退）；允许调整布局；方向 B（对话即工作台）为基线并融合方向 A 优点（项目/版本滑出面板、工作区页头、概览入口条、模式切换前置）；分阶段稳步推进。原型归档于 `outputs/ui-redesign/`。

### 里程碑

- [x] M0：方向确认、双原型归档、ExecPlan 与交接建立。
- [x] M1：`--zw-*` Token 层与新壳骨架（深色图标轨 / 中央对话舞台 / 右侧上下文检查器 / 状态栏 / 项目滑出面板）。
- [x] M2：概览、工程、结构、交付四工作区页面重构（含概览"下一步"入口条与全页面 token 化）。
- [x] M3：V2Workspace 拆分为 v2/pages 五文件、label 去重、App.css 无 V2 残留确认。
- [x] M4：浮窗/对话框 .zw-shell 作用域统一、检查器折叠与窄屏抽屉、状态栏健康接入、文档契约修订与全量回归。
- [x] M5：图标轨常显中文标签；CAD Intent 只读取当前项目的受控结构上下文，并验证显式输入优先、项目硬件隔离和上下文 hash。

### 风险边界

- V1 `AppShell`/`App.css` 视觉不动，`VITE_ZHANGWEN_V2_UI=0` 回退保持可用。
- 不改共享 contracts、API、SQLite schema；不拆 `DevicesTab.tsx` 内部逻辑（留独立任务）。
- 不调用真实 Provider、串口、上传、复位、Flash、安装或发布；不使用 `git add -A`，不覆盖共享工作树其他差异。

## ExecPlan：ZW-CLOSURE-001 两阶段产品闭环与原始 P0 收口

状态：软件实现与自动验收完成，外部验收待办。详细范围、产品决定、安全边界和验收矩阵见 `tasks/ZW-CLOSURE-001-product-closure.md`。

### 里程碑

- [x] 创建 ExecPlan 并冻结真实/模拟验收边界。
- [x] 云端邮箱身份、本地代理、画像与账号级项目隔离。
- [x] 唯一项目进度、三步创建、简化计划和自动交接。
- [x] 自动浇花 Hardware Skill、结构化代码与设备模拟闭环。
- [x] 项目复制/回收区、质量收口和仓库内完整自动测试。
- [ ] 真实 SMTP/DeepSeek/实体硬件、同提交安装包和干净 Windows 发布验收。

### 风险边界

- 真实 SMTP、DeepSeek、设备和公开部署未提供前不得宣称外部闭环完成。
- 不使用 `git add -A`、stash/reset/clean，不覆盖共享工作树已有差异。
- 日常设备路径只做 MicroPython 文件上传；Flash 擦除和固件烧录不在本任务自动执行范围。

## ExecPlan：ZW-MAINT-003 全项目代码审查与保守重构

状态：已完成（未提交，保留在共享工作树中）。详细发现、选择标准、验证矩阵和 Decision Log 见 `tasks/ZW-MAINT-003-codebase-review-refactor.md` 与 `docs/reports/CODEBASE_REVIEW_2026-07-25.md`。

### 里程碑

- [x] 建立架构、UI 契约、工作树和检查入口基线。
- [x] 运行全栈自动检查并按真实证据排序发现。
- [x] 对高价值、低风险问题先补测试再保守重构。
- [x] 完成全栈验收、审查报告和 durable handoff。

### 风险边界

- 不进行无失败证据的全库改名、依赖升级、格式化或目录重排。
- 不覆盖共享工作树现有差异，不改变公开契约和产品 UI 不变量。
- 设备只做代码审查与 Mock/Dry Run 回归，不调用真实 Provider、串口、上传、复位或 Flash。

## ExecPlan：ZW-MAINT-002 工作树目录整理与参考输入归类

状态：已完成（未提交，保留在共享工作树中）。详细边界、移动清单和验证要求见 `tasks/ZW-MAINT-002-worktree-directory-classification.md`。

### 里程碑

- [x] 审计根目录用途、Git 归属、磁盘占用和有效引用。
- [x] 归类跟踪参考包、本机参考输入和品牌源文件。
- [x] 更新目录地图、忽略规则和有效路径引用。
- [x] 完成只读构建检查、定向回归和交接。

### 风险边界

- 不删除或迁移用户数据、输出、依赖和构建缓存。
- 不暂存、回退或覆盖当前其他任务的大量未提交差异。
- 不调用真实 Provider、设备、串口、上传、复位或 Flash 操作。

## ExecPlan：ZW-PKG-002 GitHub 公开预发布

本计划把已经生成的 Windows x64 `0.1.1` 安装器作为未签名预发布测试版交付。公开仓库固定为
`yusen/zhangwen-desktop`，Git 历史只包含面向用户的 `README.md`；约 394 MB 的安装器不进入 Git，改为
`v0.1.1` GitHub Pre-release 附件。详细门禁和恢复依据见 `tasks/ZW-PKG-002-github-prerelease.md`。

### 里程碑

- [x] 用户明确授权公开仓库、仓库名和未签名 Pre-release 边界。
- [x] 对 `0.1.1` 运行非安装式完整包验证并核对 SHA-256、大小与签名状态。
- [x] 提交只含 `README.md` 的独立发布仓库并推送 `main`。
- [x] 创建 `v0.1.1` Pre-release、上传唯一安装器附件并复核公开下载页。

### 决策与风险

- 不推送当前混合且大量未提交的开发仓库，不复用其 Git 历史，不使用 `git add -A`。
- 安装器未签名，README 和 Release 必须同时提示 SmartScreen；本次只标记 Pre-release，不声称稳定正式版。
- 干净断网 Windows 外部验收仍待完成；真实 Provider、串口、上传、复位、Flash 擦除和固件烧录不在发布流程中执行。

## ExecPlan：ZW-PKG-001 M6 品牌图标与自动版本安装器

本计划把用户提供、现归档于 `assets/branding/logo.png` 的源文件作为掌问统一应用图标，并把根目录入口收敛为无需手工改版本的一键构建。当前
`tauri.conf.json` 的 `0.1.x` 是安装器版本单一事实源；每次默认打包先计算下一个补丁版本，只有构建和非安装式验证
全部成功才保留新版本，失败恢复原配置。`--check`、`--verify-only` 和显式安装 smoke 均不递增。

### 范围与方案

1. 从用户原始方形 PNG 生成 Tauri Windows `.ico` 与标准 PNG 尺寸；同一品牌图标用于原生标题栏/任务栏、EXE/NSIS、
   Web favicon、登录品牌区和桌面顶栏，不改变“掌问 — AI 创客工程工作台”名称与布局契约。
2. 新增可独立测试的 PowerShell 版本函数和版本化构建编排；根 `build-installer.bat` 默认只需双击或直接运行。
3. 从 `0.1.0` 起成功生成序列为 `0.1.1`、`0.1.2`……；失败构建不占号，检查和验证现有包不占号。
4. 自动验收覆盖版本计算/写入/失败边界、图标资源存在、品牌 UI、TypeScript 与生产前端构建；本里程碑不安装、
   不签名、不发布，也不连接 Provider 或真实设备。

### 里程碑

- [x] 固化 M6 验收、版本单一事实源与失败回滚策略。
- [x] 生成并接入桌面、安装器和应用内品牌图标。
- [x] 实现根目录一键自动版本打包与 PowerShell 回归。
- [x] 完成 UI Contract、构建检查、文档和 HANDOFF 收尾。

### 决策与风险

- 版本按“构建并验证成功次数”递增，不按脚本启动或失败尝试次数递增；避免出现无可交付安装包的空版本。
- 直接调用底层 `pnpm package:windows` 仍是固定版本高级入口；日常交付统一使用根脚本，避免双重递增。
- `0.1.1` 已在 2026-07-20 完整生成并通过非安装式包验证；该包未签名，只允许按 ZW-PKG-002 作为预发布测试版交付。

## ExecPlan：ZW-STABILITY-002 本地服务、硬件目录、启动与多 Provider 稳定化

本计划解决频繁“本地服务未连接”、Hardware Skill 重复扫描、完整入口启动缓慢和单 Provider 限制。详细根因、
安全边界、里程碑和验收命令见 `tasks/ZW-STABILITY-002-local-service-catalog-startup-multi-provider.md`。

状态：已完成（M1-M11）。陈旧 Vite、Sidecar 冷启动/有界恢复、服务端恢复门禁、简洁 UI、Provider 凭据保存与对话运行时、OpenAI-compatible usage-only 流式帧和自定义模型目录均已收口。

### 里程碑

- [x] 启动、运行期健康、Hardware Skill 和 Sidecar 生命周期证据固化。
- [x] 持久 Hardware Skill 索引、按选择加载和手动刷新。
- [x] 宿主有界恢复、健康迟滞和启动关键路径优化。
- [x] DeepSeek、千问、GLM、Kimi Provider 配置与调用链。
- [x] 项目文件审计、低风险整理、自动回归和完整入口验收。
- [x] 陈旧开发进程所有权、Sidecar 重启预算与初次失败降级。
- [x] 服务端自动恢复并发门禁与普通模式信息分层修复。
- [x] 简洁 UI/UX 三档验收、工作树审计和新版 NSIS 安装包。
- [x] 开发态 Tauri 千问凭据保存、错误反馈与对话运行时配置链路修复。
- [x] Kimi/GLM 空 choices 流式帧兼容、Kimi 三模型、自定义模型持久化与业务流回归。

### 决策与风险

- 启动慢和运行期误报是不同根因，分别以阶段耗时和连续健康状态验收。
- 目录索引只作可再生展示投影；目标 Hardware Skill 和项目硬件仍完整失败关闭。
- Sidecar 自动恢复必须有窗口、次数上限和退避；不允许无界循环。
- 不删除用户数据、外部参考目录、未提交任务或未知输出，不运行真实付费 Provider 和设备操作。

## ExecPlan：ZW-AGENT-006 M28 立项书浮窗与跳过 Spec 的自动交接

本计划修正问题引导师确认链：立项书查看直接使用既有 Artifact 浮窗，不再创建聊天占位消息；确认立项书只确认 Proposal，
不再自动生成或展示 Spec。项目中已有智能工程师时，桌面切换到该专家并自动开始一轮实现；没有时停在已确认状态且不新增专家。

### 范围与方案

1. 前端拦截 `view_project_proposal`，按稳定 Proposal Artifact/Version ID 打开浮窗并保持单一 `CenterChat`。
2. 后端 `confirm_project_proposal` 删除 Spec Provider 调用，按现有项目成员条件返回可选自动 handoff。
3. 中央确认流不再投影 `VALIDATED` Spec；智能工程师可基于已确认立项书生成 nullable-Spec CodeRun，现有安全门禁保持。
4. 更新 UI/API/架构契约、专家行为包、回归测试和交接记录；不操作真实 Provider、串口、上传或 Flash。

### 验收

- 点击“查看立项书”不发起 `/chat/stream`，打开对应文档浮窗且中央对话不出现右栏提示。
- 确认立项书后数据库不新增 Spec；已有智能工程师时自动切换并发送执行请求，没有时不产生 handoff。
- 前端定向 UI 契约、后端 Proposal/Runtime 回归、类型检查与 production build 通过。

### 决策与风险

- Spec 表、API、Artifact 和显式 Code/Lesson Agent 入口保留兼容，本轮只移除问题引导师前台链和智能工程师硬门禁。
- 自动交接不调用“添加专家”；后端只在现有、未移除的智能工程师存在时下发 handoff。
- 代码无需 Spec 不等于放宽安全：文件白名单、凭据、主机访问、Board API、静态/语法与设备确认继续失败关闭。

## ExecPlan：ZW-AGENT-006 M27 行空板、教案路线与根目录打包入口

本计划完成三项用户定向改进：把行空板 K10 从 Markdown/模板提示提升为机器可读代码生成门禁；让问题引导师在当前
推荐方案上明确提供“生成立项书 / 生成教案版本”两条路线；在仓库根目录提供一键 Windows 安装包脚本。复用现有
Board Skill、Proposal、Spec、LessonRun 和 Windows NSIS 构建链，不新增一级 Tab、教学数据表或设备操作。

### 范围与方案

1. 增加 `unihiker-k10-micropython` 板级契约，覆盖 `unihiker_k10`、`k10_base`、构造实例、常用成员/签名和跨板错误；
   Code Agent、智能工程师草稿与 `STATIC` Worker 根据已选 K10 或 Spec BOM 使用同一契约。
2. 方案卡同时提供工程立项和教案版本。选择作为 confirmed `delivery_track` SharedFact 持久化并投影为
   `ProjectSharedContext.deliveryTrack`；两条路线均先确认表格式实施基线和 Spec，确认 Spec 后只生成对应代码或教案。
3. 根目录 `build-installer.bat` 默认调用既有 `package:windows` 和 `verify:package:windows`；提供只读 `--check`、
   `--verify-only`，以及必须显式传入的隔离安装/桌面 smoke 参数。
4. 自动测试只使用离线 AST、Fake Provider、临时 SQLite、DOM 和脚本语法检查，不调用真实收费模型、串口、上传、复位、
   Flash 擦除、固件烧录，也不在本里程碑重新执行耗时完整打包。

### 里程碑

- [x] K10 多模块 Board API 契约、生成注入和 AST 失败关闭。
- [x] 问题引导师双路线、共享上下文投影和 Spec 后分流。
- [x] 根目录打包脚本与安全检查模式。
- [x] 组合回归、UI Contract、任务记录和 HANDOFF 收尾。

### 决策与风险

- K10 契约只对现有官方资料明确覆盖的对象失败关闭；Camera/MQTT 等资料不完整对象保留开放成员，避免误拒合法固件 API。
- “教案版本”不绕过 Proposal/Spec 确认：实施基线保证硬件、供电和安全事实可审计；确认 Spec 时与代码生成互斥。
- 默认打包不安装、不启动、不签名、不发布；安装 smoke 和桌面 smoke 保留显式参数与既有环境拒绝检查。

## ExecPlan：ZW-AGENT-006 M26 无确认自动恢复

本计划把智能工程师 `LOCAL_OUTPUT_REJECTED` 的失败恢复从“一次自动、再次失败人工确认”改为连续自动恢复。
恢复继续使用消息中已持久化的 `recoveryOfMessageId/recoveryLabel`，不新增数据库状态，不改变其他专家或其他错误分类。

### 范围与方案

1. 根据恢复消息指向前一失败消息的链路计算连续自动恢复次数，组件刷新或项目重载后仍能得到相同结果；
2. 智能工程师连续本地校验失败时自动沿用原需求、原专家和原会话，最多自动恢复三次，全程不显示确认按钮；
3. 达到三次上限后停止自动请求，显示无按钮的中文终态，引导用户在固定输入框补充要求，避免无限请求和费用失控；
4. 结构工程师、问题引导师和非 `LOCAL_OUTPUT_REJECTED` 继续保持现有人工恢复行为；自动测试不调用真实 Provider 或设备。

### 里程碑

- [x] 恢复链深度、三次上限和重载稳定性边界固化。
- [x] 连续自动恢复与无确认终态实现。
- [x] StrictMode、第二次失败和达到上限回归测试。
- [x] UI Contract、任务记录、HANDOFF 与组合测试收尾。

### 决策与风险

- 三次是“原始请求之外最多三个恢复请求”，既覆盖偶发结构化失败，也保持明确费用边界；不得改成无上限循环。
- 只识别带 `已按原需求自动重试` 标签的连续恢复轮次；普通用户消息和其他恢复类型不会被误计入自动链。
- 达到上限后不恢复截图中的“按原需求重试”按钮，用户仍可通过永久输入框补充或重新发送需求。

## ExecPlan：ZW-AGENT-006 M25 立项分层与 Spec 优先代码交付

本计划解决问题引导师的“推荐方案/立项书”内容雷同，以及智能工程师代码验证和接受入口重复的问题。正式立项工程
收敛为“推荐决策 → 表格式立项 → Spec 确认 → 代码生成 → 编辑器内验证并接受”；简单、临时且未进入正式立项的
代码请求仍可由智能工程师直接形成草稿。本计划不新增数据库表、右侧一级 Tab、真实设备操作或自动上传。

### 范围与方案

1. 推荐方案只回答“做什么、为什么这样选、核心逻辑/硬件与关键取舍”，立项书只回答“交付什么、如何实施、何时完成、
   如何验收和控制风险”；立项书通过既有六项领域数据按表格呈现，不复制方案正文。
2. 立项书浮窗和 Markdown/DOCX 导出使用表格结构，保留固定六项数据契约和历史版本兼容。
3. 代码浮窗移除独立“验证”页签，在代码视图底部显示两项检查摘要和单一“验证并接受代码”动作；验证失败只保留
   当前版本供修改，验证通过后原子推进到既有接受接口，不再在中央对话显示第二次“接受代码”。
4. 正式立项书确认后先生成工程 Spec；Spec 仍在中央确认。确认 Spec 后才调用既有 Code Agent 生成基于该 Spec 的代码，
   打开代码产物并由用户完成最终验证接受。简单对话代码不强制建立立项书。
5. 自动测试使用 Fake Provider、本地临时数据库和浏览器 DOM；不调用真实付费 Provider、串口、上传、复位、Flash 擦除
   或固件烧录。

### 里程碑

- [x] 契约、差异边界和验收用例固化。
- [x] 推荐方案/立项表分层与表格预览/导出。
- [x] 编辑器内验证接受和中央确认收敛。
- [x] 立项后 Spec 优先、确认后代码生成流水线。
- [x] 专项测试、UI Contract、任务记录和 HANDOFF 收尾。

### 决策与风险

- 复用 Proposal 的固定六项与 ArtifactVersion，不创建“立项表”第二套真值；表格只是更适合执行核对的呈现协议。
- “正式复杂工程”以存在已确认立项书为确定性边界，避免由 Provider 自报复杂度；没有立项书的简单临时代码保持原路径。
- “验证并接受”仍是两次既有本地状态转换组成的单一用户动作：只有静态/语法真实退出码都为 0 才调用接受接口；
  失败不接受、不上传、不自动修改代码。

## ExecPlan：ZW-AGENT-006 M24 掌控板 3.0 代码生成可靠性

本计划针对掌控板 3.0 MicroPython 代码中常见的旧版 API、虚构成员和错误调用签名，在上传前增加确定性约束。
实现复用现有 Code Agent、Hardware Skill 组件身份、`STATIC | SYNTAX` 两项验证和只读串口终端；不增加模拟执行，
不连接真实串口，不自动修改或重新上传设备代码。

### 范围与方案

1. 增加带板型组件 ID、固件族、官方来源、对象成员、调用签名和已知错误迁移提示的掌控板 3.0 API 契约；
2. 代码生成根据项目已选硬件和已确认 Spec 解析目标板，只向 Provider 注入匹配契约，并明确禁止使用契约外板载 API；
3. `STATIC` 子进程增加板级 AST 语义检查，拦截 `oled.*`、`rgb.show()`、`button_a.pressed()`、未知板载成员和参数数量错误；
4. 用户保存的新版本再次验证时复用原 Spec 与当前项目硬件解析同一契约；无匹配契约的其他开发板保持原验证行为；
5. 自动测试只使用离线代码样例和 Fake Provider，不调用真实付费模型、串口、上传、复位、Flash 擦除或固件烧录。

### 里程碑

- [x] 根因、契约边界和安全范围确认。
- [x] API 契约、生成上下文和静态 Worker 实现。
- [x] 生成、错误 API、签名与非目标板兼容回归。
- [x] 专项测试、文档、任务记录和 HANDOFF 收尾。

### 决策与风险

- API 契约是代码生成/验证专用的只读软件接口事实，不开放为 Hardware Skill 编辑器可写文件，避免用户资料修改静态执行门禁；
- 首版只对契约明确覆盖的板载对象执行失败关闭，普通 Python 名称、第三方驱动和未覆盖模块不凭猜测拒绝；
- 串口 Traceback 继续只读展示。本里程碑不增加 REPL 输入、自动补丁或自动重传；后续若增加重传，仍须用户授权、端口锁、幂等键和次数上限。

## ExecPlan：ZW-AGENT-006 M23 只读串口终端与运行错误可见性

本计划把右侧“设备”中的一次性“串口日志”改为受控只读串口终端。当前上传链只记录备份、写入、回读和复位步骤，
复位后没有持续读取设备输出，因此 `main.py` 的 `SyntaxError`、`NameError` 和普通 `print` 信息均不可见。本里程碑
只增加串口输出观察能力，不发送终端输入、不自动修改代码、不执行 Flash 擦除或固件烧录。

### 范围与方案

1. 扩展设备 Transport 协议，增加只读终端监控；生产适配器使用固定 `mpremote connect <port> repl` argv 和受控
   子进程读取，Mock Transport 提供确定性输出，不接受用户命令或任意 shell。
2. `DeviceOperationService` 为每个设备会话维护有界内存缓冲、状态、revision、取消事件和端口锁。终端与上传/固件
   操作互斥；开始设备操作前停止终端，断开设备时必须停止并释放终端进程。
3. 新增终端启动、停止、清空和快照 API；快照不持久化真实端口、凭据或设备输出到浏览器存储、SQLite 或 Artifact。
4. 右侧“设备”把“串口日志”改为“串口终端（只读）”，展示连接状态、原始多行输出、启动/暂停/清空操作；
   上传步骤仍作为独立部署状态，不再伪装成设备 stdout。
5. 先补后端 Mock 会话、端口互斥、断开清理与前端 SyntaxError/NameError 展示回归，再运行定向测试、contracts 构建、
   desktop strict typecheck 和 UI 契约测试；不连接真实串口或设备。

### 里程碑

- [x] 根因与可观察验收固化。
- [x] 后端终端协议、会话生命周期和 Mock 回归。
- [x] 前端串口终端及错误输出回归。
- [x] 定向测试、类型检查、UI 契约与 HANDOFF 收尾。

### 决策与风险

- 首版终端为只读，避免未审计输入向设备发送中断、复位或任意 REPL 命令；输出仅保存在 Sidecar 有界内存中。
- 终端进程必须与上传、备份、回读、复位和固件操作共用端口锁，不能以并行打开串口换取“实时”假象。
- 自动测试只使用 Mock Transport；真实板卡的启动早期输出捕获仍需用户在桌面设备上人工验收。

## ExecPlan：ZW-AGENT-006 M22 本地服务响应性与开发启动可诊断性

本计划修复 2026-07-18 实际桌面运行中出现的“本地服务未连接”。诊断确认 Sidecar 当时仍监听
`127.0.0.1:8100`，但单 worker 事件循环被同步专家上下文组装占用；一次请求中又对 66 个 Hardware Skill
重复迁移、完整校验和逐组件重建目录索引，健康接口因此超过前端超时并积压轮询。随后桌面启动链退出，开发
启动器按既有 finally 清理 Sidecar/Vite，但没有持久化退出原因。本里程碑只处理响应性、轮询和开发日志，
不改变三师输出、安全门禁、硬件事实优先级或设备操作。

### 范围与方案

1. `ExpertRuntime` 把同步 `ContextAssembler.assemble` 调度到受控工作线程；事件循环在上下文读取期间继续服务
   `/api/health`、取消和其他轻量 API。SQLite 连接仍在执行线程内部创建，不跨线程复用连接。
2. `HardwareSkillRepository` 为上下文提供一次性目录快照：轻量完成缺失旧行迁移，单次完整校验有效包，复用已加载
   detail 生成组件和 Markdown；不再为每个组件调用 `ensure_component_migrated` 或重建全目录索引。常规硬件库 API
   继续执行旧包隔离、K10 升级和完整失败关闭。
3. 健康 Hook 使用 4 秒专用超时、同一时刻最多一个请求，并在卸载时中止请求；5 秒轮询不再叠加 30 秒通用请求。
4. 开发启动器把 Sidecar/Vite 输出、Cargo 退出码、Job 状态和清理原因写入本机 Zhangwen 日志目录；不增加无界自动
   重启，避免正常关窗或持续故障形成重启循环。
5. 先补事件循环心跳、Hardware Skill 单快照和健康轮询去重回归，再运行后端专项、前端专项、严格类型检查和启动脚本
   解析检查；不调用真实付费 Provider、串口或设备。

### 里程碑

- [x] 只读根因复盘和耗时证据固化。
- [x] 先补响应性、目录快照和轮询回归。
- [x] 实现后端线程卸载和 Hardware Skill 扫描收敛。
- [x] 实现健康轮询去重与开发启动日志。
- [x] 专项测试、类型检查、脚本检查和 HANDOFF 收尾。

### 决策与风险

- 工作线程只承载已有同步本地读取/校验，不把云端 Provider、串口或高风险工具移入线程，也不放宽取消、认证和硬件
  revision 门禁。
- 不使用多 Uvicorn worker 掩盖阻塞；掌问的本地状态和后台协调器仍保持单 Sidecar，根因在调用边界与重复 I/O。
- 开发日志不得记录 capability token、API Key、账号会话或真实串口标识；正常关窗不自动重启。

## ExecPlan：ZW-PKG-001 M5 安装态硬件目录与 Sidecar 可诊断性修复

本计划修复 2026-07-18 实际安装验收发现的三个关联问题：安装态硬件库为空、问题引导师因硬件资源缺失返回 `UNKNOWN`、本地服务失败缺少可定位日志。当前工作树混有 ZW-AGENT-006 等并行修改；本计划只触及打包、硬件目录同步、上下文降级、健康指示及相关测试/文档，不清理、暂存或覆盖其他差异。

### 范围与方案

1. 构建时把 `services/local-api/.data/hardware-skills` 作为“经统一 Hardware Skill 校验的生产目录输入”，映射到包内只读 `zhangwen/hardware/bundled-hardware-catalog/hardware-skills`；目标路径不包含 `.data`，构建前逐包校验且继续执行凭据/绝对路径扫描。
2. `HardwareSkillRepository` 在 frozen Sidecar 首次初始化时只复制目标目录中不存在的包，复制前校验源包、拒绝符号链接，使用临时目录加原子 rename，并同步 SQLite 投影；已有同名包无论 revision 是否不同都不覆盖。
3. `ContextAssembler` 只对未选择硬件的公共知识读取增加 `OSError/UnicodeError` 降级；用户已选择硬件的 revision、规则和机械事实仍失败关闭。
4. Tauri 把 Sidecar stdout/stderr 和启动阶段写入 `%LOCALAPPDATA%\Zhangwen\logs`，前端健康初态使用明确“连接中”文本；暂不增加自动重启，避免缺少退出分类时形成静默重启循环。
5. 扩展 Python、Rust/TypeScript 与 PowerShell smoke，要求安装态硬件 API、媒体、问题引导师上下文和资源 manifest 可用。

### 里程碑

- [x] 根因复盘与验收条件固化。
- [x] 先补自动测试与包资源契约。
- [x] 实现目录同步、降级和日志。
- [x] 专项测试、typecheck、UI 契约与 package smoke。
- [x] NSIS 构建、安装器校验、文档和 HANDOFF。

### 决策与风险

- 不把可变 `.data` 目录原样放入安装路径；仅在构建阶段读取已验证包并重定位为只读 bundle，禁止数据库、凭据、临时文件和主机绝对路径进入产物。
- 首次同步只新增缺失包，不覆盖用户同名目录；未来若要自动升级 bundled revision，需要独立的已安装基线 ledger 后再设计。
- 本轮不运行真实 Provider、串口、上传、复位、Flash 擦除或固件烧录；不修改现有用户数据来伪造干净安装验收。

## ExecPlan：ZW-CAD-004 M2 行空板 K10 电子相册固定结构模板

本计划把 `references/local/复杂结构件建模的人机交互资料` 中已经确认的电子相册结构固化为结构工程师生产模板。
现有 `FREEFORM_STRUCTURE` 只支持水平盒体、圆柱和 Z 轴旋转，无法可靠表达 60° 斜面、斜面局部坐标、
L 卡扣、后部槽和多处确定性加/减法圆角，因此本里程碑新增本地拥有尺寸的专用模板，不扩大云端执行权限。

### 范围与方案

1. 新增 `UNIHIKER_K10_PHOTO_ALBUM -> unihiker-k10-photo-album.v1` 跨 Python/TypeScript 契约；模板参数为空，
   禁止 Provider 修改资料中已确认的尺寸、revision、局部坐标或几何程序。
2. 结构工程师识别“行空板 K10 电子相册/相册支架”后直接选择模板；不要求盒体尺寸、机械档案或自由结构描述。
3. 将资料中的全局/局部坐标、16 个确认阶段、加/减法方向和核对项整理为结构工程师参考；复杂结构先输出阶段规格，
   按阶段验证后由本地 Worker 生成最终模型。
4. CAD Engine 使用固定 CadQuery 函数构造单一可打印件，继续复用 STEP/STL/GLB、B-Rep、回读、流形、manifest
   和 Artifact 校验；不执行参考目录中的任何代码或路径。
5. 先补目标路由、边界、能力上下文、Worker 和真实 CadQuery 回归，再运行相关 Python 测试、contracts 构建、
   desktop strict typecheck、UI 契约检查和交接更新。

### 里程碑

- [x] 资料审计、尺寸提取与现有模板能力差距确认。
- [x] 先补模板契约、目标路由和 Worker 失败关闭测试。
- [x] 实现结构工程师参考、模板 intake 和确定性几何。
- [x] 运行真实 CadQuery 与既有模板回归。
- [x] 更新任务、架构/UI 契约和 HANDOFF。

### 决策与风险

- 首版采用固定尺寸，不向 Provider 暴露可改参数；错误的局部尺寸联动比少参数更危险。
- 模板必须保持单一连通实体；任何布尔操作、B-Rep、STEP 回读或 STL 流形校验失败均失败关闭。
- 参考资料中已撤销或失败的方法不进入生产几何；不调用真实 Provider、设备、串口、上传或固件操作。

## 阶段状态

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-005 | 本地硬件库与硬件规则引擎 | 已完成 | `tasks/ZW-005-hardware-library-rule-engine.md` | `23926cc` | `zw-005-complete` |
| ZW-006 | 立项书生成、版本与确认 | 已完成 | `tasks/ZW-006-proposal-workflow.md` | `3caf4c8` | `zw-006-complete` |
| ZW-007 | Orchestrator 与 Agent Registry | 已完成 | `tasks/ZW-007-orchestrator-agent-registry.md` | `20d6b4b` | `zw-007-complete` |
| ZW-008 | Skill Registry 与模型路由 | 已完成 | `tasks/ZW-008-skill-registry-model-router.md` | `58da5fd` | `zw-008-complete` |
| ZW-009 | 产物系统与浮窗系统 | 已完成 | `tasks/ZW-009-artifact-window-system.md` | `1901b20` | `zw-009-complete` |
| ZW-010 | Spec Agent | 已完成 | `tasks/ZW-010-spec-agent.md` | `7a31c5a` | `zw-010-complete` |
| ZW-011 | Code Agent | 已完成 | `tasks/ZW-011-code-agent.md` | `f56881d` | `zw-011-complete` |
| ZW-012 | 设备管理与 MicroPython 部署 | 外部验证待完成 | `tasks/ZW-012-device-micropython-deployment.md` | `9315c6a` | `zw-012-software-complete` |
| ZW-013 | CAD Agent | 已完成 | `tasks/ZW-013-cad-agent.md` | `6bf5ef3` | `zw-013-complete` |
| ZW-014 | Lesson Agent | 已完成 | `tasks/ZW-014-lesson-agent.md` | `04d6d5d` | `zw-014-complete` |
| ZW-015 | 分享与项目包 | 已完成 | `tasks/ZW-015-sharing-project-package.md` | `d2f52f0` | `zw-015-complete` |
| ZW-016 | MVP 全流程集成与加固 | 已完成 | `tasks/ZW-016-mvp-integration-hardening.md` | `zw-016-complete` 标签所指提交 | `zw-016-complete` |

## 用户定向 UX 跟进

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-UX-004 | 批量澄清与工作台简化 | 已完成 | `tasks/ZW-UX-004-simplified-workbench-batch-clarification.md` | `zw-ux-004-complete` 标签所指提交 | `zw-ux-004-complete` |
| ZW-UX-005 | 显式项目推荐、按项目增补工程师与共享知识库 | 实现完成且真人验收待用户 | `tasks/ZW-UX-005-explicit-project-routing-shared-knowledge.md` | 未提交 | — |
| ZW-UX-006 | 原型视觉系统渐进迁移 | 实现完成且自动验收通过（M1-M15；真人桌面串口验收待用户） | `tasks/ZW-UX-006-prototype-visual-system.md` | 未提交 | — |
| ZW-UX-007 | 项目硬件前置选择与器件项目浮窗 | 实现完成且自动与三档 UI 验收通过（M1-M6；真人验收待用户） | `tasks/ZW-UX-007-hardware-intake-component-workspace.md` | 未提交 | — |
| ZW-UX-008A | 三师结构化交接最小闭环 | 已暂停（由 ZW-STABILIZE-001 取代） | `tasks/ZW-UX-008A-structured-expert-handoff.md` | — | — |
| ZW-UX-009 | V2 对话中心 UI 全面重构（Studio 方向） | 实现完成且自动验收通过（M0-M4；真人桌面体验验收待用户） | `tasks/ZW-UX-009-v2-studio-ui-overhaul.md` | 未提交 | — |

## 用户定向 LLM 跟进

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-LLM-001 | 生产业务强制真实 LLM | 已完成 | `tasks/ZW-LLM-001-required-real-llm-generation.md` | `zw-llm-001-complete` 标签所指提交 | `zw-llm-001-complete` |
| ZW-LLM-002 | 三师结构化输出与 microSD 代码可靠性 | M4 实现完成且自动验收通过；重启后真人重试待用户 | `tasks/ZW-LLM-002-expert-structured-output-reliability.md` | 未提交 | — |
| ZW-LLM-003 | 结构工程师输出可靠性与本地校验分层 | 实现完成且自动验收通过；重启后真人桌面抽检待用户 | `tasks/ZW-LLM-003-structure-output-resilience.md` | 未提交 | — |
| ZW-LLM-004 | 生成失败诊断与对话恢复 | 实现完成且自动验收通过（真人桌面抽检待用户） | `tasks/ZW-LLM-004-generation-failure-recovery.md` | 未提交 | — |
| ZW-UX-008 | 分析后项目硬件选择与缺件补充 | 实现完成且自动与三档 UI 验收通过（真人桌面抽检待用户） | `tasks/ZW-UX-008-analysis-first-project-hardware.md` | 未提交 | — |

## 用户定向账号与访问控制

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-AUTH-001 | 本机账号注册、登录与平台门禁 | 实现完成且自动与三档 UI 验收通过（真人桌面抽检待用户） | `tasks/ZW-AUTH-001-local-account-access-gate.md` | 未提交 | — |

## 用户定向维护

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-MAINT-001 | 项目目录清理与重复实现整合 | 已完成 | `tasks/ZW-MAINT-001-project-cleanup-consolidation.md` | `zw-maint-001-complete` 标签所指提交 | `zw-maint-001-complete` |
| ZW-STABILIZE-001 | 掌问当前代码基线重整 | 已完成 | `tasks/ZW-STABILIZE-001-current-baseline-realignment.md` | `zw-stabilize-001-complete` 标签所指提交 | `zw-stabilize-001-complete` |
| ZW-WEB-001 | Web 优先开发模式切换与核心流程稳定化 | 已完成 | `tasks/ZW-WEB-001-web-first-development-mode.md` | `zw-web-001-complete` 标签所指提交 | `zw-web-001-complete` |

## 用户定向 Agent 配置

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-AGENT-001 | 三师 Agent Skill 包配置 | 已提交 | `tasks/ZW-AGENT-001-agent-skill-packages.md` | ZW-AGENT-001 至 005 工程节点提交 | - |
| ZW-AGENT-002 | 智能工程师 MicroPython 开发板与代码闭环 | 已提交 | `tasks/ZW-AGENT-002-micropython-board-code-loop.md` | ZW-AGENT-001 至 005 工程节点提交 | - |
| ZW-AGENT-003 | 工程代码工作台与设备部署闭环 | 已提交 | `tasks/ZW-AGENT-003-engineering-code-device-flow.md` | ZW-AGENT-001 至 005 工程节点提交 | - |
| ZW-AGENT-004 | MicroPython 部署可靠性与设备交互优化 | 已提交 | `tasks/ZW-AGENT-004-device-upload-reliability-ui.md` | ZW-AGENT-001 至 005 工程节点提交 | - |
| ZW-AGENT-005 | K10 Skill 驱动代码与项目开场闭环 | 已提交 | `tasks/ZW-AGENT-005-k10-skill-code-kickoff.md` | ZW-AGENT-001 至 005 工程节点提交 | - |
| ZW-AGENT-006 | 代码编辑器与中央确认流优化 | 进行中（M24 掌控板 3.0 生成可靠性自动验收通过；真机代码抽检待用户） | `tasks/ZW-AGENT-006-code-editor-confirmation-flow.md` | - | - |

## 用户定向 Hardware Skill

| 阶段 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-HW-001 | Hardware Skill 单一事实源、创建工作流与 Skill 项目编辑器 | 已完成（未提交） | `tasks/ZW-HW-001-hardware-skill-library.md` | 未提交 | — |
| ZW-HW-002 | 硬件库图片、可复制模板与默认目录收敛 | 已完成（未提交） | `tasks/ZW-HW-002-hardware-catalog-media-template.md` | 未提交 | — |
| ZW-HW-003 | 电气、结构与参考模型统一 Hardware Skill | 实现完成且自动验收通过（真人桌面抽检待用户） | `tasks/ZW-HW-003-unified-hardware-skill.md` | 未提交 | — |
| ZW-HW-004 | 外设电源轨与工作电压范围校验 | 实现完成且自动验收通过；运行库 revision 故障已修复（待重启真人抽检） | `tasks/ZW-HW-004-peripheral-power-rail-validation.md` | 未提交 | — |

## 用户定向交付

| 任务 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-PKG-001 | Windows 离线 NSIS 安装包 | 自动验收通过，外部安装验收待完成 | `tasks/ZW-PKG-001-windows-offline-installer.md` | 未提交（与当前并行工作树一起保留） | — |

## 用户定向 CAD 改造

| 任务 | 名称 | 状态 | 任务文件 | 提交 | 标签 |
|---|---|---|---|---|---|
| ZW-CAD-001 | 结构工程师真实 CAD 闭环 | 实现完成并已创建本地版本，真人验收待用户（本轮未运行自动检测） | `tasks/ZW-CAD-001-structure-engineer-real-cad.md` | 本次 CAD 收口提交 | 未打标签 |
| ZW-CAD-002 | 基于电子器件的结构创建 | 已完成 | `tasks/ZW-CAD-002-component-derived-structure.md` | 未提交 | CAD 178 tests + pnpm typecheck |
| ZW-CAD-003 | 机械档案三维预览 | 已完成 | `tasks/ZW-CAD-003-mechanical-profile-preview.md` | 未提交 | API/桌面专项、类型检查通过 |
| ZW-CAD-004 | 自然语言声明式几何与 K10 相册固定模板 | M2 已完成 | `tasks/ZW-CAD-004-natural-language-geometry.md` | 未提交 | CAD 200、Agent Skill 13、UI 17、strict typecheck 通过 |
| ZW-CAD-005 | mechanical.md 自然描述生成预览 | 实现完成且自动验收通过（真人桌面抽检待用户） | `tasks/ZW-CAD-005-mechanical-description-preview.md` | 未提交 | — |

`ZW-CAD-001` 已包含 confirmed intake 指纹、旧非活动候选封存、create/retry/finalize/confirm
修订门禁和 UI 冲突刷新；本地版本不推送、不打标签，也未运行自动检测，用户真人验收返回前
M6 保持未完成。

## 执行规则

## ExecPlan：ZW-AGENT-006 M29 智能工程师代码生成 Hardware Skill 强绑定

只读审计和本机最近运行证据表明，智能工程师已经接收项目 Hardware Skill，但已选 K10 的约 13k Markdown 在多候选上下文中被截到约 3.2k，且 M20 的提示性 grounding 允许 `codeDraft` 忽略本地 Skill 后直接保存。本计划保持普通方案对不完整机械事实的非阻断语义，只收紧实际代码交付。

### 范围与方案

1. 先补回归：已选 Skill 的后段集成说明必须进入智能工程师 Provider 上下文；忽略本地 Skill 的 `codeDraft` 必须修复重试；普通无代码硬件建议继续单轮完成。
2. 调整 ContextAssembler 的 Markdown 预算：项目已选 Hardware Skill 使用优先预算，本地 ACTIVE 候选使用紧凑预算，仍保持总量有界和 revision/ACTIVE 完整校验。
3. Runtime 对问题引导师、结构工程师继续执行原 grounding；智能工程师仅在输出 `codeDraft` 时执行 grounding，本地 Board API、文件、凭据和静态/语法门禁保持不变。
4. 更新智能工程师 Skill 规则、架构/交接文档并运行专家、Hardware Skill、代码草稿与类型相关回归；不调用真实 Provider 或设备。

### 里程碑

- [x] 固化 Provider 上下文与代码结果失败边界测试。
- [x] 实现已选 Skill 优先预算与 `codeDraft` grounding。
- [x] 运行专家/Hardware Skill/代码生成相关回归和 Python 编译检查。
- [x] 更新任务、架构、专家规则与 HANDOFF。

### 风险

- 不要求代码引用纯机械器件或未使用外设的 API；grounding 只要求代码交付明确引用并评估当前可信硬件集合，具体板载 API 仍由机器契约验证。
- 不把 Markdown 指令当执行权限；Hardware Skill 只能提供生成上下文，不能授予文件、Shell、串口、上传、Flash 或凭据能力。

## ExecPlan：ZW-AGENT-006 M30 K10 参考代码检索与生成遵循门禁

K10 代码目前只做到了“上下文中存在 Skill”和“API 名称可被机器契约接受”，没有证明代码实际按当前需求选中的参考模板生成。现场案例甚至把 AI 预览帧和屏幕提示描述为拍照成功。本计划把参考模板从提示性资料提升为可审计、可修复的本地生成契约。

### 范围与方案

1. 为 K10 Board Skill 增加多参考检索、模板生成契约和未验证能力说明；保持包 SHA-256、manifest 和只读边界不变。
2. 把所选模板及契约作为独立系统消息紧邻 Board API 契约发送，明确代码以模板为骨架增量适配。
3. 在智能工程师 `codeDraft` 保存前解析生成代码 AST，校验模板关键导入、初始化和调用锚点；校验消息携带具体模板路径和缺失锚点，驱动既有一次结构化修复。
4. 对本地资料未证实的静态拍照/照片保存能力阻止虚假成功声明，允许诚实交付已验证的摄像头预览子集。
5. 补 Board Skill 选择、Runtime 自动修复和既有 K10/掌控板回归；不修改串口、上传、固件或真实设备。

### 里程碑

- [x] 固化多参考检索、模板独立上下文和偏离模板失败测试。
- [x] 实现 K10 模板生成契约、AST 遵循校验和能力缺口校验。
- [x] 运行 Board Skill、专家 Runtime、Board API、聊天代码与 MicroPython 回归。
- [x] 更新架构、Agent 规则、任务和 HANDOFF。

### 风险

- 模板门禁只约束板级参考骨架，不要求逐行复制，也不阻止业务逻辑、状态机和界面增量；普通 Python 逻辑不做相似度误判。
- 未验证能力说明不能被解释为真实设备失败；它只表示当前本地 Skill 和官方资料没有足够依据，仍需补充受信参考或真机探测后才能扩展。

## ExecPlan：ZW-AGENT-004 M5 运行中程序安全接管与无硬件复位上传

本计划解决设备上的 `main.py` 持续运行时，普通管理命令无法进入 REPL、上传在预检阶段失败的问题。上传器在现有端口锁和终端互斥边界内，先用有界 Ctrl-C 接管解释器，再执行备份、写入、回读和 Python 运行环境重启；全过程不触发硬件 RST/EN、断电、Flash 擦除或固件烧录。

### 范围与方案

1. 为后端与共享契约增加 `INTERRUPT_RUNTIME`、`START_RUNTIME` 以及独立验证字段；保留 `RESTART/restartOk` 读取兼容。
2. `SubprocessDeviceTransport` 使用固定 argv 启动 REPL、只写入 Ctrl-C 并有界等待提示符；取消、超时和失败均确保子进程被清理。
3. 身份探测和文件操作增加 `mpremote resume`，避免独立进程的默认自动软复位；部署后执行固定的 `soft-reset exec --no-follow "import main"`，不调用硬件 `reset`。
4. 中断失败发生在任何设备写入前；启动失败沿用备份恢复，保持“上传并运行”的原子语义。
5. 设备 UI 显示“安全停止程序、文件部署、启动 Python 程序、终端观察”结果；测试只使用 Mock/Fake transport。

### 里程碑

- [x] 先补后端安全顺序、失败关闭、固定 argv 与前端呈现测试。
- [x] 实现传输层中断/启动原语和上传状态机。
- [x] 更新共享契约、设备界面与兼容读取。
- [x] 运行后端专项、前端专项、contracts build、desktop typecheck 和安全回归。
- [x] 更新 API/架构/UI 契约、任务记录与 HANDOFF。

### 决策与风险

- Ctrl-C 无法抢占原生阻塞或中断被禁用的程序；平台此时明确停止，不得静默执行硬件复位。
- MicroPython soft reset 会清空解释器堆和模块状态，但不切断硬件供电，也不等同于 ESP32/主控硬件 reset；界面必须使用准确术语。
- 新流程不删除旧枚举与字段，避免历史操作记录因反序列化失败而丢失。

## ExecPlan：ZW-UX-009 M6 普通模式信息减法与术语收敛

当前 V2 Studio 同时显示左侧图标轨与顶部五页签，并在普通模式暴露 Change Set、CAD
Intent、Worker、Job、Artifact、Project Version、Release 与原始状态码。用户需要先理解
实现架构才能操作，偏离“描述想法 → 确认方案 → 制作并验证”的产品主线。

### 范围与方案

1. 先更新 UI 契约与回归测试：左侧图标轨成为唯一工作区主导航；右侧一级 Tab 固定为
   “工作 / 产物 / 设备”；`CenterChat` 与已访问的设备工作区在切页、折叠侧栏时不卸载。
2. 普通模式只显示任务语言和当前可执行动作；版本、hash、操作路径、原始 Job/CAD 状态、
   Provider 及本地工具名仅在专业模式显示。
3. “工作”合并当前上下文、待确认修改、已确认信息与正在处理事项；“设备”懒加载既有
   `DevicesTab`，不提前扫描且不改变任何连接、上传、复位或 Flash 安全门禁。
4. 概览、工程、结构、交付页面收敛标题和说明；结构普通模式隐藏修订历史侧栏，交付普通
   模式隐藏投影 hash 与 Release 工程详情。
5. 运行 V2 壳专项、UI 契约、strict TypeScript 与生产构建，并进行真实桌面视觉复核；
   不连接真实设备，不调用上传、复位、Flash 或真实 Provider。

### 里程碑

- [ ] 固化三 Tab、单一导航和普通模式术语边界测试。
- [ ] 实现壳、右栏与状态栏信息减法。
- [ ] 实现四工作区简化文案及结构/交付专业分层。
- [ ] 完成自动回归、视觉复核和交接记录。

### 风险

- 设备工作区只能在用户主动点击“设备”后首次挂载；此后折叠或切换页签只隐藏，避免丢失
  连接摘要和操作上下文。
- 文案收敛不改变共享 contracts、REST、SQLite 或设备安全状态机；专业模式仍保留排障所需
  的精确工程信息。

## ExecPlan：ZW-UX-009 M7 对话流体化与主动推进

M6 已减少工程名词，但普通模式仍把澄清问题固定成问卷卡，并要求用户理解题号、完整度和
批量提交。M7 把普通模式改成“对话即平台”：掌问替用户完成可逆、低风险的细节决定，只在
方向不明确或真实设备动作前中断。

### 范围与方案

1. 先固化 DOM 与协议兼容测试：普通模式不出现“需求澄清、完整度、第几题、上一题、
   下一题、提交回答”；历史多问题消息仍在前端逐个收集并以既有
   `clarification_batch_answer` 一次提交。
2. 澄清问题作为普通掌问消息显示；主输入框直接回答当前问题，另保留“按掌问建议继续”
   和“我自己说”两个捷径。新问题生产最多一个真正阻塞的问题。
3. 三师与 CAD Intent 统一采用主动推进策略：可逆低风险项使用推荐默认值，非阻塞缺口
   留为验证项，只把改变产品方向的最高影响问题交给用户。
4. 普通模式只保留“对话 / 项目 / 连接 / 设置”，右栏默认收起；概览、工程、结构、交付
   及完整诊断只在专业模式出现。`CenterChat` 始终单一挂载。
5. 普通结果卡只呈现标题、两行摘要和一个主要动作；生成过程只显示一个当前状态，自动
   恢复过程不逐次打扰，达到上限后才解释。
6. 运行前端全量、后端澄清流、三师 Runtime、CAD、设备安全、strict TypeScript 与生产
   构建；桌面宽屏和窄屏只做无设备、无真实 Provider 的视觉复核。

### 里程碑

- [x] 固化普通模式自然对话、旧批量协议和安全边界测试。
- [x] 实现主输入框回答、推荐捷径和历史多问题逐个收集。
- [x] 实现三师/CAD 单阻塞问题与主动推进策略。
- [x] 收敛普通模式导航、状态和结果卡，保留专业模式完整信息。
- [x] 完成全量回归、桌面体验复核和交接记录。

完成状态（2026-07-28）：M7 已实现。desktop 全量、Sidecar 全量、strict TypeScript 和
production build 通过；真实掌问桌面以 1282×831 与 744×831 复核，窄屏发现的检查器
`hidden` 样式覆盖已修复并补测试。未执行真实 Provider、设备、上传、复位或 Flash。

### 风险

- 历史问题不能逐题发送到后端；SQLite 的完整回答门禁仍要求同一来源消息一次提交全部必填
  答案，因此前端只改变呈现方式，不改变最终批量协议。
- 串口扫描、连接、代码上传、Python 运行环境重启、设备复位、Flash 擦除和固件烧录不属于
  可逆低风险默认值，继续经过既有明确确认门禁。
- 普通模式隐藏信息只影响呈现，不删除 contracts、数据库字段、专业诊断或 V1 回退路径。

## ExecPlan：ZW-AUTH-002 云认证未配置时的本机账号恢复

当前开发桌面只显示邮箱登录，但本机没有配置 `ZHANGWEN_CLOUD_AUTH_BASE_URL`；旧
`auth_kind=local` 账号和其项目仍在本机认证库中。密码不可逆，因此恢复必须保留账号 ID 和
项目归属，只替换密码派生值。

### 里程碑

- [x] 扩展认证状态，明确区分云认证可用与本机账号存在。
- [x] 云认证未配置时恢复本机账号登录；云认证已配置时保持邮箱流程。
- [x] 增加交互式本机密码重置工具：精确账号、确认短语、隐藏输入、数据库备份和旧会话撤销。
- [x] 完成前后端认证、strict TypeScript、production build 与真实桌面登录页复核。

### 风险

- 不新增匿名 HTTP 密码重置端点；本机维护工具直接使用认证仓储并要求 OS 文件访问权限。
- 密码不得成为命令行参数、聊天内容、日志或输出；工具只报告账号和备份路径。
- 不删除认证库、不改变项目 owner、不使用 `ZHANGWEN_AUTH_DISABLED`，云账号和设备门禁不变。

- 每个阶段必须更新对应任务文件、`HANDOFF.md` 和本文件。
- 每个阶段必须有自动测试、独立提交和阶段标签。
- ZW-006、ZW-009、ZW-012、ZW-015、ZW-016 为全量回归节点。
- 真实设备、真实 API Key、固件烧录和公开发布属于外部验证或高风险确认项，不得伪造成功。
- 完成 ZW-016 后生成最终报告并停止，不得创建、规划或实现 ZW-017。
