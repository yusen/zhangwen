import { useEffect, useState } from 'react';
import type { ProjectReference, ReferenceCitation } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { Dialog } from './Dialog';
import type { ProjectDirectory } from './projectFolders';

const textExtensions = /\.(txt|md|markdown|py|lua|html?|js|ts|json|csv|css|xml|ya?ml|ino|c|h)$/i;
const supported = /\.(txt|md|markdown|py|lua|html?|js|ts|json|csv|css|xml|ya?ml|ino|c|h|pdf|docx)$/i;
export async function referenceFile(file: File, name = file.name): Promise<Pick<ProjectReference, 'name' | 'original' | 'encoding'>> {
  if (!supported.test(name)) throw new Error(`${name}：暂不支持，请先转换为文本、文本 PDF 或 DOCX。`);
  if (file.size > 1_000_000) throw new Error(`${name}：超过1MB，请拆分资料。`);
  const bytes = new Uint8Array(await file.arrayBuffer());
  if (textExtensions.test(name)) {
    let original: string;
    try { original = new TextDecoder('utf-8', { fatal: true }).decode(bytes); }
    catch { throw new Error(`${name}：请先另存为UTF-8编码。`); }
    return { name, original, encoding: 'text' };
  }
  let binary = '';
  for (let index = 0; index < bytes.length; index += 8192) binary += String.fromCharCode(...bytes.slice(index, index + 8192));
  return { name, original: btoa(binary), encoding: 'base64' };
}

export function ReferenceSources({ references, notice }: { references?: ReferenceCitation[]; notice?: string }) {
  if (!references?.length && !notice) return null;
  const count = new Set(references?.map(item => item.id)).size;
  return <details className="reference-sources"><summary>本轮提供了 {count} 份资料</summary><p className="muted">{notice} 提供片段不代表模型逐条采用，请核对回答。</p>{references?.map((item, index) => <details key={index}><summary>{item.name} · V{item.version} · 第{item.startLine}–{item.endLine}行</summary><pre>{item.text}</pre></details>)}</details>;
}
const modeLabels = { auto: '可供 AI 参考', pin: '优先参考', off: '已停用' };
type View = 'list' | 'add' | 'preview' | 'history';
export function ProjectReferences({ projectId, folder, onClose, onChanged, onModule }: {
  projectId: string; folder: ProjectDirectory | null; onClose: () => void;
  onChanged: () => Promise<void>; onModule: (text: string) => void;
}) {
  const [items, setItems] = useState<ProjectReference[]>([]);
  const [history, setHistory] = useState<ProjectReference[]>([]);
  const [view, setView] = useState<View>('list');
  const [previewBack, setPreviewBack] = useState<'list' | 'history'>('list');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const [issues, setIssues] = useState<{ name: string; message: string }[]>([]);
  const [pasteName, setPasteName] = useState('说明.md'); const [paste, setPaste] = useState('');
  const [pasteOpen, setPasteOpen] = useState(false);
  const [preview, setPreview] = useState<ProjectReference | null>(null);
  const refresh = async () => { const result = await api<{ references: ProjectReference[] }>(`/projects/${projectId}/references`); setItems(result.references); return result.references; };
  useEffect(() => { let active = true; void api<{ references: ProjectReference[] }>(`/projects/${projectId}/references`).then(r => { if (active) setItems(r.references); }).catch(e => { if (active) setError(String(e)); }); return () => { active = false; }; }, [projectId]);
  const store = async (input: Pick<ProjectReference, 'name' | 'original' | 'encoding'>, previous?: ProjectReference, mode?: ProjectReference['mode']) => {
    const result = await api<ProjectReference>(`/projects/${projectId}/references`, 'POST', { name: input.name, original: input.original, encoding: input.encoding, mode: mode ?? previous?.mode ?? 'auto', expectedVersion: previous?.version ?? 0 });
    await refresh(); return result;
  };
  const importFiles = async (files: { file: File; name: string }[]) => {
    if (!files.length) return;
    setBusy(true); setError(''); setStatus('正在解析资料…'); setIssues([]); setView('list');
    const failed: { name: string; message: string }[] = []; let count = 0;
    try {
      let current = await refresh();
      for (const { file, name } of files) {
        try {
          setStatus(`正在解析：${name}`);
          if (current.some(item => item.name === name)) throw new Error('同名资料已保留，请在该文件菜单中选择“更新文件”。');
          await store(await referenceFile(file, name)); count++; current = await refresh();
        } catch (e) { failed.push({ name, message: e instanceof Error ? e.message : String(e) }); setIssues([...failed]); }
      }
      setStatus(`已导入 ${count} 份资料${failed.length ? `，${failed.length} 份未导入` : '，可供当前项目 AI 参考'}。`); await onChanged();
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  const fromFolder = async () => {
    if (!folder) return;
    setBusy(true); setError('');
    try {
      const files: { file: File; name: string }[] = [];
      const visit = async (directory: FileSystemDirectoryHandle, prefix = '', depth = 0) => {
        if (depth > 6) throw new Error('参考资料子目录超过6层，请单独选择文件。');
        for await (const [name, handle] of (directory as FileSystemDirectoryHandle & { entries(): AsyncIterableIterator<[string, FileSystemHandle]> }).entries()) {
          if (name.startsWith('.')) continue;
          if (handle.kind === 'directory') await visit(handle as FileSystemDirectoryHandle, prefix + name + '/', depth + 1);
          else { files.push({ file: await (handle as FileSystemFileHandle).getFile(), name: prefix + name }); if (files.length > 20) throw new Error('参考资料超过20份，请分批选择文件。'); }
        }
      };
      await visit(await folder.getDirectoryHandle('参考资料'));
      if (!files.length) setStatus('参考资料目录为空。'); else await importFiles(files);
    } catch (e) { setError(e instanceof DOMException && e.name === 'NotFoundError' ? '请先在项目文件夹中建立“参考资料”目录并放入文件，或选择文件导入。' : String(e)); }
    finally { setBusy(false); }
  };
  const change = async (item: ProjectReference, mode: ProjectReference['mode']) => {
    setBusy(true); setError(''); try { await store(item, item, mode); setStatus(`${item.name}：${modeLabels[mode]}。`); await onChanged(); } catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const versions = async (item: ProjectReference) => {
    setBusy(true); setError('');
    try { const result = await api<{ references: ProjectReference[] }>(`/projects/${projectId}/references?history=true`); setHistory(result.references.filter(r => r.id === item.id).sort((a,b) => b.version-a.version)); setPreview(item); setView('history'); }
    catch (e) { setError(String(e)); } finally { setBusy(false); }
  };
  const openPreview = (item: ProjectReference, back: 'list' | 'history') => { setPreview(item); setPreviewBack(back); setView('preview'); };
  return <Dialog title="项目资料" onClose={onClose} className="reference-dialog">
    {view === 'list' && <><div className="resource-section-head"><p className="muted">添加接口说明或成功案例，供当前项目对话参考。</p><button className="primary" disabled={busy} onClick={() => { setView('add'); setError(''); }}>＋ 添加资料</button></div>
      <div className="reference-list">{items.map(item => <article key={item.id}>
        <button className="reference-name" disabled={busy} onClick={() => openPreview(item, 'list')}><strong>{item.name}</strong><small>V{item.version}</small></button>
        <span className={`reference-mode ${item.mode}`}>{modeLabels[item.mode]}</span>
        <details className="resource-menu"><summary aria-label={`${item.name}更多操作`}>⋯</summary><div>
          {(['auto', 'pin', 'off'] as const).map(mode => <button key={mode} disabled={busy || item.mode === mode} onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); void change(item, mode); }}>{mode === 'auto' ? '自动参考' : mode === 'pin' ? '优先参考' : '停用'}</button>)}
          <label className="reference-file-button">更新文件<input type="file" aria-label={`更新资料：${item.name}`} disabled={busy} onChange={event => {
            const file = event.target.files?.[0]; event.target.value = ''; if (!file) return; event.currentTarget.closest('details')?.removeAttribute('open'); setBusy(true); setError('');
            void referenceFile(file, item.name).then(input => store(input, item)).then(async () => { setStatus(`${item.name}：已更新，旧版本已保留。`); await onChanged(); }).catch(e => setError(String(e))).finally(() => setBusy(false));
          }} /></label>
          <button disabled={busy} onClick={event => { event.currentTarget.closest('details')?.removeAttribute('open'); void versions(item); }}>查看版本</button>
        </div></details>
      </article>)}{issues.map((issue,index) => <article className="reference-error" key={`issue-${index}`}><strong>{issue.name}</strong><span>未导入</span><p role="alert">{issue.message}</p></article>)}</div>
      {!items.length && <div className="resource-empty"><p>还没有项目资料</p><small>先添加一份说明书、接口文档或跑通的程序。</small></div>}
    </>}
    {view === 'add' && <><button className="resource-back" disabled={busy} onClick={() => setView('list')}>← 返回资料列表</button><div className="reference-import-options">
      <label className="reference-file-button primary">选择文件<input aria-label="导入项目资料" type="file" multiple disabled={busy} accept=".txt,.md,.markdown,.py,.html,.js,.ts,.json,.csv,.css,.xml,.yaml,.yml,.ino,.c,.h,.pdf,.docx" onChange={event => { const files = [...(event.target.files ?? [])]; event.target.value = ''; void importFiles(files.map(file => ({ file, name: file.name }))); }} /></label>
      <button disabled={busy || !folder} onClick={() => void fromFolder()}>从项目文件夹导入</button><button disabled={busy} onClick={() => setPasteOpen(value => !value)}>粘贴文字</button>
    </div><p className="muted">支持 UTF-8 文本、代码、文本 PDF 和 DOCX，每份最多1MB。扫描件与图片需先转文字。</p>
      {!folder && <small className="muted">保存到项目文件夹后，可导入其中“参考资料”目录。</small>}
      {pasteOpen && <div><label className="reference-field">文件名<input value={pasteName} onChange={e => setPasteName(e.target.value)} maxLength={200} /></label><label className="reference-field">说明内容<textarea value={paste} onChange={e => setPaste(e.target.value)} rows={6} maxLength={120000} /></label><button className="primary" disabled={busy || !paste.trim()} onClick={() => { setBusy(true); setError(''); void store({ name: pasteName, original: paste, encoding: 'text' }).then(async () => { setPaste(''); setView('list'); setStatus('说明已保存，可供当前项目 AI 参考。'); await onChanged(); }).catch(e => setError(String(e))).finally(() => setBusy(false)); }}>保存说明</button></div>}
    </>}
    {view === 'preview' && preview && <section className="reference-preview"><button className="resource-back" onClick={() => setView(previewBack)}>← {previewBack === 'history' ? '返回版本列表' : '返回资料列表'}</button><h3>{preview.name} · V{preview.version}</h3><small className="muted">提取文字预览，图片未分析；请核对表格与参数。</small><pre>{preview.text}</pre><button onClick={() => onModule(preview.text)}>用这份资料创建我的模块</button></section>}
    {view === 'history' && preview && <section><button className="resource-back" onClick={() => setView('list')}>← 返回资料列表</button><h3>{preview.name} · 历史版本</h3><div className="reference-list">{history.map(item => <article key={item.version}><button className="reference-name" onClick={() => openPreview(item, 'history')}>V{item.version}{item.version === history[0]?.version ? ' · 当前版本' : ''}</button><span>{modeLabels[item.mode]}</span><small>{item.text.length} 字</small></article>)}</div></section>}
    {error && <p role="alert">{error}</p>}{status && <p role="status" className="reference-status">{status}</p>}
    <small className="muted">启用的相关片段会发送给你配置的 AI 服务，资料随项目保存。</small>
  </Dialog>;
}
