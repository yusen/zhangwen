import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 60mm 长度方向，Y 为 20mm 宽度方向，+Z 为接口所在正面。
# 土壤湿度传感器为外置叉形探针：硬件本体不固定在盒内，盒子只需要为线束开孔。
# =========================
pcb_length = 60.0
pcb_width = 20.0
pcb_thickness = 1.6

slot_length_x = 40.0
slot_width_y = 7.0
slot_round_diameter = 7.0

tip_length_x = 7.0
tip_round_radius = 1.0
right_corner_radius = 1.0

connector_length_x = 6.0
connector_width_y = 10.0
connector_height_z = 5.7

cut_extra_z = 0.6

pcb_half_length = pcb_length / 2
pcb_half_width = pcb_width / 2
slot_radius = slot_round_diameter / 2

slot_start_x = -pcb_half_length
slot_end_x = slot_start_x + slot_length_x
slot_arc_center_x = slot_end_x - slot_radius
slot_rect_length_x = slot_arc_center_x - slot_start_x
slot_rect_center_x = slot_start_x + slot_rect_length_x / 2

tip_base_x = -pcb_half_length + tip_length_x
top_tip_y = (slot_width_y / 2 + pcb_half_width) / 2
bottom_tip_y = -top_tip_y

connector_center_x = pcb_half_length - connector_length_x / 2
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2

# PCB 基础矩形板
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
)

# 中间镂空：从 -X 边开始，总长 40mm，内部端头为直径 7mm 的圆弧
slot_rect_cut = (
    cq.Workplane("XY")
    .box(slot_rect_length_x, slot_width_y, pcb_thickness + cut_extra_z, centered=(True, True, False))
    .translate((slot_rect_center_x, 0, -cut_extra_z / 2))
)

slot_round_cut = (
    cq.Workplane("XY")
    .circle(slot_radius)
    .extrude(pcb_thickness + cut_extra_z)
    .translate((slot_arc_center_x, 0, -cut_extra_z / 2))
)

pcb = pcb.cut(slot_rect_cut.union(slot_round_cut))

# -X 端双倒角，形成两个叉形三角尖端
top_outer_cut = (
    cq.Workplane("XY")
    .polyline([
        (-pcb_half_length, pcb_half_width),
        (-pcb_half_length, top_tip_y),
        (tip_base_x, pcb_half_width),
    ])
    .close()
    .extrude(pcb_thickness + cut_extra_z)
    .translate((0, 0, -cut_extra_z / 2))
)

top_inner_cut = (
    cq.Workplane("XY")
    .polyline([
        (-pcb_half_length, slot_width_y / 2),
        (-pcb_half_length, top_tip_y),
        (tip_base_x, slot_width_y / 2),
    ])
    .close()
    .extrude(pcb_thickness + cut_extra_z)
    .translate((0, 0, -cut_extra_z / 2))
)

bottom_inner_cut = (
    cq.Workplane("XY")
    .polyline([
        (-pcb_half_length, -slot_width_y / 2),
        (-pcb_half_length, bottom_tip_y),
        (tip_base_x, -slot_width_y / 2),
    ])
    .close()
    .extrude(pcb_thickness + cut_extra_z)
    .translate((0, 0, -cut_extra_z / 2))
)

bottom_outer_cut = (
    cq.Workplane("XY")
    .polyline([
        (-pcb_half_length, -pcb_half_width),
        (-pcb_half_length, bottom_tip_y),
        (tip_base_x, -pcb_half_width),
    ])
    .close()
    .extrude(pcb_thickness + cut_extra_z)
    .translate((0, 0, -cut_extra_z / 2))
)

pcb = (
    pcb
    .cut(top_outer_cut)
    .cut(top_inner_cut)
    .cut(bottom_inner_cut)
    .cut(bottom_outer_cut)
)

# +X 面两个外角倒 1mm 圆角，两个叉形末端三角顶点倒 1mm 圆角
pcb = pcb.edges("|Z and >X").fillet(right_corner_radius)
pcb = pcb.edges("|Z and <X").fillet(tip_round_radius)

# +X 边接口，整体完全位于 PCB 上
connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

result = pcb.union(connector)

show_object(result, name="土壤湿度传感器")
