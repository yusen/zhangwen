import { useEffect, useState } from "react";
import { WorkTab } from "../right-panel/WorkTab";
import { ArtifactsTab } from "../right-panel/ArtifactsTab";
import { DevicesTab } from "../right-panel/DevicesTab";
import type { RightTab } from "./AppShell";
import type { ProjectEngineeringState } from "../../hooks/useProjectEngineeringState";
import type {
  ArtifactDefinition,
  FloatingWindowSpec,
  ProjectWorkspace,
  ProjectProgressSnapshot,
} from "@zhangwen/contracts";
import { zhCN } from "../../i18n/zh-CN";

interface RightPanelProps {
  activeTab: RightTab;
  professionalMode: boolean;
  collapsed: boolean;
  onToggleCollapsed: () => void;
  onTabChange: (tab: RightTab) => void;
  onOpenFloating: (spec: FloatingWindowSpec, artifact?: ArtifactDefinition) => void;
  onOpenArtifact: (artifactId?: string | null, versionId?: string | null) => void;
  artifactRefreshRevision: number;
  confirmationRefreshRevision: number;
  onConfirmationChanged: () => void;
  engineeringState: ProjectEngineeringState;
  workspace: ProjectWorkspace | null;
  progress?: ProjectProgressSnapshot | null;
  progressLoading?: boolean;
  progressError?: string | null;
}

const TABS: { key: RightTab; label: string; icon: "list" | "folder" | "usb" }[] = [
  { key: "work", label: zhCN.rightPanelTabs.work, icon: "list" },
  { key: "artifacts", label: zhCN.rightPanelTabs.artifacts, icon: "folder" },
  { key: "devices", label: zhCN.rightPanelTabs.devices, icon: "usb" },
];

export function RightPanel({
  activeTab,
  professionalMode,
  collapsed,
  onToggleCollapsed,
  onTabChange,
  onOpenFloating,
  onOpenArtifact,
  artifactRefreshRevision,
  confirmationRefreshRevision,
  onConfirmationChanged,
  engineeringState,
  workspace,
  progress,
  progressLoading,
  progressError,
}: RightPanelProps) {
  const [visitedTabs, setVisitedTabs] = useState<RightTab[]>([activeTab]);

  useEffect(() => {
    setVisitedTabs((current) =>
      current.includes(activeTab) ? current : [...current, activeTab],
    );
  }, [activeTab]);

  return (
    <aside
      className={`right-panel ${collapsed ? "right-panel-collapsed" : ""}`}
      data-testid="right-panel"
    >
      {collapsed && (
        <button
          type="button"
          className="right-panel-toggle right-panel-toggle-expand"
          aria-label="展开右栏"
          onClick={onToggleCollapsed}
        >
          ‹
        </button>
      )}
      <div className="right-panel-shell" hidden={collapsed}>
          <div className="right-panel-header">
            <div className="right-panel-tabs" role="tablist">
              {TABS.map((tab) => (
                <button
                  key={tab.key}
                  id={`right-tab-${tab.key}`}
                  role="tab"
                  aria-selected={activeTab === tab.key}
                  aria-controls={`right-tabpanel-${tab.key}`}
                  tabIndex={activeTab === tab.key ? 0 : -1}
                  className={`tab-btn ${
                    activeTab === tab.key ? "tab-btn-active" : ""
                  }`}
                  onClick={() => onTabChange(tab.key)}
                >
                  <RightPanelTabIcon icon={tab.icon} />
                  <span>{tab.label}</span>
                </button>
              ))}
            </div>
            <button
              type="button"
              className="right-panel-toggle"
              aria-label="收起右栏"
              onClick={onToggleCollapsed}
            >
              ›
            </button>
          </div>
          <div className="right-panel-content">
            {visitedTabs.includes("work") && (
              <div
                id="right-tabpanel-work"
                role="tabpanel"
                aria-labelledby="right-tab-work"
                hidden={activeTab !== "work"}
                className="right-panel-tabpane"
              >
                <WorkTab
                  workspace={workspace}
                  professionalMode={professionalMode}
                  refreshRevision={confirmationRefreshRevision}
                  onConfirmationChanged={onConfirmationChanged}
                  onOpenArtifact={onOpenArtifact}
                  engineeringState={engineeringState}
                  progress={progress}
                  progressLoading={progressLoading}
                  progressError={progressError}
                />
              </div>
            )}
            {visitedTabs.includes("artifacts") && (
              <div
                id="right-tabpanel-artifacts"
                role="tabpanel"
                aria-labelledby="right-tab-artifacts"
                hidden={activeTab !== "artifacts"}
                className="right-panel-tabpane"
              >
                <ArtifactsTab
                  workspace={workspace}
                  professionalMode={professionalMode}
                  onOpenFloating={onOpenFloating}
                  refreshRevision={artifactRefreshRevision}
                />
              </div>
            )}
            {visitedTabs.includes("devices") && (
              <div
                id="right-tabpanel-devices"
                role="tabpanel"
                aria-labelledby="right-tab-devices"
                hidden={activeTab !== "devices"}
                className="right-panel-tabpane"
              >
                <DevicesTab
                  workspace={workspace}
                  professionalMode={professionalMode}
                  refreshRevision={artifactRefreshRevision}
                />
              </div>
            )}
          </div>
      </div>
    </aside>
  );
}

function RightPanelTabIcon({ icon }: { icon: "list" | "folder" | "usb" }) {
  if (icon === "folder") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M3 6.5h6l2 2h10v9.5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
      </svg>
    );
  }
  if (icon === "usb") {
    return (
      <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M12 3v13m0-13-2.5 2.5M12 3l2.5 2.5M7 10v3a3 3 0 0 0 3 3h5m0 0-2-2m2 2-2 2" />
        <circle cx="7" cy="8" r="1.5" />
        <rect x="15" y="14.5" width="3" height="3" rx=".5" />
      </svg>
    );
  }
  return (
    <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M9 6h11M9 12h11M9 18h11" />
      <path d="m3.5 6 1 1 2-2M3.5 12l1 1 2-2M3.5 18l1 1 2-2" />
    </svg>
  );
}
