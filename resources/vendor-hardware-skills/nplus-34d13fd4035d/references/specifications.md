# N+ 颜色传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_34d13fd4035d",
  "name": "N+ 颜色传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/color.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/color.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

是指由于不同颜色对光线的反射系数不同，可根据接收到的反射光的强弱来判断。N+颜色循迹模块获取颜色HSV值也可以单独地获取颜色的H/S/V值。HSV指的是(色调，饱和度，亮度）
工作电源：3.3V
有效测距量程：1~8mm
尺寸：20mm x 53.5mm
接口类型 ：I2C直插接口
设备类型：输入设备
V：电源正极
G：电源负极
SDA：双向数据线
SCL:：时钟线
（1）识别RGB值
图形化:
代码:
(2)识别HSV中H的颜色
