# DFR0523 结构化规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_dfr0523",
  "name": "DFR0523 数字蠕动泵",
  "category": "ACTUATOR",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": 5.0,
    "voltageMax": 6.0,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 2.5,
    "communicationProtocol": "PWM",
    "i2cAddress": null,
    "supportedMCUs": ["hw_seed_unihiker_k10", "unihiker-k10", "k10", "esp32-s3"],
    "driverName": "pump",
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 10,
  "safetyTags": ["独立稳压5V/3A供电", "不得由GPIO或K10供电", "必须与主控共地", "默认停泵", "单次最长3秒"],
  "notes": "官方驱动板输入 5–6V，连续电流 1.8A，峰值 2.5A；PPM 500Hz、500–2500us，1400–1600us 为停止区。驱动板 27.4×28.7mm，泵额定 6V/5W，最大流量约 85ml/min。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["https://wiki.dfrobot.com/dfr0523/"]
}
```
