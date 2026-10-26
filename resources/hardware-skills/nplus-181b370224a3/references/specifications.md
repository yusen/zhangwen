# N+ 气体传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_181b370224a3",
  "name": "N+ 气体传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/gas.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/gas.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

气体传感器是一种将某种气体体积分数转化成对应电信号的转换器。探测头通过气体传感器对气体样品进行调理，通常包括滤除杂质和干扰气体、干燥或制冷处理仪表显示部分。
气体传感器是一种将气体的成份、浓度等信息转换成可以被人员、仪器仪表、计算机等利用的信息的装置，常用于检测化学物品的泄露。
气体传感器可以检测多种气体，例如：酒精、正丁烷（打火机）、一氧化碳（煤气）。气体传感器模拟量数值范围是0~4095，每一种气体触发的临界数值是不同的。这里提供两个数值，检测酒精特别灵敏，所以数值会大一点，1500左右；检测正丁烷较为不灵敏，数值变化不大，可以设置在600上下。
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
