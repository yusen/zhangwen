# 掌问 Codex 全流程自主开发规则

版本：v1.0  
适用范围：ZW-005 至 ZW-016  
执行工具：Codex  
协作模式：Codex 单工具连续执行  
用户角色：最终审阅者与外部权限提供者  
建议文件名：`CODEX_AUTONOMOUS_WORKFLOW.md`

> 本规则明确在 ZW-016 结束。不得创建、规划或实现 ZW-017。

---

## 1. 目标

本文件用于将“掌问”项目切换为 **Codex 单工具、连续阶段、自主执行** 模式。

Codex 从当前仓库真实状态出发，依次完成：

- ZW-005：本地硬件库与硬件规则引擎
- ZW-006：立项书生成、版本与确认
- ZW-007：Orchestrator 与 Agent Registry
- ZW-008：Skill Registry 与模型路由
- ZW-009：产物系统与浮窗系统
- ZW-010：Spec Agent
- ZW-011：Code Agent
- ZW-012：设备管理与 MicroPython 部署
- ZW-013：CAD Agent
- ZW-014：Lesson Agent
- ZW-015：分享与项目包
- ZW-016：MVP 全流程集成与加固

Codex 负责产品任务拆解、架构、Contracts、前端、Python Sidecar、Tauri、SQLite、Agent、Skill、模型路由、设备、CAD、UI、测试、文档、Git 阶段提交和阶段切换。

目标是：不依赖 Qoder、不依赖聊天历史、不等待普通确认，通过 Git、任务文件、测试和 HANDOFF 保证过程可恢复、可审查、可回滚。

---

## 2. 核心模式

### 2.1 Codex 是唯一正式开发执行器

从本文件生效后：

- Codex 负责所有正式代码修改；
- Codex 负责所有阶段规划、实施、联调、测试和文档；
- Codex 负责阶段提交、标签和自动切换；
- Qoder 不再参与正式代码修改；
- 用户不需要逐阶段确认普通设计和实现细节。

### 2.2 连续执行但按阶段提交

“一口气完成”不等于一次大提交。Codex 必须连续执行，但每个阶段仍建立清晰边界：

```text
读取当前状态
→ 修正规则文件
→ 完成 ZW-005
→ 测试
→ 阶段提交与标签
→ 更新 CURRENT_TASK
→ 自动进入 ZW-006
→ ...
→ 完成 ZW-016
→ 输出最终报告
```

每个阶段必须：

- 有任务文件；
- 有验收条件；
- 有自动测试；
- 有独立提交；
- 有阶段标签；
- 有 HANDOFF 记录；
- 能从该节点恢复。

### 2.3 默认自主决策

Codex 可自行决定，无需停下来询问：

- 文件拆分、组件名称和内部函数名称；
- 私有接口和可逆数据结构细节；
- 普通 UI 样式；
- 测试组织；
- 日志格式；
- 非破坏性数据库索引；
- 不改变外部协议的小范围重构；
- 低风险依赖小版本升级；
- Mock、Fixture、错误文案和低风险性能优化。

优先选择简单、可测试、可恢复、可维护、最少依赖、最小权限且与现有架构一致的方案。

---

## 3. 不可违反的产品约束

### 3.1 主界面

- 中央区域始终属于 `MainConversation`；
- 项目创建只在左侧栏；
- 设置通过右上角齿轮打开浮窗；
- 设置、产物、设备、文档、代码和 3D 模型不得替换中央主对话；
- 右侧一级栏目固定为“工作 / 产物 / 设备”；
- 产物使用右侧栏或浮窗查看；
- 打开或关闭浮窗不得丢失对话草稿；
- 切换项目时保留各项目独立草稿和对话状态。

### 3.2 推荐方案

- 同一时间只维护一套当前推荐实现方案；
- 用户通过对话修改当前方案；
- 修改生成新版本；
- 只有已确认方案才能进入正式产物流程；
- 内部可以保留候选，但前台只显示推荐结果。

### 3.3 Agent、Skill 与模型

- Agent、Skill、模型、Provider、Tool Runner 解耦；
- 同一个 Agent 可在不同步骤选择不同模型；
- Skill 支持内置和用户自定义；
- 普通模式隐藏 Agent、Skill、模型和底层工具细节；
- 专业模式可显示高级信息；
- LLM 不得绕过确定性规则直接执行高风险系统操作。

### 3.4 本地能力与安全

- 前端不得直接执行 Shell、串口或固件烧录；
- 系统操作通过 Tauri 后端或本地 Sidecar；
- API Key 使用系统凭据存储；
- API Key 不得进入项目数据库、导出包、日志、console、测试 Fixture 或 Git；
- 自动测试不得调用真实付费 LLM；
- 串口和固件测试默认使用 Mock；
- 真实 Flash 擦除、固件烧录和用户文件覆盖不得自动执行。

---

## 4. 首次启动时的规则迁移

Codex 收到本文件后，首先执行规则迁移，然后立即继续开发。

### 4.1 必须读取

- `AGENTS.md`
- `WORKFLOW.md`
- `CURRENT_TASK.md`
- `HANDOFF.md`
- `PLANS.md`
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/UI_CONTRACT.md`
- `docs/API_EVENTS.md`
- `docs/DECISIONS.md`
- `docs/development/` 下的协作规范
- `tasks/` 下已有任务
- 最近 5 个 Git 提交
- 当前分支和 `git status`
- 当前测试脚本和目录结构

文件不存在时创建最小可用版本，不得覆盖已有有效内容。

### 4.2 更新协作规则

#### `AGENTS.md`

增加：

- Codex 是唯一正式开发执行器；
- Codex 连续完成 ZW-005 至 ZW-016；
- 用户不需逐阶段确认普通事项；
- 高风险外部操作仍须停止；
- 每阶段必须测试、提交、打标签；
- Git 和 HANDOFF 是恢复依据。

#### `WORKFLOW.md`

调整为：

- Codex 单工具工作流；
- 自动规划、实施、测试和阶段收尾；
- 自动进入下一阶段；
- 额度中断恢复；
- 高风险暂停规则；
- MVP 完成版本交付规则。

#### `CURRENT_TASK.md`

指向当前真实阶段。ZW-004 已完成时设置为 ZW-005。

#### `HANDOFF.md`

只记录：

- 当前阶段和里程碑；
- 已完成、进行中、未开始；
- 测试结果；
- 当前分支和提交；
- 下一步唯一动作；
- 阻塞项。

#### `PLANS.md`

ZW-005 至 ZW-016 使用以下状态：

- 待开始
- 进行中
- 自动验收通过
- 已提交
- 外部验证待完成
- 已完成

### 4.3 规则迁移提交

```text
chore: switch to Codex autonomous development workflow
```

建议标签：

```text
codex-autonomous-workflow-v1
```

规则迁移后立即开始当前阶段。

---

## 5. Git 与分支策略

### 5.1 总任务分支

默认创建：

```text
codex/zw-005-016-autonomous
```

所有阶段在该分支连续执行。除非仓库已有明确规则，否则不要自动合并到 `main`。

### 5.2 阶段提交

```text
feat: complete ZW-005 hardware library and rule engine
feat: complete ZW-006 project proposal workflow
feat: complete ZW-007 orchestrator and agent registry
feat: complete ZW-008 skill registry and model router
feat: complete ZW-009 artifact and window system
feat: complete ZW-010 spec agent
feat: complete ZW-011 code agent
feat: complete ZW-012 device and MicroPython deployment
feat: complete ZW-013 CAD agent
feat: complete ZW-014 lesson agent
feat: complete ZW-015 sharing and project package
feat: complete ZW-016 MVP integration and hardening
```

### 5.3 阶段标签

```text
zw-005-complete
zw-006-complete
zw-007-complete
zw-008-complete
zw-009-complete
zw-010-complete
zw-011-complete
zw-012-complete
zw-013-complete
zw-014-complete
zw-015-complete
zw-016-complete
```

若只缺真实设备或签名验证，使用：

```text
zw-012-software-complete
```

### 5.4 临时提交

额度中断或长任务时可创建：

```text
wip: checkpoint ZW-XXX milestone N
```

### 5.5 禁止操作

未经外部授权不得：

- 强制推送；
- 删除远程分支；
- 重写主分支历史；
- 修改已有发布标签；
- 自动向公共远程发布；
- 自动合并到受保护分支；
- 删除无法判断归属的用户修改。

---

## 6. 每阶段连续执行循环

### 6.1 阶段开始

1. 读取规则、当前任务、HANDOFF、当前任务文件和最近两个提交；
2. 检查已有实现，避免重复开发；
3. 创建或更新任务文件；
4. 写明目标、非目标、数据模型、API、UI、测试、风险和验收条件；
5. 将 `PLANS.md` 当前阶段设为“进行中”。

### 6.2 实现

1. 按里程碑实现；
2. 每个里程碑运行最小测试；
3. 修复失败；
4. 不修改无关模块；
5. 每完成里程碑更新 `HANDOFF.md`。

### 6.3 自动验收

检查：

- 验收条件；
- 类型检查；
- 单元测试；
- 集成测试；
- 构建；
- 敏感信息；
- 数据迁移；
- UI 关键状态；
- 错误恢复；
- 产品约束一致性。

### 6.4 阶段收尾

自动验收通过后：

1. 更新任务文件、HANDOFF 和 PLANS；
2. 创建阶段提交；
3. 创建阶段标签；
4. 更新 CURRENT_TASK 为下一阶段；
5. 继续下一阶段。

若只缺外部设备或真实服务凭据：

1. 软件部分标为完成；
2. 记录外部验证待办；
3. 使用“软件完成”标签或在阶段状态中标记“外部验证待完成”；
4. 继续后续工作。

---

## 7. 额度中断恢复

### 7.1 每个里程碑后保存

`HANDOFF.md` 必须包含：

```text
当前阶段：
当前里程碑：
当前分支：
当前提交：

已完成：
正在进行：
未开始：

已运行测试：
测试结果：

未解决问题：
外部验证待办：

下一次恢复时只需执行：
```

当前任务文件同步勾选完成项并记录测试结果，尽量创建 checkpoint commit。

### 7.2 恢复时只读取

- `AGENTS.md`
- `WORKFLOW.md`
- `CURRENT_TASK.md`
- `HANDOFF.md`
- 当前任务文件
- 最近两个提交
- 当前受影响代码

直接执行 HANDOFF 的“下一次恢复时只需执行”。

### 7.3 不重复消耗额度

- 未修改且已通过的测试不重复；
- 已确定的数据模型不重新设计；
- 已完成阶段不重新审计；
- 不重复生成相同文档；
- 不重新遍历整个仓库；
- 不重新实现已有组件。

---

## 8. ZW-005 至 ZW-016 任务定义

### ZW-005：本地硬件库与硬件规则引擎

必须完成：

- 硬件分类、内置硬件、用户自定义硬件；
- 库存、参考价格、搜索和筛选；
- 电压、IO 电平、电流、GPIO；
- I2C、SPI、UART、PWM、ADC；
- ESP32 型号和 MicroPython 驱动状态；
- BOM；
- 兼容、警告、阻塞结果；
- 推荐方案硬件更新；
- “已有 / 需要购买”。

首版范围：

- ESP32、ESP32-C3、ESP32-S3；
- 按钮、LED、蜂鸣器；
- OLED、超声波、温湿度、土壤湿度、光线；
- SG90、直流电机及驱动、水泵及 MOS 驱动；
- ESP32 摄像头模块。

规则：

- 电气兼容由规则引擎决定；
- LLM 不得覆盖规则结果；
- 硬冲突阻止确认；
- 成本和难度只警告；
- 缺关键参数的自定义硬件不能自动推荐。

---

### ZW-006：立项书生成、版本与确认

必须完成：

- 立项书数据模型、章节模板、生成、版本、修改、确认、退回；
- 过期状态和方案版本关联；
- Markdown、DOCX、PDF 导出；
- 右侧产物和浮窗预览。

章节至少包括：

- 项目名称、目标、需求、功能逻辑；
- 硬件、软件、结构方案；
- 实施步骤、成本、难度、时间、风险和验收标准。

规则：

- 只有已确认方案可生成；
- 方案变化使旧立项书过期；
- 中央主对话不被替换。

---

### ZW-007：Orchestrator 与 Agent Registry

必须完成：

- AgentDefinition、AgentCapability、Agent Registry；
- ExecutionPlan、TaskNode、依赖；
- 状态机、重试、暂停、恢复；
- 用户确认节点、Mock Agent、执行日志；
- 前端工作状态卡片。

初始 Agent：

- Orchestrator
- Spec Agent
- Code Agent
- CAD Agent
- Deploy Agent
- Publish Agent
- Lesson Agent

规则：

- Agent 不直接拥有系统权限；
- 通过 Skill 和 Tool Runner；
- 状态持久化且重启可恢复；
- 普通模式隐藏内部细节。

---

### ZW-008：Skill Registry 与模型路由

必须完成：

- SkillDefinition、输入输出 Schema、权限声明；
- 内置和自定义 Skill；
- Skill Registry；
- Provider 抽象、Model Router；
- 模型策略、重试、降级、成本与质量策略；
- Tool Runner 边界；
- 专业模式 UI。

规则：

- 自定义 Skill 默认无 Shell 权限；
- 权限显式声明；
- 模型调用可 Mock；
- 模型名称不硬编码进 Agent；
- Provider 可替换。

---

### ZW-009：产物系统与浮窗系统

必须完成：

- ArtifactDefinition、ArtifactVersion、ArtifactStatus；
- 依赖与过期状态；
- 产物列表；
- 文档、代码、图片和 3D 预览；
- 通用浮窗、层级、位置和尺寸；
- 关闭后状态保持；
- 右侧产物 Tab；
- 版本切换。

规则：

- 浮窗不得卸载 MainConversation；
- 关闭浮窗不丢草稿；
- 版本和依赖可追踪。

---

### ZW-010：Spec Agent

必须完成：

- Spec Agent；
- `project_spec.yaml`、`bom.yaml`、`io_map.yaml`；
- 功能模块、状态机、软件模块、验收标准和风险；
- 版本、确认、硬件规则一致性；
- 下游过期规则和 Spec 预览。

规则：

- Spec 通过 Schema 校验；
- IO Map 通过硬件规则；
- Spec 变化使代码、CAD、部署产物过期；
- 未确认 Spec 不进入正式代码生成。

---

### ZW-011：Code Agent

必须完成：

- Code Agent；
- 工程工作区、文件白名单；
- Patch、Diff、快照、回滚；
- 测试执行、修复循环、最大重试次数；
- 文件预览、接受和退回；
- 代码 Artifact；
- MicroPython 模板、驱动依赖、配置和 README。

规则：

- 不修改工作区外文件；
- 不直接执行任意用户 Shell；
- 命令通过受控 Tool Runner；
- 所有修改可 Diff、可回滚；
- 测试失败不能标记成功。

---

### ZW-012：设备管理与 MicroPython 部署

必须完成：

- DeviceDefinition；
- 串口发现和 USB 串口；
- `mpremote`、`esptool`；
- 设备状态、端口选择；
- 代码备份、文件上传、增量上传；
- 固件烧录流程；
- REPL 日志、错误恢复；
- Mock 串口、设备面板、操作确认；
- 日志 Artifact。

默认：

- 文件上传使用 `mpremote`；
- 固件烧录使用 `esptool`；
- 自动测试只用 Mock；
- 真实擦除和烧录不自动执行。

无真实设备时标记软件完成并输出设备验收清单，不阻塞后续阶段。

---

### ZW-013：CAD Agent

必须完成：

- CAD Agent；
- CadQuery 执行框架；
- 参数 Schema、模板和尺寸校验；
- 基础几何验证；
- STEP、STL、3D 预览；
- 参数修改、Artifact；
- 安全执行、超时和资源限制。

首版模板：

- 传感器支架；
- 主控板支架；
- 电机支架；
- 舵机支架；
- 简单外壳；
- 面板开孔；
- 盒体与盖板。

规则：

- CAD 在受控环境执行；
- 不执行任意用户 Python；
- 导出失败给出原因。

---

### ZW-014：Lesson Agent

必须完成：

- Lesson Agent；
- 教师版和学生版；
- 学习目标、课时、材料清单、操作步骤；
- 安全说明、评价量表、拓展任务；
- 版本、导出、浮窗预览；
- 与方案和 Spec 关联。

规则：

- 教案变化不修改工程核心数据；
- 引用当前确认版本；
- 旧版本可查看。

---

### ZW-015：分享与项目包

必须完成：

- 项目清单、ZIP 导出和导入；
- Manifest、版本、产物选择；
- 源码、CAD、教案选择；
- 敏感信息扫描；
- 路径穿越防护；
- 校验和；
- 导入冲突处理；
- 分享设置和展示页数据。

不得导出：

- API Key、Token、Wi-Fi 密码；
- 系统凭据；
- 个人绝对路径；
- 临时日志；
- 构建缓存。

---

### ZW-016：MVP 全流程集成与加固

必须完成：

- 端到端流程；
- 项目、方案、立项书、Spec、Agent、Artifact、代码和设备状态；
- 错误恢复、应用重启恢复；
- 数据迁移、日志、性能和安全；
- 全量测试、构建；
- 用户引导、空状态、错误文案、新手流程。

必须全量验证：

- Contracts、前端、Sidecar、Tauri、SQLite；
- Agent、Skill、Artifact；
- Code Agent、Device Mock、CAD；
- 导出导入、敏感信息扫描；
- Desktop build。

---

---

## 9. 测试策略

每阶段运行：

- 受影响模块单元测试；
- 类型检查；
- 必要集成测试；
- 必要构建检查。

全量回归节点：

- ZW-006
- ZW-009
- ZW-012
- ZW-015
- ZW-016

纪律：

- 不调用真实付费 LLM；
- LLM 用 Mock Provider；
- 串口用 Mock Device；
- 固件烧录用 Dry Run；
- 文件导入使用恶意路径 Fixture；
- 数据迁移测试旧版本数据库；
- 不删除失败测试；
- 不降低类型严格度；
- 不用大量 `any` 掩盖问题。

---

## 10. 硬阻塞处理

以下事项不能伪造或自动越权：

- 真实 API Key 不存在；
- 真实设备不存在；
- 擦除真实 Flash；
- 覆盖真实设备文件；
- 需要修改系统安全策略；
- 需要管理员权限但环境不允许；
- 需要删除无法判断归属的用户数据；
- 严重合并冲突；
- 可能不可逆丢失数据的迁移。

遇到时：

1. 保存进度；
2. 创建 checkpoint commit；
3. 更新 HANDOFF；
4. 标记“外部验证待完成”；
5. 继续其他不依赖该阻塞的阶段；
6. 最终报告集中列出。

---


## 10.1 ZW-016 结束边界

完成 ZW-016 后必须停止连续开发。

Codex 应：

1. 完成 ZW-016 全量测试、桌面构建和文档；
2. 创建 `feat: complete ZW-016 MVP integration and hardening` 提交；
3. 创建 `zw-016-complete` 标签；
4. 将 `PLANS.md` 中 ZW-016 标记为已完成或外部验证待完成；
5. 将 `CURRENT_TASK.md` 状态改为“ZW-016 已完成，等待用户最终手工验收”；
6. 生成最终开发报告和手工验收清单；
7. 停止执行。

不得：

- 创建 ZW-017 任务文件；
- 创建 ZW-017 分支、提交或标签；
- 实现安装器、自动更新、代码签名或公开发布；
- 自动进入任何新的开发阶段。

---

## 11. ZW-016 最终交付

完成 ZW-005 至 ZW-016 后生成：

```text
docs/reports/CODEX_AUTONOMOUS_COMPLETION_REPORT.md
```

内容包括：

- 完成阶段；
- 每阶段 commit 和标签；
- 自动测试与构建结果；
- 未完成项和外部验证项；
- 真实设备验收清单；
- 已知限制和回滚点；
- 用户最终手工验收步骤。

最终输出：

- 当前分支；
- HEAD commit；
- 阶段提交列表；
- 标签列表；
- `git status`；
- 未跟踪文件；
- MVP 桌面构建产物位置。

---

## 12. Codex 启动指令

将本文件放到仓库根目录，然后向 Codex 发送：

```text
读取并执行仓库根目录的 CODEX_AUTONOMOUS_WORKFLOW.md。

本项目从现在开始切换为 Codex 单工具连续自主开发模式。

你的目标是从当前仓库真实状态出发，依次完成 ZW-005 至 ZW-016。

执行要求：

1. 先读取现有规则、任务、Git 状态和最近提交；
2. 以最小改动将 AGENTS.md、WORKFLOW.md、CURRENT_TASK.md、HANDOFF.md 和 PLANS.md 调整为 Codex 单工具连续执行模式；
3. 创建独立总任务分支 codex/zw-005-016-autonomous；
4. 完成规则迁移提交；
5. 立即开始 ZW-005；
6. 每个阶段完成实现、自动测试、文档、提交和标签后，自动进入下一阶段；
7. 不等待普通产品和实现确认，使用文档中的默认规则自主决策；
8. 每完成一个里程碑更新 HANDOFF；
9. 遇到额度中断时使用 checkpoint 提交，下一次从 HANDOFF 的唯一下一步继续；
10. 不重新盘点已经完成的阶段；
11. 不调用真实付费 LLM 做自动测试；
12. 不自动执行真实设备擦除、固件烧录和系统凭据变更；
13. 遇到外部权限或设备阻塞时，完成软件、Mock、脚本、UI、测试和文档，并继续其他阶段；
14. 不合并到 main，不强制推送，不重写历史；
15. 完成 ZW-016 后生成最终开发报告、最终手工验收清单和可运行 MVP 构建信息。

现在开始执行。

除非发生无法安全继续的仓库损坏或不可逆数据风险，否则不要停下来询问普通问题。
```

---

## 13. 现实边界

本规则可让 Codex 连续完成所有可自动完成的开发工作，但以下结果仍依赖外部条件：

- 真实硬件串口测试；
- 真实固件烧录；
- 真实 API 服务凭据；
- 用户最终产品体验验收。

Codex 必须完成这些能力的软件实现、Mock、Dry Run、测试、脚本和操作文档，但不得伪造真实外部验证已经成功。

最终目标是：

> Codex 连续完成 ZW-005 至 ZW-016 的所有可自动完成开发工作，形成可审查、可构建、可运行、可继续手工与真实设备验证的 MVP 完成版本。
