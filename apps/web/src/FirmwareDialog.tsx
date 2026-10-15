import { useEffect, useRef, useState } from 'react';
import type { ESPLoader, Transport } from 'esptool-js';
import type { FirmwareProfile, HardwareSummary } from '../../../packages/contracts/src/mu';
import { api } from './api';
import { Dialog } from './Dialog';
import { BoardArtwork } from './BoardArtwork';
import { sha256 } from './serial';
import { backupFirmware, checkImage, persistFirmwareBackup, writeVerified, type FirmwareBackup } from './firmware';

export function FirmwareDialog({ board, onClose, onBusy, download }: { board: HardwareSummary; onClose: () => void; onBusy: (value: boolean) => void; download: (name: string, value: string | Uint8Array) => void }) {
  const [profile, setProfile] = useState<FirmwareProfile | null>(null);
  const [file, setFile] = useState<{ name: string; bytes: Uint8Array; hash: string } | null>(null);
  const [offset, setOffset] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('');
  const [identity, setIdentity] = useState('');
  const [backup, setBackup] = useState<FirmwareBackup | null>(null);
  const [downloaded, setDownloaded] = useState(false);
  const [confirmed, setConfirmed] = useState(false);
  const [written, setWritten] = useState(false);
  const [capacity, setCapacity] = useState(0);
  const loader = useRef<ESPLoader | null>(null);
  const transport = useRef<Transport | null>(null);
  const release = useRef<(() => void) | null>(null);
  const active = useRef(true);
  const working = useRef(false);
  const nativeSerial = (navigator as Navigator & { serial?: { requestPort(): Promise<ConstructorParameters<typeof Transport>[0]> } }).serial;
  const operation = async (task: () => Promise<void>) => {
    if (working.current) return;
    working.current = true; setBusy(true); onBusy(true); setError('');
    try { await task(); } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { working.current = false; setBusy(false); onBusy(false); }
  };
  const disconnect = async () => {
    try { await transport.current?.disconnect(); } finally { transport.current = null; loader.current = null; release.current?.(); release.current = null; }
  };
  useEffect(() => {
    active.current = true;
    void api<FirmwareProfile>('/firmware/' + board.componentId).then(value => { if (active.current) { setProfile(value); setOffset('0x' + value.offset.toString(16)); } }).catch(err => { if (active.current) setError(String(err)); });
    return () => { active.current = false; void disconnect(); };
  }, [board.componentId]);
  const close = () => { if (!working.current) void operation(async () => { await disconnect(); onClose(); }); };
  const connect = async () => {
    if (!nativeSerial || !navigator.locks || !profile || !file) return;
    // Keep requestPort directly in the user's click gesture.
    const portPromise = nativeSerial.requestPort();
    await operation(async () => {
      const port = await portPromise;
      await new Promise<void>((resolve, reject) => {
        void navigator.locks.request('zhangwen-web-serial', { ifAvailable: true }, async lock => {
          if (!lock) { reject(new Error('另一标签正在使用串口，请先断开。')); return; }
          const held = new Promise<void>(done => { release.current = done; });
          try {
            const esp = await import('esptool-js');
            transport.current = new esp.Transport(port);
            const next = new esp.ESPLoader({ transport: transport.current, baudrate: 115200, romBaudrate: 115200, terminal: { clean() {}, write() {}, writeLine: value => { if (active.current) setStatus(value); } } });
            loader.current = next;
            await next.main();
            if (next.chip.CHIP_NAME !== profile.chip) throw new Error(`检测到 ${next.chip.CHIP_NAME}，与当前主控 ${profile.chip} 不一致，已阻止写入。`);
            const size = await next.getFlashSize() * 1024; setCapacity(size); setIdentity(`${next.chip.CHIP_NAME} · ${size / 1024 / 1024} MiB`);
            setStatus('芯片已识别，尚未刷写。请先备份覆盖范围。'); resolve(); await held;
          } catch (err) { reject(err); await disconnect(); }
        }).catch(reject);
      });
    });
  };
  return <Dialog title="固件刷入" onClose={close} className="firmware-dialog">
    <div className="firmware-board"><BoardArtwork board={board} /><div><strong>{board.displayName}</strong><p>{profile?.chip ?? '读取配置…'} · 使用此板专用的完整固件</p></div></div>
    <p className="firmware-warning">刷入固件会覆盖指定 Flash 区域，可能影响设备程序和数据。先保存项目并备份设备文件。此入口不执行整片擦除；备份只涵盖本次写入范围。</p>
    {profile && <a href={profile.documentation} target="_blank" rel="noreferrer">查看当前主控的官方固件与说明</a>}
    <label className="field">选择完整固件 .bin<input type="file" accept=".bin" disabled={busy || !!identity} onChange={event => {
      const selected = event.target.files?.[0]; if (!selected || !profile) return;
      setFile(null); setBackup(null); setConfirmed(false); setWritten(false); setDownloaded(false);
      void operation(async () => {
        if (!selected.name.toLowerCase().endsWith('.bin') || selected.size > 16 * 1024 * 1024) throw new Error('请选择不超过16MiB的 .bin 文件。');
        const bytes = new Uint8Array(await selected.arrayBuffer()); checkImage(bytes, profile, Number(offset));
        setFile({ name: selected.name, bytes, hash: await sha256(bytes) }); setStatus('文件和芯片头检查通过，尚未访问设备。');
      });
    }} /></label>
    <label className="field">写入偏移<input value={offset} disabled={busy || !!identity} onChange={event => { setOffset(event.target.value); setFile(null); setBackup(null); setConfirmed(false); }} placeholder="0x1000 或 0x0，以官方固件说明为准" /></label>
    <p className="muted">ESP32 常用 0x1000；带前导填充的合并包使用 0x0。ESP32-S3/C3 通常为 0x0。仅支持包含 bootloader 的完整镜像，不支持单独 app 分区。</p>
    <p className="muted">识别前按主控说明进入下载模式（通常按住 BOOT 再按 RESET）。进入下载模式会中断原程序；写入期间请勿拔线或关闭页面。</p>
    {file && <p className="checksum">{file.name} · {file.bytes.length} bytes<br />SHA-256：{file.hash}</p>}
    {!identity && <button className="primary" disabled={!file || !profile || busy || !nativeSerial || !navigator.locks} onClick={() => void connect()}>选择设备并识别芯片</button>}
    {identity && <>
      <p>实际设备：<strong>{identity}</strong></p>
      {!backup && <button disabled={busy || !file || !profile} onClick={() => void operation(async () => {
        const saved = await backupFirmware(loader.current!, profile!, file!.bytes, Number(offset), capacity, value => setStatus(`备份读取 · ${Math.round(value * 100)}%`));
        await persistFirmwareBackup(saved); setBackup(saved); setStatus('覆盖范围已备份到本浏览器。下载备份后再确认刷写。');
      })}>备份将覆盖的 Flash 区域</button>}
      {backup && <>
        <button disabled={busy} onClick={() => { download(`flash-backup-${backup.chip}-${backup.id}.bin`, backup.bytes); download(`flash-backup-${backup.id}.json`, JSON.stringify({ ...backup, bytes: undefined, size: backup.bytes.length }, null, 2)); setDownloaded(true); }}>下载原固件范围备份及恢复信息</button>
        <label className="confirm"><input type="checkbox" checked={confirmed} disabled={busy || written || !downloaded} onChange={event => setConfirmed(event.target.checked)} />我已保存备份，核对实际板型、固件来源和偏移，确认覆盖此范围。</label>
        <button className="primary" disabled={busy || written || !confirmed || !file} onClick={() => void operation(async () => {
          setWritten(true);
          await writeVerified(loader.current!, file!.bytes, Number(offset), (phase, value) => setStatus(`${phase} · ${Math.round(value * 100)}%`));
          setStatus('固件写入后 SHA-256 回读一致，尚未验收 MicroPython 功能。关闭后按设备 RESET 键，再连接设备检查。');
        })}>确认刷入固件</button>
        {written && <button disabled={busy} onClick={() => { if (window.confirm('用刚才的备份恢复本次覆盖区域？其他区域不在此备份内。')) void operation(async () => { await writeVerified(loader.current!, backup.bytes, backup.address, (phase, value) => setStatus(`恢复${phase} · ${Math.round(value * 100)}%`)); setStatus('备份范围已恢复并回读一致。关闭后按 RESET 重启。'); setWritten(false); setConfirmed(false); }); }}>恢复本次覆盖范围</button>}
      </>}
    </>}
    {status && <p role="status">{status}</p>}{error && <p role="alert" className="settings-error">{error}</p>}
    <div className="dialog-actions"><button disabled={busy} onClick={close}>关闭</button></div>
  </Dialog>;
}
