"""SQLite repository for Code Agent runs."""

from __future__ import annotations

import difflib
import hashlib
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
from zhangwen.code_agent.generator import GeneratedCode, GeneratedCodeFile
from zhangwen.code_agent.models import (
    CodeFile,
    CodeFileKind,
    CodePatch,
    CodeRevisionSource,
    CodeRun,
    CodeRunStatus,
    CodeRuntime,
    CodeTestResult,
    CodeValidationCheck,
    CodeValidationKind,
    CodeValidationStatus,
    EditableCodeFile,
)
from zhangwen.code_agent.validation import (
    CURRENT_VALIDATION_KINDS,
    pending_validation_result,
    validate_storable_code_files,
)
from zhangwen.specs.models import SpecRun, SpecRunStatus


class CodeRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def get_current_code(self, project_id: str) -> CodeRun | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM code_runs
                WHERE project_id = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return self._to_run(conn, row) if row else None

    def get_code(self, project_id: str, code_run_id: str) -> CodeRun:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM code_runs WHERE id = ? AND project_id = ?",
                (code_run_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("代码草稿不存在。")
            return self._to_run(conn, row)

    def create_from_generated(
        self,
        *,
        project_id: str,
        spec: SpecRun,
        generated: GeneratedCode,
    ) -> CodeRun:
        if spec.status != SpecRunStatus.APPROVED:
            raise ValueError("只有已确认 Spec 可以生成代码。")
        if not any(file.kind.value == "IO_MAP" for file in spec.files):
            raise ValueError("生成设备代码需要已确认的 IO Map。")
        test_result = _normalized_validation_result(generated.test_result)
        now = _now()
        code_run_id = _id("code")
        generated_by_expert_id = self._open_hardware_expert_id(project_id)
        with self._connect() as conn:
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM code_runs WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = int(max_version) + 1
            conn.execute(
                """
                UPDATE code_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND runtime = ? AND status IN (?, ?)
                """,
                (
                    CodeRunStatus.ROLLED_BACK.value,
                    "代码已生成新版本。",
                    now,
                    project_id,
                    generated.runtime.value,
                    CodeRunStatus.DRAFT.value,
                    CodeRunStatus.READY_FOR_REVIEW.value,
                ),
            )
            conn.execute(
                """
                INSERT INTO code_runs (
                  id, project_id, spec_run_id, version, status, runtime,
                  entrypoint, workspace_root, max_retries, retries,
                  test_result_json, artifact_id,
                  artifact_version_id, hardware_solution_version, bom_version,
                  io_map_version, generated_by_expert_id, stale_reason,
                  created_at, updated_at, accepted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, NULL, ?, ?, NULL)
                """,
                (
                    code_run_id,
                    project_id,
                    spec.id,
                    version,
                    CodeRunStatus.READY_FOR_REVIEW.value
                    if test_result.ok
                    else CodeRunStatus.FAILED.value,
                    generated.runtime.value,
                    generated.entrypoint,
                    f"workspace://{project_id}/code/v{version}",
                    2,
                    0,
                    json.dumps(test_result.model_dump(mode="json"), ensure_ascii=False),
                    spec.version,
                    spec.version,
                    spec.version,
                    generated_by_expert_id,
                    now,
                    now,
                ),
            )
            for file in generated.files:
                self._insert_file(conn, code_run_id, project_id, file, now)
            conn.execute(
                """
                INSERT INTO code_patches (
                  id, code_run_id, project_id, base_snapshot_id, summary, diff, created_at
                ) VALUES (?, ?, ?, NULL, ?, ?, ?)
                """,
                (
                    _id("patch"),
                    code_run_id,
                    project_id,
                    generated.summary,
                    generated.diff,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            code_run = self._to_run(conn, row)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def create_from_chat_draft(
        self,
        *,
        project_id: str,
        source_message_id: str,
        generated_by_expert_id: str | None,
        generated: GeneratedCode,
        idempotency_scope: str | None = None,
        spec_run_id: str | None = None,
    ) -> CodeRun:
        """Create one immutable draft per source message and materialization contract."""

        spec = self._load_optional_spec(project_id, spec_run_id)
        if spec is not None and spec.status != SpecRunStatus.APPROVED:
            raise ValueError("正式工程聊天代码只能绑定已确认的工程规格。")
        code_run_id = _chat_code_run_id(
            project_id,
            source_message_id,
            idempotency_scope=idempotency_scope,
        )
        test_result = _normalized_validation_result(generated.test_result)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            if existing is not None:
                if str(existing["project_id"]) != project_id:
                    raise ValueError("聊天代码版本归属项目不一致。")
                if existing["spec_run_id"] != spec_run_id:
                    raise ValueError("聊天代码版本绑定的工程规格不一致。")
                if CodeRuntime(existing["runtime"]) != generated.runtime:
                    raise ValueError("聊天代码版本绑定的运行时不一致。")
                if str(existing["entrypoint"]) != generated.entrypoint:
                    raise ValueError("聊天代码版本绑定的入口文件不一致。")
                code_run = self._to_run(conn, existing)
            else:
                max_version = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) FROM code_runs WHERE project_id = ?",
                    (project_id,),
                ).fetchone()[0]
                version = int(max_version) + 1
                conn.execute(
                    """
                    UPDATE code_runs
                    SET status = ?, stale_reason = ?, updated_at = ?
                    WHERE project_id = ? AND runtime = ? AND status IN (?, ?)
                    """,
                    (
                        CodeRunStatus.ROLLED_BACK.value,
                        "聊天代码已生成新版本。",
                        now,
                        project_id,
                        generated.runtime.value,
                        CodeRunStatus.DRAFT.value,
                        CodeRunStatus.READY_FOR_REVIEW.value,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO code_runs (
                      id, project_id, spec_run_id, version, status, runtime,
                      entrypoint, workspace_root, max_retries, retries,
                      test_result_json, artifact_id,
                      artifact_version_id, hardware_solution_version, bom_version,
                      io_map_version, generated_by_expert_id, stale_reason,
                      created_at, updated_at, accepted_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, NULL, ?, ?, ?, ?, NULL)
                    """,
                    (
                        code_run_id,
                        project_id,
                        spec_run_id,
                        version,
                        CodeRunStatus.DRAFT.value,
                        generated.runtime.value,
                        generated.entrypoint,
                        f"workspace://{project_id}/code/v{version}",
                        2,
                        0,
                        json.dumps(test_result.model_dump(mode="json"), ensure_ascii=False),
                        generated_by_expert_id,
                        "聊天代码草稿需要本地验证。",
                        now,
                        now,
                    ),
                )
                for file in generated.files:
                    self._insert_file(conn, code_run_id, project_id, file, now)
                conn.execute(
                    """
                    INSERT INTO code_patches (
                      id, code_run_id, project_id, base_snapshot_id, summary, diff, created_at
                    ) VALUES (?, ?, ?, NULL, ?, ?, ?)
                    """,
                    (
                        _id("patch"),
                        code_run_id,
                        project_id,
                        generated.summary,
                        generated.diff,
                        now,
                    ),
                )
                row = conn.execute(
                    "SELECT * FROM code_runs WHERE id = ?",
                    (code_run_id,),
                ).fetchone()
                code_run = self._to_run(conn, row)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def revise_from_user(
        self,
        *,
        project_id: str,
        base_code_run_id: str,
        files: list[EditableCodeFile],
        summary: str,
    ) -> CodeRun:
        normalized_summary = summary.strip()
        if not normalized_summary:
            raise ValueError("代码变更摘要不能为空。")
        now = _now()
        code_run_id = _id("code")
        pending_message = "用户修改已保存为新版本；尚未运行本地静态或语法检查。"
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            base_row = self._row(conn, project_id, base_code_run_id)
            current_row = conn.execute(
                """
                SELECT id FROM code_runs
                WHERE project_id = ? AND runtime = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id, base_row["runtime"]),
            ).fetchone()
            if current_row is None or current_row["id"] != base_code_run_id:
                raise CodeRevisionConflictError(
                    "代码已经产生新版本，请刷新后基于最新版本修改。"
                )
            base = self._to_run(conn, base_row)
            test_result = pending_validation_result(
                now=now,
                message=pending_message,
                runtime=base.runtime,
            ).model_copy(update={"command": "not-run-user-edit"})
            next_files, diff = _validated_user_revision(base.files, files)
            validate_storable_code_files(next_files, runtime=base.runtime)
            max_version = conn.execute(
                "SELECT COALESCE(MAX(version), 0) FROM code_runs WHERE project_id = ?",
                (project_id,),
            ).fetchone()[0]
            version = int(max_version) + 1
            conn.execute(
                """
                INSERT INTO code_runs (
                  id, project_id, spec_run_id, version, status, runtime,
                  entrypoint, workspace_root, max_retries, retries,
                  test_result_json, artifact_id,
                  artifact_version_id, hardware_solution_version, bom_version,
                  io_map_version, generated_by_expert_id, stale_reason,
                  created_at, updated_at, accepted_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    code_run_id,
                    project_id,
                    base.specRunId,
                    version,
                    CodeRunStatus.DRAFT.value,
                    base.runtime.value,
                    base.entrypoint,
                    f"workspace://{project_id}/code/v{version}",
                    base.maxRetries,
                    0,
                    json.dumps(test_result.model_dump(mode="json"), ensure_ascii=False),
                    base.hardwareSolutionVersion,
                    base.bomVersion,
                    base.ioMapVersion,
                    base.generatedByExpertId,
                    "用户修改后需要重新验证。",
                    now,
                    now,
                ),
            )
            for file in next_files:
                self._insert_file(conn, code_run_id, project_id, file, now)
            conn.execute(
                """
                INSERT INTO code_patches (
                  id, code_run_id, project_id, base_snapshot_id, summary, diff, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id("patch"),
                    code_run_id,
                    project_id,
                    base.id,
                    normalized_summary,
                    diff,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            code_run = self._to_run(conn, row)
        spec = self._load_optional_spec(project_id, code_run.specRunId)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def validate_code(
        self,
        project_id: str,
        code_run_id: str,
        test_result: CodeTestResult,
    ) -> CodeRun:
        normalized_result = _normalized_validation_result(test_result)
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._row(conn, project_id, code_run_id)
            current_row = conn.execute(
                """
                SELECT id FROM code_runs
                WHERE project_id = ? AND runtime = ?
                ORDER BY version DESC
                LIMIT 1
                """,
                (project_id, row["runtime"]),
            ).fetchone()
            if current_row is None or current_row["id"] != code_run_id:
                raise CodeRevisionConflictError(
                    "代码已经产生新版本，请刷新后验证当前版本。"
                )
            if row["status"] not in {
                CodeRunStatus.DRAFT.value,
                CodeRunStatus.FAILED.value,
                CodeRunStatus.READY_FOR_REVIEW.value,
            }:
                raise ValueError("当前代码版本状态不允许重新验证。")
            next_status = (
                CodeRunStatus.READY_FOR_REVIEW
                if normalized_result.ok
                else CodeRunStatus.FAILED
            )
            runtime = CodeRuntime(row["runtime"])
            runtime_label = (
                "ESP-Claw Lua"
                if runtime == CodeRuntime.ESP_CLAW_LUA
                else "MicroPython"
            )
            stale_reason = (
                None
                if normalized_result.ok
                else f"本地 {runtime_label} 验证未通过。"
            )
            conn.execute(
                """
                UPDATE code_runs
                SET status = ?, test_result_json = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    next_status.value,
                    json.dumps(
                        normalized_result.model_dump(mode="json"),
                        ensure_ascii=False,
                    ),
                    stale_reason,
                    now,
                    code_run_id,
                ),
            )
            updated = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            code_run = self._to_run(conn, updated)
        spec = self._load_optional_spec(project_id, code_run.specRunId)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def mark_project_code_stale(self, project_id: str, reason: str) -> int:
        now = _now()
        with self._connect() as conn:
            cursor = conn.execute(
                """
                UPDATE code_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND status IN (?, ?)
                """,
                (
                    CodeRunStatus.STALE.value,
                    reason,
                    now,
                    project_id,
                    CodeRunStatus.READY_FOR_REVIEW.value,
                    CodeRunStatus.ACCEPTED.value,
                ),
            )
            rows = conn.execute(
                "SELECT * FROM code_runs WHERE project_id = ?",
                (project_id,),
            ).fetchall()
        for row in rows:
            code_run = self.get_code(project_id, row["id"])
            spec = self._load_optional_spec(project_id, code_run.specRunId)
            self.sync_artifact(code_run, spec)
        return int(cursor.rowcount)

    def accept_code(self, project_id: str, code_run_id: str) -> CodeRun:
        now = _now()
        with self._connect() as conn:
            row = self._row(conn, project_id, code_run_id)
            if row["status"] not in {
                CodeRunStatus.READY_FOR_REVIEW.value,
                CodeRunStatus.ACCEPTED.value,
            }:
                raise ValueError("只有待确认代码草稿可以接受。")
            test_result = CodeTestResult(**json.loads(row["test_result_json"]))
            if not _normalized_validation_result(test_result).ok:
                raise ValueError("代码必须先通过静态检查和语法检查才可以接受。")
            conn.execute(
                """
                UPDATE code_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE project_id = ? AND runtime = ? AND id != ?
                  AND status = ?
                """,
                (
                    CodeRunStatus.ROLLED_BACK.value,
                    "同一部署通道已确认新代码版本。",
                    now,
                    project_id,
                    row["runtime"],
                    code_run_id,
                    CodeRunStatus.ACCEPTED.value,
                ),
            )
            conn.execute(
                """
                UPDATE code_runs
                SET status = ?, accepted_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (CodeRunStatus.ACCEPTED.value, now, now, code_run_id),
            )
            conn.execute(
                """
                UPDATE creator_code_variant_bindings
                SET validation_status = 'READY_FOR_REVIEW', updated_at = ?
                WHERE project_id = ? AND runtime = ?
                  AND code_run_id != ? AND validation_status = 'ACCEPTED'
                """,
                (now, project_id, row["runtime"], code_run_id),
            )
            conn.execute(
                """
                UPDATE creator_code_variant_bindings
                SET validation_status = 'ACCEPTED', failure_code = NULL,
                    failure_message = NULL, updated_at = ?
                WHERE project_id = ? AND code_run_id = ?
                """,
                (now, project_id, code_run_id),
            )
            updated = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            code_run = self._to_run(conn, updated)
        spec = self._load_optional_spec(project_id, code_run.specRunId)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def reject_code(
        self,
        project_id: str,
        code_run_id: str,
        reason: str | None,
    ) -> CodeRun:
        now = _now()
        with self._connect() as conn:
            self._row(conn, project_id, code_run_id)
            conn.execute(
                """
                UPDATE code_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (CodeRunStatus.REJECTED.value, reason, now, code_run_id),
            )
            updated = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            code_run = self._to_run(conn, updated)
        spec = self._load_optional_spec(project_id, code_run.specRunId)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def rollback_code(self, project_id: str, code_run_id: str) -> CodeRun:
        now = _now()
        with self._connect() as conn:
            self._row(conn, project_id, code_run_id)
            conn.execute(
                """
                UPDATE code_runs
                SET status = ?, stale_reason = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    CodeRunStatus.ROLLED_BACK.value,
                    "代码草稿已回滚，未写入项目工作区。",
                    now,
                    code_run_id,
                ),
            )
            updated = conn.execute(
                "SELECT * FROM code_runs WHERE id = ?",
                (code_run_id,),
            ).fetchone()
            code_run = self._to_run(conn, updated)
        spec = self._load_optional_spec(project_id, code_run.specRunId)
        self.sync_artifact(code_run, spec)
        return self.get_code(project_id, code_run_id)

    def sync_artifact(self, code_run: CodeRun, spec: SpecRun | None) -> None:
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
        status = _artifact_status(code_run.status)
        is_lua = code_run.runtime == CodeRuntime.ESP_CLAW_LUA
        artifact_title = "ESP-Claw Lua 工程代码" if is_lua else "MicroPython 工程代码"
        version = ArtifactRepository(self._db_path).upsert_text_artifact(
            artifact_id=(
                f"artifact_code_{code_run.projectId}_espclaw"
                if is_lua
                else f"artifact_code_{code_run.projectId}"
            ),
            project_id=code_run.projectId,
            title=artifact_title,
            kind=ArtifactKind.CODE,
            status=status,
            source_agent_id="code-agent",
            source_entity_type="code",
            source_entity_id=code_run.id,
            source_version=code_run.version,
            content=_artifact_content(code_run),
            summary=(
                f"用户修改：{code_run.patch.summary}"
                if code_run.revisionSource == CodeRevisionSource.USER
                else f"{artifact_title} v{code_run.version}"
            ),
            mime_type="text/x-lua" if is_lua else "text/x-python",
            language="lua" if is_lua else "python",
            dependencies=dependencies,
            stale_reason=code_run.staleReason,
            confirmed_at=code_run.acceptedAt,
        )
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE code_runs
                SET artifact_id = ?, artifact_version_id = ?
                WHERE id = ?
                """,
                (version.artifactId, version.id, code_run.id),
            )

    def _insert_file(
        self,
        conn: sqlite3.Connection,
        code_run_id: str,
        project_id: str,
        file: GeneratedCodeFile,
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO code_files (
              id, code_run_id, project_id, kind, path, language, content, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _id("code_file"),
                code_run_id,
                project_id,
                file.kind.value,
                file.path,
                file.language,
                file.content,
                now,
            ),
        )

    def _row(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        code_run_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM code_runs WHERE id = ? AND project_id = ?",
            (code_run_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("代码草稿不存在。")
        return row

    def _to_run(self, conn: sqlite3.Connection, row: sqlite3.Row) -> CodeRun:
        file_rows = conn.execute(
            """
            SELECT * FROM code_files
            WHERE code_run_id = ?
            ORDER BY path
            """,
            (row["id"],),
        ).fetchall()
        patch_row = conn.execute(
            "SELECT * FROM code_patches WHERE code_run_id = ?",
            (row["id"],),
        ).fetchone()
        if patch_row is None:
            raise ValueError("代码补丁不存在。")
        return CodeRun(
            id=row["id"],
            projectId=row["project_id"],
            specRunId=row["spec_run_id"],
            version=row["version"],
            status=CodeRunStatus(row["status"]),
            runtime=CodeRuntime(row["runtime"]),
            entrypoint=str(row["entrypoint"]),
            workspaceRoot=row["workspace_root"],
            maxRetries=row["max_retries"],
            retries=row["retries"],
            files=[
                CodeFile(
                    id=file_row["id"],
                    codeRunId=file_row["code_run_id"],
                    projectId=file_row["project_id"],
                    kind=CodeFileKind(file_row["kind"]),
                    path=file_row["path"],
                    language=file_row["language"],
                    content=file_row["content"],
                    createdAt=file_row["created_at"],
                )
                for file_row in file_rows
            ],
            patch=CodePatch(
                id=patch_row["id"],
                codeRunId=patch_row["code_run_id"],
                projectId=patch_row["project_id"],
                baseSnapshotId=patch_row["base_snapshot_id"],
                summary=patch_row["summary"],
                diff=patch_row["diff"],
                createdAt=patch_row["created_at"],
            ),
            testResult=CodeTestResult(**json.loads(row["test_result_json"])),
            artifactId=row["artifact_id"],
            artifactVersionId=row["artifact_version_id"],
            hardwareSolutionVersion=row["hardware_solution_version"],
            bomVersion=row["bom_version"],
            ioMapVersion=row["io_map_version"],
            generatedByExpertId=row["generated_by_expert_id"],
            staleReason=row["stale_reason"],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            acceptedAt=row["accepted_at"],
            revisionSource=(
                CodeRevisionSource.USER
                if patch_row["base_snapshot_id"]
                else CodeRevisionSource.MODEL
            ),
            requiresValidation=(
                row["status"] == CodeRunStatus.DRAFT.value
                and not CodeTestResult(**json.loads(row["test_result_json"])).ok
            ),
        )

    def _load_optional_spec(
        self,
        project_id: str,
        spec_run_id: str | None,
    ) -> SpecRun | None:
        if spec_run_id is None:
            return None
        from zhangwen.specs.repository import SpecRepository

        return SpecRepository(self._db_path).get_spec(project_id, spec_run_id)

    def _open_hardware_expert_id(self, project_id: str) -> str | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT id FROM project_experts
                WHERE project_id = ?
                  AND expert_type IN (
                    'smart_engineer',
                    'intelligent_engineer',
                    'open_hardware_designer'
                  )
                  AND removed_at IS NULL
                  AND archived_legacy_thread = 0
                ORDER BY CASE expert_type
                  WHEN 'smart_engineer' THEN 1
                  WHEN 'intelligent_engineer' THEN 2
                  WHEN 'open_hardware_designer' THEN 3
                  ELSE 99
                END, added_at ASC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return str(row["id"]) if row else None


def _artifact_status(status: CodeRunStatus) -> ArtifactStatus:
    mapping = {
        CodeRunStatus.DRAFT: ArtifactStatus.DRAFT,
        CodeRunStatus.TESTING: ArtifactStatus.GENERATING,
        CodeRunStatus.READY_FOR_REVIEW: ArtifactStatus.NEEDS_REVIEW,
        CodeRunStatus.ACCEPTED: ArtifactStatus.APPROVED,
        CodeRunStatus.STALE: ArtifactStatus.STALE,
        CodeRunStatus.REJECTED: ArtifactStatus.REJECTED,
        CodeRunStatus.ROLLED_BACK: ArtifactStatus.STALE,
        CodeRunStatus.FAILED: ArtifactStatus.FAILED,
    }
    return mapping[status]


def _artifact_content(code_run: CodeRun) -> str:
    chunks: list[str] = []
    comment = "--" if code_run.runtime == CodeRuntime.ESP_CLAW_LUA else "#"
    for file in code_run.files:
        chunks.append(f"{comment} file: {file.path}")
        chunks.append(file.content.rstrip())
        chunks.append("")
    chunks.append(f"{comment} patch")
    chunks.append(code_run.patch.diff.rstrip())
    return "\n".join(chunks).rstrip() + "\n"


def _normalized_validation_result(test_result: CodeTestResult) -> CodeTestResult:
    checks_by_kind: dict[CodeValidationKind, CodeValidationCheck] = {}
    for check in test_result.checks:
        if check.kind not in CURRENT_VALIDATION_KINDS:
            continue
        if check.kind in checks_by_kind:
            raise ValueError("代码验证结果包含重复检查项。")
        checks_by_kind[check.kind] = check
    normalized_checks: list[CodeValidationCheck] = []
    for kind in CURRENT_VALIDATION_KINDS:
        check = checks_by_kind.get(kind)
        if check is None:
            raise ValueError("代码验证结果缺少必需检查项。")
        status = (
            CodeValidationStatus.NOT_RUN
            if check.exitCode is None
            else CodeValidationStatus.PASSED
            if check.exitCode == 0
            else CodeValidationStatus.FAILED
        )
        normalized_checks.append(check.model_copy(update={"status": status}))
    ok = all(check.exitCode == 0 for check in normalized_checks)
    return test_result.model_copy(update={"ok": ok, "checks": normalized_checks})


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _chat_code_run_id(
    project_id: str,
    source_message_id: str,
    *,
    idempotency_scope: str | None = None,
) -> str:
    source_key = (
        source_message_id
        if idempotency_scope is None
        else f"{source_message_id}\x1f{idempotency_scope}"
    )
    digest = hashlib.sha256(
        f"{project_id}:{source_key}".encode("utf-8")
    ).hexdigest()[:32]
    return f"code_chat_{digest}"


class CodeRevisionConflictError(ValueError):
    pass


def _validated_user_revision(
    base_files: list[CodeFile],
    requested_files: list[EditableCodeFile],
) -> tuple[list[GeneratedCodeFile], str]:
    paths = [file.path for file in requested_files]
    if len(paths) != len(set(paths)):
        raise ValueError("代码文件路径不能重复。")
    base_by_path = {file.path: file for file in base_files}
    if set(paths) != set(base_by_path):
        raise ValueError("只能修改当前代码版本中已有的文件。")
    requested_by_path = {file.path: file for file in requested_files}
    result: list[GeneratedCodeFile] = []
    diff_chunks: list[str] = []
    for path in sorted(base_by_path):
        base = base_by_path[path]
        content = requested_by_path[path].content
        if "\x00" in content:
            raise ValueError("代码文件不能包含 NUL 字符。")
        result.append(
            GeneratedCodeFile(
                kind=base.kind,
                path=base.path,
                language=base.language,
                content=content,
            )
        )
        if content != base.content:
            diff_chunks.extend(
                difflib.unified_diff(
                    base.content.splitlines(),
                    content.splitlines(),
                    fromfile=f"a/{path}",
                    tofile=f"b/{path}",
                    lineterm="",
                )
            )
            diff_chunks.append("")
    if not diff_chunks:
        raise ValueError("代码内容没有变化。")
    return result, "\n".join(diff_chunks).rstrip() + "\n"
