# 结构化电气参数

## 工程摘要

- 主控：ESP32-S3R8，Xtensa LX7 双核 32 位，最高 240 MHz；8 MB PSRAM、8 MB Flash。
- 官方供电基线：USB Type-C 输入 5 V；BAT 输入典型 3.7 V。机器参数选择 5 V 作为连续主输入单值，BAT 的独立典型输入保留在正文和 notes。
- 对外电源轨：3.3 V 稳压输出；USB 供电时 5V/VBUS 可作为输出。外部从 5V 引脚输入时必须串联二极管。
- 接口：1 路 UART、1 路 I2C、1 路 SPI、11 路 GPIO/PWM、9 路 ADC、用户 LED 和充电 LED。
- 官方典型功耗：基础版 Type-C 5 V 时约 19 mA，BAT 3.8 V 时约 22 mA；Wi-Fi active 约 100 mA，BLE active 约 85 mA；3.8 V deep sleep 约 14 µA。
- 工作温度：-20 °C 至 65 °C。
- 未知项：官方基础版页面未给出最大峰值电流、GPIO 绝对最大电流和完整机械高度。`peakCurrent` 的 0.0 表示未知，不表示零电流。

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_xiao_esp32s3",
  "name": "Seeed Studio XIAO ESP32S3（MicroPython）",
  "category": "MCU",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": 5.0,
    "voltageMax": 5.0,
    "supplyVoltages": [3.3, 5.0],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "GPIO",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": "machine",
    "firmwareRequirement": "与 XIAO ESP32S3 兼容的官方 MicroPython ESP32_GENERIC_S3 构建"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": ["3V3_LOGIC", "USB_5V", "BATTERY_POLARITY", "ESD_SENSITIVE"],
  "notes": "机器连续供电范围选择 USB Type-C 5V 单点；BAT 为独立典型 3.7V 输入。5V/VBUS 只有在相应供电条件下作为输出，外部从 5V 引脚输入必须串联二极管。3V3 为板载稳压输出，官方说明可取 700mA。基础版最大峰值电流未知，peakCurrent=0.0 表示未知而非零电流。GPIO 逻辑为 3.3V。仅适用于基础版 XIAO ESP32S3。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["seeed:xiao-esp32s3-hardware", "seeed:xiao-esp32s3-micropython", "seeed:wiki-license"]
}
```
