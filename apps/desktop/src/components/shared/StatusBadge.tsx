interface StatusBadgeProps {
  status: "success" | "warning" | "error" | "info" | "neutral";
  label: string;
  icon?: string;
  className?: string;
}

const STATUS_ICONS: Record<StatusBadgeProps["status"], string> = {
  success: "✓",
  warning: "!",
  error: "✕",
  info: "i",
  neutral: "–",
};

/**
 * Unified status badge with icon + text (not color-only).
 * Ensures accessibility by pairing color with icon and label.
 */
export function StatusBadge({
  status,
  label,
  icon,
  className,
}: StatusBadgeProps) {
  return (
    <span
      className={`status-badge status-badge-${status} ${className ?? ""}`}
      role="status"
    >
      <i aria-hidden="true">{icon ?? STATUS_ICONS[status]}</i>
      {label}
    </span>
  );
}
