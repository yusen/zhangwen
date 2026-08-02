import { useEffect, useMemo, useState } from "react";
import {
  CadOutputRole,
  type ArtifactFile,
  type ArtifactVersion,
} from "@zhangwen/contracts";
import {
  downloadArtifactFile,
  listArtifactFiles,
} from "../../services/projectsApi";
import { Model3DViewer } from "./Model3DViewer";

interface Model3dArtifactViewerProps {
  version: ArtifactVersion;
}

interface LoadedModel {
  file: ArtifactFile;
  data: ArrayBuffer;
  files: ArtifactFile[];
}

export function Model3dArtifactViewer({ version }: Model3dArtifactViewerProps) {
  const [loaded, setLoaded] = useState<LoadedModel | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loadRevision, setLoadRevision] = useState(0);
  const [downloadingFileId, setDownloadingFileId] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    setLoaded(null);
    setError(null);

    void loadModel(version, controller.signal)
      .then((result) => setLoaded(result))
      .catch((reason: unknown) => {
        if (controller.signal.aborted) return;
        setError(reason instanceof Error ? reason.message : "3D 模型加载失败。");
      });

    return () => controller.abort();
  }, [loadRevision, version]);

  const details = useMemo(() => {
    if (!loaded) return null;
    const parts = [loaded.file.fileName, formatBytes(loaded.file.byteSize)];
    if (loaded.file.triangleCount !== null) {
      parts.push(`${loaded.file.triangleCount.toLocaleString("zh-CN")} 个三角面`);
    }
    return parts.join(" · ");
  }, [loaded]);

  return (
    <section className="model3d-artifact-viewer" aria-label="CAD 三维预览">
      {!loaded && !error && (
        <div className="model3d-loading" role="status">
          <span className="model3d-loading-indicator" aria-hidden="true" />
          <p>正在安全读取 GLB 预览...</p>
        </div>
      )}
      {error && (
        <div className="model3d-load-error">
          <p role="alert">{error}</p>
          <button type="button" onClick={() => setLoadRevision((current) => current + 1)}>
            重新加载
          </button>
        </div>
      )}
      {loaded && (
        <>
          <div className="model3d-filebar">
            <span>{details}</span>
            <button type="button" onClick={() => downloadLoadedModel(loaded)}>
              下载 GLB
            </button>
          </div>
          <Model3DViewer data={loaded.data} fileName={loaded.file.fileName} />
          <div className="model3d-exports" aria-label="CAD 制造文件">
            <span>制造文件</span>
            <div>
              {loaded.files.filter(isManufacturingFile).map((file) => (
                <button
                  key={file.id}
                  type="button"
                  disabled={downloadingFileId !== null}
                  onClick={() =>
                    void downloadArtifactOutput(version, file, setDownloadingFileId, setError)
                  }
                >
                  {downloadingFileId === file.id ? "正在下载..." : file.fileName}
                </button>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}

async function loadModel(
  version: ArtifactVersion,
  signal: AbortSignal,
): Promise<LoadedModel> {
  const response = await listArtifactFiles(
    version.projectId,
    version.artifactId,
    version.id,
    signal,
  );
  const file = selectGlbFile(response.files, version.preview.modelFileId);
  if (!file) {
    throw new Error("当前产物版本没有可用的 GLB 预览文件。");
  }
  const data = await downloadArtifactFile(
    version.projectId,
    version.artifactId,
    version.id,
    file.id,
    signal,
  );
  if (file.byteSize > 0 && data.byteLength !== file.byteSize) {
    throw new Error("GLB 文件大小与产物清单不一致，已停止渲染。");
  }
  if (data.byteLength === 0) {
    throw new Error("GLB 预览文件为空，请重新生成 CAD。");
  }
  const digest = await sha256Hex(data);
  if (digest !== file.sha256.toLowerCase()) {
    throw new Error("GLB 文件校验值与产物清单不一致，已停止渲染。");
  }
  return { file, data, files: response.files };
}

async function sha256Hex(data: ArrayBuffer): Promise<string> {
  if (!globalThis.crypto?.subtle) {
    throw new Error("当前宿主无法校验 GLB 文件，已停止渲染。");
  }
  const digest = await globalThis.crypto.subtle.digest("SHA-256", data);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, "0")).join("");
}

function selectGlbFile(
  files: ArtifactFile[],
  preferredFileId?: string | null,
): ArtifactFile | null {
  const candidates = files.filter(isGlbFile);
  return (
    candidates.find((file) => file.id === preferredFileId) ??
    candidates.find((file) => file.role === CadOutputRole.GLB_PREVIEW) ??
    candidates[0] ??
    null
  );
}

function isGlbFile(file: ArtifactFile): boolean {
  return (
    file.role === CadOutputRole.GLB_PREVIEW ||
    file.mimeType === "model/gltf-binary" ||
    file.fileName.toLowerCase().endsWith(".glb")
  );
}

function isManufacturingFile(file: ArtifactFile): boolean {
  return (
    file.role === CadOutputRole.STEP_ASSEMBLY ||
    file.role === CadOutputRole.STEP_PRINTABLE_PARTS ||
    file.role === CadOutputRole.STL_PRINTABLE_PARTS
  );
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KiB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MiB`;
}

function downloadLoadedModel({ file, data }: LoadedModel) {
  downloadBuffer(file, data);
}

async function downloadArtifactOutput(
  version: ArtifactVersion,
  file: ArtifactFile,
  setDownloadingFileId: (fileId: string | null) => void,
  setError: (message: string | null) => void,
) {
  setDownloadingFileId(file.id);
  setError(null);
  try {
    const data = await downloadArtifactFile(
      version.projectId,
      version.artifactId,
      version.id,
      file.id,
    );
    if (data.byteLength !== file.byteSize || (await sha256Hex(data)) !== file.sha256.toLowerCase()) {
      throw new Error(`${file.fileName} 与产物清单不一致，已停止下载。`);
    }
    downloadBuffer(file, data);
  } catch (reason) {
    setError(reason instanceof Error ? reason.message : "CAD 文件下载失败。");
  } finally {
    setDownloadingFileId(null);
  }
}

function downloadBuffer(file: ArtifactFile, data: ArrayBuffer) {
  const url = URL.createObjectURL(new Blob([data], { type: file.mimeType }));
  const link = document.createElement("a");
  link.href = url;
  link.download = file.fileName;
  link.click();
  URL.revokeObjectURL(url);
}
