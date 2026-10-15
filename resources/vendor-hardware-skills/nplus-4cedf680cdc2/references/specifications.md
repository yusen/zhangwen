# N+ 继电器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_4cedf680cdc2",
  "name": "N+ 继电器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/relay.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/relay.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

继电器是一种电控制器件，它具有控制系统和被控制系统之间的互动关系。通常应用于自动化的控制电路中，它实际上是用小电流去控制大电流运作的一种“自动开关”。
简单理解继电器，例如：红外传感器与LED灯同时使用是没有问题的，但是红外传感器与马达一起使用，如果没有继电器、驱动等，电机是不会工作的，因为电机的功率比较大）。故在电路中起着自动调节、安全保护、转换电路等作用。
工作电源：3.3V
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
额定通过电流：3A
最高交流电压：250V
最高直流电压：30V
V：电源正极
G：电源负极
S：信号线
常闭端接法：当信号触发端有电平信号时，继电器吸合，相当于开关由原来接通变为断开，此时设备将断电停止工作。
公共端：一般接电源正极。
常开端接法：当信号触发端有电平信号时，继电器吸合，相当于开关闭合，此时电路连通，设备通电将正常工作。
图形化:
代码:
