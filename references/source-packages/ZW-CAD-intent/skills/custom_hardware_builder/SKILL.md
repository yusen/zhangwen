# custom_hardware_builder

## 用途

用于“用户自定义硬件”独立工作流。用户在硬件库抽屉中选择“电子器件”或“结构件”，用自然语言描述一个单独硬件；LLM 负责判断信息是否足够、生成 CadQuery 硬件本体模型和硬件库 profile 草案。该流程不进入主体产品需求分析、BOM 推断、布局求解或确定性产品模板。

## 输入

输入包含：

- `hardware_name`：硬件名称。
- `custom_hardware_type`：`electronic` 或 `structural`。
- `description`：用户自然语言描述。
- `conversation`：前几轮用户补充和系统反馈。

## 关键信息检查

电子器件必须尽量确认：

- 主体外形和尺寸：长、宽、高/厚度，圆角、圆柱、PCB 或异形外轮廓。
- 坐标方向：X/Y/Z 对应的物理方向，默认硬件中心为原点，+Z 为正面。
- 固定方式：螺丝孔、卡槽、胶粘、底面固定、上盖外侧、侧面、外置不固定等。
- 开孔需求：屏幕、摄像头、按钮、接口、线缆、水管、拨杆、指示灯、传感窗口。
- 避让空间：接线座外侧、线缆出口、可插拔方向、用户操作空间。
- 关键元件位置：接口、显示屏、拨杆、连接器、固定孔坐标。

结构件必须尽量确认：

- 用途和受力/配合关系。
- 外形尺寸和壁厚。
- 与外壳或硬件的连接方式；如果用户明确说明独立存在且不连接盒体，则记录为独立结构件。
- 孔、槽、卡扣、限位、铰链、插口、口袋等结构。
- 需要避让或可拆装的方向。
- 3D 打印方向、最小厚度或倒角需求。

安装信息必须按以下两类处理：

- 用户明确说明“独立放置”“独立存在”“不与盒子连接”“无需固定”等含义时，使用 `mounting.mode: "external_independent_module"`。此时明确写入 `clearance_mm: 0` 和 `fixed_structure.type: "external_independent_module"`，省略 `mating_hardware_face` 与 `preferred_enclosure_surface`，不得为通过校验伪造盒体安装面或正间隙。
- 需要安装到盒体的普通硬件仍必须说明硬件贴合面、盒体安装位置和大于 0 的安装间隙；缺少这些信息时返回 `status: "needs_input"`。
- 只有“无需间隙”而没有明确独立语义时，不得推断为独立结构件，仍需确认真实安装方式。

`opening` 只记录盒体需要为硬件切出的开孔。本体上的通孔、盲孔、方孔、槽和镂空属于 CadQuery 硬件几何，不得误写为外壳 `opening`。独立结构件没有盒体开孔或避让需求时，`opening` 和 `keepouts` 必须为 `[]`。

如果缺少当前安装模式真正需要的关键尺寸、固定方式、开孔/避让依据，必须返回 `status: "needs_input"` 和 `missing_fields`，不要生成可提交 profile。用户已经明确某项对独立结构件“不适用”时，不得继续追问该项。

## 缺失信息表述规则

`user_feedback` 和 `missing_fields` 都是直接展示给普通用户看的内容，禁止直接输出 profile 字段名、变量名或路径，例如 `mounting.clearance_mm`、`mounting.preferred_enclosure_surface`、`mounting.holes[0].x`、`opening[0].size_mm.width`。

发现目标字段数值缺失时，必须按这个顺序表达：

1. 用自然语言说明该字段代表的真实含义。
2. 告诉用户具体还缺什么。
3. 如需要单位，明确写出单位，例如 mm。

常见字段应这样改写：

- `mounting.clearance_mm`：普通盒体安装还需要说明固定结构与外壳或安装面之间预留多少安装间隙，单位 mm；独立结构件直接记录为 0，不要追问。
- `mounting.preferred_enclosure_surface`：普通盒体安装还需要说明这个硬件默认固定在盒子的哪个位置，例如底部、上盖内侧或上盖外侧；独立结构件不输出该字段，也不要追问。
- `mounting.mating_hardware_face`：普通盒体安装还需要说明硬件本体的哪一面贴合外壳或固定结构，例如底面、背面或侧面；独立结构件不输出该字段，也不要追问。
- `mounting.holes[0].x` / `mounting.holes[0].y`：还需要说明第 1 个固定孔相对硬件中心的 X/Y 坐标，单位 mm。
- `mounting.holes[0].diameter_mm`：还需要说明第 1 个固定孔的直径，单位 mm。
- `opening[0].preferred_face`：还需要说明第 1 个外壳开孔应该位于盒子的哪个面。
- `opening[0].size_mm.width` / `opening[0].size_mm.height`：还需要说明第 1 个外壳开孔的宽度和高度，单位 mm。
- `keepouts[0].center_mm` / `keepouts[0].size_mm`：还需要说明第 1 个避让空间的位置和尺寸，单位 mm。

错误示例：

```json
{
  "user_feedback": "还缺少 mounting.clearance_mm、mounting.preferred_enclosure_surface。",
  "missing_fields": ["mounting.clearance_mm", "mounting.preferred_enclosure_surface"]
}
```

正确示例：

```json
{
  "user_feedback": "模型已经能预览。确认写入前，还需要补充两点：固定结构与外壳之间预留多少安装间隙，单位 mm；这个硬件默认固定在盒子的哪个位置，例如底部、上盖内侧或上盖外侧。",
  "missing_fields": [
    "还需要说明固定结构与外壳或安装面之间预留多少安装间隙，单位 mm。",
    "还需要说明这个硬件默认固定在盒子的哪个位置，例如底部、上盖内侧或上盖外侧。"
  ]
}
```

## 输出

只返回 JSON，不返回 Markdown。对话区只展示 `user_feedback`，不要展示 CadQuery 源码。

信息不足时：

```json
{
  "status": "needs_input",
  "user_feedback": "还缺少主体尺寸和固定方式。",
  "missing_fields": ["主体长宽厚", "固定方式"],
  "profile": null,
  "cadquery_code": ""
}
```

信息完整时，`cadquery_code` 必须是完整 Python 源码字符串，不能使用省略号、Markdown 代码块或解释文字。代码必须能被 CQ-editor 直接运行，并能由后端导出 STL。

```json
{
  "status": "ok",
  "user_feedback": "已生成预览草案，请检查中心画布。",
  "missing_fields": [],
  "profile": {
    "id": "user_custom_example",
    "name": "示例硬件",
    "hardware_system": "user_custom",
    "custom_hardware_type": "electronic",
    "category": "sensor",
    "roles": ["sensor"],
    "dimensions_mm": {
      "length_x": 30,
      "width_y": 20,
      "height_z": 8
    },
    "coordinate_system": {
      "origin": "hardware_body_center",
      "x_axis": "length direction",
      "y_axis": "width direction",
      "positive_z": "front/component side"
    },
    "mounting": {
      "mode": "base_floor_custom_mount",
      "mating_hardware_face": "-Z",
      "preferred_enclosure_surface": "base_floor",
      "clearance_mm": 0.8,
      "retainer_height_mm": 1.2,
      "holes": []
    },
    "opening": [],
    "keepouts": [],
    "cad_reference": {
      "shape": "custom_hardware",
      "color": "#4f9a94"
    },
    "cadquery_model": {
      "format": "cadquery_python",
      "path": "server/data/hardware-models/user_custom_example.py",
      "entrypoint": "result",
      "source_skill": "custom_hardware_builder",
      "status": "preview"
    },
    "source_status": "用户自定义硬件预览草案",
    "thumbnail_url": "/assets/hardware/user_custom_example.png"
  },
  "cadquery_code": "import cadquery as cq\n\nhardware_name = \"custom_example\"\nbody = cq.Workplane(\"XY\").box(30, 20, 4).translate((0, 0, 2))\nresult = body\n\nshow_object(result, name=hardware_name)"
}
```

独立结构件信息完整时，必须输出结构件标签和独立安装契约。下面示例中的中央方孔是结构件本体特征，因此 `opening` 仍为空：

```json
{
  "status": "ok",
  "user_feedback": "已生成独立结构件预览草案，请检查中心画布。",
  "missing_fields": [],
  "profile": {
    "id": "user_custom_square_bore_spacer",
    "name": "方孔圆柱结构件",
    "hardware_system": "user_custom",
    "custom_hardware_type": "structural",
    "category": "structural_part",
    "model_type": "structural_part",
    "roles": ["structural_part"],
    "dimensions_mm": {
      "length_x": 10,
      "width_y": 10,
      "height_z": 5
    },
    "coordinate_system": {
      "origin": "bottom_face_center",
      "x_axis": "length direction",
      "y_axis": "width direction",
      "positive_z": "top direction"
    },
    "mounting": {
      "mode": "external_independent_module",
      "clearance_mm": 0,
      "fixed_structure": {
        "type": "external_independent_module"
      },
      "holes": []
    },
    "opening": [],
    "keepouts": [],
    "cad_reference": {
      "shape": "custom_structural_part",
      "color": "#82909b"
    },
    "cadquery_model": {
      "format": "cadquery_python",
      "path": "server/data/hardware-models/user_custom_square_bore_spacer.py",
      "entrypoint": "result",
      "source_skill": "custom_hardware_builder",
      "status": "preview"
    },
    "source_status": "用户自定义独立结构件预览草案",
    "thumbnail_url": "/assets/hardware/user_custom_square_bore_spacer.png"
  },
  "cadquery_code": "import cadquery as cq\n\nhardware_name = \"square_bore_spacer\"\nbody = cq.Workplane(\"XY\").circle(5.0).extrude(5.0)\ncutout = cq.Workplane(\"XY\").rect(5.0, 5.0).extrude(5.0)\nresult = body.cut(cutout)\n\nshow_object(result, name=hardware_name)"
}
```

## CadQuery 约束

- 代码必须是单文件 CQ-editor 可运行脚本。
- 必须包含 `import cadquery as cq`、`result = ...`、`show_object(result, name=...)`。
- `cadquery_code` 必须是完整源码，不允许出现 `...`、```、伪代码或“此处省略”。
- 变量名、函数名和 `show_object` 的 `name` 推荐使用 ASCII；中文硬件名称放在 `profile.name` 和 `user_feedback` 中，避免 Python 文件编码或终端显示问题影响预览。
- 优先使用稳定建模写法：先生成实体，再对实体边做圆角或切孔。例如用 `.box(...).edges("|Z").fillet(...)`，不要在尚未形成实体的 sketch/vertices 阶段调用会依赖 solid 的操作。
- 孔位优先用实体切除：先创建 PCB 实体，再用 `faces(">Z").workplane().pushPoints(...).hole(...)`。
- 只描述硬件本体，不决定最终产品中的装配坐标。
- 不使用 `open`、`exec`、`eval`、`subprocess`、网络请求或本地路径 import。
- 所有尺寸单位默认 mm。

## 可运行 CadQuery 示例

下面是一个最小但完整的电子器件模型示例。生成自定义硬件时应返回类似这种完整代码，而不是省略号。

```python
import cadquery as cq

# Units: mm. Origin is the hardware body center in XY; bottom is z=0.
hardware_name = "custom_pcb_module"
pcb_length = 30.0
pcb_width = 20.0
pcb_thickness = 1.6
corner_radius = 2.0
hole_diameter = 3.0
hole_offset = 4.0

pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness)
    .translate((0, 0, pcb_thickness / 2.0))
    .edges("|Z")
    .fillet(corner_radius)
)

hole_points = [
    (-pcb_length / 2.0 + hole_offset, -pcb_width / 2.0 + hole_offset),
    (-pcb_length / 2.0 + hole_offset, pcb_width / 2.0 - hole_offset),
    (pcb_length / 2.0 - hole_offset, -pcb_width / 2.0 + hole_offset),
    (pcb_length / 2.0 - hole_offset, pcb_width / 2.0 - hole_offset),
]

pcb = (
    pcb.faces(">Z")
    .workplane()
    .pushPoints(hole_points)
    .hole(hole_diameter)
)

connector = (
    cq.Workplane("XY")
    .box(6.0, 10.0, 5.7)
    .translate((pcb_length / 2.0 - 3.0, 0, pcb_thickness + 5.7 / 2.0))
)

chip = (
    cq.Workplane("XY")
    .box(8.0, 8.0, 1.2)
    .translate((-5.0, 0, pcb_thickness + 0.6))
)

result = pcb.union(connector).union(chip)

show_object(result, name=hardware_name)
```

## 案例

用户描述：`一个继电器模块，PCB 37x26x1，四角孔直径 3mm，距边 4.8mm，-Y 面贴盒子侧壁，只有拨杆开孔。`

应识别：

- 类型：电子器件。
- 主体：PCB 长宽厚和倒角。
- 固定：四角孔。
- 安装：盒内底面，-Y 面贴侧壁。
- 开孔：拨杆开孔。
- 避让：接线座外侧空间。

用户描述：`一个外置电池口袋，内尺寸比电池大 1.5mm，壁厚 2mm，+X 面镂空。`

应识别：

- 类型：结构件。
- 主体：空心长方体口袋。
- 固定：作为结构件与外壳连接，需确认连接面或默认底面固定。
- 开口：+X 面镂空。
- 如缺少电池尺寸或口袋安装面，应要求用户补充。
