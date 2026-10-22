import { useState } from 'react';
import { Box, Check, Search } from 'lucide-react';
import type { BuiltinTemplate } from '../../../packages/contracts/src/structure';
import { Dialog } from './Dialog';

export function CaseTemplatePicker({ templates, currentId, canAdd, onAdd, onClose }: {
  templates: BuiltinTemplate[]; currentId?: string; canAdd: boolean;
  onAdd: (template: BuiltinTemplate) => void; onClose: () => void;
}) {
  const [selectedId, setSelectedId] = useState(currentId);
  const [search, setSearch] = useState('');
  const selected = templates.find(item => item.id === selectedId);
  const query = search.trim().toLocaleLowerCase();
  const visible = templates.filter(item => `${item.title} ${item.description} ${item.notes.join(' ')}`.toLocaleLowerCase().includes(query));
  return <Dialog title="添加案例模板" className="sensor-picker-dialog case-template-picker" onClose={onClose} headerActions={
    <div className="catalog-search picker-search"><Search size={17} aria-hidden="true" /><input data-dialog-autofocus aria-label="搜索案例模板" placeholder="搜索作品、型号或用途…" value={search} onChange={event => setSearch(event.target.value)} /></div>
  }>
    <p className="catalog-result-count">作品与固定座 · {visible.length} 个案例 · 加入后显示3D预览，可继续对话改造。</p>
    <div className="sensor-picker-list module-grid" role="radiogroup" aria-label="案例模板">
      {visible.map(item => <article key={item.id} className={`hardware-card module-card sensor-picker-row ${selectedId === item.id ? 'is-selected' : ''}`}>
        <label className="module-select">
          <input type="radio" name="case-template" aria-label={`选择${item.title}`} checked={selectedId === item.id} onChange={() => setSelectedId(item.id)} />
          <span className="module-visual">{item.image ? <img src={item.image} alt="" loading="lazy" /> : <Box size={48} aria-hidden="true" />}</span>
          <strong className="module-name">{item.title}</strong>
          <span className="case-template-size">初始尺寸 · {item.size.join(' × ')} mm</span>
          <span className="case-template-description">{item.description}</span>
          <span className="case-template-notes">{item.notes.join(' ')}</span>
        </label>
        <div className="module-actions"><span>{currentId === item.id ? <><Check size={13} />当前案例</> : selectedId === item.id ? '已选择' : '点击选择'}</span></div>
      </article>)}
      {!visible.length && <p className="catalog-empty" role="status">没有匹配的案例模板，请换个关键词。</p>}
    </div>
    <div className="sensor-picker-actions"><span>{!canAdd ? '保存项目后可加入案例模板' : selected ? `已选择：${selected.title}` : '选择项目需要的案例模板'}</span><button onClick={onClose}>取消</button><button className="primary" disabled={!selected || !canAdd} onClick={() => { if (selected && canAdd) onAdd(selected); }}>加入案例模板</button></div>
  </Dialog>;
}
