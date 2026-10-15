# Grove 视觉 AI 模块 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_a213fd1d2d56",
  "name": "Grove 视觉 AI 模块",
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
    "https://wiki.seeedstudio.com/cn/Grove-Vision-AI-Module/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove-视觉-ai-模块"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

Grove 视觉 AI 模块是一块拇指大小的板卡，基于 Himax HX6537-A 处理器，配备 OV2640 摄像头、数字麦克风和 6 轴惯性测量单元 (IMU)。它完全支持 Edge Impulse，允许您无缝采集原始数据、构建模型并将训练好的机器学习模型部署到模块中，无需任何编程。它兼容 XIAO 系列和 Arduino 生态系统，非常适合各种物体检测应用。
