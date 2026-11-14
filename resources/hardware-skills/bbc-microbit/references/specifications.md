# 结构化电气参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_bbc_microbit",
  "name": "BBC micro:bit（V1 / V2）",
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
    "driverName": "microbit",
    "firmwareRequirement": "官方 micro:bit MicroPython；V1/V2 API 分别核对，USB 数据线及串口 REPL 可用"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [
    "3.3V逻辑",
    "V1/V2差异",
    "不自动刷写固件"
  ],
  "notes": "Micro USB 数据线连接，3V 引脚与USB输入不可混同；GPIO不直接承受5V。5×5点阵、A/B按钮与加速度计。V2专有硬件单独核对。外形/孔位尚未提供机械档案。",
  "verificationStatus": "OFFICIAL_REFERENCE_UNTESTED",
  "sourceIds": [
    "https://microbit-micropython.readthedocs.io/en/v2-docs/",
    "https://microbit-micropython.readthedocs.io/en/v2-docs/filesystem.html",
    "https://microbit-micropython.readthedocs.io/en/v2-docs/devguide/repl.html",
    "https://python.microbit.org/v/3"
  ]
}
```
