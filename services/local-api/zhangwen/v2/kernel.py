"""Transaction boundary for V2 project state, change sets and versions."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable

from zhangwen.projects.repository import ProjectRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.v2.models import (
    CapabilityKind,
    CapabilityStatus,
    ChangeSetConfirmationPolicy,
    ChangeSetRiskLevel,
    ChangeSetStatus,
    CreateChangeSetRequest,
    CreateReleaseRequest,
    ProjectMode,
)


class ProjectKernelError(RuntimeError):
    def __init__(self, code: str, message: str, *, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class ProjectKernel:
    """Builds projections and commits bounded V2 changes over existing truth tables."""

    def __init__(self, data_dir: Path) -> None:
        self._projects = ProjectRepository(data_dir)
        self._db_path = self._projects.db_path
        # Mirror the existing Hardware Library read path: bundled resources are
        # seeded idempotently in their original table, then adapted below.
        seed_default_components(self._db_path)

    def project_state(self, project_id: str) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        self._ensure_imported_baseline(project_id)
        with self._connect() as conn:
            self._sync_capability_adapters(conn)
            state = self._project_state(conn, project_id)
            self._store_snapshot(conn, state)
            conn.commit()
            return state

    def list_change_sets(self, project_id: str) -> list[dict[str, Any]]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_change_sets
                WHERE project_id = ? ORDER BY created_at DESC, id DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._change_set_dict(row) for row in rows]

    def create_change_set(
        self, project_id: str, request: CreateChangeSetRequest
    ) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        self._ensure_imported_baseline(project_id)
        with self._connect() as conn:
            existing = conn.execute(
                """
                SELECT * FROM project_change_sets
                WHERE project_id = ? AND idempotency_key = ?
                """,
                (project_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                return self._change_set_dict(existing)
            current_version = self._current_version(conn, project_id)
            if request.base_project_version != current_version:
                raise ProjectKernelError(
                    "PROJECT_VERSION_CONFLICT",
                    f"基础版本 {request.base_project_version} 已过期，当前版本为 {current_version}。",
                    status_code=409,
                )
            validations, affected_facts, affected_artifacts, bindings = (
                self._validate_operations(conn, project_id, request.operations)
            )
            risk = self._risk_level(request.operations)
            policy = (
                ChangeSetConfirmationPolicy.EXPLICIT_RISK
                if risk is ChangeSetRiskLevel.HIGH
                else ChangeSetConfirmationPolicy.USER
            )
            status = (
                ChangeSetStatus.REJECTED
                if any(item["severity"] == "FAIL" for item in validations)
                else ChangeSetStatus.READY
            )
            change_set_id = _id("chg")
            now = _now()
            conn.execute(
                """
                INSERT INTO project_change_sets (
                  id, project_id, base_project_version, author_type, owner_domain,
                  intent_summary, operations_json, affected_facts_json,
                  affected_artifacts_json, capability_bindings_json,
                  validation_results_json, risk_level, confirmation_policy, status,
                  idempotency_key, created_at, committed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    change_set_id,
                    project_id,
                    request.base_project_version,
                    request.author_type,
                    request.owner_domain,
                    request.intent_summary,
                    _dump([item.model_dump(by_alias=True) for item in request.operations]),
                    _dump(sorted(affected_facts)),
                    _dump(sorted(affected_artifacts)),
                    _dump(sorted(bindings)),
                    _dump(validations),
                    risk.value,
                    policy.value,
                    status.value,
                    request.idempotency_key,
                    now,
                ),
            )
            self._append_event(
                conn,
                project_id=project_id,
                event_type="CHANGE_SET_PROPOSED",
                change_set_id=change_set_id,
                project_version=current_version,
                payload={"status": status.value, "riskLevel": risk.value},
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM project_change_sets WHERE id = ?", (change_set_id,)
            ).fetchone()
            assert row is not None
            return self._change_set_dict(row)

    def confirm_change_set(self, project_id: str, change_set_id: str) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            row = self._change_set_row(conn, project_id, change_set_id)
            if row["status"] == ChangeSetStatus.COMMITTED.value:
                return self._change_set_dict(row)
            if row["status"] not in {
                ChangeSetStatus.READY.value,
                ChangeSetStatus.CONFIRMED.value,
            }:
                raise ProjectKernelError(
                    "CHANGE_SET_NOT_CONFIRMABLE", "当前变更集不能确认。", status_code=409
                )
            conn.execute(
                "UPDATE project_change_sets SET status = ? WHERE id = ?",
                (ChangeSetStatus.CONFIRMED.value, change_set_id),
            )
            self._append_event(
                conn,
                project_id=project_id,
                event_type="CHANGE_SET_CONFIRMED",
                change_set_id=change_set_id,
                project_version=int(row["base_project_version"]),
                payload={},
            )
            conn.commit()
            confirmed = conn.execute(
                "SELECT * FROM project_change_sets WHERE id = ?", (change_set_id,)
            ).fetchone()
            assert confirmed is not None
            return self._change_set_dict(confirmed)

    def commit_change_set(self, project_id: str, change_set_id: str) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = self._change_set_row(conn, project_id, change_set_id)
            if row["status"] == ChangeSetStatus.COMMITTED.value:
                version = conn.execute(
                    "SELECT * FROM project_versions WHERE change_set_id = ?",
                    (change_set_id,),
                ).fetchone()
                assert version is not None
                conn.rollback()
                return self._version_dict(version)
            if row["status"] != ChangeSetStatus.CONFIRMED.value:
                raise ProjectKernelError(
                    "CHANGE_SET_NOT_CONFIRMED", "变更集必须先确认。", status_code=409
                )
            current_version = self._current_version(conn, project_id)
            base_version = int(row["base_project_version"])
            if current_version != base_version:
                raise ProjectKernelError(
                    "PROJECT_VERSION_CONFLICT",
                    f"基础版本 {base_version} 已过期，当前版本为 {current_version}。",
                    status_code=409,
                )
            operations = json.loads(str(row["operations_json"]))
            for operation in operations:
                self._apply_operation(conn, project_id, operation)
            next_version = current_version + 1
            state = self._project_state(
                conn, project_id, project_version_override=next_version
            )
            capability_hash = self._capability_snapshot_hash(conn, project_id)
            artifact_ids = self._active_artifact_version_ids(conn, project_id)
            version_id = _id("pver")
            now = _now()
            conn.execute(
                """
                INSERT INTO project_versions (
                  id, project_id, version, state_hash, change_set_id,
                  capability_snapshot_hash, artifact_version_ids_json,
                  validation_summary_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    project_id,
                    next_version,
                    state["projectionHash"],
                    change_set_id,
                    capability_hash,
                    _dump(artifact_ids),
                    row["validation_results_json"],
                    now,
                ),
            )
            conn.execute(
                """
                UPDATE project_change_sets
                SET status = ?, committed_at = ? WHERE id = ?
                """,
                (ChangeSetStatus.COMMITTED.value, now, change_set_id),
            )
            self._store_snapshot(conn, state)
            self._append_event(
                conn,
                project_id=project_id,
                event_type="CHANGE_SET_COMMITTED",
                change_set_id=change_set_id,
                project_version=next_version,
                payload={"stateHash": state["projectionHash"], "versionId": version_id},
            )
            self._append_event(
                conn,
                project_id=project_id,
                event_type="PROJECT_VERSION_CREATED",
                change_set_id=change_set_id,
                project_version=next_version,
                payload={"versionId": version_id},
            )
            conn.commit()
            version = conn.execute(
                "SELECT * FROM project_versions WHERE id = ?", (version_id,)
            ).fetchone()
            assert version is not None
            return self._version_dict(version)

    def list_versions(self, project_id: str) -> list[dict[str, Any]]:
        self._projects.assert_project_access(project_id)
        self._ensure_imported_baseline(project_id)
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM project_versions WHERE project_id = ? ORDER BY version DESC",
                (project_id,),
            ).fetchall()
            return [self._version_dict(row) for row in rows]

    def create_release(
        self, project_id: str, request: CreateReleaseRequest
    ) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        self._ensure_imported_baseline(project_id)
        with self._connect() as conn:
            if request.project_version_id:
                version = conn.execute(
                    """
                    SELECT * FROM project_versions
                    WHERE id = ? AND project_id = ?
                    """,
                    (request.project_version_id, project_id),
                ).fetchone()
            else:
                version = conn.execute(
                    """
                    SELECT * FROM project_versions
                    WHERE project_id = ? ORDER BY version DESC LIMIT 1
                    """,
                    (project_id,),
                ).fetchone()
            if version is None:
                raise ProjectKernelError(
                    "PROJECT_VERSION_REQUIRED", "请先提交一个项目版本。", status_code=409
                )
            artifact_ids = json.loads(str(version["artifact_version_ids_json"]))
            manifest = {
                "projectId": project_id,
                "projectVersionId": str(version["id"]),
                "stateHash": str(version["state_hash"]),
                "artifactVersionIds": artifact_ids,
            }
            release_id = _id("rel")
            now = _now()
            manifest_hash = _hash(manifest)
            conn.execute(
                """
                INSERT INTO project_releases (
                  id, project_id, project_version_id, name, manifest_hash,
                  artifact_version_ids_json, unverified_items_json, notes, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, '[]', ?, ?)
                """,
                (
                    release_id,
                    project_id,
                    str(version["id"]),
                    request.name,
                    manifest_hash,
                    _dump(artifact_ids),
                    request.notes,
                    now,
                ),
            )
            self._append_event(
                conn,
                project_id=project_id,
                event_type="RELEASE_CREATED",
                change_set_id=None,
                project_version=int(version["version"]),
                payload={"releaseId": release_id, "manifestHash": manifest_hash},
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM project_releases WHERE id = ?", (release_id,)
            ).fetchone()
            assert row is not None
            return self._release_dict(row)

    def list_releases(self, project_id: str) -> list[dict[str, Any]]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_releases
                WHERE project_id = ? ORDER BY created_at DESC
                """,
                (project_id,),
            ).fetchall()
            return [self._release_dict(row) for row in rows]

    def list_capabilities(self, project_id: str) -> list[dict[str, Any]]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            self._sync_capability_adapters(conn)
            rows = conn.execute(
                "SELECT * FROM capabilities ORDER BY kind, name, id"
            ).fetchall()
            conn.commit()
            return [self._capability_dict(row) for row in rows]

    def capability_coverage(self, project_id: str) -> dict[str, Any]:
        self._projects.assert_project_access(project_id)
        with self._connect() as conn:
            self._sync_capability_adapters(conn)
            coverage = self._coverage(conn, project_id)
            conn.commit()
            return coverage

    def _project_state(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        project_version_override: int | None = None,
    ) -> dict[str, Any]:
        project = conn.execute(
            "SELECT * FROM projects WHERE id = ?", (project_id,)
        ).fetchone()
        if project is None:
            raise ProjectKernelError("PROJECT_NOT_FOUND", "项目不存在。", status_code=404)
        version = (
            project_version_override
            if project_version_override is not None
            else self._current_version(conn, project_id)
        )
        facts = []
        for index, row in enumerate(
            conn.execute(
                """
                  SELECT id, field, key, value_json, source_id, updated_at
                FROM project_shared_facts
                WHERE project_id = ? AND status = 'confirmed'
                ORDER BY field, key, updated_at, id
                """,
                (project_id,),
            ).fetchall(),
            start=1,
        ):
              value = _load(row["value_json"], None)
              label, display_value = self._fact_presentation(conn, row, value)
              facts.append(
                  {
                      "id": str(row["id"]),
                      "key": str(row["key"] or row["field"]),
                      "label": label,
                      "value": value,
                      "displayValue": display_value,
                      "revision": index,
                  }
              )
        mode = self._project_mode(facts)
        artifacts = self._artifact_domains(conn, project_id)
        pending = [
            str(row["title"])
            for row in conn.execute(
                """
                SELECT title FROM project_pending_items
                WHERE project_id = ? AND status = 'open'
                ORDER BY priority, updated_at DESC
                """,
                (project_id,),
            ).fetchall()
        ]
        expert_status = {
            str(row["expert_type"]): str(row["workspace_status"] or row["status"])
            for row in conn.execute(
                """
                SELECT expert_type, workspace_status, status FROM project_experts
                WHERE project_id = ? AND removed_at IS NULL
                  AND COALESCE(archived_legacy_thread, 0) = 0
                """,
                (project_id,),
            ).fetchall()
        }
        projected_at = _now()
        payload: dict[str, Any] = {
            "schemaVersion": 1,
            "projectId": project_id,
            "projectVersion": version,
            "projectedAt": projected_at,
            "mode": mode.value,
            "stage": str(project["stage"]),
            "currentRecommendation": self._current_recommendation(conn, project_id),
            "facts": facts,
            "domains": {
                "problemGuide": {
                    "status": expert_status.get("problem_guide", "not_started"),
                    "revision": None,
                    "activeArtifactIds": artifacts["problem_guide"],
                    "pendingItems": pending,
                },
                "engineering": {
                    "status": expert_status.get("smart_engineer", "not_started"),
                    "revision": None,
                    "activeArtifactIds": artifacts["engineering"],
                    "pendingItems": pending,
                },
                "structure": {
                    "status": expert_status.get("structure_engineer", "not_started"),
                    "revision": None,
                    "activeArtifactIds": artifacts["structure"],
                    "pendingItems": pending,
                },
                "delivery": {
                    "status": "ready" if artifacts["delivery"] else "not_started",
                    "revision": None,
                    "activeArtifactIds": artifacts["delivery"],
                    "pendingItems": pending,
                },
            },
            "capabilityCoverage": self._coverage(conn, project_id),
        }
        semantic_payload = {
            key: value for key, value in payload.items() if key != "projectedAt"
        }
        semantic_payload["facts"] = [
            {
                "id": fact["id"],
                "key": fact["key"],
                "value": fact["value"],
                "revision": fact["revision"],
            }
            for fact in facts
        ]
        payload["projectionHash"] = _hash(semantic_payload)
        return payload

    def _fact_presentation(
        self,
        conn: sqlite3.Connection,
        row: sqlite3.Row,
        value: Any,
    ) -> tuple[str, str]:
        field = str(row["field"])
        key = str(row["key"] or field)
        if field == "clarification_answer":
            return self._clarification_fact_presentation(
                conn,
                source_message_id=str(row["source_id"] or ""),
                question_id=key,
                value=value,
            )
        if field == "delivery_track":
            track = value.get("track") if isinstance(value, dict) else None
            return "交付路线", {
                "project": "工程项目",
                "lesson": "教学方案",
            }.get(str(track), "已确认")
        if field == "preferred_hardware":
            components = value.get("components") if isinstance(value, dict) else None
            names = [
                str(component.get("name") or component.get("id"))
                for component in components or []
                if isinstance(component, dict)
                and (component.get("name") or component.get("id"))
            ]
            validation = value.get("validation") if isinstance(value, dict) else None
            message = validation.get("message") if isinstance(validation, dict) else None
            summary = "、".join(names) or "已确认硬件"
            if isinstance(message, str) and message.strip():
                summary = f"{summary} · {message.strip()}"
            return "项目硬件", summary
        return _human_fact_label(key), _human_fact_value(value)

    def _clarification_fact_presentation(
        self,
        conn: sqlite3.Connection,
        *,
        source_message_id: str,
        question_id: str,
        value: Any,
    ) -> tuple[str, str]:
        payloads: list[dict[str, Any]] = []
        if source_message_id:
            message = conn.execute(
                """
                SELECT structured_payload_json, metadata_json
                FROM messages WHERE id = ?
                """,
                (source_message_id,),
            ).fetchone()
            if message is not None:
                payload = _load(message["structured_payload_json"], None)
                if isinstance(payload, dict):
                    payloads.append(payload)
                metadata = _load(message["metadata_json"], {})
                reply_to = metadata.get("replyToMessageId") if isinstance(metadata, dict) else None
                if isinstance(reply_to, str) and reply_to:
                    source = conn.execute(
                        "SELECT structured_payload_json FROM messages WHERE id = ?",
                        (reply_to,),
                    ).fetchone()
                    source_payload = _load(
                        source["structured_payload_json"] if source else None,
                        None,
                    )
                    if isinstance(source_payload, dict):
                        payloads.append(source_payload)

        selected_ids = value.get("selectedOptionIds") if isinstance(value, dict) else None
        text_input = value.get("textInput") if isinstance(value, dict) else None
        for payload in payloads:
            questions = payload.get("questions")
            if not isinstance(questions, list):
                question = payload.get("question")
                questions = [question] if isinstance(question, dict) else []
            for question in questions:
                if not isinstance(question, dict) or question.get("id") != question_id:
                    continue
                label = question.get("text") or question.get("question")
                option_labels: list[str] = []
                options = question.get("options")
                if isinstance(options, list) and isinstance(selected_ids, list):
                    by_id = {
                        str(option.get("id")): str(option.get("label") or option.get("value"))
                        for option in options
                        if isinstance(option, dict) and option.get("id")
                    }
                    option_labels = [
                        by_id.get(str(option_id), str(option_id))
                        for option_id in selected_ids
                    ]
                if isinstance(text_input, str) and text_input.strip():
                    option_labels.append(text_input.strip())
                if isinstance(label, str) and label.strip():
                    return label.strip(), "、".join(option_labels) or "已确认"
        return _human_fact_label(question_id), _human_fact_value(value)

    def _validate_operations(
        self, conn: sqlite3.Connection, project_id: str, operations: Iterable[Any]
    ) -> tuple[list[dict[str, str]], set[str], set[str], set[str]]:
        validations: list[dict[str, str]] = []
        facts: set[str] = set()
        artifacts: set[str] = set()
        bindings: set[str] = set()
        for operation in operations:
            op = operation.op
            path = operation.path
            if op == "SET_PROJECT_MODE":
                try:
                    ProjectMode(str(operation.value))
                    valid = path == "/mode"
                except ValueError:
                    valid = False
                validations.append(_validation(valid, "PROJECT_MODE", "项目模式有效。", "项目模式或路径无效。"))
            elif op in {"UPSERT_FACT", "REMOVE_FACT"}:
                valid = path.startswith("/facts/") and len(path.split("/")) >= 4
                if valid:
                    facts.add(path.removeprefix("/facts/"))
                validations.append(_validation(valid, "FACT_PATH", "项目事实路径有效。", "事实路径必须为 /facts/{field}/{key}。"))
            elif op in {"BIND_CAPABILITY", "UNBIND_CAPABILITY"}:
                capability_id = path.removeprefix("/capabilities/")
                exists = conn.execute(
                    "SELECT 1 FROM capabilities WHERE id = ?", (capability_id,)
                ).fetchone()
                valid = path.startswith("/capabilities/") and exists is not None
                if valid:
                    bindings.add(capability_id)
                validations.append(_validation(valid, "CAPABILITY", "能力绑定有效。", "能力不存在或路径无效。"))
            elif op == "MARK_ARTIFACT_OUTDATED":
                artifact_id = path.removeprefix("/artifacts/")
                exists = conn.execute(
                    "SELECT 1 FROM artifacts WHERE id = ? AND project_id = ?",
                    (artifact_id, project_id),
                ).fetchone()
                valid = path.startswith("/artifacts/") and exists is not None
                if valid:
                    artifacts.add(artifact_id)
                validations.append(_validation(valid, "ARTIFACT", "产物影响有效。", "产物不存在或不属于当前项目。"))
        return validations, facts, artifacts, bindings

    def _apply_operation(
        self, conn: sqlite3.Connection, project_id: str, operation: dict[str, Any]
    ) -> None:
        op = str(operation["op"])
        path = str(operation["path"])
        now = _now()
        if op == "SET_PROJECT_MODE":
            self._upsert_fact(
                conn,
                project_id,
                field="v2",
                key="project_mode",
                value=operation.get("value"),
                now=now,
            )
        elif op == "UPSERT_FACT":
            segments = path.removeprefix("/facts/").split("/", 1)
            self._upsert_fact(
                conn,
                project_id,
                field=segments[0],
                key=segments[1],
                value=operation.get("value"),
                now=now,
            )
        elif op == "REMOVE_FACT":
            field, key = path.removeprefix("/facts/").split("/", 1)
            conn.execute(
                """
                UPDATE project_shared_facts SET status = 'superseded', updated_at = ?
                WHERE project_id = ? AND field = ? AND key = ? AND status = 'confirmed'
                """,
                (now, project_id, field, key),
            )
        elif op == "BIND_CAPABILITY":
            capability_id = path.removeprefix("/capabilities/")
            requirement_key = str(operation.get("value") or capability_id)
            conn.execute(
                """
                INSERT INTO project_capability_bindings (
                  id, project_id, capability_id, requirement_key, bound_at, unbound_at
                ) VALUES (?, ?, ?, ?, ?, NULL)
                ON CONFLICT(project_id, capability_id, requirement_key) DO UPDATE SET
                  bound_at = excluded.bound_at, unbound_at = NULL
                """,
                (_id("capb"), project_id, capability_id, requirement_key, now),
            )
        elif op == "UNBIND_CAPABILITY":
            capability_id = path.removeprefix("/capabilities/")
            conn.execute(
                """
                UPDATE project_capability_bindings SET unbound_at = ?
                WHERE project_id = ? AND capability_id = ? AND unbound_at IS NULL
                """,
                (now, project_id, capability_id),
            )
        elif op == "MARK_ARTIFACT_OUTDATED":
            artifact_id = path.removeprefix("/artifacts/")
            conn.execute(
                """
                UPDATE artifacts SET status = 'STALE', domain_status = 'outdated', updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (now, artifact_id, project_id),
            )

    def _upsert_fact(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        *,
        field: str,
        key: str,
        value: Any,
        now: str,
    ) -> None:
        previous = conn.execute(
            """
            SELECT id FROM project_shared_facts
            WHERE project_id = ? AND field = ? AND key = ? AND status = 'confirmed'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (project_id, field, key),
        ).fetchone()
        fact_id = _id("fact")
        if previous is not None:
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = 'superseded', superseded_by = ?, updated_at = ?
                WHERE id = ?
                """,
                (fact_id, now, str(previous["id"])),
            )
        conn.execute(
            """
            INSERT INTO project_shared_facts (
              id, project_id, field, key, value_json, status, source_type,
              source_id, source_expert_id, proposed_by_expert_type,
              confirmed_by, confirmed_at, superseded_by,
              affects_artifact_ids_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, 'confirmed', 'v2_change_set', NULL, NULL,
                      NULL, 'user', ?, NULL, '[]', ?, ?)
            """,
            (fact_id, project_id, field, key, _dump(value), now, now, now),
        )

    def _sync_capability_adapters(self, conn: sqlite3.Connection) -> None:
        now = _now()
        builtins = [
            ("cap:procedure:problem-guide", CapabilityKind.PROCEDURE, CapabilityStatus.VERIFIED, "问题定义流程", "agent_skill", "problem-guide", "v2"),
            ("cap:procedure:smart-engineer", CapabilityKind.PROCEDURE, CapabilityStatus.VERIFIED, "智能工程流程", "agent_skill", "smart-engineer", "v2"),
            ("cap:procedure:structure-engineer", CapabilityKind.PROCEDURE, CapabilityStatus.VERIFIED, "结构工程流程", "agent_skill", "structure-engineer", "v2"),
            ("cap:execution:cad-local", CapabilityKind.EXECUTION, CapabilityStatus.DRAFT, "本地 CAD Worker", "host", "cad.local", "v2"),
            ("cap:execution:device-serial", CapabilityKind.EXECUTION, CapabilityStatus.DRAFT, "本地串口 Runner", "host", "device.serial", "v2"),
        ]
        for item in builtins:
            host_requirements = [item[5]] if item[1] is CapabilityKind.EXECUTION else []
            self._upsert_capability(
                conn,
                capability_id=item[0],
                kind=item[1].value,
                status=item[2].value,
                name=item[3],
                version="1",
                source_type=item[4],
                source_id=item[5],
                revision=item[6],
                host_requirements=host_requirements,
                risk="MEDIUM" if host_requirements else "LOW",
                metadata={},
                now=now,
            )
        for row in conn.execute(
            """
            SELECT id, name, category, status, updated_at
            FROM hardware_components ORDER BY id
            """
        ).fetchall():
            self._upsert_capability(
                conn,
                capability_id=f"cap:hardware:{row['id']}",
                kind=CapabilityKind.RESOURCE.value,
                status=(
                    CapabilityStatus.VERIFIED.value
                    if str(row["status"]) == "ACTIVE"
                    else CapabilityStatus.DEPRECATED.value
                ),
                name=str(row["name"]),
                version="1",
                source_type="hardware_component",
                source_id=str(row["id"]),
                revision=str(row["updated_at"]),
                host_requirements=[],
                risk="LOW",
                metadata={"category": str(row["category"])},
                now=now,
            )
        if self._table_exists(conn, "mechanical_profile_versions"):
            for row in conn.execute(
                """
                SELECT profile_id, revision, display_name, evidence_level,
                       representation, content_sha256
                FROM mechanical_profile_versions ORDER BY profile_id, revision
                """
            ).fetchall():
                self._upsert_capability(
                    conn,
                    capability_id=f"cap:mechanical:{row['profile_id']}:{row['revision']}",
                    kind=CapabilityKind.RESOURCE.value,
                    status=(
                        CapabilityStatus.VERIFIED.value
                        if str(row["evidence_level"]).lower() in {"verified", "official"}
                        else CapabilityStatus.DRAFT.value
                    ),
                    name=str(row["display_name"]),
                    version=str(row["revision"]),
                    source_type="mechanical_profile",
                    source_id=str(row["profile_id"]),
                    revision=str(row["revision"]),
                    host_requirements=["cad.local"],
                    risk="MEDIUM",
                    metadata={
                        "representation": str(row["representation"]),
                        "contentSha256": str(row["content_sha256"]),
                    },
                    now=now,
                )

    def _upsert_capability(
        self,
        conn: sqlite3.Connection,
        *,
        capability_id: str,
        kind: str,
        status: str,
        name: str,
        version: str,
        source_type: str,
        source_id: str,
        revision: str,
        host_requirements: list[str],
        risk: str,
        metadata: dict[str, Any],
        now: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO capabilities (
              id, kind, status, name, version, source_type, source_id, revision,
              host_requirements_json, risk_level, metadata_json, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              kind = excluded.kind, status = excluded.status, name = excluded.name,
              version = excluded.version, source_type = excluded.source_type,
              source_id = excluded.source_id, revision = excluded.revision,
              host_requirements_json = excluded.host_requirements_json,
              risk_level = excluded.risk_level, metadata_json = excluded.metadata_json,
              updated_at = excluded.updated_at
            """,
            (
                capability_id,
                kind,
                status,
                name,
                version,
                source_type,
                source_id,
                revision,
                _dump(host_requirements),
                risk,
                _dump(metadata),
                now,
            ),
        )

    def _coverage(self, conn: sqlite3.Connection, project_id: str) -> dict[str, Any]:
        selected_ids = self._selected_hardware_ids(conn, project_id)
        verified: list[str] = []
        missing: list[dict[str, str]] = []
        for hardware_id in selected_ids:
            row = conn.execute(
                """
                SELECT id, status FROM capabilities
                WHERE source_type = 'hardware_component' AND source_id = ?
                ORDER BY updated_at DESC LIMIT 1
                """,
                (hardware_id,),
            ).fetchone()
            if row is not None and row["status"] == CapabilityStatus.VERIFIED.value:
                verified.append(str(row["id"]))
            else:
                missing.append(
                    {"requirement": hardware_id, "reason": "缺少已验证的硬件能力。"}
                )
        bound = conn.execute(
            """
            SELECT c.id, c.status FROM project_capability_bindings b
            JOIN capabilities c ON c.id = b.capability_id
            WHERE b.project_id = ? AND b.unbound_at IS NULL
            """,
            (project_id,),
        ).fetchall()
        verified.extend(
            str(row["id"])
            for row in bound
            if row["status"] == CapabilityStatus.VERIFIED.value
        )
        total = len(selected_ids)
        percent = 100 if total == 0 else round((total - len(missing)) * 100 / total)
        mode = (
            ProjectMode.STANDARD
            if not missing
            else ProjectMode.EXPLORATION
        )
        return {
            "mode": mode.value,
            "coveragePercent": percent,
            "verifiedCapabilityIds": sorted(set(verified)),
            "missing": missing,
        }

    def _selected_hardware_ids(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[str]:
        row = conn.execute(
            """
            SELECT value_json FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
              AND status = 'confirmed'
            ORDER BY updated_at DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        value = _load(row[0] if row else None, {})
        if not isinstance(value, dict) or not isinstance(value.get("components"), list):
            return []
        component_ids: list[str] = []
        for component in value["components"]:
            if not isinstance(component, dict):
                continue
            component_id = component.get("id") or component.get("componentId")
            if isinstance(component_id, str) and component_id and component_id not in component_ids:
                component_ids.append(component_id)
        return component_ids[:32]

    def _project_mode(self, facts: list[dict[str, Any]]) -> ProjectMode:
        for fact in reversed(facts):
            if fact["key"] == "project_mode":
                try:
                    return ProjectMode(str(fact["value"]))
                except ValueError:
                    break
        return ProjectMode.STANDARD

    def _artifact_domains(
        self, conn: sqlite3.Connection, project_id: str
    ) -> dict[str, list[str]]:
        result = {
            "problem_guide": [],
            "engineering": [],
            "structure": [],
            "delivery": [],
        }
        for row in conn.execute(
            """
            SELECT id, source_agent_id, kind FROM artifacts
            WHERE project_id = ? AND status NOT IN ('ARCHIVED', 'REJECTED')
            ORDER BY updated_at, id
            """,
            (project_id,),
        ).fetchall():
            source = str(row["source_agent_id"])
            kind = str(row["kind"])
            if source == "cad-agent" or kind == "MODEL_3D":
                domain = "structure"
            elif source in {"spec-agent", "code-agent", "deploy-agent"} or kind == "CODE":
                domain = "engineering"
            elif kind in {"PACKAGE", "REPORT"} or source == "lesson-agent":
                domain = "delivery"
            else:
                domain = "problem_guide"
            result[domain].append(str(row["id"]))
        return result

    def _current_recommendation(
        self, conn: sqlite3.Connection, project_id: str
    ) -> str | None:
        row = conn.execute(
            """
            SELECT sections_json FROM proposals
            WHERE project_id = ? AND status IN ('CONFIRMED', 'APPROVED')
            ORDER BY version DESC LIMIT 1
            """,
            (project_id,),
        ).fetchone()
        if row is None:
            row = conn.execute(
                """
                SELECT sections_json FROM solutions
                WHERE project_id = ? AND status = 'CONFIRMED'
                ORDER BY version DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        value = _load(row[0] if row else None, None)
        if isinstance(value, dict):
            for key in ("summary", "overview", "title", "goal"):
                if isinstance(value.get(key), str) and value[key].strip():
                    return value[key].strip()
        if isinstance(value, list):
            preferred_ids = (
                "project_overview",
                "goal",
                "functional_logic",
                "hardware_software_structure",
            )
            sections = [item for item in value if isinstance(item, dict)]
            for preferred_id in preferred_ids:
                for section in sections:
                    if section.get("id") != preferred_id:
                        continue
                    content = section.get("content")
                    if isinstance(content, str) and content.strip():
                        return content.strip()
            for section in sections:
                content = section.get("content")
                if isinstance(content, str) and content.strip():
                    return content.strip()
        return None

    def _ensure_imported_baseline(self, project_id: str) -> None:
        """Create one V2 version for an established V1 project, without copying truth."""

        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            if self._current_version(conn, project_id) > 0:
                conn.rollback()
                return
            legacy_row = conn.execute(
                """
                SELECT (
                  EXISTS(SELECT 1 FROM solutions
                         WHERE project_id = ? AND status = 'CONFIRMED')
                  OR EXISTS(SELECT 1 FROM proposals
                            WHERE project_id = ? AND status IN ('CONFIRMED', 'APPROVED'))
                  OR EXISTS(SELECT 1 FROM artifacts
                            WHERE project_id = ? AND status NOT IN ('ARCHIVED', 'REJECTED'))
                  OR EXISTS(SELECT 1 FROM device_operations WHERE project_id = ?)
                  OR EXISTS(SELECT 1 FROM cad_runs WHERE project_id = ?)
                )
                """,
                (project_id,) * 5,
            ).fetchone()
            has_v1_truth = bool(legacy_row[0]) or bool(
                self._selected_hardware_ids(conn, project_id)
            )
            if not has_v1_truth:
                conn.rollback()
                return

            self._sync_capability_adapters(conn)
            state = self._project_state(
                conn,
                project_id,
                project_version_override=1,
            )
            version_id = _id("pver")
            now = _now()
            validation_summary = [
                {
                    "code": "V1_BASELINE_IMPORTED",
                    "severity": "PASS",
                    "message": "已从现有 V1 项目事实建立 V2 只读基线。",
                }
            ]
            conn.execute(
                """
                INSERT INTO project_versions (
                  id, project_id, version, state_hash, change_set_id,
                  capability_snapshot_hash, artifact_version_ids_json,
                  validation_summary_json, created_at
                ) VALUES (?, ?, 1, ?, NULL, ?, ?, ?, ?)
                """,
                (
                    version_id,
                    project_id,
                    state["projectionHash"],
                    self._capability_snapshot_hash(conn, project_id),
                    _dump(self._active_artifact_version_ids(conn, project_id)),
                    _dump(validation_summary),
                    now,
                ),
            )
            self._store_snapshot(conn, state)
            self._append_event(
                conn,
                project_id=project_id,
                event_type="V1_BASELINE_IMPORTED",
                change_set_id=None,
                project_version=1,
                payload={"versionId": version_id, "stateHash": state["projectionHash"]},
            )
            conn.commit()

    def _store_snapshot(self, conn: sqlite3.Connection, state: dict[str, Any]) -> None:
        conn.execute(
            """
            INSERT INTO project_state_snapshots (
              id, project_id, project_version, schema_version, projection_json,
              projection_hash, projected_at
            ) VALUES (?, ?, ?, 1, ?, ?, ?)
            ON CONFLICT(project_id, project_version) DO UPDATE SET
              projection_json = excluded.projection_json,
              projection_hash = excluded.projection_hash,
              projected_at = excluded.projected_at
            """,
            (
                _id("pstate"),
                state["projectId"],
                state["projectVersion"],
                _dump(state),
                state["projectionHash"],
                state["projectedAt"],
            ),
        )

    def _append_event(
        self,
        conn: sqlite3.Connection,
        *,
        project_id: str,
        event_type: str,
        change_set_id: str | None,
        project_version: int,
        payload: dict[str, Any],
    ) -> None:
        row = conn.execute(
            "SELECT COALESCE(MAX(sequence), 0) + 1 FROM project_events WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        sequence = int(row[0])
        conn.execute(
            """
            INSERT INTO project_events (
              id, project_id, sequence, event_type, change_set_id,
              project_version, payload_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _id("pevt"),
                project_id,
                sequence,
                event_type,
                change_set_id,
                project_version,
                _dump(payload),
                _now(),
            ),
        )

    def _change_set_row(
        self, conn: sqlite3.Connection, project_id: str, change_set_id: str
    ) -> sqlite3.Row:
        row = conn.execute(
            """
            SELECT * FROM project_change_sets WHERE id = ? AND project_id = ?
            """,
            (change_set_id, project_id),
        ).fetchone()
        if row is None:
            raise ProjectKernelError("CHANGE_SET_NOT_FOUND", "变更集不存在。", status_code=404)
        return row

    def _current_version(self, conn: sqlite3.Connection, project_id: str) -> int:
        row = conn.execute(
            "SELECT COALESCE(MAX(version), 0) FROM project_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()
        return int(row[0])

    def _active_artifact_version_ids(
        self, conn: sqlite3.Connection, project_id: str
    ) -> list[str]:
        return [
            str(row[0])
            for row in conn.execute(
                """
                SELECT current_version_id FROM artifacts
                WHERE project_id = ? AND current_version_id IS NOT NULL
                  AND status NOT IN ('ARCHIVED', 'REJECTED')
                ORDER BY id
                """,
                (project_id,),
            ).fetchall()
        ]

    def _capability_snapshot_hash(self, conn: sqlite3.Connection, project_id: str) -> str:
        rows = conn.execute(
            """
            SELECT c.id, c.revision, c.status FROM project_capability_bindings b
            JOIN capabilities c ON c.id = b.capability_id
            WHERE b.project_id = ? AND b.unbound_at IS NULL ORDER BY c.id
            """,
            (project_id,),
        ).fetchall()
        return _hash([[str(item) for item in row] for row in rows])

    def _risk_level(self, operations: Iterable[Any]) -> ChangeSetRiskLevel:
        operation_names = {item.op for item in operations}
        if "MARK_ARTIFACT_OUTDATED" in operation_names:
            return ChangeSetRiskLevel.HIGH
        if operation_names & {"REMOVE_FACT", "UNBIND_CAPABILITY"}:
            return ChangeSetRiskLevel.MEDIUM
        return ChangeSetRiskLevel.LOW

    def _change_set_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "projectId": str(row["project_id"]),
            "baseProjectVersion": int(row["base_project_version"]),
            "authorType": str(row["author_type"]),
            "ownerDomain": str(row["owner_domain"]),
            "intentSummary": str(row["intent_summary"]),
            "operations": _load(row["operations_json"], []),
            "affectedFacts": _load(row["affected_facts_json"], []),
            "affectedArtifacts": _load(row["affected_artifacts_json"], []),
            "capabilityBindings": _load(row["capability_bindings_json"], []),
            "validationResults": _load(row["validation_results_json"], []),
            "riskLevel": str(row["risk_level"]),
            "confirmationPolicy": str(row["confirmation_policy"]),
            "status": str(row["status"]),
            "createdAt": str(row["created_at"]),
            "committedAt": str(row["committed_at"]) if row["committed_at"] else None,
        }

    def _version_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "projectId": str(row["project_id"]),
            "version": int(row["version"]),
            "stateHash": str(row["state_hash"]),
            "changeSetId": str(row["change_set_id"]) if row["change_set_id"] else None,
            "capabilitySnapshotHash": str(row["capability_snapshot_hash"]),
            "artifactVersionIds": _load(row["artifact_version_ids_json"], []),
            "validationSummary": _load(row["validation_summary_json"], []),
            "createdAt": str(row["created_at"]),
        }

    def _release_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "projectId": str(row["project_id"]),
            "projectVersionId": str(row["project_version_id"]),
            "name": str(row["name"]),
            "manifestHash": str(row["manifest_hash"]),
            "artifactVersionIds": _load(row["artifact_version_ids_json"], []),
            "unverifiedItems": _load(row["unverified_items_json"], []),
            "notes": str(row["notes"]),
            "createdAt": str(row["created_at"]),
        }

    def _capability_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": str(row["id"]),
            "kind": str(row["kind"]),
            "status": str(row["status"]),
            "name": str(row["name"]),
            "version": str(row["version"]),
            "sourceType": str(row["source_type"]),
            "sourceId": str(row["source_id"]),
            "revision": str(row["revision"]),
            "hostRequirements": _load(row["host_requirements_json"], []),
            "riskLevel": str(row["risk_level"]),
            "metadata": _load(row["metadata_json"], {}),
        }

    def _table_exists(self, conn: sqlite3.Connection, table: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name = ?", (table,)
            ).fetchone()
            is not None
        )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _validation(valid: bool, code: str, pass_message: str, fail_message: str) -> dict[str, str]:
    return {
        "code": code,
        "severity": "PASS" if valid else "FAIL",
        "message": pass_message if valid else fail_message,
    }


def _human_fact_label(key: str) -> str:
    labels = {
        "preferred_hardware": "项目硬件",
        "delivery_track": "交付路线",
        "project_mode": "项目模式",
        "initial_idea": "原始创意",
    }
    if key in labels:
        return labels[key]
    if key.startswith("q_") and key[2:].isdigit():
        return f"需求确认 {key[2:]}"
    cleaned = key.replace("_", " ").strip()
    return cleaned or "已确认事实"


def _human_fact_value(value: Any) -> str:
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "是" if value else "否"
    if isinstance(value, (int, float, str)):
        return str(value)
    if isinstance(value, list):
        return "、".join(_human_fact_value(item) for item in value) or "—"
    if isinstance(value, dict):
        selected = value.get("selectedOptionIds")
        text_input = value.get("textInput")
        parts = [str(item) for item in selected] if isinstance(selected, list) else []
        if isinstance(text_input, str) and text_input.strip():
            parts.append(text_input.strip())
        return "、".join(parts) or "已确认"
    return str(value)


def _load(value: Any, default: Any) -> Any:
    if value in {None, ""}:
        return default
    try:
        return json.loads(str(value))
    except (TypeError, ValueError):
        return default


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _hash(value: Any) -> str:
    return hashlib.sha256(_dump(value).encode("utf-8")).hexdigest()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
