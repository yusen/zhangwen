import type { LucideIcon } from 'lucide-react';

export function MuTool({ icon: Icon, artwork, label, hint, active = false, emphasis = false, variant = 'software', ...props }: {
  artwork?: React.ReactNode;
  icon: LucideIcon; label: string; hint?: string; active?: boolean; emphasis?: boolean; variant?: 'software' | 'hardware' | 'muted' | 'brand';
} & React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} aria-label={props['aria-label'] ?? label} className={`mu-tool tool-${variant} ${active ? 'is-active' : ''} ${emphasis ? 'run-tool' : ''}`} title={props.title ?? label}>
    <span className="tool-icon">{artwork ?? <Icon size={22} strokeWidth={2.6} aria-hidden="true" />}</span>
    <span className="tool-label">{label}</span>{hint && <small>{hint}</small>}
  </button>;
}
