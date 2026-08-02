"""SQLite repository for versioned artifacts."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.artifacts.models import (
    ArtifactDefinition,
    ArtifactDependency,
    ArtifactFile,
    ArtifactKind,
    ArtifactPreview,
    ArtifactPreviewKind,
    ArtifactPreviewSection,
    ArtifactStatus,
    ArtifactVersion,
    DomainArtifactStatus,
)
from zhangwen.proposals.models import ProposalStatus, ProposalVersion
from zhangwen.solutions.models import SolutionStatus, SolutionVersion


class ArtifactRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def list_artifacts(self, project_id: str) -> list[ArtifactDefinition]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM artifacts
                WHERE project_id = ?
                ORDER BY updated_at DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._to_artifact(conn, row) for row in rows]

    def get_artifact(self, project_id: str, artifact_id: str) -> ArtifactDefinition:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM artifacts WHERE id = ? AND project_id = ?",
                (artifact_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("产物不存在。")
            return self._to_artifact(conn, row)

    def list_artifact_files(
        self,
        project_id: str,
        artifact_id: str,
        artifact_version_id: str,
    ) -> list[ArtifactFile]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM artifact_files
                WHERE project_id = ? AND artifact_id = ? AND artifact_version_id = ?
                ORDER BY role, file_name
                """,
                (project_id, artifact_id, artifact_version_id),
            ).fetchall()
        return [_to_artifact_file(row) for row in rows]

    def get_artifact_file(
        self,
        project_id: str,
        artifact_id: str,
        artifact_version_id: str,
        file_id: str,
    ) -> tuple[ArtifactFile, str]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM artifact_files
                WHERE id = ? AND project_id = ? AND artifact_id = ?
                  AND artifact_version_id = ?
                """,
                (file_id, project_id, artifact_id, artifact_version_id),
            ).fetchone()
        if row is None:
            raise ValueError("产物文件不存在。")
        return _to_artifact_file(row), str(row["storage_key"])

    def upsert_text_artifact(
        self,
        *,
        artifact_id: str,
        project_id: str,
        title: str,
        kind: ArtifactKind,
        status: ArtifactStatus,
        source_agent_id: str,
        source_entity_type: str,
        source_entity_id: str,
        source_version: int,
        content: str,
        summary: str,
        mime_type: str,
        language: str | None = None,
        sections: list[ArtifactPreviewSection] | None = None,
        dependencies: list[ArtifactDependency] | None = None,
        stale_reason: str | None = None,
        confirmed_at: str | None = None,
    ) -> ArtifactVersion:
        now = _now()
        version_id = f"artifact_version_{artifact_id}_{source_entity_id}"
        preview = (
            ArtifactPreview(
                kind=ArtifactPreviewKind.DOCUMENT,
                summary=summary,
                sections=sections,
            )
            if sections is not None
            else ArtifactPreview(
                kind=ArtifactPreviewKind.CODE,
                summary=summary,
                code=content,
                language=language,
            )
        )
        dependency_list = dependencies or []
        checksum = hashlib.sha256(content.encode("utf-8")).hexdigest()
        with self._connect() as conn:
            existing_artifact = conn.execute(
                "SELECT * FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            if existing_artifact is None:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                      id, project_id, title, kind, status, source_agent_id,
                      current_version_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        project_id,
                        title,
                        kind.value,
                        status.value,
                        source_agent_id,
                        version_id,
                        now,
                        now,
                    ),
                )
            else:
                max_version = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM artifact_versions WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()[0]
                current_version_id = (
                    version_id
                    if source_version >= int(max_version)
                    else existing_artifact["current_version_id"]
                )
                artifact_status = (
                    status.value
                    if source_version >= int(max_version)
                    else existing_artifact["status"]
                )
                conn.execute(
                    """
                    UPDATE artifacts
                    SET title = ?, status = ?, current_version_id = ?,
                        source_agent_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title,
                        artifact_status,
                        current_version_id,
                        source_agent_id,
                        now,
                        artifact_id,
                    ),
                )

            payload = (
                artifact_id,
                project_id,
                source_version,
                status.value,
                mime_type,
                json.dumps(preview.model_dump(mode="json"), ensure_ascii=False),
                json.dumps([item.model_dump(mode="json") for item in dependency_list], ensure_ascii=False),
                None,
                source_entity_type,
                source_entity_id,
                checksum,
                stale_reason,
                now,
                confirmed_at,
                version_id,
            )
            existing_version = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            if existing_version is None:
                conn.execute(
                    """
                    INSERT INTO artifact_versions (
                      artifact_id, project_id, version, status, mime_type, preview_json,
                      dependencies_json, producer_task_id, source_entity_type,
                      source_entity_id, checksum, stale_reason, created_at, confirmed_at, id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
            else:
                conn.execute(
                    """
                    UPDATE artifact_versions
                    SET artifact_id = ?, project_id = ?, version = ?, status = ?,
                        mime_type = ?, preview_json = ?, dependencies_json = ?,
                        producer_task_id = ?, source_entity_type = ?, source_entity_id = ?,
                        checksum = ?, stale_reason = ?, created_at = ?, confirmed_at = ?
                    WHERE id = ?
                    """,
                    payload,
                )
            self._sync_artifact_dependencies(
                conn,
                project_id=project_id,
                artifact_id=artifact_id,
                version_id=version_id,
                dependencies=dependency_list,
                created_at=now,
            )
            self._apply_artifact_context(
                conn,
                artifact_id=artifact_id,
                version_id=version_id,
                project_id=project_id,
                source_agent_id=source_agent_id,
                status=status,
            )
            self._propagate_if_confirmed(
                conn,
                project_id=project_id,
                artifact_id=artifact_id,
                version=source_version,
                status=status,
            )
            row = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            return _to_version(row)

    def upsert_model_artifact(
        self,
        *,
        artifact_id: str,
        project_id: str,
        title: str,
        status: ArtifactStatus,
        source_agent_id: str,
        source_entity_type: str,
        source_entity_id: str,
        source_version: int,
        content: str | None,
        summary: str,
        model_url: str | None,
        model_file_id: str | None = None,
        checksum: str | None = None,
        mime_type: str = "model/gltf-binary",
        dependencies: list[ArtifactDependency] | None = None,
        stale_reason: str | None = None,
        confirmed_at: str | None = None,
        connection: sqlite3.Connection | None = None,
    ) -> ArtifactVersion:
        now = _now()
        version_id = f"artifact_version_{artifact_id}_{source_entity_id}"
        preview = ArtifactPreview(
            kind=ArtifactPreviewKind.MODEL_3D,
            summary=summary,
            modelUrl=model_url,
            modelFileId=model_file_id,
            placeholder="3D 模型文件尚未就绪。" if model_file_id is None else None,
        )
        dependency_list = dependencies or []
        resolved_checksum = checksum or hashlib.sha256(
            (content or summary).encode("utf-8")
        ).hexdigest()
        with (self._connect() if connection is None else nullcontext(connection)) as conn:
            existing_artifact = conn.execute(
                "SELECT * FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            if existing_artifact is None:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                      id, project_id, title, kind, status, source_agent_id,
                      current_version_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        project_id,
                        title,
                        ArtifactKind.MODEL_3D.value,
                        status.value,
                        source_agent_id,
                        version_id,
                        now,
                        now,
                    ),
                )
            else:
                max_version = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM artifact_versions WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()[0]
                current_version_id = (
                    version_id
                    if source_version >= int(max_version)
                    else existing_artifact["current_version_id"]
                )
                artifact_status = (
                    status.value
                    if source_version >= int(max_version)
                    else existing_artifact["status"]
                )
                conn.execute(
                    """
                    UPDATE artifacts
                    SET title = ?, status = ?, current_version_id = ?,
                        source_agent_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        title,
                        artifact_status,
                        current_version_id,
                        source_agent_id,
                        now,
                        artifact_id,
                    ),
                )
            payload = (
                artifact_id,
                project_id,
                source_version,
                status.value,
                mime_type,
                json.dumps(preview.model_dump(mode="json"), ensure_ascii=False),
                json.dumps([item.model_dump(mode="json") for item in dependency_list], ensure_ascii=False),
                None,
                source_entity_type,
                source_entity_id,
                resolved_checksum,
                stale_reason,
                now,
                confirmed_at,
                version_id,
            )
            existing_version = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            if existing_version is None:
                conn.execute(
                    """
                    INSERT INTO artifact_versions (
                      artifact_id, project_id, version, status, mime_type, preview_json,
                      dependencies_json, producer_task_id, source_entity_type,
                      source_entity_id, checksum, stale_reason, created_at, confirmed_at, id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
            else:
                conn.execute(
                    """
                    UPDATE artifact_versions
                    SET artifact_id = ?, project_id = ?, version = ?, status = ?,
                        mime_type = ?, preview_json = ?, dependencies_json = ?,
                        producer_task_id = ?, source_entity_type = ?, source_entity_id = ?,
                        checksum = ?, stale_reason = ?, confirmed_at = ?
                    WHERE id = ?
                    """,
                    (*payload[:12], payload[13], payload[14]),
                )
            self._sync_artifact_dependencies(
                conn,
                project_id=project_id,
                artifact_id=artifact_id,
                version_id=version_id,
                dependencies=dependency_list,
                created_at=now,
            )
            self._apply_artifact_context(
                conn,
                artifact_id=artifact_id,
                version_id=version_id,
                project_id=project_id,
                source_agent_id=source_agent_id,
                status=status,
            )
            self._propagate_if_confirmed(
                conn,
                project_id=project_id,
                artifact_id=artifact_id,
                version=source_version,
                status=status,
            )
            row = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            return _to_version(row)

    def insert_artifact_file(
        self,
        conn: sqlite3.Connection,
        *,
        file_id: str,
        artifact_id: str,
        artifact_version_id: str,
        project_id: str,
        role: str,
        file_name: str,
        storage_key: str,
        mime_type: str,
        byte_size: int,
        sha256: str,
        triangle_count: int | None,
        bounds: dict[str, object] | None,
        created_at: str,
    ) -> ArtifactFile:
        conn.execute(
            """
            INSERT INTO artifact_files (
              id, artifact_id, artifact_version_id, project_id, role, file_name,
              storage_key, mime_type, byte_size, sha256, triangle_count,
              bounds_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                file_id,
                artifact_id,
                artifact_version_id,
                project_id,
                role,
                file_name,
                storage_key,
                mime_type,
                byte_size,
                sha256,
                triangle_count,
                json.dumps(bounds, ensure_ascii=False, sort_keys=True) if bounds else None,
                created_at,
            ),
        )
        row = conn.execute(
            "SELECT * FROM artifact_files WHERE id = ?",
            (file_id,),
        ).fetchone()
        return _to_artifact_file(row)

    def transition_model_artifact(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        artifact_id: str,
        artifact_version_id: str,
        status: ArtifactStatus,
        stale_reason: str | None,
        confirmed_at: str | None,
        make_current: bool,
        now: str,
    ) -> ArtifactVersion:
        updated = conn.execute(
            """
            UPDATE artifact_versions
            SET status = ?, stale_reason = ?, confirmed_at = ?
            WHERE id = ? AND artifact_id = ? AND project_id = ?
            """,
            (
                status.value,
                stale_reason,
                confirmed_at,
                artifact_version_id,
                artifact_id,
                project_id,
            ),
        ).rowcount
        if updated != 1:
            raise ValueError("产物版本不存在。")
        if make_current:
            conn.execute(
                """
                UPDATE artifacts
                SET status = ?, current_version_id = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (status.value, artifact_version_id, now, artifact_id, project_id),
            )
        self._apply_artifact_context(
            conn,
            artifact_id=artifact_id,
            version_id=artifact_version_id,
            project_id=project_id,
            source_agent_id="cad-agent",
            status=status,
        )
        self._propagate_if_confirmed(
            conn,
            project_id=project_id,
            artifact_id=artifact_id,
            version=int(
                conn.execute(
                    "SELECT version FROM artifact_versions WHERE id = ?",
                    (artifact_version_id,),
                ).fetchone()[0]
            ),
            status=status,
        )
        row = conn.execute(
            "SELECT * FROM artifact_versions WHERE id = ?",
            (artifact_version_id,),
        ).fetchone()
        return _to_version(row)

    def upsert_from_proposal(self, proposal: ProposalVersion) -> ArtifactDefinition:
        now = _now()
        artifact_id = f"artifact_proposal_{proposal.projectId}"
        version_id = f"artifact_version_proposal_{proposal.id}"
        status = _proposal_status_to_artifact_status(proposal.status)
        preview = ArtifactPreview(
            kind=ArtifactPreviewKind.DOCUMENT,
            summary=f"项目立项书 v{proposal.version}",
            sections=[
                ArtifactPreviewSection(
                    id=section.id,
                    title=section.title,
                    content=section.content,
                )
                for section in proposal.sections
            ],
        )
        dependencies = [
            ArtifactDependency(
                artifactId=f"artifact_solution_{proposal.projectId}",
                versionId=f"artifact_version_solution_{proposal.solutionId}",
                version=proposal.solutionVersion,
                kind="solution",
                label=f"推荐实现方案 v{proposal.solutionVersion}",
                status="CONFIRMED",
            )
        ]
        checksum_payload = {
            "proposalId": proposal.id,
            "version": proposal.version,
            "status": proposal.status.value,
            "sections": [section.model_dump(mode="json") for section in proposal.sections],
        }
        checksum = hashlib.sha256(
            json.dumps(checksum_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        with self._connect() as conn:
            existing_artifact = conn.execute(
                "SELECT * FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            if existing_artifact is None:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                      id, project_id, title, kind, status, source_agent_id,
                      current_version_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        proposal.projectId,
                        "项目立项书",
                        ArtifactKind.DOCUMENT.value,
                        status.value,
                        "proposal-agent",
                        version_id,
                        now,
                        now,
                    ),
                )
            else:
                max_version = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM artifact_versions WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()[0]
                current_version_id = (
                    version_id
                    if proposal.version >= int(max_version)
                    else existing_artifact["current_version_id"]
                )
                artifact_status = (
                    status.value
                    if proposal.version >= int(max_version)
                    else existing_artifact["status"]
                )
                conn.execute(
                    """
                    UPDATE artifacts
                    SET title = ?, status = ?, current_version_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    ("项目立项书", artifact_status, current_version_id, now, artifact_id),
                )

            existing_version = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            payload = (
                artifact_id,
                proposal.projectId,
                proposal.version,
                status.value,
                "text/markdown",
                json.dumps(preview.model_dump(mode="json"), ensure_ascii=False),
                json.dumps([item.model_dump(mode="json") for item in dependencies], ensure_ascii=False),
                None,
                "proposal",
                proposal.id,
                checksum,
                proposal.staleReason,
                proposal.createdAt,
                proposal.confirmedAt,
                version_id,
            )
            if existing_version is None:
                conn.execute(
                    """
                    INSERT INTO artifact_versions (
                      artifact_id, project_id, version, status, mime_type, preview_json,
                      dependencies_json, producer_task_id, source_entity_type,
                      source_entity_id, checksum, stale_reason, created_at, confirmed_at, id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
            else:
                conn.execute(
                    """
                    UPDATE artifact_versions
                    SET artifact_id = ?, project_id = ?, version = ?, status = ?,
                        mime_type = ?, preview_json = ?, dependencies_json = ?,
                        producer_task_id = ?, source_entity_type = ?, source_entity_id = ?,
                        checksum = ?, stale_reason = ?, created_at = ?, confirmed_at = ?
                    WHERE id = ?
                    """,
                    payload,
                )
            self._sync_artifact_dependencies(
                conn,
                project_id=proposal.projectId,
                artifact_id=artifact_id,
                version_id=version_id,
                dependencies=dependencies,
                created_at=now,
            )
            self._apply_artifact_context(
                conn,
                artifact_id=artifact_id,
                version_id=version_id,
                project_id=proposal.projectId,
                source_agent_id="proposal-agent",
                status=status,
            )
            self._propagate_if_confirmed(
                conn,
                project_id=proposal.projectId,
                artifact_id=artifact_id,
                version=proposal.version,
                status=status,
            )
            row = conn.execute(
                "SELECT * FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            return self._to_artifact(conn, row)

    def upsert_from_solution(self, solution: SolutionVersion) -> ArtifactVersion:
        now = _now()
        artifact_id = f"artifact_solution_{solution.projectId}"
        version_id = f"artifact_version_solution_{solution.id}"
        status = _solution_status_to_artifact_status(solution.status)
        preview = ArtifactPreview(
            kind=ArtifactPreviewKind.DOCUMENT,
            summary=_solution_summary(solution),
            sections=[
                ArtifactPreviewSection(
                    id=section.id,
                    title=section.title,
                    content=section.content,
                )
                for section in solution.sections
            ],
        )
        dependencies: list[ArtifactDependency] = []
        if solution.basedOnVersion is not None:
            dependencies.append(
                ArtifactDependency(
                    artifactId=artifact_id,
                    versionId=None,
                    version=solution.basedOnVersion,
                    kind="solution",
                    label=f"上一版推荐实现方案 v{solution.basedOnVersion}",
                    status="HISTORY",
                )
            )
        checksum_payload = {
            "solutionId": solution.id,
            "version": solution.version,
            "status": solution.status.value,
            "basedOnVersion": solution.basedOnVersion,
            "changeSummary": solution.changeSummary,
            "sections": [section.model_dump(mode="json") for section in solution.sections],
        }
        checksum = hashlib.sha256(
            json.dumps(checksum_payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest()

        with self._connect() as conn:
            existing_artifact = conn.execute(
                "SELECT * FROM artifacts WHERE id = ?",
                (artifact_id,),
            ).fetchone()
            if existing_artifact is None:
                conn.execute(
                    """
                    INSERT INTO artifacts (
                      id, project_id, title, kind, status, source_agent_id,
                      current_version_id, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        artifact_id,
                        solution.projectId,
                        "推荐实现方案",
                        ArtifactKind.DOCUMENT.value,
                        status.value,
                        "solution-agent",
                        version_id,
                        now,
                        now,
                    ),
                )
            else:
                max_version = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM artifact_versions WHERE artifact_id = ?",
                    (artifact_id,),
                ).fetchone()[0]
                current_version_id = (
                    version_id
                    if solution.version >= int(max_version)
                    else existing_artifact["current_version_id"]
                )
                artifact_status = (
                    status.value
                    if solution.version >= int(max_version)
                    else existing_artifact["status"]
                )
                conn.execute(
                    """
                    UPDATE artifacts
                    SET title = ?, status = ?, current_version_id = ?,
                        source_agent_id = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        "推荐实现方案",
                        artifact_status,
                        current_version_id,
                        "solution-agent",
                        now,
                        artifact_id,
                    ),
                )

            payload = (
                artifact_id,
                solution.projectId,
                solution.version,
                status.value,
                "application/vnd.zhangwen.solution+json",
                json.dumps(preview.model_dump(mode="json"), ensure_ascii=False),
                json.dumps([item.model_dump(mode="json") for item in dependencies], ensure_ascii=False),
                None,
                "solution",
                solution.id,
                checksum,
                None,
                solution.createdAt,
                solution.confirmedAt,
                version_id,
            )
            existing_version = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            if existing_version is None:
                conn.execute(
                    """
                    INSERT INTO artifact_versions (
                      artifact_id, project_id, version, status, mime_type, preview_json,
                      dependencies_json, producer_task_id, source_entity_type,
                      source_entity_id, checksum, stale_reason, created_at, confirmed_at, id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    payload,
                )
            else:
                conn.execute(
                    """
                    UPDATE artifact_versions
                    SET artifact_id = ?, project_id = ?, version = ?, status = ?,
                        mime_type = ?, preview_json = ?, dependencies_json = ?,
                        producer_task_id = ?, source_entity_type = ?, source_entity_id = ?,
                        checksum = ?, stale_reason = ?, created_at = ?, confirmed_at = ?
                    WHERE id = ?
                    """,
                    payload,
                )
            self._sync_artifact_dependencies(
                conn,
                project_id=solution.projectId,
                artifact_id=artifact_id,
                version_id=version_id,
                dependencies=dependencies,
                created_at=now,
            )
            self._apply_artifact_context(
                conn,
                artifact_id=artifact_id,
                version_id=version_id,
                project_id=solution.projectId,
                source_agent_id="solution-agent",
                status=status,
            )
            self._propagate_if_confirmed(
                conn,
                project_id=solution.projectId,
                artifact_id=artifact_id,
                version=solution.version,
                status=status,
            )
            row = conn.execute(
                "SELECT * FROM artifact_versions WHERE id = ?",
                (version_id,),
            ).fetchone()
            return _to_version(row)

    def mark_proposal_artifacts_stale(self, project_id: str, reason: str) -> int:
        now = _now()
        artifact_id = f"artifact_proposal_{project_id}"
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE artifact_versions
                SET status = ?, stale_reason = ?
                WHERE artifact_id = ? AND status IN (?, ?)
                """,
                (
                    ArtifactStatus.STALE.value,
                    reason,
                    artifact_id,
                    ArtifactStatus.DRAFT.value,
                    ArtifactStatus.APPROVED.value,
                ),
            )
            conn.execute(
                """
                UPDATE artifacts
                SET status = ?, updated_at = ?
                WHERE id = ?
                """,
                (ArtifactStatus.STALE.value, now, artifact_id),
            )
            return int(cursor.rowcount)

    def mark_downstream_artifacts_stale(
        self,
        project_id: str,
        *,
        source_agents: list[str],
        reason: str,
    ) -> int:
        if not source_agents:
            return 0
        now = _now()
        placeholders = ",".join("?" for _ in source_agents)
        with self._connect() as conn:
            artifact_rows = conn.execute(
                f"""
                SELECT id FROM artifacts
                WHERE project_id = ? AND source_agent_id IN ({placeholders})
                """,
                (project_id, *source_agents),
            ).fetchall()
            artifact_ids = [row["id"] for row in artifact_rows]
            if not artifact_ids:
                return 0
            id_placeholders = ",".join("?" for _ in artifact_ids)
            cursor = conn.execute(
                f"""
                UPDATE artifact_versions
                SET status = ?, stale_reason = ?
                WHERE artifact_id IN ({id_placeholders}) AND status IN (?, ?)
                """,
                (
                    ArtifactStatus.STALE.value,
                    reason,
                    *artifact_ids,
                    ArtifactStatus.DRAFT.value,
                    ArtifactStatus.APPROVED.value,
                ),
            )
            conn.execute(
                f"""
                UPDATE artifacts
                SET status = ?, updated_at = ?
                WHERE id IN ({id_placeholders})
                """,
                (ArtifactStatus.STALE.value, now, *artifact_ids),
            )
            return int(cursor.rowcount)

    def mark_downstream_artifacts_outdated_for_upstream(
        self,
        project_id: str,
        *,
        upstream_artifact_id: str,
        upstream_version: int,
        reason: str,
    ) -> int:
        now = _now()
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT artifact_id, artifact_version_id
                FROM artifact_dependencies
                WHERE project_id = ?
                  AND upstream_artifact_id = ?
                  AND upstream_version = ?
                """,
                (project_id, upstream_artifact_id, upstream_version),
            ).fetchall()
            return self._mark_dependency_rows_outdated(conn, rows, reason=reason, now=now)

    def propagate_outdated_from_confirmed_version(
        self,
        project_id: str,
        *,
        upstream_artifact_id: str,
        confirmed_version: int,
        reason: str,
    ) -> int:
        now = _now()
        with self._connect() as conn:
            return self._propagate_confirmed_version(
                conn,
                project_id=project_id,
                upstream_artifact_id=upstream_artifact_id,
                confirmed_version=confirmed_version,
                reason=reason,
                now=now,
            )

    def _propagate_if_confirmed(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        artifact_id: str,
        version: int,
        status: ArtifactStatus,
    ) -> int:
        if status != ArtifactStatus.APPROVED:
            return 0
        return self._propagate_confirmed_version(
            conn,
            project_id=project_id,
            upstream_artifact_id=artifact_id,
            confirmed_version=version,
            reason=f"上游产物 {artifact_id} 已确认新版本 v{version}。",
            now=_now(),
        )

    def _propagate_confirmed_version(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        upstream_artifact_id: str,
        confirmed_version: int,
        reason: str,
        now: str,
    ) -> int:
        rows = conn.execute(
            """
            SELECT DISTINCT artifact_id, artifact_version_id
            FROM artifact_dependencies
            WHERE project_id = ?
              AND upstream_artifact_id = ?
              AND upstream_version IS NOT NULL
              AND upstream_version < ?
            """,
            (project_id, upstream_artifact_id, confirmed_version),
        ).fetchall()
        return self._mark_dependency_rows_outdated(conn, rows, reason=reason, now=now)

    def _mark_dependency_rows_outdated(
        self,
        conn: sqlite3.Connection,
        rows: list[sqlite3.Row],
        *,
        reason: str,
        now: str,
    ) -> int:
        if not rows:
            return 0
        version_ids = sorted({str(row["artifact_version_id"]) for row in rows})
        placeholders = ",".join("?" for _ in version_ids)
        cursor = conn.execute(
            f"""
            UPDATE artifact_versions
            SET status = ?, domain_status = ?, stale_reason = ?
            WHERE id IN ({placeholders}) AND status <> ?
            """,
            (
                ArtifactStatus.STALE.value,
                DomainArtifactStatus.OUTDATED.value,
                reason,
                *version_ids,
                ArtifactStatus.ARCHIVED.value,
            ),
        )
        conn.execute(
            f"""
            UPDATE artifacts
            SET status = ?, domain_status = ?, updated_at = ?
            WHERE current_version_id IN ({placeholders}) AND status <> ?
            """,
            (
                ArtifactStatus.STALE.value,
                DomainArtifactStatus.OUTDATED.value,
                now,
                *version_ids,
                ArtifactStatus.ARCHIVED.value,
            ),
        )
        return int(cursor.rowcount)

    def _sync_artifact_dependencies(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        artifact_id: str,
        version_id: str,
        dependencies: list[ArtifactDependency],
        created_at: str,
    ) -> None:
        conn.execute(
            "DELETE FROM artifact_dependencies WHERE artifact_version_id = ?",
            (version_id,),
        )
        for index, dependency in enumerate(dependencies):
            if not dependency.artifactId:
                raise ValueError("artifact dependency must include artifactId")
            if dependency.version is None:
                raise ValueError("artifact dependency must include version")
            conn.execute(
                """
                INSERT INTO artifact_dependencies (
                  id, project_id, artifact_id, artifact_version_id,
                  upstream_artifact_id, upstream_version_id, upstream_version,
                  relation, kind, label, status, required, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"adep_{version_id}_{index}",
                    project_id,
                    artifact_id,
                    version_id,
                    dependency.artifactId,
                    dependency.versionId,
                    dependency.version,
                    dependency.relation or "requires",
                    dependency.kind,
                    dependency.label,
                    dependency.status,
                    1 if dependency.required else 0,
                    created_at,
                ),
            )

    def _apply_artifact_context(
        self,
        conn: sqlite3.Connection,
        *,
        artifact_id: str,
        version_id: str,
        project_id: str,
        source_agent_id: str,
        status: ArtifactStatus,
    ) -> None:
        owner_type = _owner_type_for_source_agent(source_agent_id)
        owner_row = conn.execute(
            """
            SELECT id, conversation_id FROM project_experts
            WHERE project_id = ?
              AND expert_type = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            ORDER BY added_at ASC
            LIMIT 1
            """,
            (project_id, owner_type),
        ).fetchone()
        if owner_row is None:
            owner_row = conn.execute(
                """
                SELECT id, conversation_id FROM project_experts
                WHERE project_id = ?
                  AND expert_type IN ('problem_guide', 'question_guide', 'ideator')
                  AND removed_at IS NULL
                  AND archived_legacy_thread = 0
                ORDER BY CASE expert_type
                  WHEN 'problem_guide' THEN 1
                  WHEN 'question_guide' THEN 2
                  WHEN 'ideator' THEN 3
                  ELSE 99
                END, added_at ASC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            owner_type = "problem_guide" if owner_row is not None else owner_type
        context_row = conn.execute(
            "SELECT revision FROM project_shared_contexts WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        revision = int(context_row["revision"]) if context_row else 1
        conn.execute(
            """
            UPDATE artifacts
            SET owner_expert_id = ?,
                owner_expert_type = ?,
                source_conversation_id = ?,
                shared_context_revision = ?,
                domain_status = COALESCE(domain_status, CASE status
                  WHEN 'DRAFT' THEN 'draft'
                  WHEN 'GENERATING' THEN 'pending_confirmation'
                  WHEN 'NEEDS_REVIEW' THEN 'pending_confirmation'
                  WHEN 'APPROVED' THEN 'confirmed'
                  WHEN 'STALE' THEN 'outdated'
                  WHEN 'ARCHIVED' THEN 'archived'
                  ELSE 'pending_confirmation'
                END)
            WHERE id = ?
            """,
            (
                owner_row["id"] if owner_row else None,
                owner_type,
                owner_row["conversation_id"] if owner_row else None,
                revision,
                artifact_id,
            ),
        )
        conn.execute(
            """
            UPDATE artifact_versions
            SET shared_context_revision = ?,
                domain_status = COALESCE(domain_status, CASE status
                  WHEN 'DRAFT' THEN 'draft'
                  WHEN 'GENERATING' THEN 'pending_confirmation'
                  WHEN 'NEEDS_REVIEW' THEN 'pending_confirmation'
                  WHEN 'APPROVED' THEN 'confirmed'
                  WHEN 'STALE' THEN 'outdated'
                  WHEN 'ARCHIVED' THEN 'archived'
                  ELSE 'pending_confirmation'
                END)
            WHERE id = ?
            """,
            (revision, version_id),
        )
        self._sync_transition_domain_status(
            conn,
            artifact_id=artifact_id,
            version_id=version_id,
            status=status,
        )

    def _sync_transition_domain_status(
        self,
        conn: sqlite3.Connection,
        *,
        artifact_id: str,
        version_id: str,
        status: ArtifactStatus,
    ) -> None:
        transition = _domain_status_transition(status)
        if transition is None:
            return
        previous_statuses, next_status = transition
        placeholders = ",".join("?" for _ in previous_statuses)
        parameters = (next_status.value, *[item.value for item in previous_statuses])
        conn.execute(
            f"""
            UPDATE artifact_versions
            SET domain_status = ?
            WHERE id = ?
              AND domain_status IN ({placeholders})
            """,
            (parameters[0], version_id, *parameters[1:]),
        )
        conn.execute(
            f"""
            UPDATE artifacts
            SET domain_status = ?
            WHERE id = ? AND current_version_id = ?
              AND domain_status IN ({placeholders})
            """,
            (parameters[0], artifact_id, version_id, *parameters[1:]),
        )

    def _to_artifact(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
    ) -> ArtifactDefinition:
        versions = [
            _to_version(version_row)
            for version_row in conn.execute(
                """
                SELECT * FROM artifact_versions
                WHERE artifact_id = ?
                ORDER BY version DESC
                """,
                (row["id"],),
            ).fetchall()
        ]
        return ArtifactDefinition(
            id=row["id"],
            projectId=row["project_id"],
            title=row["title"],
            kind=ArtifactKind(row["kind"]),
            status=ArtifactStatus(row["status"]),
            domainStatus=_resolved_domain_status(
                ArtifactStatus(row["status"]),
                row["domain_status"],
            ),
            sourceAgentId=row["source_agent_id"],
            ownerExpertId=row["owner_expert_id"],
            ownerExpertType=row["owner_expert_type"],
            legacyOwnerExpert=row["legacy_owner_expert"],
            creatorLegacyExpert=row["creator_legacy_expert"],
            sourceConversationId=row["source_conversation_id"],
            sharedContextRevision=row["shared_context_revision"],
            currentVersionId=row["current_version_id"],
            versions=versions,
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
        )


def _to_version(row: sqlite3.Row) -> ArtifactVersion:
    preview_data: dict[str, Any] = json.loads(row["preview_json"])
    dependencies_data: list[dict[str, Any]] = json.loads(row["dependencies_json"])
    return ArtifactVersion(
        id=row["id"],
        artifactId=row["artifact_id"],
        projectId=row["project_id"],
        version=row["version"],
        status=ArtifactStatus(row["status"]),
        domainStatus=_resolved_domain_status(
            ArtifactStatus(row["status"]),
            row["domain_status"],
        ),
        mimeType=row["mime_type"],
        preview=ArtifactPreview(**preview_data),
        dependencies=[ArtifactDependency(**item) for item in dependencies_data],
        producerTaskId=row["producer_task_id"],
        sourceEntityType=row["source_entity_type"],
        sourceEntityId=row["source_entity_id"],
        checksum=row["checksum"],
        staleReason=row["stale_reason"],
        sharedContextRevision=row["shared_context_revision"],
        createdAt=row["created_at"],
        confirmedAt=row["confirmed_at"],
    )


def _to_artifact_file(row: sqlite3.Row) -> ArtifactFile:
    bounds = json.loads(row["bounds_json"]) if row["bounds_json"] else None
    return ArtifactFile(
        id=row["id"],
        artifactId=row["artifact_id"],
        artifactVersionId=row["artifact_version_id"],
        projectId=row["project_id"],
        role=row["role"],
        fileName=row["file_name"],
        mimeType=row["mime_type"],
        byteSize=row["byte_size"],
        sha256=row["sha256"],
        triangleCount=row["triangle_count"],
        bounds=bounds,
        createdAt=row["created_at"],
    )


def _proposal_status_to_artifact_status(status: ProposalStatus) -> ArtifactStatus:
    mapping = {
        ProposalStatus.DRAFT: ArtifactStatus.DRAFT,
        ProposalStatus.APPROVED: ArtifactStatus.APPROVED,
        ProposalStatus.REJECTED: ArtifactStatus.REJECTED,
        ProposalStatus.STALE: ArtifactStatus.STALE,
        ProposalStatus.SUPERSEDED: ArtifactStatus.STALE,
    }
    return mapping[status]


def _solution_status_to_artifact_status(status: SolutionStatus) -> ArtifactStatus:
    mapping = {
        SolutionStatus.DRAFT: ArtifactStatus.NEEDS_REVIEW,
        SolutionStatus.CONFIRMED: ArtifactStatus.APPROVED,
        SolutionStatus.SUPERSEDED: ArtifactStatus.STALE,
        SolutionStatus.OUTDATED: ArtifactStatus.STALE,
    }
    return mapping[status]


def _owner_type_for_source_agent(source_agent_id: str) -> str:
    if source_agent_id in {"spec-agent", "code-agent", "deploy-agent"}:
        return "smart_engineer"
    if source_agent_id == "cad-agent":
        return "structure_engineer"
    return "problem_guide"


def _domain_status_for_artifact_status(status: ArtifactStatus) -> DomainArtifactStatus:
    mapping = {
        ArtifactStatus.DRAFT: DomainArtifactStatus.DRAFT,
        ArtifactStatus.GENERATING: DomainArtifactStatus.PENDING_CONFIRMATION,
        ArtifactStatus.NEEDS_REVIEW: DomainArtifactStatus.PENDING_CONFIRMATION,
        ArtifactStatus.APPROVED: DomainArtifactStatus.CONFIRMED,
        ArtifactStatus.REJECTED: DomainArtifactStatus.PENDING_CONFIRMATION,
        ArtifactStatus.STALE: DomainArtifactStatus.OUTDATED,
        ArtifactStatus.FAILED: DomainArtifactStatus.PENDING_CONFIRMATION,
        ArtifactStatus.ARCHIVED: DomainArtifactStatus.ARCHIVED,
    }
    return mapping[status]


def _domain_status_transition(
    status: ArtifactStatus,
) -> tuple[tuple[DomainArtifactStatus, ...], DomainArtifactStatus] | None:
    if status == ArtifactStatus.NEEDS_REVIEW:
        return ((DomainArtifactStatus.DRAFT,), DomainArtifactStatus.PENDING_CONFIRMATION)
    if status == ArtifactStatus.APPROVED:
        return (
            (
                DomainArtifactStatus.DRAFT,
                DomainArtifactStatus.PENDING_CONFIRMATION,
            ),
            DomainArtifactStatus.CONFIRMED,
        )
    return None


def _resolved_domain_status(
    status: ArtifactStatus,
    stored_status: str | None,
) -> DomainArtifactStatus:
    domain_status = (
        DomainArtifactStatus(stored_status)
        if stored_status
        else _domain_status_for_artifact_status(status)
    )
    transition = _domain_status_transition(status)
    if transition is not None and domain_status in transition[0]:
        return transition[1]
    return domain_status


def _solution_summary(solution: SolutionVersion) -> str:
    title = next(
        (section.content for section in solution.sections if section.id == "goal"),
        "当前推荐实现方案",
    )
    summary = title.strip().replace("\n", " ")
    if len(summary) > 96:
        summary = f"{summary[:96]}..."
    if solution.changeSummary:
        return f"推荐实现方案 v{solution.version}；{solution.changeSummary[0]}"
    return f"推荐实现方案 v{solution.version}；{summary}"


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
