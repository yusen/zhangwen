"""K10 KIT0176 重量/力传感器探测。

官方页面对 mass 参数的单位说明存在文字冲突。
请用已知砝码验证当前固件的返回单位。
"""

import time
from unihiker_k10 import force

sensor = force()
sensor.zero()

while True:
    try:
        default_value = sensor.read()
        force_value = sensor.read(mass=False)

        print("sensor.read():", default_value)
        print("sensor.read(mass=False):", force_value)
        print("Verify units with a known mass before final use.")

    except Exception as exc:
        print("Force sensor read failed:", repr(exc))

    time.sleep_ms(500)
