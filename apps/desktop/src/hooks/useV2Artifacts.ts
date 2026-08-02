import { useCallback, useEffect, useState } from "react";
import type { ArtifactDefinition } from "@zhangwen/contracts";
import { listArtifacts } from "../services/projectsApi";

interface V2ArtifactState {
  artifacts: ArtifactDefinition[];
  loading: boolean;
  error: string | null;
}

export function useV2Artifacts(
  projectId: string | null,
  projectUpdatedAt?: string | null,
) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState<V2ArtifactState>({
    artifacts: [],
    loading: false,
    error: null,
  });

  const refresh = useCallback(() => setRevision((value) => value + 1), []);

  useEffect(() => {
    let active = true;
    if (!projectId) {
      setState({ artifacts: [], loading: false, error: null });
      return () => {
        active = false;
      };
    }
    setState((current) => ({ ...current, loading: true, error: null }));
    void listArtifacts(projectId)
      .then(({ artifacts }) => {
        if (active) setState({ artifacts, loading: false, error: null });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setState((current) => ({
          ...current,
          loading: false,
          error: error instanceof Error ? error.message : "项目产物加载失败。",
        }));
      });
    return () => {
      active = false;
    };
  }, [projectId, projectUpdatedAt, revision]);

  return { ...state, refresh };
}
