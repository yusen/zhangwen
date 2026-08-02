import { createHardwareResolver } from './hardware-library.js';
import { defaultFaceForProfile, defaultInteractionFace } from './pipeline/hardware.js';
import { guardIntent } from './pipeline/intent.js';
import {
  isPlainObject,
  normalizeHardwareFaceOverrides,
  normalizeNumberMap,
  normalizeString,
  normalizeStringArray,
} from './pipeline/shared.js';

export function buildDesignRevision(body = {}, route = {}) {
  const routeAction = route.route_action || 'new_requirement';
  const prompt = normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt);
  const currentDesignState = currentDesignStateFromBody(body);
  const hardwareResolver = createHardwareResolver(body.customHardwareProfiles);
  const baseSelectedIds = normalizeStringArray(body.selectedHardwareIds);
  const selectedIds = baseSelectedIds.length
    ? baseSelectedIds
    : normalizeStringArray(currentDesignState?.bom?.map((item) => item.hardware_id));
  const revision = emptyRevision({ routeAction, prompt });

  if (routeAction === 'selected_hardware_enclosure') {
    revision.force_selected_hardware_ids = selectedIds;
    revision.selected_hardware_intent = buildSelectedHardwareIntent({
      prompt,
      selectedHardwareIds: selectedIds,
      hardwareResolver,
    });
    revision.summary = `为 ${selectedIds.length} 个已选硬件生成外壳意图。`;
  }

  applyHardwareReplacementRevision(revision, prompt);
  applyHardwareRemovalRevision(revision, prompt, selectedIds);
  applyMountingFaceRevision(revision, prompt, currentDesignState, selectedIds, hardwareResolver);
  applyParameterRevision(revision, prompt);

  revision.status = revisionHasChanges(revision) || routeAction === 'selected_hardware_enclosure'
    ? 'ok'
    : 'noop';
  return revision;
}

export function applyRevisionToBody(body = {}, route = {}, revision = buildDesignRevision(body, route)) {
  const next = {
    ...body,
    conversationRoute: route,
    conversation_route: route,
    revisionIntent: revision,
    revision_intent: revision,
  };
  const currentDesignState = currentDesignStateFromBody(body);
  const selected = new Set(normalizeStringArray(body.selectedHardwareIds));
  if (!selected.size && Array.isArray(currentDesignState?.bom)) {
    for (const item of currentDesignState.bom) {
      if (item?.hardware_id) selected.add(item.hardware_id);
    }
  }
  for (const id of revision.remove_hardware_ids || []) selected.delete(id);
  for (const id of revision.force_selected_hardware_ids || []) selected.add(id);
  next.selectedHardwareIds = [...selected];

  next.userAnswers = [
    ...normalizeStringArray(body.userAnswers),
    ...revisionUserAnswers(revision),
  ];
  next.parameterOverrides = {
    ...normalizeNumberMap(body.parameterOverrides),
    ...normalizeNumberMap(revision.parameter_overrides),
  };
  next.hardwareFaceOverrides = {
    ...normalizeHardwareFaceOverrides(currentDesignState?.hardware_face_overrides),
    ...normalizeHardwareFaceOverrides(body.hardwareFaceOverrides),
    ...normalizeHardwareFaceOverrides(revision.hardware_face_overrides),
  };

  if (revision.selected_hardware_intent) {
    next.intent = revision.selected_hardware_intent;
  } else if ((route.route_action === 'revise_artifact' || route.route_action === 'change_mounting_face') && currentDesignState?.intent) {
    next.intent = applyRevisionToIntent(currentDesignState.intent, revision, next.selectedHardwareIds);
    next.currentDesignState = currentDesignState;
    if (!next.prompt) next.prompt = currentDesignState.intent.product_name || '当前方案修改';
  } else if ((route.route_action === 'revise_requirement') && isPlainObject(body.currentRequirementAnalysis?.partial_intent)) {
    next.intent = applyRevisionToIntent(body.currentRequirementAnalysis.partial_intent, revision, next.selectedHardwareIds);
  }

  return next;
}

export function currentDesignStateFromBody(body = {}) {
  return isPlainObject(body.currentDesignState)
    ? body.currentDesignState
    : isPlainObject(body.design_state)
      ? body.design_state
      : isPlainObject(body.designState)
        ? body.designState
        : null;
}

export function buildSelectedHardwareIntent({ prompt = '', selectedHardwareIds = [], hardwareResolver = createHardwareResolver() } = {}) {
  const profiles = hardwareResolver.getHardwareProfiles(selectedHardwareIds);
  const selected = profiles.map((profile) => profile.id);
  const requiredRoles = profiles.map((profile) => ({
    role: preferredRoleForProfile(profile),
    category: profile.category,
    function: `${profile.name || profile.id} 固定与接口/交互外露`,
    label: profile.name || profile.id,
    why_needed: '用户已在硬件库中选择该硬件，并要求为选定硬件生成盒子。',
  }));
  const mountingIntents = profiles.map((profile) => ({
    hardware_id: profile.id,
    target_face: defaultFaceForProfile(profile),
    interaction_face: defaultInteractionFace(profile),
    user_phrase: '用户要求给选定硬件做盒子',
  }));
  return guardIntent({
    schema_version: '1.0',
    product_name: '选定硬件外壳',
    functions: profiles.length
      ? profiles.map((profile) => `${profile.name || profile.id} 安装固定`)
      : ['选定硬件安装固定'],
    required_hardware_roles: requiredRoles,
    selected_hardware_ids: selected,
    mounting_intents: mountingIntents,
    enclosure_intent: {
      type: 'rectangular_box_with_lid',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: 'snap_or_screw_lid',
      allowed_shape: 'rounded_rectangular_box',
    },
    user_constraints: {
      raw_prompt: prompt,
      size_mm: {},
      notes: ['selected_hardware_enclosure'],
    },
    unknowns: [],
  });
}

function emptyRevision({ routeAction, prompt }) {
  return {
    status: 'noop',
    route_action: routeAction,
    prompt,
    add_functions: [],
    remove_functions: [],
    replace_hardware_roles: [],
    remove_hardware_ids: [],
    force_selected_hardware_ids: [],
    hardware_face_overrides: {},
    parameter_overrides: {},
    summary: '',
    source: 'deterministic_design_revision',
  };
}

function applyHardwareReplacementRevision(revision, prompt) {
  const text = normalizeString(prompt);
  if (/(超声波|距离|接近).{0,12}(人体|PIR|红外|人体传感器)|把.{0,12}(超声波|距离|接近).{0,12}(改成|换成|替换为).{0,12}(人体|PIR|红外)/i.test(text)) {
    revision.remove_hardware_ids.push('grove_ultrasonic_ranger');
    revision.force_selected_hardware_ids.push('grove_digital_pir');
    revision.replace_hardware_roles.push({
      from_hardware_id: 'grove_ultrasonic_ranger',
      to_hardware_id: 'grove_digital_pir',
      role: 'proximity_sensor',
      reason: '用户要求把接近/距离检测改为人体/PIR 检测。',
    });
    revision.add_functions.push('人体/PIR 触发检测');
    revision.role_overrides = {
      ...(revision.role_overrides || {}),
      proximity_sensor: {
        role: 'motion_sensor',
        category: 'sensor',
        function: '人体/PIR 触发检测',
        label: 'Grove - Digital PIR Sensor',
        hardware_id: 'grove_digital_pir',
        why_needed: '用户要求把超声波/距离检测改为人体/PIR 检测。',
      },
      distance_sensor: {
        role: 'motion_sensor',
        category: 'sensor',
        function: '人体/PIR 触发检测',
        label: 'Grove - Digital PIR Sensor',
        hardware_id: 'grove_digital_pir',
        why_needed: '用户要求把超声波/距离检测改为人体/PIR 检测。',
      },
    };
  }
}

function applyHardwareRemovalRevision(revision, prompt, selectedIds = []) {
  const text = normalizeString(prompt);
  if (!/(删除|去掉|不要|砍掉|移除)/.test(text)) return;
  const removals = [
    [/蜂鸣器|声音|响铃|提示音/, 'grove_passive_buzzer', '声音提醒'],
    [/屏幕|OLED|显示/, 'grove_oled_096', '显示'],
    [/按钮|按键/, 'grove_button', '按钮输入'],
    [/双按钮|两个按钮|两个按键/, 'grove_dual_button', '双按钮输入'],
    [/电池|18650|供电/, 'battery_18650_holder', '电池供电'],
    [/超声波|距离/, 'grove_ultrasonic_ranger', '接近/距离检测'],
    [/人体|PIR|红外/, 'grove_digital_pir', '人体/PIR 触发检测'],
  ];
  for (const [pattern, id, fn] of removals) {
    if (pattern.test(text) && (selectedIds.includes(id) || !revision.remove_hardware_ids.includes(id))) {
      revision.remove_hardware_ids.push(id);
      revision.remove_functions.push(fn);
    }
  }
}

function applyMountingFaceRevision(
  revision,
  prompt,
  currentDesignState = null,
  selectedIds = [],
  hardwareResolver = createHardwareResolver(),
) {
  const text = normalizeString(prompt);
  const face = targetFaceFromText(text);
  if (!face) return;
  const hardwareId = hardwareIdFromText(text, currentDesignState, selectedIds, hardwareResolver);
  if (!hardwareId) return;
  revision.hardware_face_overrides[hardwareId] = face;
  revision.summary = `${hardwareId} 安装面调整为 ${face}。`;
}

function applyParameterRevision(revision, prompt) {
  const text = normalizeString(prompt);
  const size = text.match(/(?:内腔|盒子|外壳|尺寸).{0,8}(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)/);
  if (size) {
    revision.parameter_overrides.inner_length_x = Number(size[1]);
    revision.parameter_overrides.inner_width_y = Number(size[2]);
    revision.parameter_overrides.inner_height_z = Number(size[3]);
  }
  const wall = text.match(/(?:壁厚|wall).{0,6}(\d+(?:\.\d+)?)/i);
  if (wall) revision.parameter_overrides.wall_thickness = Number(wall[1]);
}

function applyRevisionToIntent(intent = {}, revision = {}, selectedHardwareIds = []) {
  const removeFunctions = new Set(normalizeStringArray(revision.remove_functions));
  const selected = new Set(normalizeStringArray(selectedHardwareIds));
  const removeIds = new Set(normalizeStringArray(revision.remove_hardware_ids));
  const roleOverrides = isPlainObject(revision.role_overrides) ? revision.role_overrides : {};
  const requiredRoles = Array.isArray(intent.required_hardware_roles)
    ? intent.required_hardware_roles
      .map((item) => {
        const override = roleOverrides[item.role];
        return override ? { ...item, ...override } : item;
      })
      .filter((item) => !removeFunctions.has(item.function || item.label || item.role))
    : [];
  for (const id of normalizeStringArray(revision.force_selected_hardware_ids)) {
    if (id === 'grove_digital_pir' && !requiredRoles.some((item) => item.role === 'motion_sensor')) {
      requiredRoles.push({
        role: 'motion_sensor',
        category: 'sensor',
        function: '人体/PIR 触发检测',
        label: 'Grove - Digital PIR Sensor',
        why_needed: '用户要求使用人体/PIR 传感器。',
      });
    }
  }
  const baseMountingIntents = Array.isArray(intent.mounting_intents)
    ? intent.mounting_intents.filter((item) => !removeIds.has(item.hardware_id))
    : [];
  const forcedMountingIntents = buildForcedMountingIntents(revision)
    .filter((item) => !baseMountingIntents.some((existing) => existing.hardware_id === item.hardware_id));
  const next = {
    ...intent,
    functions: normalizeStringArray(intent.functions).filter((fn) => !removeFunctions.has(fn)),
    selected_hardware_ids: [...selected].filter((id) => !removeIds.has(id)),
    mounting_intents: [
      ...baseMountingIntents,
      ...forcedMountingIntents,
    ],
    required_hardware_roles: requiredRoles,
  };
  for (const fn of normalizeStringArray(revision.add_functions)) {
    if (!next.functions.includes(fn)) next.functions.push(fn);
  }
  return guardIntent(next);
}

function buildForcedMountingIntents(revision = {}) {
  const result = [];
  for (const id of normalizeStringArray(revision.force_selected_hardware_ids)) {
    if (id === 'grove_digital_pir') {
      result.push({
        hardware_id: 'grove_digital_pir',
        target_face: 'lid_inner',
        interaction_face: 'front',
        user_phrase: '用户要求改用人体/PIR 传感器',
      });
    }
  }
  return result;
}

function revisionHasChanges(revision) {
  return Boolean(
    revision.add_functions.length
    || revision.remove_functions.length
    || revision.replace_hardware_roles.length
    || revision.remove_hardware_ids.length
    || revision.force_selected_hardware_ids.length
    || Object.keys(revision.hardware_face_overrides).length
    || Object.keys(revision.parameter_overrides).length
    || revision.selected_hardware_intent,
  );
}

function revisionUserAnswers(revision) {
  if (revision.status === 'noop') return [];
  const lines = [];
  if (revision.summary) lines.push(revision.summary);
  if (revision.replace_hardware_roles.length) {
    lines.push(`硬件替换：${revision.replace_hardware_roles.map((item) => `${item.from_hardware_id} -> ${item.to_hardware_id}`).join('；')}`);
  }
  if (revision.remove_functions.length) lines.push(`删除功能：${revision.remove_functions.join('、')}`);
  if (revision.add_functions.length) lines.push(`新增功能：${revision.add_functions.join('、')}`);
  return [`用户方案修改：${lines.join('；') || revision.prompt}`];
}

function preferredRoleForProfile(profile = {}) {
  if (profile.category === 'controller') return 'controller';
  if (profile.category === 'power') return 'battery';
  const roles = Array.isArray(profile.roles) ? profile.roles : [];
  return normalizeString(roles[0]) || normalizeString(profile.category) || profile.id;
}

function targetFaceFromText(text = '') {
  if (/底壳|底部|底板|base/i.test(text)) return 'base_floor';
  if (/外表面|外侧|上盖外|盖子外|顶部外|lid_outer|outside|outer/i.test(text)) return 'lid_outer';
  if (/上盖|盖子|顶部|lid|top/i.test(text)) return 'lid_inner';
  return '';
}

function hardwareIdFromText(text = '', designState = null, selectedIds = [], hardwareResolver = createHardwareResolver()) {
  const bomIds = Array.isArray(designState?.bom)
    ? designState.bom.map((item) => item?.hardware_id).filter(Boolean)
    : [];
  const scopedIds = [...new Set([...normalizeStringArray(selectedIds), ...bomIds])];
  const scopedProfiles = hardwareResolver.getHardwareProfiles(scopedIds);
  const normalizedText = normalizeString(text).toLowerCase().replace(/\s+/g, '');
  const directProfile = scopedProfiles.find((profile) => {
    const id = normalizeString(profile.id).toLowerCase().replace(/\s+/g, '');
    const name = normalizeString(profile.name).toLowerCase().replace(/\s+/g, '');
    return (id && normalizedText.includes(id)) || (name && normalizedText.includes(name));
  });
  if (directProfile) return directProfile.id;

  const scopedCategory = [
    [/主控|控制器|开发板|controller|esp32|xiao/i, 'controller'],
    [/电池|供电|电源|battery|power/i, 'power'],
    [/屏幕|显示|oled|display/i, 'display'],
    [/按钮|按键|button/i, 'button'],
    [/蜂鸣器|声音|响铃|提示音|buzzer|speaker/i, 'speaker'],
    [/传感器|sensor/i, 'sensor'],
  ].find(([pattern]) => pattern.test(text))?.[1];
  if (scopedCategory) {
    const matched = scopedProfiles.find((profile) => profile.category === scopedCategory);
    if (matched) return matched.id;
  }

  const candidates = [
    [/蜂鸣器|声音|响铃|提示音|buzzer/i, 'grove_passive_buzzer'],
    [/屏幕|OLED|显示|display/i, 'grove_oled_096'],
    [/双按钮|两个按钮|两个按键|dual/i, 'grove_dual_button'],
    [/按钮|按键|button/i, 'grove_button'],
    [/超声波|距离|ultrasonic/i, 'grove_ultrasonic_ranger'],
    [/人体|PIR|红外|pir/i, 'grove_digital_pir'],
    [/电池|18650|battery/i, 'battery_18650_holder'],
    [/主控|ESP32|XIAO|controller/i, 'xiao_esp32s3'],
  ];
  for (const [pattern, id] of candidates) {
    if (pattern.test(text)) return actualBomId(id, designState);
  }
  return '';
}

function actualBomId(preferredId, designState = null) {
  const bom = Array.isArray(designState?.bom) ? designState.bom : [];
  if (bom.some((item) => item.hardware_id === preferredId)) return preferredId;
  if (/^xiao_/.test(preferredId)) {
    const controller = bom.find((item) => /^xiao_/i.test(item.hardware_id) || item.role === 'controller');
    if (controller?.hardware_id) return controller.hardware_id;
  }
  return preferredId;
}
