import cadquery as cq

# 方形锂电池参考模型。
# 坐标：电池本体中心位于 X/Y 原点；Z=0 是底面，+X 是电源线伸出方向。
# 本文件只描述硬件自身；三面卡槽属于外壳固定结构，由 profile 记录。
hardware_name = "方形锂电池"

# =========================
# 参数区，单位：mm
# =========================
battery_length_x = 21.0
battery_width_y = 15.0
battery_thickness_z = 4.0
corner_radius = 1.0

wire_length_x = 25.0
wire_diameter = 0.8
wire_spacing_y = 3.0
wire_center_z = battery_thickness_z / 2.0


def rounded_battery_body():
    body = cq.Workplane("XY").box(
        battery_length_x,
        battery_width_y,
        battery_thickness_z,
        centered=(True, True, False),
    )
    try:
        body = body.edges("|Z").fillet(corner_radius)
    except Exception:
        pass
    return body


def make_wire(center_y):
    return (
        cq.Workplane("YZ")
        .center(center_y, wire_center_z)
        .circle(wire_diameter / 2.0)
        .extrude(wire_length_x)
        .translate((battery_length_x / 2.0, 0, 0))
    )


def make_compact_lipo_battery():
    body = rounded_battery_body()
    positive_wire = make_wire(wire_spacing_y / 2.0)
    negative_wire = make_wire(-wire_spacing_y / 2.0)
    return body.union(positive_wire).union(negative_wire)


result = make_compact_lipo_battery()

show_object(result, name=hardware_name)
