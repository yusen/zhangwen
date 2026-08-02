# Windows 安装包验收记录

任务：`ZW-PKG-001`

当前结论：自动验收通过；干净断网 Windows 外部验收待完成。

安装器：`掌问_0.1.0_x64-setup.exe`

SHA-256：`2635CD2658C23B1E92E36BF55BCF1FBFD5AF1D2A36B6729D9ADF5395BC1783C5`

## 已完成的自动/本机验收

- [x] Windows x64 NSIS 安装器生成成功。
- [x] Tauri 配置使用 `offlineInstaller`，并禁止不安全降级。
- [x] Sidecar 在剥离 Node.js、Python 和 pnpm 的 PATH 环境中启动，`/api/health` 返回 `status=ok`。
- [x] capability token、Agent 包、BoardProfile、Board Skill 和项目 API 在打包 Sidecar 中可用。
- [x] 静态检查、语法检查、`mpremote version` 和 `esptool version` helper 通过。
- [x] 临时目录静默安装后包含桌面 EXE 和 Sidecar（174 个文件）；启动已安装 EXE 后 health 返回 `ok`，用户数据目录创建 SQLite。
- [x] `-InstallSmoke` 自动临时安装后，包内 Sidecar 在无 Node/Python PATH 下通过 health 与 capability，并初始化 SQLite/config；卸载后清理。
- [x] `-DesktopSmoke` 自动临时安装后，`zhangwen-desktop.exe` 启动包内 Sidecar，health 返回 `ok`，并在 `%LOCALAPPDATA%\Zhangwen` 初始化 SQLite/config；卸载后清理。
- [x] 临时占用 8100 时，桌面进程以退出码 `101` 失败，未启动包内 Sidecar，也未创建用户数据。
- [x] 临时安装已通过自带卸载程序清理；未留下测试进程或卸载登记。
- [x] manifest 产品名、版本、安装包大小和哈希与实际产物一致。
- [x] release/Sidecar 二进制不含仓库根路径、当前用户目录、`.env`、SQLite 或凭据标识。
- [x] 新增本地认证门禁后，打包态 smoke 会在隔离数据目录创建一次性账号并验证会话及受保护资源；临时数据随 smoke 清理。
- [x] 构建时统一校验并打入当前共享工作树的 67 个活动 Hardware Skill；首次启动仅安装缺失包，不覆盖同名用户包。
- [x] 打包态 `/api/hardware` 与 `/api/hardware/skills` 均返回 67 项，硬件媒体可读取，问题引导师上下文可装载公共硬件知识。
- [x] 安装态冷启动使用 120 秒有限就绪预算；Windows 安全扫描导致 Hardware Skill 临时目录短锁时，原子替换做有限退避并保持最终失败关闭。
- [x] Sidecar stdout/stderr 与 PID、就绪、超时、提前退出写入用户日志；前端首次探测显示“本地服务连接中”。

## 离线行为边界

- [x] 本地 UI、内置资源、本地 SQLite 读取和代码检查不依赖运行时下载。
- [ ] 在干净且断网的 Windows Sandbox/VM 中验证 WebView2 离线安装器实际安装（当前机器已有 WebView2，不能代替该外部验收）。
- [ ] 断网时手工确认云端 LLM 调用给出可理解的网络/Provider 错误；本地 UI 和数据仍可用。

## 安全和设备边界

- [x] 自动验证只使用 Mock/本地临时工作区，不连接真实串口。
- [x] 未上传设备文件、未重启真实设备、未擦除 Flash、未烧录固件。
- [ ] 真实 ESP32/K10 串口发现、备份、USB 上传和回读验证由人工在有设备时执行。
- [ ] 真实 Flash 擦除/固件烧录必须继续保留板型、固件、影响、备份和确认步骤。

## 发布前待办

1. 在干净断网 Windows 环境安装并记录 WebView2、首次启动、重装/卸载和数据保留结果。
2. 使用组织代码签名证书重签安装器，并重新记录签名和哈希；未签名包不作为公开发布包。
3. 完成真实设备人工验收后，再单独记录设备结果，不把本地 Mock 结果当成硬件成功。
