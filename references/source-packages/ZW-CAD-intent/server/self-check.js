import { existsSync, readFileSync, statSync } from 'node:fs';
import crypto from 'node:crypto';
import path from 'node:path';
import { buildCadQueryArtifact } from './cadquery-runner.js';
import { getFunctionVerifierConfig, verifyBomFunctionCoverage } from './function-verifier.js';
import { listHardwareLibrary } from './hardware-library.js';
import { getIntentModelConfig, maybeAnalyzeIntentWithModel } from './intent-model.js';
import { generateDesign, getIntentRuntimeSummary, validateCurrentDesign } from './pipeline.js';
import { listWorkflowTools } from './workflow-tools.js';

const FINGERPRINT_FILES = [
  'server/pipeline.js',
  'server/index.js',
  'server/pipeline/core.js',
  'server/conversation-route.js',
  'server/structural-parts.js',
  'server/design-revision.js',
  'server/pipeline/intent.js',
  'server/pipeline/hardware.js',
  'server/function-verifier.js',
  'server/mesh-validator.js',
  'server/requirement-analysis.js',
  'public/app.js',
  'README.md',
];

const SELF_CHECK_PROMPT = 'Self-check: make a compact ESP32 enclosure with USB-C opening, screw bosses, lid, mounts, and printability checks.';

export function sanitizeIntentModelConfig(config = {}) {
  return {
    enabled: Boolean(config.enabled),
    baseUrl: config.baseUrl || '',
    model: config.model || '',
    hasApiKey: Boolean(config.apiKey),
  };
}

export function buildFeatureFlags() {
  return {
    profile_contract_v3: true,
    mesh_validation_v4: true,
    mounting_opening_v5: true,
    ai_selfcheck_v6: true,
    conversation_route_v1: true,
    design_revision_v1: true,
    surface_engraving_v1: true,
    project_storage_v2: true,
    workflow_orchestration_v1: true,
    standalone_structural_parts_v1: true,
  };
}

export function buildSourceFingerprint(rootDir) {
  const files = FINGERPRINT_FILES.map((relativePath) => {
    const absolutePath = path.join(rootDir, relativePath);
    if (!existsSync(absolutePath)) {
      return {
        path: relativePath,
        exists: false,
        hash: '',
        mtime: '',
        size: 0,
      };
    }
    const content = readFileSync(absolutePath);
    const stat = statSync(absolutePath);
    return {
      path: relativePath,
      exists: true,
      hash: crypto.createHash('sha256').update(content).digest('hex').slice(0, 12),
      mtime: stat.mtime.toISOString(),
      size: stat.size,
    };
  });
  const combined = crypto
    .createHash('sha256')
    .update(JSON.stringify(files.map((item) => [item.path, item.hash, item.mtime, item.size])))
    .digest('hex')
    .slice(0, 12);
  return {
    algorithm: 'sha256:12',
    combined_hash: combined,
    files,
  };
}

export function buildServiceIdentity({ rootDir, port, startedAt }) {
  return {
    project: 'ZW-CAD-intent',
    port: Number(port),
    started_at: startedAt,
    node_pid: process.pid,
    node_version: process.version,
    root_basename: path.basename(rootDir || ''),
  };
}

export function buildHealthPayload({ rootDir, port, startedAt, environment, intentModelConfig, functionVerifierConfig, llmConnection, runtime, projectStorage } = {}) {
  return {
    ok: true,
    project: 'ZW-CAD-intent',
    source: 'deterministic',
    port: Number(port),
    service_identity: buildServiceIdentity({ rootDir, port, startedAt }),
    feature_flags: buildFeatureFlags(),
    source_fingerprint: buildSourceFingerprint(rootDir),
    environment,
    intentModel: sanitizeIntentModelConfig(intentModelConfig || getIntentModelConfig()),
    functionVerifier: sanitizeIntentModelConfig(functionVerifierConfig || getFunctionVerifierConfig()),
    llmConnection: sanitizeLlmConnection(llmConnection),
    workflow_tools: listWorkflowTools(),
    runtime: runtime || getIntentRuntimeSummary(),
    project_storage: projectStorage || null,
  };
}

export function sanitizeLlmConnection(connection = {}) {
  return {
    status: connection.status || 'unknown',
    message: connection.message || '',
    checked_at: connection.checked_at || '',
    source_id: connection.source_id || '',
    model: connection.model || '',
    base_url: connection.base_url || '',
    code: connection.code || '',
  };
}

export async function runSelfCheck({
  rootDir,
  dataRootDir = rootDir,
  environment,
  python,
  useModel = true,
  runCadQuery = false,
  startedAt,
  port,
} = {}) {
  const probes = [];
  const sourceFingerprint = buildSourceFingerprint(rootDir);
  const modelConfig = sanitizeIntentModelConfig(getIntentModelConfig());

  probes.push({
    id: 'health',
    label: 'service health',
    status: 'pass',
    message: 'Service identity, feature flags, source fingerprint are available.',
    details: {
      service_identity: buildServiceIdentity({ rootDir, port, startedAt }),
      feature_flags: buildFeatureFlags(),
    },
  });

  const llmProbe = await runLlmProbe({ useModel, modelConfig });
  probes.push(llmProbe);

  let artifact = null;
  try {
    artifact = await generateDesign({
      prompt: SELF_CHECK_PROMPT,
      selectedHardwareIds: ['xiao_esp32s3'],
      intentAnalysis: {
        source: 'self_check_deterministic',
        status: 'ok',
        model_status: llmProbe.status === 'pass' ? 'ok' : llmProbe.status,
        reason: llmProbe.message || '',
        confidence: null,
      },
    }, {
      rootDir: dataRootDir,
      environment,
      functionVerifier: verifyBomFunctionCoverage,
      hardwareLibrarySummary: listHardwareLibrary().profiles,
    });
    probes.push(buildArtifactProbe(artifact));
  } catch (error) {
    probes.push({
      id: 'artifact_generation',
      label: 'fixed ESP32 artifact',
      status: 'fail',
      message: errorMessage(error),
    });
  }

  if (artifact?.status === 'artifact') {
    probes.push(buildProfileContractProbe(artifact));
    probes.push(buildMountingOpeningProbe(artifact));
    probes.push(buildValidationProbe(artifact, environment));
    probes.push(buildExportsProbe(artifact));
  }

  if (runCadQuery && artifact?.status === 'artifact') {
    probes.push(await runCadQueryProbe({ artifact, rootDir: dataRootDir, environment, python }));
  } else {
    probes.push({
      id: 'cadquery_mesh_probe',
      label: 'CadQuery mesh probe',
      status: 'skipped',
      message: 'runCadQuery is false; real STEP/STL and mesh validation were not executed.',
      details: {
        cadqueryAvailable: Boolean(environment?.cadqueryAvailable),
        mesh_validation_status: artifact?.design_state?.validation_context?.mesh_validation || 'not_run',
      },
    });
  }

  const featureMarkers = buildSelfCheckFeatureMarkers({ artifact, probes, modelConfig });
  const recommendations = buildRecommendations({ probes, featureMarkers, environment, modelConfig });
  return {
    status: 'self_check',
    overall_status: rollupProbeStatus(probes),
    probes,
    feature_markers: featureMarkers,
    source_fingerprint: sourceFingerprint,
    recommendations,
  };
}

async function runLlmProbe({ useModel, modelConfig }) {
  if (!useModel) {
    return {
      id: 'llm_intent_probe',
      label: 'LLM intent probe',
      status: 'skipped',
      message: 'useModel is false; LLM probe skipped.',
      details: { intentModel: modelConfig },
    };
  }
  if (!modelConfig.enabled) {
    return {
      id: 'llm_intent_probe',
      label: 'LLM intent probe',
      status: 'skipped',
      message: 'LLM is not configured; deterministic intent path remains available.',
      details: { intentModel: modelConfig },
    };
  }
  const result = await maybeAnalyzeIntentWithModel({
    prompt: SELF_CHECK_PROMPT,
    selectedHardwareIds: ['xiao_esp32s3'],
  }, {
    hardwareLibrarySummary: listHardwareLibrary().profiles,
  });
  return {
    id: 'llm_intent_probe',
    label: 'LLM intent probe',
    status: result.status === 'ok' ? 'pass' : 'warn',
    message: result.status === 'ok'
      ? 'LLM returned structured intent.'
      : `LLM probe returned ${result.status}: ${result.reason || 'no reason'}`,
    details: {
      intentModel: modelConfig,
      model_status: result.status,
      reason: result.reason || '',
      intent_product_name: result.intent?.product_name || '',
    },
  };
}

function buildArtifactProbe(artifact = {}) {
  if (artifact.status !== 'artifact') {
    return {
      id: 'artifact_generation',
      label: 'fixed ESP32 artifact',
      status: 'fail',
      message: `Expected artifact, received ${artifact.status || 'unknown'}.`,
      details: {
        blocking_reason: artifact.blocking_reason || '',
      },
    };
  }
  return {
    id: 'artifact_generation',
    label: 'fixed ESP32 artifact',
    status: 'pass',
    message: 'Deterministic ESP32 artifact generated.',
    details: {
      design_id: artifact.design_state?.id || '',
      bom_count: Array.isArray(artifact.bom) ? artifact.bom.length : 0,
      check_count: Array.isArray(artifact.checks) ? artifact.checks.length : 0,
      has_generation_trace: Boolean(artifact.generation_trace),
    },
  };
}

function buildProfileContractProbe(artifact = {}) {
  const report = artifact.design_state?.profile_validation_report;
  const profiles = Array.isArray(report?.profiles) ? report.profiles : [];
  const hasCategories = profiles.every((profile) => profile.issue_categories && typeof profile.issue_categories === 'object');
  return {
    id: 'profile_contract_v3',
    label: 'profile contract v3',
    status: report && hasCategories ? 'pass' : 'fail',
    message: report && hasCategories
      ? 'Profile validation report includes structured issue categories.'
      : 'Profile validation report is missing structured categories.',
    details: {
      report_status: report?.status || '',
      checked_count: report?.checked_count || 0,
      profile_ids: profiles.map((item) => item.hardware_id).filter(Boolean),
    },
  };
}

function buildMountingOpeningProbe(artifact = {}) {
  const layoutPlan = artifact.design_state?.layout_plan || {};
  const mounts = Array.isArray(layoutPlan.mounting_transforms) ? layoutPlan.mounting_transforms : [];
  const openings = Array.isArray(layoutPlan.opening_transforms) ? layoutPlan.opening_transforms : [];
  const types = new Set(mounts.map((item) => item.type));
  const hasMountMetadata = mounts.some((item) => item.role && item.anchor_face && item.clearance_mm !== undefined && item.engagement_mm !== undefined);
  const hasOpeningMetadata = openings.some((item) => (
    item.basis !== undefined
    && item.source_center_mm !== undefined
    && item.projected_from_hardware !== undefined
    && item.clearance_mm !== undefined
  ));
  const pass = types.has('support_tray') && types.has('side_retainer') && types.has('end_stop') && hasMountMetadata && hasOpeningMetadata;
  return {
    id: 'mounting_opening_v5',
    label: 'mounting/opening v5',
    status: pass ? 'pass' : 'fail',
    message: pass
      ? 'Mounting transforms and opening transforms include v5 metadata.'
      : 'Missing v5 mounting/opening transform metadata.',
    details: {
      mounting_types: [...types].sort(),
      mounting_count: mounts.length,
      opening_count: openings.length,
      fallback_opening_count: openings.filter((item) => item.projected_from_hardware === true).length,
      hasMountMetadata,
      hasOpeningMetadata,
    },
  };
}

function buildValidationProbe(artifact = {}, environment = {}) {
  const validation = validateCurrentDesign({
    currentDesignState: artifact.design_state,
    cadquery_code: artifact.cadquery_code,
    artifact,
  }, { environment });
  const status = validation.validation_status === 'fail'
    ? 'fail'
    : validation.validation_status === 'pass'
      ? 'pass'
      : 'warn';
  return {
    id: 'validation_summary',
    label: 'validation summary',
    status,
    message: `Validation status: ${validation.validation_status || validation.status}.`,
    details: {
      validation_status: validation.validation_status || '',
      status_counts: validation.status_counts || {},
      mesh_validation: validation.validation_context?.mesh_validation || '',
    },
  };
}

function buildExportsProbe(artifact = {}) {
  const exports = Array.isArray(artifact.exports) ? artifact.exports : [];
  const ids = new Set(exports.map((item) => item.id));
  const required = ['preview_gltf', 'cadquery_code', 'design_state_json', 'checks_json', 'artifact_json'];
  const missing = required.filter((id) => !ids.has(id));
  const failed = exports.filter((item) => item.status === 'failed_write').map((item) => item.id);
  return {
    id: 'artifact_exports',
    label: 'artifact exports',
    status: missing.length || failed.length ? 'fail' : 'pass',
    message: missing.length || failed.length
      ? 'Required export metadata is missing or failed.'
      : 'Preview and metadata exports are present.',
    details: {
      required,
      missing,
      failed,
      export_ids: [...ids].sort(),
    },
  };
}

async function runCadQueryProbe({ artifact, rootDir, environment, python }) {
  try {
    const result = await buildCadQueryArtifact({
      rootDir,
      python,
      environment,
      body: {
        designId: artifact.design_state?.id,
        artifact,
      },
    });
    if (result.status === 'artifact_exports') {
      return {
        id: 'cadquery_mesh_probe',
        label: 'CadQuery mesh probe',
        status: result.mesh_validation_status === 'fail' ? 'fail' : result.mesh_validation_status === 'pass' ? 'pass' : 'warn',
        message: `CadQuery build completed; mesh validation: ${result.mesh_validation_status}.`,
        details: {
          mesh_validation_status: result.mesh_validation_status,
          export_ids: (result.exports || []).map((item) => item.id),
        },
      };
    }
    return {
      id: 'cadquery_mesh_probe',
      label: 'CadQuery mesh probe',
      status: result.status === 'fail' ? 'fail' : 'warn',
      message: result.message || result.blocking_reason || result.status,
      details: {
        status: result.status,
        blocking_reason: result.blocking_reason || '',
      },
    };
  } catch (error) {
    return {
      id: 'cadquery_mesh_probe',
      label: 'CadQuery mesh probe',
      status: 'fail',
      message: errorMessage(error),
    };
  }
}

function buildSelfCheckFeatureMarkers({ artifact = null, probes = [], modelConfig = {} } = {}) {
  const traceMarkers = artifact?.generation_trace?.feature_markers || {};
  return {
    profile_contract_v3: Boolean(traceMarkers.profile_contract_v3 || probePassed(probes, 'profile_contract_v3')),
    mesh_validation_v4: Boolean(traceMarkers.mesh_validation_v4),
    mounting_opening_v5: Boolean(traceMarkers.mounting_opening_v5 || probePassed(probes, 'mounting_opening_v5')),
    ai_selfcheck_v6: true,
    llm: {
      configured: Boolean(modelConfig.enabled),
      hasApiKey: Boolean(modelConfig.hasApiKey),
      model: modelConfig.model || '',
      baseUrl: modelConfig.baseUrl || '',
      probe_status: probes.find((item) => item.id === 'llm_intent_probe')?.status || '',
    },
    generation_trace: {
      present: Boolean(artifact?.generation_trace),
      schema_version: artifact?.generation_trace?.schema_version || '',
    },
  };
}

function buildRecommendations({ probes = [], featureMarkers = {}, environment = {}, modelConfig = {} } = {}) {
  const recommendations = [];
  if (!modelConfig.enabled) {
    recommendations.push('LLM 未配置或被强制 mock；如需验证模型链路，请配置环境变量后重启服务。');
  }
  if (!environment?.cadqueryAvailable) {
    recommendations.push('CadQuery/OCP 不可用；真实 STEP/STL 与 mesh 校验会保持 pending。');
  }
  if (probes.some((item) => item.status === 'fail')) {
    recommendations.push('存在 fail 探针；优先检查对应 probe.details 和 source_fingerprint 是否为最新代码。');
  }
  if (!featureMarkers.mounting_opening_v5) {
    recommendations.push('第5项 marker 缺失；检查 layout_plan 的 mounting_transforms/opening_transforms 是否来自最新服务。');
  }
  if (!recommendations.length) {
    recommendations.push('自检未发现阻断问题；如前端仍无变化，请刷新页面并确认 /api/health 的 source_fingerprint 已变化。');
  }
  return recommendations;
}

function rollupProbeStatus(probes = []) {
  if (probes.some((item) => item.status === 'fail')) return 'fail';
  if (probes.some((item) => item.status && item.status !== 'pass')) return 'warn';
  return 'pass';
}

function probePassed(probes = [], id) {
  return probes.some((item) => item.id === id && item.status === 'pass');
}

function errorMessage(error) {
  return error instanceof Error ? error.message : String(error || 'unknown error');
}
