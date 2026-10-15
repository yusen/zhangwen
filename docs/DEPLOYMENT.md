# 安装、启动与更新

## 新电脑

仓库当前公开。Windows 10/11 x64 的 PowerShell：

```powershell
irm https://raw.githubusercontent.com/yusen/zhangwen/main/install.ps1 | iex
```

macOS 13.5+（Intel / Apple Silicon）：

```bash
curl -fsSL https://raw.githubusercontent.com/yusen/zhangwen/main/install.sh | bash
```

命令下载并运行本仓库安装脚本；无需 Git、Homebrew、Node 或 Python。网络需访问 GitHub/raw/codeload、nodejs.org、PyPI 和 npm registry。浏览器使用桌面 Chrome / Edge，设备需合适的 MicroPython 固件及串口驱动；安装器不自动刷设备或安装系统驱动。AI Key 在网页设置，不写进安装命令。

## 环境准备顺序

1. 读取 GitHub main 的不可变提交 SHA，复用通过文件清单校验的已安装版本；缺失才下载该 SHA 的源码 ZIP。Windows 检查压缩包路径和链接，macOS 检查路径；逐文件校验 DEPLOYMENT.sha256 后才执行包内脚本。
2. 离线检查项目运行时和本机 Node 22+/npm、Python 3.11+；可用则复用。缺失时下载项目内 Node 24.14.0、uv 0.8.22（固定 SHA-256），由 uv 准备 Python 3.13.7。Windows x64、macOS arm64/x64 分别选择匹配运行时，不需要 sudo；安装器下载的 Node/uv/Python 放在安装根的 runtime，各程序版本共享并先检测复用。
3. Python 依赖隔离在每版 `.venv`。实际包版本和关键导入均检查；前端核对锁文件、平台及命令入口。完整依赖跳过下载，缺失才补齐，npm 优先使用缓存。源码摘要不变时跳过构建。
4. 安装与 strict 构建成功才原子切换 current.txt。失败保留原入口及数据；安装锁防止并发。下载中断留下的 download-* 目录仅供诊断，可在关闭安装器后手动清理。
5. Windows 建立桌面 ZhangWen.lnk，图标是随包掌问 Logo；macOS 生成启动掌问.command。启动后自动打开本机浏览器；同数据目录再次启动时核对已有实例标记，再打开已有平台。端口被其他程序占用时提示，不杀进程。

macOS 锁目录若因强制关机留下，确认没有安装程序后再移除提示中的 install.lock 或 bootstrap-unix.lock 目录；Windows 文件锁进程结束自动释放。

## 安装位置与数据

| 系统 | 程序及启动器 | 项目、硬件库及 API 设置 |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\ZhangWen` | 该目录下 `data` |
| macOS | `~/Library/Application Support/ZhangWen` | 该目录下 `data` |

`versions/<提交SHA>` 是独立版本。Python 环境不可跨路径或跨系统搬迁；新版本独立检查及准备依赖，旧版本保留以便回退。图标/启动文件只读 current.txt，不自行联网更新；离线可用，AI 请求仍取决于模型服务。

API 设置在 `data/mu-settings.json`，Key 为本机明文文件，不能共享或上传。项目存原 SQLite/Artifact，硬件包通过原安装器加载：74 个原包、2 个 Web 新主控包、184 个品牌包，Web 可见 258 项（5 主控、252 模块、1 供电）。现有用户包保留，未知电气参数和未联调驱动不会伪装成已验证。

现有 D:/ZW_V4 源码运行的 `.data` 不会被安装器接管。要迁移，先停止两个服务，备份新旧完整数据目录（含 SQLite WAL/SHM），再明确复制用户选定的数据副本；不要连接 V1 生产库。也可用工作台文件夹保存/加载携带项目。不要只复制单个数据库或将完整安装目录含 Key 发给他人。

## 自定义安装、测试与日常启动

Windows 自定义路径，安装后不启动：

```powershell
& ([scriptblock]::Create((irm https://raw.githubusercontent.com/yusen/zhangwen/main/install.ps1))) -InstallDir 'D:\Apps\掌问平台' -NoStart
```

macOS 自定义路径，安装后不启动：

```bash
curl -fsSL https://raw.githubusercontent.com/yusen/zhangwen/main/install.sh | ZHANGWEN_INSTALL_DIR="$HOME/Apps/掌问平台" ZHANGWEN_NO_START=1 bash
```

Windows 以后双击桌面图标；macOS 可执行：

```bash
bash "$HOME/Library/Application Support/ZhangWen/启动掌问.command"
```

源码目录仍可双击 start-web.bat / 执行 bash start-web.sh，默认该目录 `.data`。只准备环境使用 Windows `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-windows.ps1 -PrepareOnly`，macOS `bash start-web.sh --prepare-only`。服务器支持 `--no-open`、`--port 3082`。Ctrl+C 停服务。更改端口会改变浏览器授权和草稿所属 Origin。

## 更新与回退

先保存工作并关闭服务，再执行同一安装命令。已安装的同一提交校验通过时跳过源码下载；有更新则安装新目录，成功才切换入口，数据不移动、不重置。安装失败后修复网络再次执行。发现已安装源码被手工改动时会保留并报错，不覆盖；需要另行保存改动并移开该版本目录再试。

回退前先停止服务、备份 data，再把 current.txt 改成 versions 内已成功安装的旧提交 SHA。数据库若已经迁移，应连同更新前的数据备份一起回退；仅保留旧程序目录不等于数据库可逆。旧版本不会自动删除。

## 发布范围

DEPLOYMENT.sha256 是部署文件摘要清单；源码仓库不上传 node_modules、.venv、dist、运行环境二进制、用户数据、Key、备份、演示材料、开发记录或截图。构建工具保留 TypeScript/Vite，Playwright/Vitest/pytest 等测试工具不在部署依赖中。少量 CAD/旧项目模型代码仍属于原硬件与项目仓库的导入依赖，保留源码不表示已开放 CAD 界面或安装 CAD 运行时。

依赖及完整硬件包保留其来源/许可证。Git 历史中既有资料通过旧提交/备份标签可查，此次精简针对 main 当前文件树，不重写历史。

## 验证边界

Windows 的隔离安装、重复执行与启动结果见本轮开发验证记录。macOS 安装分支和 shell 语法在 Windows 检查，未以此宣称 Mac 实机验收；仓库 CI 会在 Windows、macOS Apple Silicon/Intel 上执行准备、构建及目录/服务冒烟。以对应提交的实际 Actions 结果为准。浏览器真机串口、固件刷写和模型调用属于独立验收。
