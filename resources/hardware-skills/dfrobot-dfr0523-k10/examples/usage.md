# K10 官方 MicroPython 库使用示例

目标固件：行空板 K10 官方 MicroPython 固件；仅使用官方 `unihiker_k10` 代码模式文档中公开的对象。使用官方 `unihiker_k10.pin` PWM 形态控制信号；泵不得由 K10 供电。

```python
from unihiker_k10 import pin

pump_control = pin(1)  # 仅控制信号；泵使用独立 6V 电源
pump_control.write_analog(value=300, freq=255)
```

## 安全与版本说明

- 示例端口是占位值，必须按实际接线修改；K10 官方说明中 P0/P1 为板载直连，其余 GPIO 经 I2C 转 GPIO，只提供基础高低电平能力。
- 先断电接线，并核对供电、电平、共地和峰值电流。
- 官方页面当前提供 V0.9.8 测试固件包并提示可能存在 Bug；实际可用 API 以设备当前官方固件为准。
- 若示例抛出 `NotImplementedError`，表示官方 `unihiker_k10` 代码模式文档未公开该 SKU API，不应用第三方库名替代或猜造调用。
