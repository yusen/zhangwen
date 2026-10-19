import cadquery as cq
import math

# ZW-CAD-intent deterministic template: unihiker_photo_album_v1
# Backend template library model, not LLM-authored CAD code.
# Units: millimeters.
# Project model map for natural-language edits:
# - photo_album_body -> base_part; it contains the flat base, display slope, clips, holes, and supports.
# - photo_album_body.slope_front -> the large outward display slope, not lid_part.
#   Surface frame: normal=(sin(60deg), 0, cos(60deg)); text horizontal follows +Y.
# - lid_part is intentionally empty because this product is a one-piece printable body.
# Keep these stable IDs in project/model-index.json when creating a project copy.

base_length_x = 52.08
base_width_y = 83.0
base_thickness_z = 5.0

slope_face_length = 65.5
slope_thickness = 5.0
slope_angle_deg = 60.0
slope_width_y = base_width_y
slope_anchor_x = base_length_x / 2.0
slope_offset_y = slope_width_y
cut_epsilon = 0.05
cut_overlap_y = 1.0
visible_slope_center_y = slope_offset_y - slope_width_y
base_exposure_cutter_width_y = base_width_y + 2.0 * cut_overlap_y
base_exposure_cutter_center_y = visible_slope_center_y
slope_cutter_width_y = slope_width_y + 2.0 * cut_overlap_y
slope_cutter_center_y = visible_slope_center_y
clip_perpendicular_thickness = 4.0
clip_perpendicular_length = 15.6
clip_parallel_thickness = 3.0
clip_parallel_length = 7.8
clip_offset_from_slope_top = 51.5
clip_width_y = slope_width_y
clip_center_y = visible_slope_center_y
side_block_y_depth = 7.0
side_block_parallel_extension = 51.5
inner_side_block_normal_length = 5.9
outer_side_block_normal_length = 4.7
side_block_gap_between_blocks = 2.0
side_block_union_overlap = 0.05
side_block_y_max = base_width_y / 2.0
side_block_y_min = side_block_y_max - side_block_y_depth
side_block_y_center = (side_block_y_min + side_block_y_max) / 2.0
outer_side_block_start_n = inner_side_block_normal_length + side_block_gap_between_blocks
outer_side_block_end_n = outer_side_block_start_n + outer_side_block_normal_length
plus_y_slope_back_cover_y_depth = 7.0
plus_y_slope_back_cover_y_max = base_width_y / 2.0
plus_y_slope_back_cover_y_min = plus_y_slope_back_cover_y_max - plus_y_slope_back_cover_y_depth
plus_y_slope_back_cover_y_center = (plus_y_slope_back_cover_y_min + plus_y_slope_back_cover_y_max) / 2.0
plus_y_slope_back_cover_s_min = -5.0
plus_y_slope_back_cover_s_max = 0.0
plus_y_slope_back_cover_n_min = -slope_thickness
plus_y_slope_back_cover_n_max = outer_side_block_end_n
plus_y_slope_back_cover_normal_length = plus_y_slope_back_cover_n_max - plus_y_slope_back_cover_n_min
rear_slope_block_y_length = 54.5
rear_slope_block_y_max = base_width_y / 2.0
rear_slope_block_y_min = rear_slope_block_y_max - rear_slope_block_y_length
rear_slope_block_y_center = (rear_slope_block_y_min + rear_slope_block_y_max) / 2.0
rear_slope_block_offset_from_slope_top = 1.0
rear_slope_block_s_min = rear_slope_block_offset_from_slope_top
rear_slope_block_s_length = 34.0
rear_slope_block_s_max = rear_slope_block_s_min + rear_slope_block_s_length
rear_slope_block_s_center = (rear_slope_block_s_min + rear_slope_block_s_max) / 2.0
rear_slope_block_n_max = -slope_thickness
rear_slope_block_normal_thickness = 8.5
rear_slope_block_n_min = rear_slope_block_n_max - rear_slope_block_normal_thickness
rear_slope_block_n_center = (rear_slope_block_n_min + rear_slope_block_n_max) / 2.0
rear_slope_top_slot_y_length = 49.0
rear_slope_top_slot_y_center = rear_slope_block_y_center
rear_slope_top_slot_y_min = rear_slope_top_slot_y_center - rear_slope_top_slot_y_length / 2.0
rear_slope_top_slot_y_max = rear_slope_top_slot_y_center + rear_slope_top_slot_y_length / 2.0
rear_slope_top_slot_width_n = 6.5
rear_slope_top_slot_n_max = rear_slope_block_n_max
rear_slope_top_slot_n_min = rear_slope_top_slot_n_max - rear_slope_top_slot_width_n
rear_slope_top_slot_center_n = (rear_slope_top_slot_n_min + rear_slope_top_slot_n_max) / 2.0
rear_slope_top_slot_cut_depth_s = 32.0
rear_slope_top_slot_surface_s = rear_slope_block_s_min
rear_slope_top_slot_s_min = rear_slope_top_slot_surface_s
rear_slope_top_slot_s_max = rear_slope_top_slot_s_min + rear_slope_top_slot_cut_depth_s
rear_slope_top_slot_s_center = (rear_slope_top_slot_s_min + rear_slope_top_slot_s_max) / 2.0
rear_slope_top_slot_cutter_overlap_s = 0.05
rear_slope_top_slot_cutter_s_min = rear_slope_top_slot_s_min - rear_slope_top_slot_cutter_overlap_s
rear_slope_top_slot_cutter_s_max = rear_slope_top_slot_s_max
rear_slope_top_slot_cutter_size_s = rear_slope_top_slot_cutter_s_max - rear_slope_top_slot_cutter_s_min
rear_slope_top_slot_cutter_center_s = (rear_slope_top_slot_cutter_s_min + rear_slope_top_slot_cutter_s_max) / 2.0
slope_square_hole_size = 12.0
slope_square_hole_center_s = 25.75
slope_square_hole_offset_from_minus_y = 22.5
slope_square_hole_center_y = -base_width_y / 2.0 + slope_square_hole_offset_from_minus_y
slope_square_hole_s_min = slope_square_hole_center_s - slope_square_hole_size / 2.0
slope_square_hole_s_max = slope_square_hole_center_s + slope_square_hole_size / 2.0
slope_square_hole_y_min = slope_square_hole_center_y - slope_square_hole_size / 2.0
slope_square_hole_y_max = slope_square_hole_center_y + slope_square_hole_size / 2.0
slope_square_hole_cutter_normal_padding = 1.0
slope_square_hole_cutter_normal_depth = slope_thickness + 2.0 * slope_square_hole_cutter_normal_padding
slope_square_hole_cutter_center_n = -slope_thickness / 2.0
slope_square_hole_cutter_min_n = slope_square_hole_cutter_center_n - slope_square_hole_cutter_normal_depth / 2.0
slope_square_hole_cutter_max_n = slope_square_hole_cutter_center_n + slope_square_hole_cutter_normal_depth / 2.0
narrow_stop_semicircle_diameter = 10.0
narrow_stop_semicircle_radius = 5.0
narrow_stop_semicircle_offset_from_lip_top_edge_s = 23.85
narrow_stop_semicircle_clip_parallel_top_edge_s = clip_offset_from_slope_top - clip_parallel_length
narrow_stop_semicircle_center_s = narrow_stop_semicircle_clip_parallel_top_edge_s - narrow_stop_semicircle_offset_from_lip_top_edge_s
narrow_stop_semicircle_center_y = base_width_y / 2.0
narrow_stop_semicircle_center_n = outer_side_block_end_n
narrow_stop_semicircle_s_min = narrow_stop_semicircle_center_s - narrow_stop_semicircle_radius
narrow_stop_semicircle_s_max = narrow_stop_semicircle_center_s + narrow_stop_semicircle_radius
narrow_stop_semicircle_y_min = narrow_stop_semicircle_center_y - narrow_stop_semicircle_radius
narrow_stop_semicircle_y_max = narrow_stop_semicircle_center_y
narrow_stop_semicircle_cut_depth_n = 12.6
narrow_stop_semicircle_cutter_overlap_n = 0.05
narrow_stop_semicircle_cutter_min_n = narrow_stop_semicircle_center_n - narrow_stop_semicircle_cut_depth_n - narrow_stop_semicircle_cutter_overlap_n
narrow_stop_semicircle_cutter_max_n = narrow_stop_semicircle_center_n + narrow_stop_semicircle_cutter_overlap_n
narrow_stop_semicircle_cutter_depth_n = narrow_stop_semicircle_cutter_max_n - narrow_stop_semicircle_cutter_min_n
narrow_stop_semicircle_cutter_center_n = (narrow_stop_semicircle_cutter_min_n + narrow_stop_semicircle_cutter_max_n) / 2.0
narrow_stop_semicircle_segments = 32
rear_slope_block_low_contact_fillet_radius = 8.5
rear_slope_block_low_contact_filler_segments = 24
rear_slope_block_low_contact_filler_s_min = rear_slope_block_s_max
rear_slope_block_low_contact_filler_s_max = rear_slope_block_low_contact_filler_s_min + rear_slope_block_low_contact_fillet_radius
rear_slope_block_low_contact_filler_n_max = rear_slope_block_n_max
rear_slope_block_low_contact_filler_n_min = rear_slope_block_low_contact_filler_n_max - rear_slope_block_low_contact_fillet_radius
rear_slope_block_low_contact_filler_arc_center_s = rear_slope_block_low_contact_filler_s_max
rear_slope_block_low_contact_filler_arc_center_n = rear_slope_block_low_contact_filler_n_min
rear_slope_block_low_contact_filler_overlap = cut_epsilon
rear_slope_block_low_contact_filler_width_y = rear_slope_block_y_length
rear_slope_block_low_contact_filler_center_y = rear_slope_block_y_center
stage_9_2_1_tangent_cut_radius = 3.0
stage_9_2_1_tangent_cut_segments = 24
stage_9_2_1_tangent_cut_width_y = base_width_y + 2.0 * cut_overlap_y
stage_9_2_1_tangent_cut_center_y = visible_slope_center_y
stage_9_2_1_tangent_cut_aggressive_bottom_x_overlap = 1.0
stage_9_2_1_tangent_cut_bottom_z_overlap = cut_epsilon
stage_9_2_1_break_face_cleanup_x_min_margin = 3.0
stage_9_2_1_break_face_cleanup_x_max_margin = 0.35
stage_9_2_1_break_face_cleanup_offset_x = 7.0
stage_9_2_1_break_face_cleanup_z_min = -1.0
stage_9_2_1_break_face_cleanup_z_top_extra = 4.0
stage_9_2_1_break_face_cleanup_width_y = base_width_y + 2.0 * cut_overlap_y
stage_9_2_1_break_face_cleanup_center_y = visible_slope_center_y
stage_9_2_2_base_slope_back_fillet_radius = 3.0
stage_9_2_2_base_slope_back_fillet_segments = 24
stage_9_2_2_base_slope_back_filler_width_y = base_width_y
stage_9_2_2_base_slope_back_filler_center_y = visible_slope_center_y
stage_9_2_2_base_slope_back_filler_overlap = cut_epsilon
stage_9_2_3_l_clip_slope_fillet_radius = 3.0
stage_9_2_3_l_clip_slope_fillet_segments = 24
stage_9_2_3_l_clip_slope_edge_s = clip_offset_from_slope_top + clip_perpendicular_thickness
stage_9_2_3_l_clip_slope_edge_n = 0.0
stage_9_2_3_l_clip_slope_filler_width_y = clip_width_y
stage_9_2_3_l_clip_slope_filler_center_y = clip_center_y
stage_9_2_3_l_clip_slope_filler_overlap = cut_epsilon
stage_9_2_4_l_clip_outer_corner_fillet_radius = 3.0
stage_9_2_4_l_clip_outer_corner_fillet_segments = 24
stage_9_2_4_l_clip_outer_corner_edge_s = clip_offset_from_slope_top + clip_perpendicular_thickness
stage_9_2_4_l_clip_outer_corner_edge_n = clip_perpendicular_length
stage_9_2_4_l_clip_outer_corner_width_y = clip_width_y
stage_9_2_4_l_clip_outer_corner_center_y = clip_center_y
stage_9_2_4_l_clip_outer_corner_overlap = cut_epsilon
stage_9_3_edge_fillet_radius = 10.0
stage_9_3_edge_fillet_segments = 32
stage_9_3_edge_fillet_overlap = cut_epsilon
stage_9_3_base_minus_x_edge_length_z = base_thickness_z
stage_9_3_slope_minus_y_plus_z_edge_length_n = slope_thickness
stage_9_3_slope_minus_y_plus_z_cutter_depth_n = slope_thickness + 2.0 * stage_9_3_edge_fillet_overlap
stage_9_3_slope_minus_y_plus_z_cutter_center_n = -slope_thickness / 2.0
stage_9_4_square_hole_corner_fillet_radius = 1.5
stage_9_4_square_hole_corner_fillet_segments = 16
stage_9_4_square_hole_corner_filler_overlap = cut_epsilon
stage_9_4_square_hole_corner_filler_depth_n = slope_thickness
stage_9_4_square_hole_corner_filler_center_n = -slope_thickness / 2.0
stage_9_5_rear_top_slot_plus_y_edge_fillet_radius = 2.0
stage_9_5_rear_top_slot_plus_y_edge_segments = 20
stage_9_5_rear_top_slot_plus_y_edge_s = rear_slope_block_s_min
stage_9_5_rear_top_slot_plus_y_edge_n = rear_slope_block_n_max
stage_9_5_rear_top_slot_plus_y_edge_y_min = rear_slope_top_slot_y_max
stage_9_5_rear_top_slot_plus_y_edge_y_max = rear_slope_block_y_max
stage_9_5_rear_top_slot_plus_y_edge_y_overlap = cut_epsilon
stage_9_5_rear_top_slot_plus_y_edge_width_y = (
    stage_9_5_rear_top_slot_plus_y_edge_y_max
    - stage_9_5_rear_top_slot_plus_y_edge_y_min
    + stage_9_5_rear_top_slot_plus_y_edge_y_overlap
)
stage_9_5_rear_top_slot_plus_y_edge_center_y = (
    stage_9_5_rear_top_slot_plus_y_edge_y_min
    - stage_9_5_rear_top_slot_plus_y_edge_y_overlap
    + stage_9_5_rear_top_slot_plus_y_edge_y_max
) / 2.0
stage_9_5_rear_top_slot_plus_y_edge_overlap = cut_epsilon

def make_triangular_prism_xz(points, width_y, offset_y=0.0):
    return (
        cq.Workplane("XZ")
        .polyline(points)
        .close()
        .extrude(width_y)
        .translate((0.0, offset_y - width_y / 2.0, 0.0))
    )


def make_centered_prism_xz(points, width_y, center_y=0.0):
    return (
        cq.Workplane("XZ")
        .polyline(points)
        .close()
        .extrude(width_y)
        .translate((0.0, center_y + width_y / 2.0, 0.0))
    )


def make_centered_triangular_prism_xz(points, width_y, center_y=0.0):
    return (
        cq.Workplane("XZ")
        .polyline(points)
        .close()
        .extrude(width_y)
        .translate((0.0, center_y + width_y / 2.0, 0.0))
    )


def make_photo_album_base_plus_x_tangent_arc_cut_profile_points():
    radius = stage_9_2_1_tangent_cut_radius
    angle = math.radians(slope_angle_deg)
    corner_x = base_length_x / 2.0
    corner_z = 0.0

    bottom_dir_x, bottom_dir_z = -1.0, 0.0
    slope_dir_x, slope_dir_z = -math.cos(angle), math.sin(angle)
    bisector_x = bottom_dir_x + slope_dir_x
    bisector_z = bottom_dir_z + slope_dir_z
    bisector_len = math.hypot(bisector_x, bisector_z)
    bisector_x /= bisector_len
    bisector_z /= bisector_len

    tangent_distance = radius / math.tan(angle / 2.0)
    center_distance = radius / math.sin(angle / 2.0)
    arc_center_x = corner_x + bisector_x * center_distance
    arc_center_z = corner_z + bisector_z * center_distance

    bottom_tangent = (
        corner_x + bottom_dir_x * tangent_distance,
        corner_z + bottom_dir_z * tangent_distance,
    )
    slope_tangent = (
        corner_x + slope_dir_x * tangent_distance,
        corner_z + slope_dir_z * tangent_distance,
    )
    start_angle = math.atan2(bottom_tangent[1] - arc_center_z, bottom_tangent[0] - arc_center_x)
    end_angle = math.atan2(slope_tangent[1] - arc_center_z, slope_tangent[0] - arc_center_x)

    slope_bottom_depth_z = abs(math.cos(angle) * slope_thickness)
    slope_lower_face_run_x = slope_bottom_depth_z / math.tan(angle)
    slope_bottom_left_x = corner_x - math.sin(angle) * slope_thickness - slope_lower_face_run_x
    aggressive_bottom_point = (
        slope_bottom_left_x - stage_9_2_1_tangent_cut_aggressive_bottom_x_overlap,
        corner_z - stage_9_2_1_tangent_cut_bottom_z_overlap,
    )

    profile_points = [(corner_x, corner_z), aggressive_bottom_point, bottom_tangent]
    for index in range(1, stage_9_2_1_tangent_cut_segments + 1):
        arc_angle = start_angle + (end_angle - start_angle) * index / stage_9_2_1_tangent_cut_segments
        profile_points.append((
            arc_center_x + math.cos(arc_angle) * radius,
            arc_center_z + math.sin(arc_angle) * radius,
        ))
    return profile_points


def make_photo_album_base_plus_x_tangent_arc_cutter():
    return make_centered_prism_xz(
        make_photo_album_base_plus_x_tangent_arc_cut_profile_points(),
        stage_9_2_1_tangent_cut_width_y,
        stage_9_2_1_tangent_cut_center_y,
    )


def make_photo_album_base_plus_x_break_face_cleanup_cutter():
    radius = stage_9_2_1_tangent_cut_radius
    angle = math.radians(slope_angle_deg)
    corner_x = base_length_x / 2.0
    corner_z = 0.0

    tangent_distance = radius / math.tan(angle / 2.0)
    bottom_tangent_x = corner_x - tangent_distance
    slope_tangent_z = math.sin(angle) * tangent_distance

    slope_bottom_depth_z = abs(math.cos(angle) * slope_thickness)
    slope_lower_face_run_x = slope_bottom_depth_z / math.tan(angle)
    slope_bottom_left_x = corner_x - math.sin(angle) * slope_thickness - slope_lower_face_run_x

    x_min = slope_bottom_left_x - stage_9_2_1_break_face_cleanup_x_min_margin + stage_9_2_1_break_face_cleanup_offset_x
    x_max = bottom_tangent_x + stage_9_2_1_break_face_cleanup_x_max_margin + stage_9_2_1_break_face_cleanup_offset_x
    z_min = stage_9_2_1_break_face_cleanup_z_min
    z_max = corner_z + slope_tangent_z + stage_9_2_1_break_face_cleanup_z_top_extra
    profile_points = [
        (x_min, z_min),
        (x_max, z_min),
        (x_max, z_max),
        (x_min, z_max),
    ]
    return make_centered_prism_xz(
        profile_points,
        stage_9_2_1_break_face_cleanup_width_y,
        stage_9_2_1_break_face_cleanup_center_y,
    )
def make_photo_album_base_slope_back_r3_filler_profile_points():
    radius = stage_9_2_2_base_slope_back_fillet_radius
    overlap = stage_9_2_2_base_slope_back_filler_overlap
    angle = math.radians(slope_angle_deg)

    edge_s = (
        math.sin(angle) * slope_face_length
        - math.cos(angle) * slope_thickness
        - base_thickness_z
    ) / math.sin(angle)
    edge_x, edge_z = slope_surface_point_from_top(edge_s, -slope_thickness)

    base_dir_x, base_dir_z = -1.0, 0.0
    slope_back_up_dir_x, slope_back_up_dir_z = -math.cos(angle), math.sin(angle)
    bisector_x = base_dir_x + slope_back_up_dir_x
    bisector_z = base_dir_z + slope_back_up_dir_z
    bisector_len = math.hypot(bisector_x, bisector_z)
    bisector_x /= bisector_len
    bisector_z /= bisector_len

    corner_angle = math.acos(base_dir_x * slope_back_up_dir_x + base_dir_z * slope_back_up_dir_z)
    tangent_distance = radius / math.tan(corner_angle / 2.0)
    center_distance = radius / math.sin(corner_angle / 2.0)
    arc_center_x = edge_x + bisector_x * center_distance
    arc_center_z = edge_z + bisector_z * center_distance

    base_tangent = (
        edge_x + base_dir_x * tangent_distance,
        edge_z + base_dir_z * tangent_distance,
    )
    slope_tangent = (
        edge_x + slope_back_up_dir_x * tangent_distance,
        edge_z + slope_back_up_dir_z * tangent_distance,
    )
    start_angle = math.atan2(base_tangent[1] - arc_center_z, base_tangent[0] - arc_center_x)
    end_angle = math.atan2(slope_tangent[1] - arc_center_z, slope_tangent[0] - arc_center_x)
    if end_angle < start_angle:
        end_angle += 2.0 * math.pi

    edge_overlap = (
        edge_x - bisector_x * overlap,
        edge_z - bisector_z * overlap,
    )
    profile_points = [edge_overlap, base_tangent]
    for index in range(1, stage_9_2_2_base_slope_back_fillet_segments + 1):
        arc_angle = start_angle + (end_angle - start_angle) * index / stage_9_2_2_base_slope_back_fillet_segments
        profile_points.append((
            arc_center_x + math.cos(arc_angle) * radius,
            arc_center_z + math.sin(arc_angle) * radius,
        ))
    return profile_points


def make_photo_album_base_slope_back_r3_filler():
    return make_centered_prism_xz(
        make_photo_album_base_slope_back_r3_filler_profile_points(),
        stage_9_2_2_base_slope_back_filler_width_y,
        stage_9_2_2_base_slope_back_filler_center_y,
    )

def make_photo_album_l_clip_slope_lower_r3_filler_profile_points():
    radius = stage_9_2_3_l_clip_slope_fillet_radius
    segments = stage_9_2_3_l_clip_slope_fillet_segments
    overlap = stage_9_2_3_l_clip_slope_filler_overlap
    edge_s = stage_9_2_3_l_clip_slope_edge_s
    edge_n = stage_9_2_3_l_clip_slope_edge_n
    arc_center_s = edge_s + radius
    arc_center_n = edge_n + radius

    local_points = [
        (edge_s - overlap, edge_n - overlap),
        (arc_center_s, edge_n - overlap),
        (arc_center_s, edge_n),
    ]
    for index in range(1, segments + 1):
        angle = -math.pi / 2.0 - math.pi * index / (2.0 * segments)
        local_points.append((
            arc_center_s + math.cos(angle) * radius,
            arc_center_n + math.sin(angle) * radius,
        ))
    local_points.append((edge_s - overlap, arc_center_n))

    return [
        slope_surface_point_from_top(distance_s, normal_offset)
        for distance_s, normal_offset in local_points
    ]


def make_photo_album_l_clip_slope_lower_r3_filler():
    return make_centered_prism_xz(
        make_photo_album_l_clip_slope_lower_r3_filler_profile_points(),
        stage_9_2_3_l_clip_slope_filler_width_y,
        stage_9_2_3_l_clip_slope_filler_center_y,
    )

def make_photo_album_l_clip_outer_corner_r3_cutter_profile_points():
    radius = stage_9_2_4_l_clip_outer_corner_fillet_radius
    segments = stage_9_2_4_l_clip_outer_corner_fillet_segments
    overlap = stage_9_2_4_l_clip_outer_corner_overlap
    edge_s = stage_9_2_4_l_clip_outer_corner_edge_s
    edge_n = stage_9_2_4_l_clip_outer_corner_edge_n
    arc_center_s = edge_s - radius
    arc_center_n = edge_n - radius

    local_points = [
        (edge_s + overlap, edge_n + overlap),
        (edge_s + overlap, edge_n - radius),
        (edge_s, edge_n - radius),
    ]
    for index in range(1, segments + 1):
        angle = math.pi * index / (2.0 * segments)
        local_points.append((
            arc_center_s + math.cos(angle) * radius,
            arc_center_n + math.sin(angle) * radius,
        ))
    local_points.append((edge_s - radius, edge_n + overlap))

    return [
        slope_surface_point_from_top(distance_s, normal_offset)
        for distance_s, normal_offset in local_points
    ]


def make_photo_album_l_clip_outer_corner_r3_cutter():
    return make_centered_prism_xz(
        make_photo_album_l_clip_outer_corner_r3_cutter_profile_points(),
        stage_9_2_4_l_clip_outer_corner_width_y,
        stage_9_2_4_l_clip_outer_corner_center_y,
    )

def make_photo_album_base_minus_x_vertical_edge_r10_cutter(y_sign):
    radius = stage_9_3_edge_fillet_radius
    segments = stage_9_3_edge_fillet_segments
    overlap = stage_9_3_edge_fillet_overlap
    x_edge = -base_length_x / 2.0
    y_edge = y_sign * base_width_y / 2.0

    if y_sign > 0:
        arc_center_x = x_edge + radius
        arc_center_y = y_edge - radius
        profile_points = [
            (x_edge - overlap, y_edge + overlap),
            (x_edge - overlap, y_edge - radius),
            (x_edge, y_edge - radius),
        ]
        start_angle = math.pi
        end_angle = math.pi / 2.0
        tail_point = (x_edge + radius, y_edge + overlap)
    else:
        arc_center_x = x_edge + radius
        arc_center_y = y_edge + radius
        profile_points = [
            (x_edge - overlap, y_edge - overlap),
            (x_edge - overlap, y_edge + radius),
            (x_edge, y_edge + radius),
        ]
        start_angle = math.pi
        end_angle = 3.0 * math.pi / 2.0
        tail_point = (x_edge + radius, y_edge - overlap)

    for index in range(1, segments + 1):
        angle = start_angle + (end_angle - start_angle) * index / segments
        profile_points.append((
            arc_center_x + math.cos(angle) * radius,
            arc_center_y + math.sin(angle) * radius,
        ))
    profile_points.append(tail_point)

    return (
        cq.Workplane("XY")
        .polyline(profile_points)
        .close()
        .extrude(stage_9_3_base_minus_x_edge_length_z + 2.0 * overlap)
        .translate((0.0, 0.0, -overlap))
    )


def make_photo_album_base_minus_x_vertical_edge_r10_cutters():
    minus_y_cutter = make_photo_album_base_minus_x_vertical_edge_r10_cutter(-1.0)
    plus_y_cutter = make_photo_album_base_minus_x_vertical_edge_r10_cutter(1.0)
    return minus_y_cutter.union(plus_y_cutter)


def make_slope_local_sy_prism(profile_points, center_s, center_y, center_n, depth_n):
    local_points = [
        (distance_s - center_s, point_y - center_y)
        for distance_s, point_y in profile_points
    ]
    center_x, center_z = slope_surface_point_from_top(center_s, center_n)
    return (
        cq.Workplane("XY")
        .polyline(local_points)
        .close()
        .extrude(depth_n)
        .translate((0.0, 0.0, -depth_n / 2.0))
        .rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), slope_angle_deg)
        .translate((center_x, center_y, center_z))
    )


def make_photo_album_slope_minus_y_plus_z_edge_r10_cutter_profile_points():
    radius = stage_9_3_edge_fillet_radius
    segments = stage_9_3_edge_fillet_segments
    overlap = stage_9_3_edge_fillet_overlap
    edge_s = 0.0
    edge_y = -base_width_y / 2.0
    arc_center_s = edge_s + radius
    arc_center_y = edge_y + radius

    profile_points = [
        (edge_s - overlap, edge_y - overlap),
        (edge_s - overlap, edge_y + radius),
        (edge_s, edge_y + radius),
    ]
    for index in range(1, segments + 1):
        angle = math.pi + math.pi * index / (2.0 * segments)
        profile_points.append((
            arc_center_s + math.cos(angle) * radius,
            arc_center_y + math.sin(angle) * radius,
        ))
    profile_points.append((edge_s + radius, edge_y - overlap))
    return profile_points


def make_photo_album_slope_minus_y_plus_z_edge_r10_cutter():
    profile_points = make_photo_album_slope_minus_y_plus_z_edge_r10_cutter_profile_points()
    s_values = [point[0] for point in profile_points]
    y_values = [point[1] for point in profile_points]
    center_s = (min(s_values) + max(s_values)) / 2.0
    center_y = (min(y_values) + max(y_values)) / 2.0
    return make_slope_local_sy_prism(
        profile_points,
        center_s,
        center_y,
        stage_9_3_slope_minus_y_plus_z_cutter_center_n,
        stage_9_3_slope_minus_y_plus_z_cutter_depth_n,
    )

def make_photo_album_square_hole_corner_r15_filler_profile_points(corner_s, corner_y, direction_s, direction_y):
    radius = stage_9_4_square_hole_corner_fillet_radius
    segments = stage_9_4_square_hole_corner_fillet_segments
    overlap = stage_9_4_square_hole_corner_filler_overlap
    arc_center_s = corner_s + direction_s * radius
    arc_center_y = corner_y + direction_y * radius

    start_angle = math.atan2(-direction_y * radius, 0.0)
    end_angle = math.atan2(0.0, -direction_s * radius)
    delta_angle = end_angle - start_angle
    while delta_angle > math.pi:
        delta_angle -= 2.0 * math.pi
    while delta_angle < -math.pi:
        delta_angle += 2.0 * math.pi

    profile_points = [
        (corner_s - direction_s * overlap, corner_y - direction_y * overlap),
        (arc_center_s, corner_y - direction_y * overlap),
        (arc_center_s, corner_y),
    ]
    for index in range(1, segments + 1):
        angle = start_angle + delta_angle * index / segments
        profile_points.append((
            arc_center_s + math.cos(angle) * radius,
            arc_center_y + math.sin(angle) * radius,
        ))
    profile_points.append((corner_s - direction_s * overlap, arc_center_y))
    return profile_points


def make_photo_album_square_hole_corner_r15_filler(corner_s, corner_y, direction_s, direction_y):
    profile_points = make_photo_album_square_hole_corner_r15_filler_profile_points(
        corner_s,
        corner_y,
        direction_s,
        direction_y,
    )
    s_values = [point[0] for point in profile_points]
    y_values = [point[1] for point in profile_points]
    center_s = (min(s_values) + max(s_values)) / 2.0
    center_y = (min(y_values) + max(y_values)) / 2.0
    return make_slope_local_sy_prism(
        profile_points,
        center_s,
        center_y,
        stage_9_4_square_hole_corner_filler_center_n,
        stage_9_4_square_hole_corner_filler_depth_n,
    )


def make_photo_album_square_hole_corner_r15_fillers():
    lower_left = make_photo_album_square_hole_corner_r15_filler(
        slope_square_hole_s_min,
        slope_square_hole_y_min,
        1.0,
        1.0,
    )
    lower_right = make_photo_album_square_hole_corner_r15_filler(
        slope_square_hole_s_max,
        slope_square_hole_y_min,
        -1.0,
        1.0,
    )
    upper_left = make_photo_album_square_hole_corner_r15_filler(
        slope_square_hole_s_min,
        slope_square_hole_y_max,
        1.0,
        -1.0,
    )
    upper_right = make_photo_album_square_hole_corner_r15_filler(
        slope_square_hole_s_max,
        slope_square_hole_y_max,
        -1.0,
        -1.0,
    )
    return lower_left.union(lower_right).union(upper_left).union(upper_right)

def make_photo_album_rear_top_slot_plus_y_edge_r2_filler_profile_points():
    radius = stage_9_5_rear_top_slot_plus_y_edge_fillet_radius
    segments = stage_9_5_rear_top_slot_plus_y_edge_segments
    edge_s = stage_9_5_rear_top_slot_plus_y_edge_s
    edge_n = stage_9_5_rear_top_slot_plus_y_edge_n
    overlap = stage_9_5_rear_top_slot_plus_y_edge_overlap
    arc_center_s = edge_s - radius
    arc_center_n = edge_n - radius

    local_points = [
        (edge_s + overlap, edge_n + overlap),
        (arc_center_s, edge_n + overlap),
        (arc_center_s, edge_n),
    ]
    for index in range(1, segments + 1):
        angle = math.pi / 2.0 - math.pi * index / (2.0 * segments)
        local_points.append((
            arc_center_s + math.cos(angle) * radius,
            arc_center_n + math.sin(angle) * radius,
        ))
    local_points.append((edge_s + overlap, edge_n - radius))

    return [
        slope_surface_point_from_top(distance_s, normal_offset)
        for distance_s, normal_offset in local_points
    ]


def make_photo_album_rear_top_slot_plus_y_edge_r2_filler():
    return make_centered_prism_xz(
        make_photo_album_rear_top_slot_plus_y_edge_r2_filler_profile_points(),
        stage_9_5_rear_top_slot_plus_y_edge_width_y,
        stage_9_5_rear_top_slot_plus_y_edge_center_y,
    )

def cut_base_slope_exposure(base):
    angle = math.radians(slope_angle_deg)
    cut_run_x = base_thickness_z / math.tan(angle)

    cutter_points = [
        (slope_anchor_x + cut_epsilon, -cut_epsilon),
        (slope_anchor_x + cut_epsilon, base_thickness_z + cut_epsilon),
        (slope_anchor_x - cut_run_x - cut_epsilon, base_thickness_z + cut_epsilon),
    ]

    cutter = make_centered_triangular_prism_xz(
        cutter_points,
        base_exposure_cutter_width_y,
        base_exposure_cutter_center_y,
    )
    return base.cut(cutter)


def cut_slope_bottom_protrusion(slope):
    angle = math.radians(slope_angle_deg)

    normal_x = -math.sin(angle) * slope_thickness
    normal_z = -math.cos(angle) * slope_thickness

    bottom_depth_z = abs(normal_z)
    lower_face_run_x = bottom_depth_z / math.tan(angle)
    cut_start_x = slope_anchor_x + normal_x - lower_face_run_x

    cutter_points = [
        (slope_anchor_x + cut_epsilon, -bottom_depth_z - cut_epsilon),
        (slope_anchor_x + cut_epsilon, cut_epsilon),
        (cut_start_x - cut_epsilon, cut_epsilon),
    ]

    cutter = make_centered_triangular_prism_xz(
        cutter_points,
        slope_cutter_width_y,
        slope_cutter_center_y,
    )
    return slope.cut(cutter)


def cut_final_slope_exposure(result):
    angle = math.radians(slope_angle_deg)
    cut_run_x = base_thickness_z / math.tan(angle)

    cutter_points = [
        (slope_anchor_x + cut_epsilon, -cut_epsilon),
        (slope_anchor_x + cut_epsilon, base_thickness_z + cut_epsilon),
        (slope_anchor_x - cut_run_x - cut_epsilon, base_thickness_z + cut_epsilon),
    ]

    cutter = make_centered_triangular_prism_xz(
        cutter_points,
        base_exposure_cutter_width_y,
        base_exposure_cutter_center_y,
    )
    return result.cut(cutter)


def slope_surface_point_from_top(distance_s, normal_offset=0.0):
    angle = math.radians(slope_angle_deg)
    top_x = slope_anchor_x - math.cos(angle) * slope_face_length
    top_z = math.sin(angle) * slope_face_length
    down_x = math.cos(angle)
    down_z = -math.sin(angle)
    outward_x = math.sin(angle)
    outward_z = math.cos(angle)
    return (
        top_x + down_x * distance_s + outward_x * normal_offset,
        top_z + down_z * distance_s + outward_z * normal_offset,
    )


def make_slope_local_box(center_s, center_y, center_n, size_s, size_y, size_n):
    center_x, center_z = slope_surface_point_from_top(center_s, center_n)
    return (
        cq.Workplane("XY")
        .box(size_s, size_y, size_n, centered=(True, True, True))
        .rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), slope_angle_deg)
        .translate((center_x, center_y, center_z))
    )


def make_semicircle_profile_points(radius, segments):
    return [
        (
            math.cos(math.pi * index / segments) * radius,
            -math.sin(math.pi * index / segments) * radius,
        )
        for index in range(segments + 1)
    ]


def make_slope_local_semicircle_prism(center_s, center_y, center_n, radius, depth_n, segments):
    center_x, center_z = slope_surface_point_from_top(center_s, center_n)
    profile_points = make_semicircle_profile_points(radius, segments)
    return (
        cq.Workplane("XY")
        .polyline(profile_points)
        .close()
        .extrude(depth_n)
        .translate((0.0, 0.0, -depth_n / 2.0))
        .rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), slope_angle_deg)
        .translate((center_x, center_y, center_z))
    )


def rounded_plate(length, width, thickness, radius, z_min):
    plate = (
        cq.Workplane("XY")
        .box(length, width, thickness, centered=(True, True, False))
        .translate((0, 0, z_min))
    )
    try:
        plate = plate.edges("|Z").fillet(radius)
    except Exception:
        pass
    return plate


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
    display_frame_center_y = 0.0
    display_area_length = 57.5
    display_area_width = 43.0
    display_recess_depth = 1.0
    display_area_minus_x_margin_from_frame = 10.0
    display_frame_min_x = display_frame_center_x - display_frame_length / 2.0
    display_area_center_x = display_frame_min_x + display_area_minus_x_margin_from_frame + display_area_length / 2.0
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
    gold_finger_center_x = pcb_length / 2.0 - gold_finger_length / 2.0

    pcb = rounded_plate(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius, 0)
    top_gold_finger = rounded_plate(gold_finger_length, gold_finger_width, gold_finger_thickness, pcb_corner_radius, pcb_thickness).translate((gold_finger_center_x, 0, 0))
    bottom_gold_finger = rounded_plate(gold_finger_length, gold_finger_width, gold_finger_thickness, pcb_corner_radius, -gold_finger_thickness).translate((gold_finger_center_x, 0, 0))
    display_frame = box_from_z(display_frame_length, display_frame_width, display_frame_height, display_frame_center_x, display_frame_center_y, pcb_thickness)
    display_recess_cutter = box_from_z(display_area_length, display_area_width, display_recess_depth + 0.2, display_area_center_x, display_area_center_y, display_area_surface_z)
    display_frame = display_frame.cut(display_recess_cutter)
    display_area_surface = box_from_z(display_area_length, display_area_width, 0.12, display_area_center_x, display_area_center_y, display_area_surface_z)
    camera_block = box_from_z(camera_block_size, camera_block_size, camera_block_height, camera_center_x, camera_center_y, -camera_block_height)
    camera_cylinder_z_min = -camera_block_height - camera_cylinder_height
    camera_cylinder = cylinder_from_z(camera_cylinder_diameter, camera_cylinder_height, camera_center_x, camera_center_y, camera_cylinder_z_min)
    lens_recess_cutter = cylinder_from_z(lens_diameter, lens_recess_depth + 0.2, camera_center_x, camera_center_y, camera_cylinder_z_min)
    camera_cylinder = camera_cylinder.cut(lens_recess_cutter)
    lens_surface = cylinder_from_z(lens_diameter, 0.08, camera_center_x, camera_center_y, camera_cylinder_z_min + lens_recess_depth)
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


def make_battery_wire_stub(center_y, battery_length_x, battery_thickness_z, wire_stub_length_x, wire_stub_diameter):
    return (
        cq.Workplane("YZ")
        .center(center_y, battery_thickness_z / 2.0)
        .circle(wire_stub_diameter / 2.0)
        .extrude(wire_stub_length_x)
        .translate((battery_length_x / 2.0, 0, 0))
    )


def make_unihiker_polymer_lipo_battery():
    battery_length_x = 48.0
    battery_width_y = 32.0
    battery_thickness_z = 6.0
    corner_radius = 2.0
    wire_stub_length_x = 1.0
    wire_stub_diameter = 0.8
    wire_stub_spacing_y = 3.0
    body = (
        cq.Workplane("XY")
        .box(battery_length_x, battery_width_y, battery_thickness_z, centered=(True, True, False))
    )
    try:
        body = body.edges("|Z").fillet(corner_radius)
    except Exception:
        pass
    positive_stub = make_battery_wire_stub(wire_stub_spacing_y / 2.0, battery_length_x, battery_thickness_z, wire_stub_length_x, wire_stub_diameter)
    negative_stub = make_battery_wire_stub(-wire_stub_spacing_y / 2.0, battery_length_x, battery_thickness_z, wire_stub_length_x, wire_stub_diameter)
    return body.union(positive_stub).union(negative_stub)


def make_photo_album_k10_reference():
    k10_pcb_length = 83.2
    k10_pcb_width = 51.3
    k10_pcb_thickness = 1.6
    k10_display_frame_height = 4.0
    k10_gold_finger_length = 7.0
    k10_component_height_bottom_z = 5.0
    k10_bottom_cube_height_z = 2.5
    k10_toward_slope_offset_n = 2.0
    k10_gold_finger_center_x = k10_pcb_length / 2.0 - k10_gold_finger_length / 2.0
    k10_l_clip_perpendicular_top_face_s = clip_offset_from_slope_top
    k10_pcb_down_slope_face_offset_s = k10_pcb_width / 2.0
    k10_origin_s = k10_l_clip_perpendicular_top_face_s - k10_pcb_down_slope_face_offset_s
    k10_pcb_down_slope_face_s = k10_origin_s + k10_pcb_down_slope_face_offset_s
    k10_l_clip_parallel_inner_face_n = clip_perpendicular_length - clip_parallel_thickness
    k10_display_frame_outer_offset_n = k10_pcb_thickness + k10_display_frame_height
    k10_nominal_origin_n = k10_l_clip_parallel_inner_face_n - k10_display_frame_outer_offset_n
    k10_origin_n = k10_nominal_origin_n - k10_toward_slope_offset_n
    k10_display_frame_outer_face_n = k10_origin_n + k10_display_frame_outer_offset_n
    k10_display_frame_clearance_to_l_clip_n = k10_l_clip_parallel_inner_face_n - k10_display_frame_outer_face_n
    k10_slope_surface_n = 0.0
    k10_bottom_cube_lower_face_n = k10_origin_n - k10_bottom_cube_height_z
    k10_bottom_cube_clearance_to_slope_n = k10_bottom_cube_lower_face_n - k10_slope_surface_n
    k10_target_minus_y_face_y = -base_width_y / 2.0
    k10_origin_y = k10_target_minus_y_face_y + k10_pcb_length / 2.0
    k10_origin_x, k10_origin_z = slope_surface_point_from_top(k10_origin_s, k10_origin_n)
    return (
        make_unihiker_k10()
        .rotate((0, 0, 0), (0, 0, 1), 90)
        .rotate((0, 0, 0), (0, 1, 0), slope_angle_deg)
        .translate((k10_origin_x, k10_origin_y, k10_origin_z))
    )


def make_photo_album_polymer_lipo_battery_reference():
    battery_thickness_z = 6.0
    battery_center_s = rear_slope_block_s_center
    battery_center_y = rear_slope_block_y_center
    battery_center_n = rear_slope_block_n_center
    battery_origin_n = battery_center_n - battery_thickness_z / 2.0
    battery_origin_x, battery_origin_z = slope_surface_point_from_top(battery_center_s, battery_origin_n)
    return (
        make_unihiker_polymer_lipo_battery()
        .rotate((0, 0, 0), (0, 0, 1), 90)
        .rotate((0, 0, 0), (0, 1, 0), slope_angle_deg)
        .translate((battery_origin_x, battery_center_y, battery_origin_z))
    )


def make_photo_album_l_clip():
    s0 = clip_offset_from_slope_top
    s1 = s0 + clip_perpendicular_thickness
    lip_s0 = s0 - clip_parallel_length
    outer_n = clip_perpendicular_length
    inner_n = outer_n - clip_parallel_thickness

    profile_points = [
        slope_surface_point_from_top(s0, 0.0),
        slope_surface_point_from_top(s1, 0.0),
        slope_surface_point_from_top(s1, outer_n),
        slope_surface_point_from_top(lip_s0, outer_n),
        slope_surface_point_from_top(lip_s0, inner_n),
        slope_surface_point_from_top(s0, inner_n),
    ]

    return make_centered_prism_xz(profile_points, clip_width_y, clip_center_y)


def make_photo_album_side_block(normal_min, normal_max):
    s0 = clip_offset_from_slope_top - side_block_parallel_extension
    s1 = clip_offset_from_slope_top + side_block_union_overlap

    profile_points = [
        slope_surface_point_from_top(s0, normal_min),
        slope_surface_point_from_top(s1, normal_min),
        slope_surface_point_from_top(s1, normal_max),
        slope_surface_point_from_top(s0, normal_max),
    ]

    return make_centered_prism_xz(profile_points, side_block_y_depth, side_block_y_center)


def make_photo_album_side_stop_blocks():
    inner_block = make_photo_album_side_block(0.0, inner_side_block_normal_length)
    outer_block = make_photo_album_side_block(
        outer_side_block_start_n,
        outer_side_block_end_n,
    )
    return inner_block.union(outer_block)


def make_photo_album_plus_y_slope_back_cover_block():
    profile_points = [
        slope_surface_point_from_top(plus_y_slope_back_cover_s_min, plus_y_slope_back_cover_n_min),
        slope_surface_point_from_top(plus_y_slope_back_cover_s_min, plus_y_slope_back_cover_n_max),
        slope_surface_point_from_top(plus_y_slope_back_cover_s_max, plus_y_slope_back_cover_n_max),
        slope_surface_point_from_top(plus_y_slope_back_cover_s_max, plus_y_slope_back_cover_n_min),
    ]

    return make_centered_prism_xz(
        profile_points,
        plus_y_slope_back_cover_y_depth,
        plus_y_slope_back_cover_y_center,
    )


def make_photo_album_slope_square_hole_cutter():
    return make_slope_local_box(
        slope_square_hole_center_s,
        slope_square_hole_center_y,
        slope_square_hole_cutter_center_n,
        slope_square_hole_size,
        slope_square_hole_size,
        slope_square_hole_cutter_normal_depth,
    )


def make_photo_album_rear_slope_block():
    profile_points = [
        slope_surface_point_from_top(rear_slope_block_s_min, rear_slope_block_n_min),
        slope_surface_point_from_top(rear_slope_block_s_min, rear_slope_block_n_max),
        slope_surface_point_from_top(rear_slope_block_s_max, rear_slope_block_n_max),
        slope_surface_point_from_top(rear_slope_block_s_max, rear_slope_block_n_min),
    ]

    return make_centered_prism_xz(
        profile_points,
        rear_slope_block_y_length,
        rear_slope_block_y_center,
    )


def make_photo_album_rear_slope_top_slot_cutter():
    return make_slope_local_box(
        rear_slope_top_slot_cutter_center_s,
        rear_slope_top_slot_y_center,
        rear_slope_top_slot_center_n,
        rear_slope_top_slot_cutter_size_s,
        rear_slope_top_slot_y_length,
        rear_slope_top_slot_width_n,
    )


def make_photo_album_narrow_stop_semicircle_cutter():
    return make_slope_local_semicircle_prism(
        narrow_stop_semicircle_center_s,
        narrow_stop_semicircle_center_y,
        narrow_stop_semicircle_cutter_center_n,
        narrow_stop_semicircle_radius,
        narrow_stop_semicircle_cutter_depth_n,
        narrow_stop_semicircle_segments,
    )


def make_rear_slope_low_contact_filler_profile_points():
    radius = rear_slope_block_low_contact_fillet_radius
    s_min = rear_slope_block_low_contact_filler_s_min
    n_max = rear_slope_block_low_contact_filler_n_max
    n_min = rear_slope_block_low_contact_filler_n_min
    arc_center_s = rear_slope_block_low_contact_filler_arc_center_s
    arc_center_n = rear_slope_block_low_contact_filler_arc_center_n
    overlap = rear_slope_block_low_contact_filler_overlap

    local_points = [
        (s_min - overlap, n_max + overlap),
        (arc_center_s, n_max + overlap),
        (arc_center_s, n_max),
    ]

    for index in range(1, rear_slope_block_low_contact_filler_segments + 1):
        angle = math.pi / 2.0 + math.pi * index / (2.0 * rear_slope_block_low_contact_filler_segments)
        local_points.append((
            arc_center_s + math.cos(angle) * radius,
            arc_center_n + math.sin(angle) * radius,
        ))

    local_points.append((s_min - overlap, n_min))

    return [
        slope_surface_point_from_top(distance_s, normal_offset)
        for distance_s, normal_offset in local_points
    ]


def make_photo_album_rear_slope_low_contact_filler():
    return make_centered_prism_xz(
        make_rear_slope_low_contact_filler_profile_points(),
        rear_slope_block_low_contact_filler_width_y,
        rear_slope_block_low_contact_filler_center_y,
    )


def make_photo_album_stage_1():
    base = (
        cq.Workplane("XY")
        .box(base_length_x, base_width_y, base_thickness_z, centered=(True, True, False))
    )
    base = cut_base_slope_exposure(base)
    base = base.cut(make_photo_album_base_plus_x_tangent_arc_cutter())
    base = base.cut(make_photo_album_base_plus_x_break_face_cleanup_cutter())

    angle = math.radians(slope_angle_deg)

    start_x = slope_anchor_x
    start_z = 0.0

    end_x = start_x - math.cos(angle) * slope_face_length
    end_z = start_z + math.sin(angle) * slope_face_length

    normal_x = -math.sin(angle) * slope_thickness
    normal_z = -math.cos(angle) * slope_thickness

    bottom_depth_z = abs(normal_z)
    lower_face_run_x = bottom_depth_z / math.tan(angle)

    profile_points = [
        (start_x, start_z),
        (end_x, end_z),
        (end_x + normal_x, end_z + normal_z),
        (start_x + normal_x - lower_face_run_x, start_z),
    ]

    slope = make_triangular_prism_xz(profile_points, slope_width_y, slope_offset_y)
    slope = cut_slope_bottom_protrusion(slope)
    slope = slope.cut(make_photo_album_base_plus_x_tangent_arc_cutter())
    slope = slope.cut(make_photo_album_base_plus_x_break_face_cleanup_cutter())

    result = base.union(slope)
    return cut_final_slope_exposure(result)


def make_photo_album_stage_2():
    result = make_photo_album_stage_1()
    l_clip = make_photo_album_l_clip()
    return result.union(l_clip)


def make_photo_album_stage_3():
    result = make_photo_album_stage_2()
    side_blocks = make_photo_album_side_stop_blocks()
    return result.union(side_blocks)


def make_photo_album_stage_5():
    result = make_photo_album_stage_3()
    plus_y_slope_back_cover = make_photo_album_plus_y_slope_back_cover_block()
    result = result.union(plus_y_slope_back_cover)
    square_hole = make_photo_album_slope_square_hole_cutter()
    return result.cut(square_hole)


def make_photo_album_stage_6():
    result = make_photo_album_stage_5()
    rear_slope_block = make_photo_album_rear_slope_block()
    return result.union(rear_slope_block)


def make_photo_album_stage_7():
    result = make_photo_album_stage_6()
    rear_slope_top_slot = make_photo_album_rear_slope_top_slot_cutter()
    return result.cut(rear_slope_top_slot)


def make_photo_album_stage_8():
    result = make_photo_album_stage_7()
    narrow_stop_semicircle = make_photo_album_narrow_stop_semicircle_cutter()
    return result.cut(narrow_stop_semicircle)


def make_photo_album_stage_9_1():
    result = make_photo_album_stage_8()
    rear_filler = make_photo_album_rear_slope_low_contact_filler()
    return result.union(rear_filler)


def make_photo_album_stage_9_2_1():
    result = make_photo_album_stage_9_1()
    tangent_arc_cutter = make_photo_album_base_plus_x_tangent_arc_cutter()
    result = result.cut(tangent_arc_cutter)
    break_face_cleanup_cutter = make_photo_album_base_plus_x_break_face_cleanup_cutter()
    return result.cut(break_face_cleanup_cutter)


def make_photo_album_stage_9_2_2():
    result = make_photo_album_stage_9_2_1()
    base_slope_back_filler = make_photo_album_base_slope_back_r3_filler()
    return result.union(base_slope_back_filler)


def make_photo_album_stage_9_2_3():
    result = make_photo_album_stage_9_2_2()
    l_clip_slope_filler = make_photo_album_l_clip_slope_lower_r3_filler()
    return result.union(l_clip_slope_filler)


def make_photo_album_stage_9_2_4():
    result = make_photo_album_stage_9_2_3()
    l_clip_outer_corner_cutter = make_photo_album_l_clip_outer_corner_r3_cutter()
    return result.cut(l_clip_outer_corner_cutter)


def make_photo_album_stage_9_3():
    result = make_photo_album_stage_9_2_4()
    base_minus_x_cutters = make_photo_album_base_minus_x_vertical_edge_r10_cutters()
    result = result.cut(base_minus_x_cutters)
    slope_minus_y_plus_z_cutter = make_photo_album_slope_minus_y_plus_z_edge_r10_cutter()
    return result.cut(slope_minus_y_plus_z_cutter)


def make_photo_album_stage_9_4():
    result = make_photo_album_stage_9_3()
    square_hole_corner_fillers = make_photo_album_square_hole_corner_r15_fillers()
    return result.union(square_hole_corner_fillers)


def make_photo_album_stage_9_5():
    result = make_photo_album_stage_9_4()
    rear_top_slot_plus_y_edge_filler = make_photo_album_rear_top_slot_plus_y_edge_r2_filler()
    return result.union(rear_top_slot_plus_y_edge_filler)


def build_hollow_base():
    return make_photo_album_stage_9_5()

def apply_screw_bosses(base_part):
    return base_part


def build_lid():
    return cq.Workplane("XY")


def apply_lid_screw_holes(lid_part):
    return lid_part


def apply_mounts(base_part, lid_part):
    return base_part, lid_part


def build_hardware_references():
    k10_board = make_photo_album_k10_reference()
    polymer_lipo_battery = make_photo_album_polymer_lipo_battery_reference()
    return [k10_board, polymer_lipo_battery]


base_part = build_hollow_base()
base_part = apply_screw_bosses(base_part)
lid_part = build_lid()
lid_part = apply_lid_screw_holes(lid_part)
base_part, lid_part = apply_mounts(base_part, lid_part)
hardware_reference_parts = build_hardware_references()

result = base_part
for hardware_part in hardware_reference_parts:
    result = result.union(hardware_part)

if "show_object" in globals():
    show_object(result, name="unihiker_photo_album_stage_9_5")
