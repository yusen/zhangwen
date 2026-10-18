import { useEffect, useRef, useState } from 'react';
import { Download, FileCode2, FolderOpen, RefreshCw, Save } from 'lucide-react';
import type { HardwareSummary, ProjectProgramRecord, ProgramRunSubmission, UploadReceipt, Version } from '../../../packages/contracts/src/platform';
import { ensureFolderPermission, type FolderBinding } from './projectFolders';
import { listProjectPrograms, readProjectProgram, saveProjectProgram, type ProjectProgram } from './projectPrograms';

export function ProjectPrograms({ folder, code, board, componentIds, versions, receipt, run, disabled, onBusy, onChooseFolder, onLoad, onDownload }: {
  folder: FolderBinding | null; code: string; board: HardwareSummary | undefined; componentIds: string[]; versions: Version[] | null;
  receipt: UploadReceipt | null; run: ProgramRunSubmission | null; disabled: boolean;
  onBusy: (value: boolean) => void; onChooseFolder: () => void;
  onLoad: (code: string, sourceBoard?: { id: string; name: string }) => void;
  onDownload: (name: string, value: string | Uint8Array) => void;
}) {
  const [programs, setPrograms] = useState<ProjectProgram[]>([]);
  const [issues, setIssues] = useState<string[]>([]);
  const [preview, setPreview] = useState<(ProjectProgram & { code: string }) | null>(null);
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState('');
  const [observed, setObserved] = useState<ProjectProgramRecord['verification']['observed']>('unconfirmed');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const working = useRef(false);
  const locked = disabled || !!busy;
  const label = (status: ProjectProgramRecord['verification']['observed']) => status === 'passed' ? '用户确认通过' : status === 'failed' ? '用户确认未通过' : '测试结果待确认';
  const refresh = async () => { if (!folder) return; const result = await listProjectPrograms(folder); setPrograms(result.programs); setIssues(result.issues); };
  useEffect(() => {
    let active = true;
    if (folder) void listProjectPrograms(folder).then(result => { if (active) { setPrograms(result.programs); setIssues(result.issues); } }).catch(err => { if (active) setError(String(err instanceof Error ? err.message : err)); });
    return () => { active = false; };
  }, [folder]);
  useEffect(() => {
    if (!busy) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', prevent);
    return () => window.removeEventListener('beforeunload', prevent);
  }, [busy]);
  const task = async (title: string, action: () => Promise<void>) => {
    if (working.current || disabled) return;
    working.current = true; setBusy(title); onBusy(true); setError(''); setNotice('');
    try { await action(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { working.current = false; setBusy(''); onBusy(false); }
  };
  return <section className="file-section project-programs" aria-label="项目程序">
    <h3><FolderOpen size={17} />项目程序</h3>
    <p className="muted">{folder ? `${folder.handle.name} / programs / · 保存程序副本，保留当前 main.py 和版本记录。` : '先保存项目并选择文件夹，即可在项目 programs 子文件夹中保存和查看测试程序。'}</p>
    <div className="file-actions">{folder ? <>
      <button disabled={locked || !board || !code.trim()} onClick={() => { setCreating(true); setNotice(''); }}><Save size={16} />保存当前程序</button>
      <button disabled={locked} onClick={() => void task('读取项目程序', async () => { await ensureFolderPermission(folder, true); await refresh(); })}><RefreshCw size={16} />刷新项目程序</button>
    </> : <button disabled={locked} onClick={onChooseFolder}><FolderOpen size={16} />先保存项目文件夹</button>}</div>
    {creating && <form className="program-save-form" onSubmit={event => { event.preventDefault(); void task('保存项目程序', async () => {
      if (!folder || !board) return;
      const version = versions?.filter(item => item.source !== 'ai' && item.code === code && item.boardId === board.componentId).sort((a, b) => b.revision - a.revision)[0];
      const saved = await saveProjectProgram(folder, { name, code, boardId: board.componentId, boardName: board.displayName, componentIds, sourceRevision: version?.revision ?? null, observed, note, receipt, run });
      await refresh(); setPreview(await readProjectProgram(folder, saved.directory)); setCreating(false); setName(''); setNote(''); setObserved('unconfirmed'); setNotice('程序副本已保存并回读校验，可在下方查看。');
    }); }}>
      <label className="field">程序名称<input autoFocus aria-label="程序名称" value={name} maxLength={80} required disabled={locked} placeholder="例如：OLED 空心圆测试" onChange={event => setName(event.target.value)} /></label>
      <label className="field">测试结果<select aria-label="测试结果" value={observed} disabled={locked} onChange={event => setObserved(event.target.value as ProjectProgramRecord['verification']['observed'])}><option value="unconfirmed">待确认</option><option value="passed">我已观察实物，确认通过</option><option value="failed">我已观察实物，确认未通过</option></select></label>
      <label className="field">测试说明<textarea aria-label="测试说明" value={note} maxLength={2000} disabled={locked} placeholder="记录接线、现象或需要注意的参数" onChange={event => setNote(event.target.value)} /></label>
      <p className="muted">测试结果由你确认；平台单独记录本次会话中与代码一致的上传回读、运行提交信息。</p>
      <div className="file-actions"><button type="button" disabled={locked} onClick={() => setCreating(false)}>取消保存程序</button><button className="primary" disabled={locked || !name.trim()}>保存到程序子文件夹</button></div>
    </form>}
    {folder && <div className="project-program-list">{programs.length ? programs.map(program => <article className="project-program-row" key={program.directory}>
      <FileCode2 size={18} /><div><strong>{program.record.name}</strong><small>{program.record.boardName} · {label(program.record.verification.observed)}</small><small>{new Date(program.record.createdAt).toLocaleString()}</small><code title={`programs/${program.directory}/main.py`}>programs/{program.directory}/main.py</code></div>
      <button disabled={locked} aria-label={`查看程序：${program.record.name}`} onClick={() => void task('读取程序', async () => { setPreview(null); if (folder) setPreview(await readProjectProgram(folder, program.directory)); })}>查看</button>
    </article>) : <p className="muted">还没有保存的程序。可将测试程序按名称保存到子文件夹。</p>}</div>}
    {issues.length > 0 && <p className="program-file-warning" role="status">{issues.slice(0, 3).join('；')}{issues.length > 3 && `；另有${issues.length - 3}项待核对`}</p>}
    {preview && <section className="project-program-preview" aria-label="程序预览"><h4>{preview.record.name}</h4><p>{preview.record.boardName} · {label(preview.record.verification.observed)}</p>
      <p className="muted">{preview.record.sourceRevision ? `来源：已保存版本 v${preview.record.sourceRevision}` : '来源：编辑器草稿'} · 模块 {preview.record.componentIds.length} 个 · 代码摘要一致</p>
      <p className="muted">上传回读：{preview.record.verification.uploadVerifiedAt ? new Date(preview.record.verification.uploadVerifiedAt).toLocaleString() : '未记录'} · 运行提交：{preview.record.verification.runSubmittedAt ? new Date(preview.record.verification.runSubmittedAt).toLocaleString() : '未记录'}</p>
      {preview.record.verification.note && <p className="program-observation">{preview.record.verification.note}</p>}<pre>{preview.code}</pre>
      <div className="file-actions"><button disabled={locked} onClick={() => onLoad(preview.code, { id: preview.record.boardId, name: preview.record.boardName })}>载入此程序</button><button disabled={locked} onClick={() => onDownload('main.py', preview.code)}><Download size={16} />导出程序</button></div>
    </section>}
    {busy && <p role="status">{busy}中…</p>}{notice && <p role="status">{notice}</p>}{error && <p className="chat-error" role="alert">{error}</p>}
  </section>;
}
