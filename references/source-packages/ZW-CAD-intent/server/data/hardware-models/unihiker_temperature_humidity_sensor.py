import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 32mm 长度方向，Y 为 22mm 宽度方向，+Z 为传感器/接口所在正面。
# PCB 位于 z=0 到 z=pcb_thickness，所有元件叠放在 +Z 面。
# 安装意图：默认外表面安装，用户偏好默认后侧面；具体装到哪个外侧面由后续装配参数决定，本模型不做旋转/平移。
# =========================
pcb_length = 32.0
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 2.0

mounting_hole_diameter = 3.0
mounting_hole_x = 4.5
mounting_hole_y = pcb_width / 2 - 3.5

connector_length_x = 6.0
connector_width_y = 10.0
connector_height_z = 5.7
connector_center_x = pcb_length / 2 - connector_length_x / 2
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2

sensor_length_x = 15.7
sensor_width_y = 12.5
sensor_height_z = 6.0
sensor_center_x = -pcb_length / 2 + sensor_length_x / 2
sensor_center_y = 0.0
sensor_center_z = pcb_thickness + sensor_height_z / 2

# PCB 主体，位于 z=0 到 z=pcb_thickness。
pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

# 两个 M3 固定孔：关于 X 轴对称，位于 x=4.5，孔中心距 Y 边 3.5mm。
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

# 温湿度传感器主体：15.7 x 12.5 x 6，-X 边与 PCB -X 边重合，整体位于 PCB 上。
sensor_body = (
    cq.Workplane("XY")
    .box(sensor_length_x, sensor_width_y, sensor_height_z, centered=(True, True, True))
    .translate((sensor_center_x, sensor_center_y, sensor_center_z))
)

result = pcb.union(connector).union(sensor_body)

show_object(result, name="温湿度传感器")
