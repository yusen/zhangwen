import { useState } from 'react';
import type { CreatePersonalModule, HardwareDetail, HardwareSummary } from '../../../packages/contracts/src/platform';
import { api } from './api';
import { Dialog } from './Dialog';
import { referenceFile } from './ProjectReferences';

export function PersonalModuleDialog({ boardId, boards, source = '', onCreated, onClose }: {
  boardId: string; boards: HardwareSummary[]; source?: string; onCreated: (item: HardwareDetail) => void; onClose: () => void;
}) {
  const [form, setForm] = useState<CreatePersonalModule>({ name: '', category: 'SENSOR', description: '', voltage: 0, logicLevel: 0, protocol: 'UNKNOWN', boardId, code: '', notes: source });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const update = <K extends keyof CreatePersonalModule>(key: K, value: CreatePersonalModule[K]) => setForm(current => ({ ...current, [key]: value }));
  const save = async () => {
    setBusy(true); setError('');
    try { onCreated(await api<HardwareDetail>('/personal-modules', 'POST', form)); }
    catch (e) { setError(e instanceof Error ? e.message : String(e)); }
    finally { setBusy(false); }
  };
  return <Dialog title="新建我的模块" onClose={onClose} className="reference-dialog">
    <p className="muted">先填写名称与类别，接线和程序可在创建后补充。</p>
    <fieldset disabled={busy} className="reference-form"><legend>模块档案</legend>
      <label>模块名称与完整型号<input aria-label="我的模块名称" maxLength={80} value={form.name} onChange={e => update('name', e.target.value)} /></label>
      <label>分类<select value={form.category} onChange={e => update('category', e.target.value as CreatePersonalModule['category'])}>{[['SENSOR','传感器'],['ACTUATOR','执行器'],['DISPLAY','显示'],['POWER','电源'],['STRUCTURE','结构件']].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label className="reference-file-button">导入资料（选填）<input aria-label="导入我的模块资料" type="file" accept=".txt,.md,.py,.json,.csv,.pdf,.docx" onChange={event => { const file = event.target.files?.[0]; event.target.value = ''; if (!file) return; setBusy(true); setError(''); void referenceFile(file).then(input => api<{ text: string }>('/reference-preview', 'POST', input)).then(result => { if (result.text.length > 20000) throw new Error('模块说明超过2万字，请先在项目资料中导入全文，再将关键参数与案例粘贴到这里。'); update('notes', result.text); if (/\.py$/i.test(file.name) && result.text.length <= 16000) update('code', result.text); }).catch(e => setError(String(e))).finally(() => setBusy(false)); }} /></label>
      {form.notes && <p role="status">已添加资料 · {form.notes.length} 字</p>}
      <details><summary>查看或粘贴资料原文</summary>      <label>资料原文与来源（最多2万字）<textarea aria-label="我的模块资料原文" maxLength={20000} rows={7} value={form.notes} onChange={e => update('notes', e.target.value)} /></label></details>
      <details className="personal-optional"><summary>补充已知参数与案例（选填）</summary>      <label>用途、接线及硬件版本<textarea maxLength={2000} rows={3} value={form.description} onChange={e => update('description', e.target.value)} /></label>
      <div className="reference-form-grid"><label>供电（V，未知留空）<input type="number" min={0} max={1000} step="any" value={form.voltage || ''} onChange={e => update('voltage', Number(e.target.value))} /></label><label>信号电平（V，未知留空）<input type="number" min={0} max={1000} step="any" value={form.logicLevel || ''} onChange={e => update('logicLevel', Number(e.target.value))} /></label></div>
      <label>通信接口<select value={form.protocol} onChange={e => update('protocol', e.target.value)}>{[['UNKNOWN','待确认'],['GPIO_DIGITAL','数字 GPIO'],['ADC','模拟 ADC'],['PWM','PWM'],['I2C','I²C'],['UART','UART'],['SPI','SPI'],['SINGLE_WIRE_TRIG_ECHO','单线测距']].map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label>
      <label>示例适用主控<select value={form.boardId} onChange={e => update('boardId', e.target.value)}><option value="">暂不添加主控案例</option>{boards.map(board => <option key={board.componentId} value={board.componentId}>{board.displayName}</option>)}</select></label>
      <label>已知可参考的 MicroPython 程序<textarea maxLength={16000} rows={5} spellCheck={false} value={form.code} onChange={e => update('code', e.target.value)} /></label>
</details>
    </fieldset>
    {error && <p role="alert">{error}</p>}<div className="reference-actions"><button disabled={busy} onClick={onClose}>取消</button><button className="primary" disabled={busy || !form.name.trim() || form.notes.length > 20000 || (!!form.code.trim() && !form.boardId)} onClick={() => void save()}>{busy ? '正在保存…' : '创建模块'}</button></div>
  </Dialog>;
}
