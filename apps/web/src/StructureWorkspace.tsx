import { StructureExports } from './StructureExports';
import { lazy, Suspense, useEffect, useRef, useState, type MutableRefObject } from 'react';
import { ArrowUp, Box, CircuitBoard, CheckCheck, ChevronRight, Download, FileCode2, FolderOpen, LoaderCircle, Maximize, Minimize, PanelLeftClose, PanelLeftOpen, Plus, Settings, SlidersHorizontal, Sparkles, X } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import type { CadProfile, CadResult, HardwarePlacement, LaserPreviewInput, StructureAction, StructureCatalog, StructureWorkspace as Workspace, TemplateParameterField } from '../../../packages/contracts/src/structure';
import { api, ApiError, bootstrap } from './api';
import { Dialog } from './Dialog';
import { CaseTemplatePicker } from './CaseTemplatePicker';
import { LaserPreview } from './LaserPreview';
import { readStructureDraft, structureDraftKey } from './structureDraft';
import { HardwarePlacementEditor, panelNames } from './HardwarePlacementEditor';
const StructurePreview = lazy(() => import('./StructurePreview').then(module => ({default: module.StructurePreview})));
const sizeText = (size?: {length_x: number; width_y: number; height_z: number}) => size ? `${size.length_x} × ${size.width_y} × ${size.height_z} mm` : '尺寸待补充';
import './structure.css';

const empty: Workspace = {revision: 0, versions: [], messages: []};
const labels: Record<string, string> = { width: '宽度 / 直径', depth: '深度', height: '高度', thickness: '厚度', scale: '整体缩放（倍）', tab_width: '目标榫宽', slot_spacing: '切缝横向间距', slot_bridge: '切缝桥宽', slot_rows: '纵向切缝段数', top_lid: '保留顶盖', bottom_lid: '保留底盖', inner_length_x: '内腔长度', inner_width_y: '内腔宽度', inner_height_z: '内腔高度', wall_thickness: '壁厚', floor_thickness: '底厚', corner_radius: '圆角半径', lid_thickness: '盖厚', lid_lip_height: '盖唇高度', lid_clearance: '盖缝间隙', min_wall_thickness: '最小壁厚', clearance: '装配间隙', screw_boss_diameter: '螺柱直径', screw_hole_diameter: '螺孔直径', usb_c_margin: 'USB开口余量', screen_window_margin: '屏幕开口余量', button_hole_margin: '按钮开口余量', vent_count: '散热孔数量', hardware_gap: '硬件间距', edge_clearance: '边缘间距' };
const groups: Record<string, string> = {design: '设计参数', box: '盒体尺寸', lid: '上盖', printing: '打印与固定', openings: '开孔', layout: '布局', hardware: '硬件位置偏移'};
const stageLabels: Record<string, string> = {requirement_analysis: '确认需求', confirmation: '确认尺寸', needs_input: '需要补充', artifact: '文件与导出'};
const flatten = (result?: CadResult, fields: TemplateParameterField[] = []): Record<string, number> => fields.length
  ? Object.fromEntries(fields.map(field => [field.key, result?.templateEdit?.parameterOverrides[field.key] ?? field.default]))
  : Object.assign({}, ...Object.values(result?.parameters ?? {}));
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);
function loadCatalog() {
  return api<StructureCatalog>('/structure/catalog');
}
function exportText(name: string, text: string) { const url = URL.createObjectURL(new Blob([text])); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

export function StructureWorkspace({ projectId, active, board, modules, designType = 'model', draft: input, onDraftChange: setInput, onSaveProject, onSettings, onBusy, onSaved, onHardwareDetail, onManageHardware, hardwareBlocked, hardwareDirty, onDirtyChange, saveDraftRef }: {
  projectId?: string; active: boolean; board?: HardwareSummary; modules: HardwareSummary[];
  designType?: 'model' | 'laser';
  draft: string; onDraftChange: (value: string) => void;
  onSaveProject: () => void; onSettings: () => void; onBusy: (value: boolean) => void; onSaved: (id: string) => Promise<void>;
  onHardwareDetail: (item: HardwareSummary) => void;
  onManageHardware: () => void; hardwareDirty: boolean; hardwareBlocked: boolean;
  onDirtyChange: (dirty: boolean) => void;
  saveDraftRef: MutableRefObject<(() => void) | null>;
}) {
  const [catalog, setCatalog] = useState<StructureCatalog | null>(null);
  const [catalogLoading, setCatalogLoading] = useState(false);
  const [catalogRevision, setCatalogRevision] = useState(0);
  const [workspace, setWorkspace] = useState<Workspace>(empty);
  const initialDraft = useRef(readStructureDraft(projectId,designType));
  const [selectedVersion, setSelectedVersion] = useState<number | null>(initialDraft.current?.sourceRevision ?? null);
  const [draftLoadedFor, setDraftLoadedFor] = useState<number | null>(null);
  const [parameterSourceRevision, setParameterSourceRevision] = useState<number | null>(initialDraft.current?.sourceRevision??null);
  const [draftConflict, setDraftConflict] = useState(false);
  const laser = designType === 'laser';
  const versions = workspace.versions.filter(v => (v.designType ?? 'model') === designType);
  const messages = workspace.messages.filter(m => (m.designType ?? 'model') === designType);
  const current = versions.find(v => v.revision === selectedVersion) ?? versions[0];
  const result = current?.result;
  const templateFields = catalog?.templates?.find(item => item.id === result?.builtinTemplate?.id && item.revision === result?.builtinTemplate?.revision)?.parameterFields ?? [];
  const parameterGroups = templateFields.length ? Object.fromEntries([...new Set(templateFields.map(field => field.group))]
    .map(group => [group, Object.fromEntries(templateFields.filter(field => field.group === group).map(field => [field.key, field.default]))])) : result?.parameters ?? {};
  const [selected, setSelected] = useState<string[]>([]);
  const [customProfiles, setCustomProfiles] = useState<Record<string, unknown>[]>([]);
  const [params, setParams] = useState<Record<string, number>>({});
  const [laserDraft, setLaserDraft] = useState<{key: string; result?: CadResult; error?: string} | null>(null);
  const [faces, setFaces] = useState<Record<string, 'base_floor' | 'lid_inner'>>({});
  const [rotations, setRotations] = useState<Record<string, number>>({});
  const [hardwarePlacements, setHardwarePlacements] = useState<HardwarePlacement[]>([]);
  const [busy, setBusy] = useState('');
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState(0);
  const [picker, setPicker] = useState(false);
  const [casePicker, setCasePicker] = useState(false);
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [custom, setCustom] = useState(false);
  const [profileText, setProfileText] = useState('');
  const [code, setCode] = useState(false);
  const [exports, setExports] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [parametersExpanded, setParametersExpanded] = useState(false);
  const inspector = useRef<HTMLElement>(null);
  const dimensionsSection = useRef<HTMLDetailsElement>(null);
  const revealParameters = () => { setParametersExpanded(value => !value); setTab('model'); if (dimensionsSection.current) dimensionsSection.current.open = true; requestAnimationFrame(() => { inspector.current?.focus(); if (inspector.current) inspector.current.scrollTop = 0; }); };
  const [tab, setTab] = useState('chat');
  const [elapsed, setElapsed] = useState(0);
  const log = useRef<HTMLDivElement>(null);
  const scope = useRef(projectId); scope.current = projectId;
  const hardwareRevisions = [board, ...modules].filter(Boolean).map(item => `${item?.componentId}:${item?.revision}`).join('|');

  useEffect(() => {
    let live = true;
    if (active) {
      setCatalogLoading(true);
      void loadCatalog().then(value => { if (live) setCatalog(value); })
        .catch(e => { if (live) setError(errorText(e)); })
        .finally(()=>{if(live)setCatalogLoading(false);});
    }
    return () => { live = false; };
  }, [active, hardwareRevisions, catalogRevision]);
  useEffect(()=>{
    const refresh=()=>setCatalogRevision(n=>n+1);
    window.addEventListener('hardware-mechanical-saved',refresh);
    return ()=>window.removeEventListener('hardware-mechanical-saved',refresh);
  },[]);
  useEffect(() => {
    if (!active || !projectId || busyRef.current) return;
    let live = true;
    // A read started before generation may finish after its new revision.
    void api<Workspace>(`/projects/${projectId}/structure`).then(value => { if (live) setWorkspace(current => value.revision > current.revision ? value : current); }).catch(e => { if (live) setError(errorText(e)); });
    return () => { live = false; };
  }, [active, projectId]);
  useEffect(() => {
    setWorkspace(empty); setSelected([]); setCustomProfiles([]); setError(''); setErrorStatus(0);
  }, [projectId]);
  useEffect(() => {
    if (!current || draftLoadedFor === current.revision) return;
    if (current.result.builtinTemplate && !catalog) return;
    const local=initialDraft.current;
    setSelected(local?.selected ?? current.selectedIds); setCustomProfiles(local?.customProfiles ?? current.customProfiles);
    setParams({...flatten(current.result, templateFields), ...(local ? Object.fromEntries(Object.entries(local.params).map(([k,v])=>[k,v===null?NaN:v])) : {})});
    setFaces(local?.faces ?? {}); setRotations(local?.rotations ?? {});
    setHardwarePlacements(local?.hardwarePlacements ?? current.result.designSpec?.hardwarePlacements ?? []);
    setDraftConflict(!!local && local.sourceRevision !== current.revision);
    setParameterSourceRevision(local?.sourceRevision??current.revision);
    setDraftLoadedFor(current.revision); initialDraft.current=null;
  }, [current, draftLoadedFor, catalog]);
  useEffect(() => { if (!busy) return; setElapsed(0); const timer = setInterval(() => setElapsed(n => n + 1), 1000); return () => clearInterval(timer); }, [busy]);
  useEffect(() => { log.current?.scrollTo({top: log.current.scrollHeight, behavior: 'auto'}); }, [workspace.messages.length, busy]);
  useEffect(() => { const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setFullscreen(false); }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, []);

  const act = async (action: StructureAction['action'], message = '', option = '', template?: StructureAction['template']) => {
    if (!projectId || busyRef.current) return;
    if (hardwareDirty) { setError('项目器件有未保存更改，请打开“项目器件”保存后继续。结构草稿已保留。'); return; }
    if (draftConflict) { setError('本地参数的来源版本已不存在，请先导出保留草稿，再明确载入当前参数。'); return; }
    if (result?.builtinTemplate && dimensionsDirty && ['analyze', 'revise', 'selected'].includes(action)) { setError('案例参数尚未应用，请先应用参数或恢复本版参数，再继续对话或切换案例。对话输入和参数草稿已保留。'); return; }
    const id = projectId; busyRef.current = true; onBusy(true); setError(''); setErrorStatus(0); setBusy(action === 'build' || action === 'parameters' ? '正在检查并构建模型' : action === 'selected' ? (catalog?.templates?.some(item => item.id === template) ? '正在生成模板3D预览' : '正在生成尺寸草案') : '正在处理结构需求');
    try {
      await bootstrap();
      const value = await api<Workspace>(`/projects/${id}/structure`, 'POST', {action, expectedRevision: workspace.revision,
        sourceRevision: current?.revision, message, selectedIds: selected, hardwareComponentIds: [board, ...modules].filter((item): item is HardwareSummary => !!item).map(item => item.componentId),
        hardwarePlacements: !template && (action === 'parameters' || action === 'build' || action === 'validate' || placementsDirty) ? hardwarePlacements : undefined,
        customProfiles, parameters: template ? {} : params, faces: template ? {} : faces, rotations: template ? {} : rotations, resolutionOptionId: option, designType, template} satisfies StructureAction);
      if (scope.current !== id) return;
      try {localStorage.removeItem(structureDraftKey(id,designType));} catch {setError('新结构版本已保存，但浏览器旧草稿未能清理，请核对来源版本。');}
      initialDraft.current=null; setDraftLoadedFor(null);
      setWorkspace(value); setSelectedVersion(null); if (['analyze', 'revise'].includes(action) && message === input) setInput(''); setTab(value.versions[0]?.result.status === 'artifact' ? 'model' : 'chat');
      await onSaved(id);
    } catch (e) { if (scope.current === id) { setError(errorText(e)); setErrorStatus(e instanceof ApiError ? e.status : 0); } }
    finally { busyRef.current = false; setBusy(''); onBusy(false); }
  };
  const selectedProfiles = selected.map(id => catalog?.profiles.find(p => p.id === id) ?? customProfiles.find(p => p.id === id) as unknown as CadProfile).filter(Boolean);
  const projectHardware = [...(board ? [board] : []), ...modules];
  const matchedIds = catalog?.profiles.filter(p => projectHardware.some(h => h.componentId === p.componentId)).map(p => p.id) ?? [];
  const missingParts = projectHardware.filter(h => !catalog?.profiles.some(p => p.componentId === h.componentId));
  const bom = result?.bom ?? result?.partial_bom ?? [];
  const placementsDirty = JSON.stringify(hardwarePlacements) !== JSON.stringify(result?.designSpec?.hardwarePlacements ?? []);
  const invalidPlacements = hardwarePlacements.some(p=>!Number.isFinite(p.x) || !Number.isFinite(p.y));
  const dimensionsDirty = JSON.stringify(params) !== JSON.stringify(flatten(result, templateFields)) || !!Object.keys(faces).length || !!Object.keys(rotations).length || placementsDirty;
  const savedParams = flatten(result, templateFields);
  const invalidParameters = Object.values(params).some(value => !Number.isFinite(value)) || templateFields.some(field => params[field.key] !== savedParams[field.key] && (params[field.key] < field.min || params[field.key] > field.max));
  const draftDirty = !!current && draftLoadedFor===current.revision && (draftConflict || dimensionsDirty || JSON.stringify(selected)!==JSON.stringify(current.selectedIds) || JSON.stringify(customProfiles)!==JSON.stringify(current.customProfiles));
  const preserveDraft = () => {
    if (!projectId || !current || draftLoadedFor!==current.revision) return;
    if (!draftDirty) {localStorage.removeItem(structureDraftKey(projectId,designType));return;}
    localStorage.setItem(structureDraftKey(projectId,designType),JSON.stringify({sourceRevision:parameterSourceRevision??current.revision,params,faces,rotations,selected,customProfiles,hardwarePlacements}));
  };
  saveDraftRef.current = preserveDraft;
  useEffect(() => { onDirtyChange(draftDirty || !!input.trim()); }, [draftDirty,input,onDirtyChange]);
  useEffect(() => {
    if (!current || draftLoadedFor!==current.revision) return;
    try { preserveDraft(); } catch { setError('浏览器无法保留结构草稿，请导出草稿以免丢失。'); }
  }, [projectId,designType,current?.revision,draftLoadedFor,parameterSourceRevision,params,faces,rotations,selected,customProfiles,hardwarePlacements,draftDirty]);
  const previewKey = JSON.stringify([projectId, workspace.revision, current?.revision, params, hardwarePlacements]);
  const draftPreview = laserDraft?.key === previewKey ? laserDraft : null;
  const previewDirty = laser && !draftConflict && dimensionsDirty && !!result?.designSpec && result.status !== 'needs_input';
  useEffect(() => {
    if (!active || !previewDirty || !projectId || !current || busy) return;
    let live = true;
    if (Object.values(params).some(value => !Number.isFinite(value)) || invalidPlacements) {
      setLaserDraft({key: previewKey, error: '请填写完整的有效尺寸。'});
      return;
    }
    const timer = setTimeout(() => {
      void api<CadResult>(`/projects/${projectId}/structure/preview`, 'POST', {
        expectedRevision: workspace.revision, sourceRevision: current.revision, parameters: params, hardwarePlacements,
      } satisfies LaserPreviewInput).then(value => {
        if (live) setLaserDraft({key: previewKey, result: value});
      }).catch(error => { if (live) setLaserDraft({key: previewKey, error: errorText(error)}); });
    }, 250);
    return () => { live = false; clearTimeout(timer); };
  }, [active, previewDirty, projectId, current, busy, previewKey, params, hardwarePlacements, invalidPlacements, workspace.revision]);
  const selectVersion = (revision: number) => { if (draftDirty && !window.confirm('参数尚未应用。切换将采用所选版本的参数，建议先导出草稿。继续吗？')) return; setSelectedVersion(revision); setDraftLoadedFor(null); setError(''); };
  const report = result?.requirement_analysis_report as {functions?: {name: string; matched_hardware_name?: string; library_status?: string}[]} | undefined;
  const addProfile = () => { try { const value: unknown = JSON.parse(profileText); if (!value || typeof value !== 'object' || Array.isArray(value) || !('id' in value) || typeof value.id !== 'string') throw new Error('需要包含id的硬件结构资料对象。'); if (catalog?.profiles.some(p => p.id === value.id)) throw new Error('此id属于已有结构资料，请为自定义资料使用新id。'); const p = value as Record<string, unknown>; setCustomProfiles(v => [...v.filter(x => x.id !== p.id), p]); setSelected(v => [...new Set([...v, p.id as string])]); setCustom(false); setError(''); } catch (e) { setError(errorText(e)); } };

  return <div className={`structure-surface ${collapsed ? 'structure-collapsed' : ''} ${fullscreen ? 'structure-fullscreen' : ''}`} hidden={!active}>
    <nav className="mobile-tabs" aria-label="结构工作区切换">{[['parts', '硬件与尺寸'], ['chat', '结构对话'], ['model', '模型']].map(([key, label]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>)}</nav>
    <main className="structure-workbench" aria-label="结构工程师工作区">
      <aside className={`panel structure-parts structure-mobile-${tab === 'parts' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Box size={17} />{laser ? "图纸模板" : "设计与硬件"}</h2><button aria-label="收起结构硬件" onClick={() => setCollapsed(true)}><PanelLeftClose size={17} /></button></div>
        <div className="structure-parts-scroll">
          <button className="structure-add" disabled={hardwareBlocked||!!busy} onClick={onManageHardware}><CircuitBoard size={17}/>{board?'调整主控与模块':'选择主控与模块'}</button>
          <details className="compact-disclosure structure-basic-templates"><summary>基础形状模板</summary><div className="structure-templates" aria-label={laser ? '激光图纸模板' : '无硬件3D模板'}>{(laser ? [['plate', '矩形挂牌'], ['round-tag', '圆形挂牌'], ['finger-box', '榫齿盒'], ['rounded-box', '圆角盒子'], ['panel-box', '胶合收纳盒板件']] : [['box', '开口收纳盒'], ['cup', '圆柱笔筒'], ['bracket', 'L形支架']]).map(([id, name]) => <button key={id} disabled={!projectId || !!busy} onClick={() => void act('selected', '使用' + name + '模板', '', id as StructureAction['template'])}>{name}<ChevronRight size={14} /></button>)}</div></details>
          {!laser && !!catalog?.templates?.length && <><h3 className="structure-template-heading">案例模板</h3><button className="structure-add" disabled={!!busy} onClick={() => setCasePicker(true)}><Plus size={17} />添加案例模板</button>{result?.builtinTemplate ? <div className="structure-selected structure-selected-case" aria-label="当前案例模板"><article>{result.builtinTemplate.image && <img src={result.builtinTemplate.image} alt="" />}<div><strong>{result.builtinTemplate.title}</strong><small>{sizeText(result.design_state?.enclosure_parameters.outer_box_size)}</small></div></article></div> : null}</>}
          {<>
          {!!matchedIds.length && <button className="structure-text-action" disabled={!!busy} onClick={() => setSelected(v => [...new Set([...v, ...matchedIds])].slice(0, 32))}>加入项目中的器件 · {matchedIds.length}</button>}
          {catalogLoading && <p role="status" className="structure-caption">正在更新尺寸与安装资料…</p>}
          {catalog && !catalogLoading && missingParts.length > 0 && <details open className="structure-missing"><summary>{missingParts.length} 个器件需要补充尺寸</summary><p className="structure-caption">请逐个补充外形和所需孔位/开口；未参与安装的器件可以不补。</p>{missingParts.map(h=><button key={h.componentId} disabled={!!busy} onClick={()=>onHardwareDetail(h)}>补充 {h.displayName}</button>)}</details>}
          <button className="structure-add" disabled={!!busy} onClick={() => {setPendingIds(selected); setPicker(true);}}><Plus size={17} />选择结构硬件</button>
          <details className="compact-disclosure"><summary>结构安装说明</summary><p className="structure-caption">无硬件作品可直接描述。主控与模块可在本页选择，三师共用已保存的选择。结构硬件用于确定参与安装的器件与尺寸。装配与加工前请核对实物。</p></details>
          <div className="structure-selected">{selectedProfiles.map(p => <article key={p.id}>{p.thumbnail_url ? <img src={p.thumbnail_url} alt="" /> : <Box size={19} />}<div><strong>{p.name ?? p.id}</strong><small>{sizeText(p.dimensions_mm)}</small></div><button aria-label={`移除 ${p.name ?? p.id}`} disabled={!!busy} onClick={() => setSelected(v => v.filter(x => x !== p.id))}><X size={14} /></button></article>)}</div>
          {!selected.length && <p className="structure-caption">还没有选择结构硬件</p>}
          {!laser && <><button className="structure-selected-build" disabled={!projectId || !selected.length || !!busy} onClick={() => void act('selected')}>按所选硬件生成草案<ChevronRight size={15} /></button></>}
          <details className="classroom-details"><summary>高级：导入尺寸资料</summary><p className="structure-caption">一般可从器件详情补充尺寸和孔位；已有 JSON 尺寸档案时，可在这里导入。</p><button className="structure-text-action" disabled={!!busy} onClick={() => setCustom(true)}>导入项目尺寸档案</button></details>
          {!!bom.length && <details><summary>本轮硬件清单 · {bom.length}</summary>{bom.map((p, i) => <p className="structure-bom" key={`${p.hardware_id}-${i}`}><span>{i + 1}</span>{p.name || catalog?.profiles.find(x => x.id === p.hardware_id)?.name || p.hardware_id}</p>)}</details>}
          </>}
        </div>
        <footer className="structure-side-foot">尺寸单位 mm</footer>
      </aside>
      <button className="structure-restore" aria-label="展开结构硬件" onClick={() => setCollapsed(false)}><PanelLeftOpen size={18} /></button>
      <section className={`panel ai-panel structure-chat structure-mobile-${tab === 'chat' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Sparkles size={18} />结构工程师</h2><button className="api-settings-entry" aria-label="结构设计 AI 设置" onClick={onSettings} disabled={!!busy}><Settings size={14} />AI 设置</button></div>
        <div className="messages" ref={log} role="log" aria-label="结构设计对话记录">
          {!projectId && <div className="structure-onboarding"><FolderOpen size={26} /><h3>在当前项目中开始设计</h3><p>先保存或新建项目，结构对话、尺寸与模型版本会保存在同一个项目中。</p><button className="primary" onClick={onSaveProject}>保存项目</button></div>}
          {projectId && !messages.length && <div className="conversation-empty"><span><Sparkles size={24} /></span><p>{laser ? '描述你要制作的平面图纸、材料与尺寸。' : '说说想做什么，我会结合项目器件和相关案例，先生成模型预览。尺寸不确定也可以开始。'}<br />也可在左侧选择模板。</p></div>}
          {messages.map(m => <article className={`message ${m.role}`} key={m.id}><strong>{m.role === 'user' ? '你' : laser ? '结构工程师 · 激光造物' : '结构工程师 · 3D造物'}</strong>{m.content.length > 450 ? <><p className="structure-message-text">{m.content.slice(0, 220)}…</p><details><summary>展开完整回复</summary><p className="structure-message-text">{m.content}</p></details></> : <p className="structure-message-text">{m.content}</p>}</article>)}
          {result && <section className="structure-next" aria-label="结构设计下一步"><span className={`structure-stage stage-${result.status}`}>{!laser && result.status === 'artifact' ? '模型预览' : stageLabels[result.status] ?? '结构检查'}</span><h3>{result.title ?? '本轮结构设计'}</h3>
            {report?.functions && <ul>{report.functions.slice(0, 6).map((f, i) => <li key={i}>{f.name} · {f.library_status === 'missing' ? '需要补充硬件资料' : f.matched_hardware_name || '已分析'}</li>)}</ul>}
            {!!result.questions?.length && <p>{result.questions[0]}</p>}
            {!laser && result.status === 'needs_input' && ['design_questions', 'template_questions'].includes(result.blocking_reason ?? '') && <><p>也可以先按合理假设出一版预览，再看着模型调整。</p><button disabled={!!busy} onClick={() => void act('revise', '请根据已有需求和已选模块，参考相近案例，先用可调整的合理默认尺寸生成模型预览；明确列出假设和待核对的硬件差异，不把精密孔位或实物适配写成已确认。')}>先生成方案预览</button></>}
            {result.status === 'requirement_analysis' && <button className="primary" disabled={!!busy} onClick={() => void act('confirm')}>确认需求，检查尺寸</button>}
            {result.status === 'confirmation' && <><p>{laser ? '确认材料尺寸与轮廓，再生成毫米图纸。' : '外形 ' + sizeText(result.design_state?.enclosure_parameters.outer_box_size)}</p><button className="primary" disabled={!!busy} onClick={() => void act('build')}>{laser ? '确认参数，生成图纸' : '确认参数，生成模型'}</button></>}
            {result.resolution_options?.filter(o => !['confirm_requirement_analysis'].includes(o.id)).slice(0, 5).map(o => <button disabled={!!busy} key={o.id} title={o.description} onClick={() => void act('revise', o.label || o.id, o.id)}>{o.label || o.title || o.id}</button>)}
            {result.status === 'artifact' && <p>{result.build?.message || (result.build?.status === 'artifact_exports' ? '模型已生成，可以查看、修改尺寸或导出。' : '建模未完成，请查看检查结果。')}</p>}
            {!laser && result.status === 'artifact' && <div className="structure-preview-basis" aria-label="预览依据与待确认项"><p>{result.builtinTemplate ? `参考案例：${result.builtinTemplate.title}。` : '已根据需求生成方案。'}先确认外形与布局，再调整细节；制作前需核对安装尺寸和活动空间。</p>{!!result.previewAssumptions?.length && <><strong>设计假设 · 尺寸以当前参数为准</strong><ul>{result.previewAssumptions.map((text, index) => <li key={index}>{text}</li>)}</ul></>}</div>}
            {current?.offline && <small>{result.designKind ? '按模板生成' : '按所选硬件设计外壳 · 未进行 AI 功能覆盖判断'}</small>}
          </section>}
          {busy && <p className="ai-progress" role="status"><LoaderCircle size={16} className="spin" />{busy} · {elapsed} 秒</p>}
        </div>
        {error && <p className="chat-error" role="alert">{error}{errorStatus === 409 ? <button disabled={!!busy} onClick={() => void api<Workspace>(`/projects/${projectId}/structure`).then(v => {setWorkspace(v); setSelectedVersion(null); setError('');}).catch(e => setError(errorText(e)))}>重新加载记录</button> : <>{input.trim() && <button disabled={!!busy} onClick={() => void act(current ? 'revise' : 'analyze', input)}>重试当前需求</button>}{errorStatus === 502 && <button disabled={!!busy} onClick={onSettings}>AI 设置</button>}</>}</p>}
        <form className="chat-form" onSubmit={e => {e.preventDefault(); void act(current ? 'revise' : 'analyze', input);}}><label className="sr-only" htmlFor="structure-message">发送给结构工程师</label><textarea id="structure-message" placeholder={laser ? "描述材料、厚度、图案轮廓与毫米尺寸…" : result?.builtinTemplate ? `基于${result.builtinTemplate.title}，描述要调整的尺寸、孔位、凹字或结构…` : "描述想做什么，先看模型预览；也可说明要改哪里…"} value={input} maxLength={4000} disabled={!projectId || !!busy} onChange={e => setInput(e.target.value)} onKeyDown={e => {if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing && input.trim()) {e.preventDefault(); void act(current ? 'revise' : 'analyze', input);}}} /><div><span>{laser ? "描述作品 → 确认尺寸 → 导出图纸" : result?.builtinTemplate ? "基于当前案例对话 → 检查并更新3D" : "描述需求 → 生成预览 → 确认与调整"}</span><button className="primary icon-button" aria-label="发送结构需求" disabled={!projectId || !input.trim() || !!busy}>{busy ? <LoaderCircle size={19} className="spin" /> : <ArrowUp size={20} />}</button></div></form>
      </section>
      <section className={`panel structure-model ${parametersExpanded ? 'parameters-expanded' : ''} structure-mobile-${tab === 'model' ? 'show' : 'hide'}`}>
        <div className="filebar"><span><Box size={16} />{laser ? "激光造物" : "3D造物"}</span><select aria-label="结构历史版本" disabled={!versions.length || !!busy} value={current?.revision ?? ''} onChange={e => selectVersion(Number(e.target.value))}>{!versions.length && <option value="">尚无版本</option>}{versions.map(v => <option key={v.revision} value={v.revision}>V{v.revision} · {v.name || v.result.title || v.prompt.slice(0, 24)} · {stageLabels[v.result.status] ?? '检查结果'}</option>)}</select><span className="filebar-space" /><button disabled={!current || !!busy} aria-pressed={parametersExpanded} onClick={revealParameters}><SlidersHorizontal size={15} />参数</button><button disabled={!(result?.design_state || result?.designSpec) || !!busy || ((laser || !!result?.builtinTemplate) && dimensionsDirty)} onClick={() => void act('validate')}><CheckCheck size={15} />检查</button><button aria-label={fullscreen ? '退出模型全屏' : '模型全屏'} onClick={() => setFullscreen(v => !v)}>{fullscreen ? <Minimize size={16} /> : <Maximize size={16} />}</button><button disabled={!result?.exports?.length || ((laser || !!result?.builtinTemplate) && dimensionsDirty) || !!busy} onClick={() => setExports(true)}><Download size={16} />导出</button></div>
        {active && laser ? <><LaserPreview result={previewDirty && draftPreview?.result ? draftPreview.result : result} />{previewDirty && <p className="structure-caption laser-draft-status" role="status">{draftPreview?.error ? `${draftPreview.error} 当前仍显示 V${current?.revision} 已应用图纸。` : draftPreview?.result ? '参数草案预览 · 尚未应用；应用参数后可导出新图纸。' : `正在更新参数预览；当前仍显示 V${current?.revision} 已应用图纸。`}</p>}</> : active && <Suspense fallback={<p className="structure-caption" role="status">正在准备模型视图区…</p>}><StructurePreview result={result} /></Suspense>}
        <section ref={inspector} tabIndex={-1} className="structure-inspector" aria-label="结构参数与检查">
          {draftDirty && <div className="structure-draft-note" role="status"><p>结构草稿已在本浏览器保留 · 基于 V{parameterSourceRevision} · 尚未应用到模型</p><button onClick={()=>exportText('structure-draft.json',JSON.stringify({sourceRevision:parameterSourceRevision,params,faces,rotations,selected,customProfiles,hardwarePlacements},null,2))}>导出参数草稿</button>{!draftConflict && dimensionsDirty && <button disabled={!!busy} onClick={()=>{if(!window.confirm("恢复当前已保存版本的参数？尚未应用的参数修改将放弃，对话输入保留。"))return;setParams(flatten(result, templateFields));setFaces({});setRotations({});setHardwarePlacements(result?.designSpec?.hardwarePlacements??[]);setError('');}}>恢复本版参数</button>}{draftConflict && <p role="alert">草稿来源版本已不可用，请先导出保留，再选择是否放弃本地参数。</p>}{draftConflict && <button onClick={()=>{setParameterSourceRevision(current?.revision??null);setParams(flatten(result, templateFields));setFaces({});setRotations({});setHardwarePlacements(result?.designSpec?.hardwarePlacements??[]);setSelected(current?.selectedIds??[]);setCustomProfiles(current?.customProfiles??[]);setDraftConflict(false);if(projectId)localStorage.removeItem(structureDraftKey(projectId,designType));}}>放弃本地参数，载入当前版本</button>}</div>}
          <details ref={dimensionsSection} open><summary><SlidersHorizontal size={15} />尺寸与布局{dimensionsDirty && <small>未应用</small>}</summary>
          {result?.builtinTemplate && <div className="structure-template-info"><strong>{result.builtinTemplate.title} · 案例改造</strong><p>{sizeText(result.design_state?.enclosure_parameters.outer_box_size)}</p><details><summary>查看案例说明与适配提醒</summary><p>{templateFields.length ? "修改参数后点击应用，生成新版本；也可通过对话改孔位和结构。" : "此案例可通过对话修改尺寸、孔位和结构。"}</p>{result.builtinTemplate.notes.map(note => <p key={note}>{note}</p>)}<small>模板修订 {result.builtinTemplate.revision}；修改后需重新核对实物。</small></details>{result.templateEdit?.summary && <p>{result.templateEdit.summary}</p>}{!!Object.keys(result.templateEdit?.parameterOverrides ?? {}).length && <p aria-label="模板参数修改">已调整 {Object.keys(result.templateEdit?.parameterOverrides ?? {}).length} 项模板尺寸</p>}{result.templateEdit?.partOperations.map(part => <p key={part.partId}>{result.templateParts?.find(item => item.id === part.partId)?.label ?? '打印部件'} · {part.operations.length} 项结构改造</p>)}{result.status === 'needs_input' && <p>等待补充说明，当前显示此前保留的模型。</p>}</div>}
          {result?.designTemplate === 'rounded-box' && <p className="structure-caption">宽度、深度、高度均为盒子外尺寸。{result.designSpec?.roundedBox?.pattern_version === 2 ? '四角切缝交错接到上下边缘，保留中间连接桥。' : '旧版切缝未接通上下边缘，应用参数可生成修正版。'}接缝需胶合，材料与榫接须先试切。刀缝在加工软件中补偿。</p>}{!Object.keys(parameterGroups).length && <p className="structure-caption">{current?"本版尚未生成尺寸参数。可继续说明需求或先生成方案预览，也可选择案例。":"生成预览后可在这里调整尺寸。"}</p>}
          {Object.entries(parameterGroups).map(([group, values]) => <fieldset disabled={!!busy} key={group}><legend>{groups[group] || group}</legend><div className="structure-param-grid">{Object.keys(values).map(key => ['top_lid', 'bottom_lid'].includes(key) ? <label className="structure-param-toggle" key={key}><input type="checkbox" checked={params[key] === 1} onChange={e => setParams(v => ({...v, [key]: e.target.checked ? 1 : 0}))} />{labels[key]}</label> : <label key={key}>{templateFields.find(field => field.key === key)?.label ?? labels[key] ?? key}{templateFields.find(field => field.key === key)?.unit && <small>{templateFields.find(field => field.key === key)?.unit}</small>}<input aria-label={templateFields.find(field => field.key === key)?.label ?? labels[key] ?? key} type="number" min={templateFields.find(field => field.key === key)?.min ?? (key.endsWith('_offset_x') || key.endsWith('_offset_y') ? -500 : key === 'scale' ? .1 : 0)} max={templateFields.find(field => field.key === key)?.max ?? (key === 'scale' ? 5 : 1000)} step={templateFields.find(field => field.key === key)?.step ?? (['vent_count', 'slot_rows'].includes(key) ? 1 : .1)} value={Number.isFinite(params[key]) ? params[key] : ''} onChange={e => setParams(v => ({...v, [key]: e.target.value === '' ? NaN : Number(e.target.value)}))} /></label>)}</div></fieldset>)}
          {!!result?.design_state?.layout_plan?.hardware_transforms.length && <fieldset disabled={!!busy}><legend>安装面与朝向</legend>{result.design_state.layout_plan.hardware_transforms.map((h, i) => <div className="structure-placement" key={`${h.hardware_id}-${i}`}><strong>{h.name}</strong><label>安装面<select value={faces[h.hardware_id] ?? h.mount_surface ?? 'base_floor'} onChange={e => setFaces(v => ({...v, [h.hardware_id]: e.target.value as 'base_floor' | 'lid_inner'}))}><option value="base_floor">底壳内侧</option><option value="lid_inner">上盖内侧</option></select></label><label>平面旋转<select value={rotations[h.hardware_id] ?? h.layout_rotation_deg ?? 0} onChange={e => setRotations(v => ({...v, [h.hardware_id]: Number(e.target.value)}))}>{[0, 90, 180, 270].map(n => <option key={n} value={n}>{n}°</option>)}</select></label></div>)}</fieldset>}
          {invalidParameters && <p className="structure-caption" role="alert">请填写有效数值，并保持在各参数的允许范围内。</p>}{(result?.design_state || result?.designSpec) && <button className="primary" disabled={!!busy || result.status === 'needs_input' || invalidPlacements || invalidParameters} onClick={() => void act(result.status === 'confirmation' ? 'build' : 'parameters')}>{result.builtinTemplate ? (dimensionsDirty ? '应用参数，生成新版本' : '重新生成当前模型') : result.status === 'confirmation' ? (laser ? '应用参数并生成图纸' : '应用参数并生成模型') : '应用参数，重新生成'}</button>}
        </details>
          {laser && (result?.designSpec?.roundedBox || result?.designSpec?.fingerBox) && <>
            <HardwarePlacementEditor hardware={projectHardware} profiles={catalog?.profiles??[]} placements={hardwarePlacements} onChange={setHardwarePlacements} onDetail={onHardwareDetail} spec={result.designSpec} disabled={!!busy || catalogLoading}/>
            <button className="primary" disabled={!!busy || result.status==='needs_input' || invalidPlacements || Object.values(params).some(v=>!Number.isFinite(v))} onClick={()=>void act(result.status==='confirmation'?'build':'parameters')}>应用安装布局，生成图纸</button>
          </>}
          {!!result?.hardwareInstallations?.length && <details className="hardware-installation-report"><summary>{result.status==='needs_input'?'上一版安装清单':'本版安装清单'} · {result.hardwareInstallations.length} 个器件</summary>{result.hardwareInstallations.map(i=><article key={i.placement.componentId}><strong>{i.name}</strong><p>{panelNames[i.placement.panel]} · 中心 {i.placement.x}, {i.placement.y} mm · {i.placement.rotation}° · {i.cutCount} 个切口</p><p>{i.note}</p><details><summary>所用尺寸来源记录</summary><small>资料修订：{i.placement.skillRevision}</small><pre>{String(i.source.documentation??'').split('<!-- web-mechanical-notes -->')[1]?.split('<!-- /web-mechanical-notes -->')[0] ?? '原模块机械档案；完整记录见导出安装清单。'}</pre></details></article>)}</details>}
        <details><summary><CheckCheck size={15} />检查结果 · {result?.checks?.length ?? 0}</summary>{result?.checks?.map((c, i) => <p className={`structure-check check-${c.status}`} key={i}><strong>{c.status === 'pass' ? '通过' : c.status === 'fail' ? '未通过' : c.status === 'pending' ? '待验证' : '提示'}</strong>{c.message}</p>)}<p className="structure-caption">电脑检查通过后，仍需试装并检查尺寸、活动空间和强度。</p></details><details className="classroom-details"><summary>高级：建模过程</summary><button disabled={!result?.cadquery_code} onClick={() => setCode(true)}><FileCode2 size={15} />查看建模代码</button></details></section>
      </section>
    </main>
    {casePicker && <CaseTemplatePicker templates={catalog?.templates ?? []} currentId={result?.builtinTemplate?.id} canAdd={!!projectId && !busy} onClose={() => setCasePicker(false)} onAdd={item => { setCasePicker(false); void act('selected', '使用' + item.title + '模板', '', item.id); }} />}
    {picker && <Dialog title="选择结构硬件" onClose={() => setPicker(false)} className="structure-picker"><p className="muted">这些资料提供几何尺寸与安装规则，用于选择参与安装的器件。需要调整主控或模块时，使用本页的“选择主控与模块”或“调整主控与模块”；已保存的选择三师共用。</p><label className="field">搜索结构硬件<input data-dialog-autofocus value={search} onChange={e => setSearch(e.target.value)} placeholder="名称、型号或功能" /></label><div className="structure-profile-grid">{catalog?.profiles.filter(p => `${p.name} ${p.id} ${p.roles.join(' ')}`.toLowerCase().includes(search.toLowerCase())).map(p => <label key={p.id}><input type="checkbox" checked={pendingIds.includes(p.id)} disabled={!pendingIds.includes(p.id) && pendingIds.length >= 32} onChange={e => setPendingIds(v => e.target.checked ? [...v, p.id] : v.filter(x => x !== p.id))} />{p.thumbnail_url ? <img src={p.thumbnail_url} alt="" loading="lazy" /> : <Box size={22} />}<strong>{p.name}</strong><small>{sizeText(p.dimensions_mm)}</small></label>)}</div><div className="structure-dialog-actions"><span>已选择 {pendingIds.length} 个</span><button onClick={() => setPicker(false)}>取消</button><button className="primary" onClick={() => {setSelected(pendingIds); setPicker(false);}}>完成选择</button></div></Dialog>}
    {custom && <Dialog title="补充结构尺寸资料" onClose={() => setCustom(false)}><p className="muted">粘贴原 CAD 格式的 JSON profile，至少含 id、name、dimensions_mm、mounting、opening、keepouts、cad_reference。缺少孔位会阻止建模。资料随当前项目版本保存。</p><textarea className="structure-profile-input" aria-label="自定义结构资料 JSON" value={profileText} onChange={e => setProfileText(e.target.value)} placeholder={'{"id":"my_module","name":"我的模块","dimensions_mm":{"length_x":30,"width_y":20,"height_z":8}}'} />{error && <p role="alert" className="settings-error">{error}</p>}<button className="primary" onClick={addProfile}>加入资料</button></Dialog>}
    {code && <Dialog title="建模代码" onClose={() => setCode(false)}><p className="muted">代码由结构工具根据校验后的参数生成，不直接执行 AI 返回的代码。</p><pre className="candidate-code">{result?.cadquery_code}</pre><button onClick={() => exportText('cadquery.py', result?.cadquery_code ?? '')}><Download size={16} />下载代码</button></Dialog>}
    {exports && <Dialog title="导出结构文件" onClose={() => setExports(false)}><StructureExports files={result?.exports??[]} laser={laser}/></Dialog>}
  </div>;
}
