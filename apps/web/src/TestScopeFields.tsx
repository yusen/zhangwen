import type { ControllerBaseline } from '../../../packages/contracts/src/workflow';
import type { TestSuggestion } from './workflowDrafts';

export function testScopeError(test: TestSuggestion, controllers: ControllerBaseline[]) {
  const ids=test.controllerIds??[];
  if(new Set(ids).size!==ids.length)return '关联主控重复，请重新选择。';
  if(ids.some(id=>!controllers.some(c=>c.id===id)))return '关联主控已移出项目，请重新选择。';
  const selected=controllers.filter(c=>!ids.length||ids.includes(c.id));
  return test.componentId&&!selected.some(c=>c.modules.some(m=>m.id===test.componentId))?`器件 ${test.componentId} 不在所选主控中，请重新选择。`:'';
}

export function TestScopeFields({test,controllers,onChange,label='测试'}:{test:TestSuggestion;controllers:ControllerBaseline[];onChange:(value:Partial<TestSuggestion>)=>void;label?:string}) {
  const selected=controllers.filter(c=>!test.controllerIds?.length||test.controllerIds.includes(c.id));
  const modules=[...new Map(selected.flatMap(c=>c.modules.map(m=>[m.id,{...m,name:`${c.name} · ${m.name}`} ] as const))).values()];
  const error=testScopeError(test,controllers);
  return <>
    <label className="field">关联主控<select aria-label={`${label} · 关联主控`} value={test.controllerIds?.length===1?test.controllerIds[0]:test.controllerIds?.length?'__multiple':''} onChange={e=>onChange({controllerIds:e.target.value?[e.target.value]:[]})}>
      <option value="">全部主控 / 整机</option>
      {!!test.controllerIds?.length&&test.controllerIds.length>1&&<option value="__multiple">指定 {test.controllerIds.length} 块主控</option>}
      {test.controllerIds?.filter(id=>!controllers.some(c=>c.id===id)).map(id=><option key={id} value={id}>失效主控：{id}</option>)}
      {controllers.map(c=><option key={c.id} value={c.id}>{c.name}</option>)}
    </select></label>
    {controllers.length>1&&<details className="classroom-details"><summary>按主控逐块选择</summary><small>未勾选时表示全部主控；勾选后只跟踪参与主控的器件与程序。</small>{controllers.map(c=><label key={c.id} className="workflow-checkbox"><input type="checkbox" aria-label={`${label} · 参与主控 ${c.name}`} checked={test.controllerIds?.includes(c.id)??false} onChange={e=>onChange({controllerIds:e.target.checked?[...(test.controllerIds??[]),c.id]:(test.controllerIds??[]).filter(id=>id!==c.id)})}/>{c.name}</label>)}</details>}
    <label className="field">关联器件<select aria-label={`${label} · 关联器件`} value={test.componentId} onChange={e=>onChange({componentId:e.target.value})}>
      <option value="">整机 / 不指定模块</option>
      {!!test.componentId&&!modules.some(m=>m.id===test.componentId)&&<option value={test.componentId}>失效器件：{test.componentId}</option>}
      {modules.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}
    </select></label>
    {error&&<p role="alert" className="workflow-warning">{error}</p>}
  </>;
}
