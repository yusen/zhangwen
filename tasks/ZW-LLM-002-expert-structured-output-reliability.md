# ZW-LLM-002 — 三师结构化输出与 microSD 代码可靠性

状态：M4 实现完成且自动验收通过；重启后真人重试待用户（2026-07-16）

## 1. 目标

修复真实桌面中提交整组需求确认后，智能工程师连续两次返回
`LLM_OUTPUT_INVALID` 的问题，同时保持云端输出不可信、本地校验权威和设备操作安全边界。

## 2. 已确认原因

- 本次答案与来源问题均已持久化；失败发生在智能工程师 `ExpertRuntime` 的结构化输出校验阶段。
- `uiPayload` 在 `ExpertRuntimeOutput` 的 Provider JSON Schema 中只是通用字典，澄清问题的严格结构只在
  返回后校验；`question` 还必须逐字段复制 `questions[0]`，真实模型容易连续违反冗余契约。
- K10 Board Skill 的 TF 卡读取示例需要 `import os` 与 `os.listdir("/sd")`，而当前 MicroPython
  静态边界把整个 `os` 模块当作主机能力拒绝；同类电子相册历史回复曾被迫改成内存存图才通过。
- 失败运行只保存通用用户错误，不保存脱敏后的校验类别/字段；无法在不重放真实付费请求的情况下
  区分 JSON 缺失、Pydantic 字段错误和本地代码边界错误。
- 2026-07-16 真实 NTP 闹钟回归的两次 Provider 输出可以进入本地代码校验；失败记录明确显示普通字符串
  `replace()` 被按文件替换调用拒绝，`YOUR_WIFI_PASSWORD` 类非秘密占位符被按真实硬编码凭据拒绝。

## 3. 非目标与安全边界

- 不调用真实云端 LLM，不读取或输出 API Key。
- 不执行真实串口扫描、连接、代码上传、设备重启、Flash 擦除或固件烧录。
- 不允许生成代码在主机验证过程中执行。
- 不放开文件写入、删除、重命名、Shell、进程、网络或动态执行能力。
- 不修改并行 `ZW-AGENT-006` 的当前任务指针，不创建 `ZW-017`。

## 4. 实施计划

### M1：先补回归

- 证明 Provider Schema 明确包含澄清问题字段，而不是任意对象。
- 证明省略或错误复制兼容 `question` 时由 Sidecar 从 `questions[0]` 规范化。
- 证明 K10 `os.listdir("/sd")` 可通过静态与语法检查，同时 `os.system`、删除和 `open` 仍被拒绝。
- 证明两次无效输出的用户错误不变，但 `expert_runs.error` 可保存不含模型原文的脱敏诊断。

### M2：实现

- 为澄清 payload 增加类型化 Provider Schema，并在验证后保持字典兼容输出。
- 把 `question` 降为兼容镜像字段，由本地从首题生成，不再要求模型精确复制。
- 只从禁止导入列表移除 `os`；继续按 AST 拒绝 `system/remove/rename/open` 等调用。
- `StructuredLLMError` 增加仅供本地审计的脱敏诊断，不改变前端 `LLM_OUTPUT_INVALID` 文案。

### M3：验证与交接

- 运行结构化 Runtime、MicroPython 校验、聊天流和真实 LLM fake-provider 边界测试。
- 运行相关 Python 编译与 `git diff --check`。
- 更新本任务、`PLANS.md` 和 `HANDOFF.md`；不暂存、不提交、不打标签、不推送。

### M4：真实 NTP 闹钟回归修复

- 以本机 `expert_runs.error` 为证据复现字符串 `replace()` 和 Wi-Fi 凭据占位符误报。
- 只允许明确的非秘密占位值；真实硬编码 API Key、访问令牌和 Wi-Fi 密码继续拒绝。
- 区分普通对象方法与 `os`/`uos` 文件变更调用；字符串 `replace()` 放行，设备端删除、重命名、
  替换和系统命令继续拒绝。
- 运行 MicroPython 校验、智能工程师 Runtime 和聊天链路定向回归；重启 Sidecar 后再进行真人重试。

## 5. Decision Log

- 2026-07-15：不增加本地模板回退或第三次模型调用；修复 Schema 表达和确定性校验冲突。
- 2026-07-15：允许 MicroPython `os` 仅因为代码不会在主机执行，且破坏性/执行性调用仍由 AST 黑名单拒绝。
- 2026-07-15：不保存 Provider 原始无效输出；诊断只保存错误类型、字段位置和受控本地错误文本。
- 2026-07-15：保留前端兼容的 `question` 字段，但其值由 Sidecar 从 `questions[0]` 规范化。
- 2026-07-16：凭据占位符必须是本地白名单中的显式非秘密值；不因修复误报而允许真实凭据进入代码。
- 2026-07-16：破坏性方法名只在直接危险调用或已解析为 `os`/`uos` 模块调用时拒绝，不再按任意对象的
  同名方法全局拦截。

## 6. Progress

- 2026-07-15：完成只读诊断，确认本次运行、答案持久化、重试次数、Schema 缺口和 microSD 校验冲突；M1 开始。
- 2026-07-15：M1 完成。新增 Provider Schema、兼容镜像规范化、microSD 安全调用和脱敏诊断回归；修复前
  结果为 `7 failed, 35 passed`，准确覆盖四个缺口。
- 2026-07-15：M2 完成。`uiPayload` 改为字典兼容的类型化边界；`question` 由 Sidecar 从首题生成；
  MicroPython 允许导入 `os` 但继续拒绝 `system/remove/rename/open`；失败运行只保存字段级脱敏诊断。
- 2026-07-15：M3 完成。针对性回归 `42 passed`；聊天、代码/CAD Artifact、进度与 fake-provider 边界
  `66 passed, 1 warning`；代码生成与三师 Runtime 扩展回归 `23 passed, 1 warning`；5 个 Python 文件
  内存编译和定向 `git diff --check` 通过。环境未安装 Ruff，未将其伪报为通过。
- 2026-07-15：未调用真实云端 LLM、串口或设备；未暂存、提交、打标签或推送。用户可在当前桌面重试
  原失败消息，真实 Provider 行为作为最后的人工验收。
- 2026-07-16：用户真实桌面重试仍出现“云端模型连续两次未返回有效结构”；任务重新进入调查，开始核对
  当前 Sidecar 版本、本机 `expert_runs` 脱敏诊断以及需求确认后的智能工程师输出校验链路。
- 2026-07-16：M4 实现完成。静态校验允许显式非秘密 Wi-Fi 占位符和普通字符串/容器的
  `replace()`/`remove()`，但仍拒绝真实硬编码密码、直接危险调用以及 `os`/`uos` 文件变更和系统命令；
  智能工程师提示词要求未提供网络配置时使用固定占位符，不得猜测凭据。
- 2026-07-16：M4 定向回归合计 `140 passed`；两组各有 1 条既有 Starlette/httpx 弃用警告。
  4 个 Python 文件内存编译和定向 `git diff --check` 通过。未调用真实付费 LLM、串口或设备，未终止
  当前桌面进程；正在运行的非热重载 Sidecar 早于本次修复启动，需关闭并重新运行 `start-local.bat`
  后再重试原消息。
