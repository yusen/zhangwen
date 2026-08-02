# 三师系统 Phase 5：项目工作台界面和交互

日期：2026-07-10

## 范围

本阶段只改造现有项目工作台 UI 和交互，不创建第二套工作台，不引入新的 UI 框架或全局状态管理，不暴露 EntryRouter、ProjectCoordinator、模型路由、系统提示词或 Skill 参数。

## 修改摘要

- 将现有工作台收敛为左、中、右三栏：左侧为项目总览、已参与专家和项目资源；中央在项目总览与当前专家独立对话之间切换；右侧固定为工作、产物、设备。
- 左侧只显示三师专家：`problem_guide`、`smart_engineer`、`structure_engineer`，并从领域数据读取状态、待确认和过期标记。
- 专家切换只改变当前专家、工作区、线程和输入草稿，不创建 Handoff，不复制聊天记录，不修改共享事实。
- 聊天发送请求携带 `projectId`、`expertWorkspaceId`、`threadId`、`expertType`，避免用项目级消息前端过滤模拟线程。
- 输入草稿按 `${projectId}:${expertType}:${threadId}` 隔离，切换专家、项目总览和右侧页签时保持草稿。
- 工作页只突出领域层 `isHighlighted=true` 的唯一 PendingItem，其他事项放入“后续事项”。
- 产物页支持当前专家/全部专家、类型和状态筛选，显示版本、领域状态、所属专家、依赖和过期原因。
- 设备页保留串口扫描和会话摘要；连接、上传 Dry Run、固件 Dry Run 等操作入口只对 `smart_engineer` 显示。
- 后端补充添加/移除专家和 PendingItem 处理接口，移除专家为软移除，保留历史线程、产物和任务。

## 修改文件列表

- `packages/contracts/src/api.ts`
- `packages/contracts/src/index.ts`
- `services/local-api/zhangwen/projects/models.py`
- `services/local-api/zhangwen/projects/repository.py`
- `services/local-api/zhangwen/projects/router.py`
- `services/local-api/tests/test_project_repository.py`
- `apps/desktop/src/services/projectsApi.ts`
- `apps/desktop/src/hooks/useProjects.ts`
- `apps/desktop/src/utils/experts.ts`
- `apps/desktop/src/components/layout/AppShell.tsx`
- `apps/desktop/src/components/layout/LeftSidebar.tsx`
- `apps/desktop/src/components/layout/CenterChat.tsx`
- `apps/desktop/src/components/layout/RightPanel.tsx`
- `apps/desktop/src/components/right-panel/WorkTab.tsx`
- `apps/desktop/src/components/right-panel/ArtifactsTab.tsx`
- `apps/desktop/src/components/right-panel/DevicesTab.tsx`
- `apps/desktop/src/App.css`
- `apps/desktop/src/__tests__/ProjectWorkspace.test.tsx`
- `apps/desktop/src/__tests__/ProjectIsolation.test.tsx`
- `apps/desktop/src/__tests__/RightPanel.test.tsx`
- `apps/desktop/src/__tests__/DeepSeekChat.test.tsx`
- `apps/desktop/src/__tests__/SettingsDeepSeek.test.tsx`

## 左中右布局

- 左侧固定包含“项目总览 / 已参与专家 / 项目资源”。
- 点击“项目总览”只把中央切回总览，右侧当前页签保持不变。
- 中央只存在两种主状态：项目总览、专家独立对话。
- 右侧一级 Tab 固定为“工作 / 产物 / 设备”，切换右侧页签不改变当前专家、线程、草稿或中央滚动状态。

## 三师独立线程

- 已参与专家列表过滤为三师专家，不展示旧四专家、主路由、协调器或智能工程师 Skill。
- `add_project_expert()` 创建或恢复对应 ExpertWorkspace，并创建独立 ConversationThread；不会复制完整聊天。
- `remove_project_expert()` 使用 `removed_at` 软移除，至少保留一位专家，历史对话、产物和任务保留。
- 发送聊天时前端把当前 `projectExpertId`、`threadId`、`expertType` 一起传给后端。

## 专家切换和草稿保持

- 专家切换前保存当前草稿，目标专家按 `${projectId}:${expertType}:${threadId}` 恢复草稿。
- 每个线程保存滚动位置，切回专家时恢复。
- 手动切换专家不创建 Handoff，不复制消息，不改变 SharedFact。

## 唯一待处理事项

- `WorkTab` 从领域数据读取当前高亮事项，不在前端重新计算优先级。
- 同一时间只把 `currentPendingItem` 或 `isHighlighted=true` 的 PendingItem 作为主卡突出显示。
- 处理/暂不处理调用项目 PendingItem 应用服务，完成后刷新工作台。
- 其他待处理事项折叠在“后续事项”中。

## 产物版本和过期展示

- 产物页展示统一项目产物库。
- 支持当前专家、全部专家、类型和领域状态筛选。
- 每项显示标题、类型、所属专家、版本、状态、更新时间、过期标记、依赖和过期原因。
- 旧版本不删除；过期产物不作为默认输入。

## 设备权限

- `smart_engineer` 可看到受控操作入口：连接 Mock 端口、上传 Dry Run、固件 Dry Run。
- `problem_guide` 和 `structure_engineer` 只显示必要设备摘要、串口扫描、会话状态和只读提示。
- 前端设备操作仍调用现有应用服务，经过 ToolRunner/dry-run/确认策略，不直接执行真实串口上传、Flash 擦除或固件烧录。

## 旧项目兼容

- 旧项目打开时缺失新字段使用默认值，不因缺少 PendingItem、ExpertWorkspace 新字段或新领域状态崩溃。
- 旧专家数据通过已有迁移和兼容字段映射到三师 UI；旧线程、旧产物和旧版本继续可查看。
- 前端状态映射保留 legacy 容错，但用户可见专家列表只显示三师参与成员。

## 自动测试结果

- `pnpm --filter @zhangwen/desktop typecheck`：通过。
- `pnpm --filter @zhangwen/desktop test -- RightPanel`：通过，实际运行 7 个测试文件 / 59 个测试；仍有既有 WorkTab React `act(...)` warning。
- `pnpm typecheck`：通过。
- `.venv\Scripts\python.exe -m pytest services/local-api/tests/ -q --rootdir services/local-api`：125 passed，1 个既有 Starlette warning；结束后仍有 Windows pytest 临时目录 cleanup `PermissionError`。
- `pnpm --filter @zhangwen/desktop build`：通过，刷新 `apps/desktop/dist`。
- `cargo check --manifest-path apps/desktop/src-tauri/Cargo.toml`：通过。
- `pnpm --filter @zhangwen/desktop run lint`：未运行，当前 desktop package 没有 `lint` script。

## 人工验收结果

启动方式：

- `.venv\Scripts\python.exe -m uvicorn zhangwen.main:app --port 8100 --host 127.0.0.1 --app-dir services/local-api`
- `pnpm --filter @zhangwen/desktop dev -- --host 127.0.0.1`
- 浏览器访问 `http://localhost:5173/`

已验证：

- 页面标题为“掌问 — AI 创客工程工作台”，首屏非空，三栏工作台、左侧项目总览、已参与专家、项目资源和右侧固定 Tab 正常显示。
- 浏览器控制台没有应用级 error/warn。
- 在已有项目中添加“问题引导师”并进入，中央切到问题引导师独立对话，智能工程师旧线程仍保留。
- 问题引导师草稿切到智能工程师后不出现；右侧保持“产物”页签；切回问题引导师后草稿恢复。
- 设备页权限复验通过：问题引导师看不到“上传 Dry Run / 固件 Dry Run”，智能工程师仍可看到这些受控入口。

未执行的人工项：

- 未发送真实 Agent 消息，避免在用户未确认的情况下触发真实付费 LLM；当前环境页面也提示未配置 DeepSeek API Key。
- 未连接真实串口设备，未执行 `mpremote`、`esptool`、Flash 擦除、固件烧录或设备文件写入。
- 产物过期链路和多 PendingItem 候选链路通过自动测试覆盖，没有在真实 UI 中手工制造完整上下游版本场景。

## 尚未完成项

- 没有新增 lint 脚本；当前只能报告 `pnpm --filter @zhangwen/desktop run lint` 不可用。
- 真实付费 LLM 对话、真实硬件和完整串口工作流仍需人工在有凭据和设备时验收。
- 已有测试仍输出 WorkTab `act(...)` warning，测试结果通过但 warning 未在本阶段清理。

## 回滚方法

- 代码回滚：回退本阶段涉及的 frontend/backend/contracts/test 文件和本说明文档。
- 数据回滚：本阶段没有新增数据库迁移；UI 添加专家调用会软创建/恢复 ExpertWorkspace 和线程。如需回退人工验收中添加的专家，可使用现有移除专家入口软移除，不要硬删除历史线程。
- 构建产物回滚：重新运行上一阶段对应的 `pnpm --filter @zhangwen/desktop build` 或还原 `apps/desktop/dist`。
