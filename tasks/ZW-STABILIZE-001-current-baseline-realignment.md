# ZW-STABILIZE-001 — 掌问当前代码基线重整

状态：已完成

## 1. 目标

在保留现有可用代码、SQLite 前向兼容和用户数据的前提下，冻结唯一产品基线；用路由注册、API 调用、组件入口、引用搜索和测试证据分类现有模块；将可自动验证的最小主流程稳定为“创建项目 → 问题引导师独立对话 → 推荐并确认方案 → 右侧查看同一版本化产物 → 切换智能工程师且线程/草稿隔离 → 重启恢复项目”。

## 2. 不可变验收

- 不新增产品功能、页面、API、数据库表、领域模型、专家或工作流。
- 不继续 ZW-UX-005～ZW-UX-010；ZW-UX-008A 的未完成代码增量必须撤回。
- `docs/CURRENT_BASELINE.md` 给出唯一产品/技术/schema/Provider 基线及 KEEP/FIX/DEPRECATE/UNKNOWN 清单。
- `docs/DEPRECATION_PLAN.md` 只列有调用证据、替代实现、风险和删除前测试的候选，不因文件名直接删除。
- 主流程具备自动测试，阻断错误被修复；非阻断问题仅记录。
- 不删除用户项目、消息、草稿、私有记忆、Artifact、ArtifactVersion 或旧项目兼容字段。
- 不调用真实付费 LLM、真实串口、mpremote、esptool、Flash 擦除或固件烧录。

## 3. 里程碑

### M1 — Baseline freeze and evidence inventory

- [x] 暂停 ZW-UX-008A 并撤回其未完成 contracts/backend 新功能增量。
- [x] 用入口、路由、调用和测试证据完成模块分类。
- [x] 创建 `docs/CURRENT_BASELINE.md`。

### M2 — Deprecation plan and main-flow tests

- [x] 创建 `docs/DEPRECATION_PLAN.md`。
- [x] 补充/修复最小主流程后端与桌面自动测试。
- [x] 仅修复会阻止该主流程运行的错误；全量验证未发现其他主流程阻断。

### M3 — Full validation and handoff

- [x] 运行用户指定的 contracts/desktop/backend/Cargo/whitespace 全量验证。
- [x] 更新 `docs/DECISIONS.md`、`HANDOFF.md`、`PLANS.md` 和本任务。
- [x] 记录实际删除、剩余阻塞和下一项唯一建议任务。

## 4. Progress

- 2026-07-10：任务启动。停止 ZW-UX-008A；通过 `apply_patch` 精确撤回其未完成的 v23、handoff API、领域模型、Runtime 和 ContextAssembler 增量；保留 `tasks/ZW-UX-003-three-expert-system.md` 用户自有修改。M1 进入证据清单与当前基线固化。
- 2026-07-10：M1 完成。新增 `docs/CURRENT_BASELINE.md`，用 React/Sidecar 入口、Router 注册、桌面 API 引用和测试证据完成 KEEP/FIX/DEPRECATE/UNKNOWN 分类，并冻结唯一主流程与 schema v22/DeepSeek/本地执行边界。
- 2026-07-10：M2 证据与测试完成。新增 `docs/DEPRECATION_PLAN.md` 和 `test_current_baseline_flow.py`；后者使用 fake Provider 串联项目创建、问题引导、方案生成/确认、同一 ArtifactVersion、专家线程/草稿隔离和 Repository 重建恢复，首次运行 1 passed。修复 contracts v21/backend v22 漂移并同步桌面 fixtures；删除三个经无引用和替代测试证明的占位/旧卡片文件。
- 2026-07-10：M3 完成。contracts build/typecheck、desktop typecheck/67 tests/build、Python compileall/146 tests、Cargo check 和 `git diff --check` 全部通过；仅保留既有 React `act(...)` 与 Starlette/httpx deprecation warning。未调用真实付费 LLM、串口或硬件。下一项唯一建议任务是 `ZW-STABILIZE-002 跨端契约一致性门禁`，只增加 Python/TypeScript DTO 与枚举的自动对照，不开发产品功能。

## 5. Decision Log

- 2026-07-10：稳定基线以当前已提交 schema v22、三师独立线程、Provider 驱动澄清/方案和版本化 Solution Artifact 为准；未完成的 v23 结构化交接不是当前基线。
- 2026-07-10：本任务不做推测性删除。只有无调用、存在替代且有测试覆盖的代码才允许删除；否则记录到 DEPRECATION_PLAN。
- 2026-07-10：独立 `/clarify` 与 `/solution/*` 写 API 虽与中央对话动作重叠，但仓库外调用未知且部分测试仍直接依赖，列为 DEPRECATE 而不删除；legacy expert 值继续 KEEP 以保护用户数据。
- 2026-07-10：实际删除仅限两个无引用旧卡片组件和一个无 import 占位包；未删除路由、表、领域模型、用户数据或 legacy 兼容值。

## 6. Safety

- 不读取、打印或修改真实凭据。
- 不扫描、连接或操作真实设备。
- 不使用 `git clean`、历史重写、强推或递归通配删除。
- 不暂存 `tasks/ZW-UX-003-three-expert-system.md` 的用户自有改动。
