# 掌问本地 Web

本地部署的创作平台：MicroPython 编程、硬件资料库、AI 对话、Web Serial 上传，以及结构设计、3D 与激光造物。

## 一条命令安装并启动

Windows 10/11 x64，在 **PowerShell** 执行：

```powershell
irm https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1 | iex
```

在 Windows CMD 中执行：

```cmd
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -Command "irm https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.ps1 | iex"
```

macOS 13.5+，Apple Silicon / Intel，在终端执行：

```bash
curl -fsSL https://gitee.com/zmh1979/ask-with-your-palm/raw/master/install.sh | bash
```

无需预装 Git、Node.js 或 Python，无需先下载仓库。先检测已有环境，缺失才准备项目内运行时；依赖按锁定版本检查、补齐，随后构建并打开浏览器。默认 http://127.0.0.1:3080 ，端口不可用时自动切换到空闲端口，实际地址显示在服务窗口。首次安装需要联网。

Windows 自动创建桌面 **ZhangWen** 启动图标（掌问手掌 Logo），以后双击即可。macOS 自动创建带掌问 Logo 的 **掌问.app**，优先放入可写的 `/Applications`，否则放入个人 `~/Applications`；可从 Finder 打开或固定到 Dock。点击后在终端启动本地服务并打开浏览器。原 `~/Library/Application Support/ZhangWen/启动掌问.command` 也可继续使用。保留服务窗口，Ctrl+C 停止服务。使用桌面 Chrome / Edge 进行 Web Serial 和本地项目文件夹操作；Safari 不支持 Web Serial。

macOS 找不到入口时，无需卸载或重启电脑：先在 Finder 按 `⌘⇧G` 分别查看 `/Applications` 与 `~/Applications`。从旧版平台内更新可能使用旧安装器，遗漏新增入口；新版本正常启动时会尝试补齐。也可先保存项目、在原服务终端按 `Ctrl+C`，再重跑上方安装命令，依赖完整时会复用，用户数据保留。安装输出中的 `Application:` 是实际入口路径；安装失败时先查看错误，不要删除 `data`。

再次执行安装命令检查并安装 Gitee 最新版本；同一版本校验通过后跳过源码下载。每日启动使用图标/本地启动文件。平台支持启动检查和手动「检查更新」，确认后才安装，下次启动生效；检查失败不影响现有工作台。新版本准备成功才切换入口，旧版本和用户数据保留。

Windows 安装、启动和后台更新会隔离当前进程的 PowerShell 模块路径，避免 PowerShell 7 / 自动化环境与系统 Windows PowerShell 5.1 混用。旧版更新出现 `Get-FileHash` 加载失败时，见[部署指南中的恢复步骤](docs/DEPLOYMENT.md#windows-powershell-模块冲突)。

国内入口的源码、更新与首次安装依赖均使用国内下载源；用户数据与程序版本分开保存。旧版 Windows 桌面版保留于原 Git 历史与 `v0.1.1` / `v0.1.3` 标签，新版不自动迁移旧桌面数据。下载来源、切换渠道及验证边界见 [国内安装说明](docs/DOMESTIC_INSTALLATION.md)。

## 工作台

- 左上「模式」切换智能工程师、结构设计师和学习设计师；智能工程师和结构设计师可用，学习设计师提供界面与模板预览，学习业务待开发。平台以桌面 Web 为目标。
- K10、XIAO ESP32S3、ESP32-C3、掌控板 2.0 / 3.0；253 个模块，支持跨品牌选择、品牌及输入输出筛选。模块图片随包保存，新资料标明编程及电气参数是否完成联调。
- 新建项目先选择名称和本地文件夹，主控在工作台左侧选择，可稍后选择并保存。左侧已加入模块、中间掌问 AI、右侧编辑器；收起左栏仅扩展对话区。AI 代码先作为候选预览；保存、上传、回读校验和运行各自显示结果。
- 选择掌控板 2.0 时，AI 使用官方 v2.0.1 编程参考；不同主控使用各自资料。回复未附代码时明确提示，已完成历史回复中遗漏的有效代码可恢复为候选版本。
- 本地文件夹保存/加载项目，恢复对话及历史代码，编辑器版本下拉切换。
- 结构设计师：保留硬件外壳设计和32份几何资料，另可不选硬件，通过收纳盒、笔筒、支架模板及受约束参数生成真实 CadQuery 模型与 STEP/STL。激光切割图纸有独立对话、历史和预览/切割图，导出毫米 SVG/DXF，无需 LaserMaker。详见[功能与使用边界](docs/PLATFORM_UPGRADE_20261018.md)。
- 结构对话和模型随同一项目保存/加载，文件夹 `structure/` 中可查看模型及报告。按所选硬件生成外壳草案无需AI；自然语言需求使用平台API设置。
- 学习设计师通过「切换视角」选择教师/学生工作台，顶部「问题引导 / 项目学习 / 成果档案」切换栏目，并提供海报和赛事资料入口。右侧「选择模板」先预览，确认后替换当前材料版式；选择仅临时保留，刷新重置，生成、保存、导入导出仍待开发。
- 「文件 → 项目程序」在项目子文件夹归档程序及测试记录，保留主控、模块和来源版本信息。
- 页面「API 设置」可分别配置三个模式，提供 DeepSeek、GLM、Qwen、Kimi 与自定义 OpenAI 兼容接口。Key 只存本机，不随项目导出；手工编程不需要 Key。
- 模块资料可按主控编辑本机示例、接线选项与支持主控，跨品牌使用须核对协议、引脚、电平和库。资料中的基础示例、诊断示例与未联调项有明确区分。
- 浏览器直连 MicroPython 设备，支持 main.py 上传、SHA 回读、运行、停止、终端与文件读取。上传回读通过后自动运行，运行中按钮切换为停止；代码全屏仍保留工具栏。五款主控随包提供已固定版本与摘要的官方默认固件，点击固件并选择串口后直接更新，自动执行覆盖范围备份、镜像/芯片校验、刷入及回读；尚未完成真实刷写验收。

终端随新增输出自动滚到底部，重新打开显示最新内容。K10 上传检查可展开具体问题、预览官方屏幕 API 修复，接受保存后再上传；模块资料可独立标记「已核实主控」。结构设计入口为「3D造物 / 激光造物」，激光模板支持六面榫齿盒、圆角弯折盒及中文文字轮廓；圆角盒新版切缝交错接到上下边缘，旧图保留，可重新生成新版。实际弯折、刀缝与装配需按材料试切。

I²C模块资料显示默认/参考地址，可按主控保存实际地址与接线；这些记录不自动代表实物核实。AI优先沿用当前主控的本机案例，其他板型案例保持隔离。盛思超声波增加用户提供的单文件控制参考：0x0B写入测量命令、等待2ms、读取2字节换算厘米，无需替换固件；协议模拟通过，实物测距仍需用户上传后观察。掌控板2.0的P1为GPIO32、P0为GPIO33，原始 `machine.Pin(1/0)` 与板上P号不可混用。

部署仓库只保留构建及运行必需的源码、依赖锁、启动器、完整硬件资料与来源说明。不包含用户库、Key、设备备份、PPT、开发过程记录、截图、测试产物或桌面应用壳。运行依赖引用的原项目/Artifact/Hardware Skill 代码继续复用，未另造数据仓库。

数据默认在 Windows `%LOCALAPPDATA%\ZhangWen\data` / macOS `~/Library/Application Support/ZhangWen/data`，与程序版本分开。现有源码目录启动仍默认使用该目录的 `.data`；安装器不会自动读取或搬迁旧用户库。迁移、回退及自定义目录见 [部署指南](docs/DEPLOYMENT.md)。

## 已下载源码时

Windows 双击 `start-web.bat`，macOS 执行 `bash start-web.sh`。已有 Node 22+、Python 3.12+ 时也可以 `npm run setup` 后 `npm start`。Intel Mac 使用 Python 3.12/3.13；启动入口会自动选择兼容环境，几何依赖按处理器分别锁定。

安装入口先检查已有环境；缺失时直接下载 Node 24.14.0、Python 3.13.7（独立构建 20250918），核验固定 SHA-256，再用 Python 自带的 `venv + pip` 创建隔离环境和安装依赖，无需 uv。Windows 和 macOS 均适用。不修改系统 PATH、执行策略或凭据，无管理员权限要求。服务只监听 `127.0.0.1`。

[第三方来源与声明](docs/THIRD_PARTY_NOTICES.md)

[项目目录与数据位置](docs/PROJECT_LAYOUT.md)
