# cadquery_build

## 用途

运行生成好的 CadQuery 代码，导出真实 STEP/STL 和 mesh 检查结果。

## 何时调用

- artifact 生成后自动静默调用。
- 用户手动点击 CadQuery build 或需要刷新真实模型时。

## 输入格式

```json
{
  "artifact": {},
  "designId": "ZW-PRODUCT-20260623-120000"
}
```

## 输出格式

```json
{
  "status": "artifact_exports",
  "exports": [],
  "mesh_validation_report": {}
}
```

## 失败状态

- `pending`：CadQuery 或依赖缺失，前端应明确显示真实 3D 模型暂不可用，保留 2D 草案或调试预览，但不要把它当作真实 3D 降级模型。
- `needs_input`：代码缺失或运行失败，需要显示失败原因。
