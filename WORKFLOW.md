# 掌问 Codex 自主开发工作流

本文件定义 `CODEX_AUTONOMOUS_WORKFLOW.md` 生效后的执行方式。`AGENTS.md`、PRD、架构、UI 契约和当前任务文件是前置约束。

## 1. 启动与恢复

开始或恢复工作时读取：

- `AGENTS.md`
- `WORKFLOW.md`
- `CURRENT_TASK.md`
- `HANDOFF.md`
- 当前 `tasks/ZW-*.md`
- 最近两个 Git 提交
- 当前阶段直接涉及的代码和测试

首次切换到自主开发模式时，还需读取 `CODEX_AUTONOMOUS_WORKFLOW.md`、`PLANS.md`、`docs/PRD.md`、`docs/ARCHITECTURE.md`、`docs/UI_CONTRACT.md`、`docs/API_EVENTS.md`、`docs/DECISIONS.md` 和 `docs/development/`。

## 2. 连续阶段

Codex 在 `codex/zw-005-016-autonomous` 分支连续完成：

1. ZW-005 本地硬件库与硬件规则引擎
2. ZW-006 立项书生成、版本与确认
3. ZW-007 Orchestrator 与 Agent Registry
4. ZW-008 Skill Registry 与模型路由
5. ZW-009 产物系统与浮窗系统
6. ZW-010 Spec Agent
7. ZW-011 Code Agent
8. ZW-012 设备管理与 MicroPython 部署
9. ZW-013 CAD Agent
10. ZW-014 Lesson Agent
11. ZW-015 分享与项目包
12. ZW-016 MVP 全流程集成与加固

完成 ZW-016 后停止。不得创建、规划或实现 ZW-017。

## 3. 阶段循环

每个阶段按以下顺序执行：

1. 检查已有实现，避免重复开发。
2. 创建或更新阶段任务文件，写明目标、非目标、数据模型、API、UI、测试、风险和验收条件。
3. 将 `PLANS.md` 中当前阶段标记为“进行中”。
4. 按里程碑实现，每个里程碑后运行受影响最小测试。
5. 更新 `HANDOFF.md` 和当前任务文件 Progress。
6. 完成阶段自动验收：验收条件、类型检查、单元测试、集成测试、必要构建、敏感信息、迁移、UI 不变量和错误恢复。
7. 更新任务文件、`HANDOFF.md`、`PLANS.md`、`docs/API_EVENTS.md` 和 `docs/DECISIONS.md` 中相关内容。
8. 创建阶段提交和阶段标签。
9. 更新 `CURRENT_TASK.md` 为下一阶段并继续。

## 4. 自主决策

Codex 可自行决定普通实现细节，包括文件拆分、组件命名、私有接口、测试组织、日志格式、非破坏性索引、可逆重构、Mock、Fixture 和普通 UI 文案。

以下事项必须停止或记录为外部验证待办：

- 真实 API Key 不存在或需要变更系统凭据；
- 真实设备不存在；
- 真实 Flash 擦除、固件烧录或覆盖设备文件；
- 公开发布、强制推送、重写历史；
- 管理员权限或系统安全策略变更；
- 不可逆数据删除或无法判断归属的用户数据。

## 5. Git 规则

- 总任务分支：`codex/zw-005-016-autonomous`。
- 不合并到 `main`，不强制推送，不重写历史。
- 阶段提交使用 `CODEX_AUTONOMOUS_WORKFLOW.md` 中定义的提交信息。
- 阶段标签使用 `zw-XXX-complete`；真实设备缺失时 ZW-012 可用 `zw-012-software-complete` 并记录外部验证待办。
- 不盲目使用 `git add -A`；提交前检查 diff、敏感信息和构建产物。

## 6. 测试策略

每阶段运行受影响模块单元测试、类型检查、必要集成测试和必要构建检查。

全量回归节点：

- ZW-006
- ZW-009
- ZW-012
- ZW-015
- ZW-016

纪律：

- 自动测试不得调用真实付费 LLM。
- 串口、设备和固件测试默认使用 Mock 或 Dry Run。
- 不删除失败测试，不降低类型严格度，不用大量 `any` 掩盖问题。
- 敏感信息不得进入日志、测试快照、导出包或 Git。

## 7. 中断恢复

`HANDOFF.md` 必须持续记录：

- 当前阶段、里程碑、分支和提交；
- 已完成、进行中、未开始；
- 已运行命令和测试结果；
- 未解决问题和外部验证待办；
- 下一次恢复时只需执行的唯一动作。

额度中断或长任务可创建 `wip: checkpoint ZW-XXX milestone N`。恢复后从 `HANDOFF.md` 的下一步继续，不重新实现已完成阶段。

## 8. ZW-016 交付

完成 ZW-016 后必须：

1. 完成全量测试、桌面构建和文档。
2. 创建 `feat: complete ZW-016 MVP integration and hardening` 提交。
3. 创建 `zw-016-complete` 标签。
4. 将 `CURRENT_TASK.md` 改为“ZW-016 已完成，等待用户最终手工验收”。
5. 生成 `docs/reports/CODEX_AUTONOMOUS_COMPLETION_REPORT.md`，包含最终开发报告、手工验收清单和 MVP 构建信息。
6. 停止执行，不进入任何新阶段。
