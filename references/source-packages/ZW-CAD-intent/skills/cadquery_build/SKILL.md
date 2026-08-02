---
name: cadquery-build
description: 运行 ZW-CAD-intent 项目 CadQuery 源码并导出真实 STEP/STL。用于普通盒体构建，也用于 structural_parts_v1 项目的整体并排预览、逐结构件导出、manifest 和逐件 mesh 校验。
---

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

`template_parts_v1` 案例模板使用以下导出契约：

```json
{
  "template_parts_manifest": {
    "schema_version": "template_parts_v1",
    "scene_only": true,
    "parts": [
      { "id": "main_body", "printable": true }
    ],
    "references": []
  },
  "exports": [
    { "id": "cadquery_template_scene_stl", "printable": false, "scene_only": true },
    { "id": "cadquery_template_main_body_stl", "printable_part_id": "main_body" }
  ]
}
```

模板整体场景、参考件和可打印部件必须分别标记。整体场景与参考件不得生成普通 `base/lid/hardware` 伪导出；只有 `printable: true` 的模板部件进入可打印 STL 清单并执行制造 mesh 校验。项目源码使用模板适配后的完整 CQ-editor 文件，构建失败时保留 2D 案例预览并返回明确错误。

`structural_parts_v1` 项目额外返回：

```json
{
  "status": "artifact_exports",
  "exports": [
    {
      "id": "cadquery_structural_scene_stl",
      "printable": false,
      "scene_only": true
    },
    {
      "id": "cadquery_structural_quadruped_dog_thigh_stl",
      "printable_part_id": "quadruped_dog_thigh"
    }
  ],
  "structural_parts_manifest": {
    "schema_version": "structural_parts_v1",
    "parts": []
  },
  "mesh_validation_report": {}
}
```

## 结构件导出规则

- `model.step` 和 `model.stl` 是按 15 mm 间距并排的整体预览，导出项标记 `printable: false`、`scene_only: true`。
- 每个结构件分别写入 `structural-parts/` 下的 STEP 和 STL，并用 `printable_part_id` 关联 `printable_parts`。
- 写入 `structural-parts-manifest.json`，记录每个零件的 ID、名称、文件名和路径。
- mesh 校验同时检查整体场景和每个独立 STL；前端可打印清单只展示独立零件。

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

结构件源码不满足 `structural_parts_v1`、对象列表为空或某个条目不是有效 CadQuery 对象时必须失败，不能改走普通盒体导出。

## 验证方式

- 单件项目应产生一组独立 STEP/STL 和一个不可打印整体预览。
- 多件项目应逐件导出且文件名、manifest、`printable_part_id` 一一对应。
- 不得产生误导性的底壳、上盖或硬件代理导出项。
