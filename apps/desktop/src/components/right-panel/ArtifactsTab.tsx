import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArtifactKind,
  ArtifactPreviewKind,
  ArtifactStatus,
  DomainArtifactStatus,
  FloatingWindowKind,
  ProposalExportFormat,
  type ArtifactDefinition,
  type ArtifactVersion,
  type FloatingWindowSpec,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import { listArtifacts, proposalExportUrl } from "../../services/projectsApi";
import { getExpertDisplayName } from "../../utils/experts";
import { useHostAdapter } from "../../platform";
import { EmptyState } from "../shared/EmptyState";
import { ErrorRetry } from "../shared/ErrorRetry";

const STATUS_LABELS: Record<string, string> = {
  [ArtifactStatus.DRAFT]: "草稿",
  [ArtifactStatus.GENERATING]: "生成中",
  [ArtifactStatus.NEEDS_REVIEW]: "待确认",
  [ArtifactStatus.APPROVED]: "已确认",
  [ArtifactStatus.REJECTED]: "已退回",
  [ArtifactStatus.STALE]: "已过期",
  [ArtifactStatus.FAILED]: "失败",
  [ArtifactStatus.ARCHIVED]: "已归档",
  [DomainArtifactStatus.DRAFT]: "草稿",
  [DomainArtifactStatus.PENDING_CONFIRMATION]: "待确认",
  [DomainArtifactStatus.CONFIRMED]: "已确认",
  [DomainArtifactStatus.OUTDATED]: "已过期",
  [DomainArtifactStatus.ARCHIVED]: "已归档",
};

const KIND_LABELS: Record<string, string> = {
  [ArtifactKind.DOCUMENT]: "文档",
  [ArtifactKind.CODE]: "代码",
  [ArtifactKind.IMAGE]: "图片",
  [ArtifactKind.MODEL_3D]: "3D",
  [ArtifactKind.DEVICE_LOG]: "设备日志",
  [ArtifactKind.PACKAGE]: "项目包",
  [ArtifactKind.REPORT]: "报告",
};

function statusTone(status: string): "success" | "warning" | "error" | "info" {
  const normalized = status.toUpperCase();
  if (["APPROVED", "CONFIRMED"].includes(normalized)) return "success";
  if (["GENERATING", "NEEDS_REVIEW", "PENDING_CONFIRMATION"].includes(normalized)) return "warning";
  if (["FAILED", "REJECTED", "STALE", "OUTDATED", "ARCHIVED"].includes(normalized)) return "error";
  return "info";
}

interface ArtifactsTabProps {
  workspace: ProjectWorkspace | null;
  professionalMode: boolean;
  refreshRevision: number;
  onOpenFloating: (spec: FloatingWindowSpec, artifact?: ArtifactDefinition) => void;
}

type ArtifactGroupKey = "review" | "approved" | "history";

interface GroupedArtifactItem {
  artifact: ArtifactDefinition;
  versions: ArtifactVersion[];
}

interface ArtifactGroup {
  key: ArtifactGroupKey;
  label: string;
  items: GroupedArtifactItem[];
}

export function ArtifactsTab({
  workspace,
  professionalMode,
  refreshRevision,
  onOpenFloating,
}: ArtifactsTabProps) {
  const [artifacts, setArtifacts] = useState<ArtifactDefinition[]>([]);
  const [selectedVersions, setSelectedVersions] = useState<Record<string, string>>({});
  const [expertFilter, setExpertFilter] = useState<"current" | "all">("current");
  const [kindFilter, setKindFilter] = useState("all");
  const [statusFilter, setStatusFilter] = useState("all");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const previousRefreshRevision = useRef(refreshRevision);
  const projectId = workspace?.project.id ?? null;
  const projectUpdatedAt = workspace?.project.updatedAt ?? null;

  useEffect(() => {
    const selectCurrentVersion = previousRefreshRevision.current !== refreshRevision;
    previousRefreshRevision.current = refreshRevision;
    if (!projectId) {
      setArtifacts([]);
      setSelectedVersions({});
      setError(null);
      setLoading(false);
      return;
    }

    let canceled = false;
    setLoading(true);
    setError(null);
    void listArtifacts(projectId)
      .then((response) => {
        if (canceled) return;
        setArtifacts(response.artifacts);
        setSelectedVersions((current) => {
          const next: Record<string, string> = {};
          for (const artifact of response.artifacts) {
            next[artifact.id] =
              (selectCurrentVersion ? null : current[artifact.id]) ??
              artifact.currentVersionId ??
              artifact.versions[0]?.id ??
              "";
          }
          for (const group of groupArtifacts(response.artifacts)) {
            for (const item of group.items) {
              const selectionKey = groupedVersionSelectionKey(group.key, item.artifact.id);
              const currentVersionId = current[selectionKey];
              next[selectionKey] =
                (!selectCurrentVersion &&
                item.versions.some((version) => version.id === currentVersionId)
                  ? currentVersionId
                  : null) ??
                item.versions[0]?.id ??
                "";
            }
          }
          return next;
        });
      })
      .catch((err: unknown) => {
        if (!canceled) {
          setError(err instanceof Error ? err.message : "产物加载失败。");
          setArtifacts([]);
        }
      })
      .finally(() => {
        if (!canceled) setLoading(false);
      });

    return () => {
      canceled = true;
    };
  }, [projectId, projectUpdatedAt, refreshRevision]);

  const activeExpertId = workspace?.project.activeExpertId ?? null;
  const filteredArtifacts = useMemo(
    () =>
      artifacts.filter((artifact) => {
        if (
          professionalMode &&
          expertFilter === "current" &&
          activeExpertId &&
          artifact.ownerExpertId &&
          artifact.ownerExpertId !== activeExpertId
        ) {
          return false;
        }
        if (kindFilter !== "all" && artifact.kind !== kindFilter) return false;
        return true;
      }),
    [activeExpertId, artifacts, expertFilter, kindFilter, professionalMode]
  );
  const currentSolution = useMemo(
    () =>
      [...artifacts]
        .filter((artifact) => artifact.versions.some(isSolutionVersion))
        .sort((left, right) => right.updatedAt.localeCompare(left.updatedAt))[0] ?? null,
    [artifacts]
  );
  const remainingArtifacts = useMemo(
    () =>
      filteredArtifacts.filter((artifact) => artifact.id !== currentSolution?.id),
    [currentSolution?.id, filteredArtifacts]
  );
  const grouped = useMemo(
    () => groupArtifacts(remainingArtifacts, statusFilter),
    [remainingArtifacts, statusFilter]
  );
  const visibleCurrentSolution = useMemo(
    () =>
      currentSolution &&
      filteredArtifacts.some((artifact) => artifact.id === currentSolution.id) &&
      groupArtifacts([currentSolution], statusFilter).length > 0
        ? currentSolution
        : null,
    [currentSolution, filteredArtifacts, statusFilter],
  );
  const visibleArtifactCount =
    grouped.reduce((count, group) => count + group.items.length, 0) +
    (visibleCurrentSolution ? 1 : 0);

  return (
    <div className="artifacts-tab" data-testid="artifacts-tab">
      {!projectId && (
        <p className="tab-description">打开项目后显示文档、代码、图片和 3D 产物。</p>
      )}
      {projectId && loading && (
        <p className="tab-description">正在加载产物...</p>
      )}
      {projectId && (
        <div className="artifact-filters" aria-label="产物筛选">
          {professionalMode && <label>
              专家
              <select
                value={expertFilter}
                onChange={(event) => setExpertFilter(event.target.value as "current" | "all")}
              >
                <option value="current">当前专家</option>
                <option value="all">全部专家</option>
              </select>
            </label>}
          <label>
            类型
            <select value={kindFilter} onChange={(event) => setKindFilter(event.target.value)}>
              <option value="all">全部类型</option>
              {Object.entries(KIND_LABELS).map(([kind, label]) => (
                <option key={kind} value={kind}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            状态
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">全部状态</option>
              {Object.values(DomainArtifactStatus).map((status) => (
                <option key={status} value={status}>
                  {STATUS_LABELS[status] ?? status}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
      {projectId && error && (
        <ErrorRetry message={error} />
      )}
      {projectId && !loading && !error && visibleArtifactCount === 0 && (
        <EmptyState
          icon="📦"
          title="还没有产物"
          description="继续在对话中推进项目，产物会自动出现在这里。"
        />
      )}
      {projectId && !loading && !error && visibleArtifactCount > 0 && (
        <div className="artifact-groups">
          {visibleCurrentSolution && (
            <section className="artifact-current-solution" aria-label="当前推荐方案">
              <h4>当前推荐方案</h4>
              <ArtifactCard
                artifact={visibleCurrentSolution}
                selectedVersion={selectedArtifactVersion(
                  visibleCurrentSolution,
                  selectedVersions[visibleCurrentSolution.id]
                )}
                selectableVersions={visibleCurrentSolution.versions}
                professionalMode={professionalMode}
                currentRecommendation
                onSelectVersion={(versionId) =>
                  setSelectedVersions((current) => ({
                    ...current,
                    [visibleCurrentSolution.id]: versionId,
                  }))
                }
                onOpenFloating={() => {
                  const selectedVersion = selectedArtifactVersion(
                    visibleCurrentSolution,
                    selectedVersions[visibleCurrentSolution.id]
                  );
                  if (!selectedVersion) return;
                  onOpenFloating(
                    artifactToWindowSpec(visibleCurrentSolution, selectedVersion),
                    visibleCurrentSolution
                  );
                }}
              />
            </section>
          )}
          {grouped.map((group) => (
            <section key={group.key} className="artifact-group" aria-label={group.label}>
              <h4>{group.label}</h4>
              <div className="artifact-list">
                {group.items.map(({ artifact, versions }) => {
                  const selectionKey = groupedVersionSelectionKey(group.key, artifact.id);
                  const selectedVersion =
                    versions.find(
                      (version) => version.id === selectedVersions[selectionKey]
                    ) ?? versions[0] ?? null;
                  return (
                    <ArtifactCard
                      key={`${group.key}:${artifact.id}`}
                      artifact={artifact}
                      selectedVersion={selectedVersion}
                      selectableVersions={versions}
                      professionalMode={professionalMode}
                      currentRecommendation={false}
                      onSelectVersion={(versionId) =>
                        setSelectedVersions((current) => ({
                          ...current,
                          [selectionKey]: versionId,
                        }))
                      }
                      onOpenFloating={() => {
                        if (!selectedVersion) return;
                        onOpenFloating(
                          artifactToWindowSpec(artifact, selectedVersion),
                          artifact
                        );
                      }}
                    />
                  );
                })}
              </div>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}

function ArtifactCard({
  artifact,
  selectedVersion,
  selectableVersions,
  professionalMode,
  currentRecommendation,
  onSelectVersion,
  onOpenFloating,
}: {
  artifact: ArtifactDefinition;
  selectedVersion: ArtifactVersion | null;
  selectableVersions: ArtifactVersion[];
  professionalMode: boolean;
  currentRecommendation: boolean;
  onSelectVersion: (versionId: string) => void;
  onOpenFloating: () => void;
}) {
  const { capabilities, unsupportedMessage } = useHostAdapter();
  const isModelPreview = selectedVersion?.preview.kind === ArtifactPreviewKind.MODEL_3D;
  const modelPreviewBlocked = isModelPreview && !capabilities.localCadExecution;
  return (
    <div className={`artifact-card ${currentRecommendation ? "artifact-card-current" : ""}`}>
      <div className="artifact-header">
        <span className="artifact-title">{artifact.title}</span>
        <span className="artifact-version">
          {selectedVersion ? `v${selectedVersion.version}` : "无版本"}
        </span>
      </div>
      <span className="artifact-kind">{KIND_LABELS[artifact.kind] ?? artifact.kind}</span>
      <span
        className="artifact-status"
        data-status={statusTone(selectedVersion?.domainStatus ?? selectedVersion?.status ?? artifact.domainStatus ?? artifact.status)}
      >
        {selectedVersion
          ? STATUS_LABELS[selectedVersion.domainStatus ?? selectedVersion.status] ??
            selectedVersion.domainStatus ??
            selectedVersion.status
          : STATUS_LABELS[artifact.domainStatus ?? artifact.status] ??
            artifact.domainStatus ??
            artifact.status}
      </span>
      {selectedVersion?.staleReason && (
        <span className="artifact-warning">{selectedVersion.staleReason}</span>
      )}
      {professionalMode && (
        <span className="artifact-source">
          所属专家：{getExpertDisplayName(artifact.ownerExpertType)}
        </span>
      )}
      <span className="artifact-source">
        摘要：{selectedVersion?.preview.summary ?? "暂无摘要"}
      </span>
      {professionalMode && selectedVersion?.dependencies.length ? (
        <ul className="artifact-dependencies" aria-label="产物依赖">
          {selectedVersion.dependencies.map((dependency) => (
            <li key={`${dependency.kind}-${dependency.artifactId}`}>
              {dependency.label} · {STATUS_LABELS[dependency.status] ?? dependency.status}
            </li>
          ))}
        </ul>
      ) : null}
      <div className="artifact-actions">
        {professionalMode && selectableVersions.length > 1 && (
          <label className="artifact-version-select">
            版本
            <select
              value={selectedVersion?.id ?? ""}
              onChange={(event) => onSelectVersion(event.target.value)}
            >
              {selectableVersions.map((version) => (
                <option key={version.id} value={version.id}>
                  v{version.version} · {STATUS_LABELS[version.status] ?? version.status}
                </option>
              ))}
            </select>
          </label>
        )}
        <button
          className="artifact-open-btn"
          onClick={onOpenFloating}
          disabled={!selectedVersion || modelPreviewBlocked}
          title={modelPreviewBlocked ? unsupportedMessage("localCadExecution") ?? undefined : undefined}
        >
          {isModelPreview ? "打开 3D 模型" : "完整查看"}
        </button>
        {modelPreviewBlocked && (
          <span className="artifact-warning">
            {unsupportedMessage("localCadExecution")}
          </span>
        )}
        {professionalMode && selectedVersion?.sourceEntityType === "proposal" && selectedVersion.sourceEntityId && (
          <>
            <a
              className="artifact-export-link"
              href={proposalExportUrl(
                selectedVersion.projectId,
                selectedVersion.sourceEntityId,
                ProposalExportFormat.MARKDOWN
              )}
            >
              Markdown
            </a>
            <a
              className="artifact-export-link"
              href={proposalExportUrl(
                selectedVersion.projectId,
                selectedVersion.sourceEntityId,
                ProposalExportFormat.DOCX
              )}
            >
              DOCX
            </a>
          </>
        )}
      </div>
    </div>
  );
}

function selectedArtifactVersion(
  artifact: ArtifactDefinition,
  selectedVersionId?: string
): ArtifactVersion | null {
  return (
    artifact.versions.find((version) => version.id === selectedVersionId) ??
    artifact.versions.find((version) => version.id === artifact.currentVersionId) ??
    artifact.versions[0] ??
    null
  );
}

function isSolutionVersion(version: ArtifactVersion): boolean {
  return (
    version.sourceEntityType === "solution" ||
    version.mimeType === "application/vnd.zhangwen.solution+json"
  );
}

function groupArtifacts(
  artifacts: ArtifactDefinition[],
  statusFilter = "all",
): ArtifactGroup[] {
  const groups: Array<{ key: ArtifactGroupKey; label: string }> = [
    { key: "review", label: "待确认" },
    { key: "approved", label: "已确认" },
    { key: "history", label: "历史版本" },
  ];
  return groups
    .map((group) => ({
      ...group,
      items: artifacts.flatMap((artifact): GroupedArtifactItem[] => {
        const versions = artifact.versions.filter(
          (version) =>
            artifactVersionGroup(version) === group.key &&
            (statusFilter === "all" || artifactVersionDomainStatus(version) === statusFilter),
        );
        if (versions.length > 0) return [{ artifact, versions }];
        if (
          artifact.versions.length === 0 &&
          artifactStatusGroup(artifact.status, artifact.domainStatus) === group.key &&
          (statusFilter === "all" || artifactDomainStatus(artifact) === statusFilter)
        ) {
          return [{ artifact, versions: [] }];
        }
        return [];
      }),
    }))
    .filter((group) => group.items.length > 0);
}

function artifactVersionGroup(version: ArtifactVersion): ArtifactGroupKey {
  return artifactStatusGroup(version.status, version.domainStatus);
}

function artifactStatusGroup(
  status: ArtifactStatus,
  domainStatus?: DomainArtifactStatus | null,
): ArtifactGroupKey {
  if (status === ArtifactStatus.APPROVED) return "approved";
  if (
    status === ArtifactStatus.STALE ||
    status === ArtifactStatus.REJECTED ||
    status === ArtifactStatus.FAILED ||
    status === ArtifactStatus.ARCHIVED
  ) {
    return "history";
  }
  if (
    status === ArtifactStatus.DRAFT ||
    status === ArtifactStatus.GENERATING ||
    status === ArtifactStatus.NEEDS_REVIEW
  ) {
    return "review";
  }
  if (domainStatus === DomainArtifactStatus.CONFIRMED) return "approved";
  if (
    domainStatus === DomainArtifactStatus.OUTDATED ||
    domainStatus === DomainArtifactStatus.ARCHIVED
  ) {
    return "history";
  }
  return "review";
}

function artifactVersionDomainStatus(version: ArtifactVersion): string {
  return version.domainStatus ?? domainStatusForArtifactStatus(version.status);
}

function artifactDomainStatus(artifact: ArtifactDefinition): string {
  return artifact.domainStatus ?? domainStatusForArtifactStatus(artifact.status);
}

function domainStatusForArtifactStatus(status: ArtifactStatus): DomainArtifactStatus {
  if (status === ArtifactStatus.APPROVED) return DomainArtifactStatus.CONFIRMED;
  if (status === ArtifactStatus.STALE || status === ArtifactStatus.REJECTED) {
    return DomainArtifactStatus.OUTDATED;
  }
  if (status === ArtifactStatus.ARCHIVED) return DomainArtifactStatus.ARCHIVED;
  if (status === ArtifactStatus.DRAFT) return DomainArtifactStatus.DRAFT;
  return DomainArtifactStatus.PENDING_CONFIRMATION;
}

function groupedVersionSelectionKey(group: ArtifactGroupKey, artifactId: string): string {
  return `${group}:${artifactId}`;
}

function artifactToWindowSpec(
  artifact: ArtifactDefinition,
  version: ArtifactVersion
): FloatingWindowSpec {
  const codeWindow = version.preview.kind === ArtifactPreviewKind.CODE;
  const modelWindow = version.preview.kind === ArtifactPreviewKind.MODEL_3D;
  return {
    id: `window_${artifact.id}_${version.id}`,
    kind: previewToWindowKind(version.preview.kind),
    title: `${artifact.title} v${version.version}`,
    artifactId: artifact.id,
    versionId: version.id,
    singletonKey: `${artifact.id}:${version.id}`,
    initialBounds: codeWindow
      ? { x: 48, y: 60, width: 920, height: 640 }
      : modelWindow
        ? { x: 56, y: 60, width: 860, height: 640 }
        : { x: 80, y: 72, width: 640, height: 520 },
  };
}

function previewToWindowKind(kind: ArtifactPreviewKind): FloatingWindowKind {
  if (kind === ArtifactPreviewKind.CODE) return FloatingWindowKind.CODE;
  if (kind === ArtifactPreviewKind.IMAGE) return FloatingWindowKind.IMAGE;
  if (kind === ArtifactPreviewKind.MODEL_3D) return FloatingWindowKind.MODEL_3D;
  return FloatingWindowKind.DOCUMENT;
}
