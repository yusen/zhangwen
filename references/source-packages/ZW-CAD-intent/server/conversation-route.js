import { isPlainObject, normalizeString, normalizeStringArray } from './pipeline/shared.js';
import { isSurfaceEngravingPrompt } from './surface-engraving.js';
import { detectStandaloneStructuralPartsRequest, STRUCTURAL_PART_ROUTE_ACTION } from './structural-parts.js';

const ROUTE_ACTIONS = new Set([
  'new_requirement',
  'confirm_requirement_analysis',
  'revise_requirement',
  'revise_artifact',
  'selected_hardware_enclosure',
  'standalone_structural_parts',
  'provide_custom_profile',
  'change_mounting_face',
  'surface_engraving',
  'model_edit',
  'confirm_model_edit',
  'cancel_model_edit',
  'undo_model_edit',
  'build_confirmed',
]);

export function buildConversationRoute(body = {}) {
  const explicit = normalizeRouteAction(body.routeAction || body.route_action);
  const prompt = normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt);
  const context = isPlainObject(body.conversationContext) ? body.conversationContext : {};
  const stage = normalizeString(context.workflowStage || context.workflow_stage || context.currentStage || context.current_stage);
  const selectedHardwareIds = normalizeStringArray(body.selectedHardwareIds);
  const hasCurrentDesignState = isPlainObject(body.currentDesignState) || isPlainObject(body.design_state) || isPlainObject(body.designState);
  const hasDraft = Boolean(context.hasDraft || context.has_draft || (stage === 'confirming' && hasCurrentDesignState));
  const hasArtifact = Boolean(context.hasArtifact || context.has_artifact || (hasCurrentDesignState && !hasDraft));
  const hasRequirementAnalysis = Boolean(context.hasRequirementAnalysis || context.has_requirement_analysis);
  const lastNeedsInput = isPlainObject(body.lastNeedsInput)
    ? body.lastNeedsInput
    : isPlainObject(body.last_needs_input)
      ? body.last_needs_input
      : null;
  const projectSessionState = isPlainObject(body.projectSessionState)
    ? body.projectSessionState
    : isPlainObject(body.project_session_state)
      ? body.project_session_state
      : null;

  const validExplicitStructuralRoute = explicit === STRUCTURAL_PART_ROUTE_ACTION
    ? detectStandaloneStructuralPartsRequest(body).requested
    : false;
  if (explicit && (explicit !== STRUCTURAL_PART_ROUTE_ACTION || validExplicitStructuralRoute)) {
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
  const currentDesignState = isPlainObject(body.currentDesignState)
    ? body.currentDesignState
    : isPlainObject(body.design_state)
      ? body.design_state
      : isPlainObject(body.designState)
        ? body.designState
        : null;
  const currentSurfaceEngravings = Array.isArray(currentDesignState?.surface_engravings)
    ? currentDesignState.surface_engravings
    : Array.isArray(body.surfaceEngravings)
      ? body.surfaceEngravings
      : Array.isArray(body.surface_engravings)
        ? body.surface_engravings
        : [];
  const explicitSurfaceDraft = isPlainObject(body.surfaceEngravingDraft)
    ? body.surfaceEngravingDraft
    : isPlainObject(body.surface_engraving_draft)
      ? body.surface_engraving_draft
      : null;
  const lastSurfaceDraft = isPlainObject(lastNeedsInput?.surface_engraving_draft)
    ? lastNeedsInput.surface_engraving_draft
    : isPlainObject(lastNeedsInput?.surfaceEngravingDraft)
      ? lastNeedsInput.surfaceEngravingDraft
      : null;
  const pendingSurfaceDraft = explicitSurfaceDraft || lastSurfaceDraft;
  const hasPendingSurfaceEngraving = hasSurfaceEngravingDraft(explicitSurfaceDraft)
    || hasSurfaceEngravingDraft(lastSurfaceDraft)
    || String(lastNeedsInput?.blocking_reason || '').startsWith('surface_engraving_');
  const hasExistingSurfaceEngraving = currentSurfaceEngravings.length > 0;
  const hasReusableModel = hasArtifact || hasDraft || Boolean(context.hasArtifact || context.has_artifact);
  const isExplicitEngravingRequest = isSurfaceEngravingPrompt(prompt, currentSurfaceEngravings)
    || isExpandedSurfaceEngravingPrompt(prompt);
  const surfaceEngravingTransition = hasPendingSurfaceEngraving
    ? buildSurfaceEngravingToModelEditTransition()
    : null;

  const hasPendingModelEditConfirmation = isPendingModelEditConfirmation(lastNeedsInput)
    || isPendingModelEditSession(projectSessionState);
  if (hasPendingModelEditConfirmation && isModelEditConfirmation(prompt)) {
    return route('confirm_model_edit', 0.99, '用户确认执行上一轮高影响模型修改。', {
      stage,
      contextTransition: surfaceEngravingTransition,
    });
  }
  if (hasPendingModelEditConfirmation && isModelEditCancellation(prompt)) {
    return route('cancel_model_edit', 0.99, '用户取消上一轮待确认模型修改。', {
      stage,
      contextTransition: surfaceEngravingTransition,
    });
  }
  if (hasArtifact && isModelEditUndo(prompt)) {
    return route('undo_model_edit', 0.98, '用户要求撤销当前项目最近一次模型修改。', {
      stage,
      contextTransition: surfaceEngravingTransition,
    });
  }
  if (hasArtifact && isExplicitMechanicalModelEditRequest(prompt)) {
    return route('model_edit', 0.98, '已有项目，最新输入明确要求修改结构、边线、孔槽、厚度或硬件位置。', {
      stage,
      contextTransition: surfaceEngravingTransition,
    });
  }

  if (isExplicitEngravingRequest && hasReusableModel) {
    return route('surface_engraving', 0.96, '已有模型且最新输入描述了刻字增改删操作。', { stage });
  }
  if (hasPendingSurfaceEngraving
    && hasReusableModel
    && isPendingSurfaceEngravingContinuation(prompt, pendingSurfaceDraft, lastNeedsInput)) {
    return route('surface_engraving', 0.98, '正在补充或修正上一轮尚未完成的刻字要求。', { stage });
  }
  if (hasExistingSurfaceEngraving
    && hasReusableModel
    && isExistingSurfaceEngravingAdjustment(prompt)) {
    return route('surface_engraving', 0.94, '已有刻字，最新短句是在调整其字号或单行排版。', { stage });
  }
  const standaloneStructuralParts = detectStandaloneStructuralPartsRequest(body);
  if (standaloneStructuralParts.requested) {
    return route(STRUCTURAL_PART_ROUTE_ACTION, 0.96, '用户选择或明确点名了通用结构件，且没有要求生成盒子或外壳。', { stage });
  }
  if (selectedHardwareIds.length > 0 && (isSelectedHardwareEnclosureRequest(prompt) || isGenericEnclosureBuildRequest(prompt))) {
    return route('selected_hardware_enclosure', 0.94, '用户要求为当前选定硬件生成盒子。', { stage });
  }
  if (isNewRequirementRequest(prompt)) {
    return route('new_requirement', 0.9, '用户明确提出新的产品需求，重新进行需求分析。', { stage });
  }
  if (isMountingFaceChange(prompt)) {
    return route(hasArtifact ? 'model_edit' : hasDraft ? 'revise_artifact' : 'change_mounting_face', 0.9, '用户要求调整当前模型中的硬件安装面。', {
      stage,
      contextTransition: hasArtifact ? surfaceEngravingTransition : null,
    });
  }
  if (hasArtifact && isModelEditRequest(prompt)) {
    return route('model_edit', 0.9, '已有项目，最新输入是针对当前模型的自然语言修改。', {
      stage,
      contextTransition: surfaceEngravingTransition,
    });
  }
  if (hasArtifact) {
    return route('model_edit', 0.84, '已有活动项目，普通后续对话默认针对当前模型处理。', {
      stage,
      contextTransition: surfaceEngravingTransition,
    });
  }
  if (hasDraft) {
    return route('revise_artifact', 0.82, '已有草案或 artifact，非确认输入按方案修改处理。', { stage });
  }
  if (hasRequirementAnalysis || stage === 'requirement_analysis') {
    return route('revise_requirement', 0.82, '需求分析阶段收到非确认输入，按需求修改处理。', { stage });
  }
  return route('new_requirement', 0.72, '没有可复用任务上下文，按新需求分析处理。', { stage });
}

function isPendingModelEditConfirmation(value) {
  if (!isPlainObject(value)) return false;
  const explicitlyPending = value.blocking_reason === 'model_edit_confirmation'
    || value.status === 'model_edit_confirmation';
  return explicitlyPending
    && isPlainObject(value.model_edit_plan)
    && value.model_edit_plan.requires_confirmation === true;
}

function isPendingModelEditSession(value) {
  if (!isPlainObject(value)) return false;
  const activeDrafts = isPlainObject(value.active_drafts)
    ? value.active_drafts
    : isPlainObject(value.activeDrafts)
      ? value.activeDrafts
      : null;
  const pending = activeDrafts?.model_edit || activeDrafts?.modelEdit;
  return isPlainObject(pending)
    && pending.requires_confirmation === true
    && Boolean(normalizeString(pending.plan_id || pending.planId));
}

function isModelEditConfirmation(prompt = '') {
  const text = normalizeConfirmationText(prompt);
  return ['确认修改', '确认执行修改', '执行修改', '继续修改', '同意修改', '确认'].includes(text);
}

function isModelEditCancellation(prompt = '') {
  const text = normalizeConfirmationText(prompt);
  return ['取消修改', '不要修改', '放弃修改', '不改了', '取消'].includes(text);
}

function isModelEditUndo(prompt = '') {
  const text = normalizeString(prompt).replace(/[。.!！\s]/g, '');
  return /^(?:撤销|撤回|回退|恢复上一版|恢复上一个版本|回到上一版|undo)(?:刚才的?修改|上次修改)?$/i.test(text);
}

function isExplicitMechanicalModelEditRequest(prompt = '') {
  const text = normalizeString(prompt);
  if (!text) return false;
  if (isEngravingOffsetContinuation(text)) return false;
  const engravingOnNamedSurface = /(?:上盖|盖子|顶面|底壳|底面|正面|前面|背面|后面|左侧面?|右侧面?|大斜面|主斜面|L\s*形卡槽外斜面|卡槽斜面|小斜面|斜面).{0,12}(?:上的|上|表面的)?(?:刻字|文字|字样|铭文|上面的字|字)/i.test(text);
  const strongMechanicalAction = /圆角|倒圆|倒角|切角|磨圆|削平|开孔|扩孔|封孔|挖槽|加厚|减薄|移动硬件|删除结构|(?:开|打|钻|做|新增|增加|添加).{0,12}(?:孔|槽|开口)|(?:删除|删掉|移除|去掉).{0,12}(?:孔|槽口|凹槽|开口)|(?:孔|槽口|开口).{0,12}(?:加大|放大|缩小|调整|移动|封堵)|(?:凸台|台阶|卡扣|支架|加强筋|螺柱).{0,12}(?:削掉|切掉|磨掉|删除|去掉)|\b(?:fillet|chamfer)\b/i.test(text);
  if (engravingOnNamedSurface && !strongMechanicalAction) return false;

  const roundedOrChamferedEdge = /(?:倒|做|加|增加|添加|新增|改|调整|设置|设为).{0,12}(?:圆角|倒圆|圆弧角|倒角|切角|fillet|chamfer)|(?:圆角|倒圆|圆弧角|倒角|切角|fillet|chamfer).{0,12}(?:改|调整|加大|增大|缩小|设置|设为|半径|尺寸)|(?:边线|边缘|棱边).{0,16}(?:圆角|倒圆|倒角|切角|fillet|chamfer)/i;
  if (roundedOrChamferedEdge.test(text)) return true;
  const colloquialEdgeFinish = /(?:磨圆|修圆|磨成圆|修成圆|做圆|圆滑|去锐边|去掉锐边|削平|磨平).{0,16}(?:边线|边缘|棱边|顶边|底边|这个面|该面|平面|斜面)|(?:边线|边缘|棱边|顶边|底边|这个面|该面|平面|斜面).{0,16}(?:磨圆|修圆|磨成圆|修成圆|做圆|圆滑|去锐边|去掉锐边|削平|磨平)/i;
  if (colloquialEdgeFinish.test(text)) return true;
  const engravingTextTarget = /(?:刻字|文字|字样|铭文|编号|logo)/i.test(text);
  const edgeDimensionShorthand = /(?:^|[，,。；;\s])(?:R|C)\s*\d+(?:\.\d+)?(?:\s*mm|\s*毫米)?(?:$|[，,。；;\s])/i;
  const qualifiedEdgeDimensionShorthand = /(?:最高处|最低处|顶部|底部|左侧|右侧|前侧|后侧)?(?:的)?(?:边线|边缘|棱边|边).{0,12}(?:做|设为|设置为|改成|改为)?\s*(?:R|C)\s*\d+(?:\.\d+)?|(?:R|C)\s*\d+(?:\.\d+)?.{0,12}(?:边线|边缘|棱边)/i;
  const faceDimensionShorthand = /(?:给|把|将|在)?\s*(?:这个|那个|该)?\s*(?:面|平面|斜面|边|边线|边缘|棱边).{0,12}(?:做|加|设为|设置为|改成|改为)?\s*(?:R|C)\s*\d+(?:\.\d+)?(?:\s*mm|\s*毫米)?/i;
  if (!engravingTextTarget && (edgeDimensionShorthand.test(text)
    || qualifiedEdgeDimensionShorthand.test(text)
    || faceDimensionShorthand.test(text))) return true;

  const openingFeature = '(?:散热孔|通风孔|开孔|开口|按钮孔|螺丝孔|安装孔|孔径|孔位|圆孔|方孔|孔|槽口|槽|窗口)';
  const openingAction = '(?:(?<![避绕躲])开|打|钻|增加|添加|新增|扩大|扩孔|加大|放大|变大|缩小|缩径|变小|移动|移到|调整|修改|改成|改为|封上?|封闭|封堵|堵上?|删除|删掉|移除|去掉)';
  if (new RegExp(`${openingAction}.{0,16}${openingFeature}|${openingFeature}.{0,16}${openingAction}`, 'i').test(text)) return true;
  if (/(?:做|留|预留|挖|切)(?:一个|个|出)?(?:.{0,12}(?:直径|宽|长|\d+(?:\.\d+)?\s*(?:mm|毫米)))?.{0,8}(?:圆孔|方孔|孔|槽口|槽|开口|窗口)/i.test(text)) return true;

  if (/(?:壁厚|板厚|壳厚|厚度).{0,16}(?:改|调整|增加|增厚|减薄|减少|设为|设置|变成|改成|\d+(?:\.\d+)?\s*(?:mm|毫米))|(?:改|调整|增加|增厚|减薄|减少|设为|设置|变成|改成).{0,16}(?:壁厚|板厚|壳厚|厚度)/i.test(text)) return true;

  const hardwareTarget = '(?:硬件|模块|传感器|主控|控制器|开发板|电池|电源|蜂鸣器|摄像头|屏幕|显示屏|舵机|接口|USB(?:-?C)?)';
  const moveAction = '(?:移动|移到|挪动|挪到|放到|放在|装到|装在|安装到|安装在|旋转|转动|换到|调整位置|重新布置)';
  if (new RegExp(`${hardwareTarget}.{0,20}${moveAction}|${moveAction}.{0,20}${hardwareTarget}`, 'i').test(text)) return true;

  const structuralTarget = '(?:卡扣|加强筋|支架|凸台|台阶|螺柱|螺丝柱|安装柱|固定柱|底壳|上盖|盖子|主体|壳体|外壳|盒子|结构|部件)';
  const destructiveAction = '(?:删除|删掉|移除|去掉|削掉|切掉|磨掉|取消|拆掉|不要|撤掉)';
  if (/(?:删除|删掉|去掉|削掉|切掉).{0,12}(?:刻字|文字|字样|编号|logo).{0,8}(?:所在|下面|旁边|附近)(?:的)?(?:平面|斜面|面|凸台|台阶)/i.test(text)) return true;
  const structuralDeletion = new RegExp(`${destructiveAction}.{0,20}${structuralTarget}|${structuralTarget}.{0,20}${destructiveAction}`, 'i').test(text);
  if (!structuralDeletion) return false;
  if (!engravingTextTarget) return true;
  const unambiguousStructure = '(?:卡扣|加强筋|支架|凸台|台阶|螺柱|螺丝柱|安装柱|固定柱)';
  if (new RegExp(`${destructiveAction}.{0,20}${unambiguousStructure}|${unambiguousStructure}.{0,20}${destructiveAction}`, 'i').test(text)) return true;
  return false;
}

function isModelEditRequest(prompt = '') {
  const text = normalizeString(prompt);
  if (!text) return false;
  const action = /(?:改|换|调整|移动|移到|挪到|旋转|加大|缩小|加高|加宽|加长|增加|添加|新增|删除|删掉|移除|去掉|开孔|封孔|改成|变成|换成|重排|对齐|居中|分成|分两排|两行|多行|换行|undo|move|resize|rotate|add|remove|delete|replace|change)/i;
  const target = /(?:模型|项目|盒子|外壳|壳体|底壳|上盖|主体|斜面|平面|侧面|正面|背面|前面|后面|左边|右边|顶部|底部|孔|槽|开口|螺柱|卡扣|硬件|模块|传感器|主控|电池|接口|文字|刻字|字号|部件|尺寸|长度|宽度|高度|壁厚|角度|位置|这个|那个|它)/i;
  return action.test(text) && target.test(text);
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

export function isGenericEnclosureBuildRequest(prompt = '') {
  const text = normalizeString(prompt).replace(/\s+/g, '');
  if (!text || text.length > 24) return false;
  return /^(?:请|帮我)?(?:直接|开始|现在)?(?:做|生成|制作|设计|建模)(?:一个|个|下)?(?:带盖)?(?:盒子|外壳|壳|保护盒)$|^(?:盒子|外壳|壳|保护盒)(?:生成|建模|制作|设计)$|^(?:生成|制作|设计|建模)(?:盒子|外壳|壳|保护盒)$|^(?:make|build|generate|design)(?:a|an)?(?:box|case|enclosure)$/i.test(text);
}

export function isNewRequirementRequest(prompt = '') {
  const text = normalizeString(prompt);
  if (!text || isSelectedHardwareEnclosureRequest(text)) return false;
  return /(?:新项目|新任务|另一个项目|另外做一个|重新开始一个项目|我要做的(?:是|事)|我想做的(?:是|事)|需求改成|这不是当前模型|不要修改当前模型)/i.test(text);
}

export function isMountingFaceChange(prompt = '') {
  const text = normalizeString(prompt);
  return /(移到|放到|装到|安装到|放在|装在).{0,12}(底壳|底部|底板|上盖|盖子|顶部|侧面|前面|后面|左侧|右侧)|mount.*(base|lid|top|side|front|back)/i.test(text);
}

function isProfileProvision(prompt = '') {
  return /(profile|JSON|参数).{0,12}(补充|提供|粘贴|加入)|补充.{0,8}(硬件|模块).{0,8}(profile|参数)/i.test(normalizeString(prompt));
}

function hasSurfaceEngravingDraft(value) {
  if (!isPlainObject(value)) return false;
  return value.schema_version === 'surface_engraving_draft_v1'
    || Array.isArray(value.pending_operations)
    || Array.isArray(value.pendingOperations)
    || isPlainObject(value.requested_layout)
    || isPlainObject(value.requestedLayout);
}

function isExpandedSurfaceEngravingPrompt(prompt = '') {
  const text = normalizeString(prompt);
  if (!text) return false;
  if (/(?:写上|印上|标上|写到|印到|标到|写在|印在|标在)/i.test(text)) return true;
  if (/(?:字样|字号|字高|字体|铭牌|编号|logo)/i.test(text)) return true;
  return /(?:刻字|雕刻|凹刻|铭文|文字|字体|字样|编号|logo).{0,20}(?:换行|两行|二行|2\s*行|多行|分成?两排|第一行|第二行)|(?:换行|两行|二行|2\s*行|多行|分成?两排|第一行|第二行).{0,20}(?:刻字|雕刻|凹刻|铭文|文字|字体|字样|编号|logo)/i.test(text);
}

function isPendingSurfaceEngravingContinuation(prompt = '', draft = null, lastNeedsInput = null) {
  const text = normalizeString(prompt);
  if (!text || isNewRequirementRequest(text)) return false;
  if (isEngravingOffsetContinuation(text)) return true;
  if (isClearlyNonEngravingModelRevision(text)) return false;
  if (isExpandedSurfaceEngravingPrompt(text)) return true;
  if (isEngravingCancellationContinuation(text)) return true;
  if (isEngravingLayoutContinuation(text)) return true;

  const missingFields = collectSurfaceEngravingMissingFields(draft, lastNeedsInput);
  if (!missingFields.length) {
    // 兼容旧版阻断状态，但只接受形态明确的刻字参数，不再把任意短句当作刻字续答。
    return isEngravingFontContinuation(text)
      || isEngravingSurfaceContinuation(text)
      || isExplicitEngravingTextContinuation(text);
  }

  return missingFields.some((field) => {
    if (isFontHeightMissingField(field)) return isEngravingFontContinuation(text);
    if (isSurfaceOrPositionMissingField(field)) return isEngravingSurfaceContinuation(text);
    if (isEngravingTextMissingField(field)) return isEngravingTextContinuation(text);
    if (isEngravingLayoutMissingField(field)) return isEngravingLayoutContinuation(text);
    if (isTargetEngravingMissingField(field)) return isTargetEngravingContinuation(text);
    return false;
  });
}

function isEngravingCancellationContinuation(prompt = '') {
  const text = normalizeString(prompt).replace(/[。.!！\s]/g, '');
  return /^(?:取消(?:这次|当前)?刻字|这次不刻了|不刻了|放弃刻字)$/i.test(text);
}

function collectSurfaceEngravingMissingFields(draft = null, lastNeedsInput = null) {
  const candidates = [
    ...(Array.isArray(draft?.missing_fields) ? draft.missing_fields : []),
    ...(Array.isArray(draft?.missingFields) ? draft.missingFields : []),
    ...(Array.isArray(lastNeedsInput?.missing_fields) ? lastNeedsInput.missing_fields : []),
    ...(Array.isArray(lastNeedsInput?.missingFields) ? lastNeedsInput.missingFields : []),
  ];
  return [...new Set(candidates.map(normalizeString).filter(Boolean))];
}

function isFontHeightMissingField(field = '') {
  return /(?:字体高度|字高|字号|字体大小|font[_\s-]*height)/i.test(normalizeString(field));
}

function isSurfaceOrPositionMissingField(field = '') {
  return /(?:目标零件|目标外部平面|目标平面|外部平面|具体平面位置|九宫格|锚点|法向|参考点|target[_\s-]*part|normal[_\s-]*hint|point[_\s-]*hint|x[_\s-]*direction|anchor)/i.test(normalizeString(field));
}

function isEngravingTextMissingField(field = '') {
  return /(?:文字内容|刻字内容|单行文字|text)/i.test(normalizeString(field));
}

function isEngravingLayoutMissingField(field = '') {
  return /(?:排版|行数|单行|多行|换行|layout|line[_\s-]*count)/i.test(normalizeString(field));
}

function isTargetEngravingMissingField(field = '') {
  return /(?:目标刻字|哪一条刻字|哪条刻字|刻字编号|engraving[_\s-]*(?:id|target))/i.test(normalizeString(field));
}

function isEngravingSurfaceContinuation(prompt = '') {
  const text = normalizeString(prompt);
  const surface = /(?:上盖|盖子|顶面|顶部|底壳|底面|底部|正面|前面|背面|后面|左侧面?|右侧面?|侧面|大斜面|主斜面|带方孔的斜面|L\s*形卡槽外斜面|卡槽斜面|小斜面|前侧窄斜面|斜面)/i;
  const position = /(?:正中央|中央|中心|正中|左上|中上|上方中央|右上|左中|左侧中央|右中|右侧中央|左下|中下|下方中央|右下|边缘|角落)/i;
  return surface.test(text) || position.test(text);
}

function isExplicitEngravingTextContinuation(prompt = '') {
  const text = normalizeString(prompt);
  return /(?:内容|文字|字样)\s*(?:是|为|改成|换成|修改为|调整为)?\s*[：:]?\s*\S|[“"'‘][^”"'’\r\n]{1,64}[”"'’]/i.test(text);
}

function isEngravingTextContinuation(prompt = '') {
  const text = normalizeString(prompt);
  if (!text || /[\r\n]/.test(text) || [...text].length > 64) return false;
  if (isExplicitEngravingTextContinuation(text)) return true;
  if (/^(?:确认|确认修改|执行修改|继续|取消|取消修改|不要修改|放弃修改|撤销|撤回|回退|undo)$/i.test(text.replace(/[。.!！\s]/g, ''))) return false;
  return !/(?:mm|毫米|字高|字号|字体|上盖|底壳|平面|斜面|正面|背面|侧面|单行|两行|多行|换行)/i.test(text);
}

function isTargetEngravingContinuation(prompt = '') {
  const text = normalizeString(prompt);
  return /(?:编号|ID)\s*[：:]?\s*[\w.-]+|(?:文字|内容|字样)\s*(?:是|为)?\s*[：:]?\s*[“"'‘]?[^，。,.；;”"'’\r\n]{1,64}/i.test(text);
}

function isExistingSurfaceEngravingAdjustment(prompt = '') {
  const text = normalizeString(prompt);
  if (!text || isClearlyNonEngravingModelRevision(text)) return false;
  if (isEngravingOffsetContinuation(text)) return true;
  if (isEngravingLayoutContinuation(text)) return true;
  if (/^(?:把|将)?(?:它|这个|这条|上面的|刚才的|原来的)?\s*(?:改|换|调整|变大|变小)?\s*(?:成|为|到)?\s*\d+(?:\.\d+)?\s*(?:mm|毫米)$/i.test(text)) return true;
  return /^(?:改|换|调整)(?:成|为)?\s*\d+(?:\.\d+)?\s*(?:mm|毫米)$/i.test(text);
}

function isEngravingLayoutContinuation(prompt = '') {
  const text = normalizeString(prompt).replace(/\s+/g, '');
  return /(?:保持|还是|就用|改成|换成|调整为|刻成|排成|分成)?(?:单行|一行|两行|二行|2行|多行)|(?:换行|不换行|分两排|分成两排|第一行|第二行)/i.test(text);
}

function isEngravingFontContinuation(prompt = '') {
  const text = normalizeString(prompt).replace(/\s+/g, '');
  return /^(?:字高|字号|字体高度)?(?:改|换|调整)?(?:成|为|到)?\d+(?:\.\d+)?(?:mm|毫米)$/i.test(text)
    || /(?:字高|字号|字体高度).{0,8}\d+(?:\.\d+)?(?:mm|毫米)?/i.test(text);
}

function isEngravingOffsetContinuation(prompt = '') {
  const text = normalizeString(prompt);
  if (!/(?:刻字|文字|字样|铭文|编号|这条字|上面的字|刚才的字)/i.test(text)) return false;
  return /(?:向|往)?(?:左|右|上|下|前|后)(?:侧|边|方)?(?:移动|偏移|挪|调整)?\s*-?\d+(?:\.\d+)?\s*(?:mm|毫米)|(?:移动|偏移|挪动|调整位置).{0,12}-?\d+(?:\.\d+)?\s*(?:mm|毫米)|(?:避开|绕开|躲开).{0,12}(?:孔|槽|开口|边缘)/i.test(text);
}

function isClearlyNonEngravingModelRevision(prompt = '') {
  const text = normalizeString(prompt);
  if (!text) return false;
  if (isEngravingOffsetContinuation(text)) return false;
  if (isModelEditUndo(text) || isExplicitMechanicalModelEditRequest(text)) return true;
  const modelFeature = '(?:散热孔|通风孔|开孔|开口|按钮孔|螺丝孔|孔位|螺柱|螺丝柱|安装柱|卡扣|槽|窗口|支架|加强筋|硬件|模块|传感器|主控|电池|接口|USB)';
  const revisionAction = '(?:改|换|调整|移动|移到|放到|增加|添加|新增|加上?|减少|删除|移除|去掉|分两排|改成|变成|重新布置)';
  return /(?:盒子|外壳|壳体|底壳|上盖).{0,16}(?:长|宽|高|尺寸|壁厚|厚度|颜色|材质|形状|圆角|倒角|加高|加宽|加长|缩小|放大|变高|变宽|变长)|(?:长|宽|高|尺寸|壁厚|厚度|颜色|材质|形状|圆角|倒角).{0,16}(?:盒子|外壳|壳体|底壳|上盖)/i.test(text)
    || new RegExp(`${modelFeature}.{0,20}${revisionAction}|${revisionAction}.{0,20}${modelFeature}`, 'i').test(text);
}

function normalizeConfirmationText(prompt = '') {
  return normalizeString(prompt).replace(/[。.!！\s]/g, '');
}

function route(routeAction, confidence, reason, extra = {}) {
  const result = {
    route_action: routeAction,
    confidence,
    reason,
    source: 'deterministic_conversation_route',
    workflow_stage: extra.stage || '',
  };
  if (isPlainObject(extra.contextTransition)) {
    result.context_transition = extra.contextTransition;
  }
  return result;
}

function buildSurfaceEngravingToModelEditTransition() {
  return {
    from: 'surface_engraving',
    to: 'model_edit',
    action: 'supersede',
    clear_surface_engraving_draft: true,
  };
}
