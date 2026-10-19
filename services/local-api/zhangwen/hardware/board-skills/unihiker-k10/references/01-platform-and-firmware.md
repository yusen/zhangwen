# 平台与固件

## K10 硬件基线

K10 是 MCU 开发板，核心参数包括：

- ESP32-S3 N16R8；
- 双核 Xtensa LX7，最高 240 MHz；
- 16 MB Flash；
- 8 MB PSRAM；
- 2.8 英寸 240×320 ILI9341 彩色 LCD；
- GC2145 200 万像素摄像头；
- AHT20 温湿度；
- LTR303ALS 环境光；
- SC7A20H 三轴加速度；
- 双 MEMS 麦克风；
- 2 W 扬声器；
- 3 颗 WS2812 RGB；
- Type-C、TF 卡、P0/P1、I2C 和金手指扩展。

## 与 M10 的差异

| 项目 | K10 | M10 |
|---|---|---|
| 架构 | MCU | Linux 单板计算机 |
| 默认语言 | MicroPython/Arduino | 完整 Python |
| 系统 | 无桌面 Linux | Debian |
| K10 代码库 | `unihiker_k10` | 不适用 |
| M10 常用库 | 不使用 | `unihiker`、`pinpong` |
| 软件安装 | 固件内置模块 | 可用 Linux/Python 包管理 |

## 固件检查

```python
try:
    import unihiker_k10
    print("OK: unihiker_k10")
except ImportError as exc:
    print("Missing K10 MicroPython firmware/library:", exc)
```

进一步探测：

```python
import unihiker_k10
print(dir(unihiker_k10))
```

AI：

```python
import ai
print(dir(ai))
```

语音：

```python
import asr
print(dir(asr))
```

## 固件切换风险

烧录 K10 MicroPython 固件后，如需恢复 Mind+ 默认图形化使用方式，需要按官方流程恢复设备初始设置或擦除并重新烧录。

在修改固件前应记录：

- 当前固件名称；
- 固件版本；
- 烧录日期；
- 项目依赖；
- 是否需要恢复出厂环境。
