# 第三方与资料来源

2026-10-19新增五个固定3D模板，来自用户提供的ZW-CAD-intent归档：掌控板3.0外壳、K10相册支架及侧式/卧式/立式舵机固定座。原Python源码和配套图片按只读副本保存在services/structure-cad/templates，manifest记录原相对路径、SHA-256及模板修订，原注释保持。未推定或新增来源素材的许可；参考硬件仅用于装配展示，不等同实物或打印验收。

文字雕刻随包提供Noto Sans SC可变字体（Google Fonts上游，SIL Open Font License 1.1），仅使用400字重生成确定性矢量轮廓。原字体、完整OFL许可与来源/SHA在resources/fonts；不依赖系统安装字体或在线字体服务。字体轮廓通过已锁定的fonttools生成，SVG含填充轮廓，DXF含雕刻层闭合轮廓；不附加机器加工参数。

本版复用旧掌问仓库的后端源码、Hardware Skill 格式与硬件资料，部署文件摘要见根目录 `DEPLOYMENT.sha256`，资料来源见各硬件包的 `references/sources.md`。保留包内原 NOTICE、许可证及来源链接。没有为第三方资料授予额外许可。

当前 Web 前端使用 React、Vite、CodeMirror、Lucide；后端使用 FastAPI、Pydantic、Uvicorn、HTTPX、PyYAML 等。精确版本由根 `package-lock.json` 与 `services/local-api/requirements-web-lock.txt` 锁定；依赖的许可证随各上游分发。

浏览器固件功能使用 Espressif [esptool-js](https://github.com/espressif/esptool-js) 0.5.6（Apache-2.0），由package-lock锁定。本地构建包含其芯片支持和RAM stub资源，不通过CDN加载；依赖安装目录保留上游LICENSE。默认官方固件现保存在resources/firmware，并被部署导出白名单包含；来源、版本、摘要与原版权声明见该目录README/manifest和许可证，不新增第三方授权。

Windows/macOS 安装入口在缺少运行环境时直接下载 Node.js（上游 https://nodejs.org/，含自身第三方许可证）和 python-build-standalone 的 CPython 3.13.7 独立发行版（上游 https://github.com/astral-sh/python-build-standalone ，构建 20250918）。这两份运行时以及前端的 npm 包、Python 依赖都从上述国内镜像获取，镜像内容对应上游发布文件；环境准备以 Python 自带的 venv/ensurepip/pip 完成，无需 uv。三个平台的独立运行时摘要与上游 SHA256SUMS 比对后固定；安装时再次校验。运行环境下载后保留其自带的 Python 许可证与第三方许可证文件，源码仓库不包含这些二进制。

旧桌面版的 Wokwi Elements、ESP32-S3 QEMU 和 ESP-Claw 声明保存在旧版恢复标签的 `docs/THIRD_PARTY_NOTICES.md` 中。本版 Web 启动不安装或调用这些仿真运行时，不包含 QEMU 或 ESP-Claw 二进制。

本轮多品牌模块资料和官方产品图来自盛思（乐动）、Seeed Studio Grove及N+公开文档。逐项文档与原图URL、署名、版权状态、图像处理和SHA见 `vendor-catalog-manifest.json` 及各包 `references/sources.md`。盛思声明保留所有版权，N+文档署名©2020 nplus；未把文档/代码许可证当作产品图片许可。官方图片包含厂商产品示意图，均未由AI合成；按用户要求随部署资料保留来源与版权声明。

掌控板2.0编程摘要依据用户指定的 https://mpython.readthedocs.io/zh-cn/v2.0.1/index.html 及其同版本库说明。官方署名©2018–2020 labplus，All Rights Reserved；仅保留调用摘要、来源与项目最小例程，未镜像整站或授予额外许可。核对URL与SHA见 `services/local-api/zhangwen/web/programming-skills/mpython-v2/references/sources.json`。

主控选择补充的三张配图来自 Espressif ESP32-C3-DevKitM-1 官方文档、Seeed Studio XIAO ESP32S3 Sense 官方文档与盛思掌控板2.0官方硬件说明。图片版权归各厂商，保留原图来源，不将文档/代码许可证当作图片的额外授权。原图URL、原始/转换SHA、尺寸与处理说明见 `apps/web/src/assets/boards/sources.json`；图片仅用于产品识别，通用C3注明开发板示例，掌控板2.0为官方产品示意图。配图不改变原Hardware Skill与硬件能力定义。

结构设计师复用用户提供的 ZW-CAD-intent（2026-06-26）确定性需求/BOM/布局/CadQuery工具与Markdown技能契约，来源摘要见开发工作区docs/structure-source-manifest.json。仅迁入运行代码、32份几何profile和6张附带硬件图，未复制其.env、模型凭据、用户导出模型、node_modules或Python环境。几何资料是安装尺寸扩展，不替代现有Hardware Skill编程/电气库。

3D预览使用Three.js 0.160.1（MIT）；真实建模使用CadQuery 2.8.0（Apache-2.0）、cadquery-ocp/OCCT绑定及trimesh 4.12.2（MIT）等锁定依赖。安装环境保留各上游发行包自带LICENSE和NOTICE；OCCT本身适用LGPL-2.1及OCCT例外。二进制环境与用户模型不随源码上传，模型不代表实物强度或加工验收。
