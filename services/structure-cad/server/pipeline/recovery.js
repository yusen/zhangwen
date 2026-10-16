import { enclosureGenerator } from './cad.js';
import { boxSizingTool, estimateTopInteractionArea, layoutSolverTool, minimumInnerSizeForBossClearance } from './layout.js';
import { DEFAULT_PARAMETERS, normalizeNumberMap, round } from './shared.js';
import { findBlockingValidationFailure } from './trace.js';
import { validateDesign } from './validation.js';

export function buildNeedsInputFromTool({
  title,
  message,
  partial_intent,
  partial_bom,
  missing_hardware_requests,
  questions,
  resolution_options,
  checks,
  profile_validation_report,
  function_verification_report,
  profile_template,
  required_profile_fields,
  blocking_reason,
}) {
  return {
    status: 'needs_input',
    title,
    message,
    questions,
    resolution_options: Array.isArray(resolution_options) ? resolution_options : [],
    partial_intent,
    partial_bom,
    missing_hardware_requests: Array.isArray(missing_hardware_requests) ? missing_hardware_requests : [],
    checks: Array.isArray(checks) ? checks : [],
    function_verification_report: function_verification_report || null,
    profile_validation_report: profile_validation_report || null,
    profile_template: profile_template || null,
    required_profile_fields: Array.isArray(required_profile_fields) ? required_profile_fields : [],
    blocking_reason,
    source: 'deterministic',
  };
}

export function buildValidationFailureQuestions(check = {}) {
  if (check.id === 'wall_thickness') {
    return ['是否把壁厚调回最小要求以上？'];
  }
  if (check.id === 'screw_boss_clearance') {
    return ['是否允许增大盒体长宽，或减小螺丝柱直径？', '是否调整硬件安装面或位置，避开四角螺丝柱？'];
  }
  if (check.id === 'screw_boss_wall') {
    return ['是否增大螺丝柱直径，或减小螺丝孔直径？'];
  }
  if (check.id === 'inside_inner_cavity' || check.id === 'lid_stack_clearance' || check.id === 'keepout_clearance') {
    return ['是否允许增大盒体尺寸？', '是否减少硬件数量或换用更小的硬件？'];
  }
  if (check.id === 'hardware_interference' || check.id === 'mount_hardware_clearance') {
    return ['是否增大硬件间距或盒体尺寸？', '是否调整安装面或减少硬件数量？'];
  }
  if (check.id === 'printability_basic') {
    return ['是否补充或修改硬件 profile 中的固定结构尺寸？', '是否替换为固定结构更容易打印的硬件？'];
  }
  return ['是否允许后端调整参数后重新生成？', '是否减少硬件数量、调整安装面或放宽尺寸约束？'];
}

export function buildValidationFailureResolutionOptions({ check = {}, enclosure = {}, parameters = DEFAULT_PARAMETERS }) {
  const expanded = {
    inner_length_x: Math.ceil(Number(enclosure.inner_box_size?.length_x || parameters.inner_length_x || 0) + 16),
    inner_width_y: Math.ceil(Number(enclosure.inner_box_size?.width_y || parameters.inner_width_y || 0) + 16),
  };
  if (check.id === 'wall_thickness') {
    return [
      {
        id: 'raise_wall_thickness',
        label: '提高壁厚',
        action: 'adjust_parameter',
        description: '把壁厚调回最小壁厚要求以上，然后重新生成并校验。',
        recommended: true,
        parameter_overrides: {
          wall_thickness: Math.max(parameters.wall_thickness, parameters.min_wall_thickness),
        },
      },
    ];
  }
  if (check.id === 'screw_boss_clearance') {
    return [
      {
        id: 'expand_box_for_boss_clearance',
        label: '增大盒体避让螺丝柱',
        action: 'increase_box_size',
        description: '增大内腔长宽，让四角螺丝柱远离硬件 footprint 后重新生成。',
        recommended: true,
        parameter_overrides: expanded,
      },
      {
        id: 'reduce_screw_boss_diameter',
        label: '减小螺丝柱直径',
        action: 'adjust_parameter',
        description: '在可制造前提下减小螺丝柱直径，释放硬件避让空间。',
        recommended: false,
        parameter_overrides: {
          screw_boss_diameter: Math.max(5, Number(parameters.screw_boss_diameter || 8) - 1),
        },
      },
      {
        id: 'move_hardware_from_corners',
        label: '调整硬件位置',
        action: 'change_mounting_face',
        description: '指定要移动的硬件和目标安装面，让硬件避开四角螺丝柱。',
        recommended: false,
      },
    ];
  }
  if (check.id === 'screw_boss_wall') {
    const required = check.details?.required_radial_wall_mm || Math.max(1.2, parameters.min_wall_thickness * 0.75);
    return [
      {
        id: 'increase_screw_boss_diameter',
        label: '增大螺丝柱直径',
        action: 'adjust_parameter',
        description: '增大螺丝柱外径，保证螺丝孔周围有足够材料。',
        recommended: true,
        parameter_overrides: {
          screw_boss_diameter: round(Number(parameters.screw_hole_diameter || 0) + required * 2),
        },
      },
      {
        id: 'reduce_screw_hole_diameter',
        label: '减小螺丝孔直径',
        action: 'adjust_parameter',
        description: '在螺丝规格允许时减小孔径，增加孔周围壁厚。',
        recommended: false,
        parameter_overrides: {
          screw_hole_diameter: Math.max(1.6, round(Number(parameters.screw_boss_diameter || 0) - required * 2)),
        },
      },
    ];
  }
  if (check.id === 'keepout_clearance') {
    return [
      {
        id: 'increase_keepout_clearance_space',
        label: '增大避让空间',
        action: 'increase_box_size',
        description: '增大内腔高度，并适度放宽长宽，让硬件 keepout 空间不被盖子或壳体占用。',
        recommended: true,
        parameter_overrides: {
          ...expanded,
          inner_height_z: Math.ceil(Math.max(
            Number(enclosure.inner_box_size?.height_z || parameters.inner_height_z || 0) + 10,
            Number(check.details?.required_inner_height_z || 0),
          )),
        },
      },
      {
        id: 'move_keepout_hardware',
        label: '调整硬件安装',
        action: 'change_mounting_face',
        description: '把产生避让空间冲突的硬件移动到另一安装面，或调整位置后重新校验。',
        recommended: false,
      },
    ];
  }
  if (check.id === 'lid_stack_clearance') {
    const requiredClearance = Number(check.details?.required_clearance_mm || parameters.clearance || 0);
    const currentClearance = Number(check.details?.clearance_mm || 0);
    const missingHeight = Math.max(4, Math.ceil(requiredClearance - currentClearance + 2));
    return [
      {
        id: 'increase_lid_stack_height',
        label: '增高盒体重新校验',
        action: 'increase_box_size',
        description: '增大内腔高度，让上盖内侧硬件和底壳硬件之间留出垂直余量后重新生成。',
        recommended: true,
        parameter_overrides: {
          ...expanded,
          inner_height_z: Math.ceil(Number(enclosure.inner_box_size?.height_z || parameters.inner_height_z || 0) + missingHeight),
        },
      },
      {
        id: 'move_lid_stack_hardware',
        label: '调整安装面',
        action: 'change_mounting_face',
        description: '把部分盖内硬件改到底壳或调整安装层，减少上下堆叠高度。',
        recommended: false,
      },
      {
        id: 'remove_or_replace_hardware_after_lid_stack_fail',
        label: '减少或替换硬件',
        action: 'remove_or_replace_hardware',
        description: '删减非必要硬件，或换成更薄的硬件 profile。',
        recommended: false,
      },
    ];
  }
  if (check.id === 'mount_hardware_clearance') {
    return [
      {
        id: 'increase_mount_hardware_clearance',
        label: '增大固定结构避让',
        action: 'increase_box_size',
        description: '增大内腔长宽并提高硬件间距，让托台、限位条和硬件参考包围盒重新布局后避开。',
        recommended: true,
        parameter_overrides: {
          ...expanded,
          hardware_gap: Math.ceil(Number(parameters.hardware_gap || 0) + 4),
        },
      },
      {
        id: 'move_mount_conflict_hardware',
        label: '调整安装面',
        action: 'change_mounting_face',
        description: '把产生固定结构干涉的硬件移动到底壳或上盖内侧的另一层后重新生成。',
        recommended: false,
      },
      {
        id: 'remove_or_replace_hardware_after_mount_conflict',
        label: '减少或替换硬件',
        action: 'remove_or_replace_hardware',
        description: '删减非必要硬件，或换成固定结构占用更小的硬件 profile。',
        recommended: false,
      },
    ];
  }
  if (check.id === 'printability_basic') {
    return [
      {
        id: 'complete_mounting_profile_for_printability',
        label: '补充固定结构参数',
        action: 'complete_hardware_profile',
        description: '检查硬件 profile 的 mounting.clearance_mm、retainer_height_mm 或固定结构尺寸，让托台/限位条达到可打印最小特征。',
        recommended: true,
        evidence: {
          failed: check.details?.failed || [],
          warned: check.details?.warned || [],
          pending: check.details?.pending || [],
        },
      },
      {
        id: 'remove_or_replace_hardware_after_printability_fail',
        label: '减少或替换硬件',
        action: 'remove_or_replace_hardware',
        description: '删减非必要硬件，或换成固定结构更厚、更容易 3D 打印的硬件 profile。',
        recommended: false,
      },
    ];
  }
  return [
    {
      id: 'expand_box_after_validation_fail',
      label: '增大盒体重新校验',
      action: 'increase_box_size',
      description: '增大内腔长宽后重新布局、重新校验。',
      recommended: true,
      parameter_overrides: expanded,
    },
    {
      id: 'remove_or_replace_hardware_after_validation_fail',
      label: '减少或替换硬件',
      action: 'remove_or_replace_hardware',
      description: '删减非必要硬件，或换成尺寸更小的硬件 profile。',
      recommended: false,
    },
  ];
}

export function repairValidationFailure({
  validation,
  enclosure,
  orientedHardwareSpecs,
  parameters,
  userConstraints,
  bom,
  hardwareProfiles,
  environment,
}) {
  let failed = findBlockingValidationFailure(validation.checks);
  if (!failed) return { status: 'skipped_no_failure' };
  if (userConstraints?.size_mm?.outer_max) return { status: 'skipped_user_size_limit' };
  let currentEnclosure = enclosure;
  let currentParameters = { ...parameters };
  let currentLayoutPlan = null;
  let currentCad = null;
  let currentValidation = validation;
  const appliedOptions = [];

  for (let attempt = 0; attempt < 3; attempt += 1) {
    if (!['screw_boss_clearance', 'inside_inner_cavity', 'lid_stack_clearance', 'face_capacity', 'keepout_clearance', 'mount_hardware_clearance'].includes(failed.id)) {
      return { status: 'skipped_unhandled_failure' };
    }
    const option = buildValidationFailureResolutionOptions({
      check: failed,
      enclosure: currentEnclosure,
      parameters: currentParameters,
    }).find((item) => item.action === 'increase_box_size' && item.parameter_overrides);
    if (!option) return { status: 'skipped_no_repair_option' };
    appliedOptions.push(option);
    currentParameters = {
      ...currentParameters,
      ...normalizeNumberMap(option.parameter_overrides),
    };
    currentEnclosure = boxSizingTool({
      orientedHardwareSpecs,
      parameters: currentParameters,
      userConstraints,
    });
    currentLayoutPlan = layoutSolverTool({
      enclosure: currentEnclosure,
      orientedHardwareSpecs,
      parameters: currentParameters,
    });
    currentCad = enclosureGenerator({
      enclosure: currentEnclosure,
      layoutPlan: currentLayoutPlan,
      bom,
      hardwareProfiles,
      parameters: currentParameters,
    });
    currentValidation = validateDesign({
      enclosure: currentEnclosure,
      layoutPlan: currentLayoutPlan,
      orientedHardwareSpecs,
      parameters: currentParameters,
      environment,
      cadqueryCode: currentCad.cadquery_code,
    });
    failed = findBlockingValidationFailure(currentValidation.checks);
    if (!failed) break;
  }

  if (failed) return { status: 'failed', validation: currentValidation };
  return {
    status: 'ok',
    enclosure: currentEnclosure,
    parameters: currentParameters,
    layoutPlan: currentLayoutPlan,
    cad: currentCad,
    validation: currentValidation,
    warning: {
      id: 'validation_auto_repair',
      status: 'warn',
      message: `模型校验未通过，已自动应用 ${appliedOptions.length} 轮参数修复并重新校验。`,
      details: {
        initial_failed_check: appliedOptions[0] ? findBlockingValidationFailure(validation.checks)?.id : '',
        applied_options: appliedOptions.map((item) => item.id),
        parameter_overrides: appliedOptions.map((item) => item.parameter_overrides),
      },
    },
  };
}

export function buildMissingHardwareResolutionOptions(requests = []) {
  const labels = Array.isArray(requests) && requests.length
    ? requests.map((item) => item.label || item.role).filter(Boolean).join('、')
    : '缺失硬件';
  return [
    {
      id: 'provide_missing_profiles',
      label: '补充硬件 profile',
      action: 'provide_custom_hardware_profile',
      description: `按下方模板补齐 ${labels} 的尺寸、安装、开孔和避让参数，系统会继续确定性建模。`,
      recommended: false,
    },
    {
      id: 'ignore_missing_hardware_continue',
      label: '忽略缺失功能继续',
      action: 'ignore_missing_hardware_continue',
      description: `不编造 ${labels} 的 profile，先删除这些库内缺失的功能，只用剩余可匹配硬件继续生成盒子。`,
      recommended: true,
    },
    {
      id: 'remove_unsupported_features',
      label: '砍掉或替换功能',
      action: 'remove_or_replace_feature',
      description: '删除硬件库暂不支持的功能，或改用硬件库中已有的同类硬件。',
      recommended: false,
    },
  ];
}

export function buildProfileIncompleteResolutionOptions(profileResult = {}) {
  return [
    {
      id: 'complete_profile_fields',
      label: '补齐 profile 字段',
      action: 'complete_hardware_profile',
      description: profileResult.message || '补齐硬件尺寸、坐标系、固定方式、开孔、避让和参考模型字段后重新生成。',
      recommended: true,
    },
    {
      id: 'select_known_profile',
      label: '换用已有硬件',
      action: 'select_known_hardware',
      description: '从硬件库选择字段完整的硬件，避免使用缺字段的 profile。',
      recommended: false,
    },
  ];
}

export function buildFaceCapacityResolutionOptions({ capacity, enclosure, orientedHardwareSpecs, parameters, userConstraints }) {
  const details = capacity?.details || {};
  const hasExplicitMaxSize = Boolean(userConstraints?.size_mm?.outer_max);
  const suggestedInner = suggestInnerSizeForFaceCapacity({
    capacity,
    enclosure,
    orientedHardwareSpecs,
    parameters,
  });
  const evidence = {
    face: details.face || 'top',
    utilization: details.utilization ?? null,
    required_area_mm2: details.required_top_area_mm2 ?? null,
    available_area_mm2: details.available_top_area_mm2 ?? null,
  };
  return [
    {
      id: 'allow_larger_box',
      label: hasExplicitMaxSize ? '放宽最大尺寸' : '允许增大盒体',
      action: 'increase_box_size',
      description: hasExplicitMaxSize
        ? '当前需求写死了最大外形尺寸，后端不能突破；放宽尺寸后可重新自动扩盒并校验。'
        : '允许后端增大内腔长宽，重新布局顶面交互硬件和开孔。',
      recommended: !hasExplicitMaxSize,
      parameter_overrides: suggestedInner,
      evidence,
    },
    {
      id: 'move_interactions_to_side',
      label: '调整安装面',
      action: 'change_mounting_face',
      description: '把部分按钮、蜂鸣器或传感器改到侧面，减少顶面占用后重新生成。',
      recommended: hasExplicitMaxSize,
      evidence,
    },
    {
      id: 'remove_or_replace_hardware',
      label: '减少或替换硬件',
      action: 'remove_or_replace_hardware',
      description: '删减非必要硬件，或换成尺寸更小、开孔更少的硬件 profile。',
      recommended: false,
      evidence,
    },
  ];
}

export function suggestInnerSizeForFaceCapacity({ capacity, enclosure, orientedHardwareSpecs, parameters = DEFAULT_PARAMETERS }) {
  const inner = enclosure?.inner_box_size || {};
  const currentLength = Number(inner.length_x || 0);
  const currentWidth = Number(inner.width_y || 0);
  const topSpecs = (orientedHardwareSpecs || []).filter((item) => item.target_face !== 'base_floor');
  const currentArea = Math.max(1, currentLength * currentWidth);
  const requiredArea = Math.ceil((capacity?.details?.total_top_area_mm2 || estimateTopInteractionArea(topSpecs)) / 0.66);
  if (!currentLength || !currentWidth || requiredArea <= currentArea) return {};
  const scale = Math.sqrt(requiredArea / currentArea);
  const bossSafeInner = minimumInnerSizeForBossClearance(topSpecs, parameters);
  return {
    inner_length_x: Math.max(Math.ceil(currentLength * scale), bossSafeInner.length_x),
    inner_width_y: Math.max(Math.ceil(currentWidth * scale), bossSafeInner.width_y),
  };
}
