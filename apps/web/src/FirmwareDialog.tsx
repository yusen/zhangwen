import { useEffect, useRef, useState } from 'react';
import type { ESPLoader, Transport } from 'esptool-js';
import type { FirmwareProfile, HardwareSummary } from '../../../packages/contracts/src/mu';
import { api } from './api';
import { Dialog } from './Dialog';
import { BoardArtwork } from './BoardArtwork';
import { backupFirmware, persistFirmwareBackup, loadDefaultFirmware, writeVerified, type FirmwareBackup } from './firmware';

export function FirmwareDialog({ board, onClose, onBusy, download }: { board: HardwareSummary; onClose: () => void; onBusy: (value: boolean) => void; download: (name: string, value: string | Uint8Array) => void }) {
  const [profile, setProfile] = useState<FirmwareProfile | null>(null);
  const [file, setFile] = useState<Uint8Array | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('正在核对本地默认固件…');
  const [identity, setIdentity] = useState('');
  const [backup, setBackup] = useState<FirmwareBackup | null>(null);
  const [confirmed, setConfirmed] = useState(false);
  const [written, setWritten] = useState(false);
  const loader = useRef<ESPLoader | null>(null);
  const transport = useRef<Transport | null>(null);
  const release = useRef<(() => void) | null>(null);
  const active = useRef(true);
  const working = useRef(false);
  const nativeSerial = (navigator as Navigator & { serial?: { requestPort(): Promise<ConstructorParameters<typeof Transport>[0]> } }).serial;
  const disconnect = async () => {
    try { await transport.current?.disconnect(); } finally { transport.current = null; loader.current = null; release.current?.(); release.current = null; }
  };
  const operation = async (task: () => Promise<void>) => {
    if (working.current) return;
    working.current = true; setBusy(true); onBusy(true); setError('');
    try { await task(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { working.current = false; setBusy(false); onBusy(false); }
  };
  useEffect(() => {
    active.current = true;
    const controller = new AbortController();
    void (async () => {
      const value = await api<FirmwareProfile>('/firmware/' + board.componentId);
      if (!active.current) return;
      setProfile(value);
      if (!value.image) { setStatus(value.unavailable ?? '暂无已核实的默认固件。'); return; }
      const bytes = await loadDefaultFirmware(value, controller.signal);
      if (active.current) { setFile(bytes); setStatus('本地固件大小、SHA-256和芯片镜像头核对通过。'); }
    })().catch(err => { if (active.current && !controller.signal.aborted) setError(String(err)); });
    return () => { active.current = false; controller.abort(); void disconnect(); };
  }, [board.componentId]);
  const close = () => { if (!working.current) void operation(async () => { await disconnect(); onClose(); }); };
  const saveBackup = (saved: FirmwareBackup) => {
    download(`flash-backup-${saved.chip}-${saved.id}.bin`, saved.bytes);
    download(`flash-backup-${saved.id}.json`, JSON.stringify({ ...saved, bytes: undefined, size: saved.bytes.length }, null, 2));
  };
  const flash = () => {
    if (!nativeSerial || !navigator.locks || !profile || !file || !confirmed || working.current) return;
    // Port selection must begin in the button gesture. No backend serial access.
    const portPromise = nativeSerial.requestPort();
    void operation(async () => {
      const port = await portPromise;
      await new Promise<void>((resolve, reject) => {
        void navigator.locks.request('zhangwen-web-serial', { ifAvailable: true }, async lock => {
          if (!lock) { reject(new Error('另一标签正在使用串口，请先断开。')); return; }
          const held = new Promise<void>(done => { release.current = done; });
          let saved: FirmwareBackup | null = null;
          try {
            const esp = await import('esptool-js');
            transport.current = new esp.Transport(port);
            const peer = new esp.ESPLoader({ transport: transport.current, baudrate: 115200, romBaudrate: 115200, terminal: { clean() {}, write() {}, writeLine: value => { if (active.current) setStatus(value); } } });
            loader.current = peer;
            await peer.main();
            if (peer.chip.CHIP_NAME !== profile.chip) throw new Error(`检测到 ${peer.chip.CHIP_NAME}，与当前主控 ${profile.chip} 不一致，已阻止写入。`);
            const capacity = await peer.getFlashSize() * 1024;
            setIdentity(`${peer.chip.CHIP_NAME} · ${capacity / 1024 / 1024} MiB`);
            saved = await backupFirmware(peer, profile, file, profile.offset, capacity, value => setStatus(`备份读取 · ${Math.round(value * 100)}%`));
            await persistFirmwareBackup(saved);
            setBackup(saved); saveBackup(saved);
            setWritten(true);
            await writeVerified(peer, file, profile.offset, (phase, value) => setStatus(`${phase} · ${Math.round(value * 100)}%`));
            setStatus('固件已写入，SHA-256回读一致。关闭后按RESET重启，再连接检查MicroPython及板载功能。');
            resolve();
          } catch (err) {
            reject(err);
            // Keep a communicating peer available for range recovery after a write failure.
            if (!saved) await disconnect();
          }
          await held;
        }).catch(reject);
      });
    });
  };
  return <Dialog title="固件刷入" onClose={close} className="firmware-dialog">
    <div className="firmware-board"><BoardArtwork board={board} /><div><strong>{board.displayName}</strong><p>{profile?.image?.version ?? '读取板型配置…'}</p></div></div>
    <p className="firmware-warning">刷入会覆盖固件及部分设备程序、数据。请先保存设备文件。平台会自动备份本次覆盖范围、刷入并回读核对，不整片擦除。</p>
    {profile?.image && <><p>默认固件：<strong>{profile.image.version}</strong> · {(profile.image.size / 1024 / 1024).toFixed(2)} MiB</p><p className="muted">{profile.image.notes}</p><a href={profile.image.sourceUrl} target="_blank" rel="noreferrer">官方来源与版本说明</a><details><summary>镜像校验信息</summary><p className="checksum">{profile.image.name} · 偏移 0x{profile.offset.toString(16)}<br />SHA-256：{profile.image.sha256}</p></details></>}
    <p className="muted">按主控说明进入下载模式（通常按住BOOT再按RESET），再点击刷入；写入期间请勿拔线或关闭页面。备份保存在当前浏览器并尝试下载，可在下方重新下载。</p>
    {!written && <><label className="confirm"><input type="checkbox" checked={confirmed} disabled={busy || !file} onChange={event => setConfirmed(event.target.checked)} />我已保存设备文件，确认将所选设备刷为当前主控的默认固件。</label><button className="primary" disabled={!file || !confirmed || busy || !nativeSerial || !navigator.locks || !!identity} onClick={flash}>一键刷入默认固件</button></>}
    {identity && <p>实际设备：<strong>{identity}</strong></p>}
    {backup && <button disabled={busy} onClick={() => saveBackup(backup)}>重新下载覆盖范围备份与恢复信息</button>}
    {backup && written && <button disabled={busy} onClick={() => { if (window.confirm('用本次备份恢复覆盖区域？')) void operation(async () => { await writeVerified(loader.current!, backup.bytes, backup.address, (phase, value) => setStatus(`恢复${phase} · ${Math.round(value * 100)}%`)); setStatus('备份范围已恢复并回读一致。关闭后按RESET重启。'); }); }}>恢复本次覆盖范围</button>}
    {status && <p role="status">{status}</p>}{error && <p role="alert" className="settings-error">{error}</p>}
    <div className="dialog-actions"><button disabled={busy} onClick={close}>关闭</button></div>
  </Dialog>;
}
