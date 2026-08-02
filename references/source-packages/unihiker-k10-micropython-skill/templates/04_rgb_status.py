"""K10 三颗板载 RGB 灯示例。"""

import time
from unihiker_k10 import rgb

rgb.brightness(5)

try:
    while True:
        rgb.write(num=0, R=255, G=0, B=0)
        rgb.write(num=1, R=0, G=255, B=0)
        rgb.write(num=2, R=0, G=0, B=255)
        time.sleep(1)

        rgb.write(color=0xFF00FF)
        time.sleep(1)

        rgb.clear()
        time.sleep(1)

except KeyboardInterrupt:
    rgb.clear()
    print("RGB demo stopped")
