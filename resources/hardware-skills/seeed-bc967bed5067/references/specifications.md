# Grove - 多通道气体传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_bc967bed5067",
  "name": "Grove - 多通道气体传感器",
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
    "https://wiki.seeedstudio.com/cn/Grove-Multichannel_Gas_Sensor/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---多通道气体传感器"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

一个封装内包含三个独立的气体通道，采用 ATmega168PA 制造。可检测的气体包括：一氧化碳（CO）、二氧化氮（NO2）、氢气（H2）、氨气（NH3）、甲烷（CH4）等。Grove 兼容。
