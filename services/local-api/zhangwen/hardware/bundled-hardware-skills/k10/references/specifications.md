# 行空板 K10 结构化电气参数

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seed_unihiker_k10",
  "name": "行空板 K10",
  "category": "MCU",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": 5.0,
    "voltageMax": 5.0,
    "supplyVoltages": [3.3, 5.0],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "GPIO/I2C/UART/Wi-Fi/Bluetooth LE",
    "i2cAddress": null,
    "supportedMCUs": [
      "unihiker-k10",
      "k10",
      "esp32-s3",
      "esp32-s3-n16r8"
    ],
    "driverName": "unihiker_k10",
    "firmwareRequirement": "K10 MicroPython firmware with unihiker_k10 and k10_base modules"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": 8,
  "safetyTags": [
    "USB-C 5V供电",
    "PH2.0电池3.0-6.0V安全工作区",
    "3.3V逻辑",
    "GPIO输入不得超过3.6V",
    "高功率负载需独立供电",
    "整板峰值电流需按应用实测"
  ],
  "notes": "DFRobot DFR0992；ESP32-S3 N16R8。整板推荐 5V 供电，对外设提供离散 3.3V/5V 电源轨；外设信号仍必须按 3.3V GPIO/ADC 上限独立校验。peakCurrent=0 表示公开资料未给出整板峰值，不表示实际电流为零。结构与模型见同一 Skill 的 mechanical.md 和 cadquery.py。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": [
    "https://www.unihiker.com.cn/wiki/k10/jianjie",
    "https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10",
    "user-verified:unihiker-k10-structure-2026-07-16"
  ]
}
```

## 板载能力摘要

| 类别 | 器件或能力 | MicroPython 入口 |
|---|---|---|
| 显示 | 2.8 英寸 240×320 LCD | `unihiker_k10.screen` |
| 摄像头 | GC2145 | `k10_base.Camera` / `ai` |
| 温湿度 | AHT20 | `unihiker_k10.temp_humi` |
| 环境光 | LTR303ALS | `unihiker_k10.light` |
| 加速度 | SC7A20H | `unihiker_k10.acce` |
| 音频 | 双 MEMS 麦克风、2 W 扬声器 | `mic` / `speaker` |
| 扩展 | P0/P1、I2C、金手指、TF 卡 | `pin` / `TF_card` |
