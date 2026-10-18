import { useCallback, useEffect, useRef, useState } from 'react';
import palmMark from './assets/palm-mark.png';
import { ArrowUp, BookOpen, Check, CheckCheck, ChevronRight, CircuitBoard, Download, FileCode2, Files, FolderOpen, HelpCircle, LoaderCircle, Plus, Save, Search, Sparkles, Square, Terminal, Unplug, Usb, X, Play, ZoomIn, ZoomOut, AlignLeft, Moon, Sun, Settings, PanelLeftClose, PanelLeftOpen, Maximize, Minimize, Cpu, Layers3, GraduationCap, UserRound, Box, ScanLine } from 'lucide-react';
import type { AiSettings, ChatMessage, CheckResult, CreateProject, HardwareDetail, HardwareSummary, Project, ProjectSnapshot, ProjectSummary, ProgramRunSubmission, UploadManifest, Version, WorkspaceMode } from '../../../packages/contracts/src/mu';
import { DEFAULT_AI_MODEL } from '../../../packages/contracts/src/mu';
import { api, bootstrap, chat } from './api';
import { MicroPythonDevice, serialApi } from './serial';
import { latestBackup, persistBackup } from './backups';
import { Editor, type EditorHandle } from './Editor';
import { Dialog } from './Dialog';
import { AiSettingsDialog } from './AiSettingsDialog';
import { MuTool } from './MuTool';
import { FeedbackToast } from './FeedbackToast';
import { AssistantMessage } from './AssistantMessage';
import { UserMessage } from './UserMessage';
import { replyCode, streamText } from './assistantReply';
import { moduleDirection, selectableModules, filterModules, type ModuleDirection } from './hardwareLibrary';
import { ModuleFilters } from './ModuleFilters';
import { HardwareDetails } from './HardwareDetails';
import { guideCode, guideKind } from './moduleExamples';
import { ModuleCard } from './ModuleCard';
import { BoardPicker } from './BoardPicker';
import { DeviceFilesDialog } from './DeviceFilesDialog';
import { copyProjectPrograms } from './projectPrograms';
import { HardwareGuide, integrationPrompt } from './HardwareGuide';
import { BoardArtwork } from './BoardArtwork';
import { ModePicker, workspaceModes } from './WorkspaceModes';
import { LearningWorkspace } from './LearningWorkspace';
import type { LearningRole } from './LearningMaterials';
import { learningSections, type LearningSection } from './LearningSections';
import { StructureWorkspace } from './StructureWorkspace';
import { UpdateCenter } from './UpdateCenter';
import { FirmwareDialog } from './FirmwareDialog';
import { ensureFolderPermission, pickProjectDirectory, pickerCancelled, prepareNewDirectory, readProjectDirectory, recallFolder, rememberFolder, writeProjectDirectory, type FolderBinding, type ProjectDirectory } from './projectFolders';

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

export default function App() {
  const [mode, setMode] = useState<WorkspaceMode>(() => { const value = stored('mu-workspace-mode'); return value === 'structure' || value === 'learning' ? value : 'engineer'; });
  const [structureBusy, setStructureBusy] = useState(false);
  const structureBusyRef = useRef(structureBusy); structureBusyRef.current = structureBusy;
  const [modeDialog, setModeDialog] = useState(false);
  const [structureDesignType, setStructureDesignType] = useState<'model' | 'laser'>('model');
  const [structureDrafts, setStructureDrafts] = useState({model: '', laser: ''});
  const [learningRole, setLearningRole] = useState<LearningRole>('teacher');
  const [learningSection, setLearningSection] = useState<LearningSection>('guidance');
  const [learningRoleDialog, setLearningRoleDialog] = useState(false);
  const modeInfo = workspaceModes.find(item => item.id === mode)!;
  const selectMode = (value: WorkspaceMode) => { setMode(value); store('mu-workspace-mode', value); setCodeFullscreen(false); setModeDialog(false); setLearningRoleDialog(false); };
  const [hardware, setHardware] = useState<HardwareSummary[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  useEffect(() => { setStructureDrafts({model: '', laser: ''}); }, [project?.id]);
  const [code, setCode] = useState(() => stored('mu-scratch-code') ?? '');
  const [name, setName] = useState('未命名项目');
  const [draftRevision, setDraftRevision] = useState<number | null>(null);
  const [board, setBoard] = useState(() => scratchHardware().board);
  const [components, setComponents] = useState<string[]>(() => scratchHardware().components);
  const [search, setSearch] = useState('');
  const [moduleFilter, setModuleFilter] = useState<ModuleDirection | 'all'>('all');
  const [moduleBrandFilter, setModuleBrandFilter] = useState('all');
  const [moduleTypeFilter, setModuleTypeFilter] = useState('');
  const [detail, setDetail] = useState<HardwareDetail | null>(null);
  const [moduleSample, setModuleSample] = useState<{ item: HardwareSummary; code: string; base: string; scope?: string } | null>(null);
  const [sensorPicker, setSensorPicker] = useState(false);
  const [pendingSensors, setPendingSensors] = useState<string[]>([]);
  const [returnToPicker, setReturnToPicker] = useState(false);
  const [newDialog, setNewDialog] = useState(false);
  const [creationMode, setCreationMode] = useState<'new' | 'save'>('save');
  const [newFolder, setNewFolder] = useState<ProjectDirectory | null>(null);
  const [newName, setNewName] = useState('我的项目');
  const [versions, setVersions] = useState<Version[] | null>(null);
  const [codeVersions, setCodeVersions] = useState<Version[]>([]);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const [historyRefresh, setHistoryRefresh] = useState(0);
  const [folder, setFolder] = useState<FolderBinding | null>(null);
  const folderRef = useRef<FolderBinding | null>(null);
  const folderQueue = useRef<Promise<void>>(Promise.resolve());
  const [folderStatus, setFolderStatus] = useState('');
  const [folderError, setFolderError] = useState('');
  const folderPending = useRef(0);
  const folderErrorRef = useRef(folderError); folderErrorRef.current = folderError;
  const [filesDialog, setFilesDialog] = useState(false);
  const [fileVersions, setFileVersions] = useState<Version[] | null>(null);
  const [uploadAfterSave, setUploadAfterSave] = useState(false);
  const [editExample, setEditExample] = useState(false);
  const [check, setCheck] = useState<CheckResult | null>(null);
  const [aiConfigured, setAiConfigured] = useState(false);
  const [aiModel, setAiModel] = useState<string>(DEFAULT_AI_MODEL);
  const [aiBaseUrl, setAiBaseUrl] = useState('https://api.deepseek.com');
  const [aiSettingsDialog, setAiSettingsDialog] = useState(false);
  const [message, setMessage] = useState('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [candidate, setCandidate] = useState<{ code: string; revision?: number; boardId?: string } | null>(null);
  const [codePreview, setCodePreview] = useState<{ code: string; revision?: number; boardId?: string } | null>(null);
  const visibleCode = codePreview?.code ?? code;
  const [error, setError] = useState('');
  const [notice, setNoticeText] = useState('');
  const [noticeSequence, setNoticeSequence] = useState(0);
  const setNotice = (value: string) => { setNoticeText(value); setNoticeSequence(count => count + 1); };
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [aiPhase, setAiPhase] = useState<'preparing' | 'waiting' | 'generating'>('preparing');
  const [aiElapsed, setAiElapsed] = useState(0);
  const [streamedReply, setStreamedReply] = useState('');
  const aiController = useRef<AbortController | null>(null);
  const sendingMessage = useRef(false);
  const [pendingPrompt, setPendingPrompt] = useState('');
  const [chatError, setChatError] = useState('');
  const [guideScope, setGuideScope] = useState(0);
  const [guideReveal, setGuideReveal] = useState(0);
  const hardwareGuide = useRef<HTMLElement>(null);
  const chatInput = useRef<HTMLTextAreaElement>(null);
  const conversationPane = useRef<HTMLDivElement>(null);
  const followConversation = useRef(false);
  useEffect(() => {
    if (!followConversation.current) return;
    const frame = requestAnimationFrame(() => {
      const pane = conversationPane.current;
      if (pane && followConversation.current) pane.scrollTop = pane.scrollHeight;
    });
    return () => cancelAnimationFrame(frame);
  }, [pendingPrompt, streamedReply, messages]);
  useEffect(() => {
    if (!guideReveal) return;
    const frame = requestAnimationFrame(() => {
      hardwareGuide.current?.focus({ preventScroll: true });
      hardwareGuide.current?.scrollIntoView({ block: 'nearest' });
    });
    return () => cancelAnimationFrame(frame);
  }, [guideReveal]);
  useEffect(() => {
    if (!aiBusy) return;
    const started = Date.now(); setAiElapsed(0);
    const timer = setInterval(() => setAiElapsed(Math.floor((Date.now() - started) / 1000)), 1000);
    return () => clearInterval(timer);
  }, [aiBusy]);
  useEffect(() => () => aiController.current?.abort(), []);
  const [logs, setLogs] = useState('尚未连接设备。使用桌面 Chrome / Edge 打开本机页面，然后点击「连接设备」。\n');
  const [repl, setRepl] = useState('');
  const [progress, setProgress] = useState<number | null>(null);
  const [, redraw] = useState(0);
  const [mobileTab, setMobileTab] = useState('code');
  const [boardDialog, setBoardDialog] = useState(false);
  const [loadDialog, setLoadDialog] = useState(false);
  const [helpDialog, setHelpDialog] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [zoom, setZoom] = useState(100);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => stored('mu-theme') === 'dark' ? 'dark' : 'light');
  const [hardwareCollapsed, setHardwareCollapsed] = useState(() => stored('mu-hardware-collapsed') === 'true');
  const [codeFullscreen, setCodeFullscreen] = useState(false);
  const [firmwareDialog, setFirmwareDialog] = useState(false);
  const [flashing, setFlashing] = useState(false);
  const flashingRef = useRef(flashing); flashingRef.current = flashing;
  useEffect(() => { store('mu-hardware-collapsed', String(hardwareCollapsed)); }, [hardwareCollapsed]);
  useEffect(() => {
    if (!codeFullscreen) return;
    const outside = document.querySelectorAll<HTMLElement>('.workspace-titlebar, .mu-toolbar, .mobile-tabs, .hardware-panel, .hardware-restore, .ai-panel, .statusbar');
    outside.forEach(node => { node.inert = true; });
    const escape = (event: KeyboardEvent) => { if (event.key === 'Escape') setCodeFullscreen(false); };
    window.addEventListener('keydown', escape);
    return () => { window.removeEventListener('keydown', escape); outside.forEach(node => { node.inert = false; }); };
  }, [codeFullscreen]);
  const editor = useRef<EditorHandle>(null);
  useEffect(() => { document.documentElement.dataset.theme = theme; store('mu-theme', theme); }, [theme]);
  const device = useRef<MicroPythonDevice | null>(null);
  const [runSubmission, setRunSubmission] = useState<ProgramRunSubmission | null>(null);
  const releasePort = useRef<(() => void) | null>(null);
  const manualDirty = project ? (code !== project.code || name !== project.name || board !== project.boardId || JSON.stringify(components) !== JSON.stringify(project.componentIds)) : code.length > 0 || components.length > 0;
  const dirty = manualDirty || (codePreview !== null && codePreview.code !== project?.code);
  // Choosing hardware must not hide the first AI program; protect unsaved code itself.
  const manualCodeDirty = project ? code !== project.code : code.length > 0;
  const manualCodeDirtyRef = useRef(manualCodeDirty); manualCodeDirtyRef.current = manualCodeDirty;
  const deviceState = device.current?.state ?? 'disconnected';
  const connected = deviceState === 'connected';
  const running = deviceState === 'running';
  const deviceBusy = deviceState === 'busy' || deviceState === 'connecting';
  const boardInfo = hardware.find(item => item.componentId === board);
  const currentCode = useRef(visibleCode); currentCode.current = visibleCode;
  const currentHardware = useRef({ board, components }); currentHardware.current = { board, components };
  const currentProject = useRef(project?.id); currentProject.current = project?.id;
  const restoredPreviewProject = useRef<string | null>(null);
  const dirtyRef = useRef(dirty); dirtyRef.current = dirty;
  const busyRef = useRef(busy); busyRef.current = busy;
  const addLog = useCallback((text: string) => { setLogs(value => (value + text).slice(-60_000)); }, []);

  const action = async (label: string, task: () => Promise<unknown>) => {
    setBusy(label); setError(''); setNotice('');
    try { await task(); } catch (err) { setError(errorText(err)); } finally { setBusy(''); }
  };
  const openAiSettings = () => void action('读取 API 设置', async () => { const settings = await api<AiSettings>('/settings/ai'); setAiConfigured(settings.aiConfigured); setAiModel(settings.aiModel); setAiBaseUrl(settings.aiBaseUrl ?? 'https://api.deepseek.com'); setAiSettingsDialog(true); });
  const bindFolder = (value: FolderBinding | null, status = '') => { folderRef.current = value; setFolder(value); setFolderStatus(status); setFolderError(''); };
  const syncFolder = async (id: string) => {
    const binding = folderRef.current;
    if (!binding || binding.projectId !== id) return;
    const run = async () => {
      try {
        if (currentProject.current === id) setFolderStatus('正在同步');
        const snapshot = await api<ProjectSnapshot>(`/projects/${id}/snapshot`);
        await writeProjectDirectory(binding, snapshot);
        if (currentProject.current === id) { setFolderStatus('已同步'); setFolderError(''); }
      } catch (err) {
        // A failed disk checkpoint must not turn a completed AI reply into a failure.
        await rememberFolder(binding).catch(() => {});
        if (currentProject.current === id) { setFolderStatus('未同步'); setFolderError('本机记录已保留，项目文件夹未完成同步：' + errorText(err)); }
      }
    };
    folderPending.current++;
    const pending = folderQueue.current.then(run, run); folderQueue.current = pending;
    try { await pending; } finally { folderPending.current--; }
  };
  useEffect(() => {
    let active = true;
    setCodeVersions([]);
    if (project) void api<{ versions: Version[] }>(`/projects/${project.id}/versions`).then(result => {
      if (!active) return;
      setCodeVersions(result.versions);
      const firstLoad = restoredPreviewProject.current !== project.id;
      restoredPreviewProject.current = project.id;
      const recovered = result.versions.find(item => item.source === 'ai' && item.boardId === currentHardware.current.board && item.code.trim());
      if (firstLoad && recovered && !project.code.trim() && !currentCode.current.trim() && !manualCodeDirtyRef.current) {
        setCandidate(recovered); setCodePreview(recovered); setCheck(null);
      }
    }).catch(err => { if (active) setError('读取代码历史失败：' + errorText(err)); });
    return () => { active = false; };
  }, [project?.id, project?.revision, historyRefresh]);
  const applyProject = (value: Project, restoreDraft = true) => {
    if (value.id !== currentProject.current) {
      followConversation.current = false; bindFolder(null);
      currentProject.current = value.id;
      void recallFolder(value.id).then(binding => { if (currentProject.current === value.id && !folderRef.current) bindFolder(binding, binding ? '已关联' : ''); }).catch(err => { if (currentProject.current === value.id) setFolderError(errorText(err)); });
    }
    setProject(value); setName(value.name); setBoard(value.boardId); setComponents(value.componentIds); setDraftRevision(null);
    setSelectedVersion(value.revision); setHistoryRefresh(count => count + 1);
    setMessages(value.messages); setCandidate(null); setCodePreview(null); setCheck(null); setChatError(''); store('mu-active-project', value.id);
    let draft: { code: string; name: string; board: string; components: string[]; baseRevision: number } | null = null;
    try { draft = JSON.parse(stored('mu-draft-' + value.id) ?? 'null'); } catch { /* invalid draft */ }
    if (restoreDraft && draft && typeof draft.code === 'string' && typeof draft.name === 'string' && typeof draft.board === 'string' && Array.isArray(draft.components)) {
      setCode(draft.code); setName(draft.name); setBoard(draft.board); setComponents(draft.components); setDraftRevision(draft.baseRevision);
      if (draft.code !== value.code) setSelectedVersion(null);
      setNotice(draft.baseRevision !== value.revision ? '发现本地草稿，但服务端版本已更新。先导出草稿，再核对版本。' : '已恢复本地草稿；保存后才成为项目版本。');
    } else setCode(value.code);
  };
  const refreshProjects = async () => setProjects((await api<{ projects: ProjectSummary[] }>('/projects')).projects);
  const persistDraftNow = () => {
    if (project && dirty) store('mu-draft-' + project.id, JSON.stringify({ code, name, board, components, baseRevision: draftRevision ?? project.revision }));
  };
  const openSave = () => { setError(''); setCreationMode('save'); setNewFolder(null); setNewName(name === '未命名项目' ? '我的项目' : name); setNewDialog(true); };
  const openNew = () => {
    if (dirty && !window.confirm('当前项目有未保存更改。确定开始一个新项目吗？建议先保存当前项目。')) return;
    setError(''); setCreationMode('new'); setNewFolder(null); setNewName('我的项目'); setNewDialog(true);
  };
  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const session = await bootstrap();
        const [catalog, list] = await Promise.all([api<{ skills: HardwareSummary[] }>('/hardware'), api<{ projects: ProjectSummary[] }>('/projects')]);
        if (!active) return;
        setAiConfigured(session.aiConfigured); setAiModel(session.aiModel ?? DEFAULT_AI_MODEL); setHardware(catalog.skills); setProjects(list.projects);
        setAiBaseUrl(session.aiBaseUrl ?? 'https://api.deepseek.com');
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
      if (dirtyRef.current || structureBusyRef.current || folderPending.current || folderErrorRef.current || sendingMessage.current || device.current?.state === 'busy' || flashingRef.current) { event.preventDefault(); event.returnValue = ''; }
    };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, []);
  const save = async () => {
    if (sendingMessage.current && !project) { setNotice('正在准备首次对话项目，请稍后保存。'); return; }
    if (!project || !folderRef.current) { openSave(); return; }
    if (mode === 'structure' && !dirty) { await ensureFolderPermission(folderRef.current, true); await syncFolder(project.id); setNotice('结构与项目文件已同步到本地文件夹。'); return project; }
    if (codePreview && manualDirty && codePreview.code !== code && !window.confirm('保存此候选会替换当前手工草稿。先返回原稿保存，或确认继续？')) return;
    await ensureFolderPermission(folderRef.current, true);
    const saved = await api<Project>('/projects/' + project.id, 'PUT', { code: visibleCode, name, boardId: board, componentIds: components, expectedRevision: draftRevision ?? project.revision });
    try { localStorage.removeItem('mu-draft-' + project.id); } catch { /* unavailable */ }
    applyProject(saved, false); await refreshProjects(); await syncFolder(saved.id); setNotice(`已保存到本机 · 版本 ${saved.revision}`);
    return saved;
  };
  const saveRef = useRef(save); saveRef.current = save;
  useEffect(() => {
    const key = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') { event.preventDefault(); if (!busyRef.current && !structureBusyRef.current) void action('保存', () => saveRef.current()); } };
    window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key);
  }, []);
  const chooseProject = async (id: string) => {
    if (id === project?.id) return true;
    if (dirty && !window.confirm('当前修改尚未保存。草稿保留在本浏览器；仍要切换项目吗？')) return false;
    persistDraftNow();
    let opened = false;
    await action('打开项目', async () => { applyProject(await api<Project>('/projects/' + id)); setGuideScope(value => value + 1); opened = true; });
    return opened;
  };
  const selectNewFolder = async () => {
    const selection = pickProjectDirectory();
    await action('选择项目文件夹', async () => {
      try {
        const handle = await selection; await prepareNewDirectory(handle); setNewFolder(handle);
        if (!newName.trim() || newName === '我的项目') setNewName(handle.name.slice(0, 80));
      } catch (err) { if (!pickerCancelled(err)) throw err; }
    });
  };
  const finishFolderProject = async () => {
    if (!newFolder) throw new Error('请先选择本地项目文件夹。');
    if (creationMode === 'save' && codePreview && manualDirty && codePreview.code !== code && !window.confirm('保存此候选会替换当前手工草稿。先返回原稿保存，或确认继续？')) return;
    await prepareNewDirectory(newFolder);
    if (creationMode === 'save' && project && folderRef.current) await copyProjectPrograms(folderRef.current, newFolder);
    persistDraftNow();
    const request: CreateProject = { name: newName, boardId: creationMode === 'new' ? '' : board, code: creationMode === 'new' ? '' : visibleCode, componentIds: creationMode === 'new' ? [] : components };
    const value = creationMode === 'save' && project
      ? await api<Project>('/projects/' + project.id, 'PUT', { ...request, expectedRevision: draftRevision ?? project.revision })
      : await api<Project>('/projects', 'POST', request);
    applyProject(value, false);
    bindFolder({ projectId: value.id, handle: newFolder, checkpointHash: null, mainHash: null }, '未同步');
    setNewDialog(false); setGuideScope(count => count + 1); setMobileTab('code');
    if (creationMode === 'new') setHardwareCollapsed(false);
    try { localStorage.removeItem('mu-scratch-code'); localStorage.removeItem('mu-scratch-hardware'); localStorage.removeItem('mu-draft-' + value.id); } catch { /* unavailable */ }
    await refreshProjects(); await syncFolder(value.id);
    setNotice(creationMode === 'new' ? '项目已创建，可在左侧选择主控板。' : '项目已保存到本机；文件夹同步状态见项目文件夹栏。');
    if (uploadAfterSave) { setUploadAfterSave(false); await uploadSaved(value); }
  };
  const loadFolder = async () => {
    if (dirty && !window.confirm('当前修改尚未保存，仍要加载另一个项目文件夹吗？本浏览器草稿会保留。')) return;
    const selection = pickProjectDirectory();
    await action('加载项目文件夹', async () => {
      try {
        const handle = await selection, loaded = await readProjectDirectory(handle);
        const value = await api<Project>('/projects/import', 'POST', loaded.snapshot);
        persistDraftNow(); applyProject(value, false);
        const binding = { ...loaded.binding, projectId: value.id }; bindFolder(binding, '已载入');
        await rememberFolder(binding).catch(err => { setFolderError(errorText(err)); });
        if (loaded.externalCode !== null) { setCode(loaded.externalCode); setSelectedVersion(null); setNotice('文件夹 main.py 与快照不同，已作为未保存草稿载入；原对话和版本仍保留，保存后产生新版本。'); }
        else setNotice('已从项目文件夹恢复代码、过往对话与历史版本。');
        setLoadDialog(false); setGuideScope(count => count + 1); setMobileTab('ai'); await refreshProjects();
      } catch (err) { if (!pickerCancelled(err)) throw err; }
    });
  };
  const switchBoard = (id: string) => {
    if (id === board) return;
    setBoard(id); setCheck(null); setCandidate(null); setCodePreview(null); setChatError('');
    setGuideScope(count => count + 1); setGuideReveal(count => count + 1); setMobileTab('ai');
    setNotice(board ? '已切换主控，对话按新主控更新；旧主控对话保留在历史区，当前代码请重新核对。' : '已选择主控，可添加模块或开始对话；保存后记录到项目。');
  };
  const selectCodeVersion = (revision: number) => {
    const version = codeVersions.find(item => item.revision === revision); if (!version) return;
    if (version.boardId && version.boardId !== board && !window.confirm('此版本来自其他主控。仅将代码载入草稿，当前主控不变；确认继续核对吗？')) return;
    if (version.source === 'ai') { setCodePreview(version); setCheck(null); setMobileTab('code'); return; }
    if (dirty && version.code !== code && !window.confirm('用历史版本替换当前未保存代码？当前草稿建议先保存或导出。')) return;
    setCode(version.code); setCodePreview(null); setSelectedVersion(revision); setCheck(null); setCandidate(null);
    setNotice(revision === project?.revision ? '已载入当前保存版本。' : '历史代码已载入草稿；保存会创建新版本，原历史不会覆盖。');
  };
  const openDetail = (item: HardwareSummary, fromPicker = false, edit = false) => void action('读取资料', async () => {
    const value = await api<HardwareDetail>('/hardware/' + item.skillName);
    setReturnToPicker(fromPicker); if (fromPicker) setSensorPicker(false); setEditExample(edit); setDetail(value);
  });
  const clearModuleFilters = () => { setSearch(''); setModuleFilter('all'); setModuleBrandFilter('all'); setModuleTypeFilter(''); };
  const openSensorPicker = () => { clearModuleFilters(); setPendingSensors([]); setSensorPicker(true); };
  const loadModuleSample = (item: HardwareSummary) => void action('读取模块示例', async () => {
    const value = await api<HardwareDetail>('/hardware/' + item.skillName);
    const samples = value.files.filter(file => file.path.startsWith('examples/'));
    const pythonFile = samples.find(file => file.path.endsWith('.py'));
    const blocks = samples.flatMap(file => [...file.content.matchAll(/```(?:python|micropython|py)\s*\n([\s\S]*?)```/g)].map(match => match[1]));
    const guide = value.moduleGuides?.find(example => example.boardId === board);
    const local = value.localExamples?.find(example => example.boardId === board);
    const sample = local?.code.trim() || (guide ? guideCode(guide, local?.setup) : value.moduleGuides?.length ? '' : pythonFile?.content || blocks[0]);
    if (!sample?.trim()) { setNotice('此模块资料包尚无可直接载入的 Python 示例，请查看完整资料。'); return; }
    setModuleSample({ item, code: sample.trimEnd() + '\n', base: code,
      scope: local?.code.trim() ? '本机保存的当前主控案例；请核对实际接线。' : guide ? guideKind[guide.kind] + '。' + guide.summary : undefined });
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
  const runProgram = async () => {
    const activeDevice = device.current;
    if (!activeDevice) return;
    await activeDevice.run();
    const uploaded = activeDevice.receipt;
    if (uploaded) setRunSubmission({ projectId: uploaded.projectId, revision: uploaded.revision, boardId: board, sha256: uploaded.sha256, submittedAt: new Date().toISOString() });
  };
  const uploadSaved = async (saved: Project) => {
    if (device.current?.state !== 'connected') throw new Error('先连接设备并停止程序。');
    const targetDevice = device.current;
    const plan = await api<UploadManifest>(`/projects/${saved.id}/upload-manifest`, 'POST', { expectedRevision: saved.revision });
    if (currentProject.current !== saved.id || currentCode.current !== saved.code || currentHardware.current.board !== saved.boardId
      || JSON.stringify(currentHardware.current.components) !== JSON.stringify(saved.componentIds)) throw new Error('准备上传时项目已变更，请再次点击上传。');
    if (device.current !== targetDevice || targetDevice.state !== 'connected') throw new Error('设备连接已变更，请重新连接后上传。');
    setProgress(0);
    try {
      await targetDevice.upload(plan, persistBackup, (done, total) => setProgress(total ? Math.round(done / total * 100) : 100));
      setNotice('main.py 上传回读一致。程序尚未运行。');
    } finally { setProgress(null); }
  };
  const prepareUpload = async () => {
    setTerminalOpen(true); setMobileTab('code');
    if (!device.current || device.current.state === 'disconnected') await connectDevice();
    if (device.current?.state !== 'connected') return;
    if (!project) { setUploadAfterSave(true); openSave(); return; }
    await action('保存并上传', async () => {
      const saved = dirty ? await save() : project;
      if (saved) await uploadSaved(saved);
    });
  };
  const sendRepl = async () => {
    const command = repl;
    if (!command.trim() || busy || deviceBusy) return;
    if (!device.current || device.current.state === 'disconnected') await connectDevice();
    const target = device.current;
    if (!target || !['connected', 'running'].includes(target.state)) return;
    await action('发送 REPL', async () => {
      if (target.state === 'running') await target.stop();
      await target.repl(command); setRepl(value => value === command ? '' : value);
    });
  };
  const sendMessage = async (preset?: string, intent?: 'integration') => {
    const prompt = preset ?? message;
    if (!prompt.trim() || sendingMessage.current || loading || busy || !board) return;
    const base = visibleCode; const chatBoard = board; const chatComponents = [...components];
    let id = project?.id;
    sendingMessage.current = true;
    setAiBusy(true); setAiPhase('preparing'); setStreamedReply(''); setError(''); setChatError('');
    try {
      // Refresh the token/config so a server restart or another tab cannot silently disable sending.
      const session = await bootstrap();
      setAiConfigured(session.aiConfigured); setAiModel(session.aiModel ?? DEFAULT_AI_MODEL);
      setAiBaseUrl(session.aiBaseUrl ?? 'https://api.deepseek.com');
      if (!session.aiConfigured) { setAiSettingsDialog(true); setChatError('先填写 API Key，保存后再发送。输入内容已保留。'); return; }
      followConversation.current = true; setPendingPrompt(prompt);
      if (!id) {
        const created = await api<Project>('/projects', 'POST', { name: name === '未命名项目' ? '我的项目' : name, code: base, boardId: chatBoard, componentIds: chatComponents } satisfies CreateProject);
        id = created.id;
        // Adopt the saved snapshot without overwriting edits made while this request was pending.
        setProject(created); currentProject.current = id; setName(created.name); setDraftRevision(null);
        setSelectedVersion(currentCode.current === base ? created.revision : null);
        setMessages(created.messages); store('mu-active-project', id);
        setProjects(value => [created, ...value.filter(item => item.id !== id)]);
        setNotice('已为首次对话保存当前项目。');
      }
      const controller = new AbortController(); aiController.current = controller;
      setAiPhase('waiting'); setCandidate(null);
      const result = await chat(id, { message: prompt, code: base, boardId: chatBoard, componentIds: chatComponents, ...(intent ? { intent } : {}) }, controller.signal, event => {
        if (event.type === 'delta') { setAiPhase('generating'); setStreamedReply(value => value + event.content); }
      });
      if (currentProject.current === id) {
        setMessages(result.messages); if (preset === undefined) setMessage(value => value === prompt ? '' : value);
        const reply = result.messages.filter(item => item.role === 'assistant' && item.status === 'COMPLETED').at(-1);
        const suggestion = reply ? replyCode(reply.content) : null;
        let history = { versions: codeVersions };
        try { history = await api<{ versions: Version[] }>(`/projects/${id}/versions`); setCodeVersions(history.versions); }
        catch { setNotice('回复已完成，暂时无法读取版本号；代码候选仍可预览，请稍后刷新历史。'); }
        if (suggestion !== null) {
          const version = history.versions.find(item => item.messageId === reply?.id) ?? history.versions.find(item => item.source === 'ai' && item.code === suggestion && item.boardId === chatBoard);
          const next = { code: suggestion, revision: version?.revision, boardId: chatBoard };
          setCandidate(next);
          if (currentCode.current === base && !manualCodeDirtyRef.current) { setCodePreview(next); setCheck(null); }
        }
        setHistoryRefresh(count => count + 1); await syncFolder(id);
      }
    } catch (err) {
      const detail = aiController.current?.signal.aborted ? '已取消本次 AI 请求。输入已保留，代码未修改。' : errorText(err);
      setError(detail); setChatError(detail);
      if (id && currentProject.current === id) {
        try { const saved = await api<Project>('/projects/' + id); setMessages(saved.messages); } catch { /* keep the prompt and existing conversation for retry */ }
        await syncFolder(id);
      }
    } finally { aiController.current = null; sendingMessage.current = false; setAiBusy(false); setPendingPrompt(''); setStreamedReply(''); }
  };
  const showReplyCode = (content: string, messageId: string, boardId?: string) => {
    const value = replyCode(content); if (value === null) return;
    if (boardId && boardId !== board && !window.confirm('此代码来自其他主控，仅预览代码，当前主控不变。继续吗？')) return;
    const version = codeVersions.find(item => item.messageId === messageId);
    setCodePreview({ code: value, revision: version?.revision, boardId }); setCheck(null); setMobileTab('code');
  };
  const editPreview = () => {
    if (!codePreview) return;
    if (manualDirty && codePreview.code !== code && !window.confirm('用此候选替换未保存的手工草稿？可先返回原稿保存或导出。')) return;
    setCode(codePreview.code); setSelectedVersion(codePreview.revision ?? null); setCodePreview(null); setCandidate(null); setCheck(null);
  };
  const fillReply = (answer: string) => { setMessage(value => (value.trim() ? value + '\n' + answer : answer).slice(0, 4000)); chatInput.current?.focus(); };
  const boardSensors = selectableModules(hardware);
  const available = filterModules(boardSensors, moduleBrandFilter, moduleFilter, moduleTypeFilter, search);
  const outsideLibrary = components.filter(id => !boardSensors.some(item => item.componentId === id));
  const selectedSensors = components.map(id => hardware.find(item => item.componentId === id)).filter((item): item is HardwareSummary => !!item && !!moduleDirection(item));
  const receipt = device.current?.receipt;
  const canRun = connected && receipt && !dirty && receipt.projectId === project?.id && receipt.revision === project.revision;
  const activeMessages = messages.filter(item => (item.boardId ?? project?.boardId ?? board) === board);
  const pastMessages = messages.filter(item => !activeMessages.includes(item));

  return <div className={`app final-workbench ${hardwareCollapsed ? 'hardware-collapsed' : ''} ${codeFullscreen ? 'code-fullscreen' : ''}`}>
    <header className="workspace-titlebar">
      <a className="title-brand" href="/" aria-label="掌问工作台"><span><img src={palmMark} alt="" width={24} height={24} /></span><strong>掌问</strong></a>
      <span className="title-filename title-mode" aria-label="当前模式">{modeInfo.name}</span>
      <div className="current-project" aria-label="当前项目" title={name}><strong>{name}</strong>{dirty && <span className="dirty-dot" aria-label="代码未保存" />}</div>
      <span className="document-info">{mode === 'engineer' ? `${dirty ? '未保存更改' : project ? '本地工作区' : '未保存'} · ${zoom}%` : mode === 'structure' ? '结构工作区 · 本机保存' : '学习工作区 · 界面预览'}</span>
      <button className="theme-toggle" aria-label={theme === 'light' ? '切换深色主题' : '切换浅色主题'} title={theme === 'light' ? '深色主题' : '浅色主题'} onClick={() => setTheme(value => value === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={17} /> : <Sun size={17} />}</button>
    </header>
    <header className="mu-toolbar" aria-label="Mu 工具栏">
      <div className="mu-commands">
        <div className="tool-group" role="group" aria-label="三师模式">
        <MuTool icon={Layers3} label="模式" aria-label="模式切换" variant="brand" active={modeDialog} disabled={loading || !!busy || aiBusy || structureBusy || deviceBusy || running || flashing || deviceState === 'attention'} onClick={() => setModeDialog(true)} title={`切换三师模式 · ${modeInfo.name}`} />
        </div>
        {mode === 'engineer' && <><div className="tool-group" role="group" aria-label="项目操作">
        <MuTool icon={Plus} label="新建" aria-label="新建项目" disabled={loading || !!busy || aiBusy || deviceBusy} onClick={openNew} />
        <MuTool icon={FolderOpen} label="加载" active={loadDialog} disabled={loading || !!busy || aiBusy || deviceBusy} onClick={() => void action('读取项目', async () => { await refreshProjects(); setLoadDialog(true); })} />
        <MuTool icon={Save} label="保存" disabled={loading || !!busy || (aiBusy && !project)} onClick={() => void action('保存', save)} />
        <MuTool icon={Files} label="文件" active={filesDialog || versions !== null} disabled={loading || !!busy || deviceBusy} onClick={() => void action('读取文件信息', async () => { setFileVersions(project ? (await api<{ versions: Version[] }>(`/projects/${project.id}/versions`)).versions : null); setFilesDialog(true); })} title="本机代码、设备文件与项目历史版本" />
        </div>
        <div className="tool-group" role="group" aria-label="开发工具">
        <MuTool icon={CheckCheck} label="检查" disabled={loading || !board || !!busy} onClick={() => void action('检查', async () => { const result = await api<CheckResult>('/check', 'POST', { code: visibleCode, boardId: board, componentIds: components }); setCheck(result); setMobileTab('code'); })} />
        <MuTool icon={AlignLeft} label="格式化" title="按 Python 语法整理四空格缩进（可撤销），不运行代码" disabled={loading || !!busy || !!codePreview || !code.length} onClick={() => { setMobileTab('code'); editor.current?.formatIndentation(); setCheck(null); setNotice('已按 Python 语法整理四空格缩进，可在编辑器中撤销。请检查后再保存。'); }} />
        </div>
        <div className="tool-group" role="group" aria-label="设备操作">
        <MuTool icon={ArrowUp} label="上传" variant="hardware" disabled={loading || !board || !!busy || aiBusy || deviceBusy || running || deviceState === 'attention'} onClick={() => void prepareUpload()} title="保存并上传 main.py，自动备份和回读校验" />
        <MuTool icon={running || deviceState === 'attention' ? Square : Play} label={running || deviceState === 'attention' ? '停止' : '运行'} emphasis active={running} disabled={!!busy || deviceBusy || !(running || canRun || deviceState === 'attention')} onClick={() => { setTerminalOpen(true); setMobileTab('code'); void action(running || deviceState === 'attention' ? '停止' : '运行', async () => { if (running || deviceState === 'attention') await device.current?.stop(); else await runProgram(); }); }} />
        <MuTool icon={Terminal} label="REPL" active={terminalOpen} aria-pressed={terminalOpen} onClick={() => { setTerminalOpen(value => !value); setMobileTab('code'); }} />
        <MuTool icon={Cpu} label="固件刷入" variant="hardware" disabled={loading || !board || !!busy || aiBusy || flashing || deviceState !== 'disconnected'} title={board ? `刷入 ${boardInfo?.displayName ?? '当前主控'} 对应固件；请先断开设备` : '请先在左侧选择主控板'} onClick={() => setFirmwareDialog(true)} />
        </div></>}
        {mode === 'structure' && <><div className="tool-group" role="group" aria-label="结构项目操作">
          <MuTool icon={Plus} label="新建" aria-label="新建项目" disabled={loading || structureBusy || !!busy} onClick={openNew} />
          <MuTool icon={FolderOpen} label="加载" disabled={loading || structureBusy || !!busy} onClick={() => void action('读取项目', async () => { await refreshProjects(); setLoadDialog(true); })} />
          <MuTool icon={Save} label="保存" disabled={loading || structureBusy || !!busy} onClick={() => void action('保存', save)} />
        </div><div className="tool-group" role="group" aria-label="结构设计功能">
          <MuTool icon={Box} label="3D建模" active={structureDesignType === 'model'} aria-pressed={structureDesignType === 'model'} disabled={structureBusy} onClick={() => setStructureDesignType('model')} />
          <MuTool icon={ScanLine} label="激光切割图纸" active={structureDesignType === 'laser'} aria-pressed={structureDesignType === 'laser'} disabled={structureBusy} onClick={() => setStructureDesignType('laser')} />
        </div></>}
        {mode === 'learning' && <><div className="tool-group" role="group" aria-label="学习栏目切换">
          {learningSections.map(({id,label,note,icon})=><MuTool key={id} icon={icon} label={label} active={learningSection === id} variant={learningSection === id ? 'software' : 'muted'} aria-pressed={learningSection === id} aria-controls="learning-section-content" onClick={()=>setLearningSection(id)} title={`${label}${note ? ` · ${note}` : ''}`} />)}
        </div><div className="tool-group" role="group" aria-label="学习工作台操作">
          <MuTool icon={learningRole === 'teacher' ? GraduationCap : UserRound} label="切换视角" active={learningRoleDialog} onClick={() => setLearningRoleDialog(true)} title={`当前：${learningRole === 'teacher' ? '教师工作台' : '学生工作台'}，点击切换`} />
          <MuTool icon={Plus} label="新建" aria-label="新建学习项目（待开发）" disabled title="学习项目操作待开发，当前可预览界面" />
          <MuTool icon={FolderOpen} label="加载" disabled title="学习项目加载待开发" />
          <MuTool icon={Save} label="保存" disabled title="学习内容保存待开发" />
        </div></>}
        <div className="tool-group" role="group" aria-label="设置与帮助">
        <MuTool icon={Settings} label="API 设置" variant="muted" active={aiSettingsDialog} disabled={loading || !!busy || aiBusy || structureBusy} onClick={openAiSettings} title="设置掌问 AI API" />
        <UpdateCenter enabled={!loading} blocked={!!busy || aiBusy || structureBusy || deviceBusy || running || flashing || deviceState === 'attention'} unsaved={dirty || !!folderError || folderPending.current > 0} />
        <MuTool icon={HelpCircle} label="帮助" variant="muted" active={helpDialog} onClick={() => setHelpDialog(true)} />
        </div>
      </div>
      {(mode === 'engineer' || deviceState !== 'disconnected') && <button className={`connection toolbar-status ${deviceState !== 'disconnected' ? 'is-connected' : ''}`} disabled={!!busy || deviceBusy} onClick={deviceState === 'disconnected' ? () => { setTerminalOpen(true); setMobileTab('code'); void connectDevice(); } : disconnect}>{deviceBusy ? <LoaderCircle size={17} className="spin" /> : deviceState === 'disconnected' ? <Usb size={17} /> : <Unplug size={17} />}<span>{deviceState === 'disconnected' ? '连接设备' : deviceState === 'connecting' ? '正在连接' : deviceState === 'attention' ? '需要重连 · 断开' : '已连接 · 断开'}</span></button>}
    </header>
    <FeedbackToast error={error} notice={notice} sequence={noticeSequence} busy={busy} progress={progress} onCancel={() => device.current?.cancel()} />
    <div className="engineering-surface" hidden={mode !== 'engineer'}>
    <nav className="mobile-tabs" aria-label="工作区切换">{[['hardware', '硬件库'], ['ai', '掌问 AI'], ['code', '代码']].map(([key, label]) => <button key={key} className={mobileTab === key ? 'active' : ''} onClick={() => { setMobileTab(key); if (key === 'hardware') setHardwareCollapsed(false); }}>{label}</button>)}</nav>
    <main className="workbench">
      <aside className={`hardware-panel panel mobile-${mobileTab === 'hardware' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><CircuitBoard size={18} />已加入的模块</h2><button className="icon-button hardware-collapse" aria-label="收起硬件模块" title="向左收起硬件模块" onClick={() => setHardwareCollapsed(true)}><PanelLeftClose size={17} /></button></div>
        <div className="selected-sensors-toolbar"><span className="board-field-label">主控板</span><button className={`board-control${board ? '' : ' needs-board'}`} aria-label="主控板" title={board ? '点击更换主控板' : '选择项目使用的主控板'} disabled={loading || !!busy || aiBusy || deviceBusy} onClick={() => setBoardDialog(true)}><BoardArtwork board={boardInfo} /><span>{boardInfo?.displayName ?? '选择主控板'}</span><ChevronRight size={14} /></button>{!board && !loading && <p className="board-select-hint">先选主控，再添加模块</p>}<button className="add-sensor-button" disabled={loading || !!busy || aiBusy || deviceBusy || !board} onClick={openSensorPicker}><Plus size={18} />添加模块</button></div>
        <div className="catalog-list selected-sensor-list">{loading ? <p className="muted">正在读取项目…</p> : (['input', 'output'] as const).map(direction => {
          const items = selectedSensors.filter(item => moduleDirection(item) === direction);
          return items.length > 0 && <section className="module-group" key={direction} aria-label={direction === 'input' ? '已加入的输入模块' : '已加入的输出模块'}><h3>{direction === 'input' ? '输入模块' : '输出模块'}<span>{items.length}</span></h3><div className="module-grid">{items.map(item => <ModuleCard key={item.componentId} item={item} disabled={!!busy || aiBusy || deviceBusy} outside={!boardSensors.some(module => module.componentId === item.componentId)} onDetail={() => openDetail(item)} onEditExample={() => openDetail(item, false, true)} onLoad={() => loadModuleSample(item)} onRemove={() => { setComponents(value => value.filter(id => id !== item.componentId)); setCheck(null); setCandidate(null); setCodePreview(null); }} />)}</div></section>;
        })}{!loading && board && !selectedSensors.length && <div className="selected-sensors-empty"><CircuitBoard size={42} /><strong>为项目添加模块</strong><p>点击「添加模块」，选择传感器、执行器或显示模块。</p></div>}</div>
        {outsideLibrary.length > 0 && <p className="library-notice">有 {outsideLibrary.length} 个项目元件的资料缺失或未激活，已保留；请查看资料并核对。</p>}
        <footer className="catalog-foot"><BookOpen size={16} /><span>输入感知 · 输出控制<br /><small>点击模块查看资料，⋮ 展开选项</small></span></footer>
      </aside>
      <button className="hardware-restore" aria-label="展开硬件模块" title="展开硬件模块" onClick={() => { setHardwareCollapsed(false); setMobileTab('hardware'); }}><PanelLeftOpen size={18} /><span>硬件模块</span><small>{selectedSensors.length}</small></button>
      <section className={`ai-panel panel mobile-${mobileTab === 'ai' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Sparkles size={18} />掌问 AI</h2><button className="api-settings-entry" disabled={loading || !!busy || aiBusy} onClick={openAiSettings} aria-label="掌问 AI API 设置"><Settings size={14} /><span>{aiConfigured ? '已配置' : '未配置'}</span> · 设置</button></div>
        <div ref={conversationPane} className="messages" role="log" aria-label="掌问对话记录" onWheel={event => { if (event.deltaY < 0) followConversation.current = false; }} onPointerDown={event => { if (event.target === event.currentTarget) followConversation.current = false; }} onKeyDown={event => { if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) followConversation.current = false; }} onScroll={event => { const pane = event.currentTarget; if (pane.scrollHeight - pane.scrollTop - pane.clientHeight <= 64) followConversation.current = true; }}>
          {!loading && boardInfo && <section ref={components.length ? undefined : hardwareGuide} tabIndex={-1} className="conversation-board-context" aria-label="当前主控对话"><BoardArtwork board={boardInfo} /><div><strong>{boardInfo.displayName}</strong><p>按当前主控的固件与编程参考继续对话。</p></div></section>}
          {!loading && components.length > 0 && <section ref={hardwareGuide} className="message assistant hardware-guide" aria-label="掌问硬件引导" tabIndex={-1}>
            <HardwareGuide key={JSON.stringify([guideScope, board, components])} board={boardInfo} componentIds={components} hardware={hardware} disabled={loading || !!busy || aiBusy || deviceBusy || !board} onTest={() => void sendMessage(integrationPrompt(boardInfo, board, components, hardware), 'integration')} onDevelop={() => chatInput.current?.focus()} />
          </section>}
          {!loading && !board && <section className="board-selection-prompt" aria-label="选择主控引导"><CircuitBoard size={24} /><div><strong>这个项目使用哪款主控？</strong><p>选择后，掌问会按对应的固件和库生成代码。</p></div><button className="primary" disabled={!!busy || aiBusy || deviceBusy} onClick={() => setBoardDialog(true)}>选择主控</button></section>}
          {board && !activeMessages.length && !pendingPrompt && !components.length && <div className="conversation-empty"><span><Sparkles size={24} strokeWidth={1.6} /></span><p>描述你的想法，或粘贴需要分析的代码与报错。</p></div>}
          {pastMessages.length > 0 && <details className="past-board-conversations"><summary>之前主控的对话 · {pastMessages.length} 条</summary>{pastMessages.map(item => <article className={`message ${item.role}`} key={item.id}><strong>{hardware.find(value => value.componentId === (item.boardId ?? project?.boardId))?.displayName ?? '之前主控'} · {item.role === 'user' ? '你' : '掌问'}</strong>{item.role === 'assistant' && item.status === 'COMPLETED' ? <AssistantMessage content={item.content} revision={codeVersions.find(version => version.messageId === item.id)?.revision} disabled={!!busy || aiBusy || deviceBusy} onCode={() => showReplyCode(item.content, item.id, item.boardId ?? project?.boardId)} /> : item.role === 'user' ? <UserMessage content={item.content} /> : <pre>{item.content}</pre>}</article>)}</details>}
          {activeMessages.map(item => <article className={`message ${item.role}`} key={item.id}><strong>{item.role === 'user' ? '你' : '掌问'}{item.status === 'FAILED' ? ' · 请求失败' : ''}</strong>{item.role === 'assistant' && item.status === 'COMPLETED' ? <AssistantMessage content={item.content} revision={codeVersions.find(version => version.messageId === item.id)?.revision} disabled={!!busy || aiBusy || deviceBusy} onCode={() => showReplyCode(item.content, item.id, item.boardId ?? project?.boardId)} onReply={item.id === activeMessages.filter(value => value.role === 'assistant' && value.status === 'COMPLETED').at(-1)?.id ? fillReply : undefined} /> : item.role === 'user' ? <UserMessage content={item.content} /> : <pre>{item.content}</pre>}</article>)}
          {pendingPrompt && <article className="message user"><strong>你 · 正在发送</strong><UserMessage content={pendingPrompt} /></article>}
          {aiBusy && streamedReply && <article className="message assistant"><strong>掌问 · 正在生成</strong><pre>{streamText(streamedReply)}</pre></article>}
          {aiBusy && <div className="ai-progress"><p className="muted" role="status"><LoaderCircle size={16} className="spin" /> {aiPhase === 'preparing' ? '正在准备对话' : aiPhase === 'waiting' ? `正在等待 ${aiBaseUrl.startsWith('https://api.deepseek.com') ? 'DeepSeek' : '模型'} 回答` : '正在生成回答'} · {aiElapsed} 秒</p>{aiPhase !== 'preparing' && <button type="button" onClick={() => aiController.current?.abort()}>取消生成</button>}{aiPhase === 'waiting' && aiElapsed >= 20 && <small>供应商暂未返回正文，可继续等待或取消后稍后重试。</small>}</div>}
          {candidate && !codePreview && <div className="candidate"><FileCode2 size={19} /><span>新代码已生成，当前草稿已保留。</span><button disabled={!!busy || deviceBusy || aiBusy} onClick={() => { setCodePreview(candidate); setCheck(null); setMobileTab('code'); }}>查看新版本</button></div>}
        </div>
        {chatError && <p className="chat-error" role="alert">{chatError}</p>}
        {!project && <p className="chat-hint">首次发送会自动保存当前项目、代码和已加入模块。</p>}
        <form className="chat-form" onSubmit={event => { event.preventDefault(); void sendMessage(); }}><label className="sr-only" htmlFor="chat-message">发送给掌问 AI</label><textarea ref={chatInput} id="chat-message" value={message} onChange={event => setMessage(event.target.value)} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.nativeEvent.isComposing && !loading && !busy && !aiBusy && message.trim()) { event.preventDefault(); void sendMessage(); } }} placeholder="和掌问聊聊你的想法…" maxLength={4000} /><div><span>{!board ? "请先选择项目使用的主控板" : !aiConfigured ? "AI 未配置 · 点击 API 设置" : "候选预览后保存，设备操作单独确认"}</span><button className="primary icon-button" aria-label="发送" disabled={loading || !!busy || !board || !message.trim() || aiBusy}>{aiBusy ? <LoaderCircle size={19} className="spin" /> : <ArrowUp size={20} />}</button></div></form>
      </section>
      <section className={`code-panel panel mobile-${mobileTab === 'code' ? 'show' : 'hide'}`}>
        <div className="filebar"><span><FileCode2 size={16} />main.py</span><span className="filebar-space" /><span className={dirty ? 'unsaved' : 'status-ready'}>{project ? dirty ? '未保存' : '已保存' : '项目尚未保存'}</span><select className="code-version-select" aria-label="代码历史版本" disabled={!project || !codeVersions.length || !!busy || aiBusy || deviceBusy} value={codePreview ? codePreview.revision ?? 'preview' : selectedVersion ?? 'draft'} onChange={event => { if (event.target.value === 'draft') setCodePreview(null); else selectCodeVersion(Number(event.target.value)); }}><option value="draft" disabled={!codePreview}>{project ? '未保存草稿' : '尚无版本'}</option>{codePreview && !codePreview.revision && <option value="preview">AI候选 · 未保存</option>}{codeVersions.map(version => <option key={version.revision} value={version.revision}>V{version.revision} · {version.name || "MicroPython 程序"} · {version.source === 'ai' ? 'AI候选 · 未保存' : '已保存'}{version.boardId && version.boardId !== board ? ' · 其他主控' : ''}</option>)}</select><div className="editor-view-controls"><button aria-label="缩小代码" title="缩小代码" disabled={zoom <= 80} onClick={() => setZoom(value => Math.max(80, value - 10))}><ZoomOut size={16} /></button><span aria-label="代码字号比例">{zoom}%</span><button aria-label="放大代码" title="放大代码" disabled={zoom >= 160} onClick={() => setZoom(value => Math.min(160, value + 10))}><ZoomIn size={16} /></button><button aria-label={codeFullscreen ? '退出代码全屏' : '代码全屏'} title={codeFullscreen ? '退出全屏（Esc）' : '代码全屏'} onClick={() => setCodeFullscreen(value => !value)}>{codeFullscreen ? <Minimize size={16} /> : <Maximize size={16} />}</button></div><button aria-label="导出当前代码" onClick={() => download("main.py", visibleCode)}><Download size={16} />导出</button></div>
        {project && <div className={`project-folder-status ${folderError ? 'has-error' : ''}`} role="status"><FolderOpen size={14} /><span>{folder ? `${folder.handle.name} · ${folderStatus}` : '仅在本机 · 保存时选择项目文件夹'}</span>{folder && <button disabled={!!busy || aiBusy || deviceBusy} onClick={() => { setUploadAfterSave(false); openSave(); }}>另存文件夹</button>}{folderError && <p>{folderError}</p>}</div>}
        {codePreview && <section className="code-preview-banner" aria-label="AI代码候选预览"><div><strong>AI候选{codePreview.revision ? ` · v${codePreview.revision}` : ''} · 尚未保存</strong><small>{manualDirty ? '原手工草稿已保留，可随时返回。' : '原保存版本保留在历史中。'}{codePreview.boardId && codePreview.boardId !== board && ' 此代码来自其他主控，请核对兼容性。'}</small></div><button disabled={!!busy || aiBusy || deviceBusy} onClick={editPreview}>继续编辑此版本</button><button disabled={!!busy || aiBusy || deviceBusy} onClick={() => { setCodePreview(null); setCheck(null); }}>返回原稿</button><button className="primary" disabled={!!busy || aiBusy || deviceBusy} onClick={() => void action('保存', save)}>保存此版本</button></section>}
        <Editor ref={editor} zoom={zoom} readOnly={loading || !!busy || deviceBusy || codePreview !== null} value={visibleCode} onChange={value => { setCode(value); setSelectedVersion(null); setCheck(null); }} />
        {check && <section className="check-results" aria-label="检查结果"><div><strong>{check.valid ? '静态检查完成' : '检查发现问题'}</strong><button className="icon-button" aria-label="关闭检查" onClick={() => setCheck(null)}><X size={16} /></button></div>{check.diagnostics.map((item, index) => <p className={`diagnostic ${item.severity.toLowerCase()}`} key={index}><span>{item.severity === 'PASS' ? '通过' : item.severity === 'FAIL' ? '错误' : '提示'}</span>{item.line ? `第 ${item.line} 行 · ` : ''}{item.message}</p>)}</section>}
        <section className="terminal-panel" hidden={!terminalOpen}><div className="terminal-head"><h3><Terminal size={17} />串口终端</h3><span>{running ? '正在执行 · 发送会先中断' : connected ? 'REPL 已连接' : deviceState === 'attention' ? '连接需核对' : '未连接'}</span><button disabled={!!busy} onClick={() => setLogs('')}>清空</button><button onClick={() => void action('导出设备备份', async () => { const backup = await latestBackup(); if (!backup) throw new Error('尚无设备备份。'); if (backup.bytes) download('main-before-upload.py', backup.bytes); else setNotice('上次上传前设备不存在 main.py，无需恢复旧文件。'); })}>备份</button><button aria-label="收起终端" onClick={() => setTerminalOpen(false)}><X size={16} /></button></div><pre className="serial-log" aria-label="串口输出">{logs}</pre><form className="repl-form" onSubmit={event => { event.preventDefault(); void sendRepl(); }}><span aria-hidden="true">&gt;&gt;&gt;</span><input aria-label="REPL 命令" placeholder={running ? '输入命令，发送时先中断当前程序' : connected ? '输入命令，按 Enter 发送' : '输入命令，发送时选择并连接设备'} value={repl} maxLength={4000} onChange={event => setRepl(event.target.value)} onKeyDown={event => { if (event.ctrlKey && event.key.toLowerCase() === 'c' && event.currentTarget.selectionStart === event.currentTarget.selectionEnd && running && !busy) { event.preventDefault(); void action('中断程序', () => device.current!.stop()); } }} disabled={!!busy || deviceBusy} /><button disabled={!repl.trim() || !!busy || deviceBusy || deviceState === 'attention'} title={running ? '中断当前程序并发送' : connected ? '发送命令' : '连接设备并发送'} aria-label="发送 REPL 命令"><ArrowUp size={17} /></button></form></section>
      </section>
    </main>
    </div>
    <StructureWorkspace key={`${project?.id ?? 'new'}-${structureDesignType}`} designType={structureDesignType} draft={structureDrafts[structureDesignType]} onDraftChange={value => setStructureDrafts(prev => ({...prev, [structureDesignType]: value}))} projectId={project?.id} active={mode === 'structure'} board={boardInfo} modules={selectedSensors} onSaveProject={openSave} onSettings={openAiSettings} onBusy={setStructureBusy} onSaved={syncFolder} />
    <LearningWorkspace active={mode === 'learning'} projectName={name} project={project} board={boardInfo} modules={selectedSensors} role={learningRole} onRole={setLearningRole} section={learningSection} onSection={setLearningSection} roleDialog={learningRoleDialog} onCloseRole={() => setLearningRoleDialog(false)} />
    <footer className="statusbar">{mode === 'engineer' ? <><span><span className="status-dot" />MicroPython · Web Serial</span><span>{components.length + (board ? 1 : 0)} 个硬件 · main.py<span className="status-separator">/</span>{device.current?.identity?.machine ?? '设备未连接'}</span><span>本机保存 · 设备操作需确认</span></> : <><span>{modeInfo.name}{mode === 'learning' ? ' · 界面预览' : ' · CadQuery'}</span><span>{mode === 'learning' ? '生成功能待开发' : '项目内容已保留'}</span></>}</footer>
    {modeDialog && <ModePicker current={mode} onSelect={selectMode} onClose={() => setModeDialog(false)} />}
    {boardDialog && <BoardPicker boards={hardware} selected={board} onClose={() => setBoardDialog(false)} onSelect={item => { switchBoard(item.componentId); setBoardDialog(false); }} onHelp={() => { setBoardDialog(false); setHelpDialog(true); }} />}
    {loadDialog && <Dialog title="加载项目" onClose={() => setLoadDialog(false)}><p className="muted">选择项目文件夹，恢复主控、模块、过往对话和全部代码版本。</p><button className="primary choose-project-folder" disabled={!!busy} onClick={() => void loadFolder()}><FolderOpen size={19} />选择项目文件夹</button>{error && <p className="settings-error" role="alert">{error}</p>}<h3 className="recent-projects-title">最近本机项目</h3><p className="muted">也可继续打开本机工作记录；旧项目保存时可选择项目文件夹。</p>{projects.length ? projects.map(item => <button className="load-project-row" disabled={!!busy} key={item.id} onClick={async () => { if (await chooseProject(item.id)) setLoadDialog(false); }}><FolderOpen size={22} /><span><strong>{item.name}</strong><small>版本 {item.revision} · {new Date(item.updatedAt).toLocaleString()}</small></span>{item.id === project?.id ? <Check size={18} /> : <ChevronRight size={18} />}</button>) : <p>还没有最近项目，可从文件夹加载。</p>}</Dialog>}
    {helpDialog && <Dialog title="掌问 Mu 工作台使用说明" onClose={() => setHelpDialog(false)}><ol className="help-steps"><li>点击左上「模式」在智能工程师、结构设计师、学习设计师之间切换。结构设计师支持外壳需求、尺寸确认、真实模型与导出；学习设计师可预览学习设置、目标、资料和四类学习材料，生成与保存功能待开发。切换保留当前项目；主控板在智能工程师左侧选择。「检查更新」需安装器部署，确认安装后下次启动生效。</li><li>打开即进入一个未命名项目。选择主控板，添加模块并编写代码；点击「新建」或首次「保存」，选择本地项目文件夹。点击「加载→选择项目文件夹」恢复代码、对话和历史版本。</li><li>左侧用图片、名称和选项列表显示已加入的输入/输出模块，点击「添加模块」选择；任意主控均可跨品牌选择，通过品牌及传感器/执行器类型筛选。硬件栏可向左收起，点击窄栏图标恢复；收起仅增加对话宽度，代码栏保持不变。</li><li>检查代码后点击「上传」：自动连接、保存、备份并回读校验，无需再次确认。运行仍单独点击。模块菜单「编辑案例」可按当前主控保存接线与程序。</li><li>点击「运行」提交设备命令，通过 REPL/串口输出与实物观察判断；运行时同一按钮变为「停止」。</li><li>编辑器顶部的版本下拉框可查看保存版本与 AI 生成版本；AI 代码在右侧以候选预览，保存后成为新的当前版本；有手工修改时保留原稿。切换主控会更新对话，之前主控的记录可展开查看。「文件」可载入/导出代码或浏览设备文件；代码栏可缩放、全屏，Esc 退出全屏。</li><li>「固件刷入」按当前主控打开。先断开编程串口，选择厂商完整 .bin，识别芯片、备份覆盖范围并下载，确认后写入和回读校验。固件未内置。</li></ol><p className="muted">启用 AI：点击「API 设置」，填写 API 基础地址、模型名称和 Key，可使用 DeepSeek 或其他兼容 OpenAI Chat Completions 的服务；本机服务可免 Key。发送时当前代码与所选硬件资料会提交给所配置的服务，代码生成后在右侧预览，保存后才成为当前程序。可先点击「测试连接」。Web Serial 需要桌面 Chrome/Edge；main.py 文件上传最多 64 KiB。</p></Dialog>}
    {firmwareDialog && boardInfo && <FirmwareDialog board={boardInfo} onClose={() => setFirmwareDialog(false)} onBusy={setFlashing} download={download} />}
    {aiSettingsDialog && <AiSettingsDialog settings={{ aiConfigured, aiModel, aiBaseUrl }} initialMode={mode} onClose={() => setAiSettingsDialog(false)} onSaved={result => { if (!result.mode || result.mode === 'engineer') { setAiConfigured(result.aiConfigured); setAiModel(result.aiModel); setAiBaseUrl(result.aiBaseUrl ?? 'https://api.deepseek.com'); } setAiSettingsDialog(false); setNotice(result.aiConfigured ? '所选模式的 API 已保存，立即生效。' : '所选模式的 API Key 已清除。'); }} />}
    {newDialog && !boardDialog && !helpDialog && <Dialog title={creationMode === 'new' ? '新建项目' : '保存项目'} onClose={() => { if (!busy) { setNewDialog(false); setUploadAfterSave(false); } }}><form onSubmit={event => { event.preventDefault(); void action('保存项目文件夹', finishFolderProject); }}><label className="field">项目名称<input autoFocus value={newName} maxLength={80} onChange={event => setNewName(event.target.value)} required disabled={busy === '保存项目文件夹'} /></label><div className="field">项目文件夹<button type="button" className="choose-project-folder" disabled={!!busy} onClick={() => void selectNewFolder()}><FolderOpen size={19} />{newFolder ? '重新选择文件夹' : '选择本地文件夹'}</button><span className="selected-project-folder" aria-label="已选项目文件夹">{newFolder?.name ?? '尚未选择'}</span></div><p className="muted">{creationMode === 'new' ? '在所选文件夹创建空白项目，主控板可在主界面选择。取消保留当前项目。' : '保存当前代码、主控、模块，以及已有对话和代码版本。'} 文件夹包含 main.py 和 zhangwen.project.json，可在其他电脑加载。</p>{error && <p className="settings-error" role="alert">{error}</p>}<button className="primary" disabled={!newName.trim() || !newFolder || !!busy}>{creationMode === 'new' ? '创建项目' : '保存项目'}</button></form></Dialog>}
    {sensorPicker && <Dialog className="sensor-picker-dialog" title="添加模块" onClose={() => setSensorPicker(false)} headerActions={<>
      <div className="catalog-search picker-search"><Search size={17} aria-hidden="true" /><input data-dialog-autofocus aria-label="搜索硬件" placeholder="搜索名称、型号或功能…" value={search} onChange={event => setSearch(event.target.value)} /></div>
      <ModuleFilters items={boardSensors} brand={moduleBrandFilter} direction={moduleFilter} type={moduleTypeFilter} onBrand={setModuleBrandFilter} onType={(direction, type) => { setModuleFilter(direction); setModuleTypeFilter(type); }} onClear={clearModuleFilters} />
    </>}>
      <div className="sensor-picker-context"><strong>多品牌模块库</strong><span>当前主控：{boardInfo?.displayName}</span></div>
      <p className="catalog-result-count" aria-live="polite">找到 {available.length} 个模块 · 可跨品牌选择，接线与驱动需单独核对</p>
      <div className="sensor-picker-list module-grid">{available.map(item => { const added = components.includes(item.componentId); return <ModuleCard key={item.componentId} item={item} added={added} checked={added || pendingSensors.includes(item.componentId)} disabled={added || !!busy || aiBusy || deviceBusy || (!pendingSensors.includes(item.componentId) && components.length + pendingSensors.length >= 32)} onToggle={checked => setPendingSensors(value => checked ? [...new Set([...value, item.componentId])] : value.filter(id => id !== item.componentId))} onDetail={() => openDetail(item, true)} />; })}{!available.length && <p className="catalog-empty muted">没有匹配的模块，试试其他品牌、类型或关键词。</p>}</div>
      <div className="sensor-picker-actions"><span>{pendingSensors.length ? `已选择 ${pendingSensors.length} 个` : '选择项目需要的模块'}{components.length + pendingSensors.length >= 32 && ' · 已达32项上限'}</span><button onClick={() => setSensorPicker(false)}>取消</button><button className="primary" aria-label="加入所选模块" disabled={!pendingSensors.length || !!busy || aiBusy || deviceBusy} onClick={() => { followConversation.current = false; setComponents(value => [...new Set([...value, ...pendingSensors])]); setCheck(null); setCandidate(null); setCodePreview(null); setSensorPicker(false); setMobileTab('ai'); setGuideReveal(value => value + 1); }}>{pendingSensors.length ? `加入 ${pendingSensors.length} 个模块` : '加入模块'}</button></div>
    </Dialog>}
    {detail && <HardwareDetails detail={detail} board={boardInfo} boards={hardware.filter(item => item.category === 'MCU')} editExample={editExample} onSaved={value => { setDetail(value); setHardware(items => items.map(item => item.skillName === value.skillName ? value : item)); }} onClose={() => { setDetail(null); if (returnToPicker) setSensorPicker(true); setReturnToPicker(false); }} />}
    {moduleSample && <Dialog title={`载入模块：${moduleSample.item.displayName}`} onClose={() => setModuleSample(null)}>{moduleSample.scope && <p className="module-guide-summary">{moduleSample.scope}</p>}<p className="muted">示例来自此硬件资料包。确认后替换当前 main.py 草稿；请按实际接线修改端口并检查，保存和上传仍需单独操作。</p><pre className="candidate-code">{moduleSample.code}</pre><button className="primary" onClick={() => { if (code !== moduleSample.base && !window.confirm('预览后代码已改变，仍用此示例替换当前草稿吗？')) return; setCode(moduleSample.code); setCodePreview(null); setSelectedVersion(null); setCheck(null); setModuleSample(null); setMobileTab('code'); setNotice('已载入当前主控的模块示例，尚未保存或上传。请核对固件、端口和接线。'); }}>替换当前代码</button></Dialog>}
    {filesDialog && <DeviceFilesDialog device={device.current} connected={connected} code={visibleCode} versions={fileVersions} disabled={!!busy} onClose={() => setFilesDialog(false)} onDownload={download} onHistory={() => { setFilesDialog(false); setVersions(fileVersions); }} folder={folder} board={boardInfo} componentIds={components} programReceipt={project && board === project.boardId && !dirty ? receipt ?? null : null} programRun={runSubmission} onChooseFolder={() => { setFilesDialog(false); setUploadAfterSave(false); openSave(); }} onLoad={(value, sourceBoard) => { const differentBoard = sourceBoard && sourceBoard.id !== board; if ((differentBoard || (code !== value && code.length)) && !window.confirm(`${differentBoard ? `此程序用于 ${sourceBoard.name}，当前主控不会切换，请核对代码与接线。` : ''}用此文件替换编辑器草稿？设备文件不会改变。`)) return; setCode(value); setCodePreview(null); setSelectedVersion(null); setCheck(null); setFilesDialog(false); setNotice('文件已载入编辑器，尚未保存或上传。'); setMobileTab('code'); }} />}
    {versions && <Dialog title="保存的代码版本" onClose={() => setVersions(null)}><p className="muted">选择一个版本放入编辑器，再保存会创建新版本。历史记录不会被覆盖。</p><button onClick={() => void action("重新载入", async () => { if (dirty && !window.confirm("重新载入会放弃本地草稿，请先导出需要保留的代码。继续吗？")) return; if (!project) return; const saved = await api<Project>("/projects/" + project.id); try { localStorage.removeItem("mu-draft-" + project.id); } catch { /* unavailable */ } applyProject(saved, false); setVersions(null); })}>重新载入当前已保存项目</button>{versions.map(version => <article className="version-row" key={version.revision}><div><strong>版本 {version.revision}</strong><small>{new Date(version.createdAt).toLocaleString()}</small></div><button onClick={() => { selectCodeVersion(version.revision); setVersions(null); }}>载入代码</button><button onClick={() => download(`main-v${version.revision}.py`, version.code)}><Download size={17} />导出</button></article>)}</Dialog>}
  </div>;
}
