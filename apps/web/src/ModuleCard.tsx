import { useId, useRef, useState } from 'react';
import { ArrowDownToLine, ArrowUpFromLine, BookOpen, Check, CircuitBoard, Cog, Monitor, X, MoreVertical, FileCode2 } from 'lucide-react';
import type { HardwareSummary } from '../../../packages/contracts/src/platform';
import { moduleBrand, moduleDirection, moduleType } from './hardwareLibrary';
import { FloatingMenu } from './FloatingMenu';
import { verificationSummary } from './hardwareVerificationState';

function ModuleVisual({ item }: { item: HardwareSummary }) {
  const [failed, setFailed] = useState(false);
  const media = item.media.find(image => /cover|product/i.test(image.path)) ?? item.media[0];
  const Icon = item.category === 'DISPLAY' ? Monitor : item.category === 'ACTUATOR' ? Cog : CircuitBoard;
  return <span className="module-visual">{media && !failed
    ? <img loading="lazy" src={media.url} alt={media.alt} onError={() => setFailed(true)} />
    : <Icon size={48} strokeWidth={1.5} aria-hidden="true" />}</span>;
}

export function ModuleCard({ item, boardId, checked, added, disabled, outside, onToggle, onDetail, onEditExample, onRemove, onLoad }: {
  item: HardwareSummary; boardId?: string; checked?: boolean; added?: boolean; disabled?: boolean; outside?: boolean;
  boards: HardwareSummary[];
  onToggle?: (checked: boolean) => void; onDetail: () => void; onRemove?: () => void; onLoad?: () => void;
  onEditExample?: () => void;
}) {
  const [expanded, setExpanded] = useState(false);
  const options = useRef<HTMLButtonElement>(null);
  const menuId = useId();
  const direction = moduleDirection(item);
  const verification = verificationSummary(item, boardId);
  const verificationText = verification.text;
  const DirectionIcon = direction === 'input' ? ArrowDownToLine : ArrowUpFromLine;
  const content = <><ModuleVisual item={item} /><strong className="module-name" title={item.displayName}>{item.displayName}</strong>
    <span className="module-brand">{item.personal ? '我的模块' : moduleBrand(item)}{item.catalog?.programmingSupport === 'reference' && <small className="module-reference-status" title="编程参考资料，还需要用实物测试"> · 待实测</small>}</span>
    <span className={`module-direction ${direction}`}><DirectionIcon size={13} aria-hidden="true" />{direction === 'input' ? '输入' : direction === 'output' ? '输出' : '配套'} · {moduleType(item)}</span></>;
  if (!onToggle) {
    const shortName = item.displayName.replace(/^(?:DFRobot\s+)?(?:[A-Z]{2,}\d{3,}\s*)?(?:Gravity\s*)?/i, '').trim() || item.displayName;
    return <article className="hardware-card module-card selected module-row" onContextMenu={event => { event.preventDefault(); if (!disabled) setExpanded(true); }}>
      <button className="module-open" aria-label={`资料：${item.displayName}`} title={item.displayName} onClick={onDetail}><ModuleVisual item={item} /><strong className="module-name">{shortName}</strong></button>
      <button ref={options} className="module-options-toggle" aria-label={`模块选项：${item.displayName}`} aria-expanded={expanded} aria-haspopup="menu" aria-controls={expanded ? menuId : undefined} disabled={disabled} onClick={() => setExpanded(value => !value)} onKeyDown={event => { if (event.key === 'ArrowDown') { event.preventDefault(); setExpanded(true); } }}><MoreVertical size={16} /></button>
      <button className={`module-verification-status verification-badge ${verification.tone}`} type="button" disabled={disabled} aria-label={`核实状态：${item.displayName}`} title={`${verificationText}；点击修改`} onClick={onDetail}>{verificationText}</button>
      {outside && <small className="module-warning">资料需核对</small>}
      {expanded && options.current && <FloatingMenu id={menuId} label={`${item.displayName}的操作`} anchor={options.current} onClose={restore => { setExpanded(false); if (restore) options.current?.focus({ preventScroll: true }); }} items={[
        { label: '查看资料', icon: BookOpen, action: onDetail },
        ...(onEditExample ? [{ label: '编辑案例', icon: FileCode2, disabled, action: onEditExample }] : []),
        ...(onLoad ? [{ label: '载入示例', ariaLabel: `载入模块：${item.displayName}`, icon: FileCode2, disabled, action: onLoad }] : []),
        ...(onRemove ? [{ label: '移除模块', ariaLabel: `移除${item.displayName}`, icon: X, disabled, danger: true, action: onRemove }] : []),
      ]} />}
    </article>;
  }
  return <article className={`hardware-card module-card sensor-picker-row ${checked ? 'is-selected' : ''}`}>
    <label className="module-select">
      <input type="checkbox" aria-label={`选择${item.displayName}`} checked={checked} disabled={disabled} onChange={event => onToggle(event.target.checked)} />
      {content}
      <span className={`module-verification-status verification-badge ${verification.tone}`} title={verificationText}>{verificationText}</span>
    </label>
    {outside && <small className="module-warning">资料需核对</small>}
    <div className="module-actions">
      <span>{added ? <><Check size={13} />已加入</> : checked ? '已选择' : '点击选择'}</span><button aria-label={`资料：${item.displayName}`} onClick={onDetail}><BookOpen size={16} />资料</button>
    </div>
  </article>;
}
