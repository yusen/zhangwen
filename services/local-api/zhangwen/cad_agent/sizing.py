"""Deterministic enclosure sizing from immutable mechanical profiles."""

from __future__ import annotations

from collections import defaultdict
from math import ceil, sqrt
from typing import Iterable

from zhangwen.cad_agent.models import (
    CadResolvedComponent,
    CadSizingEvidence,
    CadTemplateKind,
)
from zhangwen.cad_agent.profile_repository import MechanicalProfileSnapshot
from zhangwen.cad_agent.template_catalog import production_parameter_spec


_HORIZONTAL_SURFACES = {"base_floor", "lid_inner", "lid_outer"}
_FRONT_BACK_SURFACES = {"front_inner", "back_inner"}
_LEFT_RIGHT_SURFACES = {"left_inner", "right_inner"}


def resolve_enclosure_sizing(
    parameters: dict[str, float],
    components: Iterable[CadResolvedComponent],
    snapshots: Iterable[MechanicalProfileSnapshot],
) -> tuple[dict[str, float], CadSizingEvidence]:
    """Fill only omitted enclosure axes and preserve explicit user constraints."""

    resolved = {name: float(value) for name, value in parameters.items()}
    profile_by_id = {profile.profile_id: profile for profile in snapshots}
    edge = resolved.get(
        "edge_clearance",
        production_parameter_spec(CadTemplateKind.BOX_WITH_LID, "edge_clearance").default,
    )
    gap = resolved.get(
        "hardware_gap",
        production_parameter_spec(CadTemplateKind.BOX_WITH_LID, "hardware_gap").default,
    )
    grouped: dict[str, list[tuple[float, float, float, float | None, float | None]]] = (
        defaultdict(list)
    )
    base_heights: list[float] = []
    lid_heights: list[float] = []

    for component in components:
        profile = profile_by_id[component.resolvedProfileId]
        length = profile.dimensions.length_x
        width = profile.dimensions.width_y
        if int(component.rotationDeg) % 360 in (90, 270):
            length, width = width, length
        surface = component.mountSurface or profile.mounting.preferred_surface.value
        if surface == "external":
            continue
        offset_x = component.offsetMm.x if component.offsetMm is not None else None
        offset_y = component.offsetMm.y if component.offsetMm is not None else None
        grouped[surface].append(
            (length, width, profile.dimensions.height_z, offset_x, offset_y)
        )
        if surface == "base_floor":
            base_heights.append(profile.dimensions.height_z)
        elif surface == "lid_inner":
            lid_heights.append(profile.dimensions.height_z)

    # Preserve the verified prototype's conservative empty-cavity floor.
    required_width = 80.0
    required_depth = 50.0
    required_height = 28.0

    horizontal = [
        item
        for surface in _HORIZONTAL_SURFACES
        for item in grouped.get(surface, ())
    ]
    horizontal_length, horizontal_width = _required_surface_size(horizontal, edge, gap)
    required_width = max(required_width, horizontal_length)
    required_depth = max(required_depth, horizontal_width)

    front_back = [
        item
        for surface in _FRONT_BACK_SURFACES
        for item in grouped.get(surface, ())
    ]
    side_length, side_height = _required_surface_size(front_back, edge, gap)
    required_width = max(required_width, side_length)
    required_height = max(required_height, side_height)

    left_right = [
        item
        for surface in _LEFT_RIGHT_SURFACES
        for item in grouped.get(surface, ())
    ]
    side_depth, side_height = _required_surface_size(left_right, edge, gap)
    required_depth = max(required_depth, side_depth)
    required_height = max(required_height, side_height)

    vertical_stack = max(base_heights, default=0.0) + max(lid_heights, default=0.0)
    if base_heights and lid_heights:
        vertical_stack += gap
    elif vertical_stack:
        vertical_stack += edge
    required_height = max(required_height, vertical_stack)

    required = {
        "width": _round_up(required_width),
        "height": _round_up(required_height),
        "depth": _round_up(required_depth),
    }
    auto_resolved: list[str] = []
    for name, value in required.items():
        if name not in resolved:
            resolved[name] = value
            auto_resolved.append(name)
    mode = (
        "AUTO"
        if len(auto_resolved) == 3
        else "MIXED"
        if auto_resolved
        else "EXPLICIT"
    )
    return resolved, CadSizingEvidence(
        mode=mode,
        requiredParameters=required,
        autoResolvedParameters=auto_resolved,
    )


def _required_surface_size(
    items: list[tuple[float, float, float, float | None, float | None]],
    edge: float,
    gap: float,
) -> tuple[float, float]:
    if not items:
        return 0.0, 0.0
    automatic = [(length, width) for length, width, _height, x, y in items if x is None or y is None]
    explicit = [(length, width, x, y) for length, width, _height, x, y in items if x is not None and y is not None]
    required_length = 0.0
    required_width = 0.0
    if automatic:
        area = sum(length * width for length, width in automatic)
        row_capacity = max(max(length for length, _width in automatic), sqrt(area * 1.8))
        rows: list[list[tuple[float, float]]] = []
        current: list[tuple[float, float]] = []
        current_length = 0.0
        for item in sorted(automatic, key=lambda value: (-value[0], -value[1])):
            candidate = item[0] if not current else current_length + gap + item[0]
            if current and candidate > row_capacity:
                rows.append(current)
                current = []
                current_length = 0.0
                candidate = item[0]
            current.append(item)
            current_length = candidate
        if current:
            rows.append(current)
        required_length = max(
            sum(length for length, _width in row) + gap * max(0, len(row) - 1)
            for row in rows
        )
        required_width = sum(max(width for _length, width in row) for row in rows)
        required_width += gap * max(0, len(rows) - 1)
    for length, width, x, y in explicit:
        required_length = max(required_length, 2 * (abs(float(x)) + length / 2))
        required_width = max(required_width, 2 * (abs(float(y)) + width / 2))
    return required_length + edge * 2, required_width + edge * 2


def _round_up(value: float) -> float:
    return float(ceil(value * 10 - 1e-9) / 10)


__all__ = ["resolve_enclosure_sizing"]
