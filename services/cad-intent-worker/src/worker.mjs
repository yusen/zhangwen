import crypto from 'node:crypto';
import { spawn } from 'node:child_process';
import { readFile } from 'node:fs/promises';
import path from 'node:path';
import readline from 'node:readline';

import { sanitizeBuildResult } from './build-result.mjs';
import { buildConversationRoute } from '../../../references/source-packages/ZW-CAD-intent/server/conversation-route.js';
import {
  buildDeterministicProductResponse,
  detectDeterministicProduct,
  listDeterministicTemplateProjects,
} from '../../../references/source-packages/ZW-CAD-intent/server/deterministic-products.js';
import { buildCadQueryArtifact, preflightCadQueryCode } from '../../../references/source-packages/ZW-CAD-intent/server/cadquery-runner.js';
import { detectStandaloneStructuralPartsRequest } from '../../../references/source-packages/ZW-CAD-intent/server/structural-parts.js';
import { isSurfaceEngravingPrompt } from '../../../references/source-packages/ZW-CAD-intent/server/surface-engraving.js';
import { buildBatchModelTemplate } from '../../../references/source-packages/ZW-CAD-intent/server/template-library/batch-model-cases.js';
import { buildUnihikerPhotoAlbumTemplate } from '../../../references/source-packages/ZW-CAD-intent/server/template-library/unihiker-photo-album.js';
import { buildUnihikerSmartWateringTemplate } from '../../../references/source-packages/ZW-CAD-intent/server/template-library/unihiker-smart-watering-system.js';
import { buildXiaoSmartPendantTemplate } from '../../../references/source-packages/ZW-CAD-intent/server/template-library/xiao-smart-pendant.js';
import { listWorkflowTools } from '../../../references/source-packages/ZW-CAD-intent/server/workflow-tools.js';

const PROTOCOL = 'zhangwen.cad.intent.worker';
const VERSION = 1;
const MAX_LINE_BYTES = 512 * 1024;
const MAX_SOURCE_BYTES = 384 * 1024;
const FORBIDDEN_KEYS = new Set([
  'rootdir', 'workingdirectory', 'cwd', 'path', 'filepath', 'shell', 'command',
  'argv', 'apikey', 'providerkey', 'token', 'password', 'modelsource',
]);

const input = readline.createInterface({ input: process.stdin, crlfDelay: Infinity });
for await (const line of input) {
  if (!line.trim()) continue;
  let requestId = 'invalid';
  try {
    if (Buffer.byteLength(line, 'utf8') > MAX_LINE_BYTES) throw failure('REQUEST_TOO_LARGE', 'CAD Intent 请求超过大小上限。');
    const request = JSON.parse(line);
    requestId = text(request?.id) || requestId;
    validateRequest(request);
    const result = await dispatch(request.action, request.payload || {});
    write({ protocol: PROTOCOL, version: VERSION, id: request.id, ok: true, result });
  } catch (error) {
    write({
      protocol: PROTOCOL,
      version: VERSION,
      id: requestId,
      ok: false,
      error: {
        code: text(error?.code) || 'CAD_INTENT_WORKER_ERROR',
        message: error instanceof Error ? error.message : String(error),
        retryable: false,
      },
    });
  }
}

async function dispatch(action, payload) {
  if (action === 'describe') {
    return {
      source: 'ZW-CAD-intent',
      sourceTreeSha256: 'c6054bcb0a3c106f931583eb931babd1c0cf846b03f08343aafdb509a3a852ee',
      templates: listDeterministicTemplateProjects().map((item) => ({ id: item.id, name: item.name, status: item.status })),
      workflowTools: listWorkflowTools().map((item) => ({ id: item.id, stage: item.stage, kind: item.kind || 'deterministic_tool' })),
      boundaries: ['no_http', 'no_project_store', 'no_provider_credentials', 'no_arbitrary_path', 'no_hardware_truth_write'],
    };
  }
  if (action === 'route') return routeIntent(payload);
  if (action === 'draft') return draftIntent(payload);
  if (action === 'plan_edit') return planEdit(payload);
  if (action === 'preflight') return preflight(payload);
  if (action === 'build') return build(payload);
  throw failure('ACTION_NOT_ALLOWED', `CAD Intent action 不允许：${action}`);
}

function routeIntent(payload) {
  const prompt = boundedText(payload.prompt, 4000, 'prompt');
  const body = requestBody(payload, prompt);
  const route = buildConversationRoute(body);
  const product = detectProductWithCurrentTurnPriority(body, prompt);
  const structural = detectStandaloneStructuralPartsRequest(body);
  return {
    kind: 'RequirementAnalysis',
    route,
    deterministicProduct: product ? compactProduct(product) : null,
    standaloneStructuralParts: structural,
    surfaceEngraving: isSurfaceEngravingPrompt(prompt),
    capabilityGap: capabilityGap(product, payload.capabilitySnapshot),
  };
}

function draftIntent(payload) {
  const prompt = boundedText(payload.prompt, 4000, 'prompt');
  const body = requestBody(payload, prompt);
  const route = buildConversationRoute(body);
  const detection = detectProductWithCurrentTurnPriority(body, prompt);
  if (!detection?.product) {
    return {
      kind: 'CadDraft',
      status: 'needs_input',
      route,
      message: '当前自由结构还没有命中经过验证的确定性模板；请补充关键尺寸、结构对象或选择受信模板。',
      capabilityGap: [],
    };
  }
  const artifact = buildTemplateArtifact(detection, body);
  const source = text(artifact?.cadquery_code);
  if (!source) {
    return {
      kind: 'CadDraft',
      status: 'needs_input',
      route,
      deterministicProduct: compactProduct(detection),
      message: text(artifact?.message) || '模板尚未形成可构建 CadQuery 源码。',
      capabilityGap: capabilityGap(detection, payload.capabilitySnapshot),
    };
  }
  assertSourceSize(source);
  return {
    kind: 'CadDraft',
    status: 'ready',
    route,
    deterministicProduct: compactProduct(detection),
    source,
    sourceSha256: sha256(source),
    objectIndex: buildObjectIndex(artifact),
    designState: boundedDesignState(artifact.design_state),
    previewAssets: Array.isArray(artifact.preview_assets) ? artifact.preview_assets.slice(0, 64) : [],
    checks: Array.isArray(artifact.checks) ? artifact.checks.slice(0, 100) : [],
    warnings: Array.isArray(artifact.warnings) ? artifact.warnings.slice(0, 50) : [],
    capabilityGap: capabilityGap(detection, payload.capabilitySnapshot),
  };
}

function planEdit(payload) {
  const prompt = boundedText(payload.prompt, 4000, 'prompt');
  const source = boundedSource(payload.source);
  const expectedHash = text(payload.sourceSha256).toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(expectedHash) || sha256(source) !== expectedHash) {
    throw failure('SOURCE_HASH_MISMATCH', '当前 CAD 源码哈希与请求不一致，已停止修改。');
  }
  const route = buildConversationRoute(requestBody(payload, prompt));
  const thickness = thicknessPlan(prompt, source);
  if (thickness) {
    const nextSource = applyExactPatch(source, thickness.patch);
    return {
      kind: 'CadChangeSet',
      status: 'ready',
      route,
      riskLevel: 'MEDIUM',
      confirmationPolicy: 'USER',
      operations: [{ type: 'parameter_patch', target: 'wall_thickness', from: thickness.from, to: thickness.to }],
      patch: { ...thickness.patch, resultSha256: sha256(nextSource) },
      sourceSha256: expectedHash,
      resultSourceSha256: sha256(nextSource),
      objectIndex: Array.isArray(payload.objectIndex) ? payload.objectIndex.slice(0, 256) : [],
    };
  }
  if (isSurfaceEngravingPrompt(prompt)) {
    return {
      kind: 'CadChangeSet',
      status: 'needs_input',
      route,
      riskLevel: 'MEDIUM',
      confirmationPolicy: 'USER',
      operations: [{ type: 'surface_engraving', prompt }],
      missingFields: engravingMissingFields(prompt),
      message: '刻字会使用 ZW-CAD-intent 的表面选择和预检流程；请补齐目标表面、文字和字高后再生成精确补丁。',
      sourceSha256: expectedHash,
    };
  }
  return {
    kind: 'CadChangeSet',
    status: 'needs_input',
    route,
    riskLevel: 'MEDIUM',
    confirmationPolicy: 'USER',
    operations: [],
    missingFields: ['target_object', 'bounded_dimension_or_feature'],
    message: '请指出要修改的对象，并提供可验证的尺寸或特征，例如“底壳壁厚增加 1mm”。',
    sourceSha256: expectedHash,
  };
}

async function preflight(payload) {
  const source = boundedSource(payload.source);
  assertSourceSize(source);
  const python = text(process.env.ZHANGWEN_CAD_PYTHON) || 'python';
  const result = await preflightCadQueryCode({ python, code: source });
  return { kind: 'CadValidationReport', sourceSha256: sha256(source), preflight: result };
}

async function build(payload) {
  const source = boundedSource(payload.source);
  const expectedHash = text(payload.sourceSha256).toLowerCase();
  if (!/^[a-f0-9]{64}$/.test(expectedHash) || sha256(source) !== expectedHash) {
    throw failure('SOURCE_HASH_MISMATCH', '构建源码哈希与已确认修订不一致。');
  }
  const rootDir = text(process.env.ZHANGWEN_CAD_STAGING_ROOT);
  if (!rootDir || !path.isAbsolute(rootDir)) {
    throw failure('CAD_STAGING_UNAVAILABLE', 'CAD 构建暂存目录未由宿主配置。');
  }
  const python = text(process.env.ZHANGWEN_CAD_PYTHON) || 'python';
  const environment = {
    cadqueryAvailable: process.env.ZHANGWEN_CADQUERY_AVAILABLE === '1',
    requiredPythonPackages: ['cadquery', 'OCP'],
  };
  const result = await buildCadQueryArtifact({
    rootDir,
    python,
    environment,
    body: { cadquery_code: source },
  });
  const withPreview = await ensureGlbPreview(result, python);
  return sanitizeBuildResult(withPreview, rootDir, expectedHash);
}

async function ensureGlbPreview(result, python) {
  if (text(result?.status) !== 'artifact_exports' || !Array.isArray(result?.exports)) return result;
  const existing = result.exports.find((item) => text(item?.format).toLowerCase() === 'glb');
  if (existing) return result;
  const source = result.exports.find((item) => {
    const format = text(item?.format).toLowerCase();
    const filePath = text(item?.path);
    return format === 'stl' && path.basename(filePath).toLowerCase() === 'model.stl';
  }) || result.exports.find((item) => text(item?.format).toLowerCase() === 'stl');
  const sourcePath = text(source?.path);
  if (!sourcePath || !path.isAbsolute(sourcePath)) {
    return {
      ...result,
      status: 'fail',
      blocking_reason: 'glb_preview_source_missing',
      message: 'CAD 构建没有生成可转换的 STL 预览源。',
    };
  }
  const previewPath = path.join(path.dirname(sourcePath), 'preview.glb');
  const script = [
    'import pathlib, sys, trimesh',
    'scene = trimesh.load(sys.argv[1], force="scene")',
    'payload = scene.export(file_type="glb")',
    'pathlib.Path(sys.argv[2]).write_bytes(payload)',
  ].join('\n');
  await runProcess(python, ['-c', script, sourcePath, previewPath], 60000);
  let previewSize = 0;
  let previewMagic = '';
  try {
    const preview = await readFile(previewPath);
    previewSize = preview.length;
    previewMagic = preview.subarray(0, 4).toString('ascii');
  } catch {
    previewSize = 0;
  }
  if (previewSize <= 0 || previewMagic !== 'glTF') {
    return {
      ...result,
      status: 'fail',
      blocking_reason: 'glb_preview_failed',
      message: 'CAD 已导出 STEP/STL，但 GLB 三维预览生成失败。',
    };
  }
  return {
    ...result,
    exports: [
      ...result.exports,
      {
        id: 'cadquery_glb_preview',
        label: '3D 交互预览 GLB',
        format: 'glb',
        path: previewPath,
        fidelity: 'cadquery_tessellation',
        status: 'available',
      },
    ],
  };
}

function runProcess(executable, args, timeoutMs) {
  return new Promise((resolve) => {
    const child = spawn(executable, args, {
      windowsHide: true,
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => child.kill(), timeoutMs);
    child.stdout.on('data', (chunk) => { stdout += chunk.toString('utf8'); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString('utf8'); });
    child.on('close', (exitCode) => {
      clearTimeout(timer);
      resolve({ exitCode: Number(exitCode ?? 1), stdout, stderr });
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ exitCode: 1, stdout, stderr: error.message });
    });
  });
}

function buildTemplateArtifact(detection, body) {
  const context = { stage: 'artifact', designId: text(body.projectId) || 'ZW-V2-CAD-DRAFT' };
  const args = { product: detection.product, detection, body, context };
  if (detection.product.id === 'unihiker_plant_caregiver') return buildUnihikerSmartWateringTemplate(args);
  if (detection.product.id === 'unihiker_photo_album') return buildUnihikerPhotoAlbumTemplate(args);
  if (detection.product.id === 'xiao_smart_pendant') return buildXiaoSmartPendantTemplate(args);
  if (detection.product.template_case === true) return buildBatchModelTemplate(args);
  return buildDeterministicProductResponse(detection, body);
}

function requestBody(payload, prompt) {
  const projectContext = controlledProjectStructureContext(payload);
  const selectedHardwareIds = projectContext
    ? projectContext.selectedHardware.map((item) => item.id)
    : stringArray(payload.hardwareProfileSnapshot?.selectedHardwareIds, 64);
  const currentRevision = isObject(payload.currentCadRevision)
    ? payload.currentCadRevision
    : projectContext?.currentCadRevision;
  return {
    prompt,
    latestUserMessage: prompt,
    routeAction: text(payload.routeAction),
    selectedHardwareIds,
    userAnswers: projectContextAnswers(projectContext),
    currentDesignState: isObject(currentRevision) ? {
      id: text(currentRevision.id),
      source_hash: text(currentRevision.sourceSha256),
      object_index: Array.isArray(currentRevision.objectIndex) ? currentRevision.objectIndex.slice(0, 256) : [],
    } : null,
    conversationContext: isObject(payload.routeContext) ? safeObject(payload.routeContext, 64) : {},
    projectId: text(payload.projectId),
    projectStructureContext: projectContext,
  };
}

function detectProductWithCurrentTurnPriority(body, prompt) {
  const explicitTurn = detectDeterministicProduct({
    ...body,
    prompt,
    latestUserMessage: prompt,
    userAnswers: [],
  });
  return explicitTurn || detectDeterministicProduct(body);
}

function controlledProjectStructureContext(payload) {
  const value = payload.projectStructureContext;
  if (value == null) return null;
  if (!isObject(value)
    || value.schemaVersion !== 1
    || text(value.projectId) !== text(payload.projectId)
    || Number(value.projectVersion) !== Number(payload.baseProjectVersion)
    || !/^[a-f0-9]{64}$/.test(text(value.projectionHash).toLowerCase())
    || !/^[a-f0-9]{64}$/.test(text(value.contextSha256).toLowerCase())) {
    throw failure('PROJECT_STRUCTURE_CONTEXT_INVALID', 'CAD Intent 项目结构上下文与当前项目版本不匹配。');
  }
  const selectedHardware = (Array.isArray(value.selectedHardware) ? value.selectedHardware : [])
    .slice(0, 32)
    .filter((item) => isObject(item) && text(item.id) && text(item.name))
    .map((item) => ({
      id: text(item.id).slice(0, 160),
      name: text(item.name).slice(0, 200),
      skillName: text(item.skillName).slice(0, 200),
      skillRevision: text(item.skillRevision).slice(0, 160),
    }));
  const confirmedFacts = (Array.isArray(value.confirmedFacts) ? value.confirmedFacts : [])
    .slice(0, 24)
    .filter((item) => isObject(item) && text(item.key))
    .map((item) => ({
      key: text(item.key).slice(0, 120),
      label: text(item.label).slice(0, 200),
      displayValue: text(item.displayValue).slice(0, 1200),
      revision: Math.max(0, Number(item.revision) || 0),
    }));
  const upstreamArtifacts = (Array.isArray(value.upstreamArtifacts) ? value.upstreamArtifacts : [])
    .slice(0, 12)
    .filter((item) => isObject(item) && text(item.artifactId))
    .map((item) => ({
      artifactId: text(item.artifactId).slice(0, 160),
      title: text(item.title).slice(0, 240),
      kind: text(item.kind).slice(0, 80),
      summary: text(item.summary).slice(0, 1200),
    }));
  const mechanicalProfiles = (Array.isArray(value.mechanicalProfiles) ? value.mechanicalProfiles : [])
    .slice(0, 32)
    .filter((item) => isObject(item) && text(item.hardwareId) && text(item.profileId))
    .map((item) => ({
      hardwareId: text(item.hardwareId).slice(0, 160),
      profileId: text(item.profileId).slice(0, 160),
      revision: text(item.revision).slice(0, 160),
      displayName: text(item.displayName).slice(0, 240),
      evidenceLevel: text(item.evidenceLevel).slice(0, 80),
      representation: text(item.representation).slice(0, 120),
      contentSha256: text(item.contentSha256).toLowerCase(),
      geometry: controlledProfileGeometry(item.geometry),
    }));
  const currentCadRevision = isObject(value.currentCadRevision)
    ? {
        id: text(value.currentCadRevision.id).slice(0, 160),
        sourceSha256: text(value.currentCadRevision.sourceSha256).toLowerCase(),
        objectIndex: Array.isArray(value.currentCadRevision.objectIndex)
          ? value.currentCadRevision.objectIndex.slice(0, 256)
          : [],
      }
    : null;
  return {
    schemaVersion: 1,
    projectId: text(value.projectId),
    projectVersion: Number(value.projectVersion),
    projectionHash: text(value.projectionHash).toLowerCase(),
    contextSha256: text(value.contextSha256).toLowerCase(),
    projectName: text(value.projectName).slice(0, 120),
    initialIdea: text(value.initialIdea).slice(0, 4000),
    currentRecommendation: text(value.currentRecommendation).slice(0, 4000),
    stage: text(value.stage).slice(0, 80),
    mode: text(value.mode).slice(0, 80),
    confirmedFacts,
    selectedHardware,
    mechanicalProfiles,
    upstreamArtifacts,
    currentCadRevision,
  };
}

function projectContextAnswers(context) {
  if (!context) return [];
  const result = [
    context.projectName,
    context.initialIdea,
    context.currentRecommendation,
    ...context.confirmedFacts.flatMap((item) => [item.label, item.displayValue]),
    ...context.upstreamArtifacts.flatMap((item) => [item.title, item.summary]),
  ].map(text).filter(Boolean);
  return [...new Set(result)].slice(0, 64);
}

function controlledProfileGeometry(value) {
  if (!isObject(value)) return {};
  const allowed = [
    'profile_id', 'revision', 'category', 'roles', 'dimensions',
    'coordinate_system', 'mounting', 'model_kind', 'keepouts',
    'openings', 'preview_geometry',
  ];
  return Object.fromEntries(
    allowed
      .filter((key) => key in value)
      .map((key) => [key, controlledJson(value[key], 0)]),
  );
}

function controlledJson(value, depth) {
  if (depth > 6 || value == null) return value == null ? null : undefined;
  if (['boolean', 'number'].includes(typeof value)) return value;
  if (typeof value === 'string') return value.slice(0, 500);
  if (Array.isArray(value)) return value.slice(0, 64).map((item) => controlledJson(item, depth + 1));
  if (isObject(value)) {
    return Object.fromEntries(
      Object.entries(value)
        .slice(0, 64)
        .map(([key, child]) => [key.slice(0, 120), controlledJson(child, depth + 1)]),
    );
  }
  return undefined;
}

function thicknessPlan(prompt, source) {
  if (!/(壁厚|wall\s*thickness|加厚|thicken)/i.test(prompt)) return null;
  const match = source.match(/wall_thickness["']?\s*[:=]\s*(\d+(?:\.\d+)?)/);
  if (!match) return null;
  const current = Number(match[1]);
  const setMatch = prompt.match(/(?:改为|设为|调整为|to)\s*(\d+(?:\.\d+)?)\s*mm/i);
  const deltaMatch = prompt.match(/(?:增加|加厚|增厚|by)\s*(\d+(?:\.\d+)?)\s*mm/i);
  const next = setMatch ? Number(setMatch[1]) : deltaMatch ? current + Number(deltaMatch[1]) : NaN;
  if (!Number.isFinite(next) || next < 1 || next > 8) return null;
  const search = match[0];
  const replace = search.replace(match[1], String(Number(next.toFixed(3))));
  return { from: current, to: next, patch: { search, replace, occurrence: 1 } };
}

function applyExactPatch(source, patch) {
  const first = source.indexOf(patch.search);
  if (first < 0 || source.indexOf(patch.search, first + patch.search.length) >= 0) {
    throw failure('PATCH_TARGET_AMBIGUOUS', '源码补丁目标不存在或不唯一。');
  }
  return `${source.slice(0, first)}${patch.replace}${source.slice(first + patch.search.length)}`;
}

function engravingMissingFields(prompt) {
  const missing = [];
  if (!/(上盖|底壳|正面|背面|侧面|斜面|top|lid|base|side|front|back)/i.test(prompt)) missing.push('target_surface');
  if (!/[“"'].*[”"']|(?:刻上|文字|text)\s*[\p{L}\p{N}]/iu.test(prompt)) missing.push('text');
  if (!/(?:字高|font\s*height)\s*\d+(?:\.\d+)?\s*mm/i.test(prompt)) missing.push('font_height_mm');
  return missing;
}

function buildObjectIndex(artifact) {
  const result = [
    { id: 'assembly', type: 'assembly', label: '当前装配', parentId: null },
    { id: 'base_part', type: 'part', label: '底壳', parentId: 'assembly' },
    { id: 'lid_part', type: 'part', label: '上盖', parentId: 'assembly' },
  ];
  const transforms = artifact?.design_state?.layout_plan?.hardware_transforms;
  if (Array.isArray(transforms)) {
    for (const item of transforms.slice(0, 64)) {
      const id = text(item?.hardware_id);
      if (id) result.push({ id: `hardware:${id}`, type: 'hardware_reference', label: id, parentId: 'assembly' });
    }
  }
  return result;
}

function boundedDesignState(value) {
  if (!isObject(value)) return null;
  const allowed = ['id', 'template_id', 'cad_parameters', 'enclosure_parameters', 'parameters', 'mounting_plan', 'warnings'];
  return Object.fromEntries(allowed.filter((key) => key in value).map((key) => [key, value[key]]));
}

function capabilityGap(detection, snapshot) {
  if (!detection?.product) return [];
  const verifiedSources = new Set(
    (Array.isArray(snapshot) ? snapshot : [])
      .filter((item) => item?.status === 'VERIFIED')
      .map((item) => text(item?.sourceId)),
  );
  return (detection.product.hardware || [])
    .map((item) => text(item.hardware_id))
    .filter((id) => id && !verifiedSources.has(id));
}

function compactProduct(detection) {
  return {
    id: detection.product.id,
    name: detection.product.product_name || detection.product.name,
    templateId: detection.product.template_id,
    hardwareIds: (detection.product.hardware || []).map((item) => item.hardware_id),
    confidence: detection.confidence,
    reason: detection.reason,
  };
}

function validateRequest(request) {
  if (!isObject(request) || request.protocol !== PROTOCOL || request.version !== VERSION) throw failure('PROTOCOL_INVALID', 'CAD Intent Worker 协议不匹配。');
  if (!/^[A-Za-z0-9_.:-]{1,120}$/.test(text(request.id))) throw failure('REQUEST_ID_INVALID', 'CAD Intent 请求 ID 无效。');
  if (!['describe', 'route', 'draft', 'plan_edit', 'preflight', 'build'].includes(request.action)) throw failure('ACTION_NOT_ALLOWED', 'CAD Intent action 不允许。');
  rejectForbiddenKeys(request.payload || {});
}

function rejectForbiddenKeys(value) {
  if (Array.isArray(value)) { value.forEach(rejectForbiddenKeys); return; }
  if (!isObject(value)) return;
  for (const [key, child] of Object.entries(value)) {
    const normalized = key.replace(/[^a-z0-9]/gi, '').toLowerCase();
    if (FORBIDDEN_KEYS.has(normalized)) throw failure('FORBIDDEN_FIELD', `CAD Intent 请求字段不允许：${key}`);
    rejectForbiddenKeys(child);
  }
}

function safeObject(value, maxKeys) {
  return Object.fromEntries(Object.entries(value).slice(0, maxKeys).filter(([, child]) => ['string', 'number', 'boolean'].includes(typeof child) || child === null));
}

function stringArray(value, maxItems) { return Array.isArray(value) ? value.filter((item) => typeof item === 'string').slice(0, maxItems) : []; }
function boundedText(value, max, label) { const result = text(value); if (!result || Buffer.byteLength(result, 'utf8') > max) throw failure('FIELD_INVALID', `${label} 缺失或超过大小上限。`); return result; }
function boundedSource(value) { if (typeof value !== 'string' || !value || Buffer.byteLength(value, 'utf8') > MAX_SOURCE_BYTES) throw failure('FIELD_INVALID', 'source 缺失或超过大小上限。'); return value; }
function assertSourceSize(source) { if (Buffer.byteLength(source, 'utf8') > MAX_SOURCE_BYTES) throw failure('SOURCE_TOO_LARGE', 'CAD 源码超过 Worker 上限。'); }
function text(value) { return typeof value === 'string' ? value.trim() : ''; }
function isObject(value) { return Boolean(value) && typeof value === 'object' && !Array.isArray(value); }
function sha256(value) { return crypto.createHash('sha256').update(value, 'utf8').digest('hex'); }
function failure(code, message) { const error = new Error(message); error.code = code; return error; }
function write(value) { process.stdout.write(`${JSON.stringify(value)}\n`); }
