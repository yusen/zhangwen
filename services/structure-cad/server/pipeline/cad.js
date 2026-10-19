import { writePreviewStlFiles } from '../stl-exporter.js';
import { hardwareOffsetKeyBase } from './layout.js';
import { DEFAULT_PARAMETERS } from './shared.js';

export function enclosureGenerator({ enclosure, layoutPlan, bom, hardwareProfiles, parameters }) {
  return {
    base_part: {
      type: 'rounded_rectangular_shell',
      size_mm: enclosure.outer_box_size,
    },
    lid_part: {
      type: 'flat_lid_with_lip',
      thickness_mm: enclosure.lid_thickness,
    },
    assembly: {
      parts: ['base_part', 'lid_part', ...hardwareProfiles.map((item) => item.id)],
    },
    cad_parameters: {
      generator: 'deterministic_cadquery_text_v1',
      note: '此代码文本由后端固定程序生成；当前环境未安装 CadQuery 时只作为展示和后续执行输入。',
    },
    cadquery_code: buildCadQueryCode({
      enclosure,
      layoutPlan,
      bom,
      hardwareProfiles,
      parameters,
    }),
  };
}

export function cadqueryRuntimeDetails(environment = {}) {
  return {
    python: environment?.python || '',
    pythonAvailable: Boolean(environment?.pythonAvailable),
    pythonVersion: environment?.pythonVersion || '',
    requiredPythonPackages: Array.isArray(environment?.requiredPythonPackages)
      ? environment.requiredPythonPackages
      : ['cadquery', 'OCP'],
    missingPythonPackages: Array.isArray(environment?.missingPythonPackages)
      ? environment.missingPythonPackages
      : [],
    packageChecks: Array.isArray(environment?.packageChecks)
      ? environment.packageChecks
      : [],
  };
}

export function cadqueryRuntimeMessage(environment = {}, details = cadqueryRuntimeDetails(environment)) {
  if (environment?.cadqueryAvailable) return '检测到 CadQuery，可接入真实 STEP/STL 导出。';
  if (!details.pythonAvailable && details.python) {
    return `当前 Python 不可用：${details.python}；真实 CadQuery 布尔建模和 STEP/STL 导出为 pending。`;
  }
  const missing = details.missingPythonPackages.filter((item) => ['cadquery', 'OCP'].includes(item));
  if (missing.length) {
    return `当前 Python 环境缺少 ${missing.join(', ')}；真实 CadQuery 布尔建模和 STEP/STL 导出为 pending。`;
  }
  return '当前 Python 环境未检测到 CadQuery/OCP，真实 CadQuery 布尔建模和 STEP/STL 导出为 pending。';
}

export async function exportPreviewTool({ rootDir, designId, enclosure, layoutPlan, environment }) {
  let stlExports = [];
  const warnings = [
    {
      id: 'preview_stl_simplified',
      status: 'warn',
      message: '当前 STL 是用于前端预览和接口验证的简化盒体/硬件包围盒，不等同于最终 CadQuery 布尔模型。',
    },
  ];
  try {
    stlExports = await writePreviewStlFiles({
      rootDir,
      designId,
      enclosure,
      layoutPlan,
    });
  } catch (error) {
    stlExports = buildFailedPreviewExports(error);
    warnings.push(buildExportWriteWarning({
      id: 'preview_export_write_failed',
      message: '简化 STL/glTF 预览文件写入失败；主体方案仍可查看，但预览下载暂不可用。',
      error,
    }));
  }
  const exports = [
    ...stlExports,
    {
      id: 'step',
      label: 'STEP',
      format: 'step',
      url: null,
      status: environment?.cadqueryAvailable ? 'not_generated_yet' : 'pending_missing_cadquery',
    },
  ];
  return {
    preview_assets: [],
    exports,
    warnings,
  };
}

export function buildFailedPreviewExports(error) {
  const message = exportErrorMessage(error);
  return [
    {
      id: 'base_stl',
      label: '底壳简化 STL',
      format: 'stl',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'preview_simplified',
    },
    {
      id: 'lid_stl',
      label: '上盖简化 STL',
      format: 'stl',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'preview_simplified',
    },
    {
      id: 'hardware_reference_stl',
      label: '硬件参考简化 STL',
      format: 'stl',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'preview_simplified',
    },
    {
      id: 'opening_reference_stl',
      label: '开孔参考简化 STL',
      format: 'stl',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'preview_simplified',
    },
    {
      id: 'preview_gltf',
      label: '整体简化 glTF 预览',
      format: 'gltf',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'preview_simplified',
    },
  ];
}

export function buildFailedMetadataExports(error) {
  const message = exportErrorMessage(error);
  return [
    {
      id: 'cadquery_code',
      label: 'CadQuery 生成器代码',
      format: 'py',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'deterministic_text',
    },
    {
      id: 'design_state_json',
      label: 'DesignState JSON',
      format: 'json',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'deterministic_state',
    },
    {
      id: 'checks_json',
      label: '校验报告 JSON',
      format: 'json',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'deterministic_validation',
    },
    {
      id: 'artifact_json',
      label: '完整 Artifact JSON',
      format: 'json',
      url: null,
      status: 'failed_write',
      message,
      fidelity: 'deterministic_artifact',
    },
  ];
}

export function buildExportWriteWarning({ id, message, error }) {
  return {
    id,
    status: 'warn',
    message,
    details: serializeExportError(error),
  };
}

export function exportErrorMessage(error) {
  if (error instanceof Error) return error.message;
  return String(error || 'unknown export write error');
}

export function serializeExportError(error) {
  if (!error || typeof error !== 'object') {
    return { message: exportErrorMessage(error) };
  }
  return {
    name: error.name || 'Error',
    code: typeof error.code === 'string' ? error.code : '',
    path: typeof error.path === 'string' ? error.path : '',
    message: exportErrorMessage(error),
  };
}

export function buildCadQueryCode({ enclosure, layoutPlan, bom, hardwareProfiles, parameters }) {
  const cadDataJson = pythonJsonLiteral({
    hardware_profiles: Object.fromEntries(hardwareProfiles.map((profile) => {
      const d = profile.dimensions_mm;
      return [
        String(profile.id),
        {
          name: String(profile.name || profile.id),
          category: String(profile.category || 'hardware'),
          size: [Number(d.length_x), Number(d.width_y), Number(d.height_z)],
          dimensions: profile.dimensions_mm || {},
          cad_reference: profile.cad_reference || {},
          legacy_reference: profile.legacy_reference || {},
          keepouts: Array.isArray(profile.keepouts) ? profile.keepouts : [],
          openings: Array.isArray(profile.opening) ? profile.opening : [],
        },
      ];
    })),
    hardware_transforms: (layoutPlan.hardware_transforms || []).map((item) => ({
      id: String(item.hardware_id),
      name: String(item.name || item.hardware_id),
      category: String(item.category || ''),
      center: [Number(item.center.x), Number(item.center.y), Number(item.center.z)],
      size: [
        Number(item.bounding_box.length_x),
        Number(item.bounding_box.width_y),
        Number(item.bounding_box.height_z),
      ],
      dimensions: item.dimensions_mm || item.bounding_box || {},
      cad_reference: item.cad_reference || {},
      keepouts: Array.isArray(item.keepouts) ? item.keepouts : [],
      openings: Array.isArray(item.openings) ? item.openings : [],
      layout_rotation_deg: Number(item.layout_rotation_deg || 0),
    })),
    opening_transforms: (layoutPlan.opening_transforms || []).map((item) => ({
      id: String(item.id),
      hardware_id: String(item.hardware_id),
      type: String(item.type),
      face: String(item.face),
      basis: String(item.basis || ''),
      center: [Number(item.center.x), Number(item.center.y), Number(item.center.z)],
      source_center_mm: item.source_center_mm || { x: 0, y: 0, z: 0 },
      clearance_mm: item.clearance_mm ?? null,
      projected_from_hardware: Boolean(item.projected_from_hardware),
      size: item.size_mm || {},
    })),
    mounting_hole_transforms: (layoutPlan.mounting_hole_transforms || []).map((item) => ({
      id: String(item.id),
      hardware_id: String(item.hardware_id),
      type: String(item.type || 'mounting_screw_hole'),
      role: String(item.role || 'mounting_hole'),
      face: String(item.face),
      mount_surface: String(item.mount_surface || ''),
      center: [Number(item.center.x), Number(item.center.y), Number(item.center.z)],
      source_center_mm: item.source_center_mm || { x: 0, y: 0, z: 0 },
      diameter_mm: Number(item.diameter_mm || item.size_mm?.diameter || 2.1),
      fastener: String(item.fastener || 'M2 self-tapping'),
      source: String(item.source || ''),
      size: item.size_mm || {},
    })),
    mounting_transforms: (layoutPlan.mounting_transforms || []).map((item) => ({
      id: String(item.id),
      hardware_id: String(item.hardware_id),
      type: String(item.type),
      role: String(item.role || ''),
      anchor_face: String(item.anchor_face || ''),
      mount_surface: String(item.mount_surface || 'base_floor'),
      center: [Number(item.center.x), Number(item.center.y), Number(item.center.z)],
      size: [
        Number(item.size_mm.length_x),
        Number(item.size_mm.width_y),
        Number(item.size_mm.height_z),
      ],
      clearance_mm: item.clearance_mm ?? null,
      engagement_mm: item.engagement_mm ?? null,
    })),
    screw_bosses: (enclosure.screw_bosses || []).map((item) => ({
      x: Number(item.x),
      y: Number(item.y),
    })),
    bom,
  });

  return `# ZW-CAD-intent deterministic CadQuery generator
# This code is generated by backend tools, not directly by an LLM.
# Units: millimeters.

import json
import cadquery as cq

outer_length = ${enclosure.outer_box_size.length_x}
outer_width = ${enclosure.outer_box_size.width_y}
outer_height = ${enclosure.outer_box_size.height_z}
inner_length = ${enclosure.inner_box_size.length_x}
inner_width = ${enclosure.inner_box_size.width_y}
inner_height = ${enclosure.inner_box_size.height_z}
wall_thickness = ${parameters.wall_thickness}
floor_thickness = ${parameters.floor_thickness}
lid_thickness = ${parameters.lid_thickness}
lid_lip_height = ${parameters.lid_lip_height}
lid_clearance = ${parameters.lid_clearance}
corner_radius = ${parameters.corner_radius}
screw_boss_diameter = ${parameters.screw_boss_diameter}
screw_hole_diameter = ${parameters.screw_hole_diameter}

cad_data = json.loads(${cadDataJson})
hardware_profiles = cad_data["hardware_profiles"]
hardware_transforms = cad_data["hardware_transforms"]
opening_transforms = cad_data["opening_transforms"]
mounting_hole_transforms = cad_data["mounting_hole_transforms"]
mounting_transforms = cad_data["mounting_transforms"]
screw_bosses = cad_data["screw_bosses"]
bom = cad_data["bom"]


def rounded_box(length, width, height, radius):
    part = cq.Workplane("XY").box(float(length), float(width), float(height), centered=(True, True, False))
    effective_radius = max(0, min(float(radius), float(length) / 2 - 0.2, float(width) / 2 - 0.2))
    if effective_radius <= 0:
        return part
    try:
        return part.edges("|Z").fillet(effective_radius)
    except Exception:
        return part


def box_part(size, center):
    return cq.Workplane("XY").box(float(size[0]), float(size[1]), float(size[2])).translate(tuple(center))


def cylinder_part(diameter, height, center, axis="z"):
    part = cq.Workplane("XY").circle(float(diameter) / 2).extrude(float(height))
    if axis == "x":
        part = part.rotate((0, 0, 0), (0, 1, 0), 90)
    elif axis == "y":
        part = part.rotate((0, 0, 0), (1, 0, 0), 90)
    return part.translate(tuple(center))


def build_hollow_base():
    base_height = outer_height - lid_thickness
    outer = rounded_box(outer_length, outer_width, base_height, corner_radius)
    inner_cut = (
        cq.Workplane("XY")
        .workplane(offset=floor_thickness)
        .box(inner_length, inner_width, outer_height, centered=(True, True, False))
    )
    return outer.cut(inner_cut)


def apply_screw_bosses(base):
    boss_height = max(0.2, outer_height - lid_thickness - floor_thickness - 0.4)
    for boss in screw_bosses:
        boss_part = (
            cq.Workplane("XY")
            .center(float(boss["x"]), float(boss["y"]))
            .circle(float(screw_boss_diameter) / 2)
            .extrude(float(boss_height))
            .translate((0, 0, floor_thickness))
        )
        base = base.union(boss_part)
    screw_hole_points = [(boss["x"], boss["y"]) for boss in screw_bosses]
    if screw_hole_points:
        base = (
            base.faces(">Z")
            .workplane()
            .pushPoints(screw_hole_points)
            .circle(screw_hole_diameter / 2)
            .cutThruAll()
        )
    return base


def apply_lid_screw_holes(lid):
    screw_hole_points = [(boss["x"], boss["y"]) for boss in screw_bosses]
    if screw_hole_points:
        lid = (
            lid.faces(">Z")
            .workplane()
            .pushPoints(screw_hole_points)
            .circle(screw_hole_diameter / 2)
            .cutThruAll()
        )
    return lid


def rectangular_cut(part, opening, width=10, height=6):
    x, y, z = opening["center"]
    if opening["face"] == "left":
        cutter = cq.Workplane("YZ").center(y, z).box(width, height, wall_thickness * 8)
        return part.cut(cutter.translate((-outer_length / 2, 0, 0)))
    if opening["face"] == "right":
        cutter = cq.Workplane("YZ").center(y, z).box(width, height, wall_thickness * 8)
        return part.cut(cutter.translate((outer_length / 2, 0, 0)))
    if opening["face"] == "front":
        cutter = cq.Workplane("XZ").center(x, z).box(width, height, wall_thickness * 8)
        return part.cut(cutter.translate((0, -outer_width / 2, 0)))
    if opening["face"] == "back":
        cutter = cq.Workplane("XZ").center(x, z).box(width, height, wall_thickness * 8)
        return part.cut(cutter.translate((0, outer_width / 2, 0)))
    cutter = cq.Workplane("XY").center(x, y).box(width, height, max(lid_thickness + lid_lip_height, 1) * 4)
    return part.cut(cutter.translate((0, 0, outer_height - lid_thickness / 2)))


def round_cut(part, opening, diameter=4):
    x, y, z = opening["center"]
    if opening["face"] == "bottom":
        cutter = cq.Workplane("XY").center(x, y).circle(diameter / 2).extrude(max(floor_thickness, 1) * 4, both=True)
        return part.cut(cutter)
    if opening["face"] == "left":
        cutter = cq.Workplane("YZ").center(y, z).circle(diameter / 2).extrude(wall_thickness * 8, both=True)
        return part.cut(cutter.translate((-outer_length / 2, 0, 0)))
    if opening["face"] == "right":
        cutter = cq.Workplane("YZ").center(y, z).circle(diameter / 2).extrude(wall_thickness * 8, both=True)
        return part.cut(cutter.translate((outer_length / 2, 0, 0)))
    if opening["face"] == "front":
        cutter = cq.Workplane("XZ").center(x, z).circle(diameter / 2).extrude(wall_thickness * 8, both=True)
        return part.cut(cutter.translate((0, -outer_width / 2, 0)))
    if opening["face"] == "back":
        cutter = cq.Workplane("XZ").center(x, z).circle(diameter / 2).extrude(wall_thickness * 8, both=True)
        return part.cut(cutter.translate((0, outer_width / 2, 0)))
    cutter = cq.Workplane("XY").center(x, y).circle(diameter / 2).extrude(max(lid_thickness + lid_lip_height, 1) * 4, both=True)
    return part.cut(cutter.translate((0, 0, outer_height - lid_thickness)))


def opening_rect_size(opening, default_width, default_height):
    size = opening.get("size") or {}
    width = size.get("width") or size.get("length_x") or default_width
    height = size.get("height") or size.get("width_y") or default_height
    return float(width), float(height)


def opening_slot_size(opening, default_length, default_width):
    size = opening.get("size") or {}
    length = size.get("length") or size.get("length_x") or default_length
    width = size.get("width") or size.get("width_y") or default_width
    return float(length), float(width)


def opening_diameter(opening, default_diameter):
    size = opening.get("size") or {}
    return float(size.get("diameter") or size.get("diameter_mm") or default_diameter)


def opening_count(opening):
    size = opening.get("size") or {}
    return max(1, int(size.get("count") or 1))


def opening_pitch(opening, fallback):
    size = opening.get("size") or {}
    return float(size.get("pitch") or size.get("pitch_mm") or fallback)


def centered_offsets(count, pitch):
    start = -pitch * (count - 1) / 2
    return [start + index * pitch for index in range(count)]


def shifted_opening(opening, offset, axis):
    shifted = dict(opening)
    x, y, z = opening["center"]
    face = opening["face"]
    if axis == "secondary":
        if face == "top":
            shifted["center"] = (x, y + offset, z)
        else:
            shifted["center"] = (x, y, z + offset)
    elif face in ("left", "right"):
        shifted["center"] = (x, y + offset, z)
    else:
        shifted["center"] = (x + offset, y, z)
    return shifted


def apply_openings(base, lid):
    for opening in opening_transforms:
        if opening["type"] in ("rectangular_cutout", "rectangular_window"):
            width, height = opening_rect_size(opening, 18, 10) if opening["face"] == "top" else opening_rect_size(opening, 10, 6)
            if opening["face"] == "top":
                lid = rectangular_cut(lid, opening, width, height)
            else:
                base = rectangular_cut(base, opening, width, height)
        elif opening["type"] == "round_hole":
            diameter = opening_diameter(opening, 4)
            if opening["face"] == "top":
                lid = round_cut(lid, opening, diameter)
            else:
                base = round_cut(base, opening, diameter)
        elif opening["type"] == "hole_array":
            diameter = opening_diameter(opening, 4)
            pitch = opening_pitch(opening, diameter)
            for offset in centered_offsets(opening_count(opening), pitch):
                item = shifted_opening(opening, offset, "primary")
                if opening["face"] == "top":
                    lid = round_cut(lid, item, diameter)
                else:
                    base = round_cut(base, item, diameter)
        elif opening["type"] == "slot_array":
            length, width = opening_slot_size(opening, 10, 2)
            pitch = opening_pitch(opening, width)
            for offset in centered_offsets(opening_count(opening), pitch):
                item = shifted_opening(opening, offset, "secondary")
                if opening["face"] == "top":
                    lid = rectangular_cut(lid, item, length, width)
                else:
                    base = rectangular_cut(base, item, length, width)
    return base, lid


def apply_mounting_holes(base, lid):
    for hole in mounting_hole_transforms:
        diameter = float(hole.get("diameter_mm") or opening_diameter(hole, 2.1))
        if hole["face"] == "top":
            lid = round_cut(lid, hole, diameter)
        else:
            base = round_cut(base, hole, diameter)
    return base, lid


def build_mounts():
    mounts = []
    for mount in mounting_transforms:
        pad = box_part(mount["size"], mount["center"])
        mounts.append(pad)
    return mounts


def apply_mounts(base, lid):
    for mount in mounting_transforms:
        pad = box_part(mount["size"], mount["center"])
        if mount.get("mount_surface") == "lid_inner":
            lid = lid.union(pad)
        else:
            base = base.union(pad)
    return base, lid


def build_lid():
    lid = rounded_box(outer_length, outer_width, lid_thickness, corner_radius)
    lip_outer_length = max(1, inner_length - lid_clearance * 2)
    lip_outer_width = max(1, inner_width - lid_clearance * 2)
    lip_wall = max(1.0, min(wall_thickness * 0.72, lip_outer_length / 5, lip_outer_width / 5))
    lip_inner_length = max(0.2, lip_outer_length - lip_wall * 2)
    lip_inner_width = max(0.2, lip_outer_width - lip_wall * 2)
    lip = cq.Workplane("XY").box(lip_outer_length, lip_outer_width, lid_lip_height, centered=(True, True, False))
    lip_void = cq.Workplane("XY").box(lip_inner_length, lip_inner_width, lid_lip_height + 0.8, centered=(True, True, False))
    lip = lip.cut(lip_void)
    lip = lip.translate((0, 0, -lid_lip_height))
    return lid.union(lip).translate((0, 0, outer_height - lid_thickness))


def rotate_part_for_item(part, item):
    angle = float(item.get("layout_rotation_deg") or 0)
    if abs(angle) < 0.001:
        return part
    center = item["center"]
    return part.rotate((center[0], center[1], 0), (center[0], center[1], 1), angle)


def profile_note(profile, note_id):
    legacy = profile.get("legacy_reference") or {}
    for note in legacy.get("notes") or []:
        if note.get("id") == note_id:
            return note.get("value") or {}
    return {}


def feature_data_for(profile):
    return profile_note(profile, "grove_features_mm") or profile_note(profile, "xiao_features_mm") or {}


def pcb_thickness_for(profile, size):
    dims = profile.get("dimensions") or {}
    fallback = min(1.6, float(size[2]) * 0.45)
    return min(float(size[2]), max(0.6, float(dims.get("pcb_thickness") or dims.get("pcb_thickness_assumed") or fallback)))


def pcb_center_z_for(item, profile):
    size = item["size"]
    center = item["center"]
    return center[2] - float(size[2]) / 2 + pcb_thickness_for(profile, size) / 2


def local_center_from_pcb(item, profile, x=0, y=0, z=0):
    center = item["center"]
    return [
        center[0] + float(x or 0),
        center[1] + float(y or 0),
        pcb_center_z_for(item, profile) + float(z or 0),
    ]


def local_box_part(item, profile, size, local_center):
    return rotate_part_for_item(box_part(size, local_center_from_pcb(
        item,
        profile,
        local_center[0],
        local_center[1],
        local_center[2],
    )), item)


def local_cylinder_part(item, profile, diameter, height, local_center, axis="z"):
    return rotate_part_for_item(cylinder_part(
        diameter,
        height,
        local_center_from_pcb(item, profile, local_center[0], local_center[1], local_center[2]),
        axis,
    ), item)


def add_keepout_parts(parts, item, profile):
    # Keepouts stay in cad_data for internal fit checks, but are not rendered in user-facing previews.
    return parts


def add_grove_connector_reference(parts, item, profile, features):
    connector = features.get("connector_keepout") or {}
    if not connector:
        return
    width = float(connector.get("width") or 8)
    depth = float(connector.get("depth") or 8)
    height = float(connector.get("height") or 4)
    side = str(connector.get("side") or "").upper()
    size = [depth, width, height] if side in ("+X", "-X") else [width, depth, height]
    z = connector.get("center_z_from_pcb_center")
    if z is None:
        z = connector.get("center_z")
    if z is None:
        z = pcb_thickness_for(profile, item["size"]) / 2 + height / 2
    parts.append(local_box_part(item, profile, size, [
        float(connector.get("center_x") or 0),
        float(connector.get("center_y") or 0),
        float(z),
    ]))


def add_xiao_reference(parts, item, profile, features):
    pcb_thickness = pcb_thickness_for(profile, item["size"])
    main = features.get("main_component") or {}
    if main:
        parts.append(local_box_part(item, profile, [
            float(main.get("length_x") or 12),
            float(main.get("width_y") or 13),
            float(main.get("height") or 1),
        ], [
            float(main.get("center_x") or -3),
            float(main.get("center_y") or 0),
            float(main.get("center_z_from_pcb_center") or (pcb_thickness / 2 + 0.5)),
        ]))
    port = features.get("typec_port") or profile_note(profile, "typec_port_mm") or {}
    if port:
        height = float(port.get("height") or 3.2)
        width = float(port.get("length_y") or port.get("width_y") or port.get("width") or 8.8)
        depth = min(5.2, max(2.2, float(port.get("outer_protrusion") or 1.5) + 2.4))
        parts.append(local_box_part(item, profile, [depth, width, height], [
            float(port.get("center_x_from_board_center") or port.get("center_x") or item["size"][0] / 2 - depth / 2),
            float(port.get("center_y_from_board_center") or port.get("center_y") or 0),
            float(port.get("center_z_from_pcb_center") or (pcb_thickness / 2 + height / 2)),
        ]))


def add_button_reference(parts, item, profile, features):
    buttons = features.get("buttons") or []
    if not buttons:
        count = 2 if "dual" in str(item.get("id", "")).lower() else 1
        pitch = min(float(item["size"][0]) * 0.5, 20)
        buttons = [{"center_x": (index - (count - 1) / 2) * pitch, "center_y": 0} for index in range(count)]
    pcb_thickness = pcb_thickness_for(profile, item["size"])
    for button in buttons:
        x = float(button.get("center_x") or 0)
        y = float(button.get("center_y") or 0)
        body_w = float(button.get("body_width") or 12)
        body_d = float(button.get("body_depth") or 12)
        body_h = float(button.get("body_height") or 2.4)
        stem_d = float(button.get("stem_diameter") or 3.8)
        stem_h = float(button.get("stem_height") or 3.2)
        cap_d = float(button.get("cap_diameter") or max(8, body_w))
        cap_h = float(button.get("cap_height") or 3.2)
        parts.append(local_box_part(item, profile, [body_w, body_d, body_h], [x, y, pcb_thickness / 2 + body_h / 2]))
        parts.append(local_cylinder_part(item, profile, stem_d, stem_h, [x, y, pcb_thickness / 2 + body_h + stem_h / 2]))
        parts.append(local_cylinder_part(item, profile, cap_d, cap_h, [x, y, pcb_thickness / 2 + body_h + stem_h + cap_h / 2]))


def add_ultrasonic_reference(parts, item, profile, features):
    transducers = features.get("transducers") or {}
    centers = transducers.get("centers") or [{"x": -12.5, "y": 0}, {"x": 12.5, "y": 0}]
    diameter = float(transducers.get("diameter") or 16)
    height = float(transducers.get("height") or 12)
    pcb_thickness = pcb_thickness_for(profile, item["size"])
    for center in centers:
        parts.append(local_cylinder_part(item, profile, diameter, height, [
            float(center.get("x") or 0),
            float(center.get("y") or 0),
            pcb_thickness / 2 + height / 2,
        ]))


def add_category_reference_parts(parts, item, profile):
    size = [float(item["size"][0]), float(item["size"][1]), float(item["size"][2])]
    dims = profile.get("dimensions") or item.get("dimensions") or {}
    category = str(profile.get("category") or item.get("category") or "").lower()
    shape = str((profile.get("cad_reference") or {}).get("shape", "")).lower()
    features = feature_data_for(profile)
    pcb_thickness = pcb_thickness_for(profile, size)
    parts.append(local_box_part(item, profile, [size[0], size[1], pcb_thickness], [0, 0, 0]))

    text = f"{item.get('id', '')} {category} {shape}"
    add_grove_connector_reference(parts, item, profile, features)
    if "xiao" in text or "pcb_with_usb" in text:
        add_xiao_reference(parts, item, profile, features)
    elif "ultrasonic" in text:
        add_ultrasonic_reference(parts, item, profile, features)
    elif "button" in text:
        add_button_reference(parts, item, profile, features)
    elif "display" in text or "oled" in text or "screen" in text:
        panel_length = float(dims.get("panel_length_x", size[0] * 0.72))
        panel_width = float(dims.get("panel_width_y", size[1] * 0.58))
        parts.append(local_box_part(item, profile, [panel_length, panel_width, max(0.35, size[2] * 0.08)], [0, 0, pcb_thickness / 2 + 0.25]))
    elif "buzzer" in text or "speaker" in text:
        parts.append(local_cylinder_part(item, profile, min(size[0], size[1]) * 0.72, max(1.2, size[2] * 0.45), [0, 0, pcb_thickness / 2 + max(1.2, size[2] * 0.45) / 2]))
    elif "battery" in text:
        parts.append(local_cylinder_part(item, profile, min(size[1] * 0.7, size[2] * 0.7), size[0] * 0.82, [0, 0, pcb_thickness / 2 + min(size[1] * 0.7, size[2] * 0.7) / 2], "x"))
    elif "sensor" in text or "pir" in text or "camera" in text:
        parts.append(local_cylinder_part(item, profile, min(size[0], size[1]) * 0.36, max(1.0, size[2] * 0.28), [0, 0, pcb_thickness / 2 + max(1.0, size[2] * 0.28) / 2]))
    else:
        component_height = max(0.8, min(size[2] - pcb_thickness, max(1.2, size[2] * 0.28)))
        parts.append(local_box_part(item, profile, [size[0] * 0.36, size[1] * 0.32, component_height], [-size[0] * 0.12, 0, pcb_thickness / 2 + component_height / 2]))


def build_hardware_references():
    parts = []
    for item in hardware_transforms:
        profile = hardware_profiles.get(item["id"], {})
        add_category_reference_parts(parts, item, profile)
    return parts


base_part = build_hollow_base()
base_part = apply_screw_bosses(base_part)
lid_part = build_lid()
lid_part = apply_lid_screw_holes(lid_part)
base_part, lid_part = apply_mounts(base_part, lid_part)
base_part, lid_part = apply_openings(base_part, lid_part)
base_part, lid_part = apply_mounting_holes(base_part, lid_part)
mount_parts = build_mounts()
hardware_reference_parts = build_hardware_references()
`;
}

export function buildPreviewAssets({ enclosure, layoutPlan, parameters = DEFAULT_PARAMETERS }) {
  const hardwareItems = (layoutPlan.hardware_transforms || []).map((item) => ({
    id: item.hardware_id,
    name: item.name,
    category: item.category,
    center: item.center,
    size: item.bounding_box,
    dimensions_mm: item.dimensions_mm || item.bounding_box,
    cad_reference: item.cad_reference || {},
    openings: item.openings || [],
    keepouts: item.keepouts || [],
    surface: item.mount_surface,
    layout_rotation_deg: item.layout_rotation_deg || 0,
  }));
  return [
    {
      id: 'scene_preview',
      type: 'layout_scene',
      units: 'mm',
      enclosure: {
        outer_box_size: enclosure.outer_box_size,
        inner_box_size: enclosure.inner_box_size,
        screw_bosses: enclosure.screw_bosses,
        wall_thickness: enclosure.wall_thickness,
        floor_thickness: enclosure.floor_thickness,
        lid_thickness: enclosure.lid_thickness,
        lid_lip_height: enclosure.lid_lip_height,
        lid_clearance: enclosure.lid_clearance,
        corner_radius: enclosure.corner_radius,
        screw_boss_diameter: parameters.screw_boss_diameter,
        screw_hole_diameter: parameters.screw_hole_diameter,
      },
      hardware: hardwareItems,
      openings: [
        ...(layoutPlan.opening_transforms || []),
        ...(layoutPlan.mounting_hole_transforms || []),
      ],
      mounts: layoutPlan.mounting_transforms,
      modes: {
        assembly: {
          show: ['base', 'lid', 'hardware', 'openings', 'mounts'],
          explode: false,
        },
        exploded: {
          show: ['base', 'lid', 'hardware', 'openings', 'mounts'],
          explode: true,
        },
        base: {
          show: ['base', 'mounts'],
          explode: false,
        },
        lid: {
          show: ['lid', 'mounts'],
          explode: false,
        },
        hardware: {
          show: ['hardware'],
          explode: false,
        },
      },
    },
  ];
}

export function buildParameterGroups(parameters, enclosure, layoutPlan = null) {
  const hardware = {};
  for (const item of layoutPlan?.hardware_transforms || []) {
    const keyBase = hardwareOffsetKeyBase(item.hardware_id);
    hardware[`${keyBase}_offset_x`] = Number(parameters[`${keyBase}_offset_x`] || 0);
    hardware[`${keyBase}_offset_y`] = Number(parameters[`${keyBase}_offset_y`] || 0);
  }
  return {
    box: {
      inner_length_x: parameters.inner_length_x > 0 ? parameters.inner_length_x : enclosure.inner_box_size.length_x,
      inner_width_y: parameters.inner_width_y > 0 ? parameters.inner_width_y : enclosure.inner_box_size.width_y,
      inner_height_z: parameters.inner_height_z > 0 ? parameters.inner_height_z : enclosure.inner_box_size.height_z,
      wall_thickness: parameters.wall_thickness,
      corner_radius: parameters.corner_radius,
    },
    lid: {
      lid_thickness: parameters.lid_thickness,
      lid_lip_height: parameters.lid_lip_height,
      lid_clearance: parameters.lid_clearance,
    },
    printing: {
      min_wall_thickness: parameters.min_wall_thickness,
      clearance: parameters.clearance,
      screw_boss_diameter: parameters.screw_boss_diameter,
      screw_hole_diameter: parameters.screw_hole_diameter,
    },
    openings: {
      usb_c_margin: parameters.usb_c_margin,
      screen_window_margin: parameters.screen_window_margin,
      button_hole_margin: parameters.button_hole_margin,
      vent_count: parameters.vent_count,
    },
    layout: {
      hardware_gap: parameters.hardware_gap,
      edge_clearance: parameters.edge_clearance,
    },
    hardware,
  };
}

export function pythonJsonLiteral(value) {
  return pyString(JSON.stringify(stripUnsafeTextForPython(value)));
}

export function pyString(value) {
  return JSON.stringify(String(value)).replace(/[\u007f-\uffff]/g, (char) => {
    const code = char.charCodeAt(0).toString(16).padStart(4, '0');
    return `\\u${code}`;
  });
}

export function stripUnsafeTextForPython(value) {
  if (Array.isArray(value)) return value.map(stripUnsafeTextForPython);
  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, stripUnsafeTextForPython(item)]),
    );
  }
  if (typeof value === 'string') {
    return value.replace(/[\uD800-\uDFFF]/g, '?');
  }
  return value;
}
