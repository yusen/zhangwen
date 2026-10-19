# DFR0026 MicroPython 使用示例

以下代码是板卡适配参考，不代表已经在目标硬件上运行。上板前必须从对应 Board Skill 确认 ADC 构造方式、通道和满量程。

## 最小读取

```python
from machine import ADC
import time

# 不同板卡可能需要改为 ADC(Pin(gpio))。
adc = ADC(0)

while True:
    raw = adc.read()
    print("light_raw=", raw)
    time.sleep(0.1)
```

## 滤波与相对亮度

```python
from machine import ADC
import time

ADC_CHANNEL = 0
SAMPLES = 8
SAMPLE_INTERVAL_MS = 20
LOOP_INTERVAL_MS = 100
ADC_FULL_SCALE = 4095  # 按目标板卡修改；read_u16() 通常使用 65535。

adc = ADC(ADC_CHANNEL)


def read_average() -> int:
    total = 0
    for _ in range(SAMPLES):
        total += adc.read()
        time.sleep_ms(SAMPLE_INTERVAL_MS)
    return total // SAMPLES


while True:
    raw = read_average()
    relative_percent = max(0.0, min(100.0, raw * 100.0 / ADC_FULL_SCALE))
    print("raw={}, relative={:.1f}%".format(raw, relative_percent))
    time.sleep_ms(LOOP_INTERVAL_MS)
```

相对百分比不是 lux。需要 lux 时，必须使用参考照度计完成标定，并记录供电、ADC 参考、外壳开孔和光学条件。

## 上板前检查

1. 确认主控端口是 ADC 输入，并确认 ADC 最大输入电压。
2. 推荐先使用 3.3 V 供电；若采用 5 V，必须确认输出上限并增加必要保护。
3. 断电接线：Signal → ADC、VCC → 3.3 V、GND → GND。
4. 在 REPL 中确认 `from machine import ADC` 成功。
5. 遮挡和照亮传感器，确认读数变化方向和动态范围。
6. 需要阈值控制时，先记录实际环境的暗、亮数据，再设置阈值与滞回。

