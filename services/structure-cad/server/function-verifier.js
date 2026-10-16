import {
  getFunctionVerifierConfig,
  requestChatCompletionJson,
} from './model-sources.js';

const MAX_FUNCTION_VERIFY_ATTEMPTS = 3;

export { getFunctionVerifierConfig };

export function buildFunctionVerifyUnavailableResult(reason = 'function_verifier_not_configured') {
  return {
    status: 'needs_input',
    verification_status: 'blocked',
    reason,
    attempts_used: 0,
    max_attempts: MAX_FUNCTION_VERIFY_ATTEMPTS,
    missing_functions: [],
    missing_hardware: [],
    uncovered_requirements: [],
    library_violations: [],
    message: 'BOM 功能验证需要 LLM 可用；当前 LLM 未配置或不可用，因此不能继续进入 profile、布局和建模阶段。',
  };
}

export async function verifyBomFunctionCoverage({
  intent,
  bom,
  hardwareLibrarySummary,
  config = getFunctionVerifierConfig(),
} = {}) {
  if (!config.enabled) return buildFunctionVerifyUnavailableResult('function_verifier_not_configured');
  try {
    const raw = await requestFunctionVerificationJson({
      intent,
      bom,
      hardwareLibrarySummary,
      config,
    });
    return normalizeFunctionVerification(raw);
  } catch (error) {
    return buildFunctionVerifyUnavailableResult(error instanceof Error ? error.message : String(error));
  }
}

export function normalizeFunctionVerification(value = {}) {
  const statusText = String(value.status || value.verification_status || '').toLowerCase();
  const ok = value.ok === true || ['ok', 'pass', 'passed'].includes(statusText);
  return {
    status: ok ? 'ok' : 'needs_input',
    verification_status: ok ? 'pass' : 'fail',
    reason: String(value.reason || value.message || ''),
    missing_functions: normalizeList(value.missing_functions),
    missing_hardware: normalizeMissingHardware(value.missing_hardware),
    uncovered_requirements: normalizeList(value.uncovered_requirements),
    library_violations: normalizeList(value.library_violations),
    covered_functions: normalizeList(value.covered_functions),
    notes: normalizeList(value.notes),
    confidence: Number.isFinite(Number(value.confidence)) ? Number(value.confidence) : null,
    raw: value && typeof value === 'object' ? value : {},
  };
}

async function requestFunctionVerificationJson({
  intent,
  bom,
  hardwareLibrarySummary,
  config,
}) {
  return requestChatCompletionJson({
    config,
    temperature: 0,
    responseFormat: { type: 'json_object' },
    messages: [
      { role: 'system', content: buildFunctionVerifySystemPrompt() },
      {
        role: 'user',
        content: JSON.stringify({
          intent,
          bom,
          hardware_library_summary: hardwareLibrarySummary,
        }, null, 2),
      },
    ],
  });
}

function buildFunctionVerifySystemPrompt() {
  return [
    'You are the function verifier for ZW-CAD-intent.',
    'Workflow overview: this step runs after hardware_bom_select and before profile_check, orientation_resolve, layout_solve, design_validate, cadquery_generate, artifact_export, and cadquery_build.',
    'Return ONLY a JSON object.',
    'Check whether the proposed BOM can cover the user intent functions and required_hardware_roles.',
    'Check every hardware_id in BOM exists in hardware_library_summary.',
    'Do not invent hardware. If a function is not covered by the selected BOM and library, report it.',
    'Do not pass a BOM that drops user-requested functions unless the user explicitly chose a resolution option that removes or ignores those functions.',
    'Return shape: { "status": "ok" | "needs_input", "missing_functions": [], "missing_hardware": [], "uncovered_requirements": [], "library_violations": [], "covered_functions": [], "reason": "", "confidence": 0.0 }.',
  ].join('\n');
}

function normalizeList(value) {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => typeof item === 'string' ? item : JSON.stringify(item))
    .filter(Boolean);
}

function normalizeMissingHardware(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (typeof item === 'string') return { label: item, hardware_id: '', function: item };
    return {
      label: String(item?.label || item?.name || item?.role || item?.function || ''),
      hardware_id: String(item?.hardware_id || item?.id || ''),
      function: String(item?.function || item?.role || item?.label || ''),
      reason: String(item?.reason || item?.why_needed || ''),
    };
  }).filter((item) => item.label || item.hardware_id || item.function);
}
