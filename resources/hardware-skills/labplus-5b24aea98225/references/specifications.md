# 盛思 热敏电阻 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_5b24aea98225",
  "name": "盛思 热敏电阻",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E7%83%AD%E6%95%8F%E7%94%B5%E9%98%BB.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E7%83%AD%E6%95%8F%E7%94%B5%E9%98%BB.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

热敏电阻随温度升高而增大，可用于测量环境温度变化。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
测量范围：0-100℃
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
AO 温度值
AO
温度值
NC 空
NC
空
1、使用前需将热敏电阻探头插入模块上的耳机接口，注意需将耳机头的金属部分完全插入；
2、将模块接入模拟输入接口，可以直接获取温度值，单位为℃。
3、掌控板OLED屏实时显示传感器测量的温度值，同时当温度大于28度时，RGB灯亮红色，反之亮绿色。
图形化代码
