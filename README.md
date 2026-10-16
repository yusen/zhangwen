# 掌问 Mu Web

本地部署的创作平台：MicroPython 编程、硬件资料库、AI 对话、Web Serial 上传，以及外壳结构设计与模型导出。

## 一条命令安装并启动

Windows 10/11 x64，在 **PowerShell** 执行：

```powershell
irm https://raw.githubusercontent.com/yusen/zhangwen/main/install.ps1 | iex
```

macOS 13.5+，Apple Silicon / Intel，在终端执行：

```bash
curl -fsSL https://raw.githubusercontent.com/yusen/zhangwen/main/install.sh | bash
```

无需预装 Git、Node.js 或 Python，无需先下载仓库。先检测已有环境，缺失才准备项目内运行时；依赖按锁定版本检查、补齐，随后构建并打开浏览器。默认 http://127.0.0.1:3080 ，端口不可用时自动切换到空闲端口，实际地址显示在服务窗口。首次安装需要联网。

Windows 自动创建桌面 **ZhangWen** 启动图标（掌问手掌 Logo），以后双击即可。macOS 自动创建带掌问 Logo 的 **掌问.app**，优先放入可写的 `/Applications`，否则放入个人 `~/Applications`；可从 Finder 打开或固定到 Dock。点击后在终端启动本地服务并打开浏览器。原 `~/Library/Application Support/ZhangWen/启动掌问.command` 也可继续使用。保留服务窗口，Ctrl+C 停止服务。使用桌面 Chrome / Edge 进行 Web Serial 和本地项目文件夹操作；Safari 不支持 Web Serial。

macOS 找不到入口时，无需卸载或重启电脑：先在 Finder 按 `⌘⇧G` 分别查看 `/Applications` 与 `~/Applications`。从旧版平台内更新可能使用旧安装器，遗漏新增入口；新版本正常启动时会尝试补齐。也可先保存项目、在原服务终端按 `Ctrl+C`，再重跑上方安装命令，依赖完整时会复用，用户数据保留。安装输出中的 `Application:` 是实际入口路径；安装失败时先查看错误，不要删除 `data`。

再次执行安装命令检查并安装 GitHub 最新版本；同一版本校验通过后跳过源码下载。每日启动使用图标/本地启动文件。平台支持启动检查和手动「检查更新」，确认后才安装，下次启动生效；检查失败不影响现有工作台。新版本准备成功才切换入口，旧版本和用户数据保留。

## 工作台

- 左上「模式」切换智能工程师、结构设计师和学习设计师；智能工程师和结构设计师可用，学习设计师提供界面与模板预览，学习业务待开发。平台以桌面 Web 为目标。
- K10、XIAO ESP32S3、ESP32-C3、掌控板 2.0 / 3.0；252 个模块，支持跨品牌选择、品牌及输入输出筛选。模块图片随包保存，新资料标明编程及电气参数是否完成联调。
- 左侧已加入模块、中间掌问 AI、右侧编辑器。AI 代码先作为候选预览；保存、上传、回读校验和运行各自显示结果。
- 选择掌控板 2.0 时，AI 使用官方 v2.0.1 编程参考；不同主控使用各自资料。回复未附代码时明确提示，已完成历史回复中遗漏的有效代码可恢复为候选版本。
- 本地文件夹保存/加载项目，恢复对话及历史代码，编辑器版本下拉切换。
- 结构设计师：需求分析→确认尺寸→真实 CadQuery 模型，支持整体/爆炸/底壳/上盖/硬件视图、安装面与尺寸调整、检查、STEP/STL导出和独立历史版本。迁入32份几何资料；未知尺寸须补充，当前以矩形带盖 FDM 外壳为范围。
- 结构对话和模型随同一项目保存/加载，文件夹 `structure/` 中可查看模型及报告。按所选硬件生成外壳草案无需AI；自然语言需求使用平台API设置。
- 学习设计师通过「切换视角」选择教师/学生工作台，分别提供教学准备、探究记录、作品说明、反思、海报和赛事资料入口。右侧「选择模板」先预览，确认后替换当前材料版式；选择仅临时保留，刷新重置，生成、保存、导入导出仍待开发。
- 「文件 → 项目程序」在项目子文件夹归档程序及测试记录，保留主控、模块和来源版本信息。
- 页面「API 设置」支持 DeepSeek 和其他 OpenAI 兼容接口。Key 只存本机，不随项目导出；手工编程不需要 Key。
- 浏览器直连 MicroPython 设备，支持 main.py 上传、SHA 回读、运行、停止、终端与文件读取。固件功能需另选厂商镜像、显式确认，尚未完成真实刷写验收。

部署仓库只保留构建及运行必需的源码、依赖锁、启动器、完整硬件资料与来源说明。不包含用户库、Key、设备备份、PPT、开发过程记录、截图、测试产物或桌面应用壳。运行依赖引用的原项目/Artifact/Hardware Skill 代码继续复用，未另造数据仓库。

数据默认在 Windows `%LOCALAPPDATA%\ZhangWen\data` / macOS `~/Library/Application Support/ZhangWen/data`，与程序版本分开。现有源码目录启动仍默认使用该目录的 `.data`；安装器不会自动读取或搬迁旧用户库。迁移、回退及自定义目录见 [部署指南](docs/DEPLOYMENT.md)。

## 已下载源码时

Windows 双击 `start-web.bat`，macOS 执行 `bash start-web.sh`。已有 Node 22+、Python 3.12+ 时也可以 `npm run setup` 后 `npm start`。Intel Mac 使用 Python 3.12/3.13；启动入口会自动选择兼容环境，几何依赖按处理器分别锁定。

自动准备的回退版本为 Node 24.14.0、Python 3.13.7，下载 Node/uv 均核验 SHA-256。不修改系统 PATH、执行策略或凭据，无管理员权限要求。服务只监听 `127.0.0.1`。

[第三方来源与声明](docs/THIRD_PARTY_NOTICES.md)
