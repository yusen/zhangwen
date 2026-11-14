# 电气与主控资料

```zhangwen:hardware-spec:v1
{
  "schema": "zhangwen.hardware-skill/v1",
  "componentId": "hw_luatos_esp32c3_core",
  "name": "esp32C3",
  "category": "MCU",
  "electrical": {
    "voltage": 3.3,
    "voltageMin": null,
    "voltageMax": null,
    "supplyVoltages": [3.3, 5.0],
    "logicLevel": 3.3,
    "peakCurrent": 0.0,
    "communicationProtocol": "GPIO",
    "i2cAddress": null,
    "supportedMCUs": [],
    "driverName": "machine",
    "firmwareRequirement": "须由用户确认已安装支持 UART0 REPL 的 ESP32_GENERIC_C3 MicroPython；出厂 LuatOS 不能直接运行 main.py"
  },
  "stock": 0,
  "price": 0.0,
  "ageRecommendation": null,
  "safetyTags": ["3.3V逻辑", "经典款CH343P串口", "启动绑带引脚", "高度暂定", "不自动烧录"],
  "notes": "51×21mm PCB；4MB SPI Flash；Type-C 经 CH343P 接 UART0 GPIO21(TX)/20(RX)。5V 为开发板输入，3.3V 为稳压轨，GPIO 不耐5V。峰值电流0表示未知，不能据此计算电源余量。型号与固件未做实板验收。",
  "verificationStatus": "OFFICIAL_REFERENCE_UNTESTED",
  "sourceIds": ["https://wiki-zh.luatos.org/chips/esp32c3/board.html", "https://wiki-zh.luatos.org/chips/esp32c3/hardware.html", "https://micropython.org/download/ESP32_GENERIC_C3/"]
}
```

ESP32-C3 为单核 RISC-V、最高 160MHz，支持 2.4GHz Wi-Fi 与 Bluetooth LE；本板外置 4MB Flash。芯片能力、板上接线与所装固件分别核对。MicroPython 是否提供某模块及其 API 以设备固件为准。

## 32 个排针位置

以下编号沿用用户引脚图：从元件面看，天线在上、USB 在下；左列从上到下 1–16，右列从上到下 17–32。官方原理图 J2 是连接器符号编号，方向不同，不能直接将其编号当成下表物理编号。GPIO 名称与信号网络可交叉核对。

UART位置存在来源冲突：商品图把物理8标TX、9标RX，官方板页文字表却把8列U0_RX、9列U0_TX。本表保留用户图方向并标为待核对；GPIO21=UART0_TX、GPIO20=UART0_RX的芯片网络不变，接线必须查实物背面丝印/对应批次图，不能凭这两项物理编号接线。

| 左物理脚 | 信号 | 右物理脚 | 信号 |
| --- | --- | --- | --- |
| 1 | GND | 17 | GND |
| 2 | GPIO0 / ADC1_CH0 | 18 | 3.3V |
| 3 | GPIO1 / ADC1_CH1 | 19 | GPIO2 / ADC1_CH2 / 启动绑带 |
| 4 | GPIO12 / D4 LED | 20 | GPIO3 / ADC1_CH3 |
| 5 | GPIO18 / USB D- | 21 | GPIO10 |
| 6 | GPIO19 / USB D+ | 22 | GPIO6 |
| 7 | GND | 23 | GPIO7 |
| 8 | GPIO21 / UART0 TX | 24 | GPIO11 / VDD_SPI |
| 9 | GPIO20 / UART0 RX | 25 | GND |
| 10 | GPIO13 / D5 LED | 26 | 3.3V |
| 11 | NC | 27 | GPIO5 / ADC2_CH0 |
| 12 | RESET / EN | 28 | GPIO4 / ADC1_CH4 |
| 13 | 3.3V | 29 | GPIO8 / 启动绑带 |
| 14 | GND | 30 | GPIO9 / BOOT / 启动绑带 |
| 15 | PWB / 稳压器使能 | 31 | 5V / VBUS |
| 16 | 5V / VBUS | 32 | GND |

两侧均为 16 脚，2.54mm 节距，排间中心距 17.78mm。GPIO12/13 在这块经典板上接 LED，但通用芯片指南把 GPIO12–17 列为通常用于外部 Flash 的一组；本板的 Flash 数据线为 GPIO14–17，GPIO11 是 VDD_SPI 网络。不要把通用“全可用 GPIO”表直接套到本板。

## 接口使用说明

- GPIO 编号用于 `machine.Pin(n)`；物理脚号 1–32 不能直接传给 Pin。
- UART0 接 USB-UART；使用 GPIO20/21 连接外设会与 REPL/上传通道冲突。
- 用户图里的 UART1(GPIO0/1)、I2C(GPIO5/4)、SPI(GPIO2/3/10/7) 和 PWM01–04 是示意映射。ESP32 GPIO 矩阵和 MicroPython 参数决定实际分配，不是每个接口专用的固定脚。
- GPIO2/8/9 为启动绑带；BOOT 将 GPIO9 拉低。先核对上电外部电平，不能让外设改变启动模式。
- 用户商品表写“2路12比特ADC/4路PWM”，引脚图同时出现 ADC4，口径不一致。芯片具有 ADC1 五通道(GPIO0–4)及 ADC2 单通道(GPIO5)，PWM 有6个 LEDC 通道；不以商品表限制芯片能力，也不承诺所有通道在特定 MicroPython/无线状态下可用。ADC2 有芯片/驱动限制，优先用 ADC1 并查所装固件。
- D4=GPIO12、D5=GPIO13，官方经典款参考为高电平亮；首次只做用户明确运行的有时限测试。
- 经典款外置Flash使用DIO，两线数据方式释放GPIO12/13；QIO模式会将其复用为SPIHD/SPIWP。内置Flash芯片变体的GPIO11/12/13也不可照用；先核对固件Flash模式和芯片型号，不能自动改配置。
- PWB 属稳压使能，GPIO11 属 VDD_SPI；两者不作为普通信号脚。NC 不使用。
