# micro:bit MicroPython 编程参考

适用 BBC micro:bit V1/V2，先确认实际板型与官方 MicroPython 固件。V1/V2 通用部分使用 `from microbit import *`。

- 显示：`display.show(Image.HAPPY)`、`display.clear()`；5×5 点阵。`sleep(500)` 的单位是毫秒。
- 按钮：`button_a.is_pressed()` / `button_b.was_pressed()`。加速度：`accelerometer.get_values()`。温度：`temperature()`，不是环境温度仪器的精度承诺。
- 引脚：`pin0.read_analog()`、`pin1.write_digital(1)`；按实物 P0/P1/P2 引脚接线。不要使用 ESP32 的 `machine.Pin(GPIO)`、`mpython.oled` 或 `unihiker_k10.screen`。
- V2 的麦克风、扬声器、触摸 Logo 不视为 V1 通用能力；先识别板型，按对应文档查询，不无条件导入 V2 专有模块。
- 文件：`open(name, 'rb'/'wb')`、文件 `read/write/close`、`os.listdir()`。文件系统无目录层级、容量有限；不要依赖 ESP32 的 os.stat/rename、json、hashlib、binascii、compile 或固定 machine.unique_id API。
- MicroPython 串口 REPL 使用 115200 波特率；Ctrl-C 中断，raw REPL 用 Ctrl-A/Ctrl-D/Ctrl-B。掌问仅用户点击后通过浏览器 Web Serial 操作。
- main.py 是 MicroPython 的启动程序；保存到设备后下次重启可能执行。首次用官方 Python 编辑器准备固件可能替换已有程序，应先自行备份；掌问不自动烧录 HEX 或切换引导模式。
- 掌问上传前将原 main.py 两次读取核对并持久备份到浏览器，再分块覆盖并完整回读，在浏览器计算 SHA-256。无原子 rename；写入中断不自动恢复或重发，必须重新连接并核对。文件空间不足会真实失败。
- micro:bit 连接标识标为 session: 会话身份，不当成硬件序列号或跨重连实测凭证。

## 最小有界示例
```python
# 用途：micro:bit 点阵自检；无外接器件。
from microbit import display, Image, sleep
display.show(Image.HAPPY)
sleep(600)
display.clear()
print("MICROBIT_DISPLAY_TEST_RETURNED")
```
屏幕现象须由用户观察；打印标记不代表实物已验收。
