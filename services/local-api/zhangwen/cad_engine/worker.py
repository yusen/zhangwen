"""Fixed-input, fixed-destination CAD worker process.

The Sidecar materializes one immutable build specification and sends it over
stdin.  The worker never opens the project database or receives the data root;
its current working directory is the only output destination.
"""

from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from hashlib import sha256
import json
import math
from pathlib import Path
import re
import sys
from typing import Any, TextIO

from pydantic import ValidationError

from zhangwen.cad_agent.models import (
    SUPPORTED_TEMPLATE_REVISIONS,
    CadBuildSpec as AgentCadBuildSpec,
    CadTemplateKind,
)
from zhangwen.cad_agent.worker_protocol import (
    MAX_REQUEST_BYTES,
    WORKER_PROTOCOL,
    WORKER_VERSION,
    canonical_json_bytes,
)
from zhangwen.cad_agent.template_catalog import production_template_parameter_specs
from zhangwen.cad_engine.engine import (
    CadBuildArtifacts,
    CadDesignRejected,
    CadGeometryRejected,
    build_cad_artifacts,
)
from zhangwen.cad_engine.geometry import CadRuntimeUnavailable
from zhangwen.cad_engine.models import (
    BoxWithLidParameters,
    CadBuildSpec,
    ComponentMountParameters,
    ExternalPlacement,
    HardwareInstance,
    HardwareProfile,
    LidFastenerPattern,
    MountSurface,
    Point2,
    Point3,
    SurfacePlacement,
)
from zhangwen.cad_engine.profiles import unihiker_k10_profile
from zhangwen.cad_engine.validation import read_stl_triangles


SAFE_JOB_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,119}$")
SAFE_ENGINE_ID = re.compile(r"^[a-z][a-z0-9_-]{0,63}$")
K10_PROFILE_ALIASES = {
    "unihiker_k10": "unihiker_k10",
    "hw_seed_unihiker_k10": "unihiker_k10",
}


class WorkerFailure(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        exit_code: int = 65,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.exit_code = exit_code
        self.retryable = retryable


def main(
    argv: list[str] | None = None,
    *,
    input_stream: TextIO | None = None,
    output_stream: TextIO | None = None,
) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    job_id = args[0] if len(args) == 1 else ""
    emitter = _ProtocolEmitter(job_id, output_stream or sys.stdout)
    if len(args) != 1 or not SAFE_JOB_ID.fullmatch(job_id):
        failure = WorkerFailure(
            "CAD_WORKER_USAGE",
            "cad-worker requires exactly one valid job identifier",
            exit_code=64,
        )
        emitter.error(failure)
        return failure.exit_code

    emitter.emit("STARTED", {})
    try:
        emitter.progress("VALIDATING", 5)
        request = load_job_request(input_stream or sys.stdin, job_id)
        emitter.progress("RESOLVING_PROFILES", 20)
        engine_spec = adapt_build_spec(request)
        destination = _working_directory()
        emitter.progress("BUILDING", 35)
        # Third-party geometry libraries must not corrupt the NDJSON channel.
        with redirect_stdout(sys.stderr):
            artifacts = build_cad_artifacts(
                engine_spec,
                destination,
                manifest_design_id=request.jobId,
                manifest_spec_sha256=sha256(canonical_json_bytes(request)).hexdigest(),
            )
        emitter.progress("STORING_ARTIFACTS", 95)
        payload = build_result_payload(artifacts)
        emitter.emit("RESULT", payload)
        return 0
    except WorkerFailure as failure:
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except ValidationError as exc:
        failure = WorkerFailure(
            "CAD_BUILD_SPEC_INVALID",
            _validation_error_message(exc),
        )
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except CadDesignRejected as exc:
        failure = WorkerFailure(
            "CAD_DESIGN_REJECTED",
            _failed_check_message(exc.report),
        )
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except CadGeometryRejected as exc:
        failure = WorkerFailure(
            "CAD_GEOMETRY_REJECTED",
            _failed_check_message(exc.report),
        )
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except CadRuntimeUnavailable as exc:
        failure = WorkerFailure("CAD_RUNTIME_UNAVAILABLE", str(exc), exit_code=69)
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except FileExistsError as exc:
        failure = WorkerFailure(
            "CAD_STAGING_NOT_EMPTY",
            str(exc),
            exit_code=73,
            retryable=True,
        )
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except OSError as exc:
        failure = WorkerFailure(
            "CAD_WORKER_IO_ERROR",
            f"{type(exc).__name__}: {exc}",
            exit_code=74,
            retryable=True,
        )
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code
    except Exception as exc:  # The process boundary must always return one NDJSON error.
        failure = WorkerFailure(
            "CAD_WORKER_INTERNAL_ERROR",
            f"{type(exc).__name__}: {exc}",
            exit_code=70,
            retryable=True,
        )
        _log(job_id, failure.code, str(failure))
        emitter.error(failure)
        return failure.exit_code


def load_job_request(input_stream: TextIO, job_id: str) -> AgentCadBuildSpec:
    """Read exactly one bounded JSON build specification from stdin."""

    if not SAFE_JOB_ID.fullmatch(job_id):
        raise WorkerFailure("CAD_JOB_ID_INVALID", "CAD job identifier is invalid")
    try:
        raw_text = input_stream.read(MAX_REQUEST_BYTES + 1)
    except (OSError, UnicodeError) as exc:
        raise WorkerFailure(
            "CAD_REQUEST_READ_FAILED",
            "CAD build specification could not be read from stdin",
            exit_code=66,
            retryable=True,
        ) from exc
    if not isinstance(raw_text, str):
        raise WorkerFailure("CAD_REQUEST_JSON_INVALID", "CAD build specification must be UTF-8 text")
    if len(raw_text.encode("utf-8")) > MAX_REQUEST_BYTES:
        raise WorkerFailure(
            "CAD_REQUEST_TOO_LARGE",
            "CAD build specification exceeds the 256 KiB input limit",
        )
    if not raw_text.strip():
        raise WorkerFailure("CAD_REQUEST_MISSING", "CAD build specification is missing")
    try:
        raw_request = json.loads(raw_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise WorkerFailure(
            "CAD_REQUEST_JSON_INVALID",
            "CAD job request is not valid JSON",
        ) from exc
    if not isinstance(raw_request, dict):
        raise WorkerFailure("CAD_REQUEST_JSON_INVALID", "CAD job request must be an object")
    normalized = _normalize_agent_request(raw_request)
    request = AgentCadBuildSpec.model_validate(normalized)
    if request.jobId != job_id:
        raise WorkerFailure(
            "CAD_JOB_ID_MISMATCH",
            "CAD request job identifier does not match the selected row",
        )
    return request


def adapt_build_spec(request: AgentCadBuildSpec) -> CadBuildSpec:
    """Convert the server-materialized agent contract to the engine contract."""

    if request.templateKind not in {
        CadTemplateKind.BOX_WITH_LID,
        CadTemplateKind.COMPONENT_MOUNT,
        CadTemplateKind.FREEFORM_STRUCTURE,
        CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM,
    }:
        raise WorkerFailure(
            "CAD_TEMPLATE_UNSUPPORTED",
            f"unsupported deterministic template: {request.templateKind.value}",
        )
    if request.templateRevision != SUPPORTED_TEMPLATE_REVISIONS[request.templateKind]:
        raise WorkerFailure(
            "CAD_TEMPLATE_REVISION_UNSUPPORTED",
            f"unsupported template revision: {request.templateRevision}",
        )
    if request.templateKind is CadTemplateKind.FREEFORM_STRUCTURE:
        if request.geometry is None:
            raise WorkerFailure(
                "CAD_FREEFORM_GEOMETRY_MISSING",
                "freeform structure requires declarative geometry",
            )
        if request.parameters or request.components or request.profileSnapshots:
            raise WorkerFailure(
                "CAD_FREEFORM_INPUT_CONFLICT",
                "freeform structure cannot include template parameters or hardware profiles",
            )
        unknown_constraints = sorted(set(request.constraints) - {"process"})
        if unknown_constraints:
            raise WorkerFailure(
                "CAD_CONSTRAINT_UNSUPPORTED",
                "unsupported freeform constraint(s): " + ", ".join(unknown_constraints),
            )
        process = request.constraints.get("process")
        if process is not None and str(process).strip().upper() != "FDM":
            raise WorkerFailure(
                "CAD_PROCESS_UNSUPPORTED",
                "the freeform structure template supports FDM only",
            )
        return CadBuildSpec(
            design_id=_safe_engine_identifier(request.jobId, prefix="job"),
            template="freeform_structure",
            template_revision=request.templateRevision,
            freeform_geometry=request.geometry,
        )
    if request.templateKind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM:
        if (
            request.parameters
            or request.components
            or request.profileSnapshots
            or request.geometry is not None
        ):
            raise WorkerFailure(
                "CAD_K10_PHOTO_ALBUM_INPUT_CONFLICT",
                "K10 photo album template cannot include parameters, components, profiles, or geometry",
            )
        unknown_constraints = sorted(set(request.constraints) - {"process"})
        if unknown_constraints:
            raise WorkerFailure(
                "CAD_CONSTRAINT_UNSUPPORTED",
                "unsupported K10 photo album constraint(s): " + ", ".join(unknown_constraints),
            )
        process = request.constraints.get("process")
        if process is not None and str(process).strip().upper() != "FDM":
            raise WorkerFailure(
                "CAD_PROCESS_UNSUPPORTED",
                "the K10 photo album template supports FDM only",
            )
        return CadBuildSpec(
            design_id=_safe_engine_identifier(request.jobId, prefix="job"),
            template="unihiker_k10_photo_album",
            template_revision=request.templateRevision,
        )
    enclosure = (
        _adapt_enclosure(request)
        if request.templateKind is CadTemplateKind.BOX_WITH_LID
        else None
    )
    snapshot_by_id: dict[str, dict[str, Any]] = {}
    for snapshot_model in request.profileSnapshots:
        snapshot = snapshot_model.model_dump(mode="json")
        raw_identifier = _snapshot_identifier(snapshot)
        canonical_identifier = _canonical_profile_id(raw_identifier)
        if canonical_identifier in snapshot_by_id:
            raise WorkerFailure(
                "CAD_PROFILE_DUPLICATE",
                f"duplicate mechanical profile snapshot: {canonical_identifier}",
            )
        snapshot_by_id[canonical_identifier] = snapshot

    required_profile_ids: list[str] = []
    component_profile_ids: list[str] = []
    for component in request.components:
        declared_profile_id = _canonical_profile_id(component.profileId)
        resolved_profile_id = _canonical_profile_id(component.resolvedProfileId)
        if declared_profile_id != resolved_profile_id:
            raise WorkerFailure(
                "CAD_COMPONENT_PROFILE_CONFLICT",
                f"component {component.instanceId} does not match its resolved profile",
            )
        snapshot = snapshot_by_id.get(resolved_profile_id)
        if (
            snapshot is None
            or snapshot.get("revision") != component.resolvedProfileRevision
            or snapshot.get("content_sha256") != component.resolvedProfileSha256
        ):
            raise WorkerFailure(
                "CAD_PROFILE_SNAPSHOT_MISMATCH",
                f"resolved mechanical profile snapshot does not match: {component.instanceId}",
            )
        profile_id = resolved_profile_id
        component_profile_ids.append(profile_id)
        if profile_id not in required_profile_ids:
            required_profile_ids.append(profile_id)

    profiles: list[HardwareProfile] = []
    for profile_id in required_profile_ids:
        snapshot = snapshot_by_id.get(profile_id)
        if profile_id == "unihiker_k10":
            profiles.append(_adapt_k10_snapshot(snapshot))
        elif snapshot is None:
            raise WorkerFailure(
                "CAD_PROFILE_SNAPSHOT_MISSING",
                f"mechanical profile snapshot is missing: {profile_id}",
            )
        else:
            profiles.append(_adapt_envelope_snapshot(profile_id, snapshot))

    profiles_by_id = {profile.profile_id: profile for profile in profiles}
    if request.templateKind is CadTemplateKind.COMPONENT_MOUNT:
        if len(request.components) != 1 or len(profiles) != 1:
            raise WorkerFailure(
                "CAD_COMPONENT_MOUNT_PROFILE_COUNT",
                "component mount requires exactly one resolved mechanical profile",
            )
        component = request.components[0]
        profile_id = component_profile_ids[0]
        parameters = _adapt_component_mount_parameters(request)
        instance = _adapt_component_mount_instance(
            component,
            profile_id,
            profiles_by_id[profile_id],
            parameters,
        )
        return CadBuildSpec(
            design_id=_safe_engine_identifier(request.jobId, prefix="job"),
            template="component_mount",
            template_revision=request.templateRevision,
            component_mount=parameters,
            profiles=tuple(profiles),
            hardware=(instance,),
        )
    assert enclosure is not None
    instances = tuple(
        _adapt_component(component, profile_id, profiles_by_id[profile_id], enclosure)
        for component, profile_id in zip(
            request.components,
            component_profile_ids,
            strict=True,
        )
    )
    return CadBuildSpec(
        design_id=_safe_engine_identifier(request.jobId, prefix="job"),
        template="box_with_lid",
        template_revision=request.templateRevision,
        enclosure=enclosure,
        profiles=tuple(profiles),
        hardware=instances,
    )


def _adapt_component_mount_parameters(
    request: AgentCadBuildSpec,
) -> ComponentMountParameters:
    aliases = {
        "base_thickness": ("base_thickness", "baseThickness", "baseThicknessMm"),
        "edge_margin": ("edge_margin", "edgeMargin", "edgeMarginMm"),
        "component_clearance": (
            "component_clearance",
            "componentClearance",
            "componentClearanceMm",
        ),
        "retainer_height": ("retainer_height", "retainerHeight", "retainerHeightMm"),
        "fastener_hole_diameter": (
            "fastener_hole_diameter",
            "fastenerHoleDiameter",
            "fastenerHoleDiameterMm",
        ),
        "corner_radius": ("corner_radius", "cornerRadius", "cornerRadiusMm"),
    }
    recognized = {key for names in aliases.values() for key in names}
    unknown_parameters = sorted(set(request.parameters) - recognized)
    if unknown_parameters:
        raise WorkerFailure(
            "CAD_PARAMETER_UNSUPPORTED",
            "unsupported component mount parameter(s): " + ", ".join(unknown_parameters),
        )
    unknown_constraints = sorted(set(request.constraints) - {"process"})
    if unknown_constraints:
        raise WorkerFailure(
            "CAD_CONSTRAINT_UNSUPPORTED",
            "unsupported component mount constraint(s): " + ", ".join(unknown_constraints),
        )
    process = request.constraints.get("process")
    if process is not None and str(process).strip().upper() != "FDM":
        raise WorkerFailure(
            "CAD_PROCESS_UNSUPPORTED",
            "the component mount template supports FDM only",
        )
    values: dict[str, float] = {}
    for definition in production_template_parameter_specs(CadTemplateKind.COMPONENT_MOUNT):
        selected = _first_number(request.parameters, aliases[definition.name])
        if selected is not None:
            if not definition.accepts(selected):
                raise WorkerFailure(
                    "CAD_PARAMETER_OUT_OF_RANGE",
                    "component mount parameter is outside the supported range: "
                    + definition.name,
                )
            values[definition.name] = selected
    return ComponentMountParameters(**values)


def _adapt_component_mount_instance(
    component: Any,
    profile_id: str,
    profile: HardwareProfile,
    parameters: ComponentMountParameters,
) -> HardwareInstance:
    try:
        rotation = int(component.rotationDeg) % 360
    except (TypeError, ValueError) as exc:
        raise WorkerFailure(
            "CAD_COMPONENT_ROTATION_INVALID",
            f"component rotation is invalid: {component.instanceId}",
        ) from exc
    if not math.isclose(float(component.rotationDeg) % 360, rotation, abs_tol=1e-6) or rotation not in {
        0,
        90,
        180,
        270,
    }:
        raise WorkerFailure(
            "CAD_COMPONENT_ROTATION_UNSUPPORTED",
            f"component rotation must be 0, 90, 180, or 270 degrees: {component.instanceId}",
        )
    if component.mountSurface not in {None, MountSurface.EXTERNAL}:
        raise WorkerFailure(
            "CAD_COMPONENT_SURFACE_UNSUPPORTED",
            "component mount derives placement from the selected profile",
        )
    if component.offsetMm is not None:
        raise WorkerFailure(
            "CAD_COMPONENT_OFFSET_UNSUPPORTED",
            "component mount centers the selected profile deterministically",
        )
    return HardwareInstance(
        instance_id=_safe_engine_identifier(component.instanceId, prefix="component"),
        profile_id=profile_id,
        placement=ExternalPlacement(
            surface="external",
            center=Point3(
                x=0.0,
                y=0.0,
                z=(
                    parameters.base_thickness
                    + profile.dimensions.height_z / 2
                ),
            ),
        ),
        rotation_z_deg=rotation,
        include_reference_geometry=True,
    )


def build_result_payload(artifacts: CadBuildArtifacts) -> dict[str, Any]:
    """Create the worker manifest consumed by the parent-side artifact store."""

    output = artifacts.output_directory
    summary_parts = {part.part_id: part for part in artifacts.geometry_summary.parts}
    assembly_bounds = artifacts.geometry_summary.assembly_bounds.model_dump(mode="json")
    role_by_name = {
        "assembly.step": "STEP_ASSEMBLY",
        "preview.glb": "GLB_PREVIEW",
        "parameters.json": "PARAMETERS",
        "profiles.json": "PROFILE_SNAPSHOTS",
        "validation.json": "VALIDATION_REPORT",
        "geometry-summary.json": "GEOMETRY_SUMMARY",
        "manifest.json": "MANIFEST",
    }
    mime_by_name = {
        "assembly.step": "model/step",
        "preview.glb": "model/gltf-binary",
        "parameters.json": "application/json",
        "profiles.json": "application/json",
        "validation.json": "application/json",
        "geometry-summary.json": "application/json",
        "manifest.json": "application/json",
    }
    for path in output.iterdir():
        if path.name == "assembly.step":
            continue
        if path.suffix == ".step":
            role_by_name[path.name] = "STEP_PRINTABLE_PARTS"
            mime_by_name[path.name] = "model/step"
        elif path.suffix == ".stl":
            role_by_name[path.name] = "STL_PRINTABLE_PARTS"
            mime_by_name[path.name] = "model/stl"
    files: list[dict[str, Any]] = []
    for file_name in sorted(role_by_name):
        file = output / file_name
        content = file.read_bytes()
        triangle_count: int | None = None
        bounds: dict[str, Any] | None = None
        if file.suffix == ".stl":
            triangle_count = len(read_stl_triangles(file))
            part = summary_parts.get(file.stem)
            if part is None:
                raise WorkerFailure(
                    "CAD_OUTPUT_PART_UNKNOWN",
                    f"printable output has no geometry summary: {file_name}",
                )
            bounds = part.bounds.model_dump(mode="json")
        elif file.suffix == ".step" and file_name != "assembly.step":
            part = summary_parts.get(file.stem)
            if part is None:
                raise WorkerFailure(
                    "CAD_OUTPUT_PART_UNKNOWN",
                    f"printable output has no geometry summary: {file_name}",
                )
            bounds = part.bounds.model_dump(mode="json")
        elif file_name == "preview.glb":
            triangle_count = artifacts.geometry_summary.preview_triangle_count
            bounds = assembly_bounds
        elif file_name == "assembly.step":
            bounds = assembly_bounds
        files.append(
            {
                "relativePath": file_name,
                "fileName": file_name,
                "role": role_by_name[file_name],
                "mimeType": mime_by_name[file_name],
                "byteSize": len(content),
                "sha256": sha256(content).hexdigest(),
                "triangleCount": triangle_count,
                "bounds": bounds,
            }
        )
    return {
        "manifest": {
            "schemaVersion": "1.0",
            "engineId": artifacts.manifest.engine_id,
            "engineVersion": artifacts.manifest.engine_version,
            "designId": artifacts.manifest.design_id,
            "specSha256": artifacts.manifest.spec_sha256,
            "files": files,
        },
        "validation": artifacts.validation.model_dump(mode="json"),
        "geometrySummary": artifacts.geometry_summary.model_dump(mode="json"),
    }


def _adapt_enclosure(request: AgentCadBuildSpec) -> BoxWithLidParameters:
    parameters = request.parameters
    constraints = request.constraints
    aliases = {
        "inner_length_x": ("inner_length_x", "innerLengthX", "length_x", "width"),
        "inner_width_y": ("inner_width_y", "innerWidthY", "width_y", "depth"),
        "inner_height_z": ("inner_height_z", "innerHeightZ", "height_z", "height"),
        "wall_thickness": ("wall_thickness", "wallThickness", "wallThicknessMm"),
        "floor_thickness": ("floor_thickness", "floorThickness", "floorThicknessMm"),
        "lid_thickness": ("lid_thickness", "lidThickness", "lidThicknessMm"),
        "lid_lip_height": ("lid_lip_height", "lidLipHeight", "lidLipHeightMm"),
        "lid_lip_thickness": (
            "lid_lip_thickness",
            "lidLipThickness",
            "lidLipThicknessMm",
        ),
        "lid_clearance": ("lid_clearance", "lidClearance", "lidClearanceMm"),
        "corner_radius": ("corner_radius", "cornerRadius", "cornerRadiusMm"),
        "hardware_gap": ("hardware_gap", "hardwareGap", "hardwareGapMm"),
        "edge_clearance": ("edge_clearance", "edgeClearance", "edgeClearanceMm"),
    }
    recognized_parameter_keys = {key for names in aliases.values() for key in names}
    recognized_parameter_keys.update(
        {
            "screw_posts",
            "screwPosts",
            "screw_boss_diameter",
            "screwBossDiameterMm",
            "screw_hole_diameter",
            "screwHoleDiameterMm",
            "screw_post_edge_inset",
            "screwPostEdgeInsetMm",
        }
    )
    unknown_parameters = sorted(set(parameters) - recognized_parameter_keys)
    if unknown_parameters:
        raise WorkerFailure(
            "CAD_PARAMETER_UNSUPPORTED",
            "unsupported box parameter(s): " + ", ".join(unknown_parameters),
        )
    fastener_aliases = {
        "screw_posts": ("screw_posts", "screwPosts"),
        "screw_boss_diameter": ("screw_boss_diameter", "screwBossDiameterMm"),
        "screw_hole_diameter": ("screw_hole_diameter", "screwHoleDiameterMm"),
        "screw_post_edge_inset": ("screw_post_edge_inset", "screwPostEdgeInsetMm"),
    }
    for definition in production_template_parameter_specs(CadTemplateKind.BOX_WITH_LID):
        selected = _first_number(
            parameters,
            aliases.get(definition.name, fastener_aliases.get(definition.name, (definition.name,))),
        )
        if selected is not None and not definition.accepts(selected):
            raise WorkerFailure(
                "CAD_PARAMETER_OUT_OF_RANGE",
                f"box parameter is outside the supported range: {definition.name}",
            )
    recognized_constraint_keys = {
        "process",
        "minWallThicknessMm",
        "min_wall_thickness",
        "hardwareGapMm",
        "edgeClearanceMm",
    }
    unknown_constraints = sorted(set(constraints) - recognized_constraint_keys)
    if unknown_constraints:
        raise WorkerFailure(
            "CAD_CONSTRAINT_UNSUPPORTED",
            "unsupported box constraint(s): " + ", ".join(unknown_constraints),
        )
    process = constraints.get("process")
    if process is not None and str(process).strip().upper() != "FDM":
        raise WorkerFailure(
            "CAD_PROCESS_UNSUPPORTED",
            "the current deterministic enclosure profile supports FDM only",
        )

    defaults = BoxWithLidParameters()
    values: dict[str, float] = {}
    for field_name, names in aliases.items():
        selected = _first_number(parameters, names)
        if selected is None:
            selected = _first_number(constraints, names)
        if selected is not None:
            values[field_name] = selected
    minimum_wall = _first_number(
        constraints,
        ("minWallThicknessMm", "min_wall_thickness"),
    )
    if minimum_wall is not None:
        values["min_wall_thickness"] = minimum_wall

    screw_posts = _first_number(parameters, ("screw_posts", "screwPosts"))
    if screw_posts is None:
        screw_posts = 4
    if screw_posts not in (0, 4):
        raise WorkerFailure(
            "CAD_FASTENER_PATTERN_UNSUPPORTED",
            "the current box template supports zero or four lid screw posts",
        )
    fastener_defaults = defaults.lid_fasteners
    post_outer_diameter = _first_number(
        parameters,
        ("screw_boss_diameter", "screwBossDiameterMm"),
    )
    hole_diameter = _first_number(
        parameters,
        ("screw_hole_diameter", "screwHoleDiameterMm"),
    )
    edge_inset = _first_number(
        parameters,
        ("screw_post_edge_inset", "screwPostEdgeInsetMm"),
    )
    fasteners = LidFastenerPattern(
        enabled=bool(screw_posts),
        post_outer_diameter=(
            fastener_defaults.post_outer_diameter
            if post_outer_diameter is None
            else post_outer_diameter
        ),
        hole_diameter=(
            fastener_defaults.hole_diameter if hole_diameter is None else hole_diameter
        ),
        edge_inset=fastener_defaults.edge_inset if edge_inset is None else edge_inset,
        top_clearance=fastener_defaults.top_clearance,
    )
    return BoxWithLidParameters(
        **values,
        lid_fasteners=fasteners,
    )


def _adapt_k10_snapshot(snapshot: dict[str, Any] | None) -> HardwareProfile:
    trusted = unihiker_k10_profile()
    if snapshot is None:
        return trusted
    profile = _hardware_profile_from_snapshot(snapshot)
    if (
        profile.profile_id != trusted.profile_id
        or profile.model_kind != trusted.model_kind
        or profile.source != trusted.source
    ):
        raise WorkerFailure(
            "CAD_K10_PROFILE_MISMATCH",
            "K10 profile snapshot does not match the trusted model identity",
        )
    return profile


def _adapt_envelope_snapshot(
    profile_id: str,
    snapshot: dict[str, Any],
) -> HardwareProfile:
    profile = _hardware_profile_from_snapshot(snapshot)
    if profile.profile_id != profile_id:
        raise WorkerFailure(
            "CAD_PROFILE_ID_MISMATCH",
            f"mechanical profile identity does not match: {profile_id}",
        )
    return profile


def _hardware_profile_from_snapshot(snapshot: dict[str, Any]) -> HardwareProfile:
    payload = deepcopy(snapshot)
    for key in (
        "schema_version",
        "schemaVersion",
        "evidence_level",
        "evidenceLevel",
        "representation",
        "content_sha256",
        "contentSha256",
    ):
        payload.pop(key, None)
    try:
        return HardwareProfile.model_validate(payload)
    except ValidationError as exc:
        raise WorkerFailure(
            "CAD_PROFILE_INVALID",
            _validation_error_message(exc),
        ) from exc


def _adapt_component(
    component: Any,
    profile_id: str,
    profile: HardwareProfile,
    enclosure: BoxWithLidParameters,
) -> HardwareInstance:
    try:
        rotation = int(component.rotationDeg) % 360
    except (TypeError, ValueError) as exc:
        raise WorkerFailure(
            "CAD_COMPONENT_ROTATION_INVALID",
            f"component rotation is invalid: {component.instanceId}",
        ) from exc
    if not math.isclose(float(component.rotationDeg) % 360, rotation, abs_tol=1e-6) or rotation not in {
        0,
        90,
        180,
        270,
    }:
        raise WorkerFailure(
            "CAD_COMPONENT_ROTATION_UNSUPPORTED",
            f"component rotation must be 0, 90, 180, or 270 degrees: {component.instanceId}",
        )
    raw_surface = component.mountSurface or profile.mounting.preferred_surface.value
    try:
        surface = MountSurface(raw_surface)
    except ValueError as exc:
        raise WorkerFailure(
            "CAD_COMPONENT_SURFACE_UNSUPPORTED",
            f"unsupported mount surface for component {component.instanceId}: {raw_surface}",
        ) from exc
    offset = component.offsetMm
    offset_values = _offset_coordinates(offset)
    if surface is MountSurface.EXTERNAL:
        if offset_values is None:
            length = (
                profile.dimensions.width_y
                if rotation in (90, 270)
                else profile.dimensions.length_x
            )
            center = Point3(
                x=enclosure.outer_length_x / 2
                + length / 2
                + max(enclosure.hardware_gap, profile.mounting.clearance),
                y=0.0,
                z=profile.dimensions.height_z / 2,
            )
        else:
            center = Point3(
                x=offset_values[0],
                y=offset_values[1],
                z=offset_values[2],
            )
        placement: ExternalPlacement | SurfacePlacement = ExternalPlacement(
            surface="external",
            center=center,
        )
    else:
        if offset_values is not None and not math.isclose(
            offset_values[2],
            0.0,
            abs_tol=1e-6,
        ):
            raise WorkerFailure(
                "CAD_COMPONENT_Z_OFFSET_UNSUPPORTED",
                f"mounted component Z is derived from its surface: {component.instanceId}",
            )
        placement = SurfacePlacement(
            surface=surface.value,
            center=(
                Point2(x=offset_values[0], y=offset_values[1])
                if offset_values is not None
                else None
            ),
        )
    return HardwareInstance(
        instance_id=_safe_engine_identifier(component.instanceId, prefix="component"),
        profile_id=profile_id,
        placement=placement,
        rotation_z_deg=rotation,
        include_reference_geometry=True,
    )


def _working_directory() -> Path:
    destination = Path.cwd().resolve(strict=True)
    if not destination.is_dir():
        raise WorkerFailure(
            "CAD_STAGING_INVALID",
            "CAD worker current directory is not a directory",
            exit_code=73,
        )
    return destination


def _normalize_agent_request(raw_request: dict[str, Any]) -> dict[str, Any]:
    normalized = deepcopy(raw_request)
    components = normalized.get("components")
    if not isinstance(components, list):
        return normalized
    for component in components:
        if not isinstance(component, dict):
            continue
        offset = component.get("offsetMm")
        if isinstance(offset, (list, tuple)) and len(offset) == 3:
            component["offsetMm"] = {"x": offset[0], "y": offset[1], "z": offset[2]}
    return normalized


def _offset_coordinates(offset: Any) -> tuple[float, float, float] | None:
    if offset is None:
        return None
    if all(hasattr(offset, axis) for axis in ("x", "y", "z")):
        return float(offset.x), float(offset.y), float(offset.z)
    if isinstance(offset, (list, tuple)) and len(offset) == 3:
        return float(offset[0]), float(offset[1]), float(offset[2])
    raise WorkerFailure("CAD_COMPONENT_OFFSET_INVALID", "component offset is invalid")


def _snapshot_identifier(snapshot: dict[str, Any]) -> str:
    for key in ("profile_id", "profileId", "hardware_id", "hardwareId", "id"):
        value = snapshot.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise WorkerFailure("CAD_PROFILE_ID_MISSING", "mechanical profile snapshot has no identifier")


def _canonical_profile_id(raw_identifier: str) -> str:
    known = K10_PROFILE_ALIASES.get(raw_identifier)
    if known:
        return known
    if not SAFE_ENGINE_ID.fullmatch(raw_identifier):
        raise WorkerFailure(
            "CAD_PROFILE_ID_INVALID",
            f"mechanical profile identifier is invalid: {raw_identifier}",
        )
    return raw_identifier


def _safe_engine_identifier(value: str, *, prefix: str) -> str:
    normalized = re.sub(r"[^a-z0-9_-]+", "_", value.lower()).strip("_-")
    if not normalized or not normalized[0].isalpha():
        normalized = f"{prefix}_{normalized}" if normalized else prefix
    if len(normalized) > 63:
        digest = sha256(value.encode("utf-8")).hexdigest()[:10]
        normalized = f"{normalized[:52]}_{digest}"
    if not SAFE_ENGINE_ID.fullmatch(normalized):
        raise WorkerFailure("CAD_IDENTIFIER_INVALID", "CAD identifier cannot be normalized safely")
    return normalized


def _first_number(values: dict[str, Any], names: tuple[str, ...]) -> float | None:
    for name in names:
        if name not in values:
            continue
        value = values[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise WorkerFailure("CAD_NUMBER_INVALID", f"CAD numeric field is invalid: {name}")
        number = float(value)
        if not math.isfinite(number):
            raise WorkerFailure("CAD_NUMBER_INVALID", f"CAD numeric field is not finite: {name}")
        return number
    return None


class _ProtocolEmitter:
    def __init__(self, job_id: str, stream: TextIO) -> None:
        self._job_id = job_id
        self._stream = stream
        self._sequence = 0

    def emit(self, event: str, payload: dict[str, Any]) -> None:
        self._sequence += 1
        message = {
            "protocol": WORKER_PROTOCOL,
            "version": WORKER_VERSION,
            "jobId": self._job_id,
            "sequence": self._sequence,
            "event": event,
            "payload": payload,
        }
        self._stream.write(
            json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n"
        )
        self._stream.flush()

    def progress(self, phase: str, progress: int) -> None:
        self.emit("PROGRESS", {"phase": phase, "progress": progress})

    def error(self, failure: WorkerFailure) -> None:
        self.emit(
            "ERROR",
            {
                "code": failure.code,
                "message": str(failure),
                "retryable": failure.retryable,
            },
        )


def _log(job_id: str, code: str, message: str) -> None:
    sys.stderr.write(f"cad-worker job={job_id or '-'} code={code} message={message}\n")
    sys.stderr.flush()


def _validation_error_message(exc: ValidationError) -> str:
    fields = sorted(
        ".".join(str(item) for item in error["loc"])
        for error in exc.errors(include_url=False, include_input=False)
    )
    return "CAD build specification validation failed: " + ", ".join(fields[:12])


def _failed_check_message(report: Any) -> str:
    failed = [check.check_id for check in report.checks if check.status == "fail"]
    return "CAD validation failed: " + ", ".join(failed)


if __name__ == "__main__":
    raise SystemExit(main())
