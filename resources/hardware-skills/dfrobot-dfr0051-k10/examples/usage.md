# K10 官方 MicroPython 库使用示例

目标固件：行空板 K10 官方 MicroPython 固件；仅使用官方 `unihiker_k10` 代码模式文档中公开的对象。官方 `unihiker_k10.pin` 模拟输入 API。

```python
from unihiker_k10 import pin

sensor = pin(0)  # 示例端口，按实际接线修改
print(sensor.read_analog())
```

## 安全与版本说明

- 示例端口是占位值，必须按实际接线修改；K10 官方说明中 P0/P1 为板载直连，其余 GPIO 经 I2C 转 GPIO，只提供基础高低电平能力。
- 先断电接线，并核对供电、电平、共地和峰值电流。
- 官方页面当前提供 V0.9.8 测试固件包并提示可能存在 Bug；实际可用 API 以设备当前官方固件为准。
- 若示例抛出 `NotImplementedError`，表示官方 `unihiker_k10` 代码模式文档未公开该 SKU API，不应用第三方库名替代或猜造调用。
