import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import {
  CodeRuntime,
  CodeRunStatus,
  CodeValidationKind,
  type CodeRun,
  type CodeValidationCheck,
} from "@zhangwen/contracts";
import { ApiError } from "../../services/api";
import {
  acceptCode,
  getCode,
  reviseCode,
  validateCode,
} from "../../services/projectsApi";

const MonacoCodeEditor = lazy(() => import("./MonacoCodeEditor"));

type CodeArtifactView = "code" | "changes";

interface CodeArtifactEditorProps {
  projectId: string;
  codeRunId: string;
  onCodeRunChanged: (codeRun: CodeRun) => void | Promise<void>;
  readOnly?: boolean;
}

const VIEW_LABELS: { key: CodeArtifactView; label: string }[] = [
  { key: "code", label: "代码" },
  { key: "changes", label: "变更" },
];

const VALIDATION_LABELS: Record<string, string> = {
  [CodeValidationKind.STATIC]: "静态检查",
  [CodeValidationKind.SYNTAX]: "语法检查",
};

const VALIDATABLE_CODE_RUN_STATUSES = new Set<CodeRun["status"]>([
  CodeRunStatus.DRAFT,
  CodeRunStatus.FAILED,
  CodeRunStatus.READY_FOR_REVIEW,
]);

const REQUIRED_VALIDATION_KINDS = [
  CodeValidationKind.STATIC,
  CodeValidationKind.SYNTAX,
] as const;

export function CodeArtifactEditor({
  projectId,
  codeRunId,
  onCodeRunChanged,
  readOnly = false,
}: CodeArtifactEditorProps) {
  const [view, setView] = useState<CodeArtifactView>("code");
  const [codeRun, setCodeRun] = useState<CodeRun | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [selectedPath, setSelectedPath] = useState<string | null>(null);
  const [summary, setSummary] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [validating, setValidating] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    setError(null);
    setStatus(null);
    void getCode(projectId, codeRunId)
      .then((response) => {
        if (canceled) return;
        setCodeRun(response.codeRun);
        setDrafts(codeDrafts(response.codeRun));
        setSelectedPath(response.codeRun.files[0]?.path ?? null);
        setSummary("");
      })
      .catch((reason: unknown) => {
        if (!canceled) {
          setError(reason instanceof Error ? reason.message : "加载代码版本失败。");
        }
      })
      .finally(() => {
        if (!canceled) setLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, [codeRunId, projectId]);

  const dirty = useMemo(
    () =>
      codeRun?.files.some((file) => drafts[file.path] !== file.content) ?? false,
    [codeRun, drafts],
  );
  const selectedFile =
    codeRun?.files.find((file) => file.path === selectedPath) ?? codeRun?.files[0] ?? null;
  const canValidate =
    codeRun !== null && VALIDATABLE_CODE_RUN_STATUSES.has(codeRun.status);
  const actionBusy = saving || validating;
  const runtimeLabel = codeRun?.runtime === CodeRuntime.ESP_CLAW_LUA
    ? "ESP-Claw Lua"
    : "MicroPython";

  const installCodeRun = (next: CodeRun, nextSummary = "") => {
    setCodeRun(next);
    setDrafts(codeDrafts(next));
    setSelectedPath((current) =>
      current && next.files.some((file) => file.path === current)
        ? current
        : next.files[0]?.path ?? null,
    );
    setSummary(nextSummary);
  };

  const discard = () => {
    if (!codeRun) return;
    setDrafts(codeDrafts(codeRun));
    setSummary("");
    setError(null);
    setStatus(null);
  };

  const save = async () => {
    if (!codeRun || !dirty || !summary.trim() || validating) return;
    setSaving(true);
    setError(null);
    setStatus(null);
    try {
      const response = await reviseCode(projectId, codeRun.id, {
        baseCodeRunId: codeRun.id,
        files: codeRun.files.map((file) => ({
          path: file.path,
          content: drafts[file.path] ?? file.content,
        })),
        summary: summary.trim(),
      });
      installCodeRun(response.codeRun, response.codeRun.patch.summary);
      setStatus(`已保存为不可变新版本 v${response.codeRun.version}。`);
      notifyCodeRunChanged(onCodeRunChanged, response.codeRun);
    } catch (reason) {
      if (
        reason instanceof ApiError &&
        (reason.status === 409 || reason.code === "CODE_REVISION_CONFLICT")
      ) {
        setError("代码已有更新版本，当前未保存内容已保留。请查看最新版本后重新应用修改。");
      } else {
        setError(reason instanceof Error ? reason.message : "保存代码新版本失败。");
      }
    } finally {
      setSaving(false);
    }
  };

  const validateAndAccept = async () => {
    if (!codeRun || dirty || !canValidate || saving) return;
    setValidating(true);
    setError(null);
    setStatus(null);
    try {
      const validationResponse = await validateCode(projectId, {
        codeRunId: codeRun.id,
      });
      installCodeRun(validationResponse.codeRun, summary);
      notifyCodeRunChanged(onCodeRunChanged, validationResponse.codeRun);
      if (!requiredValidationPassed(validationResponse.codeRun)) {
        setStatus("本地验证未通过，代码未接受。请根据检查结果修改后重试。");
        return;
      }
      const acceptanceResponse = await acceptCode(projectId, {
        codeRunId: validationResponse.codeRun.id,
      });
      installCodeRun(acceptanceResponse.codeRun, summary);
      setStatus("静态检查和语法检查已通过，代码已接受，可在设备页上传。");
      notifyCodeRunChanged(onCodeRunChanged, acceptanceResponse.codeRun);
    } catch (reason) {
      setError(
        reason instanceof Error
          ? reason.message
          : "验证并接受代码失败，代码尚未接受。",
      );
    } finally {
      setValidating(false);
    }
  };

  if (loading) return <p className="floating-placeholder">正在加载代码版本...</p>;
  if (!codeRun) {
    return <p className="code-artifact-error" role="alert">{error ?? "代码版本不可用。"}</p>;
  }

  return (
    <section className="code-artifact-editor" aria-label={`${runtimeLabel} 代码产物`}>
      <div className="code-artifact-subtabs" role="tablist" aria-label="代码产物视图">
        {VIEW_LABELS.map((item) => (
          <button
            key={item.key}
            type="button"
            role="tab"
            aria-selected={view === item.key}
            className={view === item.key ? "is-selected" : ""}
            onClick={() => setView(item.key)}
          >
            {item.label}
          </button>
        ))}
      </div>

      <p className="code-visibility-note">
        {readOnly
          ? "普通模式只读；切换三师专业模式后可保存不可变新版本"
          : "未保存修改智能工程师不可见；保存后下一次回复可见"}
      </p>

      {view === "code" && (
        <div className="code-edit-view">
          <div className="code-file-tabs" role="tablist" aria-label="代码文件">
            {codeRun.files.map((file) => (
              <button
                key={file.path}
                type="button"
                role="tab"
                aria-label={file.path}
                aria-selected={selectedFile?.path === file.path}
                className={selectedFile?.path === file.path ? "is-selected" : ""}
                onClick={() => setSelectedPath(file.path)}
              >
                {file.path}
                {drafts[file.path] !== file.content ? " *" : ""}
              </button>
            ))}
          </div>
          {selectedFile && (
            <Suspense
              fallback={(
                <div className="code-editor-shell code-editor-loading" role="status">
                  正在加载代码编辑器...
                </div>
              )}
            >
              <MonacoCodeEditor
                projectId={projectId}
                codeRunId={codeRun.id}
                filePath={selectedFile.path}
                runtime={codeRun.runtime}
                value={drafts[selectedFile.path] ?? selectedFile.content}
                readOnly={readOnly}
                onChange={(value) => {
                  setDrafts((current) => ({
                    ...current,
                    [selectedFile.path]: value,
                  }));
                  setStatus(null);
                }}
              />
            </Suspense>
          )}
          {!readOnly ? (
            <>
              <label className="code-change-summary">
                <span>变更摘要</span>
                <input
                  aria-label="变更摘要"
                  value={summary}
                  maxLength={500}
                  onChange={(event) => {
                    setSummary(event.target.value);
                    setStatus(null);
                  }}
                  placeholder={`概括本次 ${runtimeLabel} 修改`}
                />
              </label>
              <div className="code-editor-actions">
                <button
                  type="button"
                  disabled={(!dirty && !summary) || actionBusy}
                  onClick={discard}
                >
                  放弃修改
                </button>
                <button
                  type="button"
                  className="code-primary-action"
                  disabled={!dirty || !summary.trim() || actionBusy}
                  onClick={() => void save()}
                >
                  {saving ? "保存中..." : "保存新版本"}
                </button>
              </div>
            </>
          ) : null}
          <section className="code-finalization" aria-label="代码验证与接受">
            <div className="code-finalization-heading">
              <div>
                <strong>最终代码门禁</strong>
                <span>只运行静态检查和语法检查，不执行代码</span>
              </div>
              <button
                type="button"
                className="code-validate-action"
                disabled={dirty || actionBusy || !canValidate}
                onClick={() => void validateAndAccept()}
              >
                {validating ? "正在验证..." : "验证并接受代码"}
              </button>
            </div>
            <div
              className="code-validation-summary"
              role="region"
              aria-label="本地验证结果"
            >
              {REQUIRED_VALIDATION_KINDS.map((kind) => {
                const check = codeRun.testResult.checks.find(
                  (candidate) => candidate.kind === kind,
                );
                return (
                  <span key={kind} className={validationClassName(check?.exitCode ?? null)}>
                    {VALIDATION_LABELS[kind]}：{validationStatus(check?.exitCode ?? null)}
                  </span>
                );
              })}
            </div>
            {codeRun.testResult.checks.some(
              (check) => check.kind !== CodeValidationKind.SIMULATION,
            ) && (
              <details className="code-validation-details">
                <summary>查看检查命令与输出</summary>
                <div className="code-validation-list">
                  {codeRun.testResult.checks
                    .filter((check) => check.kind !== CodeValidationKind.SIMULATION)
                    .map((check) => (
                      <ValidationCheck key={check.kind} check={check} />
                    ))}
                </div>
              </details>
            )}
            {dirty && <p className="code-validation-pending">请先保存当前修改，再验证并接受。</p>}
            {!dirty && !canValidate && codeRun.status !== CodeRunStatus.ACCEPTED && (
              <p className="code-validation-pending">
                当前代码版本状态不允许验证；请打开最新草稿或待确认版本。
              </p>
            )}
            {codeRun.status === CodeRunStatus.ACCEPTED && (
              <p className="code-validation-pending">当前版本已接受，可在设备页上传。</p>
            )}
          </section>
        </div>
      )}

      {view === "changes" && (
        <div className="code-change-view">
          <dl>
            <div>
              <dt>版本</dt>
              <dd>v{codeRun.version}</dd>
            </div>
            <div>
              <dt>来源</dt>
              <dd>{codeRun.revisionSource === "USER" ? "用户保存" : "智能工程师生成"}</dd>
            </div>
          </dl>
          <h4>变更摘要</h4>
          <p>{codeRun.patch.summary || "暂无变更摘要。"}</p>
          <h4>版本差异</h4>
          <pre>{codeRun.patch.diff || "当前版本没有可显示的差异。"}</pre>
        </div>
      )}

      {status && <p className="code-artifact-status" role="status">{status}</p>}
      {error && <p className="code-artifact-error" role="alert">{error}</p>}
    </section>
  );
}

function ValidationCheck({ check }: { check: CodeValidationCheck }) {
  return (
    <article className="code-validation-item">
      <header>
        <strong>{VALIDATION_LABELS[check.kind] ?? check.kind}</strong>
        <span className={validationClassName(check.exitCode)}>
          {validationStatus(check.exitCode)}
        </span>
      </header>
      <code>{check.command}</code>
      <pre>{check.output || "无输出"}</pre>
    </article>
  );
}

function validationStatus(exitCode: number | null): string {
  if (exitCode === null) return "未运行";
  if (exitCode === 0) return "通过";
  return `失败（退出码 ${exitCode}）`;
}

function validationClassName(exitCode: number | null): string {
  if (exitCode === null) return "is-not-run";
  return exitCode === 0 ? "is-passed" : "is-failed";
}

function requiredValidationPassed(codeRun: CodeRun): boolean {
  return (
    codeRun.status === CodeRunStatus.READY_FOR_REVIEW &&
    !codeRun.requiresValidation &&
    codeRun.testResult.ok &&
    REQUIRED_VALIDATION_KINDS.every(
      (kind) =>
        codeRun.testResult.checks.filter((check) => check.kind === kind).length === 1 &&
        codeRun.testResult.checks.find((check) => check.kind === kind)?.exitCode === 0,
    )
  );
}

function codeDrafts(codeRun: CodeRun): Record<string, string> {
  return Object.fromEntries(codeRun.files.map((file) => [file.path, file.content]));
}

function notifyCodeRunChanged(
  callback: CodeArtifactEditorProps["onCodeRunChanged"],
  codeRun: CodeRun,
) {
  void Promise.resolve(callback(codeRun)).catch(() => undefined);
}
