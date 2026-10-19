---
name: mpython-v3
description: 为掌控板3.0（ESP32-S3、彩色屏）编写和调试官方MicroPython代码；使用mpython.display和lcd颜色，避免误用掌控板2.0的单色oled接口。
---

# 掌控板 3.0 MicroPython 编程

目标为 `hw_labplus_mpython_esp32s3_v3`，官方掌控板3.0 ESP32-S3固件。先读 [API 和示例](references/api.md)。完整原始资料位于 `resources/hardware-skills/labplus-mpython-esp32s3-v3/`（相对项目根），按需求查 `examples/usage.md`、`references/specifications.md`、`references/integration.md` 和 `references/sources.md`，不要同时照搬全部外设示例。

使用 `mpython.display` 和 `lcd` 颜色对象，不照搬2.0的单色OLED流程。需要修改代码时给出完整main.py，先核对固件和实际连接；外接端口依据当前硬件资料，未知签名先问或请求用户显式REPL确认。

代码参考是文档证据，不是设备成功记录。当前3.0没有本项目真实硬件验收，不把2.0空心圆实测当成3.0验收。保持代码建议、接受、保存、上传和运行独立；本Skill不授予设备、命令或固件权限。
