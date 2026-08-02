# ZW-LLM-001 — 生产业务强制真实 LLM

状态：已完成（2026-07-10）

## 1. 目标

将掌问所有需要理解、路由、规划内容、生成或修订内容的生产业务路径统一接入已配置的真实 DeepSeek，不再用本地模板、关键词规则或静默降级伪装成模型结果。

本任务所称“所有操作”按产品安全边界分为：

- 必须调用真实 LLM：项目创意路由、三师回复、需求澄清、推荐方案生成/修订、立项书生成/修订、Spec 内容、MicroPython 代码草稿、CAD 模板/参数设计、课程教案。
- 必须保持本地确定性：权限与确认、状态机、版本持久化、硬件电气校验、输出 Schema 校验、代码静态检查、CAD 参数边界/几何校验、文件/Shell/串口/设备执行。

## 2. 非目标

- 不允许云端 LLM 直接访问项目数据库、文件系统、Shell、串口或设备。
- 不把硬件电气规则、审批门禁、版本状态和设备安全交给模型决定。
- 不在自动测试中调用真实付费 LLM；自动测试继续使用 fake provider。
- 不读取、打印、记录或提交真实 API Key。
- 不扫描、连接或写入真实设备，不执行 `mpremote`、`esptool`、Flash 擦除或固件烧录。
- 不创建、规划或实现 `ZW-017`。

## 3. 初始审计与完成状态

- 初始已使用 Provider：项目聊天、三师 ExpertRuntime、澄清、推荐方案生成与修订。
- 初始缺口已修复：生产 EntryRouter 不再回落关键词路由，桌面已删除 `localSuggestProject()`；立项书、Spec、MicroPython 代码、CAD 设计输入和教案均已改为 Provider 驱动。
- 生产 HTTP 创建项目在缺少 `routerResult` 时必须先调用 Provider；仓储层的同步路由辅助仅供测试夹具和项目包本地导入恢复，不对外伪装为 AI 成功结果。
- 继续本地执行并保持权威：硬件 Rule Engine、Spec/CAD/代码输出校验、Artifact 同步、审批、文件/Shell/串口/设备操作。

## 4. 契约与错误

新增共享生产约束：

- 所有 AI 生成入口在 Key 缺失时返回 `CONFIG_MISSING`，不得生成本地替代内容。
- Provider 失败时返回原有可执行 LLM 错误；不得持久化伪造成功的业务产物。
- 两次结构化输出仍不满足 Pydantic Schema 时返回 `LLM_OUTPUT_INVALID`，并保持上一个有效版本不变。
- 每个生成操作只持久化通过 Schema 与本地安全校验的输出。
- ModelRouter 继续选择并审计模型；生产 Provider 固定通过 LLM Gateway 调用。

## 5. 里程碑

### M1：共享结构化 LLM 边界与项目入口

- 新增可复用的结构化 completion、JSON 提取、Pydantic 校验、一次修复重试和错误模型。
- 项目建议接口始终调用 Provider；显式专家选择作为模型约束，不再绕过调用。
- 创建项目缺少 `routerResult` 时由后端调用真实 EntryRouter；已有模型建议可复用，用户手工选择仍优先。
- 删除桌面 `localSuggestProject()` 降级；模型失败时显示可重试错误并禁止使用伪建议创建。

### M2：立项书

- 直接 API 与中央对话的立项书生成/修订共用真实 LLM 服务。
- 模型返回固定章节 Schema；本地 Repository 只负责版本、状态、Artifact 同步和过期传播。
- 立项书确认/拒绝/导出保持本地确定性。

### M3：Spec、代码、CAD 与教案

- Spec：模型生成项目规格与 IO 建议；BOM 组件和电气兼容由本地硬件库/Rule Engine 约束。
- 代码：模型生成受限文件清单；本地校验路径、必需文件、密钥模式和 Python 语法，不执行真实 Shell。
- CAD：模型选择允许的模板和参数；本地边界/几何校验与受控 STEP/STL 预览保持权威，不执行用户 Python。
- 教案：模型生成四类文档；本地固定文件类型/路径并执行敏感信息检查。

### M4：验证与收尾

- fake provider 覆盖每个入口只调用 Provider、无 Key/无效 JSON/Provider 失败不落伪产物。
- 运行全量后端、前端、类型检查、构建和 Cargo。
- 使用隔离临时数据和 Windows Credential Store 中已保存的 Key 执行真实 DeepSeek 烟测；不输出 Key，不触发设备路径。
- 更新 API/Decision/HANDOFF/PLANS，创建独立提交和本地阶段标签；不推送。

## 6. 验收标准

- 项目建议、立项书、Spec、代码、CAD 设计和教案的生产请求均可由 fake provider 测试证明恰好发生模型调用。
- 删除或绕过 API Key 后，上述入口全部返回 `CONFIG_MISSING`，数据库和 Artifact 数量不增加。
- 无效 JSON 最多重试一次，仍无效返回 `LLM_OUTPUT_INVALID`，不得回落到本地模板。
- 真实 DeepSeek 隔离烟测覆盖项目路由、立项书、Spec、代码、CAD、教案，并保存通过本地校验的产物。
- 真实烟测不执行 Shell、串口扫描、设备连接、上传、Flash 或固件操作。
- 普通/专业模式、中央对话常驻和右侧固定三 Tab 不回归。

## 7. Decision Log

- 2026-07-10：使用用户定向编号 `ZW-LLM-001`，不使用禁止的 `ZW-017`。
- 2026-07-10：“所有操作”限定为所有生产 AI 推理/内容生成；本地安全、执行和持久化不是 LLM 操作。
- 2026-07-10：自动测试必须继续 fake provider；真实付费调用只进入单独标记的隔离烟测步骤。
- 2026-07-10：模型失败必须显式失败，不允许本地模板或关键词路由伪装成成功结果。
- 2026-07-10：保留 `useModelRouting` 请求字段用于旧客户端兼容，但生产建议接口忽略其布尔值并始终调用 Provider；已有有效 `routerResult` 可在创建请求中复用，缺失时由后端补做一次模型路由。
- 2026-07-10：立项书模型只返回固定六章节的内容字段；本地服务固定章节 ID/标题并在持久化前校验顺序和非空内容，Repository 不再生成或追加本地章节。
- 2026-07-10：Spec 的项目目标、模块、验收、风险、硬件候选和 IO 建议来自模型；本地硬件库过滤组件并运行电气 Rule Engine/IO 引用校验。代码固定为五个受限路径并在持久化前执行敏感模式、Shell 能力和 Python AST 检查。CAD 模型仅能选择允许模板和数值参数，用户约束优先，本地范围/几何预览权威。教案固定四类 Markdown 路径并在持久化前扫描凭据、真实串口标识和本机路径。

## 8. 预计修改范围

- LLM：`services/local-api/zhangwen/llm/` 共享结构化调用与错误。
- 项目入口：`experts/entry_router.py`、`projects/router.py`、桌面项目创建对话框及测试。
- 生成器：`proposals/`、`specs/`、`code_agent/`、`cad_agent/`、`lesson_agent/` 及对应测试。
- 对话：`chat/idea_flow.py` 和项目聊天回归。
- 契约/文档：`packages/contracts`、`docs/API_EVENTS.md`、`docs/DECISIONS.md`、本任务、`CURRENT_TASK.md`、`PLANS.md`、`HANDOFF.md`。

## 9. 安全与回滚

- `.codex/config.toml` 保持本地忽略，不进入暂存或提交。
- 真实 Key 只从 Windows Credential Manager 读取到进程内存，不写日志、数据库、导出包或测试 Fixture。
- 真实烟测使用隔离临时项目数据；不得删除现有项目或覆盖现有 Artifact。
- 回滚以本任务独立提交为边界，不修改历史提交，不强推。

## 10. Progress

- 2026-07-10：用户要求所有生产业务调用真实 LLM。完成初步审计并建立 ExecPlan；M1 开始。
- 2026-07-10：M1 完成。新增共享结构化 completion、JSON 提取、Pydantic 校验、一次修复重试、`LLM_OUTPUT_INVALID` 和 HTTP 错误映射；项目建议与缺少 `routerResult` 的创建强制调用 Provider，显式选师作为模型约束并保持用户优先；桌面删除本地建议降级并在模型失败时清空建议、禁用创建、提供重试。定向后端 13 通过，桌面 14 通过，contracts typecheck 与 Python compile 通过。M2 开始。
- 2026-07-10：M2 完成。新增 Provider 驱动的立项书生成/修订服务，直接 API 与中央对话共用固定六章节 Schema；Repository 仅接收已校验章节并处理版本、状态和 Artifact。缺 Key/无效输出不新增立项书版本，聊天结构化错误进入 `chat.error`。立项书/Artifact 定向 18 通过，聊天回归 23 通过。M3 开始。
- 2026-07-10：M3 完成。Spec、代码、CAD 和教案全部迁移到共享 Provider 结构化调用，保留本地硬件/IO、路径/AST/敏感模式、模板参数/几何和文档敏感信息校验。任务级强制 Provider/失败边界 15 通过，跨生成链路定向回归 41 通过。M4 开始。
- 2026-07-10：M4 完成。任务级 fake-provider 边界 17 项通过；全量后端 149 通过，全量桌面 7 文件/67 测试通过，contracts build/typecheck、根 typecheck、桌面生产构建、Cargo check、Python compileall 和 `git diff --check` 通过。真实 DeepSeek 隔离烟测通过项目路由/创建、两位工程师、问题引导、方案、立项书、Spec、代码、CAD 和教案；隔离库生成 11 个 Artifact/11 个版本、6 条模型路由审计、2 条专家运行、1 条立项书及 Spec/代码/CAD/教案运行。未执行 Shell、串口、上传、Flash 或固件操作。

## 11. 收尾状态

- 分支：`codex/zw-005-016-autonomous`。
- 实际改动：共享 LLM 边界与错误契约；项目入口和桌面建议；对话/三师/澄清/方案；立项书、Spec、代码、CAD、教案生成器；fake-provider 与真实隔离烟测；API/决策/任务/交接文档。
- 项目内剩余工作：无。真实设备、Shell、上传、Flash 和固件仍属独立高风险确认项，本任务不执行。
- 已知非阻断项：后端有 1 条既有 Starlette/httpx 弃用警告；桌面异步测试有既有 React `act(...)` 警告。Windows 临时 SQLite 清理竞态已通过 `TestClient` 上下文和 `ignore_cleanup_errors=True` 修复，为避免重复付费未重放全部真实调用。
- 下一条命令：提交并创建本地标签后运行 `git status --short --branch` 和 `git log -1 --oneline --decorate`，确认仅保留用户所有的 `tasks/ZW-UX-003-three-expert-system.md` 两条运行记录以及已忽略的 `.codex/config.toml`。
- 版本边界：独立提交 `feat(ZW-LLM-001): require provider-backed generation`，本地标签 `zw-llm-001-complete`；不推送。
