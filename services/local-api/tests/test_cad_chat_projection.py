from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from zhangwen.cad_agent.chat_projection import (
    cad_artifact_payload,
    sync_cad_message_projection,
)
from zhangwen.cad_agent.models import (
    CadRun,
    CadRunStatus,
    CadTemplateKind,
    CadValidation,
)
from zhangwen.chat.router import _runtime_ui_payload
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


NOW = "2026-07-13T08:00:00+00:00"


@pytest.mark.parametrize(
    "status",
    [
        CadRunStatus.DRAFT,
        CadRunStatus.READY_FOR_REVIEW,
        CadRunStatus.APPROVED,
        CadRunStatus.FAILED,
    ],
)
def test_cad_chat_payload_is_derived_from_local_run(status: CadRunStatus) -> None:
    cad_run = _cad_run(status)

    payload = cad_artifact_payload(cad_run)

    assert payload == {
        "type": "cad_artifact",
        "cadRunId": "cad_projection_1",
        "artifactId": "artifact_cad_projection" if status != CadRunStatus.DRAFT else None,
        "artifactVersionId": "artifact_version_cad_projection"
        if status != CadRunStatus.DRAFT
        else None,
        "version": 2,
        "status": status.value,
        "title": "结构件 CAD 模型",
        "summary": "带盖参数化外壳",
    }


def test_runtime_payload_filters_provider_cad_artifact() -> None:
    provider_payload = {
        "type": "cad_artifact",
        "cadRunId": "provider_fake",
        "artifactId": "provider_fake_artifact",
    }

    assert _runtime_ui_payload(provider_payload, None, None) is None
    local_run = _cad_run(CadRunStatus.DRAFT)
    projected = _runtime_ui_payload(provider_payload, None, local_run)
    assert projected == cad_artifact_payload(local_run)
    assert projected["cadRunId"] != "provider_fake"


def test_sync_cad_projection_updates_only_originating_assistant_message(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="参数化外壳",
        project_name="CAD 投影",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    conversation_id = workspace.experts[0].conversationId
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            """
            INSERT INTO messages (
              id, conversation_id, project_id, role, content, reasoning_content,
              status, model, error_json, usage_json, structured_payload_json,
              metadata_json, created_at, updated_at
            ) VALUES ('msg_cad_projection', ?, ?, 'assistant', '结构草稿', NULL,
                      'COMPLETED', NULL, NULL, NULL, NULL, NULL, ?, ?)
            """,
            (conversation_id, workspace.project.id, NOW, NOW),
        )

    cad_run = _cad_run(CadRunStatus.READY_FOR_REVIEW).model_copy(
        update={
            "projectId": workspace.project.id,
            "sourceMessageId": "msg_cad_projection",
        }
    )
    assert sync_cad_message_projection(repository.db_path, cad_run) is True

    with sqlite3.connect(repository.db_path) as conn:
        raw_payload = conn.execute(
            "SELECT structured_payload_json FROM messages WHERE id = 'msg_cad_projection'"
        ).fetchone()[0]
    assert json.loads(raw_payload) == cad_artifact_payload(cad_run)

    missing_source = cad_run.model_copy(update={"sourceMessageId": "msg_other_project"})
    assert sync_cad_message_projection(repository.db_path, missing_source) is False


def _cad_run(status: CadRunStatus) -> CadRun:
    has_artifact = status != CadRunStatus.DRAFT
    return CadRun(
        id="cad_projection_1",
        projectId="project_projection_1",
        specRunId=None,
        templateKind=CadTemplateKind.BOX_WITH_LID,
        version=2,
        status=status,
        commandLabel="cadquery-deterministic",
        parameters=[],
        validation=CadValidation(ok=status != CadRunStatus.FAILED, checks=[]),
        files=[],
        artifactId="artifact_cad_projection" if has_artifact else None,
        artifactVersionId="artifact_version_cad_projection" if has_artifact else None,
        sourceMessageId="msg_cad_projection",
        generatedByExpertId="expert_structure_1",
        engineId="cadquery-deterministic",
        engineVersion="2.8.0",
        designState={"summary": "带盖参数化外壳"},
        latestJob=None,
        staleReason=None,
        createdAt=NOW,
        updatedAt=NOW,
        confirmedAt=NOW if status == CadRunStatus.APPROVED else None,
    )
