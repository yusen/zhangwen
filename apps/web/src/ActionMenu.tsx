import { useEffect, useId, useLayoutEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { ChevronDown, type LucideIcon } from 'lucide-react';

export interface MenuAction {
  label: string;
  icon?: LucideIcon;
  onSelect: () => void;
  disabled?: boolean;
  group?: string;
  shortcut?: string;
}

// A portal keeps menus outside the scrolling toolbars and CodeMirror layers.
export function ActionMenu({ label, children, items, disabled, className = '', align = 'left' }: {
  label: string; children?: ReactNode; items: MenuAction[]; disabled?: boolean;
  className?: string; align?: 'left' | 'right';
}) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState({ top: 0, left: 0 });
  const trigger = useRef<HTMLButtonElement>(null);
  const menu = useRef<HTMLDivElement>(null);
  const id = useId();
  const close = (restore = false) => { setOpen(false); if (restore) trigger.current?.focus(); };
  useLayoutEffect(() => {
    if (!open) return;
    const place = () => {
      const anchor = trigger.current?.getBoundingClientRect(), panel = menu.current;
      if (!anchor || !panel) return;
      const left = align === 'right' ? anchor.right - panel.offsetWidth : anchor.left;
      setPosition({ left: Math.max(8, Math.min(left, innerWidth - panel.offsetWidth - 8)),
        top: Math.max(8, Math.min(anchor.bottom + 6, innerHeight - panel.offsetHeight - 8)) });
    };
    place();
    menu.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus();
    window.addEventListener('resize', place);
    window.addEventListener('scroll', place, true);
    return () => { window.removeEventListener('resize', place); window.removeEventListener('scroll', place, true); };
  }, [open, align]);
  useEffect(() => {
    if (!open) return;
    const outside = (event: PointerEvent) => {
      if (!menu.current?.contains(event.target as Node) && !trigger.current?.contains(event.target as Node)) close();
    };
    document.addEventListener('pointerdown', outside);
    return () => document.removeEventListener('pointerdown', outside);
  }, [open]);
  useEffect(() => { if (disabled) setOpen(false); }, [disabled]);
  return <>
    <button ref={trigger} className={`action-menu-trigger ${className}`} aria-label={label} aria-haspopup="menu" aria-expanded={open} aria-controls={open ? id : undefined} disabled={disabled}
      onClick={() => setOpen(value => !value)} onKeyDown={event => { if (event.key === 'ArrowDown' || event.key === 'ArrowUp') { event.preventDefault(); setOpen(true); } }}>
      {children ?? <>{label}<ChevronDown size={13} aria-hidden="true" /></>}
    </button>
    {open && createPortal(<div ref={menu} id={id} role="menu" aria-label={label} className="workbench-action-menu" style={position}
      onBlur={event => { if (!event.currentTarget.contains(event.relatedTarget as Node)) close(); }}
      onKeyDown={event => {
        const buttons = Array.from(menu.current?.querySelectorAll<HTMLButtonElement>('button:not(:disabled)') ?? []);
        const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
        if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); close(true); }
        else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
          event.preventDefault();
          const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
          buttons[next]?.focus();
        } else if (event.key === 'Tab') close(true);
      }}>
      {items.map(({ label: text, icon: Icon, disabled: locked, onSelect, group, shortcut }, index) => <div key={`${text}-${index}`}>
        {group && <div className="action-menu-group">{group}</div>}
        <button role="menuitem" aria-label={text} disabled={locked} onClick={() => { close(true); onSelect(); }}>
          {Icon && <Icon size={16} aria-hidden="true" />}<span>{text}</span>{shortcut && <small>{shortcut}</small>}
        </button>
      </div>)}
    </div>, document.body)}
  </>;
}
