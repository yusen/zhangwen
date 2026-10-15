# DFR0029 结构化规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_dfr0029_button",
  "name": "DFR0029 Gravity 数字按钮",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.3,
    "voltageMax": 5.0,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.02,
    "communicationProtocol": "GPIO_DIGITAL",
    "i2cAddress": null,
    "supportedMCUs": ["hw_seed_unihiker_k10", "unihiker-k10", "k10", "esp32-s3"],
    "driverName": "digital_button",
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 6,
  "safetyTags": ["K10方案固定3.3V", "软件去抖", "使用前确认输入极性"],
  "notes": "官方规格：3.3–5V、数字接口、板载指示灯、尺寸22×30mm。官方未给出最大电流；目录暂按20mA保守预算，量产前必须实测。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["https://wiki.dfrobot.com/dfr0029-b/"]
}
```
