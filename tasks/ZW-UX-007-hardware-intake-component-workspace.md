# ZW-UX-007 — 项目硬件前置选择与器件项目浮窗

状态：实现完成，自动回归与三档隔离浏览器 UI 验收通过；待用户桌面真人验收（2026-07-14，未提交）

## 1. 目标

1. 新建项目时先提供可搜索的“已有硬件（可选）”选择器；用户选择的硬件成为后续路由、澄清和方案生成的已确认上下文，掌问只推荐缺少的器件。
2. 把硬件选择放在点击“分析并推荐”之前，但不把它伪装成第一张必答 LLM 澄清卡；空选择明确表示“由掌问按需求推荐”。
3. 把公共知识中的器件编辑从概览/单表单升级为现有浮窗体系内的器件项目编辑器，提供受控文件夹树、Markdown 文件选择、编辑、放弃修改、保存和 revision 冲突保护。
4. 让三位工程师读取同一份已选硬件事实和已保存器件 Markdown，不建立平行项目模型，不重写 `AppShell`。

## 2. 不可变边界

- 中央 `CenterChat` 始终保持单实例挂载；打开设置、硬件选择器或器件浮窗不得丢失草稿、滚动、附件和引用。
- 右侧一级 Tab 固定为“工作 / 产物 / 设备”，器件编辑器不新增页面、路由或一级 Tab。
- 用户所选硬件是“优先使用的现有器件”，不是最终 BOM；方案仍可补充缺口，但不得重复推荐已选器件。
- `/api/projects/suggest` 与 `/api/projects` 都由 Sidecar 重新校验组件存在且为 `ACTIVE`；不能信任客户端名称、参数或旧建议结果。
- 硬件选择变化与创意文本变化同样使旧分析失效；未经重新分析不得创建项目。
- 器件文件只允许受控包内相对路径、UTF-8 Markdown 和有限大小；保存使用整体 revision compare-and-swap，冲突时保留本地草稿。
- 云端 LLM 不直接读写文件；本地 Sidecar 读取受控器件包并向模型提供有界上下文。
- 不改 `CURRENT_TASK.md`，不覆盖 `ZW-UX-003`、`ZW-UX-005`、`ZW-UX-006`、`ZW-AGENT-006`、`ZW-PKG-001`、K10/CAD 等并行修改。
- 不调用真实付费 LLM，不扫描或连接串口，不上传代码，不重启设备，不执行 Flash 擦除或固件烧录。

## 3. 交互与领域决策

### 3.1 创建阶段“步骤 0”

- `ProjectCreationDialog` 最先显示“步骤 0 · 选择已有硬件（可选）”，支持搜索、多选、清空和明确跳过。
- 点击“分析并推荐”时发送 `selectedHardwareIds`；按钮加载期间禁止修改选择或并发提交。
- 修改任一选择后清空 `routerResult`、推荐名称和专家选择，并要求“重新分析并推荐”。
- 已选择硬件时，EntryRouter 只收到 Sidecar 根据 ACTIVE 组件生成的受控摘要；可见 kickoff 仍只包含用户创意，不插入隐藏 JSON 或第二条用户消息。
- 创建项目时在同一事务内写入一条 `confirmed` 的 `preferred_hardware` SharedFact，并记录组件 ID、名称、类别与保存时更新时间快照。
- 已选硬件在后续上下文中优先于关键词命中的公共知识；提示明确要求复用这些器件并只补齐功能缺口。

### 3.2 后续澄清与推荐

- 已选器件足够时不再询问“准备使用什么硬件”。
- 未选择、选择不完整或本地兼容性校验阻塞时，首轮澄清才询问硬件约束；动态库选择仍由本地选择器负责，不让 Provider 自由生成 component ID。
- 方案中的硬件建议必须排除已选 ID，并把已选器件标为“用户已有”；本轮不新增第二套 BOM 或推荐持久化模型。

### 3.3 器件项目浮窗

- 公共知识列表保留“查看”，把编辑入口改为“编辑器件项目”；点击后关闭设置覆盖层并打开现有浮窗。
- 浮窗使用单例 key `hardware-component:{componentId}`，遵守最多三个浮窗与窄屏自动收起右栏规则。
- 左侧展示标准 Markdown 文件树，右侧使用现有 Monaco 编辑器；支持文件切换、保存、放弃修改、加载/错误/成功状态。
- 首期标准文件为 `README.md`、`docs/specifications.md`、`docs/integration.md`、`docs/safety.md`；路径集合由 Sidecar 固定，不支持任意创建、重命名或删除。
- 内置内容从组件结构化字段生成，用户修改写入数据目录 overlay；DB 中的电气和兼容性字段继续作为规则引擎真值，Markdown 不能扩大权限或改写安全校验。
- 三师公共知识读取有效 Markdown overlay；未保存草稿不会进入下一次回复。

## 4. API / 契约

- `SuggestProjectRequest.selectedHardwareIds?: string[]`
- `CreateProjectRequest.selectedHardwareIds?: string[]`
- `HardwareComponentPackageFile`
- `HardwareComponentPackageDetail`
- `HardwareComponentPackageResponse`
- `UpdateHardwareComponentPackageFileRequest`
- `GET /api/hardware/components/{componentId}/package`
- `PUT /api/hardware/components/{componentId}/package/files`
- `SuggestProjectResponse.suggestion.selectedHardwareWarnings?: string[]`（Python 响应当前始终返回数组）
- `FloatingWindowKind.HARDWARE_COMPONENT = "hardware-component"`
- 非法、重复或超过上限的选择由请求边界返回 422；未知、归档或 Rule Engine FAIL 返回 `422 PROJECT_VALIDATION_FAILED`；revision 冲突返回 `409 HARDWARE_COMPONENT_PACKAGE_CONFLICT`。
- 单个 Markdown 文件最多 40,000 字符，整包最多 100,000 字符；只有保存成功的有效 overlay 会进入三师上下文。

## 5. 可观察验收

- [x] 空选择不会阻止分析或创建，且请求体明确携带空数组。
- [x] 选择硬件后 suggest/create 请求均携带相同 ID；修改选择会使旧推荐失效。
- [x] 未知或 `ARCHIVED` 组件不能进入项目；创建事务失败不留下半个项目或半条事实。
- [x] kickoff 仍只有原始用户创意；三师在后续不重复提及器件名称时仍能读取相同的已选参数。
- [x] 方案生成上下文明确要求复用已选器件并只补推荐缺口；自动测试验证提示约束，真实云端回答仍待桌面真人抽检。
- [x] 设置与项目工具中的“编辑器件项目”打开同一浮窗；文件树可选四个 Markdown，保存后刷新 revision，放弃恢复服务端内容。
- [x] revision 冲突保留当前编辑草稿并加载最新 revision；读取失败可保稿重试，不静默覆盖其他保存。
- [x] `390x844`、`720x720`、`1280x720` 保持单一 `main`、固定三 Tab、中央草稿与零页面级横向溢出。
- [x] 自动测试不调用真实 LLM、串口、设备或 Flash。

## 6. 实施步骤

- [x] M1：审计创建/kickoff/上下文/硬件库/浮窗调用链，确定步骤 0 与受控器件包边界。
- [x] M2：shared contracts、Python 边界模型与失败用例先行。
- [x] M3：实现 ACTIVE 选择校验、项目 confirmed fact、上下文优先级和缺口提示。
- [x] M4：实现受控器件 Markdown 包仓储与 HTTP API。
- [x] M5：实现创建硬件选择器与器件浮窗编辑器。
- [x] M6：完成前后端回归、UI Contract 三档验收、文档与 HANDOFF 收尾。

## 7. Decision Log

- 2026-07-14：硬件选择属于创建阶段“步骤 0”，不是第一张必答 LLM 澄清题。动态硬件库需要搜索、稳定 component ID 和本地状态校验，不能塞进 Provider 所有的有限选项卡。
- 2026-07-14：请求字段使用 `selectedHardwareIds`；项目事实语义为 `preferred_hardware`，表示优先复用而非冻结最终 BOM。
- 2026-07-14：首期不新增 `project_hardware_items` 或第二套 BOM 表；在创建事务内写 confirmed SharedFact，并由统一上下文装配器精确加载组件。
- 2026-07-14：器件项目采用固定四文件 Markdown 包与数据目录 overlay；结构化电气/兼容性字段仍由现有组件 CRUD 和规则引擎维护。
- 2026-07-14：编辑器复用既有浮窗/Monaco/整体 revision 模式；不在设置弹窗内嵌第二个工作台。

## 8. Progress

- 2026-07-14：M1 完成。已复核 `ProjectCreationDialog -> /projects/suggest -> EntryRouter`、`/projects -> repository transaction -> kickoff -> CenterChat`、三师 ContextAssembler、HardwareLibrary 和 FloatingWindow；确认等到首张澄清卡再选硬件会错过路由与首次上下文。
- 2026-07-14：M2 开始。先增加共享请求/器件包契约和失败测试，再修改前后端实现。
- 2026-07-14：M2/M3 完成。`selectedHardwareIds` 已贯通 suggest/create；Sidecar 在 Provider/写库前复核 ACTIVE 状态和 Rule Engine，FAIL 返回 422，WARNING 继续。创建事务写 confirmed `preferred_hardware`（固定 `prefer_selected_and_fill_gaps` policy），幂等重放不重复；kickoff 仍只有原始创意。
- 2026-07-14：M4 完成。新增固定四文件的器件 Markdown 包、数据目录 overlay、UTF-8/白名单/大小/符号链接边界、原子写入和整体 revision CAS；相关与已选器件都以总计不超过 16,000 字符的有效 Markdown 进入三师公共知识。
- 2026-07-14：M5 完成。创建覆盖层新增可搜索、多选、可跳过的硬件步骤 0；选择变化使旧分析失效。公共知识“编辑项目”打开现有单例浮窗，左侧文件树、右侧 Monaco，支持保存、放弃和 409 自动加载最新 revision 且保留草稿。
- 2026-07-14：M6 收口修复完成：补结构化 Rule Engine 中文提醒、步骤 0“清空选择”、项目工具统一浮窗入口、未保存 Markdown 关闭/淘汰保护、最小化草稿保持、保存竞态锁定和 409 刷新重试。
- 2026-07-14：最终自动验证通过：contracts build、desktop strict typecheck、desktop production build；前端定向 `8 files / 89 tests`，后端硬件/项目链路 `57 passed`，项目聊天回归 `10 passed`。生产构建只保留既有 Monaco 大 chunk 警告。
- 2026-07-14：扩大后端组合为 `74 passed / 3 failed`。两项失败来自 `test_three_expert_runtime.py` 中既有乱码 K10 测试文本，一项来自并行 K10 Board Skill 目录文件未列入 `CHECKSUMS.sha256`；未在本任务中越界修改。
- 2026-07-14：隔离浏览器三档 UI Contract 验收通过。`1280x720` 覆盖步骤 0、清空、选择变化使旧推荐失效、中文硬件提醒和器件浮窗；`720x720` 浮窗约 `704x656`、树与编辑器并列；`390x844` 文件树位于编辑器上方且操作可达。三档均无页面级横向溢出，只有一个 `main`，右侧一级 Tab 固定为“工作 / 产物 / 设备”，中央草稿保持。
- 2026-07-14：相关 Python `py_compile`、全工作树 `git diff --check` 通过；本地 Fake Provider 开发页 `http://127.0.0.1:5173` 与 Sidecar `http://127.0.0.1:8100/api/health` 均返回 HTTP 200。

## 9. Safety

- 不运行 `git reset --hard`、`git clean`、整库 stash、`git add -A`、强制推送或公开发布。
- 不把 API Key、串口标识、绝对路径、命令、工具输入输出或模型推理写入器件 Markdown、日志、测试或 Git。
- 不执行真实硬件发现、串口连接、上传、重启、Flash 擦除或固件烧录。
