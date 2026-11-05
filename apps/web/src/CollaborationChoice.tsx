import { useState } from 'react';
import type { ChangeRole, RequirementChange } from '../../../packages/contracts/src/workflow';

export function CollaborationChoice({projectId,change,disabled,onSave}:{projectId:string;change:RequirementChange;disabled:boolean;onSave:(roles:ChangeRole[])=>Promise<boolean>}) {
  const key=`zhangwen-collaboration-${projectId}-${change.id}`;
  const [selectionDraft,setSelected]=useState<ChangeRole[]>(()=>{try{const v:unknown=JSON.parse(localStorage.getItem(key)??'null');if(Array.isArray(v)&&v.every(r=>r==='engineer'||r==='structure'))return [...new Set(v)] as ChangeRole[];}catch{/* Saved choice remains available. */}return change.tasks.map(t=>t.role);});
  const selected=[...new Set([...selectionDraft,...change.tasks.filter(t=>t.status!=='pending').map(t=>t.role)])];
  const [storageError,setStorageError]=useState('');
  const changeSelection=(roles:ChangeRole[])=>{setSelected(roles);try{localStorage.setItem(key,JSON.stringify(roles));setStorageError('');}catch{setStorageError('选择草稿未能保存在浏览器中，请在离开前保存选择。');}};
  const save=async(roles:ChangeRole[])=>{if(await onSave(roles)){setSelected(roles);try{localStorage.removeItem(key);}catch{/* Selection is saved to the project. */}}};
  const decided=change.collaborationDecided||change.tasks.length>0;
  const hasWork=change.tasks.some(t=>t.status!=='pending');
  return <section className="collaboration-choice" aria-label="选择协作伙伴">
    <p>{decided?`已选择：${change.tasks.length?change.tasks.map(t=>t.role==='engineer'?'智能工程师':'结构工程师').join('、'):'暂不需要协作'}。`:'目标已确认，接下来请谁协作？'}</p>
    <details open={!decided||undefined}><summary>{decided?'查看或调整分工':'选择伙伴'}</summary>
      <fieldset disabled={disabled}><legend>可以选一位、两位，或暂不协作</legend>
        {([['structure','结构工程师','外形、材料、安装与活动空间'],['engineer','智能工程师','传感、控制、交互与程序']] as const).map(([role,name,duty])=><label key={role} className="collaboration-option"><input type="checkbox" checked={selected.includes(role)} disabled={change.tasks.some(t=>t.role===role&&t.status!=='pending')} onChange={e=>changeSelection(e.target.checked?[...selected,role]:selected.filter(r=>r!==role))}/><span><strong>{name}</strong><small>{duty}</small></span></label>)}
        <div className="workflow-actions"><button className="primary" disabled={!selected.length} onClick={()=>void save(selected)}>请所选伙伴协作</button><button disabled={hasWork} onClick={()=>void save([])}>暂不需要协作</button></div>
      </fieldset>
      <small>这里只记录分工。打开伙伴后，由你发送具体要求；也可以随时直接找任一位伙伴。</small>
      {hasWork&&<small>已有处理记录的伙伴会保留在分工中。</small>}
      {storageError&&<p role="alert">{storageError}</p>}
    </details>
  </section>;
}
