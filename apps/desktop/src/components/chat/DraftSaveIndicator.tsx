interface DraftSaveIndicatorProps {
  draftSaveError: string | null;
  draftSaving: boolean;
  isDirty: boolean;
  hasSavedDraft: boolean;
  onRetry: () => void;
}

/**
 * Displays the four-state draft persistence indicator:
 * unsaved / saving / saved / save-failed.
 * Extracted from CenterChat to isolate draft status rendering.
 */
export function DraftSaveIndicator({
  draftSaveError,
  draftSaving,
  isDirty,
  hasSavedDraft,
  onRetry,
}: DraftSaveIndicatorProps) {
  return (
    <div className="draft-save-indicator" role="status" aria-live="polite">
      {draftSaveError ? (
        <span className="draft-save-failed">
          保存失败
          <button
            type="button"
            className="link-button"
            onClick={onRetry}
          >
            重试
          </button>
        </span>
      ) : draftSaving ? (
        <span className="draft-saving">保存中...</span>
      ) : isDirty ? (
        <span className="draft-unsaved">未保存</span>
      ) : hasSavedDraft ? (
        <span className="draft-saved">已保存</span>
      ) : null}
    </div>
  );
}
