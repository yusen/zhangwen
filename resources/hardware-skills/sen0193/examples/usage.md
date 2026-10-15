# MicroPython 读取与标定示例

```python
from machine import ADC, Pin

class SoilMoistureSensor:
    def __init__(self, pin: int, dry: int, wet: int) -> None:
        if abs(dry - wet) < 100:
            raise ValueError("invalid soil calibration")
        self._adc = ADC(Pin(pin))
        self._dry = dry
        self._wet = wet

    def percent(self) -> int:
        raw = self._adc.read_u16()
        low, high = sorted((self._dry, self._wet))
        if raw < 0 or raw > 65535:
            raise RuntimeError("soil sensor out of range")
        value = round((raw - self._dry) * 100 / (self._wet - self._dry))
        return max(0, min(100, value))
```

引脚号需由已确认 K10 IO Map 提供，不在示例中猜测。
