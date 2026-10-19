# 结构描述与机械档案

## 自然语言描述

官方 RDK X5 产品规格书 V1.1 给出的整板外形包络为长 85 mm、宽 56 mm、高 20 mm。本包建立以包络中心为 XY 原点、长边为 X、短边为 Y、元件高度为正 Z 的基础占位模型；模型只表达总体占用空间，不表达 PCB 板厚、圆角、散热器、连接器、天线和元件的真实形状。

官方尺寸图显示四个直径 2.5 mm 的安装孔，但当前提取资料未能把各孔中心无歧义地转换到本包坐标系，因此孔中心不写入机器 JSON。HDMI、Type-C、Micro-USB、RJ45、USB-A、40PIN、MIPI CSI/DSI、音频、CAN FD、TF 卡和天线的开口与线缆弯折区也不从图片猜测；用于外壳时必须取得官方 2D/3D 图纸或实物测量后再补充。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "drobotics_rdk_x5_envelope",
    "display_name": "D-Robotics RDK X5",
    "category": "mcu",
    "roles": ["mcu", "compute"],
    "dimensions": {
      "length_x": 85.0,
      "width_y": 56.0,
      "height_z": 20.0
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
      "clearance": 1.0,
      "mating_hardware_face": null,
      "allowed_enclosure_surfaces": ["external"],
      "holes": []
    },
    "model_kind": "envelope",
    "keepouts": [],
    "openings": []
  },
  "model": {
    "path": "models/cadquery.py",
    "sha256": "96c21e7da711226a03f8d25c3ce608f22beba9c769da575815054a481caab276",
    "verificationStatus": "OFFICIAL_DOC_VERIFIED",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```
