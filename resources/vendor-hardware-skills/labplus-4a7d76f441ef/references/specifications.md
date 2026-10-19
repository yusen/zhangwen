# 盛思 烟雾传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_4a7d76f441ef",
  "name": "盛思 烟雾传感器",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E7%83%9F%E9%9B%BE%E4%BC%A0%E6%84%9F%E5%99%A8.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E7%83%9F%E9%9B%BE%E4%BC%A0%E6%84%9F%E5%99%A8.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

基于MQ-2气敏传感器，用于检测大气环境中烟雾、液化气、甲烷、丁烷灯气体浓度，气体浓度越大，AO输出越大。
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
特别提醒：传感器通电后，需要预热20S左右，测量的数据才稳定，传感器发热属于正常现象，因为内部有电热丝。
掌控板OLED屏实时显示传感器测量的烟雾模拟值，同时当测量值大于2000时，掌控板RGB灯亮。
