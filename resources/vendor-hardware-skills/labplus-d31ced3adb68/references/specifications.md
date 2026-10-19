# 盛思 音乐播放MP3 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_d31ced3adb68",
  "name": "盛思 音乐播放MP3",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/MP3%E9%9F%B3%E4%B9%90%E6%92%AD%E6%94%BE.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/MP3%E9%9F%B3%E4%B9%90%E6%92%AD%E6%94%BE.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

MP3播放模块，可通过软串口发送指令操控播放内存中保存的歌曲。
工作电压： VCC 3.3V -5V
模块尺寸：32*48mm
固定安装：2个兼容塑料积木通孔
通讯方式：串口，波特率9600
文件格式：MP3/WAV
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
按A键暂停歌曲；按B键继续播放。
