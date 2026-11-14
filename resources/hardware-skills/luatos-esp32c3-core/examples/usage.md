# MicroPython 最小检查

以下为用户显式运行的短程序，前提是设备已有支持 UART0 REPL 的 MicroPython；出厂 LuatOS 不能直接运行。LED示例还须确认是外置Flash经典版及DIO模式，QIO/内置Flash变体不能照用GPIO12/13。

```python
# 先核对运行时；不会改变引脚或设备设置
import sys
print(sys.implementation)
```

```python
# 经典款 D4：GPIO12，高电平亮；3次后熄灭，不自动启动
from machine import Pin
from time import sleep_ms
led = Pin(12, Pin.OUT, value=0)
try:
    for _ in range(3):
        led.value(1)
        sleep_ms(200)
        led.value(0)
        sleep_ms(200)
finally:
    led.value(0)
```

预期为 D4 闪烁3次并熄灭，实际结果须由观察记录确认。该示例没有本板实测记录，不自动复制到用户 main.py，不把结构模型放入设备上传清单。
