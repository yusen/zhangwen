import { memo } from "react";
import { ChatProgressStatus, type ChatProgress } from "@zhangwen/contracts";

interface MessageActionProgressProps {
  expertName: string;
  progress: ChatProgress[];
  professionalMode: boolean;
}

/**
 * Displays real-time action progress within an expert reply bubble.
 * Shows completed steps and the current running/waiting action.
 * Extracted from CenterChat for isolated rendering and memoization.
 */
export const MessageActionProgress = memo(function MessageActionProgress({
  expertName,
  progress,
  professionalMode,
}: MessageActionProgressProps) {
  const ordered = [...progress].sort((left, right) => left.sequence - right.sequence);
  const current =
    [...ordered]
      .reverse()
      .find(
        (item) =>
          item.status === ChatProgressStatus.RUNNING ||
          item.status === ChatProgressStatus.WAITING,
      ) ??
    ordered[ordered.length - 1];
  if (!current) return null;

  const completed = ordered.filter(
    (item) => item.status === ChatProgressStatus.COMPLETED && item.id !== current.id
  );
  const isRunning = current.status === ChatProgressStatus.RUNNING;

  return (
    <div
      className="message-action-progress"
      role="status"
      aria-live="polite"
      aria-label={`${expertName}执行进度`}
      data-status={current.status.toLowerCase()}
    >
      {professionalMode && completed.length > 0 && (
        <ol className="message-action-progress-list" aria-label="已完成动作">
          {completed.map((item) => (
            <li className="message-action-progress-item" key={item.id}>
              {item.label}
            </li>
          ))}
        </ol>
      )}
      <div className="message-action-progress-current">
        <span className="message-action-progress-label">{current.label}</span>
        {isRunning && (
          <span className="message-generation-dots" aria-hidden="true">
            <i />
            <i />
            <i />
          </span>
        )}
      </div>
    </div>
  );
});
