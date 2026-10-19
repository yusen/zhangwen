# 项目目录

日常使用安装命令、桌面/应用程序入口，或源码根目录的 `start-web.bat` / `start-web.sh`。启动时检测已有环境和依赖，缺失才下载。

## 平台源码与资源

| 目录 | 内容 |
| --- | --- |
| `apps/web/src/` | 三师工作台、编辑器、预览与浏览器 Web Serial |
| `packages/contracts/src/` | 前后端共享的 TypeScript 数据契约 |
| `services/local-api/zhangwen/web/` | 本机 API、项目与历史、AI 接口及设计生成 |
| `services/local-api/zhangwen/` 其他子目录 | 运行依赖的原项目存储、硬件资料与专家能力 |
| `services/structure-cad/` | 结构几何资料与建模依赖 |
| `resources/` | 硬件案例、图片、官方固件、字体及来源/许可 |
| `scripts/` | 安装、环境检测、启动及 Windows/macOS 应用入口 |
| `docs/` | 部署说明、功能边界与第三方声明 |

`dist/`、`node_modules/`、`.venv/` 及本机运行时在安装/启动时生成，不上传 GitHub。

## 用户内容

一条命令安装时，数据和程序版本分开：Windows 为 `%LOCALAPPDATA%\ZhangWen\data`，macOS 为 `~/Library/Application Support/ZhangWen/data`。直接运行源码默认使用源码根目录 `.data/`，可通过启动配置指定其他目录。

API 设置、数据库、对话与历史产物、本机修改的案例均属于用户数据。工作台选定的项目文件夹另存 `zhangwen.project.json`、`main.py`、程序及结构子目录。建议将项目放在自己的文档目录，避免与平台程序版本混淆。

`.backups/`、`.device-backups/` 是本机备份。整理和发布不移动或清空已有用户数据；迁移与回退见 [部署指南](DEPLOYMENT.md)。

## 完整开发工作区

以下内容只在开发工作区保留，不进入部署仓库：

| 目录 | 用途 |
| --- | --- |
| `apps/web/e2e/`、`apps/web/tests/`、`services/local-api/tests/`、`scripts/tests/` | 自动化测试 |
| `scripts/verification/` | 专项验证工具；其中 `verify-real-board.mjs` 操作真实设备，须明确安排设备验收 |
| `scripts/release/` | 白名单部署导出，不自动提交或推送 Git |
| `tasks/`、`CURRENT_TASK.md`、`HANDOFF.md` | 计划与交接 |
| `outputs/`、`imports/` | 演示输出及输入副本 |
| `.test-data/`、`test-results/`、`.runtime/` | 隔离测试、验证报告和运行记录 |
| `.publish/` | 每次新建的部署候选目录 |

所有验证工具从项目根目录运行。旧记录中 `scripts/verify-*.mjs` 对应现路径 `scripts/verification/verify-*.mjs`，历史记录保留原文。部署导出入口改为：

```powershell
python scripts/release/export-deployment.py .publish/release-candidate
```

使用已准备好的开发 Python/Node 环境，目标必须是 `.publish/` 下尚不存在的目录。导出收集运行依赖、离线精简测试依赖锁并生成 `DEPLOYMENT.sha256`；不覆盖旧候选，不包含用户数据、密钥、测试及开发过程资料。发布前仍需隔离构建与检查。
