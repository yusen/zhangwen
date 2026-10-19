# cadquery_generate

## 用途

由后端确定性程序生成 CadQuery 建模代码。LLM 不直接写 CadQuery 代码。

## 何时调用

- `layout_solve` 后。
- 影响结构、开孔、固定方式、盒体参数的步骤被重跑后。

## 输入格式

```json
{
  "enclosure": {},
  "layout_plan": {},
  "bom": [],
  "hardware_profiles": [],
  "parameters": {}
}
```

## 输出格式

```json
{
  "status": "ok",
  "cadquery_code": "string",
  "cad_parameters": {}
}
```

## 失败状态

如果无法生成安全代码，应返回 `needs_input` 或 validation fail，不能把用户输入当成代码执行。

