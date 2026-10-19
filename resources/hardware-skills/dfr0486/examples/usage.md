# MicroPython 集成轮廓

```python
from machine import I2C
import ssd1306

def create_display(i2c: I2C) -> ssd1306.SSD1306_I2C:
    if 0x3C not in i2c.scan():
        raise RuntimeError("DFR0486 not found at 0x3C")
    return ssd1306.SSD1306_I2C(128, 64, i2c)
```

I2C 对象必须由已确认的 K10 Board API/IO Map 创建，不在示例中猜测引脚。
