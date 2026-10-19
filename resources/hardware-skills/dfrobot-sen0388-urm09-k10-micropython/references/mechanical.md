# 结构描述与机械档案

## 证据边界

DFRobot 官方只确认 SEN0388 模块外形为 47×22mm。下列探头、接线座、孔位和高度来自用户提供并已能建模的 URM09 参考资料，尚未对 SEN0388 实物逐项复核，因此只能用于早期结构预览和预留包络，不能直接用于最终开模或加工。

## 自然语言描述

- 坐标：PCB 平面中心为 X/Y 原点，X 沿 22mm 边，Y 沿 47mm 边，+Z 指向双探头正面；PCB 位于 Z=0–1.6mm。
- PCB：参考尺寸 22×47×1.6mm，四角圆角半径 2mm；22×47mm 与 SEN0388 官方整体外形一致。
- 双探头：参考直径 16.4mm、突出 12.4mm，中心位于 X=0、Y=±10.75mm。
- 接线座：参考包络 5.5×10×6.3mm，位于 PCB 背面并靠 +X 边居中。
- 总参考包络：22×47×20.3mm，从背面接线座最低点 -6.3mm 到探头最高点 +14.0mm。
- 安装孔：参考孔径 3mm，四孔中心距各自相邻 X/Y 方向 PCB 边缘均为 2.4mm；孔中心坐标 X=±8.6mm、Y=±21.1mm。该孔位只继承自用户 URM09 参考模型，尚未确认为 SEN0388 官方孔位。
- 两个探头前方必须保留无遮挡的声学视场；壳体开孔不得压住或覆盖探头正面，也应避免近距离反射边缘。
- 正式结构件发布前，必须用 SEN0388 实物或官方尺寸图复核 PCB 厚度、孔位、探头高度、接线座方向和线缆弯折空间。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "dfrobot_sen0388_urm09_envelope",
    "display_name": "DFRobot SEN0388 URM09 触发式超声波传感器",
    "category": "sensor",
    "roles": [
      "sensor"
    ],
    "dimensions": {
      "length_x": 22.0,
      "width_y": 47.0,
      "height_z": 20.3
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
      "allowed_enclosure_surfaces": [
        "external"
      ],
      "holes": [
        {
          "hole_id": "h1",
          "center": {
            "x": -8.6,
            "y": -21.1
          },
          "diameter": 3.0,
          "fastener": "unspecified"
        },
        {
          "hole_id": "h2",
          "center": {
            "x": -8.6,
            "y": 21.1
          },
          "diameter": 3.0,
          "fastener": "unspecified"
        },
        {
          "hole_id": "h3",
          "center": {
            "x": 8.6,
            "y": -21.1
          },
          "diameter": 3.0,
          "fastener": "unspecified"
        },
        {
          "hole_id": "h4",
          "center": {
            "x": 8.6,
            "y": 21.1
          },
          "diameter": 3.0,
          "fastener": "unspecified"
        }
      ]
    },
    "model_kind": "envelope",
    "keepouts": [
      {
        "keepout_id": "rear_connector_and_cable",
        "center": {
          "x": 8.25,
          "y": 0.0,
          "z": -3.15
        },
        "size": {
          "length_x": 5.5,
          "width_y": 10.0,
          "height_z": 6.3
        }
      }
    ],
    "openings": [
      {
        "kind": "circle",
        "opening_id": "transducer_a_view",
        "center": {
          "x": 0.0,
          "y": -10.75
        },
        "center_z": 14.0,
        "diameter": 16.4,
        "preferred_face": "front",
        "clearance": 0.8
      },
      {
        "kind": "circle",
        "opening_id": "transducer_b_view",
        "center": {
          "x": 0.0,
          "y": 10.75
        },
        "center_z": 14.0,
        "diameter": 16.4,
        "preferred_face": "front",
        "clearance": 0.8
      }
    ],
    "preview_geometry": {
      "primitives": [
        {
          "primitive_id": "pcb",
          "operation": "add",
          "kind": "rounded_box",
          "center": {
            "x": 0.0,
            "y": 0.0,
            "z": 0.8
          },
          "size": {
            "length_x": 22.0,
            "width_y": 47.0,
            "height_z": 1.6
          },
          "corner_radius": 2.0,
          "rotation_z_deg": 0,
          "role": "pcb"
        },
        {
          "primitive_id": "probe_pos_y",
          "operation": "add",
          "kind": "cylinder",
          "center": {
            "x": 0.0,
            "y": 10.75,
            "z": 7.8
          },
          "diameter": 16.4,
          "height": 12.4,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "sensor"
        },
        {
          "primitive_id": "probe_neg_y",
          "operation": "add",
          "kind": "cylinder",
          "center": {
            "x": 0.0,
            "y": -10.75,
            "z": 7.8
          },
          "diameter": 16.4,
          "height": 12.4,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "sensor"
        },
        {
          "primitive_id": "connector",
          "operation": "add",
          "kind": "box",
          "center": {
            "x": 19.25,
            "y": 0.0,
            "z": -3.15
          },
          "size": {
            "length_x": 5.5,
            "width_y": 10.0,
            "height_z": 6.3
          },
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "connector"
        },
        {
          "primitive_id": "mount_hole_1",
          "operation": "cut",
          "kind": "cylinder",
          "center": {
            "x": 8.6,
            "y": 21.1,
            "z": 0.8
          },
          "diameter": 3.0,
          "height": 1.6,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "mount_hole_2",
          "operation": "cut",
          "kind": "cylinder",
          "center": {
            "x": -8.6,
            "y": 21.1,
            "z": 0.8
          },
          "diameter": 3.0,
          "height": 1.6,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "mount_hole_3",
          "operation": "cut",
          "kind": "cylinder",
          "center": {
            "x": 8.6,
            "y": -21.1,
            "z": 0.8
          },
          "diameter": 3.0,
          "height": 1.6,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        },
        {
          "primitive_id": "mount_hole_4",
          "operation": "cut",
          "kind": "cylinder",
          "center": {
            "x": -8.6,
            "y": -21.1,
            "z": 0.8
          },
          "diameter": 3.0,
          "height": 1.6,
          "corner_radius": 0.0,
          "rotation_z_deg": 0,
          "role": "feature"
        }
      ],
      "source_sha256": "78089484bec36f47e4aa7ca8e64bded63d0cb0dbdf6005efed4615f593127d87"
    }
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "a20e186a6414d0b2eb329f4746edbbbd5f728748fd1c91fc124a6b0dfde840af",
    "verificationStatus": "VERIFIED_REFERENCE",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```
