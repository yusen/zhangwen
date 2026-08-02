# ZW-UX-005 — 显式项目推荐、按项目增补工程师与共享知识库

状态：实现完成，定向自动验证通过，真人验收待用户（2026-07-14）

## 1. 目标

1. 新建项目时不再根据输入停顿自动调用模型；用户完成思考和输入后，显式点击按钮分析并获得项目名、初始工程师和参与工程师推荐。
2. 项目创建后允许从当前项目对话按需加入尚未参与的问题引导师、智能工程师或结构工程师；新增工程师只属于当前项目，并拥有独立线程和私有记忆。
3. 三位工程师继续读取同一套公共工程知识；专家行为文件和私有记忆仍保持隔离。
4. 完善“设置 → 公共知识”的组件知识添加、搜索和详情查看，使用户可以确认模型实际可读取的知识内容。

## 2. 非目标

- 不新增第四位用户可见专家，不暴露 EntryRouter 或 ProjectCoordinator。
- 不合并三位工程师的 ConversationThread、私有草稿或私有记忆。
- 不新增右侧一级 Tab，不卸载中央 `CenterChat`。
- 不新增通用文档向量库、远程知识服务或数据库 migration；本轮复用全局硬件组件、开发板档案和机械档案。
- 不修改或混入并行 `ZW-AGENT-006`、`ZW-PKG-001`、`ZW-UX-003` 用户改动。
- 不运行真实付费 LLM、真实串口、Flash 擦除或固件烧录。

## 3. 当前基线

- `ProjectCreationDialog` 当前在输入变化后等待约 250ms 自动调用 `/api/projects/suggest`，用户尚未完成描述时可能得到过早推荐。
- `ProjectRepository.add_project_expert()`、项目专家 HTTP API、桌面 `useProjects.addExpert()` 已存在，并支持创建或恢复当前项目的独立专家工作区；当前 UI 未暴露入口。
- `ContextAssembler.publicKnowledge` 已对三位工程师统一读取全局硬件组件与匹配的 BoardProfile，并已有三师一致性测试。
- “设置 → 公共知识”已有组件新增、编辑、归档、开发板档案和机械档案，但组件列表缺少明确详情入口，新增表单未暴露模型已支持的安全标签、适龄、I2C、驱动、固件和兼容主控字段。

## 4. 交互与契约设计

### 4.1 显式分析并推荐

- 创意输入只更新本地草稿，不触发网络请求。
- 用户点击“分析并推荐”后才调用 `/api/projects/suggest`。
- 请求期间按钮显示“正在分析…”，禁止并发重复调用。
- 分析成功后显示项目名称、推荐参与工程师、初始工程师和可理解的推荐原因。
- 分析完成后修改创意会立即使旧推荐失效；必须再次点击“重新分析并推荐”才能创建项目。
- 建议失败不生成本地替代结果，保留输入并提供显式重试。

### 4.2 按项目增补工程师

- 输入区工程师胶囊末尾在仍有缺失工程师时显示“＋ 添加工程师”。
- 展开后只列出当前项目尚未参与的 canonical 三师成员。
- 点击成员调用现有 `POST /api/projects/{projectId}/experts`，`activate=true`；成功后刷新工作区并直接把下一条回复目标切到新增工程师。
- 添加期间锁定重复操作；失败保留面板并显示可恢复错误。
- 新增工程师不复制完整聊天，只读取必要公共知识、confirmed facts、决策和相关产物。

### 4.3 共享公共知识

- 公共知识是全局工程知识源，不按项目专家复制；问题引导师、智能工程师和结构工程师使用同一条目 revision。
- Agent Skill 行为文件、专家线程、私有草稿和私有记忆不属于公共知识。
- 组件知识、BoardProfile 和机械档案继续作为不同专业视图；普通模式只开放组件知识，专业模式按需开放开发板和机械档案。

### 4.4 知识添加与查看

- 公共知识页明确显示“三位工程师共享”。
- 组件列表提供“查看”和“编辑”动作；查看区显示名称、分类、电气参数、协议、I2C、兼容主控、驱动、固件、库存、价格、适龄、安全标签、说明和更新时间。
- 新增/编辑表单补齐上述可编辑字段，空可选字段按契约提交为 `null` 或空数组。
- 搜索同时匹配名称、说明、电气/协议与安全标签；创建或编辑成功后刷新列表并打开最新详情。

## 5. 里程碑

### M1：任务与显式推荐

- 更新项目创建组件及测试，移除输入 debounce 网络调用。
- 固化旧推荐失效和显式重试行为。

### M2：项目工程师增补

- 在中央输入区增加缺失工程师入口。
- 接通 `AppShell -> CenterChat -> ChatInput -> useProjects.addExpert`。
- 覆盖添加成功、激活目标、失败和无缺失成员时隐藏入口。

### M3：共享知识库 UX

- 完善组件添加字段、详情查看和搜索。
- 保持三师共享 ContextAssembler 语义，并补必要回归。

### M4：文档、验证与交接

- 同步 PRD、API、架构、UI 契约、Decision Log、任务和 HANDOFF。
- 运行 contracts/desktop/backend 定向测试、类型检查和 `git diff --check`；真实 LLM 与真人 UI 仍由用户验收。

## 6. 验收标准

- 仅输入创意且未点击按钮时，前端不会请求 `/api/projects/suggest`。
- 点击“分析并推荐”只发出一次请求；成功前“开始项目”保持禁用。
- 修改已分析创意后旧推荐立即失效，不能用旧路由创建项目。
- 单专家项目可在中央输入区加入其余任一工程师；新增成员出现为胶囊并成为下一条回复目标。
- 三位工程师读取同一条新增/编辑公共知识，且不共享完整聊天和私有记忆。
- 用户可以新增完整组件知识、搜索条目、打开详情、编辑后看到最新内容。
- 中央对话保持单一挂载，右侧一级 Tab 仍只有“工作 / 产物 / 设备”。

## 7. Progress

- 2026-07-14：完成实际仓库审计。确认项目专家增补后端/API/hook 已存在，公共知识已在 ContextAssembler 中三师共享；本轮聚焦显式项目推荐、增补入口和知识库查看/添加 UX。
- 2026-07-14：M1 完成。项目创意输入不再 debounce 调用 Provider；“分析并推荐”是唯一建议触发器，请求中防重复，输入变更用 request sequence 丢弃旧响应并使旧推荐失效。
- 2026-07-14：M2 完成。输入区在存在未参与三师成员时显示“＋ 添加工程师”，复用项目专家 add/restore API，成功后激活新增独立线程；全部三师已加入后入口自动隐藏。
- 2026-07-14：M3 完成。公共知识页明确三师共享，组件知识增加完整添加/编辑字段、列表查看按钮、双栏详情、响应式单列、状态反馈和名称/说明/电气/协议/安全标签搜索；异步列表请求使用 sequence 防止旧响应覆盖新筛选。
- 2026-07-14：M4 完成。PRD、API、架构、当前基线、UI 契约和 Decision Log 已同步；定向自动验证通过，真人布局与真实 Provider 推荐待用户验收。

## 8. Decision Log

- 2026-07-14：使用用户定向任务 `ZW-UX-005`，不创建禁止的 `ZW-017`。
- 2026-07-14：将“临时添加工程师”解释为“按当前项目按需加入”，成员及线程持久化以支持项目重开；不创建跨项目全局专家实例。
- 2026-07-14：公共知识继续以现有全局工程硬件知识为边界，不在本轮引入通用 RAG 或新 schema。

## 9. 预计修改范围

- Desktop：`ProjectCreationDialog.tsx`、`AppShell.tsx`、`CenterChat.tsx`、`ChatInput.tsx`、`HardwareLibrary.tsx`、`SettingsDialog.tsx`、`App.css` 和定向测试。
- Backend：`hardware/repository.py` 的公共知识搜索及定向测试；项目专家 API 只复用，不重写。
- Docs：`PLANS.md`、`docs/PRD.md`、`docs/API_EVENTS.md`、`docs/ARCHITECTURE.md`、`docs/UI_CONTRACT.md`、`docs/DECISIONS.md`、`HANDOFF.md`。

## 10. 验证命令

- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/desktop exec vitest run src/__tests__/ProjectWorkspace.test.tsx src/__tests__/ProjectIsolation.test.tsx src/__tests__/UnifiedProjectConversation.test.tsx`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py services/local-api/tests/test_three_expert_runtime.py services/local-api/tests/test_zw005_hardware_crud.py -q --rootdir services/local-api`
- `git diff --check`

## 11. Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `ProjectWorkspace.test.tsx` 本轮相关 5 项：通过；覆盖无自动 suggest、显式分析、旧推荐失效、手工名称/专家保持、失败边界。
- `ProjectIsolation.test.tsx`：`4 passed`；包含项目创建后添加结构工程师、激活新线程和 `CenterChat` 单实例。
- `PublicKnowledgeLibrary.test.tsx`：`1 passed`；覆盖完整详情、公共知识添加字段、三师共享提示和搜索请求。
- `UnifiedProjectConversation.test.tsx`：`3 passed`；设置覆盖层、公共知识入口和中央对话单实例通过。
- `RightPanel.test.tsx` UI 契约定向 3 项：通过；工作/产物/设备切换、浮窗和草稿保持不卸载中央对话。
- `test_zw005_hardware_crud.py`：`14 passed`；包含说明、电气 JSON 和安全标签搜索。
- `test_three_expert_runtime.py -k public_hardware_knowledge`：`3 passed`；三位工程师读取相同新增/编辑知识。
- `test_project_repository.py -k "add_and_remove_project_expert or remove_project_expert_requires_one_remaining_expert"`：`2 passed`。
- `git diff --check`：通过，仅有 Windows LF -> CRLF 提示。

未归因到本任务的并行工作树结果：

- `ProjectWorkspace.test.tsx` 全文件为 `14 passed / 1 failed`；失败仅为并行 `services/api.ts` 已把旧“本地后端未连接”文案改成“掌问本地服务未连接”，旧断言未同步。
- 三个后端文件合并运行时为 `37 passed / 3 failed`；失败来自并行修改的 K10 Board Skill 文件与 `CHECKSUMS.sha256` 不一致，导致 BoardProfile/Skill 校验失败。本任务未修改或覆盖这些文件。

## 12. 真人验收与剩余工作

- 在新建项目覆盖层持续输入和停顿，确认网络不自动请求；完成输入后点击“分析并推荐”，检查推荐名称和工程师。
- 分析后修改任一创意字符，确认旧推荐隐藏且“开始项目”禁用；重新分析后才能创建。
- 创建仅含问题引导师的项目，从输入区添加智能工程师和结构工程师，确认新胶囊出现并直接成为回复目标；重开项目后成员仍存在。
- 在设置公共知识中添加带 I2C、兼容主控、安全标签和说明的组件，搜索并打开详情；分别向三位工程师询问同一组件，确认都使用最新知识但不串用完整聊天。
- 在 `390x844`、`720x720`、`1280x720` 检查工程师面板、知识表单和详情无重叠、无页面横向溢出。
