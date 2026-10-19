# N+ 土壤湿度传感器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_nplus_d2b4b38a4c73",
  "name": "N+ 土壤湿度传感器",
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
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/soild.html",
    "https://nplus-doc.readthedocs.io/zh-cn/latest/electroics/sensor/soild.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

土壤湿度传感器又名土壤水分传感器，土壤含水量传感器。土壤湿度传感器由不锈钢防水探头构成，可长期埋设于土壤和堤坝内使用，对表层和深层土壤进行墒情的定点监测和在线测量，是利用判断土壤中水分含量的多少来判定土壤湿度的大小。
工作电源：3.3V
尺寸：3.14 x 18 ²mm
接口类型 ：3PIN直插接口
设备类型：模拟输出
V：电源正极
G：电源负极
S：信号线
图形化:
代码:
