# 掌问 V4 开发规则

用户于 2026-10-12 授权完成最小 MVP。当前工作区初始为空；V1 保留原样。
先读 CURRENT_TASK.md、HANDOFF.md、tasks/MVP.md。本目录以本文件和 MVP 计划为准。

- 产品是回环本地 Web + MicroPython，浏览器 Web Serial 为设备通道，无 Tauri/Rust。
- 复用 services/local-api/zhangwen 下 V1 源码、Hardware Skill、SQLite projects/Conversation/Artifact；不另造硬件静态数组或平行项目库。
- 原代码和资源清单见 docs/legacy-source-manifest.json；不读写 V1 用户库、不覆盖 V1。
- 默认新 .data；旧数据仅通过离线备份副本演练导入，禁止新版本直接连接旧生产库。
- 保存、检查、回读校验、运行提交、实际观察分开显示，不虚报硬件或 AI 成功。
- 上传仅清单内文件，备份、校验、端口互斥、故障恢复；无 Flash/删除设备根目录。
- 只监听 127.0.0.1，精确 Host/Origin 和写请求会话校验。模型只能返回文本和待接受代码，无设备/命令权限。
- TypeScript strict；跨端契约先定义，设备协议测试用 Fake，真实设备验收单列。
- 完成时更新计划、HANDOFF 和验证记录；不自行发布或改系统凭据。
