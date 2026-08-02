from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from zhangwen.cad_engine.models import (
    CadBuildSpec,
    CadEngineModel,
    HardwareMounting,
    HardwareMountingStrategy,
    MountSurface,
)
from zhangwen.cad_engine.profiles import trusted_profile, unihiker_k10_profile


FIXTURE = Path(__file__).parent / "fixtures" / "cad_engine" / "box_with_lid_k10.json"
FORBIDDEN_INPUT_FIELDS = ("path", "url", "code", "script", "command")


def fixture_payload() -> dict[str, object]:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_box_with_lid_fixture_is_a_strict_valid_spec() -> None:
    spec = CadBuildSpec.model_validate(fixture_payload())

    assert spec.template == "box_with_lid"
    assert spec.profiles[0] == unihiker_k10_profile()
    assert spec.openings[0].kind == "circle"
    assert spec.openings[1].kind == "rectangle"


@pytest.mark.parametrize("field_name", FORBIDDEN_INPUT_FIELDS)
def test_spec_rejects_forbidden_top_level_fields(field_name: str) -> None:
    payload = fixture_payload()
    payload[field_name] = "untrusted-value"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CadBuildSpec.model_validate(payload)


@pytest.mark.parametrize("field_name", FORBIDDEN_INPUT_FIELDS)
def test_spec_rejects_forbidden_nested_fields(field_name: str) -> None:
    payload = deepcopy(fixture_payload())
    profiles = payload["profiles"]
    assert isinstance(profiles, list)
    profile = profiles[0]
    assert isinstance(profile, dict)
    profile[field_name] = "untrusted-value"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CadBuildSpec.model_validate(payload)


def test_trusted_k10_dimensions_cannot_be_overridden() -> None:
    payload = fixture_payload()
    profiles = payload["profiles"]
    assert isinstance(profiles, list)
    profile = profiles[0]
    assert isinstance(profile, dict)
    dimensions = profile["dimensions"]
    assert isinstance(dimensions, dict)
    dimensions["length_x"] = 82.0

    with pytest.raises(ValidationError, match="dimensions cannot be overridden"):
        CadBuildSpec.model_validate(payload)


def test_unknown_hardware_profile_reference_is_rejected() -> None:
    payload = fixture_payload()
    hardware = payload["hardware"]
    assert isinstance(hardware, list)
    instance = hardware[0]
    assert isinstance(instance, dict)
    instance["profile_id"] = "invented_controller"

    with pytest.raises(ValidationError, match="unknown profiles"):
        CadBuildSpec.model_validate(payload)


def test_mounting_strategy_is_profile_only() -> None:
    payload = fixture_payload()
    hardware = payload["hardware"]
    assert isinstance(hardware, list)
    instance = hardware[0]
    assert isinstance(instance, dict)
    instance["mounting_strategy"] = "edge_retainer"

    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        CadBuildSpec.model_validate(payload)


def test_mounting_strategy_is_a_closed_enum() -> None:
    with pytest.raises(ValidationError, match="Input should be"):
        HardwareMounting(
            mode="base_floor",
            preferred_surface=MountSurface.BASE_FLOOR,
            strategy="freeform_geometry",
        )


def test_edge_retainer_strategy_is_restricted_to_base_floor_profiles() -> None:
    with pytest.raises(ValidationError, match="edge retainer requires a base-floor profile"):
        HardwareMounting(
            mode="inner_surface",
            preferred_surface=MountSurface.FRONT_INNER,
            strategy=HardwareMountingStrategy.EDGE_RETAINER,
        )


def test_trusted_profile_registry_is_closed() -> None:
    assert trusted_profile("unihiker_k10") == unihiker_k10_profile()
    with pytest.raises(KeyError, match="unknown trusted hardware profile"):
        trusted_profile("invented_controller")


def test_no_boundary_model_exposes_an_active_content_field() -> None:
    pending = [CadEngineModel]
    seen: set[type[CadEngineModel]] = set()
    while pending:
        model = pending.pop()
        if model in seen:
            continue
        seen.add(model)
        pending.extend(model.__subclasses__())

    for model in seen:
        assert set(model.model_fields).isdisjoint(FORBIDDEN_INPUT_FIELDS), model.__name__
