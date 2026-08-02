import cadquery as cq

# 单节 18650 电池座的简化参考母版。
# 坐标：托盘中心位于 X/Y 原点；Z=0 是落在安装面上的底面，+Z 是开口方向。
# 该模型只表达 77 x 21 x 21 mm 的开口托盘，不包含电池、触点或导线。
# 这是非制造级母版，制造前需要按实物电池和装配余量校准。
hardware_name = "18650 电池座（简化参考）"

# 参数区，单位：mm。
holder_length_x = 77.0
holder_width_y = 21.0
holder_height_z = 21.0
wall_thickness = 2.0
corner_radius = 1.0


def make_rounded_plate(length_x, width_y, height_z):
    plate = cq.Workplane("XY").box(
        length_x,
        width_y,
        height_z,
        centered=(True, True, False),
    )
    try:
        plate = plate.edges("|Z").fillet(corner_radius)
    except Exception:
        pass
    return plate


def make_battery_18650_holder():
    base = make_rounded_plate(holder_length_x, holder_width_y, wall_thickness)

    wall_center_z = holder_height_z / 2.0
    side_wall_center_y = holder_width_y / 2.0 - wall_thickness / 2.0
    end_wall_center_x = holder_length_x / 2.0 - wall_thickness / 2.0

    plus_y_wall = (
        cq.Workplane("XY")
        .box(
            holder_length_x,
            wall_thickness,
            holder_height_z,
            centered=(True, True, True),
        )
        .translate((0.0, side_wall_center_y, wall_center_z))
    )
    minus_y_wall = plus_y_wall.translate((0.0, -2.0 * side_wall_center_y, 0.0))

    plus_x_wall = (
        cq.Workplane("XY")
        .box(
            wall_thickness,
            holder_width_y,
            holder_height_z,
            centered=(True, True, True),
        )
        .translate((end_wall_center_x, 0.0, wall_center_z))
    )
    minus_x_wall = plus_x_wall.translate((-2.0 * end_wall_center_x, 0.0, 0.0))

    return (
        base
        .union(plus_y_wall)
        .union(minus_y_wall)
        .union(plus_x_wall)
        .union(minus_x_wall)
    )


result = make_battery_18650_holder()

show_object(result, name=hardware_name)
