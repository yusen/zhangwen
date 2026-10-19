# RDK X5 使用示例

## 适用范围

目标为全板载标准版 RDK X5，系统为匹配硬件的 RDK OS 3.x。以下 Python 代码不会自动执行，未在当前环境连接实板测试。开始前使用独立 5 V / 5 A 电源，确认 40PIN 只接 3.3 V 信号，并根据官方引脚图检查物理针脚与复用状态。

## 1. 确认 Hobot.GPIO 目标板与编号模式

```python
import Hobot.GPIO as GPIO

print(GPIO.VERSION)
print(GPIO.model)
GPIO.setmode(GPIO.BOARD)
print(GPIO.getmode())
GPIO.cleanup()
```

预期 `GPIO.model` 为 `RDK_X5`。如果不是，停止接线并核对系统镜像与板卡型号。

## 2. 输入控制输出

```python
import Hobot.GPIO as GPIO

INPUT_PIN = 37
OUTPUT_PIN = 31

GPIO.setmode(GPIO.BOARD)
GPIO.setwarnings(True)
try:
    GPIO.setup(INPUT_PIN, GPIO.IN)
    GPIO.setup(OUTPUT_PIN, GPIO.OUT, initial=GPIO.LOW)
    GPIO.output(OUTPUT_PIN, GPIO.input(INPUT_PIN))
finally:
    GPIO.cleanup()
```

针脚号采用 BOARD 物理编号。输入只能在 GND 与 3.3 V 之间切换；输出只用于小信号或外部驱动器输入。

## 3. 硬件 PWM

```python
import Hobot.GPIO as GPIO
from time import sleep

PWM_PIN = 33

GPIO.setmode(GPIO.BOARD)
try:
    pwm = GPIO.PWM(PWM_PIN, 1000)
    pwm.start(10)
    sleep(1)
    pwm.ChangeDutyCycle(50)
    sleep(1)
    pwm.stop()
finally:
    GPIO.cleanup()
```

物理针脚 33 属于默认启用的 PWM3 组。只使用硬件 PWM 针脚，频率保持在官方 0.05 Hz 至 1 MHz 范围内；电机和大功率负载必须外接驱动与保护。

## 4. 只读系统信息

```python
import os
import platform

print(platform.machine())
print(platform.platform())
print(os.cpu_count())
```

这些是通用只读信息，不能替代 RDK OS 版本、BPU、温度或接口的专用验证。

## 5. 外设集成清单

在编写 I2C、SPI、UART、CAN、MIPI 或显示程序前，逐项确认：

1. 使用标准版 RDK X5 的官方针脚图，而不是 Module 载板图。
2. 外设供电、逻辑电平、峰值电流与主板能力匹配。
3. `srpi-config` 中同组复用功能没有冲突，并已按要求重启。
4. 相机、TF 卡、DSI、CAN 和天线都在完全断电时连接。
5. 网络名称和凭据由运行时安全配置注入，不写入 Skill、代码或日志。
