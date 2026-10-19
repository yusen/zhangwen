# DFRobot SEN0388 URM09 × 行空板 K10 MicroPython

本包为“掌问”提供 DFRobot SEN0388 URM09 Gravity 触发式超声波传感器在行空板 K10 上的硬件事实、MicroPython 接入方法、机械参考包络与安全边界。

## 适用范围

- 传感器：URM09 Ultrasonic Distance Sensor (Trig)，SKU SEN0388。
- 主控：行空板 K10（DFR0992）。
- 固件：包含 `unihiker_k10` 库和 `ultrasonic` 类的 K10 MicroPython 固件。
- 接口：K10 P1 单线数字接口；P1 同时作为 `trig` 和 `echo`。

## 黄金路径

```python
from unihiker_k10 import ultrasonic

sensor = ultrasonic(trig=1, echo=1)
distance_cm = sensor.distance()
```

SEN0388 的 `D` 引脚通过时分复用完成触发与回波，不使用 ADC，不使用 `read_analog()`，也不做电压比例换算。

## 验证状态

- 型号、接口、电气、量程和 K10 API：已按 DFRobot/行空板官方资料核对。
- 示例代码：已通过静态语法检查，尚未在真实 K10 + SEN0388 上运行。
- 机械包络：官方只确认 47×22mm 外形；探头、接线座和孔位细节来自用户提供的 URM09 参考模型，正式开壳前必须对照 SEN0388 实物复核。
- CadQuery 模型：只作为参考包络，不代表官方机械认证。

