import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 31mm 长度方向，Y 为 22mm 宽度方向，+Z 为旋转角度传感器/接口所在正面。
# PCB 位于 z=0 到 z=pcb_thickness。
# 安装意图：默认外表面安装，用户偏好默认右侧面；具体安装到哪个外侧面由后续装配参数决定，本模型不做旋转/平移。
# =========================
pcb_length = 31.0
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
mounting_hole_edge_offset = 3.5
mounting_hole_x = -pcb_length / 2.0 + mounting_hole_edge_offset
mounting_hole_y = pcb_width / 2.0 - mounting_hole_edge_offset

sensor_center_x = 0.0
sensor_center_y = 0.0

sensor_base_length_x = 11.8
sensor_base_width_y = 9.7
sensor_base_height_z = 7.0

sensor_middle_diameter = 6.0
sensor_middle_height_z = 4.0

sensor_top_diameter = 11.5
sensor_top_height_z = 13.5

# PCB 主体：31 x 22 x 1mm，四角 R2mm。
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

# 两个靠近 -X 边的 M3 固定孔，圆心距相邻板边 3.5mm。
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

# 旋转角度传感器底部长方体：11.8 x 9.7 x 7mm。
sensor_base = (
    cq.Workplane("XY")
    .box(sensor_base_length_x, sensor_base_width_y, sensor_base_height_z, centered=(True, True, False))
    .translate((sensor_center_x, sensor_center_y, pcb_thickness))
)

# 中间圆柱：D6 x 4mm，叠放在底部长方体上。
sensor_middle_z = pcb_thickness + sensor_base_height_z
sensor_middle = (
    cq.Workplane("XY")
    .circle(sensor_middle_diameter / 2.0)
    .extrude(sensor_middle_height_z)
    .translate((sensor_center_x, sensor_center_y, sensor_middle_z))
)

# 顶部旋钮/轴体：D11.5 x 13.5mm，叠放在中间圆柱上。
sensor_top_z = sensor_middle_z + sensor_middle_height_z
sensor_top = (
    cq.Workplane("XY")
    .circle(sensor_top_diameter / 2.0)
    .extrude(sensor_top_height_z)
    .translate((sensor_center_x, sensor_center_y, sensor_top_z))
)

result = (
    pcb
    .union(connector)
    .union(sensor_base)
    .union(sensor_middle)
    .union(sensor_top)
)

show_object(result, name="旋转角度传感器")
