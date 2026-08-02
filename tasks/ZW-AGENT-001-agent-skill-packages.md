# ZW-AGENT-001 - 三师 Agent Skill 包配置

状态：已提交（ZW-AGENT-001 至 005 工程节点）

## 1. 目标

把问题引导师、智能工程师和结构工程师的行为配置改为目录化 Agent Skill 包。每个包以 `SKILL.md` 为运行时入口，通过相对路径引用按需加载的 Markdown 参考文件；设置中的专业模式提供可发现、可校验、可恢复默认的文件编辑入口。现有三师身份、权限、Tool Runner、安全确认、项目单一对话和 Provider 历史隔离保持不变。

本任务是用户定向功能，不创建或恢复 ZW-017。

## 2. 不可变边界

- 三位 canonical 智能体固定，不新增、删除或复制专家。
- 一个项目仍只有一条可见时间线和一份项目草稿；`@智能体` 仍只改变下一条消息的目标。
- 每位智能体继续使用独立 `conversationId`、私有记忆和最多 12 条自身 Provider 历史。
- 云端 LLM 不直接读取文件、执行脚本、Shell、串口或设备操作。
- Markdown 不得扩大 Skill 权限、风险策略、工具白名单或硬件安全边界。
- 不新增数据库表或迁移；schema 保持 v22。
- 内置包只读，用户修改写入当前 `settings.data_dir` 下的 overlay；fake、paid 和正式数据继续隔离。
- 保留现有 `skill-description-overrides.json` 和 user Skill 兼容，不做破坏性删除。

## 3. 包结构

```text
experts/agent-packages/<agent-slug>/
|-- manifest.json          # 系统锁定身份、能力、权限边界和参考加载规则
|-- SKILL.md               # 必需，标准 name/description frontmatter + 行为正文
`-- references/*.md        # manifest 声明的可编辑参考文件
```

有效读取优先级：数据目录同路径 overlay > 内置包。保存采用 revision 乐观并发检查和同目录原子替换。只允许 manifest 白名单内的 UTF-8 Markdown 文件；拒绝绝对路径、`..`、未声明文件、错误 frontmatter、断链引用和超限内容。

## 4. 可观察验收

- `GET /api/agent-packages` 只返回固定三师摘要；详情返回 `SKILL.md` 和声明的参考文件，不暴露主机绝对路径。
- `PUT` 保存有效 Markdown 后刷新和重启可恢复；内置源文件不被修改；`POST reset` 恢复默认。
- 错误 frontmatter、错误 name、路径穿越、断链引用、内容超限和旧 revision 均返回明确 4xx。
- 修改后的目标 Agent `SKILL.md`/匹配参考文件进入下一次 Provider system prompt；不进入其他 Agent。
- 当前专家绑定的执行 Skill 名称/描述进入有界能力摘要；已有 Skill 描述覆盖继续生效。
- 项目工作区的三师定义从同一 manifest/config 生成，结构工程师的完整 Skill 列表不再被旧 SQLite seed 截断。
- 普通模式不渲染也不请求 Agent/Skill 配置；专业模式可在设置的“智能体”区选择三师、切换文件、编辑、保存和恢复默认。
- 打开设置、切换智能体/文件、保存或关闭设置时 `CenterChat` 保持单实例，项目草稿不丢；右侧一级 Tab 仍只有“工作 / 产物 / 设备”。
- 390x844、720x720、1280x720 下设置编辑器无页面级横向溢出、控件重叠或不可达操作。

## 5. 实施步骤

- [x] 增加 Agent package contracts、Pydantic 模型、包解析/校验和内置三师包。
- [x] 增加 list/detail/save/reset API，补 overlay、revision、原子写和安全测试。
- [x] 让 expert config、workspace definitions 和三条 Provider prompt 入口读取同一有效包。
- [x] 用录制 Fake Provider 证明目标包内容进入 system prompt 且不跨专家泄漏。
- [x] 把设置改为分区导航，并实现专业模式限定的包文件编辑器与执行能力视图。
- [x] 完成自动测试、浏览器 UI Contract 验收、基线/决策/交接更新。

## 6. Decision Log

- 2026-07-11：Agent 的行为规则使用一个顶层 `SKILL.md`；现有 34 个 Registry Skill 继续作为受控执行能力。UI 明确区分“行为文件”和“执行能力”，不把提示词文本当作工具权限。
- 2026-07-11：不采用样例仓库中的 README 作为运行时入口。README 是面向人的说明；运行时只加载 `SKILL.md` 和 manifest 明确声明、按关键词选中的参考文件。
- 2026-07-11：不把产品 Agent 包放入 `.agents/skills` 或 `ai/skills`，避免与 Codex/Qoder 开发工具 Skill 混淆。
- 2026-07-11：不通过新增 SQLite 表保存文件；使用数据目录 overlay 保持 v22 和旧项目兼容。

## 7. Progress

- 2026-07-11：读取用户提供的 `README.md`、`SKILL.md`、`STYLE_PRESETS.md` 结构，确认采用 metadata -> `SKILL.md` -> references 的渐进加载模型；完成现有前后端、运行时和 UI Contract 差距审查。
- 2026-07-11：完成三师内置包、数据目录 overlay、校验/并发/原子保存、list/detail/save/reset API、共享 contracts 和 7 个包级自动测试。
- 2026-07-11：expert config、项目工作区定义、ExpertRuntime、中央 IDEA 流和澄清/方案生成已统一读取有效包；Recording Provider 证明目标包进入目标 system prompt 且不跨专家泄漏。
- 2026-07-11：专业模式设置已拆分为“模型与界面 / 智能体 / 公共知识”，完成行为文件编辑器、执行能力视图、保存/放弃/恢复默认和响应式布局；普通模式不加载 Agent 包。
- 2026-07-11：浏览器在 390x844、720x720、1280x720 验证无页面级横向溢出，`CenterChat` 单实例、右侧固定三 Tab 和控制台零错误；浏览器保存标记已恢复，fake overlay 无残留。
- 2026-07-11：首轮全量 Python 门禁发现 `_clarify_with_llm` 未显式接收数据目录，导致真实 Provider 澄清路径 6 个回归失败；已最小修复，相关 8 个测试和全量 168 个 Python 测试通过。
- 2026-07-11：最终门禁通过：contracts build/typecheck、desktop typecheck/81 tests/build、Python compileall/168 tests、Cargo check；三个 Agent 包经 `quick_validate.py` UTF-8 模式校验通过。仅保留既有 React `act(...)` 和 Starlette/httpx deprecation warning。

## 8. Safety

- 自动测试只使用 Fake/Recording Provider，不调用真实付费 LLM。
- 不执行 Agent 包中的脚本或资产；本轮仅支持声明过的 Markdown 文本。
- 不操作真实串口、Flash、固件、CAD 或外部发布。
- 不暂存或覆盖 `tasks/ZW-UX-003-three-expert-system.md` 的用户自有改动。
