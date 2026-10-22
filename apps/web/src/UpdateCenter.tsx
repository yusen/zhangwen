import { useEffect, useRef, useState } from 'react';
import { Check, Download, LoaderCircle, RefreshCw } from 'lucide-react';
import type { InstallUpdate, PlatformUpdate } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { Dialog } from './Dialog';
import { ToolbarButton } from './ToolbarButton';

function ReleaseNotes({ title, version, notes }: { title: string; version: string | null; notes: string[] }) {
  return <section className="update-release-notes" aria-label={title}>
    <h4>{title}{version && <span>{version}</span>}</h4>
    {notes.length ? <ul>{notes.map((note, index) => <li key={index}>{note}</li>)}</ul> : <p className="muted">此版本未提供更新说明。</p>}
  </section>;
}

export function UpdateCenter({ enabled, blocked, unsaved }: { enabled: boolean; blocked: boolean; unsaved: boolean }) {
  const [info, setInfo] = useState<PlatformUpdate | null>(null);
  const [open, setOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const [requesting, setRequesting] = useState(false);
  const [error, setError] = useState('');
  const [confirmed, setConfirmed] = useState(false);
  const alive = useRef(true);
  const checkingRef = useRef(false);
  const hasChecked = useRef(false);
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  async function check() {
    if (checkingRef.current) return;
    checkingRef.current = true; hasChecked.current = true;
    setChecking(true); setError(''); setConfirmed(false);
    try { const result = await api<PlatformUpdate>('/updates/check', 'POST'); if (alive.current) setInfo(result); }
    catch (err) { if (alive.current) setError(err instanceof Error ? err.message : '检查更新失败，请稍后重试。'); }
    finally { checkingRef.current = false; if (alive.current) setChecking(false); }
  }
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    void api<PlatformUpdate>('/updates').then(result => {
      if (cancelled) return;
      setInfo(current => current ?? result);
      // Only managed installations check automatically; no silent installation.
      if (result.deployment === 'managed' && result.state === 'unchecked' && !hasChecked.current) void check();
    }).catch(() => { /* Explicit opening offers a retry and an error. */ });
    return () => { cancelled = true; };
  }, [enabled]);
  const installing = info?.job?.state === 'installing';
  useEffect(() => {
    if (!installing) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout>;
    const poll = async () => {
      try { const result = await api<PlatformUpdate>('/updates'); if (!cancelled) { setInfo(result); setError(''); } }
      catch { if (!cancelled) setError('暂时无法读取更新进度；请保持服务运行，稍后重试。'); }
      if (!cancelled) timer = setTimeout(() => void poll(), 2000);
    };
    timer = setTimeout(() => void poll(), 1500);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [installing]);
  const ready = info?.job?.state === 'ready';
  const available = info?.state === 'available' && !ready;
  async function install() {
    if (!info?.canInstall || !info.checkToken || !info.latestRevision || !confirmed || blocked || unsaved) return;
    setRequesting(true); setError('');
    try {
      const body: InstallUpdate = { revision: info.latestRevision, checkToken: info.checkToken, confirmed: true };
      setInfo(await api<PlatformUpdate>('/updates/install', 'POST', body)); setConfirmed(false);
    } catch (err) { setError(err instanceof Error ? err.message : '无法开始更新。'); }
    finally { setRequesting(false); }
  }
  const actions = <div className="update-actions"><button onClick={() => setOpen(false)}>{unsaved ? '返回保存' : '稍后再说'}</button><button disabled={checking || installing || requesting} onClick={() => void check()}><RefreshCw size={16} />{checking ? '检查中…' : '重新检查'}</button>{info?.canInstall && !installing && !ready && <button className="primary" disabled={!confirmed || unsaved || blocked || checking || requesting} onClick={() => void install()}><Download size={16} />{requesting ? '正在提交…' : '确认更新'}</button>}</div>;
  return <>
    <ToolbarButton icon={installing ? LoaderCircle : RefreshCw} label="检查更新" variant={available || ready ? 'brand' : 'muted'} active={open} disabled={!enabled} hint={installing ? '安装中' : ready ? '待重启' : available ? '有更新' : undefined} title={ready ? '新版本已安装，下次启动生效' : available ? '发现新版本，点击查看' : '检查平台更新'} onClick={() => { setOpen(true); if (!info || info.state === 'unchecked') void check(); }} />
    {open && <Dialog title="平台更新" onClose={() => setOpen(false)} className="update-dialog" footer={actions}>
      <div className="update-summary"><span className="mode-mark">{installing || checking ? <LoaderCircle className="spin" size={25} /> : ready || info?.state === 'current' ? <Check size={25} /> : <RefreshCw size={25} />}</span><div><h3 data-dialog-autofocus tabIndex={-1}>{installing ? '正在安装更新' : ready ? '下次启动使用新版本' : checking ? '正在检查更新' : available ? '发现新版本' : '掌问本地平台'}</h3><p>{info?.deployment === 'managed' ? '一键部署版本 · Windows / macOS' : '本地开发工作区'}</p></div></div>
      <dl className="update-versions"><dt>当前版本</dt><dd>{info?.currentVersion ?? (info?.deployment === 'managed' ? '旧版（未标注版本号）' : '开发版本')}</dd><dt>线上版本</dt><dd>{info?.latestVersion ?? (info?.latestRevision ? '旧版（未标注版本号）' : '尚未检测')}</dd>{info?.checkedAt && <><dt>上次检查</dt><dd>{new Date(info.checkedAt).toLocaleString()}</dd></>}</dl>
      <p role="status" className="update-message">{checking ? '正在获取版本信息…' : info?.job?.message ?? info?.message ?? '点击下方按钮检查最新版本。'}</p>
      {error && <p className="settings-error" role="alert">{error}</p>}
      {info && <>
        {info.latestRevision && info.latestVersion !== info.currentVersion && <ReleaseNotes title="线上版本更新说明" version={info.latestVersion} notes={info.latestReleaseNotes ?? []} />}
        <ReleaseNotes title="当前版本更新说明" version={info.currentVersion} notes={info.currentReleaseNotes ?? []} />
      </>}
      {info?.deployment === 'managed' && !ready && !installing && available && <><p className="muted">确认后下载并校验新版本，环境准备成功才切换启动版本。项目与 API 设置保留；当前服务继续运行，下次启动生效。</p>{(unsaved || blocked) && <p className="update-save-hint">{unsaved ? '请先返回工作台保存项目和代码。' : '请等待当前任务完成，并停止设备程序后再更新。'}</p>}<label className="confirm"><input type="checkbox" checked={confirmed} onChange={event => setConfirmed(event.target.checked)} disabled={unsaved || blocked || requesting} />我已保存项目，确认安装新版本。</label></>}
      {ready && <p className="update-save-hint">保存项目后，关闭原服务窗口，再从 Windows 桌面图标或 macOS「启动掌问.command」打开。仅刷新网页不会重启服务。</p>}
    </Dialog>}
  </>;
}
