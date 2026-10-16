import type { LucideIcon } from 'lucide-react';

export function MuTool({ icon: Icon, artwork, label, hint, planned = false, active = false, emphasis = false, variant = 'software', ...props }: {
  artwork?: React.ReactNode;
  icon: LucideIcon; label: string; hint?: string; planned?: boolean; active?: boolean; emphasis?: boolean; variant?: 'software' | 'hardware' | 'muted' | 'brand';
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} aria-label={props['aria-label'] ?? (planned ? `${label}（待开发）` : label)} className={`mu-tool tool-${variant} ${active ? 'is-active' : ''} ${emphasis ? 'run-tool' : ''} ${planned ? 'tool-planned' : ''}`} title={props.title ?? (planned ? `${label} · 待开发` : label)}>
    <span className="tool-icon">{artwork ?? <Icon size={22} strokeWidth={2.6} aria-hidden="true" />}{planned && <small className="tool-planned-badge" aria-hidden="true">待开发</small>}</span>
    <span className="tool-label">{label}</span>{hint && <small>{hint}</small>}
  </button>;
}
