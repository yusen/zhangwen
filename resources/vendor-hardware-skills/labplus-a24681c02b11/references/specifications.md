# 盛思 电子标签RFID 规格

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_labplus_a24681c02b11",
  "name": "盛思 电子标签RFID",
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
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/RFID.html",
    "https://labplus-ledong-module-documentation.readthedocs.io/zh-cn/latest/%E4%BC%A0%E6%84%9F%E5%99%A8%E7%B1%BB/RFID.html"
  ],
  "notes": "官方资料已收录，尚未针对当前主控/固件完成 MicroPython 驱动、引脚及实物联调。结构化电气字段的 0 仅为旧版格式的未知占位，绝非 0V 或已验证参数；不得据此接线或判断兼容。"
}
```

## 官方原文节选

能有效识别射频卡ID并读写信息，可模拟实现电子钱包的充值和扣费功能。
工作电压： VCC 3.3V -5V
模块尺寸：24*48mm
固定安装：2个兼容塑料积木通孔
探测距离：0.5-1cm
数据类型：ID和电子钱包信息
引脚 定义
引脚
定义
GND 地
GND
地
VCC 电源
VCC
电源
SCL I2C时钟
SCL
I2C时钟
SDA I2C数据
SDA
I2C数据
1、按A键获取射频卡序列号并初始化设置并RGB亮红灯，按B键对射频卡充值并亮绿灯。
2、掌控板OLED屏显示RFID序列号和当前余额。。
