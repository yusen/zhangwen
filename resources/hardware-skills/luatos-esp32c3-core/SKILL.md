---
name: luatos-esp32c3-core
description: esp32C3 经典串口板型；51×21mm PCB、Type-C/CH343P、4MB Flash，附引脚与暂定高度的3D结构参考。
---

# esp32C3

适用于用户提供的蓝色 CORE-ESP32、独立八脚 Flash、RST/BOOT 和 Type-C 布局，与官方经典款资料一致。具体批次须核对背面型号和串口芯片；不将此身份套到无 USB-UART 芯片的 USB 直连精简款、SuperMini 或乐鑫 DevKitM。

- [电气与引脚](references/specifications.md)
- [MicroPython 与连接](references/integration.md)
- [结构尺寸、假设与避让](references/mechanical.md)
- [兼容规则](references/compatibility-rules.md)
- [供电与边界](references/safety.md)
- [来源与冲突说明](references/sources.md)
- [最小使用示例](examples/usage.md)
- [验证清单](tests/validation-cases.md)

结构参考可用于初步布局；板厚、器件三轴位置与高度暂定，不是精密制造图。模型仅文本和数据，不授予命令、串口或设备执行权限。
