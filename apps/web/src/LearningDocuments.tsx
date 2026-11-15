import { useEffect, useRef, useState } from 'react';
import { BookOpen, Download, FileText, LoaderCircle, Plus, RefreshCw, Save, Sparkles } from 'lucide-react';
import type { LearningDocument, LearningDocumentKind, WorkflowView } from '../../../packages/contracts/src/workflow';
import { api, ApiError } from './api';
import { escapeHtml } from './workflowUtils';
import { referenceFile } from './ProjectReferences';
import type { ProjectReference } from '../../../packages/contracts/src/platform';
import './learningDocuments.css';

const labels:Record<LearningDocumentKind,string>={teaching:'教案大纲',poster:'展示海报文案',application:'申报材料',log:'过程日志'};
interface Draft {id?:string;kind:LearningDocumentKind;title:string;content:string;prompt:string;source:'blank'|'project';baseRevision:number|null;edited:boolean}
const empty=(teaching:boolean):Draft=>({kind:teaching?'teaching':'poster',title:'',content:'',prompt:'',source:teaching?'blank':'project',baseRevision:null,edited:false});
function read(key:string,teaching:boolean):Draft{
  try{const value=JSON.parse(localStorage.getItem(key)??'null') as Draft|null;
    if(value&&value.kind in labels&&[value.title,value.content,value.prompt].every(s=>typeof s==='string')&&['blank','project'].includes(value.source)&&value.content.length<=30000&&value.prompt.length<=4000)return {...empty(teaching),...value};
  }catch{/* keep existing records authoritative */}return empty(teaching);
}
export function documentHtml(title:string,content:string):string{
  return `<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>${escapeHtml(title)}</title><style>body{font:16px/1.8 system-ui;max-width:900px;margin:40px auto;padding:0 24px;color:#223047}pre{font:inherit;white-space:pre-wrap;overflow-wrap:anywhere}@media print{body{margin:0}}</style><h1>${escapeHtml(title)}</h1><pre>${escapeHtml(content)}</pre></html>`;
}
function download(name:string,text:string,type:string){const url=URL.createObjectURL(new Blob([text],{type}));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

/** Separate text workflow, stored in the original project Artifact. No model tools. */
export function LearningDocuments({projectId,teaching,active,disabled,onNew,onSaved,onDirty,onBusy,onRegisterSave,refreshKey}: {
  projectId?:string;teaching:boolean;active:boolean;disabled:boolean;onNew:()=>void;onSaved:(id:string)=>Promise<void>;
  onDirty:(dirty:boolean)=>void;onBusy:(busy:boolean)=>void;onRegisterSave:(fn:(()=>Promise<void>)|null)=>void;
  refreshKey?:number;
}){
  const key=`zhangwen-document-draft-${projectId??'scratch'}-${teaching?'teaching':'archive'}`;
  const [draft,setDraft]=useState(()=>read(key,teaching)),draftRef=useRef(draft);draftRef.current=draft;
  const [view,setView]=useState<WorkflowView|null>(null),viewRef=useRef(view);viewRef.current=view;
  const [busy,setBusy]=useState(false),busyRef=useRef(false),alive=useRef(true);
  const [error,setError]=useState(''),[notice,setNotice]=useState(''),[conflict,setConflict]=useState(false),[unknown,setUnknown]=useState(false),[editing,setEditing]=useState(false);
  const [refreshing,setRefreshing]=useState(false),[conflictReady,setConflictReady]=useState(false);
  const [storageError,setStorageError]=useState('');
  const [imports,setImports]=useState<ProjectReference[]>([]);
  const refreshImports=async()=>{if(!projectId||teaching)return;const result=await api<{references:ProjectReference[]}>(`/projects/${projectId}/references`);if(alive.current)setImports(result.references.filter(r=>r.name.startsWith('成果档案/')));};
  const dirty=draft.edited||!!draft.prompt.trim();
  useEffect(()=>{alive.current=true;return()=>{alive.current=false;onDirty(false);onRegisterSave(null);};},[]);
  useEffect(()=>{onDirty(dirty);try{if(dirty)localStorage.setItem(key,JSON.stringify(draft));else localStorage.removeItem(key);setStorageError('');}catch{setStorageError('浏览器未能保留草稿，请导出当前内容后再离开。');}},[dirty,draft,key,onDirty]);
  const refresh=async()=>{if(!projectId)return;setRefreshing(true);try{const result=await api<WorkflowView>(`/projects/${projectId}/workflow`);if(alive.current){setView(result);viewRef.current=result;setUnknown(false);setConflictReady(true);if(!draftRef.current.edited&&!draftRef.current.content){const doc=[...(result.checkpoint.documents??[])].reverse().find(d=>teaching?d.kind==='teaching':d.kind!=='teaching');if(doc)setDraft(p=>({...p,id:doc.id,kind:doc.kind,title:doc.title,content:doc.content,source:doc.source,baseRevision:result.checkpoint.revision}));}}}catch(e){if(alive.current)setError(String(e instanceof Error?e.message:e));}finally{if(alive.current)setRefreshing(false);}};
  useEffect(()=>{if(active&&!busyRef.current){void refresh();void refreshImports().catch(e=>setError(e instanceof Error?e.message:String(e)));}},[active,projectId,refreshKey]);
  const update=(patch:Partial<Draft>)=>setDraft(p=>({...p,...patch,edited:true,baseRevision:p.baseRevision??viewRef.current?.checkpoint.revision??null}));
  const write=async(generating:boolean)=>{
    if(!projectId||!viewRef.current||busyRef.current||disabled||unknown||conflict)return;
    if(!generating&&!draftRef.current.edited){setNotice('当前文档没有新修改，沿用已保存版本。');return;}
    const current=draftRef.current;if(generating?!current.prompt.trim():!current.title.trim()||!current.content.trim())return;
    const preserve=current.edited;busyRef.current=true;setBusy(true);onBusy(true);setError('');setNotice('');
    try{
      const before=new Set(viewRef.current.checkpoint.documents?.map(d=>`${d.id}:${d.revision}`));
      const result=await api<WorkflowView>(`/projects/${projectId}/workflow/documents${generating?'/generate':''}`,'POST',generating?
        {kind:current.kind,source:current.source,message:current.prompt.trim(),expectedRevision:viewRef.current.checkpoint.revision}:
        {id:current.id,kind:current.kind,title:current.title.trim(),content:current.content,expectedRevision:current.baseRevision??viewRef.current.checkpoint.revision});
      if(!alive.current)return;setView(result);viewRef.current=result;
      const doc=result.checkpoint.documents?.find(d=>!before.has(`${d.id}:${d.revision}`));
      if(!doc)throw new Error('请刷新记录核对保存结果。');
      setDraft(p=>generating&&preserve?{...p,prompt:p.prompt===current.prompt?'':p.prompt,baseRevision:result.checkpoint.revision}:{...p,id:doc.id,title:doc.title,content:doc.content,kind:doc.kind,prompt:generating&&p.prompt===current.prompt?'':p.prompt,edited:false,baseRevision:result.checkpoint.revision});
      setEditing(false);setNotice(generating?(preserve?'新生成稿已单独保存；你的手工修改仍保留。可保存原稿后从文档列表打开生成稿。':'已生成并保存草稿，请核对后使用。'):'修改已保存为新版本。');
      await onSaved(projectId);
    }catch(e){if(alive.current){const uncertain=!(e instanceof ApiError);setUnknown(uncertain);setConflictReady(false);setConflict(uncertain||(e instanceof ApiError&&e.status===409));setError((e instanceof Error?e.message:String(e))+(uncertain?'。请先刷新核对保存记录，原输入保留。':''));}}
    finally{busyRef.current=false;if(alive.current)setBusy(false);onBusy(false);}
  };
  useEffect(()=>{onRegisterSave(active?()=>write(false):null);});
  const documents=(view?.checkpoint.documents??[]).filter(d=>teaching?d.kind==='teaching':d.kind!=='teaching');
  const latest=documents.filter((d,i)=>!documents.slice(i+1).some(n=>n.id===d.id)).reverse();
  const open=(doc?:LearningDocument)=>{if(draftRef.current.edited){setError('先保存或导出当前手工修改，再打开其他文档。');return;}setDraft({...empty(teaching),...(doc?{id:doc.id,kind:doc.kind,title:doc.title,content:doc.content,source:doc.source}:{}),baseRevision:view?.checkpoint.revision??null});setEditing(!doc);setError('');};
  const locked=disabled||busy||!projectId||!view||unknown||conflict;
  const importFile=async(file?:File)=>{
    if(!file||!projectId||locked)return;busyRef.current=true;setBusy(true);onBusy(true);setError('');
    try{
      const input=await referenceFile(file,'成果档案/'+file.name);
      const previous=imports.find(r=>r.name===input.name);
      await api(`/projects/${projectId}/references`,'POST',{...input,mode:'off',expectedVersion:previous?.version??0});
      await refreshImports();await onSaved(projectId);setNotice('材料已归入成果档案，未自动提供给 AI。');
    }catch(e){const uncertain=!(e instanceof ApiError);setError((e instanceof Error?e.message:String(e))+(uncertain?'。请先刷新核对，勿重复导入。':''));if(uncertain)setUnknown(true);}
    finally{busyRef.current=false;if(alive.current)setBusy(false);onBusy(false);}
  };
  const fileName=(draft.title||labels[draft.kind]).replace(/[<>:"/\\|?*\x00-\x1f]/g,'_').slice(0,80);
  return <section hidden={!active} className={`learning-documents ${teaching?'teaching-documents':'archive-documents'}`} aria-label={teaching?'教学设计':'成果材料'}>
    <div className="document-request panel">
      <header><h2><BookOpen size={18}/>{teaching?'设计一次学习':'整理成果材料'}</h2><small>{teaching?'探索 · 造物 · 迭代':'海报 · 申报 · 日志'}</small></header>
      {!projectId?<div className="workflow-empty"><h3>从一个主题开始</h3><p>新建项目即可保存教案，不需要先准备硬件。</p><button className="primary" onClick={onNew}>新建项目</button></div>:<>
        {teaching?<fieldset disabled={busy||disabled}><legend>这次从哪里开始？</legend><label><input type="radio" name="teaching-source" checked={draft.source==='blank'} onChange={()=>setDraft(p=>({...p,source:'blank'}))}/>从空白主题开始</label><label><input type="radio" name="teaching-source" checked={draft.source==='project'} onChange={()=>setDraft(p=>({...p,source:'project'}))}/>基于当前作品设计</label></fieldset>:<label className="field">要准备什么？<select value={draft.kind} disabled={busy||draft.edited} onChange={e=>setDraft({...empty(false),kind:e.target.value as LearningDocumentKind,baseRevision:view?.checkpoint.revision??null})}>{Object.entries(labels).filter(([id])=>id!=='teaching').map(([id,label])=><option key={id} value={id}>{label}</option>)}</select></label>}
        <p className="muted">{teaching?(draft.source==='blank'?'说说主题、学生年级和课时，也可以补充已有基础。':'会参考当前已保存的作品目标、器件和实际记录。'): '按已保存的作品资料整理文案；参赛要求和实际结果由你补充核对。'}</p>
        <label className="field">{teaching?'教学想法':'材料要求'}<textarea aria-label={teaching?'教学想法':'材料要求'} rows={5} maxLength={4000} value={draft.prompt} disabled={busy||disabled} placeholder={teaching?'例如：初中七年级，用2课时探索感应开盖盒，学生初次接触传感器。':'例如：为课堂作品展示写海报文案，突出问题、做法和测试发现。'} onChange={e=>setDraft(p=>({...p,prompt:e.target.value}))}/></label>
        <button className="primary" disabled={locked||!draft.prompt.trim()} onClick={()=>void write(true)}>{busy?<LoaderCircle className="spin" size={16}/>:<Sparkles size={16}/>} {busy?'正在整理…':teaching?'生成教案大纲':'整理材料草稿'}</button>
        {teaching&&<details className="classroom-details"><summary>三阶六维怎样用在教案里？</summary><p>探索：创新、关心；造物：设计、合作；迭代：批判、成长。每阶段都有活动、教师追问和可观察证据，便于根据课堂实际调整。</p></details>}
        <div className="document-history"><h3>已保存文档</h3>{!latest.length&&<p className="muted">生成或手工保存后会出现在这里。</p>}{latest.map(d=><button key={d.id} aria-pressed={draft.id===d.id} disabled={busy} onClick={()=>open(d)}><FileText size={15}/><span>{d.title}</span><small>V{d.revision}</small></button>)}</div>
        {!teaching&&<div className="document-history"><h3>已有材料</h3><label className="reference-file-button">添加已有材料<input aria-label="添加成果材料" type="file" disabled={locked} accept=".txt,.md,.pdf,.docx,.csv" onChange={e=>{const file=e.target.files?.[0];e.target.value='';void importFile(file);}}/></label><p className="muted">支持文字、PDF 和 Word，单份1MB以内。图片可在下方“图片与日志”中添加。</p>{imports.map(r=><p key={r.id}>{r.name.slice('成果档案/'.length)} · V{r.version}</p>)}</div>}
      </>}
    </div>
    <div className="document-editor panel">
      <header><h2><FileText size={17}/>{teaching?'教案大纲':'成果文档'}</h2><button aria-label="刷新文档记录" disabled={busy||refreshing} onClick={()=>void refresh()}><RefreshCw size={16}/></button><button disabled={locked} onClick={()=>open()}><Plus size={16}/>空白文档</button></header>
      <div className="document-feedback" aria-live="polite">{error&&<p role="alert" className="chat-error">{error}</p>}{storageError&&<p role="alert">{storageError}</p>}{notice&&<p role="status">{notice}</p>}{conflict&&<><button disabled={busy||refreshing} onClick={()=>void refresh()}>刷新记录，保留草稿</button><button disabled={unknown||!view||busy||refreshing||!conflictReady} onClick={()=>{setDraft(p=>({...p,baseRevision:view!.checkpoint.revision}));setConflict(false);setError('');setNotice('已按最新记录继续编辑；原稿尚未覆盖或保存。');}}>已核对，继续编辑</button></>}</div>
      <div className="document-editor-scroll">
        {editing||draft.edited?<><label className="field">文档名称<input aria-label="文档名称" maxLength={100} value={draft.title} disabled={busy} onChange={e=>update({title:e.target.value})}/></label><label className="field">文档内容<textarea aria-label="文档内容" className="document-content-input" rows={20} maxLength={30000} value={draft.content} disabled={busy} onChange={e=>update({content:e.target.value})}/></label></>:draft.content?<>{draft.content.split('\n')[0]!=='# '+draft.title&&<h3>{draft.title}</h3>}<div className="document-preview">{draft.content.split('\n').map((line,i)=>line.startsWith('# ')?<h3 key={i}>{line.slice(2)}</h3>:line.startsWith('## ')?<h4 key={i}>{line.slice(3)}</h4>:<p key={i}>{line.replace(/^- /,'• ')||'\u00a0'}</p>)}</div></>:<div className="workflow-empty"><BookOpen size={32}/><h3>{teaching?'把一个主题变成可上课的方案':'让制作过程和成果留得下来'}</h3><p>{teaching?'生成后可以继续编辑，或直接从空白教案开始。':'选择材料类型，说明用途；也可以手工记录。'}</p><button disabled={locked} onClick={()=>open()}>手工编写</button></div>}
      </div>
      <footer><span role="status">{draft.edited?'手工修改尚未保存':draft.content?'已保存草稿 · 请核对后使用':'尚无文档'}</span>{!editing&&draft.content&&<button disabled={locked} onClick={()=>setEditing(true)}>编辑内容</button>}<button disabled={locked||!draft.edited||!draft.title.trim()||!draft.content.trim()} onClick={()=>void write(false)}><Save size={15}/>保存文档</button><button disabled={!draft.content} onClick={()=>download(fileName+'.md',draft.content,'text/markdown;charset=utf-8')}><Download size={15}/>导出文本</button><button disabled={!draft.content} onClick={()=>download(fileName+'.html',documentHtml(draft.title,draft.content),'text/html;charset=utf-8')}>打印版</button></footer>
    </div>
  </section>;
}
