import { useEffect, useRef, useState, type KeyboardEvent } from 'react';
import { Box, ChevronRight, Copy, File, FileCode2, FileJson, FileText, Folder, FolderOpen, Image as ImageIcon, LoaderCircle, MoreHorizontal, PanelRightClose, RefreshCw, Search, X } from 'lucide-react';
import type { OpenProjectFolderInput, OpenProjectFolderResult } from '../../../packages/contracts/src/projectFolder';
import { api } from './api';
import { ActionMenu } from './ActionMenu';
import { Dialog } from './Dialog';
import { ensureFolderPermission, openProjectFolder, type FolderBinding } from './projectFolders';
import { folderContents, folderPurposes, projectFilePreview, searchFolderFiles, type FolderContents, type FolderSearchResult, type ProjectFilePreview } from './projectFolderTree';
import './project-folder-sidebar.css';

const message = (error: unknown) => error instanceof Error ? error.message : String(error);
type SelectedFile = { handle: FileSystemFileHandle; path: string };
function FileIcon({ name }: { name: string }) {
  const type = /\.(png|jpe?g|webp|gif|bmp|avif)$/i.test(name) ? 'image' : /\.json$/i.test(name) ? 'json' : /\.(py|lua|[cm]?[jt]sx?|html?|css|c|h|cpp|hpp|ino|scad)$/i.test(name) ? 'code' : /\.(stl|step|stp|dxf)$/i.test(name) ? 'model' : /\.(md|txt|csv|log|toml|ya?ml)$/i.test(name) ? 'text' : 'file';
  const Icon = { image: ImageIcon, json: FileJson, code: FileCode2, model: Box, text: FileText, file: File }[type];
  return <Icon size={15} className={`folder-file-icon is-${type}`} aria-hidden="true" />;
}
function FileRow({ handle, path, selected, onSelect, search = false }: SelectedFile & { selected: string; onSelect: (file: SelectedFile) => void; search?: boolean }) {
  return <button className={`folder-file-row ${selected === path ? 'selected' : ''}`} data-folder-row aria-label={`预览 ${path}`} title={[path, folderPurposes[handle.name]].filter(Boolean).join('\n')} onClick={() => onSelect({ handle, path })}>
    <FileIcon name={handle.name} /><span className="folder-row-copy"><span>{handle.name}</span>{search && <small>{path.includes('/') ? path.slice(0, path.lastIndexOf('/')) : '项目根目录'}</small>}</span>
  </button>;
}
type TreeProps = { expanded: Set<string>; onToggle: (path: string, open: boolean) => void; selected: string; onSelect: (file: SelectedFile) => void };
function DirectoryBranch({ handle, depth, path, ...tree }: { handle: FileSystemDirectoryHandle; depth: number; path: string } & TreeProps) {
  const open = tree.expanded.has(path);
  const [contents, setContents] = useState<FolderContents | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    if (!open || contents || depth >= 10) return;
    let active = true;
    void folderContents(handle).then(value => { if (active) { setContents(value); setError(''); } }).catch(e => { if (active) setError(message(e)); });
    return () => { active = false; };
  }, [open, handle, depth, contents]);
  return <li><details className="folder-branch" open={open} onToggle={e => tree.onToggle(path, e.currentTarget.open)}>
    <summary data-folder-row title={[path, folderPurposes[handle.name]].filter(Boolean).join('\n')}><ChevronRight size={13} className="folder-chevron" aria-hidden="true" />{open ? <FolderOpen size={15} aria-hidden="true" /> : <Folder size={15} aria-hidden="true" />}<span>{handle.name}</span></summary>
    {open && (depth >= 10 ? <p className="folder-inline-note">层级较深，请在系统文件夹查看。</p> : error ? <p role="alert" className="folder-inline-note">{error}</p> : !contents ? <p role="status" className="folder-inline-note">读取中…</p> : <FolderEntries contents={contents} depth={depth + 1} path={path} {...tree} />)}
  </details></li>;
}
function FolderEntries({ contents, depth = 0, path = '', ...tree }: { contents: FolderContents; depth?: number; path?: string } & TreeProps) {
  return <><ul className="folder-tree" aria-label={path ? `${path} 的内容` : '项目内容目录'}>
    {contents.entries.map(handle => handle.kind === 'directory'
      ? <DirectoryBranch key={handle.name} handle={handle as FileSystemDirectoryHandle} depth={depth} path={`${path}${handle.name}/`} {...tree} />
      : <li key={handle.name}><FileRow handle={handle as FileSystemFileHandle} path={path + handle.name} selected={tree.selected} onSelect={tree.onSelect} /></li>)}
  </ul>{!contents.entries.length && <p className="folder-inline-note">此目录为空。</p>}{contents.truncated && <p className="folder-inline-note" role="status">仅显示前500项，其余请在系统文件夹查看。</p>}</>;
}
function treeKeys(event: KeyboardEvent<HTMLElement>) {
  if (!['ArrowDown', 'ArrowUp', 'ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
  const current = (event.target as HTMLElement).closest<HTMLElement>('[data-folder-row]');
  if (!current) return;
  const rows = Array.from(event.currentTarget.querySelectorAll<HTMLElement>('[data-folder-row]')).filter(row => row.getClientRects().length > 0);
  const index = rows.indexOf(current);
  if (index < 0) return;
  event.preventDefault();
  if (event.key === 'ArrowRight') {
    if (current.tagName === 'SUMMARY' && !(current.parentElement as HTMLDetailsElement).open) (current.parentElement as HTMLDetailsElement).open = true;
    else rows[index + 1]?.focus();
  } else if (event.key === 'ArrowLeft') {
    if (current.tagName === 'SUMMARY' && (current.parentElement as HTMLDetailsElement).open) (current.parentElement as HTMLDetailsElement).open = false;
    else current.closest('ul')?.closest('details')?.querySelector<HTMLElement>(':scope > summary')?.focus();
  } else rows[event.key === 'Home' ? 0 : event.key === 'End' ? rows.length - 1 : Math.max(0, Math.min(rows.length - 1, index + (event.key === 'ArrowDown' ? 1 : -1)))]?.focus();
}
function FilePreview({ selection, onClose, onOpenFolder }: { selection: SelectedFile; onClose: () => void; onOpenFolder: () => void }) {
  const [preview, setPreview] = useState<ProjectFilePreview | null>(null);
  const [error, setError] = useState('');
  const [url, setUrl] = useState('');
  useEffect(() => { let active = true; void projectFilePreview(selection.handle).then(value => { if (active) setPreview(value); }).catch(e => { if (active) setError(message(e)); }); return () => { active = false; }; }, [selection]);
  useEffect(() => {
    if (preview?.kind !== 'image') return;
    const reader = new FileReader(); let active = true;
    const ext = preview.file.name.split('.').at(-1)!.toLowerCase();
    const mime = ({ png: 'image/png', jpg: 'image/jpeg', jpeg: 'image/jpeg', webp: 'image/webp', gif: 'image/gif', bmp: 'image/bmp', avif: 'image/avif' } as Record<string, string>)[ext];
    reader.onload = () => { if (active && typeof reader.result === 'string') setUrl(reader.result); };
    reader.onerror = () => { if (active) setError('图片读取失败，可在系统文件夹中查看。'); };
    reader.readAsDataURL(new Blob([preview.file], { type: mime }));
    return () => { active = false; if (reader.readyState === FileReader.LOADING) reader.abort(); };
  }, [preview]);
  return <Dialog title={`预览：${selection.handle.name}`} className="project-file-preview" onClose={onClose} footer={<><span>只读预览 · 不会替换当前代码</span><button onClick={onOpenFolder}><FolderOpen size={15} />打开所在项目文件夹</button></>}>
    <p className="folder-preview-path">{selection.path}{preview && <small>{new Intl.NumberFormat('zh-CN').format(preview.file.size)} 字节 · 磁盘已保存内容</small>}</p>
    {error ? <p role="alert">{error}</p> : !preview ? <p role="status">正在读取文件…</p> : preview.kind === 'text' ? <pre className="folder-preview-text" aria-label="文件内容">{preview.text || '（空文件）'}</pre> : preview.kind === 'image' ? url && <img className="folder-preview-image" alt={selection.handle.name} src={url} onError={() => setError('图片无法解码，可在系统文件夹中查看。')} /> : <div className="folder-preview-unsupported"><FileIcon name={selection.handle.name} /><p>{preview.note}</p></div>}
  </Dialog>;
}

export function ProjectFolderPanel({ binding, restoring, status, syncError, unsaved, hidden, onLoadFolder, onChooseFolder, onLocated, onClose }: {
  binding: FolderBinding | null; restoring: boolean; status: string; syncError: string; unsaved: boolean; hidden?: boolean;
  onLoadFolder: () => void; onChooseFolder: () => void; onLocated: (path: string) => Promise<void>; onClose: () => void;
}) {
  const [contents, setContents] = useState<FolderContents | null>(null);
  const [loading, setLoading] = useState(false);
  const [opening, setOpening] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [path, setPath] = useState(binding?.nativePath ?? '');
  const [location, setLocation] = useState(false);
  const [revision, setRevision] = useState(0);
  const [expanded, setExpanded] = useState(new Set<string>());
  const [rootOpen, setRootOpen] = useState(true);
  const [query, setQuery] = useState('');
  const [searching, setSearching] = useState(false);
  const [results, setResults] = useState<FolderSearchResult | null>(null);
  const [searchError, setSearchError] = useState('');
  const [selection, setSelection] = useState<SelectedFile | null>(null);
  const [selected, setSelected] = useState('');
  const alive = useRef(true);
  const openPending = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => {
    setContents(null); setExpanded(new Set()); setRootOpen(true); setQuery(''); setSelection(null); setSelected('');
    setPath(binding?.nativePath ?? ''); setError(''); setNotice('');
  }, [binding?.handle]);
  useEffect(() => {
    if (!binding) return;
    if (status === '正在同步') { setLoading(true); return; }
    let active = true; setLoading(true); setError('');
    void ensureFolderPermission(binding).then(() => folderContents(binding.handle)).then(value => { if (active) setContents(value); })
      .catch(e => { if (active) { setContents(null); setError(message(e)); } }).finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [binding?.handle, binding?.checkpointHash, status, revision]);
  useEffect(() => {
    const controller = new AbortController(); setResults(null); setSearchError('');
    if (!query.trim() || !binding || !contents || loading) { setSearching(false); return; }
    setSearching(true);
    const timer = window.setTimeout(() => {
      void searchFolderFiles(binding.handle, query, controller.signal).then(value => { if (!controller.signal.aborted) setResults(value); })
        .catch(e => { if (!controller.signal.aborted) setSearchError(message(e)); }).finally(() => { if (!controller.signal.aborted) setSearching(false); });
    }, 180);
    return () => { controller.abort(); clearTimeout(timer); };
  }, [query, binding, contents, loading, revision]);
  const refresh = async () => {
    if (!binding || loading || openPending.current) return;
    setError('');
    try { await ensureFolderPermission(binding, true); if (alive.current) setRevision(v => v + 1); }
    catch (e) { if (alive.current) { setContents(null); setResults(null); setError(message(e)); } }
  };
  const open = async (locate = false, useManual = false) => {
    if (!binding?.checkpointHash || openPending.current) return;
    if (useManual && !path.trim()) { setError('请粘贴此项目文件夹的完整路径。'); return; }
    openPending.current = true; setOpening(true); setError(''); setNotice('');
    const input: OpenProjectFolderInput = { checkpointHash: binding.checkpointHash };
    if (locate) input.chooseAgain = true;
    if (useManual || (!locate && binding.nativePath)) input.path = (useManual ? path : binding.nativePath)!.trim();
    try {
      if(binding.managed&&!locate&&!useManual){await openProjectFolder(binding);setNotice('已请求系统打开文档目录中的项目文件夹。');return;}
      const result = await api<OpenProjectFolderResult>(`/projects/${binding.projectId}/folder/open`, 'POST', input);
      if (!alive.current) return;
      if (result.status === 'canceled') { setNotice('已取消定位。'); return; }
      setPath(result.path); setNotice('已请求系统打开项目文件夹。');
      try { await onLocated(result.path); } catch { if (alive.current) setError('已发出打开请求，但未记住路径；下次可重新定位。'); }
    } catch (e) { if (alive.current) { setError(message(e)); setLocation(true); } }
    finally { openPending.current = false; if (alive.current) setOpening(false); }
  };
  const onToggle = (key: string, value: boolean) => setExpanded(current => { if (current.has(key) === value) return current; const next = new Set(current); if (value) next.add(key); else next.delete(key); return next; });
  const onSelect = (file: SelectedFile) => { setSelected(file.path); setSelection(file); };
  return <aside className="project-folder-panel" aria-label="项目文件夹" id="project-folder-panel" hidden={hidden}>
    <header className="folder-panel-head"><h2>项目文件夹</h2><button aria-label="打开项目文件夹" title="在系统文件管理器中打开；首次需定位同一文件夹" disabled={opening || !binding?.checkpointHash} onClick={() => void open()}>{opening ? <LoaderCircle size={16} className="spin" /> : <FolderOpen size={16} />}</button><button aria-label="刷新目录 / 重新授权" title="刷新目录 / 重新授权" disabled={opening || loading || !binding} onClick={() => void refresh()}><RefreshCw size={15} /></button><button aria-label="收起项目文件夹" title="收起项目文件夹" onClick={onClose}><PanelRightClose size={16} /></button></header>
    {binding ? <>
      <div className="folder-project-root"><FolderOpen size={16} aria-hidden="true" /><strong title={binding.nativePath ?? binding.handle.name}>{binding.managed?binding.nativePath?.split(/[\\/]/).at(-1)??binding.handle.name:binding.handle.name}</strong><ActionMenu label="文件夹选项" align="right" disabled={opening} items={[
        { label: '手动定位与完整路径', icon: FolderOpen, onSelect: () => setLocation(true) },
        { label: '重新定位项目文件夹', icon: FolderOpen, disabled: !binding.checkpointHash, onSelect: () => void open(true) },
        { label: '复制完整路径', icon: Copy, disabled: !path, onSelect: () => void navigator.clipboard.writeText(path).then(() => setNotice('路径已复制。')).catch(() => setError('未能复制，可在完整路径中手动复制。')) },
        { label: '折叠全部目录', icon: Folder, onSelect: () => { setExpanded(new Set()); setRootOpen(true); } },
      ]}><MoreHorizontal size={16} /></ActionMenu></div>
      <label className="folder-search"><Search size={14} aria-hidden="true" /><input type="search" aria-label="筛选项目文件" placeholder="筛选文件…" value={query} maxLength={120} onChange={e => setQuery(e.target.value)} />{query && <button aria-label="清除文件筛选" onClick={() => setQuery('')}><X size={14} /></button>}</label>
      <a className="folder-skip" href="#workspace-stage" onClick={event => { event.preventDefault(); document.getElementById('workspace-stage')?.focus(); }}>跳过文件目录</a>
      <div className="folder-panel-content" onKeyDown={treeKeys}>
        {loading ? <p role="status" className="folder-inline-note">正在读取目录…</p> : contents && <>
          <details className="folder-all-files" open={rootOpen} onToggle={e => setRootOpen(e.currentTarget.open)} hidden={!!query.trim()}><summary data-folder-row><ChevronRight size={13} className="folder-chevron" aria-hidden="true" /><span>所有文件</span></summary><FolderEntries key={revision} contents={contents} expanded={expanded} onToggle={onToggle} selected={selected} onSelect={onSelect} /></details>
          {!!query.trim() && <div aria-label="文件筛选结果">{searching ? <p className="folder-inline-note" role="status">正在筛选…</p> : results && <><p className="folder-result-count" role="status">{results.files.length} 个匹配文件{results.truncated ? ' · 已达扫描范围上限' : ''}</p>{results.files.map(file => <FileRow key={file.path} {...file} search selected={selected} onSelect={onSelect} />)}{!results.files.length && <p className="folder-inline-note">没有匹配文件，试试其他名称。</p>}{!!results.unreadable && <p role="alert" className="folder-inline-note">{results.unreadable} 个子目录无法读取，可重新授权或在系统中查看。</p>}</>}{searchError && <p role="alert" className="folder-inline-note">{searchError}</p>}</div>}
        </>}
        {error && <p role="alert" className="folder-inline-note folder-error">{error}</p>}
        {syncError && <p role="alert" className="folder-inline-note folder-error">{syncError}</p>}
        {notice && <p role="status" className="folder-inline-note">{notice}</p>}
      </div>
      <footer className="folder-panel-foot"><span>{status || '已关联'}{unsaved ? ' · 修改未保存' : ''}</span><details className="compact-disclosure"><summary>存储说明</summary><p>目录展示已保存的文件，点击文件可预览。浏览器草稿尚未保存；本机记录是已保存的项目；文件夹是已同步的可携带副本。对话与配置保存在 zhangwen.project.json 中。</p></details></footer>
    </> : <div className="folder-panel-empty">{restoring ? <><LoaderCircle size={27} className="spin" /><p role="status">正在恢复原文件夹关联…</p></> : <><FolderOpen size={27} /><strong>本机记录已打开</strong><p>尚未关联磁盘文件夹。</p>{syncError && <p role="alert">{syncError}</p>}<button className="primary" onClick={onLoadFolder}>打开已有项目文件夹</button><button onClick={onChooseFolder}>另存到新文件夹</button><details className="compact-disclosure"><summary>存储说明</summary><p>本机记录已经打开。选择原文件夹会加载其中的项目；保存当前项目到新位置请使用另存。未保存修改仍需保存。</p></details></>}</div>}
    {location && <Dialog title="文件夹位置" className="folder-location-dialog" onClose={() => { if (!opening) setLocation(false); }}><p>首次打开时，需选择同一个项目文件夹。也可粘贴完整路径。</p><label className="field">本机文件夹完整路径<input aria-label="本机文件夹完整路径" value={path} maxLength={2048} disabled={opening} onChange={e => setPath(e.target.value)} placeholder="Windows 或 macOS 的项目文件夹完整路径" /></label><div className="folder-location-actions"><button disabled={opening || !binding?.checkpointHash} onClick={() => void open(true)}>重新定位</button><button disabled={opening || !path} onClick={() => void navigator.clipboard.writeText(path).then(() => setNotice('路径已复制。')).catch(() => setError('未能复制，请手动复制路径。'))}>复制路径</button><button className="primary" disabled={opening || !path.trim() || !binding?.checkpointHash} onClick={() => void open(false, true)}>{opening ? '正在打开…' : '按此路径打开'}</button></div>{error && <p role="alert">{error}</p>}{notice && <p role="status">{notice}</p>}</Dialog>}
    {selection && <FilePreview key={selection.path} selection={selection} onClose={() => setSelection(null)} onOpenFolder={() => { setSelection(null); void open(); }} />}
  </aside>;
}
