from machine import Pin
import time

# GPIO21 is intentionally excluded: it conflicts with microSD use on XIAO Sense.
TEST_PIN = 1
output = Pin(TEST_PIN, Pin.OUT, value=0)

try:
    for _ in range(4):
        output.value(not output.value())
        time.sleep_ms(200)
finally:
    output.value(0)
