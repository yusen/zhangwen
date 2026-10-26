# Grove - 二氧化碳 & 温湿度传感器 (SCD30) 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_f22c17defd6c",
  "name": "Grove - 二氧化碳 & 温湿度传感器 (SCD30)",
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
    "https://wiki.seeedstudio.com/cn/Grove-CO2_Temperature_Humidity_Sensor-SCD30/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---二氧化碳--温湿度传感器-scd30"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

Grove - SCD30 是一款兼容 Arduino 的 3 合 1 环境传感器，用于二氧化碳、温度和湿度测量。基于 Sensirion SCD30，其非分散红外 (NDIR) 技术实现了高精度和宽测量范围，并通过建模和补偿外部热源的算法来测量湿度和温度。可轻松集成到各种环境监测应用中，例如智能通风系统。
