import { getHardwareLibrarySummary } from '../hardware-library.js';
import { CODE_GUARD_PATTERNS } from './intent.js';
import { DEFAULT_PARAMETERS } from './shared.js';

export function findBlockingValidationFailure(checks = []) {
  return checks.find((check) => check.status === 'fail') || null;
}

export function summarizeValidationStatus(checks = []) {
  if (checks.some((item) => item.status === 'fail')) return 'fail';
  if (checks.some((item) => item.status === 'pending')) return 'pending';
  if (checks.some((item) => item.status === 'warn')) return 'warn';
  return 'pass';
}

export function countCheckStatuses(checks = []) {
  return checks.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
}

export function withNeedsInputGenerationTrace(result, intentAnalysis = {}) {
  return {
    ...result,
    generation_trace: buildNeedsInputGenerationTrace(result, intentAnalysis),
  };
}

export function buildNeedsInputGenerationTrace(result = {}, intentAnalysis = {}) {
  const partialBom = Array.isArray(result.partial_bom) ? result.partial_bom : [];
  const checks = Array.isArray(result.checks) ? result.checks : [];
  const functionVerification = result.function_verification_report && typeof result.function_verification_report === 'object'
    ? result.function_verification_report
    : null;
  return {
    schema_version: 'generation_trace_v1',
    stage: 'needs_input',
    generated_at: new Date().toISOString(),
    intent: summarizeIntentTrace(intentAnalysis),
    conversation_route: summarizeRouteTrace(result.conversation_route || intentAnalysis.conversation_route),
    revision_intent: summarizeRevisionTrace(result.revision_intent || intentAnalysis.revision_intent),
    resolution_option_route: summarizeResolutionOptionTrace(result.resolution_option_route),
    ignored_missing_hardware_requests: Array.isArray(result.ignored_missing_hardware_requests)
      ? result.ignored_missing_hardware_requests
      : [],
    dropped_functions: Array.isArray(result.dropped_functions) ? result.dropped_functions : [],
    blocking_reason: result.blocking_reason || '',
    completed_until: completedUntilForBlockingReason(result.blocking_reason),
    hardware: {
      partial_bom_count: partialBom.length,
      hardware_ids: partialBom.map((item) => item.hardware_id).filter(Boolean),
      function_verification: functionVerification ? {
        status: functionVerification.verification_status || functionVerification.status || '',
        attempts_used: functionVerification.attempts_used || 0,
        missing_function_count: Array.isArray(functionVerification.missing_functions) ? functionVerification.missing_functions.length : 0,
        missing_hardware_count: Array.isArray(functionVerification.missing_hardware) ? functionVerification.missing_hardware.length : 0,
      } : null,
    },
    profile: summarizeProfileTrace(result.profile_validation_report),
    validation: {
      status_counts: countCheckStatuses(checks),
      failing_ids: checks.filter((item) => item.status === 'fail').map((item) => item.id),
      warning_ids: checks.filter((item) => item.status === 'warn').map((item) => item.id),
    },
    feature_markers: {
      profile_contract_v3: Boolean(result.profile_validation_report || result.profile_template),
      mesh_validation_v4: false,
      mounting_opening_v5: false,
      ai_selfcheck_v6: true,
    },
    source: 'deterministic',
  };
}

export function buildGenerationTrace({
  stage = 'artifact',
  intentAnalysis = {},
  bom = [],
  designState = {},
  layoutPlan = {},
  validation = {},
  exports = [],
  profileValidationReport = null,
} = {}) {
  const checks = Array.isArray(validation.checks) ? validation.checks : [];
  const exportReport = summarizeExportReport(exports);
  const openings = Array.isArray(layoutPlan.opening_transforms) ? layoutPlan.opening_transforms : [];
  const mounts = Array.isArray(layoutPlan.mounting_transforms) ? layoutPlan.mounting_transforms : [];
  const mountingHoles = Array.isArray(layoutPlan.mounting_hole_transforms) ? layoutPlan.mounting_hole_transforms : [];
  return {
    schema_version: 'generation_trace_v1',
    stage,
    generated_at: new Date().toISOString(),
    intent: summarizeIntentTrace(intentAnalysis),
    conversation_route: summarizeRouteTrace(designState.conversation_route || intentAnalysis.conversation_route),
    revision_intent: summarizeRevisionTrace(designState.revision_intent || intentAnalysis.revision_intent),
    resolution_option_route: summarizeResolutionOptionTrace(designState.resolution_option_route),
    ignored_missing_hardware_requests: Array.isArray(designState.ignored_missing_hardware_requests)
      ? designState.ignored_missing_hardware_requests
      : [],
    dropped_functions: Array.isArray(designState.dropped_functions) ? designState.dropped_functions : [],
    hardware: {
      bom_count: Array.isArray(bom) ? bom.length : 0,
      hardware_ids: Array.isArray(bom) ? bom.map((item) => item.hardware_id).filter(Boolean) : [],
      function_verification: summarizeFunctionVerificationTrace(designState.function_verification_report),
    },
    profile: summarizeProfileTrace(profileValidationReport || designState.profile_validation_report),
    layout: {
      hardware_count: Array.isArray(layoutPlan.hardware_transforms) ? layoutPlan.hardware_transforms.length : 0,
      opening_count: openings.length,
      mounting_count: mounts.length,
      mounting_hole_count: mountingHoles.length,
      fallback_opening_count: openings.filter((item) => item.projected_from_hardware === true).length,
    },
    mounting_by_hardware: summarizeMountingByHardware(mounts, mountingHoles, layoutPlan.hardware_transforms || []),
    opening_summary: {
      ids: openings.map((item) => item.id).filter(Boolean),
      faces: countBy(openings, (item) => item.face || 'unknown'),
      mounting_hole_ids: mountingHoles.map((item) => item.id).filter(Boolean),
      mounting_hole_faces: countBy(mountingHoles, (item) => item.face || 'unknown'),
      fallback_ids: openings
        .filter((item) => item.projected_from_hardware === true)
        .map((item) => item.id)
        .filter(Boolean),
    },
    validation: {
      validation_status: summarizeValidationStatus(checks),
      status_counts: countCheckStatuses(checks),
      failing_ids: checks.filter((item) => item.status === 'fail').map((item) => item.id),
      warning_ids: checks.filter((item) => item.status === 'warn').map((item) => item.id),
      pending_ids: checks.filter((item) => item.status === 'pending').map((item) => item.id),
      mesh_validation: validation.validation_context?.mesh_validation || designState.validation_context?.mesh_validation || null,
    },
    exports: {
      total_count: exportReport.total_count,
      available_count: exportReport.available_count,
      pending_count: exportReport.pending_count,
      failed_count: exportReport.failed_count,
      ids: exportReport.items.map((item) => item.id).filter(Boolean),
      formats: exportReport.formats,
    },
    feature_markers: summarizeFeatureMarkers({
      profileValidationReport: profileValidationReport || designState.profile_validation_report,
      layoutPlan,
      checks,
      validationContext: validation.validation_context || designState.validation_context,
      exports,
    }),
    source: 'deterministic',
  };
}

export function summarizeIntentTrace(intentAnalysis = {}) {
  return {
    source: intentAnalysis.source || '',
    status: intentAnalysis.status || '',
    model_status: intentAnalysis.model_status || '',
    reason: intentAnalysis.reason || '',
    confidence: intentAnalysis.confidence ?? null,
  };
}

export function summarizeRouteTrace(route = null) {
  if (!route || typeof route !== 'object') {
    return {
      route_action: '',
      confidence: null,
      reason: '',
      source: '',
    };
  }
  return {
    route_action: route.route_action || '',
    confidence: route.confidence ?? null,
    reason: route.reason || '',
    source: route.source || '',
  };
}

export function summarizeRevisionTrace(revision = null) {
  if (!revision || typeof revision !== 'object') {
    return {
      status: '',
      route_action: '',
      summary: '',
      changed: false,
    };
  }
  return {
    status: revision.status || '',
    route_action: revision.route_action || '',
    summary: revision.summary || '',
    changed: Boolean(
      (Array.isArray(revision.add_functions) && revision.add_functions.length)
      || (Array.isArray(revision.remove_functions) && revision.remove_functions.length)
      || (Array.isArray(revision.replace_hardware_roles) && revision.replace_hardware_roles.length)
      || (Array.isArray(revision.remove_hardware_ids) && revision.remove_hardware_ids.length)
      || (Array.isArray(revision.force_selected_hardware_ids) && revision.force_selected_hardware_ids.length)
      || (revision.hardware_face_overrides && Object.keys(revision.hardware_face_overrides).length)
      || (revision.parameter_overrides && Object.keys(revision.parameter_overrides).length)
    ),
    add_functions: Array.isArray(revision.add_functions) ? revision.add_functions : [],
    remove_functions: Array.isArray(revision.remove_functions) ? revision.remove_functions : [],
    replace_hardware_roles: Array.isArray(revision.replace_hardware_roles) ? revision.replace_hardware_roles : [],
    remove_hardware_ids: Array.isArray(revision.remove_hardware_ids) ? revision.remove_hardware_ids : [],
    force_selected_hardware_ids: Array.isArray(revision.force_selected_hardware_ids) ? revision.force_selected_hardware_ids : [],
    hardware_face_overrides: revision.hardware_face_overrides || {},
    parameter_overrides: revision.parameter_overrides || {},
  };
}

export function summarizeResolutionOptionTrace(route = null) {
  if (!route || typeof route !== 'object') {
    return {
      status: '',
      option_id: '',
      action: '',
      confidence: null,
      reason: '',
      source: '',
    };
  }
  return {
    status: route.status || '',
    option_id: route.option_id || '',
    action: route.action || '',
    confidence: route.confidence ?? null,
    reason: route.reason || '',
    source: route.source || '',
  };
}

export function summarizeProfileTrace(report = null) {
  if (!report || typeof report !== 'object') {
    return {
      validation_status: '',
      checked_count: 0,
      pending_count: 0,
      profile_ids: [],
    };
  }
  const profiles = Array.isArray(report.profiles) ? report.profiles : [];
  return {
    validation_status: report.status || '',
    checked_count: Number(report.checked_count || profiles.length || 0),
    pending_count: profiles.filter((item) => item.status === 'pending').length,
    profile_ids: profiles.map((item) => item.hardware_id).filter(Boolean),
  };
}

export function summarizeFunctionVerificationTrace(report = null) {
  if (!report || typeof report !== 'object') {
    return {
      status: '',
      attempts_used: 0,
      missing_function_count: 0,
      missing_hardware_count: 0,
    };
  }
  return {
    status: report.verification_status || report.status || '',
    attempts_used: Number(report.attempts_used || 0),
    max_attempts: Number(report.max_attempts || 0),
    missing_function_count: Array.isArray(report.missing_functions) ? report.missing_functions.length : 0,
    missing_hardware_count: Array.isArray(report.missing_hardware) ? report.missing_hardware.length : 0,
    uncovered_requirement_count: Array.isArray(report.uncovered_requirements) ? report.uncovered_requirements.length : 0,
  };
}

export function summarizeMountingByHardware(mounts = [], mountingHoles = [], hardwareTransforms = []) {
  const ids = new Set([
    ...mounts.map((item) => item.hardware_id || 'unknown'),
    ...mountingHoles.map((item) => item.hardware_id || 'unknown'),
    ...hardwareTransforms.map((item) => item.hardware_id || 'unknown'),
  ]);
  const mountsByHardware = groupBy(mounts, (item) => item.hardware_id || 'unknown');
  const holesByHardware = groupBy(mountingHoles, (item) => item.hardware_id || 'unknown');
  const hardwareById = new Map(hardwareTransforms.map((item) => [item.hardware_id || 'unknown', item]));
  return [...ids].map((hardwareId) => {
    const items = mountsByHardware.get(hardwareId) || [];
    const holes = holesByHardware.get(hardwareId) || [];
    const types = [...new Set(items.map((item) => item.type).filter(Boolean))].sort();
    const hardware = hardwareById.get(hardwareId) || {};
    return {
      hardware_id: hardwareId,
      count: items.length,
      mounting_hole_count: holes.length,
      strategy: hardware.mounting_strategy || '',
      types,
      roles: [...new Set(items.map((item) => item.role).filter(Boolean))].sort(),
      anchor_faces: [...new Set(items.map((item) => item.anchor_face).filter(Boolean))].sort(),
      has_support_tray: types.includes('support_tray'),
      has_side_retainer: types.includes('side_retainer'),
      has_end_stop: types.includes('end_stop'),
      has_lid_press: types.some((type) => String(type).startsWith('lid_press')),
      has_mounting_holes: holes.length > 0,
      clearance_mm: firstFiniteNumber(items.map((item) => item.clearance_mm)),
      engagement_mm: firstFiniteNumber(items.map((item) => item.engagement_mm)),
    };
  });
}

export function summarizeFeatureMarkers({
  profileValidationReport = null,
  layoutPlan = {},
  checks = [],
  validationContext = {},
  exports = [],
} = {}) {
  const openings = Array.isArray(layoutPlan.opening_transforms) ? layoutPlan.opening_transforms : [];
  const mounts = Array.isArray(layoutPlan.mounting_transforms) ? layoutPlan.mounting_transforms : [];
  const mountingHoles = Array.isArray(layoutPlan.mounting_hole_transforms) ? layoutPlan.mounting_hole_transforms : [];
  const mountTypes = new Set(mounts.map((item) => item.type));
  const hasMountMetadata = mounts.some((item) => item.role && item.anchor_face && item.clearance_mm !== undefined)
    || mountingHoles.some((item) => item.fastener && item.source_center_mm && item.diameter_mm !== undefined);
  const hasOpeningMetadata = openings.some((item) => (
    item.basis !== undefined
    && item.source_center_mm !== undefined
    && item.projected_from_hardware !== undefined
    && item.clearance_mm !== undefined
  ));
  return {
    profile_contract_v3: Boolean(profileValidationReport?.profiles),
    mesh_validation_v4: checks.some((item) => item.id === 'mesh_validation')
      || Boolean(validationContext?.mesh_validation),
    mounting_opening_v5: Boolean(hasMountMetadata && hasOpeningMetadata),
    ai_selfcheck_v6: true,
    support_tray: mountTypes.has('support_tray'),
    side_retainer: mountTypes.has('side_retainer'),
    end_stop: mountTypes.has('end_stop'),
    lid_press: [...mountTypes].some((type) => String(type).startsWith('lid_press')),
    mounting_holes: mountingHoles.length > 0,
    opening_source_center: hasOpeningMetadata,
  };
}

export function firstFiniteNumber(values = []) {
  const value = values.find((item) => Number.isFinite(Number(item)));
  return value === undefined ? null : Number(value);
}

export function completedUntilForBlockingReason(reason = '') {
  if (reason === 'empty_prompt') return 'prompt';
  if (reason === 'missing_hardware') return 'bom';
  if (reason === 'function_verifier_unavailable') return 'bom_function_verification';
  if (reason === 'function_verification_failed') return 'bom_function_verification';
  if (reason === 'profile_incomplete') return 'profile_validation';
  if (String(reason).startsWith('validation_')) return 'validation';
  if (reason === 'face_capacity_fail') return 'face_capacity';
  if (reason === 'missing_design_state') return 'regenerate_input';
  return 'needs_input';
}

export function summarizeExportReport(exports = []) {
  const items = Array.isArray(exports) ? exports : [];
  const reportItems = items.map((item) => ({
    id: item.id || '',
    label: item.label || item.id || '',
    format: item.format || 'unknown',
    url: item.url || null,
    status: item.status || '',
    fidelity: item.fidelity || '',
    availability: exportAvailability(item),
  }));
  const availabilityCounts = countBy(reportItems, (item) => item.availability);
  return {
    total_count: reportItems.length,
    available_count: availabilityCounts.available || 0,
    pending_count: availabilityCounts.pending || 0,
    failed_count: availabilityCounts.failed || 0,
    unavailable_count: availabilityCounts.unavailable || 0,
    formats: countBy(reportItems, (item) => item.format || 'unknown'),
    items: reportItems,
  };
}

export function exportAvailability(item = {}) {
  if (item.status === 'failed_write') return 'failed';
  if (['pending_missing_cadquery', 'not_generated_yet', 'pending'].includes(item.status)) return 'pending';
  if (item.url) return 'available';
  return 'unavailable';
}

export function countBy(items, getKey) {
  return items.reduce((acc, item) => {
    const key = getKey(item);
    acc[key] = (acc[key] || 0) + 1;
    return acc;
  }, {});
}

export function groupBy(items = [], getKey) {
  const map = new Map();
  for (const item of items) {
    const key = getKey(item);
    if (!map.has(key)) map.set(key, []);
    map.get(key).push(item);
  }
  return map;
}

export function getIntentRuntimeSummary() {
  return {
    mode: 'deterministic_mock_intent',
    hardware_library_summary: getHardwareLibrarySummary(),
    code_guard_patterns: CODE_GUARD_PATTERNS.map((pattern) => pattern.source),
    default_parameters: DEFAULT_PARAMETERS,
  };
}
