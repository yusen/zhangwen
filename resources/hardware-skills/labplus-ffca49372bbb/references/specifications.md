# 盛思 蜂鸣器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_ffca49372bbb",
  "name": "盛思 蜂鸣器",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E6%9C%89%E6%BA%90%E8%9C%82%E9%B8%A3%E5%99%A8.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E6%9C%89%E6%BA%90%E8%9C%82%E9%B8%A3%E5%99%A8.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

有源蜂鸣器，高电平工作，低电平停止。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
控制方式：数字输入
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
DI 数字输入
DI
数字输入
NC 空
NC
空
按A键蜂鸣器发出声音，按B键停止。
