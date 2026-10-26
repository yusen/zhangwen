# N+ 超声波传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_81c91725522e",
  "name": "N+ 超声波传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/ultrasonic.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/ultrasonic.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

超声波传感器是将超声波信号转换成其他能量信号（通常是电信号）的传感器。超声波传感器是一种输入设备。它具有发射和接收超声波的探头，超声波碰到杂质或分界面会产生显著反射形成反射回波。根据发射和接收的时间差计算出前方物体的距离。
技术规格 工作电源：3.3V 工作电流：10mA 工作温度：-10°C ~+70°C 分辨率：1mm 有效测距量程：4cm~250cm 尺寸：20mm x 53.5mm 接口类型 ：I2C直插接口 设备类型：输入设备
工作电源：3.3V
工作电流：10mA
工作温度：-10°C ~+70°C
分辨率：1mm
有效测距量程：4cm~250cm
尺寸：20mm x 53.5mm
接口类型 ：I2C直插接口
设备类型：输入设备
接口定义 V：电源正极 G：电源负极 SDA：双向数据线 SCL:：时钟线
V：电源正极
G：电源负极
SDA：双向数据线
SCL:：时钟线
图形化
代码
