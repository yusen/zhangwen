# N+ 180°舵机 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_2ad6a9f375bf",
  "name": "N+ 180°舵机",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/servo180.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/servo180.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

180°舵机旋转范围为0-180°，接受精确控制，可旋转到指定的角度。舵机（英文叫Servo）：它由直流电机、减速齿轮组、传感器和控制电路组成的一套自动控制系统。通过发送信号，指定输出轴旋转角度。
工作电源：3.3V
旋转角度：180°
尺寸：3.14 x 18 ²mm
工作扭矩：1.6KG/CM
反应转速：0.12~0.13/60°
设备类型：输出
橙黄线：脉冲输入
红色线：电源输入
棕色线：地线
图形化:
代码:
