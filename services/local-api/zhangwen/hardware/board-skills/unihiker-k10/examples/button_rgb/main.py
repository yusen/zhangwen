import time
from unihiker_k10 import button, rgb

button_a = button(button.a)
button_b = button(button.b)

show_colors = False
clear_colors = False


def on_button_a():
    global show_colors
    show_colors = True


def on_button_b():
    global clear_colors
    clear_colors = True


button_a.event_pressed = on_button_a
button_b.event_pressed = on_button_b

rgb.brightness(5)
rgb.clear()

while True:
    if show_colors:
        show_colors = False
        rgb.write(num=0, R=255, G=0, B=0)
        rgb.write(num=1, R=0, G=255, B=0)
        rgb.write(num=2, R=0, G=0, B=255)
        print("RGB colors on")

    if clear_colors:
        clear_colors = False
        rgb.clear()
        print("RGB off")

    time.sleep_ms(10)
