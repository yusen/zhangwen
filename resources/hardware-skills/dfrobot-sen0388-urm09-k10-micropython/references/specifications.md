# 结构化电气参数

## 工程摘要

- 官方工作电压：3.3–5.5V DC；在 K10 上推荐使用 P1 的 3.3V。
- 最大瞬时电流：小于 20mA；库中以 20mA 作为保守校验上限。
- 接口：`D` 单线数字 TRIG/ECHO 时分复用，内部带下拉。
- 测量能力：2–500cm，分辨率 1cm，标称精度 1%，最高测量频率 25Hz，声学频率 40±2kHz。
- 触发时序：主控输出至少 10μs 高电平后切换为输入，回波高电平最长约 35000μs。
- 模块官方外形：47×22mm。
- 未完成事项：真实 K10 + SEN0388 实机测距、供电瞬态和机械装配验证。

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_dfrobot_sen0388_urm09_trig_k10",
  "name": "DFRobot SEN0388 URM09 触发式超声波传感器（行空板 K10 MicroPython）",
  "category": "SENSOR",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": 3.3,
    "voltageMax": 5.5,
    "supplyVoltages": [],
    "logicLevel": 3.3,
    "peakCurrent": 0.02,
    "communicationProtocol": "DIGITAL",
    "i2cAddress": null,
    "supportedMCUs": ["unihiker-k10"],
    "driverName": "unihiker_k10.ultrasonic.distance",
    "firmwareRequirement": "UNIHIKER K10 MicroPython firmware with unihiker_k10 ultrasonic support"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": ["3V3_DIGITAL_IO", "SINGLE_WIRE_TRIG_ECHO", "NO_REVERSE_POLARITY", "OPEN_ULTRASONIC_TRANSDUCER"],
  "notes": "SEN0388 官方支持3.3-5.5V、单线D引脚TRIG/ECHO时分复用、2-500cm量程、25Hz最高测量频率和小于20mA最大瞬时电流。面向K10时推荐P1端口3.3V同源供电，并固定使用ultrasonic(trig=1, echo=1).distance()；禁止生成SEN0307模拟量ADC换算代码。代码和参考结构尚未完成真实硬件验证。",
  "verificationStatus": "OFFICIAL_DOC_VERIFIED",
  "sourceIds": ["vendor-product:dfrobot-sen0388", "vendor-product:dfrobot-sen0388-cn", "vendor-board:unihiker-k10-micropython", "user-code:mindplus-sen0388-2026-07-17"]
}
```

