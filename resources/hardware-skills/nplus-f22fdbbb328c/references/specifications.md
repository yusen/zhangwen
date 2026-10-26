# N+ 按键 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_f22fdbbb328c",
  "name": "N+ 按键",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/button.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/button.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

按键是一种输入设备，是按压式的开关数字输入模块，具有按下和抬起两种状态，按下为低电平输出，抬起为高电平输出。
技术规格 工作电源：3.3V 按压式按键 尺寸：3.14 x 18 ²mm 接口类型 ：3PIN直插接口 设备类型：输入
工作电源：3.3V
按压式按键
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
设备类型：输入
接口定义 V：电源正极 G：电源负极 S：信号线
V：电源正极
G：电源负极
S：信号线
图形化:
代码:
