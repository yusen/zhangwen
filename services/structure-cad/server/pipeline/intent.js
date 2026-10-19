import { createHardwareResolver } from '../hardware-library.js';
import { chooseHardwareForRole, defaultInteractionFace } from './hardware.js';
import { isPlainObject, normalizeString, normalizeStringArray } from './shared.js';

export const CODE_GUARD_PATTERNS = [
  /\bimport\s+cadquery\b/i,
  /\bcadquery\b/i,
  /\bcq\.Workplane\b/i,
  /\bdef\s+build_model\b/i,
  /\bclass\s+\w+/i,
  /```/,
];

export const FUNCTION_ROLE_RULES = [
  {
    role: 'display',
    category: 'display',
    requiredHardwareRole: 'display',
    patterns: [/oled/i, /display/i, /screen/i, /显示/, /屏幕/, /屏/],
  },
  {
    role: 'dual_button',
    category: 'button',
    requiredHardwareRole: 'dual_button',
    patterns: [/two\s*buttons?/i, /dual\s*buttons?/i, /两个.{0,4}(?:按钮|按键)/, /两颗.{0,4}(?:按钮|按键)/, /双(?:按钮|按键)/],
  },
  {
    role: 'button',
    category: 'button',
    requiredHardwareRole: 'button',
    patterns: [/button/i, /按钮/, /按键/, /按鈕/],
  },
  {
    role: 'buzzer',
    category: 'speaker',
    requiredHardwareRole: 'buzzer',
    patterns: [/buzzer/i, /beeper/i, /蜂鸣器/, /蜂鳴器/, /发声/, /报警/, /提示音/, /响铃/],
  },
  {
    role: 'temperature_humidity',
    category: 'sensor',
    requiredHardwareRole: 'temperature_humidity_sensor',
    patterns: [/temperature/i, /humidity/i, /sht4/i, /温湿度/, /温度/, /湿度/, /溫濕度/, /溫度/, /濕度/],
  },
  {
    role: 'battery',
    category: 'power',
    requiredHardwareRole: 'battery',
    patterns: [/battery/i, /18650/i, /电池/, /電池/, /供电/, /供電/],
  },
  {
    role: 'controller',
    category: 'controller',
    requiredHardwareRole: 'controller',
    patterns: [/esp32/i, /xiao/i, /主控/, /开发板/, /控制器/],
  },
  {
    role: 'ventilation',
    category: 'enclosure_feature',
    requiredHardwareRole: '',
    patterns: [/ventilation/i, /vent/i, /散热孔/, /散熱孔/, /通风孔/, /通風孔/, /散热/, /散熱/],
  },
];

export const UNSUPPORTED_HARDWARE_RULES = [
  {
    role: 'soil_moisture_sensor',
    category: 'sensor',
    function: '土壤湿度检测',
    label: '土壤湿度传感器',
    patterns: [/soil/i, /土壤湿度/, /土湿/, /土壤.*湿度/],
  },
  {
    role: 'water_pump',
    category: 'actuator',
    function: '出水控制',
    label: '水泵或电磁阀',
    patterns: [/water\s*pump/i, /pump/i, /valve/i, /水泵/, /电磁阀/, /抽水/, /出水/, /浇水/, /灌溉/],
  },
  {
    role: 'pump_driver',
    category: 'power',
    function: '水泵/阀门驱动控制',
    label: '继电器/MOSFET 驱动模块',
    patterns: [/mosfet/i, /driver/i, /relay/i, /驱动/, /继电器/, /水泵/, /电磁阀/, /抽水/, /浇水/, /灌溉/],
  },
  {
    role: 'camera',
    category: 'sensor',
    label: '摄像头',
    patterns: [/camera/i, /摄像头/, /相机/, /图像/],
  },
  {
    role: 'gps',
    category: 'sensor',
    label: 'GPS 定位模块',
    patterns: [/\bgps\b/i, /定位/],
  },
  {
    role: 'motor',
    category: 'actuator',
    label: '电机',
    patterns: [/motor/i, /电机/, /马达/],
  },
  {
    role: 'relay',
    category: 'power',
    label: '继电器',
    patterns: [/relay/i, /继电器/],
  },
  {
    role: 'camera_sensor',
    category: 'sensor',
    label: '视觉传感器',
    patterns: [/vision/i, /视觉/],
  },
];

export const PRODUCT_REQUIREMENT_RULES = [
  {
    id: 'watering_irrigation',
    productName: '智能浇花系统',
    patterns: [/智能浇花/, /自动浇水/, /浇花系统/, /自动灌溉/, /灌溉系统/, /watering/i, /irrigation/i],
    functions: ['土壤湿度检测', '出水控制', '水泵/阀门驱动控制', '系统供电'],
    supportedRoles: [
      {
        role: 'battery',
        category: 'power',
        function: '系统供电',
        why_needed: '智能浇花系统通常需要为主控和执行器预留供电方案。',
      },
    ],
    unsupportedRoles: [
      {
        role: 'soil_moisture_sensor',
        category: 'sensor',
        function: '土壤湿度检测',
        label: '土壤湿度传感器',
        why_needed: '智能浇花系统需要检测土壤湿度，但当前硬件库没有土壤湿度传感器 profile。',
      },
      {
        role: 'water_pump',
        category: 'actuator',
        function: '出水控制',
        label: '水泵或电磁阀',
        why_needed: '智能浇花系统需要控制水流输出，但当前硬件库没有水泵或电磁阀 profile。',
      },
      {
        role: 'pump_driver',
        category: 'power',
        function: '水泵/阀门驱动控制',
        label: '继电器/MOSFET 驱动模块',
        why_needed: '主控不能直接驱动水泵或阀门，需要继电器、MOSFET 或等效驱动模块，但当前硬件库没有对应 profile。',
      },
    ],
  },
  {
    id: 'smart_trash_bin',
    productName: '智能垃圾桶',
    patterns: [/智能垃圾桶/, /自动垃圾桶/, /感应垃圾桶/, /自动开盖垃圾桶/, /smart\s*(trash|garbage)\s*bin/i, /trash\s*bin/i, /garbage\s*bin/i],
    functions: ['开盖执行', '触发检测/接近检测', '主控计算', '系统供电'],
    supportedRoles: [
      {
        role: 'servo',
        category: 'actuator',
        function: '开盖执行',
        label: '舵机/开盖执行器',
        why_needed: '智能垃圾桶需要能打开或带动上盖的执行器；当前硬件库可优先尝试 MG90S 舵机。',
      },
      {
        role: 'proximity_sensor',
        category: 'sensor',
        function: '触发检测/接近检测',
        label: '接近/距离/人体触发传感器',
        why_needed: '智能垃圾桶需要检测用户靠近或投放动作，当前硬件库可优先尝试超声波或 PIR 传感器。',
      },
      {
        role: 'battery',
        category: 'power',
        function: '系统供电',
        why_needed: '智能垃圾桶通常需要为主控、传感器和舵机预留供电方案。',
      },
    ],
  },
];

export const UNSUPPORTED_SHAPE_PATTERNS = [
  /复杂曲面/,
  /任意曲面/,
  /汽车外壳/,
  /人物/,
  /雕塑/,
  /organic/i,
  /freeform/i,
];

export function intentAnalyzer({
  prompt,
  selectedHardwareIds = [],
  currentDesignState = null,
  userAnswers = [],
  hardwareResolver = createHardwareResolver(),
  originalPrompt = '',
}) {
  if (UNSUPPORTED_SHAPE_PATTERNS.some((pattern) => pattern.test(prompt))) {
    return {
      status: 'unsupported',
      response: {
        status: 'needs_input',
        title: '当前只支持带盖长方体电子外壳',
        message: '第一版 ZW-CAD-intent 只做可靠的 3D 打印电子硬件包装盒，暂不做任意曲面或复杂外观。',
        questions: [
          '是否改成带盖长方体盒子？',
          '如果不能改成长方体，是否先砍掉复杂外观需求，只保留硬件安装和开孔？',
        ],
        blocking_reason: 'unsupported_shape',
      },
    };
  }

  const selectedProfiles = hardwareResolver.getHardwareProfiles(selectedHardwareIds);
  const functions = inferFunctions(prompt, userAnswers);
  const requiredRoles = inferRequiredHardwareRoles({ prompt, functions, selectedProfiles });
  const unsupportedRoles = inferUnsupportedHardwareRoles(prompt, userAnswers);
  const allRequiredRoles = dedupeRequiredRoles([...requiredRoles, ...unsupportedRoles]);
  const selectedHardware = selectedProfiles.map((profile) => profile.id);
  const controllerIds = selectedProfiles
    .filter((profile) => profile.category === 'controller')
    .map((profile) => profile.id);
  const mentionsKnownController = /xiao|esp32|nrf52840|开发板|主控|控制器/i.test(prompt);

  const unknowns = [];
  if (!controllerIds.length && !mentionsKnownController) {
    unknowns.push({
      id: 'controller_choice',
      message: '需要一个主控，但用户没有说明或选择具体控制器。',
      options: ['从硬件库选择 XIAO ESP32S3', '从硬件库选择 XIAO nRF52840 Sense', '用户补充其他主控 profile'],
    });
  }
  if (/尺寸|大小|长|宽|高|max|最大/i.test(prompt) === false && !currentDesignState) {
    unknowns.push({
      id: 'size_preference',
      message: '用户没有给盒子尺寸偏好，程序会按硬件自动推导一版。',
      optional: true,
    });
  }

  const productName = inferProductName(originalPrompt || prompt, functions, prompt);
  const intent = {
    schema_version: '1.0',
    product_name: productName,
    functions,
    required_hardware_roles: allRequiredRoles,
    selected_hardware_ids: selectedHardware,
    mounting_intents: buildMountingIntents({ prompt, selectedProfiles, requiredRoles: allRequiredRoles, hardwareResolver }),
    enclosure_intent: {
      type: 'rectangular_box_with_lid',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: /螺丝|screw|四角/i.test(prompt) ? 'screw_lid' : 'snap_or_screw_lid',
      allowed_shape: 'rounded_rectangular_box',
    },
    user_constraints: parseUserConstraints(prompt, userAnswers),
    unknowns,
  };

  return {
    status: 'ok',
    intent,
    questions: unknowns.filter((item) => !item.optional).map((item) => item.message),
    confidence: unknowns.some((item) => !item.optional) ? 0.72 : 0.88,
  };
}

export function guardIntent(intent) {
  const text = JSON.stringify(intent);
  if (CODE_GUARD_PATTERNS.some((pattern) => pattern.test(text))) {
    throw new Error('LLM intent 中出现了 CadQuery/Python/代码片段，已拒绝。');
  }
  return intent;
}

export function normalizeExternalIntent(value, { prompt = '', selectedHardwareIds = [] } = {}) {
  const safe = stripForbiddenIntentFields(value);
  const fallback = intentAnalyzer({
    prompt,
    selectedHardwareIds,
    currentDesignState: null,
    userAnswers: [],
  }).intent;
  const normalized = {
    schema_version: normalizeString(safe.schema_version) || '1.0',
    product_name: normalizeString(safe.product_name) || fallback.product_name,
    functions: normalizeStringArray(safe.functions).length
      ? normalizeStringArray(safe.functions)
      : fallback.functions,
    required_hardware_roles: normalizeRequiredHardwareRoles(safe.required_hardware_roles).length
      ? normalizeRequiredHardwareRoles(safe.required_hardware_roles)
      : fallback.required_hardware_roles,
    selected_hardware_ids: normalizeStringArray(safe.selected_hardware_ids).length
      ? normalizeStringArray(safe.selected_hardware_ids)
      : normalizeStringArray(selectedHardwareIds),
    mounting_intents: normalizeMountingIntents(safe.mounting_intents).length
      ? normalizeMountingIntents(safe.mounting_intents)
      : fallback.mounting_intents,
    enclosure_intent: {
      type: 'rectangular_box_with_lid',
      manufacturing: 'fdm_3d_printing',
      lid_strategy: normalizeString(safe.enclosure_intent?.lid_strategy) || fallback.enclosure_intent.lid_strategy,
      allowed_shape: 'rounded_rectangular_box',
    },
    user_constraints: isPlainObject(safe.user_constraints)
      ? {
          raw_prompt: prompt,
          size_mm: isPlainObject(safe.user_constraints.size_mm) ? safe.user_constraints.size_mm : {},
          notes: normalizeStringArray(safe.user_constraints.notes),
        }
      : fallback.user_constraints,
    unknowns: Array.isArray(safe.unknowns) ? safe.unknowns.filter(isPlainObject) : fallback.unknowns,
  };
  return mergeExternalIntentWithLocalSignals(normalized, fallback);
}

export function mergeExternalIntentWithLocalSignals(externalIntent, localIntent) {
  const required = [...normalizeRequiredHardwareRoles(externalIntent.required_hardware_roles)];
  for (const localRole of normalizeRequiredHardwareRoles(localIntent.required_hardware_roles)) {
    if (required.some((item) => item.role === localRole.role)) continue;
    required.push(localRole);
  }
  const mountingById = new Map(normalizeMountingIntents(externalIntent.mounting_intents).map((item) => [item.hardware_id, item]));
  for (const localMount of normalizeMountingIntents(localIntent.mounting_intents)) {
    if (!mountingById.has(localMount.hardware_id)) mountingById.set(localMount.hardware_id, localMount);
  }
  return {
    ...externalIntent,
    functions: [...new Set([...normalizeStringArray(externalIntent.functions), ...normalizeStringArray(localIntent.functions)])],
    required_hardware_roles: required,
    mounting_intents: [...mountingById.values()],
  };
}

export function inferFunctions(prompt, userAnswers = []) {
  const functions = new Set();
  for (const rule of FUNCTION_ROLE_RULES) {
    if (rule.patterns.some((pattern) => pattern.test(prompt))) {
      if (rule.role === 'controller') continue;
      functions.add(labelFunction(rule.role));
    }
  }
  if (!userAnswersRemoveUnsupportedHardware(userAnswers)) {
    for (const preset of matchingRequirementPresets(prompt)) {
      for (const fn of preset.functions) functions.add(fn);
    }
  }
  if (/timer|clock|计时器|闹钟|时钟/i.test(prompt)) {
    functions.add('计时/显示');
    functions.add('声音提醒');
  }
  if (/温湿度/i.test(prompt)) {
    functions.add('温湿度感知');
  }
  if (/土壤湿度|土湿|soil/i.test(prompt)) {
    functions.add('土壤湿度检测');
  }
  if (/水泵|电磁阀|抽水|出水|浇水|灌溉|water\s*pump|pump|valve/i.test(prompt)) {
    functions.add('出水控制');
  }
  if (/舵机|伺服|servo|开盖|自动盖|自动开盖/i.test(prompt)) {
    functions.add('开盖执行');
  }
  if (/接近|靠近|距离|超声波|红外|感应|pir|人体|触发|proximity|distance|ultrasonic|motion/i.test(prompt)) {
    functions.add('触发检测/接近检测');
  }
  if (!functions.size) {
    if (isExplicitControllerEnclosureRequest(prompt)) {
      functions.add('主控保护和接口外露');
    } else if (isComplexProductIdea(prompt)) {
      functions.add('需求功能不明确');
    } else {
      functions.add('主控保护和接口外露');
    }
  }
  return [...functions];
}

export function inferRequiredHardwareRoles({ prompt, functions, selectedProfiles }) {
  const roles = [];
  const add = (role, category, fn, why, extra = {}) => {
    if (!roles.some((item) => item.role === role)) {
      roles.push({
        role,
        category,
        function: fn,
        why_needed: why,
        ...extra,
      });
    }
  };
  for (const rule of FUNCTION_ROLE_RULES) {
    if (rule.patterns.some((pattern) => pattern.test(prompt))) {
      if (!rule.requiredHardwareRole) continue;
      add(rule.requiredHardwareRole, rule.category, labelFunction(rule.role), `用户需求提到了 ${labelFunction(rule.role)}。`);
    }
  }
  if (/timer|clock|计时器|闹钟|时钟/i.test(prompt)) {
    add('display', 'display', '计时/显示', '计时器通常需要显示时间。');
    add('button', 'button', '用户输入', '计时器通常需要开始/停止或设置按钮。');
    add('buzzer', 'speaker', '声音提醒', '计时器通常需要蜂鸣提示。');
  }
  if (/温湿度/i.test(prompt)) {
    add('temperature_humidity_sensor', 'sensor', '温湿度感知', '温湿度盒子需要温湿度传感器。');
  }
  if (/舵机|伺服|servo|开盖|自动盖|自动开盖/i.test(prompt)) {
    add('servo', 'actuator', '开盖执行', '开盖或机械动作需要舵机/执行器。', { label: '舵机/开盖执行器' });
  }
  if (/接近|靠近|距离|超声波|红外|感应|pir|人体|触发|proximity|distance|ultrasonic|motion/i.test(prompt)) {
    add('proximity_sensor', 'sensor', '触发检测/接近检测', '自动触发需要接近、距离或人体检测传感器。', { label: '接近/距离/人体触发传感器' });
  }
  for (const preset of matchingRequirementPresets(prompt)) {
    for (const required of preset.supportedRoles || []) {
      add(required.role, required.category, required.function, required.why_needed, {
        label: required.label,
        generated_by: `requirement_preset:${preset.id}`,
      });
    }
  }
  if (functions.includes('需求功能不明确')) {
    add('requirement_clarification', 'unknown', '需求功能不明确', '用户提出了产品想法，但当前描述不足以确定需要哪些传感器、执行器或输出器。', {
      label: '需要补充功能说明',
      unsupported_in_library: true,
      generated_by: 'complex_requirement_clarification',
    });
  }
  if (!selectedProfiles.some((profile) => profile.category === 'controller')) {
    add('controller', 'controller', '主控计算', '所有电子外壳方案都需要主控或开发板。');
  }
  return roles;
}

export function inferUnsupportedHardwareRoles(prompt, userAnswers = []) {
  if (userAnswersRemoveUnsupportedHardware(userAnswers)) return [];
  const genericRoles = UNSUPPORTED_HARDWARE_RULES
    .filter((rule) => rule.patterns.some((pattern) => pattern.test(prompt)))
    .map((rule) => ({
      role: rule.role,
      category: rule.category,
      function: rule.function || rule.label,
      label: rule.label,
      why_needed: `用户需求提到了 ${rule.label}，但当前硬件库没有对应 profile。`,
      unsupported_in_library: true,
    }));
  const presetRoles = matchingRequirementPresets(prompt)
    .flatMap((preset) => (preset.unsupportedRoles || []).map((role) => ({
      ...role,
      generated_by: `requirement_preset:${preset.id}`,
      unsupported_in_library: true,
    })));
  return dedupeRequiredRoles([...genericRoles, ...presetRoles]);
}

export function userAnswersRemoveUnsupportedHardware(userAnswers = []) {
  const text = normalizeStringArray(userAnswers).join(' ');
  return /remove_or_replace_feature|砍掉|删除|去掉|不要|不做|替换/.test(text);
}

export function inferProductName(prompt, functions, analysisPrompt = prompt) {
  const extracted = extractProjectName(prompt) || extractProjectName(analysisPrompt);
  if (extracted) return extracted;
  const preset = matchingRequirementPresets(analysisPrompt)[0] || matchingRequirementPresets(prompt)[0];
  if (preset?.productName) return preset.productName;
  if (/温湿度/.test(prompt)) return '温湿度传感器盒';
  if (/计时器|timer/i.test(prompt)) return '桌面计时器';
  if (/闹钟|clock/i.test(prompt)) return '桌面闹钟';
  if (/esp32|xiao|开发板/i.test(prompt)) return '开发板外壳';
  if (isComplexProductIdea(prompt) || isComplexProductIdea(analysisPrompt)) return '用户产品想法';
  const first = functions[0] || '电子项目';
  return `${first}外壳`;
}

export function buildMountingIntents({ prompt, selectedProfiles, requiredRoles, hardwareResolver = createHardwareResolver() }) {
  const ids = new Set([
    ...selectedProfiles.map((profile) => profile.id),
    ...requiredRoles.map((role) => chooseHardwareForRole(role, {}, hardwareResolver)?.id).filter(Boolean),
  ]);
  return [...ids].map((id) => {
    const profile = hardwareResolver.getHardwareProfile(id);
    const category = profile?.category || '';
    const topInteraction = ['display', 'button', 'speaker'].includes(category);
    const frontSensor = category === 'sensor' && /前|front|朝前/i.test(prompt);
    return {
      hardware_id: id,
      target_face: category === 'controller' || category === 'power' ? 'base_floor' : 'lid_inner',
      interaction_face: frontSensor ? 'front' : topInteraction ? 'top' : defaultInteractionFace(profile),
      user_phrase: extractMountingPhrase(prompt, category),
    };
  });
}

export function parseUserConstraints(prompt, userAnswers) {
  const constraints = {
    raw_prompt: prompt,
    user_answers: userAnswers,
    size_mm: {},
  };
  const sizeMatch = prompt.match(/(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)\s*[xX×*]\s*(\d+(?:\.\d+)?)/);
  if (sizeMatch && !userAnswersRelaxMaxSize(userAnswers)) {
    constraints.size_mm.outer_max = {
      length_x: Number(sizeMatch[1]),
      width_y: Number(sizeMatch[2]),
      height_z: Number(sizeMatch[3]),
    };
  } else if (sizeMatch) {
    constraints.size_mm.relaxed_outer_max = {
      length_x: Number(sizeMatch[1]),
      width_y: Number(sizeMatch[2]),
      height_z: Number(sizeMatch[3]),
    };
  }
  return constraints;
}

export function userAnswersRelaxMaxSize(userAnswers = []) {
  const text = normalizeStringArray(userAnswers).join(' ');
  return /increase_box_size|放宽最大尺寸|允许增大|增大盒体|放宽尺寸|自动扩盒/.test(text);
}

export function labelFunction(role) {
  return {
    display: '显示',
    dual_button: '双按钮输入',
    button: '按钮输入',
    buzzer: '声音提醒',
    temperature_humidity: '温湿度感知',
    battery: '电池供电',
    controller: '主控计算',
    ventilation: '散热',
  }[role] || role;
}

export function matchingRequirementPresets(prompt = '') {
  return PRODUCT_REQUIREMENT_RULES.filter((preset) => preset.patterns.some((pattern) => pattern.test(prompt)));
}

export function isExplicitControllerEnclosureRequest(prompt = '') {
  return /(?:esp32|xiao|开发板|主控板|控制器).{0,12}(?:外壳|盒子|保护|usb|接口)|(?:外壳|盒子).{0,12}(?:esp32|xiao|开发板|主控板|控制器)|usb-c|type-c|接口外露/i.test(prompt);
}

export function isComplexProductIdea(prompt = '') {
  return /智能|系统|设备|装置|机器人|垃圾桶|浇花|浇水|灌溉|闹钟|计时器|产品|方案|smart|system|device|bin|watering/i.test(prompt)
    && !isExplicitControllerEnclosureRequest(prompt);
}

export function extractProjectName(prompt = '') {
  const text = normalizeString(prompt)
    .replace(/原始需求[:：]/g, ' ')
    .replace(/用户补充信息[:：]/g, ' ')
    .replace(/最新用户消息[:：]/g, ' ');
  const patterns = [
    /(?:我要做的(?:是|事)|我想做的(?:是|事)|其实(?:是|要做)|实际(?:是|要做)|真正(?:要做|的是)|需求(?:是|改成))\s*(?:一个|一套|个)?\s*([^，。,.!?！？\n]{2,32}?(?:系统|垃圾桶|浇花|浇水|灌溉|闹钟|计时器|设备|装置|盒子|外壳|产品))/i,
    /(?:做|制作|设计|生成|我要|想做|帮我做|给我做|create|make|build)\s*(?:一个|一套|个)?\s*([^，。,.!?！？\n]{2,32}?(?:系统|垃圾桶|浇花|浇水|灌溉|闹钟|计时器|设备|装置|盒子|外壳|产品))/i,
    /(?:做|制作|设计|生成|我要|想做|帮我做|给我做)\s*(?:一个|一套|个)?\s*(智能[^，。,.!?！？\n]{1,24})/,
    /([^，。,.!?！？\n]{2,32}?(?:智能垃圾桶|智能浇花系统|自动浇水系统|智能闹钟|桌面计时器))/i,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    const value = normalizeString(match?.[1])
      .replace(/^(一个|一套|个)/, '')
      .replace(/^(做的(?:是|事)|要做的(?:是|事)|是|需求(?:是|改成)|改成|换成|重新做)/, '')
      .trim();
    if (/智能浇花$/.test(value)) return '智能浇花系统';
    if (value) return value;
  }
  if (/智能垃圾桶/.test(text)) return '智能垃圾桶';
  if (/智能浇花|浇花系统|自动浇水|自动灌溉|灌溉系统/.test(text)) return '智能浇花系统';
  return '';
}

export function dedupeRequiredRoles(roles = []) {
  const seen = new Set();
  const result = [];
  for (const role of roles) {
    const key = `${role.role || ''}:${role.category || ''}`;
    if (seen.has(key)) continue;
    seen.add(key);
    result.push(role);
  }
  return result;
}

export function extractMountingPhrase(prompt, category) {
  if (category === 'sensor' && /朝前|前面|front/i.test(prompt)) return '传感器开孔朝前';
  if (category === 'display' && /上面|顶部|top/i.test(prompt)) return '显示交互面在顶部';
  return '';
}

export function normalizeRequiredHardwareRoles(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isPlainObject)
    .map((item) => ({
      role: normalizeString(item.role || item.hardware_role),
      category: normalizeString(item.category),
      function: normalizeString(item.function || item.function_name),
      label: normalizeString(item.label || item.hardware_label || item.name),
      why_needed: normalizeString(item.why_needed) || '由 intent 分析得出。',
      unsupported_in_library: Boolean(item.unsupported_in_library),
      generated_by: normalizeString(item.generated_by),
    }))
    .filter((item) => item.role && item.category);
}

export function normalizeMountingIntents(value) {
  if (!Array.isArray(value)) return [];
  return value
    .filter(isPlainObject)
    .map((item) => ({
      hardware_id: normalizeString(item.hardware_id),
      target_face: normalizeAllowedTargetFace(item.target_face),
      interaction_face: normalizeAllowedInteractionFace(item.interaction_face),
      user_phrase: normalizeString(item.user_phrase || item.description),
    }))
    .filter((item) => item.hardware_id);
}

export function normalizeAllowedTargetFace(value) {
  const text = normalizeString(value);
  return ['base_floor', 'lid_inner', 'front_inner'].includes(text) ? text : '';
}

export function normalizeAllowedInteractionFace(value) {
  const text = normalizeString(value);
  return ['top', 'front', 'left', 'right', 'back', 'inside'].includes(text) ? text : '';
}

export function stripForbiddenIntentFields(value) {
  if (!isPlainObject(value)) return {};
  const forbidden = new Set([
    'code',
    'cadquery_code',
    'python_code',
    'scad_code',
    'openscad_code',
    'cad_coordinates',
    'final_coordinates',
    'rotation_matrix',
    'transforms',
    'hardware_transforms',
    'opening_transforms',
    'mounting_transforms',
  ]);
  const result = {};
  for (const [key, item] of Object.entries(value)) {
    if (forbidden.has(key)) continue;
    if (Array.isArray(item)) {
      result[key] = item.map((child) => stripForbiddenIntentFields(child));
    } else if (isPlainObject(item)) {
      result[key] = stripForbiddenIntentFields(item);
    } else {
      result[key] = item;
    }
  }
  return result;
}
