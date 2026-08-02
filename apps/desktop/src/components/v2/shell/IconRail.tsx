import { ProjectWorkspaceKind } from "@zhangwen/contracts";

export type StudioView = "chat" | "lab" | ProjectWorkspaceKind;

interface IconRailProps {
  view: StudioView;
  onViewChange: (view: StudioView) => void;
  onOpenProjects: () => void;
  onOpenBridge: () => void;
  onOpenSettings: () => void;
  onLogout?: () => void;
  accountName?: string;
  professionalMode: boolean;
}

const ICONS = {
  chat: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8v.5z" />
    </svg>
  ),
  overview: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="9" /><circle cx="12" cy="12" r="3.5" />
    </svg>
  ),
  engineering: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M16 18l6-6-6-6M8 6l-6 6 6 6" />
    </svg>
  ),
  lab: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M9 3v5l-5 9a2 2 0 0 0 1.8 3h12.4a2 2 0 0 0 1.8-3l-5-9V3" />
      <path d="M8 12h8M8 3h8" />
    </svg>
  ),
  structure: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M21 16.5v-9L12 3 3 7.5v9L12 21l9-4.5z" /><path d="M3.3 7.3L12 12l8.7-4.7M12 22V12" />
    </svg>
  ),
  delivery: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M22 2L11 13M22 2l-7 20-4-9-9-4 20-7z" />
    </svg>
  ),
  projects: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" /><path d="M9 22V12h6v10" />
    </svg>
  ),
  bridge: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
    </svg>
  ),
  settings: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
} as const;

const VIEW_ITEMS: Array<{ id: StudioView; label: string; icon: keyof typeof ICONS }> = [
  { id: "chat", label: "对话", icon: "chat" },
  { id: "lab", label: "设备实验室", icon: "lab" },
  { id: ProjectWorkspaceKind.OVERVIEW, label: "概览", icon: "overview" },
  { id: ProjectWorkspaceKind.ENGINEERING, label: "工程", icon: "engineering" },
  { id: ProjectWorkspaceKind.STRUCTURE, label: "结构", icon: "structure" },
  { id: ProjectWorkspaceKind.DELIVERY, label: "交付", icon: "delivery" },
];

export function IconRail({
  view,
  onViewChange,
  onOpenProjects,
  onOpenBridge,
  onOpenSettings,
  onLogout,
  accountName,
  professionalMode,
}: IconRailProps) {
  const visibleViewItems = professionalMode
    ? VIEW_ITEMS
    : VIEW_ITEMS.filter((item) => item.id === "chat" || item.id === "lab");
  return (
    <nav className="zw-rail" aria-label="主导航">
      <button type="button" className="zw-rail-logo" aria-label="掌问首页" onClick={() => onViewChange("chat")}>
        问
      </button>
      {visibleViewItems.map((item) => (
        <button
          key={item.id}
          type="button"
          className="zw-rail-btn"
          aria-label={item.label}
          title={item.label}
          aria-current={view === item.id ? "page" : undefined}
          onClick={() => onViewChange(item.id)}
        >
          {ICONS[item.icon]}
          <span className="zw-rail-label">{item.label}</span>
        </button>
      ))}
      <span className="zw-rail-sep" aria-hidden="true" />
      <button type="button" className="zw-rail-btn" aria-label="项目与版本" title="项目与版本" onClick={onOpenProjects}>
        {ICONS.projects}
        <span className="zw-rail-label">项目</span>
      </button>
      <span className="zw-rail-grow" aria-hidden="true" />
      <button type="button" className="zw-rail-btn" aria-label="网页连接" title="让网页版连接本机" onClick={onOpenBridge}>
        {ICONS.bridge}
        <span className="zw-rail-label">连接</span>
      </button>
      <button type="button" className="zw-rail-btn" aria-label="设置" title="设置" onClick={onOpenSettings}>
        {ICONS.settings}
        <span className="zw-rail-label">设置</span>
      </button>
      {onLogout && (
        <button
          type="button"
          className="zw-rail-avatar"
          aria-label={`退出 ${accountName ?? "账号"}`}
          title={`退出 ${accountName ?? "账号"}`}
          onClick={onLogout}
        >
          <span className="zw-rail-avatar-mark">{(accountName ?? "账").slice(0, 1)}</span>
          <span className="zw-rail-label">账号</span>
        </button>
      )}
    </nav>
  );
}
