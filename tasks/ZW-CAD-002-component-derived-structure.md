# ZW-CAD-002 — 基于电子器件的结构创建

状态：已完成（2026-07-16）

## 1. 目标

结构工程师不再把所有建模请求归一为盒体。用户可以选择一个已确认的电子器件机械档案，生成与该器件尺寸、固定孔和避让信息绑定的确定性安装结构；明确外壳请求继续使用 `BOX_WITH_LID`，目标不明确时先确认建模目标。

首个新增生产模板为 `COMPONENT_MOUNT -> component-mount.v1`，输出安装底座、可拆压框、器件参考几何、STEP/STL/GLB、参数和校验报告。

## 2. 已确认问题

- 当前 CAD intake 的首问是“盒内物品”，并强制收集盒体内腔长宽高。
- `canonicalize_output()` 无论用户建模目标为何，最终都生成 `BOX_WITH_LID`。
- Runtime 提示词、能力上下文、边界校验和 Worker allowlist 都只接受 `BOX_WITH_LID`。
- 项目已有 `SENSOR_BRACKET/MCU_MOUNT/...` 历史枚举，但生产 Worker 没有对应真实几何实现，不能直接声称支持。

## 3. 范围与安全边界

- 新增一个适用于任意已确认电子器件机械档案的通用 `COMPONENT_MOUNT` 模板。
- 只消费 Sidecar 固化的 `hardwareId/profileId/revision/contentSha256` 和结构化机械快照。
- 不执行 Hardware Skill 的 `models/cadquery.py`、Provider 代码、用户代码、路径、命令或 URL。
- `REFERENCE_ONLY` 模型仍只作为审计资料；通用器件预览由受控机械包络、孔位和已注册模型种类生成。
- 不实现自由曲面、通用 CAD、切片、任意插件或任意 Python 执行。
- 不修改 `CURRENT_TASK.md`，不覆盖并行任务，不创建 ZW-017。

## 4. 实施计划

### M1：意图与 intake

- 区分盒体、器件安装结构和目标不明确三种入口。
- 目标不明确时返回结构化目标选择；器件安装结构只要求选择一个已确认机械档案，不要求盒体尺寸。
- 将目标和机械档案选择持久化为项目事实，修订时封存旧 intake。

### M2：契约与本地边界

- 增加 `COMPONENT_MOUNT`、固定 revision 和受限参数目录。
- Runtime、上下文能力和 Agent 说明允许两个生产模板，并继续拒绝未确认器件、代码和 Provider 自有 revision。
- Job 只对盒体执行 enclosure 自动尺寸；器件安装结构必须恰好固化一个机械档案。

### M3：确定性几何

- 基于器件包络生成圆角底座和可拆压框；底座按机械档案固定孔生成通孔。
- 预览包含器件受控参考几何；通用档案使用包络和孔位，已注册 model kind 使用内置受信几何。
- 继续输出固定 11 文件并复用现有 STEP/STL/GLB、BRep、回读、流形和 manifest 校验。

### M4：测试与文档

- 先补目标路由、intake、Runtime、Job/Worker 和真实 CadQuery golden 回归。
- 运行 CAD、三师、聊天、contracts/desktop 类型检查和 Python 编译。
- 更新 PRD、架构、API、baseline、decision、PLANS 和 HANDOFF。

## 5. 验收标准

- “给这个传感器做安装座”不再进入盒体尺寸问题，且必须选择精确机械档案。
- “做一个装传感器的外壳”仍进入 `BOX_WITH_LID`。
- “创建一个三维结构”先询问是外壳还是器件安装结构，不静默生成盒子。
- `COMPONENT_MOUNT` Job 固化一个机械档案，生成底座/压框与器件参考预览；未知或多器件输入失败关闭。
- 现有盒体全部回归继续通过，Hardware Skill Python 不获得执行权限。

## 6. Decision Log

- 2026-07-16：新增通用 `COMPONENT_MOUNT`，不启用没有生产几何实现的历史支架枚举。
- 2026-07-16：器件机械档案是结构尺寸权威；自然语言名称不直接转换为硬件 ID。
- 2026-07-16：为保持 Artifact、预览和存储契约稳定，组件安装结构继续输出固定 11 文件；`base` 表示安装底座，`lid` 表示可拆压框。

## 7. Progress

- 2026-07-16：完成现状审计，确认 intake、Runtime、能力上下文、Job sizing、Worker 和 Engine 均为盒体专用；M1 开始。
- 2026-07-16：完成目标分流和项目事实持久化。安装座/固定底座/托架/支架/压框进入 `COMPONENT_MOUNT`，外壳/保护壳/盒体进入 `BOX_WITH_LID`，模糊三维结构请求返回目标澄清卡。
- 2026-07-16：完成 `COMPONENT_MOUNT -> component-mount.v1` 参数目录、Runtime/Job/Worker 边界和确定性几何。Job 恰好固化一个机械档案，不执行 enclosure sizing；Worker 生成圆角底座、可拆压框、档案固定孔和器件参考预览。
- 2026-07-16：保持固定 11 文件 Artifact 契约；`base`/`lid` 在组件路径分别表示安装底座/可拆压框。Hardware Skill `models/cadquery.py` 继续 `REFERENCE_ONLY`。
- 2026-07-16：结构工程师 Skill、CAD 声明规则、PRD、架构、API、baseline 和 decision 已同步两个生产模板。

## 8. Verification

- `python -m compileall -q`：CAD Agent、CAD Engine、Experts、Chat 相关模块通过。
- CAD 全量测试：`178 passed`，含 intake、Runtime、Job、Worker、真实 CadQuery STEP/STL/GLB golden 和旧盒体回归。
- 结构工程师/Agent Skill/聊天回归：`26 passed`，仅有既存 Starlette/httpx 弃用警告。
- `pnpm typecheck`：contracts build、contracts typecheck、desktop typecheck 全部通过。
- 环境未安装 Ruff，未伪报格式检查通过；未调用真实 Provider、串口、Flash、固件或任意 Hardware Skill Python。
