import { useState } from 'react';
import type { HardwareDetail, HardwareSummary, SaveHardwareExample } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { guideCode, guideKind, guideLabels, guideValues, renderGuideText } from './moduleExamples';

export function HardwareExampleEditor({ detail, board, boards, startEditing, onSaved }: {
  detail: HardwareDetail; board?: HardwareSummary; boards: HardwareSummary[]; startEditing: boolean; onSaved: (value: HardwareDetail) => void;
}) {
  const saved = detail.localExamples?.find(item => item.boardId === board?.componentId);
  const guide = detail.moduleGuides?.find(item => item.boardId === board?.componentId);
  const otherExamples = detail.localExamples?.filter(item => item.boardId !== board?.componentId) ?? [];
  const initialSetup = guide ? guideValues(guide, saved?.setup) : {};
  const [editing, setEditing] = useState(startEditing);
  const [notes, setNotes] = useState(saved?.notes ?? '');
  const [setup, setSetup] = useState<Record<string, string>>(initialSetup);
  const [code, setCode] = useState(saved?.code ?? (guide ? guideCode(guide, initialSetup) : ''));
  const [supportedBoardIds, setSupportedBoardIds] = useState<string[]>(detail.supportedBoardIds ?? []);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const changed = notes !== (saved?.notes ?? '') || code !== (saved?.code ?? '')
    || (saved ? JSON.stringify(setup) !== JSON.stringify(initialSetup) : Boolean(guide))
    || JSON.stringify([...supportedBoardIds].sort()) !== JSON.stringify([...(detail.supportedBoardIds ?? [])].sort());
  const generated = guide ? guideCode(guide, setup) : '';
  const pins = Object.entries(setup).filter(([key]) => ['sig', 'sig2', 'sig3', 'rx', 'tx'].includes(key)).map(([, value]) => value);
  const pinError = new Set(pins).size < pins.length;
  const changeOption = (key: string, value: string) => {
    const next = { ...setup, [key]: value };
    // Preserve manual code. Only keep an untouched generated example in sync.
    if (guide && code === guideCode(guide, setup)) setCode(guideCode(guide, next));
    setSetup(next); setStatus('');
  };
  const save = async () => {
    if (!board || saving) return;
    setSaving(true); setError(''); setStatus('');
    try {
      const value = await api<HardwareDetail>(`/hardware/${detail.skillName}/example`, 'PUT', {
        boardId: board.componentId, notes, code, ...(guide ? { setup } : {}), supportedBoardIds, expectedRevision: detail.revision,
      } satisfies SaveHardwareExample);
      onSaved(value); setStatus('已保存，下次对话会自动参考；本次未上传或运行。');
    } catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setSaving(false); }
  };
  return <section className="sensor-section module-example" aria-label="我的模块案例">
    <div className="module-example-head"><h3>接线与案例</h3><button type="button" disabled={!board || saving} onClick={() => setEditing(value => !value)}>{editing ? '收起编辑' : '编辑案例'}</button></div>
    <p className="muted">当前编辑主控：{board?.displayName ?? '请先选择主控'}{saved ? ' · 已有本机案例' : guide ? ' · 内置参考可用' : ' · 尚无本机案例'}</p>
    <p className="muted" aria-label="案例来源">{saved ? '案例来源：当前主控的本机保存版本（优先用于对话）。' : guide ? '案例来源：当前主控的内置参考。' : '当前主控暂无可用案例。'}{otherExamples.length > 0 && ` 其他主控已有本机案例：${otherExamples.map(item => boards.find(b => b.componentId === item.boardId)?.displayName ?? item.boardId).join('、')}；代码与接线按主控分别保存。`}</p>
    {editing && <>
      <fieldset className="module-supported-boards" disabled={saving} aria-describedby="module-support-help">
        <legend>支持的主控（可多选）</legend>
        <div>{boards.map(item => <label key={item.componentId}>
          <input type="checkbox" checked={supportedBoardIds.includes(item.componentId)} onChange={event => {
            setSupportedBoardIds(ids => event.target.checked ? [...ids, item.componentId] : ids.filter(id => id !== item.componentId));
            setStatus('');
          }} />
          <span>{item.displayName}</span>
        </label>)}</div>
        <p id="module-support-help">标注模块的适配范围；各主控的代码与接线分别保存。未选择表示尚未标注。</p>
        {board && supportedBoardIds.length > 0 && !supportedBoardIds.includes(board.componentId)
          && <p>当前主控未勾选，仍可维护它的独立案例。</p>}
      </fieldset>
      {guide && <div className="module-guide" aria-label="模块接线选项">
        <span className={`module-guide-kind ${guide.kind}`}>{guideKind[guide.kind]}</span>
        <span className="module-guide-interface">{guideLabels(guide, setup).interface}</span>
        <p className="module-guide-summary">{guide.summary}</p>
        <div className="module-guide-fields">{guide.fields.filter(field => field.options.length > 1).map(field => <label key={field.key}>
          <span>{field.label}</span><select aria-label={field.label} value={setup[field.key]} disabled={saving} onChange={event => changeOption(field.key, event.target.value)}>
            {field.options.map(option => <option key={option.value} value={option.value}>{option.label}</option>)}
          </select>
        </label>)}</div>
        {pinError && <p role="alert" className="module-example-error">多路信号不能使用同一引脚，请分别选择。</p>}
        {guide.connections.length > 0 && <dl className="module-guide-wiring" aria-label="接线对应">{guide.connections.map(connection => <div key={connection.signal}><dt>{connection.signal}</dt><dd>{renderGuideText(connection.target, guideLabels(guide, setup))}</dd></div>)}</dl>}
        <details className="module-guide-help"><summary>使用说明与资料来源</summary><ul>{guide.notes.map((note, index) => <li key={index}>{note}</li>)}</ul>
          {guide.sources.map((url, index) => <a key={url} href={url} target="_blank" rel="noopener noreferrer">参考资料 {index + 1} ↗</a>)}
        </details>
      </div>}
      <label htmlFor="module-example-notes">补充说明（选填）</label>
      <textarea id="module-example-notes" aria-label="接线与使用备注" value={notes} disabled={saving} maxLength={2000} rows={notes.length > 140 ? 3 : 1} onChange={event => { setNotes(event.target.value); setStatus(''); }} placeholder="例如：固件版本、模块批次或实际测试现象" />
      {saved?.notes && !saved.setup && <small className="muted">已保留原备注；上面的默认选项只是建议，请按实际接线选择。</small>}
      {guide && code !== generated && <div className="module-guide-regenerate"><span>当前为自定义代码，修改接线不会覆盖它。</span><button type="button" disabled={saving} onClick={() => { setCode(generated); setStatus('已按当前选项载入内置示例，保存后生效。'); }}>按接线更新示例</button></div>}
      <label htmlFor="module-example-code">MicroPython 案例代码</label>
      <textarea id="module-example-code" className="module-example-code" value={code} disabled={saving} maxLength={16000} rows={9} spellCheck={false} onChange={event => { setCode(event.target.value); setStatus(''); }} placeholder="粘贴可参考的程序。保存后无需在每轮对话重新上传。" />
      <div className="module-example-actions"><small className="muted">保存支持主控与当前主控案例，供后续对话参考；保存不代表实测通过。</small><button type="button" className="primary" disabled={!board || saving || !changed || pinError} onClick={() => void save()}>{saving ? '正在保存…' : '保存案例'}</button></div>
      {error && <p className="module-example-error" role="alert">{error}</p>}{status && <p role="status">{status}</p>}
    </>}
  </section>;
}
