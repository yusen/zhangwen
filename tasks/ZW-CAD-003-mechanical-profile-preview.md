# ZW-CAD-003 — 机械档案三维预览

状态：已完成（2026-07-16）

## 1. 目标

在专业模式“设置 → 公共知识 → 机械档案”中，为每个机械档案提供“查看 3D 预览”按钮。预览使用
Hardware Skill 当前 revision 编译出的机器可读机械快照，不依赖项目 CAD Artifact，也不执行
`models/cadquery.py`。Hardware Skill 更新完成并刷新投影后，新 revision 应立即可预览。

## 2. 产品边界

- 用户创建传感器结构件继续通过结构工程师中央对话进入 `COMPONENT_MOUNT`；不使用器件的零件进入
  `FREEFORM_STRUCTURE`，不在设置页建立第二套建模流程。
- 3D 预览使用既有浮窗层，不新增右侧一级 Tab，不替换或卸载中央主对话。
- 自然语言 `mechanical.md` 正文不能直接成为可信几何。AI/人工必须把正文中已确认的可见实体编译到
  `preview_geometry`；预览只读取通过 Schema、哈希和版本校验的机器 JSON。
- 细分预览表达受控 PCB、连接器、传感体以及安装孔、接口开口与禁布区；没有声明式实体时才退回包络，
  并明确标注“仅包络预览”。它是机械档案示意，不冒充制造级 STEP/STL。
- 精确外观仍需要受信 STEP/STL/GLB，或新增受控内置 `model_kind`；参考 CadQuery Python 保持
  `REFERENCE_ONLY`。

## 3. 实施计划

1. 扩展机械档案列表契约，返回坐标系、model kind、安装孔、开口和禁布区。
2. 增加机械档案预览浮窗类型和受控 Three.js 示意查看器。
3. 从机械档案卡片打开浮窗；打开时关闭设置层，保持单一 CenterChat、草稿和三个右侧一级 Tab。
4. 增加 API、组件、AppShell/UI 契约回归，并更新 Hardware Skill 编写说明和交接记录。

## 4. 验收标准

- 每个机械档案显示“查看 3D 预览”。
- 点击后浮窗显示当前 profileId/revision、外形包络、安装孔、开口和禁布区图例。
- Hardware Skill 保存事件刷新列表后，预览按钮使用新 revision 数据，无需执行 CadQuery 或等待项目建模。
- 设置层关闭，CenterChat 实例和未发送草稿保持，右侧一级 Tab 仍只有“工作 / 产物 / 设备”。
- API 缺失或结构化机械数据非法时失败关闭，不从自然语言猜尺寸。

## 5. Decision Log

- 2026-07-16：预览采用机器可读快照的客户端受控示意几何，不在 Hardware Skill 保存时执行任意 Python。
- 2026-07-16：预览使用独立机械档案浮窗，不伪造项目 ArtifactVersion，也不修改中央建模确认流。

## 6. 完成记录

- 机械档案 API 和 TypeScript 契约已增加 `coordinateSystem/modelKind/mountingHoles/openings/keepouts`。
- 机械档案卡片已增加“查看 3D 预览”，通过既有浮窗显示包络、安装孔、开口和禁布区，并提供
  适配模型/重置视图；WebGL 不可用时显示受控降级提示。
- 打开预览会关闭设置覆盖层，但不重挂载中央对话；专业模式关闭时同步关闭该技术浮窗。
- AI 编写规范和可复制模板已写明资料要求、即时预览来源和四级精度边界。

验证（2026-07-16）：

- `.venv\\Scripts\\python.exe -m pytest services/local-api/tests/test_cad_mechanical_profile_api.py -q --rootdir services/local-api`：`2 passed`。
- `.venv\\Scripts\\python.exe -m pytest services/local-api/tests/test_unified_hardware_skill.py services/local-api/tests/test_hardware_skills.py services/local-api/tests/test_cad_mechanical_profiles.py -q --rootdir services/local-api`：`23 passed`。
- `pnpm --filter @zhangwen/desktop test -- MechanicalProfileLibrary.test.tsx ProjectWorkspace.test.tsx`：`30 passed`。
- `pnpm --filter @zhangwen/contracts typecheck`、`pnpm --filter @zhangwen/desktop typecheck`：通过。
- 范围内 `git diff --check`：通过；只有工作树换行风格提示。

未运行真实桌面 WebGL/三视口人工验收；不能把自动测试描述为真人视觉验收。制造级外观仍需受信
STEP/STL/GLB 或平台审核的专用 `model_kind`，普通 Hardware Skill 当前只生成受控示意。
