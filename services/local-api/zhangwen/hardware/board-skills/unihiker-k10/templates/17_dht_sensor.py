"""K10 外接 DHT11/DHT22，连接到 P0。"""

import time
from unihiker_k10 import dht

sensor = dht(0)

while True:
    try:
        temperature, humidity = sensor.read()
        print("Temperature:", temperature, "Humidity:", humidity)
    except Exception as exc:
        print("DHT read failed:", repr(exc))

    time.sleep(1)
