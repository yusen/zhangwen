"""K10 移动检测。"""

import time
import ai
from unihiker_k10 import screen

ai.init_ai()
ai.camera_start()
ai.move_detect()
screen.init(dir=2)

try:
    while True:
        image_data = ai.camera_capture()
        screen.show_camera_img(image_data)

        if ai.is_ai_data_updated():
            data = ai.get_ai_data()
            print("Move:", data.get("move_flag"))

        time.sleep_ms(1)

except KeyboardInterrupt:
    print("Motion detector stopped")

finally:
    ai.deinit_ai()
