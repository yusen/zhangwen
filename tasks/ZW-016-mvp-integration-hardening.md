# ZW-016 MVP Integration and Hardening

## 2026-07-09 Post-MVP Solution Revision and Artifact UX Fix Record

This task remains complete and no ZW-017 work is started. A second post-ZW-016 desktop fix was applied on the same branch to address solution revision, solution display, and right-panel workflow issues:

- Natural-language solution changes now revise the current solution version instead of regenerating the whole project output.
- Solution revisions create a new draft version with `basedOnVersion`, `changeSummary`, and a durable `SolutionRevision` record containing `changedSections`, preserved sections, and impact summary.
- Generated and revised implementation solutions are synchronized into the Artifact system, so the chat `solution_card` and right-side Artifact point to the same `solutionId`/`artifactId`/`artifactVersionId`.
- Chat now renders structured implementation-solution cards with summary, expandable sections, version/status, revision diff, and actions.
- The Work tab now behaves as a project overview: current stage, one current user need, current solution mini-card, latest three Artifacts, and a simplified flow indicator.
- Solution revision marks dependent proposals stale/outdated but does not automatically regenerate or update the proposal.

Validation added/updated:

- Sidecar solution revision tests for targeted change, version lineage, changed/preserved sections, Artifact sync, restore, and proposal stale behavior.
- Project chat stream tests for `solution_card` generation and natural-language revision without proposal generation.
- Desktop solution card rendering tests and Work tab overview/latest Artifact tests.
- Existing right-panel floating-window tests now locate the intended Artifact by title instead of assuming the first Artifact is the proposal.

Post-fix validation:

- `pnpm typecheck`: passed.
- `pnpm --filter @zhangwen/desktop test`: 52 passed.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`: 101 passed, 1 known Starlette warning, plus known Windows pytest temp cleanup `PermissionError` after success.
- `pnpm build:desktop`: passed.
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`: passed.
- `pnpm tauri:build`: passed.
- `git diff --check`: passed with LF/CRLF warnings only.

## 2026-07-09 Post-MVP Desktop Fix Record

This task remains complete and no ZW-017 work is started. A post-ZW-016 desktop fix was applied on the same branch to address three user-reported MVP issues:

- New project selection now immediately switches the central conversation to the new project state; old project messages, drafts and stream callbacks are project-scoped and stale reloads are ignored.
- IDEA-stage clarification and solution/proposal actions now run through the central chat. The old central top "需求澄清" and "生成方案" buttons were removed.
- Clarification and next-step choices are persisted as chat-message structured payloads in SQLite schema v14.
- The device tab now scans host serial ports through the Python Sidecar and displays COM metadata, empty state and classified scan errors. It does not auto-connect or run device commands.

Validation added/updated:

- Project isolation frontend test.
- Structured IDEA chat/card frontend test.
- Project repository structured payload persistence test.
- Project chat stream structured response test.
- Serial scan Sidecar tests for multiple ports, empty list and scan error.

Post-fix validation:

- `pnpm --filter @zhangwen/contracts build`: passed.
- `pnpm --filter @zhangwen/contracts typecheck`: passed.
- `pnpm --filter @zhangwen/desktop typecheck`: passed.
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`: 97 passed.
- `pnpm --filter @zhangwen/desktop test`: 50 passed.
- `pnpm build:desktop`: passed.
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`: passed.
- `pnpm tauri:build`: passed.

## Purpose / Big Picture

ZW-016 收束 ZW-005 至 ZW-015 的软件能力，形成可审计、可运行、可继续人工验收的 MVP 完成版。本阶段不新增后续产品阶段，只做端到端集成、错误恢复、安全边界、全量测试、桌面构建验证、最终开发报告和手工验收清单。

## Scope

- 从现有项目数据派生 MVP readiness：项目、方案、立项书、执行计划、Spec、Code、Device Dry Run、CAD、Lesson、Package、Artifact 和安全边界。
- Sidecar 提供只读 readiness API，不新增 SQLite schema。
- 右侧“工作”Tab 显示 MVP 交付就绪度，中央主对话保持常驻。
- 端到端自动测试覆盖完整软件闭环，不调用真实付费 LLM、不访问真实串口、不执行真实 Shell/CadQuery/固件操作。
- 生成最终开发报告、手工验收清单和 MVP 桌面构建信息。

## Non-goals

- 不创建、规划或实现 ZW-017。
- 不实现安装器、自动更新、代码签名、公网发布或云同步。
- 不执行真实 DeepSeek 付费调用、真实串口扫描、真实设备文件写入、Flash 擦除或固件烧录。
- 不重写 ZW-005 至 ZW-015 已有能力。

## Interfaces and Data Contracts

- `MvpReadinessStatus`: `READY | NEEDS_ACTION | BLOCKED`
- `MvpReadinessItemId`: `PROJECT_BASELINE | SOLUTION | PROPOSAL | EXECUTION_PLAN | SPEC | CODE | DEVICE_DRY_RUN | CAD | LESSON | PACKAGE | ARTIFACTS | SECURITY`
- `GET /api/projects/{projectId}/mvp/readiness`
- `MvpReadinessReport`: overall status, ready/total counts, item evidence, external validation required and manual acceptance steps.

## Milestones

### M1 Contracts and Sidecar Readiness

新增 readiness contracts、Python models、只读聚合 repository 和 Sidecar route。

### M2 Desktop Readiness Surface

右侧“工作”Tab 展示 MVP 交付就绪度和外部验证待办，保持中央 `CenterChat` 常驻。

### M3 End-to-End Regression

新增 ZW-016 后端完整软件闭环测试和前端 readiness/UI contract 测试。

### M4 Full Validation and Final Delivery

运行全量回归、桌面构建验证、敏感信息扫描，更新最终报告、手工验收清单、HANDOFF、API_EVENTS、DECISIONS、PLANS 和 CURRENT_TASK。

## Progress

- [x] M1 Contracts and Sidecar Readiness
- [x] M2 Desktop Readiness Surface
- [x] M3 End-to-End Regression
- [x] M4 Full Validation and Final Delivery

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | Readiness 数据来源 | 从现有 SQLite 表只读派生，不新增 schema | ZW-016 是集成加固阶段，避免为汇总状态引入迁移风险 |
| A-02 | 外部验证处理 | readiness 明确列出真实设备、真实 API Key 和固件操作为人工验证 | 自动测试不能伪造真实外部成功 |
| A-03 | UI 位置 | 放在右侧“工作”Tab | 保持中央主对话常驻，符合 UI Contract |
| A-04 | 自动测试策略 | 方案确认用 repository fixture，后续阶段走真实 Sidecar API | 避免真实 LLM 费用，同时验证跨模块 API 闭环 |

## Validation

- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw016_mvp_integration.py -q --rootdir services/local-api`：2 passed。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- RightPanel.test.tsx`：48 passed。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`：95 passed。
- `pnpm --filter @zhangwen/desktop test`：48 passed。
- `pnpm --filter @zhangwen/desktop build`：通过，产物位于 `apps/desktop/dist`。
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen`：通过。
- `pnpm tauri:build`：通过，`apps/desktop/src-tauri/target/release/zhangwen-desktop.exe` 已生成。
- 敏感信息扫描：未发现真实 API Key、Authorization、Bearer token、真实串口标识或个人绝对路径；仅命中文档中的安全规则示例和扫描命令文本。

## Final Delivery Artifacts

- 最终开发报告：`docs/reports/CODEX_AUTONOMOUS_COMPLETION_REPORT.md`
- 最终手工验收清单：`docs/reports/MANUAL_ACCEPTANCE_CHECKLIST.md`
- MVP 构建信息：`docs/reports/MVP_BUILD_INFO.md`

## Handoff

ZW-016 自动验收已通过，最终报告、手工验收清单和 MVP 构建信息已生成。阶段提交与 `zw-016-complete` 标签完成后停止连续开发，等待用户最终手工验收。不得创建、规划或实现 ZW-017。
