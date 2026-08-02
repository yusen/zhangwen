import { useEffect, useRef, useState } from "react";
import {
  ACESFilmicToneMapping,
  Box3,
  Color,
  DirectionalLight,
  GridHelper,
  HemisphereLight,
  MathUtils,
  Object3D,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
  type Material,
  type Mesh,
  type Texture,
} from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface Model3DViewerProps {
  data: ArrayBuffer;
  fileName: string;
}

interface ViewControls {
  fit: () => void;
  reset: () => void;
  setMode: (mode: ViewMode) => void;
}

type ViewMode = "assembly" | "lid" | "base" | "hardware" | "exploded";

const VIEW_MODES: { id: ViewMode; label: string }[] = [
  { id: "assembly", label: "整体" },
  { id: "lid", label: "上盖" },
  { id: "base", label: "底壳" },
  { id: "hardware", label: "硬件" },
  { id: "exploded", label: "爆炸" },
];

/**
 * 本地 GLB 查看器。模型字节必须由上层通过带 capability 的 API 获取。
 */
export function Model3DViewer({ data, fileName }: Model3DViewerProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const controlsRef = useRef<ViewControls | null>(null);
  const viewModeRef = useRef<ViewMode>("assembly");
  const [error, setError] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [viewMode, setViewMode] = useState<ViewMode>("assembly");

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let disposed = false;
    let animationFrame = 0;
    let modelRoot: Object3D | null = null;
    const originalPositions = new Map<Object3D, Vector3>();
    let resizeObserver: ResizeObserver | null = null;
    setError(null);
    setReady(false);

    const scene = new Scene();
    scene.background = new Color(0xf4f6f7);
    const camera = new PerspectiveCamera(40, 1, 0.01, 100_000);
    camera.up.set(0, 0, 1);
    const renderer = new WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    renderer.outputColorSpace = SRGBColorSpace;
    renderer.toneMapping = ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.setAttribute("aria-label", `${fileName} 三维视图`);
    container.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.screenSpacePanning = true;
    controls.minDistance = 0.01;
    controls.maxDistance = 100_000;

    const grid = new GridHelper(10, 20, 0x91a0aa, 0xd5dce0);
    grid.rotateX(MathUtils.degToRad(90));
    scene.add(grid);
    scene.add(new HemisphereLight(0xffffff, 0x5f6b73, 2.2));
    const keyLight = new DirectionalLight(0xffffff, 3.1);
    keyLight.position.set(4, -6, 8);
    scene.add(keyLight);
    const fillLight = new DirectionalLight(0xddeeff, 1.4);
    fillLight.position.set(-5, 4, 2);
    scene.add(fillLight);

    const resize = () => {
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };

    const fitModel = () => {
      if (!modelRoot) return;
      modelRoot.updateMatrixWorld(true);
      const box = visibleBounds(modelRoot);
      if (box.isEmpty()) {
        setError("GLB 文件没有可显示的几何体。");
        return;
      }
      setError(null);
      const size = box.getSize(new Vector3());
      const center = box.getCenter(new Vector3());
      const radius = Math.max(size.length() / 2, 0.001);
      const verticalFov = MathUtils.degToRad(camera.fov);
      const distanceForHeight = radius / Math.tan(verticalFov / 2);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const distanceForWidth = radius / Math.tan(horizontalFov / 2);
      const distance = Math.max(distanceForHeight, distanceForWidth) * 1.25;

      controls.target.copy(center);
      camera.near = Math.max(radius / 10_000, 0.001);
      camera.far = Math.max(distance + radius * 20, 100);
      camera.position.copy(center).add(new Vector3(1, -1.25, 0.85).normalize().multiplyScalar(distance));
      camera.updateProjectionMatrix();
      controls.minDistance = Math.max(radius * 0.02, 0.001);
      controls.maxDistance = Math.max(radius * 100, distance * 4);
      controls.update();

      grid.scale.setScalar(Math.max(radius / 5, 0.01));
      grid.position.set(center.x, center.y, box.min.z);
    };

    const applyViewMode = (mode: ViewMode) => {
      if (!modelRoot) return;
      for (const part of modelRoot.children) {
        const original = originalPositions.get(part);
        if (original) part.position.copy(original);
      }
      modelRoot.updateMatrixWorld(true);
      const assemblyBounds = new Box3().setFromObject(modelRoot);
      const assemblySize = assemblyBounds.getSize(new Vector3());
      const separation = Math.max(assemblySize.length() * 0.2, 0.005);
      for (const part of modelRoot.children) {
        const name = part.name.toLowerCase();
        const isBase = name === "base";
        const isLid = name === "lid";
        const isHardware = !isBase && !isLid;
        part.visible =
          mode === "assembly" ||
          mode === "exploded" ||
          (mode === "base" && isBase) ||
          (mode === "lid" && isLid) ||
          (mode === "hardware" && isHardware);
        if (mode === "exploded" && isLid) part.position.z += separation;
      }
      fitModel();
    };

    const resetView = () => {
      applyViewMode(viewModeRef.current);
      fitModel();
    };
    controlsRef.current = { fit: fitModel, reset: resetView, setMode: applyViewMode };

    resize();
    if (typeof ResizeObserver === "function") {
      resizeObserver = new ResizeObserver(resize);
      resizeObserver.observe(container);
    } else {
      window.addEventListener("resize", resize);
    }

    const animate = () => {
      if (disposed) return;
      controls.update();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    };
    animate();

    const loader = new GLTFLoader();
    loader.parse(
      data,
      "",
      (gltf) => {
        if (disposed) {
          disposeObject(gltf.scene);
          return;
        }
        modelRoot = gltf.scene;
        for (const part of modelRoot.children) {
          originalPositions.set(part, part.position.clone());
        }
        scene.add(modelRoot);
        applyViewMode(viewModeRef.current);
        setReady(true);
      },
      () => {
        if (!disposed) setError("GLB 文件解析失败，请重新生成模型或重试加载。");
      },
    );

    return () => {
      disposed = true;
      controlsRef.current = null;
      window.cancelAnimationFrame(animationFrame);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", resize);
      controls.dispose();
      if (modelRoot) {
        scene.remove(modelRoot);
        disposeObject(modelRoot);
      }
      grid.geometry.dispose();
      disposeMaterial(grid.material);
      renderer.renderLists.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [data, fileName]);

  return (
    <section className="model3d-viewer" aria-label="三维模型查看器">
      <div className="model3d-toolbar" role="toolbar" aria-label="三维视图工具">
        <div className="model3d-view-modes" aria-label="模型显示模式">
          {VIEW_MODES.map((mode) => (
            <button
              key={mode.id}
              type="button"
              aria-pressed={viewMode === mode.id}
              disabled={!ready}
              onClick={() => {
                viewModeRef.current = mode.id;
                setViewMode(mode.id);
                controlsRef.current?.setMode(mode.id);
              }}
            >
              {mode.label}
            </button>
          ))}
        </div>
        <div className="model3d-camera-actions">
          <button type="button" onClick={() => controlsRef.current?.fit()} disabled={!ready}>
            适配模型
          </button>
          <button type="button" onClick={() => controlsRef.current?.reset()} disabled={!ready}>
            重置视图
          </button>
        </div>
      </div>
      <div ref={containerRef} className="model3d-canvas" data-testid="model3d-canvas" />
      {error && <p className="model3d-error" role="alert">{error}</p>}
    </section>
  );
}

function visibleBounds(root: Object3D): Box3 {
  const bounds = new Box3();
  for (const part of root.children) {
    if (!part.visible) continue;
    bounds.union(new Box3().setFromObject(part));
  }
  return bounds;
}

function disposeObject(root: Object3D) {
  root.traverse((object) => {
    const mesh = object as Mesh;
    mesh.geometry?.dispose();
    if (Array.isArray(mesh.material)) {
      mesh.material.forEach(disposeMaterial);
    } else if (mesh.material) {
      disposeMaterial(mesh.material);
    }
  });
}

function disposeMaterial(material: Material) {
  for (const value of Object.values(material)) {
    if (isTexture(value)) value.dispose();
  }
  material.dispose();
}

function isTexture(value: unknown): value is Texture {
  return Boolean(
    value &&
      typeof value === "object" &&
      "isTexture" in value &&
      (value as { isTexture?: unknown }).isTexture === true,
  );
}
