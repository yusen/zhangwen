import { stat } from 'node:fs/promises';
import path from 'node:path';

export async function sanitizeBuildResult(result, rootDir, sourceSha256) {
  const exports = Array.isArray(result?.exports)
    ? (await Promise.all(result.exports.slice(0, 64).map(async (item) => {
        const absolute = text(item?.path);
        let storageKey = '';
        if (absolute) {
          const relative = path.relative(rootDir, absolute);
          if (!relative.startsWith('..') && !path.isAbsolute(relative)) {
            try {
              const file = await stat(absolute);
              if (file.isFile()) storageKey = relative.split(path.sep).join('/');
            } catch {
              storageKey = '';
            }
          }
        }
        const declaredStatus = text(item?.status);
        return {
          id: text(item?.id),
          label: text(item?.label),
          format: text(item?.format),
          fidelity: text(item?.fidelity),
          status: storageKey ? (declaredStatus || 'available') : 'unavailable',
          storageKey,
        };
      }))).filter((item) => item.storageKey || item.status !== 'available')
    : [];
  return {
    kind: 'CadBuildResult',
    status: text(result?.status) || 'failed',
    blockingReason: text(result?.blocking_reason),
    message: text(result?.message),
    sourceSha256,
    exports,
    meshValidationStatus: text(result?.mesh_validation_status),
    meshValidationReport: isObject(result?.mesh_validation_report)
      ? safeObject(result.mesh_validation_report, 64)
      : null,
  };
}

function safeObject(value, maxKeys) {
  return Object.fromEntries(
    Object.entries(value)
      .slice(0, maxKeys)
      .filter(([, child]) => ['string', 'number', 'boolean'].includes(typeof child) || child === null),
  );
}

function text(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function isObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}
