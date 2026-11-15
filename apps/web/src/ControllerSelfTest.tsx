import { useEffect, useState } from 'react';
import type { ControllerSelfTest as Report } from '../../../packages/contracts/src/channels';
import { Dialog } from './Dialog';
import { MicroPythonDevice } from './serial';
import { MICROBIT_BOARD, selfTestPrograms } from './controllerDiagnostics';

export function ControllerSelfTest({ boardId, scope, device, onClose, onLoadCode }: {
  boardId: string; scope: string; device: MicroPythonDevice | null; onClose: () => void; onLoadCode?: (code: string) => void;
}) {
  const key = `zhangwen-controller-check:${scope}:${boardId}`;
  const [report, setReport] = useState<Report | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  useEffect(() => {
    try { const value: unknown = JSON.parse(localStorage.getItem(key) ?? 'null'); if (value && typeof value === 'object' && 'boardId' in value && value.boardId === boardId && 'checks' in value && Array.isArray(value.checks) && 'identity' in value && typeof value.identity === 'object' && value.identity && 'uniqueId' in value.identity && 'observed' in value && ['unconfirmed','passed','failed'].includes(String(value.observed)) && 'note' in value && typeof value.note === 'string' && 'checkedAt' in value && typeof value.checkedAt === 'string' && value.checks.every(item=>item && typeof item.label==='string' && typeof item.detail==='string' && ['passed','failed','unavailable'].includes(item.status))) setReport(value as Report); } catch { /* no prior evidence */ }
  }, [key, boardId]);
  const save = (value: Report) => { setReport(value); try { localStorage.setItem(key, JSON.stringify(value)); } catch { setError('自检结果已显示，但浏览器记录保存失败；请复制结果。'); } };
  const fresh = report && device?.identity?.uniqueId === report.identity.uniqueId && report.connectionId === device?.connectionId && ['connected','running'].includes(device.state);
  return <Dialog title="主控自检" onClose={() => { if (!busy) onClose(); }} className="controller-self-test">
    <p>开发顺序：主控自检 → 逐项测试模块 → 联合运行。自检只执行下方固定读取程序，不覆盖项目或设备文件。</p>
    <p className="muted">请先停止当前程序。接口读数只能证明本次调用返回，点阵、屏幕、接线和实物功能须单独观察。</p>
    <button className="primary" disabled={busy || device?.state !== 'connected'} onClick={() => {
      setBusy(true); setError('');
      void device!.selfTest(boardId).then(save).catch(err => setError(err instanceof Error ? err.message : String(err))).finally(() => setBusy(false));
    }}>{busy ? '正在自检…' : '执行主控自检'}</button>
    {device?.state !== 'connected' && !busy && <p role="status">先在当前开发通道连接设备，并停止程序。</p>}
    {error && <p role="alert" className="settings-error">{error}</p>}
    {report && <section aria-label="主控自检结果">
      <p><strong>{fresh ? '本次连接的接口结果' : '历史接口记录 · 需重新自检'}</strong> · {new Date(report.checkedAt).toLocaleString()}</p>
      <ul>{report.checks.map(item => <li key={item.id}><strong>{item.label}：{item.status === 'passed' ? '读取通过' : item.status === 'failed' ? '未通过' : '接口不可用'}</strong><p>{item.detail}</p></li>)}</ul>
      <label>实际观察<select aria-label="主控自检实际观察" value={report.observed} disabled={!fresh || busy} onChange={event => save({ ...report, observed: event.target.value as Report['observed'] })}><option value="unconfirmed">尚未确认</option><option value="passed">已观察，符合预期</option><option value="failed">已观察，存在异常</option></select></label>
      <label>观察说明<textarea aria-label="主控自检观察说明" value={report.note} maxLength={2000} disabled={!fresh || busy} onChange={event => save({ ...report, note: event.target.value })}/></label>
      <p className="muted">记录保存在当前浏览器，按项目、通道和主控区分。</p>
    </section>}
    {boardId === MICROBIT_BOARD && onLoadCode && <button disabled={busy} onClick={() => { onLoadCode('# micro:bit 点阵自检：显示笑脸600毫秒后清屏，无外接模块。\nfrom microbit import display, Image, sleep\ndisplay.show(Image.HAPPY)\nsleep(600)\ndisplay.clear()\nprint("MICROBIT_DISPLAY_TEST_RETURNED")\n'); onClose(); }}>载入点阵测试程序</button>}
    <details><summary>查看固定自检程序</summary>{selfTestPrograms(boardId).map(item => <div key={item.id}><strong>{item.label}</strong><pre>{item.code}</pre></div>)}</details>
  </Dialog>;
}
