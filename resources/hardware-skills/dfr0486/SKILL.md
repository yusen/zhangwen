---
name: dfr0486
description: DFRobot DFR0486 Gravity SSD1306 I2C OLED 的受信规格、K10 接线与显示安全规则。
---

# DFR0486 OLED

- K10 方案使用 3.3V、GND、SCL、SDA，默认 I2C 地址按官方模块资料登记为 `0x3C`。
- 分辨率 128×64，不能把它当作 K10 板载屏 API。
- 更新频率应受限，避免无意义的全屏高频刷新。
- 本包不授予文件、Shell、串口或网络权限。
