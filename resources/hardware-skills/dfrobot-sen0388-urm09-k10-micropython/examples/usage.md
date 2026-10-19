# DFRobot SEN0388 URM09 × 行空板 K10 MicroPython 示例

## 目标环境与接线

- 行空板 K10（DFR0992）MicroPython 固件，使用 `unihiker_k10` 库。
- SEN0388 接 K10 P1：`+` 接 3.3V，`-` 接 GND，`D` 接 Signal。
- P1 同时作为 `trig` 和 `echo`；不使用 ADC。

## 示例 1：屏幕显示距离（推荐）

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

该示例以用户提供的 MindPlus 导出代码为基线，只增加 100ms 循环间隔，并把 `line=1-1` 化简为 `line=0`。

## 示例 2：最小串口输出

```python
import time

from unihiker_k10 import ultrasonic


sensor = ultrasonic(trig=1, echo=1)

while True:
    print("distance_cm:", sensor.distance())
    time.sleep_ms(100)
```

## 生成代码时必须保持

- 导入 `unihiker_k10.ultrasonic`。
- P1 配置必须是 `trig=1, echo=1`；若用户明确改接 P0，则同时改为 `trig=0, echo=0`。
- 直接调用 `.distance()`，不要生成 `pin().read_analog()`、ADC 满量程或电压距离公式。
- 循环间隔不得短于 40ms，常规场景使用 100ms。
- 2cm 以下和 500cm 以上读数不得作为有效测距结果。

## 实测前检查

1. 实物型号确认为 SEN0388，而不是 SEN0307 或 SEN0304。
2. `+`、`-`、`D` 与 K10 P1 丝印一一对应，使用 3.3V 并共地。
3. 在 30cm、50cm、100cm 处分别采集至少 20 次读数。
4. 记录固件版本、MindPlus/K10 扩展版本和异常值，不把静态语法检查当作实机验证。
5. 保证两个探头前方无遮挡，避免斜面、小目标、吸声材料和相邻超声模块串扰。

