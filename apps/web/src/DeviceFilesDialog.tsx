import { useState } from 'react';
import { Download, FileCode2, Folder, LoaderCircle, RefreshCw } from 'lucide-react';
import type { DeviceFile, DeviceFileContent, Version } from '../../../packages/contracts/src/mu';
import type { MicroPythonDevice } from './serial';
import { Dialog } from './Dialog';

export function DeviceFilesDialog({ device, connected, code, versions, disabled, onClose, onLoad, onDownload, onHistory }: {
  device: MicroPythonDevice | null; connected: boolean; code: string; versions: Version[] | null; disabled: boolean;
  onClose: () => void; onLoad: (code: string) => void; onDownload: (name: string, value: string | Uint8Array) => void;
  onHistory: () => void;
}) {
  const [files, setFiles] = useState<DeviceFile[] | null>(null);
  const [preview, setPreview] = useState<DeviceFileContent | null>(null);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const task = async (label: string, run: () => Promise<void>) => {
    setBusy(label); setError('');
    try { await run(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setBusy(''); }
  };
  const locked = disabled || !!busy;
  const decode = (value: Uint8Array) => new TextDecoder('utf-8', { fatal: true }).decode(value);
  return <Dialog className="device-files-dialog" title="项目与设备文件" onClose={() => { if (!busy) onClose(); }}>
    <section className="file-section"><h3>本机 main.py</h3><p className="muted">载入文件仅替换编辑器草稿。保存、检查、上传仍需分别操作。</p>
      <div className="file-actions"><button disabled={locked} onClick={() => onDownload('main.py', code)}><Download size={16} />导出当前代码</button>
        <label className="file-import">载入本机 .py<input aria-label="载入本机 Python 文件" type="file" accept=".py,text/x-python" disabled={locked} onChange={event => {
          const file = event.target.files?.[0]; event.target.value = ''; if (!file) return;
          void task('读取本机文件', async () => { if (!file.name.toLowerCase().endsWith('.py') || file.size > 65536) throw new Error('请选择64 KiB以内的 .py 文件。'); const text = decode(new Uint8Array(await file.arrayBuffer())); if (text.includes('\0')) throw new Error('代码文件不能包含NUL。'); onLoad(text); });
        }} /></label></div>
    </section>
    <section className="file-section"><h3>设备根目录</h3><p className="muted">{connected ? '浏览和读取文件会校验摘要；上传仅允许项目清单中的 main.py。' : '连接 MicroPython 设备并停止程序后，可浏览和读取设备文件。'}</p>
      <button disabled={!connected || locked} onClick={() => void task('读取设备目录', async () => { if (!device) return; setPreview(null); setFiles(await device.listFiles()); })}><RefreshCw size={16} />刷新设备文件</button>
      {files && <div className="device-file-list">{files.length ? files.map(file => <article className="device-file-row" key={file.path}>{file.directory ? <Folder size={18} /> : <FileCode2 size={18} />}<span><strong>{file.path}</strong><small>{file.directory ? '目录' : `${file.size} bytes`}</small></span><button disabled={!connected || locked || file.directory || file.size > 65536} onClick={() => void task('读取设备文件', async () => { if (device) setPreview(await device.readFile(file.path)); })}>读取</button></article>) : <p className="muted">设备根目录为空。</p>}</div>}
      {preview && <div className="device-file-preview"><strong>{preview.path} · 回读校验一致</strong><p className="checksum">SHA-256: {preview.sha256}</p><pre>{(() => { try { return decode(preview.bytes); } catch { return '二进制文件，可导出保存。'; } })()}</pre><div className="file-actions"><button disabled={locked} onClick={() => onDownload(preview.path, preview.bytes)}><Download size={16} />导出设备文件</button>{preview.path.endsWith('.py') && <button disabled={locked} onClick={() => { try { const text = decode(preview.bytes); if (text.includes('\0')) throw new Error('代码文件不能包含NUL。'); onLoad(text); } catch (err) { setError(String(err)); } }}>载入编辑器</button>}</div></div>}
    </section>
    <section className="file-section"><h3>项目历史版本</h3><button disabled={locked || !versions} onClick={onHistory}>查看保存的代码版本{versions ? `（${versions.length}）` : ''}</button>{!versions && <p className="muted">保存项目后可查看历史版本。</p>}</section>
    {busy && <p role="status"><LoaderCircle className="spin" size={16} />{busy}中…</p>}{error && <p className="chat-error" role="alert">{error}</p>}
  </Dialog>;
}
