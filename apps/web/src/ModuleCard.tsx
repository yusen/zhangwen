import { useState } from 'react';
import { ArrowDownToLine, ArrowUpFromLine, BookOpen, Check, CircuitBoard, Cog, Monitor, X, MoreVertical } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/mu';
import { moduleBrand, moduleDirection, moduleType } from './hardwareLibrary';

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
  const [expanded, setExpanded] = useState(false);
  const direction = moduleDirection(item);
  const DirectionIcon = direction === 'input' ? ArrowDownToLine : ArrowUpFromLine;
  const content = <><ModuleVisual item={item} /><strong className="module-name">{item.displayName}</strong>
    <span className="module-brand">{moduleBrand(item)}{item.catalog?.programmingSupport === 'reference' && <small className="module-reference-status"> · 编程待联调</small>}</span>
    <span className={`module-direction ${direction}`}><DirectionIcon size={13} aria-hidden="true" />{direction === 'input' ? '输入' : '输出'} · {moduleType(item)}</span></>;
  if (!onToggle) {
    const shortName = item.displayName.replace(/^(?:DFRobot\s+)?(?:[A-Z]{2,}\d{3,}\s*)?(?:Gravity\s*)?/i, '').trim() || item.displayName;
    return <article className="hardware-card module-card selected module-row">
      <button className="module-open" aria-label={`资料：${item.displayName}`} title={item.displayName} onClick={onDetail}><ModuleVisual item={item} /><strong className="module-name">{shortName}</strong></button>
      <button className="module-options-toggle" aria-label={`模块选项：${item.displayName}`} aria-expanded={expanded} disabled={disabled} onClick={() => setExpanded(value => !value)}><MoreVertical size={16} /></button>
      {outside && <small className="module-warning">资料需核对</small>}
      {expanded && <div className="module-actions" role="group" aria-label={`${item.displayName}的操作`}>
        <button onClick={onDetail}>查看资料</button>
        {onLoad && <button disabled={disabled} aria-label={`载入模块：${item.displayName}`} onClick={onLoad}>载入示例</button>}
        <button disabled={disabled} aria-label={`移除${item.displayName}`} onClick={onRemove}><X size={14} />移除模块</button>
      </div>}
    </article>;
  }
  return <article className={`hardware-card module-card sensor-picker-row ${checked ? 'is-selected' : ''}`}>
    <label className="module-select">
      <input type="checkbox" aria-label={`选择${item.displayName}`} checked={checked} disabled={disabled} onChange={event => onToggle(event.target.checked)} />
      {content}
    </label>
    {outside && <small className="module-warning">资料需核对</small>}
    <div className="module-actions">
      <span>{added ? <><Check size={13} />已加入</> : checked ? '已选择' : '点击选择'}</span><button aria-label={`资料：${item.displayName}`} onClick={onDetail}><BookOpen size={16} />资料</button>
    </div>
  </article>;
}
