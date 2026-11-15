import { useEffect, useMemo, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { LoaderCircle, RefreshCw, Save, Send, Settings, Sparkles, Upload, Wifi } from 'lucide-react';
import type { ChannelsCheckpoint, DevelopmentChannel } from '../../../packages/contracts/src/channels';
import type { HardwareDetail, HardwareSummary, Project, Version } from '../../../packages/contracts/src/platform';
import type { ControllerWorkspaceProps } from './ControllerWorkspace';
import { api } from './api';
import { mosaicoScope } from './controllerApi';
import { ChatCodingConnection, ChatCodingConversation, ChatCodingTask, useChatCoding } from './ChatCodingWorkspace';
import { ToolbarButton } from './ToolbarButton';
import { ProjectHardwareDialog } from './ProjectHardwareDialog';
import { BoardPicker } from './BoardPicker';
import { Dialog } from './Dialog';
import { HardwareDetails } from './HardwareDetails';
import { EngineeringModuleList } from './EngineeringUi';
import { ModuleCard } from './ModuleCard';
import { selectableModules } from './hardwareLibrary';
import { guideCode } from './moduleExamples';

const errorText = (error:unknown) => error instanceof Error ? error.message : String(error);
function projectView(pid:string, channel:DevelopmentChannel):Project {
  const version=channel.versions.at(-1)!;
  return {id:pid,name:channel.name,boardId:channel.boardId,componentIds:channel.componentIds,
    revision:channel.revision,updatedAt:version.createdAt,programmingMode:'chat-coding',
    hardwareRevisions:channel.hardwareRevisions,code:version.code,checksum:version.checksum,
    messages:channel.messages.map((item,index)=>({...item,id:`${channel.id}_${index}`}))};
}

/** The same Mosaico workflow, bound to a channel instead of the original board. */
export function MosaicoControllerWorkspace(props:ControllerWorkspaceProps) {
  const {projectId,channel,hardware,active,selected,mobileTab,actionsHost,connectionHost,modulesHost,dialogsHost,
    onSettings,onSaved,onActivity,onState,onChange,saveSelected,manageSelected,promptSelected,programsSelected,onHardwareSaved}=props;
  const key=`zhangwen-mosaico-controller:${projectId}:${channel.id}`;
  const restored=useRef((()=>{try{return JSON.parse(localStorage.getItem(key)??'null') as {name:string;boardId:string;componentIds:string[];task:string;baseRevision:number}|null;}catch{return null;}})()).current;
  const valid=restored&&typeof restored.name==='string'&&typeof restored.boardId==='string'&&Array.isArray(restored.componentIds)&&restored.componentIds.every(id=>typeof id==='string')&&typeof restored.task==='string'&&Number.isSafeInteger(restored.baseRevision)?restored:null;
  const [name,setName]=useState(valid?.name??channel.name),[boardId,setBoardId]=useState(valid?.boardId??channel.boardId);
  const [components,setComponents]=useState(valid?.componentIds??channel.componentIds),[task,setTask]=useState(valid?.task??channel.versions.at(-1)!.code);
  const [baseRevision,setBaseRevision]=useState(valid?.baseRevision??channel.revision);
  const [busy,setBusy]=useState(''),[chatBusy,setChatBusy]=useState(false),[error,setError]=useState('');
  const [managing,setManaging]=useState(false),[choosing,setChoosing]=useState(false),[picking,setPicking]=useState(false);
  const [pending,setPending]=useState<string[]>([]),[search,setSearch]=useState(''),[detail,setDetail]=useState<HardwareDetail|null>(null),[editExample,setEditExample]=useState(false);
  const board=hardware.find(item=>item.componentId===boardId);
  const hardwareDirty=name!==channel.name||boardId!==channel.boardId||JSON.stringify(components)!==JSON.stringify(channel.componentIds);
  const taskDirty=task!==channel.versions.at(-1)!.code;
  const current=useRef(channel); current.current=channel;
  const scope=useMemo(()=>mosaicoScope(projectId,channel.id,()=>current.current.revision),[projectId,channel.id]);
  const project=useMemo(()=>projectView(projectId,channel),[projectId,channel]);
  const callbacks=useRef({onActivity,onState,onChange,onSaved});callbacks.current={onActivity,onState,onChange,onSaved};
  const update=(value:DevelopmentChannel)=>{current.current=value;callbacks.current.onChange(value);setBaseRevision(value.revision);};
  const refresh=async()=>{
    const value=await api<ChannelsCheckpoint>(`/projects/${projectId}/channels`);
    const latest=value.channels.find(item=>item.id===channel.id);
    if(!latest)throw new Error('当前主控不存在。');
    update(latest);await callbacks.current.onSaved(projectId);
  };
  const saveChannel=async(hardwareOnly=false)=>{
    if(!hardwareDirty&&(hardwareOnly||!taskDirty)){await refresh();return projectView(projectId,current.current);}
    const value=await api<DevelopmentChannel>(`/projects/${projectId}/channels/${channel.id}`,'PUT',{
      expectedRevision:baseRevision,name,boardId,componentIds:components,code:hardwareOnly?channel.versions.at(-1)!.code:task});
    update(value);await callbacks.current.onSaved(projectId);return projectView(projectId,value);
  };
  const prepare=async()=>{
    if(hardwareDirty)await saveChannel(true);
    const prepared=await scope.client<Project>(`/projects/${projectId}`);
    current.current={...current.current,revision:prepared.revision};
    return prepared;
  };
  const chat=useChatCoding({active:true,project,task,unsaved:hardwareDirty||taskDirty,disabled:!!busy,
    onSaved:refresh,onBusy:setChatBusy,prepareProject:prepare,onProjectPrepared:()=>{},controllerScope:scope});
  const locked=!!busy||chatBusy;
  const dirty=hardwareDirty||taskDirty||chat.lua.hasUnsaved;
  const prompt=chat.source==='local'?chat.lua.prompt:task;
  const perform=async(label:string,work:()=>Promise<unknown>)=>{setBusy(label);setError('');try{await work();}catch(e){setError(errorText(e)+'；未自动重发。');}finally{setBusy('');}};
  const saveTask=()=>perform('保存任务',()=>saveChannel());
  const save=async()=>{
    if(locked)return;
    if(managing){await perform('保存器件选择',()=>saveChannel(true));return;}
    if(hardwareDirty){try{await saveChannel(true);}catch(e){setError(errorText(e));return;}}
    if(board?.programmingMode!=='chat-coding')return;
    if(chat.source==='local')await chat.lua.requestSave();else await saveTask();
  };
  useEffect(()=>{try{if(hardwareDirty||taskDirty)localStorage.setItem(key,JSON.stringify({name,boardId,componentIds:components,task,baseRevision}));else localStorage.removeItem(key);}catch{setError('浏览器草稿保存失败，请保存或复制当前内容。');}},[key,hardwareDirty,taskDirty,name,boardId,components,task,baseRevision]);
  useEffect(()=>{callbacks.current.onActivity(channel.id,locked||chat.device.state.connected||chat.state.connected);},[channel.id,locked,chat.device.state.connected,chat.state.connected]);
  useEffect(()=>()=>callbacks.current.onActivity(channel.id,false),[channel.id]);
  useEffect(()=>{if(selected)callbacks.current.onState({id:channel.id,name,boardId,componentIds:components,hardwareDirty,dirty,locked,status:error||busy||chat.lua.error||chat.error,prompt,source:chat.source==='device'?'device':'local'});},[selected,channel.id,name,boardId,components,hardwareDirty,dirty,locked,error,busy,chat.lua.error,chat.error,prompt,chat.source]);
  useEffect(()=>{
    if(!selected)return;
    const target={id:channel.id,read:()=>prompt,write:chat.source==='local'?chat.lua.setPrompt:setTask};promptSelected.current=target;
    return()=>{if(promptSelected.current===target)promptSelected.current=null;};
  },[selected,channel.id,prompt,chat.source,promptSelected]);
  useEffect(()=>{
    if(!selected)return;
    const programs=()=>{if(chat.source==='local')chat.lua.setSaveReview(true);};programsSelected.current=programs;
    const manage=()=>setManaging(true);manageSelected.current=manage;
    return()=>{if(programsSelected.current===programs)programsSelected.current=null;if(manageSelected.current===manage)manageSelected.current=null;};
  },[selected,chat.source,programsSelected,manageSelected]);
  useEffect(()=>{
    if(!active)return;
    const handler=async()=>{const dialog=document.activeElement?.closest('dialog');if(dialog&&!dialog.classList.contains('project-hardware-dialog'))return;await save();};
    saveSelected.current=handler;
    const shortcut=(event:KeyboardEvent)=>{if((event.ctrlKey||event.metaKey)&&event.key.toLowerCase()==='s'){event.preventDefault();void handler();}};
    window.addEventListener('keydown',shortcut);return()=>{window.removeEventListener('keydown',shortcut);if(saveSelected.current===handler)saveSelected.current=null;};
  });
  const openDetail=(item:HardwareSummary,edit=false)=>void perform('读取器件资料',async()=>{const value=await api<HardwareDetail>(`/hardware/${item.componentId}`);setDetail(value);setEditExample(edit);});
  const loadModule=(item:HardwareSummary)=>void perform('读取模块程序',async()=>{
    if(chat.source!=='local')throw new Error('请切换到Lua脚本编程，再载入模块程序。');
    const value=await api<HardwareDetail>(`/hardware/${item.componentId}`);
    const guide=value.moduleGuides?.find(v=>v.boardId===boardId);
    const code=value.localExamples?.find(v=>v.boardId===boardId)?.code??(guide?guideCode(guide):'');
    if(!code)throw new Error('此模块暂无当前主控的程序，请查看资料后描述需求。');
    if(chat.lua.hasUnsaved&&!window.confirm('载入模块程序会替换当前未保存手工稿，确定继续？'))return;
    chat.lua.returnToDraft();chat.lua.setDraft(code);props.onMobileTab('code');
  });
  const versions:Version[]=channel.versions.map(v=>({...v,source:'saved',programmingMode:'chat-coding',name:'设备任务'}));
  return <>
    {active&&actionsHost&&createPortal(<div className="tool-group" role="group" aria-label="设备操作">
      {chat.source==='local'?<><ToolbarButton icon={Save} label="保存代码" disabled={chat.lua.locked||!chat.lua.editorCode.trim()||chat.lua.saved} onClick={()=>void chat.lua.save()}/><ToolbarButton icon={Sparkles} label="生成代码" disabled={chat.lua.generateLocked||!chat.lua.prompt.trim()} onClick={()=>void chat.lua.generate()}/><ToolbarButton icon={Upload} label="上传运行" aria-label="上传并运行" disabled={!!chat.lua.uploadAndRunBlockedReason||hardwareDirty} onClick={()=>void chat.lua.uploadAndRun()}/></>:<><ToolbarButton icon={Send} label="发送任务" disabled={!chat.canSend} onClick={chat.send}/><ToolbarButton icon={RefreshCw} label="刷新回复" disabled={!chat.state.connected||chat.locked} onClick={()=>void chat.perform('读取设备回复','/sync')}/></>}
      <ToolbarButton icon={Settings} label="设备设置" disabled={locked} onClick={()=>{chat.device.chooseSection('status');props.onMobileTab('code');if(!chat.device.state.connected)chat.setConnectionOpen(true);}}/>
    </div>,actionsHost)}
    {active&&connectionHost&&createPortal(<button className={`connection toolbar-status ${chat.device.state.connected?'is-connected':''}`} disabled={locked} onClick={()=>chat.setConnectionOpen(true)}>{locked?<LoaderCircle size={17} className="spin"/>:<Wifi size={17}/>}<span>{chat.device.state.connected?'已连接 · 设置':'连接设备'}</span></button>,connectionHost)}
    {active&&modulesHost&&createPortal(<EngineeringModuleList boardId={boardId} hardware={hardware} componentIds={components} disabled={locked} chatCoding onDetail={openDetail} onEditExample={item=>openDetail(item,true)} onLoad={loadModule}/>,modulesHost)}
    {error&&<p className="chat-error" role="alert">{error}</p>}
    <ChatCodingConversation chat={chat} task={task} onTask={setTask} onSave={()=>void saveTask()} mobileTab={mobileTab} onSettings={onSettings}/>
    <ChatCodingTask chat={chat} task={task} versions={versions} selectedVersion={null} onVersion={revision=>{const version=channel.versions.find(v=>v.revision===revision);if(version&&(!taskDirty||window.confirm('载入历史任务会替换未保存任务，确定继续？')))setTask(version.code);}} mobileTab={mobileTab} saveState={dirty?'当前主控有未保存修改':'当前主控已保存'} folderError="" onRetryFolder={()=>void refresh()}/>
    {selected&&dialogsHost&&createPortal(<>
      {chat.connectionOpen&&<ChatCodingConnection chat={chat} onSave={()=>void saveTask()}/>}
      {managing&&<ProjectHardwareDialog controllerName={name} onControllerName={setName} boardId={boardId} board={board} componentIds={components} hardware={hardware} dirty={hardwareDirty} savedProject blocked={locked} error={error} busy={busy} onClose={()=>{if(!locked)setManaging(false);}} onChooseBoard={()=>{if(chat.device.state.connected||chat.state.connected){setError('请先断开此主控设备，再更换型号。');return;}setChoosing(true);}} onAdd={()=>{setPending([]);setSearch('');setPicking(true);}} onRemove={id=>setComponents(v=>v.filter(item=>item!==id))} onDetail={openDetail} onSave={()=>void perform('保存器件选择',()=>saveChannel(true))}/>}
      {choosing&&<BoardPicker boards={hardware.filter(v=>v.category==='MCU')} selected={boardId} onClose={()=>setChoosing(false)} onSelect={item=>{setBoardId(item.componentId);setChoosing(false);}} onHelp={()=>setChoosing(false)}/>}
      {picking&&<Dialog title="添加模块" className="sensor-picker-dialog" onClose={()=>setPicking(false)}><label>搜索硬件<input aria-label="搜索硬件" value={search} onChange={e=>setSearch(e.target.value)}/></label><div className="sensor-picker-list module-grid">{selectableModules(hardware).filter(item=>!search||`${item.displayName} ${item.componentId}`.toLowerCase().includes(search.toLowerCase())).map(item=><ModuleCard key={item.componentId} item={item} boardId={boardId} boards={hardware.filter(v=>v.category==='MCU')} added={components.includes(item.componentId)} checked={components.includes(item.componentId)||pending.includes(item.componentId)} disabled={components.includes(item.componentId)||components.length+pending.length>=32&&!pending.includes(item.componentId)} onToggle={checked=>setPending(v=>checked?[...v,item.componentId]:v.filter(id=>id!==item.componentId))} onDetail={()=>openDetail(item)}/>)}</div><button className="primary" disabled={!pending.length} onClick={()=>{setComponents(v=>[...v,...pending]);setPicking(false);}}>加入项目</button></Dialog>}
      {detail&&<HardwareDetails detail={detail} board={board} boards={hardware.filter(item=>item.category==='MCU')} editExample={editExample} onClose={()=>setDetail(null)} onSaved={value=>{setDetail(value);onHardwareSaved(value);}}/>}
    </>,dialogsHost)}
  </>;
}
