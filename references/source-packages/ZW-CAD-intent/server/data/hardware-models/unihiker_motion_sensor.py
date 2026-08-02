import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：PCB 中心为原点，X 为 30mm 长度方向，Y 为 22mm 宽度方向，+Z 为接口所在正面。
# 运动传感器主体按用户确认：朝 +X 侧伸出，轴线沿 X，Y/Z 居中。
# =========================
pcb_length = 30.0
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 2.0

mounting_hole_diameter = 3.0
mounting_hole_x = 4.5
mounting_hole_y = pcb_width / 2 - 3.5

connector_length_x = 6.0
connector_width_y = 10.0
connector_height_z = 5.7
connector_center_x = -pcb_length / 2 + connector_length_x / 2
connector_center_y = 0.0
connector_center_z = pcb_thickness + connector_height_z / 2

sensor_axis_y = 0.0
sensor_axis_z = pcb_thickness / 2

disc_diameter = 11.7
disc_thickness_x = 1.0
sensor_embed_x = 3.5
disc_start_x = pcb_length / 2 - sensor_embed_x

cylinder_diameter = 9.5
cylinder_length_x = 5.0
cylinder_start_x = disc_start_x + disc_thickness_x

hemisphere_diameter = 9.5
hemisphere_radius = hemisphere_diameter / 2
hemisphere_base_x = cylinder_start_x + cylinder_length_x

pcb = (
    cq.Workplane("XY")
    .box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    .edges("|Z")
    .fillet(pcb_corner_radius)
)

for hole_y in (-mounting_hole_y, mounting_hole_y):
    pcb = (
        pcb.faces(">Z")
        .workplane()
        .pushPoints([(mounting_hole_x, hole_y)])
        .hole(mounting_hole_diameter)
    )

connector = (
    cq.Workplane("XY")
    .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
    .translate((connector_center_x, connector_center_y, connector_center_z))
)

sensor_disc = (
    cq.Workplane("YZ")
    .circle(disc_diameter / 2)
    .extrude(disc_thickness_x)
    .translate((disc_start_x, sensor_axis_y, sensor_axis_z))
)

sensor_cylinder = (
    cq.Workplane("YZ")
    .circle(cylinder_diameter / 2)
    .extrude(cylinder_length_x)
    .translate((cylinder_start_x, sensor_axis_y, sensor_axis_z))
)

sphere = (
    cq.Workplane("XY")
    .sphere(hemisphere_radius)
    .translate((hemisphere_base_x, sensor_axis_y, sensor_axis_z))
)

hemisphere_keep = (
    cq.Workplane("XY")
    .box(
        hemisphere_radius,
        hemisphere_radius * 2,
        hemisphere_radius * 2,
        centered=(False, True, True),
    )
    .translate((hemisphere_base_x, sensor_axis_y, sensor_axis_z))
)

sensor_hemisphere = sphere.intersect(hemisphere_keep)

result = (
    pcb
    .union(connector)
    .union(sensor_disc)
    .union(sensor_cylinder)
    .union(sensor_hemisphere)
)

show_object(result, name="运动传感器")
