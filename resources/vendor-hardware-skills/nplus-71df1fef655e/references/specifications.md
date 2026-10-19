# N+ 旋转电位器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_71df1fef655e",
  "name": "N+ 旋转电位器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/potentiometer.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/potentiometer.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

旋转电位器由电阻体和可移动的电刷组成。当电刷沿电阻体移动时，在输出端即获得与位移量成一定关系的电阻值或电压。由于它在电路中的作用是获得与输入电压（外加电压）成一定关 系得输出电压，因此称之为电位器。
技术规格 工作电源：3.3V 尺寸：3.14 x 18 ²mm 接口类型 ：3PIN直插接口 设备类型：模拟输入 数值范围：通过旋转旋钮可以使输出电压从0变化到4095，或者从4095变化到0
工作电源：3.3V
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
设备类型：模拟输入
数值范围：通过旋转旋钮可以使输出电压从0变化到4095，或者从4095变化到0
接口定义 V：电源正极 G：电源负极 S：信号线
V：电源正极
G：电源负极
S：信号线
图形化:
代码:
