# N+ 火焰传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_8cbe6d8de049",
  "name": "N+ 火焰传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/fire.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/fire.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

火焰传感器，可以实现对火焰的检测，适合所有火焰探测需要的场合，例如灭火机器人、火焰报警器。尽管火焰传感器是用来感知火焰，但是它并不防火。因此使用时请与火焰保持一定距离，以免烧坏传感器。火焰越大，数值越小。
技术规格 工作电源：3.3V 尺寸：3.14 x 18 ²mm 接口类型 ：3PIN直插接口 设备类型：模拟输入
工作电源：3.3V
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
设备类型：模拟输入
接口定义 V：电源正极 G：电源负极 S：信号线
V：电源正极
G：电源负极
S：信号线
图形化:
代码:
