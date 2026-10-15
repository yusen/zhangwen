# D-Robotics RDK X5 Hardware Skill

本包按《掌问 Hardware Skill AI 编写与上线规范（v2）》整理标准版 D-Robotics RDK X5 的官方电气、计算、接口、RDK OS、Hobot.GPIO、结构包络和安全边界。

## 内容

- `SKILL.md`：使用入口和渐进加载导航。
- `references/`：电气、兼容、结构、集成、安全和官方来源。
- `models/cadquery.py`：85 × 56 × 20 mm 的 REFERENCE_ONLY 包络模型。
- `examples/usage.md`：Markdown 内联 Python 示例。
- `tests/validation-cases.md`：机器自检和人工验收。
- `assets/`：官方开发板接口图和 40PIN 功能对照图。

## 导入

保持顶层目录名为 `d-robotics-rdk-x5`，将完整目录导入掌问 Hardware Skill 目录。修改任何声明文本、模型或媒体元数据后必须重新计算哈希和 package revision。

## 验证状态与限制

- 关键参数逐项核对 D-Robotics 官方产品规格书、RDK DOC 和官方文档仓库。
- 未执行真实板卡、电气、外设、散热、网络、相机或机械装配测试。
- 当前环境没有掌问实际 `HardwareSkillRepository` 加载器；应用可见性为 `NOT_VERIFIED`。
- 机械能力仅为官方 85 × 56 × 20 mm 包络。官方图纸显示四个直径 2.5 mm 的安装孔，但本包未把未统一到明确坐标系的孔中心写入机器 JSON。
- 本包面向全板载标准版 RDK X5，不等同于 RDK X5 Module 或其载板。
