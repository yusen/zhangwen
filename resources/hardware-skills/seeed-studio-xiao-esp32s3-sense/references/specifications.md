# 结构化电气参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_xiao_esp32s3_sense",
  "name": "Seeed Studio XIAO ESP32S3 Sense",
  "category": "MCU",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": 5.0,
    "voltageMax": 5.0,
    "supplyVoltages": [
      3.3,
      5.0
    ],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "GPIO/I2C/SPI/PDM/USB/Wi-Fi/Bluetooth LE",
    "i2cAddress": null,
    "supportedMCUs": [
      "seeedstudio/xiao_esp32s3_sense",
      "xiao-esp32s3-sense"
    ],
    "driverName": "xiao_esp32s3_sense",
    "firmwareRequirement": "XIAO ESP32S3 Sense exact-board MicroPython or verified application package"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 8,
  "safetyTags": [
    "USB 5V供电",
    "3.3V逻辑",
    "GPIO21与microSD片选冲突",
    "执行器需独立供电"
  ],
  "notes": "规范板型 seeedstudio/xiao_esp32s3_sense；8 MB Flash、8 MB OPI PSRAM，Sense 扩展含 OV2640、PDM 麦克风和 SPI microSD。peakCurrent=0 表示未固化整板峰值，并非实际电流为零。",
  "verificationStatus": "MIGRATED_UNVERIFIED",
  "sourceIds": [
    "sqlite:hw_seeed_xiao_esp32s3_sense"
  ]
}
```
