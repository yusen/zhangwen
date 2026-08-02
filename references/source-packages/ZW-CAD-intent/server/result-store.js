import crypto from 'node:crypto';
import { mkdir, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { touchProjectActivity } from './project-store.js';

const RETENTION_POLICY_SCHEMA_VERSION = 'project_retention_v2';
const STORAGE_POLICY_VERSION = 'project_storage_policy_v2';
const RETENTION_POLICY_FILENAME = '.project-retention.json';
const RETENTION_AUDIT_FILENAME = 'project-retention-audit.json';
const activeProjectLeases = new Map();
const deletingProjectKeys = new Set();
let cleanupQueue = Promise.resolve();

const PRODUCT_RESULT_PREFIX = 'ZW-PRODUCT';
const PRODUCT_RESULT_PATTERN = /^ZW-PRODUCT-\d{8}-\d{6}(?:-\d{2})?$/;
const MANAGED_RESULT_FILES = Object.freeze([
  'base.stl',
  'lid.stl',
  'hardware-reference.stl',
  'opening-reference.stl',
  'preview.gltf',
  'cadquery.py',
  'run-cadquery-export.py',
  'model.step',
  'base.step',
  'lid.step',
  'hardware.step',
  'model.stl',
  'hardware.stl',
  'mesh-checks.json',
  'design-state.json',
  'checks.json',
  'artifact.json',
]);
const MANAGED_WORKFLOW_FILES = Object.freeze([
  '01_intent.json',
  '02_bom.json',
  '03_profile_report.json',
  '04_feasibility_report.json',
  '05_layout_plan.json',
  '06_checks.json',
  '07_cadquery.py',
  '08_export_manifest.json',
]);

export async function allocateResultDirectory({ rootDir, startedAt = new Date(), taskId = '' } = {}) {
  const exportsDir = path.join(rootDir, 'exports');
  const baseId = createResultId(startedAt);
  const requestedTaskId = normalizeTaskId(taskId);

  try {
    await mkdir(exportsDir, { recursive: true });
    await initializeRetentionPolicyForFreshRoot(exportsDir);
    if (requestedTaskId) {
      const exportDir = path.join(exportsDir, requestedTaskId);
      for (let attempt = 0; attempt < 50; attempt += 1) {
        await waitForProjectDeletion({ rootDir, resultId: requestedTaskId });
        if (await isExpiredProjectId(exportsDir, requestedTaskId)) {
          const error = new Error('当前项目已超过“最近三个”保留范围并被清理，旧页面不能重新创建它。请新建项目。');
          error.code = 'project_expired';
          throw error;
        }
        await mkdir(exportDir, { recursive: true });
        let leaseToken = '';
        try {
          leaseToken = acquireResultDirectoryLease({ rootDir, resultId: requestedTaskId });
          await touchProjectActivity({
            rootDir,
            projectId: requestedTaskId,
            now: new Date(),
          });
          return {
            status: 'ok',
            resultId: requestedTaskId,
            exportDir,
            started_at: startedAt.toISOString(),
            reused: true,
            lease_token: leaseToken,
            warning: null,
          };
        } catch (error) {
          if (leaseToken) {
            releaseResultDirectoryLease({
              rootDir,
              resultId: requestedTaskId,
              leaseToken,
            });
          }
          if (error?.code === 'project_cleanup_in_progress') continue;
          throw error;
        }
      }
      const error = new Error('项目清理仍在进行，请稍后重试。');
      error.code = 'project_cleanup_in_progress';
      throw error;
    }

    for (let index = 1; index <= 99; index += 1) {
      const resultId = index === 1 ? baseId : `${baseId}-${String(index).padStart(2, '0')}`;
      const exportDir = path.join(exportsDir, resultId);
      try {
        if (await isExpiredProjectId(exportsDir, resultId)) continue;
        await mkdir(exportDir);
        const leaseToken = acquireResultDirectoryLease({ rootDir, resultId });
        return {
          status: 'ok',
          resultId,
          exportDir,
          started_at: startedAt.toISOString(),
          reused: false,
          lease_token: leaseToken,
          warning: null,
        };
      } catch (error) {
        if (error?.code === 'EEXIST') continue;
        throw error;
      }
    }
    throw new Error(`Cannot allocate unique ${PRODUCT_RESULT_PREFIX} result directory.`);
  } catch (error) {
    if (error?.code === 'project_expired') throw error;
    const failedResultId = requestedTaskId || baseId;
    return {
      status: 'failed',
      resultId: failedResultId,
      exportDir: path.join(exportsDir, failedResultId),
      started_at: startedAt.toISOString(),
      warning: {
        id: 'result_directory_allocate_failed',
        status: 'fail',
        message: '项目目录分配失败；为避免写入错误项目，本轮已停止。',
        details: serializeResultStoreError(error),
      },
    };
  }
}

export async function clearManagedResultArtifacts({ rootDir, resultId } = {}) {
  const managedResultId = normalizeTaskId(resultId);
  if (!managedResultId) {
    return {
      status: 'warn',
      deleted: [],
      failed: [],
      warning: {
        id: 'managed_result_cleanup_skipped',
        status: 'warn',
        message: 'Result cleanup skipped because task id is not managed by ZW-CAD-intent.',
      },
    };
  }
  const exportDir = path.join(rootDir, 'exports', managedResultId);
  const report = {
    status: 'ok',
    resultId: managedResultId,
    deleted: [],
    failed: [],
  };

  await mkdir(exportDir, { recursive: true });
  for (const filename of MANAGED_RESULT_FILES) {
    const target = path.join(exportDir, filename);
    try {
      await rm(target, { force: true });
      report.deleted.push(filename);
    } catch (error) {
      report.failed.push({
        name: filename,
        path: target,
        error: serializeResultStoreError(error),
      });
    }
  }

  for (const filename of MANAGED_WORKFLOW_FILES) {
    const target = path.join(exportDir, 'workflow', filename);
    try {
      await rm(target, { force: true });
      report.deleted.push(`workflow/${filename}`);
    } catch (error) {
      report.failed.push({
        name: `workflow/${filename}`,
        path: target,
        error: serializeResultStoreError(error),
      });
    }
  }

  if (report.failed.length) report.status = 'warn';
  return report;
}

export async function cleanupResultDirectories(options = {}) {
  const task = cleanupQueue.catch(() => undefined).then(() => cleanupResultDirectoriesUnlocked(options));
  cleanupQueue = task.catch(() => undefined);
  return task;
}

async function cleanupResultDirectoriesUnlocked({ rootDir, keepCount = 3 } = {}) {
  const exportsDir = path.join(rootDir, 'exports');
  const report = {
    status: 'ok',
    keep_count: keepCount,
    kept: [],
    protected_projects: [],
    pending_deletion: [],
    deleted: [],
    failed: [],
  };

  try {
    await mkdir(exportsDir, { recursive: true });
    const entries = await readdir(exportsDir, { withFileTypes: true });
    const resultDirs = [];
    for (const entry of entries) {
      if (!entry.isDirectory() || !isManagedResultDirectory(entry.name)) continue;
      const fullPath = path.join(exportsDir, entry.name);
      const info = await stat(fullPath);
      const manifest = await readProjectManifest(fullPath);
      resultDirs.push({
        name: entry.name,
        path: fullPath,
        mtimeMs: info.mtimeMs,
        manifest,
        activityMs: projectActivityMs(manifest, info.mtimeMs, entry.name),
        active: isResultDirectoryActive({ rootDir, resultId: entry.name }),
      });
    }

    resultDirs.sort((a, b) => (
      b.activityMs - a.activityMs || b.name.localeCompare(a.name)
    ));
    const latest = resultDirs.slice(0, Math.max(0, keepCount));
    const latestIds = new Set(latest.map((item) => item.name));
    const activeOutsideLatest = resultDirs.filter((item) => item.active && !latestIds.has(item.name));
    const removable = resultDirs.filter((item) => !latestIds.has(item.name) && !item.active);
    report.protected_projects = activeOutsideLatest.map((item) => item.name);
    report.kept = [...latest, ...activeOutsideLatest].map((item) => item.name);

    const policy = await readRetentionPolicy(exportsDir);
    if (policy && policy.retention_enabled !== true) {
      report.status = 'retention_disabled';
      report.retention_enabled = false;
      report.kept = resultDirs.map((item) => item.name);
      report.pending_deletion = removable.map((item) => item.name);
      return report;
    }
    if (!policy && resultDirs.length > 0) {
      report.status = 'migration_required';
      report.pending_deletion = removable.map((item) => item.name);
      report.migration_required = true;
      report.audit_path = path.join(exportsDir, RETENTION_AUDIT_FILENAME);
      if (!await retentionAuditIsCurrent(exportsDir, resultDirs)) {
        await writeProjectRetentionAudit({
          exportsDir,
          resultDirs,
          keptIds: new Set(report.kept),
          pendingIds: new Set(report.pending_deletion),
          keepCount,
        });
      }
      return report;
    }
    if (!policy) {
      await writeRetentionPolicy(exportsDir, {
        retention_enabled: true,
        enabled_at: new Date().toISOString(),
        migration_confirmed_at: '',
        deleted_project_ids: [],
      });
    }

    for (const item of removable) {
      const deletionKey = leaseKey(rootDir, item.name);
      try {
        if (isResultDirectoryActive({ rootDir, resultId: item.name })) {
          if (!report.protected_projects.includes(item.name)) report.protected_projects.push(item.name);
          if (!report.kept.includes(item.name)) report.kept.push(item.name);
          continue;
        }
        deletingProjectKeys.add(deletionKey);
        if (isResultDirectoryActive({ rootDir, resultId: item.name })) {
          if (!report.protected_projects.includes(item.name)) report.protected_projects.push(item.name);
          if (!report.kept.includes(item.name)) report.kept.push(item.name);
          continue;
        }
        assertSafeManagedRemoval(exportsDir, item.path, item.name);
        await recordDeletedProjectIds(exportsDir, [item.name]);
        await rm(item.path, { recursive: true, force: true });
        report.deleted.push(item.name);
      } catch (error) {
        report.failed.push({
          name: item.name,
          path: item.path,
          error: serializeResultStoreError(error),
        });
      } finally {
        deletingProjectKeys.delete(deletionKey);
      }
    }
    if (report.failed.length) report.status = 'warn';
    return report;
  } catch (error) {
    return {
      ...report,
      status: 'warn',
      error: serializeResultStoreError(error),
    };
  }
}

export function acquireResultDirectoryLease({ rootDir, resultId } = {}) {
  const managedResultId = normalizeTaskId(resultId);
  if (!rootDir || !managedResultId) return '';
  const key = leaseKey(rootDir, managedResultId);
  if (deletingProjectKeys.has(key)) {
    const error = new Error('项目正在执行保留策略清理，请稍后重试。');
    error.code = 'project_cleanup_in_progress';
    throw error;
  }
  const token = crypto.randomUUID();
  const tokens = activeProjectLeases.get(key) || new Map();
  const timer = setTimeout(() => {
    releaseResultDirectoryLease({ rootDir, resultId: managedResultId, leaseToken: token });
  }, 10 * 60 * 1000);
  timer.unref?.();
  tokens.set(token, timer);
  activeProjectLeases.set(key, tokens);
  return token;
}

export function releaseResultDirectoryLease({ rootDir, resultId, leaseToken = '' } = {}) {
  const managedResultId = normalizeTaskId(resultId);
  if (!rootDir || !managedResultId || !leaseToken) return false;
  const key = leaseKey(rootDir, managedResultId);
  const tokens = activeProjectLeases.get(key);
  const timer = tokens?.get(leaseToken);
  if (!timer) return false;
  clearTimeout(timer);
  tokens.delete(leaseToken);
  if (!tokens.size) activeProjectLeases.delete(key);
  return true;
}

export async function generateProjectRetentionAudit({ rootDir, keepCount = 3 } = {}) {
  const exportsDir = path.join(rootDir, 'exports');
  await mkdir(exportsDir, { recursive: true });
  const resultDirs = await collectManagedResultDirectories(exportsDir, rootDir);
  resultDirs.sort((a, b) => b.activityMs - a.activityMs || b.name.localeCompare(a.name));
  const kept = resultDirs.slice(0, keepCount);
  const pending = resultDirs.slice(keepCount);
  const audit = await writeProjectRetentionAudit({
    exportsDir,
    resultDirs,
    keptIds: new Set(kept.map((item) => item.name)),
    pendingIds: new Set(pending.map((item) => item.name)),
    keepCount,
  });
  return {
    status: 'dry_run',
    audit_path: path.join(exportsDir, RETENTION_AUDIT_FILENAME),
    kept: kept.map((item) => item.name),
    pending_deletion: pending.map((item) => item.name),
    audit,
  };
}

export async function confirmProjectRetentionMigration({ rootDir, confirmed = false, keepCount = 3 } = {}) {
  if (confirmed !== true) {
    const error = new Error('必须收到用户明确确认，才能执行旧项目的一次性清理。');
    error.code = 'project_retention_confirmation_required';
    throw error;
  }
  const exportsDir = path.join(rootDir, 'exports');
  await mkdir(exportsDir, { recursive: true });
  const resultDirs = await collectManagedResultDirectories(exportsDir, rootDir);
  resultDirs.sort((a, b) => b.activityMs - a.activityMs || b.name.localeCompare(a.name));
  if (!await retentionAuditIsCurrent(exportsDir, resultDirs)) {
    await generateProjectRetentionAudit({ rootDir, keepCount });
    const error = new Error('项目活动顺序已变化，已重新生成保留清单；请核对新清单后再次确认。');
    error.code = 'project_retention_audit_stale';
    throw error;
  }
  const existingPolicy = await readRetentionPolicy(exportsDir) || {};
  await writeRetentionPolicy(exportsDir, {
    ...existingPolicy,
    retention_enabled: true,
    enabled_at: existingPolicy.enabled_at || new Date().toISOString(),
    migration_confirmed_at: new Date().toISOString(),
    deleted_project_ids: existingPolicy.deleted_project_ids || [],
  });
  return cleanupResultDirectories({ rootDir, keepCount });
}

export async function getProjectStorageHealth({ rootDir } = {}) {
  const exportsDir = path.join(rootDir, 'exports');
  await mkdir(exportsDir, { recursive: true });
  const projects = await collectManagedResultDirectories(exportsDir, rootDir);
  const sizes = [];
  for (const project of projects) sizes.push({ project_id: project.name, size_bytes: await directorySize(project.path) });
  const totalBytes = sizes.reduce((sum, item) => sum + item.size_bytes, 0);
  const policy = await readRetentionPolicy(exportsDir);
  let audit = null;
  try {
    audit = JSON.parse(await readFile(path.join(exportsDir, RETENTION_AUDIT_FILENAME), 'utf8'));
  } catch {
    audit = null;
  }
  const warnings = [];
  for (const item of sizes.filter((entry) => entry.size_bytes > 256 * 1024 * 1024)) {
    warnings.push({
      id: 'project_storage_large_project',
      status: 'warn',
      project_id: item.project_id,
      message: '单个项目目录已超过 256 MiB。',
    });
  }
  if (totalBytes > 1024 * 1024 * 1024) {
    warnings.push({
      id: 'project_storage_total_large',
      status: 'warn',
      message: '受管项目目录总量已超过 1 GiB。',
    });
  }
  return {
    schema_version: 'project_storage_health_v1',
    project_count: projects.length,
    total_bytes: totalBytes,
    retention_enabled: policy?.retention_enabled === true,
    migration_required: !policy && projects.length > 0,
    last_audit_at: audit?.generated_at || '',
    pending_delete_count: Number(audit?.pending_delete_count || 0),
    warnings,
  };
}

async function collectManagedResultDirectories(exportsDir, rootDir) {
  const entries = await readdir(exportsDir, { withFileTypes: true });
  const result = [];
  for (const entry of entries) {
    if (!entry.isDirectory() || !isManagedResultDirectory(entry.name)) continue;
    const fullPath = path.join(exportsDir, entry.name);
    const info = await stat(fullPath);
    const manifest = await readProjectManifest(fullPath);
    result.push({
      name: entry.name,
      path: fullPath,
      mtimeMs: info.mtimeMs,
      manifest,
      activityMs: projectActivityMs(manifest, info.mtimeMs, entry.name),
      active: isResultDirectoryActive({ rootDir, resultId: entry.name }),
    });
  }
  return result;
}

async function readProjectManifest(resultDir) {
  try {
    const text = await readFile(path.join(resultDir, 'project', 'project.json'), 'utf8');
    const manifest = JSON.parse(text);
    return manifest?.schema_version === 'zwcad_project_v1'
      && manifest?.project_id === path.basename(resultDir)
      ? manifest
      : null;
  } catch (error) {
    if (error?.code === 'ENOENT' || error?.name === 'SyntaxError') return null;
    throw error;
  }
}

function projectActivityMs(manifest, mtimeMs, resultId) {
  for (const value of [manifest?.last_activity_at, manifest?.updated_at, manifest?.created_at]) {
    const parsed = Date.parse(value || '');
    if (Number.isFinite(parsed)) return parsed;
  }
  const match = String(resultId).match(/^ZW-PRODUCT-(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/);
  if (match) {
    const parsed = new Date(
      Number(match[1]), Number(match[2]) - 1, Number(match[3]),
      Number(match[4]), Number(match[5]), Number(match[6]),
    ).getTime();
    if (Number.isFinite(parsed)) return parsed;
  }
  return mtimeMs;
}

function isResultDirectoryActive({ rootDir, resultId }) {
  return (activeProjectLeases.get(leaseKey(rootDir, resultId))?.size || 0) > 0;
}

function leaseKey(rootDir, resultId) {
  return `${path.resolve(rootDir).toLowerCase()}\n${resultId}`;
}

async function waitForProjectDeletion({ rootDir, resultId } = {}) {
  const key = leaseKey(rootDir, resultId);
  while (deletingProjectKeys.has(key)) {
    await new Promise((resolve) => setTimeout(resolve, 10));
  }
}

async function readRetentionPolicy(exportsDir) {
  try {
    const value = JSON.parse(await readFile(path.join(exportsDir, RETENTION_POLICY_FILENAME), 'utf8'));
    if (
      !value
      || typeof value !== 'object'
      || Array.isArray(value)
      || value.schema_version !== RETENTION_POLICY_SCHEMA_VERSION
      || typeof value.retention_enabled !== 'boolean'
      || !Array.isArray(value.deleted_project_ids)
    ) {
      const error = new Error('项目保留策略文件格式或版本无效；为保护现有项目，已停止自动清理。');
      error.code = 'project_retention_policy_invalid';
      throw error;
    }
    return value;
  } catch (error) {
    if (error?.code === 'ENOENT') return null;
    if (error?.name === 'SyntaxError') {
      error.code = 'project_retention_policy_invalid';
    }
    throw error;
  }
}

async function initializeRetentionPolicyForFreshRoot(exportsDir) {
  const policy = await readRetentionPolicy(exportsDir);
  if (policy) return policy;
  const entries = await readdir(exportsDir, { withFileTypes: true });
  if (entries.some((entry) => entry.isDirectory() && isManagedResultDirectory(entry.name))) return null;
  return writeRetentionPolicy(exportsDir, {
    retention_enabled: true,
    enabled_at: new Date().toISOString(),
    migration_confirmed_at: '',
    deleted_project_ids: [],
  });
}

async function writeRetentionPolicy(exportsDir, value) {
  const result = {
    schema_version: RETENTION_POLICY_SCHEMA_VERSION,
    retention_enabled: value.retention_enabled === true,
    enabled_at: String(value.enabled_at || ''),
    migration_confirmed_at: String(value.migration_confirmed_at || ''),
    deleted_project_ids: [...new Set(Array.isArray(value.deleted_project_ids) ? value.deleted_project_ids : [])]
      .filter(isManagedResultDirectory),
    updated_at: new Date().toISOString(),
  };
  const policyPath = path.join(exportsDir, RETENTION_POLICY_FILENAME);
  const tempPath = `${policyPath}.${process.pid}.${crypto.randomUUID()}.tmp`;
  await writeFile(tempPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
  try {
    await rename(tempPath, policyPath);
  } catch (error) {
    try {
      await writeFile(policyPath, `${JSON.stringify(result, null, 2)}\n`, 'utf8');
      await rm(tempPath, { force: true });
    } catch {
      throw error;
    }
  }
  return result;
}

async function recordDeletedProjectIds(exportsDir, deletedIds) {
  const policy = await readRetentionPolicy(exportsDir) || {};
  return writeRetentionPolicy(exportsDir, {
    ...policy,
    retention_enabled: true,
    deleted_project_ids: [...(policy.deleted_project_ids || []), ...deletedIds],
  });
}

async function isExpiredProjectId(exportsDir, resultId) {
  const policy = await readRetentionPolicy(exportsDir);
  return Array.isArray(policy?.deleted_project_ids) && policy.deleted_project_ids.includes(resultId);
}

export async function isExpiredResultProject({ rootDir, resultId } = {}) {
  const managedResultId = normalizeTaskId(resultId);
  if (!rootDir || !managedResultId) return false;
  return isExpiredProjectId(path.join(rootDir, 'exports'), managedResultId);
}

async function pathExists(target) {
  try {
    await stat(target);
    return true;
  } catch (error) {
    if (error?.code === 'ENOENT') return false;
    throw error;
  }
}

function assertSafeManagedRemoval(exportsDir, targetPath, resultId) {
  const resolvedExports = path.resolve(exportsDir);
  const resolvedTarget = path.resolve(targetPath);
  if (!isManagedResultDirectory(resultId)
    || path.basename(resolvedTarget) !== resultId
    || !resolvedTarget.startsWith(`${resolvedExports}${path.sep}`)) {
    const error = new Error('拒绝删除不在受管 exports 根目录内的路径。');
    error.code = 'unsafe_result_cleanup_path';
    throw error;
  }
}

async function writeProjectRetentionAudit({ exportsDir, resultDirs, keptIds, pendingIds, keepCount }) {
  const projects = [];
  for (const item of resultDirs) {
    projects.push({
      project_id: item.name,
      title: String(item.manifest?.title || ''),
      lifecycle_status: String(item.manifest?.lifecycle_status || (item.manifest ? 'ready' : 'legacy_or_transient')),
      last_activity_at: new Date(item.activityMs).toISOString(),
      size_bytes: await directorySize(item.path),
      decision: keptIds.has(item.name) ? 'keep' : pendingIds.has(item.name) ? 'pending_delete' : 'protected',
      reason: item.active
        ? '当前请求正在使用该项目。'
        : keptIds.has(item.name)
          ? `按活动时间位于最近 ${keepCount} 个项目内。`
          : `按活动时间超出最近 ${keepCount} 个项目；等待用户确认后删除整个项目目录。`,
    });
  }
  const audit = {
    schema_version: 'project_retention_audit_v1',
    generated_at: new Date().toISOString(),
    dry_run: true,
    keep_count: keepCount,
    project_count: projects.length,
    keep_count_actual: projects.filter((item) => item.decision === 'keep').length,
    pending_delete_count: projects.filter((item) => item.decision === 'pending_delete').length,
    projects,
  };
  await writeFile(path.join(exportsDir, RETENTION_AUDIT_FILENAME), `${JSON.stringify(audit, null, 2)}\n`, 'utf8');
  return audit;
}

async function retentionAuditIsCurrent(exportsDir, resultDirs) {
  try {
    const audit = JSON.parse(await readFile(path.join(exportsDir, RETENTION_AUDIT_FILENAME), 'utf8'));
    const generatedMs = Date.parse(audit?.generated_at || '');
    if (!Number.isFinite(generatedMs) || Date.now() - generatedMs > 5 * 60 * 1000) return false;
    const auditedProjects = Array.isArray(audit?.projects)
      ? audit.projects.map((item) => ({
          id: item.project_id,
          activity: item.last_activity_at,
        }))
      : [];
    const currentProjects = resultDirs.map((item) => ({
      id: item.name,
      activity: new Date(item.activityMs).toISOString(),
    }));
    return auditedProjects.length === currentProjects.length
      && auditedProjects.every((item, index) => (
        item.id === currentProjects[index].id
        && item.activity === currentProjects[index].activity
      ));
  } catch {
    return false;
  }
}

async function directorySize(root) {
  let total = 0;
  for (const entry of await readdir(root, { withFileTypes: true })) {
    const target = path.join(root, entry.name);
    if (entry.isSymbolicLink()) continue;
    if (entry.isDirectory()) total += await directorySize(target);
    else if (entry.isFile()) total += (await stat(target)).size;
  }
  return total;
}

export function createResultId(date = new Date()) {
  return `${PRODUCT_RESULT_PREFIX}-${formatLocalTimestamp(date)}`;
}

export function isManagedResultDirectory(name = '') {
  return PRODUCT_RESULT_PATTERN.test(String(name));
}

export function normalizeTaskId(value = '') {
  const text = typeof value === 'string' ? value.trim() : '';
  return isManagedResultDirectory(text) ? text : '';
}

export function formatLocalTimestamp(date = new Date()) {
  const value = date instanceof Date ? date : new Date(date);
  return [
    value.getFullYear(),
    pad2(value.getMonth() + 1),
    pad2(value.getDate()),
    '-',
    pad2(value.getHours()),
    pad2(value.getMinutes()),
    pad2(value.getSeconds()),
  ].join('');
}

function pad2(value) {
  return String(value).padStart(2, '0');
}

function serializeResultStoreError(error) {
  if (!error || typeof error !== 'object') {
    return { message: String(error || 'unknown result store error') };
  }
  return {
    name: error.name || 'Error',
    code: typeof error.code === 'string' ? error.code : '',
    path: typeof error.path === 'string' ? error.path : '',
    message: error instanceof Error ? error.message : String(error),
  };
}
