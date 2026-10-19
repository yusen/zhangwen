# 行空板 K10 集成说明

## 供电与连接

- USB Type-C 使用稳定 5 V 供电，并承担固件维护和 REPL 串口通信。
- PH2.0 电池口按 3.0–6.0 V 工作区使用，接入前核对极性。
- 外部信号按 3.3 V 逻辑设计；大电流负载独立供电并与 K10 共地。
- P0/P1 是全功能 IO；金手指的其他扩展 IO 只按基础数字输入/输出规划。

## MicroPython 基线

1. 使用 K10 专用 MicroPython 固件。
2. 在 Thonny 中选择 ESP32 解释器和当前 K10 串口。
3. 先验证 `import unihiker_k10` 和 `from k10_base import Camera`。
4. 需要脱机启动时，把经过确认的代码上传为设备根目录 `main.py`。

固件烧录、Flash 擦除和真实设备上传均不是本 Hardware Skill 的隐式能力，必须经过应用中的
明确授权与设备安全确认。
