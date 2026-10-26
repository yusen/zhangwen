---
name: unihiker-k10-display
description: 行空板K10官方MicroPython屏幕调用、初始化与显示提交，区分外接模块驱动和板载屏幕。
---

# 行空板 K10 屏幕编程参考

仅适用于 `hw_seed_unihiker_k10`。复用项目原 `hardware/board-skills/unihiker-k10/references/03-screen-api.md` 与 `templates/01_screen_shapes.py`，来源为 https://www.unihiker.com.cn/wiki/k10/micropython_unihiker_k10 。以下官方接口资料随生成请求完整加载，不依赖聊天时联网，也不表示当前设备已测试通过。

屏幕完整流程必须是：`from unihiker_k10 import screen` → 程序开始时仅一次 `screen.init(dir=2)` → `screen.clear()` / `screen.show_bg(color=0x000000)` → `screen.draw_text(text="…", x=10, y=20, font_size=24, color=0xFFFFFF)` → `screen.show_draw()`。刷新在主循环进行，普通面板0.5至1秒一次；初始化放在循环外。

`Screen` 对象没有 `canvas` 的报错应先核对是否遗漏 `screen.init()`；不得根据此报错猜造 `unihiker_k10.draw.text()`、`screen.text()`、`screen.canvas`、framebuf、mpython.oled 或 M10 GUI。本参考的文字接口为 `screen.draw_text()`，绘制后需要 `screen.show_draw()`，颜色与背景应有对比，坐标保持在屏内。旧助手回复里的 draw/text 推测无效，修复必须回到本参考。缺少当前固件 API 时请提供最小探测程序，不能猜另一个接口。

外接模块与板载显示分别选驱动：Grove超声波单SIG使用该模块的当前主控兼容案例（machine.Pin + time_pulse_us），不改成只适用于DFRobot模块的 ultrasonic。屏幕仍用K10官方screen；不要因传感器用machine就更换屏幕API。

导入或初始化出现 ETIMEDOUT 时，明确提示当前屏幕初始化失败并打印异常。串口测距可继续，但必须明确“仅串口运行，屏幕不可用”，不能以测距正常宣称屏幕正常。不应在每轮循环反复吞掉相同绘图错误、无提示跳过显示或无限重试初始化。

代码应有中文用途/接线/关键参数/步骤/异常处理注释。提供完整main.py；仅供用户接受、上传运行和反馈，不能宣称已经显示或测试成功。
