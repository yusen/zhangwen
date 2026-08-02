import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 30mm 长度方向，Y 为 22mm 宽度方向，+Z 为元件/接口所在正面。
# PCB 位于 z=0 到 z=pcb_thickness。
# 安装意图：默认外表面安装，用户偏好默认前侧面；具体安装到哪个外侧面由后续装配参数决定，本模型不做旋转/平移。
# =========================
pcb_length = 30.0
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

microphone_diameter = 9.7
microphone_length_x = 7.0
microphone_radius = microphone_diameter / 2.0
microphone_embed_x = 7.0
microphone_center_x = -pcb_length / 2.0 + microphone_embed_x - microphone_length_x / 2.0
microphone_center_y = 0.0
microphone_center_z = pcb_thickness

# PCB 主体：30 x 22 x 1mm，四角 R2mm。
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

# 声音传感器主体：直径 9.7mm、厚度 7mm 的圆柱。
# 圆柱轴线沿 X 方向，圆底面平行 PCB -X 端面；从 PCB -X 边向内深入 7mm。
# 主体中心线在 X 轴上：y=0，z=pcb_thickness。
microphone = (
    cq.Workplane("YZ")
    .circle(microphone_radius)
    .extrude(microphone_length_x)
    .translate((microphone_center_x - microphone_length_x / 2.0, microphone_center_y, microphone_center_z))
)

result = pcb.union(connector).union(microphone)
show_object(result, name="声音传感器")
