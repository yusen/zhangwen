# 盛思 土壤湿度 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_8760b02b3fe7",
  "name": "盛思 土壤湿度",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%9C%9F%E5%A3%A4%E6%B9%BF%E5%BA%A6.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

可用于检测土壤的水分，当土壤缺水时，传感器输出值将减小，反之将增大。
工作电压： VCC 3.3V -5V
固定安装：2个螺丝孔
数据类型：模拟采样值
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
AO 模拟采样值
AO
模拟采样值
NC 空
NC
空
AO口输出模拟值，将探头插入土壤，然后使用主控AD转换器读取AO引脚。土壤水分越大，AO输出越大。
掌控板OLED屏显示土壤湿度测量值，同时当测量值小于2000时，掌控板RGB灯亮。
