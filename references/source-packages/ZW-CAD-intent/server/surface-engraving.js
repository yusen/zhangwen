import crypto from 'node:crypto';
import { readFileSync } from 'node:fs';
import { mkdtemp, rm, writeFile } from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { preflightCadQueryCode } from './cadquery-runner.js';
import {
  buildModelNeedsInput,
  getIntentModelConfig,
  requestChatCompletionJson,
} from './model-sources.js';
import { isPlainObject, normalizeString } from './pipeline/shared.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const SKILL_ROOT = path.resolve(__dirname, '..', 'skills', 'surface-engraving');
const SKILL_SOURCE = readFileSync(path.join(SKILL_ROOT, 'SKILL.md'), 'utf8');
const HELPER_SOURCE = readFileSync(path.join(SKILL_ROOT, 'references', 'cadquery-planar-engraving.py'), 'utf8').trim();

const PATCH_START = '# ZW-CAD-intent surface engraving start';
const PATCH_END = '# ZW-CAD-intent surface engraving end';
const DEPTH_MM = 0.6;
const MIN_FONT_HEIGHT_MM = 3;
const MAX_TEXT_LENGTH = 32;
const MAX_MULTILINE_TEXT_LENGTH = 256;
const MAX_MULTILINE_LINES = 32;
const RUN_TIMEOUT_MS = 90000;
const ALLOWED_ANCHORS = new Set([
  'top_left',
  'top_center',
  'top_right',
  'center_left',
  'center',
  'center_right',
  'bottom_left',
  'bottom_center',
  'bottom_right',
]);
const USER_POSITION_GUIDANCE = '请说明文字在目标平面上的大致位置：左上、上方中央、右上、左侧中央、正中央、右侧中央、左下、下方中央或右下。';
const USER_POSITION_EXAMPLE = '可以直接回复：“刻在斜面正中央，字高 5mm。”';
const USER_OFFSET_EXAMPLE = '需要微调时可以回复：“刻在斜面正中央，再向右移动 3mm、向上移动 2mm，字高 5mm。”';
const USER_SURFACE_GUIDANCE = '请说明要刻在哪个零件的哪个外部平面，例如“上盖外表面”“底壳正面”或“斜面正面”；不需要输入零件代码、法向量或坐标。';
const USER_FONT_HEIGHT_GUIDANCE = '请确认字体高度，单位为毫米，例如“字高 5mm”；系统不会自动缩放。';
const USER_TEXT_GUIDANCE = '请说明要刻的单行文字内容，例如“ZW-CAD”。';
const USER_GENERIC_GUIDANCE = '请补充刻字内容或目标外部平面；不需要输入英文参数名或 CAD 坐标。';
const DRAFT_SCHEMA_VERSION = 'surface_engraving_draft_v1';
const ENGRAVING_SCHEMA_VERSION = 'surface_engraving_v2';
const SURFACE_SELECTOR_VERSION = 'planar_surface_selector_v3';
const AUTO_FONT_HEIGHT_MAX_MM = 8;
const AUTO_FONT_HEIGHT_RATIO = 0.7;
const ORIGINAL_FEATURE_CONFLICT_CODE = 'engraving_original_feature_conflict';
const FORCE_CONFIRMATION_SCHEMA_VERSION = 'surface_engraving_original_feature_confirmation_v1';
const SOURCE_HASH_PATTERN = /^[a-f0-9]{64}$/i;
const OVERRIDE_GEOMETRY_FIELDS = [
  'text',
  'lines',
  'layout_mode',
  'line_spacing_ratio',
  'requested_layout',
  'surface_id',
  'target_part',
  'normal_hint',
  'point_hint',
  'x_direction',
  'anchor',
  'offset_u_mm',
  'offset_v_mm',
  'rotation_deg',
  'font_height_mm',
  'depth_mm',
  'font_kind',
];

export function isSurfaceEngravingPrompt(prompt = '', currentEngravings = []) {
  const text = normalizeString(prompt);
  if (!text) return false;
  if (/(刻字|刻上|刻下|雕刻|凹刻|铭文|写上|印上|标上|字样|编号|logo|engrave|engraving)/i.test(text)) return true;
  if (/(?:再|另外|新增|追加).{0,8}(?:刻|写|印|标|加).{0,6}(?:一条|文字|字样)?|(?:新增|追加).{0,6}(?:一条文字|文字|字样|刻字)/i.test(text)) return true;
  if (!Array.isArray(currentEngravings) || !currentEngravings.length) return false;
  return /(?:文字|字体|字号|字高|这条字|上面的字|侧面的字|单行|两行|多行|换行|分两排|第一行|第二行).{0,16}(?:改|换|删除|删掉|移除|取消|变大|变小|保持)|(?:改|换|删除|删掉|移除|取消|调整|保持).{0,16}(?:文字|字体|字号|刻的字|单行|两行|多行|换行)|^(?:改成|调整为|换成)\s*\d+(?:\.\d+)?\s*(?:mm|毫米)$/i.test(text);
}

export function normalizeSurfaceEngravings(value = []) {
  if (!Array.isArray(value)) return [];
  const result = [];
  for (const item of value) {
    const normalized = normalizeEngravingSpec(item);
    if (normalized.status === 'ok') result.push(normalized.spec);
  }
  return result;
}

export function migrateLegacySurfaceEngravings({ engravings = [], modelSurfaces = [], report = [] } = {}) {
  const surfaces = normalizeModelSurfaces(modelSurfaces);
  const reports = new Map((Array.isArray(report) ? report : [])
    .filter(isPlainObject)
    .map((item) => [normalizeString(item.id), item]));
  const migrations = [];
  const unresolved = [];
  const result = (Array.isArray(engravings) ? engravings : []).map((item) => {
    if (!isPlainObject(item)) return item;
    const currentSelectorVersion = normalizeString(item.surface_selector_version || item.surfaceSelectorVersion);
    if (currentSelectorVersion === SURFACE_SELECTOR_VERSION) return item;
    const targetPart = normalizeTargetPart(item.target_part || item.targetPart);
    const historical = reports.get(normalizeString(item.id));
    const reportedNormal = normalizeDirection(historical?.face_normal || historical?.faceNormal);
    const normal = reportedNormal || normalizeDirection(item.normal_hint || item.normalHint);
    const sameOrientation = surfaces.filter((surface) => (
      surface.target_part === targetPart
      && normal
      && directionAlignment(surface.normal_hint, normal) >= 0.92
    ));
    if (!sameOrientation.length) {
      unresolved.push({
        engraving_id: normalizeString(item.id),
        current_surface_id: normalizeString(item.surface_id || item.surfaceId),
        reason: reportedNormal
          ? '旧刻字报告的真实面法向无法匹配当前稳定表面。'
          : '旧刻字缺少可匹配的稳定表面法向。',
        reported_face_normal: reportedNormal,
        candidates: surfaces
          .filter((surface) => surface.target_part === targetPart)
          .map((surface) => ({
            id: surface.id,
            label: surface.label,
            aliases: surface.aliases,
          })),
      });
      return item;
    }
    const faceCenter = normalizeVector(historical?.face_center || historical?.faceCenter);
    if (sameOrientation.length === 1) {
      const selected = sameOrientation[0];
      const migrated = migrateEngravingSurfaceFrame(item, selected);
      migrations.push({
        engraving_id: normalizeString(item.id),
        from_surface_id: normalizeString(item.surface_id || item.surfaceId),
        to_surface_id: selected.id,
        reason: '当前零件和法向只有一个稳定平面候选，已升级表面身份版本。',
      });
      return migrated;
    }
    if (!faceCenter) {
      unresolved.push({
        engraving_id: normalizeString(item.id),
        current_surface_id: normalizeString(item.surface_id || item.surfaceId),
        candidates: sameOrientation.map((surface) => ({
          id: surface.id,
          label: surface.label,
          aliases: surface.aliases,
        })),
      });
      return item;
    }
    const ranked = sameOrientation.map((surface) => ({
      surface,
      plane_distance_mm: pointToSurfacePlaneDistance(faceCenter, surface),
    })).sort((left, right) => left.plane_distance_mm - right.plane_distance_mm);
    if (ranked.length > 1 && ranked[0].plane_distance_mm + 0.5 >= ranked[1].plane_distance_mm) {
      unresolved.push({
        engraving_id: normalizeString(item.id),
        current_surface_id: normalizeString(item.surface_id || item.surfaceId),
        candidates: ranked.map(({ surface, plane_distance_mm: distance }) => ({
          id: surface.id,
          label: surface.label,
          aliases: surface.aliases,
          plane_distance_mm: Math.round(distance * 1000) / 1000,
        })),
      });
      return item;
    }
    const selected = ranked[0].surface;
    const migrated = migrateEngravingSurfaceFrame(item, selected);
    migrations.push({
      engraving_id: normalizeString(item.id),
      from_surface_id: normalizeString(item.surface_id || item.surfaceId),
      to_surface_id: selected.id,
      reason: '根据旧刻字报告的真实面中心和法向匹配稳定表面。',
    });
    return migrated;
  });
  return {
    surface_engravings: result,
    migrations,
    unresolved,
    requires_confirmation: unresolved.length > 0,
  };
}

function migrateEngravingSurfaceFrame(item, selected) {
  return {
    ...item,
    surface_id: selected.id,
    surface: selected.label,
    normal_hint: selected.normal_hint,
    point_hint: selected.point_hint,
    x_direction: selected.x_direction,
    surface_area_hint_mm2: selected.area_hint_mm2,
    surface_span_hint_mm: selected.local_span_hint_mm,
    surface_selector_version: selected.selector_version || SURFACE_SELECTOR_VERSION,
  };
}

function resolveLegacySurfaceConfirmation({ engravings, currentDesignState, migration, prompt }) {
  const normalizedPrompt = normalizeString(prompt).toLowerCase();
  const surfaces = normalizeModelSurfaces(
    currentDesignState?.engraving_surfaces
      || currentDesignState?.model_index?.surfaces
      || currentDesignState?.cad_parameters?.engraving_surfaces,
  );
  const surfacesById = new Map(surfaces.map((surface) => [surface.id, surface]));
  const selections = new Map(Object.entries(isPlainObject(migration?.selections) ? migration.selections : {})
    .map(([engravingId, surfaceId]) => [normalizeString(engravingId), surfacesById.get(normalizeString(surfaceId).toLowerCase())])
    .filter(([, surface]) => surface));
  const unresolvedItems = Array.isArray(migration?.unresolved) ? migration.unresolved : [];
  const remaining = [];
  for (const [index, unresolved] of unresolvedItems.entries()) {
    const engravingId = normalizeString(unresolved.engraving_id);
    if (selections.has(engravingId)) continue;
    const scopedPrompt = legacySurfaceSelectionScope({
      prompt: normalizedPrompt,
      unresolved,
      engraving: engravings.find((item) => normalizeString(item.id) === engravingId),
      index,
      total: unresolvedItems.length,
    });
    const matches = (unresolved.candidates || []).filter((candidate) => (
      [candidate.id, candidate.label, ...(candidate.aliases || [])]
        .map((term) => normalizeString(term).toLowerCase())
        .filter(Boolean)
        .some((term) => scopedPrompt.includes(term))
    ));
    if (matches.length !== 1) {
      remaining.push(unresolved);
      continue;
    }
    const surface = surfacesById.get(normalizeString(matches[0].id).toLowerCase());
    if (!surface) {
      remaining.push(unresolved);
      continue;
    }
    selections.set(engravingId, surface);
  }
  const migrated = [];
  const surfaceEngravings = engravings.map((engraving) => {
    const surface = selections.get(normalizeString(engraving.id));
    if (!surface) return engraving;
    migrated.push({
      engraving_id: normalizeString(engraving.id),
      from_surface_id: normalizeString(engraving.surface_id || engraving.surfaceId),
      to_surface_id: surface.id,
      reason: '用户确认旧刻字实际所在的稳定表面。',
    });
    return normalizeEngravingSpec({
      ...engraving,
      surface_id: surface.id,
      surface: surface.label,
      normal_hint: surface.normal_hint,
      point_hint: surface.point_hint,
      x_direction: surface.x_direction,
      surface_area_hint_mm2: surface.area_hint_mm2,
      surface_span_hint_mm: surface.local_span_hint_mm,
      surface_selector_version: surface.selector_version || SURFACE_SELECTOR_VERSION,
    }).spec;
  });
  return {
    resolved: unresolvedItems.length > 0 && remaining.length === 0,
    surface_engravings: surfaceEngravings,
    unresolved: remaining,
    migrations: migrated,
    selections: Object.fromEntries([...selections].map(([engravingId, surface]) => [engravingId, surface.id])),
  };
}

function legacySurfaceSelectionScope({ prompt = '', unresolved = {}, engraving = {}, index = 0, total = 1 } = {}) {
  if (total <= 1) return prompt;
  const clauses = normalizeString(prompt).split(/[，,。；;\n]+/).map((item) => item.trim()).filter(Boolean);
  const identifiers = [
    normalizeString(unresolved.engraving_id).toLowerCase(),
    normalizeString(engraving?.text).toLowerCase(),
    `第${index + 1}条`,
    `第${index + 1}个`,
  ].filter(Boolean);
  return clauses.find((clause) => identifiers.some((identifier) => clause.toLowerCase().includes(identifier))) || '';
}

export async function analyzeSurfaceEngravingRequest(body = {}, { python, cadqueryAvailable = true } = {}) {
  const prompt = normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt);
  if (isClearlyUnrelatedMechanicalEdit(prompt)) {
    return {
      status: 'not_applicable',
      reason: '最新输入是结构、孔槽、边线或硬件位置修改，不属于模型表面刻字。',
    };
  }
  const currentDesignState = currentDesignStateFromBody(body);
  let currentEngravings = normalizeSurfaceEngravings(
    body.surfaceEngravings
      || body.surface_engravings
      || currentDesignState?.surface_engravings,
  );
  const legacyMigration = body.surfaceEngravingMigration
    || body.surface_engraving_migration
    || body.lastNeedsInput?.surface_engraving_migration
    || body.last_needs_input?.surface_engraving_migration
    || currentDesignState?.surface_engraving_migration
    || null;
  let resolvedLegacyMigration = null;
  if (legacyMigration?.requires_confirmation) {
    const resolution = resolveLegacySurfaceConfirmation({
      engravings: currentEngravings,
      currentDesignState,
      migration: legacyMigration,
      prompt,
    });
    if (!resolution.resolved) {
      const labels = [...new Set((resolution.unresolved || legacyMigration.unresolved || [])
        .flatMap((item) => (item.candidates || []).map((candidate) => candidate.label))
        .filter(Boolean))];
      const response = buildSurfaceEngravingNeedsInput({
        message: '旧刻字记录缺少可唯一确认的稳定表面。为避免重建时把已有文字移动到另一个斜面，本轮保持当前模型不变。',
        questions: [labels.length
          ? `请按文字内容或编号说明原有刻字实际位于${labels.map((item) => `“${item}”`).join('还是')}。`
          : '请重新说明原有刻字实际位于哪个外部平面。'],
        blockingReason: 'surface_engraving_surface_identity_confirmation',
        currentEngravings: resolution.surface_engravings,
      });
      response.surface_engraving_migration = {
        ...legacyMigration,
        selections: resolution.selections,
        unresolved: resolution.unresolved,
        requires_confirmation: true,
      };
      return {
        status: 'needs_input',
        response,
      };
    }
    currentEngravings = resolution.surface_engravings;
    resolvedLegacyMigration = resolution;
  }
  const sourceCode = stripSurfaceEngravingCode(
    normalizeString(body.currentCadQueryCode || body.current_cadquery_code || body.cadquery_code),
  );
  const previousDraft = surfaceEngravingDraftFromBody(body);
  const userTurns = collectSurfaceEngravingTurns(body, prompt, previousDraft);
  if (!currentDesignState || !sourceCode) {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: '刻字只能在真实模型生成后进行，当前缺少可复用的模型状态或 CadQuery 源码。',
        questions: ['请先完成模型生成，再说明刻什么字、刻在哪个平面以及字体高度。'],
        blockingReason: 'surface_engraving_requires_artifact',
        currentEngravings,
      }),
    };
  }
  if (isExplicitOriginalFeatureConflictConfirmation(prompt)) {
    return confirmOriginalFeatureConflictEngraving({
      body,
      prompt,
      python,
      cadqueryAvailable,
      sourceCode,
      currentDesignState,
      currentEngravings,
      previousDraft,
    });
  }
  if (resolvedLegacyMigration) {
    const patch = buildSurfaceEngravingPatch(currentEngravings);
    const patchValidation = await validateSurfaceEngravingPatch(patch, currentEngravings, { python });
    if (patchValidation.status !== 'pass') {
      return {
        status: 'needs_input',
        response: buildSurfaceEngravingNeedsInput({
          message: `旧刻字表面迁移补丁未通过安全校验：${patchValidation.message}`,
          questions: ['请重新确认每条旧刻字所在的目标平面。'],
          blockingReason: 'surface_engraving_surface_identity_migration_rejected',
          currentEngravings,
        }),
      };
    }
    const preflight = cadqueryAvailable
      ? await preflightSurfaceEngravings({ python, sourceCode, surfaceEngravings: currentEngravings, patch })
      : { status: 'pending', message: 'CadQuery 环境不可用，迁移将在真实构建阶段校验。', report: [] };
    if (preflight.status === 'fail') {
      return {
        status: 'needs_input',
        response: buildSurfaceEngravingNeedsInput({
          message: preflight.message,
          questions: ['旧刻字的稳定表面身份已确认，但几何预检未通过，请重新确认目标平面或位置。'],
          blockingReason: `surface_engraving_${preflight.code || 'migration_preflight_failed'}`,
          currentEngravings,
          preflight,
        }),
      };
    }
    return {
      status: 'ok',
      surface_engravings: currentEngravings,
      surface_engraving_operations: resolvedLegacyMigration.migrations.map((migration) => ({
        action: 'update',
        target_id: migration.engraving_id,
        engraving: currentEngravings.find((item) => item.id === migration.engraving_id),
      })),
      surface_engraving_patch: patch,
      surface_engraving_preflight: preflight,
      surface_engraving_draft: null,
      surface_engraving_turns: [],
      surface_engraving_migration: {
        migrations: resolvedLegacyMigration.migrations,
        unresolved: [],
        requires_confirmation: false,
      },
      summary: `已确认并保存 ${resolvedLegacyMigration.migrations.length} 条旧刻字的目标表面；原锚点和偏移参数已保留，并已重新执行几何预检。`,
      clean_cadquery_code: sourceCode,
    };
  }
  if (previousDraft && /^(?:取消(?:这次|当前)?刻字|这次不刻了|不刻了|放弃刻字)[。.!！\s]*$/.test(prompt)) {
    const patch = buildSurfaceEngravingPatch(currentEngravings);
    return {
      status: 'ok',
      surface_engravings: currentEngravings,
      surface_engraving_operations: [],
      surface_engraving_patch: patch,
      surface_engraving_preflight: { status: 'pending', message: '本轮未改变模型刻字。', report: [] },
      surface_engraving_draft: null,
      surface_engraving_turns: [],
      surface_engraving_unsupported_layout: null,
      summary: '已取消本轮尚未完成的刻字要求，模型和已有刻字保持不变。',
      clean_cadquery_code: sourceCode,
    };
  }
  const config = getIntentModelConfig();
  if (!config.enabled) {
    return {
      status: 'needs_input',
      response: buildModelNeedsInput(new Error('LLM 未配置或未启用，无法解析自然语言刻字位置。'), {
        config,
        code: 'llm_unavailable',
        requestKind: 'surface_engraving',
      }),
    };
  }

  let rawResult;
  try {
    rawResult = await requestChatCompletionJson({
      config,
      requestKind: 'surface_engraving',
      temperature: 0.05,
      responseFormat: { type: 'json_object' },
      messages: [
        { role: 'system', content: buildSurfaceEngravingSystemPrompt() },
        {
          role: 'user',
          content: JSON.stringify({
            user_message: prompt,
            engraving_conversation: userTurns,
            pending_surface_engraving_draft: previousDraft,
            current_surface_engravings: currentEngravings,
            last_needs_input: body.lastNeedsInput || body.last_needs_input || null,
            current_design_state: currentDesignState,
            current_clean_cadquery_code: sourceCode,
          }, null, 2),
        },
      ],
    });
  } catch (error) {
    return {
      status: 'needs_input',
      response: buildModelNeedsInput(error, {
        config,
        code: error?.code || 'llm_surface_engraving_failed',
        requestKind: 'surface_engraving',
      }),
    };
  }
  if (normalizeString(rawResult?.status).toLowerCase() === 'not_applicable') {
    return {
      status: 'not_applicable',
      reason: normalizeString(rawResult?.reason || rawResult?.message)
        || '刻字分析器判定最新输入不属于表面刻字。',
    };
  }

  const draft = buildMergedSurfaceEngravingDraft({
    body,
    prompt,
    previousDraft,
    userTurns,
    rawResult,
    currentEngravings,
    currentDesignState,
  });
  const explicitRequestedLayout = detectRequestedLayout(prompt);
  if (explicitRequestedLayout.multiline === true && !isSingleLineLayoutConfirmation(prompt)) {
    draft.requested_layout = { ...draft.requested_layout, ...explicitRequestedLayout, multiline: true };
  }
  const defaultedDraft = applySurfaceEngravingDraftDefaults(draft, currentEngravings);
  const completedOperations = completeSurfaceEngravingOperations(
    defaultedDraft.pending_operations,
    currentDesignState,
    prompt,
  );
  defaultedDraft.pending_operations = completedOperations;
  const ambiguousSurface = completedOperations.find((operation) => (
    Array.isArray(operation?.engraving?.surface_candidate_labels)
    && operation.engraving.surface_candidate_labels.length > 1
  ));
  if (ambiguousSurface) {
    const labels = ambiguousSurface.engraving.surface_candidate_labels;
    defaultedDraft.missing_fields = ['可唯一识别的目标外部平面'];
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: `“斜面”可能指 ${labels.map((item) => `「${item}」`).join('或')}，这些候选面积接近，不能安全猜测。`,
        questions: [`请选择${labels.map((item) => `“${item}”`).join('或')}。`],
        blockingReason: 'surface_engraving_surface_ambiguous',
        currentEngravings,
        draft: defaultedDraft,
      }),
    };
  }
  const applied = applySurfaceEngravingOperations(currentEngravings, completedOperations);
  if (applied.status !== 'ok') {
    defaultedDraft.missing_fields = missingFieldsFromNeedsInput(applied);
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: applied.message,
        questions: applied.questions,
        blockingReason: applied.blocking_reason,
        currentEngravings,
        draft: defaultedDraft,
      }),
    };
  }
  defaultedDraft.pending_operations = defaultedDraft.pending_operations.map((operation, index) => {
    const resolved = applied.operations?.[index]?.engraving;
    return resolved
      ? { ...operation, engraving: { ...(operation.engraving || {}), id: resolved.id } }
      : operation;
  });
  const fontResolution = await resolveAutomaticFontHeights({
    python,
    sourceCode,
    cadqueryAvailable,
    applied,
    draft: defaultedDraft,
  });
  if (fontResolution.status !== 'ok') {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: fontResolution.message,
        questions: fontResolution.questions,
        blockingReason: fontResolution.blocking_reason,
        currentEngravings,
        draft: defaultedDraft,
      }),
    };
  }
  const resolvedApplied = dedupeResolvedSurfaceEngravings(fontResolution.applied);
  const patch = buildSurfaceEngravingPatch(resolvedApplied.surface_engravings);
  const patchValidation = await validateSurfaceEngravingPatch(patch, resolvedApplied.surface_engravings, { python });
  if (patchValidation.status !== 'pass') {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: `刻字补丁未通过安全校验：${patchValidation.message}`,
        questions: ['请重新描述刻字要求，系统会重新生成受限刻字补丁。'],
        blockingReason: 'surface_engraving_patch_rejected',
        currentEngravings,
        draft: defaultedDraft,
      }),
    };
  }

  const reusableFontPreflight = preflightMatchesSurfaceEngravings(
    fontResolution.preflight,
    resolvedApplied.surface_engravings,
  ) ? fontResolution.preflight : null;
  const preflight = cadqueryAvailable
    ? reusableFontPreflight || await preflightSurfaceEngravings({
      python,
      sourceCode,
      surfaceEngravings: resolvedApplied.surface_engravings,
      patch,
    })
    : { status: 'pending', message: 'CadQuery 环境不可用，刻字将在真实构建阶段校验。', report: [] };
  if (preflight.status === 'fail') {
    const verifiedSuggestion = await findVerifiedFontHeightSuggestion({
      python,
      sourceCode,
      cadqueryAvailable,
      surfaceEngravings: resolvedApplied.surface_engravings,
      operations: resolvedApplied.operations,
      failure: preflight,
    });
    const suggestion = finiteNumber(verifiedSuggestion?.font_height_mm);
    const forceableConflict = preflight.code === ORIGINAL_FEATURE_CONFLICT_CODE;
    const resolvedSurfaceLabel = surfaceLabelForId(currentDesignState, preflight.details?.surface_id);
    const surfacePrefix = resolvedSurfaceLabel
      ? `系统当前按“${resolvedSurfaceLabel}”进行预检。`
      : '';
    const questions = Number.isFinite(suggestion) && suggestion >= MIN_FONT_HEIGHT_MM
      ? [`当前位置建议把字体高度改为不超过 ${suggestion.toFixed(2)}mm，请确认新的字体高度。`]
      : ['请调整目标平面、位置或字体高度后重试。'];
    if (forceableConflict) {
      questions.push('如果确认接受文字被边界裁断或影响现有孔位，请回复“确认强制刻字”。');
    }
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: Number.isFinite(suggestion)
          ? `${surfacePrefix}${preflight.message}已用完整文字切除体、孔洞和偏移进一步验证可用字号。`
          : `${surfacePrefix}${preflight.message}`,
        questions,
        blockingReason: `surface_engraving_${preflight.code || 'preflight_failed'}`,
        currentEngravings,
        draft: {
          ...defaultedDraft,
          pending_operations: resolvedApplied.operations || defaultedDraft.pending_operations,
          surface_engravings: resolvedApplied.surface_engravings,
          suggested_font_height_mm: Number.isFinite(suggestion) ? suggestion : null,
          original_feature_conflict_confirmation: forceableConflict
            ? buildOriginalFeatureConflictConfirmation({
                body,
                sourceCode,
                surfaceEngravings: resolvedApplied.surface_engravings,
                preflight,
                surfaceLabel: resolvedSurfaceLabel,
              })
            : null,
        },
        preflight,
      }),
    };
  }

  return {
    status: 'ok',
    surface_engravings: resolvedApplied.surface_engravings,
    surface_engraving_operations: resolvedApplied.operations,
    surface_engraving_patch: patch,
    surface_engraving_preflight: preflight,
    surface_engraving_draft: null,
    surface_engraving_turns: [],
    surface_engraving_unsupported_layout: null,
    summary: buildResolvedEngravingSummary(resolvedApplied.surface_engravings, defaultedDraft, rawResult?.summary),
    clean_cadquery_code: sourceCode,
  };
}

function isExplicitOriginalFeatureConflictConfirmation(value = '') {
  const text = normalizeString(value).replace(/[。.!！\s]/g, '');
  return /^(?:确认强制刻字|强制刻字|无视(?:影响|冲突)(?:直接|继续|仍然)?刻字|忽略(?:影响|冲突)(?:直接|继续|仍然)?刻字|忽略冲突继续刻字|仍然强制刻字)$/i.test(text);
}

async function confirmOriginalFeatureConflictEngraving({
  body = {},
  python,
  cadqueryAvailable = true,
  sourceCode = '',
  currentDesignState = {},
  currentEngravings = [],
  previousDraft = null,
} = {}) {
  const confirmation = normalizeOriginalFeatureConflictConfirmation(
    previousDraft?.original_feature_conflict_confirmation,
  );
  const expectedBlockingReason = `surface_engraving_${ORIGINAL_FEATURE_CONFLICT_CODE}`;
  const lastBlockingReason = normalizeString(
    body.projectSessionState?.last_blocking_state?.blocking_reason
      || body.project_session_state?.last_blocking_state?.blocking_reason
      || body.lastNeedsInput?.blocking_reason
      || body.last_needs_input?.blocking_reason,
  );
  const taskId = normalizeString(body.taskId || body.task_id || currentDesignState?.id);
  const sourceHash = cleanCadQuerySourceHash(sourceCode);
  const candidateEngravings = normalizeSurfaceEngravings(previousDraft?.surface_engravings);
  const candidateHash = surfaceEngravingStateHash(candidateEngravings);
  const reapplied = applySurfaceEngravingOperations(
    currentEngravings,
    previousDraft?.pending_operations || [],
  );
  const reappliedHash = reapplied.status === 'ok'
    ? surfaceEngravingStateHash(reapplied.surface_engravings)
    : '';
  const valid = confirmation
    && lastBlockingReason === expectedBlockingReason
    && confirmation.task_id === taskId
    && confirmation.source_hash === sourceHash
    && confirmation.spec_hash === candidateHash
    && candidateHash === reappliedHash
    && candidateEngravings.some((item) => item.id === confirmation.engraving_id
      && item.surface_id === confirmation.surface_id);
  if (!valid) {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: '当前没有可复用的上一轮孔边冲突确认，或模型与刻字参数已经发生变化。系统不会直接跳过安全检查。',
        questions: ['请重新说明刻字内容、目标平面、位置和字号；系统会先重新预检。'],
        blockingReason: 'surface_engraving_force_confirmation_unavailable',
        currentEngravings,
        draft: previousDraft ? {
          ...previousDraft,
          original_feature_conflict_confirmation: null,
        } : null,
      }),
    };
  }
  if (!cadqueryAvailable || !python) {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: '当前 CadQuery 环境不可用，无法复检并执行强制刻字。',
        questions: ['请稍后重试；强制刻字不会在缺少真实几何校验时执行。'],
        blockingReason: 'surface_engraving_force_confirmation_runtime_unavailable',
        currentEngravings,
        draft: previousDraft,
      }),
    };
  }
  const normalPatch = buildSurfaceEngravingPatch(candidateEngravings);
  const normalPatchValidation = await validateSurfaceEngravingPatch(normalPatch, candidateEngravings, { python });
  if (normalPatchValidation.status !== 'pass') {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: `待确认刻字补丁未通过安全校验：${normalPatchValidation.message}`,
        questions: ['请重新提交刻字要求。'],
        blockingReason: 'surface_engraving_force_confirmation_patch_rejected',
        currentEngravings,
      }),
    };
  }
  const retry = await preflightSurfaceEngravings({
    python,
    sourceCode,
    surfaceEngravings: candidateEngravings,
    patch: normalPatch,
  });
  if (retry.status === 'pass') {
    return {
      status: 'ok',
      surface_engravings: candidateEngravings,
      surface_engraving_operations: reapplied.operations,
      surface_engraving_patch: normalPatch,
      surface_engraving_preflight: retry,
      surface_engraving_draft: null,
      surface_engraving_turns: [],
      surface_engraving_unsupported_layout: null,
      summary: `${summarizeSurfaceEngravings(candidateEngravings)}复检已正常通过，无需强制覆盖。`,
      clean_cadquery_code: sourceCode,
    };
  }
  const failedId = normalizeString(retry.details?.engraving_id);
  const failedSurfaceId = normalizeString(retry.details?.surface_id);
  if (retry.code !== ORIGINAL_FEATURE_CONFLICT_CODE
    || failedId !== confirmation.engraving_id
    || failedSurfaceId !== confirmation.surface_id) {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: retry.message || '复检出现了不同的几何问题，不能沿用上一轮强制确认。',
        questions: ['请按当前提示调整刻字参数后重试。'],
        blockingReason: `surface_engraving_${retry.code || 'force_confirmation_recheck_failed'}`,
        currentEngravings,
        draft: {
          ...previousDraft,
          original_feature_conflict_confirmation: null,
        },
        preflight: retry,
      }),
    };
  }
  const forcedEngravings = candidateEngravings.map((item) => (
    item.id === confirmation.engraving_id
      ? {
          ...item,
          allow_original_feature_intersection: true,
          original_feature_intersection_source_hash: sourceHash,
        }
      : item
  ));
  const forcedPatch = buildSurfaceEngravingPatch(forcedEngravings);
  const forcedPatchValidation = await validateSurfaceEngravingPatch(forcedPatch, forcedEngravings, { python });
  if (forcedPatchValidation.status !== 'pass') {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: `强制刻字补丁未通过安全校验：${forcedPatchValidation.message}`,
        questions: ['请重新提交刻字要求。'],
        blockingReason: 'surface_engraving_force_confirmation_patch_rejected',
        currentEngravings,
      }),
    };
  }
  const forcedPreflight = await preflightSurfaceEngravings({
    python,
    sourceCode,
    surfaceEngravings: forcedEngravings,
    patch: forcedPatch,
  });
  if (forcedPreflight.status !== 'pass') {
    return {
      status: 'needs_input',
      response: buildSurfaceEngravingNeedsInput({
        message: forcedPreflight.message || '强制刻字仍未通过其余安全检查。',
        questions: ['请调整文字、位置、字号或目标平面后重试。'],
        blockingReason: `surface_engraving_${forcedPreflight.code || 'force_confirmation_failed'}`,
        currentEngravings,
        preflight: forcedPreflight,
      }),
    };
  }
  return {
    status: 'ok',
    surface_engravings: forcedEngravings,
    surface_engraving_operations: replaceOperationEngravings(reapplied.operations, forcedEngravings),
    surface_engraving_patch: forcedPatch,
    surface_engraving_preflight: forcedPreflight,
    surface_engraving_draft: null,
    surface_engraving_turns: [],
    surface_engraving_unsupported_layout: null,
    original_feature_intersection_override: {
      engraving_id: confirmation.engraving_id,
      surface_id: confirmation.surface_id,
      surface_label: confirmation.conflict.surface_label,
      source_hash: sourceHash,
    },
    summary: `${summarizeSurfaceEngravings(forcedEngravings)}已按你的明确确认强制应用；与原模型边界或孔位相交的文字部分可能被裁断。`,
    clean_cadquery_code: sourceCode,
  };
}

function buildOriginalFeatureConflictConfirmation({
  body = {},
  sourceCode = '',
  surfaceEngravings = [],
  preflight = {},
  surfaceLabel = '',
} = {}) {
  const normalized = normalizeSurfaceEngravings(surfaceEngravings);
  return {
    schema_version: FORCE_CONFIRMATION_SCHEMA_VERSION,
    task_id: normalizeString(body.taskId || body.task_id || currentDesignStateFromBody(body)?.id),
    source_hash: cleanCadQuerySourceHash(sourceCode),
    spec_hash: surfaceEngravingStateHash(normalized),
    engraving_id: normalizeString(preflight.details?.engraving_id),
    surface_id: normalizeString(preflight.details?.surface_id),
    conflict: compactOriginalFeatureConflict(preflight, surfaceLabel),
  };
}

function normalizeOriginalFeatureConflictConfirmation(value) {
  if (!isPlainObject(value)) return null;
  const conflict = isPlainObject(value.conflict) ? value.conflict : {};
  const result = {
    schema_version: normalizeString(value.schema_version),
    task_id: normalizeString(value.task_id),
    source_hash: normalizeString(value.source_hash).toLowerCase(),
    spec_hash: normalizeString(value.spec_hash).toLowerCase(),
    engraving_id: normalizeString(value.engraving_id),
    surface_id: normalizeString(value.surface_id),
    conflict: {
      code: normalizeString(conflict.code),
      surface_label: normalizeString(conflict.surface_label),
      reference_intersection_ratio: finiteNumberOrNull(conflict.reference_intersection_ratio),
      current_intersection_ratio: finiteNumberOrNull(conflict.current_intersection_ratio),
      reference_missing_volume: finiteNumberOrNull(conflict.reference_missing_volume),
      intersection_tolerance_volume: finiteNumberOrNull(conflict.intersection_tolerance_volume),
      max_font_height_mm: finiteNumberOrNull(conflict.max_font_height_mm),
      face_bounds: normalizeFiniteNumberArray(conflict.face_bounds, 4),
      text_size_uv: normalizeFiniteNumberArray(conflict.text_size_uv, 2),
    },
  };
  if (result.schema_version !== FORCE_CONFIRMATION_SCHEMA_VERSION
    || !result.task_id
    || !SOURCE_HASH_PATTERN.test(result.source_hash)
    || !SOURCE_HASH_PATTERN.test(result.spec_hash)
    || !result.engraving_id
    || !result.surface_id
    || result.conflict.code !== ORIGINAL_FEATURE_CONFLICT_CODE) return null;
  return result;
}

function compactOriginalFeatureConflict(preflight = {}, surfaceLabel = '') {
  const details = preflight.details || {};
  return {
    code: ORIGINAL_FEATURE_CONFLICT_CODE,
    surface_label: normalizeString(surfaceLabel),
    reference_intersection_ratio: finiteNumberOrNull(details.reference_intersection_ratio),
    current_intersection_ratio: finiteNumberOrNull(details.current_intersection_ratio),
    reference_missing_volume: finiteNumberOrNull(details.reference_missing_volume),
    intersection_tolerance_volume: finiteNumberOrNull(details.intersection_tolerance_volume),
    max_font_height_mm: finiteNumberOrNull(details.max_font_height_mm),
    face_bounds: normalizeFiniteNumberArray(details.face_bounds, 4),
    text_size_uv: normalizeFiniteNumberArray(details.text_size_uv, 2),
  };
}

function replaceOperationEngravings(operations = [], surfaceEngravings = []) {
  const byId = new Map(surfaceEngravings.map((item) => [item.id, item]));
  return (operations || []).map((operation) => {
    const id = normalizeString(operation?.engraving?.id || operation?.target_id);
    return id && byId.has(id) ? { ...operation, engraving: byId.get(id) } : operation;
  });
}

function cleanCadQuerySourceHash(sourceCode = '') {
  return crypto.createHash('sha256').update(stripSurfaceEngravingCode(sourceCode), 'utf8').digest('hex');
}

function surfaceEngravingStateHash(surfaceEngravings = []) {
  const canonical = normalizeSurfaceEngravings(surfaceEngravings).map((item) => {
    const {
      allow_original_feature_intersection: _allow,
      original_feature_intersection_source_hash: _sourceHash,
      ...spec
    } = item;
    return spec;
  });
  return crypto.createHash('sha256').update(JSON.stringify(canonical), 'utf8').digest('hex');
}

function surfaceLabelForId(currentDesignState = {}, surfaceId = '') {
  const targetId = normalizeString(surfaceId).toLowerCase();
  if (!targetId) return '';
  return normalizeModelSurfaces(
    currentDesignState?.engraving_surfaces
      || currentDesignState?.model_surfaces
      || currentDesignState?.cad_parameters?.engraving_surfaces
      || currentDesignState?.model_index?.surfaces,
  ).find((item) => item.id === targetId)?.label || '';
}

function normalizeFiniteNumberArray(value, length) {
  if (!Array.isArray(value) || value.length !== length) return [];
  const result = value.map(finiteNumber);
  return result.every(Number.isFinite) ? result : [];
}

function finiteNumberOrNull(value) {
  const result = finiteNumber(value);
  return Number.isFinite(result) ? result : null;
}

export function applySurfaceEngravingResultToBody(body = {}, result = {}) {
  const currentDesignState = currentDesignStateFromBody(body) || {};
  const revision = {
    status: 'ok',
    route_action: 'surface_engraving',
    prompt: normalizeString(body.latestUserMessage || body.latest_user_message || body.prompt),
    add_functions: [],
    remove_functions: [],
    replace_hardware_roles: [],
    remove_hardware_ids: [],
    force_selected_hardware_ids: [],
    hardware_face_overrides: {},
    parameter_overrides: {},
    surface_engraving_operations: result.surface_engraving_operations || [],
    surface_engraving_migration: result.surface_engraving_migration
      || body.surfaceEngravingMigration
      || body.surface_engraving_migration
      || currentDesignState.surface_engraving_migration
      || null,
    summary: result.summary || '',
    source: 'llm_surface_engraving',
  };
  return {
    ...body,
    prompt: currentDesignState.intent?.product_name || body.prompt || '当前模型刻字',
    currentDesignState: {
      ...currentDesignState,
      surface_engravings: result.surface_engravings || [],
      surface_engraving_patch: result.surface_engraving_patch || '',
      surface_engraving_preflight: result.surface_engraving_preflight || null,
      revision_intent: revision,
    },
    surfaceEngravings: result.surface_engravings || [],
    surfaceEngravingPatch: result.surface_engraving_patch || '',
    surfaceEngravingPreflight: result.surface_engraving_preflight || null,
    surfaceEngravingDraft: null,
    surfaceEngravingTurns: [],
    revisionIntent: revision,
    revision_intent: revision,
  };
}

export function injectSurfaceEngravingCode(sourceCode = '', surfaceEngravings = [], patch = '') {
  const cleanSource = stripSurfaceEngravingCode(sourceCode);
  const rawNormalized = normalizeSurfaceEngravings(surfaceEngravings);
  const normalized = invalidateSurfaceEngravingOverridesForSource(rawNormalized, cleanSource);
  const invalidatedOverride = normalized.some((item, index) => (
    item.allow_original_feature_intersection !== rawNormalized[index]?.allow_original_feature_intersection
  ));
  if (!normalized.length) return cleanSource;
  const templatePlan = detectTemplateEngravingPatchPlan(cleanSource);
  const resolvedPatch = templatePlan
    ? buildTemplateEngravingPatch(normalized, templatePlan)
    : invalidatedOverride
      ? buildSurfaceEngravingPatch(normalized)
      : normalizeString(patch) || buildSurfaceEngravingPatch(normalized);
  const block = [PATCH_START, HELPER_SOURCE, resolvedPatch, PATCH_END].join('\n\n');
  const resultIndex = cleanSource.lastIndexOf('\nresult =');
  const insertionIndex = resultIndex >= 0 ? resultIndex + 1 : cleanSource.length;
  const prefix = cleanSource.slice(0, insertionIndex).replace(/\s*$/, '');
  const suffix = cleanSource.slice(insertionIndex).replace(/^\s*/, '');
  return `${prefix}\n\n${block}\n\n${suffix}`.trimEnd() + '\n';
}

function detectTemplateEngravingPatchPlan(sourceCode = '') {
  if (!/^\s*TEMPLATE_PARTS_SCHEMA_VERSION\s*=\s*["']template_parts_v1["']/m.test(sourceCode)) {
    return null;
  }
  const hasVariable = (name) => new RegExp(`^\\s*${name}\\s*=`, 'm').test(sourceCode);
  if (hasVariable('base_part') && hasVariable('lid_part')) {
    return { baseVariable: 'base_part', lidVariable: 'lid_part' };
  }
  if (hasVariable('bottom_shell') && hasVariable('top_cover')) {
    return { baseVariable: 'bottom_shell', lidVariable: 'top_cover' };
  }
  if (hasVariable('main_body')) {
    return { baseVariable: 'main_body', lidVariable: 'main_body', singlePart: true };
  }
  return null;
}

function buildTemplateEngravingPatch(surfaceEngravings = [], plan = {}) {
  const baseVariable = normalizeString(plan.baseVariable);
  const lidVariable = normalizeString(plan.lidVariable);
  if (!baseVariable || !lidVariable) return buildSurfaceEngravingPatch(surfaceEngravings);
  const singlePart = plan.singlePart === true || baseVariable === lidVariable;
  const adapted = surfaceEngravings.map((item) => (
    singlePart ? { ...item, target_part: 'base_part' } : item
  ));
  const lines = [
    `surface_engraving_specs = ${pythonLiteral(adapted)}`,
    `base_part, lid_part = apply_surface_engraving_patch(${baseVariable}, ${lidVariable}, surface_engraving_specs)`,
  ];
  // Keep explicit mappings for every template, including canonical variable names.
  // This makes the adapter contract inspectable and remains a harmless Python
  // self-assignment when the source already uses base_part/lid_part.
  lines.push(`${baseVariable} = base_part`);
  if (lidVariable !== baseVariable) lines.push(`${lidVariable} = lid_part`);
  return lines.join('\n');
}

export function invalidateSurfaceEngravingOverridesForSource(surfaceEngravings = [], sourceCode = '') {
  const sourceHash = cleanCadQuerySourceHash(sourceCode);
  return normalizeSurfaceEngravings(surfaceEngravings).map((item) => {
    if (!item.allow_original_feature_intersection
      || item.original_feature_intersection_source_hash === sourceHash) return item;
    const {
      allow_original_feature_intersection: _allow,
      original_feature_intersection_source_hash: _confirmedSourceHash,
      ...rest
    } = item;
    return rest;
  });
}

export function stripSurfaceEngravingCode(sourceCode = '') {
  const source = String(sourceCode || '');
  const start = source.indexOf(PATCH_START);
  if (start < 0) return source;
  const end = source.indexOf(PATCH_END, start);
  if (end < 0) return source.slice(0, start).trimEnd() + '\n';
  return `${source.slice(0, start)}${source.slice(end + PATCH_END.length)}`
    .replace(/\n{3,}/g, '\n\n')
    .trimEnd() + '\n';
}

export function buildSurfaceEngravingPatch(surfaceEngravings = []) {
  const normalized = normalizeSurfaceEngravings(surfaceEngravings);
  if (!normalized.length) return '';
  return [
    `surface_engraving_specs = ${pythonLiteral(normalized)}`,
    'base_part, lid_part = apply_surface_engraving_patch(base_part, lid_part, surface_engraving_specs)',
  ].join('\n');
}

export async function validateSurfaceEngravingPatch(patch = '', surfaceEngravings = [], { python } = {}) {
  const expected = normalizeSurfaceEngravings(surfaceEngravings);
  if (!expected.length && !normalizeString(patch)) {
    return { status: 'pass', message: '空刻字状态无需补丁。', surface_engravings: [] };
  }
  if (!python || !normalizeString(patch)) {
    return { status: 'fail', message: '缺少 Python AST 校验环境或刻字补丁。' };
  }
  const astScript = [
    'import ast, json, sys',
    'source = sys.stdin.read()',
    'try:',
    '    tree = ast.parse(source, mode="exec")',
    '    if len(tree.body) != 2:',
    '        raise ValueError("patch must contain exactly two statements")',
    '    first, second = tree.body',
    '    if not isinstance(first, ast.Assign) or len(first.targets) != 1 or not isinstance(first.targets[0], ast.Name) or first.targets[0].id != "surface_engraving_specs":',
    '        raise ValueError("first statement must assign surface_engraving_specs")',
    '    specs = ast.literal_eval(first.value)',
    '    if not isinstance(second, ast.Assign) or len(second.targets) != 1 or not isinstance(second.targets[0], ast.Tuple):',
    '        raise ValueError("second statement must assign base_part and lid_part")',
    '    target_names = [item.id for item in second.targets[0].elts if isinstance(item, ast.Name)]',
    '    if target_names != ["base_part", "lid_part"]:',
    '        raise ValueError("second statement targets are not allowed")',
    '    call = second.value',
    '    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name) or call.func.id != "apply_surface_engraving_patch":',
    '        raise ValueError("only apply_surface_engraving_patch may be called")',
    '    if len(call.args) != 3 or any(not isinstance(item, ast.Name) for item in call.args):',
    '        raise ValueError("engraving helper must receive exactly three named variables")',
    '    call_names = [item.id for item in call.args]',
    '    if call_names != ["base_part", "lid_part", "surface_engraving_specs"] or call.keywords:',
    '        raise ValueError("engraving helper arguments are invalid")',
    '    allowed = (ast.Module, ast.Assign, ast.Name, ast.Store, ast.Load, ast.List, ast.Tuple, ast.Dict, ast.Constant, ast.Call, ast.UnaryOp, ast.USub, ast.UAdd)',
    '    if any(not isinstance(node, allowed) for node in ast.walk(tree)):',
    '        raise ValueError("patch contains a forbidden AST node")',
    '    print(json.dumps({"status": "pass", "specs": specs}, ensure_ascii=False))',
    'except Exception as error:',
    '    print(json.dumps({"status": "fail", "message": str(error)}, ensure_ascii=False))',
  ].join('\n');
  const processResult = await runProcess(python, ['-c', astScript], {
    input: patch,
    timeoutMs: 15000,
  });
  if (processResult.exitCode !== 0) {
    return { status: 'fail', message: processResult.stderr || 'Python AST 校验执行失败。' };
  }
  let parsed;
  try {
    parsed = JSON.parse(lastNonEmptyLine(processResult.stdout));
  } catch {
    return { status: 'fail', message: 'Python AST 校验没有返回合法 JSON。' };
  }
  if (parsed.status !== 'pass') return { status: 'fail', message: parsed.message || '刻字补丁结构不合法。' };
  const patchSpecs = normalizeSurfaceEngravings(parsed.specs);
  if (!Array.isArray(parsed.specs) || patchSpecs.length !== parsed.specs.length) {
    return { status: 'fail', message: '刻字补丁包含无法识别或越界的参数。', ast_safe: true };
  }
  if (JSON.stringify(patchSpecs) !== JSON.stringify(expected)) {
    return { status: 'fail', message: '刻字补丁参数与结构化刻字状态不一致。', ast_safe: true };
  }
  return { status: 'pass', message: '刻字补丁通过 AST 白名单校验。', surface_engravings: patchSpecs };
}

export async function preflightSurfaceEngravings({ python, sourceCode, surfaceEngravings, patch } = {}) {
  const normalized = normalizeSurfaceEngravings(surfaceEngravings);
  if (!normalized.length) return { status: 'pass', report: [] };
  if (!python || !normalizeString(sourceCode)) {
    return { status: 'pending', message: '缺少 CadQuery 预检环境，刻字将在真实构建阶段校验。', report: [] };
  }
  const patchedSource = injectSurfaceEngravingCode(sourceCode, normalized, patch);
  const sourceValidation = await preflightCadQueryCode({ python, code: patchedSource });
  if (sourceValidation.status === 'fail') {
    return {
      status: 'fail',
      code: 'cadquery_source_rejected',
      message: '当前 CadQuery 源码或刻字注入结果未通过静态安全检查。',
      details: sourceValidation.details || {},
    };
  }
  const tempRoot = await mkdtemp(path.join(os.tmpdir(), 'zwcad-surface-engraving-'));
  const sourcePath = path.join(tempRoot, 'engraving-preflight.py');
  const runnerPath = path.join(tempRoot, 'run-preflight.py');
  const runnerSource = [
    'import json, runpy, sys',
    `source_path = ${JSON.stringify(sourcePath)}`,
    'def show_object(*args, **kwargs):',
    '    return None',
    'try:',
    '    ns = runpy.run_path(source_path, init_globals={"show_object": show_object})',
    '    print(json.dumps({"status": "pass", "report": ns.get("SURFACE_ENGRAVING_REPORT", [])}, ensure_ascii=False))',
    'except Exception as error:',
    '    print(json.dumps({',
    '        "status": "fail",',
    '        "code": getattr(error, "code", "cadquery_preflight_failed"),',
    '        "message": str(error),',
    '        "details": getattr(error, "details", {}),',
    '    }, ensure_ascii=False))',
  ].join('\n');
  try {
    await writeFile(sourcePath, patchedSource, 'utf8');
    await writeFile(runnerPath, runnerSource, 'utf8');
    const processResult = await runProcess(python, [runnerPath], { cwd: tempRoot, timeoutMs: RUN_TIMEOUT_MS });
    if (processResult.exitCode !== 0) {
      return {
        status: 'fail',
        code: 'cadquery_preflight_execution_failed',
        message: processResult.stderr || 'CadQuery 刻字预检执行失败。',
        details: {},
      };
    }
    try {
      return JSON.parse(lastNonEmptyLine(processResult.stdout));
    } catch {
      return {
        status: 'fail',
        code: 'cadquery_preflight_invalid_output',
        message: 'CadQuery 刻字预检没有返回合法结果。',
        details: {},
      };
    }
  } finally {
    const resolvedTemp = path.resolve(tempRoot);
    const resolvedSystemTemp = path.resolve(os.tmpdir());
    if (resolvedTemp.startsWith(`${resolvedSystemTemp}${path.sep}`)) {
      await rm(resolvedTemp, { recursive: true, force: true });
    }
  }
}

export function summarizeSurfaceEngravings(surfaceEngravings = []) {
  const normalized = normalizeSurfaceEngravings(surfaceEngravings);
  if (!normalized.length) return '已删除全部模型表面刻字。';
  return `当前模型包含 ${normalized.length} 条凹刻：${normalized.map((item) => {
    const lines = Array.isArray(item.lines) ? item.lines : [item.text];
    const layout = lines.length > 1 ? `${lines.length} 行：${lines.join(' / ')}` : item.text;
    return `${layout}（${item.font_height_mm}mm）`;
  }).join('、')}。`;
}

function buildSurfaceEngravingSystemPrompt() {
  return [
    '你是 ZW-CAD-intent 的 surface-engraving 工具。',
    '只返回 JSON，不要使用 Markdown。',
    '严格遵守下面的 skill 契约，并阅读当前未刻字 CadQuery 源码确定目标外部平面的法向量、参考点和文字横向。',
    SKILL_SOURCE,
    '后端固定调用 apply_surface_engraving_patch(base_part, lid_part, surface_engraving_specs)，不要复制或重写 helper。',
    '输出 operations，每项 action 只能是 add、update、remove、clear。',
    '无论信息是否完整，都要在 operations 或 surface_engraving_draft.pending_operations 中返回本轮已经识别出的部分字段；不得丢弃前几轮草稿字段。',
    'add/update 的 engraving 只填写能够从自然语言、草稿、现有刻字或源码可靠推导的字段；update 通过 target_id 引用现有刻字，未修改字段可以省略并继承。',
    '用户没有说明平面内位置时可以推断为中央；没有说明字号时允许留空，由后端按目标面容量安全计算。',
    '理解同句多字段、倒装、省略、毫米简称和多轮补充。不要因为用户没有说内部字段名而追问。',
    '如果用户要求两行、多行、换行或分两排，保留其他已识别字段，并在 requested_layout 中记录 multiline=true、line_count；有明确换行时输出 engraving.lines。后端会执行受限的多行凹刻。',
    '面向用户的 message 和 questions 必须只使用中文自然语言，明确告诉用户应该怎样回复。不得展示 target_part、anchor、top_left、offset_u_mm、font_height_mm、normal_hint 等内部字段或英文枚举，也不得要求用户输入坐标或法向量。',
    '只有刻字内容缺失、目标外部平面确实有重要歧义或多个已有刻字无法确定修改目标时才请求用户补充。',
    '不要选择曲面，不要生成凸字。深度始终为 0.6mm。',
    '不得自行输出 allow_original_feature_intersection、original_feature_intersection_source_hash 或 original_feature_conflict_confirmation；这些字段只能由服务器在有效冲突确认后追加。',
  ].join('\n\n');
}

function surfaceEngravingDraftFromBody(body = {}) {
  const explicit = body.surfaceEngravingDraft || body.surface_engraving_draft;
  const lastNeedsInput = body.lastNeedsInput || body.last_needs_input || {};
  const taskId = normalizeString(body.taskId || body.task_id || currentDesignStateFromBody(body)?.id);
  const draft = normalizeSurfaceEngravingDraft(
    explicit || lastNeedsInput.surface_engraving_draft || lastNeedsInput.surfaceEngravingDraft || null,
    taskId,
  );
  if (draft?.task_id && taskId && draft.task_id !== taskId) return null;
  return draft;
}

function normalizeSurfaceEngravingDraft(value, taskId = '') {
  if (!isPlainObject(value)) return null;
  const pending = Array.isArray(value.pending_operations)
    ? value.pending_operations
    : Array.isArray(value.operations)
      ? value.operations
      : [];
  const userTurns = normalizeEngravingTurns(value.user_turns || value.userTurns);
  return {
    schema_version: DRAFT_SCHEMA_VERSION,
    draft_id: normalizeString(value.draft_id || value.draftId),
    task_id: normalizeString(value.task_id || value.taskId || taskId),
    pending_operations: pending.map(normalizePartialOperation).filter(Boolean),
    surface_engravings: normalizeSurfaceEngravings(value.surface_engravings || value.surfaceEngravings),
    provided_fields: normalizeStringList(value.provided_fields || value.providedFields),
    inferred_fields: normalizeStringList(value.inferred_fields || value.inferredFields),
    missing_fields: normalizeStringList(value.missing_fields || value.missingFields),
    user_turns: userTurns,
    requested_layout: normalizeRequestedLayout(value.requested_layout || value.requestedLayout),
    suggested_font_height_mm: finiteNumberOrNull(value.suggested_font_height_mm ?? value.suggestedFontHeightMm),
    original_feature_conflict_confirmation: normalizeOriginalFeatureConflictConfirmation(
      value.original_feature_conflict_confirmation || value.originalFeatureConflictConfirmation,
    ),
  };
}

function collectSurfaceEngravingTurns(body = {}, prompt = '', previousDraft = null) {
  const explicit = previousDraft
    ? normalizeEngravingTurns(body.surfaceEngravingTurns || body.surface_engraving_turns)
    : [];
  const previous = normalizeEngravingTurns(previousDraft?.user_turns);
  const projectTurns = (Array.isArray(body.projectConversation) ? body.projectConversation : [])
    .slice(-20)
    .map((turn) => ({ role: 'user', content: normalizeString(turn?.user_message) }))
    .filter((turn) => turn.content && isLikelySurfaceEngravingTurn(turn.content, Boolean(previousDraft)));
  const answers = Array.isArray(body.userAnswers) ? body.userAnswers : Array.isArray(body.user_answers) ? body.user_answers : [];
  const answerTurns = answers.slice(-10).map((item) => ({
    role: 'user',
    content: normalizeString(item).replace(/^(?:修改意见|补充信息|用户需求|修改需求)\s*[：:]\s*/, ''),
  })).filter((item) => item.content && isLikelySurfaceEngravingTurn(item.content, Boolean(previousDraft)));
  const combined = [...projectTurns, ...previous, ...explicit, ...answerTurns, { role: 'user', content: prompt }];
  const result = [];
  for (const turn of combined) {
    const content = normalizeString(turn?.content || turn?.text || turn);
    if (!content) continue;
    const role = normalizeString(turn?.role) || 'user';
    if (result.at(-1)?.content === content && result.at(-1)?.role === role) continue;
    result.push({ role, content });
  }
  return result.slice(-12);
}

function isClearlyUnrelatedMechanicalEdit(value = '') {
  const text = normalizeString(value);
  if (!text) return false;
  if (/(?:刻字|文字|字样|铭文|编号|这条字|上面的字|刚才的字)/i.test(text)
    && /(?:移动|偏移|挪动|调整位置|向左|向右|向上|向下|避开|绕开|躲开)/i.test(text)) return false;
  const engravingOnNamedSurface = /(?:上盖|盖子|顶面|底壳|底面|正面|前面|背面|后面|左侧面?|右侧面?|大斜面|主斜面|L\s*形卡槽外斜面|卡槽斜面|小斜面|斜面).{0,12}(?:上的|上|表面的)?(?:刻字|文字|字样|铭文|上面的字|字)/i.test(text);
  const strongMechanicalAction = /圆角|倒圆|倒角|切角|磨圆|削平|开孔|扩孔|封孔|挖槽|加厚|减薄|移动硬件|删除结构|(?:开|打|钻|做|新增|增加|添加).{0,12}(?:孔|槽|开口)|(?:删除|删掉|移除|去掉).{0,12}(?:孔|槽口|凹槽|开口)|(?:孔|槽口|开口).{0,12}(?:加大|放大|缩小|调整|移动|封堵)|(?:凸台|台阶|卡扣|支架|加强筋|螺柱).{0,12}(?:削掉|切掉|磨掉|删除|去掉)|\b(?:fillet|chamfer)\b/i.test(text);
  if (engravingOnNamedSurface && !strongMechanicalAction) return false;
  const colloquialEdgeOrFace = /(?:磨圆|修圆|磨成圆|修成圆|做圆|圆滑|去锐边|去掉锐边|削平|磨平).{0,16}(?:边线|边缘|棱边|顶边|底边|这个面|该面|平面|斜面)|(?:边线|边缘|棱边|顶边|底边|这个面|该面|平面|斜面).{0,16}(?:磨圆|修圆|磨成圆|修成圆|做圆|圆滑|去锐边|去掉锐边|削平|磨平)/i;
  const faceDimensionShorthand = /(?:给|把|将|在)?\s*(?:这个|那个|该)?\s*(?:面|平面|斜面|边|边线|边缘|棱边).{0,12}(?:做|加|设为|设置为|改成|改为)?\s*(?:R|C)\s*\d+(?:\.\d+)?(?:\s*mm|\s*毫米)?/i;
  const openingFeature = '(?:散热孔|通风孔|开孔|开口|按钮孔|螺丝孔|安装孔|孔径|孔位|圆孔|方孔|孔|槽口|槽|窗口)';
  const openingAction = '(?:(?<![避绕躲])开|打|钻|增加|添加|新增|扩大|扩孔|加大|放大|变大|缩小|缩径|变小|移动|移到|调整|修改|改成|改为|封上?|封闭|封堵|堵上?|删除|删掉|移除|去掉)';
  const changesOpening = new RegExp(`${openingAction}.{0,16}${openingFeature}|${openingFeature}.{0,16}${openingAction}`, 'i').test(text)
    || /(?:做|留|预留|挖|切)(?:一个|个|出)?(?:.{0,12}(?:直径|宽|长|\d+(?:\.\d+)?\s*(?:mm|毫米)))?.{0,8}(?:圆孔|方孔|孔|槽口|槽|开口|窗口)/i.test(text);
  const removesReferencedStructure = /(?:删除|删掉|去掉|削掉|切掉|磨掉).{0,20}(?:凸台|台阶|卡扣|支架|加强筋|螺柱|螺丝柱)|(?:凸台|台阶|卡扣|支架|加强筋|螺柱|螺丝柱).{0,20}(?:删除|删掉|去掉|削掉|切掉|磨掉)|(?:删除|删掉|去掉|削掉|切掉).{0,12}(?:刻字|文字|字样|编号|logo).{0,8}(?:所在|下面|旁边|附近)(?:的)?(?:平面|斜面|面|凸台|台阶)/i.test(text);
  if (colloquialEdgeOrFace.test(text) || faceDimensionShorthand.test(text) || changesOpening || removesReferencedStructure) return true;
  if (isSurfaceEngravingPrompt(text)) return false;
  if (/(?:在|往|给).{0,20}(?:开|打|钻)(?:一个|个)?\s*\d*(?:\.\d+)?\s*(?:mm|毫米)?\s*孔|(?:把|将).{1,24}(?:移动|移到|挪到|旋转|删除|移除)/i.test(text)) return true;
  const action = /圆角|倒圆|倒角|切角|削平|开孔|扩孔|封孔|挖槽|加厚|减薄|壁厚|厚度|移动|移到|挪到|旋转|删除|撤销|\b(?:fillet|chamfer|move|rotate|undo)\b/i;
  const target = /模型|主体|底壳|上盖|斜面|平面|边|边线|棱边|孔|槽|硬件|模块|传感器|主控|电池|接口|最高处|最低处/i;
  return action.test(text) && target.test(text);
}

function isLikelySurfaceEngravingTurn(value = '', hasDraft = false) {
  const text = normalizeString(value);
  if (!text) return false;
  if (isSurfaceEngravingPrompt(text)) return true;
  if (!hasDraft) return false;
  return /^(?:\d+(?:\.\d+)?\s*(?:mm|毫米)|(?:改成|改为|换成|换为|调整为)\s*\d+(?:\.\d+)?\s*(?:mm|毫米)?|(?:那就|就按|保持|继续|还是)?.{0,6}(?:单行|一行|两行|多行|换行))/.test(text)
    || /(?:上盖|盖子|顶面|底壳|底面|前面|后面|左侧|右侧|左边|右边|斜面).{0,16}(?:中央|中心|正中|左上|右上|左下|右下|角|边)/.test(text)
    || /(?:内容|文字|字样)\s*(?:是|为|改成|换成)?\s*[：:]?|[“"'‘][^”"'’\r\n]{1,64}[”"'’]/.test(text);
}

function normalizeEngravingTurns(value) {
  if (!Array.isArray(value)) return [];
  return value.map((turn) => {
    if (typeof turn === 'string') return { role: 'user', content: normalizeString(turn) };
    return { role: normalizeString(turn?.role) || 'user', content: normalizeString(turn?.content || turn?.text) };
  }).filter((turn) => turn.content).slice(-12);
}

function buildMergedSurfaceEngravingDraft({
  body,
  prompt,
  previousDraft,
  userTurns,
  rawResult,
  currentEngravings,
  currentDesignState,
} = {}) {
  const rawDraft = normalizeSurfaceEngravingDraft(rawResult?.surface_engraving_draft, body?.taskId || body?.task_id);
  const rawDraftOperations = rawDraft?.pending_operations || [];
  const rawResultOperations = Array.isArray(rawResult?.operations)
    ? rawResult.operations.map(normalizePartialOperation).filter(Boolean)
    : [];
  const rawOperations = [...rawDraftOperations, ...rawResultOperations];
  let pending = previousDraft?.pending_operations?.map((item) => ({ ...item, engraving: { ...(item.engraving || {}) } })) || [];
  const natural = naturalLanguageEngravingOperation(prompt, previousDraft, currentEngravings, currentDesignState);
  if (natural.explicit_add && pending.length && natural.operation) {
    const rawCandidate = [...rawDraftOperations, ...rawResultOperations]
      .reverse()
      .find((operation) => normalizeString(operation?.action).toLowerCase() === 'add');
    pending.push(rawCandidate ? mergePartialOperation(rawCandidate, natural.operation) : natural.operation);
  } else {
    pending = mergePendingOperations(pending, rawDraftOperations);
    pending = mergePendingOperations(pending, rawResultOperations);
    if (natural.operation) pending = mergePendingOperations(pending, [natural.operation]);
  }
  const naturalAction = normalizeString(natural.operation?.action).toLowerCase();
  if (currentEngravings.length > 1
    && ['update', 'remove'].includes(naturalAction)
    && !normalizeString(natural.operation?.target_id)
    && !previousDraft?.pending_operations?.some((operation) => normalizeString(operation?.target_id))) {
    const partialUpdate = normalizePartialOperation(natural.operation)
      || pending.find((operation) => normalizeString(operation?.action).toLowerCase() === 'update')
      || { action: 'update', target_id: '', engraving: {} };
    pending = [{ ...partialUpdate, action: 'update', target_id: '' }];
  }
  const providedFields = dedupeStrings([
    ...(previousDraft?.provided_fields || []),
    ...(rawDraft?.provided_fields || []),
    ...natural.provided_fields,
  ]);
  const inferredFields = dedupeStrings([
    ...(previousDraft?.inferred_fields || []),
    ...(rawDraft?.inferred_fields || []),
    ...fieldNamesFromOperations(rawOperations).filter((field) => !natural.provided_fields.includes(field)),
  ]).filter((field) => !providedFields.includes(field));
  const requestedLayout = {
    ...normalizeRequestedLayout(previousDraft?.requested_layout),
    ...normalizeRequestedLayout(rawDraft?.requested_layout),
    ...natural.requested_layout,
  };
  if (natural.single_line_confirmed
    || (natural.provided_fields.includes('text') && natural.requested_layout?.multiline !== true)) {
    requestedLayout.multiline = false;
    delete requestedLayout.line_count;
  }
  const taskId = normalizeString(body?.taskId || body?.task_id || previousDraft?.task_id || currentDesignState?.id);
  const draftId = previousDraft?.draft_id
    || rawDraft?.draft_id
    || `engraving_draft_${crypto.createHash('sha1').update(JSON.stringify({ taskId, turns: userTurns })).digest('hex').slice(0, 10)}`;
  return {
    schema_version: DRAFT_SCHEMA_VERSION,
    draft_id: draftId,
    task_id: taskId,
    pending_operations: pending,
    provided_fields: providedFields,
    inferred_fields: inferredFields,
    missing_fields: [],
    user_turns: userTurns,
    requested_layout: requestedLayout,
  };
}

function naturalLanguageEngravingOperation(prompt = '', previousDraft = null, currentEngravings = [], currentDesignState = {}) {
  const text = normalizeString(prompt);
  if (!text) return { operation: null, provided_fields: [], requested_layout: {}, single_line_confirmed: false };
  const provided = [];
  const engraving = {};
  const extractedText = extractEngravingText(text, previousDraft, currentEngravings);
  if (extractedText) {
    engraving.text = extractedText;
    if (/\r|\n/.test(extractedText)) {
      engraving.lines = splitEngravingLines(extractedText);
      engraving.layout_mode = 'multiline';
    }
    provided.push('text');
  }
  const fontHeight = extractFontHeight(text, previousDraft, extractedText);
  if (Number.isFinite(fontHeight)) {
    engraving.font_height_mm = fontHeight;
    provided.push('font_height_mm');
  }
  const surfaceIntentText = textWithoutEngravingContent(text, currentEngravings, extractedText);
  const targetPart = targetPartFromText(surfaceIntentText);
  if (targetPart) {
    engraving.target_part = targetPart;
    engraving.surface = surfaceIntentText;
    provided.push('target_part', 'surface');
  } else if (/(上盖|盖子|底壳|底座|底面|前面|后面|背面|正面|左侧|右侧|左面|右面|斜面)/i.test(surfaceIntentText)) {
    engraving.surface = surfaceIntentText;
    provided.push('surface');
  }
  const anchor = anchorFromText(surfaceIntentText);
  if (anchor) {
    engraving.anchor = anchor;
    provided.push('anchor');
  }
  const offsetU = extractDirectionalOffset(text, 'u');
  const offsetV = extractDirectionalOffset(text, 'v');
  if (Number.isFinite(offsetU)) {
    engraving.offset_u_mm = offsetU;
    provided.push('offset_u_mm');
  }
  if (Number.isFinite(offsetV)) {
    engraving.offset_v_mm = offsetV;
    provided.push('offset_v_mm');
  }
  const rotation = text.match(/(?:旋转|转动)\s*(-?\d+(?:\.\d+)?)\s*(?:度|°)?/i);
  if (rotation) {
    engraving.rotation_deg = Number(rotation[1]);
    provided.push('rotation_deg');
  }
  const previousOperation = previousDraft?.pending_operations?.[0] || null;
  const explicitClear = /(?:删除|清除|移除).{0,8}(?:全部|所有).{0,8}(?:刻字|文字)|清空刻字/.test(text);
  const explicitRemove = !explicitClear && /(?:删除|删掉|清除|移除|取消).{0,12}(?:刻字|文字|字样)|(?:刻字|文字|字样).{0,12}(?:删除|删掉|清除|移除|取消)/.test(text);
  const explicitUpdate = /(?:改成|换成|修改|调整|变成|改为|换为)/.test(text);
  const explicitAdd = /(?:再|另外|新增|追加|多).{0,6}(?:刻|写|印|标|加)|再来一条|(?:新增|追加).{0,6}(?:文字|字样|刻字)/.test(text);
  const layoutOnly = isLayoutOrFontOnlyMessage(text);
  let action = previousOperation?.action || '';
  let targetId = normalizeString(previousOperation?.target_id || previousOperation?.targetId);
  if (explicitClear) action = 'clear';
  else if (explicitRemove) action = 'remove';
  else if (explicitUpdate && previousOperation?.action === 'add' && !previousOperation?.target_id) action = 'add';
  else if (explicitUpdate) action = 'update';
  else if (explicitAdd) action = 'add';
  else if (!action && layoutOnly && currentEngravings.length === 1) action = 'update';
  else if (!action) action = 'add';
  if ((action === 'update' || action === 'remove') && !targetId) {
    targetId = matchExistingSurfaceEngravingId(text, currentEngravings, currentDesignState);
    if (!targetId && currentEngravings.length === 1) targetId = currentEngravings[0].id;
  }
  const requestedLayout = detectRequestedLayout(text);
  const singleLineConfirmed = isSingleLineLayoutConfirmation(text);
  if (singleLineConfirmed) requestedLayout.multiline = false;
  const normalizedProvided = dedupeStrings(provided);
  const operation = action === 'clear'
    ? { action: 'clear' }
    : action === 'remove'
      ? { action: 'remove', target_id: targetId }
      : { action, target_id: targetId, engraving, provided_fields: normalizedProvided };
  return {
    operation,
    provided_fields: normalizedProvided,
    requested_layout: requestedLayout,
    single_line_confirmed: singleLineConfirmed,
    explicit_add: explicitAdd,
  };
}

function isSingleLineLayoutConfirmation(value = '') {
  return /(?:保持|继续|就按|改成|使用|还是).{0,4}单行|(?:单行|一行)(?:就行|即可|就好|继续)|就刻一行|那就单行|(?:不|不要|别|不用|无需|取消)\s*换行|(?:改成|换成|保持)一行|^\s*单行\s*$/.test(normalizeString(value));
}

function extractEngravingText(prompt = '', previousDraft = null, currentEngravings = []) {
  const text = normalizeString(prompt);
  const firstLine = text.match(/第一行\s*(?:是|为|写|刻)?\s*[：:]?\s*([^，。；;\r\n]+)/i);
  const secondLine = text.match(/第二行\s*(?:是|为|写|刻)?\s*[：:]?\s*([^，。；;\r\n]+)/i);
  if (firstLine?.[1] && secondLine?.[1]) return [normalizeString(firstLine[1]), normalizeString(secondLine[1])].join('\n');
  if (hasMultilineTextContent(text)) {
    const quotedMultiline = text.match(/[“"'‘]([^”"'’]*\r?\n[^”"'’]*)[”"'’]/);
    if (quotedMultiline?.[1]) return splitEngravingLines(quotedMultiline[1]).join('\n');
    const content = text.match(/(?:内容|文字|字样)\s*(?:是|为|改成|换成)?\s*[：:]?\s*([\s\S]+)/i)?.[1] || '';
    const contentLines = splitEngravingLines(content).filter((line) => !/^(?:字高|字号|字体高度|字体大小|位置|刻在|放在|位于|目标|旋转|转动)/i.test(line));
    if (contentLines.length > 1) return contentLines.join('\n');
  }
  const quotedValues = [...text.matchAll(/[“"'‘]([^”"'’\r\n]{1,64})[”"'’]/g)]
    .map((match) => normalizeString(match[1]))
    .filter(Boolean);
  if (/(?:改成|换成|修改为|调整为|变成|改为|换为)/.test(text) && quotedValues.length >= 2) {
    return quotedValues.at(-1);
  }
  const mentionedExisting = uniquelyMentionedExistingEngraving(text, currentEngravings);
  if (mentionedExisting) {
    const afterExisting = text.slice(text.indexOf(mentionedExisting.text) + mentionedExisting.text.length);
    const replacement = afterExisting.match(/^\s*(?:改成|换成|修改为|调整为|变成|改为|换为)\s*[“"'‘]?([^，。,.；;”"'’\r\n]{1,64})/i);
    const replacementText = cleanExtractedEngravingText(replacement?.[1]);
    if (replacementText) return replacementText;
  }
  const explicitQuotedText = text.match(/(?:内容|文字|字样|刻上|刻下|刻字|写上|印上|标上|写着|刻着)\s*(?:是|为|改成|换成)?\s*[：:]?\s*[“"'‘]([^”"'’\r\n]{1,64})[”"'’]/i);
  if (explicitQuotedText?.[1]) return normalizeString(explicitQuotedText[1]);
  const patterns = [
    /(?:内容|文字|字样)\s*(?:是|为|改成|换成)?\s*[：:]?\s*[“"'‘]([^”"'’\r\n]{1,64})[”"'’]/i,
    /(?:把|将)?(?:这条|上面的|刚才的|原来的)?\s*(?:文字|刻字|字样)\s*(?:改成|换成|修改为|调整为|变成|改为|换为)\s*[“"'‘]?([^，。,.；;”"'’\r\n]{1,64})/i,
    /[“"'‘]([^”"'’\r\n]{1,64})[”"'’]/,
    /(?:内容|文字|字样)\s*(?:是|为|改成|换成)?\s*[：:]?\s*([^，。,.；;\r\n]{1,64})/i,
    /(?:刻|写|印|标|加)\s*(?:一条|一行)\s*[：:]?\s*([^，。,.；;\r\n]{1,64})/i,
    /(?:刻上|刻下|刻字|写上|印上|标上|写着|刻着)\s*([^，。,.；;\r\n]{1,64})/i,
  ];
  for (const pattern of patterns) {
    const match = text.match(pattern);
    const value = cleanExtractedEngravingText(match?.[1]);
    if (value && !/^(?:字高|字体高度|字号)?\s*\d+(?:\.\d+)?\s*(?:mm|毫米)?$/i.test(value)) return value;
  }
  const missing = previousDraft?.missing_fields || [];
  if (missing.includes('文字内容') && text.length <= MAX_TEXT_LENGTH && !/[\r\n]|(?:mm|毫米|字高|字体|字号|左侧|右侧|上盖|底壳|单行|两行|多行|换行)/i.test(text)) {
    return text.replace(/^[“"'‘]|[”"'’]$/g, '').trim();
  }
  return '';
}

function cleanExtractedEngravingText(value = '') {
  return normalizeString(value)
    .replace(/\s*(?:字高|字号|字体高度|字体大小)\s*[：:]?\s*\d+(?:\.\d+)?\s*(?:mm|毫米)?[\s\S]*$/i, '')
    .replace(/(.+?)\s*高\s*\d+(?:\.\d+)?(?:\s*(?:mm|毫米))?[\s\S]*$/i, '$1')
    .replace(/\s+(?:旋转|转动|放在|刻在|位于|保持单行|单行|两行|多行|换行)[\s\S]*$/i, '')
    .replace(/^[“"'‘]|[”"'’]$/g, '')
    .trim();
}

function uniquelyMentionedExistingEngraving(text = '', currentEngravings = []) {
  const mentioned = (currentEngravings || []).filter((item) => {
    const content = normalizeString(item?.text);
    return content && normalizeString(text).includes(content);
  });
  return mentioned.length === 1 ? mentioned[0] : null;
}

function textWithoutEngravingContent(text = '', currentEngravings = [], extractedText = '') {
  let result = normalizeString(text).replace(/[“"'‘][^”"'’\r\n]{1,64}[”"'’]/g, ' ');
  if (extractedText) result = result.split(extractedText).join(' ');
  if (/(?:改成|换成|修改为|调整为|变成|改为|换为)/.test(result)) {
    for (const item of currentEngravings || []) {
      const content = normalizeString(item?.text);
      if (content) result = result.split(content).join(' ');
    }
  }
  return result;
}

function extractFontHeight(prompt = '', previousDraft = null, extractedText = '') {
  const text = normalizeString(prompt);
  let parameterText = text.replace(/[“"'‘][^”"'’\r\n]{1,64}[”"'’]/g, ' ');
  if (extractedText) parameterText = parameterText.replace(extractedText, ' ');
  const explicit = parameterText.match(/(?:字高|字体高度|字号|字体|高|(?:改成|改为|换成|换为|调整为))\s*(?:要|为|是)?\s*[：:]?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)?/i);
  if (explicit) return finiteNumber(explicit[1]);
  const bare = text.match(/^\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)(?:\s*[，,。.]|\s*$)/i);
  if (bare && (previousDraft || /刻|字|行|排/.test(text))) return finiteNumber(bare[1]);
  return NaN;
}

function extractDirectionalOffset(text = '', axis = 'u') {
  const patterns = axis === 'u'
    ? [[/向右(?:移动|偏移)?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)/, 1], [/向左(?:移动|偏移)?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)/, -1]]
    : [[/向上(?:移动|偏移)?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)/, 1], [/向下(?:移动|偏移)?\s*(\d+(?:\.\d+)?)\s*(?:mm|毫米)/, -1]];
  for (const [pattern, sign] of patterns) {
    const match = normalizeString(text).match(pattern);
    if (match) return sign * Number(match[1]);
  }
  return NaN;
}

function detectRequestedLayout(text = '') {
  const value = normalizeString(text);
  const multiline = /(?:两行|多行|换行|分成?\s*(?:两|二|三|四|\d+)\s*(?:行|排)|刻成\s*(?:两|二|三|四|\d+)\s*行|第一行|第二行|分两排)/.test(value)
    || hasMultilineTextContent(value);
  const countMatch = value.match(/(?:刻成|分成?|排成?)?\s*(\d+|两|二|三|四)\s*(?:行|排)/);
  const countMap = { 两: 2, 二: 2, 三: 3, 四: 4 };
  const lineCount = countMatch ? Number(countMap[countMatch[1]] || countMatch[1]) : multiline ? 2 : null;
  return multiline ? { multiline: true, line_count: lineCount } : {};
}

function splitEngravingLines(value = '', requestedCount = null) {
  const text = normalizeString(value).replace(/\r\n/g, '\n').replace(/\r/g, '\n');
  const explicit = text.split('\n').map((item) => item.trim()).filter(Boolean);
  if (explicit.length > 1) return explicit;
  const count = Number.isFinite(Number(requestedCount)) ? Math.max(2, Math.min(MAX_MULTILINE_LINES, Math.floor(Number(requestedCount)))) : 2;
  const chars = [...text];
  if (!chars.length) return [];
  const lines = [];
  const chunkSize = Math.max(1, Math.ceil(chars.length / count));
  for (let index = 0; index < chars.length; index += chunkSize) lines.push(chars.slice(index, index + chunkSize).join(''));
  return lines;
}

function hasMultilineTextContent(value = '') {
  const text = String(value || '');
  if (!/[\r\n]/.test(text)) return false;
  if (/[“"'‘][^”"'’]*[\r\n][^”"'’]*[”"'’]/.test(text)) return true;
  const contentWithNextLine = text.match(/(?:内容|文字|字样)\s*(?:是|为|改成|换成)?\s*[：:]?\s*[^\r\n]*\r?\n\s*([^\r\n]+)/i);
  if (contentWithNextLine) {
    return !/^(?:字高|字号|字体高度|字体大小|位置|刻在|放在|位于|目标|旋转|转动)/i.test(normalizeString(contentWithNextLine[1]));
  }
  const lines = text.split(/\r?\n/).map(normalizeString).filter(Boolean);
  return lines.length > 1 && lines.every((line) => !/^(?:在|内容|文字|字样|字高|字号|字体高度|位置|刻在|放在|位于|目标|旋转|转动)/.test(line));
}

function isLayoutOrFontOnlyMessage(text = '') {
  const value = normalizeString(text);
  return /^(?:\d+(?:\.\d+)?\s*(?:mm|毫米)|字高\s*\d+(?:\.\d+)?\s*(?:mm|毫米)?|改成\s*\d+(?:\.\d+)?\s*(?:mm|毫米)?|(?:保持|改成|刻成|分成|排成|不要|不|取消)?.{0,4}(?:单行|一行|两行|多行|换行|分两排))/.test(value);
}

function isAmbiguousExistingEngravingUpdate(text = '') {
  const value = normalizeString(text);
  if (!/(?:改|换|调整|变成|变为|改为|删除|删掉|移除|取消|单行|两行|多行|换行|字号|字高)/.test(value)) return false;
  const hasSpecificTarget = /(?:上盖|盖子|底壳|底座|底面|前面|后面|背面|正面|左侧|右侧|左面|右面|左边|右边|斜面|左上|右上|左下|右下|中央|中心|正中|“[^”]+”|"[^"]+"|'[^']+')/.test(value);
  return !hasSpecificTarget;
}

function normalizePartialOperation(value) {
  if (!isPlainObject(value)) return null;
  const action = normalizeString(value.action).toLowerCase();
  const engraving = isPlainObject(value.engraving) ? copyDefinedEngravingFields(value.engraving) : copyDefinedEngravingFields(value);
  return {
    action: ['add', 'update', 'remove', 'clear'].includes(action) ? action : '',
    target_id: normalizeString(value.target_id || value.targetId || value.id),
    engraving,
    provided_fields: normalizeStringList(value.provided_fields || value.providedFields),
    inferred_fields: normalizeStringList(value.inferred_fields || value.inferredFields),
    inherited_fields: normalizeStringList(value.inherited_fields || value.inheritedFields),
  };
}

function copyDefinedEngravingFields(value = {}) {
  const result = {};
  const keys = ['schema_version', 'id', 'text', 'lines', 'layout_mode', 'layoutMode', 'line_spacing_ratio', 'lineSpacingRatio', 'requested_layout', 'requestedLayout', 'target_part', 'targetPart', 'surface', 'surface_name', 'target_surface', 'face', 'surface_id', 'surfaceId', 'surface_area_hint_mm2', 'surfaceAreaHintMm2', 'surface_span_hint_mm', 'surfaceSpanHintMm', 'surface_selector_version', 'surfaceSelectorVersion', 'normal_hint', 'normalHint', 'point_hint', 'pointHint', 'x_direction', 'xDirection', 'anchor', 'offset_u_mm', 'offsetUMm', 'offset_v_mm', 'offsetVMm', 'rotation_deg', 'rotationDeg', 'font_height_mm', 'fontHeightMm', 'depth_mm', 'font_kind'];
  for (const key of keys) {
    if (value[key] !== undefined && value[key] !== null && value[key] !== '') result[key] = value[key];
  }
  return result;
}

function mergePendingOperations(current = [], incoming = []) {
  if (!incoming.length) return current;
  if (!current.length) return incoming.map((item) => ({ ...item, engraving: { ...(item.engraving || {}) } }));
  if (current.length === 1 && incoming.length === 1) return [mergePartialOperation(current[0], incoming[0])];
  const result = current.map((item) => ({ ...item, engraving: { ...(item.engraving || {}) } }));
  for (const operation of incoming) {
    const targetId = normalizeString(operation.target_id || operation.engraving?.id);
    const index = targetId ? result.findIndex((item) => normalizeString(item.target_id || item.engraving?.id) === targetId) : -1;
    if (index >= 0) result[index] = mergePartialOperation(result[index], operation);
    else result.push(operation);
  }
  return result;
}

function mergePartialOperation(base = {}, overlay = {}) {
  const engraving = { ...(base.engraving || {}) };
  const baseSurface = surfaceIdentityFromEngraving(base.engraving || {});
  const overlaySurface = surfaceIdentityFromEngraving(overlay.engraving || {});
  if (overlaySurface && baseSurface && overlaySurface !== baseSurface) clearSurfaceFrame(engraving);
  for (const [key, value] of Object.entries(overlay.engraving || {})) {
    if (value !== undefined && value !== null && value !== '') engraving[key] = value;
  }
  return {
    action: normalizeString(overlay.action) || normalizeString(base.action),
    target_id: normalizeString(overlay.target_id) || normalizeString(base.target_id),
    engraving,
    provided_fields: dedupeStrings([...(base.provided_fields || []), ...(overlay.provided_fields || [])]),
    inferred_fields: dedupeStrings([...(base.inferred_fields || []), ...(overlay.inferred_fields || [])]),
    inherited_fields: dedupeStrings([...(base.inherited_fields || []), ...(overlay.inherited_fields || [])]),
  };
}

function applySurfaceEngravingDraftDefaults(draft = {}, currentEngravings = []) {
  const next = { ...draft, pending_operations: [] };
  for (const raw of draft.pending_operations || []) {
    const operation = normalizePartialOperation(raw) || { action: '', target_id: '', engraving: {} };
    const operationProvided = new Set([
      ...(draft.pending_operations?.length === 1 ? draft.provided_fields || [] : []),
      ...(operation.provided_fields || []),
    ]);
    operation.inferred_fields = (operation.inferred_fields || []).filter((field) => !operationProvided.has(field));
    if (!operation.action) operation.action = 'add';
    if (operation.action === 'clear' || operation.action === 'remove') {
      next.pending_operations.push(operation);
      continue;
    }
    let existing = null;
    if (operation.action === 'update') {
      if (!operation.target_id && currentEngravings.length === 1) operation.target_id = currentEngravings[0].id;
      existing = currentEngravings.find((item) => item.id === operation.target_id) || null;
    }
    const inherited = { ...(existing || {}) };
    const requestedSurface = surfaceIdentityFromEngraving(operation.engraving || {});
    const existingSurface = surfaceIdentityFromEngraving(existing || {});
    if (requestedSurface && existingSurface && requestedSurface !== existingSurface) clearSurfaceFrame(inherited);
    const engraving = { ...inherited, ...(operation.engraving || {}) };
    const layout = normalizeRequestedLayout({
      ...(next.requested_layout || {}),
      ...(engraving.requested_layout || engraving.requestedLayout || {}),
      multiline: next.requested_layout?.multiline === true
        || engraving.layout_mode === 'multiline'
      || Array.isArray(engraving.lines) && engraving.lines.length > 1,
    });
    if (next.requested_layout?.multiline === false) {
      const singleText = operationProvided.has('text')
        ? normalizeString(engraving.text).replace(/\r?\n/g, '')
        : Array.isArray(engraving.lines) && engraving.lines.length
        ? engraving.lines.map(normalizeString).filter(Boolean).join('')
        : normalizeString(engraving.text).replace(/\r?\n/g, '');
      engraving.text = singleText;
      engraving.lines = singleText ? [singleText] : [];
      engraving.layout_mode = 'single_line';
      engraving.requested_layout = { multiline: false, line_count: 1, layout_mode: 'single_line' };
    } else if (layout.multiline === true && (!Array.isArray(engraving.lines) || engraving.lines.length <= 1) && normalizeString(engraving.text)) {
      engraving.lines = splitEngravingLines(engraving.text, layout.line_count);
      engraving.text = engraving.lines.join('\n');
      engraving.layout_mode = 'multiline';
      engraving.requested_layout = { ...layout, multiline: true, line_count: engraving.lines.length, layout_mode: 'multiline' };
    } else if (layout.multiline === true && Array.isArray(engraving.lines) && engraving.lines.length > 1) {
      engraving.text = engraving.lines.map(normalizeString).filter(Boolean).join('\n');
      engraving.layout_mode = 'multiline';
      engraving.requested_layout = { ...layout, multiline: true, line_count: engraving.lines.length, layout_mode: 'multiline' };
    }
    if (existing?.allow_original_feature_intersection
      && engravingGeometrySignature(existing) !== engravingGeometrySignature(engraving)) {
      delete engraving.allow_original_feature_intersection;
      delete engraving.original_feature_intersection_source_hash;
    }
    if (existing) operation.inherited_fields = dedupeStrings([...(operation.inherited_fields || []), ...Object.keys(existing)]);
    if (!ALLOWED_ANCHORS.has(normalizeString(engraving.anchor).toLowerCase())) {
      engraving.anchor = 'center';
      operation.inferred_fields = dedupeStrings([...(operation.inferred_fields || []), 'anchor']);
    }
    if (!Number.isFinite(finiteNumber(engraving.font_height_mm))) {
      engraving.font_height_mm = AUTO_FONT_HEIGHT_MAX_MM;
      operation.inferred_fields = dedupeStrings([...(operation.inferred_fields || []), 'font_height_mm']);
    } else if (!operationProvided.has('font_height_mm') && !operation.inherited_fields.includes('font_height_mm')) {
      operation.inferred_fields = dedupeStrings([...(operation.inferred_fields || []), 'font_height_mm']);
    }
    operation.engraving = engraving;
    next.pending_operations.push(operation);
  }
  next.inferred_fields = dedupeStrings([
    ...(draft.inferred_fields || []),
    ...next.pending_operations.flatMap((operation) => operation.inferred_fields || []),
  ]).filter((field) => !(draft.provided_fields || []).includes(field));
  return next;
}

async function resolveAutomaticFontHeights({ python, sourceCode, cadqueryAvailable, applied, draft } = {}) {
  const autoIds = new Set();
  (draft.pending_operations || []).forEach((operation, index) => {
    if (!(operation.inferred_fields || []).includes('font_height_mm') || (operation.inherited_fields || []).includes('font_height_mm')) return;
    const id = applied.operations?.[index]?.engraving?.id;
    if (id) autoIds.add(id);
  });
  if (!autoIds.size) return { status: 'ok', applied };
  if (!cadqueryAvailable || !python || !normalizeString(sourceCode)) {
    return {
      status: 'needs_input',
      message: '当前环境暂时无法测量目标平面的安全字号。',
      questions: ['请稍后重试，或明确给出不小于 3mm 的字体高度。'],
      blocking_reason: 'surface_engraving_auto_font_measurement_unavailable',
    };
  }
  let engravings = applied.surface_engravings.map((item) => ({ ...item }));
  let verifiedPreflight = null;
  for (const id of autoIds) {
    const probe = engravings.map((item) => item.id === id ? { ...item, font_height_mm: 1000 } : item);
    const probeResult = await preflightSurfaceEngravings({
      python,
      sourceCode,
      surfaceEngravings: probe,
      patch: buildSurfaceEngravingPatch(probe),
    });
    const maxFit = finiteNumber(probeResult?.details?.max_font_height_mm);
    if (probeResult.status !== 'pass' && !Number.isFinite(maxFit)) {
      return {
        status: 'needs_input',
        message: probeResult.message || '无法完成目标平面的安全字号测量。',
        questions: ['请调整刻字内容或目标外部平面后重试。'],
        blocking_reason: `surface_engraving_${probeResult.code || 'auto_font_measurement_failed'}`,
      };
    }
    const candidate = chooseAutomaticFontHeight(maxFit);
    if (!Number.isFinite(candidate)) {
      return {
        status: 'needs_input',
        message: '当前目标平面无法容纳最小 3mm 的单行刻字。',
        questions: ['请缩短文字，或改选面积更大的外部平面。'],
        blocking_reason: 'surface_engraving_auto_font_unavailable',
      };
    }
    let fittedHeight = NaN;
    let lastFitResult = null;
    for (let height = candidate; height >= MIN_FONT_HEIGHT_MM; height = Math.round((height - 0.5) * 2) / 2) {
      const trial = engravings.map((item) => item.id === id ? { ...item, font_height_mm: height } : item);
      const fitResult = await preflightSurfaceEngravings({
        python,
        sourceCode,
        surfaceEngravings: trial,
        patch: buildSurfaceEngravingPatch(trial),
      });
      lastFitResult = fitResult;
      if (fitResult.status === 'pass') {
        fittedHeight = height;
        engravings = trial;
        verifiedPreflight = fitResult;
        break;
      }
      if (['cjk_font_missing', 'font_missing', 'surface_identity_mismatch', 'planar_face_not_found'].includes(fitResult.code)) break;
    }
    if (!Number.isFinite(fittedHeight)) {
      return {
        status: 'needs_input',
        message: lastFitResult?.message || '当前目标位置无法安全容纳最小 3mm 的刻字。',
        questions: ['请缩短文字、调整平面内位置，或改选面积更大的外部平面。'],
        blocking_reason: `surface_engraving_${lastFitResult?.code || 'auto_font_unavailable'}`,
      };
    }
  }
  const byId = new Map(engravings.map((item) => [item.id, item]));
  const operations = (applied.operations || []).map((operation) => {
    const id = operation?.engraving?.id;
    return id && byId.has(id) ? { ...operation, engraving: byId.get(id) } : operation;
  });
  return {
    status: 'ok',
    applied: { ...applied, surface_engravings: engravings, operations },
    preflight: verifiedPreflight,
  };
}

async function findVerifiedFontHeightSuggestion({
  python,
  sourceCode,
  cadqueryAvailable,
  surfaceEngravings = [],
  operations = [],
  failure = null,
} = {}) {
  if (!cadqueryAvailable || !python || !normalizeString(sourceCode) || failure?.status !== 'fail') return null;
  if (!['font_height_too_large', 'engraving_out_of_bounds', 'engraving_original_feature_conflict'].includes(failure.code)) {
    return null;
  }
  const engravingId = normalizeString(failure.details?.engraving_id);
  const changedIds = new Set((operations || [])
    .map((operation) => normalizeString(operation?.engraving?.id || operation?.target_id))
    .filter(Boolean));
  if (!engravingId || !changedIds.has(engravingId)) return null;
  const target = surfaceEngravings.find((item) => item.id === engravingId);
  if (!target) return null;
  const requested = finiteNumber(target.font_height_mm);
  const measuredMaximum = finiteNumber(failure.details?.max_font_height_mm);
  if (!Number.isFinite(requested) || !Number.isFinite(measuredMaximum)) return null;
  const upper = Math.floor(Math.min(measuredMaximum, requested - 0.5) * 2) / 2;
  if (upper < MIN_FONT_HEIGHT_MM) return null;
  const candidates = dedupeStrings([
    upper,
    Math.floor(upper * 0.8 * 2) / 2,
    Math.floor(upper * 0.6 * 2) / 2,
    MIN_FONT_HEIGHT_MM,
  ].filter((height) => height >= MIN_FONT_HEIGHT_MM).map(String)).map(Number);
  for (const height of candidates) {
    const trial = surfaceEngravings.map((item) => (
      item.id === engravingId ? { ...item, font_height_mm: height } : item
    ));
    const fitResult = await preflightSurfaceEngravings({
      python,
      sourceCode,
      surfaceEngravings: trial,
      patch: buildSurfaceEngravingPatch(trial),
    });
    if (fitResult.status === 'pass') {
      return { font_height_mm: height, preflight: fitResult };
    }
    const failedId = normalizeString(fitResult.details?.engraving_id);
    if (failedId && failedId !== engravingId) break;
    if (['cjk_font_missing', 'font_missing', 'surface_identity_mismatch', 'planar_face_not_found', 'planar_face_not_external'].includes(fitResult.code)) {
      break;
    }
  }
  return null;
}

function preflightMatchesSurfaceEngravings(preflight, surfaceEngravings = []) {
  if (preflight?.status !== 'pass' || !Array.isArray(preflight.report)) return false;
  const expectedIds = normalizeSurfaceEngravings(surfaceEngravings).map((item) => item.id);
  const reportIds = preflight.report.map((item) => normalizeString(item?.id));
  return JSON.stringify(reportIds) === JSON.stringify(expectedIds);
}

export function chooseAutomaticFontHeight(maxFitValue) {
  const maxFit = finiteNumber(maxFitValue);
  if (!Number.isFinite(maxFit)) return AUTO_FONT_HEIGHT_MAX_MM;
  if (maxFit < MIN_FONT_HEIGHT_MM) return NaN;
  return Math.max(
    MIN_FONT_HEIGHT_MM,
    Math.floor(Math.min(AUTO_FONT_HEIGHT_MAX_MM, maxFit * AUTO_FONT_HEIGHT_RATIO) * 2) / 2,
  );
}

function dedupeResolvedSurfaceEngravings(applied = {}) {
  const canonicalByKey = new Map();
  const canonicalById = new Map();
  const engravings = [];
  for (const item of normalizeSurfaceEngravings(applied.surface_engravings)) {
    const key = canonicalEngravingKey(item);
    const existing = canonicalByKey.get(key);
    if (existing) {
      canonicalById.set(item.id, existing);
      continue;
    }
    canonicalByKey.set(key, item);
    canonicalById.set(item.id, item);
    engravings.push(item);
  }
  const operations = (applied.operations || []).map((operation) => {
    const engraving = operation?.engraving;
    if (!engraving?.id) return operation;
    const canonical = canonicalById.get(engraving.id) || engraving;
    if (canonical.id === engraving.id) return { ...operation, engraving: canonical };
    return {
      action: 'update',
      target_id: canonical.id,
      engraving: canonical,
      no_change: true,
    };
  });
  return { ...applied, surface_engravings: engravings, operations };
}

function canonicalEngravingKey(value = {}) {
  const normalized = normalizeEngravingSpec(value);
  if (normalized.status !== 'ok') return JSON.stringify(value);
  const { id: _id, ...spec } = normalized.spec;
  return JSON.stringify(spec);
}

function buildResolvedEngravingSummary(engravings = [], draft = {}, rawSummary = '') {
  const inferredFontIds = [];
  for (const operation of draft.pending_operations || []) {
    if ((operation.inferred_fields || []).includes('font_height_mm') && !(operation.inherited_fields || []).includes('font_height_mm')) {
      const id = operation.engraving?.id || operation.target_id;
      const resolved = engravings.find((item) => item.id === id) || engravings.at(-1);
      if (resolved) inferredFontIds.push(`${resolved.text} 采用 ${formatNumber(resolved.font_height_mm)}mm`);
    }
  }
  if (!inferredFontIds.length && normalizeString(rawSummary)) return normalizeString(rawSummary);
  const suffix = inferredFontIds.length ? ` 未指定字号的刻字已按目标面容量自动选择：${inferredFontIds.join('、')}。` : '';
  return `${summarizeSurfaceEngravings(engravings)}${suffix}`.trim();
}

function missingFieldsFromNeedsInput(result = {}) {
  if (Array.isArray(result.missing_fields) && result.missing_fields.length) {
    return dedupeStrings(result.missing_fields);
  }
  const text = `${result.message || ''} ${(result.questions || []).join(' ')}`;
  const missing = [];
  if (/文字内容|刻字内容/.test(text)) missing.push('文字内容');
  if (/目标零件|目标外部平面|哪个外部平面/.test(text)) missing.push('目标外部平面');
  if (/修改哪一条|删除哪一条/.test(text)) missing.push('目标刻字');
  return missing;
}

function normalizeRequestedLayout(value) {
  if (!isPlainObject(value)) return {};
  const result = {};
  if (value.multiline === true || value.multiline === false) result.multiline = value.multiline;
  const count = finiteNumber(value.line_count ?? value.lineCount);
  if (Number.isFinite(count)) result.line_count = Math.max(1, Math.floor(count));
  const mode = normalizeString(value.layout_mode ?? value.layoutMode).toLowerCase();
  if (mode === 'multiline' || mode === 'single_line') result.layout_mode = mode;
  const spacing = finiteNumber(value.line_spacing_ratio ?? value.lineSpacingRatio);
  if (Number.isFinite(spacing)) result.line_spacing_ratio = Math.min(3, Math.max(0.8, spacing));
  return result;
}

function fieldNamesFromOperations(operations = []) {
  return dedupeStrings(operations.flatMap((operation) => Object.keys(operation?.engraving || {})));
}

function normalizeStringList(value) {
  return Array.isArray(value) ? dedupeStrings(value.map(normalizeString).filter(Boolean)) : [];
}

function dedupeStrings(value = []) {
  return [...new Set(value.map(normalizeString).filter(Boolean))];
}

function formatNumber(value) {
  const number = finiteNumber(value);
  return Number.isInteger(number) ? String(number) : String(Math.round(number * 100) / 100);
}

function completeSurfaceEngravingOperations(rawOperations, currentDesignState = {}, prompt = '') {
  if (!Array.isArray(rawOperations)) return rawOperations;
  const enclosure = currentDesignState?.enclosure_parameters || {};
  const outer = enclosure.outer_box_size || {};
  const parameters = currentDesignState?.parameters || {};
  const length = finiteNumber(outer.length_x);
  const width = finiteNumber(outer.width_y);
  const height = finiteNumber(outer.height_z);
  const lidThickness = finiteNumber(parameters.lid_thickness ?? enclosure.lid_thickness);
  const baseHeight = Number.isFinite(height)
    ? Math.max(0, height - (Number.isFinite(lidThickness) ? lidThickness : 3))
    : NaN;
  return rawOperations.map((operation) => {
    const action = normalizeString(operation?.action).toLowerCase();
    if (!['add', 'update'].includes(action)) return operation;
    const engraving = isPlainObject(operation?.engraving)
      ? { ...operation.engraving }
      : {};
    const surfaceText = [
      engraving.surface,
      engraving.surface_name,
      engraving.target_surface,
      engraving.face,
      prompt,
    ].map(normalizeString).filter(Boolean).join(' ');
    const surfaceMatch = matchModelSurface(
      surfaceText,
      currentDesignState,
      engraving.surface_id || engraving.surfaceId,
      prompt,
    );
    const catalogSurface = surfaceMatch?.ambiguous ? null : surfaceMatch;
    if (surfaceMatch?.ambiguous) {
      engraving.surface_candidate_ids = surfaceMatch.candidates.map((item) => item.id);
      engraving.surface_candidate_labels = surfaceMatch.candidates.map((item) => item.label);
    } else {
      delete engraving.surface_candidate_ids;
      delete engraving.surface_candidate_labels;
    }
    let targetPart = catalogSurface?.target_part
      || normalizeTargetPart(engraving.target_part || engraving.targetPart);
    if (!targetPart) targetPart = targetPartFromText(surfaceText);
    if (targetPart) engraving.target_part = targetPart;
    if (!ALLOWED_ANCHORS.has(normalizeString(engraving.anchor).toLowerCase())) {
      const anchor = anchorFromText(surfaceText);
      if (anchor) engraving.anchor = anchor;
    }
    const frame = catalogSurface || standardSurfaceFrame({
      targetPart,
      text: surfaceText,
      length,
      width,
      height,
      baseHeight,
    });
    if (frame) {
      if (catalogSurface) {
        engraving.surface_id = catalogSurface.id;
        engraving.surface = catalogSurface.label;
        engraving.surface_area_hint_mm2 = catalogSurface.area_hint_mm2;
        engraving.surface_span_hint_mm = catalogSurface.local_span_hint_mm;
        engraving.surface_selector_version = catalogSurface.selector_version;
        engraving.normal_hint = frame.normal_hint;
        engraving.point_hint = frame.point_hint;
        engraving.x_direction = frame.x_direction;
      } else {
        if (!normalizeDirection(engraving.normal_hint || engraving.normalHint)) engraving.normal_hint = frame.normal_hint;
        if (!normalizeVector(engraving.point_hint || engraving.pointHint)) engraving.point_hint = frame.point_hint;
        if (!normalizeDirection(engraving.x_direction || engraving.xDirection)) engraving.x_direction = frame.x_direction;
      }
    }
    return { ...operation, engraving };
  });
}

function targetPartFromText(text = '') {
  const identity = surfaceIdentityFromText(text);
  if (identity === 'top') return 'lid_part';
  if (['bottom', 'front', 'back', 'left', 'right', 'slope'].includes(identity)) return 'base_part';
  if (/上盖|盖子|盖板|顶面|顶部|上表面/i.test(text) || /\blid\b/i.test(text)) return 'lid_part';
  if (/底壳|底座|底面|前侧|前面|前边|后侧|后面|后边|左侧|左面|左边|右侧|右面|右边|正面|背面/i.test(text)
    || /\b(?:base|front|back|left|right|bottom)\b/i.test(text)) return 'base_part';
  return '';
}

function matchExistingSurfaceEngravingId(text = '', currentEngravings = [], currentDesignState = {}) {
  if (!Array.isArray(currentEngravings) || !currentEngravings.length) return '';
  let candidates = currentEngravings.slice();
  const mentionedByText = candidates.filter((item) => normalizeString(item.text) && normalizeString(text).includes(item.text));
  if (mentionedByText.length === 1) return mentionedByText[0].id;
  if (mentionedByText.length > 1) candidates = mentionedByText;
  const catalogSurface = matchModelSurface(text, currentDesignState, '', text);
  if (catalogSurface && !catalogSurface.ambiguous) {
    const byStableSurface = candidates.filter((item) => (
      normalizeString(item.surface_id || item.surfaceId).toLowerCase() === catalogSurface.id
    ));
    if (byStableSurface.length === 1) return byStableSurface[0].id;
    if (byStableSurface.length > 1) candidates = byStableSurface;
  }
  const requestedSurface = surfaceIdentityFromText(text);
  if (requestedSurface) {
    candidates = candidates.filter((item) => {
      const identity = surfaceIdentityFromEngraving(item);
      return requestedSurface === 'slope' ? identity === 'slope' || identity.startsWith('normal:') : identity === requestedSurface;
    });
  }
  const requestedPart = targetPartFromText(text);
  if (requestedPart) candidates = candidates.filter((item) => item.target_part === requestedPart);
  const requestedAnchor = anchorFromText(text);
  if (requestedAnchor && /(?:左上|右上|左下|右下|中央|中心|正中|居中|上方中央|下方中央|左侧中央|右侧中央)/.test(text)) {
    candidates = candidates.filter((item) => item.anchor === requestedAnchor);
  }
  return candidates.length === 1 ? candidates[0].id : '';
}

function surfaceIdentityFromEngraving(value = {}) {
  const described = surfaceIdentityFromText([
    value.surface,
    value.surface_name,
    value.target_surface,
    value.face,
  ].map(normalizeString).filter(Boolean).join(' '));
  if (described) return described;
  const normal = normalizeDirection(value.normal_hint || value.normalHint);
  if (!normal) return normalizeTargetPart(value.target_part || value.targetPart) === 'lid_part' ? 'top' : '';
  const length = Math.sqrt(normal.reduce((sum, item) => sum + item * item, 0));
  const [x, y, z] = normal.map((item) => item / length);
  if (x > 0.92) return 'right';
  if (x < -0.92) return 'left';
  if (y > 0.92) return 'back';
  if (y < -0.92) return 'front';
  if (z > 0.92) return 'top';
  if (z < -0.92) return 'bottom';
  return `normal:${[x, y, z].map((item) => item.toFixed(3)).join(',')}`;
}

function surfaceIdentityFromText(value = '') {
  const text = normalizeString(value);
  if (/(?:斜面|倾斜平面)(?:的)?(?:上表面|顶面|表面)/i.test(text)) return 'slope';
  const patterns = [
    ['right', /右侧|右面|右边|\bright\b/ig],
    ['left', /左侧|左面|左边|\bleft\b/ig],
    ['front', /前侧|前面|前边|正面|\bfront\b/ig],
    ['back', /后侧|后面|后边|背面|\bback\b/ig],
    ['bottom', /底面|底部外|\bbottom\b/ig],
    ['top', /上盖|盖子|盖板|顶面|顶部|上表面|\b(?:lid|top)\b/ig],
    ['slope', /斜面|倾斜平面|\bslope\b/ig],
  ];
  let selected = '';
  let selectedIndex = -1;
  for (const [identity, pattern] of patterns) {
    for (const match of text.matchAll(pattern)) {
      if ((match.index ?? -1) >= selectedIndex) {
        selected = identity;
        selectedIndex = match.index ?? -1;
      }
    }
  }
  return selected;
}

function matchModelSurface(text = '', currentDesignState = {}, requestedId = '', prompt = '') {
  const catalog = normalizeModelSurfaces(
    currentDesignState?.engraving_surfaces
      || currentDesignState?.model_surfaces
      || currentDesignState?.cad_parameters?.engraving_surfaces
      || currentDesignState?.model_index?.surfaces,
  );
  if (!catalog.length) return null;
  const promptText = normalizeString(prompt)
    .replace(/[“"'‘][^”"'’\r\n]{1,256}[”"'’]/g, ' ')
    .toLowerCase();
  const promptHasSurface = lastSurfaceMentionEnd(promptText) > 0;
  const surfaceId = normalizeString(requestedId).toLowerCase();
  if (surfaceId && !promptHasSurface) {
    const byId = catalog.find((item) => item.id === surfaceId);
    if (byId) return byId;
  }
  const normalizedText = promptHasSurface ? promptText : normalizeString(text).toLowerCase();
  if (!normalizedText) return null;
  const candidates = [];
  for (const surface of catalog) {
    const terms = [surface.id, surface.label, ...surface.aliases]
      .flatMap(surfaceMatchTermVariants)
      .filter(Boolean);
    const matches = terms
      .map((term) => ({ term, index: normalizedText.lastIndexOf(term) }))
      .filter((match) => match.index >= 0)
      .map((match) => ({ ...match, end: match.index + match.term.length }));
    const matchedEnd = Math.max(0, ...matches.map((match) => match.end));
    const matchedLength = Math.max(0, ...matches
      .filter((match) => match.end === matchedEnd)
      .map((match) => match.term.length));
    if (matchedEnd) candidates.push({ surface, matchedEnd, matchedLength });
  }
  candidates.sort((left, right) => right.matchedEnd - left.matchedEnd || right.matchedLength - left.matchedLength);
  const lastMentionEnd = lastSurfaceMentionEnd(normalizedText);
  if (candidates[0]?.matchedEnd >= lastMentionEnd) return candidates[0]?.surface || null;
  if (candidates[0]) {
    const trailingSurfaceModifier = normalizedText.slice(candidates[0].matchedEnd, lastMentionEnd);
    if (/^(?:(?:的)?(?:上|外)?(?:表面|正面|顶面)|(?:的)?(?:左|右|上|下)(?:侧|方)?|中央|中心|正中|居中)+$/.test(trailingSurfaceModifier)) {
      return candidates[0].surface;
    }
  }
  if (/(?:斜面|倾斜平面|\bslope\b)/i.test(normalizedText)) {
    const slopes = catalog.filter((surface) => (
      surface.surface_kind === 'slope'
      || surface.label.includes('斜面')
      || surface.aliases.some((alias) => alias.includes('斜面'))
    )).sort((left, right) => right.area_hint_mm2 - left.area_hint_mm2);
    if (slopes.length === 1) return slopes[0];
    if (hasSpecificSlopeQualifier(normalizedText) && slopes.length > 1) {
      return { ambiguous: true, candidates: slopes };
    }
    if (slopes.length > 1 && slopes[0].area_hint_mm2 > 0
      && slopes[0].area_hint_mm2 >= slopes[1].area_hint_mm2 * 2) return slopes[0];
    if (slopes.length > 1) return { ambiguous: true, candidates: slopes };
  }
  return null;
}

function surfaceMatchTermVariants(value = '') {
  const source = normalizeString(value).toLowerCase();
  if (!source) return [];
  const variants = new Set([source]);
  const compactL = source.replace(/l\s+[形型]/g, (match) => match.replace(/\s+/g, ''));
  variants.add(compactL);
  for (const item of [...variants]) {
    variants.add(item.replace(/l形/g, 'l型'));
    variants.add(item.replace(/l型/g, 'l形'));
    if (item.includes('外斜面')) {
      variants.add(item.replace(/外斜面/g, '外侧斜面'));
      variants.add(item.replace(/外斜面/g, '外侧面斜面'));
      variants.add(item.replace(/外斜面/g, '外侧面'));
    }
  }
  return [...variants];
}

function hasSpecificSlopeQualifier(value = '') {
  return /(?:l\s*[形型]|卡槽|方孔|正方形孔|主斜面|主体.{0,3}斜面|大斜面|小斜面|窄斜面|显示斜面)/i.test(normalizeString(value));
}

function lastSurfaceMentionEnd(text = '') {
  const pattern = /右侧|右面|右边|左侧|左面|左边|前侧|前面|前边|正面|后侧|后面|后边|背面|底面|底部外|上盖|盖子|盖板|顶面|顶部|上表面|斜面|倾斜平面|\b(?:right|left|front|back|bottom|lid|top|slope)\b/ig;
  let end = 0;
  for (const match of normalizeString(text).matchAll(pattern)) {
    end = Math.max(end, (match.index || 0) + match[0].length);
  }
  return end;
}

function normalizeModelSurfaces(value) {
  if (!Array.isArray(value)) return [];
  return value.map((item) => {
    if (!isPlainObject(item)) return null;
    const id = normalizeString(item.id || item.surface_id || item.surfaceId).toLowerCase();
    const targetPart = normalizeTargetPart(item.target_part || item.targetPart);
    const normalHint = normalizeDirection(item.normal_hint || item.normalHint);
    const pointHint = normalizeVector(item.point_hint || item.pointHint);
    const xDirection = normalizeDirection(item.x_direction || item.xDirection);
    if (!id || !targetPart || !normalHint || !pointHint || !xDirection) return null;
    return {
      id,
      label: normalizeString(item.label || item.name || id),
      aliases: normalizeStringList(item.aliases),
      target_part: targetPart,
      normal_hint: normalHint,
      point_hint: pointHint,
      x_direction: xDirection,
      surface_kind: normalizeString(item.surface_kind || item.surfaceKind).toLowerCase(),
      area_hint_mm2: finiteNumber(item.area_hint_mm2 ?? item.areaHintMm2) || 0,
      local_span_hint_mm: Array.isArray(item.local_span_hint_mm) ? item.local_span_hint_mm.map(finiteNumber) : [],
      selector_version: normalizeString(item.selector_version || item.selectorVersion),
    };
  }).filter(Boolean);
}

function clearSurfaceFrame(value = {}) {
  for (const key of ['normal_hint', 'normalHint', 'point_hint', 'pointHint', 'x_direction', 'xDirection']) {
    delete value[key];
  }
  return value;
}

function anchorFromText(text = '') {
  const value = normalizeString(text);
  if (/左上|左上角|top\s*left|upper\s*left/i.test(value)) return 'top_left';
  if (/右上|右上角|top\s*right|upper\s*right/i.test(value)) return 'top_right';
  if (/左下|左下角|bottom\s*left|lower\s*left/i.test(value)) return 'bottom_left';
  if (/右下|右下角|bottom\s*right|lower\s*right/i.test(value)) return 'bottom_right';
  if (/上方中央|顶部中央|上边中央|top\s*center/i.test(value)) return 'top_center';
  if (/下方中央|底部中央|下边中央|bottom\s*center/i.test(value)) return 'bottom_center';
  if (/左侧中央|左边中央|center\s*left/i.test(value)) return 'center_left';
  if (/右侧中央|右边中央|center\s*right/i.test(value)) return 'center_right';
  if (/中央|中心|正中|居中|center|middle/i.test(value)) return 'center';
  return '';
}

function standardSurfaceFrame({ targetPart, text, length, width, height, baseHeight }) {
  if (targetPart === 'lid_part' && Number.isFinite(height)) {
    return {
      normal_hint: [0, 0, 1],
      point_hint: [0, 0, height],
      x_direction: [1, 0, 0],
    };
  }
  if (targetPart !== 'base_part') return null;
  const surfaceIdentity = surfaceIdentityFromText(text);
  if (surfaceIdentity === 'bottom' && Number.isFinite(length) && Number.isFinite(width)) {
    return {
      normal_hint: [0, 0, -1],
      point_hint: [0, 0, 0],
      x_direction: [1, 0, 0],
    };
  }
  const sideZ = Number.isFinite(baseHeight) ? baseHeight / 2 : 0;
  if (surfaceIdentity === 'right' && Number.isFinite(length)) {
    return {
      normal_hint: [1, 0, 0],
      point_hint: [length / 2, 0, sideZ],
      x_direction: [0, 1, 0],
    };
  }
  if (surfaceIdentity === 'left' && Number.isFinite(length)) {
    return {
      normal_hint: [-1, 0, 0],
      point_hint: [-length / 2, 0, sideZ],
      x_direction: [0, -1, 0],
    };
  }
  if (surfaceIdentity === 'front' && Number.isFinite(width)) {
    return {
      normal_hint: [0, -1, 0],
      point_hint: [0, -width / 2, sideZ],
      x_direction: [1, 0, 0],
    };
  }
  if (surfaceIdentity === 'back' && Number.isFinite(width)) {
    return {
      normal_hint: [0, 1, 0],
      point_hint: [0, width / 2, sideZ],
      x_direction: [-1, 0, 0],
    };
  }
  return null;
}

export function applySurfaceEngravingOperations(currentEngravings = [], rawOperations = []) {
  if (!Array.isArray(rawOperations) || !rawOperations.length) {
    return {
      status: 'needs_input',
      message: '目前还无法确定要执行的刻字操作。',
      questions: ['请明确要新增、修改还是删除哪一条刻字。'],
      blocking_reason: 'surface_engraving_missing_operations',
    };
  }
  const next = normalizeSurfaceEngravings(currentEngravings);
  const operations = [];
  for (const raw of rawOperations) {
    const action = normalizeString(raw?.action).toLowerCase();
    if (action === 'clear') {
      next.splice(0, next.length);
      operations.push({ action: 'clear' });
      continue;
    }
    if (action === 'remove') {
      const targetId = normalizeString(raw?.target_id || raw?.id);
      const index = next.findIndex((item) => item.id === targetId);
      if (index < 0) {
        return {
          status: 'needs_input',
          message: '无法确定要删除哪一条刻字。',
          questions: ['请说明要删除的刻字文字或所在位置。'],
          blocking_reason: 'surface_engraving_remove_target_missing',
        };
      }
      next.splice(index, 1);
      operations.push({ action: 'remove', target_id: targetId });
      continue;
    }
    if (action === 'add') {
      const normalized = normalizeEngravingSpec(raw?.engraving || raw);
      if (normalized.status !== 'ok') return normalized;
      const spec = {
        ...normalized.spec,
        id: normalized.spec.id || createEngravingId(normalized.spec, next.length),
      };
      const sameIdIndex = spec.id ? next.findIndex((item) => item.id === spec.id) : -1;
      const equivalentIndex = sameIdIndex >= 0 ? sameIdIndex : next.findIndex((item) => equivalentEngravingSpec(item, spec));
      if (equivalentIndex >= 0) {
        const noChange = equivalentEngravingSpec(next[equivalentIndex], spec);
        const stableSpec = { ...spec, id: next[equivalentIndex].id };
        next[equivalentIndex] = stableSpec;
        operations.push({ action: 'update', target_id: stableSpec.id, engraving: stableSpec, no_change: noChange });
        continue;
      }
      next.push(spec);
      operations.push({ action: 'add', engraving: spec });
      continue;
    }
    if (action === 'update') {
      const targetId = normalizeString(raw?.target_id || raw?.id) || (next.length === 1 ? next[0].id : '');
      const index = next.findIndex((item) => item.id === targetId);
      if (index < 0) {
        return {
          status: 'needs_input',
          message: '无法确定要修改哪一条刻字。',
          questions: ['请说明要修改的刻字文字或所在位置。'],
          blocking_reason: 'surface_engraving_update_target_missing',
        };
      }
      const previous = next[index];
      let normalized = normalizeEngravingSpec(raw?.engraving || {}, previous);
      if (normalized.status !== 'ok') return normalized;
      if (previous.allow_original_feature_intersection
        && engravingGeometrySignature(previous) !== engravingGeometrySignature(normalized.spec)) {
        const {
          allow_original_feature_intersection: _allow,
          original_feature_intersection_source_hash: _sourceHash,
          ...withoutOverride
        } = normalized.spec;
        normalized = { status: 'ok', spec: withoutOverride };
      }
      next[index] = { ...normalized.spec, id: targetId };
      operations.push({ action: 'update', target_id: targetId, engraving: next[index] });
      continue;
    }
    return {
      status: 'needs_input',
      message: `不支持的刻字操作：${action || '空操作'}。`,
      questions: ['请明确要新增、修改、删除单条或删除全部刻字。'],
      blocking_reason: 'surface_engraving_invalid_operation',
    };
  }
  return { status: 'ok', surface_engravings: next, operations };
}

function equivalentEngravingSpec(left = {}, right = {}) {
  const normalizedLeft = normalizeEngravingSpec(left);
  const normalizedRight = normalizeEngravingSpec(right);
  if (normalizedLeft.status !== 'ok' || normalizedRight.status !== 'ok') return false;
  const withoutId = (spec) => {
    const { id: _id, ...rest } = spec;
    return rest;
  };
  return JSON.stringify(withoutId(normalizedLeft.spec)) === JSON.stringify(withoutId(normalizedRight.spec));
}

function normalizeEngravingSpec(value = {}, fallback = null) {
  const base = isPlainObject(fallback) ? fallback : {};
  const input = isPlainObject(value) ? value : {};
  const rawText = normalizeString(input.text ?? base.text);
  const explicitLineValues = Array.isArray(input.lines) ? input.lines.map(normalizeString) : [];
  const hasEmptyExplicitLine = explicitLineValues.some((item) => !item);
  const hasEmptyTextLine = /(?:^|\r?\n)\s*\r?\n/.test(rawText);
  const rawLines = Array.isArray(input.lines)
    ? explicitLineValues.filter((item) => item.length > 0)
    : Array.isArray(base.lines)
      ? base.lines.map(normalizeString).filter((item) => item.length > 0)
      : [];
  const requestedLayout = normalizeRequestedLayout(input.layout || input.requested_layout || base.layout || base.requested_layout);
  const multilineRequested = requestedLayout.multiline === true || rawLines.length > 1 || /\r|\n/.test(rawText);
  const lines = rawLines.length
    ? rawLines
      : multilineRequested
      ? splitEngravingLines(rawText, requestedLayout.line_count)
      : [];
  const text = multilineRequested && lines.length > 1 ? lines.join('\n') : rawText.replace(/\r?\n/g, '');
  const targetPart = normalizeTargetPart(input.target_part ?? input.targetPart ?? base.target_part);
  const anchor = normalizeString(input.anchor ?? base.anchor).toLowerCase();
  const normalHint = normalizeDirection(input.normal_hint ?? input.normalHint ?? base.normal_hint);
  const pointHint = normalizeVector(input.point_hint ?? input.pointHint ?? base.point_hint);
  const xDirection = normalizeDirection(input.x_direction ?? input.xDirection ?? base.x_direction);
  const fontHeight = finiteNumber(input.font_height_mm ?? input.fontHeightMm ?? base.font_height_mm);
  const allowOriginalFeatureIntersection = (input.allow_original_feature_intersection
    ?? base.allow_original_feature_intersection) === true;
  const originalFeatureIntersectionSourceHash = normalizeString(
    input.original_feature_intersection_source_hash
      ?? base.original_feature_intersection_source_hash,
  ).toLowerCase();
  const missing = [];
  if (!text) missing.push('文字内容');
  if (!targetPart) missing.push('目标零件');
  if (!ALLOWED_ANCHORS.has(anchor)) missing.push('具体平面位置/九宫格锚点');
  if (!normalHint || !pointHint || !xDirection) missing.push('可唯一识别的目标外部平面');
  if (!Number.isFinite(fontHeight)) missing.push('字体高度');
  if (missing.length) {
    return {
      status: 'needs_input',
      message: `还缺少${missing.join('、')}。`,
      questions: userFacingEngravingQuestions(missing.map((item) => `请明确${item}。`)),
      blocking_reason: 'surface_engraving_missing_parameters',
      missing_fields: missing,
    };
  }
  const plainLength = [...text.replace(/\r?\n/g, '')].length;
  const lineLengthExceeded = lines.some((line) => [...line].length > MAX_TEXT_LENGTH);
  if ((!multilineRequested && plainLength > MAX_TEXT_LENGTH) || (multilineRequested && (plainLength > MAX_MULTILINE_TEXT_LENGTH || lines.length > MAX_MULTILINE_LINES || lineLengthExceeded))) {
    return {
      status: 'needs_input',
      message: multilineRequested
        ? `多行刻字最多支持 ${MAX_MULTILINE_LINES} 行、总计 ${MAX_MULTILINE_TEXT_LENGTH} 个字符，且每行不超过 ${MAX_TEXT_LENGTH} 个字符。`
        : `单行刻字最多支持 ${MAX_TEXT_LENGTH} 个字符。`,
      questions: multilineRequested ? ['请缩短文字或减少行数后重试。'] : ['请缩短文字，或拆成多条单行刻字。'],
      blocking_reason: 'surface_engraving_text_too_long',
    };
  }
  const controlText = text.replace(/\r?\n/g, '');
  if (/[\u0000-\u0009\u000B\u000C\u000E-\u001F\u007F-\u009F\u2028\u2029]/.test(controlText)
    || hasEmptyExplicitLine
    || hasEmptyTextLine
    || (multilineRequested && lines.some((line) => !line.trim()))) {
    return {
      status: 'needs_input',
      message: multilineRequested ? '多行刻字内容不能包含控制字符或空行。' : '刻字内容不能包含换行、制表符或其他控制字符。',
      questions: [multilineRequested ? '请删除空行和控制字符后重试。' : '请把刻字内容改成单行普通文字。'],
      blocking_reason: 'surface_engraving_invalid_text',
    };
  }
  if (fontHeight < MIN_FONT_HEIGHT_MM) {
    return {
      status: 'needs_input',
      message: `字体高度不能小于 ${MIN_FONT_HEIGHT_MM}mm。`,
      questions: [`请确认不小于 ${MIN_FONT_HEIGHT_MM}mm 的字体高度。`],
      blocking_reason: 'surface_engraving_font_too_small',
    };
  }
  return {
    status: 'ok',
    spec: {
      schema_version: ENGRAVING_SCHEMA_VERSION,
      id: normalizeEngravingId(input.id ?? base.id),
      text,
      lines: multilineRequested && lines.length > 1 ? lines : [text],
      layout_mode: multilineRequested && lines.length > 1 ? 'multiline' : 'single_line',
      line_spacing_ratio: normalizeLineSpacing(input.line_spacing_ratio ?? input.lineSpacingRatio ?? base.line_spacing_ratio),
      requested_layout: requestedLayout,
      surface_id: normalizeString(input.surface_id ?? input.surfaceId ?? base.surface_id ?? base.surfaceId),
      surface_area_hint_mm2: finiteNumber(input.surface_area_hint_mm2 ?? input.surfaceAreaHintMm2 ?? base.surface_area_hint_mm2) || 0,
      surface_span_hint_mm: normalizePositivePair(input.surface_span_hint_mm ?? input.surfaceSpanHintMm ?? base.surface_span_hint_mm),
      surface_selector_version: normalizeString(input.surface_selector_version ?? input.surfaceSelectorVersion ?? base.surface_selector_version),
      target_part: targetPart,
      normal_hint: normalHint,
      point_hint: pointHint,
      x_direction: xDirection,
      anchor,
      offset_u_mm: finiteNumber(input.offset_u_mm ?? input.offsetUMm ?? base.offset_u_mm) || 0,
      offset_v_mm: finiteNumber(input.offset_v_mm ?? input.offsetVMm ?? base.offset_v_mm) || 0,
      rotation_deg: normalizeRotation(input.rotation_deg ?? input.rotationDeg ?? base.rotation_deg),
      font_height_mm: fontHeight,
      depth_mm: DEPTH_MM,
      font_kind: normalizeString(input.font_kind ?? input.fontKind ?? base.font_kind).toLowerCase() === 'bold' ? 'bold' : 'regular',
      ...(allowOriginalFeatureIntersection ? { allow_original_feature_intersection: true } : {}),
      ...(allowOriginalFeatureIntersection && SOURCE_HASH_PATTERN.test(originalFeatureIntersectionSourceHash)
        ? { original_feature_intersection_source_hash: originalFeatureIntersectionSourceHash }
        : {}),
    },
  };
}

function engravingGeometrySignature(value = {}) {
  const normalized = normalizeEngravingSpec(value);
  if (normalized.status !== 'ok') return '';
  return JSON.stringify(Object.fromEntries(
    OVERRIDE_GEOMETRY_FIELDS.map((key) => [key, normalized.spec[key]]),
  ));
}

function normalizeTargetPart(value) {
  const text = normalizeString(value).toLowerCase();
  if (['base', 'base_part', '底壳', '底座'].includes(text)) return 'base_part';
  if (['lid', 'lid_part', '上盖', '盖子'].includes(text)) return 'lid_part';
  return '';
}

function normalizeVector(value) {
  if (!Array.isArray(value) || value.length !== 3) return null;
  const vector = value.map(finiteNumber);
  return vector.every(Number.isFinite) ? vector : null;
}

function normalizePositivePair(value) {
  if (!Array.isArray(value) || value.length !== 2) return [];
  const pair = value.map(finiteNumber);
  return pair.every((item) => Number.isFinite(item) && item > 0) ? pair : [];
}

function normalizeDirection(value) {
  const vector = normalizeVector(value);
  if (!vector) return null;
  const length = Math.sqrt(vector.reduce((sum, item) => sum + item * item, 0));
  return length > 1e-6 ? vector : null;
}

function directionAlignment(left, right) {
  const a = normalizeDirection(left);
  const b = normalizeDirection(right);
  if (!a || !b) return -1;
  const aLength = Math.sqrt(a.reduce((sum, item) => sum + item * item, 0));
  const bLength = Math.sqrt(b.reduce((sum, item) => sum + item * item, 0));
  return a.reduce((sum, item, index) => sum + item * b[index], 0) / (aLength * bLength);
}

function pointToSurfacePlaneDistance(point, surface) {
  const normal = normalizeDirection(surface.normal_hint);
  const planePoint = normalizeVector(surface.point_hint);
  if (!normal || !planePoint) return Number.POSITIVE_INFINITY;
  const length = Math.sqrt(normal.reduce((sum, item) => sum + item * item, 0));
  return Math.abs(point.reduce((sum, item, index) => sum + (item - planePoint[index]) * normal[index], 0) / length);
}

function normalizeEngravingId(value) {
  const id = normalizeString(value);
  return /^engraving_[a-z0-9_-]{1,48}$/i.test(id) ? id : '';
}

function finiteNumber(value) {
  if (value === '' || value === null || value === undefined) return NaN;
  const number = Number(value);
  return Number.isFinite(number) ? number : NaN;
}

function normalizeRotation(value) {
  const number = finiteNumber(value);
  if (!Number.isFinite(number)) return 0;
  return ((number % 360) + 360) % 360;
}

function normalizeLineSpacing(value) {
  const number = finiteNumber(value);
  if (!Number.isFinite(number)) return 1.2;
  return Math.min(3, Math.max(0.8, number));
}

function createEngravingId(spec, index) {
  return `engraving_${crypto.createHash('sha1').update(JSON.stringify({ spec, index })).digest('hex').slice(0, 10)}`;
}

function pythonLiteral(value) {
  if (value === null || value === undefined) return 'None';
  if (typeof value === 'boolean') return value ? 'True' : 'False';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : 'None';
  if (typeof value === 'string') return JSON.stringify(value.replace(/[\uD800-\uDFFF]/g, '?'));
  if (Array.isArray(value)) return `[${value.map(pythonLiteral).join(', ')}]`;
  if (typeof value === 'object') {
    return `{${Object.entries(value).map(([key, item]) => `${pythonLiteral(key)}: ${pythonLiteral(item)}`).join(', ')}}`;
  }
  return 'None';
}

function buildSurfaceEngravingNeedsInput({
  message,
  questions,
  blockingReason,
  currentEngravings,
  draft = null,
  preflight = null,
  unsupportedLayout = null,
}) {
  return {
    status: 'needs_input',
    title: '需要确认刻字参数',
    message: userFacingEngravingMessage(message),
    questions: userFacingEngravingQuestions(questions),
    blocking_reason: blockingReason,
    surface_engravings: currentEngravings || [],
    surface_engraving_draft: draft,
    surface_engraving_turns: normalizeEngravingTurns(draft?.user_turns),
    surface_engraving_unsupported_layout: unsupportedLayout,
    surface_engraving_preflight: preflight,
    source: 'llm_surface_engraving',
  };
}

function userFacingEngravingMessage(value) {
  const message = normalizeString(value);
  if (!message || containsInternalEngravingTerm(message)) return USER_GENERIC_GUIDANCE;
  return message;
}

function userFacingEngravingQuestions(value) {
  const questions = normalizeQuestions(value);
  const result = [];
  const add = (question) => {
    const normalized = normalizeString(question);
    if (normalized && !result.includes(normalized)) result.push(normalized);
  };
  for (const question of questions) {
    let handled = false;
    if (/(?:建议|最多|不超过).{0,16}\d+(?:\.\d+)?\s*(?:mm|毫米)/i.test(question)) {
      add(question);
      handled = true;
    }
    if (/(?:具体平面位置|九宫格锚点|\banchor\b|top_left|top_center|top_right|center_left|center_right|bottom_left|bottom_center|bottom_right|offset_[uv]_mm|局部偏移|偏移量)/i.test(question)) {
      add(USER_POSITION_GUIDANCE);
      add(USER_POSITION_EXAMPLE);
      add(USER_OFFSET_EXAMPLE);
      handled = true;
    }
    if (!handled && /(?:字体高度|字高|font_height_mm)/i.test(question)) {
      add(USER_FONT_HEIGHT_GUIDANCE);
      handled = true;
    }
    if (/(?:目标零件|目标外部平面|可唯一识别的目标外部平面|target_part|base_part|lid_part|normal_hint|point_hint|x_direction|法向量|参考点|世界坐标)/i.test(question)) {
      add(USER_SURFACE_GUIDANCE);
      handled = true;
    }
    if (/(?:文字内容|刻字内容|(?:^|[^a-z])text(?:[^a-z]|$))/i.test(question)) {
      add(USER_TEXT_GUIDANCE);
      handled = true;
    }
    if (!handled) {
      add(containsInternalEngravingTerm(question) ? USER_GENERIC_GUIDANCE : question);
    }
  }
  if (!result.length) add(USER_GENERIC_GUIDANCE);
  return result.slice(0, 8);
}

function containsInternalEngravingTerm(value) {
  return /(?:surface_engraving_[a-z_]+|target_part|base_part|lid_part|\banchor\b|top_left|top_center|top_right|center_left|center_right|bottom_left|bottom_center|bottom_right|offset_[uv]_mm|font_height_mm|normal_hint|point_hint|x_direction|九宫格锚点)/i.test(normalizeString(value));
}

function normalizeQuestions(value) {
  if (!Array.isArray(value)) return [];
  return value.map(normalizeString).filter(Boolean).slice(0, 8);
}

function currentDesignStateFromBody(body = {}) {
  if (isPlainObject(body.currentDesignState)) return body.currentDesignState;
  if (isPlainObject(body.current_design_state)) return body.current_design_state;
  if (isPlainObject(body.designState)) return body.designState;
  if (isPlainObject(body.design_state)) return body.design_state;
  return null;
}

function runProcess(command, args, { cwd, input = '', timeoutMs = 15000 } = {}) {
  return new Promise((resolve) => {
    const child = spawn(command, args, {
      cwd,
      env: {
        ...process.env,
        PYTHONUTF8: '1',
        PYTHONIOENCODING: 'utf-8',
      },
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    let finished = false;
    const timeout = setTimeout(() => {
      if (!finished) child.kill();
    }, timeoutMs);
    child.stdout.on('data', (chunk) => { stdout += chunk.toString(); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString(); });
    child.on('error', (error) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve({ exitCode: -1, stdout, stderr: error.message || String(error) });
    });
    child.on('close', (code) => {
      if (finished) return;
      finished = true;
      clearTimeout(timeout);
      resolve({ exitCode: code ?? -1, stdout, stderr });
    });
    child.stdin.end(input);
  });
}

function lastNonEmptyLine(value = '') {
  return String(value).split(/\r?\n/).map((line) => line.trim()).filter(Boolean).at(-1) || '';
}
