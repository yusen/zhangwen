# 安全与故障排查

## 回调或线程导致重启

官方 FAQ 指出，在 MQTT、引脚中断、多线程等回调或线程中使用屏幕显示，可能因屏幕更新内存占用较大而导致异常重启。

正确模式：

```python
event_pending = False

def callback():
    global event_pending
    event_pending = True

while True:
    if event_pending:
        event_pending = False
        screen.draw_text(text="event")
        screen.show_draw()
```

## AI 画面卡住

避免高频调用：

- 摄像头显示初始化；
- `camera_start()`；
- `move_detect()`、`code_scanner()` 等模式切换函数。

这些操作只应在初始化或明确的状态切换时执行。

## 持续重启或死机

排查顺序：

1. 回退到 `templates/00_profile_probe.py`；
2. 删除屏幕、AI、TF 卡和网络，只保留串口；
3. 检查供电和 USB 数据线；
4. 检查外接执行器电流和接线；
5. 检查是否在回调/线程中刷新屏幕；
6. 检查是否循环初始化 AI；
7. 检查 TF 卡质量；
8. 按官方流程恢复设备初始化设置或擦除；
9. 重新烧录匹配固件。

## 导入失败

```text
ImportError: no module named ...
```

检查：

- 是否为 K10；
- 是否烧录 `unihiker_k10` MicroPython 固件；
- 是否误用了 `educore`、M10 或普通 ESP32 示例；
- 模块名大小写；
- 当前固件版本是否包含 AI/ASR；
- 是否需要恢复后重新烧录。

## 串口无法识别

- 更换支持数据的 USB 线；
- 直接连接电脑 USB 口；
- 关闭占用串口的软件；
- Windows 10/11 通常不需额外驱动；
- Windows 7 按官方说明安装驱动；
- 烧录时按住 BOOT，完成后按 RST。

## 外接执行器

- 舵机、电机、泵、灯带和继电器先评估电流；
- 大负载独立供电并共地；
- 感性负载使用驱动器和续流保护；
- 禁止直接从 GPIO 驱动电机、泵或继电器线圈；
- 上电先设置安全状态。
