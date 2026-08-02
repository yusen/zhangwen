import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ArtifactPreviewKind, FloatingWindowKind } from "@zhangwen/contracts";
import type {
  AuthAccount,
  ArtifactDefinition,
  AgentPackageSummary,
  ArtifactVersion,
  CodeRun,
  ExpertConversation,
  ExpertType,
  FloatingWindowSpec,
  HardwareSkillSummary,
  MechanicalProfileSummary,
} from "@zhangwen/contracts";
import { TopBar } from "./TopBar";
import { LeftSidebar } from "./LeftSidebar";
import { CenterChat, type CenterChatInteractionControls } from "./CenterChat";
import { RightPanel } from "./RightPanel";
import { FloatingWindow } from "../floating/FloatingWindow";
import { SettingsDialog } from "../settings/SettingsDialog";
import { ConfirmDialog } from "../shared/ConfirmDialog";
import { ProjectCreationDialog } from "../projects/ProjectCreationDialog";
import { ProjectToolsDialog } from "../projects/ProjectToolsDialog";
import {
  HardwareSelectionDialog,
  selectedProjectHardwareIds,
} from "../hardware/HardwareSelectionDialog";
import { useLlmSettings } from "../../hooks/useLlmSettings";
import type { CreateProjectFromIdeaInput } from "../../hooks/useProjects";
import { useProjects } from "../../hooks/useProjects";
import { getArtifact } from "../../services/projectsApi";
import { useHealthCheck } from "../../hooks/useHealthCheck";
import { useProjectEngineeringState } from "../../hooks/useProjectEngineeringState";
import { useProjectProgress } from "../../hooks/useProjectProgress";

export type RightTab = "work" | "artifacts" | "devices";
interface FloatingWindowEntry {
  spec: FloatingWindowSpec;
  artifact?: ArtifactDefinition;
  hardwareComponentId?: string;
  hardwareSkillName?: string;
  agentExpertType?: ExpertType;
  mechanicalProfile?: MechanicalProfileSummary;
}

interface AppShellProps {
  account?: AuthAccount;
  onLogout?: () => Promise<void> | void;
}

export function AppShell({ account, onLogout }: AppShellProps = {}) {
  const [narrowViewport, setNarrowViewport] = useState(isNarrowViewport);
  const [activeTab, setActiveTab] = useState<RightTab>("work");
  const [sidebarCollapsed, setSidebarCollapsed] = useState(isNarrowViewport);
  const [rightPanelCollapsed, setRightPanelCollapsed] = useState(isNarrowViewport);
  const [floatingWindows, setFloatingWindows] = useState<FloatingWindowEntry[]>([]);
  const floatingWindowsRef = useRef<FloatingWindowEntry[]>([]);
  const dirtyFloatingWindowIds = useRef(new Set<string>());
  const [closedWindowState, setClosedWindowState] = useState<
    Record<string, FloatingWindowSpec>
  >({});
  const [nextZIndex, setNextZIndex] = useState(1000);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [projectCreateOpen, setProjectCreateOpen] = useState(false);
  const [projectToolsOpen, setProjectToolsOpen] = useState(false);
  const [projectHardwarePickerOpen, setProjectHardwarePickerOpen] = useState(false);
  const [professionalMode, setProfessionalMode] = useState(false);
  const [artifactRefreshRevision, setArtifactRefreshRevision] = useState(0);
  const [confirmationRefreshRevision, setConfirmationRefreshRevision] = useState(0);
  const [selectedExpertByProject, setSelectedExpertByProject] = useState<
    Record<string, string>
  >({});
  const [switchTarget, setSwitchTarget] = useState<string | null>(null);
  const [switchDiscardsDraft, setSwitchDiscardsDraft] = useState(false);
  const streamingRef = useRef(false);
  const centerChatControlsRef = useRef<CenterChatInteractionControls | null>(null);
  const llmSettings = useLlmSettings();
  const health = useHealthCheck();
  const projects = useProjects(llmSettings.config?.defaultModel);
  const activeProjectId = projects.activeWorkspace?.project.id ?? null;
  const activeProviderModels = useMemo(
    () => llmSettings.config
      ? llmSettings.models.filter((model) => model.provider === llmSettings.config?.provider)
      : llmSettings.models,
    [llmSettings.config, llmSettings.models],
  );
  const engineeringState = useProjectEngineeringState(
    activeProjectId,
    confirmationRefreshRevision,
    projects.activeWorkspace?.project.updatedAt,
  );
  const projectProgress = useProjectProgress(
    activeProjectId,
    confirmationRefreshRevision + artifactRefreshRevision,
    projects.activeWorkspace?.project.updatedAt,
  );
  const expertConversations = (
    projects.activeWorkspace?.expertConversations ?? []
  ).filter((conversation) => !conversation.archivedLegacyThread);
  const selectedExpertCandidate = activeProjectId
    ? selectedExpertByProject[activeProjectId]
    : undefined;
  const selectedExpertId =
    selectedExpertCandidate &&
    expertConversations.some(
      (conversation) => conversation.projectExpertId === selectedExpertCandidate
    )
      ? selectedExpertCandidate
      : projects.activeWorkspace?.project.activeExpertId ??
        expertConversations[0]?.projectExpertId ??
        null;

  useEffect(() => {
    floatingWindowsRef.current = floatingWindows;
  }, [floatingWindows]);

  useEffect(() => {
    const handleViewportResize = () => {
      const narrow = isNarrowViewport();
      setNarrowViewport(narrow);
      if (narrow) {
        setSidebarCollapsed(true);
        setRightPanelCollapsed(true);
      }
    };
    window.addEventListener("resize", handleViewportResize);
    return () => window.removeEventListener("resize", handleViewportResize);
  }, []);

  useEffect(() => {
    const drawerSelector = !sidebarCollapsed
      ? '[data-testid="left-sidebar"]'
      : !rightPanelCollapsed
        ? '[data-testid="right-panel"] .right-panel-shell'
        : null;
    if (!narrowViewport || !drawerSelector) return;
    const drawer = document.querySelector<HTMLElement>(drawerSelector);
    if (!drawer) return;
    const previousFocus = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const focusableSelector = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])';
    const frame = window.requestAnimationFrame(() => {
      drawer.querySelector<HTMLElement>(focusableSelector)?.focus();
    });
    const handleKeyDown = (event: KeyboardEvent) => {
      const nestedModal = document.querySelector<HTMLElement>(
        '[role="dialog"][aria-modal="true"]',
      );
      if (nestedModal) return;
      if (event.key === "Escape") {
        event.preventDefault();
        if (!sidebarCollapsed) setSidebarCollapsed(true);
        if (!rightPanelCollapsed) setRightPanelCollapsed(true);
        return;
      }
      if (event.key !== "Tab") return;
      const focusable = Array.from(
        drawer.querySelectorAll<HTMLElement>(focusableSelector),
      ).filter((element) => element.offsetParent !== null);
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) {
        event.preventDefault();
        return;
      }
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => {
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
      previousFocus?.focus();
    };
  }, [narrowViewport, rightPanelCollapsed, sidebarCollapsed]);

  useEffect(() => {
    const workspace = projects.activeWorkspace;
    const defaultModel = llmSettings.config?.defaultModel;
    if (!workspace || !defaultModel || activeProviderModels.length === 0) return;
    if (activeProviderModels.some((model) => model.id === workspace.project.selectedModel)) return;
    void projects.setModel(workspace.project.id, defaultModel);
  }, [activeProviderModels, llmSettings.config?.defaultModel, projects.activeWorkspace, projects.setModel]);

  const handleSelectExpert = useCallback(
    (projectExpertId: string) => {
      if (!activeProjectId) return;
      setSelectedExpertByProject((current) =>
        current[activeProjectId] === projectExpertId
          ? current
          : { ...current, [activeProjectId]: projectExpertId }
      );
    },
    [activeProjectId]
  );

  const handleOpenFloating = useCallback((
    spec: FloatingWindowSpec,
    artifact?: ArtifactDefinition,
    hardwareComponentId?: string,
    hardwareSkillName?: string,
    agentExpertType?: ExpertType,
    mechanicalProfile?: MechanicalProfileSummary,
  ) => {
    const singletonKey = spec.singletonKey ?? spec.id;
    const currentWindows = floatingWindowsRef.current;
    const existing = currentWindows.findIndex(
      (entry) => (entry.spec.singletonKey ?? entry.spec.id) === singletonKey,
    );
    const evicted =
      existing < 0 && currentWindows.length >= 3 ? currentWindows[0] : undefined;
    if (
      evicted &&
      dirtyFloatingWindowIds.current.has(evicted.spec.id) &&
      !window.confirm(
        `“${evicted.spec.title}”有未保存修改。继续打开新浮窗将关闭它，是否放弃这些修改？`,
      )
    ) {
      return false;
    }
    if (evicted) {
      dirtyFloatingWindowIds.current.delete(evicted.spec.id);
      const evictedKey = evicted.spec.singletonKey ?? evicted.spec.id;
      setClosedWindowState((state) => ({
        ...state,
        [evictedKey]: evicted.spec,
      }));
    }
    if (isNarrowViewport()) {
      setRightPanelCollapsed(true);
    }
    const zIndex = nextZIndex + 1;
    setNextZIndex(zIndex);
    setFloatingWindows((current) => {
      const existing = current.findIndex(
        (entry) => (entry.spec.singletonKey ?? entry.spec.id) === singletonKey
      );
      const restored = closedWindowState[singletonKey];
      const nextSpec: FloatingWindowSpec = {
        ...spec,
        ...restored,
        id: spec.id,
        title: spec.title,
        artifactId: spec.artifactId,
        versionId: spec.versionId,
        singletonKey,
        minimized: false,
        zIndex,
      };
      if (existing >= 0) {
        return current.map((entry, index) =>
          index === existing
            ? {
                spec: nextSpec,
                artifact,
                hardwareComponentId,
                hardwareSkillName,
                agentExpertType,
                mechanicalProfile,
              }
            : entry
        );
      }
      return [
        ...current.slice(-2),
        {
          spec: nextSpec,
          artifact,
          hardwareComponentId,
          hardwareSkillName,
          agentExpertType,
          mechanicalProfile,
        },
      ];
    });
    return true;
  }, [closedWindowState, nextZIndex]);

  const handleOpenHardwareSkill = useCallback(
    (skill: HardwareSkillSummary) => {
      const opened = handleOpenFloating(
        {
          id: `window_hardware_skill_${skill.skillName}`,
          kind: FloatingWindowKind.HARDWARE_SKILL,
          title: `${skill.displayName} · Hardware Skill`,
          singletonKey: `hardware-skill:${skill.skillName}`,
          initialBounds: { x: 48, y: 60, width: 920, height: 640 },
        },
        undefined,
        undefined,
        skill.skillName,
      );
      if (opened) {
        setSettingsOpen(false);
        setProjectToolsOpen(false);
      }
    },
    [handleOpenFloating],
  );

  const handleOpenAgentPackage = useCallback(
    (agentPackage: AgentPackageSummary) => {
      const opened = handleOpenFloating(
        {
          id: `window_agent_package_${agentPackage.expertType}`,
          kind: FloatingWindowKind.AGENT_PACKAGE,
          title: `${agentPackage.displayName} · 行为项目`,
          singletonKey: `agent-package:${agentPackage.expertType}`,
          initialBounds: { x: 48, y: 60, width: 920, height: 640 },
        },
        undefined,
        undefined,
        undefined,
        agentPackage.expertType,
      );
      if (opened) setSettingsOpen(false);
    },
    [handleOpenFloating],
  );

  const handleOpenMechanicalProfilePreview = useCallback(
    (profile: MechanicalProfileSummary) => {
      const opened = handleOpenFloating(
        {
          id: `window_mechanical_profile_${profile.profileId}_${profile.revision}`,
          kind: FloatingWindowKind.MECHANICAL_PROFILE,
          title: `${profile.displayName} · 机械档案预览`,
          singletonKey: `mechanical-profile:${profile.profileId}`,
          initialBounds: { x: 72, y: 64, width: 820, height: 620 },
        },
        undefined,
        undefined,
        undefined,
        undefined,
        profile,
      );
      if (opened) setSettingsOpen(false);
    },
    [handleOpenFloating],
  );

  const handleOpenArtifactById = useCallback(
    async (artifactId?: string | null, versionId?: string | null) => {
      const projectId = projects.activeWorkspace?.project.id;
      if (!projectId || !artifactId) return;
      try {
        const response = await getArtifact(projectId, artifactId);
        const version =
          response.artifact.versions.find((item) => item.id === versionId) ??
          response.artifact.versions.find(
            (item) => item.id === response.artifact.currentVersionId
          ) ??
          response.artifact.versions[0];
        if (!version) return;
        handleOpenFloating(
          artifactToWindowSpec(response.artifact, version),
          response.artifact
        );
      } catch {
        // Keep the central conversation unchanged if the artifact is unavailable.
      }
    },
    [handleOpenFloating, projects.activeWorkspace?.project.id]
  );

  const handleFocusFloating = useCallback((id: string) => {
    const zIndex = nextZIndex + 1;
    setNextZIndex(zIndex);
    setFloatingWindows((current) =>
      current.map((entry) =>
        entry.spec.id === id
          ? { ...entry, spec: { ...entry.spec, zIndex } }
          : entry
      )
    );
  }, [nextZIndex]);

  const handleCloseFloating = useCallback((id: string) => {
    const closing = floatingWindowsRef.current.find(
      (entry) => entry.spec.id === id,
    );
    if (
      closing &&
      dirtyFloatingWindowIds.current.has(id) &&
      !window.confirm(
        `“${closing.spec.title}”有未保存修改。确定关闭并放弃这些修改？`,
      )
    ) {
      return;
    }
    dirtyFloatingWindowIds.current.delete(id);
    setFloatingWindows((current) => {
      const closing = current.find((entry) => entry.spec.id === id);
      if (closing) {
        const key = closing.spec.singletonKey ?? closing.spec.id;
        setClosedWindowState((state) => ({ ...state, [key]: closing.spec }));
      }
      return current.filter((entry) => entry.spec.id !== id);
    });
  }, []);

  const handleFloatingDirtyChange = useCallback((id: string, dirty: boolean) => {
    if (dirty) {
      dirtyFloatingWindowIds.current.add(id);
    } else {
      dirtyFloatingWindowIds.current.delete(id);
    }
  }, []);

  const handleProfessionalModeChange = useCallback((enabled: boolean) => {
    if (enabled) {
      setProfessionalMode(true);
      return;
    }

    const technicalWindows = floatingWindowsRef.current.filter((entry) =>
      entry.spec.kind === FloatingWindowKind.HARDWARE_SKILL ||
      entry.spec.kind === FloatingWindowKind.AGENT_PACKAGE ||
      entry.spec.kind === FloatingWindowKind.MECHANICAL_PROFILE
    );
    const dirtyTechnicalWindows = technicalWindows.filter((entry) =>
      dirtyFloatingWindowIds.current.has(entry.spec.id)
    );
    if (
      dirtyTechnicalWindows.length > 0 &&
      !window.confirm(
        `关闭专业模式将关闭 ${technicalWindows.length} 个行为/硬件项目浮窗，并放弃 ${dirtyTechnicalWindows.length} 个未保存草稿。确定继续？`,
      )
    ) {
      return;
    }

    if (technicalWindows.length > 0) {
      const technicalIds = new Set(technicalWindows.map((entry) => entry.spec.id));
      for (const id of technicalIds) dirtyFloatingWindowIds.current.delete(id);
      setClosedWindowState((current) => {
        const next = { ...current };
        for (const entry of technicalWindows) {
          next[entry.spec.singletonKey ?? entry.spec.id] = entry.spec;
        }
        return next;
      });
      setFloatingWindows((current) =>
        current.filter((entry) => !technicalIds.has(entry.spec.id))
      );
    }
    setProfessionalMode(false);
  }, []);

  const handleMinimizeFloating = useCallback((id: string) => {
    setFloatingWindows((current) =>
      current.map((entry) =>
        entry.spec.id === id
          ? { ...entry, spec: { ...entry.spec, minimized: !entry.spec.minimized } }
          : entry
      )
    );
  }, []);

  const handleToggleMaximizeFloating = useCallback((id: string) => {
    setFloatingWindows((current) =>
      current.map((entry) =>
        entry.spec.id === id
          ? {
              ...entry,
              spec: {
                ...entry.spec,
                maximized: !entry.spec.maximized,
                minimized: false,
              },
            }
          : entry
      )
    );
  }, []);

  const handleCodeRunChanged = useCallback(
    async (artifactId: string, codeRun: CodeRun) => {
      setArtifactRefreshRevision((current) => current + 1);
      setConfirmationRefreshRevision((current) => current + 1);
      try {
        const response = await getArtifact(codeRun.projectId, artifactId);
        const nextVersion =
          response.artifact.versions.find(
            (version) => version.id === codeRun.artifactVersionId,
          ) ??
          response.artifact.versions.find(
            (version) => version.id === response.artifact.currentVersionId,
          ) ??
          response.artifact.versions[0] ??
          null;
        setFloatingWindows((current) =>
          current.map((entry) => {
            if (entry.spec.artifactId !== artifactId || !nextVersion) return entry;
            return {
              artifact: response.artifact,
              spec: {
                ...entry.spec,
                title: `${response.artifact.title} v${nextVersion.version}`,
                versionId: nextVersion.id,
                singletonKey: `${artifactId}:${nextVersion.id}`,
              },
            };
          }),
        );
      } catch {
        // The editor keeps the saved CodeRun visible even if artifact refresh is delayed.
      }
    },
    [],
  );

  const handleConfirmationChanged = useCallback(() => {
    setConfirmationRefreshRevision((current) => current + 1);
  }, []);

  const handleOpenProject = useCallback(
    async (projectId: string) => {
      if (projectId === activeProjectId) return;
      if (streamingRef.current) {
        setSwitchTarget(projectId);
        setSwitchDiscardsDraft(false);
        return;
      }
      try {
        await centerChatControlsRef.current?.flushDraft();
      } catch {
        setSwitchTarget(projectId);
        setSwitchDiscardsDraft(true);
        return;
      }
      await projects.open(projectId);
    },
    [activeProjectId, projects]
  );

  const handleLogout = useCallback(async () => {
    if (!onLogout) return;
    if (
      streamingRef.current &&
      !window.confirm("当前正在生成回复。退出会停止生成，是否继续？")
    ) {
      return;
    }
    if (streamingRef.current) {
      await centerChatControlsRef.current?.stopStreaming();
    }
    try {
      await centerChatControlsRef.current?.flushDraft();
    } catch {
      if (!window.confirm("草稿保存失败。退出将放弃尚未保存的内容，是否继续？")) {
        return;
      }
    }
    await onLogout();
  }, [onLogout]);

  const handleCreateProject = useCallback(
    async (input: CreateProjectFromIdeaInput) => {
      try {
        await centerChatControlsRef.current?.flushDraft();
      } catch {
        throw new Error("当前项目草稿保存失败，请先重试保存后再创建新项目。");
      }
      const workspace = await projects.create(input);
      return workspace;
    },
    [projects]
  );

  const handleAddProjectExpert = useCallback(
    async (expertType: ExpertType) => {
      if (!activeProjectId) return null;
      const workspace = await projects.addExpert(activeProjectId, expertType, true);
      const addedExpert = (workspace.experts ?? []).find(
        (expert) =>
          expert.expertType === expertType &&
          !expert.archivedLegacyThread &&
          !expert.removedAt,
      );
      if (addedExpert) {
        setSelectedExpertByProject((current) => ({
          ...current,
          [activeProjectId]: addedExpert.id,
        }));
      }
      return (workspace.expertConversations ?? []).find(
        (conversation: ExpertConversation) =>
          conversation.projectExpertId === addedExpert?.id &&
          !conversation.archivedLegacyThread,
      ) ?? null;
    },
    [activeProjectId, projects],
  );

  const handleStreamingChange = useCallback((streaming: boolean) => {
    streamingRef.current = streaming;
  }, []);

  const handleInteractionControlsChange = useCallback(
    (controls: CenterChatInteractionControls | null) => {
      centerChatControlsRef.current = controls;
    },
    [],
  );

  const handleToggleSidebar = useCallback(() => {
    const nextCollapsed = !sidebarCollapsed;
    if (isNarrowViewport() && !nextCollapsed) {
      setRightPanelCollapsed(true);
    }
    setSidebarCollapsed(nextCollapsed);
  }, [sidebarCollapsed]);

  const handleToggleRightPanel = useCallback(() => {
    const nextCollapsed = !rightPanelCollapsed;
    if (isNarrowViewport() && !nextCollapsed) {
      setSidebarCollapsed(true);
    }
    setRightPanelCollapsed(nextCollapsed);
  }, [rightPanelCollapsed]);

  return (
    <div className="app-shell">
      <TopBar
        account={account}
        onLogout={onLogout ? handleLogout : undefined}
        health={health}
        sidebarCollapsed={sidebarCollapsed}
        onToggleSidebar={handleToggleSidebar}
        onOpenSettings={() => setSettingsOpen(true)}
        onOpenProjectCreate={() => setProjectCreateOpen(true)}
        onOpenProjectTools={() => setProjectToolsOpen(true)}
        onOpenProject={handleOpenProject}
        projects={projects.projects}
        activeProjectId={projects.activeProjectId}
        project={projects.activeWorkspace?.project ?? null}
        progress={projectProgress.progress}
      />
      <div className={`app-body ${sidebarCollapsed ? "" : "app-body-sidebar-open"}`}>
        {narrowViewport && (!sidebarCollapsed || !rightPanelCollapsed) && (
          <button
            type="button"
            className="drawer-scrim"
            aria-label="关闭打开的抽屉"
            onClick={() => {
              setSidebarCollapsed(true);
              setRightPanelCollapsed(true);
            }}
          />
        )}
        {!sidebarCollapsed && (
          <LeftSidebar
            workspace={projects.activeWorkspace}
            projects={projects.projects}
            archivedProjects={projects.archivedProjects}
            activeProjectId={projects.activeProjectId}
            error={projects.error}
            onOpenProjectCreate={() => setProjectCreateOpen(true)}
            onOpenProject={handleOpenProject}
            onArchiveProject={projects.archive}
            onRestoreProject={projects.restore}
            onPermanentDeleteProject={projects.permanentDelete}
            onDismissError={projects.dismissError}
            onRetryLoad={projects.refreshList}
            onCloseDrawer={() => setSidebarCollapsed(true)}
          />
        )}
        <CenterChat
          config={llmSettings.config}
          workspace={projects.activeWorkspace}
          selectedExpertId={selectedExpertId}
          models={activeProviderModels}
          professionalMode={professionalMode}
          draftSaving={projects.draftSaving}
          draftSaveError={projects.draftSaveError}
          onOpenSettings={() => setSettingsOpen(true)}
          onOpenArtifact={(artifactId, versionId) => {
            void handleOpenArtifactById(artifactId, versionId);
          }}
          onOpenHardwareSelection={() => setProjectHardwarePickerOpen(true)}
          onSaveDraft={projects.saveDraft}
          onSelectExpert={handleSelectExpert}
          onAddExpert={handleAddProjectExpert}
          onSelectModel={projects.setModel}
          onReloadProject={async (projectId) => {
            await projects.loadWorkspace(projectId);
            await projects.refreshList();
            setArtifactRefreshRevision((current) => current + 1);
            setConfirmationRefreshRevision((current) => current + 1);
          }}
          onDismissPendingItem={async (pendingItemId) => {
            const projectId = projects.activeWorkspace?.project.id;
            if (!projectId) return null;
            return projects.dismissPending(projectId, pendingItemId);
          }}
          confirmationRefreshRevision={confirmationRefreshRevision}
          engineeringState={engineeringState}
          onStreamingChange={handleStreamingChange}
          onInteractionControlsChange={handleInteractionControlsChange}
        />
        <RightPanel
          activeTab={activeTab}
          professionalMode={professionalMode}
          collapsed={rightPanelCollapsed}
          onToggleCollapsed={handleToggleRightPanel}
          onTabChange={setActiveTab}
          onOpenFloating={handleOpenFloating}
          onOpenArtifact={(artifactId, versionId) => {
            void handleOpenArtifactById(artifactId, versionId);
          }}
          artifactRefreshRevision={artifactRefreshRevision}
          confirmationRefreshRevision={confirmationRefreshRevision}
          onConfirmationChanged={handleConfirmationChanged}
          engineeringState={engineeringState}
          workspace={projects.activeWorkspace}
          progress={projectProgress.progress}
          progressLoading={projectProgress.loading}
          progressError={projectProgress.error}
        />
      </div>
      <div className="floating-layer" aria-label="浮窗层">
        {floatingWindows.map((entry) => (
          <FloatingWindow
            key={entry.spec.id}
            spec={entry.spec}
            artifact={entry.artifact}
            hardwareComponentId={entry.hardwareComponentId}
            hardwareSkillName={entry.hardwareSkillName}
            agentExpertType={entry.agentExpertType}
            mechanicalProfile={entry.mechanicalProfile}
            active={
              entry.spec.zIndex ===
              Math.max(...floatingWindows.map((item) => item.spec.zIndex ?? 0))
            }
            onFocus={handleFocusFloating}
            onClose={handleCloseFloating}
            onMinimize={handleMinimizeFloating}
            onToggleMaximize={handleToggleMaximizeFloating}
            onDirtyChange={handleFloatingDirtyChange}
            onCodeRunChanged={handleCodeRunChanged}
          />
        ))}
      </div>
      {settingsOpen && (
        <SettingsDialog
          config={llmSettings.config}
          models={llmSettings.models}
          saving={llmSettings.saving}
          testing={llmSettings.testing}
          message={llmSettings.message}
          error={llmSettings.error}
          professionalMode={professionalMode}
          onProfessionalModeChange={handleProfessionalModeChange}
          onSave={llmSettings.save}
          onClearKey={llmSettings.clearKey}
          onTest={llmSettings.test}
          onOpenHardwareSkill={handleOpenHardwareSkill}
          onOpenMechanicalProfilePreview={handleOpenMechanicalProfilePreview}
          onOpenAgentPackage={handleOpenAgentPackage}
          onClose={() => setSettingsOpen(false)}
        />
      )}
      <ProjectCreationDialog
        open={projectCreateOpen}
        professionalMode={professionalMode}
        onCreateProject={handleCreateProject}
        onClose={() => setProjectCreateOpen(false)}
      />
      <HardwareSelectionDialog
        open={projectHardwarePickerOpen && Boolean(projects.activeWorkspace)}
        title="添加项目电子器件"
        description="选择后会更新当前项目硬件，三师下一轮规划将读取最新结果。"
        initialSelectedIds={selectedProjectHardwareIds(
          projects.activeWorkspace?.sharedContext?.confirmedFacts,
        )}
        confirmLabel="添加到项目"
        onConfirm={async (selectedHardwareIds) => {
          const projectId = projects.activeWorkspace?.project.id;
          if (!projectId) throw new Error("请先打开一个项目。");
          const response = await projects.setHardware(projectId, selectedHardwareIds);
          return { warnings: response.selectedHardwareWarnings };
        }}
        onClose={() => setProjectHardwarePickerOpen(false)}
      />
      <ProjectToolsDialog
        open={projectToolsOpen}
        workspace={projects.activeWorkspace}
        onRenameProject={projects.rename}
        onArchiveProject={projects.archive}
        onDuplicateProject={projects.duplicate}
        onExportProjectPackage={projects.exportPackage}
        onImportProjectPackage={projects.importPackage}
        professionalMode={professionalMode}
        onOpenHardwareSkill={handleOpenHardwareSkill}
        onManageProjectHardware={() => {
          setProjectToolsOpen(false);
          setProjectHardwarePickerOpen(true);
        }}
        onClose={() => setProjectToolsOpen(false)}
      />
      <ConfirmDialog
        open={switchTarget !== null}
        title="切换项目"
        message={
          switchDiscardsDraft
            ? "草稿保存失败。切换项目将放弃尚未保存的内容，确定切换？"
            : "当前正在生成回复，切换项目会先停止生成并保存草稿。确定切换？"
        }
        confirmLabel="切换"
        onConfirm={async () => {
          const target = switchTarget;
          setSwitchTarget(null);
          const discardDraft = switchDiscardsDraft;
          setSwitchDiscardsDraft(false);
          if (!target) return;
          if (streamingRef.current) {
            await centerChatControlsRef.current?.stopStreaming();
          }
          if (!discardDraft) {
            try {
              await centerChatControlsRef.current?.flushDraft();
            } catch {
              setSwitchTarget(target);
              setSwitchDiscardsDraft(true);
              return;
            }
          }
          await projects.open(target);
        }}
        onCancel={() => {
          setSwitchTarget(null);
          setSwitchDiscardsDraft(false);
        }}
      />
    </div>
  );
}

function isNarrowViewport(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(max-width: 720px)").matches
  );
}

function artifactToWindowSpec(
  artifact: ArtifactDefinition,
  version: ArtifactVersion
): FloatingWindowSpec {
  const codeWindow = version.preview.kind === ArtifactPreviewKind.CODE;
  return {
    id: `window_${artifact.id}_${version.id}`,
    kind: previewToWindowKind(version.preview.kind),
    title: `${artifact.title} v${version.version}`,
    artifactId: artifact.id,
    versionId: version.id,
    singletonKey: `${artifact.id}:${version.id}`,
    initialBounds: codeWindow
      ? { x: 48, y: 60, width: 920, height: 640 }
      : { x: 80, y: 72, width: 640, height: 520 },
  };
}

function previewToWindowKind(kind: ArtifactPreviewKind): FloatingWindowKind {
  if (kind === ArtifactPreviewKind.CODE) return FloatingWindowKind.CODE;
  if (kind === ArtifactPreviewKind.IMAGE) return FloatingWindowKind.IMAGE;
  if (kind === ArtifactPreviewKind.MODEL_3D) return FloatingWindowKind.MODEL_3D;
  return FloatingWindowKind.DOCUMENT;
}
