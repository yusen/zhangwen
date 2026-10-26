# 盛思 语音录放 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_9084b07bd892",
  "name": "盛思 语音录放",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E8%AF%AD%E9%9F%B3%E5%BD%95%E6%94%BE.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E8%AF%AD%E9%9F%B3%E5%BD%95%E6%94%BE.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

可以预先录制0-7秒的语音并保存,可以通过引脚控制在需要的时候播放出来。
工作电压： VCC 3.3V -5V
模块尺寸：32*48mm
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
PLAY 播放
PLAY
播放
NC 空
NC
空
录制方法：
-1、按住「录制」键不放即为录音，REC LED灯会亮起，松开按键录音停止。
-2、REC引脚持续高电平为录音，恢复低电平录音停止。
播放方法：
-1、按住「播放」键时即放音，松开按键即停止
-2、PLAY引脚持续高电平为放音，恢复低电平停止放音停止。
按语音录放模块上的REC键先录制0-7秒的语音并保存,然后按A键播放出来。
