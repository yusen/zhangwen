---
name: dfr0026-ambient-light-sensor
description: DFRobot DFR0026 模拟环境光线传感器硬件档案；包含3–5V模拟电气规格、MicroPython ADC案例、机械档案、CadQuery参考模型、兼容规则与安全边界。
---

# DFRobot DFR0026 模拟环境光线传感器

本 Skill 为 DFR0026（PT550、Gravity PH2.0-3P）提供电气、接线、MicroPython、结构、图片和验证事实。

## 核心边界

- 供电 3–5 V；模拟输出按 0–5 V 最大值保守校核。
- 目标主控必须提供 ADC；3.3 V-only ADC 不能直接承受潜在 5 V 输出。
- ADC 原始值表示相对光强，未经标定不能当作 lux。
- 精细机械档案采用用户模型 30 × 22 mm；官方标称 20 × 30 mm，制造前必须实物复核。
- CadQuery 源码为 `REFERENCE_ONLY`，不授予模型执行、文件、Shell、串口或设备权限。

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [机械档案](references/mechanical.md)
- [兼容规则](references/compatibility-rules.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [MicroPython 使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)
- [CadQuery 参考模型](models/cadquery.py)
