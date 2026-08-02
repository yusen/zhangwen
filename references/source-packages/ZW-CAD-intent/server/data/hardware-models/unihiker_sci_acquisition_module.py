import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标规则：
# PCB 中心为原点，X 为 PCB 长边方向，Y 为 PCB 短边方向，+Z 为元件面。
# PCB 位于 z=0 到 z=pcb_thickness。
# 本模型只画 SCI 采集模块硬件本身，不决定最终外壳装配位置。
# =========================
hardware_name = "SCI采集模块"

# PCB
pcb_length = 62.0
pcb_width = 52.0
pcb_thickness = 1.6
pcb_corner_radius = 2.0

# 固定孔：四角，孔径 3mm，孔心距相邻侧边 2.8mm
mount_hole_diameter = 3.0
mount_hole_edge_offset = 2.8
mount_hole_x = pcb_length / 2.0 - mount_hole_edge_offset
mount_hole_y = pcb_width / 2.0 - mount_hole_edge_offset

# 数据线接线座：4 个，均为 6 x 12 x 5.7mm
connector_length_x = 6.0
connector_width_y = 12.0
connector_height_z = 5.7
connector_gap_y = 1.5
connector_center_z = pcb_thickness + connector_height_z / 2.0

# +X 边 1 个接线座：+X 外边与 PCB +X 边齐平，Y 居中
plus_x_connector_center_x = pcb_length / 2.0 - connector_length_x / 2.0
plus_x_connector_center_y = 0.0

# -X 边 3 个接线座：-X 外边与 PCB -X 边齐平，沿 Y 等距排列，整体居中
minus_x_connector_center_x = -pcb_length / 2.0 + connector_length_x / 2.0
minus_x_connector_pitch_y = connector_width_y + connector_gap_y
minus_x_connector_centers_y = [
    -minus_x_connector_pitch_y,
    0.0,
    minus_x_connector_pitch_y,
]

# 显示屏框架：37 x 24 x 2mm，位于 PCB 中心
display_frame_length_x = 37.0
display_frame_width_y = 24.0
display_frame_height_z = 2.0
display_frame_center_x = 0.0
display_frame_center_y = 0.0
display_frame_center_z = pcb_thickness + display_frame_height_z / 2.0

# 显示区域：30 x 18mm，+Y 边距离框架 +Y 边 2mm
# 显示区域厚度未给出，这里用 0.3mm 薄片表示可视区域。
display_area_length_x = 30.0
display_area_width_y = 18.0
display_area_height_z = 0.3
display_area_plus_y_margin = 2.0
display_area_center_x = 0.0
display_area_center_y = (
    display_frame_width_y / 2.0
    - display_area_plus_y_margin
    - display_area_width_y / 2.0
)
display_area_center_z = pcb_thickness + display_frame_height_z + display_area_height_z / 2.0


# =========================
# 建模函数
# =========================
def rounded_box(length, width, height, radius, centered=(True, True, False)):
    part = (
        cq.Workplane("XY")
        .box(length, width, height, centered=centered)
    )
    if radius > 0:
        try:
            part = part.edges("|Z").fillet(radius)
        except Exception:
            pass
    return part


def make_mount_hole_cutter(x, y, diameter, height):
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(diameter / 2.0)
        .extrude(height)
        .translate((0, 0, -0.3))
    )


def make_box(length, width, height, center_x, center_y, center_z):
    return (
        cq.Workplane("XY")
        .box(length, width, height, centered=(True, True, True))
        .translate((center_x, center_y, center_z))
    )


# =========================
# PCB 主体和固定孔
# =========================
pcb = rounded_box(
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
    pcb = pcb.cut(
        make_mount_hole_cutter(
            hx,
            hy,
            mount_hole_diameter,
            pcb_thickness + 0.6,
        )
    )


# =========================
# 数据线接线座
# =========================
plus_x_connector = make_box(
    connector_length_x,
    connector_width_y,
    connector_height_z,
    plus_x_connector_center_x,
    plus_x_connector_center_y,
    connector_center_z,
)

minus_x_connectors = []
for cy in minus_x_connector_centers_y:
    minus_x_connectors.append(
        make_box(
            connector_length_x,
            connector_width_y,
            connector_height_z,
            minus_x_connector_center_x,
            cy,
            connector_center_z,
        )
    )


# =========================
# 显示屏
# =========================
display_frame = make_box(
    display_frame_length_x,
    display_frame_width_y,
    display_frame_height_z,
    display_frame_center_x,
    display_frame_center_y,
    display_frame_center_z,
)

display_area = make_box(
    display_area_length_x,
    display_area_width_y,
    display_area_height_z,
    display_area_center_x,
    display_area_center_y,
    display_area_center_z,
)


# =========================
# 合并结果
# =========================
result = pcb.union(plus_x_connector)

for connector in minus_x_connectors:
    result = result.union(connector)

result = (
    result
    .union(display_frame)
    .union(display_area)
)

show_object(result, name=hardware_name)
