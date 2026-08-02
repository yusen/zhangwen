import crypto from 'node:crypto';
import { createHardwareResolver, getHardwareLibrarySummary } from '../hardware-library.js';
import {
  buildDeterministicProductResponse,
  detectDeterministicProduct,
  MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID,
  UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID,
  UNIHIKER_HANDHELD_FAN_TEMPLATE_ID,
  UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID,
} from '../deterministic-products.js';
import {
  allocateResultDirectory,
  cleanupResultDirectories,
  clearManagedResultArtifacts,
  normalizeTaskId,
  releaseResultDirectoryLease,
} from '../result-store.js';
import {
  writeArtifactMetadataFiles,
  writeArtifactSnapshotFile,
  writeProjectDefaultParametersFile,
  writeProjectModelSourceFile,
} from '../stl-exporter.js';
import { buildFailedWorkflowArtifactExports, writeWorkflowArtifactFiles } from '../workflow-artifacts.js';
import { buildUnihikerSmartWateringTemplate, UNIHIKER_SMART_WATERING_TEMPLATE_ID } from '../template-library/unihiker-smart-watering-system.js';
import { buildUnihikerPhotoAlbumTemplate, UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID } from '../template-library/unihiker-photo-album.js';
import { buildXiaoSmartPendantTemplate, XIAO_SMART_PENDANT_TEMPLATE_ID } from '../template-library/xiao-smart-pendant.js';
import { buildBatchModelTemplate } from '../template-library/batch-model-cases.js';
import { buildFunctionVerifyUnavailableResult } from '../function-verifier.js';
import { buildExportWriteWarning, buildFailedMetadataExports, buildFailedPreviewExports, buildParameterGroups, buildPreviewAssets, enclosureGenerator, exportPreviewTool } from './cad.js';
import { applyHardwareFaceOverrides, applyHardwareRotationOverrides, hardwareBomTool, hardwareProfileTool, orientationTool } from './hardware.js';
import { guardIntent, intentAnalyzer, normalizeExternalIntent } from './intent.js';
import { boxSizingTool, faceCapacityChecker, layoutSolverTool, repairFaceCapacityByExpandingBox } from './layout.js';
import { buildFaceCapacityResolutionOptions, buildMissingHardwareResolutionOptions, buildNeedsInputFromTool, buildProfileIncompleteResolutionOptions, buildValidationFailureQuestions, buildValidationFailureResolutionOptions, repairValidationFailure } from './recovery.js';
import { DEFAULT_PARAMETERS, isPlainObject, normalizeHardwareFaceOverrides, normalizeHardwareRotationOverrides, normalizeNumberMap, normalizeString, normalizeStringArray } from './shared.js';
import { buildSurfaceEngravingPatch, injectSurfaceEngravingCode, normalizeSurfaceEngravings } from '../surface-engraving.js';
import { buildGenerationTrace, buildNeedsInputGenerationTrace, findBlockingValidationFailure, withNeedsInputGenerationTrace } from './trace.js';
import { validateDesign } from './validation.js';
import { readProjectWorkspace, withProjectMutationLock } from '../project-store.js';
import { buildStandaloneStructuralPartsResponse } from '../structural-parts.js';

const DETERMINISTIC_TEMPLATE_BUILDERS = new Map([
  [UNIHIKER_SMART_WATERING_TEMPLATE_ID, buildUnihikerSmartWateringTemplate],
  [UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID, buildUnihikerPhotoAlbumTemplate],
  [XIAO_SMART_PENDANT_TEMPLATE_ID, buildXiaoSmartPendantTemplate],
  [UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID, buildBatchModelTemplate],
  [UNIHIKER_HANDHELD_FAN_TEMPLATE_ID, buildBatchModelTemplate],
  [MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID, buildBatchModelTemplate],
  [UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID, buildBatchModelTemplate],
]);

const DETERMINISTIC_TEMPLATE_PROMPTS = new Map([
  [UNIHIKER_SMART_WATERING_TEMPLATE_ID, '行空板智能浇花系统'],
  [UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID, '行空板电子相册产品'],
  [XIAO_SMART_PENDANT_TEMPLATE_ID, 'XIAO智能项链'],
  [UNIHIKER_LIGHT_EFFECT_CUP_TEMPLATE_ID, '行空板光效水杯'],
  [UNIHIKER_HANDHELD_FAN_TEMPLATE_ID, '行空板手持小风扇'],
  [MPYTHON_BOARD_ENCLOSURE_TEMPLATE_ID, '掌控板外壳'],
  [UNIHIKER_AUTO_OPEN_LID_BOX_TEMPLATE_ID, '行空板自动感应开盖智能盒子'],
]);

export async function generateDesign(body = {}, context = {}) {
  const projectId = normalizeTaskId(body.taskId || body.task_id || body.currentDesignState?.id || body.design_state?.id);
  if (projectId) {
    return withProjectMutationLock(
      { rootDir: context.rootDir, projectId },
      () => generateDesignUnlocked(body, context),
    );
  }
  return generateDesignUnlocked(body, context);
}

async function generateDesignUnlocked(body = {}, context = {}) {
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
  const projectId = normalizeTaskId(body.taskId || body.task_id || draftState.id);
  const templateConfirmationState = await readTemplateConfirmationState({
    rootDir: context.rootDir,
    projectId,
  });
  const templateConfirmation = templateConfirmationState.marker;
  if ((draftState.template_confirmation_required === true || templateConfirmationState.required) && !templateConfirmation) {
    return withNeedsInputGenerationTrace({
      status: 'needs_input',
      title: '模板确认标记缺失',
      message: '服务器未找到当前确认草案对应的有效模板标记，不能根据客户端字段继续建模。请重新提交智能浇花系统需求。',
      questions: ['请重新提交智能浇花系统需求，生成新的 2D 确认草案。'],
      blocking_reason: 'template_confirmation_missing',
    }, {
      source: 'build',
      status: 'needs_input',
      model_status: 'skipped',
      reason: 'template_confirmation_missing',
      confidence: null,
    });
  }
  const templateId = normalizeString(
    templateConfirmation?.template_id
      || draftState.template_id
      || draftState.intent?.template_id
      || draftState.deterministic_product?.template_id,
  );
  if (templateConfirmation?.template_id && !DETERMINISTIC_TEMPLATE_BUILDERS.has(templateConfirmation.template_id)) {
    return withNeedsInputGenerationTrace({
      status: 'needs_input',
      title: '模板确认标记无效',
      message: '当前确认草案对应的模板标记无法识别，出于安全原因不会按客户端字段继续建模。请重新提交需求。',
      questions: ['请新建或重新提交智能浇花系统需求。'],
      blocking_reason: 'template_confirmation_invalid',
    }, {
      source: 'build',
      status: 'needs_input',
      model_status: 'skipped',
      reason: 'template_confirmation_invalid',
      confidence: null,
    });
  }
  const canonicalPrompt = DETERMINISTIC_TEMPLATE_PROMPTS.get(templateId) || '';
  const isDeterministicTemplate = Boolean(canonicalPrompt);
  return generateDesign({
    // Rebuild this template from its server-owned product definition even if a
    // client edits the draft prompt, BOM, or layout metadata before confirming.
    prompt: canonicalPrompt || body.prompt || draftState.intent.product_name,
    // A recognized deterministic confirmation is rebuilt from the server
    // template. Never let client-selected ids steer product detection.
    selectedHardwareIds: isDeterministicTemplate
      ? []
      : draftState.bom?.map((item) => item.hardware_id) || [],
    currentDesignState: draftState,
    taskId: projectId,
    parameterOverrides: body.parameterOverrides,
    hardwareFaceOverrides: body.hardwareFaceOverrides,
    hardwareRotationOverrides: body.hardwareRotationOverrides,
    customHardwareProfiles: body.customHardwareProfiles || extractCustomProfilesFromDesignState(draftState),
    intent: isDeterministicTemplate ? undefined : draftState.intent,
    intentAnalysis: body.intentAnalysis || draftState.intent_analysis || draftState.intentAnalysis,
    conversationRoute: body.conversationRoute || body.conversation_route || draftState.conversation_route,
    revisionIntent: body.revisionIntent || body.revision_intent || draftState.revision_intent,
    resolutionOptionRoute: body.resolutionOptionRoute || body.resolution_option_route || draftState.resolution_option_route,
    ignoredMissingHardwareRequests: body.ignoredMissingHardwareRequests || body.ignored_missing_hardware_requests || draftState.ignored_missing_hardware_requests,
    droppedFunctions: body.droppedFunctions || body.dropped_functions || draftState.dropped_functions,
    surfaceEngravings: body.surfaceEngravings || body.surface_engravings || draftState.surface_engravings,
    surfaceEngravingPatch: body.surfaceEngravingPatch || body.surface_engraving_patch || draftState.surface_engraving_patch,
  }, context);
}

async function readTemplateConfirmationState({ rootDir, projectId } = {}) {
  if (!rootDir || !projectId) return { marker: null, required: false };
  try {
    const workspace = await readProjectWorkspace({ rootDir, projectId });
    const session = workspace?.session_state;
    const marker = session?.template_confirmation;
    const validMarker = isPlainObject(marker)
      && normalizeString(marker.task_id || marker.project_id) === projectId
      && normalizeString(marker.status) === 'pending'
      ? marker
      : null;
    return {
      marker: validMarker,
      required: session?.template_confirmation_required === true || Boolean(validMarker),
    };
  } catch {
    return { marker: null, required: false };
  }
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

  const standaloneStructuralParts = await buildStandaloneStructuralPartsResponse(body, context, {
    stage: options.stage === 'artifact' ? 'artifact' : 'confirmation',
  });
  if (standaloneStructuralParts) {
    return {
      status: 'standalone_structural_parts',
      response: standaloneStructuralParts,
    };
  }

  const deterministicProductDetection = detectDeterministicProduct(body);
  if (deterministicProductDetection) {
    const deterministicProductResponse = await buildDeterministicProductPipelineResponse({
      detection: deterministicProductDetection,
      body,
      context,
      stage: options.stage === 'artifact' ? 'artifact' : 'confirmation',
    });
    return {
      status: 'deterministic_product',
      response: deterministicProductResponse,
    };
  }

  const selectedHardwareIds = normalizeStringArray(body.selectedHardwareIds);
  const parameterOverrides = normalizeNumberMap(body.parameterOverrides);
  const userAnswers = normalizeStringArray(body.userAnswers);
  const currentDesignState = isPlainObject(body.currentDesignState) ? body.currentDesignState : null;
  const surfaceEngravings = normalizeSurfaceEngravings(
    body.surfaceEngravings
      || body.surface_engravings
      || currentDesignState?.surface_engravings,
  );
  // The structured engraving state is authoritative. Rebuild the only allowed
  // helper call instead of carrying executable patch text across API boundaries.
  const surfaceEngravingPatch = buildSurfaceEngravingPatch(surfaceEngravings);
  const surfaceEngravingPreflight = body.surfaceEngravingPreflight
    || body.surface_engraving_preflight
    || currentDesignState?.surface_engraving_preflight
    || null;
  const projectDefaultParameters = projectDefaultParametersFromDesignState(currentDesignState);
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
    surfaceEngravings,
    surfaceEngravingPatch,
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
    surfaceEngravings,
    surfaceEngravingPatch,
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
    projectDefaultParameters,
    enclosure,
    layoutPlan,
    cad,
    validation,
    autoRepairWarnings,
    taskId,
    taskStartedAt,
    surfaceEngravings,
    surfaceEngravingPatch,
    surfaceEngravingPreflight,
    projectSourceUpdateAuthorized: hasExplicitProjectRegeneration(body),
    surfaceEngravingUpdateAuthorized: hasExplicitSurfaceEngravingUpdate(body),
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
    projectDefaultParameters,
    surfaceEngravings = [],
    surfaceEngravingPatch = '',
    surfaceEngravingPreflight = null,
    projectSourceUpdateAuthorized = false,
    surfaceEngravingUpdateAuthorized = false,
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
  if (resultAllocation.status !== 'ok') {
    return buildResultAllocationFailureResponse(resultAllocation);
  }
  let allocationCleanupCompleted = false;
  try {
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
    projectDefaultParameters,
    surfaceEngravings,
    surfaceEngravingPatch,
    surfaceEngravingPreflight,
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
    surface_engravings: surfaceEngravings,
    surface_engraving_patch: surfaceEngravingPatch,
    surface_engraving_preflight: surfaceEngravingPreflight,
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
  if (projectSourceUpdateAuthorized) {
    Object.defineProperty(artifact, 'project_source_update_authorized', {
      value: true,
      enumerable: false,
    });
  }
  if (surfaceEngravingUpdateAuthorized) {
    Object.defineProperty(artifact, 'surface_engraving_update_authorized', {
      value: true,
      enumerable: false,
    });
  }
  try {
    await attachProjectModelSourceFile({
      rootDir: context.rootDir,
      designId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'project_workspace_write_failed',
      message: '项目源码副本或默认参数写入失败；主体方案已生成，但后续项目修改和恢复默认值可能不可用。',
      error,
    }));
    artifact.warnings = designState.warnings;
  }
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
  releaseResultDirectoryLease({
    rootDir: context.rootDir,
    resultId: designId,
    leaseToken: resultAllocation.lease_token,
  });
  const cleanupReport = await cleanupResultDirectories({
    rootDir: context.rootDir,
    keepCount: 3,
  });
  allocationCleanupCompleted = true;
  if (cleanupReport.status === 'migration_required') {
    designState.warnings.push({
      id: 'project_retention_migration_pending',
      status: 'info',
      message: '已生成旧项目清理清单；未经用户明确确认，不会删除历史项目。',
    });
    artifact.warnings = designState.warnings;
  } else if (cleanupReport.status !== 'ok') {
    designState.warnings.push({
      id: 'result_history_cleanup_failed',
      status: 'warn',
      message: '历史结果清理失败；本轮结果已生成，但旧结果可能未完全删除。',
      details: cleanupReport,
    });
    artifact.warnings = designState.warnings;
  }
  return artifact;
  } finally {
    releaseResultDirectoryLease({
      rootDir: context.rootDir,
      resultId: resultAllocation.resultId,
      leaseToken: resultAllocation.lease_token,
    });
    if (!allocationCleanupCompleted) {
      await cleanupResultDirectories({ rootDir: context.rootDir, keepCount: 3 }).catch(() => undefined);
    }
  }
}

async function buildDeterministicProductPipelineResponse({
  detection,
  body = {},
  context = {},
  stage = 'artifact',
} = {}) {
  const product = detection?.product;
  const templateBuilder = product?.template_id
    ? DETERMINISTIC_TEMPLATE_BUILDERS.get(product.template_id)
    : null;
  if (!templateBuilder) {
    return buildDeterministicProductResponse(detection, body);
  }

  if (stage === 'confirmation' && product?.template_id === UNIHIKER_SMART_WATERING_TEMPLATE_ID) {
    const taskId = normalizeTaskId(body.taskId || body.task_id);
    const draftDesignId = taskId
      || normalizeString(body.currentDesignState?.id || body.current_design_state?.id)
      || 'ZW-PRODUCT-TEMPLATE-DRAFT';
    const draft = templateBuilder({
      product,
      detection,
      body,
      context: {
        ...context,
        stage: 'confirmation',
        designId: draftDesignId,
        resultStartedAt: body.taskStartedAt
          || body.task_started_at
          || context.resultStartedAt
          || new Date().toISOString(),
      },
    });
    return buildDeterministicTemplateConfirmationResponse(draft, { product, detection });
  }

  const taskId = normalizeTaskId(body.taskId || body.task_id || body.currentDesignState?.id);
  const taskStartedAt = normalizeString(body.taskStartedAt || body.task_started_at || body.currentDesignState?.result_started_at);
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
  if (resultAllocation.status !== 'ok') {
    return buildResultAllocationFailureResponse(resultAllocation);
  }
  let allocationCleanupCompleted = false;
  try {
  const reuseCleanupReport = resultAllocation.reused
    ? await clearManagedResultArtifacts({ rootDir: context.rootDir, resultId: resultAllocation.resultId })
    : null;

  const artifact = templateBuilder({
    product,
    detection,
    body,
    context: {
      ...context,
      designId: resultAllocation.resultId,
      resultStartedAt: resultAllocation.started_at,
    },
  });

  if (artifact.status !== 'artifact') {
    return artifact;
  }

  const designState = artifact.design_state;
  const surfaceEngravings = normalizeSurfaceEngravings(
    body.surfaceEngravings
      || body.surface_engravings
      || body.currentDesignState?.surface_engravings,
  );
  const surfaceEngravingPatch = buildSurfaceEngravingPatch(surfaceEngravings);
  const surfaceEngravingPreflight = body.surfaceEngravingPreflight
    || body.surface_engraving_preflight
    || body.currentDesignState?.surface_engraving_preflight
    || null;
  artifact.cadquery_code = injectSurfaceEngravingCode(
    artifact.cadquery_code,
    surfaceEngravings,
    surfaceEngravingPatch,
  );
  artifact.surface_engravings = surfaceEngravings;
  artifact.surface_engraving_patch = surfaceEngravingPatch;
  artifact.surface_engraving_preflight = surfaceEngravingPreflight;
  designState.surface_engravings = surfaceEngravings;
  designState.surface_engraving_patch = surfaceEngravingPatch;
  designState.surface_engraving_preflight = surfaceEngravingPreflight;
  if (resultAllocation.warning) designState.warnings.push(resultAllocation.warning);
  if (reuseCleanupReport?.status === 'warn') {
    designState.warnings.push({
      id: 'task_result_cleanup_warn',
      status: 'warn',
      message: '当前任务目录旧产物清理不完整；本轮会继续写入最新版本产物。',
      details: reuseCleanupReport,
    });
  }

  const exportResult = await exportTemplatePreview({
    rootDir: context.rootDir,
    designId: resultAllocation.resultId,
    artifact,
    environment: context.environment,
  });
  artifact.exports = exportResult.exports;
  designState.exports = artifact.exports;
  designState.warnings.push(...exportResult.warnings);
  artifact.warnings = designState.warnings;
  if (hasExplicitProjectRegeneration(body)) {
    Object.defineProperty(artifact, 'project_source_update_authorized', {
      value: true,
      enumerable: false,
    });
  }
  if (hasExplicitSurfaceEngravingUpdate(body)) {
    Object.defineProperty(artifact, 'surface_engraving_update_authorized', {
      value: true,
      enumerable: false,
    });
  }
  await attachProjectModelSourceFile({
    rootDir: context.rootDir,
    designId: resultAllocation.resultId,
    artifact,
  });
  refreshTemplateTrace(artifact);

  let metadataExports = [];
  try {
    metadataExports = await writeArtifactMetadataFiles({
      rootDir: context.rootDir,
      designId: resultAllocation.resultId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'artifact_metadata_write_failed',
      message: '确定性模板 artifact 元数据写入失败；主体模型已生成，但 cadquery.py、design-state.json、checks.json 或 artifact.json 暂不可下载。',
      error,
    }));
    metadataExports = buildFailedMetadataExports(error);
  }
  artifact.exports = [...artifact.exports, ...metadataExports];
  designState.exports = artifact.exports;
  artifact.warnings = designState.warnings;
  refreshTemplateTrace(artifact);

  let workflowExports = [];
  try {
    workflowExports = await writeWorkflowArtifactFiles({
      rootDir: context.rootDir,
      designId: resultAllocation.resultId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'workflow_artifacts_write_failed',
      message: '确定性模板 workflow 调试产物写入失败；主体模型和基础导出仍可继续使用。',
      error,
    }));
    workflowExports = buildFailedWorkflowArtifactExports(error);
  }
  artifact.exports = [...artifact.exports, ...workflowExports];
  designState.exports = artifact.exports;
  artifact.warnings = designState.warnings;
  refreshTemplateTrace(artifact);

  try {
    await writeArtifactSnapshotFile({
      rootDir: context.rootDir,
      designId: resultAllocation.resultId,
      artifact,
    });
  } catch (error) {
    designState.warnings.push(buildExportWriteWarning({
      id: 'artifact_snapshot_write_failed',
      message: '确定性模板最终 artifact 快照写入失败；主体响应已返回。',
      error,
    }));
    artifact.warnings = designState.warnings;
    refreshTemplateTrace(artifact);
  }

  releaseResultDirectoryLease({
    rootDir: context.rootDir,
    resultId: resultAllocation.resultId,
    leaseToken: resultAllocation.lease_token,
  });
  const cleanupReport = await cleanupResultDirectories({
    rootDir: context.rootDir,
    keepCount: 3,
  });
  allocationCleanupCompleted = true;
  if (cleanupReport.status === 'migration_required') {
    designState.warnings.push({
      id: 'project_retention_migration_pending',
      status: 'info',
      message: '已生成旧项目清理清单；未经用户明确确认，不会删除历史项目。',
    });
    artifact.warnings = designState.warnings;
  } else if (cleanupReport.status !== 'ok') {
    designState.warnings.push({
      id: 'result_history_cleanup_failed',
      status: 'warn',
      message: '历史结果清理失败；本轮结果已生成，但旧结果可能未完全删除。',
      details: cleanupReport,
    });
    artifact.warnings = designState.warnings;
  }

  return artifact;
  } finally {
    releaseResultDirectoryLease({
      rootDir: context.rootDir,
      resultId: resultAllocation.resultId,
      leaseToken: resultAllocation.lease_token,
    });
    if (!allocationCleanupCompleted) {
      await cleanupResultDirectories({ rootDir: context.rootDir, keepCount: 3 }).catch(() => undefined);
    }
  }
}

function buildDeterministicTemplateConfirmationResponse(artifact, { product, detection } = {}) {
  if (!artifact || artifact.status !== 'artifact') return artifact;

  // A template draft carries the same BOM/layout contract as the final artifact,
  // but deliberately omits executable CAD source and export metadata until the
  // user confirms the 2D preview.
  const {
    cadquery_code: _cadqueryCode,
    exports: _exports,
    project_files: _projectFiles,
    ...draft
  } = artifact;
  const generationTrace = {
    ...(artifact.generation_trace || {}),
    stage: 'confirmation',
    generated_at: new Date().toISOString(),
  };
  const designState = {
    ...(artifact.design_state || {}),
    template_confirmation_required: true,
    template_layout_locked: true,
    generation_trace: generationTrace,
  };
  return {
    ...draft,
    status: 'confirmation',
    title: `${product?.product_name || '行空板植物养护系统'} 参数确认`,
    message: '已按智能浇花模板完成 BOM、盒体尺寸和固定硬件布局预审。请先检查 2D 布局；确认后才会生成真实 CadQuery 模型和导出文件。',
    deterministic_product: artifact.deterministic_product || {
      id: product?.id || 'unihiker_plant_caregiver',
      product_name: product?.product_name || '行空板植物养护系统',
      template_id: UNIHIKER_SMART_WATERING_TEMPLATE_ID,
      matched: true,
      source: detection?.source || 'deterministic_product_detector',
    },
    design_state: designState,
    generation_trace: generationTrace,
    template_layout_locked: true,
    next_step: '确认 2D 布局后继续建模',
    source: 'deterministic_product_template',
  };
}

function buildResultAllocationFailureResponse(allocation = {}) {
  const warning = allocation?.warning && typeof allocation.warning === 'object'
    ? allocation.warning
    : null;
  return withNeedsInputGenerationTrace({
    status: 'needs_input',
    title: '项目存储暂不可用',
    message: '无法安全分配当前项目目录，本轮没有写入任何模型文件。请检查服务器存储状态后重试。',
    questions: ['请稍后重试；如果仍然失败，请检查项目保留策略文件和服务器磁盘状态。'],
    blocking_reason: 'result_directory_allocate_failed',
    warnings: warning ? [warning] : [],
    source: 'deterministic',
  }, {
    source: 'project_lifecycle',
    status: 'needs_input',
    model_status: 'skipped',
    reason: warning?.details?.code || 'result_directory_allocate_failed',
    confidence: null,
  });
}

async function attachProjectDefaultParametersFile({ rootDir, designId, artifact }) {
  const defaultParameters = await writeProjectDefaultParametersFile({
    rootDir,
    designId,
    artifact,
  });
  const projectFiles = {
    ...(artifact.project_files || artifact.design_state?.project_files || {}),
    default_parameters: defaultParameters,
  };
  artifact.project_files = projectFiles;
  artifact.project_default_parameters = defaultParameters.parameters;
  artifact.default_parameters = defaultParameters.parameters;
  if (artifact.design_state && typeof artifact.design_state === 'object') {
    artifact.design_state.project_files = projectFiles;
    artifact.design_state.project_default_parameters = defaultParameters.parameters;
    artifact.design_state.default_parameters = defaultParameters.parameters;
  }
  artifact.exports = mergeExportsById(artifact.exports || [], [defaultParameters]);
  if (artifact.design_state && typeof artifact.design_state === 'object') {
    artifact.design_state.exports = mergeExportsById(artifact.design_state.exports || [], [defaultParameters]);
  }
}

async function attachProjectModelSourceFile({ rootDir, designId, artifact }) {
  const filename = projectModelSourceFilename(artifact);
  const source = await writeProjectModelSourceFile({
    rootDir,
    designId,
    artifact,
    filename,
  });
  const defaultParameters = await writeProjectDefaultParametersFile({
    rootDir,
    designId,
    artifact,
  });
  const projectFiles = {
    ...(artifact.project_files || artifact.design_state?.project_files || {}),
    model_source: source,
    default_parameters: defaultParameters,
    project_manifest: projectStateFileEntry(designId, 'project.json', '项目清单'),
    model_index: projectStateFileEntry(designId, 'model-index.json', '模型对象与表面索引'),
    project_memory: projectStateFileEntry(designId, 'project-memory.json', '项目长期记忆'),
    conversation: projectStateFileEntry(designId, 'conversation.jsonl', '项目可见对话记录', 'jsonl'),
    session_state: projectStateFileEntry(designId, 'session-state.json', '项目会话状态'),
  };
  artifact.project_files = projectFiles;
  artifact.project_default_parameters = defaultParameters.parameters;
  artifact.default_parameters = defaultParameters.parameters;
  attachProjectPersistenceState(artifact, source, designId);
  if (artifact.design_state && typeof artifact.design_state === 'object') {
    artifact.design_state.project_files = projectFiles;
    artifact.design_state.project_default_parameters = defaultParameters.parameters;
    artifact.design_state.default_parameters = defaultParameters.parameters;
  }
  artifact.exports = mergeExportsById(artifact.exports || [], [source, defaultParameters]);
  if (artifact.design_state && typeof artifact.design_state === 'object') {
    artifact.design_state.exports = mergeExportsById(artifact.design_state.exports || [], [source, defaultParameters]);
  }
}

function projectStateFileEntry(designId, filename, label, format = 'json') {
  return {
    id: `project_${filename.replace(/[^a-z0-9]+/gi, '_').replace(/^_+|_+$/g, '')}`,
    label,
    format,
    url: `/exports/${designId}/project/${filename}`,
    fidelity: 'project_state',
  };
}

function attachProjectPersistenceState(artifact, source, designId) {
  const state = {
    project_id: designId,
    project_manifest: source.project_manifest || null,
    project_revision: source.project_revision || 1,
    project_source_hash: source.source_hash || '',
    model_index: source.model_index || null,
    project_memory_summary: source.project_memory_summary || '',
    model_edit_history: source.model_edit_history || [],
  };
  Object.assign(artifact, state);
  if (artifact.design_state && typeof artifact.design_state === 'object') {
    Object.assign(artifact.design_state, state);
  }
}

function projectModelSourceFilename(artifact = {}) {
  if (artifact.template_id === UNIHIKER_PHOTO_ALBUM_TEMPLATE_ID) return 'unihiker-photo-album.cq.py';
  const templateId = normalizeString(artifact.template_id).replace(/[^\w.-]+/g, '-').slice(0, 80);
  return templateId ? `${templateId}.cq.py` : 'model-source.cq.py';
}

function mergeExportsById(existing = [], incoming = []) {
  const byKey = new Map();
  for (const item of [...existing, ...incoming]) {
    if (!item) continue;
    const key = item.id || item.url || item.path || JSON.stringify(item);
    byKey.set(key, item);
  }
  return [...byKey.values()];
}

function hasExplicitProjectRegeneration(body = {}) {
  return [
    body.parameterOverrides,
    body.parameter_overrides,
    body.hardwareFaceOverrides,
    body.hardware_face_overrides,
    body.hardwareRotationOverrides,
    body.hardware_rotation_overrides,
  ].some((value) => value && typeof value === 'object' && Object.keys(value).length > 0);
}

function hasExplicitSurfaceEngravingUpdate(body = {}) {
  if (Object.prototype.hasOwnProperty.call(body, 'surfaceEngravingUpdateAuthorized')) {
    return body.surfaceEngravingUpdateAuthorized === true;
  }
  if (Object.prototype.hasOwnProperty.call(body, 'surface_engraving_update_authorized')) {
    return body.surface_engraving_update_authorized === true;
  }
  return Object.prototype.hasOwnProperty.call(body, 'surfaceEngravings')
    || Object.prototype.hasOwnProperty.call(body, 'surface_engravings');
}

async function exportTemplatePreview({ rootDir, designId, artifact, environment }) {
  if (artifact?.template_case === true || artifact?.design_mode === 'template_case') {
    return {
      preview_assets: Array.isArray(artifact.preview_assets) ? artifact.preview_assets : [],
      exports: Array.isArray(artifact.exports) ? artifact.exports : [],
      warnings: [],
    };
  }
  try {
    return await exportPreviewTool({
      rootDir,
      designId,
      enclosure: artifact.design_state.enclosure_parameters,
      layoutPlan: artifact.design_state.layout_plan,
      environment,
    });
  } catch (error) {
    return {
      preview_assets: [],
      exports: buildFailedPreviewExports(error),
      warnings: [buildExportWriteWarning({
        id: 'preview_export_write_failed',
        message: '确定性模板简化预览写入失败；CadQuery 模板代码和主体 artifact 仍已生成。',
        error,
      })],
    };
  }
}

function refreshTemplateTrace(artifact) {
  const checks = Array.isArray(artifact.checks) ? artifact.checks : [];
  artifact.generation_trace = {
    ...(artifact.generation_trace || {}),
    generated_at: new Date().toISOString(),
    exports: {
      total_count: Array.isArray(artifact.exports) ? artifact.exports.length : 0,
      ids: Array.isArray(artifact.exports) ? artifact.exports.map((item) => item.id).filter(Boolean) : [],
    },
    validation: {
      validation_status: checks.some((item) => item.status === 'fail') ? 'fail' : 'pending',
      status_counts: checks.reduce((acc, item) => {
        acc[item.status] = (acc[item.status] || 0) + 1;
        return acc;
      }, {}),
      failing_ids: checks.filter((item) => item.status === 'fail').map((item) => item.id),
      pending_ids: checks.filter((item) => item.status === 'pending').map((item) => item.id),
    },
  };
  artifact.design_state.generation_trace = artifact.generation_trace;
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
    projectDefaultParameters: prepared.projectDefaultParameters,
    surfaceEngravings: prepared.surfaceEngravings,
    surfaceEngravingPatch: prepared.surfaceEngravingPatch,
    surfaceEngravingPreflight: prepared.surfaceEngravingPreflight,
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
    surface_engravings: prepared.surfaceEngravings || [],
    surface_engraving_patch: prepared.surfaceEngravingPatch || '',
    surface_engraving_preflight: prepared.surfaceEngravingPreflight || null,
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
  projectDefaultParameters = null,
  surfaceEngravings = [],
  surfaceEngravingPatch = '',
  surfaceEngravingPreflight = null,
  hardwareFaceOverrides,
  hardwareRotationOverrides,
  conversationRoute = null,
  revisionIntent = null,
  resolutionOptionRoute = null,
  ignoredMissingHardwareRequests = [],
  droppedFunctions = [],
  warnings,
}) {
  const normalizedSurfaceEngravings = normalizeSurfaceEngravings(surfaceEngravings);
  const surfaceOverrideWarnings = buildSurfaceEngravingOverrideWarnings(
    normalizedSurfaceEngravings,
    surfaceEngravingPreflight,
  );
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
    project_default_parameters: projectDefaultParameters || parameters,
    default_parameters: projectDefaultParameters || parameters,
    surface_engravings: normalizedSurfaceEngravings,
    surface_engraving_patch: normalizeString(surfaceEngravingPatch),
    surface_engraving_preflight: surfaceEngravingPreflight,
    hardware_face_overrides: hardwareFaceOverrides,
    hardware_rotation_overrides: hardwareRotationOverrides,
    conversation_route: conversationRoute,
    revision_intent: revisionIntent,
    resolution_option_route: resolutionOptionRoute,
    ignored_missing_hardware_requests: ignoredMissingHardwareRequests,
    dropped_functions: droppedFunctions,
    warnings: [...(Array.isArray(warnings) ? warnings : []), ...surfaceOverrideWarnings],
  };
}

function buildSurfaceEngravingOverrideWarnings(surfaceEngravings = [], preflight = null) {
  const forcedIds = new Set(surfaceEngravings
    .filter((item) => item?.allow_original_feature_intersection === true)
    .map((item) => item.id)
    .filter(Boolean));
  const report = Array.isArray(preflight?.report) ? preflight.report : [];
  const warnings = [];
  for (const item of report) {
    const override = item?.original_feature_intersection_override;
    if (!override?.applied || (forcedIds.size && !forcedIds.has(item.id))) continue;
    warnings.push({
      id: `surface_engraving_override_${item.id || 'unknown'}`,
      status: 'warn',
      message: '已按用户确认强制刻字；文字可能被边界裁断或影响现有孔位，请检查预览和导出模型。',
      details: override,
    });
  }
  return warnings;
}

function projectDefaultParametersFromDesignState(designState = null) {
  if (!isPlainObject(designState)) return null;
  const existing = designState.project_default_parameters || designState.default_parameters;
  return isPlainObject(existing) && Object.keys(existing).length ? existing : null;
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
    surfaceEngravings: body.surfaceEngravings || body.surface_engravings || currentDesignState.surface_engravings,
    surfaceEngravingPatch: body.surfaceEngravingPatch || body.surface_engraving_patch || currentDesignState.surface_engraving_patch,
    surfaceEngravingPreflight: body.surfaceEngravingPreflight || body.surface_engraving_preflight || currentDesignState.surface_engraving_preflight,
    surfaceEngravingUpdateAuthorized: hasExplicitSurfaceEngravingUpdate(body),
    revisionIntent: body.revisionIntent || body.revision_intent || currentDesignState.revision_intent,
    conversationRoute: body.conversationRoute || body.conversation_route || currentDesignState.conversation_route,
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
