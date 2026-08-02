import crypto from 'node:crypto';
import { AsyncLocalStorage } from 'node:async_hooks';
import { mkdir, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';

export const PROJECT_MANIFEST_SCHEMA_VERSION = 'zwcad_project_v1';
export const PROJECT_MEMORY_SCHEMA_VERSION = 'project_memory_v1';
export const MODEL_INDEX_SCHEMA_VERSION = 'model_index_v1';
export const PROJECT_REVISION_SCHEMA_VERSION = 'project_revision_v1';
export const PROJECT_STORAGE_POLICY_VERSION = 'project_storage_policy_v2';
export const PROJECT_SESSION_SCHEMA_VERSION = 'project_session_state_v1';
export const PROJECT_CONVERSATION_SCHEMA_VERSION = 'project_conversation_v1';

export const PROJECT_STORAGE_LIMITS = Object.freeze({
  memoryBytes: 1024 * 1024,
  memoryArrayItems: 100,
  memorySummaryBytes: 4 * 1024,
  memoryTextBytes: 2 * 1024,
  memoryObjectBytes: 16 * 1024,
  conversationTurns: 1000,
  conversationBytes: 4 * 1024 * 1024,
  conversationContextTurns: 20,
  revisions: 20,
  stagedMaxAgeMs: 24 * 60 * 60 * 1000,
});

const PROJECT_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/;
const SOURCE_FILENAME_PATTERN = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}\.py$/i;
const LIFECYCLE_STATUSES = new Set(['draft', 'ready', 'failed']);
const projectMutationQueues = new Map();
const projectMutationContext = new AsyncLocalStorage();

export async function withProjectMutationLock({ rootDir, projectId } = {}, task) {
  if (typeof task !== 'function') throw new TypeError('project mutation task is required.');
  const key = `${path.resolve(rootDir).toLowerCase()}\n${safeProjectId(projectId)}`;
  const activeKeys = projectMutationContext.getStore();
  if (activeKeys?.has(key)) return task();

  const previous = projectMutationQueues.get(key) || Promise.resolve();
  let releaseGate;
  const gate = new Promise((resolve) => { releaseGate = resolve; });
  const tail = previous.catch(() => undefined).then(() => gate);
  projectMutationQueues.set(key, tail);
  await previous.catch(() => undefined);
  const nextKeys = new Set(activeKeys || []);
  nextKeys.add(key);
  try {
    return await projectMutationContext.run(nextKeys, task);
  } finally {
    releaseGate();
    if (projectMutationQueues.get(key) === tail) projectMutationQueues.delete(key);
  }
}

export async function ensureProjectLifecycle(options = {}) {
  return withProjectMutationLock(options, () => ensureProjectLifecycleUnlocked(options));
}

async function ensureProjectLifecycleUnlocked({
  rootDir,
  projectId,
  title = '',
  sourceFilename = 'model-source.cq.py',
  lifecycleStatus = 'draft',
  now = new Date(),
} = {}) {
  const paths = projectPaths({ rootDir, projectId, sourceFilename });
  await Promise.all([
    mkdir(paths.projectDir, { recursive: true }),
    mkdir(paths.assetsDir, { recursive: true }),
    mkdir(paths.revisionsDir, { recursive: true }),
    mkdir(paths.stagedDir, { recursive: true }),
  ]);
  const existing = await readJsonIfPresent(paths.manifestPath);
  const timestamp = normalizeDate(now).toISOString();
  const activityTimestamp = monotonicProjectTimestamp(existing, timestamp);
  const filename = safeSourceFilename(existing?.model_source?.filename || paths.sourceFilename);
  const manifest = {
    ...(existing || {}),
    schema_version: PROJECT_MANIFEST_SCHEMA_VERSION,
    storage_policy_version: PROJECT_STORAGE_POLICY_VERSION,
    project_id: paths.projectId,
    title: textValue(title || existing?.title),
    created_at: normalizeTimestamp(existing?.created_at, timestamp),
    updated_at: activityTimestamp,
    last_activity_at: activityTimestamp,
    lifecycle_status: normalizeLifecycleStatus(
      existing?.lifecycle_status === 'ready' && lifecycleStatus === 'draft'
        ? 'ready'
        : lifecycleStatus || existing?.lifecycle_status,
    ),
    project_revision: positiveInteger(existing?.project_revision, 1),
    project_source_hash: normalizeHash(existing?.project_source_hash),
    model_source: {
      filename,
      sha256: normalizeHash(existing?.model_source?.sha256 || existing?.project_source_hash),
    },
    template: isObject(existing?.template)
      ? existing.template
      : { id: '', source: 'generated_model' },
  };
  await writeJsonAtomic(paths.manifestPath, manifest);
  if (await readTextIfPresent(paths.conversationPath) === null) {
    await writeFileAtomic(paths.conversationPath, '');
  }
  if (await readJsonIfPresent(paths.sessionStatePath) === null) {
    await writeJsonAtomic(paths.sessionStatePath, {
      schema_version: PROJECT_SESSION_SCHEMA_VERSION,
      project_id: paths.projectId,
      updated_at: timestamp,
      workflow_stage: lifecycleStatus === 'ready' ? 'review' : 'requirement_analysis',
      parameter_overrides: {},
      last_blocking_state: null,
      active_drafts: {},
      template_confirmation: null,
      template_confirmation_required: false,
    });
  }
  await cleanupOrphanedStagedFiles({ rootDir, projectId, now });
  return {
    status: manifest.lifecycle_status,
    project_id: paths.projectId,
    project_dir: paths.projectDir,
    project_manifest: manifest,
    paths,
  };
}

export async function ensureProjectWorkspace(options = {}) {
  return withProjectMutationLock(options, () => ensureProjectWorkspaceUnlocked(options));
}

async function ensureProjectWorkspaceUnlocked({
  rootDir,
  projectId,
  source = '',
  sourceFilename = 'model-source.cq.py',
  artifact = {},
  now = new Date(),
} = {}) {
  const paths = projectPaths({ rootDir, projectId, sourceFilename });
  const lifecycle = await ensureProjectLifecycle({
    rootDir,
    projectId,
    sourceFilename,
    title: artifact?.title || artifact?.design_state?.intent?.product_name,
    lifecycleStatus: 'ready',
    now,
  });
  const existingManifest = lifecycle.project_manifest;
  const existingManifestFilename = safeSourceFilename(existingManifest?.model_source?.filename || paths.sourceFilename);
  const existingManifestSource = await readTextIfPresent(path.join(paths.projectDir, existingManifestFilename));
  const manifestSourceFilename = existingManifestSource === null
    && !normalizeHash(existingManifest?.model_source?.sha256 || existingManifest?.project_source_hash)
    ? paths.sourceFilename
    : existingManifestFilename;
  const sourcePath = path.join(paths.projectDir, manifestSourceFilename);
  const existingSource = manifestSourceFilename === existingManifestFilename
    ? existingManifestSource
    : await readTextIfPresent(sourcePath);
  const initialized = existingSource === null;
  const projectSource = initialized ? String(source || '') : existingSource;
  if (initialized) await writeFileAtomic(sourcePath, projectSource);

  const sourceHash = hashProjectSource(projectSource);
  const timestamp = normalizeDate(now).toISOString();
  const revision = positiveInteger(existingManifest?.project_revision, 1);
  const createdAt = normalizeTimestamp(existingManifest?.created_at, timestamp);
  const manifest = {
    ...existingManifest,
    schema_version: PROJECT_MANIFEST_SCHEMA_VERSION,
    storage_policy_version: PROJECT_STORAGE_POLICY_VERSION,
    project_id: paths.projectId,
    title: textValue(existingManifest?.title || artifact?.title || artifact?.design_state?.intent?.product_name),
    created_at: createdAt,
    updated_at: timestamp,
    last_activity_at: timestamp,
    lifecycle_status: 'ready',
    project_revision: revision,
    project_source_hash: sourceHash,
    model_source: {
      filename: manifestSourceFilename,
      sha256: sourceHash,
    },
    template: normalizeTemplateMetadata(existingManifest?.template, artifact),
  };
  await writeJsonAtomic(paths.manifestPath, manifest);

  const revisionPaths = revisionFilePaths(paths.revisionsDir, revision);
  if (await readTextIfPresent(revisionPaths.sourcePath) === null) {
    await writeFileAtomic(revisionPaths.sourcePath, projectSource);
  }
  if (await readJsonIfPresent(revisionPaths.metadataPath) === null) {
    await writeJsonAtomic(revisionPaths.metadataPath, buildRevisionMetadata({
      projectId: paths.projectId,
      revision,
      sourceFilename: manifestSourceFilename,
      sourceHash,
      createdAt,
      summary: initialized ? '初始化项目源码副本。' : '登记已有项目源码。',
      changeType: initialized ? 'project_initialized' : 'project_migrated',
    }));
  }
  await pruneProjectRevisions({ rootDir, projectId });

  const modelIndex = await ensureModelIndex({
    path: paths.modelIndexPath,
    projectId: paths.projectId,
    sourceFilename: manifestSourceFilename,
    sourceHash,
    artifact,
    timestamp: createdAt,
  });
  const projectMemory = await ensureProjectMemory({
    path: paths.projectMemoryPath,
    projectId: paths.projectId,
    artifact,
    timestamp: createdAt,
    sourceHash,
  });
  await writeProjectSessionState({
    rootDir,
    projectId,
    state: {
      workflow_stage: 'review',
      parameter_overrides: artifact?.design_state?.parameter_overrides || {},
      last_blocking_state: null,
      active_drafts: {},
      template_confirmation: null,
      template_confirmation_required: false,
    },
    now,
  });

  return {
    status: 'ready',
    initialized,
    project_id: paths.projectId,
    project_dir: paths.projectDir,
    source_path: sourcePath,
    source_filename: manifestSourceFilename,
    source: projectSource,
    source_hash: sourceHash,
    project_revision: revision,
    revision_id: revisionId(revision),
    project_manifest: manifest,
    model_index: modelIndex,
    project_memory: projectMemory,
  };
}

export async function readProjectWorkspace({ rootDir, projectId } = {}) {
  const paths = projectPaths({ rootDir, projectId });
  const manifest = await readJsonIfPresent(paths.manifestPath);
  if (!manifest) return { status: 'missing', project_id: paths.projectId };
  const sourceFilename = safeSourceFilename(manifest.model_source?.filename || paths.sourceFilename);
  const sourcePath = path.join(paths.projectDir, sourceFilename);
  const source = await readTextIfPresent(sourcePath);
  if (source === null) {
    return {
      status: normalizeLifecycleStatus(manifest.lifecycle_status || 'draft'),
      project_id: paths.projectId,
      project_dir: paths.projectDir,
      source_path: sourcePath,
      source_filename: sourceFilename,
      source: '',
      source_hash: '',
      project_revision: positiveInteger(manifest.project_revision, 1),
      revision_id: revisionId(positiveInteger(manifest.project_revision, 1)),
      project_manifest: normalizeProjectManifest(manifest, paths.projectId),
      model_index: await readJsonIfPresent(paths.modelIndexPath),
      project_memory: await readJsonIfPresent(paths.projectMemoryPath),
      session_state: await readJsonIfPresent(paths.sessionStatePath),
    };
  }
  const sourceHash = hashProjectSource(source);
  return {
    status: 'ready',
    project_id: paths.projectId,
    project_dir: paths.projectDir,
    source_path: sourcePath,
    source_filename: sourceFilename,
    source,
    source_hash: sourceHash,
    project_revision: positiveInteger(manifest.project_revision, 1),
    revision_id: revisionId(positiveInteger(manifest.project_revision, 1)),
    project_manifest: {
      ...normalizeProjectManifest(manifest, paths.projectId),
      project_source_hash: sourceHash,
      model_source: { filename: sourceFilename, sha256: sourceHash },
    },
    model_index: await readJsonIfPresent(paths.modelIndexPath),
    project_memory: normalizeProjectMemory(await readJsonIfPresent(paths.projectMemoryPath), {
      projectId: paths.projectId,
      sourceHash,
    }),
    session_state: await readJsonIfPresent(paths.sessionStatePath),
  };
}

export async function commitProjectSourceRevision(options = {}) {
  return withProjectMutationLock(options, () => commitProjectSourceRevisionUnlocked(options));
}

async function commitProjectSourceRevisionUnlocked({
  rootDir,
  projectId,
  source,
  expectedSourceHash = '',
  summary = '更新项目模型源码。',
  changeType = 'model_edit',
  operations = [],
  riskLevel = 'low',
  memorySummary = '',
  projectMemoryUpdate = null,
  now = new Date(),
} = {}) {
  const current = await readProjectWorkspace({ rootDir, projectId });
  const expected = normalizeHash(expectedSourceHash);
  if (expected && expected !== current.source_hash) {
    const error = new Error('项目源码已被其他修改更新，请基于最新版本重新生成补丁。');
    error.code = 'project_source_hash_conflict';
    error.expected_source_hash = expected;
    error.actual_source_hash = current.source_hash;
    throw error;
  }

  const nextSource = String(source ?? '');
  const nextHash = hashProjectSource(nextSource);
  if (nextHash === current.source_hash) {
    return { ...current, changed: false };
  }

  const paths = projectPaths({
    rootDir,
    projectId,
    sourceFilename: current.source_filename,
  });
  const revision = current.project_revision + 1;
  const timestamp = normalizeDate(now).toISOString();
  const revisionPaths = revisionFilePaths(paths.revisionsDir, revision);
  await mkdir(paths.revisionsDir, { recursive: true });
  await writeFileAtomic(revisionPaths.sourcePath, nextSource);
  await writeJsonAtomic(revisionPaths.metadataPath, buildRevisionMetadata({
    projectId: paths.projectId,
    revision,
    sourceFilename: current.source_filename,
    sourceHash: nextHash,
    previousSourceHash: current.source_hash,
    createdAt: timestamp,
    summary,
    changeType,
    operations,
    riskLevel,
  }));
  await writeFileAtomic(current.source_path, nextSource);

  const manifest = {
    ...current.project_manifest,
    schema_version: PROJECT_MANIFEST_SCHEMA_VERSION,
    storage_policy_version: PROJECT_STORAGE_POLICY_VERSION,
    updated_at: timestamp,
    last_activity_at: timestamp,
    lifecycle_status: 'ready',
    project_revision: revision,
    revision_id: revisionId(revision),
    project_source_hash: nextHash,
    model_source: {
      filename: current.source_filename,
      sha256: nextHash,
    },
  };
  await writeJsonAtomic(paths.manifestPath, manifest);

  const modelIndex = {
    ...(current.model_index || {}),
    schema_version: MODEL_INDEX_SCHEMA_VERSION,
    project_id: paths.projectId,
    updated_at: timestamp,
    source_file: current.source_filename,
    source_hash: nextHash,
  };
  await writeJsonAtomic(paths.modelIndexPath, modelIndex);

  const historyEntry = {
    revision,
    created_at: timestamp,
    source_hash: nextHash,
    previous_source_hash: current.source_hash,
    change_type: textValue(changeType) || 'model_edit',
    risk_level: normalizeRiskLevel(riskLevel),
    summary: textValue(summary) || '更新项目模型源码。',
    operations: jsonArray(operations),
  };
  const suppliedMemory = isObject(projectMemoryUpdate) ? JSON.parse(JSON.stringify(projectMemoryUpdate)) : {};
  const projectMemory = normalizeProjectMemory({
    ...(current.project_memory || {}),
    ...suppliedMemory,
    schema_version: PROJECT_MEMORY_SCHEMA_VERSION,
    project_id: paths.projectId,
    updated_at: timestamp,
    summary: textValue(memorySummary || suppliedMemory.summary || current.project_memory?.summary),
    project_source_hash: nextHash,
    last_revision_id: textValue(suppliedMemory.last_revision_id) || revisionId(revision),
    model_edit_history: [
      ...jsonArray(current.project_memory?.model_edit_history),
      historyEntry,
    ],
  }, { projectId: paths.projectId, sourceHash: nextHash, timestamp });
  await writeJsonCompactAtomic(paths.projectMemoryPath, projectMemory);
  await pruneProjectRevisions({ rootDir, projectId });

  return {
    status: 'ready',
    changed: true,
    project_id: paths.projectId,
    project_dir: paths.projectDir,
    source_path: current.source_path,
    source_filename: current.source_filename,
    source: nextSource,
    source_hash: nextHash,
    project_revision: revision,
    revision_id: revisionId(revision),
    project_manifest: manifest,
    model_index: modelIndex,
    project_memory: projectMemory,
  };
}

export async function restorePreviousProjectRevision(options = {}) {
  return withProjectMutationLock(options, () => restorePreviousProjectRevisionUnlocked(options));
}

async function restorePreviousProjectRevisionUnlocked({
  rootDir,
  projectId,
  expectedSourceHash = '',
  transformSource = null,
  now = new Date(),
} = {}) {
  const current = await readProjectWorkspace({ rootDir, projectId });
  const expected = normalizeHash(expectedSourceHash);
  if (expected && expected !== current.source_hash) {
    const error = new Error('项目源码已被其他修改更新，请刷新后再撤销。');
    error.code = 'project_source_hash_conflict';
    error.expected_source_hash = expected;
    error.actual_source_hash = current.source_hash;
    throw error;
  }
  if (current.project_revision <= 1) {
    const error = new Error('当前项目还没有可恢复的上一版源码。');
    error.code = 'project_revision_not_available';
    throw error;
  }

  const paths = projectPaths({
    rootDir,
    projectId,
    sourceFilename: current.source_filename,
  });
  const targetRevision = current.project_revision - 1;
  const targetPaths = revisionFilePaths(paths.revisionsDir, targetRevision);
  const targetSource = await readTextIfPresent(targetPaths.sourcePath);
  if (targetSource === null) {
    const error = new Error('上一版项目源码快照缺失，无法撤销。');
    error.code = 'project_revision_source_missing';
    error.revision_id = revisionId(targetRevision);
    throw error;
  }

  // Callers that keep derived metadata alongside the source may need to
  // invalidate stale annotations before the restored revision is committed.
  // The hook is deliberately in-memory and is never persisted as part of the
  // project contract.
  const nextSource = typeof transformSource === 'function'
    ? await transformSource(targetSource, {
        current,
        target_revision: targetRevision,
      })
    : targetSource;

  return commitProjectSourceRevision({
    rootDir,
    projectId,
    source: String(nextSource ?? ''),
    expectedSourceHash: current.source_hash,
    summary: `恢复到项目修订 ${revisionId(targetRevision)}。`,
    changeType: 'undo_model_edit',
    operations: [{ action: 'restore_revision', revision_id: revisionId(targetRevision) }],
    riskLevel: 'low',
    now,
  });
}

export async function touchProjectActivity(options = {}) {
  return withProjectMutationLock(options, () => touchProjectActivityUnlocked(options));
}

async function touchProjectActivityUnlocked({
  rootDir,
  projectId,
  lifecycleStatus = '',
  title = '',
  now = new Date(),
} = {}) {
  const paths = projectPaths({ rootDir, projectId });
  const existing = await readJsonIfPresent(paths.manifestPath);
  if (!existing) {
    return ensureProjectLifecycle({
      rootDir,
      projectId,
      title,
      lifecycleStatus: lifecycleStatus || 'draft',
      now,
    });
  }
  const timestamp = normalizeDate(now).toISOString();
  const activityTimestamp = monotonicProjectTimestamp(existing, timestamp);
  const manifest = {
    ...normalizeProjectManifest(existing, paths.projectId),
    storage_policy_version: PROJECT_STORAGE_POLICY_VERSION,
    title: textValue(title || existing.title),
    updated_at: activityTimestamp,
    last_activity_at: activityTimestamp,
    lifecycle_status: lifecycleStatus
      ? normalizeLifecycleStatus(lifecycleStatus)
      : normalizeLifecycleStatus(existing.lifecycle_status),
  };
  await writeJsonAtomic(paths.manifestPath, manifest);
  return {
    status: manifest.lifecycle_status,
    project_id: paths.projectId,
    project_dir: paths.projectDir,
    project_manifest: manifest,
    paths,
  };
}

export async function appendProjectConversationTurn(options = {}) {
  return withProjectMutationLock(options, () => appendProjectConversationTurnUnlocked(options));
}

async function appendProjectConversationTurnUnlocked({
  rootDir,
  projectId,
  userMessage = '',
  assistantResponse = {},
  routeAction = '',
  now = new Date(),
} = {}) {
  const lifecycle = await touchProjectActivity({ rootDir, projectId, now });
  const paths = lifecycle.paths;
  const timestamp = normalizeDate(now).toISOString();
  const turn = {
    schema_version: PROJECT_CONVERSATION_SCHEMA_VERSION,
    turn_id: crypto.randomUUID(),
    created_at: timestamp,
    route_action: truncateUtf8(redactCredentials(routeAction), 256),
    user_message: truncateUtf8(redactCredentials(userMessage), 64 * 1024),
    assistant_response: normalizeVisibleAssistantResponse(assistantResponse),
  };
  const existingText = await readTextIfPresent(paths.conversationPath) || '';
  const turns = existingText.split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        return JSON.parse(line);
      } catch {
        return null;
      }
    })
    .filter(isObject);
  turns.push(turn);
  while (turns.length > PROJECT_STORAGE_LIMITS.conversationTurns) turns.shift();
  let output = conversationJsonLines(turns);
  while (turns.length > 1 && Buffer.byteLength(output, 'utf8') > PROJECT_STORAGE_LIMITS.conversationBytes) {
    turns.shift();
    output = conversationJsonLines(turns);
  }
  if (Buffer.byteLength(output, 'utf8') > PROJECT_STORAGE_LIMITS.conversationBytes) {
    turn.user_message = truncateUtf8(turn.user_message, 64 * 1024);
    turn.assistant_response = {
      status: truncateUtf8(turn.assistant_response?.status, 256),
      title: truncateUtf8(turn.assistant_response?.title, 2 * 1024),
      message: truncateUtf8(turn.assistant_response?.message, 256 * 1024),
      questions: [],
      blocking_reason: truncateUtf8(turn.assistant_response?.blocking_reason, 512),
      summary: truncateUtf8(turn.assistant_response?.summary, 64 * 1024),
      truncated: true,
    };
    output = conversationJsonLines([turn]);
  }
  if (Buffer.byteLength(output, 'utf8') > PROJECT_STORAGE_LIMITS.conversationBytes) {
    const error = new Error('单轮可见对话超过项目存储上限。');
    error.code = 'project_conversation_turn_too_large';
    throw error;
  }
  await writeFileAtomic(paths.conversationPath, output);
  return turn;
}

export async function readProjectConversation({
  rootDir,
  projectId,
  limit = PROJECT_STORAGE_LIMITS.conversationContextTurns,
} = {}) {
  const paths = projectPaths({ rootDir, projectId });
  const text = await readTextIfPresent(paths.conversationPath);
  if (!text) return [];
  const turns = text.split(/\r?\n/).map((line) => {
    try {
      return JSON.parse(line);
    } catch {
      return null;
    }
  }).filter(isObject);
  return turns.slice(-Math.max(0, Math.min(100, positiveInteger(limit, PROJECT_STORAGE_LIMITS.conversationContextTurns))));
}

export async function writeProjectSessionState(options = {}) {
  return withProjectMutationLock(options, () => writeProjectSessionStateUnlocked(options));
}

async function writeProjectSessionStateUnlocked({
  rootDir,
  projectId,
  state = {},
  now = new Date(),
} = {}) {
  const paths = projectPaths({ rootDir, projectId });
  await mkdir(paths.projectDir, { recursive: true });
  const existing = await readJsonIfPresent(paths.sessionStatePath) || {};
  const timestamp = normalizeDate(now).toISOString();
  const activeDrafts = isObject(state.active_drafts)
    ? state.active_drafts
    : isObject(state.activeDrafts)
      ? state.activeDrafts
      : existing.active_drafts || {};
  const hasTemplateConfirmation = Object.prototype.hasOwnProperty.call(state, 'template_confirmation')
    || Object.prototype.hasOwnProperty.call(state, 'templateConfirmation');
  const templateConfirmation = hasTemplateConfirmation
    ? (state.template_confirmation ?? state.templateConfirmation)
    : (existing.template_confirmation || null);
  const hasTemplateConfirmationRequired = Object.prototype.hasOwnProperty.call(state, 'template_confirmation_required')
    || Object.prototype.hasOwnProperty.call(state, 'templateConfirmationRequired');
  const templateConfirmationRequired = hasTemplateConfirmationRequired
    ? Boolean(state.template_confirmation_required ?? state.templateConfirmationRequired)
    : existing.template_confirmation_required === true;
  const result = sanitizeSessionState({
    ...existing,
    ...state,
    schema_version: PROJECT_SESSION_SCHEMA_VERSION,
    project_id: paths.projectId,
    updated_at: timestamp,
    workflow_stage: textValue(state.workflow_stage || state.workflowStage || existing.workflow_stage),
    parameter_overrides: isObject(state.parameter_overrides || state.parameterOverrides)
      ? state.parameter_overrides || state.parameterOverrides
      : existing.parameter_overrides || {},
    last_blocking_state: state.last_blocking_state === null || state.lastBlockingState === null
      ? null
      : state.last_blocking_state || state.lastBlockingState || existing.last_blocking_state || null,
    active_drafts: activeDrafts,
    template_confirmation: templateConfirmation,
    template_confirmation_required: templateConfirmationRequired,
  });
  await writeJsonAtomic(paths.sessionStatePath, result);
  return result;
}

export async function cleanupOrphanedStagedFiles(options = {}) {
  return withProjectMutationLock(options, () => cleanupOrphanedStagedFilesUnlocked(options));
}

async function cleanupOrphanedStagedFilesUnlocked({ rootDir, projectId, now = new Date() } = {}) {
  const paths = projectPaths({ rootDir, projectId });
  await mkdir(paths.stagedDir, { recursive: true });
  const cutoff = normalizeDate(now).getTime() - PROJECT_STORAGE_LIMITS.stagedMaxAgeMs;
  const removed = [];
  for (const entry of await readdir(paths.stagedDir, { withFileTypes: true })) {
    if (!entry.isFile()) continue;
    const filePath = path.join(paths.stagedDir, entry.name);
    const info = await stat(filePath);
    if (info.mtimeMs >= cutoff) continue;
    await rm(filePath, { force: true });
    removed.push(entry.name);
  }
  return removed;
}

export async function pruneProjectRevisions(options = {}) {
  return withProjectMutationLock(options, () => pruneProjectRevisionsUnlocked(options));
}

async function pruneProjectRevisionsUnlocked({ rootDir, projectId } = {}) {
  const paths = projectPaths({ rootDir, projectId });
  await mkdir(paths.revisionsDir, { recursive: true });
  const entries = await readdir(paths.revisionsDir, { withFileTypes: true });
  const revisions = [...new Set(entries
    .filter((entry) => entry.isFile())
    .map((entry) => entry.name.match(/^(\d{6})\.(?:cq\.py|json)$/)?.[1])
    .filter(Boolean)
    .map(Number))].sort((left, right) => left - right);
  if (revisions.length <= PROJECT_STORAGE_LIMITS.revisions) return [];
  const keep = new Set([
    revisions[0],
    ...revisions.slice(-(PROJECT_STORAGE_LIMITS.revisions - 1)),
  ]);
  const removed = [];
  for (const revision of revisions) {
    if (keep.has(revision)) continue;
    const files = revisionFilePaths(paths.revisionsDir, revision);
    await Promise.all([rm(files.sourcePath, { force: true }), rm(files.metadataPath, { force: true })]);
    removed.push(revisionId(revision));
  }
  return removed;
}

export function normalizeProjectMemory(value = {}, {
  projectId = '',
  sourceHash = '',
  timestamp = new Date().toISOString(),
} = {}) {
  const input = isObject(value) ? value : {};
  const normalized = {
    schema_version: PROJECT_MEMORY_SCHEMA_VERSION,
    project_id: textValue(projectId || input.project_id),
    created_at: normalizeTimestamp(input.created_at, timestamp),
    updated_at: normalizeTimestamp(input.updated_at, timestamp),
    summary: truncateUtf8(redactCredentials(input.summary), PROJECT_STORAGE_LIMITS.memorySummaryBytes),
    facts: normalizeMemoryArray(input.facts),
    decisions: normalizeMemoryArray(input.decisions),
    constraints: normalizeMemoryArray(input.constraints),
    objects: normalizeMemoryArray(input.objects),
    revisions: normalizeMemoryArray(input.revisions),
    model_edit_history: normalizeMemoryArray(input.model_edit_history),
    last_revision_id: truncateUtf8(redactCredentials(input.last_revision_id), 256),
    project_source_hash: normalizeHash(sourceHash || input.project_source_hash),
  };
  const evictionOrder = ['model_edit_history', 'revisions', 'facts', 'decisions', 'constraints', 'objects'];
  while (Buffer.byteLength(JSON.stringify(normalized), 'utf8') + 1 > PROJECT_STORAGE_LIMITS.memoryBytes) {
    const key = evictionOrder.find((candidate) => normalized[candidate].length > 0);
    if (!key) break;
    normalized[key].shift();
  }
  return normalized;
}

export function hashProjectSource(source = '') {
  return crypto.createHash('sha256').update(String(source), 'utf8').digest('hex');
}

export function projectPaths({ rootDir, projectId, sourceFilename = 'model-source.cq.py' } = {}) {
  if (!rootDir) throw new TypeError('rootDir is required.');
  const normalizedProjectId = safeProjectId(projectId);
  const safeFilename = safeSourceFilename(sourceFilename);
  const projectDir = path.join(path.resolve(rootDir), 'exports', normalizedProjectId, 'project');
  return {
    projectId: normalizedProjectId,
    projectDir,
    sourceFilename: safeFilename,
    manifestPath: path.join(projectDir, 'project.json'),
    modelIndexPath: path.join(projectDir, 'model-index.json'),
    projectMemoryPath: path.join(projectDir, 'project-memory.json'),
    conversationPath: path.join(projectDir, 'conversation.jsonl'),
    sessionStatePath: path.join(projectDir, 'session-state.json'),
    assetsDir: path.join(projectDir, 'assets'),
    revisionsDir: path.join(projectDir, 'revisions'),
    stagedDir: path.join(projectDir, 'staged'),
  };
}

function safeProjectId(value) {
  const projectId = textValue(value);
  if (!PROJECT_ID_PATTERN.test(projectId)) {
    throw new TypeError('projectId contains unsupported characters.');
  }
  return projectId;
}

function safeSourceFilename(value) {
  const filename = path.basename(textValue(value));
  if (!SOURCE_FILENAME_PATTERN.test(filename) || filename !== textValue(value)) {
    throw new TypeError('sourceFilename must be a safe Python filename.');
  }
  return filename;
}

async function ensureModelIndex({ path: filePath, projectId, sourceFilename, sourceHash, artifact, timestamp }) {
  const existing = await readJsonIfPresent(filePath);
  const provided = isObject(artifact?.model_index)
    ? artifact.model_index
    : isObject(artifact?.design_state?.model_index)
      ? artifact.design_state.model_index
      : {};
  const artifactSurfaces = jsonArray(artifact?.engraving_surfaces || artifact?.design_state?.engraving_surfaces);
  const artifactObjects = buildArtifactModelObjects(artifact);
  const result = {
    ...(existing || provided),
    schema_version: MODEL_INDEX_SCHEMA_VERSION,
    project_id: projectId,
    created_at: normalizeTimestamp(existing?.created_at, timestamp),
    updated_at: normalizeTimestamp(existing?.updated_at, timestamp),
    source_file: sourceFilename,
    source_hash: sourceHash,
    objects: mergeIndexedItems(jsonArray(existing?.objects || provided.objects), artifactObjects),
    surfaces: mergeIndexedItems(jsonArray(existing?.surfaces || provided.surfaces), artifactSurfaces),
  };
  await writeJsonCompactAtomic(filePath, result);
  return result;
}

function buildArtifactModelObjects(artifact = {}) {
  const printable = jsonArray(artifact?.printable_parts || artifact?.design_state?.printable_parts)
    .map((item) => ({ ...item, object_type: item.object_type || 'printable_part' }));
  const hardware = jsonArray(artifact?.bom || artifact?.design_state?.bom)
    .map((item) => ({
      id: item.hardware_id || item.id,
      label: item.name || item.label || item.hardware_id,
      object_type: 'hardware',
      role: item.role || '',
    }));
  return mergeIndexedItems(printable, hardware);
}

function mergeIndexedItems(left = [], right = []) {
  const result = new Map();
  for (const item of [...left, ...right]) {
    if (!isObject(item)) continue;
    const id = textValue(item.id || item.surface_id || item.hardware_id);
    const key = id || crypto.createHash('sha1').update(JSON.stringify(item)).digest('hex');
    result.set(key, { ...(result.get(key) || {}), ...item });
  }
  return [...result.values()];
}

async function ensureProjectMemory({ path: filePath, projectId, artifact, timestamp, sourceHash }) {
  const existing = await readJsonIfPresent(filePath);
  const provided = isObject(artifact?.project_memory)
    ? artifact.project_memory
    : isObject(artifact?.design_state?.project_memory)
      ? artifact.design_state.project_memory
      : {};
  const result = normalizeProjectMemory({
    ...(existing || provided),
    schema_version: PROJECT_MEMORY_SCHEMA_VERSION,
    project_id: projectId,
    created_at: normalizeTimestamp(existing?.created_at, timestamp),
    updated_at: normalizeTimestamp(existing?.updated_at, timestamp),
    summary: textValue(existing?.summary || provided.summary || artifact?.title),
    facts: jsonArray(existing?.facts || provided.facts),
    decisions: jsonArray(existing?.decisions || provided.decisions),
    constraints: jsonArray(existing?.constraints || provided.constraints),
    objects: jsonArray(existing?.objects || provided.objects),
    revisions: jsonArray(existing?.revisions || provided.revisions),
    last_revision_id: textValue(existing?.last_revision_id || provided.last_revision_id),
    project_source_hash: textValue(existing?.project_source_hash || provided.project_source_hash || sourceHash),
    model_edit_history: jsonArray(existing?.model_edit_history || provided.model_edit_history),
  }, { projectId, sourceHash, timestamp });
  await writeJsonCompactAtomic(filePath, result);
  return result;
}

function normalizeTemplateMetadata(existing, artifact) {
  const value = isObject(existing) ? existing : {};
  const templateId = textValue(value.id || artifact?.template_id || artifact?.design_state?.intent?.template_id);
  if (!templateId) return { id: '', source: textValue(value.source) || 'generated_model' };
  const templateCase = artifact?.template_case === true || artifact?.design_mode === 'template_case'
    || artifact?.design_state?.template_case === true;
  const source = artifact?.template_source || artifact?.design_state?.template_source || {};
  return {
    id: templateId,
    source: textValue(value.source) || 'deterministic_template',
    ...(templateCase ? {
      model_contract: textValue(value.model_contract || artifact?.model_contract || artifact?.design_state?.model_contract),
      source_filename: textValue(value.source_filename || source.filename),
      source_sha256: textValue(value.source_sha256 || source.sha256),
    } : {}),
  };
}

function buildRevisionMetadata({
  projectId,
  revision,
  sourceFilename,
  sourceHash,
  previousSourceHash = '',
  createdAt,
  summary,
  changeType,
  operations = [],
  riskLevel = 'low',
}) {
  return {
    schema_version: PROJECT_REVISION_SCHEMA_VERSION,
    project_id: projectId,
    revision,
    created_at: createdAt,
    source_file: sourceFilename,
    source_hash: sourceHash,
    previous_source_hash: normalizeHash(previousSourceHash),
    change_type: textValue(changeType),
    risk_level: normalizeRiskLevel(riskLevel),
    summary: textValue(summary),
    operations: jsonArray(operations),
  };
}

function revisionFilePaths(revisionsDir, revision) {
  const prefix = revisionId(revision);
  return {
    sourcePath: path.join(revisionsDir, `${prefix}.cq.py`),
    metadataPath: path.join(revisionsDir, `${prefix}.json`),
  };
}

function revisionId(revision) {
  return String(revision).padStart(6, '0');
}

async function readTextIfPresent(filePath) {
  try {
    return await readFile(filePath, 'utf8');
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    throw error;
  }
}

async function readJsonIfPresent(filePath) {
  const text = await readTextIfPresent(filePath);
  if (text === null) return null;
  try {
    const value = JSON.parse(text);
    return isObject(value) ? value : null;
  } catch (error) {
    error.code = 'invalid_project_json';
    error.path = filePath;
    throw error;
  }
}

async function writeJsonAtomic(filePath, value) {
  await writeFileAtomic(filePath, `${JSON.stringify(value, null, 2)}\n`);
}

async function writeJsonCompactAtomic(filePath, value) {
  await writeFileAtomic(filePath, `${JSON.stringify(value)}\n`);
}

async function writeFileAtomic(filePath, content) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const tempPath = `${filePath}.${process.pid}.${crypto.randomUUID()}.tmp`;
  await writeFile(tempPath, content, 'utf8');
  try {
    await rename(tempPath, filePath);
  } catch (error) {
    try {
      const current = await readTextIfPresent(filePath);
      if (current !== null) {
        await writeFile(filePath, content, 'utf8');
        await rm(tempPath, { force: true });
        return;
      }
    } catch {
      // Preserve the original rename error below.
    }
    throw error;
  }
}

function normalizeProjectManifest(value, projectId) {
  const input = isObject(value) ? value : {};
  const fallbackTimestamp = new Date(0).toISOString();
  const createdAt = normalizeTimestamp(input.created_at, fallbackTimestamp);
  const updatedAt = normalizeTimestamp(input.updated_at, createdAt);
  const lastActivityAt = normalizeTimestamp(input.last_activity_at, updatedAt);
  const filename = safeSourceFilename(input.model_source?.filename || 'model-source.cq.py');
  const sourceHash = normalizeHash(input.model_source?.sha256 || input.project_source_hash);
  return {
    ...input,
    schema_version: PROJECT_MANIFEST_SCHEMA_VERSION,
    storage_policy_version: textValue(input.storage_policy_version) || PROJECT_STORAGE_POLICY_VERSION,
    project_id: projectId,
    title: textValue(input.title),
    created_at: createdAt,
    updated_at: updatedAt,
    last_activity_at: lastActivityAt,
    lifecycle_status: normalizeLifecycleStatus(input.lifecycle_status || (sourceHash ? 'ready' : 'draft')),
    project_revision: positiveInteger(input.project_revision, 1),
    project_source_hash: sourceHash,
    model_source: { filename, sha256: sourceHash },
    template: isObject(input.template) ? input.template : { id: '', source: 'generated_model' },
  };
}

function normalizeLifecycleStatus(value) {
  const status = textValue(value).toLowerCase();
  return LIFECYCLE_STATUSES.has(status) ? status : 'draft';
}

function normalizeMemoryArray(value) {
  return (Array.isArray(value) ? value : [])
    .slice(-PROJECT_STORAGE_LIMITS.memoryArrayItems)
    .map((item) => {
      if (typeof item === 'string') {
        return truncateUtf8(redactCredentials(item), PROJECT_STORAGE_LIMITS.memoryTextBytes);
      }
      const sanitized = sanitizeJsonValue(item);
      const encoded = JSON.stringify(sanitized);
      if (Buffer.byteLength(encoded, 'utf8') <= PROJECT_STORAGE_LIMITS.memoryObjectBytes) return sanitized;
      return {
        summary: truncateUtf8(redactCredentials(encoded), PROJECT_STORAGE_LIMITS.memoryObjectBytes - 64),
        truncated: true,
      };
    });
}

function sanitizeSessionState(value) {
  const sanitized = sanitizeJsonValue(value, 0, 8 * 1024);
  const encoded = JSON.stringify(sanitized);
  if (Buffer.byteLength(encoded, 'utf8') <= 256 * 1024) return sanitized;
  return {
    schema_version: PROJECT_SESSION_SCHEMA_VERSION,
    project_id: textValue(value?.project_id),
    updated_at: textValue(value?.updated_at),
    workflow_stage: textValue(value?.workflow_stage),
    parameter_overrides: {},
    last_blocking_state: sanitizeJsonValue(value?.last_blocking_state),
    active_drafts: {},
    template_confirmation: null,
    template_confirmation_required: value?.template_confirmation_required === true,
    truncated: true,
  };
}

function sanitizeJsonValue(value, depth = 0, stringLimit = PROJECT_STORAGE_LIMITS.memoryTextBytes) {
  if (value === null || value === undefined) return value ?? null;
  if (typeof value === 'string') return truncateUtf8(redactCredentials(value), stringLimit);
  if (typeof value === 'number' || typeof value === 'boolean') return value;
  if (depth >= 10) return '[层级过深，已截断]';
  if (Array.isArray(value)) {
    return value.slice(-PROJECT_STORAGE_LIMITS.memoryArrayItems)
      .map((item) => sanitizeJsonValue(item, depth + 1, stringLimit));
  }
  if (!isObject(value)) return truncateUtf8(redactCredentials(String(value)), stringLimit);
  const result = {};
  for (const [key, item] of Object.entries(value).slice(0, 200)) {
    if (/(?:api.?key|token|password|secret|authorization|密钥|密码)/i.test(key)) {
      result[key] = '[已脱敏]';
    } else {
      result[key] = sanitizeJsonValue(item, depth + 1, stringLimit);
    }
  }
  return result;
}

function normalizeVisibleAssistantResponse(value = {}) {
  const response = isObject(value) ? value : {};
  const summary = response.summary
    || response.surface_engraving_summary
    || response.model_edit_plan?.intent_summary
    || response.revision_intent?.summary
    || '';
  return sanitizeJsonValue({
    status: textValue(response.status),
    title: textValue(response.title),
    message: textValue(response.message),
    questions: (Array.isArray(response.questions) ? response.questions : [])
      .slice(0, 50)
      .map((item) => truncateUtf8(redactCredentials(textValue(item)), 8 * 1024)),
    blocking_reason: textValue(response.blocking_reason),
    summary,
  }, 0, 64 * 1024);
}

function conversationJsonLines(turns) {
  return turns.length ? `${turns.map((turn) => JSON.stringify(turn)).join('\n')}\n` : '';
}

function redactCredentials(value) {
  return String(value ?? '')
    .replace(/\bBearer\s+[A-Za-z0-9._~+\/-]+=*/gi, 'Bearer [已脱敏]')
    .replace(/\bsk-[A-Za-z0-9_-]{12,}\b/g, '[已脱敏]')
    .replace(/((?:api[ _-]?key|access[ _-]?token|token|password|secret|密钥|密码)\s*(?:是|为|[:=])\s*)[^\s,，;；]+/gi, '$1[已脱敏]');
}

function truncateUtf8(value, maxBytes) {
  const text = String(value ?? '');
  if (Buffer.byteLength(text, 'utf8') <= maxBytes) return text;
  return Buffer.from(text, 'utf8').subarray(0, Math.max(0, maxBytes - 3)).toString('utf8').replace(/\uFFFD+$/g, '') + '…';
}

function positiveInteger(value, fallback) {
  const number = Number(value);
  return Number.isInteger(number) && number > 0 ? number : fallback;
}

function normalizeDate(value) {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isFinite(date.getTime()) ? date : new Date();
}

function normalizeTimestamp(value, fallback) {
  const date = value ? new Date(value) : null;
  return date && Number.isFinite(date.getTime()) ? date.toISOString() : fallback;
}

function monotonicProjectTimestamp(existing, requestedTimestamp) {
  const requestedMs = Date.parse(requestedTimestamp || '');
  let latestMs = Number.isFinite(requestedMs) ? requestedMs : Date.now();
  for (const value of [existing?.last_activity_at, existing?.updated_at]) {
    const parsed = Date.parse(value || '');
    if (Number.isFinite(parsed)) latestMs = Math.max(latestMs, parsed);
  }
  return new Date(latestMs).toISOString();
}

function normalizeHash(value) {
  const hash = textValue(value).toLowerCase();
  return /^[a-f0-9]{64}$/.test(hash) ? hash : '';
}

function normalizeRiskLevel(value) {
  const level = textValue(value).toLowerCase();
  return ['low', 'medium', 'high'].includes(level) ? level : 'low';
}

function jsonArray(value) {
  return Array.isArray(value) ? JSON.parse(JSON.stringify(value)) : [];
}

function textValue(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function isObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
