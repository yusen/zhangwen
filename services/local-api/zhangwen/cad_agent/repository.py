"""SQLite repository for CAD Agent runs."""

from __future__ import annotations

import json
import hashlib
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.artifacts.models import ArtifactDependency, ArtifactStatus
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.cad_agent.artifact_store import PublishedCadFile
from zhangwen.cad_agent.generator import GeneratedCad, GeneratedCadFile, template_specs
from zhangwen.cad_agent.template_catalog import production_parameter_spec
from zhangwen.cad_agent.sizing import resolve_enclosure_sizing
from zhangwen.cad_agent.job_repository import CadJobRepository
from zhangwen.cad_agent.models import (
    SUPPORTED_TEMPLATE_REVISIONS,
    CadDraft,
    CadBuildSpec,
    CadResolvedComponent,
    CadFile,
    CadFileKind,
    CadRun,
    CadRunStatus,
    CadTemplateKind,
    CadValidation,
    CadValidationCheck,
    CadParameter,
    CadOutputRole,
    CadJob,
    CadJobStatus,
)
from zhangwen.cad_agent.worker_protocol import canonical_json_bytes
from zhangwen.cad_agent.profile_repository import (
    MechanicalProfileSnapshot,
    MechanicalProfileRepository,
    canonical_profile_id,
)
from zhangwen.cad_agent.intake import (
    CAD_VIRTUAL_HARDWARE_PREFIX,
    CadProfileIntake,
    assert_current_cad_intake_revision,
    bind_current_cad_intake_revision,
)
from zhangwen.cad_agent.chat_projection import sync_cad_message_projection
from zhangwen.specs.models import SpecRun, SpecRunStatus
from zhangwen.projects.models import ExpertType


class CadRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get_current_cad(self, project_id: str) -> CadRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM cad_runs
                WHERE project_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return self._to_run(conn, row) if row else None

    def get_cad(self, project_id: str, cad_run_id: str) -> CadRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM cad_runs WHERE id = ? AND project_id = ?",
                (cad_run_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("CAD 运行不存在。")
            return self._to_run(conn, row)

    def create_draft(
        self,
        *,
        project_id: str,
        draft: CadDraft,
        source_message_id: str,
        generated_by_expert_id: str,
    ) -> CadRun:
        if draft.specRunId is not None:
            spec = self._load_spec(project_id, draft.specRunId)
            if spec.status != SpecRunStatus.APPROVED:
                raise ValueError("CAD 草稿引用的 Spec 尚未确认。")
        now = _now()
        cad_run_id = _id("cad")
        validation = CadValidation(
            ok=False,
            checks=[
                CadValidationCheck(
                    dimension="build:pending",
                    severity="WARNING",
                    message="结构参数已固化，等待本地 CAD Worker 建模。",
                    details=f"template={draft.templateKind.value}",
                )
            ],
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            draft = bind_current_cad_intake_revision(
                conn,
                project_id=project_id,
                draft=draft,
            )
            parameters = _parameters_for_draft(draft)
            staleable_statuses = (
                CadRunStatus.DRAFT.value,
                CadRunStatus.VALIDATED.value,
                CadRunStatus.READY_FOR_REVIEW.value,
                CadRunStatus.FAILED.value,
                CadRunStatus.CANCELED.value,
                CadRunStatus.REJECTED.value,
            )
            status_placeholders = ", ".join("?" for _ in staleable_statuses)
            stale_reason = "结构工程师已生成新的 CAD 草稿。"
            candidate_rows = conn.execute(
                f"""
                SELECT cr.id, cr.source_message_id, cr.artifact_id,
                       cr.artifact_version_id, m.structured_payload_json
                FROM cad_runs cr
                LEFT JOIN messages m
                  ON m.id = cr.source_message_id AND m.project_id = cr.project_id
                WHERE cr.project_id = ? AND cr.status IN ({status_placeholders})
                """,
                (project_id, *staleable_statuses),
            ).fetchall()
            version = int(
                conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM cad_runs WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]
            ) + 1
            conn.execute(
                f"""
                UPDATE cad_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN ({status_placeholders})
                """,
                (
                    CadRunStatus.STALE.value,
                    stale_reason,
                    now,
                    project_id,
                    *staleable_statuses,
                ),
            )
            CadProfileIntake._mark_cad_artifacts_stale(
                conn,
                project_id=project_id,
                candidate_rows=candidate_rows,
                reason=stale_reason,
                now=now,
            )
            for candidate in candidate_rows:
                CadProfileIntake._mark_cad_projection_stale(
                    conn,
                    project_id=project_id,
                    cad_run_id=str(candidate["id"]),
                    source_message_id=candidate["source_message_id"],
                    payload_json=candidate["structured_payload_json"],
                    now=now,
                )
            conn.execute(
                """
                INSERT INTO cad_runs (
                  id, project_id, spec_run_id, template_kind, version, status,
                  command_label, parameters_json, validation_json, artifact_id,
                  artifact_version_id, source_message_id, generated_by_expert_id,
                  engine_id, engine_version, design_state_json, latest_job_id,
                  stale_reason, created_at, updated_at, confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?,
                          'cadquery-deterministic', '2.8.0', ?, NULL, NULL, ?, ?, NULL)
                """,
                (
                    cad_run_id,
                    project_id,
                    draft.specRunId,
                    draft.templateKind.value,
                    version,
                    CadRunStatus.DRAFT.value,
                    "cadquery-deterministic",
                    json.dumps(
                        [item.model_dump(mode="json") for item in parameters],
                        ensure_ascii=False,
                    ),
                    json.dumps(validation.model_dump(mode="json"), ensure_ascii=False),
                    source_message_id,
                    generated_by_expert_id,
                    json.dumps(draft.model_dump(mode="json"), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM cad_runs WHERE id = ?",
                (cad_run_id,),
            ).fetchone()
            return self._to_run(conn, row)

    def create_job(
        self,
        *,
        project_id: str,
        cad_run_id: str,
        client_request_id: str | None,
    ) -> CadJob:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT cr.*, pe.expert_type AS generated_expert_type
                FROM cad_runs cr
                LEFT JOIN project_experts pe
                  ON pe.id = cr.generated_by_expert_id
                WHERE cr.id = ? AND cr.project_id = ?
                """,
                (cad_run_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("CAD 运行不存在。")
            draft = CadDraft.model_validate(json.loads(row["design_state_json"] or "{}"))
            assert_current_cad_intake_revision(
                conn,
                project_id=project_id,
                draft=draft,
                run_created_at=str(row["created_at"]),
            )
            existing = None
            if client_request_id:
                existing = conn.execute(
                    """
                    SELECT cad_run_id FROM cad_jobs
                    WHERE project_id = ? AND client_request_id = ?
                    """,
                    (project_id, client_request_id),
                ).fetchone()
            idempotent_retry = existing is not None and str(existing["cad_run_id"]) == cad_run_id
            if row["status"] not in {
                CadRunStatus.DRAFT.value,
                CadRunStatus.FAILED.value,
                CadRunStatus.CANCELED.value,
            } and not idempotent_retry:
                raise ValueError("CAD_RUN_NOT_BUILDABLE")
            if row["generated_expert_type"] != ExpertType.STRUCTURE_ENGINEER.value:
                raise ValueError("CAD_SOURCE_EXPERT_INVALID")
            if row["engine_id"] != "cadquery-deterministic":
                raise ValueError("CAD_ENGINE_UNSUPPORTED")
        template_revision = draft.templateRevision or SUPPORTED_TEMPLATE_REVISIONS[draft.templateKind]
        if template_revision != SUPPORTED_TEMPLATE_REVISIONS[draft.templateKind]:
            raise ValueError("CAD_TEMPLATE_REVISION_UNSUPPORTED")
        job_id = _job_id(project_id, client_request_id)
        resolved_components, profile_snapshots = _materialize_components_for_draft(
            self._db_path,
            project_id,
            draft,
        )
        if draft.templateKind is CadTemplateKind.COMPONENT_MOUNT:
            if len(resolved_components) != 1 or len(profile_snapshots) != 1:
                raise ValueError("COMPONENT_MOUNT requires exactly one mechanical profile")
            resolved_parameters = dict(draft.parameters)
            sizing_evidence = None
        elif draft.templateKind is CadTemplateKind.FREEFORM_STRUCTURE:
            if resolved_components or profile_snapshots or draft.geometry is None:
                raise ValueError("FREEFORM_STRUCTURE requires geometry without hardware")
            resolved_parameters = {}
            sizing_evidence = None
        elif draft.templateKind is CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM:
            if resolved_components or profile_snapshots or draft.geometry is not None:
                raise ValueError("UNIHIKER_K10_PHOTO_ALBUM requires fixed local geometry")
            if draft.parameters:
                raise ValueError("UNIHIKER_K10_PHOTO_ALBUM does not accept parameters")
            resolved_parameters = {}
            sizing_evidence = None
        else:
            resolved_parameters, sizing_evidence = resolve_enclosure_sizing(
                draft.parameters,
                [CadResolvedComponent.model_validate(item) for item in resolved_components],
                [MechanicalProfileSnapshot.model_validate(item) for item in profile_snapshots],
            )
        request_payload = draft.model_dump(mode="json")
        request_payload.update(
            {
                "jobId": job_id,
                "projectId": project_id,
                "templateRevision": template_revision,
                "components": resolved_components,
                "profileSnapshots": profile_snapshots,
                "parameters": resolved_parameters,
                "sizingEvidence": (
                    sizing_evidence.model_dump(mode="json")
                    if sizing_evidence is not None
                    else None
                ),
            }
        )
        request = CadBuildSpec.model_validate(request_payload)
        request_hash = hashlib.sha256(canonical_json_bytes(request)).hexdigest()
        job = CadJobRepository(self._db_path).create(
            job_id=job_id,
            project_id=project_id,
            cad_run_id=cad_run_id,
            client_request_id=client_request_id,
            source_message_id=row["source_message_id"],
            project_expert_id=row["generated_by_expert_id"],
            spec_run_id=row["spec_run_id"],
            request_hash=request_hash,
            request=request,
            created_at=_now(),
        )
        resolved_draft = draft.model_copy(update={"parameters": resolved_parameters})
        resolved_cad_parameters = _parameters_for_draft(resolved_draft)
        with self._connect() as conn:
            conn.execute(
                "UPDATE cad_runs SET parameters_json = ?, updated_at = ? WHERE id = ?",
                (
                    json.dumps(
                        [item.model_dump(mode="json") for item in resolved_cad_parameters],
                        ensure_ascii=False,
                    ),
                    _now(),
                    cad_run_id,
                ),
            )
        sync_cad_message_projection(self._db_path, self.get_cad(project_id, cad_run_id))
        return job

    def retry_job(
        self,
        *,
        project_id: str,
        job_id: str,
        client_request_id: str | None,
    ) -> CadJob:
        previous = CadJobRepository(self._db_path).get(project_id, job_id)
        with self._connect() as conn:
            run_row = self._row(conn, project_id, previous.cadRunId)
            assert_current_cad_intake_revision(
                conn,
                project_id=project_id,
                draft=previous.request,
                run_created_at=str(run_row["created_at"]),
            )
        if previous.status not in {
            CadJobStatus.FAILED,
            CadJobStatus.TIMED_OUT,
            CadJobStatus.INTERRUPTED,
        } or (previous.error is not None and not previous.error.retryable):
            raise ValueError("CAD_JOB_NOT_RETRYABLE")
        next_job_id = _job_id(project_id, client_request_id)
        request = previous.request.model_copy(update={"jobId": next_job_id})
        request_hash = hashlib.sha256(canonical_json_bytes(request)).hexdigest()
        job = CadJobRepository(self._db_path).create(
            job_id=next_job_id,
            project_id=project_id,
            cad_run_id=previous.cadRunId,
            client_request_id=client_request_id,
            source_message_id=previous.sourceMessageId,
            project_expert_id=previous.projectExpertId,
            spec_run_id=previous.specRunId,
            request_hash=request_hash,
            request=request,
            created_at=_now(),
        )
        sync_cad_message_projection(
            self._db_path,
            self.get_cad(project_id, previous.cadRunId),
        )
        return job

    def finalize_job_success(
        self,
        *,
        job_id: str,
        worker_result: dict[str, object],
        published_files: list[PublishedCadFile],
    ) -> CadRun:
        completed_at = _now()
        validation = _cad_validation(worker_result.get("validation"))
        if not validation.ok:
            raise ValueError("CAD_VALIDATION_FAILED")
        manifest = worker_result.get("manifest")
        if not isinstance(manifest, dict):
            raise ValueError("CAD_WORKER_MANIFEST_INVALID")
        file_ids = {item.file_name: _id("artifact_file") for item in published_files}
        preview = next(
            (item for item in published_files if item.role == CadOutputRole.GLB_PREVIEW.value),
            None,
        )
        manifest_file = next(
            (item for item in published_files if item.role == CadOutputRole.MANIFEST.value),
            None,
        )
        if preview is None or manifest_file is None:
            raise ValueError("CAD_REQUIRED_OUTPUT_MISSING")

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            job_row = conn.execute(
                "SELECT * FROM cad_jobs WHERE id = ?",
                (job_id,),
            ).fetchone()
            if job_row is None:
                raise ValueError("CAD Job 不存在。")
            run_row = self._row(conn, str(job_row["project_id"]), str(job_row["cad_run_id"]))
            if (
                job_row["status"] != CadJobStatus.RUNNING.value
                or run_row["status"] != CadRunStatus.RUNNING.value
                or run_row["latest_job_id"] != job_id
            ):
                raise ValueError("CAD_JOB_NOT_RUNNING")
            assert_current_cad_intake_revision(
                conn,
                project_id=str(job_row["project_id"]),
                draft=CadBuildSpec.model_validate_json(job_row["request_json"]),
                run_created_at=str(run_row["created_at"]),
            )

            project_id = str(job_row["project_id"])
            cad_run_id = str(job_row["cad_run_id"])
            artifact_id = cad_artifact_id(project_id)
            version_id = cad_artifact_version_id(project_id, cad_run_id)
            spec = self._load_spec(project_id, str(run_row["spec_run_id"])) if run_row["spec_run_id"] else None
            artifact_repository = ArtifactRepository(self._db_path)
            version = artifact_repository.upsert_model_artifact(
                artifact_id=artifact_id,
                project_id=project_id,
                title="结构件 CAD 模型",
                status=ArtifactStatus.NEEDS_REVIEW,
                source_agent_id="cad-agent",
                source_entity_type="cad",
                source_entity_id=cad_run_id,
                source_version=int(run_row["version"]),
                content=None,
                summary=f"{_template_label(CadTemplateKind(run_row['template_kind']))} v{run_row['version']}",
                model_url=(
                    f"/api/projects/{project_id}/artifacts/{artifact_id}/versions/"
                    f"{version_id}/files/{file_ids[preview.file_name]}"
                ),
                model_file_id=file_ids[preview.file_name],
                checksum=manifest_file.sha256,
                mime_type=preview.mime_type,
                dependencies=_artifact_dependencies(spec),
                connection=conn,
            )
            if version.id != version_id:
                raise ValueError("CAD_ARTIFACT_VERSION_MISMATCH")

            for item in published_files:
                artifact_file_id = file_ids[item.file_name]
                artifact_repository.insert_artifact_file(
                    conn,
                    file_id=artifact_file_id,
                    artifact_id=artifact_id,
                    artifact_version_id=version_id,
                    project_id=project_id,
                    role=item.role,
                    file_name=item.file_name,
                    storage_key=item.storage_key,
                    mime_type=item.mime_type,
                    byte_size=item.byte_size,
                    sha256=item.sha256,
                    triangle_count=item.triangle_count,
                    bounds=item.bounds,
                    created_at=completed_at,
                )
                conn.execute(
                    """
                    INSERT INTO cad_files (
                      id, cad_run_id, project_id, kind, role, path, file_name,
                      storage_key, mime_type, content, byte_size, sha256, bounds_json,
                      triangle_count, artifact_file_id, artifact_id,
                      artifact_version_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, '', ?, ?, ?, NULL, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        _id("cad_file"),
                        cad_run_id,
                        project_id,
                        _legacy_file_kind(item.role),
                        item.role,
                        item.file_name,
                        item.storage_key,
                        item.mime_type,
                        item.byte_size,
                        item.sha256,
                        json.dumps(item.bounds, ensure_ascii=False, sort_keys=True)
                        if item.bounds
                        else None,
                        item.triangle_count,
                        artifact_file_id,
                        artifact_id,
                        version_id,
                        completed_at,
                    ),
                )

            conn.execute(
                """
                UPDATE cad_runs
                SET validation_json = ?, artifact_id = ?, artifact_version_id = ?,
                    engine_id = ?, engine_version = ?, stale_reason = NULL,
                    updated_at = ?
                WHERE id = ? AND latest_job_id = ? AND status = ?
                """,
                (
                    validation.model_dump_json(),
                    artifact_id,
                    version_id,
                    str(manifest.get("engineId")),
                    str(manifest.get("engineVersion")),
                    completed_at,
                    cad_run_id,
                    job_id,
                    CadRunStatus.RUNNING.value,
                ),
            )
            safe_result = {
                "manifest": {
                    key: value for key, value in manifest.items() if key != "files"
                },
                "files": [
                    {
                        "id": file_ids[item.file_name],
                        "role": item.role,
                        "fileName": item.file_name,
                        "mimeType": item.mime_type,
                        "byteSize": item.byte_size,
                        "sha256": item.sha256,
                        "triangleCount": item.triangle_count,
                        "bounds": item.bounds,
                    }
                    for item in published_files
                ],
                "validation": validation.model_dump(mode="json"),
                "geometrySummary": worker_result.get("geometrySummary"),
            }
            CadJobRepository(self._db_path).finish_success_with_conn(
                conn,
                job_id,
                safe_result,
                completed_at,
            )
        cad_run = self.get_cad(str(job_row["project_id"]), str(job_row["cad_run_id"]))
        sync_cad_message_projection(self._db_path, cad_run)
        return cad_run

    def create_from_generated(
        self,
        *,
        project_id: str,
        spec: SpecRun,
        generated: GeneratedCad,
    ) -> CadRun:
        if spec.status != SpecRunStatus.APPROVED:
            raise ValueError("只有已确认 Spec 可以生成 CAD。")
        now = _now()
        cad_run_id = _id("cad")
        status = (
            CadRunStatus.READY_FOR_REVIEW
            if generated.validation.ok
            else CadRunStatus.FAILED
        )
        with self._connect() as conn:
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM cad_runs WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = int(max_version) + 1
            conn.execute(
                """
                UPDATE cad_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN (?, ?, ?)
                """,
                (
                    CadRunStatus.STALE.value,
                    "CAD 已生成新版本。",
                    now,
                    project_id,
                    CadRunStatus.DRAFT.value,
                    CadRunStatus.VALIDATED.value,
                    CadRunStatus.READY_FOR_REVIEW.value,
                ),
            )
            conn.execute(
                """
                INSERT INTO cad_runs (
                  id, project_id, spec_run_id, template_kind, version, status,
                  command_label, parameters_json, validation_json, artifact_id,
                  artifact_version_id, stale_reason, created_at, updated_at,
                  confirmed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, ?, ?, NULL)
                """,
                (
                    cad_run_id,
                    project_id,
                    spec.id,
                    generated.template_kind.value,
                    version,
                    status.value,
                    generated.command_label,
                    json.dumps([item.model_dump(mode="json") for item in generated.parameters], ensure_ascii=False),
                    json.dumps(generated.validation.model_dump(mode="json"), ensure_ascii=False),
                    now,
                    now,
                ),
            )
            for file in generated.files:
                self._insert_file(conn, cad_run_id, project_id, file, now)
            row = conn.execute(
                "SELECT * FROM cad_runs WHERE id = ?",
                (cad_run_id,),
            ).fetchone()
            cad_run = self._to_run(conn, row)
        self.sync_artifact(cad_run, spec)
        return self.get_cad(project_id, cad_run_id)

    def confirm_cad(self, project_id: str, cad_run_id: str) -> CadRun:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row(conn, project_id, cad_run_id)
            draft = (
                CadDraft.model_validate_json(row["design_state_json"])
                if row["design_state_json"]
                else None
            )
            assert_current_cad_intake_revision(
                conn,
                project_id=project_id,
                draft=draft,
                run_created_at=str(row["created_at"]),
            )
            if row["status"] not in {
                CadRunStatus.READY_FOR_REVIEW.value,
                CadRunStatus.APPROVED.value,
            }:
                raise ValueError("只有待确认 CAD 可以确认。")
            latest = conn.execute(
                "SELECT id FROM cad_runs WHERE project_id = ? ORDER BY version DESC LIMIT 1",
                (project_id,),
            ).fetchone()
            if latest is None or latest["id"] != cad_run_id:
                raise ValueError("只能确认当前最新 CAD 版本。")
            validation = CadValidation.model_validate_json(row["validation_json"])
            if not validation.ok:
                raise ValueError("CAD 必须通过几何校验才可以确认。")
            previous = conn.execute(
                """
                SELECT artifact_version_id FROM cad_runs
                WHERE project_id = ? AND id <> ? AND status = ?
                """,
                (project_id, cad_run_id, CadRunStatus.APPROVED.value),
            ).fetchall()
            conn.execute(
                """
                UPDATE cad_runs SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND id <> ? AND status = ?
                """,
                (
                    CadRunStatus.STALE.value,
                    f"CAD 已确认新版本 {row['version']}。",
                    now,
                    project_id,
                    cad_run_id,
                    CadRunStatus.APPROVED.value,
                ),
            )
            previous_ids = [str(item["artifact_version_id"]) for item in previous if item["artifact_version_id"]]
            if previous_ids:
                placeholders = ",".join("?" for _ in previous_ids)
                conn.execute(
                    f"""
                    UPDATE artifact_versions
                    SET status = ?, domain_status = ?, stale_reason = ?
                    WHERE id IN ({placeholders})
                    """,
                    (
                        ArtifactStatus.STALE.value,
                        "outdated",
                        f"CAD 已确认新版本 {row['version']}。",
                        *previous_ids,
                    ),
                )
            conn.execute(
                """
                UPDATE cad_runs
                SET status = ?, confirmed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (CadRunStatus.APPROVED.value, now, now, cad_run_id),
            )
            if row["artifact_id"] and row["artifact_version_id"]:
                ArtifactRepository(self._db_path).transition_model_artifact(
                    conn,
                    project_id=project_id,
                    artifact_id=str(row["artifact_id"]),
                    artifact_version_id=str(row["artifact_version_id"]),
                    status=ArtifactStatus.APPROVED,
                    stale_reason=None,
                    confirmed_at=now,
                    make_current=True,
                    now=now,
                )
            updated = conn.execute(
                "SELECT * FROM cad_runs WHERE id = ?",
                (cad_run_id,),
            ).fetchone()
            cad_run = self._to_run(conn, updated)
        sync_cad_message_projection(self._db_path, cad_run)
        return cad_run

    def reject_cad(
        self,
        project_id: str,
        cad_run_id: str,
        reason: str | None,
    ) -> CadRun:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row(conn, project_id, cad_run_id)
            if row["status"] not in {
                CadRunStatus.READY_FOR_REVIEW.value,
                CadRunStatus.APPROVED.value,
                CadRunStatus.REJECTED.value,
            }:
                raise ValueError("只有待确认 CAD 可以退回。")
            conn.execute(
                """
                UPDATE cad_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (CadRunStatus.REJECTED.value, reason, now, cad_run_id),
            )
            if row["artifact_id"] and row["artifact_version_id"]:
                previous = conn.execute(
                    """
                    SELECT artifact_version_id FROM cad_runs
                    WHERE project_id = ? AND version < ? AND status = ?
                      AND artifact_version_id IS NOT NULL
                    ORDER BY version DESC LIMIT 1
                    """,
                    (project_id, row["version"], CadRunStatus.APPROVED.value),
                ).fetchone()
                ArtifactRepository(self._db_path).transition_model_artifact(
                    conn,
                    project_id=project_id,
                    artifact_id=str(row["artifact_id"]),
                    artifact_version_id=str(row["artifact_version_id"]),
                    status=ArtifactStatus.REJECTED,
                    stale_reason=reason,
                    confirmed_at=None,
                    make_current=previous is None,
                    now=now,
                )
                if previous is not None:
                    conn.execute(
                        """
                        UPDATE artifacts
                        SET current_version_id = ?, status = ?, domain_status = ?, updated_at = ?
                        WHERE id = ? AND project_id = ?
                        """,
                        (
                            str(previous["artifact_version_id"]),
                            ArtifactStatus.APPROVED.value,
                            "confirmed",
                            now,
                            str(row["artifact_id"]),
                            project_id,
                        ),
                    )
            updated = conn.execute(
                "SELECT * FROM cad_runs WHERE id = ?",
                (cad_run_id,),
            ).fetchone()
            cad_run = self._to_run(conn, updated)
        sync_cad_message_projection(self._db_path, cad_run)
        return cad_run

    def sync_artifact(self, cad_run: CadRun, spec: SpecRun | None) -> None:
        dependencies = (
            [
                ArtifactDependency(
                    artifactId=f"artifact_spec_{spec.projectId}_project_spec",
                    versionId=spec.files[0].artifactVersionId if spec.files else None,
                    version=spec.version,
                    kind="spec",
                    label=f"工程规格 v{spec.version}",
                    status=spec.status.value,
                )
            ]
            if spec is not None
            else []
        )
        preview_file = next(
            (file for file in cad_run.files if file.role == CadOutputRole.GLB_PREVIEW),
            None,
        )
        version = ArtifactRepository(self._db_path).upsert_model_artifact(
            artifact_id=f"artifact_cad_{cad_run.projectId}",
            project_id=cad_run.projectId,
            title="结构件 CAD 模型",
            status=_artifact_status(cad_run.status),
            source_agent_id="cad-agent",
            source_entity_type="cad",
            source_entity_id=cad_run.id,
            source_version=cad_run.version,
            content=_artifact_content(cad_run),
            summary=f"{_template_label(cad_run.templateKind)} v{cad_run.version}",
            model_url=(
                f"/api/projects/{cad_run.projectId}/artifacts/"
                f"artifact_cad_{cad_run.projectId}/versions/"
                f"artifact_version_artifact_cad_{cad_run.projectId}_{cad_run.id}/files/"
                f"{preview_file.artifactFileId}"
                if preview_file and preview_file.artifactFileId
                else f"artifact://{cad_run.projectId}/cad/{cad_run.id}/model.stl"
            ),
            model_file_id=preview_file.artifactFileId if preview_file else None,
            checksum=preview_file.sha256 if preview_file else None,
            mime_type=preview_file.mimeType if preview_file else "model/stl",
            dependencies=dependencies,
            stale_reason=cad_run.staleReason,
            confirmed_at=cad_run.confirmedAt,
        )
        with self._connect() as conn:
            conn.execute(
                "UPDATE cad_runs SET artifact_id = ?, artifact_version_id = ? WHERE id = ?",
                (version.artifactId, version.id, cad_run.id),
            )
            conn.execute(
                """
                UPDATE cad_files
                SET artifact_id = ?, artifact_version_id = ?
                WHERE cad_run_id = ?
                """,
                (version.artifactId, version.id, cad_run.id),
            )

    def _insert_file(
        self,
        conn: sqlite3.Connection,
        cad_run_id: str,
        project_id: str,
        file: GeneratedCadFile,
        now: str,
    ) -> None:
        role = {
            CadFileKind.STEP: CadOutputRole.STEP_ASSEMBLY,
            CadFileKind.STL: CadOutputRole.STL_PRINTABLE_PARTS,
            CadFileKind.PARAMETERS: CadOutputRole.PARAMETERS,
        }[file.kind]
        content_bytes = file.content.encode("utf-8")
        conn.execute(
            """
            INSERT INTO cad_files (
              id, cad_run_id, project_id, kind, role, path, file_name,
              storage_key, mime_type, content, byte_size, sha256, bounds_json,
              triangle_count, artifact_file_id, artifact_id,
              artifact_version_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, ?, ?, NULL, NULL,
                      NULL, NULL, NULL, ?)
            """,
            (
                _id("cad_file"),
                cad_run_id,
                project_id,
                file.kind.value,
                role.value,
                file.path,
                file.path.replace("\\", "/").rsplit("/", 1)[-1],
                file.mime_type,
                file.content,
                len(content_bytes),
                hashlib.sha256(content_bytes).hexdigest(),
                now,
            ),
        )

    def _row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        cad_run_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM cad_runs WHERE id = ? AND project_id = ?",
            (cad_run_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("CAD 运行不存在。")
        return row

    def _to_run(self, conn: sqlite3.Connection, row: sqlite3.Row) -> CadRun:
        files = [
            CadFile(
                id=file_row["id"],
                cadRunId=file_row["cad_run_id"],
                projectId=file_row["project_id"],
                kind=CadFileKind(file_row["kind"]) if file_row["kind"] else None,
                role=CadOutputRole(file_row["role"]) if file_row["role"] else None,
                path=file_row["path"] or "",
                fileName=file_row["file_name"],
                artifactFileId=file_row["artifact_file_id"],
                storageKey=file_row["storage_key"],
                mimeType=file_row["mime_type"],
                content=file_row["content"],
                byteSize=file_row["byte_size"],
                sha256=file_row["sha256"],
                bounds=json.loads(file_row["bounds_json"])
                if file_row["bounds_json"]
                else None,
                triangleCount=file_row["triangle_count"],
                artifactId=file_row["artifact_id"],
                artifactVersionId=file_row["artifact_version_id"],
                createdAt=file_row["created_at"],
            )
            for file_row in conn.execute(
                """
                SELECT * FROM cad_files
                WHERE cad_run_id = ?
                ORDER BY CASE kind
                  WHEN 'PARAMETERS' THEN 1
                  WHEN 'STEP' THEN 2
                  WHEN 'STL' THEN 3
                  ELSE 99
                END
                """,
                (row["id"],),
            ).fetchall()
        ]
        return CadRun(
            id=row["id"],
            projectId=row["project_id"],
            specRunId=row["spec_run_id"],
            templateKind=CadTemplateKind(row["template_kind"]),
            version=row["version"],
            status=CadRunStatus(row["status"]),
            commandLabel=row["command_label"],
            parameters=[
                CadParameter(**item)
                for item in json.loads(row["parameters_json"])
            ],
            validation=CadValidation(**json.loads(row["validation_json"])),
            files=files,
            artifactId=row["artifact_id"],
            artifactVersionId=row["artifact_version_id"],
            sourceMessageId=row["source_message_id"],
            generatedByExpertId=row["generated_by_expert_id"],
            engineId=row["engine_id"],
            engineVersion=row["engine_version"],
            designState=json.loads(row["design_state_json"])
            if row["design_state_json"]
            else None,
            latestJob=(
                CadJobRepository(self._db_path).get(
                    row["project_id"],
                    row["latest_job_id"],
                )
                if row["latest_job_id"]
                else None
            ),
            staleReason=row["stale_reason"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            confirmedAt=row["confirmed_at"],
        )

    def _load_spec(self, project_id: str, spec_run_id: str) -> SpecRun:
        from zhangwen.specs.repository import SpecRepository

        return SpecRepository(self._db_path).get_spec(project_id, spec_run_id)


def _parameters_for_draft(draft: CadDraft) -> list[CadParameter]:
    definitions = template_specs()[draft.templateKind]
    allowed = {name for name, _label, _unit, _default, _minimum, _maximum in definitions}
    unknown = sorted(set(draft.parameters) - allowed)
    if unknown:
        raise ValueError(f"CAD 草稿包含模板不支持的参数：{unknown}")
    parameters: list[CadParameter] = []
    for name, label, unit, default, minimum, maximum in definitions:
        value = float(draft.parameters.get(name, default))
        if not production_parameter_spec(draft.templateKind, name).accepts(value):
            raise ValueError(f"CAD 参数 {name} 超出允许范围。")
        parameters.append(
            CadParameter(
                name=name,
                label=label,
                unit=unit,
                value=value,
                min=minimum,
                max=maximum,
            )
        )
    return parameters


def cad_artifact_id(project_id: str) -> str:
    return f"artifact_cad_{project_id}"


def cad_artifact_version_id(project_id: str, cad_run_id: str) -> str:
    artifact_id = cad_artifact_id(project_id)
    return f"artifact_version_{artifact_id}_{cad_run_id}"


def _job_id(project_id: str, client_request_id: str | None) -> str:
    if client_request_id:
        identity = hashlib.sha256(
            f"{project_id}\0{client_request_id}".encode("utf-8")
        ).hexdigest()[:32]
        return f"cadjob_{identity}"
    return _id("cadjob")


def _materialize_components_for_draft(
    db_path: Path,
    project_id: str,
    draft: CadDraft,
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    repository = MechanicalProfileRepository(db_path)
    repository.seed_builtin_profiles()
    components: list[dict[str, object]] = []
    snapshots: dict[str, dict[str, object]] = {}
    for component in draft.components:
        if not component.hardwareId or not component.profileId:
            raise ValueError(f"CAD_COMPONENT_PROFILE_MISSING: {component.instanceId}")
        try:
            if component.hardwareId.startswith(CAD_VIRTUAL_HARDWARE_PREFIX):
                snapshot = CadProfileIntake(db_path).resolve_virtual_hardware(
                    project_id=project_id,
                    hardware_id=component.hardwareId,
                    declared_profile_id=component.profileId,
                )
            else:
                snapshot = repository.resolve_for_hardware(component.hardwareId)
            declared_profile_id = canonical_profile_id(component.profileId)
        except (KeyError, ValueError) as exc:
            if str(exc) == "CAD_PROJECT_PROFILE_SELECTION_STALE":
                raise ValueError("CAD_PROJECT_PROFILE_SELECTION_STALE") from exc
            raise ValueError(f"CAD_PROFILE_SNAPSHOT_MISSING: {exc}") from exc
        if declared_profile_id != snapshot.profile_id:
            raise ValueError(f"CAD_COMPONENT_PROFILE_CONFLICT: {component.instanceId}")
        snapshots[snapshot.profile_id] = snapshot.model_dump(mode="json")
        resolved_component = component.model_dump(mode="json")
        resolved_component.update(
            {
                "resolvedProfileId": snapshot.profile_id,
                "resolvedProfileRevision": snapshot.revision,
                "resolvedProfileSha256": snapshot.content_sha256,
            }
        )
        components.append(resolved_component)
    return components, list(snapshots.values())


def _cad_validation(value: object) -> CadValidation:
    if not isinstance(value, dict) or not isinstance(value.get("checks"), list):
        raise ValueError("CAD_WORKER_VALIDATION_INVALID")
    checks: list[CadValidationCheck] = []
    for raw in value["checks"]:
        if not isinstance(raw, dict):
            raise ValueError("CAD_WORKER_VALIDATION_INVALID")
        evidence = raw.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
        checks.append(
            CadValidationCheck(
                dimension=str(raw.get("check_id") or raw.get("checkId") or "unknown"),
                severity=str(raw.get("status") or "fail").upper(),
                message=str(raw.get("message") or "CAD 校验未提供说明。"),
                details="; ".join(str(item) for item in evidence),
            )
        )
    return CadValidation(ok=value.get("ok") is True, checks=checks)


def _legacy_file_kind(role: str) -> str | None:
    return {
        CadOutputRole.STEP_ASSEMBLY.value: CadFileKind.STEP.value,
        CadOutputRole.STEP_PRINTABLE_PARTS.value: CadFileKind.STEP.value,
        CadOutputRole.STL_PRINTABLE_PARTS.value: CadFileKind.STL.value,
        CadOutputRole.PARAMETERS.value: CadFileKind.PARAMETERS.value,
    }.get(role)


def _artifact_dependencies(spec: SpecRun | None) -> list[ArtifactDependency]:
    if spec is None:
        return []
    return [
        ArtifactDependency(
            artifactId=f"artifact_spec_{spec.projectId}_project_spec",
            versionId=spec.files[0].artifactVersionId if spec.files else None,
            version=spec.version,
            kind="spec",
            label=f"工程规格 v{spec.version}",
            status=spec.status.value,
        )
    ]


def _artifact_status(status: CadRunStatus) -> ArtifactStatus:
    mapping = {
        CadRunStatus.DRAFT: ArtifactStatus.DRAFT,
        CadRunStatus.QUEUED: ArtifactStatus.GENERATING,
        CadRunStatus.RUNNING: ArtifactStatus.GENERATING,
        CadRunStatus.VALIDATED: ArtifactStatus.NEEDS_REVIEW,
        CadRunStatus.READY_FOR_REVIEW: ArtifactStatus.NEEDS_REVIEW,
        CadRunStatus.APPROVED: ArtifactStatus.APPROVED,
        CadRunStatus.REJECTED: ArtifactStatus.REJECTED,
        CadRunStatus.STALE: ArtifactStatus.STALE,
        CadRunStatus.FAILED: ArtifactStatus.FAILED,
        CadRunStatus.CANCELED: ArtifactStatus.FAILED,
    }
    return mapping[status]


def _artifact_content(cad_run: CadRun) -> str:
    chunks: list[str] = []
    for file in cad_run.files:
        chunks.append(f"# file: {file.path}")
        chunks.append((file.content or file.sha256 or "binary").rstrip())
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def _template_label(kind: CadTemplateKind) -> str:
    return {
        CadTemplateKind.COMPONENT_MOUNT: "器件安装底座与压框",
        CadTemplateKind.FREEFORM_STRUCTURE: "自然语言自定义零件",
        CadTemplateKind.UNIHIKER_K10_PHOTO_ALBUM: "行空板 K10 电子相册支架",
        CadTemplateKind.SENSOR_BRACKET: "传感器支架",
        CadTemplateKind.MCU_MOUNT: "主控板支架",
        CadTemplateKind.MOTOR_MOUNT: "电机支架",
        CadTemplateKind.SERVO_MOUNT: "舵机支架",
        CadTemplateKind.SIMPLE_ENCLOSURE: "简单外壳",
        CadTemplateKind.PANEL_CUTOUT: "面板开孔",
        CadTemplateKind.BOX_WITH_LID: "盒体与盖板",
    }[kind]


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
