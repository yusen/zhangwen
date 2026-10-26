# Grove - 数字光传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_46151ae00fc3",
  "name": "Grove - 数字光传感器",
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
    "https://wiki.seeedstudio.com/cn/Grove-Digital_Light_Sensor/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---数字光传感器"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

该模块基于 I2C 光到数字转换器 TSL2561，将光强转换为数字信号。它具有三种检测模式（红外模式、全光谱模式和人眼可见模式），可用于在各种光线条件下测量光强变化，适配许多流行的微控制器。
