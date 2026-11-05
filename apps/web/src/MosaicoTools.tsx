import { useEffect, useRef, useState } from 'react';
import { api } from './api';
import { generate } from 'lean-qr';
import type { MosaicoConfig, MosaicoDeviceState, MosaicoFileData, MosaicoFileEntry, MosaicoSection, MosaicoWechatState, MosaicoWriteResult } from '../../../packages/contracts/src/platform';
import './mosaico-tools.css';

export const mosaicoSections: [MosaicoSection, string][] = [['records','任务与记录'],['status','设备状态'],['basic','网络与时间'],['llm','设备模型'],['asr','语音识别'],['im','消息平台'],['search','网络与搜索'],['memory','设备记忆'],['logs','实时日志'],['capabilities','设备能力'],['skills','Lua模块'],['files','设备文件']];
const errorText = (e: unknown) => e instanceof Error ? e.message : String(e);
const id = () => crypto.randomUUID().replaceAll('-', '');
type Fields = [string, string, string?][];
const fields: Record<string, Fields> = {
  basic: [['wifi_ssid','Wi-Fi名称'],['wifi_password','Wi-Fi密码','password'],['time_timezone','时区（设备格式）']],
  llm: [['llm_backend_type','接口类型'],['llm_profile','接口预设'],['llm_model','模型名称'],['llm_base_url','API地址'],['llm_api_key','API密钥','password'],['llm_auth_type','认证方式'],['llm_timeout_ms','超时（毫秒）'],['llm_max_tokens','最大输出Token'],['llm_max_tokens_field','Token参数名称'],['llm_reasoning_effort','推理强度'],['llm_supports_tools','支持工具调用'],['llm_supports_vision','支持图片'],['llm_default_image_max_bytes','图片大小上限（字节）'],['llm_image_remote_url_only','仅远程图片URL']],
  asr: [['asr_provider','语音服务'],['asr_model','语音模型'],['asr_endpoint','服务地址'],['asr_api_key','语音密钥','password'],['asr_workspace_id','工作空间'],['asr_language_hint','识别语言']],
  im: [['wechat_account_id','微信账号ID'],['wechat_token','微信Token','password'],['wechat_base_url','微信服务地址'],['wechat_cdn_base_url','微信CDN地址'],['qq_app_id','QQ应用ID'],['qq_app_secret','QQ应用密钥','password'],['feishu_app_id','飞书应用ID'],['feishu_app_secret','飞书应用密钥','password'],['tg_bot_token','Telegram Bot Token','password']],
  search: [['search_brave_key','Brave搜索密钥','password'],['search_tavily_key','Tavily搜索密钥','password'],['search_http_allowlist','HTTP访问白名单']],
};
export function useMosaicoDevice(active: boolean, onBusy: (busy: boolean) => void) {
  const [state,setState] = useState<MosaicoDeviceState>({connected:false});
  const [section,setSection] = useState<MosaicoSection>('records');
  const [busy,setBusy] = useState('');
  const [error,setError] = useState('');
  const [notice,setNotice] = useState('');
  const unsaved=useRef(false);
  const current = useRef(state); current.current = state;
  const running = useRef(false), mounted = useRef(true);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  useEffect(() => { let live = true; if (active) void api<MosaicoDeviceState>('/mosaico').then(v => { if(live) setState(v); }).catch(e => {if(live) setError(errorText(e));}); return () => {live=false;}; },[active]);
  async function run<T>(label: string, path: string, method = 'GET', body?: Record<string, unknown>): Promise<T> {
    if (running.current) throw new Error('请等待当前设备操作完成。');
    running.current = true; setBusy(label); onBusy(true); setError(''); setNotice('');
    const connectionId = current.current.connectionId;
    try {
      const value = await api<T>('/mosaico' + path, method, method === 'GET' ? undefined : (path==='/connect'?body:{connectionId,requestId:id(),...body}));
      if (mounted.current && value && typeof value === 'object' && 'connected' in value) setState(value as MosaicoDeviceState);
      return value;
    } catch(e) {
      if(mounted.current) { setError(errorText(e)); try { setState(await api<MosaicoDeviceState>('/mosaico')); } catch { /* retain error */ } }
      throw e;
    } finally { running.current=false; if(mounted.current) setBusy(''); onBusy(false); }
  }
  const connect = async (endpoint: string) => { const result=await run<MosaicoDeviceState>('连接设备','/connect','POST',{endpoint});current.current=result;return result; };
  const chooseSection=(value:MosaicoSection)=>{if(unsaved.current&&!window.confirm('当前设备修改尚未保存，放弃并切换？'))return;unsaved.current=false;setSection(value);};
  return {state,section,setSection,chooseSection,unsaved,busy,error,notice,setNotice,run,connect,disconnect:()=>run<MosaicoDeviceState>('断开连接','/disconnect','POST')};
}
export type MosaicoController = ReturnType<typeof useMosaicoDevice>;
export const decode = (v: string) => Uint8Array.from(atob(v), c=>c.charCodeAt(0));
export const encode = (v: Uint8Array) => {let s='';for(const n of v)s+=String.fromCharCode(n);return btoa(s);};
export function download(name: string, raw: Uint8Array) { const blob=new Blob([new Uint8Array(raw)]),url=URL.createObjectURL(blob);const a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000); }
const fieldValue = (v: unknown) => typeof v === 'boolean' ? (v?'是':'否') : String(v ?? '未提供');

export function MosaicoTools({device,projectId,disabled,onProjectSaved}:{device:MosaicoController;projectId?:string;disabled:boolean;onProjectSaved?:()=>Promise<void>}) {
  const {section,state,run}=device;
  const [config,setConfig]=useState<MosaicoConfig|null>(null),[patch,setPatch]=useState<Record<string,string>>({});
  const [items,setItems]=useState<Record<string, unknown>[]>([]),[status,setStatus]=useState<Record<string, unknown>>({});
  const [path,setPath]=useState('/'),[entries,setEntries]=useState<MosaicoFileEntry[]>([]),[file,setFile]=useState<MosaicoFileData|null>(null);
  const [text,setText]=useState(''),[fileDirty,setFileDirty]=useState(false),[newName,setNewName]=useState('');
  const [binary,setBinary]=useState(false);
  const [backups,setBackups]=useState<{id:string;path:string;content:string;exists:boolean;createdAt:string}[]>([]);
  const [wechat,setWechat]=useState<MosaicoWechatState|null>(null),[logs,setLogs]=useState<{active:boolean;entries:{seq:number;text:string}[];dropped:number;error:string}>({active:false,entries:[],dropped:0,error:''});
  const [loaded,setLoaded]=useState(''),[localError,setLocalError]=useState('');
  const configDirty=Object.keys(patch).length>0;
  const locked=disabled||!!device.busy;
  const dirty=configDirty||fileDirty;
  useEffect(()=>{device.unsaved.current=dirty;return()=>{device.unsaved.current=false;};},[dirty,device.unsaved]);
  const scope=state.connectionId+':'+section;
  const alive=useRef(scope);alive.current=scope;
  const memoryPaths=[['/memory/memory.md','长期记忆（只读）'],['/memory/soul.md','性格设定'],['/memory/identity.md','身份设定'],['/memory/user.md','用户资料']];
  const report=(work:()=>Promise<unknown>)=>{setLocalError('');void work().catch(e=>setLocalError(errorText(e)));};
  async function load() {
    const token=scope;
    if (!state.connected) return;
    setLocalError('');
    if (section==='status') { const v=await run<MosaicoDeviceState>('读取设备状态','/status');if(alive.current===token)setStatus(v.status??{}); }
    else if (section in fields || section==='capabilities'||section==='skills') {
      const v=await run<MosaicoConfig>('读取设备配置','/config/'+section);if(alive.current!==token)return;setConfig(v);setPatch({});
      if(section==='capabilities'||section==='skills'){const list=await run<{items:Record<string,unknown>[]}>('读取设备清单','/'+section);if(alive.current===token)setItems(list.items??[]);}
    } else if (section==='files') { await listFiles(path); }
    else if(section==='logs'){const v=await run<typeof logs>('读取日志','/logs');if(alive.current===token)setLogs(v);}
    if(alive.current===token)setLoaded(token);
  }
  useEffect(()=>{setConfig(null);setPatch({});setItems([]);setFile(null);setText('');setFileDirty(false);setWechat(null);setBackups([]);setLocalError('');setLoaded('');if(state.connected)report(load);},[scope,state.connected]);
  useEffect(()=>{if(!dirty)return;const prevent=(e:BeforeUnloadEvent)=>{e.preventDefault();e.returnValue='';};window.addEventListener('beforeunload',prevent);return()=>window.removeEventListener('beforeunload',prevent);},[dirty]);
  useEffect(()=>{
    if(section!=='logs'||!logs.active||!state.connected)return;
    let live=true,reading=false;
    const timer=setInterval(()=>{if(reading||document.hidden||device.busy)return;reading=true;void api<typeof logs>('/mosaico/logs').then(v=>{if(live)setLogs(v);}).catch(e=>{if(live)setLocalError(errorText(e));}).finally(()=>{reading=false;});},1500);
    return()=>{live=false;clearInterval(timer);};
  },[section,logs.active,state.connected,device.busy]);
  async function saveConfig(){if(!config)return;const v=await run<MosaicoWriteResult>('保存设备配置','/config','POST',{section,revision:config.revision,patch});const message=v.message;const fresh=await run<MosaicoConfig>('回读设备配置','/config/'+section);setConfig(fresh);setPatch({});device.setNotice(message);}
  async function listFiles(target:string){const v=await run<{entries:MosaicoFileEntry[]}>('读取设备目录','/files?path='+encodeURIComponent(target));if(alive.current!==scope)return;setPath(target);setEntries(v.entries??[]);}
  async function openFile(target:string){if(fileDirty&&!window.confirm('放弃当前未保存的设备文件修改？'))return;const token=scope;const v=await run<MosaicoFileData>('读取设备文件','/file?path='+encodeURIComponent(target));if(alive.current!==token)return;setFile(v);try{const content=new TextDecoder('utf-8',{fatal:true}).decode(decode(v.content));setBinary(content.includes('\0'));setText(content.includes('\0')?'':content);}catch{setText('');setBinary(true);}setFileDirty(false);}
  async function saveFile(raw?:Uint8Array,target?:string,expected?:string|null){
    const v=await run<MosaicoWriteResult>('备份并写入设备文件','/file','POST',{projectId,path:target??file?.path,content:encode(raw??new TextEncoder().encode(text)),expectedChecksum:expected!==undefined?expected:(file?.missing?null:file?.sha256)});
    setFileDirty(false);await onProjectSaved?.();if(file?.path===target||!target){const next=await run<MosaicoFileData>('回读设备文件','/file?path='+encodeURIComponent(target??file!.path));setFile(next);setText(new TextDecoder().decode(decode(next.content)));}await listFiles(path);device.setNotice(v.message);
  }
  async function upload(selected:File){
    if(selected.size<1||selected.size>1_000_000)throw new Error('文件须为1字节至1 MB。');
    const target=(path==='/'?'':path)+'/'+selected.name;
    const previous=await run<MosaicoFileData>('检查设备目标文件','/file?path='+encodeURIComponent(target));
    if(!previous.missing&&!window.confirm('设备上已有同名文件。备份后覆盖？'))return;
    await saveFile(new Uint8Array(await selected.arrayBuffer()),target,previous.missing?null:previous.sha256);
  }
  const selectSection=(value:MosaicoSection)=>device.chooseSection(value);
  const selection=(key:string,ids:string[],defaults?:string[])=>{const value=patch[key]??config?.values[key]??'';return value===''?new Set(defaults??ids):new Set(value==='__none__'||value==='none'?[]:value.split(','));};
  const toggle=(key:string,value:string,on:boolean,ids:string[],defaults?:string[])=>{const values=selection(key,ids,defaults);if(on)values.add(value);else values.delete(value);setPatch(p=>({...p,[key]:values.size?[...values].join(','):'__none__'}));};
  return <div className="mosaico-tools">
    <div className="mosaico-tools-nav"><label>设备工具<select aria-label="Mosaico功能" value={section} onChange={e=>selectSection(e.target.value as MosaicoSection)}>{mosaicoSections.filter(([key])=>key!=='records').map(([key,label])=><option key={key} value={key}>{label}</option>)}</select></label><button disabled={locked||!state.connected} onClick={()=>{if(!dirty||window.confirm('重新读取将放弃当前设备修改，继续？'))report(load);}}>重新读取</button></div>
    {!state.connected?<p className="muted">点击右上角「连接设备」填写地址并连接，即可在这里操作Mosaico。</p>:<>
    <p className="muted">{state.endpoint} · 操作作用于设备</p>
    {section==='status'&&<><dl className="mosaico-status">{[['wifi_connected','Wi-Fi已连接'],['ip','设备IP'],['wifi_mode','网络模式'],['ap_active','配网热点'],['ap_ssid','热点名称'],['ap_ip','热点IP'],['storage_base_path','设备存储']].filter(([key])=>key in status).map(([key,label])=><div key={key}><dt>{label}</dt><dd>{fieldValue(status[key])}</dd></div>)}</dl><button disabled={locked} onClick={()=>{if(window.confirm('重启Mosaico会中断设备当前连接。确定重启？'))report(async()=>{const v=await run<MosaicoWriteResult>('提交设备重启','/restart','POST');await run<MosaicoDeviceState>('读取本机连接状态','');device.setNotice(v.message);});}}>重启设备</button></>}
    {(section in fields)&&config&&<form onSubmit={e=>{e.preventDefault();report(saveConfig);}}>
      <p className="muted">已有密钥仅显示是否配置。留空保持；勾选清除才会删除。设备模型独立于掌问模型。</p>
      {fields[section].filter(([key])=>config.available.includes(key)).map(([key,label,type])=><div className="mosaico-config-field" key={key}><label>{label}<input aria-label={label} type={type??'text'} autoComplete="off" disabled={locked} value={patch[key]??(type==='password'?'':config.values[key]??'')} placeholder={type==='password'&&config.secrets.includes(key)?'已配置，留空保持':''} onChange={e=>{const value=e.target.value;setPatch(p=>{const next={...p};if(type==='password'&&!value)delete next[key];else if(value===config.values[key])delete next[key];else next[key]=value;return next;});}}/></label>{type==='password'&&<label className="mosaico-check"><input type="checkbox" checked={patch[key]===''} disabled={locked} onChange={e=>setPatch(p=>{const next={...p};if(e.target.checked)next[key]='';else delete next[key];return next;})}/>清除已存密钥</label>}</div>)}
      {!config.available.length&&<p>当前固件未提供此配置。</p>}
      {section==='im'&&<details><summary>微信扫码登录</summary><label>微信账号ID<input value={patch.wechat_account_id??config.values.wechat_account_id??''} onChange={e=>setPatch(p=>({...p,wechat_account_id:e.target.value}))}/></label><div className="mosaico-actions"><button type="button" disabled={locked} onClick={()=>report(async()=>setWechat(await run<MosaicoWechatState>('申请微信登录','/wechat/start','POST',{accountId:patch.wechat_account_id??config.values.wechat_account_id??''})))}>开始扫码登录</button><button type="button" disabled={locked} onClick={()=>report(async()=>setWechat(await run<MosaicoWechatState>('检查扫码状态','/wechat')))}>检查扫码状态</button><button type="button" disabled={locked} onClick={()=>report(async()=>setWechat(await run<MosaicoWechatState>('取消微信登录','/wechat/cancel','POST')))}>取消登录</button></div>{wechat&&<><p>{wechat.message??wechat.status??(wechat.completed?'已完成扫码，请保存配置':'等待扫码')}</p>{wechat.qr_data_url&&<WechatQR value={wechat.qr_data_url}/>} {wechat.completed&&wechat.token&&<button type="button" disabled={locked} onClick={()=>setPatch(p=>({...p,wechat_token:wechat.token!,...(wechat.account_id?{wechat_account_id:wechat.account_id}:{}),...(wechat.base_url?{wechat_base_url:wechat.base_url}:{})}))}>采用扫码结果（再保存）</button>}</>}</details>}
      <button className="primary" disabled={locked||!configDirty}>保存到设备</button>
    </form>}
    {(section==='capabilities'||section==='skills')&&config&&<>
      <p className="muted">更改只在保存后提交给设备，部分选项需要重启生效。</p>
      <div className="mosaico-cap-list">{items.map(item=>{const value=String(item[section==='skills'?'module_id':'group_id']),ids=items.map(i=>String(i[section==='skills'?'module_id':'group_id']));const key=section==='skills'?'enabled_lua_modules':'enabled_cap_groups';return <article key={value}><strong>{String(item.display_name??value)}</strong><small>{value}</small><label><input type="checkbox" disabled={locked} checked={selection(key,ids).has(value)} onChange={e=>toggle(key,value,e.target.checked,ids)}/>启用</label>{section==='capabilities'&&<label><input type="checkbox" disabled={locked||!selection(key,ids).has(value)} checked={selection('llm_visible_cap_groups',ids,items.filter(i=>i.default_llm_visible).map(i=>String(i.group_id))).has(value)} onChange={e=>toggle('llm_visible_cap_groups',value,e.target.checked,ids,items.filter(i=>i.default_llm_visible).map(i=>String(i.group_id)))}/>设备Agent可见</label>}</article>;})}</div><button className="primary" disabled={locked||!configDirty} onClick={()=>report(saveConfig)}>保存到设备</button>
    </>}
    {(section==='files'||section==='memory')&&<>
      {!projectId&&<p className="muted">可查看和下载文件。保存Mosaico项目后才能写入，以保留操作前备份。</p>}
      {section==='memory'?<div className="mosaico-memory-list">{memoryPaths.map(([target,label])=><button disabled={locked} key={target} onClick={()=>report(()=>openFile(target))}>{label}</button>)}</div>:<>
        <div className="mosaico-actions"><strong>{path}</strong><button disabled={locked} onClick={()=>report(async()=>{const archive=await run<{content:string}>('打包下载设备目录','/archive?path='+encodeURIComponent(path));download((path.split('/').at(-1)||'mosaico')+'.tar',decode(archive.content));})}>下载此目录</button><button disabled={locked||path==='/'||!projectId||entries.length>0} onClick={()=>{if(window.confirm('删除空目录 '+path+'？'))report(async()=>{const result=await run<MosaicoWriteResult>('删除设备空目录','/directory-delete','POST',{projectId,path});device.setNotice(result.message);await listFiles(path.slice(0,path.lastIndexOf('/'))||'/');});}}>删除空目录</button><button disabled={locked||path==='/'} onClick={()=>report(()=>listFiles(path.slice(0,path.lastIndexOf('/'))||'/'))}>上级目录</button><label className="mosaico-upload">上传文件<input aria-label="上传Mosaico文件" type="file" disabled={locked||!projectId} onChange={e=>{const f=e.target.files?.[0];if(f)report(()=>upload(f));e.target.value='';}}/></label></div>
        <div className="mosaico-actions"><input aria-label="设备新文件或文件夹名称" placeholder="新文件或文件夹名称" disabled={locked} value={newName} onChange={e=>setNewName(e.target.value)}/><button disabled={locked||!newName||!projectId} onClick={()=>{const target=(path==='/'?'':path)+'/'+newName;if(fileDirty&&!window.confirm('放弃当前未保存的设备文件修改？'))return;setFile({path:target,content:'',sha256:'',size:0,encoding:'base64',missing:true});setBinary(false);setText('');setFileDirty(true);}}>新建文件</button><button disabled={locked||!newName} onClick={()=>report(async()=>{await run('创建设备文件夹','/mkdir','POST',{path:(path==='/'?'':path)+'/'+newName});setNewName('');await listFiles(path);})}>新建文件夹</button></div>
        <div className="mosaico-file-list">{entries.map(entry=><button disabled={locked} key={entry.path} onClick={()=>report(()=>entry.is_dir?listFiles(entry.path):openFile(entry.path))}><span>{entry.is_dir?'目录':'文件'} · {entry.name}</span><small>{entry.is_dir?'':entry.size+' B'}</small></button>)}</div>
      </>}
      {file&&<section className="mosaico-file-editor"><h3>{file.path}</h3><p className="muted">{file.missing?'设备上尚不存在':file.size+' B · SHA256 '+file.sha256}</p>{binary&&<p className="muted">二进制文件可下载或替换上传，不作为文本编辑。</p>}<textarea aria-label="设备文件内容" disabled={locked||binary||file.path==='/memory/memory.md'} value={text} onChange={e=>{setText(e.target.value);setFileDirty(true);}}/><div className="mosaico-actions"><button disabled={locked||binary||!projectId||!fileDirty||file.path==='/memory/memory.md'} onClick={()=>report(()=>saveFile())}>备份并保存到设备</button><button disabled={locked||!!file.missing} onClick={()=>download(file.path.split('/').at(-1)??'device-file',decode(file.content))}>下载文件</button>{section==='files'&&<button disabled={locked||!projectId||!!file.missing} onClick={()=>{if(window.confirm('备份后删除设备文件 '+file.path+'？'))report(async()=>{const result=await run<MosaicoWriteResult>('备份并删除设备文件','/file-delete','POST',{projectId,path:file.path,expectedChecksum:file.sha256});device.setNotice(result.message);setFile(null);setFileDirty(false);await listFiles(path);});}}>备份并删除</button>}</div></section>}
      {projectId&&<details><summary>设备文件备份</summary><button disabled={locked} onClick={()=>report(async()=>setBackups((await run<{items:typeof backups}>('读取项目备份','/backups/'+projectId)).items))}>读取备份</button>{backups.map(b=><article key={b.id}><p>{b.path} · {b.createdAt}{!b.exists?' · 原文件不存在':''}</p>{b.exists&&<><button onClick={()=>download((b.path.split('/').at(-1)??'file')+'.backup',decode(b.content))}>下载备份</button><button disabled={locked} onClick={()=>report(async()=>{const current=await run<MosaicoFileData>('核对恢复目标','/file?path='+encodeURIComponent(b.path));if(window.confirm('将此备份恢复到设备 '+b.path+'？当前文件会再次备份。'))await saveFile(decode(b.content),b.path,current.missing?null:current.sha256);})}>恢复此备份</button></>}</article>)}</details>}
    </>}
    {section==='logs'&&<><div className="mosaico-actions"><button disabled={locked||logs.active} onClick={()=>report(async()=>setLogs(await run<typeof logs>('开始读取设备日志','/logs/start','POST')))}>开始读取日志</button><button disabled={locked||!logs.active} onClick={()=>report(async()=>setLogs(await run<typeof logs>('停止读取日志','/logs/stop','POST')))}>停止读取</button><button onClick={()=>download('mosaico-logs.txt',new TextEncoder().encode(logs.entries.map(e=>e.text).join('\n')))}>导出当前日志</button></div><p>{logs.active?'正在读取':'未读取'} · 仅保留本次最近1000条{logs.dropped?'，已移出 '+logs.dropped+' 条':''}</p>{logs.error&&<p role="alert">{logs.error}</p>}<pre className="mosaico-logs" aria-label="Mosaico实时日志">{logs.entries.map(e=>e.text).join('\n')||'尚无日志。'}</pre></>}
    {!loaded&&!device.busy&&!localError&&<p className="muted">请选择或重新读取设备功能。</p>}
    </>}
    {device.busy&&<p role="status">{device.busy}…</p>}
    {state.unknownWrite&&<p role="alert" className="chat-error">{state.unknownWrite}</p>}
    {(localError||device.error)&&<p role="alert" className="chat-error">{localError||device.error}</p>}
    {device.notice&&<p role="status">{device.notice}</p>}
  </div>;
}

function WechatQR({value}:{value:string}) {
  const canvas=useRef<HTMLCanvasElement>(null);
  useEffect(()=>{if(canvas.current&&!value.startsWith('data:'))generate(value).toCanvas(canvas.current,{pad:4});},[value]);
  return value.startsWith('data:image/') ? <img className="mosaico-qr" alt="微信登录二维码" src={value}/> : <div><canvas ref={canvas} className="mosaico-qr" aria-label="微信登录二维码"/><p>请用微信扫描二维码，完成后检查扫码状态。</p></div>;
}
