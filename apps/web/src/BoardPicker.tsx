import { useState } from 'react';
import { Check, Search } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/mu';
import { Dialog } from './Dialog';
import { BoardArtwork } from './BoardArtwork';
import { boardImages } from './boardImages';

function BoardCard({ item, selected, onSelect }: { item: HardwareSummary; selected: boolean; onSelect: () => void }) {
  const code = item.displayName.match(/\b(?:K\d+|ESP32[\w-]*|RP\d+|DFR\d+)\b/i)?.[0];
  return <button className={`board-choice board-product-card ${selected ? 'is-active' : ''}`} aria-label={item.displayName} aria-pressed={selected} onClick={onSelect}>
    <div className="board-product-image"><BoardArtwork board={item} />
      {code && <span className="board-product-code">{code}</span>}
      {boardImages[item.componentId]?.caption && <small className="board-product-caption">{boardImages[item.componentId]?.caption}</small>}
    </div>
    <div className="board-product-body"><strong>{item.displayName}</strong><p>{item.description}</p></div>
    <div className="board-product-state">{selected ? <><Check size={15} />当前选择</> : '点击选择'}</div>
  </button>;
}

export function BoardPicker({ boards, selected, onSelect, onClose, onHelp }: {
  boards: HardwareSummary[]; selected: string; onSelect: (item: HardwareSummary) => void; onClose: () => void; onHelp: () => void;
}) {
  const [query, setQuery] = useState('');
  const available = boards.filter(item => item.category === 'MCU' && item.status === 'ACTIVE');
  const filtered = available.filter(item => `${item.displayName} ${item.description} ${item.skillName}`.toLowerCase().includes(query.trim().toLowerCase()));
  return <Dialog className="board-picker-dialog" title="选择主控板" onClose={onClose}>
    <div className="board-picker-intro"><p>找不到想要的主控？<button onClick={onHelp}>查看帮助</button></p><span>硬件库 · {available.length} 款</span></div>
    <div className="catalog-search board-picker-search"><Search size={17} /><input autoFocus aria-label="搜索主控板" value={query} onChange={event => setQuery(event.target.value)} placeholder="搜索主控名称…" /></div>
    <p className="muted board-picker-note">选择与实际设备一致的主控，上传前核对型号与固件。</p>
    <div className="board-choice-grid">{filtered.map(item => <BoardCard key={item.componentId} item={item} selected={selected === item.componentId} onSelect={() => onSelect(item)} />)}{!filtered.length && <p className="muted">没有匹配的主控板，试试其他关键词。</p>}</div>
  </Dialog>;
}
