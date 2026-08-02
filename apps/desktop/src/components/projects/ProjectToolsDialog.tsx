import { useEffect, useState } from "react";
import type {
  HardwareSkillSummary,
  ImportProjectPackageResponse,
  ProjectPackageRecord,
  ProjectWorkspace,
} from "@zhangwen/contracts";
import { HardwareLibrary } from "../hardware/HardwareLibrary";
import { ConfirmDialog } from "../shared/ConfirmDialog";
import { useDialogFocusTrap } from "../../hooks/useDialogFocusTrap";

const PROJECT_NAME_MAX = 50;

interface ProjectToolsDialogProps {
  open: boolean;
  workspace: ProjectWorkspace | null;
  onRenameProject: (projectId: string, name: string) => Promise<unknown>;
  onArchiveProject: (projectId: string) => Promise<unknown>;
  onDuplicateProject: (projectId: string, name?: string) => Promise<ProjectWorkspace>;
  onExportProjectPackage: (projectId: string) => Promise<ProjectPackageRecord>;
  onImportProjectPackage: (
    zipBase64: string
  ) => Promise<ImportProjectPackageResponse>;
  professionalMode: boolean;
  onOpenHardwareSkill: (skill: HardwareSkillSummary) => void;
  onManageProjectHardware: () => void;
  onClose: () => void;
}

export function ProjectToolsDialog({
  open,
  workspace,
  onRenameProject,
  onArchiveProject,
  onDuplicateProject,
  onExportProjectPackage,
  onImportProjectPackage,
  professionalMode,
  onOpenHardwareSkill,
  onManageProjectHardware,
  onClose,
}: ProjectToolsDialogProps) {
  const [projectName, setProjectName] = useState("");
  const [renaming, setRenaming] = useState(false);
  const [archiveOpen, setArchiveOpen] = useState(false);
  const [duplicating, setDuplicating] = useState(false);
  const [packageZipBase64, setPackageZipBase64] = useState("");
  const [packageMessage, setPackageMessage] = useState<string | null>(null);
  const [packageError, setPackageError] = useState<string | null>(null);
  const [exportingPackage, setExportingPackage] = useState(false);
  const [importingPackage, setImportingPackage] = useState(false);
  const dialogRef = useDialogFocusTrap<HTMLDivElement>(open && !archiveOpen, onClose);

  useEffect(() => {
    if (open) {
      setProjectName(workspace?.project.name ?? "");
      setPackageMessage(null);
      setPackageError(null);
    }
  }, [open, workspace?.project.id, workspace?.project.name]);

  if (!open) return null;

  const projectId = workspace?.project.id ?? null;
  const handleRename = () => {
    const name = projectName.trim();
    if (!projectId || !name || name.length > PROJECT_NAME_MAX) return;
    setRenaming(true);
    void onRenameProject(projectId, name).finally(() => setRenaming(false));
  };
  const handleExport = () => {
    if (!projectId) return;
    setPackageMessage(null);
    setPackageError(null);
    setExportingPackage(true);
    void onExportProjectPackage(projectId)
      .then((projectPackage) => {
        if (projectPackage.zipBase64) {
          setPackageZipBase64(projectPackage.zipBase64);
        }
        setPackageMessage(`已导出 ${projectPackage.fileName}`);
      })
      .catch((error: unknown) => {
        setPackageError(
          error instanceof Error
            ? error.message
            : "项目包导出失败，请稍后重试。"
        );
      })
      .finally(() => setExportingPackage(false));
  };
  const handleImport = () => {
    const payload = packageZipBase64.trim();
    if (!payload) return;
    setPackageMessage(null);
    setPackageError(null);
    setImportingPackage(true);
    void onImportProjectPackage(payload)
      .then((response) => {
        setPackageMessage(`已导入 ${response.workspace.project.name}`);
      })
      .catch((error: unknown) => {
        setPackageError(
          error instanceof Error
            ? error.message
            : "项目包导入失败，请检查内容。"
        );
      })
      .finally(() => setImportingPackage(false));
  };

  return (
    <>
      <div className="settings-overlay project-dialog-overlay">
        <div
          className="project-dialog project-tools-dialog"
          ref={dialogRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby="project-tools-title"
          tabIndex={-1}
        >
          <div className="settings-header">
            <h2 id="project-tools-title">项目工具</h2>
            <button
              type="button"
              className="floating-close"
              aria-label="关闭项目工具"
              onClick={onClose}
            >
              ✕
            </button>
          </div>
          <div className="project-tools-body">
            <section className="project-tools-section" aria-label="项目管理">
              <h3>项目管理</h3>
              {workspace ? (
                <>
                  <label className="project-dialog-field">
                    <span>项目名称</span>
                    <input
                      aria-label="项目工具中的项目名称"
                      value={projectName}
                      maxLength={PROJECT_NAME_MAX}
                      onChange={(event) => setProjectName(event.target.value)}
                    />
                  </label>
                  <div className="project-tools-actions">
                    <button
                      type="button"
                      disabled={duplicating}
                      onClick={() => {
                        if (!projectId) return;
                        setDuplicating(true);
                        void onDuplicateProject(projectId)
                          .then(onClose)
                          .finally(() => setDuplicating(false));
                      }}
                    >
                      {duplicating ? "复制中..." : "复制项目"}
                    </button>
                    <button
                      type="button"
                      disabled={
                        renaming ||
                        !projectName.trim() ||
                        projectName.trim() === workspace.project.name
                      }
                      onClick={handleRename}
                    >
                      {renaming ? "重命名中..." : "重命名项目"}
                    </button>
                    <button
                      type="button"
                      className="danger-action"
                      onClick={() => setArchiveOpen(true)}
                    >
                      归档项目
                    </button>
                  </div>
                </>
              ) : (
                <p className="tab-description">请先选择一个项目。</p>
              )}
            </section>

            <section className="project-tools-section" aria-label="项目包">
              <h3>项目包</h3>
              <button
                type="button"
                onClick={handleExport}
                disabled={!projectId || exportingPackage}
              >
                {exportingPackage ? "导出中..." : "导出当前项目包"}
              </button>
              <textarea
                aria-label="项目包 Base64"
                placeholder="粘贴项目包 Base64 ZIP"
                value={packageZipBase64}
                onChange={(event) => setPackageZipBase64(event.target.value)}
                rows={4}
              />
              <button
                type="button"
                onClick={handleImport}
                disabled={!packageZipBase64.trim() || importingPackage}
              >
                {importingPackage ? "导入中..." : "导入项目包"}
              </button>
              {packageMessage && (
                <p className="project-package-message" role="status">
                  {packageMessage}
                </p>
              )}
              {packageError && (
                <p className="project-create-error" role="alert">
                  {packageError}
                </p>
              )}
            </section>

            <section className="project-tools-section project-tools-hardware" aria-label="硬件库">
              <div className="project-tools-project-hardware">
                <div>
                  <h3>项目硬件</h3>
                  <p>管理三师规划时优先使用的电子器件；公共硬件知识库不会因此改变。</p>
                </div>
                <button
                  type="button"
                  className="primary-action"
                  disabled={!projectId}
                  onClick={onManageProjectHardware}
                >
                  管理项目硬件
                </button>
              </div>
              <HardwareLibrary
                professionalMode={professionalMode}
                onOpenSkillProject={onOpenHardwareSkill}
              />
            </section>
          </div>
        </div>
      </div>
      <ConfirmDialog
        open={archiveOpen}
        title="归档项目"
        message={
          workspace
            ? `确定归档项目“${workspace.project.name}”？归档后不再显示在项目列表中。`
            : ""
        }
        confirmLabel="归档"
        onConfirm={() => {
          if (!projectId) return;
          setArchiveOpen(false);
          void onArchiveProject(projectId).then(onClose);
        }}
        onCancel={() => setArchiveOpen(false)}
      />
    </>
  );
}
