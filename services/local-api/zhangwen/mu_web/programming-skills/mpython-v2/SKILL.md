---
name: mpython-v2
description: 为掌控板2.0（ESP32、128×64单色OLED）编写和调试MicroPython；用于该板的屏幕、按键、RGB和板载传感器代码，不用于掌控板3.0彩屏API。
---

# 掌控板 2.0 MicroPython 编程

先确认目标为 `hw_labplus_mpython_v2`，使用官方 mPython ESP32 固件。看到 ESP32-S3、彩色显示或 `display` 请求时先核对主控版本。

按需读 [API 和代码参考](references/api.md)。硬件接线、电平和可用模块仍以当前 Hardware Skill 为准；不得用此编程参考推定外接引脚。

输出可单独保存的完整 main.py。屏幕使用 `from mpython import oled`，128×64、0/1单色；绘制后 `oled.show()`。不能套用3.0的 `lcd.WHITE` 或彩屏尺寸。用户需要联调时先问接口/固件，再分模块提供最小程序、预期现象和观察方法。

未知API先通过用户显式REPL检查 `import mpython; print(dir(mpython))`；不能臆造库、引脚或声称已上传/测试。代码只是待接受建议，不授予串口、命令或固件操作权限。

验证分级：空心圆示例已于2026-10-15在COM522掌控2.0运行，用户确认实物显示；其余API参考不等于本机全部实测。记录当前固件差异，不把2.0结果套到3.0。
