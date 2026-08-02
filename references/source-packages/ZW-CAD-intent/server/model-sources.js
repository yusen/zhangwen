import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import path from 'node:path';

const DEFAULT_MODEL = 'gpt-5.5';
const DEFAULT_BASE_URL = 'https://api.openai.com/v1';
const DEFAULT_REQUEST_TIMEOUT_MS = 90000;
const DEFAULT_PROBE_TIMEOUT_MS = 45000;
const TIMEOUT_ENV_BY_REQUEST_KIND = Object.freeze({
  probe: 'ZW_CAD_INTENT_PROBE_TIMEOUT_MS',
  intent_analysis: 'ZW_CAD_INTENT_INTENT_TIMEOUT_MS',
  function_verify: 'ZW_CAD_INTENT_VERIFY_TIMEOUT_MS',
  surface_engraving: 'ZW_CAD_INTENT_SURFACE_ENGRAVING_TIMEOUT_MS',
  model_edit: 'ZW_CAD_INTENT_MODEL_EDIT_TIMEOUT_MS',
});
const LOCAL_CONFIG_RELATIVE_PATH = path.join('server', 'data', 'model-sources.local.json');
const PROBE_PROMPT = 'Probe ZW-CAD-intent LLM connection. Return a tiny JSON object.';

let rootDir = process.cwd();
let runtimeState = null;

export function configureModelSources(options = {}) {
  if (options.rootDir) rootDir = options.rootDir;
  runtimeState = null;
}

export function getIntentModelConfig() {
  const source = getActiveModelSource();
  const apiKey = source?.apiKey || '';
  return {
    enabled: Boolean(source?.enabled && apiKey),
    apiKey,
    baseUrl: trimTrailingSlash(source?.baseUrl || DEFAULT_BASE_URL),
    model: source?.model || DEFAULT_MODEL,
    sourceId: source?.id || '',
    sourceName: source?.name || '',
  };
}

export function getFunctionVerifierConfig() {
  return getIntentModelConfig();
}

export function getModelSourcesPayload() {
  const state = ensureState();
  return {
    activeSourceId: state.activeSourceId,
    sources: state.sources.map(sanitizeSource),
    connection: state.connection || buildNotConfiguredConnection(getActiveModelSource()),
  };
}

export function saveModelSource(input = {}) {
  const state = ensureState();
  const id = normalizeId(input.id) || createSourceId(input.name || input.model || 'model');
  const existing = state.sources.find((item) => item.id === id);
  const source = normalizeSource({
    ...(existing || {}),
    id,
    name: input.name ?? existing?.name,
    baseUrl: input.baseUrl ?? input.base_url ?? existing?.baseUrl,
    model: input.model ?? existing?.model,
    apiKey: input.apiKey !== undefined ? input.apiKey : input.api_key !== undefined ? input.api_key : existing?.apiKey,
    enabled: input.enabled !== undefined ? input.enabled : existing?.enabled ?? true,
    lastProbe: existing?.lastProbe || null,
  });
  const index = state.sources.findIndex((item) => item.id === id);
  if (index >= 0) state.sources[index] = source;
  else state.sources.push(source);
  if (!state.activeSourceId || input.setActive === true || input.set_active === true) {
    state.activeSourceId = source.id;
  }
  persistState();
  return sanitizeSource(source);
}

export function setActiveModelSource(id) {
  const state = ensureState();
  const normalized = normalizeId(id);
  const source = state.sources.find((item) => item.id === normalized);
  if (!source) {
    const error = new Error('未找到指定模型源。');
    error.code = 'model_source_not_found';
    throw error;
  }
  state.activeSourceId = source.id;
  state.connection = source.lastProbe || buildUnknownConnection(source);
  persistState();
  return getModelSourcesPayload();
}

export async function probeModelSource(id = '') {
  const state = ensureState();
  const source = id
    ? state.sources.find((item) => item.id === normalizeId(id))
    : getActiveModelSource();
  const checkedAt = new Date().toISOString();
  let result = null;
  if (!source) {
    result = {
      status: 'not_configured',
      message: '未配置模型源。',
      checked_at: checkedAt,
      source_id: '',
      model: '',
      base_url: '',
    };
  } else if (!source.enabled || !source.apiKey) {
    result = buildNotConfiguredConnection(source, checkedAt);
  } else {
    result = await requestProbe(source, checkedAt);
  }
  if (source) {
    source.lastProbe = result;
  }
  if (!id || source?.id === state.activeSourceId) {
    state.connection = result;
  }
  persistState();
  return result;
}

export async function requestChatCompletionJson({
  messages,
  temperature = 0,
  responseFormat = { type: 'json_object' },
  config = getIntentModelConfig(),
  requestKind = 'llm_chat_completion',
  timeoutMs,
} = {}) {
  const resolvedTimeoutMs = resolveRequestTimeoutMs(requestKind, timeoutMs);
  if (!config.enabled) {
    throw buildModelUnavailableError('llm_unavailable', 'LLM 未配置或未启用，请先在模型源面板配置可用的 API key、base URL 和模型名。', {
      request_kind: requestKind,
      timeout_ms: resolvedTimeoutMs,
      elapsed_ms: 0,
      source_id: config.sourceId || '',
      model: config.model || '',
    });
  }
  const controller = new AbortController();
  const startedAt = Date.now();
  let timedOut = false;
  const metadata = (extra = {}) => buildModelRequestMetadata({
    config,
    requestKind,
    timeoutMs: resolvedTimeoutMs,
    elapsedMs: Date.now() - startedAt,
    ...extra,
  });
  const timeout = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, resolvedTimeoutMs);
  try {
    const response = await fetch(`${trimTrailingSlash(config.baseUrl)}/chat/completions`, {
      method: 'POST',
      signal: controller.signal,
      headers: {
        Authorization: `Bearer ${config.apiKey}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: config.model,
        temperature,
        response_format: responseFormat,
        messages,
      }),
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
      throw buildModelUnavailableError(
        'llm_request_failed',
        data?.error?.message || `模型接口请求失败，HTTP ${response.status}。`,
        metadata({ http_status: response.status }),
      );
    }
    const content = data?.choices?.[0]?.message?.content;
    if (typeof content !== 'string' || !content.trim()) {
      throw buildModelUnavailableError('llm_empty_response', '模型接口返回空内容。', metadata());
    }
    try {
      const parsed = JSON.parse(content);
      recordModelRequestConnection({
        config,
        requestKind,
        connection: buildConnectedConnection(config, metadata()),
      });
      return parsed;
    } catch (error) {
      throw buildModelUnavailableError('llm_invalid_json', `模型返回内容不是合法 JSON：${error instanceof Error ? error.message : String(error)}`, metadata());
    }
  } catch (error) {
    if (isModelUnavailableError(error)) {
      attachModelRequestMetadata(error, metadata(error.model_request || {}));
      recordModelRequestFailureConnection({ config, requestKind, error });
      logModelRequestFailure(error);
      throw error;
    }
    const code = timedOut || isAbortLikeError(error) ? 'llm_request_timeout' : 'llm_request_failed';
    const message = normalizeLlmRequestError(error, { timedOut, timeoutMs: resolvedTimeoutMs });
    const wrapped = buildModelUnavailableError(code, message, metadata());
    recordModelRequestFailureConnection({ config, requestKind, error: wrapped });
    logModelRequestFailure(wrapped);
    throw wrapped;
  } finally {
    clearTimeout(timeout);
  }
}

export function buildModelUnavailableError(code, message, requestMetadata = {}) {
  const error = new Error(message);
  error.code = code;
  if (requestMetadata && Object.keys(requestMetadata).length) {
    error.model_request = requestMetadata;
  }
  return error;
}

export function buildModelNeedsInput(error, metadata = {}) {
  const code = error?.code || metadata.code || 'llm_intent_failed';
  const configured = Boolean(metadata.config?.enabled);
  const requestMetadata = error?.model_request || metadata.model_request || {};
  return {
    status: 'needs_input',
    title: configured ? 'LLM 模型调用失败' : 'LLM 模型未连接',
    message: `${error instanceof Error ? error.message : String(error || 'LLM 不可用')} 请在右上角 LLM 状态中检查模型源配置。`,
    questions: [
      '请检查 API key 是否有效。',
      '请检查 base URL 是否以 /v1 结尾并可访问。',
      '请检查模型名、账号余额和模型权限。',
    ],
    blocking_reason: configured ? 'llm_intent_failed' : 'llm_unavailable',
    model_error: {
      code,
      message: error instanceof Error ? error.message : String(error || ''),
      source_id: metadata.config?.sourceId || '',
      model: metadata.config?.model || '',
      base_url: metadata.config?.baseUrl || '',
      request_kind: requestMetadata.request_kind || metadata.requestKind || '',
      elapsed_ms: Number.isFinite(requestMetadata.elapsed_ms) ? requestMetadata.elapsed_ms : null,
      timeout_ms: Number.isFinite(requestMetadata.timeout_ms) ? requestMetadata.timeout_ms : null,
      http_status: Number.isFinite(requestMetadata.http_status) ? requestMetadata.http_status : null,
    },
    intent_analysis: {
      source: 'model_intent',
      status: 'needs_input',
      model_status: configured ? 'failed' : 'not_configured',
      reason: error instanceof Error ? error.message : String(error || ''),
      confidence: null,
      questions: [],
    },
  };
}

function ensureState() {
  if (runtimeState) return runtimeState;
  runtimeState = loadState();
  return runtimeState;
}

function loadState() {
  const configPath = localConfigPath();
  if (existsSync(configPath)) {
    try {
      const parsed = JSON.parse(readFileSync(configPath, 'utf8'));
      const sources = Array.isArray(parsed.sources) ? parsed.sources.map(normalizeSource).filter(Boolean) : [];
      const activeSourceId = normalizeId(parsed.activeSourceId || parsed.active_source_id)
        || sources.find((item) => item.enabled)?.id
        || sources[0]?.id
        || '';
      return {
        activeSourceId,
        sources,
        connection: parsed.connection || buildUnknownConnection(sources.find((item) => item.id === activeSourceId)),
      };
    } catch {
      return buildEnvState();
    }
  }
  return buildEnvState();
}

function buildEnvState() {
  const apiKey = process.env.ZW_CAD_INTENT_API_KEY || process.env.ZW_CAD_API_KEY || '';
  const baseUrl = process.env.ZW_CAD_INTENT_API_BASE_URL || process.env.ZW_CAD_API_BASE_URL || DEFAULT_BASE_URL;
  const model = process.env.ZW_CAD_INTENT_MODEL || process.env.ZW_CAD_MODEL || DEFAULT_MODEL;
  const enabled = Boolean(apiKey) && process.env.ZW_CAD_INTENT_FORCE_MOCK !== '1';
  const source = normalizeSource({
    id: 'env',
    name: '环境变量模型源',
    baseUrl,
    model,
    apiKey,
    enabled,
  });
  return {
    activeSourceId: source.id,
    sources: [source],
    connection: buildUnknownConnection(source),
  };
}

function persistState() {
  const state = ensureState();
  const configPath = localConfigPath();
  mkdirSync(path.dirname(configPath), { recursive: true });
  writeFileSync(configPath, `${JSON.stringify({
    activeSourceId: state.activeSourceId,
    sources: state.sources,
    connection: state.connection,
  }, null, 2)}\n`, 'utf8');
}

function localConfigPath() {
  return path.join(rootDir, LOCAL_CONFIG_RELATIVE_PATH);
}

function getActiveModelSource() {
  const state = ensureState();
  return state.sources.find((item) => item.id === state.activeSourceId)
    || state.sources.find((item) => item.enabled)
    || state.sources[0]
    || null;
}

function normalizeSource(value = {}) {
  const id = normalizeId(value.id) || createSourceId(value.name || value.model || 'model');
  return {
    id,
    name: normalizeString(value.name) || id,
    baseUrl: trimTrailingSlash(value.baseUrl || value.base_url || DEFAULT_BASE_URL),
    model: normalizeString(value.model) || DEFAULT_MODEL,
    apiKey: normalizeString(value.apiKey || value.api_key),
    enabled: value.enabled !== false,
    lastProbe: value.lastProbe || value.last_probe || null,
  };
}

function sanitizeSource(source = {}) {
  return {
    id: source.id || '',
    name: source.name || '',
    baseUrl: source.baseUrl || '',
    model: source.model || '',
    enabled: Boolean(source.enabled),
    hasApiKey: Boolean(source.apiKey),
    maskedApiKey: maskApiKey(source.apiKey),
    lastProbe: source.lastProbe || null,
  };
}

async function requestProbe(source, checkedAt) {
  try {
    await requestChatCompletionJson({
      requestKind: 'probe',
      config: {
        enabled: true,
        apiKey: source.apiKey,
        baseUrl: source.baseUrl,
        model: source.model,
        sourceId: source.id,
      },
      temperature: 0,
      messages: [
        { role: 'system', content: 'Return ONLY JSON: {"ok": true}.' },
        { role: 'user', content: PROBE_PROMPT },
      ],
    });
    return {
      status: 'connected',
      message: 'LLM 已连接。',
      checked_at: checkedAt,
      source_id: source.id,
      model: source.model,
      base_url: source.baseUrl,
    };
  } catch (error) {
    return {
      status: 'failed',
      message: error instanceof Error ? error.message : String(error),
      checked_at: checkedAt,
      source_id: source.id,
      model: source.model,
      base_url: source.baseUrl,
      code: error?.code || 'llm_probe_failed',
    };
  }
}

function buildUnknownConnection(source = null) {
  return {
    status: source?.enabled && source?.apiKey ? 'unknown' : 'not_configured',
    message: source?.enabled && source?.apiKey ? '尚未检测 LLM 连接。' : '未配置可用 LLM 模型源。',
    checked_at: '',
    source_id: source?.id || '',
    model: source?.model || '',
    base_url: source?.baseUrl || '',
  };
}

function buildNotConfiguredConnection(source = null, checkedAt = new Date().toISOString()) {
  return {
    status: 'not_configured',
    message: source ? '模型源未启用或缺少 API key。' : '未配置模型源。',
    checked_at: checkedAt,
    source_id: source?.id || '',
    model: source?.model || '',
    base_url: source?.baseUrl || '',
  };
}

function buildConnectedConnection(config = {}, requestMetadata = {}, checkedAt = new Date().toISOString()) {
  return {
    status: 'connected',
    message: 'LLM 已连接。',
    checked_at: checkedAt,
    source_id: config.sourceId || '',
    model: config.model || '',
    base_url: trimTrailingSlash(config.baseUrl || ''),
    code: '',
    request_kind: requestMetadata.request_kind || '',
    elapsed_ms: Number.isFinite(requestMetadata.elapsed_ms) ? requestMetadata.elapsed_ms : null,
  };
}

function buildFailedConnection(config = {}, error, checkedAt = new Date().toISOString()) {
  const requestMetadata = error?.model_request || {};
  return {
    status: 'failed',
    message: error instanceof Error ? error.message : String(error || 'LLM 连接失败。'),
    checked_at: checkedAt,
    source_id: config.sourceId || requestMetadata.source_id || '',
    model: config.model || requestMetadata.model || '',
    base_url: trimTrailingSlash(config.baseUrl || ''),
    code: error?.code || 'llm_request_failed',
    request_kind: requestMetadata.request_kind || '',
    elapsed_ms: Number.isFinite(requestMetadata.elapsed_ms) ? requestMetadata.elapsed_ms : null,
    timeout_ms: Number.isFinite(requestMetadata.timeout_ms) ? requestMetadata.timeout_ms : null,
    http_status: Number.isFinite(requestMetadata.http_status) ? requestMetadata.http_status : null,
  };
}

function recordModelRequestConnection({ config = {}, requestKind = '', connection = null } = {}) {
  if (!connection || requestKind === 'probe') return;
  const state = ensureState();
  const source = findModelSourceForConfig(state, config);
  if (!source) return;
  const normalizedConnection = {
    ...connection,
    source_id: source.id,
    model: connection.model || source.model || '',
    base_url: connection.base_url || source.baseUrl || '',
  };
  source.lastProbe = normalizedConnection;
  if (source.id === state.activeSourceId) state.connection = normalizedConnection;
  persistState();
}

function recordModelRequestFailureConnection({ config = {}, requestKind = '', error = null } = {}) {
  if (requestKind === 'probe') return;
  if (isReachableModelResponseError(error)) {
    recordModelRequestConnection({
      config,
      requestKind,
      connection: buildConnectedConnection(config, error?.model_request || {}),
    });
    return;
  }
  if (!isConnectionFailureError(error)) return;
  recordModelRequestConnection({
    config,
    requestKind,
    connection: buildFailedConnection(config, error),
  });
}

function findModelSourceForConfig(state = {}, config = {}) {
  const sourceId = normalizeId(config.sourceId || config.source_id);
  return state.sources.find((item) => item.id === sourceId)
    || state.sources.find((item) => item.id === state.activeSourceId
      && trimTrailingSlash(item.baseUrl) === trimTrailingSlash(config.baseUrl)
      && item.model === config.model)
    || null;
}

function createSourceId(value) {
  const base = normalizeId(value) || 'model';
  const state = runtimeState;
  if (!state?.sources?.some((item) => item.id === base)) return base;
  let index = 2;
  while (state.sources.some((item) => item.id === `${base}-${index}`)) index += 1;
  return `${base}-${index}`;
}

function normalizeId(value) {
  return normalizeString(value)
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 64);
}

function normalizeString(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function trimTrailingSlash(value) {
  return String(value || '').replace(/\/+$/, '');
}

function maskApiKey(value = '') {
  const key = normalizeString(value);
  if (!key) return '';
  if (key.length <= 8) return '****';
  return `${key.slice(0, 4)}...${key.slice(-4)}`;
}

function resolveRequestTimeoutMs(requestKind = '', explicitTimeoutMs = undefined) {
  const explicit = parsePositiveInteger(explicitTimeoutMs);
  if (explicit) return explicit;
  const envName = TIMEOUT_ENV_BY_REQUEST_KIND[requestKind] || '';
  const kindTimeout = envName ? parsePositiveInteger(process.env[envName]) : 0;
  if (kindTimeout) return kindTimeout;
  const sharedTimeout = parsePositiveInteger(process.env.ZW_CAD_INTENT_LLM_TIMEOUT_MS);
  if (sharedTimeout) return sharedTimeout;
  return requestKind === 'probe' ? DEFAULT_PROBE_TIMEOUT_MS : DEFAULT_REQUEST_TIMEOUT_MS;
}

function parsePositiveInteger(value) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? Math.round(number) : 0;
}

function buildModelRequestMetadata({
  config = {},
  requestKind = '',
  timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS,
  elapsedMs = 0,
  http_status,
} = {}) {
  return {
    request_kind: requestKind,
    source_id: config.sourceId || '',
    model: config.model || '',
    timeout_ms: Number(timeoutMs),
    elapsed_ms: Math.max(0, Number(elapsedMs) || 0),
    ...(Number.isFinite(http_status) ? { http_status } : {}),
  };
}

function attachModelRequestMetadata(error, requestMetadata = {}) {
  if (!error || typeof error !== 'object') return;
  error.model_request = {
    ...(error.model_request || {}),
    ...(requestMetadata || {}),
  };
}

function logModelRequestFailure(error) {
  const request = error?.model_request || {};
  console.warn('[zwcadintent] LLM request failed', {
    code: error?.code || 'llm_request_failed',
    request_kind: request.request_kind || '',
    source_id: request.source_id || '',
    model: request.model || '',
    elapsed_ms: request.elapsed_ms ?? null,
    timeout_ms: request.timeout_ms ?? null,
    http_status: request.http_status ?? null,
  });
}

function normalizeLlmRequestError(error, { timedOut = false, timeoutMs = DEFAULT_REQUEST_TIMEOUT_MS } = {}) {
  const text = error instanceof Error ? `${error.message || ''} ${error.name || ''}`.trim() : String(error || '');
  if (timedOut || /AbortError|aborted|operation was aborted/i.test(text)) {
    return `本次模型调用超过 ${Math.round(timeoutMs / 1000)} 秒未完成，已中断。请重新发送，或检查模型服务响应时间、网络与 base URL。`;
  }
  if (/timeout|timed out|超时/i.test(text)) {
    return '本次模型调用超时，请检查模型服务响应时间、网络与 base URL。';
  }
  return `模型接口不可用：${error instanceof Error ? error.message : String(error)}`;
}

function isAbortLikeError(error) {
  const text = error instanceof Error ? `${error.name || ''} ${error.message || ''}` : String(error || '');
  return /AbortError|aborted|operation was aborted/i.test(text);
}

function isModelUnavailableError(error) {
  return typeof error?.code === 'string' && error.code.startsWith('llm_');
}

function isReachableModelResponseError(error) {
  return ['llm_empty_response', 'llm_invalid_json'].includes(error?.code);
}

function isConnectionFailureError(error) {
  const code = error?.code || '';
  const requestMetadata = error?.model_request || {};
  const httpStatus = Number(requestMetadata.http_status);
  if (code === 'llm_request_timeout') return true;
  if (code !== 'llm_request_failed') return false;
  if (!Number.isFinite(httpStatus)) return true;
  return httpStatus === 429 || httpStatus >= 500;
}
