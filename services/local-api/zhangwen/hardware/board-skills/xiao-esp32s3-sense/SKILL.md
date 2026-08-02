---
name: xiao-esp32s3-sense-micropython-engineer
description: 为 Seeed Studio XIAO ESP32S3 Sense 编写保守、可验证的 MicroPython 程序。
version: 1.0.0
target: Seeed Studio XIAO ESP32S3 Sense
runtime: MicroPython
primary_profile: xiao_esp32s3_sense
---

# XIAO ESP32S3 Sense MicroPython 工程约束

只为 `seeedstudio/xiao_esp32s3_sense` 生成代码，不得把通用 ESP32-S3 或其他 XIAO 型号当作等价板型。

- 以 8 MB Flash、8 MB OPI PSRAM 档案为准。
- 摄像头、PDM 麦克风、SPI microSD 和 USB Serial/JTAG 的引脚与可用 API必须由当前固件档案确认。
- SD 启用后，GPIO21 与用户 LED 冲突；不得同时驱动。
- 未在引用资料或当前固件探测中确认的摄像头、音频、SD API 必须标记为能力待确认，不得编造导入或函数。
- 外接器件可以使用，但不能引入第三种主控板。
- 上传前保留用户同名文件；不得擦除整片 Flash，不得覆盖凭据或隐式执行固件烧录。
- 执行器输出须限制范围、刷新率，并在异常或断连时回到安全值。

优先从最小能力探测开始，再按探测结果适配代码。输出应说明固件前提、引脚冲突、接线和验证步骤。
