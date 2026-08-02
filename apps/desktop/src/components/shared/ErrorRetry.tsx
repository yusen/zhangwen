interface ErrorRetryProps {
  message: string;
  onRetry?: () => void;
  retryLabel?: string;
  className?: string;
}

/**
 * Unified error display with optional retry button.
 * Replaces scattered inline error patterns across panels.
 */
export function ErrorRetry({
  message,
  onRetry,
  retryLabel = "重试",
  className,
}: ErrorRetryProps) {
  return (
    <div className={`error-retry ${className ?? ""}`} role="alert">
      <span className="error-retry-icon" aria-hidden="true">
        ⚠
      </span>
      <p className="error-retry-message">{message}</p>
      {onRetry && (
        <button type="button" className="secondary-btn" onClick={onRetry}>
          {retryLabel}
        </button>
      )}
    </div>
  );
}
