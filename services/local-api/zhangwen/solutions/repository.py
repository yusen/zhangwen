"""SQLite solution repository — extends ProjectRepository's DB."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.solutions.models import (
    SolutionRevision,
    SolutionSection,
    SolutionSectionChange,
    SolutionStatus,
    SolutionVersion,
)


class SolutionRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def list_solutions(self, project_id: str) -> list[SolutionVersion]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM solutions
                WHERE project_id = ?
                ORDER BY version DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._to_version(row) for row in rows]

    def get_current_solution(self, project_id: str) -> SolutionVersion | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM solutions
                WHERE project_id = ? AND status != ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id, SolutionStatus.SUPERSEDED.value),
            ).fetchone()
            return self._to_version(row) if row else None

    def get_solution(self, project_id: str, solution_id: str) -> SolutionVersion:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM solutions WHERE id = ? AND project_id = ?",
                (solution_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("方案不存在。")
            return self._to_version(row)

    def create_solution(
        self,
        project_id: str,
        sections: list[SolutionSection],
        *,
        based_on_version: int | None = None,
        change_summary: list[str] | None = None,
    ) -> SolutionVersion:
        now = _now()
        solution_id = _id("sol")
        with self._connect() as conn:
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM solutions WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = max_version + 1
            # Supersede all previous drafts
            conn.execute(
                """
                UPDATE solutions SET status = ?
                WHERE project_id = ? AND status = ?
                """,
                (SolutionStatus.SUPERSEDED.value, project_id, SolutionStatus.DRAFT.value),
            )
            sections_data = [s.model_dump(mode="json") for s in sections]
            conn.execute(
                """
                INSERT INTO solutions (
                    id, project_id, version, status, sections_json, created_at,
                    confirmed_at, based_on_version, change_summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)
                """,
                (
                    solution_id,
                    project_id,
                    version,
                    SolutionStatus.DRAFT.value,
                    json.dumps(sections_data, ensure_ascii=False),
                    now,
                    based_on_version,
                    json.dumps(change_summary or [], ensure_ascii=False),
                ),
            )
            row = conn.execute("SELECT * FROM solutions WHERE id = ?", (solution_id,)).fetchone()
            solution = self._to_version(row)
        self.sync_artifact(solution)
        return self.get_solution(project_id, solution.id)

    def create_revision_from_llm(
        self,
        project_id: str,
        *,
        base: SolutionVersion,
        revised_sections: list[SolutionSection],
        user_request: str,
        changed_sections: list[SolutionSectionChange],
        preserved_sections: list[str],
        impact_summary: list[str],
    ) -> tuple[SolutionVersion, SolutionRevision]:
        if base.projectId != project_id:
            raise ValueError("基础方案不属于当前项目。")
        solution = self.create_solution(
            project_id,
            revised_sections,
            based_on_version=base.version,
            change_summary=impact_summary,
        )
        revision = self._create_revision(
            project_id=project_id,
            base=base,
            solution=solution,
            user_request=user_request.strip(),
            changed_sections=changed_sections,
            preserved_sections=preserved_sections,
            impact_summary=impact_summary,
        )
        return self.get_solution(project_id, solution.id), revision

    def restore_previous_solution(self, project_id: str) -> SolutionVersion:
        current = self.get_current_solution(project_id)
        if current is None:
            raise ValueError("当前还没有可恢复的推荐实现方案。")
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM solution_revisions
                WHERE project_id = ? AND new_solution_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_id, current.id),
            ).fetchone()
            if row is None:
                raise ValueError("当前方案没有可恢复的上一版本。")
            conn.execute(
                "UPDATE solutions SET status = ? WHERE id = ?",
                (SolutionStatus.SUPERSEDED.value, current.id),
            )
            base_id = row["base_solution_id"]
        self.sync_artifact(self.get_solution(project_id, current.id))
        base = self.get_solution(project_id, base_id)
        self._set_current_artifact(base)
        return self.get_solution(project_id, base_id)

    def confirm_solution(self, project_id: str, solution_id: str) -> SolutionVersion:
        now = _now()
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM solutions WHERE id = ? AND project_id = ?",
                (solution_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("方案不存在。")
            conn.execute(
                "UPDATE solutions SET status = ?, confirmed_at = ? WHERE id = ?",
                (SolutionStatus.CONFIRMED.value, now, solution_id),
            )
            updated = conn.execute(
                "SELECT * FROM solutions WHERE id = ?", (solution_id,)
            ).fetchone()
            solution = self._to_version(updated)
        self.sync_artifact(solution)
        return self.get_solution(project_id, solution.id)

    def sync_artifact(self, solution: SolutionVersion) -> None:
        from zhangwen.artifacts.repository import ArtifactRepository

        version = ArtifactRepository(self._db_path).upsert_from_solution(solution)
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE solutions
                SET artifact_id = ?, artifact_version_id = ?
                WHERE id = ?
                """,
                (version.artifactId, version.id, solution.id),
            )

    def get_revision_for_solution(
        self,
        project_id: str,
        solution_id: str,
    ) -> SolutionRevision | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM solution_revisions
                WHERE project_id = ? AND new_solution_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (project_id, solution_id),
            ).fetchone()
            return self._to_revision(row) if row else None

    def _set_current_artifact(self, solution: SolutionVersion) -> None:
        if not solution.artifactId or not solution.artifactVersionId:
            self.sync_artifact(solution)
            solution = self.get_solution(solution.projectId, solution.id)
        from zhangwen.artifacts.models import ArtifactStatus

        status = (
            ArtifactStatus.APPROVED.value
            if solution.status == SolutionStatus.CONFIRMED
            else ArtifactStatus.NEEDS_REVIEW.value
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE artifacts
                SET current_version_id = ?, status = ?, updated_at = ?
                WHERE id = ?
                """,
                (solution.artifactVersionId, status, _now(), solution.artifactId),
            )

    def _create_revision(
        self,
        *,
        project_id: str,
        base: SolutionVersion,
        solution: SolutionVersion,
        user_request: str,
        changed_sections: list[SolutionSectionChange],
        preserved_sections: list[str],
        impact_summary: list[str],
    ) -> SolutionRevision:
        now = _now()
        revision_id = _id("solrev")
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO solution_revisions (
                  id, project_id, base_solution_id, base_version, new_solution_id,
                  new_version, user_request, changed_sections_json,
                  preserved_sections_json, impact_summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    revision_id,
                    project_id,
                    base.id,
                    base.version,
                    solution.id,
                    solution.version,
                    user_request,
                    json.dumps(
                        [item.model_dump(mode="json") for item in changed_sections],
                        ensure_ascii=False,
                    ),
                    json.dumps(preserved_sections, ensure_ascii=False),
                    json.dumps(impact_summary, ensure_ascii=False),
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM solution_revisions WHERE id = ?",
                (revision_id,),
            ).fetchone()
            return self._to_revision(row)

    def _to_version(self, row: sqlite3.Row) -> SolutionVersion:
        sections_data: list[dict[str, Any]] = json.loads(row["sections_json"])
        return SolutionVersion(
            id=row["id"],
            projectId=row["project_id"],
            version=row["version"],
            status=SolutionStatus(row["status"]),
            basedOnVersion=row["based_on_version"] if "based_on_version" in row.keys() else None,
            changeSummary=json.loads(row["change_summary_json"] or "[]")
            if "change_summary_json" in row.keys()
            else [],
            sections=[SolutionSection(**s) for s in sections_data],
            artifactId=row["artifact_id"] if "artifact_id" in row.keys() else None,
            artifactVersionId=row["artifact_version_id"]
            if "artifact_version_id" in row.keys()
            else None,
            createdAt=row["created_at"],
            confirmedAt=row["confirmed_at"],
        )

    def _to_revision(self, row: sqlite3.Row) -> SolutionRevision:
        return SolutionRevision(
            id=row["id"],
            projectId=row["project_id"],
            baseSolutionId=row["base_solution_id"],
            baseVersion=row["base_version"],
            newSolutionId=row["new_solution_id"],
            newVersion=row["new_version"],
            userRequest=row["user_request"],
            changedSections=[
                SolutionSectionChange(**item)
                for item in json.loads(row["changed_sections_json"])
            ],
            preservedSections=json.loads(row["preserved_sections_json"]),
            impactSummary=json.loads(row["impact_summary_json"]),
            createdAt=row["created_at"],
        )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
