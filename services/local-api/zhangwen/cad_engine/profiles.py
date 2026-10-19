"""Built-in mechanical profiles and trusted reference geometry identifiers."""

from __future__ import annotations

from zhangwen.cad_engine.models import (
    HardwareCoordinateSystem,
    HardwareModelKind,
    HardwareMounting,
    HardwareMountingStrategy,
    HardwareProfile,
    KeepoutSpec,
    Face,
    MountSurface,
    ProfileCircularOpening,
    ProfileRectangularOpening,
    ProfileMountingHole,
    ProfileSource,
    Size3,
    Point2,
    Point3,
)


def unihiker_k10_profile() -> HardwareProfile:
    """Return the immutable, measured K10 mechanical profile.

    Dimensions mirror the trusted profile from the verified prototype.  The
    model intentionally declares no enclosure fixing or opening: a K10 is an
    independent module unless a future reviewed profile says otherwise.
    """

    return HardwareProfile(
        profile_id="unihiker_k10",
        revision="measured-v1",
        display_name="UNIHIKER K10",
        category="controller",
        roles=("controller", "display", "camera"),
        dimensions=Size3(length_x=83.2, width_y=51.3, height_z=10.6),
        coordinate_system=HardwareCoordinateSystem(
            origin="pcb_center",
            x_axis="length",
            y_axis="width",
            positive_z="component_side",
        ),
        mounting=HardwareMounting(
            mode="external_independent_module",
            preferred_surface=MountSurface.EXTERNAL,
            clearance=0.8,
        ),
        model_kind=HardwareModelKind.UNIHIKER_K10,
        source=ProfileSource.TRUSTED,
    )


def unihiker_ultrasonic_distance_sensor_profile() -> HardwareProfile:
    """Return the measured four-hole, dual-transducer ultrasonic profile."""

    return HardwareProfile(
        profile_id="unihiker_ultrasonic_distance_sensor",
        revision="measured-v1",
        display_name="UNIHIKER ultrasonic distance sensor",
        category="sensor",
        roles=("ultrasonic", "distance_sensor", "sensor"),
        dimensions=Size3(length_x=22.0, width_y=47.0, height_z=20.3),
        coordinate_system=HardwareCoordinateSystem(
            origin="pcb_center",
            x_axis="length",
            y_axis="width",
            positive_z="component_side",
        ),
        mounting=HardwareMounting(
            mode="inner_surface",
            preferred_surface=MountSurface.FRONT_INNER,
            clearance=0.8,
            mating_hardware_face="+Z",
            allowed_enclosure_surfaces=(
                MountSurface.LID_INNER,
                MountSurface.FRONT_INNER,
                MountSurface.BACK_INNER,
                MountSurface.LEFT_INNER,
                MountSurface.RIGHT_INNER,
            ),
            holes=tuple(
                ProfileMountingHole(
                    hole_id=hole_id,
                    center=Point2(x=x, y=y),
                    diameter=3.0,
                    fastener="M3",
                )
                for hole_id, x, y in (
                    ("m3_hole_minus_x_minus_y", -8.6, -21.1),
                    ("m3_hole_minus_x_plus_y", -8.6, 21.1),
                    ("m3_hole_plus_x_minus_y", 8.6, -21.1),
                    ("m3_hole_plus_x_plus_y", 8.6, 21.1),
                )
            ),
        ),
        model_kind=HardwareModelKind.UNIHIKER_ULTRASONIC_DISTANCE_SENSOR,
        source=ProfileSource.TRUSTED,
        openings=tuple(
            ProfileCircularOpening(
                opening_id=opening_id,
                center=Point2(x=0.0, y=y),
                diameter=17.4,
                preferred_face=Face.FRONT,
                clearance=0.5,
            )
            for opening_id, y in (
                ("minus_y_transducer_window", -10.75),
                ("plus_y_transducer_window", 10.75),
            )
        ),
        keepouts=(
            KeepoutSpec(
                keepout_id="transducer_volume",
                center=Point3(x=0.0, y=0.0, z=-1.55),
                size=Size3(length_x=19.0, width_y=38.0, height_z=14.0),
            ),
            KeepoutSpec(
                keepout_id="bottom_connector_volume",
                center=Point3(x=8.25, y=0.0, z=-13.3),
                size=Size3(length_x=7.0, width_y=12.0, height_z=7.0),
            ),
        ),
    )


def xiao_esp32s3_profile() -> HardwareProfile:
    """Return the confirmed XIAO ESP32S3 Sense base-board envelope."""

    return HardwareProfile(
        profile_id="xiao_esp32s3",
        revision="confirmed-v1",
        display_name="Seeed Studio XIAO ESP32S3 Sense",
        category="controller",
        roles=("compute", "wifi", "ble", "usb", "camera", "microphone", "storage"),
        dimensions=Size3(length_x=21.0, width_y=17.8, height_z=4.8),
        coordinate_system=HardwareCoordinateSystem(
            origin="pcb_center",
            x_axis="length",
            y_axis="width",
            positive_z="component_side",
        ),
        mounting=HardwareMounting(
            mode="base_floor",
            preferred_surface=MountSurface.BASE_FLOOR,
            strategy=HardwareMountingStrategy.EDGE_RETAINER,
            clearance=0.6,
            mating_hardware_face="-Z",
            allowed_enclosure_surfaces=(MountSurface.BASE_FLOOR,),
        ),
        source=ProfileSource.TRUSTED,
        openings=(
            ProfileRectangularOpening(
                opening_id="usb_c",
                center=Point2(x=8.6, y=0.0),
                center_z=2.4,
                size_u=10.0,
                size_v=5.6,
                preferred_face=Face.LEFT,
                clearance=0.8,
            ),
        ),
        keepouts=(
            KeepoutSpec(
                keepout_id="top_components",
                center=Point3(x=-2.0, y=0.0, z=2.1),
                size=Size3(length_x=16.0, width_y=13.0, height_z=4.2),
            ),
        ),
    )


def grove_oled_096_profile() -> HardwareProfile:
    """Return the confirmed 40 x 20 mm Grove OLED mechanical profile."""

    return HardwareProfile(
        profile_id="grove_oled_096",
        revision="confirmed-v1",
        display_name="Grove - OLED Display 0.96 inch",
        category="display",
        roles=("display", "ui"),
        dimensions=Size3(length_x=40.0, width_y=20.0, height_z=8.1),
        coordinate_system=HardwareCoordinateSystem(
            origin="pcb_center",
            x_axis="length",
            y_axis="width",
            positive_z="component_side",
        ),
        mounting=HardwareMounting(
            mode="lid_inner",
            preferred_surface=MountSurface.LID_INNER,
            strategy=HardwareMountingStrategy.HOLE_FASTENED,
            clearance=0.7,
            mating_hardware_face="+Z",
            allowed_enclosure_surfaces=(MountSurface.LID_INNER,),
            holes=tuple(
                ProfileMountingHole(
                    hole_id=hole_id,
                    center=Point2(x=x, y=y),
                    diameter=2.1,
                    fastener="M2",
                )
                for hole_id, x, y in (
                    ("m2_hole_left", -20.0, 0.0),
                    ("m2_hole_right_back", 10.0, 10.0),
                    ("m2_hole_right_front", 10.0, -10.0),
                )
            ),
        ),
        source=ProfileSource.TRUSTED,
        openings=(
            ProfileRectangularOpening(
                opening_id="screen_window",
                center=Point2(x=-5.0, y=0.0),
                size_u=26.0,
                size_v=14.5,
                preferred_face=Face.TOP,
                clearance=0.8,
            ),
        ),
        keepouts=(
            KeepoutSpec(
                keepout_id="display_stack",
                center=Point3(x=-5.0, y=0.0, z=2.5),
                size=Size3(length_x=30.0, width_y=17.0, height_z=5.0),
            ),
        ),
    )


def grove_button_profile() -> HardwareProfile:
    """Return the confirmed Grove single-button mechanical profile."""

    return HardwareProfile(
        profile_id="grove_button",
        revision="confirmed-v1",
        display_name="Grove - Button",
        category="sensor",
        roles=("button", "input"),
        dimensions=Size3(length_x=20.0, width_y=20.0, height_z=17.6),
        coordinate_system=HardwareCoordinateSystem(
            origin="pcb_center",
            x_axis="length",
            y_axis="width",
            positive_z="component_side",
        ),
        mounting=HardwareMounting(
            mode="lid_inner",
            preferred_surface=MountSurface.LID_INNER,
            strategy=HardwareMountingStrategy.HOLE_FASTENED,
            clearance=0.7,
            mating_hardware_face="+Z",
            allowed_enclosure_surfaces=(MountSurface.LID_INNER,),
            holes=(
                ProfileMountingHole(
                    hole_id="m2_hole_left",
                    center=Point2(x=-10.0, y=0.0),
                    diameter=2.1,
                    fastener="M2",
                ),
                ProfileMountingHole(
                    hole_id="m2_hole_right",
                    center=Point2(x=10.0, y=0.0),
                    diameter=2.1,
                    fastener="M2",
                ),
            ),
        ),
        source=ProfileSource.TRUSTED,
        openings=(
            ProfileCircularOpening(
                opening_id="button_hole",
                center=Point2(x=0.0, y=0.0),
                diameter=9.0,
                preferred_face=Face.TOP,
                clearance=0.7,
            ),
        ),
        keepouts=(
            KeepoutSpec(
                keepout_id="button_travel",
                center=Point3(x=0.0, y=0.0, z=0.0),
                size=Size3(length_x=20.0, width_y=16.0, height_z=17.6),
            ),
        ),
    )


def trusted_profile(profile_id: str) -> HardwareProfile:
    """Resolve a reviewed profile by its exact identifier."""

    if profile_id == "unihiker_k10":
        return unihiker_k10_profile()
    if profile_id == "unihiker_ultrasonic_distance_sensor":
        return unihiker_ultrasonic_distance_sensor_profile()
    if profile_id == "xiao_esp32s3":
        return xiao_esp32s3_profile()
    if profile_id == "grove_oled_096":
        return grove_oled_096_profile()
    if profile_id == "grove_button":
        return grove_button_profile()
    raise KeyError(f"unknown trusted hardware profile: {profile_id}")


def trusted_profiles() -> tuple[HardwareProfile, ...]:
    return (
        unihiker_k10_profile(),
        unihiker_ultrasonic_distance_sensor_profile(),
        xiao_esp32s3_profile(),
        grove_oled_096_profile(),
        grove_button_profile(),
    )
