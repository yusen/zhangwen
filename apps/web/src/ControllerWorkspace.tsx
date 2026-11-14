import type { FolderBinding } from './projectFolders';
import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { createPortal } from 'react-dom';
import { AlignLeft, ArrowUp, CheckCheck, Download, History, LoaderCircle, MoreHorizontal, Search, Sparkles, Terminal, Undo2, Upload, X } from 'lucide-react';
import type { ChannelsCheckpoint, DevelopmentChannel, ChannelManifest } from '../../../packages/contracts/src/channels';
import type { CheckResult, CodeRepair, HardwareDetail, HardwareSummary, UploadReceipt, Version } from '../../../packages/contracts/src/platform';
import { api, ApiError } from './api';
import { ActionMenu } from './ActionMenu';
import { AssistantMessage } from './AssistantMessage';
import { UserMessage } from './UserMessage';
import { replyCode } from './assistantReply';
import { BoardArtwork } from './BoardArtwork';
import { BoardPicker } from './BoardPicker';
import { Editor, type EditorHandle } from './Editor';
import { Dialog } from './Dialog';
import { ProjectHardwareDialog } from './ProjectHardwareDialog';
import { HardwareDetails } from './HardwareDetails';
import { HardwareGuide, integrationPrompt } from './HardwareGuide';
import { IntegrationProgress } from './IntegrationProgress';
import { ModuleCard } from './ModuleCard';
import { ModuleFilters } from './ModuleFilters';
import { filterModules, selectableModules, type ModuleDirection } from './hardwareLibrary';
import { guideCode } from './moduleExamples';
import { PersonalModuleDialog } from './PersonalModuleDialog';
import { MicroPythonDevice, serialApi } from './serial';
import { latestBackup, persistBackup } from './backups';
import { ControllerSelfTest } from './ControllerSelfTest';
import { FirmwareDialog } from './FirmwareDialog';
import { MICROBIT_BOARD } from './controllerDiagnostics';
import { DeviceFilesDialog } from './DeviceFilesDialog';
import { EngineeringActions, EngineeringChatHeader, EngineeringComposer, EngineeringConnection, EngineeringFilebar, EngineeringModuleList } from './EngineeringUi';

export interface ControllerWorkspaceProps {
  folder:FolderBinding|null; projectId: string; channel: DevelopmentChannel; hardware: HardwareSummary[]; active: boolean; mobileTab: string;
  actionsHost: HTMLElement|null; connectionHost: HTMLElement|null; modulesHost: HTMLElement|null;
  configured: boolean; onSettings: () => void; fullscreen: boolean; onFullscreen: (value: boolean) => void; onMobileTab: (value: string) => void;
  onHardwareSaved: (value: HardwareDetail) => void;
  saveSelected: MutableRefObject<(() => Promise<void>) | null>; manageSelected: MutableRefObject<(() => void) | null>;
  programsSelected: MutableRefObject<(() => void) | null>;
  onState: (value: {id:string;dirty:boolean;locked:boolean;status:string}) => void;
  onChange: (value: DevelopmentChannel) => void; onSaved: (pid: string) => Promise<void>; onActivity: (id: string,value: boolean) => void;
}
const errorText=(error:unknown)=>error instanceof Error?error.message:String(error);
function download(name:string,value:string|Uint8Array){const url=URL.createObjectURL(new Blob([typeof value==='string'?value:new Uint8Array(value).buffer]));const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}

export function ControllerWorkspace({folder,projectId,channel,hardware,active,mobileTab,actionsHost,connectionHost,modulesHost,configured,onSettings,fullscreen,onFullscreen,onMobileTab,onHardwareSaved,saveSelected,manageSelected,programsSelected,onState,onChange,onSaved,onActivity}:ControllerWorkspaceProps){
  const key=`zhangwen-channel-draft:${projectId}:${channel.id}`;
  const saved=channel.versions.at(-1)!;
  const restored=useRef((()=>{try{const value=JSON.parse(localStorage.getItem(key)??'null');if(value&&typeof value.code==='string'&&typeof value.name==='string'&&typeof value.boardId==='string'&&Number.isSafeInteger(value.baseRevision)&&Array.isArray(value.componentIds)&&value.componentIds.every((id:unknown)=>typeof id==='string'))return value as {code:string;name:string;boardId:string;componentIds:string[];baseRevision:number};}catch{/* no draft */}return null;})()).current;
  const [code,setCode]=useState(restored?.code??saved.code),[name,setName]=useState(restored?.name??channel.name),[boardId,setBoardId]=useState(restored?.boardId??channel.boardId),[components,setComponents]=useState(restored?.componentIds??channel.componentIds),[baseRevision,setBaseRevision]=useState(restored?.baseRevision??channel.revision);
  const promptKey=key+':prompt';
  const [prompt,setPrompt]=useState(()=>{try{return localStorage.getItem(promptKey)??'';}catch{return '';}});
  const [preview,setPreview]=useState<string|null>(null),[selectedVersion,setSelectedVersion]=useState<number|null>(restored?null:saved.revision),[zoom,setZoom]=useState(100);
  const [busy,setBusy]=useState(''),[generating,setGenerating]=useState(false),[error,setError]=useState(''),[status,setStatus]=useState(''),[conflict,setConflict]=useState(false);
  const [check,setCheck]=useState<CheckResult|null>(null),[terminalOpen,setTerminalOpen]=useState(false),[log,setLog]=useState('尚未连接设备。'),[repl,setRepl]=useState('');
  const [receipt,setReceipt]=useState<UploadReceipt|null>(null),[runSubmitted,setRunSubmitted]=useState(false),[runAt,setRunAt]=useState<string|null>(null),[observed,setObserved]=useState('unconfirmed');
  const [selfTest,setSelfTest]=useState(false),[firmware,setFirmware]=useState(false),[flashing,setFlashing]=useState(false),[execution,setExecution]=useState(false),[files,setFiles]=useState<'board'|'programs'|null>(null),[history,setHistory]=useState(false);
  const [managing,setManaging]=useState(false),[choosingBoard,setChoosingBoard]=useState(false),[picking,setPicking]=useState(false),[pending,setPending]=useState<string[]>([]);
  const [search,setSearch]=useState(''),[brand,setBrand]=useState('all'),[direction,setDirection]=useState<ModuleDirection|'all'>('all'),[moduleType,setModuleType]=useState(''),[onlyPersonal,setOnlyPersonal]=useState(false),[personal,setPersonal]=useState(false);
  const [detail,setDetail]=useState<HardwareDetail|null>(null),[editExample,setEditExample]=useState(false),[sample,setSample]=useState<{item:HardwareSummary;code:string;base:string}|null>(null),[testTarget,setTestTarget]=useState<string|null>(()=>{
    try{const value=JSON.parse(localStorage.getItem(key+':integration')??'null');if(value&&value.boardId===boardId&&JSON.stringify(value.componentIds)===JSON.stringify(components))return typeof value.targetId==='string'&&components.includes(value.targetId)?value.targetId:null;}catch{/* use saved conversation */}
    const latest=channel.messages.filter(item=>(!item.boardId||item.boardId===boardId)&&JSON.stringify(item.componentIds)===JSON.stringify(components)).at(-1);return latest?.intent==='integration'&&latest.integrationModuleId&&components.includes(latest.integrationModuleId)?latest.integrationModuleId:null;
  });
  const device=useRef<MicroPythonDevice|null>(null),generation=useRef<AbortController|null>(null),editor=useRef<EditorHandle>(null),input=useRef<HTMLTextAreaElement>(null),importInput=useRef<HTMLInputElement>(null),messages=useRef<HTMLDivElement>(null);
  const [,redraw]=useState(0),callbacks=useRef({onActivity,onState});callbacks.current={onActivity,onState};
  const board=hardware.find(item=>item.componentId===boardId),state=device.current?.state??'disconnected',running=state==='running',attention=state==='attention';
  const locked=!!busy||generating||flashing||['busy','connecting'].includes(state),hardwareDirty=boardId!==channel.boardId||name!==channel.name||JSON.stringify(components)!==JSON.stringify(channel.componentIds),dirty=hardwareDirty||code!==saved.code;
  const visibleCode=preview??code,currentReceipt=receipt&&!dirty&&device.current?.receipt===receipt&&receipt.revision===channel.revision;
  const activeMessages=channel.messages.filter(item=>!item.boardId||item.boardId===boardId),pastMessages=channel.messages.filter(item=>item.boardId&&item.boardId!==boardId);
  const latestReply=activeMessages.filter(item=>item.role==='assistant').at(-1),latestReplyCode=latestReply?replyCode(latestReply.content):null;
  const versions:Version[]=channel.versions.map(value=>({...value,boardId:value.boardId??channel.boardId,source:'saved',name:'MicroPython 程序'}));
  const modules=selectableModules(hardware),available=filterModules(modules,brand,direction,moduleType,search).filter(item=>!onlyPersonal||item.personal);
  const modified=(value:string)=>{setCode(value);setSelectedVersion(null);setCheck(null);setReceipt(null);setRunSubmitted(false);setObserved('unconfirmed');};
  useEffect(()=>{try{if(dirty)localStorage.setItem(key,JSON.stringify({code,name,boardId,componentIds:components,baseRevision}));else localStorage.removeItem(key);}catch{setError('浏览器草稿保存失败，请保存或导出代码。');}},[key,dirty,code,name,boardId,components,baseRevision]);
  useEffect(()=>{try{if(prompt)localStorage.setItem(promptKey,prompt);else localStorage.removeItem(promptKey);}catch{setError('需求草稿未能保存在浏览器，请复制保留。');}},[promptKey,prompt]);
  useEffect(()=>{try{localStorage.setItem(key+':integration',JSON.stringify({boardId,componentIds:components,targetId:testTarget}));}catch{/* saved messages retain integration metadata */}},[key,boardId,components,testTarget]);
  useEffect(()=>{callbacks.current.onActivity(channel.id,locked||state!=='disconnected');},[channel.id,locked,state]);
  useEffect(()=>{if(active)callbacks.current.onState({id:channel.id,dirty,locked,status:error||busy||status});},[active,channel.id,dirty,locked,status,error,busy]);
  useEffect(()=>()=>{generation.current?.abort();void device.current?.disconnect();callbacks.current.onActivity(channel.id,false);},[channel.id]);
  useEffect(()=>{const warn=(event:BeforeUnloadEvent)=>{if(device.current&&device.current.state!=='disconnected'){event.preventDefault();event.returnValue='';}};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[]);
  useEffect(()=>{if(active)messages.current?.scrollTo({top:messages.current.scrollHeight});},[active,channel.messages.length,generating]);
  const action=async(label:string,task:()=>Promise<void>)=>{setBusy(label);setError('');try{await task();}catch(err){setError(errorText(err));if(err instanceof ApiError&&err.status===409)setConflict(true);}finally{setBusy('');}};
  const accept=(value:DevelopmentChannel)=>{onChange(value);setBaseRevision(value.revision);setConflict(false);};
  const save=async(value=code,hardwareOnly=false)=>{
    if(!hardwareDirty&&(hardwareOnly||value===saved.code)){await onSaved(projectId);setStatus('当前项目没有新修改，已保留上次保存内容。');return channel;}
    const next=await api<DevelopmentChannel>(`/projects/${projectId}/channels/${channel.id}`,'PUT',{expectedRevision:baseRevision,name,boardId,componentIds:components,code:hardwareOnly?saved.code:value});
    accept(next);setReceipt(null);setRunSubmitted(false);if(!hardwareOnly){setCode(value);setSelectedVersion(next.versions.at(-1)!.revision);if(preview===value)setPreview(null);}else if(code===next.versions.at(-1)!.code&&!preview)setSelectedVersion(next.versions.at(-1)!.revision);setStatus(`已保存 V${next.versions.at(-1)!.revision}；尚未上传。`);await onSaved(projectId);return next;
  };
  useEffect(()=>{
    if(!active)return;
    const handler=async()=>{if(locked)return;const dialog=document.activeElement?.closest('dialog');if(dialog&&!dialog.classList.contains('project-hardware-dialog'))return;await action('保存项目',async()=>{if(managing){if(hardwareDirty)await save(code,true);}else await save();});};
    const manage=()=>setManaging(true),programs=()=>setFiles('programs');saveSelected.current=handler;manageSelected.current=manage;programsSelected.current=programs;
    const shortcut=(event:KeyboardEvent)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();void handler();}};window.addEventListener('keydown',shortcut);
    return()=>{window.removeEventListener('keydown',shortcut);if(saveSelected.current===handler)saveSelected.current=null;if(manageSelected.current===manage)manageSelected.current=null;if(programsSelected.current===programs)programsSelected.current=null;};
  });
  const generate=async(preset?:string,target?:string)=>{
    const text=preset??prompt;if(locked||conflict||!text.trim())return;target=target??(testTarget&&components.includes(testTarget)?testTarget:undefined);
    setGenerating(true);setError('');const controller=new AbortController();generation.current=controller;
    try{
      const current=hardwareDirty?await save(code,true):channel;
      const value=await api<DevelopmentChannel>(`/projects/${projectId}/channels/${channel.id}/chat`,'POST',{expectedRevision:current.revision,message:text,code,...(target?{intent:'integration',integrationModuleId:target}:{})},controller.signal);
      accept(value);if(!preset)setPrompt(previous=>previous===text?'':previous);const candidate=replyCode(value.messages.at(-1)?.content??'');if(candidate!==null){setPreview(candidate);setSelectedVersion(null);onMobileTab('code');}if(target)setTestTarget(target);await onSaved(projectId);
    }catch(err){setError(errorText(err)+'；未自动重发。结果未知时先重新读取记录。');if(err instanceof ApiError&&err.status===409)setConflict(true);}finally{setGenerating(false);}
  };
  const connect=async()=>{
    const serial=serialApi();if(!serial){setError('请用电脑 Chrome 或 Edge 连接串口。');return;}
    const selected=serial.requestPort();
    await action('选择设备并检测固件',async()=>{const port=await selected;const next=new MicroPythonDevice(port,text=>setLog(previous=>(previous+text).slice(-24000)),()=>redraw(value=>value+1),8000,boardId);device.current=next;setReceipt(null);setRunSubmitted(false);try{await next.connect();setStatus('MicroPython 固件检测通过，设备已连接；可先进行主控自检。');}catch(err){device.current=null;throw err;}});
  };
  const run=async()=>{const target=device.current;if(!target)throw new Error('请先连接设备。');setRunSubmitted(false);await target.run();setRunAt(new Date().toISOString());setRunSubmitted(true);setStatus('运行命令已提交；实际效果待观察。');};
  const upload=async()=>{
    if(preview!==null){setStatus('请先点击「采用此代码」或「保存此版本」，再上传并运行；当前草稿仍保留。');onMobileTab('code');return;}
    setTerminalOpen(true);onMobileTab('code');if(state==='disconnected')await connect();if(device.current?.state!=='connected')return;
    await action('上传并运行',async()=>{const target=device.current!;const value=dirty?await save():channel;const manifest=await api<ChannelManifest>(`/projects/${projectId}/channels/${channel.id}/upload-manifest`,'POST',{expectedRevision:value.revision});
      if(manifest.channelId!==channel.id||manifest.projectId!==projectId||manifest.boardId!==boardId||manifest.files[0]?.content!==code||device.current!==target)throw new Error('清单、当前代码或设备已变化，未上传。');
      setReceipt(null);setRunSubmitted(false);setObserved('unconfirmed');const verified=await target.upload(manifest,data=>persistBackup({...data,projectId,channelId:channel.id}),(done,total)=>setStatus(`正在上传 ${done}/${total} bytes`));setReceipt(verified);await run();setStatus('main.py 上传回读一致，运行命令已提交。请查看终端和实物现象。');});
  };
  const showCode=(value:string)=>{setPreview(value);setCheck(null);onMobileTab('code');};
  const repair=(kind:'k10-screen'|'mpython-pins')=>void action('预览代码修复',async()=>{const value=await api<CodeRepair>(`/code/repair-${kind}`,'POST',{code:visibleCode,boardId,componentIds:components});showCode(value.code);setCheck(value.check);setStatus(value.summary);});
  const checkCode=()=>void action('检查代码',async()=>{setCheck(await api<CheckResult>('/check','POST',{code:visibleCode,boardId,componentIds:components}));});
  const openDetail=(item:HardwareSummary,edit=false)=>void action('读取资料',async()=>{setDetail(await api<HardwareDetail>('/hardware/'+item.skillName));setEditExample(edit);});
  const loadSample=(item:HardwareSummary)=>void action('读取模块示例',async()=>{const detail=await api<HardwareDetail>('/hardware/'+item.skillName);const local=detail.localExamples?.find(value=>value.boardId===boardId),guide=detail.moduleGuides?.find(value=>value.boardId===boardId);const files=detail.files.filter(file=>file.path.startsWith('examples/'));const value=local?.code.trim()||(guide?guideCode(guide,local?.setup):detail.moduleGuides?.length?'':files.find(file=>file.path.endsWith('.py'))?.content||files.flatMap(file=>[...file.content.matchAll(/```(?:python|micropython|py)\s*\n([\s\S]*?)```/g)].map(match=>match[1]))[0]);if(!value?.trim())throw new Error('此模块尚无当前主控的 Python 示例，请查看完整资料。');setSample({item,code:value.trimEnd()+'\n',base:code});});
  const startTest=(target=components[0])=>{if(target)void generate(integrationPrompt(board,boardId,components,hardware,target),target);};
  const fillReply=(value:string)=>{setPrompt(previous=>(previous.trim()?previous+'\n'+value:value).slice(0,4000));input.current?.focus();};
  const loadCode=(value:string,sourceBoard?:{id:string;name:string})=>{if(sourceBoard&&sourceBoard.id!==boardId&&!window.confirm('此版本来自其他主控。仅将代码载入草稿，当前主控不变；确认继续核对吗？'))return;if(dirty&&!window.confirm('用此程序替换未保存的手工草稿？请先保存或导出需要保留的内容。'))return;setPreview(null);modified(value);onMobileTab('code');};
  const canRun=!!currentReceipt&&state==='connected';
  const actions=<EngineeringActions boardId={boardId} uploadDisabled={locked||running||attention||conflict} runDisabled={locked||attention||!(running||canRun)} checkDisabled={locked||running} firmwareDisabled={locked||state!=='disconnected'} running={running} attention={attention} terminalOpen={terminalOpen} reason={attention?'连接已中断，请先断开并重新连接。':'请连接当前主控并上传校验当前程序。'} onUpload={()=>void upload()} onRun={()=>{setTerminalOpen(true);onMobileTab('code');void action(running?'停止':'运行',async()=>{if(running)await device.current?.stop();else await run();});}} onTerminal={()=>{setTerminalOpen(value=>!value);onMobileTab('code');}} onSelfTest={()=>setSelfTest(true)} onFirmware={()=>setFirmware(true)}/>;
  const connections=<EngineeringConnection state={state} disabled={locked} filesActive={files==='board'} onFiles={()=>setFiles('board')} onConnect={()=>{if(state==='disconnected'){setTerminalOpen(true);onMobileTab('code');void connect();}else void action('断开设备',async()=>{await device.current?.disconnect();device.current=null;setReceipt(null);setRunSubmitted(false);redraw(value=>value+1);});}}/>;
  const moduleList=<EngineeringModuleList boardId={boardId} hardware={hardware} componentIds={components} disabled={locked} onDetail={openDetail} onEditExample={item=>openDetail(item,true)} onLoad={loadSample}/>;
  return <>{active&&actionsHost&&createPortal(actions,actionsHost)}{active&&connectionHost&&createPortal(connections,connectionHost)}{active&&modulesHost&&createPortal(moduleList,modulesHost)}
    <section className={`ai-panel panel mobile-${mobileTab==='ai'?'show':'hide'}`}>
      <EngineeringChatHeader configured={configured} disabled={locked} onSettings={onSettings}/>
      <div ref={messages} className="messages" role="log" aria-label="掌问对话记录">
        {!activeMessages.length&&!components.length&&<section className="conversation-board-context" aria-label="当前主控对话"><BoardArtwork board={board}/><div><strong>{board?.displayName}</strong><p>告诉我想让作品做什么，或把遇到的问题发给我。</p></div></section>}
        {!!components.length&&<section className="message assistant hardware-guide" aria-label="掌问硬件引导"><HardwareGuide key={JSON.stringify([boardId,components])} board={board} componentIds={components} hardware={hardware} disabled={locked} onTest={()=>startTest()} onDevelop={()=>{setTestTarget(null);input.current?.focus();}}/></section>}
        {!activeMessages.length&&!components.length&&<div className="conversation-empty"><span><Sparkles size={24} strokeWidth={1.6}/></span><p>描述你的想法，或粘贴需要分析的代码与报错。</p></div>}
        {!!pastMessages.length&&<details className="past-board-conversations"><summary>之前主控的对话 · {pastMessages.length} 条</summary>{pastMessages.map((item,index)=><article className={`message ${item.role}`} key={index}><strong>{hardware.find(board=>board.componentId===item.boardId)?.displayName} · {item.role==='user'?'你':'掌问'}</strong><pre>{item.content}</pre></article>)}</details>}
        {activeMessages.map((item,index)=><article className={`message ${item.role}`} key={index}><strong>{item.role==='user'?'你':'掌问'}</strong>{item.role==='assistant'?<AssistantMessage content={item.content} disabled={locked} onCode={showCode} onReply={item===latestReply?fillReply:undefined} hasProgram={!!visibleCode.trim()} isCurrentCode={replyCode(item.content)?.trimEnd()===visibleCode.trimEnd()}/>:<UserMessage content={item.content}/>}</article>)}
        {generating&&<div className="ai-progress"><p className="muted" role="status"><LoaderCircle size={16} className="spin"/>正在等待模型回答…</p><button onClick={()=>generation.current?.abort()}>取消生成</button></div>}
      </div>
      {testTarget&&components.includes(testTarget)&&<IntegrationProgress state={{targetId:testTarget,index:components.indexOf(testTarget),total:components.length,nextId:components[components.indexOf(testTarget)+1]??null}} componentIds={components} hardware={hardware} disabled={locked} onSelect={startTest} onDevelop={()=>setTestTarget(null)}/>}
      {error&&<p className="chat-error" role="alert">{error}</p>}
      {conflict&&<button disabled={locked} onClick={()=>void action('读取并核对最新基线',async()=>{const state=await api<ChannelsCheckpoint>(`/projects/${projectId}/channels`);const next=state.channels.find(item=>item.id===channel.id);if(!next)throw new Error('主控记录不存在。');if(window.confirm('保留当前草稿，采用最新保存基线？请核对双方修改。'))accept(next);})}>读取并核对最新基线</button>}
      {status&&<p className="chat-hint" role="status">{status}</p>}
      <EngineeringComposer inputRef={input} value={prompt} onChange={setPrompt} onSend={()=>void generate()} disabled={locked||conflict} generating={generating}/>
    </section>
    <section className={`code-panel panel mobile-${mobileTab==='code'?'show':'hide'}`}>
      <EngineeringFilebar zoom={zoom} fullscreen={fullscreen} onZoom={setZoom} onFullscreen={()=>onFullscreen(!fullscreen)} versions={<select className="code-version-select" aria-label="代码历史版本" disabled={locked} value={preview!==null?'preview':selectedVersion??'draft'} onChange={event=>{if(event.target.value==='draft'){setPreview(null);return;}const value=channel.versions.find(item=>item.revision===Number(event.target.value));if(value&&(!dirty||window.confirm('将历史代码载入当前草稿？未保存代码将被替换，请先保存或导出。'))){setPreview(null);modified(value.code);setSelectedVersion(value.revision);}}}><option value="draft" disabled={preview===null}>未保存草稿</option>{preview!==null&&<option value="preview">AI生成稿 · 未保存</option>}{versions.slice().reverse().map(version=><option key={version.revision} value={version.revision}>V{version.revision} · MicroPython 程序 · 已保存{version.boardId&&version.boardId!==boardId?' · 其他主控':''}</option>)}</select>} tools={<ActionMenu label="代码工具" align="right" disabled={locked} items={[
        {label:'导入程序…',icon:Upload,onSelect:()=>importInput.current?.click()},
        {label:'导出当前程序',icon:Download,onSelect:()=>download('main.py',visibleCode)},
        {label:'整理缩进',icon:AlignLeft,group:'代码排版',disabled:preview!==null||!code.length,onSelect:()=>editor.current?.formatIndentation()},
        {label:'撤销编辑',icon:Undo2,disabled:preview!==null,shortcut:'Ctrl / ⌘ + Z',onSelect:()=>editor.current?.undo()},
        {label:'检查代码',icon:CheckCheck,group:'检查与记录',onSelect:checkCode},
        {label:'查看执行记录',icon:Terminal,onSelect:()=>setExecution(true)},
        {label:'管理版本',icon:History,group:'历史版本',onSelect:()=>setHistory(true)},
      ]}><MoreHorizontal size={18}/></ActionMenu>}/>
      <input ref={importInput} className="sr-only" type="file" accept=".py,text/x-python" aria-label="导入 Python 程序" onChange={event=>{const file=event.target.files?.[0];event.target.value='';if(file)void action('导入程序',async()=>{if(file.size>65536)throw new Error('程序不能超过65536字节。');const text=new TextDecoder('utf-8',{fatal:true}).decode(await file.arrayBuffer());if(text.includes('\0'))throw new Error('程序不能包含NUL。');loadCode(text);});}}/>
      {latestReplyCode!==null&&<div className="code-source-note" role="note" aria-label="代码与回复对应">{latestReplyCode.trimEnd()===visibleCode.trimEnd()?'右侧代码与最新回复一致。':<><span>右侧代码与最新回复不同。</span><button disabled={locked} onClick={()=>showCode(latestReplyCode)}>查看最新回复代码</button></>}</div>}
      {preview!==null&&<section className="code-preview-banner" aria-label="AI代码生成稿预览"><div><strong>AI生成稿 · 尚未保存</strong><small>{dirty?'原手工草稿已保留，可随时返回。':'原保存版本保留在历史中。'}</small></div><button disabled={locked} onClick={()=>{if(dirty&&preview!==code&&!window.confirm('用此生成稿替换未保存的手工草稿？可先返回原稿保存或导出。'))return;modified(preview);setPreview(null);}}>采用此代码</button><button disabled={locked} onClick={()=>{setPreview(null);setCheck(null);}}>返回原稿</button><button className="primary" disabled={locked} onClick={()=>void action('保存此版本',async()=>{if(dirty&&preview!==code&&!window.confirm('保存此生成稿会替换当前手工草稿。先返回原稿保存，或确认继续？'))return;await save(preview);})}>保存此版本</button></section>}
      <Editor ref={editor} zoom={zoom} readOnly={locked||preview!==null} value={visibleCode} onChange={modified}/>
      {check&&<section className="check-results" aria-label="检查结果"><div><strong>{check.valid?'静态检查完成':'检查发现问题'}</strong><button disabled={locked} onClick={checkCode}>重新检查</button><button className="icon-button" aria-label="关闭检查" onClick={()=>setCheck(null)}><X size={16}/></button></div>{check.diagnostics.some(item=>item.repair==='k10-screen')&&<button disabled={locked} onClick={()=>repair('k10-screen')}>预览屏幕修复</button>}{check.diagnostics.some(item=>item.repair==='mpython-pins')&&<button disabled={locked} onClick={()=>repair('mpython-pins')}>按P号预览修复</button>}{check.diagnostics.map((item,index)=><p className={`diagnostic ${item.severity.toLowerCase()}`} key={index}>{item.severity==='PASS'?'通过 · ':item.severity==='FAIL'?'错误 · ':'提示 · '}{item.line?`第 ${item.line} 行 · `:''}{item.message}</p>)}</section>}
      <section className="terminal-panel" hidden={!terminalOpen}><div className="terminal-head"><h3><Terminal size={17}/>REPL</h3><span>{running?'正在执行 · 发送会先中断':state==='connected'?'设备已连接':attention?'连接需核对':'未连接'}</span><button disabled={locked} onClick={()=>setLog('')}>清空</button><button onClick={()=>void action('导出设备备份',async()=>{const value=await latestBackup({projectId,channelId:channel.id});if(!value)throw new Error('尚无设备备份。');if(value.bytes)download('main-before-upload.py',value.bytes);else setStatus('上次上传前设备不存在 main.py，无需恢复旧文件。');})}>备份</button><button aria-label="收起终端" onClick={()=>setTerminalOpen(false)}><X size={16}/></button></div><pre className="serial-log" aria-label="串口输出">{log}</pre><details className="terminal-commands"><summary>高级：发送设备命令</summary><form className="repl-form" onSubmit={event=>{event.preventDefault();const command=repl;if(locked||!command.trim()||attention)return;void(async()=>{if(state==='disconnected')await connect();if(!device.current||!['connected','running'].includes(device.current.state))return;await action('发送设备命令',async()=>{const target=device.current!;if(target.state==='running')await target.stop();await target.repl(command);setReceipt(null);setRunSubmitted(false);setRepl('');});})();}}><span aria-hidden="true">&gt;&gt;&gt;</span><input aria-label="REPL 命令" value={repl} maxLength={4000} onChange={event=>setRepl(event.target.value)} placeholder={running?'输入命令，发送时先中断当前程序':state==='connected'?'输入命令，按 Enter 发送':'输入命令，发送时选择并连接设备'} onKeyDown={event=>{if(event.ctrlKey&&event.key.toLowerCase()==='c'&&event.currentTarget.selectionStart===event.currentTarget.selectionEnd&&running&&!locked){event.preventDefault();void action('中断程序',async()=>{await device.current?.stop();});}}} disabled={locked}/><button disabled={locked||!repl.trim()||attention} aria-label="发送 REPL 命令"><ArrowUp size={17}/></button></form></details></section>
    </section>
    {managing&&<ProjectHardwareDialog controllerName={name} onControllerName={setName} boardId={boardId} board={board} componentIds={components} hardware={hardware} dirty={hardwareDirty} savedProject blocked={locked} error={error} busy={busy} onClose={()=>{if(!locked)setManaging(false);}} onChooseBoard={()=>{if(state!=='disconnected'){setError('请先断开当前设备，再更换主控型号。');return;}setChoosingBoard(true);}} onAdd={()=>{setPending([]);setSearch('');setPicking(true);}} onRemove={id=>setComponents(previous=>previous.filter(value=>value!==id))} onDetail={openDetail} onSave={()=>void action('保存器件选择',async()=>{await save(code,true);})}/>}
    {choosingBoard&&<BoardPicker boards={hardware.filter(item=>item.programmingMode!=='chat-coding')} selected={boardId} onClose={()=>setChoosingBoard(false)} onSelect={item=>{setBoardId(item.componentId);setReceipt(null);setRunSubmitted(false);setTestTarget(null);setChoosingBoard(false);}} onHelp={()=>{setChoosingBoard(false);setStatus('请按实际主控选择型号；原代码和历史继续保留，须重新核对兼容性。');}}/>}
    {picking&&<Dialog title="添加模块" className="sensor-picker-dialog" onClose={()=>setPicking(false)} headerActions={<><div className="catalog-search picker-search"><Search size={17}/><input data-dialog-autofocus aria-label="搜索硬件" placeholder="搜索名称、型号或功能…" value={search} onChange={event=>setSearch(event.target.value)}/></div><ModuleFilters items={modules} brand={brand} direction={direction} type={moduleType} onBrand={setBrand} onType={(value,type)=>{setDirection(value);setModuleType(type);}} onClear={()=>{setSearch('');setBrand('all');setDirection('all');setModuleType('');}}/></>}><div className="sensor-picker-context"><strong>多品牌模块库</strong><span>当前主控：{board?.displayName}</span></div><div className="reference-actions"><button className="primary" onClick={()=>{setPicking(false);setPersonal(true);}}>新建我的模块</button><label><input type="checkbox" checked={onlyPersonal} onChange={event=>setOnlyPersonal(event.target.checked)}/>只看我的模块</label></div><p className="catalog-result-count">找到 {available.length} 个模块 · 可跨品牌选择，接线与驱动需单独核对</p><div className="sensor-picker-list module-grid">{available.map(item=><ModuleCard key={item.componentId} item={item} boardId={boardId} boards={hardware.filter(value=>value.category==='MCU')} added={components.includes(item.componentId)} checked={components.includes(item.componentId)||pending.includes(item.componentId)} disabled={locked||components.includes(item.componentId)||(!pending.includes(item.componentId)&&components.length+pending.length>=32)} onToggle={checked=>setPending(previous=>checked?[...previous,item.componentId]:previous.filter(id=>id!==item.componentId))} onDetail={()=>openDetail(item)}/>)}</div><div className="sensor-picker-actions"><span>已选择 {pending.length} 个</span><button onClick={()=>setPicking(false)}>取消</button><button className="primary" aria-label="加入所选模块" disabled={!pending.length||locked} onClick={()=>{setComponents(previous=>[...new Set([...previous,...pending])]);setCheck(null);setReceipt(null);setTestTarget(null);setPicking(false);onMobileTab('ai');}}>加入 {pending.length} 个模块</button></div></Dialog>}
    {personal&&<PersonalModuleDialog boardId={boardId} boards={hardware.filter(item=>item.category==='MCU')} source="" onClose={()=>setPersonal(false)} onCreated={value=>{onHardwareSaved(value);setComponents(previous=>previous.length<32?[...previous,value.componentId]:previous);setPersonal(false);setDetail(value);}}/>}
    {detail&&<HardwareDetails detail={detail} board={board} boards={hardware.filter(item=>item.category==='MCU')} editExample={editExample} onSaved={value=>{setDetail(value);onHardwareSaved(value);setCheck(null);}} onClose={()=>setDetail(null)}/>}
    {sample&&<Dialog title={`载入模块：${sample.item.displayName}`} onClose={()=>setSample(null)}><p className="muted">示例来自当前主控的硬件资料包；载入后仍需保存并显式上传。</p><pre className="candidate-code">{sample.code}</pre><button className="primary" onClick={()=>{if(code!==sample.base&&!window.confirm('预览后代码已改变，仍用此示例替换当前草稿吗？'))return;loadCode(sample.code);setSample(null);}}>替换当前代码</button></Dialog>}
    {selfTest&&<ControllerSelfTest scope={`${projectId}:${channel.id}`} boardId={boardId} device={device.current} onClose={()=>setSelfTest(false)} onLoadCode={loadCode}/>}
    {firmware&&board&&(boardId===MICROBIT_BOARD?<Dialog title="micro:bit 固件准备" onClose={()=>setFirmware(false)}><p>先备份设备上的旧程序，再使用官方 Python 编辑器为实际 V1/V2 主控准备 MicroPython。完成后回到掌问连接串口，运行主控自检，再上传 main.py。</p><a href="https://python.microbit.org/v/3" target="_blank" rel="noreferrer">打开官方 micro:bit Python 编辑器</a><p className="muted">掌问不会自动刷写 HEX。main.py 上传前备份并完整回读；写入中断后须重连核对，不自动重发。</p></Dialog>:<FirmwareDialog board={board} onClose={()=>setFirmware(false)} onBusy={setFlashing}/>)}
    {files&&<DeviceFilesDialog view={files} device={device.current} connected={state==='connected'} code={visibleCode} versions={versions} disabled={locked} onClose={()=>setFiles(null)} onLoad={loadCode} onDownload={download} onHistory={()=>{setFiles(null);setHistory(true);}} folder={folder} controller={{id:channel.id,name:channel.name,revision:channel.revision}} board={board} componentIds={components} programReceipt={currentReceipt?receipt:null} programRun={runSubmitted&&currentReceipt&&runAt?{projectId,revision:receipt!.revision,boardId,sha256:receipt!.sha256,submittedAt:runAt}:null} onChooseFolder={()=>setStatus('此主控随当前项目文件夹统一保存。')}/>}
    {history&&<Dialog title="保存的代码版本" onClose={()=>setHistory(false)}><p className="muted">选择版本载入草稿；再次保存创建新版本，历史保持。</p>{versions.slice().reverse().map(version=><article className="version-row" key={version.revision}><div><strong>V{version.revision} · MicroPython 程序</strong><small>{new Date(version.createdAt).toLocaleString()}</small></div><button onClick={()=>{loadCode(version.code);setHistory(false);}}>载入代码</button><button onClick={()=>download(`main-v${version.revision}.py`,version.code)}>导出</button></article>)}</Dialog>}
    {execution&&<Dialog title="本次执行结果" onClose={()=>setExecution(false)}><p>{dirty?'当前修改尚未上传校验。':'以下记录仅对应当前已保存版本。'}</p><p>{currentReceipt?`V${receipt!.revision} · 上传回读一致`:'当前版本尚无有效上传回读记录'}</p><p>{runSubmitted&&currentReceipt?'运行命令已提交':'尚无当前版本的运行提交记录'} · 实物结果待观察</p><label>实际观察<select aria-label="通道实际观察" value={observed} disabled={!runSubmitted||!currentReceipt} onChange={event=>setObserved(event.target.value)}><option value="unconfirmed">待观察</option><option value="passed">符合预期</option><option value="failed">存在异常</option></select></label><details><summary>备份与恢复</summary><p>备份按主控隔离；载入只恢复为草稿，不会操作设备。</p><button disabled={locked} onClick={()=>void action('读取备份',async()=>{const value=await latestBackup({projectId,channelId:channel.id});if(!value?.bytes)throw new Error('此主控暂无可恢复的旧 main.py。');loadCode(new TextDecoder('utf-8',{fatal:true}).decode(value.bytes));setExecution(false);setStatus('已载入上传前备份；尚未保存或上传。');})}>将此通道备份载入编辑器</button></details></Dialog>}
  </>;
}
