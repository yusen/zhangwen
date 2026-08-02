"""Deterministic placement, surface frames, and profile feature projection."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass

from zhangwen.cad_engine.models import (
    Aabb,
    CadBuildSpec,
    CircularOpening,
    ExternalPlacement,
    Face,
    HardwareInstance,
    HardwareMountingStrategy,
    HardwareProfile,
    LayoutResult,
    MountSurface,
    Point2,
    Point3,
    ProfileCircularOpening,
    ProfileRectangularOpening,
    OpeningSpec,
    RectangularOpening,
    ResolvedHardware,
    ResolvedKeepout,
    ResolvedMountingHole,
    ResolvedMount,
    ResolvedMountKind,
    ResolvedOpening,
    Size3,
    SurfacePlacement,
)

MOUNT_JOIN_OVERLAP_MM = 0.05


@dataclass(frozen=True)
class _Frame:
    basis_x: tuple[float, float, float]
    basis_y: tuple[float, float, float]
    normal: tuple[float, float, float]


@dataclass(frozen=True)
class _PackResult:
    centers: dict[str, Point2]
    required_length: float
    required_width: float
    usable_length: float
    usable_width: float


def resolve_layout(spec: CadBuildSpec) -> LayoutResult:
    """Resolve hardware and project trusted profile features into the enclosure."""

    if spec.template in {"freeform_structure", "unihiker_k10_photo_album"}:
        return LayoutResult(hardware=())

    profiles = {profile.profile_id: profile for profile in spec.profiles}
    automatic: dict[MountSurface, list[tuple[HardwareInstance, HardwareProfile]]] = defaultdict(list)
    centers: dict[str, Point2] = {}
    capacity_violations: list[str] = []

    for instance in spec.hardware:
        placement = instance.placement
        profile = profiles[instance.profile_id]
        if isinstance(placement, SurfacePlacement):
            surface = MountSurface(placement.surface)
            if placement.center is None:
                automatic[surface].append((instance, profile))
            else:
                centers[instance.instance_id] = placement.center

    for surface, items in automatic.items():
        length, width, vertical_origin = _pack_dimensions(spec, surface)
        packed = _pack_in_rows(
            items,
            inner_length=length,
            inner_width=width,
            gap=spec.enclosure.hardware_gap,
            edge_clearance=_effective_edge_clearance(spec, items),
            surface=surface,
        )
        packed_centers = packed.centers
        if vertical_origin:
            packed_centers = {
                key: Point2(x=value.x, y=value.y + vertical_origin)
                for key, value in packed_centers.items()
            }
        if (
            packed.required_length > packed.usable_length + 1e-6
            or packed.required_width > packed.usable_width + 1e-6
        ):
            capacity_violations.append(
                f"{surface.value}:required={packed.required_length:.6f}x"
                f"{packed.required_width:.6f},usable={packed.usable_length:.6f}x"
                f"{packed.usable_width:.6f}"
            )
        for instance, profile in items:
            packed_centers[instance.instance_id] = _anchor_cross_face_opening(
                packed_centers[instance.instance_id],
                instance,
                profile,
                spec,
            )
        centers.update(packed_centers)

    resolved: list[ResolvedHardware] = []
    for instance in spec.hardware:
        profile = profiles[instance.profile_id]
        placement = instance.placement
        if isinstance(placement, ExternalPlacement):
            surface = MountSurface.EXTERNAL
            center = placement.center
        else:
            surface = MountSurface(placement.surface)
            center_xy = centers[instance.instance_id]
            center = _surface_center(
                surface,
                center_xy,
                profile,
                spec,
                instance_id=instance.instance_id,
            )
        frame = _frame_for(surface, instance.rotation_z_deg)
        size = rotated_size(profile.dimensions, instance.rotation_z_deg)
        resolved.append(
            ResolvedHardware(
                instance_id=instance.instance_id,
                profile_id=instance.profile_id,
                model_kind=profile.model_kind,
                surface=surface,
                center=center,
                rotated_size=size,
                rotation_z_deg=instance.rotation_z_deg,
                bounds=_transformed_bounds(center, profile.dimensions, frame),
                include_reference_geometry=instance.include_reference_geometry,
                basis_x=Point3(x=frame.basis_x[0], y=frame.basis_x[1], z=frame.basis_x[2]),
                basis_y=Point3(x=frame.basis_y[0], y=frame.basis_y[1], z=frame.basis_y[2]),
                normal=Point3(x=frame.normal[0], y=frame.normal[1], z=frame.normal[2]),
            )
        )

    by_instance = {item.instance_id: item for item in resolved}
    projected_openings: list[ResolvedOpening] = []
    projected_holes: list[ResolvedMountingHole] = []
    projected_keepouts: list[ResolvedKeepout] = []
    for instance in spec.hardware:
        item = by_instance[instance.instance_id]
        profile = profiles[instance.profile_id]
        if item.surface is not MountSurface.EXTERNAL:
            projected_openings.extend(_project_profile_openings(item, profile, spec))
            projected_holes.extend(_project_profile_holes(item, profile))
        projected_keepouts.extend(_project_keepouts(item, profile))
    if spec.template == "component_mount":
        return LayoutResult(
            hardware=tuple(resolved),
            openings=(),
            mounting_holes=(),
            keepouts=tuple(projected_keepouts),
            mounts=(),
            capacity_violations=(),
        )
    resolved_mounts = _resolve_mounts(spec, resolved, profiles, projected_openings)

    return LayoutResult(
        hardware=tuple(resolved),
        openings=tuple(projected_openings),
        mounting_holes=tuple(projected_holes),
        keepouts=tuple(projected_keepouts),
        mounts=tuple(resolved_mounts),
        capacity_violations=tuple(capacity_violations),
    )


def rotated_size(size: Size3, rotation_z_deg: int) -> Size3:
    if rotation_z_deg in (90, 270):
        return Size3(
            length_x=size.width_y,
            width_y=size.length_x,
            height_z=size.height_z,
        )
    return size


def aabb_from_center_size(center: Point3, size: Size3) -> Aabb:
    return Aabb(
        min_x=center.x - size.length_x / 2,
        min_y=center.y - size.width_y / 2,
        min_z=center.z - size.height_z / 2,
        max_x=center.x + size.length_x / 2,
        max_y=center.y + size.width_y / 2,
        max_z=center.z + size.height_z / 2,
    )


def aabb_overlap(left: Aabb, right: Aabb, clearance: float = 0.0) -> bool:
    """Return whether two boxes overlap or violate a requested separation."""

    return all(
        (
            left.max_x + clearance > right.min_x,
            right.max_x + clearance > left.min_x,
            left.max_y + clearance > right.min_y,
            right.max_y + clearance > left.min_y,
            left.max_z + clearance > right.min_z,
            right.max_z + clearance > left.min_z,
        )
    )


def combined_aabb(bounds: Iterable[Aabb]) -> Aabb:
    items = tuple(bounds)
    if not items:
        raise ValueError("at least one AABB is required")
    return Aabb(
        min_x=min(item.min_x for item in items),
        min_y=min(item.min_y for item in items),
        min_z=min(item.min_z for item in items),
        max_x=max(item.max_x for item in items),
        max_y=max(item.max_y for item in items),
        max_z=max(item.max_z for item in items),
    )


def lid_fastener_centers(spec: CadBuildSpec) -> tuple[Point2, ...]:
    fasteners = spec.enclosure.lid_fasteners
    if not fasteners.enabled:
        return ()
    x = spec.enclosure.inner_length_x / 2 - fasteners.edge_inset
    y = spec.enclosure.inner_width_y / 2 - fasteners.edge_inset
    return (
        Point2(x=-x, y=-y),
        Point2(x=x, y=-y),
        Point2(x=-x, y=y),
        Point2(x=x, y=y),
    )


def _pack_dimensions(spec: CadBuildSpec, surface: MountSurface) -> tuple[float, float, float]:
    if surface in (MountSurface.FRONT_INNER, MountSurface.BACK_INNER):
        return (
            spec.enclosure.inner_length_x,
            spec.enclosure.inner_height_z,
            spec.enclosure.floor_thickness + spec.enclosure.inner_height_z / 2,
        )
    if surface in (MountSurface.LEFT_INNER, MountSurface.RIGHT_INNER):
        return (
            spec.enclosure.inner_width_y,
            spec.enclosure.inner_height_z,
            spec.enclosure.floor_thickness + spec.enclosure.inner_height_z / 2,
        )
    return spec.enclosure.inner_length_x, spec.enclosure.inner_width_y, 0.0


def _effective_edge_clearance(
    spec: CadBuildSpec,
    items: list[tuple[HardwareInstance, HardwareProfile]],
) -> float:
    """Reserve both the enclosure edge and every profile's mounting clearance."""

    return max(
        spec.enclosure.edge_clearance,
        *(profile.mounting.clearance for _, profile in items),
    )


def _surface_center(
    surface: MountSurface,
    center: Point2,
    profile: HardwareProfile,
    spec: CadBuildSpec,
    *,
    instance_id: str,
) -> Point3:
    enclosure = spec.enclosure
    height = profile.dimensions.height_z
    if surface is MountSurface.BASE_FLOOR:
        support_height = max(
            [
                standoff.height
                for standoff in spec.standoffs
                if standoff.supports_instance_id == instance_id
            ]
            + (
                [enclosure.min_wall_thickness]
                if profile.mounting.strategy is HardwareMountingStrategy.EDGE_RETAINER
                else []
            ),
            default=0.0,
        )
        return Point3(
            x=center.x,
            y=center.y,
            z=enclosure.floor_thickness + support_height + height / 2,
        )
    if surface is MountSurface.LID_INNER:
        return Point3(x=center.x, y=center.y, z=enclosure.base_height_z - height / 2)
    if surface is MountSurface.LID_OUTER:
        return Point3(x=center.x, y=center.y, z=enclosure.overall_height_z + height / 2)
    if surface is MountSurface.FRONT_INNER:
        return Point3(
            x=center.x,
            y=-enclosure.outer_width_y / 2 + enclosure.wall_thickness + height / 2,
            z=center.y,
        )
    if surface is MountSurface.BACK_INNER:
        return Point3(
            x=center.x,
            y=enclosure.outer_width_y / 2 - enclosure.wall_thickness - height / 2,
            z=center.y,
        )
    if surface is MountSurface.LEFT_INNER:
        return Point3(
            x=-enclosure.outer_length_x / 2 + enclosure.wall_thickness + height / 2,
            y=center.x,
            z=center.y,
        )
    if surface is MountSurface.RIGHT_INNER:
        return Point3(
            x=enclosure.outer_length_x / 2 - enclosure.wall_thickness - height / 2,
            y=center.x,
            z=center.y,
        )
    raise ValueError("external hardware requires an explicit three-dimensional center")


def _resolve_mounts(
    spec: CadBuildSpec,
    hardware: list[ResolvedHardware],
    profiles: dict[str, HardwareProfile],
    openings: list[ResolvedOpening],
) -> list[ResolvedMount]:
    enclosure = spec.enclosure
    feature = enclosure.min_wall_thickness
    join_overlap = MOUNT_JOIN_OVERLAP_MM
    result: list[ResolvedMount] = []
    for item in hardware:
        profile = profiles[item.profile_id]
        if profile.mounting.strategy is not HardwareMountingStrategy.EDGE_RETAINER:
            continue
        if item.surface is not MountSurface.BASE_FLOOR:
            continue
        clearance = profile.mounting.clearance
        tray_length = item.rotated_size.length_x + (clearance + join_overlap) * 2
        tray_width = item.rotated_size.width_y + (clearance + join_overlap) * 2
        tray_height = feature + join_overlap
        tray_z = enclosure.floor_thickness + (feature - join_overlap) / 2
        retainer_height = feature + join_overlap
        retainer_z = enclosure.floor_thickness + feature + (feature - join_overlap) / 2
        mounts = (
            (
                "support_tray",
                ResolvedMountKind.SUPPORT_TRAY,
                Point3(x=item.center.x, y=item.center.y, z=tray_z),
                Size3(length_x=tray_length, width_y=tray_width, height_z=tray_height),
            ),
            (
                "side_retainer_front",
                ResolvedMountKind.SIDE_RETAINER,
                Point3(
                    x=item.center.x,
                    y=item.center.y
                    - item.rotated_size.width_y / 2
                    - clearance
                    - feature / 2,
                    z=retainer_z,
                ),
                Size3(
                    length_x=item.rotated_size.length_x,
                    width_y=feature,
                    height_z=retainer_height,
                ),
            ),
            (
                "side_retainer_back",
                ResolvedMountKind.SIDE_RETAINER,
                Point3(
                    x=item.center.x,
                    y=item.center.y
                    + item.rotated_size.width_y / 2
                    + clearance
                    + feature / 2,
                    z=retainer_z,
                ),
                Size3(
                    length_x=item.rotated_size.length_x,
                    width_y=feature,
                    height_z=retainer_height,
                ),
            ),
            (
                "end_stop_left",
                ResolvedMountKind.END_STOP,
                Point3(
                    x=item.center.x
                    - item.rotated_size.length_x / 2
                    - clearance
                    - feature / 2,
                    y=item.center.y,
                    z=retainer_z,
                ),
                Size3(
                    length_x=feature,
                    width_y=item.rotated_size.width_y,
                    height_z=retainer_height,
                ),
            ),
            (
                "end_stop_right",
                ResolvedMountKind.END_STOP,
                Point3(
                    x=item.center.x
                    + item.rotated_size.length_x / 2
                    + clearance
                    + feature / 2,
                    y=item.center.y,
                    z=retainer_z,
                ),
                Size3(
                    length_x=feature,
                    width_y=item.rotated_size.width_y,
                    height_z=retainer_height,
                ),
            ),
        )
        for suffix, kind, center, size in mounts:
            center, size = _trim_retainer_for_service_opening(
                item=item,
                suffix=suffix,
                center=center,
                size=size,
                openings=openings,
                join_overlap=join_overlap,
            )
            result.append(
                ResolvedMount(
                    mount_id=f"{item.instance_id}_{suffix}",
                    hardware_instance_id=item.instance_id,
                    kind=kind,
                    center=center,
                    size=size,
                    bounds=aabb_from_center_size(center, size),
                )
            )
    return result


def _trim_retainer_for_service_opening(
    *,
    item: ResolvedHardware,
    suffix: str,
    center: Point3,
    size: Size3,
    openings: list[ResolvedOpening],
    join_overlap: float,
) -> tuple[Point3, Size3]:
    service_face = {
        "side_retainer_front": Face.FRONT,
        "side_retainer_back": Face.BACK,
        "end_stop_left": Face.LEFT,
        "end_stop_right": Face.RIGHT,
    }.get(suffix)
    if service_face is None:
        return center, size
    bounds = aabb_from_center_size(center, size)
    mount_u_min, mount_u_max = (
        (bounds.min_y, bounds.max_y)
        if service_face in {Face.LEFT, Face.RIGHT}
        else (bounds.min_x, bounds.max_x)
    )
    opening_bottoms: list[float] = []
    for projected in openings:
        opening = projected.opening
        if (
            projected.hardware_instance_id != item.instance_id
            or opening.face is not service_face
        ):
            continue
        half_u, half_v = _opening_half_size(opening)
        opening_u_min = opening.center_u - half_u
        opening_u_max = opening.center_u + half_u
        opening_bottom = opening.center_v - half_v
        opening_top = opening.center_v + half_v
        overlaps_u = min(mount_u_max, opening_u_max) - max(mount_u_min, opening_u_min) > 1e-6
        overlaps_z = min(bounds.max_z, opening_top) - max(bounds.min_z, opening_bottom) > 1e-6
        if overlaps_u and overlaps_z:
            opening_bottoms.append(opening_bottom)
    if not opening_bottoms:
        return center, size

    retainer_floor = item.bounds.min_z
    maximum_z = min(opening_bottoms)
    if maximum_z <= retainer_floor + 1e-6:
        return center, size
    minimum_z = retainer_floor - join_overlap
    trimmed_height = maximum_z - minimum_z
    return (
        Point3(x=center.x, y=center.y, z=minimum_z + trimmed_height / 2),
        Size3(
            length_x=size.length_x,
            width_y=size.width_y,
            height_z=trimmed_height,
        ),
    )


def _opening_half_size(
    opening: CircularOpening | RectangularOpening,
) -> tuple[float, float]:
    if isinstance(opening, CircularOpening):
        half = opening.diameter / 2
        return half, half
    return opening.size_u / 2, opening.size_v / 2


def _frame_for(surface: MountSurface, rotation_z_deg: int) -> _Frame:
    base = {
        MountSurface.BASE_FLOOR: _Frame((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        MountSurface.LID_INNER: _Frame((1.0, 0.0, 0.0), (0.0, -1.0, 0.0), (0.0, 0.0, -1.0)),
        MountSurface.LID_OUTER: _Frame((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
        MountSurface.FRONT_INNER: _Frame((1.0, 0.0, 0.0), (0.0, 0.0, 1.0), (0.0, -1.0, 0.0)),
        MountSurface.BACK_INNER: _Frame((1.0, 0.0, 0.0), (0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
        MountSurface.LEFT_INNER: _Frame((0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (-1.0, 0.0, 0.0)),
        MountSurface.RIGHT_INNER: _Frame((0.0, 0.0, -1.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0)),
        MountSurface.EXTERNAL: _Frame((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    }[surface]
    angle = rotation_z_deg % 360
    if angle == 0:
        return base
    if angle == 90:
        return _Frame(base.basis_y, _neg(base.basis_x), base.normal)
    if angle == 180:
        return _Frame(_neg(base.basis_x), _neg(base.basis_y), base.normal)
    if angle == 270:
        return _Frame(_neg(base.basis_y), base.basis_x, base.normal)
    raise ValueError("rotation must be a quarter turn")


def _neg(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(-value for value in vector)  # type: ignore[return-value]


def _world_point(center: Point3, frame: _Frame, local: Point3) -> Point3:
    return Point3(
        x=center.x + frame.basis_x[0] * local.x + frame.basis_y[0] * local.y + frame.normal[0] * local.z,
        y=center.y + frame.basis_x[1] * local.x + frame.basis_y[1] * local.y + frame.normal[1] * local.z,
        z=center.z + frame.basis_x[2] * local.x + frame.basis_y[2] * local.y + frame.normal[2] * local.z,
    )


def _transformed_bounds(center: Point3, size: Size3, frame: _Frame) -> Aabb:
    points = [
        _world_point(center, frame, Point3(x=x, y=y, z=z))
        for x in (-size.length_x / 2, size.length_x / 2)
        for y in (-size.width_y / 2, size.width_y / 2)
        for z in (-size.height_z / 2, size.height_z / 2)
    ]
    return Aabb(
        min_x=min(point.x for point in points),
        min_y=min(point.y for point in points),
        min_z=min(point.z for point in points),
        max_x=max(point.x for point in points),
        max_y=max(point.y for point in points),
        max_z=max(point.z for point in points),
    )


def _surface_face(surface: MountSurface) -> Face | None:
    return {
        MountSurface.BASE_FLOOR: Face.BOTTOM,
        MountSurface.LID_INNER: Face.TOP,
        MountSurface.LID_OUTER: Face.TOP,
        MountSurface.FRONT_INNER: Face.FRONT,
        MountSurface.BACK_INNER: Face.BACK,
        MountSurface.LEFT_INNER: Face.LEFT,
        MountSurface.RIGHT_INNER: Face.RIGHT,
    }.get(surface)


def _opening_from_profile(
    item: ResolvedHardware,
    opening: ProfileCircularOpening | ProfileRectangularOpening,
    spec: CadBuildSpec,
) -> tuple[OpeningSpec, Point3]:
    mounted_face = _surface_face(item.surface)
    face = (
        opening.preferred_face
        if item.surface in {
            MountSurface.BASE_FLOOR,
            MountSurface.LID_INNER,
            MountSurface.LID_OUTER,
        }
        and opening.preferred_face in {Face.LEFT, Face.RIGHT, Face.FRONT, Face.BACK}
        else mounted_face
    )
    if face is None:
        raise ValueError("external hardware cannot project an enclosure opening")
    cross_face = face is not mounted_face
    local = Point3(
        x=opening.center.x,
        y=opening.center.y,
        z=opening.center_z if cross_face else item.rotated_size.height_z / 2,
    )
    world = _world_point(item.center, _frame_for(item.surface, item.rotation_z_deg), local)
    if cross_face:
        world = _project_to_face_plane(face, world, spec)
    if isinstance(opening, ProfileCircularOpening):
        return (
            CircularOpening(
                opening_id=f"{item.instance_id}_{opening.opening_id}",
                face=face,
                center_u=_face_u(face, world),
                center_v=_face_v(face, world),
                diameter=opening.diameter + opening.clearance * 2,
            ),
            world,
        )
    size_u = opening.size_u
    size_v = opening.size_v
    if item.rotation_z_deg in (90, 270):
        size_u, size_v = size_v, size_u
    return (
        RectangularOpening(
            opening_id=f"{item.instance_id}_{opening.opening_id}",
            face=face,
            center_u=_face_u(face, world),
            center_v=_face_v(face, world),
            size_u=size_u + opening.clearance * 2,
            size_v=size_v + opening.clearance * 2,
            corner_radius=opening.corner_radius,
        ),
        world,
    )


def _project_profile_openings(
    item: ResolvedHardware,
    profile: HardwareProfile,
    spec: CadBuildSpec,
) -> list[ResolvedOpening]:
    result: list[ResolvedOpening] = []
    for opening in profile.openings:
        projected, world = _opening_from_profile(item, opening, spec)
        result.append(
            ResolvedOpening(
                opening_id=projected.opening_id,
                hardware_instance_id=item.instance_id,
                opening=projected,
                world_center=world,
            )
        )
    return result


def _project_profile_holes(
    item: ResolvedHardware,
    profile: HardwareProfile,
) -> list[ResolvedMountingHole]:
    face = _surface_face(item.surface)
    if face is None:
        return []
    frame = _frame_for(item.surface, item.rotation_z_deg)
    result: list[ResolvedMountingHole] = []
    for hole in profile.mounting.holes:
        world = _world_point(
            item.center,
            frame,
            Point3(x=hole.center.x, y=hole.center.y, z=item.rotated_size.height_z / 2),
        )
        result.append(
            ResolvedMountingHole(
                hole_id=f"{item.instance_id}_{hole.hole_id}",
                hardware_instance_id=item.instance_id,
                opening=CircularOpening(
                    opening_id=f"{item.instance_id}_{hole.hole_id}",
                    face=face,
                    center_u=_face_u(face, world),
                    center_v=_face_v(face, world),
                    diameter=hole.diameter,
                ),
                world_center=world,
            )
        )
    return result


def _project_keepouts(item: ResolvedHardware, profile: HardwareProfile) -> list[ResolvedKeepout]:
    frame = _frame_for(item.surface, item.rotation_z_deg)
    result: list[ResolvedKeepout] = []
    for keepout in profile.keepouts:
        center = _world_point(item.center, frame, keepout.center)
        result.append(
            ResolvedKeepout(
                keepout_id=f"{item.instance_id}_{keepout.keepout_id}",
                hardware_instance_id=item.instance_id,
                bounds=_transformed_bounds(center, keepout.size, frame),
            )
        )
    return result


def _face_u(face: Face, point: Point3) -> float:
    if face in (Face.TOP, Face.BOTTOM, Face.FRONT, Face.BACK):
        return point.x
    return point.y


def _face_v(face: Face, point: Point3) -> float:
    if face in (Face.TOP, Face.BOTTOM):
        return point.y
    return point.z


def _project_to_face_plane(face: Face, point: Point3, spec: CadBuildSpec) -> Point3:
    enclosure = spec.enclosure
    if face is Face.LEFT:
        return Point3(x=-enclosure.outer_length_x / 2, y=point.y, z=point.z)
    if face is Face.RIGHT:
        return Point3(x=enclosure.outer_length_x / 2, y=point.y, z=point.z)
    if face is Face.FRONT:
        return Point3(x=point.x, y=-enclosure.outer_width_y / 2, z=point.z)
    if face is Face.BACK:
        return Point3(x=point.x, y=enclosure.outer_width_y / 2, z=point.z)
    return point


def _anchor_cross_face_opening(
    center: Point2,
    instance: HardwareInstance,
    profile: HardwareProfile,
    spec: CadBuildSpec,
) -> Point2:
    placement = instance.placement
    if not isinstance(placement, SurfacePlacement) or MountSurface(placement.surface) not in {
        MountSurface.BASE_FLOOR,
        MountSurface.LID_INNER,
        MountSurface.LID_OUTER,
    }:
        return center
    side_faces = {
        opening.preferred_face
        for opening in profile.openings
        if opening.preferred_face in {Face.LEFT, Face.RIGHT, Face.FRONT, Face.BACK}
    }
    if not side_faces:
        return center
    if len(side_faces) > 1:
        raise ValueError(
            f"hardware profile requests openings on multiple side faces: {profile.profile_id}"
        )
    face = next(iter(side_faces))
    size = rotated_size(profile.dimensions, instance.rotation_z_deg)
    clearance = profile.mounting.clearance
    if profile.mounting.strategy is HardwareMountingStrategy.EDGE_RETAINER:
        clearance += spec.enclosure.min_wall_thickness
    enclosure = spec.enclosure
    if face is Face.LEFT:
        return Point2(
            x=-enclosure.inner_length_x / 2 + size.length_x / 2 + clearance,
            y=center.y,
        )
    if face is Face.RIGHT:
        return Point2(
            x=enclosure.inner_length_x / 2 - size.length_x / 2 - clearance,
            y=center.y,
        )
    if face is Face.FRONT:
        return Point2(
            x=center.x,
            y=-enclosure.inner_width_y / 2 + size.width_y / 2 + clearance,
        )
    return Point2(
        x=center.x,
        y=enclosure.inner_width_y / 2 - size.width_y / 2 - clearance,
    )


def _pack_in_rows(
    items: list[tuple[HardwareInstance, HardwareProfile]],
    *,
    inner_length: float,
    inner_width: float,
    gap: float,
    edge_clearance: float,
    surface: MountSurface,
) -> _PackResult:
    """Pack footprints in stable rows, centered on their mounting surface."""

    del surface
    measured = [
        (instance, rotated_size(profile.dimensions, instance.rotation_z_deg))
        for instance, profile in items
    ]
    measured.sort(key=lambda item: (-item[1].length_x, item[0].instance_id))
    usable_length = max(0.0, inner_length - edge_clearance * 2)
    usable_width = max(0.0, inner_width - edge_clearance * 2)
    rows: list[list[tuple[HardwareInstance, Size3]]] = []
    current: list[tuple[HardwareInstance, Size3]] = []
    current_width = 0.0
    for item in measured:
        width = item[1].length_x
        candidate_width = width if not current else current_width + gap + width
        if current and candidate_width > usable_length:
            rows.append(current)
            current = []
            current_width = 0.0
            candidate_width = width
        current.append(item)
        current_width = candidate_width
    if current:
        rows.append(current)

    row_heights = [max(item[1].width_y for item in row) for row in rows]
    total_height = sum(row_heights) + gap * max(0, len(rows) - 1)
    cursor_y = -total_height / 2
    result: dict[str, Point2] = {}
    for row, row_height in zip(rows, row_heights, strict=True):
        row_width = sum(item[1].length_x for item in row) + gap * max(0, len(row) - 1)
        cursor_x = -row_width / 2
        for instance, size in row:
            result[instance.instance_id] = Point2(
                x=round(cursor_x + size.length_x / 2, 6),
                y=round(cursor_y + row_height / 2, 6),
            )
            cursor_x += size.length_x + gap
        cursor_y += row_height + gap

    required_length = max(
        (
            sum(item[1].length_x for item in row) + gap * max(0, len(row) - 1)
            for row in rows
        ),
        default=0.0,
    )
    return _PackResult(
        centers=result,
        required_length=required_length,
        required_width=total_height,
        usable_length=usable_length,
        usable_width=usable_width,
    )
