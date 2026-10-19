import { guardIntent, normalizeExternalIntent } from './pipeline.js';
import {
  buildModelNeedsInput,
  getIntentModelConfig,
  requestChatCompletionJson,
} from './model-sources.js';

export { getIntentModelConfig };

export async function maybeAnalyzeIntentWithModel(body, { hardwareLibrarySummary }) {
  const config = getIntentModelConfig();
  if (!config.enabled) {
    return {
      status: 'needs_input',
      reason: 'model_not_configured',
      response: buildModelNeedsInput(new Error('LLM 未配置或未启用，无法进行需求意图分析。'), { config, code: 'llm_unavailable' }),
    };
  }
  const prompt = typeof body.prompt === 'string' ? body.prompt.trim() : '';
  if (!prompt) {
    return { status: 'skipped', reason: 'empty_prompt' };
  }

  try {
    const rawIntent = await requestIntentJson({ prompt, body, hardwareLibrarySummary, config });
    const intent = guardIntent(normalizeExternalIntent(rawIntent, {
      prompt,
      selectedHardwareIds: Array.isArray(body.selectedHardwareIds) ? body.selectedHardwareIds : [],
    }));
    return { status: 'ok', intent, source: 'model_intent' };
  } catch (error) {
    return {
      status: 'needs_input',
      reason: error instanceof Error ? error.message : String(error),
      response: buildModelNeedsInput(error, { config, code: error?.code || 'llm_intent_failed' }),
    };
  }
}

async function requestIntentJson({ prompt, body, hardwareLibrarySummary, config }) {
  return requestChatCompletionJson({
    config,
    temperature: 0.1,
    responseFormat: { type: 'json_object' },
    messages: [
      { role: 'system', content: buildSystemPrompt() },
      {
        role: 'user',
        content: JSON.stringify({
          prompt,
          selected_hardware_ids: body.selectedHardwareIds || [],
          current_design_state: body.currentDesignState || null,
          engineering_hardware_context: body.engineeringHardware || [],
          hardware_library_summary: hardwareLibrarySummary,
        }, null, 2),
      },
    ],
  });
}

function buildSystemPrompt() {
  return [
    'You are the intent_analyzer for ZW-CAD-intent.',
    'Workflow overview: conversation_route -> requirement_function_selection_analysis -> intent_analyze -> hardware_bom_select -> function_verify -> profile_check -> orientation_resolve -> box_feasibility_check -> layout_solve -> design_validate -> cadquery_generate -> artifact_export -> cadquery_build.',
    'Branching rules: design_revision handles user revisions; resolution_option_route handles blocking choices; selected_hardware_enclosure handles selected-hardware boxes; build_confirmed handles confirmed 2D drafts.',
    'Return ONLY a JSON object representing structured Intent.',
    'You may infer product functions and required hardware roles from the user prompt.',
    'Use only hardware ids that exist in hardware_library_summary or selected_hardware_ids.',
    'If a required hardware is not in the library, include a required_hardware_roles item with unsupported_in_library=true.',
    'Do not output CadQuery code, Python code, OpenSCAD code, final CAD coordinates, transforms, rotation matrices, or hole coordinates.',
    'Never silently simplify a complex product into a controller-only enclosure when functions or hardware are missing.',
    'Respect engineering_hardware_context as the current project hardware. Never substitute its controller or modules silently. If dimensions are missing, report unsupported_in_library and ask the user to provide a custom profile or explicitly select different parts.',
    'Allowed mounting target_face values: base_floor, lid_inner, front_inner.',
    'Allowed interaction_face values: top, front, left, right, back, inside.',
    'Enclosure must remain rectangular_box_with_lid for FDM 3D printing.',
  ].join('\n');
}
