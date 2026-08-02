"""K10 P1 舵机安全示例。

只连接小型低功耗舵机。大舵机需要独立供电，并与 K10 共地。
"""

import time
from unihiker_k10 import servo

SAFE_ANGLE = 90
MIN_ANGLE = 20
MAX_ANGLE = 160

servo_1 = servo(1)

try:
    servo_1.angle(value=SAFE_ANGLE)
    time.sleep(1)

    while True:
        servo_1.angle(value=MIN_ANGLE)
        time.sleep(1)

        servo_1.angle(value=SAFE_ANGLE)
        time.sleep(1)

        servo_1.angle(value=MAX_ANGLE)
        time.sleep(1)

        servo_1.angle(value=SAFE_ANGLE)
        time.sleep(1)

except KeyboardInterrupt:
    servo_1.angle(value=SAFE_ANGLE)
    print("Servo returned to safe angle")
