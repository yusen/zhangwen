---
id: unihiker-k10
name: 行空板 K10
aliases: 行空板K10, K10, UNIHIKER K10, DFRobot K10
platform: ESP32-S3 N16R8
language: micropython
---

# 行空板 K10 BoardProfile

## 身份与运行时

- 主控模块：ESP32-S3 N16R8，Xtensa LX7 双核，最高 240 MHz。
- 存储：16 MB Flash、8 MB PSRAM；片上 SRAM 512 KB、ROM 384 KB、RTC SRAM 16 KB。
- 默认代码语言：MicroPython。
- K10 专用模块：优先使用 `unihiker_k10`、`k10_base` 和官方示例中声明的 API，不套用通用 ESP32 引脚或驱动名称。
- 日常代码更新：优先 USB-C 串口文件上传；不得因普通代码修改擦除 Flash 或重刷 MicroPython 固件。

## 板载资源

- 2.8 英寸 240 x 320 ILI9341 彩色 LCD。
- GC2145 2 MP 摄像头，官方标注 80 度视场角。
- AHT20 温湿度传感器。
- LTR303ALS 环境光传感器，官方标注 0-64k Lux。
- SC7A20H 三轴加速度计，量程支持 +/-2G、+/-4G、+/-8G、+/-16G。
- 双 MEMS 麦克风、2 W 扬声器、3 颗 WS2812 RGB LED。
- A、B、RST、BOOT 按键和 TF 卡槽。

## 接口与供电

- USB-C：5 V 供电和程序上传。
- 2Pin PH2.0 电池接口：3.0-6.0 V DC；官方推荐 3.7 V 锂电池或 3 节 1.5 V 电池。
- 3Pin PH2.0 全功能 GPIO x2。
- 4Pin PH2.0 I2C x1。
- 金手指扩展：全功能 GPIO x2、I2C x1、数字 IO x15。
- GPIO 逻辑按 3.3 V 设计。连接 5 V 逻辑外设前必须增加电平转换或确认模块兼容。
- 官方规格页未给出整板峰值电流。涉及摄像头、屏幕、扬声器、电机或舵机时，必须单独核算电源并实测，不得猜测额定电流。

## MicroPython API 线索

- 屏幕：`from unihiker_k10 import screen`。
- 按键、温湿度、光线、加速度、RGB、麦克风和扬声器：使用 `unihiker_k10` 对应模块。
- 摄像头、TF 卡、Wi-Fi 和 MQTT：官方示例使用 `k10_base` 对应类。
- 通用扩展口：官方示例使用 `from unihiker_k10 import pin`，以端口编号初始化；生成代码前仍需根据原理图或已确认 IO Map 复核端口能力。

## 生成代码前检查

1. 确认项目选择的是 K10，而不是行空板 M10 或通用 ESP32-S3。
2. 优先复用板载传感器和显示资源，避免重复选型。
3. 对外接执行器确认端口、电压、电流、驱动和独立供电需求。
4. 把 Wi-Fi 密码、令牌和服务地址放入本地配置，不写入代码产物、日志或 Git。
5. 先运行无硬件副作用的语法、导入和逻辑检查；真实上传后再做设备重连、异常日志和核心功能验证。

## 官方来源

- K10 文档入口：https://www.unihiker.com/wiki/K10/
- 硬件规格：https://www.unihiker.com/wiki/K10/HardwareReference/hardwarereference_specs/
- MicroPython 示例：https://www.unihiker.com/wiki/K10/Examples/examples_mpy/

本文只固化上述官方页面可核对内容。完整引脚复用、原理图细节和固件兼容性应在具体项目中再次确认。
