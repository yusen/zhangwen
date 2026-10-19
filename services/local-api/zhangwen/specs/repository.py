"""SQLite repository for Spec Agent runs."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.artifacts.models import (
    ArtifactDependency,
    ArtifactKind,
    ArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.proposals.models import ProposalVersion
from zhangwen.specs.generator import GeneratedSpec, GeneratedSpecFile
from zhangwen.specs.models import (
    SpecFile,
    SpecFileKind,
    SpecRun,
    SpecRunStatus,
    SpecValidation,
)


class SpecRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get_current_spec(self, project_id: str) -> SpecRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM spec_runs
                WHERE project_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return self._to_spec(conn, row) if row else None

    def get_spec(self, project_id: str, spec_run_id: str) -> SpecRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM spec_runs WHERE id = ? AND project_id = ?",
                (spec_run_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("Spec 不存在。")
            return self._to_spec(conn, row)

    def create_from_generated(
        self,
        *,
        project_id: str,
        proposal: ProposalVersion,
        generated: GeneratedSpec,
    ) -> SpecRun:
        now = _now()
        spec_run_id = _id("spec")
        status = (
            SpecRunStatus.VALIDATED
            if generated.validation.ok
            else SpecRunStatus.FAILED
        )
        with self._connect() as conn:
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM spec_runs WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = int(max_version) + 1
            conn.execute(
                """
                UPDATE spec_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN (?, ?)
                """,
                (
                    SpecRunStatus.STALE.value,
                    "Spec 已生成新版本。",
                    now,
                    project_id,
                    SpecRunStatus.DRAFT.value,
                    SpecRunStatus.VALIDATED.value,
                ),
            )
            conn.execute(
                """
                INSERT INTO spec_runs (
                  id, project_id, proposal_id, version, status, validation_json,
                  stale_reason, created_at, updated_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)
                """,
                (
                    spec_run_id,
                    project_id,
                    proposal.id,
                    version,
                    status.value,
                    json.dumps(generated.validation.model_dump(mode="json"), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            for generated_file in generated.files:
                self._insert_file(conn, spec_run_id, project_id, generated_file, now)
            row = conn.execute(
                "SELECT * FROM spec_runs WHERE id = ?",
                (spec_run_id,),
            ).fetchone()
            spec = self._to_spec(conn, row)
        self.sync_artifacts(spec, proposal)
        return self.get_spec(project_id, spec_run_id)

    def confirm_spec(self, project_id: str, spec_run_id: str) -> SpecRun:
        now = _now()
        with self._connect() as conn:
            row = self._row(conn, project_id, spec_run_id)
            if row["status"] not in {SpecRunStatus.VALIDATED.value, SpecRunStatus.APPROVED.value}:
                raise ValueError("只有已校验通过的 Spec 可以确认。")
            conn.execute(
                """
                UPDATE spec_runs
                SET status = ?, confirmed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (SpecRunStatus.APPROVED.value, now, now, spec_run_id),
            )
            updated = conn.execute(
                "SELECT * FROM spec_runs WHERE id = ?",
                (spec_run_id,),
            ).fetchone()
            spec = self._to_spec(conn, updated)
        self._sync_existing_artifacts(spec)
        ArtifactRepository(self._db_path).mark_downstream_artifacts_stale(
            project_id,
            source_agents=["code-agent", "cad-agent", "deploy-agent"],
            reason="硬件方案或 IO Map 已确认新版本，下游产物需要重新生成。",
        )
        from zhangwen.code_agent.repository import CodeRepository

        CodeRepository(self._db_path).mark_project_code_stale(
            project_id,
            "硬件方案或 IO Map 已确认新版本，MicroPython 代码需要重新检查。",
        )
        return self.get_spec(project_id, spec_run_id)

    def reject_spec(self, project_id: str, spec_run_id: str, reason: str | None) -> SpecRun:
        now = _now()
        with self._connect() as conn:
            self._row(conn, project_id, spec_run_id)
            conn.execute(
                """
                UPDATE spec_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (SpecRunStatus.REJECTED.value, reason, now, spec_run_id),
            )
            updated = conn.execute(
                "SELECT * FROM spec_runs WHERE id = ?",
                (spec_run_id,),
            ).fetchone()
            spec = self._to_spec(conn, updated)
        self._sync_existing_artifacts(spec)
        return self.get_spec(project_id, spec_run_id)

    def sync_artifacts(self, spec: SpecRun, proposal: ProposalVersion) -> None:
        dependencies = [
            ArtifactDependency(
                artifactId=f"artifact_proposal_{spec.projectId}",
                versionId=f"artifact_version_proposal_{proposal.id}",
                version=proposal.version,
                kind="proposal",
                label=f"项目立项书 v{proposal.version}",
                status=proposal.status.value,
            )
        ]
        for file in spec.files:
            version = ArtifactRepository(self._db_path).upsert_text_artifact(
                artifact_id=f"artifact_spec_{spec.projectId}_{file.kind.value.lower()}",
                project_id=spec.projectId,
                title=_title(file.kind),
                kind=ArtifactKind.DOCUMENT,
                status=_artifact_status(spec.status),
                source_agent_id="spec-agent",
                source_entity_type="spec",
                source_entity_id=f"{spec.id}_{file.kind.value}",
                source_version=spec.version,
                content=file.content,
                summary=f"{_title(file.kind)} v{spec.version}",
                mime_type=file.mimeType,
                language="yaml",
                dependencies=dependencies,
                stale_reason=spec.staleReason,
                confirmed_at=spec.confirmedAt,
            )
            self._link_file_artifact(file.id, version.artifactId, version.id)

    def _sync_existing_artifacts(self, spec: SpecRun) -> None:
        with self._connect() as conn:
            proposal_row = conn.execute(
                "SELECT * FROM proposals WHERE id = ? AND project_id = ?",
                (spec.proposalId, spec.projectId),
            ).fetchone()
        if proposal_row is None:
            return
        from zhangwen.proposals.repository import ProposalRepository

        proposal = ProposalRepository(self._db_path).get_proposal(
            spec.projectId,
            spec.proposalId,
        )
        self.sync_artifacts(spec, proposal)

    def _link_file_artifact(
        self,
        file_id: str,
        artifact_id: str,
        artifact_version_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE spec_files
                SET artifact_id = ?, artifact_version_id = ?
                WHERE id = ?
                """,
                (artifact_id, artifact_version_id, file_id),
            )

    def _insert_file(
        self,
        conn: sqlite3.Connection,
        spec_run_id: str,
        project_id: str,
        file: GeneratedSpecFile,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO spec_files (
              id, spec_run_id, project_id, kind, path, mime_type, content,
              artifact_id, artifact_version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                _id("spec_file"),
                spec_run_id,
                project_id,
                file.kind.value,
                file.path,
                "application/x-yaml",
                file.content,
                now,
            ),
        )

    def _row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        spec_run_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM spec_runs WHERE id = ? AND project_id = ?",
            (spec_run_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("Spec 不存在。")
        return row

    def _to_spec(self, conn: sqlite3.Connection, row: sqlite3.Row) -> SpecRun:
        files = [
            SpecFile(
                id=file_row["id"],
                specRunId=file_row["spec_run_id"],
                projectId=file_row["project_id"],
                kind=SpecFileKind(file_row["kind"]),
                path=file_row["path"],
                mimeType=file_row["mime_type"],
                content=file_row["content"],
                artifactId=file_row["artifact_id"],
                artifactVersionId=file_row["artifact_version_id"],
                createdAt=file_row["created_at"],
            )
            for file_row in conn.execute(
                """
                SELECT * FROM spec_files
                WHERE spec_run_id = ?
                ORDER BY CASE kind
                  WHEN 'PROJECT_SPEC' THEN 1
                  WHEN 'BOM' THEN 2
                  WHEN 'IO_MAP' THEN 3
                  ELSE 99
                END
                """,
                (row["id"],),
            ).fetchall()
        ]
        return SpecRun(
            id=row["id"],
            projectId=row["project_id"],
            proposalId=row["proposal_id"],
            version=row["version"],
            status=SpecRunStatus(row["status"]),
            files=files,
            validation=SpecValidation(**json.loads(row["validation_json"])),
            staleReason=row["stale_reason"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            confirmedAt=row["confirmed_at"],
        )


def _artifact_status(status: SpecRunStatus) -> ArtifactStatus:
    mapping = {
        SpecRunStatus.DRAFT: ArtifactStatus.DRAFT,
        SpecRunStatus.VALIDATED: ArtifactStatus.NEEDS_REVIEW,
        SpecRunStatus.APPROVED: ArtifactStatus.APPROVED,
        SpecRunStatus.REJECTED: ArtifactStatus.REJECTED,
        SpecRunStatus.STALE: ArtifactStatus.STALE,
        SpecRunStatus.FAILED: ArtifactStatus.FAILED,
    }
    return mapping[status]


def _title(kind: SpecFileKind) -> str:
    return {
        SpecFileKind.PROJECT_SPEC: "工程规格 project_spec.yaml",
        SpecFileKind.BOM: "物料清单 bom.yaml",
        SpecFileKind.IO_MAP: "接线定义 io_map.yaml",
    }[kind]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
