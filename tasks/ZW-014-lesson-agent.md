# ZW-014 Lesson Agent

## Purpose / Big Picture

ZW-014 建立 Lesson Agent 的教学材料闭环。MVP 需要能从已确认 Spec 和立项书生成教师教案、学生任务单、评价量表和安全说明，并同步为可预览的文档 Artifact。教案变化不修改工程核心数据，不调用真实 LLM，也不写入真实项目工作区文件。

## Scope

- Lesson shared contracts 与 Python Pydantic models。
- SQLite v12 `lesson_runs` 与 `lesson_files`。
- 确定性 Markdown 教案生成器。
- Lesson API：读取当前、生成、确认、退回。
- 文档 Artifact 同步与旧版本过期状态。
- 右侧“工作”Tab 显示教案状态、课时、学段、文档数量和确认操作。

## Non-goals

- 调用真实 LLM 生成教学材料。
- DOCX/PDF 教案导出。
- 修改方案、Spec、Code、CAD 或设备部署核心数据。
- 分享、项目包和 MVP 硬化阶段实现。

## Interfaces and Data Contracts

- `LessonDocumentKind`: `TEACHER_GUIDE | STUDENT_WORKSHEET | RUBRIC | SAFETY_NOTES`
- `LessonRunStatus`: `DRAFT | READY_FOR_REVIEW | APPROVED | REJECTED | STALE | FAILED`
- `LessonFile`: `id/lessonRunId/projectId/kind/title/path/mimeType/content/artifactId/artifactVersionId/createdAt`
- `LessonRun`: `id/projectId/specRunId/proposalId/version/status/gradeBand/lessonHours/files/staleReason/createdAt/updatedAt/confirmedAt`
- `GenerateLessonRequest`: `specRunId/gradeBand?/lessonHours?`
- `ConfirmLessonRequest`: `lessonRunId`
- `RejectLessonRequest`: `lessonRunId/reason?`

## Milestones

### M1 Contracts, Schema and API

新增 Lesson contracts、Python models、SQLite v12 migration、Sidecar Lesson API 和文档 Artifact 同步。

### M2 Work Tab UI

新增右侧“工作”Tab 课程教案卡片，支持读取、生成、确认、退回，并保持中央主对话常驻。

### M3 Tests and Validation

新增后端 Lesson Agent 测试和前端 RightPanel 回归测试；同步 schema v12 断言。

### M4 Stage Close

运行本阶段完整验证；更新文档、决策、交接并提交阶段。

## Progress

- [x] M1 Contracts, Schema and API
- [x] M2 Work Tab UI
- [x] M3 Tests and Validation
- [x] M4 Stage Close

## Surprises & Discoveries

- 生成第二版教案时，旧版 `lesson_runs` 已被标记为 `STALE`，但对应 Artifact 版本也必须重新同步，否则产物 Tab 会展示不一致状态。已在 LessonRepository 中修复并添加测试。
- 文档 Artifact 需要章节预览；`ArtifactRepository.upsert_text_artifact` 增加了可选 `sections` 参数，默认代码预览行为保持不变。

## Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| A-01 | 教案生成策略 | 确定性 Markdown 模板 | 避免真实 LLM 成本和凭据风险，保证自动测试可重复 |
| A-02 | 生成前置条件 | 必须使用 `APPROVED` Spec，并引用对应立项书 | 防止草稿工程数据进入教学材料 |
| A-03 | Artifact 同步 | 每类教学文档一个 `DOCUMENT` Artifact | 便于右侧产物 Tab 和浮窗分别查看教师版、学生版、量表和安全说明 |
| A-04 | 工程数据边界 | 教案确认不修改方案、Spec、Code、CAD 或设备数据 | 教案属于教学表达产物，不应改变工程基线 |

## Validation

- `pnpm --filter @zhangwen/contracts build`：通过。
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen/lesson_agent services/local-api/zhangwen/main.py services/local-api/zhangwen/projects/migrations.py services/local-api/zhangwen/projects/models.py services/local-api/zhangwen/projects/repository.py services/local-api/zhangwen/artifacts/repository.py`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw014_lesson_agent.py -v --rootdir services/local-api`：4 passed；仅 Starlette/httpx deprecation warning 和 pytest 退出时 Windows 临时目录清理 `PermissionError`。
- `pnpm --filter @zhangwen/contracts typecheck`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -v --rootdir services/local-api`：87 passed；仅 Starlette/httpx deprecation warning 和 pytest 退出时 Windows 临时目录清理 `PermissionError`。
- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- --run src/__tests__/RightPanel.test.tsx`：45 passed（Vitest 实际运行桌面测试全套 6 files）。
- `pnpm --filter @zhangwen/desktop build`：通过。
- `git diff --check`：通过；仅 Git 行尾转换提示。
- 敏感信息扫描：受影响文件仅命中既有测试假掩码 `sk-****alue`、契约字段名 `apiKey`、安全文档说明和本阶段测试中的反向断言；无真实凭据、真实串口或用户隐私数据。

## Outcomes & Retrospective

- 完成 Lesson shared contracts、SQLite v12、Sidecar Lesson API、确定性教案生成、文档 Artifact 同步和右侧“工作”Tab 教案操作。
- 未调用真实 LLM、未写入真实工作区、未访问真实设备或系统凭据。
- 中央主对话保持常驻；教案在右侧工作栏操作，完整内容复用产物/浮窗系统。

## Handoff

ZW-014 软件能力已自动验收通过，下一步是创建阶段提交 `feat: complete ZW-014 lesson agent` 并打标签 `zw-014-complete`，随后进入 ZW-015 分享与项目包。
