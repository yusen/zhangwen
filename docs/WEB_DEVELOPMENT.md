# 掌问 Web Development Mode

日期：2026-07-10

## 定位

Browser Host 是显式的无设备开发入口；默认 `pnpm start` 启动完整 Tauri 本地应用，串口扫描、连接和上传仅在该桌面应用的“设备”Tab 中明确发起，但掌问仍只有一套产品：

```text
Browser Host / Tauri Host
        ↓
同一个 React 应用
        ↓
同一个 API Client
        ↓
FastAPI Sidecar
        ↓
三师领域层 / SQLite / LLM Provider / ToolRunner
```

Browser 与 Tauri 只在宿主能力上不同。Project、ExpertWorkspace、Conversation、SharedFact、Decision、Artifact、Handoff、ProjectCoordinator 和 ContextAssembler 不按平台分叉。

## 启动

```powershell
pnpm dev:web
```

或者两个终端分别运行：

```powershell
.venv\Scripts\python.exe -m uvicorn zhangwen.main:app --port 8100 --host 127.0.0.1 --app-dir services/local-api
pnpm --filter @zhangwen/desktop dev -- --host 127.0.0.1
```

浏览器入口：`http://localhost:5173`。API 默认：`http://127.0.0.1:8100`。非敏感 API 地址可用 `VITE_ZHANGWEN_API_BASE_URL` 覆盖；不得通过 Vite 环境传 Provider Key。

完整交互验收可使用不调用真实云端模型的内部 QA 隔离配置：

```powershell
pnpm dev:web:fake
```

该入口只为本地 Web 验收启用 `ZHANGWEN_LLM_TEST_MODE=fake`，并把数据目录切到 `.data/web-fake`。它不会读取正式 Key 或正式项目，不是生产 Provider 的自动 fallback；关闭进程后设置随子进程消失。

真实云端模型验收入口：

```powershell
pnpm dev:web:paid
```

`dev:web:paid` 是内部真实云端验收配置，使用 DeepSeek 和 `.data/web-paid` 隔离项目数据，不是产品的“付费模式”。后端只从 `ZHANGWEN_DEEPSEEK_API_KEY` 或 Windows Credential Manager 读取 Key，浏览器不持有凭据。产品界面统一显示云端 LLM，顶栏只显示本地服务健康，设置页使用“测试云端连接”；项目建议、聊天和连接测试均会产生真实 Provider 请求。`fake` 与 `paid` 仅作为内部启动配置互斥。

### 真实云端模型最小验收顺序

真实云端验收必须由测试人员显式启动，不进入普通自动测试，也不允许在 Provider 失败时自动切换到 fake。为控制调用量，单次验收按以下顺序进行：

1. 在后端环境或 Windows Credential Manager 配置测试 Key，运行 `pnpm dev:web:paid`。
2. 先只读确认 `/api/health` 返回 `llmTestMode: "paid"`、`usesPaidLlm: true`。这些字段仅用于内部诊断，不生成免费/付费产品标签；标准模式同样使用真实 Provider，因此其 `usesPaidLlm` 也为 `true`，只有显式 fake 配置为 `false`。
3. 需要验证凭据时，仅点击一次“测试云端连接”。
4. 使用最短需求创建一个测试项目；创建动作会调用 EntryRouter，属于一次真实计费请求。
5. 分别发送一条最短的 `@问题引导师`、`@智能工程师`、`@结构工程师` 消息，确认前台仍为一条时间线、回复者标签正确，后端三条消息分别进入对应的独立 `conversationId`。
6. 结束后按 `Ctrl+C` 停止启动器，确认 8100/5173 无残留监听。测试数据只保留在 `.data/web-paid`，不得复制到正式数据目录。

2026-07-11 已完成一次未发起模型请求的启动与只读验收：Health 与内部模式诊断正确，浏览器控制台无错误；没有点击连接测试、创建项目或发送消息，因此没有发起真实 DeepSeek 请求。此历史验收早于产品 UI 统一为云端 LLM 的决策。

## 模型服务

自动测试只使用 fake Provider。手工 Web 开发可选择在 FastAPI 进程环境设置 `ZHANGWEN_DEEPSEEK_API_KEY`，或使用当前已有后端 Windows Credential Manager 配置。

React 只读取 `keySaved` 和掩码状态，不读取真实 Key。Browser Host 不显示 Key 输入/清除控件，带 Web Host 标识或本地 Vite Origin 的 Key 提交会被后端拒绝。

## 平台能力

`apps/desktop/src/platform` 是唯一平台判断入口。Web Host 支持同一个 React、REST/SSE、FastAPI、SQLite 项目恢复和浏览器文件选择能力声明；不支持任意本地路径读写、原生窗口、Credential Store、Shell、串口扫描/连接、设备上传/Flash 和本地 CAD 执行。

设备页可显示已有摘要、Mock/Dry Run 结果和桌面能力说明，但不会发起设备操作。不支持能力同时受到前端 Capability Gate 和 FastAPI Host Gate 保护。

Web 文件上传接口尚未在当前基线中新增；项目资源仍必须由 FastAPI/SQLite 管理，禁止转为 LocalStorage/IndexedDB 主存储。

## 当前核心验收

- 从左侧创建项目，并由 EntryRouter 按需求推荐和选择参与智能体。
- 一个项目只显示一条聚合时间线和一份项目草稿；回复显示对应智能体名称。
- 输入框上方显示参与智能体胶囊，可输入 `@智能体` 指定下一位回复者。
- 底层仍按智能体使用独立 `conversationId`、私有记忆和最多 12 条有界 Provider 历史；所有智能体共享项目事实、决策、产物和公共硬件知识。
- 整组澄清提交。
- 生成并确认唯一推荐方案。
- 对话方案卡与右侧 Artifact 指向同一个版本。
- 浏览器刷新后从 FastAPI/SQLite 恢复项目、聚合消息与项目草稿。
- project/conversation/request/response turn 校验阻止旧 SSE 串线。
- Web Host 不能执行串口、上传、Flash、Shell 或本地 CAD。
- `dev:web:fake` 中实际通过 `@智能工程师` 和 `@结构工程师` 连续发送，页面保持单一 `CenterChat`，两条消息分别持久化到不同 `conversationId`，回复者名称和 metadata 与目标一致。

专业模式设置中的“智能体”使用目录化 Agent Skill 包：可编辑三师各自的 `SKILL.md` 和声明的参考 Markdown，保存到当前 Web 数据目录 overlay，下一次目标智能体回复生效；恢复默认会删除对应覆盖。界面另列出三师绑定的全部 Registry Skill 执行能力，其描述覆盖继续保存在 SQLite 同目录的 `skill-description-overrides.json`。普通模式不请求包配置；“公共知识”可新增、搜索和编辑公共硬件知识，三师运行时共享读取。以上均不改变 v22 schema。

`dev:web:fake` 的 Agent 包覆盖位于 `.data/web-fake/agent-packages`，`dev:web:paid` 位于 `.data/web-paid/agent-packages`，不会互相或与正式数据串线。Markdown 不能在 Web Host 获得 Shell、串口、设备、文件或 CAD 权限。

## 恢复桌面阶段

后续桌面集成恢复时保留并继续验证 Tauri/Rust Sidecar 生命周期、Windows Credential Manager、原生窗口/文件适配、真实串口/mpremote/esptool/Flash 确认点、本地 CAD/CadQuery、安装包、签名、自动更新和桌面视觉适配。恢复时不得复制 React、API、数据库或三师领域逻辑。
