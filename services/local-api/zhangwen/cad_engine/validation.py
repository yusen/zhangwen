"""Pure and geometry-backed validation for deterministic CAD builds."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from itertools import combinations
from pathlib import Path
import struct

from zhangwen.cad_engine.layout import (
    MOUNT_JOIN_OVERLAP_MM,
    aabb_from_center_size,
    aabb_overlap,
    lid_fastener_centers,
)
from zhangwen.cad_engine.models import (
    Aabb,
    CadBuildSpec,
    CircularOpening,
    Face,
    HardwareMountingStrategy,
    LayoutResult,
    MountSurface,
    Point3,
    RectangularOpening,
    ResolvedMount,
    ResolvedMountKind,
    ResolvedMountingHole,
    Size3,
    ValidationCheck,
    ValidationReport,
    ValidationStatus,
)


def validate_design(spec: CadBuildSpec, layout: LayoutResult) -> ValidationReport:
    """Run all checks that do not require the optional CAD runtime."""

    source_check = ValidationCheck(
            check_id="source_deterministic",
            status=ValidationStatus.PASS,
            message="The build uses fixed engine functions and a declarative specification.",
        )
    if spec.template == "component_mount":
        checks = (
            source_check,
            _component_mount_contract_check(spec, layout),
            _component_mount_profile_hole_check(spec),
        )
        return ValidationReport(
            ok=all(check.status is not ValidationStatus.FAIL for check in checks),
            checks=checks,
        )
    if spec.template == "freeform_structure":
        geometry = spec.freeform_geometry
        recipe_check = ValidationCheck(
            check_id="freeform_recipe",
            status=(
                ValidationStatus.PASS
                if geometry is not None and geometry.primitives
                else ValidationStatus.FAIL
            ),
            message=(
                "The bounded declarative CSG recipe is present."
                if geometry is not None and geometry.primitives
                else "The declarative CSG recipe is missing."
            ),
            evidence=(
                f"primitive_count={len(geometry.primitives) if geometry is not None else 0}",
                "components=0",
            ),
        )
        checks = (source_check, recipe_check)
        return ValidationReport(
            ok=all(check.status is not ValidationStatus.FAIL for check in checks),
            checks=checks,
        )
    if spec.template == "unihiker_k10_photo_album":
        template_check = ValidationCheck(
            check_id="k10_photo_album_template",
            status=ValidationStatus.PASS,
            message="The fixed K10 photo album stage specification is selected.",
            evidence=(
                f"revision={spec.template_revision}",
                "base=52.08x83x5mm",
                "slope=65.5x83x5mm@60deg",
            ),
        )
        return ValidationReport(ok=True, checks=(source_check, template_check))
    checks = (
        source_check,
        _minimum_wall_check(spec),
        _layout_capacity_check(layout),
        _hardware_bounds_check(spec, layout),
        _mounting_completeness_check(spec, layout),
        _hardware_interference_check(spec, layout),
        _mount_clearance_check(spec, layout),
        _profile_opening_wall_check(spec, layout),
        _support_clearance_check(spec, layout),
        _opening_mount_clearance_check(spec, layout),
        _opening_bounds_check(spec, layout),
        _keepout_clearance_check(spec, layout),
    )
    return ValidationReport(
        ok=all(check.status is not ValidationStatus.FAIL for check in checks),
        checks=checks,
    )


def _component_mount_contract_check(
    spec: CadBuildSpec,
    layout: LayoutResult,
) -> ValidationCheck:
    parameters = spec.component_mount
    failures: list[str] = []
    if parameters is None:
        failures.append("parameters")
    if len(spec.profiles) != 1:
        failures.append("profile_count")
    if len(spec.hardware) != 1 or len(layout.hardware) != 1:
        failures.append("hardware_count")
    elif layout.hardware[0].surface is not MountSurface.EXTERNAL:
        failures.append("derived_placement")
    elif parameters is not None and abs(
        layout.hardware[0].bounds.min_z - parameters.base_thickness
    ) > 1e-6:
        failures.append("base_contact")
    return ValidationCheck(
        check_id="component_mount_contract",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Component mount inputs are incomplete or inconsistent: " + ", ".join(failures)
            if failures
            else "One confirmed component profile deterministically defines the mount structure."
        ),
        evidence=(
            f"profiles={len(spec.profiles)}",
            f"hardware={len(spec.hardware)}",
            f"layout_hardware={len(layout.hardware)}",
        ),
    )


def _component_mount_profile_hole_check(spec: CadBuildSpec) -> ValidationCheck:
    failures: list[str] = []
    evidence: list[str] = []
    if len(spec.profiles) == 1:
        profile = spec.profiles[0]
        half_length = profile.dimensions.length_x / 2
        half_width = profile.dimensions.width_y / 2
        for hole in profile.mounting.holes:
            radius = hole.diameter / 2
            inside = (
                abs(hole.center.x) + radius <= half_length + 1e-6
                and abs(hole.center.y) + radius <= half_width + 1e-6
            )
            evidence.append(f"{hole.hole_id}:inside_profile={str(inside).lower()}")
            if not inside:
                failures.append(hole.hole_id)
    return ValidationCheck(
        check_id="component_mount_profile_holes",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Profile mounting holes leave the component footprint: " + ", ".join(failures)
            if failures
            else "All declared profile mounting holes fit the component footprint."
        ),
        evidence=tuple(evidence),
    )


def merge_validation_reports(*reports: ValidationReport) -> ValidationReport:
    checks = tuple(check for report in reports for check in report.checks)
    return ValidationReport(
        ok=all(check.status is not ValidationStatus.FAIL for check in checks),
        checks=checks,
    )


def validate_brep_parts(parts: Iterable[tuple[str, object]]) -> ValidationReport:
    """Validate positive volume and OpenCascade validity on each exported part."""

    failures: list[str] = []
    evidence: list[str] = []
    for part_id, shape in parts:
        valid = bool(shape.isValid())
        volume = float(shape.Volume())
        solids = len(shape.Solids())
        evidence.append(
            f"{part_id}:valid={str(valid).lower()},volume_mm3={volume:.6f},solids={solids}"
        )
        if not valid or volume <= 1e-6 or solids < 1:
            failures.append(part_id)
    return ValidationReport(
        ok=not failures,
        checks=(
            ValidationCheck(
                check_id="brep_positive_volume",
                status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
                message=(
                    "Invalid or zero-volume BRep parts: " + ", ".join(failures)
                    if failures
                    else "Every BRep part is valid and has positive volume."
                ),
                evidence=tuple(evidence),
            ),
        ),
    )


def validate_step_round_trip(step_file: Path) -> ValidationReport:
    """Read a STEP export back through CadQuery and require valid solids."""

    try:
        import cadquery as cq

        imported = cq.importers.importStep(str(step_file)).val()
        valid = bool(imported.isValid())
        volume = float(imported.Volume())
        solids = len(imported.Solids())
        ok = valid and volume > 1e-6 and solids >= 1
        evidence = (
            f"valid={str(valid).lower()}",
            f"volume_mm3={volume:.6f}",
            f"solids={solids}",
        )
    except Exception as exc:  # OpenCascade import errors need to become validation evidence.
        ok = False
        evidence = (f"read_error={type(exc).__name__}:{exc}",)
    return ValidationReport(
        ok=ok,
        checks=(
            ValidationCheck(
                check_id="step_round_trip",
                status=ValidationStatus.PASS if ok else ValidationStatus.FAIL,
                message=(
                    "STEP re-import produced valid positive-volume solids."
                    if ok
                    else "STEP re-import did not produce valid positive-volume solids."
                ),
                evidence=evidence,
            ),
        ),
    )


def validate_stl_meshes(stl_files: Iterable[Path]) -> ValidationReport:
    """Require every STL triangle edge to have exactly two incident faces."""

    failures: list[str] = []
    evidence: list[str] = []
    for stl_file in stl_files:
        triangles = read_stl_triangles(stl_file)
        edge_counts: Counter[tuple[tuple[int, int, int], tuple[int, int, int]]] = Counter()
        for triangle in triangles:
            vertices = tuple(_quantized_vertex(vertex) for vertex in triangle)
            edge_counts.update(
                tuple(sorted((vertices[index], vertices[(index + 1) % 3])))
                for index in range(3)
            )
        boundary_edges = sum(1 for count in edge_counts.values() if count == 1)
        non_manifold_edges = sum(1 for count in edge_counts.values() if count > 2)
        ok = bool(triangles) and boundary_edges == 0 and non_manifold_edges == 0
        if not ok:
            failures.append(stl_file.name)
        evidence.append(
            f"{stl_file.name}:triangles={len(triangles)},boundary_edges={boundary_edges},"
            f"non_manifold_edges={non_manifold_edges}"
        )
    return ValidationReport(
        ok=not failures,
        checks=(
            ValidationCheck(
                check_id="stl_watertight_manifold",
                status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
                message=(
                    "STL topology failed for: " + ", ".join(failures)
                    if failures
                    else "Every STL is watertight and two-manifold."
                ),
                evidence=tuple(evidence),
            ),
        ),
    )


def read_stl_triangles(
    stl_file: Path,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]]:
    data = stl_file.read_bytes()
    if len(data) >= 84:
        triangle_count = struct.unpack_from("<I", data, 80)[0]
        if 84 + triangle_count * 50 == len(data):
            triangles = []
            offset = 84
            for _ in range(triangle_count):
                values = struct.unpack_from("<12fH", data, offset)
                triangles.append(
                    (
                        (values[3], values[4], values[5]),
                        (values[6], values[7], values[8]),
                        (values[9], values[10], values[11]),
                    )
                )
                offset += 50
            return triangles
    vertices: list[tuple[float, float, float]] = []
    for raw_line in data.decode("ascii", errors="strict").splitlines():
        fields = raw_line.strip().split()
        if len(fields) == 4 and fields[0] == "vertex":
            vertices.append((float(fields[1]), float(fields[2]), float(fields[3])))
    if len(vertices) % 3:
        raise ValueError(f"malformed STL triangle list: {stl_file.name}")
    return [tuple(vertices[index : index + 3]) for index in range(0, len(vertices), 3)]  # type: ignore[list-item]


def _minimum_wall_check(spec: CadBuildSpec) -> ValidationCheck:
    enclosure = spec.enclosure
    features = {
        "wall": enclosure.wall_thickness,
        "floor": enclosure.floor_thickness,
        "lid": enclosure.lid_thickness,
        "lid_lip": enclosure.lid_lip_thickness,
    }
    fasteners = enclosure.lid_fasteners
    if fasteners.enabled:
        features["lid_fastener_radial_wall"] = (
            fasteners.post_outer_diameter - fasteners.hole_diameter
        ) / 2
    for standoff in spec.standoffs:
        features[f"standoff_{standoff.standoff_id}_radial_wall"] = (
            standoff.outer_diameter - standoff.bore_diameter
        ) / 2
    minimum = min(features.values())
    failures = sorted(name for name, value in features.items() if value < enclosure.min_wall_thickness)
    return ValidationCheck(
        check_id="minimum_wall_thickness",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Features below the configured minimum: " + ", ".join(failures)
            if failures
            else "All modeled walls meet the configured minimum thickness."
        ),
        evidence=tuple(
            [f"required_mm={enclosure.min_wall_thickness:.6f}", f"minimum_mm={minimum:.6f}"]
            + [f"{name}={value:.6f}" for name, value in sorted(features.items())]
        ),
    )


def _layout_capacity_check(layout: LayoutResult) -> ValidationCheck:
    return ValidationCheck(
        check_id="layout_surface_capacity",
        status=(
            ValidationStatus.FAIL
            if layout.capacity_violations
            else ValidationStatus.PASS
        ),
        message=(
            "Automatic hardware layout exceeds an available mounting surface."
            if layout.capacity_violations
            else "Automatic hardware layout fits every selected mounting surface."
        ),
        evidence=layout.capacity_violations,
    )


def _hardware_bounds_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    failures: list[str] = []
    evidence: list[str] = []
    profiles = {profile.profile_id: profile for profile in spec.profiles}
    enclosure = spec.enclosure
    for item in layout.hardware:
        clearance = profiles[item.profile_id].mounting.clearance
        bounds = item.bounds
        if item.surface in (MountSurface.BASE_FLOOR, MountSurface.LID_INNER):
            ok = (
                bounds.min_x >= -enclosure.inner_length_x / 2 + clearance
                and bounds.max_x <= enclosure.inner_length_x / 2 - clearance
                and bounds.min_y >= -enclosure.inner_width_y / 2 + clearance
                and bounds.max_y <= enclosure.inner_width_y / 2 - clearance
                and bounds.min_z >= enclosure.floor_thickness - 1e-6
                and bounds.max_z <= enclosure.base_height_z + 1e-6
            )
        elif item.surface is MountSurface.LID_OUTER:
            ok = (
                bounds.min_x >= -enclosure.outer_length_x / 2
                and bounds.max_x <= enclosure.outer_length_x / 2
                and bounds.min_y >= -enclosure.outer_width_y / 2
                and bounds.max_y <= enclosure.outer_width_y / 2
                and bounds.min_z >= enclosure.overall_height_z - 1e-6
            )
        elif item.surface in (MountSurface.FRONT_INNER, MountSurface.BACK_INNER):
            ok = (
                bounds.min_x >= -enclosure.inner_length_x / 2 + clearance
                and bounds.max_x <= enclosure.inner_length_x / 2 - clearance
                and bounds.min_y >= -enclosure.inner_width_y / 2 - 1e-6
                and bounds.max_y <= enclosure.inner_width_y / 2 + 1e-6
                and bounds.min_z >= enclosure.floor_thickness + clearance
                and bounds.max_z <= enclosure.base_height_z - clearance
            )
        elif item.surface in (MountSurface.LEFT_INNER, MountSurface.RIGHT_INNER):
            ok = (
                bounds.min_x >= -enclosure.inner_length_x / 2 - 1e-6
                and bounds.max_x <= enclosure.inner_length_x / 2 + 1e-6
                and bounds.min_y >= -enclosure.inner_width_y / 2 + clearance
                and bounds.max_y <= enclosure.inner_width_y / 2 - clearance
                and bounds.min_z >= enclosure.floor_thickness + clearance
                and bounds.max_z <= enclosure.base_height_z - clearance
            )
        else:
            ok = not aabb_overlap(bounds, _enclosure_aabb(spec), clearance)
        if not ok:
            failures.append(item.instance_id)
        evidence.append(f"{item.instance_id}:surface={item.surface},inside={str(ok).lower()}")
    return ValidationCheck(
        check_id="hardware_bounds",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Hardware violates its mounting region: " + ", ".join(failures)
            if failures
            else "Hardware envelopes fit their declared mounting regions."
        ),
        evidence=tuple(evidence),
    )


def _mounting_completeness_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    profiles = {profile.profile_id: profile for profile in spec.profiles}
    mounts_by_hardware: dict[str, list[ResolvedMount]] = {}
    holes_by_hardware: dict[str, list[ResolvedMountingHole]] = {}
    for mount in layout.mounts:
        mounts_by_hardware.setdefault(mount.hardware_instance_id, []).append(mount)
    for hole in layout.mounting_holes:
        holes_by_hardware.setdefault(hole.hardware_instance_id, []).append(hole)

    failures: list[str] = []
    evidence: list[str] = []
    expected_edge_counts = Counter(
        {
            ResolvedMountKind.SUPPORT_TRAY: 1,
            ResolvedMountKind.SIDE_RETAINER: 2,
            ResolvedMountKind.END_STOP: 2,
        }
    )
    for item in layout.hardware:
        profile = profiles[item.profile_id]
        strategy = profile.mounting.strategy
        mounts = mounts_by_hardware.get(item.instance_id, [])
        holes = holes_by_hardware.get(item.instance_id, [])
        if strategy is HardwareMountingStrategy.EDGE_RETAINER:
            counts = Counter(mount.kind for mount in mounts)
            ok = (
                item.surface is MountSurface.BASE_FLOOR
                and counts == expected_edge_counts
                and not holes
            )
            detail = (
                f"support={counts[ResolvedMountKind.SUPPORT_TRAY]},"
                f"side={counts[ResolvedMountKind.SIDE_RETAINER]},"
                f"end={counts[ResolvedMountKind.END_STOP]}"
            )
        elif strategy is HardwareMountingStrategy.HOLE_FASTENED:
            expected_holes = {
                f"{item.instance_id}_{hole.hole_id}" for hole in profile.mounting.holes
            }
            actual_holes = {hole.hole_id for hole in holes}
            ok = bool(expected_holes) and actual_holes == expected_holes and not mounts
            detail = f"expected_holes={len(expected_holes)},actual_holes={len(actual_holes)}"
        else:
            ok = not mounts
            detail = f"mounts={len(mounts)},holes={len(holes)}"
        evidence.append(
            f"{item.instance_id}:strategy={strategy.value},ok={str(ok).lower()},{detail}"
        )
        if not ok:
            failures.append(item.instance_id)

    known_instances = {item.instance_id for item in layout.hardware}
    orphan_mounts = [
        mount.mount_id
        for mount in layout.mounts
        if mount.hardware_instance_id not in known_instances
    ]
    failures.extend(orphan_mounts)
    return ValidationCheck(
        check_id="mounting_completeness",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Hardware lacks its complete trusted mounting strategy output: "
            + ", ".join(failures)
            if failures
            else "Every hardware item has its complete trusted mounting strategy output."
        ),
        evidence=tuple([*evidence, *(f"orphan={item}" for item in orphan_mounts)]),
    )


def _mount_clearance_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    enclosure = spec.enclosure
    collisions: list[str] = []
    outside: list[str] = []
    for mount in layout.mounts:
        bounds = mount.bounds
        inside = (
            bounds.min_x >= -enclosure.inner_length_x / 2 - 1e-6
            and bounds.max_x <= enclosure.inner_length_x / 2 + 1e-6
            and bounds.min_y >= -enclosure.inner_width_y / 2 - 1e-6
            and bounds.max_y <= enclosure.inner_width_y / 2 + 1e-6
            and bounds.min_z >= enclosure.floor_thickness - MOUNT_JOIN_OVERLAP_MM - 1e-6
            and bounds.max_z <= enclosure.base_height_z + 1e-6
        )
        if not inside:
            outside.append(mount.mount_id)
        for hardware in layout.hardware:
            if hardware.instance_id == mount.hardware_instance_id:
                continue
            if aabb_overlap(bounds, hardware.bounds):
                collisions.append(f"{mount.mount_id}:{hardware.instance_id}")
    failed = bool(collisions or outside)
    return ValidationCheck(
        check_id="mount_clearance",
        status=ValidationStatus.FAIL if failed else ValidationStatus.PASS,
        message=(
            "A resolved mount collides with non-target hardware or leaves the cavity."
            if failed
            else "Resolved mounts remain inside the cavity and clear of non-target hardware."
        ),
        evidence=tuple(
            [*(f"collision={item}" for item in collisions), *(f"outside={item}" for item in outside)]
        ),
    )


def _profile_opening_wall_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    """Require cross-face openings to be supported by hardware near that wall."""

    profiles = {profile.profile_id: profile for profile in spec.profiles}
    hardware_by_id = {item.instance_id: item for item in layout.hardware}
    failures: list[str] = []
    evidence: list[str] = []
    inner = spec.enclosure
    cross_face_surfaces = {
        MountSurface.BASE_FLOOR,
        MountSurface.LID_INNER,
        MountSurface.LID_OUTER,
    }
    side_faces = {Face.LEFT, Face.RIGHT, Face.FRONT, Face.BACK}
    for instance in spec.hardware:
        item = hardware_by_id[instance.instance_id]
        profile = profiles[instance.profile_id]
        if item.surface not in cross_face_surfaces:
            continue
        for opening in profile.openings:
            if opening.preferred_face not in side_faces:
                continue
            face = opening.preferred_face
            if face is Face.FRONT:
                gap = item.bounds.min_y - (-inner.inner_width_y / 2)
            elif face is Face.BACK:
                gap = inner.inner_width_y / 2 - item.bounds.max_y
            elif face is Face.LEFT:
                gap = item.bounds.min_x - (-inner.inner_length_x / 2)
            else:
                gap = inner.inner_length_x / 2 - item.bounds.max_x
            allowed_gap = profile.mounting.clearance
            if profile.mounting.strategy is HardwareMountingStrategy.EDGE_RETAINER:
                allowed_gap += spec.enclosure.min_wall_thickness
            ok = gap <= allowed_gap + 1e-6
            opening_id = f"{instance.instance_id}_{opening.opening_id}"
            evidence.append(f"{opening_id}:face={face.value},gap_mm={gap:.6f}")
            if not ok:
                failures.append(opening_id)
    return ValidationCheck(
        check_id="profile_opening_wall_clearance",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Cross-face openings are too far from their requested enclosure wall: "
            + ", ".join(failures)
            if failures
            else "Cross-face openings are anchored to their requested enclosure walls."
        ),
        evidence=tuple(evidence),
    )


def _hardware_interference_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    collisions: list[str] = []
    for left, right in combinations(layout.hardware, 2):
        if aabb_overlap(left.bounds, right.bounds, spec.enclosure.hardware_gap):
            collisions.append(f"{left.instance_id}:{right.instance_id}")
    return ValidationCheck(
        check_id="hardware_interference",
        status=ValidationStatus.FAIL if collisions else ValidationStatus.PASS,
        message=(
            "Hardware AABB clearance violations were found."
            if collisions
            else "Hardware AABBs satisfy the requested separation."
        ),
        evidence=tuple(collisions),
    )


def _support_clearance_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    enclosure = spec.enclosure
    support_boxes: list[tuple[str, str | None, Aabb]] = []
    for standoff in spec.standoffs:
        center = Point3(
            x=standoff.center.x,
            y=standoff.center.y,
            z=enclosure.floor_thickness + standoff.height / 2,
        )
        support_boxes.append(
            (
                standoff.standoff_id,
                standoff.supports_instance_id,
                aabb_from_center_size(
                    center,
                    Size3(
                        length_x=standoff.outer_diameter,
                        width_y=standoff.outer_diameter,
                        height_z=standoff.height,
                    ),
                ),
            )
        )
    fasteners = enclosure.lid_fasteners
    post_height = enclosure.inner_height_z - fasteners.top_clearance
    for index, center in enumerate(lid_fastener_centers(spec), start=1):
        support_boxes.append(
            (
                f"lid_post_{index}",
                None,
                aabb_from_center_size(
                    Point3(
                        x=center.x,
                        y=center.y,
                        z=enclosure.floor_thickness + post_height / 2,
                    ),
                    Size3(
                        length_x=fasteners.post_outer_diameter,
                        width_y=fasteners.post_outer_diameter,
                        height_z=post_height,
                    ),
                ),
            )
        )
    collisions: list[str] = []
    for support_id, supported_instance_id, bounds in support_boxes:
        for hardware in layout.hardware:
            if hardware.surface not in (MountSurface.BASE_FLOOR, MountSurface.LID_INNER):
                continue
            if supported_instance_id == hardware.instance_id:
                continue
            if aabb_overlap(bounds, hardware.bounds, 0.05):
                collisions.append(f"{support_id}:{hardware.instance_id}")
    standoff_bounds_failures = [
        standoff.standoff_id
        for standoff in spec.standoffs
        if (
            abs(standoff.center.x) + standoff.outer_diameter / 2 > enclosure.inner_length_x / 2
            or abs(standoff.center.y) + standoff.outer_diameter / 2 > enclosure.inner_width_y / 2
            or standoff.height > enclosure.inner_height_z
        )
    ]
    evidence = tuple(
        [f"collision={item}" for item in collisions]
        + [f"outside_cavity={item}" for item in standoff_bounds_failures]
    )
    failed = bool(collisions or standoff_bounds_failures)
    return ValidationCheck(
        check_id="support_clearance",
        status=ValidationStatus.FAIL if failed else ValidationStatus.PASS,
        message=(
            "A post or standoff violates hardware or cavity clearance."
            if failed
            else "Posts and standoffs satisfy cavity and hardware clearance checks."
        ),
        evidence=evidence,
    )


def _opening_mount_clearance_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    generated = tuple(item.opening for item in layout.openings)
    structures = _opening_conflict_structures(spec, layout)
    conflicts: list[str] = []
    for opening in (*spec.openings, *generated):
        opening_rect = _opening_face_rect(opening)
        for structure_id, structure_kind, bounds in structures:
            if not _structure_reaches_face(spec, opening.face, structure_kind, bounds):
                continue
            if _rectangles_overlap(opening_rect, _bounds_face_rect(opening.face, bounds)):
                conflicts.append(f"{opening.opening_id}:{structure_id}")
    return ValidationCheck(
        check_id="opening_mount_clearance",
        status=ValidationStatus.FAIL if conflicts else ValidationStatus.PASS,
        message=(
            f"{len(conflicts)} opening footprint conflict(s) with a post, standoff, or mount."
            if conflicts
            else "Opening footprints clear posts, standoffs, and resolved mounts."
        ),
        evidence=tuple(conflicts[:64]),
    )


def _opening_conflict_structures(
    spec: CadBuildSpec,
    layout: LayoutResult,
) -> list[tuple[str, str, Aabb]]:
    enclosure = spec.enclosure
    structures: list[tuple[str, str, Aabb]] = []
    for standoff in spec.standoffs:
        center = Point3(
            x=standoff.center.x,
            y=standoff.center.y,
            z=enclosure.floor_thickness + standoff.height / 2,
        )
        structures.append(
            (
                standoff.standoff_id,
                "standoff",
                aabb_from_center_size(
                    center,
                    Size3(
                        length_x=standoff.outer_diameter,
                        width_y=standoff.outer_diameter,
                        height_z=standoff.height,
                    ),
                ),
            )
        )
    fasteners = enclosure.lid_fasteners
    post_height = enclosure.inner_height_z - fasteners.top_clearance
    for index, center in enumerate(lid_fastener_centers(spec), start=1):
        structures.append(
            (
                f"lid_post_{index}",
                "lid_post",
                aabb_from_center_size(
                    Point3(
                        x=center.x,
                        y=center.y,
                        z=enclosure.floor_thickness + post_height / 2,
                    ),
                    Size3(
                        length_x=fasteners.post_outer_diameter,
                        width_y=fasteners.post_outer_diameter,
                        height_z=post_height,
                    ),
                ),
            )
        )
    structures.extend((mount.mount_id, "mount", mount.bounds) for mount in layout.mounts)
    return structures


def _structure_reaches_face(
    spec: CadBuildSpec,
    face: Face,
    structure_kind: str,
    bounds: Aabb,
) -> bool:
    enclosure = spec.enclosure
    if face is Face.BOTTOM:
        return bounds.min_z <= enclosure.floor_thickness + 1e-6
    if face is Face.TOP:
        return structure_kind == "lid_post" or (
            bounds.max_z >= enclosure.base_height_z - enclosure.min_wall_thickness
        )
    band = enclosure.wall_thickness + enclosure.min_wall_thickness
    if face is Face.LEFT:
        return bounds.min_x <= -enclosure.inner_length_x / 2 + band
    if face is Face.RIGHT:
        return bounds.max_x >= enclosure.inner_length_x / 2 - band
    if face is Face.FRONT:
        return bounds.min_y <= -enclosure.inner_width_y / 2 + band
    return bounds.max_y >= enclosure.inner_width_y / 2 - band


def _opening_face_rect(
    opening: CircularOpening | RectangularOpening,
) -> tuple[float, float, float, float]:
    if isinstance(opening, CircularOpening):
        half_u = half_v = opening.diameter / 2
    else:
        half_u = opening.size_u / 2
        half_v = opening.size_v / 2
    return (
        opening.center_u - half_u,
        opening.center_u + half_u,
        opening.center_v - half_v,
        opening.center_v + half_v,
    )


def _bounds_face_rect(face: Face, bounds: Aabb) -> tuple[float, float, float, float]:
    if face in (Face.TOP, Face.BOTTOM):
        return bounds.min_x, bounds.max_x, bounds.min_y, bounds.max_y
    if face in (Face.LEFT, Face.RIGHT):
        return bounds.min_y, bounds.max_y, bounds.min_z, bounds.max_z
    return bounds.min_x, bounds.max_x, bounds.min_z, bounds.max_z


def _rectangles_overlap(
    left: tuple[float, float, float, float],
    right: tuple[float, float, float, float],
) -> bool:
    overlap_u = min(left[1], right[1]) - max(left[0], right[0])
    overlap_v = min(left[3], right[3]) - max(left[2], right[2])
    return overlap_u > 1e-6 and overlap_v > 1e-6


def _opening_bounds_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    failures: list[str] = []
    evidence: list[str] = []
    enclosure = spec.enclosure
    required = enclosure.min_wall_thickness
    generated = tuple(item.opening for item in layout.openings) + tuple(
        item.opening for item in layout.mounting_holes
    )
    for opening in (*spec.openings, *generated):
        if isinstance(opening, CircularOpening):
            half_u = half_v = opening.diameter / 2
        elif isinstance(opening, RectangularOpening):
            half_u = opening.size_u / 2
            half_v = opening.size_v / 2
        else:  # The discriminated input union makes this unreachable.
            raise TypeError(f"unsupported opening model: {type(opening).__name__}")
        if opening.face in (Face.TOP, Face.BOTTOM):
            limit_u = enclosure.outer_length_x / 2
            limit_v_low = -enclosure.outer_width_y / 2
            limit_v_high = enclosure.outer_width_y / 2
        elif opening.face in (Face.LEFT, Face.RIGHT):
            limit_u = enclosure.outer_width_y / 2
            limit_v_low = 0.0
            limit_v_high = enclosure.base_height_z
        else:
            limit_u = enclosure.outer_length_x / 2
            limit_v_low = 0.0
            limit_v_high = enclosure.base_height_z
        margin_u = limit_u - abs(opening.center_u) - half_u
        margin_v = min(
            opening.center_v - half_v - limit_v_low,
            limit_v_high - opening.center_v - half_v,
        )
        if opening.face in (Face.TOP, Face.BOTTOM):
            margin_v = enclosure.outer_width_y / 2 - abs(opening.center_v) - half_v
        ok = margin_u >= required and margin_v >= required
        if not ok:
            failures.append(opening.opening_id)
        evidence.append(
            f"{opening.opening_id}:edge_margin_u_mm={margin_u:.6f},"
            f"edge_margin_v_mm={margin_v:.6f}"
        )
    return ValidationCheck(
        check_id="opening_edge_clearance",
        status=ValidationStatus.FAIL if failures else ValidationStatus.PASS,
        message=(
            "Openings leave insufficient edge material: " + ", ".join(failures)
            if failures
            else "Openings preserve the configured minimum edge material."
        ),
        evidence=tuple(evidence),
    )


def _keepout_clearance_check(spec: CadBuildSpec, layout: LayoutResult) -> ValidationCheck:
    profiles = {profile.profile_id: profile for profile in spec.profiles}
    hardware_by_id = {item.instance_id: item for item in layout.hardware}
    violations: list[str] = []
    evidence: list[str] = []
    for keepout in layout.keepouts:
        owner = hardware_by_id[keepout.hardware_instance_id]
        clearance = profiles[owner.profile_id].mounting.clearance
        for other in layout.hardware:
            if other.instance_id == owner.instance_id:
                continue
            if aabb_overlap(keepout.bounds, other.bounds, clearance):
                violations.append(f"{keepout.keepout_id}:{other.instance_id}")
        inside = _keepout_inside_build_region(spec, owner.surface, keepout.bounds)
        if not inside:
            violations.append(f"{keepout.keepout_id}:outside_build_region")
        evidence.append(
            f"{keepout.keepout_id}:surface={owner.surface},inside={str(inside).lower()}"
        )
    return ValidationCheck(
        check_id="profile_keepout_clearance",
        status=ValidationStatus.FAIL if violations else ValidationStatus.PASS,
        message=(
            "Profile keepouts intersect hardware or leave the build region."
            if violations
            else "Profile keepouts remain clear of other hardware and the build boundary."
        ),
        evidence=tuple([*evidence, *violations]),
    )


def _keepout_inside_build_region(
    spec: CadBuildSpec,
    surface: MountSurface,
    bounds: Aabb,
) -> bool:
    if surface is MountSurface.EXTERNAL:
        return True
    enclosure = spec.enclosure
    if surface is MountSurface.LID_OUTER:
        return (
            bounds.min_x >= -enclosure.outer_length_x / 2 - 1e-6
            and bounds.max_x <= enclosure.outer_length_x / 2 + 1e-6
            and bounds.min_y >= -enclosure.outer_width_y / 2 - 1e-6
            and bounds.max_y <= enclosure.outer_width_y / 2 + 1e-6
            and bounds.min_z >= enclosure.base_height_z - 1e-6
        )
    return (
        bounds.min_x >= -enclosure.inner_length_x / 2 - 1e-6
        and bounds.max_x <= enclosure.inner_length_x / 2 + 1e-6
        and bounds.min_y >= -enclosure.inner_width_y / 2 - 1e-6
        and bounds.max_y <= enclosure.inner_width_y / 2 + 1e-6
        and bounds.min_z >= enclosure.floor_thickness - 1e-6
        and bounds.max_z <= enclosure.base_height_z + 1e-6
    )


def _enclosure_aabb(spec: CadBuildSpec) -> Aabb:
    enclosure = spec.enclosure
    return Aabb(
        min_x=-enclosure.outer_length_x / 2,
        min_y=-enclosure.outer_width_y / 2,
        min_z=0.0,
        max_x=enclosure.outer_length_x / 2,
        max_y=enclosure.outer_width_y / 2,
        max_z=enclosure.overall_height_z,
    )


def _quantized_vertex(vertex: tuple[float, float, float]) -> tuple[int, int, int]:
    tolerance = 1e-5
    return tuple(round(value / tolerance) for value in vertex)  # type: ignore[return-value]
