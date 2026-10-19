# MicroPython 安全控制示例

```python
from machine import Pin, PWM
from time import ticks_diff, ticks_ms, sleep_ms

class Pump:
    MAX_RUN_MS = 3000
    MIN_INTERVAL_MS = 60000

    def __init__(self, pin: int) -> None:
        self._pwm = PWM(Pin(pin), freq=500)
        self._last_stop = -self.MIN_INTERVAL_MS
        self.stop()

    def stop(self) -> None:
        self._pwm.duty_ns(1_500_000)
        self._last_stop = ticks_ms()

    def run_limited(self, duration_ms: int) -> int:
        duration_ms = max(0, min(duration_ms, self.MAX_RUN_MS))
        if ticks_diff(ticks_ms(), self._last_stop) < self.MIN_INTERVAL_MS:
            raise RuntimeError("pump interval is too short")
        try:
            self._pwm.duty_ns(1_000_000)
            sleep_ms(duration_ms)
            return duration_ms
        finally:
            self.stop()
```

引脚号需由已确认 K10 IO Map 提供；异常路径必须调用 `stop()`。
