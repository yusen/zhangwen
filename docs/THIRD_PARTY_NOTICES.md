# 第三方组件声明

## Wokwi Elements 1.9.2

- 项目：`@wokwi/elements`
- 来源：https://github.com/wokwi/wokwi-elements
- 许可证：MIT（上游许可证：https://github.com/wokwi/wokwi-elements/blob/main/LICENSE）
- 用途：项目实物仿真的板卡、外设外观和交互控件。它不执行硬件仿真。
- 分发：作为 pnpm 锁定依赖由前端本地打包。

## Espressif ESP32-S3 QEMU

- 参考：https://github.com/espressif/esp-toolchain-docs/blob/main/qemu/esp32s3/README.md
- 用途：可选的离线固件级 CPU/Flash/UART 运行时。
- 当前状态：本仓库未包含 QEMU 可执行文件，也未把它加入当前安装器。启用分发前必须固定版本与 SHA-256，并随二进制提供对应许可证和完整第三方声明。

## ESP-Claw

- 项目：https://github.com/espressif/esp-claw
- K10 板级来源：https://github.com/espressif/esp-claw/tree/master/application/edge_agent/boards/dfrobot/dfrobot_k10
- XIAO Sense 板级来源：https://github.com/espressif/esp-claw/tree/master/application/edge_agent/boards/seeedstudio/xiao_esp32s3_sense
- Lua 能力参考：https://esp-claw.com/en/reference-cap/cap-lua/
- MCP 能力参考：https://esp-claw.com/en/reference-cap/cap-mcp/
- 用途：双板事实、预构建运行时包，以及 ESP-Claw Lua 代码部署协议的参考。
- 当前状态：仓库不编译或重新分发 ESP-Claw 源码/二进制；运行时包必须单独固定来源、版本和 SHA-256。首版代码部署仅连接用户在专业模式中明确配对、且通过私网/同主机/能力门禁的 Web 与 MCP 端点；尚未实现 mDNS 自动发现或设备级认证。
