import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import {
  CreatorCommand,
  CreatorStage,
  ProjectWorkspaceKind,
  type AuthAccount,
  type CodeRun,
  type CreatorStage as CreatorStageType,
  type CreatorWorkSummary,
  type CreatorWorkspace,
  type DevicePackageRevision,
} from "@zhangwen/contracts";
import { CenterChat, type CenterChatInteractionControls } from "../components/layout/CenterChat";
import {
  HardwareSelectionDialog,
  selectedProjectHardwareIds,
} from "../components/hardware/HardwareSelectionDialog";
import { SettingsDialog } from "../components/settings/SettingsDialog";
import { useLlmSettings } from "../hooks/useLlmSettings";
import { useProjects } from "../hooks/useProjects";
import { ApiError } from "../services/api";
import {
  executeCreatorCommand,
  getCreatorWorkspace,
  importCreatorDelivery,
  listCreatorDevicePackages,
} from "../services/creatorApi";
import { getCurrentCode } from "../services/projectsApi";
import { StableIntentKeyStore } from "../utils/stableIntentKey";
import { useCreatorWorks } from "./state/useCreatorWorks";

const IdeaSolutionStage = lazy(() => import("./stages/IdeaSolutionStage"));
const DigitalPrototypeStage = lazy(() => import("./stages/DigitalPrototypeStage"));
const StructureStage = lazy(() => import("./stages/StructureStage"));
const PhysicalRunStage = lazy(() => import("./stages/PhysicalRunStage"));
const CodeArtifactEditor = lazy(
  () => import("../components/floating/CodeArtifactEditor")
    .then((module) => ({ default: module.CodeArtifactEditor })),
);

const STAGE_LABELS: Record<CreatorStageType, string> = {
  IDEA_SOLUTION: "创意与方案",
  DIGITAL_PROTOTYPE: "数字原型",
  STRUCTURE_3D: "3D 结构",
  PHYSICAL_RUN: "实物运行",
};

type CreatorDrawer = "evidence" | "details" | "code" | "debug" | "parameters";
type CreatorIconName =
  | "archive"
  | "back"
  | "check"
  | "code"
  | "copy"
  | "debug"
  | "evidence"
  | "import"
  | "lock"
  | "package"
  | "parameters"
  | "plus"
  | "settings";

export function CreatorApp({
  account,
  onLogout,
}: {
  account?: AuthAccount;
  onLogout?: () => Promise<void> | void;
}) {
  const creator = useCreatorWorks();
  const llmSettings = useLlmSettings();
  const projects = useProjects(llmSettings.config?.defaultModel);
  const controlsRef = useRef<CenterChatInteractionControls | null>(null);
  const intentKeys = useRef(new StableIntentKeyStore("creator-app"));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [professionalMode, setProfessionalMode] = useState(false);
  const [busyMessage, setBusyMessage] = useState<string | null>(null);

  const openWork = async (workId: string) => {
    setBusyMessage("正在打开作品…");
    try {
      await controlsRef.current?.flushDraft();
      await projects.open(workId);
      await creator.open(workId);
    } finally {
      setBusyMessage(null);
    }
  };

  const createWork = async (name: string, initialIdea: string) => {
    setBusyMessage("正在建立作品…");
    try {
      const workspace = await creator.create({
        name: name.trim() || undefined,
        initialIdea,
        idempotencyKey: operationKey("create"),
      });
      await projects.open(workspace.workId);
    } finally {
      setBusyMessage(null);
    }
  };

  const archiveWork = async (work: CreatorWorkSummary, archived: boolean) => {
    setBusyMessage(archived ? "正在归档作品…" : "正在恢复作品…");
    try {
      const current = await getCreatorWorkspace(work.id);
      await executeCreatorCommand(work.id, CreatorCommand.ARCHIVE_WORK, {
        baseProjectVersion: current.workspace.projectVersion,
        idempotencyKey: operationKey(archived ? "archive" : "restore"),
        payload: { archived },
      });
      await creator.refresh();
    } finally {
      setBusyMessage(null);
    }
  };

  const duplicateWork = async (work: CreatorWorkSummary) => {
    setBusyMessage("正在复制作品…");
    try {
      const duplicated = await projects.duplicate(work.id, `${work.name}（副本）`);
      await creator.refresh();
      await creator.open(duplicated.project.id);
    } finally {
      setBusyMessage(null);
    }
  };

  const closeWork = async () => {
    await controlsRef.current?.flushDraft();
    creator.close();
  };

  const importDelivery = async (file: File) => {
    setBusyMessage("正在校验并导入作品包…");
    const intentScope = "import-delivery";
    const intentFingerprint = {
      fileName: file.name,
      fileSize: file.size,
      lastModified: file.lastModified,
    };
    try {
      const zipBase64 = await fileToBase64(file);
      const response = await importCreatorDelivery({
        zipBase64,
        idempotencyKey: intentKeys.current.key(intentScope, intentFingerprint),
      });
      intentKeys.current.complete(intentScope);
      await creator.refresh();
      await projects.open(response.workspace.workId);
      await creator.open(response.workspace.workId);
    } finally {
      setBusyMessage(null);
    }
  };

  return (
    <div className="creator-app">
      {creator.workspace ? (
        <CreatorWorkbench
          workspace={creator.workspace}
          projectWorkspace={projects.activeWorkspace}
          projectApi={projects}
          llmSettings={llmSettings}
          professionalMode={professionalMode}
          controlsRef={controlsRef}
          onBack={() => void closeWork()}
          onOpenSettings={() => setSettingsOpen(true)}
          onProfessionalModeChange={setProfessionalMode}
          onRefreshCreator={() => creator.open(creator.workspace!.workId)}
          onCancelJob={async (jobId) => {
            const current = creator.workspace;
            if (!current) return;
            const intentScope = `cancel-job:${current.workId}:${jobId}`;
            await creator.cancelJob(
              current.workId,
              jobId,
              intentKeys.current.key(intentScope, { jobId }),
            );
            intentKeys.current.complete(intentScope);
          }}
          onRetryJob={async (jobId) => {
            const current = creator.workspace;
            if (!current) return;
            const intentScope = `retry-job:${current.workId}:${jobId}`;
            await creator.retryJob(
              current.workId,
              jobId,
              intentKeys.current.key(intentScope, { jobId }),
            );
            intentKeys.current.complete(intentScope);
          }}
          onCommand={async (command, payload) => {
            const current = creator.workspace;
            if (!current) return;
            await creator.command(current.workId, command, {
              baseProjectVersion: current.projectVersion,
              idempotencyKey: operationKey(command.toLocaleLowerCase()),
              payload,
            });
          }}
        />
      ) : (
        <WorksHome
          account={account}
          works={creator.works}
          loading={creator.loading}
          error={creator.error}
          busyMessage={busyMessage}
          onCreate={createWork}
          onImport={importDelivery}
          onOpen={(workId) => void openWork(workId)}
          onDuplicate={(work) => void duplicateWork(work)}
          onArchive={(work, archived) => void archiveWork(work, archived)}
          onOpenSettings={() => setSettingsOpen(true)}
          onLogout={onLogout}
        />
      )}
      {busyMessage ? <div className="creator-toast" role="status">{busyMessage}</div> : null}
      {settingsOpen ? (
        <SettingsDialog
          config={llmSettings.config}
          models={llmSettings.models}
          saving={llmSettings.saving}
          testing={llmSettings.testing}
          message={llmSettings.message}
          error={llmSettings.error}
          professionalMode={professionalMode}
          showModeControl
          onProfessionalModeChange={setProfessionalMode}
          onSave={llmSettings.save}
          onClearKey={llmSettings.clearKey}
          onTest={llmSettings.test}
          onClose={() => setSettingsOpen(false)}
        />
      ) : null}
    </div>
  );
}

function WorksHome({
  account,
  works,
  loading,
  error,
  busyMessage,
  onCreate,
  onImport,
  onOpen,
  onDuplicate,
  onArchive,
  onOpenSettings,
  onLogout,
}: {
  account?: AuthAccount;
  works: CreatorWorkSummary[];
  loading: boolean;
  error: string | null;
  busyMessage: string | null;
  onCreate: (name: string, idea: string) => Promise<void>;
  onImport: (file: File) => Promise<void>;
  onOpen: (workId: string) => void;
  onDuplicate: (work: CreatorWorkSummary) => void;
  onArchive: (work: CreatorWorkSummary, archived: boolean) => void;
  onOpenSettings: () => void;
  onLogout?: () => Promise<void> | void;
}) {
  const [createOpen, setCreateOpen] = useState(false);
  const [importOpen, setImportOpen] = useState(false);
  const [catalogOpen, setCatalogOpen] = useState(false);
  const [showArchived, setShowArchived] = useState(false);
  const visible = works.filter((work) => showArchived ? Boolean(work.archivedAt) : !work.archivedAt);

  return (
    <main className="creator-home">
      <header className="creator-home-header">
        <a className="creator-brand" href="#creator-works" aria-label="掌问创作端首页">
          <span className="creator-brand-mark">问</span>
          <span><strong>掌问创作端</strong><small>让想法成为真实作品</small></span>
        </a>
        <div className="creator-home-actions">
          <button type="button" className="creator-home-catalog" aria-label="打开设备包目录" title="设备包目录" onClick={() => setCatalogOpen(true)}><CreatorIcon name="package" /><span>设备包目录</span></button>
          <button type="button" className="creator-home-import" aria-label="导入作品包" title="导入作品包" onClick={() => setImportOpen(true)}><CreatorIcon name="import" /><span>导入作品包</span></button>
          <button type="button" className="creator-primary-button creator-header-create" aria-label="新建作品" title="新建作品" onClick={() => setCreateOpen(true)}><CreatorIcon name="plus" /><span>新建作品</span></button>
          <span>{account?.displayName ?? "本地创作者"}</span>
          <button type="button" aria-label="打开设置" title="设置" onClick={onOpenSettings}><CreatorIcon name="settings" /></button>
          {onLogout ? <button type="button" className="creator-logout-button" onClick={() => void onLogout()}>退出</button> : null}
        </div>
      </header>
      <section className="creator-home-intro" id="creator-works">
        <div>
          <h1>我的作品</h1>
          <p>从一个想法开始，把它做成可验证、可运行、可复现的真实作品。</p>
        </div>
        <button type="button" className="creator-primary-button creator-intro-create" onClick={() => setCreateOpen(true)}><CreatorIcon name="plus" />新建作品</button>
      </section>
      <nav className="creator-work-filter" aria-label="作品筛选">
        <button type="button" className={!showArchived ? "active" : ""} onClick={() => setShowArchived(false)}>进行中的作品</button>
        <button type="button" className={showArchived ? "active" : ""} onClick={() => setShowArchived(true)}>已归档</button>
      </nav>
      {error ? <div className="creator-error" role="alert"><strong>作品加载失败</strong><span>{error}</span></div> : null}
      {loading ? <div className="creator-loading" role="status">正在读取本地作品…</div> : null}
      {!loading && visible.length === 0 && showArchived ? (
        <section className="creator-home-empty">
          <CreatorIcon name="archive" />
          <h2>还没有归档作品</h2>
          <p>归档后的作品会保留全部对话、版本和证据。</p>
        </section>
      ) : (
        <section className="creator-work-grid" aria-label="作品列表">
          {visible.map((work) => (
            <article className="creator-work-card" key={work.id}>
              <button type="button" className="creator-work-card-main" onClick={() => onOpen(work.id)} disabled={Boolean(busyMessage)}>
                <WorkPreview work={work} />
                <div className="creator-work-card-copy">
                  <span>{phaseLabel(work.phase)}</span>
                  <h2>{work.name}</h2>
                  <p>{work.initialIdea}</p>
                </div>
                <footer>
                  <span className={`creator-work-badge tone-${workTone(work)}`}>等级 {work.verificationLevel}/6 · {work.verificationLabel}</span>
                  <span>{formatUpdatedAt(work.updatedAt)}</span>
                </footer>
              </button>
              <div className="creator-work-card-actions">
                <span>下一步：{work.nextActionLabel}</span>
                <div>
                  {!work.archivedAt ? <button type="button" onClick={() => onDuplicate(work)}><CreatorIcon name="copy" />复制</button> : null}
                  <button type="button" onClick={() => onArchive(work, !work.archivedAt)}><CreatorIcon name="archive" />{work.archivedAt ? "恢复" : "归档"}</button>
                </div>
              </div>
            </article>
          ))}
          {!showArchived ? (
            <button type="button" className="creator-new-work-card" onClick={() => setCreateOpen(true)}>
              <span><CreatorIcon name="plus" /></span>
              <strong>开始一个新作品</strong>
              <small>直接告诉掌问你想做什么</small>
            </button>
          ) : null}
        </section>
      )}
      {createOpen ? <CreateWorkDialog onClose={() => setCreateOpen(false)} onCreate={async (name, idea) => {
        await onCreate(name, idea);
        setCreateOpen(false);
      }} /> : null}
      {importOpen ? <ImportWorkDialog onClose={() => setImportOpen(false)} onImport={async (file) => {
        await onImport(file);
        setImportOpen(false);
      }} /> : null}
      {catalogOpen ? <DevicePackageCatalogDialog onClose={() => setCatalogOpen(false)} /> : null}
    </main>
  );
}

function CreateWorkDialog({
  onClose,
  onCreate,
}: {
  onClose: () => void;
  onCreate: (name: string, idea: string) => Promise<void>;
}) {
  const [name, setName] = useState("");
  const [idea, setIdea] = useState("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialog = useCreatorDialogFocus<HTMLFormElement>(true, onClose);
  return (
    <div className="creator-modal-backdrop">
      <form ref={dialog.dialogRef} className="creator-modal" role="dialog" aria-modal="true" aria-labelledby="create-work-title" onKeyDown={(event) => {
        if (saving && event.key === "Escape") return;
        dialog.onDialogKeyDown(event);
      }} onSubmit={(event) => {
        event.preventDefault();
        setSaving(true);
        setError(null);
        void onCreate(name, idea).catch((reason: unknown) => {
          setError(reason instanceof Error ? reason.message : "作品创建失败。" );
          setSaving(false);
        });
      }}>
        <header><span>新作品</span><h2 id="create-work-title">你想做什么？</h2><p>先说想法即可，名称可以留空由掌问整理。</p></header>
        <label><span>作品名称（可选）</span><input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} placeholder="例如：会照顾植物的桌面伙伴" /></label>
        <label><span>我的想法</span><textarea required value={idea} onChange={(event) => setIdea(event.target.value)} maxLength={4000} placeholder="描述使用场景、希望它如何表现，暂时不需要懂硬件。" /></label>
        {error ? <p className="creator-error" role="alert">{error}</p> : null}
        <footer><button type="button" onClick={onClose}>取消</button><button type="submit" className="creator-primary-button" disabled={saving || !idea.trim()}>{saving ? "正在创建…" : "开始创作"}</button></footer>
      </form>
    </div>
  );
}

function ImportWorkDialog({
  onClose,
  onImport,
}: {
  onClose: () => void;
  onImport: (file: File) => Promise<void>;
}) {
  const [file, setFile] = useState<File | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dialog = useCreatorDialogFocus<HTMLFormElement>(true, onClose);
  return (
    <div className="creator-modal-backdrop">
      <form ref={dialog.dialogRef} className="creator-modal" role="dialog" aria-modal="true" aria-labelledby="import-work-title" onKeyDown={(event) => {
        if (saving && event.key === "Escape") return;
        dialog.onDialogKeyDown(event);
      }} onSubmit={(event) => {
        event.preventDefault();
        if (!file) return;
        setSaving(true);
        setError(null);
        void onImport(file).catch((reason: unknown) => {
          setError(reason instanceof Error ? reason.message : "作品包导入失败。");
          setSaving(false);
        });
      }}>
        <header><span>受控复现</span><h2 id="import-work-title">导入作品包</h2><p>导入会校验路径、大小、Hash 与隐私；原作品的验证等级不会继承。</p></header>
        <label><span>作品包文件</span><input type="file" accept=".zip,.zwcreator.zip,application/zip" required onChange={(event) => setFile(event.target.files?.[0] ?? null)} /></label>
        <p>导入与后续复现将由当前已认证账户签署；更改显示名不会改变签署主体。</p>
        {error ? <p className="creator-error" role="alert">{error}</p> : null}
        <footer><button type="button" onClick={onClose}>取消</button><button type="submit" className="creator-primary-button" disabled={saving || !file}>{saving ? "正在校验…" : "校验并导入"}</button></footer>
      </form>
    </div>
  );
}

function DevicePackageCatalogDialog({ onClose }: { onClose: () => void }) {
  const [packages, setPackages] = useState<DevicePackageRevision[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const dialog = useCreatorDialogFocus<HTMLElement>(true, onClose);
  useEffect(() => {
    let active = true;
    void listCreatorDevicePackages()
      .then((response) => {
        if (active) setPackages(response.packages);
      })
      .catch((reason: unknown) => {
        if (active) setError(reason instanceof Error ? reason.message : "设备包目录加载失败。");
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);
  return (
    <div className="creator-modal-backdrop">
      <section ref={dialog.dialogRef} className="creator-modal creator-catalog-modal" role="dialog" aria-modal="true" aria-labelledby="device-package-title" onKeyDown={dialog.onDialogKeyDown}>
        <header>
          <span>设备包目录</span>
          <h2 id="device-package-title">可验证的硬件能力</h2>
          <p>目录只展示已安装且能进入掌问项目流程的设备包，不把普通串口设备伪装成受支持硬件。</p>
        </header>
        {loading ? <div className="creator-loading" role="status">正在读取设备包目录…</div> : null}
        {error ? <div className="creator-error" role="alert">{error}</div> : null}
        {!loading && !error ? (
          <div className="creator-catalog-list">
            {packages.map((item) => (
              <article key={`${item.id}-${item.version}`}>
                <div><span>{item.boardProfileId}</span><h3>{item.displayName}</h3><small>版本 {item.version} · {item.source}</small></div>
                <dl>
                  <div><dt>运行方式</dt><dd>{item.deploymentChannels.join(" / ") || "未声明"}</dd></div>
                  <div><dt>仿真能力</dt><dd>{item.simulationModes.join(" / ") || "仅真机"}</dd></div>
                  <div><dt>功能范围</dt><dd>{item.capabilities.join(" / ") || "待补充"}</dd></div>
                </dl>
              </article>
            ))}
            {packages.length === 0 ? <div className="creator-home-empty"><h3>还没有可用设备包</h3><p>安装并校验设备包后，它会出现在这里。</p></div> : null}
          </div>
        ) : null}
        <footer><button type="button" onClick={onClose}>关闭</button></footer>
      </section>
    </div>
  );
}

function CreatorWorkbench({
  workspace,
  projectWorkspace,
  projectApi,
  llmSettings,
  professionalMode,
  controlsRef,
  onBack,
  onOpenSettings,
  onProfessionalModeChange,
  onRefreshCreator,
  onCancelJob,
  onRetryJob,
  onCommand,
}: {
  workspace: CreatorWorkspace;
  projectWorkspace: ReturnType<typeof useProjects>["activeWorkspace"];
  projectApi: ReturnType<typeof useProjects>;
  llmSettings: ReturnType<typeof useLlmSettings>;
  professionalMode: boolean;
  controlsRef: React.MutableRefObject<CenterChatInteractionControls | null>;
  onBack: () => void;
  onOpenSettings: () => void;
  onProfessionalModeChange: (enabled: boolean) => void;
  onRefreshCreator: () => Promise<unknown> | unknown;
  onCancelJob: (jobId: string) => Promise<void>;
  onRetryJob: (jobId: string) => Promise<void>;
  onCommand: (command: CreatorCommand, payload: Record<string, unknown>) => Promise<void>;
}) {
  const [activeStage, setActiveStage] = useState<CreatorStageType>(workspace.activeStage);
  const [drawer, setDrawer] = useState<CreatorDrawer | null>(null);
  const [focusMode, setFocusMode] = useState(false);
  const [hardwareSelectionOpen, setHardwareSelectionOpen] = useState(false);
  const drawerDialog = useCreatorDialogFocus<HTMLElement>(drawer !== null, () => setDrawer(null));
  const workIdRef = useRef(workspace.workId);
  const workspaceStageRef = useRef(workspace.activeStage);
  useEffect(() => {
    if (workIdRef.current !== workspace.workId) {
      workIdRef.current = workspace.workId;
      workspaceStageRef.current = workspace.activeStage;
      setActiveStage(workspace.activeStage);
      setFocusMode(false);
      return;
    }
    if (workspaceStageRef.current !== workspace.activeStage) {
      workspaceStageRef.current = workspace.activeStage;
      setActiveStage(workspace.activeStage);
    }
  }, [workspace.activeStage, workspace.workId]);
  useEffect(() => {
    if (activeStage !== CreatorStage.DIGITAL_PROTOTYPE) setFocusMode(false);
  }, [activeStage]);
  const models = useMemo(
    () => llmSettings.config
      ? llmSettings.models.filter((model) => model.provider === llmSettings.config?.provider)
      : llmSettings.models,
    [llmSettings.config, llmSettings.models],
  );
  const conversations = (projectWorkspace?.expertConversations ?? []).filter((item) => !item.archivedLegacyThread);
  const selectedExpertId = projectWorkspace?.project.activeExpertId ?? conversations[0]?.projectExpertId ?? null;
  const context = creatorChatContext(activeStage, workspace.projectVersion);

  return (
    <main className="creator-workbench">
      <header className="creator-workbench-header">
        <div className="creator-workbench-identity">
          <button type="button" className="creator-back-button" aria-label="返回我的作品" title="返回我的作品" onClick={onBack}><CreatorIcon name="back" /></button>
          <div><h1>{workspace.name}</h1><p>{phaseLabel(workspace.phase)} · {STAGE_LABELS[activeStage]}</p></div>
        </div>
        <div className="creator-level-summary">
          <div className="creator-level-ring" aria-label={`验证等级 ${workspace.verificationLevel}`} style={{ "--creator-level": workspace.verificationLevel } as React.CSSProperties}><strong>{workspace.verificationLevel}</strong><span>/ 6</span></div>
          <div><strong>验证等级</strong><span>{workspace.verificationLabel}</span></div>
        </div>
        <div className="creator-progress-summary">
          <div><span>建议下一步</span><strong>{workspace.nextAction.label}</strong></div>
          {workspace.nextAction.stage !== activeStage ? (
            <button type="button" className="creator-next-button" onClick={() => setActiveStage(workspace.nextAction.stage)}>
              打开{STAGE_LABELS[workspace.nextAction.stage]}
            </button>
          ) : null}
          <button
            type="button"
            className={`creator-mode-toggle ${professionalMode ? "is-active" : ""}`}
            role="switch"
            aria-checked={professionalMode}
            aria-label="三师专业模式"
            title={professionalMode ? "关闭三师专业模式" : "开启三师专业模式"}
            onClick={() => onProfessionalModeChange(!professionalMode)}
          >
            <span>三师</span>
            <strong>{professionalMode ? "专业" : "普通"}</strong>
          </button>
          <button type="button" className="creator-icon-button" aria-label="查看证据与交付" title="证据与交付" onClick={() => setDrawer("evidence")}><CreatorIcon name="evidence" /></button>
          <button type="button" className="creator-icon-button" aria-label="打开设置" title="设置" onClick={onOpenSettings}><CreatorIcon name="settings" /></button>
        </div>
      </header>
      <div className={`creator-workbench-body${focusMode ? " is-stage-focused" : ""}`}>
        <section className="creator-chat-pane" aria-label="与掌问对话">
          <header><strong>与掌问一起创作</strong><span>{professionalMode ? "三师专业模式" : "对话主入口"}</span></header>
          <div className="creator-chat-mount">
            <CenterChat
              rootElement="div"
              config={llmSettings.config}
              workspace={projectWorkspace}
              selectedExpertId={selectedExpertId}
              models={models}
              professionalMode={professionalMode}
              creatorWorkflow
              draftSaving={projectApi.draftSaving}
              draftSaveError={projectApi.draftSaveError}
              workspaceContext={context}
              onOpenSettings={onOpenSettings}
              onOpenArtifact={() => setDrawer("details")}
              onOpenHardwareSelection={() => setHardwareSelectionOpen(true)}
              onSaveDraft={projectApi.saveDraft}
              onSelectExpert={(expertId) => { void projectApi.activateExpert(workspace.projectId, expertId); }}
              onAddExpert={async (expertType) => {
                const updated = await projectApi.addExpert(workspace.projectId, expertType, true);
                const expert = updated.experts?.find(
                  (item) => item.expertType === expertType && !item.removedAt,
                );
                return updated.expertConversations?.find(
                  (item) => item.projectExpertId === expert?.id,
                ) ?? null;
              }}
              onSelectModel={projectApi.setModel}
              onReloadProject={async (projectId) => {
                await projectApi.loadWorkspace(projectId);
                await onRefreshCreator();
              }}
              onDismissPendingItem={(pendingId) => projectApi.dismissPending(workspace.projectId, pendingId)}
              onInteractionControlsChange={(controls) => { controlsRef.current = controls; }}
            />
          </div>
        </section>
        <section className="creator-stage-pane" aria-label="作品阶段工作区">
          <div className="creator-stagebar">
            <nav className="creator-stage-nav" aria-label="作品阶段">
              {workspace.stages.map((item) => (
                <button type="button" key={item.stage} className={`${activeStage === item.stage ? "active" : ""} status-${item.status.toLowerCase()}`} aria-current={activeStage === item.stage ? "step" : undefined} aria-label={`${item.label}，${stageStatusLabel(item.status)}`} title={`${item.label} · ${stageStatusLabel(item.status)}`} onClick={() => setActiveStage(item.stage)}>
                  <span><strong>{item.label}</strong><small>{stageStatusLabel(item.status)}</small></span>
                  {item.status === "PASSED" ? <CreatorIcon name="check" /> : item.status === "BLOCKED" ? <CreatorIcon name="lock" /> : null}
                </button>
              ))}
            </nav>
            <div className="creator-workspace-tools" aria-label="作品工具">
              <button type="button" aria-label="打开方案详情" title="方案详情" onClick={() => setDrawer("details")}><CreatorIcon name="package" /><span>方案详情</span></button>
              <button type="button" aria-label="打开代码工作区" title="代码" onClick={() => setDrawer("code")}><CreatorIcon name="code" /><span>代码</span></button>
              <button type="button" aria-label="打开图形调试" title="图形调试" onClick={() => setDrawer("debug")}><CreatorIcon name="debug" /><span>图形调试</span></button>
              <button type="button" aria-label="打开参数版本" title="参数版本" onClick={() => setDrawer("parameters")}><CreatorIcon name="parameters" /><span>参数版本</span></button>
              <button type="button" aria-label="打开证据与交付" title="证据与交付" onClick={() => setDrawer("evidence")}><CreatorIcon name="evidence" /><span>证据与交付</span></button>
            </div>
          </div>
          <div className="creator-stage-scroll">
            <Suspense fallback={<div className="creator-loading">正在加载阶段工作区…</div>}>
              <CreatorStageView
                stage={activeStage}
                workspace={workspace}
                projectWorkspace={projectWorkspace}
                professionalMode={professionalMode}
                focusMode={focusMode}
                onFocusModeChange={setFocusMode}
                onCommand={onCommand}
                onOpenHardwareSelection={() => setHardwareSelectionOpen(true)}
              />
            </Suspense>
          </div>
        </section>
      </div>
      {drawer ? (
        <div className="creator-drawer-backdrop" onClick={() => setDrawer(null)}>
          <aside ref={drawerDialog.dialogRef} className={`creator-drawer ${drawer === "code" ? "creator-drawer-code" : ""}`} role="dialog" aria-modal="true" aria-label={drawerTitle(drawer)} onKeyDown={drawerDialog.onDialogKeyDown} onClick={(event) => event.stopPropagation()}>
            <header><div><span>当前作品</span><h2>{drawerTitle(drawer)}</h2></div><button type="button" onClick={() => setDrawer(null)}>关闭</button></header>
            <CreatorDrawerView
              drawer={drawer}
              workspace={workspace}
              professionalMode={professionalMode}
              onCancelJob={onCancelJob}
              onRetryJob={onRetryJob}
              onRefreshCreator={onRefreshCreator}
              onOpenStage={(stage) => {
                setActiveStage(stage);
                setDrawer(null);
              }}
            />
          </aside>
        </div>
      ) : null}
      <HardwareSelectionDialog
        open={hardwareSelectionOpen}
        title="为当前方案选择电子器件"
        description="选择会真实保存到作品；掌问会据此检查 BOM、IO、供电和仿真能力。"
        initialSelectedIds={selectedProjectHardwareIds(projectWorkspace?.sharedContext?.confirmedFacts)}
        confirmLabel="保存到作品"
        onClose={() => setHardwareSelectionOpen(false)}
        onConfirm={async (selectedHardwareIds) => {
          const response = await projectApi.setHardware(workspace.projectId, selectedHardwareIds);
          await onRefreshCreator();
          return { warnings: response.selectedHardwareWarnings };
        }}
      />
    </main>
  );
}

function CreatorStageView({
  stage,
  workspace,
  projectWorkspace,
  professionalMode,
  focusMode,
  onFocusModeChange,
  onCommand,
  onOpenHardwareSelection,
}: {
  stage: CreatorStageType;
  workspace: CreatorWorkspace;
  projectWorkspace: ReturnType<typeof useProjects>["activeWorkspace"];
  professionalMode: boolean;
  focusMode: boolean;
  onFocusModeChange: (focused: boolean) => void;
  onCommand: (command: CreatorCommand, payload: Record<string, unknown>) => Promise<void>;
  onOpenHardwareSelection: () => void;
}) {
  switch (stage) {
    case CreatorStage.IDEA_SOLUTION: return <IdeaSolutionStage workspace={workspace} professionalMode={professionalMode} onCommand={onCommand} onOpenHardwareSelection={onOpenHardwareSelection} />;
    case CreatorStage.DIGITAL_PROTOTYPE: return <DigitalPrototypeStage workspace={workspace} professionalMode={professionalMode} focusMode={focusMode} onFocusModeChange={onFocusModeChange} onCommand={onCommand} />;
    case CreatorStage.STRUCTURE_3D: return <StructureStage workspace={workspace} professionalMode={professionalMode} onCommand={onCommand} />;
    case CreatorStage.PHYSICAL_RUN: return <PhysicalRunStage workspace={workspace} projectWorkspace={projectWorkspace} professionalMode={professionalMode} onCommand={onCommand} />;
  }
}

function CreatorDrawerView({
  drawer,
  workspace,
  professionalMode,
  onCancelJob,
  onRetryJob,
  onRefreshCreator,
  onOpenStage,
}: {
  drawer: CreatorDrawer;
  workspace: CreatorWorkspace;
  professionalMode: boolean;
  onCancelJob: (jobId: string) => Promise<void>;
  onRetryJob: (jobId: string) => Promise<void>;
  onRefreshCreator: () => Promise<unknown> | unknown;
  onOpenStage: (stage: CreatorStageType) => void;
}) {
  if (drawer === "evidence") return <EvidenceDrawer workspace={workspace} />;
  if (drawer === "details") return <DetailsDrawer workspace={workspace} />;
  if (drawer === "code") {
    return (
      <CreatorCodeDrawer
        workspace={workspace}
        professionalMode={professionalMode}
        onCancelJob={onCancelJob}
        onRetryJob={onRetryJob}
        onRefreshCreator={onRefreshCreator}
        onOpenDigitalPrototype={() => onOpenStage(CreatorStage.DIGITAL_PROTOTYPE)}
      />
    );
  }
  if (drawer === "debug") {
    return (
      <div className="creator-drawer-list">
        <article><span className="creator-drawer-kicker">图形调试</span><h3>由当前方案自动生成</h3><p>传感器输入、执行器状态、故障注入和验收场景都在数字原型中联动；真机阶段只开放安全范围内的校准和控制。</p></article>
        <article><h3>当前验证边界</h3><p>{workspace.currentSolution?.simulation ?? "确认方案后才会声明可仿真的能力，未实现的协议不会显示为可调试。"}</p></article>
        <button type="button" className="creator-drawer-primary" onClick={() => onOpenStage(CreatorStage.DIGITAL_PROTOTYPE)}>打开图形调试</button>
      </div>
    );
  }
  const revisions = workspace.parameterRevisions;
  return (
    <div className="creator-drawer-list">
      <article><span className="creator-drawer-kicker">不可变修订</span><h3>参数版本</h3><p>参数先保存为项目版本，再明确应用到仿真或同步到真机；凭据不会进入版本。</p></article>
      {revisions.length ? revisions.map((revision) => (
        <article key={revision.id} className="creator-parameter-revision">
          <span>P{revision.revision}</span>
          <strong>{revision.label}</strong>
          <p>{Object.entries(revision.values).map(([key, value]) => `${key}=${String(value)}`).join(" · ") || "空参数集"}</p>
          <small>{revision.boardId} · 档案 {revision.profileRevision}</small>
        </article>
      )) : <div className="creator-drawer-empty"><h3>还没有参数版本</h3><p>在数字原型的图形调试区保存第一份参数后，这里会显示版本绑定。</p></div>}
      <button type="button" className="creator-drawer-primary" onClick={() => onOpenStage(CreatorStage.DIGITAL_PROTOTYPE)}>进入数字原型管理参数</button>
    </div>
  );
}

function CreatorCodeDrawer({
  workspace,
  professionalMode,
  onCancelJob,
  onRetryJob,
  onRefreshCreator,
  onOpenDigitalPrototype,
}: {
  workspace: CreatorWorkspace;
  professionalMode: boolean;
  onCancelJob: (jobId: string) => Promise<void>;
  onRetryJob: (jobId: string) => Promise<void>;
  onRefreshCreator: () => Promise<unknown> | unknown;
  onOpenDigitalPrototype: () => void;
}) {
  const [codeRun, setCodeRun] = useState<CodeRun | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const jobs = workspace.jobs.filter(
    (job) => job.kind === "CODE_PREPARATION" || job.kind === "DIGITAL_PROTOTYPE",
  );

  useEffect(() => {
    let canceled = false;
    setLoading(true);
    setLoadError(null);
    void getCurrentCode(workspace.projectId)
      .then((response) => {
        if (!canceled) setCodeRun(response.codeRun);
      })
      .catch((reason: unknown) => {
        if (canceled) return;
        setCodeRun(null);
        if (!(reason instanceof ApiError && reason.status === 404)) {
          setLoadError(reason instanceof Error ? reason.message : "加载当前代码失败。");
        }
      })
      .finally(() => {
        if (!canceled) setLoading(false);
      });
    return () => {
      canceled = true;
    };
  }, [refreshKey, workspace.projectId]);

  if (loading) {
    return <div className="creator-code-loading" role="status">正在读取当前代码版本…</div>;
  }

  if (loadError) {
    return (
      <div className="creator-drawer-list">
        <div className="creator-error" role="alert">{loadError}</div>
        <button type="button" className="creator-drawer-primary" onClick={() => setRefreshKey((value) => value + 1)}>重新加载代码</button>
      </div>
    );
  }

  if (!codeRun) {
    return (
      <div className="creator-drawer-list">
        <div className="creator-drawer-empty creator-code-empty">
          <span className="creator-drawer-kicker">真实产物状态</span>
          <h3>尚未生成代码</h3>
          <p>方案确认后，代码准备任务会自动生成部署变体并执行静态与语法检查。无需在对话中再次要求智能工程师生成；请查看下方任务状态，失败时可直接重试。</p>
        </div>
        {workspace.currentSolution ? (
          <article>
            <span className="creator-drawer-kicker">代码依据 · 方案 S{workspace.currentSolution.revision}</span>
            <h3>{workspace.currentSolution.software}</h3>
            <p>{workspace.currentSolution.logic}</p>
          </article>
        ) : null}
        {jobs.map((job) => (
          <article key={job.id} className="creator-job-summary">
            <span>{job.kind === "CODE_PREPARATION" ? "代码准备任务" : "数字原型任务"}</span>
            <strong>{jobStatusLabel(job.status)} · {job.progress}%</strong>
            <small>{job.message ?? `绑定方案 ${job.solutionRevisionId}`}</small>
            {job.status === "QUEUED"
            || job.status === "RUNNING"
            || job.status === "WAITING_CONFIRMATION" ? (
              <button type="button" onClick={() => void onCancelJob(job.id)}>取消任务</button>
            ) : null}
            {job.status === "FAILED"
            && job.result?.error
            && typeof job.result.error === "object"
            && "retryable" in job.result.error
            && job.result.error.retryable === true ? (
              <button type="button" onClick={() => void onRetryJob(job.id)}>重试生成</button>
            ) : null}
          </article>
        ))}
        <button type="button" className="creator-drawer-primary" onClick={onOpenDigitalPrototype}>进入数字原型查看准备状态</button>
      </div>
    );
  }

  return (
    <div className="creator-code-workspace">
      <div className="creator-drawer-note">
        <strong>真实代码版本 v{codeRun.version}</strong>
        <span>{codeRun.files.length} 个文件 · {codeRun.runtime} · {codeRun.status}。保存修改会创建不可变新版本，不覆盖历史代码。</span>
      </div>
      <Suspense fallback={<div className="creator-code-loading" role="status">正在加载代码编辑器…</div>}>
        <CodeArtifactEditor
          projectId={workspace.projectId}
          codeRunId={codeRun.id}
          readOnly={!professionalMode}
          onCodeRunChanged={async (next) => {
            setCodeRun(next);
            await onRefreshCreator();
          }}
        />
      </Suspense>
    </div>
  );
}

function EvidenceDrawer({ workspace }: { workspace: CreatorWorkspace }) {
  return (
    <div className="creator-drawer-list">
      <article className="creator-evidence-overview">
        <div className="creator-level-ring" aria-label={`验证等级 ${workspace.verificationLevel}`} style={{ "--creator-level": workspace.verificationLevel } as React.CSSProperties}><strong>{workspace.verificationLevel}</strong><span>/ 6</span></div>
        <div><span className="creator-drawer-kicker">当前证据覆盖</span><h3>{workspace.verificationLabel}</h3><p>验证等级只由已记录证据推进，不由对话文本自动声明。</p></div>
      </article>
      {workspace.evidence.length ? workspace.evidence.map((item) => (
        <article key={item.id}>
          <span className={`creator-evidence-state state-${item.status.toLowerCase()}`}>{item.status === "CURRENT" ? "当前有效" : item.status === "STALE" ? "已过期" : item.status === "FAILED" ? "未通过" : "已被替代"}</span>
          <h3>{evidenceLabel(item.kind)}</h3>
          <p>{item.summary}</p>
          <small>{new Date(item.recordedAt).toLocaleString("zh-CN")}</small>
          {item.invalidationReason ? <em>{item.invalidationReason}</em> : null}
        </article>
      )) : <div className="creator-drawer-empty"><h3>还没有验证证据</h3><p>目标确认、静态检查、仿真和真机行为会依次形成可追溯证据。</p></div>}
    </div>
  );
}

function DetailsDrawer({ workspace }: { workspace: CreatorWorkspace }) {
  const solution = workspace.currentSolution;
  return (
    <div className="creator-drawer-list">
      <article><span className="creator-drawer-kicker">作品目标</span><h3>{workspace.currentGoal?.statement ?? "待整理"}</h3><p>{workspace.currentGoal?.observableBehavior ?? "掌问会先把想法整理成可观察行为。"}</p></article>
      <article><span className="creator-drawer-kicker">当前方案</span><h3>{solution ? `方案 S${solution.revision}` : "目标确认后生成"}</h3><p>{solution?.summary ?? "当前还没有已确认方案。"}</p></article>
      {solution ? (
        <>
          <article><h3>硬件与结构</h3><p>{solution.hardware}</p><p>{solution.structure}</p></article>
          <article><h3>BOM</h3>{solution.bom.length ? <ul>{solution.bom.map((item) => <li key={item.componentId}>{item.name} × {item.quantity}</li>)}</ul> : <p>当前方案没有器件清单。</p>}</article>
          <article><h3>IO Map</h3>{solution.ioMap.length ? <ul>{solution.ioMap.map((item) => <li key={`${item.signal}-${item.pin}`}>{item.signal} → {item.pin}：{item.purpose}</li>)}</ul> : <p>当前方案没有引脚映射。</p>}</article>
          <article><h3>安全与仿真边界</h3><p>{solution.safety}</p><p>{solution.simulation}</p></article>
        </>
      ) : null}
      <article><h3>验收场景</h3>{workspace.acceptanceScenarios.length ? <ul>{workspace.acceptanceScenarios.map((item) => <li key={item.id}>{item.title}{item.required ? "（必需）" : ""}</li>)}</ul> : <p>方案确认后生成项目特有验收场景。</p>}</article>
    </div>
  );
}

function creatorChatContext(stage: CreatorStageType, projectVersion: number) {
  if (stage === CreatorStage.DIGITAL_PROTOTYPE) return { workspaceKind: ProjectWorkspaceKind.ENGINEERING, workspaceView: "validation", projectVersion } as const;
  if (stage === CreatorStage.STRUCTURE_3D) return { workspaceKind: ProjectWorkspaceKind.STRUCTURE, workspaceView: "cad", projectVersion } as const;
  if (stage === CreatorStage.PHYSICAL_RUN) return { workspaceKind: ProjectWorkspaceKind.ENGINEERING, workspaceView: "device", projectVersion } as const;
  return { workspaceKind: ProjectWorkspaceKind.OVERVIEW, workspaceView: "overview", projectVersion } as const;
}

function stageStatusLabel(status: CreatorWorkspace["stages"][number]["status"]): string {
  return { NOT_STARTED: "未开始", ACTIVE: "进行中", READY: "可查看", PASSED: "已通过", BLOCKED: "有前置条件", NOT_APPLICABLE: "不适用" }[status];
}

function phaseLabel(phase: CreatorWorkspace["phase"]): string {
  return {
    IDEA: "整理创意",
    GOAL_REVIEW: "确认目标",
    SOLUTION_REVIEW: "确认方案",
    DIGITAL_BUILDING: "构建数字原型",
    SIMULATING: "运行功能仿真",
    SIMULATION_PASSED: "仿真已通过",
    DEVICE_CONNECTED: "设备已连接",
    DEPLOYED: "代码已部署",
    PHYSICAL_VALIDATING: "真机验收中",
    PHYSICAL_PASSED: "真机已通过",
    ACCEPTED: "作品已验收",
    DELIVERED: "作品已交付",
  }[phase];
}

function jobStatusLabel(status: CreatorWorkspace["jobs"][number]["status"]): string {
  return {
    QUEUED: "已排队",
    RUNNING: "进行中",
    WAITING_CONFIRMATION: "等待确认",
    SUCCEEDED: "已完成",
    FAILED: "失败",
    CANCELED: "已取消",
  }[status];
}

function evidenceLabel(kind: CreatorWorkspace["evidence"][number]["kind"]): string {
  return { GOAL_CONFIRMATION: "目标确认", STATIC_VALIDATION: "静态检查", SIMULATION: "功能仿真", DEVICE_CONNECTION: "设备连接", DEPLOYMENT: "部署回读", PHYSICAL_BEHAVIOR: "真机行为", USER_ACCEPTANCE: "用户验收", REPRODUCTION: "复现验证", STRUCTURE_CHECK: "结构检查" }[kind];
}

function operationKey(prefix: string): string {
  const value = globalThis.crypto?.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(36).slice(2)}`;
  return `creator-${prefix}-${value}`;
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  for (let offset = 0; offset < bytes.length; offset += 0x8000) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 0x8000));
  }
  return globalThis.btoa(binary);
}

const CREATOR_DIALOG_FOCUSABLE = [
  "button:not([disabled])",
  "input:not([disabled])",
  "textarea:not([disabled])",
  "select:not([disabled])",
  "a[href]",
  "[tabindex]:not([tabindex='-1'])",
].join(",");

function useCreatorDialogFocus<T extends HTMLElement>(active: boolean, onClose: () => void) {
  const dialogRef = useRef<T | null>(null);
  const restoreFocusRef = useRef<HTMLElement | null>(null);
  const closeRef = useRef(onClose);
  closeRef.current = onClose;

  useEffect(() => {
    if (!active) return;
    restoreFocusRef.current = document.activeElement instanceof HTMLElement
      ? document.activeElement
      : null;
    const dialogRoot = dialogRef.current;
    const overlay = dialogRoot?.parentElement ?? null;
    const backgroundSiblings = overlay?.parentElement
      ? [...overlay.parentElement.children].filter((element): element is HTMLElement => (
        element instanceof HTMLElement && element !== overlay
      ))
      : [];
    const alreadyInert = new Set(backgroundSiblings.filter((element) => element.hasAttribute("inert")));
    backgroundSiblings.forEach((element) => element.setAttribute("inert", ""));
    creatorDialogFocusable(dialogRef.current)[0]?.focus();
    return () => {
      backgroundSiblings.forEach((element) => {
        if (!alreadyInert.has(element)) element.removeAttribute("inert");
      });
      const restoreTarget = restoreFocusRef.current;
      restoreFocusRef.current = null;
      if (restoreTarget?.isConnected) restoreTarget.focus();
    };
  }, [active]);

  const onDialogKeyDown = (event: React.KeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.preventDefault();
      closeRef.current();
      return;
    }
    if (event.key !== "Tab") return;
    const focusable = creatorDialogFocusable(dialogRef.current);
    if (!focusable.length) {
      event.preventDefault();
      dialogRef.current?.focus();
      return;
    }
    const first = focusable[0]!;
    const last = focusable[focusable.length - 1]!;
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault();
      last.focus();
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault();
      first.focus();
    }
  };

  return { dialogRef, onDialogKeyDown };
}

function creatorDialogFocusable(root: HTMLElement | null): HTMLElement[] {
  if (!root) return [];
  return [...root.querySelectorAll<HTMLElement>(CREATOR_DIALOG_FOCUSABLE)]
    .filter((element) => !element.hasAttribute("hidden") && element.getAttribute("aria-hidden") !== "true");
}

function WorkPreview({ work }: { work: CreatorWorkSummary }) {
  return (
    <div className={`creator-work-preview preview-${previewKind(work)}`} aria-hidden="true">
      <span>{work.legacy ? "历史项目" : STAGE_LABELS[work.stage]}</span>
      <div className="creator-preview-object">
        <i />
        <i />
        <i />
      </div>
    </div>
  );
}

function previewKind(work: CreatorWorkSummary): "idea" | "digital" | "structure" | "physical" {
  if (work.stage === CreatorStage.DIGITAL_PROTOTYPE) return "digital";
  if (work.stage === CreatorStage.STRUCTURE_3D) return "structure";
  if (work.stage === CreatorStage.PHYSICAL_RUN) return "physical";
  return "idea";
}

function workTone(work: CreatorWorkSummary): "brand" | "warn" | "ok" {
  if (work.verificationLevel >= 5) return "ok";
  if (work.verificationLevel === 0) return "warn";
  return "brand";
}

function formatUpdatedAt(value: string): string {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "最近更新";
  return `${date.toLocaleDateString("zh-CN", { month: "numeric", day: "numeric" })} 更新`;
}

function drawerTitle(drawer: CreatorDrawer): string {
  return {
    details: "方案详情",
    code: "代码工作区",
    debug: "图形调试",
    parameters: "参数版本",
    evidence: "证据与交付",
  }[drawer];
}

function CreatorIcon({ name }: { name: CreatorIconName }) {
  const paths: Record<CreatorIconName, React.ReactNode> = {
    archive: <><path d="M4 7h16" /><path d="M6 7v12h12V7" /><path d="M9 11h6" /><path d="M5 4h14l1 3H4z" /></>,
    back: <><path d="m15 18-6-6 6-6" /><path d="M9 12h10" /></>,
    check: <path d="m5 12 4 4L19 6" />,
    code: <><path d="m9 18-6-6 6-6" /><path d="m15 6 6 6-6 6" /></>,
    copy: <><rect x="8" y="8" width="11" height="11" rx="2" /><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2" /></>,
    debug: <><path d="M4 7h10" /><path d="M18 7h2" /><path d="M4 17h2" /><path d="M10 17h10" /><circle cx="16" cy="7" r="2" /><circle cx="8" cy="17" r="2" /></>,
    evidence: <><path d="M9 5h6" /><path d="M9 9h6" /><path d="M9 13h4" /><path d="M7 3h10a2 2 0 0 1 2 2v15l-3-2-4 2-4-2-3 2V5a2 2 0 0 1 2-2Z" /></>,
    import: <><path d="M12 3v12" /><path d="m7 10 5 5 5-5" /><path d="M5 21h14" /></>,
    lock: <><rect x="5" y="10" width="14" height="10" rx="2" /><path d="M8 10V7a4 4 0 0 1 8 0v3" /></>,
    package: <><path d="m12 3 8 4-8 4-8-4 8-4Z" /><path d="m4 7 8 4 8-4" /><path d="M4 7v10l8 4 8-4V7" /><path d="M12 11v10" /></>,
    parameters: <><path d="M4 6h16" /><path d="M4 12h16" /><path d="M4 18h16" /><circle cx="8" cy="6" r="2" /><circle cx="16" cy="12" r="2" /><circle cx="10" cy="18" r="2" /></>,
    plus: <><path d="M12 5v14" /><path d="M5 12h14" /></>,
    settings: <><circle cx="12" cy="12" r="3" /><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1v.09h-4V21a1.7 1.7 0 0 0-1.08-1.6 1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 4.6 15a1.7 1.7 0 0 0-.6-1 1.7 1.7 0 0 0-1-.4h-.09v-4H3A1.7 1.7 0 0 0 4.6 8.52a1.7 1.7 0 0 0-.34-1.88l-.06-.06 2.83-2.83.06.06A1.7 1.7 0 0 0 9 4.6a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1v-.09h4V3A1.7 1.7 0 0 0 15.48 4.6a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 9c.08.38.29.73.6 1 .29.25.65.39 1 .4h.09v4H21a1.7 1.7 0 0 0-1.6.6Z" /></>,
  };
  return <svg className="creator-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{paths[name]}</svg>;
}
