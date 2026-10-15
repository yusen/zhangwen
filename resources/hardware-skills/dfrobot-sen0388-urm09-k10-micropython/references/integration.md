# 行空板 K10 MicroPython 集成

## 接线

| SEN0388 标识 | 功能 | K10 P1 Gravity 端口 | 说明 |
|---|---|---|---|
| `+` | 电源输入 | `3.3V` | K10 场景推荐使用 3.3V 同源供电 |
| `-` | 电源地 | `GND` | 必须与 K10 共地 |
| `D` | 单线 TRIG/ECHO | `P1/SIGNAL` | 同一 GPIO 先输出触发，再切换输入测回波 |

K10 的 P0、P1 是直连 ESP32-S3 的全功能 GPIO。本文固定使用 P1，因此 API 中 `trig=1`、`echo=1`。

## 固件与 API

推荐路径：K10 MicroPython 固件 + `unihiker_k10` 库。

```python
from unihiker_k10 import ultrasonic

sensor = ultrasonic(trig=1, echo=1)
distance_cm = sensor.distance()
```

`distance()` 已封装至少 10μs 的触发、GPIO 输入切换、回波计时和厘米换算。不要再叠加 SEN0307 的 ADC 公式。

## 初始化步骤

1. 断电确认实物为 SEN0388，逐一核对 `+`、`-`、`D`。
2. 将模块接到 K10 P1，并使用 P1 的 3.3V 和 GND。
3. 确认固件可导入 `from unihiker_k10 import ultrasonic`。
4. 创建 `ultrasonic(trig=1, echo=1)`，先仅打印 `.distance()`。
5. 用平整挡板在 30cm、50cm、100cm 处核对读数，再加入屏幕显示或控制逻辑。
6. 采样间隔保持不短于 40ms；通用程序建议 100ms。

## MindPlus/K10 屏幕示例

```python
import time

from unihiker_k10 import screen, ultrasonic


screen.init(dir=2)
sonic_p1 = ultrasonic(trig=1, echo=1)

while True:
    distance_cm = sonic_p1.distance()
    screen.clear()
    screen.draw_text(
        text=str(distance_cm),
        line=0,
        font_size=24,
        color=0x0000FF,
    )
    screen.show_draw()
    print(distance_cm)
    time.sleep_ms(100)
```

## 故障排查

| 现象 | 检查 |
|---|---|
| 导入失败 | K10 固件是否包含 `unihiker_k10` 及 `ultrasonic` 类 |
| 始终无有效距离 | 型号是否为 SEN0388、`D` 是否接 P1、是否共地、供电是否为 3.3V |
| 一直超时或固定极值 | 是否错误地把 `trig` 和 `echo` 配成不同引脚，或仍在使用模拟量代码 |
| 近距离无效 | 目标可能进入 2cm 以下盲区 |
| 读数跳动 | 目标是否平整、面积足够并正对探头；检查多径反射和相邻超声模块串扰 |
| 刷新异常 | 循环是否快于 40ms；先改为 100ms 并只保留单个传感器 |
| 库导入失败 | 检查目录名、manifest/内容 revision、模型 SHA 和 componentId 唯一性 |

## 型号边界

- SEN0388：单线数字 `D`，使用 `ultrasonic(trig=n, echo=n)`。
- SEN0307：模拟量 `A`，不能套用本包驱动。
- SEN0304：I2C，不能套用本包驱动。
- HC-SR04 类双线模块：TRIG/ECHO 通常为不同引脚，不应照抄本包同引脚配置。

