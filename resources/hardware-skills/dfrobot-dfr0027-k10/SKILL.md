---
name: dfrobot-dfr0027-k10
description: 为行空板 K10 MicroPython 项目提供 DFR0027 的GPIO接入、兼容和安全边界；API 与电气值仍需按当前固件和实物复核。
---

# DFRobot DFR0027 数字震动传感器

本 Skill 为 DFR0027 提供电气、兼容、集成和安全事实。

## 核心边界

- 推荐机器基线：3.3 V 供电、3.3 V 逻辑、GPIO 通信。
- 以 3.3 V 逻辑为接入基线；上电前复核模块丝印和官方页面。
- 峰值电流、具体 K10 引脚和当前固件 API 尚未逐项实测。

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [兼容规则](references/compatibility-rules.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)
