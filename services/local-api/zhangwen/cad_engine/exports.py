"""Fixed-name CAD exports, snapshots, manifests, and compact GLB generation."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from pathlib import Path
import struct
from typing import Any

from zhangwen.cad_engine.geometry import CadGeometry, GeometryPart, assembly_compound
from zhangwen.cad_engine.layout import combined_aabb
from zhangwen.cad_engine.models import (
    Aabb,
    ArtifactManifest,
    CadBuildSpec,
    GeometrySummary,
    ManifestFile,
    PartGeometrySummary,
    ValidationReport,
)


ENGINE_VERSION = "0.1.0"


@dataclass(frozen=True)
class GeometryExportResult:
    files: tuple[Path, ...]
    summary: GeometrySummary


def export_geometry(geometry: CadGeometry, output_directory: Path) -> GeometryExportResult:
    """Write STEP, printable STLs, and a GLB preview under fixed names."""

    import cadquery as cq

    step_file = output_directory / "assembly.step"
    glb_file = output_directory / "preview.glb"
    cq.exporters.export(assembly_compound(geometry), str(step_file))
    printable_files: list[Path] = []
    for part in geometry.printable_parts:
        part_step = output_directory / f"{part.part_id}.step"
        part_stl = output_directory / f"{part.part_id}.stl"
        cq.exporters.export(part.shape, str(part_step))
        cq.exporters.export(
            part.shape,
            str(part_stl),
            tolerance=0.05,
            angularTolerance=0.1,
            opt={"ascii": True},
        )
        printable_files.extend((part_step, part_stl))
    triangle_count = write_glb(geometry.parts, glb_file)
    summary = geometry_summary(geometry, triangle_count=triangle_count)
    return GeometryExportResult(
        files=(step_file, *printable_files, glb_file),
        summary=summary,
    )


def write_snapshots(
    *,
    spec: CadBuildSpec,
    report: ValidationReport,
    summary: GeometrySummary,
    output_directory: Path,
) -> tuple[Path, ...]:
    parameters_file = output_directory / "parameters.json"
    profiles_file = output_directory / "profiles.json"
    validation_file = output_directory / "validation.json"
    summary_file = output_directory / "geometry-summary.json"
    parameter_snapshot = {
        "schema_version": spec.schema_version,
        "design_id": spec.design_id,
        "template": spec.template,
        "template_revision": spec.template_revision,
        "units": spec.units,
        "enclosure": (
            spec.enclosure.model_dump(mode="json")
            if spec.enclosure is not None
            else None
        ),
        "component_mount": (
            spec.component_mount.model_dump(mode="json")
            if spec.component_mount is not None
            else None
        ),
        "freeform_geometry": (
            spec.freeform_geometry.model_dump(mode="json")
            if spec.freeform_geometry is not None
            else None
        ),
        "standoffs": [item.model_dump(mode="json") for item in spec.standoffs],
        "openings": [item.model_dump(mode="json") for item in spec.openings],
        "hardware": [item.model_dump(mode="json") for item in spec.hardware],
    }
    _write_json(parameters_file, parameter_snapshot)
    _write_json(
        profiles_file,
        {"profiles": [profile.model_dump(mode="json") for profile in spec.profiles]},
    )
    _write_json(validation_file, report.model_dump(mode="json"))
    _write_json(summary_file, summary.model_dump(mode="json"))
    return parameters_file, profiles_file, validation_file, summary_file


def write_manifest(
    *,
    spec: CadBuildSpec,
    files: tuple[Path, ...],
    output_directory: Path,
    manifest_design_id: str | None = None,
    manifest_spec_sha256: str | None = None,
) -> tuple[Path, ArtifactManifest]:
    roles = {
        "assembly.step": ("step", "model/step"),
        "base.step": ("step_printable_parts", "model/step"),
        "base.stl": ("base_stl", "model/stl"),
        "lid.step": ("step_printable_parts", "model/step"),
        "lid.stl": ("lid_stl", "model/stl"),
        "preview.glb": ("preview_glb", "model/gltf-binary"),
        "parameters.json": ("parameters", "application/json"),
        "profiles.json": ("profiles", "application/json"),
        "validation.json": ("validation", "application/json"),
        "geometry-summary.json": ("geometry_summary", "application/json"),
    }
    entries = []
    for file in sorted(files, key=lambda item: item.name):
        if file.name in roles:
            role, mime_type = roles[file.name]
        elif file.suffix == ".step":
            role, mime_type = "step_printable_parts", "model/step"
        elif file.suffix == ".stl":
            role, mime_type = "stl_printable_parts", "model/stl"
        else:
            raise ValueError(f"unsupported CAD export file: {file.name}")
        content = file.read_bytes()
        entries.append(
            ManifestFile(
                role=role,
                file_name=file.name,
                mime_type=mime_type,
                byte_size=len(content),
                sha256=sha256(content).hexdigest(),
            )
        )
    manifest = ArtifactManifest(
        engine_version=ENGINE_VERSION,
        design_id=manifest_design_id or spec.design_id,
        spec_sha256=(
            manifest_spec_sha256
            or sha256(canonical_json_bytes(spec.model_dump(mode="json"))).hexdigest()
        ),
        files=tuple(entries),
    )
    manifest_file = output_directory / "manifest.json"
    _write_json(manifest_file, manifest.model_dump(mode="json"))
    return manifest_file, manifest


def geometry_summary(geometry: CadGeometry, *, triangle_count: int) -> GeometrySummary:
    parts: list[PartGeometrySummary] = []
    for part in geometry.parts:
        bounds = shape_aabb(part.shape)
        parts.append(
            PartGeometrySummary(
                part_id=part.part_id,
                role=part.role,
                bounds=bounds,
                volume_mm3=max(0.0, float(part.shape.Volume())),
                solid_count=len(part.shape.Solids()),
            )
        )
    return GeometrySummary(
        parts=tuple(parts),
        assembly_bounds=combined_aabb(item.bounds for item in parts),
        total_volume_mm3=sum(item.volume_mm3 for item in parts),
        preview_triangle_count=triangle_count,
    )


def shape_aabb(shape: Any) -> Aabb:
    bounds = shape.BoundingBox()
    return Aabb(
        min_x=float(bounds.xmin),
        min_y=float(bounds.ymin),
        min_z=float(bounds.zmin),
        max_x=float(bounds.xmax),
        max_y=float(bounds.ymax),
        max_z=float(bounds.zmax),
    )


def write_glb(parts: tuple[GeometryPart, ...], destination: Path) -> int:
    """Create a standards-compliant GLB directly from CadQuery tessellation."""

    binary = bytearray()
    buffer_views: list[dict[str, Any]] = []
    accessors: list[dict[str, Any]] = []
    materials: list[dict[str, Any]] = []
    meshes: list[dict[str, Any]] = []
    nodes: list[dict[str, Any]] = []
    triangle_total = 0

    for part in parts:
        vertices, triangles = part.shape.tessellate(0.1, 0.1)
        if not vertices or not triangles:
            continue
        positions = [
            (float(vertex.x) / 1000, float(vertex.y) / 1000, float(vertex.z) / 1000)
            for vertex in vertices
        ]
        indices = [int(vertex_index) for triangle in triangles for vertex_index in triangle]
        normals = _vertex_normals(positions, triangles)
        position_bytes = b"".join(struct.pack("<3f", *position) for position in positions)
        normal_bytes = b"".join(struct.pack("<3f", *normal) for normal in normals)
        index_bytes = b"".join(struct.pack("<I", item) for item in indices)
        position_view = _append_buffer_view(binary, buffer_views, position_bytes, target=34962)
        normal_view = _append_buffer_view(binary, buffer_views, normal_bytes, target=34962)
        index_view = _append_buffer_view(binary, buffer_views, index_bytes, target=34963)
        position_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": position_view,
                "componentType": 5126,
                "count": len(positions),
                "type": "VEC3",
                "min": [min(item[axis] for item in positions) for axis in range(3)],
                "max": [max(item[axis] for item in positions) for axis in range(3)],
            }
        )
        normal_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": normal_view,
                "componentType": 5126,
                "count": len(normals),
                "type": "VEC3",
            }
        )
        index_accessor = len(accessors)
        accessors.append(
            {
                "bufferView": index_view,
                "componentType": 5125,
                "count": len(indices),
                "type": "SCALAR",
            }
        )
        materials.append(
            {
                "name": part.role,
                "pbrMetallicRoughness": {
                    "baseColorFactor": list(part.color_rgba),
                    "metallicFactor": 0.0,
                    "roughnessFactor": 0.72,
                },
                "doubleSided": True,
            }
        )
        meshes.append(
            {
                "name": part.part_id,
                "primitives": [
                    {
                        "attributes": {
                            "POSITION": position_accessor,
                            "NORMAL": normal_accessor,
                        },
                        "indices": index_accessor,
                        "material": len(materials) - 1,
                    }
                ],
            }
        )
        nodes.append({"name": part.part_id, "mesh": len(meshes) - 1})
        triangle_total += len(triangles)

    document = {
        "asset": {"version": "2.0", "generator": "zhangwen-cad-engine"},
        "scene": 0,
        "scenes": [{"nodes": list(range(len(nodes)))}],
        "nodes": nodes,
        "meshes": meshes,
        "materials": materials,
        "buffers": [{"byteLength": len(binary)}],
        "bufferViews": buffer_views,
        "accessors": accessors,
    }
    json_chunk = canonical_json_bytes(document)
    json_chunk += b" " * ((4 - len(json_chunk) % 4) % 4)
    binary.extend(b"\x00" * ((4 - len(binary) % 4) % 4))
    total_length = 12 + 8 + len(json_chunk) + 8 + len(binary)
    glb = bytearray(struct.pack("<4sII", b"glTF", 2, total_length))
    glb.extend(struct.pack("<II", len(json_chunk), 0x4E4F534A))
    glb.extend(json_chunk)
    glb.extend(struct.pack("<II", len(binary), 0x004E4942))
    glb.extend(binary)
    destination.write_bytes(glb)
    return triangle_total


def _vertex_normals(
    positions: list[tuple[float, float, float]],
    triangles: list[tuple[int, int, int]],
) -> list[tuple[float, float, float]]:
    accumulated = [[0.0, 0.0, 0.0] for _ in positions]
    for first, second, third in triangles:
        origin = positions[int(first)]
        edge_a = tuple(positions[int(second)][axis] - origin[axis] for axis in range(3))
        edge_b = tuple(positions[int(third)][axis] - origin[axis] for axis in range(3))
        normal = (
            edge_a[1] * edge_b[2] - edge_a[2] * edge_b[1],
            edge_a[2] * edge_b[0] - edge_a[0] * edge_b[2],
            edge_a[0] * edge_b[1] - edge_a[1] * edge_b[0],
        )
        for vertex_index in (first, second, third):
            target = accumulated[int(vertex_index)]
            for axis in range(3):
                target[axis] += normal[axis]
    result: list[tuple[float, float, float]] = []
    for normal in accumulated:
        length = sum(value * value for value in normal) ** 0.5
        result.append(
            tuple(value / length for value in normal)
            if length > 1e-20
            else (0.0, 0.0, 1.0)
        )
    return result


def canonical_json_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _append_buffer_view(
    binary: bytearray,
    buffer_views: list[dict[str, Any]],
    content: bytes,
    *,
    target: int,
) -> int:
    binary.extend(b"\x00" * ((4 - len(binary) % 4) % 4))
    offset = len(binary)
    binary.extend(content)
    buffer_views.append(
        {
            "buffer": 0,
            "byteOffset": offset,
            "byteLength": len(content),
            "target": target,
        }
    )
    return len(buffer_views) - 1


def _write_json(destination: Path, value: Any) -> None:
    destination.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
