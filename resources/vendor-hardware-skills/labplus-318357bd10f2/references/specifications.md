# 盛思 超声波传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_318357bd10f2",
  "name": "盛思 超声波传感器",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%B6%85%E5%A3%B0%E6%B3%A2.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

用于超声波定位、测距、避障等应用场景，采用I2C通讯将测距值返回主控。
工作电压： VCC 3.3V -5V
模块尺寸：32*48mm
固定安装：2个兼容塑料积木通孔
测量范围：10-200cm
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
图形化代码
