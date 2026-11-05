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
  if (!latest) return '尚未开始';
  if (latest.confirmed) return `V${latest.revision} · 已确认`;
  return confirmed ? `V${confirmed.revision} 已确认 · V${latest.revision} 草稿` : `草稿 V${latest.revision} · 待确认`;
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
