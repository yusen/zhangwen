import { forwardRef, useId } from 'react';
import type { LucideIcon } from 'lucide-react';

export const ToolbarButton = forwardRef<HTMLButtonElement, {
  artwork?: React.ReactNode;
  disabledReason?: string;
  icon: LucideIcon; label: string; hint?: string; planned?: boolean; active?: boolean; emphasis?: boolean; variant?: 'software' | 'hardware' | 'muted' | 'brand';
} & React.ButtonHTMLAttributes<HTMLButtonElement>>(function ToolbarButton({ icon: Icon, artwork, label, hint, disabledReason, planned = false, active = false, emphasis = false, variant = 'software', className = '', ...props }, ref) {
  const reasonId = useId();
  const reason = props.disabled ? disabledReason : undefined;
  const button = <button {...props} ref={ref} aria-describedby={reason ? [props['aria-describedby'], reasonId].filter(Boolean).join(' ') : props['aria-describedby']} aria-label={props['aria-label'] ?? (planned ? `${label}（待开发）` : label)} className={`zhangwen-tool tool-${variant} ${active ? 'is-active' : ''} ${emphasis ? 'run-tool' : ''} ${planned ? 'tool-planned' : ''} ${className}`} title={reason ?? props.title ?? (planned ? `${label} · 待开发` : label)}>
    <span className="tool-icon">{artwork ?? <Icon size={22} strokeWidth={2.6} aria-hidden="true" />}{planned && <small className="tool-planned-badge" aria-hidden="true">待开发</small>}</span>
    <span className="tool-label">{label}</span>{hint && <small>{hint}</small>}
  </button>;
  return reason ? <span className="tool-disabled-explanation" tabIndex={0} role="group" aria-label={label} aria-describedby={reasonId}>
    {button}<span className="tool-disabled-reason" id={reasonId} role="tooltip">{reason}</span>
  </span> : button;
});
