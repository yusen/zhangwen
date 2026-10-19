"""K10 人脸注册与识别。

A 键请求注册人脸，B 键请求识别人脸。
按键回调只设置标志，AI 操作在主循环执行。
"""

import time
import ai
from unihiker_k10 import button, screen

button_a = button(button.a)
button_b = button(button.b)

register_pending = False
recognize_pending = False


def on_button_a():
    global register_pending
    register_pending = True


def on_button_b():
    global recognize_pending
    recognize_pending = True


button_a.event_pressed = on_button_a
button_b.event_pressed = on_button_b

ai.init_ai()
ai.camera_start()
ai.face_recognize_start()
screen.init(dir=2)

try:
    while True:
        if register_pending:
            register_pending = False
            print("Register face")
            ai.register_face()

        if recognize_pending:
            recognize_pending = False
            print("Recognize face")
            ai.recognize_face()

        image_data = ai.camera_capture()
        screen.show_camera_img(image_data)

        if ai.is_ai_data_updated():
            data = ai.get_ai_data()
            face_flag = data.get("face_flag")
            print("Face:", face_flag)

            if face_flag:
                face_data = data.get("face_detect", {})
                print("Face ID:", face_data.get("face_id"))
                print("Left eye:", face_data.get("left_eye"))

        time.sleep_ms(1)

except KeyboardInterrupt:
    print("Face recognition stopped")

finally:
    ai.deinit_ai()
