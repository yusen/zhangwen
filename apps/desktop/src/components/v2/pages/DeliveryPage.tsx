import type {
  ArtifactDefinition,
  ProjectRelease,
  ProjectState,
  ProjectVersion,
} from "@zhangwen/contracts";
import { ArtifactWorkspace } from "./common";

export function DeliveryPage({
  versions,
  releases,
  state,
  artifacts,
  artifactsLoading,
  artifactsError,
  professionalMode,
}: {
  versions: ProjectVersion[];
  releases: ProjectRelease[];
  state: ProjectState | null;
  artifacts: ArtifactDefinition[];
  artifactsLoading: boolean;
  artifactsError: string | null;
  professionalMode: boolean;
}) {
  return (
    <div className="v2-delivery-page">
      <div className={`v2-page-grid v2-delivery-grid ${professionalMode ? "is-professional" : "is-simple"}`}>
        <section className="v2-hero-card">
          <span className="v2-card-label">{professionalMode ? "当前交付基线" : "当前成果"}</span>
          <h2>{versions[0]
            ? professionalMode ? `项目版本 V${versions[0].version}` : "已保存项目进度"
            : professionalMode ? "尚未创建 Project Version" : "成果正在准备中"}</h2>
          <p>{professionalMode
            ? versions[0]?.changeSetId
              ? "该版本由已确认 Change Set 生成。"
              : "该版本由现有 V1 项目事实建立兼容基线。"
            : "方案、代码、3D 模型和验证结果会集中保存在下方。"}</p>
          {professionalMode && <div className="v2-delivery-hash">{state?.projectionHash ?? "等待首次投影"}</div>}
        </section>
        <section className="v2-list-card">
          <div className="v2-section-heading"><span>{professionalMode ? "版本历史" : "保存记录"}</span><b>{versions.length}</b></div>
          <ul>{versions.map((item, index) => (
            <li key={item.id}>
              <span>{professionalMode
                ? `V${item.version}${item.changeSetId ? "" : " · V1 导入基线"}`
                : `第 ${versions.length - index} 次保存`}</span>
              <strong>{new Date(item.createdAt).toLocaleString()}</strong>
            </li>
          ))}</ul>
        </section>
        {professionalMode && <section className="v2-list-card">
          <div className="v2-section-heading"><span>Release</span><b>{releases.length}</b></div>
          <ul>{releases.map((item) => <li key={item.id}><span>{item.name}</span><strong>{item.unverifiedItems.length ? `${item.unverifiedItems.length} 项未验证` : "清单完整"}</strong></li>)}{!releases.length && <li className="v2-muted">确认后续 Change Set，即可在兼容基线上继续创建 Release。</li>}</ul>
        </section>}
      </div>
      <ArtifactWorkspace
        title="全部成果"
        lead={professionalMode
          ? "已有文档、代码、3D、日志和项目包继续使用同一份版本数据。"
          : "选择一项即可查看方案、代码、3D 模型或验证结果。"}
        artifacts={artifacts}
        loading={artifactsLoading}
        error={artifactsError}
        empty="当前项目尚无可查看成果。"
        professionalMode={professionalMode}
      />
    </div>
  );
}
