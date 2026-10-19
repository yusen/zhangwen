# 结构化电气参数

## 工程摘要

- SoC：D-Robotics Sunrise 5；CPU 为 8 × 1.5 GHz Arm Cortex-A55，BPU 为 10 TOPS INT8，GPU 为 32 GFLOPS。
- 内存：4 GB 或 8 GB LPDDR4；存储为 1 Gbit NAND 和支持 UHS-I 的 microSD。
- 主供电：官方要求 5 V / 5 A DC Type-C 适配器；机器供电范围采用单点 5.0 V。
- 对外电源轨：40PIN 提供 3.3 V 与 5 V。不同官方页面对 40PIN 单接口负载给出 1 A/1 A 与 800 mA/500 mA 两组数据；本包安全设计采用后者作为保守上限，并要求多接口同时使用时重新核算。
- 40PIN：28 个 3.3 V GPIO，支持 SPI、I2C、I2S、PWM、UART；GPIO 最大耐压 3.46 V。
- 显示：4-lane MIPI DSI v1.2、HDMI Type-A，最高 1080p@60fps。
- 相机：2 × 4-lane MIPI CSI-2 v2.1；网络包含千兆以太网/PoE、Wi-Fi 6 与 Bluetooth 5.4。
- 工作温度：-20 °C 至 +60 °C。
- 未知项：官方未给出开发板实际最大峰值输入电流或所有负载组合下的总输出能力。`peakCurrent` 的 0.0 表示未知，不表示零电流；5 A 是推荐适配器能力，不是实测板卡峰值。

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_drobotics_rdk_x5",
  "name": "D-Robotics RDK X5",
  "category": "MCU",
  "electrical": {
    "voltage": 5.0,
    "voltageMin": 5.0,
    "voltageMax": 5.0,
    "supplyVoltages": [3.3, 5.0],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "GPIO",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": "Hobot.GPIO",
    "firmwareRequirement": "RDK OS 3.x；3.0.0 及以上为 Ubuntu 22.04，并包含匹配 RDK X5 的 hobot-gpio"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": ["5V_5A_INPUT", "3V3_LOGIC", "THERMAL_MANAGEMENT", "ESD_SENSITIVE", "NO_HOT_PLUG_CAMERA"],
  "notes": "标准版 RDK X5 使用 5V/5A Type-C 独立适配器；不得用电脑 USB 口作为主供电。40PIN 逻辑为3.3V，最大耐压3.46V，暴露3.3V和5V电源轨。不同官方页的40PIN输出能力存在1A/1A与800mA/500mA差异，本包采用800mA@3.3V、500mA@5V的保守限制。peakCurrent=0.0表示开发板实际最大峰值未知，5A只是适配器能力。仅适用于全板载标准版RDK X5，不适用于RDK X5 Module。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["drobotics:rdk-x5-spec-v1.1", "drobotics:rdk-x5-hardware", "drobotics:rdk-x5-40pin", "drobotics:rdk-doc-license"]
}
```
