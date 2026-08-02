interface StageHeaderProps {
  projectName: string | null;
  versionTag: string | null;
  stageText: string | null;
  professionalMode: boolean;
  onToggleProfessionalMode: () => void;
  inspectorOpen: boolean;
  onToggleInspector: () => void;
}

export function StageHeader({
  projectName,
  versionTag,
  stageText,
  professionalMode,
  onToggleProfessionalMode,
  inspectorOpen,
  onToggleInspector,
}: StageHeaderProps) {
  return (
    <header className="zw-stage-head">
      <div className="zw-stage-proj">
        <strong>{projectName ?? "选择或创建项目"}</strong>
        {versionTag && <span className="zw-ver-tag">{versionTag}</span>}
        {stageText && <span className="zw-stage-pill"><i aria-hidden="true" />{stageText}</span>}
        <span className="zw-stage-tools">
          <button
            type="button"
            className="zw-mode-toggle"
            onClick={onToggleProfessionalMode}
          >
            {professionalMode ? "返回简洁模式" : "专业视图"}
          </button>
          <button
            type="button"
            className="zw-mode-toggle"
            aria-pressed={inspectorOpen}
            onClick={onToggleInspector}
          >
            {inspectorOpen ? "收起侧栏" : "打开侧栏"}
          </button>
        </span>
      </div>
    </header>
  );
}
