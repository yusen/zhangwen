import { isPlainObject, normalizeString, normalizeStringArray } from './pipeline/shared.js';

const ACTION_ALIASES = Object.freeze({
  confirm_requirement_analysis: ['confirm_requirement_analysis'],
  ignore_missing_hardware_continue: ['ignore_missing_hardware_continue', 'remove_or_replace_feature'],
  provide_custom_hardware_profile: ['provide_custom_hardware_profile', 'complete_hardware_profile'],
  increase_box_size: ['increase_box_size', 'adjust_parameter'],
  adjust_parameter: ['adjust_parameter'],
  change_mounting_face: ['change_mounting_face'],
  remove_or_replace_hardware: ['remove_or_replace_hardware'],
  remove_or_replace_feature: ['remove_or_replace_feature', 'ignore_missing_hardware_continue'],
});

export function routeResolutionOption(body = {}) {
  const options = collectResolutionOptions(body);
  const explicitId = normalizeString(body.resolutionOptionId || body.resolution_option_id);
  if (!options.length) return null;
  if (explicitId) {
    const option = options.find((item) => normalizeString(item.id) === explicitId);
    if (option) {
      return matchedRoute(option, 1, '前端按钮明确指定 resolution option。', 'explicit_resolution_option_id');
    }
    return ambiguousRoute({
      options,
      reason: `没有找到 id 为 ${explicitId} 的处理选项。`,
      confidence: 0.1,
    });
  }

  const text = normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt);
  if (!text) return null;
  const direct = matchByIdOrActionText(text, options);
  if (direct) return direct;
  const semantic = matchBySemanticText(text, options);
  if (semantic) return semantic;
  if (isVagueOptionReply(text)) {
    return ambiguousRoute({
      options,
      reason: '用户回复太模糊，无法可靠判断要选择哪个处理方案。',
      confidence: 0.32,
    });
  }
  return null;
}

export function applyResolutionRouteToBody(body = {}, route = null) {
  if (!route || route.status !== 'matched') return body;
  const option = route.option || {};
  const action = option.action || route.action || '';
  const next = {
    ...body,
    resolutionOptionRoute: summarizeResolutionRoute(route),
    resolution_option_route: summarizeResolutionRoute(route),
  };
  const answers = normalizeStringArray(body.userAnswers);
  answers.push(`resolution_option:${option.id || route.option_id} action:${action} ${option.label || ''} ${option.description || ''}`.trim());
  if (action === 'ignore_missing_hardware_continue') {
    answers.push('ignore_missing_hardware_continue remove_or_replace_feature 忽略缺失硬件，用剩余库内硬件继续。');
    next.ignoreMissingHardware = true;
    next.ignore_missing_hardware = true;
  }
  if (action === 'ignore_missing_hardware_continue' || action === 'confirm_requirement_analysis') {
    next.routeAction = 'confirm_requirement_analysis';
    next.route_action = 'confirm_requirement_analysis';
    next.requirementAnalysisConfirmed = true;
    next.requirement_analysis_confirmed = true;
  }
  next.userAnswers = answers;
  if (option.parameter_overrides) {
    next.parameterOverrides = {
      ...(isPlainObject(body.parameterOverrides) ? body.parameterOverrides : {}),
      ...option.parameter_overrides,
    };
  }
  return next;
}

export function buildAmbiguousResolutionOptionResponse(route = {}) {
  const options = Array.isArray(route.available_options) ? route.available_options : [];
  return {
    status: 'needs_input',
    title: '需要明确处理方式',
    message: '我看到了你在回复处理选项，但还不能确定你想选哪一个。请直接点击按钮，或者明确说“忽略缺失继续 / 补充 profile / 修改需求 / 增大盒子”。',
    questions: ['请明确选择一个处理方式后继续。'],
    resolution_options: options,
    blocking_reason: 'resolution_option_ambiguous',
    resolution_option_route: summarizeResolutionRoute(route),
    source: 'deterministic_resolution_option_route',
  };
}

export function summarizeResolutionRoute(route = {}) {
  return {
    status: route.status || '',
    option_id: route.option_id || '',
    action: route.action || '',
    confidence: route.confidence ?? null,
    reason: route.reason || '',
    source: route.source || 'deterministic_resolution_option_route',
  };
}

export function collectResolutionOptions(body = {}) {
  return [
    ...normalizeOptions(body.activeResolutionOptions || body.active_resolution_options),
    ...normalizeOptions(body.lastNeedsInput?.resolution_options || body.last_needs_input?.resolution_options),
    ...normalizeOptions(body.currentRequirementAnalysis?.resolution_options || body.current_requirement_analysis?.resolution_options),
    ...normalizeOptions(body.currentDesignState?.resolution_options || body.current_design_state?.resolution_options),
  ].filter((option, index, all) => option.id && all.findIndex((item) => item.id === option.id) === index);
}

function normalizeOptions(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isPlainObject)
    .map((item) => ({
      ...item,
      id: normalizeString(item.id),
      action: normalizeString(item.action),
      label: normalizeString(item.label),
      description: normalizeString(item.description),
    }))
    .filter((item) => item.id || item.action);
}

function matchByIdOrActionText(text, options) {
  const normalized = text.toLowerCase();
  for (const option of options) {
    const candidates = [option.id, option.action].filter(Boolean).map((item) => item.toLowerCase());
    if (candidates.some((item) => item && normalized.includes(item))) {
      return matchedRoute(option, 0.96, '用户文本直接包含 option id 或 action。', 'text_id_or_action');
    }
  }
  return null;
}

function matchBySemanticText(text, options) {
  const rules = [
    {
      action: 'ignore_missing_hardware_continue',
      confidence: 0.92,
      reason: '用户要求忽略缺失硬件/砍掉不支持功能，并用剩余硬件继续。',
      pattern: /(忽略|跳过|先不管|不管|不用|不要|砍掉|删除|去掉|移除|舍弃|不做).{0,16}(缺失|不支持|没有|暂不支持|硬件|功能)|用.{0,8}(剩下|现有|已有|库内).{0,12}(继续|生成|做|建模)|继续.{0,12}(剩下|现有|已有|库内)|先做能做的|能做多少做多少/,
    },
    {
      action: 'provide_custom_hardware_profile',
      confidence: 0.9,
      reason: '用户表示要补充硬件 profile 或 JSON 参数。',
      pattern: /(补|补充|提供|粘贴|填写|添加|加入).{0,12}(profile|json|参数|尺寸|硬件)|我来.{0,8}(补|提供|填|粘贴)/i,
    },
    {
      action: 'increase_box_size',
      confidence: 0.88,
      reason: '用户允许增大或放宽盒子尺寸。',
      pattern: /(增大|放大|扩大|加大|放宽|自动扩).{0,12}(盒子|盒体|外壳|尺寸|空间|内腔)|larger|increase/i,
    },
    {
      action: 'change_mounting_face',
      confidence: 0.86,
      reason: '用户要求调整硬件安装面。',
      pattern: /(移到|放到|装到|安装到|放在|挪到).{0,16}(底壳|底部|底板|上盖|盖子|顶部|侧面|前面|后面|左侧|右侧)|mount.*(base|lid|top|side|front|back)/i,
    },
    {
      action: 'confirm_requirement_analysis',
      confidence: 0.9,
      reason: '用户确认当前分析。',
      pattern: /^(确认|确认分析|认可|可以|没问题|继续|按这个分析|分析正确)[。.!！\s]*$/,
    },
  ];
  for (const rule of rules) {
    if (!rule.pattern.test(text)) continue;
    const option = findOptionByAction(options, rule.action);
    if (option) return matchedRoute(option, rule.confidence, rule.reason, 'semantic_text');
  }
  return null;
}

function findOptionByAction(options, action) {
  const aliases = ACTION_ALIASES[action] || [action];
  return options.find((option) => aliases.includes(option.action) || aliases.includes(option.id));
}

function matchedRoute(option, confidence, reason, source) {
  return {
    status: 'matched',
    option_id: option.id || '',
    action: option.action || '',
    option,
    confidence,
    reason,
    source,
  };
}

function ambiguousRoute({ options, reason, confidence }) {
  return {
    status: 'ambiguous',
    option_id: '',
    action: '',
    confidence,
    reason,
    available_options: options,
    source: 'deterministic_resolution_option_route',
  };
}

function isVagueOptionReply(text) {
  return /^(随便吧?|都行吧?|你看着办吧?|自己决定吧?|不知道|无所谓|看情况|任选|随意|whatever)[。.!！\s]*$/i.test(text);
}
