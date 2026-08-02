# ZW-LLM-004 — 生成失败诊断与对话恢复

状态：实现完成且自动验收通过；重启后真人桌面抽检待用户（2026-07-17）

## 1. 目标

让 `LOCAL_OUTPUT_REJECTED`、`LLM_OUTPUT_INVALID` 和应用重启后遗留的生成中断都成为可解释、可操作、
不阻断对话的恢复状态。失败消息必须说明常见原因，提供适合该错误的按钮，并在原项目、原专家、原需求
上下文中继续；修改需求时把原需求恢复到输入框而不是要求用户重新输入。

## 2. 真实诊断基线

2026-07-17 对本机最近 200 条失败运行只读统计：

- 19 条失败 `expert_runs`；消息错误码为 `LLM_OUTPUT_INVALID=10`、`LOCAL_OUTPUT_REJECTED=5`、
  `UNKNOWN=2`、`CANCELED=2`、`NETWORK_UNAVAILABLE=1`。
- 最近 5 条结构工程师本地拒绝中，4 条是完整自由结构请求未返回
  `FREEFORM_STRUCTURE.geometry`，1 条是非 CAD intake 返回 CAD 输出。
- 智能工程师旧失败主要来自写模式 `open()`、硬编码凭据、主机文件调用和未引用已选 Hardware Skill；
  这些确定性本地拒绝在 ZW-LLM-003 已改为独立错误码，旧数据库记录仍保留历史分类。
- 中断消息由启动时把遗留 `STREAMING` 归一化为 `FAILED` 产生；后端已写 `userActions`，但中央对话此前
  只显示文字，未渲染普通失败消息的动作，这是“对话卡住”的直接 UI 根因。

## 3. 产品与安全边界

- 不把无效 Provider 输出持久化为业务产物，不用本地模板伪装云端成功，也不增加无上限自动重试。
- 自由结构改用专用 `DeclarativeGeometry` 结构化生成，再由本地服务封装为 CAD 草稿；几何仍来自真实
  Provider，最多一次修复重试，仍经过 Pydantic、CAD intake 和 Worker 边界。
- “重新生成”创建一个明确的新恢复轮次，沿用原项目、原专家和原用户文本；UI 用恢复事件标识，不重复
  显示一整条用户需求。“修改原需求”只恢复草稿并聚焦输入框，不自动发送。
- 错误提示只公开受控分类和解决建议，不公开 Provider 原文、内部路径、凭据或敏感诊断。
- 中央 `CenterChat` 始终单实例；恢复动作不清空附件/引用/草稿，不新增右侧一级 Tab。

## 4. 计划

1. 为自由结构增加专用受控几何编译路径，消除通用大 Schema 经常漏掉 geometry 的根因。
2. 增加 `GENERATION_INTERRUPTED` 错误码，并为三类错误返回不同 `userActions`。
3. 中央失败卡显示“原因与建议”，消费 `retry/revise_request/open_settings` 动作。
4. 新恢复轮次精确复用失败消息对应的原用户内容和专家；修改动作恢复原文到草稿。
5. 覆盖自由结构生成、错误映射、启动中断、三类按钮、草稿/专家/单实例/三 Tab 回归。

## 5. 验收标准

- `FREEFORM_STRUCTURE` 完整描述不再依赖模型填充整个 `ExpertRuntimeOutput`，专用几何 Schema 成功后必有
  `cadDraft.geometry`；无效几何仍明确失败。
- 三类错误都显示原因、解决建议和至少一个可执行按钮；按钮文本不能只有模糊的“重试”。
- 点击重新生成后原失败卡保留，新轮次进入同一专家；点击修改需求后原文进入输入框且不自动请求。
- 应用重启后的中断消息使用明确错误码和“继续生成 / 修改原需求”，不再停在一行死提示。
- UI 回归确认中央对话单实例、草稿保留以及右侧“工作 / 产物 / 设备”不变。

## 6. Decision Log

- 2026-07-17：失败恢复由后端 `userActions` 决定，前端只对受控动作 ID 执行白名单行为。
- 2026-07-17：重试是新轮次而非复活旧流，避免重复领取旧请求或重放已提交的澄清事务。
- 2026-07-17：自由结构使用只含声明式几何的小 Schema，再由本地封装公共专家输出；其他专家和 CAD
  类型继续使用既有公共契约，不把该路径扩大为确定性内容 fallback。

## 7. 实现结果

- 新增 `FreeformGeometryCompiler`，以最多一次修复生成受控 `DeclarativeGeometry`；完整
  `FREEFORM_STRUCTURE` intake 不再依赖 Provider 同时填写整个 `ExpertRuntimeOutput.cadDraft.geometry`。
- Python/TypeScript 契约新增 `GENERATION_INTERRUPTED`；启动归一化、三类错误文案和 `userActions`
  已分层。
- `CenterChat` 新增失败恢复卡、具体原因/建议、按钮白名单、原消息定位、草稿回填和同专家恢复 turn；
  历史中断错误继续兼容。
- `recoveryOfMessageId/recoveryLabel` 从桌面请求写入 Sidecar 用户消息元数据，重载后仍能显示恢复事件。
- UI、API、架构、baseline、PRD 和决策记录已同步。

## 8. 改动文件

- 实现：`services/local-api/zhangwen/cad_agent/freeform_geometry.py`、
  `services/local-api/zhangwen/experts/runtime.py`、`services/local-api/zhangwen/llm/{contracts,errors}.py`、
  `services/local-api/zhangwen/projects/{models,repository}.py`、`services/local-api/zhangwen/chat/router.py`、
  `packages/contracts/src/{api,enums}.ts`、`apps/desktop/src/components/layout/CenterChat.tsx`、
  `apps/desktop/src/styles/visual-workspace.css`。
- 测试：`apps/desktop/src/__tests__/MessageRecovery.test.tsx`、
  `services/local-api/tests/test_llm_error_recovery.py`、`test_project_chat_stream.py`、
  `test_project_repository.py`、`test_structure_engineer_cad_runtime.py`、
  `test_expert_runtime_clarification.py`、`test_required_real_llm.py`。
- 记录：`docs/{API_EVENTS,ARCHITECTURE,CURRENT_BASELINE,DECISIONS,PRD,UI_CONTRACT}.md`、`PLANS.md`、
  `HANDOFF.md` 与本任务文件。

## 9. 自动验证

- `D:\ZW_V1\.venv\Scripts\python.exe -m pytest` 定向六组后端文件：`88 passed`，只有既存
  Starlette/httpx 弃用警告。
- Desktop `MessageRecovery`、`RightPanel`、`ProjectIsolation`、`UnifiedProjectConversation`、
  `ExpertHandoff`、`VisualSystemContract`：`61 passed`。
- `pnpm --filter @zhangwen/contracts build`、Desktop strict typecheck 和
  `pnpm --filter @zhangwen/desktop build` 通过；只有既存 Vite chunk-size 提示。

## 10. 未完成与下一步

- 当前 Sidecar/桌面不是热更新进程。用户需关闭并重新启动掌问，在真实项目历史失败卡上抽检按钮和原
  专家恢复，再提交一个完整尺寸的无器件自由结构请求做真实 Provider 验收。
- 自动测试未调用真实付费 Provider，因此不能宣称真实模型以后永不返回无效 JSON；本任务保证根因路径
  已缩小，仍失败时有明确分类、建议和恢复动作，不再让对话停死。

## 11. 安全与恢复说明

- 分支：`codex/zw-005-016-autonomous`。工作树混有多个未提交任务；本任务未暂存、未提交、未打标签、
  未推送，未修改 `CURRENT_TASK.md`。
- 禁止整库 stash/reset/clean、`git add -A`、真实串口上传、Flash 擦除、固件烧录、强制推送和公开发布。
- 不得用本地模板伪装 Provider 成功、增加无界重试、输出 Provider 原文或放宽本地工程/安全校验。
