/** Project learning and acceptance records in the original Artifact store. */
export interface ProjectDefinition {
  problem: string; audience: string; goal: string; behavior: string;
  parameters: string; exceptionPolicy: string; constraints: string; criteria: string[];
}
export interface DefinitionVersion extends ProjectDefinition { revision: number; createdAt: string; confirmed: boolean }
export interface ProjectConditions { firmware: string; wiring: string; power: string; assembly: string }
export type TestStage = 'module' | 'system' | 'assembly';
export interface ProjectTestCase { id: string; revision: number; title: string; stage: TestStage; componentId: string; procedure: string; expected: string; active: boolean }
export interface CodeReference { mode: 'micropython' | 'lua' | 'idea' | 'claw' | 'none'; revision: number | null; checksum: string; name: string }
export interface StructureReference { revision: number; checksum: string; name: string }
export interface ProjectBaseline {
  boardId: string; boardName: string; modules: { id: string; name: string; revision: string }[];
  definitionRevision: number | null; code: CodeReference; structure: StructureReference | null;
  conditions: ProjectConditions; fingerprint: string;
}
export interface TestObservation {
  caseId: string; result: 'passed' | 'failed' | 'blocked'; observer: string;
  prediction: string; observed: string; explanation: string; changes: string;
  evidenceIds: string[]; code: Pick<CodeReference, 'mode' | 'revision'>; structureRevision: number | null;
  expectedBaseline: string;
}
export interface ProjectTestRun {
  id: string; createdAt: string; test: ProjectTestCase; baseline: ProjectBaseline;
  result: TestObservation['result']; observer: string; prediction: string; observed: string;
  explanation: string; changes: string; evidenceIds: string[];
}
export interface ProjectEvidence { id: string; name: string; mime: 'image/png' | 'image/jpeg' | 'image/webp' | 'text/plain'; content: string; checksum: string; caption: string; createdAt: string }
export interface ProjectReflection { revision: number; createdAt: string; role: 'teacher' | 'student'; author: string; summary: string; learned: string; nextStep: string }
export interface ReviewSource { baseline: ProjectBaseline; records: string; checkedAt: string; facts: string[]; method: 'records' | 'ai' }
export type LearningDocumentKind = 'teaching' | 'poster' | 'application' | 'log';
export interface LearningDocument { id: string; revision: number; kind: LearningDocumentKind; title: string; content: string; createdAt: string; source: 'blank' | 'project'; sourceFingerprint: string | null; generated: boolean }
export interface DocumentMessage { id:string; role:'user'|'assistant'; scope:'teaching'|'archive'; source:'blank'|'project'; content:string; createdAt:string }
export interface ProjectReview { conclusion: string; gaps: string[]; nextSteps: string[]; decisions: string[]; comparison: string; source?: ReviewSource | null }
export interface WorkflowProposal { summary: string; question: { text: string; options: string[] } | null; definition: ProjectDefinition | null; tests: Omit<ProjectTestCase, 'id' | 'revision' | 'active'>[]; review?: ProjectReview | null }
export interface WorkflowMessage { id: string; role: 'user' | 'assistant'; content: string; createdAt: string }
export type ChangeRole = 'engineer' | 'structure';
export interface ChangeTask {
  role: ChangeRole; status: 'pending' | 'working' | 'delivered' | 'not_needed'; note: string;
  code: CodeReference | null; structure: StructureReference | null; updatedAt: string;
}
export interface RequirementChange {
  id: string; createdAt: string; sourceMode: ChangeRole | 'learning'; summary: string;
  baseDefinitionRevision: number | null; definitionRevision: number | null;
  status: 'proposed' | 'confirmed' | 'completed' | 'cancelled'; baseline: ProjectBaseline;
  tasks: ChangeTask[]; verificationRunIds: string[]; completedAt: string | null;
  collaborationDecided?: boolean;
}
export interface WorkflowCheckpoint {
  documents?: LearningDocument[];
  documentMessages?: DocumentMessage[];
  schemaVersion: 1; revision: number; definitions: DefinitionVersion[]; conditions: ProjectConditions;
  cases: ProjectTestCase[]; runs: ProjectTestRun[]; evidence: ProjectEvidence[];
  reflections: ProjectReflection[]; messages: WorkflowMessage[];
  changes?: RequirementChange[];
}
export interface WorkflowView {
  checkpoint: WorkflowCheckpoint; current: ProjectBaseline; codeVersions: CodeReference[];
  structureVersions: StructureReference[];
  caseStates: { id: string; status: 'unrecorded' | 'passed' | 'failed' | 'blocked' | 'stale'; reasons: string[]; runId: string | null }[];
  reviewRecords: string;
}

/** Read-only projection of the existing Project/Artifact records, never a second store. */
export interface SharedProjectInfo {
  projectId: string; projectName: string; projectRevision: number; workflowRevision: number;
  current: ProjectBaseline; confirmedDefinition: DefinitionVersion | null;
  actualConditions: ProjectConditions;
  requirementChanges: Pick<RequirementChange, 'id' | 'summary' | 'status' | 'sourceMode' | 'definitionRevision' | 'tasks'>[];
  tests: { id: string; title: string; stage: TestStage; status: WorkflowView['caseStates'][number]['status'];
    reasons: string[]; observed: string; recordedResult: TestObservation['result'] | null; recordedBaseline: string | null }[];
  program: { text: string; truncated: boolean; characters: number };
  structure: { text: string; truncated: boolean; characters: number };
  fingerprint: string;
}
