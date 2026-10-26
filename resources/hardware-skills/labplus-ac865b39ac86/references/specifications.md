# 盛思 编码直流电机 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_ac865b39ac86",
  "name": "盛思 编码直流电机",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E7%BC%96%E7%A0%81%E7%9B%B4%E6%B5%81%E7%94%B5%E6%9C%BA.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E7%BC%96%E7%A0%81%E7%9B%B4%E6%B5%81%E7%94%B5%E6%9C%BA.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

直流减速电机TT马达+编码器，强磁抗干扰。
工作电压：DC3.3—5V
尺寸：70*27*22mm
减速比： 1：48
转 速 : 115rpm
轴径： 5mm
编码器分辨率：13PPR
引脚 定义
引脚
定义
M+
GND
A相
B相
VCC
M-
