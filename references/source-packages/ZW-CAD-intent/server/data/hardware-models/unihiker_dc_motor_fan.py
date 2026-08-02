import cadquery as cq

# =========================
# 参数区，单位：mm
# =========================
hardware_name = "直流电机风扇"

# PCB
pcb_length = 52.0
pcb_width = 22.0
pcb_thickness = 1.0
pcb_corner_radius = 2.5

# 接线口：+X 边与 PCB +X 边对齐，位于中间
connector_length = 4.7
connector_width = 8.0
connector_height = 6.0
connector_center_x = pcb_length / 2 - connector_length / 2
connector_center_y = 0.0

# 固定孔：四角，孔心距相邻边 4.8mm
mount_hole_diameter = 3.0
mount_hole_edge_offset = 4.8
mount_hole_x = pcb_length / 2 - mount_hole_edge_offset
mount_hole_y = pcb_width / 2 - mount_hole_edge_offset

# 电机主体：X 方向 27，Y 方向 22，高 17
motor_length = 27.0
motor_width = 22.0
motor_height = 17.0
motor_center_x = 0.0
motor_center_y = 0.0
motor_center_z = pcb_thickness + motor_height / 2
motor_minus_y_face = motor_center_y - motor_width / 2
motor_axis_z = motor_center_z

# -Y 面圆柱座
front_cylinder_diameter = 6.0
front_cylinder_length = 1.5

# 输出轴
shaft_diameter = 2.0
shaft_length = 4.0

# 风扇扇叶中心圆柱
fan_hub_diameter = 24.0
fan_hub_length = 11.5
fan_hub_fillet = 2.0


# =========================
# 建模函数
# =========================
def rounded_pcb(length, width, thickness, radius):
    return (
        cq.Workplane("XY")
        .box(length, width, thickness, centered=(True, True, False))
        .edges("|Z")
        .fillet(radius)
    )


def cylinder_along_minus_y(diameter, length, x, y_start, z, fillet_radius=0.0):
    # 先沿 Z 轴拉伸，再绕 X 轴旋转 90 度，让圆柱朝 -Y 方向伸出。
    shape = cq.Workplane("XY").circle(diameter / 2).extrude(length)
    if fillet_radius > 0:
        shape = shape.edges().fillet(fillet_radius)
    return shape.rotate((0, 0, 0), (1, 0, 0), 90).translate((x, y_start, z))


# =========================
# PCB 与固定孔
# =========================
pcb = rounded_pcb(
    pcb_length,
    pcb_width,
    pcb_thickness,
    pcb_corner_radius,
)

mount_holes = [
    (-mount_hole_x, -mount_hole_y),
    (-mount_hole_x, mount_hole_y),
    (mount_hole_x, -mount_hole_y),
    (mount_hole_x, mount_hole_y),
]

for hx, hy in mount_holes:
    cutter = (
        cq.Workplane("XY")
        .center(hx, hy)
        .circle(mount_hole_diameter / 2)
        .extrude(pcb_thickness + 0.6)
        .translate((0, 0, -0.3))
    )
    pcb = pcb.cut(cutter)


# =========================
# PCB +Z 面元件
# =========================
connector = (
    cq.Workplane("XY")
    .box(connector_length, connector_width, connector_height, centered=(True, True, False))
    .translate((connector_center_x, connector_center_y, pcb_thickness))
)

motor_body = (
    cq.Workplane("XY")
    .box(motor_length, motor_width, motor_height, centered=(True, True, True))
    .translate((motor_center_x, motor_center_y, motor_center_z))
)

front_cylinder = cylinder_along_minus_y(
    front_cylinder_diameter,
    front_cylinder_length,
    motor_center_x,
    motor_minus_y_face,
    motor_axis_z,
)

shaft = cylinder_along_minus_y(
    shaft_diameter,
    shaft_length,
    motor_center_x,
    motor_minus_y_face - front_cylinder_length,
    motor_axis_z,
)

fan_hub = cylinder_along_minus_y(
    fan_hub_diameter,
    fan_hub_length,
    motor_center_x,
    motor_minus_y_face - front_cylinder_length - shaft_length,
    motor_axis_z,
    fillet_radius=fan_hub_fillet,
)


# =========================
# 合并结果
# =========================
result = (
    pcb
    .union(connector)
    .union(motor_body)
    .union(front_cylinder)
    .union(shaft)
    .union(fan_hub)
)

show_object(result, name=hardware_name)
