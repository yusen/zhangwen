import type { HardwareModuleGuide } from '../../../packages/contracts/src/platform';

export const guideValues = (guide: HardwareModuleGuide, setup?: Record<string, string>) => Object.fromEntries(
  guide.fields.map(field => [field.key, field.options.some(option => option.value === setup?.[field.key]) ? setup![field.key] : field.default]),
);
export const renderGuideText = (template: string, values: Record<string, string>) =>
  template.replace(/\{\{([A-Za-z0-9_]+)\}\}/g, (_, key: string) => values[key] ?? '');
export const guideCode = (guide: HardwareModuleGuide, setup?: Record<string, string>) => renderGuideText(guide.codeTemplate, guideValues(guide, setup));
export const guideLabels = (guide: HardwareModuleGuide, setup?: Record<string, string>) => {
  const values = guideValues(guide, setup);
  return Object.fromEntries(guide.fields.map(field => [field.key, field.options.find(option => option.value === values[field.key])!.label]));
};
export const guideKind = { functional: '功能示例 · 待实测', diagnostic: '连通诊断 · 不含完整测量驱动', reference: '接线参考 · 待补驱动' };
