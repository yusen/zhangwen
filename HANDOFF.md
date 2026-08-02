# 掌问开发交接

## 当前状态

- 当前任务：`ZW-CREATOR-001` 掌问创作端 V3 重建。
- 状态：M0–M7 与 M8.1–M8.5 软件重基线及对话/仿真版本收口已完成；M8.6 真人/真机/安装包验收和
  M8.7 发布收口待执行（2026-08-02）。
- 产品权威：`docs/PRD_CREATOR_V3.md`。
- 实施计划：`tasks/ZW-CREATOR-001-creator-workbench-rebaseline.md`。
- 分支：`codex/zw-005-016-autonomous`。
- M0 恢复提交：`2519d1a`（`chore: checkpoint Creator V3 implementation baseline`）。
- M0 恢复标签：`zw-creator-001-m0-recovery`。
- M1：`f1e4467` / `zw-creator-001-m1-complete`。
- M2：`c209303` / `zw-creator-001-m2-complete`。
- M3：`60cbacb` / `zw-creator-001-m3-complete`。
- M4：`dc5658f` / `zw-creator-001-m4-complete`。
- M5：`af28dbe` / `zw-creator-001-m5-complete`。
- M6：`64ca33d` / `zw-creator-001-m6-complete`。
- M7：`cf44f14`（`feat: complete Creator delivery and reproduction`）/
  `zw-creator-001-m7-complete`；标签在本交接收尾提交后指向最终状态。
- 未推送、未发布，也未运行真实 Provider、串口、ESP-Claw、Flash 或设备动作。
- 已生成仅供人工上传的 `GitHub_Upload_Zhangwen/` 源码快照；该目录被 `.gitignore` 排除，未初始化
  Git、未提交、未推送或公开发布。快照含 1,132 个文件（约 21.88 MiB），与源工作区逐文件 SHA-256
  比对一致；扫描未发现高置信度凭据字面量，唯一 `.env.example` 为占位配置模板。

## 本轮已完成

### M0 恢复点与权威切换

- 审计并显式固化 134 个文件中的累积 Device Lab、ESP-Claw、双板代理、V2 修复和 Creator 文档；
- 高风险凭据字面量扫描为 0，未跟踪文件中无数据库、日志、固件、密钥或设备私有数据；
- `docs/PRD.md`、`docs/PRD_V2.md`、`docs/UI_CONTRACT.md` 和 `ZW-UX-009` 已标记为
  Legacy Creator UI，只保留教学、迁移与安全参考；
- 新增仅开发态显式启用的 `VITE_ZHANGWEN_CREATOR_UI=1` 开关，旧壳仍可回退且不会双壳写状态；
- `pnpm build:contracts` 与 `pnpm typecheck` 通过；Device Lab/ESP-Claw/XIAO 定向测试
  `70 passed`（1 个依赖弃用 warning）。

### M1 契约、投影与迁移

- 新增 `packages/contracts/src/creator.ts`，统一四阶段、生命周期、0–6 等级、修订、证据、
  命令、唯一下一步、设备包和 SSE 事件契约；
- 新增严格 `extra="forbid"` 的 Creator Pydantic 边界和按命令负载模型；
- 数据库升级 V30，新增作品状态、Goal/Solution 修订、AcceptanceScenario、Evidence、幂等命令
  与事件表；旧项目首次读取只建立 LEGACY 适配，不修改原始对话和产物；
- 新增 `/api/creator/works`、workspace、commands、events 和 device-packages 聚合 API；
- 实现单调版本冲突、幂等重放、幂等键复用拒绝、证据前置、失效传播和自动降级；
- 部署成功只记录 DEPLOYMENT，等级 5 只由 PHYSICAL_BEHAVIOR 当前有效证据产生；
- `pnpm build:contracts`、`pnpm typecheck` 通过；Creator/项目仓储测试 `25 passed`。

### M2 作品首页与 Creator 壳层

- 新增隔离的 `apps/desktop/src/creator/` 创作端：首页接入真实作品列表、新建、打开、复制、归档与恢复；
- 建立左侧持续对话、右侧四阶段的双栏工作台，顶部由 Creator 聚合投影展示作品状态、验证等级和唯一下一步；
- 四个重型阶段按需加载；通用抽屉、设置、加载和错误状态已接入；Creator 保留工作台级“三师专业模式”，
  普通模式呈现统一掌问，专业模式展开三师路由、模型和工程细节；
- 阶段切换保持同一个 `CenterChat` 实例，草稿不丢失；390/720/1280 层级测试通过；
- 开发构建默认进入 Creator，可用 `VITE_ZHANGWEN_CREATOR_UI=0` 回退；测试与生产在 M8 前继续保留旧壳；
- `pnpm typecheck` 通过；桌面前端全量测试 `39 files / 249 tests passed`。

### M3 创意与方案纵向闭环

- 修复结构化澄清语义：完整度低于 80 且模型漏给问题时，服务端补成一个方向性文本问题；每轮仍最多一个问题；
- Creator 投影可读取旧聊天流的最新方案草稿，不要求用户在两个系统重复生成方案；
- 创意阶段新增目标与完整工程方案的保存/确认表单，覆盖 BOM、IO、供电、结构、仿真、安全和双端验收场景；
- “选择并添加电子器件”打开真实本地硬件选择器并保存项目，不再发送伪聊天消息；
- 确认方案进入 `DIGITAL_BUILDING`，并记录代码、数字原型、必要结构草案的排队事件，不把排队当成成功证据；
- `pnpm typecheck` 通过；M1/M3 后端 `9 passed`（2 个环境 warning）；桌面全量 `39 files / 251 tests passed`。

### M4 数字原型与仿真

- Creator 已确认方案可直接物化既有 `DeviceLabSceneV1`，不创建重复旧立项书；仍要求项目显式选择代理设备包，绝不默认猜板；
- 数字原型阶段嵌入 Wokwi Elements/Device Lab，接入图形输入、执行器解锁、遥测事件、参数版本比较/回滚、安全停止和故障注入；
- 静态证据校验真实场景修订及当前方案；仿真通过证据校验真实 SIMULATOR 会话已停止并覆盖全部必需场景；
- Caller 自写成功文本或运行中的会话均不能推进等级；只有真实记录使作品到等级 3；
- `pnpm typecheck` 通过；Creator M4/Device Lab `23 passed`；桌面全量 `40 files / 252 tests passed`。仅功能模型/Mock，无真实 QEMU 或硬件动作。

### M5 3D 结构

- Creator 结构阶段复用 CAD Intent 与 Artifact：结构描述、不可变修订、确认/撤销、真实构建、GLB 预览及 STL/STEP 下载均沿已有安全边界；
- Creator 路径关闭 CSS 装饰模型；没有真实 GLB 时只显示文字状态，不提供“模拟导出”；
- 无结构需求显示“不适用”且不阻塞；有结构需求展示方案约束和修订历史；
- `RECORD_STRUCTURE_CHECK` 只接受当前方案绑定的已确认 CAD 修订，并要求真实 Artifact 清单含 GLB、STL、STEP、manifest；
- contracts/类型检查通过；Creator M1/M5 `7 passed`；桌面全量 `40 files / 252 tests passed`。未执行真实 CAD Worker。

### M6 设备包与实物运行

- Creator 实物阶段接入服务端设备包目录及既有安全 `DevicesTab`，USB 串口和 ESP-Claw 在同一
  “代码上传”动作中保持同级，未复制第二套设备执行器；
- 仿真等级 3 是真实操作软门禁；设备连接证据必须绑定就绪串口会话或已配对端点，并与当前方案
  自动生成场景的设备包一致；
- 部署证据必须绑定完成、非 dry-run、文件回读及运行时验证通过的 `UPLOAD_CODE`。部署后仍是等级 4；
- 新增不可变实物验收会话，绑定方案、部署、设备、操作者、急停与全部必需场景，只有通过后达到等级 5；
- 没有 `zwdbg/1` 握手时，真机原始传感器不显示伪值且执行器控制失败关闭；参数版本与显式同步沿用
  现有暂存、原子提交、回读和恢复能力；
- `pnpm build:contracts`、Python 编译、`pnpm typecheck` 通过；Creator/Device Lab/ESP-Claw
  `65 passed`；桌面全量 `40 files / 252 tests passed`。全部设备测试使用 Mock/Fake。

### M7 证据、交付与受控复现

- 等级 5 后增加明确人类验收；系统/AI 身份不能代签，只有当前真机行为证据和用户接受共同形成等级 6；
- 场景、代码、参数、结构修订进入证据绑定，关系真值变化会把相应下游证据标为 `STALE`、记录原因
  并自动降低等级，不删除历史；
- 新增 `creator_deliveries`、`creator_delivery_imports`、`creator_reproductions` V30 repair 表与严格契约；
- 新增分享、可复现、模板三种 `creator-delivery/v1` 包，复用既有安全项目包，增加 manifest、成员
  Hash、整体 SHA-256、脱敏证据、隐私报告、复现指南和三类能力成熟度声明；
- 导入复检路径、成员、大小、Hash 和隐私，创建新项目并把验证重置到等级 1；不同于原验收者的
  第二用户在副本独立达到等级 6 后，才能向原作品提交 Hash 绑定的复现回执；
- 作品首页增加受控导入，实物阶段增加最终验收、三种包下载和复现回执 UI；
- Python 编译缓存不再使 K10 Board Skill 失效：只忽略 `__pycache__` 内 `.pyc`，其余包边界不放宽；
- 交付契约已固化为 `docs/CREATOR_DELIVERY.md`。M7 专项后端 `5 passed`、Board Skill `20 passed`、
  前端全量 `40 files / 253 tests passed`、Local API 全量 `852 passed`；contracts、strict TypeScript
  与生产 Vite build 全部通过。仅有既有依赖弃用和受限 `.pytest_cache` 写入 warning。

### M8.1–M8.5 Creator 主路径重基线

- 澄清问题不再使用固定通用兜底；回答提交后澄清卡立即退出，服务端按已持久化答案决定恢复还是只重试整理。
- 问题引导师采用产品经理式连续访谈：回答后直接提出当前项目的下一个具体产品决策，禁止
  “是否继续、怎么继续、是否还要补充”类元问题；旧“继续补充需求”动作在 Creator 中隐藏。
- 对话、目标草稿、方案草稿和 Creator 投影采用稳定来源绑定；方案是唯一需要用户确认的工程事实。
- 立项书改为创意方案中的可选文档投影：用户确认方案后可单独生成；方案变化后旧立项书标记为过期，
  不影响数字原型、代码和后续部署。
- 方案确认后自动准备 USB MicroPython 与 ESP-Claw 对应代码变体，失败进入带原因的可恢复状态。
- 数字原型采用代码、器件连线画布、UART/事件终端和单一调试抽屉的工作区；传感器输入、执行器控制、
  参数版本不再同时挤在底部。
- 场景从当前方案 BOM、IO、供电、验收场景和代码绑定生成。画布可见呈现传感器到主控、主控到驱动、
  驱动到负载、独立供电和共地连线；未确认连接使用虚线，不伪装成已验证电气事实。
- 传感器测试只显示当前项目验收场景实际引用的输入通道；自动浇花因此显示土壤湿度及其干燥启动、
  湿润停止、超时停机和断线归零，不展示无关板载温度滑块。
- 只有方案明确要求本地、本机、局域网、内网或离线 MQTT Broker 时才加入本地 MQTT 服务节点；
  仅写“MQTT”时要求确认 Broker 归属，云端 MQTT 不自动添加本地服务。场景生成不会启动真实监听端口。
- 实物运行保持 USB 串口与 ESP-Claw 同级上传通道，终端、身份、代码变体、回读、安全停止及专业输入
  继续复用同一部署状态机。

### 新产品基线

- 新增 `docs/PRD_CREATOR_V3.md`，把用户确认的 HTML 交互原型固化为正式产品需求。
- 新创作端顶层改为“我的作品”和“一个打开的作品”。
- 作品工作台采用左侧持续对话、右侧四阶段工作区：创意与方案、数字原型、3D 结构、实物运行。
- 顶部固定呈现作品状态、0–6 验证等级和唯一建议下一步。
- 四阶段始终可查看，真实部署、执行器解锁和验收等动作按证据受控。
- 方案确认后自动生成数字原型；功能仿真通过后才允许真实部署。
- 3D 结构作为可见阶段，但无结构需求的作品不被阻塞。
- 代码、方案详情、图形调试、参数版本和证据使用按需抽屉；Creator 保留三师专业模式作为信息分层，
  两种模式共享同一作品状态。
- 统一设备确认通道展示动作、目标、风险和恢复，并使用真实任务进度。

### 新 ExecPlan

- 新增 `tasks/ZW-CREATOR-001-creator-workbench-rebaseline.md`，包含 M0–M8、契约、API 方向、
  迁移、测试、风险、恢复、Surprises 和 Decision Log。
- 任务编号使用 `ZW-CREATOR-001`，不创建历史流程禁止的 `ZW-017`。
- 建议在同一仓库的 `apps/desktop/src/creator/` 建立隔离新前端，并增加聚合 Creator service；
  不复制项目库、SQLite、设备执行器或凭据存储。
- K10/XIAO 只作为首批代理验证设备包，Creator UI 和生命周期不写死板型。
- 自研 `ZW-Core-01` 在真实设备包和握手实现前只能作为设计/模拟设备，不能伪装已连接。

### 权威与任务切换

- `AGENTS.md` 已切换到 Creator V3 产品不变量；旧 `UI_CONTRACT.md`、`PRD_V2.md` 和旧壳只作
  教学/迁移/回退参考。
- `PLANS.md` 已增加 `ZW-CREATOR-001` 索引、里程碑和风险边界。
- `CURRENT_TASK.md` 已切换到新任务，并写明实施前必须先建立恢复检查点。
- `ZW-DEVICE-LAB-001` 不再是当前任务，但其 Device Lab、双部署通道、参数版本和安全门禁作为
  Creator 的可复用平台能力保留。

## 保留的既有能力

- 项目、账号、版本和本地持久化；
- LLM 设置、流式聊天、结构化澄清与三师内部责任域；
- Hardware Skill、器件目录、规则引擎、BOM、IO 和供电检查；
- Artifact、代码版本、Monaco、CAD Intent 和结构生成；
- Device Lab、Wokwi Elements、参数版本、模拟器和遥测；
- USB 与 ESP-Claw 同级代码部署；
- 串口锁、确认、备份、回读、取消、幂等、失败恢复和隐私扫描；
- 现有 V2 “选择并添加电子器件”真实本地选择器修复。

这些能力必须通过新的 Creator 聚合投影和命令接入，不能复制第二套实现。

## 未完成

- 尚未完成 M8.6 的真实登录态 390/720/1280 响应式与键盘真人走查、真实 K10/XIAO 硬件确认点、
  安装包冷启动/升级/卸载/数据保留验收；
- 尚未完成 M8.7 发布收口；旧 V1/V2 壳只能在 Creator、教学端和历史项目迁移验收通过后清理。

## 本轮改动文件

M8.1–M8.5 与本轮设备实验室修正：

- `services/local-api/zhangwen/device_lab/models.py`、`scene.py` 与共享 contracts：新增项目测试场景、
  服务节点、方案驱动连线拓扑及显式本地 MQTT 判定；
- `apps/desktop/src/components/device-lab/DeviceLabWorkspace.tsx` 与 `device-lab.css`：Wokwi 式连线画布、
  项目特定传感器输入和单一调试抽屉；
- `services/local-api/zhangwen/creator/models.py`、`repository.py` 与 `IdeaSolutionStage.tsx`：
  新增可选 `GENERATE_PROJECT_BOOK` 命令及 CURRENT/STALE 文档投影；
- `services/local-api/zhangwen/chat/idea_flow.py`：问题引导师信息齐全后自动生成并投影方案，不在对话
  中确认方案或询问是否生成立项书；删除硬编码“接下来怎么继续/继续补充需求”分支；
- `services/local-api/zhangwen/clarification/service.py`、prompts 与问题引导师 Skill：增加产品经理式
  连续追问规则，并在 Pydantic 边界拒绝元问题；
- `services/local-api/zhangwen/device_lab/scene.py`、`service.py` 与 `DigitalPrototypeStage.tsx`：
  当前 Creator Solution/CodeRun 显式绑定到场景、仿真启动和证据，修复历史 Proposal 抢占；
- `CreatorApp.tsx`、三师 prompts 与问题引导师 Skill：服务端阶段变化自动导航，移除同阶段泛化
  “继续”和重复确认；
- `CreatorApp.test.tsx`、`DeviceLabWorkspace.test.tsx`、`test_creator_m1.py`、`test_creator_m3.py`、
  `test_current_baseline_flow.py`：覆盖可选立项书、项目特定输入、真实拓扑及 MQTT 需求门禁；
- `docs/PRD_CREATOR_V3.md`、当前 ExecPlan、`docs/DECISIONS.md` 与本交接记录：固化产品与安全边界。
- `docs/GITHUB_UPLOAD_GUIDE.md` 与根 `.gitignore`：固化 GitHub 上传范围、排除项、人工上传步骤和
  许可证待决状态；生成目录只复制追踪的工作区文件。

完成性复核主要改动：

- Creator 前端壳、恢复状态、响应式/焦点管理、实物阶段、Device Lab 安装/参数入口和稳定意图键；
- Creator contracts、repository/router、持久 Job runner、指标投影、交付/导入恢复；
- Device Lab/设备操作幂等、设备包注册表、精确身份和首次部署/恢复指标；
- V30 迁移、项目创建事务钩子、项目包补偿清理及真实 V29 fixture；
- Creator M1–M7、设备实验室、迁移、指标、硬件门禁和前端恢复/布局回归；
- `PRD_CREATOR_V3.md`、`CREATOR_DELIVERY.md`、`CREATOR_METRICS.md`、决策、验收、ExecPlan
  与本交接记录。

完整路径以本次提交的显式文件清单为准；M0–M7 早期里程碑历史仍保留在各阶段提交。

以下为最初产品规划轮的历史记录：

- 新增：`docs/PRD_CREATOR_V3.md`。
- 新增：`tasks/ZW-CREATOR-001-creator-workbench-rebaseline.md`。
- 更新：`AGENTS.md`。
- 更新：`PLANS.md`。
- 更新：`CURRENT_TASK.md`。
- 更新：`HANDOFF.md`。

上述规划轮当时未修改业务源代码；M0–M7 的实际实现和验证结果见前文及里程碑提交。

## 本轮命令与验证

M8.1–M8.5 与本轮反馈修正已执行：

- `pnpm --dir apps/desktop test -- --reporter=dot`：`42 files / 270 tests passed`；
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_device_lab.py services/local-api/tests/test_creator_m1.py services/local-api/tests/test_creator_m3.py services/local-api/tests/test_creator_m4.py services/local-api/tests/test_current_baseline_flow.py services/local-api/tests/test_agent_skill_packages.py -q --rootdir services/local-api`：
  `53 passed, 2 warnings`；
- 产品经理式访谈补充回归：
  `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_creator_m3.py services/local-api/tests/test_current_baseline_flow.py services/local-api/tests/test_agent_skill_packages.py -q --rootdir services/local-api`：
  `21 passed, 2 warnings`；
- `pnpm typecheck`：共享 contracts 与桌面端严格类型全部通过；
- `pnpm build:desktop`：生产 Vite 构建通过，代码编辑器已形成按需块；保留 Monaco/主包大分块提示；
- 本轮隔离 Fake 浏览器服务健康检查通过，但页面停在账号/本地服务连接门禁，未绕过登录或伪造
  Creator 项目截图；实际项目画面的 390/720/1280 视觉走查保留给 M8.6；
- Local API 最终全量：`884 passed, 1 deselected, 2 warnings in 859.18s`；
- 默认排除的 1 项是带双门禁的 `hardware` M8 真机验收入口，未执行真实设备动作；
- 两个 Python warning 分别来自第三方 TestClient 弃用和受限
  `.pytest_cache` 写入；pytest 退出后的临时目录清理还会打印同一权限异常，但测试进程退出码为 0。

## 本轮完成性加固

- Creator 三类自动任务进入持久 `creator_jobs`，刷新后从服务端恢复真实状态；作品、阶段、对话草稿、
  焦点、抽屉和 390/720/1280 响应式状态均有回归测试；
- 仿真、参数、实物验收、交付与设备安装使用持久稳定意图；设备安装的语义指纹排除一次性确认令牌，
  重挂载重新准备后仍复用原 `operationId`；
- V30 迁移先规范化受支持的旧形态，再对 V29 历史表做零损摘要；全部 repair、外键和摘要通过后
  才写数据库级指标，全新库不计入旧库迁移；
- 交付导入使用持久意图日志、确定性项目 ID、即时补偿和启动恢复；进程中断不留下可见孤立项目，
  同包可重试、换包复用键被拒绝；
- 设备包、USB/ESP-Claw 精确身份、首次部署/恢复指标、结构 Artifact 真值、交付材料与第二用户身份
  均在公开边界失败关闭。

## 已确认决定

- Creator V3 产品 UI/UX 覆盖旧固定右侧三 Tab、图标轨和用模式切换页面的旧约束；Creator 内保留
  三师专业模式，普通/专业模式只改变信息层级并共享同一作品事实。
- 工程方案是唯一需要用户确认的事实；立项书是确认方案后按需生成的可选文档投影，不能阻塞数字原型。
- 数字原型的输入、测试、器件和连线必须由当前方案生成；不显示与项目验收无关的板载通道。
- 本地 MQTT 只能由明确的本地/局域网/离线 Broker 需求加入场景，不能因出现通用 MQTT 字样而启动服务。
- 真实代码只能来自 `CodeRun`，不存在时显示明确空状态。
- 桌面工作区按约三分之一对话、三分之二阶段画布分配。
- 安全、凭据、串口、Flash、执行器确认、互斥、回读和恢复不属于可删除的旧 UI 约束。
- 新 UI 在同一仓库隔离建设，旧壳先回退、后删除。
- 生命周期、系统 Job 和验证等级分离；验证等级为 0–6。
- 部署成功不等于真机运行通过；等级 5 必须有指定设备/固件上的行为证据。
- 四阶段可查看、动作受控；3D 对无结构需求项目不形成硬门禁。
- Creator 以设备包组织硬件，K10/XIAO 是代理验证，自研硬件通过相同契约加入。

## 已知问题与风险

- Creator M0–M7 与 M8.1–M8.5 软件路径已实现，但旧壳尚未删除；在 M8.6–M8.7
  迁移/教学验收前仍需保留明确回退入口。
- 当前仓库没有随安装包分发的固定 QEMU 二进制和兼容仿真镜像，不能宣称固件级仿真已交付。
- 真实 K10/XIAO、USB、ESP-Claw、参数同步、QEMU 和执行器仍需人工确认点测试。
- 三类包的第二用户闭环已由隔离的测试用户/项目自动验证，尚未由真实第二位真人和真实硬件执行。
- 本轮浏览器画面受账号/本地服务连接门禁阻断，尚未完成真实登录态下的像素级和键盘走查。

## 下一精确动作

执行 `ZW-CREATOR-001` M8.6：在隔离 Fake 数据与真实登录态下完成 390/720/1280 项目全流程、
键盘和焦点走查；再分别在明确确认点下完成 K10/XIAO 真实硬件连接、USB/ESP-Claw 部署、急停、
断线和恢复验收；随后验证安装包冷启动、升级、卸载与数据保留。全部通过后进入 M8.7，
冻结教学端旧壳并完成 Creator 正式发布收口。

## 危险边界

- 不得执行 `git reset --hard`、`git clean`、未知范围 stash、整库移动或覆盖本机运行数据。
- 不得在 M8 迁移与教学验收前删除旧 AppShell/V2AppShell、旧测试、前期产品材料或 Device Lab 实现。
- 不得执行整片 Flash 擦除、覆盖 NVS/用户数据、真实烧录、强制推送或公开发布。
- 不得把 Wi-Fi 密码、令牌、端点地址、真实串口/设备 ID 或本机路径写入项目、参数、日志、夹具或导出包。
- 不得把“局域网可访问”“部署任务成功”或 AI 文本当作设备身份、真机通过或用户验收证据。
- 场景中的本地 MQTT 节点只是方案能力声明；未经用户确认不得启动真实 Broker、监听局域网端口或修改防火墙。

## 2026-08-02 私有 GitHub 源码仓库

- 用户明确授权新建私有 GitHub 仓库并上传当前源码快照；目标仓库为
  `https://github.com/yusen/zhangwen`，GitHub API 已确认 `private=true`。
- 这次上传是私有源码备份，不是 M8.7 公开发布，不改变 Creator 的产品、真机或安装包验收状态。
- 当前工作区是无 `.git` 历史的源码快照；已在 `main` 初始化新仓库。历史交接中记录的里程碑提交和
  标签仍是恢复依据说明，但不能从此快照恢复为真实 Git 对象；首次上传会建立新的单提交基线。
- 上传前复核得到 1,132 个文件、22,948,007 bytes（21.88 MiB），无单文件超过 20 MiB；
  高置信度 GitHub/AWS/Google/OpenAI Key 与私钥头特征扫描为 0。唯一 `.env.example` 只含
  `change-me`、`replace-with-*`、空用户名/密码和 `example.invalid` 占位配置。
- 本轮只改变版本库与交接元数据，未修改业务代码，因此不重复运行产品测试；最近完整自动验证仍为
  前文的桌面端 `42 files / 270 tests passed`、Local API `884 passed, 1 hardware deselected`
  以及 contracts、严格 TypeScript 和生产构建通过。
- 已运行的新增命令包括：`git init -b main`、GitHub 凭据账号检查、仓库名称可用性检查、
  GitHub REST 私有仓库创建、文件体积审计和仅输出文件名的高置信度凭据扫描。
- `git diff --cached --check` 识别出 7 个历史文件的 94 条既有空白格式报告，主要是 Markdown
  强制换行尾空格，另有两个 Python 文件末尾多空行；为保持无历史源码快照原样，本轮未顺手重写。
- 下一精确动作：为新仓库配置 `origin`，显式暂存当前源码快照，创建初始提交并推送 `main`；
  随后通过 GitHub 连接器复核远端提交和 Private 可见性，再把结果回写本交接。
- 不得把仓库切换为 Public，不得强制推送，不得把本机 Git 凭据、API token 或 Credential Manager
  输出写入仓库、日志或交接。
