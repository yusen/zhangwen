import { useEffect, useRef, useState } from 'react';
import { Download, ImagePlus, LoaderCircle, RefreshCw, Settings } from 'lucide-react';
import type { GenerateProjectImage, ImageSettings, ProjectImages, ProjectImageKind } from '../../../packages/contracts/src/images';
import type { ProjectReference } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { Dialog } from './Dialog';
import { ImageSettingsDialog } from './ImageSettingsDialog';
import './projectImages.css';

const names={block:'线路方框图',concept:'项目方案图'};
const statuses={generating:'生成中',completed:'已生成',failed:'未生成',unknown:'结果未知'};
const mime=(r:ProjectReference)=>r.name.endsWith('.png')?'image/png':r.name.endsWith('.webp')?'image/webp':'image/jpeg';
const source=(r:ProjectReference)=>`data:${mime(r)};base64,${r.original}`;

export function ProjectImageDialog({projectId,projectName,onClose,onBusy,onSaved,hardwareDirty}:{
  projectId:string;projectName:string;onClose:()=>void;onBusy:(busy:boolean)=>void;onSaved:()=>Promise<void>;hardwareDirty:boolean;
}) {
  const [data,setData]=useState<ProjectImages>({jobs:[],references:[]});
  const [settings,setSettings]=useState<ImageSettings|null>(null),[showSettings,setShowSettings]=useState(false);
  const [kind,setKind]=useState<ProjectImageKind>('block');
  const [size,setSize]=useState<GenerateProjectImage['size']>('1536x1024');
  const [prompt,setPrompt]=useState(()=>{try{return localStorage.getItem('zw-image-prompt:'+projectId)??'';}catch{return '';}});
  const [selected,setSelected]=useState('');
  const [descriptions,setDescriptions]=useState<Record<string,string>>(()=>{try{const v:unknown=JSON.parse(localStorage.getItem('zw-image-descriptions:'+projectId)??'{}');return v&&typeof v==='object'&&!Array.isArray(v)?Object.fromEntries(Object.entries(v).filter(([k,t])=>/^ref_[a-f0-9]{32}$/.test(k)&&typeof t==='string'&&t.length<=12000)):{};}catch{return {};}});
  const [busy,setBusy]=useState(''),[error,setError]=useState(''),[notice,setNotice]=useState('');
  const mounted=useRef(true),working=useRef(false);
  const selectedRef=data.references.find(r=>r.id===selected);
  const description=selectedRef?(descriptions[selectedRef.id]??selectedRef.imageDescription??''):'';
  useEffect(()=>{mounted.current=true;return()=>{mounted.current=false;onBusy(false);};},[]);
  const load=async()=>{
    const [images,config]=await Promise.all([api<ProjectImages>(`/projects/${projectId}/images`),api<ImageSettings>('/settings/images')]);
    if(!mounted.current)return;
    setData(images);setSettings(config);
    setSelected(current=>images.references.some(r=>r.id===current)?current:images.references.at(-1)?.id||'');
  };
  useEffect(()=>{void load().catch(e=>setError(String(e)));},[projectId]);
  useEffect(()=>{try{localStorage.setItem('zw-image-descriptions:'+projectId,JSON.stringify(descriptions));}catch{setError('图示说明未能备份到浏览器，请先复制保留。');}},[descriptions,projectId]);
  useEffect(()=>{try{localStorage.setItem('zw-image-prompt:'+projectId,prompt);}catch{setError('画图要求未能备份到浏览器，请先复制保留。');}},[prompt,projectId]);
  const start=async()=>{
    if(working.current)return;working.current=true;setBusy('生成');onBusy(true);setError('');setNotice('');
    const request:GenerateProjectImage={requestId:crypto.randomUUID().replaceAll('-',''),kind,prompt:prompt.trim(),size};
    try {
      const value=await api<ProjectImages>(`/projects/${projectId}/images`,'POST',request);
      if(!mounted.current)return;setData(value);
      const job=value.jobs.find(j=>j.requestId===request.requestId);setNotice(job?.message??'请刷新图稿核对结果。');
      if(job?.referenceId)setSelected(job.referenceId);
      if(job?.status==='completed')await onSaved().catch(()=>{if(mounted.current)setError('图稿已保存在本机；项目文件夹同步未完成，请稍后保存项目。');});
    }catch(e){if(mounted.current)setError((e instanceof Error?e.message:'生成连接中断。')+' 没有自动重发。请刷新图稿与生成记录核对结果。');}
    finally{working.current=false;if(mounted.current)setBusy('');onBusy(false);}
  };
  const share=async()=>{
    if(!selectedRef||working.current)return;working.current=true;setBusy('保存');onBusy(true);setError('');setNotice('');
    try {
      const item=await api<ProjectReference>(`/projects/${projectId}/references`,'POST',{name:selectedRef.name,original:selectedRef.original,encoding:'base64',mode:'auto',expectedVersion:selectedRef.version,imageDescription:description});
      if(!mounted.current)return;
      setData(old=>({...old,references:old.references.map(r=>r.id===item.id?item:r)}));setDescriptions(old=>{const next={...old};delete next[item.id];return next;});setNotice('已保存核对后的图示说明，三师可参考这份文字；原图保留，未进行实物验证。');
      await onSaved().catch(()=>{if(mounted.current)setError('共用资料已保存，项目文件夹同步未完成，请稍后保存项目。');});
    }catch(e){if(mounted.current)setError((e instanceof Error?e.message:'保存结果未知。')+' 未自动重发，请刷新资料核对。');}
    finally{working.current=false;if(mounted.current)setBusy('');onBusy(false);}
  };
  if(showSettings)return <ImageSettingsDialog onClose={()=>{setShowSettings(false);void load().catch(e=>setError(String(e)));}}/>;
  return <Dialog title="生成项目图示" className="project-image-dialog" onClose={()=>{if(!working.current)onClose();}}>
    <p className="muted">{projectName} · 基于已保存资料画图，生成结果先保留为待核对图稿。</p>
    <div className="project-image-layout"><section aria-label="图示生成设置">
      <div className="project-image-kinds" role="group" aria-label="图示类型">{(['block','concept'] as const).map(k=><button key={k} disabled={!!busy} aria-pressed={kind===k} onClick={()=>setKind(k)}>{names[k]}</button>)}</div>
      <label className="field">画图要求<textarea data-dialog-autofocus rows={5} maxLength={4000} disabled={!!busy} value={prompt} onChange={e=>setPrompt(e.target.value)} placeholder={kind==='block'?'例如：画出传感器、主控、显示屏和电机的关系，用不同线型区分供电和信号，中文标注。':'例如：画出实验装置的整体布局，标出底座、运动部件和各主控的位置，采用教学方案示意风格。'}/></label>
      <label className="field">图片尺寸<select value={size} disabled={!!busy} onChange={e=>setSize(e.target.value as GenerateProjectImage['size'])}><option value="1536x1024">横向 · 1536 × 1024</option><option value="1024x1024">方形 · 1024 × 1024</option><option value="1024x1536">纵向 · 1024 × 1536</option></select></label>
      <button className="project-image-settings" disabled={!!busy} onClick={()=>setShowSettings(true)}><Settings size={16}/>{settings?.configured?`图片模型：${settings.model}`:'配置图片模型 API'}</button>
      <p className="muted">图片服务将收到画图要求，以及项目目标、全部主控与模块、实际条件、结构说明和相关资料文字。每次生成一张，可能产生图片服务用量。</p>
      {hardwareDirty&&<p role="status">器件有未保存修改，请先保存器件，再生成图示。</p>}
      <button className="primary project-image-generate" disabled={!!busy||!settings?.configured||!prompt.trim()||hardwareDirty||data.jobs.some(j=>j.status==='generating')} onClick={()=>void start()}>{busy==='生成'?<LoaderCircle size={17} className="spin"/>:<ImagePlus size={17}/>} {busy==='生成'?'图片生成中…':'生成图示'}</button>
      <p className="muted">图中文字、线路和尺寸需要核对。方框图表达功能关系，实际引脚与供电须查看器件资料。</p>
    </section><section className="project-image-preview" aria-label="图稿预览">
      {data.references.length>0&&<label className="field">已保存图稿<select disabled={!!busy} value={selected} onChange={e=>setSelected(e.target.value)}>{data.references.map((r,i)=><option key={r.id} value={r.id}>{i+1}. {r.name.split('/').at(-1)?.replace(/-[a-f0-9]{32}/,'')} · {r.mode==='off'?'待核对':'已加入资料'}</option>)}</select></label>}
      {selectedRef?<><a href={source(selectedRef)} download={selectedRef.name.split('/').at(-1)} title="下载已保存图片"><img src={source(selectedRef)} alt={selectedRef.imageDescription||'AI生成的项目概念图'}/></a><a className="project-image-download" href={source(selectedRef)} download={selectedRef.name.split('/').at(-1)}><Download size={16}/>下载图片</a><label className="field">图示说明（核对后供三师参考）<textarea rows={4} maxLength={12000} value={description} disabled={!!busy} onChange={e=>setDescriptions(old=>({...old,[selectedRef.id]:e.target.value}))}/></label><button disabled={!!busy||!description.trim()||(selectedRef.mode!=='off'&&description===selectedRef.imageDescription)} onClick={()=>void share()}>{busy==='保存'?'保存中…':selectedRef.mode==='off'?'核对后加入共用资料':'保存图示说明'}</button><small className="muted">请写明仍待确认的连接、型号和尺寸。三师读取已保存说明，不会自动分析原图。</small></>:<div className="project-image-empty"><ImagePlus size={36}/><p>{busy==='生成'?'图片服务正在生成，完成后显示在这里。':'生成后的图稿将在这里显示，可下载并核对说明。'}</p></div>}
    </section></div>
    {error&&<p role="alert" className="settings-error">{error}</p>}{notice&&<p role="status">{notice}</p>}
    <details className="classroom-details"><summary>生成记录 · {data.jobs.length} 次</summary>{data.jobs.map(job=><article className="project-image-job" key={job.requestId}><strong>{names[job.kind]} · {statuses[job.status]}</strong><small>{new Date(job.createdAt).toLocaleString()}</small><p>{job.prompt}</p><p>{job.message}</p><small>依据项目 V{job.source.projectRevision} / 学习记录 V{job.source.workflowRevision}</small></article>)}<p className="muted">超时或结果未知不会自动重发。再次点击生成会创建新请求，可能再次计费。</p></details>
    <div className="dialog-actions"><button disabled={!!busy} onClick={()=>{setError('');void load().catch(e=>setError(String(e)));}}><RefreshCw size={15}/>刷新图稿与记录</button><button disabled={!!busy} onClick={onClose}>关闭</button></div>
  </Dialog>;
}
