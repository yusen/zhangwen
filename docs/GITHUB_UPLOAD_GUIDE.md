# 掌问 GitHub 上传指南

本仓库的可上传源码快照会生成在仓库根目录下的 `GitHub_Upload_Zhangwen/`。该目录本身已被
`.gitignore` 排除，目的是让它作为独立上传源，而不会被嵌套提交回当前工作区。

## 包含内容

- 当前工作区中所有已由 Git 追踪的产品源代码、测试、共享契约、构建配置、桌面端资源、文档、
  任务记录、开发脚本、模板和受控参考资料；
- 当前尚未提交的工作区修改也会按文件当前内容写入快照；
- `.gitignore`、`.gitattributes`、`.npmrc`、`README.md` 与锁文件，保证新仓库可以复现依赖解析规则。

## 明确排除

- Git 元数据和本机 Codex 配置：`.git/`、`.codex/`；
- 依赖、虚拟环境、构建与测试缓存：`node_modules/`、`.pnpm-store/`、`.venv/`、`dist/`、`target/`、
  `coverage/`、`.pytest_cache/`；
- 本地项目数据、日志、临时文件、导出物和本地参考空间：`.data/`、`.tmp/`、`outputs/`、
  `references/local/`、`*.log`；
- 实际环境变量、API Key、Wi-Fi 凭据、真实串口标识、设备日志与任何其他用户私有数据。

仓库中的 `.env.example` 是保留的公开配置模板：其中只能包含 `change-me`、`replace-with...` 等
占位值，不能填入真实凭据。

上传前已对已追踪文件执行高置信度凭据扫描，未发现私钥或常见 API/GitHub/Google/Slack Token
字面量；公开前仍应由仓库拥有者再次检查新增文件和 GitHub 的 secret scanning 提示。

## 上传步骤

1. 在 GitHub 创建一个空仓库；不要勾选自动创建 README、LICENSE 或 `.gitignore`。
2. 打开 `GitHub_Upload_Zhangwen/`，确认其中只有本指南列出的源代码和文档。
3. 在该目录执行：

   ```powershell
   git init
   git add .
   git status
   git commit -m "Initial Zhangwen Creator source snapshot"
   git branch -M main
   git remote add origin <你的 GitHub 仓库地址>
   git push -u origin main
   ```

4. 推送前阅读 `git status`；若出现 `.env`、数据库、日志、设备导出或任何凭据文件，停止并移除它们。

## 许可证

当前仓库没有可公开授权的 `LICENSE` 文件。上传到 GitHub 不会自动授予他人使用、修改或分发权。
请在公开前由项目拥有者决定是否添加 MIT、Apache-2.0、GPL-3.0 或保留专有授权；不要在未确认授权
策略前替项目添加许可证。

## 当前验证状态

源码快照对应 `ZW-CREATOR-001` 的当前工作区：Creator M0–M7 与 M8.1–M8.5 软件路径已完成；
M8.6 真人/真机/安装包验收和 M8.7 发布收口仍未完成。上传源代码不等同于已完成公开发布或真机验收。

本次快照包含 1,132 个文件、约 21.88 MiB；每个文件已与源工作区逐个比对 SHA-256，未发现差异。
