import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 22mm 长度方向，Y 为 47mm 宽度方向，+Z 为两个超声波探头所在正面。
# PCB 位于 z=0 到 z=pcb_thickness。
# 安装意图：默认安装到外壳内表面，用户偏好默认前侧面；写入硬件库时记录“接线座所在 +X 边默认朝下”。
# 本模型只描述硬件自身，不做最终外壳装配旋转/平移。
# =========================
pcb_length = 22.0
pcb_width = 47.0
pcb_thickness = 1.6
pcb_corner_radius = 2.0

connector_length_x = 5.5
connector_width_y = 10.0
connector_height_z = 6.3
connector_center_x = pcb_length / 2.0 - connector_length_x / 2.0
connector_center_y = 0.0
connector_center_z = -connector_height_z / 2.0

mounting_hole_diameter = 3.0
mounting_hole_edge_offset = 2.4
mounting_hole_x = pcb_length / 2.0 - mounting_hole_edge_offset
mounting_hole_y = pcb_width / 2.0 - mounting_hole_edge_offset

transducer_diameter = 16.4
transducer_radius = transducer_diameter / 2.0
transducer_height_z = 12.4
transducer_pitch_y = 21.5
transducer_center_x = 0.0
transducer_center_y_offset = transducer_pitch_y / 2.0
transducer_base_z = pcb_thickness

pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

mounting_hole_points = [
    (-mounting_hole_x, -mounting_hole_y),
    (-mounting_hole_x, mounting_hole_y),
    (mounting_hole_x, -mounting_hole_y),
    (mounting_hole_x, mounting_hole_y),
]

pcb = (
    pcb.faces(">Z")
    .workplane()
    .pushPoints(mounting_hole_points)
    .hole(mounting_hole_diameter)
)

connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

transducer_a = (
    cq.Workplane("XY")
    .circle(transducer_radius)
    .extrude(transducer_height_z)
    .translate((transducer_center_x, -transducer_center_y_offset, transducer_base_z))
)

transducer_b = (
    cq.Workplane("XY")
    .circle(transducer_radius)
    .extrude(transducer_height_z)
    .translate((transducer_center_x, transducer_center_y_offset, transducer_base_z))
)

result = pcb.union(connector).union(transducer_a).union(transducer_b)
show_object(result, name="超声波测距传感器")
