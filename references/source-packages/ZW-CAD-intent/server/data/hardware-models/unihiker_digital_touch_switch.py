import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 35.5mm 长度方向，Y 为 22mm 宽度方向，+Z 为触摸面/接口所在正面。
# PCB 位于 z=0 到 z=pcb_thickness。
# 安装意图：默认外表面安装，用户偏好默认左侧面；具体安装到哪个外侧面由后续装配参数决定，本模型不做旋转/平移。
# =========================
pcb_length = 35.5
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 2.0

connector_length_x = 6.0
connector_width_y = 10.0
connector_height_z = 5.7
connector_center_x = pcb_length / 2.0 - connector_length_x / 2.0
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2.0

mounting_hole_diameter = 3.0
mounting_hole_x = 4.5
mounting_hole_y = pcb_width / 2.0 - 3.5

touch_pad_length_x = 15.0
touch_pad_width_y = pcb_width - 2.0
touch_pad_height_z = 0.4
touch_pad_corner_radius = 1.5
touch_pad_minus_x_gap = 1.0
touch_pad_center_x = -pcb_length / 2.0 + touch_pad_minus_x_gap + touch_pad_length_x / 2.0
touch_pad_center_y = 0.0
touch_pad_center_z = pcb_thickness + touch_pad_height_z / 2.0

# PCB 主体：35.5 x 22 x 1mm，四角 R2mm。
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

# 两个 M3 固定孔：关于 X 轴对称，位于 x=4.5，圆心距 Y 边 3.5mm。
for hole_y in (-mounting_hole_y, mounting_hole_y):
    pcb = (
        pcb.faces(">Z")
        .workplane()
        .pushPoints([(mounting_hole_x, hole_y)])
        .hole(mounting_hole_diameter)
    )

# +X 边接线口：6 x 10 x 5.7mm，+X 外边与 PCB +X 外边齐平，整体位于 PCB 上。
connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

# 触摸接触面：15 x 20 x 0.4mm，四角 R1.5mm。
# 其 -X 边距离 PCB -X 边 1mm，Y 方向距离 PCB +/-Y 边各 1mm。
touch_pad = (
    cq.Workplane("XY")
    .box(touch_pad_length_x, touch_pad_width_y, touch_pad_height_z, centered=(True, True, True))
    .edges("|Z")
    .fillet(touch_pad_corner_radius)
    .translate((touch_pad_center_x, touch_pad_center_y, touch_pad_center_z))
)

result = pcb.union(connector).union(touch_pad)
show_object(result, name="数字触摸开关")
