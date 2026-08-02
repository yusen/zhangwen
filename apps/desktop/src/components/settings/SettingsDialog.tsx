import { useEffect, useRef, useState } from "react";
import type {
  ConnectionTestRequest,
  ConnectionTestResult,
  LLMConfig,
  ModelConfig,
  SaveLLMConfigRequest,
  AgentPackageSummary,
  HardwareSkillSummary,
  MechanicalProfileSummary,
} from "@zhangwen/contracts";
import { LlmSettingsPanel } from "./LlmSettingsPanel";
import { ExpertSkillSettings } from "./ExpertSkillSettings";
import { HardwareLibrary } from "../hardware/HardwareLibrary";
import { AccountProfileSettings } from "./AccountProfileSettings";

interface SettingsDialogProps {
  config: LLMConfig | null;
  models: ModelConfig[];
  saving: boolean;
  testing: boolean;
  message: string | null;
  error: string | null;
  professionalMode: boolean;
  showModeControl?: boolean;
  onProfessionalModeChange: (enabled: boolean) => void;
  onSave: (request: SaveLLMConfigRequest) => Promise<void>;
  onClearKey: () => Promise<void>;
  onTest: (request: ConnectionTestRequest) => Promise<ConnectionTestResult>;
  onOpenHardwareSkill?: (skill: HardwareSkillSummary) => void;
  onOpenMechanicalProfilePreview?: (profile: MechanicalProfileSummary) => void;
  onOpenAgentPackage?: (agentPackage: AgentPackageSummary) => void;
  onClose: () => void;
}

export function SettingsDialog({
  config,
  models,
  saving,
  testing,
  message,
  error,
  professionalMode,
  showModeControl = true,
  onProfessionalModeChange,
  onSave,
  onClearKey,
  onTest,
  onOpenHardwareSkill,
  onOpenMechanicalProfilePreview,
  onOpenAgentPackage,
  onClose,
}: SettingsDialogProps) {
  const [section, setSection] = useState<"general" | "profile" | "agents" | "hardware">("general");
  const dialogRef = useRef<HTMLDivElement>(null);
  const closeButtonRef = useRef<HTMLButtonElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!professionalMode && section === "agents") setSection("general");
  }, [professionalMode, section]);

  useEffect(() => {
    const activeElement =
      document.activeElement instanceof HTMLElement && document.activeElement !== document.body
        ? document.activeElement
        : document.querySelector<HTMLElement>('[aria-label="打开设置"]');
    previouslyFocusedRef.current = activeElement;
    closeButtonRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab" || !dialogRef.current) return;

      const focusable = Array.from(
        dialogRef.current.querySelectorAll<HTMLElement>(
          'button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [href], [tabindex]:not([tabindex="-1"])',
        ),
      ).filter((element) => element.offsetParent !== null);
      if (focusable.length === 0) {
        event.preventDefault();
        return;
      }

      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first || !last) return;
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
      document.removeEventListener("keydown", handleKeyDown);
      previouslyFocusedRef.current?.focus();
    };
  }, []);

  return (
    <div className="settings-overlay" data-testid="settings-dialog">
      <div
        className="settings-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-title"
      >
        <div className="settings-header">
          <h2 id="settings-title">设置</h2>
          <button
            ref={closeButtonRef}
            type="button"
            className="floating-close"
            onClick={onClose}
            aria-label="关闭设置"
          >
            ✕
          </button>
        </div>
        <div className="settings-layout">
          <nav className="settings-nav" aria-label="设置分类">
            <button
              type="button"
              className={section === "general" ? "active" : ""}
              aria-current={section === "general" ? "page" : undefined}
              onClick={() => setSection("general")}
            >
              模型与界面
            </button>
            <button
              type="button"
              className={section === "profile" ? "active" : ""}
              aria-current={section === "profile" ? "page" : undefined}
              onClick={() => setSection("profile")}
            >
              使用偏好
            </button>
            {professionalMode && (
              <button
                type="button"
                className={section === "agents" ? "active" : ""}
                aria-current={section === "agents" ? "page" : undefined}
                onClick={() => setSection("agents")}
              >
                智能体
              </button>
            )}
            <button
              type="button"
              className={section === "hardware" ? "active" : ""}
              aria-current={section === "hardware" ? "page" : undefined}
              onClick={() => setSection("hardware")}
            >
              公共知识
            </button>
          </nav>
          <div className="settings-content">
            {section === "general" && (
              <>
                <header className="settings-section-header">
                  <span>工作台设置</span>
                  <h3>模型与界面</h3>
                  <p>
                    {showModeControl
                      ? "普通模式保持必要信息，专业模式展开模型与工程配置。"
                      : "配置创作对话使用的模型连接；工程细节在各创作阶段按需展开。"}
                  </p>
                </header>
                {showModeControl ? <section className="settings-mode-section" aria-label="界面模式">
                  <div className="settings-mode-copy">
                    <strong>界面模式</strong>
                    <span>专业模式显示模型、Agent、Skill 和高级工程信息。</span>
                  </div>
                  <label className="professional-toggle">
                    <input
                      type="checkbox"
                      checked={professionalMode}
                      onChange={(event) => onProfessionalModeChange(event.target.checked)}
                    />
                    <span>专业模式</span>
                  </label>
                  <span className="settings-mode-status">
                    {professionalMode ? "已开启" : "已关闭"}
                  </span>
                </section> : null}
                <LlmSettingsPanel
                  config={config}
                  models={models}
                  saving={saving}
                  testing={testing}
                  message={message}
                  error={error}
                  professionalMode={professionalMode}
                  onSave={onSave}
                  onClearKey={onClearKey}
                  onTest={onTest}
                />
              </>
            )}
            {section === "profile" && <AccountProfileSettings />}
            {section === "agents" && professionalMode && (
              <ExpertSkillSettings onOpenPackage={onOpenAgentPackage} />
            )}
            {section === "hardware" && (
              <section className="settings-resource-section" aria-label="公共知识库">
                <div className="settings-resource-heading">
                  <div>
                    <h3>公共知识库</h3>
                    <p>只维护一份工程知识，三位工程师按当前任务读取相关条目。</p>
                  </div>
                </div>
                <div className="shared-knowledge-banner" role="note">
                  <strong>三位工程师共享</strong>
                  <span>问题引导师</span>
                  <span>智能工程师</span>
                  <span>结构工程师</span>
                  <small>各自的对话、行为文件和私有记忆仍保持隔离。</small>
                </div>
                <HardwareLibrary
                  allowBoardProfiles={professionalMode}
                  professionalMode={professionalMode}
                  onOpenSkillProject={onOpenHardwareSkill}
                  onOpenMechanicalProfilePreview={onOpenMechanicalProfilePreview}
                />
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
