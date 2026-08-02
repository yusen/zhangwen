import cadquery as cq

# 8 舵机机器狗小腿参考母版。
# 坐标：结构件中心为原点；X 为小腿长度，Y 为宽度，Z 为高度；+X 是膝关节端。
# 模型包含远离膝关节一端的圆角和一个沿 Y 方向贯穿的膝关节孔。
hardware_name = "8 舵机机器狗小腿"

# 参数区，单位：mm。
shin_length_x = 50.0
shin_width_y = 12.0
shin_height_z = 10.0
distal_round_radius = 5.0

knee_hole_diameter = 3.0
knee_hole_x = 20.0
knee_hole_z = 0.0


def make_axis_y_cutter(diameter, length_y):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(length_y)
        .rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 90.0)
    )


def make_quadruped_dog_shin():
    distal_arc_center_x = -shin_length_x / 2.0 + distal_round_radius
    proximal_x = shin_length_x / 2.0
    half_height_z = shin_height_z / 2.0
    shin = (
        cq.Workplane("XZ")
        .moveTo(distal_arc_center_x, -half_height_z)
        .lineTo(proximal_x, -half_height_z)
        .lineTo(proximal_x, half_height_z)
        .lineTo(distal_arc_center_x, half_height_z)
        .threePointArc(
            (-shin_length_x / 2.0, 0.0),
            (distal_arc_center_x, -half_height_z),
        )
        .close()
        .extrude(shin_width_y / 2.0, both=True)
    )

    cutter_length_y = shin_width_y + 2.0
    knee_hole = make_axis_y_cutter(knee_hole_diameter, cutter_length_y).translate(
        (knee_hole_x, cutter_length_y / 2.0, knee_hole_z)
    )
    return shin.cut(knee_hole)


result = make_quadruped_dog_shin()

show_object(result, name=hardware_name)
