---
name: seeed-xiao-esp32s3-micropython
description: 为基础版 Seeed Studio XIAO ESP32S3 提供 3.3V 电气边界、GPIO/ADC/PWM/UART/I2C/SPI 引脚映射、官方 MicroPython machine/network API、安全接线和示例；用于编写或核对 XIAO ESP32S3 MicroPython 硬件方案，并排除 Sense/Plus 专属能力和未经验证的烧录操作。
---

# Seeed Studio XIAO ESP32S3（MicroPython）

本 Skill 为基础版 Seeed Studio XIAO ESP32S3 提供电气、兼容、集成和安全事实。

## 核心边界

- GPIO 逻辑基线为 3.3 V；推荐从 USB Type-C 的 5 V 或 BAT 的典型 3.7 V 输入供电，不得把 5 V 直接施加到 GPIO。
- 5V 引脚外部供电必须按官方要求串联二极管；3V3 是稳压输出，官方说明最多可取 700 mA，但仍需核算板卡与负载热耗散。
- 仅针对基础版，不把 XIAO ESP32S3 Sense 或 Plus 的专属硬件写为本板能力。
- 未提供机械档案，因为官方资料缺少完整高度和三维基准；未知峰值电流以 0.0 表示“未知”，不表示零电流。
- 不授予文件、Shell、网络、串口、上传、Flash 擦除或固件烧录权限；凭据只允许运行时安全注入。

## 工作方式

1. 先读取规格和安全边界，再选择引脚与总线。
2. 对照集成表区分 XIAO 丝印编号和 ESP32-S3 GPIO 编号；MicroPython `Pin()` 使用实际 GPIO 号。
3. 使用示例作为起点，并根据目标固件的实际 API 做小步验证。
4. 涉及供电、无线、低功耗或板载 LED 时，保留官方资料中的未知和冲突，不做推断。

## 渐进加载

- [结构化电气参数](references/specifications.md)
- [兼容规则](references/compatibility-rules.md)
- [集成说明](references/integration.md)
- [安全边界](references/safety.md)
- [资料来源](references/sources.md)
- [使用示例](examples/usage.md)
- [验证用例](tests/validation-cases.md)
