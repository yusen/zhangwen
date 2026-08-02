import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CreatorWorkSummary, CreatorWorkspace } from "@zhangwen/contracts";
import { useCreatorWorks } from "../creator/state/useCreatorWorks";

const mocks = vi.hoisted(() => ({
  listCreatorWorks: vi.fn(),
  getCreatorWorkspace: vi.fn(),
}));

vi.mock("../services/creatorApi", async (importOriginal) => ({
  ...await importOriginal<typeof import("../services/creatorApi")>(),
  listCreatorWorks: mocks.listCreatorWorks,
  getCreatorWorkspace: mocks.getCreatorWorkspace,
}));

describe("Creator workspace recovery", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mocks.listCreatorWorks.mockResolvedValue({
      works: [workFixture()],
      activeWorkId: "prj_creator",
    });
    mocks.getCreatorWorkspace.mockResolvedValue({
      workspace: workspaceFixture(),
    });
  });

  it("restores the active work and its projected stage after every mount", async () => {
    const first = render(<RecoveryProbe />);

    expect(await screen.findByTestId("recovered-work")).toHaveTextContent("prj_creator");
    expect(screen.getByTestId("recovered-stage")).toHaveTextContent("PHYSICAL_RUN");
    first.unmount();

    render(<RecoveryProbe />);

    expect(await screen.findByTestId("recovered-work")).toHaveTextContent("prj_creator");
    expect(screen.getByTestId("recovered-stage")).toHaveTextContent("PHYSICAL_RUN");
    expect(mocks.listCreatorWorks).toHaveBeenCalledTimes(2);
    expect(mocks.getCreatorWorkspace).toHaveBeenNthCalledWith(1, "prj_creator");
    expect(mocks.getCreatorWorkspace).toHaveBeenNthCalledWith(2, "prj_creator");
  });

  it.each([
    {
      label: "is absent from the work list",
      activeWorkId: "missing_work",
      works: [workFixture()],
    },
    {
      label: "points to an archived work",
      activeWorkId: "prj_creator",
      works: [{ ...workFixture(), archivedAt: "2026-07-31T02:00:00Z" }],
    },
  ])("returns to the works home when activeWorkId $label", async ({ activeWorkId, works }) => {
    mocks.listCreatorWorks.mockResolvedValue({ works, activeWorkId });

    render(<RecoveryProbe />);

    await waitFor(() => expect(screen.getByTestId("recovery-state")).toHaveTextContent("home"));
    expect(mocks.getCreatorWorkspace).not.toHaveBeenCalled();
  });

  it("rejects a workspace response that does not match the active work", async () => {
    mocks.getCreatorWorkspace.mockResolvedValue({
      workspace: { ...workspaceFixture(), workId: "different_work" },
    });

    render(<RecoveryProbe />);

    await waitFor(() => expect(screen.getByTestId("recovery-state")).toHaveTextContent("home"));
    expect(mocks.getCreatorWorkspace).toHaveBeenCalledWith("prj_creator");
  });
});

function RecoveryProbe() {
  const creator = useCreatorWorks();
  if (creator.loading) return <output data-testid="recovery-state">loading</output>;
  if (!creator.workspace) return <output data-testid="recovery-state">home</output>;
  return (
    <>
      <output data-testid="recovered-work">{creator.workspace.workId}</output>
      <output data-testid="recovered-stage">{creator.workspace.activeStage}</output>
    </>
  );
}

function workFixture(): CreatorWorkSummary {
  return {
    id: "prj_creator",
    name: "自动浇花伙伴",
    initialIdea: "土壤干燥时自动浇水",
    phase: "GOAL_REVIEW",
    stage: "IDEA_SOLUTION",
    verificationLevel: 0,
    verificationLabel: "尚未验证",
    nextActionLabel: "确认作品目标",
    archivedAt: null,
    updatedAt: "2026-07-31T00:00:00Z",
    legacy: false,
  };
}

function workspaceFixture(): CreatorWorkspace {
  return {
    schemaVersion: 1,
    workId: "prj_creator",
    projectId: "prj_creator",
    projectVersion: 2,
    name: "自动浇花伙伴",
    initialIdea: "土壤干燥时自动浇水",
    phase: "SIMULATION_PASSED",
    activeStage: "PHYSICAL_RUN",
    verificationLevel: 3,
    verificationLabel: "功能仿真已通过",
    stages: [
      {
        stage: "IDEA_SOLUTION",
        label: "创意与方案",
        status: "PASSED",
        detail: "目标与当前方案",
      },
      {
        stage: "DIGITAL_PROTOTYPE",
        label: "数字原型",
        status: "PASSED",
        detail: "仿真、参数与日志",
      },
      {
        stage: "STRUCTURE_3D",
        label: "3D 结构",
        status: "READY",
        detail: "结构版本与制造检查",
      },
      {
        stage: "PHYSICAL_RUN",
        label: "实物运行",
        status: "ACTIVE",
        detail: "设备连接、部署和真机验收",
      },
    ],
    confirmedGoal: null,
    draftGoal: null,
    confirmedSolution: null,
    draftSolution: null,
    projectBookProjection: {
      status: "EMPTY",
      goalRevisionId: null,
      solutionRevisionId: null,
      updatedAt: null,
    },
    conversationProjectionStatus: {
      status: "IDLE",
      receiptId: null,
      sourceMessageId: null,
      message: null,
    },
    currentGoal: null,
    currentSolution: null,
    acceptanceScenarios: [],
    evidence: [],
    jobs: [],
    codeVariants: [],
    parameterRevisions: [],
    nextAction: {
      id: "connect-device",
      label: "连接并确认设备",
      command: "RECORD_DEVICE_CONNECTION",
      stage: "PHYSICAL_RUN",
      enabled: true,
      blockedReason: null,
      riskLevel: "MEDIUM",
    },
    archivedAt: null,
    updatedAt: "2026-07-31T01:00:00Z",
    legacy: false,
    needsOrganization: false,
  };
}
