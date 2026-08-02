import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：
# 主体中心为原点，X 为水泵长度方向，Y/Z 为圆柱截面方向。
# +X 端面：吸水口
# +Z 上侧：出水口，靠近 +X 端
# -X 端面：电源线凸起
# 本模型只画水泵硬件本身，不决定最终外壳装配位置。
# 外壳规则备注：使用此硬件时，盒子右侧面默认开直径 12mm 的水泵电源线通道。
# =========================
hardware_name = "直流水泵"

# 主体圆柱
body_diameter = 25.0
body_radius = body_diameter / 2.0
body_length = 45.0

# +X 吸水口：直径 5mm，长 10mm
inlet_diameter = 5.0
inlet_radius = inlet_diameter / 2.0
inlet_length = 10.0

# +Z 出水口：直径 5mm，长 10mm
# 出水口中心距主体 +X 端面 7.5mm。
outlet_diameter = 5.0
outlet_radius = outlet_diameter / 2.0
outlet_length = 10.0
outlet_center_x = body_length / 2.0 - 7.5
outlet_center_y = 0.0
outlet_embed_depth = 1.0

# -X 电源线凸起：直径 2mm，凸出 0.5mm
wire_bump_diameter = 2.0
wire_bump_radius = wire_bump_diameter / 2.0
wire_bump_height = 0.5

# 外壳开孔信息，仅作为硬件 profile 后续使用，不在硬件本体中建模
enclosure_cable_opening_diameter = 12.0


# =========================
# 建模
# =========================

# 主体：沿 X 轴的圆柱，范围 x=-22.5 到 x=+22.5
body = (
    cq.Workplane("YZ")
    .circle(body_radius)
    .extrude(body_length)
    .translate((-body_length / 2.0, 0, 0))
)

# 吸水口：从 +X 端面中心向 +X 方向伸出
inlet = (
    cq.Workplane("YZ")
    .circle(inlet_radius)
    .extrude(inlet_length)
    .translate((body_length / 2.0, 0, 0))
)

# 出水口：在主体上侧靠近 +X 端，向 +Z 方向伸出。
# 加 1mm 嵌入深度，保证与主体可靠相交并 union 成一体。
outlet = (
    cq.Workplane("XY")
    .center(outlet_center_x, outlet_center_y)
    .circle(outlet_radius)
    .extrude(outlet_length + outlet_embed_depth)
    .translate((0, 0, body_radius - outlet_embed_depth))
)

# 电源线凸起：位于 -X 端面中心，向 -X 方向凸出
wire_bump = (
    cq.Workplane("YZ")
    .circle(wire_bump_radius)
    .extrude(wire_bump_height)
    .translate((-body_length / 2.0 - wire_bump_height, 0, 0))
)

# 合并结果
result = (
    body
    .union(inlet)
    .union(outlet)
    .union(wire_bump)
)

show_object(result, name=hardware_name)
