# 外接硬件 API

## 舵机

验证级别：D；供电为 C。

```python
from unihiker_k10 import servo

servo_1 = servo(1)
servo_1.angle(value=90)
```

端口示例为 P1，角度范围按官方页面为 0～180°。

上电时先移动到安全中位；大舵机必须独立供电并共地。

## RGB 灯带

```python
from unihiker_k10 import neopixel

strip = neopixel(0, 3)
strip.brightness(9)
strip.write(0, 1, 0x00, 0x00, 0xFF)
```

官方页面注释与示例端口描述存在文字不一致，端口号应以构造参数和实际接线为准。

## DHT11/DHT22

```python
from unihiker_k10 import dht

sensor = dht(0)
temperature, humidity = sensor.read()
```

官方说明可自动识别 DHT11 或 DHT22。

## DS18B20

```python
from unihiker_k10 import ds18b20

sensor = ds18b20(1)
temperature = sensor.read()
```

## 超声波

```python
from unihiker_k10 import ultrasonic

sensor = ultrasonic(trig=0, echo=0)
distance = sensor.distance()
```

官方说明 trig 和 echo 使用同一端口时可用于 SEN0388。

## 重量/力传感器 KIT0176

```python
from unihiker_k10 import force

sensor = force()
sensor.zero()
value = sensor.read()
```

官方示例还使用：

```python
sensor.read(mass=False)
```

页面文字对默认返回“质量/力”的说明存在表述冲突。正式项目应通过已知砝码和串口输出验证单位，不应仅凭注释决定。

## GPIO、ADC 与 PWM

```python
from unihiker_k10 import pin

p0 = pin(0)
p1 = pin(1)
p2 = pin(2)
```

数字：

```python
p0.read_digital()
p0.write_digital(value=0)
p0.write_digital(value=1)
```

模拟输入：

```python
p0.read_analog()
```

模拟/PWM 输出：

```python
p1.write_analog(value=500, freq=255)
```

官方示例的 `value` 使用 0、500、1000；正式项目应先用小功率负载验证范围和频率含义。

## GPIO 限制

官方说明：

- P0/P1 为板载全功能端口；
- 其余部分 GPIO 经 I2C 转 GPIO 芯片扩展；
- 扩展 GPIO 只有基础高低电平能力。

不要假设所有引脚均支持 ADC、PWM、中断或高速通信。
