# K10 官方 MicroPython 库使用示例

目标固件：行空板 K10 官方 MicroPython 固件；仅使用官方 `unihiker_k10` 代码模式文档中公开的对象。没有猜造 API；官方代码模式文档未给出该 SKU 的 `unihiker_k10` 专用对象。

```python
raise NotImplementedError("SEN0575 没有已公开的 unihiker_k10 专用 API；请使用 Mind+ 官方扩展或按厂商协议实现")
```

## 安全与版本说明

- 示例端口是占位值，必须按实际接线修改；K10 官方说明中 P0/P1 为板载直连，其余 GPIO 经 I2C 转 GPIO，只提供基础高低电平能力。
- 先断电接线，并核对供电、电平、共地和峰值电流。
- 官方页面当前提供 V0.9.8 测试固件包并提示可能存在 Bug；实际可用 API 以设备当前官方固件为准。
- 若示例抛出 `NotImplementedError`，表示官方 `unihiker_k10` 代码模式文档未公开该 SKU API，不应用第三方库名替代或猜造调用。
