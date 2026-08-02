from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.skills.models import SkillPermission, SkillRunStatus
from zhangwen.skills.registry import built_in_skills
from zhangwen.skills.runtime import (
    CadBuildEnqueueRequest,
    CadBuildEnqueueResult,
    SkillRuntime,
    validate_skill_permissions,
)


def test_only_parametric_modeling_owns_cad_build_tool() -> None:
    owners = [
        skill.id
        for skill in built_in_skills()
        if "cad.build" in skill.requiredTools
    ]
    assert owners == ["parametric-modeling"]


def test_cad_build_tool_requires_run_and_artifact_permissions() -> None:
    skill = next(item for item in built_in_skills() if item.id == "parametric-modeling")
    validate_skill_permissions(skill)

    missing_run_cad = skill.model_copy(
        update={"permissions": [SkillPermission.READ_PROJECT]}
    )
    with pytest.raises(ValueError, match="RUN_CAD"):
        validate_skill_permissions(missing_run_cad)


@pytest.mark.asyncio
async def test_cad_build_handler_requires_confirmation_and_uses_server_payload(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="参数化外壳",
        project_name="CAD Skill",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    calls: list[CadBuildEnqueueRequest] = []

    def enqueue(request: CadBuildEnqueueRequest) -> CadBuildEnqueueResult:
        calls.append(request)
        return CadBuildEnqueueResult(
            cadJobId="cadjob_confirmed_1",
            cadRunId=request.cadRunId,
            status="QUEUED",
        )

    runtime = SkillRuntime.with_cad_build(repository.db_path, enqueue)
    payload = {
        "projectId": workspace.project.id,
        "cadRunId": "cad_server_owned_1",
        "clientRequestId": "confirm:cad_server_owned_1",
    }

    awaiting = await runtime.run(
        project_id=workspace.project.id,
        skill_id="parametric-modeling",
        payload=payload,
        confirmed=False,
        requesting_expert=ExpertType.STRUCTURE_ENGINEER,
    )
    assert awaiting.status == SkillRunStatus.AWAITING_CONFIRMATION
    assert calls == []

    completed = await runtime.run(
        project_id=workspace.project.id,
        skill_id="parametric-modeling",
        payload=payload,
        confirmed=True,
        requesting_expert=ExpertType.STRUCTURE_ENGINEER,
    )
    assert completed.status == SkillRunStatus.COMPLETED
    assert completed.output == {
        "cadJobId": "cadjob_confirmed_1",
        "cadRunId": "cad_server_owned_1",
        "status": "QUEUED",
    }
    assert calls == [CadBuildEnqueueRequest.model_validate(payload)]
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM tool_runs").fetchone()[0] == 1


@pytest.mark.asyncio
async def test_cad_build_rejects_cross_project_payload_before_enqueue(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="参数化外壳",
        project_name="CAD Skill project scope",
        initial_expert=ExpertType.STRUCTURE_ENGINEER,
        participating_experts=[ExpertType.STRUCTURE_ENGINEER],
    )
    calls: list[CadBuildEnqueueRequest] = []
    runtime = SkillRuntime.with_cad_build(
        repository.db_path,
        lambda request: calls.append(request) or {
            "cadJobId": "cadjob_never",
            "cadRunId": request.cadRunId,
            "status": "QUEUED",
        },
    )

    with pytest.raises(ValueError, match="projectId does not match"):
        await runtime.run(
            project_id=workspace.project.id,
            skill_id="parametric-modeling",
            payload={
                "projectId": "project_other",
                "cadRunId": "cad_server_owned_1",
            },
            confirmed=True,
            requesting_expert=ExpertType.STRUCTURE_ENGINEER,
        )
    assert calls == []
