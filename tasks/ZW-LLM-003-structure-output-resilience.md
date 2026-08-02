# ZW-LLM-003 — 结构工程师输出可靠性与本地校验分层

状态：实现完成且自动验收通过；重启后真人桌面抽检待用户（2026-07-16）

## 1. 目标

修复结构工程师在正常结构描述下被硬件库约束误判，继而显示“云端模型连续两次未返回有效结构”的问题；同时建立可复用的输出失败分类，让云端结构错误、本地工程约束错误和 CAD 确认状态不再混为同一种报错。

## 2. 已确认原因

- 失败运行 `expertrun_d59fa31a8b204898be2c906ed08bf585` 的两次 Provider 输出均进入了本地校验，最终异常来自硬件 grounding，而不是 JSON 解析或 Pydantic 结构解析。
- 当前 grounding 使用“模块、传感器、安装、开孔”等结构工程常用词判断是否发生硬件选型，导致普通机械描述被错误当作“绕开本地硬件库”。
- 结构化调用层把本地 `validate_result` 拒绝与 Provider JSON/Schema 错误统一转换为 `LLM_OUTPUT_INVALID`，因此用户看到的文案错误地归因于云端结构。
- CAD 链路已经由本地确认状态生成 `hardwareId/profileId`，这比要求自然语言重复器件名称更可靠，但现有 grounding 未优先使用该结构化证据。

## 3. 非目标与安全边界

- 不调用真实云端 LLM，不读取或输出 API Key。
- 不操作串口、设备、Flash 或固件。
- 不降低未确认机械参数、越权硬件引用、危险代码和工具边界校验。
- 不保存 Provider 原始失败输出；只持久化脱敏后的失败类别与本地诊断。
- 不修改并行任务指针 `CURRENT_TASK.md`，不创建 ZW-017。

## 4. 实施计划

### M1：回归与契约

- 固化普通“传感器安装/开孔”结构描述只调用一次 Provider 并通过的回归。
- 固化外部硬件替换建议仍必须引用并评估 ACTIVE 本地库的回归。
- 固化 CAD 使用已确认 `hardwareId/profileId` 作为 grounding 证据的回归。
- 固化 Provider 结构错误与本地工程约束错误使用不同错误码和文案的回归。

状态：已完成。

### M2：grounding 语义收窄

- 将普通结构词从硬件选型触发条件中移除，只在明确选型、替换、BOM、电气方案或代码输出时启用文本 grounding。
- CAD 输出优先校验本地已确认的硬件/机械档案 ID，不要求自然语言重复器件名称。
- 保留未知器件、未确认机械档案和绕开 ACTIVE 本地库的拒绝逻辑。

状态：已完成。

### M3：失败类型分层

- Provider 无 JSON 或不满足输出 Schema：继续返回 `LLM_OUTPUT_INVALID`。
- Provider 结构有效但未通过本地工程/安全约束：返回独立的 `LOCAL_OUTPUT_REJECTED`。
- 两类失败都保留一次定向修复重试和脱敏诊断，不泄露 Provider 原始文本。

状态：已完成。

### M4：验证

- 运行结构工程师、CAD intake、三师 grounding、聊天 API 和共享契约定向测试。
- 运行相关 Python 编译、TypeScript 类型检查和 `git diff --check`。
- 不使用真实付费 Provider；最后由用户重启 Sidecar 后进行真人桌面抽检。

状态：自动验证已完成；真人桌面抽检待用户重启后进行。

### M5：交接

- 更新本任务、`PLANS.md` 与 `HANDOFF.md`，记录改动、命令、测试、风险和重启要求。

状态：已完成。

## 5. 验收标准

- 普通结构工程描述不再因“传感器、安装、开孔”等词被误判为硬件选型。
- 固定安装 CAD 只要引用本地确认的 `hardwareId/profileId`，无需在自然语言中重复器件名也能通过 grounding。
- 明确推荐外部主控或绕开 ACTIVE 本地库时，仍触发修复重试或本地拒绝。
- 本地约束连续拒绝不再向用户显示“云端模型未返回有效结构”。
- 真正的无效 JSON/Schema 仍返回原有 `LLM_OUTPUT_INVALID`，保持准确诊断。

## 6. Decision Log

- 2026-07-16：grounding 证据优先级确定为“本地确认的结构化 ID > 本地硬件别名文本 > 无证据”；普通结构术语不构成硬件选型证据。
- 2026-07-16：保留两次生成上限，不增加第三次付费调用或本地伪答案回退。
- 2026-07-16：新增本地拒绝错误码，而不是继续复用云端结构错误文案。

## 7. Progress

- 2026-07-16：完成只读诊断，从本地运行记录确认真实失败来自硬件 grounding，且错误被调用层错误归类为 `LLM_OUTPUT_INVALID`；M1 开始。
- 2026-07-16：新增普通机械术语、结构建议、外部主控替换、CAD 已确认 ID、两类失败诊断和聊天 SSE 错误传播回归；先确认旧实现按预期失败，再完成实现。
- 2026-07-16：grounding 只在明确选型/替换/BOM/硬件或电气方案、类型化硬件选择和代码草稿上启用；CAD 改用已确认 `hardwareId/profileId`。普通“传感器模块安装、接口开孔、建议采用加强筋”一次通过。
- 2026-07-16：`complete_structured()` 将 Pydantic/JSON 失败保留为 `LLM_OUTPUT_INVALID`，本地 `validate_result` 连续拒绝改为 `LOCAL_OUTPUT_REJECTED`；ExpertRuntime 输出应用阶段也不再把本地异常伪装为云端结构错误。
- 2026-07-16：核心定向回归 `10 passed`；完整三师/CAD/聊天/进度扩展回归 `96 passed, 1 deselected`，被跳过的旧 K10 映射夹具随后修复并单测 `1 passed`；Spec/Code/CAD/Lesson 服务回归 `23 passed`；最终两类聊天错误 SSE 对照 `2 passed`。仅有既存 Starlette/httpx 弃用警告。
- 2026-07-16：contracts 与 desktop TypeScript build/typecheck 全部通过，5 个本轮 Python 实现文件内存编译通过。未调用真实付费 LLM、串口或设备，未暂存、提交、打标签或推送。
