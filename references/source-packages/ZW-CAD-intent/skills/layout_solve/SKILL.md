---
name: layout-solve
description: 为 ZW-CAD-intent 普通盒体项目生成硬件、开孔、固定结构和固定孔布局。独立通用结构件项目跳过盒体布局，由 standalone_structural_parts 单独生成仅用于预览的结构件场景。
---

# layout_solve

## 用途

生成硬件、功能开孔、固定结构和 M2 固定孔的位置。

## 何时调用

- `box_feasibility_check` 通过后。
- 用户修改硬件位置、安装面、旋转、间距或盒体尺寸后。
- `design_mode: "structural_part_project"` 时跳过本步骤，不生成 hardware、opening、mounting 或 mounting-hole transforms。

## 输入格式

```json
{
  "enclosure": {},
  "oriented_hardware_specs": [],
  "parameters": {}
}
```

## 输出格式

```json
{
  "status": "ok",
  "layout_plan": {
    "hardware_transforms": [],
    "opening_transforms": [],
    "mounting_transforms": [],
    "mounting_hole_transforms": []
  }
}
```

## 失败状态

布局无法满足约束时应返回 `needs_input`，要求用户增大盒体、调整安装面或减少硬件。

独立结构件的 `structural_scene` 由专用流程沿 X 轴按 15 mm 间距生成，所有位移都标记为 `preview_only`，不属于本 skill 的盒体布局结果。

## 验证方式

- 普通盒体项目继续输出四类 transforms。
- 独立结构件项目不得出现盒体布局、固定孔或伪造装配关系。
