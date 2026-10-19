# N+ 灯带 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_fe83f6e5c369",
  "name": "N+ 灯带",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/light.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

灯带是指把RGB灯用特殊的加工工艺焊接在铜线或者带状柔性线路板上面，再连接上电源发光，因其发光时形状如一条光带而得名。而且每盏灯都能亮无数种的颜色。所以用于装饰的效果特别好。
技术规格 工作电源：3.3V 灯带宽度：9.5mm 接口类型 ：3PIN直插接口 设备类型：输出
工作电源：3.3V
灯带宽度：9.5mm
接口类型 ：3PIN直插接口
设备类型：输出
接口定义 V：电源正极 G：电源负极 D：信号线
V：电源正极
G：电源负极
D：信号线
图形化:
代码:
