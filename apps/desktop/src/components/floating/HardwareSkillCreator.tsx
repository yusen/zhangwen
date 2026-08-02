import { useEffect, useRef, useState } from "react";
import type {
  HardwareSkillDetail,
  HardwareSkillDraft,
  HardwareSkillDraftSource,
} from "@zhangwen/contracts";
import {
  confirmHardwareSkillDraft,
  continueHardwareSkillDraft,
  createHardwareSkillDraft,
  deleteHardwareSkillDraft,
} from "../../services/hardwareApi";

type CreatorStep = "sources" | "supplement" | "preview";

interface HardwareSkillCreatorProps {
  onCreated: (skill: HardwareSkillDetail) => void;
  onCancel: () => void;
  technicalLabels?: boolean;
}

const ACCEPTED_EXTENSIONS = new Set(["md", "markdown", "txt", "json", "csv", "pdf"]);
const MAX_FILES = 8;
const MAX_FILE_BYTES = 500_000;
const MAX_PDF_BYTES = 2_000_000;

export function HardwareSkillCreator({
  onCreated,
  onCancel,
  technicalLabels = true,
}: HardwareSkillCreatorProps) {
  const [step, setStep] = useState<CreatorStep>("sources");
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [pastedSource, setPastedSource] = useState("");
  const [uploadedSources, setUploadedSources] = useState<HardwareSkillDraftSource[]>([]);
  const [draft, setDraft] = useState<HardwareSkillDraft | null>(null);
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const draftIdRef = useRef<string | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
      const draftId = draftIdRef.current;
      draftIdRef.current = null;
      if (draftId) void deleteHardwareSkillDraft(draftId).catch(() => undefined);
    };
  }, []);

  const createDraft = async () => {
    const sources = [...uploadedSources];
    if (pastedSource.trim()) {
      sources.unshift({
        name: "pasted-notes.md",
        mediaType: "text/markdown",
        content: pastedSource.trim(),
      });
    }
    if (sources.length === 0) {
      setError("请粘贴说明，或上传至少一个 Markdown、TXT、JSON、CSV、PDF 文件。");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const response = await createHardwareSkillDraft({
        name: name.trim() || undefined,
        description: description.trim() || undefined,
        sources,
      });
      if (!mountedRef.current) {
        void deleteHardwareSkillDraft(response.draft.id).catch(() => undefined);
        return;
      }
      draftIdRef.current = response.draft.id;
      setDraft(response.draft);
      setStep("supplement");
    } catch (createError) {
      if (mountedRef.current) {
        setError(createError instanceof Error ? createError.message : "生成草稿失败，请重试。");
      }
    } finally {
      if (mountedRef.current) setBusy(false);
    }
  };

  const submitMessage = async () => {
    if (!draft || !message.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const response = await continueHardwareSkillDraft(draft.id, {
        message: message.trim(),
        expectedRevision: draft.revision,
      });
      if (!mountedRef.current) {
        void deleteHardwareSkillDraft(draft.id).catch(() => undefined);
        return;
      }
      setDraft(response.draft);
      setMessage("");
    } catch (messageError) {
      if (mountedRef.current) {
        setError(messageError instanceof Error ? messageError.message : "补充资料失败，请重试。");
      }
    } finally {
      if (mountedRef.current) setBusy(false);
    }
  };

  const confirm = async () => {
    if (!draft || !draft.canConfirm) return;
    setBusy(true);
    setError(null);
    try {
      const response = await confirmHardwareSkillDraft(draft.id, {
        expectedRevision: draft.revision,
      });
      draftIdRef.current = null;
      if (mountedRef.current) onCreated(response.skill);
    } catch (confirmError) {
      if (mountedRef.current) {
        setError(confirmError instanceof Error ? confirmError.message : "确认创建失败，请重试。");
      }
    } finally {
      if (mountedRef.current) setBusy(false);
    }
  };

  const cancel = () => {
    const draftId = draftIdRef.current ?? draft?.id ?? null;
    draftIdRef.current = null;
    if (draftId) void deleteHardwareSkillDraft(draftId).catch(() => undefined);
    onCancel();
  };

  const readFiles = async (files: FileList | null) => {
    if (!files) return;
    const selected = Array.from(files);
    if (selected.length + uploadedSources.length > MAX_FILES) {
      setError(`最多上传 ${MAX_FILES} 个资料文件。`);
      if (fileInputRef.current) fileInputRef.current.value = "";
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const next: HardwareSkillDraftSource[] = [];
      for (const file of selected) {
        const extension = file.name.split(".").at(-1)?.toLowerCase() ?? "";
        if (!ACCEPTED_EXTENSIONS.has(extension)) {
          throw new Error(`${file.name} 类型不受支持，仅接受 Markdown、TXT、JSON、CSV、PDF。`);
        }
        const maxBytes = extension === "pdf" ? MAX_PDF_BYTES : MAX_FILE_BYTES;
        if (file.size > maxBytes) {
          throw new Error(
            `${file.name} 超过${extension === "pdf" ? " 2 MB" : " 500 KB"}限制。`,
          );
        }
        next.push({
          name: file.name,
          mediaType: mediaTypeForFile(file),
          content: extension === "pdf" ? await fileToBase64(file) : await fileToUtf8(file),
        });
      }
      setUploadedSources((current) => [...current, ...next]);
    } catch (uploadError) {
      setError(uploadError instanceof Error ? uploadError.message : "读取资料失败。");
    } finally {
      setBusy(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  };

  return (
    <section
      className="hardware-skill-creator"
      role="region"
      aria-label={technicalLabels ? "创建 Hardware Skill" : "创建硬件知识"}
    >
      <header>
        <div>
          <span>{technicalLabels ? "硬件库项目" : "器件资料"}</span>
          <h4>{technicalLabels ? "新建 Hardware Skill" : "新建硬件知识"}</h4>
        </div>
        <button
          type="button"
          aria-label={technicalLabels ? "关闭 Hardware Skill 创建器" : "关闭硬件知识创建器"}
          onClick={cancel}
        >×</button>
      </header>

      <ol className="hardware-skill-steps" aria-label="创建步骤">
        <li className={step === "sources" ? "is-current" : "is-complete"}>1 资料</li>
        <li className={step === "supplement" ? "is-current" : step === "preview" ? "is-complete" : ""}>2 补充</li>
        <li className={step === "preview" ? "is-current" : ""}>3 预览确认</li>
      </ol>

      {step === "sources" && (
        <div className="hardware-skill-source-step">
          <div className="hardware-skill-source-meta">
            <label>
              <span>{technicalLabels ? "Skill 名称" : "硬件名称"}</span>
              <input
                aria-label={technicalLabels ? "Skill 名称" : "硬件名称"}
                value={name}
                maxLength={100}
                placeholder="例如：BME280 环境传感器"
                onChange={(event) => setName(event.target.value)}
              />
            </label>
            <label>
              <span>简短说明（可选）</span>
              <input
                aria-label={technicalLabels ? "Skill 简短说明" : "硬件简短说明"}
                value={description}
                maxLength={500}
                placeholder="记录适用场景"
                onChange={(event) => setDescription(event.target.value)}
              />
            </label>
          </div>
          <label>
            <span>粘贴资料</span>
            <textarea
              aria-label="粘贴资料"
              value={pastedSource}
              rows={7}
              placeholder="粘贴数据手册摘录、接线说明、参数或安全要求"
              onChange={(event) => setPastedSource(event.target.value)}
            />
          </label>
          <div className="hardware-skill-upload">
            <label>
              <span>上传资料</span>
              <input
                ref={fileInputRef}
                type="file"
                multiple
                accept=".md,.markdown,.txt,.json,.csv,.pdf,text/markdown,text/plain,application/json,text/csv,application/pdf"
                aria-label={technicalLabels ? "上传 Hardware Skill 资料" : "上传硬件资料"}
                disabled={busy}
                onChange={(event) => void readFiles(event.target.files)}
              />
            </label>
            <small>
              支持 Markdown、TXT、JSON、CSV（500 KB）和 PDF（2 MB，本地提取文本）；最多 8 个文件。
            </small>
            {uploadedSources.length > 0 && (
              <ul>
                {uploadedSources.map((source, index) => (
                  <li key={`${source.name}:${index}`}>
                    <span>{source.name}</span>
                    <button
                      type="button"
                      aria-label={`移除 ${source.name}`}
                      onClick={() => setUploadedSources((current) => current.filter((_, itemIndex) => itemIndex !== index))}
                    >移除</button>
                  </li>
                ))}
              </ul>
            )}
          </div>
          <div className="hardware-skill-creator-actions">
            <button type="button" onClick={cancel}>取消</button>
            <button type="button" disabled={busy || (!pastedSource.trim() && uploadedSources.length === 0)} onClick={() => void createDraft()}>
              {busy ? "生成中..." : "生成草稿"}
            </button>
          </div>
        </div>
      )}

      {step === "supplement" && draft && (
        <div className="hardware-skill-supplement-step">
          <DraftSummary draft={draft} technicalLabels={technicalLabels} />
          {draft.missingQuestions.length > 0 ? (
            <section className="hardware-skill-questions" aria-label="待补充问题">
              <strong>还需要确认</strong>
              <ul>{draft.missingQuestions.map((question) => <li key={question}>{question}</li>)}</ul>
            </section>
          ) : (
            <p className="hardware-skill-ready" role="status">关键资料已齐备，可以进入预览确认。</p>
          )}
          <label>
            <span>补充说明</span>
            <textarea
              aria-label="补充说明"
              value={message}
              rows={4}
              placeholder="回答上方问题，或继续补充参数、规则和使用边界"
              onChange={(event) => setMessage(event.target.value)}
            />
          </label>
          <div className="hardware-skill-creator-actions">
            <button type="button" onClick={cancel}>取消</button>
            <button type="button" disabled={busy || !message.trim()} onClick={() => void submitMessage()}>
              {busy ? "提交中..." : "提交补充"}
            </button>
            <button type="button" disabled={busy || !draft.canConfirm} onClick={() => setStep("preview")}>
              预览确认
            </button>
          </div>
        </div>
      )}

      {step === "preview" && draft && (
        <div className="hardware-skill-preview-step">
          <DraftSummary draft={draft} technicalLabels={technicalLabels} />
          <div className="hardware-skill-preview-grid">
            <section>
              <strong>目录文件</strong>
              <ul>{draft.files.map((file) => <li key={file.path}>{technicalLabels ? file.path : file.title}</li>)}</ul>
            </section>
            <section>
              <strong>声明式规则</strong>
              {draft.rules.length > 0 ? (
                <ul>{draft.rules.map((rule) => (
                  <li key={rule.id}>
                    {technicalLabels && <><code>{rule.operator}</code> · </>}{rule.message}
                  </li>
                ))}</ul>
              ) : <p>没有额外兼容规则。</p>}
            </section>
          </div>
          <p className="hardware-skill-confirm-note">
            确认后本地服务才会保存{technicalLabels ? " Hardware Skill 项目" : "硬件知识"}并加入三位工程师的有效上下文。
          </p>
          <div className="hardware-skill-creator-actions">
            <button type="button" disabled={busy} onClick={() => setStep("supplement")}>返回补充</button>
            <button type="button" disabled={busy || !draft.canConfirm} onClick={() => void confirm()}>
              {busy ? "创建中..." : "确认创建"}
            </button>
          </div>
        </div>
      )}

      {error && <p className="hardware-skill-creator-error" role="alert">{error}</p>}
    </section>
  );
}

function DraftSummary({
  draft,
  technicalLabels,
}: {
  draft: HardwareSkillDraft;
  technicalLabels: boolean;
}) {
  return (
    <>
      <div className="hardware-skill-draft-summary">
        <div><span>资料</span><strong>{draft.sources.length} 份</strong></div>
        <div><span>文件</span><strong>{draft.files.length} 个</strong></div>
        <div><span>{technicalLabels ? "规则" : "兼容检查"}</span><strong>{draft.rules.length} 条</strong></div>
        <div><span>校验</span><strong>{draft.diagnostics.length === 0 ? "无阻塞问题" : `${draft.diagnostics.length} 项`}</strong></div>
      </div>
      {draft.diagnostics.length > 0 && (
        <section
          className="hardware-skill-diagnostics"
          aria-label={technicalLabels ? "Hardware Skill 校验诊断" : "硬件知识校验诊断"}
        >
          <strong>校验诊断</strong>
          <ul>
            {draft.diagnostics.map((diagnostic) => (
              <li
                key={`${diagnostic.path}:${diagnostic.code}:${diagnostic.message}`}
                data-severity={diagnostic.severity}
                role={diagnostic.severity === "error" ? "alert" : "status"}
              >
                <strong>{diagnostic.severity === "error" ? "需要修正" : "提醒"}</strong>
                {technicalLabels && <code>{diagnostic.path}</code>}
                <span>{diagnostic.message}</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </>
  );
}

function mediaTypeForFile(file: File): string {
  if (file.type) return file.type;
  const extension = file.name.split(".").at(-1)?.toLowerCase();
  if (extension === "json") return "application/json";
  if (extension === "csv") return "text/csv";
  if (extension === "pdf") return "application/pdf";
  if (extension === "md" || extension === "markdown") return "text/markdown";
  return "text/plain";
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunkSize = 0x8000;
  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + chunkSize));
  }
  return btoa(binary);
}

async function fileToUtf8(file: File): Promise<string> {
  try {
    return new TextDecoder("utf-8", { fatal: true }).decode(await file.arrayBuffer());
  } catch {
    throw new Error(`${file.name} 不是有效 UTF-8 文本，请先转换编码。`);
  }
}
