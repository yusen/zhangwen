# design_validate

## 用途

执行确定性规则校验，包括硬件干涉、壳体内腔、固定结构、开孔对齐、壁厚、打印可行性和 CadQuery 静态检查。

## 何时调用

- `layout_solve` 和 `cadquery_generate` 后。
- 用户通过 GUI 或对话修改参数后。

## 输入格式

```json
{
  "enclosure": {},
  "layout_plan": {},
  "parameters": {},
  "cadquery_code": ""
}
```

## 输出格式

```json
{
  "status": "ok",
  "checks": [],
  "warnings": [],
  "validation_context": {}
}
```

## 失败状态

- `needs_input`：存在阻断性 `fail` 检查。反馈必须说明失败项、建议动作和可选按钮。

