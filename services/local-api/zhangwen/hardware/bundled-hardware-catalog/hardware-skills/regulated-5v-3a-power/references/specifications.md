# 结构化供电要求

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_power_5v_3a_regulated",
  "name": "外接稳压 5V/3A 电源",
  "category": "POWER",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": 5.0,
    "voltageMax": 5.0,
    "supplyVoltages": [5.0],
    "logicLevel": 0.0,
    "peakCurrent": 3.0,
    "communicationProtocol": "POWER",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": null,
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 12,
  "safetyTags": ["实物铭牌必须5V且不低于3A", "必须核对极性", "需短路与过流保护", "与K10共地但不反向供电"],
  "notes": "通用供电要求，不代表已核验的具体产品。DFR0523 官方峰值电流为 2.5A，因此闭环固定选择额定不低于 5V/3A 的稳压电源。",
  "verificationStatus": "REQUIREMENT_VERIFIED",
  "sourceIds": ["https://wiki.dfrobot.com/dfr0523/"]
}
```
