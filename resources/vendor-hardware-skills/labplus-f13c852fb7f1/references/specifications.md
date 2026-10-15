# 盛思 全球定位系统 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_f13c852fb7f1",
  "name": "盛思 全球定位系统",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E5%8C%97%E6%96%97%E6%A8%A1%E5%9D%97.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

用于进行北斗、GPS定位。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
通讯方式：串口，波特率9600
输出：位置信息
定位精度：2.5 米（CEP50，开阔地）
首次定位时间：32 秒（也有可能是几分钟，要看具体环境而定）
低功耗：连续运行<25mA
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
TX 串口发送
TX
串口发送
RX 串口接收
RX
串口接收
每个3秒获取卫星定位信息并打印
