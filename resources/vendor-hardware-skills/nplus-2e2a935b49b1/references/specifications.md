# N+ 电机驱动 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_2e2a935b49b1",
  "name": "N+ 电机驱动",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/motor.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/motor.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

脚控制马达正转、反转、停止等动作，速度范围是0~100。
工作电源：3.3V
尺寸：20mm x 53.5mm
接口类型 ：I2C直插接口
设备类型：输入设备
V：电源正极
G：电源负极
SDA：双向数据线
SCL:：时钟线
图形化:
代码:
