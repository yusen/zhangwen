"""行空板 K10 已验证 CadQuery 参考模型。

坐标单位为 mm。此文件参与 Hardware Skill revision 和 SHA-256 校验，但普通 Skill 保存
不会直接执行它；生产 CAD Worker 只消费由 mechanical.md 派生的受控机械档案快照。
"""

import cadquery as cq


hardware_name = "行空板K10"

pcb_length = 83.2
pcb_width = 51.3
pcb_thickness = 1.6
pcb_corner_radius = 1.0

display_frame_length = 71.0
display_frame_width = 51.0
display_frame_height = 4.0
display_frame_minus_x_margin = 5.5
display_frame_center_x = (
    -pcb_length / 2 + display_frame_minus_x_margin + display_frame_length / 2
)
display_frame_center_y = 0.0

display_area_length = 57.5
display_area_width = 43.0
display_recess_depth = 1.0
display_area_minus_x_margin_from_frame = 10.0
display_frame_min_x = display_frame_center_x - display_frame_length / 2
display_area_center_x = (
    display_frame_min_x
    + display_area_minus_x_margin_from_frame
    + display_area_length / 2
)
display_area_center_y = 0.0
display_area_surface_z = pcb_thickness + display_frame_height - display_recess_depth

camera_center_x = -12.0
camera_center_y = 0.0
camera_block_size = 8.0
camera_block_height = 2.5
camera_cylinder_diameter = 8.0
camera_cylinder_height = 2.5
lens_diameter = 2.5
lens_recess_depth = 1.0

gold_finger_length = 7.0
gold_finger_width = pcb_width
gold_finger_thickness = 0.06
gold_finger_center_x = pcb_length / 2 - gold_finger_length / 2
gold_finger_center_y = 0.0


def rounded_plate(length, width, thickness, radius, z_min):
    return (
        cq.Workplane("XY")
        .box(length, width, thickness, centered=(True, True, False))
        .edges("|Z")
        .fillet(radius)
        .translate((0, 0, z_min))
    )


def box_from_z(length, width, height, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .box(length, width, height, centered=(True, True, False))
        .translate((center_x, center_y, z_min))
    )


def cylinder_from_z(diameter, height, center_x, center_y, z_min):
    return (
        cq.Workplane("XY")
        .circle(diameter / 2)
        .extrude(height)
        .translate((center_x, center_y, z_min))
    )


def build_model():
    pcb = rounded_plate(
        pcb_length,
        pcb_width,
        pcb_thickness,
        pcb_corner_radius,
        0,
    )

    top_gold_finger = rounded_plate(
        gold_finger_length,
        gold_finger_width,
        gold_finger_thickness,
        pcb_corner_radius,
        pcb_thickness,
    ).translate((gold_finger_center_x, gold_finger_center_y, 0))
    bottom_gold_finger = rounded_plate(
        gold_finger_length,
        gold_finger_width,
        gold_finger_thickness,
        pcb_corner_radius,
        -gold_finger_thickness,
    ).translate((gold_finger_center_x, gold_finger_center_y, 0))

    display_frame = box_from_z(
        display_frame_length,
        display_frame_width,
        display_frame_height,
        display_frame_center_x,
        display_frame_center_y,
        pcb_thickness,
    )
    display_recess_cutter = box_from_z(
        display_area_length,
        display_area_width,
        display_recess_depth + 0.2,
        display_area_center_x,
        display_area_center_y,
        display_area_surface_z,
    )
    display_frame = display_frame.cut(display_recess_cutter)
    display_area_surface = box_from_z(
        display_area_length,
        display_area_width,
        0.12,
        display_area_center_x,
        display_area_center_y,
        display_area_surface_z,
    )

    camera_block = box_from_z(
        camera_block_size,
        camera_block_size,
        camera_block_height,
        camera_center_x,
        camera_center_y,
        -camera_block_height,
    )
    camera_cylinder_z_min = -camera_block_height - camera_cylinder_height
    camera_cylinder = cylinder_from_z(
        camera_cylinder_diameter,
        camera_cylinder_height,
        camera_center_x,
        camera_center_y,
        camera_cylinder_z_min,
    )
    lens_recess_cutter = cylinder_from_z(
        lens_diameter,
        lens_recess_depth + 0.2,
        camera_center_x,
        camera_center_y,
        camera_cylinder_z_min,
    )
    camera_cylinder = camera_cylinder.cut(lens_recess_cutter)
    lens_surface = cylinder_from_z(
        lens_diameter,
        0.08,
        camera_center_x,
        camera_center_y,
        camera_cylinder_z_min + lens_recess_depth,
    )

    return (
        pcb
        .union(top_gold_finger)
        .union(bottom_gold_finger)
        .union(display_frame)
        .union(display_area_surface)
        .union(camera_block)
        .union(camera_cylinder)
        .union(lens_surface)
    )


result = build_model()

if "show_object" in globals():
    show_object(result, name=hardware_name)
