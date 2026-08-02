import { createHash } from 'node:crypto';
import { spawn } from 'node:child_process';
import {
  getIntentModelConfig,
  requestChatCompletionJson,
} from './model-sources.js';

/**
 * The model-edit contract is deliberately independent from the HTTP route.
 * A route can stage a plan, validate it, ask for confirmation, and then hand
 * the resulting source to project-store without giving the model a filesystem
 * handle.
 */
export const MODEL_EDIT_PLAN_SCHEMA_VERSION = 'model_edit_plan_v1';
export const PROJECT_MEMORY_SCHEMA_VERSION = 'project_memory_v1';
export const MAX_MODEL_EDIT_SOURCE_BYTES = 2 * 1024 * 1024;
export const MAX_MODEL_EDIT_PATCHES = 64;

const ALLOWED_PYTHON_IMPORTS = new Set(['cadquery', 'math', 'json']);
const HIGH_RISK_WORDS = /(delete|remove|replace|cut|hole|opening|slot|cutout|shell|body|structure|base_part|lid_part|hardware|wall|fillet|chamfer|roundover|开孔|扩孔|封孔|孔洞|孔径|孔位|开口|槽口|开槽|挖槽|删除|移除|替换|主体|结构|底壳|上盖|硬件|壁厚|厚度|圆角|倒圆|倒角|切角|削平)/i;
const MEDIUM_RISK_WORDS = /(add|insert|move|translate|rotate|mount|dimension|parameter|offset|增加|新增|移动|平移|旋转|安装|尺寸|参数|偏移)/i;
const LOW_RISK_WORDS = /(engrave|label|text|cosmetic|刻字|文字|标记|铭牌|外观)/i;
const FORBIDDEN_NAMES = new Set([
  'open', 'exec', 'eval', 'compile', '__import__', 'input', 'globals', 'locals', 'vars', 'dir',
  'getattr', 'setattr', 'delattr', 'breakpoint', 'help', 'exit', 'quit',
  'subprocess', 'os', 'sys', 'pathlib', 'shutil', 'socket', 'requests', 'urllib', 'http',
  'importlib', 'builtins', 'ctypes', 'pickle', 'marshal', 'tempfile',
  'export', 'exportshape', 'exportdxf', 'exportstep', 'save', 'load', 'dump',
  'importstep', 'importdxf', 'importbrep', 'importbin', 'importshape',
  'read_text', 'write_text', 'read_bytes', 'write_bytes', 'unlink', 'remove',
]);
const FORBIDDEN_CALL_PATTERN = /\b(?:open|exec|eval|compile|__import__|input|globals|locals|vars|dir|getattr|setattr|delattr|breakpoint)\s*\(/i;
const FORBIDDEN_MODULE_PATTERN = /\b(?:subprocess|os|sys|pathlib|shutil|socket|requests|urllib|http|importlib|builtins|ctypes|pickle|marshal|tempfile)\b/i;
const FORBIDDEN_IO_ATTRIBUTE_PATTERN = /\.(?:export|save|load|dump|read_text|write_text|read_bytes|write_bytes|unlink|remove|mkdir|rmdir)\s*\(/i;
const FORBIDDEN_CADQUERY_IO_PATTERN = /\b(?:exporters|importers)\b|\.(?:exportshape|exportdxf|exportstep|importstep|importdxf|importbrep|importbin|importshape)\s*\(/i;

export function hashCadQuerySource(source = '') {
  return createHash('sha256').update(String(source), 'utf8').digest('hex');
}

// Short alias used by project-store integrations.
export const hashSource = hashCadQuerySource;

export function isValidSourceHash(value) {
  return typeof value === 'string' && /^[a-f0-9]{64}$/i.test(value.trim());
}

/**
 * Keep patch targets inside the active project. The source filename is a
 * basename because project-store owns the actual absolute directory.
 */
export function validateProjectRelativePath(value, { sourceFilename = '' } = {}) {
  const input = typeof value === 'string' ? value.trim().replaceAll('\\', '/') : '';
  if (!input) return { status: 'pass', path: sourceFilename || '' };
  const normalizedSource = typeof sourceFilename === 'string'
    ? sourceFilename.trim().replaceAll('\\', '/')
    : '';
  const invalid = !input
    || input.startsWith('/')
    || /^[a-zA-Z]:\//.test(input)
    || input.includes('/')
    || input.split('/').some((part) => part === '..' || part === '.' || part === '')
    || input.includes('\0');
  if (invalid) {
    return {
      status: 'fail',
      code: 'project_scope_violation',
      message: '模型补丁只能指向当前项目源码，不能使用绝对路径或目录跳转。',
      path: input,
    };
  }
  if (normalizedSource && input !== normalizedSource) {
    return {
      status: 'fail',
      code: 'project_source_target_mismatch',
      message: '模型补丁只能修改当前项目的主 CadQuery 源码。',
      path: input,
      expected: normalizedSource,
    };
  }
  if (!normalizedSource && !/\.py$/i.test(input)) {
    return {
      status: 'fail',
      code: 'project_source_target_mismatch',
      message: '模型补丁目标必须是当前项目的 CadQuery Python 源码文件。',
      path: input,
    };
  }
  return { status: 'pass', path: input };
}

export function normalizeModelEditPatch(value = {}, { sourceFilename = '' } = {}) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return { status: 'fail', code: 'invalid_patch', message: '模型补丁必须是对象。' };
  }
  const oldText = firstNonEmptyDefinedString(value.old_text, value.oldText, value.before, value.from);
  const newText = firstDefinedString(value.new_text, value.newText, value.after, value.to);
  const targetFile = firstString(value.target_file, value.targetFile, value.file, value.path);
  const scope = validateProjectRelativePath(targetFile, { sourceFilename });
  if (scope.status === 'fail') return scope;
  if (!oldText) {
    return {
      status: 'fail',
      code: 'empty_old_text',
      message: '精确补丁必须提供非空 old_text，避免把代码写到未确认的位置。',
    };
  }
  if (newText === null) {
    return { status: 'fail', code: 'missing_new_text', message: '精确补丁缺少 new_text。' };
  }
  const occurrence = parsePositiveInteger(value.occurrence || value.occurrence_index);
  const expectedCount = parsePositiveInteger(value.expected_count || value.expectedCount);
  return {
    status: 'pass',
    patch: {
      id: normalizeStableId(value.id || value.patch_id || value.patchId) || '',
      target_file: scope.path,
      old_text: oldText,
      new_text: newText,
      occurrence: occurrence || null,
      expected_count: expectedCount || null,
      reason: redactSensitiveText(firstString(value.reason, value.summary, value.description) || ''),
    },
  };
}

export function normalizeModelEditPatches(value = {}, options = {}) {
  let raw = [];
  if (Array.isArray(value)) raw = value;
  else if (value && typeof value === 'object') {
    if (Array.isArray(value.patches)) raw = value.patches;
    else if (Array.isArray(value.code_patches)) raw = value.code_patches;
    else if (Array.isArray(value.codePatches)) raw = value.codePatches;
    else if (value.patch && typeof value.patch === 'object') raw = [value.patch];
    else if (value.old_text !== undefined || value.oldText !== undefined) raw = [value];
  }
  const errors = [];
  const patches = [];
  if (raw.length > MAX_MODEL_EDIT_PATCHES) {
    errors.push({ code: 'too_many_patches', message: `一次修改最多允许 ${MAX_MODEL_EDIT_PATCHES} 个精确补丁。` });
  }
  for (const item of raw.slice(0, MAX_MODEL_EDIT_PATCHES)) {
    const normalized = normalizeModelEditPatch(item, options);
    if (normalized.status === 'fail') errors.push(normalized);
    else patches.push(normalized.patch);
  }
  return { status: errors.length ? 'fail' : 'pass', patches, errors };
}

/**
 * Apply old_text/new_text patches with an optimistic source hash check. No
 * path is opened here; the caller supplies the source read from project-store
 * and writes the returned source only after the rest of validation succeeds.
 */
export function applyExactSourcePatches({
  source = '',
  patches = [],
  expectedSourceHash = '',
  sourceHash = '',
  sourceFilename = '',
  requireExpectedHash = true,
} = {}) {
  const original = typeof source === 'string' ? source : '';
  if (Buffer.byteLength(original, 'utf8') > MAX_MODEL_EDIT_SOURCE_BYTES) {
    return failure('source_too_large', '当前项目源码超过允许的安全大小。');
  }
  const expected = String(expectedSourceHash || sourceHash || '').trim().toLowerCase();
  const actual = hashCadQuerySource(original);
  if (requireExpectedHash && !isValidSourceHash(expected)) {
    return failure('missing_source_hash', '模型修改缺少当前项目源码哈希，已拒绝执行。', { actual_source_hash: actual });
  }
  if (expected && expected !== actual) {
    return failure('source_hash_mismatch', '当前项目源码已发生变化，请重新读取项目后再修改。', {
      expected_source_hash: expected,
      actual_source_hash: actual,
    });
  }
  if (!Array.isArray(patches) || patches.length > MAX_MODEL_EDIT_PATCHES) {
    return failure('invalid_patch_set', '模型补丁集合格式不正确。');
  }
  let next = original;
  let trustedSourceRanges = original.length
    ? [{ current_start: 0, current_end: original.length, baseline_start: 0, baseline_end: original.length }]
    : [];
  const applied = [];
  for (const input of patches) {
    const normalized = normalizeModelEditPatch(input, { sourceFilename });
    if (normalized.status === 'fail') return failure(normalized.code, normalized.message, normalized);
    const patch = normalized.patch;
    const occurrences = countOccurrences(next, patch.old_text);
    if (patch.expected_count !== null && occurrences !== patch.expected_count) {
      return failure('patch_expected_count_mismatch', `补丁 ${patch.id || '(未命名)'} 的 old_text 出现次数与预期不符。`, {
        patch_id: patch.id,
        expected_count: patch.expected_count,
        actual_count: occurrences,
      });
    }
    if (!occurrences) {
      return failure('patch_old_text_not_found', `补丁 ${patch.id || '(未命名)'} 的 old_text 在当前源码中不存在。`, { patch_id: patch.id });
    }
    if (occurrences > 1 && !patch.occurrence) {
      return failure('patch_old_text_ambiguous', `补丁 ${patch.id || '(未命名)'} 的 old_text 出现多次，请提供稳定上下文。`, {
        patch_id: patch.id,
        actual_count: occurrences,
      });
    }
    const index = patch.occurrence
      ? findOccurrenceIndex(next, patch.old_text, patch.occurrence)
      : next.indexOf(patch.old_text);
    if (index < 0) {
      return failure('patch_occurrence_not_found', `补丁 ${patch.id || '(未命名)'} 指定的出现位置不存在。`, { patch_id: patch.id });
    }
    trustedSourceRanges = updateTrustedSourceRangesForReplacement(
      trustedSourceRanges,
      index,
      patch.old_text,
      patch.new_text,
    );
    next = `${next.slice(0, index)}${patch.new_text}${next.slice(index + patch.old_text.length)}`;
    if (Buffer.byteLength(next, 'utf8') > MAX_MODEL_EDIT_SOURCE_BYTES) {
      return failure('source_too_large', '补丁应用后源码超过允许的安全大小。', { patch_id: patch.id });
    }
    applied.push({
      id: patch.id,
      target_file: patch.target_file,
      old_text_sha256: hashCadQuerySource(patch.old_text),
      new_text_sha256: hashCadQuerySource(patch.new_text),
      occurrence: patch.occurrence || 1,
      reason: patch.reason,
    });
  }
  return {
    status: 'pass',
    source: next,
    source_hash_before: actual,
    source_hash_after: hashCadQuerySource(next),
    applied_patches: applied,
    trusted_source_ranges: trustedSourceRanges,
  };
}

export function validateCadQuerySourceSafety(source = '', {
  requireCadQueryImport = false,
  baselineSource = '',
  trustedSourceRanges = null,
} = {}) {
  const result = scanCadQuerySourceSafety(source, { requireCadQueryImport });
  if (typeof baselineSource !== 'string' || !baselineSource) return result;
  const baseline = scanCadQuerySourceSafety(baselineSource, { requireCadQueryImport: false });
  const trustedRanges = Array.isArray(trustedSourceRanges)
    ? normalizeTrustedSourceRanges(trustedSourceRanges)
    : buildConservativeTrustedSourceRanges(baselineSource, String(source || ''));
  const errors = subtractBaselineSafetyErrors(result.errors, baseline.errors, trustedRanges);
  return {
    ...result,
    status: errors.length ? 'fail' : 'pass',
    message: errors.length ? '模型源码未通过安全检查。' : '模型源码通过增量静态安全检查。',
    errors,
    baseline_issues_allowed: Math.max(0, result.errors.length - errors.length),
  };
}

function scanCadQuerySourceSafety(source = '', { requireCadQueryImport = false } = {}) {
  const code = typeof source === 'string' ? source : '';
  const errors = [];
  const warnings = [];
  if (!code.trim()) errors.push({ code: 'empty_source', message: 'CadQuery 源码为空。' });
  if (Buffer.byteLength(code, 'utf8') > MAX_MODEL_EDIT_SOURCE_BYTES) {
    errors.push({ code: 'source_too_large', message: 'CadQuery 源码超过允许的安全大小。' });
  }
  const masked = maskPythonStringsAndComments(code);
  const imports = collectPythonImports(masked);
  for (const item of imports) {
    if (!ALLOWED_PYTHON_IMPORTS.has(item.module)) {
      errors.push({
        code: 'forbidden_import',
        message: `禁止导入 Python 模块 ${item.module}。`,
        module: item.module,
        start: item.start,
        end: item.end,
      });
    }
    if (item.module === 'json' && !/^import\s+json$/i.test(item.statement)) {
      errors.push({
        code: 'restricted_json_import',
        message: 'JSON 只允许使用“import json”后调用内存解析接口。',
        start: item.start,
        end: item.end,
      });
    }
  }
  if (requireCadQueryImport && !imports.some((item) => item.module === 'cadquery')) {
    errors.push({ code: 'missing_cadquery_import', message: '项目源码必须显式导入 cadquery。' });
  }
  pushPatternSafetyErrors(errors, masked, FORBIDDEN_CALL_PATTERN, {
    code: 'forbidden_call',
    message: '源码包含文件、进程或动态执行调用。',
  });
  pushPatternSafetyErrors(errors, masked, FORBIDDEN_MODULE_PATTERN, {
    code: 'forbidden_module',
    message: '源码包含文件、网络或系统模块。',
  });
  pushPatternSafetyErrors(errors, masked, FORBIDDEN_IO_ATTRIBUTE_PATTERN, {
    code: 'forbidden_io_api',
    message: '项目源码不能自行导入或导出文件。',
  });
  pushPatternSafetyErrors(errors, masked, FORBIDDEN_CADQUERY_IO_PATTERN, {
    code: 'forbidden_io_api',
    message: '项目源码不能自行导入或导出文件。',
  });
  pushPatternSafetyErrors(errors, masked, /__[^\n]{0,80}?__/, {
    code: 'dunder_access',
    message: '禁止通过双下划线属性绕过项目代码安全边界。',
  });
  pushPatternSafetyErrors(errors, masked, /^\s*(?:global|nonlocal)\s+[^\r\n]+/m, {
    code: 'global_state_mutation',
    message: '禁止修改解释器全局状态。',
  });
  if (/\b(?:with|try)\s*\(/.test(masked)) {
    warnings.push({ code: 'complex_control_flow', message: '复杂控制流将由 CadQuery 运行预检再次检查。' });
  }
  return {
    status: errors.length ? 'fail' : 'pass',
    id: 'model_edit_source_safety',
    message: errors.length ? '模型源码未通过安全检查。' : '模型源码通过静态安全检查。',
    errors,
    warnings,
    imports,
  };
}

function pushPatternSafetyErrors(errors, source, pattern, { code, message }) {
  const flags = pattern.flags.includes('g') ? pattern.flags : `${pattern.flags}g`;
  const matcher = new RegExp(pattern.source, flags);
  for (const match of source.matchAll(matcher)) {
    const tokenStart = Number(match.index);
    const lineStart = source.lastIndexOf('\n', Math.max(0, tokenStart - 1)) + 1;
    const nextNewline = source.indexOf('\n', tokenStart);
    const lineEnd = nextNewline < 0 ? source.length : nextNewline;
    errors.push({
      code,
      message,
      token: String(match[0] || '').trim().toLowerCase(),
      start: lineStart,
      end: lineEnd,
    });
  }
}

function subtractBaselineSafetyErrors(currentErrors = [], baselineErrors = [], trustedSourceRanges = []) {
  const alwaysEnforced = new Set(['empty_source', 'source_too_large', 'missing_cadquery_import', 'python_syntax']);
  const matchedBaselineErrors = new Set();
  const remaining = [];
  for (const error of currentErrors) {
    if (alwaysEnforced.has(error?.code)) {
      remaining.push(error);
      continue;
    }
    const mappedRange = mapCurrentErrorToBaseline(error, trustedSourceRanges);
    if (!mappedRange) {
      remaining.push(error);
      continue;
    }
    const key = safetyErrorFingerprint(error);
    const baselineIndex = baselineErrors.findIndex((baselineError, index) => (
      !matchedBaselineErrors.has(index)
      && safetyErrorFingerprint(baselineError) === key
      && baselineError?.start === mappedRange.start
      && baselineError?.end === mappedRange.end
    ));
    if (baselineIndex < 0) remaining.push(error);
    else matchedBaselineErrors.add(baselineIndex);
  }
  return remaining;
}

function safetyErrorFingerprint(error = {}) {
  return JSON.stringify([
    error.code || '',
    error.module || '',
    error.token || '',
    error.message || '',
    error.node_type || '',
    error.semantic || '',
  ]);
}

function mapCurrentErrorToBaseline(error = {}, trustedSourceRanges = []) {
  const start = Number(error.start);
  const end = Number(error.end);
  if (!Number.isInteger(start) || !Number.isInteger(end) || start < 0 || end <= start) return null;
  const range = trustedSourceRanges.find((item) => (
    item.current_start <= start && item.current_end >= end
  ));
  if (!range) return null;
  const baselineStart = range.baseline_start + (start - range.current_start);
  return { start: baselineStart, end: baselineStart + (end - start) };
}

function buildConservativeTrustedSourceRanges(baselineSource = '', currentSource = '') {
  const baseline = String(baselineSource || '');
  const current = String(currentSource || '');
  const prefixLength = commonPrefixLength(baseline, current);
  const suffixLength = commonSuffixLength(baseline, current, prefixLength);
  return normalizeTrustedSourceRanges([
    prefixLength > 0
      ? { current_start: 0, current_end: prefixLength, baseline_start: 0, baseline_end: prefixLength }
      : null,
    suffixLength > 0
      ? {
        current_start: current.length - suffixLength,
        current_end: current.length,
        baseline_start: baseline.length - suffixLength,
        baseline_end: baseline.length,
      }
      : null,
  ].filter(Boolean));
}

function updateTrustedSourceRangesForReplacement(ranges = [], index = 0, oldText = '', newText = '') {
  const oldLength = String(oldText).length;
  const replacement = String(newText);
  const oldEnd = index + oldLength;
  const delta = replacement.length - oldLength;
  const prefixLength = commonPrefixLength(String(oldText), replacement);
  const suffixLength = commonSuffixLength(String(oldText), replacement, prefixLength);
  const next = [];
  projectTrustedRange(ranges, 0, index, 0, next);
  projectTrustedRange(ranges, index, index + prefixLength, index, next);
  if (suffixLength > 0) {
    projectTrustedRange(
      ranges,
      oldEnd - suffixLength,
      oldEnd,
      index + replacement.length - suffixLength,
      next,
    );
  }
  projectTrustedRange(ranges, oldEnd, Number.POSITIVE_INFINITY, oldEnd + delta, next);
  return normalizeTrustedSourceRanges(next);
}

function projectTrustedRange(ranges, oldStart, oldEnd, newStart, output) {
  if (!(oldEnd > oldStart)) return;
  for (const range of ranges) {
    const intersectionStart = Math.max(range.current_start, oldStart);
    const intersectionEnd = Math.min(range.current_end, oldEnd);
    if (intersectionEnd <= intersectionStart) continue;
    const projectedStart = newStart + (intersectionStart - oldStart);
    output.push({
      current_start: projectedStart,
      current_end: projectedStart + (intersectionEnd - intersectionStart),
      baseline_start: range.baseline_start + (intersectionStart - range.current_start),
      baseline_end: range.baseline_start + (intersectionEnd - range.current_start),
    });
  }
}

function normalizeTrustedSourceRanges(ranges = []) {
  const normalized = ranges
    .map((range) => ({
      current_start: Number(range?.current_start),
      current_end: Number(range?.current_end),
      baseline_start: Number(range?.baseline_start),
      baseline_end: Number(range?.baseline_end),
    }))
    .filter((range) => (
      Number.isInteger(range.current_start)
      && Number.isInteger(range.current_end)
      && Number.isInteger(range.baseline_start)
      && Number.isInteger(range.baseline_end)
      && range.current_start >= 0
      && range.baseline_start >= 0
      && range.current_end > range.current_start
      && range.baseline_end - range.baseline_start === range.current_end - range.current_start
    ))
    .sort((left, right) => left.current_start - right.current_start || left.baseline_start - right.baseline_start);
  const merged = [];
  for (const range of normalized) {
    const previous = merged.at(-1);
    if (previous
      && previous.current_end === range.current_start
      && previous.baseline_end === range.baseline_start) {
      previous.current_end = range.current_end;
      previous.baseline_end = range.baseline_end;
    } else merged.push({ ...range });
  }
  return merged;
}

function commonPrefixLength(left = '', right = '') {
  const limit = Math.min(left.length, right.length);
  let length = 0;
  while (length < limit && left[length] === right[length]) length += 1;
  return length;
}

function commonSuffixLength(left = '', right = '', usedPrefixLength = 0) {
  const limit = Math.min(left.length, right.length) - usedPrefixLength;
  let length = 0;
  while (length < limit
    && left[left.length - length - 1] === right[right.length - length - 1]) length += 1;
  return length;
}

/**
 * Optional Python AST pass. Static checks are intentionally synchronous for
 * route-level validation; this pass is used before a staged source is built.
 */
export async function validateCadQuerySourceSafetyWithAst(source = '', {
  python = process.env.PYTHON || 'python',
  timeoutMs = 15000,
  requireCadQueryImport = false,
  baselineSource = '',
  trustedSourceRanges = null,
} = {}) {
  const trustedRanges = Array.isArray(trustedSourceRanges)
    ? normalizeTrustedSourceRanges(trustedSourceRanges)
    : typeof baselineSource === 'string' && baselineSource
      ? buildConservativeTrustedSourceRanges(baselineSource, String(source || ''))
      : [];
  const staticResult = validateCadQuerySourceSafety(source, {
    requireCadQueryImport,
    baselineSource,
    trustedSourceRanges: trustedRanges,
  });
  if (staticResult.status === 'fail') return staticResult;
  const script = buildAstSafetyScript();
  let result = await runPythonAstCheck(python, script, source, timeoutMs);
  if (result.status === 'fail' && typeof baselineSource === 'string' && baselineSource) {
    const baselineResult = await runPythonAstCheck(python, script, baselineSource, timeoutMs);
    if (baselineResult.status === 'fail') {
      const errors = subtractBaselineSafetyErrors(
        result.errors || [],
        baselineResult.errors || [],
        trustedRanges,
      );
      result = {
        ...result,
        status: errors.length ? 'fail' : 'pass',
        errors,
        baseline_issues_allowed: Math.max(0, (result.errors || []).length - errors.length),
      };
    }
  }
  if (result.status === 'pending') {
    return {
      ...staticResult,
      status: 'pending',
      id: 'model_edit_source_ast_pending',
      message: '静态安全检查通过，等待 Python AST 预检。',
      ast: result,
    };
  }
  if (result.status === 'fail') {
    return {
      ...staticResult,
      status: 'fail',
      id: 'model_edit_source_ast',
      message: '模型源码未通过 Python AST 安全检查。',
      errors: [...staticResult.errors, ...(result.errors || [])],
      ast: result,
    };
  }
  return { ...staticResult, ast: result };
}

export function classifyModelEditRisk(operations = [], patches = []) {
  const normalizedOperations = Array.isArray(operations) ? operations : [];
  const reasons = [];
  let level = 'low';
  const rank = { low: 0, medium: 1, high: 2 };
  const raise = (next, reason) => {
    if (rank[next] > rank[level]) level = next;
    if (reason && !reasons.includes(reason)) reasons.push(reason);
  };
  for (const operation of normalizedOperations) {
    const text = operationText(operation);
    const explicit = normalizeRisk(operation?.risk_level || operation?.riskLevel);
    if (explicit) raise(explicit, `操作 ${operation.id || operation.type || '未命名'} 标记为 ${explicit} 风险。`);
    if (operation?.destructive === true) raise('high', `操作 ${operation.id || operation.type || '未命名'} 会删除或替换现有结构。`);
    if (HIGH_RISK_WORDS.test(text)) raise('high', `操作 ${operation.id || operation.type || '未命名'} 可能改变主体、孔位或硬件结构。`);
    else if (MEDIUM_RISK_WORDS.test(text)) raise('medium', `操作 ${operation.id || operation.type || '未命名'} 会改变尺寸、位置或安装关系。`);
    else if (LOW_RISK_WORDS.test(text)) raise('low', `操作 ${operation.id || operation.type || '未命名'} 主要影响文字或外观。`);
  }
  for (const patch of Array.isArray(patches) ? patches : []) {
    const text = `${patch?.old_text || ''}\n${patch?.new_text || ''}`;
    const delta = Math.abs(String(patch?.new_text || '').length - String(patch?.old_text || '').length);
    // Operation labels come from the model and cannot downgrade what the code
    // actually changes. Direct edits to build entry points always need review.
    if (/(build_hollow_base|build_lid|base_part|lid_part|apply_mounts|hardware_reference_parts|def\s+|\.(?:cut|hole|cboreHole|cskHole|slot2D|fillet|chamfer)\s*\(|(?:hole|opening|slot|cutout)[a-z0-9_]*(?:diameter|radius|width|height|length|size|offset)|(?:fillet|chamfer|roundover)[a-z0-9_]*(?:radius|size)|(?:edge|corner)[a-z0-9_]*(?:radius|fillet|chamfer))/i.test(text)) {
      raise('high', '补丁触及主体构建入口或部件装配代码。');
    } else if (delta > 1200) {
      raise('medium', '补丁改动代码量较大，需要复核。');
    }
  }
  if (!normalizedOperations.length && !patches.length) {
    return { risk_level: 'low', requires_confirmation: false, reasons: ['没有可执行的模型修改操作。'] };
  }
  return {
    risk_level: level,
    requires_confirmation: level === 'high',
    reasons,
  };
}

export function normalizeModelEditOperation(value = {}, index = 0) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null;
  const type = normalizeStableId(value.type || value.operation || value.action || value.kind) || 'source_patch';
  const id = normalizeStableId(value.id || value.operation_id || value.operationId) || `${type}-${index + 1}`;
  const params = value.parameters && typeof value.parameters === 'object' ? value.parameters
    : value.params && typeof value.params === 'object' ? value.params : {};
  return {
    id,
    type,
    target_id: firstString(value.target_id, value.targetId, value.object_id, value.objectId) || '',
    summary: redactSensitiveText(firstString(value.summary, value.description, value.reason) || type),
    parameters: jsonSafe(params),
    risk_level: normalizeRisk(value.risk_level || value.riskLevel) || '',
    destructive: value.destructive === true,
  };
}

export function normalizeModelEditPlan(raw = {}, context = {}) {
  const source = typeof context.currentSource === 'string' ? context.currentSource : '';
  const sourceHash = firstString(raw.source_hash, raw.sourceHash, raw.base_source_hash, raw.baseSourceHash, context.sourceHash) || '';
  const rawOperations = Array.isArray(raw.operations)
    ? raw.operations
    : Array.isArray(raw.edits)
      ? raw.edits
      : [];
  const operations = rawOperations.map(normalizeModelEditOperation).filter(Boolean);
  const patchResult = normalizeModelEditPatches(raw, { sourceFilename: context.sourceFilename || raw.source_filename || '' });
  if (!operations.length && patchResult.patches.length) {
    operations.push({
      id: 'source-patch-1',
      type: 'source_patch',
      target_id: '',
      summary: '应用模型源码精确补丁',
      parameters: {},
      risk_level: '',
      destructive: false,
    });
  }
  const risk = classifyModelEditRisk(operations, patchResult.patches);
  const directSourceErrors = ['cadquery_code', 'new_source', 'full_source', 'replacement_source']
    .filter((key) => typeof raw[key] === 'string' && raw[key].trim())
    .map((key) => ({
      code: 'full_source_replacement_forbidden',
      message: `模型修改计划不能通过 ${key} 替换完整源码，必须使用精确补丁。`,
    }));
  const inheritedValidationErrors = Array.isArray(raw.validation_errors)
    ? raw.validation_errors
        .filter((item) => item && typeof item === 'object')
        .map((item) => ({
          code: normalizeStableId(item.code) || 'invalid_plan',
          message: redactSensitiveText(firstString(item.message) || '模型修改计划未通过前置校验。'),
        }))
    : [];
  const requestedStatus = normalizePlanStatus(raw.status);
  const inferredStatus = patchResult.errors.length || directSourceErrors.length
    ? 'blocked'
    : !operations.length && !patchResult.patches.length
      ? 'noop'
      : requestedStatus || 'ok';
  return {
    schema_version: MODEL_EDIT_PLAN_SCHEMA_VERSION,
    plan_id: normalizeStableId(raw.plan_id || raw.planId || raw.id) || buildStablePlanId({
      projectId: firstString(raw.project_id, raw.projectId, context.projectId) || '',
      sourceHash,
      summary: firstString(raw.intent_summary, raw.intentSummary, raw.summary, raw.message) || '',
      operations,
      patches: patchResult.patches,
    }),
    project_id: firstString(raw.project_id, raw.projectId, context.projectId) || '',
    intent_summary: redactSensitiveText(firstString(raw.intent_summary, raw.intentSummary, raw.summary, raw.message) || ''),
    source_hash: sourceHash.toLowerCase(),
    base_source_hash: sourceHash.toLowerCase(),
    source_filename: firstString(raw.source_filename, raw.sourceFilename, context.sourceFilename) || '',
    operations,
    patches: patchResult.patches,
    code_patches: patchResult.patches,
    risk_level: risk.risk_level,
    risk_reasons: risk.reasons,
    requires_confirmation: requestedStatus === 'needs_confirmation'
      || raw.requires_confirmation === true
      || raw.requiresConfirmation === true
      || risk.requires_confirmation,
    current_project_only: raw.current_project_only !== false && raw.currentProjectOnly !== false,
    status: inferredStatus,
    questions: normalizeTextList(raw.questions),
    unsupported_requests: normalizeTextList(raw.unsupported_requests || raw.unsupportedRequests),
    warnings: normalizeTextList(raw.warnings),
    memory_update: normalizeMemoryUpdate(raw.memory_update || raw.memoryUpdate),
    validation_errors: [...inheritedValidationErrors, ...patchResult.errors, ...directSourceErrors],
  };
}

export function validateModelEditPlan(planOrRaw = {}, {
  source = '',
  sourceHash = '',
  projectId = '',
  sourceFilename = '',
  requireExpectedHash = true,
  requireCadQueryImport = false,
} = {}) {
  // Plans cross an HTTP/LLM trust boundary. Normalize every plan again even
  // when it already advertises the current schema so callers cannot smuggle a
  // downgraded risk flag or unnormalized operation through confirmation.
  const plan = normalizeModelEditPlan(planOrRaw, {
    currentSource: source,
    sourceHash,
    projectId,
    sourceFilename,
  });
  const errors = [...(Array.isArray(plan.validation_errors) ? plan.validation_errors : [])];
  if (plan.schema_version !== MODEL_EDIT_PLAN_SCHEMA_VERSION) {
    errors.push({ code: 'invalid_plan_schema', message: '模型修改计划版本不受支持。' });
  }
  if (plan.current_project_only !== true) {
    errors.push({ code: 'project_scope_violation', message: '模型修改只能作用于当前项目副本。' });
  }
  if (projectId && plan.project_id !== projectId) {
    errors.push({ code: 'project_id_mismatch', message: '模型修改计划不属于当前项目。' });
  }
  if (plan.operations.length > 0 && plan.patches.length === 0 && !['needs_input', 'noop'].includes(plan.status)) {
    errors.push({ code: 'missing_code_patch', message: '模型修改计划描述了操作，但没有提供可执行的精确源码补丁。' });
  }
  const expectedHash = firstString(plan.source_hash, plan.base_source_hash, sourceHash) || '';
  const patchResult = applyExactSourcePatches({
    source,
    patches: plan.patches || plan.code_patches,
    expectedSourceHash: expectedHash,
    sourceFilename: sourceFilename || plan.source_filename,
    requireExpectedHash,
  });
  if (patchResult.status === 'fail') errors.push({ code: patchResult.code, message: patchResult.message, details: patchResult });
  if (patchResult.status === 'pass'
    && plan.patches.length > 0
    && patchResult.source_hash_before === patchResult.source_hash_after) {
    errors.push({ code: 'no_source_change', message: '模型补丁应用后源码没有发生变化，已拒绝报告为成功修改。' });
  }
  const patchSafety = patchResult.status === 'pass'
    ? validateModelEditPatchSafety(plan.patches)
    : null;
  if (patchSafety?.status === 'fail') errors.push(...patchSafety.errors);
  const safety = patchResult.status === 'pass'
    ? validateCadQuerySourceSafety(patchResult.source, {
      requireCadQueryImport,
      baselineSource: source,
      trustedSourceRanges: patchResult.trusted_source_ranges,
    })
    : null;
  if (safety?.status === 'fail') errors.push(...safety.errors);
  const status = errors.length
    ? 'blocked'
    : ['needs_input', 'blocked'].includes(plan.status)
      ? plan.status
    : plan.status === 'noop'
      ? 'noop'
      : plan.requires_confirmation
        ? 'needs_confirmation'
        : 'ok';
  return {
    status,
    valid: !errors.length,
    ok: !errors.length,
    plan,
    source: patchResult.status === 'pass' ? patchResult.source : source,
    source_hash_before: patchResult.source_hash_before || hashCadQuerySource(source),
    source_hash_after: patchResult.source_hash_after || hashCadQuerySource(source),
    applied_patches: patchResult.applied_patches || [],
    trusted_source_ranges: patchResult.trusted_source_ranges || [],
    patch_safety: patchSafety,
    safety,
    risk: classifyModelEditRisk(plan.operations, plan.patches),
    errors,
    message: errors.length
      ? '模型修改计划未通过校验，原项目源码保持不变。'
      : status === 'needs_confirmation'
        ? '模型修改计划需要用户确认后才能写入项目副本。'
        : status === 'noop'
          ? '没有检测到可执行的模型修改。'
          : '模型修改计划通过校验，可以在当前项目副本中构建。',
  };
}

function validateModelEditPatchSafety(patches = []) {
  const errors = [];
  const warnings = [];
  for (const patch of Array.isArray(patches) ? patches : []) {
    if (!String(patch?.new_text ?? '').trim()) continue;
    const result = validateCadQuerySourceSafety(String(patch.new_text), {
      baselineSource: String(patch.old_text || ''),
    });
    for (const error of result.errors || []) {
      if (error.code === 'empty_source' || error.code === 'missing_cadquery_import') continue;
      errors.push({ ...error, patch_id: patch.id || '' });
    }
    for (const warning of result.warnings || []) {
      warnings.push({ ...warning, patch_id: patch.id || '' });
    }
  }
  return {
    status: errors.length ? 'fail' : 'pass',
    id: 'model_edit_patch_delta_safety',
    message: errors.length ? '模型补丁新增了不允许的代码结构。' : '模型补丁增量通过静态安全检查。',
    errors,
    warnings,
  };
}

export async function validateModelEditPlanWithAst(planOrRaw = {}, options = {}) {
  const validation = validateModelEditPlan(planOrRaw, options);
  if (!validation.valid || validation.status === 'noop') return validation;
  const astSafety = await validateCadQuerySourceSafetyWithAst(validation.source, {
    python: options.python,
    timeoutMs: options.timeoutMs,
    requireCadQueryImport: options.requireCadQueryImport,
    baselineSource: options.source,
    trustedSourceRanges: validation.trusted_source_ranges,
  });
  if (astSafety.status !== 'pass') {
    return {
      ...validation,
      status: 'blocked',
      valid: false,
      ok: false,
      safety: astSafety,
      errors: [
        ...validation.errors,
        ...(astSafety.errors || [{ code: astSafety.id || 'python_ast_unavailable', message: astSafety.message }]),
      ],
      message: astSafety.status === 'pending'
        ? 'Python AST 预检不可用，模型修改未写入当前项目。'
        : '模型修改计划未通过 Python AST 安全检查，原项目源码保持不变。',
    };
  }
  return { ...validation, safety: astSafety };
}

export function buildProjectMemoryUpdate({
  plan = {},
  previousMemory = {},
  projectId = '',
  sourceHashBefore = '',
  sourceHashAfter = '',
  revisionId = '',
  timestamp = new Date().toISOString(),
} = {}) {
  const previous = normalizeProjectMemory(previousMemory, { projectId });
  const update = normalizeMemoryUpdate(plan.memory_update || plan.memoryUpdate);
  const summary = redactSensitiveText(plan.intent_summary || plan.summary || '');
  const revision = {
    revision_id: normalizeStableId(revisionId || plan.plan_id) || `revision-${Date.now().toString(36)}`,
    plan_id: normalizeStableId(plan.plan_id || plan.planId) || '',
    timestamp,
    summary,
    risk_level: normalizeRisk(plan.risk_level) || 'low',
    operation_ids: Array.isArray(plan.operations) ? plan.operations.map((item) => item?.id).filter(Boolean) : [],
    source_hash_before: sourceHashBefore || plan.source_hash || '',
    source_hash_after: sourceHashAfter || '',
  };
  const revisions = appendUniqueById(previous.revisions, revision, 'revision_id', 100);
  return {
    ...previous,
    schema_version: PROJECT_MEMORY_SCHEMA_VERSION,
    project_id: projectId || previous.project_id || plan.project_id || '',
    summary: update.summary || summary || previous.summary,
    facts: mergeTextItems(
      previous.facts.filter((item) => !update.remove_facts.includes(item)),
      update.facts,
    ),
    decisions: mergeTextItems(previous.decisions, update.decisions),
    constraints: mergeTextItems(previous.constraints, update.constraints),
    objects: mergeObjects(previous.objects, update.objects),
    revisions,
    last_revision_id: revision.revision_id,
    project_source_hash: sourceHashAfter || previous.project_source_hash || '',
    updated_at: timestamp,
  };
}

export function mergeProjectMemory(previousMemory = {}, update = {}, context = {}) {
  return buildProjectMemoryUpdate({
    ...context,
    previousMemory,
    plan: { ...context.plan, memory_update: update },
  });
}

export function normalizeProjectMemory(value = {}, { projectId = '' } = {}) {
  const input = value && typeof value === 'object' && !Array.isArray(value) ? value : {};
  return {
    schema_version: PROJECT_MEMORY_SCHEMA_VERSION,
    project_id: firstString(input.project_id, input.projectId, projectId) || '',
    summary: redactSensitiveText(firstString(input.summary, input.memory_summary) || ''),
    facts: normalizeTextList(input.facts),
    decisions: normalizeTextList(input.decisions),
    constraints: normalizeTextList(input.constraints),
    objects: Array.isArray(input.objects) ? input.objects.filter((item) => item && typeof item === 'object').slice(-100).map(jsonSafe) : [],
    revisions: Array.isArray(input.revisions) ? input.revisions.filter((item) => item && typeof item === 'object').slice(-100).map(jsonSafe) : [],
    last_revision_id: firstString(input.last_revision_id, input.lastRevisionId) || '',
    project_source_hash: firstString(input.project_source_hash, input.projectSourceHash) || '',
    updated_at: firstString(input.updated_at, input.updatedAt) || '',
  };
}

export function buildModelEditSystemPrompt() {
  return [
    '你是 ZW-CAD-intent 当前项目模型修改 agent。',
    '只修改用户当前项目副本中的主 CadQuery 源码；公共模板、其他项目、ZW-CAD-code 和服务器代码均为只读。',
    '理解用户自然语言后输出 JSON，不要输出 Markdown、Python 文件或绝对路径。',
    '输出 schema_version=model_edit_plan_v1，包含 intent_summary、project_id、source_hash、operations、patches、risk_level、requires_confirmation、memory_update。',
    '每个 patches 项必须提供 target_file（可省略，省略表示当前主源码）、唯一且有足够上下文的 old_text、new_text；后端会要求 old_text 在当前源码中精确匹配。',
    '不得猜测当前源码中不存在的对象。无法确定目标时返回 needs_input 和具体中文问题，不要生成危险补丁。',
    '结合最近可见对话理解“这个面、最高处的边、刚才那个孔”等指代；最新明确动作优先于旧草稿。',
    '“圆角、倒圆、R2、圆角半径 2mm”对应 CadQuery fillet，数值为圆角半径；“倒角、切角、C2、45°倒角”对应 chamfer，数值为倒角尺寸。不要混淆 fillet 与 chamfer。',
    '优先用 model_index 的稳定对象/表面 ID 和源码几何语义确定目标边；如果多个边都符合“最高处的边”等描述，返回 needs_input，用自然中文列出候选边及区分方法。',
    '删除/替换硬件、开孔、主体结构、底壳/上盖、壁厚、圆角、倒角、孔槽和硬件安装关系等实体结构变化必须标记 requires_confirmation=true。刻字内容、排版和纯外观标记可低风险，但仍必须保留源码哈希。',
    '禁止导入文件、网络、系统、进程、反射或动态执行模块；只允许 cadquery、math 和用于内存字符串解析的 json。json.load/json.dump 等文件对象接口仍然禁止。',
    '记忆更新只记录项目事实、用户确认和本次修改摘要，不记录 API key、token、密码或完整源码。',
  ].join('\n');
}

export function buildModelEditMessages({
  prompt = '',
  projectId = '',
  source = '',
  sourceHash = '',
  sourceFilename = '',
  projectMemory = {},
  modelIndex = {},
  editHistory = [],
  recentConversation = [],
} = {}) {
  const boundedSource = String(source || '').slice(0, MAX_MODEL_EDIT_SOURCE_BYTES);
  return [
    { role: 'system', content: buildModelEditSystemPrompt() },
    {
      role: 'user',
      content: JSON.stringify({
        user_request: redactSensitiveText(prompt),
        project_id: projectId,
        source_filename: sourceFilename,
        source_hash: sourceHash || hashCadQuerySource(boundedSource),
        current_cadquery_source: boundedSource,
        project_memory: normalizeProjectMemory(projectMemory, { projectId }),
        model_index: jsonSafe(modelIndex),
        recent_edit_history: Array.isArray(editHistory) ? editHistory.slice(-20).map(jsonSafe) : [],
        recent_visible_conversation: Array.isArray(recentConversation)
          ? recentConversation.slice(-20).map(jsonSafe)
          : [],
      }, null, 2),
    },
  ];
}

export async function requestModelEditPlan({
  prompt = '',
  projectId = '',
  source = '',
  sourceHash = '',
  sourceFilename = '',
  projectMemory = {},
  modelIndex = {},
  editHistory = [],
  recentConversation = [],
  config = getIntentModelConfig(),
} = {}) {
  const raw = await requestChatCompletionJson({
    config,
    requestKind: 'model_edit',
    temperature: 0,
    responseFormat: { type: 'json_object' },
    messages: buildModelEditMessages({
      prompt,
      projectId,
      source,
      sourceHash,
      sourceFilename,
      projectMemory,
      modelIndex,
      editHistory,
      recentConversation,
    }),
  });
  return normalizeModelEditPlan(raw, { currentSource: source, sourceHash, projectId, sourceFilename });
}

function firstString(...values) {
  for (const value of values) if (typeof value === 'string' && value.trim()) return value.trim();
  return null;
}

function firstNonEmptyDefinedString(...values) {
  for (const value of values) if (typeof value === 'string' && value.trim()) return value;
  return null;
}

function firstDefinedString(...values) {
  for (const value of values) if (typeof value === 'string') return value;
  return null;
}

function buildStablePlanId(value = {}) {
  const digest = hashCadQuerySource(JSON.stringify(jsonSafe(value))).slice(0, 20);
  return `edit-${digest}`;
}

function normalizeStableId(value) {
  return typeof value === 'string'
    ? value.trim().toLowerCase().replace(/[^a-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 96)
    : '';
}

function normalizeRisk(value) {
  const text = typeof value === 'string' ? value.trim().toLowerCase() : '';
  return ['low', 'medium', 'high'].includes(text) ? text : '';
}

function normalizePlanStatus(value) {
  const text = typeof value === 'string' ? value.trim().toLowerCase() : '';
  if (['needs_input', 'blocked', 'needs_confirmation', 'confirmation_required', 'ok', 'noop'].includes(text)) {
    return text === 'confirmation_required' ? 'needs_confirmation' : text;
  }
  return '';
}

function parsePositiveInteger(value) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : 0;
}

function countOccurrences(text, needle) {
  if (!needle) return 0;
  let count = 0;
  let index = 0;
  while ((index = text.indexOf(needle, index)) >= 0) {
    count += 1;
    index += needle.length;
  }
  return count;
}

function findOccurrenceIndex(text, needle, occurrence) {
  let index = -1;
  let offset = 0;
  for (let count = 0; count < occurrence; count += 1) {
    index = text.indexOf(needle, offset);
    if (index < 0) return -1;
    offset = index + needle.length;
  }
  return index;
}

function operationText(operation = {}) {
  return [operation.type, operation.id, operation.target_id, operation.summary, JSON.stringify(operation.parameters || {})].filter(Boolean).join(' ');
}

function normalizeTextList(value) {
  if (!Array.isArray(value)) return [];
  return [...new Set(value
    .filter((item) => typeof item === 'string' && item.trim())
    .map((item) => redactSensitiveText(item.trim()))
    .slice(-100))];
}

function normalizeMemoryUpdate(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return {
    summary: '', facts: [], remove_facts: [], decisions: [], constraints: [], objects: [],
  };
  return {
    summary: redactSensitiveText(firstString(value.summary, value.memory_summary) || ''),
    facts: normalizeTextList(value.facts),
    remove_facts: normalizeTextList(value.remove_facts || value.removeFacts),
    decisions: normalizeTextList(value.decisions),
    constraints: normalizeTextList(value.constraints),
    objects: Array.isArray(value.objects) ? value.objects.filter((item) => item && typeof item === 'object').slice(-100).map(jsonSafe) : [],
  };
}

function mergeTextItems(a = [], b = []) {
  return [...new Set([...normalizeTextList(a), ...normalizeTextList(b)])].slice(-100);
}

function mergeObjects(a = [], b = []) {
  const result = [...(Array.isArray(a) ? a : []), ...(Array.isArray(b) ? b : [])]
    .filter((item) => item && typeof item === 'object')
    .map(jsonSafe);
  const byId = new Map();
  result.forEach((item, index) => byId.set(item.id || item.object_id || `object-${index}`, item));
  return [...byId.values()].slice(-100);
}

function appendUniqueById(items = [], item = {}, key = 'id', limit = 100) {
  const result = [...(Array.isArray(items) ? items : []), item];
  const map = new Map();
  for (const entry of result) map.set(entry?.[key] || `${key}-${map.size}`, entry);
  return [...map.values()].slice(-limit);
}

function jsonSafe(value) {
  try {
    return JSON.parse(JSON.stringify(value));
  } catch {
    return {};
  }
}

function redactSensitiveText(value = '') {
  return String(value || '')
    .replace(/\b(?:sk|rk)-[A-Za-z0-9_-]{12,}\b/g, '[已隐藏凭据]')
    .replace(/\b(api[_-]?key|token|password|secret)\s*[:=]\s*[^\s,;]+/gi, '$1=[已隐藏]');
}

function failure(code, message, details = {}) {
  return { status: 'fail', code, message, ...details };
}

function maskPythonStringsAndComments(code = '') {
  let result = '';
  let index = 0;
  let quote = '';
  let triple = false;
  let comment = false;
  while (index < code.length) {
    const current = code[index];
    const next = code.slice(index, index + 3);
    if (comment) {
      if (current === '\n') {
        comment = false;
        result += '\n';
      } else result += ' ';
      index += 1;
      continue;
    }
    if (quote) {
      if (triple && next === quote.repeat(3)) {
        result += '   ';
        index += 3;
        quote = '';
        triple = false;
      } else if (!triple && current === quote && code[index - 1] !== '\\') {
        result += ' ';
        index += 1;
        quote = '';
      } else {
        result += current === '\n' ? '\n' : ' ';
        index += 1;
      }
      continue;
    }
    if (current === '#') {
      comment = true;
      result += ' ';
      index += 1;
      continue;
    }
    if (next === '"""' || next === "'''") {
      quote = current;
      triple = true;
      result += '   ';
      index += 3;
      continue;
    }
    if (current === '"' || current === "'") {
      quote = current;
      triple = false;
      result += ' ';
      index += 1;
      continue;
    }
    result += current;
    index += 1;
  }
  return result;
}

function collectPythonImports(maskedCode = '') {
  const imports = [];
  for (const lineMatch of maskedCode.matchAll(/[^\r\n]*(?:\r\n|\n|\r|$)/g)) {
    if (!lineMatch[0]) continue;
    const line = lineMatch[0].replace(/(?:\r\n|\n|\r)$/, '');
    const lineStart = Number(lineMatch.index);
    const statementStart = lineStart + (line.match(/^\s*/)?.[0].length || 0);
    const statementEnd = lineStart + line.length;
    const importMatch = line.match(/^\s*import\s+([^#]+)$/);
    if (importMatch) {
      for (const part of importMatch[1].split(',')) {
        const module = part.trim().split(/\s+as\s+/i)[0].trim();
        if (module) imports.push({
          module: module.split('.')[0],
          statement: line.trim(),
          start: statementStart,
          end: statementEnd,
        });
      }
    }
    const fromMatch = line.match(/^\s*from\s+([\w.]+)\s+import\s+/);
    if (fromMatch) imports.push({
      module: fromMatch[1].split('.')[0],
      statement: line.trim(),
      start: statementStart,
      end: statementEnd,
    });
  }
  return imports;
}

function buildAstSafetyScript() {
  return [
    'import ast, json, sys',
    'source = sys.stdin.read()',
    'errors = []',
    'allowed = {"cadquery", "math", "json"}',
    'forbidden = {"open", "exec", "eval", "compile", "__import__", "input", "globals", "locals", "vars", "dir", "getattr", "setattr", "delattr", "subprocess", "os", "sys", "pathlib", "shutil", "socket", "requests", "urllib", "http", "importlib", "builtins", "ctypes", "pickle", "marshal", "tempfile", "export", "exportshape", "exportdxf", "exportstep", "save", "load", "dump", "importstep", "importdxf", "importbrep", "importbin", "importshape", "read_text", "write_text", "read_bytes", "write_bytes", "unlink", "remove", "mkdir", "rmdir"}',
    'forbidden_attrs = forbidden | {"exporters", "importers"}',
    'try: tree = ast.parse(source)',
    'except Exception as exc: print(json.dumps({"status":"fail", "errors":[{"code":"python_syntax", "message":str(exc)}]})); sys.exit(0)',
    'parents = {child: parent for parent in ast.walk(tree) for child in ast.iter_child_nodes(parent)}',
    'lines = source.splitlines(keepends=True)',
    'line_starts = []',
    'total = 0',
    'for line in lines:',
    '    line_starts.append(total)',
    '    total += len(line.encode("utf-16-le")) // 2',
    'def utf16_offset(lineno, byte_col):',
    '    if not lineno or lineno < 1 or lineno > len(lines): return None',
    '    prefix = lines[lineno - 1].encode("utf-8")[:byte_col].decode("utf-8", "ignore")',
    '    return line_starts[lineno - 1] + len(prefix.encode("utf-16-le")) // 2',
    'def security_context(node):',
    '    current = node',
    '    parent = parents.get(current)',
    '    while parent is not None and not isinstance(parent, (ast.stmt, ast.Module)):',
    '        current = parent',
    '        parent = parents.get(current)',
    '    return current',
    'def add_error(code, message, node):',
    '    context = security_context(node)',
    '    errors.append({"code": code, "message": message, "start": utf16_offset(getattr(context, "lineno", None), getattr(context, "col_offset", 0)), "end": utf16_offset(getattr(context, "end_lineno", None), getattr(context, "end_col_offset", 0)), "node_type": type(context).__name__, "semantic": ast.dump(context, annotate_fields=True, include_attributes=False)})',
    'def call_target_has_subscript(node):',
    '    return any(isinstance(part, ast.Subscript) for part in ast.walk(node))',
    'for node in ast.walk(tree):',
    '    if isinstance(node, ast.Import):',
    '        for alias in node.names:',
    '            parts = alias.name.lower().split(".")',
    '            if parts[0] not in allowed or any(part in {"exporters", "importers"} for part in parts): add_error("forbidden_import", alias.name, node)',
    '    elif isinstance(node, ast.ImportFrom):',
    '        root = (node.module or "").split(".")[0]',
    '        names = {alias.name.lower() for alias in node.names}',
    '        if root not in allowed or root == "json" or names & {"exporters", "importers"}: add_error("forbidden_import", node.module or "", node)',
    '    elif isinstance(node, ast.Call):',
    '        target = node.func.id if isinstance(node.func, ast.Name) else node.func.attr if isinstance(node.func, ast.Attribute) else ""',
    '        if target.lower() in forbidden: add_error("forbidden_call", target, node)',
    '        elif not isinstance(node.func, (ast.Name, ast.Attribute)) or call_target_has_subscript(node.func): add_error("dynamic_call_target", type(node.func).__name__, node)',
    '    elif isinstance(node, ast.Attribute) and node.attr.startswith("__"): add_error("dunder_access", node.attr, node)',
    '    elif isinstance(node, ast.Attribute) and node.attr.lower() in forbidden_attrs: add_error("forbidden_attribute", node.attr, node)',
    '    elif isinstance(node, (ast.Global, ast.Nonlocal)): add_error("global_state_mutation", type(node).__name__, node)',
    'print(json.dumps({"status":"fail" if errors else "pass", "errors":errors}, ensure_ascii=False))',
  ].join('\n');
}

function runPythonAstCheck(python, script, source, timeoutMs) {
  return new Promise((resolve) => {
    let stdout = '';
    let stderr = '';
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    let child;
    try {
      child = spawn(python, ['-c', script], {
        cwd: process.cwd(),
        windowsHide: true,
        env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
        stdio: ['pipe', 'pipe', 'pipe'],
      });
    } catch (error) {
      finish({ status: 'pending', code: 'python_unavailable', message: error instanceof Error ? error.message : String(error) });
      return;
    }
    const timer = setTimeout(() => {
      child.kill();
      finish({ status: 'pending', code: 'python_ast_timeout', message: 'Python AST 预检超时。' });
    }, timeoutMs);
    child.stdout.on('data', (chunk) => { stdout += chunk.toString('utf8'); });
    child.stderr.on('data', (chunk) => { stderr += chunk.toString('utf8'); });
    child.on('error', (error) => {
      clearTimeout(timer);
      finish({ status: 'pending', code: 'python_unavailable', message: error instanceof Error ? error.message : String(error) });
    });
    child.on('close', () => {
      clearTimeout(timer);
      try {
        const parsed = JSON.parse(stdout.trim());
        finish({ ...parsed, stderr });
      } catch {
        finish({ status: 'pending', code: 'python_ast_invalid_response', message: stderr || 'Python AST 预检没有返回结果。' });
      }
    });
    child.stdin.end(source, 'utf8');
  });
}
