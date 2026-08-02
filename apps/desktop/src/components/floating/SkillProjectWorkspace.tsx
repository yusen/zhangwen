import { useEffect, useMemo, useRef, useState } from "react";
import MonacoCodeEditor from "./MonacoCodeEditor";

export interface SkillProjectFile {
  path: string;
  title: string;
  kind: string;
  content: string;
  editable: boolean;
  overridden?: boolean;
}

interface SkillProjectDiagnostic {
  path: string;
  message: string;
  severity: "warning" | "error";
}

interface SkillProjectWorkspaceProps {
  ariaLabel: string;
  projectKey: string;
  revision: string;
  files: SkillProjectFile[];
  manifestItems: Array<{ label: string; value: string }>;
  diagnostics?: SkillProjectDiagnostic[];
  saving?: boolean;
  onSave: (updates: Array<{ path: string; content: string }>) => Promise<string>;
  onReset?: (path: string) => Promise<string>;
  onDirtyChange?: (dirty: boolean) => void;
}

export function SkillProjectWorkspace({
  ariaLabel,
  projectKey,
  revision,
  files,
  manifestItems,
  diagnostics = [],
  saving = false,
  onSave,
  onReset,
  onDirtyChange,
}: SkillProjectWorkspaceProps) {
  const [selectedPath, setSelectedPath] = useState(files[0]?.path ?? "SKILL.md");
  const [drafts, setDrafts] = useState<Record<string, string>>(() => fileContents(files));
  const [localSaving, setLocalSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const previousFilesRef = useRef<Record<string, string>>(fileContents(files));

  useEffect(() => {
    const previousFiles = previousFilesRef.current;
    const nextFiles = fileContents(files);
    setDrafts((current) => {
      const next: Record<string, string> = {};
      for (const file of files) {
        const currentDraft = current[file.path];
        const previousBase = previousFiles[file.path];
        next[file.path] =
          currentDraft !== undefined && currentDraft !== previousBase
            ? currentDraft
            : file.content;
      }
      return next;
    });
    previousFilesRef.current = nextFiles;
    setSelectedPath((current) =>
      files.some((file) => file.path === current) ? current : files[0]?.path ?? "SKILL.md",
    );
  }, [files, revision]);

  const dirtyPaths = useMemo(
    () => files
      .filter((file) => (drafts[file.path] ?? file.content) !== file.content)
      .map((file) => file.path),
    [drafts, files],
  );
  const dirty = dirtyPaths.length > 0;
  const busy = saving || localSaving;

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  const selectedFile = files.find((file) => file.path === selectedPath) ?? files[0] ?? null;
  const groups = useMemo(() => groupFiles(files), [files]);

  const saveAll = async () => {
    if (!dirty || busy) return;
    setLocalSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const message = await onSave(
        dirtyPaths.map((path) => ({ path, content: drafts[path] ?? "" })),
      );
      setFeedback(message);
    } catch (saveError) {
      setError(saveError instanceof Error ? saveError.message : "保存失败，请重试。");
    } finally {
      setLocalSaving(false);
    }
  };

  const resetSelected = async () => {
    if (!selectedFile?.overridden || !onReset || dirty || busy) return;
    if (!window.confirm(`确定把“${selectedFile.path}”恢复为内置默认内容？`)) return;
    setLocalSaving(true);
    setError(null);
    setFeedback(null);
    try {
      setFeedback(await onReset(selectedFile.path));
    } catch (resetError) {
      setError(resetError instanceof Error ? resetError.message : "恢复默认失败，请重试。");
    } finally {
      setLocalSaving(false);
    }
  };

  return (
    <section className="skill-project-editor" role="region" aria-label={ariaLabel}>
      <header className="skill-project-summary">
        <div>
          <strong>manifest.json（系统只读）</strong>
          <span>身份、权限和工具边界不允许通过 Markdown 修改。</span>
        </div>
        <dl>
          {manifestItems.map((item) => (
            <div key={item.label}>
              <dt>{item.label}</dt>
              <dd title={item.value}>{item.value}</dd>
            </div>
          ))}
          <div>
            <dt>内容版本</dt>
            <dd title={revision}>{revision.slice(0, 12)}</dd>
          </div>
        </dl>
      </header>

      {diagnostics.map((issue) => (
        <p
          key={`${issue.path}:${issue.message}`}
          className={`skill-project-diagnostic is-${issue.severity}`}
          role={issue.severity === "error" ? "alert" : "status"}
        >
          {issue.path}：{issue.message}
        </p>
      ))}

      <div className="skill-project-workspace">
        <nav className="skill-project-tree" aria-label="Skill 项目文件夹">
          {groups.map((group) => (
            <div key={group.folder} className="skill-project-tree-group">
              <strong>{group.folder}</strong>
              {group.files.map((file) => {
                const fileDirty = (drafts[file.path] ?? file.content) !== file.content;
                return (
                  <button
                    key={file.path}
                    type="button"
                    className={selectedFile?.path === file.path ? "is-selected" : ""}
                    onClick={() => {
                      setSelectedPath(file.path);
                      setFeedback(null);
                    }}
                    disabled={busy}
                    aria-label={`${file.title} ${file.path}`}
                  >
                    <span>{fileKindBadge(file)}</span>
                    <span>
                      <strong>{file.title}</strong>
                      <small>{file.path.split("/").at(-1)}</small>
                    </span>
                    {fileDirty ? <i>未存</i> : file.overridden ? <i>已改</i> : null}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>

        <div className="skill-project-file">
          <div className="skill-project-filebar">
            <div>
              <strong>{selectedFile?.path ?? "未选择文件"}</strong>
              <span>
                {selectedFile?.editable === false
                  ? "只读"
                  : dirtyPaths.includes(selectedFile?.path ?? "")
                    ? "有未保存修改"
                    : "已同步"}
              </span>
            </div>
            <span>{(drafts[selectedFile?.path ?? ""] ?? "").length.toLocaleString()} 字符</span>
          </div>
          {selectedFile ? (
            <MonacoCodeEditor
              projectId="skill-project"
              codeRunId={projectKey}
              filePath={selectedFile.path}
              value={drafts[selectedFile.path] ?? selectedFile.content}
              readOnly={!selectedFile.editable || busy}
              onChange={(content) => {
                setDrafts((current) => ({ ...current, [selectedFile.path]: content }));
                setFeedback(null);
                setError(null);
              }}
            />
          ) : (
            <p className="floating-placeholder">这个项目没有可编辑文件。</p>
          )}
          <footer className="skill-project-actions">
            <span role="status">
              {dirtyPaths.length > 0
                ? `${dirtyPaths.length} 个文件有未保存修改`
                : "全部文件已同步"}
            </span>
            {onReset && (
              <button
                type="button"
                disabled={!selectedFile?.overridden || dirty || busy}
                onClick={() => void resetSelected()}
              >
                恢复内置
              </button>
            )}
            <button
              type="button"
              disabled={!dirty || busy}
              onClick={() => {
                setDrafts(fileContents(files));
                setFeedback(null);
                setError(null);
              }}
            >
              放弃全部
            </button>
            <button type="button" disabled={!dirty || busy} onClick={() => void saveAll()}>
              {busy ? "保存中..." : "保存全部"}
            </button>
          </footer>
          {error && <p className="skill-project-feedback is-error" role="alert">{error}</p>}
          {feedback && <p className="skill-project-feedback is-success" role="status">{feedback}</p>}
        </div>
      </div>
    </section>
  );
}

function fileContents(files: SkillProjectFile[]): Record<string, string> {
  return Object.fromEntries(files.map((file) => [file.path, file.content]));
}

function groupFiles(files: SkillProjectFile[]) {
  const groups = new Map<string, SkillProjectFile[]>();
  for (const file of files) {
    const separator = file.path.lastIndexOf("/");
    const folder = separator < 0 ? "项目根目录" : file.path.slice(0, separator);
    groups.set(folder, [...(groups.get(folder) ?? []), file]);
  }
  return Array.from(groups, ([folder, groupedFiles]) => ({ folder, files: groupedFiles }));
}

function fileKindBadge(file: SkillProjectFile): string {
  if (file.kind === "entry") return "主";
  if (file.kind === "model" || file.path.endsWith(".py")) return "PY";
  if (file.kind === "test") return "测";
  if (file.kind === "example") return "例";
  return "MD";
}
