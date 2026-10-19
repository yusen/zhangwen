# 盛思 循迹传感器（模拟） 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_9a155a9d4670",
  "name": "盛思 循迹传感器（模拟）",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%BE%AA%E8%BF%B9%E4%BC%A0%E6%84%9F%E5%99%A8%EF%BC%88%E6%A8%A1%E6%8B%9F%EF%BC%89.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

通过探测两个引脚模拟值，可用于循迹线检测，返回模拟探测值。 可设置阈值。
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
A0 A0模拟采样值
A0
A0模拟采样值
A1 A1模拟采样值
A1
A1模拟采样值
设置两个输入引脚，获取循迹探测值
