---
name: workflow-orchestration
description: ZW-CAD-intent 总流程编排说明。用于告诉 LLM 和内部 agent 当前任务应按哪个阶段推进、何时分支、何时阻断，以及哪些职责必须交给确定性工具。
---

# workflow_orchestration

## 独立结构件优先分支

新需求进入通用电子产品或盒体流程前，必须先判断是否命中 `standalone_structural_parts`：

- 用户只选择了 `hardware_system: "common"` 且 `model_type: "structural_part"` 的一个或多个通用件，并且没有要求盒子、盒体或外壳时，进入独立结构件流程。
- 用户没有预选硬件，但在自然语言中明确点名通用件中的结构件，并且没有要求盒体时，也进入该流程。
- 用户提到“盒子、盒体、外壳、壳体、保护壳、机箱”等外壳意图时，不得进入独立结构件流程；继续走普通盒体链路。
- 电子元器件与结构件混选时，不得把整个需求误判为纯结构件项目；按普通电子项目规则继续分析。

命中后使用 `route_action: "standalone_structural_parts"` 和 `design_mode: "structural_part_project"`，直接交给 `standalone_structural_parts` skill。该分支必须跳过主控补全、电子功能覆盖验证、安装朝向、盒体尺寸、盒体布局和外壳生成，只执行通用结构件母版校验、并排预览规划、项目副本建立、CadQuery 构建和逐件导出。

## 内置确定性产品分支

### 批量小模型模板案例分支

在新需求路由中，以下明确案例名称要在通用 LLM 意图分析前命中确定性模板：光效水杯、手持小风扇、掌控板外壳、行空板自动感应开盖智能盒子。它们的 `template_id` 分别为 `unihiker_light_effect_cup_v1`、`unihiker_handheld_fan_v1`、`mpython_board_enclosure_v1` 和 `unihiker_auto_open_lid_box_v1`。

该分支使用 `model_contract: "template_parts_v1"`：固定 BOM 和案例源码中的硬件摆放直接进入 artifact；源码中的可打印部件由 `template_parts[].printable` 声明，硬件参考件由 `template_reference_parts` 声明。整体场景只用于关系预览，必须是 `scene_only`/`printable: false`，不可混入 STL 可打印清单。水杯、风扇和自动开盖等纯泛词不应命中这些模板，只有带有案例限定词时才短路。

模板源码副本写入当前任务的 `exports/<task>/project`，模型编辑、重建和撤销只作用于项目副本；公共批量案例母版保持只读。缺少模板源码、部件入口或硬件 profile 时应明确阻断，不得回退普通盒体或包围盒代理。

未命中独立结构件流程时，在 `conversation_route` 识别出新需求后、进入通用 LLM 意图分析之前，必须执行 `deterministic_product_route`。

- 命中 `unihiker_plant_caregiver` 且模板已实现时，调用后台模板库 `unihiker_smart_watering_system_v1` 生成锁定 BOM/布局的普通盒体 `confirmation` 草案和 2D `layout_scene`；用户确认后才进入 `build_confirmed` 和 artifact/CadQuery 导出阶段。模板数据仍绕过通用 BOM 和布局推导。
- 命中 XIAO 或掌控板植物看护占位产品时，返回占位响应，不回落到通用流程。
- 未命中内置确定性产品时，才继续标准主链路。

## 用途

这是 `ZW-CAD-intent` 的总流程 skill。它不直接生成 CAD、不直接选硬件、不直接写坐标，而是说明整个 zwagent 应如何按阶段调用已有 skills。

LLM 在理解用户需求或验证 BOM 时必须知道：自己只负责需求理解、功能覆盖判断和对话解释；硬件库约束、布局、坐标、开孔、固定结构、CadQuery 代码和真实导出都由后端确定性工具完成。

## 标准盒体主链路

1. `conversation_route`：先判断用户本轮动作。
   - 已有 artifact 且输入涉及刻字时进入 `surface_engraving`，不回到通用需求分析。
   - 已有活动项目的其他模型修改进入 `model_edit`，读取项目源码、索引、记忆和修订历史。
2. `requirement_function_selection_analysis`：复杂需求先拆功能、推导硬件角色、匹配硬件库。
3. `intent_analyze`：把需求整理成结构化 intent。
4. `hardware_bom_select`：只从硬件库或 custom profile 中选 BOM。
5. `function_verify`：验证 BOM 是否覆盖需求功能，且硬件确实存在。
6. `profile_check`：检查硬件 profile 的尺寸、安装、开孔和避让字段。
7. `orientation_resolve`：确定安装面、交互面和旋转。
8. `box_feasibility_check`：计算盒体尺寸并检查安装面容量。
9. `layout_solve`：生成硬件、开孔、固定结构和固定孔布局。
10. `design_validate`：执行干涉、壁厚、开孔、固定结构和 CadQuery 静态校验。
11. `cadquery_generate`：生成确定性 CadQuery 代码和 CAD 参数。
12. `artifact_export`：写入任务目录、artifact、design-state、checks 和 workflow 产物。
13. `cadquery_build`：运行 CadQuery，导出真实 STL/STEP。

以上链路只适用于普通电子项目和盒体项目。独立结构件项目不得为了复用这条链路而伪造 controller、enclosure、mounting 或 box layout 数据。

## 分支规则

- 需求分析或确认前草案的修改可走 `design_revision`；真实模型生成后的普通修改走 `model_edit`，只修改当前项目副本。
- 已有模型的刻字请求走 `surface_engraving`，由该 skill 生成受限 CadQuery 刻字补丁并重新构建。
- `model_edit` 生成带源码哈希的精确补丁，先写暂存区并完成安全与 CadQuery 验证；低影响修改可自动提交，高影响修改必须等待确认。
- 用户可取消待确认修改或撤销最近一次项目修订；失败时保留或自动恢复原源码、artifact 和预览。
- 用户点击或输入阻断选项时，先走 `resolution_option_route`，再执行对应恢复路径。
- 用户只选择或明确点名通用结构件且没有盒体意图时，走 `standalone_structural_parts`；首次返回参数确认，确认后生成独立结构件 artifact。
- 用户已选硬件并要求“给选定硬件做盒子”时，走 `selected_hardware_enclosure`，不强行从自然语言推导复杂功能。
- 用户在 2D 草案阶段回复“继续建模/生成模型/就按这个做”时，走 `build_confirmed`，不能回到旧的缺硬件或需求分析流程。
- 智能浇花模板草案只允许修改盒体尺寸；BOM、硬件安装面、旋转和坐标必须由服务端模板重建，不能信任客户端回传的草稿布局。
- 用户明确新建产品需求时，走 `new_requirement` 并清理旧任务上下文。

## 硬性边界

- 首次需求分析和主体生成中，LLM 不允许决定最终 CAD 坐标、变换矩阵或模型代码。
- 只有 `model_edit` 可让 LLM 为当前项目 CadQuery 源码副本生成精确 `old_text/new_text` 补丁；公共模板、其他项目、服务器、硬件库和其他 ZW-CAD 分支始终只读。
- 不能编造硬件库不存在的硬件尺寸或 profile。
- 独立结构件项目只允许使用通用件库中已有且 `model_type: "structural_part"` 的母版；不支持 custom profile，也不从自然语言临时生成任意结构。
- 结构件缺少可读取、可静态校验的 `cadquery_model` 时必须返回 `structural_model_template_unavailable`，不能用包围盒或电子板代理继续。
- 多结构件默认每个 profile 一件，沿 X 轴按 15 mm 间距并排。此位置只用于整体预览，不表示装配、配合或连接关系。
- 缺少硬件时必须明确提示缺失功能与缺失硬件；只有用户选择忽略或补 profile 后才能继续。
- LLM 不可用时必须返回可理解的阻断原因，不能静默退回本地需求分析。
- 真实 3D 模型生成失败时必须显示明确错误，不能静默切到简化模型当成真实结果。

## 输出要求

本 skill 本身不产生 CAD 产物。它应体现在每轮 trace、workflow 工具清单或 LLM system prompt 中，帮助后续 skill 判断当前阶段和允许动作。

## 验证方式

- 首轮需求应先进入需求分析确认，而不是直接建模。
- 已有 2D 草案后，“继续建模”必须进入构建路径。
- 缺失硬件选择“忽略缺失功能继续”后，不能再次回到同一个缺失硬件阻断。
- 方案修改必须在同一任务目录内重算。
- 纯结构件单选、多选和自然语言点名均不得出现 controller、XIAO fallback 或盒体产物。
- 结构件整体预览必须标记为不可打印场景；每个结构件必须保留独立 STEP/STL 导出项并分别执行 mesh 校验。
- 公共结构件母版在项目建立后保持只读，后续修改只作用于 `project/structural-parts.cq.py` 及其修订。
