import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  HardwareSkillDetail,
  HardwareSkillSummary,
  MechanicalProfileSummary,
} from "@zhangwen/contracts";
import {
  getHardwareSkill,
  listHardwareSkills,
  refreshHardwareCatalog,
} from "../../services/hardwareApi";
import { HardwareSkillCreator } from "../floating/HardwareSkillCreator";
import { BoardProfileLibrary } from "./BoardProfileLibrary";
import { coverMedia, HardwareMediaImage } from "./HardwareMediaImage";
import { subscribeHardwareSkillUpdated } from "../../utils/hardwareSkillEvents";
import {
  operatingVoltageLabel,
  supplyRailsLabel,
} from "../../utils/hardwareElectrical";

const MechanicalProfileLibrary = lazy(async () => {
  const module = await import("./MechanicalProfileLibrary");
  return { default: module.MechanicalProfileLibrary };
});

const CATEGORY_LABELS: Record<string, string> = {
  MCU: "主控",
  SENSOR: "传感器",
  ACTUATOR: "执行器",
  DISPLAY: "显示",
  POWER: "供电",
  STRUCTURE: "结构",
};

interface HardwareLibraryProps {
  allowBoardProfiles?: boolean;
  professionalMode?: boolean;
  onOpenSkillProject?: (skill: HardwareSkillSummary) => void;
  onOpenMechanicalProfilePreview?: (profile: MechanicalProfileSummary) => void;
}

export function HardwareLibrary({
  allowBoardProfiles = false,
  professionalMode = false,
  onOpenSkillProject,
  onOpenMechanicalProfilePreview,
}: HardwareLibraryProps) {
  const [activeView, setActiveView] = useState<"skills" | "boards" | "mechanical">("skills");
  const [skills, setSkills] = useState<HardwareSkillSummary[]>([]);
  const [selectedSkillName, setSelectedSkillName] = useState<string | null>(null);
  const [detail, setDetail] = useState<HardwareSkillDetail | null>(null);
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailRefreshRevision, setDetailRefreshRevision] = useState(0);
  const [search, setSearch] = useState("");
  const [filterCategory, setFilterCategory] = useState("");
  const [creatorOpen, setCreatorOpen] = useState(false);
  const [catalogStale, setCatalogStale] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const loadRequestSeq = useRef(0);
  const detailRequestSeq = useRef(0);

  const loadSkills = useCallback(async () => {
    const requestSeq = ++loadRequestSeq.current;
    setLoading(true);
    setError(null);
    try {
      const response = await listHardwareSkills();
      if (requestSeq !== loadRequestSeq.current) return;
      setSkills(response.skills);
      setSelectedSkillName((current) =>
        current && response.skills.some((skill) => skill.skillName === current)
          ? current
          : null,
      );
    } catch (loadError) {
      if (requestSeq !== loadRequestSeq.current) return;
      setError(loadError instanceof Error
        ? loadError.message
        : professionalMode ? "加载 Hardware Skill 硬件库失败。" : "加载硬件知识库失败。");
    } finally {
      if (requestSeq === loadRequestSeq.current) setLoading(false);
    }
  }, [professionalMode]);

  useEffect(() => {
    void loadSkills();
  }, [loadSkills]);

  useEffect(() => subscribeHardwareSkillUpdated((updated) => {
    setCatalogStale(true);
    setStatus(`“${updated.displayName}”已有更新，请手动刷新硬件目录。`);
  }), []);

  const refreshCatalog = useCallback(async () => {
    const requestSeq = ++loadRequestSeq.current;
    setLoading(true);
    setError(null);
    setStatus("正在完整校验并刷新硬件目录，完成前仍可使用当前列表。");
    try {
      const response = await refreshHardwareCatalog();
      if (requestSeq !== loadRequestSeq.current) return;
      setSkills(response.skills);
      setSelectedSkillName((current) =>
        current && response.skills.some((skill) => skill.skillName === current)
          ? current
          : null,
      );
      setCatalogStale(false);
      setDetailRefreshRevision((current) => current + 1);
      setStatus(`硬件目录已刷新，共 ${response.skills.length} 个项目。`);
    } catch (refreshError) {
      if (requestSeq !== loadRequestSeq.current) return;
      setError(refreshError instanceof Error
        ? refreshError.message
        : "刷新硬件目录失败，当前缓存列表未改变。");
    } finally {
      if (requestSeq === loadRequestSeq.current) setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!selectedSkillName) {
      setDetail(null);
      return;
    }
    const requestSeq = ++detailRequestSeq.current;
    setDetail((current) =>
      current?.skillName === selectedSkillName ? current : null,
    );
    setDetailLoading(true);
    setError(null);
    void getHardwareSkill(selectedSkillName)
      .then((response) => {
        if (requestSeq === detailRequestSeq.current) setDetail(response.skill);
      })
      .catch((detailError) => {
        if (requestSeq === detailRequestSeq.current) {
          setError(detailError instanceof Error
            ? detailError.message
            : professionalMode ? "加载 Hardware Skill 详情失败。" : "加载硬件知识详情失败。");
        }
      })
      .finally(() => {
        if (requestSeq === detailRequestSeq.current) setDetailLoading(false);
      });
  }, [detailRefreshRevision, professionalMode, selectedSkillName]);

  const visibleView = allowBoardProfiles ? activeView : "skills";
  const visibleSkills = useMemo(() => {
    const query = search.trim().toLocaleLowerCase("zh-CN");
    return skills.filter((skill) => {
      if (filterCategory && skill.category !== filterCategory) return false;
      if (!query) return true;
      return `${skill.displayName} ${skill.description} ${skill.verificationStatus}`
        .toLocaleLowerCase("zh-CN")
        .includes(query);
    });
  }, [filterCategory, search, skills]);
  const selectedSummary = skills.find((skill) => skill.skillName === selectedSkillName) ?? null;

  return (
    <div className="hardware-library">
      <div className="hardware-header">
        <div>
          <h3 className="sidebar-heading">
            {professionalMode ? "Hardware Skill 硬件库" : "硬件知识库"}
          </h3>
          <p>
            {professionalMode
              ? "器件说明、结构化电气参数和兼容规则统一来自当前有效 Skill 项目。"
              : "三位工程师统一读取已验证的器件说明、电气参数和兼容规则。"}
          </p>
        </div>
        {visibleView === "skills" && (
          <div className="hardware-header-actions">
            <button
              type="button"
              className={`hardware-refresh-btn ${catalogStale ? "has-update" : ""}`}
              onClick={() => void refreshCatalog()}
              disabled={loading}
            >
              {loading ? "正在刷新..." : catalogStale ? "刷新硬件目录（有更新）" : "刷新硬件目录"}
            </button>
            <button
              type="button"
              className="hardware-add-btn"
              onClick={() => {
                setCreatorOpen((current) => !current);
                setStatus(null);
                setError(null);
              }}
            >
              {creatorOpen
                ? "收起创建器"
                : professionalMode ? "新建 Hardware Skill" : "新建硬件知识"}
            </button>
          </div>
        )}
      </div>

      {allowBoardProfiles && (
        <div className="hardware-library-tabs" role="tablist" aria-label="硬件库类型">
          <button
            type="button"
            role="tab"
            aria-selected={visibleView === "skills"}
            className={visibleView === "skills" ? "is-selected" : ""}
            onClick={() => setActiveView("skills")}
          >
            器件知识
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={visibleView === "boards"}
            className={visibleView === "boards" ? "is-selected" : ""}
            onClick={() => setActiveView("boards")}
          >
            开发板档案
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={visibleView === "mechanical"}
            className={visibleView === "mechanical" ? "is-selected" : ""}
            onClick={() => setActiveView("mechanical")}
          >
            机械档案
          </button>
        </div>
      )}

      {visibleView === "boards" ? (
        <BoardProfileLibrary />
      ) : visibleView === "mechanical" ? (
        <Suspense fallback={<p className="sidebar-placeholder">加载机械档案...</p>}>
          <MechanicalProfileLibrary onOpenPreview={onOpenMechanicalProfilePreview} />
        </Suspense>
      ) : (
        <>
          {creatorOpen && (
            <HardwareSkillCreator
              technicalLabels={professionalMode}
              onCancel={() => setCreatorOpen(false)}
              onCreated={(created) => {
                setCreatorOpen(false);
                setCatalogStale(true);
                setStatus(professionalMode
                  ? `已创建“${created.displayName}”，请手动刷新 Hardware Skill 目录后显示。`
                  : `已创建“${created.displayName}”，请手动刷新硬件目录后显示。`);
              }}
            />
          )}

          {error && <p className="hardware-error" role="alert">{error}</p>}
          {status && <p className="hardware-knowledge-status" role="status">{status}</p>}

          <div className="hardware-search-row">
            <input
              className="hardware-search"
              aria-label={professionalMode ? "搜索 Hardware Skill" : "搜索硬件知识"}
              placeholder="搜索器件名称、说明或验证状态..."
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
            <span>{visibleSkills.length} 个项目</span>
          </div>

          <div className="hardware-filters" aria-label={professionalMode ? "Hardware Skill 分类" : "硬件知识分类"}>
            <button
              type="button"
              className={`filter-btn ${!filterCategory ? "filter-btn-active" : ""}`}
              aria-pressed={!filterCategory}
              onClick={() => setFilterCategory("")}
            >全部</button>
            {Object.entries(CATEGORY_LABELS).map(([key, label]) => (
              <button
                key={key}
                type="button"
                className={`filter-btn ${filterCategory === key ? "filter-btn-active" : ""}`}
                aria-pressed={filterCategory === key}
                onClick={() => setFilterCategory(key)}
              >{label}</button>
            ))}
          </div>

          {loading && (
            <p className="sidebar-placeholder" role="status">
              {professionalMode ? "正在读取 Hardware Skill..." : "正在读取硬件知识..."}
            </p>
          )}
          {!loading && visibleSkills.length === 0 && (
            <p className="sidebar-placeholder">没有匹配的硬件知识项目。</p>
          )}

          <div className="hardware-skill-browser">
            <ul className="hardware-skill-list" aria-label={professionalMode ? "Hardware Skill 项目" : "硬件知识项目"}>
              {visibleSkills.map((skill) => (
                <li key={skill.skillName} className={skill.skillName === selectedSkillName ? "is-selected" : ""}>
                  <button
                    type="button"
                    aria-label={`查看 ${skill.displayName}`}
                    onClick={() => setSelectedSkillName(skill.skillName)}
                  >
                    <span className="hardware-skill-list-media" aria-hidden="true">
                      {coverMedia(skill.media) && (
                        <HardwareMediaImage
                          asset={coverMedia(skill.media)!}
                          className="hardware-skill-list-cover"
                        />
                      )}
                    </span>
                    <span>
                      <strong>{skill.displayName}</strong>
                      <small>{CATEGORY_LABELS[skill.category] ?? skill.category} · {statusLabel(skill.status)}</small>
                    </span>
                    <i className={skill.diagnostics.some((item) => item.severity === "error") ? "is-error" : ""}>
                      {skill.diagnostics.some((item) => item.severity === "error") ? "需修正" : "可使用"}
                    </i>
                  </button>
                </li>
              ))}
            </ul>

            <section
              className="hardware-skill-detail"
              role="region"
              aria-label={`${professionalMode ? "Hardware Skill" : "硬件知识"} 详情 ${selectedSummary?.displayName ?? "未选择"}`}
            >
              {detailLoading && !detail ? (
                <p className="sidebar-placeholder" role="status">正在读取详情...</p>
              ) : detail ? (
                <>
                  {coverMedia(detail.media) && (
                    <figure className="hardware-skill-media">
                      <HardwareMediaImage
                        asset={coverMedia(detail.media)!}
                        className="hardware-skill-cover"
                      />
                      <figcaption>
                        图片来源：{coverMedia(detail.media)!.attribution}
                      </figcaption>
                    </figure>
                  )}
                  <header>
                    <div>
                      <span>{CATEGORY_LABELS[detail.category] ?? detail.category}</span>
                      <h4>{detail.displayName}</h4>
                      <p>{detail.description}</p>
                    </div>
                    <span className={`hardware-skill-status is-${detail.status.toLowerCase()}`}>
                      {statusLabel(detail.status)}
                    </span>
                  </header>

                  <dl className="hardware-skill-facts">
                    <div><dt>工作电压</dt><dd>{operatingVoltageLabel(detail.specification.electrical)}</dd></div>
                    {supplyRailsLabel(detail.specification.electrical) && (
                      <div><dt>外设电源轨</dt><dd>{supplyRailsLabel(detail.specification.electrical)}</dd></div>
                    )}
                    <div><dt>逻辑电平</dt><dd>{detail.specification.electrical.logicLevel} V</dd></div>
                    <div><dt>峰值电流</dt><dd>{detail.specification.electrical.peakCurrent} A</dd></div>
                    <div><dt>通信</dt><dd>{detail.specification.electrical.communicationProtocol}</dd></div>
                    <div><dt>I2C 地址</dt><dd>{detail.specification.electrical.i2cAddress ?? "不适用"}</dd></div>
                    <div><dt>兼容主控</dt><dd>{detail.specification.electrical.supportedMCUs.join("、") || "待确认"}</dd></div>
                  </dl>

                  <div className="hardware-skill-context-note" role="note">
                    <strong>三位工程师共享同一有效版本</strong>
                    <span>问题引导师、智能工程师和结构工程师从这里读取器件知识。</span>
                  </div>

                  {detail.diagnostics.map((diagnostic) => (
                    <p key={`${diagnostic.path}:${diagnostic.code}`} className="hardware-error" role={diagnostic.severity === "error" ? "alert" : "status"}>
                      {diagnostic.path}：{diagnostic.message}
                    </p>
                  ))}

                  {professionalMode && (
                    <div className="hardware-skill-advanced">
                      <dl>
                        <div><dt>项目目录</dt><dd>{detail.skillName}</dd></div>
                        <div><dt>验证来源</dt><dd>{sourceLabel(detail.sourceKind)}</dd></div>
                        <div><dt>内容版本</dt><dd title={detail.revision}>{detail.revision.slice(0, 12)}</dd></div>
                        <div><dt>规则</dt><dd>{detail.rules.length} 条声明式规则</dd></div>
                      </dl>
                      <ul aria-label="Hardware Skill 文件">
                        {detail.files.map((file) => <li key={file.path}>{file.path}</li>)}
                      </ul>
                      {onOpenSkillProject && (
                        <button
                          type="button"
                          aria-label={`打开 Skill 项目 ${detail.displayName}`}
                          onClick={() => onOpenSkillProject(summaryFromDetail(detail))}
                        >
                          打开 Skill 项目
                        </button>
                      )}
                    </div>
                  )}
                </>
              ) : (
                <p className="sidebar-placeholder">
                  从左侧选择一个{professionalMode ? " Hardware Skill" : "硬件知识项目"}。
                </p>
              )}
            </section>
          </div>
        </>
      )}
    </div>
  );
}

function summaryFromDetail(detail: HardwareSkillDetail): HardwareSkillSummary {
  const { files: _files, specification: _specification, rules: _rules, ...summary } = detail;
  return summary;
}

function statusLabel(status: HardwareSkillSummary["status"]): string {
  return {
    ACTIVE: "已启用",
    DRAFT: "草稿",
    ARCHIVED: "已归档",
    INVALID: "校验失败",
  }[status] ?? status;
}

function sourceLabel(sourceKind: HardwareSkillSummary["sourceKind"]): string {
  return {
    BUNDLED: "内置",
    MIGRATED: "旧硬件库迁移",
    UPLOAD: "上传资料",
    DIALOGUE: "对话补充",
    MANUAL: "手动维护",
  }[sourceKind] ?? sourceKind;
}
