# N+ 触碰传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_dbe8c4f7e0ad",
  "name": "N+ 触碰传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/touch.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/touch.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

触碰传感器，是一个利用接触片实现检测触碰功能的传感器，触碰模块主要用于检测外界触碰情况，有触碰时，输出低电平；没触碰，输出高电平。
技术规格 工作电源：3.3V 尺寸：3.14 x 18 ²mm 接口类型 ：3PIN直插接口 设备类型：输入
工作电源：3.3V
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
设备类型：输入
接口定义 V：电源正极 G：电源负极 S：信号线
V：电源正极
G：电源负极
S：信号线
图形化:
代码:
