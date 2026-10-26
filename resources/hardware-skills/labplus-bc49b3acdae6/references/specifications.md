# 盛思 人体感应 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_bc49b3acdae6",
  "name": "盛思 人体感应",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E4%BA%BA%E4%BD%93%E6%84%9F%E5%BA%94.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E4%BA%BA%E4%BD%93%E6%84%9F%E5%BA%94.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

基于热释电红外传感器，能检测人或动物身体发射的红外线而输出电信号。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
数据类型：触发–1 未触发–0
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
DO 数字输出
DO
数字输出
NC 空
NC
空
当有人接近触发人体感应传感器时，掌控板RGB灯亮。
