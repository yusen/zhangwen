import type { WorkflowView } from '../../../packages/contracts/src/workflow';
import type { TestSuggestion } from './workflowDrafts';
import { stages } from './workflowUtils';

export function WorkflowTestDrafts({ tests, modules, disabled, onChange, onSave }: {
  tests: TestSuggestion[]; modules: WorkflowView['current']['modules']; disabled: boolean;
  onChange: (tests: TestSuggestion[]) => void; onSave: () => void;
}) {
  if (!tests.length) return null;
  const update = (index: number, change: Partial<TestSuggestion>) => onChange(tests.map((t, i) => i === index ? { ...t, ...change } : t));
  return <section className="workflow-generated-tests" aria-label="待保存测试清单">
    <header><h3>测试清单 <small>{tests.length} 项待保存</small></h3><span>展开可修改</span></header>
    {tests.map((test, i) => <details key={i} className="workflow-generated-test">
      <summary><span>{i + 1}. {test.title || '未命名测试'}</span><small>{stages[test.stage]}</small></summary>
      <fieldset disabled={disabled}>
        <label className="field">测试名称 *<input aria-label={`建议 ${i + 1} · 测试名称`} maxLength={100} value={test.title} onChange={e => update(i, { title: e.target.value })}/></label>
        <div className="workflow-two-fields">
          <label className="field">阶段<select aria-label={`建议 ${i + 1} · 阶段`} value={test.stage} onChange={e => update(i, { stage: e.target.value as TestSuggestion['stage'] })}>{Object.entries(stages).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
          <label className="field">关联器件<select aria-label={`建议 ${i + 1} · 关联器件`} value={test.componentId} onChange={e => update(i, { componentId: e.target.value })}><option value="">整机 / 不指定模块</option>{test.componentId && !modules.some(m => m.id === test.componentId) && <option value={test.componentId}>原关联器件（已移出项目）</option>}{modules.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
        </div>
        <label className="field">测试步骤 *<textarea aria-label={`建议 ${i + 1} · 测试步骤`} rows={2} maxLength={1500} value={test.procedure} onChange={e => update(i, { procedure: e.target.value })}/></label>
        <label className="field">预期结果 *<textarea aria-label={`建议 ${i + 1} · 预期结果`} rows={2} maxLength={1500} value={test.expected} onChange={e => update(i, { expected: e.target.value })}/></label>
        <button className="workflow-text-button" onClick={() => onChange(tests.filter((_, n) => n !== i))}>移除此项</button>
      </fieldset>
    </details>)}
    <div className="workflow-actions"><button className="primary" disabled={disabled} onClick={onSave}>保存测试清单（{tests.length}项）</button><small>保存后再记录实际测试结果</small></div>
  </section>;
}
