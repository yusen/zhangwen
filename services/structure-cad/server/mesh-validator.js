import { writeFile } from 'node:fs/promises';
import { spawn } from 'node:child_process';

const MESH_VALIDATION_TIMEOUT_MS = 90000;
const DEFAULT_THRESHOLDS = Object.freeze({
  overhang_angle_deg: 45,
  bridge_warn_mm: 8,
  bridge_fail_mm: 16,
});

export async function validateMeshArtifacts({
  python,
  environment = {},
  stlPaths = {},
  outputPath = '',
  parameters = {},
} = {}) {
  if (!environment?.cadqueryAvailable) {
    const report = buildPendingMeshReport('pending_missing_cadquery', 'CadQuery/OCP is required before real mesh validation can run.', {
      cadquery_available: false,
    });
    await writeMeshReport(outputPath, report);
    return report;
  }

  if (environmentHasMissingPackage(environment, 'trimesh')) {
    const report = buildPendingMeshReport('pending_missing_trimesh', 'Python package trimesh is missing, so real STL mesh validation is pending.', {
      cadquery_available: true,
      trimesh_available: false,
      missingPythonPackages: environment.missingPythonPackages || [],
    });
    await writeMeshReport(outputPath, report);
    return report;
  }

  const parts = [
    { id: 'base', label: 'base_part', path: stlPaths.baseStlPath },
    { id: 'lid', label: 'lid_part', path: stlPaths.lidStlPath },
    { id: 'assembly', label: 'assembly', path: stlPaths.stlPath },
  ].filter((item) => item.path);

  const payload = {
    parts,
    thresholds: {
      ...DEFAULT_THRESHOLDS,
      min_wall_thickness_mm: Number(parameters.min_wall_thickness || 0),
      wall_thickness_mm: Number(parameters.wall_thickness || 0),
    },
  };
  const result = await runPythonMeshValidation(python, payload);
  if (result.exitCode !== 0) {
    const missingTrimesh = /No module named ['"]?trimesh|ModuleNotFoundError.*trimesh/i.test(result.stderr);
    const report = missingTrimesh
      ? buildPendingMeshReport('pending_missing_trimesh', 'Python package trimesh is missing, so real STL mesh validation is pending.', {
          stderr: result.stderr,
        })
      : buildPendingMeshReport('pending_mesh_validation_failed', 'Mesh validation runner failed before producing a report.', {
          stdout: result.stdout,
          stderr: result.stderr,
        }, 'warn');
    await writeMeshReport(outputPath, report);
    return report;
  }

  let report;
  try {
    report = JSON.parse(result.stdout);
  } catch {
    report = buildPendingMeshReport('pending_mesh_validation_failed', 'Mesh validation runner returned invalid JSON.', {
      stdout: result.stdout,
      stderr: result.stderr,
    }, 'warn');
  }
  report = normalizeMeshReport(report);
  await writeMeshReport(outputPath, report);
  return report;
}

export function meshValidationStatus(report = null) {
  if (!report || typeof report !== 'object') return 'pending_missing_mesh_report';
  if (['pass', 'warn', 'fail'].includes(report.status)) return report.status;
  if (typeof report.status === 'string' && report.status.startsWith('pending')) return report.status;
  const checks = Array.isArray(report.checks) ? report.checks : [];
  if (checks.some((item) => item.status === 'fail')) return 'fail';
  if (checks.some((item) => item.status === 'warn')) return 'warn';
  if (checks.some((item) => String(item.status || '').startsWith('pending'))) return 'pending_mesh_validation';
  return checks.length ? 'pass' : 'pending_missing_mesh_report';
}

export function meshReportToCheck(report = null) {
  if (!report || typeof report !== 'object') {
    return {
      id: 'mesh_validation',
      label: '真实 mesh 校验',
      status: 'pending',
      message: '尚未生成真实 STL mesh 校验报告。',
      details: { status: 'pending_missing_mesh_report' },
    };
  }
  const status = normalizeCheckStatus(meshValidationStatus(report));
  return {
    id: 'mesh_validation',
    label: '真实 mesh 校验',
    status,
    message: report.message || meshValidationMessage(report),
    details: {
      mesh_validation_status: report.status || meshValidationStatus(report),
      checked_parts: Array.isArray(report.parts) ? report.parts.map((item) => item.id || item.label || item.path) : [],
      checks: Array.isArray(report.checks) ? report.checks : [],
      exports: report.exports || [],
    },
  };
}

function environmentHasMissingPackage(environment = {}, name) {
  if ((environment.missingPythonPackages || []).includes(name)) return true;
  const check = (environment.packageChecks || []).find((item) => item.name === name);
  return check ? check.status !== 'pass' : false;
}

function buildPendingMeshReport(status, message, details = {}, checkStatus = 'pending') {
  return {
    status,
    message,
    parts: [],
    checks: [
      {
        id: status,
        label: 'mesh validation runtime',
        status: checkStatus,
        message,
        details,
      },
    ],
    thresholds: DEFAULT_THRESHOLDS,
  };
}

function normalizeMeshReport(report = {}) {
  const checks = Array.isArray(report.checks) ? report.checks : [];
  return {
    status: report.status || summarizeMeshChecks(checks),
    message: report.message || meshValidationMessage({ ...report, checks }),
    parts: Array.isArray(report.parts) ? report.parts : [],
    checks,
    thresholds: report.thresholds || DEFAULT_THRESHOLDS,
  };
}

function summarizeMeshChecks(checks = []) {
  if (checks.some((item) => item.status === 'fail')) return 'fail';
  if (checks.some((item) => item.status === 'warn')) return 'warn';
  if (checks.some((item) => String(item.status || '').startsWith('pending'))) return 'pending_mesh_validation';
  return checks.length ? 'pass' : 'pending_mesh_validation';
}

function meshValidationMessage(report = {}) {
  const status = report.status || summarizeMeshChecks(report.checks || []);
  if (status === 'pass') return '真实 STL mesh 基础制造校验通过。';
  if (status === 'warn') return '真实 STL mesh 存在制造风险，需要人工复核。';
  if (status === 'fail') return '真实 STL mesh 存在阻断性制造问题。';
  return '真实 STL mesh 校验尚未完成。';
}

function normalizeCheckStatus(status) {
  if (status === 'pass' || status === 'warn' || status === 'fail') return status;
  return 'pending';
}

async function writeMeshReport(outputPath, report) {
  if (!outputPath) return;
  await writeFile(outputPath, JSON.stringify(report, null, 2), 'utf8');
}

function runPythonMeshValidation(python, payload) {
  return new Promise((resolve) => {
    const child = spawn(python, ['-c', MESH_VALIDATOR_SCRIPT], {
      windowsHide: true,
      stdio: ['pipe', 'pipe', 'pipe'],
    });
    let stdout = '';
    let stderr = '';
    const timer = setTimeout(() => {
      child.kill();
    }, MESH_VALIDATION_TIMEOUT_MS);
    child.stdout.on('data', (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on('data', (chunk) => {
      stderr += chunk.toString();
    });
    child.on('close', (exitCode) => {
      clearTimeout(timer);
      resolve({ exitCode, stdout, stderr });
    });
    child.on('error', (error) => {
      clearTimeout(timer);
      resolve({ exitCode: 1, stdout, stderr: error.message });
    });
    child.stdin.write(JSON.stringify(payload));
    child.stdin.end();
  });
}

const MESH_VALIDATOR_SCRIPT = String.raw`
import json
import math
import sys

import trimesh

payload = json.loads(sys.stdin.read() or "{}")
parts = payload.get("parts") or []
thresholds = payload.get("thresholds") or {}

def status_rank(status):
    return {"pass": 0, "pending": 1, "warn": 2, "fail": 3}.get(status, 1)

def worst_status(items):
    if not items:
        return "pending"
    return max((item.get("status", "pending") for item in items), key=status_rank)

def mesh_list(mesh):
    if hasattr(mesh, "geometry") and isinstance(mesh.geometry, dict):
        return list(mesh.geometry.values())
    return [mesh]

def number(value, fallback=0):
    try:
        result = float(value)
        if math.isfinite(result):
            return result
    except Exception:
        pass
    return fallback

def get_faces(mesh):
    faces = getattr(mesh, "faces", [])
    try:
        return len(faces)
    except Exception:
        return 0

def get_vertices(mesh):
    vertices = getattr(mesh, "vertices", [])
    try:
        return len(vertices)
    except Exception:
        return 0

def get_area_faces(mesh):
    area_faces = getattr(mesh, "area_faces", [])
    try:
        return [float(item) for item in area_faces]
    except Exception:
        return []

def get_extents(mesh):
    extents = getattr(mesh, "extents", [0, 0, 0])
    try:
        return [float(item) for item in extents]
    except Exception:
        return [0, 0, 0]

def analyze_part(part):
    path = part.get("path")
    meshes = mesh_list(trimesh.load_mesh(path, force="mesh"))
    part_checks = []
    part_info = {
        "id": part.get("id"),
        "label": part.get("label"),
        "path": path,
        "mesh_count": len(meshes),
        "face_count": sum(get_faces(mesh) for mesh in meshes),
        "vertex_count": sum(get_vertices(mesh) for mesh in meshes),
    }

    watertight_failures = []
    degenerate_faces = 0
    component_count = len(meshes)
    overhang_faces = 0
    bridge_span = 0
    for index, mesh in enumerate(meshes):
        if not bool(getattr(mesh, "is_watertight", False)):
            watertight_failures.append(index)
        degenerate_faces += sum(1 for area in get_area_faces(mesh) if area <= 1e-9)
        extents = get_extents(mesh)
        bridge_span = max(bridge_span, max(extents[0], extents[1]) if len(extents) >= 2 else 0)
        normals = getattr(mesh, "face_normals", [])
        for normal in normals:
            try:
                nz = float(normal[2])
            except Exception:
                continue
            if nz < -math.cos(math.radians(number(thresholds.get("overhang_angle_deg"), 45))):
                overhang_faces += 1

    part_checks.append({
        "id": "watertight",
        "label": "watertight",
        "status": "fail" if watertight_failures else "pass",
        "message": "mesh is watertight" if not watertight_failures else "mesh has open boundaries or is not watertight",
        "details": {"failed_mesh_indices": watertight_failures}
    })
    part_checks.append({
        "id": "manifold_and_degenerate",
        "label": "manifold and degenerate faces",
        "status": "fail" if degenerate_faces else "pass",
        "message": "no degenerate faces detected" if not degenerate_faces else "degenerate faces detected",
        "details": {"degenerate_face_count": degenerate_faces}
    })
    part_checks.append({
        "id": "connected_components",
        "label": "connected components",
        "status": "warn" if component_count > 1 else "pass",
        "message": "single connected mesh" if component_count <= 1 else "multiple mesh components detected",
        "details": {"component_count": component_count}
    })
    min_wall = number(thresholds.get("min_wall_thickness_mm"), 0)
    wall = number(thresholds.get("wall_thickness_mm"), 0)
    part_checks.append({
        "id": "thin_wall",
        "label": "thin wall",
        "status": "fail" if min_wall and wall and wall < min_wall else "pending",
        "message": "parameter wall thickness passes minimum" if min_wall and wall and wall >= min_wall else "local mesh wall thickness needs geometric thickness analysis",
        "details": {"wall_thickness_mm": wall, "min_wall_thickness_mm": min_wall, "requires_local_thickness": True}
    })
    bridge_warn = number(thresholds.get("bridge_warn_mm"), 8)
    bridge_fail = number(thresholds.get("bridge_fail_mm"), 16)
    overhang_status = "fail" if bridge_span > bridge_fail else "warn" if overhang_faces or bridge_span > bridge_warn else "pass"
    part_checks.append({
        "id": "overhang_bridge",
        "label": "overhang and bridge",
        "status": overhang_status,
        "message": "overhang/bridge risk estimated from face normals and XY span",
        "details": {"overhang_face_count": overhang_faces, "estimated_bridge_span_mm": bridge_span}
    })
    part_checks.append({
        "id": "self_intersection",
        "label": "self intersection",
        "status": "pending",
        "message": "trimesh self-intersection capability is not available in this runtime",
        "details": {"requires_advanced_mesh_backend": True}
    })
    return part_info, part_checks

report_parts = []
checks = []
for part in parts:
    info, part_checks = analyze_part(part)
    report_parts.append(info)
    for check in part_checks:
        item = dict(check)
        item["part_id"] = part.get("id")
        checks.append(item)

status = worst_status(checks)
print(json.dumps({
    "status": status,
    "message": "Real STL mesh validation completed.",
    "parts": report_parts,
    "checks": checks,
    "thresholds": thresholds
}, ensure_ascii=False))
`;
