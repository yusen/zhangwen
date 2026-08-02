import cadquery as cq

# 行空板聚合物锂电池参考模型。
# 坐标：电池本体中心位于 X/Y 原点，底面 z=0，+X 为电源输出线占位方向。
# 本文件只描述硬件本体；三边卡槽和外部固定口袋属于外壳固定结构，由 profile 记录。
hardware_name = "行空板聚合物锂电池"

# =========================
# 参数区，单位：mm
# =========================
battery_length_x = 48.0
battery_width_y = 32.0
battery_thickness_z = 6.0
corner_radius = 2.0

wire_stub_length_x = 1.0
wire_stub_diameter = 0.8
wire_stub_spacing_y = 3.0
wire_stub_center_z = battery_thickness_z / 2.0


def make_battery_body():
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


def make_wire_stub(center_y):
    return (
        cq.Workplane("YZ")
        .center(center_y, wire_stub_center_z)
        .circle(wire_stub_diameter / 2.0)
        .extrude(wire_stub_length_x)
        .translate((battery_length_x / 2.0, 0, 0))
    )


def make_unihiker_polymer_lipo_battery():
    body = make_battery_body()
    positive_stub = make_wire_stub(wire_stub_spacing_y / 2.0)
    negative_stub = make_wire_stub(-wire_stub_spacing_y / 2.0)
    return body.union(positive_stub).union(negative_stub)


result = make_unihiker_polymer_lipo_battery()

show_object(result, name=hardware_name)
