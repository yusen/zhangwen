# 集成说明

## 目标与版本边界

本资料面向基础版 Seeed Studio XIAO ESP32S3，固件使用与 ESP32-S3 兼容的官方 MicroPython `ESP32_GENERIC_S3` 构建。Seeed 页面示例包含两个不同日期的同版本固件文件名，因此不把某个文件名固定为唯一要求；下载时应从官方 MicroPython 固件页选择当前兼容构建并在板上确认。

本 Skill 不包含烧录、擦除 Flash、上传脚本或主机串口操作命令，也不授予这些权限。若确需首次烧录，请在包外遵循 Seeed 官方页面和工具安全流程，并自行确认目标设备与备份。

## 基础版引脚表

MicroPython `Pin()` 使用 ESP32-S3 实际 GPIO 号。

| XIAO 丝印 | GPIO | 主要能力 | MicroPython 提示 |
|---|---:|---|---|
| D0 | 1 | GPIO、ADC、Touch | `Pin(1)` / `ADC(Pin(1))` |
| D1 | 2 | GPIO、ADC、Touch | `Pin(2)` / `ADC(Pin(2))` |
| D2 | 3 | GPIO、ADC、Touch | `Pin(3)` / `ADC(Pin(3))` |
| D3 | 4 | GPIO、ADC、Touch | `Pin(4)` / `ADC(Pin(4))` |
| D4 | 5 | GPIO、ADC、Touch、I2C SDA | `Pin(5)` |
| D5 | 6 | GPIO、ADC、Touch、I2C SCL | `Pin(6)` |
| D6 | 43 | GPIO、UART TX | `Pin(43)` |
| D7 | 44 | GPIO、UART RX | `Pin(44)` |
| D8 | 7 | GPIO、ADC、Touch、SPI SCK | `Pin(7)` |
| D9 | 8 | GPIO、ADC、Touch、SPI MISO | `Pin(8)` |
| D10 | 9 | GPIO、ADC、Touch、SPI MOSI | `Pin(9)` |
| USER_LED | 21 | 板载用户 LED | `Pin(21)`；先验证有效电平 |
| BOOT | 0 | 启动配置 | 不作为普通外设引脚的默认选择 |
| 3V3 | — | 3.3 V 稳压输出 | 官方说明最多可取 700 mA |
| 5V | — | USB VBUS 输入/输出 | 外部输入必须串联二极管 |
| BAT | — | 电池输入 | 典型 3.7 V，严格核对极性 |
| GND | — | 公共地 | 外设信号必须共地 |

## 官方 MicroPython 能力

- `machine.freq()`：读取或设置 CPU 频率；页面列出 20、40、80、160、240 MHz。
- `esp32.mcu_temperature()`：读取 MCU 内部温度；这不是环境温度传感器。
- `network.WLAN`：STA/AP、扫描、连接、接口信息；网络名称和凭据必须由运行时安全注入，禁止写回 Skill。
- `time`：秒、毫秒、微秒延时和 ticks 计时。
- `machine.Timer`：硬件定时器 ID 0–3；官方页面说明该端口不支持虚拟定时器。
- `machine.Pin`：基础版可用外部 GPIO 号 1–9、43、44；GPIO21 为用户 LED。
- `machine.UART`：推荐板载串口映射 TX=GPIO43、RX=GPIO44。
- `machine.PWM`：支持输出引脚；页面给出基础频率 1 Hz–40 MHz，并说明高频会降低占空比分辨率。
- `machine.ADC`：基础版 GPIO1–9 可用；支持 `read_u16()`，`read_uv()` 是否可用需按目标固件确认。
- `machine.SoftSPI` / `machine.SPI`：软件 SPI 可选输出引脚；硬件 SPI 示例使用 SPI(1)、SCK=GPIO7、MOSI=GPIO9、MISO=GPIO8。
- `machine.SoftI2C` / `machine.I2C`：硬件 I2C 示例使用 I2C(0)、SCL=GPIO6、SDA=GPIO5、400 kHz。
- `esp.flash_size()` 可读取 Flash 容量。页面还列出低层 Flash 擦写 API，但本 Skill 排除破坏性调用，不提供调用示例。

## 推荐上电与初始化

1. 断电状态下确认使用基础版板卡、GND 共地、GPIO 不承受 5 V。
2. 优先用 USB Type-C 5 V 供电；若使用 BAT 或 5V 引脚供电，先按官方电源说明检查极性和隔离二极管。
3. 接入单个外设，确认其供电电压、逻辑电平和峰值电流，再接总线信号。
4. 启动 REPL 后先读取 `machine.freq()`，再用最小 GPIO 或总线扫描程序验证固件和引脚。
5. 对板载 LED、ADC 电压换算、PWM 频率和低功耗数据做目标固件与实板验证后再用于产品逻辑。

## 页面冲突与板卡差异

- MicroPython 页面展示的 LED 示例使用 GPIO6；硬件概览把基础版 USER_LED 标为 GPIO21。不要把 GPIO6 当作板载 LED，应以 GPIO21 起步并确认有效电平。
- MicroPython 页面硬件 SPI 表将 SCK 写成 D7，但其代码与硬件引脚图使用 GPIO7；基础版丝印 GPIO7 对应 D8。本包采用 D8/GPIO7。
- 页面个别文字误写 ESP32C3；本包只采用 XIAO ESP32S3 的代码映射和硬件表。
- Sense 的摄像头、数字麦克风、存储卡以及 Plus 的扩展引脚均不属于基础版默认能力。

## 故障排查

- I2C 扫描为空：核对 SDA=D4/GPIO5、SCL=D5/GPIO6、共地、上拉和外设供电。
- SPI 无响应：核对 D8/GPIO7 为 SCK、D9/GPIO8 为 MISO、D10/GPIO9 为 MOSI，以及外设片选和 SPI 模式。
- UART 乱码：核对 D6/GPIO43 TX、D7/GPIO44 RX、交叉接线、共地和波特率。
- ADC 饱和或异常：确保模拟输入未超过 3.3 V 逻辑域，并在目标固件验证衰减、校准和 `read_uv()` 支持。
- LED 不亮：验证 GPIO21 的有效电平，不要照抄页面中的 GPIO6 示例。
- 无线或高负载复位：先检查电源瞬态和布线；最大峰值电流未知，不能按 19 mA 静态典型值设计电源。
