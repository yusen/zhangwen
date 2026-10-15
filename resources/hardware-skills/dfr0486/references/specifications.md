# DFR0486 结构化规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_dfr0486",
  "name": "DFR0486 Gravity SSD1306 OLED",
  "category": "DISPLAY",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.3,
    "voltageMax": 5.0,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.02275,
    "communicationProtocol": "I2C",
    "i2cAddress": "0x3C",
    "supportedMCUs": ["hw_seed_unihiker_k10", "unihiker-k10", "k10", "esp32-s3"],
    "driverName": "ssd1306",
    "firmwareRequirement": null
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 8,
  "safetyTags": ["K10方案推荐3.3V供电", "确认I2C地址", "限制全屏刷新频率"],
  "notes": "官方规格：3.3–5V，128×64，Gravity-I2C，60fps，满屏功耗约22.75mA，模块41.20×26.20mm，15g。地址0x3C按模块SSD1306资料登记，使用前仍应扫描确认。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["https://wiki.dfrobot.com/dfr0486/"]
}
```
