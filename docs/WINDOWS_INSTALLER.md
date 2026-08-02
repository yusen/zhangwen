# Windows 安装包

掌问的 Windows 发布包是 x64 NSIS 安装器：

`apps/desktop/src-tauri/target/release/bundle/nsis/掌问_0.1.x_x64-setup.exe`

Windows 原生标题栏/任务栏、桌面 EXE、NSIS 安装器、浏览器标签、登录页和工作台顶栏统一使用 `assets/branding/logo.png`
生成的掌问品牌图标。原生壳重启后才会更新标题栏和任务栏；Vite 页面热更新不会替换正在运行的 EXE 图标。

安装包内包含 Tauri 桌面壳、Vite 前端、PyInstaller Sidecar、Python 运行时、生产 Python 依赖、Agent/Board Skill、经统一校验的 66 个 Hardware Skill 只读快照及媒体、静态/语法验证 worker、`mpremote` 和 `esptool`。安装完成后不需要 Node.js、pnpm、Python、Rust 或再次下载本地运行依赖。

## 系统要求

- Windows x64。
- 当前安装器使用 Tauri NSIS `currentUser` 模式，不需要管理员权限。
- 安装器配置了 WebView2 `offlineInstaller`。构建机需要联网获取离线 WebView2 安装器；目标机安装时不应再为 WebView2 下载运行依赖。
- USB 串口设备可能仍需要 Windows 本身提供的 USB-串口驱动；驱动不包含在本应用依赖包中。

## 安装、启动和卸载

1. 双击 `掌问_0.1.0_x64-setup.exe`，按安装器提示完成当前用户安装。
2. 从开始菜单或安装目录启动 `zhangwen-desktop.exe`。窗口标题和产品界面显示“掌问 — AI 创客工程工作台”。
3. 卸载使用 Windows“已安装的应用”或安装目录中的 `uninstall.exe`。卸载不会删除 `%LOCALAPPDATA%\Zhangwen` 中的项目数据。

首次启动时，Tauri 从安装资源目录启动 `sidecar\zhangwen-sidecar\zhangwen-sidecar.exe`。Sidecar 使用随机 capability token 与桌面壳握手，只监听本机回环地址。它会原子安装用户目录中缺失的 Hardware Skill 并建立 SQLite 投影；已有同名用户包不会被覆盖。

## 数据和凭据

- SQLite、非敏感配置、Hardware Skill、Sidecar 启动日志和设备备份：`%LOCALAPPDATA%\Zhangwen`。
- `logs\sidecar-startup.log` 记录 Python 初始化；`logs\sidecar-process.log` 记录 Tauri 启动命令、PID、就绪、超时和提前退出，并收集 Sidecar stdout/stderr。
- API Key 不写入安装目录、SQLite、项目包、日志或前端存储；Windows 上由 Credential Manager 保存。
- 安装目录用于程序和只读资源，不应手工写入项目数据库或设备备份。

## 离线边界

离线可用的部分包括前端 UI、本地项目数据读取、内置 Agent/Board Skill 资源、代码静态/语法检查、Mock 设备链路和本地设备工具的启动边界。应用不会因为缺少 Node.js、Python 或在线依赖下载而退出。

云端 LLM 对话仍是用户主动配置的业务能力，需要可用网络和合法 Provider 凭据；网络断开时只影响该调用，不应影响本地 UI 或已保存数据。真实串口上传使用 USB 串口，Flash 擦除和固件烧录仍需明确确认，安装器不会自动执行这些操作。

未签名的本地构建包可能触发 Windows SmartScreen。发布前应使用组织证书签名并在受控机器上做最终验收；本任务不包含代码签名、自动更新或公开发布。

## 构建和验证

在仓库根目录双击或运行一键脚本。默认自动递增 `0.1.x`，依次构建并验证，不执行安装：

```bat
build-installer.bat
build-installer.bat --check
build-installer.bat --verify-only
```

`apps/desktop/src-tauri/tauri.conf.json` 是安装器版本的单一事实源。当前为 `0.1.0` 时，下一次成功运行根脚本生成
`0.1.1`，再下一次成功生成 `0.1.2`。只有构建和非安装式验证都通过才保留新版本；失败会恢复旧版本，
`--check`、`--verify-only`、`--install-smoke` 和 `--desktop-smoke` 都不递增。日常打包不需要手工修改 JSON、Cargo 或
package 文件。

`--install-smoke` 与 `--desktop-smoke` 会执行隔离安装/卸载或启动已安装桌面，仅在明确需要且满足无既有安装、端口和数据边界时手动使用。底层固定版本构建命令为：

```powershell
pnpm package:windows
pnpm verify:package:windows
# 可选：临时安装、启动和卸载 smoke（要求当前用户没有已安装的“掌问”）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev\verify-windows-package.ps1 -InstallSmoke
# 可选：临时安装并启动完整桌面应用（要求 8100 空闲，且没有现有应用/数据）
powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev\verify-windows-package.ps1 -DesktopSmoke
```

底层命令不会自动递增版本，主要用于开发诊断；日常交付统一使用根目录 `build-installer.bat`。

构建脚本会先构建 contracts，逐包校验生产 Hardware Skill 快照，使用 PyInstaller 生成 Sidecar，运行无 Node/Python PATH 的 Sidecar smoke，再生成 NSIS 安装器和 `package-manifest.json`。Smoke 同时校验认证、Agent/BoardProfile、硬件目录数量、媒体、问题引导师上下文、SQLite 和本地工具。验证脚本还会校验 manifest、安装包 SHA-256、离线 WebView2 配置、资源 Sidecar、用户目录边界和 release 二进制中的构建机路径。`-InstallSmoke` 会在隔离临时目录中静默安装、验证包内 Sidecar 的 health、capability、SQLite/config 初始化，再卸载清理。`-DesktopSmoke` 还会启动已安装的 `zhangwen-desktop.exe`，验证它从包内启动 Sidecar，并在 `%LOCALAPPDATA%\Zhangwen` 初始化 SQLite/config；该检查要求 8100 空闲且当前用户没有既有掌问安装或数据。

最终安装器仍应在干净 Windows 虚拟机或 Windows Sandbox 中断网验证安装、首次启动、卸载和数据保留；这一步不由自动脚本伪造为已完成。
