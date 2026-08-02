import { useCallback, useEffect, useState } from "react";
import type { ProjectProgressSnapshot } from "@zhangwen/contracts";
import { getProjectProgress } from "../services/projectsApi";


export function useProjectProgress(
  projectId: string | null,
  refreshRevision: number,
  projectUpdatedAt?: string | null,
) {
  const [progress, setProgress] = useState<ProjectProgressSnapshot | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!projectId) {
      setProgress(null);
      setError(null);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const response = await getProjectProgress(projectId);
      setProgress(response.progress);
    } catch (reason) {
      setProgress(null);
      setError(reason instanceof Error ? reason.message : "项目进度加载失败。" );
    } finally {
      setLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    void refresh();
  }, [refresh, refreshRevision, projectUpdatedAt]);

  return { progress, loading, error, refresh };
}
