# N+ LED灯 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_d6083f07c228",
  "name": "N+ LED灯",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/LED.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/LED.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

发光二极管简称为LED。单色LED模块，高电平亮，低电平灭。
技术规格 工作电源：3.3V 尺寸：20mm x 53.5mm 接口类型 ：3PIN直插接口 设备类型：输出
工作电源：3.3V
尺寸：20mm x 53.5mm
接口类型 ：3PIN直插接口
设备类型：输出
接口定义 V：电源正极 G：电源负极 S：信号线
V：电源正极
G：电源负极
S：信号线
图形化
高电平 → 亮:
低电平 → 不亮:
