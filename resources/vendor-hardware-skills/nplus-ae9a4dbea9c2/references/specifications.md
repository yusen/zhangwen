# N+ RGB彩灯 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_ae9a4dbea9c2",
  "name": "N+ RGB彩灯",
  "category": "ACTUATOR",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/RGB.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/RGB.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

RGB灯是在一个物理封装里面，有R（红）、G（绿）、B（蓝）三种颜色的LED灯，这三个灯非常靠近，从远处看可以当作一个三色的发光点。使用方法与灯带一样，只需要把RGB彩灯看做灯数为一的灯带。
技术规格 工作电源：3.3V 亮度：0~100 尺寸：3.14 x 18 ²mm 接口类型 ：3PIN直插接口 设备类型：输出
工作电源：3.3V
亮度：0~100
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
设备类型：输出
接口定义 V：电源正极 G：电源负极 S：信号线
V：电源正极
G：电源负极
S：信号线
图形化:
代码:
