# ZW-001 — Repository Bootstrap

本文件遵循根目录 `PLANS.md`，是 living ExecPlan。

## Purpose / Big Picture

建立可启动、可验证、可交接的 Tauri + React + TypeScript 桌面壳与 Python FastAPI sidecar。用户启动开发环境后可以看到永久中央主对话、左侧项目栏和右侧工作/产物/设备 Tab，并通过健康检查确认前后端连通。

本轮基线修复的目标是让 Qoder 已实现代码成为具备 Git 基线、依赖可复现、测试可运行、Tauri 结构有效的工程基线；不进入 ZW-002。

## Scope

- 初始化/修复 Git 工作树与忽略规则。
- 修复 Node/pnpm 依赖安装和 pnpm store 位置。
- 修复 Python sidecar 项目级虚拟环境与依赖声明。
- 修复 Tauri v2 Cargo 结构。
- 清理 `HANDOFF.md` 与本任务文件的重复旧段落。
- 验证 ZW-001 静态主布局、右侧 Tab、草稿保留、浮窗不替换主对话。

## Non-goals

- 不实现账号、真实 Agent、硬件规则、串口或云端模型。
- 不实现项目 CRUD、WebSocket 事件推送或 ZW-002。
- 不改变现有 UI 视觉设计。
- 不实现浮窗拖拽、缩放、贴边或真实产物预览。

## Repository Orientation

```text
apps/desktop/           — Tauri v2 + React 18 + TypeScript (Vite)
services/local-api/     — Python FastAPI sidecar
packages/contracts/     — 共享 TypeScript 枚举与类型
scripts-dev/            — 开发与测试脚本
docs/                   — 产品与架构文档
tasks/                  — 任务 ExecPlan
```

## Interfaces and Data Contracts

### HTTP API

| 方法 | 路径 | 用途 |
|---|---|---|
| GET | `/api/health` | 健康检查，返回 `status` / `version` / `uptimeSeconds` |

### 共享枚举（packages/contracts）

- `ProjectStage`
- `TaskStatus`
- `ArtifactStatus`
- `DeviceSessionStatus`
- `EventType`

## Milestones

- [x] M1: Monorepo 初始化（pnpm workspace、`.gitignore`）
- [x] M2: 共享 Contracts 包（枚举、事件、API 类型）
- [x] M3: Python FastAPI Sidecar（健康检查端点 + pytest）
- [x] M4: Tauri + React + Vite 前端骨架
- [x] M5: 静态主布局（左+中+右三栏，中央对话常驻）
- [x] M6: 健康检查与连通指示（`useHealthCheck` hook + `HealthIndicator`）
- [x] M7: 模拟浮窗验证（`FloatingWindow` 组件，不影响主对话）
- [x] M8: 前端测试（21 个测试通过）
- [x] M9: 开发脚本（`dev.ps1` + `test.ps1`）
- [x] M10: Git 工作树初始化与依赖环境修复
- [ ] M11: Qoder checkpoint 基准提交（等待 Git 身份配置）

## Progress

- [x] (2026-07-08) Qoder 完成 Monorepo、contracts、sidecar、桌面壳、三栏布局、浮窗模拟、健康检查、测试和脚本的初始实现。
- [x] (2026-07-08) Codex 接管盘点发现：当前目录不是 Git 工作树，pnpm 依赖链接损坏，Python 全局环境缺 pytest，Tauri `Cargo.toml` 声明 `[lib]` 但缺少 `src/lib.rs`，交接文档有重复旧段落。
- [x] (2026-07-08) 在 `D:\ZW_V1` 初始化 Git。未发现当前目录或父目录已有 `.git`；README 表明该内容来自开发基线包复制流程。同盘其他 Git 项目无证据表明是当前目录原仓库，未复制其他项目 `.git`。
- [x] (2026-07-08) 删除损坏的 `node_modules` 并执行 `pnpm install --frozen-lockfile`。首次受网络沙箱阻止，提权后安装成功；`pnpm-lock.yaml` 未因安装改变。
- [x] (2026-07-08) 新增 `.npmrc`，将 pnpm store 固定为项目内 `.pnpm-store/`；更新 `.gitignore` 忽略 `.pnpm-store/`。
- [x] (2026-07-08) 使用 `py -3.13 -m venv .venv` 创建项目级虚拟环境，安装 `services/local-api/requirements.txt`，新增 `requirements-lock.txt` 记录精确版本。
- [x] (2026-07-08) 修复 Tauri v2 结构：新增 `src/lib.rs`，`main.rs` 调用 `zhangwen_desktop_lib::run()`，新增最小 `icons/icon.ico`。
- [x] (2026-07-08) 新增最小 UI 回归测试，验证右侧 Tab 和浮窗操作后只有一个中央主对话实例。
- [x] (2026-07-08) 清理 `HANDOFF.md` 和本任务文件重复的新旧段落。
- [x] (2026-07-08) 复跑最终验证：`scripts-dev/test.ps1`、Sidecar HTTP 冒烟、`cargo build` 均通过。

## Status by Area

| 功能或模块 | 状态 | 证据 | 是否符合文档 | 建议处理 |
| ----- | -- | -- | ------ | ---- |
| Git 工作树 | 部分完成 | `git init` 已完成；checkpoint 提交待 Git 身份 | 部分符合 | 用户配置身份后提交 |
| Node/pnpm 依赖 | 已完成并验证 | `pnpm install --frozen-lockfile` 成功 | 符合 | 可保留 |
| Contracts | 已完成并验证 | `pnpm --filter @zhangwen/contracts typecheck` 通过 | 符合 | 可保留 |
| Desktop 类型检查 | 已完成并验证 | `pnpm --filter @zhangwen/desktop typecheck` 通过 | 符合 | 可保留 |
| 前端测试 | 已完成并验证 | `pnpm --filter @zhangwen/desktop test`，21 passed | 符合 | 可保留 |
| 前端构建 | 已完成并验证 | `pnpm --filter @zhangwen/desktop build` 通过 | 符合 | 可保留 |
| Python Sidecar | 已完成并验证 | `.venv` + pytest 2 passed | 符合 ZW-001 | 可保留 |
| Tauri Cargo 结构 | 已完成并验证 | `cargo metadata` / `cargo check` 通过 | 符合骨架要求 | 可保留 |
| 浮窗系统 | 部分完成 | overlay 占位测试通过 | 符合 ZW-001，未满足完整 PRD | 后续任务实现拖拽/缩放 |
| 真实项目 CRUD / Agent / 串口 | 未开始 | 无实现 | ZW-001 非目标 | ZW-002+ 再做 |

## Surprises & Discoveries

- Qoder 交接记录中的“全量验证通过”在接管时无法复现，原因是依赖目录损坏、Python 全局环境缺 pytest、Tauri 缺 `src/lib.rs`。
- pnpm 默认尝试使用 `D:\.pnpm-store\v11`，在受限环境下无权限；项目级 `.npmrc` 解决该问题。
- `cargo check` 依赖下载成功后仍失败一次，原因是 Tauri build script 要求 `icons/icon.ico`。
- Python health 测试通过但有 1 个 Starlette/FastAPI deprecation warning，不影响当前 ZW-001。

## Decision Log

| 日期 | 决策 | 选择 | 理由 |
|---|---|---|---|
| 2026-07-08 | 包管理器 | pnpm | monorepo workspace，磁盘效率高 |
| 2026-07-08 | Tauri 版本 | v2 | 支持后续 sidecar，当前按 v2 标准结构修复 |
| 2026-07-08 | 前端样式 | 原生 CSS | MVP 保持轻量，不引入重框架 |
| 2026-07-08 | Sidecar 启动方式 | 初期独立启动 | 降低初始复杂度，后续集成 Tauri sidecar API |
| 2026-07-08 | 串口归属 | Python pyserial | PRD 待确认决策的默认假设；ZW-001 不实现 |
| 2026-07-08 | 首发平台 | Windows 优先 | PRD 默认假设 |
| 2026-07-08 | 右侧面板宽度 | 320px | 适中信息密度 |
| 2026-07-08 | Sidecar 端口 | 8100 | 避免与 Vite 5173 冲突 |
| 2026-07-08 | pnpm store | 项目内 `.pnpm-store/` | 避免写入无权限的 `D:\.pnpm-store`，且可被 Git 忽略 |
| 2026-07-08 | Python 环境 | Python 3.13 + `.venv` | `pyproject.toml` 要求 `>=3.11`；3.13 可用且依赖安装/测试通过 |
| 2026-07-08 | Python 锁定依赖 | `requirements-lock.txt` | 保留范围声明，同时记录本次可复现精确版本 |
| 2026-07-08 | Tauri 入口 | `main.rs` 调用 `lib.rs` 的 `run()` | 匹配 `Cargo.toml` 已声明的 `[lib]`，不是删除配置绕过 |

## Validation

### 已运行命令与结果

```powershell
git init
# 通过：Initialized empty Git repository in D:/ZW_V1/.git/

pnpm install --frozen-lockfile
# 首次失败：网络沙箱 EACCES；提权后通过，lockfile up to date

pnpm --filter @zhangwen/contracts typecheck
# 通过

pnpm --filter @zhangwen/desktop typecheck
# 通过

pnpm --filter @zhangwen/desktop test
# 通过：3 files, 21 tests passed

pnpm --filter @zhangwen/desktop build
# 通过：vite build completed

py -3.13 -m venv .venv
# 通过

.\.venv\Scripts\python.exe -m pip install -r services\local-api\requirements.txt
# 首次失败：网络沙箱；提权后通过

.\.venv\Scripts\python.exe -m pip check
# 通过：No broken requirements found.

D:\ZW_V1\.venv\Scripts\python.exe -m pytest tests/ -v
# 通过：2 passed, 1 warning

cargo metadata --no-deps --format-version 1
# 通过

cargo check
# 首次失败：网络沙箱；提权下载后发现缺 icons/icon.ico；补图标后通过

cargo build
# 通过

.\scripts-dev\test.ps1
# 通过：contracts typecheck、desktop typecheck、21 frontend tests、2 pytest

D:\ZW_V1\.venv\Scripts\python.exe -m uvicorn zhangwen.main:app --host 127.0.0.1 --port 8100
# 后台启动后请求 http://127.0.0.1:8100/api/health 通过：
# {"status":"ok","version":"0.1.0","uptimeSeconds":2.62}

python scripts/check_ai_assets.py
# 通过：Shared Skills are in sync.
```

### 手工验收

尚未启动长驻 dev server 做手工浏览器验收。本轮自动测试已覆盖：

1. 左侧项目栏、中央主对话、右侧栏同时存在。
2. 右侧一级 Tab 只有“工作 / 产物 / 设备”。
3. 切换 Tab 后输入草稿保留。
4. 打开和关闭浮窗后草稿保留，中央对话仍存在。
5. Tab 和浮窗操作后中央主对话没有重复实例。
6. 健康检查 API 结构通过 Python 测试。
7. 状态枚举来自 `@zhangwen/contracts`。

## Outcomes & Retrospective

ZW-001 工程基线已从“代码存在但不可复现验证”修复为“依赖可安装、前端/Python/Rust 检查可运行、Tauri 结构有效”。仍需用户配置 Git 身份并完成 checkpoint 提交，才能完全满足“Qoder 代码被保存为可回退基准”。

## Handoff

- 当前分支：main
- checkpoint 提交：待完成，缺少 Git 身份。
- 下一步：
  1. 用户配置 `git config user.name` 和 `git config user.email`。
  2. 运行 `git add -A`。
  3. 运行 `git commit -m "chore: checkpoint Qoder bootstrap implementation"`。
  4. 复查 `git status`。
- 禁止重复：不要重写 `main.py` 为包含 startup event 的版本；不要把中央主对话改成可被路由替换的内容区；不要进入 ZW-002 直到 checkpoint 提交完成。

## Historical Notes

Qoder 初始实现曾记录“全量测试通过：contracts typecheck + frontend typecheck + 20 vitest + 2 pytest”。Codex 接管时该声明无法复现；本文件以 2026-07-08 本轮实际命令输出为准。
