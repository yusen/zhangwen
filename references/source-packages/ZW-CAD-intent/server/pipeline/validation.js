import { meshReportToCheck, meshValidationStatus } from '../mesh-validator.js';
import { cadqueryRuntimeDetails, cadqueryRuntimeMessage } from './cad.js';
import { hardwareWorldBox, keepoutWorldBox, mountWorldBox } from './layout.js';
import { buildValidationFailureResolutionOptions } from './recovery.js';
import { DEFAULT_PARAMETERS, clamp, isPlainObject, normalizeString, round, stripPythonStringLiterals, within } from './shared.js';
import { countCheckStatuses, findBlockingValidationFailure, groupBy, summarizeExportReport, summarizeValidationStatus, withNeedsInputGenerationTrace } from './trace.js';

export function validateCurrentDesign(body = {}, context = {}) {
  const designState = isPlainObject(body.currentDesignState)
    ? body.currentDesignState
    : isPlainObject(body.design_state)
      ? body.design_state
      : isPlainObject(body.designState)
        ? body.designState
        : null;
  if (isTemplateCaseDesign(designState, body)) {
    return validateTemplateCaseDesign(designState, body);
  }
  if (!designState?.enclosure_parameters || !designState?.layout_plan) {
    return withNeedsInputGenerationTrace({
      status: 'needs_input',
      message: '缺少 enclosure_parameters 或 layout_plan，无法重新校验。',
      questions: ['请先生成一个完整 artifact。'],
      blocking_reason: 'missing_validation_context',
    }, {
      source: 'validation',
      status: 'needs_input',
      model_status: 'skipped',
      reason: 'missing_validation_context',
      confidence: null,
    });
  }
  const validation = validateDesign({
    enclosure: designState.enclosure_parameters,
    layoutPlan: designState.layout_plan,
    orientedHardwareSpecs: designState.layout_plan.hardware_transforms || [],
    parameters: designState.parameters || DEFAULT_PARAMETERS,
    environment: context.environment,
    cadqueryCode: typeof body.cadquery_code === 'string' ? body.cadquery_code : '',
    meshValidationReport: designState.mesh_validation_report || body.artifact?.mesh_validation_report || body.mesh_validation_report,
  });
  const blockingValidation = findBlockingValidationFailure(validation.checks);
  const exportReport = summarizeExportReport(
    Array.isArray(designState.exports)
      ? designState.exports
      : Array.isArray(body.artifact?.exports)
        ? body.artifact.exports
        : body.exports,
  );
  return {
    status: 'validation',
    validation_status: summarizeValidationStatus(validation.checks),
    status_counts: countCheckStatuses(validation.checks),
    checks: validation.checks,
    warnings: validation.warnings,
    validation_context: validation.validation_context,
    export_report: exportReport,
    resolution_options: blockingValidation
      ? buildValidationFailureResolutionOptions({
          check: blockingValidation,
          enclosure: designState.enclosure_parameters,
          parameters: designState.parameters || DEFAULT_PARAMETERS,
        })
      : [],
    blocking_reason: blockingValidation ? `validation_${blockingValidation.id}_fail` : '',
    source: 'deterministic',
  };
}

function isTemplateCaseDesign(designState = {}, body = {}) {
  return designState?.design_mode === 'template_case'
    || designState?.template_case === true
    || body?.artifact?.design_mode === 'template_case'
    || body?.artifact?.template_case === true;
}

function validateTemplateCaseDesign(designState = {}, body = {}) {
  const checks = [];
  const parts = Array.isArray(designState.printable_parts)
    ? designState.printable_parts
    : Array.isArray(body?.artifact?.printable_parts)
      ? body.artifact.printable_parts
      : [];
  const source = designState.template_source || body?.artifact?.template_source || {};
  const contractPass = designState.model_contract === 'template_parts_v1'
    || body?.artifact?.model_contract === 'template_parts_v1';
  checks.push({
    id: 'template_parts_contract',
    label: '模板部件契约',
    status: contractPass && parts.length ? 'pass' : 'fail',
    message: contractPass && parts.length
      ? '模板案例部件契约有效。'
      : '模板案例缺少 template_parts_v1 或可打印部件清单。',
  });
  const sourceHashPass = !source.expected_sha256 || !source.sha256 || source.expected_sha256 === source.sha256;
  checks.push({
    id: 'template_source_hash',
    label: '模板源码哈希',
    status: sourceHashPass ? 'pass' : 'fail',
    message: sourceHashPass ? '模板源码哈希记录一致。' : '模板源码哈希记录不一致。',
  });
  const exports = Array.isArray(designState.exports)
    ? designState.exports
    : Array.isArray(body?.artifact?.exports)
      ? body.artifact.exports
      : [];
  const fakeEnclosureExports = exports.filter((item) => ['cadquery_base_stl', 'cadquery_lid_stl', 'cadquery_hardware_stl'].includes(item?.id));
  checks.push({
    id: 'template_no_fake_enclosure_exports',
    label: '模板导出清单',
    status: fakeEnclosureExports.length ? 'fail' : 'pass',
    message: fakeEnclosureExports.length ? '模板案例不应生成普通盒体伪导出。' : '模板导出未包含普通盒体伪导出。',
    details: { fake_exports: fakeEnclosureExports.map((item) => item.id) },
  });
  if (designState.mesh_validation_report || body?.artifact?.mesh_validation_report) {
    checks.push(meshReportToCheck(designState.mesh_validation_report || body.artifact.mesh_validation_report));
  }
  const blocking = checks.find((item) => item.status === 'fail');
  return {
    status: 'validation',
    validation_status: blocking ? 'fail' : 'pass',
    status_counts: countCheckStatuses(checks),
    checks,
    warnings: [],
    validation_context: {
      model_contract: 'template_parts_v1',
      template_case: true,
      source_hash: source.sha256 || '',
      mesh_validation: designState.mesh_validation_report
        ? meshValidationStatus(designState.mesh_validation_report)
        : 'not_run',
    },
    export_report: summarizeExportReport(exports),
    resolution_options: [],
    blocking_reason: blocking ? `validation_${blocking.id}_fail` : '',
    source: 'deterministic',
  };
}

export function validateDesign({ enclosure, layoutPlan, parameters, environment, cadqueryCode = '', meshValidationReport = null }) {
  const checks = [];
  const warnings = [];
  checks.push({
    id: 'source_deterministic',
    label: '生成来源',
    status: 'pass',
    message: '模型数据由确定性后端工具链生成，不来自 LLM 直接 CAD 代码。',
  });
  checks.push({
    id: 'wall_thickness',
    label: '壁厚',
    status: parameters.wall_thickness >= parameters.min_wall_thickness ? 'pass' : 'fail',
    message: `壁厚 ${parameters.wall_thickness} mm，最小要求 ${parameters.min_wall_thickness} mm。`,
  });
  const interference = checkAabbInterference(layoutPlan.hardware_transforms, parameters.hardware_gap);
  checks.push({
    id: 'hardware_interference',
    label: '硬件干涉',
    status: interference.length ? 'fail' : 'pass',
    message: interference.length
      ? `发现 ${interference.length} 组硬件 AABB 间距不足。`
      : '硬件简化 AABB 之间没有发现明确碰撞。',
    details: interference,
  });
  checks.push({
    id: 'inside_inner_cavity',
    label: '内腔容纳',
    status: checkInsideCavity(enclosure, layoutPlan.hardware_transforms) ? 'pass' : 'fail',
    message: '硬件参考包围盒按当前布局位于内腔范围内。',
  });
  const mountHardwareClearance = checkMountHardwareClearance(layoutPlan);
  checks.push({
    id: 'mount_hardware_clearance',
    label: '固定结构干涉',
    status: mountHardwareClearance.status,
    message: mountHardwareClearance.message,
    details: mountHardwareClearance.details,
  });
  const mountingCompleteness = checkMountingStructureCompleteness(enclosure, layoutPlan);
  checks.push({
    id: 'mounting_structure_completeness',
    label: 'Mounting structure completeness',
    status: mountingCompleteness.status,
    message: mountingCompleteness.message,
    details: mountingCompleteness.details,
  });
  const keepoutClearance = checkKeepoutClearance(enclosure, layoutPlan, parameters);
  checks.push({
    id: 'keepout_clearance',
    label: '硬件避让空间',
    status: keepoutClearance.status,
    message: keepoutClearance.message,
    details: keepoutClearance.details,
  });
  const faceCapacity = checkFaceCapacity(enclosure, layoutPlan, parameters);
  checks.push({
    id: 'face_capacity',
    label: '面容量',
    status: faceCapacity.status,
    message: faceCapacity.message,
    details: faceCapacity.details,
  });
  const bossClearance = checkScrewBossClearance(enclosure, layoutPlan, parameters);
  checks.push({
    id: 'screw_boss_clearance',
    label: '螺丝柱避让',
    status: bossClearance.status,
    message: bossClearance.message,
    details: bossClearance.details,
  });
  const bossWall = checkScrewBossWallThickness(parameters);
  checks.push({
    id: 'screw_boss_wall',
    label: '螺丝柱壁厚',
    status: bossWall.status,
    message: bossWall.message,
    details: bossWall.details,
  });
  const lidStack = checkLidStackClearance(enclosure, layoutPlan, parameters);
  checks.push({
    id: 'lid_stack_clearance',
    label: '盖内高度余量',
    status: lidStack.status,
    message: lidStack.message,
    details: lidStack.details,
  });
  const openingAlignment = checkOpeningAlignment(enclosure, layoutPlan);
  checks.push({
    id: 'opening_alignment',
    label: '开孔对齐',
    status: openingAlignment.status,
    message: openingAlignment.message,
    details: openingAlignment.details,
  });
  const usbAccess = checkUsbAccessClearance(enclosure, layoutPlan, parameters);
  checks.push({
    id: 'usb_access_clearance',
    label: 'USB/侧面接口插拔空间',
    status: usbAccess.status,
    message: usbAccess.message,
    details: usbAccess.details,
  });
  const openingMountClearance = checkOpeningMountClearance(enclosure, layoutPlan, parameters);
  checks.push({
    id: 'opening_mount_clearance',
    label: 'Opening clearance from mounts',
    status: openingMountClearance.status,
    message: openingMountClearance.message,
    details: openingMountClearance.details,
  });
  const codeCheck = validateGeneratedCadQueryCode(cadqueryCode);
  checks.push({
    id: 'cadquery_code_static',
    label: 'CadQuery code static check',
    status: codeCheck.status,
    message: codeCheck.message,
    details: codeCheck.details,
  });
  const runtimeDetails = cadqueryRuntimeDetails(environment);
  checks.push({
    id: 'cadquery_runtime',
    label: 'CadQuery 运行环境',
    status: environment?.cadqueryAvailable ? 'pass' : 'pending',
    message: cadqueryRuntimeMessage(environment, runtimeDetails),
    details: runtimeDetails,
  });
  const printability = checkPrintabilityBasic({
    enclosure,
    layoutPlan,
    parameters,
    environment,
    bossWall,
    meshValidationReport,
  });
  checks.push({
    id: 'printability_basic',
    label: '基础打印可行性',
    status: printability.status,
    message: printability.message,
    details: printability.details,
  });
  checks.push(meshReportToCheck(meshValidationReport));
  if (!environment?.cadqueryAvailable) {
    warnings.push({
      id: 'cadquery_missing',
      status: 'pending',
      message: '请安装项目 Python 环境中的 cadquery、OCP 等依赖后，再生成真实 STEP/STL。',
      details: runtimeDetails,
    });
  }
  return {
    checks,
    warnings,
    validation_context: {
      aabb_model: 'simplified_hardware_boxes',
      mesh_validation: meshValidationReport
        ? meshValidationStatus(meshValidationReport)
        : environment?.cadqueryAvailable
          ? 'available_after_cadquery_export'
          : 'pending_missing_cadquery',
    },
  };
}

export function checkAabbInterference(transforms, gap) {
  const failures = [];
  for (let i = 0; i < transforms.length; i += 1) {
    for (let j = i + 1; j < transforms.length; j += 1) {
      const a = transforms[i];
      const b = transforms[j];
      if (a.mount_surface !== b.mount_surface) continue;
      const overlapX = Math.abs(a.center.x - b.center.x) < (a.bounding_box.length_x + b.bounding_box.length_x) / 2 + gap * 0.2;
      const overlapY = Math.abs(a.center.y - b.center.y) < (a.bounding_box.width_y + b.bounding_box.width_y) / 2 + gap * 0.2;
      if (overlapX && overlapY) {
        failures.push({ a: a.hardware_id, b: b.hardware_id });
      }
    }
  }
  return failures;
}

export function checkInsideCavity(enclosure, transforms) {
  const inner = enclosure.inner_box_size;
  return transforms.every((item) => {
    const halfX = item.bounding_box.length_x / 2;
    const halfY = item.bounding_box.width_y / 2;
    const halfZ = item.bounding_box.height_z / 2;
    const zIsAllowed = item.mount_surface === 'lid_outer'
      ? item.center.z - halfZ >= enclosure.outer_box_size.height_z - 0.25
      : item.center.z >= 0 && item.center.z <= enclosure.outer_box_size.height_z;
    return (
      item.center.x - halfX >= -inner.length_x / 2 &&
      item.center.x + halfX <= inner.length_x / 2 &&
      item.center.y - halfY >= -inner.width_y / 2 &&
      item.center.y + halfY <= inner.width_y / 2 &&
      zIsAllowed
    );
  });
}

export function checkMountHardwareClearance(layoutPlan) {
  const collisions = [];
  const hardwareBoxes = (layoutPlan.hardware_transforms || []).map((item) => ({
    hardware: item,
    box: hardwareWorldBox(item),
  }));
  for (const mount of layoutPlan.mounting_transforms || []) {
    const mountBox = mountWorldBox(mount);
    if (!mountBox) continue;
    for (const { hardware, box } of hardwareBoxes) {
      if (!box) continue;
      if (mount.hardware_id === hardware.hardware_id && mountAllowedToEngageHardware(mount, hardware, box)) continue;
      const overlap = boxOverlap3d(mountBox, box);
      if (!overlap) continue;
      collisions.push({
        mount_id: mount.id || '',
        mount_type: mount.type || 'mount',
        mount_hardware_id: mount.hardware_id || '',
        hardware_id: hardware.hardware_id,
        mount_surface: mount.mount_surface || hardware.mount_surface || '',
        overlap_mm: overlap,
        mount_box: mountBox,
        hardware_box: box,
      });
    }
  }
  return {
    status: collisions.length ? 'fail' : 'pass',
    message: collisions.length
      ? `发现 ${collisions.length} 处固定结构侵入硬件参考包围盒。`
      : '支撑托台和限位结构没有侵入硬件参考包围盒。',
    details: {
      checked_mount_count: (layoutPlan.mounting_transforms || []).length,
      checked_hardware_count: (layoutPlan.hardware_transforms || []).length,
      collisions,
    },
  };
}

export function mountAllowedToEngageHardware(mount = {}, hardware = {}, hardwareBox = null) {
  const mountBox = mountWorldBox(mount);
  const box = hardwareBox || hardwareWorldBox(hardware);
  if (!mountBox || !box) return false;
  if (mount.type === 'support_tray') return !boxOverlap3d(mountBox, box);
  const role = normalizeString(mount.role);
  if (!['lateral_retainer', 'end_retainer', 'press'].includes(role)) return false;
  const tolerance = 0.05;
  const separatedX = mountBox.min_x >= box.max_x - tolerance || mountBox.max_x <= box.min_x + tolerance;
  const separatedY = mountBox.min_y >= box.max_y - tolerance || mountBox.max_y <= box.min_y + tolerance;
  return separatedX || separatedY;
}

export function checkMountingStructureCompleteness(enclosure, layoutPlan) {
  const allMounts = layoutPlan.mounting_transforms || [];
  const allHoles = layoutPlan.mounting_hole_transforms || [];
  const allHardware = layoutPlan.hardware_transforms || [];
  if (!allHardware.length) {
    return {
      status: 'pass',
      message: 'No hardware needs generated mounting structures.',
      details: { summaries: [], missing: [] },
    };
  }
  const mountsByHardware = groupBy(allMounts, (mount) => mount.hardware_id || '');
  const holesByHardware = groupBy(allHoles, (hole) => hole.hardware_id || '');
  const missing = [];
  const summaries = [];
  for (const hardware of allHardware) {
    const mounts = mountsByHardware.get(hardware.hardware_id) || [];
    const holes = holesByHardware.get(hardware.hardware_id) || [];
    const strategy = normalizeString(hardware.mounting_strategy) || 'profile_specific';
    if (strategy === 'shell_through_screw_holes') {
      const expectedCount = Array.isArray(hardware.mounting_holes) ? hardware.mounting_holes.length : 0;
      const expectedFace = hardware.mount_surface === 'base_floor' ? 'bottom' : 'top';
      const faceMismatch = holes.filter((hole) => hole.face !== expectedFace);
      const invalidDiameter = holes.filter((hole) => Number(hole.diameter_mm || hole.size_mm?.diameter || 0) <= 0);
      const offPlane = holes.filter((hole) => !openingOnFacePlane(hole, enclosure));
      const summary = {
        hardware_id: hardware.hardware_id,
        mount_surface: hardware.mount_surface,
        strategy,
        expected_hole_count: expectedCount,
        generated_hole_count: holes.length,
        expected_face: expectedFace,
        mount_count: mounts.length,
        status: expectedCount > 0
          && holes.length >= expectedCount
          && !faceMismatch.length
          && !invalidDiameter.length
          && !offPlane.length
          ? 'pass'
          : 'fail',
      };
      summaries.push(summary);
      if (summary.status !== 'pass') {
        missing.push({
          ...summary,
          missing_mounting_holes: holes.length < expectedCount,
          face_mismatch: faceMismatch.map((hole) => hole.id || ''),
          invalid_diameter: invalidDiameter.map((hole) => hole.id || ''),
          off_plane: offPlane.map((hole) => hole.id || ''),
        });
      }
      continue;
    }
    if (strategy === 'missing_mounting_holes') {
      const summary = {
        hardware_id: hardware.hardware_id,
        mount_surface: hardware.mount_surface,
        strategy,
        status: 'fail',
        mount_count: mounts.length,
        generated_hole_count: holes.length,
      };
      summaries.push(summary);
      missing.push({
        ...summary,
        missing_mounting_holes: true,
      });
      continue;
    }
    const support = mounts.filter((mount) => mount.role === 'support' || mount.role === 'hold_down_support' || mount.type === 'support_tray');
    const retainers = mounts.filter((mount) => ['lateral_retainer', 'end_retainer', 'press'].includes(mount.role));
    const anchored = mounts.filter((mount) => normalizeString(mount.anchor_face));
    const surfaceMismatch = mounts.filter((mount) => mount.mount_surface !== hardware.mount_surface);
    const requiresRetainerSet = strategy === 'edge_retainer' || mounts.length > 0;
    const summary = {
      hardware_id: hardware.hardware_id,
      mount_surface: hardware.mount_surface,
      strategy,
      support_count: support.length,
      retainer_or_press_count: retainers.length,
      anchored_count: anchored.length,
      mount_count: mounts.length,
      status: !requiresRetainerSet || (support.length && retainers.length && anchored.length === mounts.length && !surfaceMismatch.length) ? 'pass' : 'fail',
    };
    summaries.push(summary);
    if (summary.status !== 'pass') {
      missing.push({
        ...summary,
        missing_support: support.length === 0,
        missing_retainer_or_press: retainers.length === 0,
        missing_anchor_face: anchored.length !== mounts.length,
        surface_mismatch: surfaceMismatch.map((mount) => mount.id || ''),
      });
    }
  }
  return {
    status: missing.length ? 'fail' : 'pass',
    message: missing.length
      ? `${missing.length} hardware item(s) lack the expected mounting strategy output.`
      : 'Each hardware item has the expected deterministic mounting strategy output.',
    details: {
      summaries,
      missing,
      checked_mount_count: allMounts.length,
      checked_mounting_hole_count: allHoles.length,
    },
  };
}

export function boxOverlap3d(a, b, tolerance = 0.05) {
  const overlap = {
    x: axisOverlap(a.min_x, a.max_x, b.min_x, b.max_x),
    y: axisOverlap(a.min_y, a.max_y, b.min_y, b.max_y),
    z: axisOverlap(a.min_z, a.max_z, b.min_z, b.max_z),
  };
  if (overlap.x <= tolerance || overlap.y <= tolerance || overlap.z <= tolerance) return null;
  return {
    x: round(overlap.x),
    y: round(overlap.y),
    z: round(overlap.z),
  };
}

export function axisOverlap(aMin, aMax, bMin, bMax) {
  return Math.min(aMax, bMax) - Math.max(aMin, bMin);
}

export function checkKeepoutClearance(enclosure, layoutPlan, parameters = DEFAULT_PARAMETERS) {
  const inner = enclosure.inner_box_size;
  const violations = [];
  const unsupported = [];
  let checkedCount = 0;
  let requiredInnerHeight = Number(enclosure.inner_box_size?.height_z || 0);

  for (const transform of layoutPlan.hardware_transforms || []) {
    for (const keepout of transform.keepouts || []) {
      const box = keepoutWorldBox(transform, keepout);
      if (!box) {
        unsupported.push({
          hardware_id: transform.hardware_id,
          keepout_id: keepout.id || '',
          shape: keepout.shape || 'unknown',
        });
        continue;
      }
      checkedCount += 1;
      const isLidOuter = transform.mount_surface === 'lid_outer';
      const minZ = isLidOuter
        ? enclosure.outer_box_size.height_z - parameters.clearance
        : 0;
      const maxZ = transform.mount_surface === 'base_floor'
        ? enclosure.outer_box_size.height_z - enclosure.lid_thickness - parameters.clearance
        : enclosure.outer_box_size.height_z + 0.25;
      const axes = [];
      if (box.min_x < -inner.length_x / 2 || box.max_x > inner.length_x / 2) axes.push('x');
      if (box.min_y < -inner.width_y / 2 || box.max_y > inner.width_y / 2) axes.push('y');
      if (box.min_z < minZ || (!isLidOuter && box.max_z > maxZ)) axes.push('z');
      if (axes.length) {
        if (transform.mount_surface === 'base_floor' && box.max_z > maxZ) {
          requiredInnerHeight = Math.max(
            requiredInnerHeight,
            box.max_z - enclosure.floor_thickness + parameters.clearance,
          );
        }
        violations.push({
          hardware_id: transform.hardware_id,
          keepout_id: keepout.id || '',
          shape: keepout.shape || 'box',
          axes,
          box,
          allowed: {
            min_x: round(-inner.length_x / 2),
            max_x: round(inner.length_x / 2),
            min_y: round(-inner.width_y / 2),
            max_y: round(inner.width_y / 2),
            min_z: round(minZ),
            max_z: isLidOuter ? null : round(maxZ),
          },
        });
      }
    }
  }

  const status = violations.length ? 'fail' : unsupported.length ? 'pending' : 'pass';
  return {
    status,
    message: status === 'pass'
      ? `已检查 ${checkedCount} 个硬件避让空间，均位于当前可用内腔范围内。`
      : status === 'pending'
        ? `有 ${unsupported.length} 个 keepout 形状暂未进入简化 AABB 校验。`
        : `有 ${violations.length} 个硬件避让空间超出当前可用内腔，需要增大盒体或调整安装面。`,
    details: {
      checked_count: checkedCount,
      unsupported,
      violations,
      required_inner_height_z: round(requiredInnerHeight),
    },
  };
}

export function checkFaceCapacity(enclosure, layoutPlan, parameters) {
  const faces = new Map();
  const addArea = (face, area, id, kind) => {
    if (!faces.has(face)) faces.set(face, { face, used_area_mm2: 0, items: [] });
    const entry = faces.get(face);
    entry.used_area_mm2 += area;
    entry.items.push({ id, kind, area_mm2: round(area) });
  };
  for (const item of layoutPlan.hardware_transforms || []) {
    const face = item.mount_surface === 'base_floor' ? 'base_floor' : 'top';
    const margin = parameters.hardware_gap;
    addArea(
      face,
      (item.bounding_box.length_x + margin) * (item.bounding_box.width_y + margin),
      item.hardware_id,
      'hardware_footprint',
    );
  }
  for (const opening of layoutPlan.opening_transforms || []) {
    const openingSize = openingFootprintSize(opening);
    addArea(
      opening.face || 'top',
      (openingSize.length_x + parameters.clearance) * (openingSize.width_y + parameters.clearance),
      opening.id,
      'opening',
    );
  }
  for (const hole of layoutPlan.mounting_hole_transforms || []) {
    const holeSize = openingFootprintSize(hole);
    addArea(
      hole.face || 'top',
      (holeSize.length_x + parameters.clearance) * (holeSize.width_y + parameters.clearance),
      hole.id,
      'mounting_hole',
    );
  }

  const capacityForFace = (face) => {
    if (face === 'left' || face === 'right') return enclosure.inner_box_size.width_y * enclosure.inner_box_size.height_z;
    if (face === 'front' || face === 'back') return enclosure.inner_box_size.length_x * enclosure.inner_box_size.height_z;
    return enclosure.inner_box_size.length_x * enclosure.inner_box_size.width_y;
  };
  const details = [...faces.values()].map((entry) => {
    const capacity = capacityForFace(entry.face);
    return {
      ...entry,
      used_area_mm2: round(entry.used_area_mm2),
      capacity_area_mm2: round(capacity),
      utilization: round(entry.used_area_mm2 / Math.max(capacity, 1), 3),
    };
  });
  const maxUtilization = Math.max(0, ...details.map((item) => item.utilization));
  const status = maxUtilization > 0.9 ? 'fail' : maxUtilization > 0.76 ? 'warn' : 'pass';
  return {
    status,
    message: status === 'pass'
      ? '各安装面按当前简化 footprint 仍有可用空间。'
      : `安装面最高占用率约 ${round(maxUtilization * 100, 1)}%，需要增大盒体或调整安装面。`,
    details,
  };
}

export function checkScrewBossClearance(enclosure, layoutPlan, parameters) {
  const radius = parameters.screw_boss_diameter / 2;
  const clearance = Math.max(0.8, parameters.clearance * 0.8);
  const collisions = [];
  for (const boss of enclosure.screw_bosses || []) {
    for (const item of layoutPlan.hardware_transforms || []) {
      const rect = hardwareRect(item, parameters.clearance);
      if (circleIntersectsRect(boss.x, boss.y, radius + clearance, rect)) {
        collisions.push({
          boss: { x: boss.x, y: boss.y },
          hardware_id: item.hardware_id,
          required_clearance_mm: round(clearance),
        });
      }
    }
  }
  return {
    status: collisions.length ? 'fail' : 'pass',
    message: collisions.length
      ? `发现 ${collisions.length} 处螺丝柱与硬件 footprint 过近。`
      : '四角螺丝柱与硬件 footprint 保持了基础避让距离。',
    details: collisions,
  };
}

export function checkScrewBossWallThickness(parameters) {
  const radialWall = round((Number(parameters.screw_boss_diameter || 0) - Number(parameters.screw_hole_diameter || 0)) / 2);
  const required = Math.max(1.2, round(Number(parameters.min_wall_thickness || DEFAULT_PARAMETERS.min_wall_thickness) * 0.75));
  const status = radialWall >= required ? 'pass' : 'fail';
  return {
    status,
    message: status === 'pass'
      ? `螺丝柱孔周围径向壁厚 ${radialWall} mm，满足至少 ${required} mm 的基础打印要求。`
      : `螺丝柱孔周围径向壁厚只有 ${radialWall} mm，低于 ${required} mm，打印或拧螺丝时可能开裂。`,
    details: {
      screw_boss_diameter: parameters.screw_boss_diameter,
      screw_hole_diameter: parameters.screw_hole_diameter,
      radial_wall_mm: radialWall,
      required_radial_wall_mm: required,
    },
  };
}

export function checkPrintabilityBasic({ enclosure, layoutPlan, parameters, environment, bossWall, meshValidationReport = null }) {
  const mountFeature = checkMountMinimumFeatureSize(layoutPlan, parameters);
  const partExportability = checkPartExportability(enclosure);
  const previewMeshAnchor = checkPreviewMeshAnchoring(enclosure, layoutPlan);
  const realMeshCheck = buildRealMeshPrintabilitySubcheck(meshValidationReport, environment);
  const subchecks = [
    {
      id: 'wall_thickness',
      label: '壁厚',
      status: parameters.wall_thickness >= parameters.min_wall_thickness ? 'pass' : 'fail',
      message: `壁厚 ${parameters.wall_thickness} mm，最小要求 ${parameters.min_wall_thickness} mm。`,
      details: {
        wall_thickness: parameters.wall_thickness,
        min_wall_thickness: parameters.min_wall_thickness,
      },
    },
    {
      id: 'lid_clearance',
      label: '盖子配合间隙',
      status: enclosure.lid_clearance >= 0.2 ? 'pass' : 'warn',
      message: `盖子配合间隙 ${enclosure.lid_clearance} mm。`,
      details: {
        lid_clearance: enclosure.lid_clearance,
        recommended_min_mm: 0.2,
      },
    },
    {
      id: 'screw_boss_wall',
      label: '螺丝柱壁厚',
      status: bossWall.status,
      message: bossWall.message,
      details: bossWall.details,
    },
    partExportability,
    mountFeature,
    previewMeshAnchor,
    realMeshCheck,
    {
      id: 'mesh_overhang_bridge_island',
      label: '悬垂/桥接/孤立小块',
      status: 'pending',
      message: environment?.cadqueryAvailable
        ? '需要真实 mesh 分析后确认悬垂、桥接和孤立小块。'
        : '当前缺少 CadQuery/OCP，真实 mesh 尚未生成，悬垂、桥接和孤立小块保持 pending。',
      details: {
        requires_mesh: true,
        cadquery_available: Boolean(environment?.cadqueryAvailable),
      },
    },
  ];
  const status = summarizeSubcheckStatus(subchecks);
  return {
    status,
    message: printabilityMessage(status, subchecks),
    details: {
      subchecks,
      failed: subchecks.filter((item) => item.status === 'fail').map((item) => item.id),
      pending: subchecks.filter((item) => item.status === 'pending').map((item) => item.id),
      warned: subchecks.filter((item) => item.status === 'warn').map((item) => item.id),
    },
  };
}

export function checkPartExportability(enclosure) {
  const outer = enclosure.outer_box_size || {};
  const baseHeight = Number(outer.height_z || 0) - Number(enclosure.lid_thickness || 0);
  const ok = (
    Number(outer.length_x || 0) > 0
    && Number(outer.width_y || 0) > 0
    && baseHeight > 0
    && Number(enclosure.lid_thickness || 0) > 0
  );
  return {
    id: 'split_part_dimensions',
    label: '分件尺寸',
    status: ok ? 'pass' : 'fail',
    message: ok
      ? '底壳和上盖分件尺寸为正，可以进入导出流程。'
      : '底壳或上盖存在非正尺寸，不能作为可打印分件导出。',
    details: {
      outer_box_size: outer,
      base_height_z: round(baseHeight),
      lid_thickness: enclosure.lid_thickness,
    },
  };
}

export function buildRealMeshPrintabilitySubcheck(meshValidationReport = null, environment = {}) {
  if (!meshValidationReport) {
    return {
      id: 'real_mesh_validation',
      label: '真实 STL mesh 校验',
      status: 'pending',
      message: environment?.cadqueryAvailable
        ? '需要运行 CadQuery 导出真实 STL 后进行 mesh 校验。'
        : '当前缺少 CadQuery/OCP，真实 STL mesh 尚未生成。',
      details: {
        requires_mesh: true,
        cadquery_available: Boolean(environment?.cadqueryAvailable),
      },
    };
  }
  const status = meshReportToCheck(meshValidationReport).status;
  const riskChecks = (meshValidationReport.checks || []).filter((item) => (
    ['watertight', 'manifold_and_degenerate', 'connected_components', 'thin_wall', 'overhang_bridge', 'self_intersection'].includes(item.id)
  ));
  return {
    id: 'real_mesh_validation',
    label: '真实 STL mesh 校验',
    status,
    message: meshValidationReport.message || '真实 STL mesh 校验报告已合并。',
    details: {
      mesh_validation_status: meshValidationStatus(meshValidationReport),
      risk_checks: riskChecks,
    },
  };
}

export function checkMountMinimumFeatureSize(layoutPlan, parameters) {
  const minFeature = Math.max(0.8, round(Number(parameters.min_wall_thickness || DEFAULT_PARAMETERS.min_wall_thickness) * 0.5));
  const tooSmall = [];
  for (const mount of layoutPlan.mounting_transforms || []) {
    const size = mount.size_mm || {};
    const dimensions = {
      length_x: Number(size.length_x || 0),
      width_y: Number(size.width_y || 0),
      height_z: Number(size.height_z || 0),
    };
    const smallAxes = Object.entries(dimensions)
      .filter(([, value]) => value > 0 && value < minFeature)
      .map(([axis]) => axis);
    if (smallAxes.length) {
      tooSmall.push({
        mount_id: mount.id || '',
        hardware_id: mount.hardware_id || '',
        type: mount.type || 'mount',
        small_axes: smallAxes,
        size_mm: dimensions,
      });
    }
  }
  return {
    id: 'mount_min_feature_size',
    label: '固定结构最小特征',
    status: tooSmall.length ? 'fail' : 'pass',
    message: tooSmall.length
      ? `发现 ${tooSmall.length} 个固定结构局部尺寸低于 ${minFeature} mm。`
      : `固定结构局部尺寸不低于 ${minFeature} mm 的基础打印阈值。`,
    details: {
      min_feature_mm: minFeature,
      violations: tooSmall,
    },
  };
}

export function checkPreviewMeshAnchoring(enclosure, layoutPlan) {
  const tolerance = 0.25;
  const outer = enclosure.outer_box_size || {};
  const floorPlaneZ = Number(enclosure.floor_thickness || 0);
  const lidPlateBottomZ = Number(outer.height_z || 0) - Number(enclosure.lid_thickness || 0);
  const lidLipBottomZ = lidPlateBottomZ - Number(enclosure.lid_lip_height || 0);
  const lidAnchorPlanes = uniqueRoundedNumbers([lidLipBottomZ, lidPlateBottomZ]);
  const floatingMounts = [];
  const outOfBoundsMounts = [];
  const unsupportedMounts = [];
  const mounts = layoutPlan.mounting_transforms || [];

  for (const mount of mounts) {
    const box = mountWorldBox(mount);
    if (!box) {
      unsupportedMounts.push({
        mount_id: mount.id || '',
        reason: 'missing_or_invalid_box',
      });
      continue;
    }
    if (!boxWithinOuterFootprint(box, outer)) {
      outOfBoundsMounts.push({
        mount_id: mount.id || '',
        mount_surface: mount.mount_surface || '',
        box,
      });
    }

    let anchored = false;
    let anchor = null;
    if (mount.mount_surface === 'base_floor') {
      anchored = boxTouchesZPlane(box, floorPlaneZ, tolerance);
      anchor = { surface: 'base_floor', z: round(floorPlaneZ) };
    } else if (mount.mount_surface === 'lid_inner') {
      const touchedPlane = lidAnchorPlanes.find((plane) => boxTouchesZPlane(box, plane, tolerance));
      anchored = Number.isFinite(touchedPlane);
      anchor = {
        surface: 'lid_inner',
        z_planes: lidAnchorPlanes.map((plane) => round(plane)),
      };
    } else if (mount.mount_surface === 'lid_outer') {
      anchored = boxTouchesZPlane(box, Number(outer.height_z || 0), tolerance);
      anchor = {
        surface: 'lid_outer',
        z: round(Number(outer.height_z || 0)),
      };
    } else {
      unsupportedMounts.push({
        mount_id: mount.id || '',
        reason: 'unknown_mount_surface',
        mount_surface: mount.mount_surface || '',
      });
      continue;
    }

    if (!anchored) {
      floatingMounts.push({
        mount_id: mount.id || '',
        hardware_id: mount.hardware_id || '',
        type: mount.type || 'mount',
        mount_surface: mount.mount_surface || '',
        expected_anchor: anchor,
        box,
      });
    }
  }

  const status = floatingMounts.length || outOfBoundsMounts.length
    ? 'fail'
    : unsupportedMounts.length
      ? 'warn'
      : 'pass';
  return {
    id: 'preview_mesh_anchor',
    label: '预览几何连接性',
    status,
    message: status === 'pass'
      ? '简化预览几何中的固定结构都贴合到底壳或上盖锚面。'
      : status === 'warn'
        ? `有 ${unsupportedMounts.length} 个固定结构缺少足够信息，无法完成预览几何连接性检查。`
        : `发现 ${floatingMounts.length + outOfBoundsMounts.length} 个固定结构在预览几何中可能悬空或超出分件边界。`,
    details: {
      basis: 'simplified_preview_aabb',
      checked_mount_count: mounts.length,
      tolerance_mm: tolerance,
      anchors: {
        base_floor_z: round(floorPlaneZ),
        lid_inner_z_planes: lidAnchorPlanes.map((plane) => round(plane)),
      },
      floating_mounts: floatingMounts,
      out_of_bounds_mounts: outOfBoundsMounts,
      unsupported_mounts: unsupportedMounts,
      requires_real_mesh_followup: true,
    },
  };
}

export function uniqueRoundedNumbers(values = []) {
  return [...new Set(values
    .filter((value) => Number.isFinite(value))
    .map((value) => round(value)))];
}

export function boxTouchesZPlane(box, planeZ, tolerance = 0.25) {
  return box.min_z <= planeZ + tolerance && box.max_z >= planeZ - tolerance;
}

export function boxWithinOuterFootprint(box, outer = {}, tolerance = 0.25) {
  const halfX = Number(outer.length_x || 0) / 2;
  const halfY = Number(outer.width_y || 0) / 2;
  return (
    box.min_x >= -halfX - tolerance
    && box.max_x <= halfX + tolerance
    && box.min_y >= -halfY - tolerance
    && box.max_y <= halfY + tolerance
  );
}

export function summarizeSubcheckStatus(subchecks) {
  if (subchecks.some((item) => item.status === 'fail')) return 'fail';
  if (subchecks.some((item) => item.status === 'pending')) return 'pending';
  if (subchecks.some((item) => item.status === 'warn')) return 'warn';
  return 'pass';
}

export function printabilityMessage(status, subchecks) {
  if (status === 'fail') {
    const failed = subchecks.filter((item) => item.status === 'fail').map((item) => item.label).join('、');
    return `基础打印可行性存在明确失败项：${failed}。`;
  }
  if (status === 'pending') {
    return '基础尺寸检查已完成；悬垂、桥接和孤立小块需要真实 mesh 后继续验证。';
  }
  if (status === 'warn') {
    const warned = subchecks.filter((item) => item.status === 'warn').map((item) => item.label).join('、');
    return `基础打印可行性有风险项：${warned}。`;
  }
  return '基础打印尺寸检查通过。';
}

export function checkLidStackClearance(enclosure, layoutPlan, parameters) {
  const floorHardware = (layoutPlan.hardware_transforms || []).filter((item) => item.mount_surface === 'base_floor');
  const lidHardware = (layoutPlan.hardware_transforms || []).filter((item) => item.mount_surface === 'lid_inner');
  if (!floorHardware.length || !lidHardware.length) {
    return {
      status: 'pass',
      message: '当前布局没有同时跨底壳和上盖的硬件堆叠风险。',
      details: { floor_top_z: null, lid_bottom_z: null, clearance_mm: null },
    };
  }
  const floorTop = Math.max(...floorHardware.map((item) => item.center.z + item.bounding_box.height_z / 2));
  const lidBottom = Math.min(...lidHardware.map((item) => item.center.z - item.bounding_box.height_z / 2));
  const clearance = round(lidBottom - floorTop);
  const status = clearance < 0 ? 'fail' : clearance < parameters.clearance ? 'warn' : 'pass';
  return {
    status,
    message: status === 'pass'
      ? `盖内硬件与底壳硬件之间的垂直余量为 ${clearance} mm。`
      : `盖内硬件与底壳硬件之间的垂直余量只有 ${clearance} mm，需要增高盒体或调整安装面。`,
    details: {
      floor_top_z: round(floorTop),
      lid_bottom_z: round(lidBottom),
      clearance_mm: clearance,
      required_clearance_mm: parameters.clearance,
      inner_height_z: enclosure.inner_box_size.height_z,
    },
  };
}

export function checkOpeningAlignment(enclosure, layoutPlan) {
  const openingMap = new Map((layoutPlan.opening_transforms || []).map((item) => [item.id, item]));
  const missing = [];
  const misaligned = [];
  let requiredCount = 0;
  for (const transform of layoutPlan.hardware_transforms || []) {
    for (const [index, opening] of (transform.openings || []).entries()) {
      requiredCount += 1;
      const id = `${transform.hardware_id}_${opening.id || index}`;
      const generated = openingMap.get(id);
      if (!generated) {
        missing.push(id);
        continue;
      }
      if (!openingOnFacePlane(generated, enclosure)) {
        misaligned.push({
          id,
          face: generated.face,
          center: generated.center,
        });
      }
    }
  }
  const status = missing.length || misaligned.length ? 'fail' : requiredCount ? 'pass' : 'warn';
  return {
    status,
    message: status === 'pass'
      ? `已为 ${requiredCount} 个硬件 opening 生成并对齐开孔 transform。`
      : requiredCount
        ? `有 ${missing.length + misaligned.length} 个硬件 opening 缺少或未贴合目标外壳面。`
        : '当前 BOM 没有需要开孔的硬件。',
    details: {
      required_openings: requiredCount,
      generated_openings: layoutPlan.opening_transforms?.length || 0,
      missing,
      misaligned,
    },
  };
}

export function checkUsbAccessClearance(enclosure, layoutPlan, parameters) {
  const sideOpenings = (layoutPlan.opening_transforms || []).filter((opening) => {
    const text = `${opening.id} ${opening.type}`.toLowerCase();
    return ['left', 'right', 'front', 'back'].includes(opening.face) && (/usb|connector|cutout/.test(text));
  });
  if (!sideOpenings.length) {
    return {
      status: 'pass',
      message: '当前布局没有需要侧面插拔空间检查的 USB/连接器开孔。',
      details: [],
    };
  }
  const hardwareById = new Map((layoutPlan.hardware_transforms || []).map((item) => [item.hardware_id, item]));
  const maxGap = parameters.wall_thickness + parameters.usb_c_margin + parameters.clearance;
  const details = sideOpenings.map((opening) => {
    const hardware = hardwareById.get(opening.hardware_id);
    const gap = hardware ? sideGapToInnerWall(enclosure, hardware, opening.face) : Infinity;
    return {
      opening_id: opening.id,
      hardware_id: opening.hardware_id,
      face: opening.face,
      hardware_to_inner_wall_gap_mm: Number.isFinite(gap) ? round(gap) : null,
      max_recommended_gap_mm: round(maxGap),
      status: Number.isFinite(gap) && gap <= maxGap ? 'pass' : 'fail',
    };
  });
  const failures = details.filter((item) => item.status === 'fail');
  return {
    status: failures.length ? 'fail' : 'pass',
    message: failures.length
      ? `有 ${failures.length} 个侧面接口离外壳内壁过远，插拔通道可能过深。`
      : '侧面 USB/连接器硬件已经贴近对应内壁，插拔通道长度在建议范围内。',
    details,
  };
}

export function checkOpeningMountClearance(enclosure, layoutPlan, parameters = DEFAULT_PARAMETERS) {
  const conflicts = [];
  const warningConflicts = [];
  const minGap = Math.max(0.4, Number(parameters.clearance || DEFAULT_PARAMETERS.clearance) * 0.4);
  for (const opening of layoutPlan.opening_transforms || []) {
    const openingRect = openingFaceRect(opening, minGap);
    if (!openingRect) continue;
    if (opening.face === 'top') {
      for (const boss of enclosure.screw_bosses || []) {
        const radius = Number(parameters.screw_boss_diameter || DEFAULT_PARAMETERS.screw_boss_diameter) / 2 + minGap;
        if (circleIntersectsRect(Number(boss.x || 0), Number(boss.y || 0), radius, openingRect)) {
          conflicts.push({
            opening_id: opening.id || '',
            conflict_type: 'screw_boss',
            boss: { x: Number(boss.x || 0), y: Number(boss.y || 0) },
            face: opening.face,
          });
        }
      }
    }
    for (const mount of layoutPlan.mounting_transforms || []) {
      const mountRect = mountFaceRect(mount, opening.face, enclosure, minGap, parameters);
      if (!mountRect) continue;
      const overlap = rectOverlap2d(openingRect, mountRect);
      if (!overlap) continue;
      const entry = {
        opening_id: opening.id || '',
        hardware_id: opening.hardware_id || '',
        mount_id: mount.id || '',
        mount_hardware_id: mount.hardware_id || '',
        conflict_type: 'mount',
        face: opening.face,
        overlap_mm: overlap,
      };
      if (mount.hardware_id === opening.hardware_id || openingUsesCenterFallback(opening) || !isMajorOpeningMountOverlap(openingRect, mountRect, overlap)) {
        warningConflicts.push(entry);
      } else {
        conflicts.push(entry);
      }
    }
    for (const hole of layoutPlan.mounting_hole_transforms || []) {
      if (hole.face !== opening.face) continue;
      const holeRect = openingFaceRect(hole, minGap);
      const overlap = rectOverlap2d(openingRect, holeRect);
      if (!overlap) continue;
      const entry = {
        opening_id: opening.id || '',
        hardware_id: opening.hardware_id || '',
        mounting_hole_id: hole.id || '',
        mounting_hole_hardware_id: hole.hardware_id || '',
        conflict_type: 'mounting_hole',
        face: opening.face,
        overlap_mm: overlap,
      };
      if (hole.hardware_id === opening.hardware_id || !isMajorOpeningMountOverlap(openingRect, holeRect, overlap)) {
        warningConflicts.push(entry);
      } else {
        conflicts.push(entry);
      }
    }
  }
  const status = conflicts.length ? 'fail' : warningConflicts.length ? 'warn' : 'pass';
  return {
    status,
    message: status === 'fail'
      ? `${conflicts.length} opening footprint conflict(s) with screw bosses or other mounting structures.`
      : status === 'warn'
        ? `${warningConflicts.length} opening footprint(s) are close to their own mounting structures; review profile offsets.`
        : 'Opening footprints avoid screw bosses and generated mounting structures in the simplified check.',
    details: {
      conflicts,
      warnings: warningConflicts,
      clearance_mm: round(minGap),
    },
  };
}

export function openingFaceRect(opening = {}, padding = 0) {
  const center = opening.center || {};
  const footprint = openingFootprintSize(opening);
  return rectOnFace(opening.face || 'top', center, footprint, padding);
}

export function mountFaceRect(mount = {}, face = 'top', enclosure = {}, padding = 0, parameters = DEFAULT_PARAMETERS) {
  const center = mount.center || {};
  const size = mount.size_mm || {};
  if (mount.mount_surface === 'base_floor' && face === 'top') return null;
  if ((mount.mount_surface === 'lid_inner' || mount.mount_surface === 'lid_outer') && face !== 'top') return null;
  if (['left', 'right', 'front', 'back'].includes(face) && !mountNearFace(mount, face, enclosure, parameters)) return null;
  return rectOnFace(face, center, {
    length_x: Number(size.length_x || 0),
    width_y: Number(size.width_y || 0),
    height_z: Number(size.height_z || 0),
  }, padding);
}

export function mountNearFace(mount = {}, face = 'top', enclosure = {}, parameters = DEFAULT_PARAMETERS) {
  const box = mountWorldBox(mount);
  if (!box) return false;
  const inner = enclosure.inner_box_size || {};
  const band = Math.max(
    1,
    Number(parameters.wall_thickness || DEFAULT_PARAMETERS.wall_thickness)
      + Number(parameters.clearance || DEFAULT_PARAMETERS.clearance) * 2,
  );
  if (face === 'left') return box.min_x <= -Number(inner.length_x || 0) / 2 + band;
  if (face === 'right') return box.max_x >= Number(inner.length_x || 0) / 2 - band;
  if (face === 'front') return box.min_y <= -Number(inner.width_y || 0) / 2 + band;
  if (face === 'back') return box.max_y >= Number(inner.width_y || 0) / 2 - band;
  return true;
}

export function rectOnFace(face, center = {}, size = {}, padding = 0) {
  const lengthX = Number(size.length_x || 0);
  const widthY = Number(size.width_y || 0);
  const heightZ = Number(size.height_z || 0);
  if (face === 'left' || face === 'right') {
    return centeredRect2d(Number(center.y || 0), Number(center.z || 0), widthY, heightZ || widthY, padding);
  }
  if (face === 'front' || face === 'back') {
    return centeredRect2d(Number(center.x || 0), Number(center.z || 0), lengthX, heightZ || widthY, padding);
  }
  return centeredRect2d(Number(center.x || 0), Number(center.y || 0), lengthX, widthY, padding);
}

export function centeredRect2d(cx, cy, width, height, padding = 0) {
  if (!Number.isFinite(cx) || !Number.isFinite(cy) || width <= 0 || height <= 0) return null;
  return {
    min_x: round(cx - width / 2 - padding),
    max_x: round(cx + width / 2 + padding),
    min_y: round(cy - height / 2 - padding),
    max_y: round(cy + height / 2 + padding),
  };
}

export function rectsOverlap2d(a, b, tolerance = 0.05) {
  return Boolean(rectOverlap2d(a, b, tolerance));
}

export function rectOverlap2d(a, b, tolerance = 0.05) {
  if (!a || !b) return null;
  const x = axisOverlap(a.min_x, a.max_x, b.min_x, b.max_x);
  const y = axisOverlap(a.min_y, a.max_y, b.min_y, b.max_y);
  if (x <= tolerance || y <= tolerance) return null;
  return { x: round(x), y: round(y), area_mm2: round(x * y) };
}

export function openingUsesCenterFallback(opening = {}) {
  return opening.projected_from_hardware === true;
}

export function isMajorOpeningMountOverlap(openingRect, mountRect, overlap) {
  const openingArea = rectArea(openingRect);
  const mountArea = rectArea(mountRect);
  const smaller = Math.max(1, Math.min(openingArea, mountArea));
  return overlap.area_mm2 / smaller >= 0.45;
}

export function rectArea(rect = {}) {
  return Math.max(0, Number(rect.max_x || 0) - Number(rect.min_x || 0))
    * Math.max(0, Number(rect.max_y || 0) - Number(rect.min_y || 0));
}

export function openingFootprintSize(opening) {
  const size = opening.size_mm || {};
  const diameter = Number(size.diameter || opening.diameter_mm || 0);
  const count = Number(size.count || opening.count || 1);
  const pitch = Number(size.pitch || size.pitch_mm || opening.pitch_mm || diameter || 1);
  if (diameter > 0) {
    return {
      length_x: round(diameter + Math.max(0, count - 1) * pitch),
      width_y: round(diameter),
    };
  }
  const slotLength = Number(size.length || size.length_x || opening.slot_mm?.length || 0);
  const slotWidth = Number(size.width || size.width_y || opening.slot_mm?.width || 0);
  if (opening.type === 'slot_array' || slotLength > 0) {
    return {
      length_x: round(Math.max(slotLength, 1)),
      width_y: round(Math.max(slotWidth + Math.max(0, count - 1) * pitch, 1)),
    };
  }
  const width = Number(size.width || size.length_x || opening.width_mm || 0);
  const height = Number(size.height || size.width_y || opening.height_mm || 0);
  const footprint = {
    length_x: round(Math.max(width, 1)),
    width_y: round(Math.max(height, 1)),
  };
  if (Number(opening.layout_rotation_deg || 0) % 180 !== 0) {
    return {
      length_x: footprint.width_y,
      width_y: footprint.length_x,
    };
  }
  return footprint;
}

export function hardwareRect(item, padding = 0) {
  const halfX = item.bounding_box.length_x / 2 + padding;
  const halfY = item.bounding_box.width_y / 2 + padding;
  return {
    min_x: item.center.x - halfX,
    max_x: item.center.x + halfX,
    min_y: item.center.y - halfY,
    max_y: item.center.y + halfY,
  };
}

export function circleIntersectsRect(cx, cy, radius, rect) {
  const nearestX = clamp(cx, rect.min_x, rect.max_x);
  const nearestY = clamp(cy, rect.min_y, rect.max_y);
  const dx = cx - nearestX;
  const dy = cy - nearestY;
  return dx * dx + dy * dy <= radius * radius;
}

export function openingOnFacePlane(opening, enclosure) {
  const outer = enclosure.outer_box_size;
  const c = opening.center || {};
  const tolerance = 0.25;
  if (!outer) return false;
  if (opening.face === 'left') {
    return Math.abs(c.x + outer.length_x / 2) <= tolerance && within(c.y, -outer.width_y / 2, outer.width_y / 2) && within(c.z, 0, outer.height_z);
  }
  if (opening.face === 'right') {
    return Math.abs(c.x - outer.length_x / 2) <= tolerance && within(c.y, -outer.width_y / 2, outer.width_y / 2) && within(c.z, 0, outer.height_z);
  }
  if (opening.face === 'front') {
    return Math.abs(c.y + outer.width_y / 2) <= tolerance && within(c.x, -outer.length_x / 2, outer.length_x / 2) && within(c.z, 0, outer.height_z);
  }
  if (opening.face === 'back') {
    return Math.abs(c.y - outer.width_y / 2) <= tolerance && within(c.x, -outer.length_x / 2, outer.length_x / 2) && within(c.z, 0, outer.height_z);
  }
  if (opening.face === 'bottom') {
    return Math.abs(c.z) <= tolerance && within(c.x, -outer.length_x / 2, outer.length_x / 2) && within(c.y, -outer.width_y / 2, outer.width_y / 2);
  }
  return Math.abs(c.z - outer.height_z) <= tolerance && within(c.x, -outer.length_x / 2, outer.length_x / 2) && within(c.y, -outer.width_y / 2, outer.width_y / 2);
}

export function sideGapToInnerWall(enclosure, hardware, face) {
  const inner = enclosure.inner_box_size;
  if (face === 'left') return hardware.center.x - hardware.bounding_box.length_x / 2 + inner.length_x / 2;
  if (face === 'right') return inner.length_x / 2 - (hardware.center.x + hardware.bounding_box.length_x / 2);
  if (face === 'front') return hardware.center.y - hardware.bounding_box.width_y / 2 + inner.width_y / 2;
  if (face === 'back') return inner.width_y / 2 - (hardware.center.y + hardware.bounding_box.width_y / 2);
  return Infinity;
}

export function validateGeneratedCadQueryCode(code) {
  const text = typeof code === 'string' ? code : '';
  const codeWithoutStrings = stripPythonStringLiterals(text);
  const missing = [
    'import cadquery as cq',
    'def build_hollow_base',
    'def apply_screw_bosses',
    'def apply_lid_screw_holes',
    'base_part = build_hollow_base()',
    'base_part = apply_screw_bosses(base_part)',
    'lid_part = build_lid()',
    'lid_part = apply_lid_screw_holes(lid_part)',
    'hardware_reference_parts = build_hardware_references()',
    'def apply_openings',
    'def build_mounts',
    'def apply_mounts',
    'base_part, lid_part = apply_mounts(base_part, lid_part)',
  ].filter((needle) => !text.includes(needle));
  const forbidden = [
    /\bopen\s*\(/,
    /\bexec\s*\(/,
    /\beval\s*\(/,
    /\bsubprocess\b/,
    /\bos\.system\b/,
    /\brequests\b/,
    /\bsocket\b/,
  ].filter((pattern) => pattern.test(codeWithoutStrings)).map((pattern) => pattern.source);
  if (!text.trim()) {
    return {
      status: 'pending',
      message: 'CadQuery code is not available in this validation request.',
      details: { missing, forbidden },
    };
  }
  if (missing.length || forbidden.length) {
    return {
      status: 'fail',
      message: 'Generated CadQuery code failed static safety/shape checks.',
      details: { missing, forbidden },
    };
  }
  return {
    status: 'pass',
    message: 'Generated CadQuery code contains required deterministic entry points and no blocked APIs.',
    details: { missing: [], forbidden: [] },
  };
}
