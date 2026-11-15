import { useState } from 'react';
import type { HardwareDetail, HardwareSummary, HardwareVerificationRecord, SaveHardwareVerification } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { verificationDimensions, verificationLabels, verificationSummary } from './hardwareVerificationState';
import { guideLabels, renderGuideText } from './moduleExamples';

export const verifiedBoardNames = (item: HardwareSummary, boards: HardwareSummary[]) => (item.verifiedBoardIds ?? [])
  .map(id => (boards.find(board => board.componentId === id)?.displayName ?? id).replace(/（[^）]*）/g, '').trim()).join('、');
type View = 'summary' | 'details' | 'test';
export function HardwareVerification({ detail, board, boards, onSaved, view = 'details', onNavigate, onEditExample }: {
  detail: HardwareDetail; board?: HardwareSummary; boards: HardwareSummary[]; onSaved: (value: HardwareDetail) => void;
  view?: View; onNavigate?: (value: View) => void; onEditExample?: () => void;
}) {
  const rows = (detail.verificationRecords ?? []).filter(row => row.boardId === board?.componentId);
  const functional = rows.find(row => row.dimension === 'function');
  const example = detail.localExamples?.find(row => row.boardId === board?.componentId);
  const guide = detail.moduleGuides?.find(row => row.boardId === board?.componentId);
  const wiringText = example?.notes || (guide ? guide.connections.map(row => row.signal + ' → ' + renderGuideText(row.target, guideLabels(guide, example?.setup))).join('\n') : '');
  const [editing, setEditing] = useState(view === 'test');
  const [dimension, setDimension] = useState<HardwareVerificationRecord['dimension']>('function');
  const [state, setState] = useState<HardwareVerificationRecord['state'] | ''>(view === 'test' ? '' : 'pending');
  const [notes, setNotes] = useState(functional?.notes ?? '');
  const [firmware, setFirmware] = useState(functional?.firmware ?? rows.find(row => row.dimension === 'driver')?.firmware ?? '');
  const [wiring, setWiring] = useState(functional?.wiring ?? (wiringText.length <= 1500 ? wiringText : ''));
  const [evidence, setEvidence] = useState('');
  const [saving, setSaving] = useState(false); const [error, setError] = useState('');
  const [conditionsOpen, setConditionsOpen] = useState(!functional?.firmware || !functional?.wiring);
  const summary = verificationSummary(detail, board?.componentId);
  const begin = (key: HardwareVerificationRecord['dimension']) => {
    const row = rows.find(r => r.dimension === key);
    setDimension(key); setState(row?.state ?? 'pending'); setNotes(row?.notes ?? '');
    setFirmware(row?.firmware ?? ''); setWiring(row?.wiring ?? (wiringText.length <= 1500 ? wiringText : ''));
    setEvidence(row?.evidence ?? ''); setEditing(true); setError(''); setConditionsOpen(!row?.firmware || !row?.wiring);
  };
  const save = async () => {
    if (!board || !state || saving) return;
    setSaving(true); setError('');
    try {
      const value = await api<HardwareDetail>(`/hardware/${detail.skillName}/verification`, 'PUT', {
        expectedRevision: detail.revision, record: { boardId: board.componentId, dimension, state, notes, firmware, wiring, evidence },
      } satisfies SaveHardwareVerification);
      onSaved(value); setEditing(false); if (view === 'test') onNavigate?.('summary');
    } catch (e) { setError(e instanceof Error ? e.message : String(e)); setConditionsOpen(true); } finally { setSaving(false); }
  };
  if (view === 'summary') {
    const relevant = rows.filter(row => ['electrical','wiring','driver','function'].includes(row.dimension));
    const stale = relevant.some(row => row.stale && row.state !== 'unverified');
    const failed = relevant.some(row => !row.stale && row.state === 'failed');
    const label = stale ? '需复核' : failed ? '测试异常' : functional?.state === 'passed' ? '用户实测通过' : '待测试';
    return <section className="resource-test-summary" aria-label="模块核实状态"><div><small>功能测试 · {board?.displayName ?? '请先选择主控'}</small><strong className={`verification-badge ${stale ? 'pending' : failed ? 'failed' : functional?.state ?? 'unverified'}`}>{label}</strong></div><div className="reference-actions"><button disabled={!board} onClick={() => onNavigate?.('test')}>记录测试结果</button><button onClick={() => onNavigate?.('details')}>核实详情</button></div></section>;
  }
  const needsConditions = ['driver', 'function'].includes(dimension) && (state === 'passed' || state === 'failed');
  return <section className="sensor-section" aria-label="模块核实记录">
    <h3>{view === 'test' ? '记录测试结果' : '核实详情'} · {board?.displayName ?? '请先选择主控'}</h3>
    {view === 'details' && <><p className={`verification-badge ${summary.tone}`}>{summary.text}</p><div className="verification-rows">{Object.entries(verificationDimensions).map(([key, label]) => {
      const row = rows.find(r => r.dimension === key);
      return <div className="verification-row" key={key}><strong>{label}</strong><span className={`verification-badge ${row?.stale ? 'pending' : row?.state ?? 'unverified'}`}>{row?.stale ? '需复核' : row ? row.state === 'passed' && !['driver','function'].includes(key) ? '用户核对通过' : verificationLabels[row.state] : '未核实'}</span><button disabled={!board || saving} onClick={() => begin(key as HardwareVerificationRecord['dimension'])}>记录{label}</button>{row && <details><summary>查看条件与依据</summary><p>{new Date(row.updatedAt).toLocaleString()}<br />固件/库：{row.firmware || '未记录'}<br />接线：{row.wiring || '未记录'}</p><pre>{row.evidence}</pre><p>{row.notes}</p>{['driver','function'].includes(key) && <small>案例摘要：{row.codeHash.slice(0,12)}</small>}</details>}</div>;
    })}</div></>}
    {editing && <fieldset disabled={saving} className="reference-form"><legend>{view === 'test' ? '本次功能测试' : verificationDimensions[dimension]}</legend>
      <p className="muted">当前案例：{example?.code.trim() ? '本机已保存' : '尚未保存测试代码'}{onEditExample && !example?.code.trim() && <button type="button" onClick={onEditExample}>编辑案例</button>}</p>
      <label>测试结果<select aria-label="核实结果" value={state} onChange={e => setState(e.target.value as typeof state)}>{view === 'test' ? <><option value="">请选择结果</option><option value="passed">正常</option><option value="failed">异常</option></> : Object.entries(verificationLabels).map(([value, label]) => <option key={value} value={value}>{value === 'passed' && !['driver','function'].includes(dimension) ? '用户核对通过' : label}</option>)}</select></label>
      <label>{view === 'test' ? '预期与实际现象' : '资料来源 / 测试现象'}<textarea aria-label="核实依据与现象" rows={3} maxLength={1500} value={evidence} onChange={e => setEvidence(e.target.value)} placeholder="例如预期显示温度，实际显示23℃；可粘贴串口输出。" /></label>
      <details className="test-conditions" open={conditionsOpen} onToggle={event => setConditionsOpen(event.currentTarget.open)}><summary>测试条件与备注{needsConditions && (!firmware.trim() || !wiring.trim()) ? ' · 请补充' : ' · 查看并核对'}</summary>
        <label className="reference-field">固件与库版本<input aria-label="核实固件与库" maxLength={150} value={firmware} onChange={e => setFirmware(e.target.value)} placeholder="不清楚版本请填写“未知”" /></label>
        <label className="reference-field">实际接线或测量条件<textarea aria-label="核实接线条件" rows={2} maxLength={1500} value={wiring} onChange={e => setWiring(e.target.value)} /></label>
        <label className="reference-field">适用范围与备注<textarea rows={2} maxLength={1500} value={notes} onChange={e => setNotes(e.target.value)} /></label>
      </details>
      <small className="muted">记录仅适用于上述主控、案例与条件；上传成功不能代替实际观察。</small>
      {error && <p role="alert">{error}</p>}<div className="reference-actions"><button onClick={() => { setEditing(false); if (view === 'test') onNavigate?.('summary'); }}>取消</button><button className="primary" disabled={!board || !state || (needsConditions && !example?.code.trim()) || (['documented','passed','failed'].includes(state) && !evidence.trim())} onClick={() => void save()}>保存核实记录</button></div>
    </fieldset>}
    {view === 'details' && <>
      {!!detail.verifiedBoardIds?.length && <details><summary>旧版主控标记</summary><p>{verifiedBoardNames(detail, boards)}。条件未记录，保留为历史标记。</p></details>}
      {(detail.verificationRecords ?? []).some(row => row.boardId !== board?.componentId) && <details><summary>其他主控记录</summary>{(detail.verificationRecords ?? []).filter(row => row.boardId !== board?.componentId).map(row => <p key={row.boardId+row.dimension}>{boards.find(b => b.componentId === row.boardId)?.displayName} · {verificationDimensions[row.dimension]} · {row.stale ? '需复核' : verificationLabels[row.state]}</p>)}</details>}
    </>}
  </section>;
}
