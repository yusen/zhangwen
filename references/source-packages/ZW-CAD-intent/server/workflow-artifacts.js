import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { withProjectMutationLock } from './project-store.js';

const WORKFLOW_ARTIFACTS = Object.freeze([
  {
    id: 'workflow_intent_json',
    workflow_step: 1,
    filename: '01_intent.json',
    label: '01 用户意图 JSON',
    format: 'json',
    fidelity: 'workflow_debug_intent',
  },
  {
    id: 'workflow_bom_json',
    workflow_step: 2,
    filename: '02_bom.json',
    label: '02 硬件 BOM JSON',
    format: 'json',
    fidelity: 'workflow_debug_bom',
  },
  {
    id: 'workflow_profile_report_json',
    workflow_step: 3,
    filename: '03_profile_report.json',
    label: '03 Profile 检查 JSON',
    format: 'json',
    fidelity: 'workflow_debug_profile',
  },
  {
    id: 'workflow_feasibility_report_json',
    workflow_step: 4,
    filename: '04_feasibility_report.json',
    label: '04 可行性预审 JSON',
    format: 'json',
    fidelity: 'workflow_debug_feasibility',
  },
  {
    id: 'workflow_layout_plan_json',
    workflow_step: 5,
    filename: '05_layout_plan.json',
    label: '05 布局计划 JSON',
    format: 'json',
    fidelity: 'workflow_debug_layout',
  },
  {
    id: 'workflow_checks_json',
    workflow_step: 6,
    filename: '06_checks.json',
    label: '06 完整校验 JSON',
    format: 'json',
    fidelity: 'workflow_debug_checks',
  },
  {
    id: 'workflow_cadquery_py',
    workflow_step: 7,
    filename: '07_cadquery.py',
    label: '07 CadQuery 代码',
    format: 'py',
    fidelity: 'workflow_debug_cadquery',
  },
  {
    id: 'workflow_export_manifest_json',
    workflow_step: 8,
    filename: '08_export_manifest.json',
    label: '08 导出清单 JSON',
    format: 'json',
    fidelity: 'workflow_debug_exports',
  },
]);

export async function writeWorkflowArtifactFiles(options = {}) {
  return withProjectMutationLock(
    { rootDir: options.rootDir, projectId: options.designId },
    () => writeWorkflowArtifactFilesUnlocked(options),
  );
}

async function writeWorkflowArtifactFilesUnlocked({ rootDir, designId, artifact }) {
  const exportDir = path.join(rootDir, 'exports', designId, 'workflow');
  await mkdir(exportDir, { recursive: true });

  const workflowExports = buildWorkflowExportEntries({ designId, exportDir });
  const fullExports = mergeExports(artifact.exports || [], workflowExports);
  const contents = buildWorkflowArtifactContents({
    artifact: {
      ...artifact,
      exports: fullExports,
      design_state: {
        ...(artifact.design_state || {}),
        exports: fullExports,
      },
    },
    exports: fullExports,
  });

  await Promise.all(workflowExports.map((entry) => writeFile(
    path.join(exportDir, entry.filename),
    contents.get(entry.filename) || '',
    'utf8',
  )));

  return workflowExports.map(stripInternalFields);
}

export function buildFailedWorkflowArtifactExports(error) {
  const message = error instanceof Error ? error.message : String(error || 'unknown workflow artifact write error');
  return WORKFLOW_ARTIFACTS.map((entry) => ({
    ...stripInternalFields({
      ...entry,
      url: null,
      path: null,
    }),
    status: 'failed_write',
    message,
  }));
}

export function buildWorkflowArtifactContents({ artifact = {}, exports = [] } = {}) {
  const designState = artifact.design_state || {};
  const checks = Array.isArray(artifact.checks) ? artifact.checks : [];
  const warnings = Array.isArray(artifact.warnings) ? artifact.warnings : [];
  const validationContext = designState.validation_context || artifact.validation_context || {};
  const contents = new Map();

  contents.set('01_intent.json', json({
    status: 'workflow_artifact',
    workflow_step: 1,
    artifact_name: '01_intent.json',
    design_id: designState.id || '',
    intent: designState.intent || {},
    conversation_route: artifact.conversation_route || designState.conversation_route || null,
    revision_intent: artifact.revision_intent || designState.revision_intent || null,
    intent_analysis: artifact.intent_analysis || {},
    generation_trace: artifact.generation_trace?.intent || null,
    source: artifact.source || 'deterministic',
  }));

  contents.set('02_bom.json', json({
    status: 'workflow_artifact',
    workflow_step: 2,
    artifact_name: '02_bom.json',
    design_id: designState.id || '',
    bom_count: Array.isArray(artifact.bom) ? artifact.bom.length : 0,
    bom: artifact.bom || [],
    function_verification_report: artifact.function_verification_report || designState.function_verification_report || null,
    missing_hardware_requests: artifact.missing_hardware_requests || [],
    source: artifact.source || 'deterministic',
  }));

  contents.set('03_profile_report.json', json({
    status: 'workflow_artifact',
    workflow_step: 3,
    artifact_name: '03_profile_report.json',
    design_id: designState.id || '',
    profile_validation_report: designState.profile_validation_report || null,
    hardware_profiles: designState.hardware_profiles || [],
    source: artifact.source || 'deterministic',
  }));

  contents.set('04_feasibility_report.json', json({
    status: 'workflow_artifact',
    workflow_step: 4,
    artifact_name: '04_feasibility_report.json',
    design_id: designState.id || '',
    enclosure_parameters: designState.enclosure_parameters || {},
    template_case: designState.template_case === true || artifact.template_case === true,
    model_contract: designState.model_contract || artifact.model_contract || '',
    template_parts: designState.template_parts || artifact.template_parts || [],
    parameters: designState.parameters || {},
    feasibility_checks: selectFeasibilityChecks(checks),
    auto_repair_warnings: warnings.filter((item) => /auto_repair|validation_auto_repair/.test(String(item.id || ''))),
    warnings,
    validation_status: summarizeValidationStatus(checks),
    status_counts: countCheckStatuses(checks),
    source: artifact.source || 'deterministic',
  }));

  contents.set('05_layout_plan.json', json({
    status: 'workflow_artifact',
    workflow_step: 5,
    artifact_name: '05_layout_plan.json',
    design_id: designState.id || '',
    layout_plan: designState.layout_plan || {},
    scene_kind: designState.layout_plan?.scene_kind || '',
    template_case: designState.template_case === true || artifact.template_case === true,
    model_contract: designState.model_contract || artifact.model_contract || '',
    mounting_plan: designState.mounting_plan || [],
    hardware_face_overrides: designState.hardware_face_overrides || {},
    hardware_rotation_overrides: designState.hardware_rotation_overrides || {},
    revision_intent: artifact.revision_intent || designState.revision_intent || null,
    source: artifact.source || 'deterministic',
  }));

  contents.set('06_checks.json', json({
    status: 'workflow_artifact',
    workflow_step: 6,
    artifact_name: '06_checks.json',
    design_id: designState.id || '',
    validation_status: summarizeValidationStatus(checks),
    status_counts: countCheckStatuses(checks),
    checks,
    warnings,
    validation_context: validationContext,
    source: artifact.source || 'deterministic',
  }));

  contents.set('07_cadquery.py', artifact.cadquery_code || '');

  contents.set('08_export_manifest.json', json({
    status: 'workflow_artifact',
    workflow_step: 8,
    artifact_name: '08_export_manifest.json',
    design_id: designState.id || '',
    template_case: designState.template_case === true || artifact.template_case === true,
    model_contract: designState.model_contract || artifact.model_contract || '',
    template_parts_manifest: artifact.template_parts_manifest || designState.template_parts_manifest || null,
    export_count: exports.length,
    available_count: exports.filter((item) => Boolean(item.url)).length,
    pending_count: exports.filter((item) => ['pending', 'pending_missing_cadquery', 'not_generated_yet'].includes(item.status)).length,
    failed_count: exports.filter((item) => ['failed', 'failed_write'].includes(item.status)).length,
    available_formats: [...new Set(exports.map((item) => item.format).filter(Boolean))].sort(),
    exports: exports.map(stripInternalFields),
    source: artifact.source || 'deterministic',
  }));

  return contents;
}

function buildWorkflowExportEntries({ designId, exportDir }) {
  return WORKFLOW_ARTIFACTS.map((entry) => ({
    ...entry,
    url: `/exports/${designId}/workflow/${entry.filename}`,
    path: path.join(exportDir, entry.filename),
  }));
}

function stripInternalFields(entry = {}) {
  const { filename, ...publicEntry } = entry;
  return publicEntry;
}

function mergeExports(existing = [], incoming = []) {
  const byKey = new Map();
  for (const item of [...existing, ...incoming]) {
    const key = item.id || item.url || item.path || JSON.stringify(item);
    byKey.set(key, item);
  }
  return [...byKey.values()];
}

function selectFeasibilityChecks(checks = []) {
  const ids = new Set([
    'hardware_interference',
    'inside_inner_cavity',
    'keepout_clearance',
    'face_capacity',
    'screw_boss_clearance',
    'lid_stack_clearance',
    'opening_alignment',
    'usb_access_clearance',
    'opening_mount_clearance',
  ]);
  return checks.filter((item) => ids.has(item.id));
}

function summarizeValidationStatus(checks = []) {
  if (checks.some((item) => item.status === 'fail')) return 'fail';
  if (checks.some((item) => item.status === 'pending')) return 'pending';
  if (checks.some((item) => item.status === 'warn')) return 'warn';
  return 'pass';
}

function countCheckStatuses(checks = []) {
  return checks.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
}

function json(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}
