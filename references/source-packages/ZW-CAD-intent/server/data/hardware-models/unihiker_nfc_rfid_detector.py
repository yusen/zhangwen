import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 110mm 长度方向，Y 为 50mm 宽度方向，+Z 为正面。
# =========================
pcb_length = 110.0
pcb_width = 50.0
pcb_thickness = 1.6
pcb_corner_radius = 4.0

mounting_hole_diameter = 3.0
mounting_hole_edge_offset = 4.8
mounting_hole_x = pcb_length / 2 - mounting_hole_edge_offset
mounting_hole_y = pcb_width / 2 - mounting_hole_edge_offset

connector_length_x = 6.0
connector_width_y = 12.0
connector_height_z = 5.7
connector_center_x = pcb_length / 2 - connector_length_x / 2
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2

coil_length_x = 47.0
coil_width_y = 40.0
coil_center_x = -15.0
coil_center_y = 0.0
coil_height_z = 0.18

# PCB 主体，位于 z=0 到 z=pcb_thickness。
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

# 四角 M3 固定孔，孔中心距相邻板边 4.8mm。
for hole_x in (-mounting_hole_x, mounting_hole_x):
    for hole_y in (-mounting_hole_y, mounting_hole_y):
        pcb = (
            pcb.faces(">Z")
            .workplane()
            .pushPoints([(hole_x, hole_y)])
            .hole(mounting_hole_diameter)
        )

# NFC 线圈区域：按用户要求用单块区域表达，不画多圈线。
coil_area = (
    cq.Workplane("XY")
    .box(coil_length_x, coil_width_y, coil_height_z, centered=(True, True, False))
    .translate((coil_center_x, coil_center_y, pcb_thickness + 0.02))
)

# +X 边接线口：6 x 12 x 5.7，+X 外边与 PCB +X 外边齐平。
connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

result = pcb.union(coil_area).union(connector)
show_object(result, name="NFC近场通讯模块")
