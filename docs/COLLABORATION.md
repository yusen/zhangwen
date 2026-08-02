# Codex × Qoder 开发协作协议

## 1. 目标

任何开发者或编码 Agent 在没有此前聊天记录的情况下，只读取仓库即可继续工作。工具之间通过 Git、任务文件、契约和交接日志协作，不通过复制聊天内容协作。

## 2. 开始任务前

按顺序读取：`AGENTS.md`、`HANDOFF.md`、当前 `tasks/ZW-*.md`、相关 docs、代码与测试。确认分支与任务 ID。发现任务文件缺失时先创建，不直接开始大规模修改。

## 3. 结束或暂停前

更新任务 Progress、Decision Log、测试结果和 HANDOFF.md。提交应小而完整，不提交生成缓存、密钥和本地串口信息。

## 4. 职责建议

- Qoder：UI 视觉、组件、交互、前端联调、Spec 驱动的小到中型功能。
- Codex：架构、跨模块实现、后端、设备服务、测试、复杂重构和独立审查。
- 两者都可完成任意任务；最终以任务范围和契约为准。

## 5. 冲突处理

代码行为与文档冲突时先判断哪一方已通过测试。若是未记录的实现偏差，停止扩大修改，新增 Decision Log，再修正文档或代码。不得默默选择其中一方。

## 6. 共享 Skill

只编辑 `ai/skills`，运行 `python scripts/sync_ai_assets.py`。CI 运行 `python scripts/check_ai_assets.py` 防止两边漂移。

## 7. 分支与提交

- 分支：`feat/ZW-<id>-short-name`、`fix/ZW-<id>-short-name`
- 提交：`feat(ZW-001): description`
- 合并前：格式化 + 类型检查 + 单元测试 + 验收场景
