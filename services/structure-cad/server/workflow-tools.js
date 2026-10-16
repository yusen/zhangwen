export const WORKFLOW_TOOLS = Object.freeze([
  {
    id: 'workflow_orchestration',
    stage: 'workflow',
    kind: 'orchestration_skill',
    description: 'ZW-CAD-intent 总流程导航：说明从对话调度、需求分析、BOM、验证、profile、布局、校验到 CadQuery 导出的完整链路和分支边界。',
    input_schema: {
      conversationContext: 'object',
      prompt: 'string',
      currentDesignState: 'object|null',
      currentRequirementAnalysis: 'object|null',
      lastNeedsInput: 'object|null',
    },
    output_schema: {
      next_skill: 'string',
      allowed_actions: 'string[]',
      blocking_policy: 'string',
      reason: 'string',
    },
  },
  {
    id: 'conversation_route',
    stage: 'conversation',
    kind: 'orchestration_skill',
    description: '根据当前阶段、最新用户输入和已有任务状态，判断本轮应该确认分析、修改需求、修改方案、用选定硬件建盒或继续建模。',
    input_schema: {
      conversationContext: 'object',
      prompt: 'string',
      latestUserMessage: 'string',
      selectedHardwareIds: 'string[]',
      currentRequirementAnalysis: 'object|null',
      currentDesignState: 'object|null',
    },
    output_schema: {
      route_action: 'new_requirement|confirm_requirement_analysis|revise_requirement|revise_artifact|selected_hardware_enclosure|provide_custom_profile|change_mounting_face|build_confirmed',
      confidence: 'number',
      reason: 'string',
    },
  },
  {
    id: 'design_revision',
    stage: 'revision',
    kind: 'orchestration_skill',
    description: '把用户的修改语句转成结构化修订意图，在当前 taskId 内更新 intent、BOM 选择、安装面覆盖和参数覆盖后重算。',
    input_schema: {
      prompt: 'string',
      currentDesignState: 'object|null',
      currentRequirementAnalysis: 'object|null',
      selectedHardwareIds: 'string[]',
      hardware_library_summary: 'object[]',
    },
    output_schema: {
      add_functions: 'string[]',
      remove_functions: 'string[]',
      replace_hardware_roles: 'object[]',
      remove_hardware_ids: 'string[]',
      force_selected_hardware_ids: 'string[]',
      hardware_face_overrides: 'object',
      parameter_overrides: 'object',
    },
  },
  {
    id: 'requirement_function_selection_analysis',
    stage: 'requirement_analysis',
    kind: 'orchestration_skill',
    description: '上层需求-功能-选型分析：拆解用户需求、推导硬件角色、匹配硬件库并决定是否需要用户取舍。',
    input_schema: {
      prompt: 'string',
      selectedHardwareIds: 'string[]',
      currentDesignState: 'object|null',
      hardware_library_summary: 'object[]',
      userAnswers: 'string[]',
    },
    output_schema: {
      status: 'ok|needs_input|blocked',
      functions: 'object[]',
      available_functions: 'string[]',
      unsupported_functions: 'string[]',
      matched_hardware: 'object[]',
      missing_hardware_requests: 'object[]',
      user_message: 'string',
    },
  },
  {
    id: 'intent_analyze',
    stage: 'intent',
    description: '把用户自然语言和已有任务状态转为结构化 intent。',
    input_schema: {
      prompt: 'string',
      selectedHardwareIds: 'string[]',
      currentDesignState: 'object|null',
      userAnswers: 'string[]',
    },
    output_schema: {
      status: 'ok|needs_input',
      intent: 'object',
      questions: 'string[]',
      blocking_reason: 'string',
    },
  },
  {
    id: 'hardware_bom_select',
    stage: 'bom',
    description: '只从硬件库选择满足 intent 的 BOM。',
    input_schema: {
      intent: 'object',
      selectedHardwareIds: 'string[]',
      customHardwareProfiles: 'object[]',
    },
    output_schema: {
      status: 'ok|needs_input',
      bom: 'object[]',
      missing_hardware_requests: 'object[]',
      warnings: 'object[]',
    },
  },
  {
    id: 'function_verify',
    stage: 'bom_verification',
    description: 'LLM 验证 BOM 功能覆盖和硬件库存在性。',
    input_schema: {
      intent: 'object',
      bom: 'object[]',
      hardware_library_summary: 'object[]',
      max_attempts: 'number',
    },
    output_schema: {
      status: 'ok|needs_input',
      verification_status: 'pass|fail|blocked',
      missing_functions: 'string[]',
      missing_hardware: 'object[]',
      attempts_used: 'number',
    },
  },
  {
    id: 'profile_check',
    stage: 'profile',
    description: '检查 BOM 中硬件 profile 的尺寸、安装、开孔、避让和参考模型字段。',
    input_schema: {
      bom: 'object[]',
      customHardwareProfiles: 'object[]',
    },
    output_schema: {
      status: 'ok|needs_input',
      hardware_profiles: 'object[]',
      profile_validation_report: 'object',
    },
  },
  {
    id: 'orientation_resolve',
    stage: 'orientation',
    description: '确定硬件安装面、交互面和旋转覆盖。',
    input_schema: {
      mounting_intents: 'object[]',
      hardware_profiles: 'object[]',
      hardwareFaceOverrides: 'object',
      hardwareRotationOverrides: 'object',
    },
    output_schema: {
      status: 'ok',
      mounting_plan: 'object[]',
      oriented_hardware_specs: 'object[]',
    },
  },
  {
    id: 'box_feasibility_check',
    stage: 'feasibility',
    description: '计算盒体尺寸并检查安装面容量。',
    input_schema: {
      oriented_hardware_specs: 'object[]',
      parameters: 'object',
      user_constraints: 'object',
    },
    output_schema: {
      status: 'ok|needs_input',
      enclosure: 'object',
      capacity: 'object',
    },
  },
  {
    id: 'layout_solve',
    stage: 'layout',
    description: '生成硬件、开孔、固定结构和固定孔的位置。',
    input_schema: {
      enclosure: 'object',
      oriented_hardware_specs: 'object[]',
      parameters: 'object',
    },
    output_schema: {
      status: 'ok',
      layout_plan: 'object',
    },
  },
  {
    id: 'design_validate',
    stage: 'validation',
    description: '执行干涉、壁厚、开孔、固定结构、CadQuery 静态检查等确定性校验。',
    input_schema: {
      enclosure: 'object',
      layout_plan: 'object',
      parameters: 'object',
      cadquery_code: 'string',
    },
    output_schema: {
      status: 'ok|needs_input',
      checks: 'object[]',
      warnings: 'object[]',
      validation_context: 'object',
    },
  },
  {
    id: 'cadquery_generate',
    stage: 'cadquery',
    description: '生成确定性 CadQuery 代码和 CAD 参数。',
    input_schema: {
      enclosure: 'object',
      layout_plan: 'object',
      bom: 'object[]',
      hardware_profiles: 'object[]',
      parameters: 'object',
    },
    output_schema: {
      status: 'ok',
      cadquery_code: 'string',
      cad_parameters: 'object',
    },
  },
  {
    id: 'artifact_export',
    stage: 'artifact',
    description: '写入任务目录、2D/调试预览资产、metadata 和 8 个 workflow 产物。',
    input_schema: {
      prepared: 'object',
      taskId: 'string',
    },
    output_schema: {
      status: 'artifact|needs_input',
      design_state: 'object',
      exports: 'object[]',
    },
  },
  {
    id: 'cadquery_build',
    stage: 'cadquery_build',
    description: '运行 CadQuery 并导出真实 STL/STEP。',
    input_schema: {
      artifact: 'object',
      designId: 'string',
    },
    output_schema: {
      status: 'artifact_exports|needs_input',
      exports: 'object[]',
      mesh_validation_report: 'object',
    },
  },
]);

export function listWorkflowTools() {
  return WORKFLOW_TOOLS.map((tool) => ({ ...tool }));
}

export function getWorkflowTool(id) {
  return WORKFLOW_TOOLS.find((tool) => tool.id === id) || null;
}

export function createToolTrace(id, { input = {}, output = {}, status = '', attempts = 1 } = {}) {
  const tool = getWorkflowTool(id);
  return {
    tool_id: id,
    stage: tool?.stage || '',
    status: status || output.status || '',
    attempts,
    input_summary: summarizeToolPayload(input),
    output_summary: summarizeToolPayload(output),
  };
}

function summarizeToolPayload(value) {
  if (!value || typeof value !== 'object') return {};
  const summary = {};
  for (const [key, item] of Object.entries(value)) {
    if (Array.isArray(item)) summary[key] = { type: 'array', count: item.length };
    else if (item && typeof item === 'object') summary[key] = { type: 'object', keys: Object.keys(item).slice(0, 12) };
    else summary[key] = item;
  }
  return summary;
}
