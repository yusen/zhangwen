# SEN0193 结构化规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_sen0193",
  "name": "SEN0193 电容式土壤湿度传感器",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.3,
    "voltageMax": 5.5,
    "supplyVoltages": [],
    "logicLevel": 3.0,
    "peakCurrent": 0.005,
    "communicationProtocol": "ADC",
    "i2cAddress": null,
    "supportedMCUs": ["hw_seed_unihiker_k10", "unihiker-k10", "k10", "esp32-s3"],
    "driverName": "soil_moisture",
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 8,
  "safetyTags": ["推荐3.3V供电", "模拟输出不超过3.0V", "仅探针防腐不代表整板防水", "使用前必须干湿标定"],
  "notes": "官方规格：工作电压 3.3–5.5V，工作电流 5mA，模拟输出 0–3.0V，PH2.0-3P，尺寸 3.86×0.905 英寸（约 98.0×23.0mm），重量 15g。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["https://wiki.dfrobot.com/sen0193/"]
}
```
