# Grove - 光学旋转编码器(TCUT1600X01) 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_c55ce3abb1de",
  "name": "Grove - 光学旋转编码器(TCUT1600X01)",
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
    "https://wiki.seeedstudio.com/cn/Grove-Optical_Rotary_Encoder-TCUT1600X01/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---光学旋转编码器tcut1600x01"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

Grove - 光学旋转编码器(TCUT1600X01)是一种透射式传感器，包含一个红外发射器和两个光电晶体管检测器。通常情况下，红外发射器发射红外光线，光电晶体管检测器接收红外光线，然后光电晶体管被打开，两个输出均为高电平，板载LED指示灯亮起。当有障碍物阻挡时，光电晶体管无法接收到红外光线，因此光电晶体管将关闭，两个输出均为低电平，板载LED指示灯熄灭。
