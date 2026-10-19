# 结构化电气参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_esp32_generic_c3",
  "name": "ESP32-C3（通用 MicroPython）",
  "category": "MCU",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": null,
    "voltageMax": null,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "GPIO",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": "machine",
    "firmwareRequirement": "ESP32_GENERIC_C3 MicroPython；4MB及以上Flash，USB串口支持取决于接线与板卡"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [
    "3.3V逻辑",
    "USB供电",
    "无自动烧录"
  ],
  "notes": "ESP32_GENERIC_C3 MicroPython，GPIO 为 3.3V；USB供电经过开发板稳压。通用芯片档案不声明板载 LED、屏幕或开发板别名引脚。峰值电流未固化，0为未知占位。",
  "verificationStatus": "OFFICIAL_API_REFERENCE_UNTESTED",
  "sourceIds": [
    "https://micropython.org/download/ESP32_GENERIC_C3/"
  ]
}
```
