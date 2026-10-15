# 掌控板 2.0 · OLED 空心圆
from mpython import oled

oled.fill(0)
oled.circle(64, 32, 24, 1)
oled.show()
print("ZW_CIRCLE_OK: center=(64,32), radius=24, outline")
