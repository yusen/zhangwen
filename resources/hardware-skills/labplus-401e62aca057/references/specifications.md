# 盛思 语音识别模块 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_401e62aca057",
  "name": "盛思 语音识别模块",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%AF%AD%E9%9F%B3%E8%AF%86%E5%88%AB%E6%A8%A1%E5%9D%97.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E8%AF%AD%E9%9F%B3%E8%AF%86%E5%88%AB%E6%A8%A1%E5%9D%97.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

用于进行离线语音识别，将语音识别为文字，带腔体式喇叭。
工作电压： VCC 3.3V -5V
模块尺寸：32*48mm
固定安装：2个兼容塑料积木通孔
通讯方式：串口，波特率9600
输出：语音识别结果
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
使用“开灯” “关灯“指令控制板载RGB灯
