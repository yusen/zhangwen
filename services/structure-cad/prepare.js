import { buildConversationRoute } from './server/conversation-route.js';
import { applyRevisionToBody, buildDesignRevision } from './server/design-revision.js';
import { listHardwareLibrary } from './server/hardware-library.js';
import { maybeAnalyzeIntentWithModel } from './server/intent-model.js';
import { verifyBomFunctionCoverage } from './server/function-verifier.js';
import { prepareDesign, generateDesign, buildDesignFromDraft } from './server/pipeline.js';
import { buildMergedIntentBody, buildRequirementAnalysisResponse } from './server/requirement-analysis.js';
import { applyResolutionRouteToBody, buildAmbiguousResolutionOptionResponse, routeResolutionOption } from './server/resolution-options.js';
export async function prepare(body, {rootDir,environment}) {
    const resolutionRoute = routeResolutionOption(body);
    if (resolutionRoute?.status === 'ambiguous') {
      return buildAmbiguousResolutionOptionResponse(resolutionRoute);
      return;
    }
    if (resolutionRoute?.status === 'matched') {
      body = applyResolutionRouteToBody(body, resolutionRoute);
    }
    const route = buildConversationRoute(body);
    const revision = shouldBuildRevision(route)
      ? buildDesignRevision(body, route)
      : null;
    let routedBody = revision
      ? applyRevisionToBody(body, route, revision)
      : withRouteMetadata(body, route, null);
    if (route.route_action === 'new_requirement') {
      routedBody = resetRoutedBodyForNewRequirement(routedBody, route);
    }
    if (route.route_action === 'selected_hardware_enclosure') {
      routedBody.prompt = routedBody.latestUserMessage || routedBody.latest_user_message || routedBody.prompt || routedBody.intent?.product_name || '选定硬件外壳';
      const result = await prepareDesign(routedBody, {
        rootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      attachRouteMetadata(result, route, revision);
      return result;
      return;
    }
    const modelIntentResult = await maybeAnalyzeIntentWithModel(routedBody, {
      hardwareLibrarySummary: listHardwareLibrary().profiles,
    });
    if (modelIntentResult.status === 'needs_input') {
      const result = withRouteMetadata(modelIntentResult.response, route, revision);
      return result;
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
            rootDir,
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
      return result;
      return;
    }
    if (route.route_action === 'revise_artifact') {
      const { generationBody } = buildMergedIntentBody(routedBody, modelIntentResult);
      const hasArtifact = Boolean(routedBody.conversationContext?.hasArtifact || routedBody.conversation_context?.has_artifact);
      const result = await (hasArtifact ? generateDesign : prepareDesign)(generationBody, {
        rootDir,
        environment,
        functionVerifier: verifyBomFunctionCoverage,
        hardwareLibrarySummary: listHardwareLibrary().profiles,
      });
      attachRouteMetadata(result, route, revision);
      return result;
      return;
    }
    if (route.route_action !== 'confirm_requirement_analysis') {
      const result = await buildRequirementAnalysisResponse(routedBody, modelIntentResult, { rootDir });
      attachRouteMetadata(result, route, revision);
      return result;
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
      rootDir,
      environment,
      functionVerifier: verifyBomFunctionCoverage,
      hardwareLibrarySummary: listHardwareLibrary().profiles,
    });
    attachRouteMetadata(result, route, revision);
    return result;
    return;

}
function shouldBuildRevision(route = {}) {
  return [
    'revise_requirement',
    'revise_artifact',
    'selected_hardware_enclosure',
    'provide_custom_profile',
    'change_mounting_face',
  ].includes(route.route_action);
}

function withRouteMetadata(body = {}, route = {}, revision = null) {
  return {
    ...body,
    conversationRoute: route,
    conversation_route: route,
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
    selectedHardwareIds: body.selectedHardwareIds || [],
    selected_hardware_ids: body.selectedHardwareIds || [],
    userAnswers: [],
    user_answers: [],
    currentRequirementAnalysis: null,
    current_requirement_analysis: null,
    currentDesignState: null,
    current_design_state: null,
    conversationRoute: route,
    conversation_route: route,
    revisionIntent: null,
    revision_intent: null,
  };
}

function attachRouteMetadata(result, route, revision = null) {
  if (!result || typeof result !== 'object') return result;
  result.conversation_route = result.conversation_route || route;
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
    summary: revision.summary || '',
  };
}

