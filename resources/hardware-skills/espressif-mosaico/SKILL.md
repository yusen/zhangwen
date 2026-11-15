---
name: espressif-mosaico
description: ESP32-S31主控；板载BMI270六轴IMU、双BMM150磁力计、触摸屏、音频、电池与NAND，掌问生成Lua并通过WiFi上传运行。
---

# ESP-Mosaico（Chat Coding）

日常使用掌问模型生成Lua，用户审阅保存后点击「上传并运行」。无需USB或板载模型API。首次WiFi运行服务安装与重启分别由用户确认；设备原生Claw聊天仅在手动切换后使用设备模型。暂不做原生C/C++应用编译或固件刷写。

<!-- zhangwen:mosaico-onboard:v1 -->
## 已核对的板载硬件（2026-10-31）

**Mosaico自带BMI270六轴IMU（3轴加速度计+3轴陀螺仪），不需要另接MPU6050，也不需要先把IMU添加为外接模块。另有两颗BMM150三轴磁力计，不能把磁力计当成IMU。**

依据官方CoreBoard V1.2用户指南及BSP固定提交7cbfb390；保留V1.0/V1.2差异，V1.1按当前BSP映射为V1.2。硬件存在、当前固件驱动可用和本次实物运行成功是三件不同的事。资料版本不能替代实物丝印或当前固件配置。

| 部件 | 板载事实与用途 | Lua编程依据 |
| --- | --- | --- |
| ESP32-S31NRV16 | 双核RISC-V，最高320 MHz；16 MB封装内PSRAM，16 MB NOR，1 Gbit/128 MB SPI NAND | 标准Lua与Claw模块；不是MicroPython |
| BMI270 | 六轴IMU，7位I²C地址0x69，共享传感器中断GPIO2；摇晃、倾斜、翻转/运动采样 | `require("imu")`，`imu.new({device=...})`；read返回raw accel/gyro，不直接是g或°/s |
| 两颗BMM150 | 7位地址0x11、0x12；磁场/磁吸边缘感知，校准后才能讨论航向 | `require("magnetometer")`；两个板级名称须来自固件，不能把示例名称当成两颗实物的名称 |
| 显示与触摸 | CO5300，480×480 QSPI，2.16英寸；V1.2官方触摸CST9220系列 | `display.open()`/`screen:touch()`或`lvgl`，以当前返回宽高和touch_available为准 |
| 音频 | ES8311（0x19）、NS4150B功放、板载麦克风和扬声器 | `audio.open_input()`/`audio.open_output()`；音频初始化由固件负责 |
| 电池 | 3.7 V/65 mAh锂电池；BQ27220（0x55）电量计、TP4057充电、SAM8108开关机 | 固件提供时用`lib_fuel_gauge`；板载电量计不表示当前Lua库必然已安装 |
| 按键/反馈 | AI键GPIO7低有效、BOOT GPIO61；振动马达GPIO8高有效 | `button`/`gpio`，须避开当前固件已占用资源；POWER键不是普通AI键 |
| USB及无线 | USB 2.0 HS OTG；芯片支持Wi-Fi6、Bluetooth5.4、802.15.4 | 芯片支持不等于当前Claw有对应Lua绑定；当前掌问通过局域网固定接口上传运行 |
| 左右扩展槽 | 左H2、右H1，两组2×10P/2.54mm；右侧旋转180°；标准模块EEPROM左0x50/右0x51 | 摄像头、摇杆、交互、ToF、热像、继电器、灯矩阵是额外模块，不是主板自带 |

### 板型与资源约束

- V1.2板内I2C0：SDA GPIO56、SCL GPIO3；板外I2C1：SDA GPIO0、SCL GPIO1。V1.0板内/板外共用I2C0 GPIO0/1。不要重复`i2c.new()`初始化固件占用的板内总线；优先板级传感器对象，需要时仅借用已初始化的正确总线。
- V1.2 LCD_RST=GPIO44、LCD_SCL=GPIO42，V1.0相反。V1.2取消程序可控状态LED（旧GPIO3）与codec独立电源控制（旧GPIO56）；**V1.2 GPIO3是I²C时钟，不能沿用旧LED闪烁例程。**
- 右槽GPIO49/52/54/37/40与ES8311 I2S复用；使用板载音频时不能当作空闲扩展IO。GPIO60控制屏幕与对外3.3V/5V，低有效；不要为普通采样切断电源。GPIO57用于关机请求，BSP按开漏处理。
- 摄像头是额外模块且只支持左H2；DVP占用GPIO33/34（与USB Serial/JTAG冲突），需按相机示例采用UART调试。相机使用GPIO14时暂停该脚的普通EEPROM地址选择用途；当前管理器仍能探测固定0x50。
- 摄像头模块PCB V1.2使用OV3640、V1.4使用SC101IOT，这是摄像头模块版本，不是CoreBoard版本。交互模块含GL5506光敏、AS312 PIR、AO3400A驱动红外（默认NEC/38kHz）、6颗WS2812及两路按键/触摸，描述符板型0x16；这些均属外接模块。安装/更换模块先断开供电，不将软件插槽探测等同于带电插拔许可。
- EEPROM ACK、有效描述符、槽位已被驱动独占是三个独立状态；识别到模块名称不等于有Lua驱动。ToF 0x29和MLX90640 0x33共享总线时各只接一个同地址模块。

### 回答与代码生成

询问“板载IMU”“摇晃”“倾斜小球”“翻转检测”时，先利用上面的BMI270事实和下方Lua API，不再询问用户有没有外接IMU或索要已知的板内接线。可以先给短小有界原始采样程序；固件注册名称、量程或实际错误确实未知时，明确具体缺项。`imu_sensor`是上游文档示例名称，未证明所有Mosaico固件都用这个名字。不能因此否认板上有IMU，也不能静默换成外接MPU6050。

官方BSP是ESP-IDF C/C++参考，不是当前Lua程序。现有Lua绑定可支持的逻辑才转换为Lua；ESP-NOW组网、完整离线语音模型、USB副屏、模块EEPROM写入等不能因存在BSP示例就宣称掌问当前可直接运行。生成、保存、回读、提交、实际观察分别记录；本Skill不授予模型设备、Shell、串口或联网执行权限。

- [器件、地址与完整扩展引脚](references/specifications.md)
- [Lua与原生API边界](references/integration.md)
- [全部24个BSP示例及使用条件](examples/usage.md)
- [来源、冲突与版本](references/sources.md)
- [兼容约束](references/compatibility-rules.md)
- [操作边界](references/safety.md)
- [验收](tests/validation-cases.md)
