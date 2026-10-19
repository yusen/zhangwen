# MicroPython 使用示例

```python
from unihiker_k10 import ultrasonic

sensor = ultrasonic(trig=0, echo=0)
distance_cm = sensor.distance()
if not 2 <= distance_cm <= 500:
    raise RuntimeError("ultrasonic reading out of range")
print(distance_cm)
```

端口号必须来自已确认 IO Map；示例 API 来自 K10 Hardware Skill，真实设备仍需上板核验。
