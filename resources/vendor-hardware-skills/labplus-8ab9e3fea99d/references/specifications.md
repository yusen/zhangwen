# 盛思 循迹传感器（数字） 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_8ab9e3fea99d",
  "name": "盛思 循迹传感器（数字）",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

可用于循迹线检测，当检测到黑色时，输出高电平，检测白色时，输出低电平。
基于红外反射原理，红外发射二极管不断发射红外线，红外光电三极管接收反射回来的红外光。由于白色对红外反射强，黑色对红外反射弱，故此可检测黑、白线。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
数据类型：黑色–1 白色–0
探测距离：0.5-1cm
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
D1 D1触发值
D1
D1触发值
D2 D2触发值
D2
D2触发值
1、在安装循迹模块时约距离循迹线1CM左右；
2、循迹线的宽度至少15mm；
3、可用黑色电工胶带DIY循迹线，效果较好。
