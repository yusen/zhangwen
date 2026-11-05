import { useEffect, useRef, useState, type ReactNode } from 'react';
import { ArrowUp, Save, Sparkles, Wifi, Upload, FileCode2, MoreHorizontal, Terminal, Settings, Eye, ZoomIn, ZoomOut, Maximize, Minimize } from 'lucide-react';
import type { ChatMessage, LuaCodingCheckpoint, LuaManifest, LuaVersion, LuaWifiPlan, LuaWifiStatus, Project, ReferenceCitation, RecoverLuaRun } from '../../../packages/contracts/src/platform';
import { api, bootstrap, chat } from './api';
import { replyCode, replyView, streamText } from './assistantReply';
import type { MosaicoController } from './MosaicoTools';
import { Dialog } from './Dialog';
import { uploadAndRunLua } from './luaWifiFlow';
import { saveGeneratedLua } from './luaGeneratedSave';
import { ActionMenu } from './ActionMenu';
import { Editor } from './Editor';
import { ReferenceSources } from './ProjectReferences';

const empty = (): LuaCodingCheckpoint => ({ schemaVersion: 1, revision: 0, accepted: null, versions: [], uploads: [], runs: [] });
const errorText = (e: unknown) => e instanceof Error ? e.message : String(e);
const requestId = () => crypto.randomUUID().replaceAll('-', '');
const draftKey = (id: string) => 'zhangwen-lua-draft-' + id;

export function useLuaCoding({ active, project, disabled, device, onSaved, onBusy, prepareProject, onProjectPrepared }: {
  active: boolean; project: Project | null; unsaved: boolean; disabled: boolean; device: MosaicoController;
  onSaved: (id: string) => Promise<void>; onBusy: (busy: boolean) => void;
  prepareProject: () => Promise<Project>; onProjectPrepared: (project: Project) => void;
}) {
  const [state, setState] = useState(empty), [draft, setDraft] = useState(''), [prompt, setPrompt] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]), [busy, setBusy] = useState(''), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [preview, setPreview] = useState<LuaManifest | null>(null), [stream, setStream] = useState('');
  const [output, setOutput] = useState(''), [wifi, setWifi] = useState<LuaWifiStatus | null>(null), [wifiPlan, setWifiPlan] = useState<LuaWifiPlan | null>(null);
  const [wifiChecking, setWifiChecking] = useState(false), [wifiError, setWifiError] = useState('');
  const wifiCheck = useRef(0);
  const [timeoutMs, setTimeoutMs] = useState(30000), [loaded, setLoaded] = useState(false);
  const [resultError, setResultError] = useState('');
  const [codeCandidate, setCodeCandidate] = useState<Pick<LuaVersion, 'code' | 'revision' | 'source'> | null>(null);
  const [showingCandidate, setShowingCandidate] = useState(false), [saveReview, setSaveReview] = useState(false);
  const [draftSourceRevision, setDraftSourceRevision] = useState<number | null>(null);
  const [submittedSources, setSubmittedSources] = useState<{references: ReferenceCitation[]; notice: string} | null>(null);
  const running = useRef(false), abort = useRef<AbortController | null>(null);
  const current = useRef(project?.id); current.current = project?.id;
  const adopting = useRef<string | null>(null);
  const scope = useRef({ active, projectId: project?.id }); scope.current = { active, projectId: project?.id };
  const pid = active && project?.programmingMode === 'chat-coding' ? project.id : undefined;
  const accepted = state.versions.find(v => v.revision === state.accepted);
  const editorCode = showingCandidate && codeCandidate ? codeCandidate.code : draft;
  const saved = !!accepted && editorCode === accepted.code && (!showingCandidate || codeCandidate?.revision === accepted.revision);
  const hasUnsaved = draft !== (accepted?.code ?? '') || (showingCandidate && !saved);
  const locked = disabled || !!busy || !!device.busy || !loaded;
  const generateLocked = !active || disabled || !!busy || !!device.busy || (!!pid && !loaded && !error);

  useEffect(() => { onBusy(!!busy); }, [busy, onBusy]);
  useEffect(() => {
    let live = true;
    // First dialogue may assign a board to a blank project or create a local
    // project. Keep the prompt/draft and its in-flight request during that change.
    if (pid && adopting.current === pid) {
      adopting.current = null;
      return () => { live = false; if (adopting.current !== current.current) abort.current?.abort(); };
    }
    setLoaded(false); setState(empty()); setDraft(''); setPrompt(''); setMessages([]); setError(''); setNotice(''); setPreview(null); setWifi(null); setWifiPlan(null); setOutput('');
    setCodeCandidate(null); setShowingCandidate(false); setSaveReview(false); setDraftSourceRevision(null); setSubmittedSources(null);
    if (pid) void api<LuaCodingCheckpoint>(`/projects/${pid}/lua-coding`).then(value => {
      if (!live) return;
      setState(value); setMessages(project?.messages.filter(m => m.intent === 'lua-coding') ?? []);
      setOutput(value.runs.at(-1)?.output ?? '');
      let local: { draft?: string; prompt?: string; candidate?: typeof codeCandidate; showingCandidate?: boolean; sourceRevision?: number } = {};
      try { local = JSON.parse(localStorage.getItem(draftKey(pid)) ?? '{}') as typeof local; } catch { /* invalid local draft */ }
      setDraft(typeof local.draft === 'string' ? local.draft : value.versions.find(v => v.revision === value.accepted)?.code ?? '');
      setPrompt(typeof local.prompt === 'string' ? local.prompt : '');
      if (local.candidate && typeof local.candidate.code === 'string' && Number.isInteger(local.candidate.revision)
          && ['ai','saved'].includes(local.candidate.source)) { setCodeCandidate(local.candidate); setShowingCandidate(local.showingCandidate === true); }
      setDraftSourceRevision(typeof local.sourceRevision === 'number' ? local.sourceRevision : value.accepted); setLoaded(true);
    }).catch(e => { if (live) setError(errorText(e)); });
    return () => { live = false; if (!adopting.current || adopting.current !== current.current) abort.current?.abort(); };
  }, [pid]);
  useEffect(() => {
    if (pid && loaded) try { localStorage.setItem(draftKey(pid), JSON.stringify({ draft, prompt, candidate: codeCandidate, showingCandidate, sourceRevision: draftSourceRevision })); }
    catch { setError('浏览器草稿无法保存，请保存代码或复制保留当前Lua。'); }
  }, [pid, loaded, draft, prompt, codeCandidate, showingCandidate, draftSourceRevision]);
  useEffect(() => { setWifi(null); setWifiPlan(null); setPreview(null); setNotice(''); setError(''); }, [device.state.connectionId]);

  const connectionId = device.state.connectionId;
  const uploadState = state.uploads.at(-1)?.state;
  const blockingRun = [...state.runs].reverse().find(r => r.transport === 'wifi' && ['submitted','outcome-unknown'].includes(r.state) && !state.runRecoveries?.some(a => a.runId === r.id));
  const latestRun = blockingRun;
  const runActive = blockingRun?.state === 'submitted';
  const pollScope = useRef({ active, pid, connectionId, deviceBusy: device.busy });
  pollScope.current = { active, pid, connectionId, deviceBusy: device.busy };
  // Only query an existing task. Never submit, reinstall or retry an unknown run.
  useEffect(() => {
    setResultError('');
    if (!active || !pid || !connectionId || !runActive || !latestRun) return;
    let live = true;
    const until = Date.now() + latestRun.timeoutMs + 20000;
    let timer: ReturnType<typeof setTimeout>;
    const read = async () => {
      if (!live) return;
      if (Date.now() > until) { setResultError('暂未读到最终结果，可在运行详情中继续查看。'); return; }
      if (running.current || pollScope.current.deviceBusy) { timer = setTimeout(() => void read(), 2000); return; }
      try {
        const value = await api<LuaCodingCheckpoint>('/mosaico/lua-wifi-refresh', 'POST', {
          projectId: pid, runId: latestRun.id, connectionId, requestId: requestId(),
        });
        if (!live || pollScope.current.pid !== pid || pollScope.current.connectionId !== connectionId) return;
        setState(previous => previous.runs.some(r => r.id === latestRun.id) && value.revision >= previous.revision ? value : previous);
        setOutput(value.runs.find(r => r.id === latestRun.id)?.output ?? '');
        const record = value.runs.find(r => r.id === latestRun.id);
        if (record?.state !== 'submitted') { setNotice(''); void onSaved(pid).catch(e => { if (live) setResultError(errorText(e)); }); return; }
        timer = setTimeout(() => void read(), 2000);
      } catch (e) { if (live) setResultError('结果读取中断：' + errorText(e)); }
    };
    timer = setTimeout(() => void read(), 2000);
    return () => { live = false; clearTimeout(timer); };
  }, [active, pid, connectionId, latestRun?.id, runActive]);
  // Reopening a project or reconnecting only reads readiness and file hashes.
  // It must never reinstall support or submit/retry a program.
  useEffect(() => {
    const check = ++wifiCheck.current;
    setWifi(null); setWifiError(''); setWifiChecking(false);
    if (!active || !pid || !loaded || !connectionId) return;
    let live = true;
    setWifiChecking(true);
    void api<LuaWifiStatus>(`/mosaico/lua-wifi-status?projectId=${pid}${accepted ? `&revision=${accepted.revision}` : ''}`).then(value => {
      if (live && check === wifiCheck.current && value.connectionId === connectionId) setWifi(value);
    }).catch(e => { if (live && check === wifiCheck.current) setWifiError(errorText(e)); })
      .finally(() => { if (live && check === wifiCheck.current) setWifiChecking(false); });
    return () => { live = false; };
  }, [active, pid, loaded, connectionId, accepted?.revision, uploadState, blockingRun?.id]);

  async function perform(label: string, work: (id: string) => Promise<void>) {
    if (!pid || running.current || locked) return;
    running.current = true; setBusy(label); setError(''); setNotice('');
    try { await work(pid); }
    catch (e) { if (current.current === pid) setError(errorText(e)); }
    finally {
      if (current.current === pid) {
        try { setState(await api<LuaCodingCheckpoint>(`/projects/${pid}/lua-coding`)); await onSaved(pid); }
        catch (e) { setError(errorText(e)); }
      }
      running.current = false; setBusy('');
    }
  }
  async function generate() {
    if (!prompt.trim() || generateLocked || running.current) return;
    const originalProject = project?.id;
    const text = prompt, protectDraft = draft !== (accepted?.code ?? '');
    let base = editorCode, id = pid;
    running.current = true; setBusy('正在准备编程对话'); setError(''); setNotice('');
    try {
      const session = await bootstrap();
      if (!session.aiConfigured) throw new Error('请打开「设置 → AI 设置」配置掌问模型；无需配置板载模型。');
      if (!scope.current.active || scope.current.projectId !== originalProject) return;
      const prepared = await prepareProject();
      if (!scope.current.active || scope.current.projectId !== originalProject) return;
      if (prepared.programmingMode !== 'chat-coding') throw new Error('当前主控尚未记录为 Mosaico，请重新选择主控后生成。');
      id = prepared.id;
      if (pid !== id) adopting.current = id;
      if (prepared !== project) onProjectPrepared(prepared);
      const checkpoint = await api<LuaCodingCheckpoint>(`/projects/${id}/lua-coding`);
      if (current.current !== id) return;
      setState(checkpoint); setLoaded(true);
      if (!loaded && !base.trim()) {
        base = checkpoint.versions.find(v => v.revision === checkpoint.accepted)?.code ?? '';
        setDraft(base); setDraftSourceRevision(checkpoint.accepted);
      }
      setBusy('掌问正在生成 Lua');
      const controller = new AbortController(); abort.current = controller; setStream(''); setSubmittedSources(null);
      try {
        const result = await chat(id, { message: text, code: base, boardId: prepared.boardId, componentIds: prepared.componentIds, intent: 'lua-coding' }, controller.signal,
          event => { if (current.current !== id) return; if (event.type === 'delta') setStream(v => v + event.content);
            if (event.type === 'references') setSubmittedSources({references:event.references,notice:event.notice}); });
        if (current.current === id) {
          setMessages(result.messages.filter(m => m.intent === 'lua-coding'));
          setPrompt(v => v === text ? '' : v);
          const reply = [...result.messages].reverse().find(m => m.role === 'assistant');
          const candidate = reply?.status === 'COMPLETED' ? replyCode(reply.content) : null;
          if (candidate !== null) {
            const latest = await api<LuaCodingCheckpoint>(`/projects/${id}/lua-coding`);
            if (current.current !== id) return;
            const version = [...latest.versions].reverse().find(v => v.source === 'ai' && v.code === candidate);
            setCodeCandidate({code:candidate,revision:version?.revision ?? 0,source:'ai'}); setShowingCandidate(!protectDraft);
            setBusy('正在自动保存 Lua');
            try {
              const stored = await saveGeneratedLua(api, id, loaded ? state : checkpoint, latest, candidate);
              if (current.current !== id) return;
              const accepted = stored.versions.find(v => v.revision === stored.accepted);
              if (!accepted || accepted.code !== candidate) throw new Error('未核对到生成代码的保存版本，请保留当前代码。');
              setState(stored);
              if (protectDraft) setCodeCandidate({code:candidate,revision:accepted.revision,source:'saved'});
              else { setDraft(candidate); setDraftSourceRevision(accepted.revision); setCodeCandidate(null); setShowingCandidate(false); }
              setNotice(protectDraft ? `生成代码已自动保存为V${accepted.revision}，手工草稿已保留。可查看已保存代码，再上传运行。`
                : `代码已自动保存为V${accepted.revision}。查看代码后，可点击「上传并运行」。`);
            } catch (e) { setError('自动保存未完成：' + errorText(e)); setNotice('生成代码已保留，请核对保存状态；不会自动重试。'); }
          }
          else setNotice('回复已保存；本次未生成完整代码，当前Lua版本保持。');
        }
      } finally { abort.current = null; setStream(''); }
    } catch (e) { if (current.current === id || scope.current.projectId === originalProject) setError(errorText(e)); }
    finally {
      if (id && current.current === id) {
        try { setState(await api<LuaCodingCheckpoint>(`/projects/${id}/lua-coding`)); setLoaded(true); await onSaved(id); }
        catch (e) { if (current.current === id) setError(errorText(e)); }
      }
      running.current = false; setBusy('');
    }
  }
  const save = () => perform('保存已接受 Lua', async id => {
    if (showingCandidate && draft.trim() && draft !== accepted?.code && !window.confirm('接受此生成稿会替换未保存手工稿。可先返回原稿保存。确定接受并保存生成稿？')) return;
    const value = await api<LuaCodingCheckpoint>(`/projects/${id}/lua-coding/save`, 'POST', { expectedRevision: state.revision, code: editorCode });
    setState(value); setDraft(editorCode); setDraftSourceRevision(value.accepted); setCodeCandidate(null); setShowingCandidate(false); setSaveReview(false);
    setNotice('Lua代码已保存，尚未上传或运行。');
  });
  const requestSave = async () => { if (saved && pid) await onSaved(pid); else if (showingCandidate) setSaveReview(true); else if (!draft.trim()) setError('Lua草稿为空，未保存。请填写代码或返回已保存版本。'); else await save(); };
  const viewVersion = (version: Pick<LuaVersion, 'code' | 'revision' | 'source'>) => { setCodeCandidate(accepted?.code === version.code ? accepted : version); setShowingCandidate(true); };
  const editCandidate = () => {
    if (!codeCandidate || (draft.trim() && draft !== accepted?.code && !window.confirm('用生成稿替换未保存手工稿用于编辑？可先返回原稿保存。'))) return;
    setDraft(codeCandidate.code); setDraftSourceRevision(codeCandidate.revision || null); setShowingCandidate(false);
  };
  const prepareUpload = () => perform('核对 Lua 上传清单', async id => {
    if (!saved || !accepted) throw new Error('当前修改尚未保存，请先保存代码。');
    setPreview(await device.run<LuaManifest>('读取上传目标', `/lua-manifest?projectId=${id}&revision=${accepted.revision}`));
  });
  const upload = () => perform('备份、上传并回读 Lua', async id => {
    if (!preview || !saved || accepted?.revision !== preview.revision) throw new Error('上传清单已过期。');
    if (preview.connectionId !== device.state.connectionId) throw new Error('设备连接已改变，请重新查看清单。');
    const result = await device.run<{ message: string }>('上传 Lua', '/lua-upload', 'POST', {
      projectId: id, revision: preview.revision, checksum: preview.checksum, expectedChecksum: preview.expectedChecksum,
    });
    setPreview(null); setNotice(result.message + ' 点击「WiFi运行 Lua」才会运行。');
  });
  const checkWifi = () => perform('检测WiFi运行服务', async () => {
    ++wifiCheck.current; setWifiChecking(false); setWifiError(''); setWifi(null);
    const result = await device.run<LuaWifiStatus>('检测WiFi运行', `/lua-wifi-status?projectId=${pid}${accepted ? `&revision=${accepted.revision}` : ''}`);
    setWifi(result); setNotice(result.message);
  });
  const prepareWifi = () => perform('读取WiFi初始化清单', async id => {
    setWifiPlan(await device.run<LuaWifiPlan>('读取初始化清单', '/lua-wifi-plan?projectId=' + id));
  });
  const installWifi = () => perform('备份并安装WiFi运行服务', async id => {
    if (!wifiPlan || wifiPlan.connectionId !== device.state.connectionId) throw new Error('初始化清单已过期，请重新读取。');
    await device.run<{message: string}>('安装WiFi运行服务', '/lua-wifi-install', 'POST', {projectId: id, planChecksum: wifiPlan.planChecksum});
    setWifiPlan(null); setWifi({ready:false, serviceReady:false, phase:'needs-restart', connectionId, message:'设置已安装，请重启设备后重新连接。'}); setNotice('设置已安装，请重启设备后重新连接。');
  });
  const rebootWifi = () => perform('提交设备重启', async () => {
    if (!window.confirm('重启Mosaico以加载WiFi运行服务，会中断设备当前任务与连接。确定重启？')) return;
    const result = await device.run<{message: string}>('重启设备', '/restart', 'POST');
    await device.run('读取连接状态', ''); setWifi(null); setNotice(result.message);
  });
  const run = () => perform('通过WiFi提交Lua运行', async id => {
    if (!saved || !accepted) throw new Error('请先保存代码并上传。');
    const value = await api<LuaCodingCheckpoint>(`/projects/${id}/lua-coding/wifi-run`, 'POST', {
      connectionId: device.state.connectionId, requestId: requestId(), revision: accepted.revision, timeoutMs,
    });
    setState(value); setOutput(value.runs.at(-1)?.output ?? '');
    setNotice('运行已提交，正在自动读取结果。');
  });
  const uploadAndRun = () => perform('准备上传并运行…', async id => {
    if (!saved || !accepted || !connectionId || blockingRun) throw new Error('请先保存代码，并等待当前运行结束。');
    const value = await uploadAndRunLua(api, { projectId: id, revision: accepted.revision, checksum: accepted.checksum,
      connectionId, timeoutMs, progress: setBusy });
    if (current.current === id) { setState(value); setOutput(value.runs.at(-1)?.output ?? ''); setNotice('运行已提交，正在自动读取结果。'); }
  });
  const refreshRun = (runId: string) => perform('读取WiFi运行结果', async id => {
    const value = await device.run<LuaCodingCheckpoint>('读取运行结果', '/lua-wifi-refresh', 'POST', {projectId: id, runId});
    setState(value); setOutput(value.runs.find(r => r.id === runId)?.output ?? '');
    setNotice('已读取设备任务状态与原始输出，实物结果请另行观察。');
  });
  const recoverRun = (runId: string) => perform('核对并归档旧运行', async id => {
    if (!wifi?.bootId || !wifi.recoverableRunIds?.includes(runId)) throw new Error('请先重新检测设备，确认新的启动周期。');
    if (!window.confirm('已检测到原设备地址的新启动周期。归档旧运行会保留其未知结果，不会重发；之后须另行点击运行新任务。确定归档？')) return;
    const body: RecoverLuaRun = {projectId:id,runId,connectionId:connectionId!,bootId:wifi.bootId,requestId:requestId(),confirmed:true};
    setState(await api<LuaCodingCheckpoint>('/mosaico/lua-wifi-recover','POST',body)); setResultError('');
    setNotice('旧运行已归档，原始结果保持未知。可另行点击上传并运行。');
  });
  const runBlockedReason = !pid ? '先生成代码，生成后会自动保存。' : !loaded ? '正在读取项目。'
    : !connectionId ? '请先连接Mosaico。' : busy ? busy : device.busy ? device.busy
    : disabled ? '请等待当前操作完成。' : !saved ? '当前修改尚未保存，请保存代码或查看已保存版本。'
    : wifiChecking ? '正在自动检测WiFi服务并回读Lua文件…' : wifiError ? `检测失败：${wifiError}`
    : blockingRun ? '上次运行尚未核对，请查看运行结果。' : !wifi?.ready ? wifi?.message ?? '请检测设备连接。' : '';
  const uploadAndRunBlockedReason = !pid ? '先描述需求并生成代码。' : !loaded ? '正在读取项目…'
    : !connectionId ? '请先连接设备。' : busy ? busy : device.busy ? device.busy : disabled ? '请等待当前操作完成。'
    : !saved ? '请保存当前修改，或查看已保存代码。' : runActive ? '程序正在运行，请等待结果。'
    : blockingRun ? '上次运行结果待核对，请在运行详情中查看。'
    : wifiChecking ? '正在检查连接…' : wifiError ? `连接检测失败：${wifiError}`
    : !wifi?.serviceReady ? '请先完成下方的WiFi运行设置。' : '';
  return { state, draft, setDraft, prompt, setPrompt, messages, busy, error, notice, locked, saved, accepted, preview, setPreview, stream,
    generate, generateLocked, save, prepareUpload, upload, wifi, wifiPlan, setWifiPlan, checkWifi, prepareWifi, installWifi, rebootWifi, refreshRun, output, timeoutMs, setTimeoutMs, run,
    wifiChecking, wifiError, runBlockedReason, uploadAndRun, uploadAndRunBlockedReason, runActive, resultError,
    codeCandidate, showingCandidate, editorCode, hasUnsaved, draftSourceRevision, submittedSources, saveReview, setSaveReview,
    requestSave, viewVersion, editCandidate, returnToDraft: () => setShowingCandidate(false), recoverRun, blockingRun,
    clearError: () => setError(''), cancel: () => abort.current?.abort(), ready: !!pid && loaded };
}

type LuaController = ReturnType<typeof useLuaCoding>;
export function LuaConversation({ lua, mobileTab, onSettings, onSource, picker }: { lua: LuaController; mobileTab: string; onSettings: () => void; onSource: () => void; picker?: ReactNode }) {
  return <section className={`ai-panel panel native-chat-panel mobile-${mobileTab === 'ai' ? 'show' : 'hide'}`} aria-label="掌问Lua编程对话">
    <div className="panel-head"><h2><Sparkles size={18}/>掌问 · 编程助手</h2><button className="api-settings-entry" onClick={onSettings} disabled={!!lua.busy}>AI 设置</button></div>
    {picker ?? <details className="lua-source"><summary>编程方式 · 掌问模型</summary><label>编程来源<select aria-label="编程来源" value="local" disabled={!!lua.busy} onChange={onSource}><option value="local">掌问模型生成 Lua（推荐）</option><option value="device">设备原生 Claw</option></select></label></details>}
    <div className="messages" role="log" aria-label="掌问Lua对话">
      <section className="conversation-board-context"><Sparkles size={24}/><div><strong>说说你想让 Mosaico 做什么</strong><p>生成代码 → 自动保存 → 上传并运行。生成代码会带中文注释；手工修改后请保存。已有手工草稿会保留，上传运行由你点击。</p></div></section>
      {lua.messages.map(m => { const reply=replyView(m.content); return <article key={m.id} className={`message ${m.role}`}><strong>{m.role === 'user' ? '你' : '掌问 AI'}</strong>{m.role==='assistant'?<><p>{reply.summary}</p>{reply.points.length>0&&<ul>{reply.points.map((p,i)=><li key={i}>{p}</li>)}</ul>}{reply.question&&<p>{reply.question.text}</p>}{reply.question?.options.map(option=><button key={option} disabled={lua.locked} onClick={()=>lua.setPrompt(option)}>{option}</button>)}{reply.details&&<details><summary>详情</summary><pre>{reply.details}</pre></details>}<details><summary>原始回复</summary><pre>{m.content}</pre></details></>:<pre>{m.content}</pre>}{m.role === 'assistant' && m.status === 'COMPLETED' && replyCode(m.content) !== null && <button disabled={lua.locked} onClick={() => { const code=replyCode(m.content)!; const version=lua.state.versions.find(v=>v.source==='ai'&&v.code===code); lua.viewVersion({code,revision:version?.revision??0,source:'ai'}); }}>查看代码</button>}{m.role==='assistant' && <ReferenceSources references={m.references} notice={m.referenceNotice}/>}</article>; })}
      {lua.busy && lua.submittedSources && <ReferenceSources references={lua.submittedSources.references} notice={lua.submittedSources.notice}/>}
      {lua.stream && <article className="message assistant"><strong>正在生成</strong><pre>{streamText(lua.stream)}</pre></article>}
    </div>
    {lua.error && <p className="chat-error" role="alert">{lua.error}</p>}{lua.notice && <p className="chat-hint" role="status">{lua.notice}</p>}
    {!lua.ready && <p className="chat-hint">直接描述需求即可生成；主控和模块会自动记录，无需先载入示例或连接设备。</p>}
    <form className="chat-form" onSubmit={e => { e.preventDefault(); void lua.generate(); }}>
      <label className="sr-only" htmlFor="lua-prompt">Lua编程需求</label><textarea id="lua-prompt" value={lua.prompt} maxLength={4000} disabled={lua.generateLocked} placeholder="描述想让 Mosaico 完成的一个小任务…" onChange={e => lua.setPrompt(e.target.value)} onKeyDown={e => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing) { e.preventDefault(); void lua.generate(); } }}/>
      <div><span>{lua.busy || '生成后自动保存 · 自己修改后请点保存'}</span>{lua.busy.includes('生成') && <button type="button" onClick={lua.cancel}>取消生成</button>}<button className="primary icon-button" aria-label="使用掌问模型生成Lua" disabled={lua.generateLocked || !lua.prompt.trim()}><ArrowUp size={20}/></button></div>
    </form>
  </section>;
}

export function LuaProgram({ lua, connected, onConnect, observations, saveState, folderError, onRetryFolder }: {
  lua: LuaController; connected: boolean; onConnect: () => void; observations: ReactNode;
  saveState: string; folderError: string; onRetryFolder: () => void;
}) {
  const [panel, setPanel] = useState<'results' | 'settings' | 'observations' | 'status' | null>(null);
  const [zoom, setZoom] = useState(100), [fullscreen, setFullscreen] = useState(false);
  useEffect(() => {
    if (!fullscreen) return;
    const escape = (e: KeyboardEvent) => { if (e.key === 'Escape' && !document.querySelector('dialog[open]')) setFullscreen(false); };
    document.addEventListener('keydown', escape);
    return () => document.removeEventListener('keydown', escape);
  }, [fullscreen]);
  const last = lua.state.runs.at(-1);
  const archived = !!last && lua.state.runRecoveries?.some(r=>r.runId===last.id);
  const result = archived ? '旧运行已归档，原始结果仍待核对' : last?.state === 'outcome-unknown' ? '运行结果待核对'
    : last?.deviceState === 'done' ? '设备报告运行结束，请查看实物效果'
    : last?.deviceState === 'timeout' ? '已达到时限，可在运行设置中调整'
    : last?.deviceState === 'failed' || last?.deviceState === 'rejected' ? '运行失败，请查看错误'
    : last?.state === 'returned' ? '运行已返回，请查看运行结果'
    : lua.runActive ? '程序正在运行，结果将自动更新…' : '';
  const statusText = lua.busy || lua.error || lua.resultError || folderError || [lua.saved ? `V${lua.accepted?.revision} 已保存` : lua.showingCandidate ? '生成稿预览 · 未保存为当前版本' : '手工草稿 · 未保存', last ? `上次 V${last.revision}：${result}` : '', lua.uploadAndRunBlockedReason || '可以上传并运行'].filter(Boolean).join(' · ');
  const resultBadge = archived ? '已归档' : last?.state==='outcome-unknown' ? '待核对' : lua.runActive ? '运行中' : last?.deviceState==='failed'||last?.deviceState==='rejected' ? '失败' : last?.deviceState==='timeout' ? '超时' : '查看';
  const needsSetup = connected && !lua.wifiChecking && (lua.wifi?.phase === 'needs-install' || lua.wifi?.phase === 'needs-restart');
  return <div className={`lua-code-workspace ${fullscreen ? 'lua-code-fullscreen' : ''}`}>
    <div className="filebar lua-filebar"><span><FileCode2 size={16}/>main.lua</span><span className="filebar-space"/>
      <select className="code-version-select" aria-label="Lua历史版本" disabled={lua.locked} value={lua.showingCandidate ? lua.codeCandidate?.revision || 'candidate' : 'draft'} onChange={e => { if(e.target.value==='draft') lua.returnToDraft(); else {const v=lua.state.versions.find(v=>v.revision===Number(e.target.value));if(v)lua.viewVersion(v);} }}><option value="draft">{lua.saved ? `V${lua.accepted?.revision} · 已保存` : lua.draftSourceRevision ? `基于 V${lua.draftSourceRevision} 的草稿` : '手工草稿'}</option>{lua.showingCandidate && !lua.codeCandidate?.revision && <option value="candidate">新生成稿 · 待接受</option>}{[...lua.state.versions].reverse().map(v => <option key={v.revision} value={v.revision}>V{v.revision} · {v.source === 'ai' ? 'AI生成稿' : '已保存'}</option>)}</select>
      <button className="icon-button" title="保存代码修改（生成代码自动保存）" aria-label="保存代码修改" disabled={lua.locked || !lua.editorCode.trim() || lua.saved} onClick={() => void lua.save()}><Save size={16}/></button>
      <div className="editor-view-controls"><button aria-label="缩小代码" title="缩小代码" disabled={zoom <= 80} onClick={() => setZoom(v => Math.max(80, v-10))}><ZoomOut size={16}/></button><span aria-label="代码字号比例">{zoom}%</span><button aria-label="放大代码" title="放大代码" disabled={zoom >= 160} onClick={() => setZoom(v => Math.min(160, v+10))}><ZoomIn size={16}/></button><button aria-label={fullscreen ? '退出代码全屏' : '代码全屏'} title="代码全屏" onClick={() => setFullscreen(v => !v)}>{fullscreen ? <Minimize size={16}/> : <Maximize size={16}/>}</button></div>
      <ActionMenu label="代码工具" align="right" items={[
        {label:'查看完整状态',icon:Eye,onSelect:()=>setPanel('status')},
        {label:'运行结果',icon:Terminal,onSelect:()=>setPanel('results')},
        {label:'运行设置',icon:Settings,onSelect:()=>setPanel('settings')},
        {label:'我的实际观察',icon:Eye,onSelect:()=>setPanel('observations')},
        {label:'放大代码',icon:ZoomIn,disabled:zoom >= 160,onSelect:()=>setZoom(v=>Math.min(160,v+10))},
        {label:'缩小代码',icon:ZoomOut,disabled:zoom <= 80,onSelect:()=>setZoom(v=>Math.max(80,v-10))},
        {label:'仅上传代码',icon:Upload,disabled:lua.locked || !lua.saved || !connected,onSelect:()=>void lua.prepareUpload()},
        {label:'重新检测连接',icon:Wifi,disabled:lua.locked || !lua.ready || !connected || lua.wifiChecking,onSelect:()=>void lua.checkWifi()},
        ...(!connected ? [{label:'连接设备',icon:Wifi,onSelect:onConnect}] : []),
      ]}><MoreHorizontal size={18}/></ActionMenu>
    </div>
    <div className="lua-editor-status" role="status"><button className="lua-status-summary" aria-label="查看完整状态" title={statusText} onClick={()=>setPanel('status')}>{statusText}</button>{needsSetup && <button disabled={lua.locked} onClick={() => void (lua.wifi?.phase === 'needs-restart' ? lua.rebootWifi() : lua.prepareWifi())}>{lua.wifi?.phase === 'needs-restart' ? '重启设备' : '设置WiFi运行'}</button>}{folderError && <button disabled={lua.locked} onClick={onRetryFolder}>重试同步</button>}{last && <button title={result} onClick={()=>setPanel('results')}>结果：{resultBadge}</button>}</div>
    {lua.codeCandidate && <div className="lua-candidate-bar" role="note"><span>{lua.codeCandidate.source === 'saved' ? '生成版本已保存 · 手工草稿保留' : lua.showingCandidate ? '生成稿预览 · 原稿保留' : '新生成稿已保留'}</span>{lua.showingCandidate ? <><button disabled={lua.locked} onClick={lua.returnToDraft}>返回原稿</button><button disabled={lua.locked} onClick={lua.editCandidate}>采用并编辑</button>{!lua.saved && <button className="primary" disabled={lua.locked} onClick={()=>void lua.save()}>接受并保存</button>}</> : <button disabled={lua.locked} onClick={()=>lua.viewVersion(lua.codeCandidate!)}>{lua.codeCandidate.source === 'saved' ? '查看已保存代码' : '查看新生成稿'}</button>}</div>}
    <Editor value={lua.editorCode} onChange={lua.setDraft} readOnly={lua.locked || lua.showingCandidate} language="lua" label="Lua代码编辑器" zoom={zoom}/>
    {panel==='status' && <Dialog title="当前编程状态" onClose={()=>setPanel(null)}><p>{statusText}</p><p>{saveState}</p><div className="lua-actions">{!connected ? <button onClick={()=>{setPanel(null);onConnect();}}>连接设备</button> : <button disabled={lua.locked || lua.wifiChecking} onClick={()=>void lua.checkWifi()}>重新检测连接</button>}{last && <button onClick={()=>setPanel('results')}>查看运行结果</button>}</div></Dialog>}
    {lua.saveReview && <Dialog title="接受并保存生成稿 Lua" onClose={()=>lua.setSaveReview(false)}><p>当前显示的是生成稿。明确接受后才成为项目当前Lua版本；不会上传或运行。</p><div className="lua-actions"><button onClick={()=>lua.setSaveReview(false)}>继续审阅</button><button className="primary" disabled={lua.locked} onClick={()=>void lua.save()}>接受并保存</button></div></Dialog>}
    {panel === 'results' && <Dialog title="运行结果" onClose={()=>setPanel(null)}><div className="lua-dialog-content">
      {result && <p role="status">V{last?.revision} · {result}</p>}
    <section className="lua-run-details">
      <pre className="lua-console" aria-label="Lua运行输出">{lua.output || '尚无运行输出。'}</pre>
      {last?.transport === 'wifi' && <button disabled={lua.locked || !connected} onClick={() => void lua.refreshRun(last.id)}>查看最新结果</button>}
      {lua.blockingRun && <section className="lua-recovery"><p>上次运行未完成核对，不会重发。新启动周期可核对并归档，原始结果仍保持未知。</p><button disabled={lua.locked || !connected || lua.wifiChecking} onClick={()=>void lua.checkWifi()}>检测设备启动周期</button>{lua.wifi?.recoverableRunIds?.includes(lua.blockingRun.id) && <button disabled={lua.locked} onClick={()=>void lua.recoverRun(lua.blockingRun!.id)}>核对并归档旧运行</button>}</section>}
      <p className="muted">设备输出与实际效果分开记录。断开连接不会停止设备上的程序。</p>
    <details><summary>上传与运行记录</summary>{lua.state.wifiSetups?.map(s => <p key={s.id}>WiFi运行服务安装 · {s.state === 'verified' ? '文件回读校验通过，不代表已启动' : '结果待核对，不会自动重发'}</p>)}{[...lua.state.uploads].reverse().map(u => <p key={u.id}>上传 V{u.revision} · {u.state === 'verified' ? '回读校验通过' : '结果待核对，不会自动重发'}<br/><small>{u.path} · {u.createdAt}</small></p>)}{[...lua.state.runs].reverse().map(r => <article key={r.id}><p>{r.transport === 'wifi' ? 'WiFi' : 'USB历史'}运行 V{r.revision} · {r.deviceState ?? (r.state === 'returned' ? '控制台已返回，请核对输出' : '运行结果待核对')} · 时限{r.timeoutMs/1000}秒</p>{r.transport === 'wifi' && !lua.state.runRecoveries?.some(a=>a.runId===r.id) && <button disabled={lua.locked || !connected} onClick={() => void lua.refreshRun(r.id)}>读取运行结果</button>}<pre>{r.output}</pre>{lua.state.runRecoveries?.filter(a=>a.runId===r.id).map(a=><p key={a.id}>已核对新启动周期并归档 · {a.createdAt}；原始运行结果未改写。</p>)}</article>)}</details>
    </section></div></Dialog>}
    {panel === 'settings' && <Dialog title="运行设置" onClose={()=>setPanel(null)}><div className="lua-dialog-content">
      <div className="lua-actions"><label>最长运行时间<select aria-label="Lua运行时限" value={lua.timeoutMs} disabled={lua.locked} onChange={e => lua.setTimeoutMs(Number(e.target.value))}>{[5000,10000,30000,60000].map(ms => <option key={ms} value={ms}>{ms/1000}秒</option>)}</select></label></div>
      <p className="muted">默认30秒，超过后由设备结束任务；包含绘图等耗时。</p>
      <div className="lua-actions"><button disabled={lua.locked || !lua.ready || !connected || lua.wifiChecking} onClick={() => void lua.checkWifi()}><Wifi size={15}/>重新检测连接</button><button disabled={lua.locked || !lua.saved || !connected} onClick={() => { setPanel(null); void lua.prepareUpload(); }}><Upload size={15}/>仅上传代码</button><button disabled={!!lua.runBlockedReason || !!lua.blockingRun} onClick={() => void lua.run()}>仅运行已上传代码</button></div>
      <details><summary>WiFi运行设置</summary><div className="lua-actions"><button disabled={lua.locked || !lua.ready || !connected} onClick={() => { setPanel(null); void lua.prepareWifi(); }}>查看安装清单</button><button disabled={lua.locked || !connected} onClick={() => void lua.rebootWifi()}>重启设备</button></div></details>
    </div></Dialog>}
    {panel === 'observations' && <Dialog title="我的实际观察" onClose={()=>setPanel(null)}>{observations}</Dialog>}
    {lua.preview && <Dialog title="确认 Lua 上传清单" onClose={() => { if (!lua.busy) lua.setPreview(null); }}><p>仅写入以下1个Lua文件；覆盖前备份，写后回读。上传不会运行。</p><p>V{lua.preview.revision} · {lua.preview.size}字节</p><p>文件：{lua.preview.path}</p><details className="classroom-details"><summary>查看文件校验信息</summary><p>SHA256 {lua.preview.checksum}</p></details><p>{lua.preview.expectedChecksum ? '设备已有此文件，核对后备份并覆盖。' : '设备目标尚不存在，将创建文件。'}</p><div className="lua-actions"><button disabled={!!lua.busy} onClick={() => lua.setPreview(null)}>取消</button><button className="primary" disabled={!!lua.busy} onClick={() => void lua.upload()}>确认上传 Lua</button></div></Dialog>}
    {lua.wifiPlan && <Dialog title="设置WiFi运行" onClose={() => { if (!lua.busy) lua.setWifiPlan(null); }}><p>仅安装以下2份文件：固定Lua运行服务、专用启动规则。保留现有{lua.wifiPlan.preservedRules}条规则，写前备份并回读。安装不重启，也不运行项目代码。</p>{lua.wifiPlan.files.map(f => <details key={f.path}><summary>{f.path} · {f.size}字节</summary><p>SHA256 {f.checksum}</p><pre>{f.content}</pre></details>)}<p>安装完成后，重启设备并重新连接即可。以后不用重复设置。</p><div className="lua-actions"><button disabled={!!lua.busy} onClick={() => lua.setWifiPlan(null)}>取消</button><button className="primary" disabled={!!lua.busy} onClick={() => void lua.installWifi()}>安装并继续</button></div></Dialog>}
  </div>;
}
