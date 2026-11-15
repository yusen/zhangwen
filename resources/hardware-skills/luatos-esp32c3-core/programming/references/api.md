# API 与板型限制

- `from machine import Pin; Pin(12, Pin.OUT, value=0)`：经典板 D4；D5 为 GPIO13。高电平亮。先核对批次，测试结束拉低。
- LED示例前须确认外置Flash及DIO模式；QIO会占GPIO12/13，内置Flash芯片变体不可照用；不自动改Flash配置。
- `Pin(9, Pin.IN, Pin.PULL_UP).value()`：BOOT，按下为低；GPIO2/8/9为启动绑带，避免外设影响启动。
- UART0 GPIO21 TX / GPIO20 RX 已接 CH343P，保留给 REPL/文件通道。
- 物理8/9的TX/RX在商品图和官网文字表中相反，接线必须按实物丝印核对，不擅自裁决；GPIO21/20的芯片网络含义不变。
- I2C 示例分配可用 `I2C(0, scl=Pin(5), sda=Pin(4), freq=100000)`，必须与实际接线一致；这两个脚不是不可更改的固定 I2C。
- SPI 示例用 GPIO2 SCK / GPIO3 MOSI / GPIO10 MISO / GPIO7 CS，注意GPIO2绑带；以固件构造函数和实际接线为准。
- ADC1为GPIO0–4，GPIO5为ADC2且存在芯片/驱动限制；商品“2路ADC、4路PWM”不是完整芯片能力。ADC范围、衰减和Wi-Fi共用条件按所装固件核对。
- GPIO11是VDD_SPI，GPIO14–17为Flash信号，PWB是稳压使能，不用于普通外设。用户图中的物理脚4是GPIO12，物理脚12是RESET，不能混淆。
- GPIO为3.3V。5V/VBUS是供电，不是逻辑电平。外设电源与瞬态电流未验证。
- 当前不提供本板已核实的默认烧录镜像；不能自动烧录、切引导模式或改设备文件。

固件差异无法确认时，说明缺少哪一项信息；用户可在REPL查看 `import sys; print(sys.implementation)`。不得声称已上传、已测试或已看到 LED。
