"""SQLite repository for Lesson Agent runs."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from zhangwen.artifacts.models import (
    ArtifactDependency,
    ArtifactKind,
    ArtifactPreviewSection,
    ArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.lesson_agent.generator import GeneratedLesson, GeneratedLessonFile
from zhangwen.lesson_agent.models import (
    LessonDocumentKind,
    LessonFile,
    LessonRun,
    LessonRunStatus,
)
from zhangwen.proposals.models import ProposalVersion
from zhangwen.specs.models import SpecRun, SpecRunStatus


class LessonRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get_current_lesson(self, project_id: str) -> LessonRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM lesson_runs
                WHERE project_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return self._to_run(conn, row) if row else None

    def get_lesson(self, project_id: str, lesson_run_id: str) -> LessonRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM lesson_runs WHERE id = ? AND project_id = ?",
                (lesson_run_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("教案不存在。")
            return self._to_run(conn, row)

    def create_from_generated(
        self,
        *,
        project_id: str,
        spec: SpecRun,
        proposal: ProposalVersion,
        generated: GeneratedLesson,
    ) -> LessonRun:
        if spec.status != SpecRunStatus.APPROVED:
            raise ValueError("只有已确认 Spec 可以生成教案。")
        now = _now()
        lesson_run_id = _id("lesson")
        stale_lessons: list[LessonRun] = []
        with self._connect() as conn:
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM lesson_runs WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = int(max_version) + 1
            stale_run_ids = [
                row["id"]
                for row in conn.execute(
                    """
                    SELECT id FROM lesson_runs
                    WHERE project_id = ? AND status IN (?, ?, ?)
                    """,
                    (
                        project_id,
                        LessonRunStatus.DRAFT.value,
                        LessonRunStatus.READY_FOR_REVIEW.value,
                        LessonRunStatus.APPROVED.value,
                    ),
                ).fetchall()
            ]
            conn.execute(
                """
                UPDATE lesson_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN (?, ?, ?)
                """,
                (
                    LessonRunStatus.STALE.value,
                    "教案已生成新版本。",
                    now,
                    project_id,
                    LessonRunStatus.DRAFT.value,
                    LessonRunStatus.READY_FOR_REVIEW.value,
                    LessonRunStatus.APPROVED.value,
                ),
            )
            for stale_run_id in stale_run_ids:
                stale_row = conn.execute(
                    "SELECT * FROM lesson_runs WHERE id = ?",
                    (stale_run_id,),
                ).fetchone()
                stale_lessons.append(self._to_run(conn, stale_row))
            conn.execute(
                """
                INSERT INTO lesson_runs (
                  id, project_id, spec_run_id, proposal_id, version, status,
                  grade_band, lesson_hours, stale_reason, created_at, updated_at,
                  confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL)
                """,
                (
                    lesson_run_id,
                    project_id,
                    spec.id,
                    proposal.id,
                    version,
                    LessonRunStatus.READY_FOR_REVIEW.value,
                    generated.grade_band,
                    generated.lesson_hours,
                    now,
                    now,
                ),
            )
            for file in generated.files:
                self._insert_file(conn, lesson_run_id, project_id, file, now)
            row = conn.execute(
                "SELECT * FROM lesson_runs WHERE id = ?",
                (lesson_run_id,),
            ).fetchone()
            lesson = self._to_run(conn, row)
        for stale_lesson in stale_lessons:
            stale_spec = self._load_spec(project_id, stale_lesson.specRunId)
            stale_proposal = self._load_proposal(project_id, stale_lesson.proposalId)
            self.sync_artifacts(stale_lesson, stale_spec, stale_proposal)
        self.sync_artifacts(lesson, spec, proposal)
        return self.get_lesson(project_id, lesson_run_id)

    def confirm_lesson(self, project_id: str, lesson_run_id: str) -> LessonRun:
        now = _now()
        with self._connect() as conn:
            row = self._row(conn, project_id, lesson_run_id)
            if row["status"] not in {
                LessonRunStatus.READY_FOR_REVIEW.value,
                LessonRunStatus.APPROVED.value,
            }:
                raise ValueError("只有待确认教案可以确认。")
            conn.execute(
                """
                UPDATE lesson_runs
                SET status = ?, confirmed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (LessonRunStatus.APPROVED.value, now, now, lesson_run_id),
            )
            updated = conn.execute(
                "SELECT * FROM lesson_runs WHERE id = ?",
                (lesson_run_id,),
            ).fetchone()
            lesson = self._to_run(conn, updated)
        spec = self._load_spec(project_id, lesson.specRunId)
        proposal = self._load_proposal(project_id, lesson.proposalId)
        self.sync_artifacts(lesson, spec, proposal)
        return self.get_lesson(project_id, lesson_run_id)

    def reject_lesson(
        self,
        project_id: str,
        lesson_run_id: str,
        reason: str | None,
    ) -> LessonRun:
        now = _now()
        with self._connect() as conn:
            self._row(conn, project_id, lesson_run_id)
            conn.execute(
                """
                UPDATE lesson_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (LessonRunStatus.REJECTED.value, reason, now, lesson_run_id),
            )
            updated = conn.execute(
                "SELECT * FROM lesson_runs WHERE id = ?",
                (lesson_run_id,),
            ).fetchone()
            lesson = self._to_run(conn, updated)
        spec = self._load_spec(project_id, lesson.specRunId)
        proposal = self._load_proposal(project_id, lesson.proposalId)
        self.sync_artifacts(lesson, spec, proposal)
        return self.get_lesson(project_id, lesson_run_id)

    def sync_artifacts(
        self,
        lesson: LessonRun,
        spec: SpecRun,
        proposal: ProposalVersion,
    ) -> None:
        dependencies = [
            ArtifactDependency(
                artifactId=f"artifact_proposal_{lesson.projectId}",
                versionId=f"artifact_version_proposal_{proposal.id}",
                version=proposal.version,
                kind="proposal",
                label=f"项目立项书 v{proposal.version}",
                status=proposal.status.value,
            ),
            ArtifactDependency(
                artifactId=f"artifact_spec_{lesson.projectId}_project_spec",
                versionId=spec.files[0].artifactVersionId if spec.files else None,
                version=spec.version,
                kind="spec",
                label=f"工程规格 v{spec.version}",
                status=spec.status.value,
            ),
        ]
        for file in lesson.files:
            version = ArtifactRepository(self._db_path).upsert_text_artifact(
                artifact_id=f"artifact_lesson_{lesson.projectId}_{file.kind.value.lower()}",
                project_id=lesson.projectId,
                title=file.title,
                kind=ArtifactKind.DOCUMENT,
                status=_artifact_status(lesson.status),
                source_agent_id="lesson-agent",
                source_entity_type="lesson",
                source_entity_id=f"{lesson.id}_{file.kind.value}",
                source_version=lesson.version,
                content=file.content,
                summary=f"{file.title} v{lesson.version}",
                mime_type=file.mimeType,
                language="markdown",
                sections=_markdown_sections(file.content),
                dependencies=dependencies,
                stale_reason=lesson.staleReason,
                confirmed_at=lesson.confirmedAt,
            )
            self._link_file_artifact(file.id, version.artifactId, version.id)

    def _insert_file(
        self,
        conn: sqlite3.Connection,
        lesson_run_id: str,
        project_id: str,
        file: GeneratedLessonFile,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO lesson_files (
              id, lesson_run_id, project_id, kind, title, path, mime_type,
              content, artifact_id, artifact_version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?)
            """,
            (
                _id("lesson_file"),
                lesson_run_id,
                project_id,
                file.kind.value,
                file.title,
                file.path,
                file.mime_type,
                file.content,
                now,
            ),
        )

    def _link_file_artifact(
        self,
        file_id: str,
        artifact_id: str,
        artifact_version_id: str,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE lesson_files
                SET artifact_id = ?, artifact_version_id = ?
                WHERE id = ?
                """,
                (artifact_id, artifact_version_id, file_id),
            )

    def _row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        lesson_run_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM lesson_runs WHERE id = ? AND project_id = ?",
            (lesson_run_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("教案不存在。")
        return row

    def _to_run(self, conn: sqlite3.Connection, row: sqlite3.Row) -> LessonRun:
        files = [
            LessonFile(
                id=file_row["id"],
                lessonRunId=file_row["lesson_run_id"],
                projectId=file_row["project_id"],
                kind=LessonDocumentKind(file_row["kind"]),
                title=file_row["title"],
                path=file_row["path"],
                mimeType=file_row["mime_type"],
                content=file_row["content"],
                artifactId=file_row["artifact_id"],
                artifactVersionId=file_row["artifact_version_id"],
                createdAt=file_row["created_at"],
            )
            for file_row in conn.execute(
                """
                SELECT * FROM lesson_files
                WHERE lesson_run_id = ?
                ORDER BY CASE kind
                  WHEN 'TEACHER_GUIDE' THEN 1
                  WHEN 'STUDENT_WORKSHEET' THEN 2
                  WHEN 'RUBRIC' THEN 3
                  WHEN 'SAFETY_NOTES' THEN 4
                  ELSE 99
                END
                """,
                (row["id"],),
            ).fetchall()
        ]
        return LessonRun(
            id=row["id"],
            projectId=row["project_id"],
            specRunId=row["spec_run_id"],
            proposalId=row["proposal_id"],
            version=row["version"],
            status=LessonRunStatus(row["status"]),
            gradeBand=row["grade_band"],
            lessonHours=row["lesson_hours"],
            files=files,
            staleReason=row["stale_reason"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            confirmedAt=row["confirmed_at"],
        )

    def _load_spec(self, project_id: str, spec_run_id: str) -> SpecRun:
        from zhangwen.specs.repository import SpecRepository

        return SpecRepository(self._db_path).get_spec(project_id, spec_run_id)

    def _load_proposal(self, project_id: str, proposal_id: str) -> ProposalVersion:
        from zhangwen.proposals.repository import ProposalRepository

        return ProposalRepository(self._db_path).get_proposal(project_id, proposal_id)


def _artifact_status(status: LessonRunStatus) -> ArtifactStatus:
    mapping = {
        LessonRunStatus.DRAFT: ArtifactStatus.DRAFT,
        LessonRunStatus.READY_FOR_REVIEW: ArtifactStatus.NEEDS_REVIEW,
        LessonRunStatus.APPROVED: ArtifactStatus.APPROVED,
        LessonRunStatus.REJECTED: ArtifactStatus.REJECTED,
        LessonRunStatus.STALE: ArtifactStatus.STALE,
        LessonRunStatus.FAILED: ArtifactStatus.FAILED,
    }
    return mapping[status]


def _markdown_sections(content: str) -> list[ArtifactPreviewSection]:
    sections: list[ArtifactPreviewSection] = []
    current_title = "内容"
    current_id = "content"
    current_lines: list[str] = []
    for line in content.splitlines():
        if line.startswith("# "):
            if current_lines:
                sections.append(
                    ArtifactPreviewSection(
                        id=current_id,
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                    )
                )
                current_lines = []
            current_title = line[2:].strip() or "内容"
            current_id = _section_id(current_title)
            continue
        if line.startswith("## "):
            if current_lines:
                sections.append(
                    ArtifactPreviewSection(
                        id=current_id,
                        title=current_title,
                        content="\n".join(current_lines).strip(),
                    )
                )
                current_lines = []
            current_title = line[3:].strip() or "内容"
            current_id = _section_id(current_title)
            continue
        current_lines.append(line)
    if current_lines:
        sections.append(
            ArtifactPreviewSection(
                id=current_id,
                title=current_title,
                content="\n".join(current_lines).strip(),
            )
        )
    return [section for section in sections if section.content]


def _section_id(title: str) -> str:
    return "lesson_" + sha256(title.encode("utf-8")).hexdigest()[:12]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
