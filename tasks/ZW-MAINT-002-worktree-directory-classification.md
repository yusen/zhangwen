# ZW-MAINT-002 — 工作树目录整理与参考输入归类

状态：已完成（2026-07-25；未提交，保留在共享工作树中）

本文件遵循根目录 `PLANS.md` 和 `WORKFLOW.md`，是 living ExecPlan。

## 1. Purpose / Big Picture

在不覆盖当前大量未提交功能、不删除用户数据和不改变运行时行为的前提下，收拢仓库根目录散落的参考输入与品牌源文件，建立可读、可维护的目录地图。

完成后可观察结果：

- 根目录不再散落 CAD 原型、外部硬件工程、复杂结构资料和原始 K10 Skill 包。
- 版本控制内的参考包进入 `references/source-packages/`，仅本机使用且不提交的输入进入 `references/local/`。
- 品牌源文件进入 `assets/branding/`，安装器脚本从新位置读取。
- `references/README.md` 说明每类目录的来源、版本控制和处理边界。

## 2. Scope

- 移动受版本控制的 `unihiker-k10-micropython-skill/` 到 `references/source-packages/`。
- 移动本机参考目录 `ZW-CAD-intent/`、`openclaw-robot-dog-soul-k12(1)/` 和 `复杂结构件建模的人机交互资料/` 到 `references/local/`，保留原目录名和全部内容。
- 移动根目录 `logo.png` 到 `assets/branding/logo.png`。
- 更新有效代码、构建脚本、文档、任务记录和 `.gitignore` 中的路径。
- 记录根目录分类和受保护目录。

## 3. Non-goals

- 不删除或移动 `.data/`、`outputs/`、`.tmp/`、`.venv/`、`node_modules/` 或 Tauri 构建缓存。
- 不整理、暂存、回退或覆盖当前其他任务的业务代码差异。
- 不重构 `apps/`、`services/`、`packages/`、`docs/`、`tasks/` 的内部模块。
- 不调用真实 Provider、串口、设备、上传、复位、Flash 擦除或固件烧录。
- 不创建、规划或实现 ZW-017。

## 4. Repository Orientation

- 产品源码：`apps/`、`services/`、`packages/`。
- 产品与工程资料：`docs/`、`tasks/`、`specs/`、`templates/`。
- 工具与入口：`scripts/`、`scripts-dev/`、`start-local.bat`、`build-installer.bat`。
- 跟踪参考输入：`references/source-packages/`。
- 本机参考输入：`references/local/`，整体忽略，不进入 Git。
- 品牌源文件：`assets/branding/`。

## 5. Interfaces and Data Contracts

本任务不改变 HTTP、SSE、SQLite、TypeScript、设备或 UI 契约。唯一运行路径变化是安装器版本脚本读取品牌源文件的新位置。

## 6. Milestones

### M1：审计与保护边界

- [x] 读取当前任务、交接、既有项目文件审计和维护任务。
- [x] 量化根目录用途、Git 归属、磁盘占用和代码引用。
- [x] 确认运行数据、输出、依赖和构建缓存不在本次迁移范围。

### M2：目录归类

- [x] 建立 `references/source-packages/`、`references/local/` 和 `assets/branding/`。
- [x] 使用精确绝对路径移动五个已确认目标，不删除内容；移动前后分别为 49、1202、8、20、1 个文件，字节数一致。
- [x] 更新 `.gitignore` 和有效路径引用。

### M3：目录地图与验证

- [x] 增加 `references/README.md`，更新根 README 和项目文件审计。
- [x] 验证旧路径不存在、新路径存在；K10 原始包 49 个 Git blob 与移动前 HEAD 内容逐文件一致。
- [x] 安装器只读检查通过；K10 Board Skill 与相册模板回归 `12 passed`；Git whitespace 检查无错误，仅有既有 LF/CRLF 提示。

### M4：交接

- [x] 更新本任务、`CURRENT_TASK.md`、`PLANS.md` 与 `HANDOFF.md`。
- [x] 复核工作树；因多个本任务文件已混有其他阶段未提交内容，本轮不暂存、不提交，避免把共享差异并入维护提交。

## 7. Decision Log

| 编号 | 决策 | 选择 | 理由 |
|---|---|---|---|
| D-01 | 参考目录分层 | `source-packages/` 跟踪，`local/` 忽略 | 区分可恢复的仓库输入和含本机环境/私密配置的外部工程 |
| D-02 | 外部目录命名 | 移动时保留原目录名 | 降低来源混淆，避免无必要重命名 |
| D-03 | 生成物与数据 | 原地保留 | 构建缓存可由既有脚本单独处理，用户数据和输出不得借整理删除 |
| D-04 | 品牌源文件 | `assets/branding/logo.png` | 它是跨桌面、Web 和安装器使用的源资产，不属于根目录入口文件 |

## 8. Validation

- 旧的五个根目录目标不存在，新路径逐一存在。
- `git ls-files` 中 K10 原始 Skill 包仍为 49 个文件，只发生路径迁移。
- `rg` 不再发现有效代码或当前文档引用旧路径。
- `cmd /c build-installer.bat --check` 通过且不构建、不安装、不递增版本。
- 相关 K10/CAD 模板测试通过；`git diff --check` 无新增 whitespace 错误。

## 9. Handoff

已完成，无剩余实现。后续若要提交，必须逐文件和逐 hunk 审核本任务差异；禁止使用 `git add -A`、`git clean`、整库 stash/reset 或递归删除。`references/local/` 含本机外部工程及配置，只能继续保持忽略。
