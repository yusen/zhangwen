# ZW-003 — 项目管理、会话历史与本地持久化

本文件遵循根目录 `PLANS.md`，是 ZW-003 的 living ExecPlan 与完成记录。用户已确认进入实现，当前实现与验证结果记录在本文 Progress 和 Implementation Results 中。

## Background

ZW-002 已将掌问推进到 Tauri 桌面入口、DeepSeek 设置、安全凭据存储、Sidecar LLM Gateway 和真实流式对话。当前缺口是：对话仍由前端 `CenterChat` 内存状态持有，左侧项目栏仍是 mock，真实 DeepSeek 回复不会写入本地项目历史，应用重启后无法恢复项目、消息、草稿或最近项目。

ZW-003 的目标是建立本地项目管理、项目级会话历史、草稿和模型选择持久化，并把真实 DeepSeek 对话写入当前项目历史。API Key 必须继续与项目数据完全隔离。

已读取并用于本计划的仓库事实：

- `AGENTS.md`
- `HANDOFF.md`
- `tasks/ZW-002-desktop-deepseek-chat.md`
- `docs/ARCHITECTURE.md`
- `docs/UI_CONTRACT.md`
- `docs/API_EVENTS.md`
- `docs/DECISIONS.md`
- 当前 `packages/contracts`
- 当前 Python Sidecar
- 当前 Tauri 配置与 sidecar 生命周期代码
- 当前主对话、项目栏、设置、聊天流和测试代码

## Current Baseline / Facts

- 当前分支：`feature/zw-002-deepseek-chat`。
- 当前 `git status --short --branch` 显示仅有未跟踪 `.qoder/repowiki/`；业务代码没有未提交改动。
- `HANDOFF.md` 记录 ZW-002 M1-M7 已完成并验证。
- `packages/contracts` 已有 LLM、Chat、StreamChunk、LLMError 等类型，但没有 `Project`、`ProjectSummary`、`Conversation`、`Draft`、`ProjectPersistenceVersion`、项目级模型选择和项目 API 契约。
- `CenterChat.tsx` 当前自持 `messages`、`draft`、`streaming`、`activeAssistantId`，通过 `/api/chat/stream` 发起真实 DeepSeek SSE；该请求没有 `projectId`，Sidecar 不持久化消息。
- `LeftSidebar.tsx` 当前使用 `MOCK_PROJECTS`。
- `TopBar.tsx` 当前固定显示“演示项目 / 阶段：构思”。
- `WorkTab.tsx` 当前仍是模拟 Agent 列表。
- Python `settings.data_dir` 当前为 `services/local-api/.data`；LLM 非敏感配置写入 `.data/config/llm.json`，API Key 走 Windows Credential Manager。
- Tauri `lib.rs` 负责启动/关闭 Python Sidecar，不负责项目数据访问。

## Goal

用户可以创建、打开、切换、重命名和归档本地项目。每个项目拥有独立对话历史、未发送草稿和模型选择。真实 DeepSeek 对话写入当前项目历史。应用重启后恢复项目列表、最近项目、消息和草稿。数据有 schema 版本和迁移入口。中央 MainConversation 继续常驻，右侧 Tab 和浮窗不替换主对话。

## Scope

### Must Implement

- 创建本地项目。
- 打开和切换项目。
- 重命名项目。
- 归档项目；永久删除不实现。
- 项目列表和最近项目恢复。
- 每个项目独立保存：
  - 对话历史。
  - 未发送草稿。
  - 当前模型选择。
  - 基础项目状态。
- 应用重启后恢复项目、消息、草稿和最近项目。
- 数据带 schema version。
- API Key 与项目数据完全隔离。
- DeepSeek 用户消息、助手流式回复、错误、取消和 token usage 写入当前项目历史。
- `CenterChat` / MainConversation 保持常驻；项目切换只更新其数据，不用路由或条件渲染替换中央区域。

## Non-goals

ZW-003 不实现：

- 需求澄清。
- 硬件推荐。
- 推荐实现方案。
- 立项书。
- Agent Registry。
- Skill Registry。
- 总控 Agent。
- 串口。
- MicroPython 上传。
- 固件烧录。
- CAD。
- 教案。
- 分享。
- 云同步。
- 用户注册。
- 对话全文搜索。
- 多窗口/多进程并发编辑。
- 项目永久删除和回收站恢复。

## Domain Model

所有跨前后端字段、枚举和序列化规则先进入 `packages/contracts`，Sidecar 用 Pydantic 模型对齐。UI 不复制自由字符串状态。

### Identifiers

```ts
export type ProjectId = string; // prj_<uuid/hex>
export type ConversationId = string; // conv_<uuid/hex>
export type MessageId = string; // msg_<uuid/hex>
```

ID 由 Sidecar 生成。UI 不自行生成持久化 ID；临时 optimistic ID 只能在 UI 内部使用，提交后以 Sidecar 返回为准。

### Persistence Version

```ts
export const ProjectPersistenceVersion = {
  V1: 1,
} as const;

export type ProjectPersistenceVersion =
  (typeof ProjectPersistenceVersion)[keyof typeof ProjectPersistenceVersion];
```

### Project

```ts
export interface Project {
  id: ProjectId;
  name: string;
  stage: ProjectStage;
  profile: ProjectProfile;
  conversationId: ConversationId;
  selectedModel: LLMModelId;
  archivedAt: string | null;
  createdAt: string;
  updatedAt: string;
  lastOpenedAt: string | null;
  schemaVersion: ProjectPersistenceVersion;
}
```

### ProjectSummary

```ts
export interface ProjectSummary {
  id: ProjectId;
  name: string;
  stage: ProjectStage;
  selectedModel: LLMModelId;
  messageCount: number;
  draftUpdatedAt: string | null;
  archivedAt: string | null;
  updatedAt: string;
  lastOpenedAt: string | null;
}
```

### ProjectProfile

ZW-003 只需要最小项目资料，不提前实现完整画像。

```ts
export interface ProjectProfile {
  initialIdea: string;
}
```

### Conversation

```ts
export interface Conversation {
  id: ConversationId;
  projectId: ProjectId;
  messages: ChatMessage[];
  updatedAt: string;
}
```

ZW-003 复用 ZW-002 的 `ChatMessage`、`ChatRole`、`ChatMessageStatus`、`LLMModelId`、`LLMError` 和 `TokenUsage`。需要扩展 `ChatMessage`：

```ts
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
  usage?: TokenUsage;
}
```

`usage` 作为可选字段加入，便于持久化 DeepSeek 完成事件中的 token 信息。

### Draft

```ts
export interface Draft {
  projectId: ProjectId;
  content: string;
  updatedAt: string | null;
}
```

### ProjectWorkspace

```ts
export interface ProjectWorkspace {
  project: Project;
  conversation: Conversation;
  draft: Draft;
}
```

### AppWorkspaceState

```ts
export interface AppWorkspaceState {
  schemaVersion: ProjectPersistenceVersion;
  projects: ProjectSummary[];
  activeProjectId: ProjectId | null;
}
```

## Recommended Storage

### Recommendation: SQLite for ZW-003

Use Python standard library `sqlite3` managed by Sidecar.

Development path:

```text
services/local-api/.data/projects/zhangwen.sqlite3
```

Production path:

```text
%LOCALAPPDATA%/Zhangwen/projects/zhangwen.sqlite3
```

The exact production root should be derived by Sidecar config. Current code already centralizes `settings.data_dir`; ZW-003 should extend that rather than adding Tauri-side file access.

### Reasons

- Conversation history is append/update heavy; SQLite is more reliable than rewriting JSON files for every streaming delta.
- SQLite supports schema versioning through `PRAGMA user_version`.
- SQLite gives atomic transactions for “append user message + assistant placeholder + update project timestamp”.
- SQLite is in Python stdlib, so no new runtime dependency is required.
- Corruption detection and backup are more controllable than scattered JSON files.
- It aligns with `docs/ARCHITECTURE.md`, which names SQLite as the long-term local state store.

### Rejected for ZW-003: Project JSON Files

JSON files are still acceptable for very early prototypes, but less appropriate now because ZW-002 already streams real LLM output. Persisting every delta to JSON would either rewrite large files frequently or risk losing partial generation state. JSON can remain useful later for project export/import, not as the primary local state DB.

### Rejected: Tauri Store

Tauri Store would put project state in the desktop process and bypass the Python Sidecar boundary. Project data, LLM conversation writes, future Tool Runner and audit state should remain under Sidecar ownership.

## Data Directory

Recommended layout:

```text
<data_dir>/
├─ config/
│  └─ llm.json                 # existing non-sensitive LLM config, no API Key
├─ projects/
│  ├─ zhangwen.sqlite3          # project index, metadata, messages, drafts
│  ├─ zhangwen.sqlite3-wal
│  ├─ zhangwen.sqlite3-shm
│  └─ backups/
│     └─ zhangwen-YYYYMMDD-HHMMSS.sqlite3
└─ logs/
   └─ ...
```

Security rule:

- API Key remains in Windows Credential Manager.
- Project DB never stores API Key, Authorization headers, masked key, or provider secret material.
- Project DB may store the selected model ID and message content.

## SQLite Schema Draft

### `meta`

```sql
CREATE TABLE meta (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
```

Required keys:

- `schemaVersion`
- `activeProjectId`
- `createdAt`
- `updatedAt`

### `projects`

```sql
CREATE TABLE projects (
  id TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  stage TEXT NOT NULL,
  initial_idea TEXT NOT NULL DEFAULT '',
  selected_model TEXT NOT NULL,
  archived_at TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  last_opened_at TEXT NULL
);
```

### `conversations`

```sql
CREATE TABLE conversations (
  id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL UNIQUE REFERENCES projects(id) ON DELETE RESTRICT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);
```

### `messages`

```sql
CREATE TABLE messages (
  id TEXT PRIMARY KEY,
  conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
  project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
  role TEXT NOT NULL,
  content TEXT NOT NULL,
  reasoning_content TEXT NULL,
  status TEXT NOT NULL,
  model TEXT NULL,
  error_json TEXT NULL,
  usage_json TEXT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE INDEX idx_messages_project_created
  ON messages(project_id, created_at);
```

### `drafts`

```sql
CREATE TABLE drafts (
  project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
  content TEXT NOT NULL,
  updated_at TEXT NULL
);
```

## Schema Migration

Use SQLite `PRAGMA user_version` as the authoritative schema version.

Migration design:

- `ProjectPersistenceVersion.V1 = 1` maps to SQLite `user_version = 1`.
- `ProjectRepository.open()` checks `user_version`.
- If database does not exist: create V1 schema in a single transaction.
- If `user_version == 0` and tables are absent: initialize V1.
- If `user_version < CURRENT`: run ordered migration functions.
- If `user_version > CURRENT`: reject with `UNSUPPORTED_PROJECT_SCHEMA_VERSION`.
- Before migration, copy database into `projects/backups/`.
- Migrations are pure SQL/Python functions covered by tests.

Minimum migration API:

```py
CURRENT_SCHEMA_VERSION = 1

def migrate(conn: sqlite3.Connection) -> None:
    version = get_user_version(conn)
    if version > CURRENT_SCHEMA_VERSION:
        raise UnsupportedSchemaVersion(...)
    if version == 0:
        create_v1(conn)
```

## Contracts Changes

Expected changes:

- `packages/contracts/src/enums.ts`
  - Add `ProjectPersistenceVersion`.
  - Reuse existing `ProjectStage`.
  - Reuse existing `ChatRole`, `ChatMessageStatus`, `LLMModelId`.
- `packages/contracts/src/api.ts`
  - Add project and conversation models.
  - Add project request/response types.
  - Add project-scoped chat request/response types if needed.
  - Add persistence errors or extend existing `ZwError` usage.
- `packages/contracts/src/events.ts`
  - Add `project.created`, `project.updated`, `project.archived`, `project.opened`, `conversation.message.created`, `conversation.message.updated`, `draft.updated` if ZW-003 chooses to publish events.
  - If not implementing WebSocket/event bus in ZW-003, update docs to state HTTP responses are authoritative for this task.
- `packages/contracts/src/index.ts`
  - Export new types.

Expected new or extended types:

```ts
export interface CreateProjectRequest {
  name: string;
  initialIdea: string;
  selectedModel?: LLMModelId;
}

export interface RenameProjectRequest {
  name: string;
}

export interface ArchiveProjectRequest {
  archived: boolean;
}

export interface UpdateProjectModelRequest {
  selectedModel: LLMModelId;
}

export interface SaveDraftRequest {
  content: string;
}

export interface ProjectListResponse {
  projects: ProjectSummary[];
  activeProjectId: ProjectId | null;
}

export interface ProjectWorkspaceResponse {
  workspace: ProjectWorkspace;
}

export interface PersistedChatRequest {
  content: string;
  model?: LLMModelId;
  abortPrevious?: boolean;
}
```

## Sidecar / Tauri Boundary

### Sidecar Responsibilities

- Own all project data reads/writes.
- Own SQLite schema, migrations, backups and corruption handling.
- Generate project/conversation/message IDs.
- Validate project names, IDs, archived state and message input.
- Persist user message before LLM call.
- Persist assistant placeholder before streaming starts.
- Update assistant message on deltas, completion, cancellation and errors.
- Continue owning API Key retrieval from Windows Credential Manager.
- Ensure project DB contains no API Key or credential fields.

### Tauri Responsibilities

- Continue starting/stopping Sidecar.
- Do not read/write project DB directly.
- Optional future improvement: pass production data directory to Sidecar via environment variable. Not required if Sidecar config already resolves a valid app data path.

### Frontend Responsibilities

- Use Sidecar HTTP/SSE APIs only.
- Keep current `CenterChat` mounted.
- Render active project data from state.
- Save drafts through Sidecar.
- Send chat through project-scoped endpoint.
- Do not persist project data in localStorage except optional ephemeral UI preferences.

## API Contract

### Project APIs

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/projects` | List non-archived projects and active/recent project |
| `POST` | `/api/projects` | Create project |
| `GET` | `/api/projects/{projectId}` | Load project workspace with conversation and draft |
| `POST` | `/api/projects/{projectId}/open` | Mark project active/recent |
| `PATCH` | `/api/projects/{projectId}` | Rename project and/or update selected model |
| `POST` | `/api/projects/{projectId}/archive` | Archive project |
| `PUT` | `/api/projects/{projectId}/draft` | Save project draft |

### Project-scoped Chat APIs

Preferred new endpoint:

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/api/projects/{projectId}/chat/stream` | Send user message in project and stream persisted assistant reply |
| `POST` | `/api/projects/{projectId}/chat/cancel/{requestId}` | Cancel active project chat request |

The existing `/api/chat/stream` can remain temporarily for tests or non-persistent ad-hoc chat, but the UI must use the project-scoped endpoint after ZW-003.

### SSE Events

Project-scoped stream chunks should extend existing `StreamChunk`:

```ts
export interface ProjectStreamChunk extends StreamChunk {
  projectId: ProjectId;
  conversationId: ConversationId;
  userMessageId?: MessageId;
}
```

Events remain:

- `chat.started`
- `chat.delta`
- `chat.completed`
- `chat.error`
- `chat.canceled`

Each event must include `requestId`, `messageId`, `projectId`, `conversationId`. Frontend ignores chunks whose `requestId` or `projectId` does not match the active request.

### Error Codes

Add project persistence errors, returned in `ZwError` or `LLMError` where appropriate:

- `PROJECT_NOT_FOUND`
- `PROJECT_ARCHIVED`
- `PROJECT_NAME_REQUIRED`
- `PROJECT_NAME_TOO_LONG`
- `MESSAGE_EMPTY`
- `DRAFT_TOO_LARGE`
- `PERSISTENCE_READ_FAILED`
- `PERSISTENCE_WRITE_FAILED`
- `PROJECT_SCHEMA_UNSUPPORTED`
- `PROJECT_DATABASE_CORRUPT`
- `PROJECT_CONFLICT_ACTIVE_REQUEST`

Chinese user messages must be actionable and must not leak local paths unless explicitly useful for troubleshooting.

## Frontend State Management

Use React hooks and local reducer/context for ZW-003. Do not introduce Redux/Zustand unless state complexity demonstrably exceeds this task.

Recommended structure:

```text
apps/desktop/src/hooks/useProjects.ts
apps/desktop/src/services/projectsApi.ts
apps/desktop/src/components/project/CreateProjectDialog.tsx
apps/desktop/src/components/project/ProjectList.tsx
```

### AppShell Ownership

`AppShell` should own workspace state:

```ts
interface WorkspaceState {
  projects: ProjectSummary[];
  activeProjectId: ProjectId | null;
  activeWorkspace: ProjectWorkspace | null;
  loading: boolean;
  error: ZwError | null;
}
```

Data flow:

- `AppShell` loads `/api/projects`.
- If `activeProjectId` exists, load `/api/projects/{activeProjectId}`.
- `LeftSidebar` receives projects and active id.
- `TopBar` receives active project name/stage.
- `CenterChat` receives active workspace, config, model selection and actions.
- `WorkTab` receives current project basics.

### CenterChat Requirements

- `CenterChat` remains mounted once under `AppShell`.
- No `key={projectId}` on `CenterChat`.
- Message list and draft are props/state derived from active project workspace.
- Switching projects updates visible messages and draft without unmounting the component.
- If no project exists, show an empty state inside the central chat area with create-project action; do not replace the central region.
- Draft saves are debounced, e.g. 300-500 ms, and flushed on project switch / before send.
- Active stream blocks project switch or requires explicit cancellation; recommended MVP behavior: prompt to stop current generation before switching.

### Model Selection

- Each project has `selectedModel`.
- New project default selected model comes from current LLM config `defaultModel`.
- Main conversation shows compact current model control.
- Changing project model calls `PATCH /api/projects/{projectId}` and only affects that project.
- Global settings default model remains a default for new projects, not an override for existing project choices.

## Data Corruption Recovery

### SQLite Integrity

On Sidecar startup or first project repository open:

- Ensure DB directory exists.
- Run `PRAGMA integrity_check`.
- If OK, proceed.
- If corrupt:
  - Move corrupt DB to `projects/backups/corrupt-YYYYMMDD-HHMMSS.sqlite3`.
  - Try latest backup.
  - If backup valid, restore and return warning.
  - If no backup valid, initialize empty DB and return structured warning.

### Backups

Create backups:

- Before schema migration.
- Before archive operations if implemented as bulk metadata updates.
- Optional daily backup on first write of the day.

### Partial Streaming Failure

Persistence behavior:

- User message is committed before upstream DeepSeek call.
- Assistant placeholder is committed before streaming.
- Each delta may update the assistant row with accumulated content.
- On process crash mid-stream, assistant message remains `STREAMING`.
- On next startup, repository normalizes stale `STREAMING` messages to `FAILED` with error message “上次生成被中断，可重试。”

### Atomic Writes

- Use transactions for create project, rename, archive, draft save, message append and stream status updates.
- Use WAL mode for resilience:

```sql
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
```

## Implementation Milestones

### M1 — Contracts-first Project and Conversation Model

Expected files:

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/events.ts`
- `packages/contracts/src/index.ts`
- possibly new `packages/contracts/src/projects.ts`

Validation:

```powershell
pnpm --filter @zhangwen/contracts build
pnpm --filter @zhangwen/contracts typecheck
```

Acceptance:

- Shared contracts define project, conversation, draft, schema version, request and response types.
- Project model references `ProjectStage` and `LLMModelId` from existing contracts.

### M2 — Sidecar SQLite Repository and Migration Layer

Expected files:

- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/errors.py`
- `services/local-api/zhangwen/config.py`
- tests for schema init, migration, corruption/stale streaming normalization

Validation:

```powershell
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -v --rootdir services/local-api
```

Acceptance:

- Empty DB initializes V1 schema.
- `PRAGMA user_version` is set to 1.
- Create/open/list/rename/archive/save draft work through repository.
- API Key fields are not present in project DB schema or rows.

### M3 — Project HTTP API

Expected files:

- `services/local-api/zhangwen/projects/router.py`
- `services/local-api/zhangwen/main.py`
- API tests

Validation:

```powershell
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_projects_api.py -v --rootdir services/local-api
```

Acceptance:

- REST API supports create, list, open, load, rename, model update, archive and draft save.
- Archived projects are hidden from default list but not physically deleted.
- Recent/active project restores after repository reload.

### M4 — Persisted Project-scoped DeepSeek Chat

Expected files:

- `services/local-api/zhangwen/chat/router.py`
- `services/local-api/zhangwen/chat/sessions.py`
- `services/local-api/zhangwen/projects/repository.py`
- chat persistence tests

Validation:

```powershell
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_chat_stream.py -v --rootdir services/local-api
```

Acceptance:

- Sending chat in project persists user message and assistant placeholder.
- Stream deltas update assistant content.
- Completed/canceled/error statuses persist.
- Reloading project returns full conversation history.
- Tests use `httpx.MockTransport`; no real DeepSeek calls.

### M5 — Frontend Project Workspace State

Expected files:

- `apps/desktop/src/services/projectsApi.ts`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/TopBar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/right-panel/WorkTab.tsx`
- project UI components as needed

Validation:

```powershell
pnpm --filter @zhangwen/desktop typecheck
pnpm --filter @zhangwen/desktop test
```

Acceptance:

- User can create a project from the UI.
- Project appears in left sidebar.
- Switching projects restores independent messages, draft and selected model.
- TopBar and WorkTab reflect active project.
- CenterChat remains a single mounted instance.

### M6 — Restart Recovery and UI Regression

Expected files:

- frontend tests
- Sidecar tests
- `docs/API_EVENTS.md`
- `docs/DECISIONS.md`
- task and handoff updates

Validation:

```powershell
pnpm test:frontend
.\.venv\Scripts\python.exe -m pytest services/local-api/tests/ -v --rootdir services/local-api
```

Acceptance:

- Simulated app reload restores project list, active project, messages and draft.
- Settings floating window, right Tab switch and artifact floating window still do not clear draft or unmount CenterChat.
- Stale streaming messages after restart are normalized to failed/retryable.

### M7 — Full Validation and Handoff

Expected validation:

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

- Actual command outputs are recorded in this task and `HANDOFF.md`.
- No project DB, WAL, backups, API Key or local user data are staged.

## Test Plan

### Contracts

- Build/typecheck contracts.
- Add compile-time examples for project API shapes if the package has test harness later.

### Sidecar Repository Tests

- Initializes V1 DB when missing.
- Refuses unsupported future schema version.
- Creates project with default stage `IDEA`.
- Lists non-archived projects sorted by last opened/updated.
- Opens project and updates active/recent metadata.
- Renames project with validation.
- Archives project without deleting messages.
- Saves draft per project.
- Saves selected model per project.
- Reloads repository and restores data.
- Normalizes stale `STREAMING` assistant messages to `FAILED`.
- Does not persist API Key or masked Key in SQLite.
- Backs up before migration.

### Sidecar API Tests

- `POST /api/projects`.
- `GET /api/projects`.
- `GET /api/projects/{projectId}`.
- `POST /api/projects/{projectId}/open`.
- `PATCH /api/projects/{projectId}` rename/model update.
- `POST /api/projects/{projectId}/archive`.
- `PUT /api/projects/{projectId}/draft`.
- Structured errors for not found, archived, invalid name, empty message and persistence failure.

### Project Chat Tests

- Project-scoped chat persists user and assistant messages.
- Streaming delta updates persisted assistant content.
- Completion persists `COMPLETED`, model and usage.
- Cancellation persists `CANCELED`.
- Upstream 401/402/429/500/503 persists `FAILED` with safe Chinese error.
- Concurrent request in same project cancels or rejects old request deterministically.
- Request for archived project fails before calling DeepSeek.
- Mock transport prevents real DeepSeek network calls.

### Frontend Tests

- App loads projects and restores active project.
- Empty state appears inside center chat when no project exists.
- Create project updates sidebar and activates project.
- Rename project updates sidebar and TopBar.
- Archive project removes it from default sidebar list.
- Switching projects restores independent draft.
- Switching projects restores independent message history.
- Project model can switch Flash/Pro independently of global default.
- Sending message uses project-scoped stream endpoint and renders persisted deltas.
- Stop generation calls project-scoped cancel endpoint.
- Settings open/close does not lose project draft.
- Right tabs and artifact floating window do not unmount or duplicate CenterChat.
- MainConversation remains mounted once across project switch.

### Manual Acceptance

1. Start Tauri desktop app.
2. Confirm Sidecar connected.
3. Create project A with an initial idea.
4. Create project B with a different initial idea.
5. Type draft in project A, switch to project B, type different draft, switch back and confirm project A draft restored.
6. Configure valid DeepSeek API Key if not already configured.
7. Send a message in project A and confirm streaming reply appears.
8. Switch to project B and confirm project A messages are not shown.
9. Send a message in project B with different model.
10. Restart app and confirm project list, recent project, messages, drafts and model choices restore.
11. Rename project and confirm sidebar/topbar/work tab update.
12. Archive project and confirm it disappears from default list without deleting DB manually.
13. Open settings and right panel tabs during the flow; confirm CenterChat remains mounted and draft persists.

## File List

### Contracts

- `packages/contracts/src/enums.ts`
- `packages/contracts/src/api.ts`
- `packages/contracts/src/events.ts`
- `packages/contracts/src/index.ts`
- optional `packages/contracts/src/projects.ts`

### Python Sidecar

- `services/local-api/zhangwen/config.py`
- `services/local-api/zhangwen/main.py`
- `services/local-api/zhangwen/projects/__init__.py`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/projects/migrations.py`
- `services/local-api/zhangwen/projects/router.py`
- `services/local-api/zhangwen/projects/errors.py`
- `services/local-api/zhangwen/chat/router.py`
- `services/local-api/zhangwen/chat/sessions.py`
- `services/local-api/tests/test_project_repository.py`
- `services/local-api/tests/test_projects_api.py`
- `services/local-api/tests/test_project_chat_stream.py`

### Frontend

- `apps/desktop/src/services/projectsApi.ts`
- `apps/desktop/src/services/llmApi.ts`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/hooks/useChatStream.ts`
- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/TopBar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/right-panel/WorkTab.tsx`
- `apps/desktop/src/components/project/CreateProjectDialog.tsx`
- optional `apps/desktop/src/components/project/ProjectList.tsx`
- frontend tests under `apps/desktop/src/__tests__/`

### Tauri / Scripts / Docs

- Tauri code likely unchanged unless production data dir env is needed.
- `docs/API_EVENTS.md`
- `docs/DECISIONS.md`
- `HANDOFF.md`
- `tasks/ZW-003-project-conversation-persistence.md`
- `.gitignore` only if SQLite data patterns are not already covered.

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| Persisting every token delta causes too many DB writes | Performance issue | Throttle DB updates during stream or persist accumulated content every N chars / 250 ms, always persist final event |
| CenterChat remounts during project switch | Violates UI contract | Regression test uses mount counter or stable test id count across project changes |
| Old `/api/chat/stream` and new project endpoint diverge | Bugs and duplicated logic | Extract shared streaming service; UI uses only project endpoint |
| SQLite DB committed accidentally | User data leak | Ensure `.data/` ignored; final git status check |
| API Key accidentally joins project snapshot | Security issue | Schema excludes key fields; repository test searches DB dump for fake key |
| Crash during stream leaves stuck message | Bad UX | Startup normalization from `STREAMING` to `FAILED` |
| Project archive while generation active | Inconsistent state | Reject archive with active request or cancel request before archive |
| Unsupported future schema opens silently | Data loss | Reject future schema version explicitly |

## Decision Log

| Date | Decision | Choice | Reason |
|---|---|---|---|
| 2026-07-08 | ZW-003 primary storage | SQLite via Python stdlib `sqlite3` | Real streaming chat needs transactional append/update and schema migration; no new dependency required |
| 2026-07-08 | Project data owner | Python Sidecar | Preserves architecture boundary; UI/Tauri do not access local project files directly |
| 2026-07-08 | API Key separation | Keep Windows Credential Manager only | Project DB must not contain API Key, masked Key or auth headers |
| 2026-07-08 | Chat persistence boundary | New project-scoped chat stream endpoint | Ensures real DeepSeek conversation writes into current project history |
| 2026-07-08 | Frontend state | React hook/reducer, no new state library | Current app state remains small and scoped to AppShell |

## Progress

- [x] (2026-07-08) Read required project rules, ZW-002 task, architecture/UI/API/decision docs, current Contracts, Sidecar, Tauri and main conversation code.
- [x] (2026-07-08) Confirmed current ZW-002 implementation state from `HANDOFF.md` and source files.
- [x] (2026-07-08) Created ZW-003 planning draft.
- [x] (2026-07-08) User confirmed implementation start.
- [x] (2026-07-08) M1 Contracts-first Project and Conversation Model completed. Added shared project, conversation, draft, project stream and persistence version contracts. Validation: `pnpm --filter @zhangwen/contracts build` passed; `pnpm --filter @zhangwen/contracts typecheck` passed.
- [x] (2026-07-08) M2 Sidecar SQLite Repository and Migration Layer completed. Added SQLite schema, migration, repository, project models and repository tests. Validation: `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_repository.py -v --rootdir services/local-api` passed, 6 tests.
- [x] (2026-07-08) M3 Project HTTP API completed. Added projects router and registered it in FastAPI. Validation: `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_projects_api.py -v --rootdir services/local-api` passed, 2 tests.
- [x] (2026-07-08) M4 Persisted Project-scoped DeepSeek Chat completed. Added project-scoped stream/cancel endpoints and persistence updates for assistant deltas/completion/errors. Validation: `.\.venv\Scripts\python.exe -m pytest services/local-api/tests/test_project_chat_stream.py -v --rootdir services/local-api` passed, 2 tests.
- [x] (2026-07-08) M5 Frontend Project Workspace State completed. Added project API client, `useProjects`, sidebar project list/create/rename/archive controls, project-aware TopBar/WorkTab, project-scoped `CenterChat`, draft autosave and project stream usage. Validation: `pnpm --filter @zhangwen/desktop typecheck` passed; `pnpm --filter @zhangwen/desktop test` passed, 6 files / 29 tests.
- [x] (2026-07-08) M6 Restart Recovery and UI Regression completed. SQLite repository restores project list, active project, messages, drafts and selected model; stale streaming messages normalize to failed; frontend tests cover project switch draft recovery and `CenterChat` node stability across project/right-tab changes.
- [x] (2026-07-08) M7 Full Validation completed. Actual commands passed: `pnpm --filter @zhangwen/contracts build`; `pnpm --filter @zhangwen/contracts typecheck`; `pnpm --filter @zhangwen/desktop typecheck`; `pnpm --filter @zhangwen/desktop test`; `pnpm --filter @zhangwen/desktop build`; `.\.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api`; `.\.venv\Scripts\python.exe scripts/check_ai_assets.py`; `cargo check` from `apps/desktop/src-tauri`.
- [x] (2026-07-08) Final UI contract fix completed before close. Removed the duplicate central project creation form from `CenterChat`; project creation remains only in `LeftSidebar`; central empty state now stays inside MainConversation. Validation: `pnpm --filter @zhangwen/desktop test -- src/__tests__/ProjectWorkspace.test.tsx` passed and `pnpm --filter @zhangwen/desktop typecheck` passed.

## Implementation Results

ZW-003 is implemented and validated on 2026-07-08.

### Verified Commands

```powershell
pnpm --filter @zhangwen/contracts build
pnpm --filter @zhangwen/contracts typecheck
pnpm --filter @zhangwen/desktop typecheck
pnpm --filter @zhangwen/desktop test
pnpm --filter @zhangwen/desktop build
.\.venv\Scripts\python.exe -m pytest services/local-api/tests -v --rootdir services/local-api
.\.venv\Scripts\python.exe scripts/check_ai_assets.py
cargo check
```

Results:

- Contracts build/typecheck passed.
- Desktop typecheck passed.
- Desktop tests passed: 6 files, 31 tests.
- Desktop build passed.
- Sidecar tests passed: 23 tests, 1 Starlette/httpx deprecation warning.
- `scripts/check_ai_assets.py` passed: Shared Skills are in sync.
- Tauri `cargo check` passed.
- Pytest emitted a Windows temp cleanup `PermissionError` in an ignored atexit callback after successful exit; test process exit code was 0.

### Remaining Non-blocking Items

- Full Tauri installer build was not rerun in ZW-003 because this task did not change Tauri packaging and previous ZW-002 handoff already recorded packaging environment blockers.
- Permanent delete, export/import, full-text search and cloud sync remain out of scope.

## Definition of Done

- User can create, open, switch, rename and archive local projects.
- Each project has independent conversation history, draft and selected model.
- App restart restores project list, active/recent project, messages, drafts and model choices.
- Data schema has version and migration path.
- API Key remains outside project DB and project files.
- Real DeepSeek user messages, assistant replies, cancellations and errors persist in current project history.
- MainConversation remains mounted once; project switching updates content without replacing central area.
- Right “工作 / 产物 / 设备” tabs and settings/floating windows do not clear draft or unmount chat.
- Contracts define project/conversation/persistence API shapes.
- Sidecar owns all local project persistence.
- Automatic tests cover repository, API, streaming persistence, UI project switching and invariant regressions.
- Validation commands and outcomes are recorded in this task and `HANDOFF.md`.
