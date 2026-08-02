import { useCallback, useEffect, useState } from "react";
import type { V2ProjectData } from "../services/v2Api";
import { getV2ProjectData } from "../services/v2Api";

interface V2ProjectDataState {
  data: V2ProjectData | null;
  loading: boolean;
  error: string | null;
}

export function useV2ProjectData(projectId: string | null) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<V2ProjectDataState>({
    data: null,
    loading: false,
    error: null,
  });

  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    if (!projectId) {
      setState({ data: null, loading: false, error: null });
      return;
    }
    const controller = new AbortController();
    setState((current) => ({ ...current, loading: true, error: null }));
    void getV2ProjectData(projectId, controller.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "V2 项目状态加载失败。",
        }));
      });
    return () => controller.abort();
  }, [projectId, revision]);

  return { ...state, refresh };
}
