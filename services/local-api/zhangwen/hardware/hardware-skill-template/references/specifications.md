# 结构化电气参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "<唯一硬件ID>",
  "name": "<硬件显示名称>",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.3,
    "voltageMax": 3.3,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.05,
    "communicationProtocol": "I2C",
    "i2cAddress": null,
    "supportedMCUs": ["unihiker-k10"],
    "driverName": null,
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [],
  "notes": "<补充规格边界>",
  "verificationStatus": "USER_CONFIRMED",
  "sourceIds": ["<资料来源标识>"]
}
```
