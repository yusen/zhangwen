# 结构描述与机械档案

## 自然语言描述

记录 PCB 或主体尺寸、坐标原点、正方向、主要器件、接口、安装孔、开孔、运动空间和
禁布区。每个尺寸写明单位和相对基准；不确定的信息标记为“待实物验证”。

至少确认整体长/宽/高和坐标系后，应用才能显示基础包络预览。要让预览可用于结构件设计，还应
提供安装面与方式、孔中心和孔径、接口/感应窗口的形状/尺寸/中心/所在面，以及线缆、光学视场
或运动空间的三轴禁布区。这里是 3D 预览几何的唯一来源：应用在用户点击预览时把已确认实体编译为
受控几何。禁止从图片猜测尺寸；不要手工维护第二份 `preview_geometry`。

## 机器可读机械档案

```zhangwen:hardware-mechanical:v1
{
  "schema": "zhangwen.hardware-mechanical/v1",
  "profile": {
    "profile_id": "example_sensor_profile",
    "display_name": "<硬件显示名称>",
    "category": "sensor",
    "roles": ["sensor"],
    "dimensions": {
      "length_x": 30.0,
      "width_y": 20.0,
      "height_z": 8.0
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
    "sha256": "823d137af7116df2453ecf1c3a0294d433a6688c5714a6ebb5eb07bc2ce64a63",
    "verificationStatus": "USER_CONFIRMED",
    "executionPolicy": "REFERENCE_ONLY"
  }
}
```

修改 `models/cadquery.py` 后必须重新计算其规范化 UTF-8 内容的 SHA-256，并同步更新这里。

保存成功后，用户点击“查看 3D 预览”时，应用只把上方自然描述发送给结构化模型，生成受限实体并以
`source_sha256` 绑定当前描述。缓存缺失或描述改变时会自动重建并回写；不执行参考 Python，也不要求
预先生成图片。制造级复现仍需要来源明确且经过审核的 STEP/STL/GLB 或平台受信参数模型，普通用户包
不得自行声明受信模型身份。
