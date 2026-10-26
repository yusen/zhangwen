# 盛思 PM2.5(旧版，仅探头，无模块) 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_87d187e346f7",
  "name": "盛思 PM2.5(旧版，仅探头，无模块)",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/PM2.5.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

用于进行PM2.5检测。
工作电压： VCC 3.3V -5V
通讯方式：串口，波特率9600
输出：PM2.5检测值0-500μg/m³
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
AO 输入
AO
输入
PLS 脉冲
PLS
脉冲
图形化代码
