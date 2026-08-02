# ZW-CAD-intent

`ZW-CAD-intent` 是 ZhangWen 当前的网页端 AI 建模 agent 分支，路线是：

```text
LLM 需求理解 + 后端内部 tool 编排 + 确定性 CAD 生成
```

它不是 MCP server，也不是多个 LLM 进程互相协作的多智能体系统。当前实现是单个 Node 后端服务内的一套内部 tools。首次建模仍由确定性程序生成；模型生成后，LLM 可以在严格安全边界内为当前项目源码副本生成精确修改补丁。硬件库约束、首次 BOM/布局、补丁校验、CadQuery 构建和真实 STEP/STL 导出仍由后端控制。

核心原则：

- 硬件只能来自 `server/data/hardware-library.json` 或用户临时提供的 custom profile。
- 硬件体系 `common` 的中文名称统一为“通用件”。通用件通过正交字段 `model_type` 分为 `electronic_component`（电子元器件）和 `structural_part`（结构件），原有 `category` 和 `roles` 继续表达功能角色。
- 首次建模时 LLM 不直接决定最终 CAD 坐标、旋转矩阵或模型代码；后续 `model_edit` 只允许修改当前项目 CadQuery 副本，不能修改公共模板、服务器、硬件库或其他项目。
- 硬件库缺失时必须明确反馈缺什么功能、缺什么硬件，不能编造尺寸继续建模。
- 用户可以选择补 profile，也可以选择忽略缺失功能，用剩余库内硬件继续流程。
- 普通电子项目的外壳形态限定为适合 3D 打印的带盖长方体盒子，带必要圆角、开孔、固定孔或固定槽。独立结构件项目不生成盒体。
- 同一任务内的补充、返工、GUI 调参和 CadQuery build 复用同一个 `ZW-PRODUCT-*` 结果目录。
- 纯结构件项目允许没有任何主控或电子器件，但只使用通用件库中已有且通过校验的结构件 CadQuery 母版。
- LLM 不可用时明确阻断，不回退成本地 deterministic intent。
- 真实 3D 模型缺失或加载失败时明确报错，不静默切换到简化 3D 预览。

## 环境准备与启动

项目使用手动部署流程。新环境需要先安装 Node.js 20+、npm 和 Python 3.10+；真实 STEP/STL 导出还需要准备本页“CadQuery 与 Python 环境”列出的 Python 依赖。

安装 Node 依赖并启动服务：

```powershell
cd E:\GOODproject\ZhangWen\ZW-CAD-intent
npm.cmd install
npm.cmd run start
```

开发模式和直接运行后端的等价命令：

```powershell
npm.cmd run dev
node .\server\index.js
```

模型源需要由服务器管理员手动写入本机 `.env.local`，或在服务启动后点击页面右上角的 LLM 状态灯进行配置。不要把真实 API key、token、密码或私有 URL 写入源码。

默认地址：

```text
http://localhost:5187
```

健康检查：

```text
http://localhost:5187/api/health
```

临时换端口：

```powershell
$env:ZW_CAD_INTENT_PORT=5197
npm.cmd run start
```

如果看到 `EADDRINUSE` 或 `port 5187 is already in use`，说明旧服务还占着端口：

```powershell
netstat -ano | findstr :5187
Stop-Process -Id <PID>
npm.cmd run start
```

当前前端依赖 `three`。Node 和 npm 依赖版本以 `package.json`、`package-lock.json` 为准。

## Windows 单文件离线安装器

Windows 10/11 x64 安装包的构建命令：

```powershell
cd E:\GOODproject\ZhangWen\ZW-CAD-intent
npm.cmd run package:win
```

最终产物：

```text
dist/ZW-CAD-intent-Setup-0.1.0-win-x64.exe
```

这个 EXE 内置 Node.js、Python、CadQuery/OCP 和前端依赖。目标电脑不需要预装这些运行环境，也不需要联网完成安装。安装范围是当前 Windows 用户，安装完成后只创建桌面和开始菜单快捷方式，不会自动启动。

打包流程使用生产文件白名单，并明确排除 `.env`、`.env.local`、`server/data/model-sources.local.json`、`exports/`、日志、测试和本机运行产物。安装后的第一次启动会显示未配置 LLM，使用者需要在模型源面板中填写自己的 API key；构建机上的 API key 不会进入安装包。

当前安装器未做代码签名，因此在其他电脑首次运行时可能出现 Windows SmartScreen 的“未知发布者”提示。完整的构建边界、固定运行时版本和许可证说明见 `packaging/README.md`。

## LLM 模型源

LLM 是当前流程的必要能力之一。没有可用模型源时，需求意图分析会返回：

```text
status: needs_input
blocking_reason: llm_unavailable
```

模型调用失败、超时、返回空内容或返回非法 JSON 时，会返回：

```text
status: needs_input
blocking_reason: llm_intent_failed
```

系统不会在 LLM 不可用时静默回退成本地 deterministic intent。这样做是为了避免用户以为模型真的理解了需求，但实际只是旧规则硬凑出来的结果。

`.env.local` 示例：

```env
ZW_CAD_INTENT_API_KEY=请在这里填写你的模型服务密钥
ZW_CAD_INTENT_API_BASE_URL=https://你的模型服务/v1
ZW_CAD_INTENT_MODEL=请在这里填写模型名
ZW_CAD_INTENT_FORCE_MOCK=0
```

兼容旧变量名：

```env
ZW_CAD_API_KEY=请在这里填写你的模型服务密钥
ZW_CAD_API_BASE_URL=https://你的模型服务/v1
ZW_CAD_MODEL=请在这里填写模型名
```

`ZW_CAD_INTENT_FORCE_MOCK=1` 表示禁用当前 LLM 配置或模拟未配置状态，主要用于测试阻断行为；它不是“离线继续完整建模”的开关。

本地模型源面板配置会写入：

```text
server/data/model-sources.local.json
```

这个文件的优先级高于 `.env.local`。如果改了 `.env.local` 但页面仍显示旧模型源，优先检查并备份处理 `server/data/model-sources.local.json`。

安全要求：

- 不要把 API key、token、密码或私有 URL 写入源码、README、提交历史或聊天记录。
- 后端接口返回给前端时只暴露 `hasApiKey`、掩码和元信息，不返回明文 key。
- `.env.local` 和 `server/data/model-sources.local.json` 都应该只保存在本机。

## 当前工作流

ZW-CAD-intent 是任务制工作流：

1. 用户第一次发送需求、选择硬件后发送建盒指令，或选择通用结构件开始独立建模，即视为创建或进入一个任务。
2. 后端创建或复用 `exports/ZW-PRODUCT-yyyyMMdd-HHmmss/` 任务目录。
3. 每轮输入先经过 `conversation_route`，判断用户是在提新需求、进入独立结构件项目、确认分析、修改需求、修改方案、选择阻断选项，还是确认继续建模。
4. 普通自然语言需求先进入“需求-功能-硬件-库匹配分析确认”阶段；纯通用结构件需求进入 `standalone_structural_parts`，不运行电子功能分析。
5. 普通项目确认分析后进入 BOM、profile、盒体可行性、布局、校验和 2D 参数确认；结构件项目只确认结构件清单、母版状态和并排预览。
6. 用户确认继续建模后，后端生成最终 artifact。结构件项目不会添加主控，不会生成底壳或上盖。
7. 同一任务内，用户补充需求、修改方案、GUI 调参或运行 CadQuery build，都会复用同一个 `ZW-PRODUCT-*` 目录；项目源码以逐版修订保存，受管预览和导出更新为最新版。
8. 用户点击“新任务”并二次确认后，下一次发送会创建新的任务目录，并清空旧硬件选择、草案、artifact 和阻断状态。
9. 受管项目按最近活动时间最多保留三份；正在执行的项目临时受保护。旧项目首次纳入保留策略时，先生成审计清单并按存储层规则等待明确确认。

主链路：

```text
conversation_route
-> requirement_function_selection_analysis
-> intent_analyze
-> hardware_bom_select
-> function_verify
-> profile_check
-> orientation_resolve
-> box_feasibility_check
-> layout_solve
-> design_validate
-> cadquery_generate
-> artifact_export
-> cadquery_build
```

独立结构件链路：

```text
conversation_route
-> standalone_structural_parts
-> 通用结构件母版校验
-> structural_parts_v1 项目源码
-> artifact_export
-> cadquery_build
```

该链路使用 `route_action: "standalone_structural_parts"`、`design_mode: "structural_part_project"` 和 `hardware_system: "common"`，跳过主控选择、电子功能验证、安装朝向、盒体尺寸、盒体布局和外壳生成。

关键分支：

- `design_revision`：用户说“把 A 改成 B / 删除某功能 / 换传感器 / 调整安装面”时，解析成结构化修改意图，并在同一 taskId 内重算。
- `model_edit`：真实模型生成后的普通自然语言修改默认针对当前项目。LLM 输出带源码哈希的精确补丁，后端先暂存和构建；高影响修改确认后才提交，失败时恢复原版本。
- `surface_engraving`：处理外部平面的单行或多行凹刻，支持自然语言位置、字号和分行。
- `resolution_option_route`：阻断步骤有按钮时，用户也可以直接打字选择，例如“忽略缺失功能继续”“我来补参数”。
- `standalone_structural_parts`：只选择或明确点名通用结构件且没有盒体意图时，使用现有母版建立无主控、无盒体的结构件项目。
- `selected_hardware_enclosure`：用户已经选择硬件并要求“给选定硬件做盒子”时，不强制推复杂功能需求，直接基于已选硬件布局、固定、开孔和建盒。
- `build_confirmed`：2D 草案阶段用户确认继续时，必须走构建路径，不重新跑旧需求分析。

缺失硬件时，系统会明确说明：

- 用户需求包含哪些功能。
- 每个功能需要哪些硬件角色。
- 硬件库里哪些已有，哪些没有。
- 用户可以补充 custom profile、修改需求，或选择“忽略缺失功能继续”。

选择“忽略缺失功能继续”后，系统会删除缺失硬件对应功能和角色，只保留硬件库能满足的部分继续流程。它不会伪造缺失硬件尺寸，也不会写入假的 profile。

## 内部 Tools 与 Skills

内部 tool 的契约写在：

```text
skills/<tool_id>/SKILL.md
```

这些 Markdown skills 是 zwcadintent agent 和 Codex 共同遵守的说明，不是 MCP tools，也不会启动单独 MCP server。

当前 tools：

- `workflow_orchestration`：总流程说明型 skill，约束完整链路、分支边界和 LLM 职责。
- `conversation_route`：判断本轮用户输入应该走确认、修改、新需求、选项回复、已选硬件建盒或确认构建。
- `standalone_structural_parts`：校验并组合通用结构件母版，建立独立结构件项目并定义逐件导出契约。
- `model_edit`：理解当前模型的自然语言修改，并安全更新当前项目源码副本、修订和项目记忆。
- `design_revision`：把用户修改语句转成结构化 revision intent。
- `resolution_option_route`：把用户按钮点击或文本回复匹配到当前可用 resolution option。
- `requirement_function_selection_analysis`：需求、功能、硬件角色和硬件库匹配的上层分析。
- `intent_analyze`：把用户需求和任务上下文转成结构化 intent。
- `hardware_bom_select`：只从硬件库或 custom profile 中选择 BOM。
- `function_verify`：验证 BOM 是否覆盖用户需求、硬件是否确实存在于库中。
- `profile_check`：检查硬件尺寸、安装、开孔、避让和参考模型字段。
- `orientation_resolve`：确定安装面、交互面和旋转。
- `box_feasibility_check`：计算盒体尺寸并检查安装面容量。
- `layout_solve`：生成硬件、开孔、固定结构和固定孔位置。
- `design_validate`：执行干涉、壁厚、开孔、固定结构、CadQuery 静态检查等校验。
- `cadquery_generate`：生成确定性 CadQuery 建模代码。
- `artifact_export`：写入任务目录、2D/调试预览资产、metadata 和 workflow 产物。
- `cadquery_build`：运行 CadQuery 并导出真实 STEP/STL。

每个已生成模型的项目目录包含：

```text
exports/<projectId>/project/
  project.json
  <model-source>.cq.py
  model-index.json
  project-memory.json
  default-parameters.json
  assets/
  revisions/
  staged/
```

公共模板只在项目首次创建时复制。独立结构件项目的主源码为 `project/structural-parts.cq.py`；后续自然语言修改、刻字、参数同步和撤销都以项目副本为唯一写入目标，不会反向修改通用件母版。

后续如果添加 ZW-CAD-intent 专用 skill，必须继续使用 Markdown 和独立目录。不要把 `ZW-CAD-code` 的 runtime skills 迁移、复制或复用到本项目。

## Workflow 产物

每个任务目录位于：

```text
exports/ZW-PRODUCT-yyyyMMdd-HHmmss/
```

同一秒内多次创建会追加后缀，例如：

```text
exports/ZW-PRODUCT-20260624-103654-02/
```

workflow 调试产物位于：

```text
exports/ZW-PRODUCT-yyyyMMdd-HHmmss/workflow/
```

当前标准 workflow 产物：

```text
00_requirement_analysis.json  需求、补充信息、功能拆解、硬件角色、库内匹配/缺失、route/revision 摘要
01_intent.json                结构化用户意图、功能、约束、意图来源
02_bom.json                   BOM、硬件选择、缺失硬件请求
03_profile_report.json        硬件 profile 完整性、pending/fail 字段、profile 摘要
04_feasibility_report.json    盒体尺寸、面容量、预审校验、自动修复记录
05_layout_plan.json           硬件、开孔、固定结构、固定孔的位置和安装面
06_checks.json                校验结果、warnings、validation_context
07_cadquery.py                后端确定性程序生成的 CadQuery 建模代码
08_export_manifest.json       STL、STEP、glTF、JSON、代码等导出项状态
```

`00_requirement_analysis.json` 会在首轮需求分析后立即写入。`01_intent.json` 和 `02_bom.json` 在需求分析阶段会先以 partial 形式写入，最终建模后会被完整版本覆盖。`03-08` 只在完成后续阶段后出现。

独立结构件项目继续写入 workflow 调试产物，但 `function_verification_report` 明确标记为 `skipped_structural_part_project`，盒体可行性和盒体布局不作为该模式的必需检查；`05_layout_plan.json` 记录的是结构件并排预览场景，不表示真实装配关系。

普通盒体 artifact 仍会保留：

```text
cadquery.py
design-state.json
checks.json
artifact.json
preview.gltf
base.stl
lid.stl
hardware-reference.stl
opening-reference.stl
```

CadQuery build 成功后，还会写回同一任务目录：

```text
model.step
model.stl
base.step
base.stl
lid.step
lid.stl
hardware.step
hardware.stl
mesh-checks.json
```

独立结构件 CadQuery build 成功后写入：

```text
model.step                              并排整体预览，不作为可打印零件
model.stl                               并排整体预览，不作为可打印零件
structural-parts/<part-id>.step         单个结构件 STEP
structural-parts/<part-id>.stl          单个结构件 STL
structural-parts-manifest.json          逐件导出清单
mesh-checks.json                        整体和逐件 mesh 检查
```

多结构件默认每个条目一件，沿 X 轴按 15 mm 间距并排。这个排列只方便整体预览，不代表系统推导了装配、配合或连接关系。

## 前端行为

前端是一个任务制建模界面：

- 底部主按钮是“发送”。
- “新任务”按钮会弹出二次确认框，确认后清空当前任务状态。
- 中央区域根据阶段显示需求分析、2D 参数确认、3D 模型预览或阻断反馈。
- 左侧对话流会同步显示需求分析、needs_input、确认、修订和错误反馈。
- 右侧面板包含 BOM 和 GUI 参数。
- 顶部状态栏只显示服务状态、LLM 状态和 CadQuery 状态。
- LLM 状态灯可点击，打开模型源配置面板。

LLM 状态表示模型源连通性或本轮调用状态，不表示 3D 模型是否已经生成。真实 3D 模型状态只在 3D 预览区域显示。

模型预览模式：

- 整体
- 爆炸
- 上盖
- 底壳
- 硬件

以上是普通盒体项目模式。`design_mode: "structural_part_project"` 时隐藏爆炸、上盖、底壳和硬件模式，改为：

- 整体预览
- 每个结构件的单项预览

结构件导出清单只把逐件 STL 列为可打印零件；并排整体预览不会混入打印清单。

爆炸视图当前规则是只抬高上盖，并让上盖半透明；底壳、硬件和其他零部件保持原装配位置。

当真实 CadQuery 导出可用时：

- “整体/上盖/底壳”优先加载对应真实 STL。
- “硬件”优先加载 `cadquery_hardware_stl`。
- “爆炸”优先用真实 `cadquery_base_stl`、`cadquery_lid_stl`、`cadquery_hardware_stl` 组成复合 STL 视图。

如果真实 CadQuery 导出缺失或失败，3D 预览区域会明确显示“暂无真实 3D 模型”或“模型加载失败”，并提示检查 CadQuery 生成和导出报告；前端不会把调试 glTF/STL 静默当作真实 3D 模型降级加载。2D 草案/调试预览是确认建模前的正式流程阶段，不等同于真实 3D 模型降级。

GUI 调参会调用 `/api/design/regenerate` 复用当前 taskId，并通过 `previewRevision` 给预览 URL 追加版本参数，避免同一任务目录覆盖文件后浏览器继续显示旧 STL/glTF。

## 硬件库与固定策略

硬件库位置：

```text
server/data/hardware-library.json
```

硬件参考模型位置：

```text
server/data/hardware-models/
```

`common` 硬件体系在界面和文档中统一称为“通用件”，前端按 `model_type` 显示两个二级分类和数量：

- `electronic_component`（电子元器件）：MG90S、PCA9685、方形锂电池。
- `structural_part`（结构件）：机器狗身体、机器狗大腿、机器狗小腿、18650 电池座。

`model_type` 不替代 `category` 或 `roles`。例如 18650 电池座仍保留 `power` 类别及 `battery` / `power` 角色，但作为结构件母版参与独立结构件流程。

独立结构件首版只支持上述通用件库现有母版，不支持从零生成任意自然语言结构，也不接受 custom profile。缺少有效 `cadquery_model` 时返回明确阻断，不使用电子板或包围盒代理。

用户也可以通过前端硬件库抽屉进入“用户自定义硬件”工作流，用自然语言描述电子器件或结构件，预览确认后永久写入 `user_custom` 硬件体系。

永久写入硬件库的新 profile 必须包含 `cadquery_model`，引用 `server/data/hardware-models/<hardware_id>.py`。这个 `.py` 文件只记录硬件自身的基础参考几何，不决定最终安装面、旋转或平移。`dimensions_mm.length_x/width_y/height_z` 是布局和碰撞使用的最大包围盒，真实预览参考形状以对应 CadQuery 模型文件为准。

硬件坐标规则：

- PCB 中心为原点。
- X 轴是 PCB 长度方向。
- Y 轴是 PCB 宽度方向。
- +Z 是正面或元件面。

固定策略由后端确定性规则决定：

- `xiao_esp*` 主控默认使用 `edge_retainer`，生成托台、侧向限位和端部挡块。
- 行空板体系默认主控为 `unihiker_k10`；该主控默认独立使用或插入 K10 IO 扩展板，不生成盒体固定结构。
- 其他有固定孔数据的显示器、传感器、按钮、蜂鸣器、执行器等硬件默认使用 `shell_through_screw_holes`。
- `external_independent_module` 表示独立外置硬件，只参与硬件库、BOM 和选型，不生成外壳安装结构、固定孔或开孔；当前用于行空板 K10 主控和 K10 IO 扩展板等模块。
- 螺丝孔默认按 M2 自攻螺丝贯穿孔处理。
- 固定孔优先读取 `mounting.holes[]`。
- 旧 profile 兼容读取 `legacy_reference.notes[id="mounting_holes_mm"].value.holes[]`。
- 孔径优先级是单孔 `diameter` / `diameter_mm`、profile 级 `hole_diameter` / `hole_diameter_mm`、默认 `2.1 mm`。
- 非 `xiao_esp*` 且需要螺丝固定的硬件如果没有固定孔数据，会返回 `needs_input`，不会估算孔位。

当前硬件库已包含一批行空板体系常用模块，例如 NFC、光线、运动、土壤湿度、按钮、温湿度、LED、RGB 灯环、声音、触摸、超声波、舵机、旋转角度、K10 IO 扩展板、K10 主控和直流电机风扇。

缺硬件或 profile 不完整时，后端会返回缺失项、需要补充的字段和 profile 模板。用户可补 profile 后继续，也可以砍掉、替换或忽略缺失功能。

## API

主要 API：

- `GET /api/health`：服务身份、端口、Python/CadQuery 依赖、LLM 连接状态、workflow tools、feature flags、源码指纹。
- `GET /api/model-sources`：读取模型源列表、当前 active source 和最近连接状态。
- `POST /api/model-sources`：新增或更新模型源；API key 只写入本地，不回传明文。
- `POST /api/model-sources/active`：切换当前模型源。
- `POST /api/model-sources/probe`：立即探测当前或指定模型源。
- `GET /api/hardware/library`：硬件库摘要；通用件 profile 会暴露 `model_type`、别名、模型质量和 `cadquery_model`。
- `POST /api/agent/prepare`：当前前端主入口；处理 route、需求分析、确认、修订、阻断选项和 2D 参数确认。
- `POST /api/agent/generate`：兼容旧的一步生成入口，不是当前前端主流程重点；命中智能浇花时同样先返回 `confirmation` 和 `layout_scene`，确认后再生成 artifact。
- `POST /api/design/build`：用户确认 2D 参数后，从 draft 生成最终 artifact。
- `POST /api/design/regenerate`：GUI 参数变化或已有 artifact 修改后重生成。
- `POST /api/design/validate`：对当前 `design_state` 重新校验。
- `POST /api/export`：按 `format`、`formats`、`id`、`ids`、`exportIds` 过滤导出项。
- `POST /api/cadquery/build`：运行 CadQuery，导出真实 STEP/STL，并把结果写回当前任务目录。
- `POST /api/self-check`：AI 接手自检，检查服务身份、LLM、关键特性、生成链路和导出项。

`/api/agent/prepare` 的典型阶段：

- 未确认需求分析：返回 `status: "requirement_analysis"`。
- 智能浇花模板命中：跳过 LLM 意图分析，但先返回锁定 BOM/布局的 `status: "confirmation"` 和 2D `layout_scene`；确认后才由 `/api/design/build` 生成真实 artifact。

批量小模型模板案例：

- `unihiker_light_effect_cup_v1` 光效水杯
- `unihiker_handheld_fan_v1` 手持小风扇
- `mpython_board_enclosure_v1` 掌控板外壳
- `unihiker_auto_open_lid_box_v1` 行空板自动感应开盖智能盒子

这些案例使用 `template_parts_v1` 契约。模板源码保存在 `server/template-library/batch-models/`，命中后复制到当前项目副本；可打印部件逐件导出 STEP/STL，硬件参考件和整体场景只用于预览，不会伪造普通盒体的底壳、上盖或硬件导出。
- 纯通用结构件请求：先返回 `status: "confirmation"` 和 `design_mode: "structural_part_project"`，确认后建立结构件 artifact。
- 用户确认分析后：返回 `status: "confirmation"`，进入 2D 参数确认。
- 缺硬件、profile 不完整、布局、校验、LLM 或 function verifier 阻断：返回 `status: "needs_input"`。
- 2D 草案确认建模由 `/api/design/build` 返回 `status: "artifact"`。

`/api/cadquery/build` 不会创建新任务目录。它使用 `artifact.design_state.id`，把真实 STL/STEP 写回同一个 `ZW-PRODUCT-*` 目录，并更新 `artifact.json`、`design-state.json`、`checks.json` 和 `workflow/08_export_manifest.json`。

## CadQuery 与 Python 环境

后端会检查 Python 环境中的：

- `cadquery`
- `OCP`
- `trimesh`
- `fastapi`
- `uvicorn`

如果 CadQuery 或 mesh 校验依赖缺失，系统仍可生成 2D/调试预览资产、workflow 产物和 CadQuery 代码文本；真实 STEP/STL 导出会标记为 pending 或 failed，不会伪造真实模型，也不会在前端静默切到简化 3D 模型。

建议项目专用 Python 环境：

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install cadquery OCP trimesh fastapi uvicorn
```

然后按实际环境设置：

```powershell
$env:ZW_CAD_INTENT_PYTHON="E:\GOODproject\ZhangWen\ZW-CAD-intent\.venv\Scripts\python.exe"
npm.cmd run dev
```

后端查找 Python 的顺序：

1. `ZW_CAD_INTENT_PYTHON`
2. `PYTHON`
3. `python`

## Custom Profile 最小示例

```json
{
  "id": "user_camera_module",
  "name": "用户提供摄像头模块",
  "category": "sensor",
  "roles": ["camera"],
  "dimensions_mm": {
    "length_x": 24,
    "width_y": 24,
    "height_z": 8
  },
  "coordinate_system": {
    "origin": "pcb_center",
    "x_axis": "board length",
    "y_axis": "board width",
    "positive_z": "lens side"
  },
  "mounting": {
    "mode": "screw_holes",
    "mating_hardware_face": "+Z",
    "preferred_enclosure_surface": "lid_inner",
    "clearance_mm": 0.8,
    "holes": [
      { "id": "hole_1", "x": -8, "y": -8, "diameter_mm": 2.1 },
      { "id": "hole_2", "x": 8, "y": -8, "diameter_mm": 2.1 },
      { "id": "hole_3", "x": -8, "y": 8, "diameter_mm": 2.1 },
      { "id": "hole_4", "x": 8, "y": 8, "diameter_mm": 2.1 }
    ]
  },
  "opening": [
    {
      "id": "lens_window",
      "type": "round_hole",
      "basis": "lens_center",
      "preferred_face": "top",
      "center_mm": { "x": 0, "y": 0, "z": 4 },
      "diameter_mm": 10,
      "clearance_mm": 0.8
    }
  ],
  "keepouts": [],
  "cad_reference": {
    "shape": "camera_pcb",
    "color": "#334455"
  },
  "source_status": "用户临时提供，未写入硬件库"
}
```

profile 尽量补齐：

- `dimensions_mm`
- `coordinate_system`
- `mounting`
- `mounting.holes[]`
- `opening`
- `opening.center_mm`：开孔中心相对硬件自身坐标系，按 PCB 中心原点、X/Y/Z 毫米坐标填写。
- `keepouts`
- `cad_reference`
- `source_status`

## 测试

```powershell
cd E:\GOODproject\ZhangWen\ZW-CAD-intent
npm.cmd test
```

等价命令：

```powershell
node --test server/*.test.js
```

重点测试：

```powershell
node --test server/model-sources.test.js server/model-source.test.js server/preview-ui.test.js server/pipeline.test.js
```

文档改动通常不需要跑完整测试；如果 README 中涉及 API、任务目录、workflow 产物或命令变化，建议跑一次 `npm.cmd test`。

## AI 接手检查

Codex 或其他 agent 接手时，建议先检查：

1. `GET /api/health`
   - `service_identity.project` 应为 `ZW-CAD-intent`。
   - 端口默认应为 `5187`。
   - 前端运行状态中的 service 显示应为 `ZW-CAD-intent : 5187`。
   - `feature_flags` 应包含 `conversation_route_v1`、`design_revision_v1`、`workflow_orchestration_v1`、`standalone_structural_parts_v1`。
   - `workflow_tools` 应列出全部内部 tools。
   - `llmConnection.status` 应为 `connected`、`failed`、`not_configured` 或 `checking/unknown` 语义之一。
   - `source_fingerprint` 应能反映关键源码文件 hash/mtime。

2. 模型源
   - 右上角 LLM 状态灯应可点击并打开模型源面板。
   - `GET /api/model-sources` 不应泄露明文 API key。
   - `server/data/model-sources.local.json` 优先级高于 `.env.local`。

3. 生成结果
   - `artifact.generation_trace` 和 `design_state.generation_trace` 应存在。
   - `workflow/00_requirement_analysis.json` 应记录用户原始需求、route 和 revision 摘要。
   - `workflow/05_layout_plan.json` 应能看到硬件、开孔、固定结构和固定孔位置。
   - `workflow/06_checks.json` 应能定位干涉、壁厚、开孔对齐、固定结构等问题。

4. 前端状态
   - 顶部应显示服务状态、LLM 状态和 CadQuery 状态，不再显示“模型源：暂无模型”这类 3D 预览状态。
   - 新任务后旧 3D 预览、硬件选择、草案、artifact 和阻断状态应清空。
   - 需求分析阶段不应显示旧模型残影。
   - 2D 草案阶段输入“继续建模”应进入 `/api/design/build`，不应回到缺失硬件循环。

5. 缺失硬件与修订路径
   - 缺硬件时应出现可恢复选项。
   - “忽略缺失功能继续”应保留库内可满足硬件并继续生成。
   - 用户提出“把 A 改成 B / 移到底壳 / 删除某功能”时应进入 `design_revision` 路径。

6. 通用件与独立结构件
   - 硬件库界面应显示“通用件”，并区分“电子元器件”和“结构件”。
   - 纯结构件单选、多选和自然语言点名不应产生 controller、XIAO fallback、底壳或上盖。
   - 结构件整体预览按 15 mm 间距并排且不可打印；逐件 STEP/STL 应能单独选择和校验。
   - 提到“盒子/外壳”或混选电子元器件时，不应进入 `standalone_structural_parts`。
