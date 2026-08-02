import { useCallback, useEffect, useState } from "react";
import type { AgentPackageDetail, ExpertType } from "@zhangwen/contracts";
import { ApiError } from "../../services/api";
import {
  getAgentPackage,
  resetAgentPackageFile,
  updateAgentPackageFile,
} from "../../services/projectsApi";
import { SkillProjectWorkspace } from "./SkillProjectWorkspace";

interface AgentPackageEditorProps {
  expertType: ExpertType;
  onDirtyChange?: (dirty: boolean) => void;
}

export function AgentPackageEditor({
  expertType,
  onDirtyChange,
}: AgentPackageEditorProps) {
  const [detail, setDetail] = useState<AgentPackageDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const response = await getAgentPackage(expertType);
      setDetail(response.package);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "无法读取工程师行为项目。");
    } finally {
      setLoading(false);
    }
  }, [expertType]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !detail) {
    return <p className="floating-placeholder" role="status">正在读取工程师行为项目...</p>;
  }
  if (!detail) {
    return (
      <div className="floating-placeholder">
        <p role="alert">{loadError ?? "工程师行为项目不可用。"}</p>
        <button type="button" onClick={() => void load()}>重试</button>
      </div>
    );
  }

  return (
    <SkillProjectWorkspace
      ariaLabel={`${detail.displayName}行为项目编辑器`}
      projectKey={`agent-package-${detail.expertType}`}
      revision={detail.revision}
      files={detail.files}
      diagnostics={detail.validationIssues}
      manifestItems={[
        { label: "工程师", value: detail.displayName },
        { label: "行为包", value: detail.skillName },
        { label: "受控能力", value: `${detail.skillIds.length} 项` },
      ]}
      onDirtyChange={onDirtyChange}
      onSave={async (updates) => {
        let current = detail;
        try {
          for (const update of updates) {
            const response = await updateAgentPackageFile(current.expertType, {
              ...update,
              expectedRevision: current.revision,
            });
            current = response.package;
            setDetail(current);
          }
          return `已保存 ${updates.length} 个文件。下一次${current.displayName}回复开始生效。`;
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) {
            const latest = await getAgentPackage(detail.expertType);
            setDetail(latest.package);
            throw new Error("服务端版本已更新，当前草稿仍保留，请检查后再次保存。");
          }
          throw error;
        }
      }}
      onReset={async (path) => {
        try {
          const response = await resetAgentPackageFile(detail.expertType, {
            path,
            expectedRevision: detail.revision,
          });
          setDetail(response.package);
          return `已把 ${path} 恢复为内置默认内容。下一次${response.package.displayName}回复开始生效。`;
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) {
            const latest = await getAgentPackage(detail.expertType);
            setDetail(latest.package);
            throw new Error("服务端版本已更新，请确认最新内容后再恢复默认。");
          }
          throw error;
        }
      }}
    />
  );
}
