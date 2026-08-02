"""K10 P0/P1 GPIO、ADC 与 PWM 基础测试。

接线前确认电平和负载，不要直接驱动电机、泵或继电器线圈。
"""

import time
from unihiker_k10 import pin

p0 = pin(0)
p1 = pin(1)

while True:
    try:
        print("P0 digital:", p0.read_digital())
        print("P0 analog:", p0.read_analog())

        p1.write_digital(value=1)
        time.sleep_ms(500)

        p1.write_digital(value=0)
        time.sleep_ms(500)

        p1.write_analog(value=500, freq=255)
        time.sleep_ms(500)

        p1.write_analog(value=0, freq=255)
        time.sleep_ms(500)

    except Exception as exc:
        print("GPIO test failed:", repr(exc))
        time.sleep(1)
