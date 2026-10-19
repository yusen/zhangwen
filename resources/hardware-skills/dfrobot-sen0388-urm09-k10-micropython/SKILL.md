---
name: dfrobot-sen0388-urm09-k10-micropython
description: 为 DFRobot SEN0388 URM09 Gravity 触发式超声波传感器接入行空板 K10 提供单线 TRIG/ECHO 接线、unihiker_k10 MicroPython 代码、兼容校验、机械参考包络和安全边界；用于 K10 P0/P1 测距代码生成、硬件方案校验、故障排查和传感器结构件设计，不适用于 SEN0307 模拟量版、SEN0304 I2C 版或双引脚 HC-SR04 用法。
---

# DFRobot SEN0388 URM09 × 行空板 K10 MicroPython

使用本 Skill 为 SEN0388 生成接线、代码、校验规则和参考结构件。

## 核心规则

- 将传感器 `+`、`-`、`D` 分别接到 K10 P1 的 3.3V、GND、Signal。
- 将同一个 P1 同时传给 `ultrasonic(trig=1, echo=1)`；`D` 是单线时分复用数字接口。
- 用 `.distance()` 直接取得厘米距离；不要生成 ADC 读取、电压比例或 `read_analog()` 代码。
- 有效量程为 2–500cm，最大测量频率为 25Hz；循环间隔不得短于 40ms，通用示例使用 100ms。
- K10 场景优先使用 3.3V 同源供电。SEN0388 官方供电范围为 3.3–5.5V，但不要向 K10 P1 输入 5V 数字信号。
- 不要混用 SEN0307 模拟量、SEN0304 I2C 或两根独立 TRIG/ECHO 的驱动方式。

## 使用流程

1. 读取 [电气参数](references/specifications.md) 与 [兼容规则](references/compatibility-rules.md) 完成选型校验。
2. 读取 [集成说明](references/integration.md) 与 [使用示例](examples/usage.md) 生成 K10 MicroPython 代码。
3. 读取 [安全边界](references/safety.md) 检查供电、插接和安装环境。
4. 设计外壳时读取 [机械档案](references/mechanical.md) 和 [CadQuery 参考模型](models/cadquery.py)，并保留探头声学视场。
5. 发布前按 [验证用例](tests/validation-cases.md) 完成实物复核。

## 资料入口

- [资料来源](references/sources.md)
- [机械档案](references/mechanical.md)
- [使用示例](examples/usage.md)

