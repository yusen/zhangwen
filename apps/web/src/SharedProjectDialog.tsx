import { useEffect, useRef, useState } from 'react';
import type { SharedProjectInfo } from '../../../packages/contracts/src/workflow';
import { api } from './api';
import { Dialog } from './Dialog';
import './shared-project.css';

const statusNames = {unrecorded:'未记录',passed:'观察通过',failed:'观察未通过',blocked:'暂无法测试',stale:'需复测'};
const roleNames = {engineer:'智能工程师',structure:'结构工程师'};
const taskNames = {pending:'待处理',working:'处理中',delivered:'已交付',not_needed:'无需调整'};

export function SharedProjectDialog({projectId,unsaved,onClose}: {projectId:string;unsaved:boolean;onClose:()=>void}) {
  const [value,setValue]=useState<SharedProjectInfo|null>(null);
  const [error,setError]=useState('');
  const [loading,setLoading]=useState(true);
  const [refresh,setRefresh]=useState(0);
  const requestId=useRef(0);
  useEffect(()=>{
    const request=++requestId.current;
    setValue(null);setError('');setLoading(true);
    void api<SharedProjectInfo>(`/projects/${projectId}/workflow/shared`).then(result=>{
      if(request!==requestId.current)return;
      if(result.projectId!==projectId)throw new Error('资料与当前作品不一致');
      setValue(result);
    }).catch(e=>{if(request===requestId.current)setError(e instanceof Error?e.message:String(e));})
      .finally(()=>{if(request===requestId.current)setLoading(false);});
    return()=>{requestId.current++;};
  },[projectId,refresh]);
  return <Dialog title="三师共享信息" onClose={onClose} className="shared-project-dialog">
    <p className="muted">三师读取同一作品的已保存资料。查看资料不会发起协作或设备操作。</p>
    {unsaved&&<p className="shared-project-warning" role="note">当前还有未保存内容；下方展示已保存版本，手工草稿继续保留。</p>}
    <div className="shared-project-tools"><span aria-live="polite">{loading?'正在读取共享资料…':value?`作品：${value.projectName}`:'尚未读取到共享资料'}</span><button disabled={loading} onClick={()=>setRefresh(v=>v+1)}>刷新共享信息</button></div>
    {error&&<p role="alert">{error}。请刷新后核对。</p>}
    {value&&<div className="shared-project-content">
      <section><h3>作品目标</h3><p>{value.confirmedDefinition?.goal||'尚未确认目标，可以先讨论或独立工作。'}</p>{value.confirmedDefinition&&<details><summary>查看目标 V{value.confirmedDefinition.revision} 与完成条件</summary><p>{value.confirmedDefinition.behavior}</p><ul>{value.confirmedDefinition.criteria.map((text,i)=><li key={i}>{text}</li>)}</ul></details>}</section>
      <section><h3>主控与模块</h3><p>主控：{value.current.boardName}</p>{value.current.modules.find(m=>m.id===value.current.boardId)&&<small>主控资料版本：{value.current.modules.find(m=>m.id===value.current.boardId)?.revision}</small>}<ul>{value.current.modules.filter(m=>m.id!==value.current.boardId).map(m=><li key={m.id}>{m.name}<small>资料版本：{m.revision}</small></li>)}</ul>{!value.current.modules.some(m=>m.id!==value.current.boardId)&&<p className="muted">尚未选择外接模块。</p>}</section>
      <section><h3>成果版本</h3><p>程序：{value.current.code.revision?`${value.current.code.name} V${value.current.code.revision}（${value.current.code.mode}）`:'尚无当前已保存程序'}</p><p>结构：{value.current.structure?`${value.current.structure.name} V${value.current.structure.revision}`:'尚无已生成结构'}</p><small>只引用已保存成果；对话和手工草稿各自保留。</small></section>
      <section><h3>接线与实际条件</h3><dl>{([['firmware','固件'],['wiring','接线'],['power','供电'],['assembly','装配']] as const).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{value.actualConditions[key]||'未记录'}</dd></div>)}</dl></section>
      <section><h3>当前协作分工</h3>{value.requirementChanges.some(c=>c.tasks.length)?value.requirementChanges.filter(c=>c.tasks.length).map(c=><div key={c.id}><p>{c.summary}</p><ul>{c.tasks.map(t=><li key={t.role}>{roleNames[t.role]}：{taskNames[t.status]}{t.note&&<small>{t.note}</small>}</li>)}</ul></div>):<p className="muted">尚无已安排的协作任务。是否需要协作，由你决定。</p>}</section>
      <section><h3>测试与观察</h3>{!value.tests.length?<p className="muted">尚未保存测试清单。</p>:<ul>{value.tests.map(t=><li key={t.id}><strong>{t.title}：{statusNames[t.status]}</strong>{!!t.reasons.length&&<p>{t.reasons.join('；')}</p>}{t.observed&&<details><summary>查看已有观察</summary><p>{t.observed}</p><small>这是已有观察记录；当前是否适用以上方状态为准。</small></details>}</li>)}</ul>}</section>
      <p className="muted">保存、AI检查、设备提交与实际观察分别记录。当前状态不由文件齐全或历史通过自动推断。</p>
    </div>}
  </Dialog>;
}
