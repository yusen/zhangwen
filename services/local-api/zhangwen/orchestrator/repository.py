"""SQLite repository for execution plans and task nodes."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from zhangwen.orchestrator.models import (
    ExecutionPlan,
    TaskLogEntry,
    TaskNode,
    TaskStatus,
)


class OrchestratorRepository:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def create_plan(
        self,
        project_id: str,
        proposal_id: str,
        node_specs: list[dict[str, Any]],
    ) -> ExecutionPlan:
        now = _now()
        plan_id = _id("plan")
        id_map = {
            str(spec["id"]): f"{plan_id}_{spec['id']}"
            for spec in node_specs
        }
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO execution_plans (
                  id, project_id, proposal_id, status, created_at, updated_at,
                  started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    plan_id,
                    project_id,
                    proposal_id,
                    TaskStatus.QUEUED.value,
                    now,
                    now,
                ),
            )
            for spec in node_specs:
                node_id = id_map[str(spec["id"])]
                dependencies = [
                    id_map[str(dep)]
                    for dep in spec.get("dependencies", [])
                ]
                conn.execute(
                    """
                    INSERT INTO task_nodes (
                      id, plan_id, project_id, agent_id, title, description,
                      status, dependencies_json, attempts, max_attempts,
                      requires_approval, logs_json, error, created_at,
                      updated_at, started_at, completed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, NULL, ?, ?, NULL, NULL)
                    """,
                    (
                        node_id,
                        plan_id,
                        project_id,
                        str(spec["agentId"]),
                        str(spec["title"]),
                        str(spec["description"]),
                        TaskStatus.QUEUED.value,
                        json.dumps(dependencies, ensure_ascii=False),
                        int(spec.get("maxAttempts", 2)),
                        1 if bool(spec.get("requiresApproval", False)) else 0,
                        json.dumps(
                            [
                                _log("INFO", "任务已加入执行计划。").model_dump(
                                    mode="json"
                                )
                            ],
                            ensure_ascii=False,
                        ),
                        now,
                        now,
                    ),
                )
            row = conn.execute(
                "SELECT * FROM execution_plans WHERE id = ? AND project_id = ?",
                (plan_id, project_id),
            ).fetchone()
            return self._to_plan(conn, row)

    def get_current_plan(self, project_id: str) -> ExecutionPlan | None:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT * FROM execution_plans
                WHERE project_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (project_id,),
            ).fetchone()
            return self._to_plan(conn, row) if row else None

    def get_plan(self, project_id: str, plan_id: str) -> ExecutionPlan:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM execution_plans WHERE id = ? AND project_id = ?",
                (plan_id, project_id),
            ).fetchone()
            if row is None:
                raise ValueError("执行计划不存在。")
            return self._to_plan(conn, row)

    def save_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE execution_plans
                SET status = ?, updated_at = ?, started_at = ?, completed_at = ?
                WHERE id = ? AND project_id = ?
                """,
                (
                    plan.status.value,
                    plan.updatedAt,
                    plan.startedAt,
                    plan.completedAt,
                    plan.id,
                    plan.projectId,
                ),
            )
            for node in plan.nodes:
                conn.execute(
                    """
                    UPDATE task_nodes
                    SET status = ?, attempts = ?, max_attempts = ?,
                        requires_approval = ?, logs_json = ?, error = ?,
                        updated_at = ?, started_at = ?, completed_at = ?
                    WHERE id = ? AND plan_id = ?
                    """,
                    (
                        node.status.value,
                        node.attempts,
                        node.maxAttempts,
                        1 if node.requiresApproval else 0,
                        json.dumps(
                            [log.model_dump(mode="json") for log in node.logs],
                            ensure_ascii=False,
                        ),
                        node.error,
                        node.updatedAt,
                        node.startedAt,
                        node.completedAt,
                        node.id,
                        plan.id,
                    ),
                )
            row = conn.execute(
                "SELECT * FROM execution_plans WHERE id = ? AND project_id = ?",
                (plan.id, plan.projectId),
            ).fetchone()
            return self._to_plan(conn, row)

    def _to_plan(self, conn: sqlite3.Connection, row: sqlite3.Row) -> ExecutionPlan:
        node_rows = conn.execute(
            """
            SELECT * FROM task_nodes
            WHERE plan_id = ?
            ORDER BY created_at ASC
            """,
            (row["id"],),
        ).fetchall()
        return ExecutionPlan(
            id=row["id"],
            projectId=row["project_id"],
            proposalId=row["proposal_id"],
            status=TaskStatus(row["status"]),
            nodes=[_to_node(node_row) for node_row in node_rows],
            createdAt=row["created_at"],
            updatedAt=row["updated_at"],
            startedAt=row["started_at"],
            completedAt=row["completed_at"],
        )


def _to_node(row: sqlite3.Row) -> TaskNode:
    return TaskNode(
        id=row["id"],
        planId=row["plan_id"],
        projectId=row["project_id"],
        agentId=row["agent_id"],
        title=row["title"],
        description=row["description"],
        status=TaskStatus(row["status"]),
        dependencies=json.loads(row["dependencies_json"]),
        attempts=int(row["attempts"]),
        maxAttempts=int(row["max_attempts"]),
        requiresApproval=bool(row["requires_approval"]),
        logs=[TaskLogEntry(**item) for item in json.loads(row["logs_json"])],
        error=row["error"],
        createdAt=row["created_at"],
        updatedAt=row["updated_at"],
        startedAt=row["started_at"],
        completedAt=row["completed_at"],
    )


def add_log(node: TaskNode, level: str, message: str) -> None:
    node.logs.append(_log(level, message))
    node.updatedAt = _now()


def touch_plan(plan: ExecutionPlan) -> None:
    plan.updatedAt = _now()


def _log(level: str, message: str) -> TaskLogEntry:
    return TaskLogEntry(
        id=_id("log"),
        level=level,
        message=message,
        createdAt=_now(),
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
