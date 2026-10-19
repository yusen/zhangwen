---
name: dfrobot-sen0305-k10
description: 为行空板 K10 MicroPython 项目提供 SEN0305 的I2C接入、兼容和安全边界；API 与电气值仍需按当前固件和实物复核。
---

# DFRobot SEN0305 HUSKYLENS 二哈 AI 摄像头

本 Skill 为 SEN0305 提供电气、兼容、集成和安全事实。

## 核心边界

- 推荐机器基线：5.0 V 供电、3.3 V 逻辑、I2C 通信。
- HUSKYLENS 官方范围为 3.3–5.0 V；本包机器基线取 5.0 V，逻辑基线仍为 3.3 V。
- 峰值电流、具体 K10 引脚和当前固件 API 尚未逐项实测。

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [兼容规则](references/compatibility-rules.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)
