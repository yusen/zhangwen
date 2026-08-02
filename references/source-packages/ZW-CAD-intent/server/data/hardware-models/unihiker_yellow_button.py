import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 30mm 长度方向，Y 为 22mm 宽度方向，+Z 为按钮/接口所在正面。
# PCB 位于 z=0 到 z=pcb_thickness，所有元件叠放在 +Z 面。
# =========================
pcb_length = 30.0
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 2.0

mounting_hole_diameter = 3.0
mounting_hole_edge_offset = 3.5
mounting_hole_x = -pcb_length / 2 + mounting_hole_edge_offset
mounting_hole_y = pcb_width / 2 - mounting_hole_edge_offset

connector_length_x = 6.0
connector_width_y = 10.0
connector_height_z = 5.7
connector_center_x = pcb_length / 2 - connector_length_x / 2
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2

button_center_x = -3.5
button_center_y = 0.0

button_base_length_x = 12.0
button_base_width_y = 12.0
button_base_height_z = 3.0

small_cylinder_diameter = 5.5
small_cylinder_height_z = 3.0

cap_disc_diameter = 13.0
cap_disc_height_z = 1.2

cap_cylinder_diameter = 11.7
cap_cylinder_height_z = 4.5

# PCB 主体。
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

# 两个靠近 -X 边的 M3 固定孔，孔中心距相邻板边 3.5mm。
for hole_y in (-mounting_hole_y, mounting_hole_y):
    pcb = (
        pcb.faces(">Z")
        .workplane()
        .pushPoints([(mounting_hole_x, hole_y)])
        .hole(mounting_hole_diameter)
    )

# +X 边接线口：6 x 10 x 5.7，+X 外边与 PCB +X 外边齐平，整体位于 PCB 上。
connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

# 按钮底部长方体：12 x 12 x 3，中心位于 x=-3.5。
button_base = (
    cq.Workplane("XY")
    .box(button_base_length_x, button_base_width_y, button_base_height_z, centered=(True, True, False))
    .translate((button_center_x, button_center_y, pcb_thickness))
)

# 小圆柱体：直径 5.5，高 3，叠放在按钮底部长方体上。
small_cylinder_z = pcb_thickness + button_base_height_z
small_cylinder = (
    cq.Workplane("XY")
    .circle(small_cylinder_diameter / 2)
    .extrude(small_cylinder_height_z)
    .translate((button_center_x, button_center_y, small_cylinder_z))
)

# 按键帽薄圆片：直径 13，高 1.2，位于小圆柱上方。
cap_disc_z = small_cylinder_z + small_cylinder_height_z
cap_disc = (
    cq.Workplane("XY")
    .circle(cap_disc_diameter / 2)
    .extrude(cap_disc_height_z)
    .translate((button_center_x, button_center_y, cap_disc_z))
)

# 按键帽上方圆柱：直径 11.7，高 4.5，位于薄圆片上方。
cap_cylinder_z = cap_disc_z + cap_disc_height_z
cap_cylinder = (
    cq.Workplane("XY")
    .circle(cap_cylinder_diameter / 2)
    .extrude(cap_cylinder_height_z)
    .translate((button_center_x, button_center_y, cap_cylinder_z))
)

result = (
    pcb
    .union(connector)
    .union(button_base)
    .union(small_cylinder)
    .union(cap_disc)
    .union(cap_cylinder)
)

show_object(result, name="黄色按钮")
