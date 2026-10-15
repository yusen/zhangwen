# 第三方与资料来源

本版复用旧掌问仓库的后端源码、Hardware Skill 格式与硬件资料，来源及摘要见 `legacy-source-manifest.json`、`hardware-import-snapshot.json` 和各硬件包的 `references/sources.md`。保留包内原 NOTICE、许可证及来源链接。没有为第三方资料授予额外许可。

当前 Web 前端使用 React、Vite、CodeMirror、Lucide；后端使用 FastAPI、Pydantic、Uvicorn、HTTPX、PyYAML 等。精确版本由根 `package-lock.json` 与 `services/local-api/requirements-web-lock.txt` 锁定；依赖的许可证随各上游分发。

Windows 启动时从官方源下载 Node.js（https://nodejs.org/，含自身第三方许可证）与 uv（https://github.com/astral-sh/uv，MIT/Apache-2.0），通过 uv 下载 python-build-standalone 的 CPython 发行版。运行环境下载后保留其自带的许可证文件，源码仓库不包含这些二进制。

旧桌面版的 Wokwi Elements、ESP32-S3 QEMU 和 ESP-Claw 声明保存在旧版恢复标签的 `docs/THIRD_PARTY_NOTICES.md` 中。当前保留的仿真兼容源码另有 `services/local-api/zhangwen/domains/simulation/THIRD_PARTY_NOTICES.md`，本版 Web 启动不安装或调用这些仿真运行时，不包含 QEMU 或 ESP-Claw 二进制。
