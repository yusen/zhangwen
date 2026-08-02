"""Single-concurrency coordinator for persistent CAD jobs."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.cad_agent.artifact_store import ArtifactFileStore
from zhangwen.cad_agent.chat_projection import sync_cad_message_projection
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import CadJob, CadJobStatus
from zhangwen.cad_agent.repository import (
    CadRepository,
    cad_artifact_id,
    cad_artifact_version_id,
)
from zhangwen.cad_agent.worker_client import CadWorkerClient, CadWorkerError


class CadJobCoordinator:
    def __init__(self, db_path: Path, data_dir: Path) -> None:
        self.db_path = db_path.resolve()
        self.data_dir = data_dir.resolve()
        self._jobs = CadJobRepository(self.db_path)
        self._cad = CadRepository(self.db_path)
        self._store = ArtifactFileStore(self.data_dir)
        self._worker = CadWorkerClient()
        self._wake = asyncio.Event()
        self._shutdown = asyncio.Event()
        self._runner: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._runner is not None and not self._runner.done():
            return
        interrupted = self._jobs.active_jobs()
        self._jobs.recover_interrupted(_now())
        for job in interrupted:
            self._cleanup_interrupted(job)
            sync_cad_message_projection(
                self.db_path,
                self._cad.get_cad(job.projectId, job.cadRunId),
            )
        self._shutdown.clear()
        self._runner = asyncio.create_task(self._run_loop(), name="cad-job-coordinator")
        self._wake.set()

    async def stop(self) -> None:
        self._shutdown.set()
        self._wake.set()
        runner = self._runner
        self._runner = None
        if runner is None:
            return
        runner.cancel()
        with suppress(asyncio.CancelledError):
            await runner

    def submit(self, job: CadJob) -> CadJob:
        self._wake.set()
        return job

    async def cancel(self, project_id: str, job_id: str) -> CadJob:
        job = self._jobs.request_cancel(project_id, job_id, _now())
        if job.status == CadJobStatus.CANCEL_REQUESTED:
            await self._worker.cancel(job_id)
        self._wake.set()
        current = self._jobs.get(project_id, job_id)
        if current.status == CadJobStatus.CANCELED:
            sync_cad_message_projection(
                self.db_path,
                self._cad.get_cad(project_id, current.cadRunId),
            )
        return current

    def retry(
        self,
        *,
        project_id: str,
        job_id: str,
        client_request_id: str | None,
    ) -> CadJob:
        job = self._cad.retry_job(
            project_id=project_id,
            job_id=job_id,
            client_request_id=client_request_id,
        )
        return self.submit(job)

    async def _run_loop(self) -> None:
        while not self._shutdown.is_set():
            self._wake.clear()
            queued_ids = self._jobs.queued_ids()
            if not queued_ids:
                await self._wake.wait()
                continue
            for job_id in queued_ids:
                if self._shutdown.is_set():
                    return
                try:
                    await self._execute(job_id)
                except asyncio.CancelledError:
                    await self._worker.cancel(job_id)
                    raise
                except Exception as exc:
                    self._finish_unexpected(job_id, exc)

    async def _execute(self, job_id: str) -> None:
        job = self._jobs.mark_running(job_id, _now())
        staging = self._store.prepare_staging(job_id)
        published = False
        artifact_id = cad_artifact_id(job.projectId)
        version_id = cad_artifact_version_id(job.projectId, job.cadRunId)
        try:
            result = await self._worker.run(
                job_id,
                request=job.request,
                staging_dir=staging,
                on_progress=lambda phase, progress: self._jobs.update_progress(
                    job_id,
                    phase,
                    progress,
                ),
            )
            manifest = result.get("manifest")
            if not isinstance(manifest, dict):
                raise CadWorkerError(
                    "CAD_WORKER_PROTOCOL_INVALID",
                    "CAD Worker 未返回有效 manifest。",
                    retryable=False,
                )
            validated = self._store.validate_manifest(
                job_id,
                manifest,
                expected_design_id=job.id,
                expected_spec_sha256=job.requestHash,
            )
            files = self._store.publish(
                job_id=job_id,
                project_id=job.projectId,
                artifact_id=artifact_id,
                version_id=version_id,
                files=validated,
            )
            published = True
            self._cad.finalize_job_success(
                job_id=job_id,
                worker_result=result,
                published_files=files,
            )
        except asyncio.CancelledError:
            if published:
                self._remove_published(job.projectId, artifact_id, version_id)
            raise
        except CadWorkerError as exc:
            if published:
                self._remove_published(job.projectId, artifact_id, version_id)
            current = self._jobs.get(job.projectId, job_id)
            status = (
                CadJobStatus.CANCELED
                if current.status == CadJobStatus.CANCEL_REQUESTED
                else CadJobStatus.TIMED_OUT
                if exc.code == "CAD_WORKER_TIMED_OUT"
                else CadJobStatus.FAILED
            )
            self._jobs.finish_error(
                job_id,
                status=status,
                code=exc.code,
                message=exc.message,
                retryable=exc.retryable,
                completed_at=_now(),
            )
            sync_cad_message_projection(
                self.db_path,
                self._cad.get_cad(job.projectId, job.cadRunId),
            )
        except Exception as exc:
            if published:
                self._remove_published(job.projectId, artifact_id, version_id)
            current = self._jobs.get(job.projectId, job_id)
            intake_revised = str(exc) == "CAD_INTAKE_REVISED"
            self._jobs.finish_error(
                job_id,
                status=(
                    CadJobStatus.CANCELED
                    if current.status == CadJobStatus.CANCEL_REQUESTED
                    else CadJobStatus.FAILED
                ),
                code=(
                    "CAD_INTAKE_REVISED"
                    if intake_revised
                    else "CAD_JOB_FINALIZE_FAILED"
                ),
                message=(
                    "CAD 结构输入已更新，旧 Worker 结果已丢弃。"
                    if intake_revised
                    else f"{type(exc).__name__}: {exc}"
                ),
                retryable=not intake_revised,
                completed_at=_now(),
            )
            sync_cad_message_projection(
                self.db_path,
                self._cad.get_cad(job.projectId, job.cadRunId),
            )
        finally:
            with suppress(ValueError, OSError):
                self._store.discard_publish_staging(job_id)
            with suppress(ValueError, OSError):
                self._store.discard_staging(job_id)

    def _finish_unexpected(self, job_id: str, exc: Exception) -> None:
        with suppress(ValueError):
            job = self._jobs.get_by_id(job_id)
            self._jobs.finish_error(
                job_id,
                status=CadJobStatus.FAILED,
                code="CAD_COORDINATOR_ERROR",
                message=f"{type(exc).__name__}: {exc}",
                retryable=True,
                completed_at=_now(),
            )
            sync_cad_message_projection(
                self.db_path,
                self._cad.get_cad(job.projectId, job.cadRunId),
            )

    def _cleanup_interrupted(self, job: CadJob) -> None:
        with suppress(ValueError, OSError):
            self._store.discard_publish_staging(job.id)
        with suppress(ValueError, OSError):
            self._store.discard_staging(job.id)
        artifact_id = cad_artifact_id(job.projectId)
        version_id = cad_artifact_version_id(job.projectId, job.cadRunId)
        self._remove_published(job.projectId, artifact_id, version_id)

    def _remove_published(
        self,
        project_id: str,
        artifact_id: str,
        version_id: str,
    ) -> None:
        # A committed finalizer always owns at least one artifact_files row.
        import sqlite3

        with sqlite3.connect(self.db_path) as conn:
            referenced = conn.execute(
                "SELECT 1 FROM artifact_files WHERE artifact_version_id = ? LIMIT 1",
                (version_id,),
            ).fetchone()
        if referenced is None:
            with suppress(ValueError, OSError):
                self._store.remove_published(
                    project_id=project_id,
                    artifact_id=artifact_id,
                    version_id=version_id,
                )


def _now() -> str:
    return datetime.now(UTC).isoformat()
