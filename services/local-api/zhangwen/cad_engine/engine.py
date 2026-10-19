"""End-to-end deterministic CAD engine orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from zhangwen.cad_engine.exports import (
    export_geometry,
    write_manifest,
    write_snapshots,
)
from zhangwen.cad_engine.geometry import build_geometry
from zhangwen.cad_engine.layout import resolve_layout
from zhangwen.cad_engine.models import (
    ArtifactManifest,
    CadBuildSpec,
    GeometrySummary,
    LayoutResult,
    ValidationReport,
)
from zhangwen.cad_engine.validation import (
    merge_validation_reports,
    validate_brep_parts,
    validate_design,
    validate_step_round_trip,
    validate_stl_meshes,
)


class CadDesignRejected(ValueError):
    def __init__(self, report: ValidationReport) -> None:
        super().__init__("CAD build specification failed deterministic validation")
        self.report = report


class CadGeometryRejected(RuntimeError):
    def __init__(self, report: ValidationReport) -> None:
        super().__init__("CAD outputs failed geometry validation")
        self.report = report


@dataclass(frozen=True)
class CadBuildArtifacts:
    output_directory: Path
    manifest_file: Path
    manifest: ArtifactManifest
    validation: ValidationReport
    geometry_summary: GeometrySummary
    layout: LayoutResult


def build_cad_artifacts(
    spec: CadBuildSpec,
    output_directory: Path,
    *,
    manifest_design_id: str | None = None,
    manifest_spec_sha256: str | None = None,
) -> CadBuildArtifacts:
    """Validate, build, verify, and write one immutable artifact set."""

    if not isinstance(spec, CadBuildSpec):
        raise TypeError("spec must be a validated CadBuildSpec")
    layout = resolve_layout(spec)
    design_report = validate_design(spec, layout)
    if not design_report.ok:
        raise CadDesignRejected(design_report)

    destination = Path(output_directory)
    if destination.exists() and any(destination.iterdir()):
        raise FileExistsError("CAD artifact directory must be empty")
    destination.mkdir(parents=True, exist_ok=True)

    geometry = build_geometry(spec, layout)
    brep_report = validate_brep_parts(
        (part.part_id, part.shape) for part in geometry.parts
    )
    if not brep_report.ok:
        raise CadGeometryRejected(merge_validation_reports(design_report, brep_report))

    geometry_exports = export_geometry(geometry, destination)
    step_report = validate_step_round_trip(destination / "assembly.step")
    stl_report = validate_stl_meshes(
        tuple(destination / f"{part.part_id}.stl" for part in geometry.printable_parts)
    )
    final_report = merge_validation_reports(
        design_report,
        brep_report,
        step_report,
        stl_report,
    )
    snapshot_files = write_snapshots(
        spec=spec,
        report=final_report,
        summary=geometry_exports.summary,
        output_directory=destination,
    )
    if not final_report.ok:
        raise CadGeometryRejected(final_report)

    manifest_file, manifest = write_manifest(
        spec=spec,
        files=(*geometry_exports.files, *snapshot_files),
        output_directory=destination,
        manifest_design_id=manifest_design_id,
        manifest_spec_sha256=manifest_spec_sha256,
    )
    return CadBuildArtifacts(
        output_directory=destination,
        manifest_file=manifest_file,
        manifest=manifest,
        validation=final_report,
        geometry_summary=geometry_exports.summary,
        layout=layout,
    )
