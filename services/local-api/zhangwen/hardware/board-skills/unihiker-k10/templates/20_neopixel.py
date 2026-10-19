"""K10 外接 RGB 灯带示例，端口 P0，3 颗灯珠。"""

import time
from unihiker_k10 import neopixel

strip = neopixel(0, 3)
strip.brightness(4)

while True:
    try:
        strip.write(0, 0, 0xFF, 0x00, 0x00)
        strip.write(1, 1, 0x00, 0xFF, 0x00)
        strip.write(2, 2, 0x00, 0x00, 0xFF)
        time.sleep(1)

        strip.write(0, 2, 0x00, 0x00, 0x00)
        time.sleep(1)

    except Exception as exc:
        print("NeoPixel operation failed:", repr(exc))
        time.sleep(1)
