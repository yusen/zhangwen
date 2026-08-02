import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArtifactPreviewKind,
  FloatingWindowKind,
  ProjectWorkspaceKind,
  type AuthAccount,
  type ArtifactDefinition,
  type ArtifactVersion,
  type CodeRun,
  type ExpertConversation,
  type ExpertType,
  type FloatingWindowSpec,
  type ProjectWorkspaceKind as ProjectWorkspaceKindType,
} from "@zhangwen/contracts";
import { CenterChat, type CenterChatInteractionControls } from "../layout/CenterChat";
import { ProjectCreationDialog } from "../projects/ProjectCreationDialog";
import {
  HardwareSelectionDialog,
  selectedProjectHardwareIds,
} from "../hardware/HardwareSelectionDialog";
import { SettingsDialog } from "../settings/SettingsDialog";
import { useProjects, type CreateProjectFromIdeaInput } from "../../hooks/useProjects";
import { useLlmSettings } from "../../hooks/useLlmSettings";
import { useV2ProjectData } from "../../hooks/useV2ProjectData";
import { useV2CadWorkspace } from "../../hooks/useV2CadWorkspace";
import { useV2Artifacts } from "../../hooks/useV2Artifacts";
import { useProjectProgress } from "../../hooks/useProjectProgress";
import { useHealthCheck } from "../../hooks/useHealthCheck";
import { V2ChangeSetPanel } from "./V2ChangeSetPanel";
import { V2Workspace, type EngineeringWorkspaceView } from "./V2Workspace";
import { V2LocalBridgeDialog } from "./V2LocalBridgeDialog";
import { FloatingWindow } from "../floating/FloatingWindow";
import { getArtifact } from "../../services/projectsApi";
import { IconRail, type StudioView } from "./shell/IconRail";
import { StageHeader } from "./shell/StageHeader";
import { Inspector, type InspectorTab } from "./shell/Inspector";
import { StatusBar } from "./shell/StatusBar";
import { ProjectDrawer } from "./shell/ProjectDrawer";
import { providerLabel, stageLabel } from "./shell/labels";
import { DeviceLabWorkspace } from "../device-lab/DeviceLabWorkspace";

export function V2AppShell({ account, onLogout }: { account?: AuthAccount; onLogout?: () => Promise<void> | void }) {
  const [view, setView] = useState<StudioView>("chat");
  const [workspaceTab, setWorkspaceTab] = useState<ProjectWorkspaceKindType>(ProjectWorkspaceKind.OVERVIEW);
  const [inspectorTab, setInspectorTab] = useState<InspectorTab>("work");
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [professionalMode, setProfessionalMode] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [bridgeOpen, setBridgeOpen] = useState(false);
  const [hardwarePickerOpen, setHardwarePickerOpen] = useState(false);
  const [artifactWindow, setArtifactWindow] = useState<{
    artifact: ArtifactDefinition;
    spec: FloatingWindowSpec;
  } | null>(null);
  const [artifactWindowDirty, setArtifactWindowDirty] = useState(false);
  const [deviceRefreshBump, setDeviceRefreshBump] = useState(0);
  const [engineeringView, setEngineeringView] = useState<EngineeringWorkspaceView>("hardware");
  const [expertOverrideId, setExpertOverrideId] = useState<string | null>(null);
  const controlsRef = useRef<CenterChatInteractionControls | null>(null);
  const llmSettings = useLlmSettings();
  const health = useHealthCheck();
  const projects = useProjects(llmSettings.config?.defaultModel);
  const projectId = projects.activeWorkspace?.project.id ?? null;
  const v2 = useV2ProjectData(projectId);
  const cad = useV2CadWorkspace(projectId);
  const projectUpdatedAt = projects.activeWorkspace?.project.updatedAt ?? null;
  const artifacts = useV2Artifacts(projectId, projectUpdatedAt);
  const progress = useProjectProgress(
    projectId,
    v2.data?.state.projectVersion ?? 0,
    projectUpdatedAt,
  );
  const deviceRefreshRevision = (projectUpdatedAt ? Date.parse(projectUpdatedAt) || 0 : 0)
    + deviceRefreshBump;
  const models = useMemo(
    () => llmSettings.config
      ? llmSettings.models.filter((model) => model.provider === llmSettings.config?.provider)
      : llmSettings.models,
    [llmSettings.config, llmSettings.models],
  );
  const conversations = (projects.activeWorkspace?.expertConversations ?? []).filter(
    (conversation) => !conversation.archivedLegacyThread,
  );
  const activeWorkspaceKind = view === "chat" || view === "lab" ? workspaceTab : view;
  const baseChatContext = v2ChatContext(
    activeWorkspaceKind,
    engineeringView,
    v2.data?.state.projectVersion ?? 0,
  );
  const chatContext = view === "lab"
    ? {
        ...baseChatContext,
        label: "设备实验室",
        view: "device-lab",
        hint: "只为 K10 与 XIAO ESP32S3 Sense 提供本地仿真和图形化调参。",
      }
    : baseChatContext;
  const contextualExpertId = projects.activeWorkspace?.experts?.find(
    (expert) => expert.expertType === chatContext.expertType && !expert.removedAt,
  )?.id ?? null;
  const selectedExpertId = expertOverrideId
    ?? contextualExpertId
    ?? projects.activeWorkspace?.project.activeExpertId
    ?? conversations[0]?.projectExpertId
    ?? null;

  useEffect(() => {
    setExpertOverrideId(null);
  }, [activeWorkspaceKind, projectId]);

  useEffect(() => {
    if (typeof window.matchMedia !== "function") return undefined;
    const narrowViewport = window.matchMedia("(max-width: 860px)");
    const collapseInspector = (event: MediaQueryListEvent) => {
      if (event.matches) setInspectorOpen(false);
    };

    if (narrowViewport.matches) setInspectorOpen(false);
    narrowViewport.addEventListener("change", collapseInspector);
    return () => narrowViewport.removeEventListener("change", collapseInspector);
  }, []);

  const changeView = (next: StudioView) => {
    if (!professionalMode && next !== "chat" && next !== "lab") return;
    setView(next);
    if (next !== "chat" && next !== "lab") setWorkspaceTab(next);
  };

  const changeProfessionalMode = (enabled: boolean) => {
    setProfessionalMode(enabled);
    if (!enabled) setView("chat");
  };

  const openProject = async (targetId: string) => {
    setDrawerOpen(false);
    if (targetId === projectId) return;
    await controlsRef.current?.flushDraft();
    await projects.open(targetId);
  };

  const createProject = async (input: CreateProjectFromIdeaInput) => {
    await controlsRef.current?.flushDraft();
    return projects.create(input);
  };

  const addExpert = async (expertType: ExpertType): Promise<ExpertConversation | null> => {
    if (!projectId) return null;
    const workspace = await projects.addExpert(projectId, expertType, true);
    const expert = workspace.experts?.find((item) => item.expertType === expertType && !item.removedAt);
    return workspace.expertConversations?.find((item) => item.projectExpertId === expert?.id) ?? null;
  };

  const openArtifact = async (artifactId?: string | null, versionId?: string | null) => {
    if (!projectId || !artifactId) {
      changeView(ProjectWorkspaceKind.DELIVERY);
      return;
    }
    const response = await getArtifact(projectId, artifactId);
    const version = response.artifact.versions.find((item) => item.id === versionId)
      ?? response.artifact.versions.find((item) => item.id === response.artifact.currentVersionId)
      ?? response.artifact.versions[0];
    if (!version) return;
    setArtifactWindowDirty(false);
    setArtifactWindow({
      artifact: response.artifact,
      spec: artifactWindowSpec(response.artifact, version),
    });
  };

  const closeArtifactWindow = () => {
    if (
      artifactWindowDirty
      && !window.confirm("代码有未保存修改。确定关闭并放弃这些修改？")
    ) return;
    setArtifactWindow(null);
    setArtifactWindowDirty(false);
  };

  const handleCodeRunChanged = async (_artifactId: string, _codeRun: CodeRun) => {
    artifacts.refresh();
    v2.refresh();
    await progress.refresh();
    if (projectId) await projects.loadWorkspace(projectId);
    setDeviceRefreshBump((value) => value + 1);
  };

  const jobs = cad.workspace?.jobs ?? [];
  const runningJobs = jobs.filter((job) => job.status === "RUNNING" || job.status === "QUEUED").length;
  const pendingChangeSets = v2.data?.changeSets.filter(
    (item) => item.status === "READY" || item.status === "CONFIRMED",
  ) ?? [];
  const openJobs = () => {
    setInspectorTab("work");
    setInspectorOpen(true);
  };
  const hasProject = Boolean(projects.activeWorkspace);

  return (
    <div className={`zw-shell ${inspectorOpen ? "" : "is-inspector-collapsed"}`} data-testid="v2-app-shell">
      <IconRail
        view={view}
        onViewChange={changeView}
        onOpenProjects={() => setDrawerOpen(true)}
        onOpenBridge={() => setBridgeOpen(true)}
        onOpenSettings={() => setSettingsOpen(true)}
        onLogout={onLogout ? () => void onLogout() : undefined}
        accountName={account?.displayName}
        professionalMode={professionalMode}
      />

      <div className="zw-stage">
        <StageHeader
          projectName={projects.activeWorkspace?.project.name ?? null}
          versionTag={v2.data
            ? professionalMode
              ? `V${v2.data.state.projectVersion} · ${stageLabel(v2.data.state.stage)}`
              : stageLabel(v2.data.state.stage)
            : null}
          stageText={v2.data ? null : "项目状态同步中"}
          professionalMode={professionalMode}
          onToggleProfessionalMode={() => changeProfessionalMode(!professionalMode)}
          inspectorOpen={inspectorOpen}
          onToggleInspector={() => setInspectorOpen((value) => !value)}
        />
        <div className="zw-stage-body">
          {!hasProject && (
            <div className="zw-stage-empty">
              <div>
                <span className="zw-eyebrow">AI 创客工程工作台</span>
                <h1>从一个真实项目开始</h1>
                <p>自由描述想法，掌问会把意图整理为可检查、可提交的工程变化。</p>
                <button type="button" className="zw-primary-btn" onClick={() => setCreateOpen(true)}>
                  ＋ 新建项目
                </button>
              </div>
            </div>
          )}
          {hasProject && view !== "chat" && view !== "lab" && (
            <V2Workspace
              kind={activeWorkspaceKind}
              workspace={projects.activeWorkspace}
              state={v2.data?.state ?? null}
              coverage={v2.data?.coverage ?? null}
              versions={v2.data?.versions ?? []}
              releases={v2.data?.releases ?? []}
              artifacts={artifacts.artifacts}
              artifactsLoading={artifacts.loading}
              artifactsError={artifacts.error}
              progress={progress.progress}
              progressLoading={progress.loading}
              progressError={progress.error}
              deviceRefreshRevision={deviceRefreshRevision}
              engineeringView={engineeringView}
              onEngineeringViewChange={(next) => {
                setEngineeringView(next);
                if (next === "device") {
                  setInspectorTab("device");
                  setInspectorOpen(true);
                }
              }}
              professionalMode={professionalMode}
              cadWorkspace={cad.workspace}
              cadBusy={cad.busy || cad.loading}
              cadError={cad.error}
              cadLastResult={cad.lastResult}
              onCadSubmit={async (prompt, mode) => {
                if (!v2.data) throw new Error("项目状态尚未同步，请稍后重试。");
                const result = await cad.submit({
                  prompt,
                  mode,
                  baseProjectVersion: v2.data.state.projectVersion,
                  currentRevisionId: cad.workspace?.currentRevision?.id,
                });
                v2.refresh();
                artifacts.refresh();
                return result;
              }}
              onCadConfirm={async (revisionId) => {
                const result = await cad.confirmAndBuild(revisionId);
                v2.refresh();
                artifacts.refresh();
                return result;
              }}
              onCadBuild={async (revisionId) => {
                const result = await cad.build(revisionId);
                v2.refresh();
                artifacts.refresh();
                return result;
              }}
              onCadUndo={async (revisionId) => {
                if (!v2.data) throw new Error("项目状态尚未同步，请稍后重试。");
                const result = await cad.undo(revisionId, v2.data.state.projectVersion);
                v2.refresh();
                return result;
              }}
              onOpenArtifact={(artifactId, versionId) => {
                void openArtifact(artifactId, versionId);
              }}
              onOpenAi={() => changeView("chat")}
              onOpenJobs={openJobs}
              onOpenWorkspace={(kind) => changeView(kind)}
            />
          )}
          {hasProject && view === "lab" && projectId && (
            <DeviceLabWorkspace
              projectId={projectId}
              professionalMode={professionalMode}
              onBackToChat={() => setView("chat")}
            />
          )}
          <div className="zw-stage-chat" hidden={!hasProject || view !== "chat"}>
            <CenterChat
              config={llmSettings.config}
              workspace={projects.activeWorkspace}
              selectedExpertId={selectedExpertId}
              models={models}
              professionalMode={professionalMode}
              workspaceContext={{
                workspaceKind: activeWorkspaceKind,
                workspaceView: chatContext.view,
                projectVersion: chatContext.projectVersion,
              }}
              draftSaving={projects.draftSaving}
              draftSaveError={projects.draftSaveError}
              onOpenSettings={() => setSettingsOpen(true)}
              onOpenArtifact={(artifactId, versionId) => {
                void openArtifact(artifactId, versionId);
              }}
              onOpenHardwareSelection={() => setHardwarePickerOpen(true)}
              onSaveDraft={projects.saveDraft}
              onSelectExpert={(expertId) => {
                setExpertOverrideId(expertId);
                if (projectId) void projects.activateExpert(projectId, expertId);
              }}
              onAddExpert={addExpert}
              onSelectModel={projects.setModel}
              onReloadProject={async (id) => {
                await projects.loadWorkspace(id);
                v2.refresh();
                artifacts.refresh();
                await progress.refresh();
              }}
              onDismissPendingItem={async (pendingId) => projectId ? projects.dismissPending(projectId, pendingId) : null}
              onInteractionControlsChange={(controls) => { controlsRef.current = controls; }}
            />
          </div>
        </div>
      </div>

      <Inspector
        open={inspectorOpen}
        contextLabel={chatContext.label}
        contextHint={chatContext.hint}
        tab={inspectorTab}
        onTabChange={setInspectorTab}
        changeSetPanel={projectId && pendingChangeSets.length ? (
          <V2ChangeSetPanel
            projectId={projectId}
            changeSets={pendingChangeSets}
            professionalMode={professionalMode}
            onChanged={v2.refresh}
          />
        ) : null}
        pendingChangeCount={pendingChangeSets.length}
        facts={v2.data?.state.facts ?? []}
        professionalMode={professionalMode}
        artifacts={artifacts.artifacts}
        onOpenArtifact={(artifactId, versionId) => {
          void openArtifact(artifactId, versionId);
        }}
        jobs={jobs}
        workspace={projects.activeWorkspace}
        deviceRefreshRevision={deviceRefreshRevision}
        onOpenDeviceLab={() => setView("lab")}
      />

      <StatusBar
        healthStatus={health.status}
        providerText={providerLabel(llmSettings.config?.provider)}
        runningJobs={runningJobs}
        professionalMode={professionalMode}
        onOpenJobs={openJobs}
      />

      {drawerOpen && (
        <ProjectDrawer
          projects={projects.projects}
          activeProjectId={projectId}
          versions={v2.data?.versions ?? []}
          onSelectProject={(targetId) => void openProject(targetId)}
          onCreateProject={() => {
            setDrawerOpen(false);
            setCreateOpen(true);
          }}
          onClose={() => setDrawerOpen(false)}
        />
      )}

      {v2.error && <div className="v2-toast" role="alert">{v2.error}<button type="button" onClick={v2.refresh}>重试</button></div>}
      {settingsOpen && <SettingsDialog config={llmSettings.config} models={llmSettings.models} saving={llmSettings.saving} testing={llmSettings.testing} message={llmSettings.message} error={llmSettings.error} professionalMode={professionalMode} onProfessionalModeChange={changeProfessionalMode} onSave={llmSettings.save} onClearKey={llmSettings.clearKey} onTest={llmSettings.test} onClose={() => setSettingsOpen(false)} />}
      <ProjectCreationDialog open={createOpen} professionalMode={professionalMode} onCreateProject={createProject} onClose={() => setCreateOpen(false)} />
      <HardwareSelectionDialog
        open={hardwarePickerOpen && Boolean(projects.activeWorkspace)}
        title="添加项目电子器件"
        description="选择后会更新当前项目硬件，三师下一轮规划将读取最新结果。"
        initialSelectedIds={selectedProjectHardwareIds(
          projects.activeWorkspace?.sharedContext?.confirmedFacts,
        )}
        confirmLabel="添加到项目"
        onConfirm={async (selectedHardwareIds) => {
          if (!projectId) throw new Error("请先打开一个项目。");
          const response = await projects.setHardware(projectId, selectedHardwareIds);
          v2.refresh();
          await progress.refresh();
          return { warnings: response.selectedHardwareWarnings };
        }}
        onClose={() => setHardwarePickerOpen(false)}
      />
      {bridgeOpen && <V2LocalBridgeDialog projectId={projectId} professionalMode={professionalMode} onClose={() => setBridgeOpen(false)} />}
      {artifactWindow && (
        <div className="floating-layer" aria-label="浮窗层">
          <FloatingWindow
            spec={artifactWindow.spec}
            artifact={artifactWindow.artifact}
            active
            onFocus={() => undefined}
            onClose={closeArtifactWindow}
            onMinimize={() => setArtifactWindow((current) => current ? {
              ...current,
              spec: { ...current.spec, minimized: !current.spec.minimized },
            } : current)}
            onToggleMaximize={() => setArtifactWindow((current) => current ? {
              ...current,
              spec: { ...current.spec, maximized: !current.spec.maximized },
            } : current)}
            onDirtyChange={(_id, dirty) => setArtifactWindowDirty(dirty)}
            onCodeRunChanged={handleCodeRunChanged}
          />
        </div>
      )}
    </div>
  );
}

function artifactWindowSpec(
  artifact: ArtifactDefinition,
  version: ArtifactVersion,
): FloatingWindowSpec {
  const codeWindow = version.preview.kind === ArtifactPreviewKind.CODE;
  const kind = codeWindow
    ? FloatingWindowKind.CODE
    : version.preview.kind === ArtifactPreviewKind.MODEL_3D
      ? FloatingWindowKind.MODEL_3D
      : version.preview.kind === ArtifactPreviewKind.IMAGE
        ? FloatingWindowKind.IMAGE
        : FloatingWindowKind.DOCUMENT;
  return {
    id: `v2_window_${artifact.id}_${version.id}`,
    kind,
    title: `${artifact.title} v${version.version}`,
    artifactId: artifact.id,
    versionId: version.id,
    singletonKey: `${artifact.id}:${version.id}`,
    initialBounds: codeWindow
      ? { x: 48, y: 60, width: 920, height: 640 }
      : { x: 80, y: 72, width: 720, height: 560 },
    zIndex: 120,
  };
}

interface V2ChatContext {
  label: string;
  view: string;
  hint: string;
  expertType: ExpertType;
  projectVersion: number;
}

function v2ChatContext(
  workspace: ProjectWorkspaceKindType,
  engineeringView: EngineeringWorkspaceView,
  projectVersion: number,
): V2ChatContext {
  if (workspace === ProjectWorkspaceKind.ENGINEERING) {
    const view = ({
      hardware: ["工程 · 硬件", "hardware", "核对器件、供电和接线要求。"],
      code: ["工程 · 代码", "code", "围绕当前代码和检查结果协作。"],
      device: ["工程 · 设备", "device", "区分设备附加、接管、上传和运行证据；执行仍需本地确认。"],
      validation: ["工程 · 验证", "validation", "只依据软件、模拟和硬件证据判断完成度。"],
    } as const)[engineeringView];
    return {
      label: view[0],
      view: view[1],
      hint: view[2],
      expertType: "smart_engineer",
      projectVersion,
    };
  }
  if (workspace === ProjectWorkspaceKind.STRUCTURE) {
    return {
      label: "结构设计",
      view: "cad",
      hint: "围绕当前模型、尺寸和生成结果协作。",
      expertType: "structure_engineer",
      projectVersion,
    };
  }
  if (workspace === ProjectWorkspaceKind.DELIVERY) {
    return {
      label: "成果交付",
      view: "release",
      hint: "核对项目成果、验证结果和待处理问题。",
      expertType: "smart_engineer",
      projectVersion,
    };
  }
  return {
    label: "项目概览",
    view: "overview",
    hint: "聚焦目标、约束、成功标准与唯一当前推荐方案。",
    expertType: "problem_guide",
    projectVersion,
  };
}
