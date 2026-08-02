# ZW-MAINT-001 — 项目目录清理与重复实现整合

状态：已完成（2026-07-10）

本文件遵循根目录 `PLANS.md` 和 `WORKFLOW.md`，是 living ExecPlan。

## 1. Purpose / Big Picture

在不破坏掌问当前可运行环境、用户数据和恢复依据的前提下，清理完成阶段遗留的可再生构建/测试缓存，移除已失效的基线文件和不可达旧代码，并把重复的测试 Fake、LLM 配置加载和权威文档入口整合到清晰位置。

完成后可观察结果：

- 项目目录释放约 6.3 GB 可再生空间，主要来自 Tauri/Rust `target`。
- 根目录只保留当前开发入口；原始 v0.1 PRD 进入 `docs/archive/`，当前 `docs/PRD.md` 继续作为权威产品基线。
- 自动测试 Fake 集中在 `services/local-api/tests/fakes.py`，`conftest.py` 只负责 fixture 装配。
- 生产 LLM 配置读取复用共享安全边界，旧的不可达 Provider/关键词辅助代码被移除。

## 2. Scope

- 删除可再生目录：Rust/Tauri target、Tauri gen、前端/Contracts dist、Qoder repowiki、pytest/Python cache、根 `.pnpm-store`。
- 保留 `.venv`、全部 `node_modules`，保证本地开发仍可启动；它们不是交付源码，但属于当前可运行依赖环境。
- 保留 `services/local-api/.data`、`.codex/config.toml` 和 Windows Credential Store 中的凭据，不读取或修改其内容。
- 集中通用测试 Credential Store、序列 Provider 和结构化全局 Fake Provider。
- 复用 `llm.runtime.require_llm_config()`，移除 EntryRouter/ProjectRepository 中已不可达的重复辅助代码。
- 重写当前 README；删除失效的初始包 `MANIFEST.json`；移动原始 PRD 到历史文档目录并修正当前 PRD 状态。
- 压缩 `HANDOFF.md` 为当前权威交接，历史细节由任务文件、Git 提交和标签恢复。

## 3. Non-goals

- 不删除或迁移用户项目、SQLite 数据库、对话、草稿、私有记忆、Artifact 或版本。
- 不删除依赖锁文件、`.venv`、`node_modules`、Codex/Qoder 配置、Agent 或 Skill 镜像。
- 不重构大型 Repository，不升级依赖，不改变 API/UI 行为。
- 不调用真实付费 LLM，不扫描或操作真实设备，不运行 `mpremote`、`esptool`、Flash 或固件操作。
- 不创建、规划或实现 `ZW-017`。

## 4. Repository Orientation

- 当前应用入口：`README.md`、`package.json`、`scripts-dev/start-local.ps1`。
- 当前产品基线：`docs/PRD.md`、`docs/UI_CONTRACT.md`、`docs/API_EVENTS.md`、`docs/DECISIONS.md`。
- 共享 LLM Runtime：`services/local-api/zhangwen/llm/runtime.py`。
- 测试支持：`services/local-api/tests/conftest.py`、`services/local-api/tests/fakes.py`。
- 受保护本地状态：`services/local-api/.data/`、`.codex/config.toml`。

## 5. Interfaces and Data Contracts

本任务不改变 HTTP、SSE、SQLite 或 TypeScript 契约。LLM 配置整合必须保持 `CONFIG_MISSING`、Provider 错误和聊天错误事件的既有行为。

## 6. Architecture & Boundaries

- `llm.runtime` 是非敏感模型设置和安全凭据读取的唯一共享实现。
- `tests.fakes` 是跨测试复用 Fake 的单一位置；`conftest` 只声明自动 fixture。
- Git 跟踪源文件和权威文档；构建产物、缓存和用户数据继续通过 `.gitignore` 隔离。
- `ai/skills` 是 Skill 源，`.agents/skills` 与 `.qoder/skills` 是工具发现镜像，三者不得因内容相同而合并成单一路径。

## 7. UI & Interaction

无 UI 或交互行为变更。现有桌面开发服务和中央主对话不受影响。

## 8. Milestones

### M1：审计与保护边界

- 量化生成物、依赖和用户数据目录。
- 建立明确删除允许列表和保护列表。

### M2：源码与文档整合

- 集中测试 Fake 和 LLM 配置加载。
- 删除不可达旧代码。
- 整合 README、PRD 和历史原始 PRD；移除失效 Manifest。

### M3：验证与生成物删除

- 运行受影响测试、全量回归、类型检查、构建/Cargo 和 AI 资产一致性检查。
- 验证完成后按解析后的绝对路径删除允许列表生成物，复核保护项与 Git 状态。

### M4：交接与版本边界

- 更新任务、`CURRENT_TASK.md`、`PLANS.md`、`HANDOFF.md` 和 Decision Log。
- 创建独立提交与本地标签，不推送。

## 9. Progress

- [x] (2026-07-10) M1 完成：确认约 6.3 GB 可再生生成物；`.venv`/`node_modules` 约 129 MB，保留以维持可运行性；`.data`、本地 Codex 配置和用户未暂存任务记录进入保护列表。
- [x] (2026-07-10) M2 完成：集中测试 Fake 和生产 LLM 配置读取；移除旧同步 EntryRouter、重复 JSON 提取和不可达仓储关键词代码；重写 README/架构，更新 PRD，归档原始 PRD 并删除失效 Manifest。定向后端 68 通过。
- [x] (2026-07-10) M3 完成：全量后端 145 通过，桌面 7 文件/67 测试通过，根 typecheck、桌面生产构建、Cargo check、Python compileall 和 Skill 镜像检查通过。执行允许列表清理，删除 33 个生成/缓存目录并释放 6296.37 MB；保护目录和 `.data` 5 文件/2.75 MB 不变。
- [x] (2026-07-10) M4 完成：任务、当前状态、计划、决策和交接已收尾；准备独立提交和本地标签，不推送。

## 10. Surprises & Discoveries

- `apps/desktop/src-tauri/target` 单独占用约 6290.86 MB，是本次空间清理的主体。
- 根 `MANIFEST.json` 只描述最初开发基线包，已与当前 321 个跟踪文件和本地配置策略失配。
- 当前 PRD 仍写有 schema v20、允许 EntryRouter 确定性生产降级和真实 LLM 尚未验证等旧状态，需要与 v22/ZW-LLM-001 对齐。

## 11. Decision Log

| 编号 | 决策 | 选择 | 理由 |
|------|------|------|------|
| D-01 | 依赖目录 | 保留 `.venv` 和全部 `node_modules` | 保证清理后仍可直接运行和验证；依赖不属于未知垃圾 |
| D-02 | 用户状态 | 保留 `.data`、本地 Codex 配置和用户任务记录 | 清理授权不扩展为删除用户数据或凭据 |
| D-03 | Skill 重复 | 保留源目录和两个发现镜像 | 这是跨工具兼容设计，由同步/检查脚本维护 |
| D-04 | 历史 PRD | 移至 `docs/archive/`，不删除内容 | 清理根目录同时保留产品来源和 Git 可追溯性 |
| D-05 | 初始 Manifest | 删除 | 已失效且无运行/构建引用，Git 历史可恢复 |

## 12. Autonomous Execution Notes

- 删除仅使用显式允许列表；每个目标在执行前解析绝对路径并验证位于 `D:\ZW_V1` 内。
- 不使用 `git clean`、通配符递归删除或跨 Shell 拼接删除目标。
- 不暂存用户所有的 `tasks/ZW-UX-003-three-expert-system.md` 两条记录。

## 13. Minimum Test Plan

- `pytest`：项目路由、项目聊天、三师 Runtime、真实 LLM fake-provider 边界。
- 全量后端测试。
- Contracts build/typecheck、根 typecheck、桌面全量测试和生产构建。
- Python compileall、Cargo check、AI Skill 镜像一致性和 Git whitespace 检查。
- 删除后验证保护目录存在、删除允许列表不存在、服务健康和 Git 只包含预期变更。

## 14. Validation

工作目录：`D:\ZW_V1`

自动测试不使用真实 Provider 或设备。构建/测试在删除生成物之前完成，防止验证命令重新生成待清理目录。

## 15. Outcomes & Retrospective

- 生成物由一个可重复、支持 `-WhatIf` 且校验路径的 PowerShell 脚本管理，不再依赖危险的手工递归删除。
- 删除与整合后净减少超过 500 行跟踪代码/测试重复，同时保留所有对外契约。
- 生产 EntryRouter 的 Provider-only 边界更清晰；仓储恢复专用本地路由不再伪装成模型客户端。
- 历史原始 PRD 保留在 `docs/archive/`，当前 README/PRD/架构/交接恢复单一权威入口。

## 16. Handoff

下一步：提交并创建本地标签后运行 `git status --short --branch` 和 `git log -1 --oneline --decorate`，确认仅保留用户所有的 ZW-UX-003 两条记录和已忽略的本地配置。
