import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import type { LucideIcon } from 'lucide-react';

export function FloatingMenu({ id, label, anchor, items, onClose }: {
  id: string; label: string; anchor: HTMLElement;
  items: { label: string; ariaLabel?: string; icon: LucideIcon; disabled?: boolean; danger?: boolean; action: () => void }[];
  onClose: (restoreFocus: boolean) => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const close = useRef(onClose); close.current = onClose;
  const [position, setPosition] = useState({ left: 0, top: 0 });
  useLayoutEffect(() => {
    const bounds = anchor.getBoundingClientRect(), menu = ref.current!.getBoundingClientRect();
    const left = bounds.right + 6 + menu.width <= innerWidth - 8 ? bounds.right + 6 : bounds.left - menu.width - 6;
    setPosition({ left: Math.max(8, Math.min(left, innerWidth - menu.width - 8)), top: Math.max(8, Math.min(bounds.top, innerHeight - menu.height - 8)) });
    ref.current?.querySelector<HTMLButtonElement>('button:not(:disabled)')?.focus({ preventScroll: true });
  }, [anchor]);
  useEffect(() => {
    const outside = (event: PointerEvent | FocusEvent) => { if (!ref.current?.contains(event.target as Node) && !anchor.contains(event.target as Node)) close.current(false); };
    const scroll = (event: Event) => { if (!ref.current?.contains(event.target as Node)) close.current(false); };
    const resize = () => close.current(false);
    document.addEventListener('pointerdown', outside);
    document.addEventListener('focusin', outside);
    window.addEventListener('scroll', scroll, true);
    window.addEventListener('resize', resize);
    return () => { document.removeEventListener('pointerdown', outside); document.removeEventListener('focusin', outside); window.removeEventListener('scroll', scroll, true); window.removeEventListener('resize', resize); };
  }, [anchor]);
  return createPortal(<div id={id} ref={ref} className="module-context-menu" role="menu" aria-label={label} style={position} onKeyDown={event => {
    const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>('button:not(:disabled)')];
    const index = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); onClose(true); }
    else if (event.key === 'Tab') onClose(true);
    else if (['ArrowDown', 'ArrowUp', 'Home', 'End'].includes(event.key)) {
      event.preventDefault();
      const next = event.key === 'Home' ? 0 : event.key === 'End' ? buttons.length - 1 : (index + (event.key === 'ArrowDown' ? 1 : -1) + buttons.length) % buttons.length;
      buttons[next]?.focus();
    }
  }}>{items.map(({ icon: Icon, ...item }) => <button key={item.label} role="menuitem" aria-label={item.ariaLabel ?? item.label} disabled={item.disabled} className={item.danger ? 'danger' : ''} onClick={() => { onClose(true); item.action(); }}><Icon size={16} aria-hidden="true" />{item.label}</button>)}</div>, document.body);
}
