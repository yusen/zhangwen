export function selectViewerSourceFromExports(exports = [], mode = 'assembly', options = {}) {
  const cacheKey = options?.cacheKey || '';
  const usableExports = Array.isArray(exports) ? exports.filter(isUsableExport) : [];
  if (mode === 'exploded') {
    const cadqueryParts = buildCadqueryPartsSource(usableExports, cacheKey);
    if (cadqueryParts) return cadqueryParts;
    return null;
  }
  if (String(mode).startsWith('structural_part:')) {
    const partId = String(mode).slice('structural_part:'.length);
    const part = (Array.isArray(options.printableParts) ? options.printableParts : [])
      .find((item) => String(item?.id || '') === partId);
    const exportId = part?.source_export_id || part?.export_id || '';
    const item = exportId ? findExportById(usableExports, exportId) : null;
    return item ? exportToViewerSource(item, mode, cacheKey) : null;
  }
  if (String(mode).startsWith('template_part:')) {
    const partId = String(mode).slice('template_part:'.length);
    const part = (Array.isArray(options.printableParts) ? options.printableParts : [])
      .find((item) => String(item?.id || '') === partId);
    const exportId = part?.source_export_id || part?.export_id || '';
    const item = exportId
      ? findExportById(usableExports, exportId)
      : usableExports.find((entry) => entry.template_part_id === partId && normalizeFormat(entry.format) === 'stl');
    return item ? exportToViewerSource(item, mode, cacheKey) : null;
  }
  const preferred = preferredExportIdsForMode(mode);
  const item = findExportById(usableExports, preferred);
  if (!item) return null;

  const source = exportToViewerSource(item, mode, cacheKey);
  return source;
}

export function isRealCadQuerySource(source = {}) {
  return source.fidelity === 'cadquery' || source.format === 'cadquery_parts' || String(source.id || '').startsWith('cadquery_');
}

export function viewerStatusActionForModelEvent(event = {}, { viewerNotice = null, isCadqueryBuilding = false } = {}) {
  if (event.type === 'ready') {
    return viewerNotice
      ? { action: 'show_notice', notice: viewerNotice }
      : { action: 'hide' };
  }
  if (event.type === 'error') {
    return {
      action: 'show_error',
      title: '模型加载失败',
      body: event.message || '',
    };
  }
  if (event.type === 'loading' && !isCadqueryBuilding) {
    return {
      action: 'show_loading',
      title: '加载模型',
      body: event.message || '',
      thinking: true,
    };
  }
  return { action: 'none' };
}

function preferredExportIdsForMode(mode = 'assembly') {
  return {
    assembly: ['cadquery_stl', 'cadquery_structural_scene_stl', 'cadquery_template_scene_stl'],
    base: ['cadquery_base_stl'],
    lid: ['cadquery_lid_stl'],
    hardware: ['cadquery_hardware_stl'],
    exploded: [],
  }[mode] || ['cadquery_stl'];
}

function buildCadqueryPartsSource(exports, cacheKey = '') {
  const base = findExportById(exports, 'cadquery_base_stl');
  const lid = findExportById(exports, 'cadquery_lid_stl');
  const hardware = findExportById(exports, 'cadquery_hardware_stl');
  if (!base || !lid || !hardware) return null;
  const baseSource = exportToViewerSource(base, 'base', cacheKey);
  const lidSource = exportToViewerSource(lid, 'lid', cacheKey);
  const hardwareSource = exportToViewerSource(hardware, 'hardware', cacheKey);
  const source = {
    id: 'cadquery_exploded_parts',
    url: `cadquery_parts:${[baseSource.url, lidSource.url, hardwareSource.url].join('|')}`,
    format: 'cadquery_parts',
    label: '真实 CadQuery 爆炸视图',
    mode: 'exploded',
    fidelity: 'cadquery',
    parts: [
      baseSource,
      lidSource,
      hardwareSource,
    ],
  };
  return source;
}

function findExportById(exports, ids) {
  const idList = Array.isArray(ids) ? ids : [ids];
  return idList
    .map((id) => exports.find((item) => item.id === id))
    .find(Boolean) || null;
}

function exportToViewerSource(item, mode, cacheKey = '') {
  return {
    id: item.id || '',
    url: withCacheKey(item.url, cacheKey),
    format: normalizeFormat(item.format) || formatFromUrl(item.url),
    label: item.label || item.id || item.url,
    mode: viewerModeForExport(item, mode),
    fidelity: item.fidelity || '',
  };
}

function viewerModeForExport(item, mode) {
  const id = item.id || '';
  if (id.includes('base')) return 'base';
  if (id.includes('lid')) return 'lid';
  if (id.includes('hardware')) return 'hardware';
  if (String(mode).startsWith('structural_part:')) return 'structural_part';
  if (String(mode).startsWith('template_part:')) return 'template_part';
  return mode === 'exploded' ? 'assembly' : mode;
}

function isUsableExport(item) {
  if (!item?.url) return false;
  return !['pending', 'pending_missing_cadquery', 'not_generated_yet', 'failed', 'failed_write'].includes(item.status);
}

function withCacheKey(url = '', cacheKey = '') {
  if (!cacheKey || !url || String(url).startsWith('cadquery_parts:')) return url;
  const separator = String(url).includes('?') ? '&' : '?';
  return `${url}${separator}v=${encodeURIComponent(cacheKey)}`;
}

function normalizeFormat(value) {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}

function formatFromUrl(url = '') {
  const match = String(url).toLowerCase().match(/\.([a-z0-9]+)(?:$|\?)/);
  return match ? match[1] : '';
}
