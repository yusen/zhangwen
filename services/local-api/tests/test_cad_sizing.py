from __future__ import annotations

from zhangwen.cad_agent.models import CadResolvedComponent
from zhangwen.cad_agent.models import CadDraft, CadTemplateKind
from zhangwen.cad_agent.profile_repository import MechanicalProfileSnapshot
from zhangwen.cad_agent.profile_seeds import normalize_profile_snapshot_payload
from zhangwen.cad_agent.sizing import resolve_enclosure_sizing
from zhangwen.cad_engine.models import (
    HardwareCoordinateSystem,
    HardwareMounting,
    HardwareProfile,
    MountSurface,
    ProfileSource,
    Size3,
)


def _snapshot(profile_id: str, length: float, width: float, height: float) -> MechanicalProfileSnapshot:
    profile = HardwareProfile(
        profile_id=profile_id,
        revision="measured-v1",
        display_name=profile_id,
        category="controller",
        dimensions=Size3(length_x=length, width_y=width, height_z=height),
        coordinate_system=HardwareCoordinateSystem(origin="pcb_center"),
        mounting=HardwareMounting(
            mode="base_floor",
            preferred_surface=MountSurface.BASE_FLOOR,
        ),
        source=ProfileSource.DECLARED,
    )
    payload = profile.model_dump(mode="json")
    payload.update(
        {
            "schema_version": "1.0",
            "evidence_level": "CONFIRMED",
            "representation": "parametric_envelope",
        }
    )
    import hashlib
    import json

    normalized = normalize_profile_snapshot_payload(payload)
    payload["content_sha256"] = hashlib.sha256(
        json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return MechanicalProfileSnapshot.model_validate(payload)


def _component(instance_id: str, profile: MechanicalProfileSnapshot) -> CadResolvedComponent:
    return CadResolvedComponent(
        instanceId=instance_id,
        hardwareId=f"hw_{instance_id}",
        profileId=profile.profile_id,
        resolvedProfileId=profile.profile_id,
        resolvedProfileRevision=profile.revision,
        resolvedProfileSha256=profile.content_sha256,
        mountSurface="base_floor",
    )


def test_missing_axes_are_resolved_from_component_footprints() -> None:
    left = _snapshot("left_board", 80, 40, 18)
    right = _snapshot("right_board", 60, 30, 12)

    parameters, evidence = resolve_enclosure_sizing(
        {"wall_thickness": 2.4, "edge_clearance": 8, "hardware_gap": 5},
        [_component("left", left), _component("right", right)],
        [left, right],
    )

    assert evidence.mode == "AUTO"
    assert set(evidence.autoResolvedParameters) == {"width", "height", "depth"}
    assert parameters["width"] >= 96
    assert parameters["depth"] >= 86
    assert parameters["height"] >= 28


def test_explicit_axes_are_preserved_and_required_size_remains_auditable() -> None:
    board = _snapshot("large_board", 120, 80, 30)

    parameters, evidence = resolve_enclosure_sizing(
        {"width": 60, "height": 20, "depth": 50},
        [_component("board", board)],
        [board],
    )

    assert evidence.mode == "EXPLICIT"
    assert parameters == {"width": 60, "height": 20, "depth": 50}
    assert evidence.requiredParameters["width"] > parameters["width"]
    assert evidence.requiredParameters["depth"] > parameters["depth"]
    assert evidence.requiredParameters["height"] > parameters["height"]


def test_no_component_auto_size_uses_catalog_minimums() -> None:
    parameters, evidence = resolve_enclosure_sizing({}, [], [])

    assert parameters == {"width": 80, "height": 28, "depth": 50}
    assert evidence.mode == "AUTO"


def test_structure_engineer_draft_can_request_fully_automatic_sizing() -> None:
    draft = CadDraft(
        templateKind=CadTemplateKind.BOX_WITH_LID,
        parameters={},
        summary="server resolves enclosure dimensions",
    )

    assert draft.parameters == {}
