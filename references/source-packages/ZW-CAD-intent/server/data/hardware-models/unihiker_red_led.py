import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 30mm 长度方向，Y 为 22mm 宽度方向，+Z 为 LED/接口所在正面。
# PCB 位于 z=0 到 z=pcb_thickness，所有元件叠放在 +Z 面。
# 安装意图：默认外表面安装，用户偏好默认前侧面；具体装到哪个外侧面由后续装配参数决定，本模型不做旋转/平移。
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

led_center_x = -3.0
led_center_y = 0.0

led_disc_diameter = 5.6
led_disc_height_z = 1.0

led_cylinder_diameter = 5.0
led_cylinder_height_z = 7.0

led_hemisphere_diameter = 5.0
led_hemisphere_radius = led_hemisphere_diameter / 2

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

# LED 底部圆片：直径 5.6，高 1，位于 PCB +Z 面。
led_disc_z = pcb_thickness
led_disc = (
    cq.Workplane("XY")
    .circle(led_disc_diameter / 2)
    .extrude(led_disc_height_z)
    .translate((led_center_x, led_center_y, led_disc_z))
)

# LED 圆柱：直径 5，高 7，叠放在底部圆片上。
led_cylinder_z = led_disc_z + led_disc_height_z
led_cylinder = (
    cq.Workplane("XY")
    .circle(led_cylinder_diameter / 2)
    .extrude(led_cylinder_height_z)
    .translate((led_center_x, led_center_y, led_cylinder_z))
)

# LED 顶部半球：直径 5，底面位于圆柱顶面。
led_hemisphere_base_z = led_cylinder_z + led_cylinder_height_z
led_sphere = (
    cq.Workplane("XY")
    .sphere(led_hemisphere_radius)
    .translate((led_center_x, led_center_y, led_hemisphere_base_z))
)

hemisphere_keep = (
    cq.Workplane("XY")
    .box(
        led_hemisphere_radius * 2,
        led_hemisphere_radius * 2,
        led_hemisphere_radius,
        centered=(True, True, False),
    )
    .translate((led_center_x, led_center_y, led_hemisphere_base_z))
)

led_hemisphere = led_sphere.intersect(hemisphere_keep)

result = (
    pcb
    .union(connector)
    .union(led_disc)
    .union(led_cylinder)
    .union(led_hemisphere)
)

show_object(result, name="红色LED")
