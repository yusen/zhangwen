from __future__ import annotations

from hashlib import sha256
from io import StringIO
import asyncio
import json
import time

import pytest

from zhangwen.cad_agent.models import CadBuildSpec
from zhangwen.cad_agent.artifact_store import ArtifactFileStore
from zhangwen.cad_agent.models import CadDraft
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.cad_agent import worker_client as worker_client_module
from zhangwen.cad_agent.worker_client import (
    CANCEL_WAIT_SECONDS,
    PROCESS_MEMORY_BYTES,
    CadWorkerClient,
    CadWorkerError,
)
from zhangwen.cad_agent.profile_repository import MechanicalProfileRepository
from zhangwen.projects.repository import ProjectRepository
from zhangwen.cad_agent.worker_protocol import WORKER_PROTOCOL, WORKER_VERSION
from zhangwen.cad_engine import worker
from zhangwen.cad_engine.layout import resolve_layout
from zhangwen.cad_engine.models import Face, ResolvedMountKind
from zhangwen.cad_engine.validation import validate_design
from zhangwen.cad_engine.worker import WorkerFailure, adapt_build_spec, load_job_request


def agent_request(job_id: str = "cadjob-1") -> dict[str, object]:
    return {
        "jobId": job_id,
        "projectId": "project-1",
        "templateKind": "BOX_WITH_LID",
        "templateRevision": "box-with-lid.v1",
        "parameters": {
            "width": 100.0,
            "depth": 70.0,
            "height": 40.0,
            "wall_thickness": 2.4,
            "screw_posts": 4,
        },
        "components": [],
        "constraints": {"process": "FDM", "minWallThicknessMm": 1.6},
        "summary": "Deterministic box with lid",
        "requestedOutputs": [],
        "profileSnapshots": [],
    }


def test_load_job_request_reads_exactly_one_stdin_json() -> None:
    payload = json.dumps(agent_request(), ensure_ascii=False)
    loaded = load_job_request(StringIO(payload), "cadjob-1")

    assert loaded.jobId == "cadjob-1"
    assert loaded.projectId == "project-1"

    with pytest.raises(WorkerFailure, match="not valid JSON"):
        load_job_request(StringIO(payload + payload), "cadjob-1")


def test_worker_emits_versioned_ndjson_and_uses_current_directory(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = CadBuildSpec.model_validate(agent_request())
    sentinel = object()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        worker,
        "build_cad_artifacts",
        lambda spec, destination, **kwargs: sentinel,
    )
    monkeypatch.setattr(
        worker,
        "build_result_payload",
        lambda artifacts: {
            "manifest": {
                "schemaVersion": "1.0",
                "engineId": "zhangwen-cad-engine",
                "engineVersion": "2.8.0",
                "designId": "cadjob-1",
                "specSha256": "a" * 64,
                "files": [],
            },
            "validation": {"ok": True, "checks": []},
            "geometrySummary": {},
        },
    )
    output = StringIO()

    exit_code = worker.main(
        ["cadjob-1"],
        input_stream=StringIO(request.model_dump_json()),
        output_stream=output,
    )

    events = [json.loads(line) for line in output.getvalue().splitlines()]
    assert exit_code == 0
    assert [event["event"] for event in events] == [
        "STARTED",
        "PROGRESS",
        "PROGRESS",
        "PROGRESS",
        "PROGRESS",
        "RESULT",
    ]
    assert all(event["protocol"] == WORKER_PROTOCOL for event in events)
    assert all(event["version"] == WORKER_VERSION for event in events)
    assert [event["sequence"] for event in events] == list(range(1, 7))


def test_worker_rejects_path_like_job_identifier_as_ndjson() -> None:
    output = StringIO()
    exit_code = worker.main(
        ["../outside"],
        input_stream=StringIO("{}"),
        output_stream=output,
    )

    event = json.loads(output.getvalue())
    assert exit_code == 64
    assert event["event"] == "ERROR"
    assert event["payload"]["code"] == "CAD_WORKER_USAGE"


def test_adapter_rejects_unimplemented_parameters_instead_of_ignoring_them() -> None:
    request = agent_request()
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters["freeform_surface_strength"] = 2.0

    with pytest.raises(WorkerFailure, match="unsupported box parameter"):
        adapt_build_spec(CadBuildSpec.model_validate(request))


@pytest.mark.parametrize(
    ("name", "value"),
    (("width", 300.0), ("screw_posts", 2.0)),
)
def test_adapter_enforces_production_parameter_catalog(name: str, value: float) -> None:
    request = agent_request()
    parameters = request["parameters"]
    assert isinstance(parameters, dict)
    parameters[name] = value

    with pytest.raises(WorkerFailure, match="outside the supported range"):
        adapt_build_spec(CadBuildSpec.model_validate(request))


def test_adapter_rejects_unowned_template_revision() -> None:
    request = agent_request()
    request["templateRevision"] = "box-with-lid.v2"

    with pytest.raises(WorkerFailure, match="unsupported template revision"):
        adapt_build_spec(CadBuildSpec.model_validate(request))


def test_adapter_preserves_complete_trusted_profile_snapshot(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    profiles = MechanicalProfileRepository(projects.db_path)
    profiles.seed_builtin_profiles()
    ultrasonic = profiles.get("unihiker_ultrasonic_distance_sensor")
    request = agent_request("cadjob-profile")
    request["components"] = [
        {
            "instanceId": "distance-sensor",
            "hardwareId": "hw_ultrasonic_exact",
            "profileId": ultrasonic.profile_id,
            "resolvedProfileId": ultrasonic.profile_id,
            "resolvedProfileRevision": ultrasonic.revision,
            "resolvedProfileSha256": ultrasonic.content_sha256,
            "mountSurface": ultrasonic.mounting.preferred_surface.value,
            "rotationDeg": 0,
        }
    ]
    request["profileSnapshots"] = [ultrasonic.model_dump(mode="json")]

    engine_spec = adapt_build_spec(CadBuildSpec.model_validate(request))

    adapted = engine_spec.profiles[0]
    assert adapted.model_kind == ultrasonic.model_kind
    assert adapted.openings == ultrasonic.openings
    assert adapted.keepouts == ultrasonic.keepouts
    assert adapted.mounting.holes == ultrasonic.mounting.holes


def test_component_mount_adapter_derives_structure_from_one_profile(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    profiles = MechanicalProfileRepository(projects.db_path)
    profiles.seed_builtin_profiles()
    xiao = profiles.get("xiao_esp32s3")
    request = {
        "jobId": "cadjob-component-mount",
        "projectId": "project-1",
        "templateKind": "COMPONENT_MOUNT",
        "templateRevision": "component-mount.v1",
        "parameters": {},
        "components": [
            {
                "instanceId": "mounted-xiao",
                "hardwareId": "hw_xiao_exact",
                "profileId": xiao.profile_id,
                "resolvedProfileId": xiao.profile_id,
                "resolvedProfileRevision": xiao.revision,
                "resolvedProfileSha256": xiao.content_sha256,
            }
        ],
        "constraints": {"process": "FDM"},
        "summary": "Profile-derived XIAO mount",
        "requestedOutputs": [],
        "profileSnapshots": [xiao.model_dump(mode="json")],
    }

    engine_spec = adapt_build_spec(CadBuildSpec.model_validate(request))
    layout = resolve_layout(engine_spec)

    assert engine_spec.template == "component_mount"
    assert engine_spec.enclosure is None
    assert engine_spec.component_mount is not None
    assert engine_spec.component_mount.base_thickness == 3.0
    assert len(layout.hardware) == 1
    assert layout.hardware[0].bounds.min_z == pytest.approx(3.0)
    assert validate_design(engine_spec, layout).ok is True


def test_repository_materializes_confirmed_hardware_profile_for_worker(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("CAD profile", "生成超声波外壳")
    profiles = MechanicalProfileRepository(projects.db_path)
    profiles.seed_builtin_profiles(now="2026-07-13T00:00:00+00:00")
    ultrasonic = profiles.get("unihiker_ultrasonic_distance_sensor")
    with projects._connect() as conn:
        conn.execute(
            """
            INSERT INTO hardware_components (
              id, name, category, status, electrical_json, stock, price,
              age_recommendation, safety_tags_json, notes, created_at, updated_at
            ) VALUES (
              'hw_ultrasonic_exact', '超声波测距模块', 'sensor', 'active', '{}',
              0, 0, NULL, '[]', '', ?, ?
            )
            """,
            ("2026-07-13T00:00:00+00:00", "2026-07-13T00:00:00+00:00"),
        )
        conn.execute(
            """
            INSERT INTO hardware_mechanical_links (
              id, hardware_component_id, mechanical_profile_id,
              mechanical_profile_revision, evidence_level, confirmed_at,
              created_at, updated_at
            ) VALUES (?, ?, ?, ?, 'TRUSTED', ?, ?, ?)
            """,
            (
                "link_ultrasonic_exact",
                "hw_ultrasonic_exact",
                ultrasonic.profile_id,
                ultrasonic.revision,
                "2026-07-13T00:00:00+00:00",
                "2026-07-13T00:00:00+00:00",
                "2026-07-13T00:00:00+00:00",
            ),
        )
    cad_run = CadRepository(projects.db_path).create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={"width": 100, "depth": 70, "height": 40},
            components=[
                {
                    "instanceId": "distance-sensor",
                    "hardwareId": "hw_ultrasonic_exact",
                    "profileId": ultrasonic.profile_id,
                    "mountSurface": ultrasonic.mounting.preferred_surface.value,
                }
            ],
            constraints={"process": "FDM"},
            summary="带超声波开孔的外壳",
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=workspace.experts[0].id,
    )

    job = CadRepository(projects.db_path).create_job(
        project_id=workspace.project.id,
        cad_run_id=cad_run.id,
        client_request_id="profile-resolution",
    )

    component = job.request.components[0]
    assert component.hardwareId == "hw_ultrasonic_exact"
    assert component.profileId == ultrasonic.profile_id
    assert component.resolvedProfileId == ultrasonic.profile_id
    assert component.resolvedProfileRevision == ultrasonic.revision
    assert component.resolvedProfileSha256 == ultrasonic.content_sha256
    assert adapt_build_spec(job.request).profiles[0].profile_id == ultrasonic.profile_id


def test_adapter_rejects_resolved_profile_snapshot_mismatch(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    profiles = MechanicalProfileRepository(projects.db_path)
    profiles.seed_builtin_profiles()
    ultrasonic = profiles.get("unihiker_ultrasonic_distance_sensor")
    request = agent_request("cadjob-profile-mismatch")
    request["components"] = [
        {
            "instanceId": "distance-sensor",
            "hardwareId": "hw_ultrasonic_exact",
            "profileId": ultrasonic.profile_id,
            "resolvedProfileId": ultrasonic.profile_id,
            "resolvedProfileRevision": ultrasonic.revision,
            "resolvedProfileSha256": "0" * 64,
            "mountSurface": ultrasonic.mounting.preferred_surface.value,
        }
    ]
    request["profileSnapshots"] = [ultrasonic.model_dump(mode="json")]

    with pytest.raises(WorkerFailure, match="resolved mechanical profile snapshot"):
        adapt_build_spec(CadBuildSpec.model_validate(request))


def test_worker_client_sends_stdin_and_uses_job_staging(tmp_path) -> None:
    pytest.importorskip("cadquery", reason="CadQuery is an optional CAD runtime dependency")
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging("cadjob-client")
    request = CadBuildSpec.model_validate(agent_request("cadjob-client"))

    result = asyncio.run(
        CadWorkerClient().run(
            "cadjob-client",
            request=request,
            staging_dir=staging,
        )
    )

    assert result["manifest"]["designId"] == "cadjob-client"
    files = store.validate_manifest("cadjob-client", result["manifest"])
    assert len(files) == 11
    assert {
        (item.file_name, item.role, item.mime_type)
        for item in files
        if item.file_name in {"base.step", "lid.step"}
    } == {
        ("base.step", "STEP_PRINTABLE_PARTS", "model/step"),
        ("lid.step", "STEP_PRINTABLE_PARTS", "model/step"),
    }


def test_xiao_trusted_profile_auto_sizing_real_worker_golden(tmp_path) -> None:
    cadquery = pytest.importorskip(
        "cadquery", reason="CadQuery is required for the real XIAO golden"
    )
    trimesh = pytest.importorskip(
        "trimesh", reason="trimesh validates the real XIAO meshes"
    )
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("XIAO CAD golden", "Generate a fitted XIAO enclosure")
    profiles = MechanicalProfileRepository(projects.db_path)
    profiles.seed_builtin_profiles(now="2026-07-13T00:00:00+00:00")
    xiao = profiles.get("xiao_esp32s3", revision="confirmed-v1")
    with projects._connect() as conn:
        conn.execute(
            """
            INSERT INTO hardware_components (
              id, name, category, status, electrical_json, stock, price,
              age_recommendation, safety_tags_json, notes, created_at, updated_at
            ) VALUES (
              'hw_xiao_esp32s3_exact', 'Seeed Studio XIAO ESP32S3', 'controller',
              'active', '{}', 0, 0, NULL, '[]', '', ?, ?
            )
            """,
            ("2026-07-13T00:00:00+00:00", "2026-07-13T00:00:00+00:00"),
        )
    profiles.confirm_hardware_link(
        "hw_xiao_esp32s3_exact",
        profile_id=xiao.profile_id,
        revision=xiao.revision,
        now="2026-07-13T00:00:00+00:00",
    )
    cad_run = CadRepository(projects.db_path).create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={},
            components=[
                {
                    "instanceId": "xiao_controller",
                    "hardwareId": "hw_xiao_esp32s3_exact",
                    "profileId": xiao.profile_id,
                    "mountSurface": "base_floor",
                }
            ],
            constraints={"process": "FDM"},
            summary="Automatically sized XIAO ESP32S3 enclosure with USB access",
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=workspace.experts[0].id,
    )
    job = CadRepository(projects.db_path).create_job(
        project_id=workspace.project.id,
        cad_run_id=cad_run.id,
        client_request_id="xiao-real-worker-golden",
    )

    assert job.request.parameters == {"width": 80.0, "height": 28.0, "depth": 50.0}
    assert job.request.sizingEvidence is not None
    assert job.request.sizingEvidence.mode == "AUTO"
    assert set(job.request.sizingEvidence.autoResolvedParameters) == {"width", "height", "depth"}
    assert job.request.sizingEvidence.requiredParameters == {
        "width": 80.0,
        "height": 28.0,
        "depth": 50.0,
    }
    assert len(job.request.profileSnapshots) == 1
    frozen_xiao = job.request.profileSnapshots[0]
    assert frozen_xiao.profile_id == "xiao_esp32s3"
    assert frozen_xiao.revision == "confirmed-v1"
    assert frozen_xiao.evidence_level == "TRUSTED"
    assert frozen_xiao.content_sha256 == xiao.content_sha256
    assert frozen_xiao.mounting.strategy.value == "edge_retainer"
    assert frozen_xiao.openings[0].center_z == 2.4

    engine_spec = adapt_build_spec(job.request)
    layout = resolve_layout(engine_spec)
    assert [mount.kind for mount in layout.mounts] == [
        ResolvedMountKind.SUPPORT_TRAY,
        ResolvedMountKind.SIDE_RETAINER,
        ResolvedMountKind.SIDE_RETAINER,
        ResolvedMountKind.END_STOP,
        ResolvedMountKind.END_STOP,
    ]
    assert [mount.hardware_instance_id for mount in layout.mounts] == ["xiao_controller"] * 5
    assert len(layout.openings) == 1
    usb_opening = layout.openings[0]
    assert usb_opening.opening.face is Face.LEFT
    assert usb_opening.opening.center_u == pytest.approx(0.0)
    assert usb_opening.opening.size_u == pytest.approx(11.6)
    assert usb_opening.opening.size_v == pytest.approx(7.2)
    assert usb_opening.world_center.z - layout.hardware[0].center.z == pytest.approx(2.4)
    assert validate_design(engine_spec, layout).ok is True

    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging(job.id)
    result = asyncio.run(
        CadWorkerClient().run(
            job.id,
            request=job.request,
            staging_dir=staging,
        )
    )
    manifest = result["manifest"]
    files = store.validate_manifest(
        job.id,
        manifest,
        expected_design_id=job.id,
        expected_spec_sha256=job.requestHash,
    )

    assert len(files) == 11
    assert {item.file_name for item in files} == {
        "assembly.step",
        "base.step",
        "base.stl",
        "geometry-summary.json",
        "lid.step",
        "lid.stl",
        "manifest.json",
        "parameters.json",
        "preview.glb",
        "profiles.json",
        "validation.json",
    }
    for item in files:
        content = item.source_path.read_bytes()
        assert item.byte_size == len(content)
        assert item.sha256 == sha256(content).hexdigest()
    base = cadquery.importers.importStep(str(staging / "base.step")).val()
    assert base.isValid()
    assert len(base.Solids()) == 1
    for file_name in ("base.stl", "lid.stl"):
        mesh = trimesh.load_mesh(staging / file_name, force="mesh")
        assert mesh.is_watertight
        assert mesh.is_volume
    glb = (staging / "preview.glb").read_bytes()
    assert glb[:4] == b"glTF"
    assert trimesh.load(staging / "preview.glb", force="scene").geometry


@pytest.mark.asyncio
async def test_worker_client_cancel_terminates_process_within_five_seconds(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    script = """
import json
import sys
import time

job_id = sys.argv[1]
sys.stdin.read()
for sequence, event, payload in (
    (1, "STARTED", {}),
    (2, "PROGRESS", {"phase": "BUILDING", "progress": 40}),
):
    print(json.dumps({
        "protocol": "zhangwen.cad.worker",
        "version": 1,
        "jobId": job_id,
        "sequence": sequence,
        "event": event,
        "payload": payload,
    }), flush=True)
time.sleep(60)
"""
    helper = tmp_path / "sleeping_cad_worker.py"
    helper.write_text(script, encoding="utf-8")
    monkeypatch.setattr(
        worker_client_module,
        "_worker_command",
        lambda job_id: [worker_client_module._python_executable(), str(helper), job_id],
    )
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging("cadjob-cancel")
    request = CadBuildSpec.model_validate(agent_request("cadjob-cancel"))
    building = asyncio.Event()
    client = CadWorkerClient()
    task = asyncio.create_task(
        client.run(
            "cadjob-cancel",
            request=request,
            staging_dir=staging,
            on_progress=lambda _phase, _progress: building.set(),
        )
    )
    await asyncio.wait_for(building.wait(), timeout=3)

    started = time.monotonic()
    assert await client.cancel("cadjob-cancel") is True
    with pytest.raises(CadWorkerError):
        await task

    assert time.monotonic() - started < CANCEL_WAIT_SECONDS
    assert "cadjob-cancel" not in client._running


def test_worker_resource_limits_match_cad_contract() -> None:
    assert PROCESS_MEMORY_BYTES == 1024 * 1024 * 1024
    assert CANCEL_WAIT_SECONDS == 5
