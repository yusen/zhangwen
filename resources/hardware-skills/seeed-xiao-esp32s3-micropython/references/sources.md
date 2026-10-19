# 资料来源

| sourceId | 类型 | URL/标识 | 支持的事实 | 核对状态 |
|---|---|---|---|---|
| seeed:xiao-esp32s3-micropython | Seeed Studio 官方 Wiki | https://wiki.seeedstudio.com/cn/xiao_esp32s3_with_micropython/ | MicroPython 固件方向、machine/network API、GPIO/ADC/PWM/UART/I2C/SPI/Timer 示例与页面冲突 | 已核对，2026-07-17 |
| seeed:xiao-esp32s3-hardware | Seeed Studio 官方 Wiki | https://wiki.seeedstudio.com/cn/xiao_esp32s3_getting_started/ | 基础版芯片、存储、无线、供电、典型功耗、温度、尺寸、引脚、3V3/5V 边界 | 已核对，2026-07-17 |
| seeed:wiki-license | Seeed Studio 官方 Wiki | https://wiki.seeedstudio.com/cn/License/ | 文档与图片 CC BY-SA 4.0；嵌入代码与软件库默认 MIT，第三方内容按各自许可 | 已核对，2026-07-17 |

## 证据边界

- 图片来自 Seeed Studio 官方 XIAO ESP32S3 Wiki 资源，并按其文档/图片许可记录署名。
- 未把搜索摘要、非官方教程、商品评论或 AI 推断作为官方参数依据。
- 官方页面混合基础版、Sense 和 Plus 表格；本包只提取基础版列，并把不一致写入集成说明。
- 官方页面未给出基础版完整高度和最大峰值电流，因此分别省略机械档案并将机器峰值设为未知。
