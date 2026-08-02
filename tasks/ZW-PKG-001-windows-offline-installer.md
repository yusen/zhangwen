# ZW-PKG-001 - Windows 离线安装包

状态：M6 自动验收通过，`0.1.1` 完整打包与外部安装验收待执行

## 1. 目标

将“掌问”本地桌面应用构建为 Windows NSIS 安装包。安装完成后，目标机器不需要预装 Node.js、pnpm、Python、Rust 或额外下载依赖，即可启动桌面应用并使用已经实现的本地 FastAPI Sidecar、项目数据、内置 Skill 和受控设备能力。

## 2. 范围

- 用 PyInstaller 生成包含 Python 运行时和生产依赖的 Windows Sidecar。
- 将 Sidecar 及其非 Python 资源（Agent 包、Board Skill、提示词和验证 worker）放入 Tauri 资源目录。
- 让生产 Tauri 进程从资源目录启动 Sidecar，并把 SQLite、非敏感配置和设备备份写入用户可写的 `%LOCALAPPDATA%\Zhangwen` 应用数据目录；API Key 继续由 Windows Credential Manager 保存。
- 使用 Tauri CLI 生成 NSIS 安装包，并提供可重复的构建脚本和离线验收脚本。
- 保留 `start-local.bat` 开发入口，不改变真实设备上传、Flash 擦除和固件烧录的确认边界。

## 3. 非目标

- 不实现自动更新、代码签名、公网发布或云同步。
- 不在安装包中预置 API Key、Wi-Fi 密码、真实串口标识或用户数据。
- 不改变设备操作协议；默认仍使用 USB 串口，Flash 擦除和固件烧录仍需显式确认。
- 不覆盖当前进行中的 ZW-AGENT-006 或用户自有的 ZW-UX-003 工作树修改。

## 4. 方案与决策

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| P-01 | Sidecar 运行时 | PyInstaller onedir | 包含 Python 解释器和第三方依赖，避免安装后依赖系统 Python；目录形态便于资源路径和子进程验证 worker 稳定工作。 |
| P-02 | Sidecar 启动 | release 仅解析 bundled resource；debug 构建回退到 `.venv` | 安装态不携带开发机路径；开发态仍可直接运行。 |
| P-03 | 用户数据 | `app.path().local_data_dir()` 通过 `ZHANGWEN_DATA_DIR` 注入 Sidecar | Windows 安装目录可能只读；SQLite、非敏感配置和设备备份留在 `%LOCALAPPDATA%\Zhangwen`，凭据仍在 Windows Credential Manager。 |
| P-04 | 安装器 | Tauri NSIS | 仓库已有 NSIS 目标配置，Windows 用户可直接运行单一安装包。 |
| P-05 | 离线边界 | 构建机可下载构建工具；安装后不联网下载依赖 | 应用运行只使用安装包内前端、Sidecar 和资源；LLM 网络调用仍是用户主动配置的业务能力，不属于依赖下载。 |

## 5. 验收条件

- `pnpm package:windows` 在 Windows 构建机生成 `.exe` NSIS 安装包。
- 解包/安装后的应用目录包含 Sidecar 可执行文件、Python 运行时 DLL、Python 第三方依赖和内置 Markdown/模板资源。
- 在没有 `python.exe`、`node.exe`、`pnpm` 的 PATH 环境中直接启动安装后的 `zhangwen-desktop.exe`（产品显示名为“掌问”），Sidecar 健康检查返回 `status=ok`，桌面 capability token 校验通过。
- 新安装首次启动能在用户数据目录创建 SQLite/config 目录；安装目录不产生可写数据库或设备备份。
- Sidecar 资源加载、代码静态/语法验证、Mock 设备链路和至少一个健康 API 在打包后自动验收通过。
- 安装后运行不因缺少在线下载而退出；网络不可用时只影响主动调用云端 LLM，不影响本地 UI 和本地数据读取。
- 自动测试、构建命令、安装包路径、已知限制和下一步写入 `HANDOFF.md` 与本任务文件。

## 6. 实施里程碑

- [x] M1：构建脚本、PyInstaller spec 和 Tauri 生产 Sidecar 启动。
- [x] M2：资源路径、用户数据目录、CORS 和验证 worker 适配 frozen runtime。
- [x] M3：NSIS 安装包构建与离线 smoke test（自动构建和本机临时安装已通过，干净断网机器验收待完成）。
- [x] M4：文档、交接和残余风险收尾。
- [x] M5：修复安装态硬件目录缺失、问题引导师连带失败与 Sidecar 不可诊断问题，重新打包验收。
- [x] M6：接入用户品牌图标，并让根目录脚本按成功生成次数自动递增 `0.1.x`。

## 6.0A M6 可观察验收（2026-07-20）

- 用户提供、现归类于 `assets/branding/logo.png` 的源文件生成 Windows 多尺寸 `icon.ico`，Tauri 原生标题栏/任务栏、桌面 EXE 和 NSIS
  安装器使用该图标；Web favicon、登录品牌区和桌面顶栏显示同一品牌图标。
- 在当前 `0.1.0` 上直接运行或双击 `build-installer.bat`，无需编辑配置即可尝试生成并验证 `0.1.1`；下次成功为
  `0.1.2`，依次递增。
- 只有构建与 `verify:package:windows` 都成功才保留新版本。构建/验证失败时恢复旧 `tauri.conf.json`；
  `--check`、`--verify-only`、`--install-smoke`、`--desktop-smoke` 不递增。
- 自动测试验证 `0.1.0 → 0.1.1`、跨个位递增、非法版本拒绝和配置写入；默认构建仍不安装、不签名、不发布。

### M6 Decision Log

- `apps/desktop/src-tauri/tauri.conf.json` 是安装器展示版本的单一事实源；Rust/JS 工作区包版本继续表示内部包版本，
  不跟随每次安装器生成，避免无业务意义的 lockfile 扰动。
- “生成次数”按通过既有完整构建和非安装式验证的可交付次数计数，失败尝试不占用版本号。

### M6 Progress 与验证

- [x] 原始执行 `pnpm exec tauri icon logo.png` 生成 Windows ICO 和标准多尺寸 PNG；源文件现位于 `assets/branding/logo.png`，`128x128.png` 视觉复核与原 Logo 一致，
  前端生产构建复制 `public/app-logo.png`。
- [x] 新增 `installer-versioning.ps1`、`build-versioned-installer.ps1` 和无 Pester 依赖的事务测试；并发构建使用独占锁，
  成功保留版本，失败按原始字节恢复配置。
- [x] `cmd /c build-installer.bat --check`：通过，显示当前 `0.1.0`、下一成功版本 `0.1.1`；检查后版本未变化。
- [x] UI Contract 组合 `5 files / 64 passed`；覆盖 Logo 资源、登录页、中央主对话单实例和固定三 Tab。
- [x] `pnpm typecheck`、`pnpm build:desktop`、`git diff --check`：通过；仅保留既有 Vite 大 chunk 与换行提示。
- [x] 针对截图红框补齐原生壳：`build.rs` 显式监听 `icons/icon.ico`，主窗口启动时调用 `set_icon`；
  `cargo check --release` 与 `cargo test --release`（5 passed）通过，UI Contract 追加原生图标接线断言后
  `3 files / 58 passed`。
- [x] `cargo build --release` 通过；从新 `target/release/zhangwen-desktop.exe` 提取的关联图标已视觉复核为蓝底白色
  掌问 Logo，不再是纯蓝方块。没有启动该 EXE 或关闭当前用户窗口。
- [ ] 未运行默认完整安装器构建，因此不能把现有 `0.1.0` 安装包描述为包含新 Logo；下一步由用户直接双击或运行
  `build-installer.bat` 生成并验证 `0.1.1`。

## 6.0 M5 可观察验收（2026-07-18）

- 安装包包含 `bundled-hardware-skills`、`catalog-assets` 和构建时通过统一校验的生产硬件目录快照，不携带 SQLite、凭据或其他 `.data` 用户状态。
- 首次启动将快照中缺失的 Hardware Skill 原子投影到 `%LOCALAPPDATA%\Zhangwen\hardware-skills`；已有同名目录一律保留，不覆盖用户修改。
- 打包态 `/api/hardware` 与 `/api/hardware/skills` 返回非空且达到快照 manifest 的预期数量，媒体可读取，SQLite 投影与包 revision 一致。
- 单个 bundled 硬件资源缺失或损坏时，未选择该硬件的问题引导师上下文降级为无硬件知识，不再返回笼统 `UNKNOWN`；用户已确认硬件仍保持失败关闭。
- Tauri 将 Sidecar stdout/stderr、启动 PID、就绪/超时/退出码写入用户日志目录；健康指示初始状态显示“连接中”，失败状态保留可理解的诊断提示。
- 打包 smoke 覆盖认证、Agent 包、BoardProfile、硬件目录、媒体、问题引导师上下文、SQLite、验证 worker 与设备 helper；不连接真实串口或 Provider。

### M5 Progress

- [x] 完成安装态只读复盘：确认 Agent 包存在；`hardware/bundled-hardware-skills`、`catalog-assets` 和 66 个活动 Hardware Skill 未进入安装包。
- [x] 确认问题引导师失败链：`ContextAssembler` 读取缺失 K10 规格抛出 `FileNotFoundError`，被 chat catch-all 转成 `UNKNOWN`。
- [x] 更新契约/测试与 ExecPlan。
- [x] 实现硬件快照打包、首次启动保守同步与异常降级；66 个活动包已通过构建前统一校验。
- [x] 实现 Sidecar stdout/stderr 与启动事件日志，并将健康指示初始状态改为“本地服务连接中”。
- [x] 完成自动验收、NSIS 重打包和交接。

## 6.1 当前进度

- M1/M2 已完成：Sidecar、资源、frozen worker、`mpremote`/`esptool` helper、用户数据目录和 capability/CORS 边界已实现并有自动测试。
- M3 已完成软件部分：`pnpm package:windows` 已生成 x64 NSIS 安装包；自动 Sidecar smoke、精简 PATH 启动、静默安装/卸载 smoke 已通过。
- M4 已完成：构建信息、离线安装说明、验收记录和最终交接已写入仓库；仅保留干净断网 Windows 外部验收。

## 6.2 Validation Results

- 当前安装器：`掌问_0.1.0_x64-setup.exe`，393,125,574 bytes，SHA-256
  `DD02AD1E43655F3C4274882EE68756E29A3D6632B7FC12A01593EB44A9D4AB61`，未签名。
- 当前 Sidecar：x64 onedir，payload 819,166,272 bytes，exe SHA-256
  `D6C1657489F0AF5EFD59CEC0550EE190F23F3C15C9DE17320FEDF45F838CEE43`。
- `pnpm verify:package:windows` 通过：health、capability、认证、Agent/BoardProfile、66 个硬件组件与 Skill、
  硬件媒体、问题引导师上下文、SQLite、静态/语法 worker、`mpremote`、`esptool`、manifest 和构建路径扫描均通过。
- `scripts-dev/verify-windows-package.ps1 -InstallSmoke` 通过：临时安装包中的 Sidecar
  在无 Node/Python PATH 下创建 SQLite/config，并通过 health 和 capability 验证后卸载清理。
- `scripts-dev/verify-windows-package.ps1 -DesktopSmoke` 通过：已安装的桌面 EXE 启动包内
  Sidecar，health=`ok`，并在 `%LOCALAPPDATA%\Zhangwen` 创建 SQLite/config，随后卸载清理。
- 端口冲突 smoke 通过：临时占用 8100 时桌面进程退出码为 `101`，没有启动包内
  Sidecar，也没有创建用户数据。
- 临时安装启动通过：仅保留 Windows 系统目录的 PATH 下，已安装 EXE 拉起 Sidecar，
  health=`ok`，SQLite 创建于用户数据目录；卸载后无残留进程或卸载登记。
- `cargo fmt --check` 因 toolchain 未安装 `rustfmt` 组件未执行成功；`cargo check`、
  TypeScript typecheck、contracts build 和打包构建均通过。

## 6.3 Deliverables

- `scripts-dev/build-windows-sidecar.ps1`
- `scripts-dev/test-packaged-sidecar.ps1`
- `scripts-dev/build-windows-package.ps1`
- `scripts-dev/verify-windows-package.ps1`
- `apps/desktop/src-tauri/resources/sidecar/zhangwen-sidecar/`
- `apps/desktop/src-tauri/target/release/bundle/nsis/掌问_0.1.0_x64-setup.exe`
- `docs/WINDOWS_INSTALLER.md`
- `docs/reports/WINDOWS_INSTALLER_BUILD_INFO.md`
- `docs/reports/WINDOWS_INSTALLER_ACCEPTANCE.md`

## 6.4 Outcome & Remaining Risk

安装后本地运行时不再依赖 Node.js、pnpm、Python、Rust 或在线依赖下载。云端 LLM
仍需要用户主动配置网络和凭据；真实 USB 串口、Flash 擦除和固件烧录仍按既有确认边界执行。
若 8100 已被未知本地进程占用，或 Sidecar 未能从包内资源就绪，桌面启动会明确失败，
不会连接到未知服务或显示不可用窗口。
当前安装器未签名，且尚未在干净断网 Windows Sandbox/VM 完成 WebView2 离线安装验收，
因此状态保持“外部安装验收待完成”，不能当作公开发布包。

## 7. 验证命令

- `pnpm --filter @zhangwen/contracts build`
- `pnpm --filter @zhangwen/desktop typecheck`
- `.venv\\Scripts\\python.exe -m pytest services/local-api/tests/test_packaged_runtime.py -q --rootdir services/local-api`
- `.venv\\Scripts\\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`
- `pnpm package:windows`
- `pnpm verify:package:windows`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev/verify-windows-package.ps1 -InstallSmoke`
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts-dev/verify-windows-package.ps1 -DesktopSmoke`

## 8. 安全记录

- 构建和 smoke test 不连接真实串口、不上传文件、不擦除 Flash、不烧录固件。
- 不安装或运行来自用户项目的任意 Python；PyInstaller 只封装仓库 Sidecar。
- 安装包扫描不得包含 `.env`、API Key、Bearer token、真实串口标识、个人绝对路径或 `.data` 数据库。

## 9. 2026-07-15 当前工作树重打包记录

- 基于当前工作树生成 `apps/desktop/src-tauri/target/release/bundle/nsis/掌问_0.1.0_x64-setup.exe`。
- 安装包大小：`389646128` bytes；SHA-256：`59E3AE325C55831569809B938781466F4380D9B00302DF0FEB470322B9194868`。
- `pnpm verify:package:windows`、`verify-windows-package.ps1 -InstallSmoke` 和 `-DesktopSmoke` 均通过；安装后桌面程序、包内 Sidecar、health、capability、SQLite/config 初始化和卸载清理均通过。
- 打包前发现 K10 Board Skill 的 `manifest.json` 已记录新版 `tests/syntax_check.py`，但外层 `CHECKSUMS.sha256` 漏同步 manifest 摘要；仅修正该摘要后，BoardProfile/BoardSkill `8 passed`。
- 当前包未签名，Windows SmartScreen 可能提示未知发布者；包内包含 WebView2 offline installer，不依赖在线下载、Node.js 或 Python。

## 10. 2026-07-18 当前工作树重打包记录

- 用户要求立即打包后，基于分支 `codex/zw-005-016-autonomous`、HEAD `291ff20` 和当前混合工作树重新生成安装器；未清理、暂存或覆盖其他任务修改。
- 首次 `pnpm package:windows` 在 Sidecar smoke 中因新增认证门禁返回 `AUTH_REQUIRED`；已更新
  `scripts-dev/test-packaged-sidecar.ps1`，在隔离临时数据目录注册一次性本地账号并携带会话验证受保护资源。
- 完整重跑 `pnpm package:windows` 通过。安装器大小 `389935857` bytes，SHA-256
  `F5514DF2BC69D5F0D12D40DE3661571148674677B8B4458BD03505389D5D7DBD`；Sidecar payload
  `815025358` bytes，exe SHA-256 `F9B6BB026E67B9C120EA5E1A1D215378B655D3DF65C710AB7B3CF59FEAEECE97`。
- `pnpm verify:package:windows` 与 `verify-windows-package.ps1 -InstallSmoke` 均通过；精简 PATH 下的
  health、capability、本地认证、受保护资源、SQLite/config、验证 worker、设备 helper、静默安装和卸载清理通过。
- 本轮未运行完整桌面 `-DesktopSmoke`，未操作真实设备；安装器仍未签名，干净断网 Windows 外部验收仍待完成。

## 11. 2026-07-18 M5 安装态硬件与诊断修复记录

- 根因是旧包遗漏 Hardware Skill 资源；问题引导师读取缺失 K10 规格后抛出 `FileNotFoundError`，与硬件库为空同源。
- 构建前校验并打入 66 个活动 Hardware Skill；首次启动仅原子安装缺失包并同步 SQLite，同名用户包不覆盖。
- package smoke 已验证 66 个组件、66 个 Skill、硬件媒体和无 Provider 的问题引导师上下文。
- 新安装器 `393125574` bytes，SHA-256
  `DD02AD1E43655F3C4274882EE68756E29A3D6632B7FC12A01593EB44A9D4AB61`；Sidecar payload
  `819166272` bytes，exe SHA-256 `D6C1657489F0AF5EFD59CEC0550EE190F23F3C15C9DE17320FEDF45F838CEE43`。
- `pnpm package:windows`、`pnpm verify:package:windows`、Python 定向 25 项、UI 合同 53 项、Rust 2 项和
  `pnpm build:desktop` 通过。API 全量在 10 分钟上限被终止；前端全量有 4 个范围外既有失败。
- 当前用户已有安装和真实应用数据，本轮未运行会安装/卸载的 smoke；不得为测试覆盖现有用户状态。
