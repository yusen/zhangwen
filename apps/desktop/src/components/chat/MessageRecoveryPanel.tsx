import { memo } from "react";
import { LLMErrorCode, type LLMError } from "@zhangwen/contracts";
import { isInterruptedGeneration } from "../../hooks/useAutomaticRecovery";

interface MessageRecoveryPanelProps {
  error: LLMError;
  disabled: boolean;
  canRecover: boolean;
  onAction: (actionId: string) => void;
}

/**
 * Displays structured failure recovery options for a failed assistant message.
 * Shows error message, guidance copy, and actionable recovery buttons.
 * Extracted from CenterChat for isolated rendering and testability.
 */
export const MessageRecoveryPanel = memo(function MessageRecoveryPanel({
  error,
  disabled,
  canRecover,
  onAction,
}: MessageRecoveryPanelProps) {
  const copy = recoveryCopy(error);
  const actions = recoveryActions(error);
  return (
    <section className="message-recovery-panel" aria-label="生成失败恢复方案">
      <p className="message-error" role="alert">{error.message}</p>
      <div className="message-recovery-guidance">
        <strong>{copy.title}</strong>
        <span>{copy.guidance}</span>
      </div>
      {actions.length > 0 && (
        <div className="message-recovery-actions">
          {actions.map((action) => (
            <button
              key={action.id}
              type="button"
              className={
                action.id === "retry"
                  ? "message-recovery-primary"
                  : "message-recovery-secondary"
              }
              disabled={
                disabled
                || (action.id !== "open_settings" && !canRecover)
              }
              onClick={() => onAction(action.id)}
            >
              {action.label}
            </button>
          ))}
        </div>
      )}
    </section>
  );
});

function recoveryCopy(error: LLMError): { title: string; guidance: string } {
  if (error.code === LLMErrorCode.LOCAL_OUTPUT_REJECTED) {
    return {
      title: "生成结果未通过本地校验",
      guidance: "本次生成没有遵循当前工程上下文，或触碰了代码、凭据、主机文件访问或设备安全边界，因此没有写入工程产物。原需求本身不需要修改，可以按原需求重新生成。",
    };
  }
  if (error.code === LLMErrorCode.LLM_OUTPUT_INVALID) {
    return {
      title: "云端结构化输出不完整",
      guidance: "这通常不是需求内容错误。建议先重新生成；若连续出现，可检查模型、思考模式和超时时间设置。",
    };
  }
  if (isInterruptedGeneration(error)) {
    return {
      title: "生成过程已中断",
      guidance: "应用关闭、Sidecar 重启或连接断开都可能造成中断。原需求已经保留，可以直接继续生成，或先修改原需求。",
    };
  }
  if (error.code === LLMErrorCode.CANCELED) {
    return {
      title: "生成已停止",
      guidance: "原需求仍保留在对话中，需要时可以重新生成。",
    };
  }
  return {
    title: "本次生成没有完成",
    guidance: "原需求不会丢失。请按下方操作继续；若问题反复出现，可先检查本地服务和模型设置。",
  };
}

function recoveryActions(error: LLMError): { id: string; label: string }[] {
  if (error.code === LLMErrorCode.LOCAL_OUTPUT_REJECTED) {
    return [
      { id: "retry", label: "按原需求重试" },
    ];
  }
  if (error.code === LLMErrorCode.LLM_OUTPUT_INVALID) {
    return [
      { id: "retry", label: "重新生成" },
      { id: "open_settings", label: "检查模型设置" },
    ];
  }
  if (isInterruptedGeneration(error)) {
    return [
      { id: "retry", label: "继续生成" },
      { id: "revise_request", label: "修改原需求" },
    ];
  }
  const actions = error.userActions.map((action) => (
    action.id === "retry" ? { ...action, label: "重新生成" } : action
  ));
  return actions.length > 0
    ? actions
    : error.retryable
      ? [{ id: "retry", label: "重新生成" }]
      : [];
}
