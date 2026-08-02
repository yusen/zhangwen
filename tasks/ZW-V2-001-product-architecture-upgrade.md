# ZW-V2-001 — V1 基线上的 V2 产品与架构升级

状态：M0-M5.3 软件实现与自动验收已完成；三师电子相册真人纵向流程、代码验收和 CAD 源码→真实 3D 构建已闭环，实体设备上传、对话 Change Set 化、Project Release 和其余 M6 外部验收待办

日期：2026-07-26

权威 PRD：`docs/PRD_V2.md`

工作分支：`codex/zw-005-016-autonomous`（规划基线 HEAD `291ff20`）

当前仓库任务：`ZW-V2-001`；`ZW-CLOSURE-001` 外部验收待办继续保留

## 0. Progress

- [x] 2026-07-28 三师真人纵向流程：在真实桌面中新建“行空板K10桌面电子相册”，问题引导师完成两轮澄清、唯一推荐方案和立项书；智能工程师在两次本地输出拒绝后保留原需求自动恢复，第三次生成 `src/main.py`，STATIC/SYNTAX 均通过并接受为 v1；结构工程师通过受控 `ProjectStructureContext` 从泛化指令恢复 K10/电池装配树，确认 `cadrev-ce966248cdf34f65b42eb32d31407b96` 后生成并回显 102,096-byte GLB、4 个 STEP 和 3 个 STL。V1 导入基线已推进到 V2，`CAD_INTENT/CAD_BUILD` 均 `SUCCEEDED · 100%`；实体设备未连接，未执行上传、复位、Flash 或固件烧录。操作记录见 `docs/THREE_EXPERT_END_TO_END_GUIDE.md`。
- [x] 2026-07-28 CAD 真人构建修复：当前 K10 源码的可选 `lid.stl` 未落盘时，原 Worker 仍声明 `available`，触发宿主 `CAD_BUILD_OUTPUT_INVALID`。现改为 Worker 只发布 staging 内真实存在的文件，缺失可选导出标记 `unavailable`，越界/符号链接仍由宿主失败关闭；GLB 按非零大小和 `glTF` 文件头确认。真实页面用同一 revision 重跑成功。Worker/golden `11 passed`、CAD Intent `5 passed`、三师/CAD/代码后端组合 `39 passed`、桌面定向 `6 files / 26 passed`。
- [x] 2026-07-26 V2 可读事实与上下文对话修复：普通界面隐藏 `q_*`/内部 ID/原始 JSON并恢复来源问题与选项中文；保持单一对话实例，把工作区、工程子页和项目版本同时传入问题引导师与 Expert Runtime，并按页面选择主责工程师。真实项目五项事实烟测、后端组合 32 项、桌面 35 文件 218 项、contracts/typecheck/production build 通过；桌面与 Sidecar 已重启。
- [x] 2026-07-26 V1→V2 联动修复：旧项目幂等导入基线、列表式方案摘要、preferred hardware、Artifact、设备与验证真实投影已完成；并发基线、Project Kernel/CAD/项目/进度/Artifact/设备后端组合 29 项，桌面 35 文件 218 项、strict typecheck 通过。未调用真实设备、上传、reset、Flash 或 Provider。
- [x] 2026-07-26 M5.3 代码/结构闭环：V2 代码页复用原有不可变版本编辑、静态/语法验证和“接受”浮窗，接受后进入设备页执行扫描→连接→受控上传→哈希回读→启动→只读日志；Web 仅在 Local Bridge 授权后开放对应能力。V2 结构页确认源码后调用受控 Node Worker 和本机 CadQuery，生成并校验 GLB/STEP/STL、持久化 ArtifactFile 和 SHA-256，再在原结构页加载 GLB。未连接或写入真实设备。
- [x] 2026-07-26：用户确认连续完成 M0-M5；`CURRENT_TASK.md` 已切换到本任务。
- [x] M0 契约与来源冻结：共享 contracts、149 文件来源快照、排除策略和 3 组 source golden 已通过。
- [x] M1 Project Kernel 与 Capability Facade：schema v27、备份迁移、投影、Change Set、Version/Release 与能力 Adapter 已通过 25 项测试。
- [x] M2 V2 UI Shell：四工作区、全局 AI 面板、项目/版本、Change Set、Job 抽屉、专业模式和 V1 feature flag 回退已完成；新增 UI 测试 2 项通过。
- [x] M3 CAD Intent Worker：受控无 HTTP IPC、清理宿主凭据的子进程环境、Capability/Hardware 快照、哈希绑定源码与补丁、预检/真实导出动作、Tool Job、结构修订/确认/撤销、Artifact 源码版本、对象索引及 V2 结构页已接通；M5.3 已在当前开发机用真实 CadQuery 构建并校验 GLB/STEP/STL。安装态和真人页面仍按 M6 单独验收。
- [x] M4 设备运行态接管：新增 `ATTACHED_UNVERIFIED / RUNTIME_BUSY / MANAGED`，串口附加不再执行 identity probe；写入顺序固定为 Ctrl-C 多提示符接管后探测身份，并增加跨会话 DB Runner 端口租约。硬件 reset 仅在二次短语确认后执行，随后必须重枚举并在启动窗口 break-in；备份、hash 回读、恢复、取消、终端和 Fake transport 回归共 55 项通过（其中 operation service 46 项），未访问真实串口、reset、上传、Flash 或固件。
- [x] M5 Web Local Bridge：新增回环发现、桌面创建两分钟挑战、Origin allowlist、Web 领取十分钟项目级 capability lease、一次性写 request id、撤销和持久化 Job/会话恢复。Host 门禁只映射 `cad.local / device.serial / device.upload`，Shell、任意路径、凭据和固件烧录不可授权；错误 Origin、跨项目、配对/写请求重放、过期、撤销和非回环均有测试。纯 Web、Web+Bridge、Tauri、实验 Web Serial 能力矩阵已覆盖；Bridge/Host 7 项和桌面全量 218 项通过。
- [x] 最终组合门禁：CAD 来源/Worker `8 passed`；Sidecar 全量 `733 passed, 1 warning`；Desktop `35 files / 218 passed`；contracts build、根 strict typecheck、production desktop build 和定向 `git diff --check` 通过。唯一后端 warning 为既有 Starlette/httpx 弃用提示，前端仅有既有 Monaco/Vite 大分块提示。
- [x] M5.3 最终门禁：CAD Worker `8 passed`；真实 CAD 与设备上传/终端专项 `60 passed`；Desktop 全量 `36 files / 223 passed`；contracts build、strict typecheck 和 production Vite build 通过。测试未写入、复位或烧录真实设备。

## 1. 目标

在不丢弃 V1 账号、项目、三师、Hardware Skill、Artifact、设备和 CAD 历史的前提下，完成 V2 产品与架构升级：

- 全面重构 UI 为“概览 / 工程 / 结构 / 交付”实际工作区和全局 AI 协作面板。
- 建立 Project Kernel、Change Set、Capability Engine、Project Version 和 Release。
- 以用户指定的 `ZW-CAD-intent` 为 CAD 行为基线融合真实 3D 工作流。
- 解决旧程序运行时连接/上传被阻断的问题。
- 通过 Local Bridge 让 Web 安全执行本地 CAD 和设备 Job。

## 2. 非目标

- M5.1 只为有既有 V1 工程事实的项目建立一条可审计基线，不批量复制或改写方案、硬件、Artifact、设备和 CAD 业务数据。
- 不执行 Flash 擦除、固件烧录、真实串口上传或公开发布。
- 不把外部 CAD 目录连同 `node_modules`、本地模型配置或运行产物直接复制进仓库。
- 不把 Project State 实现成与现有关系表竞争的第二套巨大 JSON 真值。
- 不创建编号 `ZW-017`；V2 使用独立命名空间。

## 3. 当前证据

- V1 PRD 版本为 `v1.1-closure`，SQLite schema v26，纵向软件与模拟闭环已完成，外部验收仍待办。
- 当前 UI 和 Host capability 是主动门禁；Web 没有 Local Bridge 配对协议。
- 现有上传已经实现 Ctrl-C 接管，但连接阶段先执行 identity probe，旧程序繁忙时可能在进入接管前失败。
- 指定 `ZW-CAD-intent` 非依赖树为 149 文件、8,392,462 bytes，组合 SHA-256 为
  `c6054bcb0a3c106f931583eb931babd1c0cf846b03f08343aafdb509a3a852ee`；46 个 JS 文件语法通过。
- 指定 CAD 拷贝没有 `server/*.test.js` 和 `packaging/`；`npm test` 为 0 tests，不能作为生产验收证据。

## 4. 实施里程碑

### M0：契约与来源冻结

- [x] 评审并冻结 `docs/PRD_V2.md`。
- [x] 为 V2 新增共享 contracts：ProjectState、ChangeSet、Capability、ProjectVersion、Release、ToolJob、HostCapabilityLease。
- [x] 对 `ZW-CAD-intent` 建立可追溯来源快照、排除清单和 hash manifest。
- [x] 重建 CAD 缺失测试与 golden，先证明行为再融合。

### M1：Project Kernel 与 Capability Facade

- [x] schema 前进迁移、备份和历史回放测试。
- [x] 从 V1 关系表生成 Project State projection。
- [x] Change Set 验证、确认、原子提交、事件和版本。
- [x] 聚合 Hardware/Board/Agent Skill、机械 profile、模板和宿主执行能力。

### M2：V2 UI Shell

- [x] 新四工作区和全局 AI 协作面板。
- [x] 项目/版本导航、页面上下文和 Job 抽屉。
- [x] Change Set/Diff/确认与普通/专业模式。
- [x] V1 UI feature flag 回退和迁移验收。

### M3：CAD Intent Worker

- [x] 移除独立 HTTP UI、项目库、模型源和硬件真值，改为受控 Worker/IPC。
- [x] 适配 Capability/Hardware Skill、Project Version 和 Artifact Service。
- [x] 结构页面、对象/特征索引、自然语言补丁、修订、撤销和导出执行路径。
- [x] Worker 资源上限、源 hash、AST/mesh 预检和失败恢复；当前开发机真实 CadQuery 运行时已自动构建 GLB/STEP/STL，安装态复验保留为 M6。

### M4：设备运行态接管

- [x] Device Session 拆分 `ATTACHED_UNVERIFIED / RUNTIME_BUSY / MANAGED`。
- [x] identity probe 移到接管后的写入预检。
- [x] 合作式 Ctrl-C、多提示符识别、单 Runner 端口租约。
- [x] 用户确认后的硬件 reset、端口重枚举和启动窗口 break-in。
- [x] 备份、暂存、hash、恢复、取消、终端和模拟器验收。

### M5：Web Local Bridge

- [x] 本机回环服务与发现；安装包集成留在 M6 发布验收。
- [x] 配对挑战、Origin allowlist、短期 lease 和撤销。
- [x] 统一 CAD/设备 Job 门禁和持久化恢复。
- [x] 纯 Web、Web+Bridge、Tauri 和实验 Web Serial 能力矩阵测试。

### M6：纵向样板与发布验收

- [ ] 自动浇花从自由创意到 Project Release 的完整 V2 流程。
- [x] 电子相册从自由创意到 V2 项目版本的真人三师流程：真实 Provider 澄清/立项、代码生成与本地接受、上下文驱动 CAD Intent、真实 GLB/STEP/STL 和交付页版本/产物核对均已记录；实体上传与 Release 未包含。
- [x] V1 数据迁移、旧 CAD 读取和旧设备记录兼容（软件投影与模拟回归完成；真人设备/CAD 外部验收仍属于 M6）。
- [ ] 桌面、Web、Bridge、CAD、设备模拟器和安装包门禁。
- [x] 当前开发机真实 CadQuery 构建已独立记录：真实 Worker/CadQuery 端到端生成 GLB/STEP/STL，并校验 GLB 文件头、文件大小和 SHA-256。
- [x] 真实 Provider 三师对话已在桌面记录；没有导出或写入 Provider 凭据。
- [ ] 安装态 CAD 构建和受控真机上传分别记录，不伪造外部验收。

## 5. 测试策略

- 所有跨前后端行为先更新 shared contracts 和契约测试。
- Project Kernel 覆盖并发基础版本、幂等、事务回滚、事件重放和 projection hash。
- CAD 以外部行为 golden、模板 hash、源码补丁、AST、真实 CadQuery、STEP/STL/mesh 和安全逃逸为重点。
- 设备使用 Fake transport、串口重枚举模拟器、Ctrl-C 禁用/捕获、端口占用、取消、恢复和 Sidecar 退出测试。
- Local Bridge 覆盖错误 Origin、过期 lease、重放、越权项目、任意路径/Shell 注入和断线恢复。
- 自动测试不调用真实付费 LLM、真实串口、Flash 或固件。

## 6. Decision Log

- 2026-07-26：用户明确允许 UI 全面重构，V2 覆盖 V1 中央对话和固定三 Tab 不变量。
- 2026-07-26：用户指定 `ZW-CAD-intent` 为重新验证后的 3D 基线；审计确认语法完整，但当前传递目录缺少测试和 packaging，因此先作为行为权威建立 golden。
- 2026-07-26：CAD 首期采用受控 Node Worker 融合，不把独立服务的账号、项目、模型源、硬件库和前端带入掌问。
- 2026-07-26：设备问题根因包括连接 identity probe 早于上传接管；V2 拆分附加与管理态，并增加用户确认后的硬件 reset 接管层。
- 2026-07-26：Web 采用 Local Bridge 获得完整本地能力；Web Serial 只作为受限实验路径。
- 2026-07-26：V1 数据和外部验收任务继续保留；V2 不改写当前 `CURRENT_TASK.md`。
- 2026-07-26：旧项目的 V2 第一个版本固定为无 Change Set 的只读 V1 导入基线；空白项目继续 V0。工程页直接读取现有事实源，不再从聊天摘要或空 SharedContext 推断完成度。
- 2026-07-26：V2 继续复用同一项目聊天历史和输入草稿，但活动工作区/子页决定默认主责工程师并成为受限 Provider 上下文；该上下文只负责聚焦回答，不授予本地执行权限，也不作为完成证据。
- 2026-07-26：M5.2 不宣称完成对话 Change Set 化。现有 V1 Runtime 产生的 confirmed/proposed fact、Artifact 和 PendingItem 仍按原领域仓储写入；把所有正式 AI 修改统一转换为“提议 → Change Set → 用户确认 → Project Version”需要后续独立契约与迁移。

## 7. 风险

- 外部 CAD 模块缺失自动测试，直接融合可能造成不可见行为漂移。
- Node + Python 双 Worker 会增加安装包、启动、资源和故障诊断复杂度。
- UI 全面重构会影响大量既有桌面测试，需要先固化领域和数据契约、再迁移页面。
- 硬件 reset 虽不擦除 Flash，但可能改变电机、继电器等执行器状态，必须有安全默认态和确认。
- Local Bridge 扩大 Web 到本机的信任边界，必须在功能开发前完成威胁模型和协议测试。

## 8. 下一步唯一动作

当前电子相册项目已完成真人三师流程并停在“V2 · 可上传”：代码已接受、真实 3D 已回显、CAD Intent/Build 均成功，设备页真实显示“未连接设备”。下一步只能在用户提供测试设备并明确允许日常 MicroPython 写入后，按“工程 → 设备 → 扫描 → 连接 → 上传并运行 → 只读终端”记录一次受控真机上传；不要把固件烧录、Flash 擦除或硬件 reset 混入日常上传。
