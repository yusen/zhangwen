import type { HardwarePlacement } from '../../../packages/contracts/src/structure';
export interface StructureParameterDraft {
  sourceRevision: number;
  params: Record<string, number | null>;
  faces: Record<string, 'base_floor' | 'lid_inner'>;
  rotations: Record<string, number>;
  selected: string[];
  customProfiles: Record<string, unknown>[];
  hardwarePlacements?: HardwarePlacement[];
}
export const structureDraftKey = (projectId: string, type: string) => `zhangwen-structure-draft-${projectId}-${type}`;
export function readStructureDraft(projectId: string | undefined, type: string): StructureParameterDraft | null {
  if (!projectId) return null;
  try {
    const raw = localStorage.getItem(structureDraftKey(projectId,type));
    if (!raw || raw.length > 1_000_000) return null;
    const v = JSON.parse(raw) as StructureParameterDraft;
    if (!Number.isInteger(v.sourceRevision) || v.sourceRevision < 1 || !v.params || typeof v.params !== 'object' || Array.isArray(v.params)
        || !Object.values(v.params).every(n => n === null || typeof n === 'number')
        || !v.faces || !Object.values(v.faces).every(n=>n==='base_floor'||n==='lid_inner')
        || !v.rotations || !Object.values(v.rotations).every(n=>typeof n==='number')
        || !Array.isArray(v.selected) || !v.selected.every(n=>typeof n==='string')
        || !Array.isArray(v.customProfiles) || !v.customProfiles.every(n=>n&&typeof n==='object'&&!Array.isArray(n))) return null;
    if (v.hardwarePlacements !== undefined) {
      if (!Array.isArray(v.hardwarePlacements) || v.hardwarePlacements.length > 33 || !v.hardwarePlacements.every(p=>p && typeof p.componentId==='string' && typeof p.skillRevision==='string'
        && ['top','bottom','front','back','left','right'].includes(p.panel) && [0,90,180,270].includes(p.rotation)
        && ['screw','adhesive','opening_only'].includes(p.method) && typeof p.includeOpenings==='boolean'
        && (p.x===null || typeof p.x==='number') && (p.y===null || typeof p.y==='number'))) return null;
      v.hardwarePlacements = v.hardwarePlacements.map(p=>({...p,x:p.x===null?NaN:p.x,y:p.y===null?NaN:p.y}));
    }
    return v;
  } catch { return null; }
}
