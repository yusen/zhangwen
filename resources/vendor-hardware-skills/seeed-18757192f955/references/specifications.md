# Grove - 旋转角度传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_18757192f955",
  "name": "Grove - 旋转角度传感器",
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
    "https://wiki.seeedstudio.com/cn/Grove-Rotary_Angle_Sensor/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---旋转角度传感器"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

Grove - 旋转角度传感器，这款电位计模块在其 D1 接口上输出 0 到 Vcc（使用 Seeeduino 时为 5V DC）之间的模拟信号。D2 接口未使用。角度范围为 300 度，值呈线性变化。电阻值为 10k 欧姆，非常适合 Arduino 使用。这也可以称为旋转角度传感器。
