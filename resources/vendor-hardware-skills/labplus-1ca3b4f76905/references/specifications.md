# 盛思 继电器 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_1ca3b4f76905",
  "name": "盛思 继电器",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E7%BB%A7%E7%94%B5%E5%99%A8.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E6%89%A7%E8%A1%8C%E5%99%A8%E7%B1%BB/%E7%BB%A7%E7%94%B5%E5%99%A8.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

用于切换开关控制,支持控制Type-A USB设备，如USB风扇，USB小家电等。
工作电压： VCC 3.3V -5V
模块尺寸：32*48mm
固定安装：2个兼容塑料积木通孔
控制方式：数字输入
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
DI 数字输入
DI
数字输入
NC 空
NC
空
端口 功能描述
端口
功能描述
Micro USB端口 当接USB功率设备时，须要接MicroUSB外部供电
Micro USB端口
当接USB功率设备时，须要接MicroUSB外部供电
Type-A USB端口 用于接受控的USB小功率设备，在使用时须接microUSB接口供电。高电平时，USB端口的VDD连通microUSB VDD，输出+5V,低电平则断开，不会输出电压
Type-A USB端口
用于接受控的USB小功率设备，在使用时须接microUSB接口供电。高电平时，USB端口的VDD连通microUSB VDD，输出+5V,低电平则断开，不会输出电压
接线端子IN+ 受控设备正极。平时与OUT+断开，有信号闭合
接线端子IN+
受控设备正极。平时与OUT+断开，有信号闭合
接线端子IN- 受控设备负极与OUT-连通
接线端子IN-
受控设备负极与OUT-连通
接线端子OUT+ 受控设备正极。平时与IN+断开，有信号闭合
接线端子OUT+
受控设备正极。平时与IN+断开，有信号闭合
接线端子OUT- 受控设备负极与IN-连通
接线端子OUT-
受控设备负极与IN-连通
A按键按下，打开继电器；B按键按下，关闭继电器。A按键按下，发射激光；B按键按下，激光关闭。
