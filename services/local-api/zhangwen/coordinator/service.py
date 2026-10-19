"""Deterministic project coordinator state machine."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.projects.migrations import migrate
from zhangwen.projects.models import (
    DomainTaskStatus,
    ExpertType,
    ExpertWorkspaceStatus,
    Handoff,
    HandoffStatus,
    PendingItem,
    PendingItemPriority,
    PendingItemStatus,
    ProjectTask,
    ProjectExpertStatus,
    SharedFact,
    SharedFactStatus,
)


PRIORITY_WEIGHT: dict[PendingItemPriority, int] = {
    PendingItemPriority.SAFETY: 600,
    PendingItemPriority.BLOCKING: 500,
    PendingItemPriority.CONFLICT: 400,
    PendingItemPriority.CONFIRMATION: 300,
    PendingItemPriority.MISSING_INPUT: 200,
    PendingItemPriority.NORMAL: 100,
}

HANDOFF_TRANSITIONS: dict[HandoffStatus, set[HandoffStatus]] = {
    HandoffStatus.PROPOSED: {
        HandoffStatus.ACCEPTED,
        HandoffStatus.REJECTED,
        HandoffStatus.CANCELLED,
    },
    HandoffStatus.ACCEPTED: {
        HandoffStatus.IN_PROGRESS,
        HandoffStatus.CANCELLED,
    },
    HandoffStatus.IN_PROGRESS: {
        HandoffStatus.COMPLETED,
        HandoffStatus.CANCELLED,
    },
    HandoffStatus.COMPLETED: set(),
    HandoffStatus.REJECTED: set(),
    HandoffStatus.CANCELLED: set(),
}

TASK_TRANSITIONS: dict[DomainTaskStatus, set[DomainTaskStatus]] = {
    DomainTaskStatus.QUEUED: {
        DomainTaskStatus.READY,
        DomainTaskStatus.BLOCKED,
        DomainTaskStatus.CANCELLED,
    },
    DomainTaskStatus.READY: {
        DomainTaskStatus.RUNNING,
        DomainTaskStatus.BLOCKED,
        DomainTaskStatus.CANCELLED,
    },
    DomainTaskStatus.RUNNING: {
        DomainTaskStatus.AWAITING_USER,
        DomainTaskStatus.COMPLETED,
        DomainTaskStatus.FAILED,
        DomainTaskStatus.BLOCKED,
        DomainTaskStatus.CANCELLED,
    },
    DomainTaskStatus.BLOCKED: {
        DomainTaskStatus.READY,
        DomainTaskStatus.CANCELLED,
    },
    DomainTaskStatus.AWAITING_USER: {
        DomainTaskStatus.READY,
        DomainTaskStatus.RUNNING,
        DomainTaskStatus.CANCELLED,
    },
    DomainTaskStatus.COMPLETED: set(),
    DomainTaskStatus.FAILED: set(),
    DomainTaskStatus.CANCELLED: set(),
}


class ProjectCoordinatorService:
    """Coordinates shared project state without invoking LLMs or tools."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            migrate(conn)

    def propose_shared_fact(
        self,
        *,
        project_id: str,
        field: str,
        value: object,
        source_type: str,
        source_id: str | None = None,
        source_expert_id: str | None = None,
        source_expert_type: ExpertType | str | None = None,
        key: str | None = None,
        affects_artifact_ids: list[str] | None = None,
        fact_id: str | None = None,
        created_at: str | None = None,
    ) -> SharedFact:
        now = created_at or _now()
        fact_key = key or field
        new_id = fact_id or _id("fact")
        with self._connect() as conn:
            self._ensure_project(conn, project_id)
            conn.execute(
                """
                INSERT INTO project_shared_facts (
                  id, project_id, field, key, value_json, status, source_type,
                  source_id, source_expert_id, proposed_by_expert_type,
                  confirmed_by, confirmed_at, superseded_by,
                  affects_artifact_ids_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    project_id,
                    field,
                    fact_key,
                    json.dumps(value, ensure_ascii=False),
                    SharedFactStatus.PROPOSED.value,
                    source_type,
                    source_id,
                    source_expert_id,
                    _expert_value(source_expert_type),
                    None,
                    None,
                    None,
                    json.dumps(affects_artifact_ids or [], ensure_ascii=False),
                    now,
                    now,
                ),
            )
            return _shared_fact(self._require_fact(conn, project_id, new_id))

    def record_llm_candidate_fact(
        self,
        *,
        project_id: str,
        field: str,
        value: object,
        proposed_by: ExpertType | str,
        reason: str | None = None,
        key: str | None = None,
    ) -> SharedFact:
        source_id = f"llm_candidate:{reason}" if reason else "llm_candidate"
        return self.propose_shared_fact(
            project_id=project_id,
            field=field,
            key=key,
            value=value,
            source_type="expert",
            source_id=source_id,
            source_expert_type=proposed_by,
        )

    def confirm_shared_fact(
        self,
        *,
        project_id: str,
        fact_id: str,
        confirmed_by: str,
    ) -> SharedFact:
        if not confirmed_by:
            raise ValueError("confirmed_by is required")
        now = _now()
        with self._connect() as conn:
            row = self._require_fact(conn, project_id, fact_id)
            status = SharedFactStatus(row["status"])
            if status != SharedFactStatus.PROPOSED:
                raise ValueError(f"cannot confirm shared fact in {status.value} state")
            fact_key = row["key"] or row["field"]
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = ?, superseded_by = ?, updated_at = ?
                WHERE project_id = ?
                  AND id <> ?
                  AND COALESCE(key, field) = ?
                  AND status = ?
                """,
                (
                    SharedFactStatus.SUPERSEDED.value,
                    fact_id,
                    now,
                    project_id,
                    fact_id,
                    fact_key,
                    SharedFactStatus.CONFIRMED.value,
                ),
            )
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = ?, confirmed_by = ?, confirmed_at = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    SharedFactStatus.CONFIRMED.value,
                    confirmed_by,
                    now,
                    now,
                    fact_id,
                    project_id,
                ),
            )
            return _shared_fact(self._require_fact(conn, project_id, fact_id))

    def reject_shared_fact(self, *, project_id: str, fact_id: str) -> SharedFact:
        now = _now()
        with self._connect() as conn:
            row = self._require_fact(conn, project_id, fact_id)
            status = SharedFactStatus(row["status"])
            if status == SharedFactStatus.REJECTED:
                return _shared_fact(row)
            if status != SharedFactStatus.PROPOSED:
                raise ValueError(f"cannot reject shared fact in {status.value} state")
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (SharedFactStatus.REJECTED.value, now, fact_id, project_id),
            )
            return _shared_fact(self._require_fact(conn, project_id, fact_id))

    def supersede_shared_fact(
        self,
        *,
        project_id: str,
        fact_id: str,
        superseded_by: str,
    ) -> SharedFact:
        if fact_id == superseded_by:
            raise ValueError("a shared fact cannot supersede itself")
        now = _now()
        with self._connect() as conn:
            row = self._require_fact(conn, project_id, fact_id)
            status = SharedFactStatus(row["status"])
            if status in {SharedFactStatus.REJECTED, SharedFactStatus.SUPERSEDED}:
                raise ValueError(f"cannot supersede shared fact in {status.value} state")
            self._require_fact(conn, project_id, superseded_by)
            conn.execute(
                """
                UPDATE project_shared_facts
                SET status = ?, superseded_by = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    SharedFactStatus.SUPERSEDED.value,
                    superseded_by,
                    now,
                    fact_id,
                    project_id,
                ),
            )
            return _shared_fact(self._require_fact(conn, project_id, fact_id))

    def list_shared_facts(self, project_id: str) -> list[SharedFact]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM project_shared_facts
                WHERE project_id = ?
                ORDER BY created_at ASC
                """,
                (project_id,),
            ).fetchall()
            return [_shared_fact(row) for row in rows]

    def create_pending_item(
        self,
        *,
        project_id: str,
        title: str,
        description: str,
        priority: PendingItemPriority,
        reason: str,
        affected_experts: list[ExpertType | str] | None = None,
        options: list[str] | None = None,
        critical_path: bool = False,
        item_id: str | None = None,
        created_at: str | None = None,
    ) -> PendingItem:
        now = created_at or _now()
        pending_id = item_id or _id("pending")
        affected = [_expert_value(item) for item in (affected_experts or [])]
        with self._connect() as conn:
            self._ensure_project(conn, project_id)
            conn.execute(
                """
                INSERT INTO project_pending_items (
                  id, project_id, title, description, priority, reason,
                  affected_experts_json, options_json, status, is_highlighted,
                  critical_path, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    pending_id,
                    project_id,
                    title,
                    description,
                    priority.value,
                    reason,
                    json.dumps(affected, ensure_ascii=False),
                    json.dumps(options or [], ensure_ascii=False),
                    PendingItemStatus.OPEN.value,
                    0,
                    1 if critical_path else 0,
                    now,
                    now,
                ),
            )
            self._refresh_highlighted_pending_item(conn, project_id)
            return _pending_item(self._require_pending_item(conn, project_id, pending_id))

    def record_llm_candidate_conflict(
        self,
        *,
        project_id: str,
        title: str,
        description: str,
        affected_experts: list[ExpertType | str],
        reason: str,
        critical_path: bool = False,
    ) -> PendingItem:
        return self.create_pending_item(
            project_id=project_id,
            title=title,
            description=description,
            priority=PendingItemPriority.CONFLICT,
            reason=reason,
            affected_experts=affected_experts,
            critical_path=critical_path,
        )

    def refresh_highlighted_pending_item(self, project_id: str) -> PendingItem | None:
        with self._connect() as conn:
            return self._refresh_highlighted_pending_item(conn, project_id)

    def resolve_pending_item(self, *, project_id: str, pending_item_id: str) -> PendingItem:
        return self._close_pending_item(
            project_id=project_id,
            pending_item_id=pending_item_id,
            status=PendingItemStatus.RESOLVED,
        )

    def dismiss_pending_item(self, *, project_id: str, pending_item_id: str) -> PendingItem:
        return self._close_pending_item(
            project_id=project_id,
            pending_item_id=pending_item_id,
            status=PendingItemStatus.DISMISSED,
        )

    def create_handoff(
        self,
        *,
        project_id: str,
        from_expert: ExpertType | str,
        to_expert: ExpertType | str,
        handoff_type: str,
        summary: str | None = None,
        confirmed_requirements: list[str] | None = None,
        shared_fact_ids: list[str] | None = None,
        related_artifacts: list[str] | None = None,
        required_outputs: list[str] | None = None,
        dependencies: list[str] | None = None,
        open_questions: list[str] | None = None,
        current_pending_item_id: str | None = None,
        handoff_id: str | None = None,
        created_at: str | None = None,
    ) -> Handoff:
        now = created_at or _now()
        from_value = _expert_value(from_expert)
        to_value = _expert_value(to_expert)
        new_id = handoff_id or _id("handoff")
        with self._connect() as conn:
            self._ensure_project(conn, project_id)
            self._ensure_project_expert(conn, project_id, from_value)
            self._ensure_project_expert(conn, project_id, to_value)
            conn.execute(
                """
                INSERT INTO project_handoffs (
                  id, project_id, from_expert_type, to_expert_type,
                  handoff_type, status, summary, confirmed_requirements_json,
                  shared_fact_ids_json, related_artifact_ids_json,
                  required_outputs_json, dependencies_json, open_questions_json,
                  current_pending_item_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    project_id,
                    from_value,
                    to_value,
                    handoff_type,
                    HandoffStatus.PROPOSED.value,
                    summary,
                    json.dumps(confirmed_requirements or [], ensure_ascii=False),
                    json.dumps(shared_fact_ids or [], ensure_ascii=False),
                    json.dumps(related_artifacts or [], ensure_ascii=False),
                    json.dumps(required_outputs or [], ensure_ascii=False),
                    json.dumps(dependencies or [], ensure_ascii=False),
                    json.dumps(open_questions or [], ensure_ascii=False),
                    current_pending_item_id,
                    now,
                    now,
                ),
            )
            return _handoff(self._require_handoff(conn, project_id, new_id))

    def transition_handoff(
        self,
        *,
        project_id: str,
        handoff_id: str,
        next_status: HandoffStatus,
    ) -> Handoff:
        now = _now()
        with self._connect() as conn:
            row = self._require_handoff(conn, project_id, handoff_id)
            current = HandoffStatus(row["status"])
            if current == next_status:
                return _handoff(row)
            if next_status not in HANDOFF_TRANSITIONS[current]:
                raise ValueError(
                    f"invalid handoff transition {current.value} -> {next_status.value}"
                )
            conn.execute(
                """
                UPDATE project_handoffs
                SET status = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (next_status.value, now, handoff_id, project_id),
            )
            return _handoff(self._require_handoff(conn, project_id, handoff_id))

    def create_task(
        self,
        *,
        project_id: str,
        title: str,
        description: str,
        owner_expert: ExpertType | str,
        status: DomainTaskStatus = DomainTaskStatus.QUEUED,
        dependency_task_ids: list[str] | None = None,
        artifact_ids: list[str] | None = None,
        current_pending_item_id: str | None = None,
        task_id: str | None = None,
        created_at: str | None = None,
    ) -> ProjectTask:
        now = created_at or _now()
        owner = _expert_value(owner_expert)
        new_id = task_id or _id("task")
        with self._connect() as conn:
            self._ensure_project(conn, project_id)
            self._ensure_project_expert(conn, project_id, owner)
            conn.execute(
                """
                INSERT INTO project_tasks (
                  id, project_id, title, description, owner_expert_type, status,
                  dependency_task_ids_json, artifact_ids_json,
                  current_pending_item_id, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    new_id,
                    project_id,
                    title,
                    description,
                    owner,
                    status.value,
                    json.dumps(dependency_task_ids or [], ensure_ascii=False),
                    json.dumps(artifact_ids or [], ensure_ascii=False),
                    current_pending_item_id,
                    now,
                    now,
                ),
            )
            return _task(self._require_task(conn, project_id, new_id))

    def transition_task(
        self,
        *,
        project_id: str,
        task_id: str,
        next_status: DomainTaskStatus,
    ) -> ProjectTask:
        now = _now()
        with self._connect() as conn:
            row = self._require_task(conn, project_id, task_id)
            current = DomainTaskStatus(row["status"])
            if current == next_status:
                return _task(row)
            if next_status not in TASK_TRANSITIONS[current]:
                raise ValueError(
                    f"invalid task transition {current.value} -> {next_status.value}"
                )
            conn.execute(
                """
                UPDATE project_tasks
                SET status = ?, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (next_status.value, now, task_id, project_id),
            )
            return _task(self._require_task(conn, project_id, task_id))

    def get_task(self, *, project_id: str, task_id: str) -> ProjectTask:
        with self._connect() as conn:
            return _task(self._require_task(conn, project_id, task_id))

    def refresh_expert_statuses(self, project_id: str) -> None:
        """Derive visible expert state from tasks, pending items and outdated artifacts."""
        with self._connect() as conn:
            self._ensure_project(conn, project_id)
            project = conn.execute(
                "SELECT active_expert_id FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            experts = conn.execute(
                """
                SELECT id, expert_type FROM project_experts
                WHERE project_id = ? AND removed_at IS NULL AND archived_legacy_thread = 0
                """,
                (project_id,),
            ).fetchall()
            pending = conn.execute(
                """
                SELECT priority, affected_experts_json FROM project_pending_items
                WHERE project_id = ? AND status = ?
                """,
                (project_id, PendingItemStatus.OPEN.value),
            ).fetchall()
            tasks = conn.execute(
                """
                SELECT owner_expert_type, status, title FROM project_tasks
                WHERE project_id = ?
                ORDER BY updated_at DESC
                """,
                (project_id,),
            ).fetchall()
            outdated = {
                str(row["owner_expert_type"])
                for row in conn.execute(
                    """
                    SELECT DISTINCT owner_expert_type FROM artifacts
                    WHERE project_id = ? AND domain_status = 'outdated'
                      AND owner_expert_type IS NOT NULL
                    """,
                    (project_id,),
                ).fetchall()
            }
            for expert in experts:
                expert_type = str(expert["expert_type"])
                affected_priorities = [
                    PendingItemPriority(row["priority"])
                    for row in pending
                    if expert_type in _json_list(row["affected_experts_json"])
                ]
                expert_tasks = [row for row in tasks if row["owner_expert_type"] == expert_type]
                current_task = str(expert_tasks[0]["title"]) if expert_tasks else None
                task_statuses = {str(row["status"]) for row in expert_tasks}
                if expert_type in outdated:
                    status = ProjectExpertStatus.BLOCKED
                    workspace_status = ExpertWorkspaceStatus.OUTDATED
                elif any(
                    priority
                    in {
                        PendingItemPriority.SAFETY,
                        PendingItemPriority.BLOCKING,
                        PendingItemPriority.CONFLICT,
                    }
                    for priority in affected_priorities
                ) or DomainTaskStatus.BLOCKED.value in task_statuses:
                    status = ProjectExpertStatus.BLOCKED
                    workspace_status = ExpertWorkspaceStatus.WAITING_DEPENDENCY
                elif any(
                    priority
                    in {
                        PendingItemPriority.CONFIRMATION,
                        PendingItemPriority.MISSING_INPUT,
                    }
                    for priority in affected_priorities
                ) or DomainTaskStatus.AWAITING_USER.value in task_statuses:
                    status = ProjectExpertStatus.WAITING_USER
                    workspace_status = ExpertWorkspaceStatus.AWAITING_USER
                elif DomainTaskStatus.RUNNING.value in task_statuses or project["active_expert_id"] == expert["id"]:
                    status = ProjectExpertStatus.WORKING
                    workspace_status = ExpertWorkspaceStatus.IN_PROGRESS
                elif expert_tasks and task_statuses <= {DomainTaskStatus.COMPLETED.value}:
                    status = ProjectExpertStatus.COMPLETED
                    workspace_status = ExpertWorkspaceStatus.COMPLETED
                else:
                    status = ProjectExpertStatus.IDLE
                    workspace_status = ExpertWorkspaceStatus.NOT_STARTED
                conn.execute(
                    """
                    UPDATE project_experts
                    SET status = ?, workspace_status = ?, current_task = COALESCE(?, current_task)
                    WHERE id = ?
                    """,
                    (status.value, workspace_status.value, current_task, expert["id"]),
                )

    def _close_pending_item(
        self,
        *,
        project_id: str,
        pending_item_id: str,
        status: PendingItemStatus,
    ) -> PendingItem:
        now = _now()
        with self._connect() as conn:
            self._require_pending_item(conn, project_id, pending_item_id)
            conn.execute(
                """
                UPDATE project_pending_items
                SET status = ?, is_highlighted = 0, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (status.value, now, pending_item_id, project_id),
            )
            self._refresh_highlighted_pending_item(conn, project_id)
            return _pending_item(self._require_pending_item(conn, project_id, pending_item_id))

    def _refresh_highlighted_pending_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
    ) -> PendingItem | None:
        rows = conn.execute(
            """
            SELECT * FROM project_pending_items
            WHERE project_id = ? AND status = ?
            """,
            (project_id, PendingItemStatus.OPEN.value),
        ).fetchall()
        selected: sqlite3.Row | None = None
        if rows:
            selected = sorted(rows, key=_pending_sort_key)[0]
        conn.execute(
            """
            UPDATE project_pending_items
            SET is_highlighted = 0
            WHERE project_id = ?
            """,
            (project_id,),
        )
        if selected is not None:
            conn.execute(
                """
                UPDATE project_pending_items
                SET is_highlighted = 1, updated_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (_now(), selected["id"], project_id),
            )
            selected = self._require_pending_item(conn, project_id, str(selected["id"]))
            return _pending_item(selected)
        return None

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_project(self, conn: sqlite3.Connection, project_id: str) -> None:
        row = conn.execute("SELECT id FROM projects WHERE id = ?", (project_id,)).fetchone()
        if row is None:
            raise ValueError("project not found")

    def _ensure_project_expert(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        expert_type: str,
    ) -> None:
        row = conn.execute(
            """
            SELECT id FROM project_experts
            WHERE project_id = ?
              AND expert_type = ?
              AND removed_at IS NULL
              AND archived_legacy_thread = 0
            LIMIT 1
            """,
            (project_id, expert_type),
        ).fetchone()
        if row is None:
            raise ValueError(f"expert {expert_type} is not active in project")

    def _require_fact(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        fact_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM project_shared_facts WHERE id = ? AND project_id = ?",
            (fact_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("shared fact not found")
        return row

    def _require_pending_item(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        pending_item_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM project_pending_items WHERE id = ? AND project_id = ?",
            (pending_item_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("pending item not found")
        return row

    def _require_handoff(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        handoff_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM project_handoffs WHERE id = ? AND project_id = ?",
            (handoff_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("handoff not found")
        return row

    def _require_task(
        self,
        conn: sqlite3.Connection,
        project_id: str,
        task_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM project_tasks WHERE id = ? AND project_id = ?",
            (task_id, project_id),
        ).fetchone()
        if row is None:
            raise ValueError("task not found")
        return row


def _shared_fact(row: sqlite3.Row) -> SharedFact:
    status = SharedFactStatus(row["status"])
    return SharedFact(
        id=row["id"],
        projectId=row["project_id"],
        field=row["field"],
        key=row["key"] or row["field"],
        value=json.loads(row["value_json"]),
        status=status,
        sourceType=row["source_type"],
        sourceId=row["source_id"],
        sourceExpertId=row["source_expert_id"],
        proposedBy=_coerce_expert(row["proposed_by_expert_type"]),
        confirmed=status == SharedFactStatus.CONFIRMED,
        confirmedBy=row["confirmed_by"],
        confirmedAt=row["confirmed_at"],
        supersededBy=row["superseded_by"],
        affectsArtifactIds=_json_list(row["affects_artifact_ids_json"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _pending_item(row: sqlite3.Row) -> PendingItem:
    return PendingItem(
        id=row["id"],
        projectId=row["project_id"],
        title=row["title"],
        description=row["description"],
        priority=PendingItemPriority(row["priority"]),
        reason=row["reason"],
        affectedExperts=[ExpertType(item) for item in _json_list(row["affected_experts_json"])],
        options=_json_list(row["options_json"]),
        status=PendingItemStatus(row["status"]),
        isHighlighted=bool(row["is_highlighted"]),
        criticalPath=bool(row["critical_path"]),
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _handoff(row: sqlite3.Row) -> Handoff:
    return Handoff(
        id=row["id"],
        projectId=row["project_id"],
        fromExpert=ExpertType(row["from_expert_type"]),
        toExpert=ExpertType(row["to_expert_type"]),
        handoffType=row["handoff_type"],
        status=HandoffStatus(row["status"]),
        summary=row["summary"],
        confirmedRequirements=_json_list(row["confirmed_requirements_json"]),
        sharedFactIds=_json_list(row["shared_fact_ids_json"]),
        relatedArtifacts=_json_list(row["related_artifact_ids_json"]),
        requiredOutputs=_json_list(row["required_outputs_json"]),
        dependencies=_json_list(row["dependencies_json"]),
        openQuestions=_json_list(row["open_questions_json"]),
        currentPendingItemId=row["current_pending_item_id"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _task(row: sqlite3.Row) -> ProjectTask:
    return ProjectTask(
        id=row["id"],
        projectId=row["project_id"],
        title=row["title"],
        description=row["description"],
        ownerExpert=ExpertType(row["owner_expert_type"]),
        status=DomainTaskStatus(row["status"]),
        dependencyTaskIds=_json_list(row["dependency_task_ids_json"]),
        artifactIds=_json_list(row["artifact_ids_json"]),
        currentPendingItemId=row["current_pending_item_id"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
    )


def _pending_sort_key(row: sqlite3.Row) -> tuple[int, int, str, int]:
    priority = PendingItemPriority(row["priority"])
    affected_count = len(_json_list(row["affected_experts_json"]))
    critical_path = 1 if row["critical_path"] else 0
    return (
        -PRIORITY_WEIGHT[priority],
        -affected_count,
        row["created_at"],
        -critical_path,
    )


def _coerce_expert(value: str | None) -> ExpertType | str | None:
    if value is None:
        return None
    try:
        return ExpertType(value)
    except ValueError:
        return value


def _expert_value(value: ExpertType | str | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, ExpertType):
        return value.value
    return ExpertType(value).value


def _json_list(raw_json: str | None) -> list[str]:
    if not raw_json:
        return []
    loaded = json.loads(raw_json)
    return [str(item) for item in loaded] if isinstance(loaded, list) else []


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
