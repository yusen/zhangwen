import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

export async function writePreviewStlFiles({ rootDir, designId, enclosure, layoutPlan }) {
  const exportDir = path.join(rootDir, 'exports', designId);
  await mkdir(exportDir, { recursive: true });

  const basePath = path.join(exportDir, 'base.stl');
  const lidPath = path.join(exportDir, 'lid.stl');
  const referencePath = path.join(exportDir, 'hardware-reference.stl');
  const openingReferencePath = path.join(exportDir, 'opening-reference.stl');
  const gltfPath = path.join(exportDir, 'preview.gltf');
  const previewBoxes = buildPreviewBoxes({ enclosure, layoutPlan });

  const base = sceneBoxesToStl(
    'zwcad_intent_base_preview',
    previewBoxes.filter((box) => box.id === 'base' || (box.kind === 'mount' && box.mountSurface === 'base_floor')),
  );
  const lid = sceneBoxesToStl(
    'zwcad_intent_lid_preview',
    previewBoxes.filter((box) => box.id === 'lid' || (box.kind === 'mount' && box.mountSurface === 'lid_inner')),
  );
  const hardware = sceneBoxesToStl(
    'zwcad_intent_hardware_reference_preview',
    previewBoxes.filter((box) => box.kind === 'hardware'),
  );
  const openingReference = sceneBoxesToStl(
    'zwcad_intent_opening_reference_preview',
    previewBoxes.filter((box) => box.kind === 'opening'),
  );
  const gltf = sceneBoxesToGltf(previewBoxes);

  await Promise.all([
    writeFile(basePath, base, 'utf8'),
    writeFile(lidPath, lid, 'utf8'),
    writeFile(referencePath, hardware, 'utf8'),
    writeFile(openingReferencePath, openingReference, 'utf8'),
    writeFile(gltfPath, JSON.stringify(gltf, null, 2), 'utf8'),
  ]);

  return [
    {
      id: 'base_stl',
      label: '底壳简化 STL',
      format: 'stl',
      url: `/exports/${designId}/base.stl`,
      path: basePath,
      fidelity: 'preview_simplified',
    },
    {
      id: 'lid_stl',
      label: '上盖简化 STL',
      format: 'stl',
      url: `/exports/${designId}/lid.stl`,
      path: lidPath,
      fidelity: 'preview_simplified',
    },
    {
      id: 'hardware_reference_stl',
      label: '硬件参考简化 STL',
      format: 'stl',
      url: `/exports/${designId}/hardware-reference.stl`,
      path: referencePath,
      fidelity: 'preview_simplified',
    },
    {
      id: 'opening_reference_stl',
      label: '开孔参考简化 STL',
      format: 'stl',
      url: `/exports/${designId}/opening-reference.stl`,
      path: openingReferencePath,
      fidelity: 'preview_simplified',
    },
    {
      id: 'preview_gltf',
      label: '整体简化 glTF 预览',
      format: 'gltf',
      url: `/exports/${designId}/preview.gltf`,
      path: gltfPath,
      fidelity: 'preview_simplified',
    },
  ];
}

export async function writeArtifactMetadataFiles({ rootDir, designId, artifact }) {
  const exportDir = path.join(rootDir, 'exports', designId);
  await mkdir(exportDir, { recursive: true });

  const validationReport = buildValidationReport(artifact);
  const entries = [
    {
      id: 'cadquery_code',
      label: 'CadQuery 生成器代码',
      format: 'py',
      filename: 'cadquery.py',
      content: artifact.cadquery_code || '',
      fidelity: 'deterministic_text',
    },
    {
      id: 'design_state_json',
      label: 'DesignState JSON',
      format: 'json',
      filename: 'design-state.json',
      content: JSON.stringify(artifact.design_state || {}, null, 2),
      fidelity: 'deterministic_state',
    },
    {
      id: 'checks_json',
      label: '校验报告 JSON',
      format: 'json',
      filename: 'checks.json',
      content: JSON.stringify(validationReport, null, 2),
      fidelity: 'deterministic_validation',
    },
  ];
  const publicEntries = entries.map((entry) => ({
    id: entry.id,
    label: entry.label,
    format: entry.format,
    url: `/exports/${designId}/${entry.filename}`,
    path: path.join(exportDir, entry.filename),
    fidelity: entry.fidelity,
  }));

  const artifactSnapshot = {
    ...artifact,
    exports: [...(artifact.exports || []), ...publicEntries],
    design_state: {
      ...(artifact.design_state || {}),
      exports: [...(artifact.exports || []), ...publicEntries],
    },
  };

  await Promise.all([
    ...entries.map((entry) => writeFile(path.join(exportDir, entry.filename), entry.content, 'utf8')),
    writeFile(path.join(exportDir, 'artifact.json'), JSON.stringify(artifactSnapshot, null, 2), 'utf8'),
  ]);

  return [
    ...publicEntries,
    {
      id: 'artifact_json',
      label: '完整 Artifact JSON',
      format: 'json',
      url: `/exports/${designId}/artifact.json`,
      path: path.join(exportDir, 'artifact.json'),
      fidelity: 'deterministic_artifact',
    },
  ];
}

export async function writeArtifactSnapshotFile({ rootDir, designId, artifact }) {
  const exportDir = path.join(rootDir, 'exports', designId);
  await mkdir(exportDir, { recursive: true });
  await Promise.all([
    writeFile(
      path.join(exportDir, 'artifact.json'),
      JSON.stringify(buildArtifactSnapshot(artifact), null, 2),
      'utf8',
    ),
    writeFile(
      path.join(exportDir, 'design-state.json'),
      JSON.stringify(artifact.design_state || {}, null, 2),
      'utf8',
    ),
    writeFile(
      path.join(exportDir, 'checks.json'),
      JSON.stringify(buildValidationReport(artifact), null, 2),
      'utf8',
    ),
  ]);
}

function buildValidationReport(artifact = {}) {
  const checks = Array.isArray(artifact.checks) ? artifact.checks : [];
  const warnings = Array.isArray(artifact.warnings) ? artifact.warnings : [];
  const validationContext = isPlainObject(artifact.design_state?.validation_context)
    ? artifact.design_state.validation_context
    : isPlainObject(artifact.validation_context)
      ? artifact.validation_context
      : {};

  return {
    status: 'validation_report',
    validation_status: summarizeValidationStatus(checks),
    status_counts: countCheckStatuses(checks),
    checks,
    warnings,
    validation_context: validationContext,
    source: artifact.source || 'deterministic',
  };
}

function buildArtifactSnapshot(artifact = {}) {
  const exports = Array.isArray(artifact.exports) ? artifact.exports : [];
  return {
    ...artifact,
    exports,
    design_state: {
      ...(artifact.design_state || {}),
      exports,
    },
  };
}

function summarizeValidationStatus(checks = []) {
  if (checks.some((item) => item.status === 'fail')) return 'fail';
  if (checks.some((item) => item.status === 'pending')) return 'pending';
  if (checks.some((item) => item.status === 'warn')) return 'warn';
  return 'pass';
}

function countCheckStatuses(checks = []) {
  return checks.reduce((acc, item) => {
    acc[item.status] = (acc[item.status] || 0) + 1;
    return acc;
  }, {});
}

function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function boxToStl(name, box) {
  return sceneBoxesToStl(name, [box]);
}

function buildPreviewBoxes({ enclosure, layoutPlan }) {
  const shellBoxes = buildBaseShellPreviewBoxes(enclosure);
  return [
    ...shellBoxes,
    {
      id: 'lid',
      name: 'Lid preview shell',
      kind: 'lid',
      material: 'lid',
      size: [
        enclosure.outer_box_size.length_x,
        enclosure.outer_box_size.width_y,
        enclosure.lid_thickness,
      ],
      center: [0, 0, enclosure.outer_box_size.height_z - enclosure.lid_thickness / 2],
    },
    ...layoutPlan.hardware_transforms.map((item) => ({
      id: item.hardware_id,
      name: item.name || item.hardware_id,
      kind: 'hardware',
      material: materialForCategory(item.category),
      size: [
        item.bounding_box.length_x,
        item.bounding_box.width_y,
        item.bounding_box.height_z,
      ],
      center: [item.center.x, item.center.y, item.center.z],
    })),
    ...(layoutPlan.mounting_transforms || []).map((item) => ({
      id: item.id,
      name: item.id,
      kind: 'mount',
      material: 'mount',
      mountSurface: item.mount_surface || '',
      size: [
        item.size_mm.length_x,
        item.size_mm.width_y,
        item.size_mm.height_z,
      ],
      center: [item.center.x, item.center.y, item.center.z],
    })),
    ...[
      ...(layoutPlan.opening_transforms || []),
      ...(layoutPlan.mounting_hole_transforms || []),
    ].map((item) => openingPreviewBox(item)),
  ];
}

function buildBaseShellPreviewBoxes(enclosure = {}) {
  const outer = enclosure.outer_box_size || {};
  const inner = enclosure.inner_box_size || {};
  const outerLength = Number(outer.length_x || 80);
  const outerWidth = Number(outer.width_y || 50);
  const outerHeight = Number(outer.height_z || 24);
  const wallThickness = Math.max(0.6, Number(enclosure.wall_thickness || (outerLength - Number(inner.length_x || outerLength - 2.4)) / 2 || 1.2));
  const floorThickness = Math.max(0.6, Number(enclosure.floor_thickness || wallThickness));
  const lidThickness = Math.max(1.2, Number(enclosure.lid_thickness || outerHeight - Number(inner.height_z || outerHeight - 5)));
  const baseHeight = Math.max(2, outerHeight - lidThickness);
  const wallHeight = Math.max(0.01, baseHeight - floorThickness);
  const wallCenterZ = floorThickness + wallHeight / 2;
  const endWallLength = Math.max(0.01, outerLength - wallThickness * 2);
  const boxes = [
    {
      id: 'base_floor',
      name: 'base_floor',
      kind: 'base',
      material: 'base',
      size: [outerLength, outerWidth, floorThickness],
      center: [0, 0, floorThickness / 2],
    },
    {
      id: 'base_wall_front',
      name: 'base_wall_front',
      kind: 'base',
      material: 'base',
      size: [outerLength, wallThickness, wallHeight],
      center: [0, -outerWidth / 2 + wallThickness / 2, wallCenterZ],
    },
    {
      id: 'base_wall_back',
      name: 'base_wall_back',
      kind: 'base',
      material: 'base',
      size: [outerLength, wallThickness, wallHeight],
      center: [0, outerWidth / 2 - wallThickness / 2, wallCenterZ],
    },
    {
      id: 'base_wall_left',
      name: 'base_wall_left',
      kind: 'base',
      material: 'base',
      size: [wallThickness, endWallLength, wallHeight],
      center: [-outerLength / 2 + wallThickness / 2, 0, wallCenterZ],
    },
    {
      id: 'base_wall_right',
      name: 'base_wall_right',
      kind: 'base',
      material: 'base',
      size: [wallThickness, endWallLength, wallHeight],
      center: [outerLength / 2 - wallThickness / 2, 0, wallCenterZ],
    },
  ];
  return boxes;
}

function openingPreviewBox(opening = {}) {
  const footprint = openingFootprintSize(opening);
  const thickness = 0.6;
  const center = opening.center || {};
  const face = opening.face || 'top';
  let size = [footprint.length_x, footprint.width_y, thickness];
  if (face === 'left' || face === 'right') {
    size = [thickness, footprint.length_x, footprint.width_y];
  } else if (face === 'front' || face === 'back') {
    size = [footprint.length_x, thickness, footprint.width_y];
  }
  return {
    id: opening.id,
    name: `${opening.id || 'opening'}_opening_marker`,
    kind: 'opening',
    material: 'opening',
    face,
    size,
    center: [center.x || 0, center.y || 0, center.z || 0],
  };
}

function openingFootprintSize(opening = {}) {
  const size = opening.size_mm || {};
  const diameter = Number(size.diameter || opening.diameter_mm || 0);
  const count = Number(size.count || opening.count || 1);
  const pitch = Number(size.pitch || size.pitch_mm || opening.pitch_mm || diameter || 1);
  if (opening.type === 'hole_array' || opening.type === 'round_hole') {
    const length = opening.type === 'hole_array'
      ? (Math.max(1, count) - 1) * pitch + diameter
      : diameter;
    return {
      length_x: Math.max(0.8, length || 4),
      width_y: Math.max(0.8, diameter || 4),
    };
  }
  const slotLength = Number(size.length || size.length_x || opening.slot_mm?.length || 0);
  const slotWidth = Number(size.width || size.width_y || opening.slot_mm?.width || 0);
  if (opening.type === 'slot_array' || slotLength > 0) {
    return {
      length_x: Math.max(0.8, slotLength || 8),
      width_y: Math.max(0.8, (Math.max(1, count) - 1) * pitch + (slotWidth || 2)),
    };
  }
  const width = Number(size.width || size.length_x || opening.width_mm || 0);
  const height = Number(size.height || size.width_y || opening.height_mm || 0);
  return {
    length_x: Math.max(0.8, width || 10),
    width_y: Math.max(0.8, height || 6),
  };
}

function sceneBoxesToStl(name, boxes) {
  const triangles = boxes.flatMap((box) => (
    box.shape === 'cylinder_z' ? cylinderTriangles(box) : boxTriangles(box)
  ));
  return [
    `solid ${name}`,
    ...triangles.map((triangle) => formatTriangle(triangle.normal, triangle.points)),
    `endsolid ${name}`,
    '',
  ].join('\n');
}

function sceneBoxesToGltf(boxes) {
  const cubeGeometry = createCubeGeometryBuffer();
  const materials = [
    ['base', [0.72, 0.78, 0.82, 1]],
    ['lid', [0.95, 0.96, 0.97, 0.72]],
    ['controller', [0.41, 0.65, 0.49, 1]],
    ['display', [0.29, 0.58, 0.65, 1]],
    ['button', [0.76, 0.64, 0.36, 1]],
    ['speaker', [0.62, 0.48, 0.69, 1]],
    ['sensor', [0.83, 0.52, 0.39, 1]],
    ['power', [0.48, 0.53, 0.56, 1]],
    ['mount', [0.95, 0.73, 0.30, 1]],
    ['opening', [0.92, 0.22, 0.18, 0.68]],
    ['hardware', [0.52, 0.59, 0.64, 1]],
  ];
  const materialByName = new Map(materials.map(([name], index) => [name, index]));
  const meshes = boxes.map((box) => ({
    name: box.name,
    primitives: [
      {
        attributes: { POSITION: 0 },
        indices: 1,
        material: materialByName.get(box.material) ?? materialByName.get('hardware'),
      },
    ],
  }));
  return {
    asset: {
      version: '2.0',
      generator: 'ZW-CAD-intent simplified preview exporter',
    },
    scene: 0,
    scenes: [{ nodes: boxes.map((_, index) => index) }],
    nodes: boxes.map((box, index) => ({
      name: box.name,
      mesh: index,
      translation: box.center.map((value) => Number(value) || 0),
      scale: box.size.map((value) => Math.max(0.001, Number(value) || 1)),
    })),
    meshes,
    materials: materials.map(([name, color]) => ({
      name,
      pbrMetallicRoughness: {
        baseColorFactor: color,
        metallicFactor: 0,
        roughnessFactor: 0.85,
      },
      alphaMode: color[3] < 1 ? 'BLEND' : 'OPAQUE',
      doubleSided: true,
    })),
    buffers: [
      {
        uri: `data:application/octet-stream;base64,${cubeGeometry.buffer.toString('base64')}`,
        byteLength: cubeGeometry.buffer.length,
      },
    ],
    bufferViews: [
      {
        buffer: 0,
        byteOffset: cubeGeometry.positionOffset,
        byteLength: cubeGeometry.positionByteLength,
        target: 34962,
      },
      {
        buffer: 0,
        byteOffset: cubeGeometry.indexOffset,
        byteLength: cubeGeometry.indexByteLength,
        target: 34963,
      },
    ],
    accessors: [
      {
        bufferView: 0,
        byteOffset: 0,
        componentType: 5126,
        count: 8,
        type: 'VEC3',
        min: [-0.5, -0.5, -0.5],
        max: [0.5, 0.5, 0.5],
      },
      {
        bufferView: 1,
        byteOffset: 0,
        componentType: 5123,
        count: 36,
        type: 'SCALAR',
      },
    ],
  };
}

function createCubeGeometryBuffer() {
  const positions = [
    [-0.5, 0.5, -0.5],
    [0.5, 0.5, -0.5],
    [0.5, -0.5, -0.5],
    [-0.5, -0.5, -0.5],
    [-0.5, 0.5, 0.5],
    [0.5, 0.5, 0.5],
    [0.5, -0.5, 0.5],
    [-0.5, -0.5, 0.5],
  ];
  const indices = [
    0, 2, 1, 0, 3, 2,
    4, 5, 6, 4, 6, 7,
    0, 1, 5, 0, 5, 4,
    3, 7, 6, 3, 6, 2,
    2, 6, 5, 2, 5, 1,
    0, 4, 7, 0, 7, 3,
  ];
  const positionByteLength = positions.length * 3 * 4;
  const indexByteLength = indices.length * 2;
  const buffer = Buffer.alloc(positionByteLength + indexByteLength);
  let offset = 0;
  for (const point of positions) {
    for (const value of point) {
      buffer.writeFloatLE(value, offset);
      offset += 4;
    }
  }
  const indexOffset = offset;
  for (const index of indices) {
    buffer.writeUInt16LE(index, offset);
    offset += 2;
  }
  return {
    buffer,
    positionOffset: 0,
    positionByteLength,
    indexOffset,
    indexByteLength,
  };
}

function materialForCategory(category) {
  return {
    controller: 'controller',
    display: 'display',
    button: 'button',
    speaker: 'speaker',
    sensor: 'sensor',
    power: 'power',
  }[category] || 'hardware';
}

function boxTriangles({ size, center }) {
  const [sx, sy, sz] = size.map((value) => Number(value) || 1);
  const [cx, cy, cz] = center.map((value) => Number(value) || 0);
  const x0 = cx - sx / 2;
  const x1 = cx + sx / 2;
  const y0 = cy - sy / 2;
  const y1 = cy + sy / 2;
  const z0 = cz - sz / 2;
  const z1 = cz + sz / 2;
  const v = {
    nwb: [x0, y1, z0],
    neb: [x1, y1, z0],
    seb: [x1, y0, z0],
    swb: [x0, y0, z0],
    nwt: [x0, y1, z1],
    net: [x1, y1, z1],
    set: [x1, y0, z1],
    swt: [x0, y0, z1],
  };
  return [
    tri([0, 0, -1], v.nwb, v.seb, v.neb),
    tri([0, 0, -1], v.nwb, v.swb, v.seb),
    tri([0, 0, 1], v.nwt, v.net, v.set),
    tri([0, 0, 1], v.nwt, v.set, v.swt),
    tri([0, 1, 0], v.nwb, v.neb, v.net),
    tri([0, 1, 0], v.nwb, v.net, v.nwt),
    tri([0, -1, 0], v.swb, v.swt, v.set),
    tri([0, -1, 0], v.swb, v.set, v.seb),
    tri([1, 0, 0], v.seb, v.set, v.net),
    tri([1, 0, 0], v.seb, v.net, v.neb),
    tri([-1, 0, 0], v.nwb, v.nwt, v.swt),
    tri([-1, 0, 0], v.nwb, v.swt, v.swb),
  ];
}

function cylinderTriangles({ diameter, size, center }, segments = 32) {
  const radius = Math.max(0.001, Number(diameter || size?.[0] || 1) / 2);
  const height = Math.max(0.001, Number(size?.[2] || 1));
  const [cx, cy, cz] = center.map((value) => Number(value) || 0);
  const z0 = cz - height / 2;
  const z1 = cz + height / 2;
  const topCenter = [cx, cy, z1];
  const bottomCenter = [cx, cy, z0];
  const triangles = [];
  for (let index = 0; index < segments; index += 1) {
    const a0 = (Math.PI * 2 * index) / segments;
    const a1 = (Math.PI * 2 * (index + 1)) / segments;
    const p0b = [cx + Math.cos(a0) * radius, cy + Math.sin(a0) * radius, z0];
    const p1b = [cx + Math.cos(a1) * radius, cy + Math.sin(a1) * radius, z0];
    const p0t = [p0b[0], p0b[1], z1];
    const p1t = [p1b[0], p1b[1], z1];
    const normal = [Math.cos((a0 + a1) / 2), Math.sin((a0 + a1) / 2), 0];
    triangles.push(tri(normal, p0b, p1b, p1t));
    triangles.push(tri(normal, p0b, p1t, p0t));
    triangles.push(tri([0, 0, 1], topCenter, p0t, p1t));
    triangles.push(tri([0, 0, -1], bottomCenter, p1b, p0b));
  }
  return triangles;
}

function tri(normal, ...points) {
  return { normal, points };
}

function formatTriangle(normal, points) {
  const vertexLines = points
    .map((point) => `      vertex ${fmt(point[0])} ${fmt(point[1])} ${fmt(point[2])}`)
    .join('\n');
  return [
    `  facet normal ${fmt(normal[0])} ${fmt(normal[1])} ${fmt(normal[2])}`,
    '    outer loop',
    vertexLines,
    '    endloop',
    '  endfacet',
  ].join('\n');
}

function fmt(value) {
  return Number(value).toFixed(4).replace(/\.?0+$/, '');
}
