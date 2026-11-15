import type { DefinitionVersion, ProjectDefinition, WorkflowMessage, WorkflowProposal } from '../../../packages/contracts/src/workflow';

export function definitionIssues(value: ProjectDefinition) {
  const issues: { label: string; message: string }[] = [];
  if (!value.goal.trim()) issues.push({ label: '项目目标 *', message: '项目目标' });
  if (!value.behavior.trim()) issues.push({ label: '动作规则 *', message: '动作规则' });
  const criteria = value.criteria.map(c => c.trim()).filter(Boolean);
  if (!criteria.length) issues.push({ label: '验收条件 *（每行一条）', message: '至少一条验收条件' });
  else if (criteria.length > 30 || criteria.some(c => c.length > 500)) issues.push({ label: '验收条件 *（每行一条）', message: '验收条件最多30条，每条不超过500字' });
  return issues;
}

/** Draft and confirmation are distinct; never label an existing draft as undefined. */
export function definitionProgress(saved: DefinitionVersion[], draft: ProjectDefinition | null) {
  const latest = saved.at(-1), confirmed = [...saved].reverse().find(d => d.confirmed);
  if (draft) return confirmed ? `V${confirmed.revision} 已确认 · 有修改待保存` : '编辑中 · 待确认';
  if (!latest) return '尚未保存目标';
  if (latest.confirmed) return `V${latest.revision} · 已确认`;
  return confirmed ? `V${confirmed.revision} 已确认 · V${latest.revision} 草稿` : `草稿 V${latest.revision} · 待确认`;
}

/** Confirmation comes from saved versions, never conversational claims. */
export function sharedDefinitionStatus(saved: DefinitionVersion[] | undefined) {
  if (!saved) return '正在读取目标记录';
  const confirmed = [...saved].reverse().find(d => d.confirmed);
  return confirmed ? `共用目标：V${confirmed.revision} 已确认` : '共用目标：尚未确认';
}

/** History recovery is explicit and only accepts a complete definition shape. */
export function latestSuggestedDefinition(messages: WorkflowMessage[]): ProjectDefinition | null {
  for (const message of [...messages].reverse()) {
    if (message.role !== 'assistant') continue;
    try {
      const d = JSON.parse(message.content).definition;
      if (d && ['problem', 'audience', 'goal', 'behavior', 'parameters', 'exceptionPolicy', 'constraints'].every(k => typeof d[k] === 'string')
        && Array.isArray(d.criteria) && d.criteria.every((c: unknown) => typeof c === 'string')) return d;
    } catch { /* An unreadable historical reply must not hide an older valid suggestion. */ }
  }
  return null;
}

export function asksDefinitionConfirmation(proposal: WorkflowProposal) {
  return !!proposal.definition && !!proposal.question && /确认|确定|定稿|按这版|按此/.test([proposal.question.text, ...proposal.question.options].join(' '));
}

export function latestSuggestedTests(messages: WorkflowMessage[]): WorkflowProposal['tests'] {
  const message = [...messages].reverse().find(m => m.role === 'assistant');
  if (!message) return [];
  try {
    const proposal = JSON.parse(message.content) as WorkflowProposal;
    return Array.isArray(proposal.tests) ? proposal.tests : [];
  } catch { return []; }
}

/** Used only by an explicit fill action, not when loading history or accepting AI claims. */
export function criteriaFromTests(tests: WorkflowProposal['tests']) {
  return [...new Set(tests.filter(t => t.stage === 'system').map(t => t.expected.trim()).filter(Boolean))];
}
