export function resolveExportRequest(body = {}, environment = {}) {
  const allExports = collectExports(body);
  const requestedFormats = normalizeFilterList(body.formats ?? body.format);
  const requestedIds = normalizeFilterList(body.ids ?? body.id ?? body.exportIds);
  const exports = allExports.filter((item) => {
    const format = normalizeFilterValue(item.format);
    const id = normalizeFilterValue(item.id);
    const matchesFormat = !requestedFormats.length || requestedFormats.includes(format);
    const matchesId = !requestedIds.length || requestedIds.includes(id);
    return matchesFormat && matchesId;
  });

  return {
    status: 'export',
    message: '第一版导出由 artifact.exports 提供；真实 STEP/STL 需要 CadQuery 环境可用后再生成。',
    exports,
    filters: {
      formats: requestedFormats,
      ids: requestedIds,
    },
    available_formats: [...new Set(allExports.map((item) => normalizeFilterValue(item.format)).filter(Boolean))].sort(),
    export_count: exports.length,
    total_export_count: allExports.length,
    environment,
    source: 'deterministic',
  };
}

function collectExports(body = {}) {
  if (Array.isArray(body.artifact?.exports)) return body.artifact.exports;
  const designState = body.design_state || body.designState || body.currentDesignState;
  if (Array.isArray(designState?.exports)) return designState.exports;
  if (Array.isArray(body.exports)) return body.exports;
  return [];
}

function normalizeFilterList(value) {
  if (Array.isArray(value)) return [...new Set(value.map(normalizeFilterValue).filter(Boolean))];
  const normalized = normalizeFilterValue(value);
  return normalized ? [normalized] : [];
}

function normalizeFilterValue(value) {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}
