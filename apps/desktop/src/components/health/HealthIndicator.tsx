interface HealthIndicatorProps {
  status: "checking" | "ok" | "recovering" | "disconnected";
}

export function HealthIndicator({ status }: HealthIndicatorProps) {
  const isConnected = status === "ok";
  const isChecking = status === "checking";
  const isRecovering = status === "recovering";
  const serviceLabel = isChecking
    ? "本地服务连接中"
    : isConnected
      ? "本地服务正常"
      : isRecovering
        ? "本地服务正在恢复连接"
        : "本地服务未连接";
  const compactLabel = isChecking
    ? "连接中"
    : isConnected
      ? "正常"
      : isRecovering
        ? "恢复中"
        : "未连接";

  return (
    <span
      className={`health-indicator ${isConnected ? "health-connected" : isChecking ? "health-checking" : isRecovering ? "health-recovering" : "health-disconnected"}`}
      data-testid="health-indicator"
      title={serviceLabel}
      aria-label={serviceLabel}
    >
      <span className="health-dot" aria-hidden="true" />
      <span className="health-label-wide">{serviceLabel}</span>
      <span className="health-label-compact" aria-hidden="true">
        {compactLabel}
      </span>
    </span>
  );
}
