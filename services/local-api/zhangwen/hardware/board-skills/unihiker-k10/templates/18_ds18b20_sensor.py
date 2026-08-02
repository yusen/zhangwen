"""K10 外接 DS18B20，连接到 P1。"""

import time
from unihiker_k10 import ds18b20

sensor = ds18b20(1)

while True:
    try:
        temperature = sensor.read()
        print("Temperature:", temperature)
    except Exception as exc:
        print("DS18B20 read failed:", repr(exc))

    time.sleep(1)
