from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from zhangwen.cad_engine.engine import build_cad_artifacts
from zhangwen.cad_engine.layout import resolve_layout
from zhangwen.cad_engine.models import (
    BoxWithLidParameters,
    CadBuildSpec,
    ComponentMountParameters,
    ExternalPlacement,
    HardwareCoordinateSystem,
    HardwareInstance,
    HardwareMounting,
    HardwareMountingStrategy,
    HardwareProfile,
    MountSurface,
    Point2,
    Point3,
    ProfileMountingHole,
    ProfileSource,
    ResolvedMountKind,
    Size3,
    SurfacePlacement,
)
from zhangwen.cad_engine.profiles import (
    unihiker_k10_profile,
    unihiker_ultrasonic_distance_sensor_profile,
)
from zhangwen.cad_engine.validation import validate_design


def empty_box_spec() -> CadBuildSpec:
    return CadBuildSpec(
        design_id="golden_empty_box",
        enclosure=BoxWithLidParameters(
            inner_length_x=70.0,
            inner_width_y=70.0,
            inner_height_z=60.0,
        ),
    )


def k10_spec() -> CadBuildSpec:
    profile = unihiker_k10_profile()
    return CadBuildSpec(
        design_id="golden_k10",
        enclosure=empty_box_spec().enclosure,
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="k10_reference",
                profile_id=profile.profile_id,
                placement=ExternalPlacement(
                    surface="external",
                    center=Point3(x=100.0, y=0.0, z=10.0),
                ),
            ),
        ),
    )


def ultrasonic_spec() -> CadBuildSpec:
    profile = unihiker_ultrasonic_distance_sensor_profile()
    return CadBuildSpec(
        design_id="golden_ultrasonic",
        enclosure=empty_box_spec().enclosure,
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="front_ultrasonic",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="front_inner",
                    center=Point2(x=0.0, y=31.2),
                ),
            ),
        ),
    )


def mixed_spec() -> CadBuildSpec:
    ultrasonic = unihiker_ultrasonic_distance_sensor_profile()
    k10 = unihiker_k10_profile()
    return CadBuildSpec(
        design_id="golden_mixed",
        enclosure=empty_box_spec().enclosure,
        profiles=(ultrasonic, k10),
        hardware=(
            HardwareInstance(
                instance_id="front_ultrasonic",
                profile_id=ultrasonic.profile_id,
                placement=SurfacePlacement(
                    surface="front_inner",
                    center=Point2(x=0.0, y=31.2),
                ),
            ),
            HardwareInstance(
                instance_id="k10_reference",
                profile_id=k10.profile_id,
                placement=ExternalPlacement(
                    surface="external",
                    center=Point3(x=100.0, y=0.0, z=10.0),
                ),
            ),
        ),
    )


def edge_retainer_spec() -> CadBuildSpec:
    profile = HardwareProfile(
        profile_id="semantic_retained_board",
        revision="semantic-v1",
        display_name="Semantic retained board",
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
    return CadBuildSpec(
        design_id="golden_edge_retainer",
        enclosure=empty_box_spec().enclosure,
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="semantic_retained_board",
                profile_id=profile.profile_id,
                placement=SurfacePlacement(
                    surface="base_floor",
                    center=Point2(x=0.0, y=0.0),
                ),
            ),
        ),
    )


def component_mount_spec() -> CadBuildSpec:
    profile = HardwareProfile(
        profile_id="ambient_light_sensor",
        revision="confirmed-v1",
        display_name="Ambient light sensor",
        category="sensor",
        roles=("sensor",),
        dimensions=Size3(length_x=30.0, width_y=22.0, height_z=6.7),
        coordinate_system=HardwareCoordinateSystem(origin="envelope_center"),
        mounting=HardwareMounting(
            mode="external_independent_module",
            preferred_surface=MountSurface.EXTERNAL,
            clearance=0.8,
            strategy=HardwareMountingStrategy.HOLE_FASTENED,
            holes=(
                ProfileMountingHole(
                    hole_id="mount_left",
                    center=Point2(x=-12.0, y=0.0),
                    diameter=3.0,
                ),
                ProfileMountingHole(
                    hole_id="mount_right",
                    center=Point2(x=12.0, y=0.0),
                    diameter=3.0,
                ),
            ),
        ),
        source=ProfileSource.DECLARED,
    )
    parameters = ComponentMountParameters()
    return CadBuildSpec(
        design_id="golden_component_mount",
        template="component_mount",
        template_revision="component-mount.v1",
        component_mount=parameters,
        profiles=(profile,),
        hardware=(
            HardwareInstance(
                instance_id="mounted_xiao",
                profile_id=profile.profile_id,
                placement=ExternalPlacement(
                    surface="external",
                    center=Point3(
                        x=0.0,
                        y=0.0,
                        z=parameters.base_thickness + profile.dimensions.height_z / 2,
                    ),
                ),
            ),
        ),
    )
def test_empty_box_semantic_golden() -> None:
    spec = empty_box_spec()
    layout = resolve_layout(spec)

    assert layout.hardware == ()
    assert layout.openings == ()
    assert validate_design(spec, layout).ok is True


def test_k10_external_semantic_golden() -> None:
    spec = k10_spec()
    layout = resolve_layout(spec)

    assert len(layout.hardware) == 1
    assert layout.hardware[0].rotated_size.model_dump() == {
        "length_x": 83.2,
        "width_y": 51.3,
        "height_z": 10.6,
    }
    assert layout.openings == ()
    assert layout.mounting_holes == ()
    assert validate_design(spec, layout).ok is True


def test_front_ultrasonic_semantic_golden() -> None:
    spec = ultrasonic_spec()
    layout = resolve_layout(spec)

    assert layout.hardware[0].normal.model_dump() == {"x": 0.0, "y": -1.0, "z": 0.0}
    assert [item.opening.diameter for item in layout.openings] == [18.4, 18.4]
    assert [item.opening.center_u for item in layout.openings] == [0.0, 0.0]
    assert [item.opening.center_v for item in layout.openings] == [20.45, 41.95]
    assert len(layout.mounting_holes) == 4
    assert {item.opening.diameter for item in layout.mounting_holes} == {3.0}
    assert len(layout.keepouts) == 2
    assert validate_design(spec, layout).ok is True


def test_mixed_assembly_semantic_golden() -> None:
    spec = mixed_spec()
    layout = resolve_layout(spec)

    assert [item.instance_id for item in layout.hardware] == [
        "front_ultrasonic",
        "k10_reference",
    ]
    assert len(layout.openings) == 2
    assert len(layout.mounting_holes) == 4
    assert validate_design(spec, layout).ok is True


def test_edge_retainer_semantic_golden() -> None:
    spec = edge_retainer_spec()
    layout = resolve_layout(spec)

    assert [mount.kind for mount in layout.mounts] == [
        ResolvedMountKind.SUPPORT_TRAY,
        ResolvedMountKind.SIDE_RETAINER,
        ResolvedMountKind.SIDE_RETAINER,
        ResolvedMountKind.END_STOP,
        ResolvedMountKind.END_STOP,
    ]
    assert [mount.hardware_instance_id for mount in layout.mounts] == [
        "semantic_retained_board"
    ] * 5
    assert validate_design(spec, layout).ok is True


def test_component_mount_semantic_golden() -> None:
    spec = component_mount_spec()
    layout = resolve_layout(spec)

    assert spec.enclosure is None
    assert layout.hardware[0].bounds.min_z == pytest.approx(3.0)
    assert layout.mounts == ()
    assert validate_design(spec, layout).ok is True


@pytest.mark.parametrize(
    ("name", "factory"),
    (
        ("empty", empty_box_spec),
        ("k10", k10_spec),
        ("ultrasonic", ultrasonic_spec),
        ("mixed", mixed_spec),
        ("edge_retainer", edge_retainer_spec),
        ("component_mount", component_mount_spec),
    ),
)
def test_semantic_golden_real_exports(
    name: str,
    factory: Callable[[], CadBuildSpec],
    tmp_path: Path,
) -> None:
    pytest.importorskip("cadquery", reason="CadQuery is required for the real export golden")
    result = build_cad_artifacts(factory(), tmp_path / name)

    assert result.validation.ok is True
    assert {item.name for item in result.output_directory.iterdir()} == {
        "assembly.step",
        "base.step",
        "base.stl",
        "geometry-summary.json",
        "lid.step",
        "lid.stl",
        "manifest.json",
        "parameters.json",
        "preview.glb",
        "profiles.json",
        "validation.json",
    }
    assert (result.output_directory / "assembly.step").stat().st_size > 0
    assert (result.output_directory / "base.stl").stat().st_size > 0
    assert (result.output_directory / "lid.stl").stat().st_size > 0
    assert (result.output_directory / "preview.glb").read_bytes()[:4] == b"glTF"
    if name == "edge_retainer":
        assert len(result.layout.mounts) == 5
        assert result.geometry_summary.parts[0].part_id == "base"
