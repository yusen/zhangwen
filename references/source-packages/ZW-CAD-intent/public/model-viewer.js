import * as THREE from '/vendor/three/build/three.module.js';
import { OrbitControls } from '/vendor/three/examples/jsm/controls/OrbitControls.js';
import { GLTFLoader } from '/vendor/three/examples/jsm/loaders/GLTFLoader.js';
import { STLLoader } from '/vendor/three/examples/jsm/loaders/STLLoader.js';

const DEFAULT_MATERIAL = new THREE.MeshStandardMaterial({
  color: 0xd9e1e5,
  roughness: 0.72,
  metalness: 0.05,
});

const STL_MATERIALS = {
  assembly: new THREE.MeshStandardMaterial({ color: 0xd7dee3, roughness: 0.72, metalness: 0.05 }),
  base: new THREE.MeshStandardMaterial({ color: 0xaebbc3, roughness: 0.78, metalness: 0.03 }),
  lid: new THREE.MeshStandardMaterial({ color: 0xf2f5f6, roughness: 0.62, metalness: 0.03, transparent: true, opacity: 0.82 }),
  hardware: new THREE.MeshStandardMaterial({ color: 0x6ca27c, roughness: 0.7, metalness: 0.02 }),
  openings: new THREE.MeshStandardMaterial({ color: 0xd94a3a, roughness: 0.68, metalness: 0.02 }),
  mounts: new THREE.MeshStandardMaterial({ color: 0xe4b84d, roughness: 0.72, metalness: 0.02 }),
};

const SCENE_MATERIALS = {
  base: new THREE.MeshStandardMaterial({ color: 0xc6d0d7, roughness: 0.78, metalness: 0.03 }),
  lid: new THREE.MeshStandardMaterial({ color: 0xf4f7f8, roughness: 0.62, metalness: 0.03, transparent: true, opacity: 0.84 }),
  mount: new THREE.MeshStandardMaterial({ color: 0xe4b84d, roughness: 0.72, metalness: 0.02 }),
  opening: new THREE.MeshStandardMaterial({ color: 0xd94a3a, roughness: 0.68, metalness: 0.02, transparent: true, opacity: 0.72 }),
  pcb: new THREE.MeshStandardMaterial({ color: 0x1f8a5b, roughness: 0.8, metalness: 0.02 }),
  component: new THREE.MeshStandardMaterial({ color: 0x2f3f46, roughness: 0.7, metalness: 0.04 }),
  connector: new THREE.MeshStandardMaterial({ color: 0xb7c1c8, roughness: 0.42, metalness: 0.25 }),
  screen: new THREE.MeshStandardMaterial({ color: 0x1c3442, roughness: 0.4, metalness: 0.02 }),
  button: new THREE.MeshStandardMaterial({ color: 0xd2a04b, roughness: 0.62, metalness: 0.03 }),
  sensor: new THREE.MeshStandardMaterial({ color: 0xd48664, roughness: 0.7, metalness: 0.02 }),
  battery: new THREE.MeshStandardMaterial({ color: 0x5c6870, roughness: 0.68, metalness: 0.08 }),
};

const EXPLODED_LID_LIFT_RATIO = 0.42;
const EXPLODED_LID_LIFT_MIN = 12;
const AXIS_GIZMO_SIZE = 88;

export function createModelViewer(container, options = {}) {
  const status = typeof options.onStatus === 'function' ? options.onStatus : () => {};
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setClearColor(0x000000, 0);
  container.appendChild(renderer.domElement);
  const axisGizmo = createAxisGizmo(container);

  const scene = new THREE.Scene();
  scene.up.set(0, 0, 1);

  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 10000);
  camera.up.set(0, 0, 1);
  camera.position.set(120, -140, 90);

  const controls = new OrbitControls(camera, renderer.domElement);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.screenSpacePanning = false;
  controls.minDistance = 6;
  controls.maxDistance = 3000;

  const root = new THREE.Group();
  root.name = 'zwcad-model-root';
  scene.add(root);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x7d8790, 2.5));
  const keyLight = new THREE.DirectionalLight(0xffffff, 2.4);
  keyLight.position.set(120, -160, 180);
  scene.add(keyLight);
  const fillLight = new THREE.DirectionalLight(0xffffff, 0.8);
  fillLight.position.set(-120, 100, 90);
  scene.add(fillLight);

  const grid = new THREE.GridHelper(220, 22, 0xb8c3ca, 0xd9e0e4);
  grid.rotateX(Math.PI / 2);
  grid.material.opacity = 0.38;
  grid.material.transparent = true;
  scene.add(grid);

  const axes = new THREE.AxesHelper(28);
  scene.add(axes);

  const gltfLoader = new GLTFLoader();
  const stlLoader = new STLLoader();
  const resizeObserver = new ResizeObserver(resize);
  let currentAbortController = null;
  let currentSource = null;
  let disposed = false;

  resizeObserver.observe(container);
  window.addEventListener('resize', resize);
  resize();
  animate();

  async function load(source) {
    if (!source?.url) {
      clearModel();
      currentSource = null;
      status({ type: 'empty', message: 'No 3D model source available.' });
      return;
    }
    const nextSource = {
      url: source.url,
      format: normalizeFormat(source.format),
      mode: source.mode || 'assembly',
      label: source.label || source.url,
      parts: Array.isArray(source.parts) ? source.parts : [],
    };
    if (currentSource
      && currentSource.url === nextSource.url
      && currentSource.mode === nextSource.mode
      && currentSource.format === nextSource.format) {
      status({ type: 'ready', message: nextSource.label });
      return;
    }
    currentSource = nextSource;
    if (currentAbortController) currentAbortController.abort();
    currentAbortController = new AbortController();
    const signal = currentAbortController.signal;
    status({ type: 'loading', message: `Loading ${nextSource.label}` });
    try {
      const object = await loadObject(nextSource, signal);
      if (signal.aborted) {
        disposeObject(object);
        return;
      }
      clearModel();
      root.add(object);
      frameObject(object);
      status({ type: 'ready', message: nextSource.label });
    } catch (error) {
      if (signal.aborted) return;
      clearModel();
      status({
        type: 'error',
        message: error instanceof Error ? error.message : String(error),
      });
      throw error;
    }
  }

  async function loadScene(sceneData, mode = 'assembly') {
    if (!sceneData || typeof sceneData !== 'object') {
      clearModel();
      currentSource = null;
      status({ type: 'empty', message: 'No layout scene available.' });
      return;
    }
    const nextSource = {
      url: `layout_scene:${sceneData.id || 'scene_preview'}`,
      format: 'layout_scene',
      mode: normalizePreviewMode(mode),
      label: `layout scene ${normalizePreviewMode(mode)}`,
    };
    if (currentSource
      && currentSource.url === nextSource.url
      && currentSource.mode === nextSource.mode
      && currentSource.format === nextSource.format) {
      status({ type: 'ready', message: nextSource.label });
      return;
    }
    currentSource = nextSource;
    if (currentAbortController) currentAbortController.abort();
    currentAbortController = null;
    status({ type: 'loading', message: nextSource.label });
    const object = buildSceneObject(sceneData, nextSource.mode);
    clearModel();
    root.add(object);
    frameObject(object);
    status({ type: 'ready', message: nextSource.label });
  }

  function resetView() {
    const object = root.children[0];
    if (object) frameObject(object);
  }

  function clear() {
    if (currentAbortController) currentAbortController.abort();
    currentAbortController = null;
    currentSource = null;
    clearModel();
  }

  function setZoom(value) {
    const zoom = Math.min(2.2, Math.max(0.45, Number(value) || 1));
    camera.zoom = zoom;
    camera.updateProjectionMatrix();
  }

  function dispose() {
    disposed = true;
    if (currentAbortController) currentAbortController.abort();
    resizeObserver.disconnect();
    window.removeEventListener('resize', resize);
    clearModel();
    axisGizmo.dispose();
    renderer.dispose();
    container.removeChild(renderer.domElement);
  }

  async function loadObject(source, signal) {
    if (source.format === 'cadquery_parts') {
      return loadCadqueryParts(source, signal);
    }
    if (source.format === 'gltf' || source.url.endsWith('.gltf') || source.url.endsWith('.glb')) {
      return loadGltf(source.url, signal);
    }
    if (source.format === 'stl' || source.url.endsWith('.stl')) {
      return loadStl(source, signal);
    }
    throw new Error(`Unsupported 3D model format: ${source.format || source.url}`);
  }

  async function loadGltf(url, signal) {
    const gltf = await gltfLoader.loadAsync(url);
    if (signal.aborted) {
      disposeObject(gltf.scene);
      return new THREE.Group();
    }
    gltf.scene.traverse((child) => {
      if (!child.isMesh) return;
      child.castShadow = false;
      child.receiveShadow = true;
      if (!child.material) child.material = DEFAULT_MATERIAL.clone();
    });
    return gltf.scene;
  }

  async function loadStl(source, signal) {
    const geometry = await stlLoader.loadAsync(source.url);
    if (signal.aborted) {
      geometry.dispose();
      return new THREE.Group();
    }
    geometry.computeVertexNormals();
    const material = (STL_MATERIALS[source.mode] || STL_MATERIALS.assembly).clone();
    const mesh = new THREE.Mesh(geometry, material);
    mesh.name = source.label || 'STL model';
    mesh.castShadow = false;
    mesh.receiveShadow = true;
    return mesh;
  }

  async function loadCadqueryParts(source, signal) {
    const group = new THREE.Group();
    group.name = source.label || 'CadQuery parts';
    const parts = Array.isArray(source.parts) ? source.parts : [];
    const loaded = await Promise.all(parts.map(async (part) => {
      const mesh = await loadStl(part, signal);
      mesh.name = part.label || part.id || mesh.name;
      mesh.position.add(partOffsetForMode(part.mode, source.mode));
      return mesh;
    }));
    if (signal.aborted) {
      loaded.forEach(disposeObject);
      return new THREE.Group();
    }
    loaded.forEach((mesh) => group.add(mesh));
    return group;
  }

  function frameObject(object) {
    const box = new THREE.Box3().setFromObject(object);
    if (box.isEmpty()) return;
    const center = box.getCenter(new THREE.Vector3());
    const size = box.getSize(new THREE.Vector3());
    const maxSize = Math.max(size.x, size.y, size.z, 1);
    const distance = maxSize / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov) / 2));
    const viewDistance = distance * 1.65;
    const direction = new THREE.Vector3(0.82, -1, 0.64).normalize();

    controls.target.copy(center);
    camera.near = Math.max(0.1, maxSize / 1200);
    camera.far = Math.max(2000, maxSize * 24);
    camera.position.copy(center).add(direction.multiplyScalar(viewDistance));
    camera.updateProjectionMatrix();
    controls.update();
  }

  function clearModel() {
    while (root.children.length) {
      const child = root.children.pop();
      disposeObject(child);
    }
  }

  function resize() {
    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight);
    renderer.setSize(width, height, false);
    camera.aspect = width / height;
    camera.updateProjectionMatrix();
  }

  function animate() {
    if (disposed) return;
    controls.update();
    renderer.render(scene, camera);
    axisGizmo.render(camera);
    window.requestAnimationFrame(animate);
  }

  return {
    load,
    loadScene,
    clear,
    resetView,
    setZoom,
    dispose,
  };
}

function disposeObject(object) {
  object.traverse?.((child) => {
    if (child.geometry) child.geometry.dispose();
    disposeMaterial(child.material);
  });
}

function disposeMaterial(material) {
  if (!material) return;
  if (Array.isArray(material)) {
    material.forEach(disposeMaterial);
    return;
  }
  for (const value of Object.values(material)) {
    if (value?.isTexture) value.dispose();
  }
  material.dispose?.();
}

function createAxisGizmo(container) {
  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(AXIS_GIZMO_SIZE, AXIS_GIZMO_SIZE, false);
  renderer.setClearColor(0x000000, 0);
  renderer.domElement.className = 'axis-gizmo';
  renderer.domElement.setAttribute('aria-hidden', 'true');
  container.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
  camera.position.set(0, 0, 6);
  camera.lookAt(0, 0, 0);
  scene.add(new THREE.AmbientLight(0xffffff, 2.6));

  const group = new THREE.Group();
  scene.add(group);
  group.add(makeAxisArrow('X', 0xff4f4f, new THREE.Vector3(1, 0, 0)));
  group.add(makeAxisArrow('Y', 0x31a354, new THREE.Vector3(0, 1, 0)));
  group.add(makeAxisArrow('Z', 0x3b82f6, new THREE.Vector3(0, 0, 1)));

  return {
    render(mainCamera) {
      group.quaternion.copy(mainCamera.quaternion).invert();
      renderer.render(scene, camera);
    },
    dispose() {
      disposeObject(group);
      renderer.dispose();
      container.removeChild(renderer.domElement);
    },
  };
}

function makeAxisArrow(label, color, direction) {
  const group = new THREE.Group();
  const length = 1.7;
  const origin = new THREE.Vector3(0, 0, 0);
  const arrow = new THREE.ArrowHelper(direction.clone().normalize(), origin, length, color, 0.42, 0.2);
  group.add(arrow);
  const sprite = makeAxisLabel(label, color);
  sprite.position.copy(direction.clone().normalize().multiplyScalar(length + 0.38));
  group.add(sprite);
  return group;
}

function makeAxisLabel(label, color) {
  const canvas = document.createElement('canvas');
  canvas.width = 64;
  canvas.height = 64;
  const context = canvas.getContext('2d');
  context.clearRect(0, 0, canvas.width, canvas.height);
  context.fillStyle = `#${color.toString(16).padStart(6, '0')}`;
  context.font = '700 36px Segoe UI, Arial, sans-serif';
  context.textAlign = 'center';
  context.textBaseline = 'middle';
  context.fillText(label, 32, 34);
  const texture = new THREE.CanvasTexture(canvas);
  const material = new THREE.SpriteMaterial({ map: texture, transparent: true });
  const sprite = new THREE.Sprite(material);
  sprite.scale.set(0.55, 0.55, 0.55);
  return sprite;
}

function buildSceneObject(sceneData = {}, mode = 'assembly') {
  const group = new THREE.Group();
  group.name = `layout_scene_${mode}`;
  const enclosure = sceneData.enclosure || {};
  const outer = enclosure.outer_box_size || {};
  const inner = enclosure.inner_box_size || {};
  const outerLength = numberOr(outer.length_x, 80);
  const outerWidth = numberOr(outer.width_y, 50);
  const outerHeight = numberOr(outer.height_z, 24);
  const innerHeight = numberOr(inner.height_z, Math.max(8, outerHeight - 5));
  const wallThickness = Math.max(0.6, numberOr(enclosure.wall_thickness, Math.max(1.2, (outerLength - numberOr(inner.length_x, outerLength - 2.4)) / 2)));
  const floorThickness = Math.max(0.6, numberOr(enclosure.floor_thickness, wallThickness));
  const lidThickness = Math.max(1.2, numberOr(enclosure.lid_thickness, outerHeight - innerHeight));
  const baseHeight = Math.max(2, outerHeight - lidThickness);
  const show = new Set(sceneData.modes?.[mode]?.show || modeShowList(mode));
  const exploded = Boolean(sceneData.modes?.[mode]?.explode || mode === 'exploded');
  const baseOffset = new THREE.Vector3();
  const lidOffset = exploded ? lidLiftOffset(outerHeight) : new THREE.Vector3();

  if (show.has('base')) {
    const baseShell = buildBaseShellPreview({
      outerLength,
      outerWidth,
      baseHeight,
      wallThickness,
      floorThickness,
    });
    baseShell.position.add(baseOffset);
    group.add(baseShell);
    for (const boss of enclosure.screw_bosses || []) {
      const holeDiameter = numberOr(enclosure.screw_hole_diameter, 2.2);
      const pilot = makeCylinderMesh('screw_boss_pilot_hole', holeDiameter, 0.45, [
        numberOr(boss.x, 0),
        numberOr(boss.y, 0),
        baseHeight + 0.24,
      ], SCENE_MATERIALS.opening);
      pilot.position.add(baseOffset);
      group.add(pilot);
    }
  }

  if (show.has('lid')) {
    const lid = makeBoxMesh('lid_part', [outerLength, outerWidth, lidThickness], [0, 0, outerHeight - lidThickness / 2], SCENE_MATERIALS.lid);
    lid.position.add(lidOffset);
    group.add(lid);
    for (const boss of enclosure.screw_bosses || []) {
      const lidHole = makeCylinderMesh('lid_screw_through_hole', numberOr(enclosure.screw_hole_diameter, 2.2), 0.55, [
        numberOr(boss.x, 0),
        numberOr(boss.y, 0),
        outerHeight + 0.3,
      ], SCENE_MATERIALS.opening);
      lidHole.position.add(lidOffset);
      group.add(lidHole);
    }
  }

  if (show.has('mounts')) {
    for (const mount of sceneData.mounts || []) {
      if (mode === 'base' && mount.mount_surface !== 'base_floor') continue;
      if (mode === 'lid' && mount.mount_surface !== 'lid_inner') continue;
      const mesh = makeBoxMesh(mount.id || 'mount', sizeArray(mount.size_mm), centerArray(mount.center), SCENE_MATERIALS.mount);
      mesh.position.add(baseOffset);
      group.add(mesh);
    }
  }

  if (show.has('hardware')) {
    for (const hardware of sceneData.hardware || []) {
      const hardwareGroup = buildHardwareProxy(hardware);
      group.add(hardwareGroup);
    }
  }

  if (show.has('openings')) {
    for (const opening of sceneData.openings || []) {
      const mesh = buildOpeningMarker(opening);
      mesh.position.add(baseOffset);
      group.add(mesh);
    }
  }

  return group;
}

function buildBaseShellPreview({ outerLength, outerWidth, baseHeight, wallThickness, floorThickness }) {
  const group = new THREE.Group();
  group.name = 'base_open_shell';
  const sideWallLength = Math.max(0.01, outerLength);
  const endWallLength = Math.max(0.01, outerLength - wallThickness * 2);
  const wallHeight = Math.max(0.01, baseHeight - floorThickness);
  const wallCenterZ = floorThickness + wallHeight / 2;
  const parts = [
    ['base_floor', [outerLength, outerWidth, floorThickness], [0, 0, floorThickness / 2]],
    ['base_wall_front', [sideWallLength, wallThickness, wallHeight], [0, -outerWidth / 2 + wallThickness / 2, wallCenterZ]],
    ['base_wall_back', [sideWallLength, wallThickness, wallHeight], [0, outerWidth / 2 - wallThickness / 2, wallCenterZ]],
    ['base_wall_left', [wallThickness, endWallLength, wallHeight], [-outerLength / 2 + wallThickness / 2, 0, wallCenterZ]],
    ['base_wall_right', [wallThickness, endWallLength, wallHeight], [outerLength / 2 - wallThickness / 2, 0, wallCenterZ]],
  ];
  for (const [name, size, center] of parts) {
    group.add(makeBoxMesh(name, size, center, SCENE_MATERIALS.base));
  }
  return group;
}

function buildHardwareProxy(hardware = {}) {
  const group = new THREE.Group();
  group.name = hardware.name || hardware.id || 'hardware';
  const size = hardware.size || hardware.dimensions_mm || {};
  const length = numberOr(size.length_x, 16);
  const width = numberOr(size.width_y, 12);
  const height = numberOr(size.height_z, 4);
  const pcbThickness = Math.min(height, Math.max(0.8, numberOr(hardware.dimensions_mm?.pcb_thickness, Math.min(1.6, height * 0.45))));
  const shape = String(hardware.cad_reference?.shape || '').toLowerCase();
  const baseColor = parseColor(hardware.cad_reference?.color, hardwareColorForCategory(hardware.category));
  const pcbMaterial = new THREE.MeshStandardMaterial({ color: baseColor, roughness: 0.8, metalness: 0.02 });
  const center = centerArray(hardware.center);

  group.position.set(center[0], center[1], center[2]);
  group.rotation.z = THREE.MathUtils.degToRad(numberOr(hardware.layout_rotation_deg, 0));
  const base = makeBoxMesh(`${hardware.id || 'hardware'}_body`, [length, width, pcbThickness], [0, 0, -height / 2 + pcbThickness / 2], pcbMaterial);
  group.add(base);

  if (/battery/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    group.add(makeBoxMesh('battery_holder_body', [length, width, height], [0, 0, 0], SCENE_MATERIALS.battery));
    group.add(makeCylinderMesh('battery_cell', Math.min(width * 0.72, height * 0.72), length * 0.84, [0, 0, height * 0.1], SCENE_MATERIALS.component, 'x'));
    return group;
  }

  if (/button/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    const count = /dual|double|2/.test(`${hardware.id || ''} ${hardware.name || ''}`.toLowerCase()) ? 2 : 1;
    const pitch = count > 1 ? Math.min(length * 0.48, 20) : 0;
    for (let index = 0; index < count; index += 1) {
      const x = (index - (count - 1) / 2) * pitch;
      group.add(makeCylinderMesh('button_cap', Math.min(length / count, width) * 0.34, Math.max(1.2, height * 0.5), [x, 0, height * 0.15], SCENE_MATERIALS.button));
    }
  } else if (/display|oled|screen/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    group.add(makeBoxMesh('display_window', [length * 0.72, width * 0.5, Math.max(0.35, height * 0.08)], [0, 0, height / 2 + 0.08], SCENE_MATERIALS.screen));
  } else if (/buzzer|speaker/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    group.add(makeCylinderMesh('sounder', Math.min(length, width) * 0.36, Math.max(1.2, height * 0.45), [0, 0, height * 0.12], SCENE_MATERIALS.component));
  } else if (/ultrasonic/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    const probeDiameter = Math.min(width * 0.58, length * 0.32);
    const probePitch = Math.min(length * 0.46, 25);
    for (const x of [-probePitch / 2, probePitch / 2]) {
      group.add(makeCylinderMesh('ultrasonic_probe', probeDiameter, Math.max(2.4, height * 0.78), [x, 0, height * 0.18], SCENE_MATERIALS.sensor));
    }
  } else if (/sensor|pir|camera/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    group.add(makeCylinderMesh('sensor_feature', Math.min(length, width) * 0.28, Math.max(1.2, height * 0.42), [0, 0, height * 0.12], SCENE_MATERIALS.sensor));
  } else {
    group.add(makeBoxMesh('main_component', [length * 0.58, width * 0.48, Math.max(0.8, height - pcbThickness)], [-length * 0.08, 0, pcbThickness / 2], SCENE_MATERIALS.component));
  }

  if (/usb|controller|pcb_with_usb/.test(`${hardware.id || ''} ${hardware.category || ''} ${shape}`)) {
    group.add(makeBoxMesh('usb_connector', [Math.min(7.5, length * 0.32), Math.min(9, width * 0.5), Math.min(3.2, height)], [length / 2 - Math.min(3.8, length * 0.16), 0, -height * 0.05], SCENE_MATERIALS.connector));
  }

  return group;
}

function buildOpeningMarker(opening = {}) {
  const size = opening.size_mm || {};
  const center = centerArray(opening.center);
  const face = opening.face || 'top';
  const diameter = numberOr(size.diameter, 0);
  if (diameter > 0 || /round|hole/.test(opening.type || '')) {
    const count = Math.max(1, Math.round(numberOr(size.count, 1)));
    const pitch = numberOr(size.pitch, diameter || 2);
    const group = new THREE.Group();
    group.name = opening.id || 'opening';
    for (let index = 0; index < count; index += 1) {
      const offset = (index - (count - 1) / 2) * pitch;
      const mesh = makeCylinderMesh('opening_hole', Math.max(0.8, diameter || 2), 0.7, [offset, 0, 0], SCENE_MATERIALS.opening);
      group.add(mesh);
    }
    group.position.set(center[0], center[1], center[2]);
    orientOpeningGroup(group, face);
    return group;
  }
  const width = numberOr(size.width, numberOr(size.length, 8));
  const height = numberOr(size.height, numberOr(size.width_y, 5));
  const mesh = makeBoxMesh(opening.id || 'opening', openingMarkerSize(face, width, height), center, SCENE_MATERIALS.opening);
  return mesh;
}

function makeBoxMesh(name, size, center, material) {
  const geometry = new THREE.BoxGeometry(Math.max(0.01, size[0]), Math.max(0.01, size[1]), Math.max(0.01, size[2]));
  const mesh = new THREE.Mesh(geometry, material.clone ? material.clone() : material);
  mesh.name = name;
  mesh.position.set(numberOr(center[0], 0), numberOr(center[1], 0), numberOr(center[2], 0));
  return mesh;
}

function makeCylinderMesh(name, diameter, depth, center, material, axis = 'z') {
  const geometry = new THREE.CylinderGeometry(Math.max(0.01, diameter / 2), Math.max(0.01, diameter / 2), Math.max(0.01, depth), 32);
  const mesh = new THREE.Mesh(geometry, material.clone ? material.clone() : material);
  mesh.name = name;
  if (axis === 'x') mesh.rotation.z = Math.PI / 2;
  else if (axis === 'y') mesh.rotation.x = Math.PI / 2;
  else mesh.rotation.x = Math.PI / 2;
  mesh.position.set(numberOr(center[0], 0), numberOr(center[1], 0), numberOr(center[2], 0));
  return mesh;
}

function orientOpeningGroup(group, face) {
  if (face === 'left' || face === 'right') group.rotation.y = Math.PI / 2;
  if (face === 'front' || face === 'back') group.rotation.x = Math.PI / 2;
}

function openingMarkerSize(face, width, height) {
  if (face === 'left' || face === 'right') return [0.7, width, height];
  if (face === 'front' || face === 'back') return [width, 0.7, height];
  return [width, height, 0.7];
}

function partOffsetForMode(partMode, sourceMode) {
  if (sourceMode !== 'exploded') return new THREE.Vector3();
  if (partMode === 'lid') return lidLiftOffset();
  return new THREE.Vector3();
}

function lidLiftOffset(outerHeight = 32) {
  const lift = Math.max(EXPLODED_LID_LIFT_MIN, numberOr(outerHeight, 32) * EXPLODED_LID_LIFT_RATIO);
  return new THREE.Vector3(0, 0, lift);
}

function modeShowList(mode) {
  return {
    assembly: ['base', 'lid', 'hardware', 'openings', 'mounts'],
    exploded: ['base', 'lid', 'hardware', 'openings', 'mounts'],
    base: ['base', 'mounts'],
    lid: ['lid', 'mounts'],
    hardware: ['hardware'],
  }[mode] || ['base', 'lid', 'hardware', 'openings', 'mounts'];
}

function normalizePreviewMode(mode) {
  return ['assembly', 'exploded', 'base', 'lid', 'hardware'].includes(mode) ? mode : 'assembly';
}

function sizeArray(size = {}) {
  return [
    numberOr(size.length_x, numberOr(size.width, 1)),
    numberOr(size.width_y, numberOr(size.depth, 1)),
    numberOr(size.height_z, numberOr(size.height, 1)),
  ];
}

function centerArray(center = {}) {
  return [
    numberOr(center.x, 0),
    numberOr(center.y, 0),
    numberOr(center.z, 0),
  ];
}

function parseColor(value, fallback) {
  if (typeof value !== 'string' || !/^#[0-9a-f]{6}$/i.test(value.trim())) return fallback;
  return Number.parseInt(value.trim().slice(1), 16);
}

function hardwareColorForCategory(category) {
  return {
    controller: 0x1f8a5b,
    display: 0x4b93a5,
    button: 0xc3a35b,
    speaker: 0x9d7bb0,
    sensor: 0xd48664,
    power: 0x7b8790,
  }[category] || 0x7f8b94;
}

function numberOr(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function normalizeFormat(value) {
  return typeof value === 'string' ? value.trim().toLowerCase() : '';
}
