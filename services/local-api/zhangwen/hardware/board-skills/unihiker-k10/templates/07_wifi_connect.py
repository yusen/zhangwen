"""K10 Wi-Fi 连接示例。"""

import time
from k10_base import WiFi

SSID = "YOUR_SSID"
PASSWORD = "YOUR_PASSWORD"
TIMEOUT_MS = 20000
RETRY_DELAY_MS = 5000

wifi = WiFi()

while not wifi.status():
    try:
        print("Connecting to Wi-Fi:", SSID)
        wifi.connect(
            ssid=SSID,
            psd=PASSWORD,
            timeout=TIMEOUT_MS,
        )
        print("Wi-Fi status:", wifi.status())

        if wifi.status():
            print("Wi-Fi info:", wifi.info())
            break

    except Exception as exc:
        print("Wi-Fi connection failed:", repr(exc))

    time.sleep_ms(RETRY_DELAY_MS)
