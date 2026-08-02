# ZW-HW-001 — Hardware Skill 单一事实源、创建工作流与 Skill 项目编辑器

状态：已完成（2026-07-15，未提交）

## 1. 目标

1. 把每个硬件器件收敛为一个目录化 Hardware Skill；`SKILL.md` 与 `references/*.md` 是器件说明、结构化电气参数、兼容规则和三位工程师上下文的唯一权威来源。
2. SQLite `hardware_components` 只保留可重建的查询、库存和项目引用投影；任何兼容校验前都必须从当前有效 Hardware Skill 解析参数和规则，不能把旧 `electrical_json` 当作权威输入。
3. 新增 Hardware Skill 创建工作流：用户可上传受控资料或在创建器内通过受控补充对话完善资料，中央对话保持挂载；Sidecar 生成并校验草稿，只有用户明确确认后才原子落盘并激活。
4. 所有 Hardware Skill 统一保存到 `<data_dir>/hardware-skills/<skill-name>/`，采用用户参考 `openclaw-robot-dog-soul-k12` 的 `SKILL.md + references/ + examples/` 渐进加载形式。
5. 把硬件 Skill 和三位工程师 Skill 都放入现有浮窗体系，以文件夹树 + Monaco Markdown 编辑器呈现；不新增页面或右侧一级 Tab，不重写 `AppShell`。
6. 在专业模式设置中明确三师确认/修改入口：`设置 → 智能体 → 打开行为项目`。保存后的有效 Markdown 从下一次目标工程师回复开始生效。

## 2. 不可变边界

- 中央 `CenterChat` 始终单实例挂载；设置、创建工作流和 Skill 浮窗不得丢失草稿、滚动、附件或引用。
- 右侧一级 Tab 固定为“工作 / 产物 / 设备”；普通模式隐藏 Agent、Skill、模型和工具链细节。
- 云端 LLM 只能根据 Sidecar 提供的有界文本生成结构化草稿或提出缺失问题；不得直接读写文件、执行规则、调用 Shell、串口或设备。
- Hardware Skill 不授予执行权限。禁止 Python、Shell、动态表达式、任意函数名或文件路径成为兼容规则操作符。
- Sidecar 只执行白名单声明式规则，并由 Pydantic 边界模型校验；PASS/WARNING/FAIL 只能来自本地确定性结果。
- 上传资料限制为受控类型、大小和 UTF-8/本地解析结果；API Key、Wi-Fi 密码、串口标识、绝对路径和其他隐私数据不得写入 Skill。
- 保存使用整包 revision compare-and-swap、临时目录、`fsync` 和原子替换；未保存或校验失败的草稿不得进入三师上下文或规则引擎。
- 本任务不调用真实云端 LLM，不扫描或连接串口，不上传代码，不重启设备，不执行 Flash 擦除或固件烧录。
- 工作树包含 ZW-UX-003/005/006/007、ZW-AGENT-006、ZW-PKG-001、K10、CAD 和设备并行改动；不得使用 `git add -A`、整库 stash、reset、clean 或整文件回退。

## 3. Hardware Skill 目录和权威数据

```text
<data_dir>/hardware-skills/
└─ <skill-name>/
   ├─ manifest.json
   ├─ SKILL.md
   ├─ references/
   │  ├─ specifications.md
   │  ├─ compatibility-rules.md
   │  ├─ integration.md
   │  ├─ safety.md
   │  └─ sources.md
   ├─ examples/
   │  └─ usage.md
   └─ tests/
      └─ validation-cases.md
```

- `manifest.json` 只保存系统管理的 ID、显示名、状态、schema 版本、文件白名单和内容 revision，不承载电气或兼容真值。
- `references/specifications.md` 包含唯一 `zhangwen:hardware-spec:v1` JSON fenced block，定义类别、电压、逻辑电平、峰值电流、协议、I2C 地址、兼容主控、库存/价格/年龄和验证来源状态。
- `references/compatibility-rules.md` 包含唯一 `zhangwen:hardware-rules:v1` JSON fenced block；操作符首期限制为 `range-overlap`、`sum-lte`、`unique`、`contains-any`、`required-if`。
- `tests/validation-cases.md` 包含唯一 `zhangwen:hardware-validation:v1` JSON fenced block，用固定输入和预期 PASS/WARNING/FAIL 验证当前声明式规则。
- `SKILL.md` 负责适用场景、使用边界和渐进加载导航；三位工程师读取同一份已通过校验的有效包。
- 旧 SQLite 行首次读取时迁移为 Skill 目录，并写入等价参数/默认规则；迁移完成后数据库字段只是兼容投影。新建和编辑均先写 Skill，再同步投影。

## 4. 创建与编辑交互

### 4.1 创建 Hardware Skill

- 硬件库主操作为“新建 Hardware Skill”，打开现有浮窗/覆盖层中的三步工作流：资料、补充、预览确认。
- 资料步骤支持粘贴说明和上传受控文档；首期至少支持 UTF-8 Markdown、TXT、JSON、CSV，并对 PDF 使用本地只读文本提取，不把原始文件直接交给云端。
- Sidecar 返回 `DRAFT`、提取字段、缺失问题、来源摘要和校验问题。用户可继续在同一工作流中发送补充回答，生成新 revision。
- 预览展示目录树、结构化参数、声明式规则及 PASS/WARNING/FAIL 示例；确认激活前必须无阻塞校验问题。
- 用户确认后 Sidecar 原子创建目录、同步 SQLite 投影并返回新的 Hardware Skill；取消只删除当前会话的临时草稿。

### 4.2 编辑 Hardware Skill

- 列表项显示 Hardware Skill 名称、类别、状态、验证来源和最近更新时间；“打开 Skill 项目”使用 `hardware-skill:<skill-name>` 单例浮窗。
- 左侧文件树，右侧 Monaco Markdown；支持文件切换、保存、放弃、加载/错误/成功状态和只读结构化预览。
- 参数和规则文件保存前由 Sidecar 重新解析并运行包内 validation cases；失败时保留本地草稿并显示具体中文问题。

### 4.3 三位工程师 Skill

- 当前内置位置继续为 `services/local-api/zhangwen/experts/agent-packages/<expert>/`，用户覆盖继续保存到 `<data_dir>/agent-packages/<skill-name>/`。
- 专业模式 `设置 → 智能体` 只保留工程师摘要、执行能力边界和“打开行为项目”；编辑器使用 `agent-package:<expertType>` 单例浮窗。
- 文件树包含 `SKILL.md` 与 manifest 白名单中的 `references/*.md`；`manifest.json` 只读，不能通过 Markdown 修改身份、Skill 绑定、权限或 Tool Runner 边界。
- 最小化保留多文件草稿；关闭或第四浮窗淘汰脏编辑器前确认；409 刷新服务端 revision 但保留本地草稿。

## 5. API / 契约

- Hardware Skill 状态：`DRAFT | ACTIVE | ARCHIVED | INVALID`；当前公共库只列 ACTIVE，DRAFT 留在创建会话，ARCHIVED 隐藏，编译失败以 422 失败关闭而不伪装成 ACTIVE 项。
- Hardware Skill 文件、摘要、详情、结构化 specification、声明式 rule、validation issue 和 draft session 使用 shared contracts。
- `GET /api/hardware/skills`
- `GET /api/hardware/skills/{skillName}`
- `PUT /api/hardware/skills/{skillName}/files`
- `POST /api/hardware/skills/drafts`
- `POST /api/hardware/skills/drafts/{draftId}/messages`
- `POST /api/hardware/skills/drafts/{draftId}/confirm`
- `DELETE /api/hardware/skills/drafts/{draftId}`
- 创建/补充请求携带受控文本资料，不携带主机绝对路径；PDF 以大小受限的 base64 内容传输并在 Sidecar 本地提取。
- 非法路径、类型、结构块、算子或字段引用返回 422；revision 冲突返回 409；敏感信息检测失败时拒绝保存。
- 现有 `/api/hardware`、`/api/hardware/{componentId}` 和 `/api/hardware/validate` 保留兼容，但返回值及规则输入必须来自有效 Hardware Skill；旧四文件 package GET 只读映射当前 revision，旧 PUT 固定返回 410。

## 6. 可观察验收

- [x] 旧种子组件可自动迁移为统一目录 Skill，列表/项目选择/Spec 流程保持兼容；修改 SQLite `electrical_json` 不会改变规则结果，修改并保存 Skill 会改变结果并同步投影。
- [x] 自定义规则至少覆盖电压范围、总峰值电流、I2C 地址唯一、主控包含和条件必填；未知算子、动态表达式和恶意字段路径被拒绝。
- [x] 上传文档与对话补充都能生成 `DRAFT`；未确认草稿不出现在 ACTIVE 硬件库、不进入三师上下文；确认后目录和 SQLite 投影原子可见。
- [x] Hardware Skill 文件树严格匹配 `SKILL.md + references + examples + tests`，相对链接、UTF-8、大小、路径、symlink、revision 和敏感信息边界均有测试。
- [x] 三位工程师可从 `设置 → 专业模式 → 智能体 → 打开行为项目` 分别确认和修改目录化 Markdown；保存后下一次目标工程师回复读取新内容，未保存草稿不可见。
- [x] 硬件和工程师 Skill 浮窗在 `390x844`、`720x720`、`1280x720` 无页面级横向溢出，中央 `main` 始终为 1、草稿保持、右侧 Tab 仍只有“工作 / 产物 / 设备”。
- [x] contracts build、desktop strict typecheck/build、定向 Vitest、Sidecar pytest、`git diff --check` 通过；测试不调用真实 LLM、串口、设备或 Flash。

## 7. 实施步骤

- [x] M1：审计现有 SQLite Rule Engine、器件 Markdown overlay、K10 Board Skill、三师 Agent 包和 OpenClaw 参考格式；确定单一事实源与安全边界。
- [x] M2：更新 shared contracts、Python Pydantic 模型与失败测试。
- [x] M3：实现 Hardware Skill 包仓储、旧组件迁移、SQLite 投影同步和声明式规则解释器。
- [x] M4：实现上传/对话草稿、确认激活和三师有效上下文装配。
- [x] M5：实现 Hardware Skill 创建/列表/目录树浮窗和三师 Agent Skill 目录树浮窗。
- [x] M6：完成自动回归、三档 UI Contract 验收、PRD/API/Architecture/Decision/Baseline、任务与 HANDOFF 收尾。

## 8. Decision Log

- 2026-07-15：本任务显式取代 ZW-UX-007“SQLite 结构化字段仍为电气/安全规则真值”的决定。Hardware Skill Markdown 是唯一事实源，SQLite 仅保留兼容查询与事务投影。
- 2026-07-15：`manifest.json` 不承载电气真值；机器可读数据位于带版本标记的 JSON fenced block 中，使用户仍能以 Markdown 项目确认和修改全部规则。
- 2026-07-15：Skill“完成规则引擎”指声明规则和数据；规则执行仍由 Sidecar 通用白名单解释器负责，不能让云端模型或 Skill 文件执行代码。
- 2026-07-15：创建采用 `DRAFT → 本地校验 → 用户确认 → ACTIVE`，上传和对话是同一草稿会话的两种输入，不创建两套硬件模型。
- 2026-07-15：三师 Agent 包继续使用现有后端目录与 overlay API，只升级为浮窗文件树/Monaco 交互；`manifest.json`、权限与工具能力不开放编辑。

## 9. Progress

- 2026-07-15：M1 完成。当前存在 SQLite `electrical_json`、四文件器件 overlay 和 K10 Board Skill 三套来源；用户参考包确认采用单入口 `SKILL.md`、`references/`、`examples/`，但其自然语言自检不能直接承担确定性电气门禁。
- 2026-07-15：创建本 ExecPlan。工作树已有大量并行未提交改动，本任务按精确文件和 diff hunk 保留边界，不修改 `CURRENT_TASK.md`。
- 2026-07-15：M2 开始。shared contracts 已新增 Hardware Skill 生命周期、来源、白名单算子、目录文件、草稿会话和两个 Skill 浮窗类型；contracts build 通过，随后按后端核心、项目上下文和前端编辑器三个互斥文件边界并行实现。
- 2026-07-15：M2/M3 完成。新增目录仓储、固定文件白名单、结构块编译、敏感信息/路径/symlink/大小/revision 门禁、旧行幂等迁移、Skill → SQLite 投影同步和五类声明式算子。`test_hardware_skills + ZW-005 CRUD/Rule Engine + project hardware intake` 共 `44 passed`；contracts build、Python `py_compile` 和 desktop strict typecheck 通过。
- 2026-07-15：M4/M5 联调中。草稿 API、项目 `preferred_hardware` Skill revision、Spec/项目校验与三师 ContextAssembler 已切到有效 Skill；前端 Hardware Skill 创建器、目录树编辑器和三师行为项目浮窗已落地，正在更新跨工作区旧 UI 回归。
- 2026-07-15：M4/M5 完成。上传与创建器内补充对话共用 DRAFT 会话，支持 PDF 本地只读文本提取；确认后才创建正式目录并同步 SQLite 投影。三师入口固定为“设置 → 专业模式 → 智能体 → 打开行为项目”，行为 Markdown 与受控执行能力分层。
- 2026-07-15：M6 UI 验收完成。隔离 Fake Provider 下完成 `1280x720`、`720x720`、`390x844` 验收；两类 Skill 工作区、创建三步、中央草稿、单一 `main`、固定三 Tab/窄屏收起和页面横向溢出均符合 UI Contract，console 无 error/warn，隔离 DRAFT 已删除。
- 2026-07-15：终审补齐普通模式术语隐藏、关闭专业模式时技术浮窗/脏稿处理、创建器卸载草稿回收、逐项诊断和 Agent 文件恢复内置默认；同步旧 package 410、JSON fence、PDF/大小边界与 DRAFT 存储文档。
- 2026-07-15：M6 完成。contracts build、desktop strict typecheck/build 通过；Desktop 全量 `26 files / 165 tests` 通过；Hardware Skill/项目/Spec 后端组合 `66 passed`，Agent package 除既有乱码 K10 用例外 `8 passed / 1 deselected`；`pip check`、Python `py_compile` 通过。扩大组合为 `74 passed / 1 failed`，唯一失败是并行 K10 测试源码乱码导致 `boardSkill=null`，不属于本任务且未通过改测试或重算 CHECKSUM 掩盖。

## 10. Safety

- 不运行 `git reset --hard`、`git clean`、整库 stash、`git add -A`、强制推送或公开发布。
- 不执行真实 LLM、硬件发现、串口连接、代码上传、设备重启、Flash 擦除或固件烧录。
- 不把上传资料中的密钥、凭据、真实串口 ID、主机绝对路径或隐私数据写入 Skill、日志、测试或 Git。
