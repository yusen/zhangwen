import { DEFAULT_PARAMETERS, isFiniteNumber, isPlainObject, isPositiveNumber, normalizeString, round } from './shared.js';

export function boxSizingTool({ orientedHardwareSpecs, parameters, userConstraints }) {
  const floorSpecs = orientedHardwareSpecs.filter((item) => item.target_face === 'base_floor');
  const lidSpecs = orientedHardwareSpecs.filter((item) => item.target_face !== 'base_floor');
  const footprints = orientedHardwareSpecs.map((item) => ({
    x: item.bounding_box.length_x,
    y: item.bounding_box.width_y,
    z: item.bounding_box.height_z,
  }));
  const maxX = Math.max(...footprints.map((item) => item.x), 45);
  const maxY = Math.max(...footprints.map((item) => item.y), 30);
  const sumArea = footprints.reduce((sum, item) => sum + item.x * item.y, 0);
  const approxInnerX = Math.max(80, Math.ceil(Math.sqrt(sumArea * 1.8) + parameters.edge_clearance * 2));
  const approxInnerY = Math.max(50, Math.ceil(sumArea / Math.max(approxInnerX - parameters.edge_clearance * 2, 1) + maxY + parameters.edge_clearance));
  const floorHeight = floorSpecs.reduce((max, item) => Math.max(max, item.bounding_box.height_z), 0);
  const lidHeight = lidSpecs.reduce((max, item) => Math.max(max, item.bounding_box.height_z), 0);
  const innerHeight = Math.max(28, Math.ceil(floorHeight + lidHeight + parameters.clearance * 3 + parameters.lid_lip_height));
  const autoInner = {
    length_x: approxInnerX,
    width_y: approxInnerY,
    height_z: innerHeight,
  };
  const overriddenInner = {
    length_x: parameters.inner_length_x > 0 ? parameters.inner_length_x : autoInner.length_x,
    width_y: parameters.inner_width_y > 0 ? parameters.inner_width_y : autoInner.width_y,
    height_z: parameters.inner_height_z > 0 ? parameters.inner_height_z : autoInner.height_z,
  };
  const constrainedInner = applyUserSizeConstraints(overriddenInner, userConstraints);
  const sizeReasoning = buildSizeReasoning({
    orientedHardwareSpecs,
    floorSpecs,
    lidSpecs,
    maxX,
    maxY,
    sumArea,
    floorHeight,
    lidHeight,
    autoInner,
    overriddenInner,
    constrainedInner,
    parameters,
    userConstraints,
  });

  return {
    units: 'mm',
    inner_box_size: constrainedInner,
    outer_box_size: {
      length_x: round(constrainedInner.length_x + parameters.wall_thickness * 2),
      width_y: round(constrainedInner.width_y + parameters.wall_thickness * 2),
      height_z: round(constrainedInner.height_z + parameters.floor_thickness + parameters.lid_thickness),
    },
    wall_thickness: parameters.wall_thickness,
    floor_thickness: parameters.floor_thickness,
    lid_thickness: parameters.lid_thickness,
    lid_lip_height: parameters.lid_lip_height,
    lid_clearance: parameters.lid_clearance,
    corner_radius: parameters.corner_radius,
    screw_bosses: buildScrewBosses(constrainedInner, parameters),
    size_reasoning: sizeReasoning,
  };
}

export function buildSizeReasoning({
  orientedHardwareSpecs,
  floorSpecs,
  lidSpecs,
  maxX,
  maxY,
  sumArea,
  floorHeight,
  lidHeight,
  autoInner,
  overriddenInner,
  constrainedInner,
  parameters,
  userConstraints,
}) {
  const overrideAxes = [
    ['length_x', 'inner_length_x'],
    ['width_y', 'inner_width_y'],
    ['height_z', 'inner_height_z'],
  ].filter(([, parameterKey]) => Number(parameters[parameterKey]) > 0).map(([axis]) => axis);
  const constrainedAxes = ['length_x', 'width_y', 'height_z']
    .filter((axis) => round(overriddenInner[axis]) !== round(constrainedInner[axis]));
  const outerMax = userConstraints?.size_mm?.outer_max || null;
  const heightStack = {
    floor_hardware_height_z: round(floorHeight),
    lid_hardware_height_z: round(lidHeight),
    clearance_stack_mm: round(parameters.clearance * 3),
    lid_lip_height_mm: round(parameters.lid_lip_height),
    calculated_inner_height_z: round(floorHeight + lidHeight + parameters.clearance * 3 + parameters.lid_lip_height),
    minimum_inner_height_z: 28,
    chosen_inner_height_z: round(autoInner.height_z),
  };

  return {
    method: 'footprint_area_and_height_stack',
    summary: [
      `按 ${orientedHardwareSpecs.length} 个硬件的 footprint 面积估算内腔。`,
      `最大硬件 footprint 为 ${round(maxX)} x ${round(maxY)} mm。`,
      `高度按底壳硬件、盖内交互硬件、盖唇和间隙叠加推导。`,
    ],
    hardware_count: orientedHardwareSpecs.length,
    floor_hardware_count: floorSpecs.length,
    lid_hardware_count: lidSpecs.length,
    total_footprint_area_mm2: round(sumArea),
    max_footprint_mm: {
      length_x: round(maxX),
      width_y: round(maxY),
    },
    estimation_inputs: {
      footprint_area_multiplier: 1.8,
      edge_clearance_mm: round(parameters.edge_clearance),
      clearance_mm: round(parameters.clearance),
      minimum_inner_length_x: 80,
      minimum_inner_width_y: 50,
      minimum_inner_height_z: 28,
    },
    height_stack_mm: heightStack,
    auto_inner_box_size: roundSize(autoInner),
    overridden_inner_box_size: roundSize(overriddenInner),
    constrained_inner_box_size: roundSize(constrainedInner),
    parameter_overrides_applied: {
      axes: overrideAxes,
      length_x: overrideAxes.includes('length_x'),
      width_y: overrideAxes.includes('width_y'),
      height_z: overrideAxes.includes('height_z'),
    },
    user_constraints_applied: {
      has_outer_max: Boolean(outerMax),
      constrained_axes: constrainedAxes,
      outer_max: outerMax ? roundSize(outerMax) : null,
      before_inner_box_size: roundSize(overriddenInner),
      after_inner_box_size: roundSize(constrainedInner),
    },
  };
}

export function roundSize(size = {}) {
  return {
    length_x: round(Number(size.length_x || 0)),
    width_y: round(Number(size.width_y || 0)),
    height_z: round(Number(size.height_z || 0)),
  };
}

export function faceCapacityChecker({ enclosure, orientedHardwareSpecs }) {
  const inner = enclosure.inner_box_size;
  const topSpecs = orientedHardwareSpecs.filter((item) => item.target_face !== 'base_floor');
  const totalTopArea = estimateTopInteractionArea(topSpecs);
  const topArea = inner.length_x * inner.width_y;
  if (topSpecs.length && totalTopArea > topArea * 0.72) {
    return {
      status: 'fail',
      message: `顶面交互硬件面积约 ${round(totalTopArea)} mm2，超过可用顶面容量。`,
      details: {
        face: 'top',
        total_top_area_mm2: round(totalTopArea),
        available_top_area_mm2: round(topArea),
        required_top_area_mm2: round(totalTopArea / 0.72),
        utilization: round(totalTopArea / Math.max(topArea, 1), 3),
      },
      questions: [
        '是否允许增大盒子长宽？',
        '是否把部分按钮/传感器移动到侧面？',
        '是否减少硬件数量？',
      ],
    };
  }
  return {
    status: 'ok',
    face_layout_candidates: [
      {
        face: 'top',
        hardware_ids: topSpecs.map((item) => item.hardware_id),
        utilization: topSpecs.length ? round(totalTopArea / topArea) : 0,
      },
    ],
    face_capacity_report: {
      status: 'pass',
      message: '当前顶面容量可以容纳交互硬件和开孔。',
    },
  };
}

export function repairFaceCapacityByExpandingBox({
  enclosure,
  capacity,
  orientedHardwareSpecs,
  parameters,
  userConstraints,
}) {
  if (userConstraints?.size_mm?.outer_max) {
    return { status: 'skipped_user_size_limit' };
  }
  const topSpecs = orientedHardwareSpecs.filter((item) => item.target_face !== 'base_floor');
  if (!topSpecs.length) return { status: 'skipped_no_top_hardware' };

  const inner = enclosure.inner_box_size;
  const currentArea = Math.max(1, inner.length_x * inner.width_y);
  const requiredArea = Math.ceil((capacity.details?.total_top_area_mm2 || estimateTopInteractionArea(topSpecs)) / 0.66);
  if (requiredArea <= currentArea) return { status: 'skipped_not_needed' };

  const scale = Math.sqrt(requiredArea / currentArea);
  const bossSafeInner = minimumInnerSizeForBossClearance(topSpecs, parameters);
  const repairedParameters = {
    ...parameters,
    inner_length_x: Math.max(Math.ceil(inner.length_x * scale), bossSafeInner.length_x),
    inner_width_y: Math.max(Math.ceil(inner.width_y * scale), bossSafeInner.width_y),
  };
  const repairedEnclosure = boxSizingTool({
    orientedHardwareSpecs,
    parameters: repairedParameters,
    userConstraints,
  });
  const repairedCapacity = faceCapacityChecker({
    enclosure: repairedEnclosure,
    orientedHardwareSpecs,
  });

  if (repairedCapacity.status === 'fail') {
    return { status: 'failed', capacity: repairedCapacity };
  }

  return {
    status: 'ok',
    enclosure: repairedEnclosure,
    capacity: repairedCapacity,
    parameters: repairedParameters,
    warning: {
      id: 'face_capacity_auto_repair',
      status: 'warn',
      message: `顶面容量不足，已自动把内腔长宽从 ${round(inner.length_x)} x ${round(inner.width_y)} mm 调整到 ${round(repairedEnclosure.inner_box_size.length_x)} x ${round(repairedEnclosure.inner_box_size.width_y)} mm。`,
      details: {
        before_inner_box_size: inner,
        after_inner_box_size: repairedEnclosure.inner_box_size,
        original_capacity: capacity.details || null,
        repaired_capacity: repairedCapacity.face_layout_candidates?.[0] || null,
      },
    },
  };
}

export function estimateTopInteractionArea(topSpecs) {
  return topSpecs.reduce((sum, item) => {
    const margin = 8;
    return sum + (item.bounding_box.length_x + margin) * (item.bounding_box.width_y + margin);
  }, 0);
}

export function minimumInnerSizeForBossClearance(topSpecs, parameters) {
  const largestTopLength = Math.max(0, ...topSpecs.map((item) => Number(item.bounding_box?.length_x || 0)));
  const largestTopWidth = Math.max(0, ...topSpecs.map((item) => Number(item.bounding_box?.width_y || 0)));
  const bossKeepout = parameters.edge_clearance + parameters.screw_boss_diameter / 2 + parameters.clearance * 1.6;
  return {
    length_x: Math.ceil(largestTopLength + bossKeepout * 2),
    width_y: Math.ceil(largestTopWidth + bossKeepout * 2),
  };
}

export function layoutSolverTool({ enclosure, orientedHardwareSpecs, parameters = DEFAULT_PARAMETERS }) {
  const inner = enclosure.inner_box_size;
  const floorZ = enclosure.floor_thickness;
  const lidInnerZ = enclosure.outer_box_size.height_z - enclosure.lid_thickness - enclosure.lid_lip_height;
  const floorSpecs = orientedHardwareSpecs.filter((item) => item.target_face === 'base_floor');
  const lidSpecs = orientedHardwareSpecs.filter((item) => item.target_face !== 'base_floor');
  const floorPositions = packInRows(floorSpecs, inner, 'floor', parameters);
  const lidPositions = packInRows(lidSpecs, inner, 'lid', parameters);
  const transforms = [
    ...floorSpecs.map((spec, index) => ({
      ...buildHardwareTransform(
        spec,
        applyHardwareOffset(spec, applyOpeningFaceAnchor(spec, floorPositions[index], inner, parameters), parameters),
        floorZ + spec.bounding_box.height_z / 2,
      ),
      mount_surface: 'base_floor',
    })),
    ...lidSpecs.map((spec, index) => ({
      ...buildHardwareTransform(
        spec,
        applyHardwareOffset(spec, applyOpeningFaceAnchor(spec, lidPositions[index], inner, parameters), parameters),
        lidInnerZ - spec.bounding_box.height_z / 2,
      ),
      mount_surface: 'lid_inner',
    })),
  ];
  const openingTransforms = transforms.flatMap((transform) => buildOpeningTransforms(transform, enclosure, parameters));
  const mountingTransforms = transforms.flatMap((transform) => buildMountingTransforms(transform, parameters));
  const mountingHoleTransforms = transforms.flatMap((transform) => buildMountingHoleTransforms(transform, enclosure));
  return {
    hardware_transforms: transforms,
    opening_transforms: openingTransforms,
    mounting_transforms: mountingTransforms,
    mounting_hole_transforms: mountingHoleTransforms,
    occupied_regions: transforms.map((item) => ({
      hardware_id: item.hardware_id,
      face: item.mount_surface,
      rect: {
        x: round(item.center.x - item.bounding_box.length_x / 2),
        y: round(item.center.y - item.bounding_box.width_y / 2),
        length_x: item.bounding_box.length_x,
        width_y: item.bounding_box.width_y,
      },
    })),
    generated_by: 'layout_solver_tool',
  };
}

export function applyUserSizeConstraints(inner, userConstraints) {
  const outerMax = userConstraints?.size_mm?.outer_max;
  if (!outerMax) return inner;
  return {
    length_x: Math.min(inner.length_x, Math.max(40, outerMax.length_x - DEFAULT_PARAMETERS.wall_thickness * 2)),
    width_y: Math.min(inner.width_y, Math.max(30, outerMax.width_y - DEFAULT_PARAMETERS.wall_thickness * 2)),
    height_z: Math.min(inner.height_z, Math.max(20, outerMax.height_z - DEFAULT_PARAMETERS.floor_thickness - DEFAULT_PARAMETERS.lid_thickness)),
  };
}

export function buildScrewBosses(inner, parameters) {
  const inset = Math.max(7, parameters.screw_boss_diameter);
  return [
    { x: round(-inner.length_x / 2 + inset), y: round(-inner.width_y / 2 + inset) },
    { x: round(inner.length_x / 2 - inset), y: round(-inner.width_y / 2 + inset) },
    { x: round(-inner.length_x / 2 + inset), y: round(inner.width_y / 2 - inset) },
    { x: round(inner.length_x / 2 - inset), y: round(inner.width_y / 2 - inset) },
  ];
}

export function packInRows(specs, inner, layer, parameters = DEFAULT_PARAMETERS) {
  if (!specs.length) return [];
  const sorted = [...specs].sort((a, b) => b.bounding_box.length_x - a.bounding_box.length_x);
  const gap = Math.max(0, Number(parameters.hardware_gap ?? DEFAULT_PARAMETERS.hardware_gap));
  const edgeClearance = Math.max(0, Number(parameters.edge_clearance ?? DEFAULT_PARAMETERS.edge_clearance));
  const rows = [];
  let currentRow = [];
  let currentWidth = 0;
  for (const spec of sorted) {
    const w = spec.bounding_box.length_x + gap;
    if (currentRow.length && currentWidth + w > inner.length_x - edgeClearance * 2) {
      rows.push(currentRow);
      currentRow = [];
      currentWidth = 0;
    }
    currentRow.push(spec);
    currentWidth += w;
  }
  if (currentRow.length) rows.push(currentRow);

  const totalHeight = rows.reduce((sum, row) => sum + Math.max(...row.map((item) => item.bounding_box.width_y)) + gap, -gap);
  let y = totalHeight / 2;
  const positions = new Map();
  for (const row of rows) {
    const rowHeight = Math.max(...row.map((item) => item.bounding_box.width_y));
    const rowWidth = row.reduce((sum, item) => sum + item.bounding_box.length_x, 0) + gap * (row.length - 1);
    let x = -rowWidth / 2;
    for (const spec of row) {
      positions.set(spec.hardware_id, {
        x: round(x + spec.bounding_box.length_x / 2),
        y: round(layer === 'lid' ? y - rowHeight / 2 : -y + rowHeight / 2),
      });
      x += spec.bounding_box.length_x + gap;
    }
    y -= rowHeight + gap;
  }
  return specs.map((spec) => positions.get(spec.hardware_id) || { x: 0, y: 0 });
}

export function applyOpeningFaceAnchor(spec, position = { x: 0, y: 0 }, inner, parameters = DEFAULT_PARAMETERS) {
  const anchored = { ...position };
  const sideOpening = (spec.openings || []).find((opening) => {
    const face = opening.preferred_face || defaultOpeningFace(spec);
    return ['left', 'right', 'front', 'back'].includes(face);
  });
  if (!sideOpening) return anchored;

  const face = sideOpening.preferred_face || defaultOpeningFace(spec);
  const inset = Math.max(0, Number(parameters.clearance ?? DEFAULT_PARAMETERS.clearance));
  if (face === 'left') {
    anchored.x = -inner.length_x / 2 + spec.bounding_box.length_x / 2 + inset;
  } else if (face === 'right') {
    anchored.x = inner.length_x / 2 - spec.bounding_box.length_x / 2 - inset;
  } else if (face === 'front') {
    anchored.y = -inner.width_y / 2 + spec.bounding_box.width_y / 2 + inset;
  } else if (face === 'back') {
    anchored.y = inner.width_y / 2 - spec.bounding_box.width_y / 2 - inset;
  }
  return {
    x: round(anchored.x),
    y: round(anchored.y),
  };
}

export function applyHardwareOffset(spec, position = { x: 0, y: 0 }, parameters = DEFAULT_PARAMETERS) {
  const keyBase = hardwareOffsetKeyBase(spec.hardware_id);
  return {
    x: round(Number(position.x || 0) + Number(parameters[`${keyBase}_offset_x`] || 0)),
    y: round(Number(position.y || 0) + Number(parameters[`${keyBase}_offset_y`] || 0)),
  };
}

export function hardwareOffsetKeyBase(hardwareId) {
  return `hw_${String(hardwareId || 'hardware').replace(/[^a-zA-Z0-9_]+/g, '_')}`;
}

export function buildHardwareTransform(spec, position, z) {
  return {
    hardware_id: spec.hardware_id,
    name: spec.name,
    category: spec.category,
    center: {
      x: round(position.x),
      y: round(position.y),
      z: round(z),
    },
    rotation: spec.rotation,
    layout_rotation_deg: spec.layout_rotation_deg || 0,
    bounding_box: spec.bounding_box,
    dimensions_mm: spec.dimensions_mm || spec.bounding_box,
    cad_reference: spec.cad_reference || {},
    openings: spec.openings,
    mounting: spec.mounting,
    legacy_reference: spec.legacy_reference || {},
    mounting_strategy: spec.mounting_strategy || 'profile_specific',
    mounting_holes: spec.mounting_holes || [],
    keepouts: spec.keepouts || [],
  };
}

export function buildOpeningTransforms(transform, enclosure, parameters = DEFAULT_PARAMETERS) {
  return (transform.openings || []).map((opening, index) => {
    const sourceCenter = openingSourceCenter(opening);
    return {
      id: `${transform.hardware_id}_${opening.id || index}`,
      hardware_id: transform.hardware_id,
      type: opening.type,
      face: opening.preferred_face || defaultOpeningFace(transform),
      basis: normalizeString(opening.basis),
      center: projectOpeningCenter(transform, opening, enclosure),
      source_center_mm: sourceCenter,
      clearance_mm: isFiniteNumber(opening.clearance_mm) ? Number(opening.clearance_mm) : null,
      projected_from_hardware: !hasOpeningLocalCenter(opening),
      layout_rotation_deg: transform.layout_rotation_deg || 0,
      size_mm: normalizeOpeningSize(opening, parameters),
      generated_by: 'layout_solver_tool',
    };
  });
}

export function normalizeOpeningSize(opening = {}, parameters = DEFAULT_PARAMETERS) {
  const size = { ...(opening.size_mm || {}) };
  if (opening.slot_mm) {
    size.width = Number(opening.slot_mm.width || size.width || 0);
    size.length = Number(opening.slot_mm.length || opening.slot_mm.length_x || size.length || size.length_x || 0);
  }
  if (opening.diameter_mm) size.diameter = Number(opening.diameter_mm);
  if (opening.count) size.count = Number(opening.count);
  if (opening.pitch_mm) size.pitch = Number(opening.pitch_mm);
  return applyOpeningParameterAdjustments(opening, size, parameters);
}

export function applyOpeningParameterAdjustments(opening = {}, size = {}, parameters = DEFAULT_PARAMETERS) {
  const result = { ...size };
  const delta = openingMarginDelta(opening, parameters);
  if (delta) {
    if (['rectangular_cutout', 'rectangular_window'].includes(opening.type)) {
      if (isPositiveNumber(result.width)) result.width = round(Math.max(0.2, Number(result.width) + delta * 2));
      if (isPositiveNumber(result.height)) result.height = round(Math.max(0.2, Number(result.height) + delta * 2));
    } else if (opening.type === 'round_hole' && isPositiveNumber(result.diameter)) {
      result.diameter = round(Math.max(0.2, Number(result.diameter) + delta * 2));
    }
  }
  if (['hole_array', 'slot_array'].includes(opening.type) && Number(parameters.vent_count) !== DEFAULT_PARAMETERS.vent_count) {
    result.count = Math.max(1, Math.round(Number(parameters.vent_count || result.count || 1)));
  }
  return result;
}

export function openingMarginDelta(opening = {}, parameters = DEFAULT_PARAMETERS) {
  const text = `${opening.id || ''} ${opening.type || ''} ${opening.basis || ''}`.toLowerCase();
  if (/usb|connector/.test(text)) return Number(parameters.usb_c_margin || 0) - DEFAULT_PARAMETERS.usb_c_margin;
  if (/screen|display|window|active_area/.test(text)) return Number(parameters.screen_window_margin || 0) - DEFAULT_PARAMETERS.screen_window_margin;
  if (/button|actuator/.test(text)) return Number(parameters.button_hole_margin || 0) - DEFAULT_PARAMETERS.button_hole_margin;
  return 0;
}

export function buildMountingTransforms(transform, parameters = DEFAULT_PARAMETERS) {
  if (transform.mounting_strategy === 'shell_through_screw_holes') return [];
  const bb = transform.bounding_box;
  const mounting = transform.mounting || {};
  const fixedStructure = isPlainObject(mounting.fixed_structure) ? mounting.fixed_structure : {};
  const clearance = Math.max(0, Number(mounting.clearance_mm ?? parameters.clearance ?? 0.6));
  const minFeature = Math.max(
    0.8,
    Number(fixedStructure.min_feature_mm || 0),
    round(Number(parameters.min_wall_thickness || DEFAULT_PARAMETERS.min_wall_thickness) * 0.5),
  );
  const pad = round(clearance * 2 + minFeature);
  const trayHeight = round(Math.max(
    minFeature,
    Number(fixedStructure.tray_thickness_mm || 0),
    1.4,
  ));
  const isLidMount = transform.mount_surface === 'lid_inner';
  const hardwareAnchorZ = isLidMount
    ? transform.center.z + bb.height_z / 2
    : transform.center.z - bb.height_z / 2;
  const trayCenterZ = round(hardwareAnchorZ + (isLidMount ? trayHeight / 2 : -trayHeight / 2));
  const anchorFace = isLidMount ? 'lid_inner' : 'base_floor_top';
  const mounts = [
    {
      id: `${transform.hardware_id}_tray`,
      hardware_id: transform.hardware_id,
      type: 'support_tray',
      role: isLidMount ? 'hold_down_support' : 'support',
      anchor_face: anchorFace,
      mount_surface: transform.mount_surface,
      center: {
        x: transform.center.x,
        y: transform.center.y,
        z: trayCenterZ,
      },
      size_mm: {
        length_x: round(bb.length_x + pad),
        width_y: round(bb.width_y + pad),
        height_z: trayHeight,
      },
      clearance_mm: clearance,
      engagement_mm: trayHeight,
    },
  ];
  const retainerHeight = Number(mounting.retainer_height_mm || 0);
  if (retainerHeight > 0) {
    const railThickness = round(Math.max(minFeature, clearance * 1.5));
    const railHeight = round(Math.max(retainerHeight, minFeature));
    const engagement = round(Math.max(minFeature, Math.min(railHeight, bb.height_z + clearance)));
    const z = round(hardwareAnchorZ + (isLidMount ? -railHeight / 2 : railHeight / 2));
    const yOffset = bb.width_y / 2 + railThickness / 2 + clearance;
    for (const side of [-1, 1]) {
      mounts.push({
        id: `${transform.hardware_id}_side_retainer_${side < 0 ? 'front' : 'back'}`,
        hardware_id: transform.hardware_id,
        type: isLidMount ? 'lid_press_retainer' : 'side_retainer',
        role: isLidMount ? 'press' : 'lateral_retainer',
        anchor_face: anchorFace,
        mount_surface: transform.mount_surface,
        center: {
          x: transform.center.x,
          y: round(transform.center.y + side * yOffset),
          z,
        },
        size_mm: {
          length_x: round(bb.length_x + pad),
          width_y: round(railThickness),
          height_z: railHeight,
        },
        clearance_mm: clearance,
        engagement_mm: engagement,
      });
    }
    const xOffset = bb.length_x / 2 + railThickness / 2 + clearance;
    for (const side of [-1, 1]) {
      mounts.push({
        id: `${transform.hardware_id}_end_stop_${side < 0 ? 'left' : 'right'}`,
        hardware_id: transform.hardware_id,
        type: isLidMount ? 'lid_press_end_stop' : 'end_stop',
        role: isLidMount ? 'press' : 'end_retainer',
        anchor_face: anchorFace,
        mount_surface: transform.mount_surface,
        center: {
          x: round(transform.center.x + side * xOffset),
          y: transform.center.y,
          z,
        },
        size_mm: {
          length_x: round(railThickness),
          width_y: round(bb.width_y + pad),
          height_z: railHeight,
        },
        clearance_mm: clearance,
        engagement_mm: engagement,
      });
    }
  }
  return mounts;
}

export function buildMountingHoleTransforms(transform, enclosure) {
  if (transform.mounting_strategy !== 'shell_through_screw_holes') return [];
  const isLidMount = transform.mount_surface === 'lid_inner';
  const face = isLidMount ? 'top' : 'bottom';
  const z = isLidMount ? enclosure.outer_box_size.height_z : 0;
  return (transform.mounting_holes || []).map((hole, index) => {
    const local = rotateLocalXY(hole, transform.layout_rotation_deg || 0);
    const diameter = round(Math.max(0.2, Number(hole.diameter_mm || 2.1)));
    return {
      id: `${transform.hardware_id}_mounting_hole_${index + 1}`,
      hardware_id: transform.hardware_id,
      type: 'mounting_screw_hole',
      role: hole.role || 'mounting_hole',
      face,
      mount_surface: transform.mount_surface,
      center: {
        x: round(transform.center.x + local.x),
        y: round(transform.center.y + local.y),
        z: round(z),
      },
      diameter_mm: diameter,
      size_mm: {
        diameter,
        length_x: diameter,
        width_y: diameter,
      },
      fastener: hole.fastener || 'M2 self-tapping',
      source_center_mm: {
        x: round(Number(hole.x || 0)),
        y: round(Number(hole.y || 0)),
        z: round(Number(hole.z || 0)),
      },
      source: hole.source || '',
      layout_rotation_deg: transform.layout_rotation_deg || 0,
      generated_by: 'layout_solver_tool',
    };
  });
}

export function projectOpeningCenter(transform, opening, enclosure) {
  const face = opening.preferred_face || defaultOpeningFace(transform);
  const sourceCenter = openingSourceCenter(opening);
  const local = rotateLocalXY(sourceCenter, transform.layout_rotation_deg || 0);
  const projected = {
    x: round(transform.center.x + local.x),
    y: round(transform.center.y + local.y),
    z: round(transform.center.z + Number(sourceCenter.z || 0)),
  };
  if (face === 'left') {
    return {
      x: round(-enclosure.outer_box_size.length_x / 2),
      y: projected.y,
      z: projected.z,
    };
  }
  if (face === 'right') {
    return {
      x: round(enclosure.outer_box_size.length_x / 2),
      y: projected.y,
      z: projected.z,
    };
  }
  if (face === 'front') {
    return {
      x: projected.x,
      y: round(-enclosure.outer_box_size.width_y / 2),
      z: projected.z,
    };
  }
  if (face === 'back') {
    return {
      x: projected.x,
      y: round(enclosure.outer_box_size.width_y / 2),
      z: projected.z,
    };
  }
  return {
    x: projected.x,
    y: projected.y,
    z: round(enclosure.outer_box_size.height_z),
  };
}

export function openingSourceCenter(opening = {}) {
  const source = isPlainObject(opening.center_mm)
    ? opening.center_mm
    : isPlainObject(opening.offset_mm)
      ? opening.offset_mm
      : {};
  return {
    x: round(Number(source.x || 0)),
    y: round(Number(source.y || 0)),
    z: round(Number(source.z || 0)),
  };
}

export function hasOpeningLocalCenter(opening = {}) {
  return isPlainObject(opening.center_mm) || isPlainObject(opening.offset_mm);
}

export function defaultOpeningFace(transform) {
  if (transform.category === 'controller') return 'left';
  if (transform.category === 'sensor') return 'front';
  return 'top';
}

export function hardwareWorldBox(item = {}) {
  const bb = item.bounding_box || {};
  const center = item.center || {};
  return worldBoxFromCenterAndSize(center, {
    length_x: Number(bb.length_x || 0),
    width_y: Number(bb.width_y || 0),
    height_z: Number(bb.height_z || 0),
  });
}

export function mountWorldBox(mount = {}) {
  const size = mount.size_mm || {};
  return worldBoxFromCenterAndSize(mount.center || {}, {
    length_x: Number(size.length_x || 0),
    width_y: Number(size.width_y || 0),
    height_z: Number(size.height_z || 0),
  });
}

export function worldBoxFromCenterAndSize(center = {}, size = {}) {
  if (size.length_x <= 0 || size.width_y <= 0 || size.height_z <= 0) return null;
  const x = Number(center.x || 0);
  const y = Number(center.y || 0);
  const z = Number(center.z || 0);
  return {
    min_x: round(x - size.length_x / 2),
    max_x: round(x + size.length_x / 2),
    min_y: round(y - size.width_y / 2),
    max_y: round(y + size.width_y / 2),
    min_z: round(z - size.height_z / 2),
    max_z: round(z + size.height_z / 2),
  };
}

export function keepoutWorldBox(transform, keepout = {}) {
  const local = normalizeKeepoutBox(keepout, transform.layout_rotation_deg || 0);
  if (!local) return null;
  return {
    min_x: round(transform.center.x + local.center.x - local.size.length_x / 2),
    max_x: round(transform.center.x + local.center.x + local.size.length_x / 2),
    min_y: round(transform.center.y + local.center.y - local.size.width_y / 2),
    max_y: round(transform.center.y + local.center.y + local.size.width_y / 2),
    min_z: round(transform.center.z + local.center.z - local.size.height_z / 2),
    max_z: round(transform.center.z + local.center.z + local.size.height_z / 2),
  };
}

export function normalizeKeepoutBox(keepout = {}, rotationDeg = 0) {
  let size = null;
  if (keepout.shape === 'box' && keepout.size_mm) {
    size = {
      length_x: Number(keepout.size_mm.length_x || 0),
      width_y: Number(keepout.size_mm.width_y || 0),
      height_z: Number(keepout.size_mm.height_z || 0),
    };
  } else if (keepout.shape === 'cylinder' && keepout.diameter_mm && keepout.height_z) {
    size = {
      length_x: Number(keepout.diameter_mm),
      width_y: Number(keepout.diameter_mm),
      height_z: Number(keepout.height_z),
    };
  }
  if (!size || size.length_x <= 0 || size.width_y <= 0 || size.height_z <= 0) return null;
  const center = rotateLocalXY(keepout.center_mm || {}, rotationDeg);
  const rotated = Math.abs(Number(rotationDeg || 0)) % 180 !== 0;
  return {
    center: {
      x: center.x,
      y: center.y,
      z: Number(keepout.center_mm?.z || 0),
    },
    size: rotated
      ? { length_x: size.width_y, width_y: size.length_x, height_z: size.height_z }
      : size,
  };
}

export function rotateLocalXY(center = {}, rotationDeg = 0) {
  const x = Number(center.x || 0);
  const y = Number(center.y || 0);
  const normalized = ((Number(rotationDeg || 0) % 360) + 360) % 360;
  if (normalized === 90) return { x: round(-y), y: round(x) };
  if (normalized === 180) return { x: round(-x), y: round(-y) };
  if (normalized === 270) return { x: round(y), y: round(-x) };
  return { x: round(x), y: round(y) };
}
