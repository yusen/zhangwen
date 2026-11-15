import { useEffect, useRef, useState } from 'react';
import type { WorkspaceMode } from '../../../packages/contracts/src/platform';
import type { ChangeRole, ChangeTask, RequirementChange, WorkflowView } from '../../../packages/contracts/src/workflow';
import { api, ApiError } from './api';
import { Dialog } from './Dialog';
import { lastConfirmed } from './workflowUtils';
import { CollaborationChoice } from './CollaborationChoice';
import './requirement-sync.css';

const roles = {engineer:'智能工程师',structure:'结构工程师',learning:'学习设计师'};
const statuses = {pending:'待处理',working:'处理中',delivered:'已提交修改成果',not_needed:'已说明无需调整'};
export function changeProgress(change:RequirementChange,view:WorkflowView):string {
  if(change.status==='proposed')return change.baseDefinitionRevision===view.current.definitionRevision?'待学习设计师整理':'需求已更新，待重新整理';
  if(change.status==='cancelled')return '已撤销';
  if(change.definitionRevision!==view.current.definitionRevision)return '历史需求变更';
  const artifactChanged=change.tasks.some(t=>t.code&&JSON.stringify(t.code)!==JSON.stringify(view.current.code)||t.structure&&JSON.stringify(t.structure)!==JSON.stringify(view.current.structure));
  if(change.status==='completed'){
    const active=view.checkpoint.cases.filter(c=>c.active);
    const changed=!active.length||active.some(c=>!view.caseStates.some(s=>s.id===c.id&&s.status==='passed'))||artifactChanged;
    return changed?'验收后条件有变化，需重新核对':'已记录变更验收';
  }
  if(artifactChanged)return '程序或结构有新修改，请重新核对';
  if(!change.collaborationDecided&&!change.tasks.length)return '目标已确认，待选择协作';
  if(!change.tasks.length)return '暂不协作，可自行制作与测试';
  return change.tasks.every(t=>t.status==='delivered'||t.status==='not_needed')?'修改已处理，请测试作品':'请继续完成修改';
}

export function RequirementSync({projectId,sourceMode,initialText,onClose,onReview,onTask,onSaved,onBusy,engineeringDirty}: {
  projectId:string;sourceMode:WorkspaceMode;initialText:string;onClose:()=>void;
  onReview:(id:string)=>boolean;onTask:(role:ChangeRole,text:string)=>boolean;
  onSaved:(id:string)=>Promise<void>;onBusy:(value:boolean)=>void;engineeringDirty:boolean;
}) {
  const key=`zhangwen-change-input-${projectId}-${sourceMode}`;
  const [summary,setSummary]=useState(()=>{try{return localStorage.getItem(key)??initialText;}catch{return initialText;}});
  const [view,setView]=useState<WorkflowView|null>(null),[busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState(''),[needsRefresh,setNeedsRefresh]=useState(false);
  const noteKey=`zhangwen-change-notes-${projectId}`;
  const [notes,setNotes]=useState<Record<string,string>>(()=>{try{const v=JSON.parse(localStorage.getItem(noteKey)??'{}');return v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).filter(([,text])=>typeof text==='string')) as Record<string,string>:{};}catch{return {};}});
  const alive=useRef(true),sequence=useRef(0),writing=useRef(false);
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;onBusy(false);};},[]);
  useEffect(()=>{try{if(summary)localStorage.setItem(key,summary);else localStorage.removeItem(key);}catch{setError('浏览器未能保存变更草稿，请复制文本留存。');}},[key,summary]);
  useEffect(()=>{try{if(Object.keys(notes).length)localStorage.setItem(noteKey,JSON.stringify(notes));else localStorage.removeItem(noteKey);}catch{setError('浏览器未能保存处理说明草稿，请复制文本留存。');}},[noteKey,notes]);
  const refresh=async()=>{const seq=++sequence.current;try{const data=await api<WorkflowView>(`/projects/${projectId}/workflow`);if(alive.current&&seq===sequence.current){setView(data);setNeedsRefresh(false);setError('');}}catch(e){if(alive.current)setError(String(e instanceof Error?e.message:e));}};
  useEffect(()=>{void refresh();},[projectId]);
  const write=async(path:string,body:Record<string,unknown>={},method='POST'):Promise<boolean>=>{
    if(!view||writing.current||needsRefresh)return false;
    writing.current=true;setBusy(true);onBusy(true);setError('');setNotice('');
    try{
      const data=await api<WorkflowView>(`/projects/${projectId}/workflow${path}`,method,{expectedRevision:view.checkpoint.revision,...body});
      if(!alive.current)return false;
      sequence.current++;setView(data);setNotice('已保存。完成修改后，还需要测试作品并记录实际现象。');
      try{await onSaved(projectId);}catch(e){if(alive.current)setError(`本机已保存，项目文件夹同步未完成：${String(e instanceof Error?e.message:e)}。无需重复提交。`);}
      return true;
    }catch(e){if(alive.current){const uncertain=!(e instanceof ApiError);setNeedsRefresh(uncertain||e.status===409);setError(`${String(e instanceof Error?e.message:e)}${uncertain?'。提交结果未知，请刷新记录核对，勿直接重发。':''}`);}return false;}
    finally{writing.current=false;if(alive.current)setBusy(false);onBusy(false);}
  };
  const changes=view?.checkpoint.changes??[],current=view&&lastConfirmed(view.checkpoint),disabled=busy||!view||needsRefresh;
  const tasks=(change:RequirementChange)=>change.tasks.map(task=>{
    const k=change.id+task.role,note=notes[k]??task.note;
    const locked=disabled||change.status!=='confirmed'||change.definitionRevision!==view?.current.definitionRevision;
    const update=async(status:ChangeTask['status'])=>{
      const code=view?.current.code,structure=view?.current.structure;
      if(await write(`/changes/${change.id}/tasks/${task.role}`,{status,note,
        ...(status==='delivered'?(task.role==='engineer'?{code:{mode:code?.mode,revision:code?.revision}}:{structureRevision:structure?.revision}):{})},'PUT'))setNotes(previous=>{const next={...previous};delete next[k];return next;});
    };
    return <section className="requirement-task" key={task.role} aria-label={`${roles[task.role]}变更任务`}>
      <header><strong>{roles[task.role]}</strong><span>{statuses[task.status]}</span></header>
      {task.code&&<p>本次成果：{task.code.mode} V{task.code.revision} · {task.code.name}</p>}{task.structure&&<p>本次成果：结构 V{task.structure.revision} · {task.structure.name}</p>}
      {!locked&&engineeringDirty&&task.role==='engineer'&&<p className="muted">请先保存程序和器件选择，再提交本次修改。</p>}
      <label className="field">{roles[task.role]}处理说明<textarea aria-label={`${roles[task.role]}处理说明`} maxLength={1500} rows={2} disabled={locked} value={note} onChange={e=>setNotes(v=>({...v,[k]:e.target.value}))}/></label>
      <div className="requirement-actions"><button disabled={locked} onClick={()=>void update('working')}>开始处理</button>
        <button disabled={locked} onClick={()=>{const text=`处理项目调整（需求 V${change.definitionRevision}）：\n${change.summary}\n请依据当前已确认需求与实际条件，检查本角色的影响并给出修改方案及复测步骤。提交成果不代表实物通过。`;if(onTask(task.role,text))onClose();else setError('目标输入过长或当前设备状态不允许切换，请先处理后再打开任务。');}}>打开{roles[task.role]}</button>
        <button disabled={locked||engineeringDirty&&task.role==='engineer'||(task.role==='engineer'?!view?.current.code.revision:!view?.current.structure)} onClick={()=>void update('delivered')}>提交当前{task.role==='engineer'?'程序':'结构'}成果</button>
        <button disabled={locked||!note.trim()} onClick={()=>void update('not_needed')}>说明无需调整</button></div>
    </section>;
  });
  return <Dialog title="调整目标与分工" className="requirement-sync-dialog" onClose={()=>{if(!writing.current)onClose();}}>
    <section className="requirement-current">{!view ? <p role="status">{error ? '目标读取未完成，请刷新记录。' : '正在读取已保存目标与分工…'}</p> : <><strong>当前已确认目标{current?` V${current.revision}`:'：尚未确认'}</strong><p>{current?.goal||'可先提出想法，再由学习设计师整理。'}</p>{current&&<details><summary>查看动作规则与完成条件</summary><p>{current.behavior}</p><ul>{current.criteria.map((c,i)=><li key={i}>{c}</li>)}</ul></details>}</>}</section>
    <p className="muted">写下想改什么，请学习设计师整理并由你确认，再选择请谁协作。三位伙伴共用已保存目标，具体任务由你发送。</p>
    <label className="field">这次想改什么<textarea aria-label="这次想改什么" rows={3} maxLength={2000} disabled={busy} value={summary} onChange={e=>setSummary(e.target.value)} placeholder="例如：离开后等待3秒关闭，等待期间再次靠近取消关闭"/></label>
    <div className="requirement-actions"><button className="primary" disabled={disabled||!summary.trim()} onClick={async()=>{if(await write('/changes',{summary,sourceMode}))setSummary('');}}>提交给学习设计师</button><button disabled={busy} onClick={()=>void refresh()}>刷新记录</button></div>
    <div aria-live="polite">{busy&&<p role="status">正在保存…</p>}{error&&<p role="alert" className="requirement-error">{error}</p>}{notice&&<p role="status">{notice}</p>}</div>
    <h3>接下来要做的事</h3>{!view&&<p>正在读取当前项目…</p>}{view&&!changes.length&&<p className="muted">还没有调整记录。确认作品目标后，可以选择请谁协作。</p>}
    {[...changes].reverse().map(change=><article key={change.id} className="requirement-change">
      <header><strong>{roles[change.sourceMode]}提出{change.definitionRevision?` · 需求 V${change.definitionRevision}`:''}</strong><span>{view&&changeProgress(change,view)}</span></header><p>{change.summary}</p>
      <details className="classroom-details"><summary>查看调整记录</summary><small>来源需求 {change.baseDefinitionRevision?`V${change.baseDefinitionRevision}`:'未确认'} · {new Date(change.createdAt).toLocaleString()}</small></details>
      {change.status==='proposed'&&<div className="requirement-actions"><button disabled={disabled||change.baseDefinitionRevision!==view?.current.definitionRevision} onClick={()=>{if(onReview(change.id))onClose();}}>到学习设计师整理</button>
        {change.baseDefinitionRevision!==view?.current.definitionRevision&&<button disabled={disabled} onClick={()=>void write(`/changes/${change.id}/rebase`)}>按最新需求重新整理</button>}<button disabled={disabled} onClick={()=>void write(`/changes/${change.id}/cancel`)}>撤销此提案</button></div>}
      {change.status==='confirmed'&&change.definitionRevision===view?.current.definitionRevision&&<CollaborationChoice projectId={projectId} change={change} disabled={disabled} onSave={roles=>write(`/changes/${change.id}/collaboration`,{roles},'PUT')}/>}
      {tasks(change)}{change.status==='confirmed'&&change.definitionRevision===view?.current.definitionRevision&&<button className="primary" disabled={disabled||!change.collaborationDecided&&!change.tasks.length||change.tasks.some(t=>t.status==='pending'||t.status==='working')} onClick={()=>void write(`/changes/${change.id}/complete`)}>核对观察，完成本次调整</button>}
      {change.status==='completed'&&<p>完成验收：{change.verificationRunIds.length}项观察记录；{change.completedAt&&new Date(change.completedAt).toLocaleString()}。历史结论以当时版本与条件为准。</p>}
    </article>)}
  </Dialog>;
}
