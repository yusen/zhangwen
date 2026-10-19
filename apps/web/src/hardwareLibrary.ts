import type { HardwareSummary } from '../../../packages/contracts/src/platform';

export type ModuleDirection = 'input' | 'output';

/** Use the source catalog's category; names never determine electrical direction. */
export function moduleDirection(item: HardwareSummary): ModuleDirection | null {
  if (item.category === 'SENSOR') return 'input';
  if (item.category === 'ACTUATOR' || item.category === 'DISPLAY') return 'output';
  return null;
}

/** All active modules are selectable with every board. Compatibility is checked separately. */
export function selectableModules(hardware: HardwareSummary[]): HardwareSummary[] {
  return hardware.filter(item => item.status === 'ACTIVE' && moduleDirection(item));
}

export const moduleBrand = (item: HardwareSummary) => item.catalog?.brand ?? '其他';
export const moduleType = (item: HardwareSummary) => item.catalog?.moduleType ?? (moduleDirection(item) === 'input' ? '其他输入' : '其他输出');

export function filterModules(items: HardwareSummary[], brand: string, direction: ModuleDirection | 'all', type: string, search: string): HardwareSummary[] {
  const query = search.trim().toLocaleLowerCase();
  return items.filter(item => (brand === 'all' || moduleBrand(item) === brand)
    && (direction === 'all' || moduleDirection(item) === direction)
    && (!type || moduleType(item) === type)
    && `${item.displayName} ${item.description} ${moduleBrand(item)} ${moduleType(item)}`.toLocaleLowerCase().includes(query));
}
