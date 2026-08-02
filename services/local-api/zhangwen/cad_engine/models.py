"""Strict boundary models for the deterministic CAD engine.

The build specification is intentionally declarative.  It contains dimensions,
placements, and trusted model identifiers only; there is no field that can carry
source text, a command, a URL, or a filesystem location.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


IDENTIFIER_PATTERN = r"^[a-z][a-z0-9_-]{0,63}$"
MAX_MODEL_SIZE_MM = 800.0


class CadEngineModel(BaseModel):
    """Base for all engine boundary models."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class Point2(CadEngineModel):
    x: float = Field(ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    y: float = Field(ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)


class Point3(CadEngineModel):
    x: float = Field(ge=-MAX_MODEL_SIZE_MM * 2, le=MAX_MODEL_SIZE_MM * 2)
    y: float = Field(ge=-MAX_MODEL_SIZE_MM * 2, le=MAX_MODEL_SIZE_MM * 2)
    z: float = Field(ge=-MAX_MODEL_SIZE_MM * 2, le=MAX_MODEL_SIZE_MM * 2)


class Size3(CadEngineModel):
    length_x: float = Field(gt=0, le=MAX_MODEL_SIZE_MM)
    width_y: float = Field(gt=0, le=MAX_MODEL_SIZE_MM)
    height_z: float = Field(gt=0, le=MAX_MODEL_SIZE_MM)


class DeclarativePrimitive(CadEngineModel):
    """One bounded, non-executable primitive compiled from natural language."""

    primitive_id: str = Field(pattern=IDENTIFIER_PATTERN)
    operation: Literal["add", "cut"] = "add"
    kind: Literal["box", "rounded_box", "cylinder"]
    center: Point3
    size: Size3 | None = None
    diameter: float | None = Field(default=None, gt=0, le=MAX_MODEL_SIZE_MM)
    height: float | None = Field(default=None, gt=0, le=MAX_MODEL_SIZE_MM)
    corner_radius: float = Field(default=0.0, ge=0.0, le=100.0)
    rotation_z_deg: Literal[0, 90, 180, 270] = 0
    role: Literal["body", "pcb", "connector", "sensor", "feature"] = "body"

    @model_validator(mode="after")
    def validate_shape_fields(self) -> "DeclarativePrimitive":
        if self.kind in {"box", "rounded_box"}:
            if self.size is None or self.diameter is not None or self.height is not None:
                raise ValueError("box primitive requires size and forbids diameter/height")
            shortest = min(self.size.length_x, self.size.width_y)
            if self.kind == "box" and self.corner_radius != 0:
                raise ValueError("box primitive cannot declare a corner radius")
            if self.kind == "rounded_box" and self.corner_radius >= shortest / 2:
                raise ValueError("rounded box radius must be smaller than half its footprint")
            half_extents = (
                self.size.length_x / 2,
                self.size.width_y / 2,
                self.size.height_z / 2,
            )
        else:
            if self.size is not None or self.diameter is None or self.height is None:
                raise ValueError("cylinder primitive requires diameter/height and forbids size")
            if self.corner_radius != 0 or self.rotation_z_deg != 0:
                raise ValueError("cylinder primitive does not support corner radius or rotation")
            half_extents = (self.diameter / 2, self.diameter / 2, self.height / 2)
        for coordinate, half_extent in zip(
            (self.center.x, self.center.y, self.center.z),
            half_extents,
            strict=True,
        ):
            if abs(coordinate) + half_extent > MAX_MODEL_SIZE_MM:
                raise ValueError("declarative primitive exceeds the supported model bounds")
        return self


class DeclarativeGeometry(CadEngineModel):
    """Ordered single-result CSG recipe; the first primitive establishes the solid."""

    primitives: tuple[DeclarativePrimitive, ...] = Field(min_length=1, max_length=32)

    @model_validator(mode="after")
    def validate_recipe(self) -> "DeclarativeGeometry":
        identifiers = [item.primitive_id for item in self.primitives]
        if len(set(identifiers)) != len(identifiers):
            raise ValueError("declarative primitive identifiers must be unique")
        if self.primitives[0].operation != "add":
            raise ValueError("declarative geometry must start with an additive primitive")
        return self


class PreviewDeclarativeGeometry(DeclarativeGeometry):
    """Hardware preview cache bound to one normalized natural description."""

    # None is accepted only so immutable snapshots written before CAD-005 remain
    # readable. The preview endpoint treats it as stale and every newly compiled
    # cache always writes a concrete description hash.
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class Face(StrEnum):
    TOP = "top"
    BOTTOM = "bottom"
    LEFT = "left"
    RIGHT = "right"
    FRONT = "front"
    BACK = "back"


class MountSurface(StrEnum):
    BASE_FLOOR = "base_floor"
    LID_INNER = "lid_inner"
    LID_OUTER = "lid_outer"
    FRONT_INNER = "front_inner"
    BACK_INNER = "back_inner"
    LEFT_INNER = "left_inner"
    RIGHT_INNER = "right_inner"
    EXTERNAL = "external"


class HardwareModelKind(StrEnum):
    ENVELOPE = "envelope"
    UNIHIKER_K10 = "unihiker_k10"
    UNIHIKER_ULTRASONIC_DISTANCE_SENSOR = "unihiker_ultrasonic_distance_sensor"


class HardwareMountingStrategy(StrEnum):
    NONE = "none"
    HOLE_FASTENED = "hole_fastened"
    EDGE_RETAINER = "edge_retainer"


class ResolvedMountKind(StrEnum):
    SUPPORT_TRAY = "support_tray"
    SIDE_RETAINER = "side_retainer"
    END_STOP = "end_stop"


class ProfileSource(StrEnum):
    DECLARED = "declared"
    TRUSTED = "trusted"


class ValidationStatus(StrEnum):
    PASS = "pass"
    WARNING = "warning"
    FAIL = "fail"


class LidFastenerPattern(CadEngineModel):
    enabled: bool = True
    post_outer_diameter: float = Field(default=8.0, ge=4.0, le=20.0)
    hole_diameter: float = Field(default=2.4, ge=1.0, le=8.0)
    edge_inset: float = Field(default=8.0, ge=3.0, le=40.0)
    top_clearance: float = Field(default=0.4, ge=0.1, le=4.0)

    @model_validator(mode="after")
    def validate_radial_wall(self) -> "LidFastenerPattern":
        if self.hole_diameter >= self.post_outer_diameter:
            raise ValueError("lid fastener hole must be smaller than its post")
        if self.edge_inset < self.post_outer_diameter / 2:
            raise ValueError("lid fastener edge inset cannot place a post outside the cavity")
        return self


class BoxWithLidParameters(CadEngineModel):
    inner_length_x: float = Field(default=100.0, ge=30.0, le=MAX_MODEL_SIZE_MM)
    inner_width_y: float = Field(default=70.0, ge=30.0, le=MAX_MODEL_SIZE_MM)
    inner_height_z: float = Field(default=40.0, ge=12.0, le=400.0)
    wall_thickness: float = Field(default=2.4, ge=0.8, le=12.0)
    floor_thickness: float = Field(default=2.4, ge=0.8, le=12.0)
    lid_thickness: float = Field(default=3.0, ge=0.8, le=12.0)
    lid_lip_height: float = Field(default=4.0, ge=1.0, le=20.0)
    lid_lip_thickness: float = Field(default=1.6, ge=0.8, le=8.0)
    lid_clearance: float = Field(default=0.35, ge=0.1, le=2.0)
    corner_radius: float = Field(default=5.0, ge=0.0, le=40.0)
    min_wall_thickness: float = Field(default=1.6, ge=0.8, le=6.0)
    hardware_gap: float = Field(default=5.0, ge=0.0, le=30.0)
    edge_clearance: float = Field(default=8.0, ge=0.0, le=40.0)
    lid_fasteners: LidFastenerPattern = Field(default_factory=LidFastenerPattern)

    @model_validator(mode="after")
    def validate_geometry_ranges(self) -> "BoxWithLidParameters":
        outer_length = self.inner_length_x + self.wall_thickness * 2
        outer_width = self.inner_width_y + self.wall_thickness * 2
        if self.corner_radius >= min(outer_length, outer_width) / 2:
            raise ValueError("corner radius must be smaller than half the outer footprint")
        lip_outer_length = self.inner_length_x - self.lid_clearance * 2
        lip_outer_width = self.inner_width_y - self.lid_clearance * 2
        if min(lip_outer_length, lip_outer_width) <= self.lid_lip_thickness * 2:
            raise ValueError("lid lip leaves no open interior")
        fasteners = self.lid_fasteners
        if fasteners.enabled:
            if fasteners.edge_inset + fasteners.post_outer_diameter / 2 >= min(
                self.inner_length_x,
                self.inner_width_y,
            ) / 2:
                raise ValueError("lid fastener pattern does not fit the inner footprint")
            if fasteners.top_clearance >= self.inner_height_z:
                raise ValueError("lid fastener top clearance exceeds the cavity height")
        return self

    @property
    def outer_length_x(self) -> float:
        return self.inner_length_x + self.wall_thickness * 2

    @property
    def outer_width_y(self) -> float:
        return self.inner_width_y + self.wall_thickness * 2

    @property
    def base_height_z(self) -> float:
        return self.floor_thickness + self.inner_height_z

    @property
    def overall_height_z(self) -> float:
        return self.base_height_z + self.lid_thickness


class ComponentMountParameters(CadEngineModel):
    """Bounded parameters for a structure derived from one hardware profile."""

    base_thickness: float = Field(default=3.0, ge=1.2, le=12.0)
    edge_margin: float = Field(default=7.0, ge=4.0, le=30.0)
    component_clearance: float = Field(default=0.8, ge=0.2, le=5.0)
    retainer_height: float = Field(default=3.0, ge=1.0, le=20.0)
    fastener_hole_diameter: float = Field(default=3.2, ge=1.5, le=8.0)
    corner_radius: float = Field(default=3.0, ge=0.0, le=20.0)

    @model_validator(mode="after")
    def validate_fastener_band(self) -> "ComponentMountParameters":
        if self.fastener_hole_diameter + 1.6 > self.edge_margin:
            raise ValueError("component mount edge margin leaves too little fastener wall")
        return self


class StandoffSpec(CadEngineModel):
    standoff_id: str = Field(pattern=IDENTIFIER_PATTERN)
    center: Point2
    outer_diameter: float = Field(ge=3.0, le=20.0)
    bore_diameter: float = Field(ge=0.8, le=10.0)
    height: float = Field(ge=1.0, le=100.0)
    supports_instance_id: str | None = Field(default=None, pattern=IDENTIFIER_PATTERN)

    @model_validator(mode="after")
    def validate_bore(self) -> "StandoffSpec":
        if self.bore_diameter >= self.outer_diameter:
            raise ValueError("standoff bore must be smaller than its outer diameter")
        return self


class CircularOpening(CadEngineModel):
    kind: Literal["circle"] = "circle"
    opening_id: str = Field(pattern=IDENTIFIER_PATTERN)
    face: Face
    center_u: float = Field(ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    center_v: float = Field(ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    diameter: float = Field(ge=0.8, le=200.0)


class RectangularOpening(CadEngineModel):
    kind: Literal["rectangle"] = "rectangle"
    opening_id: str = Field(pattern=IDENTIFIER_PATTERN)
    face: Face
    center_u: float = Field(ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    center_v: float = Field(ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    size_u: float = Field(ge=0.8, le=400.0)
    size_v: float = Field(ge=0.8, le=400.0)
    corner_radius: float = Field(default=0.0, ge=0.0, le=40.0)

    @model_validator(mode="after")
    def validate_corner_radius(self) -> "RectangularOpening":
        if self.corner_radius >= min(self.size_u, self.size_v) / 2:
            raise ValueError("opening corner radius must be smaller than half its shortest side")
        return self


OpeningSpec = Annotated[
    CircularOpening | RectangularOpening,
    Field(discriminator="kind"),
]


class ProfileCircularOpening(CadEngineModel):
    """An opening declared in a hardware profile's local XY plane."""

    kind: Literal["circle"] = "circle"
    opening_id: str = Field(pattern=IDENTIFIER_PATTERN)
    center: Point2
    center_z: float = Field(default=0.0, ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    diameter: float = Field(ge=0.8, le=200.0)
    preferred_face: Face = Face.FRONT
    clearance: float = Field(default=0.0, ge=0.0, le=10.0)


class ProfileRectangularOpening(CadEngineModel):
    """A rectangular opening declared in a hardware profile's local XY plane."""

    kind: Literal["rectangle"] = "rectangle"
    opening_id: str = Field(pattern=IDENTIFIER_PATTERN)
    center: Point2
    center_z: float = Field(default=0.0, ge=-MAX_MODEL_SIZE_MM, le=MAX_MODEL_SIZE_MM)
    size_u: float = Field(ge=0.8, le=400.0)
    size_v: float = Field(ge=0.8, le=400.0)
    corner_radius: float = Field(default=0.0, ge=0.0, le=40.0)
    preferred_face: Face = Face.FRONT
    clearance: float = Field(default=0.0, ge=0.0, le=10.0)

    @model_validator(mode="after")
    def validate_corner_radius(self) -> "ProfileRectangularOpening":
        if self.corner_radius >= min(self.size_u, self.size_v) / 2:
            raise ValueError(
                "profile opening corner radius must be smaller than half its shortest side"
            )
        return self


ProfileOpeningSpec = Annotated[
    ProfileCircularOpening | ProfileRectangularOpening,
    Field(discriminator="kind"),
]


class ProfileMountingHole(CadEngineModel):
    """A fastener hole declared in a hardware profile's local XY plane."""

    hole_id: str = Field(pattern=IDENTIFIER_PATTERN)
    center: Point2
    diameter: float = Field(ge=1.0, le=20.0)
    fastener: str = Field(
        default="M3",
        pattern=r"^[A-Za-z0-9][A-Za-z0-9+_.-]{0,31}$",
    )


class HardwareCoordinateSystem(CadEngineModel):
    origin: Literal["envelope_center", "pcb_center"]
    x_axis: Literal["length"] = "length"
    y_axis: Literal["width"] = "width"
    positive_z: Literal["component_side", "height"] = "height"


class HardwareMounting(CadEngineModel):
    mode: Literal[
        "envelope_only",
        "external_independent_module",
        "base_floor",
        "lid_inner",
        "lid_outer",
        "front_inner",
        "back_inner",
        "left_inner",
        "right_inner",
        "inner_surface",
    ]
    preferred_surface: MountSurface
    strategy: HardwareMountingStrategy = HardwareMountingStrategy.NONE
    clearance: float = Field(default=0.8, ge=0.0, le=10.0)
    mating_hardware_face: Literal["+X", "-X", "+Y", "-Y", "+Z", "-Z"] | None = None
    allowed_enclosure_surfaces: tuple[MountSurface, ...] = Field(default=())
    holes: tuple[ProfileMountingHole, ...] = Field(default=(), max_length=32)

    @model_validator(mode="after")
    def validate_strategy(self) -> "HardwareMounting":
        if self.strategy is HardwareMountingStrategy.HOLE_FASTENED and not self.holes:
            raise ValueError("hole-fastened strategy requires profile mounting holes")
        if self.strategy is HardwareMountingStrategy.EDGE_RETAINER:
            if self.mode != "base_floor" or self.preferred_surface is not MountSurface.BASE_FLOOR:
                raise ValueError("edge retainer requires a base-floor profile")
            if any(
                surface is not MountSurface.BASE_FLOOR
                for surface in self.allowed_enclosure_surfaces
            ):
                raise ValueError("edge retainer may allow only the base-floor surface")
        return self


class KeepoutSpec(CadEngineModel):
    keepout_id: str = Field(pattern=IDENTIFIER_PATTERN)
    center: Point3
    size: Size3


class HardwareProfile(CadEngineModel):
    profile_id: str = Field(pattern=IDENTIFIER_PATTERN)
    revision: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9:._-]{0,159}$")
    display_name: str = Field(min_length=1, max_length=120)
    category: str = Field(pattern=IDENTIFIER_PATTERN)
    roles: tuple[str, ...] = Field(default=(), max_length=16)
    dimensions: Size3
    coordinate_system: HardwareCoordinateSystem
    mounting: HardwareMounting
    model_kind: HardwareModelKind = HardwareModelKind.ENVELOPE
    source: ProfileSource = ProfileSource.DECLARED
    keepouts: tuple[KeepoutSpec, ...] = Field(default=(), max_length=16)
    openings: tuple[ProfileOpeningSpec, ...] = Field(default=(), max_length=32)
    preview_geometry: PreviewDeclarativeGeometry | None = None

    @model_validator(mode="after")
    def validate_trusted_model(self) -> "HardwareProfile":
        if len(set(self.roles)) != len(self.roles):
            raise ValueError("hardware profile roles must be unique")
        trusted_dimensions = {
            "unihiker_k10": (83.2, 51.3, 10.6),
            "unihiker_ultrasonic_distance_sensor": (22.0, 47.0, 20.3),
            "xiao_esp32s3": (21.0, 17.8, 4.8),
            "grove_oled_096": (40.0, 20.0, 8.1),
            "grove_button": (20.0, 20.0, 17.6),
        }
        actual = (
            self.dimensions.length_x,
            self.dimensions.width_y,
            self.dimensions.height_z,
        )
        if self.source is ProfileSource.TRUSTED:
            expected = trusted_dimensions.get(self.profile_id)
            if expected is None:
                raise ValueError("only registered hardware profiles may use a trusted source")
            if any(
                abs(left - right) > 1e-6
                for left, right in zip(actual, expected, strict=True)
            ):
                raise ValueError("trusted hardware dimensions cannot be overridden")
        if self.model_kind is HardwareModelKind.UNIHIKER_K10 and (
            self.profile_id != "unihiker_k10" or self.source is not ProfileSource.TRUSTED
        ):
            raise ValueError("the K10 geometry is available only through its trusted profile")
        if self.model_kind is HardwareModelKind.UNIHIKER_ULTRASONIC_DISTANCE_SENSOR and (
            self.profile_id != "unihiker_ultrasonic_distance_sensor"
            or self.source is not ProfileSource.TRUSTED
        ):
            raise ValueError("the trusted ultrasonic profile cannot be overridden")
        if (
            self.model_kind
            not in {
                HardwareModelKind.ENVELOPE,
                HardwareModelKind.UNIHIKER_K10,
                HardwareModelKind.UNIHIKER_ULTRASONIC_DISTANCE_SENSOR,
            }
            and self.source is not ProfileSource.TRUSTED
        ):
            raise ValueError("registered hardware geometry requires a trusted profile")
        opening_ids = [opening.opening_id for opening in self.openings]
        if len(set(opening_ids)) != len(opening_ids):
            raise ValueError("hardware profile opening identifiers must be unique")
        hole_ids = [hole.hole_id for hole in self.mounting.holes]
        if len(set(hole_ids)) != len(hole_ids):
            raise ValueError("hardware profile mounting hole identifiers must be unique")
        if self.mounting.allowed_enclosure_surfaces and (
            self.mounting.preferred_surface not in self.mounting.allowed_enclosure_surfaces
        ):
            raise ValueError("preferred mounting surface must be allowed by the profile")
        return self


class SurfacePlacement(CadEngineModel):
    surface: Literal[
        "base_floor",
        "lid_inner",
        "lid_outer",
        "front_inner",
        "back_inner",
        "left_inner",
        "right_inner",
    ]
    center: Point2 | None = None


class ExternalPlacement(CadEngineModel):
    surface: Literal["external"]
    center: Point3


HardwarePlacement = Annotated[
    SurfacePlacement | ExternalPlacement,
    Field(discriminator="surface"),
]


class HardwareInstance(CadEngineModel):
    instance_id: str = Field(pattern=IDENTIFIER_PATTERN)
    profile_id: str = Field(pattern=IDENTIFIER_PATTERN)
    placement: HardwarePlacement
    rotation_z_deg: Literal[0, 90, 180, 270] = 0
    include_reference_geometry: bool = True


class CadBuildSpec(CadEngineModel):
    schema_version: Literal["1.0"] = "1.0"
    design_id: str = Field(pattern=IDENTIFIER_PATTERN)
    template: Literal[
        "box_with_lid",
        "component_mount",
        "freeform_structure",
        "unihiker_k10_photo_album",
    ] = "box_with_lid"
    template_revision: str = Field(
        default="box-with-lid-v1",
        pattern=r"^[a-zA-Z0-9][a-zA-Z0-9:._-]{0,159}$",
    )
    units: Literal["mm"] = "mm"
    enclosure: BoxWithLidParameters | None = None
    component_mount: ComponentMountParameters | None = None
    freeform_geometry: DeclarativeGeometry | None = None
    standoffs: tuple[StandoffSpec, ...] = Field(default=(), max_length=32)
    openings: tuple[OpeningSpec, ...] = Field(default=(), max_length=32)
    profiles: tuple[HardwareProfile, ...] = Field(default=(), max_length=32)
    hardware: tuple[HardwareInstance, ...] = Field(default=(), max_length=32)

    @model_validator(mode="before")
    @classmethod
    def apply_template_defaults(cls, value: Any) -> Any:
        if isinstance(value, dict) and value.get("template", "box_with_lid") == "box_with_lid":
            if "enclosure" not in value:
                value = {**value, "enclosure": {}}
        return value

    @model_validator(mode="after")
    def validate_references(self) -> "CadBuildSpec":
        if self.template == "freeform_structure":
            if self.freeform_geometry is None:
                raise ValueError("freeform structure requires declarative geometry")
            if (
                self.enclosure is not None
                or self.component_mount is not None
                or self.standoffs
                or self.openings
                or self.profiles
                or self.hardware
            ):
                raise ValueError("freeform structure cannot include enclosure or hardware features")
        elif self.template == "unihiker_k10_photo_album":
            if (
                self.enclosure is not None
                or self.component_mount is not None
                or self.freeform_geometry is not None
                or self.standoffs
                or self.openings
                or self.profiles
                or self.hardware
            ):
                raise ValueError("K10 photo album template uses fixed local geometry only")
        elif self.template == "component_mount":
            if self.component_mount is None:
                raise ValueError("component mount template requires component_mount parameters")
            if (
                self.enclosure is not None
                or self.freeform_geometry is not None
                or self.standoffs
                or self.openings
            ):
                raise ValueError("component mount template cannot include enclosure features")
            if len(self.profiles) != 1 or len(self.hardware) != 1:
                raise ValueError("component mount template requires exactly one profile and instance")
        else:
            if self.enclosure is None:
                raise ValueError("box template requires enclosure parameters")
            if self.component_mount is not None or self.freeform_geometry is not None:
                raise ValueError("box template cannot include other template parameters")
        profile_ids = [profile.profile_id for profile in self.profiles]
        instance_ids = [instance.instance_id for instance in self.hardware]
        standoff_ids = [standoff.standoff_id for standoff in self.standoffs]
        opening_ids = [opening.opening_id for opening in self.openings]
        for label, identifiers in (
            ("profile", profile_ids),
            ("hardware instance", instance_ids),
            ("standoff", standoff_ids),
            ("opening", opening_ids),
        ):
            if len(set(identifiers)) != len(identifiers):
                raise ValueError(f"duplicate {label} identifier")
        known_profiles = set(profile_ids)
        missing = sorted(
            {instance.profile_id for instance in self.hardware if instance.profile_id not in known_profiles}
        )
        if missing:
            raise ValueError(f"hardware instances reference unknown profiles: {', '.join(missing)}")
        known_instances = set(instance_ids)
        profiles_by_id = {profile.profile_id: profile for profile in self.profiles}
        instances_by_id = {instance.instance_id: instance for instance in self.hardware}
        if self.template == "box_with_lid":
            for instance in self.hardware:
                profile = profiles_by_id[instance.profile_id]
                placement_surface = MountSurface(instance.placement.surface)
                required_surface = {
                    "external_independent_module": MountSurface.EXTERNAL,
                    "base_floor": MountSurface.BASE_FLOOR,
                    "lid_inner": MountSurface.LID_INNER,
                    "lid_outer": MountSurface.LID_OUTER,
                    "front_inner": MountSurface.FRONT_INNER,
                    "back_inner": MountSurface.BACK_INNER,
                    "left_inner": MountSurface.LEFT_INNER,
                    "right_inner": MountSurface.RIGHT_INNER,
                }.get(profile.mounting.mode)
                if required_surface is not None and placement_surface is not required_surface:
                    raise ValueError(
                        f"hardware instance {instance.instance_id} must use "
                        f"mounting surface {required_surface}"
                    )
                if profile.mounting.allowed_enclosure_surfaces and (
                    placement_surface not in profile.mounting.allowed_enclosure_surfaces
                ):
                    raise ValueError(
                        f"hardware instance {instance.instance_id} uses a surface not allowed by profile"
                    )
        missing_support_targets = sorted(
            {
                standoff.supports_instance_id
                for standoff in self.standoffs
                if standoff.supports_instance_id is not None
                and standoff.supports_instance_id not in known_instances
            }
        )
        if missing_support_targets:
            raise ValueError(
                "standoffs reference unknown hardware instances: "
                + ", ".join(missing_support_targets)
            )
        invalid_support_targets = sorted(
            {
                standoff.supports_instance_id
                for standoff in self.standoffs
                if standoff.supports_instance_id is not None
                and MountSurface(instances_by_id[standoff.supports_instance_id].placement.surface)
                is not MountSurface.BASE_FLOOR
            }
        )
        if invalid_support_targets:
            raise ValueError(
                "standoffs may support only base-floor hardware: "
                + ", ".join(invalid_support_targets)
            )
        return self


class Aabb(CadEngineModel):
    min_x: float
    min_y: float
    min_z: float
    max_x: float
    max_y: float
    max_z: float


class ResolvedHardware(CadEngineModel):
    instance_id: str
    profile_id: str
    model_kind: HardwareModelKind
    surface: MountSurface
    center: Point3
    rotated_size: Size3
    rotation_z_deg: Literal[0, 90, 180, 270]
    bounds: Aabb
    include_reference_geometry: bool
    basis_x: Point3 = Field(default_factory=lambda: Point3(x=1.0, y=0.0, z=0.0))
    basis_y: Point3 = Field(default_factory=lambda: Point3(x=0.0, y=1.0, z=0.0))
    normal: Point3 = Field(default_factory=lambda: Point3(x=0.0, y=0.0, z=1.0))


class ResolvedOpening(CadEngineModel):
    opening_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hardware_instance_id: str = Field(pattern=IDENTIFIER_PATTERN)
    opening: OpeningSpec
    world_center: Point3


class ResolvedMountingHole(CadEngineModel):
    hole_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hardware_instance_id: str = Field(pattern=IDENTIFIER_PATTERN)
    opening: CircularOpening
    world_center: Point3


class ResolvedKeepout(CadEngineModel):
    keepout_id: str = Field(pattern=IDENTIFIER_PATTERN)
    hardware_instance_id: str = Field(pattern=IDENTIFIER_PATTERN)
    bounds: Aabb


class ResolvedMount(CadEngineModel):
    mount_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,95}$")
    hardware_instance_id: str = Field(pattern=IDENTIFIER_PATTERN)
    kind: ResolvedMountKind
    center: Point3
    size: Size3
    bounds: Aabb


class LayoutResult(CadEngineModel):
    hardware: tuple[ResolvedHardware, ...]
    openings: tuple[ResolvedOpening, ...] = Field(default=())
    mounting_holes: tuple[ResolvedMountingHole, ...] = Field(default=())
    keepouts: tuple[ResolvedKeepout, ...] = Field(default=())
    mounts: tuple[ResolvedMount, ...] = Field(default=(), max_length=160)
    capacity_violations: tuple[str, ...] = Field(default=(), max_length=32)


class ValidationCheck(CadEngineModel):
    check_id: str = Field(pattern=IDENTIFIER_PATTERN)
    status: ValidationStatus
    message: str = Field(min_length=1, max_length=1000)
    evidence: tuple[str, ...] = Field(default=(), max_length=64)


class ValidationReport(CadEngineModel):
    ok: bool
    checks: tuple[ValidationCheck, ...]


class PartGeometrySummary(CadEngineModel):
    part_id: str = Field(pattern=IDENTIFIER_PATTERN)
    role: str = Field(pattern=IDENTIFIER_PATTERN)
    bounds: Aabb
    volume_mm3: float = Field(ge=0.0)
    solid_count: int = Field(ge=0)


class GeometrySummary(CadEngineModel):
    units: Literal["mm"] = "mm"
    parts: tuple[PartGeometrySummary, ...]
    assembly_bounds: Aabb
    total_volume_mm3: float = Field(ge=0.0)
    preview_triangle_count: int = Field(ge=0)


class ManifestFile(CadEngineModel):
    role: str = Field(pattern=IDENTIFIER_PATTERN)
    file_name: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,127}$")
    mime_type: str = Field(min_length=1, max_length=120)
    byte_size: int = Field(ge=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class ArtifactManifest(CadEngineModel):
    schema_version: Literal["1.0"] = "1.0"
    engine_id: Literal["zhangwen-cad-engine"] = "zhangwen-cad-engine"
    engine_version: str = Field(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$")
    design_id: str = Field(pattern=IDENTIFIER_PATTERN)
    spec_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: tuple[ManifestFile, ...]
