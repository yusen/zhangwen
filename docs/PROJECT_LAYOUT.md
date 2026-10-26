# 项目目录

日常使用安装命令、桌面/应用程序入口，或源码根目录的 `start-web.bat` / `start-web.sh`。启动时检测已有环境和依赖，缺失才下载。

## 平台源码与资源

| 目录 | 内容 |
| --- | --- |
| `apps/web/src/` | 三师工作台、编辑器、预览与浏览器 Web Serial |
| `packages/contracts/src/` | 前后端共享的 TypeScript 数据契约 |
| `services/local-api/zhangwen/web/` | 本机 API、项目与历史、AI 接口及设计生成 |
| `services/local-api/zhangwen/` 其他子目录 | 运行依赖的原项目存储、硬件资料与专家能力 |
| `services/structure-cad/` | 建模引擎与依赖，硬件事实读取统一资源目录 |
| `resources/hardware-skills/<skillName>/` | 单模块电气/接线/编程/机械/模型与图片，见 [资源说明](../resources/README.md) |
| `resources/structure-parts/<profileId>/` | 尚未准确绑定电子模块的结构参考 |
| `resources/hardware-resources.json` | 文件路径/摘要与明确组件关联 |
| `resources/` 其他目录 | 固件、字体及来源/许可 |
| `scripts/` | 安装、环境检测、启动及 Windows/macOS 应用入口 |
| `docs/` | 部署说明、功能边界与第三方声明 |

`dist/`、`node_modules/`、`.venv/` 及本机运行时在安装/启动时生成，不上传 GitHub。

## 用户内容

一条命令安装时，数据和程序版本分开：Windows 为 `%LOCALAPPDATA%\ZhangWen\data`，macOS 为 `~/Library/Application Support/ZhangWen/data`。直接运行源码默认使用源码根目录 `.data/`，可通过启动配置指定其他目录。

API 设置、数据库、对话与历史产物、本机修改的案例均属于用户数据。工作台选定的项目文件夹另存 `zhangwen.project.json`、`main.py`、程序及结构子目录。建议将项目放在自己的文档目录，避免与平台程序版本混淆。

项目保存时，历史文件按用途和版本输出，例如：

```text
我的项目/
  main.py                          当前已保存程序入口
  zhangwen.project.json             项目、对话与历史快照
  硬件/
    模块名称_skillName/
      资料版本_内容摘要/
        模块资料.json               组件ID和原资料修订
        约束与参考/                 电气、接线、安全与来源
        编程/                      案例与已有主控API
        结构/                      机械档案、外形、模型；缺项有说明
  代码/
    已保存版本/V002_空心圆/main.py
    AI候选/V003_空心圆改进/main.py
  结构/
    3D造物/V004_主控外壳/model.step
    激光造物/V005_灯罩/cut.svg
```

名称沿用对应版本的用途，清理路径禁用字符并限制长度；版本号用于区分同名修改。结构文件不再以内部任务ID作为可见目录名。同一版若引用多个同名部件文件，会放入“文件组01”等子目录，保留原文件名供预览与加工工具使用。AI候选单独归档，不自动成为根目录当前程序。

硬件目录归档当前已保存选择的模块与结构历史中明确关联的结构件；同一模块的约束、编程和机械资料放在一起。资料版本按内容摘要区分，更新后新增，旧副本保留。副本不自动导入硬件库、不执行参考模型、不进入设备上传清单。缺少机械资料时明确说明。项目装配与激光图涉及多个模块，仍按项目结构版本保存。详见 [硬件约束审查](HARDWARE_RESOURCE_LAYOUT_20261025.md)。

旧项目的 `structure/随机ID/…` 仍可加载；下一次成功同步会额外生成上述分类目录，旧目录与用户文件保持。要获得没有旧目录的干净副本，可用「项目 → 另存到文件夹…」保存到新文件夹。`zhangwen.project.json` 仍是完整恢复对话、模型和版本的依据；浏览历史文件时如需另行编辑，先复制文件，避免修改历史副本后触发同步冲突。手工保存的项目程序仍沿用 `programs/` 档案入口。

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
