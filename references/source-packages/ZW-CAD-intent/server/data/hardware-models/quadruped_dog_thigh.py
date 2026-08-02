import cadquery as cq

# 8 舵机机器狗大腿参考母版。
# 坐标：结构件中心为原点；X 为大腿长度，Y 为宽度，Z 为高度。
# 模型包含两个舵盘固定孔和一个膝关节贯穿孔，三种孔的轴线均沿 Y。
hardware_name = "8 舵机机器狗大腿"

# 参数区，单位：mm。
thigh_length_x = 60.0
thigh_width_y = 15.0
thigh_height_z = 18.0

servo_horn_hole_diameter = 1.5
servo_horn_hole_x = -21.0
servo_horn_hole_z_positions = (-6.8, 6.8)

knee_hole_diameter = 3.0
knee_hole_x = 25.0
knee_hole_z = 0.0


def make_axis_y_cutter(diameter, length_y):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(length_y)
        .rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 90.0)
    )


def make_quadruped_dog_thigh():
    thigh = cq.Workplane("XY").box(
        thigh_length_x,
        thigh_width_y,
        thigh_height_z,
        centered=(True, True, True),
    )

    cutter_length_y = thigh_width_y + 2.0
    horn_hole = make_axis_y_cutter(servo_horn_hole_diameter, cutter_length_y)
    for center_z in servo_horn_hole_z_positions:
        positioned_hole = horn_hole.translate(
            (servo_horn_hole_x, cutter_length_y / 2.0, center_z)
        )
        thigh = thigh.cut(positioned_hole)

    knee_hole = make_axis_y_cutter(knee_hole_diameter, cutter_length_y).translate(
        (knee_hole_x, cutter_length_y / 2.0, knee_hole_z)
    )
    return thigh.cut(knee_hole)


result = make_quadruped_dog_thigh()

show_object(result, name=hardware_name)
