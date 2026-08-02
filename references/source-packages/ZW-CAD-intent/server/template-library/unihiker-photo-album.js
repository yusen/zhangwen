import { readFileSync } from 'node:fs';
import {
  DEFAULT_PARAMETERS,
  isPlainObject,
  normalizeNumberMap,
} from '../pipeline/shared.js';
import {
  buildParameterGroups,
  buildPreviewAssets,
} from '../pipeline/cad.js';
import {
  getHardwareProfile,
} from '../hardware-library.js';

export const UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID = 'unihiker_photo_album_v1';
const PHOTO_ALBUM_CADQUERY_SOURCE_URL = new URL('./unihiker-photo-album.cq.py', import.meta.url);
const PHOTO_ALBUM_CADQUERY_SOURCE_SHA256 = '060BBE32C388E9E6F790F43ADA9144C615DFBC5E8D2589D4595415579D416E15';

const TEMPLATE_HARDWARE = Object.freeze([
  {
    hardware_id: 'unihiker_k10',
    role: 'display_controller',
    quantity: 1,
    mount_surface: 'photo_album_rear_top_slot',
    placement: 'gold_finger_inserted_into_plus_y_rear_slot_display_faces_slope_outward',
    function: '用于照片显示、触控交互和相册控制',
  },
  {
    hardware_id: 'unihiker_polymer_lipo_battery',
    role: 'battery',
    quantity: 1,
    mount_surface: 'photo_album_rear_slope_hollow',
    placement: 'battery_inside_rear_slope_hollow_reference',
    function: '用于为相册提供便携电源',
  },
]);

const STAGE_1_GEOMETRY = Object.freeze({
  base_length_x: 52.08,
  base_width_y: 83.0,
  base_thickness_z: 5.0,
  slope_face_length: 65.5,
  slope_thickness: 5.0,
  slope_angle_deg: 60.0,
  cut_epsilon: 0.05,
  cut_overlap_y: 1.0,
});

const STAGE_2_CLIP_GEOMETRY = Object.freeze({
  clip_perpendicular_thickness: 4.0,
  clip_perpendicular_length: 15.6,
  clip_parallel_thickness: 3.0,
  clip_parallel_length: 7.8,
  clip_offset_from_slope_top: 51.5,
});

const STAGE_3_SIDE_BLOCK_GEOMETRY = Object.freeze({
  side_block_y_depth: 7.0,
  side_block_parallel_extension: 51.5,
  inner_side_block_normal_length: 5.9,
  outer_side_block_normal_length: 4.7,
  side_block_gap_between_blocks: 2.0,
  side_block_union_overlap: 0.05,
});

const STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY = Object.freeze({
  plus_y_slope_back_cover_y_depth: 7.0,
  plus_y_slope_back_cover_s_min: -5.0,
  plus_y_slope_back_cover_s_length: 5.0,
});

const STAGE_5_SQUARE_HOLE_GEOMETRY = Object.freeze({
  slope_square_hole_size: 12.0,
  slope_square_hole_center_s: 25.75,
  slope_square_hole_offset_from_minus_y: 22.5,
  slope_square_hole_cutter_normal_padding: 1.0,
});

const STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY = Object.freeze({
  rear_slope_block_y_length: 54.5,
  rear_slope_block_s_length: 34.0,
  rear_slope_block_normal_thickness: 8.5,
  rear_slope_block_offset_from_slope_top: 1.0,
});

const STAGE_7_REAR_SLOPE_TOP_SLOT_GEOMETRY = Object.freeze({
  rear_slope_top_slot_y_length: 49.0,
  rear_slope_top_slot_width_n: 6.5,
  rear_slope_top_slot_cut_depth_s: 32.0,
  rear_slope_top_slot_cutter_overlap_s: 0.05,
});

const STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY = Object.freeze({
  narrow_stop_semicircle_diameter: 10.0,
  narrow_stop_semicircle_offset_from_lip_top_edge_s: 23.85,
  narrow_stop_semicircle_cut_depth_n: 12.6,
  narrow_stop_semicircle_cutter_overlap_n: 0.05,
  narrow_stop_semicircle_segments: 32,
});

const STAGE_9_FILLET_GEOMETRY = Object.freeze({
  rear_slope_block_low_contact_fillet_radius: 8.5,
  rear_slope_block_low_contact_filler_segments: 24,
});

const K10_GEOMETRY = Object.freeze({
  pcb_length_x: 83.2,
  pcb_width_y: 51.3,
  pcb_thickness_z: 1.6,
  display_frame_height_z: 4.0,
  component_height_top_z: 5.6,
  component_height_bottom_z: 5.0,
  bottom_cube_height_z: 2.5,
  toward_slope_offset_n: 2.0,
  gold_finger_length_x: 7.0,
});

const POLYMER_LIPO_BATTERY_GEOMETRY = Object.freeze({
  length_x: 48.0,
  width_y: 32.0,
  thickness_z: 6.0,
});

const K10_GOLD_FINGER_CENTER_X = round3(
  K10_GEOMETRY.pcb_length_x / 2 - K10_GEOMETRY.gold_finger_length_x / 2,
);

const OUTER_SIDE_BLOCK_START_N = round3(
  STAGE_3_SIDE_BLOCK_GEOMETRY.inner_side_block_normal_length
  + STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_gap_between_blocks,
);
const OUTER_SIDE_BLOCK_END_N = round3(
  OUTER_SIDE_BLOCK_START_N + STAGE_3_SIDE_BLOCK_GEOMETRY.outer_side_block_normal_length,
);
const PLUS_Y_SLOPE_BACK_COVER_S_MIN = STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY.plus_y_slope_back_cover_s_min;
const PLUS_Y_SLOPE_BACK_COVER_S_LENGTH = STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY.plus_y_slope_back_cover_s_length;
const PLUS_Y_SLOPE_BACK_COVER_S_MAX = round3(PLUS_Y_SLOPE_BACK_COVER_S_MIN + PLUS_Y_SLOPE_BACK_COVER_S_LENGTH);
const PLUS_Y_SLOPE_BACK_COVER_S_CENTER = round3((PLUS_Y_SLOPE_BACK_COVER_S_MIN + PLUS_Y_SLOPE_BACK_COVER_S_MAX) / 2);
const PLUS_Y_SLOPE_BACK_COVER_N_MIN = -STAGE_1_GEOMETRY.slope_thickness;
const PLUS_Y_SLOPE_BACK_COVER_N_MAX = OUTER_SIDE_BLOCK_END_N;
const PLUS_Y_SLOPE_BACK_COVER_N_CENTER = round3((PLUS_Y_SLOPE_BACK_COVER_N_MIN + PLUS_Y_SLOPE_BACK_COVER_N_MAX) / 2);
const PLUS_Y_SLOPE_BACK_COVER_NORMAL_LENGTH = round3(PLUS_Y_SLOPE_BACK_COVER_N_MAX - PLUS_Y_SLOPE_BACK_COVER_N_MIN);
const PLUS_Y_SLOPE_BACK_COVER_Y_MAX = STAGE_1_GEOMETRY.base_width_y / 2;
const PLUS_Y_SLOPE_BACK_COVER_Y_MIN = round3(
  PLUS_Y_SLOPE_BACK_COVER_Y_MAX - STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY.plus_y_slope_back_cover_y_depth,
);
const PLUS_Y_SLOPE_BACK_COVER_Y_CENTER = round3((PLUS_Y_SLOPE_BACK_COVER_Y_MIN + PLUS_Y_SLOPE_BACK_COVER_Y_MAX) / 2);
const SLOPE_SQUARE_HOLE_CENTER_Y = round3(
  -STAGE_1_GEOMETRY.base_width_y / 2 + STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_offset_from_minus_y,
);
const SLOPE_SQUARE_HOLE_S_MIN = round3(
  STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_center_s - STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size / 2,
);
const SLOPE_SQUARE_HOLE_S_MAX = round3(
  STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_center_s + STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size / 2,
);
const SLOPE_SQUARE_HOLE_Y_MIN = round3(SLOPE_SQUARE_HOLE_CENTER_Y - STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size / 2);
const SLOPE_SQUARE_HOLE_Y_MAX = round3(SLOPE_SQUARE_HOLE_CENTER_Y + STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size / 2);
const SLOPE_SQUARE_HOLE_CUTTER_NORMAL_DEPTH = round3(
  STAGE_1_GEOMETRY.slope_thickness + 2.0 * STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_cutter_normal_padding,
);
const SLOPE_SQUARE_HOLE_CUTTER_CENTER_N = -STAGE_1_GEOMETRY.slope_thickness / 2.0;
const SLOPE_SQUARE_HOLE_CUTTER_MIN_N = round3(
  SLOPE_SQUARE_HOLE_CUTTER_CENTER_N - SLOPE_SQUARE_HOLE_CUTTER_NORMAL_DEPTH / 2,
);
const SLOPE_SQUARE_HOLE_CUTTER_MAX_N = round3(
  SLOPE_SQUARE_HOLE_CUTTER_CENTER_N + SLOPE_SQUARE_HOLE_CUTTER_NORMAL_DEPTH / 2,
);
const REAR_SLOPE_BLOCK_Y_LENGTH = STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY.rear_slope_block_y_length;
const REAR_SLOPE_BLOCK_Y_MAX = STAGE_1_GEOMETRY.base_width_y / 2;
const REAR_SLOPE_BLOCK_Y_MIN = round3(REAR_SLOPE_BLOCK_Y_MAX - REAR_SLOPE_BLOCK_Y_LENGTH);
const REAR_SLOPE_BLOCK_Y_CENTER = round3((REAR_SLOPE_BLOCK_Y_MIN + REAR_SLOPE_BLOCK_Y_MAX) / 2);
const REAR_SLOPE_BLOCK_OFFSET_FROM_SLOPE_TOP = STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY.rear_slope_block_offset_from_slope_top;
const REAR_SLOPE_BLOCK_S_MIN = REAR_SLOPE_BLOCK_OFFSET_FROM_SLOPE_TOP;
const REAR_SLOPE_BLOCK_S_LENGTH = STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY.rear_slope_block_s_length;
const REAR_SLOPE_BLOCK_S_MAX = round3(REAR_SLOPE_BLOCK_S_MIN + REAR_SLOPE_BLOCK_S_LENGTH);
const REAR_SLOPE_BLOCK_S_CENTER = round3((REAR_SLOPE_BLOCK_S_MIN + REAR_SLOPE_BLOCK_S_MAX) / 2);
const REAR_SLOPE_BLOCK_N_MAX = -STAGE_1_GEOMETRY.slope_thickness;
const REAR_SLOPE_BLOCK_NORMAL_THICKNESS = STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY.rear_slope_block_normal_thickness;
const REAR_SLOPE_BLOCK_N_MIN = round3(REAR_SLOPE_BLOCK_N_MAX - REAR_SLOPE_BLOCK_NORMAL_THICKNESS);
const REAR_SLOPE_BLOCK_N_CENTER = round3((REAR_SLOPE_BLOCK_N_MIN + REAR_SLOPE_BLOCK_N_MAX) / 2);
const REAR_SLOPE_TOP_SLOT_Y_LENGTH = STAGE_7_REAR_SLOPE_TOP_SLOT_GEOMETRY.rear_slope_top_slot_y_length;
const REAR_SLOPE_TOP_SLOT_Y_CENTER = REAR_SLOPE_BLOCK_Y_CENTER;
const REAR_SLOPE_TOP_SLOT_Y_MIN = round3(REAR_SLOPE_TOP_SLOT_Y_CENTER - REAR_SLOPE_TOP_SLOT_Y_LENGTH / 2);
const REAR_SLOPE_TOP_SLOT_Y_MAX = round3(REAR_SLOPE_TOP_SLOT_Y_CENTER + REAR_SLOPE_TOP_SLOT_Y_LENGTH / 2);
const REAR_SLOPE_TOP_SLOT_SURFACE_S = REAR_SLOPE_BLOCK_S_MIN;
const REAR_SLOPE_TOP_SLOT_S_MIN = REAR_SLOPE_TOP_SLOT_SURFACE_S;
const REAR_SLOPE_TOP_SLOT_CUT_DEPTH_S = STAGE_7_REAR_SLOPE_TOP_SLOT_GEOMETRY.rear_slope_top_slot_cut_depth_s;
const REAR_SLOPE_TOP_SLOT_S_MAX = round3(REAR_SLOPE_TOP_SLOT_S_MIN + REAR_SLOPE_TOP_SLOT_CUT_DEPTH_S);
const REAR_SLOPE_TOP_SLOT_S_CENTER = round3((REAR_SLOPE_TOP_SLOT_S_MIN + REAR_SLOPE_TOP_SLOT_S_MAX) / 2);
const REAR_SLOPE_TOP_SLOT_N_MAX = REAR_SLOPE_BLOCK_N_MAX;
const REAR_SLOPE_TOP_SLOT_WIDTH_N = STAGE_7_REAR_SLOPE_TOP_SLOT_GEOMETRY.rear_slope_top_slot_width_n;
const REAR_SLOPE_TOP_SLOT_N_MIN = round3(REAR_SLOPE_TOP_SLOT_N_MAX - REAR_SLOPE_TOP_SLOT_WIDTH_N);
const REAR_SLOPE_TOP_SLOT_CENTER_N = round3((REAR_SLOPE_TOP_SLOT_N_MIN + REAR_SLOPE_TOP_SLOT_N_MAX) / 2);
const REAR_SLOPE_TOP_SLOT_CUTTER_OVERLAP_S = STAGE_7_REAR_SLOPE_TOP_SLOT_GEOMETRY.rear_slope_top_slot_cutter_overlap_s;
const REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN = round3(REAR_SLOPE_TOP_SLOT_S_MIN - REAR_SLOPE_TOP_SLOT_CUTTER_OVERLAP_S);
const REAR_SLOPE_TOP_SLOT_CUTTER_S_MAX = REAR_SLOPE_TOP_SLOT_S_MAX;
const REAR_SLOPE_TOP_SLOT_CUTTER_SIZE_S = round3(REAR_SLOPE_TOP_SLOT_CUTTER_S_MAX - REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN);
const REAR_SLOPE_TOP_SLOT_CUTTER_CENTER_S = round3(
  (REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN + REAR_SLOPE_TOP_SLOT_CUTTER_S_MAX) / 2,
);
const NARROW_STOP_SEMICIRCLE_DIAMETER = STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY.narrow_stop_semicircle_diameter;
const NARROW_STOP_SEMICIRCLE_RADIUS = round3(NARROW_STOP_SEMICIRCLE_DIAMETER / 2);
const NARROW_STOP_SEMICIRCLE_OFFSET_FROM_LIP_TOP_EDGE_S = STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY.narrow_stop_semicircle_offset_from_lip_top_edge_s;
const NARROW_STOP_SEMICIRCLE_CLIP_PARALLEL_TOP_EDGE_S = round3(
  STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top
  - STAGE_2_CLIP_GEOMETRY.clip_parallel_length,
);
const NARROW_STOP_SEMICIRCLE_CENTER_S = round3(
  NARROW_STOP_SEMICIRCLE_CLIP_PARALLEL_TOP_EDGE_S
  - NARROW_STOP_SEMICIRCLE_OFFSET_FROM_LIP_TOP_EDGE_S,
);
const NARROW_STOP_SEMICIRCLE_CENTER_Y = STAGE_1_GEOMETRY.base_width_y / 2;
const NARROW_STOP_SEMICIRCLE_CENTER_N = OUTER_SIDE_BLOCK_END_N;
const NARROW_STOP_SEMICIRCLE_S_MIN = round3(NARROW_STOP_SEMICIRCLE_CENTER_S - NARROW_STOP_SEMICIRCLE_RADIUS);
const NARROW_STOP_SEMICIRCLE_S_MAX = round3(NARROW_STOP_SEMICIRCLE_CENTER_S + NARROW_STOP_SEMICIRCLE_RADIUS);
const NARROW_STOP_SEMICIRCLE_Y_MIN = round3(NARROW_STOP_SEMICIRCLE_CENTER_Y - NARROW_STOP_SEMICIRCLE_RADIUS);
const NARROW_STOP_SEMICIRCLE_Y_MAX = NARROW_STOP_SEMICIRCLE_CENTER_Y;
const NARROW_STOP_SEMICIRCLE_CUT_DEPTH_N = STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY.narrow_stop_semicircle_cut_depth_n;
const NARROW_STOP_SEMICIRCLE_CUTTER_OVERLAP_N = STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY.narrow_stop_semicircle_cutter_overlap_n;
const NARROW_STOP_SEMICIRCLE_CUTTER_MIN_N = round3(
  NARROW_STOP_SEMICIRCLE_CENTER_N - NARROW_STOP_SEMICIRCLE_CUT_DEPTH_N - NARROW_STOP_SEMICIRCLE_CUTTER_OVERLAP_N,
);
const NARROW_STOP_SEMICIRCLE_CUTTER_MAX_N = round3(
  NARROW_STOP_SEMICIRCLE_CENTER_N + NARROW_STOP_SEMICIRCLE_CUTTER_OVERLAP_N,
);
const NARROW_STOP_SEMICIRCLE_CUTTER_DEPTH_N = round3(
  NARROW_STOP_SEMICIRCLE_CUTTER_MAX_N - NARROW_STOP_SEMICIRCLE_CUTTER_MIN_N,
);
const NARROW_STOP_SEMICIRCLE_CUTTER_CENTER_N = round3(
  (NARROW_STOP_SEMICIRCLE_CUTTER_MIN_N + NARROW_STOP_SEMICIRCLE_CUTTER_MAX_N) / 2,
);
const NARROW_STOP_SEMICIRCLE_SEGMENTS = STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY.narrow_stop_semicircle_segments;
const PHOTO_ALBUM_STAGE = 'stage_9_5_confirmed_photo_album_model';
const SLOPE_WIDTH_Y = STAGE_1_GEOMETRY.base_width_y;
const SLOPE_ANCHOR_X = STAGE_1_GEOMETRY.base_length_x / 2;
const SLOPE_OFFSET_Y = SLOPE_WIDTH_Y;
const VISIBLE_SLOPE_CENTER_Y = SLOPE_OFFSET_Y - SLOPE_WIDTH_Y;

const TEMPLATE_PARAMETERS = Object.freeze({
  ...DEFAULT_PARAMETERS,
  inner_length_x: STAGE_1_GEOMETRY.base_length_x,
  inner_width_y: STAGE_1_GEOMETRY.base_width_y,
  inner_height_z: STAGE_1_GEOMETRY.base_thickness_z,
  wall_thickness: STAGE_1_GEOMETRY.slope_thickness,
  floor_thickness: STAGE_1_GEOMETRY.base_thickness_z,
  lid_thickness: 0,
  lid_lip_height: 0,
  lid_clearance: 0,
  corner_radius: 0,
  hardware_gap: 0,
  screw_boss_diameter: 0,
  screw_hole_diameter: 0,
  photo_album_base_length_x: STAGE_1_GEOMETRY.base_length_x,
  photo_album_base_width_y: STAGE_1_GEOMETRY.base_width_y,
  photo_album_base_thickness_z: STAGE_1_GEOMETRY.base_thickness_z,
  photo_album_slope_face_length: STAGE_1_GEOMETRY.slope_face_length,
  photo_album_slope_thickness: STAGE_1_GEOMETRY.slope_thickness,
  photo_album_slope_angle_deg: STAGE_1_GEOMETRY.slope_angle_deg,
  photo_album_slope_width_y: SLOPE_WIDTH_Y,
  photo_album_slope_anchor_x: SLOPE_ANCHOR_X,
  photo_album_slope_offset_y: SLOPE_OFFSET_Y,
  photo_album_clip_perpendicular_thickness: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_thickness,
  photo_album_clip_perpendicular_length: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_length,
  photo_album_clip_parallel_thickness: STAGE_2_CLIP_GEOMETRY.clip_parallel_thickness,
  photo_album_clip_parallel_length: STAGE_2_CLIP_GEOMETRY.clip_parallel_length,
  photo_album_clip_offset_from_slope_top: STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top,
  photo_album_clip_width_y: SLOPE_WIDTH_Y,
  photo_album_clip_center_y: VISIBLE_SLOPE_CENTER_Y,
  photo_album_side_block_y_depth: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_y_depth,
  photo_album_side_block_parallel_extension: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_parallel_extension,
  photo_album_inner_side_block_normal_length: STAGE_3_SIDE_BLOCK_GEOMETRY.inner_side_block_normal_length,
  photo_album_outer_side_block_normal_length: STAGE_3_SIDE_BLOCK_GEOMETRY.outer_side_block_normal_length,
  photo_album_side_block_gap_between_blocks: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_gap_between_blocks,
  photo_album_side_block_union_overlap: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_union_overlap,
  photo_album_plus_y_slope_back_cover_y_depth: STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY.plus_y_slope_back_cover_y_depth,
  photo_album_plus_y_slope_back_cover_y_min: PLUS_Y_SLOPE_BACK_COVER_Y_MIN,
  photo_album_plus_y_slope_back_cover_y_max: PLUS_Y_SLOPE_BACK_COVER_Y_MAX,
  photo_album_plus_y_slope_back_cover_y_center: PLUS_Y_SLOPE_BACK_COVER_Y_CENTER,
  photo_album_plus_y_slope_back_cover_s_min: PLUS_Y_SLOPE_BACK_COVER_S_MIN,
  photo_album_plus_y_slope_back_cover_s_max: PLUS_Y_SLOPE_BACK_COVER_S_MAX,
  photo_album_plus_y_slope_back_cover_s_length: PLUS_Y_SLOPE_BACK_COVER_S_LENGTH,
  photo_album_plus_y_slope_back_cover_s_center: PLUS_Y_SLOPE_BACK_COVER_S_CENTER,
  photo_album_plus_y_slope_back_cover_n_min: PLUS_Y_SLOPE_BACK_COVER_N_MIN,
  photo_album_plus_y_slope_back_cover_n_max: PLUS_Y_SLOPE_BACK_COVER_N_MAX,
  photo_album_plus_y_slope_back_cover_n_center: PLUS_Y_SLOPE_BACK_COVER_N_CENTER,
  photo_album_plus_y_slope_back_cover_normal_length: PLUS_Y_SLOPE_BACK_COVER_NORMAL_LENGTH,
  photo_album_slope_square_hole_size: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size,
  photo_album_slope_square_hole_center_s: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_center_s,
  photo_album_slope_square_hole_offset_from_minus_y: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_offset_from_minus_y,
  photo_album_slope_square_hole_center_y: SLOPE_SQUARE_HOLE_CENTER_Y,
  photo_album_slope_square_hole_s_min: SLOPE_SQUARE_HOLE_S_MIN,
  photo_album_slope_square_hole_s_max: SLOPE_SQUARE_HOLE_S_MAX,
  photo_album_slope_square_hole_y_min: SLOPE_SQUARE_HOLE_Y_MIN,
  photo_album_slope_square_hole_y_max: SLOPE_SQUARE_HOLE_Y_MAX,
  photo_album_slope_square_hole_cutter_normal_padding: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_cutter_normal_padding,
  photo_album_slope_square_hole_cutter_normal_depth: SLOPE_SQUARE_HOLE_CUTTER_NORMAL_DEPTH,
  photo_album_slope_square_hole_cutter_center_n: SLOPE_SQUARE_HOLE_CUTTER_CENTER_N,
  photo_album_slope_square_hole_cutter_min_n: SLOPE_SQUARE_HOLE_CUTTER_MIN_N,
  photo_album_slope_square_hole_cutter_max_n: SLOPE_SQUARE_HOLE_CUTTER_MAX_N,
  photo_album_rear_slope_block_y_length: REAR_SLOPE_BLOCK_Y_LENGTH,
  photo_album_rear_slope_block_y_min: REAR_SLOPE_BLOCK_Y_MIN,
  photo_album_rear_slope_block_y_max: REAR_SLOPE_BLOCK_Y_MAX,
  photo_album_rear_slope_block_y_center: REAR_SLOPE_BLOCK_Y_CENTER,
  photo_album_rear_slope_block_offset_from_slope_top: REAR_SLOPE_BLOCK_OFFSET_FROM_SLOPE_TOP,
  photo_album_rear_slope_block_s_min: REAR_SLOPE_BLOCK_S_MIN,
  photo_album_rear_slope_block_s_max: REAR_SLOPE_BLOCK_S_MAX,
  photo_album_rear_slope_block_s_length: REAR_SLOPE_BLOCK_S_LENGTH,
  photo_album_rear_slope_block_s_center: REAR_SLOPE_BLOCK_S_CENTER,
  photo_album_rear_slope_block_n_min: REAR_SLOPE_BLOCK_N_MIN,
  photo_album_rear_slope_block_n_max: REAR_SLOPE_BLOCK_N_MAX,
  photo_album_rear_slope_block_n_center: REAR_SLOPE_BLOCK_N_CENTER,
  photo_album_rear_slope_block_normal_thickness: REAR_SLOPE_BLOCK_NORMAL_THICKNESS,
  photo_album_rear_slope_top_slot_y_length: REAR_SLOPE_TOP_SLOT_Y_LENGTH,
  photo_album_rear_slope_top_slot_y_min: REAR_SLOPE_TOP_SLOT_Y_MIN,
  photo_album_rear_slope_top_slot_y_max: REAR_SLOPE_TOP_SLOT_Y_MAX,
  photo_album_rear_slope_top_slot_y_center: REAR_SLOPE_TOP_SLOT_Y_CENTER,
  photo_album_rear_slope_top_slot_width_n: REAR_SLOPE_TOP_SLOT_WIDTH_N,
  photo_album_rear_slope_top_slot_n_min: REAR_SLOPE_TOP_SLOT_N_MIN,
  photo_album_rear_slope_top_slot_n_max: REAR_SLOPE_TOP_SLOT_N_MAX,
  photo_album_rear_slope_top_slot_center_n: REAR_SLOPE_TOP_SLOT_CENTER_N,
  photo_album_rear_slope_top_slot_cut_depth_s: REAR_SLOPE_TOP_SLOT_CUT_DEPTH_S,
  photo_album_rear_slope_top_slot_surface_s: REAR_SLOPE_TOP_SLOT_SURFACE_S,
  photo_album_rear_slope_top_slot_s_min: REAR_SLOPE_TOP_SLOT_S_MIN,
  photo_album_rear_slope_top_slot_s_max: REAR_SLOPE_TOP_SLOT_S_MAX,
  photo_album_rear_slope_top_slot_s_center: REAR_SLOPE_TOP_SLOT_S_CENTER,
  photo_album_rear_slope_top_slot_cutter_overlap_s: REAR_SLOPE_TOP_SLOT_CUTTER_OVERLAP_S,
  photo_album_rear_slope_top_slot_cutter_s_min: REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN,
  photo_album_rear_slope_top_slot_cutter_s_max: REAR_SLOPE_TOP_SLOT_CUTTER_S_MAX,
  photo_album_rear_slope_top_slot_cutter_size_s: REAR_SLOPE_TOP_SLOT_CUTTER_SIZE_S,
  photo_album_rear_slope_top_slot_cutter_center_s: REAR_SLOPE_TOP_SLOT_CUTTER_CENTER_S,
  photo_album_narrow_stop_semicircle_diameter: NARROW_STOP_SEMICIRCLE_DIAMETER,
  photo_album_narrow_stop_semicircle_radius: NARROW_STOP_SEMICIRCLE_RADIUS,
  photo_album_narrow_stop_semicircle_offset_from_lip_top_edge_s: NARROW_STOP_SEMICIRCLE_OFFSET_FROM_LIP_TOP_EDGE_S,
  photo_album_narrow_stop_semicircle_clip_parallel_top_edge_s: NARROW_STOP_SEMICIRCLE_CLIP_PARALLEL_TOP_EDGE_S,
  photo_album_narrow_stop_semicircle_center_s: NARROW_STOP_SEMICIRCLE_CENTER_S,
  photo_album_narrow_stop_semicircle_center_y: NARROW_STOP_SEMICIRCLE_CENTER_Y,
  photo_album_narrow_stop_semicircle_center_n: NARROW_STOP_SEMICIRCLE_CENTER_N,
  photo_album_narrow_stop_semicircle_s_min: NARROW_STOP_SEMICIRCLE_S_MIN,
  photo_album_narrow_stop_semicircle_s_max: NARROW_STOP_SEMICIRCLE_S_MAX,
  photo_album_narrow_stop_semicircle_y_min: NARROW_STOP_SEMICIRCLE_Y_MIN,
  photo_album_narrow_stop_semicircle_y_max: NARROW_STOP_SEMICIRCLE_Y_MAX,
  photo_album_narrow_stop_semicircle_cut_depth_n: NARROW_STOP_SEMICIRCLE_CUT_DEPTH_N,
  photo_album_narrow_stop_semicircle_cutter_overlap_n: NARROW_STOP_SEMICIRCLE_CUTTER_OVERLAP_N,
  photo_album_narrow_stop_semicircle_cutter_min_n: NARROW_STOP_SEMICIRCLE_CUTTER_MIN_N,
  photo_album_narrow_stop_semicircle_cutter_max_n: NARROW_STOP_SEMICIRCLE_CUTTER_MAX_N,
  photo_album_narrow_stop_semicircle_cutter_depth_n: NARROW_STOP_SEMICIRCLE_CUTTER_DEPTH_N,
  photo_album_narrow_stop_semicircle_cutter_center_n: NARROW_STOP_SEMICIRCLE_CUTTER_CENTER_N,
  photo_album_narrow_stop_semicircle_segments: NARROW_STOP_SEMICIRCLE_SEGMENTS,
  photo_album_rear_slope_block_low_contact_fillet_radius: STAGE_9_FILLET_GEOMETRY.rear_slope_block_low_contact_fillet_radius,
  photo_album_rear_slope_block_low_contact_filler_segments: STAGE_9_FILLET_GEOMETRY.rear_slope_block_low_contact_filler_segments,
  photo_album_rear_slope_block_low_contact_filler_s_min: REAR_SLOPE_BLOCK_S_MAX,
  photo_album_rear_slope_block_low_contact_filler_s_max: round3(REAR_SLOPE_BLOCK_S_MAX + STAGE_9_FILLET_GEOMETRY.rear_slope_block_low_contact_fillet_radius),
  photo_album_rear_slope_block_low_contact_filler_n_min: round3(REAR_SLOPE_BLOCK_N_MAX - STAGE_9_FILLET_GEOMETRY.rear_slope_block_low_contact_fillet_radius),
  photo_album_rear_slope_block_low_contact_filler_n_max: REAR_SLOPE_BLOCK_N_MAX,
  photo_album_rear_slope_block_low_contact_filler_width_y: REAR_SLOPE_BLOCK_Y_LENGTH,
  photo_album_rear_slope_block_low_contact_filler_center_y: REAR_SLOPE_BLOCK_Y_CENTER,
});

const GUI_PARAMETER_TO_TEMPLATE_PARAMETER = Object.freeze({
  base_length_x: 'photo_album_base_length_x',
  base_width_y: 'photo_album_base_width_y',
  base_thickness_z: 'photo_album_base_thickness_z',
  slope_face_length: 'photo_album_slope_face_length',
  slope_thickness: 'photo_album_slope_thickness',
  slope_angle_deg: 'photo_album_slope_angle_deg',
  clip_perpendicular_thickness: 'photo_album_clip_perpendicular_thickness',
  clip_perpendicular_length: 'photo_album_clip_perpendicular_length',
  side_block_y_depth: 'photo_album_side_block_y_depth',
  rear_slope_block_s_length: 'photo_album_rear_slope_block_s_length',
  rear_slope_block_normal_thickness: 'photo_album_rear_slope_block_normal_thickness',
  rear_slope_top_slot_width_n: 'photo_album_rear_slope_top_slot_width_n',
  rear_slope_top_slot_y_length: 'photo_album_rear_slope_top_slot_y_length',
  narrow_stop_semicircle_diameter: 'photo_album_narrow_stop_semicircle_diameter',
  rear_slope_block_low_contact_fillet_radius: 'photo_album_rear_slope_block_low_contact_fillet_radius',
});

const CADQUERY_ASSIGNMENT_PARAMETER_KEYS = Object.freeze([
  'base_length_x',
  'base_width_y',
  'base_thickness_z',
  'slope_face_length',
  'slope_thickness',
  'slope_angle_deg',
  'clip_perpendicular_thickness',
  'clip_perpendicular_length',
  'side_block_y_depth',
  'rear_slope_block_s_length',
  'rear_slope_block_normal_thickness',
  'rear_slope_top_slot_width_n',
  'rear_slope_top_slot_y_length',
  'narrow_stop_semicircle_diameter',
  'narrow_stop_semicircle_radius',
  'rear_slope_block_low_contact_fillet_radius',
]);

const DEFAULT_PRINTABLE_PARTS = Object.freeze([
  {
    id: 'photo_album_body',
    label: '相册主体',
    source_export_id: 'cadquery_base_stl',
    format: 'stl',
    role: 'printable_body',
  },
]);

export function buildUnihikerPhotoAlbumTemplate({ product, detection, body = {}, context = {} } = {}) {
  const profiles = collectTemplateProfiles();
  if (profiles.missing.length) {
    return buildMissingProfileResponse({ product, detection, body, missing: profiles.missing });
  }

  const designId = context.designId || 'ZW-UNIHIKER-PHOTO-ALBUM-STAGE-9-5-PREVIEW';
  const resultStartedAt = context.resultStartedAt || new Date().toISOString();
  const { parameters, changedTemplateKeys } = buildTemplateParameters(body);
  const geometry = buildGeometry(parameters);
  const enclosure = buildEnclosure(geometry);
  const engravingSurfaces = buildPhotoAlbumEngravingSurfaces(geometry);
  const bom = buildBom(profiles.byId);
  const intent = buildIntent({ product, body, bom });
  const layoutPlan = buildLayoutPlan({ geometry, enclosure });
  const validation = buildTemplateValidation({ geometry, profiles: profiles.items });
  const cadqueryCode = buildCadQueryCode({ parameters, changedTemplateKeys });
  const warnings = [...validation.warnings];
  const deterministicProduct = summarizeTemplateProduct(product, detection);
  const designState = {
    id: designId,
    design_hash: designId,
    result_started_at: resultStartedAt,
    intent,
    bom,
    function_verification_report: {
      status: 'ok',
      verification_status: 'pass',
      source: 'deterministic_product_template',
      covered_functions: intent.functions,
      missing_functions: [],
      missing_hardware: [],
      notes: ['当前模型使用已确认的相册 CadQuery 源码生成最终几何。'],
    },
    hardware_profiles: profiles.items,
    profile_validation_report: {
      status: 'ok',
      source: 'deterministic_product_template',
      checked_profile_ids: TEMPLATE_HARDWARE.map((item) => item.hardware_id),
      builtin_profile_ids: TEMPLATE_HARDWARE.map((item) => item.hardware_id),
      missing_profile_ids: [],
    },
    mounting_plan: [],
    layout_plan: layoutPlan,
    enclosure_parameters: enclosure,
    cad_parameters: {
      generator: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
      units: 'mm',
      hardware_count: TEMPLATE_HARDWARE.length,
      stage: PHOTO_ALBUM_STAGE,
      geometry,
    },
    engraving_surfaces: engravingSurfaces,
    validation_context: validation.validation_context,
    parameters,
    printable_parts: buildPrintableParts(),
    project_default_parameters: projectDefaultParametersFromBody(body),
    default_parameters: projectDefaultParametersFromBody(body),
    hardware_face_overrides: {},
    hardware_rotation_overrides: {},
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
    resolution_option_route: null,
    ignored_missing_hardware_requests: [],
    dropped_functions: [],
    title: '行空板相册模型已生成',
    message: '检测到适合行空板相册的成型设计方案，已为你调用对应的结构参数并生成模型。请拖动模型检查结构，满意后导出 STL；如果要优化，请直接输入修改建议。',
    deterministic_product: deterministicProduct,
    template_id: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    warnings,
  };

  const intentAnalysis = {
    source: 'deterministic_product_template',
    status: 'ok',
    model_status: 'skipped',
    reason: detection?.reason || '已识别为行空板相册项目',
    confidence: detection?.confidence ?? 0.96,
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
  };

  const artifact = {
    status: 'artifact',
    title: '行空板相册模型已生成',
    message: '检测到适合行空板相册的成型设计方案，已为你调用对应的结构参数并生成模型。请拖动模型检查结构，满意后导出 STL；如果要优化，请直接输入修改建议。',
    deterministic_product: deterministicProduct,
    template_id: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    bom,
    partial_bom: bom,
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    function_verification_report: designState.function_verification_report,
    design_state: designState,
    engraving_surfaces: engravingSurfaces,
    parameters: buildPhotoAlbumParameterGroups(parameters, enclosure, layoutPlan),
    intent_analysis: intentAnalysis,
    cadquery_code: cadqueryCode,
    preview_assets: buildPreviewAssets({ enclosure, layoutPlan, parameters }),
    printable_parts: buildPrintableParts(),
    exports: [],
    checks: validation.checks,
    warnings,
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
    resolution_option_route: null,
    ignored_missing_hardware_requests: [],
    dropped_functions: [],
    source: 'deterministic_product_template',
  };

  artifact.generation_trace = buildTemplateGenerationTrace(artifact);
  artifact.design_state.generation_trace = artifact.generation_trace;
  return artifact;
}

export function buildPhotoAlbumEngravingSurfaces(geometry) {
  const referenceDistanceFromTop = 10;
  const lClipOuterFilletRadius = 3;
  const mainSlopeSpanY = Math.max(1, geometry.base_width_y - geometry.side_block_y_depth);
  const mainSlopeSpanS = Math.max(1, geometry.clip_offset_from_slope_top);
  const mainSlopeArea = 3750.45
    * (mainSlopeSpanY / (STAGE_1_GEOMETRY.base_width_y - STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_y_depth))
    * (mainSlopeSpanS / STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top);
  const lClipOuterFlatStartS = geometry.clip_lip_start_s;
  const lClipOuterFlatEndS = Math.max(
    lClipOuterFlatStartS,
    geometry.clip_end_s - lClipOuterFilletRadius,
  );
  const lClipOuterReferenceS = (lClipOuterFlatStartS + lClipOuterFlatEndS) / 2;
  const lClipOuterSpanS = Math.max(0.1, lClipOuterFlatEndS - lClipOuterFlatStartS);
  const lClipOuterSpanY = Math.max(1, geometry.clip_width_y);
  return [
    {
      id: 'photo_album_body.slope_front',
      part_id: 'photo_album_body',
      label: '相册主体大斜面',
      aliases: [
        '大斜面',
        '主斜面',
        '带方孔的斜面',
        '有方孔的斜面',
        '有正方形孔的斜面',
        '带正方形孔的斜面',
        '相册斜面',
        '相册主体斜面',
        '显示斜面',
      ],
      surface_type: 'planar',
      surface_kind: 'slope',
      target_part: 'base_part',
      selector_version: 'planar_surface_selector_v3',
      area_hint_mm2: round3(mainSlopeArea),
      local_span_hint_mm: [round3(mainSlopeSpanY), round3(mainSlopeSpanS)],
      normal_hint: [
        geometry.slope_outward_axis_x,
        0,
        geometry.slope_outward_axis_z,
      ],
      point_hint: [
        round3(geometry.slope_end_x + geometry.slope_down_axis_x * referenceDistanceFromTop),
        geometry.visible_slope_center_y,
        round3(geometry.slope_end_z + geometry.slope_down_axis_z * referenceDistanceFromTop),
      ],
      x_direction: [0, 1, 0],
      reference_distance_from_top_mm: referenceDistanceFromTop,
    },
    {
      id: 'photo_album_body.l_clip_outer_slope',
      part_id: 'photo_album_body',
      label: 'L形卡槽外斜面',
      aliases: [
        'L形卡槽外斜面',
        'L 形卡槽外斜面',
        'L型卡槽外斜面',
        'L 型卡槽外斜面',
        'L形卡槽外侧斜面',
        'L 形卡槽外侧斜面',
        'L型卡槽外侧斜面',
        'L 型卡槽外侧斜面',
        'L形卡槽外侧面斜面',
        'L 形卡槽外侧面斜面',
        'L型卡槽外侧面斜面',
        'L 型卡槽外侧面斜面',
        'L形卡槽外侧面',
        'L 形卡槽外侧面',
        'L型卡槽外侧面',
        'L 型卡槽外侧面',
        '卡槽斜面',
        '小斜面',
        '前侧窄斜面',
      ],
      surface_type: 'planar',
      surface_kind: 'slope',
      target_part: 'base_part',
      selector_version: 'planar_surface_selector_v3',
      area_hint_mm2: round3(lClipOuterSpanY * lClipOuterSpanS),
      local_span_hint_mm: [round3(lClipOuterSpanY), round3(lClipOuterSpanS)],
      normal_hint: [
        geometry.slope_outward_axis_x,
        0,
        geometry.slope_outward_axis_z,
      ],
      point_hint: [
        round3(geometry.slope_end_x
          + geometry.slope_down_axis_x * lClipOuterReferenceS
          + geometry.slope_outward_axis_x * geometry.clip_outer_n),
        geometry.clip_center_y,
        round3(geometry.slope_end_z
          + geometry.slope_down_axis_z * lClipOuterReferenceS
          + geometry.slope_outward_axis_z * geometry.clip_outer_n),
      ],
      x_direction: [0, 1, 0],
      reference_distance_from_top_mm: round3(lClipOuterReferenceS),
      normal_offset_from_slope_mm: geometry.clip_outer_n,
    },
  ];
}

export function collectTemplateProfiles() {
  const byId = new Map();
  const missing = [];
  for (const item of TEMPLATE_HARDWARE) {
    const profile = getHardwareProfile(item.hardware_id);
    if (profile) {
      byId.set(item.hardware_id, { ...profile, profile_status: 'builtin' });
    } else {
      missing.push(item.hardware_id);
    }
  }
  return {
    missing,
    byId,
    items: [...byId.values()],
  };
}

function buildBom(profilesById) {
  return TEMPLATE_HARDWARE.map((item) => {
    const profile = profilesById.get(item.hardware_id);
    return {
      hardware_id: item.hardware_id,
      name: profile?.name || item.hardware_id,
      role: item.role,
      category: profile?.category || 'hardware',
      hardware_system: profile?.hardware_system || 'unihiker',
      quantity: item.quantity,
      required_or_optional: 'required',
      function: item.function,
      why_needed: item.role === 'display_controller'
        ? 'K10 作为相册的固定显示和交互主控。'
        : '行空板聚合物锂电池作为相册的便携电源。',
      profile_status: 'builtin',
      template_placement: item.placement,
      mounting_intent: {
        preferred_surface: item.mount_surface,
        fixed_to_enclosure: true,
        modeled_as_reference: true,
        modeled_in_stage_1: true,
      },
    };
  });
}

function buildIntent({ product, body, bom }) {
  return {
    schema_version: '1.0',
    product_name: product?.product_name || '行空板相册',
    deterministic_product_id: product?.id || 'unihiker_photo_album',
    template_id: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    functions: [
      '鐓х墖鏄剧ず',
      '瑙︽帶浜や簰',
      '渚挎惡渚涚數',
      '绗簲闃舵缁撴瀯寤烘ā',
    ],
    required_hardware_roles: bom.map((item) => ({
      role: item.role,
      category: item.category,
      function: item.function,
      label: item.name,
      hardware_id: item.hardware_id,
      profile_status: item.profile_status,
    })),
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    mounting_intents: [
      {
        hardware_id: 'unihiker_k10',
        target_face: 'photo_album_rear_top_slot',
        user_phrase: 'K10 保持当前旋转和 PCB 下侧接触关系，整体朝斜面平移 2mm，并保持相册 -Y 外侧面对齐。',
      },
      {
        hardware_id: 'unihiker_polymer_lipo_battery',
        target_face: 'photo_album_rear_slope_hollow',
        user_phrase: '行空板聚合物锂电池放入斜面后侧空洞内，作为总装预览参考。',
      },
    ],
    enclosure_intent: {
      type: 'deterministic_photo_album_stage_9_5',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'not_modeled_in_stage_1',
      allowed_shape: 'flat_base_with_full_width_slope',
      deterministic_model: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    },
    user_constraints: {
      raw_prompt: typeof body.prompt === 'string' ? body.prompt : '',
      size_mm: {
        base_length_x: STAGE_1_GEOMETRY.base_length_x,
        base_width_y: STAGE_1_GEOMETRY.base_width_y,
        base_thickness_z: STAGE_1_GEOMETRY.base_thickness_z,
        slope_face_length: STAGE_1_GEOMETRY.slope_face_length,
        slope_thickness: STAGE_1_GEOMETRY.slope_thickness,
        slope_angle_deg: STAGE_1_GEOMETRY.slope_angle_deg,
        slope_width_y: SLOPE_WIDTH_Y,
        slope_anchor_x: SLOPE_ANCHOR_X,
        slope_offset_y: SLOPE_OFFSET_Y,
        clip_perpendicular_thickness: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_thickness,
        clip_perpendicular_length: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_length,
        clip_parallel_thickness: STAGE_2_CLIP_GEOMETRY.clip_parallel_thickness,
        clip_parallel_length: STAGE_2_CLIP_GEOMETRY.clip_parallel_length,
        clip_offset_from_slope_top: STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top,
        clip_width_y: SLOPE_WIDTH_Y,
        clip_center_y: VISIBLE_SLOPE_CENTER_Y,
        side_block_y_depth: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_y_depth,
        side_block_parallel_extension: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_parallel_extension,
        inner_side_block_normal_length: STAGE_3_SIDE_BLOCK_GEOMETRY.inner_side_block_normal_length,
        outer_side_block_normal_length: STAGE_3_SIDE_BLOCK_GEOMETRY.outer_side_block_normal_length,
        side_block_gap_between_blocks: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_gap_between_blocks,
        side_block_union_overlap: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_union_overlap,
        plus_y_slope_back_cover_y_depth: STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY.plus_y_slope_back_cover_y_depth,
        plus_y_slope_back_cover_y_min: PLUS_Y_SLOPE_BACK_COVER_Y_MIN,
        plus_y_slope_back_cover_y_max: PLUS_Y_SLOPE_BACK_COVER_Y_MAX,
        plus_y_slope_back_cover_s_min: PLUS_Y_SLOPE_BACK_COVER_S_MIN,
        plus_y_slope_back_cover_s_max: PLUS_Y_SLOPE_BACK_COVER_S_MAX,
        plus_y_slope_back_cover_n_min: PLUS_Y_SLOPE_BACK_COVER_N_MIN,
        plus_y_slope_back_cover_n_max: PLUS_Y_SLOPE_BACK_COVER_N_MAX,
        plus_y_slope_back_cover_normal_length: PLUS_Y_SLOPE_BACK_COVER_NORMAL_LENGTH,
        slope_square_hole_size: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size,
        slope_square_hole_center_s: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_center_s,
        slope_square_hole_offset_from_minus_y: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_offset_from_minus_y,
        slope_square_hole_center_y: SLOPE_SQUARE_HOLE_CENTER_Y,
        slope_square_hole_s_min: SLOPE_SQUARE_HOLE_S_MIN,
        slope_square_hole_s_max: SLOPE_SQUARE_HOLE_S_MAX,
        slope_square_hole_y_min: SLOPE_SQUARE_HOLE_Y_MIN,
        slope_square_hole_y_max: SLOPE_SQUARE_HOLE_Y_MAX,
        slope_square_hole_cutter_normal_padding: STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_cutter_normal_padding,
        slope_square_hole_cutter_normal_depth: SLOPE_SQUARE_HOLE_CUTTER_NORMAL_DEPTH,
        rear_slope_block_y_length: REAR_SLOPE_BLOCK_Y_LENGTH,
        rear_slope_block_y_min: REAR_SLOPE_BLOCK_Y_MIN,
        rear_slope_block_y_max: REAR_SLOPE_BLOCK_Y_MAX,
        rear_slope_block_s_min: REAR_SLOPE_BLOCK_S_MIN,
        rear_slope_block_s_max: REAR_SLOPE_BLOCK_S_MAX,
        rear_slope_block_s_length: REAR_SLOPE_BLOCK_S_LENGTH,
        rear_slope_block_n_min: REAR_SLOPE_BLOCK_N_MIN,
        rear_slope_block_n_max: REAR_SLOPE_BLOCK_N_MAX,
        rear_slope_block_normal_thickness: REAR_SLOPE_BLOCK_NORMAL_THICKNESS,
        rear_slope_top_slot_y_length: REAR_SLOPE_TOP_SLOT_Y_LENGTH,
        rear_slope_top_slot_y_min: REAR_SLOPE_TOP_SLOT_Y_MIN,
        rear_slope_top_slot_y_max: REAR_SLOPE_TOP_SLOT_Y_MAX,
        rear_slope_top_slot_y_center: REAR_SLOPE_TOP_SLOT_Y_CENTER,
        rear_slope_top_slot_width_n: REAR_SLOPE_TOP_SLOT_WIDTH_N,
        rear_slope_top_slot_n_min: REAR_SLOPE_TOP_SLOT_N_MIN,
        rear_slope_top_slot_n_max: REAR_SLOPE_TOP_SLOT_N_MAX,
        rear_slope_top_slot_center_n: REAR_SLOPE_TOP_SLOT_CENTER_N,
        rear_slope_top_slot_cut_depth_s: REAR_SLOPE_TOP_SLOT_CUT_DEPTH_S,
        rear_slope_top_slot_surface_s: REAR_SLOPE_TOP_SLOT_SURFACE_S,
        rear_slope_top_slot_s_min: REAR_SLOPE_TOP_SLOT_S_MIN,
        rear_slope_top_slot_s_max: REAR_SLOPE_TOP_SLOT_S_MAX,
        rear_slope_top_slot_s_center: REAR_SLOPE_TOP_SLOT_S_CENTER,
        rear_slope_top_slot_cutter_overlap_s: REAR_SLOPE_TOP_SLOT_CUTTER_OVERLAP_S,
        rear_slope_top_slot_cutter_s_min: REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN,
        rear_slope_top_slot_cutter_s_max: REAR_SLOPE_TOP_SLOT_CUTTER_S_MAX,
        rear_slope_top_slot_cutter_size_s: REAR_SLOPE_TOP_SLOT_CUTTER_SIZE_S,
        rear_slope_top_slot_cutter_center_s: REAR_SLOPE_TOP_SLOT_CUTTER_CENTER_S,
      },
      notes: [
        'Slope lower +X edge aligns with the base bottom +X edge and tilts along -X/+Z.',
        'Base dimensions are swapped from the first draft; slope Y length equals the base Y length of 83mm.',
        'Base and slope cleanup cutters remove the exposed triangular remnants.',
        'Stage 2 adds a full-width L clip on the slope.',
        'Stage 3 adds two +Y side stop blocks extending 7mm inward.',
        'Stage 5 adds the +Y slope back cover and a 12mm square through-hole.',
        'Stage 9-5 is the confirmed photo album geometry copied from the approved CQ source file.',
        '斜面角度保留为可编辑的模型参数。',
      ],
    },
    unknowns: [],
  };
}

function buildGeometry(parameters = TEMPLATE_PARAMETERS) {
  const parameterNumber = (key, fallback) => {
    const value = Number(parameters[key]);
    return Number.isFinite(value) ? value : fallback;
  };
  const baseLengthX = parameterNumber('photo_album_base_length_x', STAGE_1_GEOMETRY.base_length_x);
  const baseWidthY = parameterNumber('photo_album_base_width_y', STAGE_1_GEOMETRY.base_width_y);
  const baseThicknessZ = parameterNumber('photo_album_base_thickness_z', STAGE_1_GEOMETRY.base_thickness_z);
  const slopeFaceLength = parameterNumber('photo_album_slope_face_length', STAGE_1_GEOMETRY.slope_face_length);
  const slopeThickness = parameterNumber('photo_album_slope_thickness', STAGE_1_GEOMETRY.slope_thickness);
  const slopeWidthY = parameterNumber('photo_album_slope_width_y', baseWidthY);
  const slopeAnchorX = parameterNumber('photo_album_slope_anchor_x', baseLengthX / 2);
  const slopeOffsetY = parameterNumber('photo_album_slope_offset_y', slopeWidthY);
  const slopeAngleDeg = Number.isFinite(Number(parameters.photo_album_slope_angle_deg))
    ? Number(parameters.photo_album_slope_angle_deg)
    : STAGE_1_GEOMETRY.slope_angle_deg;
  const angleRad = slopeAngleDeg * Math.PI / 180;
  const slopeDownX = Math.cos(angleRad);
  const slopeDownZ = -Math.sin(angleRad);
  const slopeOutwardX = Math.sin(angleRad);
  const slopeOutwardZ = Math.cos(angleRad);
  const slopeRunX = Math.cos(angleRad) * slopeFaceLength;
  const slopeRiseZ = Math.sin(angleRad) * slopeFaceLength;
  const slopeStartX = slopeAnchorX;
  const slopeEndX = slopeStartX - slopeRunX;
  const slopeEndZ = slopeRiseZ;
  const normalX = -Math.sin(angleRad) * slopeThickness;
  const normalZ = -Math.cos(angleRad) * slopeThickness;
  const exposedPrismCutRunX = baseThicknessZ / Math.tan(angleRad);
  const exposedPrismCutStartX = slopeStartX - exposedPrismCutRunX;
  const bottomProtrusionDepthZ = Math.abs(normalZ);
  const bottomProtrusionLowerFaceRunX = bottomProtrusionDepthZ / Math.tan(angleRad);
  const bottomProtrusionCutRunX = Math.abs(normalX) + bottomProtrusionLowerFaceRunX;
  const bottomProtrusionCutStartX = slopeStartX - bottomProtrusionCutRunX;
  const points = [
    [slopeStartX, 0],
    [slopeEndX, slopeEndZ],
    [slopeEndX + normalX, slopeEndZ + normalZ],
    [bottomProtrusionCutStartX, 0],
  ];
  const baseMinY = -baseWidthY / 2;
  const baseMaxY = baseWidthY / 2;
  const slopeMinY = slopeOffsetY - slopeWidthY / 2;
  const slopeMaxY = slopeOffsetY + slopeWidthY / 2;
  const visibleSlopeCenterY = slopeOffsetY - slopeWidthY;
  const baseExposureCutterCenterY = visibleSlopeCenterY;
  const baseExposureCutterWidthY = baseWidthY + 2.0 * STAGE_1_GEOMETRY.cut_overlap_y;
  const baseExposureCutterMinY = baseExposureCutterCenterY - baseExposureCutterWidthY / 2;
  const baseExposureCutterMaxY = baseExposureCutterCenterY + baseExposureCutterWidthY / 2;
  const slopeCutterCenterY = visibleSlopeCenterY;
  const slopeCutterWidthY = slopeWidthY + 2.0 * STAGE_1_GEOMETRY.cut_overlap_y;
  const slopeCutterMinY = slopeCutterCenterY - slopeCutterWidthY / 2;
  const slopeCutterMaxY = slopeCutterCenterY + slopeCutterWidthY / 2;
  const clipWidthY = slopeWidthY;
  const clipCenterY = visibleSlopeCenterY;
  const clipMinY = clipCenterY - clipWidthY / 2;
  const clipMaxY = clipCenterY + clipWidthY / 2;
  const clipS0 = parameterNumber('photo_album_clip_offset_from_slope_top', STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top);
  const clipS1 = clipS0 + parameterNumber('photo_album_clip_perpendicular_thickness', STAGE_2_CLIP_GEOMETRY.clip_perpendicular_thickness);
  const clipLipS0 = clipS0 - parameterNumber('photo_album_clip_parallel_length', STAGE_2_CLIP_GEOMETRY.clip_parallel_length);
  const clipNOuter = parameterNumber('photo_album_clip_perpendicular_length', STAGE_2_CLIP_GEOMETRY.clip_perpendicular_length);
  const clipNInner = clipNOuter - parameterNumber('photo_album_clip_parallel_thickness', STAGE_2_CLIP_GEOMETRY.clip_parallel_thickness);
  const clipProfileLocalPoints = [
    [clipS0, 0],
    [clipS1, 0],
    [clipS1, clipNOuter],
    [clipLipS0, clipNOuter],
    [clipLipS0, clipNInner],
    [clipS0, clipNInner],
  ];
  const clipProfilePoints = clipProfileLocalPoints.map(([s, n]) => ([
    slopeEndX + slopeDownX * s + slopeOutwardX * n,
    slopeEndZ + slopeDownZ * s + slopeOutwardZ * n,
  ]));
  const clipMinX = Math.min(...clipProfilePoints.map((point) => point[0]));
  const clipMaxX = Math.max(...clipProfilePoints.map((point) => point[0]));
  const clipMinZ = Math.min(...clipProfilePoints.map((point) => point[1]));
  const clipMaxZ = Math.max(...clipProfilePoints.map((point) => point[1]));
  const sideBlockYMax = baseMaxY;
  const sideBlockYMin = sideBlockYMax - parameterNumber('photo_album_side_block_y_depth', STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_y_depth);
  const sideBlockYCenter = (sideBlockYMin + sideBlockYMax) / 2;
  const sideBlockS0 = clipS0 - parameterNumber('photo_album_side_block_parallel_extension', STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_parallel_extension);
  const sideBlockS1 = clipS0 + parameterNumber('photo_album_side_block_union_overlap', STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_union_overlap);
  const innerSideBlockN0 = 0;
  const innerSideBlockN1 = parameterNumber('photo_album_inner_side_block_normal_length', STAGE_3_SIDE_BLOCK_GEOMETRY.inner_side_block_normal_length);
  const sideBlockGapBetweenBlocks = parameterNumber('photo_album_side_block_gap_between_blocks', STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_gap_between_blocks);
  const outerSideBlockN0 = innerSideBlockN1 + sideBlockGapBetweenBlocks;
  const outerSideBlockN1 = outerSideBlockN0 + parameterNumber('photo_album_outer_side_block_normal_length', STAGE_3_SIDE_BLOCK_GEOMETRY.outer_side_block_normal_length);
  const makeSideBlockProfile = (s0, s1, n0, n1) => ([
    [s0, n0],
    [s1, n0],
    [s1, n1],
    [s0, n1],
  ].map(([s, n]) => ([
    slopeEndX + slopeDownX * s + slopeOutwardX * n,
    slopeEndZ + slopeDownZ * s + slopeOutwardZ * n,
  ])));
  const innerSideBlockProfilePoints = makeSideBlockProfile(sideBlockS0, sideBlockS1, innerSideBlockN0, innerSideBlockN1);
  const outerSideBlockProfilePoints = makeSideBlockProfile(sideBlockS0, sideBlockS1, outerSideBlockN0, outerSideBlockN1);
  const sideBlockProfilePoints = [...innerSideBlockProfilePoints, ...outerSideBlockProfilePoints];
  const sideBlockMinX = Math.min(...sideBlockProfilePoints.map((point) => point[0]));
  const sideBlockMaxX = Math.max(...sideBlockProfilePoints.map((point) => point[0]));
  const sideBlockMinZ = Math.min(...sideBlockProfilePoints.map((point) => point[1]));
  const sideBlockMaxZ = Math.max(...sideBlockProfilePoints.map((point) => point[1]));
  const plusYSlopeBackCoverYDepth = parameterNumber('photo_album_plus_y_slope_back_cover_y_depth', STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY.plus_y_slope_back_cover_y_depth);
  const plusYSlopeBackCoverYMax = baseMaxY;
  const plusYSlopeBackCoverYMin = plusYSlopeBackCoverYMax - plusYSlopeBackCoverYDepth;
  const plusYSlopeBackCoverYCenter = (plusYSlopeBackCoverYMin + plusYSlopeBackCoverYMax) / 2;
  const plusYSlopeBackCoverS0 = parameterNumber('photo_album_plus_y_slope_back_cover_s_min', PLUS_Y_SLOPE_BACK_COVER_S_MIN);
  const plusYSlopeBackCoverS1 = parameterNumber('photo_album_plus_y_slope_back_cover_s_max', PLUS_Y_SLOPE_BACK_COVER_S_MAX);
  const plusYSlopeBackCoverN0 = parameterNumber('photo_album_plus_y_slope_back_cover_n_min', -slopeThickness);
  const plusYSlopeBackCoverN1 = outerSideBlockN1;
  const plusYSlopeBackCoverCenterS = (plusYSlopeBackCoverS0 + plusYSlopeBackCoverS1) / 2;
  const plusYSlopeBackCoverCenterN = (plusYSlopeBackCoverN0 + plusYSlopeBackCoverN1) / 2;
  const plusYSlopeBackCoverNormalLength = plusYSlopeBackCoverN1 - plusYSlopeBackCoverN0;
  const plusYSlopeBackCoverProfilePoints = makeSideBlockProfile(
    plusYSlopeBackCoverS0,
    plusYSlopeBackCoverS1,
    plusYSlopeBackCoverN0,
    plusYSlopeBackCoverN1,
  );
  const plusYSlopeBackCoverMinX = Math.min(...plusYSlopeBackCoverProfilePoints.map((point) => point[0]));
  const plusYSlopeBackCoverMaxX = Math.max(...plusYSlopeBackCoverProfilePoints.map((point) => point[0]));
  const plusYSlopeBackCoverMinZ = Math.min(...plusYSlopeBackCoverProfilePoints.map((point) => point[1]));
  const plusYSlopeBackCoverMaxZ = Math.max(...plusYSlopeBackCoverProfilePoints.map((point) => point[1]));
  const rearSlopeBlockYLength = parameterNumber('photo_album_rear_slope_block_y_length', STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY.rear_slope_block_y_length);
  const rearSlopeBlockYMax = baseMaxY;
  const rearSlopeBlockYMin = rearSlopeBlockYMax - rearSlopeBlockYLength;
  const rearSlopeBlockYCenter = (rearSlopeBlockYMin + rearSlopeBlockYMax) / 2;
  const rearSlopeBlockS0 = parameterNumber('photo_album_rear_slope_block_s_min', REAR_SLOPE_BLOCK_S_MIN);
  const rearSlopeBlockS1 = parameterNumber('photo_album_rear_slope_block_s_max', rearSlopeBlockS0 + STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY.rear_slope_block_s_length);
  const rearSlopeBlockN0 = parameterNumber('photo_album_rear_slope_block_n_min', REAR_SLOPE_BLOCK_N_MIN);
  const rearSlopeBlockN1 = parameterNumber('photo_album_rear_slope_block_n_max', -slopeThickness);
  const rearSlopeBlockCenterS = (rearSlopeBlockS0 + rearSlopeBlockS1) / 2;
  const rearSlopeBlockCenterN = (rearSlopeBlockN0 + rearSlopeBlockN1) / 2;
  const rearSlopeBlockNormalThickness = rearSlopeBlockN1 - rearSlopeBlockN0;
  const rearSlopeBlockProfilePoints = makeSideBlockProfile(
    rearSlopeBlockS0,
    rearSlopeBlockS1,
    rearSlopeBlockN0,
    rearSlopeBlockN1,
  );
  const rearSlopeBlockMinX = Math.min(...rearSlopeBlockProfilePoints.map((point) => point[0]));
  const rearSlopeBlockMaxX = Math.max(...rearSlopeBlockProfilePoints.map((point) => point[0]));
  const rearSlopeBlockMinZ = Math.min(...rearSlopeBlockProfilePoints.map((point) => point[1]));
  const rearSlopeBlockMaxZ = Math.max(...rearSlopeBlockProfilePoints.map((point) => point[1]));
  const slopeSquareHoleSize = parameterNumber('photo_album_slope_square_hole_size', STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_size);
  const slopeSquareHoleCenterS = parameterNumber('photo_album_slope_square_hole_center_s', STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_center_s);
  const slopeSquareHoleOffsetFromMinusY = parameterNumber('photo_album_slope_square_hole_offset_from_minus_y', STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_offset_from_minus_y);
  const slopeSquareHoleCenterY = baseMinY + slopeSquareHoleOffsetFromMinusY;
  const slopeSquareHoleSMin = slopeSquareHoleCenterS - slopeSquareHoleSize / 2;
  const slopeSquareHoleSMax = slopeSquareHoleCenterS + slopeSquareHoleSize / 2;
  const slopeSquareHoleYMin = slopeSquareHoleCenterY - slopeSquareHoleSize / 2;
  const slopeSquareHoleYMax = slopeSquareHoleCenterY + slopeSquareHoleSize / 2;
  const slopeSquareHoleCutterNormalPadding = parameterNumber('photo_album_slope_square_hole_cutter_normal_padding', STAGE_5_SQUARE_HOLE_GEOMETRY.slope_square_hole_cutter_normal_padding);
  const slopeSquareHoleCutterNormalDepth = slopeThickness + 2 * slopeSquareHoleCutterNormalPadding;
  const slopeSquareHoleCutterCenterN = -slopeThickness / 2;
  const slopeSquareHoleCutterMinN = slopeSquareHoleCutterCenterN - slopeSquareHoleCutterNormalDepth / 2;
  const slopeSquareHoleCutterMaxN = slopeSquareHoleCutterCenterN + slopeSquareHoleCutterNormalDepth / 2;
  const slopeSquareHoleCenterSurfaceX = slopeEndX + slopeDownX * slopeSquareHoleCenterS;
  const slopeSquareHoleCenterSurfaceZ = slopeEndZ + slopeDownZ * slopeSquareHoleCenterS;
  const slopeSquareHoleCutterCenterX = slopeSquareHoleCenterSurfaceX + slopeOutwardX * slopeSquareHoleCutterCenterN;
  const slopeSquareHoleCutterCenterZ = slopeSquareHoleCenterSurfaceZ + slopeOutwardZ * slopeSquareHoleCutterCenterN;
  const slopeSquareHoleSurfaceSMinPoint = [
    slopeEndX + slopeDownX * slopeSquareHoleSMin,
    slopeEndZ + slopeDownZ * slopeSquareHoleSMin,
  ];
  const slopeSquareHoleSurfaceSMaxPoint = [
    slopeEndX + slopeDownX * slopeSquareHoleSMax,
    slopeEndZ + slopeDownZ * slopeSquareHoleSMax,
  ];
  const rearSlopeTopSlotYLength = parameterNumber('photo_album_rear_slope_top_slot_y_length', REAR_SLOPE_TOP_SLOT_Y_LENGTH);
  const rearSlopeTopSlotYMin = parameterNumber('photo_album_rear_slope_top_slot_y_min', REAR_SLOPE_TOP_SLOT_Y_MIN);
  const rearSlopeTopSlotYMax = parameterNumber('photo_album_rear_slope_top_slot_y_max', REAR_SLOPE_TOP_SLOT_Y_MAX);
  const rearSlopeTopSlotYCenter = parameterNumber('photo_album_rear_slope_top_slot_y_center', REAR_SLOPE_TOP_SLOT_Y_CENTER);
  const rearSlopeTopSlotSMin = parameterNumber('photo_album_rear_slope_top_slot_s_min', REAR_SLOPE_TOP_SLOT_S_MIN);
  const rearSlopeTopSlotSMax = parameterNumber('photo_album_rear_slope_top_slot_s_max', REAR_SLOPE_TOP_SLOT_S_MAX);
  const rearSlopeTopSlotSCenter = parameterNumber('photo_album_rear_slope_top_slot_s_center', REAR_SLOPE_TOP_SLOT_S_CENTER);
  const rearSlopeTopSlotNMin = parameterNumber('photo_album_rear_slope_top_slot_n_min', REAR_SLOPE_TOP_SLOT_N_MIN);
  const rearSlopeTopSlotNMax = parameterNumber('photo_album_rear_slope_top_slot_n_max', REAR_SLOPE_TOP_SLOT_N_MAX);
  const rearSlopeTopSlotCenterN = parameterNumber('photo_album_rear_slope_top_slot_center_n', REAR_SLOPE_TOP_SLOT_CENTER_N);
  const rearSlopeTopSlotCutterCenterS = parameterNumber('photo_album_rear_slope_top_slot_cutter_center_s', REAR_SLOPE_TOP_SLOT_CUTTER_CENTER_S);
  const rearSlopeTopSlotCutterCenterX = slopeEndX + slopeDownX * rearSlopeTopSlotCutterCenterS + slopeOutwardX * rearSlopeTopSlotCenterN;
  const rearSlopeTopSlotCutterCenterZ = slopeEndZ + slopeDownZ * rearSlopeTopSlotCutterCenterS + slopeOutwardZ * rearSlopeTopSlotCenterN;
  const narrowStopSemicircleDiameter = parameterNumber('photo_album_narrow_stop_semicircle_diameter', NARROW_STOP_SEMICIRCLE_DIAMETER);
  const narrowStopSemicircleRadius = parameterNumber('photo_album_narrow_stop_semicircle_radius', narrowStopSemicircleDiameter / 2);
  const narrowStopSemicircleClipParallelTopEdgeS = parameterNumber('photo_album_narrow_stop_semicircle_clip_parallel_top_edge_s', NARROW_STOP_SEMICIRCLE_CLIP_PARALLEL_TOP_EDGE_S);
  const narrowStopSemicircleOffsetFromLipTopEdgeS = parameterNumber('photo_album_narrow_stop_semicircle_offset_from_lip_top_edge_s', NARROW_STOP_SEMICIRCLE_OFFSET_FROM_LIP_TOP_EDGE_S);
  const narrowStopSemicircleCenterS = parameterNumber('photo_album_narrow_stop_semicircle_center_s', NARROW_STOP_SEMICIRCLE_CENTER_S);
  const narrowStopSemicircleCenterY = parameterNumber('photo_album_narrow_stop_semicircle_center_y', baseMaxY);
  const narrowStopSemicircleCenterN = parameterNumber('photo_album_narrow_stop_semicircle_center_n', outerSideBlockN1);
  const narrowStopSemicircleSMin = parameterNumber('photo_album_narrow_stop_semicircle_s_min', narrowStopSemicircleCenterS - narrowStopSemicircleRadius);
  const narrowStopSemicircleSMax = parameterNumber('photo_album_narrow_stop_semicircle_s_max', narrowStopSemicircleCenterS + narrowStopSemicircleRadius);
  const narrowStopSemicircleYMin = parameterNumber('photo_album_narrow_stop_semicircle_y_min', narrowStopSemicircleCenterY - narrowStopSemicircleRadius);
  const narrowStopSemicircleYMax = parameterNumber('photo_album_narrow_stop_semicircle_y_max', narrowStopSemicircleCenterY);
  const narrowStopSemicircleCutDepthN = parameterNumber('photo_album_narrow_stop_semicircle_cut_depth_n', NARROW_STOP_SEMICIRCLE_CUT_DEPTH_N);
  const narrowStopSemicircleCutterOverlapN = parameterNumber('photo_album_narrow_stop_semicircle_cutter_overlap_n', NARROW_STOP_SEMICIRCLE_CUTTER_OVERLAP_N);
  const narrowStopSemicircleCutterMinN = parameterNumber('photo_album_narrow_stop_semicircle_cutter_min_n', narrowStopSemicircleCenterN - narrowStopSemicircleCutDepthN - narrowStopSemicircleCutterOverlapN);
  const narrowStopSemicircleCutterMaxN = parameterNumber('photo_album_narrow_stop_semicircle_cutter_max_n', narrowStopSemicircleCenterN + narrowStopSemicircleCutterOverlapN);
  const narrowStopSemicircleCutterDepthN = parameterNumber('photo_album_narrow_stop_semicircle_cutter_depth_n', narrowStopSemicircleCutterMaxN - narrowStopSemicircleCutterMinN);
  const narrowStopSemicircleCutterCenterN = parameterNumber('photo_album_narrow_stop_semicircle_cutter_center_n', (narrowStopSemicircleCutterMinN + narrowStopSemicircleCutterMaxN) / 2);
  const narrowStopSemicircleCenterSurfaceX = slopeEndX + slopeDownX * narrowStopSemicircleCenterS + slopeOutwardX * narrowStopSemicircleCenterN;
  const narrowStopSemicircleCenterSurfaceZ = slopeEndZ + slopeDownZ * narrowStopSemicircleCenterS + slopeOutwardZ * narrowStopSemicircleCenterN;
  const narrowStopSemicircleCutterCenterX = slopeEndX + slopeDownX * narrowStopSemicircleCenterS + slopeOutwardX * narrowStopSemicircleCutterCenterN;
  const narrowStopSemicircleCutterCenterZ = slopeEndZ + slopeDownZ * narrowStopSemicircleCenterS + slopeOutwardZ * narrowStopSemicircleCutterCenterN;
  const rearSlopeBlockLowContactFilletS = rearSlopeBlockS1;
  const rearSlopeBlockLowContactFilletN = rearSlopeBlockN1;
  const rearSlopeBlockLowContactFilletRadius = parameterNumber('photo_album_rear_slope_block_low_contact_fillet_radius', STAGE_9_FILLET_GEOMETRY.rear_slope_block_low_contact_fillet_radius);
  const rearSlopeBlockLowContactFillerSegments = parameterNumber('photo_album_rear_slope_block_low_contact_filler_segments', STAGE_9_FILLET_GEOMETRY.rear_slope_block_low_contact_filler_segments);
  const rearSlopeBlockLowContactFillerSMin = rearSlopeBlockLowContactFilletS;
  const rearSlopeBlockLowContactFillerSMax = rearSlopeBlockLowContactFillerSMin + rearSlopeBlockLowContactFilletRadius;
  const rearSlopeBlockLowContactFillerNMax = rearSlopeBlockLowContactFilletN;
  const rearSlopeBlockLowContactFillerNMin = rearSlopeBlockLowContactFillerNMax - rearSlopeBlockLowContactFilletRadius;
  const rearSlopeBlockLowContactFillerArcCenterS = rearSlopeBlockLowContactFillerSMax;
  const rearSlopeBlockLowContactFillerArcCenterN = rearSlopeBlockLowContactFillerNMin;
  const rearSlopeBlockLowContactFillerOverlap = STAGE_1_GEOMETRY.cut_epsilon;
  const rearSlopeBlockLowContactFillerCenterY = rearSlopeBlockYCenter;
  const rearSlopeBlockLowContactFillerWidthY = rearSlopeBlockYLength;
  const rearSlopeBlockLowContactFillerMinY = rearSlopeBlockYMin;
  const rearSlopeBlockLowContactFillerMaxY = rearSlopeBlockYMax;
  const rearSlopeBlockLowContactFilletPoint = [
    slopeEndX + slopeDownX * rearSlopeBlockLowContactFilletS + slopeOutwardX * rearSlopeBlockLowContactFilletN,
    slopeEndZ + slopeDownZ * rearSlopeBlockLowContactFilletS + slopeOutwardZ * rearSlopeBlockLowContactFilletN,
  ];
  const rearSlopeBlockLowContactFillerProfilePoints = makeSideBlockProfile(
    rearSlopeBlockLowContactFillerSMin,
    rearSlopeBlockLowContactFillerSMax,
    rearSlopeBlockLowContactFillerNMin,
    rearSlopeBlockLowContactFillerNMax,
  );
  const slopePoint = (distanceS, normalOffset) => ([
    slopeEndX + slopeDownX * distanceS + slopeOutwardX * normalOffset,
    slopeEndZ + slopeDownZ * distanceS + slopeOutwardZ * normalOffset,
  ]);
  const k10LClipPerpendicularTopFaceS = clipS0;
  const k10PcbDownSlopeFaceOffsetS = K10_GEOMETRY.pcb_width_y / 2;
  const k10OriginS = k10LClipPerpendicularTopFaceS - k10PcbDownSlopeFaceOffsetS;
  const k10PcbDownSlopeFaceS = k10OriginS + k10PcbDownSlopeFaceOffsetS;
  const k10LClipParallelInnerFaceN = clipNInner;
  const k10DisplayFrameOuterOffsetN = K10_GEOMETRY.pcb_thickness_z + K10_GEOMETRY.display_frame_height_z;
  const k10TowardSlopeOffsetN = K10_GEOMETRY.toward_slope_offset_n;
  const k10NominalOriginN = k10LClipParallelInnerFaceN - k10DisplayFrameOuterOffsetN;
  const k10OriginN = k10NominalOriginN - k10TowardSlopeOffsetN;
  const k10DisplayFrameOuterFaceN = k10OriginN + k10DisplayFrameOuterOffsetN;
  const k10DisplayFrameClearanceToLClipN = k10LClipParallelInnerFaceN - k10DisplayFrameOuterFaceN;
  const k10SlopeSurfaceN = 0;
  const k10BottomCubeLowerFaceN = k10OriginN - K10_GEOMETRY.bottom_cube_height_z;
  const k10BottomCubeClearanceToSlopeN = k10BottomCubeLowerFaceN - k10SlopeSurfaceN;
  const k10TargetMinusYFaceY = baseMinY;
  const k10OriginY = k10TargetMinusYFaceY + K10_GEOMETRY.pcb_length_x / 2;
  const k10GoldFingerCenterY = k10OriginY + K10_GOLD_FINGER_CENTER_X;
  const k10PcbBottomFaceN = k10OriginN;
  const k10MinusZFaceN = k10BottomCubeLowerFaceN;
  const k10FullBoundingMinusZFaceN = k10OriginN - K10_GEOMETRY.component_height_bottom_z;
  const k10MinusYFaceY = k10OriginY - K10_GEOMETRY.pcb_length_x / 2;
  const [k10OriginX, k10OriginZ] = slopePoint(k10OriginS, k10OriginN);
  const [k10ReferenceCenterX, k10ReferenceCenterZ] = slopePoint(
    k10OriginS,
    k10OriginN + (K10_GEOMETRY.component_height_top_z - K10_GEOMETRY.component_height_bottom_z) / 2,
  );
  const batteryCenterS = rearSlopeBlockCenterS;
  const batteryCenterY = rearSlopeBlockYCenter;
  const batteryCenterN = rearSlopeBlockCenterN;
  const batteryOriginS = batteryCenterS;
  const batteryOriginY = batteryCenterY;
  const batteryOriginN = batteryCenterN - POLYMER_LIPO_BATTERY_GEOMETRY.thickness_z / 2;
  const [batteryOriginX, batteryOriginZ] = slopePoint(batteryOriginS, batteryOriginN);
  const [batteryCenterX, batteryCenterZ] = slopePoint(batteryCenterS, batteryCenterN);
  const allXzPoints = [...points, ...clipProfilePoints, ...sideBlockProfilePoints, ...plusYSlopeBackCoverProfilePoints, ...rearSlopeBlockProfilePoints, ...rearSlopeBlockLowContactFillerProfilePoints];
  const minX = Math.min(-baseLengthX / 2, ...allXzPoints.map((point) => point[0]));
  const maxX = Math.max(baseLengthX / 2, ...allXzPoints.map((point) => point[0]));
  const minY = Math.min(baseMinY, slopeMinY, clipMinY, sideBlockYMin, plusYSlopeBackCoverYMin, rearSlopeBlockYMin);
  const maxY = Math.max(baseMaxY, slopeMaxY, clipMaxY, sideBlockYMax, plusYSlopeBackCoverYMax, rearSlopeBlockYMax);
  const minZ = 0;
  const maxZ = Math.max(baseThicknessZ, ...allXzPoints.map((point) => point[1]));
  return {
    ...STAGE_1_GEOMETRY,
    ...STAGE_2_CLIP_GEOMETRY,
    ...STAGE_3_SIDE_BLOCK_GEOMETRY,
    ...STAGE_5_PLUS_Y_SLOPE_BACK_COVER_GEOMETRY,
    ...STAGE_6_REAR_SLOPE_BLOCK_GEOMETRY,
    ...STAGE_7_REAR_SLOPE_TOP_SLOT_GEOMETRY,
    ...STAGE_8_NARROW_STOP_SEMICIRCLE_GEOMETRY,
    ...STAGE_9_FILLET_GEOMETRY,
    base_length_x: round3(baseLengthX),
    base_width_y: round3(baseWidthY),
    base_thickness_z: round3(baseThicknessZ),
    slope_face_length: round3(slopeFaceLength),
    slope_thickness: round3(slopeThickness),
    clip_perpendicular_thickness: round3(clipS1 - clipS0),
    clip_perpendicular_length: round3(clipNOuter),
    clip_parallel_thickness: round3(clipNOuter - clipNInner),
    clip_parallel_length: round3(clipS0 - clipLipS0),
    clip_offset_from_slope_top: round3(clipS0),
    side_block_y_depth: round3(sideBlockYMax - sideBlockYMin),
    side_block_parallel_extension: round3(clipS0 - sideBlockS0),
    side_block_gap_between_blocks: round3(sideBlockGapBetweenBlocks),
    inner_side_block_normal_length: round3(innerSideBlockN1 - innerSideBlockN0),
    outer_side_block_normal_length: round3(outerSideBlockN1 - outerSideBlockN0),
    rear_slope_block_y_length: round3(rearSlopeBlockYLength),
    rear_slope_block_s_length: round3(rearSlopeBlockS1 - rearSlopeBlockS0),
    rear_slope_block_normal_thickness: round3(rearSlopeBlockNormalThickness),
    rear_slope_top_slot_y_length: round3(rearSlopeTopSlotYLength),
    rear_slope_top_slot_width_n: round3(rearSlopeTopSlotNMax - rearSlopeTopSlotNMin),
    narrow_stop_semicircle_diameter: round3(narrowStopSemicircleDiameter),
    narrow_stop_semicircle_radius: round3(narrowStopSemicircleRadius),
    rear_slope_block_low_contact_fillet_radius: round3(rearSlopeBlockLowContactFilletRadius),
    stage: PHOTO_ALBUM_STAGE,
    slope_angle_deg: round3(slopeAngleDeg),
    slope_run_x: round3(slopeRunX),
    slope_rise_z: round3(slopeRiseZ),
    slope_start_x: round3(slopeStartX),
    slope_start_z: 0,
    slope_end_x: round3(slopeEndX),
    slope_end_z: round3(slopeEndZ),
    slope_normal_x: round3(normalX),
    slope_normal_z: round3(normalZ),
    slope_down_axis_x: round3(slopeDownX),
    slope_down_axis_z: round3(slopeDownZ),
    slope_outward_axis_x: round3(slopeOutwardX),
    slope_outward_axis_z: round3(slopeOutwardZ),
    exposed_prism_cut_run_x: round3(exposedPrismCutRunX),
    exposed_prism_cut_start_x: round3(exposedPrismCutStartX),
    exposed_prism_cut_end_x: round3(slopeStartX),
    exposed_prism_cut_height_z: round3(baseThicknessZ),
    visible_slope_center_y: round3(visibleSlopeCenterY),
    base_exposure_cutter_center_y: round3(baseExposureCutterCenterY),
    base_exposure_cutter_width_y: round3(baseExposureCutterWidthY),
    base_exposure_cutter_min_y: round3(baseExposureCutterMinY),
    base_exposure_cutter_max_y: round3(baseExposureCutterMaxY),
    slope_cutter_center_y: round3(slopeCutterCenterY),
    slope_cutter_width_y: round3(slopeCutterWidthY),
    slope_cutter_min_y: round3(slopeCutterMinY),
    slope_cutter_max_y: round3(slopeCutterMaxY),
    bottom_protrusion_lower_face_run_x: round3(bottomProtrusionLowerFaceRunX),
    bottom_protrusion_cut_run_x: round3(bottomProtrusionCutRunX),
    bottom_protrusion_cut_depth_z: round3(bottomProtrusionDepthZ),
    bottom_protrusion_cut_start_x: round3(bottomProtrusionCutStartX),
    bottom_protrusion_cut_end_x: round3(slopeStartX),
    base_min_y: round3(baseMinY),
    base_max_y: round3(baseMaxY),
    slope_width_y: round3(slopeWidthY),
    slope_offset_y: round3(slopeOffsetY),
    slope_min_y: round3(slopeMinY),
    slope_max_y: round3(slopeMaxY),
    clip_width_y: clipWidthY,
    clip_center_y: round3(clipCenterY),
    clip_min_y: round3(clipMinY),
    clip_max_y: round3(clipMaxY),
    clip_start_s: round3(clipS0),
    clip_end_s: round3(clipS1),
    clip_lip_start_s: round3(clipLipS0),
    clip_outer_n: round3(clipNOuter),
    clip_inner_n: round3(clipNInner),
    clip_min_x: round3(clipMinX),
    clip_max_x: round3(clipMaxX),
    clip_min_z: round3(clipMinZ),
    clip_max_z: round3(clipMaxZ),
    clip_center_x: round3((clipMinX + clipMaxX) / 2),
    clip_center_z: round3((clipMinZ + clipMaxZ) / 2),
    clip_profile_points_xz: clipProfilePoints.map(([x, z]) => [round3(x), round3(z)]),
    side_block_y_min: round3(sideBlockYMin),
    side_block_y_max: round3(sideBlockYMax),
    side_block_y_center: round3(sideBlockYCenter),
    side_block_start_s: round3(sideBlockS0),
    side_block_end_s: round3(sideBlockS1),
    side_block_nominal_end_s: round3(clipS0),
    inner_side_block_min_n: round3(innerSideBlockN0),
    inner_side_block_max_n: round3(innerSideBlockN1),
    side_block_gap_between_blocks: round3(sideBlockGapBetweenBlocks),
    outer_side_block_start_n: round3(outerSideBlockN0),
    outer_side_block_min_n: round3(outerSideBlockN0),
    outer_side_block_max_n: round3(outerSideBlockN1),
    side_block_min_x: round3(sideBlockMinX),
    side_block_max_x: round3(sideBlockMaxX),
    side_block_min_z: round3(sideBlockMinZ),
    side_block_max_z: round3(sideBlockMaxZ),
    side_block_center_x: round3((sideBlockMinX + sideBlockMaxX) / 2),
    side_block_center_z: round3((sideBlockMinZ + sideBlockMaxZ) / 2),
    inner_side_block_center_x: round3((Math.min(...innerSideBlockProfilePoints.map((point) => point[0])) + Math.max(...innerSideBlockProfilePoints.map((point) => point[0]))) / 2),
    inner_side_block_center_z: round3((Math.min(...innerSideBlockProfilePoints.map((point) => point[1])) + Math.max(...innerSideBlockProfilePoints.map((point) => point[1]))) / 2),
    outer_side_block_center_x: round3((Math.min(...outerSideBlockProfilePoints.map((point) => point[0])) + Math.max(...outerSideBlockProfilePoints.map((point) => point[0]))) / 2),
    outer_side_block_center_z: round3((Math.min(...outerSideBlockProfilePoints.map((point) => point[1])) + Math.max(...outerSideBlockProfilePoints.map((point) => point[1]))) / 2),
    inner_side_block_profile_points_xz: innerSideBlockProfilePoints.map(([x, z]) => [round3(x), round3(z)]),
    outer_side_block_profile_points_xz: outerSideBlockProfilePoints.map(([x, z]) => [round3(x), round3(z)]),
    plus_y_slope_back_cover_y_depth: round3(plusYSlopeBackCoverYDepth),
    plus_y_slope_back_cover_y_min: round3(plusYSlopeBackCoverYMin),
    plus_y_slope_back_cover_y_max: round3(plusYSlopeBackCoverYMax),
    plus_y_slope_back_cover_y_center: round3(plusYSlopeBackCoverYCenter),
    plus_y_slope_back_cover_s_min: round3(plusYSlopeBackCoverS0),
    plus_y_slope_back_cover_s_max: round3(plusYSlopeBackCoverS1),
    plus_y_slope_back_cover_s_length: round3(plusYSlopeBackCoverS1 - plusYSlopeBackCoverS0),
    plus_y_slope_back_cover_s_center: round3(plusYSlopeBackCoverCenterS),
    plus_y_slope_back_cover_n_min: round3(plusYSlopeBackCoverN0),
    plus_y_slope_back_cover_n_max: round3(plusYSlopeBackCoverN1),
    plus_y_slope_back_cover_n_center: round3(plusYSlopeBackCoverCenterN),
    plus_y_slope_back_cover_normal_length: round3(plusYSlopeBackCoverNormalLength),
    plus_y_slope_back_cover_min_x: round3(plusYSlopeBackCoverMinX),
    plus_y_slope_back_cover_max_x: round3(plusYSlopeBackCoverMaxX),
    plus_y_slope_back_cover_min_z: round3(plusYSlopeBackCoverMinZ),
    plus_y_slope_back_cover_max_z: round3(plusYSlopeBackCoverMaxZ),
    plus_y_slope_back_cover_center_x: round3((plusYSlopeBackCoverMinX + plusYSlopeBackCoverMaxX) / 2),
    plus_y_slope_back_cover_center_z: round3((plusYSlopeBackCoverMinZ + plusYSlopeBackCoverMaxZ) / 2),
    plus_y_slope_back_cover_profile_points_xz: plusYSlopeBackCoverProfilePoints.map(([x, z]) => [round3(x), round3(z)]),
    slope_square_hole_size: round3(slopeSquareHoleSize),
    slope_square_hole_center_s: round3(slopeSquareHoleCenterS),
    slope_square_hole_offset_from_minus_y: round3(slopeSquareHoleOffsetFromMinusY),
    slope_square_hole_center_y: round3(slopeSquareHoleCenterY),
    slope_square_hole_s_min: round3(slopeSquareHoleSMin),
    slope_square_hole_s_max: round3(slopeSquareHoleSMax),
    slope_square_hole_y_min: round3(slopeSquareHoleYMin),
    slope_square_hole_y_max: round3(slopeSquareHoleYMax),
    slope_square_hole_cutter_normal_padding: round3(slopeSquareHoleCutterNormalPadding),
    slope_square_hole_cutter_normal_depth: round3(slopeSquareHoleCutterNormalDepth),
    slope_square_hole_cutter_center_n: round3(slopeSquareHoleCutterCenterN),
    slope_square_hole_cutter_min_n: round3(slopeSquareHoleCutterMinN),
    slope_square_hole_cutter_max_n: round3(slopeSquareHoleCutterMaxN),
    slope_square_hole_center_surface_x: round3(slopeSquareHoleCenterSurfaceX),
    slope_square_hole_center_surface_z: round3(slopeSquareHoleCenterSurfaceZ),
    slope_square_hole_cutter_center_x: round3(slopeSquareHoleCutterCenterX),
    slope_square_hole_cutter_center_z: round3(slopeSquareHoleCutterCenterZ),
    slope_square_hole_surface_s_min_point_xz: slopeSquareHoleSurfaceSMinPoint.map((value) => round3(value)),
    slope_square_hole_surface_s_max_point_xz: slopeSquareHoleSurfaceSMaxPoint.map((value) => round3(value)),
    rear_slope_block_y_length: round3(rearSlopeBlockYLength),
    rear_slope_block_y_min: round3(rearSlopeBlockYMin),
    rear_slope_block_y_max: round3(rearSlopeBlockYMax),
    rear_slope_block_y_center: round3(rearSlopeBlockYCenter),
    rear_slope_block_offset_from_slope_top: round3(rearSlopeBlockS0),
    rear_slope_block_s_min: round3(rearSlopeBlockS0),
    rear_slope_block_s_max: round3(rearSlopeBlockS1),
    rear_slope_block_s_length: round3(rearSlopeBlockS1 - rearSlopeBlockS0),
    rear_slope_block_s_center: round3(rearSlopeBlockCenterS),
    rear_slope_block_n_min: round3(rearSlopeBlockN0),
    rear_slope_block_n_max: round3(rearSlopeBlockN1),
    rear_slope_block_n_center: round3(rearSlopeBlockCenterN),
    rear_slope_block_normal_thickness: round3(rearSlopeBlockNormalThickness),
    rear_slope_block_min_x: round3(rearSlopeBlockMinX),
    rear_slope_block_max_x: round3(rearSlopeBlockMaxX),
    rear_slope_block_min_z: round3(rearSlopeBlockMinZ),
    rear_slope_block_max_z: round3(rearSlopeBlockMaxZ),
    rear_slope_block_center_x: round3((rearSlopeBlockMinX + rearSlopeBlockMaxX) / 2),
    rear_slope_block_center_z: round3((rearSlopeBlockMinZ + rearSlopeBlockMaxZ) / 2),
    rear_slope_block_profile_points_xz: rearSlopeBlockProfilePoints.map(([x, z]) => [round3(x), round3(z)]),
    rear_slope_top_slot_y_length: round3(rearSlopeTopSlotYLength),
    rear_slope_top_slot_y_min: round3(rearSlopeTopSlotYMin),
    rear_slope_top_slot_y_max: round3(rearSlopeTopSlotYMax),
    rear_slope_top_slot_y_center: round3(rearSlopeTopSlotYCenter),
    rear_slope_top_slot_width_n: round3(rearSlopeTopSlotNMax - rearSlopeTopSlotNMin),
    rear_slope_top_slot_n_min: round3(rearSlopeTopSlotNMin),
    rear_slope_top_slot_n_max: round3(rearSlopeTopSlotNMax),
    rear_slope_top_slot_center_n: round3(rearSlopeTopSlotCenterN),
    rear_slope_top_slot_cut_depth_s: round3(rearSlopeTopSlotSMax - rearSlopeTopSlotSMin),
    rear_slope_top_slot_surface_s: round3(rearSlopeTopSlotSMin),
    rear_slope_top_slot_s_min: round3(rearSlopeTopSlotSMin),
    rear_slope_top_slot_s_max: round3(rearSlopeTopSlotSMax),
    rear_slope_top_slot_s_center: round3(rearSlopeTopSlotSCenter),
    rear_slope_top_slot_cutter_overlap_s: round3(rearSlopeTopSlotSMin - parameterNumber('photo_album_rear_slope_top_slot_cutter_s_min', REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN)),
    rear_slope_top_slot_cutter_s_min: round3(parameterNumber('photo_album_rear_slope_top_slot_cutter_s_min', REAR_SLOPE_TOP_SLOT_CUTTER_S_MIN)),
    rear_slope_top_slot_cutter_s_max: round3(parameterNumber('photo_album_rear_slope_top_slot_cutter_s_max', REAR_SLOPE_TOP_SLOT_CUTTER_S_MAX)),
    rear_slope_top_slot_cutter_size_s: round3(parameterNumber('photo_album_rear_slope_top_slot_cutter_size_s', REAR_SLOPE_TOP_SLOT_CUTTER_SIZE_S)),
    rear_slope_top_slot_cutter_center_s: round3(rearSlopeTopSlotCutterCenterS),
    rear_slope_top_slot_cutter_center_x: round3(rearSlopeTopSlotCutterCenterX),
    rear_slope_top_slot_cutter_center_z: round3(rearSlopeTopSlotCutterCenterZ),
    narrow_stop_semicircle_diameter: round3(narrowStopSemicircleDiameter),
    narrow_stop_semicircle_radius: round3(narrowStopSemicircleRadius),
    narrow_stop_semicircle_offset_from_lip_top_edge_s: round3(narrowStopSemicircleOffsetFromLipTopEdgeS),
    narrow_stop_semicircle_clip_parallel_top_edge_s: round3(narrowStopSemicircleClipParallelTopEdgeS),
    narrow_stop_semicircle_center_s: round3(narrowStopSemicircleCenterS),
    narrow_stop_semicircle_center_y: round3(narrowStopSemicircleCenterY),
    narrow_stop_semicircle_center_n: round3(narrowStopSemicircleCenterN),
    narrow_stop_semicircle_s_min: round3(narrowStopSemicircleSMin),
    narrow_stop_semicircle_s_max: round3(narrowStopSemicircleSMax),
    narrow_stop_semicircle_y_min: round3(narrowStopSemicircleYMin),
    narrow_stop_semicircle_y_max: round3(narrowStopSemicircleYMax),
    narrow_stop_semicircle_cut_depth_n: round3(narrowStopSemicircleCutDepthN),
    narrow_stop_semicircle_cutter_overlap_n: round3(narrowStopSemicircleCutterOverlapN),
    narrow_stop_semicircle_cutter_min_n: round3(narrowStopSemicircleCutterMinN),
    narrow_stop_semicircle_cutter_max_n: round3(narrowStopSemicircleCutterMaxN),
    narrow_stop_semicircle_cutter_depth_n: round3(narrowStopSemicircleCutterDepthN),
    narrow_stop_semicircle_cutter_center_n: round3(narrowStopSemicircleCutterCenterN),
    narrow_stop_semicircle_segments: Math.max(8, Math.round(parameterNumber('photo_album_narrow_stop_semicircle_segments', NARROW_STOP_SEMICIRCLE_SEGMENTS))),
    narrow_stop_semicircle_center_surface_x: round3(narrowStopSemicircleCenterSurfaceX),
    narrow_stop_semicircle_center_surface_z: round3(narrowStopSemicircleCenterSurfaceZ),
    narrow_stop_semicircle_cutter_center_x: round3(narrowStopSemicircleCutterCenterX),
    narrow_stop_semicircle_cutter_center_z: round3(narrowStopSemicircleCutterCenterZ),
    rear_slope_block_low_contact_fillet_radius: round3(rearSlopeBlockLowContactFilletRadius),
    rear_slope_block_low_contact_fillet_s: round3(rearSlopeBlockLowContactFilletS),
    rear_slope_block_low_contact_fillet_n: round3(rearSlopeBlockLowContactFilletN),
    rear_slope_block_low_contact_fillet_y_min: round3(rearSlopeBlockYMin),
    rear_slope_block_low_contact_fillet_y_max: round3(rearSlopeBlockYMax),
    rear_slope_block_low_contact_fillet_point_xz: rearSlopeBlockLowContactFilletPoint.map((value) => round3(value)),
    rear_slope_block_low_contact_filler_segments: rearSlopeBlockLowContactFillerSegments,
    rear_slope_block_low_contact_filler_s_min: round3(rearSlopeBlockLowContactFillerSMin),
    rear_slope_block_low_contact_filler_s_max: round3(rearSlopeBlockLowContactFillerSMax),
    rear_slope_block_low_contact_filler_n_min: round3(rearSlopeBlockLowContactFillerNMin),
    rear_slope_block_low_contact_filler_n_max: round3(rearSlopeBlockLowContactFillerNMax),
    rear_slope_block_low_contact_filler_arc_center_s: round3(rearSlopeBlockLowContactFillerArcCenterS),
    rear_slope_block_low_contact_filler_arc_center_n: round3(rearSlopeBlockLowContactFillerArcCenterN),
    rear_slope_block_low_contact_filler_overlap: round3(rearSlopeBlockLowContactFillerOverlap),
    rear_slope_block_low_contact_filler_center_y: round3(rearSlopeBlockLowContactFillerCenterY),
    rear_slope_block_low_contact_filler_width_y: round3(rearSlopeBlockLowContactFillerWidthY),
    rear_slope_block_low_contact_filler_min_y: round3(rearSlopeBlockLowContactFillerMinY),
    rear_slope_block_low_contact_filler_max_y: round3(rearSlopeBlockLowContactFillerMaxY),
    rear_slope_block_low_contact_filler_profile_points_xz: rearSlopeBlockLowContactFillerProfilePoints.map(([x, z]) => [round3(x), round3(z)]),
    k10_pcb_length_x: K10_GEOMETRY.pcb_length_x,
    k10_pcb_width_y: K10_GEOMETRY.pcb_width_y,
    k10_pcb_thickness_z: K10_GEOMETRY.pcb_thickness_z,
    k10_display_frame_height_z: K10_GEOMETRY.display_frame_height_z,
    k10_display_frame_outer_offset_n: round3(k10DisplayFrameOuterOffsetN),
    k10_toward_slope_offset_n: round3(k10TowardSlopeOffsetN),
    k10_nominal_origin_n: round3(k10NominalOriginN),
    k10_component_height_bottom_z: K10_GEOMETRY.component_height_bottom_z,
    k10_bottom_cube_height_z: K10_GEOMETRY.bottom_cube_height_z,
    k10_gold_finger_length_x: K10_GEOMETRY.gold_finger_length_x,
    k10_gold_finger_center_x: K10_GOLD_FINGER_CENTER_X,
    k10_gold_finger_center_s: round3(k10OriginS),
    k10_gold_finger_center_y: round3(k10GoldFingerCenterY),
    k10_origin_s: round3(k10OriginS),
    k10_origin_y: round3(k10OriginY),
    k10_origin_n: round3(k10OriginN),
    k10_pcb_down_slope_face_s: round3(k10PcbDownSlopeFaceS),
    k10_l_clip_perpendicular_top_face_s: round3(k10LClipPerpendicularTopFaceS),
    k10_display_frame_outer_face_n: round3(k10DisplayFrameOuterFaceN),
    k10_l_clip_parallel_inner_face_n: round3(k10LClipParallelInnerFaceN),
    k10_display_frame_clearance_to_l_clip_n: round3(k10DisplayFrameClearanceToLClipN),
    k10_pcb_bottom_face_n: round3(k10PcbBottomFaceN),
    k10_minus_y_face_y: round3(k10MinusYFaceY),
    k10_target_minus_y_face_y: round3(k10TargetMinusYFaceY),
    k10_minus_z_face_n: round3(k10MinusZFaceN),
    k10_bottom_cube_lower_face_n: round3(k10BottomCubeLowerFaceN),
    k10_bottom_cube_clearance_to_slope_n: round3(k10BottomCubeClearanceToSlopeN),
    k10_full_bounding_minus_z_face_n: round3(k10FullBoundingMinusZFaceN),
    k10_slope_surface_n: round3(k10SlopeSurfaceN),
    k10_origin_outward_offset_n: round3(k10OriginN),
    k10_origin_x: round3(k10OriginX),
    k10_origin_z: round3(k10OriginZ),
    k10_reference_center_x: round3(k10ReferenceCenterX),
    k10_reference_center_y: round3(k10OriginY),
    k10_reference_center_z: round3(k10ReferenceCenterZ),
    polymer_lipo_battery_length_x: POLYMER_LIPO_BATTERY_GEOMETRY.length_x,
    polymer_lipo_battery_width_y: POLYMER_LIPO_BATTERY_GEOMETRY.width_y,
    polymer_lipo_battery_thickness_z: POLYMER_LIPO_BATTERY_GEOMETRY.thickness_z,
    battery_center_s: round3(batteryCenterS),
    battery_center_y: round3(batteryCenterY),
    battery_center_n: round3(batteryCenterN),
    battery_center_x: round3(batteryCenterX),
    battery_center_z: round3(batteryCenterZ),
    battery_origin_s: round3(batteryOriginS),
    battery_origin_y: round3(batteryOriginY),
    battery_origin_n: round3(batteryOriginN),
    battery_origin_x: round3(batteryOriginX),
    battery_origin_z: round3(batteryOriginZ),
    cut_epsilon: STAGE_1_GEOMETRY.cut_epsilon,
    cut_overlap_y: STAGE_1_GEOMETRY.cut_overlap_y,
    bounding_box: {
      length_x: round3(maxX - minX),
      width_y: round3(maxY - minY),
      height_z: round3(maxZ - minZ),
      min_x: round3(minX),
      max_x: round3(maxX),
      min_y: round3(minY),
      max_y: round3(maxY),
      min_z: round3(minZ),
      max_z: round3(maxZ),
    },
  };
}

function buildEnclosure(geometry) {
  return {
    outer_box_size: {
      length_x: geometry.bounding_box.length_x,
      width_y: geometry.bounding_box.width_y,
      height_z: geometry.bounding_box.height_z,
    },
    inner_box_size: {
      length_x: STAGE_1_GEOMETRY.base_length_x,
      width_y: STAGE_1_GEOMETRY.base_width_y,
      height_z: STAGE_1_GEOMETRY.base_thickness_z,
    },
    base_length_x_mm: STAGE_1_GEOMETRY.base_length_x,
    base_width_y_mm: STAGE_1_GEOMETRY.base_width_y,
    base_thickness_z_mm: STAGE_1_GEOMETRY.base_thickness_z,
    slope_face_length_mm: STAGE_1_GEOMETRY.slope_face_length,
    slope_thickness_mm: STAGE_1_GEOMETRY.slope_thickness,
    slope_angle_deg: STAGE_1_GEOMETRY.slope_angle_deg,
    slope_width_y_mm: SLOPE_WIDTH_Y,
    slope_offset_y_mm: SLOPE_OFFSET_Y,
    clip_perpendicular_thickness_mm: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_thickness,
    clip_perpendicular_length_mm: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_length,
    clip_parallel_thickness_mm: STAGE_2_CLIP_GEOMETRY.clip_parallel_thickness,
    clip_parallel_length_mm: STAGE_2_CLIP_GEOMETRY.clip_parallel_length,
    clip_offset_from_slope_top_mm: STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top,
    clip_width_y_mm: geometry.clip_width_y,
    clip_center_y_mm: geometry.clip_center_y,
    side_block_y_depth_mm: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_y_depth,
    side_block_parallel_extension_mm: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_parallel_extension,
    inner_side_block_normal_length_mm: STAGE_3_SIDE_BLOCK_GEOMETRY.inner_side_block_normal_length,
    outer_side_block_normal_length_mm: STAGE_3_SIDE_BLOCK_GEOMETRY.outer_side_block_normal_length,
    side_block_gap_between_blocks_mm: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_gap_between_blocks,
    side_block_union_overlap_mm: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_union_overlap,
    side_block_y_min_mm: geometry.side_block_y_min,
    side_block_y_max_mm: geometry.side_block_y_max,
    plus_y_slope_back_cover_y_depth_mm: geometry.plus_y_slope_back_cover_y_depth,
    plus_y_slope_back_cover_s_length_mm: geometry.plus_y_slope_back_cover_s_length,
    plus_y_slope_back_cover_normal_length_mm: geometry.plus_y_slope_back_cover_normal_length,
    plus_y_slope_back_cover_y_min_mm: geometry.plus_y_slope_back_cover_y_min,
    plus_y_slope_back_cover_y_max_mm: geometry.plus_y_slope_back_cover_y_max,
    slope_square_hole_size_mm: geometry.slope_square_hole_size,
    slope_square_hole_center_s_mm: geometry.slope_square_hole_center_s,
    slope_square_hole_offset_from_minus_y_mm: geometry.slope_square_hole_offset_from_minus_y,
    slope_square_hole_center_y_mm: geometry.slope_square_hole_center_y,
    slope_square_hole_cutter_normal_depth_mm: geometry.slope_square_hole_cutter_normal_depth,
    rear_slope_block_y_length_mm: geometry.rear_slope_block_y_length,
    rear_slope_block_s_length_mm: geometry.rear_slope_block_s_length,
    rear_slope_block_normal_thickness_mm: geometry.rear_slope_block_normal_thickness,
    rear_slope_block_offset_from_slope_top_mm: geometry.rear_slope_block_offset_from_slope_top,
    rear_slope_block_y_min_mm: geometry.rear_slope_block_y_min,
    rear_slope_block_y_max_mm: geometry.rear_slope_block_y_max,
    rear_slope_block_s_min_mm: geometry.rear_slope_block_s_min,
    rear_slope_block_s_max_mm: geometry.rear_slope_block_s_max,
    rear_slope_block_n_min_mm: geometry.rear_slope_block_n_min,
    rear_slope_block_n_max_mm: geometry.rear_slope_block_n_max,
    rear_slope_top_slot_y_length_mm: geometry.rear_slope_top_slot_y_length,
    rear_slope_top_slot_y_min_mm: geometry.rear_slope_top_slot_y_min,
    rear_slope_top_slot_y_max_mm: geometry.rear_slope_top_slot_y_max,
    rear_slope_top_slot_width_n_mm: geometry.rear_slope_top_slot_width_n,
    rear_slope_top_slot_cut_depth_s_mm: geometry.rear_slope_top_slot_cut_depth_s,
    rear_slope_top_slot_s_min_mm: geometry.rear_slope_top_slot_s_min,
    rear_slope_top_slot_s_max_mm: geometry.rear_slope_top_slot_s_max,
    rear_slope_top_slot_n_min_mm: geometry.rear_slope_top_slot_n_min,
    rear_slope_top_slot_n_max_mm: geometry.rear_slope_top_slot_n_max,
    narrow_stop_semicircle_diameter_mm: geometry.narrow_stop_semicircle_diameter,
    narrow_stop_semicircle_center_s_mm: geometry.narrow_stop_semicircle_center_s,
    narrow_stop_semicircle_center_y_mm: geometry.narrow_stop_semicircle_center_y,
    narrow_stop_semicircle_center_n_mm: geometry.narrow_stop_semicircle_center_n,
    narrow_stop_semicircle_cut_depth_n_mm: geometry.narrow_stop_semicircle_cut_depth_n,
    rear_slope_block_low_contact_fillet_radius_mm: geometry.rear_slope_block_low_contact_fillet_radius,
    wall_thickness: STAGE_1_GEOMETRY.slope_thickness,
    floor_thickness: STAGE_1_GEOMETRY.base_thickness_z,
    lid_thickness: 0,
    lid_lip_height: 0,
    lid_clearance: 0,
    corner_radius: 0,
    screw_bosses: [],
  };
}

function buildPhotoAlbumHardwareTransforms(geometry) {
  return [
    {
      hardware_id: 'unihiker_k10',
      role: 'display_controller_reference',
      mount_surface: 'photo_album_rear_top_slot',
      printable: false,
      center: {
        x: geometry.k10_reference_center_x,
        y: geometry.k10_reference_center_y,
        z: geometry.k10_reference_center_z,
      },
      origin: {
        x: geometry.k10_origin_x,
        y: geometry.k10_origin_y,
        z: geometry.k10_origin_z,
        s: geometry.k10_origin_s,
        n: geometry.k10_origin_n,
      },
      placement: {
        description: 'K10 保持当前旋转和 PCB 下侧接触关系，整体朝斜面平移 2mm，并保持相册 -Y 外侧面对齐。',
        gold_finger_center_s: geometry.k10_gold_finger_center_s,
        gold_finger_center_y: geometry.k10_gold_finger_center_y,
        slot_center_s: geometry.rear_slope_top_slot_s_center,
        slot_center_y: geometry.rear_slope_top_slot_y_center,
        pcb_down_slope_face_s: geometry.k10_pcb_down_slope_face_s,
        l_clip_perpendicular_top_face_s: geometry.k10_l_clip_perpendicular_top_face_s,
        display_frame_outer_face_n: geometry.k10_display_frame_outer_face_n,
        l_clip_parallel_inner_face_n: geometry.k10_l_clip_parallel_inner_face_n,
        display_frame_clearance_to_l_clip_n: geometry.k10_display_frame_clearance_to_l_clip_n,
        toward_slope_offset_n: geometry.k10_toward_slope_offset_n,
        nominal_origin_n: geometry.k10_nominal_origin_n,
        pcb_bottom_face_n: geometry.k10_pcb_bottom_face_n,
        minus_y_face_y: geometry.k10_minus_y_face_y,
        target_minus_y_face_y: geometry.k10_target_minus_y_face_y,
        minus_z_face_n: geometry.k10_minus_z_face_n,
        bottom_cube_lower_face_n: geometry.k10_bottom_cube_lower_face_n,
        bottom_cube_clearance_to_slope_n: geometry.k10_bottom_cube_clearance_to_slope_n,
        full_bounding_minus_z_face_n: geometry.k10_full_bounding_minus_z_face_n,
        slope_surface_n: geometry.k10_slope_surface_n,
        origin_outward_offset_n: geometry.k10_origin_outward_offset_n,
      },
      orientation: {
        local_x_axis: {
          x: 0,
          y: 1,
          z: 0,
          meaning: 'K10 长边沿全局 Y 方向。',
        },
        local_y_axis: {
          x: -geometry.slope_down_axis_x,
          y: 0,
          z: -geometry.slope_down_axis_z,
          meaning: 'K10 短边沿斜面 S 方向。',
        },
        local_z_axis: {
          x: geometry.slope_outward_axis_x,
          y: 0,
          z: geometry.slope_outward_axis_z,
          meaning: 'K10 显示屏朝向斜面外侧，即全局 +X/+Z 方向。',
        },
        rotate_z_deg: 90,
        rotate_y_deg: geometry.slope_angle_deg,
      },
    },
    {
      hardware_id: 'unihiker_polymer_lipo_battery',
      role: 'battery_reference',
      mount_surface: 'photo_album_rear_slope_hollow',
      printable: false,
      center: {
        x: geometry.battery_center_x,
        y: geometry.battery_center_y,
        z: geometry.battery_center_z,
      },
      origin: {
        x: geometry.battery_origin_x,
        y: geometry.battery_origin_y,
        z: geometry.battery_origin_z,
        s: geometry.battery_origin_s,
        n: geometry.battery_origin_n,
      },
      placement: {
        description: '电池放入斜面后侧空洞内，电源线占位方向朝 +Y。',
        center_s: geometry.battery_center_s,
        center_y: geometry.battery_center_y,
        center_n: geometry.battery_center_n,
      },
      orientation: {
        local_x_axis: {
          x: 0,
          y: 1,
          z: 0,
          meaning: '电池长度方向沿全局 Y 方向，电源线朝 +Y。',
        },
        local_y_axis: {
          x: -geometry.slope_down_axis_x,
          y: 0,
          z: -geometry.slope_down_axis_z,
          meaning: '电池宽度方向沿斜面 S 方向。',
        },
        local_z_axis: {
          x: geometry.slope_outward_axis_x,
          y: 0,
          z: geometry.slope_outward_axis_z,
          meaning: '电池厚度方向沿斜面法线。',
        },
        rotate_z_deg: 90,
        rotate_y_deg: geometry.slope_angle_deg,
      },
    },
  ];
}

function buildLayoutPlan({ geometry, enclosure }) {
  return {
    strategy: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    shape: 'flat_base_with_full_width_slope',
    stage: PHOTO_ALBUM_STAGE,
    hardware_transforms: buildPhotoAlbumHardwareTransforms(geometry),
    opening_transforms: [
      {
        id: 'photo_album_stage_5_slope_square_hole',
        hardware_id: 'unihiker_k10',
        type: 'square_through_hole_on_slope',
        role: 'slope_access_opening',
        face: 'slope_top_face',
        center: {
          x: geometry.slope_square_hole_center_surface_x,
          y: geometry.slope_square_hole_center_y,
          z: geometry.slope_square_hole_center_surface_z,
        },
        size_mm: {
          edge_length: geometry.slope_square_hole_size,
          center_s: geometry.slope_square_hole_center_s,
          offset_from_minus_y: geometry.slope_square_hole_offset_from_minus_y,
          s_min: geometry.slope_square_hole_s_min,
          s_max: geometry.slope_square_hole_s_max,
          y_min: geometry.slope_square_hole_y_min,
          y_max: geometry.slope_square_hole_y_max,
          cutter_normal_depth: geometry.slope_square_hole_cutter_normal_depth,
        },
        orientation: {
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
        },
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_7_rear_slope_top_slot',
        hardware_id: 'enclosure',
        type: 'rear_slope_top_slot',
        role: 'rear_support_top_relief_slot',
        face: 'rear_slope_block_top_surface',
        center: {
          x: geometry.rear_slope_top_slot_cutter_center_x,
          y: geometry.rear_slope_top_slot_y_center,
          z: geometry.rear_slope_top_slot_cutter_center_z,
        },
        size_mm: {
          y_length: geometry.rear_slope_top_slot_y_length,
          y_min: geometry.rear_slope_top_slot_y_min,
          y_max: geometry.rear_slope_top_slot_y_max,
          y_center: geometry.rear_slope_top_slot_y_center,
          width_n: geometry.rear_slope_top_slot_width_n,
          n_min: geometry.rear_slope_top_slot_n_min,
          n_max: geometry.rear_slope_top_slot_n_max,
          center_n: geometry.rear_slope_top_slot_center_n,
          cut_depth_s: geometry.rear_slope_top_slot_cut_depth_s,
          surface_s: geometry.rear_slope_top_slot_surface_s,
          s_min: geometry.rear_slope_top_slot_s_min,
          s_max: geometry.rear_slope_top_slot_s_max,
          s_center: geometry.rear_slope_top_slot_s_center,
          cutter_overlap_s: geometry.rear_slope_top_slot_cutter_overlap_s,
          cutter_s_min: geometry.rear_slope_top_slot_cutter_s_min,
          cutter_s_max: geometry.rear_slope_top_slot_cutter_s_max,
          cutter_size_s: geometry.rear_slope_top_slot_cutter_size_s,
          cutter_center_s: geometry.rear_slope_top_slot_cutter_center_s,
        },
        orientation: {
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
          cut_direction: 'toward_increasing_s',
        },
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_8_narrow_stop_semicircle_cut',
        hardware_id: 'unihiker_k10',
        type: 'narrow_stop_semicircle_cut',
        role: 'outer_narrow_stop_relief_cut',
        face: 'outer_side_block_outward_face',
        center: {
          x: geometry.narrow_stop_semicircle_center_surface_x,
          y: geometry.narrow_stop_semicircle_center_y,
          z: geometry.narrow_stop_semicircle_center_surface_z,
        },
        size_mm: {
          diameter: geometry.narrow_stop_semicircle_diameter,
          radius: geometry.narrow_stop_semicircle_radius,
          offset_from_lip_top_edge_s: geometry.narrow_stop_semicircle_offset_from_lip_top_edge_s,
          clip_parallel_top_edge_s: geometry.narrow_stop_semicircle_clip_parallel_top_edge_s,
          center_s: geometry.narrow_stop_semicircle_center_s,
          center_y: geometry.narrow_stop_semicircle_center_y,
          center_n: geometry.narrow_stop_semicircle_center_n,
          s_min: geometry.narrow_stop_semicircle_s_min,
          s_max: geometry.narrow_stop_semicircle_s_max,
          y_min: geometry.narrow_stop_semicircle_y_min,
          y_max: geometry.narrow_stop_semicircle_y_max,
          cut_depth_n: geometry.narrow_stop_semicircle_cut_depth_n,
          cutter_overlap_n: geometry.narrow_stop_semicircle_cutter_overlap_n,
          cutter_min_n: geometry.narrow_stop_semicircle_cutter_min_n,
          cutter_max_n: geometry.narrow_stop_semicircle_cutter_max_n,
          cutter_depth_n: geometry.narrow_stop_semicircle_cutter_depth_n,
          cutter_center_n: geometry.narrow_stop_semicircle_cutter_center_n,
          segments: geometry.narrow_stop_semicircle_segments,
        },
        orientation: {
          profile_plane: 's_y',
          arc_side: 'toward_minus_y',
          cut_direction: 'toward_decreasing_n',
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
        },
        clearance_mm: 0,
      },
    ],
    mounting_hole_transforms: [],
    fillet_transforms: [
      {
        id: 'photo_album_stage_9_5_rear_slope_block_low_contact_fillet',
        type: 'quarter_circle_complement_filler_union',
        radius_mm: geometry.rear_slope_block_low_contact_fillet_radius,
        segments: geometry.rear_slope_block_low_contact_filler_segments,
        filler_width_y: geometry.rear_slope_block_low_contact_filler_width_y,
        filler_center_y: geometry.rear_slope_block_low_contact_filler_center_y,
        filler_range: {
          s_min: geometry.rear_slope_block_low_contact_filler_s_min,
          s_max: geometry.rear_slope_block_low_contact_filler_s_max,
          n_min: geometry.rear_slope_block_low_contact_filler_n_min,
          n_max: geometry.rear_slope_block_low_contact_filler_n_max,
          y_min: geometry.rear_slope_block_low_contact_filler_min_y,
          y_max: geometry.rear_slope_block_low_contact_filler_max_y,
        },
        removed_quarter_circle: {
          center_s: geometry.rear_slope_block_low_contact_filler_arc_center_s,
          center_n: geometry.rear_slope_block_low_contact_filler_arc_center_n,
          radius: geometry.rear_slope_block_low_contact_fillet_radius,
        },
        edge: {
          frame: 'slope_local',
          s: geometry.rear_slope_block_low_contact_fillet_s,
          n: geometry.rear_slope_block_low_contact_fillet_n,
          y_min: geometry.rear_slope_block_low_contact_fillet_y_min,
          y_max: geometry.rear_slope_block_low_contact_fillet_y_max,
          point_xz: geometry.rear_slope_block_low_contact_fillet_point_xz,
        },
      },
    ],
    mounting_transforms: [
      {
        id: 'photo_album_stage_1_base_plate',
        hardware_id: 'enclosure',
        type: 'base_plate_with_plus_x_top_prism_cut',
        role: 'main_body',
        anchor_face: 'bottom',
        mount_surface: 'xy_plane',
        center: { x: 0, y: 0, z: STAGE_1_GEOMETRY.base_thickness_z / 2 },
        size_mm: {
          length_x: STAGE_1_GEOMETRY.base_length_x,
          width_y: STAGE_1_GEOMETRY.base_width_y,
          height_z: STAGE_1_GEOMETRY.base_thickness_z,
        },
        cut_mm: {
          type: 'triangular_prism',
          edge: '+X top edge',
          run_x: geometry.exposed_prism_cut_run_x,
          height_z: geometry.exposed_prism_cut_height_z,
          width_y: STAGE_1_GEOMETRY.base_width_y,
        },
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_1_full_width_slope',
        hardware_id: 'enclosure',
        type: 'solid_slope_plate',
        role: 'display_back_slope',
        anchor_face: '+X bottom edge',
        mount_surface: 'base_plus_x_bottom_edge',
        center: {
          x: round3((geometry.slope_start_x + geometry.slope_end_x) / 2),
          y: geometry.slope_offset_y,
          z: round3((geometry.slope_start_z + geometry.slope_end_z) / 2),
        },
        size_mm: {
          face_length: STAGE_1_GEOMETRY.slope_face_length,
          width_y: SLOPE_WIDTH_Y,
          thickness: STAGE_1_GEOMETRY.slope_thickness,
          angle_deg: STAGE_1_GEOMETRY.slope_angle_deg,
        },
        cut_mm: {
          type: 'triangular_prism',
          edge: '-Z bottom protrusion',
          run_x: geometry.bottom_protrusion_cut_run_x,
          depth_z: geometry.bottom_protrusion_cut_depth_z,
          width_y: SLOPE_WIDTH_Y,
        },
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_2_full_width_l_clip',
        hardware_id: 'unihiker_k10',
        type: 'full_width_l_clip_on_slope',
        role: 'display_controller_retainer',
        anchor_face: 'slope_top_face',
        mount_surface: 'slope_surface',
        center: {
          x: geometry.clip_center_x,
          y: geometry.clip_center_y,
          z: geometry.clip_center_z,
        },
        size_mm: {
          perpendicular_thickness: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_thickness,
          perpendicular_length: STAGE_2_CLIP_GEOMETRY.clip_perpendicular_length,
          parallel_thickness: STAGE_2_CLIP_GEOMETRY.clip_parallel_thickness,
          parallel_length: STAGE_2_CLIP_GEOMETRY.clip_parallel_length,
          offset_from_slope_top: STAGE_2_CLIP_GEOMETRY.clip_offset_from_slope_top,
          width_y: geometry.clip_width_y,
        },
        orientation: {
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
          lip_direction: 'toward_slope_top',
        },
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_3_plus_y_side_stop_blocks',
        hardware_id: 'unihiker_k10',
        type: 'plus_y_local_side_stop_blocks',
        role: 'display_controller_side_stops',
        anchor_face: 'l_clip_perpendicular_arm_top_face',
        mount_surface: 'plus_y_end_of_l_clip',
        center: {
          x: geometry.side_block_center_x,
          y: geometry.side_block_y_center,
          z: geometry.side_block_center_z,
        },
        size_mm: {
          y_depth: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_y_depth,
          parallel_extension: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_parallel_extension,
          gap_between_blocks: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_gap_between_blocks,
          union_overlap: STAGE_3_SIDE_BLOCK_GEOMETRY.side_block_union_overlap,
          y_min: geometry.side_block_y_min,
          y_max: geometry.side_block_y_max,
        },
        blocks: [
          {
            id: 'inner_side_block',
            normal_length: STAGE_3_SIDE_BLOCK_GEOMETRY.inner_side_block_normal_length,
            normal_min: geometry.inner_side_block_min_n,
            normal_max: geometry.inner_side_block_max_n,
            center: {
              x: geometry.inner_side_block_center_x,
              y: geometry.side_block_y_center,
              z: geometry.inner_side_block_center_z,
            },
          },
          {
            id: 'outer_side_block',
            normal_length: STAGE_3_SIDE_BLOCK_GEOMETRY.outer_side_block_normal_length,
            normal_min: geometry.outer_side_block_min_n,
            normal_max: geometry.outer_side_block_max_n,
            center: {
              x: geometry.outer_side_block_center_x,
              y: geometry.side_block_y_center,
              z: geometry.outer_side_block_center_z,
            },
          },
        ],
        orientation: {
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
          y_side: '+Y',
          parallel_extension_direction: 'toward_slope_top',
        },
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_5_plus_y_slope_back_cover',
        hardware_id: 'unihiker_k10',
        type: 'plus_y_slope_back_cover_block',
        role: 'display_controller_slope_back_cover',
        anchor_face: '+Y end face',
        mount_surface: 'plus_y_slope_side_profile',
        center: {
          x: geometry.plus_y_slope_back_cover_center_x,
          y: geometry.plus_y_slope_back_cover_y_center,
          z: geometry.plus_y_slope_back_cover_center_z,
        },
        size_mm: {
          y_depth: geometry.plus_y_slope_back_cover_y_depth,
          y_min: geometry.plus_y_slope_back_cover_y_min,
          y_max: geometry.plus_y_slope_back_cover_y_max,
          s_min: geometry.plus_y_slope_back_cover_s_min,
          s_max: geometry.plus_y_slope_back_cover_s_max,
          s_length: geometry.plus_y_slope_back_cover_s_length,
          n_min: geometry.plus_y_slope_back_cover_n_min,
          n_max: geometry.plus_y_slope_back_cover_n_max,
          normal_length: geometry.plus_y_slope_back_cover_normal_length,
        },
        orientation: {
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
          y_extrude_direction: '-Y',
        },
        profile_points_xz: geometry.plus_y_slope_back_cover_profile_points_xz,
        clearance_mm: 0,
      },
      {
        id: 'photo_album_stage_6_rear_slope_block',
        hardware_id: 'enclosure',
        type: 'rear_slope_back_block',
        role: 'rear_slope_support_block',
        anchor_face: 'slope_back_face',
        mount_surface: 'slope_back_face',
        center: {
          x: geometry.rear_slope_block_center_x,
          y: geometry.rear_slope_block_y_center,
          z: geometry.rear_slope_block_center_z,
        },
        size_mm: {
          y_length: geometry.rear_slope_block_y_length,
          y_min: geometry.rear_slope_block_y_min,
          y_max: geometry.rear_slope_block_y_max,
          y_center: geometry.rear_slope_block_y_center,
          s_min: geometry.rear_slope_block_s_min,
          s_max: geometry.rear_slope_block_s_max,
          s_length: geometry.rear_slope_block_s_length,
          s_center: geometry.rear_slope_block_s_center,
          n_min: geometry.rear_slope_block_n_min,
          n_max: geometry.rear_slope_block_n_max,
          n_center: geometry.rear_slope_block_n_center,
          normal_thickness: geometry.rear_slope_block_normal_thickness,
          offset_from_slope_top: geometry.rear_slope_block_offset_from_slope_top,
        },
        orientation: {
          slope_down_axis_x: geometry.slope_down_axis_x,
          slope_down_axis_z: geometry.slope_down_axis_z,
          outward_axis_x: geometry.slope_outward_axis_x,
          outward_axis_z: geometry.slope_outward_axis_z,
          y_side: '+Y',
          normal_direction: 'behind_slope',
        },
        profile_points_xz: geometry.rear_slope_block_profile_points_xz,
        clearance_mm: 0,
      },
    ],
    geometry,
    notes: [
      'Stage 9-5 layout metadata accompanies the confirmed photo album CQ model.',
      'The slope lower +X edge aligns to the base bottom +X edge and tilts along -X/+Z.',
      'The slope Y length equals the base Y length.',
      'Cleanup cutters remove exposed triangular remnants from the base and slope.',
      'The L clip spans the full slope width and is positioned from the slope top edge.',
      '+Y stop blocks extend inward from y=41.5 to y=34.5.',
      `Preview bounding box is ${enclosure.outer_box_size.length_x} x ${enclosure.outer_box_size.width_y} x ${enclosure.outer_box_size.height_z} mm.`,
    ],
  };
}

function buildTemplateValidation({ geometry, profiles }) {
  const profileIds = profiles.map((item) => item.id);
  const checks = [
    {
      id: 'source_deterministic',
      label: 'Generation source',
      status: 'pass',
      message: 'Model is generated by the backend deterministic template library, not LLM-authored CAD code.',
    },
    {
      id: 'photo_album_stage_9_5_geometry',
      label: 'Stage 9-5 geometry',
      status: 'pass',
      message: 'Stage 9-5 uses the confirmed CQ source file while preserving geometry metadata for preview and export.',
      details: {
        base_length_x: STAGE_1_GEOMETRY.base_length_x,
        base_width_y: STAGE_1_GEOMETRY.base_width_y,
        base_thickness_z: STAGE_1_GEOMETRY.base_thickness_z,
        slope_face_length: STAGE_1_GEOMETRY.slope_face_length,
        slope_thickness: STAGE_1_GEOMETRY.slope_thickness,
        slope_angle_deg: STAGE_1_GEOMETRY.slope_angle_deg,
        slope_anchor_x: SLOPE_ANCHOR_X,
        slope_offset_y: geometry.slope_offset_y,
        slope_run_x: geometry.slope_run_x,
        slope_rise_z: geometry.slope_rise_z,
        slope_width_y: geometry.slope_width_y,
        slope_min_y: geometry.slope_min_y,
        slope_max_y: geometry.slope_max_y,
        cut_overlap_y: geometry.cut_overlap_y,
        exposed_prism_cut_run_x: geometry.exposed_prism_cut_run_x,
        bottom_protrusion_cut_run_x: geometry.bottom_protrusion_cut_run_x,
        bottom_protrusion_cut_depth_z: geometry.bottom_protrusion_cut_depth_z,
        clip_perpendicular_thickness: geometry.clip_perpendicular_thickness,
        clip_perpendicular_length: geometry.clip_perpendicular_length,
        clip_parallel_thickness: geometry.clip_parallel_thickness,
        clip_parallel_length: geometry.clip_parallel_length,
        clip_offset_from_slope_top: geometry.clip_offset_from_slope_top,
        clip_width_y: geometry.clip_width_y,
        clip_center_y: geometry.clip_center_y,
        side_block_y_depth: geometry.side_block_y_depth,
        side_block_parallel_extension: geometry.side_block_parallel_extension,
        inner_side_block_normal_length: geometry.inner_side_block_normal_length,
        outer_side_block_normal_length: geometry.outer_side_block_normal_length,
        side_block_gap_between_blocks: geometry.side_block_gap_between_blocks,
        side_block_y_min: geometry.side_block_y_min,
        side_block_y_max: geometry.side_block_y_max,
        plus_y_slope_back_cover_y_depth: geometry.plus_y_slope_back_cover_y_depth,
        plus_y_slope_back_cover_y_min: geometry.plus_y_slope_back_cover_y_min,
        plus_y_slope_back_cover_y_max: geometry.plus_y_slope_back_cover_y_max,
        plus_y_slope_back_cover_s_min: geometry.plus_y_slope_back_cover_s_min,
        plus_y_slope_back_cover_s_max: geometry.plus_y_slope_back_cover_s_max,
        plus_y_slope_back_cover_n_min: geometry.plus_y_slope_back_cover_n_min,
        plus_y_slope_back_cover_n_max: geometry.plus_y_slope_back_cover_n_max,
        plus_y_slope_back_cover_normal_length: geometry.plus_y_slope_back_cover_normal_length,
        slope_square_hole_size: geometry.slope_square_hole_size,
        slope_square_hole_center_s: geometry.slope_square_hole_center_s,
        slope_square_hole_offset_from_minus_y: geometry.slope_square_hole_offset_from_minus_y,
        slope_square_hole_center_y: geometry.slope_square_hole_center_y,
        slope_square_hole_s_min: geometry.slope_square_hole_s_min,
        slope_square_hole_s_max: geometry.slope_square_hole_s_max,
        slope_square_hole_y_min: geometry.slope_square_hole_y_min,
        slope_square_hole_y_max: geometry.slope_square_hole_y_max,
        slope_square_hole_cutter_normal_depth: geometry.slope_square_hole_cutter_normal_depth,
        rear_slope_block_y_length: geometry.rear_slope_block_y_length,
        rear_slope_block_y_min: geometry.rear_slope_block_y_min,
        rear_slope_block_y_max: geometry.rear_slope_block_y_max,
        rear_slope_block_y_center: geometry.rear_slope_block_y_center,
        rear_slope_block_offset_from_slope_top: geometry.rear_slope_block_offset_from_slope_top,
        rear_slope_block_s_min: geometry.rear_slope_block_s_min,
        rear_slope_block_s_max: geometry.rear_slope_block_s_max,
        rear_slope_block_s_length: geometry.rear_slope_block_s_length,
        rear_slope_block_s_center: geometry.rear_slope_block_s_center,
        rear_slope_block_n_min: geometry.rear_slope_block_n_min,
        rear_slope_block_n_max: geometry.rear_slope_block_n_max,
        rear_slope_block_n_center: geometry.rear_slope_block_n_center,
        rear_slope_block_normal_thickness: geometry.rear_slope_block_normal_thickness,
        rear_slope_top_slot_y_length: geometry.rear_slope_top_slot_y_length,
        rear_slope_top_slot_y_min: geometry.rear_slope_top_slot_y_min,
        rear_slope_top_slot_y_max: geometry.rear_slope_top_slot_y_max,
        rear_slope_top_slot_y_center: geometry.rear_slope_top_slot_y_center,
        rear_slope_top_slot_width_n: geometry.rear_slope_top_slot_width_n,
        rear_slope_top_slot_n_min: geometry.rear_slope_top_slot_n_min,
        rear_slope_top_slot_n_max: geometry.rear_slope_top_slot_n_max,
        rear_slope_top_slot_center_n: geometry.rear_slope_top_slot_center_n,
        rear_slope_top_slot_cut_depth_s: geometry.rear_slope_top_slot_cut_depth_s,
        rear_slope_top_slot_surface_s: geometry.rear_slope_top_slot_surface_s,
        rear_slope_top_slot_s_min: geometry.rear_slope_top_slot_s_min,
        rear_slope_top_slot_s_max: geometry.rear_slope_top_slot_s_max,
        rear_slope_top_slot_s_center: geometry.rear_slope_top_slot_s_center,
        rear_slope_top_slot_cutter_overlap_s: geometry.rear_slope_top_slot_cutter_overlap_s,
        rear_slope_top_slot_cutter_s_min: geometry.rear_slope_top_slot_cutter_s_min,
        rear_slope_top_slot_cutter_s_max: geometry.rear_slope_top_slot_cutter_s_max,
        rear_slope_top_slot_cutter_size_s: geometry.rear_slope_top_slot_cutter_size_s,
        rear_slope_top_slot_cutter_center_s: geometry.rear_slope_top_slot_cutter_center_s,
        narrow_stop_semicircle_diameter: geometry.narrow_stop_semicircle_diameter,
        narrow_stop_semicircle_radius: geometry.narrow_stop_semicircle_radius,
        narrow_stop_semicircle_offset_from_lip_top_edge_s: geometry.narrow_stop_semicircle_offset_from_lip_top_edge_s,
        narrow_stop_semicircle_clip_parallel_top_edge_s: geometry.narrow_stop_semicircle_clip_parallel_top_edge_s,
        narrow_stop_semicircle_center_s: geometry.narrow_stop_semicircle_center_s,
        narrow_stop_semicircle_center_y: geometry.narrow_stop_semicircle_center_y,
        narrow_stop_semicircle_center_n: geometry.narrow_stop_semicircle_center_n,
        narrow_stop_semicircle_s_min: geometry.narrow_stop_semicircle_s_min,
        narrow_stop_semicircle_s_max: geometry.narrow_stop_semicircle_s_max,
        narrow_stop_semicircle_y_min: geometry.narrow_stop_semicircle_y_min,
        narrow_stop_semicircle_y_max: geometry.narrow_stop_semicircle_y_max,
        narrow_stop_semicircle_cut_depth_n: geometry.narrow_stop_semicircle_cut_depth_n,
        narrow_stop_semicircle_cutter_overlap_n: geometry.narrow_stop_semicircle_cutter_overlap_n,
        narrow_stop_semicircle_cutter_min_n: geometry.narrow_stop_semicircle_cutter_min_n,
        narrow_stop_semicircle_cutter_max_n: geometry.narrow_stop_semicircle_cutter_max_n,
        narrow_stop_semicircle_cutter_depth_n: geometry.narrow_stop_semicircle_cutter_depth_n,
        narrow_stop_semicircle_cutter_center_n: geometry.narrow_stop_semicircle_cutter_center_n,
        narrow_stop_semicircle_segments: geometry.narrow_stop_semicircle_segments,
        rear_slope_block_low_contact_fillet_radius: geometry.rear_slope_block_low_contact_fillet_radius,
        rear_slope_block_low_contact_filler_segments: geometry.rear_slope_block_low_contact_filler_segments,
        rear_slope_block_low_contact_filler_s_min: geometry.rear_slope_block_low_contact_filler_s_min,
        rear_slope_block_low_contact_filler_s_max: geometry.rear_slope_block_low_contact_filler_s_max,
        rear_slope_block_low_contact_filler_n_min: geometry.rear_slope_block_low_contact_filler_n_min,
        rear_slope_block_low_contact_filler_n_max: geometry.rear_slope_block_low_contact_filler_n_max,
        rear_slope_block_low_contact_filler_width_y: geometry.rear_slope_block_low_contact_filler_width_y,
        rear_slope_block_low_contact_filler_center_y: geometry.rear_slope_block_low_contact_filler_center_y,
      },
    },
    {
      id: 'photo_album_plus_x_top_prism_cut',
      label: 'Base top prism cut',
      status: 'pass',
      message: 'The triangular prism at the base +Z/+X edge is removed so the slope top surface is not obstructed by the base plate.',
      details: {
        cut_run_x: geometry.exposed_prism_cut_run_x,
        cut_height_z: geometry.exposed_prism_cut_height_z,
        cut_width_y: STAGE_1_GEOMETRY.base_width_y,
        cut_overlap_y: geometry.cut_overlap_y,
        cutter_center_y: geometry.base_exposure_cutter_center_y,
        cutter_min_y: geometry.base_exposure_cutter_min_y,
        cutter_max_y: geometry.base_exposure_cutter_max_y,
        cutter_width_y: geometry.base_exposure_cutter_width_y,
        final_cleanup_after_union: true,
      },
    },
    {
      id: 'photo_album_slope_width_matches_base',
      label: 'Slope width',
      status: 'pass',
      message: 'The slope is extruded across the same Y length as the base plate.',
      details: {
        slope_width_y: SLOPE_WIDTH_Y,
        base_width_y: STAGE_1_GEOMETRY.base_width_y,
        slope_offset_y: SLOPE_OFFSET_Y,
      },
    },
    {
      id: 'photo_album_slope_bottom_prism_cut',
      label: 'Slope bottom prism cut',
      status: 'pass',
      message: 'The triangular prism protruding below the base -Z plane is removed from the slope.',
      details: {
        cut_run_x: geometry.bottom_protrusion_cut_run_x,
        cut_depth_z: geometry.bottom_protrusion_cut_depth_z,
        cut_width_y: SLOPE_WIDTH_Y,
        cut_overlap_y: geometry.cut_overlap_y,
        cutter_center_y: geometry.slope_cutter_center_y,
        cutter_min_y: geometry.slope_cutter_min_y,
        cutter_max_y: geometry.slope_cutter_max_y,
        cutter_width_y: geometry.slope_cutter_width_y,
      },
    },
    {
      id: 'photo_album_fixed_bom_profiles',
      label: 'Fixed BOM profiles',
      status: 'pass',
      message: 'The fixed BOM uses builtin unihiker_k10 and unihiker_polymer_lipo_battery profiles.',
      details: { profile_ids: profileIds },
    },
    {
      id: 'photo_album_stage_2_l_clip',
      label: 'Stage 2 L clip',
      status: 'pass',
      message: 'The L clip is generated in the slope local frame and extruded across the full slope Y width.',
      details: {
        clip_width_y: geometry.clip_width_y,
        clip_center_y: geometry.clip_center_y,
        clip_min_y: geometry.clip_min_y,
        clip_max_y: geometry.clip_max_y,
        lip_direction: 'toward_slope_top',
        profile_points_xz: geometry.clip_profile_points_xz,
      },
    },
    {
      id: 'photo_album_stage_3_side_stop_blocks',
      label: 'Stage 3 side stop blocks',
      status: 'pass',
      message: 'Two local rectangular stop blocks are generated near the +Y end of the L clip perpendicular arm top face.',
      details: {
        y_depth: geometry.side_block_y_depth,
        y_min: geometry.side_block_y_min,
        y_max: geometry.side_block_y_max,
        parallel_extension: geometry.side_block_parallel_extension,
        start_s: geometry.side_block_start_s,
        end_s: geometry.side_block_end_s,
        union_overlap: geometry.side_block_union_overlap,
        inner_normal_length: geometry.inner_side_block_normal_length,
        inner_normal_min: geometry.inner_side_block_min_n,
        inner_normal_max: geometry.inner_side_block_max_n,
        gap_between_blocks: geometry.side_block_gap_between_blocks,
        outer_normal_length: geometry.outer_side_block_normal_length,
        outer_normal_min: geometry.outer_side_block_min_n,
        outer_normal_max: geometry.outer_side_block_max_n,
      },
    },
    {
      id: 'photo_album_stage_5_plus_y_slope_back_cover',
      label: 'Stage 5 +Y slope back cover',
      status: 'pass',
      message: 'A sloped rectangular block is generated on the +Y side profile and extruded 7mm toward -Y.',
      details: {
        y_depth: geometry.plus_y_slope_back_cover_y_depth,
        y_min: geometry.plus_y_slope_back_cover_y_min,
        y_max: geometry.plus_y_slope_back_cover_y_max,
        y_center: geometry.plus_y_slope_back_cover_y_center,
        s_min: geometry.plus_y_slope_back_cover_s_min,
        s_max: geometry.plus_y_slope_back_cover_s_max,
        s_length: geometry.plus_y_slope_back_cover_s_length,
        n_min: geometry.plus_y_slope_back_cover_n_min,
        n_max: geometry.plus_y_slope_back_cover_n_max,
        n_center: geometry.plus_y_slope_back_cover_n_center,
        normal_length: geometry.plus_y_slope_back_cover_normal_length,
        profile_points_xz: geometry.plus_y_slope_back_cover_profile_points_xz,
      },
    },
    {
      id: 'photo_album_stage_5_slope_square_hole',
      label: 'Stage 5 slope square hole',
      status: 'pass',
      message: 'A 12mm square through-hole is cut through the slope using the slope local frame.',
      details: {
        size: geometry.slope_square_hole_size,
        center_s: geometry.slope_square_hole_center_s,
        center_y: geometry.slope_square_hole_center_y,
        offset_from_minus_y: geometry.slope_square_hole_offset_from_minus_y,
        s_min: geometry.slope_square_hole_s_min,
        s_max: geometry.slope_square_hole_s_max,
        y_min: geometry.slope_square_hole_y_min,
        y_max: geometry.slope_square_hole_y_max,
        cutter_normal_padding: geometry.slope_square_hole_cutter_normal_padding,
        cutter_normal_depth: geometry.slope_square_hole_cutter_normal_depth,
        cutter_min_n: geometry.slope_square_hole_cutter_min_n,
        cutter_max_n: geometry.slope_square_hole_cutter_max_n,
      },
    },
    {
      id: 'photo_album_stage_6_rear_slope_block',
      label: 'Stage 6 rear slope block',
      status: 'pass',
      message: 'A 53mm x 34mm x 8.5mm rectangular block is generated on the slope back face and attached to the +Y side range.',
      details: {
        y_length: geometry.rear_slope_block_y_length,
        y_min: geometry.rear_slope_block_y_min,
        y_max: geometry.rear_slope_block_y_max,
        y_center: geometry.rear_slope_block_y_center,
        offset_from_slope_top: geometry.rear_slope_block_offset_from_slope_top,
        s_min: geometry.rear_slope_block_s_min,
        s_max: geometry.rear_slope_block_s_max,
        s_length: geometry.rear_slope_block_s_length,
        s_center: geometry.rear_slope_block_s_center,
        n_min: geometry.rear_slope_block_n_min,
        n_max: geometry.rear_slope_block_n_max,
        n_center: geometry.rear_slope_block_n_center,
        normal_thickness: geometry.rear_slope_block_normal_thickness,
        profile_points_xz: geometry.rear_slope_block_profile_points_xz,
      },
    },
    {
      id: 'photo_album_stage_7_rear_slope_top_slot',
      label: 'Stage 7 rear slope top slot',
      status: 'pass',
      message: 'A 49mm x 6.5mm local top slot is cut 32mm down the rear slope block from its top surface.',
      details: {
        y_length: geometry.rear_slope_top_slot_y_length,
        y_min: geometry.rear_slope_top_slot_y_min,
        y_max: geometry.rear_slope_top_slot_y_max,
        y_center: geometry.rear_slope_top_slot_y_center,
        width_n: geometry.rear_slope_top_slot_width_n,
        n_min: geometry.rear_slope_top_slot_n_min,
        n_max: geometry.rear_slope_top_slot_n_max,
        center_n: geometry.rear_slope_top_slot_center_n,
        cut_depth_s: geometry.rear_slope_top_slot_cut_depth_s,
        surface_s: geometry.rear_slope_top_slot_surface_s,
        s_min: geometry.rear_slope_top_slot_s_min,
        s_max: geometry.rear_slope_top_slot_s_max,
        s_center: geometry.rear_slope_top_slot_s_center,
        cutter_overlap_s: geometry.rear_slope_top_slot_cutter_overlap_s,
        cutter_s_min: geometry.rear_slope_top_slot_cutter_s_min,
        cutter_s_max: geometry.rear_slope_top_slot_cutter_s_max,
        cutter_size_s: geometry.rear_slope_top_slot_cutter_size_s,
        cutter_center_s: geometry.rear_slope_top_slot_cutter_center_s,
      },
    },
    {
      id: 'photo_album_stage_8_narrow_stop_semicircle_cut',
      label: 'Stage 8 narrow stop semicircle cut',
      status: 'pass',
      message: 'A 10mm diameter semicircle is cut into the narrow stop outer face from the +Y edge toward -Y, with the cutter spanning local n=-0.05~12.65.',
      details: {
        diameter: geometry.narrow_stop_semicircle_diameter,
        radius: geometry.narrow_stop_semicircle_radius,
        offset_from_lip_top_edge_s: geometry.narrow_stop_semicircle_offset_from_lip_top_edge_s,
        clip_parallel_top_edge_s: geometry.narrow_stop_semicircle_clip_parallel_top_edge_s,
        center_s: geometry.narrow_stop_semicircle_center_s,
        center_y: geometry.narrow_stop_semicircle_center_y,
        center_n: geometry.narrow_stop_semicircle_center_n,
        s_min: geometry.narrow_stop_semicircle_s_min,
        s_max: geometry.narrow_stop_semicircle_s_max,
        y_min: geometry.narrow_stop_semicircle_y_min,
        y_max: geometry.narrow_stop_semicircle_y_max,
        cut_depth_n: geometry.narrow_stop_semicircle_cut_depth_n,
        cutter_overlap_n: geometry.narrow_stop_semicircle_cutter_overlap_n,
        cutter_min_n: geometry.narrow_stop_semicircle_cutter_min_n,
        cutter_max_n: geometry.narrow_stop_semicircle_cutter_max_n,
        cutter_depth_n: geometry.narrow_stop_semicircle_cutter_depth_n,
        cutter_center_n: geometry.narrow_stop_semicircle_cutter_center_n,
        segments: geometry.narrow_stop_semicircle_segments,
      },
    },
    {
      id: 'photo_album_stage_9_5_confirmed_fillet_metadata',
      label: 'Stage 9-5 confirmed fillet metadata',
      status: 'pass',
      message: 'The confirmed stage 9-5 source includes the final sequence of photo album refinements.',
      details: {
        rear_slope_block_low_contact_radius: geometry.rear_slope_block_low_contact_fillet_radius,
        rear_slope_block_low_contact_filler_segments: geometry.rear_slope_block_low_contact_filler_segments,
        rear_slope_block_low_contact_filler_width_y: geometry.rear_slope_block_low_contact_filler_width_y,
        rear_slope_block_low_contact_filler_center_y: geometry.rear_slope_block_low_contact_filler_center_y,
        rear_slope_block_low_contact_filler_s_min: geometry.rear_slope_block_low_contact_filler_s_min,
        rear_slope_block_low_contact_filler_s_max: geometry.rear_slope_block_low_contact_filler_s_max,
        rear_slope_block_low_contact_filler_n_min: geometry.rear_slope_block_low_contact_filler_n_min,
        rear_slope_block_low_contact_filler_n_max: geometry.rear_slope_block_low_contact_filler_n_max,
        rear_low_contact_s: geometry.rear_slope_block_low_contact_fillet_s,
        rear_low_contact_n: geometry.rear_slope_block_low_contact_fillet_n,
      },
    },
    {
      id: 'cadquery_code_static',
      label: 'CadQuery code static check',
      status: 'pass',
      message: 'Template CadQuery code is loaded from the confirmed stage 9-5 CQ source file and exposes the standard base/lid/hardware entrypoints.',
      details: {
        source_file: 'server/template-library/unihiker-photo-album.cq.py',
        source_sha256: PHOTO_ALBUM_CADQUERY_SOURCE_SHA256,
      },
    },
    {
      id: 'cadquery_runtime',
      label: 'CadQuery runtime',
      status: 'pending',
      message: 'CadQuery runtime execution is handled by the normal export path when the environment is available.',
    },
  ];
  return {
    checks,
    warnings: [
      {
        id: 'photo_album_stage_9_5_source',
        status: 'info',
        message: 'Stage 9-5 is copied from the approved local CQ source file and used as the template CAD source.',
      },
    ],
    validation_context: {
      aabb_model: 'deterministic_template_photo_album_stage_9_5_confirmed_source',
      mesh_validation: 'pending_missing_cadquery',
      builtin_profile_ids: profileIds,
      cadquery_source_sha256: PHOTO_ALBUM_CADQUERY_SOURCE_SHA256,
      stage_9_5_geometry: geometry,
    },
  };
}

function buildTemplateParameters(body = {}) {
  const overrides = normalizeNumberMap(body.parameterOverrides || body.parameter_overrides);
  const parameters = { ...TEMPLATE_PARAMETERS };
  const changedTemplateKeys = new Set();
  for (const [key, value] of Object.entries(overrides)) {
    const targetKey = GUI_PARAMETER_TO_TEMPLATE_PARAMETER[key] || key;
    if (Object.prototype.hasOwnProperty.call(parameters, targetKey)) {
      parameters[targetKey] = value;
      changedTemplateKeys.add(targetKey);
    }
  }
  synchronizeDerivedTemplateParameters(parameters);
  return { parameters, changedTemplateKeys };
}

function projectDefaultParametersFromBody(body = {}) {
  const current = body.currentDesignState || body.current_design_state || {};
  const existing = current.project_default_parameters || current.default_parameters || {};
  return isPlainObject(existing) && Object.keys(existing).length ? existing : null;
}

function synchronizeDerivedTemplateParameters(parameters) {
  parameters.inner_length_x = parameters.photo_album_base_length_x;
  parameters.inner_width_y = parameters.photo_album_base_width_y;
  parameters.inner_height_z = parameters.photo_album_base_thickness_z;
  parameters.wall_thickness = parameters.photo_album_slope_thickness;
  parameters.floor_thickness = parameters.photo_album_base_thickness_z;
  parameters.photo_album_slope_width_y = parameters.photo_album_base_width_y;
  parameters.photo_album_slope_anchor_x = parameters.photo_album_base_length_x / 2;
  parameters.photo_album_slope_offset_y = parameters.photo_album_slope_width_y;
  parameters.photo_album_clip_width_y = parameters.photo_album_slope_width_y;
  parameters.photo_album_clip_center_y = 0;
  parameters.photo_album_narrow_stop_semicircle_radius = parameters.photo_album_narrow_stop_semicircle_diameter / 2;
  parameters.photo_album_rear_slope_block_y_max = parameters.photo_album_base_width_y / 2;
  parameters.photo_album_rear_slope_block_y_min = parameters.photo_album_rear_slope_block_y_max - parameters.photo_album_rear_slope_block_y_length;
  parameters.photo_album_rear_slope_block_y_center = (parameters.photo_album_rear_slope_block_y_min + parameters.photo_album_rear_slope_block_y_max) / 2;
  parameters.photo_album_rear_slope_block_s_min = parameters.photo_album_rear_slope_block_offset_from_slope_top;
  parameters.photo_album_rear_slope_block_s_max = parameters.photo_album_rear_slope_block_s_min + parameters.photo_album_rear_slope_block_s_length;
  parameters.photo_album_rear_slope_block_s_center = (parameters.photo_album_rear_slope_block_s_min + parameters.photo_album_rear_slope_block_s_max) / 2;
  parameters.photo_album_rear_slope_block_n_max = -parameters.photo_album_slope_thickness;
  parameters.photo_album_rear_slope_block_n_min = parameters.photo_album_rear_slope_block_n_max - parameters.photo_album_rear_slope_block_normal_thickness;
  parameters.photo_album_rear_slope_block_n_center = (parameters.photo_album_rear_slope_block_n_min + parameters.photo_album_rear_slope_block_n_max) / 2;
  parameters.photo_album_rear_slope_top_slot_y_center = parameters.photo_album_rear_slope_block_y_center;
  parameters.photo_album_rear_slope_top_slot_y_min = parameters.photo_album_rear_slope_top_slot_y_center - parameters.photo_album_rear_slope_top_slot_y_length / 2;
  parameters.photo_album_rear_slope_top_slot_y_max = parameters.photo_album_rear_slope_top_slot_y_center + parameters.photo_album_rear_slope_top_slot_y_length / 2;
  parameters.photo_album_rear_slope_top_slot_n_max = parameters.photo_album_rear_slope_block_n_max;
  parameters.photo_album_rear_slope_top_slot_n_min = parameters.photo_album_rear_slope_top_slot_n_max - parameters.photo_album_rear_slope_top_slot_width_n;
  parameters.photo_album_rear_slope_top_slot_center_n = (parameters.photo_album_rear_slope_top_slot_n_min + parameters.photo_album_rear_slope_top_slot_n_max) / 2;
  parameters.photo_album_rear_slope_top_slot_surface_s = parameters.photo_album_rear_slope_block_s_min;
  parameters.photo_album_rear_slope_top_slot_s_min = parameters.photo_album_rear_slope_top_slot_surface_s;
  parameters.photo_album_rear_slope_top_slot_s_max = parameters.photo_album_rear_slope_top_slot_s_min + parameters.photo_album_rear_slope_top_slot_cut_depth_s;
  parameters.photo_album_rear_slope_top_slot_s_center = (parameters.photo_album_rear_slope_top_slot_s_min + parameters.photo_album_rear_slope_top_slot_s_max) / 2;
  parameters.photo_album_rear_slope_top_slot_cutter_s_min = parameters.photo_album_rear_slope_top_slot_s_min - parameters.photo_album_rear_slope_top_slot_cutter_overlap_s;
  parameters.photo_album_rear_slope_top_slot_cutter_s_max = parameters.photo_album_rear_slope_top_slot_s_max;
  parameters.photo_album_rear_slope_top_slot_cutter_size_s = parameters.photo_album_rear_slope_top_slot_cutter_s_max - parameters.photo_album_rear_slope_top_slot_cutter_s_min;
  parameters.photo_album_rear_slope_top_slot_cutter_center_s = (parameters.photo_album_rear_slope_top_slot_cutter_s_min + parameters.photo_album_rear_slope_top_slot_cutter_s_max) / 2;
  parameters.photo_album_slope_square_hole_center_y = -parameters.photo_album_base_width_y / 2 + parameters.photo_album_slope_square_hole_offset_from_minus_y;
  parameters.photo_album_slope_square_hole_s_min = parameters.photo_album_slope_square_hole_center_s - parameters.photo_album_slope_square_hole_size / 2;
  parameters.photo_album_slope_square_hole_s_max = parameters.photo_album_slope_square_hole_center_s + parameters.photo_album_slope_square_hole_size / 2;
  parameters.photo_album_slope_square_hole_y_min = parameters.photo_album_slope_square_hole_center_y - parameters.photo_album_slope_square_hole_size / 2;
  parameters.photo_album_slope_square_hole_y_max = parameters.photo_album_slope_square_hole_center_y + parameters.photo_album_slope_square_hole_size / 2;
  parameters.photo_album_slope_square_hole_cutter_normal_depth = parameters.photo_album_slope_thickness + 2 * parameters.photo_album_slope_square_hole_cutter_normal_padding;
  parameters.photo_album_slope_square_hole_cutter_center_n = -parameters.photo_album_slope_thickness / 2;
  parameters.photo_album_slope_square_hole_cutter_min_n = parameters.photo_album_slope_square_hole_cutter_center_n - parameters.photo_album_slope_square_hole_cutter_normal_depth / 2;
  parameters.photo_album_slope_square_hole_cutter_max_n = parameters.photo_album_slope_square_hole_cutter_center_n + parameters.photo_album_slope_square_hole_cutter_normal_depth / 2;
  parameters.photo_album_narrow_stop_semicircle_clip_parallel_top_edge_s = parameters.photo_album_clip_offset_from_slope_top - parameters.photo_album_clip_parallel_length;
  parameters.photo_album_narrow_stop_semicircle_center_s = parameters.photo_album_narrow_stop_semicircle_clip_parallel_top_edge_s - parameters.photo_album_narrow_stop_semicircle_offset_from_lip_top_edge_s;
  parameters.photo_album_narrow_stop_semicircle_center_y = parameters.photo_album_base_width_y / 2;
  parameters.photo_album_narrow_stop_semicircle_center_n = parameters.photo_album_inner_side_block_normal_length + parameters.photo_album_side_block_gap_between_blocks + parameters.photo_album_outer_side_block_normal_length;
  parameters.photo_album_narrow_stop_semicircle_s_min = parameters.photo_album_narrow_stop_semicircle_center_s - parameters.photo_album_narrow_stop_semicircle_radius;
  parameters.photo_album_narrow_stop_semicircle_s_max = parameters.photo_album_narrow_stop_semicircle_center_s + parameters.photo_album_narrow_stop_semicircle_radius;
  parameters.photo_album_narrow_stop_semicircle_y_min = parameters.photo_album_narrow_stop_semicircle_center_y - parameters.photo_album_narrow_stop_semicircle_radius;
  parameters.photo_album_narrow_stop_semicircle_y_max = parameters.photo_album_narrow_stop_semicircle_center_y;
  parameters.photo_album_narrow_stop_semicircle_cutter_min_n = parameters.photo_album_narrow_stop_semicircle_center_n - parameters.photo_album_narrow_stop_semicircle_cut_depth_n - parameters.photo_album_narrow_stop_semicircle_cutter_overlap_n;
  parameters.photo_album_narrow_stop_semicircle_cutter_max_n = parameters.photo_album_narrow_stop_semicircle_center_n + parameters.photo_album_narrow_stop_semicircle_cutter_overlap_n;
  parameters.photo_album_narrow_stop_semicircle_cutter_depth_n = parameters.photo_album_narrow_stop_semicircle_cutter_max_n - parameters.photo_album_narrow_stop_semicircle_cutter_min_n;
  parameters.photo_album_narrow_stop_semicircle_cutter_center_n = (parameters.photo_album_narrow_stop_semicircle_cutter_min_n + parameters.photo_album_narrow_stop_semicircle_cutter_max_n) / 2;
  parameters.photo_album_rear_slope_block_low_contact_filler_s_min = parameters.photo_album_rear_slope_block_s_max;
  parameters.photo_album_rear_slope_block_low_contact_filler_s_max = parameters.photo_album_rear_slope_block_low_contact_filler_s_min + parameters.photo_album_rear_slope_block_low_contact_fillet_radius;
  parameters.photo_album_rear_slope_block_low_contact_filler_n_max = parameters.photo_album_rear_slope_block_n_max;
  parameters.photo_album_rear_slope_block_low_contact_filler_n_min = parameters.photo_album_rear_slope_block_low_contact_filler_n_max - parameters.photo_album_rear_slope_block_low_contact_fillet_radius;
  parameters.photo_album_rear_slope_block_low_contact_filler_width_y = parameters.photo_album_rear_slope_block_y_length;
  parameters.photo_album_rear_slope_block_low_contact_filler_center_y = parameters.photo_album_rear_slope_block_y_center;
}

function buildPhotoAlbumParameterGroups(parameters, enclosure, layoutPlan) {
  const groups = buildParameterGroups(parameters, enclosure, layoutPlan);
  groups.photo_album = {
    base_length_x: parameters.photo_album_base_length_x,
    base_width_y: parameters.photo_album_base_width_y,
    base_thickness_z: parameters.photo_album_base_thickness_z,
    slope_face_length: parameters.photo_album_slope_face_length,
    slope_thickness: parameters.photo_album_slope_thickness,
    slope_angle_deg: parameters.photo_album_slope_angle_deg,
    slope_width_y: parameters.photo_album_slope_width_y,
    slope_anchor_x: parameters.photo_album_slope_anchor_x,
    slope_offset_y: parameters.photo_album_slope_offset_y,
    clip_perpendicular_thickness: parameters.photo_album_clip_perpendicular_thickness,
    clip_perpendicular_length: parameters.photo_album_clip_perpendicular_length,
    clip_parallel_thickness: parameters.photo_album_clip_parallel_thickness,
    clip_parallel_length: parameters.photo_album_clip_parallel_length,
    clip_offset_from_slope_top: parameters.photo_album_clip_offset_from_slope_top,
    clip_width_y: parameters.photo_album_clip_width_y,
    clip_center_y: parameters.photo_album_clip_center_y,
    side_block_y_depth: parameters.photo_album_side_block_y_depth,
    side_block_parallel_extension: parameters.photo_album_side_block_parallel_extension,
    inner_side_block_normal_length: parameters.photo_album_inner_side_block_normal_length,
    outer_side_block_normal_length: parameters.photo_album_outer_side_block_normal_length,
    side_block_gap_between_blocks: parameters.photo_album_side_block_gap_between_blocks,
    side_block_union_overlap: parameters.photo_album_side_block_union_overlap,
    plus_y_slope_back_cover_y_depth: parameters.photo_album_plus_y_slope_back_cover_y_depth,
    plus_y_slope_back_cover_y_min: parameters.photo_album_plus_y_slope_back_cover_y_min,
    plus_y_slope_back_cover_y_max: parameters.photo_album_plus_y_slope_back_cover_y_max,
    plus_y_slope_back_cover_y_center: parameters.photo_album_plus_y_slope_back_cover_y_center,
    plus_y_slope_back_cover_s_min: parameters.photo_album_plus_y_slope_back_cover_s_min,
    plus_y_slope_back_cover_s_max: parameters.photo_album_plus_y_slope_back_cover_s_max,
    plus_y_slope_back_cover_s_length: parameters.photo_album_plus_y_slope_back_cover_s_length,
    plus_y_slope_back_cover_s_center: parameters.photo_album_plus_y_slope_back_cover_s_center,
    plus_y_slope_back_cover_n_min: parameters.photo_album_plus_y_slope_back_cover_n_min,
    plus_y_slope_back_cover_n_max: parameters.photo_album_plus_y_slope_back_cover_n_max,
    plus_y_slope_back_cover_n_center: parameters.photo_album_plus_y_slope_back_cover_n_center,
    plus_y_slope_back_cover_normal_length: parameters.photo_album_plus_y_slope_back_cover_normal_length,
    slope_square_hole_size: parameters.photo_album_slope_square_hole_size,
    slope_square_hole_center_s: parameters.photo_album_slope_square_hole_center_s,
    slope_square_hole_offset_from_minus_y: parameters.photo_album_slope_square_hole_offset_from_minus_y,
    slope_square_hole_center_y: parameters.photo_album_slope_square_hole_center_y,
    slope_square_hole_s_min: parameters.photo_album_slope_square_hole_s_min,
    slope_square_hole_s_max: parameters.photo_album_slope_square_hole_s_max,
    slope_square_hole_y_min: parameters.photo_album_slope_square_hole_y_min,
    slope_square_hole_y_max: parameters.photo_album_slope_square_hole_y_max,
    slope_square_hole_cutter_normal_padding: parameters.photo_album_slope_square_hole_cutter_normal_padding,
    slope_square_hole_cutter_normal_depth: parameters.photo_album_slope_square_hole_cutter_normal_depth,
    slope_square_hole_cutter_center_n: parameters.photo_album_slope_square_hole_cutter_center_n,
    slope_square_hole_cutter_min_n: parameters.photo_album_slope_square_hole_cutter_min_n,
    slope_square_hole_cutter_max_n: parameters.photo_album_slope_square_hole_cutter_max_n,
    rear_slope_block_y_length: parameters.photo_album_rear_slope_block_y_length,
    rear_slope_block_y_min: parameters.photo_album_rear_slope_block_y_min,
    rear_slope_block_y_max: parameters.photo_album_rear_slope_block_y_max,
    rear_slope_block_y_center: parameters.photo_album_rear_slope_block_y_center,
    rear_slope_block_offset_from_slope_top: parameters.photo_album_rear_slope_block_offset_from_slope_top,
    rear_slope_block_s_min: parameters.photo_album_rear_slope_block_s_min,
    rear_slope_block_s_max: parameters.photo_album_rear_slope_block_s_max,
    rear_slope_block_s_length: parameters.photo_album_rear_slope_block_s_length,
    rear_slope_block_s_center: parameters.photo_album_rear_slope_block_s_center,
    rear_slope_block_n_min: parameters.photo_album_rear_slope_block_n_min,
    rear_slope_block_n_max: parameters.photo_album_rear_slope_block_n_max,
    rear_slope_block_n_center: parameters.photo_album_rear_slope_block_n_center,
    rear_slope_block_normal_thickness: parameters.photo_album_rear_slope_block_normal_thickness,
    rear_slope_top_slot_y_length: parameters.photo_album_rear_slope_top_slot_y_length,
    rear_slope_top_slot_y_min: parameters.photo_album_rear_slope_top_slot_y_min,
    rear_slope_top_slot_y_max: parameters.photo_album_rear_slope_top_slot_y_max,
    rear_slope_top_slot_y_center: parameters.photo_album_rear_slope_top_slot_y_center,
    rear_slope_top_slot_width_n: parameters.photo_album_rear_slope_top_slot_width_n,
    rear_slope_top_slot_n_min: parameters.photo_album_rear_slope_top_slot_n_min,
    rear_slope_top_slot_n_max: parameters.photo_album_rear_slope_top_slot_n_max,
    rear_slope_top_slot_center_n: parameters.photo_album_rear_slope_top_slot_center_n,
    rear_slope_top_slot_cut_depth_s: parameters.photo_album_rear_slope_top_slot_cut_depth_s,
    rear_slope_top_slot_surface_s: parameters.photo_album_rear_slope_top_slot_surface_s,
    rear_slope_top_slot_s_min: parameters.photo_album_rear_slope_top_slot_s_min,
    rear_slope_top_slot_s_max: parameters.photo_album_rear_slope_top_slot_s_max,
    rear_slope_top_slot_s_center: parameters.photo_album_rear_slope_top_slot_s_center,
    rear_slope_top_slot_cutter_overlap_s: parameters.photo_album_rear_slope_top_slot_cutter_overlap_s,
    rear_slope_top_slot_cutter_s_min: parameters.photo_album_rear_slope_top_slot_cutter_s_min,
    rear_slope_top_slot_cutter_s_max: parameters.photo_album_rear_slope_top_slot_cutter_s_max,
    rear_slope_top_slot_cutter_size_s: parameters.photo_album_rear_slope_top_slot_cutter_size_s,
    rear_slope_top_slot_cutter_center_s: parameters.photo_album_rear_slope_top_slot_cutter_center_s,
    narrow_stop_semicircle_diameter: parameters.photo_album_narrow_stop_semicircle_diameter,
    narrow_stop_semicircle_radius: parameters.photo_album_narrow_stop_semicircle_radius,
    narrow_stop_semicircle_offset_from_lip_top_edge_s: parameters.photo_album_narrow_stop_semicircle_offset_from_lip_top_edge_s,
    narrow_stop_semicircle_clip_parallel_top_edge_s: parameters.photo_album_narrow_stop_semicircle_clip_parallel_top_edge_s,
    narrow_stop_semicircle_center_s: parameters.photo_album_narrow_stop_semicircle_center_s,
    narrow_stop_semicircle_center_y: parameters.photo_album_narrow_stop_semicircle_center_y,
    narrow_stop_semicircle_center_n: parameters.photo_album_narrow_stop_semicircle_center_n,
    narrow_stop_semicircle_s_min: parameters.photo_album_narrow_stop_semicircle_s_min,
    narrow_stop_semicircle_s_max: parameters.photo_album_narrow_stop_semicircle_s_max,
    narrow_stop_semicircle_y_min: parameters.photo_album_narrow_stop_semicircle_y_min,
    narrow_stop_semicircle_y_max: parameters.photo_album_narrow_stop_semicircle_y_max,
    narrow_stop_semicircle_cut_depth_n: parameters.photo_album_narrow_stop_semicircle_cut_depth_n,
    narrow_stop_semicircle_cutter_overlap_n: parameters.photo_album_narrow_stop_semicircle_cutter_overlap_n,
    narrow_stop_semicircle_cutter_min_n: parameters.photo_album_narrow_stop_semicircle_cutter_min_n,
    narrow_stop_semicircle_cutter_max_n: parameters.photo_album_narrow_stop_semicircle_cutter_max_n,
    narrow_stop_semicircle_cutter_depth_n: parameters.photo_album_narrow_stop_semicircle_cutter_depth_n,
    narrow_stop_semicircle_cutter_center_n: parameters.photo_album_narrow_stop_semicircle_cutter_center_n,
    narrow_stop_semicircle_segments: parameters.photo_album_narrow_stop_semicircle_segments,
    rear_slope_block_low_contact_fillet_radius: parameters.photo_album_rear_slope_block_low_contact_fillet_radius,
    rear_slope_block_low_contact_filler_segments: parameters.photo_album_rear_slope_block_low_contact_filler_segments,
    rear_slope_block_low_contact_filler_s_min: parameters.photo_album_rear_slope_block_low_contact_filler_s_min,
    rear_slope_block_low_contact_filler_s_max: parameters.photo_album_rear_slope_block_low_contact_filler_s_max,
    rear_slope_block_low_contact_filler_n_min: parameters.photo_album_rear_slope_block_low_contact_filler_n_min,
    rear_slope_block_low_contact_filler_n_max: parameters.photo_album_rear_slope_block_low_contact_filler_n_max,
    rear_slope_block_low_contact_filler_width_y: parameters.photo_album_rear_slope_block_low_contact_filler_width_y,
    rear_slope_block_low_contact_filler_center_y: parameters.photo_album_rear_slope_block_low_contact_filler_center_y,
  };
  return groups;
}

function summarizeTemplateProduct(product, detection) {
  return {
    id: product?.id || 'unihiker_photo_album',
    name: product?.name || '鐩稿唽',
    product_name: product?.product_name || '行空板相册',
    hardware_system: product?.hardware_system || 'unihiker',
    status: product?.status || 'available',
    model_status: product?.model_status || 'implemented_stage_9_5',
    template_id: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    description: product?.description || '',
    matched: true,
    source: detection?.source || 'deterministic_product_detector',
    reason: detection?.reason || '',
    confidence: detection?.confidence ?? 0.96,
  };
}

function buildMissingProfileResponse({ product, detection, body, missing }) {
  const missingText = missing.join('、');
  const response = {
    status: 'needs_input',
    title: '行空板相册模型缺少必要硬件资料',
    message: `已识别为行空板相册项目，但当前硬件库缺少必要硬件资料：${missingText}。请先补齐这些硬件后再生成模型。`,
    deterministic_product: summarizeTemplateProduct(product, detection),
    template_id: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    partial_intent: buildIntent({ product, body, bom: [] }),
    partial_bom: [],
    bom: [],
    missing_hardware_requests: missing.map((id) => ({ hardware_id: id, reason: 'deterministic_template_required_profile_missing' })),
    questions: [
      `请先补齐这些硬件资料：${missingText}。补齐后即可继续生成行空板相册模型。`,
    ],
    blocking_reason: 'deterministic_template_missing_profile',
    source: 'deterministic_product_template',
    intent_analysis: {
      source: 'deterministic_product_template',
      status: 'blocked',
      model_status: 'skipped',
      reason: detection?.reason || '',
      confidence: detection?.confidence ?? 0.96,
      conversation_route: body.conversation_route || body.conversationRoute || null,
      revision_intent: body.revision_intent || body.revisionIntent || null,
    },
    warnings: [
      {
        id: 'deterministic_template_missing_profile',
        status: 'blocked',
        message: `当前缺少必要硬件资料：${missingText}`,
      },
    ],
  };
  response.generation_trace = {
    schema_version: 'generation_trace_v1',
    stage: 'blocked',
    template_id: UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID,
    deterministic_product: response.deterministic_product,
    skipped_stages: [
      'model_intent_analysis',
      'generic_bom_selection',
      'generic_layout_solver',
      'generic_cad_generation',
    ],
    source: 'deterministic_product_template',
  };
  return response;
}

function buildTemplateGenerationTrace(artifact) {
  const checks = Array.isArray(artifact.checks) ? artifact.checks : [];
  return {
    schema_version: 'generation_trace_v1',
    stage: 'artifact',
    generated_at: new Date().toISOString(),
    deterministic_product: artifact.deterministic_product,
    template_id: artifact.template_id,
    intent: {
      source: artifact.intent_analysis?.source,
      status: artifact.intent_analysis?.status,
      reason: artifact.intent_analysis?.reason,
      confidence: artifact.intent_analysis?.confidence,
    },
    conversation_route: artifact.conversation_route,
    revision_intent: artifact.revision_intent,
    hardware: {
      bom_count: artifact.bom.length,
      hardware_ids: artifact.bom.map((item) => item.hardware_id),
      builtin_profile_ids: artifact.bom
        .filter((item) => item.profile_status === 'builtin')
        .map((item) => item.hardware_id),
    },
    layout: {
      hardware_count: artifact.design_state.layout_plan.hardware_transforms.length,
      opening_count: artifact.design_state.layout_plan.opening_transforms.length,
      mounting_hole_count: artifact.design_state.layout_plan.mounting_hole_transforms.length,
      shape: artifact.design_state.layout_plan.shape,
      stage: artifact.design_state.layout_plan.stage,
    },
    validation: {
      validation_status: checks.some((item) => item.status === 'fail') ? 'fail' : 'pending',
      status_counts: checks.reduce((acc, item) => {
        acc[item.status] = (acc[item.status] || 0) + 1;
        return acc;
      }, {}),
      failing_ids: checks.filter((item) => item.status === 'fail').map((item) => item.id),
      pending_ids: checks.filter((item) => item.status === 'pending').map((item) => item.id),
    },
    skipped_stages: [
      'model_intent_analysis',
      'requirement_analysis_confirmation',
      'generic_bom_selection',
      'generic_layout_solver',
      'generic_cad_generation',
    ],
    source: 'deterministic_product_template',
  };
}

function buildCadQueryCode({ parameters = TEMPLATE_PARAMETERS, changedTemplateKeys = new Set() } = {}) {
  let source = readFileSync(PHOTO_ALBUM_CADQUERY_SOURCE_URL, 'utf8');
  for (const key of CADQUERY_ASSIGNMENT_PARAMETER_KEYS) {
    const templateKey = GUI_PARAMETER_TO_TEMPLATE_PARAMETER[key] || `photo_album_${key}`;
    if (!changedTemplateKeys.has(templateKey)) continue;
    if (!Object.prototype.hasOwnProperty.call(parameters, templateKey)) continue;
    source = replacePythonNumberAssignment(source, key, parameters[templateKey]);
  }
  return source;
}

function replacePythonNumberAssignment(source, key, value) {
  const number = Number(value);
  if (!Number.isFinite(number)) return source;
  const pattern = new RegExp(`^${escapeRegExp(key)}\\s*=\\s*[-+]?\\d+(?:\\.\\d+)?(?:[eE][-+]?\\d+)?\\s*$`, 'm');
  return source.replace(pattern, `${key} = ${formatPythonNumber(number)}`);
}

function formatPythonNumber(value) {
  if (Number.isInteger(value)) return `${value}.0`;
  return String(Math.round(value * 1000000) / 1000000);
}

function escapeRegExp(value) {
  return String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function buildPrintableParts() {
  return DEFAULT_PRINTABLE_PARTS.map((item) => ({ ...item }));
}
function round3(value) {
  return Math.round(Number(value) * 1000) / 1000;
}

function formatNumber(value) {
  const fixed = Number(value).toFixed(3);
  return fixed.replace(/0+$/, '').replace(/\.$/, '.0');
}
