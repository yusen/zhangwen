# ZW-UX-008A — 三师结构化交接最小闭环

状态：已暂停（由 ZW-STABILIZE-001 取代）

## 1. 目标

在现有 Handoff、ProjectTask、PendingItem、ArtifactVersion、ArtifactDependency、ContextAssembler、ProjectCoordinator、ExpertWorkspace 和 ConversationThread 上完成唯一一条用户确认驱动的跨专家交接闭环：当前专家产生 `handoff_suggestion`，用户接受后由单一事务创建或恢复目标工作区和线程、创建 Handoff 与关联 Task、组装严格上下文、写入目标线程 `handoff_notice`，最后切换前端专家。

## 2. 不可变验收

- 接受前不创建 Handoff、目标 Task、目标工作区或线程，不切换专家。
- 手动点击专家不创建 Handoff。
- 不复制完整聊天，不共享私有草稿或私有记忆。
- 交接必须绑定存在且非 archived/outdated 的具体 ArtifactVersion。
- 接受使用持久化 `idempotencyKey`，重复请求返回第一次结果且不重复写入。
- 过期或 dismissed 建议不可接受。
- 三师继续使用独立线程。
- 不新建平行 Handoff、Task、Artifact、PendingItem 或 Context 系统。
- 所有跨前后端结构先修改 `packages/contracts`。

## 3. 范围

- Contracts：ArtifactVersionRef、suggestion/notice payload、accept/dismiss API、消息类型、schema v23。
- Backend：Pydantic 边界、forward-only migration、strict ContextAssembler、事务性 accept/dismiss、Runtime 仅产出建议。
- Desktop：交接建议卡、通知卡、稳定幂等键、成功后切换、失败/暂不处理保持来源线程。
- Privacy：工作区响应仅返回当前专家草稿，保留所有历史线程和数据库草稿。
- Tests：后端领域/API/事务/隐私/集成，前端卡片/切换/幂等/SSE 隔离，智能花盆两次交接和版本过期。

## 4. 非范围

- 欢迎页、能力快捷入口、项目总览全面改版、问题引导师阶段条、上下文抽屉、全类型产物卡重构、视觉美化、新专家、Skill 市场、复杂工作流画布。
- 事实依赖引擎、真实付费 LLM、真实串口、mpremote、esptool、Flash 擦除或固件烧录。

## 5. 里程碑

### M1 — Contracts-first

- [x] 修改共享枚举、API 类型和统一导出。
- [x] 修正 contracts v21 / backend v22 漂移并预留 v23。
- [x] contracts build/typecheck 通过。

### M2 — Backend transaction and strict context

- [ ] 增加 schema v23 和 migration 测试。
- [ ] 实现 strict handoff context，真正按 Task 和显式 IDs/versions 查询。
- [ ] 在 ProjectCoordinator 边界实现单事务 accept/dismiss 与持久化幂等。
- [ ] 写入目标线程 handoff_notice，最后更新 active expert。

### M3 — Runtime and desktop vertical slice

- [ ] Runtime 将 CandidateHandoff 写为 handoff_suggestion，不提前创建领域对象。
- [ ] 前端渲染 suggestion/notice，接受成功后才切换，失败和 dismiss 不切换。
- [ ] 收紧 Workspace DTO，不返回其他专家草稿。

### M4 — Acceptance and handoff

- [ ] 后端与前端要求的自动测试通过。
- [ ] 智能花盆两次交接及硬件 v2 导致结构产物 outdated 通过。
- [ ] 全量验证通过，更新 DECISIONS、HANDOFF、PLANS 和本任务。

## 6. Progress

- 2026-07-10：按用户附件直接启动实现；上一轮只读调查结论作为现状输入，不重复调查。M1 开始，先修改 `packages/contracts`。
- 2026-07-10：M1 完成；新增 ArtifactVersionRef、handoff suggestion/notice、accept/dismiss 请求响应、消息类型及 contracts v22/v23，`pnpm --filter @zhangwen/contracts build` 与 `typecheck` 通过。M2 开始，实施 v23 migration、事务接受/拒绝和 strict context。
- 2026-07-10：用户启动 ZW-STABILIZE-001 并暂停所有新功能；未完成的 contracts/backend v23 交接增量已从工作树撤回，本任务停止，不进入 M2/M3/M4。

## 7. Decision Log

- 2026-07-10：`handoff_suggestion` 复用现有消息 `structuredPayload` 持久化；用户接受前不创建 Handoff，避免增加 suggestion 领域表。
- 2026-07-10：接受幂等记录使用最小 forward-only migration，并由一个数据库事务覆盖工作区、线程、Handoff、Task、PendingItem、notice、suggestion 状态和 active expert。
- 2026-07-10：本任务编号是用户定向 `ZW-UX-008A`，不是被禁止的新阶段 `ZW-017`。

## 8. Safety

- 不调用真实 Provider 或读取/打印凭据。
- 不扫描或操作真实串口和设备。
- 不删除或覆盖现有项目、消息、草稿、私有记忆、Artifact 或 ArtifactVersion。
- 不暂存 `tasks/ZW-UX-003-three-expert-system.md` 的用户自有改动，不推送或强推。
