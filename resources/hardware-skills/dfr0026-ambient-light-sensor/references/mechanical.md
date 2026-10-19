# DFR0026 机械档案

## 自然语言描述

该器件是一块模拟环境光线传感器模块。结构模型以 PCB 中心作为 XY 原点，以 PCB 底面作为
`Z=0`；X 轴沿 PCB 的 30 mm 长度方向，Y 轴沿 22 mm 宽度方向，+Z 指向传感器和接线口所在的
元件面，+X 指向接线口。

PCB 主体长 30 mm、宽 22 mm、厚 1 mm，四个角均采用 4 mm 圆角。PCB 在模型中的范围为
`X=-15～15 mm`、`Y=-11～11 mm`、`Z=0～1 mm`。

接线口长 6 mm、宽 10 mm、高 5.7 mm，位于 PCB 的 +X 侧并沿 Y 方向居中。接线口的 +X 外侧面
与 PCB 的 +X 边 `X=15 mm` 对齐，因此接线口整体位于 PCB 投影范围内；其中心坐标为
`(12, 0, 3.85) mm`，底面位于 PCB 顶面 `Z=1 mm`，最高点为 `Z=6.7 mm`。从 PCB 的 +X 边向外
至少预留 10 mm 接线避让空间，对应 `X=15～25 mm` 的线缆 keepout。

PCB 上有两个直径 3 mm 的通孔，均靠近 -X 边，并分别位于 +Y 和 -Y 两侧。每个孔中心距离相邻
-X 板边和 ±Y 板边均为 3.5 mm，因此孔中心坐标分别为 `(-11.5, 7.5) mm` 和
`(-11.5, -7.5) mm`。

感光器件在参考模型中简化为一个直径 5 mm、高 2.7 mm 的圆柱体，位于 PCB 元件面，XY 中心坐标
为 `(-4, 0) mm`。圆柱底面位于 PCB 顶面 `Z=1 mm`，中心高度为 `Z=2.35 mm`，顶面高度为
`Z=3.7 mm`。

该参考模型的总包络为 30 × 22 × 6.7 mm。模型只表达 PCB、固定孔、接线口、感光器件和接线避让
空间，不表达焊点、铜箔、丝印、线材弯曲半径和其他小型元件；精密外壳设计仍需结合实物复核。

## 关键尺寸汇总

| 项目 | 参数 |
|---|---|
| PCB | 30 × 22 × 1 mm，四角 R4 |
| 固定孔 | 2 × 直径 3 mm；中心 `(-11.5, ±7.5)` |
| 接线口 | 6 × 10 × 5.7 mm；中心 `(12, 0, 3.85)` |
| 感光器件简化体 | 直径 5 × 2.7 mm；中心 `(-4, 0, 2.35)` |
| 总包络 | 30 × 22 × 6.7 mm |
| +X 接线避让 | 从 `X=15 mm` 向外至少 10 mm |

## 尺寸冲突与使用边界

DFRobot 页面将模块外形标称为 20 × 30 mm，而用户提供的自然语言和参考模型采用 30 × 22 mm。
本包为保持结构描述、机器机械档案和 CadQuery 模型一致，暂以 30 × 22 mm 作为当前结构基线；
制作卡扣、紧配外壳、孔位治具或批量制造前，必须用实物卡尺复核该 2 mm 宽度差异以及实际孔位。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "dfr0026_ambient_light_sensor",
    "display_name": "DFRobot DFR0026 模拟环境光线传感器",
    "category": "sensor",
    "roles": ["sensor", "ambient_light"],
    "dimensions": {
      "length_x": 30.0,
      "width_y": 22.0,
      "height_z": 6.7
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
      "strategy": "hole_fastened",
      "clearance": 0.8,
      "mating_hardware_face": null,
      "allowed_enclosure_surfaces": ["external"],
      "holes": [
        {
          "hole_id": "h1",
          "center": {"x": -11.5, "y": 7.5},
          "diameter": 3.0,
          "fastener": "M3"
        },
        {
          "hole_id": "h2",
          "center": {"x": -11.5, "y": -7.5},
          "diameter": 3.0,
          "fastener": "M3"
        }
      ]
    },
    "model_kind": "envelope",
    "preview_geometry": {
      "source_sha256": "2409c80cd73dac4e1519c572083da9e0fe0678a59d3bf606255ab0cea20b9e1b",
      "primitives": [
        {
          "primitive_id": "pcb",
          "operation": "add",
          "kind": "rounded_box",
          "center": {"x": 0.0, "y": 0.0, "z": 0.5},
          "size": {"length_x": 30.0, "width_y": 22.0, "height_z": 1.0},
          "corner_radius": 4.0,
          "rotation_z_deg": 0,
          "role": "pcb"
        },
        {
          "primitive_id": "connector",
          "operation": "add",
          "kind": "box",
          "center": {"x": 12.0, "y": 0.0, "z": 3.85},
          "size": {"length_x": 6.0, "width_y": 10.0, "height_z": 5.7},
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "connector"
        },
        {
          "primitive_id": "light_sensor",
          "operation": "add",
          "kind": "cylinder",
          "center": {"x": -4.0, "y": 0.0, "z": 2.35},
          "diameter": 5.0,
          "height": 2.7,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "sensor"
        }
      ]
    },
    "keepouts": [
      {
        "keepout_id": "connector_cable",
        "center": {"x": 20.0, "y": 0.0, "z": 3.35},
        "size": {"length_x": 10.0, "width_y": 10.0, "height_z": 6.7}
      }
    ],
    "openings": [
      {
        "kind": "circle",
        "opening_id": "sensor_view",
        "center": {"x": -4.0, "y": 0.0},
        "center_z": 2.35,
        "diameter": 5.0,
        "preferred_face": "front",
        "clearance": 0.8
      }
    ]
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "0d7607eda90fa9d676d6a53defe6f95eed18f9e4ae261bd6c07261da76082972",
    "verificationStatus": "USER_CONFIRMED",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```

## 模型安全边界

`models/cadquery.py` 固定为 `REFERENCE_ONLY`。保存时只做 UTF-8/LF 规范化、SHA-256、Python 语法和机械档案校验，不因导入 Hardware Skill 而执行模型。
