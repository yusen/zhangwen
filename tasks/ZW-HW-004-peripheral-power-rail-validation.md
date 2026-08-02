# ZW-HW-004 — 外设电源轨与工作电压范围校验

状态：实现完成且自动验收通过；运行库 revision 故障已修复，待重启桌面真人抽检（2026-07-17）

## 1. 问题

项目同时选择“行空板 K10”和“DFRobot DFR0026 模拟环境光线传感器”时，Rule Engine 把 K10 自身的
5 V 供电基线与 DFR0026 推荐的 3.3 V 工作点直接比较，返回
`PROJECT_VALIDATION_FAILED`。这是错误的物理语义：主控自身输入电压、主控对外提供的离散电源轨、
外设允许工作电压范围和信号输入上限必须分别建模。

## 2. 目标

- Hardware Skill 可声明器件允许的 `voltageMin/voltageMax` 和主控/电源可提供的离散
  `supplyVoltages`，旧包不填时继续按原 `voltage` 单值处理。
- 电压规则从主控可用电源轨中选择落入外设允许范围、且最接近推荐工作点的一条；精确推荐轨 PASS，
  仅范围兼容但偏离推荐值时 WARNING，无可用轨时 FAIL。
- 逻辑/模拟信号电平继续独立校验。供电兼容不能豁免 ADC/GPIO 过压、驱动、总线或电流规则。
- K10 声明 `[3.3, 5.0]` 外设电源轨；DFR0026 声明 3.0–5.0 V 工作范围和 3.3 V 推荐点，因此组合应选择
  3.3 V 并通过，提示仍保留 5 V 供电时校核 ADC 的安全边界。

## 3. 非目标与安全边界

- 不为 K10/DFR0026 写 ID 特例，不从 Markdown 自然语言临时猜电压，不把支持主控列表当作供电证明。
- 不把连续电压区间误写为主控能提供任意电压；`supplyVoltages` 是离散电源轨。
- 不因电压通过而忽略逻辑电平、电流余量、ADC 能力、共地和过压保护。
- 不修改串口、设备、上传、Flash 或固件流程。

## 4. 计划与验收

1. 扩展 Python/TypeScript 电气契约和 Hardware Skill 编写模板。
2. 统一声明式与旧兼容 Rule Engine 的电源轨选择算法。
3. 更新 bundled/data K10 与活动 DFR0026 Skill，并重算内容 revision。
4. 自动测试覆盖 K10+DFR0026 PASS、仅 5 V 轨 WARNING、无兼容轨 FAIL、信号过压仍 FAIL，以及项目硬件
   intake 不再返回 `PROJECT_VALIDATION_FAILED`。
5. 更新 PRD、架构、API、作者指南、Decision Log、PLANS 与 HANDOFF。

## 5. 已完成

- Python/TypeScript 电气契约已区分推荐点、连续工作范围和离散外设电源轨；旧 Skill 保持单点兼容。
- 声明式规则和旧兼容校验共享电源轨选择算法，且信号电平仍独立执行。
- K10 bundled/活动 Skill 与 DFR0026 活动 Skill 已更新并通过整包 revision 校验。
- 项目 suggest/create 的受控硬件摘要已携带新字段；K10 + DFR0026 API 回归不再返回
  `PROJECT_VALIDATION_FAILED`。
- 知识库详情和项目硬件选择器已显示工作范围/推荐点和外设电源轨，未改变中央对话或右侧三 Tab。
- 模板、AI 作者指南和当前产品/技术契约已同步。

## 6. 验证

- 后端：78 passed（Rule Engine、Hardware Skill、统一库、项目硬件 intake、CRUD/媒体/兼容 API）。
- 前端：新电气展示 5 passed；AppShell/RightPanel/Hardware Skill/缺件卡不变量 52 passed。
- Contracts build、Desktop strict typecheck、Desktop production build 通过。
- 真实数据：K10 revision `7b0fc4f2cfc036309c42b80c`，DFR0026 revision
  `4ef8c3dfd6588774f95091a5`，组合总体 PASS，供电选择 K10 3.3V，逻辑电平独立 PASS。
- 故障回归：Hardware Skill 定向组合 `54 passed`；当时活动目录 67 个包全部可加载，`invalid=[]`。
- K10 官方 MicroPython 案例跟进：活动/内置 `examples/usage.md` 现包含 22 个主题、24 个独立 Python
  代码块；联合 Hardware Skill/Board Skill 回归 `22 passed, 1 warning`，未执行真实硬件。
- SEN0388 跟进：用户确认原器件身份应从 SEN0307 改为 SEN0388，活动目录、skillName、componentId、
  电气协议、集成说明、示例和机械档案已统一迁移。黄金代码为
  `unihiker_k10.ultrasonic(trig=1, echo=1).distance()`，不再生成模拟量 ADC 方案；当前 revision
  `38f34165ae94d419ea04f2a9`；用户提供的 PNG 已登记为硬件库 `cover`，应用 SQLite 投影已同步。相关回归
  `18 passed, 1 warning`，未执行实机验证。
- 掌控板 3.0 可见性跟进：`labplus-mpython-esp32s3-v3` 因 API 文档中的 `password=None` 被旧凭据扫描器
  误判并由列表隔离。扫描器已区分明确占位值与具体凭据，真实密码/Token 仍失败关闭；活动包改为不包含
  凭据赋值的兼容写法，revision 更新为 `63f03e04d05366c47edcf770`，ACTIVE 列表、媒体、组件和机械投影均恢复。
- Hardware Skill AI 编写规范已升级到 v2，模板同步要求凭据参数只说明运行时注入，并以实际仓储加载和
  ACTIVE 列表命中作为上线条件，不能再把“目录已复制”当作成功。

## 7. Decision Log

- 2026-07-17：保留 `voltage` 作为推荐/标称工作点，新增可选范围和离散外设电源轨；不改变旧包默认语义。
- 2026-07-17：电源轨选择与信号电平校验分离；“能供电”不等于“信号可直连”。
- 2026-07-17：列表读取改为逐包失败隔离；单个 K10 或其他包校验失败不能阻断其余有效 Hardware Skill，
  但该失败包直接读取仍失败关闭，禁止自动信任或伪造 revision。
- 2026-07-17：K10 代码示例以官方 MicroPython API 页面为来源，使用“官方 API 核对 + 本地语法通过”
  验证等级；不把未上板代码标成实机验证，不复制页面示例凭据，不用初始化不完整的 MQTT 片段生成成品代码。
- 2026-07-17：用户确认实物型号为 SEN0388，且 DFRobot/行空板官方文档共同支持单线 `ultrasonic` API；因此
  将原 SEN0307 包整体迁移为 SEN0388 DIGITAL 身份，而不是继续保留冲突的模拟量默认方案。
- 2026-07-18：敏感信息扫描继续失败关闭具体凭据，但允许明确的无值占位符；同时要求 Hardware Skill 文档
  不写凭据赋值，以兼容旧 Sidecar。应用可见性必须由实际 `get_skill()` 与 ACTIVE 列表验证，而非目录存在性推断。

## 8. 运行中故障复核（2026-07-17）

- 用户报告 `HARDWARE_SKILL_INVALID: Hardware Skill 内容 revision 与 manifest 不一致`。真实活动 K10 内容
  指纹已变为 `52ba1b6befb3f23c26a54859`，manifest 仍保存旧值；已按完整内容重算并更新。
- 全库审计同时发现 `dfrobot-dfr0033-k10` 的图片替代文本超过 160 字符；旧同步数据后来再次写回超长文本，
  已再次缩短并按当前内容把 revision 更新为 `5ea6a4c5628950816b830dd8`。
- `list_skills()` 的 K10 预升级路径原来位于逐包异常隔离之外，导致 K10 损坏时整个列表直接失败；现已把
  该路径纳入同一失败关闭边界。回归测试锁定“有效包仍列出、损坏 K10 被排除、直接读取损坏 K10 仍报错”。
- 修复后对 `services/local-api/.data/hardware-skills` 执行真实仓储扫描：最终复扫时 67 个包全部加载成功，
  无无效目录。
- 后续按官方 K10 MicroPython 页面扩充 `examples/usage.md` 后，活动 K10 revision 更新为
  `7b0fc4f2cfc036309c42b80c`，内置 K10 revision 更新为 `657072f16399f8b4fdd425a6`；旧
  `52ba1b6befb3f23c26a54859` 只保留为前一故障修复节点，不再是当前真值。
- SEN0388 当前 revision 为 `38f34165ae94d419ea04f2a9`；包级解析、封面 PNG 哈希/媒体读取、
  示例/CadQuery 语法、机械 SHA、应用组件投影及 Hardware Skill 回归均通过。官方外形为 47×22mm，
  详细机械参考值仍待 SEN0388 实物复核。
- 掌控板 3.0 当前 revision 为 `63f03e04d05366c47edcf770`；联合回归 `45 passed, 1 warning`，65 个活动目录
  全部严格加载且 `invalid=[]`。应用组件为 ACTIVE，三张媒体和机械档案链接均使用同一 revision。

## 9. 剩余真人抽检

- 关闭并重新启动掌问，使非热更新 Sidecar/桌面加载新契约。
- 确认硬件详情显示 DFR0026 `3–5V（推荐 3.3V）` 和 K10 外设 `3.3V / 5V`。
- 新建项目选择 K10 + DFR0026，确认不再出现供电基线不匹配；不得把此结论解释为 5V 模拟输出可直连
  3.3V ADC。
- 刷新硬件库并确认只显示 SEN0388 新组件；用 K10 P1 的 3.3V/GND/Signal 接入实物，在 30/50/100cm
  验证 `ultrasonic(trig=1, echo=1).distance()`，并复核机械孔位后再用于最终结构件加工。
- 刷新硬件库确认“掌控板 3.0（ESP32-S3）”及三张媒体出现；若旧 Sidecar 仍缓存列表则重启掌问。
