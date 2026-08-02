import { useEffect, useRef, useState } from "react";
import type { MechanicalProfileSummary } from "@zhangwen/contracts";
import {
  ACESFilmicToneMapping,
  Box3,
  BoxGeometry,
  Color,
  CylinderGeometry,
  DirectionalLight,
  EdgesGeometry,
  GridHelper,
  Group,
  HemisphereLight,
  LineBasicMaterial,
  LineSegments,
  MathUtils,
  Mesh,
  MeshStandardMaterial,
  Object3D,
  PerspectiveCamera,
  Scene,
  SRGBColorSpace,
  Vector3,
  WebGLRenderer,
  type Material,
} from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { RoundedBoxGeometry } from "three/examples/jsm/geometries/RoundedBoxGeometry.js";

interface MechanicalProfilePreviewProps {
  profile: MechanicalProfileSummary;
}

interface PreviewControls {
  fit: () => void;
  reset: () => void;
}

const MODEL_KIND_LABELS: Record<MechanicalProfileSummary["modelKind"], string> = {
  envelope: "通用机械包络",
  unihiker_k10: "行空板 K10 受信模型",
  unihiker_ultrasonic_distance_sensor: "行空板超声波传感器受信模型",
};

/**
 * 由已校验的机械快照绘制示意几何。这里不读取或执行 Hardware Skill Python。
 */
export function MechanicalProfilePreview({ profile }: MechanicalProfilePreviewProps) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const controlsRef = useRef<PreviewControls | null>(null);
  const [ready, setReady] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    let renderer: WebGLRenderer;
    try {
      renderer = new WebGLRenderer({ antialias: true, powerPreference: "high-performance" });
    } catch {
      setError("当前环境无法初始化 3D 预览，但机械档案数据仍可用于结构建模。");
      setReady(false);
      return;
    }

    let disposed = false;
    let animationFrame = 0;
    let resizeObserver: ResizeObserver | null = null;
    setError(null);
    setReady(false);

    const scene = new Scene();
    scene.background = new Color(0xf4f6f7);
    const camera = new PerspectiveCamera(42, 1, 0.01, 100_000);
    camera.up.set(0, 0, 1);
    renderer.outputColorSpace = SRGBColorSpace;
    renderer.toneMapping = ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.05;
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.domElement.setAttribute("aria-label", `${profile.displayName} 机械档案三维视图`);
    container.appendChild(renderer.domElement);

    const orbit = new OrbitControls(camera, renderer.domElement);
    orbit.enableDamping = true;
    orbit.dampingFactor = 0.08;
    orbit.screenSpacePanning = true;

    scene.add(new HemisphereLight(0xffffff, 0x5f6b73, 2.2));
    const keyLight = new DirectionalLight(0xffffff, 3.2);
    keyLight.position.set(4, -6, 8);
    scene.add(keyLight);
    const fillLight = new DirectionalLight(0xddeeff, 1.3);
    fillLight.position.set(-5, 4, 3);
    scene.add(fillLight);

    const model = buildProfilePreview(profile);
    scene.add(model);
    const footprint = Math.max(profile.dimensions.length_x, profile.dimensions.width_y, 1);
    const grid = new GridHelper(footprint * 3, 24, 0x91a0aa, 0xd5dce0);
    grid.rotateX(MathUtils.degToRad(90));
    grid.position.z = -0.02;
    scene.add(grid);

    const resize = () => {
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
    };

    const fit = () => {
      const bounds = new Box3().setFromObject(model);
      if (bounds.isEmpty()) {
        setError("机械档案没有可显示的有效几何范围。");
        return;
      }
      const size = bounds.getSize(new Vector3());
      const center = bounds.getCenter(new Vector3());
      const radius = Math.max(size.length() / 2, 0.001);
      const verticalFov = MathUtils.degToRad(camera.fov);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const distance = Math.max(
        radius / Math.tan(verticalFov / 2),
        radius / Math.tan(horizontalFov / 2),
      ) * 1.35;
      orbit.target.copy(center);
      camera.near = Math.max(radius / 10_000, 0.001);
      camera.far = Math.max(distance + radius * 20, 100);
      camera.position
        .copy(center)
        .add(new Vector3(1, -1.25, 0.9).normalize().multiplyScalar(distance));
      camera.updateProjectionMatrix();
      orbit.update();
      setError(null);
    };

    const reset = () => fit();
    controlsRef.current = { fit, reset };
    resize();
    fit();
    setReady(true);

    if (typeof ResizeObserver === "function") {
      resizeObserver = new ResizeObserver(() => {
        resize();
        fit();
      });
      resizeObserver.observe(container);
    } else {
      window.addEventListener("resize", resize);
    }

    const animate = () => {
      if (disposed) return;
      orbit.update();
      renderer.render(scene, camera);
      animationFrame = window.requestAnimationFrame(animate);
    };
    animate();

    return () => {
      disposed = true;
      controlsRef.current = null;
      window.cancelAnimationFrame(animationFrame);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", resize);
      orbit.dispose();
      disposeObject(model);
      grid.geometry.dispose();
      disposeMaterial(grid.material);
      renderer.renderLists.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      renderer.domElement.remove();
    };
  }, [profile]);

  return (
    <article className="mechanical-profile-preview" aria-label="机械档案 3D 预览">
      <dl className="mechanical-profile-preview-metadata">
        <div>
          <dt>档案</dt>
          <dd>{profile.profileId}</dd>
        </div>
        <div>
          <dt>版本</dt>
          <dd>{profile.revision}</dd>
        </div>
        <div>
          <dt>外形</dt>
          <dd>{formatDimensions(profile)} mm</dd>
        </div>
        <div>
          <dt>几何类型</dt>
          <dd>{MODEL_KIND_LABELS[profile.modelKind]}</dd>
        </div>
        <div>
          <dt>描述实体</dt>
          <dd>{profile.previewGeometry?.primitives.length ?? 0}</dd>
        </div>
      </dl>
      <section className="model3d-viewer" aria-label="机械档案三维查看器">
        <div className="model3d-toolbar" role="toolbar" aria-label="机械档案三维视图工具">
          <div className="mechanical-profile-preview-legend" aria-label="预览图例">
            <span><i className="is-envelope" />器件包络</span>
            <span><i className="is-hole" />安装孔</span>
            <span><i className="is-opening" />接口开口</span>
            <span><i className="is-keepout" />禁布区</span>
          </div>
          <div className="model3d-camera-actions">
            <button type="button" disabled={!ready} onClick={() => controlsRef.current?.fit()}>
              适配模型
            </button>
            <button type="button" disabled={!ready} onClick={() => controlsRef.current?.reset()}>
              重置视图
            </button>
          </div>
        </div>
        <div ref={containerRef} className="model3d-canvas" data-testid="mechanical-profile-canvas" />
        {error && <p className="model3d-error" role="alert">{error}</p>}
      </section>
      <p className="floating-note">
        {profile.previewGeometry
          ? "此预览按 mechanical.md 中已编译并校验的声明式实体生成；制造级模型仍以确认后的 CAD 产物为准。"
          : "当前档案没有由自然描述编译出的声明式实体，因此仅显示包络、孔、开口和禁布区。"}
      </p>
    </article>
  );
}

function buildProfilePreview(profile: MechanicalProfileSummary): Group {
  const group = new Group();
  group.name = profile.profileId;
  const { length_x: length, width_y: width, height_z: height } = profile.dimensions;
  if (profile.previewGeometry) {
    for (const primitive of profile.previewGeometry.primitives) {
      const marker = buildDeclarativePrimitive(primitive);
      group.add(marker);
      const outline = new LineSegments(
        new EdgesGeometry(marker.geometry),
        new LineBasicMaterial({ color: 0x263238 }),
      );
      outline.position.copy(marker.position);
      outline.rotation.copy(marker.rotation);
      group.add(outline);
    }
  } else {
    const envelopeMaterial = new MeshStandardMaterial({ color: 0x2f7ac8, roughness: 0.62 });
    const envelope = new Mesh(new BoxGeometry(length, width, height), envelopeMaterial);
    envelope.name = "component_envelope";
    envelope.position.z = height / 2;
    group.add(envelope);
    const outline = new LineSegments(
      new EdgesGeometry(envelope.geometry),
      new LineBasicMaterial({ color: 0x153a5c }),
    );
    outline.position.copy(envelope.position);
    group.add(outline);
  }

  const holeMaterial = new MeshStandardMaterial({ color: 0x2b3136, roughness: 0.8 });
  for (const hole of profile.mountingHoles) {
    const marker = new Mesh(
      new CylinderGeometry(hole.diameter / 2, hole.diameter / 2, height + 0.5, 32),
      holeMaterial,
    );
    marker.name = `mounting_hole_${hole.hole_id}`;
    marker.rotation.x = Math.PI / 2;
    marker.position.set(hole.center.x, hole.center.y, height / 2);
    group.add(marker);
  }

  const openingMaterial = new MeshStandardMaterial({
    color: 0xe99028,
    emissive: 0x3b2207,
    transparent: true,
    opacity: 0.88,
  });
  for (const opening of profile.openings) {
    const marker = opening.kind === "circle"
      ? new Mesh(
          new CylinderGeometry(
            Math.max((opening.diameter ?? 1) / 2, 0.1),
            Math.max((opening.diameter ?? 1) / 2, 0.1),
            Math.max(height * 0.08, 0.3),
            32,
          ),
          openingMaterial,
        )
      : new Mesh(
          new BoxGeometry(
            Math.max(opening.size_u ?? 1, 0.1),
            Math.max(opening.size_v ?? 1, 0.1),
            Math.max(height * 0.08, 0.3),
          ),
          openingMaterial,
        );
    marker.name = `opening_${opening.opening_id}`;
    if (opening.kind === "circle") marker.rotation.x = Math.PI / 2;
    marker.position.set(
      opening.center.x,
      opening.center.y,
      opening.center_z ?? height + 0.15,
    );
    group.add(marker);
  }

  const keepoutMaterial = new MeshStandardMaterial({
    color: 0xd64b4b,
    transparent: true,
    opacity: 0.28,
    depthWrite: false,
  });
  for (const keepout of profile.keepouts) {
    const marker = new Mesh(
      new BoxGeometry(
        keepout.size.length_x,
        keepout.size.width_y,
        keepout.size.height_z,
      ),
      keepoutMaterial,
    );
    marker.name = `keepout_${keepout.keepout_id}`;
    marker.position.set(keepout.center.x, keepout.center.y, keepout.center.z);
    group.add(marker);
  }
  return group;
}

function buildDeclarativePrimitive(
  primitive: NonNullable<MechanicalProfileSummary["previewGeometry"]>["primitives"][number],
): Mesh {
  const color = {
    body: 0x607d8b,
    pcb: 0x278a55,
    connector: 0xe6e9ed,
    sensor: 0x3949ab,
    feature: 0xf1a53a,
  }[primitive.role];
  const material = new MeshStandardMaterial({
    color,
    roughness: primitive.role === "connector" ? 0.35 : 0.66,
    metalness: primitive.role === "connector" ? 0.18 : 0.02,
    transparent: primitive.operation === "cut",
    opacity: primitive.operation === "cut" ? 0.36 : 1,
  });
  let geometry: BoxGeometry | CylinderGeometry | RoundedBoxGeometry;
  if (primitive.kind === "cylinder") {
    const radius = Math.max((primitive.diameter ?? 1) / 2, 0.05);
    geometry = new CylinderGeometry(radius, radius, primitive.height ?? 1, 48);
  } else {
    const size = primitive.size ?? { length_x: 1, width_y: 1, height_z: 1 };
    geometry = primitive.kind === "rounded_box"
      ? new RoundedBoxGeometry(
          size.length_x,
          size.width_y,
          size.height_z,
          4,
          primitive.corner_radius,
        )
      : new BoxGeometry(size.length_x, size.width_y, size.height_z);
  }
  const mesh = new Mesh(geometry, material);
  mesh.name = `declarative_${primitive.primitive_id}`;
  if (primitive.kind === "cylinder") mesh.rotation.x = Math.PI / 2;
  mesh.rotation.z += MathUtils.degToRad(primitive.rotation_z_deg);
  mesh.position.set(primitive.center.x, primitive.center.y, primitive.center.z);
  return mesh;
}

function formatDimensions(profile: MechanicalProfileSummary): string {
  const { length_x, width_y, height_z } = profile.dimensions;
  return [length_x, width_y, height_z]
    .map((value) => Number.isInteger(value) ? String(value) : String(Number(value.toFixed(3))))
    .join(" × ");
}

function disposeObject(root: Object3D) {
  root.traverse((object) => {
    if (!(object instanceof Mesh) && !(object instanceof LineSegments)) return;
    object.geometry.dispose();
    disposeMaterial(object.material);
  });
}

function disposeMaterial(material: Material | Material[]) {
  const materials = Array.isArray(material) ? material : [material];
  for (const item of materials) item.dispose();
}
