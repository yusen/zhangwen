# ZW-UX-008 — 分析后项目硬件选择与缺件补充

状态：实现完成且自动与三档 UI 验收通过（2026-07-15，未提交；真人桌面抽检待用户）

## 1. 目标

1. 新建项目先提交创意并完成“分析并推荐”，随后才显示“选择项目硬件”按钮。
2. 点击按钮打开本地器件选择器，以分类筛选、搜索、卡片网格、已选计数和明确确认完成选择；开始项目时
   将选择持久化为项目硬件事实。
3. 项目内三师始终读取当前已确认硬件；规划发现缺少器件时返回结构化“硬件待补充”提醒，用户可从
   中央消息直接打开同一选择器并把器件加入项目。
4. 项目工具保留主动管理项目硬件的入口，不要求用户等待模型再次提醒。

## 2. 已确认现状与差距

- `ProjectCreationDialog` 当前在创意输入前展示“步骤 0”，并把选择传给 `/projects/suggest`；选择变化会
  清空推荐并要求重新分析，与用户指定顺序相反。
- 创建事务已经把 `selectedHardwareIds` 固化为 confirmed `preferred_hardware`；三师
  `ContextAssembler` 每轮按最新 confirmed 事实加载并标记 `selectedByUser`。
- 项目创建后没有修改 `preferred_hardware` 的 API；项目工具中的硬件库只能查看/编辑公共知识，不能把
  器件加入当前项目。
- ExpertRuntime 只有 clarification 和本地产物投影，没有受控的“打开硬件选择器”响应类型。
- `HardwareComponent` 没有可信图片字段。本任务复用用户参考图的信息架构和选择交互，不生成或伪造
  商品图片；卡片只显示库中真实名称、类别、电压、协议、库存和说明。

## 3. 不可变边界

- `CenterChat` 始终单实例挂载；打开/关闭选择器不得丢失草稿、滚动、附件、引用或当前专家。
- 右侧一级 Tab 仍固定“工作 / 产物 / 设备”；选择器使用现有覆盖层，不新增页面或一级 Tab。
- Provider 只能声明缺少的能力名称，不得生成或选择 component ID；ACTIVE 状态、组合安全和事实写入
  始终由 Sidecar 校验。
- 硬件更新采用完整选择快照并在单一 SQLite 事务中 supersede 旧 confirmed 事实；失败不能留下半状态。
- 最多选择 12 项；未知、归档或 Rule Engine FAIL 必须拒绝，WARNING 以中文文字展示。
- 不修改 `CURRENT_TASK.md`，不覆盖并行 ZW-AGENT/ZW-HW/ZW-LLM/CAD/安装包改动，不创建 ZW-017。
- 不调用真实付费 LLM，不扫描/连接串口，不上传代码，不重启设备，不执行 Flash 擦除或固件烧录。

## 4. 契约与交互

### 4.1 创建阶段

- `/projects/suggest` 保留 `selectedHardwareIds` 兼容旧客户端，但新桌面分析请求不再携带预选硬件。
- 推荐成功后显示“选择项目硬件”；未选择时明确显示“尚未选择，可由智能体规划后再补充”。
- 硬件选择不会使已完成的创意/专家分析失效；只有创意变化才要求重新分析。
- `/projects` 创建请求继续携带当前 `selectedHardwareIds`，Sidecar 在写库前重新校验。

### 4.2 项目硬件更新

- 新增 `UpdateProjectHardwareRequest { selectedHardwareIds: string[] }`。
- 新增 `PUT /api/projects/{projectId}/hardware`，返回 `{ workspace, selectedHardwareWarnings }`。
- 新事实使用 `field/key=preferred_hardware`、`status=confirmed`、`confirmedBy=user`，旧 confirmed 事实
  在同一事务中标记 `superseded` 并指向新事实。

### 4.3 三师缺件动作

- 新增 `ConversationResponseType.HARDWARE_SELECTION = "hardware_selection"`。
- Provider payload 只允许 `summary`、1-8 个 `missingCapabilities`；不得包含硬件 ID、文件、命令或工具。
- 中央消息显示缺少能力清单与“选择并添加电子器件”按钮；点击打开当前项目选择器，不发送第二条聊天。
- 项目工具提供“管理项目硬件”按钮，复用同一选择器。

## 5. 实施里程碑

- [x] M1：先补共享契约、创建顺序、项目硬件事务和 Runtime 缺件 payload 失败回归。
- [x] M2：实现后端更新接口、最新事实替换和三师受控 payload。
- [x] M3：实现复用选择器、创建后置按钮、中央提醒卡和项目工具入口。
- [x] M4：运行 contracts/typecheck、前后端定向与相关回归。
- [x] M5：按 UI Contract 验收 390/720/1280，更新文档与 HANDOFF。

## 6. Decision Log

- 2026-07-15：硬件选择改为分析后的独立本地确认步骤，不再参与入口路由；创建时仍参与 Sidecar 安全校验
  和后续三师上下文。
- 2026-07-15：项目内硬件使用完整快照替换而不是仅追加，便于用户纠正误选；所有旧事实保留 superseded
  审计记录。
- 2026-07-15：缺件由 Provider 以能力名称表达，本地选择器负责稳定 ID 和 ACTIVE/Rule Engine 校验。
- 2026-07-15：现有数据没有可信图片字段，因此首期用类别视觉标识承载卡片图片区，不引入网络图片、
  假商品图或第二套素材模型。

## 7. Progress

- 2026-07-15：完成只读审计，确认创建顺序、项目后更新接口和三师缺件动作三处差距；M1 开始。
- 2026-07-15：先写失败回归，确认项目硬件更新 API 为 404、Runtime 不接受 `hardware_selection`、
  三师提示词缺少受控缺件规则、桌面仍在分析前选硬件且没有中央缺件卡。
- 2026-07-15：M1-M3 完成。桌面改为分析完成后打开复用器件网格；创建和项目内更新均由 Sidecar
  重新校验 ACTIVE Hardware Skill/Rule Engine。项目更新在单一事务中 supersede 旧 confirmed
  `preferred_hardware` 并写入新事实；三师可返回只含能力名称的 `hardware_selection`，中央卡和项目工具
  均打开同一本地选择器。
- 2026-07-15：M4 完成。contracts build、desktop strict typecheck/production build、50 项 Runtime/项目硬件回归、
  10 项聊天流、11 项 Hardware Skill 上下文和 7 个桌面测试文件共 83 项均通过；4 个相关 Python
  源文件内存编译通过。测试仅使用 fake provider 和本地数据。
- 2026-07-15：M5 完成。隔离浏览器确认分析前不存在硬件按钮、分析成功后出现“选择项目硬件”；
  `1280x720`、`720x720`、`390x844` 分别为 4/2/1 列，均无页面级横向溢出、只有一个 `main`，
  右侧一级 Tab 固定“工作 / 产物 / 设备”。实际加入 ESP32-S3 与 BME280 后，服务端保存并显示缺少
  供电模块的中文 WARNING；隔离服务、浏览器页和测试数据已清理。
