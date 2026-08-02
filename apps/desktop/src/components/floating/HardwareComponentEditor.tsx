import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import type {
  HardwareComponentPackageDetail,
  HardwareComponentPackageFile,
} from "@zhangwen/contracts";
import {
  getHardwareComponentPackage,
  updateHardwareComponentPackageFile,
} from "../../services/hardwareApi";
import { ApiError } from "../../services/api";

const MonacoCodeEditor = lazy(() => import("./MonacoCodeEditor"));

interface HardwareComponentEditorProps {
  componentId: string;
  onDirtyChange?: (dirty: boolean) => void;
}

export function HardwareComponentEditor({
  componentId,
  onDirtyChange,
}: HardwareComponentEditorProps) {
  const [detail, setDetail] = useState<HardwareComponentPackageDetail | null>(null);
  const [selectedPath, setSelectedPath] = useState("README.md");
  const [draft, setDraft] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [feedback, setFeedback] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [conflictRefreshNeeded, setConflictRefreshNeeded] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    setFeedback(null);
    setConflictRefreshNeeded(false);
    try {
      const response = await getHardwareComponentPackage(componentId);
      const entry =
        response.package.files.find((file) => file.path === "README.md") ??
        response.package.files[0] ??
        null;
      setDetail(response.package);
      setSelectedPath(entry?.path ?? "README.md");
      setDraft(entry?.content ?? "");
    } catch (loadError) {
      setError(
        loadError instanceof Error
          ? loadError.message
          : "无法读取器件项目，请确认本地服务已启动。",
      );
    } finally {
      setLoading(false);
    }
  }, [componentId]);

  useEffect(() => {
    void load();
  }, [load]);

  const selectedFile =
    detail?.files.find((file) => file.path === selectedPath) ?? null;
  const dirty = Boolean(selectedFile && draft !== selectedFile.content);
  const tree = useMemo(() => buildFileTree(detail?.files ?? []), [detail?.files]);

  useEffect(() => {
    onDirtyChange?.(dirty);
  }, [dirty, onDirtyChange]);

  useEffect(
    () => () => {
      onDirtyChange?.(false);
    },
    [onDirtyChange],
  );

  const selectFile = (file: HardwareComponentPackageFile) => {
    if (dirty || saving) return;
    setSelectedPath(file.path);
    setDraft(file.content);
    setFeedback(null);
    setError(null);
  };

  const save = async () => {
    if (!detail || !selectedFile || !dirty || saving) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const response = await updateHardwareComponentPackageFile(componentId, {
        path: selectedFile.path,
        content: draft,
        expectedRevision: detail.revision,
      });
      const nextFile =
        response.package.files.find((file) => file.path === selectedFile.path) ??
        response.package.files[0] ??
        null;
      setDetail(response.package);
      setSelectedPath(nextFile?.path ?? "README.md");
      setDraft(nextFile?.content ?? "");
      setConflictRefreshNeeded(false);
      setFeedback(`已保存 ${selectedFile.path}；三位工程师下一次相关回复会读取新内容。`);
    } catch (saveError) {
      if (saveError instanceof ApiError && saveError.status === 409) {
        try {
          const latest = await getHardwareComponentPackage(componentId);
          setDetail(latest.package);
          setConflictRefreshNeeded(false);
          setError("器件项目已有新版本，已加载最新 revision；当前 Markdown 草稿仍保留，检查后可再次保存。");
        } catch {
          setConflictRefreshNeeded(true);
          setError("器件项目已有新版本，当前 Markdown 草稿仍保留；请保持浮窗打开并重试读取最新版本。");
        }
      } else {
        setError(
          saveError instanceof Error
            ? `${saveError.message} 当前草稿已保留。`
            : "保存失败，当前草稿已保留。",
        );
      }
    } finally {
      setSaving(false);
    }
  };

  const refreshConflictRevision = async () => {
    if (saving) return;
    setSaving(true);
    setError(null);
    setFeedback(null);
    try {
      const latest = await getHardwareComponentPackage(componentId);
      setDetail(latest.package);
      setConflictRefreshNeeded(false);
      setFeedback("已读取器件项目最新 revision，当前 Markdown 草稿仍保留；检查后可再次保存。");
    } catch (refreshError) {
      setConflictRefreshNeeded(true);
      setError(
        refreshError instanceof Error
          ? `${refreshError.message} 当前 Markdown 草稿仍保留。`
          : "最新 revision 读取失败，当前 Markdown 草稿仍保留。",
      );
    } finally {
      setSaving(false);
    }
  };

  if (loading && !detail) {
    return <p className="hardware-project-state" role="status">正在读取器件项目...</p>;
  }

  if (!detail) {
    return (
      <div className="hardware-project-state">
        <p role="alert">{error ?? "器件项目不可用。"}</p>
        <button type="button" onClick={() => void load()}>重新加载</button>
      </div>
    );
  }

  return (
    <section className="hardware-project-editor" aria-label={`${detail.componentName} 器件项目编辑器`}>
      <aside className="hardware-project-tree" aria-label="器件项目文件夹架构">
        <header>
          <span>器件项目</span>
          <strong>{detail.componentName}</strong>
          <small title={detail.revision}>版本 {detail.revision.slice(0, 8)}</small>
        </header>
        {tree.root.map((file) => (
          <FileButton
            key={file.path}
            file={file}
            selected={selectedPath === file.path}
            disabled={(dirty && selectedPath !== file.path) || saving}
            onSelect={selectFile}
          />
        ))}
        {tree.folders.map((folder) => (
          <div key={folder.name} className="hardware-project-folder">
            <div className="hardware-project-folder-name" aria-label={`文件夹 ${folder.name}`}>
              <span aria-hidden="true">▾</span>
              <strong>{folder.name}</strong>
            </div>
            {folder.files.map((file) => (
              <FileButton
                key={file.path}
                file={file}
                selected={selectedPath === file.path}
                disabled={(dirty && selectedPath !== file.path) || saving}
                onSelect={selectFile}
              />
            ))}
          </div>
        ))}
      </aside>

      <div className="hardware-project-main">
        <header className="hardware-project-toolbar">
          <div>
            <strong>{selectedFile?.path ?? "说明文档"}</strong>
            <span>{dirty ? "有未保存修改" : selectedFile?.overridden ? "用户自定义" : "结构化字段生成"}</span>
          </div>
          <span>{draft.length.toLocaleString()} / 40,000</span>
        </header>
        <div className="hardware-project-editor-surface">
          {selectedFile ? (
            <Suspense fallback={<p className="hardware-project-state" role="status">正在加载 Markdown 编辑器...</p>}>
              <MonacoCodeEditor
                projectId="hardware-library"
                codeRunId={`${componentId}:${detail.revision}`}
                filePath={selectedFile.path}
                 value={draft}
                 readOnly={saving}
                 onChange={(value) => {
                  setDraft(value);
                  setFeedback(null);
                  setError(null);
                }}
              />
            </Suspense>
          ) : (
            <p className="hardware-project-state">没有可编辑的 Markdown 文件。</p>
          )}
        </div>
        <footer className="hardware-project-actions">
          <p role="note">只有保存后的 Markdown 会进入公共知识；电气参数仍由组件规则字段控制。</p>
          <div>
            <button
              type="button"
              disabled={!dirty || saving}
              onClick={() => {
                setDraft(selectedFile?.content ?? "");
                setError(null);
                setFeedback(null);
              }}
            >
              放弃修改
            </button>
            <button
              type="button"
              className="primary-action"
              disabled={!dirty || saving}
              onClick={() => void save()}
            >
              {saving ? "保存中..." : "保存文档"}
            </button>
          </div>
        </footer>
        {feedback && <p className="hardware-project-feedback" role="status">{feedback}</p>}
        {error && (
          <div className="hardware-project-feedback is-error" role="alert">
            <span>{error}</span>
            {conflictRefreshNeeded && (
              <button
                type="button"
                disabled={saving}
                onClick={() => void refreshConflictRevision()}
              >
                {saving ? "读取中..." : "重试读取最新版本"}
              </button>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

function FileButton({
  file,
  selected,
  disabled,
  onSelect,
}: {
  file: HardwareComponentPackageFile;
  selected: boolean;
  disabled: boolean;
  onSelect: (file: HardwareComponentPackageFile) => void;
}) {
  return (
    <button
      type="button"
      className={`hardware-project-file ${selected ? "is-selected" : ""}`}
      aria-pressed={selected}
      disabled={disabled}
      onClick={() => onSelect(file)}
    >
      <span aria-hidden="true">◇</span>
      <span><strong>{file.title}</strong><small>{file.path}</small></span>
      {file.overridden && <i>已改</i>}
    </button>
  );
}

function buildFileTree(files: HardwareComponentPackageFile[]): {
  root: HardwareComponentPackageFile[];
  folders: Array<{ name: string; files: HardwareComponentPackageFile[] }>;
} {
  const root: HardwareComponentPackageFile[] = [];
  const folders = new Map<string, HardwareComponentPackageFile[]>();
  for (const file of files) {
    const [first, ...rest] = file.path.split("/");
    if (rest.length === 0 || !first) {
      root.push(file);
      continue;
    }
    const current = folders.get(first) ?? [];
    current.push(file);
    folders.set(first, current);
  }
  return {
    root,
    folders: Array.from(folders, ([name, folderFiles]) => ({
      name,
      files: folderFiles,
    })),
  };
}
