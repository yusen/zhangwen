# Wi-Fi、MQTT 和蓝牙 HID

## Wi-Fi

验证级别：D。

```python
from k10_base import WiFi

wifi = WiFi()
wifi.connect(
    ssid="YOUR_SSID",
    psd="YOUR_PASSWORD",
    timeout=50000
)
```

状态：

```python
wifi.status()
```

信息：

```python
wifi.info()
```

`timeout` 单位按官方示例为毫秒，默认值说明为 10000 毫秒。

## MQTT

验证级别：B。

官方页面导入：

```python
from k10_base import WiFi, MqttClient
```

并使用以下方法：

```python
mqttclient.connect(
    server="192.168.1.2",
    port=1883,
    client_id="",
    user="siot",
    psd="dfrobot"
)

mqttclient.connected()
mqttclient.message(topic="siot/test")
mqttclient.received(topic="siot/test", callback=callback)
mqttclient.publish(topic="siot/test", content="hello")
```

但是官方代码页面没有展示：

```python
wifi = WiFi()
mqttclient = MqttClient()
```

因此必须先运行 `templates/08_mqtt_probe.py`，确认当前固件的对象创建方式。

### MQTT 回调约束

回调中只保存消息：

```python
latest_message = None
message_pending = False

def on_message():
    global latest_message, message_pending
    latest_message = mqttclient.message(topic="siot/test")
    message_pending = True
```

屏幕刷新和复杂业务放在主循环。

## 蓝牙 HID

验证级别：D。

```python
from unihiker_k10 import hid, keycode

ble_hid = hid(name="mpy_hid")
```

连接状态：

```python
ble_hid.isconnected()
```

单键：

```python
ble_hid.keyboard_send(keycode.SPACE)
```

组合键：

```python
ble_hid.keyboard_send([keycode.CTRL, keycode.a])
```

注意 `keycode.a` 在官方示例中为小写属性。
