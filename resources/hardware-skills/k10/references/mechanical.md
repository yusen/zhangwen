# 行空板 K10 结构描述与机械档案

## 自然语言描述

行空板 K10 主体是一块长 83.2 mm、宽 51.3 mm、厚 1.6 mm 的 PCB，四角倒圆半径
1 mm。坐标原点位于 PCB 的 XY 中心，+Z 指向显示屏一侧。

主要外形器件是显示屏和摄像头：

- 显示屏位于 PCB +Z 面。框架长 71 mm、宽 51 mm、高 4 mm；框架 -X 边与 PCB -X
  边相距 5.5 mm，整体位于 PCB 投影内。
- 显示区域长 57.5 mm、宽 43 mm，从框架 +Z 面下沉 1 mm；显示区域 -X 边与框架
  -X 边相距 10 mm。
- 摄像头位于 PCB -Z 面，中心为 `x=-12 mm, y=0`。底座为边长 8 mm、高 2.5 mm 的
  长方体，外接直径 8 mm、高 2.5 mm 的圆柱；镜头直径 2.5 mm，从圆柱外表面下沉 1 mm。
- 金手指以 PCB 本体为接口，从 +X 边向 -X 延伸 7 mm，覆盖 Y 方向，并分布在 PCB
  +Z/-Z 双面。

完整结构包络为 83.2 × 51.3 × 10.6 mm。参考模型保留 PCB 平面原点与上述相对尺寸；
生产 CAD 只消费下面的受控机械档案快照，不直接执行参考源码。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "unihiker_k10",
    "display_name": "UNIHIKER K10",
    "category": "controller",
    "roles": [
      "controller",
      "display",
      "camera"
    ],
    "dimensions": {
      "length_x": 83.2,
      "width_y": 51.3,
      "height_z": 10.6
    },
    "coordinate_system": {
      "origin": "pcb_center",
      "x_axis": "length",
      "y_axis": "width",
      "positive_z": "component_side"
    },
    "mounting": {
      "mode": "external_independent_module",
      "preferred_surface": "external",
      "strategy": "none",
      "clearance": 0.8,
      "mating_hardware_face": null,
      "allowed_enclosure_surfaces": [],
      "holes": []
    },
    "model_kind": "unihiker_k10",
    "keepouts": [],
    "openings": [],
    "preview_geometry": {
      "primitives": [
        {
          "primitive_id": "pcb_main",
          "operation": "add",
          "kind": "rounded_box",
          "center": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.0
          },
          "size": {
            "length_x": 83.2,
            "width_y": 51.3,
            "height_z": 1.6
          },
          "corner_radius": 1.0,
          "rotation_z_deg": 0,
          "role": "pcb"
        },
        {
          "primitive_id": "display_frame",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": -0.6,
            "y": 0.0,
            "z": 2.8
          },
          "size": {
            "length_x": 71.0,
            "width_y": 51.0,
            "height_z": 4.0
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "body"
        },
        {
          "primitive_id": "camera_base",
          "operation": "add",
          "kind": "cylinder",
          "center": {
            "x": -12.0,
            "y": 0.0,
            "z": -2.05
          },
          "diameter": 8.0,
          "height": 2.5,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "sensor"
        }
      ],
      "source_sha256": "ff6cde96573749d5117bb4cf528fd8cd3c79b87c8240b8bfc384980b280d2fe5"
    }
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "ea55ca3d986a2c36478048f0afd7a27b9b25a7986bb4b6d3ec85258bdcb7c914",
    "verificationStatus": "VERIFIED_REFERENCE",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```

