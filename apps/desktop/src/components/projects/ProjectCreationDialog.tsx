import { useMemo, useRef, useState } from "react";
import { ValidationSeverity } from "@zhangwen/contracts";
import type {
  ExpertDefinition,
  ExpertType,
  RouterOutput,
  SuggestedProject,
  ValidationResult,
} from "@zhangwen/contracts";
import type { CreateProjectFromIdeaInput } from "../../hooks/useProjects";
import { suggestProject } from "../../services/projectsApi";
import { validateHardware } from "../../services/hardwareApi";
import { HardwareSelectionDialog } from "../hardware/HardwareSelectionDialog";
import { useDialogFocusTrap } from "../../hooks/useDialogFocusTrap";
import {
  DEFAULT_THREE_EXPERT_DEFINITIONS,
  THREE_EXPERT_TYPES,
  isThreeExpertType,
} from "../../utils/experts";

const PROJECT_NAME_MAX = 50;
interface ProjectCreationState {
  idea: string;
  analyzedIdea?: string;
  selectedHardwareIds: string[];
  generatedProjectName?: string;
  projectName: string;
  projectNameEditedByUser: boolean;
  routerResult?: RouterOutput;
  selectedExperts: ExpertType[];
  initialExpert?: ExpertType;
  expertSelectionMode: "auto" | "manual";
  status: "idle" | "routing" | "ready" | "creating" | "success" | "error";
  errorMessage?: string;
}

interface ProjectCreationDialogProps {
  open: boolean;
  professionalMode?: boolean;
  onCreateProject: (input: CreateProjectFromIdeaInput) => Promise<unknown>;
  onClose: () => void;
}

export function ProjectCreationDialog({
  open,
  professionalMode = false,
  onCreateProject,
  onClose,
}: ProjectCreationDialogProps) {
  const [creation, setCreation] = useState<ProjectCreationState>({
    idea: "",
    selectedHardwareIds: [],
    projectName: "",
    projectNameEditedByUser: false,
    selectedExperts: [],
    expertSelectionMode: "auto",
    status: "idle",
  });
  const [suggestion, setSuggestion] = useState<SuggestedProject | null>(null);
  const [adjustingExperts, setAdjustingExperts] = useState(false);
  const [hardwarePickerOpen, setHardwarePickerOpen] = useState(false);
  const [hardwareValidation, setHardwareValidation] = useState<ValidationResult | null>(null);
  const routeRequestSeq = useRef(0);
  const createIdempotencyKey = useRef<string | null>(null);
  const dialogRef = useDialogFocusTrap<HTMLDivElement>(
    open && !hardwarePickerOpen,
    onClose,
    { closeDisabled: creation.status === "creating" },
  );

  const handleAnalyze = () => {
    const trimmed = creation.idea.trim();
    if (!trimmed || creation.status === "routing" || creation.status === "creating") {
      return;
    }

    const requestSeq = ++routeRequestSeq.current;
    setCreation((current) => ({
      ...current,
      analyzedIdea: undefined,
      generatedProjectName: undefined,
      projectName: current.projectNameEditedByUser ? current.projectName : "",
      routerResult: undefined,
      selectedExperts:
        current.expertSelectionMode === "manual" ? current.selectedExperts : [],
      initialExpert:
        current.expertSelectionMode === "manual" ? current.initialExpert : undefined,
      status: "routing",
      errorMessage: undefined,
    }));
    setSuggestion(null);
    setHardwareValidation(null);
    void suggestProject({
      text: trimmed,
      selectedHardwareIds: [],
      useModelRouting: true,
    })
      .then((response) => {
        if (requestSeq !== routeRequestSeq.current) return;
        const normalized = normalizeSuggestion(response.suggestion, trimmed);
        setSuggestion(normalized);
        setCreation((current) => ({
          ...applySuggestionToCreationState(current, normalized),
          analyzedIdea: trimmed,
        }));
      })
      .catch((error: unknown) => {
        if (requestSeq !== routeRequestSeq.current) return;
        setSuggestion(null);
        setHardwareValidation(null);
        setCreation((current) => ({
          ...current,
          analyzedIdea: undefined,
          generatedProjectName: undefined,
          projectName: current.projectNameEditedByUser ? current.projectName : "",
          routerResult: undefined,
          selectedExperts:
            current.expertSelectionMode === "manual"
              ? current.selectedExperts
              : [],
          initialExpert:
            current.expertSelectionMode === "manual"
              ? current.initialExpert
              : undefined,
          status: "error",
          errorMessage:
            error instanceof Error
              ? error.message
              : "云端项目建议生成失败，请重试。",
        }));
      });
  };

  const creationExperts = useMemo(
    () => filterThreeExpertDefinitions(suggestion?.availableExperts ?? []),
    [suggestion?.availableExperts]
  );

  const handleCreate = () => {
    const trimmedIdea = creation.idea.trim();
    const projectName = creation.projectName.trim();
    const selectedHardwareIds = normalizeHardwareIds(creation.selectedHardwareIds);
    if (!trimmedIdea || creation.status === "creating") return;
    if (
      !creation.routerResult ||
      creation.analyzedIdea !== trimmedIdea
    ) {
      setCreation((current) => ({
        ...current,
        status: "error",
        errorMessage: "创意已更新，请先点击“分析并推荐”。",
      }));
      return;
    }
    if (!projectName || projectName.length > PROJECT_NAME_MAX) {
      setCreation((current) => ({
        ...current,
        status: "error",
        errorMessage: "项目名称不能为空，且不能超过 50 个字符。",
      }));
      return;
    }
    const selectedExperts = normalizeExpertList(creation.selectedExperts);
    if (selectedExperts.length === 0) {
      setCreation((current) => ({
        ...current,
        status: "error",
        errorMessage: "至少选择一位专家。",
      }));
      return;
    }
    const initialExpert =
      creation.initialExpert && selectedExperts.includes(creation.initialExpert)
        ? creation.initialExpert
        : selectedExperts[0] ?? "problem_guide";
    if (!createIdempotencyKey.current) {
      createIdempotencyKey.current =
        window.crypto?.randomUUID?.() ?? `create_${Date.now()}`;
    }

    setCreation((current) => ({
      ...current,
      initialExpert,
      selectedExperts,
      status: "creating",
      errorMessage: undefined,
    }));
    void onCreateProject({
      idea: trimmedIdea,
      projectName,
      selectedHardwareIds,
      initialExpert,
      participatingExperts: selectedExperts,
      routerResult: creation.routerResult,
      expertSelectionMode: creation.expertSelectionMode,
      idempotencyKey: createIdempotencyKey.current,
    })
      .then(() => {
        createIdempotencyKey.current = null;
        setCreation({
          idea: "",
          selectedHardwareIds: [],
          projectName: "",
          projectNameEditedByUser: false,
          selectedExperts: [],
          expertSelectionMode: "auto",
          status: "success",
        });
        setSuggestion(null);
        setHardwareValidation(null);
        setAdjustingExperts(false);
        onClose();
      })
      .catch((error: unknown) => {
        setCreation((current) => ({
          ...current,
          status: "error",
          errorMessage:
            error instanceof Error
              ? error.message
              : "创建项目失败，请稍后重试。",
        }));
      });
  };

  if (!open) return null;

  const currentStep = creation.status === "creating"
    ? 2
    : creation.routerResult || creation.status === "routing"
      ? 1
      : 0;
  const stepLabels = ["描述创意", "推荐方案与硬件", "确认创建"];

  return (
    <>
    <div className="settings-overlay project-dialog-overlay">
      <div
        className="project-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="project-create-title"
        tabIndex={-1}
      >
        <div className="settings-header">
          <h2 id="project-create-title">新建项目</h2>
          <button
            type="button"
            className="floating-close"
            aria-label="关闭新建项目"
            disabled={creation.status === "creating"}
            onClick={() => {
              if (creation.status !== "creating") onClose();
            }}
          >
            ✕
          </button>
        </div>
        <div className="project-dialog-body">
          <nav className="project-steps" aria-label="创建步骤">
            {stepLabels.map((label, idx) => (
              <span
                key={label}
                className={`project-step ${idx === currentStep ? "project-step-active" : ""} ${idx < currentStep ? "project-step-done" : ""}`}
                aria-current={idx === currentStep ? "step" : undefined}
              >
                <i aria-hidden="true">{idx < currentStep ? "✓" : idx + 1}</i>
                {label}
              </span>
            ))}
          </nav>
          <span className="sr-only" aria-live="polite">
            {`当前步骤：${stepLabels[currentStep]}`}
          </span>
          <label className="project-dialog-field">
            <span>项目创意</span>
            <textarea
              aria-label="新项目创意"
              placeholder="一句话描述你的创意"
              value={creation.idea}
              onChange={(event) => {
                createIdempotencyKey.current = null;
                routeRequestSeq.current += 1;
                const idea = event.target.value;
                setCreation((current) => ({
                  ...current,
                  idea,
                  analyzedIdea: undefined,
                  generatedProjectName: undefined,
                  projectName: current.projectNameEditedByUser
                    ? current.projectName
                    : "",
                  routerResult: undefined,
                  selectedExperts:
                    current.expertSelectionMode === "manual"
                      ? current.selectedExperts
                      : [],
                  initialExpert:
                    current.expertSelectionMode === "manual"
                      ? current.initialExpert
                      : undefined,
                  status: "idle",
                  errorMessage: undefined,
                }));
                setSuggestion(null);
              }}
              rows={4}
              autoFocus
            />
          </label>

          <div className="project-analysis-actions" aria-live="polite">
            <button
              type="button"
              className="primary-action"
              onClick={handleAnalyze}
              disabled={
                !creation.idea.trim() ||
                creation.status === "routing" ||
                creation.status === "creating"
              }
            >
              {creation.status === "routing"
                ? "正在分析..."
                : creation.analyzedIdea
                  ? "重新分析并推荐"
                  : "分析并推荐"}
            </button>
            <span>
              {creation.status === "routing"
                ? "正在根据完整创意生成项目名称和工程师建议。"
                : creation.analyzedIdea
                  ? "推荐已生成；现在可以选择项目硬件，再开始项目。"
                  : "完成创意描述后再分析，推荐会更准确。"}
            </span>
          </div>

          {creation.status === "routing" && (
            <div className="project-analysis-skeleton" aria-hidden="true">
              <span className="skeleton-line" style={{ width: "70%" }} />
              <span className="skeleton-line" style={{ width: "50%" }} />
              <span className="skeleton-line" style={{ width: "85%" }} />
            </div>
          )}

          {creation.routerResult && (
            <div className="project-suggestion" aria-live="polite">
              <label className="project-dialog-field">
                <span>项目名称</span>
                <input
                  aria-label="项目名称"
                  className="project-name-input"
                  maxLength={PROJECT_NAME_MAX}
                  value={creation.projectName}
                  onChange={(event) => {
                    setCreation((current) => ({
                      ...current,
                      projectName: event.target.value,
                      projectNameEditedByUser: true,
                    }));
                  }}
                />
                <small className="project-name-counter" aria-live="polite">
                  {creation.projectName.length}/{PROJECT_NAME_MAX}
                </small>
              </label>
              <button
                type="button"
                className="link-button"
                disabled={!creation.generatedProjectName}
                onClick={() => {
                  setCreation((current) => ({
                    ...current,
                    projectName:
                      current.generatedProjectName ?? current.projectName,
                    projectNameEditedByUser: false,
                  }));
                }}
              >
                恢复推荐名称
              </button>
              {creation.routerResult?.reason && (
                <p className="sidebar-placeholder" role="status">
                  {creation.routerResult.reason}
                </p>
              )}
              <section
                className="project-hardware-after-analysis"
                aria-labelledby="project-hardware-after-analysis-title"
              >
                <div>
                  <span>分析完成 · 可选</span>
                  <h3 id="project-hardware-after-analysis-title">确认项目硬件</h3>
                  <p>
                    先选择你已有或希望优先使用的器件；正式进入项目后，智能体会基于这些硬件规划。
                  </p>
                </div>
                <div className="project-hardware-after-analysis-actions">
                  <span className="project-hardware-count">
                    {creation.selectedHardwareIds.length > 0
                      ? `已选择 ${creation.selectedHardwareIds.length} 项项目硬件`
                      : "尚未选择，可在规划缺件时再补充"}
                  </span>
                  <button
                    type="button"
                    className="secondary-btn"
                    disabled={creation.status === "creating"}
                    onClick={() => setHardwarePickerOpen(true)}
                  >
                    选择项目硬件
                  </button>
                </div>
              </section>
              {hardwareValidation && hardwareValidation.overall !== ValidationSeverity.PASS && (
                <div className="project-hardware-warning" role="status">
                  <strong>硬件校验提醒</strong>
                  <ul>
                    {hardwareValidation.checks
                      .filter((check) => check.severity !== ValidationSeverity.PASS)
                      .map((check, index) => (
                        <li key={`${index}:${check.dimension}:${check.message}`}>
                          {check.message}{check.details ? `：${check.details}` : ""}
                        </li>
                      ))}
                  </ul>
                </div>
              )}
              {!professionalMode && (
                <div className="project-assistance-summary" role="status">
                  <strong>掌问将协助完成</strong>
                  <p>需求澄清、工程实现和结构设计会按项目需要自动配合；当前只展示一套推荐方案。</p>
                </div>
              )}
              {professionalMode && (
                <>
                <div className="project-agent-selection-heading">
                  <strong>调整参与专家</strong>
                  <button
                    type="button"
                    className="link-button"
                    aria-label="调整专家"
                    onClick={() => setAdjustingExperts((value) => !value)}
                  >
                    {adjustingExperts ? "仅看已选" : "调整专家"}
                  </button>
                </div>
                <div className="expert-chip-list" aria-label="推荐参与专家">
                {creationExperts.map((definition) => {
                  const selected = creation.selectedExperts.includes(definition.type);
                  if (!selected && !adjustingExperts) return null;
                  return (
                    <label
                      key={definition.id}
                      className={`expert-chip ${selected ? "expert-chip-selected" : ""}`}
                    >
                      <input
                        type="checkbox"
                        checked={selected}
                        onChange={(event) => {
                          const checked = event.target.checked;
                          setCreation((current) => {
                            const currentExperts = normalizeExpertList(
                              current.selectedExperts
                            );
                            const nextExperts = checked
                              ? normalizeExpertList([
                                  ...currentExperts,
                                  definition.type,
                                ])
                              : currentExperts.filter(
                                  (type) => type !== definition.type
                                );
                            if (nextExperts.length === 0) {
                              return {
                                ...current,
                                status: "error",
                                errorMessage: "至少选择一位专家。",
                                expertSelectionMode: "manual",
                              };
                            }
                            const nextInitial =
                              current.initialExpert &&
                              nextExperts.includes(current.initialExpert)
                                ? current.initialExpert
                                : nextExperts[0];
                            return {
                              ...current,
                              selectedExperts: nextExperts,
                              initialExpert: nextInitial,
                              expertSelectionMode: "manual",
                              status:
                                current.status === "error"
                                  ? "ready"
                                  : current.status,
                              errorMessage: undefined,
                            };
                          });
                        }}
                      />
                      <span>{definition.name}</span>
                      {selected && (
                        <input
                          aria-label={`设为初始专家 ${definition.name}`}
                          type="radio"
                          checked={creation.initialExpert === definition.type}
                          onChange={() => {
                            setCreation((current) => ({
                              ...current,
                              initialExpert: definition.type,
                              selectedExperts: normalizeExpertList([
                                ...current.selectedExperts,
                                definition.type,
                              ]),
                              expertSelectionMode: "manual",
                            }));
                          }}
                        />
                      )}
                    </label>
                  );
                })}
                </div>
                </>
              )}
            </div>
          )}

          {creation.errorMessage && creation.status === "error" && (
            <div className="project-create-error" role="alert">
              <span>{creation.errorMessage}</span>
              {!creation.routerResult && creation.idea.trim() && (
                <button
                  type="button"
                  className="link-button"
                  onClick={handleAnalyze}
                >
                  重新分析并推荐
                </button>
              )}
            </div>
          )}
        </div>
        <div className="project-dialog-actions">
          <button
            type="button"
            disabled={creation.status === "creating"}
            onClick={onClose}
          >
            取消
          </button>
          <button
            type="button"
            className="primary-action"
            onClick={handleCreate}
            disabled={
              !creation.idea.trim() ||
              !creation.routerResult ||
              creation.analyzedIdea !== creation.idea.trim() ||
              creation.status === "routing" ||
              creation.status === "creating"
            }
          >
            {creation.status === "creating" ? "创建中..." : "开始项目"}
          </button>
        </div>
      </div>
    </div>
    <HardwareSelectionDialog
      open={hardwarePickerOpen}
      initialSelectedIds={creation.selectedHardwareIds}
      onConfirm={async (selectedHardwareIds) => {
        createIdempotencyKey.current = null;
        const normalizedIds = normalizeHardwareIds(selectedHardwareIds);
        const response = await validateHardware(normalizedIds);
        const validation = response.result;
        if (validation.overall === ValidationSeverity.FAIL) {
          const details = validation.checks
            .filter((check) => check.severity === ValidationSeverity.FAIL)
            .map((check) => `${check.message}${check.details ? `：${check.details}` : ""}`)
            .join("；");
          throw new Error(`所选硬件未通过安全校验：${details || validation.message}`);
        }
        setHardwareValidation(validation);
        setCreation((current) => ({
          ...current,
          selectedHardwareIds: normalizedIds,
          errorMessage: undefined,
        }));
        const warnings = validation.checks
          .filter((check) => check.severity === ValidationSeverity.WARNING)
          .map((check) => `${check.message}${check.details ? `：${check.details}` : ""}`);
        if (warnings.length > 0) return { warnings };
        setHardwarePickerOpen(false);
      }}
      onClose={() => setHardwarePickerOpen(false)}
    />
    </>
  );
}

function applySuggestionToCreationState(
  current: ProjectCreationState,
  nextSuggestion: SuggestedProject,
  message?: string
): ProjectCreationState {
  const routerResult = normalizeRouterOutput(
    nextSuggestion.routerResult
  );
  const autoExperts = normalizeExpertList(routerResult.recommendedExperts);
  const selectedExperts =
    current.expertSelectionMode === "manual" && current.selectedExperts.length > 0
      ? normalizeExpertList(current.selectedExperts)
      : autoExperts;
  const initialExpert =
    current.expertSelectionMode === "manual" &&
    current.initialExpert &&
    selectedExperts.includes(current.initialExpert)
      ? current.initialExpert
      : selectedExperts.includes(routerResult.initialExpert)
        ? routerResult.initialExpert
        : selectedExperts[0];
  return {
    ...current,
    generatedProjectName: routerResult.projectName,
    projectName: current.projectNameEditedByUser
      ? current.projectName
      : routerResult.projectName,
    routerResult,
    selectedExperts,
    initialExpert,
    status: "ready",
    errorMessage: message,
  };
}

function normalizeSuggestion(
  suggestion: SuggestedProject,
  idea: string
): SuggestedProject {
  const routerResult = normalizeRouterOutput(
    suggestion.routerResult
  );
  const availableExperts = filterThreeExpertDefinitions(
    suggestion.availableExperts.length > 0
      ? suggestion.availableExperts
      : DEFAULT_THREE_EXPERT_DEFINITIONS
  );
  return {
    ...suggestion,
    name: routerResult.projectName,
    initialIdea: suggestion.initialIdea || idea,
    recommendedExpertTypes: routerResult.recommendedExperts,
    availableExperts,
    initialExpert: routerResult.initialExpert,
    routerResult,
    reason: routerResult.reason,
    confidence: routerResult.confidence,
    requiresClarification: routerResult.requiresClarification,
  };
}

function normalizeRouterOutput(
  routerResult: RouterOutput | undefined
): RouterOutput {
  if (!routerResult) {
    throw new Error("云端模型没有返回有效的项目路由结果，请重试。");
  }
  const recommended = normalizeExpertList(routerResult.recommendedExperts);
  const initial = routerResult.initialExpert;
  if (
    recommended.length === 0 ||
    !isThreeExpert(initial) ||
    !recommended.includes(initial)
  ) {
    throw new Error("云端模型返回的专家路由无效，请重试。");
  }
  return {
    ...routerResult,
    projectName: routerResult.projectName.slice(0, 40),
    initialExpert: initial,
    recommendedExperts: recommended,
    confidence: clampConfidence(routerResult.confidence),
  };
}

function normalizeExpertList(experts: ExpertType[]): ExpertType[] {
  const result: ExpertType[] = [];
  for (const expert of experts) {
    if (!isThreeExpert(expert) || result.includes(expert)) continue;
    result.push(expert);
  }
  return result;
}

function filterThreeExpertDefinitions(
  definitions: ExpertDefinition[]
): ExpertDefinition[] {
  const byType = new Map<ExpertType, ExpertDefinition>();
  for (const definition of definitions) {
    if (isThreeExpert(definition.type) && !byType.has(definition.type)) {
      byType.set(definition.type, definition);
    }
  }
  for (const definition of DEFAULT_THREE_EXPERT_DEFINITIONS) {
    if (!byType.has(definition.type)) byType.set(definition.type, definition);
  }
  return THREE_EXPERT_TYPES.map((type) => byType.get(type)).filter(
    (definition): definition is ExpertDefinition => Boolean(definition)
  );
}

function isThreeExpert(
  expert: ExpertType | string | undefined
): expert is ExpertType {
  return isThreeExpertType(expert);
}

function clampConfidence(value: number): number {
  if (!Number.isFinite(value)) return 0.4;
  return Math.max(0, Math.min(1, value));
}

function normalizeHardwareIds(ids: string[]): string[] {
  return Array.from(new Set(ids.map((id) => id.trim()).filter(Boolean))).sort();
}
