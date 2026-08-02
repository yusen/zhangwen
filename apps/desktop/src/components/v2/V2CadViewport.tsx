import { useEffect, useState } from "react";
import type {
  ArtifactVersion,
  CadIntentRevision,
  CadRun,
} from "@zhangwen/contracts";
import { getArtifact } from "../../services/projectsApi";
import { Model3dArtifactViewer } from "../floating/Model3dArtifactViewer";

export function V2CadViewport({
  revision,
  cadRun,
  refreshKey = "",
  professionalMode = false,
  decorativePlaceholder = true,
}: {
  revision: CadIntentRevision | null;
  cadRun: CadRun | null;
  refreshKey?: string;
  professionalMode?: boolean;
  decorativePlaceholder?: boolean;
}) {
  const [version, setVersion] = useState<ArtifactVersion | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [waitingForBuild, setWaitingForBuild] = useState(false);
  const projectId = revision?.projectId ?? cadRun?.projectId ?? null;
  const artifactId = revision?.artifactId ?? cadRun?.artifactId ?? null;
  const artifactVersionId = revision?.artifactVersionId ?? cadRun?.artifactVersionId ?? null;

  useEffect(() => {
    setVersion(null);
    setError(null);
    setWaitingForBuild(false);
    if (!projectId || !artifactId || !artifactVersionId) return;
    let active = true;
    void getArtifact(projectId, artifactId)
      .then(({ artifact }) => {
        if (!active) return;
        const match = artifact.versions.find(
          (item) => item.id === artifactVersionId,
        );
        if (!match) throw new Error(professionalMode
          ? "当前 CAD 产物版本不存在。请重新构建模型。"
          : "当前 3D 模型无法读取，请重新生成。");
        if (!match.preview.modelFileId) {
          setWaitingForBuild(true);
          return;
        }
        setVersion(match);
      })
      .catch((reason: unknown) => {
        if (!active) return;
        setError(reason instanceof Error ? reason.message : "3D 预览加载失败。");
      });
    return () => {
      active = false;
    };
  }, [artifactId, artifactVersionId, professionalMode, projectId, refreshKey]);

  if (version) return <Model3dArtifactViewer version={version} />;
  return (
    <div className="v2-cad-placeholder">
      {decorativePlaceholder ? <div className="v2-cad-cube" aria-hidden="true"><i /><i /><i /></div> : null}
      <strong>{error
        ? "预览暂不可用"
        : waitingForBuild
          ? professionalMode ? "源码已确认，等待 3D 构建" : "方案已确认，等待生成 3D"
          : professionalMode ? "CAD Intent 工作区" : "从一句描述开始设计"}</strong>
      <p>{error ?? (waitingForBuild
        ? professionalMode
          ? "点击“生成并验证 3D”，本地 Worker 会生成并校验 GLB、STEP 和 STL。"
          : "点击“生成 3D 模型”继续。"
        : professionalMode
          ? "描述结构目标，系统先生成可检查的源码修订；确认后再进入构建和版本链。"
          : "说明产品外形、尺寸、孔位或安装方式，系统会先给出一份可确认的 3D 方案。")}</p>
    </div>
  );
}
