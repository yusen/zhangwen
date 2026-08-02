import {
  getHardwareProfile,
} from '../hardware-library.js';
import {
  DEFAULT_PARAMETERS,
  isPlainObject,
  normalizeNumberMap,
} from '../pipeline/shared.js';
import {
  buildParameterGroups,
  buildPreviewAssets,
} from '../pipeline/cad.js';

export const UNIHIKER_SMART_WATERING_TEMPLATE_ID = 'unihiker_smart_watering_system_v1';

const TEMPLATE_HARDWARE = Object.freeze([
  {
    hardware_id: 'battery_18650_holder',
    role: 'battery',
    quantity: 1,
    mount_surface: 'base_floor',
    placement: 'inside_base_floor',
    function: '为主控和水泵驱动模块供电。',
  },
  {
    hardware_id: 'unihiker_relay_module',
    role: 'pump_driver',
    quantity: 1,
    mount_surface: 'base_floor',
    placement: 'inside_base_floor_switch_to_back_wall',
    function: '控制直流水泵电源通断。',
  },
  {
    hardware_id: 'unihiker_sci_acquisition_module',
    role: 'data_acquisition',
    quantity: 1,
    mount_surface: 'lid_outer',
    placement: 'lid_outer_surface',
    function: '采集、处理并显示传感器数据。',
  },
  {
    hardware_id: 'unihiker_k10',
    role: 'controller',
    quantity: 1,
    mount_surface: 'external_right',
    placement: 'external_right_side_not_fixed',
    function: '承担主控计算和交互显示。',
  },
  {
    hardware_id: 'unihiker_k10_io_expansion_board',
    role: 'controller_expansion',
    quantity: 1,
    mount_surface: 'external_right',
    placement: 'external_right_side_not_fixed',
    function: '为 K10 提供外接传感器和执行器接口。',
  },
  {
    hardware_id: 'unihiker_soil_moisture_sensor',
    role: 'soil_moisture_sensor',
    quantity: 1,
    mount_surface: 'external_scene',
    placement: 'external_probe_beside_box_not_connected',
    function: '检测土壤湿度，并作为盒外探头展示。',
  },
  {
    hardware_id: 'unihiker_dc_water_pump',
    role: 'water_pump',
    quantity: 1,
    mount_surface: 'external_scene',
    placement: 'external_pump_beside_box_not_connected',
    function: '执行供水养护动作，并作为盒外水泵展示。',
  },
]);

const TEMPLATE_PARAMETERS = Object.freeze({
  ...DEFAULT_PARAMETERS,
  box_length_x: 154.8,
  box_width_y: 94.8,
  box_height_z: 55.4,
  inner_length_x: 150,
  inner_width_y: 90,
  inner_height_z: 50,
  wall_thickness: 2.4,
  floor_thickness: 2.4,
  lid_thickness: 3,
  lid_lip_height: 4,
  lid_clearance: 0.35,
  corner_radius: 5,
  hardware_gap: 5,
  screw_boss_diameter: 8,
  screw_hole_diameter: 2.2,
});

export function buildUnihikerSmartWateringTemplate({ product, detection, body = {}, context = {} } = {}) {
  const profiles = collectTemplateProfiles();
  if (profiles.missing.length) {
    return buildMissingProfileResponse({ product, detection, body, missing: profiles.missing });
  }

  const stage = context.stage === 'confirmation' ? 'confirmation' : 'artifact';
  const designId = context.designId || 'ZW-PRODUCT-TEMPLATE-PREVIEW';
  const resultStartedAt = context.resultStartedAt || new Date().toISOString();
  const parameters = buildTemplateParameters(body);
  const enclosure = buildEnclosure(parameters);
  const bom = buildBom(profiles.byId);
  const intent = buildIntent({ product, body, bom });
  const layoutPlan = buildLayoutPlan({ profiles: profiles.byId, enclosure });
  const validation = buildTemplateValidation({ profiles: profiles.items, layoutPlan, enclosure });
  const cadqueryCode = stage === 'artifact'
    ? buildCadQueryCode({
        profiles: profiles.byId,
        parameters,
        enclosure,
        layoutPlan,
      })
    : '';
  const projectDefaultParameters = projectDefaultParametersFromBody(body);
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
    },
    hardware_profiles: profiles.items,
    profile_validation_report: {
      status: 'ok',
      source: 'deterministic_product_template',
      checked_profile_ids: TEMPLATE_HARDWARE.map((item) => item.hardware_id),
      missing_profile_ids: [],
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
      generator: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
      units: 'mm',
      hardware_count: TEMPLATE_HARDWARE.length,
      geometry: {
        box_length_x: enclosure.outer_box_size.length_x,
        box_width_y: enclosure.outer_box_size.width_y,
        box_height_z: enclosure.outer_box_size.height_z,
      },
    },
    validation_context: validation.validation_context,
    parameters,
    project_default_parameters: projectDefaultParameters,
    default_parameters: projectDefaultParameters,
    hardware_face_overrides: {},
    hardware_rotation_overrides: {},
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
    resolution_option_route: null,
    ignored_missing_hardware_requests: [],
    dropped_functions: [],
    deterministic_product: summarizeTemplateProduct(product, detection),
    template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    template_layout_locked: true,
    warnings: validation.warnings,
  };

  const intentAnalysis = {
    source: 'deterministic_product_template',
    status: 'ok',
    model_status: 'skipped',
    reason: detection?.reason || 'deterministic product template matched',
    confidence: detection?.confidence ?? 0.96,
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
  };

  const artifact = {
    status: 'artifact',
    title: '行空板植物养护系统模型已生成',
    message: '检测到已有相似的植物养护系统设计方案，已为你调用合适的设计参数并生成模型。请拖动模型检查结构，满意后导出 STL；如果要优化，请直接输入修改建议。',
    deterministic_product: summarizeTemplateProduct(product, detection),
    template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    bom,
    partial_bom: bom,
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    function_verification_report: designState.function_verification_report,
    design_state: designState,
    parameters: buildPlantCareParameterGroups(parameters, enclosure, layoutPlan),
    intent_analysis: intentAnalysis,
    cadquery_code: cadqueryCode,
    preview_assets: buildPreviewAssets({ enclosure, layoutPlan, parameters }),
    exports: [],
    checks: validation.checks,
    warnings: validation.warnings,
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
    resolution_option_route: null,
    ignored_missing_hardware_requests: [],
    dropped_functions: [],
    source: 'deterministic_product_template',
  };

  const blockingValidation = validation.checks.find((item) => item.status === 'fail');
  if (blockingValidation) {
    const generationTrace = {
      ...buildTemplateGenerationTrace(artifact, 'needs_input'),
      blocking_reason: 'template_layout_capacity_fail',
    };
    designState.template_confirmation_required = true;
    designState.generation_trace = generationTrace;
    return {
      status: 'needs_input',
      title: '盒体尺寸无法容纳模板硬件',
      message: blockingValidation.message,
      deterministic_product: artifact.deterministic_product,
      template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
      bom,
      partial_bom: bom,
      parameters: artifact.parameters,
      design_state: designState,
      preview_assets: artifact.preview_assets,
      checks: validation.checks,
      warnings: validation.warnings,
      questions: [
        '请增大盒体长度、宽度或高度后重新预审；模板 BOM 和硬件位置保持不变。',
      ],
      blocking_reason: 'template_layout_capacity_fail',
      generation_trace: generationTrace,
      source: 'deterministic_product_template',
    };
  }

  artifact.generation_trace = buildTemplateGenerationTrace(artifact, stage);
  artifact.design_state.generation_trace = artifact.generation_trace;
  return artifact;
}

export function collectTemplateProfiles() {
  const missing = [];
  const byId = new Map();
  for (const item of TEMPLATE_HARDWARE) {
    const profile = getHardwareProfile(item.hardware_id);
    if (!profile) {
      missing.push(item.hardware_id);
    } else {
      byId.set(item.hardware_id, profile);
    }
  }
  return {
    missing,
    byId,
    items: [...byId.values()],
  };
}

function buildMissingProfileResponse({ product, detection, body, missing }) {
  const intentAnalysis = {
    source: 'deterministic_product_template',
    status: 'needs_input',
    model_status: 'skipped',
    reason: detection?.reason || 'deterministic product template matched but required profiles are missing',
    confidence: detection?.confidence ?? 0.96,
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
  };
  const response = {
    status: 'needs_input',
    title: '植物养护系统缺少硬件资料',
    message: '已识别为行空板植物养护系统，但当前缺少模板所需的硬件资料，无法继续生成准确模型。',
    deterministic_product: summarizeTemplateProduct(product, detection),
    template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    partial_bom: TEMPLATE_HARDWARE
      .filter((item) => !missing.includes(item.hardware_id))
      .map((item) => ({ ...item, required_or_optional: 'required', profile_status: 'builtin' })),
    missing_hardware_requests: missing.map((hardwareId) => ({
      hardware_id: hardwareId,
      reason: 'deterministic_template_required_profile_missing',
      template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    })),
    questions: [
      '请先补齐上述硬件资料，再生成行空板植物养护系统模型。',
    ],
    blocking_reason: 'deterministic_template_missing_profiles',
    intent_analysis: intentAnalysis,
    conversation_route: intentAnalysis.conversation_route,
    revision_intent: intentAnalysis.revision_intent,
    source: 'deterministic_product_template',
  };
  response.generation_trace = {
    schema_version: 'generation_trace_v1',
    stage: 'needs_input',
    generated_at: new Date().toISOString(),
    deterministic_product: response.deterministic_product,
    template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    blocking_reason: response.blocking_reason,
    missing_profile_ids: missing,
    source: 'deterministic_product_template',
  };
  return response;
}

function buildBom(profilesById) {
  return TEMPLATE_HARDWARE.map((item) => {
    const profile = profilesById.get(item.hardware_id);
    return {
      hardware_id: item.hardware_id,
      name: profile?.name || item.hardware_id,
      role: item.role,
      category: profile?.category || 'hardware',
      hardware_system: profile?.hardware_system || 'common',
      quantity: item.quantity,
      required_or_optional: 'required',
      function: item.function,
      profile_status: 'builtin',
      template_placement: item.placement,
      mounting_intent: {
        preferred_surface: item.mount_surface,
        fixed_to_enclosure: item.mount_surface === 'base_floor' || item.mount_surface === 'lid_outer',
      },
    };
  });
}

function buildIntent({ product, body, bom }) {
  return {
    schema_version: '1.0',
    product_name: product?.product_name || '行空板植物养护系统',
    deterministic_product_id: product?.id || 'unihiker_plant_caregiver',
    template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    functions: [
      '主控计算和交互显示',
      '传感器采集和读数预处理',
      '土壤湿度检测',
      '继电器控制水泵通断',
      '植物养护执行',
      '电池供电',
    ],
    required_hardware_roles: bom.map((item) => ({
      role: item.role,
      category: item.category,
      function: item.function,
      label: item.name,
      hardware_id: item.hardware_id,
    })),
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    mounting_intents: [
      {
        hardware_id: 'battery_18650_holder',
        target_face: 'base_floor',
        user_phrase: '电池盒置于盒子内部底面。',
      },
      {
        hardware_id: 'unihiker_relay_module',
        target_face: 'base_floor',
        user_phrase: '继电器置于盒子内部，-Y 拨杆面贴近侧壁。',
      },
      {
        hardware_id: 'unihiker_sci_acquisition_module',
        target_face: 'lid_outer',
        user_phrase: 'SCI 采集模块置于盒子上盖表面。',
      },
      {
        hardware_id: 'unihiker_k10',
        target_face: 'external_right',
        user_phrase: 'K10 竖直插入 K10 扩展板中央插槽，仍位于盒子右侧旁边，不与盒体固定。',
      },
      {
        hardware_id: 'unihiker_k10_io_expansion_board',
        target_face: 'external_right',
        user_phrase: 'K10 扩展板保持当前位置，作为 K10 金手指插入的插槽底座，不与盒体固定。',
      },
      {
        hardware_id: 'unihiker_soil_moisture_sensor',
        target_face: 'external_scene',
        user_phrase: '土壤湿度传感器在花盆里，模型只显示在旁边。',
      },
      {
        hardware_id: 'unihiker_dc_water_pump',
        target_face: 'external_scene',
        user_phrase: '水泵在水缸里，模型只显示在旁边，并在盒体右侧预留电源线通道。',
      },
    ],
    enclosure_intent: {
      type: 'rectangular_box_with_lid',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'screw_lid',
      allowed_shape: 'rounded_rectangular_box',
      deterministic_model: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    },
    user_constraints: {
      raw_prompt: typeof body.prompt === 'string' ? body.prompt : '',
      size_mm: {},
      notes: [
        '植物养护系统使用已有设计方案生成。',
        'K10 金手指插入 K10 IO 扩展板插槽；土壤湿度传感器和水泵作为外置旁放件显示。',
      ],
    },
    unknowns: [],
  };
}

function buildTemplateParameters(body = {}) {
  const overrides = normalizeNumberMap(body.parameterOverrides || body.parameter_overrides);
  const parameters = { ...TEMPLATE_PARAMETERS };
  const aliases = {
    outer_length_x: 'box_length_x',
    outer_width_y: 'box_width_y',
    outer_height_z: 'box_height_z',
  };
  for (const [key, value] of Object.entries(overrides)) {
    const targetKey = aliases[key] || key;
    if (!['box_length_x', 'box_width_y', 'box_height_z'].includes(targetKey) || value <= 0) continue;
    parameters[targetKey] = value;
  }
  parameters.inner_length_x = round1(parameters.box_length_x - parameters.wall_thickness * 2);
  parameters.inner_width_y = round1(parameters.box_width_y - parameters.wall_thickness * 2);
  parameters.inner_height_z = round1(parameters.box_height_z - parameters.floor_thickness - parameters.lid_thickness);
  return parameters;
}

function projectDefaultParametersFromBody(body = {}) {
  const current = body.currentDesignState || body.current_design_state || {};
  const existing = current.project_default_parameters || current.default_parameters || {};
  return isPlainObject(existing) && Object.keys(existing).length ? existing : null;
}

function buildEnclosure(parameters = TEMPLATE_PARAMETERS) {
  const wall = parameters.wall_thickness;
  const floor = parameters.floor_thickness;
  const lid = parameters.lid_thickness;
  const outer = {
    length_x: round1(parameters.box_length_x),
    width_y: round1(parameters.box_width_y),
    height_z: round1(parameters.box_height_z),
  };
  const inner = {
    length_x: round1(Math.max(1, outer.length_x - wall * 2)),
    width_y: round1(Math.max(1, outer.width_y - wall * 2)),
    height_z: round1(Math.max(1, outer.height_z - floor - lid)),
  };
  return {
    outer_box_size: outer,
    inner_box_size: inner,
    wall_thickness: wall,
    floor_thickness: floor,
    lid_thickness: lid,
    lid_lip_height: parameters.lid_lip_height,
    lid_clearance: parameters.lid_clearance,
    corner_radius: parameters.corner_radius,
    screw_bosses: [
      { x: -outer.length_x / 2 + 12, y: -outer.width_y / 2 + 12 },
      { x: outer.length_x / 2 - 12, y: -outer.width_y / 2 + 12 },
      { x: -outer.length_x / 2 + 12, y: outer.width_y / 2 - 12 },
      { x: outer.length_x / 2 - 12, y: outer.width_y / 2 - 12 },
    ],
  };
}

function buildPlantCareParameterGroups(parameters, enclosure, layoutPlan) {
  const groups = buildParameterGroups(parameters, enclosure, layoutPlan);
  groups.plant_care_box = {
    box_length_x: enclosure.outer_box_size.length_x,
    box_width_y: enclosure.outer_box_size.width_y,
    box_height_z: enclosure.outer_box_size.height_z,
  };
  return groups;
}

function buildLayoutPlan({ profiles, enclosure }) {
  const outer = enclosure.outer_box_size;
  const k10ExternalX = round1(outer.length_x / 2 + 50.6);
  const soilSensorY = round1(-outer.width_y / 2 - 38.6);
  const waterPumpY = round1(-outer.width_y / 2 - 40.6);
  const transforms = [
    hardwareTransform({
      profile: profiles.get('battery_18650_holder'),
      center: { x: 0, y: 18, z: 13 },
      mount_surface: 'base_floor',
      target_face: 'base_floor',
      placement: 'inside_base_floor',
      fixed_to_enclosure: true,
    }),
    hardwareTransform({
      profile: profiles.get('unihiker_relay_module'),
      center: { x: 0, y: -31, z: 6.9 },
      mount_surface: 'base_floor',
      target_face: 'base_floor',
      placement: 'inside_base_floor_switch_to_back_wall',
      fixed_to_enclosure: true,
    }),
    hardwareTransform({
      profile: profiles.get('unihiker_sci_acquisition_module'),
      center: { x: -24, y: 0, z: enclosure.outer_box_size.height_z + 3.65 },
      mount_surface: 'lid_outer',
      target_face: 'lid_outer',
      placement: 'lid_outer_surface',
      fixed_to_enclosure: true,
    }),
    hardwareTransform({
      profile: profiles.get('unihiker_k10_io_expansion_board'),
      center: { x: k10ExternalX, y: -14, z: 14 },
      mount_surface: 'external_right',
      target_face: 'external_right',
      placement: 'external_right_side_not_fixed',
      fixed_to_enclosure: false,
    }),
    hardwareTransform({
      profile: profiles.get('unihiker_k10'),
      center: { x: k10ExternalX, y: -13.2, z: 59.75 },
      mount_surface: 'external_right',
      target_face: 'external_right',
      placement: 'external_right_inserted_into_k10_io_slot',
      fixed_to_enclosure: false,
    }),
    hardwareTransform({
      profile: profiles.get('unihiker_soil_moisture_sensor'),
      center: { x: -42, y: soilSensorY, z: 8 },
      mount_surface: 'external_scene',
      target_face: 'external_scene',
      placement: 'external_probe_beside_box_not_connected',
      fixed_to_enclosure: false,
    }),
    hardwareTransform({
      profile: profiles.get('unihiker_dc_water_pump'),
      center: { x: 44, y: waterPumpY, z: 17.5 },
      mount_surface: 'external_scene',
      target_face: 'external_scene',
      placement: 'external_pump_beside_box_not_connected',
      fixed_to_enclosure: false,
    }),
  ];

  return {
    strategy: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    hardware_transforms: transforms,
    opening_transforms: [
      {
        id: 'relay_switch_lever_slot',
        hardware_id: 'unihiker_relay_module',
        type: 'rectangular_cutout',
        face: 'back',
        basis: 'relay switch lever clearance',
        center: { x: 0, y: round1(-outer.width_y / 2), z: 8 },
        source_center_mm: { x: 0, y: -13, z: 2 },
        size_mm: { width: 8, height: 3 },
        clearance_mm: 0.5,
        projected_from_hardware: true,
      },
      {
        id: 'water_pump_power_cable_channel',
        hardware_id: 'unihiker_dc_water_pump',
        type: 'round_hole',
        face: 'right',
        basis: 'pump power cable channel',
        center: { x: round1(outer.length_x / 2), y: 24, z: 18 },
        source_center_mm: { x: 0, y: 0, z: 0 },
        size_mm: { diameter: 12 },
        diameter_mm: 12,
        clearance_mm: 0.8,
        projected_from_hardware: true,
      },
    ],
    mounting_hole_transforms: [
      ...mountingHolesForProfile({
        profile: profiles.get('unihiker_sci_acquisition_module'),
        hardwareCenter: { x: -24, y: 0, z: enclosure.outer_box_size.height_z + 3.65 },
        face: 'top',
        mount_surface: 'lid_outer',
      }),
      ...mountingHolesForProfile({
        profile: profiles.get('unihiker_relay_module'),
        hardwareCenter: { x: 0, y: -31, z: 6.9 },
        face: 'bottom',
        mount_surface: 'base_floor',
      }),
    ],
    mounting_transforms: [
      {
        id: 'battery_holder_floor_retainer',
        hardware_id: 'battery_18650_holder',
        type: 'floor_retainer_reference',
        role: 'retainer',
        anchor_face: 'bottom',
        mount_surface: 'base_floor',
        center: { x: 0, y: 18, z: 1.5 },
        size_mm: { length_x: 82, width_y: 25, height_z: 3 },
        clearance_mm: 1,
        engagement_mm: 3,
      },
    ],
    notes: [
      'K10 金手指插入 K10 IO 扩展板插槽，两者位于盒体右侧且不与盒体固定。',
      '土壤湿度传感器和水泵放在盒体旁边展示，不建立线缆和水管模型。',
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
      length_x: Number(profile.dimensions_mm?.length_x || profile.dimensions_mm?.width || 10),
      width_y: Number(profile.dimensions_mm?.width_y || profile.dimensions_mm?.depth || 10),
      height_z: Number(profile.dimensions_mm?.height_z || profile.dimensions_mm?.height || 5),
    },
    dimensions_mm: profile.dimensions_mm || {},
    cad_reference: profile.cad_reference || {},
    openings: Array.isArray(profile.opening) ? profile.opening : [],
    keepouts: Array.isArray(profile.keepouts) ? profile.keepouts : [],
    mount_surface,
    target_face,
    placement,
    fixed_to_enclosure,
    layout_rotation_deg: 0,
  };
}

function mountingHolesForProfile({ profile, hardwareCenter, face, mount_surface }) {
  const holes = Array.isArray(profile?.mounting?.holes) ? profile.mounting.holes : [];
  return holes.map((hole) => ({
    id: `${profile.id}_${hole.id}`,
    hardware_id: profile.id,
    type: 'mounting_screw_hole',
    role: 'mounting_hole',
    face,
    mount_surface,
    center: {
      x: round1(hardwareCenter.x + Number(hole.x || 0)),
      y: round1(hardwareCenter.y + Number(hole.y || 0)),
      z: hardwareCenter.z,
    },
    source_center_mm: {
      x: Number(hole.x || 0),
      y: Number(hole.y || 0),
      z: 0,
    },
    diameter_mm: Number(hole.diameter_mm || 3),
    fastener: hole.fastener || 'M3',
    source: 'deterministic_template',
    size_mm: { diameter: Number(hole.diameter_mm || 3) },
  }));
}

function buildTemplateValidation({ profiles, layoutPlan, enclosure }) {
  const ids = new Set(profiles.map((item) => item.id));
  const requiredIds = TEMPLATE_HARDWARE.map((item) => item.hardware_id);
  const missing = requiredIds.filter((id) => !ids.has(id));
  const codeCheck = {
    id: 'cadquery_code_static',
    label: 'CadQuery 代码检查',
    status: 'pass',
    message: '模型代码由固定设计模块生成，并包含完整的模型输出入口。',
  };
  const capacityCheck = buildTemplateLayoutCapacityCheck({ enclosure, layoutPlan });
  const checks = [
    {
      id: 'source_deterministic',
      label: '生成来源',
      status: 'pass',
      message: '模型由后端确定性模板库生成，不来自 LLM 直接 CAD 代码。',
    },
    {
      id: 'template_required_profiles',
      label: '模板所需硬件资料',
      status: missing.length ? 'fail' : 'pass',
      message: missing.length
        ? `缺少以下硬件资料：${missing.join('、')}`
        : '植物养护系统所需的硬件资料均已齐全。',
      details: { required_profile_ids: requiredIds, missing_profile_ids: missing },
    },
    {
      id: 'template_layout_contract',
      label: '植物养护系统布局',
      status: 'pass',
      message: '盒内、上盖和盒外硬件均已按照植物养护系统的固定布局放置。',
      details: {
        internal_ids: ['battery_18650_holder', 'unihiker_relay_module'],
        lid_outer_ids: ['unihiker_sci_acquisition_module'],
        external_ids: ['unihiker_k10', 'unihiker_k10_io_expansion_board', 'unihiker_soil_moisture_sensor', 'unihiker_dc_water_pump'],
      },
    },
    capacityCheck,
    {
      id: 'template_openings',
      label: '模板开孔',
      status: 'pass',
      message: '模型已包含继电器拨杆开口和右侧直径 12mm 的水泵电源线通道。',
      details: {
        opening_ids: layoutPlan.opening_transforms.map((item) => item.id),
      },
    },
    codeCheck,
    {
      id: 'cadquery_runtime',
      label: 'CadQuery 运行环境',
      status: 'pending',
      message: '模型将在可用的 CadQuery 环境中通过正常导出流程完成构建。',
    },
  ];
  return {
    checks,
    warnings: [],
    validation_context: {
      aabb_model: 'deterministic_template_mixed_internal_external_hardware',
      mesh_validation: 'pending_missing_cadquery',
      external_hardware_not_checked_against_inner_cavity: true,
    },
  };
}

function buildTemplateLayoutCapacityCheck({ enclosure = {}, layoutPlan = {} } = {}) {
  const outer = enclosure.outer_box_size || {};
  const inner = enclosure.inner_box_size || {};
  const wall = Number(enclosure.wall_thickness || 0);
  const floor = Number(enclosure.floor_thickness || 0);
  const lid = Number(enclosure.lid_thickness || 0);
  const margin = 0.25;
  const failures = [];
  const boundsFor = (center = {}, size = {}) => ({
    min_x: Number(center.x || 0) - Number(size.length_x || size.width || 0) / 2,
    max_x: Number(center.x || 0) + Number(size.length_x || size.width || 0) / 2,
    min_y: Number(center.y || 0) - Number(size.width_y || size.depth || size.width || 0) / 2,
    max_y: Number(center.y || 0) + Number(size.width_y || size.depth || size.width || 0) / 2,
    min_z: Number(center.z || 0) - Number(size.height_z || size.height || 0) / 2,
    max_z: Number(center.z || 0) + Number(size.height_z || size.height || 0) / 2,
  });
  const innerHalfX = Number(inner.length_x || 0) / 2;
  const innerHalfY = Number(inner.width_y || 0) / 2;
  const outerHalfX = Number(outer.length_x || 0) / 2 - wall;
  const outerHalfY = Number(outer.width_y || 0) / 2 - wall;
  const baseTop = Number(outer.height_z || 0) - lid;

  for (const item of layoutPlan.hardware_transforms || []) {
    const bounds = boundsFor(item.center, item.bounding_box || item.dimensions_mm || {});
    if (item.mount_surface === 'base_floor') {
      if (bounds.min_x < -innerHalfX + margin || bounds.max_x > innerHalfX - margin
        || bounds.min_y < -innerHalfY + margin || bounds.max_y > innerHalfY - margin
        || bounds.min_z < floor - margin || bounds.max_z > baseTop + margin) {
        failures.push({
          hardware_id: item.hardware_id,
          name: item.name,
          mount_surface: item.mount_surface,
          bounds,
          allowed: {
            min_x: -innerHalfX + margin,
            max_x: innerHalfX - margin,
            min_y: -innerHalfY + margin,
            max_y: innerHalfY - margin,
            min_z: floor - margin,
            max_z: baseTop + margin,
          },
        });
      }
    } else if (item.mount_surface === 'lid_outer'
      && (bounds.min_x < -outerHalfX + margin || bounds.max_x > outerHalfX - margin
        || bounds.min_y < -outerHalfY + margin || bounds.max_y > outerHalfY - margin)) {
      failures.push({
        hardware_id: item.hardware_id,
        name: item.name,
        mount_surface: item.mount_surface,
        bounds,
        allowed: {
          min_x: -outerHalfX + margin,
          max_x: outerHalfX - margin,
          min_y: -outerHalfY + margin,
          max_y: outerHalfY - margin,
        },
      });
    }
  }

  return {
    id: 'template_layout_capacity',
    label: '模板盒体容量与包围盒',
    status: failures.length ? 'fail' : 'pass',
    message: failures.length
      ? `当前盒体尺寸不足以容纳模板固定硬件：${failures.map((item) => item.name || item.hardware_id).join('、')}。请增大盒体尺寸后再生成。`
      : '模板盒体尺寸可以容纳盒内和上盖外侧固定硬件，盒外硬件按模板旁置展示。',
    details: {
      failures,
      external_hardware_not_checked: true,
      clearance_margin_mm: margin,
    },
  };
}

function buildTemplateGenerationTrace(artifact, stage = 'artifact') {
  const checks = Array.isArray(artifact.checks) ? artifact.checks : [];
  const isConfirmation = stage === 'confirmation';
  return {
    schema_version: 'generation_trace_v1',
    stage,
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
    },
    layout: {
      hardware_count: artifact.design_state.layout_plan.hardware_transforms.length,
      opening_count: artifact.design_state.layout_plan.opening_transforms.length,
      mounting_hole_count: artifact.design_state.layout_plan.mounting_hole_transforms.length,
      external_hardware_count: artifact.design_state.layout_plan.hardware_transforms
        .filter((item) => String(item.mount_surface).startsWith('external')).length,
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
      ...(isConfirmation ? ['generic_cad_generation', 'cadquery_build_and_export'] : ['generic_cad_generation']),
    ],
    source: 'deterministic_product_template',
  };
}

function summarizeTemplateProduct(product, detection) {
  return {
    id: product?.id || 'unihiker_plant_caregiver',
    name: product?.name || '植物看护仪',
    product_name: product?.product_name || '行空板植物养护系统',
    hardware_system: product?.hardware_system || 'unihiker',
    status: product?.status || 'available',
    model_status: product?.model_status || 'implemented',
    template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
    description: product?.description || '',
    matched: true,
    source: detection?.source || 'deterministic_product_detector',
    reason: detection?.reason || '',
    confidence: detection?.confidence ?? 0.96,
  };
}

function buildCadQueryCode({ profiles, parameters, enclosure, layoutPlan }) {
  const profileData = {};
  for (const item of TEMPLATE_HARDWARE) {
    const profile = profiles.get(item.hardware_id);
    profileData[item.hardware_id] = {
      name: profile.name,
      dimensions_mm: profile.dimensions_mm,
    };
  }
  const jsonData = JSON.stringify(profileData, null, 2);
  const outer = enclosure.outer_box_size;
  const inner = enclosure.inner_box_size;
  const baseHeight = round1(outer.height_z - parameters.lid_thickness);
  const innerCutHeight = round1(baseHeight - parameters.floor_thickness + 2);
  const bossHeight = round1(baseHeight - parameters.floor_thickness);
  const bossX = round1(outer.length_x / 2 - 12);
  const bossY = round1(outer.width_y / 2 - 12);
  const relaySlotY = round1(-outer.width_y / 2 - 0.1);
  const transformById = new Map(layoutPlan.hardware_transforms.map((item) => [item.hardware_id, item]));
  const k10ExternalX = transformById.get('unihiker_k10')?.center?.x ?? 128;
  const soilSensorY = transformById.get('unihiker_soil_moisture_sensor')?.center?.y ?? -86;
  const waterPumpY = transformById.get('unihiker_dc_water_pump')?.center?.y ?? -88;
  return `# ZW-CAD-intent deterministic template: ${UNIHIKER_SMART_WATERING_TEMPLATE_ID}
# Backend template library model, not LLM-authored CAD code.
# Units: millimeters. This single file is CQ-editor ready.

import cadquery as cq

hardware_profiles_json = ${JSON.stringify(jsonData)}


# -------------------------
# Shared helpers
# -------------------------
def rounded_box(length, width, height, radius, centered=(True, True, False)):
    part = cq.Workplane("XY").box(length, width, height, centered=centered)
    if radius > 0:
        try:
            part = part.edges("|Z").fillet(radius)
        except Exception:
            pass
    return part


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
        .circle(diameter / 2.0)
        .extrude(height)
        .translate((center_x, center_y, z_min))
    )


def make_centered_box(size, center):
    return cq.Workplane("XY").box(size[0], size[1], size[2], centered=(True, True, True)).translate(center)


def make_cylinder_z(diameter, height, center):
    return cq.Workplane("XY").circle(diameter / 2.0).extrude(height).translate(center)


def make_mount_hole_cutter(x, y, diameter, height):
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(diameter / 2.0)
        .extrude(height)
        .translate((0, 0, -0.3))
    )


# -------------------------
# Hardware builders copied from the hardware model library
# -------------------------
def make_battery_18650_holder():
    holder_length = 77.0
    holder_width = 21.0
    holder_height = 21.0
    base_thickness = 3.0
    rail_thickness = 2.0
    rail_height = 6.0
    end_block_length = 5.0
    battery_diameter = 18.0
    battery_length = 65.0
    contact_diameter = 8.0
    contact_thickness = 1.0

    base = rounded_box(holder_length, holder_width, base_thickness, 1.0)
    side_rail_y = holder_width / 2.0 - rail_thickness / 2.0
    left_rail = (
        cq.Workplane("XY")
        .box(holder_length, rail_thickness, rail_height, centered=(True, True, False))
        .translate((0, side_rail_y, base_thickness))
    )
    right_rail = left_rail.translate((0, -2.0 * side_rail_y, 0))
    end_block_x = holder_length / 2.0 - end_block_length / 2.0
    plus_end = (
        cq.Workplane("XY")
        .box(end_block_length, holder_width, holder_height, centered=(True, True, False))
        .translate((end_block_x, 0, 0))
    )
    minus_end = plus_end.translate((-2.0 * end_block_x, 0, 0))
    battery_cell = (
        cq.Workplane("YZ")
        .circle(battery_diameter / 2.0)
        .extrude(battery_length)
        .translate((-battery_length / 2.0, 0, base_thickness + battery_diameter / 2.0))
    )
    plus_contact = (
        cq.Workplane("YZ")
        .circle(contact_diameter / 2.0)
        .extrude(contact_thickness)
        .translate((holder_length / 2.0 - end_block_length - contact_thickness, 0, base_thickness + battery_diameter / 2.0))
    )
    minus_contact = (
        cq.Workplane("YZ")
        .circle(contact_diameter / 2.0)
        .extrude(contact_thickness)
        .translate((-holder_length / 2.0 + end_block_length, 0, base_thickness + battery_diameter / 2.0))
    )
    return (
        base
        .union(left_rail)
        .union(right_rail)
        .union(plus_end)
        .union(minus_end)
        .union(battery_cell)
        .union(plus_contact)
        .union(minus_contact)
    )


def make_unihiker_relay_module():
    pcb_length = 37.0
    pcb_width = 26.0
    pcb_thickness = 1.0
    pcb_corner_radius = 2.0
    mount_hole_diameter = 3.0
    mount_hole_edge_offset = 4.8
    mount_hole_x = pcb_length / 2.0 - mount_hole_edge_offset
    mount_hole_y = pcb_width / 2.0 - mount_hole_edge_offset
    signal_connector_length_x = 12.0
    signal_connector_width_y = 6.0
    signal_connector_height_z = 5.7
    signal_connector_center_y = pcb_width / 2.0 - signal_connector_width_y / 2.0
    signal_connector_center_z = pcb_thickness + signal_connector_height_z / 2.0
    power_terminal_length_x = 12.0
    power_terminal_width_y = 10.0
    power_terminal_height_z = 8.0
    power_terminal_center_x = pcb_length / 2.0 - power_terminal_length_x / 2.0
    power_terminal_center_z = pcb_thickness + power_terminal_height_z / 2.0
    switch_length_x = 7.0
    switch_width_y = 2.0
    switch_height_z = 1.5
    switch_center_y = -pcb_width / 2.0 + switch_width_y / 2.0
    switch_center_z = pcb_thickness + switch_height_z / 2.0

    pcb = rounded_box(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius)
    for hx, hy in [
        (-mount_hole_x, -mount_hole_y),
        (-mount_hole_x, mount_hole_y),
        (mount_hole_x, -mount_hole_y),
        (mount_hole_x, mount_hole_y),
    ]:
        pcb = pcb.cut(make_mount_hole_cutter(hx, hy, mount_hole_diameter, pcb_thickness + 0.6))

    signal_connector = (
        cq.Workplane("XY")
        .box(signal_connector_length_x, signal_connector_width_y, signal_connector_height_z, centered=(True, True, True))
        .translate((0, signal_connector_center_y, signal_connector_center_z))
    )
    power_terminal_plus_x = (
        cq.Workplane("XY")
        .box(power_terminal_length_x, power_terminal_width_y, power_terminal_height_z, centered=(True, True, True))
        .translate((power_terminal_center_x, 0, power_terminal_center_z))
    )
    power_terminal_minus_x = power_terminal_plus_x.translate((-2.0 * power_terminal_center_x, 0, 0))
    switch_body = (
        cq.Workplane("XY")
        .box(switch_length_x, switch_width_y, switch_height_z, centered=(True, True, True))
        .translate((0, switch_center_y, switch_center_z))
    )
    lever_length_x = 3.0
    lever_width_y = 1.2
    lever_height_z = 2.0
    lever = (
        cq.Workplane("XY")
        .box(lever_length_x, lever_width_y, lever_height_z, centered=(True, True, True))
        .translate((0, -pcb_width / 2.0 - lever_width_y / 2.0, pcb_thickness + lever_height_z / 2.0))
    )
    return (
        pcb
        .union(signal_connector)
        .union(power_terminal_plus_x)
        .union(power_terminal_minus_x)
        .union(switch_body)
        .union(lever)
    )


def make_unihiker_sci_acquisition_module():
    pcb_length = 62.0
    pcb_width = 52.0
    pcb_thickness = 1.6
    pcb_corner_radius = 2.0
    mount_hole_diameter = 3.0
    mount_hole_edge_offset = 2.8
    mount_hole_x = pcb_length / 2.0 - mount_hole_edge_offset
    mount_hole_y = pcb_width / 2.0 - mount_hole_edge_offset
    connector_length_x = 6.0
    connector_width_y = 12.0
    connector_height_z = 5.7
    connector_gap_y = 1.5
    connector_center_z = pcb_thickness + connector_height_z / 2.0
    plus_x_connector_center_x = pcb_length / 2.0 - connector_length_x / 2.0
    minus_x_connector_center_x = -pcb_length / 2.0 + connector_length_x / 2.0
    minus_x_connector_pitch_y = connector_width_y + connector_gap_y
    minus_x_connector_centers_y = [-minus_x_connector_pitch_y, 0.0, minus_x_connector_pitch_y]
    display_frame_length_x = 37.0
    display_frame_width_y = 24.0
    display_frame_height_z = 2.0
    display_frame_center_z = pcb_thickness + display_frame_height_z / 2.0
    display_area_length_x = 30.0
    display_area_width_y = 18.0
    display_area_height_z = 0.3
    display_area_center_y = display_frame_width_y / 2.0 - 2.0 - display_area_width_y / 2.0
    display_area_center_z = pcb_thickness + display_frame_height_z + display_area_height_z / 2.0

    pcb = rounded_box(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius)
    for hx, hy in [
        (-mount_hole_x, -mount_hole_y),
        (-mount_hole_x, mount_hole_y),
        (mount_hole_x, -mount_hole_y),
        (mount_hole_x, mount_hole_y),
    ]:
        pcb = pcb.cut(make_mount_hole_cutter(hx, hy, mount_hole_diameter, pcb_thickness + 0.6))

    def local_box(length, width, height, center_x, center_y, center_z):
        return (
            cq.Workplane("XY")
            .box(length, width, height, centered=(True, True, True))
            .translate((center_x, center_y, center_z))
        )

    result = pcb.union(local_box(connector_length_x, connector_width_y, connector_height_z, plus_x_connector_center_x, 0, connector_center_z))
    for cy in minus_x_connector_centers_y:
        result = result.union(local_box(connector_length_x, connector_width_y, connector_height_z, minus_x_connector_center_x, cy, connector_center_z))
    result = result.union(local_box(display_frame_length_x, display_frame_width_y, display_frame_height_z, 0, 0, display_frame_center_z))
    result = result.union(local_box(display_area_length_x, display_area_width_y, display_area_height_z, 0, display_area_center_y, display_area_center_z))
    return result


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

    pcb = rounded_plate(pcb_length, pcb_width, pcb_thickness, pcb_corner_radius, 0)
    bottom_plate = rounded_plate(pcb_length, pcb_width, bottom_plate_thickness, pcb_corner_radius, -(board_gap + bottom_plate_thickness))
    standoff_x = pcb_length / 2.0 - standoff_edge_offset
    standoff_y = pcb_width / 2.0 - standoff_edge_offset
    standoffs = None
    for x in (-standoff_x, standoff_x):
        for y in (-standoff_y, standoff_y):
            post = cq.Workplane("XY").circle(standoff_diameter / 2.0).extrude(standoff_height).translate((x, y, -board_gap))
            standoffs = post if standoffs is None else standoffs.union(post)
    switch_body = (
        cq.Workplane("XY")
        .box(switch_length, switch_width, switch_height, centered=(True, True, False))
        .translate((switch_center_x, switch_center_y, pcb_thickness))
    )
    switch_lever = (
        cq.Workplane("XY")
        .box(lever_size, lever_size, lever_height, centered=(True, True, False))
        .translate((switch_center_x, switch_center_y, pcb_thickness + switch_height))
    )
    slot_body = cq.Workplane("XY").box(slot_length, slot_width, slot_height, centered=(True, True, False))
    slot_cutout = (
        cq.Workplane("XY")
        .box(slot_cutout_length, slot_cutout_width, slot_height + 0.6, centered=(True, True, False))
        .translate((0, 0, -0.3))
    )
    k10_slot = slot_body.cut(slot_cutout).translate((0, 0, pcb_thickness))
    return pcb.union(bottom_plate).union(standoffs).union(switch_body).union(switch_lever).union(k10_slot)


def make_unihiker_soil_moisture_sensor():
    pcb_length = 60.0
    pcb_width = 20.0
    pcb_thickness = 1.6
    slot_length_x = 40.0
    slot_width_y = 7.0
    slot_round_diameter = 7.0
    tip_length_x = 7.0
    tip_round_radius = 1.0
    right_corner_radius = 1.0
    connector_length_x = 6.0
    connector_width_y = 10.0
    connector_height_z = 5.7
    cut_extra_z = 0.6

    pcb_half_length = pcb_length / 2.0
    pcb_half_width = pcb_width / 2.0
    slot_radius = slot_round_diameter / 2.0
    slot_start_x = -pcb_half_length
    slot_end_x = slot_start_x + slot_length_x
    slot_arc_center_x = slot_end_x - slot_radius
    slot_rect_length_x = slot_arc_center_x - slot_start_x
    slot_rect_center_x = slot_start_x + slot_rect_length_x / 2.0
    tip_base_x = -pcb_half_length + tip_length_x
    top_tip_y = (slot_width_y / 2.0 + pcb_half_width) / 2.0
    bottom_tip_y = -top_tip_y
    connector_center_x = pcb_half_length - connector_length_x / 2.0
    connector_center_z = pcb_thickness + connector_height_z / 2.0

    pcb = cq.Workplane("XY").box(pcb_length, pcb_width, pcb_thickness, centered=(True, True, False))
    slot_rect_cut = (
        cq.Workplane("XY")
        .box(slot_rect_length_x, slot_width_y, pcb_thickness + cut_extra_z, centered=(True, True, False))
        .translate((slot_rect_center_x, 0, -cut_extra_z / 2.0))
    )
    slot_round_cut = cq.Workplane("XY").circle(slot_radius).extrude(pcb_thickness + cut_extra_z).translate((slot_arc_center_x, 0, -cut_extra_z / 2.0))
    pcb = pcb.cut(slot_rect_cut.union(slot_round_cut))
    top_outer_cut = (
        cq.Workplane("XY")
        .polyline([(-pcb_half_length, pcb_half_width), (-pcb_half_length, top_tip_y), (tip_base_x, pcb_half_width)])
        .close()
        .extrude(pcb_thickness + cut_extra_z)
        .translate((0, 0, -cut_extra_z / 2.0))
    )
    top_inner_cut = (
        cq.Workplane("XY")
        .polyline([(-pcb_half_length, slot_width_y / 2.0), (-pcb_half_length, top_tip_y), (tip_base_x, slot_width_y / 2.0)])
        .close()
        .extrude(pcb_thickness + cut_extra_z)
        .translate((0, 0, -cut_extra_z / 2.0))
    )
    bottom_inner_cut = (
        cq.Workplane("XY")
        .polyline([(-pcb_half_length, -slot_width_y / 2.0), (-pcb_half_length, bottom_tip_y), (tip_base_x, -slot_width_y / 2.0)])
        .close()
        .extrude(pcb_thickness + cut_extra_z)
        .translate((0, 0, -cut_extra_z / 2.0))
    )
    bottom_outer_cut = (
        cq.Workplane("XY")
        .polyline([(-pcb_half_length, -pcb_half_width), (-pcb_half_length, bottom_tip_y), (tip_base_x, -pcb_half_width)])
        .close()
        .extrude(pcb_thickness + cut_extra_z)
        .translate((0, 0, -cut_extra_z / 2.0))
    )
    pcb = pcb.cut(top_outer_cut).cut(top_inner_cut).cut(bottom_inner_cut).cut(bottom_outer_cut)
    pcb = pcb.edges("|Z and >X").fillet(right_corner_radius)
    pcb = pcb.edges("|Z and <X").fillet(tip_round_radius)
    connector = (
        cq.Workplane("XY")
        .box(connector_length_x, connector_width_y, connector_height_z, centered=(True, True, True))
        .translate((connector_center_x, 0, connector_center_z))
    )
    return pcb.union(connector)


def make_unihiker_dc_water_pump():
    body_diameter = 25.0
    body_radius = body_diameter / 2.0
    body_length = 45.0
    inlet_diameter = 5.0
    inlet_radius = inlet_diameter / 2.0
    inlet_length = 10.0
    outlet_diameter = 5.0
    outlet_radius = outlet_diameter / 2.0
    outlet_length = 10.0
    outlet_center_x = body_length / 2.0 - 7.5
    outlet_center_y = 0.0
    outlet_embed_depth = 1.0
    wire_bump_diameter = 2.0
    wire_bump_radius = wire_bump_diameter / 2.0
    wire_bump_height = 0.5

    body = cq.Workplane("YZ").circle(body_radius).extrude(body_length).translate((-body_length / 2.0, 0, 0))
    inlet = cq.Workplane("YZ").circle(inlet_radius).extrude(inlet_length).translate((body_length / 2.0, 0, 0))
    outlet = (
        cq.Workplane("XY")
        .center(outlet_center_x, outlet_center_y)
        .circle(outlet_radius)
        .extrude(outlet_length + outlet_embed_depth)
        .translate((0, 0, body_radius - outlet_embed_depth))
    )
    wire_bump = cq.Workplane("YZ").circle(wire_bump_radius).extrude(wire_bump_height).translate((-body_length / 2.0 - wire_bump_height, 0, 0))
    return body.union(inlet).union(outlet).union(wire_bump)


# -------------------------
# Plant care enclosure and assembly
# main rectangular box with lid
# -------------------------
outer_length = ${pythonNumber(outer.length_x)}
outer_width = ${pythonNumber(outer.width_y)}
outer_height = ${pythonNumber(outer.height_z)}
inner_length = ${pythonNumber(inner.length_x)}
inner_width = ${pythonNumber(inner.width_y)}
inner_height = ${pythonNumber(inner.height_z)}
base_height = ${pythonNumber(baseHeight)}
lid_thickness = ${pythonNumber(parameters.lid_thickness)}
lid_lip_height = ${pythonNumber(parameters.lid_lip_height)}
wall_thickness = ${pythonNumber(parameters.wall_thickness)}
floor_thickness = ${pythonNumber(parameters.floor_thickness)}
corner_radius = ${pythonNumber(parameters.corner_radius)}


def build_hollow_base():
    base_outer = rounded_box(outer_length, outer_width, base_height, corner_radius)
    inner_cut = (
        cq.Workplane("XY")
        .workplane(offset=floor_thickness)
        .box(inner_length, inner_width, ${pythonNumber(innerCutHeight)}, centered=(True, True, False))
    )
    return base_outer.cut(inner_cut)


def build_lid():
    lid = rounded_box(outer_length, outer_width, lid_thickness, corner_radius)
    return lid.translate((0, 0, base_height + lid_lip_height))


def apply_openings(base_part):
    # relay switch opening on the back side and pump power channel on the right side
    relay_switch_slot = make_centered_box((8.0, 4.0, 3.0), (0.0, ${pythonNumber(relaySlotY)}, 8.0))
    pump_power_channel = (
        cq.Workplane("YZ")
        .center(24.0, 18.0)
        .circle(6.0)
        .extrude(6.0)
        .translate((outer_length / 2.0 - 3.0, 0, 0))
    )
    return base_part.cut(relay_switch_slot).cut(pump_power_channel)


def apply_screw_bosses(base_part):
    for x in (-${pythonNumber(bossX)}, ${pythonNumber(bossX)}):
        for y in (-${pythonNumber(bossY)}, ${pythonNumber(bossY)}):
            boss_height = ${pythonNumber(bossHeight)}
            screw_hole_height = boss_height + 2.0
            boss = make_cylinder_z(8.0, boss_height, (x, y, floor_thickness)).cut(make_cylinder_z(2.2, screw_hole_height, (x, y, floor_thickness - 1.0)))
            base_part = base_part.union(boss)
    return base_part


def apply_lid_screw_holes(lid_part):
    for x in (-${pythonNumber(bossX)}, ${pythonNumber(bossX)}):
        for y in (-${pythonNumber(bossY)}, ${pythonNumber(bossY)}):
            lid_part = lid_part.cut(make_cylinder_z(2.4, 6.0, (x, y, base_height + lid_lip_height - 0.5)))
    for dx in (-28.2, 28.2):
        for dy in (-23.2, 23.2):
            lid_part = lid_part.cut(make_cylinder_z(3.0, 6.0, (-24.0 + dx, dy, base_height + lid_lip_height - 0.5)))
    return lid_part


def build_mounts():
    retainer = make_centered_box((82.0, 25.0, 3.0), (0.0, 18.0, 1.5))
    battery_clearance = make_centered_box((78.0, 21.0, 4.0), (0.0, 18.0, 2.0))
    return [retainer.cut(battery_clearance)]


def apply_mounts(base_part, lid_part):
    for mount in build_mounts():
        base_part = base_part.union(mount)
    return base_part, lid_part


def build_hardware_references():
    # internal modules: battery holder and relay
    battery_holder = make_battery_18650_holder().translate((0.0, 18.0, 2.5))
    relay_module = make_unihiker_relay_module().translate((0.0, -31.0, 2.9))

    # lid-mounted SCI acquisition module
    sci_module = make_unihiker_sci_acquisition_module().translate((-24.0, 0.0, base_height + lid_lip_height + lid_thickness))

    # external right-side K10 and IO expansion board, shown but not fixed
    # K10 gold fingers are inserted into the K10 IO expansion board slot.
    k10_io_board = make_unihiker_k10_io_expansion_board().translate((${pythonNumber(k10ExternalX)}, -14.0, 7.95))
    k10_board = (
        make_unihiker_k10()
        .rotate((0, 0, 0), (0, 1, 0), 90)
        .rotate((0, 0, 0), (0, 0, 1), -90)
        .translate((${pythonNumber(k10ExternalX)}, -13.2, 59.75))
    )

    # beside-box external probe and pump, no cables or pipes modeled
    soil_sensor = make_unihiker_soil_moisture_sensor().translate((-42.0, ${pythonNumber(soilSensorY)}, 4.35))
    water_pump = make_unihiker_dc_water_pump().translate((44.0, ${pythonNumber(waterPumpY)}, 17.5))

    return [
        battery_holder,
        relay_module,
        sci_module,
        k10_io_board,
        k10_board,
        soil_sensor,
        water_pump,
    ]


base_part = build_hollow_base()
base_part = apply_openings(base_part)
base_part = apply_screw_bosses(base_part)
lid_part = build_lid()
lid_part = apply_lid_screw_holes(lid_part)
base_part, lid_part = apply_mounts(base_part, lid_part)
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
function round1(value) {
  return Math.round(Number(value) * 10) / 10;
}

function pythonNumber(value) {
  const number = round1(value);
  return Number.isInteger(number) ? number.toFixed(1) : String(number);
}
