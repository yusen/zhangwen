import { lazy, Suspense, useEffect, useRef, useState } from 'react';
import { ArrowUp, Box, CheckCheck, ChevronRight, Download, FileCode2, FolderOpen, LoaderCircle, Maximize, Minimize, PanelLeftClose, PanelLeftOpen, Plus, Settings, SlidersHorizontal, Sparkles, X } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import type { CadProfile, CadResult, StructureAction, StructureCatalog, StructureWorkspace as Workspace } from '../../../packages/contracts/src/structure';
import { api, ApiError, bootstrap } from './api';
import { Dialog } from './Dialog';
import { LaserPreview } from './LaserPreview';
const StructurePreview = lazy(() => import('./StructurePreview').then(module => ({default: module.StructurePreview})));
const sizeText = (size?: {length_x: number; width_y: number; height_z: number}) => size ? `${size.length_x} × ${size.width_y} × ${size.height_z} mm` : '尺寸待补充';
import './structure.css';

const empty: Workspace = {revision: 0, versions: [], messages: []};
const labels: Record<string, string> = { width: '宽度 / 直径', depth: '深度', height: '高度', thickness: '厚度', scale: '整体缩放（倍）', tab_width: '目标榫宽', slot_spacing: '切缝横向间距', slot_bridge: '切缝桥宽', slot_rows: '纵向切缝段数', top_lid: '保留顶盖', bottom_lid: '保留底盖', inner_length_x: '内腔长度', inner_width_y: '内腔宽度', inner_height_z: '内腔高度', wall_thickness: '壁厚', floor_thickness: '底厚', corner_radius: '圆角半径', lid_thickness: '盖厚', lid_lip_height: '盖唇高度', lid_clearance: '盖缝间隙', min_wall_thickness: '最小壁厚', clearance: '装配间隙', screw_boss_diameter: '螺柱直径', screw_hole_diameter: '螺孔直径', usb_c_margin: 'USB开口余量', screen_window_margin: '屏幕开口余量', button_hole_margin: '按钮开口余量', vent_count: '散热孔数量', hardware_gap: '硬件间距', edge_clearance: '边缘间距' };
const groups: Record<string, string> = {design: '设计参数', box: '盒体尺寸', lid: '上盖', printing: '打印与固定', openings: '开孔', layout: '布局', hardware: '硬件位置偏移'};
const stageLabels: Record<string, string> = {requirement_analysis: '确认需求', confirmation: '确认尺寸', needs_input: '需要补充', artifact: '文件与导出'};
const flatten = (result?: CadResult): Record<string, number> => Object.assign({}, ...Object.values(result?.parameters ?? {}));
const errorText = (error: unknown) => error instanceof Error ? error.message : String(error);
let catalogRequest: Promise<StructureCatalog> | undefined;
function loadCatalog() {
  return catalogRequest ??= api<StructureCatalog>('/structure/catalog').catch(error => { catalogRequest = undefined; throw error; });
}
function exportText(name: string, text: string) { const url = URL.createObjectURL(new Blob([text])); const a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000); }

export function StructureWorkspace({ projectId, active, board, modules, designType = 'model', draft: input, onDraftChange: setInput, onSaveProject, onSettings, onBusy, onSaved }: {
  projectId?: string; active: boolean; board?: HardwareSummary; modules: HardwareSummary[];
  designType?: 'model' | 'laser';
  draft: string; onDraftChange: (value: string) => void;
  onSaveProject: () => void; onSettings: () => void; onBusy: (value: boolean) => void; onSaved: (id: string) => Promise<void>;
}) {
  const [catalog, setCatalog] = useState<StructureCatalog | null>(null);
  const [workspace, setWorkspace] = useState<Workspace>(empty);
  const [selectedVersion, setSelectedVersion] = useState<number | null>(null);
  const laser = designType === 'laser';
  const versions = workspace.versions.filter(v => (v.designType ?? 'model') === designType);
  const messages = workspace.messages.filter(m => (m.designType ?? 'model') === designType);
  const current = versions.find(v => v.revision === selectedVersion) ?? versions[0];
  const result = current?.result;
  const [selected, setSelected] = useState<string[]>([]);
  const [customProfiles, setCustomProfiles] = useState<Record<string, unknown>[]>([]);
  const [params, setParams] = useState<Record<string, number>>({});
  const [faces, setFaces] = useState<Record<string, 'base_floor' | 'lid_inner'>>({});
  const [rotations, setRotations] = useState<Record<string, number>>({});
  const [busy, setBusy] = useState('');
  const busyRef = useRef(false);
  const [error, setError] = useState('');
  const [errorStatus, setErrorStatus] = useState(0);
  const [picker, setPicker] = useState(false);
  const [pendingIds, setPendingIds] = useState<string[]>([]);
  const [search, setSearch] = useState('');
  const [custom, setCustom] = useState(false);
  const [profileText, setProfileText] = useState('');
  const [code, setCode] = useState(false);
  const [exports, setExports] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [fullscreen, setFullscreen] = useState(false);
  const [tab, setTab] = useState('chat');
  const [elapsed, setElapsed] = useState(0);
  const log = useRef<HTMLDivElement>(null);
  const scope = useRef(projectId); scope.current = projectId;

  useEffect(() => { let live = true; if (active && !catalog) void loadCatalog().then(value => { if (live) setCatalog(value); }).catch(e => { if (live) setError(errorText(e)); }); return () => { live = false; }; }, [active, catalog]);
  useEffect(() => {
    if (!active || !projectId || busyRef.current) return;
    let live = true;
    // A read started before generation may finish after its new revision.
    void api<Workspace>(`/projects/${projectId}/structure`).then(value => { if (live) setWorkspace(current => value.revision >= current.revision ? value : current); }).catch(e => { if (live) setError(errorText(e)); });
    return () => { live = false; };
  }, [active, projectId]);
  useEffect(() => {
    setWorkspace(empty); setSelectedVersion(null); setSelected([]); setCustomProfiles([]); setError(''); setErrorStatus(0);
  }, [projectId]);
  useEffect(() => { if (current) { setSelected(current.selectedIds); setCustomProfiles(current.customProfiles); setParams(flatten(current.result)); setFaces({}); setRotations({}); } }, [current]);
  useEffect(() => { if (!busy) return; setElapsed(0); const timer = setInterval(() => setElapsed(n => n + 1), 1000); return () => clearInterval(timer); }, [busy]);
  useEffect(() => { log.current?.scrollTo({top: log.current.scrollHeight, behavior: 'auto'}); }, [workspace.messages.length, busy]);
  useEffect(() => { const key = (e: KeyboardEvent) => { if (e.key === 'Escape') setFullscreen(false); }; window.addEventListener('keydown', key); return () => window.removeEventListener('keydown', key); }, []);

  const act = async (action: StructureAction['action'], message = '', option = '', template?: StructureAction['template']) => {
    if (!projectId || busyRef.current) return;
    const id = projectId; busyRef.current = true; onBusy(true); setError(''); setErrorStatus(0); setBusy(action === 'build' || action === 'parameters' ? '正在检查并构建模型' : action === 'selected' ? '正在生成尺寸草案' : '正在处理结构需求');
    try {
      await bootstrap();
      const value = await api<Workspace>(`/projects/${id}/structure`, 'POST', {action, expectedRevision: workspace.revision,
        sourceRevision: current?.revision, message, selectedIds: selected, customProfiles, parameters: template ? {} : params, faces, rotations, resolutionOptionId: option, designType, template} satisfies StructureAction);
      if (scope.current !== id) return;
      setWorkspace(value); setSelectedVersion(null); setInput(''); setTab('chat');
      await onSaved(id);
    } catch (e) { if (scope.current === id) { setError(errorText(e)); setErrorStatus(e instanceof ApiError ? e.status : 0); } }
    finally { busyRef.current = false; setBusy(''); onBusy(false); }
  };
  const selectedProfiles = selected.map(id => catalog?.profiles.find(p => p.id === id) ?? customProfiles.find(p => p.id === id) as unknown as CadProfile).filter(Boolean);
  const projectHardware = [...(board ? [board] : []), ...modules];
  const matchedIds = catalog?.profiles.filter(p => projectHardware.some(h => h.componentId === p.componentId)).map(p => p.id) ?? [];
  const missingParts = projectHardware.filter(h => !catalog?.profiles.some(p => p.componentId === h.componentId));
  const bom = result?.bom ?? result?.partial_bom ?? [];
  const dimensionsDirty = JSON.stringify(params) !== JSON.stringify(flatten(result)) || !!Object.keys(faces).length || !!Object.keys(rotations).length;
  const selectVersion = (revision: number) => { if (dimensionsDirty && !window.confirm('尺寸参数尚未应用，切换会恢复所选版本的参数。继续吗？')) return; setSelectedVersion(revision); setError(''); };
  const report = result?.requirement_analysis_report as {functions?: {name: string; matched_hardware_name?: string; library_status?: string}[]} | undefined;
  const addProfile = () => { try { const value: unknown = JSON.parse(profileText); if (!value || typeof value !== 'object' || Array.isArray(value) || !('id' in value) || typeof value.id !== 'string') throw new Error('需要包含id的硬件结构资料对象。'); if (catalog?.profiles.some(p => p.id === value.id)) throw new Error('此id属于已有结构资料，请为自定义资料使用新id。'); const p = value as Record<string, unknown>; setCustomProfiles(v => [...v.filter(x => x.id !== p.id), p]); setSelected(v => [...new Set([...v, p.id as string])]); setCustom(false); setError(''); } catch (e) { setError(errorText(e)); } };

  return <div className={`structure-surface ${collapsed ? 'structure-collapsed' : ''} ${fullscreen ? 'structure-fullscreen' : ''}`} hidden={!active}>
    <nav className="mobile-tabs" aria-label="结构工作区切换">{[['parts', '硬件与尺寸'], ['chat', '结构对话'], ['model', '模型']].map(([key, label]) => <button key={key} className={tab === key ? 'active' : ''} onClick={() => setTab(key)}>{label}</button>)}</nav>
    <main className="structure-workbench" aria-label="结构设计师工作区">
      <aside className={`panel structure-parts structure-mobile-${tab === 'parts' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Box size={17} />{laser ? "图纸模板" : "设计与硬件"}</h2><button aria-label="收起结构硬件" onClick={() => setCollapsed(true)}><PanelLeftClose size={17} /></button></div>
        <div className="structure-parts-scroll">{!laser && <div className="structure-project-context"><small>当前工程配置</small><strong>{board?.displayName ?? '未选择主控'}</strong><span>{modules.length} 个模块</span></div>}
          <p className="structure-caption">{laser ? '先描述材料、厚度与轮廓，或从模板开始。' : '可以直接描述无硬件作品；需要安装电路时再加入结构硬件。'}</p>
          <div className="structure-templates" aria-label={laser ? '激光图纸模板' : '无硬件3D模板'}>{(laser ? [['plate', '矩形挂牌'], ['round-tag', '圆形挂牌'], ['finger-box', '榫齿盒'], ['rounded-box', '圆角盒子'], ['panel-box', '胶合收纳盒板件']] : [['box', '开口收纳盒'], ['cup', '圆柱笔筒'], ['bracket', 'L形支架']]).map(([id, name]) => <button key={id} disabled={!projectId || !!busy} onClick={() => void act('selected', '使用' + name + '模板', '', id as StructureAction['template'])}>{name}<ChevronRight size={14} /></button>)}</div>
          {!laser && <>
          {!!matchedIds.length && <button className="structure-text-action" disabled={!!busy} onClick={() => setSelected(v => [...new Set([...v, ...matchedIds])].slice(0, 32))}>加入工程中匹配的硬件 · {matchedIds.length}</button>}
          {catalog && missingParts.length > 0 && <details className="structure-missing"><summary>{missingParts.length} 个工程硬件缺结构资料</summary><p className="structure-caption">{missingParts.map(h => h.displayName).join('、')}。请补充尺寸、安装孔与开孔资料。</p></details>}
          <button className="structure-add" disabled={!!busy} onClick={() => {setPendingIds(selected); setPicker(true);}}><Plus size={17} />选择结构硬件</button>
          <div className="structure-selected">{selectedProfiles.map(p => <article key={p.id}>{p.thumbnail_url ? <img src={p.thumbnail_url} alt="" /> : <Box size={19} />}<div><strong>{p.name ?? p.id}</strong><small>{sizeText(p.dimensions_mm)}</small></div><button aria-label={`移除 ${p.name ?? p.id}`} disabled={!!busy} onClick={() => setSelected(v => v.filter(x => x !== p.id))}><X size={14} /></button></article>)}</div>
          {!selected.length && <p className="structure-caption">还没有选择结构硬件</p>}
          <button className="structure-selected-build" disabled={!projectId || !selected.length || !!busy} onClick={() => void act('selected')}>按所选硬件生成草案<ChevronRight size={15} /></button><p className="structure-caption">此方式仅做选定硬件外壳，无需 AI。</p>
          <button className="structure-text-action" disabled={!!busy} onClick={() => setCustom(true)}>补充自定义结构资料</button>
          {!!bom.length && <details open><summary>本轮硬件清单 · {bom.length}</summary>{bom.map((p, i) => <p className="structure-bom" key={`${p.hardware_id}-${i}`}><span>{i + 1}</span>{p.name || catalog?.profiles.find(x => x.id === p.hardware_id)?.name || p.hardware_id}</p>)}</details>}
          </>}
        </div>
        <footer className="structure-side-foot">尺寸单位 mm<br />装配与加工前需核对实物</footer>
      </aside>
      <button className="structure-restore" aria-label="展开结构硬件" onClick={() => setCollapsed(false)}><PanelLeftOpen size={18} /></button>
      <section className={`panel ai-panel structure-chat structure-mobile-${tab === 'chat' ? 'show' : 'hide'}`}>
        <div className="panel-head"><h2><Sparkles size={18} />掌问 AI</h2><button className="api-settings-entry" aria-label="结构设计 API 设置" onClick={onSettings} disabled={!!busy}><Settings size={14} />API 设置</button></div>
        <div className="messages" ref={log} role="log" aria-label="结构设计对话记录">
          {!projectId && <div className="structure-onboarding"><FolderOpen size={26} /><h3>在当前项目中开始设计</h3><p>先保存或新建项目，结构对话、尺寸与模型版本会保存在同一个项目中。</p><button className="primary" onClick={onSaveProject}>保存项目</button></div>}
          {projectId && !messages.length && <div className="conversation-empty"><span><Sparkles size={24} /></span><p>{laser ? '描述你要制作的平面图纸、材料与尺寸。' : '描述你想做的3D作品，不添加硬件也可以开始。'}<br />或在左侧选择模板，直接生成草案。</p></div>}
          {messages.map(m => <article className={`message ${m.role}`} key={m.id}><strong>{m.role === 'user' ? '你' : laser ? '掌问 · 激光造物' : '掌问 · 3D造物'}</strong>{m.content.length > 450 ? <><p className="structure-message-text">{m.content.slice(0, 220)}…</p><details><summary>展开完整回复</summary><p className="structure-message-text">{m.content}</p></details></> : <p className="structure-message-text">{m.content}</p>}</article>)}
          {result && <section className="structure-next" aria-label="结构设计下一步"><span className={`structure-stage stage-${result.status}`}>{stageLabels[result.status] ?? '结构检查'}</span><h3>{result.title ?? '本轮结构设计'}</h3>
            {report?.functions && <ul>{report.functions.slice(0, 6).map((f, i) => <li key={i}>{f.name} · {f.library_status === 'missing' ? '需要补充硬件资料' : f.matched_hardware_name || '已分析'}</li>)}</ul>}
            {!!result.questions?.length && <p>{result.questions[0]}</p>}
            {result.status === 'requirement_analysis' && <button className="primary" disabled={!!busy} onClick={() => void act('confirm')}>确认需求，检查尺寸</button>}
            {result.status === 'confirmation' && <><p>{laser ? '确认材料尺寸与轮廓，再生成毫米图纸。' : '外形 ' + sizeText(result.design_state?.enclosure_parameters.outer_box_size)}</p><button className="primary" disabled={!!busy} onClick={() => void act('build')}>{laser ? '确认参数，生成图纸' : '确认参数，生成模型'}</button></>}
            {result.resolution_options?.filter(o => !['confirm_requirement_analysis'].includes(o.id)).slice(0, 5).map(o => <button disabled={!!busy} key={o.id} title={o.description} onClick={() => void act('revise', o.label || o.id, o.id)}>{o.label || o.title || o.id}</button>)}
            {result.status === 'artifact' && <p>{result.build?.message || (result.build?.status === 'artifact_exports' ? '真实模型已生成，可以预览、调参或导出。' : '建模未完成，请查看检查结果。')}</p>}
            {current?.offline && <small>{result.designKind ? '按确定性模板生成，未调用AI' : '按所选硬件设计外壳 · 未进行 AI 功能覆盖判断'}</small>}
          </section>}
          {busy && <p className="ai-progress" role="status"><LoaderCircle size={16} className="spin" />{busy} · {elapsed} 秒</p>}
        </div>
        {error && <p className="chat-error" role="alert">{error}{errorStatus === 409 ? <button disabled={!!busy} onClick={() => void api<Workspace>(`/projects/${projectId}/structure`).then(v => {setWorkspace(v); setSelectedVersion(null); setError('');}).catch(e => setError(errorText(e)))}>重新加载记录</button> : <>{input.trim() && <button disabled={!!busy} onClick={() => void act(current ? 'revise' : 'analyze', input)}>重试当前需求</button>}{errorStatus === 502 && <button disabled={!!busy} onClick={onSettings}>API 设置</button>}</>}</p>}
        <form className="chat-form" onSubmit={e => {e.preventDefault(); void act(current ? 'revise' : 'analyze', input);}}><label className="sr-only" htmlFor="structure-message">发送给结构设计师</label><textarea id="structure-message" placeholder={laser ? "描述材料、厚度、图案轮廓与毫米尺寸…" : "描述3D作品与毫米尺寸，或说明希望修改的地方…"} value={input} maxLength={4000} disabled={!projectId || !!busy} onChange={e => setInput(e.target.value)} onKeyDown={e => {if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !e.nativeEvent.isComposing && input.trim()) {e.preventDefault(); void act(current ? 'revise' : 'analyze', input);}}} /><div><span>{laser ? "独立激光对话 → 确认尺寸 → 导出图纸" : "独立3D对话 → 确认尺寸 → 生成模型"}</span><button className="primary icon-button" aria-label="发送结构需求" disabled={!projectId || !input.trim() || !!busy}>{busy ? <LoaderCircle size={19} className="spin" /> : <ArrowUp size={20} />}</button></div></form>
      </section>
      <section className={`panel structure-model structure-mobile-${tab === 'model' ? 'show' : 'hide'}`}>
        <div className="filebar"><span><Box size={16} />{laser ? "激光造物" : "3D造物"}</span><select aria-label="结构历史版本" disabled={!versions.length || !!busy} value={current?.revision ?? ''} onChange={e => selectVersion(Number(e.target.value))}>{!versions.length && <option value="">尚无版本</option>}{versions.map(v => <option key={v.revision} value={v.revision}>V{v.revision} · {v.name || v.result.title || v.prompt.slice(0, 24)} · {stageLabels[v.result.status] ?? '检查结果'}</option>)}</select><span className="filebar-space" /><button disabled={!(result?.design_state || result?.designSpec) || !!busy} onClick={() => void act('validate')}><CheckCheck size={15} />检查</button><button aria-label={fullscreen ? '退出模型全屏' : '模型全屏'} onClick={() => setFullscreen(v => !v)}>{fullscreen ? <Minimize size={16} /> : <Maximize size={16} />}</button><button disabled={!result?.exports?.length} onClick={() => setExports(true)}><Download size={16} />导出</button></div>
        {active && laser ? <LaserPreview result={result} /> : active && <Suspense fallback={<p className="structure-caption" role="status">正在准备模型视图区…</p>}><StructurePreview result={result} /></Suspense>}
        <section className="structure-inspector" aria-label="结构参数与检查"><details open><summary><SlidersHorizontal size={15} />尺寸与布局{dimensionsDirty && <small>未应用</small>}</summary>
          {result?.designTemplate === 'rounded-box' && <p className="structure-caption">宽度、深度、高度均为盒子外尺寸。{result.designSpec?.roundedBox?.pattern_version === 2 ? '四角切缝交错接到上下边缘，保留中间连接桥。' : '旧版切缝未接通上下边缘，应用参数可生成修正版。'}接缝需胶合，材料与榫接须先试切。刀缝在加工软件中补偿。</p>}{!result?.parameters && <p className="structure-caption">确认需求后可在这里调整毫米尺寸。</p>}
          {Object.entries(result?.parameters ?? {}).map(([group, values]) => <fieldset disabled={!!busy} key={group}><legend>{groups[group] || group}</legend><div className="structure-param-grid">{Object.keys(values).map(key => ['top_lid', 'bottom_lid'].includes(key) ? <label className="structure-param-toggle" key={key}><input type="checkbox" checked={params[key] === 1} onChange={e => setParams(v => ({...v, [key]: e.target.checked ? 1 : 0}))} />{labels[key]}</label> : <label key={key}>{labels[key] || key}<input aria-label={labels[key] || key} type="number" min={key.endsWith('_offset_x') || key.endsWith('_offset_y') ? -500 : key === 'scale' ? .1 : 0} max={key === 'scale' ? 5 : 1000} step={['vent_count', 'slot_rows'].includes(key) ? 1 : .1} value={Number.isFinite(params[key]) ? params[key] : ''} onChange={e => setParams(v => ({...v, [key]: e.target.value === '' ? NaN : Number(e.target.value)}))} /></label>)}</div></fieldset>)}
          {!!result?.design_state?.layout_plan?.hardware_transforms.length && <fieldset disabled={!!busy}><legend>安装面与朝向</legend>{result.design_state.layout_plan.hardware_transforms.map((h, i) => <div className="structure-placement" key={`${h.hardware_id}-${i}`}><strong>{h.name}</strong><label>安装面<select value={faces[h.hardware_id] ?? h.mount_surface ?? 'base_floor'} onChange={e => setFaces(v => ({...v, [h.hardware_id]: e.target.value as 'base_floor' | 'lid_inner'}))}><option value="base_floor">底壳内侧</option><option value="lid_inner">上盖内侧</option></select></label><label>平面旋转<select value={rotations[h.hardware_id] ?? h.layout_rotation_deg ?? 0} onChange={e => setRotations(v => ({...v, [h.hardware_id]: Number(e.target.value)}))}>{[0, 90, 180, 270].map(n => <option key={n} value={n}>{n}°</option>)}</select></label></div>)}</fieldset>}
          {(result?.design_state || result?.designSpec) && <button className="primary" disabled={!!busy || Object.values(params).some(v => !Number.isFinite(v))} onClick={() => void act(result.status === 'confirmation' ? 'build' : 'parameters')}>{result.status === 'confirmation' ? (laser ? '应用参数并生成图纸' : '应用参数并生成模型') : '应用参数，重新生成'}</button>}
        </details><details><summary><CheckCheck size={15} />检查结果 · {result?.checks?.length ?? 0}</summary>{result?.checks?.map((c, i) => <p className={`structure-check check-${c.status}`} key={i}><strong>{c.status === 'pass' ? '通过' : c.status === 'fail' ? '未通过' : c.status === 'pending' ? '待验证' : '提示'}</strong>{c.message}</p>)}<p className="structure-caption">静态检查与网格检查不能替代实物装配、打印及强度测试。</p></details><button disabled={!result?.cadquery_code} onClick={() => setCode(true)}><FileCode2 size={15} />查看建模代码</button></section>
      </section>
    </main>
    {picker && <Dialog title="选择结构硬件" onClose={() => setPicker(false)} className="structure-picker"><p className="muted">这些资料提供几何尺寸与安装规则。选择不代表已核实实物；编程模块仍在智能工程师管理。</p><label className="field">搜索结构硬件<input data-dialog-autofocus value={search} onChange={e => setSearch(e.target.value)} placeholder="名称、型号或功能" /></label><div className="structure-profile-grid">{catalog?.profiles.filter(p => `${p.name} ${p.id} ${p.roles.join(' ')}`.toLowerCase().includes(search.toLowerCase())).map(p => <label key={p.id}><input type="checkbox" checked={pendingIds.includes(p.id)} disabled={!pendingIds.includes(p.id) && pendingIds.length >= 32} onChange={e => setPendingIds(v => e.target.checked ? [...v, p.id] : v.filter(x => x !== p.id))} />{p.thumbnail_url ? <img src={p.thumbnail_url} alt="" loading="lazy" /> : <Box size={22} />}<strong>{p.name}</strong><small>{sizeText(p.dimensions_mm)}</small></label>)}</div><div className="structure-dialog-actions"><span>已选择 {pendingIds.length} 个</span><button onClick={() => setPicker(false)}>取消</button><button className="primary" onClick={() => {setSelected(pendingIds); setPicker(false);}}>完成选择</button></div></Dialog>}
    {custom && <Dialog title="补充结构尺寸资料" onClose={() => setCustom(false)}><p className="muted">粘贴原 CAD 格式的 JSON profile，至少含 id、name、dimensions_mm、mounting、opening、keepouts、cad_reference。缺少孔位会阻止建模。资料随当前项目版本保存。</p><textarea className="structure-profile-input" aria-label="自定义结构资料 JSON" value={profileText} onChange={e => setProfileText(e.target.value)} placeholder={'{"id":"my_module","name":"我的模块","dimensions_mm":{"length_x":30,"width_y":20,"height_z":8}}'} />{error && <p role="alert" className="settings-error">{error}</p>}<button className="primary" onClick={addProfile}>加入资料</button></Dialog>}
    {code && <Dialog title="确定性建模代码" onClose={() => setCode(false)}><p className="muted">代码由结构工具根据校验后的参数生成，不直接执行 AI 返回的代码。</p><pre className="candidate-code">{result?.cadquery_code}</pre><button onClick={() => exportText('cadquery.py', result?.cadquery_code ?? '')}><Download size={16} />下载代码</button></Dialog>}
    {exports && <Dialog title="导出结构文件" onClose={() => setExports(false)}><p className="muted">选择当前结构版本的文件。真实模型与调试资料分别标注。</p><div className="structure-export-list">{result?.exports?.filter(e => e.url).map((e, i) => <a key={`${e.id}-${i}`} href={e.url} download><Download size={17} /><span><strong>{e.label}</strong><small>{e.fidelity === 'cadquery' || e.id.startsWith('cadquery_') ? '真实 CadQuery 模型' : (laser ? '毫米图纸 / 设计预览' : '设计代码 / 检查 / 调试资料')} · {e.format.toUpperCase()}</small></span></a>)}</div></Dialog>}
  </div>;
}
