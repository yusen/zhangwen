# 盛思 光环板(24灯) 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_c48d19378c28",
  "name": "盛思 光环板(24灯)",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/NeopixelRGB%E7%81%AF.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/NeopixelRGB%E7%81%AF.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

单板级联24颗RGB灯珠，采用LED专用主控芯片WS2812，支持单总线控制。
工作电压： VCC 3.3V -5V
固定安装：2个螺丝孔
控制方式：RGB分量
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
