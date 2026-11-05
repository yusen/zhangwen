import { useState } from 'react';
import type { HardwareDetail } from '../../../packages/contracts/src/platform';
import { api } from './api';

export function PersonalModuleFacts({ detail, onSaved, startOpen = false }: { detail: HardwareDetail; onSaved: (value: HardwareDetail) => void; startOpen?: boolean }) {
  const [voltage, setVoltage] = useState(detail.specification.electrical.voltage);
  const [logic, setLogic] = useState(detail.specification.electrical.logicLevel);
  const [protocol, setProtocol] = useState(detail.specification.electrical.communicationProtocol);
  const [busy, setBusy] = useState(false); const [error, setError] = useState(''); const [saved, setSaved] = useState(false);
  return <details open={startOpen}><summary>维护我的模块参数</summary><fieldset className="reference-form" disabled={busy}><legend>依据资料补充，未知留空</legend>
    <label>供电电压（V）<input type="number" min={0} max={1000} step="any" value={voltage || ''} onChange={e => { setVoltage(Number(e.target.value)); setSaved(false); }} /></label>
    <label>信号电平（V）<input type="number" min={0} max={1000} step="any" value={logic || ''} onChange={e => { setLogic(Number(e.target.value)); setSaved(false); }} /></label>
    <label>通信接口<input maxLength={80} value={protocol} onChange={e => { setProtocol(e.target.value); setSaved(false); }} /></label>
    <button disabled={!protocol.trim()} onClick={() => { setBusy(true); setError(''); void api<HardwareDetail>(`/personal-modules/${detail.skillName}/facts`, 'PUT', { expectedRevision: detail.revision, voltage, logicLevel: logic, protocol }).then(value => { onSaved(value); setSaved(true); }).catch(e => setError(String(e))).finally(() => setBusy(false)); }}>{busy ? '正在保存…' : '保存模块参数'}</button>
    {error && <p role="alert">{error}</p>}{saved && <p role="status">参数已保存，相关核实记录请查看是否需要复核。</p>}
  </fieldset></details>;
}
