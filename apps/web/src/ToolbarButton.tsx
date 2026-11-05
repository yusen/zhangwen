import { forwardRef } from 'react';
import type { LucideIcon } from 'lucide-react';

export const ToolbarButton = forwardRef<HTMLButtonElement, {
  artwork?: React.ReactNode;
  icon: LucideIcon; label: string; hint?: string; planned?: boolean; active?: boolean; emphasis?: boolean; variant?: 'software' | 'hardware' | 'muted' | 'brand';
} & React.ButtonHTMLAttributes<HTMLButtonElement>>(function ToolbarButton({ icon: Icon, artwork, label, hint, planned = false, active = false, emphasis = false, variant = 'software', className = '', ...props }, ref) {
  return <button {...props} ref={ref} aria-label={props['aria-label'] ?? (planned ? `${label}（待开发）` : label)} className={`zhangwen-tool tool-${variant} ${active ? 'is-active' : ''} ${emphasis ? 'run-tool' : ''} ${planned ? 'tool-planned' : ''} ${className}`} title={props.title ?? (planned ? `${label} · 待开发` : label)}>
    <span className="tool-icon">{artwork ?? <Icon size={22} strokeWidth={2.6} aria-hidden="true" />}{planned && <small className="tool-planned-badge" aria-hidden="true">待开发</small>}</span>
    <span className="tool-label">{label}</span>{hint && <small>{hint}</small>}
  </button>;
});
