import { mkdir, readdir, readFile, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import {
  addUserCustomHardwareProfile,
  getHardwareProfile,
  removeUserCustomHardwareProfile,
} from './hardware-library.js';
import {
  buildModelNeedsInput,
  getIntentModelConfig,
  requestChatCompletionJson,
} from './model-sources.js';
import {
  findInvalidProfileFields,
  validateProfileContract,
} from './pipeline/hardware.js';

const USER_CUSTOM_SYSTEM = 'user_custom';
const VALID_CUSTOM_TYPES = new Set(['electronic', 'structural']);
const EXTERNAL_INDEPENDENT_MODE = 'external_independent_module';
const RUN_TIMEOUT_MS = 90000;
const CUSTOM_PREVIEW_PREFIX = 'custom_hardware_preview_';
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

export async function previewCustomHardware(body = {}, context = {}) {
  const normalized = normalizeCustomHardwareRequest(body);
  const missingInput = findMissingDescriptionInput(normalized);
  if (missingInput.length) {
    return buildNeedsInputResponse({
      normalized,
      missing: missingInput,
      feedback: `还缺少这些关键信息：${missingInput.join('、')}。补齐后再点“预览”。`,
    });
  }

  const llmResult = context.generateCustomHardwareWithLlm
    ? await context.generateCustomHardwareWithLlm(normalized)
    : await generateCustomHardwareWithLlm(normalized);
  const draft = llmResult.status === 'ok'
    ? normalizeLlmDraft(llmResult.draft, normalized)
    : buildFallbackDraft(normalized, llmResult);
  const previewIssues = validateCustomHardwarePreviewDraft(draft);
  const commitIssues = validateCustomHardwareDraft(draft);
  const publicCommitIssues = describeCustomHardwareIssues(commitIssues);
  if (previewIssues.length) {
    return buildNeedsInputResponse({
      normalized,
      missing: previewIssues,
      feedback: draft.user_feedback || `当前描述还不能预览，缺少：${previewIssues.join('、')}。`,
      draft,
      llm_status: llmResult.status,
    });
  }

  const preview = await buildCustomHardwarePreview({
    rootDir: context.rootDir,
    python: context.python,
    environment: context.environment,
    draft,
    runPreviewCommand: context.runPreviewCommand,
  });
  const previewReady = preview.status === 'artifact_exports' && hasUsablePreviewStl(preview.exports);
  return {
    status: previewReady ? 'custom_hardware_preview' : 'needs_input',
    blocking_reason: previewReady ? '' : preview.blocking_reason || 'custom_hardware_preview_failed',
    title: '用户自定义硬件预览',
    message: previewReady
      ? sanitizeCustomHardwareFeedback(draft.user_feedback || '已生成自定义硬件预览，请检查中心画布模型。', publicCommitIssues)
      : (preview.message || '自定义硬件预览未生成，请检查中心画布提示。'),
    user_feedback: previewReady ? sanitizeCustomHardwareFeedback(draft.user_feedback || '', publicCommitIssues) : '',
    missing_fields: previewReady ? [] : describeCustomHardwareIssues([preview.message || preview.blocking_reason || '预览生成失败']),
    custom_hardware_type: normalized.custom_hardware_type,
    profile_draft: draft.profile,
    cadquery_code: draft.cadquery_code,
    source: 'custom_hardware_builder',
    llm_status: llmResult.status,
    llm_reason: llmResult.reason || '',
    preview_artifact: preview.artifact || null,
    exports: preview.exports || [],
    commit_ready: previewReady && commitIssues.length === 0,
    commit_missing_fields: publicCommitIssues,
    checks: [
      {
        id: 'custom_hardware_profile_contract',
        label: '用户自定义硬件 Profile',
        status: commitIssues.length ? 'pending' : 'pass',
        message: commitIssues.length
          ? `草案可预览，但写入前还缺少：${publicCommitIssues.join('、')}`
          : 'profile 草稿满足写入硬件库所需的最小字段。',
      },
      ...(preview.checks || []),
    ],
  };
}

async function previewCustomHardwareLegacy(body = {}, context = {}) {
  const normalized = normalizeCustomHardwareRequest(body);
  const missingInput = findMissingDescriptionInput(normalized);
  if (missingInput.length) {
    return buildNeedsInputResponse({
      normalized,
      missing: missingInput,
      feedback: `还缺少这些关键信息：${missingInput.join('、')}。补齐后再点“预览”。`,
    });
  }

  const llmResult = await generateCustomHardwareWithLlm(normalized);
  const draft = llmResult.status === 'ok'
    ? normalizeLlmDraft(llmResult.draft, normalized)
    : buildFallbackDraft(normalized, llmResult);
  const issues = validateCustomHardwareDraft(draft);
  if (issues.length) {
    return buildNeedsInputResponse({
      normalized,
      missing: issues,
      feedback: draft.user_feedback || `当前描述还不能提交，缺少：${issues.join('、')}。`,
      draft,
      llm_status: llmResult.status,
    });
  }

  const preview = await buildCustomHardwarePreview({
    rootDir: context.rootDir,
    python: context.python,
    environment: context.environment,
    draft,
    runPreviewCommand: context.runPreviewCommand,
  });
  const previewReady = preview.status === 'artifact_exports' && hasUsablePreviewStl(preview.exports);
  return {
    status: previewReady ? 'custom_hardware_preview' : 'needs_input',
    blocking_reason: previewReady ? '' : preview.blocking_reason || 'custom_hardware_preview_failed',
    title: '用户自定义硬件预览',
    message: previewReady
      ? sanitizeCustomHardwareFeedback(draft.user_feedback || '已生成自定义硬件预览，请检查中心画布模型。')
      : (preview.message || '自定义硬件预览未生成，请检查中心画布提示。'),
    user_feedback: previewReady ? sanitizeCustomHardwareFeedback(draft.user_feedback || '') : '',
    missing_fields: previewReady ? [] : describeCustomHardwareIssues([preview.message || preview.blocking_reason || '预览生成失败']),
    custom_hardware_type: normalized.custom_hardware_type,
    profile_draft: draft.profile,
    cadquery_code: draft.cadquery_code,
    source: 'custom_hardware_builder',
    llm_status: llmResult.status,
    llm_reason: llmResult.reason || '',
    preview_artifact: preview.artifact || null,
    exports: preview.exports || [],
    checks: [
      {
        id: 'custom_hardware_profile_contract',
        label: '自定义硬件 Profile',
        status: 'pass',
        message: 'profile 草案满足写入硬件库所需的最小字段。',
      },
      ...(preview.checks || []),
    ],
  };
}

export async function commitCustomHardware(body = {}, context = {}) {
  const profile = prepareUserCustomProfileForCommit(normalizeProfileForCommit(body.profile || body.profile_draft));
  const cadqueryCode = normalizeString(body.cadquery_code || body.cadqueryCode);
  const thumbnailDataUrl = normalizeString(body.thumbnail_data_url || body.thumbnailDataUrl);
  const issues = validateCustomHardwareDraft({ profile, cadquery_code: cadqueryCode });
  if (issues.length) {
    const publicIssues = describeCustomHardwareIssues(issues);
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_profile_incomplete',
      message: `自定义硬件还不能提交，缺少或无效：${publicIssues.join('、')}。`,
      missing_fields: publicIssues,
      source: 'custom_hardware_builder',
    };
  }
  const getProfile = context.getHardwareProfile || getHardwareProfile;
  const addProfile = context.addUserCustomHardwareProfile || addUserCustomHardwareProfile;
  if (getProfile(profile.id)) {
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_id_exists',
      message: `硬件 id 已存在：${profile.id}`,
      missing_fields: ['id 已存在，请换一个硬件名称或重新生成。'],
      source: 'custom_hardware_builder',
    };
  }

  const modelRelativePath = `server/data/hardware-models/${profile.id}.py`;
  const modelPath = path.join(context.rootDir, 'server', 'data', 'hardware-models', `${profile.id}.py`);
  const thumbnailRelativeUrl = `/assets/hardware/${profile.id}.png`;
  const thumbnailPath = path.join(context.rootDir, 'public', 'assets', 'hardware', `${profile.id}.png`);
  const committedProfile = {
    ...profile,
    hardware_system: USER_CUSTOM_SYSTEM,
    custom_hardware_type: normalizeCustomHardwareType(profile.custom_hardware_type),
    cadquery_model: {
      format: 'cadquery_python',
      path: modelRelativePath,
      entrypoint: 'result',
      source_skill: 'custom_hardware_builder',
      status: 'user_confirmed',
    },
    source_status: '用户自定义硬件，已确认写入硬件库',
    thumbnail_url: thumbnailRelativeUrl,
  };

  await mkdir(path.dirname(modelPath), { recursive: true });
  await writeFile(modelPath, cadqueryCode, 'utf8');
  if (thumbnailDataUrl) {
    await mkdir(path.dirname(thumbnailPath), { recursive: true });
    await writeFile(thumbnailPath, decodePngDataUrl(thumbnailDataUrl));
  } else {
    await ensureFallbackThumbnail(thumbnailPath, committedProfile);
  }
  const storedProfile = await addProfile(committedProfile);
  return {
    status: 'custom_hardware_committed',
    title: '用户自定义硬件已写入',
    message: `${committedProfile.name} 已加入“用户自定义硬件 / ${customTypeLabel(committedProfile.custom_hardware_type)}”。`,
    profile: storedProfile,
    selected_hardware_id: committedProfile.id,
    source: 'custom_hardware_builder',
    files: {
      model: modelPath,
      thumbnail: thumbnailPath,
      library: path.join(context.rootDir, 'server', 'data', 'hardware-library.json'),
    },
  };
}

export async function deleteCustomHardware(id, context = {}) {
  const profileId = normalizeString(id).toLowerCase();
  if (!profileId || !profileId.startsWith('user_custom_')) {
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_delete_forbidden',
      message: '只能删除用户自定义硬件库中的硬件。',
      source: 'custom_hardware_builder',
    };
  }
  const getProfile = context.getHardwareProfile || getHardwareProfile;
  const profile = getProfile(profileId);
  if (!profile) {
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_not_found',
      message: `未找到用户自定义硬件：${profileId}`,
      source: 'custom_hardware_builder',
    };
  }
  if (profile.hardware_system !== USER_CUSTOM_SYSTEM) {
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_delete_forbidden',
      message: '只能删除用户自定义硬件库中的硬件。',
      source: 'custom_hardware_builder',
    };
  }

  const removeProfile = context.removeUserCustomHardwareProfile || removeUserCustomHardwareProfile;
  const removedProfile = await removeProfile(profileId);
  const deleted_files = await deleteUserCustomHardwareFiles(context.rootDir, profileId);
  return {
    status: 'custom_hardware_deleted',
    title: '用户自定义硬件已删除',
    message: `${removedProfile.name || profileId} 已从用户自定义硬件库中删除。`,
    deleted_hardware_id: profileId,
    deleted_files,
    source: 'custom_hardware_builder',
  };
}

async function commitCustomHardwareLegacy(body = {}, context = {}) {
  const profile = normalizeProfileForCommit(body.profile || body.profile_draft);
  const cadqueryCode = normalizeString(body.cadquery_code || body.cadqueryCode);
  const thumbnailDataUrl = normalizeString(body.thumbnail_data_url || body.thumbnailDataUrl);
  const issues = validateCustomHardwareDraft({ profile, cadquery_code: cadqueryCode });
  if (issues.length) {
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_profile_incomplete',
      message: `自定义硬件还不能提交，缺少或无效：${issues.join('、')}。`,
      missing_fields: issues,
      source: 'custom_hardware_builder',
    };
  }
  const getProfile = context.getHardwareProfile || getHardwareProfile;
  const addProfile = context.addUserCustomHardwareProfile || addUserCustomHardwareProfile;
  if (getProfile(profile.id)) {
    return {
      status: 'needs_input',
      blocking_reason: 'custom_hardware_id_exists',
      message: `硬件 id 已存在：${profile.id}`,
      missing_fields: ['id 已存在，请换一个硬件名称或重新生成。'],
      source: 'custom_hardware_builder',
    };
  }

  const modelRelativePath = `server/data/hardware-models/${profile.id}.py`;
  const modelPath = path.join(context.rootDir, 'server', 'data', 'hardware-models', `${profile.id}.py`);
  const thumbnailRelativeUrl = `/assets/hardware/${profile.id}.png`;
  const thumbnailPath = path.join(context.rootDir, 'public', 'assets', 'hardware', `${profile.id}.png`);
  const committedProfile = {
    ...profile,
    hardware_system: USER_CUSTOM_SYSTEM,
    custom_hardware_type: normalizeCustomHardwareType(profile.custom_hardware_type),
    cadquery_model: {
      ...(profile.cadquery_model || {}),
      format: 'cadquery_python',
      path: modelRelativePath,
      entrypoint: 'result',
      source_skill: 'custom_hardware_builder',
      status: 'user_confirmed',
    },
    source_status: '用户自定义硬件，已确认写入硬件库',
    thumbnail_url: thumbnailRelativeUrl,
  };

  await mkdir(path.dirname(modelPath), { recursive: true });
  await writeFile(modelPath, cadqueryCode, 'utf8');
  if (thumbnailDataUrl) {
    await mkdir(path.dirname(thumbnailPath), { recursive: true });
    await writeFile(thumbnailPath, decodePngDataUrl(thumbnailDataUrl));
  } else {
    await ensureFallbackThumbnail(thumbnailPath, committedProfile);
  }
  const storedProfile = await addProfile(committedProfile);
  return {
    status: 'custom_hardware_committed',
    title: '用户自定义硬件已写入',
    message: `${committedProfile.name} 已加入“用户自定义硬件 / ${customTypeLabel(committedProfile.custom_hardware_type)}”。`,
    profile: storedProfile,
    selected_hardware_id: committedProfile.id,
    source: 'custom_hardware_builder',
    files: {
      model: modelPath,
      thumbnail: thumbnailPath,
      library: path.join(context.rootDir, 'server', 'data', 'hardware-library.json'),
    },
  };
}

function normalizeCustomHardwareRequest(body = {}) {
  return {
    name: normalizeString(body.name || body.hardware_name || body.hardwareName),
    custom_hardware_type: normalizeCustomHardwareType(body.custom_hardware_type || body.customHardwareType || body.type),
    description: normalizeString(body.description || body.prompt || body.message),
    conversation: Array.isArray(body.conversation) ? body.conversation : [],
    thumbnail_data_url: normalizeString(body.thumbnail_data_url || body.thumbnailDataUrl),
  };
}

function findMissingDescriptionInput(input) {
  const missing = [];
  if (!input.name) missing.push('硬件名称');
  if (!VALID_CUSTOM_TYPES.has(input.custom_hardware_type)) missing.push('电子器件/结构件类型');
  if (!input.description) missing.push('自然语言描述');
  if (!/(\d+(?:\.\d+)?)\s*(mm|毫米|cm|厘米)/i.test(input.description)) missing.push('至少一个明确尺寸');
  if (!hasExplicitIndependentMountingIntent(input.description)
    && !/(固定|安装|孔|螺丝|卡槽|贴|外部|内部|底面|上盖|侧面|无需固定|不固定)/i.test(input.description)) {
    missing.push('安装或固定方式');
  }
  return missing;
}

async function generateCustomHardwareWithLlm(input) {
  const config = getIntentModelConfig();
  if (!config.enabled) {
    return { status: 'fallback', reason: 'llm_not_configured' };
  }
  try {
    const skillText = await readCustomHardwareSkill();
    const draft = await requestChatCompletionJson({
      config,
      requestKind: 'custom_hardware_builder',
      temperature: 0.1,
      responseFormat: { type: 'json_object' },
      messages: [
        {
          role: 'system',
          content: [
            '你是 ZW-CAD-intent 的用户自定义硬件建模助手。',
            '必须遵守以下 skill，不要输出 Markdown，只返回 JSON。',
            skillText,
          ].join('\n\n'),
        },
        {
          role: 'user',
          content: JSON.stringify({
            hardware_name: input.name,
            custom_hardware_type: input.custom_hardware_type,
            description: input.description,
            conversation: input.conversation,
            required_output: {
              status: 'ok|needs_input',
              user_feedback: '中文，说明已识别的信息或缺失项',
              missing_fields: [],
              profile: {},
              cadquery_code: 'single CQ-editor runnable Python code defining result',
            },
          }, null, 2),
        },
      ],
    });
    return { status: 'ok', draft };
  } catch (error) {
    return {
      status: 'fallback',
      reason: error instanceof Error ? error.message : String(error),
      needs_input_response: buildModelNeedsInput(error, { config, code: error?.code || 'custom_hardware_llm_failed', requestKind: 'custom_hardware_builder' }),
    };
  }
}

async function readCustomHardwareSkill() {
  try {
    return await readFile(path.join(__dirname, '..', 'skills', 'custom_hardware_builder', 'SKILL.md'), 'utf8');
  } catch {
    return [
      '电子器件必须描述尺寸、主体、安装方式、开孔/接口/避让。',
      '结构件必须描述用途、尺寸、连接/固定方式、孔槽/卡扣和打印约束。',
      '如果缺少关键尺寸或固定方式，返回 needs_input。',
      '如果信息完整，返回 profile 和 cadquery_code。',
    ].join('\n');
  }
}

function normalizeLlmDraft(rawDraft, input) {
  if (!rawDraft || typeof rawDraft !== 'object') return buildFallbackDraft(input);
  if (rawDraft.status === 'needs_input') {
    const missingFields = describeCustomHardwareIssues(Array.isArray(rawDraft.missing_fields) ? rawDraft.missing_fields : []);
    return {
      user_feedback: sanitizeCustomHardwareFeedback(normalizeString(rawDraft.user_feedback || rawDraft.message), missingFields),
      missing_fields: missingFields,
      profile: normalizeProfileForCommit(rawDraft.profile || {}),
      cadquery_code: normalizeString(rawDraft.cadquery_code),
    };
  }
  const profile = normalizeProfileForCommit(rawDraft.profile || {});
  const missingFields = describeCustomHardwareIssues(Array.isArray(rawDraft.missing_fields) ? rawDraft.missing_fields : []);
  return {
    user_feedback: sanitizeCustomHardwareFeedback(normalizeString(rawDraft.user_feedback || rawDraft.message) || '已根据描述生成自定义硬件模型草案。', missingFields),
    missing_fields: missingFields,
    profile: completeGeneratedProfile(profile, input),
    cadquery_code: normalizeString(rawDraft.cadquery_code) || buildFallbackCadQueryCode(completeGeneratedProfile(profile, input)),
  };
}

function buildFallbackDraft(input, llmResult = {}) {
  const dimensions = inferDimensions(input.description);
  const category = input.custom_hardware_type === 'structural' ? 'structure' : 'custom_electronic';
  const independent = hasExplicitIndependentMountingIntent(input.description);
  const profile = completeGeneratedProfile({
    id: makeCustomHardwareId(input.name),
    name: input.name,
    category,
    roles: input.custom_hardware_type === 'structural'
      ? ['custom_structural_part', 'structure']
      : ['custom_electronic_part', 'hardware'],
    dimensions_mm: dimensions,
    coordinate_system: {
      origin: 'hardware_body_center',
      x_axis: 'length direction',
      y_axis: 'width direction',
      positive_z: 'front or component side',
    },
    mounting: independent
      ? buildIndependentMountingProfile()
      : {
          mode: 'base_floor_custom_mount',
          mating_hardware_face: '-Z',
          preferred_enclosure_surface: 'base_floor',
          clearance_mm: 0.8,
          retainer_height_mm: 1.2,
          holes: [],
          fixed_structure: {
            type: 'custom_retainer_or_mount',
            source: 'inferred_from_user_description',
          },
        },
    opening: [],
    keepouts: [],
    cad_reference: {
      shape: input.custom_hardware_type === 'structural' ? 'custom_structural_part' : 'custom_electronic_module',
      color: input.custom_hardware_type === 'structural' ? '#d7dde2' : '#2f855a',
    },
    source_status: '用户自定义硬件预览草案',
  }, input);
  return {
    user_feedback: llmResult.reason === 'llm_not_configured'
      ? '当前 LLM 未配置，已先根据描述中的尺寸生成基础预览。确认写入前建议补充更多细节。'
      : 'LLM 暂不可用，已根据描述中的尺寸生成基础预览。你可以继续补充细节后再次预览。',
    missing_fields: [],
    profile,
    cadquery_code: buildFallbackCadQueryCode(profile),
  };
}

function completeGeneratedProfile(profile, input) {
  const id = makeCustomHardwareId(profile.id || input.name);
  const independent = hasExplicitIndependentMountingIntent(input.description);
  const customHardwareType = input.custom_hardware_type;
  return {
    ...profile,
    id,
    name: normalizeString(profile.name) || input.name,
    category: normalizeString(profile.category) || (input.custom_hardware_type === 'structural' ? 'structure' : 'custom_electronic'),
    roles: Array.isArray(profile.roles) && profile.roles.length ? profile.roles : [input.custom_hardware_type === 'structural' ? 'custom_structural_part' : 'custom_electronic_part'],
    hardware_system: USER_CUSTOM_SYSTEM,
    custom_hardware_type: customHardwareType,
    model_type: customHardwareType === 'structural' ? 'structural_part' : 'electronic_component',
    dimensions_mm: profile.dimensions_mm || inferDimensions(input.description),
    coordinate_system: profile.coordinate_system || {
      origin: 'hardware_body_center',
      x_axis: 'length direction',
      y_axis: 'width direction',
      positive_z: 'front or component side',
    },
    mounting: independent
      ? buildIndependentMountingProfile(profile.mounting)
      : profile.mounting || {
          mode: 'base_floor_custom_mount',
          mating_hardware_face: '-Z',
          preferred_enclosure_surface: 'base_floor',
          clearance_mm: 0.8,
          retainer_height_mm: 1.2,
          holes: [],
        },
    opening: independent ? [] : (Array.isArray(profile.opening) ? profile.opening : []),
    keepouts: independent ? [] : (Array.isArray(profile.keepouts) ? profile.keepouts : []),
    cad_reference: profile.cad_reference || { shape: 'custom_hardware', color: '#4f9a94' },
    cadquery_model: {
      format: 'cadquery_python',
      path: `server/data/hardware-models/${id}.py`,
      entrypoint: 'result',
      source_skill: 'custom_hardware_builder',
      status: 'preview',
      ...(profile.cadquery_model || {}),
    },
    source_status: normalizeString(profile.source_status) || '用户自定义硬件预览草案',
    thumbnail_url: profile.thumbnail_url || `/assets/hardware/${id}.png`,
  };
}

function prepareUserCustomProfileForCommit(profile = {}) {
  const id = makeCustomHardwareId(profile.id || profile.name);
  const customType = normalizeCustomHardwareType(profile.custom_hardware_type);
  const validCustomType = VALID_CUSTOM_TYPES.has(customType) ? customType : 'electronic';
  return {
    ...profile,
    id,
    hardware_system: USER_CUSTOM_SYSTEM,
    custom_hardware_type: validCustomType,
    model_type: validCustomType === 'structural' ? 'structural_part' : 'electronic_component',
    cadquery_model: {
      format: 'cadquery_python',
      path: `server/data/hardware-models/${id}.py`,
      entrypoint: 'result',
      source_skill: 'custom_hardware_builder',
      status: 'preview',
    },
    source_status: normalizeString(profile.source_status) || '用户自定义硬件预览草稿',
    thumbnail_url: `/assets/hardware/${id}.png`,
  };
}

function hasExplicitIndependentMountingIntent(value) {
  const text = normalizeString(value).replace(/[\s，。；、,.!！?？]/g, '');
  if (!text) return false;
  return /(?:独立|单独)(?:放置|存在|使用|摆放|建模)/i.test(text)
    || /(?:不需要|无需|不要|不必)(?:固定|安装)(?!间隙)(?:到|在)?(?:盒子|盒体|外壳)?/i.test(text)
    || /(?:不固定|不安装)(?:到|在)?(?:盒子|盒体|外壳)?/i.test(text)
    || /(?:不需要|无需|不要|不必|不)(?:与|和)(?:盒子|盒体|外壳)(?:进行)?(?:任何)?(?:连接|固定|安装|贴合)/i.test(text);
}

function buildIndependentMountingProfile(mounting = {}) {
  const source = mounting && typeof mounting === 'object' ? mounting : {};
  const {
    mating_hardware_face: _matingHardwareFace,
    preferred_enclosure_surface: _preferredEnclosureSurface,
    retainer_height_mm: _retainerHeight,
    holes: _holes,
    fixed_structure: _fixedStructure,
    ...rest
  } = source;
  return {
    ...rest,
    mode: EXTERNAL_INDEPENDENT_MODE,
    clearance_mm: 0,
    holes: [],
    fixed_structure: {
      type: EXTERNAL_INDEPENDENT_MODE,
      source: 'explicit_user_description',
      placement_rule: '独立存在，不与盒体连接，不生成盒体固定结构或安装间隙。',
    },
  };
}

function validateCustomHardwarePreviewDraft(draft = {}) {
  const issues = [];
  const profile = draft.profile || {};
  if (!normalizeString(profile.id)) issues.push('id');
  if (!normalizeString(profile.name)) issues.push('name');
  if (!VALID_CUSTOM_TYPES.has(profile.custom_hardware_type)) issues.push('custom_hardware_type');
  if (profile.hardware_system !== USER_CUSTOM_SYSTEM) issues.push('hardware_system');
  const dimensions = profile.dimensions_mm || {};
  for (const field of ['length_x', 'width_y', 'height_z']) {
    if (!(Number(dimensions[field]) > 0)) issues.push(`dimensions_mm.${field}`);
  }
  if (!normalizeString(draft.cadquery_code)) issues.push('cadquery_code');
  if (!/import\s+cadquery\s+as\s+cq/.test(draft.cadquery_code || '')) issues.push('cadquery_code.import cadquery as cq');
  if (!/\bresult\s*=/.test(draft.cadquery_code || '')) issues.push('cadquery_code.result');
  if (!/show_object\s*\(/.test(draft.cadquery_code || '')) issues.push('cadquery_code.show_object');
  return [...new Set(issues)];
}

function validateCustomHardwareDraft(draft = {}) {
  const issues = [];
  const profile = draft.profile || {};
  if (!VALID_CUSTOM_TYPES.has(profile.custom_hardware_type)) issues.push('custom_hardware_type');
  if (profile.hardware_system !== USER_CUSTOM_SYSTEM) issues.push('hardware_system');
  issues.push(...findInvalidProfileFields(profile));
  if (!profile.cadquery_model || typeof profile.cadquery_model !== 'object') issues.push('cadquery_model');
  if (!normalizeString(draft.cadquery_code)) issues.push('cadquery_code');
  if (!/import\s+cadquery\s+as\s+cq/.test(draft.cadquery_code || '')) issues.push('cadquery_code.import cadquery as cq');
  if (!/\bresult\s*=/.test(draft.cadquery_code || '')) issues.push('cadquery_code.result');
  if (!/show_object\s*\(/.test(draft.cadquery_code || '')) issues.push('cadquery_code.show_object');
  const contract = validateProfileContract(profile);
  for (const [category, values] of Object.entries(contract)) {
    if (category === 'manufacturing_pending') continue;
    issues.push(...values);
  }
  return [...new Set(issues)];
}

async function buildCustomHardwarePreview({ rootDir, python, environment, draft, runPreviewCommand = runPython }) {
  if (!rootDir || !python) {
    return { status: 'pending', blocking_reason: 'custom_hardware_preview_context_missing', message: '缺少预览运行环境。' };
  }
  if (!environment?.cadqueryAvailable) {
    return {
      status: 'pending',
      blocking_reason: 'pending_missing_cadquery',
      message: '当前 Python 环境未检测到 cadquery/OCP，无法执行真实 CadQuery 预览。',
      artifact: buildPreviewArtifact(draft, []),
      exports: [],
    };
  }
  const buildId = `custom_hardware_preview_${draft.profile.id}_${Date.now()}`;
  const exportDir = path.join(rootDir, 'exports', buildId);
  await mkdir(exportDir, { recursive: true });
  const sourcePath = path.join(exportDir, 'cadquery.py');
  const runnerPath = path.join(exportDir, 'run-custom-hardware-export.py');
  const stepPath = path.join(exportDir, 'model.step');
  const stlPath = path.join(exportDir, 'model.stl');
  await writeFile(sourcePath, draft.cadquery_code, 'utf8');
  await writeFile(runnerPath, buildSingleResultRunner({ sourcePath, stepPath, stlPath }), 'utf8');
  const cleanupReport = await cleanupCustomHardwarePreviewDirectories({ rootDir, keepCount: 3 });
  const cleanupChecks = buildCustomHardwarePreviewCleanupChecks(cleanupReport);
  const syntaxResult = await runPreviewCommand(python, ['-m', 'py_compile', sourcePath], { cwd: exportDir, timeoutMs: RUN_TIMEOUT_MS });
  if (syntaxResult.exitCode !== 0) {
    const errorSummary = summarizePythonFailure(syntaxResult.stderr || syntaxResult.stdout);
    return {
      status: 'fail',
      blocking_reason: 'custom_hardware_cadquery_syntax_failed',
      message: `自定义硬件 CadQuery 代码语法检查失败：${errorSummary}`,
      stdout: syntaxResult.stdout,
      stderr: syntaxResult.stderr,
      error_summary: errorSummary,
      artifact: buildPreviewArtifact(draft, []),
      exports: [],
      checks: [
        buildCadQueryFailureCheck('custom_hardware_cadquery_syntax', 'CadQuery 语法检查', errorSummary),
        ...cleanupChecks,
      ],
    };
  }
  const result = await runPreviewCommand(python, [runnerPath], { cwd: exportDir, timeoutMs: RUN_TIMEOUT_MS });
  if (result.exitCode !== 0) {
    const errorSummary = summarizePythonFailure(result.stderr || result.stdout);
    return {
      status: 'fail',
      blocking_reason: 'custom_hardware_cadquery_execution_failed',
      message: `自定义硬件 CadQuery 执行失败：${errorSummary}`,
      stdout: result.stdout,
      stderr: result.stderr,
      error_summary: errorSummary,
      artifact: buildPreviewArtifact(draft, []),
      exports: [],
      checks: [
        buildCadQueryFailureCheck('custom_hardware_cadquery_execution', 'CadQuery 执行', errorSummary),
        ...cleanupChecks,
      ],
    };
  }
  const stlReady = await fileIsNonEmpty(stlPath);
  const stepReady = await fileIsNonEmpty(stepPath);
  if (!stlReady) {
    return {
      status: 'fail',
      blocking_reason: 'custom_hardware_cadquery_export_missing_stl',
      message: '自定义硬件 CadQuery 已执行，但没有生成可加载的 STL 预览文件。',
      stdout: result.stdout,
      stderr: result.stderr,
      error_summary: summarizePythonFailure(result.stderr || result.stdout) || '没有生成 model.stl。',
      artifact: buildPreviewArtifact(draft, []),
      exports: [],
      checks: [
        buildCadQueryFailureCheck('custom_hardware_cadquery_export', 'CadQuery 导出', '没有生成可加载的 STL 预览文件。'),
        ...cleanupChecks,
      ],
    };
  }
  const exports = [
    {
      id: 'cadquery_stl',
      label: '自定义硬件 STL 预览',
      format: 'stl',
      url: `/exports/${buildId}/model.stl`,
      path: stlPath,
      fidelity: 'cadquery',
    },
    ...(stepReady ? [{
      id: 'cadquery_step',
      label: '自定义硬件 STEP 预览',
      format: 'step',
      url: `/exports/${buildId}/model.step`,
      path: stepPath,
      fidelity: 'cadquery',
    }] : []),
  ];
  return {
    status: 'artifact_exports',
    message: '自定义硬件预览已生成。',
    artifact: buildPreviewArtifact(draft, exports),
    exports,
    checks: [
      {
        id: 'custom_hardware_cadquery_preview',
        label: 'CadQuery 预览',
        status: 'pass',
        message: '模型代码已成功导出 STL/STEP 预览。',
      },
      ...cleanupChecks,
    ],
  };
}

function buildCadQueryFailureCheck(id, label, errorSummary) {
  return {
    id,
    label,
    status: 'fail',
    message: errorSummary,
  };
}

async function cleanupCustomHardwarePreviewDirectories({ rootDir, keepCount = 3 } = {}) {
  const exportsDir = path.join(rootDir || '', 'exports');
  const report = {
    status: 'ok',
    keep_count: keepCount,
    kept: [],
    deleted: [],
    failed: [],
  };
  if (!rootDir) {
    return {
      ...report,
      status: 'warn',
      error: { message: 'rootDir is required for custom hardware preview cleanup.' },
    };
  }

  try {
    await mkdir(exportsDir, { recursive: true });
    const entries = await readdir(exportsDir, { withFileTypes: true });
    const previewDirs = [];
    for (const entry of entries) {
      if (!entry.isDirectory() || !entry.name.startsWith(CUSTOM_PREVIEW_PREFIX)) continue;
      const fullPath = path.join(exportsDir, entry.name);
      const resolvedExports = path.resolve(exportsDir);
      const resolvedTarget = path.resolve(fullPath);
      if (!resolvedTarget.startsWith(`${resolvedExports}${path.sep}`)) continue;
      const info = await stat(fullPath);
      previewDirs.push({
        name: entry.name,
        path: fullPath,
        mtimeMs: info.mtimeMs,
      });
    }

    previewDirs.sort((a, b) => b.mtimeMs - a.mtimeMs || b.name.localeCompare(a.name));
    report.kept = previewDirs.slice(0, keepCount).map((item) => item.name);
    for (const item of previewDirs.slice(keepCount)) {
      try {
        await rm(item.path, { recursive: true, force: true });
        report.deleted.push(item.name);
      } catch (error) {
        report.failed.push({
          name: item.name,
          path: item.path,
          error: serializeCustomHardwareCleanupError(error),
        });
      }
    }
    if (report.failed.length) report.status = 'warn';
    return report;
  } catch (error) {
    return {
      ...report,
      status: 'warn',
      error: serializeCustomHardwareCleanupError(error),
    };
  }
}

function buildCustomHardwarePreviewCleanupChecks(report = {}) {
  if (!report || report.status === 'ok') return [];
  return [{
    id: 'custom_hardware_preview_cleanup_warn',
    label: '自定义硬件临时预览清理',
    status: 'warn',
    message: '自定义硬件临时预览目录清理未完全完成，预览结果不受影响。',
    details: report,
  }];
}

function serializeCustomHardwareCleanupError(error) {
  if (!error || typeof error !== 'object') return { message: String(error || 'unknown cleanup error') };
  return {
    name: error.name || 'Error',
    code: typeof error.code === 'string' ? error.code : '',
    path: typeof error.path === 'string' ? error.path : '',
    message: error instanceof Error ? error.message : String(error),
  };
}

function summarizePythonFailure(text = '') {
  const normalized = String(text || '')
    .replace(/\r/g, '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean);
  if (!normalized.length) return '未返回详细错误。';
  const cannotFindSolid = normalized.find((line) => /Cannot find a solid on the stack/i.test(line));
  if (cannotFindSolid) {
    return `${cannotFindSolid}。通常是 CadQuery 操作顺序错误，例如在实体生成前调用 fillet/edges/vertices，请先生成 solid 再倒角或开孔。`;
  }
  const syntaxLine = normalized.find((line) => /SyntaxError|IndentationError|TabError/i.test(line));
  if (syntaxLine) return syntaxLine;
  const exceptionLine = [...normalized].reverse().find((line) => /(?:Error|Exception):/i.test(line));
  if (exceptionLine) return exceptionLine;
  return normalized.slice(-3).join(' | ').slice(0, 600);
}

function buildPreviewArtifact(draft, exports) {
  return {
    status: 'artifact',
    source: 'custom_hardware_builder',
    cadquery_code: draft.cadquery_code,
    exports,
    bom: [{
      hardware_id: draft.profile.id,
      name: draft.profile.name,
      role: draft.profile.category,
      profile_status: 'preview',
      quantity: 1,
    }],
    design_state: {
      id: `custom_hardware_${draft.profile.id}`,
      source: 'custom_hardware_builder',
      intent: {
        product_name: draft.profile.name,
        hardware_system: USER_CUSTOM_SYSTEM,
      },
      hardware_profiles: [draft.profile],
      layout_plan: {
        hardware_transforms: [],
        openings: [],
      },
    },
    checks: [],
  };
}

async function fileIsNonEmpty(filePath) {
  try {
    const info = await stat(filePath);
    return info.isFile() && info.size > 0;
  } catch {
    return false;
  }
}

async function deleteUserCustomHardwareFiles(rootDir, profileId) {
  if (!rootDir || !profileId?.startsWith('user_custom_')) return [];
  const paths = [
    path.join(rootDir, 'server', 'data', 'hardware-models', `${profileId}.py`),
    path.join(rootDir, 'public', 'assets', 'hardware', `${profileId}.png`),
    path.join(rootDir, 'public', 'assets', 'hardware', `${profileId}.svg`),
  ];
  const deleted = [];
  for (const filePath of paths) {
    try {
      await rm(filePath, { force: true });
      deleted.push(filePath);
    } catch {
      // Best-effort cleanup only; the library profile removal is the source of truth.
    }
  }
  return deleted;
}

function hasUsablePreviewStl(exports = []) {
  return Array.isArray(exports)
    && exports.some((item) => item?.id === 'cadquery_stl' && item.url && item.status !== 'failed');
}

function buildSingleResultRunner({ sourcePath, stepPath, stlPath }) {
  return `import os
import runpy
import sys

source_path = ${JSON.stringify(sourcePath)}
source_dir = os.path.dirname(os.path.abspath(source_path))
original_sys_path = list(sys.path)
sys.path = [item for item in sys.path if item and os.path.abspath(item) != source_dir]
import cadquery as cq
from cadquery import exporters
sys.path = original_sys_path

def show_object(*args, **kwargs):
    return None

ns = runpy.run_path(source_path, init_globals={"show_object": show_object})
result = ns.get("result")
if result is None:
    raise RuntimeError("cadquery.py must define result")
exporters.export(result, ${JSON.stringify(stepPath)})
exporters.export(result, ${JSON.stringify(stlPath)})
print("exported")
`;
}

function buildFallbackCadQueryCode(profile) {
  const d = profile.dimensions_mm || {};
  const color = profile.cad_reference?.color || '#4f9a94';
  return `import cadquery as cq

hardware_name = ${JSON.stringify(profile.name)}
length_x = ${safeNumber(d.length_x, 20)}
width_y = ${safeNumber(d.width_y, 20)}
height_z = ${safeNumber(d.height_z, 5)}

body = cq.Workplane("XY").box(length_x, width_y, height_z).translate((0, 0, height_z / 2))
result = body

show_object(result, name=hardware_name, options={"color": ${JSON.stringify(color)}})
`;
}

function inferDimensions(text) {
  const numbers = [...String(text || '').matchAll(/(\d+(?:\.\d+)?)\s*(mm|毫米|cm|厘米)?/gi)]
    .map((match) => {
      const value = Number(match[1]);
      const unit = String(match[2] || 'mm').toLowerCase();
      return /cm|厘米/.test(unit) ? value * 10 : value;
    })
    .filter((value) => Number.isFinite(value) && value > 0);
  return {
    length_x: numbers[0] || 30,
    width_y: numbers[1] || numbers[0] || 20,
    height_z: numbers[2] || 5,
  };
}

function makeCustomHardwareId(value) {
  const raw = normalizeString(value) || 'custom_hardware';
  const ascii = raw
    .normalize('NFKD')
    .replace(/[^\w\s-]+/g, '')
    .trim()
    .replace(/[\s-]+/g, '_')
    .toLowerCase();
  const fallback = [...raw].map((char) => char.charCodeAt(0).toString(36)).join('_').slice(0, 40);
  const slug = ascii || fallback || 'custom_hardware';
  return slug.startsWith('user_custom_') ? slug : `user_custom_${slug}`;
}

function normalizeProfileForCommit(profile = {}) {
  return profile && typeof profile === 'object' ? { ...profile } : {};
}

function normalizeCustomHardwareType(value) {
  const text = normalizeString(value).toLowerCase();
  if (['electronic', 'electronics', '电子器件', '电子硬件', '电子'].includes(text)) return 'electronic';
  if (['structural', 'structure', '结构件', '结构'].includes(text)) return 'structural';
  return text;
}

function customTypeLabel(value) {
  return value === 'structural' ? '结构件' : '电子器件';
}

function describeCustomHardwareIssues(issues = []) {
  const items = Array.isArray(issues) ? issues : [issues];
  return [...new Set(items.map(describeCustomHardwareIssue).filter(Boolean))];
}

function describeCustomHardwareIssue(issue) {
  const text = normalizeString(issue);
  if (!text) return '';
  const ordinal = issueOrdinalText(text);
  if (/mounting\.clearance_mm/.test(text)) {
    return '还需要说明固定结构与外壳或安装面之间预留多少安装间隙，单位 mm。';
  }
  if (/mounting\.preferred_enclosure_surface/.test(text)) {
    return '还需要说明这个硬件默认固定在盒子的哪个位置，例如底部、上盖内侧或上盖外侧。';
  }
  if (/mounting\.mating_hardware_face/.test(text)) {
    return '还需要说明硬件本体的哪一面贴合外壳或固定结构，例如底面、背面或侧面。';
  }
  if (/mounting\.holes(?:\[\d+\]|\[\])?\.(?:x|y)/.test(text)) {
    return `还需要说明${ordinal}固定孔相对硬件中心的 X/Y 坐标，单位 mm。`;
  }
  if (/mounting\.holes(?:\[\d+\]|\[\])?\.diameter_mm|mounting\.hole_diameter/.test(text)) {
    return `还需要说明${ordinal}固定孔的直径，单位 mm。`;
  }
  if (/mounting\.holes(?:\[\d+\])?$|mounting\.holes$/.test(text)) {
    return '还需要说明固定孔数量、每个孔相对硬件中心的位置和孔径，单位 mm。';
  }
  if (/mounting\.retainer_height_mm/.test(text)) {
    return '还需要说明卡槽、限位条或托台的高度，单位 mm。';
  }
  if (/dimensions_mm\.length_x/.test(text)) {
    return '还需要说明硬件主体沿 X 方向的长度，单位 mm。';
  }
  if (/dimensions_mm\.width_y/.test(text)) {
    return '还需要说明硬件主体沿 Y 方向的宽度，单位 mm。';
  }
  if (/dimensions_mm\.height_z/.test(text)) {
    return '还需要说明硬件主体沿 Z 方向的高度或厚度，单位 mm。';
  }
  if (/dimensions_mm/.test(text)) {
    return '还需要说明硬件主体的长、宽、高或厚度，单位 mm。';
  }
  if (/coordinate_system/.test(text)) {
    return '还需要说明硬件坐标方向：X/Y/Z 分别对应实体的哪个方向，哪个面是正面。';
  }
  if (/opening(?:\[\d+\])?\.preferred_face/.test(text)) {
    return `还需要说明${ordinal}外壳开孔应该位于盒子的哪个面。`;
  }
  if (/opening(?:\[\d+\])?\.clearance_mm/.test(text)) {
    return `还需要说明${ordinal}外壳开孔四周需要预留多少装配余量，单位 mm。`;
  }
  if (/opening(?:\[\d+\])?\.size_mm\.(?:width|height)|opening(?:\[\d+\])?\.(?:width|height)/.test(text)) {
    return `还需要说明${ordinal}外壳开孔的宽度和高度，单位 mm。`;
  }
  if (/opening(?:\[\d+\])?\.diameter_mm/.test(text)) {
    return `还需要说明${ordinal}圆形开孔的直径，单位 mm。`;
  }
  if (/opening(?:\[\d+\])?\.center_mm|opening(?:\[\d+\])?\.offset_mm/.test(text)) {
    return `还需要说明${ordinal}外壳开孔相对硬件中心或指定面的偏移位置，单位 mm。`;
  }
  if (/opening/.test(text)) {
    return '还需要说明外壳是否需要为屏幕、按钮、接口、线缆或传感窗口开孔，以及开孔的位置和尺寸。';
  }
  if (/keepouts(?:\[\d+\])?\.center_mm|keepouts(?:\[\d+\])?\.size_mm/.test(text)) {
    return `还需要说明${ordinal}避让空间的位置和尺寸，单位 mm。`;
  }
  if (/keepouts/.test(text)) {
    return '还需要说明是否需要为接线、插拔、按压、取放或散热预留避让空间。';
  }
  if (/cadquery_code\.import|cadquery_code/.test(text)) {
    return '还需要生成完整可运行的 CadQuery 模型代码，并包含可预览的 result 模型。';
  }
  if (/custom_hardware_type/.test(text)) {
    return '还需要选择这个自定义硬件属于电子器件还是结构件。';
  }
  if (/hardware_system/.test(text)) {
    return '这个硬件必须写入用户自定义硬件库，不能归入行空板、掌控板、XIAO 或通用件库。';
  }
  if (/^id$|^name$|category|roles|source_status|thumbnail_url|cad_reference|cadquery_model/.test(text)) {
    return '还需要补充写入用户自定义硬件库所需的基础信息，例如名称、类别、用途或预览资源。';
  }
  if (containsInternalProfilePath(text)) {
    return '还需要补充写入硬件库所需的尺寸、安装、开孔或避让信息，请用自然语言描述。';
  }
  return text;
}

function sanitizeCustomHardwareFeedback(feedback, publicIssues = []) {
  const issues = describeCustomHardwareIssues(publicIssues);
  let text = normalizeString(feedback);
  if (!text) {
    return issues.length ? `还缺少这些关键信息：${issues.join('、')}` : '';
  }
  const replacements = [
    [/mounting\.clearance_mm/g, '固定结构与外壳或安装面之间预留的安装间隙'],
    [/mounting\.preferred_enclosure_surface/g, '硬件默认固定在盒子的哪个位置'],
    [/mounting\.mating_hardware_face/g, '硬件本体贴合外壳或固定结构的那一面'],
    [/mounting\.holes\[(\d+)\]\.x/g, (_, index) => `第 ${Number(index) + 1} 个固定孔相对硬件中心的 X 坐标`],
    [/mounting\.holes\[(\d+)\]\.y/g, (_, index) => `第 ${Number(index) + 1} 个固定孔相对硬件中心的 Y 坐标`],
    [/mounting\.holes\[(\d+)\]\.diameter_mm/g, (_, index) => `第 ${Number(index) + 1} 个固定孔的直径`],
    [/opening\[(\d+)\]\.preferred_face/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔所在的盒子面`],
    [/opening\[(\d+)\]\.clearance_mm/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔四周的装配余量`],
    [/opening\[(\d+)\]\.size_mm\.width/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔的宽度`],
    [/opening\[(\d+)\]\.size_mm\.height/g, (_, index) => `第 ${Number(index) + 1} 个外壳开孔的高度`],
    [/keepouts\[(\d+)\]\.center_mm/g, (_, index) => `第 ${Number(index) + 1} 个避让空间的位置`],
    [/keepouts\[(\d+)\]\.size_mm/g, (_, index) => `第 ${Number(index) + 1} 个避让空间的尺寸`],
  ];
  for (const [pattern, replacement] of replacements) {
    text = text.replace(pattern, replacement);
  }
  if (containsInternalProfilePath(text) && issues.length) {
    return `还缺少这些关键信息：${issues.join('、')}`;
  }
  if (containsInternalProfilePath(text)) {
    return '还需要补充写入硬件库所需的尺寸、安装、开孔或避让信息，请用自然语言描述。';
  }
  return text;
}

function issueOrdinalText(text) {
  const match = normalizeString(text).match(/\[(\d+)\]/);
  return match ? `第 ${Number(match[1]) + 1} 个` : '';
}

function containsInternalProfilePath(text) {
  return /(?:mounting|opening|keepouts|dimensions_mm|coordinate_system|cadquery_model|cadquery_code|hardware_system|custom_hardware_type|source_status|cad_reference)(?:[\w.[\]]*)?/.test(normalizeString(text));
}

function buildNeedsInputResponse({ normalized, missing, feedback, draft = null, llm_status = '' }) {
  const publicMissing = describeCustomHardwareIssues(missing);
  const publicFeedback = sanitizeCustomHardwareFeedback(feedback, publicMissing);
  return {
    status: 'needs_input',
    blocking_reason: 'custom_hardware_missing_information',
    title: '自定义硬件信息待补充',
    message: publicFeedback,
    user_feedback: publicFeedback,
    missing_fields: publicMissing,
    custom_hardware_type: normalized.custom_hardware_type,
    profile_draft: draft?.profile || null,
    cadquery_code: '',
    source: 'custom_hardware_builder',
    llm_status,
  };
}

function normalizeString(value) {
  return String(value || '').trim();
}

function safeNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) && number > 0 ? number : fallback;
}

function decodePngDataUrl(value) {
  const match = String(value || '').match(/^data:image\/png;base64,(.+)$/);
  if (!match) throw new Error('thumbnail_data_url must be a PNG data URL');
  return Buffer.from(match[1], 'base64');
}

async function ensureFallbackThumbnail(thumbnailPath, profile) {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="320" height="240" viewBox="0 0 320 240">
  <rect width="320" height="240" fill="#ffffff"/>
  <rect x="72" y="68" width="176" height="104" rx="10" fill="${profile.custom_hardware_type === 'structural' ? '#d7dde2' : '#4f9a94'}" stroke="#26343d" stroke-width="4"/>
  <text x="160" y="202" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#26343d">${escapeXml(profile.name || profile.id)}</text>
</svg>`;
  const pngBase64 = 'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+/p9sAAAAASUVORK5CYII=';
  await mkdir(path.dirname(thumbnailPath), { recursive: true });
  await writeFile(thumbnailPath, Buffer.from(pngBase64, 'base64'));
  await writeFile(thumbnailPath.replace(/\.png$/i, '.svg'), svg, 'utf8').catch(() => {});
}

function escapeXml(value) {
  return String(value || '').replace(/[<>&"]/g, (char) => ({
    '<': '&lt;',
    '>': '&gt;',
    '&': '&amp;',
    '"': '&quot;',
  }[char]));
}

function runPython(python, args, { cwd, timeoutMs, input = '' }) {
  return new Promise((resolve) => {
    const child = spawn(python, args, {
      cwd,
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let settled = false;
    const timeout = setTimeout(() => {
      if (settled) return;
      settled = true;
      child.kill('SIGKILL');
      resolve({ exitCode: 124, stdout, stderr: `${stderr}\nTimed out after ${timeoutMs} ms`.trim() });
    }, timeoutMs);
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('close', (exitCode) => {
      if (settled) return;
      settled = true;
      clearTimeout(timeout);
      resolve({ exitCode, stdout, stderr });
    });
    if (input) child.stdin.write(input);
    child.stdin.end();
  });
}
