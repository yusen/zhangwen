import { existsSync, readFileSync } from 'node:fs';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import http from 'node:http';
import os from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { buildCadQueryArtifact } from './cadquery-runner.js';
import { buildConversationRoute, isNewRequirementRequest } from './conversation-route.js';
import { commitCustomHardware, deleteCustomHardware, previewCustomHardware } from './custom-hardware.js';
import { applyRevisionToBody, buildDesignRevision } from './design-revision.js';
import { detectDeterministicProduct, listDeterministicTemplateProjects } from './deterministic-products.js';
import { checkEnvironment } from './environment.js';
import { resolveExportRequest } from './export-resolver.js';
import { getFunctionVerifierConfig, verifyBomFunctionCoverage } from './function-verifier.js';
import { listHardwareLibrary } from './hardware-library.js';
import { getIntentModelConfig, maybeAnalyzeIntentWithModel } from './intent-model.js';
import { handleModelEditRequest } from './model-edit-service.js';
import {
  appendProjectConversationTurn,
  ensureProjectLifecycle,
  readProjectConversation,
  readProjectWorkspace,
  withProjectMutationLock,
  writeProjectSessionState,
} from './project-store.js';
import {
  allocateResultDirectory,
  acquireResultDirectoryLease,
  cleanupResultDirectories,
  getProjectStorageHealth,
  isExpiredResultProject,
  normalizeTaskId,
  releaseResultDirectoryLease,
} from './result-store.js';
import {
  analyzeSurfaceEngravingRequest,
  applySurfaceEngravingResultToBody,
  migrateLegacySurfaceEngravings,
} from './surface-engraving.js';
import {
  configureModelSources,
  getModelSourcesPayload,
  probeModelSource,
  saveModelSource,
  setActiveModelSource,
} from './model-sources.js';
import {
  buildDesignFromDraft,
  generateDesign,
  getIntentRuntimeSummary,
  prepareDesign,
  regenerateDesign,
  validateCurrentDesign,
} from './pipeline.js';
import { buildMergedIntentBody, buildRequirementAnalysisResponse } from './requirement-analysis.js';
import {
  applyResolutionRouteToBody,
  buildAmbiguousResolutionOptionResponse,
  routeResolutionOption,
} from './resolution-options.js';
import { listenHttpServer, resolvePythonExecutable, resolveServerHost } from './runtime-config.js';
import { buildHealthPayload, runSelfCheck } from './self-check.js';
import { buildPhotoAlbumEngravingSurfaces } from './template-library/unihiker-photo-album.js';
import { UNIHIKER_SMART_WATERING_TEMPLATE_ID } from './template-library/unihiker-smart-watering-system.js';
import { detectStandaloneStructuralPartsRequest, STRUCTURAL_PART_ROUTE_ACTION } from './structural-parts.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const rootDir = path.resolve(__dirname, '..');
const publicDir = path.join(rootDir, 'public');
const threeVendorDir = path.join(rootDir, 'node_modules', 'three');
const threeVendorFiles = new Map([
  ['/vendor/three/build/three.module.js', '/build/three.module.js'],
  ['/vendor/three/examples/jsm/controls/OrbitControls.js', '/examples/jsm/controls/OrbitControls.js'],
  ['/vendor/three/examples/jsm/loaders/GLTFLoader.js', '/examples/jsm/loaders/GLTFLoader.js'],
  ['/vendor/three/examples/jsm/loaders/STLLoader.js', '/examples/jsm/loaders/STLLoader.js'],
  ['/vendor/three/examples/jsm/utils/BufferGeometryUtils.js', '/examples/jsm/utils/BufferGeometryUtils.js'],
]);
loadEnvFile(path.join(rootDir, '.env.local'));
loadEnvFile(path.join(rootDir, '.env'));

const PORT = Number(process.env.ZW_CAD_INTENT_PORT || process.env.PORT || 5187);
const HOST = resolveServerHost();
const PYTHON = resolvePythonExecutable({ projectRoot: rootDir });
const serverDataRootDir = process.env.ZW_CAD_INTENT_DATA_ROOT
  ? path.resolve(process.env.ZW_CAD_INTENT_DATA_ROOT)
  : rootDir;
const environment = checkEnvironment(PYTHON);
const startedAt = new Date().toISOString();
configureModelSources({ rootDir });

const server = http.createServer(async (request, response) => {
  try {
    if ((request.url || '').startsWith('/api/')) {
      await handleApi(request, response, { dataRootDir: serverDataRootDir });
      return;
    }
    await serveStatic(request, response, { dataRootDir: serverDataRootDir });
  } catch (error) {
    sendJson(response, 500, {
      error: error instanceof Error ? error.message : String(error),
    });
  }
});

server.on('error', (error) => {
  if (error?.code === 'EADDRINUSE') {
    console.error(`ZW-CAD-intent failed to start: port ${PORT} is already in use.`);
    console.error(`Run "netstat -ano | findstr :${PORT}" to find the PID, then stop the old service before restarting.`);
    process.exit(1);
  }
  console.error(error instanceof Error ? error.stack || error.message : String(error));
  process.exit(1);
});

if (process.argv[1] && path.resolve(process.argv[1]) === __filename) {
  listenHttpServer(server, {
    port: PORT,
    host: HOST,
    onListening: () => {
      console.log('ZW-CAD-intent running at http://' + (HOST || 'localhost') + ':' + PORT);
      console.log(`CadQuery: ${environment.cadqueryAvailable ? 'available' : 'pending/missing'}`);
    },
  });
}

export async function handleApi(request, response, { dataRootDir = rootDir } = {}) {
  const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`);

  if (request.method === 'GET' && url.pathname === '/api/health') {
    const projectStorage = await getProjectStorageHealth({ rootDir: dataRootDir });
    sendJson(response, 200, buildHealthPayload({
      rootDir,
      port: PORT,
      startedAt,
      environment,
      intentModelConfig: getIntentModelConfig(),
      functionVerifierConfig: getFunctionVerifierConfig(),
      llmConnection: getModelSourcesPayload().connection,
      runtime: getIntentRuntimeSummary(),
      projectStorage,
    }));
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/model-sources') {
    sendJson(response, 200, getModelSourcesPayload());
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/model-sources') {
    const body = await readRequestJson(request);
    const source = saveModelSource(body);
    sendJson(response, 200, {
      source,
      ...getModelSourcesPayload(),
    });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/model-sources/active') {
    const body = await readRequestJson(request);
    sendJson(response, 200, setActiveModelSource(body.id || body.sourceId || body.source_id));
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/model-sources/probe') {
    const body = await readRequestJson(request);
    const connection = await probeModelSource(body.id || body.sourceId || body.source_id || '');
    sendJson(response, 200, {
      connection,
      ...getModelSourcesPayload(),
    });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/self-check') {
    const body = await readRequestJson(request);
    const diagnosticsRoot = await mkdtemp(path.join(os.tmpdir(), 'zwcad-self-check-'));
    try {
      const result = await runSelfCheck({
        rootDir,
        dataRootDir: diagnosticsRoot,
        environment,
        python: PYTHON,
        port: PORT,
        startedAt,
        useModel: body.useModel !== false,
        runCadQuery: body.runCadQuery === true,
      });
      sendJson(response, 200, result);
    } finally {
      await rm(diagnosticsRoot, { recursive: true, force: true });
    }
    return;
  }

  if (request.method === 'GET' && url.pathname === '/api/hardware/library') {
    sendJson(response, 200, {
      ...listHardwareLibrary(),
      template_projects: listDeterministicTemplateProjects(),
    });
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/custom-hardware/preview') {
    const body = await readRequestJson(request);
    const result = await previewCustomHardware(body, {
      rootDir,
      python: PYTHON,
      environment,
    });
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/custom-hardware/commit') {
    const body = await readRequestJson(request);
    const result = await commitCustomHardware(body, {
      rootDir,
      python: PYTHON,
      environment,
    });
    sendJson(response, result.status === 'custom_hardware_committed' ? 200 : 400, result);
    return;
  }

  const customHardwareDeleteMatch = url.pathname.match(/^\/api\/custom-hardware\/([^/]+)$/);
  if (request.method === 'DELETE' && customHardwareDeleteMatch) {
    const result = await deleteCustomHardware(decodeURIComponent(customHardwareDeleteMatch[1]), {
      rootDir,
      python: PYTHON,
      environment,
    });
    sendJson(response, result.status === 'custom_hardware_deleted' ? 200 : 400, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/agent/generate') {
    let body = await readRequestJson(request);
    const route = { route_action: 'new_requirement', reason: '兼容生成入口按当前项目生命周期保存。' };
    let projectRequest = null;
    let finalized = false;
    try {
      projectRequest = await ensurePrepareProjectContext(body, {
        dataRootDir,
        forceNew: false,
      });
      if (sendProjectAllocationFailure(response, projectRequest, route)) return;
      body = projectRequest.body;
      if (detectStandaloneStructuralPartsRequest(body).requested) {
        body = {
          ...body,
          prompt: body.prompt || body.latestUserMessage || body.latest_user_message || '通用件结构件项目',
          conversationRoute: {
            route_action: STRUCTURAL_PART_ROUTE_ACTION,
            confidence: 1,
            reason: '独立结构件生成入口跳过 LLM 意图和电子功能验证。',
            source: 'deterministic_conversation_route',
          },
        };
        const result = await generateDesign(body, {
          rootDir: dataRootDir,
          environment,
          functionVerifier: verifyBomFunctionCoverage,
          hardwareLibrarySummary: listHardwareLibrary().profiles,
        });
        await finalizeAgentPrepareResponse(response, 200, result, {
          body,
          route: body.conversationRoute,
          dataRootDir,
          projectRequest,
        });
        finalized = true;
        return;
      }
      const deterministicDetection = detectDeterministicProduct(body);
      if (deterministicDetection?.product?.template_id) {
        const deterministicBuilder = deterministicDetection.product.template_id === UNIHIKER_SMART_WATERING_TEMPLATE_ID
          ? prepareDesign
          : generateDesign;
        const result = await deterministicBuilder(body, {
          rootDir: dataRootDir,
          environment,
          functionVerifier: verifyBomFunctionCoverage,
          hardwareLibrarySummary: listHardwareLibrary().profiles,
        });
        await finalizeAgentPrepareResponse(response, 200, result, {
          body,
          route,
          dataRootDir,
          projectRequest,
        });
        finalized = true;
        return;
      }
      const modelIntentResult = await maybeAnalyzeIntentWithModel(body, {
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      if (modelIntentResult.status === 'needs_input') {
        await finalizeAgentPrepareResponse(response, 200, modelIntentResult.response, {
          body,
          route,
          dataRootDir,
          projectRequest,
        });
        finalized = true;
        return;
      }
      const { generationBody } = buildMergedIntentBody(body, modelIntentResult);
      const result = await generateDesign(generationBody, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      await finalizeAgentPrepareResponse(
        response,
        result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200,
        result,
        { body, route, dataRootDir, projectRequest },
      );
      finalized = true;
    } finally {
      if (projectRequest?.leaseToken && projectRequest?.resultId) {
        releaseResultDirectoryLease({
          rootDir: dataRootDir,
          resultId: projectRequest.resultId,
          leaseToken: projectRequest.leaseToken,
        });
        if (!finalized) {
          await cleanupResultDirectories({ rootDir: dataRootDir, keepCount: 3 }).catch(() => undefined);
        }
      }
    }
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/agent/prepare') {
    let body = await readRequestJson(request);
    const incomingDesignState = body.currentDesignState || body.current_design_state || body.designState || body.design_state || {};
    const incomingContext = body.conversationContext || body.conversation_context || {};
    const incomingProjectId = normalizeTaskId(
      body.taskId || body.task_id || incomingDesignState.id || incomingContext.taskId || incomingContext.task_id,
    );
    let hydrationLeaseToken = '';
    let projectRequestForRelease = null;
    const releaseHydrationLease = () => {
      if (!hydrationLeaseToken || !incomingProjectId) return;
      releaseResultDirectoryLease({
        rootDir: dataRootDir,
        resultId: incomingProjectId,
        leaseToken: hydrationLeaseToken,
      });
      hydrationLeaseToken = '';
    };
    try {
      if (incomingProjectId) {
        hydrationLeaseToken = acquireResultDirectoryLease({
          rootDir: dataRootDir,
          resultId: incomingProjectId,
        });
        if (await isExpiredResultProject({ rootDir: dataRootDir, resultId: incomingProjectId })) {
          const latestPrompt = String(body.latestUserMessage || body.latest_user_message || body.prompt || '').trim();
          const explicitlyStartsNew = body.routeAction === 'new_requirement'
            || body.route_action === 'new_requirement'
            || isNewRequirementRequest(latestPrompt)
            || /(?:新建|创建|开始)(?:一个|新的)?[^，。,.]{0,40}(?:项目|任务)/.test(latestPrompt);
          if (!explicitlyStartsNew) {
            sendJson(response, 409, {
              status: 'needs_input',
              title: '当前项目已被清理',
              message: '当前项目已超过“最近三个”保留范围，旧页面不能重新创建它。请新建项目。',
              questions: ['请新建项目后重新提交需求。'],
              blocking_reason: 'project_expired',
            });
            return;
          }
          releaseHydrationLease();
          body = {
            ...body,
            taskId: '',
            task_id: '',
            currentDesignState: null,
            current_design_state: null,
            currentArtifact: null,
            current_artifact: null,
            conversationContext: {
              ...(body.conversationContext || body.conversation_context || {}),
              taskId: '',
              task_id: '',
              hasArtifact: false,
              has_artifact: false,
            },
          };
        }
      }
      body = await hydrateActiveProjectContext(body, { projectRootDir: dataRootDir });
    const resolutionRoute = routeResolutionOption(body);
    if (resolutionRoute?.status === 'ambiguous') {
      const projectRequest = await ensurePrepareProjectContext(body, {
        dataRootDir,
        forceNew: false,
      });
      projectRequestForRelease = projectRequest;
      releaseHydrationLease();
      if (sendProjectAllocationFailure(response, projectRequest, null)) return;
      body = projectRequest.body;
      const result = buildAmbiguousResolutionOptionResponse(resolutionRoute);
      await finalizeAgentPrepareResponse(response, 200, result, {
        body,
        route: null,
        dataRootDir,
        projectRequest,
      });
      return;
    }
    if (resolutionRoute?.status === 'matched') {
      body = applyResolutionRouteToBody(body, resolutionRoute);
    }
    const route = buildConversationRoute(body);
    const projectRequest = await ensurePrepareProjectContext(body, {
      dataRootDir,
      forceNew: route.route_action === 'new_requirement',
    });
    projectRequestForRelease = projectRequest;
    releaseHydrationLease();
    if (sendProjectAllocationFailure(response, projectRequest, route)) return;
    body = projectRequest.body;
    const respond = (statusCode, result) => finalizeAgentPrepareResponse(response, statusCode, result, {
      body,
      route,
      dataRootDir,
      projectRequest,
    });
    const revision = shouldBuildRevision(route)
      ? buildDesignRevision(body, route)
      : null;
    let routedBody = revision
      ? applyRevisionToBody(body, route, revision)
      : withRouteMetadata(body, route, null);
    routedBody = applyConversationContextTransition(routedBody, route);
    if (route.route_action === 'surface_engraving') {
      if (isTemplateConfirmationDraftBody(routedBody)) {
        const draftState = routedBody.currentDesignState
          || routedBody.current_design_state
          || routedBody.design_state
          || routedBody.designState
          || {};
        const templateId = String(
          routedBody.projectSessionState?.template_confirmation?.template_id
            || routedBody.project_session_state?.template_confirmation?.template_id
            || draftState.template_id
            || draftState.intent?.template_id
            || '',
        ).trim();
        const templatePrompt = templatePromptForConfirmation(templateId);
        if (!templatePrompt) {
          const result = {
            status: 'needs_input',
            title: '确认草案尚未锁定模板',
            message: '当前仍在参数确认阶段，无法安全识别模板。请重新提交需求后再继续。',
            questions: ['请重新提交智能浇花系统需求。'],
            blocking_reason: 'template_confirmation_invalid',
          };
          attachRouteMetadata(result, route, revision);
          await respond(200, result);
          return;
        }
        const result = await prepareDesign({
          ...routedBody,
          prompt: templatePrompt,
          selectedHardwareIds: [],
          intent: undefined,
          currentDesignState: draftState,
        }, {
          rootDir: dataRootDir,
          environment,
          functionVerifier: verifyBomFunctionCoverage,
          hardwareLibrarySummary: listHardwareLibrary().profiles,
        });
        if (result?.status === 'confirmation') {
          result.title = '请先确认盒体和 2D 布局';
          result.message = '当前仍是盒体参数确认阶段，刻字会在确认并生成真实模型后处理；请先确认 2D 布局，再提交刻字要求。';
        }
        attachRouteMetadata(result, route, revision);
        await respond(200, result);
        return;
      }
      const engravingAnalysis = await analyzeSurfaceEngravingRequest({
        ...routedBody,
        latestUserMessage: body.latestUserMessage || body.latest_user_message || body.prompt,
        currentCadQueryCode: body.currentCadQueryCode || body.current_cadquery_code || body.cadquery_code,
      }, { python: PYTHON, cadqueryAvailable: environment.cadqueryAvailable });
      if (engravingAnalysis.status === 'not_applicable') {
        const fallbackRoute = {
          ...route,
          route_action: 'model_edit',
          confidence: Math.min(0.9, Number(route.confidence) || 0.8),
          reason: '刻字分析器判定最新输入不属于刻字，已重路由到模型修改。',
          context_transition: route.context_transition || {
            from: 'surface_engraving',
            to: 'model_edit',
            action: 'supersede',
            clear_surface_engraving_draft: true,
          },
        };
        const fallbackBody = applyConversationContextTransition(
          withRouteMetadata(routedBody, fallbackRoute, null),
          fallbackRoute,
        );
        const result = await handleModelEditRequest(fallbackBody, {
          rootDir: dataRootDir,
          python: PYTHON,
          environment,
        });
        attachRouteMetadata(result, fallbackRoute, null);
        await finalizeAgentPrepareResponse(response, 200, result, {
          body,
          route: fallbackRoute,
          dataRootDir,
          projectRequest,
        });
        return;
      }
      if (engravingAnalysis.status !== 'ok') {
        const result = withRouteMetadata(engravingAnalysis.response, route, revision);
        await respond(200, result);
        return;
      }
      routedBody = applySurfaceEngravingResultToBody(routedBody, engravingAnalysis);
      const result = await generateDesign(routedBody, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      attachRouteMetadata(result, route, routedBody.revisionIntent || routedBody.revision_intent);
      await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
      return;
    }
    if (['model_edit', 'confirm_model_edit', 'cancel_model_edit', 'undo_model_edit'].includes(route.route_action)) {
      const result = await handleModelEditRequest(withRouteMetadata(routedBody, route, null), {
        rootDir: dataRootDir,
        python: PYTHON,
        environment,
      });
      attachRouteMetadata(result, route, null);
      await respond(200, result);
      return;
    }
    if (route.route_action === 'new_requirement') {
      routedBody = resetRoutedBodyForNewRequirement(routedBody, route);
      if (detectDeterministicProduct(routedBody)) {
        const result = await prepareDesign(routedBody, {
          rootDir: dataRootDir,
          environment,
          functionVerifier: verifyBomFunctionCoverage,
          hardwareLibrarySummary: listHardwareLibrary().profiles,
        });
        attachRouteMetadata(result, route, revision);
        await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
        return;
      }
    }
    if (route.route_action === 'selected_hardware_enclosure') {
      routedBody.prompt = routedBody.latestUserMessage || routedBody.latest_user_message || routedBody.prompt || routedBody.intent?.product_name || '选定硬件外壳';
      const result = await prepareDesign(routedBody, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      attachRouteMetadata(result, route, revision);
      await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
      return;
    }
    if (route.route_action === STRUCTURAL_PART_ROUTE_ACTION) {
      routedBody.prompt = routedBody.latestUserMessage
        || routedBody.latest_user_message
        || routedBody.prompt
        || routedBody.intent?.product_name
        || '通用件结构件项目';
      const result = await prepareDesign(routedBody, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      attachRouteMetadata(result, route, revision);
      await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
      return;
    }
    if (route.route_action === 'build_confirmed') {
      const draftDesignState = routedBody.draftDesignState
        || routedBody.currentDesignState
        || routedBody.design_state
        || routedBody.designState
        || null;
      const result = draftDesignState?.intent
        ? await buildDesignFromDraft({
            ...routedBody,
            draftDesignState,
          }, {
            rootDir: dataRootDir,
            environment,
            functionVerifier: verifyBomFunctionCoverage,
            hardwareLibrarySummary: listHardwareLibrary().profiles,
          })
        : {
            status: 'needs_input',
            title: '请确认当前草案',
            message: '当前输入被识别为“继续建模”。如果页面已有参数确认草案，请点击“继续建模”；如果没有草案，请先完成需求分析和参数确认。',
            questions: ['请先确认参数草案，或重新提交产品需求。'],
            blocking_reason: 'missing_confirmed_draft',
            conversation_route: route,
            revision_intent: revision,
          };
      attachRouteMetadata(result, route, revision);
      await respond(200, result);
      return;
    }
    const modelIntentResult = await maybeAnalyzeIntentWithModel(routedBody, {
      hardwareLibrarySummary: listHardwareLibrary().profiles,
    });
    if (modelIntentResult.status === 'needs_input') {
      const result = withRouteMetadata(modelIntentResult.response, route, revision);
      await respond(200, result);
      return;
    }
    if (route.route_action === 'revise_artifact') {
      const { generationBody } = buildMergedIntentBody(routedBody, modelIntentResult);
      const hasArtifact = Boolean(routedBody.conversationContext?.hasArtifact || routedBody.conversation_context?.has_artifact);
      const result = await (hasArtifact ? generateDesign : prepareDesign)(generationBody, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      attachRouteMetadata(result, route, revision);
      await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
      return;
    }
    if (route.route_action !== 'confirm_requirement_analysis') {
      const result = await buildRequirementAnalysisResponse(routedBody, modelIntentResult, { rootDir: dataRootDir });
      attachRouteMetadata(result, route, revision);
      await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
      return;
    }
    const confirmedAnalysis = routedBody.currentRequirementAnalysis || routedBody.current_requirement_analysis || null;
    const confirmedBody = confirmedAnalysis?.partial_intent
      ? {
          ...routedBody,
          intent: confirmedAnalysis.partial_intent,
          intentAnalysis: confirmedAnalysis.intent_analysis || routedBody.intentAnalysis || routedBody.intent_analysis,
        }
      : routedBody;
    const { generationBody } = buildMergedIntentBody(confirmedBody, modelIntentResult);
    const result = await prepareDesign(generationBody, {
      rootDir: dataRootDir,
      environment,
      functionVerifier: verifyBomFunctionCoverage,
      hardwareLibrarySummary: listHardwareLibrary().profiles,
    });
    attachRouteMetadata(result, route, revision);
    await respond(result.status === 'needs_input' && result.blocking_reason === 'empty_prompt' ? 400 : 200, result);
    return;
    } finally {
      releaseHydrationLease();
      if (projectRequestForRelease?.leaseToken && projectRequestForRelease?.resultId) {
        releaseResultDirectoryLease({
          rootDir: dataRootDir,
          resultId: projectRequestForRelease.resultId,
          leaseToken: projectRequestForRelease.leaseToken,
        });
      }
    }
  }

  if (request.method === 'POST' && url.pathname === '/api/design/build') {
    const body = await readRequestJson(request);
    const lease = await acquireBodyProjectLease(body, { dataRootDir });
    try {
      if (lease.expired) {
        sendExpiredProjectResponse(response);
        return;
      }
      const result = await buildDesignFromDraft(body, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      sendJson(response, 200, result);
    } finally {
      releaseBodyProjectLease(lease, { dataRootDir });
    }
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/design/regenerate') {
    const body = await readRequestJson(request);
    const lease = await acquireBodyProjectLease(body, { dataRootDir });
    try {
      if (lease.expired) {
        sendExpiredProjectResponse(response);
        return;
      }
      const result = await regenerateDesign(body, {
        rootDir: dataRootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      sendJson(response, 200, result);
    } finally {
      releaseBodyProjectLease(lease, { dataRootDir });
    }
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/design/validate') {
    const body = await readRequestJson(request);
    const result = validateCurrentDesign(body, { environment });
    sendJson(response, 200, result);
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/export') {
    const body = await readRequestJson(request);
    sendJson(response, 200, resolveExportRequest(body, environment));
    return;
  }

  if (request.method === 'POST' && url.pathname === '/api/cadquery/build') {
    const body = await readRequestJson(request);
    const result = await buildCadQueryArtifact({
      rootDir: dataRootDir,
      python: PYTHON,
      environment,
      body,
      requireManagedProject: true,
    });
    sendJson(response, 200, result);
    return;
  }

  sendJson(response, 404, { error: 'Not found.' });
}

export async function hydrateActiveProjectContext(body = {}, { projectRootDir = rootDir } = {}) {
  const currentDesignState = body.currentDesignState || body.current_design_state || body.designState || body.design_state || null;
  const context = body.conversationContext || body.conversation_context || {};
  const projectId = String(body.taskId || body.task_id || currentDesignState?.id || context.taskId || context.task_id || '').trim();
  if (!projectId || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(projectId)) return body;
  let workspace;
  let projectConversation = [];
  let storedArtifact = null;
  try {
    const snapshot = await withProjectMutationLock(
      { rootDir: projectRootDir, projectId },
      async () => {
        const loadedWorkspace = await readProjectWorkspace({ rootDir: projectRootDir, projectId });
        const conversation = await readProjectConversation({
          rootDir: projectRootDir,
          projectId,
        }).catch(() => []);
        let artifact = null;
        if (loadedWorkspace.status === 'ready'
          && !(body.currentArtifact || body.current_artifact || body.artifact)) {
          try {
            artifact = JSON.parse(await readFile(
              path.join(projectRootDir, 'exports', projectId, 'artifact.json'),
              'utf8',
            ));
          } catch {
            artifact = null;
          }
        }
        return { workspace: loadedWorkspace, projectConversation: conversation, storedArtifact: artifact };
      },
    );
    workspace = snapshot.workspace;
    projectConversation = snapshot.projectConversation;
    storedArtifact = snapshot.storedArtifact;
  } catch {
    return body;
  }
  const sessionState = workspace.session_state || {};
  const restoredSurfaceDraft = resolveSurfaceEngravingDraft(body, sessionState, projectId);
  if (workspace.status !== 'ready') {
    return {
      ...body,
      taskId: projectId,
      projectManifest: workspace.project_manifest,
      projectSessionState: sessionState,
      projectConversation,
      surfaceEngravingDraft: restoredSurfaceDraft,
      conversationContext: {
        ...context,
        taskId: projectId,
        workflowStage: context.workflowStage || sessionState.workflow_stage || '',
        hasArtifact: false,
        hasCurrentDesignState: false,
      },
    };
  }
  let artifact = body.currentArtifact || body.current_artifact || body.artifact || storedArtifact;
  let hydratedDesignState = currentDesignState || artifact?.design_state || {
    id: projectId,
    project_id: projectId,
    project_manifest: workspace.project_manifest,
    project_revision: workspace.project_revision,
    project_source_hash: workspace.source_hash,
    project_memory_summary: workspace.project_memory?.summary || '',
    model_index: workspace.model_index,
  };
  let legacySurfaceMigration = null;
  let modelSurfaces = hydratedDesignState.engraving_surfaces
    || hydratedDesignState.model_index?.surfaces
    || workspace.model_index?.surfaces
    || [];
  const templateId = workspace.project_manifest?.template?.id || artifact?.template_id || '';
  const geometry = hydratedDesignState.cad_parameters?.geometry;
  if (templateId === 'unihiker_photo_album_v1' && geometry) {
    try {
      modelSurfaces = buildPhotoAlbumEngravingSurfaces(geometry);
      hydratedDesignState = {
        ...hydratedDesignState,
        engraving_surfaces: modelSurfaces,
        model_index: {
          ...(hydratedDesignState.model_index || workspace.model_index || {}),
          surfaces: modelSurfaces,
        },
      };
    } catch {
      // 旧项目几何字段不完整时保留原表面目录，后续要求用户确认。
    }
  }
  const existingEngravings = hydratedDesignState.surface_engravings || artifact?.surface_engravings || [];
  if (Array.isArray(existingEngravings) && existingEngravings.length && Array.isArray(modelSurfaces) && modelSurfaces.length) {
    let report = [];
    try {
      report = JSON.parse(await readFile(path.join(projectRootDir, 'exports', projectId, 'surface-engraving.json'), 'utf8'));
    } catch {
      report = [];
    }
    legacySurfaceMigration = migrateLegacySurfaceEngravings({
      engravings: existingEngravings,
      modelSurfaces,
      report,
    });
    hydratedDesignState = {
      ...hydratedDesignState,
      surface_engravings: legacySurfaceMigration.surface_engravings,
      surface_engraving_migration: {
        migrations: legacySurfaceMigration.migrations,
        unresolved: legacySurfaceMigration.unresolved,
        requires_confirmation: legacySurfaceMigration.requires_confirmation,
      },
    };
    if (artifact) {
      artifact = {
        ...artifact,
        surface_engravings: legacySurfaceMigration.surface_engravings,
        design_state: hydratedDesignState,
      };
    }
  }
  return {
    ...body,
    taskId: projectId,
    currentDesignState: hydratedDesignState,
    currentCadQueryCode: workspace.source,
    currentArtifact: artifact,
    projectManifest: workspace.project_manifest,
    projectRevision: workspace.project_revision,
    projectSourceHash: workspace.source_hash,
    projectMemory: workspace.project_memory,
    modelIndex: workspace.model_index,
    modelEditHistory: workspace.project_memory?.model_edit_history || [],
    surfaceEngravings: hydratedDesignState.surface_engravings || [],
    surfaceEngravingMigration: hydratedDesignState.surface_engraving_migration || null,
    projectSessionState: sessionState,
    projectConversation,
    surfaceEngravingDraft: restoredSurfaceDraft,
    conversationContext: {
      ...context,
      taskId: projectId,
      workflowStage: context.workflowStage || sessionState.workflow_stage || '',
      hasArtifact: true,
      hasCurrentDesignState: true,
    },
  };
}

function resolveSurfaceEngravingDraft(body = {}, sessionState = {}, projectId = '') {
  const activeDrafts = sessionState?.active_drafts;
  if (activeDrafts && typeof activeDrafts === 'object' && !Array.isArray(activeDrafts)) {
    const saved = activeDrafts.surface_engraving;
    return saved?.task_id === projectId ? saved : null;
  }
  // Legacy projects may not have project_session_state_v1 yet. Until their
  // first server-side state write, accept a same-project client draft for
  // backward compatibility; once active_drafts exists, the server is
  // authoritative so an old tab cannot resurrect a cleared draft.
  const explicit = body.surfaceEngravingDraft || body.surface_engraving_draft || null;
  if (!explicit || typeof explicit !== 'object' || Array.isArray(explicit)) return null;
  return !explicit.task_id || explicit.task_id === projectId ? explicit : null;
}

async function ensurePrepareProjectContext(body = {}, { dataRootDir, forceNew = false } = {}) {
  const prompt = String(body.latestUserMessage || body.latest_user_message || body.prompt || '').trim();
  if (!prompt) return { body, resultId: '', leaseToken: '' };
  const currentDesignState = body.currentDesignState || body.current_design_state || body.designState || body.design_state || {};
  const context = body.conversationContext || body.conversation_context || {};
  const previousTaskId = normalizeTaskId(body.taskId || body.task_id || currentDesignState.id || context.taskId || context.task_id);
  if (forceNew && previousTaskId) {
    const expired = await isExpiredResultProject({ rootDir: dataRootDir, resultId: previousTaskId });
    const existingProjectPath = path.join(dataRootDir, 'exports', previousTaskId, 'project', 'project.json');
    if (!expired && existsSync(existingProjectPath)) {
      await writeProjectSessionState({
        rootDir: dataRootDir,
        projectId: previousTaskId,
        state: {
          workflow_stage: 'inactive',
          last_blocking_state: null,
          active_drafts: {},
        },
      }).catch(() => undefined);
    }
  }
  const startsNewProject = forceNew || !previousTaskId;
  const requestedTaskId = startsNewProject
    ? ''
    : previousTaskId;
  const suppliedStartedAt = body.taskStartedAt || body.task_started_at || currentDesignState.result_started_at;
  const parsedStartedAt = suppliedStartedAt ? new Date(suppliedStartedAt) : null;
  const startedAt = startsNewProject
    ? new Date()
    : parsedStartedAt && Number.isFinite(parsedStartedAt.getTime())
      ? parsedStartedAt
      : new Date();
  const allocation = await allocateResultDirectory({
    rootDir: dataRootDir,
    taskId: requestedTaskId,
    startedAt,
  });
  if (allocation.status !== 'ok') {
    return {
      body,
      resultId: '',
      leaseToken: '',
      allocationFailure: allocation.warning || {
        id: 'result_directory_allocate_failed',
        status: 'fail',
        message: '项目目录分配失败。',
      },
    };
  }
  try {
    await ensureProjectLifecycle({
      rootDir: dataRootDir,
      projectId: allocation.resultId,
      title: body.currentRequirementAnalysis?.partial_intent?.product_name || '',
      lifecycleStatus: 'draft',
      now: allocation.reused ? new Date() : startedAt,
    });
  } catch (error) {
    releaseResultDirectoryLease({
      rootDir: dataRootDir,
      resultId: allocation.resultId,
      leaseToken: allocation.lease_token,
    });
    throw error;
  }
  return {
    resultId: allocation.resultId,
    leaseToken: allocation.lease_token,
    body: {
      ...body,
      taskId: allocation.resultId,
      task_id: allocation.resultId,
      taskStartedAt: allocation.started_at,
      task_started_at: allocation.started_at,
      conversationContext: {
        ...(body.conversationContext || body.conversation_context || {}),
        taskId: allocation.resultId,
      },
    },
  };
}

function sendProjectAllocationFailure(response, projectRequest = {}, route = null) {
  if (!projectRequest?.allocationFailure) return false;
  sendJson(response, 503, {
    status: 'needs_input',
    title: '项目存储暂不可用',
    message: '无法安全分配当前项目目录，本轮没有写入任何项目文件。请检查服务器存储状态后重试。',
    questions: ['请稍后重试；如果仍然失败，请检查项目保留策略文件和服务器磁盘状态。'],
    blocking_reason: 'result_directory_allocate_failed',
    conversation_route: route || null,
    warnings: [projectRequest.allocationFailure],
  });
  return true;
}

async function finalizeAgentPrepareResponse(response, statusCode, result, {
  body,
  route,
  dataRootDir,
  projectRequest,
} = {}) {
  const projectId = normalizeTaskId(
    result?.taskId
      || result?.task_id
      || result?.design_state?.id
      || body?.taskId
      || body?.task_id
      || projectRequest?.resultId,
  );
  if (result && typeof result === 'object') {
    if (projectId) {
      result.taskId = result.taskId || projectId;
      result.task_id = result.task_id || projectId;
    }
    if (route?.context_transition) {
      result.context_transition = result.context_transition || route.context_transition;
    }
  }
  if (projectId) {
    try {
      await persistVisibleProjectTurn({ rootDir: dataRootDir, projectId, body, result, route });
    } catch (error) {
      if (result && typeof result === 'object') {
        result.warnings = [
          ...(Array.isArray(result.warnings) ? result.warnings : []),
          {
            id: 'project_conversation_persist_failed',
            status: 'warn',
            message: '本轮结果已生成，但项目对话或会话状态保存失败。',
            details: { code: error?.code || '', message: error instanceof Error ? error.message : String(error) },
          },
        ];
      }
    }
  }
  if (projectRequest?.leaseToken && projectRequest?.resultId) {
    releaseResultDirectoryLease({
      rootDir: dataRootDir,
      resultId: projectRequest.resultId,
      leaseToken: projectRequest.leaseToken,
    });
  }
  if (projectId) {
    const cleanup = await cleanupResultDirectories({ rootDir: dataRootDir, keepCount: 3 });
    if (cleanup.status === 'migration_required'
      && result
      && typeof result === 'object'
      && !(result.warnings || []).some((item) => item?.id === 'project_retention_migration_pending')) {
      result.warnings = [
        ...(Array.isArray(result.warnings) ? result.warnings : []),
        {
          id: 'project_retention_migration_pending',
          status: 'info',
          message: '已生成旧项目清理清单；在用户再次确认前不会删除历史项目。',
        },
      ];
    }
  }
  sendJson(response, statusCode, result);
}

async function persistVisibleProjectTurn({ rootDir: projectRootDir, projectId, body, result, route }) {
  const lifecycleStatus = result?.status === 'artifact'
    ? 'ready'
    : result?.status === 'failed'
      ? 'failed'
      : 'draft';
  await ensureProjectLifecycle({
    rootDir: projectRootDir,
    projectId,
    title: result?.design_state?.intent?.product_name
      || result?.requirement_analysis?.partial_intent?.product_name
      || result?.current_requirement_analysis?.partial_intent?.product_name
      || body?.currentRequirementAnalysis?.partial_intent?.product_name
      || body?.current_requirement_analysis?.partial_intent?.product_name
      || '',
    lifecycleStatus,
  });
  const transition = result?.context_transition || route?.context_transition || null;
  const surfaceDraft = result?.surface_engraving_draft || result?.surfaceEngravingDraft || null;
  const modelEditPlan = result?.model_edit_plan;
  const activeDrafts = {};
  if (!transition?.clear_surface_engraving_draft && surfaceDraft?.task_id === projectId) {
    activeDrafts.surface_engraving = surfaceDraft;
  }
  if (result?.blocking_reason === 'model_edit_confirmation' && modelEditPlan?.plan_id) {
    activeDrafts.model_edit = {
      schema_version: modelEditPlan.schema_version || 'model_edit_plan_v1',
      project_id: projectId,
      plan_id: modelEditPlan.plan_id,
      intent_summary: modelEditPlan.intent_summary || '',
      requires_confirmation: true,
      source_hash: modelEditPlan.source_hash || '',
    };
  }
  const templateConfirmation = templateConfirmationFromResult(result, projectId);
  const sessionState = {
    workflow_stage: workflowStageFromResult(result),
    parameter_overrides: body?.parameterOverrides || body?.parameter_overrides || {},
    last_blocking_state: result?.status === 'needs_input'
      ? {
          status: result.status,
          blocking_reason: result.blocking_reason || '',
          message: result.message || '',
          questions: result.questions || [],
        }
      : null,
    active_drafts: activeDrafts,
  };
  if (templateConfirmation !== undefined) {
    sessionState.template_confirmation = templateConfirmation;
    sessionState.template_confirmation_required = Boolean(templateConfirmation);
  } else if (result?.status === 'artifact' || route?.route_action === 'new_requirement') {
    sessionState.template_confirmation = null;
    sessionState.template_confirmation_required = false;
  }
  await writeProjectSessionState({
    rootDir: projectRootDir,
    projectId,
    state: sessionState,
  });
  await appendProjectConversationTurn({
    rootDir: projectRootDir,
    projectId,
    userMessage: body?.latestUserMessage || body?.latest_user_message || body?.prompt || '',
    assistantResponse: result,
    routeAction: route?.route_action || result?.conversation_route?.route_action || '',
  });
}

function templateConfirmationFromResult(result = {}, projectId = '') {
  if (result?.status !== 'confirmation' || !projectId) return undefined;
  const templateId = String(
    result.template_id
      || result.design_state?.template_id
      || result.design_state?.intent?.template_id
      || '',
  ).trim();
  if (!templateId) return null;
  return {
    schema_version: 'template_confirmation_v1',
    status: 'pending',
    task_id: projectId,
    template_id: templateId,
    deterministic_product_id: String(
      result.deterministic_product?.id
        || result.design_state?.deterministic_product?.id
        || '',
    ).trim(),
    bom_hardware_ids: Array.isArray(result.bom)
      ? result.bom.map((item) => String(item?.hardware_id || '').trim()).filter(Boolean)
      : [],
  };
}

function isTemplateConfirmationDraftBody(body = {}) {
  const state = body.currentDesignState
    || body.current_design_state
    || body.design_state
    || body.designState
    || {};
  const session = body.projectSessionState || body.project_session_state || {};
  return state.template_confirmation_required === true
    || (state.template_layout_locked === true
      && (session.template_confirmation?.status === 'pending'
        || String(body.conversationContext?.workflowStage || body.conversation_context?.workflowStage || '').trim() === 'confirming'));
}

function templatePromptForConfirmation(templateId = '') {
  return {
    unihiker_smart_watering_system_v1: '行空板智能浇花系统',
    unihiker_photo_album_v1: '行空板电子相册产品',
    xiao_smart_pendant_v1: 'XIAO智能项链',
  }[templateId] || '';
}

function workflowStageFromResult(result = {}) {
  if (result.status === 'artifact') return 'review';
  if (result.status === 'confirmation') return 'confirming';
  if (result.status === 'requirement_analysis') return 'requirement_analysis';
  if (result.status === 'needs_input') return 'blocked';
  return result.status || 'idle';
}

function applyConversationContextTransition(body = {}, route = {}) {
  const transition = route.context_transition;
  if (!transition?.clear_surface_engraving_draft) return body;
  const result = { ...body };
  for (const key of [
    'surfaceEngravingDraft',
    'surface_engraving_draft',
    'surfaceEngravingTurns',
    'surface_engraving_turns',
  ]) delete result[key];
  const lastNeedsInput = result.lastNeedsInput || result.last_needs_input;
  if (String(lastNeedsInput?.blocking_reason || '').startsWith('surface_engraving_')) {
    delete result.lastNeedsInput;
    delete result.last_needs_input;
  }
  return result;
}

async function serveStatic(request, response, { dataRootDir = rootDir } = {}) {
  const url = new URL(request.url || '/', `http://${request.headers.host || 'localhost'}`);
  if (url.pathname.startsWith('/exports/')) {
    await serveExportFile(url.pathname, response, { dataRootDir });
    return;
  }
  if (url.pathname.startsWith('/vendor/three/')) {
    await serveThreeVendorFile(url.pathname, response);
    return;
  }
  const filePath = safeJoin(publicDir, url.pathname === '/' ? '/index.html' : url.pathname);
  if (!filePath) {
    response.writeHead(403);
    response.end('Forbidden');
    return;
  }
  try {
    const content = await readFile(filePath);
    response.writeHead(200, { 'Content-Type': contentTypeForPath(filePath) });
    response.end(content);
  } catch {
    const fallback = await readFile(path.join(publicDir, 'index.html'));
    response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
    response.end(fallback);
  }
}

async function serveThreeVendorFile(urlPath, response) {
  const relativePath = threeVendorFiles.get(urlPath);
  if (!relativePath) {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('Vendor file not found.');
    return;
  }
  const filePath = safeJoin(threeVendorDir, relativePath);
  if (!filePath) {
    response.writeHead(403);
    response.end('Forbidden');
    return;
  }
  try {
    const content = await readFile(filePath);
    response.writeHead(200, {
      'Content-Type': contentTypeForPath(filePath),
      'Cache-Control': 'public, max-age=31536000, immutable',
    });
    response.end(content);
  } catch {
    response.writeHead(503, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('Three.js dependency is not installed. Run npm install in ZW-CAD-intent.');
  }
}

async function serveExportFile(urlPath, response, { dataRootDir = rootDir } = {}) {
  const relative = urlPath.replace(/^\/exports\//, '');
  const filePath = safeJoin(path.join(dataRootDir, 'exports'), `/${relative}`);
  if (!filePath) {
    response.writeHead(403);
    response.end('Forbidden');
    return;
  }
  try {
    const content = await readFile(filePath);
    response.writeHead(200, { 'Content-Type': contentTypeForPath(filePath) });
    response.end(content);
  } catch {
    response.writeHead(404, { 'Content-Type': 'text/plain; charset=utf-8' });
    response.end('Export file not found.');
  }
}

async function readRequestJson(request) {
  const chunks = [];
  for await (const chunk of request) chunks.push(chunk);
  const raw = Buffer.concat(chunks).toString('utf8');
  if (!raw.trim()) return {};
  return JSON.parse(raw);
}

async function acquireBodyProjectLease(body = {}, { dataRootDir } = {}) {
  const designState = body.currentDesignState || body.current_design_state || body.designState || body.design_state || {};
  const context = body.conversationContext || body.conversation_context || {};
  const projectId = normalizeTaskId(
    body.taskId || body.task_id || designState.id || context.taskId || context.task_id,
  );
  if (!projectId) return { projectId: '', leaseToken: '', expired: false };
  const leaseToken = acquireResultDirectoryLease({ rootDir: dataRootDir, resultId: projectId });
  try {
    const expired = await isExpiredResultProject({ rootDir: dataRootDir, resultId: projectId });
    return { projectId, leaseToken, expired };
  } catch (error) {
    releaseResultDirectoryLease({ rootDir: dataRootDir, resultId: projectId, leaseToken });
    throw error;
  }
}

function releaseBodyProjectLease(lease = {}, { dataRootDir } = {}) {
  if (!lease.projectId || !lease.leaseToken) return;
  releaseResultDirectoryLease({
    rootDir: dataRootDir,
    resultId: lease.projectId,
    leaseToken: lease.leaseToken,
  });
}

function sendExpiredProjectResponse(response) {
  sendJson(response, 409, {
    status: 'needs_input',
    title: '当前项目已被清理',
    message: '当前项目已超过“最近三个”保留范围，旧页面不能重新创建它。请新建项目。',
    questions: ['请新建项目后重新提交需求。'],
    blocking_reason: 'project_expired',
  });
}

function sendJson(response, statusCode, value) {
  response.writeHead(statusCode, {
    'Content-Type': 'application/json; charset=utf-8',
    'Cache-Control': 'no-store',
  });
  response.end(JSON.stringify(value, null, 2));
}

function shouldBuildRevision(route = {}) {
  return [
    'revise_requirement',
    'revise_artifact',
    'selected_hardware_enclosure',
    'provide_custom_profile',
    'change_mounting_face',
    'surface_engraving',
  ].includes(route.route_action);
}

function withRouteMetadata(body = {}, route = {}, revision = null) {
  return {
    ...body,
    conversationRoute: route,
    conversation_route: route,
    ...(route.context_transition ? { context_transition: route.context_transition } : {}),
    revisionIntent: revision,
    revision_intent: revision,
  };
}

function resetRoutedBodyForNewRequirement(body = {}, route = {}) {
  const latest = typeof body.latestUserMessage === 'string'
    ? body.latestUserMessage.trim()
    : typeof body.latest_user_message === 'string'
      ? body.latest_user_message.trim()
      : '';
  return {
    ...body,
    prompt: latest || body.prompt || '',
    selectedHardwareIds: [],
    selected_hardware_ids: [],
    userAnswers: [],
    user_answers: [],
    currentRequirementAnalysis: null,
    current_requirement_analysis: null,
    currentDesignState: null,
    current_design_state: null,
    currentArtifact: null,
    current_artifact: null,
    currentCadQueryCode: '',
    current_cadquery_code: '',
    surfaceEngravingDraft: null,
    surface_engraving_draft: null,
    surfaceEngravingTurns: [],
    surface_engraving_turns: [],
    lastNeedsInput: null,
    last_needs_input: null,
    conversationContext: {
      ...(body.conversationContext || body.conversation_context || {}),
      taskId: body.taskId || body.task_id || '',
      hasArtifact: false,
      hasDraft: false,
      hasCurrentDesignState: false,
    },
    conversationRoute: route,
    conversation_route: route,
    revisionIntent: null,
    revision_intent: null,
  };
}

function attachRouteMetadata(result, route, revision = null) {
  if (!result || typeof result !== 'object') return result;
  result.conversation_route = result.conversation_route || route;
  if (route?.context_transition) result.context_transition = result.context_transition || route.context_transition;
  if (revision) result.revision_intent = result.revision_intent || revision;
  const resolutionRoute = result.resolution_option_route || result.resolutionOptionRoute || null;
  if (result.design_state && typeof result.design_state === 'object') {
    result.design_state.conversation_route = result.design_state.conversation_route || route;
    if (revision) result.design_state.revision_intent = result.design_state.revision_intent || revision;
    if (resolutionRoute) result.design_state.resolution_option_route = result.design_state.resolution_option_route || resolutionRoute;
  }
  if (result.generation_trace && typeof result.generation_trace === 'object') {
    result.generation_trace.conversation_route = result.generation_trace.conversation_route || summarizeRoute(route);
    if (revision) result.generation_trace.revision_intent = result.generation_trace.revision_intent || summarizeRevision(revision);
    if (resolutionRoute) result.generation_trace.resolution_option_route = result.generation_trace.resolution_option_route || resolutionRoute;
  }
  return result;
}

function summarizeRoute(route = {}) {
  return {
    route_action: route.route_action || '',
    confidence: route.confidence ?? null,
    reason: route.reason || '',
    source: route.source || '',
    ...(route.context_transition ? { context_transition: route.context_transition } : {}),
  };
}

function summarizeRevision(revision = {}) {
  return {
    status: revision.status || '',
    route_action: revision.route_action || '',
    add_functions: revision.add_functions || [],
    remove_functions: revision.remove_functions || [],
    replace_hardware_roles: revision.replace_hardware_roles || [],
    remove_hardware_ids: revision.remove_hardware_ids || [],
    force_selected_hardware_ids: revision.force_selected_hardware_ids || [],
    hardware_face_overrides: revision.hardware_face_overrides || {},
    parameter_overrides: revision.parameter_overrides || {},
    surface_engraving_operations: revision.surface_engraving_operations || [],
    surface_engraving_migration: revision.surface_engraving_migration || null,
    summary: revision.summary || '',
  };
}

function safeJoin(root, urlPath) {
  const decoded = decodeURIComponent(urlPath.split('?')[0]);
  const joined = path.resolve(root, `.${decoded}`);
  const rootResolved = path.resolve(root);
  return joined === rootResolved || joined.startsWith(rootResolved + path.sep) ? joined : null;
}

function contentTypeForPath(filePath) {
  const ext = path.extname(filePath).toLowerCase();
  return {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.py': 'text/x-python; charset=utf-8',
    '.step': 'model/step',
    '.stp': 'model/step',
    '.stl': 'model/stl',
    '.gltf': 'model/gltf+json',
    '.svg': 'image/svg+xml',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.png': 'image/png',
    '.webp': 'image/webp',
  }[ext] || 'application/octet-stream';
}

function loadEnvFile(filePath) {
  if (!existsSync(filePath)) return;
  const content = readFileSync(filePath, 'utf8');
  for (const line of content.split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const index = trimmed.indexOf('=');
    if (index < 0) continue;
    const key = trimmed.slice(0, index).trim();
    const value = trimmed.slice(index + 1).trim().replace(/^['"]|['"]$/g, '');
    if (key && !(key in process.env)) process.env[key] = value;
  }
}
