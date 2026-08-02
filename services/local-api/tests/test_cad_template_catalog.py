from __future__ import annotations

import pytest

from zhangwen.cad_agent.generator import template_specs
from zhangwen.cad_agent.models import CadDraft, CadTemplateKind
from zhangwen.cad_agent.repository import _parameters_for_draft
from zhangwen.cad_agent.template_catalog import (
    BOX_WITH_LID_PARAMETER_SPECS,
    COMPONENT_MOUNT_PARAMETER_SPECS,
    production_parameter_spec,
)
from zhangwen.experts.context_assembler import _cad_capability
from zhangwen.projects.models import ExpertType


EXPECTED_BOX_PARAMETERS = {
    "width",
    "height",
    "depth",
    "wall_thickness",
    "floor_thickness",
    "lid_thickness",
    "lid_lip_height",
    "lid_lip_thickness",
    "lid_clearance",
    "corner_radius",
    "hardware_gap",
    "edge_clearance",
    "screw_posts",
    "screw_boss_diameter",
    "screw_hole_diameter",
    "screw_post_edge_inset",
}


def test_box_with_lid_legacy_catalog_uses_the_production_source() -> None:
    legacy = template_specs()[CadTemplateKind.BOX_WITH_LID]

    assert {item[0] for item in legacy} == EXPECTED_BOX_PARAMETERS
    assert legacy == [item.as_legacy_tuple() for item in BOX_WITH_LID_PARAMETER_SPECS]


def test_screw_post_count_accepts_only_supported_patterns() -> None:
    spec = production_parameter_spec(CadTemplateKind.BOX_WITH_LID, "screw_posts")

    assert spec.accepts(0)
    assert spec.accepts(4)
    assert not spec.accepts(2)


def test_draft_parameter_materialization_rejects_unsupported_post_count() -> None:
    draft = CadDraft(
        templateKind=CadTemplateKind.BOX_WITH_LID,
        parameters={"width": 100, "screw_posts": 2},
        summary="invalid fastener pattern",
    )

    with pytest.raises(ValueError, match="screw_posts"):
        _parameters_for_draft(draft)


def test_box_parameter_defaults_are_accepted_by_their_own_rules() -> None:
    assert all(spec.accepts(spec.default) for spec in BOX_WITH_LID_PARAMETER_SPECS)


def test_component_mount_has_an_independent_bounded_parameter_catalog() -> None:
    legacy = template_specs()[CadTemplateKind.COMPONENT_MOUNT]

    assert {item[0] for item in legacy} == {
        "base_thickness",
        "edge_margin",
        "component_clearance",
        "retainer_height",
        "fastener_hole_diameter",
        "corner_radius",
    }
    assert legacy == [item.as_legacy_tuple() for item in COMPONENT_MOUNT_PARAMETER_SPECS]
    assert all(spec.accepts(spec.default) for spec in COMPONENT_MOUNT_PARAMETER_SPECS)


def test_structure_engineer_capability_exposes_catalog_and_discrete_values() -> None:
    capability = _cad_capability(ExpertType.STRUCTURE_ENGINEER)

    assert capability is not None
    templates = {
        item["templateKind"]: item for item in capability["allowedTemplates"]
    }
    parameters = templates["BOX_WITH_LID"]["parameters"]
    assert {item["name"] for item in parameters} == EXPECTED_BOX_PARAMETERS
    screw_posts = next(item for item in parameters if item["name"] == "screw_posts")
    assert screw_posts["allowedValues"] == [0, 4]
    assert {
        item["name"] for item in templates["COMPONENT_MOUNT"]["parameters"]
    } == {item.name for item in COMPONENT_MOUNT_PARAMETER_SPECS}
    freeform = templates["FREEFORM_STRUCTURE"]
    assert freeform["parameters"] == []
    assert freeform["componentCount"] == 0
    assert freeform["declarativeGeometry"]["kinds"] == [
        "box",
        "rounded_box",
        "cylinder",
    ]
    album = templates["UNIHIKER_K10_PHOTO_ALBUM"]
    assert album["templateRevision"] == "unihiker-k10-photo-album.v1"
    assert album["parameters"] == []
    assert album["componentCount"] == 0
    assert album["fixedGeometry"] is True
