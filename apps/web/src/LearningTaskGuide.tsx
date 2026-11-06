import type { ChangeRole, WorkflowView } from '../../../packages/contracts/src/workflow';
import { lastConfirmed, testLabels } from './workflowUtils';
import { learningTaskText, makingStep } from './workflowGuide';

export function LearningTaskGuide({view,disabled,selected,pendingTests,onDefine,onRecord,onTask,onDiscuss,onConditions,onCollaborate,onSummary}: {
  view:WorkflowView|null; disabled:boolean; selected:string; pendingTests:number;
  onDefine:()=>void; onRecord:(id?:string)=>void; onTask:(role:ChangeRole,text:string)=>void;
  onDiscuss:(text:string)=>void; onConditions:()=>void; onCollaborate:()=>void; onSummary:()=>void;
}) {
  if (!view) return <section className="making-task" aria-label="当前制作任务"><p role="status">正在读取项目记录…</p></section>;
  const step=makingStep(view,selected), goal=lastConfirmed(view.checkpoint);
  const text=learningTaskText(view,step.title,step.steps,step.expected);
  const cases=view.checkpoint.cases.filter(c=>c.active);
  const states=view.caseStates.filter(s=>cases.some(c=>c.id===s.id));
  const passed=states.filter(s=>s.status==='passed').length;
  const needsRetest=states.filter(s=>s.status==='stale').length;
  const readyToReview=!selected&&cases.length>0&&cases.every(c=>states.some(s=>s.id===c.id&&s.status==='passed'));
  return <>
    <section className="making-task" aria-label="当前制作任务">
      <header><small>当前制作任务</small>{step.status&&<span className={`workflow-status ${step.status}`}>{testLabels[step.status]}</span>}</header>
      <h3>{step.title}</h3>
      <p><strong>本步目标：</strong>{step.test?step.test.expected:goal?.goal??'把想法整理成可开始制作的目标。'}</p>
      {step.reasons.map(reason=><p className="workflow-warning" role="status" key={reason}>{reason}，请重新测试。</p>)}
      <h4>怎么做</h4><ol>{step.steps.map((item,i)=><li key={i}>{item}</li>)}</ol>
      <div className="making-expected"><strong>完成标志</strong><p>{step.expected}</p></div>
      <div className="workflow-actions">{!goal?<button className="primary" disabled={disabled} onClick={onDefine}>整理作品目标</button>:readyToReview?<button className="primary" disabled={disabled} onClick={onSummary}>整理成果与发现</button>:<button className="primary" disabled={disabled} onClick={()=>onRecord(step.test?.id)}>记录一次测试</button>}
        <button disabled={disabled} onClick={()=>onDiscuss(`请帮助我完成这一步，并解释需要理解的方法：\n${text}`)}>和我讨论这一步</button>
      </div>
      {!!pendingTests&&<p className="workflow-warning">有 {pendingTests} 项测试建议尚未保存。<button disabled={disabled} onClick={()=>onRecord()}>核对测试建议</button></p>}
      {goal&&<details className="classroom-details"><summary>需要工程师帮助</summary><div className="workflow-actions"><button disabled={disabled} onClick={()=>onTask('engineer',text)}>请智能工程师帮助</button><button disabled={disabled} onClick={()=>onTask('structure',text)}>请结构工程师帮助</button></div><small>将本步要求带入对应输入框，核对后由你发送。</small></details>}
    </section>
    <details className="classroom-details making-progress"><summary>查看整体制作进展</summary><dl className="classroom-record-details">
      <div><dt>作品目标</dt><dd>{goal?`V${goal.revision} 已确认`:'尚未确认'} <button onClick={onDefine}>查看目标</button></dd></div>
      <div><dt>程序</dt><dd>{view.current.code.revision?`已保存 V${view.current.code.revision}，运行与效果需到智能工程师核对`:'尚无已保存程序；需要控制功能时再编写'}</dd></div>
      <div><dt>结构</dt><dd>{view.current.structure?`已保存 V${view.current.structure.revision}，模型状态与试装需到结构工程师核对`:'尚无已保存结构；需要外壳或机构时再设计'}</dd></div>
      <div><dt>实际测试</dt><dd>{cases.length?`${cases.length} 项要求，${passed} 项有当前适用的用户通过记录${needsRetest?`，${needsRetest} 项需复测`:''}`:'尚未建立测试要求'}</dd></div>
    </dl><div className="workflow-actions"><button onClick={onConditions}>实际接线与条件</button><button onClick={onCollaborate}>查看目标调整与协作记录</button></div></details>
  </>;
}
