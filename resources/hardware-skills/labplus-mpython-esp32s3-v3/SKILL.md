---
name: labplus-mpython-esp32s3-v3
description: 掌控板 3.0 ESP32-S3 主控的 3.3V 电气、板载硬件、GPIO/I2C/UART/SPI、完整 mPython 官方类库、示例和结构包络边界。
---

# 掌控板 3.0（ESP32-S3）

本 Skill 为掌控板 3.0 提供电气、兼容、集成、结构和安全事实。

## 核心边界

- 工作电压为 3.3V；可由 USB 5V 供电，或在未接 USB 时从 3V3 金手指输入 2.7–3.6V。
- GPIO 和外设总线按 3.3V 逻辑处理，禁止把 5V 信号直接接入。
- 官方最大工作电流为 700mA、最大负载电流为 1000mA；外接负载仍须独立核算供电和散热。
- P19/P20 的 I2C 与板载传感器共享总线，扩展设备必须检查地址和上拉冲突。

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
