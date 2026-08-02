# 三师系统第一阶段：领域模型和数据迁移

生成时间：2026-07-10
范围：只实现领域模型、兼容映射和 SQLite v19 迁移；未实现主路由、协调器运行逻辑或页面布局改造。

## 修改文件清单

共享契约：
- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/index.ts`

后端领域模型与仓库：
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/artifacts/models.py`
- `services/local-api/zhangwen/artifacts/repository.py`
- `services/local-api/zhangwen/code_agent/repository.py`

桌面兼容数据与标签：
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/right-panel/WorkTab.tsx`
- `apps/desktop/src/components/right-panel/ArtifactsTab.tsx`
- `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`
- `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`
- `apps/desktop/src/__tests__/RightPanel.test.tsx`
- `apps/desktop/src/__tests__/DeepSeekChat.test.tsx`
- `apps/desktop/src/__tests__/SettingsDeepSeek.test.tsx`

测试：
- `services/local-api/tests/test_project_repository.py`
- `services/local-api/tests/test_zw004_clarification_solution.py`
- `services/local-api/tests/test_zw005_hardware_crud.py`
- `services/local-api/tests/test_zw006_proposals.py`
- `services/local-api/tests/test_zw007_orchestrator.py`
- `services/local-api/tests/test_zw008_skills_model_router.py`
- `services/local-api/tests/test_zw009_artifacts_windows.py`
- `services/local-api/tests/test_zw010_spec_agent.py`
- `services/local-api/tests/test_zw011_code_agent.py`
- `services/local-api/tests/test_zw012_devices.py`
- `services/local-api/tests/test_zw013_cad_agent.py`
- `services/local-api/tests/test_zw014_lesson_agent.py`
- `services/local-api/tests/test_zw015_project_packages.py`

## 实现内容

Schema 升级到 v19。新 canonical 专家类型为：
- `problem_guide`
- `smart_engineer`
- `structure_engineer`

兼容保留的历史值：
- v18 过渡值：`question_guide`、`intelligent_engineer`
- UX-002 四专家：`ideator`、`educator`、`open_hardware_designer`、`structure_designer`
- 规格别名：`three_d_structure_designer`

新增或补齐的领域结构：
- `ExpertWorkspaceStatus`
- `DomainArtifactStatus`
- `SharedFactStatus`
- `PendingItemPriority`
- `PendingItemStatus`
- `HandoffStatus`
- `SharedFact`
- `ProjectDecision`
- `ArtifactDependency`
- `Handoff`
- `PendingItem`

新增 SQLite 结构：
- `project_experts.legacy_expert_type`
- `project_experts.archived_legacy_thread`
- `project_experts.workspace_status`
- `conversations.owner_expert_type`
- `conversations.legacy_expert_type`
- `conversations.archived_legacy_thread`
- `artifacts.legacy_owner_expert`
- `artifacts.creator_legacy_expert`
- `artifacts.domain_status`
- `artifact_versions.domain_status`
- `project_shared_facts`
- `project_decisions`
- `project_pending_items`
- `project_handoffs`
- `artifact_dependencies`

`project_experts` 在 v19 被重建，移除旧的 `UNIQUE(project_id, expert_type)`。这样 `ideator` 和 `educator` 都映射到 `problem_guide` 后，可以作为不同归档历史线程保留，不需要合并聊天内容。

## 迁移映射

专家映射：

| 迁移前 | 迁移后 | legacyExpertType | archivedLegacyThread |
|---|---|---|---|
| `question_guide` | `problem_guide` | `question_guide` | `false` |
| `intelligent_engineer` | `smart_engineer` | `intelligent_engineer` | `false` |
| `ideator` | `problem_guide` | `ideator` | `true` |
| `educator` | `problem_guide` | `educator` | `true` |
| `open_hardware_designer` | `smart_engineer` | `open_hardware_designer` | `true` |
| `structure_designer` | `structure_engineer` | `structure_designer` | `true` |
| `three_d_structure_designer` | `structure_engineer` | `three_d_structure_designer` | `true` |

产物状态映射：

| 旧 ArtifactStatus | domainStatus |
|---|---|
| `DRAFT` | `draft` |
| `GENERATING` | `pending_confirmation` |
| `NEEDS_REVIEW` | `pending_confirmation` |
| `APPROVED` | `confirmed` |
| `STALE` | `outdated` |
| `ARCHIVED` | `archived` |

## 迁移前后数据示例

专家线程迁移前：

```json
{
  "projectExpertId": "pexp_legacy_ideator",
  "expertType": "ideator",
  "conversationId": "conv_legacy_ideator",
  "messages": ["创想家历史内容"]
}
```

专家线程迁移后：

```json
{
  "projectExpertId": "pexp_legacy_ideator",
  "expertType": "problem_guide",
  "legacyExpertType": "ideator",
  "archivedLegacyThread": true,
  "conversationId": "conv_legacy_ideator",
  "messages": ["创想家历史内容"]
}
```

`educator` 会同样映射为 `problem_guide`，但保留自己的 `conversationId` 和消息，不与 `ideator` 合并。

产物迁移前：

```json
{
  "artifactId": "artifact_code",
  "ownerExpertType": "open_hardware_designer",
  "status": "NEEDS_REVIEW"
}
```

产物迁移后：

```json
{
  "artifactId": "artifact_code",
  "ownerExpertType": "smart_engineer",
  "legacyOwnerExpert": "open_hardware_designer",
  "creatorLegacyExpert": "open_hardware_designer",
  "status": "NEEDS_REVIEW",
  "domainStatus": "pending_confirmation"
}
```

SharedFact 迁移后示例：

```json
{
  "field": "initialIdea",
  "key": "initialIdea",
  "status": "proposed",
  "sourceType": "user",
  "confirmed": false
}
```

旧 JSON 中如果只有 `confirmed: true` 但没有 `confirmedBy`，v19 会降为 `proposed`，避免没有确认来源的共享事实被当成已确认。

## 幂等性和兼容性

- v19 迁移使用 `ALTER TABLE` 前置列检查、`CREATE TABLE IF NOT EXISTS`、确定性 `artifact_dependencies.id` 和 `ON CONFLICT` 回填。
- 重复打开同一个 v19 数据库不会重复创建 canonical 三师工作区。
- `workspace.experts` 只返回当前活跃三师工作区。
- 归档 legacy 线程保留在 `project_experts` / `conversations` 中，并可通过 `ExpertConversation.legacyExpertType` 与 `archivedLegacyThread` 识别。
- 新产物 owner 映射优先使用 `smart_engineer` / `structure_engineer` / `problem_guide`，旧字段只作为迁移审计信息保留。

## 回滚方法

当前迁移体系仍是 forward-only 手写 SQLite migration，没有 down migration。

推荐回滚：
1. 在打开新版本应用前备份 `projects/zhangwen.sqlite3`。
2. 如需回滚，关闭应用。
3. 用备份文件替换当前 `zhangwen.sqlite3`。
4. 使用支持旧 schema 的应用版本打开备份。

不建议手工把 `PRAGMA user_version` 从 19 改回 18。v19 已重建 `project_experts` 并新增多张表，单独改版本号不会恢复 v18 结构。

## 验证命令

已运行并通过：

- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/contracts typecheck`
- `pnpm --filter @zhangwen/desktop typecheck`
- `pnpm --filter @zhangwen/desktop test -- ProjectWorkspace ProjectIsolation RightPanel`
- `.venv\Scripts\python.exe -m compileall services/local-api/zhangwen`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -q --rootdir services/local-api`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_zw009_artifacts_windows.py services/local-api/tests/test_zw011_code_agent.py services/local-api/tests/test_zw015_project_packages.py -q --rootdir services/local-api`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`

已知测试输出：
- 后端 pytest 仍有既有 `StarletteDeprecationWarning`。
- Windows pytest 结束后仍可能出现既有临时目录 cleanup `PermissionError`，测试结果为通过。
- 桌面相关测试仍有既有 WorkTab React `act(...)` warning，测试结果为通过。
