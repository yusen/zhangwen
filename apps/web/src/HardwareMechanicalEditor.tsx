import { useState } from 'react';
import type { HardwareDetail, SaveHardwareMechanical } from '../../../packages/contracts/src/platform';
import { api } from './api';

export function HardwareMechanicalEditor({ detail, onSaved }: { detail: HardwareDetail; onSaved: (value: HardwareDetail) => void }) {
  const [editing, setEditing] = useState(false);
  const [text, setText] = useState('');
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const doc = detail.files.find(f => f.path === 'references/mechanical.md')?.content ?? '';
  const start = () => {
    const profile = {...(detail.mechanicalProfile ?? {
      profile_id: 'module_' + detail.componentId.replace(/[^a-zA-Z0-9_]/g, '_'), display_name: detail.displayName,
      category: detail.category === 'MCU' ? 'controller' : 'module', roles: [],
      dimensions: {length_x: 0, width_y: 0, height_z: 0},
      coordinate_system: {origin: 'envelope_center', x_axis: 'length', y_axis: 'width', positive_z: 'height'},
      mounting: {mode: 'envelope_only', preferred_surface: 'base_floor', strategy: 'none', clearance: 0.8, holes: []},
      openings: [], keepouts: [], model_kind: 'envelope',
    })};
    delete profile.revision; delete profile.source;
    setText(JSON.stringify(profile, null, 2));
    setNotes(doc.match(/<!-- web-mechanical-notes -->\s*([\s\S]*?)\s*<!-- \/web-mechanical-notes -->/)?.[1] ?? '');
    setError(''); setEditing(true);
  };
  const save = async () => {
    setError('');
    try {
      const profile: unknown = JSON.parse(text);
      if (!profile || typeof profile !== 'object' || Array.isArray(profile)) throw new Error('请填写机械档案 JSON 对象。');
      setBusy(true);
      const value = await api<HardwareDetail>(`/hardware/${detail.skillName}/mechanical`, 'PUT', {
        expectedRevision: detail.revision, profile: profile as Record<string, unknown>, notes,
      } satisfies SaveHardwareMechanical);
      onSaved(value); setEditing(false); window.dispatchEvent(new Event('hardware-mechanical-saved'));
    } catch (e) { setError(e instanceof Error ? e.message : '保存失败'); }
    finally { setBusy(false); }
  };
  return <section className="sensor-section" aria-label="结构与加工资料"><h3>结构与加工资料 · 3D / 激光共用</h3>
    <p className="muted">{detail.mechanicalProfile ? '已关联本模块机械档案。' : '尚无模块机械档案。'}资料随原模块和修订保存；新设计读取最新资料，历史模型保留原版本。</p>
    <ul><li>准确型号、硬件修订、官方尺寸图或实测记录及日期。</li><li>外形长宽高、轮廓与坐标原点；安装孔的圆心坐标、孔径及固定方式。</li><li>屏幕、按钮、接口的开孔位置和尺寸；插头、线缆与元件的避让空间。</li></ul>
    <p className="muted">单位 mm，原点为板中心或外包络中心，X 为长、Y 为宽、Z 为高度。只有外形尺寸时不能保证安装孔和开孔适配。激光材料、板厚、刀缝与装配间隙在每个项目中另行确认。</p>
    {!editing ? <button onClick={start}>维护本模块机械资料</button> : <>
      <label className="field">机械档案 JSON<textarea className="structure-profile-input" aria-label="模块机械档案 JSON" value={text} onChange={e => setText(e.target.value)} maxLength={60000} disabled={busy} spellCheck={false} /></label>
      <details><summary>孔位、开口与避让填写示例（请替换为实测值）</summary><pre className="candidate-code">{`mounting.holes: [{"hole_id":"h1","center":{"x":-10,"y":5},"diameter":3,"fastener":"M3"}]
有固定孔时 mounting.strategy 用 hole_fastened。
openings: [{"kind":"rectangle","opening_id":"screen","center":{"x":0,"y":0},"size_u":20,"size_v":10,"preferred_face":"top"}]
keepouts: [{"keepout_id":"cable","center":{"x":0,"y":0,"z":10},"size":{"length_x":10,"width_y":10,"height_z":5}}]
留空数组表示尚未提供，不能据此推断实物没有孔或接口。`}</pre></details>
      <label className="field">尺寸来源、型号修订与待核实项<textarea aria-label="机械资料来源与待核实项" value={notes} onChange={e => setNotes(e.target.value)} maxLength={8000} disabled={busy} placeholder="填写官方尺寸图链接／文件名，或实测日期、型号版本及未测量项；非矩形轮廓请说明。" /></label>
      {error && <p role="alert" className="settings-error">{error}</p>}
      <button disabled={busy} onClick={() => setEditing(false)}>取消</button> <button className="primary" disabled={busy || !notes.trim()} onClick={() => void save()}>{busy ? '正在保存…' : '保存到原模块'}</button>
    </>}
  </section>;
}
