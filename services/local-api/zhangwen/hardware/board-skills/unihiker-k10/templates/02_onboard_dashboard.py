"""K10 板载环境数据面板。"""

import time
from unihiker_k10 import screen, temp_humi, light, acce

UPDATE_MS = 1000

screen.init(dir=2)
last_update = time.ticks_ms()

while True:
    now = time.ticks_ms()

    if time.ticks_diff(now, last_update) >= UPDATE_MS:
        last_update = now

        try:
            temperature = temp_humi.read_temp()
            humidity = temp_humi.read_humi()
            illuminance = light.read()
            x_value = acce.read_x()
            y_value = acce.read_y()
            z_value = acce.read_z()

            print(
                "T:", temperature,
                "H:", humidity,
                "Lux:", illuminance,
                "XYZ:", x_value, y_value, z_value,
            )

            screen.show_bg(color=0xFFFFFF)
            screen.draw_text(
                text="T: {} C".format(temperature),
                x=10,
                y=10,
                font_size=22,
                color=0xFF0000,
            )
            screen.draw_text(
                text="H: {} %RH".format(humidity),
                x=10,
                y=40,
                font_size=22,
                color=0x0000FF,
            )
            screen.draw_text(
                text="Lux: {}".format(illuminance),
                x=10,
                y=70,
                font_size=22,
                color=0x008800,
            )
            screen.draw_text(
                text="X:{} Y:{} Z:{}".format(x_value, y_value, z_value),
                x=10,
                y=100,
                font_size=18,
                color=0x000000,
            )
            screen.show_draw()

        except Exception as exc:
            print("dashboard update failed:", repr(exc))

    time.sleep_ms(10)
