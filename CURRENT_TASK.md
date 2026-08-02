# CURRENT_TASK — 当前任务

## ZW-CREATOR-001 掌问创作端 V3 重建

状态：M0–M7 已完成，等待 M8 外部验收与旧壳清理（2026-07-31）

产品文档：`docs/PRD_CREATOR_V3.md`

任务文件：`tasks/ZW-CREATOR-001-creator-workbench-rebaseline.md`

当前目标：以用户确认的交互原型 V3 为产品基线，在现有平台内核上新建隔离 Creator 前端，
完成“我的作品 → 创意与方案 → 自动数字原型 → 仿真与图形调试 → 3D 结构 → 实物运行 →
用户验收 → 可复现交付”的完整路径。

创作端不再继承“中央主对话、固定工作/产物/设备三 Tab、图标轨、全局普通/专业模式和 UI
双板白名单”等旧产品约束。设备、凭据、串口、Flash、执行器确认、互斥、回读和恢复安全边界
继续有效。K10/XIAO 作为首批代理验证设备包，不是平台永久产品定义。

M0–M7 已完成仓库内软件闭环：恢复点、V30 契约与聚合投影、真实“我的作品”首页、左侧持续
对话与右侧四阶段、目标/方案、自动数字原型、功能仿真、参数版本、真实 CAD 边界、USB/ESP-Claw
同级部署、独立真机行为、显式用户验收、三种交付包、导入验证重置和第二用户复现证据。
页面只消费服务端投影，不能在前端推断等级。交付契约见 `docs/CREATOR_DELIVERY.md`。

下一阶段 M8 必须完成 390/720/1280 真人走查、真实 K10/XIAO 确认点、断网/崩溃/取消恢复、
安装包与发布验收，之后才能移除旧 V1/V2 壳。自动测试中的 Mock/Fake 结果不能替代这些外部门槛。

恢复顺序：先读 `HANDOFF.md`、本文件、任务文件、`docs/PRD_CREATOR_V3.md`、
`docs/PRODUCT_PROJECT_BOOK.md`，再按需读取旧 `docs/UI_CONTRACT.md`、`docs/PRD_V2.md` 和
`tasks/ZW-DEVICE-LAB-001-two-board-device-lab.md` 作为迁移/安全参考。
