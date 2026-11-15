import type { ProjectConditions, ProjectDefinition, ProjectReflection, ProjectTestCase, TestObservation, WorkflowProposal } from '../../../packages/contracts/src/workflow';
import { definitionContent } from './workflowUtils';

export type CaseDraft = Omit<ProjectTestCase, 'id' | 'revision'> & { id?: string };
export type TestSuggestion = WorkflowProposal['tests'][number];
type ReflectionDraft = Pick<ProjectReflection, 'role' | 'author' | 'summary' | 'learned' | 'nextStep'>;
export interface WorkflowDrafts {
  changeId?: string;
  baseRevision: number | null;
  definition: ProjectDefinition | null;
  definitionEdited: boolean;
  pendingDefinition: ProjectDefinition | null;
  generatedTests: TestSuggestion[];
  conditions: ProjectConditions | null;
  test: CaseDraft | null;
  observations: Record<string, TestObservation>;
  reflection: ReflectionDraft | null;
  prompt: string;
}
export const freshDrafts = (): WorkflowDrafts => ({ baseRevision: null, definition: null, definitionEdited: false, pendingDefinition: null, generatedTests: [], conditions: null, test: null, observations: {}, reflection: null, prompt: '' });
export const draftKey = (id: string) => 'zhangwen-workflow-draft-' + id;
export function readDrafts(id: string): WorkflowDrafts {
  try {
    const raw = localStorage.getItem(draftKey(id));
    if (raw) {
      const v = JSON.parse(raw) as WorkflowDrafts;
      if (typeof v.prompt === 'string' && typeof v.observations === 'object' && v.observations !== null && (v.baseRevision === null || Number.isSafeInteger(v.baseRevision))) {
        // Drafts from the previous UI are hand drafts until explicitly saved.
        return { ...freshDrafts(), ...v, definitionEdited: v.definitionEdited ?? !!v.definition, generatedTests: Array.isArray(v.generatedTests) ? v.generatedTests : [] };
      }
    }
  } catch { /* Preserve the original browser backup if it cannot be read. */ }
  return freshDrafts();
}
export const testSuggestionKey = (t: TestSuggestion) => JSON.stringify([t.stage, t.componentId, t.title.trim(), t.procedure.trim(), t.expected.trim()]);
export function newTestSuggestions(tests: TestSuggestion[], saved: TestSuggestion[]): TestSuggestion[] {
  const seen = new Set(saved.map(testSuggestionKey));
  return tests.filter(test => {
    const key = testSuggestionKey(test);
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}
/** Called only for a newly received guide result, never by history refresh. */
export function projectProposal(drafts: WorkflowDrafts, proposal: WorkflowProposal, saved: ProjectTestCase[], revision: number): WorkflowDrafts {
  const definition = proposal.definition ? definitionContent(proposal.definition) : null;
  const preserveManual = !!drafts.definition && drafts.definitionEdited;
  return {
    ...drafts, baseRevision: revision, prompt: '',
    ...(definition ? preserveManual ? { pendingDefinition: definition } : { definition, definitionEdited: false, pendingDefinition: null } : {}),
    generatedTests: newTestSuggestions([...drafts.generatedTests, ...proposal.tests], saved),
  };
}
