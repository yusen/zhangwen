import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import {
  CadJobPhase,
  CadJobStatus,
  CadRunStatus,
  CadTemplateKind,
  type CadJob,
  type CadRun,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ProjectConfirmationCard } from "../components/chat/ProjectConfirmationCard";
import { WorkTab } from "../components/right-panel/WorkTab";
import {
  createHostAdapter,
  HostAdapterProvider,
  platformCapabilities,
} from "../platform";

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("CAD 中央确认", () => {
  it("DRAFT 只创建持久 CAD Job，不提前确认 CAD", async () => {
    const draft = cadRun({ status: CadRunStatus.DRAFT });
    const fetchMock = confirmationFetch(draft);
    const onReloadProject = vi.fn(async () => undefined);
    vi.stubGlobal("fetch", fetchMock);

    renderConfirmation(draft, onReloadProject);

    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    expect(within(confirmation).getByText("结构建模草稿")).toBeInTheDocument();
    fireEvent.click(within(confirmation).getByRole("button", { name: "开始建模" }));

    await waitFor(() => {
      expect(postCalls(fetchMock, "/api/projects/prj_1/cad/jobs")).toHaveLength(1);
    });
    const createCall = postCalls(fetchMock, "/api/projects/prj_1/cad/jobs")[0];
    expect(JSON.parse(String(createCall?.[1]?.body))).toEqual({
      cadRunId: "cad_1",
      clientRequestId: "cad-start-cad_1",
    });
    expect(postCalls(fetchMock, "/api/projects/prj_1/cad/confirm")).toHaveLength(0);
    expect(onReloadProject).toHaveBeenCalledWith("prj_1");
  });

  it("READY_FOR_REVIEW 才确认最终 CAD，不创建新 Job", async () => {
    const ready = cadRun({
      status: CadRunStatus.READY_FOR_REVIEW,
      artifactId: "artifact_cad_1",
      artifactVersionId: "artifact_version_cad_1",
    });
    const fetchMock = confirmationFetch(ready);
    vi.stubGlobal("fetch", fetchMock);

    renderConfirmation(ready);

    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    expect(within(confirmation).getByText("结构件 CAD")).toBeInTheDocument();
    fireEvent.click(within(confirmation).getByRole("button", { name: "确认 CAD" }));

    await waitFor(() => {
      expect(postCalls(fetchMock, "/api/projects/prj_1/cad/confirm")).toHaveLength(1);
    });
    const confirmCall = postCalls(fetchMock, "/api/projects/prj_1/cad/confirm")[0];
    expect(JSON.parse(String(confirmCall?.[1]?.body))).toEqual({ cadRunId: "cad_1" });
    expect(postCalls(fetchMock, "/api/projects/prj_1/cad/jobs")).toHaveLength(0);
  });

  it("旧 CAD 确认遇到 intake 修订冲突后刷新项目并提示使用最新草稿", async () => {
    const ready = cadRun({ status: CadRunStatus.READY_FOR_REVIEW });
    const onReloadProject = vi.fn(async () => undefined);
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.endsWith("/execution-plan/current")) return json({ plan: null });
      if (url.endsWith("/spec/current")) return json({ spec: null });
      if (url.endsWith("/code/current")) return json({ codeRun: null });
      if (url.endsWith("/cad/current")) return json({ cadRun: ready });
      if (url.endsWith("/lesson/current")) return json({ lessonRun: null });
      if (url.endsWith("/cad/confirm") && init?.method === "POST") {
        return json(
          {
            detail: {
              code: "CAD_INTAKE_REVISED",
              message: "CAD 结构输入已更新，请使用最新 CAD 草稿。",
              retryable: false,
            },
          },
          409,
        );
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderConfirmation(ready, onReloadProject);
    fireEvent.click(await screen.findByRole("button", { name: "确认 CAD" }));

    expect(
      await screen.findByText("CAD 结构输入已更新，请使用当前对话中的最新草稿。"),
    ).toBeInTheDocument();
    expect(onReloadProject).toHaveBeenCalledWith("prj_1");
  });

  it("Web 模式禁用 DRAFT 的开始建模并说明桌面能力边界", async () => {
    const draft = cadRun({ status: CadRunStatus.DRAFT });
    const fetchMock = confirmationFetch(draft);
    vi.stubGlobal("fetch", fetchMock);

    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <ProjectConfirmationCard
          workspace={workspace()}
          onResolvePendingItem={vi.fn()}
          onDismissPendingItem={vi.fn()}
          onReloadProject={vi.fn(async () => undefined)}
          onOpenArtifact={vi.fn()}
        />
      </HostAdapterProvider>,
    );

    const confirmation = await screen.findByRole("region", { name: "待你确认" });
    const startButton = within(confirmation).getByRole("button", { name: "开始建模" });
    expect(startButton).toBeDisabled();
    expect(within(confirmation).getByText(/当前浏览器模式不支持本地 CAD 执行/)).toBeInTheDocument();
    fireEvent.click(startButton);
    expect(postCalls(fetchMock, "/api/projects/prj_1/cad/jobs")).toHaveLength(0);
  });

  it("中央确认组件在工作 Tab 卸载后继续轮询并呈现 READY_FOR_REVIEW", async () => {
    const runningJob = cadJob({ status: CadJobStatus.RUNNING, progress: 32 });
    const succeededJob = cadJob({
      status: CadJobStatus.SUCCEEDED,
      phase: CadJobPhase.COMPLETED,
      progress: 100,
    });
    let currentRun = cadRun({ status: CadRunStatus.RUNNING, latestJob: runningJob });
    let jobCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/execution-plan/current")) return json({ plan: null });
      if (url.endsWith("/spec/current")) return json({ spec: null });
      if (url.endsWith("/code/current")) return json({ codeRun: null });
      if (url.endsWith("/lesson/current")) return json({ lessonRun: null });
      if (url.endsWith("/cad/current")) {
        if (jobCalls >= 2) {
          currentRun = cadRun({
            status: CadRunStatus.READY_FOR_REVIEW,
            latestJob: succeededJob,
            artifactId: "artifact_cad_1",
            artifactVersionId: "artifact_version_cad_1",
          });
        }
        return json({ cadRun: currentRun });
      }
      if (url.endsWith("/cad/jobs/job_1")) {
        jobCalls += 1;
        return json({ cadJob: jobCalls === 1 ? runningJob : succeededJob });
      }
      return json({}, 404);
    });
    const onReloadProject = vi.fn(async () => undefined);
    vi.stubGlobal("fetch", fetchMock);

    renderConfirmation(currentRun, onReloadProject);

    await waitFor(() => expect(jobCalls).toBeGreaterThanOrEqual(2), { timeout: 3000 });
    expect(await screen.findByRole("button", { name: "确认 CAD" })).toBeInTheDocument();
    expect(onReloadProject).toHaveBeenCalledWith("prj_1");
  });
});

describe("工作 Tab 的 CAD 任务", () => {
  it("删除工程流水线后不再呈现或轮询 CAD 任务", async () => {
    const fetchMock = workTabFetch(cadRun({ status: CadRunStatus.DRAFT }));
    vi.stubGlobal("fetch", fetchMock);

    renderWorkTab("tauri");

    await screen.findByRole("region", { name: "项目总览" });
    expect(screen.queryByRole("region", { name: "结构件 CAD" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "生成 CAD" })).not.toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([input]) => String(input).endsWith("/cad/current"))).toBe(false);
    expect(fetchMock.mock.calls.some(([input]) => String(input).includes("/cad/jobs/"))).toBe(false);
  });
});

function renderWorkTab(
  host: "web" | "tauri",
  onConfirmationChanged = vi.fn(),
  onOpenArtifact = vi.fn(),
) {
  return render(
    <HostAdapterProvider adapter={createHostAdapter(platformCapabilities(host))}>
      <WorkTab
        workspace={workspace()}
        professionalMode={false}
        refreshRevision={0}
        onConfirmationChanged={onConfirmationChanged}
        onOpenArtifact={onOpenArtifact}
      />
    </HostAdapterProvider>,
  );
}

function renderConfirmation(
  _run: CadRun,
  onReloadProject = vi.fn(async () => undefined),
) {
  return render(
    <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("tauri"))}>
      <ProjectConfirmationCard
        workspace={workspace()}
        onResolvePendingItem={vi.fn()}
        onDismissPendingItem={vi.fn()}
        onReloadProject={onReloadProject}
        onOpenArtifact={vi.fn()}
      />
    </HostAdapterProvider>,
  );
}

function confirmationFetch(run: CadRun) {
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/execution-plan/current")) return json({ plan: null });
    if (url.endsWith("/spec/current")) return json({ spec: null });
    if (url.endsWith("/code/current")) return json({ codeRun: null });
    if (url.endsWith("/cad/current")) return json({ cadRun: run });
    if (url.endsWith("/lesson/current")) return json({ lessonRun: null });
    if (url.endsWith("/cad/jobs") && init?.method === "POST") {
      return json({ cadJob: cadJob({ status: CadJobStatus.QUEUED }) });
    }
    if (url.endsWith("/cad/confirm") && init?.method === "POST") {
      return json({ cadRun: { ...run, status: CadRunStatus.APPROVED } });
    }
    if (url.endsWith("/cad/reject") && init?.method === "POST") {
      return json({ cadRun: { ...run, status: CadRunStatus.REJECTED } });
    }
    return json({}, 404);
  });
}

function workTabFetch(
  run: CadRun,
  jobs: {
    polledJob?: CadJob;
    canceledJob?: CadJob;
    retriedJob?: CadJob;
  } = {},
) {
  let cancelRequested = false;
  return vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.endsWith("/execution-plan/current")) return json({ plan: null });
    if (url.endsWith("/cad/current")) return json({ cadRun: run });
    if (url.endsWith("/cad/jobs/job_1/cancel") && init?.method === "POST") {
      cancelRequested = true;
      return json({ cadJob: jobs.canceledJob ?? run.latestJob });
    }
    if (url.endsWith("/cad/jobs/job_1/retry") && init?.method === "POST") {
      return json({ cadJob: jobs.retriedJob ?? run.latestJob });
    }
    if (url.endsWith("/cad/jobs/job_1") && (!init?.method || init.method === "GET")) {
      return json({ cadJob: cancelRequested ? jobs.canceledJob ?? run.latestJob : jobs.polledJob ?? run.latestJob });
    }
    return json({}, 404);
  });
}

function postCalls(fetchMock: ReturnType<typeof vi.fn>, suffix: string) {
  return fetchMock.mock.calls.filter(
    ([input, init]) => String(input).endsWith(suffix) && init?.method === "POST",
  );
}

function workspace(): ProjectWorkspace {
  return {
    project: {
      id: "prj_1",
      name: "CAD 测试项目",
      stage: "IDEA",
      profile: { initialIdea: "生成结构件三维模型" },
      conversationId: "conversation_1",
      activeExpertIds: ["expert_structure"],
      activeExpertId: "expert_structure",
      sharedContextId: null,
      coordinatorStateId: null,
      selectedModel: "deepseek-v4-flash",
      archivedAt: null,
      createdAt: "2026-07-13T00:00:00Z",
      updatedAt: "2026-07-13T00:00:00Z",
      lastOpenedAt: "2026-07-13T00:00:00Z",
      schemaVersion: 24,
    },
    conversation: {
      id: "conversation_1",
      projectId: "prj_1",
      messages: [],
      updatedAt: "2026-07-13T00:00:00Z",
    },
    draft: {
      projectId: "prj_1",
      content: "",
      updatedAt: null,
    },
  };
}

function cadRun(overrides: Partial<CadRun> = {}): CadRun {
  return {
    id: "cad_1",
    projectId: "prj_1",
    specRunId: "spec_1",
    templateKind: CadTemplateKind.BOX_WITH_LID,
    version: 1,
    status: CadRunStatus.DRAFT,
    commandLabel: "生成盒体与盖板",
    parameters: [
      { name: "width", label: "宽度", unit: "mm", value: 100, min: 20, max: 300 },
    ],
    validation: {
      ok: true,
      checks: [
        { dimension: "geometry", severity: "PASS", message: "尺寸有效", details: "" },
      ],
    },
    files: [],
    artifactId: null,
    artifactVersionId: null,
    sourceMessageId: "message_1",
    generatedByExpertId: "expert_structure",
    engineId: "cadquery-template-v1",
    engineVersion: "1.0.0",
    designState: null,
    latestJob: null,
    staleReason: null,
    createdAt: "2026-07-13T00:00:00Z",
    updatedAt: "2026-07-13T00:00:00Z",
    confirmedAt: null,
    ...overrides,
  };
}

function cadJob(overrides: Partial<CadJob> = {}): CadJob {
  const id = overrides.id ?? "job_1";
  return {
    id,
    projectId: "prj_1",
    cadRunId: "cad_1",
    clientRequestId: null,
    status: CadJobStatus.RUNNING,
    phase: CadJobPhase.BUILDING,
    progress: 50,
    sourceMessageId: "message_1",
    projectExpertId: "expert_structure",
    specRunId: "spec_1",
    requestHash: "a".repeat(64),
    request: {
      jobId: id,
      projectId: "prj_1",
      specRunId: "spec_1",
      templateKind: CadTemplateKind.BOX_WITH_LID,
      templateRevision: "1.0",
      parameters: { width: 100 },
      components: [],
      constraints: {},
      summary: "盒体与盖板",
      profileSnapshots: [],
    },
    result: null,
    error: null,
    createdAt: "2026-07-13T00:00:00Z",
    startedAt: "2026-07-13T00:00:01Z",
    completedAt: null,
    ...overrides,
  };
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
