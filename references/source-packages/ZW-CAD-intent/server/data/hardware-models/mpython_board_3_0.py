import cadquery as cq

# =========================
# 参数区，单位：mm
# 坐标：PCB 中心为原点，X 为 51.8mm 长边方向，
# Y 为 47.4mm 短边方向，+Z 为显示屏正面
# =========================

pcb_length = 51.8
pcb_width = 47.4
pcb_thickness = 1.6
pcb_corner_radius = 3.5

# 上方两处直径 3mm 安装孔
mounting_hole_diameter = 3.0
mounting_hole_points = [
    (-12.0, 18.2),
    (12.0, 18.2),
]

# 显示屏外框
display_frame_length = 35.3
display_frame_width = 24.2
display_frame_thickness = 2.9

display_frame_top_margin = 8.8
display_frame_center_x = 0.0
display_frame_center_y = (
    pcb_width / 2.0
    - display_frame_top_margin
    - display_frame_width / 2.0
)

# 显示有效区域
display_active_length = 30.2
display_active_width = 15.5
display_active_top_margin = 2.5

display_active_center_x = 0.0
display_active_center_y = (
    display_frame_center_y
    + display_frame_width / 2.0
    - display_active_top_margin
    - display_active_width / 2.0
)

# 有效显示区域顶部相对外框顶部下沉 0.2mm
display_active_recess_depth = 0.2
display_active_marker_thickness = 0.05
display_active_cutter_extra = 0.02

# A/B 按钮
button_length_x = 6.2
button_width_y = 2.7
button_height_z = 3.4

# 按钮 +Y 面与 PCB +Y 面重合
button_center_y = pcb_width / 2.0 - button_width_y / 2.0

button_centers = [
    (-19.7, button_center_y),
    (19.7, button_center_y),
]

# 按钮 +Z 面比 PCB +Z 面高 0.5mm
button_top_offset_from_pcb = 0.5
button_top_z = pcb_thickness + button_top_offset_from_pcb
button_z_min = button_top_z - button_height_z

# 两个按键柱
key_length_x = 2.5
key_width_y = 1.0
key_height_z = 2.0

# 按键的 -Y 面贴合按钮主体的 +Y 面，并沿 +Y 方向伸出
button_positive_y_face = button_center_y + button_width_y / 2.0
button_center_z = (button_z_min + button_top_z) / 2.0
key_center_y = button_positive_y_face + key_width_y / 2.0
key_z_min = button_center_z - key_height_z / 2.0


# =========================
# 建模辅助函数
# =========================

def rounded_plate(length_x, width_y, height_z, corner_radius, z_min):
    return (
        cq.Workplane("XY")
        .box(
            length_x,
            width_y,
            height_z,
            centered=(True, True, False),
        )
        .edges("|Z")
        .fillet(corner_radius)
        .translate((0.0, 0.0, z_min))
    )


def box_from_z(length_x, width_y, height_z, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .box(
            length_x,
            width_y,
            height_z,
            centered=(True, True, False),
        )
        .translate((center_x, center_y, z_min))
    )


def cylinder_from_z(diameter, height_z, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(height_z)
        .translate((center_x, center_y, z_min))
    )


# =========================
# PCB 外形与安装孔
# =========================

pcb = rounded_plate(
    pcb_length,
    pcb_width,
    pcb_thickness,
    pcb_corner_radius,
    0.0,
)

hole_cutter_height = pcb_thickness + 0.4
hole_cutter_z_min = -0.2

for hole_x, hole_y in mounting_hole_points:
    hole_cutter = cylinder_from_z(
        mounting_hole_diameter,
        hole_cutter_height,
        hole_x,
        hole_y,
        hole_cutter_z_min,
    )
    pcb = pcb.cut(hole_cutter)


# =========================
# +Z 面显示屏
# =========================

display_frame_z_min = pcb_thickness
display_frame_top_z = (
    display_frame_z_min + display_frame_thickness
)

display_frame = box_from_z(
    display_frame_length,
    display_frame_width,
    display_frame_thickness,
    display_frame_center_x,
    display_frame_center_y,
    display_frame_z_min,
)

# 从外框顶部向下切出 0.2mm 显示区域凹槽
display_active_surface_z = (
    display_frame_top_z - display_active_recess_depth
)

display_active_recess_cutter = box_from_z(
    display_active_length,
    display_active_width,
    display_active_recess_depth + display_active_cutter_extra,
    display_active_center_x,
    display_active_center_y,
    display_active_surface_z,
)

display_frame = display_frame.cut(
    display_active_recess_cutter
)

# 显示区域表面位于凹槽底部
display_active_area = box_from_z(
    display_active_length,
    display_active_width,
    display_active_marker_thickness,
    display_active_center_x,
    display_active_center_y,
    display_active_surface_z - display_active_marker_thickness,
)


# =========================
# A/B 按钮
# =========================

buttons = []

for button_x, button_y in button_centers:
    # 按钮底部进入 PCB 内部，顶部高出 PCB 0.5mm
    button = box_from_z(
        button_length_x,
        button_width_y,
        button_height_z,
        button_x,
        button_y,
        button_z_min,
    )
    buttons.append(button)


# =========================
# A/B 按键柱
# =========================

keys = []

for key_x, _ in button_centers:
    # 在按钮主体 +Y 面中心作 2.5 x 2mm 的 XZ 轮廓，沿 +Y 拉伸 1mm
    key = box_from_z(
        key_length_x,
        key_width_y,
        key_height_z,
        key_x,
        key_center_y,
        key_z_min,
    )
    keys.append(key)


# =========================
# 合并结果
# =========================

result = (
    pcb
    .union(display_frame)
    .union(display_active_area)
)

for button in buttons:
    result = result.union(button)

for key in keys:
    result = result.union(key)


show_object(result, name="掌控板3.0")
