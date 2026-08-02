# ZW-HW-003 — 电气、结构与参考模型统一 Hardware Skill

状态：实现完成且自动验收通过（2026-07-16；真人桌面抽检待用户）

## 1. 目标

把器件电气参数、兼容规则、结构自然描述、机器可读机械档案、已验证 CadQuery 参考模型、
图片、接线、安全和验证用例收敛到同一个 Hardware Skill 包。用户保存一个 Skill 后：

1. 硬件目录和硬件组合校验读取新的电气投影；
2. 三师公共知识读取同一 revision 的工程内容；
3. 结构工程师和 CAD intake 读取从同一 Skill 派生的不可变机械档案版本；
4. Hardware Skill 项目编辑器展示并编辑同一包内的 Markdown 与 Python 参考模型；
5. 不再以 `seeds.py`、机械档案硬编码和 Hardware Skill 三份手工副本表达 K10 事实。

行空板 K10 是首个统一样例。结构自然描述和参考模型来自用户提供的
`行空板K10.txt`；电气、固件和接口事实以现有已核验 K10 资料为基线。

## 2. 非目标与安全边界

- 本任务不执行真实设备扫描、连接、上传、重启、Flash 擦除或固件烧录。
- `models/cadquery.py` 是可审计、可版本化的参考源码，不因普通 Skill 保存而直接执行。
- CAD Worker 只消费经过 Pydantic 和哈希校验的机械档案快照；受信 K10 几何仍受注册模型
  身份和固定尺寸门禁约束。
- Board Skill 继续承载 MicroPython API、模板和部署能力；器件事实由 Hardware Skill 提供，
  Board Skill 不再作为 K10 尺寸或电气参数的第二真源。
- 不改动 `CURRENT_TASK.md`，不覆盖并行的 ZW-AGENT-006、ZW-UX-003 或安装包工作。

## 3. 统一目录契约

```text
<skill-name>/
├── manifest.json                         # 系统只读身份、文件白名单、媒体与 revision
├── SKILL.md                              # 器件入口与渐进加载索引
├── assets/                               # 可选真实图片
├── references/
│   ├── specifications.md                 # 电气/目录机器可读块
│   ├── compatibility-rules.md            # 确定性兼容规则
│   ├── mechanical.md                     # 自然描述 + 机械档案机器可读块
│   ├── integration.md                     # 接线、固件、初始化和集成
│   ├── safety.md                          # 安全边界
│   └── sources.md                         # 事实、图片和模型来源
├── models/
│   └── cadquery.py                        # 已验证参考模型，不作为任意执行入口
├── examples/
│   └── usage.md
└── tests/
    └── validation-cases.md
```

旧八文件 Hardware Skill 必须继续可读；只有声明机械能力的包才需要
`references/mechanical.md + models/cadquery.py`。新 revision 覆盖所有声明文件和媒体元数据。

## 4. 机器可读机械块

`references/mechanical.md` 中必须且只能包含一个
`zhangwen:hardware-mechanical:v1` JSON fence。JSON 声明现有 `HardwareProfile` 所需的
profile、坐标系、包络、安装、开孔和 keepout，以及参考模型路径、SHA-256、验证状态和
`REFERENCE_ONLY` 执行策略。服务端从 Hardware Skill revision 派生机械档案 revision，
不接受调用方伪造版本。

## 5. 实施里程碑

- [x] M1：共享契约和后端文件白名单支持机械描述/参考模型，保留旧包兼容。
- [x] M2：校验机械 JSON、模型路径/SHA/Python 语法，并在同一保存事务中同步硬件与机械投影。
- [x] M3：K10 内置统一包成为默认电气和结构事实来源；旧 K10 包安全一次性升级。
- [x] M4：提供完整可复制模板，桌面编辑器正确显示 Python 模型文件。
- [x] M5：后端、契约、桌面定向测试与文档交接完成。

## 6. Decision Log

- 2026-07-16：采用“结构化机械档案可执行、CadQuery 源码仅参考”的双层边界。原因是普通
  Hardware Skill 编辑不能隐式扩大为任意 Python 执行权限。
- 2026-07-16：保持旧八文件包兼容，统一结构文件作为受控可选能力；避免升级后把现有用户
  Hardware Skill 判为损坏或复制成第二个组件。
- 2026-07-16：机械档案 revision 由 Hardware Skill revision 派生；Skill 是事实源，SQLite
  `mechanical_profile_versions` 和 `hardware_components` 都只是可重建投影。

## 7. Progress

- 2026-07-16：完成只读审计。确认当前 K10 电气 seed、Hardware Skill、Board Skill、CAD
  trusted profile 和 CadQuery 硬编码分别存在；用户文件中的结构尺寸与现有 K10 CAD 几何
  一致，但当前 Hardware Skill 尚不能承载或投影结构与模型源码。
- 2026-07-16：完成统一目录契约、机械 JSON/Python/SHA 校验、原子电气与机械投影、旧八文件
  K10 原位升级、内置 K10 样例和可复制模板。普通保存只解析结构化机械快照，不执行用户 Python。
- 2026-07-16：桌面 Hardware Skill 项目可查看和编辑 `models/cadquery.py`，机械档案库监听
  Hardware Skill revision 更新并重新加载对应投影。Board Skill 只保留 MicroPython API 与模板职责。
- 2026-07-16：跟进导入用户新增 `dfr0026-ambient-light-sensor`。原包声明了 manifest、自定义
  checksum 和多级 Python 示例等未允许路径，并使用扩展电气/机械/验证 schema，扫描时被安全隔离。
  已在数据目录保留完整导入前备份，将可用事实转换为当前 12 文件契约，并通过应用写入入口同步为
  `hw_dfrobot_dfr0026`，revision=`12e0ff9826bd65f862516772`；电气组件、封面和机械档案关联均可读。
- 2026-07-16：新增 `docs/HARDWARE_SKILL_AI_AUTHORING_GUIDE.md` 作为任意 AI 的 v1 权威编写规范，
  自包含复制提示词、最终文件白名单、四类精确 JSON Schema、全部规则算子参数、机械枚举、
  模型/图片/revision 算法、AI 交付报告和失败对照表。可复制模板默认 `media=[]`，避免缺图即无效；
  README 明确禁止额外 checksum、Python 示例、扩展字段和伪造验证状态。
- 2026-07-16：按用户提供的 `光线传感器 (1).txt` 扩写 DFR0026 `mechanical.md` 自然语言部分，
  明确坐标系、PCB 范围、接口对齐与 Z 高度、孔中心推导、感光器件位置、总包络和 +X 线缆避让；
  机器机械档案与模型尺寸原本一致，未修改模型或 SHA。当前 Skill revision 更新为
  `28ef2fa032fb066a10e73c12`，机械投影精确关联 `skill-28ef2fa032fb066a10e73c12`。

## 8. 验证计划

- 新建/迁移旧 Hardware Skill，不丢失旧八文件内容。
- K10 首次迁移得到统一文件、真实电气规格、结构描述和模型 SHA。
- 保存规格后硬件目录与组合校验读取新 revision。
- 保存机械块后创建新的不可变机械档案并把 K10 精确关联到该 revision。
- 模型 SHA、路径、Python 语法、机械 schema 或受信尺寸不一致时整次保存回滚。
- 三师上下文包含同一 Skill 的电气、结构和参考模型内容。
- 桌面编辑器把 `models/cadquery.py` 作为 Python 文件展示并保存。

## 9. 验证结果

- Hardware Skill、目录媒体、上下文、项目硬件、机械档案/API 与三师定向后端回归：
  `73 passed, 1 existing Starlette warning`。
- 统一 K10 新装、旧包原位迁移、原子保存和 SHA 回滚：`4 passed`；机械档案 API 定向合计
  `6 passed`。
- 桌面 Hardware Skill、机械档案、目录媒体和公共知识定向回归：`4 files / 12 tests passed`；
  contracts build 与 desktop typecheck 通过。
- CAD Worker 机械回归：`14 passed`。完整性脚本确认 K10 的 12 个声明文件、模板的 11 个声明
  文件、两个模型 SHA、Python AST 和 K10 manifest revision 一致；`git diff --check` 通过。
- 当前并行工作树的 `test_structure_engineer_cad_end_to_end.py` 仍有 2 项失败：已有的 Hardware
  grounding 规则把不含器件的纯空盒 `cadDraft` 也要求引用本地 K10，导致 Provider 重试和消息失败。
  该失败不在本任务改动范围；本任务未放宽或回退并行的三师校验。
- AI 编写规范与模板定向回归：`8 passed, 1 existing Starlette warning`；文档代码围栏、模板
  文本安全边界和模型 SHA 通过。规范中的独立 revision 算法复算 K10=`ab7720b5a07b7775b0e3ca76`
  与 DFR0026=`12e0ff9826bd65f862516772`，均与应用结果一致。

## 10. 真人抽检

重启当前桌面/Sidecar，在“设置 → 公共知识库 → Hardware Skill”打开 K10：确认电气、结构和
`models/cadquery.py` 同包可见；修改一项结构描述并保存后，打开机械档案库确认 revision 自动更新。
抽检不需要连接真实硬件或执行参考模型。
