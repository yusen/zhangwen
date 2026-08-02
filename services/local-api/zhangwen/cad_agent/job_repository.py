"""Persistent state transitions for deterministic CAD worker jobs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from zhangwen.cad_agent.models import (
    CadBuildSpec,
    CadJob,
    CadJobError,
    CadJobPhase,
    CadJobStatus,
    CadRunStatus,
)
from zhangwen.cad_agent.intake import assert_current_cad_intake_revision


ACTIVE_JOB_STATUSES = (
    CadJobStatus.QUEUED.value,
    CadJobStatus.RUNNING.value,
    CadJobStatus.CANCEL_REQUESTED.value,
)


class CadJobRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create(
        self,
        *,
        job_id: str,
        project_id: str,
        cad_run_id: str,
        client_request_id: str | None,
        source_message_id: str | None,
        project_expert_id: str | None,
        spec_run_id: str | None,
        request_hash: str,
        request: CadBuildSpec,
        created_at: str,
    ) -> CadJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = None
            if client_request_id:
                existing = conn.execute(
                    """
                    SELECT * FROM cad_jobs
                    WHERE project_id = ? AND client_request_id = ?
                    """,
                    (project_id, client_request_id),
                ).fetchone()
            run = conn.execute(
                "SELECT project_id, status, created_at FROM cad_runs WHERE id = ?",
                (cad_run_id,),
            ).fetchone()
            if run is None or str(run["project_id"]) != project_id:
                raise ValueError("CAD_RUN_PROJECT_MISMATCH")
            assert_current_cad_intake_revision(
                conn,
                project_id=project_id,
                draft=request,
                run_created_at=str(run["created_at"]),
            )
            if existing is not None:
                if (
                    str(existing["request_hash"]) != request_hash
                    or str(existing["cad_run_id"]) != cad_run_id
                ):
                    raise ValueError("CAD_CLIENT_REQUEST_CONFLICT")
                return _to_job(existing)
            if request.jobId != job_id or request.projectId != project_id:
                raise ValueError("CAD_JOB_REQUEST_MISMATCH")
            if str(run["status"]) not in {
                CadRunStatus.DRAFT.value,
                CadRunStatus.FAILED.value,
                CadRunStatus.CANCELED.value,
            }:
                raise ValueError("CAD_RUN_NOT_BUILDABLE")
            queued = conn.execute(
                "SELECT COUNT(*) FROM cad_jobs WHERE status IN (?, ?, ?)",
                ACTIVE_JOB_STATUSES,
            ).fetchone()[0]
            if int(queued) >= 8:
                raise ValueError("CAD_JOB_QUEUE_FULL")
            project_active = conn.execute(
                """
                SELECT COUNT(*) FROM cad_jobs
                WHERE project_id = ? AND status IN (?, ?, ?)
                """,
                (project_id, *ACTIVE_JOB_STATUSES),
            ).fetchone()[0]
            if int(project_active) >= 1:
                raise ValueError("CAD_PROJECT_JOB_ACTIVE")
            conn.execute(
                """
                INSERT INTO cad_jobs (
                  id, project_id, cad_run_id, client_request_id, status, phase,
                  progress, source_message_id, project_expert_id, spec_run_id,
                  request_hash, request_json, result_json, error_json,
                  created_at, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?, ?, ?, NULL, NULL, ?, NULL, NULL)
                """,
                (
                    job_id,
                    project_id,
                    cad_run_id,
                    client_request_id,
                    CadJobStatus.QUEUED.value,
                    CadJobPhase.QUEUED.value,
                    source_message_id,
                    project_expert_id,
                    spec_run_id,
                    request_hash,
                    request.model_dump_json(),
                    created_at,
                ),
            )
            updated_run = conn.execute(
                """
                UPDATE cad_runs
                SET status = ?, latest_job_id = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    CadRunStatus.QUEUED.value,
                    job_id,
                    created_at,
                    cad_run_id,
                    project_id,
                ),
            ).rowcount
            if updated_run != 1:
                raise ValueError("CAD_RUN_PROJECT_MISMATCH")
            return self._row(conn, project_id, job_id)

    def get(self, project_id: str, job_id: str) -> CadJob:
        with self._connect() as conn:
            return self._row(conn, project_id, job_id)

    def get_by_id(self, job_id: str) -> CadJob:
        with self._connect() as conn:
            return self._row_by_id(conn, job_id)

    def queued_ids(self) -> list[str]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id FROM cad_jobs
                WHERE status = ?
                ORDER BY created_at, id
                """,
                (CadJobStatus.QUEUED.value,),
            ).fetchall()
        return [str(row["id"]) for row in rows]

    def active_jobs(self) -> list[CadJob]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM cad_jobs
                WHERE status IN (?, ?)
                ORDER BY created_at, id
                """,
                (
                    CadJobStatus.RUNNING.value,
                    CadJobStatus.CANCEL_REQUESTED.value,
                ),
            ).fetchall()
        return [_to_job(row) for row in rows]

    def mark_running(self, job_id: str, started_at: str) -> CadJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            updated = conn.execute(
                """
                UPDATE cad_jobs
                SET status = ?, phase = ?, progress = 1, started_at = ?
                WHERE id = ? AND status = ?
                  AND EXISTS (
                    SELECT 1 FROM cad_runs
                    WHERE cad_runs.id = cad_jobs.cad_run_id
                      AND cad_runs.latest_job_id = cad_jobs.id
                      AND cad_runs.status = ?
                  )
                """,
                (
                    CadJobStatus.RUNNING.value,
                    CadJobPhase.VALIDATING.value,
                    started_at,
                    job_id,
                    CadJobStatus.QUEUED.value,
                    CadRunStatus.QUEUED.value,
                ),
            ).rowcount
            if updated != 1:
                raise ValueError("CAD_JOB_NOT_QUEUED")
            row = self._row_by_id(conn, job_id)
            conn.execute(
                """
                UPDATE cad_runs SET status = ?, updated_at = ?
                WHERE id = ? AND latest_job_id = ? AND status = ?
                """,
                (
                    CadRunStatus.RUNNING.value,
                    started_at,
                    row.cadRunId,
                    job_id,
                    CadRunStatus.QUEUED.value,
                ),
            )
            return row

    def update_progress(
        self,
        job_id: str,
        phase: CadJobPhase,
        progress: int,
    ) -> None:
        if not 1 <= progress <= 99:
            raise ValueError("CAD Job progress must be between 1 and 99")
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE cad_jobs SET phase = ?, progress = ?
                WHERE id = ? AND status = ? AND progress <= ?
                """,
                (
                    phase.value,
                    progress,
                    job_id,
                    CadJobStatus.RUNNING.value,
                    progress,
                ),
            )

    def request_cancel(self, project_id: str, job_id: str, now: str) -> CadJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row(conn, project_id, job_id)
            if row.status == CadJobStatus.QUEUED:
                conn.execute(
                    """
                    UPDATE cad_jobs
                    SET status = ?, phase = ?, completed_at = ?
                    WHERE id = ?
                    """,
                    (
                        CadJobStatus.CANCELED.value,
                        CadJobPhase.CANCELED.value,
                        now,
                        job_id,
                    ),
                )
                conn.execute(
                    """
                    UPDATE cad_runs SET status = ?, updated_at = ?
                    WHERE id = ? AND latest_job_id = ?
                    """,
                    (CadRunStatus.CANCELED.value, now, row.cadRunId, job_id),
                )
            elif row.status in {CadJobStatus.RUNNING, CadJobStatus.CANCEL_REQUESTED}:
                conn.execute(
                    "UPDATE cad_jobs SET status = ? WHERE id = ?",
                    (CadJobStatus.CANCEL_REQUESTED.value, job_id),
                )
            return self._row(conn, project_id, job_id)

    def finish_success(
        self,
        job_id: str,
        result: dict[str, Any],
        completed_at: str,
    ) -> CadJob:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            return self.finish_success_with_conn(conn, job_id, result, completed_at)

    def finish_success_with_conn(
        self,
        conn: sqlite3.Connection,
        job_id: str,
        result: dict[str, Any],
        completed_at: str,
    ) -> CadJob:
        row = self._row_by_id(conn, job_id)
        updated = conn.execute(
                """
                UPDATE cad_jobs
                SET status = ?, phase = ?, progress = 100, result_json = ?,
                    error_json = NULL, completed_at = ?
                WHERE id = ? AND status = ?
                  AND EXISTS (
                    SELECT 1 FROM cad_runs
                    WHERE cad_runs.id = cad_jobs.cad_run_id
                      AND cad_runs.latest_job_id = cad_jobs.id
                  )
                """,
                (
                    CadJobStatus.SUCCEEDED.value,
                    CadJobPhase.COMPLETED.value,
                    json.dumps(result, ensure_ascii=False, sort_keys=True),
                    completed_at,
                    job_id,
                    CadJobStatus.RUNNING.value,
                ),
            ).rowcount
        if updated != 1:
            raise ValueError("CAD_JOB_NOT_RUNNING")
        run_updated = conn.execute(
                """
                UPDATE cad_runs SET status = ?, stale_reason = NULL, updated_at = ?
                WHERE id = ? AND latest_job_id = ? AND status = ?
                """,
                (
                    CadRunStatus.READY_FOR_REVIEW.value,
                    completed_at,
                    row.cadRunId,
                    job_id,
                    CadRunStatus.RUNNING.value,
                ),
            ).rowcount
        if run_updated != 1:
            raise ValueError("CAD_RUN_NOT_RUNNING")
        return self._row(conn, row.projectId, job_id)

    def finish_error(
        self,
        job_id: str,
        *,
        status: CadJobStatus,
        code: str,
        message: str,
        retryable: bool,
        completed_at: str,
    ) -> CadJob:
        if status not in {
            CadJobStatus.CANCELED,
            CadJobStatus.FAILED,
            CadJobStatus.TIMED_OUT,
            CadJobStatus.INTERRUPTED,
        }:
            raise ValueError("Invalid terminal CAD Job status")
        phase = CadJobPhase.CANCELED if status == CadJobStatus.CANCELED else CadJobPhase.FAILED
        error = CadJobError(code=code, message=message, retryable=retryable)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row_by_id(conn, job_id)
            updated = conn.execute(
                """
                UPDATE cad_jobs
                SET status = ?, phase = ?, error_json = ?, completed_at = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (
                    status.value,
                    phase.value,
                    error.model_dump_json(),
                    completed_at,
                    job_id,
                    CadJobStatus.RUNNING.value,
                    CadJobStatus.CANCEL_REQUESTED.value,
                ),
            ).rowcount
            if updated != 1:
                return self._row(conn, row.projectId, job_id)
            run_status = (
                CadRunStatus.CANCELED
                if status == CadJobStatus.CANCELED
                else CadRunStatus.FAILED
            )
            run_row = conn.execute(
                "SELECT created_at FROM cad_runs WHERE id = ? AND project_id = ?",
                (row.cadRunId, row.projectId),
            ).fetchone()
            if run_row is not None:
                try:
                    assert_current_cad_intake_revision(
                        conn,
                        project_id=row.projectId,
                        draft=row.request,
                        run_created_at=str(run_row["created_at"]),
                    )
                except ValueError as exc:
                    if str(exc) != "CAD_INTAKE_REVISED":
                        raise
                    run_status = CadRunStatus.STALE
            if run_status == CadRunStatus.STALE:
                revised_error = CadJobError(
                    code="CAD_INTAKE_REVISED",
                    message="CAD 结构输入已更新，旧 Worker 快照不可继续使用。",
                    retryable=False,
                )
                conn.execute(
                    "UPDATE cad_jobs SET error_json = ? WHERE id = ?",
                    (revised_error.model_dump_json(), job_id),
                )
                conn.execute(
                    """
                    UPDATE cad_runs
                    SET status = ?, stale_reason = ?, updated_at = ?
                    WHERE id = ? AND latest_job_id = ?
                    """,
                    (
                        run_status.value,
                        "CAD 结构输入已更新，旧 Worker 快照不可继续使用。",
                        completed_at,
                        row.cadRunId,
                        job_id,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE cad_runs SET status = ?, updated_at = ?
                    WHERE id = ? AND latest_job_id = ?
                    """,
                    (run_status.value, completed_at, row.cadRunId, job_id),
                )
            return self._row(conn, row.projectId, job_id)

    def recover_interrupted(self, now: str) -> int:
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            rows = conn.execute(
                """
                SELECT cj.id, cj.cad_run_id, cj.project_id, cj.request_json,
                       cr.created_at AS run_created_at
                FROM cad_jobs cj
                JOIN cad_runs cr ON cr.id = cj.cad_run_id
                WHERE cj.status IN (?, ?)
                """,
                (
                    CadJobStatus.RUNNING.value,
                    CadJobStatus.CANCEL_REQUESTED.value,
                ),
            ).fetchall()
            for row in rows:
                job_id = str(row["id"])
                run_status = CadRunStatus.FAILED
                error = CadJobError(
                    code="CAD_WORKER_INTERRUPTED",
                    message="掌问上次退出时 CAD Worker 尚未完成。",
                    retryable=True,
                )
                try:
                    assert_current_cad_intake_revision(
                        conn,
                        project_id=str(row["project_id"]),
                        draft=CadBuildSpec.model_validate_json(row["request_json"]),
                        run_created_at=str(row["run_created_at"]),
                    )
                except ValueError as exc:
                    if str(exc) != "CAD_INTAKE_REVISED":
                        raise
                    run_status = CadRunStatus.STALE
                    error = CadJobError(
                        code="CAD_INTAKE_REVISED",
                        message="CAD 结构输入已更新，旧 Worker 快照不可恢复。",
                        retryable=False,
                    )
                conn.execute(
                    """
                    UPDATE cad_jobs
                    SET status = ?, phase = ?, error_json = ?, completed_at = ?
                    WHERE id = ? AND status IN (?, ?)
                    """,
                    (
                        CadJobStatus.INTERRUPTED.value,
                        CadJobPhase.FAILED.value,
                        error.model_dump_json(),
                        now,
                        job_id,
                        CadJobStatus.RUNNING.value,
                        CadJobStatus.CANCEL_REQUESTED.value,
                    ),
                )
                if run_status == CadRunStatus.STALE:
                    conn.execute(
                        """
                        UPDATE cad_runs
                        SET status = ?, stale_reason = ?, updated_at = ?
                        WHERE id = ? AND latest_job_id = ?
                        """,
                        (
                            run_status.value,
                            "CAD 结构输入已更新，旧 Worker 快照不可恢复。",
                            now,
                            str(row["cad_run_id"]),
                            job_id,
                        ),
                    )
                else:
                    conn.execute(
                        """
                        UPDATE cad_runs SET status = ?, updated_at = ?
                        WHERE id = ? AND latest_job_id = ?
                        """,
                        (
                            run_status.value,
                            now,
                            str(row["cad_run_id"]),
                            job_id,
                        ),
                    )
        return len(rows)

    def _row(self, conn: sqlite3.Connection, project_id: str, job_id: str) -> CadJob:
        row = conn.execute(
            "SELECT * FROM cad_jobs WHERE id = ? AND project_id = ?",
            (job_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("CAD Job 不存在。")
        return _to_job(row)

    def _row_by_id(self, conn: sqlite3.Connection, job_id: str) -> CadJob:
        row = conn.execute("SELECT * FROM cad_jobs WHERE id = ?", (job_id,)).fetchone()
        if row is None:
            raise ValueError("CAD Job 不存在。")
        return _to_job(row)


def _to_job(row: sqlite3.Row) -> CadJob:
    request = CadBuildSpec.model_validate_json(row["request_json"])
    error = (
        CadJobError.model_validate_json(row["error_json"])
        if row["error_json"]
        else None
    )
    return CadJob(
        id=row["id"],
        projectId=row["project_id"],
        cadRunId=row["cad_run_id"],
        clientRequestId=row["client_request_id"],
        status=CadJobStatus(row["status"]),
        phase=CadJobPhase(row["phase"]),
        progress=row["progress"],
        sourceMessageId=row["source_message_id"],
        projectExpertId=row["project_expert_id"],
        specRunId=row["spec_run_id"],
        requestHash=row["request_hash"],
        request=request,
        result=json.loads(row["result_json"]) if row["result_json"] else None,
        error=error,
        createdAt=row["created_at"],
        startedAt=row["started_at"],
        completedAt=row["completed_at"],
    )
