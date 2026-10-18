/** Structure uses the same Project, with independent immutable Artifact versions. */
export interface CadProfile {
  id: string; name: string; category: string; roles: string[]; source_status: string;
  dimensions_mm: { length_x: number; width_y: number; height_z: number };
  thumbnail_url?: string;
  componentId?: string | null;
}
export interface CadExport { id: string; label: string; format: string; url?: string; status?: string; fidelity?: string }
export interface CadCheck { id: string; status: string; message: string; details?: unknown }
export interface CadState {
  id: string; parameters: Record<string, number>;
  enclosure_parameters: { outer_box_size: CadSize; inner_box_size?: CadSize };
  layout_plan?: { hardware_transforms: { hardware_id: string; name: string; center: { x: number; y: number; z: number }; bounding_box: CadSize; mount_surface?: string; layout_rotation_deg?: number }[] };
  bom: { hardware_id: string; name?: string; quantity?: number; role?: string }[];
  [key: string]: unknown;
}
export interface CadSize { length_x: number; width_y: number; height_z: number }
export interface CadResult {
  status: 'requirement_analysis' | 'confirmation' | 'needs_input' | 'artifact';
  title?: string; message?: string; questions?: string[]; blocking_reason?: string;
  design_state?: CadState; partial_bom?: CadState['bom']; bom?: CadState['bom'];
  parameters?: Record<string, Record<string, number>>; checks?: CadCheck[];
  exports?: CadExport[]; cadquery_code?: string;
  resolution_options?: { id: string; label?: string; title?: string; description?: string }[];
  requirement_analysis?: Record<string, unknown>;
  build?: { status: string; message?: string; blocking_reason?: string };
  designKind?: 'parametric' | 'laser';
  designSpec?: DesignSpec;
  laserTextPaths?: Record<string, string>;
  [key: string]: unknown;
}
export interface StructureVersion {
  revision: number; createdAt: string; prompt: string; selectedIds: string[];
  customProfiles: Record<string, unknown>[]; result: CadResult; offline: boolean;
  jobId: string;
  designType?: 'model' | 'laser'; name?: string;
}
export interface StructureWorkspace {
  revision: number; versions: StructureVersion[];
  messages: { id: string; role: 'user' | 'assistant'; content: string; createdAt: string; designType?: 'model' | 'laser' }[];
}
export interface StructureAction {
  action: 'analyze' | 'confirm' | 'build' | 'revise' | 'parameters' | 'validate' | 'selected';
  expectedRevision: number; sourceRevision?: number;
  message?: string; selectedIds?: string[]; customProfiles?: Record<string, unknown>[];
  parameters?: Record<string, number>; faces?: Record<string, 'base_floor' | 'lid_inner'>;
  rotations?: Record<string, number>; resolutionOptionId?: string;
  designType?: 'model' | 'laser'; template?: 'box' | 'cup' | 'bracket' | 'plate' | 'round-tag' | 'panel-box' | 'finger-box' | 'rounded-box';
}
export interface StructureCatalog { profiles: CadProfile[]; cadqueryAvailable: boolean }
export interface SolidPart { kind: 'box' | 'cylinder' | 'sphere'; operation: 'add' | 'cut'; label: string; size: number[]; center: number[]; rotation: number[] }
export interface LaserShape { kind: 'rect' | 'circle' | 'polyline' | 'line' | 'text'; operation: 'cut' | 'engrave'; x: number; y: number; width: number; height: number; radius: number; points: number[][]; closed: boolean; text?: string; fontSize?: number }
export interface PanelText { panel: 'left' | 'right' | 'front' | 'back' | 'bottom' | 'top'; x: number; y: number; text: string; fontSize: number }
export interface FingerBox { width: number; depth: number; height: number; thickness: number; material: string }
export interface RoundedBox extends FingerBox { pattern_version?: 1 | 2; corner_radius: number; tab_width: number; slot_spacing: number; slot_bridge: number; slot_rows: number; top_lid: boolean; bottom_lid: boolean }
export interface DesignSpec { title: string; summary: string; questions: string[]; solid: SolidPart[]; fingerBox?: FingerBox | null; roundedBox?: RoundedBox | null; panelTexts?: PanelText[]; drawing?: { width: number; height: number; thickness: number; material: string; kerf: number; shapes: LaserShape[] } | null }
