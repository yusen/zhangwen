import { mkdir, readdir, rm, stat } from 'node:fs/promises';
import path from 'node:path';

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
    if (requestedTaskId) {
      const exportDir = path.join(exportsDir, requestedTaskId);
      await mkdir(exportDir, { recursive: true });
      return {
        status: 'ok',
        resultId: requestedTaskId,
        exportDir,
        started_at: startedAt.toISOString(),
        reused: true,
        warning: null,
      };
    }

    for (let index = 1; index <= 99; index += 1) {
      const resultId = index === 1 ? baseId : `${baseId}-${String(index).padStart(2, '0')}`;
      const exportDir = path.join(exportsDir, resultId);
      try {
        await mkdir(exportDir);
        return {
          status: 'ok',
          resultId,
          exportDir,
          started_at: startedAt.toISOString(),
          reused: false,
          warning: null,
        };
      } catch (error) {
        if (error?.code === 'EEXIST') continue;
        throw error;
      }
    }
    throw new Error(`Cannot allocate unique ${PRODUCT_RESULT_PREFIX} result directory.`);
  } catch (error) {
    return {
      status: 'failed',
      resultId: baseId,
      exportDir: path.join(exportsDir, baseId),
      started_at: startedAt.toISOString(),
      warning: {
        id: 'result_directory_allocate_failed',
        status: 'warn',
        message: '结果目录预创建失败；后续导出会继续尝试写入并返回具体失败项。',
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

export async function cleanupResultDirectories({ rootDir, keepCount = 3 } = {}) {
  const exportsDir = path.join(rootDir, 'exports');
  const report = {
    status: 'ok',
    keep_count: keepCount,
    kept: [],
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
      resultDirs.push({
        name: entry.name,
        path: fullPath,
        mtimeMs: info.mtimeMs,
      });
    }

    resultDirs.sort((a, b) => (
      b.name.localeCompare(a.name) || b.mtimeMs - a.mtimeMs
    ));
    report.kept = resultDirs.slice(0, keepCount).map((item) => item.name);
    const removable = resultDirs.slice(keepCount);
    for (const item of removable) {
      try {
        await rm(item.path, { recursive: true, force: true });
        report.deleted.push(item.name);
      } catch (error) {
        report.failed.push({
          name: item.name,
          path: item.path,
          error: serializeResultStoreError(error),
        });
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
