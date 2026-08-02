# Codex 总任务：将现有掌问项目重构为三师系统

## 开始前

先扫描仓库并输出：
- 技术栈
- 目录结构
- 专家枚举和配置位置
- Agent Registry、Skill Registry、Model Router、Tool Runner 位置
- 项目、对话、产物、设备和任务数据模型
- 数据库与迁移工具
- 当前项目创建流程
- 当前中央对话和右侧栏实现
- 受影响文件清单

分析完成后继续实施，不等待确认。

## 必须保留

- Tauri 2 + Rust + React + TypeScript + Vite
- Local-first 混合架构
- 现有 Agent/Skill/模型/工具基础设施
- ESP32 + MicroPython MVP
- 中央主对话
- 右侧工作/产物/设备
- 旧项目兼容

## 目标架构

前台：
- problem_guide / 问题引导师
- smart_engineer / 智能工程师
- structure_engineer / 结构工程师

后台：
- entry_router
- project_coordinator

不使用子 Agent。

## 实施阶段

1. 新专家枚举、旧角色映射和迁移。
2. 三师 AgentDefinition 和独立提示词。
3. 智能工程师 Skill Registry。
4. 主路由 JSON Schema 和降级规则。
5. 项目共享上下文结构化。
6. 三师独立对话和私有草稿。
7. 项目协调器确定性状态机。
8. 产物版本、依赖和过期传播。
9. 唯一 PendingItem。
10. 项目创建和专家推荐。
11. 左中右界面改造。
12. 迁移、领域、流程和 UI 测试。

## 约束

- 不建立新的平行项目。
- 不无原因更换技术栈。
- 不只修改显示名称。
- 不在前端硬编码路由结果。
- 不把整个聊天作为共享上下文。
- 不允许 LLM 直接覆盖已确认事实。
- 不允许专家改写其他专家正式产物。
- 不删除旧版本。
- 不暴露主路由、协调器、内部 JSON 或推理过程。

## 完成输出

- 修改摘要
- 文件清单
- 数据迁移说明
- 三师和 Skill 注册说明
- 路由和协调器实现说明
- 兼容策略
- 测试结果
- 未完成项
- 启动、迁移和验证命令
