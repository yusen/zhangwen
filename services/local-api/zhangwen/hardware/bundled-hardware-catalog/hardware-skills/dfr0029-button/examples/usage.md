# MicroPython 去抖轮廓

```python
import time

def stable_button(read_level, delay_ms=30):
    first = read_level()
    time.sleep_ms(delay_ms)
    return first if read_level() == first else None
```

`read_level` 必须由已确认的 K10 数字端口提供；首次运行先记录松开和按下电平，不猜测极性。
