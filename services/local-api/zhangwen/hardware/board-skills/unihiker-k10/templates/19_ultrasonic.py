"""K10 超声波传感器示例。

trig 和 echo 使用同一端口时，官方文档说明可用于 SEN0388。
"""

import time
from unihiker_k10 import ultrasonic

sensor = ultrasonic(trig=0, echo=0)

while True:
    try:
        distance = sensor.distance()
        print("Distance:", distance)
    except Exception as exc:
        print("Ultrasonic read failed:", repr(exc))

    time.sleep_ms(100)
