# 盛思 金属轴舵机 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_2dedf3069103",
  "name": "盛思 金属轴舵机",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E9%87%91%E5%B1%9E%E8%BD%B4%E8%88%B5%E6%9C%BA.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E9%87%91%E5%B1%9E%E8%BD%B4%E8%88%B5%E6%9C%BA.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

舵机旋转范围为0-180°,接受精确控制,可旋转到指定的角度。
工作电压： VCC 3.3V -5V
旋转角度：0-180度
工作扭矩：1.6KG/CM
反应转速：0.12-0.13/60°
引脚 定义
引脚
定义
黑(GND) 地
黑(GND)
地
红(VCC) 电源
红(VCC)
电源
黄(DI) 控制信号输入
黄(DI)
控制信号输入
使舵机一直左右摆动
