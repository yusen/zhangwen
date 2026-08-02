# ZW-CAD-001 - 结构工程师真实 CAD 闭环

状态：实现完成并已创建本地版本，真人验收待用户（本轮新增修复未运行自动检测）

## 1. 目标

将 `references/local/ZW-CAD-intent` 中已经验证的确定性外壳、安装结构、开孔、基础装配和真实
CadQuery 导出能力迁入“掌问”，由结构工程师通过严格 `cadDraft` 驱动本地
Tool Runner 和受限 CAD Worker，最终生成可确认、可预览、可下载的 STEP、STL、
GLB 与校验报告。

中央区域继续保持唯一主对话；CAD 进度位于右侧“工作”，模型从右侧“产物”打开
`MODEL_3D` 浮窗，最终确认或退回只出现在中央“待你确认”卡。

## 2. 范围

- shared contracts、Pydantic 边界和 SQLite schema v24。
- 结构工程师专属 `cadDraft`，并固化来源消息、专家、Spec、模板和机械档案版本。
- 持久 `CadJob`、单并发本地 Worker、取消、重试和 Sidecar 重启恢复。
- 固定模板 CadQuery 建模，不执行 LLM 或用户提供的 Python。
- 真实 STEP/STL/GLB、参数、机械档案快照、manifest 和校验报告。
- 二进制 ArtifactVersion 文件存储和带 capability 的流式读取。
- React/Three.js `MODEL_3D` 浮窗、CAD 状态、中央确认流和响应式 UI 验收。
- 将 `references/local/ZW-CAD-intent` 测试行为重写为掌问 Python/TypeScript semantic golden。

## 3. 非目标

- 本任务不构建、验证或发布 Windows 离线安装包，不执行 `pnpm package:windows`。
- 不迁入 `references/local/ZW-CAD-intent` 的 Node HTTP 服务、独立 SPA、模型源 API 或部署脚本。
- 不保留 `cadquery_code`、`runpy`、自定义硬件 Python 或任意代码执行入口。
- 不实现自由曲面、CAE、CNC、切片、任意用户插件或通用约束求解器。
- 不覆盖、暂存或提交并行的 `ZW-PKG-001`、`ZW-AGENT-006` 代码编辑器/本地检查主体、
  任务文件和用户自有 `tasks/ZW-UX-003-three-expert-system.md` 修改。CAD 在中央发起与
  最终确认所必需的共享确认卡接线随本任务收口，不代表 `ZW-AGENT-006` 整项完成。
- 不创建、规划或实现 `ZW-017`。

## 4. 架构决策

| 编号 | 决策 | 选择 | 理由 |
|---|---|---|---|
| C-01 | 原型处置 | 只读行为与几何 oracle，按掌问边界重写 | 避免平行 Agent、HTTP 服务和 UI 壳 |
| C-02 | LLM 输出 | 仅 `cadDraft` 声明式参数 | 云端 LLM 不接触文件、Shell 或 CAD 代码 |
| C-03 | Worker | 固定入口、单 Job、仅内置模板和受信模型 | 保留确定性并关闭任意代码执行面 |
| C-04 | 文件 | SQLite 元数据 + ArtifactVersion 不可变二进制目录 | STEP/STL/GLB 不进入 SQLite 文本列 |
| C-05 | 机械档案 | 版本化快照和显式硬件 ID 映射 | 不按名称猜测尺寸或安装点 |
| C-06 | UI | 工作区显示进度，产物浮窗显示 3D，中央确认 | 遵守固定三 Tab 与中央主对话契约 |
| C-07 | 并发 | 全局和单项目均为 1，队列上限 8 | 控制 OCP 内存峰值并简化取消恢复 |

## 5. 数据与状态

- Schema v24 新增 `cad_jobs`、`artifact_files`、`hardware_mechanical_links`。
- 重建 `cad_runs/cad_files`，保留旧 ZW-013 文本行并标记
  `engine_id=template-dry-run`；新行不保存二进制内容。
- `CadRun`：`DRAFT -> QUEUED -> RUNNING -> READY_FOR_REVIEW -> APPROVED/REJECTED`，
  失败支路为 `FAILED/CANCELED`。
- `CadJob`：`QUEUED/RUNNING/CANCEL_REQUESTED/CANCELED/SUCCEEDED/FAILED/
  TIMED_OUT/INTERRUPTED`。
- `CadDraft.intakeSnapshotSha256` 由服务端对当前 confirmed CAD fact ID/值生成，随
  `CadBuildSpec` 固化；不增加 schema 列，也不允许 Provider 提供。
- 新 Job 成功前不让旧 APPROVED 版本失效；确认新版本后再传播 stale。

## 6. 实施里程碑

- [x] M1：contracts、Pydantic、schema v24、机械档案和迁移测试。
- [x] M2：CadJob、Worker 协议、进程限制、取消/恢复和安全测试。
- [x] M3：盒体/盖板/安装柱/开孔、受信硬件模型、STEP/STL/GLB 与几何校验。
- [x] M4：二进制 Artifact、结构工程师 `cadDraft`、ToolRunner 和 HTTP API。
- [x] M5：Three.js 浮窗、任务状态、中央确认和 UI contract 回归。
- [ ] M6：“结构工程师不生成”、intake 修订快照门禁、回归测试代码与文档/HANDOFF 已完成；本轮未运行测试、构建、Browser、Computer Use、Tauri 或自动 UI 检测，`390x844`、`720x720`、`1280x720` 和实际 CAD 工作流真人验收待用户。

## 7. 验收条件

- 结构工程师自然语言回复可以产生严格 `cadDraft`；其他专家返回该字段会失败。
- 未知机械档案、假定尺寸、越界参数和代码/路径字段不能进入 Worker。
- 修订后旧草稿不能创建 Job、旧失败 Job 不能重试、旧 READY 版本不能确认；失配稳定返回
  HTTP 409 `CAD_INTAKE_REVISED`。运行中旧 Job 不隐式取消，但其发布必须丢弃并转 `STALE`。
- 泛“支架/安装座/结构件/打印件”文本不得被当前 `BOX_WITH_LID` 模板静默生成成盒体。
- 空盒、K10、前侧双开孔和混合装配 semantic golden 通过。
- STEP 可回读；打印件 STL 为有限、封闭、manifold 网格；GLB 能在浮窗非空渲染。
- 取消后 5 秒内无残留 Worker；Sidecar 重启将遗留 RUNNING 标记 INTERRUPTED。
- SQLite 不含新模型二进制/base64；下载路由不接受调用方路径且要求桌面 capability。
- `390x844`、`720x720`、`1280x720` 下中央对话单实例、三 Tab 不变、无重叠。
- 本任务不运行离线安装包构建，也不声称完成离线安装验收。

## 8. 安全与资源上限

- Worker 禁止 `eval/exec/runpy`、动态 import、Shell、URL、凭据和调用方路径。
- 墙钟 180 秒、日志 64 KiB、单文件 128 MiB、单 Job 输出 256 MiB、Worker 进程
  1 GiB、最多 12 文件。
- Worker 环境只保留系统运行目录、TEMP/TMP、数据根和显式协议字段；移除 API Key、
  capability token、代理变量和用户 PATH。
- staging 与发布目录必须拒绝符号链接、junction/reparse point，并检查 resolve containment。

## 9. Progress

- 2026-07-13：按用户授权收口为独立本地 Git 版本；不推送、不打标签。提交边界只包含
  `ZW-CAD-001` 的 contracts、Sidecar、结构工程师 CAD runtime、Worker/Artifact、桌面
  CAD/3D 交互、回归测试代码及同步文档，排除 `CURRENT_TASK.md`、`ZW-PKG-001`、
  `ZW-AGENT-006` 的代码编辑器/两项检查主体与任务文件、`ZW-UX-003`、安装包/Sidecar
  打包资源和 `ZW-CAD-intent` 原型目录；仅保留 CAD 必需的共享中央确认接线。
  遵照用户要求，本次收口不运行测试、构建、Browser、Computer Use、Tauri 或自动 UI 检测；
  下一步仅由用户执行真人工作流验收。
- 2026-07-13：完成“修订后旧 CAD 快照隔离”。当前 confirmed intake 的 fact ID/值被固化为
  服务端 `intakeSnapshotSha256`，create/retry/finalize/confirm 全部复核；失配统一 HTTP 409
  `CAD_INTAKE_REVISED`。重开 intake 同事务封存旧的 `DRAFT/VALIDATED/READY_FOR_REVIEW/
  FAILED/CANCELED/REJECTED` 及聊天/Artifact 投影，保留 `QUEUED/RUNNING/APPROVED`；旧活动
  Worker 结果完成后丢弃并使 Run 过期。UI 冲突后刷新并引导最新草稿。移除会把支架/安装座/
  结构件/打印件误生成盒体的泛词门禁，并让 CAD 上下文中的裸三轴尺寸也可重开 intake。已补
  回归测试代码；遵照用户要求未执行测试、构建或 UI 检测。
- 2026-07-13：按已批准方案完成“结构工程师停在澄清、不生成”的端到端修复。结构工程师
  在 `SOLUTION_DRAFT`、`SOLUTION_CONFIRMED`、`PROPOSAL_DRAFT` 阶段的 CAD 请求优先进入
  `ExpertRuntime`，不再被通用方案路由截走；当前文本、来源 `cad_*` 澄清卡或最近结构线程
  CAD 语境可延续 CAD 意图。澄清答案、问题 answered 状态和 CAD SharedFact 现在使用同一
  SQLite 事务，非法尺寸整体回滚且可重新提交；重复 `clientTurnId` 复用原子结果，不会重放
  旧 facts。完整 intake 下 Provider 即使只返回纯文本，本地仍规范化
  `BOX_WITH_LID cadDraft`。明确“修改/改成/重做”或新尺寸会重开 intake，避免永久复用旧
  mode/dimensions/profile。机械档案只展示每个 profile 当前 revision，项目显式选择优先进入
  32 项上下文；修订会封存旧 DRAFT 和旧 pending CAD 卡。项目实际专家身份覆盖请求类型，
  非 CAD 轮次中的 Provider CAD payload 失败关闭。前端修复历史源线程提交、提交后输入锁死、失败回滚、档案说明和 CAD 卡样式。
  已补后端与前端回归测试代码，但遵照用户要求未执行任何测试、构建或 UI 检测。
- 2026-07-13：真人验收发现“直接进入结构工程师、只靠聊天描述 ESP32”不会生成
  `cadDraft`。实时只读诊断确认该项目 `structuredPayload=null`、`cad_runs=0`、
  `cad_jobs=0`、`mechanicalProfiles=[]`，不是 Worker 或 UI 隐藏故障。按用户批准恢复实现：
  复用中央整组澄清卡区分“纯储物/松散放置”和“器件固定安装”；前者允许
  `components=[]` 直接形成 `BOX_WITH_LID` 草稿，后者只接受用户显式确认的机械档案；
  缺项时必须返回结构化澄清，不再把纯文本追问当成可继续生成的成功终点。本轮实现后由
  用户真人测试，不启动 Browser、Computer Use、Tauri，也不运行自动测试或构建。
- 2026-07-13：用户接管真人测试。从本记录起停止 Browser、Computer Use、Tauri、自动 UI
  检测、测试与构建；后续按用户批准完成上述无生成修复并同步 API/UI/架构/PRD/任务/基线/
  决策/HANDOFF。历史自动验证只作为修复前基线，不覆盖本轮代码；M6 在用户完成三视口和
  实际工作流验收前不标记完成。
- 2026-07-13：M6 XIAO 真实纵向 golden 完成并修复通用服务开孔/限位结构冲突。
  `edge_retainer` 自动锚墙为邻墙限位件预留机械间隙与最小壁厚；仅在同一硬件、同一侧墙
  且开孔投影与限位件实际相交时，将对应端挡/侧限位裁到开孔下缘，同时保留 `0.05 mm`
  几何融合、横向最小壁厚和托台/双侧限位/双端挡五件完整性。开孔过低无法留下有效挡高
  时继续失败关闭。真实 `xiao_esp32s3:confirmed-v1` 已贯通 TRUSTED SHA 快照、自动
  `80x50x28 mm`、USB-C LEFT/`center_z=2.4`、真实 subprocess Worker、11 文件、
  `base.step` 单 Solid、STL watertight/volume 和非空 GLB。全部 CAD 后端专项
  `135 passed`。
- 2026-07-13：M6 专业模式机械档案产品面完成。设置页“公共知识”新增第三个内部
  Tab“机械档案”，仅在专业模式点击后懒加载；普通模式不挂载、不请求机械档案 API。
  UI 展示尺寸、安装策略/面、间隙、证据、revision 和 SHA-256 摘要，并支持显式硬件
  选择、精确 `profileId + revision` 关联、解除和服务端刷新；锁定 K10 映射不可解除或
  重映射。目标前端回归 `16 passed`，desktop typecheck 与 diff-check 通过。
- 2026-07-13：XIAO 真实纵向 golden 在实现前先证明了生产布局缺陷：受信
  `xiao_esp32s3` 使用自动尺寸和 `edge_retainer` 时，左侧 USB 服务开孔与左端挡重叠，
  且自动跨面锚墙距离未计入端挡特征厚度，导致 `mount_clearance` 与
  `opening_mount_clearance` 同时失败，Worker 无法发布 11 文件。修复必须落在通用布局/
  几何规则，不允许按 profile ID 特判，也不允许跳过碰撞校验。
- 2026-07-13：M6 canonical hash 测试基线恢复。`test_cad_sizing.py` 的动态机械档案
  fixture 在计算 SHA-256 前复用生产 `normalize_profile_snapshot_payload`，未放松快照校验；
  默认 `strategy=none` 与 `center_z=0` 保持 schema 1.0 兼容，非默认字段仍参与哈希。
  尺寸与机械档案兼容专项 `10 passed`。
- 2026-07-13：进入 M6 最终产品化收尾。只读基线审计确认开发态
  `cadDraft -> CadJob -> 真实 CadQuery Worker -> 11 个 Artifact 文件 -> GLB 下载 ->
  中央确认` 已贯通；当前 CAD 全套收集 132 项，其中 130 项通过，2 项仅因测试快照未复用
  schema 1.0 canonical hash 默认字段兼容规则而失败。先恢复该测试基线，再完成专业模式机械
  档案产品面、XIAO 真实纵向 golden、三视口桌面验收和文档交接。本轮继续禁止执行
  `pnpm package:windows`，不修改或混入 `ZW-PKG-001`、`ZW-AGENT-006`、`ZW-UX-003`。
- 2026-07-13：受信 `edge_retainer` 可制造安装结构完成。机械档案可声明严格安装策略，
  base-floor 器件确定性生成托台、两侧限位和两端挡；固定件只从不可变 profile 推导，
  不向 LLM 开放几何代码或任意结构参数。新增 mounting completeness、mount 与非目标
  硬件、opening 与 lid post/standoff/mount、keepout 与内壁冲突检查；跨面 opening 支持
  受限 `center_z`。真实 CadQuery base 为单 Solid，STEP 回读及 STL manifold 通过，
  layout/semantic golden 合并 `45 passed`。
- 2026-07-13：M6A 布局、输出和参数基线硬化完成。自动侧墙不再因 Pydantic
  `Point2` 位置参数崩溃；四侧墙 Z、第二轴容量、跨面 opening 墙面投影与显式接口距离、
  矩形孔 90/270 度换轴均有回归。Envelope 0/90/180/270 已用真实 CadQuery BRep
  AABB 对照布局结果。GLB 写入 `NORMAL`，新增 `base.step/lid.step`，Viewer 爆炸距离
  按米制模型比例计算且只抬 lid。`BOX_WITH_LID` 参数由单一目录提供，`screw_posts`
  仅接受 0/4；缺失的宽/高/深由本地根据固化机械档案确定性求解，Job 保存
  `sizingEvidence`，空盒自动内腔下限为 `80x50x28 mm`。合并专项 `53 passed`。
- 2026-07-13：进入 M6A 生产硬化。基于 `ZW-CAD-intent` 行为 oracle 和当前实际
  工作树，先修复自动侧墙布局、跨面开孔、旋转 envelope、真实 GLB 爆炸比例等已确认
  缺陷，并为第二轴容量、四侧墙自动布局、0/90/180/270 实体包围盒补回归测试；随后
  继续收敛参数目录、确定性尺寸、受信安装结构、独立打印件 STEP 和机械档案产品面。
  本轮继续禁止执行 `pnpm package:windows`，不修改或混入 `ZW-PKG-001`、
  `ZW-AGENT-006`、`ZW-UX-003`。
- 2026-07-13：M2-M4 后端收敛完成。旧 `/cad/generate` 仅保留无副作用 410 迁移
  边界，CAD Router 不再声明 Provider/凭据工厂；真实 LLM smoke 移除旧 CAD Provider
  分支。MVP 验收已改为 `CadDraft -> /cad/jobs -> CadJobCoordinator -> 真实 CadQuery
  Worker -> ArtifactVersion -> /cad/confirm`。新增 Coordinator 成功发布、运行中取消、
  重启 `INTERRUPTED` 恢复和 finalize 失败清理测试；Worker 取消等待固定 5 秒，真实
  CadQuery 证明 1 GiB 是当前可运行的进程上限候选。CAD/结构工程师/MVP/项目包合并
  专项 `114 passed`。
- 2026-07-13：M2 机械档案身份子里程碑完成。`CadBuildSpec` 将结构工程师草稿组件
  提升为服务端固化组件，记录 `resolvedProfileId/revision/SHA-256`；仓储只接受已确认
  `hardwareId -> profileId` 映射，Worker 不再把硬件 ID 当机械档案 ID，并校验 resolved
  三元组与不可变快照一致。新增普通超声波双 ID 贯通和错 SHA 拒绝测试。验证：CAD
  Worker/contracts/runtime 合并专项 `16 passed`；contracts build/typecheck 与 desktop
  typecheck 通过。
- 2026-07-13：恢复 M2-M6 正式收敛。当前优先修复结构工程师真实 `cadDraft` 中
  `hardwareId/profileId` 与 Worker 档案查找语义冲突：LLM 字段只表达已确认 BOM 映射，
  Sidecar 必须在入队时固化唯一机械档案快照，Worker 只能按服务端解析后的档案 ID 使用
  快照。随后重跑 CAD 后端/前端基线，补 Coordinator 与真实跨层验收；继续禁止运行
  `pnpm package:windows`，不修改离线安装交付物。
- 2026-07-13：进入 M2-M6 收敛验收。当前工作树已具备 `cadDraft -> CadJob ->
  Worker -> ArtifactVersion -> Three.js` 主体，但审计确认旧 `/cad/generate` 仍可绕过
  Job/Worker，Worker manifest 尚未与当前 Job 的 design/spec 摘要显式绑定。先关闭这两条
  可信路径缺口并补自动测试，再完成项目包 v2、端到端/UI 验收和文档交接；继续禁止运行
  `pnpm package:windows`，也不修改离线安装交付物。
- 2026-07-13：M1 完成。contracts 已增加类型化机械档案、安装面、Worker/Job 输出；
  `CadBuildSpec.profileSnapshots` 复用带 canonical SHA-256 校验的唯一 Pydantic 快照模型；
  v24 保持原 DDL 形状并改为单事务迁移、失败回滚和 `foreign_key_check`。K10 唯一
  alias 与超声波精确 profile 已固化。验证：contracts build 通过，schema/contracts/
  mechanical profiles 合并专项共 `12 passed`。
- 2026-07-13：按用户持续目标恢复正式实现，当前进入 M1 基线审计与契约收敛。
  先运行现有 CAD 专项测试确认真实失败面，再依次接通机械档案、Worker/Job/Artifact、
  结构工程师与桌面闭环；本任务继续明确禁止运行 `pnpm package:windows`。
- 2026-07-13：完成仓库、原型、宿主、UI、安全和打包边界分析；用户批准开始实施，
  明确本轮不进行离线安装包打包。
- 2026-07-13：从现有未提交实验实现恢复开发。静态审计确认当前仅具备 schema v24、
  CadJob/Artifact store、盒体/K10 内核和部分测试草稿；Worker 与 client 协议不一致，
  尚无 Job coordinator、结构工程师 `cadDraft` 生产接入或 Three.js viewer，不能视为
  已完成里程碑。
- 2026-07-13：开始按 contracts/schema、Job/Worker/Artifact、结构工程师、桌面 viewer
  四个边界并行收敛；继续保护 `ZW-PKG-001`、`ZW-AGENT-006` 和 `ZW-UX-003` 修改。
- 2026-07-13：用户确认按既定结论完成正式改造。恢复时重新核对实际工作树，确认
  Worker 协议常量/stdio/cwd 尚未统一，Job API 与 coordinator/finalizer 未接通，
  机械档案上下文仍为硬编码草案，Three.js 浮窗缺少稳定布局和回归测试。本轮继续
  完成端到端闭环，明确不运行 `pnpm package:windows`，也不修改离线安装包交付物。

## 10. Decision Log

- 2026-07-13：结构工程师 CAD 路由优先于 solution/proposal 通用会话分支；普通结构咨询
  仍走 ExpertRuntime 常规回复，只有明确 CAD 文本、来源 `cad_*` 问题或最近 CAD 语境加
  继续/修订表达才进入强制 intake。
- 2026-07-13：澄清回答持久化与 CAD SharedFact 固化必须同事务；失败不能留下“问题已回答、
  CAD facts 缺失”的不可恢复状态。重复 turn 只复用原子结果，不能重放旧 facts 覆盖新修订。
- 2026-07-13：CAD intake 允许通过明确修订表达开启新一轮，不能把首版项目级 mode、尺寸和
  档案当成永久输入；每个 profile 只暴露一个当前 revision，最多选择 32 个。
- 2026-07-13：CAD 草稿和 Job 必须保存包含 confirmed fact ID/值的服务端 intake SHA-256；
  create/retry/finalize/confirm 失配统一失败为 `CAD_INTAKE_REVISED`。相同数值的新一轮仍是
  新授权，幂等键不得复活旧 Job；活动 Worker 不隐式取消，但旧发布必须丢弃。
- 2026-07-13：当前确定性模板仅支持盒/壳/容器语境。泛支架、安装座、结构件和打印件不进入
  `BOX_WITH_LID` intake；未来支持时必须增加独立模板/不支持分支，不能静默生成盒体。
- 2026-07-13：真实 Windows CadQuery Worker 在 256 MiB 和 512 MiB 进程上限下均因
  OpenBLAS 内存分配失败，无法完成盒体建模；将进程内存上限修正为实测可运行的 1 GiB，
  同时保持单 Job 输出总量 256 MiB、单文件 128 MiB 和 GLB 20 MiB 上限。
- 2026-07-13：使用 `ZW-CAD-001` 用户定向任务，不占用或延伸 `ZW-017`。
- 2026-07-13：原型仅作 oracle；自然语言继续由掌问结构工程师处理。
- 2026-07-13：开发态真实 CadQuery 是本任务验收项，NSIS/PyInstaller 离线包不是。
- 2026-07-13：Worker 不直接读取项目 SQLite 或完整数据目录；Sidecar 从持久化 Job
  读取不可变 `CadBuildSpec`，通过 stdin 单 JSON 传入，Worker 仅在受控 staging cwd
  写相对路径输出，并通过版本化 NDJSON 报告事件。
- 2026-07-13：补齐 CAD Skill 的运行时权限映射，`cad.build` 必须同时声明
  `RUN_CAD` 与 `WRITE_ARTIFACT`；`/cad/confirm` 和 `/cad/reject` 与执行、取消、重试一样
  需要桌面 capability；Job 入队拒绝非结构工程师来源、非确定性引擎和未知模板 revision。
- 2026-07-13：产物 Tab 在 Web 模式禁用 `MODEL_3D` 浮窗入口，文档和代码等非 3D 产物仍可
  正常查看；新增 Web/桌面双态回归测试。未执行离线安装包打包。

## 11. Validation

以下结果均早于本轮“结构工程师不生成”修复，只作为历史基线；本轮新增代码和测试未执行
任何测试、构建、Browser、Computer Use、Tauri 或自动 UI 检测，不能据此声明当前修复已
自动通过。不同专项存在测试重叠，数量不能相加：

- `$cadTests = @(Get-ChildItem services/local-api/tests/test_cad_*.py) + @(Get-ChildItem services/local-api/tests/test_structure_engineer_cad_*.py); .\.venv\Scripts\python.exe -m pytest @cadTests -q --rootdir services/local-api`：CAD 后端专项 `135 passed, 1 warning`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_cad_engine_layout.py services/local-api/tests/test_cad_engine_semantic_golden.py -q --rootdir services/local-api`：布局与 semantic golden `47 passed`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_cad_engine_worker.py -q --rootdir services/local-api`：Worker `14 passed`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_structure_engineer_cad_end_to_end.py -q --rootdir services/local-api`：结构工程师真实 E2E `1 passed`。以上三个关键范围合计 `62 passed`，不是一次合并命令。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_cad_engine_exports.py services/local-api/tests/test_cad_mechanical_profiles.py services/local-api/tests/test_cad_sizing.py -q --rootdir services/local-api`：导出/机械档案/尺寸 `12 passed`；其中机械档案/尺寸 canonical 的独立记录为 `10 passed`。
- `pnpm --filter @zhangwen/desktop exec vitest run src/__tests__/MechanicalProfileLibrary.test.tsx src/__tests__/BoardProfileLibrary.test.tsx src/__tests__/CadConfirmationAndWorkTab.test.tsx src/__tests__/Model3DViewer.test.tsx`：`4` 个文件、`16 passed`。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test`：`128 passed / 2 failed`。两项失败来自并行
  `services/api.ts` Sidecar 断连文案已变化，而 `ProjectKickoff.test.tsx`、
  `ProjectWorkspace.test.tsx` 仍断言旧文案；与 CAD 改造无关，本任务不得修改这两个测试
  或混入 `ZW-AGENT-006`。

待用户真人验收：

- 在已确认方案或立项书阶段切换到结构工程师，直接请求“生成保护壳”，确认仍先出现 CAD
  整组澄清而不是通用方案卡；完成松散存放和尺寸后应出现可“开始建模”的 CAD 草稿。
- 固定安装完成首轮后选择服务端机械档案；切换过其他专家再提交历史结构澄清卡，回复仍回到
  源结构线程，输入框在完成后恢复。输入非法尺寸时卡片可修正并重新提交。
- CAD 草稿形成后输入“改成 120 × 80 × 40 mm”，应开启新一轮确认，不得继续使用旧尺寸。
- 新 intake 后点击旧草稿“开始建模”、旧失败 Job“重试”或旧 READY 版本“确认 CAD”，均应
  刷新并提示使用最新草稿；运行中的旧 Job 不被自动取消，但结束后不得重新出现可确认旧版本。
- `390x844`、`720x720`、`1280x720` 下专业模式机械档案第三内部 Tab、普通模式无机械
  档案请求、中央对话单实例、右侧三 Tab、CAD 进度、MODEL_3D 浮窗、11 文件和中央
  确认/退回流程。
- 使用真人判断布局、文字、交互、模型可视效果和实际结构结果；不得用既有自动回归替代或
  预先声明通过。

残余风险：K10 在 UI、DELETE 和 CAD 解析中已锁定，但直接调用机械档案 PUT API 仍可写入
重映射；该值不会改变当前 CAD 的固定 K10 解析，但服务端 guard 尚未实现。本轮按用户指令
只记录问题，不修改代码。
