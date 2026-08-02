from __future__ import annotations

import hashlib

from zhangwen.cad_agent.artifact_store import ArtifactFileStore, EXPECTED_FILES
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import CadDraft, CadJobStatus, CadRunStatus
from zhangwen.cad_agent.repository import CadRepository
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


def _manifest(staging, job_id: str) -> dict[str, object]:
    files: list[dict[str, object]] = []
    bounds = {
        "min_x": 0.0,
        "min_y": 0.0,
        "min_z": 0.0,
        "max_x": 10.0,
        "max_y": 10.0,
        "max_z": 10.0,
    }
    for file_name, (role, mime_type) in EXPECTED_FILES.items():
        content = f"validated:{file_name}".encode("utf-8")
        (staging / file_name).write_bytes(content)
        files.append(
            {
                "relativePath": file_name,
                "fileName": file_name,
                "role": role,
                "mimeType": mime_type,
                "byteSize": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "triangleCount": 4 if file_name.endswith((".stl", ".glb")) else None,
                "bounds": bounds if file_name.endswith((".step", ".stl", ".glb")) else None,
            }
        )
    return {
        "schemaVersion": "1.0",
        "engineId": "zhangwen-cad-engine",
        "engineVersion": "2.8.0",
        "designId": job_id,
        "specSha256": "a" * 64,
        "files": files,
    }


def test_success_finalizer_commits_job_run_and_binary_metadata_together(tmp_path) -> None:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project_from_idea(
        idea="生成盒体",
        project_name="CAD",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    source_message = workspace.conversation.messages[0]
    expert = workspace.experts[0]
    repository = CadRepository(projects.db_path)
    cad_run = repository.create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={"width": 80, "depth": 60, "height": 30},
            components=[],
            constraints={"process": "FDM", "minWallThicknessMm": 1.6},
            summary="盒体与盖板",
        ),
        source_message_id=source_message.id,
        generated_by_expert_id=expert.id,
    )
    job = repository.create_job(
        project_id=workspace.project.id,
        cad_run_id=cad_run.id,
        client_request_id="finalizer-1",
    )
    CadJobRepository(projects.db_path).mark_running(
        job.id,
        "2026-07-13T00:00:00+00:00",
    )

    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging(job.id)
    manifest = _manifest(staging, job.id)
    published = store.publish(
        job_id=job.id,
        project_id=workspace.project.id,
        artifact_id=f"artifact_cad_{workspace.project.id}",
        version_id=(
            f"artifact_version_artifact_cad_{workspace.project.id}_{cad_run.id}"
        ),
        files=store.validate_manifest(job.id, manifest),
    )

    finalized = repository.finalize_job_success(
        job_id=job.id,
        worker_result={
            "manifest": manifest,
            "validation": {
                "ok": True,
                "checks": [
                    {
                        "check_id": "solid_valid",
                        "status": "pass",
                        "message": "实体有效",
                        "evidence": [],
                    }
                ],
            },
            "geometrySummary": {},
        },
        published_files=published,
    )

    assert finalized.status == CadRunStatus.READY_FOR_REVIEW
    assert finalized.latestJob is not None
    assert finalized.latestJob.status == CadJobStatus.SUCCEEDED
    assert finalized.artifactId is not None
    assert finalized.artifactVersionId is not None
    assert len(finalized.files) == len(EXPECTED_FILES)
    with projects._connect() as conn:
        assert conn.execute("SELECT COUNT(*) FROM artifact_files").fetchone()[0] == len(
            EXPECTED_FILES
        )
        assert conn.execute(
            "SELECT COUNT(*) FROM cad_files WHERE content IS NOT NULL"
        ).fetchone()[0] == 0
        assert conn.execute(
            "SELECT status FROM artifact_versions WHERE id = ?",
            (finalized.artifactVersionId,),
        ).fetchone()[0] == "NEEDS_REVIEW"
