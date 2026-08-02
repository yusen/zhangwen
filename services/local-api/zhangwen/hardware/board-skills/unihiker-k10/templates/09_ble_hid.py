"""K10 蓝牙 HID：A 键发送空格，B 键发送 Ctrl+A。"""

import time
from unihiker_k10 import button, hid, keycode, screen

button_a = button(button.a)
button_b = button(button.b)
ble_hid = hid(name="k10_hid")

screen.init(dir=2)
last_connected = None

while True:
    connected = ble_hid.isconnected()

    # 仅在连接状态变化时刷新屏幕，避免高频整屏更新。
    if connected != last_connected:
        last_connected = connected
        screen.show_bg(color=0xFFFFFF)
        screen.draw_text(
            text="BLE connected" if connected else "BLE disconnected",
            line=1,
            font_size=22,
            color=0x008800 if connected else 0xFF0000,
        )
        screen.show_draw()
        print("BLE connected:", connected)

    if connected:
        if button_a.status() == 1:
            ble_hid.keyboard_send(keycode.SPACE)
            time.sleep_ms(250)

        if button_b.status() == 1:
            ble_hid.keyboard_send([keycode.CTRL, keycode.a])
            time.sleep_ms(250)

    time.sleep_ms(50)
