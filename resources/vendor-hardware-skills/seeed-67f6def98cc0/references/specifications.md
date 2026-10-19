# Grove - 热成像摄像头 IR-Array MLX90641 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_seeed_67f6def98cc0",
  "name": "Grove - 热成像摄像头 IR-Array MLX90641",
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
    "https://wiki.seeedstudio.com/cn/Grove-Thermal-Imaging-Camera-IR-Array/",
    "https://wiki.seeedstudio.com/cn/Grove_Sensor_Intro/#grove---热成像摄像头-ir-array-mlx90641"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

这款红外热成像摄像头配备了一个 16x12 的热传感器阵列 (MLX90641)，可以远距离检测物体温度，其中心区域精度为 ±1℃，平均精度为 ±1.5℃。为了轻松获取热成像，摄像头使用 I2C 协议获取低分辨率图像。该摄像头的视场角 (FOV) 为 110°x75°，温度测量范围为 -40℃ 至 300℃。
