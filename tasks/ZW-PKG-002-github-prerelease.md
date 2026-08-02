# ZW-PKG-002 - GitHub 公开预发布

状态：已完成（公开仓库、`v0.1.1` Pre-release、唯一附件和远端 digest 复核通过）

## 1. 目标

在不公开开发源码和混合工作树历史的前提下，创建公开 GitHub 仓库 `yusen/zhangwen-desktop`。仓库 `main`
只包含一份面向用户的 `README.md`；Windows x64 安装器作为 `v0.1.1` GitHub Pre-release 附件发布。

## 2. 用户授权与发布边界

- 2026-07-20 用户明确授权仓库公开。
- 仓库名固定为 `zhangwen-desktop`。
- 未签名 `0.1.1` 只作为预发布测试版，不标记稳定正式版。
- 公开发布属于高风险外部操作；上述三项授权已在执行前取得。

## 3. 方案

1. 对现有安装器运行 `build-installer.bat --verify-only`，核对包内 Sidecar、Manifest、大小、SHA-256 和签名状态。
2. 在被主仓库忽略的 `outputs/github/zhangwen-desktop` 创建独立 Git 仓库，首个提交只暂存 `README.md`。
3. 通过本机 Git Credential Manager 的 `yusen` 账号调用 GitHub 官方 API 创建公开仓库；凭据只在进程内存使用，
   不打印、不写入文件。
4. 推送 `main` 后创建 `v0.1.1` Pre-release，上传 `掌问_0.1.1_x64-setup.exe` 作为唯一自定义附件。
5. 读取远端仓库和 Release API，复核可见性、默认分支、文件清单、prerelease 属性、附件名与大小。

## 4. 发布信息

- 安装器：`apps/desktop/src-tauri/target/release/bundle/nsis/掌问_0.1.1_x64-setup.exe`
- 大小：`393763193` bytes
- SHA-256：`1E76923EA3D2BDD24A3200946D2105261E5638FA863CDB40B907A78D8E2201B6`
- Authenticode：`NotSigned`
- 目标标签：`v0.1.1`
- 目标状态：Pre-release

## 5. 验收

- [x] `build-installer.bat --verify-only` 退出码 0；Packaged Sidecar smoke 通过。
- [x] 大小和 SHA-256 与 `package-manifest.json` 一致，签名状态明确为 `NotSigned`。
- [x] README 明示预发布、SmartScreen、系统要求、哈希、数据目录、联网边界和设备风险。
- [x] GitHub 仓库公开，默认分支 `main`，树中只有 `README.md`。
- [x] `v0.1.1` 的 `draft=false`、`prerelease=true`，且唯一自定义附件名称和大小正确。
- [x] 公开下载页与 README 链接可访问；GitHub 远端 digest 与本地 SHA-256 一致。

## 8. Outcome

- 仓库：`https://github.com/yusen/zhangwen-desktop`
- Release：`https://github.com/yusen/zhangwen-desktop/releases/tag/v0.1.1`
- 下载：`https://github.com/yusen/zhangwen-desktop/releases/download/v0.1.1/Zhangwen_0.1.1_x64-setup.exe`
- 独立发布仓库 `main` HEAD：`1f3d3e8`；公开树只有 `README.md`。
- GitHub Release API 复核：`draft=false`、`prerelease=true`、附件数 `1`、附件状态 `uploaded`、大小
  `393763193` bytes、digest
  `sha256:1e76923ea3d2bdd24a3200946d2105261e5638fa863cdb40b907a78d8e2201b6`。
- GitHub 会规范化非 ASCII 附件名，因此最终统一使用 ASCII 名称 `Zhangwen_0.1.1_x64-setup.exe`；首次生成的残缺名称附件
  已在正确附件上传并校验后移除。

## 6. 风险与禁止事项

- 不推送当前开发仓库 origin，不复制其 `.git` 历史，不使用 `git add -A`。
- 不上传源码、用户项目、数据库、日志、凭据、真实串口标识、`.data` 或其他 `outputs`。
- 不执行真实 Provider、串口上传、设备复位、Flash 擦除或固件烧录。
- 干净断网 Windows 外部验收仍待完成；未签名包可能触发 SmartScreen，不能描述为稳定正式版。

## 7. Decision Log

- 使用 GitHub Release 而非普通 Git/LFS：安装器约 394 MB，超过 GitHub 普通 Git 单文件限制；Release 更符合二进制分发语义。
- 使用独立仓库而非 orphan 分支：避免当前大量未提交修改、内部文档和开发历史进入公开面。
- 公开仓库不添加 LICENSE、Logo 或安装器文件；保持用户要求的单一说明文档，二进制只存在于 Release。
