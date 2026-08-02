import { lazy, Suspense, useCallback, useEffect, useRef } from "react";
import {
  ArtifactPreviewKind,
  ArtifactStatus,
  FloatingWindowKind,
  type ArtifactDefinition,
  type ArtifactVersion,
  type CodeRun,
  type ExpertType,
  type FloatingWindowSpec,
  type MechanicalProfileSummary,
} from "@zhangwen/contracts";
import { Model3dArtifactViewer } from "./Model3dArtifactViewer";
import { HardwareComponentEditor } from "./HardwareComponentEditor";

const CodeArtifactEditor = lazy(async () => {
  const module = await import("./CodeArtifactEditor");
  return { default: module.CodeArtifactEditor };
});

const HardwareSkillEditor = lazy(async () => {
  const module = await import("./HardwareSkillEditor");
  return { default: module.HardwareSkillEditor };
});

const AgentPackageEditor = lazy(async () => {
  const module = await import("./AgentPackageEditor");
  return { default: module.AgentPackageEditor };
});

const MechanicalProfilePreview = lazy(async () => {
  const module = await import("./MechanicalProfilePreview");
  return { default: module.MechanicalProfilePreview };
});

interface FloatingWindowProps {
  spec: FloatingWindowSpec;
  artifact?: ArtifactDefinition | null;
  hardwareComponentId?: string;
  hardwareSkillName?: string;
  agentExpertType?: ExpertType;
  mechanicalProfile?: MechanicalProfileSummary;
  active: boolean;
  onFocus: (id: string) => void;
  onClose: (id: string) => void;
  onMinimize: (id: string) => void;
  onToggleMaximize: (id: string) => void;
  onDirtyChange?: (id: string, dirty: boolean) => void;
  onCodeRunChanged?: (artifactId: string, codeRun: CodeRun) => void | Promise<void>;
}

/**
 * 产物浮窗 — 打开/关闭不影响中央主对话和输入草稿。
 * 浮窗以 fixed overlay item 渲染，不改变 AppShell 的布局结构。
 */
export function FloatingWindow({
  spec,
  artifact,
  hardwareComponentId,
  hardwareSkillName,
  agentExpertType,
  mechanicalProfile,
  active,
  onFocus,
  onClose,
  onMinimize,
  onToggleMaximize,
  onDirtyChange,
  onCodeRunChanged,
}: FloatingWindowProps) {
  const windowRef = useRef<HTMLDivElement>(null);
  const version = selectVersion(artifact, spec.versionId);
  const bounds = spec.initialBounds ?? { x: 80, y: 72, width: 640, height: 520 };
  const editableCode = isEditableCodeVersion(version);
  const model3d = version?.preview.kind === ArtifactPreviewKind.MODEL_3D;
  const hardwareComponent =
    spec.kind === FloatingWindowKind.HARDWARE_COMPONENT && hardwareComponentId;
  const hardwareSkill =
    spec.kind === FloatingWindowKind.HARDWARE_SKILL && hardwareSkillName;
  const agentPackage =
    spec.kind === FloatingWindowKind.AGENT_PACKAGE && agentExpertType;
  const mechanicalProfilePreview =
    spec.kind === FloatingWindowKind.MECHANICAL_PROFILE && mechanicalProfile;
  const skillProject = Boolean(hardwareSkill || agentPackage);
  const editableProject = Boolean(hardwareComponent || skillProject);
  const handleProjectDirtyChange = useCallback(
    (dirty: boolean) => onDirtyChange?.(spec.id, dirty),
    [onDirtyChange, spec.id],
  );

  useEffect(() => {
    if (editableProject) windowRef.current?.focus();
  }, [editableProject]);

  return (
    <div
      ref={windowRef}
      className={`floating-window ${editableCode ? "floating-window-code" : ""} ${model3d ? "floating-window-model3d" : ""} ${mechanicalProfilePreview ? "floating-window-mechanical-profile" : ""} ${hardwareComponent ? "floating-window-hardware" : ""} ${skillProject ? "floating-window-skill-project" : ""} ${active ? "floating-window-active" : ""} ${
        spec.minimized ? "floating-window-minimized" : ""
      } ${spec.maximized ? "floating-window-maximized" : ""}`}
      data-testid="floating-window"
      style={
        spec.maximized
          ? { zIndex: spec.zIndex }
          : {
              left: bounds.x,
              top: bounds.y,
              width: bounds.width,
              height: bounds.height,
              zIndex: spec.zIndex,
            }
      }
      onMouseDown={() => onFocus(spec.id)}
      role="dialog"
      aria-label={spec.title}
      tabIndex={-1}
    >
      <div className="floating-header">
        <span className="floating-title">{spec.title}</span>
        <div className="floating-controls">
          <button
            className="floating-control"
            onClick={() => onMinimize(spec.id)}
            aria-label="最小化浮窗"
          >
            _
          </button>
          <button
            className="floating-control"
            onClick={() => onToggleMaximize(spec.id)}
            aria-label={spec.maximized ? "还原浮窗" : "最大化浮窗"}
          >
            {spec.maximized ? "▣" : "□"}
          </button>
          <button
            className="floating-close"
            onClick={() => onClose(spec.id)}
            aria-label="关闭浮窗"
          >
            x
          </button>
        </div>
      </div>
      {(!spec.minimized || editableProject) && (
        <div
          className={`floating-body ${editableCode ? "floating-body-code" : ""} ${model3d ? "floating-body-model3d" : ""} ${mechanicalProfilePreview ? "floating-body-mechanical-profile" : ""} ${hardwareComponent ? "floating-body-hardware" : ""} ${skillProject ? "floating-body-skill-project" : ""}`}
          hidden={spec.minimized}
        >
          {hardwareComponent ? (
            <HardwareComponentEditor
              componentId={hardwareComponentId}
              onDirtyChange={handleProjectDirtyChange}
            />
          ) : hardwareSkill ? (
            <Suspense fallback={<p className="floating-placeholder" role="status">正在打开 Hardware Skill 项目...</p>}>
              <HardwareSkillEditor
                skillName={hardwareSkillName}
                onDirtyChange={handleProjectDirtyChange}
              />
            </Suspense>
          ) : agentPackage ? (
            <Suspense fallback={<p className="floating-placeholder" role="status">正在打开工程师行为项目...</p>}>
              <AgentPackageEditor
                expertType={agentExpertType}
                onDirtyChange={handleProjectDirtyChange}
              />
            </Suspense>
          ) : mechanicalProfilePreview ? (
            <Suspense fallback={<p className="floating-placeholder" role="status">正在生成机械档案预览...</p>}>
              <MechanicalProfilePreview profile={mechanicalProfile} />
            </Suspense>
          ) : version ? (
            <ArtifactPreview
              artifact={artifact}
              version={version}
              onCodeRunChanged={onCodeRunChanged}
            />
          ) : (
            <>
              <p className="floating-placeholder">暂无可预览的产物内容。</p>
              <p>产物标题：{spec.title}</p>
              <p className="floating-note">
                关闭此浮窗不会改变中央主对话的内容和滚动位置。
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}

function ArtifactPreview({
  artifact,
  version,
  onCodeRunChanged,
}: {
  artifact?: ArtifactDefinition | null;
  version: ArtifactVersion;
  onCodeRunChanged?: FloatingWindowProps["onCodeRunChanged"];
}) {
  const editableCode = isEditableCodeVersion(version);
  const model3d = version.preview.kind === ArtifactPreviewKind.MODEL_3D;
  return (
    <article className={`floating-document ${editableCode ? "floating-document-code" : ""} ${model3d ? "floating-document-model3d" : ""}`}>
      <dl className={`floating-metadata ${editableCode ? "floating-metadata-code" : ""} ${model3d ? "floating-metadata-model3d" : ""}`}>
        <div>
          <dt>产物</dt>
          <dd>{artifact?.title ?? version.artifactId}</dd>
        </div>
        <div>
          <dt>版本</dt>
          <dd>v{version.version}</dd>
        </div>
        <div>
          <dt>状态</dt>
          <dd>{artifactStatusLabel(version.status)}</dd>
        </div>
        <div>
          <dt>校验</dt>
          <dd>{version.checksum.slice(0, 12)}</dd>
        </div>
      </dl>
      {version.preview.kind === ArtifactPreviewKind.DOCUMENT &&
        (isProposalDocument(version) ? (
          <div className="proposal-table-wrap">
            <table className="proposal-table" aria-label="项目立项表">
              <thead>
                <tr>
                  <th scope="col">立项项</th>
                  <th scope="col">执行内容</th>
                </tr>
              </thead>
              <tbody>
                {version.preview.sections?.map((section) => (
                  <tr key={section.id}>
                    <th scope="row">{section.title}</th>
                    <td>{section.content}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          version.preview.sections?.map((section) => (
            <section key={section.id} className="floating-section">
              <h3>{section.title}</h3>
              <p>{section.content}</p>
            </section>
          ))
        ))}
      {version.preview.kind === ArtifactPreviewKind.CODE &&
      version.sourceEntityType === "code" &&
      version.sourceEntityId ? (
        <Suspense fallback={<div className="floating-loading" role="status">正在加载代码编辑器…</div>}>
          <CodeArtifactEditor
            key={version.sourceEntityId}
            projectId={version.projectId}
            codeRunId={version.sourceEntityId}
            onCodeRunChanged={(codeRun) =>
              onCodeRunChanged?.(version.artifactId, codeRun)
            }
          />
        </Suspense>
      ) : version.preview.kind === ArtifactPreviewKind.CODE ? (
        <pre className="floating-code">
          <code>{version.preview.code ?? version.preview.summary}</code>
        </pre>
      ) : null}
      {version.preview.kind === ArtifactPreviewKind.IMAGE && (
        <div className="floating-media-placeholder">
          {version.preview.imageUrl ?? version.preview.placeholder ?? "图片预览待生成"}
        </div>
      )}
      {version.preview.kind === ArtifactPreviewKind.MODEL_3D && (
        <Model3dArtifactViewer version={version} />
      )}
      {version.dependencies.length > 0 && (
        <section className="floating-section">
          <h3>依赖</h3>
          <ul className="floating-dependencies">
            {version.dependencies.map((dependency) => (
              <li key={`${dependency.kind}-${dependency.artifactId}`}>
                {dependency.label} · {dependency.status}
              </li>
            ))}
          </ul>
        </section>
      )}
      {!editableCode && (
        <p className="floating-note">
          关闭此浮窗不会改变中央主对话的内容和输入草稿。
        </p>
      )}
    </article>
  );
}

function isProposalDocument(version: ArtifactVersion): boolean {
  return (
    version.sourceEntityType === "proposal" ||
    version.mimeType === "application/vnd.zhangwen.proposal+json"
  );
}

function isEditableCodeVersion(version: ArtifactVersion | null): boolean {
  return Boolean(
    version?.preview.kind === ArtifactPreviewKind.CODE &&
      version.sourceEntityType === "code" &&
      version.sourceEntityId,
  );
}

function artifactStatusLabel(status: string): string {
  return {
    [ArtifactStatus.DRAFT]: "草稿",
    [ArtifactStatus.GENERATING]: "生成中",
    [ArtifactStatus.NEEDS_REVIEW]: "待确认",
    [ArtifactStatus.APPROVED]: "已确认",
    [ArtifactStatus.REJECTED]: "已退回",
    [ArtifactStatus.STALE]: "已过期",
    [ArtifactStatus.FAILED]: "失败",
    [ArtifactStatus.ARCHIVED]: "已归档",
  }[status] ?? status;
}

function selectVersion(
  artifact?: ArtifactDefinition | null,
  versionId?: string
): ArtifactVersion | null {
  if (!artifact) return null;
  return (
    artifact.versions.find((version) => version.id === versionId) ??
    artifact.versions.find((version) => version.id === artifact.currentVersionId) ??
    artifact.versions[0] ??
    null
  );
}
