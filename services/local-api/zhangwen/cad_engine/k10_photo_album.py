"""Fixed, audited geometry for the UNIHIKER K10 electronic photo album stand.

The dimensions in this module come from the accepted stage summary under
``references/local/复杂结构件建模的人机交互资料``.  No provider-authored source or path is
executed.  Geometry is constructed with fixed CadQuery API calls in the local
``s/n/y`` frame used by the source material.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any


@dataclass(frozen=True)
class K10PhotoAlbumDimensions:
    base_length_x: float = 52.08
    width_y: float = 83.0
    base_thickness: float = 5.0
    slope_length_s: float = 65.5
    slope_thickness_n: float = 5.0
    slope_angle_deg: float = 60.0
    clip_offset_s: float = 51.5
    clip_perpendicular_thickness_s: float = 4.0
    clip_perpendicular_length_n: float = 15.6
    clip_parallel_length_s: float = 7.8
    clip_parallel_thickness_n: float = 3.0
    square_hole_size: float = 12.0
    square_hole_radius: float = 1.5
    square_hole_center_s: float = 25.75
    square_hole_center_y: float = -19.0
    rear_block_length_s: float = 34.0
    rear_block_width_y: float = 53.0
    rear_block_thickness_n: float = 8.5
    rear_slot_length_s: float = 32.0
    rear_slot_width_y: float = 49.0
    rear_slot_depth_n: float = 6.5
    limiter_notch_diameter: float = 10.0


DIMENSIONS = K10PhotoAlbumDimensions()
JOIN_OVERLAP_MM = 0.05


def build_k10_photo_album_shape(cq: Any) -> Any:
    """Build the final one-piece album stand from fixed additive/cut stages."""

    d = DIMENSIONS
    half_x = d.base_length_x / 2
    half_y = d.width_y / 2
    slope_origin = (
        half_x - d.slope_length_s * math.cos(math.radians(d.slope_angle_deg)),
        0.0,
        d.slope_length_s * math.sin(math.radians(d.slope_angle_deg)),
    )

    # Stages 1-4: base, 60-degree plate, L clip, paired +Y limiters and back cover.
    result = (
        cq.Workplane("XY")
        .box(
            d.base_length_x,
            d.width_y,
            d.base_thickness,
            centered=(True, True, False),
        )
        .val()
    )
    result = result.fuse(
        _local_box(
            cq,
            slope_origin,
            0.0,
            d.slope_length_s,
            -half_y,
            half_y,
            -d.slope_thickness_n,
            JOIN_OVERLAP_MM,
        )
    )
    # The source model anchors the lower slope edge at the base underside.  Its
    # negative-normal tail is intentionally trimmed at Z=0 before later fillets.
    below_build_plane = (
        cq.Workplane("XY")
        .box(200.0, 200.0, 40.0, centered=(True, True, False))
        .translate((0.0, 0.0, -40.0))
        .val()
    )
    result = result.cut(below_build_plane)
    result = result.fuse(
        _local_box(
            cq,
            slope_origin,
            d.clip_offset_s,
            d.clip_offset_s + d.clip_perpendicular_thickness_s,
            -half_y,
            half_y,
            -JOIN_OVERLAP_MM,
            d.clip_perpendicular_length_n,
        )
    )
    result = result.fuse(
        _local_box(
            cq,
            slope_origin,
            d.clip_offset_s - d.clip_parallel_length_s,
            d.clip_offset_s + JOIN_OVERLAP_MM,
            -half_y,
            half_y,
            d.clip_perpendicular_length_n - d.clip_parallel_thickness_n,
            d.clip_perpendicular_length_n,
        )
    )
    for n_min, n_max in ((-JOIN_OVERLAP_MM, 5.9), (7.9, 12.6)):
        result = result.fuse(
            _local_box(
                cq,
                slope_origin,
                0.0,
                51.5,
                34.5,
                41.5,
                n_min,
                n_max,
            )
        )
    result = result.fuse(
        _local_box(
            cq,
            slope_origin,
            -5.0,
            JOIN_OVERLAP_MM,
            34.5,
            41.5,
            -5.0,
            12.6,
        )
    )

    # Stages 6-7: rear support and its top slot.  The 0.05 mm overlaps are
    # deliberate, so tangent faces never create a disconnected printable part.
    result = result.fuse(
        _local_box(
            cq,
            slope_origin,
            1.0,
            35.0,
            -11.5,
            41.5,
            -13.5,
            -5.0 + JOIN_OVERLAP_MM,
        )
    )
    result = result.cut(
        _local_box(
            cq,
            slope_origin,
            0.95,
            33.0,
            -9.5,
            39.5,
            -11.5,
            -5.0 + JOIN_OVERLAP_MM * 2,
        )
    )

    # Stage 9-1: deterministic R8.5 rear transition (box minus a quarter cylinder).
    rear_filler = _local_box(
        cq,
        slope_origin,
        35.0 - JOIN_OVERLAP_MM,
        43.5,
        -11.5,
        41.5,
        -13.5,
        -5.0 + JOIN_OVERLAP_MM,
    )
    rear_quarter_cutter = _local_y_cylinder(
        cq,
        slope_origin,
        center_s=43.5,
        center_n=-13.5,
        y_min=-11.6,
        y_max=41.6,
        radius=8.5,
    )
    result = result.fuse(rear_filler.cut(rear_quarter_cutter))

    # Stages 9-2 and 9-3: every edge treatment is a deterministic polygonal
    # filler/cutter.  Native topology-index fillet selection is intentionally
    # avoided because the selected edge would change after earlier booleans.
    result = result.cut(_base_plus_x_r3_cutter(cq))
    result = result.cut(_base_plus_x_cleanup_cutter(cq))
    result = result.fuse(_base_slope_back_r3_filler(cq, slope_origin))
    result = result.fuse(_clip_lower_r3_filler(cq, slope_origin))
    result = result.cut(_clip_outer_r3_cutter(cq, slope_origin))
    result = result.cut(_base_minus_x_r10_cutters(cq))
    result = result.cut(_slope_minus_y_r10_cutter(cq, slope_origin))

    # Stages 5 and 9-4: the accepted square envelope with four deterministic R1.5
    # inside corners is equivalent to one rounded-rectangle through cutter.
    result = result.cut(
        _local_rounded_box(
            cq,
            slope_origin,
            center_s=d.square_hole_center_s,
            center_y=d.square_hole_center_y,
            s_length=d.square_hole_size,
            y_width=d.square_hole_size,
            n_min=-6.0,
            n_max=1.0,
            radius=d.square_hole_radius,
        )
    )

    # Stage 8: semicircular side notch through the narrow limiter in local n.
    result = result.cut(
        _local_n_cylinder(
            cq,
            slope_origin,
            center_s=19.85,
            center_y=41.5,
            n_min=-0.05,
            n_max=12.65,
            radius=d.limiter_notch_diameter / 2,
        )
    )

    # Stage 9-5: additive R2 transition on the 2 mm +Y edge beside the rear slot.
    result = result.fuse(_rear_slot_plus_y_r2_filler(cq, slope_origin))

    return result.clean()


def _base_plus_x_r3_cutter(cq: Any) -> Any:
    radius = 3.0
    segments = 24
    angle = math.radians(60.0)
    corner_x = DIMENSIONS.base_length_x / 2
    bottom_dir = (-1.0, 0.0)
    slope_dir = (-math.cos(angle), math.sin(angle))
    bisector = (bottom_dir[0] + slope_dir[0], bottom_dir[1] + slope_dir[1])
    length = math.hypot(*bisector)
    bisector = (bisector[0] / length, bisector[1] / length)
    tangent_distance = radius / math.tan(angle / 2)
    center_distance = radius / math.sin(angle / 2)
    center = (
        corner_x + bisector[0] * center_distance,
        bisector[1] * center_distance,
    )
    bottom_tangent = (corner_x - tangent_distance, 0.0)
    slope_tangent = (
        corner_x - math.cos(angle) * tangent_distance,
        math.sin(angle) * tangent_distance,
    )
    start = math.atan2(bottom_tangent[1] - center[1], bottom_tangent[0] - center[0])
    end = math.atan2(slope_tangent[1] - center[1], slope_tangent[0] - center[0])
    slope_bottom_depth = abs(math.cos(angle) * DIMENSIONS.slope_thickness_n)
    slope_bottom_left_x = (
        corner_x
        - math.sin(angle) * DIMENSIONS.slope_thickness_n
        - slope_bottom_depth / math.tan(angle)
    )
    points = [(corner_x, 0.0), (slope_bottom_left_x - 1.0, -0.05), bottom_tangent]
    points.extend(
        (
            center[0] + math.cos(start + (end - start) * index / segments) * radius,
            center[1] + math.sin(start + (end - start) * index / segments) * radius,
        )
        for index in range(1, segments + 1)
    )
    return _world_xz_prism(cq, points, 85.0, 0.0)


def _base_plus_x_cleanup_cutter(cq: Any) -> Any:
    radius = 3.0
    angle = math.radians(60.0)
    corner_x = DIMENSIONS.base_length_x / 2
    tangent_distance = radius / math.tan(angle / 2)
    slope_bottom_depth = abs(math.cos(angle) * DIMENSIONS.slope_thickness_n)
    slope_bottom_left_x = (
        corner_x
        - math.sin(angle) * DIMENSIONS.slope_thickness_n
        - slope_bottom_depth / math.tan(angle)
    )
    x_min = slope_bottom_left_x - 3.0 + 7.0
    x_max = corner_x - tangent_distance + 0.35 + 7.0
    z_max = math.sin(angle) * tangent_distance + 4.0
    return _world_xz_prism(
        cq,
        [(x_min, -1.0), (x_max, -1.0), (x_max, z_max), (x_min, z_max)],
        85.0,
        0.0,
    )


def _base_slope_back_r3_filler(
    cq: Any,
    origin: tuple[float, float, float],
) -> Any:
    radius = 3.0
    segments = 24
    overlap = JOIN_OVERLAP_MM
    angle = math.radians(60.0)
    edge_s = (
        math.sin(angle) * DIMENSIONS.slope_length_s
        - math.cos(angle) * DIMENSIONS.slope_thickness_n
        - DIMENSIONS.base_thickness
    ) / math.sin(angle)
    edge = _surface_point(origin, edge_s, -DIMENSIONS.slope_thickness_n)
    base_dir = (-1.0, 0.0)
    slope_dir = (-math.cos(angle), math.sin(angle))
    bisector = (base_dir[0] + slope_dir[0], base_dir[1] + slope_dir[1])
    length = math.hypot(*bisector)
    bisector = (bisector[0] / length, bisector[1] / length)
    corner_angle = math.acos(base_dir[0] * slope_dir[0] + base_dir[1] * slope_dir[1])
    tangent_distance = radius / math.tan(corner_angle / 2)
    center_distance = radius / math.sin(corner_angle / 2)
    center = (
        edge[0] + bisector[0] * center_distance,
        edge[2] + bisector[1] * center_distance,
    )
    base_tangent = (edge[0] - tangent_distance, edge[2])
    slope_tangent = (
        edge[0] - math.cos(angle) * tangent_distance,
        edge[2] + math.sin(angle) * tangent_distance,
    )
    start = math.atan2(base_tangent[1] - center[1], base_tangent[0] - center[0])
    end = math.atan2(slope_tangent[1] - center[1], slope_tangent[0] - center[0])
    if end < start:
        end += 2 * math.pi
    points = [(edge[0] - bisector[0] * overlap, edge[2] - bisector[1] * overlap), base_tangent]
    points.extend(
        (
            center[0] + math.cos(start + (end - start) * index / segments) * radius,
            center[1] + math.sin(start + (end - start) * index / segments) * radius,
        )
        for index in range(1, segments + 1)
    )
    return _world_xz_prism(cq, points, 83.0, 0.0)


def _clip_lower_r3_filler(cq: Any, origin: tuple[float, float, float]) -> Any:
    radius = 3.0
    edge_s = 55.5
    edge_n = 0.0
    center_s = edge_s + radius
    center_n = edge_n + radius
    points = [(edge_s - 0.05, edge_n - 0.05), (center_s, edge_n - 0.05), (center_s, edge_n)]
    points.extend(
        (
            center_s + math.cos(-math.pi / 2 - math.pi * index / 48) * radius,
            center_n + math.sin(-math.pi / 2 - math.pi * index / 48) * radius,
        )
        for index in range(1, 25)
    )
    points.append((edge_s - 0.05, center_n))
    return _local_sn_prism(cq, origin, points, -41.5, 41.5)


def _clip_outer_r3_cutter(cq: Any, origin: tuple[float, float, float]) -> Any:
    radius = 3.0
    edge_s = 55.5
    edge_n = 15.6
    center_s = edge_s - radius
    center_n = edge_n - radius
    points = [(edge_s + 0.05, edge_n + 0.05), (edge_s + 0.05, edge_n - radius), (edge_s, edge_n - radius)]
    points.extend(
        (
            center_s + math.cos(math.pi * index / 48) * radius,
            center_n + math.sin(math.pi * index / 48) * radius,
        )
        for index in range(1, 25)
    )
    points.append((edge_s - radius, edge_n + 0.05))
    return _local_sn_prism(cq, origin, points, -42.5, 42.5)


def _base_minus_x_r10_cutters(cq: Any) -> Any:
    radius = 10.0
    overlap = 0.05
    x_edge = -DIMENSIONS.base_length_x / 2
    cutters: list[Any] = []
    for y_sign in (-1.0, 1.0):
        y_edge = y_sign * DIMENSIONS.width_y / 2
        center_y = y_edge - y_sign * radius
        points = [
            (x_edge - overlap, y_edge + y_sign * overlap),
            (x_edge - overlap, center_y),
            (x_edge, center_y),
        ]
        start = math.pi
        end = math.pi / 2 if y_sign > 0 else 3 * math.pi / 2
        points.extend(
            (
                x_edge + radius + math.cos(start + (end - start) * index / 32) * radius,
                center_y + math.sin(start + (end - start) * index / 32) * radius,
            )
            for index in range(1, 33)
        )
        points.append((x_edge + radius, y_edge + y_sign * overlap))
        cutters.append(
            cq.Workplane("XY")
            .polyline(points)
            .close()
            .extrude(DIMENSIONS.base_thickness + 2 * overlap)
            .translate((0.0, 0.0, -overlap))
            .val()
        )
    return cutters[0].fuse(cutters[1])


def _slope_minus_y_r10_cutter(
    cq: Any,
    origin: tuple[float, float, float],
) -> Any:
    radius = 10.0
    edge_y = -DIMENSIONS.width_y / 2
    center_s = radius
    center_y = edge_y + radius
    points = [(-0.05, edge_y - 0.05), (-0.05, center_y), (0.0, center_y)]
    points.extend(
        (
            center_s + math.cos(math.pi + math.pi * index / 64) * radius,
            center_y + math.sin(math.pi + math.pi * index / 64) * radius,
        )
        for index in range(1, 33)
    )
    points.append((radius, edge_y - 0.05))
    shape = (
        cq.Workplane("XY")
        .workplane(offset=-5.05)
        .polyline(points)
        .close()
        .extrude(5.1)
        .val()
    )
    return _to_world(shape, origin)


def _rear_slot_plus_y_r2_filler(
    cq: Any,
    origin: tuple[float, float, float],
) -> Any:
    radius = 2.0
    edge_s = 1.0
    edge_n = -5.0
    center_s = edge_s - radius
    center_n = edge_n - radius
    points = [(edge_s + 0.05, edge_n + 0.05), (center_s, edge_n + 0.05), (center_s, edge_n)]
    points.extend(
        (
            center_s + math.cos(math.pi / 2 - math.pi * index / 40) * radius,
            center_n + math.sin(math.pi / 2 - math.pi * index / 40) * radius,
        )
        for index in range(1, 21)
    )
    points.append((edge_s + 0.05, edge_n - radius))
    return _local_sn_prism(cq, origin, points, 39.45, 41.5)


def _local_box(
    cq: Any,
    origin: tuple[float, float, float],
    s_min: float,
    s_max: float,
    y_min: float,
    y_max: float,
    n_min: float,
    n_max: float,
) -> Any:
    shape = (
        cq.Workplane("XY")
        .box(
            s_max - s_min,
            y_max - y_min,
            n_max - n_min,
            centered=(False, False, False),
        )
        .translate((s_min, y_min, n_min))
        .val()
    )
    return _to_world(shape, origin)


def _surface_point(
    origin: tuple[float, float, float],
    distance_s: float,
    normal_offset: float,
) -> tuple[float, float, float]:
    angle = math.radians(60.0)
    return (
        origin[0] + math.cos(angle) * distance_s + math.sin(angle) * normal_offset,
        0.0,
        origin[2] - math.sin(angle) * distance_s + math.cos(angle) * normal_offset,
    )


def _local_sn_prism(
    cq: Any,
    origin: tuple[float, float, float],
    points: list[tuple[float, float]],
    y_min: float,
    y_max: float,
) -> Any:
    world_points = [
        (point[0], point[2])
        for point in (_surface_point(origin, s, n) for s, n in points)
    ]
    return _world_xz_prism(cq, world_points, y_max - y_min, (y_min + y_max) / 2)


def _world_xz_prism(
    cq: Any,
    points: list[tuple[float, float]],
    width_y: float,
    center_y: float,
) -> Any:
    return (
        cq.Workplane("XZ")
        .polyline(points)
        .close()
        .extrude(width_y)
        .translate((0.0, center_y + width_y / 2, 0.0))
        .val()
    )


def _local_rounded_box(
    cq: Any,
    origin: tuple[float, float, float],
    *,
    center_s: float,
    center_y: float,
    s_length: float,
    y_width: float,
    n_min: float,
    n_max: float,
    radius: float,
) -> Any:
    shape = (
        cq.Workplane("XY")
        .workplane(offset=n_min)
        .center(center_s, center_y)
        .rect(s_length - 2 * radius, y_width)
        .rect(s_length, y_width - 2 * radius)
        .vertices()
        .circle(radius)
        .combine()
        .extrude(n_max - n_min)
        .val()
    )
    return _to_world(shape, origin)


def _local_n_cylinder(
    cq: Any,
    origin: tuple[float, float, float],
    *,
    center_s: float,
    center_y: float,
    n_min: float,
    n_max: float,
    radius: float,
) -> Any:
    shape = (
        cq.Workplane("XY")
        .workplane(offset=n_min)
        .center(center_s, center_y)
        .circle(radius)
        .extrude(n_max - n_min)
        .val()
    )
    return _to_world(shape, origin)


def _local_y_cylinder(
    cq: Any,
    origin: tuple[float, float, float],
    *,
    center_s: float,
    center_n: float,
    y_min: float,
    y_max: float,
    radius: float,
) -> Any:
    plane = cq.Plane(
        origin=(center_s, y_min, center_n),
        xDir=(1.0, 0.0, 0.0),
        normal=(0.0, 1.0, 0.0),
    )
    shape = cq.Workplane(plane).circle(radius).extrude(y_max - y_min).val()
    return _to_world(shape, origin)


def _to_world(shape: Any, origin: tuple[float, float, float]) -> Any:
    return shape.rotate((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), 60.0).translate(origin)


__all__ = ["DIMENSIONS", "K10PhotoAlbumDimensions", "build_k10_photo_album_shape"]
