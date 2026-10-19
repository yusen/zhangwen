# 盛思 红外接收 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_eabda30c851e",
  "name": "盛思 红外接收",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E7%BA%A2%E5%A4%96%E6%8E%A5%E6%94%B6%E6%A8%A1%E5%9D%97.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/%E7%BA%A2%E5%A4%96%E6%8E%A5%E6%94%B6%E6%A8%A1%E5%9D%97.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

可用于接收红外遥控信号，有效距离8米。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
数据类型：触发–1 未触发–0
接收距离：8m
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
DO 数字输出
DO
数字输出
NC 空
NC
空
1.串口波特率设置115200bps。程序在定义串口引脚时，注意模块端的RX、TX需要和主板上的RX、TX交叉！
2.当接收到红外调制信号，模块上的指示灯会闪烁。
图形化代码
