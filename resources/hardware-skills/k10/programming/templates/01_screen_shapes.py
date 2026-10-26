"""K10 屏幕图形最小示例。"""

import time
from unihiker_k10 import screen

screen.init(dir=2)
screen.show_bg(color=0xFFFF00)
screen.set_width(width=3)

screen.draw_line(
    x0=10,
    y0=10,
    x1=100,
    y1=10,
    color=0x0000FF,
)
screen.draw_rect(
    x=20,
    y=40,
    w=80,
    h=60,
    bcolor=0xFF0000,
    fcolor=0xFFFFFF,
)
screen.draw_circle(
    x=160,
    y=70,
    r=30,
    bcolor=0x00AA00,
    fcolor=0x00FF00,
)
screen.draw_text(
    text="K10 MicroPython",
    x=10,
    y=120,
    font_size=24,
    color=0x000000,
)
screen.show_draw()

while True:
    time.sleep(1)
