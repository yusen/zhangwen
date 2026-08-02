# ZW-AGENT-002 - 智能工程师 MicroPython 开发板与代码闭环

状态：已提交（ZW-AGENT-001 至 005 工程节点）

## 1. 目标

在不新增专家、一级 Tab、数据库表或真实硬件操作的前提下，增强智能工程师：代码生成统一采用 MicroPython；开发板档案使用可读写的 Markdown BoardProfile；内置行空板 K10；代码产物可在浮窗中修改并保存为新版本；智能工程师下一次回复能够知道用户修改过代码，并在代码相关请求中读取有界的当前文件内容。

## 2. 不可变边界

- 中央区域仍是唯一项目主对话，代码编辑只进入代码产物浮窗。
- 右侧一级 Tab 仍固定为“工作 / 产物 / 设备”。
- 云端 LLM 不直接写文件、执行 Shell、串口或设备操作；保存由本地 API 完成。
- 用户修改代码后生成新版本并标记待验证，不自动接受、上传、擦除 Flash 或烧录固件。
- MicroPython 日常上传仍优先 USB 串口，并保留备份、端口锁、超时、取消和可观察验证边界。
- Schema 保持 v22，复用 `code_runs`、`code_files`、`code_patches` 和 Artifact 版本。
- BoardProfile 是 Markdown 文件；内置文件只读，修改写入当前数据目录 overlay。
- 自动测试只使用 Fake Provider、Mock/Dry Run，不调用付费 LLM 或真实硬件。

## 3. 可观察验收

- `/api/hardware/board-profiles` 返回内置 `unihiker-k10`；详情内容是 Markdown，不暴露绝对路径。
- K10 Markdown 至少记录官方来源、ESP32-S3 N16R8、16MB Flash、8MB PSRAM、屏幕、板载传感器、接口和 MicroPython 模块边界。
- 专业模式“公共知识”可查看和编辑 K10 BoardProfile，支持 revision 冲突和恢复默认。
- 智能工程师请求提到 K10 时，ContextAssembler 注入匹配 BoardProfile；其他板型请求不注入 K10 全文。
- 代码浮窗提供“代码 / 变更 / 验证”内部视图、文件切换、编辑、放弃和保存。
- 保存代码创建新 CodeRun/ArtifactVersion，旧版本不覆盖；新版本状态为草稿且测试结果明确为“用户修改后待验证”。
- 过期基础版本、未知文件、重复路径、路径穿越和超限内容返回明确 4xx。
- 智能工程师上下文包含用户修改标记、变更摘要和有界的当前代码；其他专家不读取完整代码。
- 打开、保存和关闭代码浮窗时 `CenterChat` 保持单一挂载，输入草稿不丢，右侧一级 Tab 不变。
- 生成一份可复用的 MicroPython Board Skill 模板，并通过 Skill 格式校验。

## 4. 实施步骤

- [x] 增加 BoardProfile Markdown loader、K10 内置档案、API、contracts 和安全测试。
- [x] 扩展智能工程师 `SKILL.md` 与按需 MicroPython/BoardProfile 参考文件。
- [x] 增加用户代码修订 API，复用现有代码和 Artifact 版本表。
- [x] 让 ContextAssembler 感知用户代码修订及当前文件内容。
- [x] 在代码产物浮窗实现可编辑保存 UI 和刷新闭环。
- [x] 生成 Skill 模板，完成自动测试、浏览器验收、文档与交接。

## 5. Decision Log

- 2026-07-11：BoardProfile 使用标准 Markdown 文件和轻量 frontmatter，不新增 SQLite 表；内置文件只读，用户修改写入数据目录 overlay。
- 2026-07-11：用户保存代码创建新 CodeRun/ArtifactVersion，不原地覆盖；保存后状态为 `DRAFT`，在重新验证前不得接受或上传。
- 2026-07-11：代码编辑器复用产物浮窗，内部使用“代码 / 变更 / 验证”视图，不复制 Codecraft 的页面或烧录入口。
- 2026-07-11：智能工程师总是知道当前代码是否由用户修改；只有代码相关请求才注入有界文件正文，控制 Provider 上下文大小。
- 2026-07-11：保存和验证都以当前 CodeRun 为 compare-and-swap 基础；保存使用 `BEGIN IMMEDIATE`，旧基础版本返回 `CODE_REVISION_CONFLICT`，旧验证目标返回 `CODE_VALIDATION_CONFLICT`，前端保留未保存代码与摘要。
- 2026-07-11：MicroPython 静态、语法和 Mock 模拟验证使用固定 argv、`shell=False`、隔离临时目录和超时；每项及总体状态只由真实进程 `exitCode` 推导，输出文本不得制造通过状态。
- 2026-07-11：用户保存后的下一次智能工程师 Provider 调用重新装配最新代码版本、变更摘要、diff、验证结果和匹配 BoardProfile；未保存浏览器草稿永不进入 Provider 上下文。
- 2026-07-11：可复用 MicroPython Skill 模板只规定流程和验证契约，板型引脚、内存、模块等事实必须从有效 BoardProfile 加载，避免复制后漂移。
- 2026-07-11：浮窗层固定高于窄屏侧栏；`<=720px` 从右侧产物打开浮窗时自动收起右栏，保证代码和验证操作可达且不卸载中央对话。

## 6. Progress

- 2026-07-11：完成 Codecraft 自动浇花实例分析，确认采用设备知识、硬件冲突检查、版本化代码和验证闭环；拒绝复制其编译失败仍显示 pass、波特率不一致和缺少泵安全保护的问题。
- 2026-07-11：确认现有 v22 表足以承载代码修订版本，无需迁移；确认 K10 官方文档支持 ESP32-S3 N16R8 和 MicroPython 专用模块。
- 2026-07-11：从未提交工作树恢复本阶段；已完成位置、状态、差异统计和 `git diff --check` 基线检查，开始按当前文件与目标测试核验 BoardProfile、代码不可变修订及智能工程师上下文，现有修改不清理、不覆盖、不重复实现。
- 2026-07-11：源码与 16 个目标后端测试确认 K10 BoardProfile loader/API/overlay/revision/reset、用户代码不可变新版本/旧版本保留/409/路径边界，以及智能工程师有界读取用户修改和匹配 BoardProfile 均已实现；后续只补验证结果上下文、原子冲突、安全校验、浮窗 UI 与本地验证闭环。
- 2026-07-11：完成本地验证闭环：静态凭据/主机能力检查、Python 语法检查和 Mock MicroPython/K10 模拟测试均在受控 worker 中执行；生成代码只有真实验证通过才进入 `READY_FOR_REVIEW`，用户保存版本先进入三项 `NOT_RUN`，验证失败不得接受。
- 2026-07-11：完成代码产物浮窗“代码 / 变更 / 验证”、文件切换、摘要、放弃、不可变保存、验证与 409 保稿；保存后产物列表和浮窗更新到新版本，旧 ArtifactVersion 保留，并持续显示“未保存修改智能工程师不可见；保存后下一次回复可见”。
- 2026-07-11：完成智能工程师上下文闭环和 Provider 回归：下一次代码相关回复实际收到用户保存的新文件正文、变更摘要、diff、三项验证结果及匹配 BoardProfile；正文按 12k 预算有界分配，其他专家不读取完整代码。
- 2026-07-11：生成 `experts/skill-templates/micropython-board-project/`，包含 `SKILL.md`、`references/BOARD_PROFILE.md` 和 `references/VALIDATION.md`，格式校验通过且不硬编码 K10 板型事实。
- 2026-07-11：真实浏览器完成 390x844、720x720、1280x720 验收；编辑 README 并保存为 v2、查看 unified diff、运行三项 exitCode=0 验证，中央草稿始终保留，`main` 数量为 1，右侧一级 Tab 未变化，页面/浮窗/验证区无横向溢出或遮挡，控制台无 error/warn。
- 2026-07-11：后端全量 190 tests、compileall、Cargo check 和 Skill quick validation 通过；前端最终全量门禁结果记录在 `HANDOFF.md`。任务达到自动验收通过，但按用户要求本轮不提交、不打标签。

## 7. Safety

- 不连接或扫描真实串口，不运行 mpremote/esptool，不擦除或烧录 Flash。
- 不把用户修改的未验证代码标记为通过或已接受。
- 不把官方未提供的电流、引脚或固件结论写成确定事实。
- 不暂存或覆盖 `tasks/ZW-UX-003-three-expert-system.md` 的用户自有改动。
