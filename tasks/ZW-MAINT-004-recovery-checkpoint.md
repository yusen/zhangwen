# ZW-MAINT-004 — 共享工作树恢复检查点

状态：已完成（2026-07-29）

本文遵循根目录 `PLANS.md`、`WORKFLOW.md` 与 `CODEX_AUTONOMOUS_WORKFLOW.md`，是本次维护工作的 living ExecPlan。

## 1. Purpose / Big Picture

把长期累积、已超出人工可靠恢复能力的共享工作树变成可由 Git 精确定位和恢复的状态，同时不丢失现有源码、测试、任务记录和受审计参考输入。

完成后必须可观察到：

- 当前有效项目内容已进入一个显式恢复提交，恢复不再依赖聊天或未提交工作树。
- 本机缓存、运行数据库、用户数据和被保护的本机参考目录不进入 Git。
- `HANDOFF.md` 与 `CURRENT_TASK.md` 只描述当前恢复状态，历史仍可从恢复提交读取。
- 有独立完成提交和 `zw-maint-004-complete` 标签作为恢复入口。

## 2. Scope

- 审计全部 tracked/untracked 差异、文件类型、体积和敏感内容。
- 为本机 pytest 缓存、WorkBuddy 本机记忆和误落入源码树的运行数据库补充忽略规则。
- 通过显式路径暂存项目源码、测试、契约、文档、任务、工具、品牌资源和受审计参考快照。
- 审查 staged 状态、统计、敏感文件候选和空白错误后创建恢复提交。
- 压缩当前任务与交接，创建收尾提交和阶段标签。

## 3. Non-goals

- 不重写或重新归因既有业务改动，不声称能可靠还原此前未提交内容的历史阶段边界。
- 不使用 `git add -A`、stash、reset、clean、强制推送或递归删除。
- 不删除 `.data/`、`outputs/`、`references/local/`、构建缓存、运行数据库或其他本机数据。
- 不调用真实 Provider、串口、设备上传、复位、Flash 擦除、固件烧录、安装或发布。
- 不创建、规划或实现 ZW-017。

## 4. Repository Orientation

恢复点纳入以下显式范围：

- 根入口与工程配置：`.gitattributes`、`.gitignore`、`README.md`、`package.json`、`pnpm-lock.yaml`、`start-local.bat`、`build-installer.bat`、`reset-local-password.bat`。
- 产品与测试：`apps/`、`services/`、`packages/`。
- 文档与任务：`docs/`、`specs/`、`tasks/`、`templates/`、`PLANS.md`、`CURRENT_TASK.md`、`HANDOFF.md`。
- 工具与资产：`scripts/`、`scripts-dev/`、`assets/`。
- 可审计输入：`references/README.md`、`references/source-packages/`。
- 旧 K10 根目录的 tracked 删除与 `references/source-packages/` 下的新位置一起纳入，以记录迁移。

明确排除：`.workbuddy/`、任意 `.pytest_cache/`、`.data/`、`.tmp/`、`outputs/`、`references/local/`、`node_modules/`、`.venv/`、Tauri `target/`/Sidecar 产物，以及 `services/local-api/zhangwen/hardware/projects/` 下的运行数据库。

## 5. Milestones

### M1：边界审计

- [x] 统计 tracked/untracked 差异、文件类型和最大文件。
- [x] 检查疑似凭据、私钥、环境文件、数据库和二进制候选。
- [x] 确认 `references/source-packages/ZW-CAD-intent/` 是带来源 hash 的受审计快照。
- [x] 确认 `services/local-api/zhangwen/hardware/projects/zhangwen.sqlite3` 是运行数据，不进入 Git。

### M2：恢复提交

- [x] 补充忽略规则并复核排除项生效。
- [x] 仅使用显式路径暂存，复核 staged 文件清单、统计、空白和敏感候选。
- [x] 创建恢复提交：`97da7fa092239fb440c91676fcba0d9eb16e29fe`。

### M3：交接收口

- [x] 将 `CURRENT_TASK.md` 和 `HANDOFF.md` 压缩为当前状态。
- [x] 更新本任务与 `PLANS.md` 的完成状态。
- [x] 创建收尾提交并以 `zw-maint-004-complete` 标签作为最终恢复入口。
- [x] 确认 Git 可见工作树完全干净；明确排除的本机文件原地保留且不显示为噪声。

## 6. Decision Log

| 编号 | 决策 | 理由 |
|---|---|---|
| D-01 | 用“恢复快照 + 交接收口”两个提交，不伪造历史阶段提交 | 现有差异跨多个已完成任务且相互交织；按猜测拆分会降低可恢复性 |
| D-02 | 第一提交保留整理前的完整交接内容，第二提交再压缩 | Git 历史先保存信息，随后才能安全消除 append-only 交接噪声 |
| D-03 | 精确纳入路径，禁止 `git add -A` | 防止本机数据、未知缓存或新增敏感文件被批量带入 |
| D-04 | 不删除被排除文件，只补忽略规则 | 恢复工作树可读性不等于获得删除用户/运行数据的授权 |
| D-05 | 标签只落在交接收口提交 | 标签应指向可继续开发的最终恢复状态，而非中间快照 |
| D-06 | `references/source-packages/**` 禁止换行规范化 | 来源快照的逐文件 SHA-256 必须在检出后仍可复验 |
| D-07 | 历史交接中的真实串口、本机账号、显示名和 Project ID 在提交前脱敏 | 恢复技术结论不能以提交隐私数据为代价；测试夹具改用明确虚构值 |

## 7. Validation

本次开始前已取得以下当前工作树证据：

- `pnpm typecheck`：通过。
- desktop：`36 files / 231 passed`。
- `pnpm build:desktop`：通过；仅既有主 chunk/Monaco 体积提示。
- Rust：`5 passed`。
- cloud auth：`3 passed, 1 skipped`；仅既有弃用与 pytest 缓存权限 warning。
- Sidecar 全量本轮在 300 秒到达约 48% 后超时，已运行部分无失败；不得写成全量通过。
- `git diff --check`：无 whitespace error，仅既有 LF/CRLF 转换提示。
- 恢复点 staged 审计：784 个路径；`git diff --cached --check` 通过，禁止项和真实隐私扫描无命中，49 个 K10 文件均为 `R100` 重命名。
- CAD 来源快照：`CHECKSUMS.sha256` 的 149/149 个文件逐项匹配；`.gitattributes` 禁止该目录的换行规范化。
- 脱敏后 desktop 全量：`36 files / 231 passed`；认证与恢复脚本定向后端测试：`4 passed`，仅既有弃用/pytest 缓存权限 warning。

提交前还必须验证 staged 边界；提交后验证 tag、HEAD、工作树状态和排除项。

## 8. Recovery Procedure

- 中间恢复提交和最终提交 hash 写入 `HANDOFF.md` 与本任务。
- 最终恢复入口为标签 `zw-maint-004-complete`。
- 需要查看整理前完整交接时，从中间恢复提交读取 `HANDOFF.md`；不要用 reset 覆盖当前工作树。
- 需要恢复单个文件时，先只读比较目标提交与当前文件，再使用精确路径的 Git 恢复操作。

## 9. Handoff

任务已完成。完整整理前状态位于 `97da7fa092239fb440c91676fcba0d9eb16e29fe`，最终继续开发入口为 tag `zw-maint-004-complete`。需要查看整理前完整交接时只读执行 `git show 97da7fa:HANDOFF.md`；不要为恢复历史说明而 reset 当前工作树。运行数据库、`.workbuddy/`、pytest 缓存和 `references/local/` 继续只保留在本机。
