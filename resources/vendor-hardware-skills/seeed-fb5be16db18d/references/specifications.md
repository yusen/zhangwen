# Grove - 温湿度传感器 (高精度&迷你) v1.0 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_fb5be16db18d",
  "name": "Grove - 温湿度传感器 (高精度&迷你) v1.0",
  "category": "SENSOR",
  "electrical": {
    "voltage": 0,
    "logicLevel": 0,
    "peakCurrent": 0,
    "communicationProtocol": "UNKNOWN",
    "supportedMCUs": [],
    "firmwareRequirement": "待核对官方固件与驱动"
  },
  "verificationStatus": "UNVERIFIED",
  "sourceIds": [
    "https://wiki.seeedstudio.com/cn/Grove-TemptureAndHumidity_Sensor-High-Accuracy_AndMini-v1.0/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---温湿度传感器-高精度迷你-v10"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

这是一款多功能传感器，可同时提供温度和相对湿度信息。它采用TH02传感器，这是一款数字I2C湿度温度传感器，可满足一般用途的测量需求。在环境湿度条件为0-80% RH，温度条件为0-70°C时，它能够提供可靠的读数，覆盖了大多数家庭和日常应用中不含极端条件的需求。
