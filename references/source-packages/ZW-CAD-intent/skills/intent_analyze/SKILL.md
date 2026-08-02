---
name: intent-analyze
description: 把 ZW-CAD-intent 的自然语言需求和硬件选择整理成结构化 intent。用于普通电子盒体项目，也用于识别并保持纯通用结构件项目的 design_mode、硬件体系和无主控无盒体约束。
---

# intent_analyze

## 用途

把用户自然语言、已选硬件和当前任务状态整理成结构化 `intent`。本步骤由 LLM 主导理解需求，不生成 CAD 坐标或代码。

普通电子产品遵守同一条链路：先拆功能，再推导硬件角色，再匹配硬件库，最后进入结构化 intent。不要为某个电子产品写专用分支；不能因为库里缺硬件，就把用户需求降级成只做主控盒子。

`standalone_structural_parts` 是明确的流程模式，不是产品专用分支。命中后可由后端确定性地建立结构件 intent，不要求 LLM 推导电子功能。

## 何时调用

- 新任务第一次发送需求时。
- 用户在对话中修改产品功能、使用场景、硬件需求或尺寸约束时。
- 后续步骤发现需求不清晰，需要回到意图层重新解释时。

## 输入格式

```json
{
  "prompt": "用户原始或追加需求",
  "selectedHardwareIds": ["xiao_esp32s3"],
  "designMode": "",
  "currentDesignState": null,
  "userAnswers": []
}
```

独立结构件 intent 使用以下核心字段：

```json
{
  "design_mode": "structural_part_project",
  "product_type": "standalone_structural_parts",
  "hardware_system": "common",
  "selected_hardware_ids": ["quadruped_dog_thigh", "quadruped_dog_shin"],
  "functions": ["独立结构建模"],
  "required_hardware_roles": [
    {
      "role": "structural_part",
      "hardware_id": "quadruped_dog_thigh",
      "function": "独立结构建模"
    }
  ],
  "mounting_intents": [],
  "user_constraints": {
    "enclosure_generation": false,
    "controller_required": false,
    "scene_gap_mm": 15
  }
}
```

独立结构件 intent 不得生成 `enclosure_intent`，也不得加入 controller 角色。`model_type` 与原有 `category`、`roles` 相互独立：例如 18650 电池座仍可保留 `power` / `battery` 功能角色，但其 `model_type` 是 `structural_part`。

## 输出格式

```json
{
  "status": "ok",
  "intent": {
    "schema_version": "1.0",
    "product_name": "桌面小夜灯",
    "functions": ["灯光照明", "灯光控制"],
    "required_hardware_roles": [
      {
        "role": "light_source",
        "category": "output",
        "function": "灯光照明",
        "label": "LED 灯板或灯珠模块",
        "why_needed": "小夜灯需要光源硬件。",
        "unsupported_in_library": true
      }
    ],
    "selected_hardware_ids": ["xiao_esp32s3"],
    "mounting_intents": [],
    "enclosure_intent": {
      "type": "rectangular_box_with_lid",
      "manufacturing": "fdm_3d_printing",
      "lid_strategy": "snap_or_screw_lid",
      "allowed_shape": "rounded_rectangular_box"
    },
    "user_constraints": {
      "raw_prompt": "做一个桌面小夜灯",
      "size_mm": {},
      "notes": []
    }
  }
}
```

## 已选硬件要求

- 如果用户明确说“直接给已选硬件做盒子/装起来/不用管功能”，`selected_hardware_ids` 和对应硬件角色必须保留。
- 如果用户说“基于已选硬件做某功能产品”，输出必须包含已选硬件，并继续为缺失功能选型。
- 如果已选硬件与功能冲突、多余或无法承担用户说的功能，在 `required_hardware_roles.why_needed` 或 `user_constraints.notes` 中说明，不能静默丢弃。
- 如果所有已选硬件都是通用结构件且用户没有要求盒体，保持 `design_mode: "structural_part_project"`，不得自动补充 XIAO 或其他主控。
- 如果结构件与电子元器件混选，或用户明确要求盒体，按普通电子/盒体 intent 处理，不伪装成纯结构件项目。

## 缺失硬件要求

当硬件库没有功能所需硬件时，为该功能输出 `unsupported_in_library: true` 的 required hardware role。不要把产品名改成“主控保护和接口外露外壳”，也不要只保留 controller 后继续。

## 失败状态

- `needs_input`：需求为空、普通盒体形状超出带盖长方体盒子范围，或用户要求直接生成 CAD 代码。
- 独立结构件模式没有识别到具体通用结构件时，返回 `structural_part_selection_required`；不能把任意自然语言结构转换成临时母版。

## 验证方式

- 结构件单选、多选和明确点名都应保留 `hardware_system: "common"`、`design_mode: "structural_part_project"`。
- 独立结构件 intent 中不得出现 controller、盒体参数或盒体安装意图。
- 提到“盒子/外壳”时必须回到普通盒体 intent。
