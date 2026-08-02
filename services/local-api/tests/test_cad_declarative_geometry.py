from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from zhangwen.cad_agent.models import CadBuildSpec, CadDraft
from zhangwen.cad_engine import cadquery_available
from zhangwen.cad_engine.engine import build_cad_artifacts
from zhangwen.cad_engine.worker import adapt_build_spec, build_result_payload


def freeform_request() -> dict[str, object]:
    return {
        "jobId": "cadjob-freeform-plate",
        "projectId": "project-1",
        "templateKind": "FREEFORM_STRUCTURE",
        "templateRevision": "freeform-structure.v1",
        "parameters": {},
        "components": [],
        "constraints": {"process": "FDM"},
        "summary": "80×30×4 mm 圆角安装板，带两个直径 3 mm 通孔",
        "requestedOutputs": [],
        "profileSnapshots": [],
        "geometry": {
            "primitives": [
                {
                    "primitive_id": "plate",
                    "operation": "add",
                    "kind": "rounded_box",
                    "center": {"x": 0.0, "y": 0.0, "z": 2.0},
                    "size": {"length_x": 80.0, "width_y": 30.0, "height_z": 4.0},
                    "corner_radius": 4.0,
                    "role": "body",
                },
                {
                    "primitive_id": "left_hole",
                    "operation": "cut",
                    "kind": "cylinder",
                    "center": {"x": -30.0, "y": 0.0, "z": 2.0},
                    "diameter": 3.0,
                    "height": 6.0,
                    "role": "feature",
                },
                {
                    "primitive_id": "right_hole",
                    "operation": "cut",
                    "kind": "cylinder",
                    "center": {"x": 30.0, "y": 0.0, "z": 2.0},
                    "diameter": 3.0,
                    "height": 6.0,
                    "role": "feature",
                },
            ]
        },
    }


def test_freeform_contract_accepts_bounded_geometry_without_components() -> None:
    payload = freeform_request()
    for key in ("jobId", "projectId", "templateRevision", "profileSnapshots"):
        payload.pop(key, None)
    draft = CadDraft.model_validate(payload)

    assert draft.templateKind.value == "FREEFORM_STRUCTURE"
    assert draft.components == []
    assert draft.geometry is not None
    assert [item.operation for item in draft.geometry.primitives] == ["add", "cut", "cut"]


@pytest.mark.parametrize(
    "geometry",
    [
        {"primitives": []},
        {
            "primitives": [
                {
                    "primitive_id": "bad",
                    "operation": "cut",
                    "kind": "cylinder",
                    "center": {"x": 0, "y": 0, "z": 0},
                    "diameter": 3,
                    "height": 5,
                    "role": "feature",
                }
            ]
        },
    ],
)
def test_freeform_contract_rejects_empty_or_cut_first_geometry(
    geometry: dict[str, object],
) -> None:
    payload = freeform_request()
    for key in ("jobId", "projectId", "templateRevision", "profileSnapshots"):
        payload.pop(key, None)
    payload["geometry"] = geometry

    with pytest.raises(ValidationError):
        CadDraft.model_validate(payload)


def test_worker_adapts_freeform_geometry_without_hardware_profile() -> None:
    request = CadBuildSpec.model_validate(freeform_request())

    spec = adapt_build_spec(request)

    assert spec.template == "freeform_structure"
    assert spec.freeform_geometry is not None
    assert spec.enclosure is None
    assert spec.component_mount is None
    assert spec.hardware == ()


@pytest.mark.skipif(not cadquery_available(), reason="CadQuery runtime unavailable")
def test_freeform_worker_builds_single_part_step_stl_and_glb(tmp_path: Path) -> None:
    spec = adapt_build_spec(CadBuildSpec.model_validate(freeform_request()))

    artifacts = build_cad_artifacts(spec, tmp_path)

    names = {path.name for path in artifacts.output_directory.iterdir()}
    assert {"assembly.step", "part.step", "part.stl", "preview.glb"}.issubset(names)
    assert "base.step" not in names
    assert "lid.step" not in names
    assert artifacts.validation.ok is True
    assert artifacts.geometry_summary.parts[0].part_id == "part"
    assert artifacts.geometry_summary.parts[0].solid_count == 1

    result = build_result_payload(artifacts)
    outputs = result["manifest"]["files"]
    output_names = {item["fileName"] for item in outputs}
    assert output_names == {
        "assembly.step",
        "geometry-summary.json",
        "manifest.json",
        "parameters.json",
        "part.step",
        "part.stl",
        "preview.glb",
        "profiles.json",
        "validation.json",
    }
    printable_roles = {
        item["role"] for item in outputs if item["fileName"].startswith("part.")
    }
    assert printable_roles == {"STEP_PRINTABLE_PARTS", "STL_PRINTABLE_PARTS"}
