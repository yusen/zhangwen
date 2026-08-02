import {
  type ArtifactDefinition,
  type CadIntentResult,
  type CadIntentWorkspace,
  type CapabilityCoverage,
  type ProjectProgressSnapshot,
  type ProjectRelease,
  type ProjectState,
  type ProjectVersion,
  type ProjectWorkspace,
  type ProjectWorkspaceKind,
} from "@zhangwen/contracts";
import { WorkspaceHeader } from "./pages/common";
import { OverviewPage } from "./pages/OverviewPage";
import { EngineeringPage, type EngineeringWorkspaceView } from "./pages/EngineeringPage";
import { StructurePage } from "./pages/StructurePage";
import { DeliveryPage } from "./pages/DeliveryPage";

export type { EngineeringWorkspaceView } from "./pages/EngineeringPage";

interface V2WorkspaceProps {
  kind: ProjectWorkspaceKind;
  workspace: ProjectWorkspace | null;
  state: ProjectState | null;
  coverage: CapabilityCoverage | null;
  versions: ProjectVersion[];
  releases: ProjectRelease[];
  artifacts: ArtifactDefinition[];
  artifactsLoading: boolean;
  artifactsError: string | null;
  progress: ProjectProgressSnapshot | null;
  progressLoading: boolean;
  progressError: string | null;
  deviceRefreshRevision: number;
  engineeringView: EngineeringWorkspaceView;
  onEngineeringViewChange: (view: EngineeringWorkspaceView) => void;
  professionalMode: boolean;
  cadWorkspace: CadIntentWorkspace | null;
  cadBusy: boolean;
  cadError: string | null;
  cadLastResult: CadIntentResult | null;
  onCadSubmit: (prompt: string, mode: "draft" | "edit") => Promise<unknown>;
  onCadConfirm: (revisionId: string) => Promise<unknown>;
  onCadBuild: (revisionId: string) => Promise<unknown>;
  onCadUndo: (revisionId: string) => Promise<unknown>;
  onOpenArtifact: (artifactId: string, versionId?: string | null) => void;
  onOpenAi: () => void;
  onOpenJobs: () => void;
  onOpenWorkspace: (kind: ProjectWorkspaceKind) => void;
}

export function V2Workspace({
  kind,
  workspace,
  state,
  coverage,
  versions,
  releases,
  artifacts,
  artifactsLoading,
  artifactsError,
  progress,
  progressLoading,
  progressError,
  deviceRefreshRevision,
  engineeringView,
  onEngineeringViewChange,
  professionalMode,
  cadWorkspace,
  cadBusy,
  cadError,
  cadLastResult,
  onCadSubmit,
  onCadConfirm,
  onCadBuild,
  onCadUndo,
  onOpenArtifact,
  onOpenAi,
  onOpenJobs,
  onOpenWorkspace,
}: V2WorkspaceProps) {
  if (!workspace) {
    return (
      <main className="v2-workspace v2-empty-workspace" data-testid="v2-workspace">
        <div>
          <span className="v2-eyebrow">AI 创客工程工作台</span>
          <h1>从一个真实项目开始</h1>
          <p>自由描述想法，掌问会把意图整理为可检查、可提交的工程变化。</p>
        </div>
      </main>
    );
  }

  return (
    <main className="v2-workspace" data-testid="v2-workspace">
      <WorkspaceHeader
        title={workspaceTitle(kind)}
        subtitle={workspaceSubtitle(kind)}
        state={state}
        professionalMode={professionalMode}
        onOpenAi={onOpenAi}
        onOpenJobs={onOpenJobs}
      />
      {kind === "overview" && (
        <OverviewPage
          workspace={workspace}
          state={state}
          coverage={coverage}
          artifacts={artifacts}
          versions={versions}
          professionalMode={professionalMode}
          onOpenWorkspace={onOpenWorkspace}
        />
      )}
      {kind === "engineering" && (
        <EngineeringPage
          workspace={workspace}
          state={state}
          artifacts={artifacts}
          artifactsLoading={artifactsLoading}
          artifactsError={artifactsError}
          progress={progress}
          progressLoading={progressLoading}
          progressError={progressError}
          professionalMode={professionalMode}
          deviceRefreshRevision={deviceRefreshRevision}
          section={engineeringView}
          onSectionChange={onEngineeringViewChange}
          onOpenArtifact={onOpenArtifact}
        />
      )}
      {kind === "structure" && (
        <StructurePage
          state={state}
          professionalMode={professionalMode}
          workspace={cadWorkspace}
          busy={cadBusy}
          error={cadError}
          lastResult={cadLastResult}
          onSubmit={onCadSubmit}
          onConfirm={onCadConfirm}
          onBuild={onCadBuild}
          onUndo={onCadUndo}
        />
      )}
      {kind === "delivery" && (
        <DeliveryPage
          versions={versions}
          releases={releases}
          state={state}
          artifacts={artifacts}
          artifactsLoading={artifactsLoading}
          artifactsError={artifactsError}
          professionalMode={professionalMode}
        />
      )}
    </main>
  );
}

function workspaceTitle(kind: ProjectWorkspaceKind): string {
  return { overview: "项目概览", engineering: "制作与验证", structure: "3D 结构设计", delivery: "项目成果" }[kind];
}

function workspaceSubtitle(kind: ProjectWorkspaceKind): string {
  return {
    overview: "查看想法、当前方案和下一步。",
    engineering: "核对硬件、代码和验证结果，并安全上传到设备。",
    structure: "描述想要的外形，生成并预览可制造的 3D 模型。",
    delivery: "集中查看已经完成的文档、代码和 3D 模型。",
  }[kind];
}
