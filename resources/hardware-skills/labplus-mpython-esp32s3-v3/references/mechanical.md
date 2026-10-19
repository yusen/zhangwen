# 结构描述与机械档案

## 自然语言描述

- 预览精度等级：基础包络。单位为 mm；原点位于整体包络中心，X 轴沿官方图 51.8mm 水平方向，Y 轴沿 47.39mm 竖直方向，+Z 指向器件高度方向。
- 唯一应生成的预览实体是整体包络盒：`box`，尺寸 51.8×47.39×7.65，中心 `(0, 0, 0)`。它包住 PCB、屏幕、USB-C 和全部板载器件，不代表 PCB 本体轮廓。
- 官方图给出 PCB 标称厚度 1.5，但没有给出 PCB 在 7.65mm 总包络中的 Z 中心及完整圆角参数，因此不得另生成 PCB 实体。
- 官方图给出屏幕外框区域 41×26.55、显示区域 33.33×18.15，但没有完整给出它们相对包络原点的中心坐标和 Z 高度，因此不得另生成屏幕实体。
- 官方图给出两孔直径 3、中心距 24，但没有完整给出孔中心相对包络原点的坐标，因此 `mounting.holes` 保持空数组，不得从图片对称性猜测孔位。
- 官方图显示底部接口区域宽度 13，并标注局部高度 4；USB-C、金手指、按钮、麦克风、喇叭和传感器的完整三轴尺寸、中心及间隙均未给出，因此不生成连接器、开孔或禁布区实体。
- `mounting.clearance=0.8` 是保守设计建议，不是官方尺寸；当前模型不得用于外壳开孔、安装孔加工或制造复现。

## 建模与派生缓存边界

`mechanical.md` 的上述自然语言描述是 3D 预览唯一输入；本包不提供或手工维护 `preview_geometry`。CadQuery 文件只生成整体包络，不切孔、不表达屏幕、USB、金手指或板载器件。模型源码仅通过 Python `ast.parse` 语法检查；未运行 CadQuery 内核、未导出 STEP/STL、未进行实物装配。

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "labplus_mpython_esp32s3_v3_envelope",
    "display_name": "掌控板 3.0（ESP32-S3）",
    "category": "mcu",
    "roles": [
      "controller",
      "display",
      "sensor_hub"
    ],
    "dimensions": {
      "length_x": 51.8,
      "width_y": 47.39,
      "height_z": 7.65
    },
    "coordinate_system": {
      "origin": "envelope_center",
      "x_axis": "length",
      "y_axis": "width",
      "positive_z": "height"
    },
    "mounting": {
      "mode": "envelope_only",
      "preferred_surface": "external",
      "strategy": "none",
      "clearance": 0.8,
      "mating_hardware_face": null,
      "allowed_enclosure_surfaces": [],
      "holes": []
    },
    "model_kind": "envelope",
    "keepouts": [],
    "openings": []
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "749022bd6cdeab905cd9f615f39af12b2495c4470bae78b88d6075e98da51f0a",
    "verificationStatus": "OFFICIAL_DOC_VERIFIED",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```
