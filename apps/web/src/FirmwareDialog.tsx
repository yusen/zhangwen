import { useEffect, useRef, useState } from 'react';
import type { Transport } from 'esptool-js';
import type { FirmwareProfile, HardwareSummary } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { Dialog } from './Dialog';
import { BoardArtwork } from './BoardArtwork';
import { flashFirmware, loadDefaultFirmware } from './firmware';

export function FirmwareDialog({ board, onClose, onBusy }: { board: HardwareSummary; onClose: () => void; onBusy: (value: boolean) => void }) {
  const [profile, setProfile] = useState<FirmwareProfile | null>(null);
  const [file, setFile] = useState<Uint8Array | null>(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState('正在核对本地默认固件…');
  const [identity, setIdentity] = useState('');
  const [written, setWritten] = useState(false);
  const transport = useRef<Transport | null>(null);
  const active = useRef(true);
  const working = useRef(false);
  const nativeSerial = (navigator as Navigator & { serial?: { requestPort(): Promise<ConstructorParameters<typeof Transport>[0]> } }).serial;
  const disconnect = async () => {
    try { await transport.current?.disconnect(); } finally { transport.current = null; }
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
  const flash = () => {
    if (!nativeSerial || !navigator.locks || !profile || !file || working.current) return;
    // Port selection must begin in the button gesture. No backend serial access.
    const portPromise = nativeSerial.requestPort();
    void operation(async () => {
      const port = await portPromise;
      await navigator.locks.request('zhangwen-web-serial', { ifAvailable: true }, async lock => {
          if (!lock) throw new Error('另一标签正在使用串口，请先断开。');
          try {
            setIdentity(''); setStatus('正在识别设备芯片和 Flash 容量…');
            const esp = await import('esptool-js');
            transport.current = new esp.Transport(port);
            const peer = new esp.ESPLoader({ transport: transport.current, baudrate: 115200, romBaudrate: 115200, terminal: { clean() {}, write() {}, writeLine: value => { if (active.current) setStatus(value); } } });
            await peer.main();
            if (peer.chip.CHIP_NAME !== profile.chip) throw new Error(`检测到 ${peer.chip.CHIP_NAME}，与当前主控 ${profile.chip} 不一致，已阻止写入。`);
            const capacity = await peer.getFlashSize() * 1024;
            setIdentity(`${peer.chip.CHIP_NAME} · ${capacity / 1024 / 1024} MiB`);
            await flashFirmware(peer, profile, file, profile.offset, capacity, (phase, value) => setStatus(`${phase} · ${Math.round(value * 100)}%`));
            setWritten(true);
            setStatus('固件写入完成。关闭后按RESET重启，再连接检测MicroPython及板载功能。');
          } catch (err) {
            setStatus('固件刷入未完成，请核对错误后重新进入下载模式重试。');
            throw err;
          } finally {
            await disconnect();
          }
      });
    });
  };
  return <Dialog title="固件刷入" onClose={close} className="firmware-dialog">
    <div className="firmware-board"><BoardArtwork board={board} /><div><strong>{board.displayName}</strong><p>{profile?.image?.version ?? '读取板型配置…'}</p></div></div>
    <p className="firmware-warning">刷入会覆盖固件及部分设备程序、数据，不做备份和回读校验。点击下方按键直接刷入。</p>
    {profile?.image && <><p>默认固件：<strong>{profile.image.version}</strong> · {(profile.image.size / 1024 / 1024).toFixed(2)} MiB</p><p className="muted">{profile.image.notes}</p><a href={profile.image.sourceUrl} target="_blank" rel="noreferrer">官方来源与版本说明</a><details><summary>镜像校验信息</summary><p className="checksum">{profile.image.name} · 偏移 0x{profile.offset.toString(16)}<br />SHA-256：{profile.image.sha256}</p></details></>}
    <p className="muted">按主控说明进入下载模式（通常按住BOOT再按RESET），再点击刷入；写入期间请勿拔线或关闭页面。无需保存项目。</p>
    {!written && <button className="primary" disabled={!file || busy || !nativeSerial || !navigator.locks} onClick={flash}>一键刷入默认固件</button>}
    {identity && <p>实际设备：<strong>{identity}</strong></p>}
    {status && <p role="status">{status}</p>}{error && <p role="alert" className="settings-error">{error}</p>}
    <div className="dialog-actions"><button disabled={busy} onClick={close}>关闭</button></div>
  </Dialog>;
}
