from __future__ import annotations

import hashlib
import json

import pytest

from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import (
    CadBuildSpec,
    CadJobPhase,
    CadJobStatus,
)
from zhangwen.projects.repository import ProjectRepository


def _draft_run(repository: ProjectRepository, project_id: str, run_id: str) -> None:
    now = "2026-07-13T00:00:00+00:00"
    with repository._connect() as conn:
        conn.execute(
            """
            INSERT INTO cad_runs (
              id, project_id, spec_run_id, template_kind, version, status,
              command_label, parameters_json, validation_json, artifact_id,
              artifact_version_id, source_message_id, generated_by_expert_id,
              engine_id, engine_version, design_state_json, latest_job_id,
              stale_reason, created_at, updated_at, confirmed_at
            ) VALUES (?, ?, NULL, 'BOX_WITH_LID', 1, 'DRAFT',
                      'cadquery-deterministic', '[]', '{"ok":false,"checks":[]}',
                      NULL, NULL, NULL, NULL, 'cadquery', '2.8.0', '{}', NULL,
                      NULL, ?, ?, NULL)
            """,
            (run_id, project_id, now, now),
        )


def _build_spec(job_id: str, project_id: str) -> CadBuildSpec:
    return CadBuildSpec(
        jobId=job_id,
        projectId=project_id,
        templateKind="BOX_WITH_LID",
        templateRevision="box-with-lid.v1",
        parameters={"width": 80, "height": 50, "depth": 30},
        components=[],
        constraints={"process": "FDM", "minWallThicknessMm": 1.6},
        summary="参数化盒体与盖板",
        requestedOutputs=["GLB_PREVIEW", "STL_PRINTABLE_PARTS"],
        profileSnapshots=[],
    )


def test_job_repository_persists_transitions_and_idempotency(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("CAD", "生成盒体")
    _draft_run(projects, workspace.project.id, "cad_1")
    jobs = CadJobRepository(projects.db_path)
    spec = _build_spec("cadjob_1", workspace.project.id)
    request_hash = hashlib.sha256(
        spec.model_dump_json().encode("utf-8")
    ).hexdigest()

    created = jobs.create(
        job_id="cadjob_1",
        project_id=workspace.project.id,
        cad_run_id="cad_1",
        client_request_id="client_1",
        source_message_id=None,
        project_expert_id=None,
        spec_run_id=None,
        request_hash=request_hash,
        request=spec,
        created_at="2026-07-13T00:00:00+00:00",
    )
    duplicate = jobs.create(
        job_id="ignored_duplicate_id",
        project_id=workspace.project.id,
        cad_run_id="cad_1",
        client_request_id="client_1",
        source_message_id=None,
        project_expert_id=None,
        spec_run_id=None,
        request_hash=request_hash,
        request=spec,
        created_at="2026-07-13T00:00:01+00:00",
    )
    assert created.status == CadJobStatus.QUEUED
    assert duplicate.id == created.id

    running = jobs.mark_running("cadjob_1", "2026-07-13T00:00:02+00:00")
    jobs.update_progress("cadjob_1", CadJobPhase.BUILDING, 40)
    completed = jobs.finish_success(
        "cadjob_1",
        {
            "manifest": {
                "schemaVersion": "1.0",
                "engineId": "zhangwen-cad-engine",
                "engineVersion": "2.8.0",
                "designId": "cadjob_1",
                "specSha256": "a" * 64,
            },
            "files": [
                {
                    "id": "artifact_file_1",
                    "role": "GLB_PREVIEW",
                    "fileName": "preview.glb",
                    "mimeType": "model/gltf-binary",
                    "byteSize": 12,
                    "sha256": "b" * 64,
                }
            ],
            "validation": {"ok": True, "checks": []},
            "geometrySummary": {},
        },
        "2026-07-13T00:00:03+00:00",
    )

    assert running.status == CadJobStatus.RUNNING
    assert completed.status == CadJobStatus.SUCCEEDED
    assert completed.progress == 100
    assert completed.result is not None
    assert completed.result.files[0].role.value == "GLB_PREVIEW"
    with projects._connect() as conn:
        run = conn.execute(
            "SELECT status, latest_job_id FROM cad_runs WHERE id='cad_1'"
        ).fetchone()
    assert tuple(run) == ("READY_FOR_REVIEW", "cadjob_1")

    # A late failure from the already completed Job must not regress the CadRun.
    unchanged = jobs.finish_error(
        "cadjob_1",
        status=CadJobStatus.FAILED,
        code="LATE_ERROR",
        message="late worker event",
        retryable=True,
        completed_at="2026-07-13T00:00:04+00:00",
    )
    assert unchanged.status == CadJobStatus.SUCCEEDED
    with projects._connect() as conn:
        assert conn.execute(
            "SELECT status FROM cad_runs WHERE id='cad_1'"
        ).fetchone()[0] == "READY_FOR_REVIEW"


def test_job_repository_rejects_conflicting_idempotency_key(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("CAD", "生成盒体")
    _draft_run(projects, workspace.project.id, "cad_1")
    jobs = CadJobRepository(projects.db_path)
    spec = _build_spec("cadjob_1", workspace.project.id)
    jobs.create(
        job_id="cadjob_1",
        project_id=workspace.project.id,
        cad_run_id="cad_1",
        client_request_id="same-client-key",
        source_message_id=None,
        project_expert_id=None,
        spec_run_id=None,
        request_hash="a" * 64,
        request=spec,
        created_at="2026-07-13T00:00:00+00:00",
    )

    with pytest.raises(ValueError, match="CAD_CLIENT_REQUEST_CONFLICT"):
        jobs.create(
            job_id="cadjob_2",
            project_id=workspace.project.id,
            cad_run_id="cad_1",
            client_request_id="same-client-key",
            source_message_id=None,
            project_expert_id=None,
            spec_run_id=None,
            request_hash="b" * 64,
            request=_build_spec("cadjob_2", workspace.project.id),
            created_at="2026-07-13T00:00:01+00:00",
        )


def test_recovery_interrupts_running_job_and_only_its_latest_run(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("CAD", "生成盒体")
    _draft_run(projects, workspace.project.id, "cad_recovery")
    jobs = CadJobRepository(projects.db_path)
    spec = _build_spec("cadjob_recovery", workspace.project.id)
    jobs.create(
        job_id="cadjob_recovery",
        project_id=workspace.project.id,
        cad_run_id="cad_recovery",
        client_request_id=None,
        source_message_id=None,
        project_expert_id=None,
        spec_run_id=None,
        request_hash="c" * 64,
        request=spec,
        created_at="2026-07-13T00:00:00+00:00",
    )
    jobs.mark_running("cadjob_recovery", "2026-07-13T00:00:01+00:00")

    assert jobs.recover_interrupted("2026-07-13T00:00:02+00:00") == 1

    recovered = jobs.get(workspace.project.id, "cadjob_recovery")
    assert recovered.status == CadJobStatus.INTERRUPTED
    assert recovered.error is not None and recovered.error.retryable
    with projects._connect() as conn:
        assert conn.execute(
            "SELECT status FROM cad_runs WHERE id = 'cad_recovery'"
        ).fetchone()[0] == "FAILED"
