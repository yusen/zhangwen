import type { HardwareSummary } from '../../../packages/contracts/src/mu';

/** Display policy over the existing Hardware Skill catalog, not compatibility approval. */
export function sensorFamily(board?: HardwareSummary): 'Grove' | 'DFRobot' | null {
  if (!board) return null;
  const identity = `${board.componentId} ${board.skillName} ${board.displayName}`.toLowerCase();
  if (identity.includes('xiao') && /s3/.test(identity)) return 'Grove';
  if (identity.includes('k10')) return 'DFRobot';
  return null;
}

export type ModuleDirection = 'input' | 'output';

/** Use the source catalog's category; names never determine electrical direction. */
export function moduleDirection(item: HardwareSummary): ModuleDirection | null {
  if (item.category === 'SENSOR') return 'input';
  if (item.category === 'ACTUATOR' || item.category === 'DISPLAY') return 'output';
  return null;
}

export function modulesForBoard(hardware: HardwareSummary[], board?: HardwareSummary): HardwareSummary[] {
  const family = sensorFamily(board);
  if (!family) return [];
  return hardware.filter(item => {
    if (item.status !== 'ACTIVE' || !moduleDirection(item)) return false;
    const identity = `${item.componentId} ${item.skillName} ${item.displayName} ${item.description}`;
    return family === 'Grove' ? /(?:^|[^a-z])grove(?:[^a-z]|$)/i.test(identity) : /(?:^|[^a-z])dfrobot(?:[^a-z]|$)/i.test(identity);
  });
}
