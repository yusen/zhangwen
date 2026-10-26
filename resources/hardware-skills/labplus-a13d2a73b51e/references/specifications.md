# 盛思 摇杆 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_a13d2a73b51e",
  "name": "盛思 摇杆",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%91%87%E6%9D%86.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%91%87%E6%9D%86.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

具有(X,Y)2轴模拟输出，可以制作遥控器用于控制运动物体的方向、速度等互动作品。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
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
A1 X轴模拟采样值
A1
X轴模拟采样值
A2 Y轴模拟采样值
A2
Y轴模拟采样值
用摇杆进行上下左右操控时，掌控板OLED屏显示对应的方向。
