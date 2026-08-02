# ZW-MAINT-003 — 全项目代码审查与保守重构

状态：已完成（2026-07-25，未提交）

本文件遵循根目录 `PLANS.md` 和 `WORKFLOW.md`，是 living ExecPlan。

## 1. Purpose / Big Picture

对掌问当前前端、共享契约、Python Sidecar、Tauri 宿主与设备安全边界做一次以证据为基础的整体审查，并对能够通过自动测试证明等价的高价值问题实施小范围重构。

完成后可观察结果：

- 现有严格类型检查、自动测试和生产构建保持通过。
- 审查发现按严重度、证据、修复状态和剩余风险记录，不以代码体量或主观风格作为重构理由。
- 被重构的路径具有新增或强化的回归测试，外部 API、SSE、SQLite、UI 和设备安全契约不发生无计划变化。
- 不触碰真实 Provider、真实串口、设备文件、Flash 或公开发布。

## 2. Scope

- 审查 `apps/desktop/src`、`packages/contracts/src`、`services/local-api/zhangwen`、Tauri 宿主边界和对应测试。
- 运行现有 contracts/TypeScript、Vitest、pytest、Python 编译与必要生产构建，优先定位可复现失败和不一致。
- 检查共享状态枚举、API 边界、错误恢复、路径与凭据安全、设备端口锁/确认点、永久主对话和固定右侧三 Tab。
- 只实现有明确收益、范围受控且可以自动验证的重构；跨端契约变化必须先更新契约或测试。

## 3. Non-goals

- 不进行无失败证据的全库改名、目录重排、依赖升级或格式化。
- 不改变产品信息架构、推荐方案语义、Provider 选择或真实设备流程。
- 不整理、暂存、回退或覆盖当前共享工作树中的其他未提交差异。
- 不执行真实 LLM 请求、串口连接、上传、复位、Flash 擦除、固件烧录、安装、签名、发布或强推。
- 不创建、规划或实现 ZW-017。

## 4. Repository Orientation

- 桌面 UI：`apps/desktop/src`，必须保持 `CenterChat` 单一挂载和“工作 / 产物 / 设备”三 Tab。
- 共享契约：`packages/contracts/src`，跨端枚举和 API 结构的唯一 TypeScript 来源。
- Sidecar：`services/local-api/zhangwen`，负责 Pydantic 边界、持久化、Provider、本地工具和设备安全。
- 宿主：`apps/desktop/src-tauri`，负责本地能力与 Sidecar 生命周期，不向 Web 暴露宿主能力。

## 5. Interfaces and Data Contracts

本任务默认不改变 HTTP、SSE、SQLite、Artifact、设备操作或 UI 外部契约。若审查发现必须修正契约，先补共享 contracts/Pydantic/回归测试并在 Decision Log 单独记录；否则重构保持行为等价。

## 6. Milestones

### M1：基线与风险审计

- [x] 读取当前任务、交接、工作流、架构和完整 UI 契约。
- [x] 记录共享工作树保护边界、最近提交、模块规模和现有检查入口。
- [x] 运行类型检查、前端测试和后端测试，记录真实基线。

### M2：静态审查与发现排序

- [x] 检查大文件/长函数、重复边界逻辑、错误吞没、并发/取消、路径验证、敏感信息和设备高风险确认点。
- [x] 对 UI 永久主对话、固定三 Tab、普通/专业信息分层运行契约回归。
- [x] 把候选问题按正确性、安全性、可维护性和修复风险排序，仅选择可证明的问题进入实现。

### M3：保守重构与回归

- [x] 先补或强化失败/边界测试。
- [x] 实施最小重构，不扩大权限、不改变公开契约。
- [x] 运行受影响最小测试并回填发现、决定与文件清单。

### M4：自动验收与交接

- [x] 运行 contracts、strict TypeScript、桌面测试、Sidecar 测试、安全 Python 编译和必要生产构建。
- [x] 运行 UI 契约和设备 Mock/Dry Run 安全回归；不把真实设备验证写成通过。
- [x] 更新本任务、`PLANS.md`、`CURRENT_TASK.md` 和 `HANDOFF.md`，汇总剩余风险与下一步。

## 7. Decision Log

| 编号 | 决策 | 选择 | 理由 |
|---|---|---|---|
| D-01 | 重构选择标准 | 失败证据或可量化重复 + 自动测试保护 | 避免在大量在途差异上进行主观全库重写 |
| D-02 | 接口策略 | 默认行为等价，不改外部契约 | 当前已有广泛前后端、设备与 UI 验收基线 |
| D-03 | 设备审查 | 只读代码与 Mock/Dry Run 测试 | 真实上传、复位、擦除和烧录需要独立确认 |
| D-04 | 工作树策略 | 精确文件、精确 hunk 修改 | 共享工作树含多阶段和用户未提交成果 |
| D-05 | Sidecar 夹具 | 直接构造自包含代码草稿并走真实本地验证 | 设备测试不应依赖 Spec/LLM/Hardware Skill 目录或其他测试的执行顺序 |
| D-06 | Python 编译检查 | 排除带完整性清单的资源包 | `compileall` 写入 `__pycache__` 会按设计破坏资源包的严格目录完整性 |

## 8. Validation

- `pnpm typecheck`
- `pnpm test:frontend`
- `.venv\Scripts\python.exe -m pytest services/local-api/tests -q --rootdir services/local-api`
- `.venv\Scripts\python.exe -m compileall -q -f -x "(board-skills|bundled-hardware-skills|hardware-skill-template)" services/local-api/zhangwen`
- `pnpm build:desktop`
- 受影响专项测试、UI 契约组合和设备 Mock/Dry Run 安全测试
- `git diff --check`

## 9. Handoff

任务已完成但未提交。主要结果见 `docs/reports/CODEBASE_REVIEW_2026-07-25.md`：统一底层 401 会话失效，修复旧环境取消信号与监听器清理，复用 API 错误解析和共享状态枚举，并消除两处 Sidecar 测试夹具的目录/顺序依赖。最终 `704` 项 Sidecar、`209` 项桌面、`5` 项 Tauri 测试通过。不得为了审查整洁而执行 `git add -A`、整库 stash/reset/clean、依赖升级、真实 Provider/设备操作或不可逆删除。
