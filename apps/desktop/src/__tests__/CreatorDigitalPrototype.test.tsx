import { useEffect } from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { CreatorWorkspace, DeviceLabRun, DeviceLabSceneV1 } from "@zhangwen/contracts";
import DigitalPrototypeStage from "../creator/stages/DigitalPrototypeStage";

const scene: DeviceLabSceneV1 = {
  schemaVersion: "zhangwen.device-lab-scene/v1",
  projectId: "prj_m4",
  revision: "a".repeat(64),
  boardId: "dfrobot/dfrobot_k10",
  status: "READY",
  source: { proposalId: "csolution_1", proposalVersion: 1, proposalConfirmedAt: "2026-07-31T00:00:00Z", hardwareFactId: null, hardwareFactUpdatedAt: null, specRunId: null, specVersion: null, specConfirmedAt: null },
  binding: {
    schemaVersion: "zhangwen.digital-prototype-binding/v1",
    solutionRevisionId: "csolution_1",
    codeRunId: "code_usb_1",
    parameterSetId: null,
    componentPackVersion: "wokwi-elements@1.9.2+zhangwen-v1",
    simulationCapability: "FUNCTIONAL",
    layoutVersion: "auto-v1",
  },
  components: [{ id: "k10", name: "K10", category: "MCU", role: "controller", source: "project-hardware", simulation: "FUNCTIONAL", builtIn: false, protocol: "GPIO" }],
  connections: [],
  warnings: [],
  generatedAt: "2026-07-31T00:00:00Z",
};

const stoppedRun: DeviceLabRun = {
  id: "lab_m4",
  projectId: "prj_m4",
  boardId: "dfrobot/dfrobot_k10",
  target: "SIMULATOR",
  engine: "FUNCTIONAL_MODEL",
  status: "STOPPED",
  applicationId: null,
  parameterSetId: null,
  actuatorArmed: false,
  channelValues: {},
  revision: 2,
  startedAt: "2026-07-31T00:00:00Z",
  updatedAt: "2026-07-31T00:01:00Z",
  errorMessage: null,
  scene,
};

vi.mock("../components/device-lab/DeviceLabWorkspace", () => ({
  DeviceLabWorkspace: ({
    solutionRevisionId,
    codeRunId,
    onSceneChange,
    onRunChange,
  }: {
    solutionRevisionId?: string;
    codeRunId?: string;
    onSceneChange?: (value: DeviceLabSceneV1) => void;
    onRunChange?: (value: DeviceLabRun) => void;
  }) => {
    useEffect(() => {
      onSceneChange?.(scene);
      onRunChange?.(stoppedRun);
    }, [onRunChange, onSceneChange]);
    return (
      <div data-testid="embedded-device-lab">
        Wokwi 与图形调试 · {solutionRevisionId} · {codeRunId}
      </div>
    );
  },
}));

vi.mock("../components/floating/CodeArtifactEditor", () => ({
  CodeArtifactEditor: ({ codeRunId }: { codeRunId: string }) => (
    <div data-testid="prototype-code-editor">代码版本 {codeRunId}</div>
  ),
}));

describe("Creator M4 digital prototype", () => {
  it("binds static and simulation evidence to the real scene and stopped run", async () => {
    const onCommand = vi.fn(async () => undefined);
    render(<DigitalPrototypeStage workspace={workspace()} professionalMode={false} onCommand={onCommand} />);

    expect(await screen.findByTestId("embedded-device-lab")).toHaveTextContent(
      "csolution_1 · code_usb_1",
    );
    expect(await screen.findByTestId("prototype-code-editor")).toHaveTextContent(
      "code_usb_1",
    );
    fireEvent.click(screen.getByRole("button", { name: "记录静态检查" }));
    await waitFor(() => expect(onCommand).toHaveBeenCalledWith(
      "RECORD_STATIC_VALIDATION",
      expect.objectContaining({ sourceId: scene.revision, passed: true }),
    ));

    fireEvent.click(screen.getByRole("checkbox", { name: /过热提醒并恢复/ }));
    fireEvent.click(screen.getByRole("button", { name: "确认全部场景通过" }));
    await waitFor(() => expect(onCommand).toHaveBeenCalledWith(
      "RECORD_SIMULATION",
      expect.objectContaining({ sourceId: stoppedRun.id, passed: true }),
    ));
  });
});

function workspace(): CreatorWorkspace {
  const revisionSource = {
    sourceType: "PROFESSIONAL_EDIT" as const,
    sourceMessageId: null,
    sourceTurnId: null,
    baseRevisionId: null,
    projectionReceiptId: null,
  };
  const goal: NonNullable<CreatorWorkspace["currentGoal"]> = {
    id: "goal_1", workId: "prj_m4", revision: 1, status: "CONFIRMED",
    ...revisionSource, statement: "制作提醒器", observableBehavior: "过热提醒",
    constraints: [], successCriteria: ["过热提醒"],
    createdAt: "2026-07-31T00:00:00Z", confirmedAt: "2026-07-31T00:00:00Z",
  };
  const solution: NonNullable<CreatorWorkspace["currentSolution"]> = {
    id: "csolution_1", workId: "prj_m4", revision: 1, status: "CONFIRMED",
    ...revisionSource, summary: "提醒方案", logic: "阈值判断", hardware: "K10",
    software: "MicroPython", structure: "不需要结构", simulation: "温度注入",
    safety: "停止归零", bom: [], ioMap: [],
    createdAt: "2026-07-31T00:00:00Z", confirmedAt: "2026-07-31T00:00:00Z",
  };
  return {
    schemaVersion: 1,
    workId: "prj_m4",
    projectId: "prj_m4",
    projectVersion: 2,
    name: "温湿度提醒",
    initialIdea: "用 K10 制作提醒器",
    phase: "DIGITAL_BUILDING",
    activeStage: "DIGITAL_PROTOTYPE",
    verificationLevel: 1,
    verificationLabel: "目标已确认",
    stages: [
      { stage: "IDEA_SOLUTION", label: "创意与方案", status: "PASSED", detail: "已确认" },
      { stage: "DIGITAL_PROTOTYPE", label: "数字原型", status: "ACTIVE", detail: "仿真、参数与日志" },
      { stage: "STRUCTURE_3D", label: "3D 结构", status: "NOT_APPLICABLE", detail: "不需要结构" },
      { stage: "PHYSICAL_RUN", label: "实物运行", status: "BLOCKED", detail: "等待仿真" },
    ],
    confirmedGoal: goal,
    draftGoal: null,
    confirmedSolution: solution,
    draftSolution: null,
    projectBookProjection: { status: "SYNCHRONIZED", goalRevisionId: goal.id, solutionRevisionId: solution.id, updatedAt: solution.confirmedAt },
    conversationProjectionStatus: { status: "IDLE", receiptId: null, sourceMessageId: null, message: null },
    currentGoal: goal,
    currentSolution: solution,
    acceptanceScenarios: [{ id: "scenario_1", workId: "prj_m4", title: "过热提醒并恢复", required: true, simulationExpected: "灯亮后关闭", physicalExpected: "真机一致", createdAt: "2026-07-31T00:00:00Z" }],
    evidence: [],
    jobs: [],
    codeVariants: [{
      id: "variant_usb_1",
      workId: "prj_m4",
      solutionRevisionId: solution.id,
      deploymentChannel: "USB_SERIAL",
      runtime: "MICROPYTHON",
      codeRunId: "code_usb_1",
      devicePackageId: "dfrobot/dfrobot_k10",
      validationStatus: "READY_FOR_REVIEW",
      failureCode: null,
      failureMessage: null,
      createdAt: "2026-07-31T00:00:00Z",
      updatedAt: "2026-07-31T00:00:00Z",
    }],
    parameterRevisions: [],
    nextAction: { id: "static-validation", label: "检查场景", command: "RECORD_STATIC_VALIDATION", stage: "DIGITAL_PROTOTYPE", enabled: true, blockedReason: null, riskLevel: "LOW" },
    archivedAt: null,
    updatedAt: "2026-07-31T00:00:00Z",
    legacy: false,
    needsOrganization: false,
  };
}
