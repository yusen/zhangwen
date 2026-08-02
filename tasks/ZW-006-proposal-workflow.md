# ZW-006 立项书生成、版本与确认

## Purpose / Big Picture

用户确认唯一推荐实现方案后，掌问生成可审查、可修改、可确认和可导出的项目立项书。立项书作为后续 Orchestrator、Spec、Code、CAD、Lesson 和设备流程的正式项目基线之一；查看立项书必须通过右侧产物栏或浮窗，中央主对话保持常驻。

## Scope

- 立项书数据模型、章节模板、版本、状态和确认时间。
- 基于已确认方案生成立项书。
- 支持修改生成新版本、确认、退回和方案变化导致旧立项书过期。
- 支持 Markdown、DOCX、PDF 导出。
- 右侧“产物”栏显示真实立项书产物，浮窗预览完整内容。

## Non-goals

- Agent Registry、Skill Registry 和 Orchestrator。
- Spec Agent、代码生成、设备上传、CAD、教案和分享。
- 云端协作或公开发布。

## Repository Orientation

| 模块 | 当前状态 | ZW-006 动作 |
|---|---|---|
| `packages/contracts` | 只有方案和硬件类型 | 新增 Proposal 类型、状态和导出格式 |
| `services/local-api/zhangwen/proposals/` | 不存在 | 新增 models、repository、router、exporter |
| `services/local-api/zhangwen/projects/migrations.py` | v3 | 增加 v4 proposals 表 |
| `apps/desktop/src/components/right-panel/ArtifactsTab.tsx` | 静态 mock | 读取当前项目 proposal 列表并显示 |
| `apps/desktop/src/components/floating/FloatingWindow.tsx` | 占位内容 | 支持传入立项书预览正文 |

## Interfaces and Data Contracts

- `ProposalStatus`: `DRAFT | APPROVED | REJECTED | STALE | SUPERSEDED`
- `ProposalExportFormat`: `MARKDOWN | DOCX | PDF`
- `ProposalSection`: `id/title/content`
- `ProposalVersion`: `id/projectId/solutionId/solutionVersion/version/status/sections/createdAt/updatedAt/confirmedAt/staleReason`
- `GenerateProposalRequest`: `solutionId`
- `ReviseProposalRequest`: `proposalId/revisionMessage`
- `ConfirmProposalRequest`: `proposalId`
- `RejectProposalRequest`: `proposalId/reason`

## Milestones

### M1 Contracts and Schema

新增 shared contracts、Python Pydantic models、SQLite v4 migration 和 repository。

### M2 Proposal API and Export

实现生成、列表、当前、修改、确认、退回和导出 API。生成时要求方案为 `CONFIRMED`。

### M3 Right Panel and Floating Preview

将右侧产物 Tab 从静态 mock 改为加载项目 proposal 列表；点击完整查看打开浮窗预览，导出按钮调用后端。

### M4 Validation and Stage Close

运行 Python、contracts、desktop 类型检查、测试和构建；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts and Schema
- [x] M2 Proposal API and Export
- [x] M3 Right Panel and Floating Preview
- [x] M4 Validation and Stage Close

## Surprises & Discoveries

- `@zhangwen/desktop` 读取的是 `@zhangwen/contracts` 的 `dist` 导出；新增 contracts 后必须先运行 `pnpm --filter @zhangwen/contracts build`，否则 desktop typecheck 看不到新类型。
- 旧前端测试的产物栏 mock 会掩盖真实 proposal API 路径，已改为项目级 fetch mock。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | 立项书生成来源 | 只允许 `CONFIRMED` 方案生成 | 符合 PRD 与 ZW-006 规则，避免草稿方案进入正式产物 |
| A-02 | 导出实现 | Sidecar 使用标准库生成 Markdown、最小 DOCX、最小 PDF | MVP 避免新增依赖，自动测试可验证 MIME 和内容 |
| A-03 | 方案变化过期规则 | 生成新方案时将该项目未确认/已确认 proposal 标记为 `STALE` | 后续 Orchestrator 只能引用当前方案的立项书 |

## Validation

- `.\.venv\Scripts\python.exe -m py_compile services\local-api\zhangwen\proposals\models.py services\local-api\zhangwen\proposals\repository.py services\local-api\zhangwen\proposals\router.py services\local-api\zhangwen\proposals\exporter.py services\local-api\zhangwen\solutions\repository.py services\local-api\zhangwen\solutions\router.py services\local-api\zhangwen\main.py`：通过。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw006_proposals.py -v --rootdir services/local-api`：4 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py services/local-api/tests/test_zw004_clarification_solution.py services/local-api/tests/test_zw005_hardware_crud.py services/local-api/tests/test_zw006_proposals.py -v --rootdir services/local-api`：36 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `pnpm --filter @zhangwen/contracts build`：通过。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- RightPanel.test.tsx ProjectWorkspace.test.tsx`：6 files / 36 tests passed。
- `pnpm --filter @zhangwen/contracts build`：通过（全量回归节点）。
- `pnpm --filter @zhangwen/contracts typecheck`：通过（全量回归节点）。
- `pnpm --filter @zhangwen/desktop typecheck`：通过（全量回归节点）。
- `pnpm --filter @zhangwen/desktop test`：6 files / 36 tests passed（全量回归节点）。
- `pnpm --filter @zhangwen/desktop build`：通过，Vite 输出 `apps/desktop/dist/`（全量回归节点）。
- `.\.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api`：57 passed，1 个 Starlette/httpx warning；pytest atexit 仍有既有临时目录 `PermissionError`（全量回归节点）。
- `.\.venv\Scripts\python.exe scripts/check_ai_assets.py`：通过，Shared Skills are in sync。

## Outcomes & Retrospective

- 已新增 `ProposalStatus`、`ProposalExportFormat`、Proposal 请求/响应 contracts 和 Python Pydantic models。
- SQLite schema 升级到 v4，新增 `proposals` 表；项目 workspace 返回 `schemaVersion: 4`。
- Sidecar 新增 proposal 列表、当前、生成、修订、确认、退回和 Markdown/DOCX/PDF 导出 API。
- Proposal 生成只接受 `CONFIRMED` solution；新方案生成会将旧 DRAFT/APPROVED proposal 标记为 `STALE`。
- 右侧“产物”Tab 改为读取真实 proposal 列表，完整查看通过浮窗展示章节正文，导出链接调用 Sidecar。
- 未发现新的 API Key、日志、测试快照或 Git 敏感信息风险；proposal export 不包含凭据或本机绝对路径。
- 架构风险：DOCX/PDF 为 MVP 最小渲染器，满足自动测试和基础导出，但复杂版式留给后续增强。

## Handoff

下一步：提交 `feat: complete ZW-006 project proposal workflow`，创建 `zw-006-complete` 标签，然后进入 ZW-007。
