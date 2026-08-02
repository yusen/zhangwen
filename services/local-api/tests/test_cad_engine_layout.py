from __future__ import annotations

import pytest

from zhangwen.cad_engine.geometry import build_geometry
from zhangwen.cad_engine.layout import resolve_layout
from zhangwen.cad_engine.models import (
    BoxWithLidParameters,
    CadBuildSpec,
    CircularOpening,
    Face,
    HardwareCoordinateSystem,
    HardwareInstance,
    HardwareMounting,
    HardwareMountingStrategy,
    HardwareProfile,
    KeepoutSpec,
    MountSurface,
    Point2,
    Point3,
    ProfileCircularOpening,
    ProfileMountingHole,
    ProfileRectangularOpening,
    ProfileSource,
    Size3,
    StandoffSpec,
    SurfacePlacement,
    ResolvedMountKind,
)
from zhangwen.cad_engine.validation import validate_design


def envelope_profile(profile_id: str, *, length: float = 20.0) -> HardwareProfile:
    return HardwareProfile(
        profile_id=profile_id,
        revision="v1",
        display_name=profile_id,
        category="sensor",
        roles=("sensor",),
        dimensions=Size3(length_x=length, width_y=15.0, height_z=5.0),
        coordinate_system=HardwareCoordinateSystem(origin="envelope_center"),
        mounting=HardwareMounting(
            mode="base_floor",
            preferred_surface=MountSurface.BASE_FLOOR,
            clearance=0.8,
        ),
        source=ProfileSource.DECLARED,
    )


def check_status(spec: CadBuildSpec, check_id: str) -> str:
    report = validate_design(spec, resolve_layout(spec))
    return next(check.status for check in report.checks if check.check_id == check_id)


def sidewall_profile() -> HardwareProfile:
    return HardwareProfile(
        profile_id="sidewall_sensor",
        revision="v1",
        display_name="Sidewall sensor",
        category="sensor",
        roles=("sensor",),
        dimensions=Size3(length_x=8.0, width_y=6.0, height_z=4.0),
        coordinate_system=HardwareCoordinateSystem(origin="envelope_center"),
        mounting=HardwareMounting(
            mode="inner_surface",
            preferred_surface=MountSurface.FRONT_INNER,
            allowed_enclosure_surfaces=(
                MountSurface.FRONT_INNER,
                MountSurface.BACK_INNER,
                MountSurface.LEFT_INNER,
                MountSurface.RIGHT_INNER,
            ),
        ),
        keepouts=(
            KeepoutSpec(
                keepout_id="connector",
                center=Point3(x=1.0, y=2.0, z=0.0),
                size=Size3(length_x=2.0, width_y=2.0, height_z=2.0),
            ),
        ),
        openings=(
            ProfileCircularOpening(
                opening_id="aperture",
                center=Point2(x=1.0, y=2.0),
                diameter=2.0,
            ),
        ),
        source=ProfileSource.DECLARED,
    )


def edge_retainer_profile(profile_id: str = "retained_board") -> HardwareProfile:
    return HardwareProfile(
        profile_id=profile_id,
        revision="v1",
        display_name="Retained board",
        category="controller",
        roles=("controller",),
        dimensions=Size3(length_x=20.0, width_y=14.0, height_z=4.0),
        coordinate_system=HardwareCoordinateSystem(origin="envelope_center"),
        mounting=HardwareMounting(
            mode="base_floor",
            preferred_surface=MountSurface.BASE_FLOOR,
            clearance=0.8,
            strategy=HardwareMountingStrategy.EDGE_RETAINER,
        ),
        source=ProfileSource.DECLARED,
    )


def test_automatic_row_layout_is_stable_and_clear() -> None:
    profiles = (envelope_profile("alpha"), envelope_profile("beta"))
    hardware = tuple(
        HardwareInstance(
            instance_id=profile.profile_id,
            profile_id=profile.profile_id,
            placement=SurfacePlacement(surface="base_floor"),
        )
        for profile in profiles
    )
    spec = CadBuildSpec(design_id="auto_layout", profiles=profiles, hardware=hardware)

    first = resolve_layout(spec)
    second = resolve_layout(spec)

    assert first == second
    assert [item.center.x for item in first.hardware] == [-12.5, 12.5]
    assert validate_design(spec, first).ok is True


def test_automatic_sidewall_layout_uses_floor_and_profile_clearance() -> None:
    profile = sidewall_profile().model_copy(
        update={
            "mounting": sidewall_profile().mounting.model_copy(
                update={"clearance": 2.0}
            )
        }
    )
    spec = CadBuildSpec(
        design_id="automatic_sidewall",
        enclosure=BoxWithLidParameters(
            inner_height_z=40.0,
            floor_thickness=3.0,
            edge_clearance=0.0,
        ),
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="sensor",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="front_inner"),
            ),
        ),
    )

    layout = resolve_layout(spec)
    item = layout.hardware[0]

    assert item.bounds.min_z >= spec.enclosure.floor_thickness + 2.0 - 1e-6
    assert item.bounds.max_z <= spec.enclosure.base_height_z - 2.0 + 1e-6
    assert check_status(spec, "layout_surface_capacity") == "pass"
    assert check_status(spec, "hardware_bounds") == "pass"


def test_automatic_layout_reports_second_axis_capacity_overflow() -> None:
    profile = envelope_profile("wide", length=20.0).model_copy(
        update={"dimensions": Size3(length_x=20.0, width_y=15.0, height_z=5.0)}
    )
    profiles = tuple(profile.model_copy(update={"profile_id": f"wide_{index}"}) for index in range(3))
    spec = CadBuildSpec(
        design_id="capacity_overflow",
        enclosure=BoxWithLidParameters(
            inner_length_x=60.0,
            inner_width_y=40.0,
            edge_clearance=8.0,
            hardware_gap=5.0,
        ),
        profiles=profiles,
        hardware=tuple(
            HardwareInstance(
                instance_id=profile.profile_id,
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="base_floor"),
            )
            for profile in profiles
        ),
    )

    layout = resolve_layout(spec)

    assert any(violation.startswith("base_floor:") for violation in layout.capacity_violations)
    assert check_status(spec, "layout_surface_capacity") == "fail"


def test_explicit_overlapping_hardware_fails_interference_check() -> None:
    profiles = (envelope_profile("alpha"), envelope_profile("beta"))
    hardware = tuple(
        HardwareInstance(
            instance_id=profile.profile_id,
            profile_id=profile.profile_id,
            placement=SurfacePlacement(surface="base_floor", center=Point2(x=0.0, y=0.0)),
        )
        for profile in profiles
    )
    spec = CadBuildSpec(design_id="overlap", profiles=profiles, hardware=hardware)

    assert check_status(spec, "hardware_interference") == "fail"


def test_configured_minimum_wall_covers_shell_lip_and_posts() -> None:
    spec = CadBuildSpec(
        design_id="thin_wall",
        enclosure=BoxWithLidParameters(wall_thickness=1.2, min_wall_thickness=1.6),
    )

    assert check_status(spec, "minimum_wall_thickness") == "fail"


def test_opening_too_close_to_edge_is_rejected_before_geometry() -> None:
    spec = CadBuildSpec(
        design_id="bad_opening",
        openings=(
            CircularOpening(
                opening_id="edge_hole",
                face=Face.TOP,
                center_u=48.0,
                center_v=0.0,
                diameter=10.0,
            ),
        ),
    )

    assert check_status(spec, "opening_edge_clearance") == "fail"


def test_supported_board_is_elevated_to_the_standoff_top() -> None:
    profile = envelope_profile("controller_board")
    instance = HardwareInstance(
        instance_id="controller_board",
        profile_id=profile.profile_id,
        placement=SurfacePlacement(surface="base_floor", center=Point2(x=0.0, y=0.0)),
    )
    spec = CadBuildSpec(
        design_id="supported_board",
        profiles=(profile,),
        hardware=(instance,),
        standoffs=(
            StandoffSpec(
                standoff_id="board_post",
                center=Point2(x=0.0, y=0.0),
                outer_diameter=6.0,
                bore_diameter=2.4,
                height=8.0,
                supports_instance_id="controller_board",
            ),
        ),
    )

    layout = resolve_layout(spec)

    assert layout.hardware[0].bounds.min_z == spec.enclosure.floor_thickness + 8.0
    assert validate_design(spec, layout).ok is True


def test_edge_retainer_resolves_complete_auditable_mount_set() -> None:
    profile = edge_retainer_profile()
    spec = CadBuildSpec(
        design_id="edge_retainer_layout",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="retained_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
            ),
        ),
    )

    layout = resolve_layout(spec)

    assert [mount.kind for mount in layout.mounts] == [
        ResolvedMountKind.SUPPORT_TRAY,
        ResolvedMountKind.SIDE_RETAINER,
        ResolvedMountKind.SIDE_RETAINER,
        ResolvedMountKind.END_STOP,
        ResolvedMountKind.END_STOP,
    ]
    assert all(mount.hardware_instance_id == "retained_board" for mount in layout.mounts)
    tray = layout.mounts[0]
    assert tray.size.length_x == pytest.approx(21.7)
    assert tray.size.width_y == pytest.approx(15.7)
    assert tray.size.height_z == pytest.approx(spec.enclosure.min_wall_thickness + 0.05)
    assert tray.bounds.max_z == pytest.approx(
        spec.enclosure.floor_thickness + spec.enclosure.min_wall_thickness
    )
    end_stops = [mount for mount in layout.mounts if mount.kind is ResolvedMountKind.END_STOP]
    assert [mount.size.model_dump() for mount in end_stops] == [
        {
            "length_x": spec.enclosure.min_wall_thickness,
            "width_y": 14.0,
            "height_z": spec.enclosure.min_wall_thickness + 0.05,
        }
    ] * 2
    assert all(
        mount.bounds.min_z
        == pytest.approx(
            spec.enclosure.floor_thickness + spec.enclosure.min_wall_thickness - 0.05
        )
        for mount in end_stops
    )
    assert layout.hardware[0].bounds.min_z == pytest.approx(
        spec.enclosure.floor_thickness + spec.enclosure.min_wall_thickness
    )
    assert check_status(spec, "mounting_completeness") == "pass"
    assert check_status(spec, "mount_clearance") == "pass"


def test_edge_retainer_service_opening_trims_only_the_adjacent_end_stop_height() -> None:
    profile = edge_retainer_profile("service_board").model_copy(
        update={
            "openings": (
                ProfileRectangularOpening(
                    opening_id="service_port",
                    center=Point2(x=8.0, y=0.0),
                    center_z=2.0,
                    size_u=10.0,
                    size_v=5.6,
                    preferred_face=Face.LEFT,
                    clearance=0.8,
                ),
            ),
        }
    )
    spec = CadBuildSpec(
        design_id="edge_retainer_service_opening",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="service_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="base_floor"),
            ),
        ),
    )

    layout = resolve_layout(spec)
    hardware = layout.hardware[0]
    opening = layout.openings[0].opening
    left_stop = next(mount for mount in layout.mounts if mount.mount_id.endswith("end_stop_left"))
    right_stop = next(mount for mount in layout.mounts if mount.mount_id.endswith("end_stop_right"))

    assert hardware.bounds.min_x == pytest.approx(
        -spec.enclosure.inner_length_x / 2
        + profile.mounting.clearance
        + spec.enclosure.min_wall_thickness
    )
    assert left_stop.bounds.min_x == pytest.approx(-spec.enclosure.inner_length_x / 2)
    assert left_stop.size.length_x == pytest.approx(spec.enclosure.min_wall_thickness)
    assert left_stop.bounds.min_z == pytest.approx(hardware.bounds.min_z - 0.05)
    assert left_stop.bounds.max_z == pytest.approx(opening.center_v - opening.size_v / 2)
    assert left_stop.size.height_z < right_stop.size.height_z
    assert right_stop.size.height_z == pytest.approx(spec.enclosure.min_wall_thickness + 0.05)
    assert validate_design(spec, layout).ok is True


def test_edge_retainer_service_opening_too_low_remains_an_explicit_conflict() -> None:
    profile = edge_retainer_profile("blocked_service_board").model_copy(
        update={
            "openings": (
                ProfileRectangularOpening(
                    opening_id="blocked_service_port",
                    center=Point2(x=8.0, y=0.0),
                    center_z=0.0,
                    size_u=10.0,
                    size_v=5.6,
                    preferred_face=Face.LEFT,
                    clearance=0.8,
                ),
            ),
        }
    )
    spec = CadBuildSpec(
        design_id="edge_retainer_blocked_service_opening",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="blocked_service_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="base_floor"),
            ),
        ),
    )

    report = validate_design(spec, resolve_layout(spec))
    opening_mount = next(
        check for check in report.checks if check.check_id == "opening_mount_clearance"
    )

    assert opening_mount.status == "fail"
    assert set(opening_mount.evidence) == {
        "blocked_service_board_blocked_service_port:blocked_service_board_support_tray",
        "blocked_service_board_blocked_service_port:blocked_service_board_end_stop_left",
    }


def test_edge_retainer_missing_member_fails_mounting_completeness() -> None:
    profile = edge_retainer_profile()
    spec = CadBuildSpec(
        design_id="edge_retainer_incomplete",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="retained_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="base_floor"),
            ),
        ),
    )
    layout = resolve_layout(spec)
    incomplete = layout.model_copy(update={"mounts": layout.mounts[:-1]})

    report = validate_design(spec, incomplete)

    assert next(
        check.status for check in report.checks if check.check_id == "mounting_completeness"
    ) == "fail"


def test_edge_retainer_mount_collision_with_non_target_hardware_fails() -> None:
    retained = edge_retainer_profile()
    neighbour = envelope_profile("neighbour").model_copy(
        update={"dimensions": Size3(length_x=2.0, width_y=2.0, height_z=3.0)}
    )
    spec = CadBuildSpec(
        design_id="edge_retainer_collision",
        profiles=(retained, neighbour),
        hardware=(
            HardwareInstance(
                instance_id="retained_board",
                profile_id=retained.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
            ),
            HardwareInstance(
                instance_id="neighbour",
                profile_id=neighbour.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=11.6, y=0.0),
                ),
            ),
        ),
    )

    assert check_status(spec, "mount_clearance") == "fail"


def test_hole_fastened_strategy_requires_and_resolves_profile_holes() -> None:
    profile = envelope_profile("fastened").model_copy(
        update={
            "mounting": HardwareMounting(
                mode="base_floor",
                preferred_surface=MountSurface.BASE_FLOOR,
                strategy=HardwareMountingStrategy.HOLE_FASTENED,
                holes=(
                    ProfileMountingHole(
                        hole_id="m3_center",
                        center=Point2(x=0.0, y=0.0),
                        diameter=3.2,
                    ),
                ),
            )
        }
    )
    spec = CadBuildSpec(
        design_id="hole_fastened",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="fastened",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
            ),
        ),
    )

    layout = resolve_layout(spec)

    assert [hole.hole_id for hole in layout.mounting_holes] == ["fastened_m3_center"]
    assert check_status(spec, "mounting_completeness") == "pass"


def test_opening_over_lid_post_fails_opening_mount_clearance() -> None:
    spec = CadBuildSpec(
        design_id="opening_lid_post_collision",
        openings=(
            CircularOpening(
                opening_id="top_access",
                face=Face.TOP,
                center_u=42.0,
                center_v=27.0,
                diameter=6.0,
            ),
        ),
    )

    assert check_status(spec, "opening_mount_clearance") == "fail"


def test_opening_over_standoff_fails_opening_mount_clearance() -> None:
    spec = CadBuildSpec(
        design_id="opening_standoff_collision",
        openings=(
            CircularOpening(
                opening_id="bottom_access",
                face=Face.BOTTOM,
                center_u=0.0,
                center_v=0.0,
                diameter=6.0,
            ),
        ),
        standoffs=(
            StandoffSpec(
                standoff_id="center_post",
                center=Point2(x=0.0, y=0.0),
                outer_diameter=6.0,
                bore_diameter=2.4,
                height=8.0,
            ),
        ),
    )

    assert check_status(spec, "opening_mount_clearance") == "fail"


def test_opening_over_edge_retainer_mount_fails_opening_mount_clearance() -> None:
    profile = edge_retainer_profile()
    spec = CadBuildSpec(
        design_id="opening_edge_mount_collision",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="retained_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
            ),
        ),
        openings=(
            CircularOpening(
                opening_id="bottom_access",
                face=Face.BOTTOM,
                center_u=0.0,
                center_v=0.0,
                diameter=6.0,
            ),
        ),
    )

    assert check_status(spec, "opening_mount_clearance") == "fail"


def test_keepout_entering_inner_wall_fails_profile_keepout_clearance() -> None:
    profile = envelope_profile("wall_keepout").model_copy(
        update={
            "dimensions": Size3(length_x=10.0, width_y=10.0, height_z=4.0),
            "keepouts": (
                KeepoutSpec(
                    keepout_id="connector",
                    center=Point3(x=5.0, y=0.0, z=0.0),
                    size=Size3(length_x=4.0, width_y=4.0, height_z=4.0),
                ),
            ),
        }
    )
    spec = CadBuildSpec(
        design_id="keepout_inner_wall",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="wall_keepout",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=44.0, y=0.0),
                ),
            ),
        ),
    )

    assert check_status(spec, "hardware_bounds") == "pass"
    assert check_status(spec, "profile_keepout_clearance") == "fail"


def test_edge_retainer_geometry_is_unioned_into_base() -> None:
    pytest.importorskip("cadquery", reason="CadQuery is required for mount geometry")
    retained = edge_retainer_profile()
    unsupported = retained.model_copy(
        update={
            "profile_id": "unsupported_board",
            "mounting": retained.mounting.model_copy(
                update={"strategy": HardwareMountingStrategy.NONE}
            ),
        }
    )

    def build_spec(profile: HardwareProfile) -> CadBuildSpec:
        return CadBuildSpec(
            design_id=f"geometry_{profile.profile_id}",
            profiles=(profile,),
            hardware=(
                HardwareInstance(
                    instance_id=profile.profile_id,
                    profile_id=profile.profile_id,
                    placement=SurfacePlacement(
                        surface="base_floor",
                        center=Point2(x=0.0, y=0.0),
                    ),
                    include_reference_geometry=False,
                ),
            ),
        )

    retained_spec = build_spec(retained)
    unsupported_spec = build_spec(unsupported)
    retained_base = build_geometry(retained_spec, resolve_layout(retained_spec)).base.shape
    unsupported_base = build_geometry(unsupported_spec, resolve_layout(unsupported_spec)).base.shape

    assert retained_base.Volume() > unsupported_base.Volume()
    assert len(retained_base.Solids()) == 1


@pytest.mark.parametrize(
    ("surface", "normal", "hardware_center", "opening_center", "opening_uv"),
    (
        (
            "front_inner",
            (0.0, -1.0, 0.0),
            (3.0, -33.0, 20.0),
            (4.0, -35.0, 22.0),
            (4.0, 22.0),
        ),
        (
            "back_inner",
            (0.0, 1.0, 0.0),
            (3.0, 33.0, 20.0),
            (4.0, 35.0, 18.0),
            (4.0, 18.0),
        ),
        (
            "left_inner",
            (-1.0, 0.0, 0.0),
            (-48.0, 3.0, 20.0),
            (-50.0, 5.0, 21.0),
            (5.0, 21.0),
        ),
        (
            "right_inner",
            (1.0, 0.0, 0.0),
            (48.0, 3.0, 20.0),
            (50.0, 5.0, 19.0),
            (5.0, 19.0),
        ),
    ),
)
def test_sidewall_frames_project_stable_world_coordinates(
    surface: str,
    normal: tuple[float, float, float],
    hardware_center: tuple[float, float, float],
    opening_center: tuple[float, float, float],
    opening_uv: tuple[float, float],
) -> None:
    profile = sidewall_profile()
    spec = CadBuildSpec(
        design_id=f"sidewall_{surface}",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="sensor",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface=surface,
                    center=Point2(x=3.0, y=20.0),
                ),
            ),
        ),
    )

    layout = resolve_layout(spec)

    resolved = layout.hardware[0]
    projected = layout.openings[0]
    assert (resolved.normal.x, resolved.normal.y, resolved.normal.z) == normal
    assert (resolved.center.x, resolved.center.y, resolved.center.z) == hardware_center
    assert (
        projected.world_center.x,
        projected.world_center.y,
        projected.world_center.z,
    ) == opening_center
    assert (
        projected.opening.center_u,
        projected.opening.center_v,
    ) == opening_uv


@pytest.mark.parametrize(
    ("surface", "normal", "opening_center", "opening_uv"),
    (
        ("front_inner", (0.0, -1.0, 0.0), (1.0, -35.0, 21.0), (1.0, 21.0)),
        ("back_inner", (0.0, 1.0, 0.0), (1.0, 35.0, 19.0), (1.0, 19.0)),
        ("left_inner", (-1.0, 0.0, 0.0), (-50.0, 4.0, 18.0), (4.0, 18.0)),
        ("right_inner", (1.0, 0.0, 0.0), (50.0, 4.0, 22.0), (4.0, 22.0)),
    ),
)
def test_sidewall_quarter_turn_rotates_local_coordinates_about_the_surface_normal(
    surface: str,
    normal: tuple[float, float, float],
    opening_center: tuple[float, float, float],
    opening_uv: tuple[float, float],
) -> None:
    profile = sidewall_profile()
    spec = CadBuildSpec(
        design_id=f"sidewall_{surface}_rotated",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="sensor",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface=surface,
                    center=Point2(x=3.0, y=20.0),
                ),
                rotation_z_deg=90,
            ),
        ),
    )

    layout = resolve_layout(spec)

    resolved = layout.hardware[0]
    projected = layout.openings[0]
    assert (resolved.normal.x, resolved.normal.y, resolved.normal.z) == normal
    assert (
        projected.world_center.x,
        projected.world_center.y,
        projected.world_center.z,
    ) == opening_center
    assert (
        projected.opening.center_u,
        projected.opening.center_v,
    ) == opening_uv


def test_cross_face_opening_automatically_anchors_to_wall_and_projects_to_outer_plane() -> None:
    profile = envelope_profile("front_board", length=20.0).model_copy(
        update={
            "openings": (
                ProfileCircularOpening(
                    opening_id="usb",
                    center=Point2(x=0.0, y=0.0),
                    diameter=4.0,
                    preferred_face=Face.FRONT,
                ),
            )
        }
    )
    spec = CadBuildSpec(
        design_id="cross_face_auto",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="front_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="base_floor"),
            ),
        ),
    )

    layout = resolve_layout(spec)
    item = layout.hardware[0]
    opening = layout.openings[0]

    assert item.bounds.min_y <= -spec.enclosure.inner_width_y / 2 + profile.mounting.clearance + 1e-6
    assert opening.world_center.y == pytest.approx(-spec.enclosure.outer_width_y / 2)
    assert opening.opening.face is Face.FRONT
    assert check_status(spec, "profile_opening_wall_clearance") == "pass"


def test_cross_face_opening_explicitly_far_from_wall_fails_validation() -> None:
    profile = envelope_profile("far_board", length=20.0).model_copy(
        update={
            "openings": (
                ProfileCircularOpening(
                    opening_id="usb",
                    center=Point2(x=0.0, y=0.0),
                    diameter=4.0,
                    preferred_face=Face.FRONT,
                ),
            )
        }
    )
    spec = CadBuildSpec(
        design_id="cross_face_far",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="far_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
            ),
        ),
    )

    assert check_status(spec, "profile_opening_wall_clearance") == "fail"


def test_cross_face_opening_uses_profile_local_height_offset() -> None:
    profile = envelope_profile("height_offset_board", length=20.0).model_copy(
        update={
            "openings": (
                ProfileCircularOpening(
                    opening_id="usb",
                    center=Point2(x=0.0, y=0.0),
                    center_z=3.5,
                    diameter=4.0,
                    preferred_face=Face.FRONT,
                ),
            )
        }
    )
    spec = CadBuildSpec(
        design_id="cross_face_height_offset",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="height_offset_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(surface="base_floor"),
            ),
        ),
    )

    layout = resolve_layout(spec)

    assert layout.openings[0].world_center.z == pytest.approx(
        layout.hardware[0].center.z + 3.5
    )


@pytest.mark.parametrize(
    ("rotation", "expected_size"),
    (
        (0, (12.0, 4.0)),
        (90, (4.0, 12.0)),
        (180, (12.0, 4.0)),
        (270, (4.0, 12.0)),
    ),
)
def test_profile_rectangular_opening_swaps_face_size_on_quarter_turn(
    rotation: int,
    expected_size: tuple[float, float],
) -> None:
    profile = envelope_profile("rotated_board", length=20.0).model_copy(
        update={
            "openings": (
                ProfileRectangularOpening(
                    opening_id="slot",
                    center=Point2(x=0.0, y=0.0),
                    size_u=12.0,
                    size_v=4.0,
                    preferred_face=Face.TOP,
                ),
            )
        }
    )
    spec = CadBuildSpec(
        design_id=f"rotated_profile_opening_{rotation}",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="rotated_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
                rotation_z_deg=rotation,
            ),
        ),
    )

    opening = resolve_layout(spec).openings[0].opening

    assert opening.size_u == pytest.approx(expected_size[0])
    assert opening.size_v == pytest.approx(expected_size[1])


@pytest.mark.parametrize("rotation", (0, 90, 180, 270))
def test_envelope_quarter_turn_layout_aabb_matches_rotated_footprint(rotation: int) -> None:
    pytest.importorskip("cadquery", reason="CadQuery is required for the entity AABB check")
    profile = envelope_profile("rotating", length=20.0).model_copy(
        update={"dimensions": Size3(length_x=20.0, width_y=10.0, height_z=4.0)}
    )
    spec = CadBuildSpec(
        design_id=f"envelope_rotation_{rotation}",
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="rotating",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=7.0, y=-5.0),
                ),
                rotation_z_deg=rotation,
            ),
        ),
    )

    layout = resolve_layout(spec)
    item = layout.hardware[0]
    length, width = (20.0, 10.0) if rotation in (0, 180) else (10.0, 20.0)
    assert item.bounds.min_x == pytest.approx(7.0 - length / 2)
    assert item.bounds.max_x == pytest.approx(7.0 + length / 2)
    assert item.bounds.min_y == pytest.approx(-5.0 - width / 2)
    assert item.bounds.max_y == pytest.approx(-5.0 + width / 2)

    entity_bounds = build_geometry(spec, layout).hardware[0].shape.BoundingBox()
    assert entity_bounds.xmin == pytest.approx(item.bounds.min_x)
    assert entity_bounds.xmax == pytest.approx(item.bounds.max_x)
    assert entity_bounds.ymin == pytest.approx(item.bounds.min_y)
    assert entity_bounds.ymax == pytest.approx(item.bounds.max_y)
    assert entity_bounds.zmin == pytest.approx(item.bounds.min_z)
    assert entity_bounds.zmax == pytest.approx(item.bounds.max_z)
