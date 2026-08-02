# 领域模型与状态机

## ExpertType

- problem_guide
- smart_engineer
- structure_engineer

## ExpertWorkspaceStatus

- not_started
- waiting_dependency
- in_progress
- awaiting_user
- completed
- outdated

## ArtifactStatus

- draft
- pending_confirmation
- confirmed
- outdated
- archived

## TaskStatus

- queued
- ready
- running
- blocked
- awaiting_user
- completed
- failed
- cancelled

## HandoffStatus

- proposed
- accepted
- in_progress
- completed
- rejected
- cancelled

## SharedFactStatus

- proposed
- confirmed
- superseded
- rejected

## 关键不变量

1. 一个项目最多只有一个 `isHighlighted=true` 的 PendingItem。
2. `confirmed` 产物必须有版本号。
3. `outdated` 产物不能作为新任务的默认输入。
4. 专家只能更新自己创建的草稿或正式产物新版本。
5. SharedFact 从 proposed 变 confirmed 前必须有确认来源。
6. 下游产物保存其依赖的具体 artifactId 和 version。
7. 专家私有记忆不能直接覆盖共享事实。
