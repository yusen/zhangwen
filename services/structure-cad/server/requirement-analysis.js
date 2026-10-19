import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { createHardwareResolver } from './hardware-library.js';
import { hardwareBomTool } from './pipeline/hardware.js';
import { guardIntent, intentAnalyzer, normalizeExternalIntent } from './pipeline/intent.js';
import { buildMissingHardwareResolutionOptions } from './pipeline/recovery.js';
import { isPlainObject, normalizeString, normalizeStringArray } from './pipeline/shared.js';
import { buildNeedsInputGenerationTrace } from './pipeline/trace.js';
import { allocateResultDirectory, cleanupResultDirectories, normalizeTaskId } from './result-store.js';

export function buildMergedIntentBody(body = {}, modelIntentResult = {}) {
  if (modelIntentResult.status === 'needs_input') {
    return {
      generationBody: { ...body, intentAnalysis: modelIntentResult.response?.intent_analysis || {} },
      intentAnalysis: modelIntentResult.response?.intent_analysis || {
        source: 'model_intent',
        status: 'needs_input',
        model_status: 'failed',
        reason: modelIntentResult.reason || '',
        confidence: null,
        conversation_route: body.conversation_route || body.conversationRoute || null,
        revision_intent: body.revision_intent || body.revisionIntent || null,
      },
      localResult: modelIntentResult.response || {
        status: 'needs_input',
        title: 'LLM 模型不可用',
        message: modelIntentResult.reason || 'LLM 模型不可用，无法进行需求分析。',
        blocking_reason: 'llm_intent_failed',
      },
      mergedIntent: null,
    };
  }
  const prompt = normalizeString(body.prompt);
  const latestUserMessage = normalizeString(body.latestUserMessage || body.latest_user_message);
  const selectedHardwareIds = normalizeStringArray(body.selectedHardwareIds);
  const userAnswers = normalizeStringArray(body.userAnswers);
  const currentDesignState = isPlainObject(body.currentDesignState) ? body.currentDesignState : null;
  const hardwareResolver = createHardwareResolver(body.customHardwareProfiles);
  const analysisPrompt = buildRequirementContextText({ prompt, userAnswers, latestUserMessage });
  const usesProvidedIntent = body.intent && isPlainObject(body.intent);
  const localResult = usesProvidedIntent
    ? {
        status: 'ok',
        intent: normalizeExternalIntent(body.intent, { prompt: analysisPrompt || prompt, selectedHardwareIds }),
        confidence: null,
      }
    : intentAnalyzer({
        prompt: analysisPrompt || prompt,
        originalPrompt: prompt,
        selectedHardwareIds,
        currentDesignState,
        userAnswers,
        hardwareResolver,
      });
  const intentAnalysis = {
    source: modelIntentResult.status === 'ok'
      ? usesProvidedIntent ? 'model_intent+provided_intent' : 'model_intent+local_deterministic'
      : usesProvidedIntent ? 'provided_intent' : 'local_deterministic',
    status: localResult.status === 'ok' ? 'ok' : localResult.status || '',
    model_status: modelIntentResult.status || 'skipped',
    reason: modelIntentResult.reason || '',
    confidence: modelIntentResult.confidence ?? localResult.confidence ?? null,
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
  };
  if (localResult.status !== 'ok') {
    return {
      generationBody: { ...body, intentAnalysis },
      intentAnalysis,
      localResult,
      mergedIntent: null,
    };
  }
  const localIntent = guardIntent(localResult.intent);
  const modelIntent = modelIntentResult.status === 'ok' && isPlainObject(modelIntentResult.intent)
    ? guardIntent(normalizeExternalIntent(modelIntentResult.intent, { prompt: analysisPrompt || prompt, selectedHardwareIds }))
    : null;
  const mergedIntent = modelIntent
    ? mergeIntentWithLocalRequirementSignals(modelIntent, localIntent)
    : localIntent;
  return {
    generationBody: {
      ...body,
      prompt,
      intent: mergedIntent,
      intentAnalysis,
      latestUserMessage,
      requirement_context_text: analysisPrompt,
    },
    intentAnalysis,
    localResult,
    modelIntent,
    mergedIntent,
  };
}

export async function buildRequirementAnalysisResponse(body = {}, modelIntentResult = {}, context = {}) {
  const merged = buildMergedIntentBody(body, modelIntentResult);
  if (!merged.mergedIntent) {
    return {
      ...(merged.localResult.response || {
        status: 'needs_input',
        title: '需求分析未通过',
        message: '当前需求无法进入功能拆解。',
        blocking_reason: 'intent_analysis_failed',
      }),
      intent_analysis: merged.intentAnalysis,
      conversation_route: body.conversation_route || body.conversationRoute || null,
      revision_intent: body.revision_intent || body.revisionIntent || null,
    };
  }
  const hardwareResolver = createHardwareResolver(body.customHardwareProfiles);
  const selectedHardwareIds = normalizeStringArray(body.selectedHardwareIds);
  const bomResult = hardwareBomTool({
    intent: merged.mergedIntent,
    selectedHardwareIds,
    hardwareResolver,
  });
  const report = buildRequirementAnalysisReport({
    intent: merged.mergedIntent,
    bomResult,
    hardwareResolver,
    intentAnalysis: merged.intentAnalysis,
    body,
    analysisPrompt: merged.generationBody.requirement_context_text || '',
  });
  const response = {
    status: 'requirement_analysis',
    title: `${merged.mergedIntent.product_name || '产品需求'} 功能分析确认`,
    message: report.user_message,
    requirement_analysis_report: report,
    partial_intent: merged.mergedIntent,
    partial_bom: bomResult.bom || [],
    missing_hardware_requests: bomResult.missing_hardware_requests || [],
    conversation_route: body.conversation_route || body.conversationRoute || null,
    revision_intent: body.revision_intent || body.revisionIntent || null,
    intent_analysis: merged.intentAnalysis,
    questions: [
      '如果这个功能/硬件分析正确，请点击“确认分析”或直接回复“确认”。',
      '如果需求理解不对，请直接在对话框说明要增加、删除或替换的功能。',
    ],
    resolution_options: buildRequirementResolutionOptions(report),
    blocking_reason: report.missing_hardware_requests.length ? 'requirement_analysis_missing_hardware' : 'requirement_analysis_confirmation',
    source: 'deterministic',
  };
  response.generation_trace = buildNeedsInputGenerationTrace({
    status: 'needs_input',
    blocking_reason: response.blocking_reason,
    partial_bom: response.partial_bom,
    missing_hardware_requests: response.missing_hardware_requests,
    conversation_route: response.conversation_route,
    revision_intent: response.revision_intent,
  }, merged.intentAnalysis);
  if (context.rootDir) {
    const stageWrite = await writeRequirementAnalysisStageArtifacts({
      rootDir: context.rootDir,
      body,
      response,
      merged,
      bomResult,
      report,
    });
    response.taskId = stageWrite.taskId || response.taskId || '';
    response.task_id = response.taskId;
    response.task_started_at = stageWrite.started_at || '';
    response.stage_exports = stageWrite.stage_exports || [];
    response.warnings = [...(response.warnings || []), ...(stageWrite.warnings || [])];
  }
  return response;
}

export function buildRequirementContextText({ prompt = '', userAnswers = [], latestUserMessage = '' } = {}) {
  const original = normalizeString(prompt);
  const answers = normalizeStringArray(userAnswers);
  const latest = normalizeString(latestUserMessage);
  const parts = [];
  if (original) parts.push(`原始需求：${original}`);
  if (answers.length) parts.push(`历史补充信息：${answers.join('；')}`);
  if (latest && latest !== original) parts.push(`最新用户消息：${latest}`);
  return parts.join('\n');
}

export async function writeRequirementAnalysisStageArtifacts({
  rootDir,
  body = {},
  response = {},
  merged = {},
  bomResult = {},
  report = {},
} = {}) {
  const warnings = [];
  const requestedTaskId = normalizeTaskId(body.taskId || body.task_id);
  const startedAt = parseStartedAt(body.taskStartedAt || body.task_started_at) || new Date();
  const allocation = await allocateResultDirectory({
    rootDir,
    taskId: requestedTaskId,
    startedAt,
  });
  if (allocation.warning) warnings.push(allocation.warning);
  const taskId = allocation.resultId;
  const workflowDir = path.join(rootDir, 'exports', taskId, 'workflow');
  const stageExports = buildRequirementStageExportEntries({ taskId, workflowDir });
  try {
    await mkdir(workflowDir, { recursive: true });
    await Promise.all([
      writeFile(path.join(workflowDir, '00_requirement_analysis.json'), json({
        status: 'workflow_artifact',
        workflow_step: 0,
        artifact_name: '00_requirement_analysis.json',
        task_stage: 'requirement_analysis',
        design_id: taskId,
        original_prompt: normalizeString(body.prompt),
        latest_user_message: normalizeString(body.latestUserMessage || body.latest_user_message),
        user_answers: normalizeStringArray(body.userAnswers),
        analysis_context: merged.generationBody?.requirement_context_text || report.analysis_context || '',
        requirement_analysis_report: report,
        partial_intent: response.partial_intent || merged.mergedIntent || {},
        partial_bom: response.partial_bom || bomResult.bom || [],
        missing_hardware_requests: response.missing_hardware_requests || bomResult.missing_hardware_requests || [],
        conversation_route: response.conversation_route || null,
        revision_intent: response.revision_intent || null,
        intent_analysis: response.intent_analysis || merged.intentAnalysis || {},
        result_directory: {
          task_id: taskId,
          reused: Boolean(allocation.reused),
          started_at: allocation.started_at,
        },
        source: response.source || 'deterministic',
      })),
      writeFile(path.join(workflowDir, '01_intent.json'), json({
        status: 'workflow_artifact',
        workflow_step: 1,
        artifact_name: '01_intent.json',
        task_stage: 'requirement_analysis',
        partial: true,
        design_id: taskId,
        intent: response.partial_intent || merged.mergedIntent || {},
        conversation_route: response.conversation_route || null,
        revision_intent: response.revision_intent || null,
        intent_analysis: response.intent_analysis || merged.intentAnalysis || {},
        source: response.source || 'deterministic',
      })),
      writeFile(path.join(workflowDir, '02_bom.json'), json({
        status: 'workflow_artifact',
        workflow_step: 2,
        artifact_name: '02_bom.json',
        task_stage: 'requirement_analysis',
        partial: true,
        design_id: taskId,
        bom_count: Array.isArray(response.partial_bom) ? response.partial_bom.length : 0,
        bom: response.partial_bom || bomResult.bom || [],
        missing_hardware_requests: response.missing_hardware_requests || bomResult.missing_hardware_requests || [],
        source: response.source || 'deterministic',
      })),
    ]);
  } catch (error) {
    warnings.push({
      id: 'requirement_stage_artifacts_write_failed',
      status: 'warn',
      message: '需求分析阶段产物写入失败；需求分析结果仍会返回给页面。',
      details: serializeStageArtifactError(error),
    });
  }

  const cleanupReport = await cleanupResultDirectories({ rootDir, keepCount: 3 });
  if (cleanupReport.status !== 'ok') {
    warnings.push({
      id: 'result_history_cleanup_failed',
      status: 'warn',
      message: '历史任务目录清理失败；本轮需求分析已继续返回。',
      details: cleanupReport,
    });
  }

  return {
    taskId,
    started_at: allocation.started_at,
    stage_exports: stageExports,
    warnings,
  };
}

export function mergeIntentWithLocalRequirementSignals(externalIntent = {}, localIntent = {}) {
  const localRequired = normalizeRoleList(localIntent.required_hardware_roles);
  const externalRequired = normalizeRoleList(externalIntent.required_hardware_roles);
  const requiredByRole = new Map(externalRequired.map((role) => [role.role, role]));
  for (const localRole of localRequired) {
    const existing = requiredByRole.get(localRole.role);
    if (!existing) {
      requiredByRole.set(localRole.role, localRole);
      continue;
    }
    requiredByRole.set(localRole.role, {
      ...existing,
      ...Object.fromEntries(Object.entries(localRole).filter(([, value]) => value !== '' && value !== undefined && value !== null)),
      unsupported_in_library: Boolean(existing.unsupported_in_library || localRole.unsupported_in_library),
    });
  }
  const functions = [
    ...normalizeStringArray(externalIntent.functions),
    ...normalizeStringArray(localIntent.functions),
  ];
  return {
    ...externalIntent,
    product_name: normalizeString(localIntent.product_name) || normalizeString(externalIntent.product_name),
    functions: [...new Set(functions)],
    required_hardware_roles: [...requiredByRole.values()],
    mounting_intents: mergeByHardwareId(externalIntent.mounting_intents, localIntent.mounting_intents),
    selected_hardware_ids: [
      ...new Set([
        ...normalizeStringArray(externalIntent.selected_hardware_ids),
        ...normalizeStringArray(localIntent.selected_hardware_ids),
      ]),
    ],
    enclosure_intent: {
      ...(externalIntent.enclosure_intent || {}),
      ...(localIntent.enclosure_intent || {}),
    },
    user_constraints: localIntent.user_constraints || externalIntent.user_constraints || {},
    unknowns: Array.isArray(localIntent.unknowns) ? localIntent.unknowns : externalIntent.unknowns || [],
  };
}

export function buildRequirementAnalysisReport({
  intent = {},
  bomResult = {},
  hardwareResolver = createHardwareResolver(),
  intentAnalysis = {},
  body = {},
  analysisPrompt = '',
} = {}) {
  const bom = Array.isArray(bomResult.bom) ? bomResult.bom : [];
  const missing = Array.isArray(bomResult.missing_hardware_requests) ? bomResult.missing_hardware_requests : [];
  const requiredRoles = normalizeRoleList(intent.required_hardware_roles);
  const matchedByRole = new Map();
  for (const item of bom) {
    const profile = hardwareResolver.getHardwareProfile(item.hardware_id);
    const roles = new Set([item.role, profile?.category, ...(profile?.roles || [])].filter(Boolean));
    for (const required of requiredRoles) {
      if (
        item.role === required.role
        || roles.has(required.role)
        || (required.role === 'controller' && roles.has('compute'))
        || (required.role === 'battery' && roles.has('power'))
      ) {
        if (!matchedByRole.has(required.role)) matchedByRole.set(required.role, item);
      }
    }
  }
  const missingByRole = new Map(missing.map((item) => [item.role, item]));
  const functions = requiredRoles.map((role) => {
    const matched = matchedByRole.get(role.role);
    const missingItem = missingByRole.get(role.role);
    const status = missingItem || role.unsupported_in_library ? 'missing' : matched ? 'available' : 'pending';
    return {
      name: role.function || role.label || role.role,
      required_role: role.role,
      category: role.category,
      required_hardware: role.label || missingItem?.label || matched?.name || role.role,
      library_status: status,
      matched_hardware_id: matched?.hardware_id || '',
      matched_hardware_name: matched?.name || '',
      missing_hardware_label: missingItem?.label || (role.unsupported_in_library ? role.label || role.role : ''),
      why_needed: role.why_needed || '',
    };
  });
  const availableFunctions = functions.filter((item) => item.library_status === 'available').map((item) => item.name);
  const unavailableFunctions = functions.filter((item) => item.library_status === 'missing').map((item) => item.name);
  const pendingFunctions = functions.filter((item) => item.library_status === 'pending').map((item) => item.name);
  const matchedHardware = bom.map((item) => ({
    hardware_id: item.hardware_id,
    name: item.name,
    role: item.role,
    function: functions.find((fn) => fn.required_role === item.role || fn.matched_hardware_id === item.hardware_id)?.name || item.role,
  }));
  return {
    schema_version: 'requirement_analysis_v1',
    product_name: intent.product_name || '电子产品外壳',
    original_prompt: normalizeString(body.prompt),
    latest_user_message: normalizeString(body.latestUserMessage || body.latest_user_message),
    user_answers: normalizeStringArray(body.userAnswers),
    analysis_context: normalizeString(analysisPrompt),
    intent_source: intentAnalysis.source || '',
    model_status: intentAnalysis.model_status || '',
    functions,
    available_functions: availableFunctions,
    unavailable_functions: unavailableFunctions,
    pending_functions: pendingFunctions,
    matched_hardware: matchedHardware,
    missing_hardware_requests: missing,
    can_continue_without_changes: missing.length === 0,
    next_step: missing.length
      ? '请补充缺失硬件 profile，或删除/替换无法实现的功能。'
      : '请确认这个功能和硬件分析是否正确；确认后进入 BOM、尺寸和 2D 参数预审。',
    user_message: buildRequirementUserMessage({
      productName: intent.product_name || '这个产品',
      functions,
      matchedHardware,
      missing,
    }),
  };
}

function buildRequirementResolutionOptions(report = {}) {
  const options = [
    {
      id: 'confirm_requirement_analysis',
      label: '确认分析',
      action: 'confirm_requirement_analysis',
      description: '认可当前功能拆解和硬件库匹配结果，继续进入 BOM、盒体尺寸和 2D 参数预审。',
      recommended: true,
    },
  ];
  if (Array.isArray(report.missing_hardware_requests) && report.missing_hardware_requests.length) {
    options.push(...buildMissingHardwareResolutionOptions(report.missing_hardware_requests));
  }
  options.push({
    id: 'revise_requirement_analysis',
    label: '修改需求',
    action: 'revise_requirement_analysis',
    description: '在对话框说明要砍掉、替换或补充哪些功能。',
    recommended: false,
  });
  return options;
}

function buildRequirementUserMessage({ productName, functions = [], matchedHardware = [], missing = [] }) {
  const functionList = functions.map((item) => item.name).filter(Boolean).join('、') || '暂无明确功能';
  const hardwarePairs = functions
    .map((item) => `${item.name} -> ${item.required_hardware || item.required_role}`)
    .join('；');
  const available = matchedHardware.map((item) => item.name || item.hardware_id).filter(Boolean).join('、') || '暂无';
  const missingPairs = missing
    .map((item) => `${item.function || item.role} -> ${item.label || item.role}`)
    .join('；') || '无';
  const conclusion = missing.length
    ? '因此当前硬件库不能完整实现全部功能，需要补充 profile，或砍掉/替换这些功能后继续。'
    : '当前硬件库可以覆盖这些核心功能，确认后可以进入尺寸和 2D 布局预审。';
  return [
    `我先按需求分析：你要做的是「${productName}」。`,
    `从功能角度，它包含：${functionList}。`,
    `从硬件角度，对应关系是：${hardwarePairs}。`,
    `从 ZW-CAD-intent 硬件库角度，已有硬件：${available}；缺失硬件：${missingPairs}。`,
    `${conclusion}如果你认可这个分析，请确认；如果有不满足的地方，直接告诉我要改哪些功能。`,
  ].join('\n');
}

function normalizeRoleList(value = []) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isPlainObject)
    .map((item) => ({
      role: normalizeString(item.role || item.hardware_role),
      category: normalizeString(item.category),
      function: normalizeString(item.function || item.function_name || item.label),
      label: normalizeString(item.label || item.hardware_label || item.name),
      why_needed: normalizeString(item.why_needed),
      unsupported_in_library: Boolean(item.unsupported_in_library),
      generated_by: normalizeString(item.generated_by),
    }))
    .filter((item) => item.role && item.category);
}

function mergeByHardwareId(first = [], second = []) {
  const map = new Map();
  for (const item of [...(Array.isArray(first) ? first : []), ...(Array.isArray(second) ? second : [])]) {
    if (item?.hardware_id && !map.has(item.hardware_id)) map.set(item.hardware_id, item);
  }
  return [...map.values()];
}

function buildRequirementStageExportEntries({ taskId, workflowDir }) {
  return [
    {
      id: 'workflow_requirement_analysis_json',
      workflow_step: 0,
      label: '00 需求-功能-选型分析 JSON',
      format: 'json',
      fidelity: 'workflow_debug_requirement_analysis',
      url: `/exports/${taskId}/workflow/00_requirement_analysis.json`,
      path: path.join(workflowDir, '00_requirement_analysis.json'),
    },
    {
      id: 'workflow_intent_json',
      workflow_step: 1,
      label: '01 用户意图 JSON',
      format: 'json',
      fidelity: 'workflow_debug_intent_partial',
      url: `/exports/${taskId}/workflow/01_intent.json`,
      path: path.join(workflowDir, '01_intent.json'),
      status: 'partial',
    },
    {
      id: 'workflow_bom_json',
      workflow_step: 2,
      label: '02 硬件 BOM JSON',
      format: 'json',
      fidelity: 'workflow_debug_bom_partial',
      url: `/exports/${taskId}/workflow/02_bom.json`,
      path: path.join(workflowDir, '02_bom.json'),
      status: 'partial',
    },
  ];
}

function parseStartedAt(value) {
  const text = normalizeString(value);
  if (!text) return null;
  const date = new Date(text);
  return Number.isFinite(date.getTime()) ? date : null;
}

function json(value) {
  return `${JSON.stringify(value, null, 2)}\n`;
}

function serializeStageArtifactError(error) {
  if (!error || typeof error !== 'object') return { message: String(error || 'unknown stage artifact error') };
  return {
    name: error.name || 'Error',
    code: typeof error.code === 'string' ? error.code : '',
    path: typeof error.path === 'string' ? error.path : '',
    message: error instanceof Error ? error.message : String(error),
  };
}
