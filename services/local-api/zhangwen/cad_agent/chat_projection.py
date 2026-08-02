"""Server-owned projection of CAD state into the originating chat message."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.cad_agent.models import CadRun


CAD_ARTIFACT_PAYLOAD_TYPE = "cad_artifact"


def cad_artifact_payload(cad_run: CadRun) -> dict[str, object]:
    """Build the only CAD chat payload accepted from the local runtime."""

    return {
        "type": CAD_ARTIFACT_PAYLOAD_TYPE,
        "cadRunId": cad_run.id,
        "artifactId": cad_run.artifactId,
        "artifactVersionId": cad_run.artifactVersionId,
        "version": cad_run.version,
        "status": cad_run.status.value,
        "title": "结构件 CAD 模型",
        "summary": _cad_summary(cad_run),
    }


def sync_cad_message_projection(db_path: Path, cad_run: CadRun) -> bool:
    """Persist a terminal or intermediate CadRun state on its source message.

    The CAD Job coordinator and confirm/reject routes call this hook after a
    durable state transition. It never accepts provider-generated identifiers.
    """

    if cad_run.sourceMessageId is None:
        return False
    now = datetime.now(UTC).isoformat()
    payload_json = json.dumps(cad_artifact_payload(cad_run), ensure_ascii=False)
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        cursor = conn.execute(
            """
            UPDATE messages
            SET structured_payload_json = ?, updated_at = ?
            WHERE id = ? AND project_id = ? AND role = 'assistant'
            """,
            (payload_json, now, cad_run.sourceMessageId, cad_run.projectId),
        )
        if cursor.rowcount != 1:
            return False
        conn.execute(
            "UPDATE projects SET updated_at = ? WHERE id = ?",
            (now, cad_run.projectId),
        )
    return True


def _cad_summary(cad_run: CadRun) -> str:
    design_state = cad_run.designState
    if isinstance(design_state, dict):
        summary = design_state.get("summary")
        if isinstance(summary, str) and summary.strip():
            return summary.strip()
    failed_check = next(
        (check for check in cad_run.validation.checks if check.severity == "FAIL"),
        None,
    )
    if failed_check is not None:
        return failed_check.message
    return f"{cad_run.templateKind.value} 参数化结构 v{cad_run.version}"
