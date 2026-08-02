import crypto from 'node:crypto';
import {
  allocateResultDirectory,
  cleanupResultDirectories,
  clearManagedResultArtifacts,
  normalizeTaskId,
  releaseResultDirectoryLease,
} from './result-store.js';
import {
  writeArtifactMetadataFiles,
  writeArtifactSnapshotFile,
  writeProjectDefaultParametersFile,
  writeProjectModelSourceFile,
} from './stl-exporter.js';
import { writeWorkflowArtifactFiles } from './workflow-artifacts.js';
import { createHardwareResolver } from './hardware-library.js';
import { cadqueryRuntimeDetails, cadqueryRuntimeMessage, loadTrustedHardwareCadQueryModel } from './pipeline/cad.js';
import { normalizeString, normalizeStringArray } from './pipeline/shared.js';

export const STRUCTURAL_PARTS_SCHEMA_VERSION = 'structural_parts_v1';
export const STRUCTURAL_PART_DESIGN_MODE = 'structural_part_project';
export const STRUCTURAL_PART_ROUTE_ACTION = 'standalone_structural_parts';
export const STRUCTURAL_PART_SCENE_GAP_MM = 15;

const ENCLOSURE_WORDS = /(?:盒子|盒体|控制盒|保护盒|外壳|壳体|保护壳|机箱|带盖长方体|enclosure|housing|\bbox\b|\bcase\b)/i;
const ELECTRONIC_PROJECT_WORDS = /(?:ESP32|XIAO|Arduino|主控|控制器|控制盒|开发板|传感器|电路板|PCB|电子项目|电子元器件|电子件|接线|供电系统|驱动板|锂电池|电池供电|controller|sensor|electronics?)/i;
const MIXED_ELECTRONIC_ATTACHMENT_WORDS = /(?:和|及|以及|搭配|配合|加上?|带上?|包含).{0,10}(?:舵机|电机|servo|motor)/i;
const EXISTING_ELECTRONICS_WORDS = /(?:(?:已有|已经有|自带|手头有|手头已有|现有|不用|无需|不要|不需要).{0,12}(?:主控|控制器|开发板|传感器|电子元器件|电子件|元器件|舵机|电机|驱动板|锂电池)|(?:只要|只需|只需要|仅要|仅需|仅需要|单独).{0,12}(?:结构件|机器狗|电池座|托盘))/i;
const KNOWN_STRUCTURAL_ALIASES = Object.freeze({
  quadruped_dog_body: ['机器狗身体', '机器狗身', '机器狗主体', '四足机器狗身体', 'quadruped dog body'],
  quadruped_dog_thigh: ['机器狗大腿', '四足机器狗大腿', 'quadruped dog thigh'],
  quadruped_dog_shin: ['机器狗小腿', '四足机器狗小腿', 'quadruped dog shin'],
  battery_18650_holder: ['18650电池座', '18650 电池座', '18650电池托', '18650 电池托', '18650 battery holder'],
});

export function detectStandaloneStructuralPartsRequest(body = {}, { hardwareResolver = createHardwareResolver(body.customHardwareProfiles) } = {}) {
  const prompt = normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt);
  const explicitMode = normalizeString(body.designMode || body.design_mode || body.intent?.design_mode) === STRUCTURAL_PART_DESIGN_MODE;
  const explicitRoute = normalizeString(body.routeAction || body.route_action || body.conversationRoute?.route_action || body.conversation_route?.route_action)
    === STRUCTURAL_PART_ROUTE_ACTION;
  if (ENCLOSURE_WORDS.test(prompt)) {
    return { requested: false, reason: 'explicit_enclosure_request', profile_ids: [] };
  }

  const selectedIds = normalizeStringArray(body.selectedHardwareIds || body.selected_hardware_ids || body.intent?.selected_hardware_ids);
  const selectedProfiles = hardwareResolver.getHardwareProfiles(selectedIds);
  const selectedStructural = selectedProfiles.filter(isCommonStructuralProfile);
  const selectedHasNonStructural = selectedProfiles.length !== selectedIds.length
    || selectedProfiles.some((profile) => !isCommonStructuralProfile(profile));
  if (selectedIds.length && selectedHasNonStructural) {
    return { requested: false, reason: 'mixed_or_invalid_hardware_selection', profile_ids: [] };
  }

  const namedElectronicIds = findNamedCommonElectronicProfileIds(prompt, hardwareResolver);
  if (namedElectronicIds.length) {
    return { requested: false, reason: 'named_electronic_components', profile_ids: [] };
  }

  const namedIds = findNamedStructuralProfileIds(prompt, hardwareResolver);
  const promptWithoutNamedStructuralParts = removeNamedStructuralProfileTerms(
    prompt,
    namedIds,
    hardwareResolver,
  );
  const clearlyElectronicProject = (ELECTRONIC_PROJECT_WORDS.test(prompt)
      || MIXED_ELECTRONIC_ATTACHMENT_WORDS.test(promptWithoutNamedStructuralParts))
    && !EXISTING_ELECTRONICS_WORDS.test(prompt);
  if (selectedStructural.length
    && !clearlyElectronicProject) {
    return {
      requested: true,
      reason: 'selected_common_structural_parts',
      profile_ids: uniqueStrings(selectedStructural.map((profile) => profile.id)),
    };
  }

  if (namedIds.length
    && !clearlyElectronicProject) {
    return { requested: true, reason: 'named_common_structural_parts', profile_ids: namedIds };
  }

  if ((explicitMode || explicitRoute) && !clearlyElectronicProject) {
    return {
      requested: true,
      reason: explicitMode ? 'explicit_structural_design_mode' : 'explicit_structural_route',
      profile_ids: uniqueStrings([
        ...selectedStructural.map((profile) => profile.id),
        ...namedIds,
      ]),
    };
  }
  return { requested: false, reason: '', profile_ids: [] };
}

export async function buildStandaloneStructuralPartsResponse(body = {}, context = {}, { stage = 'confirmation' } = {}) {
  const hardwareResolver = createHardwareResolver(body.customHardwareProfiles);
  const detection = detectStandaloneStructuralPartsRequest(body, { hardwareResolver });
  if (!detection.requested) return null;
  if (!detection.profile_ids.length) {
    return needsInput(
      '请选择通用件中的结构件',
      '独立结构件项目只会使用通用件库中已有的结构母版；当前没有识别到具体结构件。',
      ['请在通用件的“结构件”分类中选择至少一个条目，或在描述中明确写出结构件名称。'],
      'structural_part_selection_required',
    );
  }

  const profiles = detection.profile_ids
    .map((id) => hardwareResolver.getHardwareProfile(id))
    .filter(Boolean);
  const invalidProfiles = profiles.filter((profile) => !isCommonStructuralProfile(profile));
  if (invalidProfiles.length || profiles.length !== detection.profile_ids.length) {
    return needsInput(
      '结构件选择无效',
      '独立结构件项目只能使用通用件库中标记为 structural_part 的现有条目。',
      ['请移除电子元器件、品牌专属硬件或不存在的条目后重试。'],
      'invalid_structural_part_selection',
    );
  }

  const resolvedModels = profiles.map((profile) => ({
    profile,
    resolution: loadTrustedHardwareCadQueryModel(profile),
  }));
  const unavailable = resolvedModels.filter((item) => item.resolution.status !== 'loaded');
  if (unavailable.length) {
    return {
      ...needsInput(
        '结构件母版不可用',
        `以下结构件没有通过校验的 CadQuery 母版：${unavailable.map((item) => item.profile.name || item.profile.id).join('、')}。为避免把包围盒代理误当成可打印结构，本次建模已停止。`,
        ['请先为这些通用件补充并校准 cadquery_model 母版，再重新生成。'],
        'structural_model_template_unavailable',
      ),
      structural_model_diagnostics: Object.fromEntries(unavailable.map((item) => [item.profile.id, {
        status: item.resolution.status,
        reason: item.resolution.reason,
        issues: item.resolution.issues || [],
        configured_path: item.resolution.configured_path || '',
      }])),
    };
  }

  const scene = buildStructuralPartsScene(profiles);
  const bom = buildStructuralBom(profiles);
  const intent = buildStructuralIntent(body, profiles, detection);
  const cadqueryCode = buildStructuralPartsCadQueryCode(resolvedModels, scene);
  const checks = buildStructuralChecks({ resolvedModels, scene, environment: context.environment });
  const warnings = buildStructuralWarnings({ profiles, environment: context.environment });
  const designId = normalizeTaskId(body.taskId || body.task_id || body.currentDesignState?.id)
    || createStructuralDesignId({ intent, scene });
  const designState = buildStructuralDesignState({
    designId,
    intent,
    bom,
    profiles,
    scene,
    checks,
    warnings,
    conversationRoute: body.conversationRoute || body.conversation_route || null,
  });

  if (stage === 'confirmation') {
    return buildStructuralConfirmation({ intent, bom, designState, scene, checks, warnings });
  }
  return persistStructuralArtifact({
    body,
    context,
    intent,
    bom,
    profiles,
    scene,
    cadqueryCode,
    checks,
    warnings,
  });
}

export function isCommonStructuralProfile(profile = {}) {
  if (normalizeString(profile.hardware_system).toLowerCase() !== 'common') return false;
  const modelType = normalizeString(profile.model_type || profile.modelType).toLowerCase();
  if (modelType) return modelType === 'structural_part';
  return normalizeString(profile.category).toLowerCase() === 'structural_part'
    || normalizeString(profile.id) === 'battery_18650_holder';
}

export function buildStructuralPartsScene(profiles = [], gapMm = STRUCTURAL_PART_SCENE_GAP_MM) {
  const dimensions = profiles.map((profile) => normalizeDimensions(profile.dimensions_mm));
  const totalLength = dimensions.reduce((sum, item) => sum + item.length_x, 0)
    + Math.max(0, dimensions.length - 1) * gapMm;
  let cursor = -totalLength / 2;
  const parts = profiles.map((profile, index) => {
    const size = dimensions[index];
    const centerX = cursor + size.length_x / 2;
    cursor += size.length_x + gapMm;
    return {
      id: profile.id,
      hardware_id: profile.id,
      name: profile.name || profile.id,
      model_type: 'structural_part',
      quantity: 1,
      size_mm: size,
      placement_mm: { x: round(centerX), y: 0, z: 0 },
      rotation_deg: { x: 0, y: 0, z: 0 },
      placement_purpose: 'preview_only',
      printable: true,
    };
  });
  return {
    schema_version: STRUCTURAL_PARTS_SCHEMA_VERSION,
    type: 'structural_parts_scene',
    units: 'mm',
    gap_mm: gapMm,
    arrangement: 'x_axis_side_by_side_preview',
    assembly_relationship: 'none_inferred',
    parts,
    bounds_mm: {
      length_x: round(totalLength),
      width_y: round(Math.max(...dimensions.map((item) => item.width_y), 0)),
      height_z: round(Math.max(...dimensions.map((item) => item.height_z), 0)),
    },
  };
}

export function buildStructuralPartsCadQueryCode(resolvedModels = [], scene = {}) {
  const builders = [];
  const builderEntries = [];
  for (const [index, item] of resolvedModels.entries()) {
    const functionName = `build_structural_part_${safePythonIdentifier(item.profile.id)}_${index + 1}`;
    const source = String(item.resolution.source || '').replace(/\r\n?/g, '\n');
    const indented = source.split('\n').map((line) => `    ${line}`).join('\n');
    builders.push(`def ${functionName}():\n    def show_object(*args, **kwargs):\n        return None\n\n${indented}\n    return ${item.resolution.entrypoint || 'result'}`);
    builderEntries.push(`    ${JSON.stringify(item.profile.id)}: ${functionName},`);
  }
  const specs = scene.parts.map((part) => ({
    id: part.id,
    name: part.name,
    placement_mm: part.placement_mm,
    size_mm: part.size_mm,
  }));
  return `# ZW-CAD-intent standalone structural parts project
# This source is assembled deterministically from trusted common-part templates.
# Scene placement is preview-only; every printable object remains exportable on its own.

import json
import cadquery as cq

${builders.join('\n\n')}

STRUCTURAL_PARTS_SCHEMA_VERSION = ${JSON.stringify(STRUCTURAL_PARTS_SCHEMA_VERSION)}
STRUCTURAL_PART_BUILDERS = {
${builderEntries.join('\n')}
}
structural_part_specs = json.loads(${JSON.stringify(JSON.stringify(specs))})
structural_parts = []
for structural_part_spec in structural_part_specs:
    structural_part_object = STRUCTURAL_PART_BUILDERS[structural_part_spec["id"]]()
    structural_parts.append({
        "id": structural_part_spec["id"],
        "name": structural_part_spec["name"],
        "object": structural_part_object,
        "placement_mm": structural_part_spec["placement_mm"],
        "size_mm": structural_part_spec["size_mm"],
    })

for structural_part_entry in structural_parts:
    structural_part_placement = structural_part_entry["placement_mm"]
    structural_part_preview = structural_part_entry["object"].translate((
        float(structural_part_placement.get("x", 0)),
        float(structural_part_placement.get("y", 0)),
        float(structural_part_placement.get("z", 0)),
    ))
    show_object(structural_part_preview, name=structural_part_entry["id"])
`;
}

function findNamedStructuralProfileIds(prompt, hardwareResolver) {
  const text = normalizeString(prompt).toLowerCase();
  if (!text) return [];
  const profiles = hardwareResolver.listProfiles().filter(isCommonStructuralProfile);
  return uniqueStrings(profiles.filter((profile) => {
    const id = normalizeString(profile.id).toLowerCase();
    const name = normalizeString(profile.name).toLowerCase();
    const aliases = uniqueStrings([
      ...(Array.isArray(profile.aliases) ? profile.aliases : []),
      ...(KNOWN_STRUCTURAL_ALIASES[profile.id] || []),
    ]);
    return matchesProfileTerm(text, id)
      || matchesProfileTerm(text, name, 4)
      || aliases.some((alias) => matchesProfileTerm(text, alias));
  }).map((profile) => profile.id));
}

function removeNamedStructuralProfileTerms(prompt, profileIds, hardwareResolver) {
  let text = normalizeString(prompt).toLowerCase();
  if (!text || !profileIds.length) return text;
  const terms = [];
  for (const profileId of profileIds) {
    const profile = hardwareResolver.getHardwareProfile(profileId);
    if (!profile) continue;
    terms.push(
      profile.id,
      profile.name,
      ...(Array.isArray(profile.aliases) ? profile.aliases : []),
      ...(KNOWN_STRUCTURAL_ALIASES[profile.id] || []),
    );
  }
  for (const term of uniqueStrings(terms)
    .map((item) => normalizeString(item).toLowerCase())
    .filter(Boolean)
    .sort((left, right) => right.length - left.length)) {
    text = text.replaceAll(term, ' ');
  }
  return text;
}

function findNamedCommonElectronicProfileIds(prompt, hardwareResolver) {
  const text = normalizeString(prompt).toLowerCase();
  if (!text || EXISTING_ELECTRONICS_WORDS.test(prompt)) return [];
  const profiles = hardwareResolver.listProfiles().filter((profile) => (
    normalizeString(profile.hardware_system).toLowerCase() === 'common'
    && normalizeString(profile.model_type).toLowerCase() === 'electronic_component'
  ));
  return uniqueStrings(profiles.filter((profile) => {
    const id = normalizeString(profile.id).toLowerCase();
    const name = normalizeString(profile.name).toLowerCase();
    const aliases = Array.isArray(profile.aliases) ? profile.aliases : [];
    const idTokens = id.split(/[^a-z0-9]+/).filter((token) => token.length >= 4);
    return matchesProfileTerm(text, id)
      || matchesProfileTerm(text, name, 4)
      || aliases.some((alias) => matchesProfileTerm(text, alias))
      || idTokens.some((token) => matchesProfileTerm(text, token));
  }).map((profile) => profile.id));
}

function matchesProfileTerm(text, term, minimumLength = 1) {
  const normalizedTerm = normalizeString(term).toLowerCase();
  if (normalizedTerm.length < minimumLength) return false;
  if (text.includes(normalizedTerm)) return true;
  const compactText = text.replace(/[\s_-]+/g, '');
  const compactTerm = normalizedTerm.replace(/[\s_-]+/g, '');
  return compactTerm.length >= minimumLength && compactText.includes(compactTerm);
}

function buildStructuralBom(profiles) {
  return profiles.map((profile) => ({
    hardware_id: profile.id,
    name: profile.name || profile.id,
    category: profile.category,
    role: 'structural_part',
    roles: Array.isArray(profile.roles) ? profile.roles : [],
    model_type: 'structural_part',
    hardware_system: 'common',
    quantity: 1,
    why_needed: '用户选择了该通用结构件作为独立建模对象。',
  }));
}

function buildStructuralIntent(body, profiles, detection) {
  const prompt = normalizeString(body.prompt || body.latestUserMessage || body.latest_user_message);
  return {
    design_mode: STRUCTURAL_PART_DESIGN_MODE,
    product_name: profiles.length === 1 ? (profiles[0].name || profiles[0].id) : '通用件结构件项目',
    product_type: 'standalone_structural_parts',
    hardware_system: 'common',
    selected_hardware_ids: profiles.map((profile) => profile.id),
    required_hardware_roles: profiles.map((profile) => ({
      role: 'structural_part',
      category: profile.category,
      hardware_id: profile.id,
      label: profile.name || profile.id,
      function: '独立结构建模',
      why_needed: '用户已选择或明确点名该结构件。',
    })),
    functions: ['独立结构建模'],
    mounting_intents: [],
    user_constraints: {
      raw_prompt: prompt,
      enclosure_generation: false,
      controller_required: false,
      scene_gap_mm: STRUCTURAL_PART_SCENE_GAP_MM,
    },
    route_reason: detection.reason,
  };
}

function buildStructuralDesignState({ designId, intent, bom, profiles, scene, checks, warnings, conversationRoute }) {
  const printableParts = buildPrintableParts(scene);
  return {
    id: designId,
    design_hash: createStructuralDesignId({ intent, scene }),
    design_mode: STRUCTURAL_PART_DESIGN_MODE,
    schema_version: STRUCTURAL_PARTS_SCHEMA_VERSION,
    structural_parts_schema_version: STRUCTURAL_PARTS_SCHEMA_VERSION,
    hardware_system: 'common',
    intent,
    bom,
    hardware_profiles: profiles,
    profile_validation_report: {
      status: 'ok',
      checked_profile_count: profiles.length,
      validation_scope: 'trusted_structural_cadquery_templates',
    },
    function_verification_report: {
      status: 'skipped',
      verification_status: 'skipped_structural_part_project',
      reason: '独立结构件项目不包含电子功能覆盖验证。',
      source: 'deterministic_structural_parts',
    },
    enclosure_parameters: null,
    mounting_plan: [],
    layout_plan: scene,
    scene,
    structural_parts: scene.parts,
    printable_parts: printableParts,
    parameters: { scene_gap_mm: scene.gap_mm },
    project_default_parameters: { scene_gap_mm: scene.gap_mm },
    default_parameters: { scene_gap_mm: scene.gap_mm },
    validation_context: {
      design_mode: STRUCTURAL_PART_DESIGN_MODE,
      geometry_contract: STRUCTURAL_PARTS_SCHEMA_VERSION,
      enclosure_checks: 'skipped',
      electronic_function_checks: 'skipped',
      mesh_validation: 'available_after_cadquery_export',
    },
    conversation_route: conversationRoute,
    warnings,
    checks,
  };
}

function buildStructuralConfirmation({ intent, bom, designState, scene, checks, warnings }) {
  const printableParts = buildPrintableParts(scene);
  return {
    status: 'confirmation',
    design_mode: STRUCTURAL_PART_DESIGN_MODE,
    schema_version: STRUCTURAL_PARTS_SCHEMA_VERSION,
    title: `${intent.product_name} 参数确认`,
    message: '已按独立结构件流程完成母版检查和并排预览规划；不会添加主控，也不会生成盒体。确认后将建立可编辑的项目源码副本。',
    bom,
    partial_bom: bom,
    function_verification_report: designState.function_verification_report,
    design_state: designState,
    structural_scene: scene,
    scene,
    structural_parts: scene.parts,
    printable_parts: printableParts,
    preview_assets: buildStructuralPreviewAssets(scene),
    parameters: [{ id: 'structural_scene', label: '结构件预览', values: { scene_gap_mm: scene.gap_mm } }],
    checks,
    warnings,
    source: 'deterministic_structural_parts',
  };
}

async function persistStructuralArtifact({ body, context, intent, bom, profiles, scene, cadqueryCode, checks, warnings }) {
  const taskId = normalizeTaskId(body.taskId || body.task_id || body.currentDesignState?.id);
  const startedText = normalizeString(body.taskStartedAt || body.task_started_at || body.currentDesignState?.result_started_at);
  const startedDate = startedText ? new Date(startedText) : null;
  const allocation = await allocateResultDirectory({
    rootDir: context.rootDir,
    taskId,
    startedAt: startedDate && Number.isFinite(startedDate.getTime()) ? startedDate : new Date(),
  });
  if (allocation.status !== 'ok') {
    return needsInput('项目目录不可用', '无法安全分配独立结构件项目目录。', ['请检查项目存储状态后重试。'], 'result_directory_allocate_failed');
  }
  try {
    if (allocation.reused) {
      await clearManagedResultArtifacts({ rootDir: context.rootDir, resultId: allocation.resultId });
    }
    const designState = buildStructuralDesignState({
      designId: allocation.resultId,
      intent,
      bom,
      profiles,
      scene,
      checks,
      warnings,
      conversationRoute: body.conversationRoute || body.conversation_route || null,
    });
    designState.result_started_at = allocation.started_at;
    const printableParts = buildPrintableParts(scene);
    const exports = buildPendingStructuralExports({
      designId: allocation.resultId,
      scene,
      cadqueryAvailable: context.environment?.cadqueryAvailable,
    });
    const artifact = {
      status: 'artifact',
      design_mode: STRUCTURAL_PART_DESIGN_MODE,
      schema_version: STRUCTURAL_PARTS_SCHEMA_VERSION,
      title: `${intent.product_name} 结构件模型`,
      message: '已生成独立结构件项目：未添加主控、未执行电子功能验证、未生成盒体。各零件保持独立可打印，整体场景仅按 15 mm 间距并排预览。',
      bom,
      function_verification_report: designState.function_verification_report,
      design_state: designState,
      structural_scene: scene,
      scene,
      structural_parts: scene.parts,
      printable_parts: printableParts,
      cadquery_code: cadqueryCode,
      preview_assets: buildStructuralPreviewAssets(scene),
      exports,
      checks,
      warnings: [...warnings, ...(allocation.warning ? [allocation.warning] : [])],
      conversation_route: body.conversationRoute || body.conversation_route || null,
      source: 'deterministic_structural_parts',
    };
    artifact.design_state.printable_parts = printableParts;
    artifact.design_state.exports = exports;
    artifact.design_state.warnings = artifact.warnings;

    const sourceEntry = await writeProjectModelSourceFile({
      rootDir: context.rootDir,
      designId: allocation.resultId,
      artifact,
      filename: 'structural-parts.cq.py',
    });
    const defaultsEntry = await writeProjectDefaultParametersFile({
      rootDir: context.rootDir,
      designId: allocation.resultId,
      artifact,
    });
    artifact.exports = mergeExports(artifact.exports, [sourceEntry, defaultsEntry]);
    attachProjectState(artifact, sourceEntry, allocation.resultId);
    const metadata = await writeArtifactMetadataFiles({ rootDir: context.rootDir, designId: allocation.resultId, artifact });
    artifact.exports = mergeExports(artifact.exports, metadata);
    artifact.design_state.exports = artifact.exports;
    const workflow = await writeWorkflowArtifactFiles({ rootDir: context.rootDir, designId: allocation.resultId, artifact });
    artifact.exports = mergeExports(artifact.exports, workflow);
    artifact.design_state.exports = artifact.exports;
    await writeArtifactSnapshotFile({ rootDir: context.rootDir, designId: allocation.resultId, artifact });
    return artifact;
  } finally {
    releaseResultDirectoryLease({
      rootDir: context.rootDir,
      resultId: allocation.resultId,
      leaseToken: allocation.lease_token,
    });
    await cleanupResultDirectories({ rootDir: context.rootDir, keepCount: 3 }).catch(() => undefined);
  }
}

function buildStructuralChecks({ resolvedModels, scene, environment }) {
  const runtimeDetails = cadqueryRuntimeDetails(environment);
  return [
    { id: 'source_deterministic', label: '生成来源', status: 'pass', message: '结构件源码由后端固定程序从硬件库可信母版组合。' },
    { id: 'structural_templates', label: '结构件母版', status: 'pass', message: `${resolvedModels.length} 个结构件母版均已通过静态校验。` },
    { id: 'controller_independence', label: '主控独立性', status: 'pass', message: '独立结构件项目不要求主控，不会自动补充电子器件。' },
    { id: 'enclosure_generation', label: '盒体生成', status: 'pass', message: '已按设计模式跳过盒体尺寸、布局和外壳生成。' },
    { id: 'structural_scene_spacing', label: '预览间距', status: scene.gap_mm >= STRUCTURAL_PART_SCENE_GAP_MM ? 'pass' : 'fail', message: `结构件按 ${scene.gap_mm} mm 间距并排，仅用于预览。` },
    { id: 'cadquery_runtime', label: 'CadQuery 运行环境', status: environment?.cadqueryAvailable ? 'pass' : 'pending', message: cadqueryRuntimeMessage(environment, runtimeDetails), details: runtimeDetails },
    { id: 'mesh_validation', label: '真实 mesh 校验', status: 'pending', message: '各结构件 STL 导出后执行逐件 mesh 校验。' },
  ];
}

function buildStructuralWarnings({ profiles, environment }) {
  const warnings = [];
  if (!environment?.cadqueryAvailable) {
    warnings.push({ id: 'cadquery_missing', status: 'pending', message: '当前环境缺少 CadQuery/OCP；项目源码可保存，但真实 STEP/STL 导出暂不可用。' });
  }
  for (const profile of profiles) {
    if (/simplified|non[-_ ]?manufacturing|非制造级|简化/i.test(`${profile.source_status || ''} ${(profile.notes || []).join(' ')}`)) {
      warnings.push({ id: `structural_template_simplified_${profile.id}`, status: 'warn', hardware_id: profile.id, message: `${profile.name || profile.id} 是简化母版，制造前需要按实物复核。` });
    }
  }
  return warnings;
}

function buildPrintableParts(scene) {
  return scene.parts.map((part) => ({
    id: part.id,
    hardware_id: part.hardware_id,
    label: part.name,
    name: part.name,
    object_type: 'structural_part',
    model_type: 'structural_part',
    quantity: 1,
    cadquery_object_key: part.id,
    source_export_id: `cadquery_structural_${part.id}_stl`,
    printable: true,
    scene_placement_mm: part.placement_mm,
    scene_placement_purpose: 'preview_only',
  }));
}

function buildStructuralPreviewAssets(scene) {
  return [{
    id: 'structural_parts_scene',
    type: 'structural_parts_scene',
    schema_version: STRUCTURAL_PARTS_SCHEMA_VERSION,
    units: 'mm',
    gap_mm: scene.gap_mm,
    parts: scene.parts,
    modes: {
      assembly: { label: '整体预览', part_ids: scene.parts.map((part) => part.id) },
      parts: scene.parts.map((part) => ({ id: part.id, label: part.name, part_ids: [part.id] })),
    },
  }];
}

function buildPendingStructuralExports({ designId, scene, cadqueryAvailable }) {
  const status = cadqueryAvailable ? 'not_generated_yet' : 'pending_missing_cadquery';
  return [
    { id: 'cadquery_structural_scene_step', label: '结构件整体预览 STEP', format: 'step', url: null, status, fidelity: 'cadquery', printable: false, scene_only: true },
    { id: 'cadquery_structural_scene_stl', label: '结构件整体预览 STL', format: 'stl', url: null, status, fidelity: 'cadquery', printable: false, scene_only: true },
    ...scene.parts.flatMap((part) => [
      { id: `cadquery_structural_${part.id}_step`, label: `${part.name} STEP`, format: 'step', url: null, status, fidelity: 'cadquery', printable_part_id: part.id },
      { id: `cadquery_structural_${part.id}_stl`, label: `${part.name} STL`, format: 'stl', url: null, status, fidelity: 'cadquery', printable_part_id: part.id },
    ]),
  ].map((item) => ({ ...item, design_id: designId }));
}

function attachProjectState(artifact, sourceEntry, designId) {
  const state = {
    project_id: designId,
    project_manifest: sourceEntry.project_manifest || null,
    project_revision: sourceEntry.project_revision || 1,
    project_source_hash: sourceEntry.source_hash || '',
    model_index: sourceEntry.model_index || null,
    project_memory_summary: sourceEntry.project_memory_summary || '',
    model_edit_history: sourceEntry.model_edit_history || [],
  };
  Object.assign(artifact, state);
  Object.assign(artifact.design_state, state);
}

function normalizeDimensions(value = {}) {
  return {
    length_x: positive(value.length_x ?? value.width, 1),
    width_y: positive(value.width_y ?? value.depth, 1),
    height_z: positive(value.height_z ?? value.height, 1),
  };
}

function positive(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function createStructuralDesignId(value) {
  return `structural_${crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, 16)}`;
}

function safePythonIdentifier(value) {
  const text = String(value || 'part').replace(/[^a-zA-Z0-9_]/g, '_');
  return /^[a-zA-Z_]/.test(text) ? text : `part_${text}`;
}

function uniqueStrings(values) {
  return [...new Set(values.map((value) => normalizeString(value)).filter(Boolean))];
}

function round(value) {
  return Math.round(Number(value) * 1000) / 1000;
}

function mergeExports(existing = [], incoming = []) {
  const result = new Map();
  for (const item of [...existing, ...incoming]) {
    if (!item) continue;
    result.set(item.id || item.url || item.path || JSON.stringify(item), item);
  }
  return [...result.values()];
}

function needsInput(title, message, questions, blockingReason) {
  return {
    status: 'needs_input',
    design_mode: STRUCTURAL_PART_DESIGN_MODE,
    title,
    message,
    questions,
    blocking_reason: blockingReason,
    source: 'deterministic_structural_parts',
  };
}
