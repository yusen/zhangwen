import type { ReactNode } from "react";

interface EmptyStateProps {
  icon?: string;
  title: string;
  description?: string;
  action?: ReactNode;
  className?: string;
}

/**
 * Displays an empty state with an icon, title, optional description,
 * and an optional call-to-action element.
 */
export function EmptyState({
  icon = "📋",
  title,
  description,
  action,
  className,
}: EmptyStateProps) {
  return (
    <div className={`empty-state ${className ?? ""}`} role="status">
      <span className="empty-state-icon" aria-hidden="true">
        {icon}
      </span>
      <strong className="empty-state-title">{title}</strong>
      {description && (
        <p className="empty-state-description">{description}</p>
      )}
      {action && <div className="empty-state-action">{action}</div>}
    </div>
  );
}
