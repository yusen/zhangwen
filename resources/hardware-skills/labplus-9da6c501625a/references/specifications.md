# 盛思 数码管 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_9da6c501625a",
  "name": "盛思 数码管",
  "category": "DISPLAY",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E6%95%B0%E7%A0%81%E7%AE%A1.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E6%95%B0%E7%A0%81%E7%AE%A1.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

4位7段LED数码管显示，可显示整形数字。
工作电压： VCC 3.3V -5V
模块尺寸：32*48mm
固定安装：2个兼容塑料积木通孔
显示范围：0-9999
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
SCL I2C时钟
SCL
I2C时钟
SDA I2C数据
SDA
I2C数据
数码管显示光线值。
