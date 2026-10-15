# 掌控板 3.0 MicroPython 使用示例

目标固件：掌控板 3.0 官方 MicroPython 固件。全部示例仅作为官方 API 使用形态的知识样例，本批次未在真实板卡运行。示例不使用 `educore`。

## 1. `mpython`：显示、板载传感器、按键与 RGB

```python
from mpython import *

display.clear(lcd.BLACK)
display.DispChar("掌控板 3.0", 0, 0, lcd.WHITE, False)
display.show()

print("light:", light.read())
print("sound:", sound.read())
print("acc:", accelerometer.get_x(), accelerometer.get_y(), accelerometer.get_z())
print("gyro:", gyroscope.get_x(), gyroscope.get_y(), gyroscope.get_z())
print("heading:", magnetic.get_heading())

if button_a.is_pressed():
    rgb.fill((0, 16, 0))
    rgb.brightness(0.2)
    rgb.write()
```

## 2. `mpython.gui`：进度条、二维码、表格与图表

```python
from mpython import *
from gui import UI, MicroExcelTable, MicroChart

ui = UI()
ui.ProgressBar(10, 10, 200, 16, 60, lcd.GREEN)
ui.qr_code("https://www.labplus.cn", 10, 40, 3)

table = MicroExcelTable(display=display, cols=2, rows=2)
table.draw_headers(["温度", "湿度"], ["设备1", "设备2"])
table.update_data([[25, 60], [26, 58]])

chart = MicroChart(display=display, width=200, height=100, val_min=0, val_max=100)
chart.draw_axis()
chart.draw_line_chart([[10, 20, 30, 40]], show_grid=True)
display.show()
```

注意：官方页面把 `exectable.update_cell` 写成 `update_cell(row, row, text)`，疑似第二个参数应为列索引；本包保留原签名，不擅自修正，使用前请通过当前固件核对。

## 3. `music`：音符、旋律与连续音高

```python
from mpython import Pin
import music

music.set_tempo(ticks=4, bpm=120)
music.play(["c4:2", "e", "g", "c5:4"], pin=6, wait=True)
music.play(music.NYAN, pin=6, wait=False, loop=False)
music.stop()
music.pitch(440, duration=500, pin=Pin.P6, wait=True)
print(music.get_tempo())
music.reset()
```

## 4. `urequests`：HTTP GET/JSON 与关闭响应

```python
import urequests

response = None
try:
    response = urequests.get("https://example.com/api/data", headers={"Accept": "application/json"})
    print(response.text)
    data = response.json()
    print(data)
finally:
    if response is not None:
        response.close()
```

`request()` 还接受 `method`、`data`、`json`、`headers`、`params`、`files`；快捷方法包括 `head/get/post/put/patch/delete`。不要在 Skill 内保存真实密码、Token 或私有 URL。

## 5. `umqtt.simple`：发布、订阅和非阻塞轮询

```python
from umqtt.simple import MQTTClient
from time import sleep_ms

def on_message(topic, msg):
    print(topic, msg)

client = MQTTClient(b"mpython3-demo", "broker.example.com", keepalive=60)
client.set_callback(on_message)
client.set_last_will(b"lab/status", b"offline", retain=True, qos=0)
client.connect(clean_session=True)
client.subscribe(b"lab/in", qos=0)
client.publish(b"lab/status", b"online", retain=True, qos=0)

try:
    while True:
        client.check_msg()
        sleep_ms(100)
finally:
    client.disconnect()
```

官方说明：`wait_msg()` 为阻塞式主循环，`check_msg()` 为非阻塞检查；QoS 支持 0 和 1，不支持 QoS 2；主题和消息使用字节。

## 6. `radio`：相同频道收发

```python
import radio

radio.on()
radio.config(7)
radio.send("hello")
message = radio.receive()
if message is not None:
    print(message)
radio.off()
```

官方签名表把 `send()`/`send_bytes()` 的参数省略，但文字说明要求传入字符串/字节；上例按官方使用语义传入消息。最大接收数据 250 字节，频道范围 1–13。

## 7. `sdcard`：SPI 初始化、挂载与文件读写

```python
from machine import Pin, SPI
import os
import sdcard

spi = SPI(1, baudrate=10_000_000, polarity=0, phase=0,
          sck=Pin(Pin.P13), mosi=Pin(Pin.P15), miso=Pin(Pin.P14))
sd = sdcard.SDCard(spi, Pin(Pin.P16))
os.mount(sd, "/sd")
with open("/sd/test.txt", "w") as file:
    file.write("Hello world!\n")
print(os.listdir("/sd"))
```

SD 卡须预先格式化为 FAT/FAT32；引脚为官方示例组合，接线前必须断电。

## 8. `bluebit`：8×8 点阵及公开驱动类

```python
from mpython import i2c
from bluebit import Matrix

matrix = Matrix(i2c)
matrix.brightness(5)
matrix.fill(1)
matrix.show()
```

官方索引还公开：`Thermistor`、`NTC`、`LM35`、`joyButton`、`SHT20`、`Color`、`AmbientLight`、`Ultrasonic`、`SEGdisplay`、`LCD1602`、`MIDI`、`MP3`、`IRRecv`、`IRTrans`、`DelveBit`、`EncoderMotor`、`Scan_Rfid`、`Rfid`。当前官方构建页未展开这些类的成员，禁止凭旧版库猜测参数；在目标固件中先执行 `import bluebit; print(dir(bluebit))`。

## 9. `parrot`：扩展板电机与红外

```python
import parrot
from time import sleep

parrot.set_speed(parrot.MOTOR_1, 50)
parrot.set_speed(parrot.MOTOR_2, -50)
print(parrot.get_speed(parrot.MOTOR_1), parrot.get_speed(parrot.MOTOR_2))
sleep(1)
parrot.set_speed(parrot.MOTOR_1, 0)
parrot.set_speed(parrot.MOTOR_2, 0)
```

官方页面还展示 `IR_encode().encode_nec(address, command)` 与 `IR().send()/stop_send()/learn()/get_learn_data()`。电机速度范围 -100～100；电机必须使用扩展板适配供电，不能直接由 GPIO 驱动。

## 10. `ds18x20`：DS18B20 扫描和读取

```python
from machine import Pin
import onewire
import ds18x20
import time

bus = onewire.OneWire(Pin(Pin.P0))
sensor = ds18x20.DS18X20(bus)
roms = sensor.scan()
sensor.convert_temp()
time.sleep_ms(750)
for rom in roms:
    print(rom, sensor.read_temp(rom))
```

每次更新温度前调用 `convert_temp()`，之后至少等待 750ms。官方页面给出的器件供电范围为 3.0–5.5V，但连接掌控板数据线时仍按 3.3V 逻辑设计。

## 11. `servo`：角度控制

```python
from mpython import sleep_ms
from servo import Servo

servo = Servo(0, min_us=750, max_us=2250, actuation_range=180)
for angle in range(0, 181, 10):
    servo.write_angle(angle)
    sleep_ms(50)
```

控制引脚必须支持 PWM，两次写角度间隔至少 20ms。舵机使用独立受保护电源并按需要共地；先从保守脉宽和角度开始，出现堵转、嗡鸣或异常发热立即断电。

## 上板前检查

1. 在当前官方固件 REPL 逐个执行 `import` 和 `dir()`，确认模块实际存在。
2. 所有外接信号使用 3.3V 逻辑；外接负载独立核算峰值电流。
3. 网络示例替换为自己的公开测试端点，但不要把凭据写回 Skill。
4. P19/P20 与板载 I2C 共享，连接 blue:bit 或扩展板前扫描地址并检查上拉。
5. 本包未实机执行；任何官方页面未展开或疑似笔误的签名必须以当前固件为准。
