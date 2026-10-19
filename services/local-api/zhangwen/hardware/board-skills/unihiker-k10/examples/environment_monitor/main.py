import time
from unihiker_k10 import button, screen, temp_humi, light, acce, rgb

UPDATE_MS = 1000

button_a = button(button.a)
button_b = button(button.b)

dim_event = False
off_event = False


def on_button_a():
    global dim_event
    dim_event = True


def on_button_b():
    global off_event
    off_event = True


button_a.event_pressed = on_button_a
button_b.event_pressed = on_button_b

screen.init(dir=2)
rgb.brightness(5)

last_update = time.ticks_ms()

while True:
    if dim_event:
        dim_event = False
        rgb.brightness(2)
        rgb.write(color=0x00AA00)
        print("RGB low brightness")

    if off_event:
        off_event = False
        rgb.clear()
        print("RGB off")

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
                temperature,
                humidity,
                illuminance,
                x_value,
                y_value,
                z_value,
            )

            screen.show_bg(color=0xFFFFFF)
            screen.draw_text(
                text="Temp: {} C".format(temperature),
                x=10,
                y=10,
                font_size=22,
                color=0xFF0000,
            )
            screen.draw_text(
                text="Humi: {} %".format(humidity),
                x=10,
                y=40,
                font_size=22,
                color=0x0000FF,
            )
            screen.draw_text(
                text="Light: {}".format(illuminance),
                x=10,
                y=70,
                font_size=22,
                color=0x008800,
            )
            screen.draw_text(
                text="XYZ: {},{},{}".format(x_value, y_value, z_value),
                x=10,
                y=100,
                font_size=18,
                color=0x000000,
            )
            screen.show_draw()

        except Exception as exc:
            print("environment monitor failed:", repr(exc))
            rgb.write(color=0xFF0000)

    time.sleep_ms(10)
