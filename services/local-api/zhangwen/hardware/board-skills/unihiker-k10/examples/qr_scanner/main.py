"""K10 二维码识别。"""

import time
import ai
from unihiker_k10 import screen

ai.init_ai()
ai.camera_start()
ai.code_scanner()
screen.init(dir=2)

try:
    while True:
        image_data = ai.camera_capture()
        screen.show_camera_img(image_data)

        if ai.is_ai_data_updated():
            data = ai.get_ai_data()
            code_data = data.get("code_data")

            if code_data:
                print("QR Code:", code_data)

        time.sleep_ms(1)

except KeyboardInterrupt:
    print("QR scanner stopped")

finally:
    ai.deinit_ai()
