import cadquery as cq
import math

# ============================================================
# 行空板自动感应开盖智能盒子（CQ-editor 单文件完整代码）
# 单位：mm
#
# 全局坐标：
#   X：盒子左右方向，+X 为右侧
#   Y：盒子两侧方向；本版舵机位于 +Y 侧，超声波位于 -Y 侧
#   Z：竖直方向，+Z 向上
#
# 已确认结构：
#   1. 外尺寸 100 x 80 x 60，壁厚/底厚/盖壁厚均为 2。
#   2. 下盒体高 40，上盖高 20；闭合缝隙 1，默认打开 70 度。
#   3. 舵机平放在盒内靠 +Y 一侧，由托台抬高至上表面与底壳上沿平齐。
#   4. 超声波模块位于 -Y 侧内表面中央，两个探头朝外。
#   5. K10 插入 K10 IO 扩展板后，整体外置于盒子右侧。
#   6. 右侧面开 15 x 10 矩形穿线孔，中心 Z=10。
#   7. 上盖使用 +Y 后方的三段外置铰链，不切削底壳或上盖避让槽。
#
# 舵机臂仅作为活动连杆的舵机端参考件；本版不生成连杆。
# 上盖绕外置铰链轴打开 70 度，舵机臂绕真实舵机轴同步转动 70 度。
# ============================================================


# =========================
# 盒体参数
# =========================
box_length_x = 100.0
box_width_y = 80.0
box_height_z = 60.0
base_height_z = 40.0
lid_height_z = 20.0

wall_thickness = 2.0
floor_thickness = 2.0
lid_wall_thickness = 2.0
lid_clearance = 0.4
corner_radius = 5.0

# 超声波 PCB 厚 1.6。装配后 local +Z 映射为 global -Y，
# 因此 PCB 原点必须比 -Y 内壁面向盒内偏移一个 PCB 厚度，
# 才能让 PCB 的 +Z 面与盒子内壁的内侧面重合。
ultrasonic_pcb_thickness = 1.6
ultrasonic_wall_inner_y = -box_width_y / 2.0 + wall_thickness
ultrasonic_pcb_origin_y = ultrasonic_wall_inner_y + ultrasonic_pcb_thickness

# 只用于盒子 -Y 侧壁的四个超声波固定孔，不改硬件参考模型本体。
ultrasonic_shell_mount_pitch_x = 39.7
ultrasonic_shell_mount_pitch_z = 14.8
ultrasonic_shell_mount_hole_diameter = 3.3
ultrasonic_shell_mount_center_z = 20.0

lid_open_angle_deg = 70.0
lid_preview_angle_deg = 70.0
# -Y 方向的大面积上盖向上打开，因此绕 X 轴使用负角度。
lid_rotation_angle_deg = -lid_preview_angle_deg

# 上盖闭合状态整体抬高 1mm；壳体范围 Z=41~61，内顶面 Z=59。
lid_closed_gap_z = 1.0
lid_closed_bottom_z = base_height_z + lid_closed_gap_z
lid_closed_top_z = lid_closed_bottom_z + lid_height_z
lid_closed_inner_top_z = lid_closed_top_z - lid_wall_thickness

# 舵机平放装配参数：local +Z -> global -X，local +Y -> global -Z。
# 舵机由托台抬高，整体 Z=28~40；沿 Y 镜像后输出轴靠近 +Y，
# 输出轴中心为 (Y=25.3, Z=34)。
servo_translation_x = 31.5
servo_center_y = 20.0
servo_translation_z = 34.0
servo_bottom_z = 28.0
servo_top_z = 40.0
servo_output_axis_y = 25.3
servo_output_axis_z = 34.0

# 真实舵机输出轴沿全局 X 方向。
servo_axis_start = (-box_length_x, servo_output_axis_y, servo_output_axis_z)
servo_axis_end = (box_length_x, servo_output_axis_y, servo_output_axis_z)

# 舵机臂局部坐标：圆柱中心为 XY 原点，底面为 Z=0。
servo_horn_hub_diameter = 7.0
servo_horn_hub_height = 3.8
servo_horn_arm_length = 12.4
servo_horn_arm_width = 5.0
servo_horn_arm_thickness = 1.4
servo_horn_arm_tangent_x = servo_horn_hub_diameter / 2.0
servo_horn_arm_end_x = servo_horn_arm_tangent_x + servo_horn_arm_length
servo_horn_shaft_cavity_diameter = 5.0
servo_horn_shaft_cavity_depth = 2.0
servo_horn_screw_hole_diameter = 1.2
servo_horn_screw_radii = (6.5, 12.5)

# 舵机臂 local +X -> global -Y，local +Y -> global -Z，local +Z -> global +X。
# 轴孔 +X 开口面放在 X=1.5，使薄臂与既有夹块之间保留 0.1mm 可视间隙。
servo_horn_hub_top_x = 1.5
servo_horn_hub_min_x = servo_horn_hub_top_x - servo_horn_hub_height

# 闭合时两个舵机臂孔从输出轴中心沿 -Y 排列。
servo_horn_closed_hole_y_1 = servo_output_axis_y - servo_horn_screw_radii[0]
servo_horn_closed_hole_y_2 = servo_output_axis_y - servo_horn_screw_radii[1]

# 外置铰链：三处 D3.5 孔共用一条沿 X 的轴线。
# 两侧固定块为 7.3 x 8 x 8，中间净距 7.5，总长 22.1。
hinge_fixed_block_length_x = 7.3
hinge_fixed_block_width_y = 8.0
hinge_fixed_block_height_z = 8.0
hinge_middle_gap_x = 7.5
hinge_fixed_center_x_offset = (hinge_middle_gap_x + hinge_fixed_block_length_x) / 2.0
hinge_total_length_x = 2.0 * hinge_fixed_block_length_x + hinge_middle_gap_x
hinge_hole_diameter = 3.5

# D8 铰链桶最内侧距底壳 +Y 外表面 1mm；公共轴线为 (Y=45, Z=36)。
hinge_wall_gap_y = 1.0
hinge_barrel_outer_diameter = 8.0
hinge_axis_y = box_width_y / 2.0 + hinge_wall_gap_y + hinge_barrel_outer_diameter / 2.0
hinge_axis_z = base_height_z - hinge_fixed_block_height_z / 2.0
hinge_axis_start = (-box_length_x, hinge_axis_y, hinge_axis_z)
hinge_axis_end = (box_length_x, hinge_axis_y, hinge_axis_z)

# 中央活动桶长 7.3；与两侧固定块各留 0.1mm X 向间隙。
hinge_lid_barrel_length_x = 7.3
hinge_axial_clearance_x = 0.1

# 固定块以隐藏重叠筋接回 +Y 后壁；活动桶先由竖直颈接到盖底高度，
# 再用整片实心腹板填满竖直颈与上盖后壁之间的空间。
hinge_fusion_overlap = 0.1
hinge_base_rib_min_y = box_width_y / 2.0 - hinge_fusion_overlap
hinge_base_rib_max_y = hinge_axis_y - hinge_fixed_block_width_y / 2.0 + hinge_fusion_overlap

# 两个底壳固定铰链块下方各增加一个 45 度三角加强肋。
# 三角肋从后壁内嵌 0.1mm 处起步，斜向外扩展到铰链块外侧底边，沿 X 贯穿块宽。
hinge_gusset_angle_deg = 45.0
hinge_gusset_inner_y = box_width_y / 2.0 - hinge_fusion_overlap
hinge_gusset_outer_y = hinge_axis_y + hinge_fixed_block_width_y / 2.0
hinge_gusset_top_z = hinge_axis_z - hinge_fixed_block_height_z / 2.0
hinge_gusset_leg_length = hinge_gusset_outer_y - hinge_gusset_inner_y
hinge_gusset_bottom_z = hinge_gusset_top_z - hinge_gusset_leg_length
hinge_gusset_fusion_height_z = 2.0 * hinge_fusion_overlap

hinge_lid_neck_width_y = 2.0
hinge_lid_neck_min_z = hinge_axis_z + hinge_barrel_outer_diameter / 2.0 - hinge_fusion_overlap
hinge_lid_web_min_y = box_width_y / 2.0 - lid_clearance / 2.0 - lid_wall_thickness - hinge_fusion_overlap
hinge_lid_web_max_y = hinge_axis_y - hinge_lid_neck_width_y / 2.0 + hinge_fusion_overlap
hinge_lid_web_min_z = lid_closed_bottom_z

# 上盖活动铰链根部补强：在闭合姿态的 YZ 侧视面中，
# 从上盖后壁下边与矩形连接腹板的交点连到铰链圆心，并填满三角区域。
hinge_lid_reinforcement_anchor_y = box_width_y / 2.0 - lid_clearance / 2.0
hinge_lid_reinforcement_anchor_z = lid_closed_bottom_z
hinge_lid_reinforcement_axis_y = hinge_axis_y
hinge_lid_reinforcement_axis_z = hinge_axis_z
hinge_lid_reinforcement_top_y = hinge_axis_y
hinge_lid_reinforcement_top_z = lid_closed_bottom_z

# 上盖闭合时覆盖完整盒口；不再生成任何运动包络切口。
lid_closed_min_y = -box_width_y / 2.0 + lid_clearance / 2.0
lid_closed_max_y = box_width_y / 2.0 - lid_clearance / 2.0
lid_closed_width_y = lid_closed_max_y - lid_closed_min_y
lid_closed_center_y = (lid_closed_min_y + lid_closed_max_y) / 2.0

# 删除圆环支点，改为沿上盖 Y 方向贯穿的直线滑槽。
# X 向宽度为 3mm；撤销此前的 -X 平移，恢复原中心 X=-3.8。
# 上梁从上盖内表面 Z=59 向下量取 3.5mm；中间净空 5mm，下梁厚 2.5mm。
lid_slide_slot_original_center_x = -3.8
lid_slide_slot_shift_x = 0.0
lid_slide_slot_center_x = lid_slide_slot_original_center_x + lid_slide_slot_shift_x
lid_slide_slot_width_x = 3.0
lid_slide_slot_clear_height_z = 5.0
lid_slide_slot_lower_beam_height_z = 2.5
lid_slide_slot_upper_beam_height_z = 3.5
lid_slide_slot_total_height_z = (
    lid_slide_slot_lower_beam_height_z
    + lid_slide_slot_clear_height_z
    + lid_slide_slot_upper_beam_height_z
)

lid_slide_slot_min_y = lid_closed_min_y
lid_slide_slot_max_y = lid_closed_max_y
lid_slide_slot_length_y = lid_slide_slot_max_y - lid_slide_slot_min_y
lid_slide_slot_center_y = (lid_slide_slot_min_y + lid_slide_slot_max_y) / 2.0

lid_slide_slot_top_z = lid_closed_inner_top_z
lid_slide_slot_upper_beam_center_z = (
    lid_slide_slot_top_z - lid_slide_slot_upper_beam_height_z / 2.0
)
lid_slide_slot_clear_max_z = (
    lid_slide_slot_top_z - lid_slide_slot_upper_beam_height_z
)
lid_slide_slot_clear_min_z = (
    lid_slide_slot_clear_max_z - lid_slide_slot_clear_height_z
)
lid_slide_slot_clear_center_z = (
    lid_slide_slot_clear_min_z + lid_slide_slot_clear_max_z
) / 2.0
lid_slide_slot_bottom_z = (
    lid_slide_slot_clear_min_z - lid_slide_slot_lower_beam_height_z
)
lid_slide_slot_lower_beam_center_z = (
    lid_slide_slot_bottom_z + lid_slide_slot_lower_beam_height_z / 2.0
)
lid_slide_slot_center_z = (
    lid_slide_slot_bottom_z + lid_slide_slot_top_z
) / 2.0
lid_slide_slot_top_fusion_overlap = hinge_fusion_overlap

# 中间净空只保留在上盖内部：前端止于前壁内表面，
# 后端止于铰链腹板起始面，前后壁和铰链腹板均不切穿。
lid_slide_slot_cutter_min_y = lid_closed_min_y + lid_wall_thickness
lid_slide_slot_cutter_max_y = hinge_lid_web_min_y
lid_slide_slot_cutter_length_y = lid_slide_slot_cutter_max_y - lid_slide_slot_cutter_min_y
lid_slide_slot_cutter_center_y = (
    lid_slide_slot_cutter_min_y + lid_slide_slot_cutter_max_y
) / 2.0


# =========================
# 基础几何 helper
# =========================
def rounded_prism(length_x, width_y, height_z, radius, z_min=0.0, center_x=0.0, center_y=0.0):
    part = (
        cq.Workplane("XY")
        .box(length_x, width_y, height_z, centered=(True, True, False))
        .edges("|Z")
        .fillet(radius)
    )
    return part.translate((center_x, center_y, z_min))


def centered_box(size_xyz, center_xyz):
    return (
        cq.Workplane("XY")
        .box(size_xyz[0], size_xyz[1], size_xyz[2], centered=(True, True, True))
        .translate(center_xyz)
    )


def box_from_z(length_x, width_y, height_z, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .box(length_x, width_y, height_z, centered=(True, True, False))
        .translate((center_x, center_y, z_min))
    )


def cylinder_from_z(diameter, height_z, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(height_z)
        .translate((center_x, center_y, z_min))
    )


def centered_cylinder_x(diameter, length_x, center_xyz):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(length_x)
        .translate((0.0, 0.0, -length_x / 2.0))
        .rotate((0, 0, 0), (0, 1, 0), 90)
        .translate(center_xyz)
    )


def centered_cylinder_y(diameter, length_y, center_xyz):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2.0)
        .extrude(length_y)
        .translate((0.0, 0.0, -length_y / 2.0))
        .rotate((0, 0, 0), (1, 0, 0), -90)
        .translate(center_xyz)
    )


def rotate_about_servo_axis(part, angle_deg):
    return part.rotate(servo_axis_start, servo_axis_end, angle_deg)


def rotate_about_hinge_axis(part, angle_deg):
    return part.rotate(hinge_axis_start, hinge_axis_end, angle_deg)


# ============================================================
# 四个真实硬件 builder
# 每个 builder 只描述硬件本体；装配旋转和平移在后文统一处理。
# ============================================================


def make_unihiker_k10():
    pcb_length = 83.2
    pcb_width = 51.3
    pcb_thickness = 1.6
    pcb_corner_radius = 1.0

    display_frame_length = 71.0
    display_frame_width = 51.0
    display_frame_height = 4.0
    display_frame_minus_x_margin = 5.5
    display_frame_center_x = -pcb_length / 2.0 + display_frame_minus_x_margin + display_frame_length / 2.0

    display_area_length = 57.5
    display_area_width = 43.0
    display_recess_depth = 1.0
    display_area_minus_x_margin_from_frame = 10.0
    display_frame_min_x = display_frame_center_x - display_frame_length / 2.0
    display_area_center_x = display_frame_min_x + display_area_minus_x_margin_from_frame + display_area_length / 2.0
    display_area_surface_z = pcb_thickness + display_frame_height - display_recess_depth

    camera_center_x = -12.0
    camera_block_size = 8.0
    camera_block_height = 2.5
    camera_cylinder_diameter = 8.0
    camera_cylinder_height = 2.5
    lens_diameter = 2.5
    lens_recess_depth = 1.0

    gold_finger_length = 7.0
    gold_finger_thickness = 0.06
    gold_finger_center_x = pcb_length / 2.0 - gold_finger_length / 2.0

    pcb = rounded_prism(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius)

    top_gold_finger = rounded_prism(
        gold_finger_length,
        pcb_width,
        gold_finger_thickness,
        pcb_corner_radius,
        pcb_thickness,
        gold_finger_center_x,
        0.0,
    )
    bottom_gold_finger = rounded_prism(
        gold_finger_length,
        pcb_width,
        gold_finger_thickness,
        pcb_corner_radius,
        -gold_finger_thickness,
        gold_finger_center_x,
        0.0,
    )

    display_frame = box_from_z(
        display_frame_length,
        display_frame_width,
        display_frame_height,
        display_frame_center_x,
        0.0,
        pcb_thickness,
    )
    display_recess = box_from_z(
        display_area_length,
        display_area_width,
        display_recess_depth + 0.2,
        display_area_center_x,
        0.0,
        display_area_surface_z,
    )
    display_frame = display_frame.cut(display_recess)
    display_surface = box_from_z(
        display_area_length,
        display_area_width,
        0.12,
        display_area_center_x,
        0.0,
        display_area_surface_z,
    )

    camera_block = box_from_z(
        camera_block_size,
        camera_block_size,
        camera_block_height,
        camera_center_x,
        0.0,
        -camera_block_height,
    )
    camera_cylinder_z_min = -camera_block_height - camera_cylinder_height
    camera_cylinder = cylinder_from_z(
        camera_cylinder_diameter,
        camera_cylinder_height,
        camera_center_x,
        0.0,
        camera_cylinder_z_min,
    )
    lens_recess = cylinder_from_z(
        lens_diameter,
        lens_recess_depth + 0.2,
        camera_center_x,
        0.0,
        camera_cylinder_z_min,
    )
    camera_cylinder = camera_cylinder.cut(lens_recess)
    lens_surface = cylinder_from_z(
        lens_diameter,
        0.08,
        camera_center_x,
        0.0,
        camera_cylinder_z_min + lens_recess_depth,
    )

    return (
        pcb
        .union(top_gold_finger)
        .union(bottom_gold_finger)
        .union(display_frame)
        .union(display_surface)
        .union(camera_block)
        .union(camera_cylinder)
        .union(lens_surface)
    )


def make_unihiker_k10_io_expansion_board():
    pcb_length = 80.0
    pcb_width = 47.0
    pcb_thickness = 1.6
    pcb_corner_radius = 2.0

    bottom_plate_thickness = 1.6
    board_gap = 3.5
    standoff_diameter = 4.0
    standoff_height = board_gap
    standoff_edge_offset = 8.0

    switch_length = 6.7
    switch_width = 13.0
    switch_height = 6.6
    switch_center_x = pcb_length / 2.0 - switch_length / 2.0
    switch_center_y = pcb_width / 2.0 - pcb_corner_radius - switch_width / 2.0
    lever_size = 4.0
    lever_height = 5.0

    slot_length = 57.0
    slot_width = 13.7
    slot_height = 15.6
    slot_cutout_length = 52.0
    slot_cutout_width = 2.0

    pcb = rounded_prism(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius)
    bottom_plate = rounded_prism(
        pcb_length,
        pcb_width,
        bottom_plate_thickness,
        pcb_corner_radius,
        -(board_gap + bottom_plate_thickness),
    )

    standoff_x = pcb_length / 2.0 - standoff_edge_offset
    standoff_y = pcb_width / 2.0 - standoff_edge_offset
    standoffs = None
    for x in (-standoff_x, standoff_x):
        for y in (-standoff_y, standoff_y):
            post = cylinder_from_z(standoff_diameter, standoff_height, x, y, -board_gap)
            standoffs = post if standoffs is None else standoffs.union(post)

    switch_body = box_from_z(
        switch_length,
        switch_width,
        switch_height,
        switch_center_x,
        switch_center_y,
        pcb_thickness,
    )
    switch_lever = box_from_z(
        lever_size,
        lever_size,
        lever_height,
        switch_center_x,
        switch_center_y,
        pcb_thickness + switch_height,
    )

    slot_body = box_from_z(slot_length, slot_width, slot_height, 0.0, 0.0, pcb_thickness)
    slot_cutout = box_from_z(
        slot_cutout_length,
        slot_cutout_width,
        slot_height + 0.6,
        0.0,
        0.0,
        pcb_thickness - 0.3,
    )
    k10_slot = slot_body.cut(slot_cutout)

    return pcb.union(bottom_plate).union(standoffs).union(switch_body).union(switch_lever).union(k10_slot)


def make_unihiker_servo():
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

    large_cylinder_diameter = 12.0
    large_cylinder_height_z = 4.0
    large_cylinder_center_x = body_length_x / 2.0 - large_cylinder_diameter / 2.0

    small_cylinder_diameter = 4.5
    small_cylinder_height_z = 4.0

    output_shaft_diameter = 5.0
    output_shaft_height_z = 4.5

    wire_port_length_x = 2.0
    wire_port_width_y = 6.0
    wire_port_depth_z = 1.2

    body = cq.Workplane("XY").box(
        body_length_x,
        body_width_y,
        body_height_z,
        centered=(True, True, False),
    )
    wire_port = centered_box(
        (wire_port_length_x, wire_port_width_y, wire_port_depth_z),
        (
            body_length_x / 2.0 - wire_port_length_x / 2.0,
            0.0,
            wire_port_depth_z / 2.0,
        ),
    )
    body = body.cut(wire_port)

    lugs = None
    for x in (-lug_center_x, lug_center_x):
        lug = centered_box((lug_extension_x, lug_width_y, lug_thickness_z), (x, 0.0, lug_center_z))
        lug_hole = cylinder_from_z(
            lug_hole_diameter,
            lug_thickness_z + 1.0,
            x,
            0.0,
            lug_minus_z_from_body_bottom - 0.5,
        )
        lug = lug.cut(lug_hole)
        lugs = lug if lugs is None else lugs.union(lug)

    large_cylinder = cylinder_from_z(
        large_cylinder_diameter,
        large_cylinder_height_z,
        large_cylinder_center_x,
        0.0,
        body_height_z,
    )
    small_cylinder = cylinder_from_z(
        small_cylinder_diameter,
        small_cylinder_height_z,
        0.0,
        0.0,
        body_height_z,
    )
    output_shaft = cylinder_from_z(
        output_shaft_diameter,
        output_shaft_height_z,
        large_cylinder_center_x,
        0.0,
        body_height_z + large_cylinder_height_z,
    )

    return body.union(lugs).union(large_cylinder).union(small_cylinder).union(output_shaft)


def make_unihiker_ultrasonic_distance_sensor():
    pcb_length = 22.0
    pcb_width = 47.0
    pcb_thickness = 1.6
    pcb_corner_radius = 2.0

    connector_length_x = 5.5
    connector_width_y = 10.0
    connector_height_z = 6.3
    connector_center_x = pcb_length / 2.0 - connector_length_x / 2.0

    mounting_hole_diameter = 3.0
    mounting_hole_edge_offset = 2.4
    mounting_hole_x = pcb_length / 2.0 - mounting_hole_edge_offset
    mounting_hole_y = pcb_width / 2.0 - mounting_hole_edge_offset

    transducer_diameter = 16.4
    transducer_height_z = 12.4
    transducer_center_y_offset = 21.5 / 2.0

    pcb = rounded_prism(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius)
    mounting_points = [
        (-mounting_hole_x, -mounting_hole_y),
        (-mounting_hole_x, mounting_hole_y),
        (mounting_hole_x, -mounting_hole_y),
        (mounting_hole_x, mounting_hole_y),
    ]
    pcb = pcb.faces(">Z").workplane().pushPoints(mounting_points).hole(mounting_hole_diameter)

    connector = centered_box(
        (connector_length_x, connector_width_y, connector_height_z),
        (connector_center_x, 0.0, -connector_height_z / 2.0),
    )
    transducer_a = cylinder_from_z(
        transducer_diameter,
        transducer_height_z,
        0.0,
        -transducer_center_y_offset,
        pcb_thickness,
    )
    transducer_b = cylinder_from_z(
        transducer_diameter,
        transducer_height_z,
        0.0,
        transducer_center_y_offset,
        pcb_thickness,
    )

    return pcb.union(connector).union(transducer_a).union(transducer_b)


# ============================================================
# 真实舵机臂
# ============================================================
def build_servo_horn():
    # 圆柱和薄臂都从局部 Z=0 起，圆柱比薄臂高 2.4mm。
    hub = cylinder_from_z(
        servo_horn_hub_diameter,
        servo_horn_hub_height,
        0.0,
        0.0,
        0.0,
    )
    tangent_arm = box_from_z(
        servo_horn_arm_length,
        servo_horn_arm_width,
        servo_horn_arm_thickness,
        servo_horn_arm_tangent_x + servo_horn_arm_length / 2.0,
        0.0,
        0.0,
    )

    # 长方体的 -X 面与圆柱在 X=3.5 相切；补块从圆心延伸到切线，
    # union 后只填充圆周和切线之间的空余区域，不改变圆柱外轮廓。
    tangent_gap_filler = box_from_z(
        servo_horn_arm_tangent_x,
        servo_horn_arm_width,
        servo_horn_arm_thickness,
        servo_horn_arm_tangent_x / 2.0,
        0.0,
        0.0,
    )
    horn = hub.union(tangent_arm).union(tangent_gap_filler)

    # D5 轴孔从圆柱 +Z 面向下切 2mm，底部保留 1.8mm。
    shaft_cavity = cylinder_from_z(
        servo_horn_shaft_cavity_diameter,
        servo_horn_shaft_cavity_depth + 0.2,
        0.0,
        0.0,
        servo_horn_hub_height - servo_horn_shaft_cavity_depth,
    )
    horn = horn.cut(shaft_cavity)

    # 两个 D1.2 通孔位于长臂中心线，距圆柱中心 6.5mm 和 12.5mm。
    for hole_x in servo_horn_screw_radii:
        screw_hole = cylinder_from_z(
            servo_horn_screw_hole_diameter,
            servo_horn_arm_thickness + 0.2,
            hole_x,
            0.0,
            -0.1,
        )
        horn = horn.cut(screw_hole)
    return horn


def place_servo_horn_closed(horn_part=None):
    # 前两次旋转得到 local X/Y/Z -> global Y/Z/X，
    # 再绕 global X 旋转 180 度，最终得到 local X/Y/Z -> global -Y/-Z/X。
    # 局部圆柱底面位于 global X=-2.3，轴孔开口面位于 X=+1.5。
    horn = build_servo_horn() if horn_part is None else horn_part
    return (
        horn
        .rotate((0, 0, 0), (0, 0, 1), 90)
        .rotate((0, 0, 0), (0, 1, 0), 90)
        .rotate((0, 0, 0), (1, 0, 0), 180)
        .translate((servo_horn_hub_min_x, servo_output_axis_y, servo_output_axis_z))
    )


# ============================================================
# 阶段 1：下盒体
# ============================================================
def build_hollow_base():
    outer = rounded_prism(
        box_length_x,
        box_width_y,
        base_height_z,
        corner_radius,
        0.0,
    )
    inner = rounded_prism(
        box_length_x - 2.0 * wall_thickness,
        box_width_y - 2.0 * wall_thickness,
        base_height_z,
        max(0.5, corner_radius - wall_thickness),
        floor_thickness,
    )
    return outer.cut(inner)


# ============================================================
# 阶段 2：-Y 侧超声波开孔 + 右侧穿线孔
# ============================================================
def apply_openings(base_part):
    # 超声波两个探头孔，孔径来自已确认的硬件 profile：D17.4。
    for x in (-10.75, 10.75):
        cutter = centered_cylinder_y(17.4, wall_thickness + 2.0, (x, -box_width_y / 2.0, 20.0))
        base_part = base_part.cut(cutter)

    # 盒壁四个安装孔：阵列中心保持 X=0、Z=20，
    # X 孔距 39.7，Z 孔距 14.8，孔径 D3.3。
    half_pitch_x = ultrasonic_shell_mount_pitch_x / 2.0
    half_pitch_z = ultrasonic_shell_mount_pitch_z / 2.0
    ultrasonic_mount_holes = [
        (-half_pitch_x, ultrasonic_shell_mount_center_z - half_pitch_z),
        (half_pitch_x, ultrasonic_shell_mount_center_z - half_pitch_z),
        (-half_pitch_x, ultrasonic_shell_mount_center_z + half_pitch_z),
        (half_pitch_x, ultrasonic_shell_mount_center_z + half_pitch_z),
    ]
    for x, z in ultrasonic_mount_holes:
        cutter = centered_cylinder_y(
            ultrasonic_shell_mount_hole_diameter,
            wall_thickness + 2.0,
            (x, -box_width_y / 2.0, z),
        )
        base_part = base_part.cut(cutter)

    # 右侧面 15 x 10 矩形穿线孔，中心位于 X=+50, Y=0, Z=10。
    cable_cutter = centered_box(
        (wall_thickness + 2.0, 15.0, 10.0),
        (box_length_x / 2.0, 0.0, 10.0),
    )
    return base_part.cut(cable_cutter)


# 自动开盖结构不使用四角螺丝柱；保留正式入口便于 CQ-editor/后续程序调用。
def apply_screw_bosses(base_part):
    return base_part


# ============================================================
# 阶段 3：舵机托台、1mm 定位槽和四个耳孔夹块
# 托台从内底面 Z=2 起、顶面 Z=29；舵机落在 Z=28 的槽底，最高面为 Z=40。
# ============================================================
servo_support_bottom_z = floor_thickness
servo_support_top_z = 29.0
servo_support_height_z = servo_support_top_z - servo_support_bottom_z
servo_support_length_x = 33.1
servo_support_width_y = 34.2
servo_support_center_x = 15.75

servo_slot_depth_z = 1.0
servo_body_slot_length_x = 23.8
servo_body_slot_width_y = 23.4
servo_body_center_x = 20.0

servo_ear_hole_axis_x = 14.3
servo_minus_y_ear_center_y = 6.2
servo_plus_y_ear_center_y = 33.8
servo_ear_hole_z = servo_output_axis_z
servo_ear_slot_length_x = 3.2
servo_ear_slot_width_y = 5.8

servo_clamp_block_width_y = 5.0
servo_clamp_block_height_z = 12.2
servo_clamp_block_center_z = 33.9
servo_clamp_hole_diameter = 2.2

# 四个夹块沿 X 延伸到托台两侧；中间保留 3mm 舵机耳片槽。
servo_support_min_x = servo_support_center_x - servo_support_length_x / 2.0
servo_support_max_x = servo_support_center_x + servo_support_length_x / 2.0
servo_clamp_gap_min_x = servo_ear_hole_axis_x - 1.5
servo_clamp_gap_max_x = servo_ear_hole_axis_x + 1.5
servo_minus_x_clamp_length = servo_clamp_gap_min_x - servo_support_min_x
servo_plus_x_clamp_length = servo_support_max_x - servo_clamp_gap_max_x
servo_minus_x_clamp_center = (servo_support_min_x + servo_clamp_gap_min_x) / 2.0
servo_plus_x_clamp_center = (servo_clamp_gap_max_x + servo_support_max_x) / 2.0

# +Y、+X 方向夹块继续采用已确认的 10mm 长度，内侧面 X=15.8 不变。
servo_plus_y_plus_x_clamp_length = 10.0
servo_plus_y_plus_x_clamp_center = servo_clamp_gap_max_x + servo_plus_y_plus_x_clamp_length / 2.0


def build_servo_support_block():
    support = box_from_z(
        servo_support_length_x,
        servo_support_width_y,
        servo_support_height_z,
        servo_support_center_x,
        servo_center_y,
        servo_support_bottom_z,
    )

    # 舵机主体底面槽：按实际投影四周增加 0.4mm 装配余量，槽深 1mm。
    body_slot = box_from_z(
        servo_body_slot_length_x,
        servo_body_slot_width_y,
        servo_slot_depth_z,
        servo_body_center_x,
        servo_center_y,
        servo_bottom_z,
    )
    support = support.cut(body_slot)

    # 两个舵机耳底面各保留一个 1mm 深定位槽。
    for ear_y in (servo_minus_y_ear_center_y, servo_plus_y_ear_center_y):
        ear_slot = box_from_z(
            servo_ear_slot_length_x,
            servo_ear_slot_width_y,
            servo_slot_depth_z,
            servo_ear_hole_axis_x,
            ear_y,
            servo_bottom_z,
        )
        support = support.cut(ear_slot)
    return support


def build_servo_ear_clamp_pair(ear_center_y, plus_x_length=None, plus_x_center=None):
    # 每个舵机耳沿孔轴 X 的前后各放一个长条夹块，两只耳合计四块。
    active_plus_x_length = servo_plus_x_clamp_length if plus_x_length is None else plus_x_length
    active_plus_x_center = servo_plus_x_clamp_center if plus_x_center is None else plus_x_center

    minus_x_block = centered_box(
        (servo_minus_x_clamp_length, servo_clamp_block_width_y, servo_clamp_block_height_z),
        (servo_minus_x_clamp_center, ear_center_y, servo_clamp_block_center_z),
    )
    plus_x_block = centered_box(
        (active_plus_x_length, servo_clamp_block_width_y, servo_clamp_block_height_z),
        (active_plus_x_center, ear_center_y, servo_clamp_block_center_z),
    )
    pair = minus_x_block.union(plus_x_block)

    screw_hole = centered_cylinder_x(
        servo_clamp_hole_diameter,
        servo_support_length_x + 2.0,
        (servo_support_center_x, ear_center_y, servo_ear_hole_z),
    )
    return pair.cut(screw_hole)


def build_servo_internal_mounts():
    support = build_servo_support_block()
    minus_y_clamps = build_servo_ear_clamp_pair(servo_minus_y_ear_center_y)
    plus_y_clamps = build_servo_ear_clamp_pair(
        servo_plus_y_ear_center_y,
        plus_x_length=servo_plus_y_plus_x_clamp_length,
        plus_x_center=servo_plus_y_plus_x_clamp_center,
    )
    return [support, minus_y_clamps, plus_y_clamps]


def build_mounts():
    return build_servo_internal_mounts()


def apply_mounts(base_part, lid_part):
    for mount in build_mounts():
        base_part = base_part.union(mount)
    return base_part, lid_part


# ============================================================
# 阶段 4：外置三段铰链、空心上盖和 Y 向贯穿滑槽
# 所有铰链连接均为加法实体；底壳后壁与上盖壳体均保持完整。
# ============================================================
def build_base_hinge_support_gusset(center_x):
    # 在 YZ 侧视平面画直角三角形，再沿 +X 拉伸 7.3mm。
    # 斜边的 Y/Z 增量相等，因此相对打印平台为严格 45 度。
    gusset = (
        cq.Workplane(
            "YZ",
            origin=(center_x - hinge_fixed_block_length_x / 2.0, 0.0, 0.0),
        )
        .moveTo(hinge_gusset_inner_y, hinge_gusset_bottom_z)
        .lineTo(hinge_gusset_inner_y, hinge_gusset_top_z)
        .lineTo(hinge_gusset_outer_y, hinge_gusset_top_z)
        .close()
        .extrude(hinge_fixed_block_length_x)
    )

    # 隐藏融合条向铰链块内部伸入 0.1mm，避免三角肋只靠共面与块体连接。
    fusion_strip = centered_box(
        (
            hinge_fixed_block_length_x,
            hinge_gusset_leg_length,
            hinge_gusset_fusion_height_z,
        ),
        (
            center_x,
            (hinge_gusset_inner_y + hinge_gusset_outer_y) / 2.0,
            hinge_gusset_top_z,
        ),
    )
    return gusset.union(fusion_strip)


def build_base_hinge_blocks():
    fixed_parts = []
    rib_width_y = hinge_base_rib_max_y - hinge_base_rib_min_y
    rib_center_y = (hinge_base_rib_min_y + hinge_base_rib_max_y) / 2.0

    for center_x in (-hinge_fixed_center_x_offset, hinge_fixed_center_x_offset):
        fixed_block = centered_box(
            (
                hinge_fixed_block_length_x,
                hinge_fixed_block_width_y,
                hinge_fixed_block_height_z,
            ),
            (center_x, hinge_axis_y, hinge_axis_z),
        )

        # 固定块距后壁 1mm；连接筋分别与后壁和固定块隐藏重叠 0.1mm。
        connection_rib = centered_box(
            (
                hinge_fixed_block_length_x,
                rib_width_y,
                hinge_fixed_block_height_z,
            ),
            (center_x, rib_center_y, hinge_axis_z),
        )
        support_gusset = build_base_hinge_support_gusset(center_x)
        fixed_leaf = fixed_block.union(connection_rib).union(support_gusset)

        pin_hole = centered_cylinder_x(
            hinge_hole_diameter,
            hinge_fixed_block_length_x + 2.0 * hinge_fusion_overlap,
            (center_x, hinge_axis_y, hinge_axis_z),
        )
        fixed_parts.append(fixed_leaf.cut(pin_hole))

    return fixed_parts[0].union(fixed_parts[1])


def build_lid_hinge_root_reinforcement():
    # 在 YZ 侧视平面画实心三角形，沿 +X 拉伸满中央铰链桶的 7.3mm 宽度。
    # 斜边直接连接上盖后壁根部和铰链圆心，消除原来仅靠窄颈连接的薄弱区。
    return (
        cq.Workplane(
            "YZ",
            origin=(-hinge_lid_barrel_length_x / 2.0, 0.0, 0.0),
        )
        .moveTo(
            hinge_lid_reinforcement_anchor_y,
            hinge_lid_reinforcement_anchor_z,
        )
        .lineTo(
            hinge_lid_reinforcement_axis_y,
            hinge_lid_reinforcement_axis_z,
        )
        .lineTo(
            hinge_lid_reinforcement_top_y,
            hinge_lid_reinforcement_top_z,
        )
        .close()
        .extrude(hinge_lid_barrel_length_x)
    )


def build_lid_hinge_leaf():
    # 中央活动件采用 D8 圆形铰链桶；D3.5 孔与两侧固定块同轴。
    barrel = centered_cylinder_x(
        hinge_barrel_outer_diameter,
        hinge_lid_barrel_length_x,
        (0.0, hinge_axis_y, hinge_axis_z),
    )
    pin_hole = centered_cylinder_x(
        hinge_hole_diameter,
        hinge_lid_barrel_length_x + 2.0 * hinge_fusion_overlap,
        (0.0, hinge_axis_y, hinge_axis_z),
    )

    # 竖直颈从桶顶部隐藏重叠 0.1mm，一直延伸到上盖顶面。
    neck_height_z = lid_closed_top_z - hinge_lid_neck_min_z
    neck = centered_box(
        (hinge_lid_barrel_length_x, hinge_lid_neck_width_y, neck_height_z),
        (
            0.0,
            hinge_axis_y,
            hinge_lid_neck_min_z + neck_height_z / 2.0,
        ),
    )

    # 整片实心腹板从上盖底边一直延伸到顶面，Y 向同时进入后壁和竖直颈。
    # 这样图示的长条空隙被完全填满，而不是只在顶部做一条桥接块。
    web_width_y = hinge_lid_web_max_y - hinge_lid_web_min_y
    web_height_z = lid_closed_top_z - hinge_lid_web_min_z
    connection_web = centered_box(
        (hinge_lid_barrel_length_x, web_width_y, web_height_z),
        (
            0.0,
            (hinge_lid_web_min_y + hinge_lid_web_max_y) / 2.0,
            hinge_lid_web_min_z + web_height_z / 2.0,
        ),
    )
    root_reinforcement = build_lid_hinge_root_reinforcement()
    reinforced_leaf = (
        barrel
        .union(neck)
        .union(connection_web)
        .union(root_reinforcement)
    )

    # 补强三角形覆盖到铰链圆心，因此最后统一重切 D3.5 销轴孔。
    return reinforced_leaf.cut(pin_hole)


def build_lid_slide_slot_beams():
    # 上梁从上盖内表面向下量取 3.5mm，下梁厚 2.5mm；中间保留 5mm 净空。
    lower_beam = centered_box(
        (
            lid_slide_slot_width_x,
            lid_slide_slot_length_y,
            lid_slide_slot_lower_beam_height_z,
        ),
        (
            lid_slide_slot_center_x,
            lid_slide_slot_center_y,
            lid_slide_slot_lower_beam_center_z,
        ),
    )
    upper_beam = centered_box(
        (
            lid_slide_slot_width_x,
            lid_slide_slot_length_y,
            lid_slide_slot_upper_beam_height_z,
        ),
        (
            lid_slide_slot_center_x,
            lid_slide_slot_center_y,
            lid_slide_slot_upper_beam_center_z,
        ),
    )

    # 隐藏融合条跨过 Z=59 内表面：向上梁和既有顶板各重叠 0.1mm。
    # 它位于顶板已有体积内，不改变从内表面向下量取的 3.5mm 可见厚度。
    top_fusion = centered_box(
        (
            lid_slide_slot_width_x,
            lid_slide_slot_length_y,
            2.0 * lid_slide_slot_top_fusion_overlap,
        ),
        (
            lid_slide_slot_center_x,
            lid_slide_slot_center_y,
            lid_slide_slot_top_z,
        ),
    )
    return lower_beam.union(upper_beam).union(top_fusion)


def build_lid_slide_slot_void_cutter():
    # 切刀只对应上盖内部的 5mm 净空，不进入前后壁和后部铰链腹板。
    return centered_box(
        (
            lid_slide_slot_width_x,
            lid_slide_slot_cutter_length_y,
            lid_slide_slot_clear_height_z,
        ),
        (
            lid_slide_slot_center_x,
            lid_slide_slot_cutter_center_y,
            lid_slide_slot_clear_center_z,
        ),
    )


def build_closed_lid_shell():
    lid_outer_length_x = box_length_x - lid_clearance
    lid_outer_width_y = lid_closed_width_y

    closed_outer = rounded_prism(
        lid_outer_length_x,
        lid_outer_width_y,
        lid_height_z,
        corner_radius,
        lid_closed_bottom_z,
        0.0,
        lid_closed_center_y,
    )
    closed_inner = rounded_prism(
        lid_outer_length_x - 2.0 * lid_wall_thickness,
        lid_outer_width_y - 2.0 * lid_wall_thickness,
        lid_height_z - lid_wall_thickness,
        max(0.5, corner_radius - lid_wall_thickness),
        lid_closed_bottom_z,
        0.0,
        lid_closed_center_y,
    )
    return closed_outer.cut(closed_inner)


def build_closed_lid_assembly():
    closed_shell = build_closed_lid_shell()
    hinge_leaf = build_lid_hinge_leaf()
    slide_slot_beams = build_lid_slide_slot_beams()
    closed_lid = closed_shell.union(hinge_leaf).union(slide_slot_beams)
    return closed_lid.cut(build_lid_slide_slot_void_cutter())


def validate_design_parameters():
    tolerance = 1.0e-6

    # 托台回滚到旧高度：舵机上表面与底壳上沿 Z=40 平齐。
    assert abs(servo_support_bottom_z - 2.0) < tolerance
    assert abs(servo_support_top_z - 29.0) < tolerance
    assert abs(servo_slot_depth_z - 1.0) < tolerance
    assert abs(servo_bottom_z - 28.0) < tolerance
    assert abs(servo_top_z - base_height_z) < tolerance
    assert abs(servo_translation_z - 34.0) < tolerance
    assert abs(servo_output_axis_z - 34.0) < tolerance
    assert abs(servo_ear_hole_z - 34.0) < tolerance
    assert abs(servo_clamp_block_center_z - 33.9) < tolerance

    # 三段铰链的公共轴、固定块间距、总长和轴向间隙。
    left_fixed_max_x = -hinge_fixed_center_x_offset + hinge_fixed_block_length_x / 2.0
    right_fixed_min_x = hinge_fixed_center_x_offset - hinge_fixed_block_length_x / 2.0
    central_barrel_max_x = hinge_lid_barrel_length_x / 2.0
    assert abs(hinge_fixed_block_width_y - 8.0) < tolerance
    assert abs(hinge_fixed_block_height_z - 8.0) < tolerance
    assert abs(hinge_barrel_outer_diameter - 8.0) < tolerance
    assert abs(hinge_axis_y - 45.0) < tolerance
    assert abs(hinge_axis_z - 36.0) < tolerance
    assert abs(hinge_lid_reinforcement_anchor_y - 39.8) < tolerance
    assert abs(hinge_lid_reinforcement_anchor_z - 41.0) < tolerance
    assert abs(hinge_lid_reinforcement_axis_y - hinge_axis_y) < tolerance
    assert abs(hinge_lid_reinforcement_axis_z - hinge_axis_z) < tolerance
    assert abs(hinge_lid_reinforcement_top_y - hinge_axis_y) < tolerance
    assert abs(
        hinge_lid_reinforcement_top_z - hinge_lid_reinforcement_anchor_z
    ) < tolerance
    assert hinge_lid_reinforcement_anchor_y < hinge_lid_reinforcement_axis_y
    assert hinge_lid_reinforcement_anchor_z > hinge_lid_reinforcement_axis_z
    assert abs(hinge_gusset_angle_deg - 45.0) < tolerance
    assert abs(
        hinge_gusset_outer_y - hinge_gusset_inner_y
        - (hinge_gusset_top_z - hinge_gusset_bottom_z)
    ) < tolerance
    assert abs(
        hinge_gusset_top_z
        - (hinge_axis_z - hinge_fixed_block_height_z / 2.0)
    ) < tolerance
    assert abs(
        hinge_gusset_outer_y
        - (hinge_axis_y + hinge_fixed_block_width_y / 2.0)
    ) < tolerance
    assert hinge_gusset_inner_y < box_width_y / 2.0
    assert hinge_gusset_bottom_z > floor_thickness
    assert abs(right_fixed_min_x - left_fixed_max_x - 7.5) < tolerance
    assert abs(hinge_total_length_x - 22.1) < tolerance
    assert abs(right_fixed_min_x - central_barrel_max_x - hinge_axial_clearance_x) < tolerance
    assert abs(hinge_axis_z + hinge_fixed_block_height_z / 2.0 - base_height_z) < tolerance
    assert abs(
        hinge_axis_y - hinge_barrel_outer_diameter / 2.0 - box_width_y / 2.0 - 1.0
    ) < tolerance

    # 上盖闭合缝隙、实心连接腹板以及 Y 向贯穿滑槽尺寸。
    assert abs(lid_closed_bottom_z - base_height_z - 1.0) < tolerance
    assert abs(hinge_lid_web_min_z - lid_closed_bottom_z) < tolerance
    assert hinge_lid_web_min_y < lid_closed_max_y - lid_wall_thickness
    assert hinge_lid_web_max_y > hinge_axis_y - hinge_lid_neck_width_y / 2.0
    assert abs(lid_slide_slot_original_center_x + 3.8) < tolerance
    assert abs(lid_slide_slot_shift_x) < tolerance
    assert abs(lid_slide_slot_center_x + 3.8) < tolerance
    assert abs(lid_slide_slot_center_z - 53.5) < tolerance
    assert abs(lid_slide_slot_width_x - 3.0) < tolerance
    assert abs(lid_slide_slot_total_height_z - 11.0) < tolerance
    assert abs(lid_slide_slot_clear_height_z - 5.0) < tolerance
    assert abs(lid_slide_slot_lower_beam_height_z - 2.5) < tolerance
    assert abs(lid_slide_slot_upper_beam_height_z - 3.5) < tolerance
    assert abs(
        lid_slide_slot_lower_beam_height_z
        + lid_slide_slot_clear_height_z
        + lid_slide_slot_upper_beam_height_z
        - lid_slide_slot_total_height_z
    ) < tolerance
    assert abs(lid_slide_slot_min_y - lid_closed_min_y) < tolerance
    assert abs(lid_slide_slot_max_y - lid_closed_max_y) < tolerance
    assert abs(
        lid_slide_slot_cutter_min_y
        - (lid_closed_min_y + lid_wall_thickness)
    ) < tolerance
    assert abs(
        lid_slide_slot_cutter_max_y - hinge_lid_web_min_y
    ) < tolerance
    assert lid_slide_slot_cutter_min_y > lid_closed_min_y
    assert lid_slide_slot_cutter_max_y < lid_closed_max_y
    assert lid_slide_slot_cutter_max_y <= hinge_lid_web_min_y
    assert abs(lid_slide_slot_top_z - lid_closed_inner_top_z) < tolerance
    assert abs(lid_slide_slot_bottom_z - 48.0) < tolerance
    assert abs(lid_slide_slot_clear_min_z - 50.5) < tolerance
    assert abs(lid_slide_slot_clear_max_z - 55.5) < tolerance
    assert abs(lid_slide_slot_top_fusion_overlap - 0.1) < tolerance

    # 闭合舵机臂朝 -Y；绕 X 轴 -70 度后方向落入 -Y、+Z 象限。
    closed_horn_vector_y = -servo_horn_screw_radii[1]
    opened_angle_rad = math.radians(-lid_open_angle_deg)
    opened_horn_vector_y = closed_horn_vector_y * math.cos(opened_angle_rad)
    opened_horn_vector_z = closed_horn_vector_y * math.sin(opened_angle_rad)
    assert opened_horn_vector_y < 0.0
    assert opened_horn_vector_z > 0.0

    # 上盖后下沿是壳体运动中最靠近底壳后壁的关键点；逐度确认始终高于 Z=40。
    closed_corner_dy = lid_closed_max_y - hinge_axis_y
    closed_corner_dz = lid_closed_bottom_z - hinge_axis_z
    for angle_deg in range(0, int(lid_open_angle_deg) + 1):
        angle_rad = math.radians(-angle_deg)
        rotated_corner_z = (
            hinge_axis_z
            + closed_corner_dy * math.sin(angle_rad)
            + closed_corner_dz * math.cos(angle_rad)
        )
        assert rotated_corner_z > base_height_z


def build_lid():
    return rotate_about_hinge_axis(build_closed_lid_assembly(), lid_rotation_angle_deg)


# 自动开盖结构不使用周边盖板螺丝；保留正式入口。
def apply_lid_screw_holes(lid_part):
    return lid_part


# ============================================================
# 阶段 5：四个硬件装配参考 + 舵机臂参考件
# ============================================================
def build_hardware_references(servo_horn_part=None):
    # 舵机平放并沿 Y 镜像：local +Z -> global -X，local +Y -> global -Z。
    # 整体 Z=28~40，输出轴朝 -X 且靠近 +Y，由托台抬高至底壳上沿。
    servo = (
        make_unihiker_servo()
        .rotate((0, 0, 0), (0, 1, 0), -90)
        .rotate((0, 0, 0), (1, 0, 0), -90)
        .translate((servo_translation_x, servo_center_y, servo_translation_z))
    )

    # 超声波：local +Z -> global -Y（朝盒外），local +X -> global -Z（接线边朝下）。
    # PCB 原点为 (0, -36.4, 20)；local +Z 面经过 1.6mm PCB 厚度后
    # 落在 global Y=-38，与盒子 -Y 内壁的内侧面重合，PCB 不再嵌入盒壁。
    ultrasonic = (
        make_unihiker_ultrasonic_distance_sensor()
        .rotate((0, 0, 0), (0, 1, 0), 90)
        .rotate((0, 0, 0), (0, 0, 1), -90)
        .translate((0.0, ultrasonic_pcb_origin_y, 20.0))
    )

    # K10 扩展板位于盒体右侧，保持水平，不与盒体固定。
    k10_io_board = make_unihiker_k10_io_expansion_board().translate((100.6, -14.0, 7.95))

    # K10 金手指插入扩展板中央插槽，复用已确认的插接旋转与位置。
    k10_board = (
        make_unihiker_k10()
        .rotate((0, 0, 0), (0, 1, 0), 90)
        .rotate((0, 0, 0), (0, 0, 1), -90)
        .translate((100.6, -13.2, 59.75))
    )

    if servo_horn_part is None:
        closed_horn = place_servo_horn_closed()
        servo_horn_part = rotate_about_servo_axis(closed_horn, lid_rotation_angle_deg)

    return [k10_board, k10_io_board, servo, ultrasonic, servo_horn_part]


# ============================================================
# 正式输出入口
# ============================================================
validate_design_parameters()

base_part = build_hollow_base()
base_part = apply_openings(base_part)
base_part = apply_screw_bosses(base_part)

closed_lid_part = build_closed_lid_assembly()
closed_servo_horn = place_servo_horn_closed()

# 上盖与舵机臂分别绕各自真实轴线转动；两者之间仅预留未来活动连杆支点。
lid_part = rotate_about_hinge_axis(closed_lid_part, lid_rotation_angle_deg)
lid_part = apply_lid_screw_holes(lid_part)
servo_horn_part = rotate_about_servo_axis(closed_servo_horn, lid_rotation_angle_deg)

base_part, lid_part = apply_mounts(base_part, lid_part)
base_part = base_part.union(build_base_hinge_blocks())

hardware_reference_parts = build_hardware_references(servo_horn_part)

# printable_parts 只有盒体和上盖；其余对象仅供装配检查。
printable_parts = {
    "base_part": base_part,
    "lid_part": lid_part,
}

result = base_part.union(lid_part)
for hardware_part in hardware_reference_parts:
    result = result.union(hardware_part)


if "show_object" in globals():
    show_object(base_part, name="01_盒体_打印件")
    show_object(lid_part, name=f"02_上盖_打印件_打开{lid_preview_angle_deg:g}度")
    show_object(hardware_reference_parts[0], name="03_行空板K10_参考")
    show_object(hardware_reference_parts[1], name="04_K10_IO扩展板_参考")
    show_object(hardware_reference_parts[2], name="05_舵机_参考")
    show_object(hardware_reference_parts[3], name="06_超声波传感器_参考")
    show_object(
        hardware_reference_parts[4],
        name=f"07_舵机臂_参考_打开{lid_preview_angle_deg:g}度",
    )
