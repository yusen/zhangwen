"""Direct CadQuery construction for the supported deterministic geometry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from zhangwen.cad_engine.layout import lid_fastener_centers
from zhangwen.cad_engine.k10_photo_album import build_k10_photo_album_shape
from zhangwen.cad_engine.models import (
    CadBuildSpec,
    CircularOpening,
    Face,
    HardwareModelKind,
    HardwareProfile,
    LayoutResult,
    MountSurface,
    RectangularOpening,
    ResolvedHardware,
)


class CadRuntimeUnavailable(RuntimeError):
    """Raised when the optional OpenCascade-backed runtime is unavailable."""


@dataclass(frozen=True)
class GeometryPart:
    part_id: str
    role: str
    shape: Any
    color_rgba: tuple[float, float, float, float]


@dataclass(frozen=True)
class CadGeometry:
    base: GeometryPart | None = None
    lid: GeometryPart | None = None
    hardware: tuple[GeometryPart, ...] = ()
    printable: tuple[GeometryPart, ...] = ()

    @property
    def printable_parts(self) -> tuple[GeometryPart, ...]:
        if self.printable:
            return self.printable
        return tuple(part for part in (self.base, self.lid) if part is not None)

    @property
    def parts(self) -> tuple[GeometryPart, ...]:
        return (*self.printable_parts, *self.hardware)


def cadquery_available() -> bool:
    try:
        import cadquery  # noqa: F401
    except ImportError:
        return False
    return True


def build_geometry(spec: CadBuildSpec, layout: LayoutResult) -> CadGeometry:
    """Build the enclosure and trusted reference hardware through direct API calls."""

    try:
        import cadquery as cq
    except ImportError as exc:
        raise CadRuntimeUnavailable("CadQuery is required for geometric export") from exc

    if spec.template == "component_mount":
        return _build_component_mount_geometry(cq, spec, layout)
    if spec.template == "freeform_structure":
        return _build_freeform_geometry(cq, spec)
    if spec.template == "unihiker_k10_photo_album":
        return CadGeometry(
            printable=(
                GeometryPart(
                    part_id="part",
                    role="k10_photo_album_printable_part",
                    shape=build_k10_photo_album_shape(cq),
                    color_rgba=(0.318, 0.388, 0.455, 1.0),
                ),
            ),
        )

    base_shape = _build_base(cq, spec)
    lid_shape = _build_lid(cq, spec)
    base_shape = _union_resolved_mounts(cq, layout, base_shape)
    base_shape, lid_shape = _apply_openings(cq, spec, layout, base_shape, lid_shape)

    hardware_parts: list[GeometryPart] = []
    for item in layout.hardware:
        if not item.include_reference_geometry:
            continue
        if item.model_kind is HardwareModelKind.UNIHIKER_K10:
            local_shape = _build_unihiker_k10(cq)
            color = (0.145, 0.388, 0.922, 1.0)
        elif item.model_kind is HardwareModelKind.UNIHIKER_ULTRASONIC_DISTANCE_SENSOR:
            local_shape = _build_unihiker_ultrasonic_distance_sensor(cq)
            color = (0.094, 0.451, 0.298, 1.0)
        else:
            local_shape = (
                cq.Workplane("XY")
                .box(
                    item.rotated_size.length_x,
                    item.rotated_size.width_y,
                    item.rotated_size.height_z,
                )
                .val()
            )
            color = (0.078, 0.722, 0.651, 0.72)
        if item.model_kind is not HardwareModelKind.ENVELOPE and item.rotation_z_deg:
            local_shape = local_shape.rotate(
                (0.0, 0.0, 0.0),
                (0.0, 0.0, 1.0),
                float(item.rotation_z_deg),
            )
        local_shape = _orient_for_surface(local_shape, item)
        local_shape = local_shape.translate((item.center.x, item.center.y, item.center.z))
        hardware_parts.append(
            GeometryPart(
                part_id=item.instance_id,
                role="hardware_reference",
                shape=local_shape,
                color_rgba=color,
            )
        )

    return CadGeometry(
        base=GeometryPart(
            part_id="base",
            role="enclosure_base",
            shape=base_shape,
            color_rgba=(0.318, 0.388, 0.455, 1.0),
        ),
        lid=GeometryPart(
            part_id="lid",
            role="enclosure_lid",
            shape=lid_shape,
            color_rgba=(0.647, 0.725, 0.804, 1.0),
        ),
        hardware=tuple(hardware_parts),
    )


def _build_freeform_geometry(cq: Any, spec: CadBuildSpec) -> CadGeometry:
    recipe = spec.freeform_geometry
    if recipe is None:
        raise ValueError("freeform geometry recipe is missing")
    result: Any | None = None
    for primitive in recipe.primitives:
        shape = _declarative_primitive_shape(cq, primitive)
        if primitive.operation == "add":
            result = shape if result is None else result.fuse(shape)
        else:
            if result is None:
                raise ValueError("freeform geometry cannot start with a cut")
            before = float(result.Volume())
            result = result.cut(shape)
            after = float(result.Volume())
            if before - after <= 1e-6:
                raise ValueError(
                    f"freeform cutter does not intersect the current solid: {primitive.primitive_id}"
                )
            if after <= 1e-6:
                raise ValueError("freeform cutter removes the entire solid")
    if result is None:
        raise ValueError("freeform geometry produced no solid")
    result = result.clean()
    if len(result.Solids()) != 1:
        raise ValueError("freeform geometry must produce exactly one connected solid")
    return CadGeometry(
        printable=(
            GeometryPart(
                part_id="part",
                role="freeform_printable_part",
                shape=result,
                color_rgba=(0.318, 0.388, 0.455, 1.0),
            ),
        ),
    )


def _declarative_primitive_shape(cq: Any, primitive: Any) -> Any:
    if primitive.kind == "cylinder":
        assert primitive.diameter is not None and primitive.height is not None
        shape = (
            cq.Workplane("XY")
            .circle(primitive.diameter / 2)
            .extrude(primitive.height)
            .translate(
                (
                    primitive.center.x,
                    primitive.center.y,
                    primitive.center.z - primitive.height / 2,
                )
            )
            .val()
        )
    else:
        assert primitive.size is not None
        if primitive.kind == "rounded_box":
            shape = _rounded_prism(
                cq,
                primitive.size.length_x,
                primitive.size.width_y,
                primitive.size.height_z,
                primitive.corner_radius,
                z_min=primitive.center.z - primitive.size.height_z / 2,
            ).translate((primitive.center.x, primitive.center.y, 0.0)).val()
        else:
            shape = (
                cq.Workplane("XY")
                .box(
                    primitive.size.length_x,
                    primitive.size.width_y,
                    primitive.size.height_z,
                )
                .translate(
                    (
                        primitive.center.x,
                        primitive.center.y,
                        primitive.center.z,
                    )
                )
                .val()
            )
    if primitive.rotation_z_deg:
        shape = shape.rotate(
            (primitive.center.x, primitive.center.y, primitive.center.z),
            (primitive.center.x, primitive.center.y, primitive.center.z + 1.0),
            float(primitive.rotation_z_deg),
        )
    return shape


def _build_component_mount_geometry(
    cq: Any,
    spec: CadBuildSpec,
    layout: LayoutResult,
) -> CadGeometry:
    parameters = spec.component_mount
    if parameters is None or len(spec.profiles) != 1 or len(layout.hardware) != 1:
        raise ValueError("component mount geometry requires one profile and one instance")
    profile = spec.profiles[0]
    item = layout.hardware[0]
    component_length = item.rotated_size.length_x
    component_width = item.rotated_size.width_y
    inner_length = component_length + parameters.component_clearance * 2
    inner_width = component_width + parameters.component_clearance * 2
    outer_length = inner_length + parameters.edge_margin * 2
    outer_width = inner_width + parameters.edge_margin * 2
    corner_radius = min(
        parameters.corner_radius,
        outer_length / 2 - 0.2,
        outer_width / 2 - 0.2,
    )
    inner_radius = max(0.0, corner_radius - parameters.edge_margin)

    base_shape = _rounded_prism(
        cq,
        outer_length,
        outer_width,
        parameters.base_thickness,
        corner_radius,
        z_min=0.0,
    )
    frame_outer = _rounded_prism(
        cq,
        outer_length,
        outer_width,
        parameters.retainer_height,
        corner_radius,
        z_min=parameters.base_thickness,
    )
    frame_inner = _rounded_prism(
        cq,
        inner_length,
        inner_width,
        parameters.retainer_height + 0.4,
        inner_radius,
        z_min=parameters.base_thickness - 0.2,
    )
    retainer_shape = frame_outer.cut(frame_inner)

    fastener_x = outer_length / 2 - parameters.edge_margin / 2
    fastener_y = outer_width / 2 - parameters.edge_margin / 2
    for x in (-fastener_x, fastener_x):
        for y in (-fastener_y, fastener_y):
            cutter = (
                cq.Workplane("XY")
                .center(x, y)
                .circle(parameters.fastener_hole_diameter / 2)
                .extrude(
                    parameters.base_thickness + parameters.retainer_height + 1.0
                )
                .translate((0.0, 0.0, -0.5))
                .val()
            )
            base_shape = base_shape.cut(cutter)
            retainer_shape = retainer_shape.cut(cutter)

    for hole in profile.mounting.holes:
        x, y = _rotate_xy(hole.center.x, hole.center.y, item.rotation_z_deg)
        cutter = (
            cq.Workplane("XY")
            .center(x, y)
            .circle(hole.diameter / 2)
            .extrude(parameters.base_thickness + 1.0)
            .translate((0.0, 0.0, -0.5))
            .val()
        )
        base_shape = base_shape.cut(cutter)

    reference_shape, reference_color = _hardware_reference_shape(cq, item, profile)
    reference_shape = _orient_for_surface(reference_shape, item)
    reference_shape = reference_shape.translate((item.center.x, item.center.y, item.center.z))
    return CadGeometry(
        base=GeometryPart(
            part_id="base",
            role="component_mount_base",
            shape=base_shape.clean().val(),
            color_rgba=(0.318, 0.388, 0.455, 1.0),
        ),
        lid=GeometryPart(
            part_id="lid",
            role="component_mount_retainer",
            shape=retainer_shape.clean().val(),
            color_rgba=(0.647, 0.725, 0.804, 1.0),
        ),
        hardware=(
            GeometryPart(
                part_id=item.instance_id,
                role="hardware_reference",
                shape=reference_shape,
                color_rgba=reference_color,
            ),
        ),
    )


def _hardware_reference_shape(
    cq: Any,
    item: ResolvedHardware,
    profile: HardwareProfile | None = None,
) -> tuple[Any, tuple[float, float, float, float]]:
    if item.model_kind is HardwareModelKind.UNIHIKER_K10:
        shape = _build_unihiker_k10(cq)
        color = (0.145, 0.388, 0.922, 1.0)
    elif item.model_kind is HardwareModelKind.UNIHIKER_ULTRASONIC_DISTANCE_SENSOR:
        shape = _build_unihiker_ultrasonic_distance_sensor(cq)
        color = (0.094, 0.451, 0.298, 1.0)
    else:
        shape = (
            cq.Workplane("XY")
            .box(
                item.rotated_size.length_x,
                item.rotated_size.width_y,
                item.rotated_size.height_z,
            )
            .val()
        )
        if profile is not None:
            for hole in profile.mounting.holes:
                x, y = _rotate_xy(hole.center.x, hole.center.y, item.rotation_z_deg)
                cutter = (
                    cq.Workplane("XY")
                    .center(x, y)
                    .circle(hole.diameter / 2)
                    .extrude(item.rotated_size.height_z + 1.0, both=True)
                    .val()
                )
                shape = shape.cut(cutter)
        color = (0.078, 0.722, 0.651, 0.72)
    if item.model_kind is not HardwareModelKind.ENVELOPE and item.rotation_z_deg:
        shape = shape.rotate(
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            float(item.rotation_z_deg),
        )
    return shape, color


def _rotate_xy(x: float, y: float, rotation_deg: int) -> tuple[float, float]:
    if rotation_deg == 90:
        return -y, x
    if rotation_deg == 180:
        return -x, -y
    if rotation_deg == 270:
        return y, -x
    return x, y


def assembly_compound(geometry: CadGeometry) -> Any:
    try:
        import cadquery as cq
    except ImportError as exc:
        raise CadRuntimeUnavailable("CadQuery is required for geometric export") from exc
    return cq.Compound.makeCompound([part.shape for part in geometry.parts])


def _build_base(cq: Any, spec: CadBuildSpec) -> Any:
    enclosure = spec.enclosure
    if enclosure is None:
        raise ValueError("box base requires enclosure parameters")
    outer = _rounded_prism(
        cq,
        enclosure.outer_length_x,
        enclosure.outer_width_y,
        enclosure.base_height_z,
        enclosure.corner_radius,
        z_min=0.0,
    )
    inner_radius = max(0.0, enclosure.corner_radius - enclosure.wall_thickness)
    inner = _rounded_prism(
        cq,
        enclosure.inner_length_x,
        enclosure.inner_width_y,
        enclosure.inner_height_z + 0.5,
        inner_radius,
        z_min=enclosure.floor_thickness,
    )
    base = outer.cut(inner)

    fasteners = enclosure.lid_fasteners
    if fasteners.enabled:
        post_height = enclosure.inner_height_z - fasteners.top_clearance
        for center in lid_fastener_centers(spec):
            post = _hollow_cylinder(
                cq,
                outer_diameter=fasteners.post_outer_diameter,
                bore_diameter=fasteners.hole_diameter,
                height=post_height + 0.05,
                x=center.x,
                y=center.y,
                z_min=enclosure.floor_thickness - 0.05,
            )
            base = base.union(post)

    for standoff in spec.standoffs:
        post = _hollow_cylinder(
            cq,
            outer_diameter=standoff.outer_diameter,
            bore_diameter=standoff.bore_diameter,
            height=standoff.height + 0.05,
            x=standoff.center.x,
            y=standoff.center.y,
            z_min=enclosure.floor_thickness - 0.05,
        )
        base = base.union(post)
    return base.clean().val()


def _build_lid(cq: Any, spec: CadBuildSpec) -> Any:
    enclosure = spec.enclosure
    if enclosure is None:
        raise ValueError("box lid requires enclosure parameters")
    plate = _rounded_prism(
        cq,
        enclosure.outer_length_x,
        enclosure.outer_width_y,
        enclosure.lid_thickness,
        enclosure.corner_radius,
        z_min=enclosure.base_height_z,
    )
    lip_outer_length = enclosure.inner_length_x - enclosure.lid_clearance * 2
    lip_outer_width = enclosure.inner_width_y - enclosure.lid_clearance * 2
    lip_inner_length = lip_outer_length - enclosure.lid_lip_thickness * 2
    lip_inner_width = lip_outer_width - enclosure.lid_lip_thickness * 2
    lip_outer_radius = max(0.0, enclosure.corner_radius - enclosure.wall_thickness)
    lip_inner_radius = max(0.0, lip_outer_radius - enclosure.lid_lip_thickness)
    lip_outer = _rounded_prism(
        cq,
        lip_outer_length,
        lip_outer_width,
        enclosure.lid_lip_height,
        lip_outer_radius,
        z_min=enclosure.base_height_z - enclosure.lid_lip_height,
    )
    lip_inner = _rounded_prism(
        cq,
        lip_inner_length,
        lip_inner_width,
        enclosure.lid_lip_height + 0.4,
        lip_inner_radius,
        z_min=enclosure.base_height_z - enclosure.lid_lip_height - 0.2,
    )
    lid = plate.union(lip_outer.cut(lip_inner))

    fasteners = enclosure.lid_fasteners
    if fasteners.enabled:
        cutter_height = enclosure.lid_thickness + enclosure.lid_lip_height + 2.0
        cutter_z = enclosure.base_height_z - enclosure.lid_lip_height - 1.0
        for center in lid_fastener_centers(spec):
            cutter = (
                cq.Workplane("XY")
                .center(center.x, center.y)
                .circle(fasteners.hole_diameter / 2)
                .extrude(cutter_height)
                .translate((0.0, 0.0, cutter_z))
            )
            lid = lid.cut(cutter)
    return lid.clean().val()


def _union_resolved_mounts(cq: Any, layout: LayoutResult, base: Any) -> Any:
    fusion_overlap = 0.05
    for mount in layout.mounts:
        shape = (
            cq.Workplane("XY")
            .box(
                mount.size.length_x,
                mount.size.width_y,
                mount.size.height_z + fusion_overlap,
            )
            .val()
            .translate(
                (
                    mount.center.x,
                    mount.center.y,
                    mount.center.z - fusion_overlap / 2,
                )
            )
        )
        base = base.fuse(shape)
    return base.clean()


def _apply_openings(
    cq: Any,
    spec: CadBuildSpec,
    layout: LayoutResult,
    base: Any,
    lid: Any,
) -> tuple[Any, Any]:
    generated = tuple(item.opening for item in layout.openings) + tuple(
        item.opening for item in layout.mounting_holes
    )
    for opening in (*spec.openings, *generated):
        cutter = _opening_cutter(cq, spec, opening)
        if opening.face is Face.TOP:
            lid = lid.cut(cutter.val())
        else:
            base = base.cut(cutter.val())
    return base.clean(), lid.clean()


def _orient_for_surface(shape: Any, item: ResolvedHardware) -> Any:
    if item.surface is MountSurface.LID_INNER:
        return shape.rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 180.0)
    if item.surface is MountSurface.FRONT_INNER:
        return shape.rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), 90.0)
    if item.surface is MountSurface.BACK_INNER:
        return shape.rotate((0.0, 0.0, 0.0), (1.0, 0.0, 0.0), -90.0)
    if item.surface is MountSurface.LEFT_INNER:
        return shape.rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), -90.0)
    if item.surface is MountSurface.RIGHT_INNER:
        return shape.rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 90.0)
    return shape


def _opening_cutter(
    cq: Any,
    spec: CadBuildSpec,
    opening: CircularOpening | RectangularOpening,
) -> Any:
    enclosure = spec.enclosure
    if opening.face in (Face.TOP, Face.BOTTOM):
        plane = "XY"
        depth = max(enclosure.floor_thickness, enclosure.lid_thickness + enclosure.lid_lip_height) + 4
        normal_translation = (
            0.0,
            0.0,
            enclosure.base_height_z + enclosure.lid_thickness / 2
            if opening.face is Face.TOP
            else enclosure.floor_thickness / 2,
        )
    elif opening.face in (Face.LEFT, Face.RIGHT):
        plane = "YZ"
        depth = enclosure.wall_thickness * 2 + 4
        normal_translation = (
            -enclosure.outer_length_x / 2
            if opening.face is Face.LEFT
            else enclosure.outer_length_x / 2,
            0.0,
            0.0,
        )
    else:
        plane = "XZ"
        depth = enclosure.wall_thickness * 2 + 4
        normal_translation = (
            0.0,
            -enclosure.outer_width_y / 2
            if opening.face is Face.FRONT
            else enclosure.outer_width_y / 2,
            0.0,
        )

    if isinstance(opening, CircularOpening):
        cutter = (
            cq.Workplane(plane)
            .center(opening.center_u, opening.center_v)
            .circle(opening.diameter / 2)
            .extrude(depth, both=True)
        )
    else:
        cutter = _rounded_rectangle_on_plane(
            cq,
            plane=plane,
            center_u=opening.center_u,
            center_v=opening.center_v,
            size_u=opening.size_u,
            size_v=opening.size_v,
            radius=opening.corner_radius,
            depth=depth,
        )
    return cutter.translate(normal_translation)


def _rounded_rectangle_on_plane(
    cq: Any,
    *,
    plane: str,
    center_u: float,
    center_v: float,
    size_u: float,
    size_v: float,
    radius: float,
    depth: float,
) -> Any:
    if radius <= 0:
        return (
            cq.Workplane(plane)
            .center(center_u, center_v)
            .rect(size_u, size_v)
            .extrude(depth, both=True)
        )
    horizontal = (
        cq.Workplane(plane)
        .center(center_u, center_v)
        .rect(size_u - radius * 2, size_v)
        .extrude(depth, both=True)
    )
    vertical = (
        cq.Workplane(plane)
        .center(center_u, center_v)
        .rect(size_u, size_v - radius * 2)
        .extrude(depth, both=True)
    )
    cutter = horizontal.union(vertical)
    for offset_u in (-size_u / 2 + radius, size_u / 2 - radius):
        for offset_v in (-size_v / 2 + radius, size_v / 2 - radius):
            corner = (
                cq.Workplane(plane)
                .center(center_u + offset_u, center_v + offset_v)
                .circle(radius)
                .extrude(depth, both=True)
            )
            cutter = cutter.union(corner)
    return cutter


def _rounded_prism(
    cq: Any,
    length: float,
    width: float,
    height: float,
    radius: float,
    *,
    z_min: float,
) -> Any:
    part = cq.Workplane("XY").box(length, width, height, centered=(True, True, False))
    effective_radius = min(radius, length / 2 - 0.2, width / 2 - 0.2)
    if effective_radius > 0:
        part = part.edges("|Z").fillet(effective_radius)
    return part.translate((0.0, 0.0, z_min))


def _hollow_cylinder(
    cq: Any,
    *,
    outer_diameter: float,
    bore_diameter: float,
    height: float,
    x: float,
    y: float,
    z_min: float,
) -> Any:
    return (
        cq.Workplane("XY")
        .center(x, y)
        .circle(outer_diameter / 2)
        .circle(bore_diameter / 2)
        .extrude(height)
        .translate((0.0, 0.0, z_min))
    )


def _build_unihiker_ultrasonic_distance_sensor(cq: Any) -> Any:
    """Build the reviewed 22 x 47 x 20.3 mm ultrasonic reference geometry."""

    pcb_length = 22.0
    pcb_width = 47.0
    pcb_thickness = 1.6
    pcb = _rounded_prism(
        cq,
        pcb_length,
        pcb_width,
        pcb_thickness,
        2.0,
        z_min=0.0,
    )
    for x in (-8.6, 8.6):
        for y in (-21.1, 21.1):
            cutter = (
                cq.Workplane("XY")
                .center(x, y)
                .circle(1.5)
                .extrude(pcb_thickness + 1.0)
                .translate((0.0, 0.0, -0.5))
            )
            pcb = pcb.cut(cutter)

    connector = (
        cq.Workplane("XY")
        .box(5.5, 10.0, 6.3, centered=(True, True, True))
        .translate((8.25, 0.0, -3.15))
        .val()
    )
    transducers = tuple(
        cq.Workplane("XY")
        .center(0.0, y)
        .circle(8.2)
        .extrude(12.4)
        .translate((0.0, 0.0, pcb_thickness))
        .val()
        for y in (-10.75, 10.75)
    )
    result = cq.Compound.makeCompound((pcb.val(), connector, *transducers))

    # Original measured extrema are -6.3 and +14.0 on local Z.
    return result.translate((0.0, 0.0, -3.85))


def _build_unihiker_k10(cq: Any) -> Any:
    """Build the reviewed K10 reference shape, centered on its full envelope."""

    pcb_length = 83.2
    pcb_width = 51.3
    pcb_thickness = 1.6
    pcb_radius = 1.0
    pcb = _rounded_prism(cq, pcb_length, pcb_width, pcb_thickness, pcb_radius, z_min=0.0).val()

    display_frame_length = 71.0
    display_frame_width = 51.0
    display_frame_height = 4.0
    display_frame_center_x = -pcb_length / 2 + 5.5 + display_frame_length / 2
    display_frame = (
        cq.Workplane("XY")
        .box(display_frame_length, display_frame_width, display_frame_height, centered=(True, True, False))
        .translate((display_frame_center_x, 0.0, pcb_thickness))
    )
    display_area_length = 57.5
    display_area_width = 43.0
    display_frame_min_x = display_frame_center_x - display_frame_length / 2
    display_area_center_x = display_frame_min_x + 10.0 + display_area_length / 2
    display_surface_z = pcb_thickness + display_frame_height - 1.0
    display_recess = (
        cq.Workplane("XY")
        .box(display_area_length, display_area_width, 1.2, centered=(True, True, False))
        .translate((display_area_center_x, 0.0, display_surface_z))
    )
    display_frame = display_frame.cut(display_recess).val()
    display_surface = (
        cq.Workplane("XY")
        .box(display_area_length, display_area_width, 0.12, centered=(True, True, False))
        .translate((display_area_center_x, 0.0, display_surface_z))
        .val()
    )

    camera_x = -12.0
    camera_block = (
        cq.Workplane("XY")
        .box(8.0, 8.0, 2.5, centered=(True, True, False))
        .translate((camera_x, 0.0, -2.5))
        .val()
    )
    camera_cylinder = (
        cq.Workplane("XY")
        .circle(4.0)
        .extrude(2.5)
        .translate((camera_x, 0.0, -5.0))
    )
    lens_recess = (
        cq.Workplane("XY")
        .circle(1.25)
        .extrude(1.2)
        .translate((camera_x, 0.0, -5.0))
    )
    camera_cylinder = camera_cylinder.cut(lens_recess).val()
    lens_surface = (
        cq.Workplane("XY")
        .circle(1.25)
        .extrude(0.08)
        .translate((camera_x, 0.0, -4.0))
        .val()
    )

    gold_length = 7.0
    gold_center_x = pcb_length / 2 - gold_length / 2
    top_gold = _rounded_prism(
        cq,
        gold_length,
        pcb_width,
        0.06,
        pcb_radius,
        z_min=pcb_thickness,
    ).translate((gold_center_x, 0.0, 0.0)).val()
    bottom_gold = _rounded_prism(
        cq,
        gold_length,
        pcb_width,
        0.06,
        pcb_radius,
        z_min=-0.06,
    ).translate((gold_center_x, 0.0, 0.0)).val()

    compound = cq.Compound.makeCompound(
        [
            pcb,
            top_gold,
            bottom_gold,
            display_frame,
            display_surface,
            camera_block,
            camera_cylinder,
            lens_surface,
        ]
    )
    # The source origin is the PCB mid-plane convention.  Shift 0.3 mm so the
    # trusted 10.6 mm envelope is centered on local Z for placement and AABB use.
    return compound.translate((0.0, 0.0, -0.3))
