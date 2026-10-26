# N+ 倾斜传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_2ece1cbc4594",
  "name": "N+ 倾斜传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/slope.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/slope.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

在倾斜开关中求以不同的倾斜角度移动以制造触发电路的原理。倾斜开关模块使用双向传导的球形倾斜开关。当它向一侧倾斜时，只要倾斜度和力满足条件开关就会通电，从而输出低电平信号。
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
