"""K10 A/B 按键安全事件模式：回调只设置标志。"""

import time
from unihiker_k10 import button, screen

button_a = button(button.a)
button_b = button(button.b)

event_a = False
event_b = False


def on_button_a_pressed():
    global event_a
    event_a = True


def on_button_b_pressed():
    global event_b
    event_b = True


button_a.event_pressed = on_button_a_pressed
button_b.event_pressed = on_button_b_pressed

screen.init(dir=2)
screen.show_bg(color=0xFFFFFF)
screen.draw_text(text="Press A or B", line=1, font_size=24, color=0x000000)
screen.show_draw()

while True:
    if event_a:
        event_a = False
        print("button A pressed")
        screen.show_bg(color=0xFFFFFF)
        screen.draw_text(text="Button A", line=1, font_size=28, color=0xFF0000)
        screen.show_draw()

    if event_b:
        event_b = False
        print("button B pressed")
        screen.show_bg(color=0xFFFFFF)
        screen.draw_text(text="Button B", line=1, font_size=28, color=0x0000FF)
        screen.show_draw()

    time.sleep_ms(10)
