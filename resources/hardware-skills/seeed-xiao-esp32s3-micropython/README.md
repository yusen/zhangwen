# Seeed Studio XIAO ESP32S3（MicroPython）Hardware Skill

本包按《掌问 Hardware Skill AI 编写与上线规范（v2）》整理基础版 Seeed Studio XIAO ESP32S3 的官方硬件事实、MicroPython API、接线边界和安全示例。

## 目录

- `SKILL.md`：入口与渐进加载导航。
- `references/`：电气参数、兼容规则、集成、安全和来源。
- `examples/usage.md`：仅含 Markdown 内联 MicroPython 示例。
- `tests/validation-cases.md`：机器自检和人工验收项。
- `assets/`：Seeed Studio 官方产品图和引脚图。

## 使用与安装

保持顶层目录名为 `seeed-xiao-esp32s3-micropython`，将完整目录导入掌问 Hardware Skill 目录。不要改动单个声明文件或媒体元数据后沿用旧 revision。

## 验证状态

- 关键电气、引脚和 MicroPython API 已逐项核对 Seeed Studio 官方 Wiki。
- 未执行真实开发板运行、外设接线、低功耗、电流或无线测试。
- 当前环境没有掌问实际 `HardwareSkillRepository` 加载器；应用可见性为 `NOT_VERIFIED`，不能声称已出现在 ACTIVE 列表。
- 未提供机械档案：官方页面只确认 21 × 17.8 mm 长宽，缺少可靠高度和完整三维基准，按规范不猜测。

## 已知限制

- 本包针对基础版 XIAO ESP32S3，不把 Sense 的摄像头、麦克风和存储卡接口，也不把 Plus 的扩展引脚写成基础版能力。
- 官方 MicroPython 页面中的固件文件日期前后不一致；应选用与 ESP32-S3 和目标工具链兼容的当前官方 `ESP32_GENERIC_S3` 构建，并在目标板验证。
- 官方 MicroPython 页面中的一个 LED 示例使用 GPIO6，而硬件概览将用户 LED 标为 GPIO21；本包以硬件概览为准并要求验证 LED 有效电平。
