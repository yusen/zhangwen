# 掌问三师系统框架包

本包用于指导 Codex 在现有“掌问”代码仓库中实施三师系统改造。

## 使用顺序

1. 阅读 `掌问_三师系统框架_v1.0.md`
2. 阅读 `docs/01-architecture.md`
3. 阅读 `docs/02-domain-and-state.md`
4. 阅读 `docs/03-workflows.md`
5. 阅读 `docs/04-migration.md`
6. 将 `scaffold/` 中的接口和配置映射到现有仓库
7. 使用 `CODEX_TASK.md` 作为 Codex 总任务
8. 按 `tests/acceptance.md` 验收

## 重要约束

- 不使用子 Agent
- 前台只显示三个专家
- 主路由和项目协调器不可见
- 中央对话为主流程
- 右侧工作只突出一个事项
- 保留现有 Tauri/React/TypeScript、本地优先、Skill Registry、Model Router、Tool Runner
- 旧项目和旧专家数据必须兼容
