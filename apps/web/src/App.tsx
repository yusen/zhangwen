import './classroom.css';
import { WorkbenchHelp } from './WorkbenchHelp';
import { StartScreen } from './StartScreen';
import { ProjectFolderPanel } from './ProjectFolderPanel';
import { readStructureDraft } from './structureDraft';
import { useCallback, useEffect, useRef, useState } from 'react';
import palmMark from './assets/palm-mark.png';
import { ArrowUp, BookOpen, Check, CheckCheck, ChevronRight, MoreHorizontal, Upload, Undo2, History, CircuitBoard, Download, FileCode2, Files, FolderOpen, HelpCircle, LoaderCircle, Plus, Save, Search, Sparkles, Square, Terminal, Unplug, Usb, Wifi, RefreshCw, Send, X, Play, ZoomIn, ZoomOut, AlignLeft, Moon, Sun, Settings, PanelLeftClose, PanelLeftOpen, Maximize, Minimize, Cpu, Layers3, Box, ScanLine, PanelRightOpen } from 'lucide-react';
import type { AiSettings, ChatMessage, CheckResult, CodeRepair, CreateProject, HardwareDetail, HardwareSummary, Project, ProjectSnapshot, ProjectSummary, ProgramRunSubmission, UploadManifest, Version, WorkspaceMode } from '../../../packages/contracts/src/platform';
import { DEFAULT_AI_MODEL } from '../../../packages/contracts/src/platform';
import { api, ApiError, bootstrap, chat } from './api';
import { MicroPythonDevice, serialApi } from './serial';
import { latestBackup, persistBackup } from './backups';
import { Editor, type EditorHandle } from './Editor';
import { Dialog } from './Dialog';
import { AiSettingsDialog } from './AiSettingsDialog';
import { ToolbarButton } from './ToolbarButton';
import { ActionMenu } from './ActionMenu';
import { FeedbackToast } from './FeedbackToast';
import { canSaveProject, projectContent, readProjectDraft, sameProjectContent, type ProjectContent } from './projectDraft';
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
import { IntegrationProgress } from './IntegrationProgress';
import { integrationScope, integrationSession } from './integrationSession';
import { BoardArtwork } from './BoardArtwork';
import { ModePicker, workspaceModes } from './WorkspaceModes';
import { LearningWorkflow } from './LearningWorkflow';
import { SharedProjectDialog } from './SharedProjectDialog';
import { RequirementSync } from './RequirementSync';
import { useChatCoding, ChatCodingConnection, ChatCodingConversation, ChatCodingTask } from './ChatCodingWorkspace';
import { learningSections, type LearningSection } from './LearningSections';
import { StructureWorkspace } from './StructureWorkspace';
import { UpdateCenter } from './UpdateCenter';
import { FirmwareDialog } from './FirmwareDialog';
import { ProjectReferences, ReferenceSources } from './ProjectReferences';
import { PersonalModuleDialog } from './PersonalModuleDialog';
import type { ReferenceCitation } from '../../../packages/contracts/src/platform';
import { ensureFolderPermission, pickProjectDirectory, pickerCancelled, prepareNewDirectory, readProjectDirectory, recallFolder, rememberFolder, writeProjectDirectory, type FolderBinding, type ProjectDirectory } from './projectFolders';
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);
function download(name: string, value: string | Uint8Array) {
    const data = typeof value === 'string' ? value : new Uint8Array(value).buffer;
    const url = URL.createObjectURL(new Blob([data], { type: 'application/octet-stream' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
}
function stored(key: string): string | null { try {
    return localStorage.getItem(key);
}
catch {
    return null;
} }
function store(key: string, value: string) { try {
    localStorage.setItem(key, value);
}
catch { /* a draft failure is reported separately on edits */ } }
export default function App() {
    const [mode, setMode] = useState<WorkspaceMode>(() => { const value = stored('zhangwen-workspace-mode'); return value === 'structure' || value === 'learning' ? value : 'engineer'; });
    const [structureBusy, setStructureBusy] = useState(false);
    const [chatCodingBusy, setChatCodingBusy] = useState(false);
    const structureBusyRef = useRef(structureBusy);
    structureBusyRef.current = structureBusy;
    const [modeDialog, setModeDialog] = useState(false);
    const [structureDesignType, setStructureDesignType] = useState<'model' | 'laser'>('model');
    const [structureDrafts, setStructureDrafts] = useState({ model: '', laser: '' });
    const [structureDirty, setStructureDirty] = useState({ model: false, laser: false });
    const structureUnsaved = structureDirty.model || structureDirty.laser;
    const updateStructureDirty = useCallback((value: boolean) => setStructureDirty(previous => previous[structureDesignType] === value ? previous : { ...previous, [structureDesignType]: value }), [structureDesignType]);
    const structureSaveRef = useRef<(() => void) | null>(null);
    const [learningSection, setLearningSection] = useState<LearningSection>('guidance');
    const [learningBusy, setLearningBusy] = useState(false);
    const [learningDirty, setLearningDirty] = useState(false);
    const learningSaveRef = useRef<(() => Promise<void>) | null>(null);
    const modeInfo = workspaceModes.find(item => item.id === mode)!;
    const selectMode = (value: WorkspaceMode) => { if (value !== mode && !confirmDeviceDiscard())
        return false; setMode(value); store('zhangwen-workspace-mode', value); setCodeFullscreen(false); setModeDialog(false); return true; };
    const [hardware, setHardware] = useState<HardwareSummary[]>([]);
    const [projects, setProjects] = useState<ProjectSummary[]>([]);
    const [sharedProjectOpen, setSharedProjectOpen] = useState(false);
    const [project, setProject] = useState<Project | null>(null);
    // This is a session entry decision, not a persisted project preference.
    // A null project can still be an active workbench when changing programming modes.
    const [workspaceOpen, setWorkspaceOpen] = useState(false);
    useEffect(() => {
        if (!workspaceOpen)
            return;
        let value = { model: '', laser: '' };
        try {
            const local = JSON.parse(stored('zhangwen-structure-input-' + (project?.id ?? 'new')) ?? 'null');
            if (local && typeof local.model === 'string' && typeof local.laser === 'string')
                value = local;
        }
        catch { /* retain the empty input */ }
        setStructureDrafts(value);
        setStructureDirty({ model: !!readStructureDraft(project?.id, 'model'), laser: !!readStructureDraft(project?.id, 'laser') });
    }, [project?.id, workspaceOpen]);
    const updateStructureInput = (value: string) => setStructureDrafts(previous => { const next = { ...previous, [structureDesignType]: value }; store('zhangwen-structure-input-' + (project?.id ?? 'new'), JSON.stringify(next)); return next; });
    const [code, setCode] = useState('');
    const [name, setName] = useState('未命名项目');
    const [draftRevision, setDraftRevision] = useState<number | null>(null);
    const [draftBase, setDraftBase] = useState<ProjectContent | null>(null);
    const [projectConflict, setProjectConflict] = useState<Project | null>(null);
    const [board, setBoard] = useState('');
    const [components, setComponents] = useState<string[]>([]);
    const [search, setSearch] = useState('');
    const [moduleFilter, setModuleFilter] = useState<ModuleDirection | 'all'>('all');
    const [moduleBrandFilter, setModuleBrandFilter] = useState('all');
    const [moduleTypeFilter, setModuleTypeFilter] = useState('');
    const [detail, setDetail] = useState<HardwareDetail | null>(null);
    const [moduleSample, setModuleSample] = useState<{
        item: HardwareSummary;
        code: string;
        base: string;
        language: 'lua' | 'python';
        boardId: string;
        projectId?: string;
        scope?: string;
    } | null>(null);
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
    const [requirementSync, setRequirementSync] = useState(false);
    const [reviewChange, setReviewChange] = useState<{
        projectId: string;
        id: string;
    } | null>(null);
    const [folder, setFolder] = useState<FolderBinding | null>(null);
    const folderRef = useRef<FolderBinding | null>(null);
    const folderQueue = useRef<Promise<void>>(Promise.resolve());
    const [folderStatus, setFolderStatus] = useState('');
    const [folderPanel, setFolderPanel] = useState(true);
    useEffect(() => {
        const narrow = window.matchMedia('(max-width:760px)');
        const adapt = () => { if (narrow.matches)
            setFolderPanel(false); };
        adapt();
        narrow.addEventListener('change', adapt);
        return () => narrow.removeEventListener('change', adapt);
    }, []);
    const folderToggle = useRef<HTMLButtonElement>(null);
    const [folderError, setFolderError] = useState('');
    const folderPending = useRef(0);
    const folderErrorRef = useRef(folderError);
    folderErrorRef.current = folderError;
    const [filesDialog, setFilesDialog] = useState<'programs' | 'board' | null>(null);
    const importInput = useRef<HTMLInputElement>(null);
    const [saveIncludesPreview, setSaveIncludesPreview] = useState(false);
    const [checkExpanded, setCheckExpanded] = useState(false);
    const [fileVersions, setFileVersions] = useState<Version[] | null>(null);
    const [uploadAfterSave, setUploadAfterSave] = useState(false);
    const [editExample, setEditExample] = useState(false);
    const [detailTab, setDetailTab] = useState<'use' | 'mechanical'>('use');
    const [check, setCheck] = useState<CheckResult | null>(null);
    const [aiConfigured, setAiConfigured] = useState(false);
    const [aiModel, setAiModel] = useState<string>(DEFAULT_AI_MODEL);
    const [aiBaseUrl, setAiBaseUrl] = useState('https://api.deepseek.com');
    const [aiSettingsDialog, setAiSettingsDialog] = useState(false);
    const [message, setMessage] = useState('');
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [candidate, setCandidate] = useState<{
        code: string;
        revision?: number;
        boardId?: string;
        source?: 'repair' | 'saved' | 'ai';
    } | null>(null);
    const [codePreview, setCodePreview] = useState<{
        code: string;
        revision?: number;
        boardId?: string;
        source?: 'repair' | 'pin-repair' | 'saved' | 'ai';
    } | null>(null);
    const visibleCode = codePreview?.code ?? code;
    const [error, setError] = useState('');
    const [notice, setNoticeText] = useState('');
    const [noticeSequence, setNoticeSequence] = useState(0);
    const setNotice = (value: string) => { setNoticeText(value); setNoticeSequence(count => count + 1); };
    const [loading, setLoading] = useState(true);
    const [initialized, setInitialized] = useState(false);
    const [bootstrapAttempt, setBootstrapAttempt] = useState(0);
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
    const [integrationExitScope, setIntegrationExitScope] = useState<string | null>(() => stored('zhangwen-integration-exit-scope'));
    const [guideReveal, setGuideReveal] = useState(0);
    const hardwareGuide = useRef<HTMLElement>(null);
    const chatInput = useRef<HTMLTextAreaElement>(null);
    const conversationPane = useRef<HTMLDivElement>(null);
    const followConversation = useRef(false);
    useEffect(() => {
        if (!followConversation.current)
            return;
        const frame = requestAnimationFrame(() => {
            const pane = conversationPane.current;
            if (pane && followConversation.current)
                pane.scrollTop = pane.scrollHeight;
        });
        return () => cancelAnimationFrame(frame);
    }, [pendingPrompt, streamedReply, messages]);
    useEffect(() => {
        if (!guideReveal)
            return;
        const frame = requestAnimationFrame(() => {
            hardwareGuide.current?.focus({ preventScroll: true });
            hardwareGuide.current?.scrollIntoView({ block: 'nearest' });
        });
        return () => cancelAnimationFrame(frame);
    }, [guideReveal]);
    useEffect(() => {
        if (!aiBusy)
            return;
        const started = Date.now();
        setAiElapsed(0);
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
    const [referencesDialog, setReferencesDialog] = useState(false);
    const [personalModule, setPersonalModule] = useState<string | null>(null);
    const [onlyPersonal, setOnlyPersonal] = useState(false);
    const [submittedSources, setSubmittedSources] = useState<{
        references: ReferenceCitation[];
        notice: string;
    } | null>(null);
    const [terminalOpen, setTerminalOpen] = useState(false);
    const serialLog = useRef<HTMLPreElement>(null);
    useEffect(() => {
        if (!terminalOpen || mode !== 'engineer')
            return;
        // Follow streamed output after layout, without scrolling the workbench.
        const frame = requestAnimationFrame(() => {
            const output = serialLog.current;
            if (output)
                output.scrollTop = output.scrollHeight;
        });
        return () => cancelAnimationFrame(frame);
    }, [logs, terminalOpen, mode]);
    const [zoom, setZoom] = useState(100);
    const [theme, setTheme] = useState<'light' | 'dark'>(() => stored('zhangwen-theme') === 'dark' ? 'dark' : 'light');
    const [hardwareCollapsed, setHardwareCollapsed] = useState(() => stored('zhangwen-hardware-collapsed') === 'true');
    const [codeFullscreen, setCodeFullscreen] = useState(false);
    const [firmwareDialog, setFirmwareDialog] = useState(false);
    const [flashing, setFlashing] = useState(false);
    const flashingRef = useRef(flashing);
    flashingRef.current = flashing;
    useEffect(() => { store('zhangwen-hardware-collapsed', String(hardwareCollapsed)); }, [hardwareCollapsed]);
    useEffect(() => {
        if (!codeFullscreen)
            return;
        const outside = Array.from(document.querySelectorAll<HTMLElement>('.mobile-tabs, .hardware-panel, .hardware-restore, .ai-panel')).map(node => ({ node, inert: node.inert }));
        outside.forEach(({ node }) => { node.inert = true; });
        const escape = (event: KeyboardEvent) => { if (event.key === 'Escape' && !event.defaultPrevented && !document.querySelector('dialog[open]'))
            setCodeFullscreen(false); };
        window.addEventListener('keydown', escape);
        return () => { window.removeEventListener('keydown', escape); outside.forEach(({ node, inert }) => { node.inert = inert; }); };
    }, [codeFullscreen]);
    const editor = useRef<EditorHandle>(null);
    useEffect(() => { document.documentElement.dataset.theme = theme; store('zhangwen-theme', theme); }, [theme]);
    const device = useRef<MicroPythonDevice | null>(null);
    const [runSubmission, setRunSubmission] = useState<ProgramRunSubmission | null>(null);
    const releasePort = useRef<(() => void) | null>(null);
    const manualDirty = project ? (code !== project.code || name !== project.name || board !== project.boardId || JSON.stringify(components) !== JSON.stringify(project.componentIds)) : code.length > 0 || components.length > 0;
    const hardwareDirty = !!project?.hardwareRevisions && [board, ...components].filter(Boolean)
        .some(id => hardware.find(item => item.componentId === id)?.revision !== project.hardwareRevisions?.[id]);
    const hardwareSelectionDirty = !!project && (board !== project.boardId || JSON.stringify(components) !== JSON.stringify(project.componentIds) || hardwareDirty);
    const dirty = manualDirty || hardwareDirty || (codePreview !== null && codePreview.code !== project?.code);
    // Choosing hardware must not hide the first AI program; protect unsaved code itself.
    const manualCodeDirty = project ? code !== project.code : code.length > 0;
    const manualCodeDirtyRef = useRef(manualCodeDirty);
    manualCodeDirtyRef.current = manualCodeDirty;
    const deviceState = device.current?.state ?? 'disconnected';
    const connected = deviceState === 'connected';
    const running = deviceState === 'running';
    const deviceBusy = deviceState === 'busy' || deviceState === 'connecting';
    const boardInfo = hardware.find(item => item.componentId === board);
    const isChatCoding = boardInfo?.programmingMode === 'chat-coding';
    const currentCode = useRef(visibleCode);
    currentCode.current = visibleCode;
    const currentHardware = useRef({ board, components });
    currentHardware.current = { board, components };
    const currentProject = useRef(project?.id);
    currentProject.current = project?.id;
    const restoredPreviewProject = useRef<string | null>(null);
    const dirtyRef = useRef(dirty);
    dirtyRef.current = dirty;
    const busyRef = useRef(busy);
    busyRef.current = busy;
    const addLog = useCallback((text: string) => { setLogs(value => (value + text).slice(-60000)); }, []);
    const action = async (label: string, task: () => Promise<unknown>) => {
        setBusy(label);
        setError('');
        setNotice('');
        try {
            await task();
        }
        catch (err) {
            setError(errorText(err));
        }
        finally {
            setBusy('');
        }
    };
    const openAiSettings = () => void action('读取 AI 设置', async () => { const settings = await api<AiSettings>('/settings/ai'); setAiConfigured(settings.aiConfigured); setAiModel(settings.aiModel); setAiBaseUrl(settings.aiBaseUrl ?? 'https://api.deepseek.com'); setAiSettingsDialog(true); });
    const bindFolder = (value: FolderBinding | null, status = '') => { folderRef.current = value; folderErrorRef.current = ''; setFolder(value); setFolderStatus(status); setFolderError(''); };
    const syncFolder = async (id: string) => {
        const binding = folderRef.current;
        if (!binding || binding.projectId !== id)
            return;
        const run = async () => {
            try {
                if (currentProject.current === id)
                    setFolderStatus('正在同步');
                const snapshot = await api<ProjectSnapshot>(`/projects/${id}/snapshot`);
                await writeProjectDirectory(binding, snapshot);
                if (currentProject.current === id) {
                    folderErrorRef.current = '';
                    setFolderStatus('已同步');
                    setFolderError('');
                }
            }
            catch (err) {
                // A failed disk checkpoint must not turn a completed AI reply into a failure.
                await rememberFolder(binding).catch(() => { });
                if (currentProject.current === id) {
                    const message = '本机记录已保留，项目文件夹未完成同步：' + errorText(err);
                    folderErrorRef.current = message;
                    setFolderStatus('未同步');
                    setFolderError(message);
                }
            }
        };
        folderPending.current++;
        const pending = folderQueue.current.then(run, run);
        folderQueue.current = pending;
        try {
            await pending;
        }
        finally {
            folderPending.current--;
        }
    };
    async function saveProjectContent(request: ProjectContent): Promise<Project> {
        if (!project)
            throw new Error('当前项目未创建。');
        const id = project.id, expected = draftRevision ?? project.revision;
        const base = expected === project.revision ? projectContent(project) : draftBase;
        const conflict = (latest: Project) => {
            if (currentProject.current === id) {
                setNewDialog(false);
                setProjectConflict(latest);
            }
            return new Error('项目内容已更新，请在「同步项目」中处理。当前需求和代码已保留。');
        };
        const latest = await api<Project>('/projects/' + id);
        if (currentProject.current !== id)
            throw new Error('项目已切换，未保存。');
        if (!canSaveProject(latest, request, expected, base))
            throw conflict(latest);
        const hardwareMatches = [request.boardId, ...request.componentIds].filter(Boolean)
            .every(id => latest.hardwareRevisions?.[id] === hardware.find(item => item.componentId === id)?.revision);
        if (sameProjectContent(latest, request) && hardwareMatches)
            return latest;
        try {
            return await api<Project>('/projects/' + id, 'PUT', { ...request, expectedRevision: latest.revision });
        }
        catch (err) {
            if (err instanceof ApiError && err.status === 409) {
                const changed = await api<Project>('/projects/' + id);
                if (changed.revision !== latest.revision)
                    throw conflict(changed);
            }
            throw err;
        }
    }
    async function prepareLuaProject(): Promise<Project> {
        if (!isChatCoding)
            throw new Error('请先选择 Mosaico 主控。');
        if (currentHardware.current.board !== board || JSON.stringify(currentHardware.current.components) !== JSON.stringify(components))
            throw new Error('主控或模块选择已改变，请重新生成。');
        const request = { name: name === '未命名项目' ? 'Mosaico 项目' : name, boardId: board,
            code: project?.programmingMode === 'chat-coding' ? code : '', componentIds: components };
        // Like a first MicroPython conversation, record the selected hardware in the
        // existing local project store. Lua acceptance and device actions stay separate.
        return project && (!project.boardId || project.programmingMode === 'chat-coding')
            ? saveProjectContent(request)
            : api<Project>('/projects', 'POST', request);
    }
    function adoptLuaProject(value: Project) {
        persistDraftNow();
        try {
            localStorage.removeItem('zhangwen-draft-' + value.id);
        }
        catch { /* server record is retained */ }
        applyProject(value, false);
        void refreshProjects().catch(err => setError(errorText(err)));
    }
    const nativeChat = useChatCoding({ active: workspaceOpen && !!isChatCoding, project, task: code, unsaved: dirty, disabled: !workspaceOpen || loading || !!busy || aiBusy || deviceBusy || structureBusy, onSaved: syncFolder, onBusy: setChatCodingBusy,
        prepareProject: prepareLuaProject, onProjectPrepared: adoptLuaProject });
    const workspaceDirty = workspaceOpen && (learningDirty || dirty || nativeChat.lua.hasUnsaved || structureUnsaved || !!structureDrafts.model.trim() || !!structureDrafts.laser.trim());
    dirtyRef.current = workspaceDirty;
    const confirmDeviceDiscard = () => { if (!nativeChat.device.unsaved.current)
        return true; if (!window.confirm('设备工具中有未保存修改，放弃并继续？'))
        return false; nativeChat.device.unsaved.current = false; nativeChat.device.setSection('records'); return true; };
    useEffect(() => {
        let active = true;
        setCodeVersions([]);
        if (project)
            void api<{
                versions: Version[];
            }>(`/projects/${project.id}/versions`).then(result => {
                if (!active)
                    return;
                setCodeVersions(result.versions);
                const firstLoad = restoredPreviewProject.current !== project.id;
                restoredPreviewProject.current = project.id;
                const recovered = result.versions.find(item => item.source === 'ai' && item.boardId === currentHardware.current.board && item.code.trim());
                if (firstLoad && recovered && !project.code.trim() && !currentCode.current.trim() && !manualCodeDirtyRef.current) {
                    setCandidate(recovered);
                    setCodePreview(recovered);
                    setCheck(null);
                }
            }).catch(err => { if (active)
                setError('读取代码历史失败：' + errorText(err)); });
        return () => { active = false; };
    }, [project?.id, project?.revision, historyRefresh]);
    const applyProject = (value: Project, restoreDraft = true) => {
        setWorkspaceOpen(true);
        if (value.programmingMode === 'chat-coding')
            setCodeFullscreen(false);
        if (value.id !== currentProject.current) {
            followConversation.current = false;
            bindFolder(null);
            currentProject.current = value.id;
            void recallFolder(value.id).then(binding => { if (currentProject.current === value.id && !folderRef.current)
                bindFolder(binding, binding ? '已关联' : ''); }).catch(err => { if (currentProject.current === value.id)
                setFolderError(errorText(err)); });
        }
        setProject(value);
        setName(value.name);
        setBoard(value.boardId);
        setComponents(value.componentIds);
        setDraftRevision(null);
        setDraftBase(null);
        setProjectConflict(null);
        setSelectedVersion(value.revision);
        setHistoryRefresh(count => count + 1);
        setMessages(value.messages);
        setCandidate(null);
        setCodePreview(null);
        setCheck(null);
        setChatError('');
        store('zhangwen-active-project', value.id);
        const draft = restoreDraft ? readProjectDraft(stored('zhangwen-draft-' + value.id), value) : null;
        if (draft) {
            setCode(draft.code);
            setName(draft.name);
            setBoard(draft.board);
            setComponents(draft.components);
            setDraftRevision(draft.baseRevision);
            setDraftBase(draft.base ?? null);
            if (draft.code !== value.code)
                setSelectedVersion(null);
            setNotice(draft.baseRevision !== value.revision ? '已恢复本地草稿；保存时将核对项目更新，代码会保留。' : '已恢复本地草稿；保存后才成为项目版本。');
        }
        else {
            setCode(value.code);
            if (!restoreDraft)
                try {
                    localStorage.removeItem('zhangwen-draft-' + value.id);
                }
                catch { /* unavailable */ }
        }
    };
    const refreshProjects = async () => setProjects((await api<{
        projects: ProjectSummary[];
    }>('/projects')).projects);
    const openLoad = () => { setLoadDialog(true); void action('读取项目', refreshProjects); };
    const persistDraftNow = () => {
        if (project && dirty)
            store('zhangwen-draft-' + project.id, JSON.stringify({ code, name, board, components, baseRevision: draftRevision ?? project.revision,
                base: draftRevision === null || draftRevision === project.revision ? projectContent(project) : draftBase }));
    };
    const openSave = (includePreview = false) => { if (!project && !confirmDeviceDiscard())
        return; setSaveIncludesPreview(includePreview); setError(''); setCreationMode('save'); setNewFolder(null); setNewName(name === '未命名项目' ? '我的项目' : name); setNewDialog(true); };
    const openNew = () => {
        if (!confirmDeviceDiscard())
            return;
        if (workspaceDirty && !window.confirm('当前项目有未保存更改。确定开始一个新项目吗？建议先保存当前项目。'))
            return;
        setError('');
        setCreationMode('new');
        setNewFolder(null);
        setNewName('我的项目');
        setNewDialog(true);
    };
    useEffect(() => {
        let active = true;
        setLoading(true);
        setError('');
        void (async () => {
            try {
                const session = await bootstrap();
                const [catalog, list] = await Promise.all([api<{
                        skills: HardwareSummary[];
                    }>('/hardware'), api<{
                        projects: ProjectSummary[];
                    }>('/projects')]);
                if (!active)
                    return;
                setAiConfigured(session.aiConfigured);
                setAiModel(session.aiModel ?? DEFAULT_AI_MODEL);
                setHardware(catalog.skills);
                setProjects(list.projects);
                setAiBaseUrl(session.aiBaseUrl ?? 'https://api.deepseek.com');
                setInitialized(true);
            }
            catch (err) {
                if (active)
                    setError(errorText(err));
            }
            finally {
                if (active)
                    setLoading(false);
            }
        })();
        return () => { active = false; };
    }, [bootstrapAttempt]);
    useEffect(() => {
        if (loading || !workspaceOpen)
            return;
        if (!project) {
            try {
                localStorage.setItem('zhangwen-scratch-code', code);
                localStorage.setItem('zhangwen-scratch-hardware', JSON.stringify({ board, components }));
            }
            catch {
                setError('浏览器草稿无法保存，请立即保存到本机服务或导出代码。');
            }
            return;
        }
        if (!dirty)
            return;
        const timer = setTimeout(() => {
            try {
                localStorage.setItem('zhangwen-draft-' + project.id, JSON.stringify({ code, name, board, components, baseRevision: draftRevision ?? project.revision,
                    base: draftRevision === null || draftRevision === project.revision ? projectContent(project) : draftBase }));
            }
            catch {
                setError('浏览器草稿无法保存，请立即保存到本机服务或导出代码。');
            }
        }, 250);
        return () => clearTimeout(timer);
    }, [code, name, board, components, project, dirty, draftRevision, draftBase, loading, workspaceOpen]);
    useEffect(() => {
        const prevent = (event: BeforeUnloadEvent) => {
            if (dirtyRef.current || structureBusyRef.current || folderPending.current || folderErrorRef.current || sendingMessage.current || device.current?.state === 'busy' || flashingRef.current) {
                event.preventDefault();
                event.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', prevent);
        return () => window.removeEventListener('beforeunload', prevent);
    }, []);
    const save = async (includePreview = false) => {
        if (sendingMessage.current && !project) {
            setNotice('正在准备首次对话项目，请稍后保存。');
            return;
        }
        if (!project || !folderRef.current) {
            openSave(includePreview);
            return;
        }
        if (!manualDirty && !hardwareDirty && (!includePreview || !codePreview || codePreview.code === project.code)) {
            await ensureFolderPermission(folderRef.current, true);
            await syncFolder(project.id);
            setNotice(folderErrorRef.current ? '本机记录已保留，文件夹未同步。可重试或另存。' : '项目文件夹已同步。');
            return project;
        }
        if (includePreview && codePreview && manualDirty && codePreview.code !== code && !window.confirm('保存此生成稿会替换当前手工草稿。先返回原稿保存，或确认继续？'))
            return;
        await ensureFolderPermission(folderRef.current, true);
        const saved = await saveProjectContent({ code: includePreview ? visibleCode : code, name, boardId: board, componentIds: components });
        try {
            localStorage.removeItem('zhangwen-draft-' + project.id);
        }
        catch { /* unavailable */ }
        const pending = !includePreview ? codePreview : null, pendingCandidate = candidate;
        applyProject(saved, false);
        if (pending) {
            setCodePreview(pending);
            setCandidate(pendingCandidate);
        }
        await refreshProjects();
        await syncFolder(saved.id);
        setNotice(folderErrorRef.current ? `本机版本 ${saved.revision} 已保留，文件夹未同步。` : `已保存到项目文件夹 · 版本 ${saved.revision}`);
        return saved;
    };
    const saveHardwareSelection = async (): Promise<boolean> => {
        if (!project) {
            openNew();
            return false;
        }
        let completed = false;
        await action('保存器件选择', async () => {
            // Save shared hardware without accepting or replacing an engineering draft.
            const saved = await saveProjectContent({ ...projectContent(project), boardId: board, componentIds: components });
            setProject(saved);
            setDraftRevision(null);
            setDraftBase(null);
            if (code !== saved.code || name !== saved.name)
                store('zhangwen-draft-' + saved.id, JSON.stringify({ code, name, board, components, baseRevision: saved.revision, base: projectContent(saved) }));
            else
                try {
                    localStorage.removeItem('zhangwen-draft-' + saved.id);
                }
                catch { /* server record is retained */ }
            if (!manualCodeDirty && !codePreview)
                setSelectedVersion(saved.revision);
            setHistoryRefresh(value => value + 1);
            completed = true;
            await refreshProjects();
            await syncFolder(saved.id);
            setNotice(folderErrorRef.current ? '器件选择已保存，项目文件夹待同步。' : '器件选择已保存，三师共用此配置。');
        });
        return completed;
    };
    const saveWorkspace = async () => {
        if (mode === 'learning') {
            if (!project) {
                openNew();
                return;
            }
            if (hardwareSelectionDirty) {
                await saveHardwareSelection();
                return;
            }
            await learningSaveRef.current?.();
            return;
        }
        if (mode === 'structure') {
            if (!project) {
                openSave();
                return;
            }
            await action('保存结构草稿', async () => { structureSaveRef.current?.(); await syncFolder(project.id); setNotice('结构草稿已保留于本浏览器；未应用参数不会改变模型版本。可导出参数草稿。'); });
            return;
        }
        ;
        if (isChatCoding && nativeChat.source === 'local') {
            if (!project) {
                await action('保存项目', () => save());
                return;
            }
            if (manualDirty || hardwareDirty) {
                let ready = false;
                await action('保存项目设置', async () => { adoptLuaProject(await prepareLuaProject()); ready = true; });
                if (!ready)
                    return;
            }
            if (nativeChat.lua.hasUnsaved && !nativeChat.lua.saved)
                await nativeChat.lua.requestSave();
            else
                await action('同步已保存代码', async () => { await syncFolder(project.id); setNotice(nativeChat.lua.hasUnsaved ? '当前查看的Lua已保存，手工草稿仍保留。' : 'Lua代码已保存到本机项目。'); });
            return;
        }
        await action('保存项目', () => save());
    };
    const saveRef = useRef(saveWorkspace);
    saveRef.current = saveWorkspace;
    const savingAllowed = useRef(false);
    savingAllowed.current = workspaceOpen && !loading && !learningBusy && !aiBusy && !deviceBusy && !flashing && !chatCodingBusy;
    useEffect(() => {
        const key = (event: KeyboardEvent) => { if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 's') {
            event.preventDefault();
            if (savingAllowed.current && !busyRef.current && !structureBusyRef.current)
                void saveRef.current();
        } };
        window.addEventListener('keydown', key);
        return () => window.removeEventListener('keydown', key);
    }, []);
    const chooseProject = async (id: string) => {
        if (id === project?.id)
            return true;
        if (!confirmDeviceDiscard())
            return false;
        if (workspaceDirty && !window.confirm('当前修改尚未保存。草稿保留在本浏览器；仍要切换项目吗？'))
            return false;
        persistDraftNow();
        let opened = false;
        await action('打开项目', async () => { applyProject(await api<Project>('/projects/' + id)); setGuideScope(value => value + 1); opened = true; });
        return opened;
    };
    const selectNewFolder = async () => {
        const selection = pickProjectDirectory();
        await action('选择项目文件夹', async () => {
            try {
                const handle = await selection;
                await prepareNewDirectory(handle);
                setNewFolder(handle);
                if (!newName.trim() || newName === '我的项目')
                    setNewName(handle.name.slice(0, 80));
            }
            catch (err) {
                if (!pickerCancelled(err))
                    throw err;
            }
        });
    };
    const finishFolderProject = async () => {
        if (!newFolder)
            throw new Error('请先选择本地项目文件夹。');
        if (creationMode === 'save' && saveIncludesPreview && codePreview && manualDirty && codePreview.code !== code && !window.confirm('保存此生成稿会替换当前手工草稿。先返回原稿保存，或确认继续？'))
            return;
        await prepareNewDirectory(newFolder);
        if (creationMode === 'save' && project && folderRef.current)
            await copyProjectPrograms(folderRef.current, newFolder);
        persistDraftNow();
        const request: CreateProject = { name: newName, boardId: creationMode === 'new' ? '' : board, code: creationMode === 'new' ? '' : saveIncludesPreview ? visibleCode : code, componentIds: creationMode === 'new' ? [] : components };
        const value = creationMode === 'save' && project
            ? await saveProjectContent({ ...request, code: request.code ?? '', componentIds: request.componentIds ?? [] })
            : await api<Project>('/projects', 'POST', request);
        const pending = creationMode === 'save' && !saveIncludesPreview ? codePreview : null, pendingCandidate = candidate;
        applyProject(value, false);
        if (pending) {
            setCodePreview(pending);
            setCandidate(pendingCandidate);
        }
        bindFolder({ projectId: value.id, handle: newFolder, checkpointHash: null, mainHash: null }, '未同步');
        setNewDialog(false);
        setGuideScope(count => count + 1);
        setMobileTab('code');
        if (creationMode === 'new')
            setHardwareCollapsed(false);
        try {
            // Starting a new session must not discard a scratch draft from an earlier one.
            if (workspaceOpen) {
                localStorage.removeItem('zhangwen-scratch-code');
                localStorage.removeItem('zhangwen-scratch-hardware');
            }
            localStorage.removeItem('zhangwen-draft-' + value.id);
        }
        catch { /* unavailable */ }
        await refreshProjects();
        await syncFolder(value.id);
        setNotice(creationMode === 'new' ? '项目已创建，可在左侧选择主控板。' : '项目已保存到本机；文件夹同步状态见项目文件夹栏。');
        if (uploadAfterSave) {
            setUploadAfterSave(false);
            if (!folderErrorRef.current)
                await uploadSaved(value);
        }
    };
    const loadFolder = async () => {
        if (!confirmDeviceDiscard())
            return;
        if (workspaceDirty && !window.confirm('当前修改尚未保存，仍要加载另一个项目文件夹吗？本浏览器草稿会保留。'))
            return;
        const selection = pickProjectDirectory();
        await action('加载项目文件夹', async () => {
            try {
                const handle = await selection, loaded = await readProjectDirectory(handle);
                const value = await api<Project>('/projects/import', 'POST', loaded.snapshot);
                persistDraftNow();
                applyProject(value, false);
                const binding = { ...loaded.binding, projectId: value.id };
                bindFolder(binding, '已载入');
                await rememberFolder(binding).catch(err => { setFolderError(errorText(err)); });
                if (loaded.externalCode !== null) {
                    setCode(loaded.externalCode);
                    setSelectedVersion(null);
                    setNotice('文件夹任务或程序与项目备份不同，已作为未保存草稿载入；原对话和版本仍保留，保存后产生新版本。');
                }
                else
                    setNotice('已从项目文件夹恢复代码、过往对话与历史版本。');
                setLoadDialog(false);
                setGuideScope(count => count + 1);
                setMobileTab('ai');
                await refreshProjects();
            }
            catch (err) {
                if (!pickerCancelled(err))
                    throw err;
            }
        });
    };
    const switchBoard = (id: string) => {
        if (id === board)
            return;
        if (!confirmDeviceDiscard())
            return;
        const nextChat = hardware.find(item => item.componentId === id)?.programmingMode === 'chat-coding';
        if (nextChat !== isChatCoding && (board || code.trim())) {
            if (deviceState !== 'disconnected') {
                setError('请先断开当前串口设备，再切换编程方式。');
                return;
            }
            if (!window.confirm('切换编程方式将开始另一份项目草稿，当前项目和草稿保留。需要完整备份时请先保存。继续吗？'))
                return;
            persistDraftNow();
            setCodeFullscreen(false);
            store('zhangwen-programming-draft-' + (isChatCoding ? 'chat-coding' : 'micropython'), JSON.stringify({ code, name, components }));
            let restored = '';
            try {
                const draft = JSON.parse(stored('zhangwen-programming-draft-' + (nextChat ? 'chat-coding' : 'micropython')) ?? 'null');
                if (typeof draft?.code === 'string')
                    restored = draft.code;
            }
            catch { /* retain the separately stored original */ }
            setProject(null);
            currentProject.current = undefined;
            bindFolder(null);
            setCode(restored);
            setName('未命名项目');
            setComponents([]);
            setMessages([]);
            setCodeVersions([]);
            setSelectedVersion(null);
            setDraftRevision(null);
            try {
                localStorage.removeItem('zhangwen-active-project');
            }
            catch { /* original project remains on the service */ }
        }
        setBoard(id);
        setCheck(null);
        setCandidate(null);
        setCodePreview(null);
        setChatError('');
        setGuideScope(count => count + 1);
        setGuideReveal(count => count + 1);
        setMobileTab('ai');
        setNotice(nextChat ? '已选择 Mosaico。生成的 Lua 会自动保存，由你点击通过 WiFi 上传并运行。' : board ? '已切换主控，对话按新主控更新；旧主控对话保留在历史区，当前代码请重新核对。' : '已选择主控，可添加模块或开始对话；保存后记录到项目。');
    };
    const selectCodeVersion = (revision: number) => {
        const version = codeVersions.find(item => item.revision === revision);
        if (!version)
            return;
        if (version.boardId && version.boardId !== board && !window.confirm('此版本来自其他主控。仅将代码载入草稿，当前主控不变；确认继续核对吗？'))
            return;
        if (version.source === 'ai') {
            setCodePreview(version);
            setCheck(null);
            setMobileTab('code');
            return;
        }
        if (dirty && version.code !== code && !window.confirm('用历史版本替换当前未保存代码？当前草稿建议先保存或导出。'))
            return;
        setCode(version.code);
        setCodePreview(null);
        setSelectedVersion(revision);
        setCheck(null);
        setCandidate(null);
        setNotice(revision === project?.revision ? '已载入当前保存版本。' : '历史代码已载入草稿；保存会创建新版本，原历史不会覆盖。');
    };
    const openDetail = (item: HardwareSummary, fromPicker = false, edit = false, mechanical = false) => void action('读取资料', async () => {
        const value = await api<HardwareDetail>('/hardware/' + item.skillName);
        setReturnToPicker(fromPicker);
        if (fromPicker)
            setSensorPicker(false);
        setEditExample(edit);
        setDetailTab(mechanical ? 'mechanical' : 'use');
        setDetail(value);
    });
    const clearModuleFilters = () => { setSearch(''); setModuleFilter('all'); setModuleBrandFilter('all'); setModuleTypeFilter(''); };
    const openSensorPicker = () => { clearModuleFilters(); setPendingSensors([]); setSensorPicker(true); };
    const removeSensor = (id: string) => { setComponents(value => value.filter(item => item !== id)); setCheck(null); setCandidate(null); setCodePreview(null); };
    const loadModuleSample = (item: HardwareSummary) => void action('读取模块示例', async () => {
        const language = isChatCoding ? 'lua' : 'python';
        if (isChatCoding && nativeChat.source !== 'local') {
            setNotice('请先切换到掌问模型 Lua 编程，再载入模块程序。');
            return;
        }
        const value = await api<HardwareDetail>('/hardware/' + item.skillName);
        const samples = value.files.filter(file => file.path.startsWith('examples/'));
        const pythonFile = samples.find(file => file.path.endsWith('.py'));
        const blocks = samples.flatMap(file => [...file.content.matchAll(/```(?:python|micropython|py)\s*\n([\s\S]*?)```/g)].map(match => match[1]));
        const guide = value.moduleGuides?.find(example => example.boardId === board);
        const local = value.localExamples?.find(example => example.boardId === board);
        const sample = local?.code.trim() || (guide ? guideCode(guide, local?.setup) : isChatCoding || value.moduleGuides?.length ? '' : pythonFile?.content || blocks[0]);
        if (!sample?.trim()) {
            setNotice(`此模块资料包尚无当前主控的 ${isChatCoding ? 'Lua' : 'Python'} 示例，请查看完整资料。`);
            return;
        }
        setModuleSample({ item, code: sample.trimEnd() + '\n', base: isChatCoding ? nativeChat.lua.editorCode : code,
            language, boardId: board, projectId: project?.id,
            scope: local?.code.trim() ? '本机保存的当前主控案例；请核对实际接线。' : guide ? guideKind[guide.kind] + '。' + guide.summary : undefined });
    });
    const connectDevice = async () => {
        const serial = serialApi();
        if (!serial || !window.isSecureContext || !navigator.locks) {
            setError('请使用电脑上的 Chrome 或 Edge 打开本机掌问，再连接设备。');
            return;
        }
        setError('');
        setBusy('选择设备并检测固件');
        try {
            // requestPort runs directly in the click gesture before awaiting anything.
            const port = await serial.requestPort();
            await new Promise<void>((resolve, reject) => {
                void navigator.locks.request('zhangwen-web-serial', { ifAvailable: true }, async (lock) => {
                    if (!lock) {
                        reject(new Error('另一个掌问标签正在使用串口，请先在那里断开。'));
                        return;
                    }
                    const held = new Promise<void>(done => { releasePort.current = done; });
                    const next = new MicroPythonDevice(port, addLog, () => redraw(value => value + 1));
                    device.current = next;
                    try {
                        await next.connect();
                        setNotice('MicroPython 固件检测通过，设备已连接。');
                        resolve();
                        await held;
                    }
                    catch (err) {
                        releasePort.current?.();
                        device.current = null;
                        reject(err);
                    }
                }).catch(reject);
            });
        }
        catch (err) {
            if (!(err instanceof DOMException && err.name === 'NotFoundError'))
                setError(errorText(err));
        }
        finally {
            setBusy('');
        }
    };
    const disconnect = () => void action('断开设备', async () => { await device.current?.disconnect(); device.current = null; releasePort.current?.(); releasePort.current = null; redraw(value => value + 1); });
    const runProgram = async (activeDevice = device.current) => {
        if (!activeDevice)
            return;
        await activeDevice.run();
        const uploaded = activeDevice.receipt;
        if (uploaded)
            setRunSubmission({ projectId: uploaded.projectId, revision: uploaded.revision, boardId: board, sha256: uploaded.sha256, submittedAt: new Date().toISOString() });
    };
    const previewScreenRepair = () => void action('预览屏幕修复', async () => {
        const repaired = await api<CodeRepair>('/code/repair-k10-screen', 'POST', { code: visibleCode, boardId: board, componentIds: components });
        setCodePreview({ code: repaired.code, boardId: board, source: 'repair' });
        setCheck(repaired.check);
        setMobileTab('code');
        setNotice(repaired.summary);
    });
    const previewPinRepair = () => void action('预览引脚修复', async () => {
        const repaired = await api<CodeRepair>('/code/repair-mpython-pins', 'POST', { code: visibleCode, boardId: board, componentIds: components });
        setCodePreview({ code: repaired.code, boardId: board, source: 'pin-repair' });
        setCheck(repaired.check);
        setMobileTab('code');
        setNotice(repaired.summary);
    });
    const uploadSaved = async (saved: Project) => {
        if (device.current?.state !== 'connected')
            throw new Error('先连接设备并停止程序。');
        const targetDevice = device.current;
        let plan: UploadManifest;
        try {
            plan = await api<UploadManifest>(`/projects/${saved.id}/upload-manifest`, 'POST', { expectedRevision: saved.revision });
        }
        catch (err) {
            if (err instanceof ApiError && err.check) {
                setCheck(err.check);
                setCheckExpanded(true);
                setMobileTab('code');
            }
            throw err;
        }
        if (currentProject.current !== saved.id || currentCode.current !== saved.code || currentHardware.current.board !== saved.boardId
            || JSON.stringify(currentHardware.current.components) !== JSON.stringify(saved.componentIds))
            throw new Error('准备上传时项目已变更，请再次点击上传。');
        if (device.current !== targetDevice || targetDevice.state !== 'connected')
            throw new Error('设备连接已变更，请重新连接后上传。');
        setProgress(0);
        try {
            await targetDevice.upload(plan, persistBackup, (done, total) => setProgress(total ? Math.round(done / total * 100) : 100));
            try {
                await runProgram(targetDevice);
            }
            catch (err) {
                throw new Error(`main.py 上传回读一致，但自动运行未完成：${errorText(err)}。请核对终端后重试运行。`);
            }
            setNotice('main.py 上传回读一致，运行命令已提交。运行中可点击「停止」；结果请查看终端和实物现象。');
        }
        finally {
            setProgress(null);
        }
    };
    const prepareUpload = async () => {
        if (codePreview) {
            setNotice('请先点击「采用此代码」或「保存此版本」，再上传并运行；当前草稿仍保留。');
            setMobileTab('code');
            return;
        }
        setTerminalOpen(true);
        setMobileTab('code');
        if (!device.current || device.current.state === 'disconnected')
            await connectDevice();
        if (device.current?.state !== 'connected')
            return;
        if (!project || !folderRef.current) {
            setUploadAfterSave(true);
            openSave();
            return;
        }
        await action('上传并运行', async () => {
            const saved = dirty ? await save() : project;
            if (saved && !folderErrorRef.current)
                await uploadSaved(saved);
        });
    };
    const sendRepl = async () => {
        const command = repl;
        if (!command.trim() || busy || deviceBusy)
            return;
        if (!device.current || device.current.state === 'disconnected')
            await connectDevice();
        const target = device.current;
        if (!target || !['connected', 'running'].includes(target.state))
            return;
        await action('发送设备命令', async () => {
            if (target.state === 'running')
                await target.stop();
            await target.repl(command);
            setRepl(value => value === command ? '' : value);
        });
    };
    const currentIntegrationScope = integrationScope(project?.id, board, components);
    const integration = integrationExitScope === currentIntegrationScope ? null : integrationSession(messages, board, components);
    const leaveIntegration = () => { setIntegrationExitScope(currentIntegrationScope); store('zhangwen-integration-exit-scope', currentIntegrationScope); setNotice('已切换到直接做作品，可输入项目想实现的功能。原测试对话保留。'); chatInput.current?.focus(); };
    const sendMessage = async (preset?: string, intent?: 'integration', targetId?: string) => {
        const prompt = preset ?? message;
        if (!prompt.trim() || sendingMessage.current || loading || busy || !board)
            return;
        const base = visibleCode;
        const chatBoard = board;
        const chatComponents = [...components];
        const chatIntent = intent ?? (integration ? 'integration' : undefined);
        const chatTarget = chatIntent === 'integration' ? (targetId ?? integration?.targetId ?? chatComponents[0]) : undefined;
        let id = project?.id;
        sendingMessage.current = true;
        setSubmittedSources(null);
        setAiBusy(true);
        setAiPhase('preparing');
        setStreamedReply('');
        setError('');
        setChatError('');
        try {
            // Refresh the token/config so a server restart or another tab cannot silently disable sending.
            const session = await bootstrap();
            setAiConfigured(session.aiConfigured);
            setAiModel(session.aiModel ?? DEFAULT_AI_MODEL);
            setAiBaseUrl(session.aiBaseUrl ?? 'https://api.deepseek.com');
            if (!session.aiConfigured) {
                setAiSettingsDialog(true);
                setChatError('先打开“AI 设置”配置服务，保存后再发送。输入内容已保留。');
                return;
            }
            followConversation.current = true;
            setPendingPrompt(prompt);
            if (!id) {
                const created = await api<Project>('/projects', 'POST', { name: name === '未命名项目' ? '我的项目' : name, code: base, boardId: chatBoard, componentIds: chatComponents } satisfies CreateProject);
                id = created.id;
                // Adopt the saved snapshot without overwriting edits made while this request was pending.
                setProject(created);
                currentProject.current = id;
                setName(created.name);
                setDraftRevision(null);
                setSelectedVersion(currentCode.current === base ? created.revision : null);
                setMessages(created.messages);
                store('zhangwen-active-project', id);
                setProjects(value => [created, ...value.filter(item => item.id !== id)]);
                setNotice('已为首次对话保存当前项目。');
            }
            const controller = new AbortController();
            aiController.current = controller;
            setAiPhase('waiting');
            setCandidate(null);
            const result = await chat(id, { message: prompt, code: base, boardId: chatBoard, componentIds: chatComponents, ...(chatIntent ? { intent: chatIntent } : {}), ...(chatTarget ? { integrationModuleId: chatTarget } : {}) }, controller.signal, event => {
                if (event.type === 'references')
                    setSubmittedSources({ references: event.references, notice: event.notice });
                if (event.type === 'delta') {
                    setAiPhase('generating');
                    setStreamedReply(value => value + event.content);
                }
            });
            if (currentProject.current === id) {
                setMessages(result.messages);
                if (preset === undefined)
                    setMessage(value => value === prompt ? '' : value);
                const reply = result.messages.filter(item => item.role === 'assistant' && item.status === 'COMPLETED').at(-1);
                const suggestion = reply ? replyCode(reply.content) : null;
                let history = { versions: codeVersions };
                try {
                    history = await api<{
                        versions: Version[];
                    }>(`/projects/${id}/versions`);
                    setCodeVersions(history.versions);
                }
                catch {
                    setNotice('回复已完成，暂时无法读取版本号；代码生成稿仍可预览，请稍后刷新历史。');
                }
                if (suggestion !== null) {
                    const version = history.versions.find(item => item.messageId === reply?.id) ?? history.versions.find(item => item.source === 'ai' && item.code === suggestion && item.boardId === chatBoard);
                    const next = { code: suggestion, revision: version?.revision, boardId: chatBoard };
                    setCandidate(next);
                    if (currentCode.current === base && !manualCodeDirtyRef.current) {
                        setCodePreview(next);
                        setCheck(null);
                    }
                }
                setHistoryRefresh(count => count + 1);
                await syncFolder(id);
            }
        }
        catch (err) {
            const detail = aiController.current?.signal.aborted ? '已取消本次 AI 请求。输入已保留，代码未修改。' : errorText(err);
            setError(detail);
            setChatError(detail);
            if (id && currentProject.current === id) {
                try {
                    const saved = await api<Project>('/projects/' + id);
                    setMessages(saved.messages);
                }
                catch { /* keep the prompt and existing conversation for retry */ }
                await syncFolder(id);
            }
        }
        finally {
            aiController.current = null;
            sendingMessage.current = false;
            setAiBusy(false);
            setPendingPrompt('');
            setStreamedReply('');
        }
    };
    const showReplyCode = (content: string, messageId: string, boardId?: string) => {
        const value = replyCode(content);
        if (value === null)
            return;
        if (boardId && boardId !== board && !window.confirm('此代码来自其他主控，仅预览代码，当前主控不变。继续吗？'))
            return;
        const version = codeVersions.find(item => item.messageId === messageId);
        setCodePreview({ code: value, revision: version?.revision, boardId });
        setCheck(null);
        setMobileTab('code');
    };
    const editPreview = () => {
        if (!codePreview)
            return;
        if (manualDirty && codePreview.code !== code && !window.confirm('用此生成稿替换未保存的手工草稿？可先返回原稿保存或导出。'))
            return;
        setCode(codePreview.code);
        setSelectedVersion(codePreview.revision ?? null);
        setCodePreview(null);
        setCandidate(null);
        setCheck(null);
    };
    const fillReply = (answer: string) => { setMessage(value => (value.trim() ? value + '\n' + answer : answer).slice(0, 4000)); chatInput.current?.focus(); };
    const boardSensors = selectableModules(hardware);
    const available = filterModules(boardSensors, moduleBrandFilter, moduleFilter, moduleTypeFilter, search).filter(item => !onlyPersonal || item.personal);
    const outsideLibrary = components.filter(id => !boardSensors.some(item => item.componentId === id));
    const selectedSensors = components.map(id => hardware.find(item => item.componentId === id)).filter((item): item is HardwareSummary => !!item && !!moduleDirection(item));
    const receipt = device.current?.receipt;
    const projectLocked = learningBusy || loading || !!busy || aiBusy || structureBusy || deviceBusy || flashing || chatCodingBusy;
    const openFiles = (view: 'programs' | 'board') => void action('读取文件信息', async () => {
        setFileVersions(project ? (await api<{
            versions: Version[];
        }>(`/projects/${project.id}/versions`)).versions : null);
        setFilesDialog(view);
    });
    const openHistory = () => void action('读取代码版本', async () => {
        setVersions(project ? (await api<{
            versions: Version[];
        }>(`/projects/${project.id}/versions`)).versions : []);
    });
    const checkCode = () => void action('检查', async () => {
        setCheck(await api<CheckResult>('/check', 'POST', { code: visibleCode, boardId: board, componentIds: components }));
        setCheckExpanded(true);
        setMobileTab('code');
    });
    const loadCode = (value: string, sourceBoard?: {
        id: string;
        name: string;
    }) => {
        const differentBoard = sourceBoard && sourceBoard.id !== board;
        if ((differentBoard || (code !== value && code.length)) && !window.confirm(`${differentBoard ? `此程序用于 ${sourceBoard.name}，当前主控不会切换，请核对代码与接线。` : ''}用此文件替换编辑器草稿？设备文件不会改变。`))
            return;
        setCode(value);
        setCodePreview(null);
        setSelectedVersion(null);
        setCheck(null);
        setFilesDialog(null);
        setNotice('程序已载入编辑器，尚未保存或上传。');
        setMobileTab('code');
    };
    const importCode = async (file?: File) => {
        if (!file)
            return;
        await action('导入程序', async () => {
            if (!file.name.toLowerCase().endsWith('.py') || file.size > 65536)
                throw new Error('请选择64 KiB以内的 .py 文件。');
            const value = new TextDecoder('utf-8', { fatal: true }).decode(await file.arrayBuffer());
            if (value.includes('\0'))
                throw new Error('代码文件不能包含NUL。');
            loadCode(value);
        });
    };
    const saveState = mode === 'learning' ? learningBusy ? '项目记录处理中…' : learningDirty ? '项目草稿 · 本浏览器保留' : folderError ? '本机已记录 · 文件夹未同步' : '项目记录随项目保存' : mode === 'structure' && structureUnsaved ? '结构草稿在本浏览器保留 · 尚未应用' : busy.includes('保存') || folderStatus === '正在同步' ? '正在保存…'
        : isChatCoding && nativeChat.source === 'local' && !!nativeChat.lua.editorCode.trim() && !nativeChat.lua.saved ? 'Lua修改未保存 · 点击「保存代码」'
            : folderError ? '本机已记录 · 文件夹未同步' : manualDirty || hardwareDirty ? '未保存更改'
                : !project ? '尚未保存项目' : !folder ? '本机已记录 · 未选文件夹' : folderStatus === '已同步' ? '已保存到项目文件夹' : `项目文件夹 · ${folderStatus}`;
    const checkLabel = !check ? '未检查 · 点击检查' : !check.valid ? `发现 ${check.diagnostics.filter(item => item.severity === 'FAIL').length} 项问题`
        : check.diagnostics.some(item => item.severity === 'WARNING') ? '代码检查通过 · 有提示' : '代码检查通过';
    const canRun = connected && receipt && !dirty && receipt.projectId === project?.id && receipt.revision === project.revision;
    const activeMessages = messages.filter(item => (item.boardId ?? project?.boardId ?? board) === board);
    const latestReply = activeMessages.filter(item => item.role === 'assistant' && item.status === 'COMPLETED').at(-1);
    const latestReplyCode = latestReply ? replyCode(latestReply.content) : null;
    const latestReplyRevision = codeVersions.find(version => version.messageId === latestReply?.id)?.revision;
    const matchesLatestReply = latestReplyCode !== null && latestReplyCode.trimEnd() === visibleCode.trimEnd();
    const pastMessages = messages.filter(item => !activeMessages.includes(item));
    return <div className={`app final-workbench ${hardwareCollapsed ? 'hardware-collapsed' : ''} ${codeFullscreen ? 'code-fullscreen' : ''}`}>
    <FeedbackToast error={workspaceOpen ? error : ''} notice={notice} sequence={noticeSequence} busy={workspaceOpen ? busy : ''} progress={progress} onCancel={() => device.current?.cancel()}/>
    {workspaceOpen && sharedProjectOpen && project && <SharedProjectDialog key={project.id} projectId={project.id} unsaved={workspaceDirty} onClose={() => setSharedProjectOpen(false)}/>}
    {workspaceOpen ? <>
    <header className="workspace-titlebar">
      <a className="title-brand" href="/" aria-label="掌问：智能体造物工作台"><span><img src={palmMark} alt="" width={24} height={24}/></span><strong>掌问：智能体造物工作台</strong></a>
      <div className="title-project-actions" role="group" aria-label="项目操作">
        <ActionMenu label="项目" disabled={projectLocked} items={[
                { label: '新建项目', icon: Plus, onSelect: openNew },
                { label: '打开项目…', icon: FolderOpen, onSelect: openLoad },
                { label: '项目进度与验收', icon: CheckCheck, onSelect: () => { selectMode('learning'); setLearningSection('project'); } },
                { label: '项目程序', icon: FileCode2, disabled: isChatCoding, onSelect: () => openFiles('programs') },
                { label: '项目资料', icon: BookOpen, onSelect: () => void action('打开项目资料', async () => { if (!project) {
                        const created = await api<Project>('/projects', 'POST', { name: name === '未命名项目' ? '我的项目' : name, boardId: board, componentIds: components, code });
                        applyProject(created, false);
                        await refreshProjects();
                    } setReferencesDialog(true); }) },
                ...projects.slice(0, 5).map((item, index) => ({ label: item.name, group: index === 0 ? '最近项目' : undefined, icon: FolderOpen, onSelect: () => void chooseProject(item.id) })),
                { label: '另存到文件夹…', icon: Save, group: '保存位置', disabled: !project, onSelect: () => { setUploadAfterSave(false); openSave(); } },
                ...(project && stored('zhangwen-conflict-backup-' + project.id) ? [{ label: '导出同步前草稿', icon: Download, onSelect: () => download('掌问-同步前草稿.json', stored('zhangwen-conflict-backup-' + project.id)!) }] : []),
            ]}/>
        <button className="title-save" aria-label="保存项目" title="保存项目（Ctrl / ⌘ + S）" disabled={projectLocked} onClick={() => void saveWorkspace()}>{busy.includes('保存') ? <LoaderCircle size={15} className="spin"/> : <Save size={15}/>}保存</button>
      </div>
      <div className="current-project" aria-label="当前项目" title={name}><strong>{name}</strong>{workspaceDirty && <span className="dirty-dot" aria-label="项目存在未保存内容"/>}</div>
      <span className={`document-info ${folderError ? 'has-error' : ''}`} role="status" aria-label="项目保存状态">{saveState}</span>
      <button className="theme-toggle" aria-label={theme === 'light' ? '切换深色主题' : '切换浅色主题'} title={theme === 'light' ? '深色主题' : '浅色主题'} onClick={() => setTheme(value => value === 'light' ? 'dark' : 'light')}>{theme === 'light' ? <Moon size={17}/> : <Sun size={17}/>}</button>
    </header>
    <header className="zhangwen-toolbar" aria-label="掌问工具栏">
      <div className="zhangwen-commands">
        <div className="tool-group" role="group" aria-label="工作角色">
        <ToolbarButton icon={Layers3} label={modeInfo.name} aria-label="模式切换" variant="brand" active={modeDialog} disabled={learningBusy || loading || !!busy || aiBusy || structureBusy || chatCodingBusy || deviceBusy || running || flashing || deviceState === 'attention'} onClick={() => setModeDialog(true)} title={`切换角色 · ${modeInfo.name}`}/>
        </div>
        {mode !== 'learning' && <div className="tool-group"><ToolbarButton icon={CheckCheck} label="项目进度" disabled={projectLocked} onClick={() => { selectMode('learning'); setLearningSection('project'); }} title="查看需求、测试与成果记录"/></div>}
        <div className="tool-group"><ToolbarButton icon={RefreshCw} label="调整目标" disabled={!project || projectLocked} onClick={() => setRequirementSync(true)} title="修改项目目标，查看三师的下一步任务"/></div>
        {mode === 'engineer' && !isChatCoding && <>
        <div className="tool-group" role="group" aria-label="设备操作">
        <ToolbarButton icon={ArrowUp} label="上传并运行" variant="hardware" disabled={loading || !board || !!busy || aiBusy || deviceBusy || running || deviceState === 'attention'} onClick={() => void prepareUpload()} title="上传并运行 main.py：保存、备份、回读校验，通过后自动运行"/>
        <ToolbarButton icon={running || deviceState === 'attention' ? Square : Play} label={running || deviceState === 'attention' ? '停止' : '运行'} emphasis active={running} disabled={!!busy || deviceBusy || !(running || canRun || deviceState === 'attention')} onClick={() => { setTerminalOpen(true); setMobileTab('code'); void action(running || deviceState === 'attention' ? '停止' : '运行', async () => { if (running || deviceState === 'attention')
                await device.current?.stop();
            else
                await runProgram(); }); }}/>
        <ToolbarButton icon={Terminal} label="运行输出" active={terminalOpen} aria-pressed={terminalOpen} onClick={() => { setTerminalOpen(value => !value); setMobileTab('code'); }}/>
        <ToolbarButton icon={Files} label="板载文件" active={filesDialog === 'board'} disabled={loading || !!busy || deviceBusy} onClick={() => openFiles('board')} title="浏览、读取和导出板载文件"/>
        <ToolbarButton icon={Cpu} label="固件刷入" variant="hardware" disabled={loading || !board || !!busy || aiBusy || flashing || deviceState !== 'disconnected'} title={board ? `刷入 ${boardInfo?.displayName ?? '当前主控'} 对应固件；请先断开设备` : '请先在左侧选择主控板'} onClick={() => setFirmwareDialog(true)}/>
        </div></>}
        {mode === 'structure' && <><div className="tool-group" role="group" aria-label="结构设计功能">
          <ToolbarButton icon={Box} label="3D造物" active={structureDesignType === 'model'} aria-pressed={structureDesignType === 'model'} disabled={structureBusy} onClick={() => setStructureDesignType('model')}/>
          <ToolbarButton icon={ScanLine} label="激光造物" active={structureDesignType === 'laser'} aria-pressed={structureDesignType === 'laser'} disabled={structureBusy} onClick={() => setStructureDesignType('laser')}/>
        </div></>}
        {mode === 'learning' && <><div className="tool-group" role="group" aria-label="学习栏目切换">
          {learningSections.map(({ id, label, note, icon }) => <ToolbarButton key={id} icon={icon} label={label} active={learningSection === id} variant={learningSection === id ? 'software' : 'muted'} aria-pressed={learningSection === id} aria-controls="learning-section-content" onClick={() => setLearningSection(id)} title={`${label}${note ? ` · ${note}` : ''}`}/>)}
        </div></>}
        {mode === 'engineer' && isChatCoding && <div className="tool-group" role="group" aria-label="设备操作">
          {nativeChat.source === 'local' ? <><ToolbarButton icon={Save} label="保存代码" title="保存手工修改（生成代码自动保存）" disabled={nativeChat.lua.locked || !nativeChat.lua.editorCode.trim() || nativeChat.lua.saved} onClick={() => void nativeChat.lua.save()}/><ToolbarButton icon={Sparkles} label="生成代码" disabled={nativeChat.lua.generateLocked || !nativeChat.lua.prompt.trim()} onClick={() => void nativeChat.lua.generate()}/><ToolbarButton icon={Upload} label="上传运行" aria-label="上传并运行" title="上传并运行已保存的代码" disabled={!!nativeChat.lua.uploadAndRunBlockedReason} onClick={() => void nativeChat.lua.uploadAndRun()}/></> : <><ToolbarButton icon={Send} label="发送任务" variant="hardware" disabled={!nativeChat.canSend} onClick={nativeChat.send} title="发送已保存任务到设备原生 Claw"/><ToolbarButton icon={RefreshCw} label="刷新回复" disabled={!nativeChat.state.connected || nativeChat.locked} onClick={() => void nativeChat.perform('读取设备回复', '/sync')}/></>}
          {<ToolbarButton icon={Settings} label="设备设置" disabled={projectLocked} onClick={() => { ; nativeChat.device.chooseSection('status'); setMobileTab('code'); if (!nativeChat.device.state.connected)
                nativeChat.setConnectionOpen(true); }} title="在右侧操作Mosaico状态、配置、日志与文件"/>}
        </div>}
        <div className="tool-group" role="group" aria-label="设置与帮助">
        <ToolbarButton icon={Settings} label="AI 设置" variant="muted" active={aiSettingsDialog} disabled={loading || !!busy || aiBusy || structureBusy || chatCodingBusy} onClick={openAiSettings} title="设置掌问 AI 模型服务"/>
        <UpdateCenter enabled={!loading} blocked={learningBusy || !!busy || aiBusy || structureBusy || chatCodingBusy || deviceBusy || running || flashing || deviceState === 'attention'} unsaved={workspaceDirty || !!folderError || folderPending.current > 0}/>
        <ToolbarButton icon={HelpCircle} label="帮助" variant="muted" active={helpDialog} onClick={() => setHelpDialog(true)}/>
        </div>
        <div className="tool-group project-tools" role="group" aria-label="项目文件与共享信息">
          <ToolbarButton ref={folderToggle} className="folder-panel-toggle" icon={PanelRightOpen} label="项目文件夹" active={!!project && folderPanel && !codeFullscreen} title={folderPanel && !codeFullscreen ? '收起项目文件夹' : '展开项目文件夹'} aria-expanded={!!project && folderPanel && !codeFullscreen} aria-controls="project-folder-panel" disabled={!project} onClick={() => { setFolderPanel(!folderPanel || codeFullscreen); if (codeFullscreen)
            setCodeFullscreen(false); }}/>
          <ToolbarButton icon={BookOpen} label="三师共享信息" active={sharedProjectOpen} aria-haspopup="dialog" disabled={!project} onClick={() => setSharedProjectOpen(true)} title="查看三师共用的已保存项目信息"/>
        </div>
      </div>
      {mode === 'engineer' && isChatCoding && <button className={`connection toolbar-status ${nativeChat.state.connected || nativeChat.device.state.connected ? 'is-connected' : ''}`} disabled={projectLocked} onClick={() => nativeChat.setConnectionOpen(true)}>{chatCodingBusy ? <LoaderCircle size={17} className="spin"/> : <Wifi size={17}/>}<span>{nativeChat.state.connected || nativeChat.device.state.connected ? '已连接 · 设置' : '连接设备'}</span></button>}
      {((mode === 'engineer' && !isChatCoding) || deviceState !== 'disconnected') && <button className={`connection toolbar-status ${deviceState !== 'disconnected' ? 'is-connected' : ''}`} disabled={!!busy || deviceBusy} onClick={deviceState === 'disconnected' ? () => { setTerminalOpen(true); setMobileTab('code'); void connectDevice(); } : disconnect}>{deviceBusy ? <LoaderCircle size={17} className="spin"/> : deviceState === 'disconnected' ? <Usb size={17}/> : <Unplug size={17}/>}<span>{deviceState === 'disconnected' ? '连接设备' : deviceBusy ? (busy === '选择设备并检测固件' ? '正在检测固件' : '设备处理中') : deviceState === 'attention' ? '需要重连 · 断开' : '已连接 · 断开'}</span></button>}
    </header>
    {projectConflict && projectConflict.id === project?.id && <Dialog title="同步项目" className="project-conflict-dialog" onClose={() => setProjectConflict(null)}>
      <p>本机项目与当前草稿有不同内容。先备份草稿并同步，再继续生成。</p>
      <p>当前草稿：{name} · {hardware.find(item => item.componentId === board)?.displayName ?? board} · {components.length} 个模块</p>
      <p>最新项目：{projectConflict.name} · {hardware.find(item => item.componentId === projectConflict.boardId)?.displayName ?? projectConflict.boardId} · {projectConflict.componentIds.length} 个模块</p>
      <details><summary>查看不同内容</summary><h3>当前草稿</h3><pre>{JSON.stringify({ name, boardId: board, componentIds: components, code }, null, 2)}</pre><h3>最新项目</h3><pre>{JSON.stringify(projectContent(projectConflict), null, 2)}</pre></details>
      <p className="muted">备份包含当前代码和编程需求。{isChatCoding && projectConflict.programmingMode === 'chat-coding' ? 'Lua代码、生成稿和需求仍保留在当前页面。' : '同步后可从下载的备份中找回草稿。'}</p>
      <div className="lua-actions"><button disabled={!!busy} onClick={() => setProjectConflict(null)}>暂不处理</button><button className="primary" disabled={!!busy || chatCodingBusy} onClick={() => void action('同步项目', async () => {
                    const id = projectConflict.id;
                    const latest = await api<Project>('/projects/' + id);
                    if (currentProject.current !== id)
                        return;
                    const backup = JSON.stringify({ schemaVersion: 1, projectId: id, baseRevision: draftRevision ?? project.revision,
                        content: { name, boardId: board, componentIds: components, code }, codePreview, candidate,
                        lua: { draft: nativeChat.lua.draft, prompt: nativeChat.lua.prompt, candidate: nativeChat.lua.codeCandidate,
                            showingCandidate: nativeChat.lua.showingCandidate, sourceRevision: nativeChat.lua.draftSourceRevision },
                        structureDrafts, savedProject: latest }, null, 2);
                    // Keep a recoverable copy even when the browser blocks the download.
                    // If storage is full, leave the original draft and conflict in place.
                    localStorage.setItem('zhangwen-conflict-backup-' + id, backup);
                    download('掌问-同步前草稿.json', backup);
                    applyProject(latest, false);
                    nativeChat.lua.clearError();
                    setError('');
                    setNewDialog(false);
                    await refreshProjects();
                    setNotice('草稿备份已下载，项目设置已同步。可继续生成代码。');
                })}>备份草稿并同步</button></div>
    </Dialog>}
    <div className="workspace-deck"><div className="workspace-stage" id="workspace-stage" tabIndex={-1}>
    <div className="engineering-surface" hidden={mode !== 'engineer'}>
    <nav className="mobile-tabs" aria-label="工作区切换">{[['hardware', '硬件库'], ['ai', isChatCoding ? (nativeChat.source === 'local' ? '编程对话' : 'Chat Coding') : '掌问 AI'], ['code', isChatCoding ? (nativeChat.source === 'local' ? '程序' : '任务与记录') : '代码']].map(([key, label]) => <button key={key} className={mobileTab === key ? 'active' : ''} onClick={() => { setMobileTab(key); if (key === 'hardware')
            setHardwareCollapsed(false); }}>{label}</button>)}</nav>
    <main className="workbench">
      <aside className={`hardware-panel panel mobile-${mobileTab === 'hardware' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><CircuitBoard size={18}/>已加入的模块</h2><button className="icon-button hardware-collapse" aria-label="收起硬件模块" title="向左收起硬件模块" onClick={() => setHardwareCollapsed(true)}><PanelLeftClose size={17}/></button></div>
        <div className="selected-sensors-toolbar"><span className="board-field-label">主控板</span><button className={`board-control${board ? '' : ' needs-board'}`} aria-label="主控板" title={board ? '点击更换主控板' : '选择项目使用的主控板'} disabled={projectLocked} onClick={() => setBoardDialog(true)}><BoardArtwork board={boardInfo}/><span>{boardInfo?.displayName ?? '选择主控板'}</span><ChevronRight size={14}/></button>{!board && !loading && <p className="board-select-hint">先选主控，再添加模块</p>}<button className="add-sensor-button" disabled={projectLocked || !board} onClick={openSensorPicker}><Plus size={18}/>{isChatCoding ? '添加外接模块' : '添加模块'}</button></div>
        <div className="catalog-list selected-sensor-list">{loading ? <p className="muted">正在读取项目…</p> : (['input', 'output', 'support'] as const).map(direction => {
                const items = selectedSensors.filter(item => moduleDirection(item) === direction);
                return items.length > 0 && <section className="module-group" key={direction} aria-label={direction === 'input' ? '已加入的输入模块' : direction === 'output' ? '已加入的输出模块' : '已加入的配套模块'}><h3>{direction === 'input' ? '输入模块' : direction === 'output' ? '输出模块' : '配套模块'}<span>{items.length}</span></h3><div className="module-grid">{items.map(item => <ModuleCard key={item.componentId} item={item} boardId={board} boards={hardware.filter(board => board.category === 'MCU')} disabled={projectLocked} outside={!boardSensors.some(module => module.componentId === item.componentId)} onDetail={() => openDetail(item)} onEditExample={() => openDetail(item, false, true)} onLoad={() => loadModuleSample(item)} onRemove={() => removeSensor(item.componentId)}/>)}</div></section>;
            })}{!loading && board && !selectedSensors.length && <div className="selected-sensors-empty"><CircuitBoard size={42}/><strong>{isChatCoding ? '查看板载能力' : '为项目添加模块'}</strong>{isChatCoding ? <><p>板载器件无需另加模块。固件接口与实测状态请查看主控资料。</p><button onClick={() => boardInfo && openDetail(boardInfo)}>查看Mosaico使用资料</button><p>需要外接器件时，点击“添加外接模块”。</p></> : <p>点击「添加模块」，选择传感器、执行器或显示模块。</p>}</div>}</div>
        {outsideLibrary.length > 0 && <p className="library-notice">有 {outsideLibrary.length} 个项目元件的资料缺失或未激活，已保留；请查看资料并核对。</p>}
        <footer className="catalog-foot"><BookOpen size={16}/><span>输入感知 · 输出控制<br /><small>点击模块查看资料，⋮ 展开选项</small></span></footer>
      </aside>
      <button className="hardware-restore" aria-label="展开硬件模块" title="展开硬件模块" onClick={() => { setHardwareCollapsed(false); setMobileTab('hardware'); }}><PanelLeftOpen size={18}/><span>硬件模块</span><small>{selectedSensors.length}</small></button>
      {isChatCoding ? <>
        <ChatCodingConversation chat={nativeChat} task={code} onTask={value => { setCode(value); setSelectedVersion(null); }} onSave={() => void action('保存项目', () => save())} mobileTab={mobileTab} onSettings={openAiSettings}/>
        <ChatCodingTask chat={nativeChat} task={code} versions={codeVersions.filter(v => v.programmingMode === 'chat-coding')} selectedVersion={selectedVersion} onVersion={selectCodeVersion} mobileTab={mobileTab} saveState={saveState} folderError={folderError} onRetryFolder={() => void action('重新保存项目文件夹', async () => { if (project && folderRef.current) {
                await ensureFolderPermission(folderRef.current, true);
                await syncFolder(project.id);
            } })}/>
      </> : <>
      <section className={`ai-panel panel mobile-${mobileTab === 'ai' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Sparkles size={18}/>智能工程师</h2><button className="api-settings-entry" disabled={loading || !!busy || aiBusy} onClick={openAiSettings} aria-label="掌问 AI 设置"><Settings size={14}/><span>{aiConfigured ? '已配置' : '未配置'}</span> · 设置</button></div>
        <div ref={conversationPane} className="messages" role="log" aria-label="掌问对话记录" onWheel={event => { if (event.deltaY < 0)
                followConversation.current = false; }} onPointerDown={event => { if (event.target === event.currentTarget)
                followConversation.current = false; }} onKeyDown={event => { if (['ArrowUp', 'PageUp', 'Home'].includes(event.key))
                followConversation.current = false; }} onScroll={event => { const pane = event.currentTarget; if (pane.scrollHeight - pane.scrollTop - pane.clientHeight <= 64)
                followConversation.current = true; }}>
          {!loading && boardInfo && <section ref={components.length ? undefined : hardwareGuide} tabIndex={-1} className="conversation-board-context" aria-label="当前主控对话"><BoardArtwork board={boardInfo}/><div><strong>{boardInfo.displayName}</strong><p>告诉我想让作品做什么，或把遇到的问题发给我。</p></div></section>}
          {!loading && components.length > 0 && <section ref={hardwareGuide} className="message assistant hardware-guide" aria-label="掌问硬件引导" tabIndex={-1}>
            <HardwareGuide key={JSON.stringify([guideScope, board, components])} board={boardInfo} componentIds={components} hardware={hardware} disabled={loading || !!busy || aiBusy || deviceBusy || !board} onTest={() => { setIntegrationExitScope(null); store('zhangwen-integration-exit-scope', ''); void sendMessage(integrationPrompt(boardInfo, board, components, hardware), 'integration', components[0]); }} onDevelop={leaveIntegration}/>
          </section>}
          {!loading && !board && <section className="board-selection-prompt" aria-label="选择主控引导"><CircuitBoard size={24}/><div><strong>这个项目使用哪款主控？</strong><p>选择作品使用的主控板，再描述你想实现的功能。</p></div><button className="primary" disabled={!!busy || aiBusy || deviceBusy} onClick={() => setBoardDialog(true)}>选择主控</button></section>}
          {board && !activeMessages.length && !pendingPrompt && !components.length && <div className="conversation-empty"><span><Sparkles size={24} strokeWidth={1.6}/></span><p>描述你的想法，或粘贴需要分析的代码与报错。</p></div>}
          {pastMessages.length > 0 && <details className="past-board-conversations"><summary>之前主控的对话 · {pastMessages.length} 条</summary>{pastMessages.map(item => <article className={`message ${item.role}`} key={item.id}><strong>{hardware.find(value => value.componentId === (item.boardId ?? project?.boardId))?.displayName ?? '之前主控'} · {item.role === 'user' ? '你' : '掌问'}</strong>{item.role === 'assistant' && item.status === 'COMPLETED' ? <AssistantMessage content={item.content} revision={codeVersions.find(version => version.messageId === item.id)?.revision} disabled={!!busy || aiBusy || deviceBusy} onCode={() => showReplyCode(item.content, item.id, item.boardId ?? project?.boardId)}/> : item.role === 'user' ? <UserMessage content={item.content}/> : <pre>{item.content}</pre>}{item.role === 'assistant' && item.status === 'COMPLETED' && <ReferenceSources references={item.references} notice={item.referenceNotice}/>}</article>)}</details>}
          {activeMessages.map(item => <article className={`message ${item.role}`} key={item.id}><strong>{item.role === 'user' ? '你' : '掌问'}{item.status === 'FAILED' ? ' · 请求失败' : ''}</strong>{item.role === 'assistant' && item.status === 'COMPLETED' ? <AssistantMessage content={item.content} revision={codeVersions.find(version => version.messageId === item.id)?.revision} disabled={!!busy || aiBusy || deviceBusy} onCode={() => showReplyCode(item.content, item.id, item.boardId ?? project?.boardId)} hasProgram={!!visibleCode.trim()} isCurrentCode={replyCode(item.content)?.trimEnd() === visibleCode.trimEnd()} onReply={item.id === activeMessages.filter(value => value.role === 'assistant' && value.status === 'COMPLETED').at(-1)?.id ? fillReply : undefined}/> : item.role === 'user' ? <UserMessage content={item.content}/> : <pre>{item.content}</pre>}{item.role === 'assistant' && item.status === 'COMPLETED' && <ReferenceSources references={item.references} notice={item.referenceNotice}/>}</article>)}
          {pendingPrompt && <article className="message user"><strong>你 · 正在发送</strong><UserMessage content={pendingPrompt}/></article>}
          {aiBusy && submittedSources && <ReferenceSources references={submittedSources.references} notice={submittedSources.notice}/>}
          {aiBusy && streamedReply && <article className="message assistant"><strong>掌问 · 正在生成</strong><pre>{streamText(streamedReply)}</pre></article>}
          {aiBusy && <div className="ai-progress"><p className="muted" role="status"><LoaderCircle size={16} className="spin"/> {aiPhase === 'preparing' ? '正在准备对话' : aiPhase === 'waiting' ? `正在等待 ${aiBaseUrl.startsWith('https://api.deepseek.com') ? 'DeepSeek' : '模型'} 回答` : '正在生成回答'} · {aiElapsed} 秒</p>{aiPhase !== 'preparing' && <button type="button" onClick={() => aiController.current?.abort()}>取消生成</button>}{aiPhase === 'waiting' && aiElapsed >= 20 && <small>供应商暂未返回正文，可继续等待或取消后稍后重试。</small>}</div>}
          {candidate && !codePreview && <div className="candidate"><FileCode2 size={19}/><span>新代码已生成，当前草稿已保留。</span><button disabled={!!busy || deviceBusy || aiBusy} onClick={() => { setCodePreview(candidate); setCheck(null); setMobileTab('code'); }}>查看新版本</button></div>}
        </div>
        {integration && <IntegrationProgress state={integration} componentIds={components} hardware={hardware} disabled={loading || !!busy || aiBusy || deviceBusy || !board} onSelect={id => void sendMessage(integrationPrompt(boardInfo, board, components, hardware, id), 'integration', id)} onDevelop={leaveIntegration}/>}
        {chatError && <p className="chat-error" role="alert">{chatError}</p>}
        {!project && <p className="chat-hint">首次发送会自动保存当前项目、代码和已加入模块。</p>}
        <form className="chat-form" onSubmit={event => { event.preventDefault(); void sendMessage(); }}><label className="sr-only" htmlFor="chat-message">发送给掌问 AI</label><textarea ref={chatInput} id="chat-message" value={message} onChange={event => setMessage(event.target.value)} onKeyDown={event => { if ((event.ctrlKey || event.metaKey) && event.key === 'Enter' && !event.nativeEvent.isComposing && !loading && !busy && !aiBusy && message.trim()) {
                event.preventDefault();
                void sendMessage();
            } }} placeholder="告诉智能工程师，你想让作品怎样工作…" maxLength={4000}/><div><span>{!board ? "请先选择项目使用的主控板" : !aiConfigured ? "先打开 AI 设置" : "核对生成代码并保存，再点击上传并运行"}</span><button className="primary icon-button" aria-label="发送" disabled={loading || !!busy || !board || !message.trim() || aiBusy}>{aiBusy ? <LoaderCircle size={19} className="spin"/> : <ArrowUp size={20}/>}</button></div></form>
      </section>
      <section className={`code-panel panel mobile-${mobileTab === 'code' ? 'show' : 'hide'}`}>
        <div className="filebar"><span><FileCode2 size={16}/>main.py</span><span className="filebar-space"/><select className="code-version-select" aria-label="代码历史版本" disabled={!project || !codeVersions.length || !!busy || aiBusy || deviceBusy} value={codePreview ? codePreview.revision ?? 'preview' : selectedVersion ?? 'draft'} onChange={event => { if (event.target.value === 'draft')
                setCodePreview(null);
            else
                selectCodeVersion(Number(event.target.value)); }}><option value="draft" disabled={!codePreview}>{project ? '未保存草稿' : '尚无版本'}</option>{codePreview && !codePreview.revision && <option value="preview">AI生成稿 · 未保存</option>}{codeVersions.map(version => <option key={version.revision} value={version.revision}>V{version.revision} · {version.name || "MicroPython 程序"} · {version.source === 'ai' ? 'AI生成稿 · 未保存' : '已保存'}{version.boardId && version.boardId !== board ? ' · 其他主控' : ''}</option>)}</select><div className="editor-view-controls"><button aria-label="缩小代码" title="缩小代码" disabled={zoom <= 80} onClick={() => setZoom(value => Math.max(80, value - 10))}><ZoomOut size={16}/></button><span aria-label="代码字号比例">{zoom}%</span><button aria-label="放大代码" title="放大代码" disabled={zoom >= 160} onClick={() => setZoom(value => Math.min(160, value + 10))}><ZoomIn size={16}/></button><button aria-label={codeFullscreen ? '退出代码全屏' : '代码全屏'} title={codeFullscreen ? '退出全屏（Esc）' : '代码全屏'} onClick={() => setCodeFullscreen(value => !value)}>{codeFullscreen ? <Minimize size={16}/> : <Maximize size={16}/>}</button></div><ActionMenu label="代码工具" align="right" disabled={loading || !!busy || deviceBusy} items={[
                    { label: '导入程序…', icon: Upload, disabled: aiBusy, onSelect: () => importInput.current?.click() },
                    { label: '导出当前程序', icon: Download, onSelect: () => download('main.py', visibleCode) },
                    { label: '整理缩进', icon: AlignLeft, group: '代码排版', disabled: !!codePreview || !code.length, onSelect: () => { editor.current?.formatIndentation(); setCheck(null); setNotice('已整理四空格缩进，不修复程序逻辑；可撤销。'); } },
                    { label: '撤销编辑', icon: Undo2, disabled: !!codePreview, shortcut: 'Ctrl / ⌘ + Z', onSelect: () => editor.current?.undo() },
                    { label: '管理版本', icon: History, group: '历史版本', disabled: !project, onSelect: openHistory },
                ]}><MoreHorizontal size={18}/></ActionMenu></div>
        <input ref={importInput} className="sr-only" type="file" accept=".py,text/x-python" aria-label="导入 Python 程序" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; void importCode(file); }}/>
        <div className={`project-folder-status ${folderError ? 'has-error' : ''}`}>
          <FolderOpen size={14}/><span>{folder ? `${folder.handle.name} · ${folderStatus}` : '保存项目时选择本地文件夹'}</span>
          {folderError && <button disabled={projectLocked} onClick={() => void action('重试文件夹同步', async () => { if (project && folderRef.current) {
                await ensureFolderPermission(folderRef.current, true);
                await syncFolder(project.id);
            } })}>重试同步</button>}
          <button className={`code-check-status ${check && !check.valid ? 'has-error' : check ? 'is-valid' : ''}`} disabled={loading || !board || !!busy || deviceBusy} title="只检查代码和硬件配置，不代表实物验证通过；上传前仍会自动检查" onClick={() => { if (check)
                setCheckExpanded(value => !value);
            else
                checkCode(); }}><CheckCheck size={14}/>{checkLabel}</button>
          {folderError && <p role="alert">{folderError}</p>}
        </div>
        {latestReplyCode !== null && latestReply && <div className="code-source-note" role="note" aria-label="代码与回复对应">{matchesLatestReply ? `右侧代码与最新回复${latestReplyRevision ? ` V${latestReplyRevision}` : ''}一致。` : <><span>右侧{selectedVersion && !codePreview ? ` V${selectedVersion}` : '代码'}与最新回复{latestReplyRevision ? ` V${latestReplyRevision}` : ''}不同。</span><button disabled={!!busy || aiBusy || deviceBusy} onClick={() => showReplyCode(latestReply.content, latestReply.id, latestReply.boardId ?? project?.boardId)}>查看最新回复代码</button></>}</div>}
        {codePreview && <section className="code-preview-banner" aria-label="AI代码生成稿预览"><div><strong>{codePreview.source === 'repair' ? '屏幕修复预览' : codePreview.source === 'pin-repair' ? '引脚修复预览' : 'AI生成稿'}{codePreview.revision ? ` · v${codePreview.revision}` : ''} · 尚未保存</strong><small>{manualDirty ? '原手工草稿已保留，可随时返回。' : '原保存版本保留在历史中。'}{codePreview.boardId && codePreview.boardId !== board && ' 此代码来自其他主控，请核对兼容性。'}</small></div><button disabled={!!busy || aiBusy || deviceBusy} onClick={editPreview}>采用此代码</button><button disabled={!!busy || aiBusy || deviceBusy} onClick={() => { setCodePreview(null); setCheck(null); }}>返回原稿</button><button className="primary" disabled={!!busy || aiBusy || deviceBusy} onClick={() => void action('保存此版本', () => save(true))}>保存此版本</button></section>}
        <Editor ref={editor} zoom={zoom} readOnly={loading || !!busy || deviceBusy || codePreview !== null} value={visibleCode} onChange={value => { setCode(value); setSelectedVersion(null); setCheck(null); }}/>
        {check && checkExpanded && <section className="check-results" aria-label="检查结果"><div><strong>{check.valid ? '静态检查完成' : '检查发现问题'}</strong><button disabled={!!busy || deviceBusy} onClick={checkCode}>重新检查</button><button className="icon-button" aria-label="关闭检查" onClick={() => setCheckExpanded(false)}><X size={16}/></button></div>{check.diagnostics.some(item => item.repair === 'k10-screen') && <button disabled={!!busy || aiBusy || deviceBusy} onClick={previewScreenRepair}>预览屏幕修复</button>}{check.diagnostics.some(item => item.repair === 'mpython-pins') && <button disabled={!!busy || aiBusy || deviceBusy} onClick={previewPinRepair}>按P号预览修复</button>}{check.diagnostics.map((item, index) => <p className={`diagnostic ${item.severity.toLowerCase()}`} key={index}><span>{item.severity === 'PASS' ? '通过' : item.severity === 'FAIL' ? '错误' : '提示'}</span>{item.line ? `第 ${item.line} 行 · ` : ''}{item.message}</p>)}</section>}
        <section className="terminal-panel" hidden={!terminalOpen}><div className="terminal-head"><h3><Terminal size={17}/>运行输出</h3><span>{running ? '正在执行 · 发送会先中断' : connected ? '设备已连接' : deviceState === 'attention' ? '连接需核对' : '未连接'}</span><button disabled={!!busy} onClick={() => setLogs('')}>清空</button><button onClick={() => void action('导出设备备份', async () => { const backup = await latestBackup(); if (!backup)
                throw new Error('尚无设备备份。'); if (backup.bytes)
                download('main-before-upload.py', backup.bytes);
            else
                setNotice('上次上传前设备不存在 main.py，无需恢复旧文件。'); })}>备份</button><button aria-label="收起终端" onClick={() => setTerminalOpen(false)}><X size={16}/></button></div><pre ref={serialLog} className="serial-log" aria-label="串口输出">{logs}</pre><details className="terminal-commands"><summary>高级：发送设备命令</summary><form className="repl-form" onSubmit={event => { event.preventDefault(); void sendRepl(); }}><span aria-hidden="true">&gt;&gt;&gt;</span><input aria-label="REPL 命令" placeholder={running ? '输入命令，发送时先中断当前程序' : connected ? '输入命令，按 Enter 发送' : '输入命令，发送时选择并连接设备'} value={repl} maxLength={4000} onChange={event => setRepl(event.target.value)} onKeyDown={event => { if (event.ctrlKey && event.key.toLowerCase() === 'c' && event.currentTarget.selectionStart === event.currentTarget.selectionEnd && running && !busy) {
                event.preventDefault();
                void action('中断程序', () => device.current!.stop());
            } }} disabled={!!busy || deviceBusy}/><button disabled={!repl.trim() || !!busy || deviceBusy || deviceState === 'attention'} title={running ? '中断当前程序并发送' : connected ? '发送命令' : '连接设备并发送'} aria-label="发送 REPL 命令"><ArrowUp size={17}/></button></form></details></section>
      </section>
      </>}
    </main>
    </div>
    {mode === 'engineer' && isChatCoding && nativeChat.connectionOpen && <ChatCodingConnection chat={nativeChat} onSave={() => void action('保存任务', () => save())}/>}
    <StructureWorkspace key={`${project?.id ?? 'new'}-${structureDesignType}`} designType={structureDesignType} draft={structureDrafts[structureDesignType]} onDraftChange={updateStructureInput} onDirtyChange={updateStructureDirty} saveDraftRef={structureSaveRef} projectId={project?.id} active={mode === 'structure'} board={boardInfo} modules={selectedSensors} onSaveProject={openSave} onSettings={openAiSettings} onBusy={setStructureBusy} onSaved={syncFolder} onHardwareDetail={item => openDetail(item, false, false, true)}/>
    <LearningWorkflow key={project?.id ?? 'scratch'} active={mode === 'learning'} project={project} board={boardInfo} modules={selectedSensors} section={learningSection} onSection={setLearningSection} onSaved={syncFolder} onBusy={setLearningBusy} onDirty={setLearningDirty} onRegisterSave={fn => { learningSaveRef.current = fn; }} onNew={openNew} blocked={loading || !!busy || aiBusy || structureBusy || chatCodingBusy || deviceBusy || flashing} engineeringDirty={dirty || nativeChat.lua.hasUnsaved} hardwareDirty={hardwareSelectionDirty} onChooseBoard={() => setBoardDialog(true)} onAddModules={openSensorPicker} onRemoveModule={removeSensor} onHardwareDetail={openDetail} onSaveHardware={saveHardwareSelection} refreshKey={historyRefresh} reviewChange={reviewChange} onReviewConsumed={() => setReviewChange(null)} onCollaborate={() => setRequirementSync(true)}/>
    </div>
    {folderPanel && project && <ProjectFolderPanel key={project.id} hidden={codeFullscreen} binding={folder} status={folderStatus} syncError={folderError} unsaved={workspaceDirty} onClose={() => { setFolderPanel(false); folderToggle.current?.focus(); }} onChooseFolder={() => { setUploadAfterSave(false); openSave(); }} onLocated={async (path) => {
                    const binding = folderRef.current;
                    if (!binding || binding.projectId !== project.id)
                        return;
                    const updated = { ...binding, nativePath: path };
                    folderRef.current = updated;
                    setFolder(updated);
                    await rememberFolder(updated);
                }}/>}
    </div>
    <footer className="statusbar">{mode === 'engineer' && isChatCoding ? <><span>Mosaico · {'Chat Coding'}</span><span>{nativeChat.source === 'local' ? '掌问生成 · WiFi运行' : '任务保存与设备发送分开'}</span><span>实物结果由观察确认</span></> : mode === 'engineer' ? <><span><span className="status-dot"/>智能工程师 · 编程与测试</span><span>{boardInfo?.displayName ?? '先选择主控板'} · {components.length} 个模块</span><span>本机保存 · 设备操作需确认</span></> : <><span>{modeInfo.name}{mode === 'learning' ? ' · 项目学习与验收' : ' · 设计与制作'}</span><span>{mode === 'learning' ? '需求 · 测试 · 证据 · 反思' : '项目内容已保留'}</span></>}</footer>
    </> : <StartScreen loading={loading} ready={initialized} busy={busy} error={error} theme={theme} onTheme={() => setTheme(value => value === 'light' ? 'dark' : 'light')} onNew={openNew} onLoad={openLoad} onRetry={() => setBootstrapAttempt(value => value + 1)}/>}
    {requirementSync && project && <RequirementSync key={project.id + '-' + mode} projectId={project.id} sourceMode={mode} initialText={(mode === 'engineer' ? (isChatCoding ? nativeChat.source === 'local' ? nativeChat.lua.prompt : '' : message) : mode === 'structure' ? structureDrafts[structureDesignType] : '').slice(0, 2000)} onClose={() => setRequirementSync(false)} onBusy={setLearningBusy} engineeringDirty={dirty || nativeChat.lua.hasUnsaved} onSaved={async (id) => { setHistoryRefresh(v => v + 1); await syncFolder(id); }} onReview={id => { if (!selectMode('learning'))
            return false; setLearningSection('guidance'); setReviewChange({ projectId: project.id, id }); return true; }} onTask={(target, text) => {
                const original = target === 'structure' ? structureDrafts[structureDesignType] : isChatCoding ? nativeChat.source === 'local' ? nativeChat.lua.prompt : code : message;
                const next = original.trim() ? original + '\n\n' + text : text;
                if (next.length > 4000 || !selectMode(target))
                    return false;
                if (target === 'structure')
                    updateStructureInput(next);
                else if (!isChatCoding)
                    setMessage(next);
                else if (nativeChat.source === 'local')
                    nativeChat.lua.setPrompt(next);
                else
                    setCode(next);
                setNotice('变更任务已带入输入框，原输入保留；请核对后发送。');
                return true;
            }}/>} 
    {modeDialog && <ModePicker current={mode} onSelect={selectMode} onClose={() => setModeDialog(false)}/>}
    {boardDialog && <BoardPicker boards={hardware} selected={board} onClose={() => setBoardDialog(false)} onSelect={item => { switchBoard(item.componentId); setBoardDialog(false); }} onHelp={() => { setBoardDialog(false); setHelpDialog(true); }}/>}
    {loadDialog && <Dialog title="打开项目" onClose={() => setLoadDialog(false)}>{busy === '读取项目' && <p className="muted" role="status">正在读取项目列表…</p>}<p className="muted">选择项目文件夹，恢复主控、模块、过往对话和全部代码版本。</p><button className="primary choose-project-folder" disabled={!!busy} onClick={() => void loadFolder()}><FolderOpen size={19}/>选择项目文件夹</button>{error && <p className="settings-error" role="alert">{error}</p>}<h3 className="recent-projects-title">最近本机项目</h3><p className="muted">也可继续打开本机工作记录；旧项目保存时可选择项目文件夹。</p>{projects.length ? projects.map(item => <button className="load-project-row" data-project-id={item.id} disabled={!!busy} key={item.id} onClick={async () => { if (await chooseProject(item.id))
        setLoadDialog(false); }}><FolderOpen size={22}/><span><strong>{item.name}</strong><small>版本 {item.revision} · {new Date(item.updatedAt).toLocaleString()}</small></span>{item.id === project?.id ? <Check size={18}/> : <ChevronRight size={18}/>}</button>) : <p>还没有最近项目，可从文件夹加载。</p>}</Dialog>}
    {helpDialog && <WorkbenchHelp mode={mode} mosaico={!!isChatCoding} source={nativeChat.source} onClose={() => setHelpDialog(false)}/>}
    {firmwareDialog && boardInfo && <FirmwareDialog board={boardInfo} onClose={() => setFirmwareDialog(false)} onBusy={setFlashing}/>}
    {aiSettingsDialog && <AiSettingsDialog settings={{ aiConfigured, aiModel, aiBaseUrl }} initialMode={mode} onClose={() => setAiSettingsDialog(false)} onSaved={result => { if (!result.mode || result.mode === 'engineer') {
        setAiConfigured(result.aiConfigured);
        setAiModel(result.aiModel);
        setAiBaseUrl(result.aiBaseUrl ?? 'https://api.deepseek.com');
    } setAiSettingsDialog(false); setNotice(result.aiConfigured ? '这位伙伴的 AI 设置已保存，立即生效。' : '这位伙伴的访问密钥已清除。'); }}/>}
    {newDialog && !boardDialog && !helpDialog && <Dialog title={creationMode === 'new' ? '新建项目' : '保存项目'} onClose={() => { if (!busy) {
        setNewDialog(false);
        setUploadAfterSave(false);
    } }}><form onSubmit={event => { event.preventDefault(); void action('保存项目文件夹', finishFolderProject); }}><label className="field">项目名称<input autoFocus value={newName} maxLength={80} onChange={event => setNewName(event.target.value)} required disabled={busy === '保存项目文件夹'}/></label><div className="field">项目文件夹<button type="button" className="choose-project-folder" disabled={!!busy} onClick={() => void selectNewFolder()}><FolderOpen size={19}/>{newFolder ? '重新选择文件夹' : '选择本地文件夹'}</button><span className="selected-project-folder" aria-label="已选项目文件夹">{newFolder?.name ?? '尚未选择'}</span></div><p className="muted">{creationMode === 'new' ? '在所选文件夹创建空白项目，主控板可在主界面选择。取消保留当前项目。' : '保存当前代码、主控、模块，以及已有对话和代码版本。'} {isChatCoding ? nativeChat.source === 'local' ? '生成的Lua自动保存并随项目项目备份保留；手工修改后需保存代码。加载后需重新连接设备。' : '原生Claw项目保留chat-task.txt和设备会话证据项目备份；加载后需重新连接设备。' : '文件夹保留 main.py 和 zhangwen.project.json；历史文件按「代码」「结构」分类，可在其他电脑加载。'}</p>{error && <p className="settings-error" role="alert">{error}</p>}<button className="primary" disabled={!newName.trim() || !newFolder || !!busy}>{creationMode === 'new' ? '创建项目' : '保存项目'}</button></form></Dialog>}
    {sensorPicker && <Dialog className="sensor-picker-dialog" title="添加模块" onClose={() => setSensorPicker(false)} headerActions={<>
      <div className="catalog-search picker-search"><Search size={17} aria-hidden="true"/><input data-dialog-autofocus aria-label="搜索硬件" placeholder="搜索名称、型号或功能…" value={search} onChange={event => setSearch(event.target.value)}/></div>
      <ModuleFilters items={boardSensors} brand={moduleBrandFilter} direction={moduleFilter} type={moduleTypeFilter} onBrand={setModuleBrandFilter} onType={(direction, type) => { setModuleFilter(direction); setModuleTypeFilter(type); }} onClear={clearModuleFilters}/>
    </>}>
      <div className="sensor-picker-context"><strong>多品牌模块库</strong><span>当前主控：{boardInfo?.displayName}</span></div>
      <div className="reference-actions"><button className="primary" onClick={() => { setSensorPicker(false); setPersonalModule(''); }}>新建我的模块</button><label><input type="checkbox" checked={onlyPersonal} onChange={event => setOnlyPersonal(event.target.checked)}/>只看我的模块</label></div>
      <p className="catalog-result-count" aria-live="polite">找到 {available.length} 个模块 · 可跨品牌选择，接线与驱动需单独核对</p>
      <div className="sensor-picker-list module-grid">{available.map(item => { const added = components.includes(item.componentId); return <ModuleCard key={item.componentId} item={item} boardId={board} boards={hardware.filter(board => board.category === 'MCU')} added={added} checked={added || pendingSensors.includes(item.componentId)} disabled={added || !!busy || aiBusy || deviceBusy || (!pendingSensors.includes(item.componentId) && components.length + pendingSensors.length >= 32)} onToggle={checked => setPendingSensors(value => checked ? [...new Set([...value, item.componentId])] : value.filter(id => id !== item.componentId))} onDetail={() => openDetail(item, true)}/>; })}{!available.length && <p className="catalog-empty muted">没有匹配的模块，试试其他品牌、类型或关键词。</p>}</div>
      <div className="sensor-picker-actions"><span>{pendingSensors.length ? `已选择 ${pendingSensors.length} 个` : '选择项目需要的模块'}{components.length + pendingSensors.length >= 32 && ' · 已达32项上限'}</span><button onClick={() => setSensorPicker(false)}>取消</button><button className="primary" aria-label="加入所选模块" disabled={!pendingSensors.length || !!busy || aiBusy || deviceBusy} onClick={() => { followConversation.current = false; setComponents(value => [...new Set([...value, ...pendingSensors])]); setCheck(null); setCandidate(null); setCodePreview(null); setSensorPicker(false); setMobileTab('ai'); setGuideReveal(value => value + 1); }}>{pendingSensors.length ? `加入 ${pendingSensors.length} 个模块` : '加入模块'}</button></div>
    </Dialog>}

    {referencesDialog && project && <ProjectReferences projectId={project.id} folder={folder?.handle ?? null} onClose={() => setReferencesDialog(false)} onChanged={() => syncFolder(project.id)} onModule={text => { setReferencesDialog(false); setPersonalModule(text); }}/>}
    {personalModule !== null && <PersonalModuleDialog boardId={board} boards={hardware.filter(item => item.category === 'MCU')} source={personalModule} onClose={() => setPersonalModule(null)} onCreated={value => { setHardware(items => [...items, value]); if (board && components.length < 32)
        setComponents(items => [...items, value.componentId]); setCheck(null); setPersonalModule(null); setDetail(value); setNotice('我的模块已创建，资料可供后续对话参考；尚未上传或实测。'); }}/>}
    {detail && <HardwareDetails detail={detail} board={boardInfo} boards={hardware.filter(item => item.category === 'MCU')} editExample={editExample} initialTab={detailTab} onSaved={value => { setCheck(null); setDetail(value); setHardware(items => items.map(item => item.skillName === value.skillName ? value : item)); }} onClose={() => { setDetail(null); if (returnToPicker)
        setSensorPicker(true); setReturnToPicker(false); }}/>}
    {moduleSample && <Dialog title={`载入模块：${moduleSample.item.displayName}`} onClose={() => setModuleSample(null)}>{moduleSample.scope && <p className="module-guide-summary">{moduleSample.scope}</p>}<p className="muted">示例来自此硬件资料包。确认后替换当前 {moduleSample.language === 'lua' ? 'main.lua' : 'main.py'} 草稿；请按实际接线修改端口并检查，保存和上传仍需单独操作。</p><pre className="candidate-code">{moduleSample.code}</pre><button className="primary" onClick={() => {
                if (board !== moduleSample.boardId || project?.id !== moduleSample.projectId || (moduleSample.language === 'lua' && nativeChat.source !== 'local')) {
                    setModuleSample(null);
                    setNotice('项目或编程方式已改变，请重新载入模块示例。');
                    return;
                }
                const current = moduleSample.language === 'lua' ? nativeChat.lua.editorCode : code;
                if (current !== moduleSample.base && !window.confirm('预览后代码已改变，仍用此示例替换当前草稿吗？'))
                    return;
                if (moduleSample.language === 'lua') {
                    nativeChat.lua.returnToDraft();
                    nativeChat.lua.setDraft(moduleSample.code);
                }
                else {
                    setCode(moduleSample.code);
                    setCodePreview(null);
                    setSelectedVersion(null);
                }
                setCheck(null);
                setModuleSample(null);
                setMobileTab('code');
                setNotice('已载入当前主控的模块示例，尚未保存或上传。请核对固件、端口和接线。');
            }}>替换当前代码</button></Dialog>}
    {filesDialog && <DeviceFilesDialog view={filesDialog} device={device.current} connected={connected} code={visibleCode} versions={fileVersions} disabled={!!busy} onClose={() => setFilesDialog(null)} onDownload={download} onHistory={() => { setFilesDialog(null); setVersions(fileVersions); }} folder={folder} board={boardInfo} componentIds={components} programReceipt={project && board === project.boardId && !dirty ? receipt ?? null : null} programRun={runSubmission} onChooseFolder={() => { setFilesDialog(null); setUploadAfterSave(false); openSave(); }} onLoad={loadCode}/>}
    {versions && <Dialog title="保存的代码版本" onClose={() => setVersions(null)}><p className="muted">选择一个版本放入编辑器，再保存会创建新版本。历史记录不会被覆盖。</p><button onClick={() => void action("重新载入", async () => { if (dirty && !window.confirm("重新载入会放弃本地草稿，请先导出需要保留的代码。继续吗？"))
        return; if (!project)
        return; const saved = await api<Project>("/projects/" + project.id); try {
        localStorage.removeItem("zhangwen-draft-" + project.id);
    }
    catch { /* unavailable */ } applyProject(saved, false); setVersions(null); })}>重新载入当前已保存项目</button>{versions.map(version => <article className="version-row" key={version.revision}><div><strong>V{version.revision} · {version.name || "MicroPython 程序"}</strong><small>{new Date(version.createdAt).toLocaleString()}</small></div><button onClick={() => { selectCodeVersion(version.revision); setVersions(null); }}>载入代码</button><button onClick={() => download(`main-v${version.revision}.py`, version.code)}><Download size={17}/>导出</button></article>)}</Dialog>}
  </div>;
}
