import {
  DEFAULT_PARAMETERS,
} from '../pipeline/shared.js';
import {
  buildParameterGroups,
  buildPreviewAssets,
} from '../pipeline/cad.js';
import {
  getHardwareProfile,
} from '../hardware-library.js';

export const XIAO_SMART_PENDANT_TEMPLATE_ID = 'xiao_smart_pendant_v1';

const TEMPLATE_HARDWARE = Object.freeze([
  {
    hardware_id: 'xiao_esp32s3_sense',
    profile_status: 'assumed_future_profile',
    role: 'camera_microphone_controller',
    quantity: 1,
    mount_surface: 'pendant_inner_front',
    placement: 'inside_front_camera_and_microphone_aligned_to_lid_openings',
    function: 'Main control, camera capture, and microphone voice input.',
  },
  {
    hardware_id: 'xiao_rgb_led_ring',
    profile_status: 'assumed_future_profile',
    role: 'rgb_led_ring',
    quantity: 1,
    mount_surface: 'pendant_lid_inner',
    placement: 'inside_front_lid_around_camera',
    function: 'Front RGB assistant status light ring.',
  },
  {
    hardware_id: 'compact_lipo_battery',
    profile_status: 'builtin',
    role: 'battery',
    quantity: 1,
    mount_surface: 'pendant_base_floor',
    placement: 'inside_back_shell_lower_area',
    function: 'Compact wearable battery power source.',
  },
]);

const ASSUMED_PROFILES = Object.freeze({
  xiao_esp32s3_sense: {
    id: 'xiao_esp32s3_sense',
    name: 'XIAO ESP32S3 Sense camera and microphone controller',
    hardware_system: 'xiao',
    category: 'controller',
    roles: ['controller', 'camera', 'microphone', 'voice_assistant', 'xiao'],
    profile_status: 'assumed_future_profile',
    dimensions_mm: {
      length_x: 22,
      width_y: 40,
      height_z: 7,
      note: 'Temporary assumed bounding box for workflow bring-up. Camera and microphone are part of this controller.',
    },
    mounting: {
      mode: 'internal_reference_mount',
      holes: [],
    },
    opening: [],
    keepouts: [],
    thumbnail_url: '/assets/hardware/xiao_esp32s3_sense.png',
  },
  xiao_rgb_led_ring: {
    id: 'xiao_rgb_led_ring',
    name: 'XIAO RGB LED ring',
    hardware_system: 'xiao',
    category: 'indicator',
    roles: ['rgb_led_ring', 'status_light', 'assistant_feedback_light'],
    profile_status: 'assumed_future_profile',
    dimensions_mm: {
      length_x: 48,
      width_y: 48,
      height_z: 2.6,
      outer_diameter: 48,
      inner_diameter: 31,
      led_count: 12,
    },
    mounting: {
      mode: 'internal_reference_mount',
      holes: [],
    },
    opening: [],
    keepouts: [],
    thumbnail_url: '/assets/hardware/xiao_rgb_led_ring.png',
  },
});

const ENCLOSURE = Object.freeze({
  pendant_diameter: 58,
  pendant_thickness_z: 16,
  inner_diameter: 51,
  front_lid_thickness: 2.4,
  floor_thickness: 2,
  lanyard_loop_outer_diameter: 12,
  lanyard_hole_diameter: 5.5,
});

const TEMPLATE_PARAMETERS = Object.freeze({
  ...DEFAULT_PARAMETERS,
  wall_thickness: 2.2,
  floor_thickness: ENCLOSURE.floor_thickness,
  lid_thickness: ENCLOSURE.front_lid_thickness,
  lid_lip_height: 2,
  lid_clearance: 0.25,
  corner_radius: 29,
  hardware_gap: 3,
  screw_boss_diameter: 5.2,
  screw_hole_diameter: 2,
});

export function buildXiaoSmartPendantTemplate({ product, detection, body = {}, context = {} } = {}) {
  const profiles = collectAssumedTemplateProfiles();
  const designId = context.designId || 'ZW-XIAO-PENDANT-TEMPLATE-PREVIEW';
  const resultStartedAt = context.resultStartedAt || new Date().toISOString();
  const enclosure = buildEnclosure();
  const bom = buildBom(profiles.byId);
  const intent = buildIntent({ product, body, bom });
  const layoutPlan = buildLayoutPlan({ profiles: profiles.byId, enclosure });
  const validation = buildTemplateValidation({ profiles: profiles.items, layoutPlan });
  const cadqueryCode = buildCadQueryCode();
  const warnings = [...validation.warnings];
  const deterministicProduct = summarizeTemplateProduct(product, detection);
  const assumedProfileIds = bom
    .filter((item) => item.profile_status === 'assumed_future_profile')
    .map((item) => item.hardware_id);
  const builtinProfileIds = bom
    .filter((item) => item.profile_status === 'builtin')
    .map((item) => item.hardware_id);
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
      notes: ['XIAO pendant v1 intentionally uses assumed future profiles for workflow bring-up.'],
    },
    hardware_profiles: profiles.items,
    profile_validation_report: {
      status: 'warn',
      source: 'deterministic_product_template',
      checked_profile_ids: TEMPLATE_HARDWARE.map((item) => item.hardware_id),
      assumed_profile_ids: assumedProfileIds,
      builtin_profile_ids: builtinProfileIds,
      missing_profile_ids: profiles.missing,
      message: 'XIAO controller and LED ring profiles are still assumed; compact_lipo_battery is read from the hardware library.',
    },
    mounting_plan: layoutPlan.hardware_transforms.map((item) => ({
      hardware_id: item.hardware_id,
      target_face: item.target_face,
      mount_surface: item.mount_surface,
      placement: item.placement,
      fixed_to_enclosure: item.fixed_to_enclosure,
    })),
    layout_plan: layoutPlan,
    enclosure_parameters: enclosure,
    cad_parameters: {
      generator: XIAO_SMART_PENDANT_TEMPLATE_ID,
      units: 'mm',
      hardware_count: TEMPLATE_HARDWARE.length,
      shape: 'circular_pendant',
    },
    validation_context: validation.validation_context,
    parameters: TEMPLATE_PARAMETERS,
    hardware_face_overrides: {},
    hardware_rotation_overrides: {},
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
    resolution_option_route: null,
    ignored_missing_hardware_requests: [],
    dropped_functions: [],
    deterministic_product: deterministicProduct,
    template_id: XIAO_SMART_PENDANT_TEMPLATE_ID,
    warnings,
  };

  const intentAnalysis = {
    source: 'deterministic_product_template',
    status: 'ok',
    model_status: 'skipped',
    reason: detection?.reason || 'deterministic XIAO smart pendant template matched',
    confidence: detection?.confidence ?? 0.96,
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
  };

  const artifact = {
    status: 'artifact',
    title: 'XIAO smart pendant deterministic model',
    message: 'Matched the built-in XIAO smart pendant template and generated a fixed circular pendant CadQuery model without generic LLM intent, BOM, or layout steps.',
    deterministic_product: deterministicProduct,
    template_id: XIAO_SMART_PENDANT_TEMPLATE_ID,
    bom,
    partial_bom: bom,
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    function_verification_report: designState.function_verification_report,
    design_state: designState,
    parameters: buildParameterGroups(TEMPLATE_PARAMETERS, enclosure, layoutPlan),
    intent_analysis: intentAnalysis,
    cadquery_code: cadqueryCode,
    preview_assets: buildPreviewAssets({ enclosure, layoutPlan, parameters: TEMPLATE_PARAMETERS }),
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

export function collectAssumedTemplateProfiles() {
  const byId = new Map();
  const missing = [];
  for (const item of TEMPLATE_HARDWARE) {
    if (item.profile_status === 'builtin') {
      const profile = getHardwareProfile(item.hardware_id);
      if (profile) {
        byId.set(item.hardware_id, { ...profile, profile_status: 'builtin' });
      } else {
        missing.push(item.hardware_id);
      }
    } else {
      byId.set(item.hardware_id, ASSUMED_PROFILES[item.hardware_id]);
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
      hardware_system: profile?.hardware_system || 'xiao',
      quantity: item.quantity,
      required_or_optional: 'required',
      function: item.function,
      profile_status: profile?.profile_status || item.profile_status,
      template_placement: item.placement,
      mounting_intent: {
        preferred_surface: item.mount_surface,
        fixed_to_enclosure: false,
      },
    };
  });
}

function buildIntent({ product, body, bom }) {
  return {
    schema_version: '1.0',
    product_name: product?.product_name || 'XIAO smart pendant',
    deterministic_product_id: product?.id || 'xiao_smart_pendant',
    template_id: XIAO_SMART_PENDANT_TEMPLATE_ID,
    functions: [
      'camera capture',
      'microphone voice input',
      'voice assistant interaction',
      'RGB light feedback',
      'wearable battery power',
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
        hardware_id: 'xiao_esp32s3_sense',
        target_face: 'pendant_inner_front',
        user_phrase: 'Camera, microphone, and controller are one assumed XIAO module aligned to the front camera and pickup holes.',
      },
      {
        hardware_id: 'xiao_rgb_led_ring',
        target_face: 'pendant_lid_inner',
        user_phrase: 'LED ring sits under the front lid and aligns with the circular light windows.',
      },
      {
        hardware_id: 'compact_lipo_battery',
        target_face: 'pendant_base_floor',
        user_phrase: 'Compact LiPo battery is placed in the lower area of the pendant back shell.',
      },
    ],
    enclosure_intent: {
      type: 'deterministic_circular_pendant',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'front_screw_lid',
      allowed_shape: 'circular_pendant',
      deterministic_model: XIAO_SMART_PENDANT_TEMPLATE_ID,
    },
    user_constraints: {
      raw_prompt: typeof body.prompt === 'string' ? body.prompt : '',
      size_mm: {},
      notes: [
        'XIAO smart pendant deterministic branch.',
        'Camera and microphone are part of xiao_esp32s3_sense; there is no standalone microphone module in this BOM.',
        'Hardware profiles are assumed in this round and should be imported later.',
      ],
    },
    unknowns: [],
  };
}

function buildEnclosure() {
  const diameter = ENCLOSURE.pendant_diameter;
  const thickness = ENCLOSURE.pendant_thickness_z;
  const innerDiameter = ENCLOSURE.inner_diameter;
  return {
    outer_box_size: {
      length_x: diameter,
      width_y: diameter + ENCLOSURE.lanyard_loop_outer_diameter,
      height_z: thickness,
    },
    inner_box_size: {
      length_x: innerDiameter,
      width_y: innerDiameter,
      height_z: thickness - ENCLOSURE.floor_thickness - ENCLOSURE.front_lid_thickness,
    },
    pendant_diameter_mm: diameter,
    pendant_thickness_z_mm: thickness,
    inner_diameter_mm: innerDiameter,
    wall_thickness: TEMPLATE_PARAMETERS.wall_thickness,
    floor_thickness: TEMPLATE_PARAMETERS.floor_thickness,
    lid_thickness: TEMPLATE_PARAMETERS.lid_thickness,
    lid_lip_height: TEMPLATE_PARAMETERS.lid_lip_height,
    lid_clearance: TEMPLATE_PARAMETERS.lid_clearance,
    corner_radius: diameter / 2,
    lanyard_loop_outer_diameter_mm: ENCLOSURE.lanyard_loop_outer_diameter,
    lanyard_hole_diameter_mm: ENCLOSURE.lanyard_hole_diameter,
    screw_bosses: radialPoints(4, 21, 45).map(([x, y]) => ({ x: round1(x), y: round1(y) })),
  };
}

function buildLayoutPlan({ profiles, enclosure }) {
  return {
    strategy: XIAO_SMART_PENDANT_TEMPLATE_ID,
    shape: 'circular_pendant',
    hardware_transforms: [
      hardwareTransform({
        profile: profiles.get('xiao_esp32s3_sense'),
        center: { x: 0, y: 2, z: 8.9 },
        mount_surface: 'pendant_inner_front',
        target_face: 'front_lid_inner',
        placement: 'inside_front_camera_and_microphone_aligned_to_lid_openings',
        fixed_to_enclosure: false,
      }),
      hardwareTransform({
        profile: profiles.get('xiao_rgb_led_ring'),
        center: { x: 0, y: 0, z: 12.6 },
        mount_surface: 'pendant_lid_inner',
        target_face: 'front_lid_inner',
        placement: 'inside_front_lid_around_camera',
        fixed_to_enclosure: false,
      }),
      hardwareTransform({
        profile: profiles.get('compact_lipo_battery'),
        center: { x: 0, y: -11, z: 4 },
        mount_surface: 'pendant_base_floor',
        target_face: 'base_floor',
        placement: 'inside_back_shell_lower_area',
        fixed_to_enclosure: false,
      }),
    ],
    opening_transforms: [
      {
        id: 'xiao_pendant_camera_lens_opening',
        hardware_id: 'xiao_esp32s3_sense',
        type: 'round_hole',
        face: 'top',
        basis: 'camera lens opening',
        center: { x: 0, y: 7, z: enclosure.outer_box_size.height_z },
        size_mm: { diameter: 7 },
        diameter_mm: 7,
        clearance_mm: 0.5,
        projected_from_hardware: true,
      },
      {
        id: 'xiao_pendant_led_ring_light_windows',
        hardware_id: 'xiao_rgb_led_ring',
        type: 'radial_round_hole_array',
        face: 'top',
        basis: 'LED ring light windows',
        center: { x: 0, y: 0, z: enclosure.outer_box_size.height_z },
        count: 12,
        radius_mm: 20,
        size_mm: { diameter: 4.4 },
        diameter_mm: 4.4,
        clearance_mm: 0.4,
        projected_from_hardware: true,
      },
      {
        id: 'xiao_pendant_microphone_pickup_holes',
        hardware_id: 'xiao_esp32s3_sense',
        type: 'round_hole_array',
        face: 'top',
        basis: 'microphone pickup holes',
        center: { x: 0, y: -8, z: enclosure.outer_box_size.height_z },
        count: 6,
        size_mm: { diameter: 1.8 },
        diameter_mm: 1.8,
        clearance_mm: 0.2,
        projected_from_hardware: true,
      },
      {
        id: 'xiao_pendant_lanyard_hole',
        hardware_id: 'enclosure',
        type: 'round_hole',
        face: 'top',
        basis: 'lanyard hole',
        center: { x: 0, y: 33, z: enclosure.outer_box_size.height_z / 2 },
        size_mm: { diameter: ENCLOSURE.lanyard_hole_diameter },
        diameter_mm: ENCLOSURE.lanyard_hole_diameter,
        clearance_mm: 0.4,
        projected_from_hardware: false,
      },
    ],
    mounting_hole_transforms: radialPoints(4, 21, 45).map(([x, y], index) => ({
      id: `xiao_pendant_lid_screw_${index + 1}`,
      hardware_id: 'enclosure',
      type: 'lid_screw_hole',
      role: 'lid_fastener',
      face: 'top',
      mount_surface: 'front_lid',
      center: { x: round1(x), y: round1(y), z: enclosure.outer_box_size.height_z },
      diameter_mm: TEMPLATE_PARAMETERS.screw_hole_diameter,
      size_mm: { diameter: TEMPLATE_PARAMETERS.screw_hole_diameter },
      source: 'deterministic_template',
    })),
    mounting_transforms: [
      {
        id: 'compact_lipo_battery_floor_pocket',
        hardware_id: 'compact_lipo_battery',
        type: 'battery_pocket_reference',
        role: 'battery_retainer',
        anchor_face: 'bottom',
        mount_surface: 'pendant_base_floor',
        center: { x: 0, y: -11, z: 2.6 },
        size_mm: { length_x: 25, width_y: 19, height_z: 1.2 },
        clearance_mm: 1,
      },
      {
        id: 'xiao_controller_standoff_pattern',
        hardware_id: 'xiao_esp32s3_sense',
        type: 'controller_standoff_reference',
        role: 'controller_support',
        anchor_face: 'bottom',
        mount_surface: 'pendant_base_floor',
        center: { x: 0, y: 2, z: 3.8 },
        size_mm: { length_x: 18, width_y: 28, height_z: 2 },
        clearance_mm: 0.8,
      },
    ],
    notes: [
      'XIAO, camera, and microphone are represented by the single assumed xiao_esp32s3_sense module.',
      'The XIAO pendant workflow is separate from unihiker plant caregiver and mpython placeholder workflows.',
    ],
  };
}

function hardwareTransform({ profile, center, mount_surface, target_face, placement, fixed_to_enclosure }) {
  return {
    hardware_id: profile.id,
    name: profile.name,
    category: profile.category,
    center,
    bounding_box: {
      length_x: Number(profile.dimensions_mm?.length_x || 10),
      width_y: Number(profile.dimensions_mm?.width_y || 10),
      height_z: Number(profile.dimensions_mm?.height_z || 5),
    },
    dimensions_mm: profile.dimensions_mm || {},
    cad_reference: profile.cad_reference || {},
    openings: Array.isArray(profile.opening) ? profile.opening : [],
    keepouts: Array.isArray(profile.keepouts) ? profile.keepouts : [],
    profile_status: profile.profile_status,
    mount_surface,
    target_face,
    placement,
    fixed_to_enclosure,
    layout_rotation_deg: 0,
  };
}

function buildTemplateValidation({ profiles, layoutPlan }) {
  const assumedIds = profiles
    .filter((item) => item.profile_status === 'assumed_future_profile')
    .map((item) => item.id);
  const builtinIds = profiles
    .filter((item) => item.profile_status === 'builtin')
    .map((item) => item.id);
  const checks = [
    {
      id: 'source_deterministic',
      label: 'Generation source',
      status: 'pass',
      message: 'Model is generated by the backend deterministic template library, not LLM-authored CAD code.',
    },
    {
      id: 'template_assumed_profiles',
      label: 'Assumed hardware profiles',
      status: 'pending',
      message: 'XIAO pendant v1 still assumes the controller and LED ring profiles; compact_lipo_battery is builtin.',
      details: { assumed_profile_ids: assumedIds, builtin_profile_ids: builtinIds },
    },
    {
      id: 'template_workflow_separation',
      label: 'Workflow separation',
      status: 'pass',
      message: 'XIAO smart pendant is routed through its own deterministic template and does not reuse the unihiker watering template.',
    },
    {
      id: 'template_openings',
      label: 'Pendant openings',
      status: 'pass',
      message: 'Camera opening, LED ring light windows, microphone pickup holes, and lanyard hole are included.',
      details: {
        opening_ids: layoutPlan.opening_transforms.map((item) => item.id),
      },
    },
    {
      id: 'cadquery_code_static',
      label: 'CadQuery code static check',
      status: 'pass',
      message: 'Template CadQuery code is generated from a fixed backend module and contains the required result entry point.',
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
        id: 'xiao_pendant_assumed_profiles',
        status: 'warn',
        message: 'xiao_esp32s3_sense and xiao_rgb_led_ring are still assumed future profiles; compact_lipo_battery is builtin.',
        assumed_profile_ids: assumedIds,
        builtin_profile_ids: builtinIds,
      },
    ],
    validation_context: {
      aabb_model: 'deterministic_template_circular_pendant_with_mixed_builtin_and_assumed_hardware',
      mesh_validation: 'pending_missing_cadquery',
      assumed_profiles: assumedIds.length > 0,
      builtin_profile_ids: builtinIds,
      non_rectangular_template_shape: 'circular_pendant',
    },
  };
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
      assumed_profile_ids: artifact.bom
        .filter((item) => item.profile_status === 'assumed_future_profile')
        .map((item) => item.hardware_id),
    },
    layout: {
      hardware_count: artifact.design_state.layout_plan.hardware_transforms.length,
      opening_count: artifact.design_state.layout_plan.opening_transforms.length,
      mounting_hole_count: artifact.design_state.layout_plan.mounting_hole_transforms.length,
      shape: 'circular_pendant',
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

function summarizeTemplateProduct(product, detection) {
  return {
    id: product?.id || 'xiao_smart_pendant',
    name: product?.name || 'Smart pendant',
    product_name: product?.product_name || 'XIAO smart pendant',
    hardware_system: product?.hardware_system || 'xiao',
    status: product?.status || 'available',
    model_status: product?.model_status || 'implemented',
    template_id: XIAO_SMART_PENDANT_TEMPLATE_ID,
    description: product?.description || '',
    matched: true,
    source: detection?.source || 'deterministic_product_detector',
    reason: detection?.reason || '',
    confidence: detection?.confidence ?? 0.96,
  };
}

function buildCadQueryCode() {
  return `# ZW-CAD-intent deterministic template: ${XIAO_SMART_PENDANT_TEMPLATE_ID}
# Backend template library model, not LLM-authored CAD code.
# Units: millimeters. This single file is CQ-editor ready.

import cadquery as cq
import math

# circular pendant shell with front lid, camera lens opening,
# LED ring light windows, microphone pickup holes, and lanyard hole.

pendant_diameter = 58.0
outer_radius = pendant_diameter / 2.0
pendant_thickness = 16.0
base_height = 13.6
lid_thickness = 2.4
floor_thickness = 2.0
inner_diameter = 51.0
inner_radius = inner_diameter / 2.0
lid_lip_height = 2.0
lanyard_loop_outer_diameter = 12.0
lanyard_loop_center_y = outer_radius + 4.0
lanyard_hole_diameter = 5.5


def radial_points(count, radius, start_angle_deg=0.0):
    result = []
    for index in range(count):
        angle = math.radians(start_angle_deg + 360.0 * index / count)
        result.append((math.cos(angle) * radius, math.sin(angle) * radius))
    return result


def make_cylinder_z(diameter, height, center_x=0.0, center_y=0.0, z_min=0.0):
    return (
        cq.Workplane("XY")
        .center(center_x, center_y)
        .circle(diameter / 2.0)
        .extrude(height)
        .translate((0, 0, z_min))
    )


def make_centered_box(size, center):
    return (
        cq.Workplane("XY")
        .box(size[0], size[1], size[2], centered=(True, True, True))
        .translate(center)
    )


def make_xiao_esp32s3_sense():
    # Assumed temporary builder: XIAO controller, camera, and microphone are one module.
    pcb = make_centered_box((22.0, 40.0, 1.2), (0.0, 0.0, 0.6))
    usb = make_centered_box((9.0, 6.0, 3.2), (0.0, -20.5, 2.4))
    camera_board = make_centered_box((11.0, 11.0, 1.2), (0.0, 7.0, 2.0))
    camera_lens = make_cylinder_z(5.2, 2.6, 0.0, 7.0, 2.6)
    microphone = make_cylinder_z(2.2, 0.4, -5.2, -8.0, 1.2)
    mic_marker_1 = make_cylinder_z(1.0, 0.25, -2.5, -10.5, 1.25)
    mic_marker_2 = make_cylinder_z(1.0, 0.25, 0.0, -11.5, 1.25)
    mic_marker_3 = make_cylinder_z(1.0, 0.25, 2.5, -10.5, 1.25)
    return (
        pcb
        .union(usb)
        .union(camera_board)
        .union(camera_lens)
        .union(microphone)
        .union(mic_marker_1)
        .union(mic_marker_2)
        .union(mic_marker_3)
    )


def make_xiao_rgb_led_ring():
    # Assumed temporary builder: 12-light RGB ring around the camera.
    ring = make_cylinder_z(48.0, 1.2, 0.0, 0.0, 0.0).cut(make_cylinder_z(31.0, 2.0, 0.0, 0.0, -0.4))
    for x, y in radial_points(12, 20.0, 90.0):
        led = make_cylinder_z(3.4, 0.9, x, y, 1.2)
        ring = ring.union(led)
    return ring


def make_compact_lipo_battery():
    # Builtin common hardware: 120mAh 3.7V square LiPo, body 21 x 15 x 4 mm with two 25 mm wires on +X.
    battery_length_x = 21.0
    battery_width_y = 15.0
    battery_thickness_z = 4.0
    wire_length_x = 25.0
    wire_diameter = 0.8
    wire_spacing_y = 3.0
    battery = make_centered_box((battery_length_x, battery_width_y, battery_thickness_z), (0.0, 0.0, battery_thickness_z / 2.0))
    positive_wire = (
        cq.Workplane("YZ")
        .center(wire_spacing_y / 2.0, battery_thickness_z / 2.0)
        .circle(wire_diameter / 2.0)
        .extrude(wire_length_x)
        .translate((battery_length_x / 2.0, 0, 0))
    )
    negative_wire = (
        cq.Workplane("YZ")
        .center(-wire_spacing_y / 2.0, battery_thickness_z / 2.0)
        .circle(wire_diameter / 2.0)
        .extrude(wire_length_x)
        .translate((battery_length_x / 2.0, 0, 0))
    )
    return battery.union(positive_wire).union(negative_wire)


def build_hollow_base():
    base_disc = make_cylinder_z(pendant_diameter, base_height, 0.0, 0.0, 0.0)
    lanyard_loop = make_cylinder_z(lanyard_loop_outer_diameter, base_height, 0.0, lanyard_loop_center_y, 0.0)
    inner_cavity = make_cylinder_z(inner_diameter, base_height + 0.6, 0.0, 0.0, floor_thickness)
    lanyard_cut = make_cylinder_z(lanyard_hole_diameter, base_height + 1.0, 0.0, lanyard_loop_center_y, -0.5)
    return base_disc.union(lanyard_loop).cut(inner_cavity).cut(lanyard_cut)


def apply_screw_bosses(base_part):
    # Four full-height internal lid screw bosses.
    boss_height = base_height - floor_thickness
    for x, y in radial_points(4, 21.0, 45.0):
        boss = make_cylinder_z(5.2, boss_height, x, y, floor_thickness)
        screw_cut = make_cylinder_z(2.0, boss_height + 1.0, x, y, floor_thickness - 0.5)
        base_part = base_part.union(boss.cut(screw_cut))
    return base_part


def build_lid():
    lid_disc = make_cylinder_z(pendant_diameter, lid_thickness, 0.0, 0.0, base_height)
    lanyard_cap = make_cylinder_z(lanyard_loop_outer_diameter, lid_thickness, 0.0, lanyard_loop_center_y, base_height)
    lip_outer = make_cylinder_z(49.4, lid_lip_height, 0.0, 0.0, base_height - lid_lip_height)
    lip_inner = make_cylinder_z(43.0, lid_lip_height + 0.8, 0.0, 0.0, base_height - lid_lip_height - 0.4)
    return lid_disc.union(lanyard_cap).union(lip_outer.cut(lip_inner))


def apply_lid_screw_holes(lid_part):
    for x, y in radial_points(4, 21.0, 45.0):
        lid_part = lid_part.cut(make_cylinder_z(2.2, lid_thickness + 1.0, x, y, base_height - 0.5))
    return lid_part


def apply_openings(base_part, lid_part):
    # camera lens opening
    lid_part = lid_part.cut(make_cylinder_z(7.0, lid_thickness + 1.2, 0.0, 7.0, base_height - 0.4))

    # LED ring light windows
    for x, y in radial_points(12, 20.0, 90.0):
        lid_part = lid_part.cut(make_cylinder_z(4.4, lid_thickness + 1.2, x, y, base_height - 0.4))

    # microphone pickup holes
    for x, y in [(-5.0, -7.0), (0.0, -7.0), (5.0, -7.0), (-3.0, -11.0), (3.0, -11.0), (0.0, -14.0)]:
        lid_part = lid_part.cut(make_cylinder_z(1.8, lid_thickness + 1.2, x, y, base_height - 0.4))

    # lanyard hole
    lanyard_cut = make_cylinder_z(lanyard_hole_diameter, pendant_thickness + 2.0, 0.0, lanyard_loop_center_y, -1.0)
    base_part = base_part.cut(lanyard_cut)
    lid_part = lid_part.cut(lanyard_cut)
    return base_part, lid_part


def build_mounts():
    battery_pocket = make_centered_box((25.0, 19.0, 1.2), (0.0, -11.0, 2.6))
    controller_tray = make_centered_box((24.0, 34.0, 1.0), (0.0, 2.0, 5.2))
    controller_clearance = make_centered_box((21.0, 31.0, 1.4), (0.0, 2.0, 5.4))
    tray = controller_tray.cut(controller_clearance)
    return [battery_pocket, tray]


def apply_mounts(base_part, lid_part):
    for mount in build_mounts():
        base_part = base_part.union(mount)
    return base_part, lid_part


def build_hardware_references():
    xiao_controller = make_xiao_esp32s3_sense().translate((0.0, 2.0, 6.0))
    led_ring = make_xiao_rgb_led_ring().translate((0.0, 0.0, 11.1))
    compact_battery = make_compact_lipo_battery().translate((0.0, -11.0, 2.0))
    return [xiao_controller, led_ring, compact_battery]


base_part = build_hollow_base()
base_part = apply_screw_bosses(base_part)
lid_part = build_lid()
lid_part = apply_lid_screw_holes(lid_part)
base_part, lid_part = apply_mounts(base_part, lid_part)
base_part, lid_part = apply_openings(base_part, lid_part)
hardware_reference_parts = build_hardware_references()

result = base_part.union(lid_part)
for hardware_part in hardware_reference_parts:
    result = result.union(hardware_part)

if "show_object" in globals():
    show_object(base_part, name="base_part")
    show_object(lid_part, name="lid_part")
    for index, hardware_part in enumerate(hardware_reference_parts):
        show_object(hardware_part, name="hardware_reference_%02d" % index)
`;
}

function radialPoints(count, radius, startAngleDeg = 0) {
  const points = [];
  for (let index = 0; index < count; index += 1) {
    const angle = (startAngleDeg + (360 * index) / count) * Math.PI / 180;
    points.push([Math.cos(angle) * radius, Math.sin(angle) * radius]);
  }
  return points;
}

function round1(value) {
  return Math.round(Number(value) * 10) / 10;
}
