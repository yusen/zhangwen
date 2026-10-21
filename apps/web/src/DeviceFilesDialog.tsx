import { useState } from 'react';
import { Download, FileCode2, Folder, LoaderCircle, RefreshCw } from 'lucide-react';
import type { DeviceFile, DeviceFileContent, HardwareSummary, ProgramRunSubmission, UploadReceipt, Version } from '../../../packages/contracts/src/platform';
import type { MicroPythonDevice } from './serial';
import { Dialog } from './Dialog';
import { ProjectPrograms } from './ProjectProgramsPanel';
import type { FolderBinding } from './projectFolders';

export function DeviceFilesDialog({ view, device, connected, code, versions, disabled, onClose, onLoad, onDownload, onHistory, folder, board, componentIds, programReceipt, programRun, onChooseFolder }: {
  view: 'programs' | 'board'; device: MicroPythonDevice | null; connected: boolean; code: string; versions: Version[] | null; disabled: boolean;
  onClose: () => void; onLoad: (code: string, sourceBoard?: { id: string; name: string }) => void; onDownload: (name: string, value: string | Uint8Array) => void;
  onHistory: () => void;
  folder: FolderBinding | null; board: HardwareSummary | undefined; componentIds: string[];
  programReceipt: UploadReceipt | null; programRun: ProgramRunSubmission | null; onChooseFolder: () => void;
}) {
  const [files, setFiles] = useState<DeviceFile[] | null>(null);
  const [preview, setPreview] = useState<DeviceFileContent | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [programBusy, setProgramBusy] = useState(false);
  const task = async (label: string, run: () => Promise<void>) => {
    setBusy(label); setError('');
    try { await run(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(''); }
  };
  const locked = disabled || !!busy || programBusy;
  const decode = (value: Uint8Array) => new TextDecoder('utf-8', { fatal: true }).decode(value);
  return <Dialog className="device-files-dialog" title={view === 'programs' ? '项目程序' : '板上文件'} onClose={() => { if (!busy && !programBusy) onClose(); }}>
    {view === 'programs' && <ProjectPrograms folder={folder} code={code} board={board} componentIds={componentIds} versions={versions} receipt={programReceipt} run={programRun} disabled={disabled || !!busy} onBusy={setProgramBusy} onChooseFolder={onChooseFolder} onLoad={onLoad} onDownload={onDownload} />}
    {view === 'board' && <section className="file-section"><h3>设备根目录</h3><p className="muted">{connected ? '浏览和读取文件会校验摘要；上传仅允许项目清单中的 main.py。' : '连接 MicroPython 设备并停止程序后，可浏览和读取设备文件。'}</p>
      <button disabled={!connected || locked} onClick={() => void task('读取设备目录', async () => { if (!device) return; setPreview(null); setFiles(await device.listFiles()); })}><RefreshCw size={16} />刷新设备文件</button>
      {files && <div className="device-file-list">{files.length ? files.map(file => <article className="device-file-row" key={file.path}>{file.directory ? <Folder size={18} /> : <FileCode2 size={18} />}<span><strong>{file.path}</strong><small>{file.directory ? '目录' : `${file.size} bytes`}</small></span><button disabled={!connected || locked || file.directory || file.size > 65536} onClick={() => void task('读取设备文件', async () => { if (device) setPreview(await device.readFile(file.path)); })}>读取</button></article>) : <p className="muted">设备根目录为空。</p>}</div>}
      {preview && <div className="device-file-preview"><strong>{preview.path} · 回读校验一致</strong><p className="checksum">SHA-256: {preview.sha256}</p><pre>{(() => { try { return decode(preview.bytes); } catch { return '二进制文件，可导出保存。'; } })()}</pre><div className="file-actions"><button disabled={locked} onClick={() => onDownload(preview.path, preview.bytes)}><Download size={16} />导出设备文件</button>{preview.path.endsWith('.py') && <button disabled={locked} onClick={() => { try { const text = decode(preview.bytes); if (text.includes('\0')) throw new Error('代码文件不能包含NUL。'); onLoad(text); } catch (err) { setError(String(err)); } }}>载入编辑器</button>}</div></div>}
    </section>}
    {view === 'programs' && <section className="file-section"><h3>项目历史版本</h3><button disabled={locked || !versions} onClick={onHistory}>查看保存的代码版本{versions ? `（${versions.length}）` : ''}</button>{!versions && <p className="muted">保存项目后可查看历史版本。</p>}</section>}
    {busy && <p role="status"><LoaderCircle className="spin" size={16} />{busy}中…</p>}{error && <p className="chat-error" role="alert">{error}</p>}
  </Dialog>;
}
