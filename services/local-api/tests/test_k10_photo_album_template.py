from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from zhangwen.cad_agent.models import CadBuildSpec, CadDraft, CadTemplateKind
from zhangwen.cad_agent.intake import CadProfileIntake
from zhangwen.cad_engine import cadquery_available
from zhangwen.cad_engine.engine import build_cad_artifacts
from zhangwen.cad_engine.layout import resolve_layout
from zhangwen.cad_engine.validation import validate_design
from zhangwen.cad_engine.worker import WorkerFailure, adapt_build_spec


def album_request() -> dict[str, object]:
    return {
        "jobId": "cadjob-k10-album",
        "projectId": "project-1",
        "templateKind": "UNIHIKER_K10_PHOTO_ALBUM",
        "templateRevision": "unihiker-k10-photo-album.v1",
        "parameters": {},
        "components": [],
        "constraints": {"process": "FDM"},
        "summary": "行空板 K10 电子相册固定结构",
        "requestedOutputs": [],
        "profileSnapshots": [],
    }


def test_album_draft_is_a_fixed_template_without_provider_geometry() -> None:
    draft = CadDraft.model_validate(
        {
            "templateKind": "UNIHIKER_K10_PHOTO_ALBUM",
            "parameters": {},
            "components": [],
            "constraints": {"process": "FDM"},
            "summary": "行空板 K10 电子相册固定结构",
        }
    )

    assert draft.templateKind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM
    assert draft.geometry is None


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("parameters", {"slope_angle": 45}, "cannot include parameters"),
        (
            "components",
            [{"instanceId": "k10", "hardwareId": "hw-k10", "profileId": "k10"}],
            "cannot include components",
        ),
    ],
)
def test_album_draft_rejects_provider_owned_inputs(
    field: str,
    value: object,
    message: str,
) -> None:
    payload = album_request()
    for key in ("jobId", "projectId", "templateRevision", "profileSnapshots"):
        payload.pop(key)
    payload[field] = value

    with pytest.raises(ValueError, match=message):
        CadDraft.model_validate(payload)


def test_album_worker_adapts_only_the_fixed_revision() -> None:
    spec = adapt_build_spec(CadBuildSpec.model_validate(album_request()))
    layout = resolve_layout(spec)

    assert spec.template == "unihiker_k10_photo_album"
    assert spec.enclosure is None
    assert spec.component_mount is None
    assert spec.freeform_geometry is None
    assert layout.hardware == ()
    assert validate_design(spec, layout).ok is True

    invalid = album_request()
    invalid["templateRevision"] = "unihiker-k10-photo-album.v2"
    with pytest.raises(WorkerFailure, match="unsupported template revision"):
        adapt_build_spec(CadBuildSpec.model_validate(invalid))


def test_structure_intake_canonicalizes_album_request_without_questions(tmp_path: Path) -> None:
    from zhangwen.projects.repository import ProjectRepository

    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("K10 相册", "生成行空板 K10 电子相册结构")
    output = SimpleNamespace(
        cadDraft=None,
        uiPayload={"type": "clarification"},
        pendingItems=["provider invented question"],
        content="provider placeholder",
    )

    intake = CadProfileIntake(projects.db_path)
    intake.canonicalize_output(
        workspace.project.id,
        output,
        requested_target="unihiker_k10_photo_album",
    )
    intake.ensure_runtime_output(
        workspace.project.id,
        output,
        requested_target="unihiker_k10_photo_album",
    )

    assert output.cadDraft.templateKind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM
    assert output.cadDraft.parameters == {}
    assert output.cadDraft.components == []
    assert output.uiPayload is None
    assert output.pendingItems == []


@pytest.mark.skipif(not cadquery_available(), reason="CadQuery runtime unavailable")
def test_album_template_builds_one_valid_printable_part(tmp_path: Path) -> None:
    spec = adapt_build_spec(CadBuildSpec.model_validate(album_request()))

    artifacts = build_cad_artifacts(spec, tmp_path)

    assert artifacts.validation.ok is True
    assert len(artifacts.geometry_summary.parts) == 1
    part = artifacts.geometry_summary.parts[0]
    assert part.part_id == "part"
    assert part.solid_count == 1
    assert part.bounds.max_y - part.bounds.min_y == pytest.approx(83.0, abs=0.2)
    names = {item.file_name for item in artifacts.manifest.files}
    assert {"assembly.step", "part.step", "part.stl", "preview.glb"}.issubset(names)
