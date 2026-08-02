# 掌问全项目代码审查报告（2026-07-25）

关联任务：`ZW-MAINT-003`

## 结论

本轮对桌面 UI、共享 TypeScript contracts、Python Sidecar、设备安全边界和 Tauri 宿主进行了整体审查。现有架构和测试基线总体稳健；没有发现需要放宽安全门禁、改变外部契约或进行全库重写的问题。

已修复三类可复现代码问题，并校正两处测试隔离/验证流程问题：

1. 底层 `apiFetch` 的流式、二进制和设备请求遇到 HTTP 401 时，过去不会触发统一会话失效，可能让工作台停留在已过期登录态。现已把 401 清理和登录门禁事件收敛到统一 API Client，所有调用路径一致生效。
2. `AbortSignal.any` 不可用的兼容分支忽略“调用前已经取消”的 signal，且成功请求后残留事件监听器。现已保留取消原因、处理预先取消，并在请求结束或任一信号触发时清理监听器。
3. 三师类型和工作区状态已经由共享 contracts 定义，但桌面工具函数仍复制字符串。现已直接使用 `ExpertType`、`ExpertWorkspaceStatus` 和 `ProjectExpertStatus` 以及精确类型映射。
4. Sidecar 全量基线唯一失败来自一条端到端测试夹具：它生成代码时引用了未进入当前 ACTIVE 候选集的 K10，违反现行 Hardware Skill grounding 门禁。夹具已改为引用上下文实际提供的 OLED Skill；产品门禁没有放宽。
5. 设备上传测试过去经由 Solution → Proposal → Spec → Code 全链路造数据，单独运行时会因硬件目录状态不同而失败、在全量顺序中却可能通过。夹具现直接创建受边界校验的聊天代码草稿，再调用真实本地 MicroPython 验证和接受接口；设备测试不再依赖 LLM、Spec 或其他测试先写入目录。

## 审查范围与证据

- 桌面：API Client、认证失效、项目切换取消、永久主对话、右侧固定三 Tab、普通/专业模式、设备恢复和生产构建。
- Contracts：状态枚举来源、严格 TypeScript、前后端边界使用方式。
- Sidecar：认证中间件、Provider/Pydantic 本地校验、路径与凭据边界、持久化、CAD Worker 和设备服务。
- 设备：桌面 capability、已接受代码、写入确认、端口锁、备份/回读、固件候选、确认 token、确认短语、Dry Run 和禁止 Flash 擦除。
- Tauri：Sidecar 固定路径、有限重启预算、capability header 注入防护和脱敏日志。

敏感信息路径扫描没有发现真实 API Key、GitHub token 或私钥。唯一长 Bearer 命中是自动测试中的显式假 token。串口测试使用 Mock/合成标识；本轮没有连接真实串口或设备。

## 已实施重构

- `apps/desktop/src/services/api.ts`
  - 统一处理所有响应的 401 会话失效。
  - 将响应错误解析导出为共享 helper，删除项目 API 的重复实现。
  - 将 signal 合并改为带显式 cleanup 的结果，修复旧环境预取消和监听器泄漏。
- `apps/desktop/src/services/projectsApi.ts`
  - 文件/CAD 错误复用统一解析。
  - 串口列表恢复使用类型化 `apiGet`，保留 `ApiError` 状态和错误码。
- `apps/desktop/src/utils/experts.ts`
  - 三师与工作区状态直接使用共享 contracts，移除复制字符串。
- 自动测试
  - 新增底层请求 401 和旧环境预取消回归。
  - 更新已确认立项书直接实现测试的 Hardware Skill grounding 夹具。
  - 将设备上传夹具改为自包含代码生命周期，消除执行顺序依赖。

## 审查工具链发现

直接对整个 `services/local-api/zhangwen` 执行 `compileall` 会在带 `CHECKSUMS.sha256` 或文件清单的 Board/Hardware Skill 资源包内写入 `__pycache__`。资源加载器随后拒绝目录外文件是正确的安全行为，但会让同一工作树上的测试出现大量连锁失败。本轮已删除仅由该检查生成的 7 个缓存目录，没有改动资源内容或降低完整性校验；后续编译检查必须排除 `board-skills`、`bundled-hardware-skills` 和 `hardware-skill-template`。

## 保留但未顺手修改的风险

以下是维护热点，不是本轮已证明的正确性缺陷：

- `services/local-api/zhangwen/chat/router.py` 的主流式入口和嵌套事件生成器规模过大；拆分必须保持 SSE 时序、取消、幂等和自动恢复，应建立独立任务和故障注入测试。
- `hardware/hardware_skills.py`、`projects/repository.py`、`cad_agent/intake.py`、`devices/service.py` 体量较大，但分别承载事务/原子替换/安全状态机；没有失败证据时不做机械拆分。
- Python 测试仍有既有 Starlette/httpx 弃用警告。本轮不升级依赖，避免把兼容性迁移混入保守重构。
- Vite 仍提示 Monaco 与主入口分块较大。后续性能任务应先记录冷启动、编辑器首次打开和安装包体积基线，再决定语言 Worker 裁剪或懒加载策略。
- `compileall` 的安全排除目前记录在任务验证矩阵中，尚未固化为仓库脚本；未来若新增统一 Python 编译脚本，应内置这三类完整性资源包的排除规则并增加“检查后目录无额外文件”的断言。
- 真实 Provider、真实硬件、固件烧录和干净 Windows 安装体验仍属于外部验证。本轮结果不得解释为这些外部场景已通过。

## 验证记录

- `pnpm typecheck`：通过。
- `pnpm test:frontend`：`32 files / 209 passed`。
- `pnpm build:desktop`：通过；仅有既有大分块提示。
- `cargo test --manifest-path apps/desktop/src-tauri/Cargo.toml`：`5 passed`。
- 安全 Python 编译检查：`SAFE_COMPILE_OK protectedCaches=0`；排除了三类完整性资源包。
- Sidecar 首轮全量基线：`703 passed / 1 failed`；失败夹具已定位并由专项测试验证修复。
- 设备/认证/宿主边界专项：`57 passed`。
- Board/Hardware Skill 完整性恢复专项：`11 passed`；受保护目录无 `__pycache__`。
- Sidecar 最终全量：`704 passed`，仅有既有 Starlette/httpx 弃用警告。
- `git diff --check`：退出码 `0`；仅有共享工作树既有 LF/CRLF 转换提示。
