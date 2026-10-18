# 掌控板 2.0 API 与最小代码（官方文档 v2.0.1）

来源：盛思 mPython 官方文档 https://mpython.readthedocs.io/zh-cn/v2.0.1/index.html 。2026-10-16 在线核对同版本 `library/mPython/mpython.html`、`mpython_code.html` 及下列类库页面；以下为调用摘要和项目示例，不是完整文档镜像。该版本仅用于掌控板 2.0 的编程基线，不证明设备固件或所有外接驱动已就绪。

## 板载对象：从 mpython 导入，直接使用

| 功能 | 导入与调用 | 关键约定 |
| --- | --- | --- |
| OLED | `from mpython import oled`；`oled.fill(0)`、`oled.show()` | 128×64，x 为 0–127，y 为 0–63，颜色 0 灭/1 亮；绘图后必须 show |
| 中文 | `oled.DispChar(s, x, y)` | 内置 16 像素高字体，支持中文；不要用普通 text 显示中文 |
| 文本模式 | `from mpython import TextMode`；`oled.DispChar(s, x, y, TextMode.normal)` | normal/rev/trans/xor；普通 ASCII 可用 `oled.text(s, x, y, 1)` |
| A/B 按键 | `from mpython import button_a, button_b`；`button_a.value()` | 未按下为 1，按下为 0；不套用其他板的 is_pressed/ispressed |
| 触摸 | `from mpython import touchPad_P`；`touchPad_P.read()` | 对象名为 touchPad_P/Y/T/H/O/N，返回原始值；阈值需现场采样，不能当作布尔值或固定阈值 |
| 光线/声音 | `from mpython import light, sound`；`light.read()`、`sound.read()` | 0–4095 原始值，不直接标为 lux 或分贝 |
| 加速度 | `from mpython import accelerometer`；`accelerometer.get_x()` / `get_y()` / `get_z()` | 单位 g，默认范围 ±2g；不能把它当陀螺仪角速度 |
| 磁力计 | `from mpython import magnetic`；`magnetic.get_x()` / `get_y()` / `get_z()`、`get_heading()` | v2.0 及以上硬件；航向 0–360 度，水平放置，必要时按提示 calibrate；不据此假定有 gyroscope |
| RGB | `from mpython import rgb`；`rgb[0] = (8, 0, 0)`；`rgb.write()` | 3 颗灯，索引 0–2，RGB 通道 0–255；`rgb.fill((r,g,b))` 后仍需 write |
| RGB 亮度 | `rgb.brightness(0.2)` | 官方支持 0–1.0；首次示例用低亮度，结束时 fill((0,0,0)) 并 write |
| 延时 | `from mpython import sleep, sleep_ms, sleep_us` | 分别为秒、毫秒、微秒；循环要有适当延时与退出方法 |

按键中断可用 `button_a.irq(handler=callback, trigger=Pin.IRQ_FALLING)`，其中 `from machine import Pin`，回调接收一个引脚参数。初学/联调优先轮询；不要在中断里进行阻塞操作、网络或复杂绘图。

**BME280 并非板载。** 官方仅在共享 I2C 扫描到地址 0x77（119）时构建 `bme280` 对象；接入匹配模块且固件确实导出后才能使用 `temperature()`（℃）、`humidity()`（%）、`pressure()`（Pa）。不能仅因选了掌控板 2.0 就生成 `from mpython import bme280`。

## OLED 绘图

来自 [mpython](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython.html) 和其继承的 [framebuf](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/micropython/framebuf.html)：

- `oled.pixel(x, y, c)`、`oled.line(x1, y1, x2, y2, c)`、`oled.hline(x, y, w, c)`、`oled.vline(x, y, h, c)`。
- `oled.rect(x, y, w, h, c)` 轮廓；`oled.fill_rect(x, y, w, h, c)` 实心矩形。
- `oled.circle(x, y, radius, c)` 空心圆；`oled.fill_circle(x, y, radius, c)` 实心圆。沿用已验收的中心 (64,32)、半径 24 示例；坐标和半径应留在屏幕内。
- `oled.triangle(x0, y0, x1, y1, x2, y2, c)`、`oled.fill_triangle(...)`、`oled.RoundRect(x, y, w, h, r, c)`；RoundRect 大小写保持一致。
- `oled.contrast(brightness)` 范围 0–255；`oled.invert(0或1)`；`oled.poweron()` / `poweroff()`。

完整 main.py：空心圆（历史实物验收只覆盖此例）。

```python
from mpython import oled

oled.fill(0)
oled.circle(64, 32, 24, 1)
oled.show()
print("ZW_CIRCLE_OK")
```

完整 main.py：中文显示（本次只核对 API 与语法，未真机运行）。

```python
from mpython import oled

oled.fill(0)
oled.DispChar("掌控板2.0", 0, 0)
oled.DispChar("你好，掌问", 0, 20)
oled.show()
```

完整 main.py：光线/声音显示、A 键点亮 RGB、B 键退出，最多运行约 10 秒。无外接模块，不猜接线或触摸阈值。

```python
from mpython import oled, light, sound, button_a, button_b, rgb, sleep_ms

try:
    for _ in range(50):
        if button_b.value() == 0:
            break
        rgb.fill((0, 8, 0) if button_a.value() == 0 else (0, 0, 0))
        rgb.write()
        oled.fill(0)
        oled.DispChar("光线: %d" % light.read(), 0, 0)
        oled.DispChar("声音: %d" % sound.read(), 0, 20)
        oled.DispChar("B键退出", 0, 40)
        oled.show()
        sleep_ms(200)
finally:
    rgb.fill((0, 0, 0))
    rgb.write()
```

## 外接 I/O：逻辑引脚与原始 GPIO 不混用

`from mpython import MPythonPin, PinMode`，构造签名 `MPythonPin(pin, mode=PinMode.IN, pull=None)`。pin 是掌控板 P 号，如 `MPythonPin(0, PinMode.IN)` 指 P0，不能据此写成 `machine.Pin(0)`；后者按 ESP32 原始 GPIO 编号解释。使用 P 号前仍需确认模块接线、电平和该引脚支持模式。

**P1=GPIO32、P0=GPIO33**，由官方同版本[源码](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/mpython_code.html)的 `pins_remap_esp32=(33,32,…)` 核对。用户说“接P1”时，不得生成 `machine.Pin(1)` 或 `SIG_PIN=1; Pin(SIG_PIN, …)`；后者实际使用GPIO1，不能据此建议更换P口或判定模块损坏。需要 `time_pulse_us` 或切换输入输出时，使用底层Pin对象：

```python
from mpython import MPythonPin, PinMode
from machine import Pin, time_pulse_us
sig = MPythonPin(1, PinMode.OUT).Pin  # 板上P1，底层GPIO32
sig.init(Pin.IN, pull=None)
# time_pulse_us(sig, 1, 40000) 仅是脉宽采样；先按所选模块协议触发。
```

本机旧案例的引脚不是用户当前接线；用户明确改为P1时更新逻辑引脚，不能继续沿用P0。内部上拉读1、输出回读高或单次超时都不是断线、端口正常或传感器损坏的充分证据。

- `PinMode.IN` → `read_digital()`；`PinMode.OUT` → `write_digital(0或1)`。
- `PinMode.ANALOG` → `read_analog()`，返回 0–4095。
- `PinMode.PWM` → `write_analog(duty, freq=1000)`，duty 为 0–1023，频率 1–78125 Hz。
- `PinMode.OUT_DRAIN` 为开漏；pull 可为 None 或 `machine.Pin.PULL_UP/PULL_DOWN`。
- 官方同版本源码明确 P4/P10 占用于板载光线/声音，P2/P3 不支持数字输出；不是所有 P 口都支持 ADC/PWM。其余模式支持和引脚映射需查当前硬件资料，不从通用 ESP32 图猜测。
- `from mpython import i2c` 复用板载共享总线，P19=SCL、P20=SDA；可用 `i2c.scan()`、`i2c.readfrom(addr, nbytes)`、`i2c.writeto(addr, data)`。先确认外设地址与电气条件，勿重复初始化/释放共享总线，勿把 P19/P20 当任意数字输出。见 [machine.I2C](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/micropython/machine/machine.I2C.html)。

## 音乐、GUI 与网络

- [music](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/music.html)：`import music`；`music.play(notes, wait=True, loop=False)`、`music.pitch(frequency, duration=200)`、`music.stop()`、`music.set_tempo(ticks=4, bpm=120)`。默认输出 P6，先核对发声硬件；不要猜 `buzzer` 对象。文档 pitch 的默认 pin 写法与 play 不一致，优先省略默认 pin，外接输出须另行核对。
- [gui](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/gui.html)：`from gui import UI`、`ui = UI(oled)`；`ui.ProgressBar(x, y, width, height, progress)`，progress 为百分比；`ui.qr_code(s, x, y, scale=2)`，scale 为 1 或 2；绘制后 `oled.show()`。类名/方法大小写不可改成其他固件样式。
- Wi-Fi：`from mpython import wifi`；`net = wifi()`；`net.connectWiFi(ssid, password, timeout=10)`；`net.disconnectWiFi()`。用位置参数传 SSID/密码（文档和源码分别写 password/passwd），处理连接失败，不嵌入真实凭据或平台 API Key。
- [urequests](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/urequests.html)：`import urequests`；`response = urequests.get(url)` 或 `post(url, json=data)`；`response.text` / `response.json()`；在 finally 中 `response.close()`。不能套用电脑 requests 的完整参数集，尤其不要假定该固件支持 timeout 参数。
- [umqtt.simple](https://mpython.readthedocs.io/zh-cn/v2.0.1/library/mPython/umqtt.simple.html)：`from umqtt.simple import MQTTClient`；`MQTTClient(client_id, server, port=0, user=None, password=None, keepalive=0, ssl=False, ssl_params={})`；connect/publish/subscribe/check_msg/disconnect，消息和主题使用 bytes，退出释放连接；不把 wait_msg 当作非阻塞。

## 其他库与缺失资料

官方该版还列出 `audio`、`radio`、`sdcard`、`bluebit`、`parrot`、`ds18x20`，这是库目录，**不保证外接模块已连接、驱动已安装或可直接跨品牌替代**。这些库的具体调用需匹配选中的模块 Skill、准确型号及相应官方同版本章节。若当前模块的掌控板2.0本机案例已给出库导入、构造和方法，优先沿用其调用；本摘要未穷举该签名不是弃用案例或索要寄存器协议的理由。没有适用案例与参考，或实际导入/调用报错时，再针对缺少的资料或固件检查，不自行编造。

例如 DS18B20 是外接器件，不能当作板载温度计；BME280、磁力计和加速度计也不能互相替代。生成的程序只是待检查/接受代码；保存、检查、上传回读、运行提交与用户实物观察分别报告。
