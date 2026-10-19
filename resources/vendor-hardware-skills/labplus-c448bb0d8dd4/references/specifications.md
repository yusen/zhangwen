# 盛思 编码电机驱动 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_c448bb0d8dd4",
  "name": "盛思 编码电机驱动",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E7%BC%96%E7%A0%81%E7%94%B5%E6%9C%BA.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E7%BC%96%E7%A0%81%E7%94%B5%E6%9C%BA.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

驱动编码直流电机，控制旋转距离和角度。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
控制方式：I2C
引脚 定义
引脚
定义
GND 负极
GND
负极
VCC 正极
VCC
正极
SCL I2C时钟
SCL
I2C时钟
SDA I2C数据
SDA
I2C数据
