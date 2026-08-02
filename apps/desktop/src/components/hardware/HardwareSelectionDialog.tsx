import { useEffect, useMemo, useState } from "react";
import {
  HardwareCategory,
  HardwareComponentStatus,
  type HardwareComponent,
  type HardwareCategory as HardwareCategoryValue,
} from "@zhangwen/contracts";
import { listHardware } from "../../services/hardwareApi";
import { coverMedia, HardwareMediaImage } from "./HardwareMediaImage";
import {
  operatingVoltageLabel,
  supplyRailsLabel,
} from "../../utils/hardwareElectrical";
import { useDialogFocusTrap } from "../../hooks/useDialogFocusTrap";

const MAX_SELECTED_HARDWARE = 12;

const CATEGORY_OPTIONS: Array<{
  value: "ALL" | HardwareCategoryValue;
  label: string;
  glyph: string;
}> = [
  { value: "ALL", label: "全部", glyph: "全" },
  { value: HardwareCategory.MCU, label: "主控", glyph: "芯" },
  { value: HardwareCategory.SENSOR, label: "传感器", glyph: "感" },
  { value: HardwareCategory.ACTUATOR, label: "执行器", glyph: "动" },
  { value: HardwareCategory.DISPLAY, label: "显示", glyph: "显" },
  { value: HardwareCategory.POWER, label: "供电", glyph: "电" },
  { value: HardwareCategory.STRUCTURE, label: "结构", glyph: "构" },
];

export interface HardwareSelectionConfirmResult {
  warnings?: string[];
}

interface HardwareSelectionDialogProps {
  open: boolean;
  title?: string;
  description?: string;
  initialSelectedIds: string[];
  confirmLabel?: string;
  onConfirm: (
    selectedHardwareIds: string[],
  ) => Promise<HardwareSelectionConfirmResult | void> | HardwareSelectionConfirmResult | void;
  onClose: () => void;
}

export function HardwareSelectionDialog({
  open,
  title = "选择项目硬件",
  description = "从本地已验证硬件库中选择；智能体会优先使用这些器件，并只补充能力缺口。",
  initialSelectedIds,
  confirmLabel = "确认选择",
  onConfirm,
  onClose,
}: HardwareSelectionDialogProps) {
  const initialSelectionSignature = normalizeHardwareIds(initialSelectedIds).join("\u0000");
  const [hardware, setHardware] = useState<HardwareComponent[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [query, setQuery] = useState("");
  const [category, setCategory] = useState<"ALL" | HardwareCategoryValue>("ALL");
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const dialogRef = useDialogFocusTrap<HTMLDivElement>(open, onClose, {
    closeDisabled: submitting,
  });

  useEffect(() => {
    if (!open) return;
    let canceled = false;
    setSelectedIds(
      initialSelectionSignature ? initialSelectionSignature.split("\u0000") : [],
    );
    setQuery("");
    setCategory("ALL");
    setSaved(false);
    setWarnings([]);
    setError(null);
    setLoading(true);
    void listHardware()
      .then((response) => {
        if (canceled) return;
        setHardware(
          response.components.filter(
            (component) => component.status === HardwareComponentStatus.ACTIVE,
          ),
        );
      })
      .catch((loadError: unknown) => {
        if (!canceled) {
          setError(
            loadError instanceof Error
              ? loadError.message
              : "硬件库暂时不可用，请稍后重试。",
          );
        }
      })
      .finally(() => {
        if (!canceled) setLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, [open, initialSelectionSignature]);

  const visibleHardware = useMemo(() => {
    const normalizedQuery = query.trim().toLocaleLowerCase("zh-CN");
    return hardware.filter((component) => {
      if (category !== "ALL" && component.category !== category) return false;
      if (!normalizedQuery) return true;
      return `${component.name} ${component.notes} ${component.category} ${component.electrical.communicationProtocol}`
        .toLocaleLowerCase("zh-CN")
        .includes(normalizedQuery);
    });
  }, [category, hardware, query]);

  if (!open) return null;

  const toggleHardware = (componentId: string, checked: boolean) => {
    setSaved(false);
    setWarnings([]);
    setError(null);
    setSelectedIds((current) =>
      normalizeHardwareIds(
        checked
          ? [...current, componentId]
          : current.filter((id) => id !== componentId),
      ),
    );
  };

  const handleConfirm = () => {
    if (saved) {
      onClose();
      return;
    }
    setSubmitting(true);
    setError(null);
    setWarnings([]);
    void Promise.resolve(onConfirm(normalizeHardwareIds(selectedIds)))
      .then((result) => {
        const nextWarnings = result?.warnings ?? [];
        if (nextWarnings.length > 0) {
          setWarnings(nextWarnings);
          setSaved(true);
          return;
        }
        onClose();
      })
      .catch((submitError: unknown) => {
        setError(
          submitError instanceof Error
            ? submitError.message
            : "项目硬件更新失败，请检查选择后重试。",
        );
      })
      .finally(() => setSubmitting(false));
  };

  return (
    <div className="settings-overlay hardware-picker-overlay">
      <div
        className="hardware-picker-dialog"
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby="hardware-picker-title"
        tabIndex={-1}
      >
        <header className="hardware-picker-header">
          <div>
            <span className="hardware-picker-eyebrow">项目硬件</span>
            <h2 id="hardware-picker-title">{title}</h2>
            <p>{description}</p>
          </div>
          <button
            type="button"
            className="floating-close"
            aria-label={`关闭${title}`}
            disabled={submitting}
            onClick={onClose}
          >
            ✕
          </button>
        </header>

        <div className="hardware-picker-toolbar">
          <div className="hardware-picker-categories" role="group" aria-label="硬件分类">
            {CATEGORY_OPTIONS.map((option) => (
              <button
                key={option.value}
                type="button"
                className={category === option.value ? "is-active" : ""}
                aria-pressed={category === option.value}
                onClick={() => setCategory(option.value)}
              >
                {option.label}
              </button>
            ))}
          </div>
          <input
            type="search"
            aria-label="搜索项目硬件"
            placeholder="搜索名称、说明或协议"
            value={query}
            onChange={(event) => setQuery(event.target.value)}
          />
        </div>

        <div className="hardware-picker-content">
          {loading ? (
            <p className="hardware-picker-state" role="status">正在读取硬件库...</p>
          ) : visibleHardware.length === 0 ? (
            <p className="hardware-picker-state">没有匹配的 ACTIVE 器件。</p>
          ) : (
            <div className="hardware-picker-grid" aria-label="可选项目硬件">
              {visibleHardware.map((component) => {
                const checked = selectedIds.includes(component.id);
                const cover = coverMedia(component.media);
                const categoryOption = CATEGORY_OPTIONS.find(
                  (option) => option.value === component.category,
                );
                return (
                  <label
                    key={component.id}
                    className={`hardware-picker-card ${checked ? "is-selected" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={checked}
                      disabled={!checked && selectedIds.length >= MAX_SELECTED_HARDWARE}
                      onChange={(event) =>
                        toggleHardware(component.id, event.target.checked)
                      }
                    />
                    {cover ? (
                      <HardwareMediaImage
                        asset={cover}
                        className="hardware-picker-visual hardware-picker-image"
                        fallback={(
                          <span
                            className="hardware-picker-visual"
                            data-category={component.category.toLowerCase()}
                            aria-hidden="true"
                          >
                            <b>{categoryOption?.glyph ?? "器"}</b>
                            <small>{categoryOption?.label ?? component.category}</small>
                          </span>
                        )}
                      />
                    ) : (
                      <span
                        className="hardware-picker-visual"
                        data-category={component.category.toLowerCase()}
                        aria-hidden="true"
                      >
                        <b>{categoryOption?.glyph ?? "器"}</b>
                        <small>{categoryOption?.label ?? component.category}</small>
                      </span>
                    )}
                    <span className="hardware-picker-card-body">
                      <strong>{component.name}</strong>
                      <small>{component.notes || "本地硬件知识库器件"}</small>
                      <span className="hardware-picker-tags">
                        <em>{operatingVoltageLabel(component.electrical)}</em>
                        {supplyRailsLabel(component.electrical) && (
                          <em>外设 {supplyRailsLabel(component.electrical)}</em>
                        )}
                        <em>{component.electrical.communicationProtocol}</em>
                        <em>库存 {component.stock}</em>
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {(error || warnings.length > 0) && (
          <div
            className={error ? "hardware-picker-message is-error" : "hardware-picker-message"}
            role={error ? "alert" : "status"}
          >
            {error ? (
              error
            ) : (
              <>
                <strong>硬件已加入项目，请留意：</strong>
                <ul>
                  {warnings.map((warning) => <li key={warning}>{warning}</li>)}
                </ul>
              </>
            )}
          </div>
        )}

        <footer className="hardware-picker-footer">
          <span>已选 {selectedIds.length} 项</span>
          <div>
            {selectedIds.length > 0 && !saved && (
              <button
                type="button"
                className="link-button"
                disabled={submitting}
                onClick={() => {
                  setSaved(false);
                  setWarnings([]);
                  setError(null);
                  setSelectedIds([]);
                }}
              >
                清空选择
              </button>
            )}
            <button type="button" disabled={submitting} onClick={onClose}>取消</button>
            <button
              type="button"
              className="primary-action"
              disabled={loading || submitting || Boolean(error && hardware.length === 0)}
              onClick={handleConfirm}
            >
              {submitting ? "保存中..." : saved ? "完成" : confirmLabel}
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}

export function selectedProjectHardwareIds(
  confirmedFacts: Array<{ field: string; value: unknown; status?: string }> | undefined,
): string[] {
  const fact = confirmedFacts?.find(
    (item) => item.field === "preferred_hardware" && item.status === "confirmed",
  );
  if (!fact || typeof fact.value !== "object" || fact.value === null) return [];
  const components = (fact.value as { components?: unknown }).components;
  if (!Array.isArray(components)) return [];
  return normalizeHardwareIds(
    components.flatMap((item) =>
      typeof item === "object" && item !== null && "id" in item
        ? [String((item as { id: unknown }).id)]
        : [],
    ),
  );
}

function normalizeHardwareIds(ids: string[]): string[] {
  return Array.from(new Set(ids.map((id) => id.trim()).filter(Boolean))).sort();
}
