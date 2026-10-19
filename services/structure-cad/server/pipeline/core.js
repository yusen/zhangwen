import crypto from 'node:crypto';
import { createHardwareResolver, getHardwareLibrarySummary } from '../hardware-library.js';
import { allocateResultDirectory, cleanupResultDirectories, clearManagedResultArtifacts, normalizeTaskId } from '../result-store.js';
import { writeArtifactMetadataFiles, writeArtifactSnapshotFile } from '../stl-exporter.js';
import { buildFailedWorkflowArtifactExports, writeWorkflowArtifactFiles } from '../workflow-artifacts.js';
import { buildFunctionVerifyUnavailableResult } from '../function-verifier.js';
import { buildExportWriteWarning, buildFailedMetadataExports, buildParameterGroups, buildPreviewAssets, enclosureGenerator, exportPreviewTool } from './cad.js';
import { applyHardwareFaceOverrides, applyHardwareRotationOverrides, hardwareBomTool, hardwareProfileTool, orientationTool } from './hardware.js';
import { guardIntent, intentAnalyzer, normalizeExternalIntent } from './intent.js';
import { boxSizingTool, faceCapacityChecker, layoutSolverTool, repairFaceCapacityByExpandingBox } from './layout.js';
import { buildFaceCapacityResolutionOptions, buildMissingHardwareResolutionOptions, buildNeedsInputFromTool, buildProfileIncompleteResolutionOptions, buildValidationFailureQuestions, buildValidationFailureResolutionOptions, repairValidationFailure } from './recovery.js';
import { DEFAULT_PARAMETERS, isPlainObject, normalizeHardwareFaceOverrides, normalizeHardwareRotationOverrides, normalizeNumberMap, normalizeString, normalizeStringArray } from './shared.js';
import { buildGenerationTrace, buildNeedsInputGenerationTrace, findBlockingValidationFailure, withNeedsInputGenerationTrace } from './trace.js';
import { validateDesign } from './validation.js';

export async function generateDesign(body = {}, context = {}) {
  const prepared = await prepareDesignCore(body, context, { stage: 'artifact' });
  if (prepared.status !== 'prepared') return prepared.response;
  return buildArtifactFromPrepared(prepared, context);
}

export async function prepareDesign(body = {}, context = {}) {
  const prepared = await prepareDesignCore(body, context, { stage: 'confirmation' });
  if (prepared.status !== 'prepared') return prepared.response;
  const draft = buildDesignDraft(prepared);
  draft.generation_trace = buildGenerationTrace({
    stage: 'confirmation',
    intentAnalysis: prepared.intentAnalysis,
    bom: prepared.bomResult.bom,
    designState: draft.design_state,
    layoutPlan: prepared.layoutPlan,
    validation: prepared.validation,
    exports: [],
    profileValidationReport: prepared.profileResult.profile_validation_report,
  });
  draft.design_state.generation_trace = draft.generation_trace;
  return draft;
}

export async function buildDesignFromDraft(body = {}, context = {}) {
  const draftState = isPlainObject(body.draftDesignState)
    ? body.draftDesignState
    : isPlainObject(body.design_state)
      ? body.design_state
      : isPlainObject(body.designState)
        ? body.designState
        : null;
  if (!draftState?.intent) {
    return withNeedsInputGenerationTrace({
      status: 'needs_input',
      title: '缺少确认草案',
      message: '缺少可建模的确认草案，请先完成需求分析和参数确认。',
      questions: ['请先提交需求并确认 BOM、盒体尺寸和硬件摆放。'],
      blocking_reason: 'missing_confirmed_draft',
    }, {
      source: 'build',
      status: 'needs_input',
      model_status: 'skipped',
      reason: 'missing_confirmed_draft',
      confidence: null,
    });
  }
  return generateDesign({
    prompt: body.prompt || draftState.intent.product_name,
    selectedHardwareIds: draftState.bom?.map((item) => item.hardware_id) || [],
    currentDesignState: draftState,
    taskId: body.taskId || body.task_id,
    parameterOverrides: body.parameterOverrides,
    hardwareFaceOverrides: body.hardwareFaceOverrides,
    hardwareRotationOverrides: body.hardwareRotationOverrides,
    customHardwareProfiles: body.customHardwareProfiles || extractCustomProfilesFromDesignState(draftState),
    intent: draftState.intent,
    intentAnalysis: body.intentAnalysis || draftState.intent_analysis || draftState.intentAnalysis,
    conversationRoute: body.conversationRoute || body.conversation_route || draftState.conversation_route,
    revisionIntent: body.revisionIntent || body.revision_intent || draftState.revision_intent,
    resolutionOptionRoute: body.resolutionOptionRoute || body.resolution_option_route || draftState.resolution_option_route,
    ignoredMissingHardwareRequests: body.ignoredMissingHardwareRequests || body.ignored_missing_hardware_requests || draftState.ignored_missing_hardware_requests,
    droppedFunctions: body.droppedFunctions || body.dropped_functions || draftState.dropped_functions,
  }, context);
}

export async function prepareDesignCore(body = {}, context = {}, options = {}) {
  const prompt = normalizeString(body.prompt);
  if (!prompt) {
    return {
      status: 'needs_input',
      response: withNeedsInputGenerationTrace({
        status: 'needs_input',
        message: '请先描述你想做的电子产品外壳。',
        questions: ['你想做什么设备？需要哪些功能或硬件？'],
        blocking_reason: 'empty_prompt',
      }, {
        source: 'none',
        status: 'needs_input',
        model_status: 'skipped',
        reason: 'empty_prompt',
        confidence: null,
      }),
    };
  }

  const selectedHardwareIds = normalizeStringArray(body.selectedHardwareIds);
  const parameterOverrides = normalizeNumberMap(body.parameterOverrides);
  const userAnswers = normalizeStringArray(body.userAnswers);
  const currentDesignState = isPlainObject(body.currentDesignState) ? body.currentDesignState : null;
  const taskId = normalizeTaskId(body.taskId || body.task_id || currentDesignState?.id);
  const taskStartedAt = normalizeString(body.taskStartedAt || body.task_started_at || currentDesignState?.result_started_at);
  const hardwareFaceOverrides = normalizeHardwareFaceOverrides(body.hardwareFaceOverrides || currentDesignState?.hardware_face_overrides);
  const hardwareRotationOverrides = normalizeHardwareRotationOverrides(body.hardwareRotationOverrides || currentDesignState?.hardware_rotation_overrides);
  const hardwareResolver = createHardwareResolver(body.customHardwareProfiles);
  const intentResult = body.intent && isPlainObject(body.intent)
    ? { status: 'ok', intent: normalizeExternalIntent(body.intent, { prompt, selectedHardwareIds }) }
    : intentAnalyzer({
        prompt,
        selectedHardwareIds,
        currentDesignState,
        userAnswers,
        hardwareResolver,
      });
  const intentAnalysis = buildIntentAnalysis({ body, intentResult });
  const conversationRoute = conversationRouteFromBody(body);
  const revisionIntent = revisionIntentFromBody(body);
  const resolutionOptionRoute = resolutionOptionRouteFromBody(body);

  if (intentResult.status !== 'ok') {
    return {
      status: 'needs_input',
      response: attachIntentAnalysis(intentResult.response, intentAnalysis, { conversationRoute, revisionIntent }),
    };
  }

  let guardedIntent = guardIntent(intentResult.intent);
  let ignoredMissingHardwareRequests = normalizeIgnoredMissingHardwareRequests(body.ignoredMissingHardwareRequests || body.ignored_missing_hardware_requests);
  let droppedFunctions = normalizeStringArray(body.droppedFunctions || body.dropped_functions);
  let bomResult = hardwareBomTool({
    intent: guardedIntent,
    selectedHardwareIds,
    hardwareResolver,
  });
  if (bomResult.status !== 'ok') {
    if (shouldIgnoreMissingHardware(body) && Array.isArray(bomResult.missing_hardware_requests) && bomResult.missing_hardware_requests.length) {
      const filtered = dropMissingHardwareFromIntent(guardedIntent, bomResult.missing_hardware_requests);
      guardedIntent = filtered.intent;
      ignoredMissingHardwareRequests = filtered.ignored_missing_hardware_requests;
      droppedFunctions = filtered.dropped_functions;
      bomResult = hardwareBomTool({
        intent: guardedIntent,
        selectedHardwareIds,
        hardwareResolver,
      });
      if (bomResult.status === 'ok') {
        bomResult.warnings.push(buildIgnoredMissingHardwareWarning(ignoredMissingHardwareRequests, droppedFunctions));
      }
    }
  }
  if (bomResult.status !== 'ok') {
    return {
      status: 'needs_input',
      response: attachIntentAnalysis(buildNeedsInputFromTool({
        title: '硬件库缺少必要硬件',
        message: bomResult.message,
        partial_intent: guardedIntent,
        partial_bom: bomResult.bom,
        missing_hardware_requests: bomResult.missing_hardware_requests,
        questions: bomResult.questions,
        resolution_options: buildMissingHardwareResolutionOptions(bomResult.missing_hardware_requests),
        blocking_reason: bomResult.blocking_reason,
      }), intentAnalysis, { conversationRoute, revisionIntent }),
    };
  }

  const functionVerification = await verifyBomFunctionsWithRetries({
    intent: guardedIntent,
    bomResult,
    verifier: context.functionVerifier,
    hardwareLibrarySummary: context.hardwareLibrarySummary || getHardwareLibrarySummary(),
  });
  if (functionVerification.status !== 'ok') {
    const missingHardware = buildFunctionVerificationMissingHardware(functionVerification.report);
    return {
      status: 'needs_input',
      response: attachIntentAnalysis(buildNeedsInputFromTool({
        title: 'BOM 功能验证未通过',
        message: buildFunctionVerificationMessage(functionVerification.report),
        partial_intent: guardedIntent,
        partial_bom: bomResult.bom,
        missing_hardware_requests: missingHardware,
        questions: buildFunctionVerificationQuestions(functionVerification.report),
        resolution_options: functionVerification.report?.verification_status === 'blocked'
          ? buildFunctionVerifierUnavailableResolutionOptions()
          : buildMissingHardwareResolutionOptions(missingHardware),
        blocking_reason: functionVerification.report?.verification_status === 'blocked'
          ? 'function_verifier_unavailable'
          : 'function_verification_failed',
        function_verification_report: functionVerification.report,
      }), intentAnalysis, { conversationRoute, revisionIntent }),
    };
  }

  const profileResult = hardwareProfileTool(bomResult.bom, { hardwareResolver });
  if (profileResult.status !== 'ok') {
    return {
      status: 'needs_input',
      response: attachIntentAnalysis(buildNeedsInputFromTool({
        title: '硬件 Profile 不完整',
        message: profileResult.message,
        partial_intent: guardedIntent,
        partial_bom: bomResult.bom,
        questions: profileResult.questions,
        resolution_options: buildProfileIncompleteResolutionOptions(profileResult),
        profile_validation_report: profileResult.profile_validation_report,
        profile_template: profileResult.profile_template,
        required_profile_fields: profileResult.required_profile_fields,
        blocking_reason: 'profile_incomplete',
      }), intentAnalysis, { conversationRoute, revisionIntent }),
    };
  }

  let oriented = orientationTool({
    mountingIntents: guardedIntent.mounting_intents,
    hardwareProfiles: profileResult.hardware_profiles,
  });
  oriented = applyHardwareFaceOverrides(oriented, hardwareFaceOverrides);
  oriented = applyHardwareRotationOverrides(oriented, hardwareRotationOverrides);
  const parameters = {
    ...DEFAULT_PARAMETERS,
    ...normalizeNumberMap(currentDesignState?.parameters),
    ...parameterOverrides,
  };
  let enclosure = boxSizingTool({
    orientedHardwareSpecs: oriented.oriented_hardware_specs,
    parameters,
    userConstraints: guardedIntent.user_constraints,
  });
  let capacity = faceCapacityChecker({
    enclosure,
    orientedHardwareSpecs: oriented.oriented_hardware_specs,
  });
  const autoRepairWarnings = [];
  if (capacity.status === 'fail') {
    const repair = repairFaceCapacityByExpandingBox({
      enclosure,
      capacity,
      orientedHardwareSpecs: oriented.oriented_hardware_specs,
      parameters,
      userConstraints: guardedIntent.user_constraints,
    });
    if (repair.status === 'ok') {
      enclosure = repair.enclosure;
      capacity = repair.capacity;
      Object.assign(parameters, repair.parameters);
      autoRepairWarnings.push(repair.warning);
    } else {
      return {
        status: 'needs_input',
        response: attachIntentAnalysis(buildNeedsInputFromTool({
          title: '当前盒体面放不下这些硬件',
          message: capacity.message,
          partial_intent: guardedIntent,
          partial_bom: bomResult.bom,
          questions: capacity.questions,
          resolution_options: buildFaceCapacityResolutionOptions({
            capacity,
            enclosure,
            orientedHardwareSpecs: oriented.oriented_hardware_specs,
            parameters,
            userConstraints: guardedIntent.user_constraints,
          }),
          blocking_reason: 'face_capacity_fail',
        }), intentAnalysis, { conversationRoute, revisionIntent }),
      };
    }
  }

  let layoutPlan = layoutSolverTool({
    enclosure,
    orientedHardwareSpecs: oriented.oriented_hardware_specs,
    parameters,
  });
  let cad = enclosureGenerator({
    enclosure,
    layoutPlan,
    bom: bomResult.bom,
    hardwareProfiles: profileResult.hardware_profiles,
    parameters,
  });
  let validation = validateDesign({
    enclosure,
    layoutPlan,
    orientedHardwareSpecs: oriented.oriented_hardware_specs,
    parameters,
    environment: context.environment,
    cadqueryCode: options.stage === 'confirmation' ? '' : cad.cadquery_code,
  });
  const validationRepair = repairValidationFailure({
    validation,
    enclosure,
    orientedHardwareSpecs: oriented.oriented_hardware_specs,
    parameters,
    userConstraints: guardedIntent.user_constraints,
    bom: bomResult.bom,
    hardwareProfiles: profileResult.hardware_profiles,
    environment: context.environment,
  });
  if (validationRepair.status === 'ok') {
    enclosure = validationRepair.enclosure;
    Object.assign(parameters, validationRepair.parameters);
    layoutPlan = validationRepair.layoutPlan;
    cad = validationRepair.cad;
    validation = validationRepair.validation;
    autoRepairWarnings.push(validationRepair.warning);
  }
  const blockingValidation = findBlockingValidationFailure(validation.checks);
  if (blockingValidation) {
    return {
      status: 'needs_input',
      response: attachIntentAnalysis(buildNeedsInputFromTool({
        title: '方案预审未通过',
        message: `${blockingValidation.label || blockingValidation.id}：${blockingValidation.message}`,
        partial_intent: guardedIntent,
        partial_bom: bomResult.bom,
        questions: buildValidationFailureQuestions(blockingValidation),
        resolution_options: buildValidationFailureResolutionOptions({
          check: blockingValidation,
          enclosure,
          parameters,
        }),
        checks: validation.checks,
        blocking_reason: `validation_${blockingValidation.id}_fail`,
      }), intentAnalysis, { conversationRoute, revisionIntent }),
    };
  }

  return {
    status: 'prepared',
    prompt,
    guardedIntent,
    intentAnalysis,
    conversationRoute,
    revisionIntent,
    resolutionOptionRoute,
    ignoredMissingHardwareRequests,
    droppedFunctions,
    bomResult,
    functionVerificationReport: functionVerification.report,
    profileResult,
    oriented,
    hardwareFaceOverrides,
    hardwareRotationOverrides,
    parameters,
    enclosure,
    layoutPlan,
    cad,
    validation,
    autoRepairWarnings,
    taskId,
    taskStartedAt,
  };
}

export async function buildArtifactFromPrepared(prepared, context = {}) {
  const {
    prompt,
    guardedIntent,
    intentAnalysis,
    conversationRoute,
    revisionIntent,
    resolutionOptionRoute,
    ignoredMissingHardwareRequests = [],
    droppedFunctions = [],
    bomResult,
    functionVerificationReport,
    profileResult,
    oriented,
    hardwareFaceOverrides,
    hardwareRotationOverrides,
    parameters,
    enclosure,
    layoutPlan,
    cad,
    validation,
    autoRepairWarnings,
    taskId,
    taskStartedAt,
  } = prepared;
  const designHash = createDesignId({ prompt, guardedIntent, parameters });
  const taskStartedDate = taskStartedAt ? new Date(taskStartedAt) : null;
  const resultStartedAt = taskId && taskStartedDate && Number.isFinite(taskStartedDate.getTime())
    ? taskStartedDate
    : context.resultStartedAt instanceof Date
      ? context.resultStartedAt
      : taskStartedDate && Number.isFinite(taskStartedDate.getTime())
      ? taskStartedDate
      : new Date();
  const resultAllocation = await allocateResultDirectory({
    rootDir: context.rootDir,
    startedAt: resultStartedAt,
    taskId,
  });
  const reuseCleanupReport = resultAllocation.reused
    ? await clearManagedResultArtifacts({ rootDir: context.rootDir, resultId: resultAllocation.resultId })
    : null;
  const designId = resultAllocation.resultId;
  const exportResult = await exportPreviewTool({
    rootDir: context.rootDir,
    designId,
    enclosure,
    layoutPlan,
    environment: context.environment,
  });
  const designState = buildPreparedDesignState({
    designId,
    guardedIntent,
    bomResult,
    functionVerificationReport,
    profileResult,
    oriented,
    layoutPlan,
    enclosure,
    cad,
    validation,
    parameters,
    hardwareFaceOverrides,
    hardwareRotationOverrides,
    conversationRoute,
    revisionIntent,
    resolutionOptionRoute,
    ignoredMissingHardwareRequests,
    droppedFunctions,
    warnings: [
      ...bomResult.warnings,
      ...profileResult.warnings,
      ...(resultAllocation.warning ? [resultAllocation.warning] : []),
      ...(reuseCleanupReport?.status === 'warn'
        ? [{
            id: 'task_result_cleanup_warn',
            status: 'warn',
            message: '当前任务目录旧产物清理不完整；本轮会继续写入最新版产物。',
            details: reuseCleanupReport,
          }]
        : []),
      ...autoRepairWarnings,
      ...validation.warnings,
      ...exportResult.warnings,
    ],
    designHash,
    resultStartedAt: resultAllocation.started_at,
  });

  const artifact = {
    status: 'artifact',
    title: `${guardedIntent.product_name} 外壳方案`,
    message: '已按硬件库数据生成确定性意图路线方案：BOM、盒体尺寸、布局、开孔、CadQuery 代码文本和校验报告都来自后端程序。',
    bom: bomResult.bom,
    function_verification_report: functionVerificationReport,
    design_state: designState,
    parameters: buildParameterGroups(parameters, enclosure, layoutPlan),
    intent_analysis: intentAnalysis,
    cadquery_code: cad.cadquery_code,
    preview_assets: buildPreviewAssets({ enclosure, layoutPlan, parameters }),
    exports: exportResult.exports,
    checks: validation.checks,
    warnings: designState.warnings,
    conversation_route: conversationRoute,
    revision_intent: revisionIntent,
    resolution_option_route: resolutionOptionRoute || null,
    ignored_missing_hardware_requests: ignoredMissingHardwareRequests,
    dropped_functions: droppedFunctions,
    source: 'deterministic',
  };
  artifact.generation_trace = buildGenerationTrace({
    stage: 'artifact',
    intentAnalysis,
    bom: bomResult.bom,
    designState,
    layoutPlan,
    validation,
    exports: artifact.exports,
    profileValidationReport: profileResult.profile_validation_report,
  });
  artifact.design_state.generation_trace = artifact.generation_trace;
  let metadataExports = [];
  try {
    metadataExports = await writeArtifactMetadataFiles({
      rootDir: context.rootDir,
      designId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'artifact_metadata_write_failed',
      message: 'Artifact 元数据导出文件写入失败；主体方案已生成，但 cadquery.py、design-state.json、checks.json 或 artifact.json 暂不可下载。',
      error,
    }));
    metadataExports = buildFailedMetadataExports(error);
  }
  artifact.exports = [...artifact.exports, ...metadataExports];
  artifact.design_state.exports = artifact.exports;
  artifact.generation_trace = buildGenerationTrace({
    stage: 'artifact',
    intentAnalysis,
    bom: bomResult.bom,
    designState: artifact.design_state,
    layoutPlan,
    validation,
    exports: artifact.exports,
    profileValidationReport: profileResult.profile_validation_report,
  });
  artifact.design_state.generation_trace = artifact.generation_trace;
  const cleanupReport = await cleanupResultDirectories({
    rootDir: context.rootDir,
    keepCount: 3,
  });
  if (cleanupReport.status !== 'ok') {
    designState.warnings.push({
      id: 'result_history_cleanup_failed',
      status: 'warn',
      message: '历史结果清理失败；本轮结果已生成，但旧结果可能未完全删除。',
      details: cleanupReport,
    });
    artifact.warnings = designState.warnings;
  }
  let workflowExports = [];
  try {
    workflowExports = await writeWorkflowArtifactFiles({
      rootDir: context.rootDir,
      designId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'workflow_artifacts_write_failed',
      message: '8 个工作流调试产物写入失败；主体方案和旧导出文件仍可继续使用。',
      error,
    }));
    workflowExports = buildFailedWorkflowArtifactExports(error);
  }
  artifact.exports = [...artifact.exports, ...workflowExports];
  artifact.design_state.exports = artifact.exports;
  artifact.warnings = designState.warnings;
  artifact.generation_trace = buildGenerationTrace({
    stage: 'artifact',
    intentAnalysis,
    bom: bomResult.bom,
    designState: artifact.design_state,
    layoutPlan,
    validation,
    exports: artifact.exports,
    profileValidationReport: profileResult.profile_validation_report,
  });
  artifact.design_state.generation_trace = artifact.generation_trace;
  try {
    await writeArtifactSnapshotFile({
      rootDir: context.rootDir,
      designId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'artifact_snapshot_write_failed',
      message: '最终 metadata 快照重写失败；主体方案已返回，但 artifact.json、design-state.json 或 checks.json 可能缺少最新导出项。',
      error,
    }));
    artifact.warnings = designState.warnings;
    artifact.generation_trace = buildGenerationTrace({
      stage: 'artifact',
      intentAnalysis,
      bom: bomResult.bom,
      designState: artifact.design_state,
      layoutPlan,
      validation,
      exports: artifact.exports,
      profileValidationReport: profileResult.profile_validation_report,
    });
    artifact.design_state.generation_trace = artifact.generation_trace;
  }
  return artifact;
}

export function buildDesignDraft(prepared) {
  const designId = createDesignId({
    prompt: prepared.prompt,
    guardedIntent: prepared.guardedIntent,
    parameters: prepared.parameters,
    stage: 'draft',
  });
  const designState = buildPreparedDesignState({
    designId,
    guardedIntent: prepared.guardedIntent,
    bomResult: prepared.bomResult,
    functionVerificationReport: prepared.functionVerificationReport,
    profileResult: prepared.profileResult,
    oriented: prepared.oriented,
    layoutPlan: prepared.layoutPlan,
    enclosure: prepared.enclosure,
    cad: prepared.cad,
    validation: prepared.validation,
    parameters: prepared.parameters,
    hardwareFaceOverrides: prepared.hardwareFaceOverrides,
    hardwareRotationOverrides: prepared.hardwareRotationOverrides,
    resolutionOptionRoute: prepared.resolutionOptionRoute || null,
    ignoredMissingHardwareRequests: prepared.ignoredMissingHardwareRequests || [],
    droppedFunctions: prepared.droppedFunctions || [],
    warnings: [
      ...prepared.bomResult.warnings,
      ...prepared.profileResult.warnings,
      ...prepared.autoRepairWarnings,
      ...prepared.validation.warnings,
    ],
    designHash: designId,
  });
  designState.intent_analysis = prepared.intentAnalysis;
  designState.conversation_route = prepared.conversationRoute;
  designState.revision_intent = prepared.revisionIntent;
  designState.resolution_option_route = prepared.resolutionOptionRoute || null;
  return {
    status: 'confirmation',
    title: `${prepared.guardedIntent.product_name} 参数确认`,
    message: '已完成意图分析、硬件 BOM、盒体尺寸和硬件摆放预审。确认后才会开始实际建模。',
    bom: prepared.bomResult.bom,
    function_verification_report: prepared.functionVerificationReport,
    partial_bom: prepared.bomResult.bom,
    design_state: designState,
    parameters: buildParameterGroups(prepared.parameters, prepared.enclosure, prepared.layoutPlan),
    intent_analysis: prepared.intentAnalysis,
    conversation_route: prepared.conversationRoute,
    revision_intent: prepared.revisionIntent,
    resolution_option_route: prepared.resolutionOptionRoute || null,
    ignored_missing_hardware_requests: prepared.ignoredMissingHardwareRequests || [],
    dropped_functions: prepared.droppedFunctions || [],
    preview_assets: buildPreviewAssets({ enclosure: prepared.enclosure, layoutPlan: prepared.layoutPlan, parameters: prepared.parameters }),
    checks: prepared.validation.checks,
    warnings: designState.warnings,
    source: 'deterministic',
  };
}

export function buildPreparedDesignState({
  designId,
  designHash,
  resultStartedAt = '',
  guardedIntent,
  bomResult,
  functionVerificationReport = null,
  profileResult,
  oriented,
  layoutPlan,
  enclosure,
  cad,
  validation,
  parameters,
  hardwareFaceOverrides,
  hardwareRotationOverrides,
  conversationRoute = null,
  revisionIntent = null,
  resolutionOptionRoute = null,
  ignoredMissingHardwareRequests = [],
  droppedFunctions = [],
  warnings,
}) {
  return {
    id: designId,
    design_hash: designHash || designId,
    result_started_at: resultStartedAt,
    intent: guardedIntent,
    bom: bomResult.bom,
    function_verification_report: functionVerificationReport,
    hardware_profiles: profileResult.hardware_profiles,
    profile_validation_report: profileResult.profile_validation_report,
    mounting_plan: oriented.mounting_plan,
    layout_plan: layoutPlan,
    enclosure_parameters: enclosure,
    cad_parameters: cad.cad_parameters,
    validation_context: validation.validation_context,
    parameters,
    hardware_face_overrides: hardwareFaceOverrides,
    hardware_rotation_overrides: hardwareRotationOverrides,
    conversation_route: conversationRoute,
    revision_intent: revisionIntent,
    resolution_option_route: resolutionOptionRoute,
    ignored_missing_hardware_requests: ignoredMissingHardwareRequests,
    dropped_functions: droppedFunctions,
    warnings,
  };
}

export function buildIntentAnalysis({ body = {}, intentResult = {} } = {}) {
  const provided = isPlainObject(body.intentAnalysis)
    ? body.intentAnalysis
    : isPlainObject(body.intent_analysis)
      ? body.intent_analysis
      : {};
  const source = normalizeString(provided.source)
    || (body.intent && isPlainObject(body.intent) ? 'external_intent' : 'local_deterministic');
  return {
    source,
    status: normalizeString(provided.status) || intentResult.status || '',
    model_status: normalizeString(provided.model_status),
    reason: normalizeString(provided.reason),
    confidence: provided.confidence !== null && provided.confidence !== undefined && Number.isFinite(Number(provided.confidence))
      ? Number(provided.confidence)
      : Number.isFinite(Number(intentResult.confidence))
        ? Number(intentResult.confidence)
        : null,
    questions: Array.isArray(intentResult.questions)
      ? intentResult.questions
      : Array.isArray(provided.questions)
        ? normalizeStringArray(provided.questions)
        : [],
    conversation_route: conversationRouteFromBody(body),
    revision_intent: revisionIntentFromBody(body),
  };
}

export function attachIntentAnalysis(result, intentAnalysis, metadata = {}) {
  if (!isPlainObject(result)) return result;
  const conversationRoute = metadata.conversationRoute || intentAnalysis.conversation_route || null;
  const revisionIntent = metadata.revisionIntent || intentAnalysis.revision_intent || null;
  const merged = {
    ...result,
    intent_analysis: intentAnalysis,
    conversation_route: conversationRoute,
    revision_intent: revisionIntent,
  };
  if (merged.status === 'needs_input' && !merged.generation_trace) {
    merged.generation_trace = buildNeedsInputGenerationTrace(merged, intentAnalysis);
  }
  return merged;
}

function conversationRouteFromBody(body = {}) {
  return isPlainObject(body.conversationRoute)
    ? body.conversationRoute
    : isPlainObject(body.conversation_route)
      ? body.conversation_route
      : null;
}

function revisionIntentFromBody(body = {}) {
  return isPlainObject(body.revisionIntent)
    ? body.revisionIntent
    : isPlainObject(body.revision_intent)
      ? body.revision_intent
      : null;
}

function resolutionOptionRouteFromBody(body = {}) {
  return isPlainObject(body.resolutionOptionRoute)
    ? body.resolutionOptionRoute
    : isPlainObject(body.resolution_option_route)
      ? body.resolution_option_route
      : null;
}

function buildFunctionVerifierUnavailableResolutionOptions() {
  return [
    {
      id: 'configure_function_verifier_llm',
      label: '配置 LLM 后重试',
      action: 'configure_llm',
      description: '配置 ZW_CAD_INTENT_API_KEY / ZW_CAD_API_KEY 并重启后端，再重新确认分析。',
      recommended: true,
    },
    {
      id: 'keep_blocking_function_verify',
      label: '保持阻断',
      action: 'keep_blocked',
      description: '当前策略要求 function_verify 不可用时停止在 BOM 功能验证阶段，避免跳过功能覆盖检查。',
      recommended: false,
    },
  ];
}

function shouldIgnoreMissingHardware(body = {}) {
  if (body.ignoreMissingHardware === true || body.ignore_missing_hardware === true) return true;
  const route = body.resolutionOptionRoute || body.resolution_option_route || {};
  if (route.action === 'ignore_missing_hardware_continue' || route.option_id === 'ignore_missing_hardware_continue') return true;
  const text = normalizeStringArray(body.userAnswers).join(' ');
  return /ignore_missing_hardware_continue|remove_or_replace_feature/.test(text);
}

function dropMissingHardwareFromIntent(intent = {}, missingRequests = []) {
  const missingRoles = new Set(missingRequests.map((item) => normalizeString(item.role)).filter(Boolean));
  const missingFunctions = new Set(missingRequests.map((item) => normalizeString(item.function)).filter(Boolean));
  const requiredRoles = Array.isArray(intent.required_hardware_roles)
    ? intent.required_hardware_roles.filter((role) => !missingRoles.has(normalizeString(role.role)))
    : [];
  const functions = normalizeStringArray(intent.functions).filter((fn) => !missingFunctions.has(fn));
  const mountingIntents = Array.isArray(intent.mounting_intents)
    ? intent.mounting_intents.filter((item) => {
        const hardwareId = normalizeString(item.hardware_id);
        return hardwareId && !missingRoles.has(hardwareId);
      })
    : [];
  return {
    intent: guardIntent({
      ...intent,
      functions,
      required_hardware_roles: requiredRoles,
      mounting_intents: mountingIntents,
      user_constraints: {
        ...(intent.user_constraints || {}),
        ignored_missing_hardware_roles: [...missingRoles],
      },
    }),
    ignored_missing_hardware_requests: missingRequests,
    dropped_functions: [...missingFunctions],
  };
}

function normalizeIgnoredMissingHardwareRequests(value = []) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isPlainObject)
    .map((item) => ({
      role: normalizeString(item.role),
      category: normalizeString(item.category),
      function: normalizeString(item.function),
      label: normalizeString(item.label),
      why_needed: normalizeString(item.why_needed || item.reason),
    }))
    .filter((item) => item.role || item.label || item.function);
}

function buildIgnoredMissingHardwareWarning(requests = [], droppedFunctions = []) {
  const labels = requests.map((item) => item.label || item.role || item.function).filter(Boolean).join('、') || '缺失硬件';
  return {
    id: 'ignored_missing_hardware_continue',
    status: 'warn',
    message: `已按用户选择忽略库内缺失硬件继续：${labels}。这些功能不会进入本轮 BOM、布局和模型。`,
    ignored_missing_hardware_requests: requests,
    dropped_functions: droppedFunctions,
  };
}

async function verifyBomFunctionsWithRetries({
  intent,
  bomResult,
  verifier,
  hardwareLibrarySummary,
  maxAttempts = 3,
}) {
  if (typeof verifier !== 'function') {
    return {
      status: 'needs_input',
      bomResult,
      report: buildFunctionVerifyUnavailableResult('function_verifier_not_configured'),
    };
  }
  let report = null;
  for (let attempt = 1; attempt <= maxAttempts; attempt += 1) {
    report = await verifier({
      intent,
      bom: bomResult.bom,
      hardwareLibrarySummary,
      attempt,
      maxAttempts,
    });
    report = normalizeFunctionVerificationReport(report, attempt, maxAttempts);
    if (report.status === 'ok') {
      return {
        status: 'ok',
        bomResult,
        report,
      };
    }
  }
  return {
    status: 'needs_input',
    bomResult,
    report,
  };
}

function normalizeFunctionVerificationReport(report = {}, attempt = 1, maxAttempts = 3) {
  const normalized = isPlainObject(report) ? report : {};
  const status = normalized.status === 'ok' ? 'ok' : 'needs_input';
  return {
    status,
    verification_status: status === 'ok'
      ? 'pass'
      : normalized.verification_status || 'fail',
    attempts_used: Number(normalized.attempts_used || attempt),
    max_attempts: Number(normalized.max_attempts || maxAttempts),
    reason: normalizeString(normalized.reason || normalized.message),
    message: normalizeString(normalized.message),
    missing_functions: normalizeStringArray(normalized.missing_functions),
    missing_hardware: Array.isArray(normalized.missing_hardware) ? normalized.missing_hardware : [],
    uncovered_requirements: normalizeStringArray(normalized.uncovered_requirements),
    library_violations: normalizeStringArray(normalized.library_violations),
    covered_functions: normalizeStringArray(normalized.covered_functions),
    notes: normalizeStringArray(normalized.notes),
    confidence: normalized.confidence ?? null,
    source: normalized.source || 'function_verifier',
  };
}

function buildFunctionVerificationMessage(report = {}) {
  if (report.verification_status === 'blocked') {
    return report.message || 'BOM 功能验证需要 LLM 可用；当前 LLM 未配置或不可用，无法继续进入下一步。';
  }
  const missingFunctions = normalizeStringArray(report.missing_functions);
  const uncovered = normalizeStringArray(report.uncovered_requirements);
  const missingHardware = buildFunctionVerificationMissingHardware(report);
  const parts = [];
  if (missingFunctions.length) parts.push(`无法覆盖的功能：${missingFunctions.join('、')}`);
  if (uncovered.length) parts.push(`未满足的需求：${uncovered.join('、')}`);
  if (missingHardware.length) parts.push(`库中缺失的硬件：${missingHardware.map((item) => item.label || item.role || item.function).filter(Boolean).join('、')}`);
  if (!parts.length && report.reason) parts.push(report.reason);
  return parts.length
    ? `${parts.join('；')}。`
    : '当前 BOM 未通过功能覆盖验证，请补充硬件 profile 或调整/删除无法实现的功能。';
}

function buildFunctionVerificationQuestions(report = {}) {
  if (report.verification_status === 'blocked') {
    return ['请配置可用的 LLM 后重试；当前策略不会跳过 function_verify。'];
  }
  return [
    '是否按硬件库 profile 格式补充缺失硬件？',
    '是否砍掉或替换当前硬件库无法覆盖的功能？',
    '也可以直接在对话框说明新的功能取舍或替代方案。',
  ];
}

function buildFunctionVerificationMissingHardware(report = {}) {
  const items = Array.isArray(report.missing_hardware) ? report.missing_hardware : [];
  return items.map((item) => {
    if (typeof item === 'string') {
      return {
        role: item,
        label: item,
        function: item,
        reason: 'BOM 功能验证认为当前硬件库缺少对应硬件。',
      };
    }
    return {
      role: normalizeString(item.role || item.function || item.label || item.hardware_id),
      label: normalizeString(item.label || item.name || item.function || item.role || item.hardware_id),
      function: normalizeString(item.function || item.role || item.label),
      hardware_id: normalizeString(item.hardware_id || item.id),
      reason: normalizeString(item.reason || item.why_needed || 'BOM 功能验证认为当前硬件库缺少对应硬件。'),
    };
  }).filter((item) => item.label || item.role || item.hardware_id);
}

export async function regenerateDesign(body = {}, context = {}) {
  const currentDesignState = isPlainObject(body.currentDesignState)
    ? body.currentDesignState
    : isPlainObject(body.design_state)
      ? body.design_state
      : isPlainObject(body.designState)
        ? body.designState
        : null;
  if (!currentDesignState?.intent) {
    return withNeedsInputGenerationTrace({
      status: 'needs_input',
      message: '缺少可再生成的 DesignState，请先生成一次模型。',
      questions: ['请重新输入产品需求，或恢复上一版 design_state。'],
      blocking_reason: 'missing_design_state',
    }, {
      source: 'regenerate',
      status: 'needs_input',
      model_status: 'skipped',
      reason: 'missing_design_state',
      confidence: null,
    });
  }
  return generateDesign({
    prompt: currentDesignState.intent.product_name,
    selectedHardwareIds: currentDesignState.bom?.map((item) => item.hardware_id) || [],
    currentDesignState,
    taskId: body.taskId || body.task_id || currentDesignState.id,
    parameterOverrides: body.parameterOverrides,
    hardwareFaceOverrides: body.hardwareFaceOverrides,
    hardwareRotationOverrides: body.hardwareRotationOverrides,
    customHardwareProfiles: body.customHardwareProfiles || extractCustomProfilesFromDesignState(currentDesignState),
  }, context);
}

export function createDesignId(value) {
  return crypto
    .createHash('sha1')
    .update(JSON.stringify(value))
    .digest('hex')
    .slice(0, 12);
}

export function extractCustomProfilesFromDesignState(designState) {
  const profiles = Array.isArray(designState?.hardware_profiles) ? designState.hardware_profiles : [];
  const builtinResolver = createHardwareResolver();
  return profiles.filter((profile) => profile?.id && !builtinResolver.getHardwareProfile(profile.id));
}
