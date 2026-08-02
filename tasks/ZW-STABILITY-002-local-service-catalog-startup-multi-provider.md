# ZW-STABILITY-002 — 本地服务、硬件目录、启动与多 Provider 稳定化

状态：已完成（M1-M11）

本文件遵循根目录 `PLANS.md` 和 `WORKFLOW.md`，是当前用户定向稳定化工作的 living ExecPlan。

## 1. Purpose / Big Picture

彻底区分并修复“启动尚未完成”“Sidecar 短暂繁忙”和“Sidecar 真实退出”三类状态；把 Hardware Skill
目录改为首次建持久索引、后续只读索引、选中后才完整加载、更新后由用户手动刷新；缩短重复启动关键路径；
并在同一 OpenAI-compatible 本地网关下增加 DeepSeek、千问、GLM、Kimi 的独立配置与凭据选择。

## 2. Observable Acceptance

- 第二次及后续启动不再无条件重编译未变化的 shared contracts，也不使用全系统 WMI/CIM 进程扫描；启动日志记录各阶段耗时。
- 开发态和安装态由 Tauri 宿主拥有 Sidecar 生命周期；Sidecar 意外退出后执行有界自动恢复，连续崩溃达到上限后停止并留下脱敏日志。
- 健康检查一次超时只显示“正在恢复连接”，保留最近一次有效状态；连续失败跨过阈值后才显示“本地服务未连接”，恢复成功自动回到正常。
- 首次 Hardware Skill 目录请求在无索引时完整建立持久索引；后续启动和打开列表只读取索引，不扫描全部 Skill 文件。
- 列表索引包含展示摘要和已验证媒体元数据；只有用户选中器件时才读取并完整校验对应 Skill 与图片内容。
- Skill 创建或编辑成功后只提示“目录有更新”，不自动扫描；用户点击“刷新硬件目录”才重建索引并更新列表。
- 设置中可选择 DeepSeek、千问、GLM、Kimi；每个 Provider 只显示自身模型、默认 Base URL，并使用独立 Windows Credential Manager 条目。
- Kimi 内置模型固定包含 `kimi-k3`、`kimi-k2.7-code`、`kimi-k2.7-code-highspeed`；专业模式可为任一 Provider 添加受控格式的自定义模型 ID，并在保存后用于项目业务请求。
- 带有效桌面 capability 的开发态 Tauri 即使携带 Vite 本地 Origin，也可以保存、测试和清除 Provider 凭据；普通 Web 与伪造/缺失 capability 继续失败关闭。
- 设置保存失败时显示服务端原因并保留未保存的 API Key；使用当前表单测试成功时，若配置尚未保存，必须明确说明后续对话不会使用该表单配置。
- 切换 Provider 后新项目使用该 Provider 的默认模型；已有当前项目若模型不属于新 Provider，收敛到新默认模型。
- 自动测试不调用真实付费 Provider、串口、设备、Flash、固件烧录或公开发布。
- Provider 流式响应可以包含 `choices: []` 的 usage-only 帧；该帧不得导致 `IndexError`/`UNKNOWN`，最终 usage 必须安全归并。Kimi 与 GLM 使用同一兼容传输并共享此回归。
- 开发入口能识别并回收由上一轮掌问启动器留下的 Vite 进程；任何自动终止都必须由持久化所有权记录和进程启动时间共同证明，不按可执行文件名猜测。
- Sidecar 连续崩溃达到预算后停止自动拉起并留下中文可诊断状态；初次启动失败时桌面仍可打开，允许用户看到本地服务状态和日志位置。
- 自动生成恢复的三次费用上限由服务端并发门禁兜底，多个前端实例不能对同一失败消息同时发起两条自动恢复。
- 普通模式不显示 Provider 名称、模型名或 Base URL；专业模式信息分组简洁，首屏优先显示状态和主要动作。
- 完成自动回归、三档 UI 验收、工作树审计后生成并校验一个新的本地 NSIS 安装包；不签名、不公开发布。

## 3. Architecture / Safety Boundaries

- 云端 Provider 仍只能接收受控消息，不能访问文件、Shell、串口或设备；API Key 不写入 JSON、SQLite、日志或前端持久化。
- Hardware Skill 持久索引只是展示和候选排序投影，不是工程真值。选中器件、项目已确认器件和规则校验继续读取并完整验证目标 Skill revision。
- 手动刷新只重建 `<data_dir>` 内的可再生目录索引，不删除、覆盖或自动升级用户 Skill。
- Sidecar 恢复有次数窗口和退避，不允许无界重启循环；桌面关闭时仍必须终止宿主拥有的 Sidecar。
- 不清理 `.data`、凭据、用户参考目录、未提交任务或未知输出；项目整理只移动明确的开发辅助文件、补充忽略规则并形成审计报告。
- 工作树整理只处理已确认的生成物、缓存、重复构建输出和文档状态；不使用整库 `stash/reset/clean`，不删除未知或用户输入内容。

## 4. Root-Cause Evidence

- `dev-launcher.log` 显示 2026-07-18 23:29:55 → 23:32:25、2026-07-19 01:07:07 → 01:08:23、
  2026-07-19 01:18:03 → 01:22:19 均发生在 Sidecar 启动之前，对应无条件 contracts 构建约 150、76、256 秒。
- 2026-07-19 01:22:20 后 Sidecar `/api/health` 仍稳定返回 200，但启动器停在 Vite 前；当前启动器在该边界调用
  `Get-NetTCPConnection/Get-CimInstance`，本机同类只读命令可超过 10–30 秒甚至不返回。
- 当前 React 健康 Hook 对任意一次 4 秒失败立即写入 `disconnected`，没有连续失败阈值或最近成功保留。
- 当前安装态 Rust 宿主持有 Sidecar 子进程但只在窗口关闭时 kill；运行期子进程退出后没有监测或恢复。
- 当前 Hardware Skill 候选缓存每次请求先遍历目录计算 fingerprint，进程重启后无持久索引；硬件列表仍完整加载每个包，
  编辑成功事件还会自动改写已挂载列表和详情。

## 5. Milestones

- [x] M1：采集启动日志、健康状态、Hardware Skill 和宿主生命周期证据，固化验收与安全边界。
- [x] M2：持久 Hardware Skill 目录索引、选中加载、手动刷新 API/UI 与缓存回归。
- [x] M3：宿主 Sidecar 有界恢复、健康状态迟滞、启动器增量构建和阶段计时。
- [x] M4：DeepSeek / 千问 / GLM / Kimi 契约、凭据、OpenAI-compatible 调用与设置 UI。
- [x] M5：项目目录审计、低风险整理、专项回归、真实完整入口启动验收和 HANDOFF 收尾。
- [x] M6：修复陈旧 Vite 启动阻塞、Sidecar 有界恢复/初次失败降级和日志所有权。
- [x] M7：增加服务端自动恢复并发/次数门禁，并补齐费用上限回归。
- [x] M8：重新审核并简化设置、中央对话和右栏 UI/UX，完成三档 UI 契约验收。
- [x] M9：全量相关测试、工作树审计、文档交接与新版 NSIS 安装包构建校验。
- [x] M10：修复开发态 Tauri 千问凭据保存、失败反馈与“保存配置 → 对话运行时”链路。
- [x] M11：修复 Kimi/GLM usage-only 流式帧导致的业务请求失败，补齐 Kimi 三模型并支持专业模式自定义模型。

## 6. Decision Log

- 2026-07-19：本轮是用户定向 `ZW-STABILITY-002`，不是自主工作流中的 `ZW-017`。
- 2026-07-19：启动慢与运行期误报共享“单 Sidecar 可用性”表象，但根因不同，验收和指标必须分开。
- 2026-07-19：目录更新采用用户要求的显式刷新语义；不再用每请求 fingerprint 自动发现变化。
- 2026-07-19：目录索引可跨进程复用，但目标 Skill 的选择、项目事实水合和规则校验不得信任索引代替完整验证。
- 2026-07-19：四家 Provider 均走各自官方 OpenAI-compatible Chat Completions 端点；不引入四套 SDK。
- 2026-07-19：项目根目录中的外部参考工程和用户输入保持原位；只有已确认无调用方的临时 QA 辅助脚本允许迁入 `scripts-dev/`。
- 2026-07-19：用户要求“解除 UI 限制”解释为移除不必要的信息密度、重复说明和错误的普通模式泄露；中央永久主对话、固定“工作 / 产物 / 设备”三 Tab、单一推荐方案等 AGENTS.md 不可变规则继续保留。
- 2026-07-19：现场 `dev-launcher.log` 确认 11:18 启动失败由 PID 56404 的陈旧掌问 Vite 占用 5173 引起；该进程命令行为本仓库 Vite 且父进程已退出。后续启动器使用带启动时间的所有权记录回收自身残留，不扫描或误杀其他 Node/Python 进程。
- 2026-07-19：服务端自动恢复使用现有消息元数据和 `BEGIN IMMEDIATE` 原子认领，不增加 schema；同一失败只能认领一次，恢复链最多三次。
- 2026-07-19：安装态 Sidecar 首次冷启动允许最多 120 秒就绪，仍受连续失败六次上限约束；Hardware Skill 目录原子替换对 Windows 安全扫描的短暂 `PermissionError` 做有限退避重试，最终失败仍原样抛出。
- 2026-07-19：共享工作树中的 67 个有效 ACTIVE Hardware Skill 全部进入最终包；不擅自删除打包过程中出现的有效用户/并行任务目录。
- 2026-07-20：Provider 凭据操作以有效桌面 capability 为授权事实；Vite 的 `http://127.0.0.1:5173` Origin 不能把真实 Tauri 降级为 Web，伪造或缺失 capability 仍拒绝。
- 2026-07-20：连接测试可以显式测试尚未保存的表单配置，但不能把测试成功误报为对话已切换；对话始终从 `require_llm_config()` 读取已保存配置和对应安全凭据。
- 2026-07-20：现场 Kimi 连接测试和配置保存均成功，但 `/api/projects/suggest` 连续返回 503；最小真实业务流复现为 `IndexError: list index out of range`。原因是 Kimi 的 SSE 会发送 `choices: []` 的 usage-only 帧，而兼容传输无条件读取 `choices[0]`。GLM 与其他 OpenAI-compatible Provider 也必须按同一协议边界容忍空 choices。
- 2026-07-20：自定义模型 ID 仅是 Provider 模型代码，不是任意 URL 或命令；限制长度和字符集、绑定 Provider、持久化到非敏感 LLM 配置，并继续走现有凭据、Base URL、结构校验与本地安全门禁。

## 7. Validation Plan

- Python：Hardware Skill 首建/持久复用/手动刷新/坏索引恢复、目标 Skill 失败关闭、多 Provider 配置/凭据/HTTP/SSE。
- TypeScript：目录首次加载、无自动刷新、手动刷新、按选择取详情、四 Provider 设置、模型过滤、健康迟滞。
- Rust：Sidecar 重启预算、关闭门禁和路径边界；`cargo test` / `cargo check`。
- Launcher：PowerShell 解析、`start-local.bat --check`、contracts 新旧时间戳分支、阶段日志。
- 集成：完整入口冷/热启动计时，health 连续探测与桌面状态；不发真实模型请求。
- 安装包：Sidecar 构建与 smoke、Tauri NSIS 构建、manifest/hash/资源/绝对路径扫描；安装态桌面 smoke 仅在隔离条件允许时执行。

## 8. Progress

- 2026-07-19：完成 M1。确认当前正在发生的一次启动在 contracts 构建前置阶段耗时 256 秒，Sidecar 起来后 health
  约 81ms 返回 200；Vite 尚未启动。确认前端单失败判离线、宿主无运行期恢复、硬件目录每请求 fingerprint 和列表全包加载。
- 2026-07-19：完成 M2。ACTIVE Hardware Skill 首次完整校验后原子写入 `cache/hardware-catalog-v1.json`；后续列表和公共候选读取持久化摘要/媒体元数据。选择项目时才完整加载目标 Skill，编辑/创建事件只标记过期，用户点击刷新按钮才重建索引。
- 2026-07-19：完成 M3。健康检查前两次失败进入 `recovering` 且保留最近成功信息，连续三次才显示未连接；Tauri 监控 Sidecar 并以 1–30 秒指数退避恢复。实测强制终止 Sidecar 后自动恢复，正常关窗后 8100/5173 均释放。
- 2026-07-19：启动路径完成增量化。contracts 未变化时跳过构建；Vite 由启动器直接托管 Node 进程；开发态优先 `.venv` Sidecar；Rust/Tauri 未变化时直接运行已构建桌面程序。热启动由历史 76–256 秒降到约 9 秒。
- 2026-07-19：完成 M4。四个 Provider 共享受控 OpenAI-compatible transport，按 Provider 校验模型、隔离 Credential Manager/环境变量；专业模式可选择服务商、Base URL 和所属模型，项目模型在切换后收敛到新默认值。
- 2026-07-19：完成 M5。临时 CAD QA 服务归入 `scripts-dev/`，本地参考/输出目录加入忽略规则，形成 `docs/reports/PROJECT_FILE_AUDIT.md`。专项验证为 Python `37 passed`、前端 `19 passed`、contracts build/strict TypeScript、启动脚本解析和定向 diff check 通过；未调用真实 Provider、串口或设备。
- 2026-07-19：开始 M6-M9。只读现场确认最后一次失败为 `Port 5173 is already in use by PID 56404`；该 PID 是 08:42 启动的 `D:\ZW_V1\apps\desktop\node_modules\vite\bin\vite.js`，父进程已不存在，8100 当前未监听。纳入启动所有权、Sidecar 预算、并发恢复、简洁 UI、测试、工作树和安装包收口。
- 2026-07-19：完成 M6-M8。启动器仅回收所有权记录、启动时间、仓库根和端口均匹配的陈旧 Vite；Sidecar 初次失败不阻止桌面诊断界面，运行期有界恢复；服务端自动恢复认领/三次上限已并发化；设置普通模式供应商无关，专业参数折叠；`720x720` 左右抽屉互斥，`390x844` 顶栏无重叠且中央对话始终只有一份。
- 2026-07-19：完成 M9。前端全套 `32 files / 200 passed`，strict TypeScript 与 production build 通过；后端按四组覆盖全部 `655` 项，发现并修复流取消任务泄漏、立项书模型参数遗漏、模板缓存污染和 Windows 目录短锁后复测通过；Rust release `5 passed`。真实 `start-local.bat` 启动后 5173/8100 正常、`/api/health status=ok`，正常关窗自动释放端口和所有权记录。
- 2026-07-19：最终 NSIS 与独立验证通过。`掌问_0.1.0_x64-setup.exe` 为 `393,644,568` bytes，SHA-256 `2635CD2658C23B1E92E36BF55BCF1FBFD5AF1D2A36B6729D9ADF5395BC1783C5`，未签名、未安装、未发布；Sidecar smoke 在 PATH 不含 Node/Python 时通过。
- 2026-07-20：完成 M10。现场日志确认 `PUT /api/settings/llm` 返回 409，而连接测试可使用未保存表单和内联 Key 返回成功，导致对话继续读取旧 Provider。修复后有效 Tauri capability 可跨 Vite Origin 保存千问配置；保存失败保留 Key 并显示服务端原因，未保存表单的测试成功明确提示“请先保存设置”。定向后端 `18 passed`、桌面设置/对话组合 `35 passed`、strict TypeScript 通过；未调用真实 Provider。
- 2026-07-20：开始 M11。已核对 Kimi 官方模型页和快速开始，确认三款目标模型及 `https://api.moonshot.cn/v1`；核对智谱官方 GLM-5.2/OpenAI-compatible 文档。使用 Credential Store 中既有 Kimi 凭据执行一次最小结构化流请求，未输出密钥或模型正文，稳定复现空 `choices` 帧触发的 `IndexError`。后续使用 MockTransport 固化，不重复消耗真实额度。
- 2026-07-20：完成 M11。兼容传输先归并 usage 并安全跳过缺失/空 choices 帧，Kimi/GLM MockTransport 回归覆盖最终正文与 token 用量；GLM `reasoning_effort` 修正为顶层。Kimi 目录补齐三款目标模型，专业模式折叠高级参数支持 Provider 绑定的受控自定义模型，并贯通设置持久化、目录、项目和运行时。定向后端 `23 passed`，完整相关后端 `93 passed`，桌面全量 `32 files / 205 passed`，strict TypeScript 与 production desktop build 通过；构建仅保留既有 Monaco/Vite 大分块提示。除最初用于定位的单次最小 Kimi 请求外，修复验证均使用假 Key/MockTransport，未调用 GLM 或其他真实 Provider。

## 9. Handoff / Dangerous Actions

- 当前工作树包含大量用户及既有里程碑未提交修改；禁止 `git reset --hard`、`git clean`、全量暂存或覆盖无关差异。
- 不删除 `references/local/`、`references/source-packages/`、`.data/` 或 `outputs/`。
- 不执行真实 Provider 连接测试、设备上传、复位、Flash 擦除或固件烧录。
