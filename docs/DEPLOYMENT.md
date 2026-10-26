# 安装、启动与更新

程序源码、运行资源、用户数据及开发验证目录的用途见 [项目目录](PROJECT_LAYOUT.md)。源码根目录只保留日常启动与安装入口；验证工具集中到 `scripts/verification/`，部署导出工具位于 `scripts/release/`，两者均不进入部署仓库。

平台支持「检查更新」：安装器部署后自动检测一次，也可从网页手动检测；确认安装后下载、校验和准备新版本，下次启动生效。开发工作区仅支持检查，禁止原地覆盖源码。更新流程及验证范围见 [三师模式与平台更新](MODES_UPDATES.md)。部署版包含自动端口切换和macOS应用启动器，具体版本以安装渠道的提交SHA为准。

## 新电脑

仓库当前公开。Windows 10/11 x64，**CMD、Windows PowerShell 和 PowerShell 7 均执行同一条命令**。首次安装与覆盖重装通用：

```cmd
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "[Net.ServicePointManager]::SecurityProtocol=[Net.SecurityProtocolType]::Tls12; & ([scriptblock]::Create([Text.Encoding]::UTF8.GetString([Net.WebClient]::new().DownloadData('https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1')))) -Reinstall"
```

首次安装创建程序和桌面入口；再次执行会下载并覆盖同一安装位置的程序，保留项目、对话和 API 设置。重装前先保存项目，在原服务窗口按 Ctrl+C；自定义安装过路径的用户须继续指定原 `-InstallDir`，见下文「自定义安装」。

macOS 13.5+（Intel / Apple Silicon）：

```bash
curl -fsSL https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.sh | bash
```

命令下载并运行本仓库安装脚本；无需 Git、Homebrew、Node 或 Python。国内入口使用 Gitee 下载源码、npm 镜像下载 Node 与 Python 独立运行时、npmmirror 下载前端包、清华 PyPI 镜像下载 Python 依赖；国内渠道不自动回退 GitHub。浏览器使用桌面 Chrome / Edge，设备需合适的 MicroPython 固件及串口驱动；安装器不自动刷设备或安装系统驱动。AI Key 在网页设置，不写进安装命令。

## 环境准备顺序

1. 读取选定仓库分支的不可变提交 SHA（Gitee master / GitHub main）。Windows 上述命令带 `-Reinstall`，同一版本也重新下载；不带该参数时复用完整包，损坏包自动下载修复。macOS 复用校验通过的版本，缺失才下载该 SHA 的源码 ZIP。Windows 检查压缩包路径和链接，macOS 检查路径；逐文件校验 DEPLOYMENT.sha256 后才执行包内脚本。
2. 离线检查项目运行时和本机 Node 22+/npm、Python 3.12+；可用则复用。缺失时直接下载 Node 24.14.0、Python 3.13.7 独立构建 20250918（固定 SHA-256），所有渠道均无需 uv。国内渠道使用 npm 国内镜像，GitHub 渠道使用 Node 官网与 python-build-standalone 上游发布文件。Windows x64、macOS arm64/x64 分别选择匹配运行时，不需要 sudo；安装器下载的运行时放在安装根的 runtime，各程序版本共享并先检测复用。
3. 使用 Python 自带的 `venv` 创建每版 `.venv`，通过环境内的 `python -m pip` 安装锁定依赖；本机解释器需具备 `venv` 和 `ensurepip`，否则选择独立 Python。已有可用 `.venv` 直接复用，不因本次准备方式变更而重建。实际包版本和关键导入均检查；前端核对锁文件、平台及命令入口。完整依赖跳过下载，缺失才补齐，npm 优先使用缓存。源码摘要不变时跳过构建。

   Windows 覆盖重装会连同旧程序环境暂存，再在原路径准备新的 `.venv`、前端依赖及构建；共享 `runtime` 中的 Node/Python 和可用下载缓存仍可复用。日常启动、正常后台更新及 macOS 同版本重试沿用上述依赖复用逻辑。
4. 安装与 strict 构建成功才原子切换 current.txt。失败保留原入口及数据；安装锁防止并发。下载中断留下的 download-* 目录仅供诊断，可在关闭安装器后手动清理。
5. Windows 建立桌面 ZhangWen.lnk，图标是随包掌问 Logo；macOS 生成启动掌问.command及掌问.app。应用放入可写的`/Applications`，否则放入个人`~/Applications`，无需sudo。应用启动终端中的本地服务并打开浏览器，同数据目录再次启动时核对标记并打开已有平台。
6. 默认端口30801或`--port`指定的首选端口不可用时，依次尝试其后最多99个端口，再由系统分配空闲端口。实际绑定的socket直接交给服务，浏览器、健康标记和精确Host/Origin使用实际端口；不终止占用进程，不允许同一数据目录启动第二份服务。

结构设计使用 CadQuery/OCP/trimesh，首次安装需要下载几何库。Intel Mac 的 numpy/numba/llvmlite/nlopt 使用独立精确版本，依赖检测与 pip 均按同一平台条件选择；Intel Mac 复用 Python 3.12/3.13，其他解释器由启动入口切换至托管 3.13.7。Windows、Apple Silicon 继续使用对应平台的锁定版本。

macOS 锁目录若因强制关机留下，确认没有安装程序后再移除提示中的 install.lock 或 bootstrap-unix.lock 目录；Windows 文件锁进程结束自动释放。

## 安装位置与数据

| 系统 | 程序及启动器 | 项目、硬件库及 API 设置 |
| --- | --- | --- |
| Windows | `%LOCALAPPDATA%\ZhangWen` | 该目录下 `data` |
| macOS | `~/Library/Application Support/ZhangWen` | 该目录下 `data` |

`versions/<提交SHA>` 是独立版本。Python 环境不可跨路径或跨系统搬迁；新版本独立检查及准备依赖，旧版本保留以便回退。图标/启动文件只读 current.txt，不自行联网更新；离线可用，AI 请求仍取决于模型服务。

API 设置在 `data/zhangwen-settings.json`，Key 为本机明文文件，不能共享或上传。项目存原 SQLite/Artifact，硬件包通过原安装器加载：74 个原包、2 个 Web 新主控包、184 个品牌包，Web 可见 258 项（5 主控、252 模块、1 供电）。现有用户包保留，未知电气参数和未联调驱动不会伪装成已验证。

统一命名版本沿用同一数据目录，自动兼容旧配置、工作区表及历史产物标识；浏览器在原地址刷新后迁移草稿、主题、目录关联和固件备份，已有新记录优先。升级前保存项目并备份，避免同时使用两代页面写入；历史对话与代码内容不因改名而重写。源码启动入口为 `python -m zhangwen.web`，模型环境变量为 `ZHANGWEN_MODEL`。

现有 D:/ZW_V4 源码运行的 `.data` 不会被安装器接管。要迁移，先停止两个服务，备份新旧完整数据目录（含 SQLite WAL/SHM），再明确复制用户选定的数据副本；不要连接 V1 生产库。也可用工作台文件夹保存/加载携带项目。不要只复制单个数据库或将完整安装目录含 Key 发给他人。

## 自定义安装、测试与日常启动

Windows 自定义路径，安装后不启动：

```powershell
& ([scriptblock]::Create((irm https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1))) -Reinstall -InstallDir 'D:\Apps\掌问平台' -NoStart
```

macOS 自定义路径，安装后不启动：

```bash
curl -fsSL https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.sh | ZHANGWEN_INSTALL_DIR="$HOME/Apps/掌问平台" ZHANGWEN_NO_START=1 bash
```

Windows 以后双击桌面图标；macOS 在应用程序中打开掌问.app，可固定到Dock。个人Applications中的应用可在Finder「前往 → 个人文件夹 → Applications」找到。应用只保存安装根目录，依照current.txt启动当前版本，更新后无需重建Dock入口；也可执行：

```bash
bash "$HOME/Library/Application Support/ZhangWen/启动掌问.command"
```

源码目录仍可双击 start-web.bat / 执行 bash start-web.sh，默认该目录 `.data`。只准备环境使用 Windows `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/bootstrap-windows.ps1 -PrepareOnly`，macOS `bash start-web.sh --prepare-only`。服务器支持 `--no-open`、`--port 3082`。Ctrl+C 停服务。更改端口会改变浏览器授权和草稿所属 Origin。

macOS可在安装命令的环境中指定`ZHANGWEN_APPLICATIONS_DIR="$HOME/Applications"`选择应用入口位置；测试时可指向临时目录。若已有同名的其他应用或链接，安装器保留它并提示，不覆盖。更改端口后可能需要重新授予串口/项目文件夹权限；已保存到本地项目的代码与对话仍在，原端口的未保存浏览器草稿不会自动迁移。

## 更新与回退

macOS关闭网页后，再次打开同一个「掌问.app」可返回正在运行的工作台，不会再开终端。首次启动仍保留一个服务终端；启动期间连续点击会等待同一服务。关闭网页不停止服务，停止或应用更新时仍在原终端按Ctrl+C。若终端报告启动失败，先处理原错误再重试，无需重新安装一份应用。

该行为通过新版受管应用入口提供。旧版用户在此修复正式发布后，使用原安装位置更新；首次正常启动会修复已有掌问.app入口。手动双击「启动掌问.command」属于终端启动方式，仍可能打开终端窗口。当前Windows验证不能代替Finder实际双击验收。

先保存工作并关闭服务，再执行同一安装命令。Windows 会重新下载核验，覆盖同一版本的程序目录、准备依赖并修复桌面入口，项目和设置所在 `data` 不移动、不重置。旧程序暂存于安装根 `download-*/previous-version`；下载或清单失败不替换原目录，环境准备失败恢复原目录，准备成功后才选择新版本。目录被占用而无法替换时提示关闭原服务后重试，不终止其他进程。不带 `-Reinstall` 的后台安装仍复用完整包，损坏包自动修复。macOS 同一提交校验通过时复用，源码被改动则保留并报错。自定义路径应始终使用原 `-InstallDir`。

回退前先停止服务、备份 data，再把 current.txt 改成 versions 内已成功安装的旧提交 SHA。数据库若已经迁移，应连同更新前的数据备份一起回退；仅保留旧程序目录不等于数据库可逆。旧版本不会自动删除。

## 旧版更新地址失效

2026-10-26核查：`a1b22e8d0cd610ad14f6e2c22ca59c3d5c3c7057` 的更新器固定访问旧 `ys_Ethan/zhangwen` 的 main，公开分支API返回404，旧安装脚本链接返回403。当前发布地址是 `zmh1979/ask-with-your-palm` 的 master，API和安装脚本正常，最新已发布版本为 `V0.4.2026.1022.02`。这些状态是当日读到的结果，后续可能变化。

服务器换了仓库，不会改写旧电脑已经安装的更新器。旧版失败发生在检查阶段，通常还没下载新版本，`updates` 下可能没有本次安装日志；在旧页面反复点击更新或刷新均无法修复旧地址。不要直接编辑 `versions` 内的源码或清单，修改会触发部署摘要检查失败。

默认Windows安装的恢复步骤：先在工作台保存项目，找到仍在运行服务的终端按Ctrl+C，再在CMD或PowerShell执行本文顶部同一条命令。它从新地址下载当前安装器，在同一个 `%LOCALAPPDATA%\ZhangWen` 下准备新版本；准备成功后选择新入口，`data` 中的项目和设置保留。自定义安装的用户，应在PowerShell执行下面命令，把示例路径替换为原安装根目录：

```powershell
& ([scriptblock]::Create((irm https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1))) -Reinstall -InstallDir 'D:\Apps\掌问平台'
```

macOS用户也应先保存并停止原服务，再运行本文顶部的新macOS安装命令；自定义位置通过 `ZHANGWEN_INSTALL_DIR` 指定原目录。不要卸载或删除data来处理仓库地址问题。更新后须启动新服务；关闭网页本身不会停止旧服务，旧服务继续运行时页面仍可能显示旧版本。

CMD中直接执行 `irm ... | iex` 会报命令不存在；`-ExecutionPolicy Bypass` 只是允许本次PowerShell执行脚本，不会令CMD识别PowerShell语法。统一命令显式启动 Windows PowerShell，先设置 TLS 1.2，再用 .NET 下载脚本；首次下载不依赖 PowerShell 模块，下载异常直接停止。命令不含会被外层 PowerShell 展开的变量，内部操作符全部包在引号内，CMD也能原样执行。安装脚本随后隔离当前进程模块路径，不修改系统环境或持久执行策略。

若使用新入口后仍失败，按阶段收集错误：检查更新看HTTP状态/完整提示；后台安装失败看安装根 `updates/<提交SHA>.log`；手动安装失败保留终端第一条错误。403/404、TLS/证书、ZIP准备失败、依赖下载超时、清单文件被修改、缺少磁盘空间和安装锁含义不同，不能只凭“更新失败”判断。日志分享前去掉API Key等私人信息，不需要发送整个data目录。

## Windows PowerShell 模块冲突

Windows 更新器固定使用系统 Windows PowerShell 5.1。服务若由 PowerShell 7、IDE 或自动化工具启动，父进程的 `PSModulePath` 可能含另一版本的模块；`-NoProfile` 不会清除这个环境变量，因而可能出现 `Get-FileHash` 无法识别或模块无法加载。

安装器、源码启动和生成的桌面启动脚本在调用模块前仅使用当前宿主自带的 `Modules` 目录；后台更新启动子进程时丢弃继承的 `PSModulePath`。桌面快捷方式明确指向系统 Windows PowerShell，避免在 PowerShell 7 目录拼接不存在的 `powershell.exe`。仅调整应用进程环境，不更改系统或用户级环境变量；直接运行安装器或快捷方式创建脚本后恢复调用方的模块路径。

旧版因模块冲突无法更新时，先保存项目并关闭原服务，再在 CMD 或 PowerShell 执行本文顶部同一条安装命令；自定义安装位置须沿用原路径。无需清空系统环境变量、卸载 PowerShell 7 或删除数据。下载、清单或准备失败会保留当前选择；后台更新日志位于安装根 `updates`。

## 发布范围

DEPLOYMENT.sha256 是部署文件摘要清单；源码仓库不上传 node_modules、.venv、dist、运行环境二进制、用户数据、Key、备份、演示材料、开发记录或截图。构建工具保留 TypeScript/Vite，Playwright/Vitest/pytest 等测试工具不在部署依赖中。结构设计使用的 CadQuery/OCP/trimesh 按平台锁定安装；五款主控的官方默认固件属于本地部署资源，随包校验摘要。用户项目、设备备份和本机编辑的案例均不从开发电脑上传。

依赖及完整硬件包保留其来源/许可证。Git 历史中既有资料通过旧提交/备份标签可查，此次精简针对 main 当前文件树，不重写历史。

## 验证边界

Windows 的隔离安装、重复执行与启动结果见本轮开发验证记录。macOS 安装分支和 shell 语法在 Windows 检查，未以此宣称 Mac 实机验收；仓库 CI 会在 Windows、macOS Apple Silicon/Intel 上执行准备、构建及目录/服务冒烟。以对应提交的实际 Actions 结果为准。浏览器真机串口、固件刷写和模型调用属于独立验收。
