# 掌问

掌问是一款本地优先的“AI 创客工程工作台”，由同一个 React 应用、FastAPI 本地服务、SQLite 项目库、共享 TypeScript 契约，以及 Browser/Tauri 两个宿主组成。Tauri 是最终桌面宿主；`start-local.bat` 是唯一完整本地应用入口，设备能力在该应用内使用。

当前产品使用三位用户可见专家：问题引导师、智能工程师和结构工程师。生产 AI 推理、生成和修订可选择 DeepSeek、千问（Qwen）、智谱 GLM 或 Kimi 的 OpenAI 兼容 API；权限、持久化、硬件规则、代码/CAD 校验以及文件、Shell、串口和设备执行保持本地受控。

当前 Web 交互采用“一个项目、一条时间线、一个输入框”：左侧创建/切换项目，创建时按需求选择参与智能体，输入框上方以胶囊显示项目智能体，并可通过 `@智能体` 指定下一位回复者。底层各智能体的 Provider 对话历史仍相互隔离，共享的只是项目事实、决策、产物和公共硬件知识。

三师行为使用产品内目录化 Agent Skill 包配置：每位智能体以 `SKILL.md` 为入口并按需读取 Markdown 参考文件。专业模式可在设置中编辑、保存或恢复默认；这些文本只影响目标智能体提示词，不会授予工具、设备或本地执行权限。现有 Registry Skill 仍是独立的受控执行能力。

硬件库同样使用目录化 Hardware Skill：每个器件以 `SKILL.md` 为入口，参数、兼容规则、集成、安全、来源和验证用例均保存在受控 Markdown 文件中。Sidecar 从有效 Skill 编译确定性规则快照，SQLite 仅保留可重建投影；客户可通过上传资料或对话生成草稿，校验并确认后才激活。三师共享读取同一有效 revision，云端 LLM 不直接写文件或执行规则。

## 目录

- `apps/desktop`：React/Vite 桌面 UI 和 Tauri 宿主。
- `services/local-api`：FastAPI Sidecar、SQLite 持久化、LLM Runtime 和本地工具边界。
- `services/local-api/zhangwen/experts/agent-packages`：三师内置 Agent Skill 包。
- `<data_dir>/hardware-skills`：统一的客户 Hardware Skill 项目；旧组件在首次读取时由 Sidecar 幂等迁移。
- `docs/HARDWARE_SKILL_AI_AUTHORING_GUIDE.md`：可直接交给任意 AI 的 Hardware Skill v1 权威编写规范、精确 Schema、哈希算法和交付检查清单。
- `packages/contracts`：跨前后端共享契约。
- `docs`：当前 PRD、架构、UI/API 契约、决策和验收记录。
- `tasks`：可恢复的 ExecPlan 和阶段记录。
- `assets/branding`：桌面、Web 和安装器共用的品牌源文件。
- `references/source-packages`：受 Git 跟踪、可审计的原始参考包。
- `references/local`：仅本机使用的外部工程和资料，整体忽略；详细边界见 `references/README.md`。
- `scripts`、`scripts-dev`：一致性检查、开发启动、构建和 QA 工具。
- `specs`、`templates`：工程规格来源和项目模板。
- `ai/skills`：Codex/Qoder 开发工具的共享 Skill 源；`.agents/skills` 和 `.qoder/skills` 是工具发现镜像，不承载产品三师配置。

`.data/` 是受保护的本地应用数据，`outputs/` 是用户/开发输出，`.venv/`、`node_modules/` 和 Tauri `target/` 是本地依赖或可再生构建缓存；这些目录不应为了“整理根目录”而移动、提交或删除。

## Windows 安装包

Windows x64 离线安装包位于
`apps/desktop/src-tauri/target/release/bundle/nsis/掌问_0.1.x_x64-setup.exe`。根目录直接运行
`build-installer.bat` 会自动递增补丁版本、构建并验证，无需手工修改版本文件。
安装后不需要 Node.js、pnpm、Python 或 Rust；本地 UI、Sidecar 和内置资源均随包提供。
安装、离线边界、数据目录、SmartScreen 和构建验证说明见
`docs/WINDOWS_INSTALLER.md`。

## 环境

- Node.js 20+
- pnpm 9+
- Python 3.11+
- Rust/Cargo（Tauri 桌面检查和构建）

```powershell
pnpm install --frozen-lockfile
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services\local-api\requirements.txt
```

## 默认启动：完整本地应用

```powershell
pnpm start
# 或
.\start-local.bat
```

`start-local.bat` 是唯一完整本地应用入口；`pnpm start` 只是它的同义命令。入口只在源码变更后重建共享 contracts，并启动 Tauri 开发宿主；Vite 由 Tauri CLI 管理，FastAPI Sidecar 由桌面主机单一托管并在异常退出后自动恢复。串口扫描、设备连接、代码上传等本地硬件能力均在这个应用内使用。

只检查完整本地应用启动脚本、不启动服务或访问硬件：

```powershell
pnpm start:check
# 或
.\start-local.bat --check
```

## 显式 Web Development Mode

```powershell
pnpm dev:web
```

访问 [http://localhost:5173](http://localhost:5173)。该命令启动 FastAPI Sidecar 和 Vite Browser Host，并在退出时清理开发子进程；它不会启动 Tauri 或 Rust。

Web Development Mode 只是同一个 React UI 的浏览器开发宿主。FastAPI/SQLite 仍拥有项目、消息、草稿、产物和 Provider 调用。浏览器不直接访问 SQLite 或 DeepSeek，不保存 Provider Key，也不允许串口、设备上传、Flash、Shell 或本地 CAD 执行。

浏览器开发需要模型服务时，优先使用 fake Provider 测试；手工开发可在启动 FastAPI 前设置对应的后端进程环境变量 `ZHANGWEN_DEEPSEEK_API_KEY`、`ZHANGWEN_QWEN_API_KEY`、`ZHANGWEN_GLM_API_KEY` 或 `ZHANGWEN_KIMI_API_KEY`，也可使用已有后端安全凭据。不同服务商的凭据相互隔离。不要把 Key 写入 Vite 环境、LocalStorage、命令日志或 Git。

需要在不调用真实云端模型的情况下验证多智能体发送交互时，使用内部 QA 隔离入口：

```powershell
pnpm dev:web:fake
```

该命令把验证数据放在 `.data/web-fake`，只在当前 FastAPI 子进程设置本地假 Provider 和假凭据。它不是生产失败 fallback，不读取或覆盖正式项目数据；默认 `pnpm dev:web` 仍使用真实 DeepSeek 配置。

需要用真实云端 DeepSeek 验证同一套 Web 交互时：

```powershell
pnpm dev:web:paid
```

`dev:web:paid` 是内部真实云端验收配置，使用隔离目录 `.data/web-paid`，不是产品的“付费模式”。Provider 为真实 DeepSeek，Key 仍只能来自后端环境变量 `ZHANGWEN_DEEPSEEK_API_KEY` 或 Windows Credential Manager，浏览器不会读取 Key。产品界面统一显示云端 LLM，顶栏只显示本地服务健康，设置页使用“测试云端连接”；创建项目、发送消息和测试连接仍可能调用真实模型并消耗 token。

建议先按 `docs/WEB_DEVELOPMENT.md` 的“真实云端模型最小验收顺序”只读确认内部配置，再由测试人员决定是否执行真实模型请求。自动测试和默认门禁不会调用真实云端模型。

- UI：`http://localhost:5173/`
- API 健康检查：`http://127.0.0.1:8100/api/health`

Tauri、Rust、Sidecar 生命周期、Windows Credential Manager 和本地设备/CAD 接口均由完整入口管理。桌面模式已实现受控串口扫描、连接和 MicroPython 文件操作；Web 模式仍严格禁用这些本地副作用。自动回归只使用 Mock transport，固件烧录和 Flash 擦除不属于自动验收。

## 验证

```powershell
pnpm typecheck
pnpm test:frontend
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api
cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml
```

自动测试只使用 fake provider 和 Mock 设备，不调用真实付费 LLM，不执行真实串口、Flash 或固件操作。

## 文档

- 产品基线：`docs/PRD.md`
- UI 契约：`docs/UI_CONTRACT.md`
- API/事件：`docs/API_EVENTS.md`
- 架构决策：`docs/DECISIONS.md`
- 当前任务：`CURRENT_TASK.md`
- 当前交接：`HANDOFF.md`
- Web 开发说明：`docs/WEB_DEVELOPMENT.md`

## 目录清理

预览会删除的可再生构建/测试目录：

```powershell
powershell -ExecutionPolicy Bypass -File scripts-dev/clean-generated.ps1 -WhatIf
```

执行清理：

```powershell
pnpm clean:generated
```

脚本不会删除 `.venv`、`node_modules`、`services/local-api/.data` 或 `.codex/config.toml`。
