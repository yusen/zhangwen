# 盛思 光敏 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_929ff6038a2a",
  "name": "盛思 光敏",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%A8%A1%E6%8B%9F%E5%85%89%E7%BA%BF.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E6%A8%A1%E6%8B%9F%E5%85%89%E7%BA%BF.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

内置光敏电阻，可实现光电转换。一般用于光线测量、光线控制。
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
AO 模拟采样值
AO
模拟采样值
NC 空
NC
空
1.AO口输出模拟值，DO口输出数字值0/1。
2.DO口数字值触发阈值可通过模块正面电位器进行调节，当红色LED亮，表示触发数字输出1，反之代表数字输出0。
3.当模拟光线传感器的测量值大于500时，掌控板RGB灯亮。
