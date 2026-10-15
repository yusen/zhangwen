"""SQLite/CAS repository for the canonical capability package platform."""

from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from zhangwen.auth.context import current_owner_subject
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.packages.adapters import LegacyPackageSnapshot, legacy_package_snapshots
from zhangwen.domains.packages.models import (
    CapabilityPackage,
    PackageConflictError,
    PackageDetailResponse,
    PackageInputSnapshot,
    PackageKind,
    PackageNotFoundError,
    PackageRevision,
    PackageRevisionStatus,
    PackageShadowResult,
    PackageValidationSummary,
    PackageWorkspace,
    PackageWorkspaceFile,
    PackageWorkspaceNotFoundError,
    PackageWorkspaceStatus,
    ShadowStatus,
    ValidationStatus,
)
from zhangwen.domains.packages.validation import (
    content_digest,
    normalize_package_path,
    validate_package_files,
)
from zhangwen.projects.repository import ProjectRepository


_SYSTEM_OWNER = "__system__"
_LOCAL_OWNER = "__local__"
_NOT_RUN = PackageValidationSummary().model_dump(mode="json", by_alias=True)
_PUBLISHED_SWAP_ATTEMPTS = 7
_PUBLISHED_SWAP_INITIAL_DELAY_SECONDS = 0.01


class PackagePlatformRepository:
    def __init__(
        self,
        data_dir: Path,
        *,
        owner_subject: str | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._db_path = ProjectRepository(self._data_dir).db_path
        subject = owner_subject if owner_subject is not None else current_owner_subject()
        self._owner_subject = subject
        self._owner_key = subject or _LOCAL_OWNER
        self._events = RealtimeEventStore(self._db_path)

    @property
    def db_path(self) -> Path:
        return self._db_path

    def ensure_legacy_packages(self) -> None:
        snapshots = legacy_package_snapshots(self._data_dir, self._db_path)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for snapshot in snapshots:
                self._upsert_legacy_snapshot(conn, snapshot)

    def list_packages(self, kind: PackageKind | None = None) -> list[CapabilityPackage]:
        self.ensure_legacy_packages()
        with self._connect() as conn:
            sql = """
                SELECT * FROM capability_packages
                WHERE owner_key IN (?, ?)
            """
            params: list[object] = [_SYSTEM_OWNER, self._owner_key]
            if kind is not None:
                sql += " AND kind = ?"
                params.append(kind.value)
            sql += " ORDER BY kind, display_name, id"
            rows = conn.execute(sql, params).fetchall()
        return [_package_from_row(row) for row in rows]

    def get_package(self, package_id: str) -> CapabilityPackage:
        self.ensure_legacy_packages()
        with self._connect() as conn:
            return _package_from_row(self._package_row(conn, package_id))

    def get_detail(self, package_id: str) -> PackageDetailResponse:
        self.ensure_legacy_packages()
        with self._connect() as conn:
            package_row = self._package_row(conn, package_id)
            revision_rows = conn.execute(
                "SELECT * FROM package_revisions WHERE package_id = ? ORDER BY revision DESC",
                (package_id,),
            ).fetchall()
        return PackageDetailResponse(
            package=_package_from_row(package_row),
            revisions=[_revision_from_row(row) for row in revision_rows],
        )

    def get_revision(self, revision_id: str) -> PackageRevision:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.* FROM package_revisions r
                JOIN capability_packages p ON p.id = r.package_id
                WHERE r.id = ? AND p.owner_key IN (?, ?)
                """,
                (revision_id, _SYSTEM_OWNER, self._owner_key),
            ).fetchone()
        if row is None:
            raise PackageNotFoundError("能力包修订不存在。")
        return _revision_from_row(row)

    def get_revision_files(self, revision_id: str) -> dict[str, str]:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT r.files_json FROM package_revisions r
                JOIN capability_packages p ON p.id = r.package_id
                WHERE r.id = ? AND p.owner_key IN (?, ?)
                """,
                (revision_id, _SYSTEM_OWNER, self._owner_key),
            ).fetchone()
        if row is None:
            raise PackageNotFoundError("能力包修订不存在。")
        loaded = json.loads(str(row["files_json"]))
        return {str(path): str(content) for path, content in loaded.items()}

    def stable_revision(self, package_id: str) -> PackageRevision:
        package = self.get_package(package_id)
        if package.stable_revision_id is None:
            raise PackageNotFoundError("能力包尚无稳定修订。")
        return self.get_revision(package.stable_revision_id)

    def create_workspace(
        self,
        *,
        package_id: str | None,
        kind: PackageKind | None = None,
        slug: str | None = None,
        display_name: str | None = None,
    ) -> PackageWorkspace:
        self.ensure_legacy_packages()
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if package_id is None:
                assert kind is not None and slug is not None and display_name is not None
                package_id = _id("package")
                conn.execute(
                    """
                    INSERT INTO capability_packages (
                      id, kind, slug, display_name, owner_subject, owner_key,
                      source_type, source_key, managed_by, stable_revision_id,
                      draft_revision_id, revision, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, 'UNIFIED', NULL, NULL, 1, ?, ?)
                    """,
                    (
                        package_id,
                        kind.value,
                        slug,
                        display_name,
                        self._owner_subject,
                        self._owner_key,
                        now,
                        now,
                    ),
                )
                files = _new_package_files(package_id, kind, display_name)
                base_revision_id = None
            else:
                package_row = self._package_row(conn, package_id)
                existing = conn.execute(
                    "SELECT id FROM package_workspaces WHERE package_id = ? AND owner_key = ?",
                    (package_id, self._owner_key),
                ).fetchone()
                if existing is not None:
                    return self._workspace(conn, str(existing["id"]))
                base_revision_id = (
                    str(package_row["stable_revision_id"])
                    if package_row["stable_revision_id"] is not None
                    else None
                )
                files = (
                    self._revision_files_conn(conn, base_revision_id)
                    if base_revision_id is not None
                    else _new_package_files(
                        package_id,
                        PackageKind(str(package_row["kind"])),
                        str(package_row["display_name"]),
                    )
                )
            workspace_id = _id("package_workspace")
            conn.execute(
                """
                INSERT INTO package_workspaces (
                  id, package_id, owner_subject, owner_key, base_revision_id,
                  draft_revision_id, revision, status, validation_summary_json,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, NULL, 1, 'DRAFT', ?, ?, ?)
                """,
                (
                    workspace_id,
                    package_id,
                    self._owner_subject,
                    self._owner_key,
                    base_revision_id,
                    _dump(_NOT_RUN),
                    now,
                    now,
                ),
            )
            self._replace_workspace_file_rows(conn, workspace_id, files, now)
        self._materialize_workspace(workspace_id, files)
        return self.get_workspace(workspace_id)

    def get_workspace(self, workspace_id: str) -> PackageWorkspace:
        with self._connect() as conn:
            return self._workspace(conn, workspace_id)

    def workspace_path(self, workspace_id: str) -> Path:
        self.get_workspace(workspace_id)
        return self._workspace_root(workspace_id) / "current"

    def workspace_owner_subject(self, workspace_id: str) -> str | None:
        """Return the owning subject for the trusted local file watcher."""

        with self._connect() as conn:
            row = conn.execute(
                "SELECT owner_subject FROM package_workspaces WHERE id = ?",
                (workspace_id,),
            ).fetchone()
        if row is None:
            raise PackageWorkspaceNotFoundError("能力包工作区不存在。")
        return str(row["owner_subject"]) if row["owner_subject"] is not None else None

    def save_files(
        self,
        workspace_id: str,
        *,
        expected_revision: int,
        updates: list[tuple[str, str, int]],
        event_reason: str = "API_SAVE",
    ) -> PackageWorkspace:
        now = _now()
        swap: _WorkspaceSwap | None = None
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            workspace_row = self._workspace_row(conn, workspace_id)
            if int(workspace_row["revision"]) != expected_revision:
                raise PackageConflictError("能力包草稿已被其他编辑更新，请刷新后重试。")
            package_row = self._package_row(conn, str(workspace_row["package_id"]))
            current_rows = conn.execute(
                "SELECT * FROM package_workspace_files WHERE workspace_id = ?",
                (workspace_id,),
            ).fetchall()
            current = {str(row["path"]): str(row["content"]) for row in current_rows}
            file_revisions = {str(row["path"]): int(row["revision"]) for row in current_rows}
            normalized_updates: dict[str, tuple[str, int]] = {}
            for raw_path, content, expected_file_revision in updates:
                try:
                    path = normalize_package_path(raw_path)
                except ValueError as exc:
                    raise PackageConflictError("能力包文件路径无效。") from exc
                if path in normalized_updates:
                    raise PackageConflictError("同一批保存不能重复更新同一路径。")
                actual_revision = file_revisions.get(path, 0)
                if actual_revision != expected_file_revision:
                    raise PackageConflictError(f"文件 {path} 已被其他编辑更新。")
                normalized_updates[path] = (content, actual_revision)
            next_files = dict(current)
            for path, (content, _) in normalized_updates.items():
                next_files[path] = content
            if next_files == current:
                return self._workspace(conn, workspace_id)

            swap = self._stage_and_swap_workspace(workspace_id, next_files)
            try:
                digest = content_digest(next_files)
                revision_number = self._next_revision_number(conn, str(package_row["id"]))
                revision_id = _id("package_revision")
                manifest = _manifest_json(next_files)
                conn.execute(
                    """
                    INSERT INTO package_revisions (
                      id, package_id, revision, status, manifest_json, files_json,
                      manifest_artifact_id, content_digest, schema_version,
                      validation_summary_json, shadow_status, created_at,
                      published_at, supersedes_revision_id
                    ) VALUES (?, ?, ?, 'DRAFT', ?, ?, ?, ?, 1, ?, 'NOT_RUN', ?, NULL, ?)
                    """,
                    (
                        revision_id,
                        str(package_row["id"]),
                        revision_number,
                        _dump(manifest),
                        _dump(next_files),
                        f"package-manifest:{digest}",
                        digest,
                        _dump(_NOT_RUN),
                        now,
                        workspace_row["base_revision_id"],
                    ),
                )
                conn.execute(
                    """
                    UPDATE capability_packages
                    SET draft_revision_id = ?, managed_by = 'UNIFIED',
                        revision = revision + 1, updated_at = ?
                    WHERE id = ?
                    """,
                    (revision_id, now, str(package_row["id"])),
                )
                conn.execute(
                    """
                    UPDATE package_workspaces
                    SET draft_revision_id = ?, revision = revision + 1,
                        status = 'DRAFT', validation_summary_json = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (revision_id, _dump(_NOT_RUN), now, workspace_id),
                )
                for path, (content, previous_revision) in normalized_updates.items():
                    conn.execute(
                        """
                        INSERT INTO package_workspace_files (
                          workspace_id, path, content, content_digest, revision, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?)
                        ON CONFLICT(workspace_id, path) DO UPDATE SET
                          content = excluded.content,
                          content_digest = excluded.content_digest,
                          revision = excluded.revision,
                          updated_at = excluded.updated_at
                        """,
                        (
                            workspace_id,
                            path,
                            content,
                            _text_digest(content),
                            previous_revision + 1,
                            now,
                        ),
                    )
                event_revision = int(package_row["revision"]) + 1
                self._events.append_package_event(
                    conn,
                    package_id=str(package_row["id"]),
                    package_revision=event_revision,
                    event_type="package.draft.saved",
                    source_event_id=f"{revision_id}:saved",
                    payload={
                        "workspaceId": workspace_id,
                        "packageRevisionId": revision_id,
                        "reason": event_reason,
                    },
                )
                conn.commit()
            except BaseException:
                conn.rollback()
                swap.rollback()
                raise
        assert swap is not None
        swap.commit()
        return self.get_workspace(workspace_id)

    def record_validation(
        self,
        workspace_id: str,
        *,
        draft_revision_id: str,
        summary: PackageValidationSummary,
    ) -> PackageWorkspace:
        now = _now()
        passed = summary.status == ValidationStatus.PASSED
        revision_status = PackageRevisionStatus.VALID if passed else PackageRevisionStatus.INVALID
        workspace_status = PackageWorkspaceStatus.VALID if passed else PackageWorkspaceStatus.INVALID
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            workspace_row = self._workspace_row(conn, workspace_id)
            if str(workspace_row["draft_revision_id"] or "") != draft_revision_id:
                raise PackageConflictError("校验期间草稿已发生变化，请重新校验。")
            package_row = self._package_row(conn, str(workspace_row["package_id"]))
            validation_id = _id("package_validation")
            conn.execute(
                """
                UPDATE package_revisions
                SET status = ?, validation_summary_json = ?
                WHERE id = ? AND package_id = ?
                """,
                (
                    revision_status.value,
                    _dump(summary.model_dump(mode="json", by_alias=True)),
                    draft_revision_id,
                    str(package_row["id"]),
                ),
            )
            conn.execute(
                """
                INSERT INTO package_validation_runs (
                  id, workspace_id, package_revision_id, status, issues_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    validation_id,
                    workspace_id,
                    draft_revision_id,
                    "PASSED" if passed else "FAILED",
                    _dump([item.model_dump(mode="json", by_alias=True) for item in summary.issues]),
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE package_workspaces
                SET status = ?, validation_summary_json = ?,
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (
                    workspace_status.value,
                    _dump(summary.model_dump(mode="json", by_alias=True)),
                    now,
                    workspace_id,
                ),
            )
            conn.execute(
                "UPDATE capability_packages SET revision = revision + 1, updated_at = ? WHERE id = ?",
                (now, str(package_row["id"])),
            )
            self._events.append_package_event(
                conn,
                package_id=str(package_row["id"]),
                package_revision=int(package_row["revision"]) + 1,
                event_type="package.validation.completed",
                source_event_id=f"{validation_id}:completed",
                payload={
                    "workspaceId": workspace_id,
                    "packageRevisionId": draft_revision_id,
                    "status": summary.status.value,
                    "issueCount": len(summary.issues),
                },
            )
        return self.get_workspace(workspace_id)

    def list_input_snapshots(self, package_id: str) -> list[PackageInputSnapshot]:
        self.get_package(package_id)
        with self._connect() as conn:
            if self._owner_subject is None:
                rows = conn.execute(
                    """
                    SELECT s.* FROM package_input_snapshots s
                    JOIN projects p ON p.id = s.work_id
                    ORDER BY s.created_at DESC LIMIT 50
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT s.* FROM package_input_snapshots s
                    JOIN projects p ON p.id = s.work_id
                    WHERE p.owner_subject = ?
                    ORDER BY s.created_at DESC LIMIT 50
                    """,
                    (self._owner_subject,),
                ).fetchall()
        snapshots = [_input_snapshot_from_row(row) for row in rows]
        return [
            snapshot
            for snapshot in snapshots
            if any(
                binding.get("packageId") == package_id
                for binding in snapshot.execution_revision_set.get("bindings", [])
                if isinstance(binding, dict)
            )
        ]

    def get_input_snapshot(
        self,
        turn_id: str,
        *,
        package_id: str | None = None,
    ) -> PackageInputSnapshot:
        with self._connect() as conn:
            if self._owner_subject is None:
                row = conn.execute(
                    "SELECT * FROM package_input_snapshots WHERE source_turn_id = ?",
                    (turn_id,),
                ).fetchone()
            else:
                row = conn.execute(
                    """
                    SELECT s.* FROM package_input_snapshots s
                    JOIN projects p ON p.id = s.work_id
                    WHERE s.source_turn_id = ? AND p.owner_subject = ?
                    """,
                    (turn_id, self._owner_subject),
                ).fetchone()
        if row is None:
            raise PackageNotFoundError("历史 Turn 没有可回放的脱敏输入快照。")
        snapshot = _input_snapshot_from_row(row)
        if package_id is not None and not any(
            binding.get("packageId") == package_id
            for binding in snapshot.execution_revision_set.get("bindings", [])
            if isinstance(binding, dict)
        ):
            raise PackageNotFoundError("该历史 Turn 未固定当前能力包，不能用于回放。")
        return snapshot

    def record_replay(
        self,
        workspace_id: str,
        *,
        revision_id: str,
        input_snapshot: PackageInputSnapshot,
        output: dict[str, object],
        tool_plan: list[dict[str, object]],
        diagnostics: dict[str, object],
    ) -> str:
        replay_id = _id("package_replay")
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            workspace_row = self._workspace_row(conn, workspace_id)
            package_row = self._package_row(conn, str(workspace_row["package_id"]))
            conn.execute(
                """
                INSERT INTO package_replay_runs (
                  id, workspace_id, package_id, package_revision_id,
                  input_snapshot_id, output_json, tool_plan_json,
                  diagnostics_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    replay_id,
                    workspace_id,
                    str(package_row["id"]),
                    revision_id,
                    input_snapshot.id,
                    _dump(output),
                    _dump(tool_plan),
                    _dump(diagnostics),
                    now,
                ),
            )
            conn.execute(
                "UPDATE capability_packages SET revision = revision + 1, updated_at = ? WHERE id = ?",
                (now, str(package_row["id"])),
            )
            self._events.append_package_event(
                conn,
                package_id=str(package_row["id"]),
                package_revision=int(package_row["revision"]) + 1,
                event_type="package.replay.completed",
                source_event_id=f"{replay_id}:completed",
                payload={"workspaceId": workspace_id, "packageRevisionId": revision_id},
            )
        return replay_id

    def record_shadow(
        self,
        workspace_id: str,
        *,
        input_snapshot: PackageInputSnapshot,
        baseline_revision_id: str,
        candidate_revision_id: str,
        baseline_output: dict[str, object],
        candidate_output: dict[str, object],
        output_diff: list[str],
        tool_plan_diff: list[str],
        diagnostics: dict[str, object],
        passed: bool,
    ) -> str:
        shadow_id = _id("package_shadow")
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            workspace_row = self._workspace_row(conn, workspace_id)
            if str(workspace_row["draft_revision_id"] or "") != candidate_revision_id:
                raise PackageConflictError("影子运行期间草稿已发生变化。")
            package_row = self._package_row(conn, str(workspace_row["package_id"]))
            conn.execute(
                """
                INSERT INTO package_shadow_runs (
                  id, workspace_id, package_id, baseline_revision_id,
                  candidate_revision_id, input_snapshot_id,
                  baseline_output_json, candidate_output_json,
                  output_diff_json, tool_plan_diff_json, diagnostics_json,
                  status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    shadow_id,
                    workspace_id,
                    str(package_row["id"]),
                    baseline_revision_id,
                    candidate_revision_id,
                    input_snapshot.id,
                    _dump(baseline_output),
                    _dump(candidate_output),
                    _dump(output_diff),
                    _dump(tool_plan_diff),
                    _dump(diagnostics),
                    "PASSED" if passed else "FAILED",
                    now,
                ),
            )
            conn.execute(
                "UPDATE package_revisions SET shadow_status = ? WHERE id = ?",
                ("PASSED" if passed else "FAILED", candidate_revision_id),
            )
            conn.execute(
                "UPDATE package_workspaces SET revision = revision + 1, updated_at = ? WHERE id = ?",
                (now, workspace_id),
            )
            conn.execute(
                "UPDATE capability_packages SET revision = revision + 1, updated_at = ? WHERE id = ?",
                (now, str(package_row["id"])),
            )
            self._events.append_package_event(
                conn,
                package_id=str(package_row["id"]),
                package_revision=int(package_row["revision"]) + 1,
                event_type="package.shadow.completed",
                source_event_id=f"{shadow_id}:completed",
                payload={
                    "workspaceId": workspace_id,
                    "candidateRevisionId": candidate_revision_id,
                    "status": "PASSED" if passed else "FAILED",
                },
            )
        return shadow_id

    def publish_workspace(
        self,
        workspace_id: str,
        *,
        expected_revision: int,
        confirmed: bool,
    ) -> tuple[CapabilityPackage, PackageRevision]:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            workspace_row = self._workspace_row(conn, workspace_id)
            if int(workspace_row["revision"]) != expected_revision:
                raise PackageConflictError("发布前草稿已变化，请刷新。")
            draft_id = str(workspace_row["draft_revision_id"] or "")
            if not draft_id:
                raise PackageConflictError("没有可发布的草稿修订。")
            package_row = self._package_row(conn, str(workspace_row["package_id"]))
            revision_row = conn.execute(
                "SELECT * FROM package_revisions WHERE id = ? AND package_id = ?",
                (draft_id, str(package_row["id"])),
            ).fetchone()
            if revision_row is None or str(revision_row["status"]) != PackageRevisionStatus.VALID.value:
                from zhangwen.domains.packages.models import PackageValidationError

                raise PackageValidationError("发布前必须通过当前草稿的完整校验。")
            if str(revision_row["shadow_status"]) != ShadowStatus.PASSED.value:
                from zhangwen.domains.packages.models import PackageShadowRequiredError

                raise PackageShadowRequiredError("发布前必须完成当前草稿的无副作用影子运行。")
            manifest = json.loads(str(revision_row["manifest_json"]))
            if _manifest_requires_confirmation(manifest) and not confirmed:
                from zhangwen.domains.packages.models import PackageConfirmationRequiredError

                raise PackageConfirmationRequiredError("该能力包声明高风险宿主能力，发布需要显式确认。")
            previous_stable = (
                str(package_row["stable_revision_id"])
                if package_row["stable_revision_id"] is not None
                else None
            )
            files = self._revision_files_conn(conn, draft_id)
            self._materialize_published(
                PackageKind(str(package_row["kind"])),
                str(package_row["id"]),
                draft_id,
                files,
            )
            conn.execute(
                """
                UPDATE package_revisions
                SET status = 'PUBLISHED', published_at = ?, supersedes_revision_id = ?
                WHERE id = ?
                """,
                (now, previous_stable, draft_id),
            )
            conn.execute(
                """
                UPDATE capability_packages
                SET stable_revision_id = ?, draft_revision_id = NULL,
                    managed_by = 'UNIFIED', revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (draft_id, now, str(package_row["id"])),
            )
            conn.execute(
                """
                UPDATE package_workspaces
                SET base_revision_id = ?, draft_revision_id = NULL,
                    status = 'PUBLISHED', revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (draft_id, now, workspace_id),
            )
            self._events.append_package_event(
                conn,
                package_id=str(package_row["id"]),
                package_revision=int(package_row["revision"]) + 1,
                event_type="package.published",
                source_event_id=f"{draft_id}:published",
                payload={"packageRevisionId": draft_id, "previousRevisionId": previous_stable},
            )
        return self.get_package(str(package_row["id"])), self.get_revision(draft_id)

    def rollback(
        self,
        package_id: str,
        *,
        target_revision_id: str,
        expected_revision: int,
        confirmed: bool,
    ) -> tuple[CapabilityPackage, PackageRevision]:
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            package_row = self._package_row(conn, package_id)
            if int(package_row["revision"]) != expected_revision:
                raise PackageConflictError("能力包稳定指针已变化，请刷新。")
            target_row = conn.execute(
                "SELECT * FROM package_revisions WHERE id = ? AND package_id = ?",
                (target_revision_id, package_id),
            ).fetchone()
            if target_row is None or str(target_row["status"]) != PackageRevisionStatus.PUBLISHED.value:
                raise PackageConflictError("只能回滚到同一能力包的已发布修订。")
            manifest = json.loads(str(target_row["manifest_json"]))
            if _manifest_requires_confirmation(manifest) and not confirmed:
                from zhangwen.domains.packages.models import PackageConfirmationRequiredError

                raise PackageConfirmationRequiredError("该能力包声明高风险宿主能力，回滚需要显式确认。")
            previous = str(package_row["stable_revision_id"] or "") or None
            conn.execute(
                """
                UPDATE capability_packages
                SET stable_revision_id = ?, managed_by = 'UNIFIED',
                    revision = revision + 1, updated_at = ?
                WHERE id = ?
                """,
                (target_revision_id, now, package_id),
            )
            event_id = _id("package_rollback")
            self._events.append_package_event(
                conn,
                package_id=package_id,
                package_revision=int(package_row["revision"]) + 1,
                event_type="package.rolled-back",
                source_event_id=f"{event_id}:completed",
                payload={"targetRevisionId": target_revision_id, "previousRevisionId": previous},
            )
        return self.get_package(package_id), self.get_revision(target_revision_id)

    def _upsert_legacy_snapshot(
        self,
        conn: sqlite3.Connection,
        snapshot: LegacyPackageSnapshot,
    ) -> None:
        now = _now()
        row = conn.execute(
            "SELECT * FROM capability_packages WHERE source_type = ? AND source_key = ?",
            (snapshot.source_type, snapshot.source_key),
        ).fetchone()
        if row is None:
            conn.execute(
                """
                INSERT INTO capability_packages (
                  id, kind, slug, display_name, owner_subject, owner_key,
                  source_type, source_key, managed_by, stable_revision_id,
                  draft_revision_id, revision, created_at, updated_at
                ) VALUES (?, ?, ?, ?, NULL, ?, ?, ?, 'LEGACY_ADAPTER', NULL, NULL, 1, ?, ?)
                """,
                (
                    snapshot.package_id,
                    snapshot.kind.value,
                    snapshot.slug,
                    snapshot.display_name,
                    _SYSTEM_OWNER,
                    snapshot.source_type,
                    snapshot.source_key,
                    now,
                    now,
                ),
            )
            row = conn.execute(
                "SELECT * FROM capability_packages WHERE id = ?",
                (snapshot.package_id,),
            ).fetchone()
            assert row is not None
        if str(row["managed_by"]) != "LEGACY_ADAPTER":
            return
        digest = content_digest(snapshot.files)
        stable_id = str(row["stable_revision_id"] or "")
        if stable_id:
            stable_row = conn.execute(
                "SELECT content_digest FROM package_revisions WHERE id = ?",
                (stable_id,),
            ).fetchone()
            if stable_row is not None and str(stable_row["content_digest"]) == digest:
                return
        package = _package_from_row(row)
        manifest, summary = validate_package_files(package, snapshot.files)
        if manifest is None or summary.status != ValidationStatus.PASSED:
            raise ValueError(f"Legacy package failed canonical validation: {snapshot.package_id}")
        revision_id = _id("package_revision")
        conn.execute(
            """
            INSERT INTO package_revisions (
              id, package_id, revision, status, manifest_json, files_json,
              manifest_artifact_id, content_digest, schema_version,
              validation_summary_json, shadow_status, created_at,
              published_at, supersedes_revision_id
            ) VALUES (?, ?, ?, 'PUBLISHED', ?, ?, ?, ?, ?, ?, 'NOT_RUN', ?, ?, ?)
            """,
            (
                revision_id,
                snapshot.package_id,
                self._next_revision_number(conn, snapshot.package_id),
                _dump(manifest.model_dump(mode="json", by_alias=True)),
                _dump(snapshot.files),
                f"package-manifest:{digest}",
                digest,
                manifest.schema_version,
                _dump(summary.model_dump(mode="json", by_alias=True)),
                now,
                now,
                stable_id or None,
            ),
        )
        conn.execute(
            """
            UPDATE capability_packages
            SET stable_revision_id = ?, revision = revision + 1, updated_at = ?
            WHERE id = ?
            """,
            (revision_id, now, snapshot.package_id),
        )
        conn.execute(
            """
            INSERT OR IGNORE INTO package_bindings (
              id, owner_key, scope_kind, scope_id, package_id, strategy,
              pinned_revision_id, revision, updated_at
            ) VALUES (?, ?, 'SYSTEM', 'default', ?, 'FOLLOW_STABLE', NULL, 1, ?)
            """,
            (_id("package_binding"), _SYSTEM_OWNER, snapshot.package_id, now),
        )
        self._materialize_published(
            snapshot.kind,
            snapshot.package_id,
            revision_id,
            snapshot.files,
        )

    def _package_row(self, conn: sqlite3.Connection, package_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM capability_packages
            WHERE id = ? AND owner_key IN (?, ?)
            """,
            (package_id, _SYSTEM_OWNER, self._owner_key),
        ).fetchone()
        if row is None:
            raise PackageNotFoundError("能力包不存在。")
        return row

    def _workspace_row(self, conn: sqlite3.Connection, workspace_id: str) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM package_workspaces
            WHERE id = ? AND owner_key = ?
            """,
            (workspace_id, self._owner_key),
        ).fetchone()
        if row is None:
            raise PackageWorkspaceNotFoundError("能力包工作区不存在。")
        return row

    def _workspace(self, conn: sqlite3.Connection, workspace_id: str) -> PackageWorkspace:
        row = self._workspace_row(conn, workspace_id)
        files = conn.execute(
            """
            SELECT * FROM package_workspace_files
            WHERE workspace_id = ? ORDER BY path
            """,
            (workspace_id,),
        ).fetchall()
        return PackageWorkspace(
            id=str(row["id"]),
            packageId=str(row["package_id"]),
            baseRevisionId=str(row["base_revision_id"]) if row["base_revision_id"] is not None else None,
            draftRevisionId=str(row["draft_revision_id"]) if row["draft_revision_id"] is not None else None,
            revision=int(row["revision"]),
            status=PackageWorkspaceStatus(str(row["status"])),
            files=[
                PackageWorkspaceFile(
                    path=str(file["path"]),
                    content=str(file["content"]),
                    contentDigest=str(file["content_digest"]),
                    revision=int(file["revision"]),
                )
                for file in files
            ],
            validationSummary=PackageValidationSummary.model_validate_json(
                str(row["validation_summary_json"])
            ),
            createdAt=str(row["created_at"]),
            updatedAt=str(row["updated_at"]),
        )

    def _revision_files_conn(self, conn: sqlite3.Connection, revision_id: str) -> dict[str, str]:
        row = conn.execute(
            "SELECT files_json FROM package_revisions WHERE id = ?",
            (revision_id,),
        ).fetchone()
        if row is None:
            raise PackageNotFoundError("能力包修订不存在。")
        loaded = json.loads(str(row["files_json"]))
        return {str(path): str(content) for path, content in loaded.items()}

    @staticmethod
    def _next_revision_number(conn: sqlite3.Connection, package_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(revision), 0) + 1 FROM package_revisions WHERE package_id = ?",
            (package_id,),
        ).fetchone()
        return int(row[0])

    @staticmethod
    def _replace_workspace_file_rows(
        conn: sqlite3.Connection,
        workspace_id: str,
        files: dict[str, str],
        now: str,
    ) -> None:
        conn.executemany(
            """
            INSERT INTO package_workspace_files (
              workspace_id, path, content, content_digest, revision, updated_at
            ) VALUES (?, ?, ?, ?, 1, ?)
            """,
            [
                (workspace_id, path, content, _text_digest(content), now)
                for path, content in sorted(files.items())
            ],
        )

    def _workspace_root(self, workspace_id: str) -> Path:
        if not workspace_id.startswith("package_workspace_"):
            raise PackageWorkspaceNotFoundError("能力包工作区标识无效。")
        root = (self._data_dir / "package-workspaces" / workspace_id).resolve(strict=False)
        expected = (self._data_dir / "package-workspaces").resolve(strict=False)
        if not root.is_relative_to(expected):
            raise PackageWorkspaceNotFoundError("能力包工作区路径无效。")
        return root

    def _materialize_workspace(self, workspace_id: str, files: dict[str, str]) -> None:
        swap = self._stage_and_swap_workspace(workspace_id, files)
        swap.commit()

    def _stage_and_swap_workspace(
        self,
        workspace_id: str,
        files: dict[str, str],
    ) -> "_WorkspaceSwap":
        root = self._workspace_root(workspace_id)
        root.mkdir(parents=True, exist_ok=True)
        stage = root / f".stage-{uuid.uuid4().hex}"
        stage.mkdir()
        for raw_path, content in sorted(files.items()):
            path = normalize_package_path(raw_path)
            destination = stage.joinpath(*PurePosixPath(path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
        current = root / "current"
        backup = root / f".backup-{uuid.uuid4().hex}"
        if current.exists():
            current.replace(backup)
        try:
            stage.replace(current)
        except BaseException:
            if backup.exists():
                backup.replace(current)
            raise
        return _WorkspaceSwap(current=current, backup=backup)

    def _materialize_published(
        self,
        kind: PackageKind,
        package_id: str,
        revision_id: str,
        files: dict[str, str],
    ) -> None:
        package_key = hashlib.sha256(package_id.encode("utf-8")).hexdigest()[:24]
        root = (
            self._data_dir
            / "packages"
            / kind.value.lower()
            / package_key
            / revision_id
        ).resolve(strict=False)
        packages_root = (self._data_dir / "packages").resolve(strict=False)
        if not root.is_relative_to(packages_root):
            raise ValueError("Published package path escaped the package root")
        if root.exists():
            if self._published_tree_matches(root, files):
                return
            raise PackageConflictError("已发布能力包修订的本地内容不一致，拒绝覆盖。")
        stage = root.with_name(f".{root.name}.{uuid.uuid4().hex}.tmp")
        stage.mkdir(parents=True)
        for raw_path, content in sorted(files.items()):
            path = normalize_package_path(raw_path)
            destination = stage.joinpath(*PurePosixPath(path).parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(content, encoding="utf-8", newline="\n")
        for attempt in range(_PUBLISHED_SWAP_ATTEMPTS):
            try:
                stage.replace(root)
                return
            except OSError as exc:
                if root.exists():
                    concurrent_revision_matches = self._published_tree_matches(
                        root,
                        files,
                    )
                    if stage.exists():
                        shutil.rmtree(stage)
                    if concurrent_revision_matches:
                        return
                    raise PackageConflictError(
                        "并发写入的能力包修订内容不一致，拒绝覆盖。"
                    ) from exc
                final_attempt = attempt + 1 == _PUBLISHED_SWAP_ATTEMPTS
                if not isinstance(exc, PermissionError) or final_attempt:
                    if stage.exists():
                        shutil.rmtree(stage)
                    raise
                time.sleep(
                    _PUBLISHED_SWAP_INITIAL_DELAY_SECONDS * (2**attempt)
                )

    @staticmethod
    def _published_tree_matches(root: Path, files: dict[str, str]) -> bool:
        expected = {
            normalize_package_path(raw_path): content
            for raw_path, content in files.items()
        }
        actual_paths = {
            path.relative_to(root).as_posix()
            for path in root.rglob("*")
            if path.is_file()
        }
        if actual_paths != set(expected):
            return False
        return all(
            root.joinpath(*PurePosixPath(path).parts).read_text(encoding="utf-8")
            == content
            for path, content in expected.items()
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


class _WorkspaceSwap:
    def __init__(self, *, current: Path, backup: Path) -> None:
        self._current = current
        self._backup = backup

    def commit(self) -> None:
        if self._backup.exists():
            shutil.rmtree(self._backup)

    def rollback(self) -> None:
        if self._current.exists():
            shutil.rmtree(self._current)
        if self._backup.exists():
            self._backup.replace(self._current)


def _package_from_row(row: sqlite3.Row) -> CapabilityPackage:
    return CapabilityPackage(
        id=str(row["id"]),
        kind=PackageKind(str(row["kind"])),
        slug=str(row["slug"]),
        displayName=str(row["display_name"]),
        ownerSubject=str(row["owner_subject"]) if row["owner_subject"] is not None else None,
        stableRevisionId=str(row["stable_revision_id"]) if row["stable_revision_id"] is not None else None,
        draftRevisionId=str(row["draft_revision_id"]) if row["draft_revision_id"] is not None else None,
        revision=int(row["revision"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
    )


def _revision_from_row(row: sqlite3.Row) -> PackageRevision:
    return PackageRevision(
        id=str(row["id"]),
        packageId=str(row["package_id"]),
        revision=int(row["revision"]),
        status=PackageRevisionStatus(str(row["status"])),
        manifestArtifactId=str(row["manifest_artifact_id"]),
        contentDigest=str(row["content_digest"]),
        schemaVersion=int(row["schema_version"]),
        validationSummary=PackageValidationSummary.model_validate_json(
            str(row["validation_summary_json"])
        ),
        shadowStatus=ShadowStatus(str(row["shadow_status"])),
        createdAt=str(row["created_at"]),
        publishedAt=str(row["published_at"]) if row["published_at"] is not None else None,
        supersedesRevisionId=str(row["supersedes_revision_id"]) if row["supersedes_revision_id"] is not None else None,
    )


def _input_snapshot_from_row(row: sqlite3.Row) -> PackageInputSnapshot:
    return PackageInputSnapshot(
        id=str(row["id"]),
        sourceTurnId=str(row["source_turn_id"]),
        workId=str(row["work_id"]),
        input=json.loads(str(row["input_json"])),
        executionRevisionSet=json.loads(str(row["execution_revision_set_json"])),
        redacted=bool(row["redacted"]),
        createdAt=str(row["created_at"]),
    )


def _new_package_files(
    package_id: str,
    kind: PackageKind,
    display_name: str,
) -> dict[str, str]:
    manifest = {
        "schemaVersion": 1,
        "id": package_id,
        "kind": kind.value,
        "displayName": display_name,
        "version": "0.1.0-draft",
        "channel": "draft",
        "capabilities": [],
        "permissions": [],
        "riskLevel": "low",
        "confirmationPolicy": "never",
        "entrypoints": {},
        "compatibility": {},
        "evidence": {},
        "files": [],
    }
    return {"manifest.json": _dump(manifest) + "\n"}


def _manifest_json(files: dict[str, str]) -> dict[str, object]:
    raw = files.get("manifest.json", "{}")
    try:
        loaded = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return loaded if isinstance(loaded, dict) else {}


def _manifest_requires_confirmation(manifest: dict[str, object]) -> bool:
    permissions = manifest.get("permissions")
    permission_values = set(permissions) if isinstance(permissions, list) else set()
    return (
        manifest.get("riskLevel") == "high"
        or manifest.get("confirmationPolicy") == "always"
        or bool(permission_values & {"RUN_SHELL", "USE_DEVICE", "RUN_CAD"})
    )


def _text_digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
