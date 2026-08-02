import { fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

interface RendererRecord {
  domElement: HTMLCanvasElement;
  renderCalls: number;
  disposeCalls: number;
  forceContextLossCalls: number;
  renderListDisposeCalls: number;
}

interface ControlsRecord {
  updateCalls: number;
  disposeCalls: number;
}

interface ViewerHarness {
  renderers: RendererRecord[];
  controls: ControlsRecord[];
  parseCalls: Array<{ data: ArrayBuffer; path: string }>;
  sceneFactory: (() => import("three").Object3D) | null;
}

type HarnessGlobal = typeof globalThis & {
  __ZW_MODEL3D_VIEWER_HARNESS__?: ViewerHarness;
};

vi.doMock("three", () => {
  const target = globalThis as HarnessGlobal;
  const harness = target.__ZW_MODEL3D_VIEWER_HARNESS__ ??= {
    renderers: [],
    controls: [],
    parseCalls: [],
    sceneFactory: null,
  };
  interface BoundsObject {
    children?: BoundsObject[];
    position?: { x: number; y: number; z: number };
    geometry?: {
      parameters?: { width?: number; height?: number; depth?: number };
      dispose?: () => void;
    };
    material?: { dispose?: () => void } | Array<{ dispose?: () => void }>;
    visible?: boolean;
  }

  class MockVector3 {
    constructor(
      public x = 0,
      public y = 0,
      public z = 0,
    ) {}

    set(x: number, y: number, z: number) {
      this.x = x;
      this.y = y;
      this.z = z;
      return this;
    }

    setScalar(value: number) {
      return this.set(value, value, value);
    }

    copy(value: { x: number; y: number; z: number }) {
      return this.set(value.x, value.y, value.z);
    }

    clone() {
      return new MockVector3(this.x, this.y, this.z);
    }

    add(value: { x: number; y: number; z: number }) {
      this.x += value.x;
      this.y += value.y;
      this.z += value.z;
      return this;
    }

    multiplyScalar(value: number) {
      this.x *= value;
      this.y *= value;
      this.z *= value;
      return this;
    }

    lengthSq() {
      return this.x ** 2 + this.y ** 2 + this.z ** 2;
    }

    length() {
      return Math.sqrt(this.lengthSq());
    }

    normalize() {
      const length = this.length();
      return length > 0 ? this.multiplyScalar(1 / length) : this;
    }
  }

  class MockObject3D implements BoundsObject {
    children: BoundsObject[] = [];
    position = new MockVector3();
    scale = new MockVector3(1, 1, 1);
    visible = true;
    name = "";

    add(...objects: BoundsObject[]) {
      this.children.push(...objects);
    }

    remove(object: BoundsObject) {
      this.children = this.children.filter((candidate) => candidate !== object);
    }

    traverse(callback: (object: BoundsObject) => void) {
      callback(this);
      for (const child of this.children) {
        if ("traverse" in child && typeof child.traverse === "function") {
          (child.traverse as (visit: (object: BoundsObject) => void) => void)(callback);
        } else {
          callback(child);
        }
      }
    }

    updateMatrixWorld() {}
  }

  class MockBox3 {
    min = new MockVector3(Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY);
    max = new MockVector3(Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY);

    setFromObject(root: BoundsObject) {
      this.min.set(Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY, Number.POSITIVE_INFINITY);
      this.max.set(Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY, Number.NEGATIVE_INFINITY);
      const visit = (object: BoundsObject, parent: MockVector3) => {
        const center = new MockVector3(
          parent.x + (object.position?.x ?? 0),
          parent.y + (object.position?.y ?? 0),
          parent.z + (object.position?.z ?? 0),
        );
        const parameters = object.geometry?.parameters;
        if (parameters) {
          const halfX = (parameters.width ?? 1) / 2;
          const halfY = (parameters.height ?? 1) / 2;
          const halfZ = (parameters.depth ?? 1) / 2;
          this.min.x = Math.min(this.min.x, center.x - halfX);
          this.min.y = Math.min(this.min.y, center.y - halfY);
          this.min.z = Math.min(this.min.z, center.z - halfZ);
          this.max.x = Math.max(this.max.x, center.x + halfX);
          this.max.y = Math.max(this.max.y, center.y + halfY);
          this.max.z = Math.max(this.max.z, center.z + halfZ);
        }
        for (const child of object.children ?? []) visit(child, center);
      };
      visit(root, new MockVector3());
      return this;
    }

    union(other: MockBox3) {
      this.min.x = Math.min(this.min.x, other.min.x);
      this.min.y = Math.min(this.min.y, other.min.y);
      this.min.z = Math.min(this.min.z, other.min.z);
      this.max.x = Math.max(this.max.x, other.max.x);
      this.max.y = Math.max(this.max.y, other.max.y);
      this.max.z = Math.max(this.max.z, other.max.z);
      return this;
    }

    isEmpty() {
      return this.min.x > this.max.x || this.min.y > this.max.y || this.min.z > this.max.z;
    }

    getSize(target: MockVector3) {
      return target.set(this.max.x - this.min.x, this.max.y - this.min.y, this.max.z - this.min.z);
    }

    getCenter(target: MockVector3) {
      return target.set(
        (this.min.x + this.max.x) / 2,
        (this.min.y + this.max.y) / 2,
        (this.min.z + this.max.z) / 2,
      );
    }
  }

  class MockPerspectiveCamera extends MockObject3D {
    up = new MockVector3();
    aspect = 1;
    near: number;
    far: number;

    constructor(public fov: number, _aspect: number, near: number, far: number) {
      super();
      this.near = near;
      this.far = far;
    }

    updateProjectionMatrix() {}
  }

  class MockGridHelper extends MockObject3D {
    geometry = { dispose: () => undefined };
    material = { dispose: () => undefined };
    rotateX() {}
  }

  class MockLight extends MockObject3D {}

  class MockWebGLRenderer {
    readonly record: RendererRecord = {
      domElement: document.createElement("canvas"),
      renderCalls: 0,
      disposeCalls: 0,
      forceContextLossCalls: 0,
      renderListDisposeCalls: 0,
    };
    readonly domElement = this.record.domElement;
    readonly renderLists = {
      dispose: () => {
        this.record.renderListDisposeCalls += 1;
      },
    };
    readonly render = () => {
      this.record.renderCalls += 1;
    };
    readonly dispose = () => {
      this.record.disposeCalls += 1;
    };
    readonly forceContextLoss = () => {
      this.record.forceContextLossCalls += 1;
    };
    readonly setPixelRatio = () => undefined;
    readonly setSize = () => undefined;
    outputColorSpace: unknown;
    toneMapping: unknown;
    toneMappingExposure = 1;

    constructor() {
      harness.renderers.push(this.record);
    }
  }

  return {
    ACESFilmicToneMapping: 1,
    Box3: MockBox3,
    Color: class MockColor {
      constructor(_value: number) {}
    },
    DirectionalLight: MockLight,
    GridHelper: MockGridHelper,
    HemisphereLight: MockLight,
    MathUtils: { degToRad: (degrees: number) => (degrees * Math.PI) / 180 },
    Object3D: MockObject3D,
    PerspectiveCamera: MockPerspectiveCamera,
    Scene: MockObject3D,
    SRGBColorSpace: "srgb",
    Vector3: MockVector3,
    WebGLRenderer: MockWebGLRenderer,
  };
});

vi.doMock("three/examples/jsm/controls/OrbitControls.js", () => ({
  OrbitControls: class MockOrbitControls {
    readonly record: ControlsRecord = { updateCalls: 0, disposeCalls: 0 };
    readonly update = () => {
      this.record.updateCalls += 1;
    };
    readonly dispose = () => {
      this.record.disposeCalls += 1;
    };
    readonly target = { copy: () => undefined };
    enableDamping = false;
    dampingFactor = 0;
    screenSpacePanning = false;
    minDistance = 0;
    maxDistance = 0;

    constructor() {
      const target = globalThis as HarnessGlobal;
      const harness = target.__ZW_MODEL3D_VIEWER_HARNESS__ ??= {
        renderers: [],
        controls: [],
        parseCalls: [],
        sceneFactory: null,
      };
      harness.controls.push(this.record);
    }
  },
}));

vi.doMock("three/examples/jsm/loaders/GLTFLoader.js", () => ({
  GLTFLoader: class MockGLTFLoader {
    parse(
      data: ArrayBuffer,
      path: string,
      onLoad: (gltf: { scene: import("three").Object3D }) => void,
      onError: (reason: unknown) => void,
    ) {
      const target = globalThis as HarnessGlobal;
      const harness = target.__ZW_MODEL3D_VIEWER_HARNESS__ ??= {
        renderers: [],
        controls: [],
        parseCalls: [],
        sceneFactory: null,
      };
      harness.parseCalls.push({ data, path });
      if (!harness.sceneFactory) {
        onError(new Error("missing test scene"));
        return;
      }
      onLoad({ scene: harness.sceneFactory() });
    }
  },
}));

let viewerHarness: ViewerHarness;
let Model3DViewer: typeof import("../components/floating/Model3DViewer").Model3DViewer;

beforeAll(async () => {
  ({ Model3DViewer } = await import("../components/floating/Model3DViewer"));
  const harness = (globalThis as HarnessGlobal).__ZW_MODEL3D_VIEWER_HARNESS__;
  if (!harness) throw new Error("Model3DViewer test harness was not initialized.");
  viewerHarness = harness;
});

beforeEach(() => {
  viewerHarness.renderers.length = 0;
  viewerHarness.controls.length = 0;
  viewerHarness.parseCalls.length = 0;
  viewerHarness.sceneFactory = null;
});

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("Three.js CAD 查看器", () => {
  it("提供五种稳定视图并在卸载时释放模型、控制器和 WebGL 上下文", async () => {
    const three = await vi.importActual<typeof import("three")>("three");
    const base = part(three, "base", [0, 0, 0]);
    const lid = part(three, "lid", [0, 0, 0.045]);
    const hardware = part(three, "ultrasonic", [0.035, 0, 0.02]);
    const modelRoot = new three.Object3D();
    modelRoot.add(base.mesh, lid.mesh, hardware.mesh);
    viewerHarness.sceneFactory = () => modelRoot;

    const requestAnimationFrame = vi.fn(() => 71);
    const cancelAnimationFrame = vi.fn();
    const resizeDisconnect = vi.fn();
    vi.stubGlobal("requestAnimationFrame", requestAnimationFrame);
    vi.stubGlobal("cancelAnimationFrame", cancelAnimationFrame);
    vi.stubGlobal(
      "ResizeObserver",
      class MockResizeObserver {
        observe() {}
        disconnect() {
          resizeDisconnect();
        }
      },
    );

    const view = render(
      <Model3DViewer
        data={Uint8Array.from([0x67, 0x6c, 0x54, 0x46]).buffer}
        fileName="assembly.glb"
      />,
    );

    const toolbar = await screen.findByRole("toolbar", { name: "三维视图工具" });
    const modes = ["整体", "上盖", "底壳", "硬件", "爆炸"];
    for (const label of modes) {
      expect(within(toolbar).getByRole("button", { name: label })).toBeEnabled();
    }
    expect(within(toolbar).getByRole("button", { name: "整体" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(viewerHarness.parseCalls).toHaveLength(1);
    expect(screen.getByLabelText("assembly.glb 三维视图")).toBeInTheDocument();

    fireEvent.click(within(toolbar).getByRole("button", { name: "上盖" }));
    expect(base.mesh.visible).toBe(false);
    expect(lid.mesh.visible).toBe(true);
    expect(hardware.mesh.visible).toBe(false);

    fireEvent.click(within(toolbar).getByRole("button", { name: "底壳" }));
    expect(base.mesh.visible).toBe(true);
    expect(lid.mesh.visible).toBe(false);
    expect(hardware.mesh.visible).toBe(false);

    fireEvent.click(within(toolbar).getByRole("button", { name: "硬件" }));
    expect(base.mesh.visible).toBe(false);
    expect(lid.mesh.visible).toBe(false);
    expect(hardware.mesh.visible).toBe(true);

    fireEvent.click(within(toolbar).getByRole("button", { name: "整体" }));
    expect(base.mesh.visible).toBe(true);
    expect(lid.mesh.visible).toBe(true);
    expect(hardware.mesh.visible).toBe(true);

    const basePosition = base.mesh.position.toArray();
    const lidPosition = lid.mesh.position.toArray();
    const hardwarePosition = hardware.mesh.position.toArray();
    fireEvent.click(within(toolbar).getByRole("button", { name: "爆炸" }));
    expect(within(toolbar).getByRole("button", { name: "爆炸" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(lid.mesh.position.x).toBe(lidPosition[0]);
    expect(lid.mesh.position.y).toBe(lidPosition[1]);
    expect(lid.mesh.position.z).toBeGreaterThan(lidPosition[2]);
    expect(lid.mesh.position.z - lidPosition[2]).toBeLessThan(0.1);
    expect(base.mesh.position.toArray()).toEqual(basePosition);
    expect(hardware.mesh.position.toArray()).toEqual(hardwarePosition);

    const firstExplodedPosition = lid.mesh.position.toArray();
    fireEvent.click(within(toolbar).getByRole("button", { name: "爆炸" }));
    expect(lid.mesh.position.toArray()).toEqual(firstExplodedPosition);
    expect(base.mesh.position.toArray()).toEqual(basePosition);
    expect(hardware.mesh.position.toArray()).toEqual(hardwarePosition);

    fireEvent.click(within(toolbar).getByRole("button", { name: "整体" }));
    expect(base.mesh.position.toArray()).toEqual(basePosition);
    expect(lid.mesh.position.toArray()).toEqual(lidPosition);
    expect(hardware.mesh.position.toArray()).toEqual(hardwarePosition);

    const renderer = viewerHarness.renderers[0];
    const controls = viewerHarness.controls[0];
    expect(renderer).toBeDefined();
    expect(controls).toBeDefined();
    expect(requestAnimationFrame).toHaveBeenCalled();
    view.unmount();

    expect(cancelAnimationFrame).toHaveBeenCalledWith(71);
    expect(resizeDisconnect).toHaveBeenCalledTimes(1);
    expect(controls?.disposeCalls).toBe(1);
    expect(renderer?.renderListDisposeCalls).toBe(1);
    expect(renderer?.disposeCalls).toBe(1);
    expect(renderer?.forceContextLossCalls).toBe(1);
    expect(renderer?.domElement.isConnected).toBe(false);
    for (const disposable of [base, lid, hardware]) {
      expect(disposable.geometryDispose).toHaveBeenCalledTimes(1);
      expect(disposable.materialDispose).toHaveBeenCalledTimes(1);
    }
  });
});

function part(
  three: typeof import("three"),
  name: string,
  position: [number, number, number],
) {
  const geometry = new three.BoxGeometry(0.04, 0.04, 0.02);
  const material = new three.MeshBasicMaterial();
  const geometryDispose = vi.spyOn(geometry, "dispose");
  const materialDispose = vi.spyOn(material, "dispose");
  const mesh = new three.Mesh(geometry, material);
  mesh.name = name;
  mesh.position.set(...position);
  return { mesh, geometryDispose, materialDispose };
}
