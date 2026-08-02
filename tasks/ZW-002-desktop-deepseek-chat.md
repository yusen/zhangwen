# ZW-002 — 桌面应用运行、LLM设置与DeepSeek真实对话

本文件遵循根目录 `PLANS.md`，是 ZW-002 的 living ExecPlan 草案。当前版本只用于规划，等待用户确认后再修改业务代码。

## Background

ZW-001 已建立 Tauri + React + TypeScript 桌面壳、Python FastAPI Sidecar、共享 Contracts、三栏布局、永久中央主对话、右侧“工作 / 产物 / 设备”Tab、模拟浮窗和健康检查。

本轮重新定义 ZW-002：不再做“项目工作区与模拟助手”作为主线，而是让掌问成为可以从 Windows 桌面启动、配置 DeepSeek API、并通过真实 DeepSeek API 进行流式对话的本地桌面应用。

已读取并用于本计划的仓库事实：

- `AGENTS.md`
- `HANDOFF.md`
- `PLANS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/UI_CONTRACT.md`
- `docs/API_EVENTS.md`
- `docs/ACCEPTANCE.md`
- `docs/DECISIONS.md`
- `docs/COLLABORATION.md`
- `tasks/ZW-001-repository-bootstrap.md`
- 当前前端、Contracts、Python Sidecar、Tauri 和测试代码

外部 API 事实来源：

- DeepSeek Chat Completion 官方文档：`https://api-docs.deepseek.com/api/create-chat-completion`
- DeepSeek Models & Pricing 官方文档：`https://api-docs.deepseek.com/quick_start/pricing`
- DeepSeek Error Codes 官方文档：`https://api-docs.deepseek.com/quick_start/error_codes`

## Current Baseline / Facts

- 当前 HEAD：`e5f989b chore: checkpoint Qoder bootstrap implementation`。
- 当前分支：`main`。
- 本地 `git tag --list` 未显示 `zw-001-complete` 标签；用户说明标签已建立，实施前应再次确认是否在远端或其他工作树。
- 当前工作树存在 ZW-001 后续启动脚本改动：`package.json`、`scripts-dev/start-local.ps1`、`start-local.bat`，以及旧版任务草案 `tasks/ZW-002-project-conversation-persistence.md`。本任务不得把这些改动当作 DeepSeek 功能实现。
- `apps/desktop/src-tauri/tauri.conf.json` 已存在 Tauri v2 配置，`devUrl` 为 Vite `http://localhost:5173`，`frontendDist` 为 `../dist`；尚未集成 Python Sidecar 进程生命周期。
- `apps/desktop/src/components/layout/AppShell.tsx` 维持 `CenterChat` 常驻，管理右侧 Tab 和模拟浮窗。
- `TopBar.tsx` 已有健康指示器和用户头像位置，可复用为设置齿轮入口。
- `CenterChat.tsx` 当前自持消息和草稿，发送后用 `setTimeout` 添加“模拟回复”。ZW-002 必须替换为真实 LLM 流程；未配置 API Key 时不得模拟真实回复。
- `api.ts` 目前固定调用 `http://127.0.0.1:8100`，只支撑健康检查。
- Python Sidecar 当前只有 `/api/health`，没有 LLM 配置、密钥存储、连接测试、聊天流或取消 API。
- `packages/contracts` 当前只有项目/任务/产物/设备状态枚举、`HealthResponse`、`ZwError` 和事件类型；没有 LLM Gateway、设置状态或流式事件契约。
- 自动测试当前覆盖 ZW-001 布局、右侧 Tab、草稿保留、浮窗不替换主对话、健康检查。

## Goal

让用户可以从 Windows 桌面开发入口启动掌问 Tauri 应用，在右上角设置浮窗中配置 DeepSeek API，并在中央永久主对话中发送消息、看到真实 DeepSeek 流式回复、停止生成、重试和获得中文错误提示。

## Scope

### Desktop Runtime

- 掌问正式运行形态为 Tauri 桌面应用。
- Vite 仅作为 Tauri 开发模式内部前端服务，不作为正式产品入口。
- 提供统一桌面开发启动命令。
- 验证 Tauri 窗口可启动。
- 验证桌面窗口可连接 Python Sidecar。
- 提供 Windows 桌面构建命令。
- 条件允许时生成 Windows 可执行程序或安装包。
- 集成 Sidecar 随 Tauri 启动和关闭的生命周期，开发模式可保留独立调试脚本。

### Settings Entry

- 在右上角用户名称或头像旁加入简洁小齿轮按钮。
- 点击齿轮打开设置浮窗。
- 设置浮窗不替换中央主对话、不卸载 `MainConversation` / `CenterChat`、不清空未发送草稿。
- 浮窗可关闭，支持 Escape、Tab 顺序、按钮可聚焦和基础 ARIA。
- 设置保存、清除、测试连接成功或失败时给出明确中文反馈。

### DeepSeek Configuration

LLM 设置页至少支持：

- 服务商：DeepSeek。
- API Base URL，默认 `https://api.deepseek.com`。
- API Key，输入时可明文编辑，保存后 UI 只显示掩码。
- 默认模型，下拉选择：
  - `deepseek-v4-flash`
  - `deepseek-v4-pro`
- 思考模式：
  - 自动
  - 关闭
  - 开启
- 高级设置：请求超时；如采用 `reasoning_effort`，只作为 DeepSeek Provider 专属参数。
- 测试连接。
- 保存。
- 清除配置。

### API Key Safety

- API Key 不提交 Git。
- API Key 不写入普通项目 JSON。
- API Key 不出现在日志、错误信息、测试快照或前端 console。
- 优先使用操作系统安全凭据存储。
- UI 只显示掩码后的 Key。
- 前端不长期保存 API Key 明文。
- DeepSeek 请求由 Python Sidecar 发起；React 主对话不直接调用 DeepSeek。

### LLM Gateway

建立供应商无关边界：

- `LLMProvider`
- `LLMConfig`
- `ModelConfig`
- `ChatRequest`
- `ChatMessage`
- `ChatResponse`
- `StreamChunk`
- `LLMError`
- `ConnectionTestResult`

实现 `DeepSeekProvider implements LLMProvider`。主对话组件只依赖通用 chat/config API，不依赖 DeepSeek SDK、DeepSeek 专属响应对象或 DeepSeek 专属参数。

### Real Conversation

中央主对话支持：

- 用户发送文本。
- 调用真实 DeepSeek API。
- 流式显示模型回复。
- 显示生成中状态。
- 停止生成。
- 网络错误提示。
- API Key 错误提示。
- 余额不足提示。
- 限流提示。
- 服务繁忙提示。
- 超时提示。
- 重试。
- 模型选择。
- 当前模型标识。

没有有效 API 配置时：

- 禁止发送真实请求。
- 明确提示用户前往设置。
- 不得使用模拟回复伪装成真实 LLM 结果。

## Non-goals

ZW-002 不实现：

- OpenAI、Anthropic 等其他供应商的正式接入。
- 完整 Model Router。
- Agent Registry。
- Skill Registry。
- 总控 Agent。
- 推荐实现方案。
- 硬件推荐。
- 立项书。
- 真实产物生成。
- 串口。
- MicroPython 上传。
- 固件烧录。
- CAD。
- 教案。
- 分享。
- 云端用户注册。
- 对话云同步。
- 项目 CRUD、本地项目持久化和项目工作区完整恢复。

架构必须允许以后增加其他供应商，但本轮只交付 DeepSeek。

## Future Task Candidates

旧草案 `tasks/ZW-002-project-conversation-persistence.md` 已被本任务方向替代，不再作为当前 ZW-002 执行计划保留。其中仍有价值的内容应作为后续任务候选重新立项：

- 本地项目工作区：创建、列表、打开、重命名、归档策略和最近项目恢复。
- 主对话项目级状态：每个项目独立消息、草稿、滚动位置和最近活动。
- 本地持久化：由 Python Sidecar 管理项目数据，开发阶段可用 JSON 项目文件，后续根据查询、审计和并发需求迁移到 SQLite。
- 数据版本和迁移：项目持久化版本、原子写入、备份恢复和未知版本错误处理。
- 右侧“工作”Tab 的项目基础状态联动。

这些内容不得混入本轮 DeepSeek 真实对话任务；需要在 ZW-003 或新的任务编号中重新确认范围后实施。

## Architecture

### High-level Flow

```text
Tauri Desktop Window
  └─ React UI
      ├─ TopBar Settings Gear
      ├─ Settings Floating Window
      └─ Permanent CenterChat
          ↓ HTTP / SSE on loopback
Python FastAPI Sidecar
  ├─ Settings API
  ├─ Secure Credential Adapter
  ├─ LLM Gateway
  │   └─ DeepSeekProvider
  └─ Streaming Chat Session Registry
      ↓ HTTPS
DeepSeek Chat Completion API
```

### Reusable ZW-001 Modules

- `AppShell.tsx`
  - 保留根布局、右侧 Tab 状态和中央对话常驻。
  - 新增设置浮窗状态时，不改变 `CenterChat` 的位置和 key。
- `TopBar.tsx`
  - 复用右侧头像区域，加入齿轮按钮。
  - 保留健康检查指示器。
- `CenterChat.tsx`
  - 复用主对话外壳和输入位置。
  - 需要移除模拟助手主路径，改为真实 LLM 状态机和流式渲染。
- `ChatInput.tsx`
  - 复用受控输入接口。
  - 需要支持禁用原因、生成中停止按钮或外部停止动作。
- `FloatingWindow.tsx`
  - 可作为设置浮窗的基础，但建议抽象出通用 `ModalWindow` / `SettingsDialog`，保持中央对话不卸载。
- `RightPanel.tsx`
  - 保持三个一级 Tab 不变，不承载设置入口。
- `api.ts`
  - 扩展为 typed API client，支持普通 JSON API 和 SSE/stream client。
- `useHealthCheck.ts`
  - 继续用于桌面窗口连接 Sidecar 的状态反馈。
- Python `main.py` / `config.py`
  - 增加 settings、llm、chat 路由。
- `packages/contracts`
  - 增加 LLM、设置、聊天流事件和错误契约。

## Security Design

### Recommended Credential Storage

优先方案：Python Sidecar 使用操作系统安全凭据存储。

- Windows：Windows Credential Manager。
- Python 建议依赖：`keyring`。
- 存储服务名：`zhangwen.deepseek`。
- 存储账号名：`default` 或本地 profile id。
- Sidecar 保存 API Key 时只进入 Credential Manager；普通配置文件只存非敏感字段。

安全备选方案：如果 `keyring` 在当前 Windows/Tauri 打包环境不可用，则使用用户目录下加密文件作为临时方案。

- Windows 使用 DPAPI，例如 Python `win32crypt` / `cryptography` 可用方案。
- 加密文件放入应用数据目录，而不是项目目录。
- 文件中只保存密文和元信息，不保存明文。
- Decision Log 必须记录为什么没有使用系统凭据存储。

不推荐方案：

- 不在 React localStorage/sessionStorage 中保存 Key。
- 不在 `services/local-api/.data` 或项目 JSON 中保存明文 Key。
- 不通过 URL、query string、日志、异常字符串传递 Key。

### Non-sensitive Config Storage

非敏感配置由 Sidecar 保存到应用级配置文件，例如：

```text
%LOCALAPPDATA%/Zhangwen/config/llm.json
```

开发模式可使用：

```text
services/local-api/.data/config/llm.json
```

保存字段：

- provider: `deepseek`
- baseUrl
- defaultModel
- thinkingMode
- reasoningEffort
- timeoutSeconds
- keySaved: boolean
- maskedApiKey
- updatedAt

### Secret Handling Rules

- Sidecar 从 Credential Manager 读取 API Key，在内存中只保留完成当前请求所需时间。
- 所有日志通过脱敏函数处理 headers、authorization、apiKey、token 字段。
- API 错误返回 `ZwError` / `LLMError`，不得包含请求头、完整上游 payload 或 API Key。
- 前端 `console` 不打印配置对象中的敏感字段。
- 测试使用假的 API Key 和 Mock Transport，不访问真实 DeepSeek 服务。

## Data Model

### Contracts: General LLM

```ts
export const LLMProviderId = {
  DEEPSEEK: "deepseek",
} as const;

export const LLMModelId = {
  DEEPSEEK_V4_FLASH: "deepseek-v4-flash",
  DEEPSEEK_V4_PRO: "deepseek-v4-pro",
} as const;

export const ThinkingMode = {
  AUTO: "AUTO",
  DISABLED: "DISABLED",
  ENABLED: "ENABLED",
} as const;

export interface ModelConfig {
  id: LLMModelId;
  label: string;
  provider: LLMProviderId;
  supportsThinking: boolean;
  supportsStreaming: boolean;
}

export interface LLMConfig {
  provider: LLMProviderId;
  baseUrl: string;
  defaultModel: LLMModelId;
  thinkingMode: ThinkingMode;
  timeoutSeconds: number;
  keySaved: boolean;
  maskedApiKey: string | null;
  updatedAt: string | null;
}
```

### Contracts: Chat

```ts
export const ChatRole = {
  SYSTEM: "system",
  USER: "user",
  ASSISTANT: "assistant",
} as const;

export const ChatMessageStatus = {
  READY: "READY",
  SENDING: "SENDING",
  STREAMING: "STREAMING",
  COMPLETED: "COMPLETED",
  FAILED: "FAILED",
  CANCELED: "CANCELED",
} as const;

export interface ChatMessage {
  id: string;
  role: ChatRole;
  content: string;
  reasoningContent?: string;
  status: ChatMessageStatus;
  createdAt: string;
  updatedAt: string;
  model?: LLMModelId;
  error?: LLMError;
}

export interface ChatRequest {
  messages: ChatMessage[];
  model?: LLMModelId;
  abortPrevious?: boolean;
}

export interface ChatResponse {
  message: ChatMessage;
  usage?: TokenUsage;
  finishReason?: string;
}
```

### Contracts: Stream Events

```ts
export const StreamChunkType = {
  START: "START",
  CONTENT_DELTA: "CONTENT_DELTA",
  REASONING_DELTA: "REASONING_DELTA",
  COMPLETED: "COMPLETED",
  ERROR: "ERROR",
  CANCELED: "CANCELED",
} as const;

export interface StreamChunk {
  requestId: string;
  messageId: string;
  type: StreamChunkType;
  delta?: string;
  accumulatedContent?: string;
  accumulatedReasoning?: string;
  model?: LLMModelId;
  error?: LLMError;
  usage?: TokenUsage;
}
```

### Contracts: Errors

```ts
export const LLMErrorCode = {
  CONFIG_MISSING: "CONFIG_MISSING",
  INVALID_REQUEST: "INVALID_REQUEST",
  AUTH_FAILED: "AUTH_FAILED",
  INSUFFICIENT_BALANCE: "INSUFFICIENT_BALANCE",
  INVALID_PARAMETERS: "INVALID_PARAMETERS",
  RATE_LIMITED: "RATE_LIMITED",
  SERVER_ERROR: "SERVER_ERROR",
  SERVICE_BUSY: "SERVICE_BUSY",
  NETWORK_UNAVAILABLE: "NETWORK_UNAVAILABLE",
  TIMEOUT: "TIMEOUT",
  CANCELED: "CANCELED",
  SIDECAR_UNAVAILABLE: "SIDECAR_UNAVAILABLE",
  UNKNOWN: "UNKNOWN",
} as const;

export interface LLMError {
  code: LLMErrorCode;
  message: string;
  retryable: boolean;
  userActions: UserAction[];
  providerStatus?: number;
}
```

## API and Streaming Events

### Sidecar HTTP APIs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/settings/llm` | 获取非敏感 LLM 配置和 Key 保存状态 |
| `PUT` | `/api/settings/llm` | 保存 Base URL、默认模型、思考模式、超时和可选 API Key |
| `DELETE` | `/api/settings/llm/api-key` | 清除保存的 API Key |
| `POST` | `/api/settings/llm/test` | 使用当前或提交的配置测试连接 |
| `GET` | `/api/llm/models` | 返回可选模型与能力声明 |
| `POST` | `/api/chat/stream` | 发起真实 LLM 对话，返回 SSE |
| `POST` | `/api/chat/cancel/{requestId}` | 取消正在进行的生成 |

### SSE vs WebSocket Decision

推荐 ZW-002 使用 SSE：

- DeepSeek Chat Completion 官方流式响应本身是 SSE。
- 本轮只有单向 token 流，从 Sidecar 到 UI，SSE 更小、更容易测试。
- 停止生成可用单独 `POST /api/chat/cancel/{requestId}`。
- 未来 Agent、设备日志、任务状态多路事件进入后，再统一升级或补充 WebSocket。

SSE 事件建议：

```text
event: chat.start
data: { StreamChunk START }

event: chat.delta
data: { StreamChunk CONTENT_DELTA | REASONING_DELTA }

event: chat.completed
data: { StreamChunk COMPLETED }

event: chat.error
data: { StreamChunk ERROR }

event: chat.canceled
data: { StreamChunk CANCELED }
```

### Cancellation and Concurrency

- Sidecar 为每个请求生成 `requestId`。
- Sidecar `ChatSessionRegistry` 保存 `requestId -> cancellation token / async task`。
- UI 同一会话默认只允许一个活动生成请求。
- 新请求发起时：
  - 若已有活动请求，UI 先要求停止或 Sidecar 按 `abortPrevious` 取消旧请求。
  - 防止旧请求的 delta 写入新消息：每个 chunk 必须带 `requestId` 和 `messageId`，前端只接受当前活动请求。
- 用户点击停止时调用 cancel API，同时关闭 SSE reader；Sidecar 取消上游 HTTP 流并返回 CANCELED。

## DeepSeekProvider Design

### Provider Boundary

Python 内部接口：

```py
class LLMProvider(Protocol):
    async def test_connection(self, config: LLMConfig, api_key: str) -> ConnectionTestResult: ...
    async def stream_chat(
        self,
        request: ChatRequest,
        config: LLMConfig,
        api_key: str,
        cancel_token: CancelToken,
    ) -> AsyncIterator[StreamChunk]: ...
```

`DeepSeekProvider` 负责：

- 将通用 `ChatRequest` 映射为 DeepSeek `/chat/completions` 请求。
- 添加 `Authorization: Bearer <api_key>`。
- 设置 `model` 为 `deepseek-v4-flash` 或 `deepseek-v4-pro`。
- 设置 `stream: true` 和 `stream_options.include_usage: true`。
- 根据通用 `ThinkingMode` 映射 DeepSeek 专属 `thinking`：
  - `AUTO`：不传 `thinking`，使用 DeepSeek 默认。
  - `DISABLED`：传 `{ "type": "disabled" }`。
  - `ENABLED`：传 `{ "type": "enabled", "reasoning_effort": ... }`，`reasoning_effort` 仅在 DeepSeek provider 内解释。
- 解析 SSE 中的 `delta.content` 和 `delta.reasoning_content`。
- 映射 `finish_reason`：`stop`、`length`、`content_filter`、`tool_calls`、`insufficient_system_resource`。
- 将 DeepSeek HTTP 错误和网络错误转换为通用 `LLMError`。

### DeepSeek API Facts

官方 Chat Completion 文档显示：

- 请求路径为 `POST /chat/completions`。
- 模型值支持 `deepseek-v4-flash` 和 `deepseek-v4-pro`。
- `stream: true` 时使用 data-only SSE，结束为 `data: [DONE]`。
- `thinking` 可控制 thinking / non-thinking，`type` 为 `enabled` 或 `disabled`。
- `reasoning_effort` 支持 `high` / `max`，兼容映射 `low` / `medium` 到 `high`，`xhigh` 到 `max`。
- 官方错误码包括 400、401、402、422、429、500、503。

## UI Interaction

### Settings Floating Window

结构：

```text
TopBar
  └─ user avatar
  └─ gear button aria-label="打开设置"

SettingsDialog
  ├─ title: 设置
  ├─ section: LLM 服务
  │   ├─ provider: DeepSeek (disabled/select with one option)
  │   ├─ API Base URL
  │   ├─ API Key input
  │   ├─ default model select
  │   ├─ thinking mode segmented/select
  │   ├─ timeout seconds input
  │   └─ optional advanced reasoning effort
  ├─ actions: 测试连接 / 保存 / 清除配置 / 关闭
  └─ feedback region role="status" / role="alert"
```

UI 规则：

- 设置浮窗通过 overlay 或 dialog 渲染，不影响 `CenterChat`。
- 关闭后草稿保留。
- API Key 保存后输入框显示掩码，如 `sk-****abcd`，不保留完整明文。
- 若用户编辑 Key，前端只在内存中暂存输入框值，保存/测试后清空明文字段。
- 测试连接期间按钮显示进行中状态。
- 错误文案中文且可执行，如“API Key 验证失败，请检查设置中的 Key”。

### Main Conversation Real LLM Flow

1. UI 启动后读取 `/api/settings/llm`。
2. 若未保存有效 Key，发送区域显示“请先在设置中配置 DeepSeek API Key”，发送按钮禁用或点击后打开设置提示。
3. 用户输入并发送文本。
4. `CenterChat` 添加用户消息，并创建 assistant 占位消息，状态为 `STREAMING`。
5. UI 打开 `/api/chat/stream` SSE。
6. Sidecar 从安全凭据读取 Key，调用 DeepSeek。
7. 每个 `CONTENT_DELTA` 追加到 assistant 消息；可选 `REASONING_DELTA` 在简洁 UI 中默认折叠或不展示，仅保留状态提示。
8. 完成后 assistant 消息状态变为 `COMPLETED`，显示模型标识。
9. 用户点击停止时，消息状态变为 `CANCELED`，保留已生成内容。
10. 错误时消息状态变为 `FAILED`，显示中文错误和“重试”动作。

## Error Handling

| Case | Internal Code | User Message | Retryable |
|---|---|---|---|
| 未配置 Key | `CONFIG_MISSING` | 请先在设置中配置 DeepSeek API Key。 | false |
| 400 请求格式错误 | `INVALID_REQUEST` | 请求格式有误，请稍后重试或更新应用。 | false |
| 401 认证失败 | `AUTH_FAILED` | API Key 验证失败，请检查设置中的 Key。 | false |
| 402 余额不足 | `INSUFFICIENT_BALANCE` | DeepSeek 账户余额不足，请充值后重试。 | false |
| 422 参数错误 | `INVALID_PARAMETERS` | 模型参数不被支持，请检查模型或思考模式设置。 | false |
| 429 限流 | `RATE_LIMITED` | 请求太频繁，请稍后再试。 | true |
| 500 服务端错误 | `SERVER_ERROR` | DeepSeek 服务暂时出错，请稍后重试。 | true |
| 503 服务繁忙 | `SERVICE_BUSY` | DeepSeek 当前繁忙，请稍后重试。 | true |
| 本地网络不可用 | `NETWORK_UNAVAILABLE` | 本机网络不可用，请检查网络连接。 | true |
| 请求超时 | `TIMEOUT` | 请求超时，请稍后重试或调大超时时间。 | true |
| 用户主动取消 | `CANCELED` | 已停止生成。 | true |
| Sidecar 未启动 | `SIDECAR_UNAVAILABLE` | 本地服务未连接，请重启桌面应用。 | true |

错误处理要求：

- 上游错误详情只写入脱敏技术日志。
- UI 不显示 API Key、Authorization header、完整敏感 payload。
- `technicalDetails` 默认不返回前端；如返回也必须脱敏。

## Tauri and Sidecar Lifecycle

### Development Mode

推荐新增统一命令：

```powershell
pnpm dev:tauri
```

期望行为：

- 启动 Python Sidecar。
- 启动 Tauri dev。
- Tauri 使用 Vite `devUrl` 作为内部前端。
- 关闭 Tauri 后 Sidecar 退出。

可选路径：

- 若 Tauri v2 sidecar 打包尚未完成，开发模式可用 PowerShell 脚本编排 `uvicorn` + `pnpm --filter @zhangwen/desktop tauri dev`。
- 但产品正式入口仍必须是 Tauri 窗口，不把浏览器作为正式入口。

### Production / Build

目标命令：

```powershell
pnpm build:desktop
pnpm tauri:build
```

构建要求：

- 前端先构建到 `apps/desktop/dist`。
- Tauri 打包时包含或启动 Sidecar。
- Windows 构建配置有效；条件允许时产出 `.exe` 或 installer。

Sidecar 打包方案待实施时验证：

- 方案 A：Python Sidecar 使用 PyInstaller 打包为 sidecar executable，并在 `tauri.conf.json` 声明 externalBin。
- 方案 B：开发阶段保留 Python 解释器启动，生产打包前补齐 PyInstaller。

推荐 ZW-002 采用方案 A 作为目标；如果环境缺 PyInstaller 或打包链受限，必须记录为未通过项，不能声称 Windows 安装包完成。

## Contracts Changes

预计修改：

- `packages/contracts/src/enums.ts`
  - 增加 `LLMProviderId`、`LLMModelId`、`ThinkingMode`、`ChatRole`、`ChatMessageStatus`、`StreamChunkType`、`LLMErrorCode`。
- `packages/contracts/src/api.ts`
  - 增加 settings、connection test、chat request/response、error 类型。
- 可新增 `packages/contracts/src/llm.ts`
  - 如果 `api.ts` 过大，独立保存 LLM Gateway 领域类型。
- `packages/contracts/src/events.ts`
  - 增加或复用 `chat.delta`、`chat.completed`，补充 `chat.started`、`chat.error`、`chat.canceled` 是否需要进入统一事件枚举。
- `packages/contracts/src/index.ts`
  - 导出新增类型。

DeepSeek 专属字段不进入所有 provider 必填字段；`reasoning_effort` 放入 DeepSeek provider 配置或 `providerOptions.deepseek`，不污染通用 `ChatRequest`。

## Expected File Changes

### Contracts

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/events.ts`
- `packages/contracts/src/index.ts`
- 可选：`packages/contracts/src/llm.ts`

### Python Sidecar

- `services/local-api/requirements.txt`
- `services/local-api/requirements-lock.txt`
- `services/local-api/zhangwen/config.py`
- `services/local-api/zhangwen/main.py`
- `services/local-api/zhangwen/settings/router.py`
- `services/local-api/zhangwen/settings/models.py`
- `services/local-api/zhangwen/settings/repository.py`
- `services/local-api/zhangwen/security/credentials.py`
- `services/local-api/zhangwen/security/redaction.py`
- `services/local-api/zhangwen/llm/contracts.py`
- `services/local-api/zhangwen/llm/gateway.py`
- `services/local-api/zhangwen/llm/deepseek.py`
- `services/local-api/zhangwen/chat/router.py`
- `services/local-api/zhangwen/chat/sessions.py`
- `services/local-api/tests/test_llm_settings.py`
- `services/local-api/tests/test_deepseek_provider.py`
- `services/local-api/tests/test_chat_stream.py`
- `services/local-api/tests/test_secret_redaction.py`

### Desktop / Frontend

- `apps/desktop/package.json`
- `apps/desktop/src-tauri/Cargo.toml`
- `apps/desktop/src-tauri/tauri.conf.json`
- `apps/desktop/src-tauri/src/lib.rs`
- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/TopBar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/chat/ChatInput.tsx`
- `apps/desktop/src/components/settings/SettingsDialog.tsx`
- `apps/desktop/src/components/settings/LlmSettingsPanel.tsx`
- `apps/desktop/src/hooks/useLlmSettings.ts`
- `apps/desktop/src/hooks/useChatStream.ts`
- `apps/desktop/src/services/api.ts`
- `apps/desktop/src/services/llmApi.ts`
- `apps/desktop/src/__tests__/SettingsDialog.test.tsx`
- `apps/desktop/src/__tests__/DeepSeekChat.test.tsx`
- `apps/desktop/src/__tests__/DesktopInvariants.test.tsx`

### Scripts and Docs

- `package.json`
- `scripts-dev/start-local.ps1` or new `scripts-dev/dev-tauri.ps1`
- `start-local.bat` if retained as desktop launcher wrapper
- `docs/API_EVENTS.md`
- `docs/DECISIONS.md`
- `HANDOFF.md`
- `tasks/ZW-002-desktop-deepseek-chat.md`

## Implementation Milestones

### M1 — Contracts-first LLM Gateway

Expected files:

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts` or `packages/contracts/src/llm.ts`
- `packages/contracts/src/events.ts`
- `packages/contracts/src/index.ts`

Validation:

```powershell
pnpm --filter @zhangwen/contracts build
pnpm --filter @zhangwen/contracts typecheck
```

Acceptance:

- All required ZW-002 LLM types exist in shared Contracts.
- DeepSeek model IDs are constrained to dropdown-supported values.
- DeepSeek-specific options are isolated.

### M2 — Sidecar Settings and Credential Storage

Expected files:

- `services/local-api/zhangwen/settings/*`
- `services/local-api/zhangwen/security/*`
- `services/local-api/zhangwen/config.py`
- `services/local-api/zhangwen/main.py`
- dependency files if `keyring` or DPAPI helper is added

Validation:

```powershell
.\.venv\Scripts\python.exe -m pip install -r services/local-api/requirements.txt
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_llm_settings.py -v --rootdir services/local-api
```

Acceptance:

- Save/read non-sensitive config works.
- API Key stored via OS credential adapter or documented secure fallback.
- GET config returns only `keySaved` and `maskedApiKey`.
- Clear config removes secret.
- Logs and errors are redacted.

### M3 — DeepSeekProvider and Mocked Streaming

Expected files:

- `services/local-api/zhangwen/llm/*`
- `services/local-api/zhangwen/chat/*`
- tests for provider mapping, streaming, cancellation and errors

Validation:

```powershell
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_deepseek_provider.py services/local-api/tests/test_chat_stream.py -v --rootdir services/local-api
```

Acceptance:

- Provider maps generic request to DeepSeek payload.
- SSE parser emits content and reasoning chunks.
- Cancellation stops active request.
- 401/402/429/500/503 and timeout are mapped to Chinese-safe errors.
- Tests use mock HTTP transport and never call real DeepSeek.

### M4 — Settings UI

Expected files:

- `TopBar.tsx`
- `AppShell.tsx`
- `SettingsDialog.tsx`
- `LlmSettingsPanel.tsx`
- `useLlmSettings.ts`
- `llmApi.ts`
- settings tests

Validation:

```powershell
pnpm --filter @zhangwen/desktop typecheck
pnpm --filter @zhangwen/desktop test
```

Acceptance:

- Gear opens settings floating window.
- Settings does not unmount or duplicate `CenterChat`.
- Draft survives settings open/close.
- API Key is masked after save.
- Model dropdown supports Flash and Pro.
- Connection test feedback is correct.

### M5 — Real Streaming Chat UI

Expected files:

- `CenterChat.tsx`
- `ChatInput.tsx`
- `useChatStream.ts`
- `llmApi.ts`
- chat tests

Validation:

```powershell
pnpm --filter @zhangwen/desktop typecheck
pnpm --filter @zhangwen/desktop test
```

Acceptance:

- Unconfigured Key blocks real send and prompts settings.
- Configured chat streams assistant reply incrementally.
- Stop generation restores input state and marks message canceled.
- Retry resends failed message.
- Current model is visible but compact.
- Error prompts are Chinese and do not leak secrets.

### M6 — Tauri Desktop Lifecycle and Build

Expected files:

- `apps/desktop/package.json`
- `apps/desktop/src-tauri/tauri.conf.json`
- `apps/desktop/src-tauri/Cargo.toml`
- `apps/desktop/src-tauri/src/lib.rs`
- root `package.json`
- scripts under `scripts-dev/`

Validation:

```powershell
pnpm dev:tauri
pnpm build:desktop
pnpm tauri:build
cargo metadata --no-deps --format-version 1
cargo check
```

Acceptance:

- Tauri dev window starts.
- Window connects to Sidecar health endpoint.
- Closing app stops Sidecar in dev/prod path.
- Windows build config parses.
- If environment supports it, executable/installer is produced; otherwise exact blocker is recorded.

### M7 — Full Validation and Handoff

Expected files:

- `docs/API_EVENTS.md`
- `docs/DECISIONS.md`
- `HANDOFF.md`
- this task file

Validation:

```powershell
pnpm typecheck
pnpm test:frontend
pnpm build:desktop
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/ -v --rootdir services/local-api
cargo metadata --no-deps --format-version 1
cargo check
python scripts/check_ai_assets.py
git status --short
```

Acceptance:

- All executed commands and real outputs are recorded.
- Any skipped desktop packaging or real API smoke test has concrete reason.
- No API Key or local credentials are staged or logged.

## Automatic Test Plan

### UI Tests

- 点击右上角齿轮打开设置浮窗。
- 打开设置不卸载、不重复创建 `CenterChat`。
- 设置开关不丢失草稿。
- API Key 保存后只显示掩码。
- 未配置 Key 时发送按钮给出设置提示。
- 模型可在 DeepSeek V4 Flash 与 DeepSeek V4 Pro 之间切换。
- 连接测试成功、失败、进行中状态正确显示。
- Mock SSE 流式消息逐步更新。
- 停止生成后状态恢复，已生成内容保留。
- 401/402/429/500/503 等错误提示为中文。

### Sidecar Tests

- LLM 配置验证。
- API Key 保存、读取、清除和掩码。
- 非敏感配置持久化。
- DeepSeek 请求映射：baseUrl、model、messages、stream、thinking、timeout。
- 流式 SSE 解析：content delta、reasoning delta、usage、DONE。
- 取消请求。
- 超时。
- 400、401、402、422、429、500、503 错误映射。
- 网络不可用映射。
- 日志脱敏。
- Mock 测试禁止真实 DeepSeek 网络访问。

### Desktop Tests / Checks

- Tauri 开发窗口可启动。
- Sidecar 随桌面应用启动。
- 关闭应用时 Sidecar 正确退出。
- 设置浮窗不替换中央对话。
- Windows 构建配置有效。
- 条件允许时验证 `.exe` 或 installer 产物存在。

## Manual Acceptance Steps

1. 运行统一桌面开发启动命令。
2. 确认打开的是 Tauri 桌面窗口，不是浏览器正式入口。
3. 确认健康指示器显示 Sidecar 已连接。
4. 在中央对话输入草稿。
5. 点击右上角齿轮打开设置，确认草稿仍在。
6. 保存 DeepSeek Base URL、API Key、默认模型和思考模式。
7. 关闭并重新打开设置，确认 Key 只显示掩码。
8. 点击测试连接，确认成功或失败反馈清晰。
9. 在中央主对话发送消息，确认真实流式回复逐步出现。
10. 生成过程中点击停止，确认状态恢复且已生成文本保留。
11. 切换“工作 / 产物 / 设备”和打开模拟浮窗，确认主对话仍在且草稿不丢。
12. 改用错误 Key，确认显示中文认证失败，不泄露 Key。
13. 模拟余额不足、限流、服务繁忙和超时，确认错误映射。
14. 关闭桌面应用，确认 Sidecar 退出。
15. 运行 Windows 构建命令，记录产物或环境阻塞原因。

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| OS 凭据存储在打包后不可用 | API Key 无法安全保存 | 抽象 credential adapter；先用 `keyring`，失败时记录 DPAPI 备选 |
| Tauri sidecar 打包复杂 | 无法生成完整 Windows 安装包 | 分阶段验证 dev lifecycle 与 PyInstaller externalBin；不可用则记录 blocker |
| SSE 在 Tauri WebView 中行为差异 | 流式显示不稳定 | 前端 stream client 封装，单测 mock ReadableStream，手工验证 Tauri window |
| 多个流并发污染消息 | 用户看到错乱回复 | requestId/messageId 校验；同会话只允许一个活动请求 |
| API Key 泄漏到日志或测试快照 | 严重安全问题 | 统一 redaction；测试断言敏感值不出现 |
| 真实 API 测试消耗额度 | 成本和隐私风险 | 自动测试只用 mock；真实 smoke test 手工且显式 opt-in |
| DeepSeek API 变更 | 请求失败或模型不可用 | Provider 隔离；模型列表集中定义；参考官方文档并记录日期 |
| ZW-001 启动脚本未提交改动混入 | 交接混乱 | 实施前明确这些文件归属，提交或整理为本任务桌面启动部分 |

## Decision Log

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | ZW-002 任务方向 | 桌面应用 + DeepSeek 真实对话 | 用户重新定义本阶段目标 |
| 2026-07-08 | 正式入口 | Tauri 桌面窗口 | PRD 与用户要求明确浏览器不是正式入口 |
| 2026-07-08 | LLM 调用位置 | Python Sidecar | 避免前端长期持有 Key；符合云端 LLM 不直接操作本地系统边界 |
| 2026-07-08 | 流式协议 | Sidecar 对 UI 使用 SSE | DeepSeek 上游为 SSE，本轮单向 token 流足够，复杂事件留给后续 WebSocket |
| 2026-07-08 | Key 存储优先级 | OS Credential Store via Python adapter | 满足 API Key 不进项目文件/日志/Git 的安全要求 |
| 2026-07-08 | DeepSeek 专属参数 | 隔离在 DeepSeekProvider | 保持 LLM Gateway 供应商无关 |
| 2026-07-08 | 自动测试网络策略 | Mock DeepSeek，不访问真实 API | 防止消耗额度和泄露真实密钥 |
| 2026-07-08 | Key 存储具体实现 | Windows Credential Manager（ctypes CredWriteW/CredReadW） | 不引入 keyring 第三方依赖；直接调用 Windows API；满足安全要求 |
| 2026-07-08 | Sidecar 生命周期管理 | Tauri Rust 代码管理（spawn on start, kill on close） | 开发模式脚本预启动时自动检测并跳过；关闭窗口时终止子进程 |
| 2026-07-08 | Windows 安装包打包 | 方案 B（开发阶段保留 Python 解释器启动） | PyInstaller 未安装；Tauri CLI 未安装；记录为环境阻塞项 |

## Handoff Requirements

实施开始、暂停、切换工具或提交前必须更新：

- 本任务 `Progress`。
- `HANDOFF.md`。
- 涉及 API/事件时更新 `docs/API_EVENTS.md`。
- 涉及安全/存储/桌面打包决策时更新 `docs/DECISIONS.md`。

记录内容必须包括：

- 已完成和未完成内容。
- 修改文件。
- 实际运行命令和结果。
- Tauri 窗口验证结果。
- Sidecar 生命周期验证结果。
- DeepSeek Mock 测试结果。
- 是否运行真实 API 手工测试；若运行，不能记录 Key。
- 当前失败项和阻塞原因。

## Progress

- [x] (2026-07-08) 读取 AGENTS、HANDOFF、PLANS、docs、ZW-001 任务、当前前端/Contracts/Python/Tauri/测试代码。
- [x] (2026-07-08) 核对当前 Git 和工作树事实：HEAD 为 `e5f989b`，本地未见 `zw-001-complete` 标签，存在启动脚本相关未提交改动。
- [x] (2026-07-08) 查询 DeepSeek 官方文档，确认 V4 模型名、Base URL、thinking、SSE 和错误码事实。
- [x] (2026-07-08) 创建本 ZW-002 计划草案。
- [x] (2026-07-08) 用户确认计划，Codex 确认当前分支为 `feature/zw-002-deepseek-chat`、工作树干净、`zw-001-complete` 存在且 HEAD 包含本任务文档。
- [x] (2026-07-08) M1 Contracts-first LLM Gateway 完成：共享 LLM、DeepSeek 模型、设置、聊天、流式和错误契约。contracts build + typecheck 通过。
- [x] (2026-07-08) M2 Sidecar Settings and Credential Storage 完成：settings router/service/repository、Windows Credential Manager（ctypes）、redaction 脱敏。13 项 Python 测试通过（含 health）。
- [x] (2026-07-08) M3 DeepSeekProvider and Mocked Streaming 完成：gateway/deepseek/errors/chat router/sessions。MockTransport 测试覆盖 payload 映射、SSE 解析、401 错误、取消、abortPrevious。
- [x] (2026-07-08) M4 Settings UI 完成：SettingsDialog/LlmSettingsPanel/useLlmSettings/llmApi。齿轮按钮打开浮窗、草稿保留、Key 掩码、模型切换、测试连接。27 项前端测试通过。
- [x] (2026-07-08) M5 Real Streaming Chat UI 完成：CenterChat 真实 LLM 流式对话、ChatInput 停止按钮、useChatStream SSE 客户端。未配置 Key 禁止发送、流式更新、停止生成、错误提示中文。
- [x] (2026-07-08) M6 Tauri Desktop Lifecycle and Build 完成：lib.rs Sidecar 生命周期管理（spawn on start, kill on close）、tauri.conf.json bundle 配置。cargo check + cargo build --release + pnpm build:desktop 通过。PyInstaller 和 Tauri CLI 未安装，记录为环境阻塞项。
- [x] (2026-07-08) M7 Full Validation and Handoff 完成：全部验证命令通过（typecheck、test、build、pip check、pytest、cargo metadata、cargo check、check_ai_assets）。HANDOFF.md、API_EVENTS.md、DECISIONS.md 已更新。

## Definition of Done

- 掌问可通过统一命令以 Tauri 桌面应用形式启动。
- Tauri 窗口可连接 Python Sidecar。
- Sidecar 可随桌面应用启动和关闭，或明确记录当前环境阻塞项。
- 设置齿轮入口存在于右上角头像/用户区域。
- 设置浮窗可打开/关闭，不替换中央主对话，不卸载 `CenterChat`，不清空草稿。
- DeepSeek Base URL、API Key、默认模型、思考模式、超时可配置。
- API Key 使用 OS 安全凭据存储或经 Decision Log 记录的安全备选方案。
- UI 只显示掩码 Key，日志/错误/测试不泄露 Key。
- LLM Gateway 通用契约存在，`DeepSeekProvider` 与 UI 解耦。
- 中央主对话可进行真实 DeepSeek 流式对话。
- 未配置 Key 时不能发送真实请求，且不会用模拟回复伪装真实 AI。
- 支持停止生成、重试、模型显示和中文错误提示。
- 400/401/402/422/429/500/503、网络、超时、取消、Sidecar 未启动均有映射。
- 自动测试覆盖 UI、Sidecar、Provider、流式、取消、错误和脱敏。
- Windows 构建命令可运行；条件允许时生成可执行程序或安装包，否则记录真实阻塞原因。
- `HANDOFF.md`、任务文件、相关契约文档和决策日志已更新。
