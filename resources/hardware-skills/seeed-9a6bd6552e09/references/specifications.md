# Grove - 三轴模拟加速度计 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_9a6bd6552e09",
  "name": "Grove - 三轴模拟加速度计",
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
    "https://wiki.seeedstudio.com/cn/Grove-3-Axis_Analog_Accelerometer/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---三轴模拟加速度计"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

ADXL335 是一款三轴 MEMS 加速度计，在测量模式下功耗仅为 150 μA！这款模拟加速度计是一款低 g 加速度计，具有 ±3 g 的最小满量程范围。ADXL335 可用于倾斜感应应用中测量重力的静态加速度，也可测量由运动、冲击或振动引起的动态加速度。
