import { useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

export function Dialog({ title, onClose, children, className }: { title: string; onClose: () => void; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => {
    const node = ref.current;
    const prior = document.activeElement as HTMLElement | null;
    node?.showModal();
    (node?.querySelector<HTMLElement>('[data-dialog-autofocus]') ?? node?.querySelector<HTMLElement>('.dialog-body input, .dialog-body textarea, .dialog-body select'))?.focus();
    return () => { node?.close(); prior?.focus(); };
  }, []);
  return <dialog className={className} ref={ref} onCancel={event => { event.preventDefault(); onClose(); }} aria-labelledby="dialog-title">
    <header className="dialog-head"><h2 id="dialog-title">{title}</h2><button className="icon-button" aria-label="关闭" onClick={onClose}><X size={20} /></button></header>
    <div className="dialog-body">{children}</div>
  </dialog>;
}
