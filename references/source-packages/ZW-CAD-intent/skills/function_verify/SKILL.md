---
name: function-verify
description: 验证 ZW-CAD-intent 普通电子项目的 BOM 功能覆盖和库内合法性。用于 BOM 生成或重选后；独立通用结构件项目必须显式跳过电子功能覆盖，只保留确定性的结构母版校验结果。
---

# function_verify

## 用途

由 LLM 验证 BOM 是否覆盖用户需求，并确认 BOM 中所有 `hardware_id` 都来自硬件库。

验证时必须参考 `requirement_function_selection_analysis` 的功能拆解结果，逐项检查功能是否被 BOM 覆盖。

## 何时调用

- `hardware_bom_select` 成功后立即调用。
- BOM 被用户修改或自动重选后重新调用。
- `design_mode: "structural_part_project"` 时不得调用 LLM 做电子功能覆盖；编排器直接记录跳过报告，并交由 `standalone_structural_parts` 校验结构母版。

## 输入格式

```json
{
  "intent": {},
  "bom": [],
  "hardware_library_summary": [],
  "attempt": 1,
  "maxAttempts": 3
}
```

独立结构件项目固定记录：

```json
{
  "status": "skipped",
  "verification_status": "skipped_structural_part_project",
  "reason": "独立结构件项目不包含电子功能覆盖验证。",
  "source": "deterministic_structural_parts"
}
```

跳过电子功能验证不等于跳过安全校验。独立结构件流程仍必须确定性检查：每个条目存在于硬件库、属于 `common`、`model_type` 为 `structural_part`、可信 `cadquery_model` 可读取且通过静态契约。

普通验证收到的 `hardware_library_summary` 也必须保留 `model_type`；该字段只用于模型分类，不能覆盖 `category` 或 `roles` 的功能语义。

## 输出格式

批量小模型模板已经由后端固定 BOM 和案例源码覆盖验证；当 `model_contract: "template_parts_v1"` 时，编排器跳过通用 LLM 功能补全，但仍检查每个 `hardware_id` 的 profile 是否存在，并在 CadQuery 预检/真实构建阶段验证模板部件契约。

```json
{
  "status": "ok",
  "verification_status": "pass",
  "covered_functions": ["主控保护"],
  "missing_functions": [],
  "missing_hardware": [],
  "uncovered_requirements": [],
  "library_violations": [],
  "attempts_used": 1,
  "max_attempts": 3
}
```

## 失败状态

- `needs_input` + `verification_status: "fail"`：功能未覆盖或硬件不在库中。
- `needs_input` + `verification_status: "blocked"`：LLM 未配置或调用失败。此时必须阻断用户，不能进入下一步。

失败反馈必须包含缺失功能、缺失硬件和用户下一步选择。

## 限制边界

- 不得因为 BOM 没有 controller 而判定独立结构件项目失败。
- 不得为通过验证而自动加入主控或电子器件。
- 普通电子项目的逐功能覆盖、库外硬件阻断和 LLM 不可用阻断保持不变。

## 验证方式

- 纯结构件项目应得到 `skipped_structural_part_project`，且不消耗 LLM function verifier 尝试次数。
- 普通电子项目仍必须逐项输出 `covered_functions`、`missing_functions` 和 `library_violations`。
