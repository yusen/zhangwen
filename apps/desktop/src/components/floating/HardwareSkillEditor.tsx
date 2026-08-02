import { useCallback, useEffect, useState } from "react";
import type { HardwareSkillDetail } from "@zhangwen/contracts";
import { ApiError } from "../../services/api";
import {
  getHardwareSkill,
  updateHardwareSkillFiles,
} from "../../services/hardwareApi";
import { publishHardwareSkillUpdated } from "../../utils/hardwareSkillEvents";
import { SkillProjectWorkspace } from "./SkillProjectWorkspace";

interface HardwareSkillEditorProps {
  skillName: string;
  onDirtyChange?: (dirty: boolean) => void;
}

export function HardwareSkillEditor({
  skillName,
  onDirtyChange,
}: HardwareSkillEditorProps) {
  const [detail, setDetail] = useState<HardwareSkillDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const response = await getHardwareSkill(skillName);
      setDetail(response.skill);
    } catch (error) {
      setLoadError(error instanceof Error ? error.message : "无法读取 Hardware Skill 项目。");
    } finally {
      setLoading(false);
    }
  }, [skillName]);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !detail) {
    return <p className="floating-placeholder" role="status">正在读取 Hardware Skill 项目...</p>;
  }
  if (!detail) {
    return (
      <div className="floating-placeholder">
        <p role="alert">{loadError ?? "Hardware Skill 项目不可用。"}</p>
        <button type="button" onClick={() => void load()}>重试</button>
      </div>
    );
  }

  return (
    <SkillProjectWorkspace
      ariaLabel={`${detail.displayName} Hardware Skill 项目编辑器`}
      projectKey={`hardware-skill-${detail.skillName}`}
      revision={detail.revision}
      files={detail.files}
      diagnostics={detail.diagnostics}
      manifestItems={[
        { label: "Skill", value: detail.skillName },
        { label: "状态", value: hardwareSkillStatus(detail.status) },
        { label: "验证", value: detail.verificationStatus },
      ]}
      onDirtyChange={onDirtyChange}
      onSave={async (updates) => {
        try {
          const response = await updateHardwareSkillFiles(detail.skillName, {
            updates,
            expectedRevision: detail.revision,
          });
          setDetail(response.skill);
          publishHardwareSkillUpdated(response.skill);
          return `已保存 ${updates.length} 个文件。下一次工程师回复将读取新版本。`;
        } catch (error) {
          if (error instanceof ApiError && error.status === 409) {
            const latest = await getHardwareSkill(detail.skillName);
            setDetail(latest.skill);
            throw new Error("服务端版本已更新，当前草稿仍保留，请检查后再次保存。");
          }
          throw error;
        }
      }}
    />
  );
}

function hardwareSkillStatus(status: HardwareSkillDetail["status"]): string {
  return {
    ACTIVE: "已启用",
    DRAFT: "草稿",
    ARCHIVED: "已归档",
    INVALID: "校验失败",
  }[status] ?? status;
}
