import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  ArtifactKind,
  ArtifactPreviewKind,
  ArtifactStatus,
  type ArtifactListResponse,
  type ProjectWorkspace,
} from "@zhangwen/contracts";
import { ArtifactsTab } from "../components/right-panel/ArtifactsTab";
import { HostAdapterProvider, createHostAdapter } from "../platform";
import { platformCapabilities } from "../platform/capabilities";
import { listArtifacts } from "../services/projectsApi";

vi.mock("../services/projectsApi", () => ({
  listArtifacts: vi.fn(),
  proposalExportUrl: vi.fn(() => "/proposal/export"),
}));

const mockedListArtifacts = vi.mocked(listArtifacts);
const workspace = {
  project: { id: "prj_cad_gate", updatedAt: "2026-07-13T00:00:00+00:00" },
} as unknown as ProjectWorkspace;

afterEach(() => {
  vi.clearAllMocks();
});

describe("ArtifactsTab CAD host gate", () => {
  it("Web 模式禁用 3D 产物并说明本地 CAD 能力边界", async () => {
    mockedListArtifacts.mockResolvedValue(modelResponse());
    const onOpenFloating = vi.fn();

    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("web"))}>
        <ArtifactsTab
          workspace={workspace}
          professionalMode={false}
          refreshRevision={0}
          onOpenFloating={onOpenFloating}
        />
      </HostAdapterProvider>
    );

    const button = await screen.findByRole("button", { name: "打开 3D 模型" });
    expect(button).toBeDisabled();
    expect(screen.getByText("当前浏览器模式不支持本地 CAD 执行。"))
      .toBeInTheDocument();
    fireEvent.click(button);
    expect(onOpenFloating).not.toHaveBeenCalled();
  });

  it("桌面模式允许打开 3D 产物浮窗", async () => {
    mockedListArtifacts.mockResolvedValue(modelResponse());
    const onOpenFloating = vi.fn();

    render(
      <HostAdapterProvider adapter={createHostAdapter(platformCapabilities("tauri"))}>
        <ArtifactsTab
          workspace={workspace}
          professionalMode={false}
          refreshRevision={0}
          onOpenFloating={onOpenFloating}
        />
      </HostAdapterProvider>
    );

    const button = await screen.findByRole("button", { name: "打开 3D 模型" });
    await waitFor(() => expect(button).toBeEnabled());
    fireEvent.click(button);
    expect(onOpenFloating).toHaveBeenCalledTimes(1);
  });
});

function modelResponse(): ArtifactListResponse {
  const version = {
    id: "artifact_version_cad_gate",
    artifactId: "artifact_cad_gate",
    projectId: "prj_cad_gate",
    version: 1,
    status: ArtifactStatus.NEEDS_REVIEW,
    mimeType: "model/gltf-binary",
    preview: {
      kind: ArtifactPreviewKind.MODEL_3D,
      summary: "结构件 GLB 预览",
      modelUrl: "/api/projects/prj_cad_gate/artifacts/file",
      modelFileId: "artifact_file_cad_gate",
    },
    dependencies: [],
    producerTaskId: null,
    sourceEntityType: "cad",
    sourceEntityId: "cad_run_gate",
    checksum: "a".repeat(64),
    staleReason: null,
    createdAt: "2026-07-13T00:00:00+00:00",
    confirmedAt: null,
  };
  return {
    artifacts: [
      {
        id: "artifact_cad_gate",
        projectId: "prj_cad_gate",
        title: "结构件 CAD 模型",
        kind: ArtifactKind.MODEL_3D,
        status: ArtifactStatus.NEEDS_REVIEW,
        sourceAgentId: "cad-agent",
        currentVersionId: version.id,
        versions: [version],
        createdAt: version.createdAt,
        updatedAt: version.createdAt,
      },
    ],
  };
}
