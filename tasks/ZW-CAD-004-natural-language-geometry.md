# ZW-CAD-004 — 自然语言声明式几何

状态：已完成（2026-07-16）

后续里程碑：M2 行空板 K10 电子相册固定结构模板（已完成，2026-07-20）

后续说明：机械档案预览缓存的生成与失效规则已由 `ZW-CAD-005` 接管；本任务中“作者把实体写入机器 JSON”的做法不再是当前编写要求。

## 1. 目标

修复机械档案 3D 预览只显示包络、不能表达 `mechanical.md` 自然描述中 PCB、连接器和传感体的问题；
同时支持用户不选择任何电子器件，直接在中央结构工程师对话中用自然语言描述一个受控三维零件。

## 2. 安全与产品边界

- 自然语言先由 AI 转成声明式几何，不直接执行 AI/Hardware Skill 生成的 Python、Shell、路径或 URL。
- 声明式几何第一版只允许有界的 `box/rounded_box/cylinder` 和 `add/cut`，限制实体数、尺寸、圆角、
  旋转和整体包围盒；本地 Schema、布尔结果、B-Rep、STEP/STL 和网格校验失败时关闭。
- 机械档案把自然描述确认后的可视实体写入机器 JSON；前端读取该快照，不在浏览器内调用云端模型。
- 无器件结构使用新 `FREEFORM_STRUCTURE` 目标和 `freeform-structure.v1`，`components=[]`，不要求机械档案。
- 中央对话、确认卡、工作进度、产物浮窗及右侧“工作 / 产物 / 设备”保持现有职责。

## 3. 计划

1. 增加跨 Python/TypeScript 的声明式几何契约和机械档案快照字段。
2. 让 DFR0026 及模板声明 PCB、接线口和感光体，机械档案浮窗按实体而非总包络绘制。
3. 增加无器件自由结构目标、结构工程师输出规则、Job 固化和受限 CAD Worker 构建。
4. 保持盒体与器件安装结构现有文件契约；自由结构使用动态单零件 STEP/STL 与同一 GLB/校验链路。
5. 增加 API、intake、模型边界、真实 CadQuery golden 和 UI 契约回归，更新文档与交接。

## 4. 验收标准

- DFR0026 预览至少分别显示圆角 PCB、接线口、感光圆柱、两个孔和线缆禁布区，不再只是 30×22×6.7 方盒。
- 缺少声明式实体的旧档案明确标注“仅包络预览”，不能声称已按自然描述生成。
- “不使用任何传感器，做一块 80×30×4 mm、带两个直径 3 mm 通孔的圆角安装板”进入
  `FREEFORM_STRUCTURE`，不要求器件档案或盒体内腔。
- 云端只能输出声明式实体；未知字段、超限尺寸、先 cut、无实体或无效布尔结果均被本地拒绝。
- 真实 Worker 为有效自由结构输出 STEP/STL/GLB 和校验报告；现有 BOX/COMPONENT_MOUNT golden 不回归。
- 打开预览或自由结构产物期间保持单一中央对话、草稿和固定三个右侧一级 Tab。

## 5. Decision Log

- 2026-07-16：不执行 `mechanical.md` 的参考 CadQuery；自然语言的可执行结果必须固化成受限声明式几何。
- 2026-07-16：自由结构是受控 CSG 零件，不宣称覆盖自由曲面、扫描网格、拓扑优化或任意 CAD Python。

## 6. 完成记录

- 机械档案契约新增 `preview_geometry`；DFR0026 已固化圆角 PCB、接线口和感光圆柱，活动 SQLite
  投影同步到 `skill-66e12c61a341dc3cd0c37a3a`。安装孔、开口和线缆禁布区继续使用原机械字段。
- 机械档案浮窗优先绘制描述实体；旧档案无该字段时明确显示“仅包络预览”。预览不执行参考 Python。
- 新增 `FREEFORM_STRUCTURE -> freeform-structure.v1`，中央结构工程师可在不选择器件的情况下把自然语言
  转为最多 32 个受控基本体的声明式 CSG；Job、Worker、B-Rep、STEP/STL/GLB 和 Artifact 链路已打通。
- 自由结构输出 `part.step/part.stl` 及公共预览/报告，共 9 个不可变文件；原盒体和器件模板继续 11 个。

## 7. 验证

- 全部 CAD/结构 Runtime 回归：`187 passed`。
- Hardware Skill、机械档案 API、结构工程师包与 Runtime：`50 passed`；机械档案 API 单独复验：`2 passed`。
- Desktop 机械档案、右侧栏和项目隔离：`50 passed`。
- Contracts build、Desktop typecheck、Desktop production build：通过。
- Python compileall、JSON 解析、范围内 `git diff --check`：通过；仅有既存 Starlette/httpx 弃用警告和
  Vite chunk-size 提示。

## 8. 未执行与下一步

- 未调用真实付费 Provider，未执行 Hardware Skill 参考 Python，未做设备、串口、Flash 或固件操作。
- 需在重启 Sidecar/桌面应用后做一次真人 WebGL 验收：打开 DFR0026 机械档案确认三实体、两孔和 keepout，
  再在中央结构工程师输入“做一块 80×30×4 mm、四角 R4、带两个直径 3 mm 通孔的安装板”。

## 9. M2 — 行空板 K10 电子相册固定结构模板

### 目标

把 `references/local/复杂结构件建模的人机交互资料` 中已确认的 16 个阶段和最终尺寸，固化为结构工程师可选择、
本地 CAD Worker 可确定性生成的 `UNIHIKER_K10_PHOTO_ALBUM` 模板。用户明确提出“行空板 K10
电子相册/相册支架”时直接使用该模板，不再让 Provider 用 `FREEFORM_STRUCTURE` 的简单图元近似斜面。

### 范围与安全边界

- 模板首版固定采用资料中最终确认的尺寸；不执行资料目录中的代码、命令或路径。
- Provider 只能选择模板并给出摘要，不能覆盖模板 revision、固定尺寸、局部坐标或建模函数。
- 本地建模器按阶段使用固定加/减法实体，并输出单一可打印件的 STEP/STL/GLB、参数快照和校验报告。
- 资料中的回退记录只作为审计依据；无效或已撤销的方法不进入生产模板。
- 不连接真实设备，不执行串口、上传、Flash、固件烧录或公开发布。

### 验收标准

- “生成行空板 K10 电子相册结构”被识别为固定模板，不进入盒体尺寸、机械档案或自由结构描述澄清。
- 能力上下文和结构工程师参考明确列出模板、固定 revision、局部 `s/n/y` 坐标及 16 阶段顺序。
- Worker 拒绝额外参数、器件档案、声明式 geometry、未知约束和错误 revision。
- 真实 CadQuery 回归生成一个连通、有效的可打印实体，包含斜面、L 卡扣、限位块、方孔、后部块、顶部槽和半圆缺口。
- 既有 BOX、COMPONENT_MOUNT 与 FREEFORM_STRUCTURE 测试不回归。

### Decision Log

- 2026-07-20：该资料是已确认的产品结构模板，不作为任意自然语言编译示例；采用专用模板类型和本地固定几何。
- 2026-07-20：首版尺寸不可由 Provider 修改。后续若要参数化变体，必须先定义尺寸依赖和独立 revision。
- 2026-07-20：保留“先阶段规格、逐阶段验证、最后生成终版”的结构工程师交互规则；CAD Worker 执行时一次生成最终受限模型。

### 完成记录与验证

- 新增跨 Python/TypeScript 的 `UNIHIKER_K10_PHOTO_ALBUM` 与固定 revision；能力上下文、目标四选一、
  直接文本识别、CadDraft/Job/Worker 失败关闭和产物标签已接入。
- 新增结构工程师参考 `K10_PHOTO_ALBUM_TEMPLATE.md`，固化 `s/n/y` 坐标、16 个确认阶段、加/减法方向和核对规则。
- 本地 `k10_photo_album.py` 实现底板、60° 斜面、L 卡扣、双限位块、背盖、圆角方孔、后部斜块、顶部槽、
  半圆缺口和 R8.5/R3/R10/R1.5/R2 确定性边处理；不使用原生边序号 fillet。
- CAD/结构工程师全量：`200 passed`；Agent Package/Skill：`13 passed`；桌面 UI 契约：`17 passed`；
  contracts build、contracts/desktop strict typecheck、Python compileall、manifest JSON 和 `git diff --check` 通过。
- 未调用真实 Provider、设备、串口、上传、Flash、固件烧录、安装器构建、签名或公开发布；桌面真人 3D 预览抽检待用户重启后执行。
