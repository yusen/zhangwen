import { useState } from 'react';
import type { HardwareDetail, HardwareSummary, SaveHardwareVerification } from '../../../packages/contracts/src/platform';
import { api } from './api';

export const verifiedBoardNames = (item: HardwareSummary, boards: HardwareSummary[]) => (item.verifiedBoardIds ?? [])
  .map(id => (boards.find(board => board.componentId === id)?.displayName ?? id).replace(/（[^）]*）/g, '').trim()).join('、');

export function HardwareVerification({ detail, board, boards, onSaved }: {
  detail: HardwareDetail; board?: HardwareSummary; boards: HardwareSummary[]; onSaved: (value: HardwareDetail) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [selected, setSelected] = useState(detail.verifiedBoardIds ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const names = verifiedBoardNames(detail, boards);
  const changed = JSON.stringify([...selected].sort()) !== JSON.stringify([...(detail.verifiedBoardIds ?? [])].sort());
  const reset = () => { setSelected(detail.verifiedBoardIds ?? []); setError(''); setEditing(false); };
  const save = async () => {
    setSaving(true); setError('');
    try {
      const value = await api<HardwareDetail>(`/hardware/${detail.skillName}/verification`, 'PUT', {
        expectedRevision: detail.revision, verifiedBoardIds: selected,
      } satisfies SaveHardwareVerification);
      onSaved(value); setSelected(value.verifiedBoardIds ?? []); setEditing(false);
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setSaving(false); }
  };
  return <section className="sensor-section module-verification" aria-label="模块核实状态">
    <div className="module-example-head"><h3>已核实主控</h3><button type="button" disabled={saving} onClick={() => { if (editing) reset(); else { setSelected(detail.verifiedBoardIds ?? []); setEditing(true); } }}>{editing ? '取消修改' : '修改核实状态'}</button></div>
    <p className="module-verification-summary">{names || '尚未标记已核实主控'}</p>
    {board && <p className="muted">当前主控：{board.displayName} · {detail.verifiedBoardIds?.includes(board.componentId) ? '已核实' : '未核实'}</p>}
    {editing && <>
      <fieldset className="module-supported-boards" disabled={saving}>
        <legend>已核实的主控（可多选）</legend>
        <div>{boards.map(item => <label key={item.componentId}><input type="checkbox" checked={selected.includes(item.componentId)} onChange={event => setSelected(ids => event.target.checked ? [...ids, item.componentId] : ids.filter(id => id !== item.componentId))} /><span>{item.displayName}</span></label>)}</div>
        <p>按实际联调结果勾选，取消勾选即可改为未核实。此处是你的核实记录，不会自动测试设备。</p>
      </fieldset>
      <div className="module-example-actions"><small className="muted">只保存核实状态，代码与支持范围分别维护。</small><button className="primary" type="button" disabled={saving || !changed} onClick={() => void save()}>{saving ? '正在保存…' : '保存核实状态'}</button></div>
      {error && <p role="alert" className="module-example-error">{error}</p>}
    </>}
  </section>;
}
