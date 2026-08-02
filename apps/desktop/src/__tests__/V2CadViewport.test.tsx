import { render, screen, waitFor } from "@testing-library/react";
import type { CadIntentRevision } from "@zhangwen/contracts";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { V2CadViewport } from "../components/v2/V2CadViewport";

const { getArtifactMock } = vi.hoisted(() => ({
  getArtifactMock: vi.fn(),
}));

vi.mock("../services/projectsApi", () => ({
  getArtifact: getArtifactMock,
}));

vi.mock("../components/floating/Model3dArtifactViewer", () => ({
  Model3dArtifactViewer: ({ version }: { version: { id: string } }) => (
    <div data-testid="model-3d-viewer">{version.id}</div>
  ),
}));

describe("V2 CAD 产物回显", () => {
  beforeEach(() => {
    getArtifactMock.mockReset();
  });

  it("构建完成后按修订版本加载 GLB 预览，并可在刷新后重新读取", async () => {
    getArtifactMock.mockResolvedValue({
      artifact: artifactWithModel("cad_model_file"),
    });
    const view = render(
      <V2CadViewport revision={revision()} cadRun={null} refreshKey="first" />,
    );

    expect(await screen.findByTestId("model-3d-viewer")).toHaveTextContent("artifact_cad_v1");
    expect(getArtifactMock).toHaveBeenCalledWith("prj_v2", "artifact_cad");

    view.rerender(
      <V2CadViewport revision={revision()} cadRun={null} refreshKey="second" />,
    );
    await waitFor(() => expect(getArtifactMock).toHaveBeenCalledTimes(2));
  });

  it("只有 CAD 源码、尚未生成模型时明确提示继续构建", async () => {
    getArtifactMock.mockResolvedValue({ artifact: artifactWithModel(null) });

    render(<V2CadViewport revision={revision()} cadRun={null} />);

    expect(await screen.findByText("方案已确认，等待生成 3D")).toBeInTheDocument();
    expect(screen.getByText(/生成 3D 模型/)).toBeInTheDocument();
  });
});

function revision(): CadIntentRevision {
  return {
    id: "cad_rev_1",
    projectId: "prj_v2",
    parentRevisionId: null,
    toolJobId: "job_cad_1",
    changeSetId: "change_cad_1",
    projectVersionId: "pver_1",
    intentSummary: "K10 电子相册外壳",
    routeAction: "draft",
    status: "CONFIRMED",
    sourceSha256: "a".repeat(64),
    objectIndex: [],
    artifactId: "artifact_cad",
    artifactVersionId: "artifact_cad_v1",
    createdAt: "2026-07-26T00:00:00Z",
    confirmedAt: "2026-07-26T00:00:01Z",
  };
}

function artifactWithModel(modelFileId: string | null) {
  return {
    id: "artifact_cad",
    projectId: "prj_v2",
    title: "K10 电子相册外壳",
    kind: "MODEL_3D",
    status: "READY",
    sourceAgentId: "structure-engineer",
    currentVersionId: "artifact_cad_v1",
    versions: [{
      id: "artifact_cad_v1",
      artifactId: "artifact_cad",
      projectId: "prj_v2",
      version: 1,
      status: "READY",
      mimeType: "model/gltf-binary",
      preview: { kind: "MODEL_3D", summary: "已通过本地构建", modelFileId },
      dependencies: [],
      producerTaskId: "job_cad_build_1",
      sourceEntityType: "cad_intent_revision",
      sourceEntityId: "cad_rev_1",
      checksum: "b".repeat(64),
      staleReason: null,
      createdAt: "2026-07-26T00:00:02Z",
      confirmedAt: "2026-07-26T00:00:03Z",
    }],
    createdAt: "2026-07-26T00:00:00Z",
    updatedAt: "2026-07-26T00:00:03Z",
  };
}
