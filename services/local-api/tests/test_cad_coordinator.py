from __future__ import annotations

import asyncio
import hashlib
import inspect
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest

from zhangwen.cad_agent.artifact_store import ArtifactFileStore, EXPECTED_FILES
from zhangwen.cad_agent.coordinator import CadJobCoordinator
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import (
    CadBuildSpec,
    CadDraft,
    CadJob,
    CadJobPhase,
    CadJobStatus,
    CadRun,
    CadRunStatus,
)
from zhangwen.cad_agent.repository import (
    CadRepository,
    cad_artifact_id,
    cad_artifact_version_id,
)
from zhangwen.cad_agent.worker_client import CadWorkerError
from zhangwen.cad_agent.worker_protocol import canonical_json_bytes
from zhangwen.projects.repository import ProjectRepository


@dataclass(frozen=True)
class _CadFixture:
    projects: ProjectRepository
    cad: CadRepository
    cad_run: CadRun
    job: CadJob


class _ControlledWorker:
    def __init__(self, *, validation_ok: bool = True, block: bool = True) -> None:
        self.validation_ok = validation_ok
        self.block = block
        self.started = asyncio.Event()
        self.release = asyncio.Event()
        self.cancel_requested = asyncio.Event()
        self.exited = asyncio.Event()

    async def run(
        self,
        job_id: str,
        *,
        request: CadBuildSpec,
        staging_dir: Path,
        on_progress: Any = None,
    ) -> dict[str, Any]:
        self.started.set()
        try:
            await _report_progress(on_progress, CadJobPhase.BUILDING, 50)
            if self.block:
                release_task = asyncio.create_task(self.release.wait())
                cancel_task = asyncio.create_task(self.cancel_requested.wait())
                done, pending = await asyncio.wait(
                    {release_task, cancel_task},
                    return_when=asyncio.FIRST_COMPLETED,
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*pending, return_exceptions=True)
                if cancel_task in done and cancel_task.result():
                    raise CadWorkerError(
                        "CAD_WORKER_CANCELED",
                        "CAD Worker canceled by test coordinator.",
                        retryable=True,
                    )
            return _write_worker_result(
                job_id,
                request,
                staging_dir,
                validation_ok=self.validation_ok,
            )
        finally:
            self.exited.set()

    async def cancel(self, job_id: str) -> bool:
        del job_id
        self.cancel_requested.set()
        return True


@pytest.mark.asyncio
async def test_coordinator_runs_job_and_atomically_publishes_artifact_files(
    tmp_path: Path,
) -> None:
    fixture = _create_cad_job(tmp_path, client_request_id="coordinator-success")
    jobs = CadJobRepository(fixture.projects.db_path)
    worker = _ControlledWorker()
    coordinator = CadJobCoordinator(fixture.projects.db_path, tmp_path)
    coordinator._worker = worker

    assert fixture.job.status == CadJobStatus.QUEUED
    assert fixture.cad.get_cad(
        fixture.job.projectId,
        fixture.cad_run.id,
    ).status == CadRunStatus.QUEUED
    await coordinator.start()
    try:
        await asyncio.wait_for(worker.started.wait(), timeout=3)
        running = jobs.get(fixture.job.projectId, fixture.job.id)
        running_run = fixture.cad.get_cad(fixture.job.projectId, fixture.cad_run.id)
        assert running.status == CadJobStatus.RUNNING
        assert running_run.status == CadRunStatus.RUNNING

        worker.release.set()
        completed = await _wait_for_job_status(
            jobs,
            fixture.job.projectId,
            fixture.job.id,
            CadJobStatus.SUCCEEDED,
        )
        completed_run = fixture.cad.get_cad(fixture.job.projectId, fixture.cad_run.id)

        assert completed.phase == CadJobPhase.COMPLETED
        assert completed.progress == 100
        assert completed_run.status == CadRunStatus.READY_FOR_REVIEW
        assert completed_run.artifactId == cad_artifact_id(fixture.job.projectId)
        assert completed_run.artifactVersionId == cad_artifact_version_id(
            fixture.job.projectId,
            fixture.cad_run.id,
        )
        with fixture.projects._connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM artifact_files").fetchone()[0] == len(
                EXPECTED_FILES
            )
            assert conn.execute(
                "SELECT COUNT(*) FROM cad_files WHERE content IS NOT NULL"
            ).fetchone()[0] == 0
        assert _published_directory(fixture, tmp_path).is_dir()
        assert not _staging_directory(fixture, tmp_path).exists()
    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_coordinator_cancel_stops_worker_and_finishes_canceled(
    tmp_path: Path,
) -> None:
    fixture = _create_cad_job(tmp_path, client_request_id="coordinator-cancel")
    jobs = CadJobRepository(fixture.projects.db_path)
    worker = _ControlledWorker()
    coordinator = CadJobCoordinator(fixture.projects.db_path, tmp_path)
    coordinator._worker = worker

    await coordinator.start()
    try:
        await asyncio.wait_for(worker.started.wait(), timeout=3)
        requested = await coordinator.cancel(fixture.job.projectId, fixture.job.id)
        assert requested.status in {
            CadJobStatus.CANCEL_REQUESTED,
            CadJobStatus.CANCELED,
        }
        await asyncio.wait_for(worker.exited.wait(), timeout=3)
        canceled = await _wait_for_job_status(
            jobs,
            fixture.job.projectId,
            fixture.job.id,
            CadJobStatus.CANCELED,
        )
        canceled_run = fixture.cad.get_cad(fixture.job.projectId, fixture.cad_run.id)

        assert worker.cancel_requested.is_set()
        assert canceled.phase == CadJobPhase.CANCELED
        assert canceled_run.status == CadRunStatus.CANCELED
        assert not _staging_directory(fixture, tmp_path).exists()
        assert not _published_directory(fixture, tmp_path).exists()
    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_coordinator_start_recovers_running_job_as_interrupted(
    tmp_path: Path,
) -> None:
    fixture = _create_cad_job(tmp_path, client_request_id="coordinator-recovery")
    jobs = CadJobRepository(fixture.projects.db_path)
    jobs.mark_running(fixture.job.id, "2026-07-13T00:00:00+00:00")
    store = ArtifactFileStore(tmp_path)
    staging = store.prepare_staging(fixture.job.id)
    (staging / "partial.tmp").write_bytes(b"partial")
    coordinator = CadJobCoordinator(fixture.projects.db_path, tmp_path)

    await coordinator.start()
    try:
        recovered = jobs.get(fixture.job.projectId, fixture.job.id)
        recovered_run = fixture.cad.get_cad(fixture.job.projectId, fixture.cad_run.id)

        assert recovered.status == CadJobStatus.INTERRUPTED
        assert recovered.phase == CadJobPhase.FAILED
        assert recovered.error is not None
        assert recovered.error.code == "CAD_WORKER_INTERRUPTED"
        assert recovered.error.retryable is True
        assert recovered_run.status == CadRunStatus.FAILED
        assert not staging.exists()
    finally:
        await coordinator.stop()


@pytest.mark.asyncio
async def test_coordinator_removes_published_files_when_finalize_fails(
    tmp_path: Path,
) -> None:
    fixture = _create_cad_job(tmp_path, client_request_id="coordinator-finalize-failure")
    jobs = CadJobRepository(fixture.projects.db_path)
    worker = _ControlledWorker(validation_ok=False, block=False)
    coordinator = CadJobCoordinator(fixture.projects.db_path, tmp_path)
    coordinator._worker = worker

    await coordinator.start()
    try:
        failed = await _wait_for_job_status(
            jobs,
            fixture.job.projectId,
            fixture.job.id,
            CadJobStatus.FAILED,
        )
        failed_run = fixture.cad.get_cad(fixture.job.projectId, fixture.cad_run.id)

        assert worker.exited.is_set()
        assert failed.error is not None
        assert failed.error.code == "CAD_JOB_FINALIZE_FAILED"
        assert failed_run.status == CadRunStatus.FAILED
        with fixture.projects._connect() as conn:
            assert conn.execute("SELECT COUNT(*) FROM artifact_files").fetchone()[0] == 0
        assert not _published_directory(fixture, tmp_path).exists()
        assert not _staging_directory(fixture, tmp_path).exists()
        assert not (
            tmp_path / "cad" / "staging" / f"publish-{fixture.job.id}"
        ).exists()
    finally:
        await coordinator.stop()


def _create_cad_job(tmp_path: Path, *, client_request_id: str) -> _CadFixture:
    projects = ProjectRepository(tmp_path)
    workspace = projects.create_project("CAD Coordinator", "Build a deterministic enclosure")
    cad = CadRepository(projects.db_path)
    cad_run = cad.create_draft(
        project_id=workspace.project.id,
        draft=CadDraft(
            templateKind="BOX_WITH_LID",
            parameters={"width": 80, "depth": 60, "height": 30},
            components=[],
            constraints={"process": "FDM", "minWallThicknessMm": 1.6},
            summary="Deterministic enclosure",
        ),
        source_message_id=workspace.conversation.messages[0].id,
        generated_by_expert_id=workspace.experts[0].id,
    )
    job = cad.create_job(
        project_id=workspace.project.id,
        cad_run_id=cad_run.id,
        client_request_id=client_request_id,
    )
    return _CadFixture(projects=projects, cad=cad, cad_run=cad_run, job=job)


def _write_worker_result(
    job_id: str,
    request: CadBuildSpec,
    staging_dir: Path,
    *,
    validation_ok: bool,
) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for file_name, (role, mime_type) in EXPECTED_FILES.items():
        content = f"coordinator:{job_id}:{file_name}".encode("utf-8")
        output = staging_dir / file_name
        output.write_bytes(content)
        files.append(
            {
                "relativePath": file_name,
                "fileName": file_name,
                "role": role,
                "mimeType": mime_type,
                "byteSize": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
                "triangleCount": 4 if file_name.endswith((".stl", ".glb")) else None,
                "bounds": None,
            }
        )
    return {
        "manifest": {
            "schemaVersion": "1.0",
            "engineId": "zhangwen-cad-engine",
            "engineVersion": "2.8.0",
            "designId": job_id,
            "specSha256": hashlib.sha256(canonical_json_bytes(request)).hexdigest(),
            "files": files,
        },
        "validation": {
            "ok": validation_ok,
            "checks": [
                {
                    "check_id": "solid_valid",
                    "status": "pass" if validation_ok else "fail",
                    "message": "Solid validated" if validation_ok else "Forced failure",
                    "evidence": [],
                }
            ],
        },
        "geometrySummary": {},
    }


async def _report_progress(callback: Any, phase: CadJobPhase, progress: int) -> None:
    if callback is None:
        return
    result = callback(phase, progress)
    if inspect.isawaitable(result):
        await result


async def _wait_for_job_status(
    jobs: CadJobRepository,
    project_id: str,
    job_id: str,
    expected: CadJobStatus,
) -> CadJob:
    async with asyncio.timeout(5):
        while True:
            job = jobs.get(project_id, job_id)
            if job.status == expected:
                return job
            await asyncio.sleep(0.01)


def _staging_directory(fixture: _CadFixture, data_dir: Path) -> Path:
    return data_dir / "cad" / "staging" / fixture.job.id


def _published_directory(fixture: _CadFixture, data_dir: Path) -> Path:
    return (
        data_dir
        / "artifact-files"
        / fixture.job.projectId
        / cad_artifact_id(fixture.job.projectId)
        / cad_artifact_version_id(fixture.job.projectId, fixture.cad_run.id)
    )
