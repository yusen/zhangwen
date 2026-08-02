import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 30mm 长度方向，Y 为 22mm 宽度方向，+Z 为传感器/接口正面。
# =========================
pcb_length = 30.0
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 4.0

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

sensor_diameter = 5.0
sensor_height_z = 2.7
sensor_center_x = -4.0
sensor_center_y = 0.0
sensor_center_z = pcb_thickness + sensor_height_z / 2

# PCB 主体，位于 z=0 到 z=pcb_thickness。
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

# 光线传感器主体：直径 5mm、厚 2.7mm 的圆柱体，中心 x=-4mm。
sensor_body = (
    cq.Workplane("XY")
    .circle(sensor_diameter / 2)
    .extrude(sensor_height_z)
    .translate((sensor_center_x, sensor_center_y, pcb_thickness))
)

result = pcb.union(connector).union(sensor_body)
show_object(result, name="光线传感器")
