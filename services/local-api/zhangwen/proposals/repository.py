"""SQLite proposal repository."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.proposals.models import (
    ProposalSection,
    ProposalStatus,
    ProposalVersion,
)
from zhangwen.solutions.models import SolutionStatus, SolutionVersion


class ProposalRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def list_proposals(self, project_id: str) -> list[ProposalVersion]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM proposals
                WHERE project_id = ?
                ORDER BY version DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._to_version(row) for row in rows]

    def get_proposal(self, project_id: str, proposal_id: str) -> ProposalVersion:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM proposals WHERE id = ? AND project_id = ?",
                (proposal_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("立项书不存在。")
            return self._to_version(row)

    def get_current_proposal(self, project_id: str) -> ProposalVersion | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM proposals
                WHERE project_id = ? AND status != ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id, ProposalStatus.SUPERSEDED.value),
            ).fetchone()
            return self._to_version(row) if row else None

    def create_from_solution(
        self,
        project_id: str,
        solution: SolutionVersion,
        sections: list[ProposalSection],
    ) -> ProposalVersion:
        return self.create_proposal(
            project_id=project_id,
            solution=solution,
            sections=sections,
            supersede_drafts=True,
        )

    def revise_proposal(
        self,
        project_id: str,
        proposal_id: str,
        sections: list[ProposalSection],
    ) -> ProposalVersion:
        current = self.get_proposal(project_id, proposal_id)
        solution = SolutionVersion(
            id=current.solutionId,
            projectId=current.projectId,
            version=current.solutionVersion,
            status=SolutionStatus.CONFIRMED,
            sections=[],
            createdAt=current.createdAt,
        )
        return self.create_proposal(
            project_id=project_id,
            solution=solution,
            sections=sections,
            supersede_drafts=True,
        )

    def create_proposal(
        self,
        *,
        project_id: str,
        solution: SolutionVersion,
        sections: list[ProposalSection],
        supersede_drafts: bool,
    ) -> ProposalVersion:
        _validate_sections(sections)
        now = _now()
        proposal_id = _id("proposal")
        with self._connect() as conn:
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM proposals WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = max_version + 1
            if supersede_drafts:
                conn.execute(
                    """
                    UPDATE proposals SET status = ?, updated_at = ?
                    WHERE project_id = ? AND status = ?
                    """,
                    (
                        ProposalStatus.SUPERSEDED.value,
                        now,
                        project_id,
                        ProposalStatus.DRAFT.value,
                    ),
                )
            conn.execute(
                """
                INSERT INTO proposals (
                  id, project_id, solution_id, solution_version, version, status,
                  sections_json, stale_reason, created_at, updated_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)
                """,
                (
                    proposal_id,
                    project_id,
                    solution.id,
                    solution.version,
                    version,
                    ProposalStatus.DRAFT.value,
                    json.dumps([s.model_dump(mode="json") for s in sections], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            proposal = self._to_version(row)
        self._sync_project_artifacts(project_id)
        return proposal

    def confirm_proposal(self, project_id: str, proposal_id: str) -> ProposalVersion:
        now = _now()
        with self._connect() as conn:
            row = self._row(conn, project_id, proposal_id)
            if row["status"] == ProposalStatus.STALE.value:
                raise ValueError("立项书已过期，不能确认。")
            conn.execute(
                """
                UPDATE proposals SET status = ?, confirmed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (ProposalStatus.APPROVED.value, now, now, proposal_id),
            )
            updated = conn.execute(
                "SELECT * FROM proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            proposal = self._to_version(updated)
        self._sync_artifact(proposal)
        return proposal

    def reject_proposal(
        self,
        project_id: str,
        proposal_id: str,
        reason: str | None,
    ) -> ProposalVersion:
        now = _now()
        with self._connect() as conn:
            self._row(conn, project_id, proposal_id)
            conn.execute(
                """
                UPDATE proposals SET status = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (ProposalStatus.REJECTED.value, reason, now, proposal_id),
            )
            updated = conn.execute(
                "SELECT * FROM proposals WHERE id = ?",
                (proposal_id,),
            ).fetchone()
            proposal = self._to_version(updated)
        self._sync_artifact(proposal)
        return proposal

    def mark_project_proposals_stale(
        self,
        project_id: str,
        reason: str,
    ) -> int:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE proposals
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN (?, ?)
                """,
                (
                    ProposalStatus.STALE.value,
                    reason,
                    now,
                    project_id,
                    ProposalStatus.DRAFT.value,
                    ProposalStatus.APPROVED.value,
                ),
            )
            count = int(cursor.rowcount)
        self._mark_artifacts_stale(project_id, reason)
        return count

    def _row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        proposal_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM proposals WHERE id = ? AND project_id = ?",
            (proposal_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("立项书不存在。")
        return row

    def _to_version(self, row: sqlite3.Row) -> ProposalVersion:
        sections_data: list[dict[str, Any]] = json.loads(row["sections_json"])
        return ProposalVersion(
            id=row["id"],
            projectId=row["project_id"],
            solutionId=row["solution_id"],
            solutionVersion=row["solution_version"],
            version=row["version"],
            status=ProposalStatus(row["status"]),
            sections=[ProposalSection(**section) for section in sections_data],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            confirmedAt=row["confirmed_at"],
            staleReason=row["stale_reason"],
        )

    def _sync_artifact(self, proposal: ProposalVersion) -> None:
        from zhangwen.artifacts.repository import ArtifactRepository

        ArtifactRepository(self._db_path).upsert_from_proposal(proposal)

    def _mark_artifacts_stale(self, project_id: str, reason: str) -> None:
        from zhangwen.artifacts.repository import ArtifactRepository

        ArtifactRepository(self._db_path).mark_proposal_artifacts_stale(project_id, reason)

    def _sync_project_artifacts(self, project_id: str) -> None:
        from zhangwen.artifacts.repository import ArtifactRepository

        artifact_repo = ArtifactRepository(self._db_path)
        for proposal in self.list_proposals(project_id):
            artifact_repo.upsert_from_proposal(proposal)


def _validate_sections(sections: list[ProposalSection]) -> None:
    expected_ids = [
        "project_overview",
        "requirements",
        "hardware_software_structure",
        "implementation_plan",
        "cost_difficulty_schedule",
        "risks_acceptance",
    ]
    if [section.id for section in sections] != expected_ids:
        raise ValueError("立项书必须包含固定顺序的六个章节。")
    if any(not section.content.strip() for section in sections):
        raise ValueError("立项书章节内容不能为空。")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
