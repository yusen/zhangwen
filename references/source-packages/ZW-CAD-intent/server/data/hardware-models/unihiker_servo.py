import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：舵机主体 XY 中心为原点，X 为主体长度方向，Y 为主体宽度方向，+Z 为输出轴所在顶面。
# 主体位于 z=0 到 z=body_height_z。
# 安装意图：舵机由外向内插入盒体；固定耳 -Z 面与盒子外表面重合。
# 本模型只描述舵机自身，不做最终外壳装配旋转/平移。
# =========================
body_length_x = 22.6
body_width_y = 12.0
body_height_z = 23.0

lug_extension_x = 5.0
lug_width_y = body_width_y
lug_thickness_z = 2.4
lug_minus_z_from_body_bottom = 16.0
lug_center_z = lug_minus_z_from_body_bottom + lug_thickness_z / 2.0
lug_center_x = body_length_x / 2.0 + lug_extension_x / 2.0

lug_hole_diameter = 2.0
lug_hole_radius = lug_hole_diameter / 2.0

large_cylinder_diameter = 12.0
large_cylinder_radius = large_cylinder_diameter / 2.0
large_cylinder_height_z = 4.0
large_cylinder_center_x = body_length_x / 2.0 - large_cylinder_radius
large_cylinder_center_y = 0.0

small_cylinder_diameter = 4.5
small_cylinder_radius = small_cylinder_diameter / 2.0
small_cylinder_height_z = 4.0
small_cylinder_center_x = 0.0
small_cylinder_center_y = 0.0

output_shaft_diameter = 5.0
output_shaft_radius = output_shaft_diameter / 2.0
output_shaft_height_z = 4.5
output_shaft_center_x = large_cylinder_center_x
output_shaft_center_y = large_cylinder_center_y

# 出线口尺寸未给出：这里用保守默认凹槽表示，可按实测修改。
wire_port_length_x = 2.0
wire_port_width_y = 6.0
wire_port_depth_z = 1.2
wire_port_center_x = body_length_x / 2.0 - wire_port_length_x / 2.0
wire_port_center_y = 0.0
wire_port_center_z = wire_port_depth_z / 2.0

# 舵机主体：22.6 x 12 x 23mm。
body = (
    cq.Workplane("XY")
    .box(body_length_x, body_width_y, body_height_z, centered=(True, True, False))
)

# -Z 面 +X 边线附近的出线口，用一个浅凹槽表达。
wire_port_cut = (
    cq.Workplane("XY")
    .box(wire_port_length_x, wire_port_width_y, wire_port_depth_z, centered=(True, True, True))
    .translate((wire_port_center_x, wire_port_center_y, wire_port_center_z))
)
body = body.cut(wire_port_cut)

# 两个固定耳：位于主体 +/-X 面，分别向外突出 5mm，厚度 2.4mm。
lug_minus_x = (
    cq.Workplane("XY")
    .box(lug_extension_x, lug_width_y, lug_thickness_z, centered=(True, True, True))
    .translate((-lug_center_x, 0.0, lug_center_z))
)

lug_plus_x = (
    cq.Workplane("XY")
    .box(lug_extension_x, lug_width_y, lug_thickness_z, centered=(True, True, True))
    .translate((lug_center_x, 0.0, lug_center_z))
)

lugs = lug_minus_x.union(lug_plus_x)

# 固定耳中心孔：每个固定耳中心有一个直径 2mm 通孔，孔轴沿 Z 方向。
for hole_x in (-lug_center_x, lug_center_x):
    lug_hole_cut = (
        cq.Workplane("XY")
        .circle(lug_hole_radius)
        .extrude(lug_thickness_z + 1.0)
        .translate((hole_x, 0.0, lug_minus_z_from_body_bottom - 0.5))
    )
    lugs = lugs.cut(lug_hole_cut)

# 主体 +Z 面的大圆柱：D12 x 4mm，与主体 +X 面相切，圆心位于 X 轴上。
large_cylinder = (
    cq.Workplane("XY")
    .circle(large_cylinder_radius)
    .extrude(large_cylinder_height_z)
    .translate((large_cylinder_center_x, large_cylinder_center_y, body_height_z))
)

# 主体 +Z 面中心的小圆柱：D4.5 x 4mm。
small_cylinder = (
    cq.Workplane("XY")
    .circle(small_cylinder_radius)
    .extrude(small_cylinder_height_z)
    .translate((small_cylinder_center_x, small_cylinder_center_y, body_height_z))
)

# 输出轴：位于大圆柱中心，D5 x 4.5mm，叠放在大圆柱上方。
output_shaft = (
    cq.Workplane("XY")
    .circle(output_shaft_radius)
    .extrude(output_shaft_height_z)
    .translate((
        output_shaft_center_x,
        output_shaft_center_y,
        body_height_z + large_cylinder_height_z,
    ))
)

result = (
    body
    .union(lugs)
    .union(large_cylinder)
    .union(small_cylinder)
    .union(output_shaft)
)

show_object(result, name="舵机")
