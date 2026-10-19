# 盛思 颜色传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_f2d23891735d",
  "name": "盛思 颜色传感器",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E9%A2%9C%E8%89%B2%E4%BC%A0%E6%84%9F%E5%99%A8.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

基于不同颜色物体对于RGB光线反射率不同的原理来分辨物体的颜色RGB分量。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
数据类型：RGB 采样值（0-255）
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
在使用时被测物体须要置于颜色传感器1CM处，使其能反射光线。要注意环境光线对颜色测量影响，最好在密闭的黑暗环境下测量。
：用掌控板OLED屏显示颜色传感器检测的RGB颜色分量。
