# Grove Vision AI 模块 V2 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_b2a68addbbde",
  "name": "Grove Vision AI 模块 V2",
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
    "https://wiki.seeedstudio.com/cn/grove_vision_ai_v2/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove-vision-ai-模块-v2"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

这是一个基于 MCU 的视觉 AI 模块，由 Himax WiseEye2 提供支持，配备 Arm Cortex-M55 和 Ethos-U55。支持 TensorFlow 和 PyTorch 框架。兼容 Arduino IDE，并支持无代码模型部署以及通过 SenseCraft AI 实现识别结果的即时可视化。
