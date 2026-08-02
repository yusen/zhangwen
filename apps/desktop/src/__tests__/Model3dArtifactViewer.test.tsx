import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import {
  ArtifactPreviewKind,
  ArtifactStatus,
  CadOutputRole,
  type ArtifactFile,
  type ArtifactVersion,
} from "@zhangwen/contracts";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Model3dArtifactViewer } from "../components/floating/Model3dArtifactViewer";

const modelViewerSpy = vi.hoisted(() => vi.fn());

vi.mock("../components/floating/Model3DViewer", () => ({
  Model3DViewer: (props: { data: ArrayBuffer; fileName: string }) => {
    modelViewerSpy(props);
    return (
      <div data-testid="mock-model3d-viewer">
        {props.fileName} · {props.data.byteLength} bytes
      </div>
    );
  },
}));

afterEach(() => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe("MODEL_3D 产物文件加载", () => {
  it("优先选择 preview 指定的 GLB，并把真实二进制交给查看器", async () => {
    const preferred = artifactFile({
      id: "file_preferred",
      role: CadOutputRole.STEP_ASSEMBLY,
      fileName: "assembly-preview.glb",
      mimeType: "model/gltf-binary",
      byteSize: 4,
    });
    const roleFallback = artifactFile({
      id: "file_role",
      role: CadOutputRole.GLB_PREVIEW,
      fileName: "fallback.glb",
      byteSize: 4,
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/files")) {
        return json({ files: [roleFallback, preferred] });
      }
      if (url.endsWith("/files/file_preferred")) {
        return binary([0x67, 0x6c, 0x54, 0x46]);
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(
      <Model3dArtifactViewer
        version={artifactVersion({ modelFileId: "file_preferred" })}
      />,
    );

    expect(await screen.findByTestId("mock-model3d-viewer")).toHaveTextContent(
      "assembly-preview.glb · 4 bytes",
    );
    expect(modelViewerSpy).toHaveBeenCalledWith(
      expect.objectContaining({ fileName: "assembly-preview.glb" }),
    );
    expect(
      fetchMock.mock.calls.some(([input]) =>
        String(input).endsWith("/files/file_preferred"),
      ),
    ).toBe(true);
    expect(
      fetchMock.mock.calls.some(([input]) => String(input).endsWith("/files/file_role")),
    ).toBe(false);
  });

  it("GLB 实际大小与不可变清单不一致时停止渲染", async () => {
    const file = artifactFile({ byteSize: 5 });
    vi.stubGlobal(
      "fetch",
      vi.fn(async (input: RequestInfo | URL) =>
        String(input).endsWith("/files")
          ? json({ files: [file] })
          : binary([0x67, 0x6c, 0x54, 0x46]),
      ),
    );

    render(<Model3dArtifactViewer version={artifactVersion()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "GLB 文件大小与产物清单不一致，已停止渲染。",
    );
    expect(screen.queryByTestId("mock-model3d-viewer")).not.toBeInTheDocument();
    expect(modelViewerSpy).not.toHaveBeenCalled();
  });

  it("加载错误提供文字原因和显式重试，成功后才挂载查看器", async () => {
    const file = artifactFile({ byteSize: 4 });
    let listAttempts = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.endsWith("/files")) {
        listAttempts += 1;
        return listAttempts === 1
          ? json({ detail: { code: "ARTIFACT_FILE_UNAVAILABLE", message: "产物文件不可读" } }, 503)
          : json({ files: [file] });
      }
      if (url.endsWith("/files/file_glb")) {
        return binary([0x67, 0x6c, 0x54, 0x46]);
      }
      return json({}, 404);
    });
    vi.stubGlobal("fetch", fetchMock);

    render(<Model3dArtifactViewer version={artifactVersion()} />);

    expect(await screen.findByRole("alert")).toHaveTextContent("产物文件不可读");
    expect(modelViewerSpy).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "重新加载" }));

    expect(await screen.findByTestId("mock-model3d-viewer")).toHaveTextContent(
      "model.glb · 4 bytes",
    );
    await waitFor(() => expect(listAttempts).toBe(2));
  });
});

function artifactVersion(
  overrides: { modelFileId?: string | null } = {},
): ArtifactVersion {
  return {
    id: "artifact_version_1",
    artifactId: "artifact_cad_1",
    projectId: "prj_1",
    version: 1,
    status: ArtifactStatus.NEEDS_REVIEW,
    mimeType: "model/gltf-binary",
    preview: {
      kind: ArtifactPreviewKind.MODEL_3D,
      summary: "结构件三维模型",
      modelFileId: overrides.modelFileId ?? "file_glb",
    },
    dependencies: [],
    producerTaskId: null,
    sourceEntityType: "cad_run",
    sourceEntityId: "cad_1",
    checksum: "a".repeat(64),
    staleReason: null,
    createdAt: "2026-07-13T00:00:00Z",
    confirmedAt: null,
  };
}

function artifactFile(overrides: Partial<ArtifactFile> = {}): ArtifactFile {
  return {
    id: "file_glb",
    artifactId: "artifact_cad_1",
    artifactVersionId: "artifact_version_1",
    projectId: "prj_1",
    role: CadOutputRole.GLB_PREVIEW,
    fileName: "model.glb",
    mimeType: "model/gltf-binary",
    byteSize: 4,
    sha256: "c74f919439792582aa4f0b188ec2a928675cdb3ba72797781ceb6dfaa86b313f",
    triangleCount: 12,
    bounds: {
      min_x: -1,
      min_y: -1,
      min_z: 0,
      max_x: 1,
      max_y: 1,
      max_z: 2,
    },
    createdAt: "2026-07-13T00:00:00Z",
    ...overrides,
  };
}

function binary(bytes: number[]): Response {
  const data = Uint8Array.from(bytes).buffer;
  return new Response(data, {
    status: 200,
    headers: { "Content-Type": "model/gltf-binary" },
  });
}

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}
