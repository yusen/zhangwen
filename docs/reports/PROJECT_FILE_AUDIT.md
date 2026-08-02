# 掌问项目文件审计（2026-07-19）

## 结论

项目源码目录划分整体合理；当前磁盘占用和 Git 噪声主要来自可再生构建产物、离线 Sidecar 打包目录、开发输出和本地参考仓库，不是业务源码重复。此次采用可逆整理：移动根目录临时 QA 脚本、补充忽略规则并记录清理入口，没有删除参考资料、用户输出、应用数据或构建缓存。

## 根目录分类

| 分类 | 路径 | 处理原则 |
| --- | --- | --- |
| 产品源码 | `apps/`、`services/`、`packages/` | 保留；按前端、Sidecar、共享契约维护 |
| 产品文档与任务 | `docs/`、`tasks/`、`specs/`、`templates/` | 保留；任务状态以 `CURRENT_TASK.md`、任务文件和 `HANDOFF.md` 为准 |
| 开发入口 | `start-local.bat`、`scripts-dev/` | 保留；临时 CAD 浏览器 QA 服务已归入 `scripts-dev/` |
| 依赖和构建缓存 | `.venv/`、`node_modules/`、`apps/desktop/src-tauri/target/` | 可再生，不提交；需要释放磁盘时使用受控清理脚本 |
| 应用数据 | `.data/` | 不提交、不自动删除；包含本地项目与配置 |
| 跟踪参考包 | `references/source-packages/` | 提交并审计；保留原始 Skill 等可恢复输入 |
| 本地参考资料 | `references/local/` | 不提交、不删除；只作为本机参考输入 |
| 品牌源文件 | `assets/branding/` | 提交并作为桌面、Web 和安装器的统一源资产 |
| 用户/开发输出 | `outputs/`、`.tmp/` | 不提交；不在整理过程中自动删除 |

## 磁盘占用快照

审计时主要目录约为：

- `apps/desktop/src-tauri/target/`：9.1 GB，Rust/Tauri 可再生增量构建缓存。
- `apps/desktop/src-tauri/resources/sidecar/`：781 MB，Windows 离线 Sidecar 打包产物，已被忽略。
- `.venv/`：1.18 GB，Python 本地依赖环境。
- 根 `node_modules/`：205 MB，pnpm 本地依赖。
- `.data/`：37 MB，本地应用数据，禁止当作缓存删除。

若确需释放空间，先运行：

```powershell
powershell -ExecutionPolicy Bypass -File scripts-dev/clean-generated.ps1 -WhatIf
```

检查目标后再执行不带 `-WhatIf` 的命令。不得将 `.data/`、参考资料目录或 `outputs/` 加入自动清理目标。

## 已完成优化

- 将根目录 `cad_browser_qa_server.py` 移至 `scripts-dev/cad-browser-qa-server.py`，并增加参数与 `preview.glb` 存在性检查。
- `.gitignore` 明确忽略本地参考仓库、`.tmp/` 和 `outputs/`，减少状态噪声而不删除文件。
- 2026-07-25 将散落根目录的跟踪参考包、本机参考工程和品牌源文件分别归入 `references/source-packages/`、`references/local/` 和 `assets/branding/`；移动前后文件数量与字节数一致。
- 完整本地启动改为增量 contracts 构建，移除高延迟 WMI/CIM 全进程扫描，并由 Tauri 单一托管 Sidecar。
- Hardware Skill 使用磁盘持久化目录索引；常规展示不再遍历和校验所有 Skill 文件。
- 开发启动日志达到 5 MB 后保留一份轮转副本，避免无限增长。

## 后续优化建议

1. `HANDOFF.md` 已超过 130 KB。下一个独立维护任务应制定“当前交接 + 只读历史归档”的契约后再拆分，不能直接截断历史恢复信息。
2. Rust `target/` 是最大磁盘项。可在 CI/开发文档中增加定期 `cargo clean` 建议，但不应在日常启动时清理，否则会显著拖慢下一次编译。
3. `apps/desktop/src-tauri/resources/sidecar/` 只应由打包脚本生成；日常开发启动不应读取或重建它。
4. 仓库仍存在大量其他任务的未提交改动。本次没有批量移动业务文件或执行自动格式化，以免覆盖并行工作。

## 2026-07-19 M9 收尾补充

- 已核对并删除 `apps/desktop/src-tauri/target/debug/` 中 5.13 GiB、5244 个可再生成文件；release 安装包、PyInstaller Sidecar、`.data`、用户输出和参考目录均保留。
- 严格 Hardware Skill 模板中误生成的单个 `__pycache__/cadquery.cpython-313.pyc` 已删除；后续 Python 测试统一设置 `PYTHONDONTWRITEBYTECODE=1`，模板固定文件树测试恢复通过。
- 最终打包时 `.data/hardware-skills` 有 67 个通过 manifest、路径、媒体哈希和内容校验的 ACTIVE 包；其中近期更新目录属于共享工作树有效资料，未按“生成物”删除。
- `git diff --check` 无空白错误，只有仓库既有 LF/CRLF 转换提示。工作树仍混合大量用户/其他任务差异，因此未暂存、未提交，也未执行整库 clean/reset。
- 清理完成后，另一套 21:45 启动的活动开发实例又按需重建了 `target/debug`，并持有 Vite、Sidecar 与已脱敏真实串口的只读终端；该活动实例及其缓存没有在收尾中终止或删除。
