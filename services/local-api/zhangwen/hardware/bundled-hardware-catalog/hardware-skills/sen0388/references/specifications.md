# SEN0388 结构化规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_sen0388",
  "name": "SEN0388 URM09 超声波测距传感器",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.3,
    "voltageMax": 5.5,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.02,
    "communicationProtocol": "SINGLE_WIRE_TRIG_ECHO",
    "i2cAddress": null,
    "supportedMCUs": ["hw_seed_unihiker_k10", "unihiker-k10", "k10", "esp32-s3"],
    "driverName": "urm09",
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 8,
  "safetyTags": ["K10方案推荐3.3V供电", "单线TRIG_ECHO", "必须处理超时"],
  "notes": "官方规格：3.3–5.5V DC，最大瞬时电流小于20mA，量程2–500cm，分辨率1cm，精度1%，最大25Hz，尺寸47×22mm。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["https://wiki.dfrobot.com/sen0388/"]
}
```
