import { createHardwareResolver } from '../hardware-library.js';
import {
  isFiniteNumber,
  isNonNegativeNumber,
  isPlainObject,
  isPositiveNumber,
  normalizeString,
  normalizeStringArray,
  SUPPORTED_MOUNT_SURFACES,
} from './shared.js';

export const DEFAULT_HARDWARE_SYSTEM = 'xiao';
export const COMMON_HARDWARE_SYSTEM = 'common';
export const USER_CUSTOM_HARDWARE_SYSTEM = 'user_custom';
const DEFAULT_CONTROLLER_BY_HARDWARE_SYSTEM = Object.freeze({
  xiao: 'xiao_esp32s3',
  unihiker: 'unihiker_k10',
});

export function hardwareBomTool({ intent, selectedHardwareIds = [], hardwareResolver = createHardwareResolver() }) {
  const bom = [];
  const warnings = [];
  const effectiveSelectedHardwareIds = collectSelectedHardwareIds(intent, selectedHardwareIds);
  const selectedProfiles = hardwareResolver.getHardwareProfiles(effectiveSelectedHardwareIds);
  const selectedSystemCheck = validateSingleBrandSystem(selectedProfiles);
  if (selectedSystemCheck.status !== 'ok') {
    return buildHardwareSystemConflictResponse(selectedSystemCheck, {
      bom,
      warnings,
      missingHardwareRequests: [],
    });
  }
  if (normalizeString(intent.design_mode || intent.designMode) === 'structural_part_project') {
    const structuralProfiles = selectedProfiles.filter((profile) => isStandaloneStructuralProfile(profile));
    if (structuralProfiles.length !== selectedProfiles.length || !structuralProfiles.length) {
      return {
        status: 'needs_input',
        bom: [],
        warnings,
        missing_hardware_requests: [],
        message: '独立结构件项目只能使用通用件库中标记为 structural_part 的条目。',
        questions: ['请选择至少一个通用结构件，并移除电子元器件或品牌专属硬件。'],
        blocking_reason: 'invalid_structural_part_selection',
        hardware_system: COMMON_HARDWARE_SYSTEM,
      };
    }
    return {
      status: 'ok',
      bom: structuralProfiles.map((profile) => createBomItem({
        profile,
        role: 'structural_part',
        whyNeeded: '用户选择了该通用结构件作为独立建模对象。',
      })),
      missing_hardware_requests: [],
      warnings,
      hardware_system: COMMON_HARDWARE_SYSTEM,
      design_mode: 'structural_part_project',
    };
  }
  const projectHardwareSystem = resolveProjectHardwareSystem({ intent, selectedProfiles, hardwareResolver });
  const usedIds = new Set();

  for (const profile of selectedProfiles) {
    if (usedIds.has(profile.id)) continue;
    bom.push(createBomItem({
      profile,
      role: profile.category,
      whyNeeded: '用户已在硬件库中选择该硬件。',
    }));
    usedIds.add(profile.id);
  }

  const requiredRoles = (intent.required_hardware_roles || []).filter((role) => !isEnclosureHardwareRole(role));
  const missingHardwareRequests = [];
  for (const required of requiredRoles) {
    if (isRoleSatisfied(required, bom, hardwareResolver)) continue;
    const profile = chooseHardwareForRole(required, intent, hardwareResolver, {
      hardwareSystem: projectHardwareSystem,
    });
    if (!profile) {
      missingHardwareRequests.push(buildMissingHardwareRequest(required));
      continue;
    }
    bom.push(createBomItem({
      profile,
      role: required.role,
      whyNeeded: required.why_needed,
    }));
    usedIds.add(profile.id);
  }

  if (missingHardwareRequests.length) {
    const labels = missingHardwareRequests.map((item) => item.label).join('、');
    const functionHardwarePairs = missingHardwareRequests
      .map((item) => `${item.function || item.label || item.role} -> ${item.label || item.role}`)
      .join('；');
    const availableHardware = bom.map((item) => item.name || item.hardware_id).filter(Boolean).join('、');
    return {
      status: 'needs_input',
      bom,
      warnings,
      missing_hardware_requests: missingHardwareRequests,
      message: `硬件库中没有能满足「${labels}」的硬件。无法覆盖的功能/硬件：${functionHardwarePairs}。${availableHardware ? `当前已能选出的库内硬件：${availableHardware}。` : ''}不能编造尺寸继续建模。`,
      questions: [
        `请按硬件库 profile 格式补充「${labels}」的尺寸、安装、开孔、避让和参考模型参数。`,
        `或者砍掉/替换这些功能，改用硬件库已有硬件。`,
      ],
      blocking_reason: 'missing_hardware',
    };
  }

  if (!bom.some((item) => hardwareResolver.getHardwareProfile(item.hardware_id)?.category === 'controller')) {
    const fallback = getDefaultControllerForHardwareSystem(hardwareResolver, projectHardwareSystem);
    if (!fallback) {
      const missingController = buildMissingHardwareRequest({
        role: 'controller',
        category: 'controller',
        function: 'main controller',
        label: `${projectHardwareSystem} controller`,
        why_needed: 'A controller is required, but the active hardware system has no matching default controller.',
      });
      return {
        status: 'needs_input',
        bom,
        warnings,
        missing_hardware_requests: [missingController],
        message: `Active hardware system "${projectHardwareSystem}" has no matching default controller.`,
        questions: [
          `Please add a controller profile for hardware_system="${projectHardwareSystem}", or switch the project hardware system.`,
        ],
        blocking_reason: 'missing_hardware',
        hardware_system: projectHardwareSystem,
      };
    }
    bom.unshift(createBomItem({
      profile: fallback,
      role: 'controller',
      whyNeeded: '用户没有指定主控，程序按当前硬件体系选择默认主控。',
    }));
    warnings.push({
      id: 'auto_selected_controller',
      status: 'warn',
      message: '主控由程序按当前硬件体系自动选择。制造前建议用户确认是否就是这个型号。',
    });
  }

  const bomSystemCheck = validateBomHardwareSystems(bom, hardwareResolver);
  if (bomSystemCheck.status !== 'ok') {
    return buildHardwareSystemConflictResponse(bomSystemCheck, {
      bom,
      warnings,
      missingHardwareRequests: [],
    });
  }

  return {
    status: 'ok',
    bom,
    missing_hardware_requests: [],
    warnings,
    hardware_system: projectHardwareSystem,
  };
}

export function hardwareProfileTool(bom, { hardwareResolver = createHardwareResolver() } = {}) {
  const hardwareProfiles = [];
  const warnings = [];
  const profileReports = [];
  for (const item of bom) {
    const profile = hardwareResolver.getHardwareProfile(item.hardware_id);
    if (!profile) {
      return {
        status: 'needs_input',
        message: `找不到硬件 profile：${item.hardware_id}`,
        questions: ['请从硬件库选择已有硬件，或按 profile 格式补充硬件参数。'],
      };
    }
    const issues = findInvalidProfileFields(profile);
    const profileSummary = buildProfileValidationSummary(profile, issues);
    if (issues.length) {
      return {
        status: 'needs_input',
        profile_validation_report: {
          status: 'fail',
          checked_count: 1,
          required_fields_checked: REQUIRED_PROFILE_FIELDS,
          issue_categories: PROFILE_ISSUE_CATEGORIES,
          profiles: [profileSummary],
        },
        required_profile_fields: buildRequiredProfileFields(),
        profile_template: buildProfileTemplate({
          role: item.role,
          category: profile.category,
          function: profile.name || item.hardware_id,
        }),
        message: `${profile.name || item.hardware_id} profile 字段缺失或无效：${issues.join(', ')}`,
        questions: ['请补齐或修正 dimensions_mm、coordinate_system、mounting、opening、keepouts、cad_reference 等结构化参数。'],
      };
    }
    if (isPendingHardwareProfile(profile)) {
      warnings.push({
        id: `profile_pending_${profile.id}`,
        status: 'pending',
        hardware_id: profile.id,
        message: `${profile.name} 存在暂定数据，可以预览，但制造前需要用户确认。`,
      });
    }
    hardwareProfiles.push(profile);
    profileReports.push(profileSummary);
  }
  return {
    status: 'ok',
    hardware_profiles: hardwareProfiles,
    profile_validation_report: {
      status: summarizeProfileReportStatus(profileReports),
      checked_count: hardwareProfiles.length,
      required_fields_checked: REQUIRED_PROFILE_FIELDS,
      issue_categories: PROFILE_ISSUE_CATEGORIES,
      profiles: profileReports,
    },
    warnings,
  };
}

export function summarizeProfileReportStatus(profileReports = []) {
  if (profileReports.some((item) => item.status === 'fail')) return 'fail';
  if (profileReports.some((item) => item.status === 'pending')) return 'pending';
  return 'pass';
}

export function orientationTool({ mountingIntents, hardwareProfiles }) {
  const intentsById = new Map((mountingIntents || []).map((item) => [item.hardware_id, item]));
  const oriented = hardwareProfiles.map((profile) => {
    const intent = intentsById.get(profile.id) || {};
    const targetFace = intent.target_face || defaultFaceForProfile(profile);
    const mountingHoles = normalizeMountingHoles(profile);
    const mountingStrategy = resolveMountingStrategy(profile, mountingHoles);
    return {
      hardware_id: profile.id,
      name: profile.name,
      category: profile.category,
      target_face: targetFace,
      interaction_face: intent.interaction_face || defaultInteractionFace(profile),
      mating_face: profile.mounting?.mating_hardware_face || '-Z',
      rotation: deterministicRotationForFace(targetFace),
      bounding_box: {
        length_x: profile.dimensions_mm.length_x,
        width_y: profile.dimensions_mm.width_y,
        height_z: profile.dimensions_mm.height_z,
      },
      dimensions_mm: profile.dimensions_mm,
      coordinate_system: profile.coordinate_system || {},
      cad_reference: profile.cad_reference || {},
      openings: profile.opening || [],
      keepouts: profile.keepouts || [],
      mounting: profile.mounting,
      legacy_reference: profile.legacy_reference || {},
      mounting_strategy: mountingStrategy,
      mounting_holes: mountingHoles,
    };
  });
  return {
    oriented_hardware_specs: oriented,
    mounting_plan: oriented.map((item) => ({
      hardware_id: item.hardware_id,
      target_face: item.target_face,
      interaction_face: item.interaction_face,
      rotation: item.rotation,
      mounting_strategy: item.mounting_strategy,
      generated_by: 'orientation_tool',
    })),
  };
}

export function applyHardwareFaceOverrides(oriented, hardwareFaceOverrides = {}) {
  const overrideEntries = Object.entries(hardwareFaceOverrides);
  if (!overrideEntries.length) return oriented;
  const specs = oriented.oriented_hardware_specs.map((spec) => {
    const targetFace = hardwareFaceOverrides[spec.hardware_id];
    if (!targetFace) return spec;
    return {
      ...spec,
      target_face: targetFace,
      rotation: deterministicRotationForFace(targetFace),
    };
  });
  return {
    ...oriented,
    oriented_hardware_specs: specs,
    mounting_plan: specs.map((item) => ({
      hardware_id: item.hardware_id,
      target_face: item.target_face,
      interaction_face: item.interaction_face,
      rotation: item.rotation,
      mating_face: item.mating_face,
      mounting_strategy: item.mounting_strategy,
    })),
  };
}

export function applyHardwareRotationOverrides(oriented, hardwareRotationOverrides = {}) {
  const overrideEntries = Object.entries(hardwareRotationOverrides);
  if (!overrideEntries.length) return oriented;
  const specs = oriented.oriented_hardware_specs.map((spec) => {
    const rotationDeg = hardwareRotationOverrides[spec.hardware_id];
    if (!Number.isFinite(rotationDeg)) return spec;
    const rotated = rotationDeg % 180 !== 0;
    return {
      ...spec,
      layout_rotation_deg: rotationDeg,
      bounding_box: rotated
        ? {
            length_x: spec.bounding_box.width_y,
            width_y: spec.bounding_box.length_x,
            height_z: spec.bounding_box.height_z,
          }
        : { ...spec.bounding_box },
    };
  });
  return {
    ...oriented,
    oriented_hardware_specs: specs,
    mounting_plan: specs.map((item) => ({
      hardware_id: item.hardware_id,
      target_face: item.target_face,
      interaction_face: item.interaction_face,
      rotation: item.rotation,
      layout_rotation_deg: item.layout_rotation_deg || 0,
      mating_face: item.mating_face,
      mounting_strategy: item.mounting_strategy,
    })),
  };
}

export function createBomItem({ profile, role, whyNeeded }) {
  return {
    hardware_id: profile.id,
    name: profile.name,
    role,
    hardware_system: profile.hardware_system || COMMON_HARDWARE_SYSTEM,
    quantity: 1,
    required_or_optional: 'required',
    why_needed: whyNeeded,
    profile_status: profile.source_status,
    mounting_intent: {
      preferred_surface: profile.mounting?.preferred_enclosure_surface || 'base_floor',
      opening_count: (profile.opening || []).length,
    },
  };
}

export function buildMissingHardwareRequest(required = {}) {
  return buildProfileMissingHardwareRequest(required);
}

export function buildProfileMissingHardwareRequest(required = {}) {
  const functionName = normalizeString(required.function) || normalizeString(required.role) || '未知功能';
  const label = normalizeString(required.label) || functionName || '未知硬件';
  return {
    role: normalizeString(required.role),
    category: normalizeString(required.category) || 'unknown',
    function: functionName,
    label,
    why_needed: normalizeString(required.why_needed) || '用户需求中需要该硬件能力。',
    options: [
      '按模板补全硬件 profile 后继续建模。',
      '删除或替换这个功能，改用硬件库已有硬件。',
    ],
    required_profile_fields: buildRequiredProfileFields(),
    profile_template: buildProfileTemplate(required),
  };
}

export function buildRequiredProfileFields() {
  return [
    'id',
    'name',
    'category',
    'roles',
    'dimensions_mm.length_x',
    'dimensions_mm.width_y',
    'dimensions_mm.height_z',
    'coordinate_system.origin',
    'coordinate_system.x_axis',
    'coordinate_system.y_axis',
    'coordinate_system.positive_z',
    'mounting.mode',
    'mounting.mating_hardware_face',
    'mounting.preferred_enclosure_surface',
    'mounting.clearance_mm',
    'mounting.retainer_height_mm',
    'mounting.holes[].x',
    'mounting.holes[].y',
    'mounting.holes[].diameter_mm',
    'opening[].id',
    'opening[].type',
    'opening[].basis',
    'opening[].preferred_face',
    'opening[].center_mm or opening[].offset_mm',
    'opening[].clearance_mm',
    'keepouts[].id',
    'keepouts[].shape',
    'keepouts[].size_mm/diameter_mm',
    'keepouts[].center_mm',
    'cad_reference.shape',
    'cad_reference.color',
    'source_status',
  ];
}

export function buildProfileTemplate(required = {}) {
  const role = normalizeString(required.role) || 'custom_hardware';
  const safeRole = role.replace(/[^a-zA-Z0-9_]+/g, '_') || 'custom_hardware';
  const label = normalizeString(required.function) || role || 'custom hardware';
  const category = normalizeString(required.category) || 'sensor';
  return {
    id: `user_${safeRole}_module`,
    name: `User supplied ${label} module`,
    category,
    roles: [role].filter(Boolean),
    dimensions_mm: {
      length_x: 'number_mm',
      width_y: 'number_mm',
      height_z: 'number_mm',
    },
    coordinate_system: {
      origin: 'pcb_center',
      x_axis: 'board length',
      y_axis: 'board width',
      positive_z: 'front/component side',
    },
    mounting: {
      mode: 'tray_with_side_retainers',
      mating_hardware_face: '-Z',
      preferred_enclosure_surface: category === 'controller' || category === 'power' ? 'base_floor' : 'lid_inner',
      clearance_mm: 0.8,
      retainer_height_mm: shouldRequireMountingHolesForCategory(category) ? 0 : 2,
      holes: shouldRequireMountingHolesForCategory(category)
        ? [
            { x: -10, y: 0, diameter_mm: 2.1 },
            { x: 10, y: 0, diameter_mm: 2.1 },
          ]
        : [],
      fixed_structure: {
        type: shouldRequireMountingHolesForCategory(category) ? 'shell_through_screw_holes' : 'support_tray_and_side_retainers',
        min_feature_mm: 1.0,
        tray_thickness_mm: 1.4,
        service_clearance_mm: 1.2,
      },
    },
    opening: [
      {
        id: 'primary_access',
        type: 'round_hole',
        basis: 'functional_center',
        preferred_face: category === 'controller' || category === 'power' ? 'left' : 'top',
        center_mm: {
          x: 0,
          y: 0,
          z: 0,
        },
        diameter_mm: 'number_mm_or_delete_if_unused',
        clearance_mm: 0.8,
      },
    ],
    keepouts: [
      {
        id: 'service_clearance',
        shape: 'box',
        size_mm: {
          length_x: 'number_mm',
          width_y: 'number_mm',
          height_z: 'number_mm',
        },
        center_mm: {
          x: 0,
          y: 0,
          z: 'number_mm',
        },
        purpose: 'connector/service/removal clearance',
      },
    ],
    cad_reference: {
      shape: 'simple_box_reference',
      color: '#334455',
    },
    source_status: 'user supplied temporary profile; not written to hardware library',
  };
}

export function buildLegacyMissingHardwareRequestTemplate(required = {}) {
  const label = normalizeString(required.function) || normalizeString(required.role) || '未知硬件';
  const safeRole = normalizeString(required.role).replace(/[^a-zA-Z0-9_]+/g, '_') || 'custom_hardware';
  return {
    role: normalizeString(required.role),
    category: normalizeString(required.category) || 'unknown',
    function: normalizeString(required.function),
    label,
    why_needed: normalizeString(required.why_needed) || '用户需求中需要该硬件能力。',
    options: [
      '按模板补充硬件 profile 后继续建模。',
      '删除或替换这个功能，改用硬件库已有硬件。',
    ],
    required_profile_fields: [
      'id',
      'name',
      'category',
      'roles',
      'dimensions_mm.length_x',
      'dimensions_mm.width_y',
      'dimensions_mm.height_z',
      'coordinate_system',
      'mounting',
      'opening',
      'keepouts',
      'cad_reference',
      'source_status',
    ],
    profile_template: {
      id: `user_${safeRole}_module`,
      name: `用户提供${label}模块`,
      category: normalizeString(required.category) || 'sensor',
      roles: [normalizeString(required.role)].filter(Boolean),
      dimensions_mm: {
        length_x: '请填写毫米数',
        width_y: '请填写毫米数',
        height_z: '请填写毫米数',
      },
      coordinate_system: {
        origin: 'pcb_center',
        x_axis: 'board length',
        y_axis: 'board width',
        positive_z: 'front/component side',
      },
      mounting: {
        mode: '请填写固定方式，例如 tray_with_retainers',
        mating_hardware_face: '+Z 或 -Z',
        preferred_enclosure_surface: 'lid_inner、lid_outer 或 base_floor',
        clearance_mm: '请填写装配间隙',
      },
      opening: [],
      keepouts: [],
      cad_reference: {
        shape: 'simple_box_reference',
        color: '#334455',
      },
      source_status: '用户待补充，未写入硬件库',
    },
  };
}

export function isRoleSatisfied(required, bom, hardwareResolver = createHardwareResolver()) {
  const requiredRole = normalizeString(required.role);
  const aliases = roleAliases(requiredRole);
  return bom.some((item) => {
    const profile = hardwareResolver.getHardwareProfile(item.hardware_id);
    if (!profile) return false;
    const profileRoles = profile.roles || [];
    if (item.role === requiredRole) return true;
    if (profile.category === requiredRole) return true;
    if (profileRoles.includes(requiredRole)) return true;
    return aliases.some((alias) => profile.category === alias || profileRoles.includes(alias));
  });
}

export function roleAliases(role) {
  return {
    controller: ['compute'],
    temperature_humidity_sensor: ['temperature', 'humidity'],
    soil_moisture_sensor: ['soil_moisture', 'moisture'],
    buzzer: ['sound'],
    battery: ['power'],
    camera_sensor: ['camera'],
    distance_sensor: ['distance', 'ultrasonic'],
    motion_sensor: ['motion', 'pir'],
    proximity_sensor: ['distance', 'ultrasonic', 'pir'],
    servo: ['actuator', 'motion'],
    lid_actuator: ['servo', 'actuator'],
  }[role] || [];
}

export function collectSelectedHardwareIds(intent = {}, selectedHardwareIds = []) {
  return [
    ...new Set([
      ...normalizeStringArray(selectedHardwareIds),
      ...normalizeStringArray(intent.selected_hardware_ids),
      ...normalizeStringArray(intent.selectedHardwareIds),
    ]),
  ];
}

export function getDefaultControllerForHardwareSystem(
  hardwareResolver = createHardwareResolver(),
  hardwareSystem = DEFAULT_HARDWARE_SYSTEM,
) {
  const normalizedSystem = normalizeHardwareSystem(hardwareSystem || DEFAULT_HARDWARE_SYSTEM);
  const profileId = DEFAULT_CONTROLLER_BY_HARDWARE_SYSTEM[normalizedSystem] || '';
  return profileId ? getHardwareProfileForSystem(hardwareResolver, profileId, normalizedSystem) : null;
}

export function chooseHardwareForRole(
  required = {},
  intent = {},
  hardwareResolver = createHardwareResolver(),
  options = {},
) {
  const requiredRole = normalizeString(required.role);
  const hardwareSystem = normalizeHardwareSystem(options.hardwareSystem || intent.hardware_system || DEFAULT_HARDWARE_SYSTEM);
  const customProfiles = typeof hardwareResolver.listCustomProfiles === 'function'
    ? hardwareResolver.listCustomProfiles()
    : [];
  const customMatch = findMatchingHardwareProfile(customProfiles, requiredRole, required, { hardwareSystem });
  if (customMatch) return customMatch;
  if (required.unsupported_in_library) return null;
  if (requiredRole === 'controller') {
    if (hardwareSystem === 'unihiker') {
      return getHardwareProfileForSystem(hardwareResolver, 'unihiker_k10', hardwareSystem);
    }
    if (/nrf52840/i.test(intent.user_constraints?.raw_prompt || '')) {
      return filterProfileForHardwareSystem(
        hardwareResolver.getHardwareProfile('xiao_nrf52840_sense'),
        hardwareSystem,
      );
    }
    return filterProfileForHardwareSystem(
      hardwareResolver.getHardwareProfile('xiao_esp32s3'),
      hardwareSystem,
    );
  }
  if (requiredRole === 'display') return getHardwareProfileForSystem(hardwareResolver, 'grove_oled_096', hardwareSystem);
  if (requiredRole === 'dual_button') return getHardwareProfileForSystem(hardwareResolver, 'grove_dual_button', hardwareSystem);
  if (requiredRole === 'button') return getHardwareProfileForSystem(hardwareResolver, 'grove_button', hardwareSystem);
  if (requiredRole === 'buzzer') return getHardwareProfileForSystem(hardwareResolver, 'grove_passive_buzzer', hardwareSystem);
  if (requiredRole === 'temperature_humidity_sensor') return getHardwareProfileForSystem(hardwareResolver, 'grove_sht4x', hardwareSystem);
  if (requiredRole === 'battery') {
    const systemBattery = hardwareSystem === 'unihiker'
      ? getHardwareProfileForSystem(hardwareResolver, 'unihiker_polymer_lipo_battery', hardwareSystem)
      : null;
    return systemBattery || getHardwareProfileForSystem(hardwareResolver, 'battery_18650_holder', hardwareSystem);
  }
  if (requiredRole === 'servo' || requiredRole === 'lid_actuator') {
    const systemMatch = hardwareSystem === 'unihiker'
      ? getHardwareProfileForSystem(hardwareResolver, 'unihiker_servo', hardwareSystem)
      : null;
    return systemMatch || getHardwareProfileForSystem(hardwareResolver, 'mg90s_servo', hardwareSystem);
  }
  if (requiredRole === 'proximity_sensor' || requiredRole === 'distance_sensor') {
    const systemMatch = hardwareSystem === 'unihiker'
      ? findMatchingHardwareProfile(hardwareResolver.listProfiles(), requiredRole, required, { hardwareSystem })
      : null;
    return systemMatch
      || getHardwareProfileForSystem(hardwareResolver, 'grove_ultrasonic_ranger', hardwareSystem)
      || getHardwareProfileForSystem(hardwareResolver, 'grove_digital_pir', hardwareSystem);
  }
  if (requiredRole === 'motion_sensor') {
    return getHardwareProfileForSystem(hardwareResolver, 'grove_digital_pir', hardwareSystem);
  }
  return findMatchingHardwareProfile(hardwareResolver.listProfiles(), requiredRole, required, { hardwareSystem });
}

export function findMatchingHardwareProfile(profiles = [], requiredRole = '', required = {}, options = {}) {
  const aliases = roleAliases(requiredRole);
  const hardwareSystem = normalizeHardwareSystem(options.hardwareSystem || '');
  return profiles.find((profile) => {
    if (!isProfileAllowedForHardwareSystem(profile, hardwareSystem)) return false;
    const profileRoles = profile.roles || [];
    if (required.category && profile.category !== required.category) return false;
    if (profile.category === requiredRole) return true;
    if (profileRoles.includes(requiredRole)) return true;
    return aliases.some((alias) => profile.category === alias || profileRoles.includes(alias));
  }) || null;
}

export function resolveProjectHardwareSystem({
  intent = {},
  selectedProfiles = [],
  hardwareResolver = createHardwareResolver(),
} = {}) {
  const explicitSystem = normalizeHardwareSystem(intent.hardware_system || intent.hardwareSystem);
  if (explicitSystem && explicitSystem !== COMMON_HARDWARE_SYSTEM) return explicitSystem;
  const selectedCheck = validateSingleBrandSystem(selectedProfiles);
  if (selectedCheck.status === 'ok' && selectedCheck.brand_system) return selectedCheck.brand_system;
  const intentProfiles = hardwareResolver.getHardwareProfiles([
    ...(Array.isArray(intent.selected_hardware_ids) ? intent.selected_hardware_ids : []),
    ...(Array.isArray(intent.selectedHardwareIds) ? intent.selectedHardwareIds : []),
  ]);
  const intentCheck = validateSingleBrandSystem(intentProfiles);
  if (intentCheck.status === 'ok' && intentCheck.brand_system) return intentCheck.brand_system;
  return DEFAULT_HARDWARE_SYSTEM;
}

export function getHardwareProfileForSystem(hardwareResolver, id, hardwareSystem = DEFAULT_HARDWARE_SYSTEM) {
  return filterProfileForHardwareSystem(hardwareResolver.getHardwareProfile(id), hardwareSystem);
}

export function filterProfileForHardwareSystem(profile, hardwareSystem = DEFAULT_HARDWARE_SYSTEM) {
  return isProfileAllowedForHardwareSystem(profile, hardwareSystem) ? profile : null;
}

export function isProfileAllowedForHardwareSystem(profile, hardwareSystem = DEFAULT_HARDWARE_SYSTEM) {
  if (!profile) return false;
  const profileSystem = normalizeHardwareSystem(profile.hardware_system);
  const projectSystem = normalizeHardwareSystem(hardwareSystem || DEFAULT_HARDWARE_SYSTEM);
  return profileSystem === COMMON_HARDWARE_SYSTEM
    || profileSystem === USER_CUSTOM_HARDWARE_SYSTEM
    || profileSystem === projectSystem;
}

export function validateBomHardwareSystems(bom = [], hardwareResolver = createHardwareResolver()) {
  const profiles = bom
    .map((item) => hardwareResolver.getHardwareProfile(item.hardware_id))
    .filter(Boolean);
  return validateSingleBrandSystem(profiles);
}

export function validateSingleBrandSystem(profiles = []) {
  const brandSystems = new Map();
  for (const profile of profiles) {
    const hardwareSystem = normalizeHardwareSystem(profile?.hardware_system);
    if (!hardwareSystem || hardwareSystem === COMMON_HARDWARE_SYSTEM || hardwareSystem === USER_CUSTOM_HARDWARE_SYSTEM) continue;
    if (!brandSystems.has(hardwareSystem)) brandSystems.set(hardwareSystem, []);
    brandSystems.get(hardwareSystem).push(profile.id);
  }
  if (brandSystems.size <= 1) {
    return {
      status: 'ok',
      brand_system: [...brandSystems.keys()][0] || '',
      brand_systems: [...brandSystems.keys()],
      conflicts: [],
    };
  }
  return {
    status: 'conflict',
    brand_system: '',
    brand_systems: [...brandSystems.keys()],
    conflicts: [...brandSystems.entries()].map(([hardware_system, hardware_ids]) => ({
      hardware_system,
      hardware_ids,
    })),
  };
}

export function buildHardwareSystemConflictResponse(
  systemCheck = {},
  { bom = [], warnings = [], missingHardwareRequests = [] } = {},
) {
  const systems = (systemCheck.brand_systems || []).join(', ');
  const conflicts = systemCheck.conflicts || [];
  return {
    status: 'needs_input',
    bom,
    warnings,
    missing_hardware_requests: missingHardwareRequests,
    hardware_system_conflict: {
      status: 'conflict',
      brand_systems: systemCheck.brand_systems || [],
      conflicts,
    },
    message: `当前项目同时选择了多个硬件品牌体系：${systems}。单次生成只能使用一个品牌体系，并可搭配 common 通用件和用户自定义硬件。`,
    questions: [
      '请只保留 XIAO、掌控板或行空板中的一个品牌体系；common 通用件和 user_custom 用户自定义硬件可以保留。',
    ],
    blocking_reason: 'mixed_hardware_systems',
  };
}

export function normalizeHardwareSystem(value) {
  return normalizeString(value).toLowerCase();
}

export const REQUIRED_PROFILE_FIELDS = Object.freeze([
  'id',
  'name',
  'category',
  'dimensions_mm',
  'coordinate_system',
  'mounting',
  'opening',
  'keepouts',
  'cad_reference',
  'source_status',
]);

export const PROFILE_ISSUE_CATEGORIES = Object.freeze([
  'missing_required',
  'invalid_dimensions',
  'mounting_issues',
  'opening_issues',
  'keepout_issues',
  'manufacturing_pending',
]);

export function findInvalidProfileFields(profile) {
  return flattenProfileIssues(validateProfileContract(profile));
}

export function validateProfileContract(profile) {
  const report = createProfileIssueReport();
  for (const field of REQUIRED_PROFILE_FIELDS) {
    if (!(field in profile)) addProfileIssue(report, 'missing_required', field);
  }
  for (const field of ['id', 'name', 'category', 'source_status']) {
    if (field in profile && !normalizeString(profile[field])) addProfileIssue(report, 'missing_required', field);
  }
  if (!isPlainObject(profile.dimensions_mm)) {
    addProfileIssue(report, 'invalid_dimensions', 'dimensions_mm');
  } else {
    for (const field of ['length_x', 'width_y', 'height_z']) {
      if (!isPositiveNumber(profile.dimensions_mm[field])) addProfileIssue(report, 'invalid_dimensions', `dimensions_mm.${field}`);
    }
  }
  if (!isPlainObject(profile.coordinate_system)) {
    addProfileIssue(report, 'missing_required', 'coordinate_system');
  } else {
    for (const field of ['origin', 'x_axis', 'y_axis', 'positive_z']) {
      if (!normalizeString(profile.coordinate_system[field])) addProfileIssue(report, 'missing_required', `coordinate_system.${field}`);
    }
  }
  if (!isPlainObject(profile.mounting)) {
    addProfileIssue(report, 'mounting_issues', 'mounting');
  } else {
    const mountingMode = normalizeString(profile.mounting.mode).toLowerCase();
    const isExternalIndependentModule = mountingMode === 'external_independent_module';
    if (!mountingMode) addProfileIssue(report, 'mounting_issues', 'mounting.mode');
    if (!isExternalIndependentModule) {
      for (const field of ['mating_hardware_face', 'preferred_enclosure_surface']) {
        if (!normalizeString(profile.mounting[field])) addProfileIssue(report, 'mounting_issues', `mounting.${field}`);
      }
    }
    if (isExternalIndependentModule) {
      const clearance = profile.mounting.clearance_mm;
      const hasValidClearance = Object.hasOwn(profile.mounting, 'clearance_mm')
        && typeof clearance === 'number'
        && isNonNegativeNumber(clearance);
      if (!hasValidClearance) addProfileIssue(report, 'mounting_issues', 'mounting.clearance_mm');
    } else if (!isPositiveNumber(profile.mounting.clearance_mm)) {
      addProfileIssue(report, 'mounting_issues', 'mounting.clearance_mm');
    }
    if ('retainer_height_mm' in profile.mounting && !isNonNegativeNumber(profile.mounting.retainer_height_mm)) {
      addProfileIssue(report, 'mounting_issues', 'mounting.retainer_height_mm');
    }
    const preferredSurface = normalizeString(profile.mounting.preferred_enclosure_surface);
    if ((!isExternalIndependentModule || preferredSurface)
      && !SUPPORTED_MOUNT_SURFACES.includes(preferredSurface)) {
      addProfileIssue(report, 'mounting_issues', 'mounting.preferred_enclosure_surface');
    }
    validateMountingFeatureDefinition(profile.mounting, report);
    validateMountingHolesForProfile(profile, report);
  }
  if (!Array.isArray(profile.opening)) {
    addProfileIssue(report, 'opening_issues', 'opening');
  } else {
    for (const [index, opening] of profile.opening.entries()) {
      for (const issue of validateOpeningDefinition(opening, index)) {
        addProfileIssue(report, 'opening_issues', issue);
      }
    }
  }
  if (!Array.isArray(profile.keepouts)) {
    addProfileIssue(report, 'keepout_issues', 'keepouts');
  } else {
    for (const [index, keepout] of profile.keepouts.entries()) {
      for (const issue of validateKeepoutDefinition(keepout, index)) {
        addProfileIssue(report, 'keepout_issues', issue);
      }
    }
  }
  if (!isPlainObject(profile.cad_reference)) addProfileIssue(report, 'missing_required', 'cad_reference');
  if (isPendingHardwareProfile(profile)) {
    addProfileIssue(report, 'manufacturing_pending', 'source_status');
  }
  return report;
}

export function createProfileIssueReport() {
  return Object.fromEntries(PROFILE_ISSUE_CATEGORIES.map((category) => [category, []]));
}

export function addProfileIssue(report, category, issue) {
  if (!report[category]) report[category] = [];
  const text = normalizeString(issue);
  if (text && !report[category].includes(text)) report[category].push(text);
}

export function flattenProfileIssues(report = {}) {
  return PROFILE_ISSUE_CATEGORIES
    .filter((category) => category !== 'manufacturing_pending')
    .flatMap((category) => report[category] || []);
}

export function validateMountingFeatureDefinition(mounting = {}, report) {
  const modeText = normalizeString(mounting.mode).toLowerCase();
  const feature = isPlainObject(mounting.fixed_structure)
    ? mounting.fixed_structure
    : isPlainObject(mounting.installation)
      ? mounting.installation
      : null;
  const needsRetainerHeight = /retainer|clip|tray|strap|screw|lug|flush|surface|slot|alignment/.test(modeText);
  if (needsRetainerHeight && 'retainer_height_mm' in mounting && !isNonNegativeNumber(mounting.retainer_height_mm)) {
    addProfileIssue(report, 'mounting_issues', 'mounting.retainer_height_mm');
  }
  if (feature) {
    for (const [key, value] of Object.entries(feature)) {
      if (/_mm$/.test(key) && value !== null && value !== undefined && !isNonNegativeNumber(value)) {
        addProfileIssue(report, 'mounting_issues', `mounting.fixed_structure.${key}`);
      }
    }
  }
}

export function validateMountingHolesForProfile(profile = {}, report) {
  const holes = normalizeMountingHoles(profile);
  if (requiresMountingHoles(profile) && !holes.length) {
    addProfileIssue(report, 'mounting_issues', 'mounting.holes');
    return;
  }
  const source = mountingHoleSource(profile);
  const rawHoles = Array.isArray(source?.holes) ? source.holes : [];
  rawHoles.forEach((hole, index) => {
    if (!isPlainObject(hole)) {
      addProfileIssue(report, 'mounting_issues', `mounting.holes[${index}]`);
      return;
    }
    if (!isFiniteNumber(hole.x)) addProfileIssue(report, 'mounting_issues', `mounting.holes[${index}].x`);
    if (!isFiniteNumber(hole.y)) addProfileIssue(report, 'mounting_issues', `mounting.holes[${index}].y`);
    const diameter = hole.diameter_mm ?? hole.diameter;
    if (diameter !== undefined && !isPositiveNumber(diameter)) {
      addProfileIssue(report, 'mounting_issues', `mounting.holes[${index}].diameter_mm`);
    }
  });
}

export function validateOpeningDefinition(opening, index) {
  const path = `opening[${index}]`;
  const issues = [];
  if (!isPlainObject(opening)) return [path];
  if (!normalizeString(opening.id)) issues.push(`${path}.id`);
  const type = normalizeString(opening.type);
  if (!type) issues.push(`${path}.type`);
  if (!normalizeString(opening.basis)) issues.push(`${path}.basis`);
  if (!normalizeString(opening.preferred_face)) issues.push(`${path}.preferred_face`);
  if (!isNonNegativeNumber(opening.clearance_mm)) issues.push(`${path}.clearance_mm`);
  issues.push(...validateOptionalVector3Definition(opening.center_mm, `${path}.center_mm`));
  issues.push(...validateOptionalVector3Definition(opening.offset_mm, `${path}.offset_mm`));
  if (['rectangular_cutout', 'rectangular_window'].includes(type)) {
    if (!isPositiveNumber(opening.size_mm?.width)) issues.push(`${path}.size_mm.width`);
    if (!isPositiveNumber(opening.size_mm?.height)) issues.push(`${path}.size_mm.height`);
  } else if (type === 'round_hole') {
    if (!isPositiveNumber(opening.diameter_mm ?? opening.size_mm?.diameter)) issues.push(`${path}.diameter_mm`);
  } else if (type === 'hole_array') {
    if (!isPositiveNumber(opening.diameter_mm ?? opening.size_mm?.diameter)) issues.push(`${path}.diameter_mm`);
    if (!isPositiveNumber(opening.count ?? opening.size_mm?.count)) issues.push(`${path}.count`);
    if (!isPositiveNumber(opening.pitch_mm ?? opening.size_mm?.pitch)) issues.push(`${path}.pitch_mm`);
  } else if (type === 'slot_array') {
    if (!isPositiveNumber(opening.slot_mm?.length ?? opening.size_mm?.length ?? opening.size_mm?.length_x)) issues.push(`${path}.slot_mm.length`);
    if (!isPositiveNumber(opening.slot_mm?.width ?? opening.size_mm?.width ?? opening.size_mm?.width_y)) issues.push(`${path}.slot_mm.width`);
    if (!isPositiveNumber(opening.count ?? opening.size_mm?.count)) issues.push(`${path}.count`);
    if (!isPositiveNumber(opening.pitch_mm ?? opening.size_mm?.pitch)) issues.push(`${path}.pitch_mm`);
  } else if (type) {
    issues.push(`${path}.type`);
  }
  return issues;
}

export function validateOptionalVector3Definition(value, path) {
  if (value === undefined || value === null) return [];
  if (!isPlainObject(value)) return [path];
  const issues = [];
  for (const field of ['x', 'y', 'z']) {
    if (!isFiniteNumber(value[field])) issues.push(`${path}.${field}`);
  }
  return issues;
}

export function validateKeepoutDefinition(keepout, index) {
  const path = `keepouts[${index}]`;
  const issues = [];
  if (!isPlainObject(keepout)) return [path];
  if (!normalizeString(keepout.id)) issues.push(`${path}.id`);
  const shape = normalizeString(keepout.shape);
  if (!shape) issues.push(`${path}.shape`);
  if (!isPlainObject(keepout.center_mm)) {
    issues.push(`${path}.center_mm`);
  } else {
    for (const field of ['x', 'y', 'z']) {
      if (!isFiniteNumber(keepout.center_mm[field])) issues.push(`${path}.center_mm.${field}`);
    }
  }
  if (shape === 'box') {
    if (!isPlainObject(keepout.size_mm)) {
      issues.push(`${path}.size_mm`);
    } else {
      for (const field of ['length_x', 'width_y', 'height_z']) {
        if (!isPositiveNumber(keepout.size_mm[field])) issues.push(`${path}.size_mm.${field}`);
      }
    }
  } else if (shape === 'cylinder') {
    if (!isPositiveNumber(keepout.diameter_mm)) issues.push(`${path}.diameter_mm`);
    if (!isPositiveNumber(keepout.height_z)) issues.push(`${path}.height_z`);
  } else if (shape) {
    issues.push(`${path}.shape`);
  }
  return issues;
}

export function buildProfileValidationSummary(profile, issues = []) {
  const issueReport = validateProfileContract(profile);
  const blockingIssues = issues.length ? issues : flattenProfileIssues(issueReport);
  const pending = issueReport.manufacturing_pending.length > 0;
  return {
    hardware_id: profile.id,
    name: profile.name,
    category: profile.category,
    hardware_system: profile.hardware_system || COMMON_HARDWARE_SYSTEM,
    status: blockingIssues.length ? 'fail' : pending ? 'pending' : 'pass',
    issues: blockingIssues,
    issue_categories: issueReport,
    manufacturing_pending: issueReport.manufacturing_pending,
    source_status: profile.source_status || '',
    dimensions_mm: profile.dimensions_mm || {},
    coordinate_system: profile.coordinate_system || {},
    mounting_mode: profile.mounting?.mode || '',
    mounting_contract: {
      mode: profile.mounting?.mode || '',
      mating_hardware_face: profile.mounting?.mating_hardware_face || '',
      preferred_enclosure_surface: profile.mounting?.preferred_enclosure_surface || '',
      clearance_mm: profile.mounting?.clearance_mm ?? null,
      retainer_height_mm: profile.mounting?.retainer_height_mm ?? null,
      fixed_structure: profile.mounting?.fixed_structure || profile.mounting?.installation || null,
      strategy: resolveMountingStrategy(profile),
      hole_count: normalizeMountingHoles(profile).length,
    },
    opening_count: Array.isArray(profile.opening) ? profile.opening.length : 0,
    keepout_count: Array.isArray(profile.keepouts) ? profile.keepouts.length : 0,
    required_fields_present: REQUIRED_PROFILE_FIELDS.filter((field) => field in profile),
    required_fields_missing: REQUIRED_PROFILE_FIELDS.filter((field) => !(field in profile)),
  };
}

export function resolveMountingStrategy(profile = {}, mountingHoles = normalizeMountingHoles(profile)) {
  if (isEspRetainerProfile(profile)) return 'edge_retainer';
  if (isExternalCabledProbeProfile(profile)) return 'external_cabled_probe';
  if (isAdhesiveOuterSurfaceProfile(profile)) return 'adhesive_outer_surface';
  if (isExternalIndependentModuleProfile(profile)) return 'external_independent_module';
  if (mountingHoles.length) return 'shell_through_screw_holes';
  if (requiresMountingHoles(profile)) return 'missing_mounting_holes';
  return 'profile_specific';
}

export function isEspRetainerProfile(profile = {}) {
  return normalizeString(profile.id) === 'xiao_esp32s3';
}

export function isEnclosureHardwareRole(role = {}) {
  const text = [
    role.role,
    role.category,
    role.function,
    role.label,
    role.name,
    role.hardware_role,
    role.hardware_label,
  ].map((value) => normalizeString(value).toLowerCase()).filter(Boolean).join(' ');
  const modelType = normalizeString(role.model_type || role.modelType).toLowerCase();
  if (modelType === 'structural_part'
    && !/(?:enclosure|case|box|shell|housing|外壳|盒体|盒子|机箱|保护壳|矩形带盖|带盖矩形)/i.test(text)) {
    return false;
  }
  return /(?:^|\b)(?:enclosure|case|box|shell|housing|rectangular_box_with_lid|rounded_rectangular_box|func_enclosure|enclosure_structure)(?:\b|$)/i.test(text)
    || /外壳|盒体|盒子|矩形带盖|带盖矩形|盖子|上盖/.test(text);
}

function isStandaloneStructuralProfile(profile = {}) {
  if (normalizeString(profile?.hardware_system).toLowerCase() !== COMMON_HARDWARE_SYSTEM) return false;
  const modelType = normalizeString(profile?.model_type || profile?.modelType).toLowerCase();
  if (modelType) return modelType === 'structural_part';
  return normalizeString(profile?.category).toLowerCase() === 'structural_part'
    || normalizeString(profile?.id) === 'battery_18650_holder';
}

export function requiresMountingHoles(profile = {}) {
  if (!profile || isEspRetainerProfile(profile)) return false;
  if (isExternalCabledProbeProfile(profile)) return false;
  if (isAdhesiveOuterSurfaceProfile(profile)) return false;
  if (isExternalIndependentModuleProfile(profile)) return false;
  return shouldRequireMountingHolesForCategory(profile.category);
}

export function shouldRequireMountingHolesForCategory(category = '') {
  return ['controller', 'display', 'button', 'speaker', 'sensor', 'actuator'].includes(normalizeString(category));
}

export function isExternalCabledProbeProfile(profile = {}) {
  const mode = normalizeString(profile.mounting?.mode).toLowerCase();
  const structureType = normalizeString(profile.mounting?.fixed_structure?.type).toLowerCase();
  return mode === 'external_cabled_probe' || structureType === 'external_cabled_probe';
}

export function isAdhesiveOuterSurfaceProfile(profile = {}) {
  const mode = normalizeString(profile.mounting?.mode).toLowerCase();
  const structureType = normalizeString(profile.mounting?.fixed_structure?.type).toLowerCase();
  return mode === 'adhesive_outer_surface' || structureType === 'adhesive_outer_surface';
}

export function isExternalIndependentModuleProfile(profile = {}) {
  const mode = normalizeString(profile.mounting?.mode).toLowerCase();
  const structureType = normalizeString(profile.mounting?.fixed_structure?.type).toLowerCase();
  return mode === 'external_independent_module' || structureType === 'external_independent_module';
}

export function normalizeMountingHoles(profile = {}) {
  const source = mountingHoleSource(profile);
  const holes = Array.isArray(source?.holes) ? source.holes : [];
  const defaultDiameter = firstPositiveNumber([
    source?.hole_diameter,
    source?.hole_diameter_mm,
    source?.diameter,
    source?.diameter_mm,
    profile.mounting?.hole_diameter,
    profile.mounting?.hole_diameter_mm,
    2.1,
  ]);
  return holes
    .map((hole, index) => {
      if (!isPlainObject(hole) || !isFiniteNumber(hole.x) || !isFiniteNumber(hole.y)) return null;
      return {
        id: normalizeString(hole.id) || normalizeString(hole.role) || `hole_${index + 1}`,
        role: normalizeString(hole.role),
        x: Number(hole.x),
        y: Number(hole.y),
        z: isFiniteNumber(hole.z) ? Number(hole.z) : 0,
        diameter_mm: firstPositiveNumber([hole.diameter_mm, hole.diameter, defaultDiameter]),
        axis: normalizeString(hole.axis || source?.axis || '+Z'),
        fastener: normalizeFastener(hole.fastener || source?.screw),
        source: source?.source || 'mounting.holes',
      };
    })
    .filter(Boolean);
}

export function mountingHoleSource(profile = {}) {
  if (Array.isArray(profile.mounting?.holes)) {
    return {
      holes: profile.mounting.holes,
      hole_diameter: profile.mounting.hole_diameter,
      hole_diameter_mm: profile.mounting.hole_diameter_mm,
      screw: profile.mounting.screw || profile.mounting.fastener,
      axis: profile.mounting.axis,
      source: 'mounting.holes',
    };
  }
  const notes = Array.isArray(profile.legacy_reference?.notes) ? profile.legacy_reference.notes : [];
  const note = notes.find((item) => item?.id === 'mounting_holes_mm' && isPlainObject(item.value));
  if (!note) return { holes: [] };
  return {
    ...note.value,
    source: 'legacy_reference.mounting_holes_mm',
  };
}

function firstPositiveNumber(values = []) {
  const value = values.find((item) => isPositiveNumber(item));
  return Number(value || 0);
}

function normalizeFastener(value) {
  const text = normalizeString(value);
  if (!text || /^m2$/i.test(text)) return 'M2 self-tapping';
  return text;
}

export function isPendingHardwareProfile(profile = {}) {
  const sourceStatus = profile.source_status || '';
  return (
    /暂定|待补充|user supplied|用户临时|未写入/i.test(sourceStatus)
    || profile.legacy_reference?.source === 'ZW-CAD/server/hardware-profiles.js'
  );
}

export function defaultFaceForProfile(profile) {
  if (!profile) return 'base_floor';
  const preferred = normalizeString(profile.mounting?.preferred_enclosure_surface);
  if (SUPPORTED_MOUNT_SURFACES.includes(preferred)) return preferred;
  if (profile.category === 'controller' || profile.category === 'power') return 'base_floor';
  return 'lid_inner';
}

export function defaultInteractionFace(profile) {
  if (!profile) return 'inside';
  if (profile.category === 'sensor') return 'front';
  if (['display', 'button', 'speaker'].includes(profile.category)) return 'top';
  if (profile.category === 'controller') return 'left';
  return 'inside';
}

export function deterministicRotationForFace(targetFace) {
  if (targetFace === 'lid_inner') return { axis: 'x', degrees: 180, rule: 'hardware +Z faces outward through lid' };
  if (targetFace === 'lid_outer') return { axis: 'none', degrees: 0, rule: 'hardware sits on outer lid surface with +Z facing outward' };
  if (targetFace === 'front_inner') return { axis: 'x', degrees: 90, rule: 'hardware +Z faces front wall' };
  return { axis: 'none', degrees: 0, rule: 'hardware sits on base floor' };
}
