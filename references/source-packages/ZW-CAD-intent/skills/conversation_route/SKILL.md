---
name: conversation-route
description: ZW-CAD-intent 对话动作路由契约。用于区分新需求、确认、盒体建模、独立通用结构件建模、当前项目修改、刻字、撤销和阻断恢复，并输出确定性的 route_action。
---

# conversation_route

## 用途

判断用户最新输入在当前任务中属于哪一种动作，并把它路由到对应工具链。本 skill 只做对话调度，不生成 CAD，不直接决定最终坐标或模型代码。

## 何时调用

- `/api/agent/prepare` 收到用户输入时优先调用。
- 用户只选择通用件结构件，或在自然语言中明确点名通用件结构件时调用，用于判断是否进入无主控、无盒体的独立结构件流程。
- 用户点击“确认分析”、输入“确认/继续”、提出修改需求、修改已生成方案、确认/取消高影响修改、撤销修改，或要求“给选定硬件做盒子”时调用。
- 已有未完成刻字草稿时仍须先判断最新明确意图；圆角、倒圆、倒角、切角、边线、开孔、厚度、硬件移动、删除结构和撤销属于模型修改，不得被刻字草稿截获。
- 前端按钮可以显式传入 `routeAction`，但后端仍应记录 route 结果。

## 输入格式

```json
{
  "prompt": "用户最新输入或原始需求",
  "latestUserMessage": "用户最新消息",
  "conversationContext": {
    "workflowStage": "requirement_analysis|confirming|review|idle",
    "hasRequirementAnalysis": true,
    "hasDraft": false,
    "hasArtifact": false,
    "taskId": "ZW-PRODUCT-20260623-120000"
  },
  "selectedHardwareIds": ["xiao_esp32s3"],
  "designMode": "",
  "currentDesignState": {},
  "surfaceEngravingDraft": {
    "schema_version": "surface_engraving_draft_v1",
    "missing_fields": ["字体高度"]
  },
  "lastNeedsInput": {},
  "routeAction": ""
}
```

## 输出格式

```json
{
  "route_action": "model_edit",
  "confidence": 0.98,
  "reason": "已有项目，最新输入明确要求修改结构、边线、孔槽、厚度或硬件位置。",
  "source": "deterministic_conversation_route",
  "context_transition": {
    "from": "surface_engraving",
    "to": "model_edit",
    "action": "supersede",
    "clear_surface_engraving_draft": true
  }
}
```

仅当本轮从未完成刻字切换到模型修改时返回 `context_transition`。调用方必须据此清除未应用的刻字草稿和旧刻字阻断状态；已经成功写入模型的刻字不得删除。

## 支持的 route_action

- `new_requirement`：新需求或普通首次需求分析。
- `confirm_requirement_analysis`：确认需求分析，进入 BOM/profile/布局预审。
- `revise_requirement`：需求分析阶段修改功能、硬件或约束。
- `revise_artifact`：确认前草案或旧兼容链路中的结构化修改。
- `selected_hardware_enclosure`：用户已选硬件，要求直接为选定硬件做盒子。
- `standalone_structural_parts`：用户只选择或明确点名通用件结构件，且没有盒体意图；后续使用 `design_mode: "structural_part_project"`。
- `provide_custom_profile`：用户准备通过“用户自定义硬件”工作流补充缺失硬件。
- `change_mounting_face`：用户要求修改硬件安装面。
- `surface_engraving`：已有 artifact 后用户提出新增、修改或删除模型表面刻字。
- `model_edit`：已有活动项目后的普通自然语言模型修改，默认针对当前项目源码副本。
- `confirm_model_edit`：确认服务端保存的高影响修改方案。
- `cancel_model_edit`：取消待确认修改，保留当前模型。
- `undo_model_edit`：把当前项目恢复到上一版源码，并生成新的撤销修订。
- `build_confirmed`：用户确认 2D 草案，进入最终建模。

## 判定优先级

1. 前端显式 `routeAction`、确认按钮等确定性动作优先。
2. 已有活动项目时，最新明确的机械修改、撤销和刻字意图优先，避免把对当前结构件项目的修改误判成新项目。
3. 对新项目检查独立结构件条件：所有已选条目都必须属于 `common` 且 `model_type` 为 `structural_part`，或者文本明确点名一个或多个已知通用结构件。
4. “盒子、盒体、外壳、壳体、保护壳、机箱”等词具有否决作用；即使点名结构件，也不进入独立结构件流程。
5. 电子元器件、品牌专属硬件、未知 ID 与结构件混选时，不返回 `standalone_structural_parts`。
6. 明确新增、修改或删除文字时进入 `surface_engraving`。
7. 刻字草稿续答必须与 `missing_fields` 对应：等待字号时接受“3mm”，等待目标面或位置时接受“大斜面正中央”，等待文字时接受“内容改成‘好好学习’”或直接文字，等待排版时接受“保持两行”。
8. 禁止以“输入不超过 64 个字符”为理由判定刻字续答。没有匹配缺失字段的短句应按当前项目的普通模型对话处理。

## 限制边界

- 本 skill 本身不输出 CadQuery、Python、OpenSCAD 或最终 CAD 坐标；`model_edit` 分支只负责把请求交给受限模型修改 skill。
- 不凭空补硬件；是否能选硬件仍由 `hardware_bom_select` 决定。
- 本 skill 只识别独立结构件请求，不校验母版代码。具体 profile、`model_type` 和 `cadquery_model` 必须由 `standalone_structural_parts` 再次确定性校验。
- 有活动项目时，用户未明确说“新项目”的后续对话默认针对当前模型；疑似新产品但意图不明确时应追问，不自动清空项目。
- 切换到模型修改只清除尚未应用的刻字草稿，不回滚已经成功刻入的文字。

## 验证方式

- 对“确认/继续/可以”应路由为 `confirm_requirement_analysis` 或 `build_confirmed`。
- 已有 artifact 时，“把超声波改成人体传感器”“把这个孔移到右边”应路由为 `model_edit`。
- 刻字草稿等待字号时，“3mm”应继续 `surface_engraving`，但“大斜面正中央”不得因短句规则被误判为字号续答。
- 刻字草稿存在时，“在最高处的边线上倒一个 2mm 圆角”应路由为 `model_edit`，并返回清除刻字草稿的 `context_transition`。
- 对“给选定硬件做一个盒子”且存在已选硬件时，应路由为 `selected_hardware_enclosure`。
- 只选择“机器狗身体”和“18650 电池座”且没有盒体词时，应路由为 `standalone_structural_parts`。
- “做一个机器狗大腿”应路由为 `standalone_structural_parts`；“给机器狗大腿做一个外壳”不得进入该路由。
- MG90S 与机器狗大腿混选时不得进入独立结构件路由。
