import type { WorkflowView } from '../../../packages/contracts/src/workflow';
import type { TestSuggestion } from './workflowDrafts';
import { stages } from './workflowUtils';
import { TestScopeFields, testScopeError } from './TestScopeFields';

export function WorkflowTestDrafts({ tests, modules, controllers, mode, disabled, onChange, onMode, onSave }: {
  controllers?: NonNullable<WorkflowView['current']['controllers']>; mode?:'merge'|'replace'; onMode?:(mode:'merge'|'replace')=>void;
  tests: TestSuggestion[]; modules: WorkflowView['current']['modules']; disabled: boolean;
  onChange: (tests: TestSuggestion[]) => void; onSave: () => void;
}) {
  if (!tests.length) return null;
  const scope=controllers??[{id:'project',name:'项目主控',boardId:'',modules,code:{mode:'none' as const,revision:null,checksum:'',name:''}}];
  const invalid=tests.some(test=>!!testScopeError(test,scope));
  const update = (index: number, change: Partial<TestSuggestion>) => onChange(tests.map((t, i) => i === index ? { ...t, ...change } : t));
  return <section className="workflow-generated-tests" aria-label="待保存测试清单">
    <header><h3>测试清单 <small>{tests.length} 项待保存</small></h3><span>展开可修改</span></header>
    {onMode&&<label className="field">保存方式<select aria-label="测试清单保存方式" value={mode??'merge'} disabled={disabled} onChange={e=>onMode(e.target.value as 'merge'|'replace')}><option value="merge">新增或更新同一测试</option><option value="replace">替换当前清单，停用未保留项</option></select><small>更新沿用测试身份；停用项的历史观察保留。</small></label>}
    {tests.map((test, i) => <details key={i} className="workflow-generated-test">
      <summary><span>{i + 1}. {test.title || '未命名测试'}</span><small>{stages[test.stage]}{testScopeError(test,scope)?' · 关联无效，需修改':''}</small></summary>
      <fieldset disabled={disabled}>
        <label className="field">测试名称 *<input aria-label={`建议 ${i + 1} · 测试名称`} maxLength={100} value={test.title} onChange={e => update(i, { title: e.target.value })}/></label>
        <div className="workflow-two-fields">
          <label className="field">阶段<select aria-label={`建议 ${i + 1} · 阶段`} value={test.stage} onChange={e => update(i, { stage: e.target.value as TestSuggestion['stage'] })}>{Object.entries(stages).map(([id, name]) => <option key={id} value={id}>{name}</option>)}</select></label>
          <TestScopeFields test={test} controllers={scope} label={`建议 ${i+1}`} onChange={change=>update(i,change)}/>
        </div>
        <label className="field">测试步骤 *<textarea aria-label={`建议 ${i + 1} · 测试步骤`} rows={2} maxLength={1500} value={test.procedure} onChange={e => update(i, { procedure: e.target.value })}/></label>
        <label className="field">预期结果 *<textarea aria-label={`建议 ${i + 1} · 预期结果`} rows={2} maxLength={1500} value={test.expected} onChange={e => update(i, { expected: e.target.value })}/></label>
        <button className="workflow-text-button" onClick={() => onChange(tests.filter((_, n) => n !== i))}>移除此项</button>
      </fieldset>
    </details>)}
    <div className="workflow-actions"><button className="primary" disabled={disabled||invalid} onClick={onSave}>保存测试清单（{tests.length}项）</button><small>{invalid?'请展开标记的测试项，修正主控或器件关联。':'保存后再记录实际测试结果'}</small></div>
  </section>;
}
