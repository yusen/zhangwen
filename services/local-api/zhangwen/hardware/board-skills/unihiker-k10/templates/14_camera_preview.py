"""K10 摄像头画面显示。"""

import time
from unihiker_k10 import screen
from k10_base import Camera

camera = Camera()

try:
    screen.init(dir=2)
    camera.init()
    screen.show_camera(camera)
    print("Camera preview started")

    while True:
        time.sleep(1)

except Exception as exc:
    print("Camera preview failed:", repr(exc))
