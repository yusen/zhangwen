import crypto from 'node:crypto';
import { readFileSync } from 'node:fs';

import { getHardwareProfile } from '../hardware-library.js';

export const TEMPLATE_CASE_CONTRACT = 'template_parts_v1';

const SOURCE_HASHES = Object.freeze({
  unihiker_light_effect_cup_v1: '6eccb944ea677d2cd3bdcc2002bcddaf81f9bba8dac5f91d37fc747de2ff27fa',
  unihiker_handheld_fan_v1: '29a323d62f667c7a47d47cc3354a1731652a0a7a841729ac002093f4adccc248',
  mpython_board_enclosure_v1: 'f30e5ebc66f27ab8259c7ce78c29613386877b0552753914f52fd2d46c9e35a4',
  unihiker_auto_open_lid_box_v1: '8608f82b54577cea5837cb34f8651b6525dfb8883e09b1985f84e6db7544312f',
});

const SOURCE_FILES = Object.freeze({
  unihiker_light_effect_cup_v1: 'unihiker_light_effect_cup_v1.cq.py',
  unihiker_handheld_fan_v1: 'unihiker_handheld_fan_v1.cq.py',
  mpython_board_enclosure_v1: 'mpython_board_enclosure_v1.cq.py',
  unihiker_auto_open_lid_box_v1: 'unihiker_auto_open_lid_box_v1.cq.py',
});

const CASE_DEFINITIONS = Object.freeze({
  unihiker_light_effect_cup_v1: {
    product_id: 'light_effect_cup',
    name: '光效水杯',
    hardware_system: 'unihiker',
    bom: [
      { hardware_id: 'unihiker_k10', role: 'controller', function: '提供显示、交互和主控计算。' },
      { hardware_id: 'unihiker_polymer_lipo_battery', role: 'battery', function: '为便携水杯提供电源。' },
      { hardware_id: 'unihiker_rgb12_led_ring', role: 'rgb_led_ring', function: '提供杯体光效。' },
    ],
    printable_parts: [
      { id: 'main_body', label: '光效水杯主体', source_name: 'main_body', bbox: { length_x: 100, width_y: 161, height_z: 100 }, center: { x: 0, y: 0, z: 50 } },
    ],
    reference_parts: [
      { id: 'rgb_ring_model', label: 'RGB12 灯环参考', hardware_id: 'unihiker_rgb12_led_ring', source_name: 'rgb_ring_model', bbox: { length_x: 47, width_y: 47, height_z: 9.1 }, center: { x: 0, y: 0, z: 50 } },
      { id: 'battery_model', label: '行空板聚合物锂电池参考', hardware_id: 'unihiker_polymer_lipo_battery', source_name: 'battery_model', bbox: { length_x: 49, width_y: 32, height_z: 6 }, center: { x: 0, y: 0, z: 25 } },
      { id: 'k10_model', label: '行空板 K10 参考', hardware_id: 'unihiker_k10', source_name: 'k10_model', bbox: { length_x: 83.2, width_y: 51.3, height_z: 10.6 }, center: { x: 0, y: 0, z: 50 } },
    ],
    bounds: { length_x: 111.6, width_y: 164.4, height_z: 100 },
    summary: '光效水杯真实 CadQuery 案例：杯体、环形把手和 K10、锂电池、RGB 灯环参考件。',
    adapter: `
TEMPLATE_PARTS_SCHEMA_VERSION = "template_parts_v1"
template_parts = [
    {"id": "main_body", "name": "光效水杯主体", "object": main_body, "printable": True, "placement_mm": {"x": 0, "y": 0, "z": 0}},
]
template_reference_parts = [
    {"id": "rgb_ring_model", "name": "RGB12 灯环参考", "object": rgb_ring_model, "printable": False},
    {"id": "battery_model", "name": "行空板聚合物锂电池参考", "object": battery_model, "printable": False},
    {"id": "k10_model", "name": "行空板 K10 参考", "object": k10_model, "printable": False},
]
template_scene = assembly
`,
  },
  unihiker_handheld_fan_v1: {
    product_id: 'handheld_fan',
    name: '手持小风扇',
    hardware_system: 'unihiker',
    bom: [
      { hardware_id: 'unihiker_k10', role: 'controller', function: '提供显示、交互和主控计算。' },
      { hardware_id: 'unihiker_polymer_lipo_battery', role: 'battery', function: '为手持风扇提供便携电源。' },
      { hardware_id: 'unihiker_dc_motor_fan', role: 'fan', function: '提供直流电机和扇叶组件。' },
    ],
    printable_parts: [
      { id: 'main_body', label: '手持小风扇主体', source_name: 'main_body', bbox: { length_x: 52, width_y: 52, height_z: 160 }, center: { x: 0, y: 0, z: 80 } },
    ],
    reference_parts: [
      { id: 'k10_model', label: '行空板 K10 参考', hardware_id: 'unihiker_k10', source_name: 'k10_model', bbox: { length_x: 83.2, width_y: 51.3, height_z: 10.6 }, center: { x: 0, y: 0, z: 170 } },
      { id: 'battery_model', label: '行空板聚合物锂电池参考', hardware_id: 'unihiker_polymer_lipo_battery', source_name: 'battery_model', bbox: { length_x: 49, width_y: 32, height_z: 6 }, center: { x: 0, y: 0, z: 35 } },
      { id: 'fan_model', label: '直流电机风扇参考', hardware_id: 'unihiker_dc_motor_fan', source_name: 'fan_model', bbox: { length_x: 52, width_y: 39, height_z: 24 }, center: { x: 0, y: -18, z: 172 } },
    ],
    bounds: { length_x: 83.2, width_y: 54, height_z: 181.5 },
    summary: '手持小风扇真实 CadQuery 案例：手柄主体和 K10、电池、直流电机风扇参考件。',
    adapter: `
TEMPLATE_PARTS_SCHEMA_VERSION = "template_parts_v1"
template_parts = [
    {"id": "main_body", "name": "手持小风扇主体", "object": main_body, "printable": True, "placement_mm": {"x": 0, "y": 0, "z": 0}},
]
template_reference_parts = [
    {"id": "k10_model", "name": "行空板 K10 参考", "object": k10_model, "printable": False},
    {"id": "battery_model", "name": "行空板聚合物锂电池参考", "object": battery_model, "printable": False},
    {"id": "fan_model", "name": "直流电机风扇参考", "object": fan_model, "printable": False},
]
template_scene = assembly
`,
  },
  mpython_board_enclosure_v1: {
    product_id: 'mpython_board_enclosure',
    name: '掌控板外壳',
    hardware_system: 'mpython',
    bom: [
      { hardware_id: 'mpython_board_3_0', role: 'controller', function: '作为掌控板外壳的匹配硬件参考。' },
    ],
    printable_parts: [
      { id: 'bottom_shell', label: '掌控板外壳底壳', source_name: 'bottom_shell', bbox: { length_x: 55, width_y: 49, height_z: 7.6 }, center: { x: 0, y: 0, z: 3.8 } },
      { id: 'top_cover', label: '掌控板外壳上盖', source_name: 'top_cover', bbox: { length_x: 55, width_y: 49, height_z: 3.2 }, center: { x: 0, y: 0, z: 8 } },
    ],
    reference_parts: [],
    bounds: { length_x: 55, width_y: 49, height_z: 10.8 },
    summary: '掌控板 3.0 外壳真实 CadQuery 案例，底壳和上盖作为两个独立打印件导出。',
    adapter: `
TEMPLATE_PARTS_SCHEMA_VERSION = "template_parts_v1"
template_parts = [
    {"id": "bottom_shell", "name": "掌控板外壳底壳", "object": bottom_shell, "printable": True, "placement_mm": {"x": 0, "y": 0, "z": 0}},
    {"id": "top_cover", "name": "掌控板外壳上盖", "object": top_cover, "printable": True, "placement_mm": {"x": 0, "y": 0, "z": 0}},
]
template_reference_parts = []
template_scene = cq.Compound.makeCompound([bottom_shell.val(), top_cover.val()])
`,
  },
  unihiker_auto_open_lid_box_v1: {
    product_id: 'auto_open_lid_box',
    name: '行空板自动感应开盖智能盒子',
    hardware_system: 'unihiker',
    bom: [
      { hardware_id: 'unihiker_k10', role: 'controller', function: '承担盒体外侧的主控和交互。' },
      { hardware_id: 'unihiker_k10_io_expansion_board', role: 'controller_expansion', function: '提供传感器和执行器接口。' },
      { hardware_id: 'unihiker_servo', role: 'servo', function: '驱动上盖自动开合。' },
      { hardware_id: 'unihiker_ultrasonic_distance_sensor', role: 'distance_sensor', function: '检测靠近动作并触发开盖。' },
    ],
    printable_parts: [
      { id: 'base_part', label: '智能盒子底盒', source_name: 'base_part', bbox: { length_x: 100, width_y: 89, height_z: 40 }, center: { x: 0, y: 0, z: 20 } },
      { id: 'lid_part', label: '智能盒子上盖', source_name: 'lid_part', bbox: { length_x: 99.6, width_y: 48.139, height_z: 92.236 }, center: { x: 48, y: 20, z: 70 } },
    ],
    reference_parts: [
      { id: 'unihiker_k10', label: '行空板 K10 参考', hardware_id: 'unihiker_k10', source_name: 'hardware_reference_parts[0]', bbox: { length_x: 83.2, width_y: 51.3, height_z: 10.6 }, center: { x: 100.6, y: -13.2, z: 59.75 } },
      { id: 'unihiker_k10_io_expansion_board', label: 'K10 IO 扩展板参考', hardware_id: 'unihiker_k10_io_expansion_board', source_name: 'hardware_reference_parts[1]', bbox: { length_x: 80, width_y: 47, height_z: 22.3 }, center: { x: 100.6, y: -14, z: 7.95 } },
      { id: 'unihiker_servo', label: '舵机参考', hardware_id: 'unihiker_servo', source_name: 'hardware_reference_parts[2]', bbox: { length_x: 32.6, width_y: 12, height_z: 31.5 }, center: { x: 35, y: 25, z: 25 } },
      { id: 'unihiker_ultrasonic_distance_sensor', label: '超声波测距传感器参考', hardware_id: 'unihiker_ultrasonic_distance_sensor', source_name: 'hardware_reference_parts[3]', bbox: { length_x: 22, width_y: 47, height_z: 20.3 }, center: { x: 0, y: -36.4, z: 20 } },
      { id: 'servo_horn', label: '舵机臂参考', source_name: 'hardware_reference_parts[4]', bbox: { length_x: 22, width_y: 8, height_z: 3 }, center: { x: 35, y: 25, z: 45 } },
    ],
    bounds: { length_x: 190.6, width_y: 119.234, height_z: 124.236 },
    summary: '行空板自动感应开盖盒真实 CadQuery 案例，包含铰链、舵机、超声波和 K10 外置参考。',
    adapter: `
TEMPLATE_PARTS_SCHEMA_VERSION = "template_parts_v1"
template_parts = [
    {"id": "base_part", "name": "智能盒子底盒", "object": base_part, "printable": True, "placement_mm": {"x": 0, "y": 0, "z": 0}},
    {"id": "lid_part", "name": "智能盒子上盖", "object": lid_part, "printable": True, "placement_mm": {"x": 0, "y": 0, "z": 0}},
]
template_reference_parts = [
    {"id": "unihiker_k10", "name": "行空板 K10 参考", "object": hardware_reference_parts[0], "printable": False},
    {"id": "unihiker_k10_io_expansion_board", "name": "K10 IO 扩展板参考", "object": hardware_reference_parts[1], "printable": False},
    {"id": "unihiker_servo", "name": "舵机参考", "object": hardware_reference_parts[2], "printable": False},
    {"id": "unihiker_ultrasonic_distance_sensor", "name": "超声波测距传感器参考", "object": hardware_reference_parts[3], "printable": False},
    {"id": "servo_horn", "name": "舵机臂参考", "object": hardware_reference_parts[4], "printable": False},
]
template_scene = cq.Compound.makeCompound([
    base_part.val(), lid_part.val(),
    *[part.val() if hasattr(part, "val") else part for part in hardware_reference_parts],
])
`,
  },
});

// World-space bounds measured from the imported source transforms.  The source
// files remain byte-for-byte copies; this metadata only drives the 2D preview.
const LAYOUT_OVERRIDES = Object.freeze({
  unihiker_light_effect_cup_v1: {
    printable_parts: {
      main_body: { bbox: { length_x: 100, width_y: 161, height_z: 100 }, center: { x: 0, y: 30.5, z: 50 } },
    },
    reference_parts: {
      rgb_ring_model: { bbox: { length_x: 47, width_y: 9.1, height_z: 47 }, center: { x: 0, y: -48.85, z: 50 } },
      battery_model: { bbox: { length_x: 6, width_y: 32, height_z: 49 }, center: { x: -53, y: 0, z: 50.5 } },
      k10_model: { bbox: { length_x: 10.6, width_y: 51.3, height_z: 83.2 }, center: { x: 50.3, y: 0, z: 50 } },
    },
  },
  unihiker_handheld_fan_v1: {
    reference_parts: {
      k10_model: { bbox: { length_x: 83.2, width_y: 10.6, height_z: 51.3 }, center: { x: 0, y: -13.8, z: 100.65 } },
      battery_model: { bbox: { length_x: 49, width_y: 6, height_z: 32 }, center: { x: 0.5, y: 16.5, z: 91 } },
      fan_model: { bbox: { length_x: 52, width_y: 39, height_z: 24 }, center: { x: 0, y: -8.5, z: 169.5 } },
    },
  },
  mpython_board_enclosure_v1: {
    printable_parts: {
      bottom_shell: { bbox: { length_x: 55, width_y: 49, height_z: 7.6 }, center: { x: 0, y: -0.75, z: 2.3 } },
      top_cover: { bbox: { length_x: 55, width_y: 49, height_z: 3.2 }, center: { x: 0, y: -0.75, z: 7.7 } },
    },
  },
  unihiker_auto_open_lid_box_v1: {
    printable_parts: {
      base_part: { bbox: { length_x: 100, width_y: 89, height_z: 40 }, center: { x: 0, y: 4.5, z: 20 } },
      lid_part: { bbox: { length_x: 99.6, width_y: 48.139, height_z: 92.236 }, center: { x: 0, y: 44.765, z: 78.118 } },
    },
    reference_parts: {
      unihiker_k10: { bbox: { length_x: 51.3, width_y: 10.6, height_z: 83.2 }, center: { x: 100.6, y: -13.5, z: 59.75 } },
      unihiker_k10_io_expansion_board: { bbox: { length_x: 80, width_y: 47, height_z: 22.3 }, center: { x: 100.6, y: -14, z: 14 } },
      unihiker_servo: { bbox: { length_x: 31.5, width_y: 32.6, height_z: 12 }, center: { x: 15.75, y: 20, z: 34 } },
      unihiker_ultrasonic_distance_sensor: { bbox: { length_x: 47, width_y: 20.3, height_z: 22 }, center: { x: 0, y: -40.25, z: 20 } },
      servo_horn: { bbox: { length_x: 3.8, width_y: 11.3, height_z: 19.3 }, center: { x: -0.4, y: 23.15, z: 40.15 } },
    },
  },
});

function materializeBatchModelDefinition(definition, templateId = '') {
  if (!definition) return null;
  const override = LAYOUT_OVERRIDES[templateId || definition.template_id];
  if (!override) return definition;
  const apply = (parts, partOverrides) => (parts || []).map((part) => ({
    ...part,
    ...(partOverrides?.[part.id] || {}),
  }));
  return {
    ...definition,
    printable_parts: apply(definition.printable_parts, override.printable_parts),
    reference_parts: apply(definition.reference_parts, override.reference_parts),
  };
}

export function getBatchModelTemplateDefinition(templateId = '') {
  return materializeBatchModelDefinition(CASE_DEFINITIONS[templateId], templateId);
}

export function listBatchModelTemplateDefinitions() {
  return Object.entries(CASE_DEFINITIONS).map(([template_id, rawDefinition]) => {
    const definition = materializeBatchModelDefinition(rawDefinition, template_id);
    return {
      template_id,
      product_id: definition.product_id,
      name: definition.name,
      hardware_system: definition.hardware_system,
      model_contract: TEMPLATE_CASE_CONTRACT,
      source_filename: SOURCE_FILES[template_id],
      source_sha256: SOURCE_HASHES[template_id],
      printable_part_ids: definition.printable_parts.map((part) => part.id),
      reference_part_ids: definition.reference_parts.map((part) => part.id),
    };
  });
}

export function buildBatchModelTemplate({ product, detection, body = {}, context = {} } = {}) {
  const templateId = String(product?.template_id || '').trim();
  const definition = materializeBatchModelDefinition(CASE_DEFINITIONS[templateId], templateId);
  if (!definition) return null;

  const profileEntries = definition.bom.map((item) => ({
    ...item,
    profile: getHardwareProfile(item.hardware_id),
  }));
  const missing = profileEntries.filter((item) => !item.profile).map((item) => item.hardware_id);
  if (missing.length) return buildMissingProfileResponse({ product, detection, definition, missing, body });

  const source = readFileSync(new URL(`./batch-models/${SOURCE_FILES[templateId]}`, import.meta.url), 'utf8');
  const sourceSha256 = crypto.createHash('sha256').update(source, 'utf8').digest('hex');
  if (sourceSha256 !== SOURCE_HASHES[templateId]) {
    return buildTemplateSourceMismatchResponse({
      product,
      detection,
      definition,
      templateId,
      sourceSha256,
      body,
    });
  }
  const designId = context.designId || 'ZW-BATCH-MODEL-TEMPLATE-PREVIEW';
  const resultStartedAt = context.resultStartedAt || new Date().toISOString();
  const bom = profileEntries.map(({ profile, ...item }) => ({
    hardware_id: item.hardware_id,
    name: profile.name,
    role: item.role,
    category: profile.category,
    hardware_system: profile.hardware_system,
    quantity: 1,
    required_or_optional: 'required',
    function: item.function,
    profile_status: 'builtin',
    dimensions_mm: profile.dimensions_mm,
    mounting_intent: {
      preferred_surface: profile.mounting?.preferred_enclosure_surface || 'external_scene',
      fixed_to_enclosure: false,
    },
  }));
  const scene = buildLayoutScene(templateId, definition, bom);
  const printableParts = definition.printable_parts.map((part) => ({
    id: part.id,
    label: part.label,
    object_type: 'printable_part',
    source_export_id: `cadquery_template_${safeId(part.id)}_stl`,
    export_id: `cadquery_template_${safeId(part.id)}_stl`,
    format: 'stl',
    dimensions_mm: part.bbox,
    preview_center_mm: part.center,
  }));
  const designState = {
    id: designId,
    design_hash: designId,
    result_started_at: resultStartedAt,
    design_mode: 'template_case',
    template_case: true,
    template_id: templateId,
    model_contract: TEMPLATE_CASE_CONTRACT,
    intent: buildIntent(product, body, bom),
    bom,
    function_verification_report: {
      status: 'ok',
      verification_status: 'pass',
      source: 'deterministic_product_template',
      covered_functions: bom.map((item) => item.function),
      missing_functions: [],
      missing_hardware: [],
    },
    hardware_profiles: profileEntries.map((item) => item.profile),
    profile_validation_report: {
      status: 'ok',
      source: 'deterministic_product_template',
      checked_profile_ids: bom.map((item) => item.hardware_id),
      missing_profile_ids: [],
    },
    mounting_plan: [],
    layout_plan: scene,
    enclosure_parameters: null,
    cad_parameters: {
      generator: templateId,
      units: 'mm',
      model_contract: TEMPLATE_CASE_CONTRACT,
      geometry: definition.bounds,
      source_filename: SOURCE_FILES[templateId],
      source_sha256: sourceSha256,
      source_sha256_expected: SOURCE_HASHES[templateId],
    },
    validation_context: {
      status: 'pass',
      model_contract: TEMPLATE_CASE_CONTRACT,
      source_hash_match: sourceSha256 === SOURCE_HASHES[templateId],
      no_proxy_geometry: true,
    },
    parameters: {},
    project_default_parameters: {},
    default_parameters: {},
    printable_parts: printableParts,
    template_parts: definition.printable_parts,
    template_reference_parts: definition.reference_parts,
    template_source: {
      filename: SOURCE_FILES[templateId],
      sha256: sourceSha256,
      expected_sha256: SOURCE_HASHES[templateId],
      original_case: definition.name,
    },
    hardware_face_overrides: {},
    hardware_rotation_overrides: {},
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
    warnings: [],
  };
  const deterministicProduct = summarizeTemplateProduct(product, detection, definition, sourceSha256);
  const intentAnalysis = {
    source: 'deterministic_product_template',
    status: 'ok',
    model_status: 'skipped',
    reason: detection?.reason || `${definition.name} 模板命中`,
    confidence: detection?.confidence ?? 0.97,
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
  };
  const checks = [
    { id: 'template_source_hash', label: '模板源码哈希', status: sourceSha256 === SOURCE_HASHES[templateId] ? 'pass' : 'fail', message: sourceSha256 === SOURCE_HASHES[templateId] ? '库内母版与导入源一致。' : '库内母版哈希与导入记录不一致。' },
    { id: 'template_parts_contract', label: '模板部件契约', status: 'pass', message: `${definition.printable_parts.length} 个可打印部件和 ${definition.reference_parts.length} 个参考部件已声明。` },
    { id: 'template_no_enclosure_proxy', label: '真实模板几何', status: 'pass', message: '使用案例原始 CadQuery 几何，不生成包围盒代理。' },
  ];
  const artifact = {
    status: 'artifact',
    title: `${definition.name}模板已生成`,
    message: `已命中“${definition.name}”模板，保留原案例的 CadQuery 几何、部件关系和硬件参考。每个可打印部件将独立导出，整体场景仅用于预览。`,
    deterministic_product: deterministicProduct,
    template_id: templateId,
    template_case: true,
    design_mode: 'template_case',
    model_contract: TEMPLATE_CASE_CONTRACT,
    template_source: designState.template_source,
    template_parts: definition.printable_parts,
    template_reference_parts: definition.reference_parts,
    bom,
    partial_bom: bom,
    selected_hardware_ids: bom.map((item) => item.hardware_id),
    function_verification_report: designState.function_verification_report,
    design_state: designState,
    intent_analysis: intentAnalysis,
    cadquery_code: `${source}\n\n# ZW-CAD-intent template adapter: ${TEMPLATE_CASE_CONTRACT}\n${definition.adapter}`,
    preview_assets: [scene],
    printable_parts: printableParts,
    exports: [],
    checks,
    warnings: [],
    conversation_route: designState.conversation_route,
    revision_intent: designState.revision_intent,
    source: 'deterministic_product_template',
  };
  artifact.generation_trace = buildTemplateGenerationTrace(artifact, definition);
  artifact.design_state.generation_trace = artifact.generation_trace;
  return artifact;
}

function buildTemplateSourceMismatchResponse({ product, detection, definition, templateId, sourceSha256, body }) {
  const expectedSha256 = SOURCE_HASHES[templateId] || '';
  const response = {
    status: 'needs_input',
    title: `${definition.name}模板源码校验失败`,
    message: `模板源码哈希不一致。期望 ${expectedSha256}，实际 ${sourceSha256}。`,
    blocking_reason: 'template_source_hash_mismatch',
    deterministic_product: summarizeTemplateProduct(product, detection, definition, sourceSha256),
    template_id: templateId,
    template_case: true,
    design_mode: 'template_case',
    model_contract: TEMPLATE_CASE_CONTRACT,
    source: 'deterministic_product_template',
    intent_analysis: {
      source: 'deterministic_product_template',
      status: 'blocked',
      model_status: 'skipped',
      reason: detection?.reason || '',
      confidence: detection?.confidence ?? 0.97,
      conversation_route: body?.conversation_route || body?.conversationRoute || null,
    },
  };
  response.generation_trace = {
    schema_version: 'generation_trace_v1',
    stage: 'blocked',
    template_id: templateId,
    model_contract: TEMPLATE_CASE_CONTRACT,
    blocking_reason: response.blocking_reason,
    source_sha256: sourceSha256,
    expected_source_sha256: expectedSha256,
    source: 'deterministic_product_template',
  };
  return response;
}

function buildMissingProfileResponse({ product, detection, definition, missing, body }) {
  const response = {
    status: 'needs_input',
    title: `${definition.name}模板缺少硬件资料`,
    message: `已识别为“${definition.name}”，但硬件库缺少：${missing.join('、')}。未使用占位模型。`,
    deterministic_product: summarizeTemplateProduct(product, detection, definition),
    template_id: product?.template_id,
    template_case: true,
    model_contract: TEMPLATE_CASE_CONTRACT,
    partial_bom: [],
    bom: [],
    missing_hardware_requests: missing.map((hardware_id) => ({ hardware_id, reason: 'deterministic_template_required_profile_missing' })),
    questions: [`请先补齐这些硬件 profile：${missing.join('、')}。`],
    blocking_reason: 'deterministic_template_missing_profile',
    source: 'deterministic_product_template',
    intent_analysis: {
      source: 'deterministic_product_template',
      status: 'blocked',
      model_status: 'skipped',
      reason: detection?.reason || '',
      confidence: detection?.confidence ?? 0.97,
      conversation_route: body.conversation_route || body.conversationRoute || null,
    },
  };
  response.generation_trace = {
    schema_version: 'generation_trace_v1',
    stage: 'blocked',
    template_id: product?.template_id || '',
    model_contract: TEMPLATE_CASE_CONTRACT,
    blocking_reason: response.blocking_reason,
    missing_profile_ids: missing,
    source: 'deterministic_product_template',
  };
  return response;
}

function buildIntent(product, body, bom) {
  return {
    product_name: product?.product_name || product?.name || '模板案例',
    hardware_system: product?.hardware_system || '',
    functions: bom.map((item) => item.function),
    required_hardware_roles: bom.map((item) => ({ role: item.role, hardware_id: item.hardware_id, required: true })),
    mounting_intents: [],
    user_constraints: { template_locked_geometry: true },
    source: 'deterministic_product_template',
    prompt: body.prompt || '',
  };
}

function buildLayoutScene(templateId, definition, bom) {
  const referenceByHardware = new Map(
    definition.reference_parts
      .filter((part) => part.hardware_id)
      .map((part) => [part.hardware_id, part]),
  );
  const parts = [
    ...definition.printable_parts.map((part) => ({
      id: part.id,
      name: part.label,
      label: part.label,
      kind: 'printable',
      printable: true,
      bbox_mm: part.bbox,
      dimensions_mm: part.bbox,
      center_mm: part.center,
      center: part.center,
    })),
    ...definition.reference_parts.map((part) => ({
      id: part.id,
      name: part.label,
      label: part.label,
      kind: 'reference',
      printable: false,
      hardware_id: part.hardware_id || '',
      bbox_mm: part.bbox,
      dimensions_mm: part.bbox,
      center_mm: part.center,
      center: part.center,
    })),
  ];
  return {
    id: `${templateId}_layout_scene`,
    type: 'layout_scene',
    scene_kind: 'template_case',
    template_case: true,
    template_id: templateId,
    units: 'mm',
    bounds_mm: definition.bounds,
    parts,
    hardware: bom.map((item) => {
      const reference = referenceByHardware.get(item.hardware_id);
      return {
        id: item.hardware_id,
        name: item.name,
        dimensions_mm: reference?.bbox || item.dimensions_mm || {},
        ...(reference?.center ? { center: reference.center } : {}),
        ...(reference ? { reference_part_id: reference.id } : {}),
        surface: 'reference',
      };
    }),
    openings: [],
    mounts: [],
    modes: {
      assembly: { show: ['parts'], explode: false },
      exploded: { show: ['parts'], explode: true },
    },
  };
}

function summarizeTemplateProduct(product, detection, definition, sourceSha256 = '') {
  return {
    id: product?.id || definition?.product_id || '',
    name: product?.name || definition?.name || '',
    product_name: product?.product_name || definition?.name || '',
    hardware_system: product?.hardware_system || definition?.hardware_system || '',
    status: product?.status || 'available',
    model_status: product?.model_status || 'implemented',
    template_id: product?.template_id || '',
    template_case: true,
    model_contract: TEMPLATE_CASE_CONTRACT,
    source_filename: SOURCE_FILES[product?.template_id] || '',
    source_sha256: sourceSha256 || SOURCE_HASHES[product?.template_id] || '',
    description: product?.description || definition?.summary || '',
    matched: true,
    source: detection?.source || 'deterministic_product_detector',
    reason: detection?.reason || '',
    confidence: detection?.confidence ?? 0.97,
  };
}

function buildTemplateGenerationTrace(artifact, definition) {
  return {
    schema_version: 'generation_trace_v1',
    stage: 'artifact',
    generated_at: new Date().toISOString(),
    deterministic_product: artifact.deterministic_product,
    template_id: artifact.template_id,
    model_contract: TEMPLATE_CASE_CONTRACT,
    source_filename: SOURCE_FILES[artifact.template_id],
    source_sha256: artifact.deterministic_product?.source_sha256 || '',
    intent: {
      source: artifact.intent_analysis?.source,
      status: artifact.intent_analysis?.status,
      reason: artifact.intent_analysis?.reason,
      confidence: artifact.intent_analysis?.confidence,
    },
    hardware: {
      bom_count: artifact.bom.length,
      hardware_ids: artifact.bom.map((item) => item.hardware_id),
    },
    parts: {
      printable_count: definition.printable_parts.length,
      printable_ids: definition.printable_parts.map((item) => item.id),
      reference_count: definition.reference_parts.length,
      reference_ids: definition.reference_parts.map((item) => item.id),
      scene_only: true,
    },
    validation: {
      validation_status: artifact.checks.some((item) => item.status === 'fail') ? 'fail' : 'pass',
      status_counts: artifact.checks.reduce((acc, item) => {
        acc[item.status] = (acc[item.status] || 0) + 1;
        return acc;
      }, {}),
    },
    skipped_stages: [
      'model_intent_analysis',
      'requirement_analysis_confirmation',
      'generic_bom_selection',
      'generic_layout_solver',
    ],
    source: 'deterministic_product_template',
  };
}

function safeId(value = '') {
  return String(value).replace(/[^a-zA-Z0-9_-]+/g, '_').replace(/^_+|_+$/g, '') || 'part';
}
