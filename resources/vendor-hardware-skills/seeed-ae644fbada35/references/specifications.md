# Grove 离线语音识别 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_ae644fbada35",
  "name": "Grove 离线语音识别",
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
    "https://wiki.seeedstudio.com/cn/Grove-Offline-Voice-Recognition/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove-离线语音识别"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

这是一款低功耗纯离线语音识别模块，识别时间小于 100 毫秒，内置 150 条预编程命令。它采用 US516P6 语音芯片，具有 32 位 RSIC 架构核心、DSP 指令集和 FPU 算术单元。非常适合需要语音控制的各种智能设备，如智能家电、玩具和灯具。
