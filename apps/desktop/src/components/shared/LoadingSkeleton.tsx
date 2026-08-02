interface LoadingSkeletonProps {
  variant?: "line" | "card" | "list";
  lines?: number;
  className?: string;
}

/**
 * Generic skeleton loading placeholder.
 * Supports line, card, and list variants for different content shapes.
 */
export function LoadingSkeleton({
  variant = "line",
  lines = 3,
  className,
}: LoadingSkeletonProps) {
  if (variant === "card") {
    return (
      <div className={`skeleton-card ${className ?? ""}`} aria-hidden="true">
        <span className="skeleton-line" style={{ width: "60%" }} />
        <span className="skeleton-line" style={{ width: "90%" }} />
        <span className="skeleton-line" style={{ width: "75%" }} />
      </div>
    );
  }

  if (variant === "list") {
    return (
      <div className={`skeleton-list ${className ?? ""}`} aria-hidden="true">
        {Array.from({ length: lines }, (_, i) => (
          <span
            key={i}
            className="skeleton-line"
            style={{ width: `${85 - i * 10}%` }}
          />
        ))}
      </div>
    );
  }

  return (
    <div className={`skeleton-lines ${className ?? ""}`} aria-hidden="true">
      {Array.from({ length: lines }, (_, i) => (
        <span
          key={i}
          className="skeleton-line"
          style={{ width: `${90 - i * 12}%` }}
        />
      ))}
    </div>
  );
}
