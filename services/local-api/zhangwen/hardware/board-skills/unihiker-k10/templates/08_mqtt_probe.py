"""K10 MQTT 对象创建探测。

官方代码页面导入 WiFi 和 MqttClient，但示例未展示对象实例化。
先运行此程序，再决定正式 MQTT 项目的写法。
"""

from k10_base import WiFi, MqttClient

print("WiFi symbol:", WiFi)
print("WiFi members:", dir(WiFi))
print("MqttClient symbol:", MqttClient)
print("MqttClient members:", dir(MqttClient))

try:
    wifi = WiFi()
    print("OK: WiFi() ->", wifi)
    print("WiFi object members:", dir(wifi))
except Exception as exc:
    print("FAIL: WiFi():", repr(exc))

try:
    mqttclient = MqttClient()
    print("OK: MqttClient() ->", mqttclient)
    print("MQTT object members:", dir(mqttclient))
    print("Verify methods: connect, connected, message, received, publish")
except Exception as exc:
    print("FAIL: MqttClient():", repr(exc))
    print("Do not generate final MQTT code until object creation is confirmed.")
