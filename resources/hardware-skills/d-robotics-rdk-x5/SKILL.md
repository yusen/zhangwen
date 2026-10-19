---
name: d-robotics-rdk-x5
description: 为标准版 D-Robotics RDK X5 提供 5V/5A 供电、3.3V 40PIN、GPIO/PWM/I2C/SPI/UART、USB、MIPI CSI/DSI、HDMI、CAN FD、网络、Hobot.GPIO、RDK OS 与 85×56×20mm 包络边界；用于编写或核对 RDK X5 硬件集成、外设接线和结构方案，并排除 X5 Module 专属接口及未经验证的烧录操作。
---

# D-Robotics RDK X5

本 Skill 为标准版 RDK X5 提供电气、兼容、集成、结构和安全事实。

## 核心边界

- 使用支持 5 V / 5 A 的独立 Type-C 电源适配器；官方明确不建议使用电脑 USB 口供电。
- 40PIN 数字 IO 是 3.3 V 逻辑，官方 40PIN 文档给出的最大耐压为 3.46 V；严禁接入 5 V 信号。
- MIPI Camera 与 TF 卡禁止带电插拔；相机排线方向、CAN 终端和外设电流必须在断电状态检查。
- 机械能力仅为 85 × 56 × 20 mm 包络，安装孔中心、接口开口和禁布区仍需官方 CAD 或实物复核。
- 不授予文件、Shell、网络、串口、上传、擦除或固件烧录权限；本 Skill 中的示例不自动执行。

## 工作方式

1. 先读规格与安全边界，确认标准版而不是 Module。
2. 对照官方 40PIN 图选择物理针脚，并检查 `srpi-config` 中的复用关系。
3. 使用 RDK OS 自带 `Hobot.GPIO` 时优先采用 BOARD 物理针脚编号，并始终清理资源。
4. 进行相机、显示、CAN、USB 或高负载集成前，先核算各接口电流和 25 W 输入能力。
5. 结构设计只把包络作为占位，孔位和开口必须用官方 2D/3D 资料复核。

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [兼容规则](references/compatibility-rules.md)
- [结构与机械档案](references/mechanical.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)
- [CadQuery 参考模型](models/cadquery.py)
