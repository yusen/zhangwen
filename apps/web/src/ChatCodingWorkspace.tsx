import { useEffect, useRef, useState } from 'react';
import { ArrowUp, FileCode2, Save, Sparkles, Unplug, Wifi } from 'lucide-react';
import { Dialog } from './Dialog';
import type { ChatCodingState, Project, Version } from '../../../packages/contracts/src/platform';
import { api } from './api';
import './chat-coding.css';
import { mosaicoPanelEndpoint } from './mosaicoPanel';
import { decode, download, encode, MosaicoTools, useMosaicoDevice } from './MosaicoTools';
import { useLuaCoding, LuaConversation, LuaProgram } from './LuaCoding';
type MosaicoSource = 'local' | 'device';

const EMPTY: ChatCodingState = { schemaVersion: 1, revision: 0, records: [], connected: false };
const errorText = (value: unknown) => value instanceof Error ? value.message : String(value);
const rememberedEndpoint = () => { try { return mosaicoPanelEndpoint(localStorage.getItem('zhangwen-mosaico-panel-address') ?? '') ?? ''; } catch { return ''; } };
const rememberEndpoint = (value: string) => { try { localStorage.setItem('zhangwen-mosaico-panel-address', value); } catch { /* optional address preference */ } };

export function useChatCoding({ active, project, task, unsaved, disabled, onSaved, onBusy, prepareProject, onProjectPrepared }: {
  active: boolean; project: Project | null; task: string; unsaved: boolean; disabled: boolean;
  onSaved: (id: string) => Promise<void>; onBusy: (value: boolean) => void;
  prepareProject: () => Promise<Project>; onProjectPrepared: (project: Project) => void;
}) {
  const [state, setState] = useState<ChatCodingState>(EMPTY);
  const [endpoint, setEndpoint] = useState(rememberedEndpoint);
  const [observation, setObservation] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [connectionOpen, setConnectionOpen] = useState(false);
  const [deviceBusy,setDeviceBusy]=useState(false);
  const [luaBusy,setLuaBusy]=useState(false);
  const [source,setSourceValue]=useState<MosaicoSource>('local');
  useEffect(()=>{setSourceValue('local');},[project?.id]);
  const prepareForSource = prepareProject;
  const setSource=(value:MosaicoSource)=>{
    if(luaBusy||busy||deviceBusy)return;
    setSourceValue(value);
  };
  const device = useMosaicoDevice(active,setDeviceBusy);
  const lua = useLuaCoding({active,project,unsaved,disabled,device,onSaved,onBusy:setLuaBusy,prepareProject:prepareForSource,onProjectPrepared});
  const [attachments,setAttachments]=useState<string[]>([]);
  useEffect(()=>{onBusy(!!busy||deviceBusy||luaBusy);},[busy,deviceBusy,luaBusy,onBusy]);
  const currentProject = useRef(project?.id); currentProject.current = project?.id;
  const mounted = useRef(true);
  const executing = useRef(false);
  const id = project?.id;
  const localSync = useRef(onSaved); localSync.current = onSaved;
  const path = id ? `/projects/${id}/chat-coding` : '';
  const taskBytes = new TextEncoder().encode(task.trim()).length;
  const saved = !!project && task === project.code && !unsaved;
  const ready = active && !!project && project.programmingMode === 'chat-coding';
  const pending = state.records.some(r => r.kind === 'submission' && r.session === state.session && (r.state === 'pending' || r.state === 'outcome-unknown'));
  const deviceMessages = state.records.filter(r => r.kind === 'device-history').sort((a,b) => {
    if (a.session !== b.session) return a.createdAt.localeCompare(b.createdAt);
    return Number(a.id.split('_').at(-1)) - Number(b.id.split('_').at(-1));
  });

  useEffect(() => {
    let current = true;
    setState(EMPTY); setEndpoint(rememberedEndpoint()); setError(''); setNotice(''); setObservation('');
    setAttachments([]);
    if (!active) setConnectionOpen(false);
    if (ready && id) void api<ChatCodingState>(`/projects/${id}/chat-coding`).then(value => {
      if (current) { setState(value); setEndpoint(value.endpoint ?? rememberedEndpoint()); }
    }).catch(err => { if (current) setError(errorText(err)); });
    return () => { current = false; };
  }, [id, ready, active]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => {
    if (!ready || !id || state.protocol !== 'legacy-websocket' || !state.connected) return;
    let current = true, reading = false;
    let revision = state.revision;
    // Read our local inbox only. Connection explicitly started the device's live
    // channel; this poll never sends/retries tasks or reconnects the device.
    const timer = window.setInterval(() => {
      if (reading || document.hidden || executing.current) return;
      reading = true;
      void api<ChatCodingState>(`/projects/${id}/chat-coding`).then(async value => {
        if (!current || executing.current || currentProject.current !== id) return;
        setState(value);
        if (value.revision !== revision) { revision = value.revision; await localSync.current(id); }
      }).catch(err => { if (current) setError(errorText(err)); }).finally(() => { reading = false; });
    }, 2000);
    return () => { current = false; window.clearInterval(timer); };
  }, [id, ready, state.connected, state.protocol]);

  async function perform(label: string, operation: string, body: unknown = {}) {
    if (!ready || !id || disabled || executing.current) return;
    executing.current = true; setBusy(label); setError(''); setNotice('');
    const projectId = id;
    try {
      const value = await api<ChatCodingState>(path + operation, 'POST', body);
      if (mounted.current && currentProject.current === projectId) {
        setState(value);
        setNotice(operation === '/send' ? '发送请求已处理。回执仅表示设备接收状态，请查看回复并观察实物。' : operation === '/disconnect' ? '已断开掌问连接；设备上的任务可能仍在运行。' : operation === '/observations' ? '已保存个人观察，未自动判定硬件成功。' : operation === '/connect' ? (value.protocol === 'legacy-websocket' ? '已连接旧版 WebIM 实时通道。回复会自动收取；设备不提供历史补读或运行状态。' : 'WebIM接口匹配；主控型号和固件能力仍须按实物核对。') : '会话记录已读取；请结合设备回复和实物现象判断。');
        if (operation === '/observations') setObservation('');
        if (operation === '/send') setAttachments([]);
        if (operation === '/connect') { setConnectionOpen(false); if (value.endpoint) rememberEndpoint(value.endpoint); }
      }
      await onSaved(projectId);
    } catch (err) {
      if (mounted.current && currentProject.current === projectId) {
        setError(errorText(err));
        // A lost response can still have committed a receipt. Read local state only.
        try {
          const value = await api<ChatCodingState>(path);
          if (mounted.current && currentProject.current === projectId) setState(value);
        } catch { /* preserve original error */ }
      }
      await onSaved(projectId);
    } finally {
      executing.current = false;
      if (mounted.current) setBusy('');
    }
  }

  const locked = disabled || !!busy || !!device.busy || luaBusy;
  const canSend = ready && saved && state.connected && !!state.bound && !locked && !pending && (state.protocol === 'legacy-websocket' || state.runState === 'idle') && taskBytes > 0 && taskBytes <= 4000;
  const send = () => { if (canSend) void perform('发送任务', '/send', {clientMessageId:crypto.randomUUID().replaceAll('-',''), expectedRevision:project!.revision,files:attachments}); };
  useEffect(()=>{setAttachments([]);},[device.state.connectionId]);
  async function uploadAttachment(file:File){
    if(!ready||!id||attachments.length>=4||locked)return;
    if(file.size<1||file.size>1_000_000){setError('附件须为1字节至1 MB。');return;}
    const filename=file.name.replace(/[^a-zA-Z0-9._-]/g,'_').slice(-100)||'attachment';
    try{const result=await device.run<{path:string;message:string}>('上传聊天附件','/attachment','POST',{projectId:id,path:'/inbox/webim/'+crypto.randomUUID().replaceAll('-','')+'_'+filename,content:encode(new Uint8Array(await file.arrayBuffer()))});setAttachments(v=>[...v,result.path]);setNotice(result.message);}catch{/* hook shows error */}
  }
  async function downloadReply(url:string){
    try{if(!device.state.connected||device.state.endpoint!==state.endpoint)throw new Error('请先连接回复所属的设备。');const v=await device.run<{content:string;missing?:boolean}>('下载设备回复文件','/file?path='+encodeURIComponent(url.slice('/files'.length)));if(v.missing)throw new Error('设备回复中的文件已不存在，未下载空文件。');download(url.split('/').at(-1)??'reply',decode(v.content));}catch(e){setError(errorText(e));}
  }
  const connectDevice = async () => {
    const target = mosaicoPanelEndpoint(device.state.endpoint ?? state.endpoint ?? endpoint);
    if (!target) { setError('请在连接设备中填写局域网IPv4 HTTP地址，例如 http://192.168.60.126。'); setConnectionOpen(true); return; }
    try {
      if(!device.state.connected) await device.connect(target);
      rememberEndpoint(target);setEndpoint(target);
      if(source==='device'&&ready&&!state.connected) await perform('连接设备','/connect',{endpoint:target});
      else setConnectionOpen(false);
    } catch { /* management hook exposes the error */ }
  };
  const disconnectDevice = async () => {try {await device.disconnect();if(state.connected)await perform('断开连接','/disconnect');setState(EMPTY);}catch{/* retain error */}};
  return { state, endpoint, setEndpoint, observation, setObservation, busy, locked, ready, saved, pending, taskBytes,
    error, notice, deviceMessages, perform, canSend, send, connectionOpen, setConnectionOpen, device, connectDevice, disconnectDevice,
    projectId:ready?id:undefined, onDeviceSaved:()=>id?onSaved(id):Promise.resolve(),attachments,setAttachments,uploadAttachment,downloadReply,source,setSource,lua };
}

type Controller = ReturnType<typeof useChatCoding>;

export function ChatCodingConnection({ chat, onSave }: { chat: Controller; onSave: () => void }) {
  const { state, locked, ready, endpoint, setEndpoint } = chat;
  return <Dialog title="连接设备 · Mosaico" className="chat-coding-connection-dialog" onClose={() => { if (!chat.busy&&!chat.device.busy) chat.setConnectionOpen(false); }}>
    <p className="muted">电脑和 Mosaico 连接同一WiFi，填入设备屏幕上的地址即可。无需配置板载模型。</p>
    <label className="field">设备地址<input type="url" inputMode="url" placeholder="http://192.168.1.20" value={chat.device.state.endpoint??endpoint} disabled={locked || state.connected || chat.device.state.connected} onChange={e => setEndpoint(e.target.value)}/></label>
    <p role="status">{chat.busy || chat.device.busy || (chat.device.state.connected || state.connected ? `设备已连接${state.connected?' · 项目聊天已连接':''}` : '设备未连接')}</p>
    {state.protocol === 'legacy-websocket' && <p className="muted">旧版 WebIM · WebSocket 实时回复。连接期间自动保存本项目的回复；设备没有会话历史接口、启动标识或运行状态，断线期间的回复无法补读。</p>}
    {state.protocol === 'session-v1' && <p className="muted">会话版 WebIM · 支持历史读取与设备启动标识。</p>}
    {state.connectionError && <p className="settings-error" role="alert">{state.connectionError}</p>}
    {chat.error && <p className="settings-error" role="alert">{chat.error}</p>}
    {chat.device.error && <p className="settings-error" role="alert">{chat.device.error}</p>}
    {!ready && <p className="muted">连接后可查看设备状态、配置、日志和文件。保存Mosaico项目后可发送任务、备份并写入文件。</p>}
    <div className="chat-coding-dialog-actions">
      {!ready && <button disabled={locked} onClick={() => { chat.setConnectionOpen(false); onSave(); }}><Save size={16}/>保存项目</button>}
      {(state.connected || chat.device.state.connected) && <button disabled={locked} onClick={() => void chat.disconnectDevice()}><Unplug size={16}/>断开连接</button>}
      {(!chat.device.state.connected || (chat.source==='device'&&ready&&!state.connected))&&<button className="primary" disabled={locked || !endpoint.trim()} onClick={() => void chat.connectDevice()}><Wifi size={16}/>{chat.device.state.connected?'连接项目聊天':'连接 Mosaico'}</button>}
    </div>
    <details><summary>固件、模型和操作说明</summary><p>默认由掌问模型生成Lua，无需配置板载模型API。通过局域网上传，初始化WiFi运行服务后即可点击运行，无需USB。无需编译SDK或MicroPython。若切换到「设备原生Claw」，才使用设备自己的模型配置。</p><p>接口匹配不能确认板型。断开连接不会停止设备任务；WiFi运行采用明确时限，请核对设备回执、输出与实物。</p></details>
  </Dialog>;
}

export function ChatCodingConversation({ chat, task, onTask, onSave, mobileTab, onSettings }: {
  chat: Controller; task: string; onTask: (value: string) => void; onSave: () => void; mobileTab: string; onSettings: () => void;
}) {
  const { state, deviceMessages, locked } = chat;
  const unmirrored = state.records.filter(r => r.kind === 'submission' && !deviceMessages.some(m => m.role === 'user' && m.session === r.session && m.text === r.text));
  const conversation = [...deviceMessages, ...unmirrored].sort((a,b) => {
    if (a.session === b.session && a.kind === 'device-history' && b.kind === 'device-history') return Number(a.id.split('_').at(-1)) - Number(b.id.split('_').at(-1));
    return a.createdAt.localeCompare(b.createdAt);
  });
  const picker=<MosaicoSourcePicker value={chat.source} disabled={locked||!!chat.lua.busy} onChange={chat.setSource}/>;
  if(chat.source==='local') return <LuaConversation lua={chat.lua} mobileTab={mobileTab} onSettings={onSettings} onSource={()=>chat.setSource('device')} picker={picker}/>;
  return <section className={`ai-panel panel native-chat-panel mobile-${mobileTab === 'ai' ? 'show' : 'hide'}`} aria-label="Mosaico Chat Coding对话">
    <div className="panel-head"><h2><Sparkles size={18}/>掌问 · Chat Coding</h2><span className="native-chat-source">设备原生 Claw</span></div>
    {picker}
    <div className="messages" role="log" aria-label="设备原生对话">
      <section className="conversation-board-context"><Wifi size={24}/><div><strong>ESP-Mosaico · 设备 Claw</strong><p>{state.connected ? '接口已连接' : '点击右上角「连接设备」配置连接'} · 保存任务后显式发送。</p></div></section>
      {!deviceMessages.length && !unmirrored.length && <div className="conversation-empty"><span><Sparkles size={24}/></span><p>描述你想让设备完成的一个小任务。</p></div>}
      {conversation.map(r => <article key={r.id} className={`message ${r.kind === 'submission' || r.role === 'user' ? 'user' : 'assistant'}`}><strong>{r.kind === 'submission' ? `你 · ${r.state === 'submitted' ? '设备已接收' : '发送结果待核对'}` : r.role === 'assistant' ? '设备 Claw' : r.role === 'user' ? '你 · 已发送' : '设备记录'}</strong><pre>{r.text}</pre>{r.files?.map(f=><small key={f}>附件：{f.split('/').at(-1)}</small>)}{r.links?.map(link=><button key={link.url} disabled={locked} onClick={()=>void chat.downloadReply(link.url)}>下载 {link.label||link.url.split('/').at(-1)}</button>)}</article>)}
    </div>
    {chat.error && <p className="chat-error" role="alert">{chat.error}</p>}
    {state.connectionError && <p className="chat-error" role="alert">{state.connectionError}</p>}
    {chat.notice && <p className="chat-hint" role="status">{chat.notice}</p>}
    <p className="chat-hint">设备收到任务后可能生成并执行 Lua。核对任务和接线后发送，回复需结合实物观察判断。</p>
    {chat.pending && <p className="chat-error" role="alert">上次发送结果未知，请在设备面板核对；不会自动重发。</p>}
    <form className="chat-form" onSubmit={e => { e.preventDefault(); chat.send(); }}>
      <label className="sr-only" htmlFor="chat-coding-task">Chat Coding任务</label>
      <textarea id="chat-coding-task" value={task} maxLength={4000} disabled={locked} onChange={e => onTask(e.target.value)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); chat.send(); } }} placeholder="描述想让 Mosaico 完成的任务…"/>
      <label className="native-chat-attachment">添加附件（最多4个，每个1 MB）<input aria-label="Chat Coding附件" type="file" disabled={locked||!chat.ready||!state.connected||!chat.device.state.connected||chat.attachments.length>=4} onChange={e=>{const file=e.target.files?.[0];if(file)void chat.uploadAttachment(file);e.target.value='';}}/></label>{chat.attachments.map(file=><div key={file}><small>{file.split('/').at(-1)}</small><button type="button" disabled={locked} onClick={()=>chat.setAttachments(paths=>paths.filter(p=>p!==file))}>移出待发送</button></div>)}<div><span>{chat.taskBytes} / 4000 字节 · {chat.saved ? '已保存' : '请先保存任务'}</span><button type="button" className="native-save-task" disabled={locked} onClick={onSave}><Save size={15}/>保存任务</button><button type="submit" className="primary icon-button" aria-label="发送任务到设备" title="发送已保存任务到设备" disabled={!chat.canSend}><ArrowUp size={20}/></button></div>
    </form>
  </section>;
}

export function ChatCodingTask({ chat, task, versions, selectedVersion, onVersion, mobileTab, saveState, folderError, onRetryFolder }: {
  chat: Controller; task: string; versions: Version[]; selectedVersion: number | null;
  onVersion: (revision: number) => void; mobileTab: string; saveState: string; folderError: string; onRetryFolder: () => void;
}) {
  const { state, locked } = chat;
  return <section className={`code-panel panel native-task-panel mobile-${mobileTab === 'code' ? 'show' : 'hide'}`} aria-label="Chat Coding任务与记录">
    {chat.source==='local'?<>
      <LuaProgram key={chat.projectId} lua={chat.lua} connected={chat.device.state.connected} onConnect={() => chat.setConnectionOpen(true)} saveState={saveState} folderError={folderError} onRetryFolder={onRetryFolder} observations={<div className="lua-observations"><label>发生了什么？<textarea aria-label="Lua实际观察" value={chat.observation} maxLength={2000} disabled={locked} onChange={e=>chat.setObservation(e.target.value)}/></label><button disabled={locked||!chat.ready||!chat.observation.trim()} onClick={()=>void chat.perform('保存观察','/observations',{text:chat.observation})}>保存观察</button>{state.records.filter(r=>r.kind==='observation').map(r=><p key={r.id}>{r.text}</p>)}</div>}/>
      {chat.device.section!=='records' && <Dialog title="设备工具" onClose={()=>chat.device.chooseSection('records')}><MosaicoTools device={chat.device} projectId={chat.projectId} onProjectSaved={chat.onDeviceSaved} disabled={locked}/></Dialog>}
    </>:<>
    {chat.device.section!=='records' && <Dialog title="设备工具" onClose={()=>chat.device.chooseSection('records')}><MosaicoTools device={chat.device} projectId={chat.projectId} onProjectSaved={chat.onDeviceSaved} disabled={locked}/></Dialog>}
    <div className="filebar"><span><FileCode2 size={16}/>chat-task.txt</span><span className="filebar-space"/><select className="code-version-select" aria-label="任务历史版本" disabled={!versions.length || locked} value={selectedVersion ?? 'draft'} onChange={e => { if (e.target.value !== 'draft') onVersion(Number(e.target.value)); }}><option value="draft" disabled>当前任务草稿</option>{versions.map(v => <option key={v.revision} value={v.revision}>V{v.revision} · {v.name || '任务'}</option>)}</select></div>
    <div className={`project-folder-status ${folderError ? 'has-error' : ''}`}><span>{saveState}</span>{folderError && <button disabled={locked} onClick={onRetryFolder}>重试同步</button>}</div>
    {folderError && <p className="chat-error" role="alert">{folderError}</p>}
    <div className="native-task-content">
      <div className="native-task-preview" aria-label="当前任务文件"><p className="muted">在对话输入框编辑，保存后形成任务版本。</p><pre>{task || '尚未输入任务。'}</pre></div>
      <p className="chat-hint" role="status">{state.protocol === 'legacy-websocket' ? '旧版实时会话 · 设备不提供运行状态' : state.session ? `设备会话：${state.runState === 'running' ? '处理中' : state.runState === 'queued' ? '已排队' : '空闲'}` : '尚未创建设备会话'} · 回执不代表实物通过。</p>
      <details className="chat-coding-receipts"><summary>发送回执 · {state.records.filter(r => r.kind === 'submission').length} 条</summary>{state.records.filter(r => r.kind === 'submission').map(r => <article key={r.id}><strong>{r.state === 'submitted' ? '设备返回接收回执' : '结果未知，勿重复发送'}</strong><p>任务 V{r.taskRevision}{r.runId !== undefined ? ` · 运行编号 ${r.runId}` : ''}</p><pre>{r.text}</pre><small>{r.createdAt} · {r.id}</small></article>)}</details>
      <section className="chat-coding-observations"><h3>我的实际观察</h3><label htmlFor="claw-observation">发生了什么？与预期哪里不同？</label><textarea id="claw-observation" value={chat.observation} maxLength={2000} disabled={locked} onChange={e => chat.setObservation(e.target.value)} placeholder="例如：屏幕出现了文字，但按键没有反应。"/><button disabled={!chat.ready || locked || !chat.observation.trim()} onClick={() => void chat.perform('保存观察','/observations',{text:chat.observation})}>保存观察</button>{state.records.filter(r => r.kind === 'observation').map(r => <article key={r.id}><p>{r.text}</p><small>{r.createdAt} · 用户记录</small></article>)}</section>
    </div>
    </>}
  </section>;
}

function MosaicoSourcePicker({value, disabled, onChange}: {value:MosaicoSource; disabled:boolean; onChange:(v:MosaicoSource)=>void}) {
  return <div className="lua-source"><label>编程方式<select aria-label="编程方式" value={value} disabled={disabled} onChange={e=>onChange(e.target.value as MosaicoSource)}><option value="local">Lua 脚本编程</option><option value="device">设备原生 Claw</option></select></label></div>;
}
