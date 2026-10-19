# 行空板 K10 MicroPython 使用示例

本文件把行空板 K10 官方 MicroPython 页面中的 API 用法整理为独立、可复制的 `main.py` 示例。代码针对
K10 专用 MicroPython 固件，不适用于行空板 M10、标准桌面 Python 或未包含 K10 库的通用 ESP32 固件。

- 官方资料：https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10
- 文档查阅日期：2026-07-17。
- 页面当前提供 Mind+ K10 扩展 0.0.5 或以上，并链接测试版 MicroPython 固件 V0.9.8；官方明确提示该固件
  仍可能存在问题。
- 本次验证级别：逐项核对官方 API、移除示例凭据、Python 语法检查通过；未在真实 K10 上逐例运行，
  因此不得描述为“已实机验证”。

## 智能工程师生成代码时必须遵守

1. 每次只选择与用户需求相关的最小示例，不把摄像头、AI、音频、Wi-Fi 和全部传感器拼进一个程序。
2. 默认生成一个完整 `main.py`，保留全部 import、对象初始化、主循环、节流和资源清理，不输出省略号。
3. 只使用本文件已经出现的 K10 API；不得臆造类名、方法名、参数名、返回字段或单位。
4. `light.read()` 的官方页面没有声明单位，变量只能命名为原始光线值，不得自动标成 lux。
5. Wi-Fi、MQTT 和服务端参数必须由用户提供或从项目配置读取；不得写入真实 SSID、密码、Token 或服务器凭据。
6. AI 模式按单任务使用；退出时调用 `ai.deinit_ai()`。摄像头画面示例与 AI 图像示例不能混用两套摄像头对象。
7. P0/P1 是全功能 IO；其他扩展 GPIO 只按基础数字输入/输出使用。所有外部信号必须满足 3.3 V 逻辑上限。
8. 烧录固件、擦除 Flash、上传文件和重启设备不是示例代码的隐式步骤，必须走应用的设备确认流程。

## 1. 屏幕显示摄像头画面

```python
import time

from k10_base import Camera
from unihiker_k10 import screen


camera = Camera()
screen.init(dir=2)
camera.init()
screen.show_camera(camera)

while True:
    time.sleep(1)
```

## 2. 屏幕绘制图形和文字

```python
import time

from unihiker_k10 import screen


screen.init(dir=2)
screen.show_bg(color=0xFFFF00)
screen.set_width(width=4)
screen.draw_line(x0=10, y0=10, x1=120, y1=80, color=0x0000FF)
screen.draw_point(x=150, y=20, color=0xFF0000)
screen.draw_rect(
    x=40,
    y=100,
    w=100,
    h=60,
    bcolor=0xFF6666,
    fcolor=0xFFFFFF,
)
screen.draw_circle(
    x=190,
    y=120,
    r=35,
    bcolor=0x00AA00,
    fcolor=0x0000FF,
)
screen.draw_text(
    text="K10 ready",
    x=10,
    y=180,
    font_size=24,
    color=0x202020,
)
screen.show_draw()

while True:
    time.sleep(1)
```

## 3. A/B 按键状态与事件

```python
import time

from unihiker_k10 import button


button_a = button(button.a)
button_b = button(button.b)


def on_a_pressed():
    print("A pressed")


def on_a_released():
    print("A released")


def on_b_pressed():
    print("B pressed")


def on_b_released():
    print("B released")


button_a.event_pressed = on_a_pressed
button_a.event_released = on_a_released
button_b.event_pressed = on_b_pressed
button_b.event_released = on_b_released

while True:
    print("A=", button_a.status(), "B=", button_b.status())
    time.sleep(0.2)
```

## 4. 温湿度、环境光和屏幕看板

`light.read()` 只按官方页面称为环境光读取值，不推断 lux 单位。

```python
import time

from unihiker_k10 import light, rgb, screen, temp_humi


screen.init(dir=2)
rgb.brightness(3)

while True:
    temperature_c = temp_humi.read_temp()
    humidity = temp_humi.read_humi()
    light_value = light.read()

    screen.show_bg(color=0xFFFFFF)
    screen.draw_text(
        text="Temp: {} C".format(temperature_c),
        x=10,
        y=20,
        font_size=24,
        color=0x202020,
    )
    screen.draw_text(
        text="Humidity: {} %RH".format(humidity),
        x=10,
        y=55,
        font_size=24,
        color=0x202020,
    )
    screen.draw_text(
        text="Light: {}".format(light_value),
        x=10,
        y=90,
        font_size=24,
        color=0x202020,
    )
    screen.show_draw()
    print(temperature_c, humidity, light_value)
    time.sleep(1)
```

若需求只读取环境光，使用下面的最小程序：

```python
import time

from unihiker_k10 import light


while True:
    print(light.read())
    time.sleep(0.1)
```

## 5. 三轴加速度

```python
import time

from unihiker_k10 import acce


while True:
    x = acce.read_x()
    y = acce.read_y()
    z = acce.read_z()
    print("x=", x, "y=", y, "z=", z)
    time.sleep(0.1)
```

## 6. 三颗板载 RGB 灯

```python
import time

from unihiker_k10 import rgb


rgb.brightness(5)

while True:
    rgb.write(num=0, R=255, G=0, B=0)
    rgb.write(num=1, R=0, G=255, B=0)
    rgb.write(num=2, R=0, G=0, B=255)
    time.sleep(1)
    rgb.clear()
    time.sleep(1)
```

## 7. TF 卡目录检查

```python
import os

from k10_base import TF_card


tf_card = TF_card()
files = os.listdir("/sd")
print("Files in /sd:", files)
```

需要记录数据时，必须另外处理文件关闭、定期同步、空间不足和意外断电；不得把只列目录的示例扩写成
未经确认的无限写入循环。

## 8. 板载麦克风和扬声器

系统存储录制与播放：

```python
import time

from unihiker_k10 import mic, speaker


filename = "sound.wav"
mic.recode_sys(name=filename, time=5)
time.sleep(1)
speaker.play_sys_music(filename)
```

TF 卡录制与播放要求已经正确挂载 TF 卡：

```python
import time

from unihiker_k10 import mic, speaker


filename = "sound.wav"
mic.recode_tf(name=filename, time=5)
time.sleep(1)
speaker.play_tf_music(filename)
```

方法名 `recode_sys` 和 `recode_tf` 是 K10 官方页面当前公开的实际拼写，不得擅自改成 `record_*`。

## 9. Wi-Fi 连接

真实网络信息不能写入 Hardware Skill。智能工程师应从用户输入或项目配置取得下面两个值。

```python
from k10_base import WiFi


NETWORK_NAME = ""
NETWORK_PASSPHRASE = ""

if not NETWORK_NAME or not NETWORK_PASSPHRASE:
    raise ValueError("请先从用户输入或项目配置读取 Wi-Fi 信息")

wifi = WiFi()
wifi.connect(ssid=NETWORK_NAME, psd=NETWORK_PASSPHRASE, timeout=50000)

if wifi.status():
    print("Wi-Fi connected")
    print(wifi.info())
else:
    print("Wi-Fi connection failed")
```

## 10. 蓝牙 HID 键盘

配对成功后，A 键发送空格，B 键发送 `Ctrl+A`。使用按键事件避免长按时在轮询循环中连续发送。

```python
import time

from unihiker_k10 import button, hid, keycode, screen


button_a = button(button.a)
button_b = button(button.b)
ble_keyboard = hid(name="K10-HID")


def send_space():
    if ble_keyboard.isconnected():
        ble_keyboard.keyboard_send(keycode.SPACE)


def send_select_all():
    if ble_keyboard.isconnected():
        ble_keyboard.keyboard_send([keycode.CTRL, keycode.a])


button_a.event_pressed = send_space
button_b.event_pressed = send_select_all

screen.init(dir=2)
while True:
    state = "HID connected" if ble_keyboard.isconnected() else "Waiting for HID"
    screen.show_bg(color=0xFFFF00)
    screen.draw_text(text=state, line=1, font_size=24, color=0x202020)
    screen.show_draw()
    time.sleep(0.2)
```

## 11. 离线语音识别与语音合成

```python
import time

import asr


def on_command(command_id):
    if command_id == 1:
        asr.add_tts_data("灯光已打开")
    elif command_id == 2:
        asr.add_tts_data("灯光已关闭")
    print("command id:", command_id)


asr.init_asr()
asr.set_asr_callback(on_command)
asr.add_asr_command(1, "kai deng")
asr.add_asr_command(2, "guan deng")
asr.start_asr()
asr.start_tts()

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    asr.free_asr()
```

## 12. AI 移动检测

```python
import time

import ai
from unihiker_k10 import screen


ai.init_ai()
ai.camera_start()
ai.move_detect()
screen.init()

try:
    while True:
        frame = ai.camera_capture()
        screen.show_camera_img(frame)
        if ai.is_ai_data_updated():
            result = ai.get_ai_data()
            print("move_flag:", result["move_flag"])
        time.sleep_ms(1)
except KeyboardInterrupt:
    ai.deinit_ai()
```

## 13. AI 二维码识别

```python
import time

import ai
from unihiker_k10 import screen


ai.init_ai()
ai.camera_start()
ai.code_scanner()
screen.init()

try:
    while True:
        frame = ai.camera_capture()
        screen.show_camera_img(frame)
        if ai.is_ai_data_updated():
            result = ai.get_ai_data()
            code_data = result["code_data"]
            if code_data:
                print("QR code:", code_data)
        time.sleep_ms(1)
except KeyboardInterrupt:
    ai.deinit_ai()
```

## 14. AI 猫脸检测

```python
import time

import ai
from unihiker_k10 import screen


ai.init_ai()
ai.camera_start()
ai.cat_detect()
screen.init()

try:
    while True:
        frame = ai.camera_capture()
        screen.show_camera_img(frame)
        if ai.is_ai_data_updated():
            result = ai.get_ai_data()
            print("cat_flag:", result["cat_flag"])
            if result["cat_flag"]:
                cat = result["cat_detect"]
                print("frame_length:", cat["frame_length"])
                print("frame_width:", cat["frame_width"])
        time.sleep_ms(1)
except KeyboardInterrupt:
    ai.deinit_ai()
```

## 15. AI 人脸注册与识别

A 键注册当前人脸，B 键触发识别。

```python
import time

import ai
from unihiker_k10 import button, screen


button_a = button(button.a)
button_b = button(button.b)


def register_current_face():
    ai.register_face()


def recognize_current_face():
    ai.recognize_face()


button_a.event_pressed = register_current_face
button_b.event_pressed = recognize_current_face

ai.init_ai()
ai.camera_start()
ai.face_recognize_start()
screen.init()

try:
    while True:
        frame = ai.camera_capture()
        screen.show_camera_img(frame)
        if ai.is_ai_data_updated():
            result = ai.get_ai_data()
            print("face_flag:", result["face_flag"])
            if result["face_flag"]:
                face = result["face_detect"]
                print("face_id:", face["face_id"])
                print("left_eye:", face["left_eye"])
        time.sleep_ms(1)
except KeyboardInterrupt:
    ai.deinit_ai()
```

## 16. P1 控制舵机

```python
import time

from unihiker_k10 import servo


servo_p1 = servo(1)

while True:
    servo_p1.angle(value=10)
    time.sleep(1)
    servo_p1.angle(value=170)
    time.sleep(1)
```

接线要求：P1 只接信号；舵机使用独立、满足堵转电流的电源，并让外部电源 GND 与 K10 GND 共地。

## 17. P0 控制三颗 RGB 灯带灯珠

```python
import time

from unihiker_k10 import neopixel


strip = neopixel(0, 3)
strip.brightness(5)

while True:
    strip.write(0, 1, 0x00, 0x00, 0xFF)
    time.sleep(1)
    strip.write(0, 1, 0x00, 0x00, 0x00)
    time.sleep(1)
```

灯带电源按总电流独立核算；不得从信号引脚给灯带供电。

## 18. P0 读取 DHT11 或 DHT22

```python
import time

from unihiker_k10 import dht


dht_sensor = dht(0)

while True:
    temperature, humidity = dht_sensor.read()
    print("temperature:", temperature)
    print("humidity:", humidity)
    time.sleep(1)
```

## 19. P1 读取 DS18B20

```python
import time

from unihiker_k10 import ds18b20


temperature_sensor = ds18b20(1)

while True:
    print("temperature:", temperature_sensor.read())
    time.sleep(1)
```

## 20. P0 单线超声波传感器

官方页面说明：`trig` 与 `echo` 使用相同引脚时，对应单线 SEN0388 接法。其他超声波型号必须按其实际
双线接口指定不同引脚，不能照抄本例。

```python
import time

from unihiker_k10 import ultrasonic


sensor = ultrasonic(trig=0, echo=0)

while True:
    print("distance:", sensor.distance())
    time.sleep(0.1)
```

## 21. 重量传感器 KIT0176

官方页面要求读取前先清零，并说明默认质量单位为克、`mass=False` 返回力值。代码同时保留两个读数，
不把两种单位混写。

```python
import time

from unihiker_k10 import force


force_sensor = force()
force_sensor.zero()

while True:
    mass_g = force_sensor.read()
    force_n = force_sensor.read(mass=False)
    print("mass_g:", mass_g, "force_n:", force_n)
    time.sleep(0.5)
```

## 22. GPIO、ADC 与 PWM

P0/P1 支持完整 IO；示例中的 P2 只演示扩展 GPIO 数字输出。

```python
import time

from unihiker_k10 import pin


p0 = pin(0)
p1 = pin(1)
p2 = pin(2)

p2.write_digital(1)
time.sleep(1)
p2.write_digital(0)

while True:
    print("P0 digital:", p0.read_digital())
    print("P0 analog:", p0.read_analog())

    p1.write_analog(value=0, freq=255)
    time.sleep(1)
    p1.write_analog(value=500, freq=255)
    time.sleep(1)
    p1.write_analog(value=1000, freq=255)
    time.sleep(1)
```

模拟输入信号不得超过 3.3 V。智能工程师不得把金手指的其他扩展 GPIO 当成 ADC 或 PWM 引脚。

## 官方页面中暂不作为黄金代码的内容

- MQTT：页面片段导入 `WiFi` 与 `MqttClient`，但没有创建 `wifi` 和 `mqttclient` 对象，并包含示例网络凭据。
  在构造方式、代理地址、账号和主题由用户确认前，智能工程师必须先追问，不能从该片段猜测可运行代码。
- 重复移动检测：官方页面连续出现两段相同示例，本文件只保留一个规范版本。
- 固件烧录：页面包含擦除与烧录步骤，但它们是高风险设备操作，不进入自动生成代码和 Hardware Skill
  隐式执行范围。

## 外接硬件通用接线边界

```text
K10 P0/P1（信号） ←→ 最高 3.3 V 的外设信号
K10 3V3           → 仅给明确支持 3.3 V 且电流允许的外设供电
K10 GND           ↔ 外设 GND / 独立电源 GND
```

使用外设前先运行本地硬件组合校验。舵机、灯带和其他大电流负载独立供电；5 V 模拟输出、数字输出或
I2C 上拉不得直接进入 K10 的 3.3 V GPIO/ADC。
