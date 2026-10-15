# 第三方与资料来源

本版复用旧掌问仓库的后端源码、Hardware Skill 格式与硬件资料，部署文件摘要见根目录 `DEPLOYMENT.sha256`，资料来源见各硬件包的 `references/sources.md`。保留包内原 NOTICE、许可证及来源链接。没有为第三方资料授予额外许可。

当前 Web 前端使用 React、Vite、CodeMirror、Lucide；后端使用 FastAPI、Pydantic、Uvicorn、HTTPX、PyYAML 等。精确版本由根 `package-lock.json` 与 `services/local-api/requirements-web-lock.txt` 锁定；依赖的许可证随各上游分发。

浏览器固件功能使用 Espressif [esptool-js](https://github.com/espressif/esptool-js) 0.5.6（Apache-2.0），由package-lock锁定。本地构建包含其芯片支持和RAM stub资源，不通过CDN加载；依赖安装目录保留上游LICENSE。厂商固件未随本项目分发，官方说明链接不表示固件再授权。

Windows/macOS 启动时从官方源下载 Node.js（https://nodejs.org/，含自身第三方许可证）与 uv（https://github.com/astral-sh/uv，MIT/Apache-2.0），通过 uv 下载 python-build-standalone 的 CPython 发行版。运行环境下载后保留其自带的许可证文件，源码仓库不包含这些二进制。

旧桌面版的 Wokwi Elements、ESP32-S3 QEMU 和 ESP-Claw 声明保存在旧版恢复标签的 `docs/THIRD_PARTY_NOTICES.md` 中。本版 Web 启动不安装或调用这些仿真运行时，不包含 QEMU 或 ESP-Claw 二进制。

本轮多品牌模块资料和官方产品图来自盛思（乐动）、Seeed Studio Grove及N+公开文档。逐项文档与原图URL、署名、版权状态、图像处理和SHA见 `vendor-catalog-manifest.json` 及各包 `references/sources.md`。盛思声明保留所有版权，N+文档署名©2020 nplus；未把文档/代码许可证当作产品图片许可。官方图片包含厂商产品示意图，均未由AI合成；按用户要求随部署资料保留来源与版权声明。
