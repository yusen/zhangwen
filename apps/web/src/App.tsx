import { useCallback, useEffect, useRef, useState } from 'react';
import { ArrowUp, BookOpen, Check, CheckCheck, ChevronRight, CircuitBoard, Download, FileCode2, Files, FolderOpen, HelpCircle, LoaderCircle, Plus, Save, Search, Sparkles, Square, Terminal, Unplug, Usb, X, Play, ZoomIn, ZoomOut, Cable, AlignLeft, Moon, Sun, Power, Settings } from 'lucide-react';
import type { AiSettings, ChatMessage, CheckResult, CreateProject, HardwareDetail, HardwareSummary, Project, ProjectSummary, UploadManifest, Version } from '../../../packages/contracts/src/mu';
import { DEFAULT_AI_MODEL } from '../../../packages/contracts/src/mu';
import { api, bootstrap } from './api';
import { MicroPythonDevice, serialApi } from './serial';
import { latestBackup, persistBackup } from './backups';
import { Editor, type EditorHandle } from './Editor';
import { Dialog } from './Dialog';
import { AiSettingsDialog } from './AiSettingsDialog';
import { MuTool } from './MuTool';
import { moduleDirection, sensorFamily, modulesForBoard, type ModuleDirection } from './hardwareLibrary';
import { HardwareDetails } from './HardwareDetails';
import { ModuleCard } from './ModuleCard';
import { BoardPicker } from './BoardPicker';
import { DeviceFilesDialog } from './DeviceFilesDialog';

const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);
function download(name: string, value: string | Uint8Array) {
  const data = typeof value === 'string' ? value : new Uint8Array(value).buffer;
  const url = URL.createObjectURL(new Blob([data], { type: 'application/octet-stream' }));
  const link = document.createElement('a'); link.href = url; link.download = name; link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function stored(key: string): string | null { try { return localStorage.getItem(key); } catch { return null; } }
function store(key: string, value: string) { try { localStorage.setItem(key, value); } catch { /* a draft failure is reported separately on edits */ } }
function scratchHardware(): { board: string; components: string[] } {
  try {
    const value: unknown = JSON.parse(stored('mu-scratch-hardware') ?? 'null');
    if (value && typeof value === 'object' && 'board' in value && typeof value.board === 'string' && 'components' in value && Array.isArray(value.components) && value.components.every(id => typeof id === 'string')) return { board: value.board, components: value.components };
  } catch { /* ignore invalid browser metadata */ }
  return { board: '', components: [] };
}
const categoryName: Record<HardwareSummary['category'], string> = { MCU: '主控板', SENSOR: '传感器', ACTUATOR: '执行器', DISPLAY: '显示', POWER: '电源', STRUCTURE: '结构' };

export default function App() {
  const [hardware, setHardware] = useState<HardwareSummary[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [code, setCode] = useState(() => stored('mu-scratch-code') ?? '');
  const [name, setName] = useState('未命名项目');
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const [board, setBoard] = useState(() => scratchHardware().board);
  const [components, setComponents] = useState<string[]>(() => scratchHardware().components);
  const [search, setSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState<ModuleDirection | 'all'>('all');
  const [detail, setDetail] = useState<HardwareDetail | null>(null);
  const [moduleSample, setModuleSample] = useState<{ item: HardwareSummary; code: string; base: string } | null>(null);
  const [sensorPicker, setSensorPicker] = useState(false);
  const [pendingSensors, setPendingSensors] = useState<string[]>([]);
  const [returnToPicker, setReturnToPicker] = useState(false);
  const [newDialog, setNewDialog] = useState(false);
  const [newName, setNewName] = useState('我的项目');
  const [newBoard, setNewBoard] = useState('');
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [filesDialog, setFilesDialog] = useState(false);
  const [fileVersions, setFileVersions] = useState<Version[] | null>(null);
  const [uploadAfterSave, setUploadAfterSave] = useState(false);
  const [manifest, setManifest] = useState<UploadManifest | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [aiConfigured, setAiConfigured] = useState(false);
  const [aiModel, setAiModel] = useState<string>(DEFAULT_AI_MODEL);
  const [aiSettingsDialog, setAiSettingsDialog] = useState(false);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [candidate, setCandidate] = useState<{ code: string; base: string } | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const sendingMessage = useRef(false);
  const [pendingPrompt, setPendingPrompt] = useState('');
  const [chatError, setChatError] = useState('');
  const [logs, setLogs] = useState('尚未连接设备。使用桌面 Chrome / Edge 打开本机页面，然后点击「连接设备」。\n');
  const [repl, setRepl] = useState('');
  const [progress, setProgress] = useState<number | null>(null);
  const [, redraw] = useState(0);
  const [mobileTab, setMobileTab] = useState('code');
  const [boardDialog, setBoardDialog] = useState(false);
  const [loadDialog, setLoadDialog] = useState(false);
  const [wiringDialog, setWiringDialog] = useState(false);
  const [helpDialog, setHelpDialog] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => stored('mu-theme') === 'dark' ? 'dark' : 'light');
  const [workspaceClosed, setWorkspaceClosed] = useState(false);
  const editor = useRef<EditorHandle>(null);
  useEffect(() => { document.documentElement.dataset.theme = theme; store('mu-theme', theme); }, [theme]);
  const device = useRef<MicroPythonDevice | null>(null);
  const releasePort = useRef<(() => void) | null>(null);
  const dirty = project ? (code !== project.code || name !== project.name || board !== project.boardId || JSON.stringify(components) !== JSON.stringify(project.componentIds)) : code.length > 0 || components.length > 0;
  const deviceState = device.current?.state ?? 'disconnected';
  const connected = deviceState === 'connected';
  const running = deviceState === 'running';
  const deviceBusy = deviceState === 'busy' || deviceState === 'connecting';
  const boardInfo = hardware.find(item => item.componentId === board);
  const currentCode = useRef(code); currentCode.current = code;
  const currentProject = useRef(project?.id); currentProject.current = project?.id;
  const dirtyRef = useRef(dirty); dirtyRef.current = dirty;
  const busyRef = useRef(busy); busyRef.current = busy;
  const addLog = useCallback((text: string) => { setLogs(value => (value + text).slice(-60_000)); }, []);

  const action = async (label: string, task: () => Promise<unknown>) => {
    setBusy(label); setError(''); setNotice('');
    try { await task(); } catch (err) { setError(errorText(err)); } finally { setBusy(''); }
  };
  const openAiSettings = () => void action('读取 API 设置', async () => { const settings = await api<AiSettings>('/settings/ai'); setAiConfigured(settings.aiConfigured); setAiModel(settings.aiModel); setAiSettingsDialog(true); });
  const applyProject = (value: Project, restoreDraft = true) => {
    setProject(value); setName(value.name); setBoard(value.boardId); setComponents(value.componentIds); setDraftRevision(null);
    setMessages(value.messages); setCandidate(null); setCheck(null); setChatError(''); store('mu-active-project', value.id);
    let draft: { code: string; name: string; board: string; components: string[]; baseRevision: number } | null = null;
    try { draft = JSON.parse(stored('mu-draft-' + value.id) ?? 'null'); } catch { /* invalid draft */ }
    if (restoreDraft && draft && typeof draft.code === 'string' && typeof draft.name === 'string' && typeof draft.board === 'string' && Array.isArray(draft.components)) {
      setCode(draft.code); setName(draft.name); setBoard(draft.board); setComponents(draft.components); setDraftRevision(draft.baseRevision);
      setNotice(draft.baseRevision !== value.revision ? '发现本地草稿，但服务端版本已更新。先导出草稿，再核对版本。' : '已恢复本地草稿；保存后才成为项目版本。');
    } else setCode(value.code);
  };
  const refreshProjects = async () => setProjects((await api<{ projects: ProjectSummary[] }>('/projects')).projects);
  const persistDraftNow = () => {
    if (project && dirty) store('mu-draft-' + project.id, JSON.stringify({ code, name, board, components, baseRevision: draftRevision ?? project.revision }));
  };
  const openSave = () => { setNewName(name === '未命名项目' ? '我的项目' : name); setNewBoard(board); setNewDialog(true); };
  const openNew = () => {
    if (dirty && !window.confirm('当前项目有未保存更改。确定开始一个新项目吗？建议先保存当前项目。')) return;
    persistDraftNow();
    try { localStorage.removeItem('mu-active-project'); } catch { /* unavailable */ }
    setProject(null); setName('未命名项目'); setCode(''); setComponents([]); setDraftRevision(null);
    setMessages([]); setCandidate(null); setCheck(null); setChatError(''); setError(''); setNotice('新项目已就绪。添加模块或编写代码，点击「保存」命名保存。');
    setMobileTab('code');
  };
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const session = await bootstrap();
        const [catalog, list] = await Promise.all([api<{ skills: HardwareSummary[] }>('/hardware'), api<{ projects: ProjectSummary[] }>('/projects')]);
        if (!active) return;
        setAiConfigured(session.aiConfigured); setAiModel(session.aiModel ?? DEFAULT_AI_MODEL); setHardware(catalog.skills); setProjects(list.projects);
        const scratch = scratchHardware();
        const initialBoard = catalog.skills.find(item => item.componentId === scratch.board && item.category === 'MCU') ?? catalog.skills.find(item => item.componentId === 'hw_seeed_xiao_esp32s3_sense') ?? catalog.skills.find(item => item.category === 'MCU');
        setBoard(initialBoard?.componentId ?? '');
        const selected = list.projects.find(item => item.id === stored('mu-active-project'));
        if (selected) { const value = await api<Project>('/projects/' + selected.id); if (active) applyProject(value); }
      } catch (err) { if (active) setError(errorText(err)); } finally { if (active) setLoading(false); }
    })();
    return () => { active = false; };
  }, []);
  useEffect(() => {
    if (loading) return;
    if (!project) {
      try { localStorage.setItem('mu-scratch-code', code); localStorage.setItem('mu-scratch-hardware', JSON.stringify({ board, components })); }
      catch { setError('浏览器草稿无法保存，请立即保存到本机服务或导出代码。'); }
      return;
    }
    if (!dirty) return;
    const timer = setTimeout(() => {
      try { localStorage.setItem('mu-draft-' + project.id, JSON.stringify({ code, name, board, components, baseRevision: draftRevision ?? project.revision })); }
      catch { setError('浏览器草稿无法保存，请立即保存到本机服务或导出代码。'); }
    }, 250);
    return () => clearTimeout(timer);
  }, [code, name, board, components, project, dirty, draftRevision, loading]);
  useEffect(() => {
    const prevent = (event: BeforeUnloadEvent) => {
      if (dirtyRef.current || device.current?.state === 'busy') { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, []);
  const save = async () => {
    if (sendingMessage.current && !project) { setNotice('正在准备首次对话项目，请稍后保存。'); return; }
    if (!project) { openSave(); return; }
    const saved = await api<Project>('/projects/' + project.id, 'PUT', { code, name, boardId: board, componentIds: components, expectedRevision: draftRevision ?? project.revision });
    try { localStorage.removeItem('mu-draft-' + project.id); } catch { /* unavailable */ }
    applyProject(saved, false); await refreshProjects(); setNotice(`已保存到本机 · 版本 ${saved.revision}`);
    return saved;
  };
  const saveRef = useRef(save); saveRef.current = save;
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); if (!busyRef.current) void action('保存', () => saveRef.current()); } };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, []);
  const chooseProject = async (id: string) => {
    if (id === project?.id) return true;
    if (dirty && !window.confirm('当前修改尚未保存。草稿保留在本浏览器；仍要切换项目吗？')) return false;
    persistDraftNow();
    let opened = false;
    await action('打开项目', async () => { applyProject(await api<Project>('/projects/' + id)); opened = true; });
    return opened;
  };
  const openDetail = (item: HardwareSummary, fromPicker = false) => void action('读取资料', async () => {
    const value = await api<HardwareDetail>('/hardware/' + item.skillName);
    setReturnToPicker(fromPicker); if (fromPicker) setSensorPicker(false); setDetail(value);
  });
  const openSensorPicker = () => { setSearch(''); setModuleFilter('all'); setPendingSensors([]); setSensorPicker(true); };
  const loadModuleSample = (item: HardwareSummary) => void action('读取模块示例', async () => {
    const value = await api<HardwareDetail>('/hardware/' + item.skillName);
    const samples = value.files.filter(file => file.path.startsWith('examples/'));
    const pythonFile = samples.find(file => file.path.endsWith('.py'));
    const blocks = samples.flatMap(file => [...file.content.matchAll(/```(?:python|micropython|py)\s*\n([\s\S]*?)```/g)].map(match => match[1]));
    const sample = pythonFile?.content ?? blocks[0];
    if (!sample?.trim()) { setNotice('此模块资料包尚无可直接载入的 Python 示例，请查看完整资料。'); return; }
    setModuleSample({ item, code: sample.trimEnd() + '\n', base: code });
  });

  const connectDevice = async () => {
    const serial = serialApi();
    if (!serial || !window.isSecureContext || !navigator.locks) { setError('Web Serial 需要桌面 Chrome/Edge 和 localhost 安全上下文。'); return; }
    setError(''); setBusy('选择并连接设备');
    try {
      // requestPort runs directly in the click gesture before awaiting anything.
      const port = await serial.requestPort();
      await new Promise<void>((resolve, reject) => {
        void navigator.locks.request('zhangwen-web-serial', { ifAvailable: true }, async lock => {
          if (!lock) { reject(new Error('另一个掌问标签正在使用串口，请先在那里断开。')); return; }
          const held = new Promise<void>(done => { releasePort.current = done; });
          const next = new MicroPythonDevice(port, addLog, () => redraw(value => value + 1));
          device.current = next;
          try { await next.connect(); resolve(); await held; }
          catch (err) { releasePort.current?.(); device.current = null; reject(err); }
        }).catch(reject);
      });
    } catch (err) { if (!(err instanceof DOMException && err.name === 'NotFoundError')) setError(errorText(err)); }
    finally { setBusy(''); }
  };
  const disconnect = () => void action('断开设备', async () => { await device.current?.disconnect(); device.current = null; releasePort.current?.(); releasePort.current = null; redraw(value => value + 1); });
  const showUploadPlan = async (saved: Project) => {
    if (device.current?.state !== 'connected') throw new Error('先连接设备并停止程序。');
    const plan = await api<UploadManifest>(`/projects/${saved.id}/upload-manifest`, 'POST', { expectedRevision: saved.revision });
    setManifest(plan); setConfirmed(false);
  };
  const prepareUpload = async () => {
    setTerminalOpen(true); setMobileTab('code');
    if (!device.current || device.current.state === 'disconnected') await connectDevice();
    if (device.current?.state !== 'connected') return;
    if (!project) { setUploadAfterSave(true); openSave(); return; }
    await action('保存并建立上传清单', async () => {
      const saved = dirty ? await save() : project;
      if (saved) await showUploadPlan(saved);
    });
  };
  const startUpload = () => {
    const plan = manifest; setManifest(null);
    void action('上传', async () => {
      if (!plan || !device.current || !confirmed) return;
      if (dirty || project?.revision !== plan.revision || project.id !== plan.projectId || board !== plan.boardId) throw new Error('清单之后项目已变更，请重新建立上传清单。');
      setProgress(0);
      try {
        await device.current.upload(plan, persistBackup, (done, total) => setProgress(total ? Math.round(done / total * 100) : 100));
        setNotice('main.py 上传回读一致。程序尚未运行。');
      } finally { setProgress(null); }
    });
  };
  const sendMessage = async () => {
    if (!message.trim() || sendingMessage.current || loading || busy || !board) return;
    const prompt = message; const base = code; const chatBoard = board; const chatComponents = [...components];
    let id = project?.id;
    sendingMessage.current = true;
    setAiBusy(true); setError(''); setChatError('');
    try {
      // Refresh the token/config so a server restart or another tab cannot silently disable sending.
      const session = await bootstrap();
      setAiConfigured(session.aiConfigured); setAiModel(session.aiModel ?? DEFAULT_AI_MODEL);
      if (!session.aiConfigured) { setAiSettingsDialog(true); setChatError('先填写 API Key，保存后再发送。输入内容已保留。'); return; }
      setPendingPrompt(prompt);
      if (!id) {
        const created = await api<Project>('/projects', 'POST', { name: name === '未命名项目' ? '我的项目' : name, code: base, boardId: chatBoard, componentIds: chatComponents } satisfies CreateProject);
        id = created.id;
        // Adopt the saved snapshot without overwriting edits made while this request was pending.
        setProject(created); currentProject.current = id; setName(created.name); setDraftRevision(null);
        setMessages(created.messages); store('mu-active-project', id);
        setProjects(value => [created, ...value.filter(item => item.id !== id)]);
        setNotice('已为首次对话保存当前项目。');
      }
      const result = await api<{ messages: ChatMessage[] }>(`/projects/${id}/chat`, 'POST', { message: prompt, code: base, boardId: chatBoard, componentIds: chatComponents });
      if (currentProject.current === id) {
        setMessages(result.messages); setMessage(value => value === prompt ? '' : value);
        const reply = result.messages.filter(item => item.role === 'assistant' && item.status === 'COMPLETED').at(-1)?.content ?? '';
        const suggestion = /```(?:python|micropython|py)\s*\n([\s\S]*?)```/.exec(reply);
        if (suggestion) setCandidate({ code: suggestion[1].trimEnd() + '\n', base });
      }
    } catch (err) {
      setError(errorText(err)); setChatError(errorText(err));
      if (id && currentProject.current === id) {
        try { const saved = await api<Project>('/projects/' + id); setMessages(saved.messages); } catch { /* keep the prompt and existing conversation for retry */ }
      }
    } finally { sendingMessage.current = false; setAiBusy(false); setPendingPrompt(''); }
  };
  const previewCandidate = useRef<{ code: string; base: string } | null>(null);
  const [acceptDialog, setAcceptDialog] = useState(false);
  const family = sensorFamily(boardInfo);
  const boardSensors = modulesForBoard(hardware, boardInfo);
  const available = boardSensors.filter(item => (moduleFilter === 'all' || moduleDirection(item) === moduleFilter) && `${item.displayName} ${item.description}`.toLowerCase().includes(search.toLowerCase()));
  const outsideLibrary = components.filter(id => !boardSensors.some(item => item.componentId === id));
  const selectedSensors = components.map(id => hardware.find(item => item.componentId === id)).filter((item): item is HardwareSummary => !!item && !!moduleDirection(item));
  const receipt = device.current?.receipt;
  const canRun = connected && receipt && !dirty && receipt.projectId === project?.id && receipt.revision === project.revision;

  if (workspaceClosed) return <div className="closed-workspace"><Sparkles size={38} /><h1>工作区已收起</h1><p>当前项目与浏览器草稿已保留。</p><button className="primary" onClick={() => setWorkspaceClosed(false)}>返回工作台</button></div>;

  return <div className="app final-workbench">
    <header className="workspace-titlebar">
      <a className="title-brand" href="/" aria-label="掌问工作台"><span><Sparkles size={15} strokeWidth={2.4} /></span><strong>掌问</strong></a>
      <span className="title-filename">main.py{dirty && <span className="dirty-dot" aria-label="代码未保存" />}</span>
      <div className="current-project" aria-label="当前项目"><strong>{name}</strong><span>{project ? '已存于本机' : '尚未保存到本机'}</span></div>
      <span className="document-info">{dirty ? '未保存更改' : project ? '本地工作区' : '未保存'} · {zoom}%</span>
      <button className="theme-toggle" aria-label={theme === 'light' ? '切换深色主题' : '切换浅色主题'} title={theme === 'light' ? '深色主题' : '浅色主题'} onClick={() => setTheme(value => value === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</button>
    </header>
    <header className="mu-toolbar" aria-label="Mu 工具栏">
      <div className="mu-commands">
        <MuTool icon={CircuitBoard} label="主控" variant="brand" active={boardDialog} disabled={loading || !!busy || aiBusy || deviceBusy || running} onClick={() => setBoardDialog(true)} title={`选择主控板 · ${boardInfo?.displayName ?? '尚未选择'}`} />
        <span className="tool-divider" aria-hidden="true" />
        <MuTool icon={Plus} label="新建" aria-label="新建项目" disabled={loading || !board || !!busy || aiBusy || deviceBusy} onClick={openNew} />
        <MuTool icon={FolderOpen} label="加载" active={loadDialog} disabled={loading || !!busy || aiBusy || deviceBusy} onClick={() => void action('读取项目', async () => { await refreshProjects(); setLoadDialog(true); })} />
        <MuTool icon={Save} label="保存" disabled={loading || !board || !!busy || (aiBusy && !project)} onClick={() => void action('保存', save)} />
        <span className="tool-divider" aria-hidden="true" />
        <MuTool icon={ArrowUp} label="上传" variant="hardware" disabled={loading || !board || !!busy || aiBusy || deviceBusy || running || deviceState === 'attention'} onClick={() => void prepareUpload()} title="连接设备、保存项目并核对 main.py 上传清单" />
        <MuTool icon={running || deviceState === 'attention' ? Square : Play} label={running || deviceState === 'attention' ? '停止' : '运行'} emphasis active={running} disabled={!!busy || deviceBusy || !(running || canRun || deviceState === 'attention')} onClick={() => { setTerminalOpen(true); setMobileTab('code'); void action(running || deviceState === 'attention' ? '停止' : '运行', async () => { if (running || deviceState === 'attention') await device.current?.stop(); else await device.current?.run(); }); }} />
        <MuTool icon={Cable} label="接线" variant="hardware" active={wiringDialog} disabled={loading || !board || !!busy} title="查看当前项目接线资料" onClick={() => setWiringDialog(true)} />
        <MuTool icon={Files} label="文件" active={filesDialog || versions !== null} disabled={loading || !!busy || deviceBusy} onClick={() => void action('读取文件信息', async () => { setFileVersions(project ? (await api<{ versions: Version[] }>(`/projects/${project.id}/versions`)).versions : null); setFilesDialog(true); })} title="本机代码、设备文件与项目历史版本" />
        <MuTool icon={Terminal} label="REPL" active={terminalOpen} aria-pressed={terminalOpen} onClick={() => { setTerminalOpen(value => !value); setMobileTab('code'); }} />
        <span className="tool-divider" aria-hidden="true" />
        <MuTool icon={CheckCheck} label="检查" disabled={loading || !board || !!busy} onClick={() => void action('检查', async () => { const result = await api<CheckResult>('/check', 'POST', { code, boardId: board, componentIds: components }); setCheck(result); setMobileTab('code'); })} />
        <MuTool icon={AlignLeft} label="格式化" title="按 Python 语法整理四空格缩进（可撤销），不运行代码" disabled={loading || !!busy || !code.length} onClick={() => { setMobileTab('code'); editor.current?.formatIndentation(); setCheck(null); setNotice('已按 Python 语法整理四空格缩进，可在编辑器中撤销。请检查后再保存。'); }} />
        <MuTool icon={ZoomIn} label="放大" disabled={zoom >= 160} onClick={() => setZoom(value => Math.min(160, value + 10))} />
        <MuTool icon={ZoomOut} label="缩小" disabled={zoom <= 80} onClick={() => setZoom(value => Math.max(80, value - 10))} />
        <MuTool icon={HelpCircle} label="帮助" variant="muted" active={helpDialog} onClick={() => setHelpDialog(true)} />
        <MuTool icon={Settings} label="API 设置" variant="muted" active={aiSettingsDialog} disabled={loading || !!busy || aiBusy} onClick={openAiSettings} title="设置掌问 AI API" />
        <span className="tool-divider" aria-hidden="true" />
        <MuTool icon={Power} label="退出" variant="muted" disabled={loading || !!busy || aiBusy || deviceState !== 'disconnected'} title="收起工作区并保留草稿；请先断开设备" onClick={() => { if (dirty && !window.confirm('项目有未保存更改。收起工作区前建议保存；仍要退出吗？浏览器草稿会保留。')) return; persistDraftNow(); setWorkspaceClosed(true); }} />
      </div>
      <button className={`connection toolbar-status ${deviceState !== 'disconnected' ? 'is-connected' : ''}`} disabled={!!busy || deviceBusy} onClick={deviceState === 'disconnected' ? () => { setTerminalOpen(true); setMobileTab('code'); void connectDevice(); } : disconnect}>{deviceBusy ? <LoaderCircle size={17} className="spin" /> : deviceState === 'disconnected' ? <Usb size={17} /> : <Unplug size={17} />}<span>{deviceState === 'disconnected' ? '连接设备' : deviceState === 'connecting' ? '正在连接' : deviceState === 'attention' ? '需要重连 · 断开' : '已连接 · 断开'}</span></button>
    </header>
    {(error || notice || busy) && <div className={`feedback ${error ? 'error' : ''}`} role={error ? 'alert' : 'status'}>{error ? <X size={17} /> : busy ? <LoaderCircle size={17} className="spin" /> : <Check size={17} />}<span>{error || (busy ? `${busy}中…` : notice)}</span>{progress !== null && <><progress value={progress} max="100" /><span>{progress}%</span><button onClick={() => device.current?.cancel()}>取消上传</button></>}<button className="icon-button" aria-label="关闭提示" onClick={() => { setError(''); setNotice(''); }}><X size={16} /></button></div>}
    <nav className="mobile-tabs" aria-label="工作区切换">{[['hardware', '硬件库'], ['ai', '掌问 AI'], ['code', '代码']].map(([key, label]) => <button key={key} className={mobileTab === key ? 'active' : ''} onClick={() => setMobileTab(key)}>{label}</button>)}</nav>
    <main className="workbench">
      <aside className={`hardware-panel panel mobile-${mobileTab === 'hardware' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><CircuitBoard size={18} />已加入的模块</h2><span>{selectedSensors.length} 个</span></div>
        <div className="selected-sensors-toolbar"><button className="board-control" aria-label="主控板" disabled={loading || !!busy || deviceBusy} onClick={() => setBoardDialog(true)}><CircuitBoard size={17} /><span>{boardInfo?.displayName ?? '选择主控板'}</span><ChevronRight size={14} /></button><button className="add-sensor-button" disabled={loading || !!busy || deviceBusy || !board} onClick={openSensorPicker}><Plus size={18} />添加模块</button></div>
        <div className="catalog-list selected-sensor-list">{loading ? <p className="muted">正在读取项目…</p> : (['input', 'output'] as const).map(direction => {
          const items = selectedSensors.filter(item => moduleDirection(item) === direction);
          return items.length > 0 && <section className="module-group" key={direction} aria-label={direction === 'input' ? '已加入的输入模块' : '已加入的输出模块'}><h3>{direction === 'input' ? '输入模块' : '输出模块'}<span>{items.length}</span></h3><div className="module-grid">{items.map(item => <ModuleCard key={item.componentId} item={item} disabled={!!busy || deviceBusy} outside={!boardSensors.some(module => module.componentId === item.componentId)} onDetail={() => openDetail(item)} onLoad={() => loadModuleSample(item)} onRemove={() => { setComponents(value => value.filter(id => id !== item.componentId)); setCheck(null); }} />)}</div></section>;
        })}{!loading && !selectedSensors.length && <div className="selected-sensors-empty"><CircuitBoard size={42} /><strong>为项目添加模块</strong><p>点击「添加模块」，选择传感器、执行器或显示模块。</p></div>}</div>
        {outsideLibrary.length > 0 && <p className="library-notice">有 {outsideLibrary.length} 个项目元件不在当前可选系列中，已保留；请在「接线」中核对。</p>}
        <footer className="catalog-foot"><BookOpen size={16} /><span>输入感知 · 输出控制<br /><small>点击大图标查看模块资料</small></span></footer>
      </aside>
      <section className={`ai-panel panel mobile-${mobileTab === 'ai' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Sparkles size={18} />掌问 AI</h2><button className="api-settings-entry" disabled={loading || !!busy || aiBusy} onClick={openAiSettings} aria-label="掌问 AI API 设置"><Settings size={14} /><span>{aiConfigured ? '已配置' : '未配置'}</span> · 设置</button></div>
        <div className="messages" role="log" aria-label="掌问对话记录">
          {!messages.length && <div className="conversation-empty"><span><Sparkles size={24} strokeWidth={1.6} /></span><p>描述你的想法，或粘贴需要分析的代码与报错。</p></div>}
          {messages.map(item => <article className={`message ${item.role}`} key={item.id}><strong>{item.role === 'user' ? '你' : '掌问'}{item.status === 'FAILED' ? ' · 请求失败' : ''}</strong><pre>{item.content}</pre></article>)}
          {pendingPrompt && <article className="message user"><strong>你 · 正在发送</strong><pre>{pendingPrompt}</pre></article>}
          {aiBusy && <p className="muted"><LoaderCircle size={16} className="spin" /> 正在请求模型，代码保持可编辑…</p>}
          {candidate && <div className="candidate"><FileCode2 size={19} /><span>有一个 main.py 建议待核对</span><button onClick={() => { previewCandidate.current = candidate; setAcceptDialog(true); }}>查看代码</button></div>}
        </div>
        {chatError && <p className="chat-error" role="alert">{chatError}</p>}
        {!project && <p className="chat-hint">首次发送会自动保存当前项目、代码和已加入模块。</p>}
        <form className="chat-form" onSubmit={event => { event.preventDefault(); void sendMessage(); }}><label className="sr-only" htmlFor="chat-message">发送给掌问 AI</label><textarea id="chat-message" value={message} onChange={event => setMessage(event.target.value)} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.nativeEvent.isComposing && !loading && !busy && !aiBusy && message.trim()) { event.preventDefault(); void sendMessage(); } }} placeholder="和掌问聊聊你的想法…" maxLength={4000} /><div><span>{!aiConfigured ? "AI 未配置 · 点击 API 设置" : "代码建议由你确认"}</span><kbd className="chat-shortcut">Ctrl ↵</kbd><button className="primary icon-button" aria-label="发送" disabled={loading || !!busy || !board || !message.trim() || aiBusy}>{aiBusy ? <LoaderCircle size={19} className="spin" /> : <ArrowUp size={20} />}</button></div></form>
      </section>
      <section className={`code-panel panel mobile-${mobileTab === 'code' ? 'show' : 'hide'}`}>
        <div className="filebar"><span><FileCode2 size={16} />main.py</span><span className="filebar-space" /><span className={dirty ? 'unsaved' : 'status-ready'}>{project ? dirty ? '未保存' : `已保存 · v${project.revision}` : '项目尚未保存'}</span><button aria-label="导出当前代码" onClick={() => download("main.py", code)}><Download size={16} />导出</button></div>
        <Editor ref={editor} zoom={zoom} readOnly={loading || !!busy || deviceBusy} value={code} onChange={value => { setCode(value); setCheck(null); }} />
        {check && <section className="check-results" aria-label="检查结果"><div><strong>{check.valid ? '静态检查完成' : '检查发现问题'}</strong><button className="icon-button" aria-label="关闭检查" onClick={() => setCheck(null)}><X size={16} /></button></div>{check.diagnostics.map((item, index) => <p className={`diagnostic ${item.severity.toLowerCase()}`} key={index}><span>{item.severity === 'PASS' ? '通过' : item.severity === 'FAIL' ? '错误' : '提示'}</span>{item.line ? `第 ${item.line} 行 · ` : ''}{item.message}</p>)}</section>}
        <section className="terminal-panel" hidden={!terminalOpen}><div className="terminal-head"><h3><Terminal size={17} />串口终端</h3><span>{running ? '运行命令已提交' : connected ? 'REPL 已连接' : deviceState === 'attention' ? '连接需核对' : '未连接'}</span><button disabled={!!busy} onClick={() => setLogs('')}>清空</button><button onClick={() => void action('导出设备备份', async () => { const backup = await latestBackup(); if (!backup) throw new Error('尚无设备备份。'); if (backup.bytes) download('main-before-upload.py', backup.bytes); else setNotice('上次上传前设备不存在 main.py，无需恢复旧文件。'); })}>备份</button><button aria-label="收起终端" onClick={() => setTerminalOpen(false)}><X size={16} /></button></div><pre className="serial-log" aria-label="串口输出">{logs}</pre><form className="repl-form" onSubmit={event => { event.preventDefault(); void action('发送 REPL', async () => { await device.current?.repl(repl); setRepl(''); }); }}><span aria-hidden="true">&gt;&gt;&gt;</span><input aria-label="REPL 命令" placeholder="连接后输入命令；运行中请先停止" value={repl} onChange={event => setRepl(event.target.value)} disabled={!connected || !!busy} /><button disabled={!connected || !!repl.trim() || !!busy} aria-label="发送 REPL 命令"><ArrowUp size={17} /></button></form></section>
      </section>
    </main>
    <footer className="statusbar"><span><span className="status-dot" />MicroPython · Web Serial</span><span>{components.length + 1} 个硬件 · main.py<span className="status-separator">/</span>{device.current?.identity?.machine ?? '设备未连接'}</span><span>本机保存 · 设备操作需确认</span></footer>
    {boardDialog && <BoardPicker boards={hardware} selected={newDialog ? newBoard : board} onClose={() => setBoardDialog(false)} onSelect={item => { if (newDialog) setNewBoard(item.componentId); else { setBoard(item.componentId); setCheck(null); } setBoardDialog(false); }} onHelp={() => { setBoardDialog(false); setHelpDialog(true); }} />}
    {loadDialog && <Dialog title="加载项目" onClose={() => setLoadDialog(false)}><p className="muted">打开本机已保存项目，当前浏览器的未保存草稿会保留。</p>{projects.length ? projects.map(item => <button className="load-project-row" key={item.id} onClick={async () => { if (await chooseProject(item.id)) setLoadDialog(false); }}><FolderOpen size={22} /><span><strong>{item.name}</strong><small>版本 {item.revision} · {new Date(item.updatedAt).toLocaleString()}</small></span>{item.id === project?.id ? <Check size={18} /> : <ChevronRight size={18} />}</button>) : <p>还没有保存的项目。关闭此窗口继续创作，点击「保存」命名保存。</p>}</Dialog>}
    {wiringDialog && <Dialog title="项目接线资料" onClose={() => setWiringDialog(false)}><p className="muted">按已选择的主控板和元件查看实际接线说明。此处展示硬件资料，接线请按具体板型、固件与供电要求核对。</p><div className="wiring-summary">{[board, ...components].map(id => hardware.find(item => item.componentId === id)).filter((item): item is HardwareSummary => !!item).map(item => <button key={item.componentId} onClick={() => { setWiringDialog(false); openDetail(item); }}><span className="hardware-image"><CircuitBoard size={26} /></span><span><strong>{item.displayName}</strong><small>{categoryName[item.category]} · 查看接线与电气资料</small></span><BookOpen size={20} /></button>)}</div>{!components.length && <p className="muted">当前尚未加入外设，可点击左侧「添加模块」选择。</p>}</Dialog>}
    {helpDialog && <Dialog title="掌问 Mu 工作台使用说明" onClose={() => setHelpDialog(false)}><ol className="help-steps"><li>打开即进入一个未命名项目。选择主控板，添加模块并编写代码；点击「保存」命名保存，点击「加载」打开已有项目。</li><li>左侧用大图标显示已加入的输入/输出模块，点击「添加模块」选择；XIAO S3 可选 Grove，K10 可选 DFRobot。中间直接对话，右侧编辑 main.py。</li><li>保存项目、检查代码；连接设备后核对清单并上传。上传前备份，上传后回读校验。</li><li>点击「运行」提交设备命令，通过 REPL/串口输出与实物观察判断；运行时同一按钮变为「停止」。</li><li>「文件」可载入/导出本机代码、浏览并读取设备根目录、查看和载入历史版本，「放大/缩小」调整编辑字号。</li></ol><p className="muted">启用 AI：点击工具栏「API 设置」，填写 DeepSeek API Key 并保存，立即生效。发送时当前代码与所选硬件资料会提交给 DeepSeek，建议接受后才进入编辑器。未配置时可继续手工编程。Web Serial 需要桌面 Chrome/Edge；本版支持 main.py 文件上传，最多 64 KiB。</p></Dialog>}
    {aiSettingsDialog && <AiSettingsDialog settings={{ aiConfigured, aiModel }} onClose={() => setAiSettingsDialog(false)} onSaved={result => { setAiConfigured(result.aiConfigured); setAiModel(result.aiModel); setAiSettingsDialog(false); setNotice(result.aiConfigured ? 'API 已保存到本机设置，立即生效。' : 'API 已清除，手工编程仍可继续。'); }} />}
    {newDialog && !boardDialog && !helpDialog && <Dialog title="保存项目" onClose={() => { setNewDialog(false); setUploadAfterSave(false); }}><form onSubmit={event => { event.preventDefault(); void action('保存项目', async () => { const request: CreateProject = { name: newName, boardId: newBoard, code, componentIds: components }; const value = await api<Project>('/projects', 'POST', request); applyProject(value, false); try { localStorage.removeItem("mu-scratch-code"); localStorage.removeItem("mu-scratch-hardware"); } catch { /* unavailable */ } await refreshProjects(); setNewDialog(false); setNotice('项目已保存到本机，可通过「加载」再次打开。'); setMobileTab('code'); if (uploadAfterSave) { setUploadAfterSave(false); await showUploadPlan(value); } }); }}><label className="field">项目名称<input autoFocus value={newName} maxLength={80} onChange={event => setNewName(event.target.value)} required /></label><div className="field">主控板<button type="button" className="board-control" aria-label="选择项目主控板" onClick={() => setBoardDialog(true)}><CircuitBoard size={17} /><span>{hardware.find(item => item.componentId === newBoard)?.displayName ?? '选择主控板'}</span><ChevronRight size={14} /></button></div><p className="muted">保存当前代码、主控板和已加入模块到本机。以后点击「加载」打开此项目。</p><button className="primary" disabled={!newName.trim() || !newBoard || !!busy}>保存项目</button></form></Dialog>}
    {sensorPicker && <Dialog className="sensor-picker-dialog" title="添加模块" onClose={() => setSensorPicker(false)}>
      <div className="sensor-picker-context"><strong>{family ?? '当前板型'} 模块库</strong><span>{boardInfo?.displayName}</span></div>
      <div className="catalog-search picker-search"><Search size={17} /><input autoFocus aria-label="搜索硬件" placeholder={`搜索 ${family ?? '当前板型'} 模块…`} value={search} onChange={event => setSearch(event.target.value)} /></div>
      <div className="module-filters" role="group" aria-label="模块类型">{(['all', 'input', 'output'] as const).map(direction => <button key={direction} aria-pressed={moduleFilter === direction} onClick={() => setModuleFilter(direction)}>{direction === 'all' ? '全部模块' : direction === 'input' ? '输入模块' : '输出模块'}<span>{boardSensors.filter(item => direction === 'all' || moduleDirection(item) === direction).length}</span></button>)}</div>
      <div className="sensor-picker-list module-grid">{available.map(item => { const added = components.includes(item.componentId); return <ModuleCard key={item.componentId} item={item} added={added} checked={added || pendingSensors.includes(item.componentId)} disabled={added || !!busy || deviceBusy || (!pendingSensors.includes(item.componentId) && components.length + pendingSensors.length >= 32)} onToggle={checked => setPendingSensors(value => checked ? [...value, item.componentId] : value.filter(id => id !== item.componentId))} onDetail={() => openDetail(item, true)} />; })}{!available.length && <p className="catalog-empty muted">{boardSensors.length ? '没有匹配的模块，试试其他分类或关键词。' : `当前硬件库尚无 ${family ?? '此板型'} 模块资料包。`}</p>}</div>
      <div className="sensor-picker-actions"><span>{pendingSensors.length ? `已选择 ${pendingSensors.length} 个` : '选择项目需要的模块'}{components.length + pendingSensors.length >= 32 && ' · 已达32项上限'}</span><button onClick={() => setSensorPicker(false)}>取消</button><button className="primary" aria-label="加入所选模块" disabled={!pendingSensors.length || !!busy || deviceBusy} onClick={() => { setComponents(value => [...new Set([...value, ...pendingSensors])]); setCheck(null); setSensorPicker(false); }}>{pendingSensors.length ? `加入 ${pendingSensors.length} 个模块` : '加入模块'}</button></div>
    </Dialog>}
    {detail && <HardwareDetails detail={detail} onClose={() => { setDetail(null); if (returnToPicker) setSensorPicker(true); setReturnToPicker(false); }} />}
    {moduleSample && <Dialog title={`载入模块：${moduleSample.item.displayName}`} onClose={() => setModuleSample(null)}><p className="muted">示例来自此硬件资料包。确认后替换当前 main.py 草稿；请按实际接线修改端口并检查，保存和上传仍需单独操作。</p><pre className="candidate-code">{moduleSample.code}</pre><button className="primary" onClick={() => { if (code !== moduleSample.base && !window.confirm('预览后代码已改变，仍用此示例替换当前草稿吗？')) return; setCode(moduleSample.code); setCheck(null); setModuleSample(null); setMobileTab('code'); setNotice('已载入原模块示例，尚未保存或上传。请核对固件、端口和接线。'); }}>替换当前代码</button></Dialog>}
    {filesDialog && <DeviceFilesDialog device={device.current} connected={connected} code={code} versions={fileVersions} disabled={!!busy} onClose={() => setFilesDialog(false)} onDownload={download} onHistory={() => { setFilesDialog(false); setVersions(fileVersions); }} onLoad={value => { if (code !== value && code.length && !window.confirm('用这个文件替换当前编辑器草稿？设备文件不会改变。')) return; setCode(value); setCheck(null); setFilesDialog(false); setNotice('文件已载入编辑器，尚未保存或上传。'); setMobileTab('code'); }} />}
    {versions && <Dialog title="保存的代码版本" onClose={() => setVersions(null)}><p className="muted">选择一个版本放入编辑器，再保存会创建新版本。历史记录不会被覆盖。</p><button onClick={() => void action("重新载入", async () => { if (dirty && !window.confirm("重新载入会放弃本地草稿，请先导出需要保留的代码。继续吗？")) return; if (!project) return; const saved = await api<Project>("/projects/" + project.id); try { localStorage.removeItem("mu-draft-" + project.id); } catch { /* unavailable */ } applyProject(saved, false); setVersions(null); })}>重新载入当前已保存项目</button>{versions.map(version => <article className="version-row" key={version.revision}><div><strong>版本 {version.revision}</strong><small>{new Date(version.createdAt).toLocaleString()}</small></div><button onClick={() => { if (!dirty || window.confirm('使用这个版本替换当前草稿？')) { setCode(version.code); setCheck(null); setVersions(null); setNotice('历史代码已放入编辑器，尚未保存为当前版本。'); } }}>载入代码</button><button onClick={() => download(`main-v${version.revision}.py`, version.code)}><Download size={17} />导出</button></article>)}</Dialog>}
    {manifest && <Dialog title="确认上传 main.py" onClose={() => setManifest(null)}><p>将版本 <strong>v{manifest.revision}</strong> 上传到当前连接的 MicroPython 设备。已有程序会被中断。</p><dl className="upload-details"><dt>项目主控</dt><dd>{boardInfo?.displayName}</dd><dt>设备报告</dt><dd>{device.current?.identity?.machine}</dd><dt>文件</dt><dd>main.py · {manifest.files[0].size} bytes</dd><dt>SHA-256</dt><dd className="checksum">{manifest.files[0].sha256}</dd></dl><p className="muted">先保存旧文件备份，再暂存、校验、替换和回读。其他用户文件保留。上传完成后，程序不会自动运行。</p><label className="confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} />我已核对实际板型、固件和接线，并同意备份后替换 main.py。</label><button className="primary" disabled={!confirmed || !!busy} onClick={startUpload}><ArrowUp size={18} />开始上传</button></Dialog>}
    {acceptDialog && previewCandidate.current && <Dialog title="核对 AI 的 main.py 建议" onClose={() => setAcceptDialog(false)}><p className="muted">接受后仅替换编辑器草稿。保存、检查和上传仍由你操作。</p><pre className="candidate-code">{previewCandidate.current.code}</pre><button className="primary" onClick={() => { const suggestion = previewCandidate.current!; if (currentCode.current !== suggestion.base && !window.confirm('你在 AI 请求后修改过代码。接受会替换当前草稿，是否继续？')) return; setCode(suggestion.code); setCheck(null); setCandidate(null); setAcceptDialog(false); setNotice('已接受 AI 建议，尚未保存。'); }}><Check size={18} />接受到编辑器</button></Dialog>}
  </div>;
}
