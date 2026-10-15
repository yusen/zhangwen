# DFR0026 结构化电气参数

## 工程摘要

- 类型：PT550 光敏二极管模拟环境光传感器。
- 官方供电范围：3.0–5.0 VDC；本包机器可读参数采用 3.3 V 安全集成基线。
- 输出：模拟电压。使用 5 V 供电时，必须先确认目标 ADC 输入上限，不能直接假定 3.3 V ADC 可承受。
- 接口：Gravity / PH2.0-3P，信号、VCC、GND。
- 官方资料给出 1–6000 lux 和约 15 μs 响应时间，但模块不直接输出经过标定的 lux 数值。
- 主控必须提供 ADC；原始值只表示相对亮度，除非已针对板卡、供电和光学结构完成标定。

## 机器可读规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_dfr0026",
  "name": "DFRobot DFR0026 模拟环境光线传感器",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.0,
    "voltageMax": 5.0,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "ANALOG",
    "i2cAddress": null,
    "supportedMCUs": [
      "unihiker-k10",
      "esp32-s3",
      "esp32",
      "rp2040",
      "generic-micropython-adc"
    ],
    "driverName": "machine.ADC",
    "firmwareRequirement": "MicroPython with machine.ADC support"
  },
  "stock": 0,
  "price": 20.0,
  "ageRecommendation": 8,
  "safetyTags": [
    "官方供电范围3-5V",
    "机器参数采用3.3V安全基线",
    "5V供电时必须校核ADC过压",
    "必须共地",
    "工作电流未知需实测"
  ],
  "notes": "推荐以3.3V供电并连接3.3V ADC。官方资料允许3-5V供电；若使用5V，必须确认模拟输出上限并增加必要的分压或缓冲保护。peakCurrent=0表示资料未提供，不表示零电流。结构档案采用用户参考模型30x22mm，官方页面标称20x30mm，制造前必须实物复核。",
  "verificationStatus": "SOURCE_VERIFIED_WITH_MECHANICAL_CONFLICT",
  "sourceIds": [
    "dfrobot-wiki:dfr0026",
    "dfrobot-product:dfr0026",
    "user-model:dfr0026-2026-07-16"
  ]
}
```

## 资料中保留但不进入当前机器模型的参数

- 官方标称量程：1–6000 lux。
- 官方标称响应时间：约 15 μs。
- 接线顺序：Signal、VCC、GND；官方线色为绿、红、黑。
- 官方资料未给出可靠的工作电流，因此电流预算必须在真实项目中补测。
