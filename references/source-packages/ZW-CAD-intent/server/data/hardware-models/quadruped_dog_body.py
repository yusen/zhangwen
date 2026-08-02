import cadquery as cq

# 8 舵机机器狗身体参考母版。
# 坐标：结构件中心为原点；X 为机身长度，Y 为机身宽度，+Z 为顶部开口方向。
# 模型包含空心主体、与顶部齐平的卡槽盖、四个舵机穿墙窗口和八个固定孔。
hardware_name = "8 舵机机器狗身体"

# 主体尺寸，单位：mm。
body_length_x = 155.0
body_width_y = 100.0
body_height_z = 55.0
wall_thickness = 1.5

# 卡槽盖参数。
lid_thickness = 1.5
lid_clearance = 0.4
slot_lip_width = 2.0
slot_lip_height = 1.5

# MG90S 穿墙窗口和固定孔参数。
servo_mount_center_x = 59.85
servo_mount_center_z = -20.1
servo_window_length_x = 24.3
servo_window_depth_y = 3.5
servo_window_height_z = 13.8
servo_screw_hole_diameter = 2.2
servo_screw_hole_x_positions = (-73.5, -46.2, 46.2, 73.5)


def make_axis_y_cutter(diameter, length_y):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(length_y)
        .rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 90.0)
    )


def make_open_body_shell():
    outer = cq.Workplane("XY").box(
        body_length_x,
        body_width_y,
        body_height_z,
        centered=(True, True, True),
    )

    inner_length_x = body_length_x - 2.0 * wall_thickness
    inner_width_y = body_width_y - 2.0 * wall_thickness
    inner_height_z = body_height_z - wall_thickness
    inner_bottom_z = -body_height_z / 2.0 + wall_thickness
    cavity = (
        cq.Workplane("XY")
        .box(
            inner_length_x,
            inner_width_y,
            inner_height_z + wall_thickness,
            centered=(True, True, False),
        )
        .translate((0.0, 0.0, inner_bottom_z))
    )
    shell = outer.cut(cavity)

    for center_x in (-servo_mount_center_x, servo_mount_center_x):
        for side_y in (-body_width_y / 2.0, body_width_y / 2.0):
            window = (
                cq.Workplane("XY")
                .box(
                    servo_window_length_x,
                    servo_window_depth_y,
                    servo_window_height_z,
                    centered=(True, True, True),
                )
                .translate((center_x, side_y, servo_mount_center_z))
            )
            shell = shell.cut(window)

    hole_length_y = body_width_y + 4.0
    hole_cutter = make_axis_y_cutter(servo_screw_hole_diameter, hole_length_y)
    for hole_x in servo_screw_hole_x_positions:
        positioned_hole = hole_cutter.translate(
            (hole_x, hole_length_y / 2.0, servo_mount_center_z)
        )
        shell = shell.cut(positioned_hole)

    return shell


def make_slot_lid():
    lid_length_x = body_length_x - 2.0 * lid_clearance
    lid_width_y = body_width_y - 2.0 * lid_clearance
    lid_center_z = body_height_z / 2.0 - lid_thickness / 2.0
    lid = (
        cq.Workplane("XY")
        .box(
            lid_length_x,
            lid_width_y,
            lid_thickness,
            centered=(True, True, True),
        )
        .translate((0.0, 0.0, lid_center_z))
    )

    lip_center_z = body_height_z / 2.0 - lid_thickness - slot_lip_height / 2.0
    lip_length_x = body_length_x - 2.0 * (wall_thickness + lid_clearance)
    lip_width_y = body_width_y - 2.0 * (wall_thickness + lid_clearance)
    long_lip_center_y = lip_width_y / 2.0 - slot_lip_width / 2.0
    short_lip_center_x = lip_length_x / 2.0 - slot_lip_width / 2.0

    plus_y_lip = (
        cq.Workplane("XY")
        .box(
            lip_length_x,
            slot_lip_width,
            slot_lip_height,
            centered=(True, True, True),
        )
        .translate((0.0, long_lip_center_y, lip_center_z))
    )
    minus_y_lip = plus_y_lip.translate((0.0, -2.0 * long_lip_center_y, 0.0))
    plus_x_lip = (
        cq.Workplane("XY")
        .box(
            slot_lip_width,
            lip_width_y,
            slot_lip_height,
            centered=(True, True, True),
        )
        .translate((short_lip_center_x, 0.0, lip_center_z))
    )
    minus_x_lip = plus_x_lip.translate((-2.0 * short_lip_center_x, 0.0, 0.0))

    return (
        lid
        .union(plus_y_lip)
        .union(minus_y_lip)
        .union(plus_x_lip)
        .union(minus_x_lip)
    )


def make_quadruped_dog_body():
    shell = make_open_body_shell()
    lid = make_slot_lid()
    return shell.union(lid)


result = make_quadruped_dog_body()

show_object(result, name=hardware_name)
