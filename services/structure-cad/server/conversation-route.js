import { isPlainObject, normalizeString, normalizeStringArray } from './pipeline/shared.js';

const ROUTE_ACTIONS = new Set([
  'new_requirement',
  'confirm_requirement_analysis',
  'revise_requirement',
  'revise_artifact',
  'selected_hardware_enclosure',
  'provide_custom_profile',
  'change_mounting_face',
  'build_confirmed',
]);

export function buildConversationRoute(body = {}) {
  const explicit = normalizeRouteAction(body.routeAction || body.route_action);
  const prompt = normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt);
  const context = isPlainObject(body.conversationContext) ? body.conversationContext : {};
  const stage = normalizeString(context.workflowStage || context.workflow_stage || context.currentStage || context.current_stage);
  const selectedHardwareIds = normalizeStringArray(body.selectedHardwareIds);
  const hasCurrentDesignState = isPlainObject(body.currentDesignState) || isPlainObject(body.design_state) || isPlainObject(body.designState);
  const hasArtifact = Boolean(context.hasArtifact || context.has_artifact || hasCurrentDesignState);
  const hasDraft = Boolean(context.hasDraft || context.has_draft || (stage === 'confirming' && hasCurrentDesignState));
  const hasRequirementAnalysis = Boolean(context.hasRequirementAnalysis || context.has_requirement_analysis);

  if (explicit) {
    return route(explicit, 1, '前端显式指定 routeAction。', { stage });
  }
  if (body.requirementAnalysisConfirmed === true) {
    return route('confirm_requirement_analysis', 1, '请求体已确认需求分析。', { stage });
  }
  if (isBuildConfirmation(prompt) && hasDraft) {
    return route('build_confirmed', 0.95, '2D 草案阶段收到建模确认语句。', { stage });
  }
  if (isRequirementConfirmation(prompt) && hasRequirementAnalysis) {
    return route('confirm_requirement_analysis', 0.95, '需求分析阶段收到确认语句。', { stage });
  }
  if (isProfileProvision(prompt)) {
    return route('provide_custom_profile', 0.86, '用户提到补充 profile 或 JSON。', { stage });
  }
  if (selectedHardwareIds.length > 0 && isSelectedHardwareEnclosureRequest(prompt)) {
    return route('selected_hardware_enclosure', 0.94, '用户要求为当前选定硬件生成盒子。', { stage });
  }
  if (isNewRequirementRequest(prompt)) {
    return route('new_requirement', 0.9, '用户明确提出新的产品需求，重新进行需求分析。', { stage });
  }
  if (isMountingFaceChange(prompt)) {
    return route(hasArtifact || hasDraft ? 'revise_artifact' : 'change_mounting_face', 0.88, '用户要求调整硬件安装面。', { stage });
  }
  if (hasArtifact || hasDraft) {
    return route('revise_artifact', 0.82, '已有草案或 artifact，非确认输入按方案修改处理。', { stage });
  }
  if (hasRequirementAnalysis || stage === 'requirement_analysis') {
    return route('revise_requirement', 0.82, '需求分析阶段收到非确认输入，按需求修改处理。', { stage });
  }
  return route('new_requirement', 0.72, '没有可复用任务上下文，按新需求分析处理。', { stage });
}

export function normalizeRouteAction(value) {
  const action = normalizeString(value);
  return ROUTE_ACTIONS.has(action) ? action : '';
}

export function isRequirementConfirmation(prompt = '') {
  const text = normalizeConfirmationText(prompt);
  return [
    '确认',
    '确认分析',
    '认可',
    '认可分析',
    '继续',
    '继续预审',
    '按这个分析',
    '分析正确',
    '没问题',
    '可以',
  ].includes(text);
}

export function isBuildConfirmation(prompt = '') {
  const text = normalizeConfirmationText(prompt);
  return [
    '确认',
    '确认方案',
    '确认这个方案',
    '继续',
    '继续建模',
    '继续生成',
    '开始建模',
    '开始生成',
    '生成模型',
    '生成3D',
    '生成3d',
    '确认继续',
    '按这个方案',
    '按这个方案建模',
    '就按这个做',
    '就这样',
    '没问题继续',
    '可以',
  ].includes(text);
}

export function isSelectedHardwareEnclosureRequest(prompt = '') {
  const text = normalizeString(prompt);
  return /(选定|已选|当前|这些|所选).{0,8}(硬件|模块).{0,16}(盒子|外壳|壳|保护盒)|给.{0,6}(选定|已选|当前|这些|所选).{0,8}(硬件|模块).{0,16}(盒子|外壳|壳|保护盒)|(?:不用管|不管|不要|不需要).{0,8}(需求|功能分析|分析需求).{0,16}(硬件|模块|盒子|外壳|壳)|只用.{0,8}(硬件|模块).{0,16}(盒子|外壳|壳|保护盒)|(硬件|模块).{0,8}(直接|开始)?(生成|做|装进|安装进).{0,8}(盒子|外壳|壳|保护盒)|selected\s+hardware.*(box|enclosure|case)/i.test(text);
}

export function isNewRequirementRequest(prompt = '') {
  const text = normalizeString(prompt);
  if (!text || isSelectedHardwareEnclosureRequest(text)) return false;
  return /(我要做的(?:是|事)|我想做的(?:是|事)|其实(?:是|要做)|实际(?:是|要做)|真正(?:要做|的是)|需求(?:是|改成)|不是.{0,24}是|改成(?:做|设计|生成)|换成(?:做|设计|生成)|重新(?:做|设计|生成|分析)|新需求|做(?:一个|个|一套)?[^，。,.!?！？\n]{1,32}(?:系统|垃圾桶|设备|装置|盒子|外壳|产品|闹钟|计时器))/i.test(text);
}

export function isMountingFaceChange(prompt = '') {
  const text = normalizeString(prompt);
  return /(移到|放到|装到|安装到|放在|装在).{0,12}(底壳|底部|底板|上盖|盖子|顶部|侧面|前面|后面|左侧|右侧)|mount.*(base|lid|top|side|front|back)/i.test(text);
}

function isProfileProvision(prompt = '') {
  return /(profile|JSON|参数).{0,12}(补充|提供|粘贴|加入)|补充.{0,8}(硬件|模块).{0,8}(profile|参数)/i.test(normalizeString(prompt));
}

function normalizeConfirmationText(prompt = '') {
  return normalizeString(prompt).replace(/[。.!！\s]/g, '');
}

function route(routeAction, confidence, reason, extra = {}) {
  return {
    route_action: routeAction,
    confidence,
    reason,
    source: 'deterministic_conversation_route',
    workflow_stage: extra.stage || '',
  };
}
