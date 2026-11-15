import type { FolderBinding } from './projectFolders';
import { useEffect, useRef, useState, type MutableRefObject } from 'react';
import { createPortal } from 'react-dom';
import { BookOpen, Plus } from 'lucide-react';
import type { ChannelsCheckpoint, DevelopmentChannel } from '../../../packages/contracts/src/channels';
import type { HardwareDetail, HardwareSummary } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { BoardArtwork } from './BoardArtwork';
import { BoardPicker } from './BoardPicker';
import { ControllerWorkspace, type ControllerContext, type ControllerPrompt } from './ControllerWorkspace';
import { MosaicoControllerWorkspace } from './MosaicoControllerWorkspace';
import './development-channels.css';

const message = (err: unknown) => err instanceof Error ? err.message : String(err);
const initialCode = '# 此主控独立保存、连接和上传。\nprint("你好，掌问！")\n';

export function DevelopmentChannels({ folder, projectId, mainBoard, hardware, engineeringActive, programsSelected, promptSelected, onState, selectorHost, workspaceHost, actionsHost, connectionHost, modulesHost,dialogsHost, configured, onSettings, fullscreen, onFullscreen, onMobileTab, onHardwareSaved, mobileTab, onSaved, onActivity, onSelection, onShared, onManageMain, saveSelected }: {
  folder:FolderBinding|null; projectId: string; mainBoard: string; hardware: HardwareSummary[]; engineeringActive:boolean; programsSelected:MutableRefObject<(()=>void)|null>; promptSelected:MutableRefObject<ControllerPrompt|null>; onState:(value:ControllerContext)=>void;
  selectorHost: HTMLElement | null; workspaceHost: HTMLElement | null; mobileTab: string;
  actionsHost: HTMLElement|null; connectionHost: HTMLElement|null; modulesHost: HTMLElement|null; dialogsHost:HTMLElement|null;
  configured: boolean; onSettings: () => void; fullscreen: boolean; onFullscreen: (value:boolean)=>void; onMobileTab: (value:string)=>void;
  onHardwareSaved: (value:HardwareDetail)=>void;
  onSaved: (pid: string) => Promise<void>; onActivity: (value: boolean) => void;
  onSelection: (channel: DevelopmentChannel | null) => void; onShared: () => void; onManageMain: () => void;
  saveSelected: MutableRefObject<(() => Promise<void>) | null>;
}) {
  const [channels, setChannels] = useState<DevelopmentChannel[]>([]);
  const [selected, setSelected] = useState('');
  const [multi, setMulti] = useState(false);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [boardId, setBoardId] = useState('');
  const [choosingBoard,setChoosingBoard]=useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [ready, setReady] = useState(false);
  const [readAttempt, setReadAttempt] = useState(0);
  const activity = useRef(new Set<string>());
  const manageSelected=useRef<(()=>void)|null>(null);
  const callbacks = useRef({ onActivity, onSelection }); callbacks.current = { onActivity, onSelection };
  const activityChanged = (id: string, active: boolean) => { if (active) activity.current.add(id); else activity.current.delete(id); callbacks.current.onActivity(activity.current.size > 0); };
  useEffect(() => {
    const controller = new AbortController(); setError('');
    void api<ChannelsCheckpoint>(`/projects/${projectId}/channels`, 'GET', undefined, controller.signal).then(value => {
      setChannels(value.channels); setMulti(value.channels.length > 0); setReady(true);
    }).catch(err => { if (!controller.signal.aborted) setError(message(err)); });
    return () => controller.abort();
  }, [projectId,readAttempt]);
  useEffect(() => { callbacks.current.onSelection(channels.find(channel => channel.id === selected) ?? null); }, [channels,selected]);
  useEffect(() => () => { callbacks.current.onActivity(false); }, []);
  useEffect(() => { activityChanged('__create', busy); }, [busy]);
  const update = (value: DevelopmentChannel) => setChannels(previous => previous.map(item => item.id === value.id ? value : item));
  const boards = hardware.filter(item => item.category === 'MCU');
  const main = hardware.find(item => item.componentId === mainBoard);
  const selector = <section className="project-controller-selector" aria-label="项目主控选择">
    <div className="controller-mode"><span className="board-field-label">项目主控</span><select aria-label="主控开发模式" value={multi ? 'multiple' : 'single'} disabled={!ready || busy} onChange={event => {
      if (event.target.value === 'single' && activity.current.size) { setError('请先停止操作并断开各主控设备，再切换单主控显示。'); return; }
      setError(''); const value = event.target.value === 'multiple'; setMulti(value); if (!value) { setSelected(''); setCreating(false); }
    }}><option value="single">单主控</option><option value="multiple">多主控</option></select></div>
    <div className="controller-peer-list" role="tablist" aria-label="项目主控" aria-orientation="vertical" onKeyDown={event => {
      if (!(event.target instanceof HTMLElement) || event.target.getAttribute('role') !== 'tab' || !['ArrowUp','ArrowDown','Home','End'].includes(event.key)) return;
      const tabs=Array.from(event.currentTarget.querySelectorAll<HTMLButtonElement>('[role=tab]')); const index=tabs.indexOf(event.target as HTMLButtonElement);
      const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(event.key==='ArrowDown'?1:-1)+tabs.length)%tabs.length;
      event.preventDefault();tabs[next]?.focus();tabs[next]?.click();
    }}>
      <button role="tab" aria-selected={!selected} tabIndex={!selected?0:-1} onClick={() => setSelected('')}><BoardArtwork board={main}/><span><strong>{main?.displayName ?? '未选择主控板'}</strong></span></button>
      {multi && channels.map(channel => <button role="tab" key={channel.id} aria-label={channel.name} aria-selected={selected===channel.id} tabIndex={selected===channel.id?0:-1} onClick={() => setSelected(channel.id)}><BoardArtwork board={hardware.find(item=>item.componentId===channel.boardId)}/><span><strong>{channel.name}</strong><small>{hardware.find(item=>item.componentId===channel.boardId)?.displayName}</small></span></button>)}
    </div>
    <button className="project-hardware-manage" onClick={()=>{if(selected)manageSelected.current?.();else onManageMain();}}>管理项目器件</button>
    {multi && <button className="controller-add" disabled={!ready || busy || channels.length>=7} onClick={() => { setCreating(value=>!value);setName(`主控${channels.length+2}`); }}><Plus size={16}/>添加主控</button>}
    {error && <p role="alert" className="settings-error">{error}</p>}
    {!ready && <button disabled={busy} onClick={()=>setReadAttempt(value=>value+1)}>重新读取主控</button>}
    {creating && <form className="channel-create" onSubmit={event => {
      event.preventDefault();setBusy(true);setError('');
      void api<DevelopmentChannel>(`/projects/${projectId}/channels`,'POST',{expectedRevision:0,name,boardId,componentIds:[],code:hardware.find(item=>item.componentId===boardId)?.programmingMode==='chat-coding'?'':initialCode}).then(async value=>{
        setChannels(previous=>[...previous,value]);setSelected(value.id);setCreating(false);await onSaved(projectId);
      }).catch(err=>setError(message(err)+'；未自动重发。结果未知时先重新读取主控。')).finally(()=>setBusy(false));
    }}><label>主控名称<input aria-label="主控名称" value={name} maxLength={80} required disabled={busy} onChange={event=>setName(event.target.value)}/></label><span>主控型号</span><button type="button" className="workflow-board" aria-label="主控型号" disabled={busy} onClick={()=>setChoosingBoard(true)}><BoardArtwork board={hardware.find(item=>item.componentId===boardId)}/><span>{hardware.find(item=>item.componentId===boardId)?.displayName??'选择主控板'}</span></button><button className="primary" disabled={busy || !name.trim() || !boardId}>添加此主控</button></form>}
    {multi && <button className="controller-shared" onClick={onShared}><BookOpen size={16}/>三师共用资料</button>}

  </section>;
  return <>{selectorHost && createPortal(selector,selectorHost)}{choosingBoard&&<BoardPicker boards={boards} selected={boardId} onClose={()=>setChoosingBoard(false)} onSelect={item=>{setBoardId(item.componentId);setChoosingBoard(false);}} onHelp={()=>{setChoosingBoard(false);setError('请按实际主控选择型号，可在主控资料中核对接口与固件。');}}/>}{workspaceHost && createPortal(<>{channels.map(channel => {const Workspace=hardware.find(item=>item.componentId===channel.boardId)?.programmingMode==='chat-coding'?MosaicoControllerWorkspace:ControllerWorkspace;return <section key={channel.id} role="tabpanel" aria-label={channel.name} hidden={selected!==channel.id}><Workspace folder={folder} projectId={projectId} channel={channel} hardware={hardware} onChange={update} onSaved={onSaved} onActivity={activityChanged} active={engineeringActive&&selected===channel.id} selected={selected===channel.id} promptSelected={promptSelected} programsSelected={programsSelected} onState={onState} mobileTab={mobileTab} actionsHost={actionsHost} dialogsHost={dialogsHost} connectionHost={connectionHost} modulesHost={modulesHost} configured={configured} onSettings={onSettings} fullscreen={fullscreen} onFullscreen={onFullscreen} onMobileTab={onMobileTab} onHardwareSaved={onHardwareSaved} manageSelected={manageSelected} saveSelected={saveSelected}/></section>;})}</>,workspaceHost)}</>;
}
