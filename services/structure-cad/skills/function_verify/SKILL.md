# function_verify

## 用途

由 LLM 验证 BOM 是否覆盖用户需求，并确认 BOM 中所有 `hardware_id` 都来自硬件库。

验证时必须参考 `requirement_function_selection_analysis` 的功能拆解结果，逐项检查功能是否被 BOM 覆盖。

## 何时调用

- `hardware_bom_select` 成功后立即调用。
- BOM 被用户修改或自动重选后重新调用。

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

## 输出格式

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
