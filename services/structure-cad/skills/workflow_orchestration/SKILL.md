---
name: workflow-orchestration
description: ZW-CAD-intent 总流程编排说明。用于告诉 LLM 和内部 agent 当前任务应按哪个阶段推进、何时分支、何时阻断，以及哪些职责必须交给确定性工具。
---

# workflow_orchestration

## 用途

这是 `ZW-CAD-intent` 的总流程 skill。它不直接生成 CAD、不直接选硬件、不直接写坐标，而是说明整个 zwagent 应如何按阶段调用已有 skills。

LLM 在理解用户需求或验证 BOM 时必须知道：自己只负责需求理解、功能覆盖判断和对话解释；硬件库约束、布局、坐标、开孔、固定结构、CadQuery 代码和真实导出都由后端确定性工具完成。

## 标准主链路

1. `conversation_route`：先判断用户本轮动作。
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

## 分支规则

- 用户提出修改需求或修改已生成方案时，先走 `design_revision`，再从受影响阶段重算，默认复用当前 `taskId`。
- 用户点击或输入阻断选项时，先走 `resolution_option_route`，再执行对应恢复路径。
- 用户已选硬件并要求“给选定硬件做盒子”时，走 `selected_hardware_enclosure`，不强行从自然语言推导复杂功能。
- 用户在 2D 草案阶段回复“继续建模/生成模型/就按这个做”时，走 `build_confirmed`，不能回到旧的缺硬件或需求分析流程。
- 用户明确新建产品需求时，走 `new_requirement` 并清理旧任务上下文。

## 硬性边界

- LLM 不允许输出最终 CAD 坐标、开孔坐标、变换矩阵、CadQuery 代码或 OpenSCAD 代码。
- 不能编造硬件库不存在的硬件尺寸或 profile。
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
