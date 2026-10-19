# 掌控板 3.0 集成说明

## 供电

| 方式 | 接法 | 边界 |
|---|---|---|
| USB | USB 端输入 5V | USB 接入时，3V3 金手指为板载稳压后的 3.3V 输出。 |
| 金手指供电 | 3V3 与 GND | 仅在未连接 USB 时输入 2.7–3.6V；不得输入 5V。 |

## 金手指与触摸引脚

| 板端 | ESP32-S3 GPIO | 官方功能 |
|---|---:|---|
| P0 | GPIO1 | ADC、数字输入、PWM/数字输出、TouchPad |
| P1 | GPIO2 | ADC、数字输入、PWM/数字输出、TouchPad |
| P2 | GPIO3 | ADC、数字输入、PWM/数字输出、TouchPad |
| P3 | GPIO4 | ADC、数字输入、PWM/数字输出、TouchPad |
| P4 | GPIO5 | ADC、数字输入、PWM/数字输出、TouchPad |
| P5 | GPIO0 | ADC、数字输入、PWM/数字输出、板载按键 A |
| P6 | GPIO7 | ADC、数字输入、PWM/数字输出、TouchPad |
| P7 | GPIO8 | ADC、数字输入、PWM/数字输出、板载 RGB LED |
| P8 | GPIO15 | 数字输入、PWM/数字输出、NeoPixel |
| P9 | GPIO16 | 数字输入、PWM/数字输出、NeoPixel |
| P10 | GPIO6 | ADC、数字输入、PWM/数字输出、板载声音传感器 |
| P11 | GPIO46 | 数字输入、PWM/数字输出、按键 B、NeoPixel |
| P12 | GPIO21 | 数字输入、PWM/数字输出、板载蜂鸣器 |
| P13 | GPIO17 | 数字输入、PWM/数字输出、NeoPixel |
| P14 | GPIO18 | 数字输入、PWM/数字输出、NeoPixel |
| P15 | GPIO48 | 数字输入、PWM/数字输出、NeoPixel |
| P16 | GPIO47 | 数字输入、PWM/数字输出、NeoPixel |
| P19 | GPIO43 | 数字 I/O、I2C SCL、板载 I2C 共享、NeoPixel |
| P20 | GPIO44 | 数字 I/O、I2C SDA、板载 I2C 共享、NeoPixel |
| Touch P/Y/T/H/O/N | GPIO9/10/11/12/13/14 | 六路板载电容触摸输入 |

官方汇总为 20 通道数字 I/O、其中 12 路 PWM、6 路触摸；6 路 12bit ADC 为 P0–P4、P6；支持 I2C、1 路最高 115200bps UART 和 SPI。

## 板内专用引脚

| 子系统 | GPIO |
|---|---|
| LCD | BL 33、CS 34、RS 35、SCK 36、SDA 37 |
| ES8388 音频 | DOUT 38、MCLK 39、DIN 40、BCK 41、LRCK 42 |

这些引脚由板载硬件占用，不应在不了解固件初始化状态时作为通用扩展 GPIO 重用。

## MicroPython 固件/API

- 官方固件基于 MicroPython 与 ESP-IDF 二次开发。
- 板载入口为 `from mpython import *`；核心对象包括 `display`、`light`、`sound`、`accelerometer`、`gyroscope`、`magnetic`、`button_a`、`button_b`、`rgb`、`i2c` 和 `MPythonPin`。
- 上电后先用当前官方固件完成 REPL 导入检查，再运行最小读取和显示程序。

## 故障排查

- 无法启动：断开全部外设，改用可靠 USB 线与 5V USB 电源，检查 3V3 是否被外部电源反灌。
- I2C 无设备：检查 P19/P20、共地、地址冲突、上拉电压及板载共享设备。
- 传感器读数异常：确认对象来自掌控板 3.0 当前固件，不要照搬掌控板 2.0 的引脚假设。
- 音频或屏幕异常：不要重配 GPIO33–42；先恢复官方固件初始化流程。

## mPython 3.0 完整类库

本节依据官方 mPython 类库索引的全部 10 个子页面整理。共收录 159 个由页面显式声明的类、函数、方法、事件或属性入口；`bluebit` 的若干 `autoclass` 和 `parrot` 的 `automodule` 在官方构建页未展开成员，本文保留官方公开类名与示例用法，不猜测缺失签名。

### 模块导航

- `mpython`：板载硬件、显示、GUI、传感器和 GPIO
- `music`：音乐与蜂鸣器
- `urequests`：HTTP 客户端
- `umqtt.simple`：MQTT 客户端
- `radio`：ESP-NOW 无线广播
- `sdcard`：SPI SD 卡
- `bluebit`：blue:bit 套件驱动
- `parrot`：掌控扩展板
- `ds18x20`：DS18B20 单总线温度
- `servo`：PWM 舵机

### 通用使用边界

- 只面向掌控板 3.0 官方 MicroPython 固件；不使用 `educore`。
- 网络 API 先完成 WLAN 联网；HTTP 响应必须 `close()`，MQTT 主题和消息按官方文档使用 `bytes`。
- `radio` 基于 ESP-NOW，频道范围 1–13；收发设备必须使用相同频道。
- SD 卡使用 FAT/FAT32，并在断电接线后通过 SPI 初始化和 `os.mount()` 挂载。
- 舵机、电机等大电流负载不得由 GPIO 直接供电；需要独立受保护电源并按需要共地。
- 所有代码在部署前先用当前固件 REPL 执行 `import`、`dir()` 和最小调用核对；本包不声称真实板卡实测。

## `mpython`：板载硬件、显示、GUI、传感器和 GPIO

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/mpython.html

### `mpython` --- 板载硬件相关函数

`mpython` 是基于掌控板封装的专有模块,内含掌控板板载资源相关功能函数。 详细代码实现可查阅 `mpython.py源码 ` 。

#### tft显示屏

掌控板板载1.47寸320*172分辨率显示屏，可以用来显示彩色文字、图片、简单动画。

通过display对象，可以实现相关显示功能。

##### `display.DispChar(str, x, y, color=lcd.WHITE, auto_wrap = False)`

类型：API。

内置思源中文字体显示函数，参数：

- `str` 待显示的字符串

- `x` 显示坐标x

- `y` 显示坐标y

- `color` 字体颜色，默认白色

- `auto_wrap` 是否换行，默认不换行

##### `display.DispChar_font(font, str, x, y, color=lcd.WHITE, auto_wrap = False)`

类型：API。

内置数码管及dvsm字体显示函数，这些字体由font-to-py.py制作，内置的只有英文和数字，用户可用这个工具自已制字体，参数：

- `font` 待显示的字体名

- `str` 待显示的字符串

- `x` 显示坐标x

- `y` 显示坐标y

- `color` 字体颜色，默认白色

- `auto_wrap` 是否换行，默认不换行

##### `display.clear(color = lcd.BLACK)`

类型：API。

清屏（背景设置）函数

- `color` 背景颜色,默认黑色

##### `display.show():`

类型：API。

缓存内容送显示屏显示

> **Attention**
>

##### `class framebuf.FrameBuffer(buffer, width, height, format, stride=width, /)`

类型：API。

构造一个 FrameBuffer 对象。

- `buffer` 缓存区

- `width height` 缓存区宽度、高度

- `format` 像素点类型，掌控板V3强制为RGB565

- `stride` 行像素点字节数

##### `display.fill(color)`

类型：API。

显存填充函数，通常用来设置显示背景, 通常不会直接调用，使用上面的display.clear(color = lcd.BLACK)。

- `color` 待填充颜色

##### `display.fill_rect(x, y, w, h, color)`

类型：API。

显存局部区域填充函数, 通常用来清除局部区域内容。

- `x y` 起点坐标

- `w h` 区域宽度、高度

- `color` 填充颜色

##### `display.pixel(x, y, color)`

类型：API。

设置/获取相应坐标点颜色。

- `x y` 显示坐标

- `color` 填充颜色,无此参数时，为获取点颜色

##### `display.hline(x, y, w, color)`

类型：API。

画水平线。

- `x y` 起点坐标

- `w` 水平线长

- `color` 填充颜色

##### `display.vline(x, y, h, color)`

类型：API。

画垂直线。

- `x y` 起点坐标

- `h` 垂直线长

- `color` 填充颜色

##### `display.rect(x, y, w, h, color)`

类型：API。

画矩形。

- `x y` 起点坐标

- `w h` 矩形宽度、高度

- `color` 填充颜色

##### `display.line(x1, y1, x2, y2, color)`

类型：API。

画直线。

- `x1 y1` 起点坐标

- `x2 y2` 终点坐标

- `color` 填充颜色

##### `display.circle(x, y, radio, color)`

类型：API。

画圆。

-- `x y` 圆心坐标

- `radio` 半径

- `color` 圆弧颜色

##### `display.quarter_circle(x, y, radio, cornername, color)`

类型：API。

画1/4圆。

-- `x y` 圆心坐标

- `radio` 半径

- `cornername` 所在象限

- `color` 圆弧颜色

##### `display.fill_circle(x, y, radio, color)`

类型：API。

画实心圆。

-- `x y` 圆心坐标

- `radio` 半径

- `color` 填充颜色

##### `display.triangle(x0, y0, x1, y1, x2, y2, color)`

类型：API。

画三角形。

- `x0 y0 x1 y1 x2 y2` 三个角点坐标

- `color` 边颜色

##### `display.fill_triangle(x0, y0, x1, y1, x2, y2, color)`

类型：API。

画实心三角形。

- `x0 y0 x1 y1 x2 y2` 三个角点坐标

- `color` 填充颜色

##### `display.RoundRect(x, y, w, h, r, color)`

类型：API。

##### `display.round_rect(x, y, w, h, r, color)`

类型：API。

画圆角矩形。

- `x y` 起点坐标

- `w h` 矩形宽高

- `r` 倒角半径

- `color` 边颜色

##### `display.ellipse(x, y, xr, yr, color, mask)`

类型：API。

画椭圆弧。

- `x y` 起点坐标

- `xr yr` x y轴半径

- `color` 边颜色

- `mask`  0x01:画第一象限 0x02:画第二象限 0x04:画第三象限 0x08:画第四象限 0xff:画完整椭圆 0x10:填充椭圆

##### `display.blit(fb, x, y, key=-1, palette=None)`

类型：API。

将一个缓存区，绘入显示framebuf给定位置。

- `fb` 待绘制缓存区

- `x y` 起点坐标

- `key` 如果指定了键，那么它应该是一个颜色整数，相应的颜色将被视为透明：所有具有该颜色值的像素都不会被绘制

- `palette` palette 参数支持在不同格式的帧缓冲区之间进行位块传输。典型用法是将单色或灰度的字形 / 图标渲染到彩色显示器上。该调色板是一个帧缓冲区实例，其格式与当前帧缓冲区的格式一致。调色板的高度为 1 个像素，其像素宽度等于源帧缓冲区中的颜色数量。N 位源的调色板需要 2**N 个像素；单色源的调色板有 2 个像素，分别代表背景色和前景色。应用程序为调色板中的每个像素分配一种颜色。当前像素的颜色将与调色板中某个像素的颜色一致，该像素的 x 坐标即为对应源像素的颜色。

##### `display.text(str, x, y, color)`

类型：API。

绘制micropython内置字体，不能显示中文，掌控板上显示过小，一般不用。

- `str` 待显示的字符串

- `x y` 显示坐标

- `color` 字体颜色，默认白色

##### `display.decode_png_internal(index)`

类型：API。

解码内置png图片，返回图片宽高及framebuf对象。

- `index` 内置图片索引

##### `display.background_color(color)`

类型：API。

设置/获取背景颜色，有参数为设置，否帽获取

- `color` 背景颜色

#### GUI库

GUI库实现一些基础GUI功能：进度条、二维码、时钟、图象解码、图表、表格。

##### `class gui.UI()`

类型：API。

构造一个UI对象。

##### `ui.ProgressBar(x, y, width, height, progress, color= lcd.WHITE)`

类型：API。

绘制一个进度条。

- `x y` 显示坐标

- `width height` 矩形宽高

- `progress` 进度值

- `color` 颜色

##### `ui.stripBar(self, x, y, width, height, progress, dir=1, frame_color=lcd.WHITE, color=lcd.WHITE)`

类型：API。

绘制一个进度条。

- `x y` 显示坐标

- `width height` 矩形宽高

- `progress` 进度值

- `frame_color` 边框颜色

- `color` 颜色

##### `ui.qr_code(str, x, y, scale = 4)`

类型：API。

绘制一个二维码。

- `str` 二维码内容

- `x y` 显示坐标

- `scale` 缩放比例

##### `class gui.Image()`

类型：API。

构造一个Image对象,用于加载Image图象，当前支持png格式。

##### `ui.load(path, invert=0)`

类型：API。

加载并解码图片文件。

- `path` 图片文件路径

- `invert` 图片反转，参数暂未用

##### `class gui.MicroExcelTable(self, display = display, x0=0, y0=0, cols=3, rows=4, cell_width=85, cell_height=30, col_header_text_color=lcd.RED, row_header_width=60, row_header_text_color=lcd.RED, data_text_color=lcd.WHITE, border_color=lcd.GREEN, show_border=True, font_size=(16, 16), cross_text="")`

类型：API。

构造一个表格对象。

- `cols rows` 行列数

- `cell_width cell_height` 单元格宽高

- `col_header_text_color` 列表头文本颜色

- `row_header_width` 行表头宽

- `row_header_text_color` 行表头文本颜色

- `data_text_color` 数据区文本颜色

- `border_color` 数据区边框颜色

- `show_border` 是否显示边框

- `font_size` 字体宽高

- `cross_text` 表头交叉处文本

##### `exectable.draw_headers(col_header_data, row_header_data)`

类型：API。

绘制表头内容。

- `col_header_data` 列表头内容，e.g. ["温度", "湿度", "气压"]

- `row_header_data` 行表头内容，e.g. ["设备1", "设备2", "设备3"]

##### `exectable.update_data(new_data)`

类型：API。

更新整个数据区内容。

- `new_data` 数据区内容

##### `exectable.update_cell(row, row, text)`

类型：API。

更新整个数据区内容。

- `row row` 待更新表格行列值

- `text` 待更新内容

##### `exectable.clear_all()`

类型：API。

清除内容。

##### `class gui.MicroChart(display = display, x0=0, y0=0, width=200, height=100, val_min = 0, val_max = 100, bg_color=lcd.BLACK, axis_color=lcd.WHITE, data_colors=[lcd.RED, lcd.GREEN, lcd.BLUE], padding=10)`

类型：API。

构造一个图表对象

- `display` 显示器

- `x0 y0` 位置

- `width height` 图表宽高

- `val_min val_max` 数值范围

- `bg_color` 背景颜色

- `axis_color` 坐标轴颜色

- `data_colors` 数据颜色列表，多条数据线时，可分别设置颜色

- `padding` 偏移

##### `chart.draw_axis(show_ticks=True)`

类型：API。

绘制坐标轴

- `show_ticks` 是否显示刻度

##### `chart.draw_grid(grid_color=None)`

类型：API。

绘制参考点

- `grid_color` 点颜色

##### `chart.draw_line_chart(data, show_grid=False)`

类型：API。

绘制折线图

- `data` 待绘制数据

- `show_grid` 是否显示参考点

##### `chart.draw_bar_chart(data, show_grid=False)`

类型：API。

绘制柱状图

- `data` 待绘制数据

- `show_grid` 是否显示参考点

#### 声音、光线

##### `light.read()`

类型：API。

读取板载光线传感器值，范围0~4095。

##### `sound.read()`

类型：API。

读取板载麦克风，范围0~4095。

#### 加速度计

通过accelerometer对象，您可以获取3轴加速度计值，单位g。 加速度范围±2g/±4g/±8g/±16g,默认为±2g。

##### `accelerometer.get_x()`

类型：API。

获取x轴上的加速度测量值，正整数或负整数，具体取决于方向。

##### `accelerometer.get_y()`

类型：API。

获取y轴上的加速度测量值，正整数或负整数，具体取决于方向。

##### `accelerometer.get_z()`

类型：API。

获取z轴上的加速度测量值，正整数或负整数，具体取决于方向。

##### `accelerometer.set_range(range)`

类型：API。

设置加速度范围,在默认,不修改为,范围在±2g。

加速度范围值为以下常量:

========================== ========= =================
常量                       值      定义
RANGE_2G                   0        范围±2g
RANGE_4G                   1        范围±4g
RANGE_8G                   2        范围±8g
RANGE_16G                  3        范围±16g
========================== ========= =================

##### `accelerometer.set_resolution(resolution)`

类型：API。

设置加速度分辨率,默认,不修改为10bit分辨率。

分辨率值为以下常量:

========================== ========= =================
常量                       值      定义
RES_14_BIT                  0      14 bit 分辨率
RES_12_BIT                  1      12 bit 分辨率
RES_10_BIT                  2      10 bit 分辨率
========================== ========= =================

##### `accelerometer.set_offset(x=None, y=None, z=None)`

类型：API。

该函数用于校准加速度计的3个轴(x,y,z)的加速值偏差。一般情况下无需校准,只有当遇到加速度偏差较大时修正。
注意,校准数据断电后不会保存。`x` , `y` , `z` 为调整偏差值,可修正范围±1g。
掌控板v2.3版本以上，掉电会保存校准数据。

##### `accelerometer.roll_pitch_angle()`

类型：API。

返回通过加速度计计算得出的欧拉角(横滚角roll、俯仰角pitch)。注意，偏航角(yaw)需要角速度，故无法测得。返回2元组（roll,pitch），单位角度。

假定，掌控板为飞机：

- 横滚角指飞机两翼所在的平面与平行线之间的夹角，机体向右滚为正,范围为[-180,180].
- 俯仰角是指机头与水平面的夹角,当飞机平行时则为0,抬头时则为正,范围为[-180,180]

> **Attention**
>

##### 运动侦测事件

提供多种平面倾斜、翻转、敲击（类似鼠标点击）、掉落的运动姿态事件。用户可预先设定回调函数，当事件发生后，触发事件回调。
回调函数定义如，function_callback(event)。`event` 参数为对应事件常量。

###### `accelerometer.event_tilt_left`

类型：属性。

向左倾斜

###### `accelerometer.event_tilt_right`

类型：属性。

向右倾斜

###### `accelerometer.event_tilt_up`

类型：属性。

向前倾斜

###### `accelerometer.event_tilt_down`

类型：属性。

向后倾斜

###### `accelerometer.event_face_up`

类型：属性。

正面朝上

###### `accelerometer.event_face_down`

类型：属性。

正面朝下

###### `accelerometer.event_single_click`

类型：属性。

单次敲击，类似鼠标的单击操作。

###### `accelerometer.event_double_click`

类型：属性。

连续敲击两次，类似鼠标的双击操作。

###### `accelerometer.event_freefall`

类型：属性。

坠落

event事件定义如下:

================================== =========
事件                              值
accelerometer.TILT_LEFT           0
accelerometer.TILT_RIGHT          1
accelerometer.TILT_UP             2
accelerometer.TILT_DOWN           3
accelerometer.FACE_UP             4
accelerometer.FACE_DOWN           5
accelerometer.SINGLE_CLICK        6
accelerometer.DOUBLE_CLICK        7
accelerometer.FREEFALL            8
================================== =========

> **Attention**
>

> accelerometer 事件的简单应用：官方页面引用 `/_static/examples/accelerometer/accelerometer_event.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

#### 陀螺仪(gyroscope)

通过gyroscope对象，您可以获取陀螺仪角速度值，角速度的单位是dps(°/S)。
角速度范围±16dps/±32dps/±64dps/±128dps/±256dps/±512dps/±1024dps/±2048dps ,默认为±256 dps。

##### `gyroscope.get_x()`

类型：API。

获取x轴上的角速度测量值，具体取决于方向。

##### `gyroscope.get_y()`

类型：API。

获取y轴上的角速度测量值，具体取决于方向。

##### `gyroscope.get_z()`

类型：API。

获取z轴上的角速度测量值，具体取决于方向。

##### `gyroscope.set_range(range)`

类型：API。

设置角速度范围,默认不修改为,范围在±256 dps。

角速度范围值为以下常量:

========================== ========= =================
常量                       值          定义
RANGE_16_DPS               0         范围±16 dps
RANGE_32_DPS               16        范围±32 dps
RANGE_64_DPS               32        范围±64 dps
RANGE_128_DPS              48        范围±128 dps
RANGE_256_DPS              64        范围±256 dps
RANGE_512_DPS              80        范围±512 dps
RANGE_1024_DPS             96        范围±1024 dps
RANGE_2048_DPS             112       范围±2048 dps
========================== ========= =================

##### `gyroscope.set_offset(x=None, y=None, z=None)`

类型：API。

该函数用于校准陀螺仪的3个轴(x,y,z)的角速值偏差。一般情况下无需校准,只有当遇到角速度偏差较大时修正。
`x` , `y` , `z` 为调整偏差值,可修正范围±1024dps。

> **Attention**
>

#### 磁力计(magnetic)

MMC5983MA磁力计函数接口,可获取3轴磁感应强度、地磁场强度、获取电子罗盘角度。

> **Attention**
>

##### `magnetic.get_x()`

类型：API。

获取x轴的磁感应值,正整数或负整数,范围±8191,单位mG(毫高斯)。

##### `magnetic.get_y()`

类型：API。

获取y轴的磁感应值,正整数或负整数,范围±8191,单位mG(毫高斯)。

##### `magnetic.get_z()`

类型：API。

获取z轴的磁感应值,正整数或负整数,范围±8191,单位mG(毫高斯)。

##### `magnetic.get_field_strength()`

类型：API。

返回计算后的磁感应值,即3轴磁力的和。计算公式,x^2+y^2+z^2的平方根。

##### `magnetic.peeling()`

类型：API。

磁力去皮。类似电子秤去皮功能, `peeling()` 后,下次 `get_field_strength()` 返回的值为减去当前磁力值后计算得出的结果。可用于去除地磁感应值的测量应用。

##### `magnetic.clear_peeling()`

类型：API。

磁力去皮功能取消。使用 `peeling()` 后,可用该函数,恢复正常地磁测量。

##### `magnetic.get_heading()`

类型：API。

获取电子罗盘角度,即改方向与地磁北极的夹角,掌控板的正上方,即USB位置视为正北方。单位角度,范围0~360。

> **Attention**
>

> **Attention**
>

##### `magnetic.calibrate()`

类型：API。

电子罗盘校准。当掌控板周边存在强磁干扰,可使用该函数清除强磁分量,才能计算准确的地磁北偏角。注意,断电后不保存校准偏移值。

校准方法,按照掌控板显示屏指示步骤操作:

1. 掌控板水平放置,在水平面旋转数圈,过程约15秒。
2. 掌控板垂直放置,沿着垂直于地面轴旋转数圈,过程约15秒。

> 磁力计应用--指北针：官方页面引用 `/_static/examples/magnetic/compass.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

#### 蜂鸣器(music)

由 `music` 模块驱动掌控板蜂鸣器,具体操作详见 `music` 模块。

#### button_[a,b]对象

掌控板上的a,b按键。button_a/button_b 是 `Button` 类的实例对象。使用 `machine.Pin.irq` 中断实现。定义了
`event_pressed` 和 `event_released` 按键按下、释放事件。 用户可轻易的实现事件回调。除此外，还实现当前或过去按键状态、按键次数等函数方法。

##### `Button(pin_num, reverse=False)`

类型：API。

Button类，按键抽象类。

- `pin_num` - IO引脚号
- `reverse` - 默认为reverse为False。适用于触发为低电平按键。如是触发为高电平按键，将reverse设为True，翻转下。

掌控板上button_a、button_b的实例::

button_a = Button(Pin.P5)
button_b = Button(Pin.P11)

当按键事件发生，触发事件回调。回调函数定义如，function_callback(pin), `pin` 为该引脚的machine.Pin对象返回。

##### `Button.event_pressed`

类型：属性。

按键按下事件。

##### `Button.event_released`

类型：属性。

按键释放事件。

> Button 事件回调的简单应用：官方页面引用 `/_static/examples/button/button_event.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

##### `Button.value()`

类型：API。

获取按键引脚电平状态。1为高电平，0位低电平。

>>> button_a.value()
>>> 1
>>> button_a.value()
>>> 0

##### `Button.is_pressed()`

类型：API。

返回当前是否按住。 `True` 表示按键按下，`False` 则未按下。

##### `Button.was_pressed()`

类型：API。

返回 `True` 或 `False` 指示自设备启动以来或上次调用此方法以来是否按下按钮。调用此方法将清除按下状态，因此必须再次按下按钮，然后才能再次返回 `True` 。

##### `Button.get_presses()`

类型：API。

返回按键的按下总数，并在返回之前将该总数重置为零。注意，计数器超过100将不再计数。

##### `Button.irq(handler=None, trigger=(Pin.IRQ_FALLING | Pin.IRQ_RISING), priority=1, wake=None)`

类型：API。

配置在引脚的触发源处于活动状态时调用的中断处理程序。用法与 machine.Pin.irq 一样。

参数:

- `handler` 是一个可选的函数，在中断触发时调用。

- `trigger` 配置可以触发中断的事件。可能的值是：

- `Pin.IRQ_FALLING` 下降沿中断
- `Pin.IRQ_RISING` 上升沿中断
- `Pin.IRQ_LOW_LEVEL` 低电平中断
- `Pin.IRQ_HIGH_LEVEL` 高电平中断

这些值可以一起进行 `OR` 运算以触发多个事件。

- `priority` 设置中断的优先级。它可以采用的值是特定于端口的，但是更高的值总是代表更高的优先级。

- `wake` 选择此中断可唤醒系统的电源模式。它可以是 `machine.IDLE` ， `machine.SLEEP` 或 `machine.DEEPSLEEP` 。

这些值也可以进行 `OR` 运算，使引脚在多种功耗模式下产生中断。

此方法返回一个回调对象。

>>> from mpython import *
>>> button_a.irq(trigger=Pin.IRQ_FALLING, handler=lambda p:print("button-a press！"))

#### touch对象

掌控板上共有6个触摸引脚分别touchpad_p/y/t/h/o/n。是Touch类的实例对象，具体包含函数方法如下。

##### `Touch(pin)`

类型：API。

##### `Touch.event_pressed`

类型：属性。

触摸按键按下事件。当按键事件发生，触发事件回调。回调函数定义如，function_callback(value), `value` 为该触摸按键的状态值。

##### `Touch.event_released`

类型：属性。

触摸按键释放事件。

##### `Touch.read()`

类型：API。

返回触摸值

##### `Touch.config(threshold)`

类型：API。

触摸阈值设置

##### `Touch.is_pressed()`

类型：API。

返回当前是否按住。 `True` 表示按键按下，`False` 则未按下。

##### `Touch.was_pressed()`

类型：API。

返回 `True` 或 `False` 指示自设备启动以来或上次调用此方法以来是否按下按钮。调用此方法将清除按下状态，因此必须再次按下按钮，然后才能再次返回 `True` 。

##### `Touch.get_presses()`

类型：API。

返回按键的按下总数，并在返回之前将该总数重置为零。注意，计数器超过100将不再计数。

#### rgb对象

用于控制掌控板的3颗RGB ws2812灯珠。rgb对象为neopixel的衍生类，继承neopixel的方法。更多的使用方法请查阅 `neopixel` 。

##### `rgb.write()`

类型：API。

把数据写入RGB灯珠中。

> **Hint**
>

通过给rgb[n]列表赋值来写入RGB颜色值。如，rgb[0]=(50,0,0)

from mpython import *

rgb[0] = (255, 0, 0)  # 设置为红色，全亮度
rgb[1] = (0, 128, 0)  # 设定为绿色，半亮度
rgb[2] = (0, 0, 64)   # 设置为蓝色，四分之一亮度

rgb.write()

##### `rgb.fill(rgb_buf)`

类型：API。

填充所有LED像素。

##### `rgb.brightness(brightness)`

类型：API。

亮度调节,范围0~1.0

#### i2c对象

mPython掌控板已实例 `I2C` 类，P19、P20 为I2C的SCL、SDA引脚。I2C设备可连接掌控板I2C总线进行操作。

详细有关I2C的读写操作，请查看 `machine.I2C` 模块或 `I2C基础教程` 章节。

#### MPythonPin类

##### `MPythonPin(pin, mode=PinMode.IN,pull=None)`

类型：API。

构建Pin对象

- `pin` 掌控板定义引脚号，具体定义看查看 `掌控板引脚定义` 。

- `mode` 引脚模式。未设定时,默认 `mode` = `PinMode.IN`

- `PinMode.IN` 等于1，数字输入模式
- `PinMode.OUT` 等于2，数字输出模式
- `PinMode.PWM` 等于3，模拟输出模式
- `PinMode.ANALOG`

#### 映射

##### `numberMap(inputNum,bMin,bMax,cMin,cMax)`

类型：API。

映射函数，参数：

- `inputNum` 为需要映射的变量

- `bMin` 为需要映射的最小值

- `bMax` 为需要映射的最大值

- `cMin` 为映射的最小值

- `cMax` 为映射的最大值

## `music`：音乐与蜂鸣器

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/music.html

### `music` --- 音乐相关功能函数

`music` 模块与micro:bit的music使用方法相同。

要使用music模块，你需要::

import music

#### 音符

以下是音符格式:

NOTE[octave][:duration]

- `NOTE` - 表示音符c、d、e、f、g、a、b。注意,“#”表示将基本音级升高半音；“b”表示将基本音级降低半音。音符 `R` ，则将其视为休息（静音）。例如，c#为C-升半音,ab为A-降半音
- `octave` - 表示音高,默认为4，为中音
- `duration` - 表示音符持续时长的节拍,默认为4节拍

例如，`A1:4` 音高为1的"A"音符，持续4个节拍（节拍也可以由 `set_tempo` 函数设定 - 见下文）。

贝多芬第五交响曲的开头::

['r4:2', 'g', 'g', 'g', 'eb:8', 'r:2', 'f', 'f', 'f', 'd:8']

八度音阶的定义和范围符合本页列出的关于科学音高表示法的表格 `科学音调记号法`.  例如，middle "C"是 `c4` 和concert “A”（440）是 `a4` 。八度音符从音符"C"开始。

#### 函数

##### `set_tempo(ticks=4, bpm=120)`

类型：API。

设置播放节奏。

- `ticks` - 音符时值,整数。默认为4,即为四分音符为一拍。

- `bpm` - 节拍速度,整数。单位,bmp(每分钟节拍数)。

可参考以下设置播放节奏:

* `music.set_tempo()` - 将播放节奏设置恢复为 ticks = 4, bpm = 120
* `music.set_tempo(ticks=8)` - 只改变音符时值,八分音符为一拍
* `music.set_tempo(bpm=180)` - 只改变节拍速度

计算节拍时长（以毫秒为单位）的计算方式： `60000/bpm/ticks_per_beat` ::

对于默认的值, 60000/120/4 = 125 milliseconds or 1 beat = 500 milliseconds

##### `get_tempo()`

类型：API。

获取当前速度作为整数元组: `(ticks, bpm)`.

##### `play(music, pin=6, wait=True, loop=False)`

类型：API。

- `music`

- 播放 `music` 包含上面定义的音乐DSL。

- 如果 `music` 是一个字符串，则应该是单个音符，例如 `'c1:4'`。

- 如果 `music` 被指定为音符列表（如上面音乐DSL部分中所定义），则它们一个接一个地播放以执行旋律。

- `pin` 默认是掌控板的P6引脚

- `wait` 阻塞：如果 `wait` 设置为 `True`, 为阻塞,否则未不。

- `loop` ：如果 `loop` 设置为 `True` ，则重复调整直到stop被调用（见下文）或阻塞调用被中断。

##### `pitch(frequency, duration=-1, pin=Pin.P6, wait=True)`

类型：API。

- `frequency`, `duration`:以给定指定毫秒数的整数频率播放频率。例如，如果频率设置为440并且长度设置为1000，那么我们会听到标准A调一秒钟。

如果 `duration` 为负，则连续播放频率，直到阻塞或者被中断，或者在后台呼叫的情况下，设置或调用新频率stop（见下文）。

- `pin` pin=Pin.P6,默认是掌控板的P6引脚。可重定义其他引脚。

请注意，您一次只能在一个引脚上播放频率。

- `wait` 阻塞：如果 `wait` 设置为 `True`, 为阻塞,否则未不。

##### `stop()`

类型：API。

停止给定引脚上的所有音乐播放。

##### `reset()`

类型：API。

以下列方式重置以下属性的状态

* `ticks = 4`
* `bpm = 120`
* `duration = 4`
* `octave = 4`

#### 内置旋律

出于教育和娱乐的目的，该模块包含几个以Python列表表示的示例曲调。它们可以像这样使用：

>>> import music
>>> music.play(music.NYAN)

所有音乐都不受版权保护，由Nicholas H.Tollervey撰写并发布到公共领域或者有一位不知名的作曲家，并受到公平（教育）使用条款的保护。

它们是:

* `DADADADUM` - 贝多芬第五交响曲C小调开幕式。
* `ENTERTAINER` - 斯科特乔普林的Ragtime经典作品“The Entertainer”的开场片段。
* `PRELUDE` - JSBach的48首前奏曲和赋格曲的第一首C大调前奏曲的开篇。
* `ODE` - 贝多芬第七交响曲D小调的“欢乐颂”主题。
* `NYAN` - Nyan Cat主题 (http://www.nyan.cat/). 作曲家不详。
* `RINGTONE` - 听起来像手机铃声的东西。用于指示传入消息。
* `FUNK` - 为秘密特工和犯罪主谋提供的时髦低音系列。
* `BLUES` - 一个boogie-woogie 12杆蓝调步行低音。
* `BIRTHDAY` - “生日快乐" 版权状态见: http://www.bbc.co.uk/news/world-us-canada-34332853
* `WEDDING` - 来自瓦格纳歌剧“Lohengrin”的新娘合唱。.
* `FUNERAL` -  “葬礼进行曲”，也被称为FrédéricChopin的钢琴奏鸣曲第2号B-minor,Op 35。
* `PUNCHLINE` -一个有趣的片段表明一个笑话已经被创造出来了。
* `PYTHON` - John Philip Sousa的游行“Liberty Bell”又名“Monty Python's Flying Circus”的主题（之后以Python编程语言命名）。
* `BADDY` - 沉默的电影时代入口的一个坏人。
* `CHASE` - 无声电影时代的追逐场景。
* `BA_DING` - 表示发生了某些事情的短信号
* `WAWAWAWAA` - 一个非常悲伤的长号。
* `JUMP_UP` - 用于游戏，表示向上移动。
* `JUMP_DOWN` - 用于游戏，表示向下移动。
* `POWER_UP` - 一种炫耀，表明一项成就被释放。
* `POWER_DOWN` - 一种悲伤，表示一项成就已经失去。
* `GE_CHANG_ZU_GUO` - 歌唱祖国
* `DONG_FANG_HONG` - 东方红
* `CAI_YUN_ZHUI_YUE` - 彩云追月
* `ZOU_JIN_XIN_SHI_DAI` - 走进新时代
* `MO_LI_HUA` - 茉莉花
* `YI_MENG_SHAN_XIAO_DIAO` - 沂蒙山小调

示例::

"""

##### music.py

Plays a simple tune using the Micropython music module.
This example requires a speaker/buzzer/headphones connected to P0 and GND.
"""
from mpython import *
import music

# play Prelude in C.
notes = [
'c4:1', 'e', 'g', 'c5', 'e5', 'g4', 'c5', 'e5', 'c4', 'e', 'g', 'c5', 'e5', 'g4', 'c5', 'e5',
'c4', 'd', 'a', 'd5', 'f5', 'a4', 'd5', 'f5', 'c4', 'd', 'a', 'd5', 'f5', 'a4', 'd5', 'f5',
'b3', 'd4', 'g', 'd5', 'f5', 'g4', 'd5', 'f5', 'b3', 'd4', 'g', 'd5', 'f5', 'g4', 'd5', 'f5',
'c4', 'e', 'g', 'c5', 'e5', 'g4', 'c5', 'e5', 'c4', 'e', 'g', 'c5', 'e5', 'g4', 'c5', 'e5',
'c4', 'e', 'a', 'e5', 'a5', 'a4', 'e5', 'a5', 'c4', 'e', 'a', 'e5', 'a5', 'a4', 'e5', 'a5',
'c4', 'd', 'f#', 'a', 'd5', 'f#4', 'a', 'd5', 'c4', 'd', 'f#', 'a', 'd5', 'f#4', 'a', 'd5',
'b3', 'd4', 'g', 'd5', 'g5', 'g4', 'd5', 'g5', 'b3', 'd4', 'g', 'd5', 'g5', 'g4', 'd5', 'g5',
'b3', 'c4', 'e', 'g', 'c5', 'e4', 'g', 'c5', 'b3', 'c4', 'e', 'g', 'c5', 'e4', 'g', 'c5',
'a3', 'c4', 'e', 'g', 'c5', 'e4', 'g', 'c5', 'a3', 'c4', 'e', 'g', 'c5', 'e4', 'g', 'c5',
'd3', 'a', 'd4', 'f#', 'c5', 'd4', 'f#', 'c5', 'd3', 'a', 'd4', 'f#', 'c5', 'd4', 'f#', 'c5',
'g3', 'b', 'd4', 'g', 'b', 'd', 'g', 'b', 'g3', 'b3', 'd4', 'g', 'b', 'd', 'g', 'b'
]

music.play(notes)

## `urequests`：HTTP 客户端

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/urequests.html

#### `urequests` --- HTTP客户端的相关功能函数

之前我们用了 socket 库，这个作为入门的工具还是不错的，对了解一些爬虫的基本理念，掌握爬虫爬取的流程有所帮助。
入门之后，我们就需要学习一些更加高级的内容和工具来方便我们的爬取。
那么这一节来简单介绍一下 urequests 库的基本用法。

#### Response类

##### `Response(s)`

类型：API。

该Response类的对象，包含服务器对HTTP请求的响应。

- `s`-ussl对象

##### 方法

###### `close()`

类型：API。

关闭socket。

###### `content`

类型：属性。

返回响应的内容，以字节为单位。

###### `text`

类型：属性。

以文本方式返回响应的内容，编码为unicode。

###### `json()`

类型：API。

返回响应的json编码内容并转为dict类型。

#### 方法

##### `request(method, url, data=None, json=None, headers={},params=None,files=None)`

类型：API。

向服务器发送HTTP请求。

- `method` - 要使用的HTTP方法
- `url` - 要发送的URL
- `data` - 要附加到请求的正文。如果提供字典或元组列表，则将进行表单编码。
- `json` - json用于附加到请求的主体。
- `headers` - 要发送的标头字典。
- `params` - 附加到URL的URL参数。如果提供字典或元组列表，则将进行表单编码。
- `files` - 用于文件上传,类型为2元组,其中定义了文件名,文件路径和content类型。如下,{‘name’, (file directory,content-type)}

##### `head(url, **kw)`

类型：API。

发送HEAD请求,返回Response对象。

- `url` - Request对象的URL
- `**kw` - request方法的参数。

##### `get(url, **kw)`

类型：API。

发送GET请求,返回Response对象。

- `url` - Request对象的URL
- `**kw` - request方法的参数。

##### `post(url, **kw)`

类型：API。

发送POST请求,返回Response对象。

- `url` - Request对象的URL
- `**kw` - request方法的参数。

##### `put(url, **kw)`

类型：API。

发送PUT请求,返回Response对象。

- `url` - Request对象的URL
- `**kw` - request方法的参数。

##### `patch(url, **kw)`

类型：API。

送PATCH请求,返回Response对象。

- `url` - Request对象的URL
- `**kw` - request方法的参数。

##### `delete(url, **kw)`

类型：API。

发送DELETE请求。,返回Response对象。

- `url` - Request对象的URL
- `**kw` - request方法的参数。

> requests示例：官方页面引用 `/_static/examples/network/example_requests.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

## `umqtt.simple`：MQTT 客户端

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/umqtt.simple.html

### `umqtt.simple` --- 简单MQTT客户端功能函数

MQTT是一种基于发布 - 订阅的“轻量级”消息传递协议，用于在TCP / IP协议之上使用。
提供订阅/发布模式，更为简约、轻量，易于使用，针对受限环境（带宽低、网络延迟高、网络通信不稳定），可以简单概括为物联网打造。

> **Hint**
>

该模块来源于 `MicroPython-lib` : https://github.com/micropython/micropython-lib/tree/master/umqtt.simple

#### 构建对象

##### `MQTTClient(client_id, server, port=0, user=None, keepalive=0, ssl=False, ssl_params={})`

类型：API。

官方构造函数还接受名为 `password` 的可选凭据参数。本档案不把凭据参数写成“名称=具体值”的可复制形式，
避免 API 文档占位值被安全扫描误判为已保存密码；应用代码应在运行时从安全配置注入凭据，禁止写回 Skill。

- `client_id`
- `server`
- `port`
- `user`
- `password`
- `keepalive`
- `ssl`
- `ssl_params`

#### 方法

##### `MQTTClient.set_callback(f)`

类型：API。

- `f` - f(topic, msg) 为回调函数,第1参数为 `topic` 接收到的主题,第2参数为 `msg` 为该主题消息

为收到的订阅消息设置回调

##### `MQTTClient.set_last_will(topic, msg, retain=False, qos=0)`

类型：API。

`topic` 和 `msg` 为字节类型

设置MQTT“last will”消息。应该在 connect()之前调用。

##### `MQTTClient.connect( clean_session=True )`

类型：API。

连接到服务器。如果此连接使用存储在服务器上的持久会话，则返回True（如果使用clean_session = True参数，则返回False（默认值））。

##### `MQTTClient.disconnect()`

类型：API。

断开与服务器的连接，释放资源。

##### `MQTTClient.ping()`

类型：API。

Ping服务器（响应由wait_msg（）自动处理）

##### `MQTTClient.publish(topic, msg, retain=False, qos=0)`

类型：API。

`topic` 和 `msg` 为字节类型

发布消息

##### `MQTTClient.subscribe(topic, qos=0)`

类型：API。

`topic` 为字节类型

订阅主题

##### `MQTTClient.wait_msg()`

类型：API。

等待服务器消息。订阅消息将通过set_callback（）传递给回调集，任何其他消息都将在内部处理。

##### `MQTTClient.check_msg()`

类型：API。

检查服务器是否有待处理的消息。如果是，则以与wait_msg（）相同的方式处理，如果不是，则立即返回。

> **Attention**
>

* wait_msg()并且check_msg()是“主循环迭代”方法，阻塞和非阻塞版本。wait_msg()如果您没有任何其他前台任务要执行（即您的应用只响应订阅的MQTT消息），check_msg() 如果您也处理其他前台任务，则应定期在循环中调用它们 。
* 请注意，如果您只发布消息，则不需要调用wait_msg()/ check_msg()，也不要订阅消息。
* 发布和订阅都支持QoS 0和1。不支持QoS2以保持较小的代码大小。除ClientID外，目前只支持“clean session”参数进行连接。
* 与MQTT消息相关的所有数据均编码为字节。这包括消息内容和主题名称（即使MQTT规范指出主题名称是UTF-8编码的）。原因很简单：通过网络套接字接收的是二进制数据（字节）

## `radio`：ESP-NOW 无线广播

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/radio.html

#### `radio` --- radio 无线广播相关功能

radio 模块是基于 [ESP-NOW ](https://docs.espressif.com/projects/esp-idf/zh_CN/latest/esp32/api-reference/network/esp_now.html) 无连接 Wi-Fi 通信协议而实现无线广播功能,支持13 Channel,在相同的Channel内能接收到成员发出的广播消息,适合30米范围内的多板组网的通讯。

#### 函数

##### `radio.on()`

类型：API。

开启无线功能

##### `radio.off()`

类型：API。

关闭无线功能

##### `radio.config(channel)`

类型：API。

配置无线参数

- `channel` (int): 无线通道,范围1~13

##### `radio.receive()`

类型：API。

接收无线广播消息,消息以字符串形式返回。最大可接收250字节数据。如果没有接收到消息,则返回 `None` 。当 `receive` 内参数为 `True` ,即 `receive(True)` ,返回(msg,mac)的二元组。默认缺省 `receive(False)` ,即只返回msg。

##### `radio.receive_bytes()`

类型：API。

接收无线广播消息,消息以字节形式返回。其他同 `radio.receive()` 相同。

##### `radio.send()`

类型：API。

发送无线广播消息,发送数据类型为字符串。当发送成功后返回True,否则返回False。

##### `radio.send_bytes()`

类型：API。

发送无线广播消息,发送数据类型为字节。当发送成功后返回True,否则返回False。

> 无线广播示例：官方页面引用 `/_static/examples/radio/radio.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

## `sdcard`：SPI SD 卡

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/sdcard.html

### `sdcard` --- SD卡

安全数字或SD卡和微型microSD卡价格低廉，可为设备增加大量存储空间。MicroPython，只有1M的闪存来存储代码和数据。
如果你拥有更大的闪存空间,可以将micro SD卡通过SPI通讯方式连接到掌控板来扩展其存储空间。

#### SDCard类

##### `SDCard(spi, cs)`

类型：API。

创建SDCard对象,初始化SD卡。

首先,须确保SPI总线的引脚与micro SD卡物理连接正确。确保您的micro SD卡使用FAT或FAT32文件系统格式化。然后,用os.mount(),将SD卡虚拟新的FAT文件系统挂载到指定的目录中。
挂载完成后,你就可以使用Python 的文件操作(如打开,关闭,读取和写入)来访问文件。

- `spi` - machine.SPI对象
- `cs`  - SPI的CS控制引脚

> 示例-挂载SD卡：官方页面引用 `/_static/examples/file/sdcard.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

> 示例-列出所有文件：官方页面引用 `/_static/examples/file/print_directory.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

## `bluebit`：blue:bit 套件驱动

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/bluebit.html

### `bluebit` --- blue:bit驱动

`blue:bit` 模块提供bluebit套件的掌控板库。

#### NTC模块

##### `bluebit.Thermistor`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

##### `bluebit.NTC`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### LM35模块

##### `bluebit.LM35`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 四按键模块

##### `bluebit.joyButton`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 温湿度模块

##### `bluebit.SHT20`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 颜色模块

##### `bluebit.Color`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 数字光线模块

##### `bluebit.AmbientLight`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 超声波模块

##### `bluebit.Ultrasonic`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 4段数码管模块

##### `bluebit.SEGdisplay`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 8x8点阵模块

##### `Matrix(i2c=i2c)`

类型：API。

8x8点阵模块控制类

- `i2c` : I2C实例对象,默认i2c=i2c.

##### `Matrix.blink_rate(rate=None)`

类型：API。

设置像素点闪烁率

- `rate` : 闪烁间隔时间,单位秒.默认None,常亮.

##### `Matrix.brightness(brightness)`

类型：API。

设置像素点亮度

- `brightness` : 亮度级别,范围0~15.

##### `Matrix.fill(color)`

类型：API。

填充所有

-  `color` : 1亮;0灭

##### `Matrix.bitmap(bitmap)`

类型：API。

显示位图

-  `bitmap` : 8x8点阵数据

##### `Matrix.show()`

类型：API。

显示生效

除上述函数方法外,还继承 `FrameBuffer` 类 ,有关其他方法,如显示字符,绘制函数。详情可查阅 micropython framebuf模块 [FrameBuffer ](https://mpython.readthedocs.io/zh/master/library/micropython/framebuf.html) 类.

#### LCD1602模块

##### `bluebit.LCD1602`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### MIDI模块

##### `bluebit.MIDI`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### MP3模块

##### `bluebit.MP3`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 红外接收模块

##### `bluebit.IRRecv`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 红外发射模块

##### `bluebit.IRTrans`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 实验探究类

适用的模块有电压、电流、磁场、电导率、PH、光电门、气压、力传感器。

##### `bluebit.DelveBit`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### 编码电机模块

##### `bluebit.EncoderMotor`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

#### RFID模块

##### `bluebit.Scan_Rfid`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

##### `bluebit.Rfid`

官方页面公开此类名，但当前构建页未展开构造参数和成员；使用前应在目标固件 REPL 中核对。

## `parrot`：掌控扩展板

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/parrot.html

### `parrot` --- 掌控拓展板驱动

掌控拓展板parrot是mPython掌控板衍生的一款体积小巧、易于携带。支持电机驱动、语音播放、语音合成等功能的IO引脚扩展板,可扩展12路IO接口和2路I2C接口。
该库为掌控拓展板提供电机驱动,LED驱动等功能。

电机控制I2C通讯协议数据格式:

======== ======== =========== ===========
Type     Command   motor_no   speed(int)
控制电机  0x01      0x01/0x02  -100~100
======== ======== =========== ===========

*当 'speed' 为负值,反转；当为正值,正转。*

模块对象：`parrot`。官方页通过示例展示公开用法。

> 电机驱动示例：官方页面引用 `/_static/examples/mpython-shield/motor_simple.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

> NEC编码红外发码示例：官方页面引用 `/_static/examples/mpython-shield/ir_send.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

> NEC编码红外学习示例：官方页面引用 `/_static/examples/mpython-shield/ir_learn.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

## `ds18x20`：DS18B20 单总线温度

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/ds18x20.html

### `ds18x20` --- ds18b20温度传感器驱动

one wire总线是一种串行总线，仅使用一根电线进行通信（除了用于接地和电源的电线）。DS18B20温度传感器是一种非常流行的单线设备,具有体积小，硬件开销低，抗干扰能力强，精度高的特点。

- 独特的onewire(单总线)接口方式，DS18B20在与微处理器连接时仅需要一条口线即可实现微处理器与DS18B20的双向通讯。
- 测温范围 －55℃～+125℃，
- 支持多点组网功能，多个DS18B20可以并联在唯一的三线上，最多只能并联8个，实现多点测温，如果数量过多，会使供电电源电压过低，从而造成信号传输的不稳定。
- 工作电源: 3.0~5.5V/DC

#### DS18X20类

##### `DS18X20(onewire)`

类型：API。

构建DS18X20类。

- `onewire` - one wire实例对象

##### `DS18X20.scan()`

类型：API。

扫描单总线上的ds18b20设备,返回设备地址的列表。

##### `DS18X20.convert_temp()`

类型：API。

获取采样温度并进行温度单位转换。

##### `DS18X20.read_temp(rom)`

类型：API。

返回该设备的温度值。注意,在 `convert_temp()` 转换温度后,至少需要等待750毫秒,才能读取温度值。

- `rom` - 设备地址

> 示例-ds18b20：官方页面引用 `/_static/examples/onewire/ds18b20.py`；本包把可执行形态集中放在 `examples/usage.md`，不增加额外 `.py` 文件。

## `servo`：PWM 舵机

官方页面：https://mpython-esp32s3-doc.readthedocs.io/zh-cn/latest/5_api/library/mPython/servo.html

### `servo` --- 舵机驱动功能函数

#### Servo类

##### `Servo(pin, min_us=750, max_us=2250, actuation_range=180)`

类型：API。

构建Servo对象,默认使用SG90舵机。不同舵机脉冲宽度参数和角度范围会有所不一样,根据舵机型号自行设置。

> **Hint**
>

作为Servo控制引脚须为支持PWM(模拟输出)的引脚。掌控板支持PWM的引脚,详情可查阅 `掌控板接口引脚说明` 。

> **Attention**
>

* 你可以设置 `actuation_range` 来对应用给定的 `min_us` 和 `max_us` 观察到的实际运动范围值。
* 您也可以将脉冲宽度扩展到这些限制之上和之下伺服机构可能会停止，嗡嗡声，并在停止时吸收额外的电流。仔细测试，找出安全的最小值和最大值。
* 由于舵机PWM周期为20ms,即响应时间为20ms。在编程时须注意两次写舵机角度间隔时间应至少大于20ms。

- `pin` -舵机PWM控制信号引脚
- `min_us` -舵机PWM信号脉宽最小宽度,单位微秒。默认min_us=750
- `max_us` -舵机PWM信号脉宽最大宽度,单位微秒。默认max_us=2250
- `actuation_range` -舵机转动最大角度

##### `Servo.write_us(width)`

类型：API。

发送设置脉冲宽度的PWM信号。

- `width` -脉冲宽度,单位微秒。

##### `Servo.write_angle(angle)`

类型：API。

写舵机角度

- `angle` -舵机角度。

from mpython import *
from servo import Servo                 #导入舵机模块

s=Servo(0)

while True:
for i in range(0,180,1):
s.write_angle(i)
sleep_ms(50)
for i in range(180,0,-1):
s.write_angle(i)
sleep_ms(50)
