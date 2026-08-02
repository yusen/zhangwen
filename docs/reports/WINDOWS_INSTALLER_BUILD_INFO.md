# Windows 安装包构建信息

生成时间：2026-07-19（构建脚本 manifest：`2026-07-19T14:13:46.3054029Z`）

任务：`ZW-STABILITY-002`（沿用 `ZW-PKG-001` 打包契约）

分支：`codex/zw-005-016-autonomous`

构建时 HEAD：`291ff20`（工作树另有未提交的并行任务修改）

## 工具和目标

| 项目 | 值 |
|---|---|
| 产品 | 掌问 |
| 版本 | 0.1.0 |
| 目标 | `x86_64-pc-windows-msvc` |
| 安装器 | Tauri NSIS，current-user |
| WebView2 | `offlineInstaller` |
| PyInstaller | 6.21.0 |
| Python | 3.13.3 |
| Tauri CLI | 2.11.4 |
| Rust Tauri crate | 2.11.5 |

## 命令结果

| 命令 | 结果 |
|---|---|
| `pnpm --filter @zhangwen/contracts build` | 通过 |
| `pnpm package:windows` | 通过，生成 NSIS 和 manifest |
| `pnpm verify:package:windows` | 通过；Sidecar smoke、manifest、路径扫描和签名状态检查通过 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev\verify-windows-package.ps1 -InstallSmoke` | 通过；临时安装、包内 Sidecar health/capability/SQLite/config 和卸载清理通过 |
| `powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev\verify-windows-package.ps1 -DesktopSmoke` | 通过；已安装桌面 EXE 启动包内 Sidecar、初始化 `%LOCALAPPDATA%\Zhangwen`、健康检查和卸载清理通过 |
| 8100 端口冲突 smoke | 通过；桌面退出码 `101`，未启动 Sidecar，未创建用户数据 |
| `.venv\Scripts\python.exe -m pytest services/local-api/tests/test_packaged_runtime.py -q --rootdir services/local-api` | 通过 |
| `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml` | 通过 |
| `pnpm --filter @zhangwen/desktop typecheck` | 通过 |
| 后端完整分组回归 | 655 项全部覆盖；发现项修复后复测通过 |
| UI 完整回归 | 32 files / 200 passed |
| `cargo test --release` | 5 passed |
| `git diff --check` | 通过 |

## 产物

| 产物 | 大小 | SHA-256 | 签名 |
|---|---:|---|---|
| `apps/desktop/src-tauri/target/release/bundle/nsis/掌问_0.1.0_x64-setup.exe` | 393,644,568 bytes | `2635CD2658C23B1E92E36BF55BCF1FBFD5AF1D2A36B6729D9ADF5395BC1783C5` | `NotSigned` |
| `apps/desktop/src-tauri/resources/sidecar/zhangwen-sidecar/zhangwen-sidecar.exe` | 28,047,066 bytes | `10C06C61B66C78AB45FF57E89E08F2C4B1B3BA408387FFFA384C30BBA7458F9A` | 未签名 |

Sidecar onedir payload 总大小为 819,717,498 bytes。`package-manifest.json` 记录了同一安装器哈希、Sidecar 哈希和 `offlineInstaller` 配置。构建前当前共享工作树的 67 个活动 Hardware Skill 全部通过统一校验，打包 smoke 验证其 API 数量、媒体和问题引导师上下文。

## 发布边界和安全检查

- Tauri release 只从 bundled resource 启动 Sidecar；`.venv` 回退仅编译进 debug 构建。
- 端口冲突、资源缺失、用户数据目录失败或 Sidecar 就绪失败会中止桌面启动，避免窗口连接到未知或不可用服务。
- Rust release EXE 和 Sidecar 已扫描，不含仓库根路径 `D:\ZW_V1` 或构建用户目录。
- Sidecar 不含 `.env`、SQLite/WAL、`__pycache__`、`.pyc`/`.pyo` 或真实凭据。
- 构建和 smoke 不连接真实串口，不上传文件，不擦除 Flash，不烧录固件。
- 安装器未签名，可能触发 SmartScreen；代码签名、自动更新、MSI 和公开发布不在本任务范围。
- 云端 LLM 仍需要用户配置网络和 Provider 凭据；这不是安装依赖下载。

## 待完成的外部验证

在干净、断网、没有 Node/Python 的 Windows Sandbox 或可回滚虚拟机中安装并启动，确认离线 WebView2 安装、首次运行、卸载和 `%LOCALAPPDATA%\Zhangwen` 数据保留。真实设备串口、上传、Flash 擦除和固件烧录仍只允许人工确认后执行。

本轮没有在当前用户环境重复运行安装/桌面 smoke，因为机器已有掌问安装和真实用户数据；上表的安装 smoke 结果属于此前同一打包契约记录。当前 `ZW-STABILITY-002` 产物已通过 Sidecar、包结构、哈希、路径和签名状态独立验证，安装态仍需在干净环境复核。
