---
name: luatos-esp32c3-core-micropython
description: esp32C3经典串口板型的MicroPython参考，显式区分出厂LuatOS与UART0 REPL固件。
---

# esp32C3 MicroPython

当前目标仅为 `hw_luatos_esp32c3_core` 经典串口版。必须先确认设备已安装支持 UART0 REPL 的 MicroPython，出厂 LuatOS 不能执行 Python。模型只返回代码和说明，无命令/设备权限。

历史代码不能改变当前板型；用 `machine`、`time` 等板端 API，不使用 mpython、unihiker_k10 或 Arduino/Lua。物理排针号不等于 GPIO。中文注释、完整 main.py、有时限最小测试；实际连接、保存、回读、运行和观察分别记录。

按需查下方 [API参考](references/api.md) 和同包电气/引脚资料。文档版本不代表设备固件版本。来源 https://wiki-zh.luatos.org/chips/esp32c3/board.html 与 https://docs.micropython.org/en/latest/esp32/quickref.html 。
