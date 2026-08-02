import { useCallback, useMemo, useRef, useState } from "react";
import type { ExpertType } from "@zhangwen/contracts";

export interface ChatExpertOption {
  id: string;
  type: ExpertType;
  name: string;
  icon: string;
}

interface ChatInputProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (text: string) => void;
  onStop?: () => void;
  disabledReason?: string | null;
  streaming?: boolean;
  inputRef?: React.RefObject<HTMLTextAreaElement>;
  experts?: ChatExpertOption[];
  availableExperts?: ChatExpertOption[];
  selectedExpertId?: string | null;
  onSelectExpert?: (projectExpertId: string) => void;
  onAddExpert?: (expertType: ExpertType) => Promise<unknown>;
  activeQuestion?: string | null;
  onUseRecommendation?: () => void;
}

export function ChatInput({
  value,
  onChange,
  onSend,
  onStop,
  disabledReason,
  streaming = false,
  inputRef,
  experts = [],
  availableExperts = [],
  selectedExpertId,
  onSelectExpert,
  onAddExpert,
  activeQuestion = null,
  onUseRecommendation,
}: ChatInputProps) {
  const [mentionOpen, setMentionOpen] = useState(false);
  const [mentionIndex, setMentionIndex] = useState(0);
  const [addExpertOpen, setAddExpertOpen] = useState(false);
  const [addingExpertType, setAddingExpertType] = useState<ExpertType | null>(null);
  const [addExpertError, setAddExpertError] = useState<string | null>(null);
  const pillStripRef = useRef<HTMLDivElement>(null);
  const mentionQuery = useMemo(() => {
    const match = value.match(/(?:^|\s)@([^\s@]*)$/);
    return match?.[1] ?? null;
  }, [value]);
  const matchingExperts = mentionQuery === null
    ? []
    : experts.filter((expert) => expert.name.includes(mentionQuery));
  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionOpen && matchingExperts.length > 0) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setMentionIndex((i) => (i + 1) % matchingExperts.length);
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setMentionIndex((i) => (i - 1 + matchingExperts.length) % matchingExperts.length);
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const target = matchingExperts[mentionIndex];
        if (target) selectMention(target);
        return;
      }
      if (e.key === "Escape") {
        e.preventDefault();
        setMentionOpen(false);
        return;
      }
    }
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      onSend(value);
    }
  };

  const selectMention = useCallback((expert: ChatExpertOption) => {
    const prefix = value.replace(/(?:^|\s)@[^\s@]*$/, (match) =>
      match.startsWith(" ") ? ` @${expert.name} ` : `@${expert.name} `
    );
    onChange(prefix);
    onSelectExpert?.(expert.id);
    setMentionOpen(false);
    setMentionIndex(0);
    inputRef?.current?.focus();
  }, [value, onChange, onSelectExpert, inputRef]);

  const handlePillStripKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    const buttons = Array.from(
      pillStripRef.current?.querySelectorAll<HTMLButtonElement>("button:not(:disabled)") ?? []
    );
    const currentIndex = buttons.indexOf(document.activeElement as HTMLButtonElement);
    if (currentIndex === -1) return;
    e.preventDefault();
    const next = e.key === "ArrowRight"
      ? (currentIndex + 1) % buttons.length
      : (currentIndex - 1 + buttons.length) % buttons.length;
    buttons[next]?.focus();
  };

  const addExpert = async (expert: ChatExpertOption) => {
    if (!onAddExpert || addingExpertType || streaming) return;
    setAddingExpertType(expert.type);
    setAddExpertError(null);
    try {
      await onAddExpert(expert.type);
      setAddExpertOpen(false);
    } catch (error) {
      setAddExpertError(
        error instanceof Error ? error.message : "添加工程师失败，请稍后重试。",
      );
    } finally {
      setAddingExpertType(null);
    }
  };

  return (
    <div className="chat-input-area" data-testid="chat-input">
      {activeQuestion && (
        <div className="chat-clarification-shortcuts" role="group" aria-label="回答掌问">
          <button
            type="button"
            className="conversation-action"
            disabled={streaming || !onUseRecommendation}
            onClick={onUseRecommendation}
          >
            按掌问建议继续
          </button>
          <button
            type="button"
            className="secondary-btn"
            disabled={streaming}
            onClick={() => inputRef?.current?.focus()}
          >
            我自己说
          </button>
        </div>
      )}
      {experts.length > 0 && (
        <div className="project-expert-strip" role="group" aria-label="项目智能体" ref={pillStripRef} onKeyDown={handlePillStripKeyDown}>
          {experts.map((expert) => (
            <button
              key={expert.id}
              type="button"
              className={expert.id === selectedExpertId ? "expert-pill expert-pill-active" : "expert-pill"}
              aria-pressed={expert.id === selectedExpertId}
              onClick={() => onSelectExpert?.(expert.id)}
            >
              <span>{expertIcon(expert.icon)}</span>
              {expert.name}
            </button>
          ))}
          {availableExperts.length > 0 && (
            <button
              type="button"
              className="expert-pill expert-pill-add"
              aria-expanded={addExpertOpen}
              aria-controls="project-add-expert-panel"
              disabled={streaming || addingExpertType !== null}
              onClick={() => {
                setAddExpertOpen((open) => !open);
                setAddExpertError(null);
              }}
            >
              ＋ 添加工程师
            </button>
          )}
        </div>
      )}
      {addExpertOpen && availableExperts.length > 0 && (
        <section
          id="project-add-expert-panel"
          className="project-add-expert-panel"
          aria-label="添加项目工程师"
        >
          <div>
            <strong>加入当前项目</strong>
            <span>新增工程师拥有独立对话，只共享项目事实、产物和公共知识。</span>
          </div>
          <div className="project-add-expert-options">
            {availableExperts.map((expert) => (
              <button
                key={expert.type}
                type="button"
                aria-label={`添加${expert.name}`}
                disabled={addingExpertType !== null || streaming}
                onClick={() => void addExpert(expert)}
              >
                <span>{expertIcon(expert.icon)}</span>
                {addingExpertType === expert.type
                  ? `正在添加${expert.name}...`
                  : `添加${expert.name}`}
              </button>
            ))}
          </div>
          {addExpertError && (
            <p className="project-add-expert-error" role="alert">
              {addExpertError}
            </p>
          )}
        </section>
      )}
      {mentionOpen && matchingExperts.length > 0 && (
        <div className="mention-menu" role="listbox" aria-label="选择回复智能体" aria-activedescendant={`mention-opt-${mentionIndex}`}>
          {matchingExperts.map((expert, idx) => (
            <button
              key={expert.id}
              id={`mention-opt-${idx}`}
              type="button"
              role="option"
              aria-selected={idx === mentionIndex}
              data-highlighted={idx === mentionIndex || undefined}
              onClick={() => selectMention(expert)}
            >
              <span>{expertIcon(expert.icon)}</span>
              <strong>{expert.name}</strong>
            </button>
          ))}
        </div>
      )}
      <div className="chat-composer-row">
        <textarea
          ref={inputRef}
          className="chat-textarea"
          placeholder={
            activeQuestion
              ? "直接回答掌问，或继续描述你的想法…"
              : "描述你想做的作品…"
          }
          value={value}
          onChange={(e) => {
            onChange(e.target.value);
            setMentionOpen(/(?:^|\s)@[^\s@]*$/.test(e.target.value));
          }}
          onKeyDown={handleKeyDown}
          rows={3}
        />
        <button
          className="chat-send-btn"
          onClick={() => (streaming ? onStop?.() : onSend(value))}
          disabled={!streaming && (!value.trim() || Boolean(disabledReason))}
        >
          {streaming ? "停止" : "发送"}
        </button>
        {disabledReason && !streaming && (
          <span className="chat-disabled-reason" role="status">
            {disabledReason}
          </span>
        )}
      </div>
    </div>
  );
}

function expertIcon(icon: string): string {
  if (icon === "cpu") return "⚙";
  if (icon === "box") return "◇";
  return "✦";
}
