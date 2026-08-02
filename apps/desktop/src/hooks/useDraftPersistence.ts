import { useCallback, useEffect, useRef, useState } from "react";

interface UseDraftPersistenceOptions {
  projectId: string | null;
  workspaceDraftContent: string;
  workspaceDraftUpdatedAt?: string | null;
  onSaveDraft: (projectId: string, content: string, projectExpertId?: string | null) => Promise<unknown>;
  debounceMs?: number;
}

export interface DraftPersistenceState {
  draft: string;
  updateDraft: (value: string) => void;
  flushDraft: () => Promise<void>;
  isDirty: boolean;
  lastSavedContent: string;
}

/**
 * Manages per-project draft persistence with debounced auto-save.
 * Extracted from CenterChat to isolate draft state and reduce re-renders.
 */
export function useDraftPersistence({
  projectId,
  workspaceDraftContent,
  workspaceDraftUpdatedAt: _workspaceDraftUpdatedAt,
  onSaveDraft,
  debounceMs = 400,
}: UseDraftPersistenceOptions): DraftPersistenceState {
  const [draft, setDraft] = useState("");
  const lastSavedDraftRef = useRef("");
  const draftRef = useRef("");
  const draftSaveTimerRef = useRef<number | null>(null);
  const draftSavePromiseRef = useRef<Promise<unknown> | null>(null);
  const draftByProjectRef = useRef<Record<string, string>>({});
  const activeProjectIdRef = useRef<string | null>(null);

  const persistDraft = useCallback(
    async (savingProjectId: string, savingDraft: string) => {
      const pending = onSaveDraft(savingProjectId, savingDraft, null);
      draftSavePromiseRef.current = pending;
      try {
        await pending;
        if (activeProjectIdRef.current === savingProjectId) {
          lastSavedDraftRef.current = savingDraft;
        }
      } finally {
        if (draftSavePromiseRef.current === pending) {
          draftSavePromiseRef.current = null;
        }
      }
    },
    [onSaveDraft],
  );

  // Restore draft on project switch
  useEffect(() => {
    activeProjectIdRef.current = projectId;
    const workspaceDraft = workspaceDraftContent;
    const cachedDraft = projectId ? draftByProjectRef.current[projectId] : undefined;
    const nextDraft = cachedDraft ?? workspaceDraft;
    draftRef.current = nextDraft;
    setDraft(nextDraft);
    lastSavedDraftRef.current = workspaceDraft;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // Debounced auto-save
  useEffect(() => {
    if (!projectId) return;
    draftByProjectRef.current[projectId] = draft;
    if (draft === lastSavedDraftRef.current) return;

    const savingProjectId = projectId;
    const savingDraft = draft;
    const handle = window.setTimeout(() => {
      draftSaveTimerRef.current = null;
      void persistDraft(savingProjectId, savingDraft).catch(() => {
        // useProjects owns the visible error state; keep this draft dirty for retry.
      });
    }, debounceMs);
    draftSaveTimerRef.current = handle;
    return () => {
      window.clearTimeout(handle);
      if (draftSaveTimerRef.current === handle) draftSaveTimerRef.current = null;
    };
  }, [draft, debounceMs, persistDraft, projectId]);

  const flushDraft = useCallback(async () => {
    if (draftSaveTimerRef.current !== null) {
      window.clearTimeout(draftSaveTimerRef.current);
      draftSaveTimerRef.current = null;
    }
    try {
      await draftSavePromiseRef.current;
    } catch {
      // Retry the current dirty value below.
    }
    const savingProjectId = activeProjectIdRef.current;
    if (!savingProjectId) return;
    const savingDraft = draftRef.current;
    if (savingDraft === lastSavedDraftRef.current) return;
    await persistDraft(savingProjectId, savingDraft);
  }, [persistDraft]);

  const updateDraft = useCallback(
    (value: string) => {
      if (projectId) {
        draftByProjectRef.current[projectId] = value;
      }
      draftRef.current = value;
      setDraft(value);
    },
    [projectId],
  );

  const isDirty = draft !== lastSavedDraftRef.current;

  return {
    draft,
    updateDraft,
    flushDraft,
    isDirty,
    lastSavedContent: lastSavedDraftRef.current,
  };
}
