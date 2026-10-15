# Grove - 三轴数字指南针 v2.0 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_be82233357d8",
  "name": "Grove - 三轴数字指南针 v2.0",
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
    "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Digitial_Compass_v2.0/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---三轴数字指南针-v20"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

Grove - 三轴数字指南针是一款基于 Bosch BMM150 的数字指南针传感器。它可以测量三个垂直轴上的磁场，并通过 I2C 和 SPI 接口读取输出，非常适合三轴移动应用。
