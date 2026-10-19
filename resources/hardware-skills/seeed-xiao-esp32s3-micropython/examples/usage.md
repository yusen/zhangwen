# MicroPython 使用示例

## 适用范围

目标为基础版 XIAO ESP32S3 和兼容的官方 MicroPython `ESP32_GENERIC_S3` 构建。以下示例来自官方 API 方向的安全化整理，均未在当前环境接真实开发板测试。先阅读安全边界，确认 3.3 V 逻辑、外设供电、共地和板卡型号。

## 1. CPU 频率与 MCU 温度

```python
import machine
import esp32

print(machine.freq())
print(esp32.mcu_temperature())
```

温度是芯片内部温度，不等同于环境温度。改变 CPU 频率可能影响定时、功耗和外设，应只使用目标固件支持的值并重新验证。

## 2. 用户 LED（GPIO21）

```python
from machine import Pin
from time import sleep_ms

led = Pin(21, Pin.OUT)
for _ in range(6):
    led.value(not led.value())
    sleep_ms(250)
led.off()
```

官方硬件概览标记 USER_LED 为 GPIO21，但本包未验证有效电平；若亮灭相反，调整逻辑。不要把官方 MicroPython 页面的 GPIO6 示例当作板载 LED 定义。

## 3. GPIO 输入和输出

```python
from machine import Pin

output = Pin(2, Pin.OUT, value=0)   # D1 / GPIO2
button = Pin(3, Pin.IN, Pin.PULL_UP)  # D2 / GPIO3
output.value(button.value() == 0)
```

外接按钮只连接 GPIO 与 GND；若使用外部上拉，只能上拉到 3.3 V。

## 4. 定时器

```python
from machine import Timer

def on_tick(timer):
    print("tick")

timer = Timer(0)
timer.init(period=1000, mode=Timer.PERIODIC, callback=on_tick)
```

官方页面给出硬件定时器 ID 0–3，并说明虚拟定时器不受支持。回调应保持短小，结束时调用 `timer.deinit()`。

## 5. ADC

```python
from machine import ADC, Pin

adc = ADC(Pin(1))  # D0 / GPIO1
raw = adc.read_u16()
print(raw)
```

模拟输入不得超过 3.3 V 逻辑域。衰减、校准和 `read_uv()` 可用性依固件而异，需在目标板验证。

## 6. PWM

```python
from machine import Pin, PWM

pwm = PWM(Pin(2), freq=1000, duty_u16=32768)
print(pwm.freq())
pwm.deinit()
```

GPIO 只能驱动小信号；电机、继电器和大功率 LED 必须使用独立驱动与保护。

## 7. UART（D6/D7）

```python
from machine import UART

uart = UART(1, baudrate=9600, tx=43, rx=44)
uart.write(b"hello")
data = uart.read()
print(data)
```

UART 外设必须是 3.3 V TTL，TX/RX 交叉连接并共地。

## 8. 硬件 I2C（D4/D5）

```python
from machine import I2C, Pin

i2c = I2C(0, scl=Pin(6), sda=Pin(5), freq=400000)
print([hex(address) for address in i2c.scan()])
```

I2C 上拉只能接 3.3 V；地址和速率由所接外设决定。

## 9. 硬件 SPI（D8/D9/D10）

```python
from machine import Pin, SPI

spi = SPI(
    1,
    baudrate=10_000_000,
    sck=Pin(7),
    mosi=Pin(9),
    miso=Pin(8),
)
print(spi)
```

片选、极性和相位由外设决定。基础版 D8/GPIO7 是 SCK，D9/GPIO8 是 MISO，D10/GPIO9 是 MOSI。

## 10. WLAN 安全连接函数

```python
import network
from time import sleep_ms

def connect_wlan(network_name, network_credential, attempts=100):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    wlan.connect(network_name, network_credential)
    for _ in range(attempts):
        if wlan.isconnected():
            return wlan.ifconfig()
        sleep_ms(100)
    raise RuntimeError("network connection timed out")
```

`network_name` 和 `network_credential` 必须在运行时从安全配置注入，禁止写入 Skill、源码仓库或日志。该示例不自动执行连接。

## 11. SSD1306 OLED（可选外设）

```python
from machine import I2C, Pin
import ssd1306

i2c = I2C(0, scl=Pin(6), sda=Pin(5), freq=400000)
oled = ssd1306.SSD1306_I2C(128, 64, i2c)
oled.fill(0)
oled.text("XIAO ESP32S3", 0, 0)
oled.show()
```

`ssd1306` 不是板载显示能力；需外接 3.3 V 兼容 OLED，并确认模块地址、分辨率和驱动文件已安全安装。
