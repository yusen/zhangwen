import type { HardwareModuleGuide } from '../../../packages/contracts/src/platform';

export const validI2CAddress = (value: string) => /^0x[0-9a-f]{1,2}$/i.test(value) && Number(value) >= 1 && Number(value) <= 0x7f;
export const normalizeI2CAddress = (value: string) => validI2CAddress(value) ? '0x' + Number(value).toString(16).padStart(2, '0') : value;
export const guideValues = (guide: HardwareModuleGuide, setup?: Record<string, string>) => Object.fromEntries(
  guide.fields.map(field => [field.key, field.options.some(option => option.value === setup?.[field.key]) || (field.key === 'address' && validI2CAddress(setup?.[field.key] ?? '')) ? setup![field.key] : field.default]),
);
export const renderGuideText = (template: string, values: Record<string, string>) =>
  template.replace(/\{\{([A-Za-z0-9_]+)\}\}/g, (_, key: string) => values[key] ?? '');
export const guideCode = (guide: HardwareModuleGuide, setup?: Record<string, string>) => renderGuideText(guide.codeTemplate, guideValues(guide, setup));
export const guideLabels = (guide: HardwareModuleGuide, setup?: Record<string, string>) => {
  const values = guideValues(guide, setup);
  return Object.fromEntries(guide.fields.map(field => [field.key, field.options.find(option => option.value === values[field.key])?.label ?? values[field.key]]));
};
export const guideKind = { functional: '功能示例 · 待实测', diagnostic: '连通诊断 · 不含完整测量驱动', reference: '接线参考 · 待补驱动' };
