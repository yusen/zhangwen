import { useState } from 'react';
import { ArrowDownToLine, ArrowUpFromLine, BookOpen, Check, CircuitBoard, Cog, Monitor, X } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/mu';
import { moduleDirection } from './hardwareLibrary';

function ModuleVisual({ item }: { item: HardwareSummary }) {
  const [failed, setFailed] = useState(false);
  const media = item.media.find(image => /cover|product/i.test(image.path)) ?? item.media[0];
  const Icon = item.category === 'DISPLAY' ? Monitor : item.category === 'ACTUATOR' ? Cog : CircuitBoard;
  return <span className="module-visual">{media && !failed
    ? <img loading="lazy" src={media.url} alt={media.alt} onError={() => setFailed(true)} />
    : <Icon size={48} strokeWidth={1.5} aria-hidden="true" />}</span>;
}

export function ModuleCard({ item, checked, added, disabled, outside, onToggle, onDetail, onRemove, onLoad }: {
  item: HardwareSummary; checked?: boolean; added?: boolean; disabled?: boolean; outside?: boolean;
  onToggle?: (checked: boolean) => void; onDetail: () => void; onRemove?: () => void; onLoad?: () => void;
}) {
  const direction = moduleDirection(item);
  const DirectionIcon = direction === 'input' ? ArrowDownToLine : ArrowUpFromLine;
  const content = <><ModuleVisual item={item} /><strong className="module-name">{item.displayName}</strong>
    <span className={`module-direction ${direction}`}><DirectionIcon size={13} aria-hidden="true" />{direction === 'input' ? '输入模块' : '输出模块'}</span></>;
  return <article className={`hardware-card module-card ${onToggle ? 'sensor-picker-row' : 'selected'} ${checked ? 'is-selected' : ''}`}>
    {onToggle ? <label className="module-select">
      <input type="checkbox" aria-label={`选择${item.displayName}`} checked={checked} disabled={disabled} onChange={event => onToggle(event.target.checked)} />
      {content}
    </label> : <button className="module-open" aria-label={`资料：${item.displayName}`} onClick={onDetail}>{content}</button>}
    {outside && <small className="module-warning">当前板型需核对</small>}
    <div className="module-actions">
      {onToggle ? <><span>{added ? <><Check size={13} />已加入</> : checked ? '已选择' : '点击选择'}</span><button aria-label={`资料：${item.displayName}`} onClick={onDetail}><BookOpen size={16} />资料</button></>
        : <>{onLoad && <button disabled={disabled} aria-label={`载入模块：${item.displayName}`} onClick={onLoad}>载入模块</button>}<button disabled={disabled} aria-label={`移除${item.displayName}`} onClick={onRemove} title="从项目移除"><X size={16} />移除</button></>}
    </div>
  </article>;
}
