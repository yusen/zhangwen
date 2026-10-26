# Grove - 高温传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_dcd4bb798707",
  "name": "Grove - 高温传感器",
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
    "https://wiki.seeedstudio.com/cn/Grove-High_Temperature_Sensor/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---高温传感器"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

热电偶非常敏感，需要一个具有冷端补偿参考的优质放大器。Grove - 温度传感器使用 K 型热电偶进行温度检测，并使用热敏电阻检测环境温度作为温度补偿。该传感器的检测范围为 -50 至 600℃，精度为 ±(2.0% + 2℃)。
