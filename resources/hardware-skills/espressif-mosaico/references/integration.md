# 连接与编程

默认由掌问已配置的API生成待接受Lua，不要求配置板载模型。选择Mosaico并保存项目后，在「连接设备」填入设备显示的局域网IPv4 HTTP地址，保留原端口；无端口默认80，不固定加18789。电脑和设备处于同一局域网。

日常：生成代码 → 点击顶部「保存代码」/文件栏保存图标接受保存 → 「上传并运行」。备份、摘要冲突检查与回读保持，失败停止，结果未知不自动重发。首次WiFi运行服务只在需要时提示，安装清单与重启分别确认。默认运行上限30秒，详细结果/时限/单独上传/实际观察在「⋯ 代码工具」中。

顶部「设备设置」打开状态、网络、设备模型、ASR、IM、搜索、记忆、日志、能力、Lua模块、文件弹窗。仅手动切换到设备原生Claw聊天时才使用设备自己的模型配置；掌问API不自动复制给设备。密钥不进入项目/模型上下文；文件备份、回读、互斥和未知不重发沿用既有实现。断开连接不会停止板上的任务，设备重启另行确认。

<!-- zhangwen:lua-reference:v2 -->
# 掌问模型生成Lua与WiFi运行（2026-10-30）
用户已升级最新Claw，默认使用掌问API生成待接受Lua。审阅接受保存、单文件清单上传及回读后，通过WiFi显式点击运行。无需USB或板载模型API。
首次安装掌问固定Lua HTTP运行服务和一条启动规则：预览两份文件、原Artifact备份、摘要冲突检查及回读；另行显式重启后启用。模型不能修改运行服务、路由规则、启动项或凭据，也不获得运行接口或工具。
依据 espressif/esp-claw@519bd95900d29bfc9daf3619ff779753e3153f05。最新Lua运行能力接收绝对路径，HTTP文件管理仍使用DATA相对路径 /scripts/temp/*.lua；由固定运行服务解析绝对路径。生成代码只关心自己的Lua逻辑，不写命令或调用运行服务。用户代码时限5/10/30/60秒；提交、设备状态/原始输出与实物观察分开记录。未知不重发，设备boot_id改变不继续查询旧任务。
当前设备只读确认具备http_server、capability、json、storage以及下列常用模块；模块启用状态和具体板级外设仍需按实物核对。优先print最小测试，循环有界，使用delay.delay_ms；资源退出时清理。屏幕中文字体和新驱动签名以以下当前版本资料为准，不沿用旧资料或臆造接口。不要生成原生C/C++应用或MicroPython。

# Lua Board Manager

`board_manager` provides board metadata and camera paths.

## API

- `board_manager.get_board_info()` returns `{ name, chip, version, description, manufacturer }`.
- `board_manager.get_camera_paths()` returns `{ dev_path, meta_path }`; `meta_path` may be absent.

Both functions take no arguments and return `nil, err` when the requested information is unavailable. Missing board metadata fields are returned as empty strings.

`get_camera_paths()` queries the board camera only. The camera must already be initialized by the firmware; this call does not initialize it. Unsupported or uninitialized cameras return `nil, err`. Use `camera.list_devices()` to discover available capture devices, including external cameras.

This module only reads information. Use `display`, `lvgl`, `audio`, `camera`, or the appropriate sensor module to access hardware.

## Example

```lua
local board_manager = require("board_manager")

local info = assert(board_manager.get_board_info())
print(info.name, info.chip, info.version)

local paths, err = board_manager.get_camera_paths()
if paths then
    print(paths.dev_path)
else
    print(err)
end
```


# Lua Delay

This module describes how to correctly use delay when writing Lua scripts.

## How to call
- Import it with `local delay = require("delay")`
- Call `delay.delay_ms(ms)` to sleep for a number of milliseconds
- Call `delay.delay_us(us)` for short microsecond delays
- Call `delay.periodic(period_ms)` to create a waiter that follows a fixed interval
- **`ms` must be an integer**
- **`us` must be an integer**
- Negative `ms` and `us` values are accepted but clamped to `0`
- `period_ms` must be a positive integer and at least one scheduler tick
- `delay_us(us)` is a busy-wait intended for short hardware timing only
- `delay_us(us)` accepts `0..1000000`; use `delay_ms(ms)` for longer waits
- `periodic:wait()` returns `true` when the call waited, or `false` when the deadline was already missed
- `periodic:reset()` starts the schedule again from the current tick

## Example
```lua
local delay = require("delay")
delay.delay_ms(500)
delay.delay_us(200)

local ticker = delay.periodic(30)
for _ = 1, 10 do
    -- periodic work
    ticker:wait()
end

ticker:reset()
```


# `display` Lua API

`display` is an immediate-mode 2D drawing API for the device's built-in screen. Use it to render games, dashboards, camera overlays, and custom interfaces. It does not provide widgets or an external-screen API. One Lua job owns the screen at a time, and the returned screen must only be used by the Lua job that opened it.

Signatures below use `->` to show return values. Functions without `->` return no values.

## Quick start

```lua
local display = require("display")
local screen <close> = display.open()
local info = screen:info()
local panel_color = display.color(20, 90, 130)

screen:begin({ clear = "#101820" })
screen:fill_round_rect(12, 12, info.width - 24, 60, 8, panel_color)
screen:text(24, 30, "hello", { font_size = 24, color = 0xFFFFFFFF })
screen:present()
```

The drawing sequence is always `begin()` → draw → `present()`. The screen is released by `screen:close()`, Lua's `<close>` scope, or job exit. During a running job, dropping the Lua variable alone does not release it. Keep the screen open while its scene should remain visible.

## Open and screen information

`display.open([options]) -> screen` opens the built-in screen. Calling it again before the current screen closes raises `display already open`.

| Option | Default | Meaning |
| --- | --- | --- |
| `framebuffer_count` | `1` | `1` or `2`; use `2` only when the extra memory is justified by the scene |

The drawing format follows the built-in screen's color depth. No panel byte-order configuration is needed.

`screen:info()` returns:

| Field | Meaning |
| --- | --- |
| `width`, `height` | Screen dimensions in pixels |
| `pixel_format` | Active drawing format: `"rgb565"` or `"rgb888"` |
| `bytes_per_pixel` | `2` for RGB565 or `3` for RGB888 |
| `framebuffer_count` | Active framebuffer count |
| `framebuffer_bytes` | Total bytes reserved by all framebuffers |
| `touch_available` | Whether the built-in screen has touch input |

Cache this table if it is needed every frame.

`screen:stats()` returns the latest frame statistics:

| Field | Meaning |
| --- | --- |
| `draw_us` | Time from the start of `begin()` until `present()` begins, including framebuffer synchronization, clearing, Lua scene work, and drawing |
| `present_us` | Time spent submitting pixels and waiting for presentation |
| `sync_us` | Portion of `draw_us` spent synchronizing two framebuffers |
| `dirty_pixels` | Number of submitted pixels |
| `dirty_rects` | Number of submitted rectangles |
| `submitted_bytes` | Submitted pixel bytes before panel byte-order conversion |
| `framebuffer_bytes` | Total memory reserved by all framebuffers |

A frame with no update reports zero presentation time, rectangles, pixels, and submitted bytes.

`screen:close()` is safe to call more than once. Other screen methods raise an error after close.

## Frames and drawing state

```lua
screen:begin({ clear = 0xFF0C1520 })
screen:save()
screen:translate(20, 40)
screen:clip(0, 0, 120, 80)
screen:fill_rect(0, 0, 120, 80, 0xCC183047)
screen:restore()
local updated = screen:present()
```

- `screen:begin([{ clear = color }])` starts a frame. Omit `clear` to preserve the previous image; the first drawn frame starts from black. Starting another frame before presenting the current one is an error.
- `screen:present([{ full = false }]) -> boolean` finishes the frame and returns `true` if pixels were submitted. A frame with no changes normally returns `false`; `full = true` requests a full-screen refresh. If presentation fails, the frame remains active so it can be retried or the screen can be closed.
- `screen:save()` / `screen:restore()` save and restore translation and clipping. The stack holds at most eight saved states; restoring without a matching save is an error.
- `screen:translate(dx, dy)` adds an integer offset to subsequent drawing coordinates. `screen:clip(x, y, w, h)` intersects the current clip with a rectangle in the translated coordinate space. A negative clip width or height is an error; zero creates an empty clip. Drawing state resets at each `begin()`.

Drawing, translation, clipping, save, and restore require an active frame. `info()`, `stats()`, `measure_text()`, and `touch()` do not.

## Colors and shapes

Every shape method accepts a `color` in one of these forms:

- A packed `0xAARRGGBB` integer. On devices with 32-bit Lua integers, values with the high bit set may appear negative but retain the same color bits.
- `"#rrggbb"` or `"#rrggbbaa"`.
- `{ r = 255, g = 80, b = 40, a = 192 }` or `{ 255, 80, 40, 192 }`; omitted alpha defaults to 255.

`display.color(r, g, b[, a]) -> integer` packs components in `0..255` into a reusable color; `a` defaults to 255. Alpha 0 draws nothing, alpha 255 is opaque, and intermediate alpha values blend over the current image. A packed literal must include its alpha byte: use `0xFFFF0000` for opaque red, not `0xFF0000`. Six-digit color strings such as `"#ff0000"` are opaque.

Positions, dimensions, and radii are integers. The origin is at the top left, x grows rightward, and y grows downward. Drawing is clipped to the screen and current clip.

```lua
screen:fill_rect(x, y, w, h, color)
screen:stroke_rect(x, y, w, h, color)
screen:line(x0, y0, x1, y1, color)
screen:fill_circle(cx, cy, radius, color)
screen:stroke_circle(cx, cy, radius, color)
screen:arc(cx, cy, radius, start_deg, end_deg, color)
screen:fill_round_rect(x, y, w, h, radius, color)
screen:stroke_round_rect(x, y, w, h, radius, color)
screen:fill_triangle(x1, y1, x2, y2, x3, y3, color)
```

Arc angles are finite numbers and increase clockwise in screen coordinates.
Outlines are one pixel wide. Non-positive rectangle dimensions and negative radii draw nothing. For arcs, a sweep of at least 360 degrees draws a full circle, equal start and end angles draw nothing, and a negative difference wraps clockwise through 360 degrees.

## Text and fonts

```lua
local w, h = screen:measure_text("status", { font_size = 24 })
screen:text(8, 8, "status", { font_size = 24, color = "#ffffff" })

local font <close> = display.load_font(font_path)
screen:text(8, 40, "Temperature", { font = font, color = "#ffffff" })
```

`screen:text(x, y, text[, options])` draws a valid UTF-8 string inside an active frame. `screen:measure_text(text[, options]) -> width, height` uses the same sizing rules and can be called outside a frame. Both accept `color` (default white), `font_size` (default 24), and `font`.

Without `font`, the built-in font supports printable ASCII at integer sizes 8–64. Text is not automatically wrapped or aligned: `\n` starts a new line, `\r` returns to the start of the current line, and `\t` advances by four glyph widths. An empty string measures `0, 0`.

For other Unicode characters, load a readable DFN1 bitmap font with `display.load_font(path) -> font`. DFN1 preserves each glyph's advance, bounding box, baseline offset, and Unicode encoding. A custom font is rendered at its stored size, so `font_size` is ignored when `font` is present. A missing glyph uses the font's configured fallback glyph if available; otherwise drawing and measurement raise an error. Invalid UTF-8 also raises an error. `font:close()` is idempotent; a closed font cannot be used. Close the font only after its final synchronous `text()` or `measure_text()` call.

The built-in `bdf_font_converter` skill converts horizontal Unicode BDF 2.1/2.2 files from writable storage into DFN1 on the device. The format limits the line height, glyph width, glyph height, and horizontal advance to 64 pixels, with at most 4096 glyphs and a 1 MiB file size.

## Images and raw pixels

```lua
local image = require("image")
local frame <close> = image.load_file(image_path)
local red_tile = string.rep("\0\248", 64 * 64)
screen:begin()
screen:image(0, 0, frame, { mode = "contain", width = 120, height = 90, opacity = 220 })
screen:blit(130, 0, red_tile, { width = 64, height = 64, format = "rgb565" })
screen:present()
```

`screen:image(x, y, image_frame[, options])` accepts an `image.frame` from the `image` module. The frame must remain valid during the call. The image is drawn synchronously; it is not retained by `display`.

| `mode` | Result |
| --- | --- |
| `"raw"` (default) | Draw the selected source region at its natural size; ignore target `width` and `height` |
| `"contain"` | Fit inside the target box without distortion, centered |
| `"cover"` | Fill the target box without distortion, cropping from the center |
| `"stretch"` | Fill the target box, allowing distortion |
| `"crop"` | Draw from the source region's top left without scaling, limited by the target size |

Image options also include `source = { x = 0, y = 0, width = 32, height = 24 }` to select a source region, and `opacity` in `0..255` (default 255). Source coordinates must be inside the image and the selected region must fit. Omitted source dimensions extend to the source image's edge. For non-`raw` modes, omitted or zero target dimensions default to the selected source dimensions. Opacity 0 draws nothing.

The target box is not cleared automatically. For example, `contain` leaves any uncovered part of the box unchanged.

`screen:blit(x, y, bytes, options)` draws a Lua string of raw pixels. `options` must specify positive integer `width` and `height`, plus `format`: `"rgb565"` (little-endian pixels), `"rgb888"` (RGB byte order), or `"bgr888"` (BGR byte order). The string length must equal `width * height * bytes_per_pixel` exactly. `blit()` does not scale or apply opacity; use `image()` for those operations. Raw pointers are not accepted.

Both `image()` and `blit()` obey the current translation and clip. Their coordinates identify the destination's top-left corner.

## Touch and errors

`screen:touch() -> { points = { { id = number, x = number, y = number }, ... } }` returns the latest touch snapshot in screen coordinates. `points` contains every active touch point in provider order and is empty when nothing is touching the screen. Track a gesture with `id`; do not assume the array position remains stable. On a board without built-in touch, the call raises a not-supported error; check `screen:info().touch_available` first.

Invalid arguments, invalid UTF-8, invalid frame state, a closed screen or font, and unavailable hardware raise Lua errors. Use `pcall` when a scene should recover from an expected failure.

For animation, load images and fonts once, reuse prepared colors and pixel strings, and submit each frame with one `begin()` / `present()` pair.


# Lua Button

This module describes how to correctly use button when writing Lua scripts.

## How to call
- Import it with `local button = require("button")`
- Call `local handle = button.new(gpio_num [, active_level [, long_press_ms [, short_press_ms]]])` to create a button handle
- Call `button.on(handle, event, callback)` to subscribe to a button event
- Supported event names include `press_down`, `press_up`, `press_repeat`, `press_repeat_done`, `single_click`, `double_click`, `multiple_click`, `long_press_start`, `long_press_hold`, `long_press_up`, and `press_end`
- Call `button.off(handle [, event])` to remove a subscription or clear callbacks
- Call `button.dispatch()` to poll and dispatch pending button events
- Call `button.get_key_level(handle)` to read the current key level
- Call `button.close(handle)` when the handle is no longer needed

## Return values and events
- `button.new(...)` returns a handle or `nil, err`.
- `button.close(handle)`, `button.on(handle, event, callback)`, and `button.off(handle[, event])` return `true` or `nil, err`.
- `button.dispatch()` returns the number of dispatched callback events.
- Callback events are tables with `handle`, `event`, `repeat_count`, and `pressed_time_ms`.

## Example
```lua
local button = require("button")

local handle = button.new(0, 0)
button.on(handle, "single_click", function(evt)
  print(evt.event, evt.repeat_count)
end)

button.dispatch()
button.close(handle)
```


# Lua GPIO

This module describes how to correctly use gpio when writing Lua scripts.

## How to call
- Import it with `local gpio = require("gpio")`
- Call `gpio.set_direction(pin, mode)` to set pin mode
- Call `gpio.set_level(pin, level)` to set output level
- Call `gpio.get_level(pin)` to read pin level
- Call `gpio.close(pin)` to reset and release the pin; repeated close is safe

Supported modes are `"input"`, `"output"`, `"input_output"`, `"output_od"`, `"input_output_od"`, and `"disable"`.

`set_direction` and `set_level` return no values on success and raise a Lua error on failure. `get_level` returns `0` or `1`.

A pin cannot be used while another device or script owns it. Call `gpio.close(pin)` to release it; otherwise it remains in use until the job exits. Garbage collection alone does not release pins. Retry a failed close before reusing the pin.

The example uses GPIO4. Check that it is available and output-capable on your board.

## Example
```lua
local gpio = require("gpio")
gpio.set_direction(4, "output")
gpio.set_level(4, 1)
gpio.close(4)
```


<!-- zhangwen:mosaico-lua-peripherals:v1 -->
## 板载传感器与多媒体Lua补充（2026-10-31）

来源固定为esp-claw@519bd959；这是API依据，不是当前设备每个模块或板级注册名称的实测。此前已读取到的Mosaico模块列表包含imu/magnetometer/audio/camera/image/lvgl/system/vision等；列表说明编译模块，不证明某传感器已经初始化。BQ27220硬件存在，但该列表未列fuel_gauge，不能保证`lib_fuel_gauge`可require。

<!-- zhangwen:lua-confirmed-api:v1 -->
### 已核对接口速查（2026-11-01）

BMI270的Lua模块名及读数方法已经核对，并非未知：

```lua
local imu = require("imu")
local sensor = imu.new({ device = "imu_sensor" })
local sample = sensor:read()
print(sample.accel.x, sample.accel.y, sample.accel.z,
      sample.gyro.x, sample.gyro.y, sample.gyro.z)
sensor:close()
```

`require("imu")`、`imu.new`、对象`:read()`/`:close()`和`accel/gyro.x/y/z`来自已核对的Claw Lua接口。板载BMI270无需外接、无需用户再查require名。读数为原始计数，不直接是g或°/s。`imu_sensor`是上游板级注册名示例，当前设备是否采用此名、是否空闲仍待运行核实；不能把这个局部未知扩大成“Lua模块名/读数接口未知”或“没有IMU Lua接口”。

倾斜移动可用原始计数相对变化与限幅，不需要先取得校准后的角度。未提供当前设备错误时，可以给使用上游示例注册名的待验证候选：用pcall保护require、打开和采样，50ms×100帧有界循环，异常路径同样释放已打开的IMU与屏幕；说明注册名采用示例，运行失败返回原始错误。不能无依据换成触摸或静态方框并声称已完成IMU需求。用户明确改用触摸、暂停IMU或提供实际报错时，按用户要求与错误处理。
<!-- /zhangwen:lua-confirmed-api:v1 -->

### BMI270板载IMU

- 模块：`local imu = require("imu")`；优先`imu.new({device="imu_sensor"})`这种板级模式。`imu_sensor`是上游示例注册名，不是所有固件的保证；若实际报设备不存在，核对当前固件注册名，不改接线、不否认板载BMI270、不随意重新初始化I2C。
- `sensor:read()`返回`accel={x,y,z}`、`gyro={x,y,z}`、`sens_time`、`status`；`sensor:read_temperature()`是芯片原始温度；`sensor:read_int_status()`为中断位，读取可能清状态；`sensor:name()`返回名称。
- `accel`/`gyro`是芯片原始计数，**不是g、m/s²或°/s**。BMI270 sens_time是传感器计数器。板级对象保留既有采样配置；没有确认量程就不能除以固定8192/2048等系数。
- 原生BSP默认100Hz、±4g、±2000°/s，`bsp_imu_get_accel()`已按量程转g、`bsp_imu_get_gyro()`转°/s；这不能套到Lua read原始值。上游Lua BMI270外接后端默认±16g，与BSP不同。
- 板级设备一次只允许一个Lua句柄，关闭释放Lua占用但保留板级传感器；外接模式才用`imu.new({chip="bmi270",bus=bus,address=0x69})`，总线和地址必须空闲，不能与板级device混用。Mosaico内置器件优先板级模式，禁止抢占已有驱动。
- 同步读取/参数错误抛Lua异常，可用`pcall`；有界采样循环用`delay.delay_ms()`，正常和异常路径都close。不能编造`imu.init()`/`imu.read()`全局函数或`get_roll()`/`get_pitch()`。

### 板载IMU最小采样（约5秒，待用户接受后运行）

```lua
-- Mosaico板载BMI270原始采样；无需外接IMU。设备名采用上游示例，按固件报错核对。
local imu = require("imu")
local delay = require("delay")
local opened, sensor = pcall(imu.new, { device = "imu_sensor" })
if not opened then
  print("板载IMU打开失败，请核对固件设备注册名/占用：", sensor)
  return
end
local ok, err = pcall(function()
  for i = 1, 100 do
    local v = sensor:read()
    print("raw", v.accel.x, v.accel.y, v.accel.z,
          v.gyro.x, v.gyro.y, v.gyro.z)
    delay.delay_ms(50)
  end
end)
sensor:close()
if not ok then error(err) end
```

这段是API核对后的参考，未声称实板成功。先看静置和移动时原始轴是否变化，再做屏幕小球或阈值。可使用静置基线的方向/相对变化设计演示，明确其不是校准后的姿态角。六轴IMU不能单独提供无漂移绝对航向；陀螺积分和加速度倾角有运动/偏置限制。

### 两颗BMM150磁力计

- `local magnetometer=require("magnetometer")`；`magnetometer.new({device="magnetometer_sensor"})`是上游板级名称示例，Mosaico两颗器件需实际固件各自名称。不要凭BSP索引拼接不存在的Lua设备名。
- `sensor:read()`返回`magnetic={x,y,z}`、`raw_magnetic`、`status`、`calibrated`。BMM150的磁场单位是µT，raw_magnetic指应用校准前（已有工厂补偿）；不能把它当未补偿寄存器值或直接当角度。无自动航向/倾斜补偿；BMM150没有该模块的摄氏温度读取功能。
- `sensor:chip_id()`/`:name()`/`:read_int_status()`/`:close()`；板级与外接模式互斥。外接模式`{chip="bmm150",bus=bus,address=0x11}`仅在资源空闲时使用，不同时从其他驱动访问。
- `calibration_reset()` → 移动方向并多次`calibration_add_sample()` → `calibration_finish()`（至少16个样本且各轴跨度非零）；`calibration_get()`/`calibration_set({hard_iron={...},soft_iron={{...},{...},{...}}})`；结果只保留当前Lua对象，不自动持久化。磁铁/外壳/安装改变需重校准；磁吸边缘识别不是指南针角度。

### 已初始化板内I²C、电量计

`local i2c=require("i2c")`，`i2c.borrow(port)`仅借用已初始化的固件总线，不改变GPIO；`bus:scan()`返回ACK的7位地址。关闭借用句柄不会关闭板总线；器件先close再关bus。`i2c.new(port,sda,scl[,freq_hz])`只用于空闲控制器和引脚，已占用地址不能重复attach，优先器件专用板级API。

固件确有对应Lua库且0x55空闲时，`local fuel_gauge=require("lib_fuel_gauge")`，`fuel_gauge.new({borrow=true,port=0,chip="bq27220"})`，`:read()`返回`voltage_mv/current_ma/soc`，`:read_voltage_mv()`/`:read_current_ma()`/`:read_soc()`，`:close()`。不要把require名写成fuel_gauge，不重写校准/电池配置，不承诺模块列表未提供的库必然可用。板内端口随固件/板型核实。

### 显示触摸与LVGL

原有`display`章节为完整即时绘图API。自定义动画优先`display.open()`→`screen:info()`→有界循环`begin`/绘制/`present`，结束close；中文需已存在的DFN1字体，不假定内置ASCII字体含中文。触摸先查touch_available，再`screen:touch().points`。

`lvgl`与display共享屏幕，应选择一种并遵循占用/关闭要求，不能照抄原生`bsp_display_start()`或原生LVGL C调用。完整LVGL控件签名以本节后的上游Lua文档为准。

下方上游最小例子的`lvgl.run()`是持续事件循环；当前掌问有时限任务应改用有界次数的`lvgl.process_events(50)`，循环总时长留出初始化与`lvgl.deinit()`清理时间，不直接照抄无限运行例子。

### ES8311音频

`local audio=require("audio")`；`audio.open_output()`/`audio.open_input([{sample_rate=...,channels=...,bits=...}])`返回对象或nil,err；`:info()`核对真实PCM格式。输出`:set_volume(0..100)`、`:write(pcm)`、`:play_tone(freq_hz,duration_ms)`、`:close()`。播放音调频率低于采样率一半，16/32位输出支持。`:set_mute()`当前不改变声音，用volume0；输入set_volume当前不改变实际录音增益。

`audio.player({output=output})`→`:play(path_or_uri[,opts])`、`:poll()`、`:stop()`/`:pause()`/`:resume()`/`:close()`。输入`:read(bytes)`/`:read({bytes=...})`，按返回格式对齐PCM帧。先关player/recorder/analyzer再关设备；一次最多一个输入、一个输出。音频回环先低音量并控制时长，不能把BSP的ESP-SR模型或GMF管线名字当成已有Lua函数。

### 摄像头、图像、视觉

摄像头为左槽可选模块，先`camera.list_devices()`读当前可用path（或`board_manager.get_camera_paths()`读取已初始化路径），不要硬编码其他板/dev/video0。`camera.open(path,{width=...,height=...,format={"JPEG","RGBP"},nearest=true})`后查`camera.info()`实际宽高/FOURCC；模块支持与具体传感器格式分别判断。`camera.get_frame(timeout_ms)`返回image.frame；每帧用局部`<close>`或`:release()`及时释放，释放全部帧和view后才`camera.close()`。`:list_formats()`、`:flush()`、`:set_vflip(bool)`/`:set_hmirror(bool)`依当前设备支持。

`local image=require("image")`，`image.convert(frame,image.RGB565/GRAY8/JPEG/...)`、`image.resize(frame,{width=...,height=...,filter="nearest"或"bilinear"})`、`image.load_file(path)`、`image.save_file(path,frame)`。frame`:info()`/`:data()`/`:release()`；data会复制，避免每帧滥用。存储路径用`storage.get_root_dir()`与`storage.join_path()`，不猜/nand固定路径，不格式化/覆盖固件资源。

视觉文档对应具体require名：`motion_detect`、`color_detect`、`qrcode_detect`、`espdet`，不是统一`vision.detect()`。motion.new(opts)→detector:detect(frame)，首帧ready=false；color_detect.detect(frame,opts)返回detected/cx/cy/box等；qrcode_detect.detect(frame,opts)返回数组及count。espdet需固件启用且已有适配.espdl模型与正确帧格式；不能把原生human_face_detect/COCO示例直接等同于Lua已装模型。

### 系统信息

`local system=require("system")`，`system.millis()`/`uptime()`/`time()`/`date([format])`/`ip()`/`info()`，可查内存、时间与STA地址；不要把`system.info()`或模块枚举当作板载传感器设备名称列表。board_manager仅公开get_board_info/get_camera_paths，没有文档化的list_sensors/get_imu接口。

### 原生BSP API对照（仅解释参考，不能写入Lua代码）

- 入口`#include "bsp/esp_mosaico.h"`；`bsp_board_variant_get()`检查板型、`bsp_power_init()`电源；检查esp_err_t，不重复接管共享控制器。
- IMU：`bsp_imu_init()`→`bsp_imu_start(&config)`→`bsp_imu_get_accel(&x,&y,&z)`/`bsp_imu_get_gyro(...)`→stop/deinit。BSP单位g、°/s，默认量程见上。
- 磁力计：`bsp_magnetometer_init_all()`/`bsp_magnetometer_init(id)`→`bsp_magnetometer_read(id,&data)`，id为BSP_MAGNETOMETER_0/1，对应0x11/0x12，不是Lua设备名。
- HMI：`bsp_display_start()`，非LVGL任务创建/修改对象须`bsp_display_lock()`/unlock。
- 电池：`bsp_battery_init()`/read/read_basic/deinit；init可应用默认RAM配置，不等于纯读取，Lua普通程序不自行重配电池。
- 电源：`bsp_power_prepare_sleep()`/`bsp_power_enter_deep_sleep()`需预先配置唤醒源；GPIO61不是RTC IO，不能EXT1深睡唤醒。普通WiFi项目不随意关机/睡眠。
- 扩展模块：管理器init→发现PRESENT+VALID+类型匹配+FREE→claim→创建驱动→使用→删除驱动→release；清理失败保留lease，避免重开。Camera/Joystick/Interaction驱动自动管理槽位；Relay/Matrix由应用显式claim。所有这些原生API不表示Claw已提供同名Lua模块。


### 上游Lua LVGL API（固定提交，以下为只读编程资料）

# Lua LVGL Usage Guide

This document is an API guide for building LVGL UIs from Lua with the `lvgl` module.

## Core Rules

- Import the module with `local lvgl = require("lvgl")`.
- Call `lvgl.init([opts])` before creating screens or widgets.
- All widget operations are userdata methods. Use `btn:set_text("OK")`, not `lvgl.set_text(btn, "OK")`.
- Only one Lua script can own the LVGL runtime at a time. Do not use `display.open(...)` and `lvgl.init(...)` together.
- Call `lvgl.deinit()` before the script exits. The module also cleans up automatically if the owner script exits unexpectedly.
- Object handles become invalid after `obj:delete()`, after a parent object is deleted, or after `lvgl.deinit()`.
- After registering events, call `lvgl.run()` or repeatedly call `lvgl.process_events(...)`; otherwise Lua callbacks will not run.

## Minimal Example

```lua
local lvgl = require("lvgl")

lvgl.init({
    buffer_lines = 40,
    tick_ms = 5,
    task_period_ms = 10,
})

local scr = lvgl.create_screen()
scr:set_style({ bg_color = "#101820" })

local label = lvgl.label(scr, {
    text = "LVGL from Lua",
    align = "top_mid",
    y = 20,
    text_color = "#ffffff",
})

local btn = lvgl.button(scr, {
    text = "OK",
    align = "center",
    w = 120,
    h = 44,
    bg_color = "#2f80ed",
    text_color = "#ffffff",
})

btn:on("clicked", function()
    label:set_text("clicked")
end)

scr:load()
lvgl.run()
lvgl.deinit()
```

## Init And Deinit

```text
lvgl.init([opts]) -> true
```

Common `opts`:
- `buffer_lines`: draw buffer height in lines, default `40`
- `tick_ms`: LVGL tick period, default `5`
- `task_period_ms`: LVGL handler task period, default `10`

Legacy scripts may still call `lvgl.init(panel_handle, io_handle, width, height, panel_if, opts)`. The positional display parameters are ignored; only `opts` is used.

Legacy constants are still exported for older scripts:

- `lvgl.PANEL_IF_IO`
- `lvgl.PANEL_IF_RGB`
- `lvgl.PANEL_IF_MIPI_DSI`

They are not needed by `lvgl.init([opts])`.

Shutdown:

```text
lvgl.deinit() -> true
```

## Touch Input

The board's LCD touch device is connected automatically. After `lvgl.init(...)`, widgets receive touch events without registering an input handle.

## Event Loop

Register callbacks with `obj:on(event, callback)`:

```lua
local handle = btn:on("clicked", function()
    print("clicked")
end)
```

Remove callbacks:

```lua
btn:off(handle)      -- -> removed_count
btn:off("clicked")  -- -> removed_count
btn:off()           -- -> removed_count
```

Supported event names:

`clicked`, `pressed`, `released`, `long_pressed`, `value_changed`,
`focused`, `defocused`, `ready`, `cancel`

Drive the event loop:

```text
lvgl.run([{ period_ms = 200 }]) -> processed_count
```

Or:

```lua
while true do
    lvgl.process_events(50) -- -> processed_count
    -- run other periodic Lua-side work here
end
```

`lvgl.process_events([timeout_ms = 0])` treats negative timeouts as `0`. Event callbacks receive no arguments; callback errors are logged and event dispatch continues.

## Widget Constructors

All constructors follow the same basic shape:

```lua
local obj = lvgl.widget(parent, opts) -- -> object userdata
```

Basic widgets:

- `lvgl.object(parent, opts)`
- `lvgl.container(parent, opts)`
- `lvgl.label(parent, opts)`
- `lvgl.button(parent, { text = "OK" })`
- `lvgl.bar(parent, { min = 0, max = 100, value = 50 })`
- `lvgl.slider(parent, { min = 0, max = 100, value = 50 })`
- `lvgl.arc(parent, { min = 0, max = 100, value = 50 })`
- `lvgl.scale(parent, { min = 0, max = 100, value = 50 })`
- `lvgl.checkbox(parent, { text = "Enable", checked = true })`
- `lvgl.switch(parent, { checked = true })`
- `lvgl.dropdown(parent, { options = {"A", "B"}, selected = 1 })`
- `lvgl.roller(parent, { options = {"A", "B"}, selected = 1 })`
- `lvgl.keyboard(parent, { mode = "text_lower", textarea = textarea })`
- `lvgl.textarea(parent, { text = "..." })`
- `lvgl.list(parent, opts)`
- `lvgl.table(parent, { rows = 2, cols = 2 })`
- `lvgl.image(parent, { src = "<your/path/image.bin>" })`
- `lvgl.line(parent, { points = {{x=0,y=0}, {x=20,y=20}} })`
- `lvgl.spinner(parent, { anim_ms = 1000, arc_sweep = 60 })`
- `lvgl.buttonmatrix(parent, { map = {"1", "2", "\n", "3"}, one_checked = true })`
- `lvgl.calendar(parent, { today = {2026, 5, 15}, shown = {2026, 5}, highlighted = {{2026, 5, 15}} })`
- `lvgl.canvas(parent, { w = 80, h = 40, color_format = "rgb565" })`
- `lvgl.chart(parent, { type = "line", point_count = 10, min = 0, max = 100, update_mode = "shift" })`
- `lvgl.imagebutton(parent, { src = "<your/path/image.bin>" })`
- `lvgl.led(parent, { color = "#00ff00", brightness = 180, on = true })`
- `lvgl.menu(parent, opts)`
- `lvgl.msgbox(parent_or_nil, { title = "...", text = "...", buttons = {"OK"}, close_button = true })`
- `lvgl.spangroup(parent, { mode = "break", overflow = "ellipsis", spans = {"A", "B"} })`
- `lvgl.spinbox(parent, { min = 0, max = 100, value = 10, step = 1 })`
- `lvgl.tabview(parent, { tab_bar_position = "top", tab_bar_size = 36 })`
- `lvgl.tileview(parent, opts)`
- `lvgl.window(parent, opts)`
- `lvgl.eaf(parent, { src = "<your/path/anim.eaf>", loop_count = -1, loop_enabled = true })`

Lua index convention:
- dropdown/roller selected indexes are 1-based
- table rows and columns are 1-based
- buttonmatrix selected indexes are 1-based
- tabview active indexes are 1-based
- tileview `col` and `row` are 1-based

Widget-specific `opts`:

- `image`: `src`
- `line`: `points`, `y_invert`
- `arc`: `start_angle`, `end_angle`, `bg_start_angle`, `bg_end_angle`, `rotation`, `mode`
- `spinner`: `anim_ms`, `arc_sweep`
- `scale`: `mode`, `total_ticks`, `major_tick_every`, `label_show`, `angle_range`, `rotation`
- `checkbox`, `switch`: `checked`
- `dropdown`: `options`, `selected`, `dir`, `symbol`
- `roller`: `options`, `selected`, `mode`, `visible_rows`
- `keyboard`: `mode`, `popovers`, `textarea`
- `textarea`: `placeholder`, `one_line`, `password`, `max_length`, `accepted_chars`
- `table`: `rows`, `cols`, `cells`, `column_widths`
- `buttonmatrix`: `map`, `one_checked`
- `calendar`: `today`, `shown`, `highlighted`, `day_names`
- `canvas`: `w`, `h`, `color_format`
- `chart`: `type`, `point_count`, `min`, `max`, `update_mode`
- `imagebutton`: `src`
- `led`: `color`, `brightness`, `on`
- `msgbox`: `title`, `text`, `buttons`, `close_button`
- `spangroup`: `mode`, `overflow`, `indent`, `max_lines`, `spans`
- `spinbox`: `min`, `max`, `value`, `step`, `digit_count`, `dec_point_pos`, `rollover`
- `tabview`: `tab_bar_position`, `tab_bar_size`
- `eaf`: `src`, `src_data`, `loop_count`, `loop_enabled`, `frame_delay`

## Common Options

Most widgets support:

- Position and size: `x`, `y`, `w`, `h`, `align`
- Text: `text`
- Numeric values: `min`, `max`, `value`
- Style: `bg_color`, `text_color`, `border_color`, `bg_opa`, `opa`,
  `radius`, `border_width`, `pad`, `pad_row`, `pad_column`,
  `line_color`, `line_width`, `arc_width`, `font`

Colors can be strings or numbers:

```lua
bg_color = "#2f80ed"
text_color = 0xffffff
```

## Fonts

`lvgl.init()` does not load a font. Load a font explicitly, then apply it to individual controls or set it as the default:

```lua
local lvgl = require("lvgl")

local font = lvgl.font_load({ size = 24, cache_size = 128 })
lvgl.set_default_font(font)
label:set_style({ font = font })
```

- `lvgl.font_load([path][, { size = 16, cache_size = ... }])` -> font handle
- `lvgl.set_default_font(font | nil)` -> true; applies to the current root screen and subsequently created screens
- `font:set_size(px)` -> true
- `font:is_valid()` -> boolean
- `font:delete()` -> true

Without `path`, `lvgl.font_load()` uses `fonts/NotoSansSC-Regular-sub.ttf`. Passing `nil` to `lvgl.set_default_font()` restores the built-in font. An explicit `font` style on a control overrides the default font.

## EAF Animation

EAF playback is exposed as an LVGL object:

```lua
local anim = lvgl.eaf(scr, {
    src = "<your/path/idle.eaf>",
    align = "center",
    loop_count = -1,
    loop_enabled = true,
    frame_delay = 100,
})

if anim:is_loaded() then
    anim:pause()
    anim:resume()
end
```

Methods:
- `anim:set_src(path)`
- `anim:set_src_data(binary_string)`
- `anim:restart()`, `anim:pause()`, `anim:resume()`
- `anim:is_loaded()`
- `anim:get_total_frames()`, `anim:get_current_frame()`
- `anim:set_loop_count(n)`, `anim:get_loop_count()`
- `anim:set_loop_enabled(boolean)`, `anim:get_loop_enabled()`
- `anim:set_frame_delay(ms)`, `anim:get_frame_delay()`

Use either `src` or `src_data` when creating an EAF object.

## Common Methods

All LVGL object userdata supports:

- Methods that change object state return `true` on success unless another return value is shown.
- `obj:set_pos(x, y)`
- `obj:get_pos()` -> `x, y`
- `obj:set_size(w, h)`
- `obj:get_size()` -> `w, h`
- `obj:align(name[, x, y])`
- `obj:is_valid()` -> boolean
- `obj:set_style(opts)`
- `obj:set_flex(opts)`
- `obj:set_grid(opts)`
- `obj:set_grid_cell(opts)`
- `obj:set_scroll(opts)`
- `obj:on(event, callback)` -> handle
- `obj:off([handle_or_event])` -> removed_count
- `obj:delete()`
- `obj:clean()`

Screen helpers:
- `lvgl.screen()` -> active screen object
- `lvgl.create_screen()` -> screen object

Common `align` names:

`top_left`, `top_mid`, `top`, `top_right`, `bottom_left`, `bottom_mid`,
`bottom`, `bottom_right`, `left_mid`, `left`, `right_mid`, `right`,
`center`, `centre`, `default`

## Object Flags And Order

- `obj:add_flag(name)` / `obj:clear_flag(name)` -> true. Supported names: `CLICKABLE`, `PRESS_LOCK`, `SCROLLABLE`, `HIDDEN` (case-sensitive).
- `obj:move_foreground()` -> true. Moves the object above its siblings; screens have no parent and raise an error.

Use `PRESS_LOCK` on hold controls to keep receiving release events when a finger leaves the control. Clear `CLICKABLE` on decorative widgets so they do not intercept touches. `HIDDEN` disables drawing and hit testing without deleting the object. These methods raise errors for unsupported flags or invalid/deleted handles.

## Layout And Scrolling

Flex:

```lua
obj:set_flex({
    flow = "column",
    main = "start",
    cross = "center",
    track = "start",
})
```

`flow`: `row`, `column`, `row_wrap`, `row_reverse`, `row_wrap_reverse`,
`column_wrap`, `column_reverse`, `column_wrap_reverse`

`main/cross/track`: `start`, `center`, `end`, `space_between`,
`space_around`, `space_evenly`

Grid:

```lua
obj:set_grid({
    cols = {"fr", "fr"},
    rows = {"content", 40},
    col_align = "stretch",
    row_align = "start",
})
```

Grid cell:

```lua
obj:set_grid_cell({
    col = 1,
    row = 1,
    col_span = 1,
    row_span = 1,
    col_align = "stretch",
    row_align = "stretch",
})
```

Scroll:

```lua
obj:set_scroll({
    dir = "ver",
    scrollbar = "auto",
    snap_x = "none",
    snap_y = "none",
})
```

`dir`: `none`, `left`, `right`, `top`, `bottom`, `hor`, `ver`, `all`

`scrollbar`: `auto`, `off`, `on`, `active`

`snap_x/snap_y`: `none`, `start`, `end`, `center`

## Type-Specific Methods

Basic methods:

- `label/button/checkbox/dropdown/textarea/list_text/list_button:set_text(text)`
- `bar/slider/roller:set_value(v[, anim])`
- `arc/scale/dropdown/checkbox/switch/spinbox:set_value(v)`
- `bar/slider/arc/scale/dropdown/roller/checkbox/switch/spinbox:get_value()`
- `bar/slider/arc/scale/spinbox:set_range(min, max)`
- `screen:load()`
- `image:set_raw_rgb565(width, height, data[, opts])` -> true
- `image:set_raw_argb8888(width, height, data)` -> true
- `image:set_pivot(x, y)` -> true
- `image:set_rotation(angle)` -> true
- `line:set_points({{x=0,y=0}, {x=20,y=20}, ...})` -> true
- `list:add_text(text)` -> `list_text`
- `list:add_button(text[, symbol])` -> `list_button`
- `table:set_cell(row, col, text)`
- `table:get_cell(row, col)` -> string
- `buttonmatrix:set_map(map)`
- `buttonmatrix:set_selected(index)`
- `buttonmatrix:get_selected()` -> index or nil
- `buttonmatrix:get_button_text(index)` -> string
- `buttonmatrix:set_one_checked(bool)`
- `calendar:set_today(y, m, d)`
- `calendar:set_shown(y, m)`
- `calendar:set_highlighted({{y,m,d}, ...})`
- `calendar:get_pressed_date()` -> `{ year = y, month = m, day = d }` or nil
- `canvas:fill_bg(color[, opa])`
- `canvas:set_px(x, y, color[, opa])`
- `canvas:set_rgb565_data(data[, byte_order])`
- `canvas:get_px(x, y)` -> `{r, g, b, a}`
- `chart:add_series(color[, axis])` -> series handle
- `chart:set_type(type)`
- `chart:set_point_count(n)`
- `chart:set_range(min, max[, axis])`
- `chart:set_next_value(series, value)`
- `chart:set_series_values(series, values)`
- `chart:refresh()`
- `imagebutton:set_src(state, mid[, left, right])`
- `imagebutton:set_state(state)`
- `led:set_color(color)`
- `led:set_brightness(v)`
- `led:get_brightness()` -> integer
- `led:on()`, `led:off()`, `led:toggle()`
- `menu:page([title])` -> page
- `menu:cont(parent)` -> cont
- `menu:section(page)` -> section
- `menu:separator(page)` -> separator
- `menu:set_page([page])`
- `menu:set_sidebar_page([page])`
- `menu:set_mode_header(mode)`
- `menu:set_root_back_button(bool)`
- `menu:clear_history()`
- `msgbox:add_title(text)` -> msgbox_child
- `msgbox:add_text(text)` -> msgbox_child
- `msgbox:add_footer_button(text)` -> msgbox_child
- `msgbox:add_close_button()` -> msgbox_child
- `msgbox:close()`
- `msgbox:close_async()`
- `spangroup:add_span(text[, style])` -> span handle
- `spangroup:get_span_count()` -> integer
- `spangroup:refresh()`
- `span:set_text(text)`
- `span:get_text()` -> string
- `span:set_style(opts)`
- `span:delete()`
- `spinbox:set_step(v)`
- `spinbox:get_step()` -> integer
- `spinbox:increment()`
- `spinbox:decrement()`
- `spinbox:step_next()`
- `spinbox:step_prev()`
- `tabview:add_tab(name)` -> tab page
- `tabview:set_active(index[, anim])`
- `tabview:get_active()` -> index
- `tabview:get_tab_count()` -> integer
- `tabview:set_tab_text(index, text)`
- `tileview:add_tile(col, row[, dir])` -> tile
- `tileview:set_tile(tile[, anim])`
- `tileview:set_tile_by_index(col, row[, anim])`
- `tileview:get_active_tile()` -> tile or nil
- `window:add_title(text)` -> label
- `window:add_button([icon[, width]])` -> button
- `window:get_header()` -> object
- `window:get_content()` -> object

`span:set_style(opts)` applies style options through the owning `spangroup`.

- `canvas.color_format`: `rgb565`, `rgb888`, `xrgb8888`, `argb8888`, `native`
- `chart.type`: `none`, `line`, `curve`, `bar`, `stacked`, `scatter`
- `chart.update_mode`: `shift`, `circular`
- `chart` axis: `primary_y`, `y`, `secondary_y`, `primary_x`, `x`, `secondary_x`
- `imagebutton` state: `released`, `pressed`, `disabled`,
  `checked_released`, `checked_pressed`, `checked_disabled`
- `spangroup.mode`: `fixed`, `expand`, `break`
- `spangroup.overflow`: `clip`, `ellipsis`
- `menu` header mode: `top_fixed`, `top_unfixed`, `bottom_fixed`
- Direction values: `none`, `left`, `right`, `top`, `bottom`, `hor`, `ver`, `all`

## Demos

- `lvgl.demos()` -> `{name, ...}`
- `lvgl.demo(name)` -> `true`

`lvgl.demo(name)` requires an initialized LVGL runtime. Available demo names depend on firmware LVGL demo build flags.

## Raw Images And Dynamic Lines

Raw image setters accept tightly packed pixel strings. RGB565 uses little-endian bytes by default; `{swapped=true}` accepts big-endian RGB565. ARGB8888 uses B, G, R, A byte order. The string length must equal `width * height * bytes_per_pixel`. Dimensions must be positive integers; height is limited to 65535 pixels, and maximum width depends on pixel format and firmware. Oversized images raise an error.

Uploads replace the previous source. Argument, allocation, or unsupported-format errors leave the previous image intact. Lua strings and image frames may be released immediately after upload.

`set_rotation(angle)` accepts an integer in tenths of a degree, clockwise, normalized modulo 3600. `set_pivot(x, y)` uses pixel coordinates. Pivot and line coordinates must be integers in `[-32768, 32767]`. Image rotation requires firmware draw support for its color format.

Use `image` to load and convert a JPEG before displaying it:

```lua
local image = require("image")
local source <close> = image.load_file(path)
local cover <close> = image.resize(source, { width = 148, height = 148, format = image.RGB565 })
local picture = lvgl.image(scr, { w = 148, h = 148 })
picture:set_raw_rgb565(148, 148, cover:data())
picture:set_pivot(74, 74)
picture:set_rotation(450)
```

Line construction and `set_points()` accept 2–1024 point tables; omitted coordinates default to zero. Invalid arguments leave the previous line unchanged and raise a Lua error. Calls on deleted objects also raise an error.

## Limitations

- Encoder and keypad input are not available.
- Some widgets and demos depend on LVGL `LV_USE_*` build flags; disabled entries raise a Lua error such as `not enabled in firmware`.
- `lvgl.font_load(...)` requires LVGL `tiny_ttf` support.
- Image decoders and general filesystem setup are not wrapped.
- Constructor `src` and `imagebutton:set_src(...)` pass string sources to LVGL; loading them depends on firmware FS/decoder setup. `image` raw setters bypass file decoding.
- Canvas supports background fill, pixel read/write, and RGB565 pixel uploads. Advanced drawing layers are not available.
- Chart cursors and other advanced chart APIs are not wrapped.
- Span and chart series handles support only their documented methods, not general widget methods such as `set_pos`.
- Non-ASCII text rendering depends on either firmware-enabled fonts or a
  runtime TTF font applied with `font`.
