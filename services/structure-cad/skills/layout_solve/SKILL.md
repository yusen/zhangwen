# layout_solve

## 用途

生成硬件、功能开孔、固定结构和 M2 固定孔的位置。

## 何时调用

- `box_feasibility_check` 通过后。
- 用户修改硬件位置、安装面、旋转、间距或盒体尺寸后。

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

