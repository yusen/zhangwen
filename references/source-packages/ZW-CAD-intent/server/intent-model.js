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
      response: buildModelNeedsInput(error, { config, code: error?.code || 'llm_intent_failed', requestKind: 'intent_analysis' }),
    };
  }
}

async function requestIntentJson({ prompt, body, hardwareLibrarySummary, config }) {
  return requestChatCompletionJson({
    config,
    requestKind: 'intent_analysis',
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
    'Your current task is LLM-led requirement-function-hardware analysis: read the user natural language, extract product functions, infer required hardware roles, then match those roles against hardware_library_summary.',
        'Return ONLY a JSON object representing structured Intent, with these fields: schema_version, product_name, functions, required_hardware_roles, selected_hardware_ids, mounting_intents, enclosure_intent, user_constraints, unknowns, bom, missing_hardware_requests, analysis_feedback.',
    'The user input is prompt plus selected_hardware_ids. selected_hardware_ids means the user may already have selected parts from the hardware library.',
    'If the user asks to directly make a box/enclosure/assembly for selected hardware, keep every selected hardware id in selected_hardware_ids and make roles/functions for installing those parts.',
    'If the user asks to build a functional product using selected hardware, keep every selected hardware id and continue selecting additional hardware for uncovered functions.',
    'If selected hardware is irrelevant, redundant, or conflicts with the requested functions, keep it in selected_hardware_ids and explain the issue in user_constraints.notes or required_hardware_roles.why_needed.',
        'Use hardware_library_summary to choose concrete hardware ids only when the id exists there or is present in selected_hardware_ids.',
        'In bom, include selected or matched hardware objects with hardware_id, role, function, and why_needed. The backend will verify ids against hardware_library_summary.',
    'If a required hardware role is not covered by the library, include a required_hardware_roles item with unsupported_in_library=true, role, category, function, label, and why_needed.',
    'Also include every missing role in missing_hardware_requests with role, category, function, label, and why_needed.',
    'Do not put the rectangular box, enclosure, shell, lid, rounded corners, vents, cutouts, mounting holes, or case structure into required_hardware_roles, bom, or missing_hardware_requests.',
    'The rectangular_box_with_lid enclosure is the deterministic CAD product ZW-CAD-intent must generate, not a hardware-library part.',
    'Put enclosure shape, lid, rounded corners, vents, cutouts, openings, screw bosses, and size preferences only in enclosure_intent or user_constraints.',
        'Write analysis_feedback as a concise user-facing Chinese paragraph explaining requirement -> function -> hardware matching, selected hardware usage, extra/conflicting selected hardware, missing hardware, and next choices.',
    'Do not output CadQuery code, Python code, OpenSCAD code, final CAD coordinates, transforms, rotation matrices, or hole coordinates.',
    'Never silently simplify a complex product into a controller-only enclosure when functions or hardware are missing.',
    'Do not rename an unsupported product to a generic controller enclosure. Preserve the user-facing product name, such as night light, timer, trash bin, or other requested product.',
    'The final user-facing requirement report will contain BOM, missing hardware, and requirement-function-hardware feedback, so make the intent explicit enough to support that report.',
    'Allowed mounting target_face values: base_floor, lid_inner, front_inner.',
    'Allowed interaction_face values: top, front, left, right, back, inside.',
    'Enclosure must remain rectangular_box_with_lid for FDM 3D printing.',
    'BOM must contain only real hardware modules such as controllers, sensors, displays, buttons, batteries, actuators, and speakers.',
  ].join('\n');
}
