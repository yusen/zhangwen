# 结构化电气参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_mpython_v2",
  "name": "掌控板 2.0（ESP32）",
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
    "driverName": "mpython",
    "firmwareRequirement": "掌控板2.x官方mPython MicroPython固件，含mpython.oled"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [
    "3.3V逻辑",
    "USB供电",
    "无自动烧录"
  ],
  "notes": "经典掌控板 ESP32 / 128×64 OLED，3.3V逻辑，USB供电。使用 mpython.oled，不使用掌控3.0的display/LCD API。具体2.x批次传感器可能不同。峰值电流未固化，0为未知占位。",
  "verificationStatus": "OFFICIAL_API_REFERENCE_UNTESTED",
  "sourceIds": [
    "https://mpython.readthedocs.io/en/master/library/mPython/mpython.html"
  ]
}
```
