# 结构化电气参数

## 工程摘要

- 官方供电：USB 5V；或未连接 USB 时从 3V3 金手指输入 2.7–3.6V。
- 官方工作电压：3.3V；最大工作电流 700mA；最大负载电流 1000mA。
- 机器工作点采用 3.3V；连续供电范围采用未接 USB 时 3V3 端的 2.7–3.6V；对外离散电源轨仅声明 3.3V。
- 逻辑基线为 3.3V，峰值电流采用官方最大工作电流 0.7A；I2C、UART、SPI、PWM、ADC 和触摸能力保留在正文。
- 未知项：各工作模式的典型电流、外接负载可用电流随供电方式的降额、接口保护绝对最大值。

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_mpython_esp32s3_v3",
  "name": "掌控板 3.0（ESP32-S3）",
  "category": "MCU",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 2.7,
    "voltageMax": 3.6,
    "supplyVoltages": [
      3.3
    ],
    "logicLevel": 3.3,
    "peakCurrent": 0.7,
    "communicationProtocol": "GPIO",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": "mpython",
    "firmwareRequirement": "掌控板 3.0 官方 MicroPython 固件（基于 MicroPython 与 ESP-IDF）"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": [
    "3V3_LOGIC",
    "USB_POWER",
    "ESD_SENSITIVE"
  ],
  "notes": "voltage=3.3V 为官方工作点；voltageMin=2.7V、voltageMax=3.6V 对应未接 USB 时 3V3 金手指的连续供电范围。USB 5V 是独立输入路径，不表示 3V3 端可接受 5V。supplyVoltages=[3.3] 表示金手指实际暴露的离散外设电源轨。peakCurrent=0.7 表示官方最大工作电流 700mA；官方另列最大负载电流 1000mA。communicationProtocol 以 GPIO 作为单值基线，正文保留 I2C、UART、SPI、PWM、ADC 和触摸能力。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": [
    "official:index",
    "official:technical",
    "official:io",
    "official:api",
    "official:dimensions"
  ]
}
```

## 板载硬件

| 功能 | 官方规格 |
|---|---|
| MCU | ESP32-S3，Xtensa 32 位 LX7 双核，240MHz，512KB SRAM |
| 存储 | 16MB Flash、8MB PSRAM |
| 无线 | IEEE 802.11 b/g/n；Bluetooth 5、Bluetooth Mesh |
| 显示 | 1.47 英寸 ST7789 LCD，320×172 |
| 传感器 | LTR-308ALS-01 光线、双麦克风、MMC5603NJ 磁传感器、QMI8658C 六轴 |
| 人机接口 | A/B/Reset，P/Y/T/H/O/N 六路触摸，3 颗 RGB LED |
| 音频 | ES8388 编解码、NS4150 功放、1W 贴片喇叭 |
