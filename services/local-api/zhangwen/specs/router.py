"""Spec Agent HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.hardware.hardware_skills import (
    HardwareSkillNotFoundError,
    HardwareSkillValidationError,
)
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.settings.models import ModelWorkload
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.models import ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalStatus
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.specs.models import (
    ConfirmSpecRequest,
    GenerateSpecRequest,
    RejectSpecRequest,
    SpecRunResponse,
)
from zhangwen.specs.repository import SpecRepository
from zhangwen.specs.workflow import (
    FormalSpecHardwareError,
    generate_formal_project_spec,
)
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy

router = APIRouter(prefix="/api/projects", tags=["specs"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


@router.get("/{project_id}/spec/current", response_model=SpecRunResponse)
async def get_current_spec(project_id: str) -> SpecRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    spec = SpecRepository(repo.db_path).get_current_spec(project_id)
    if spec is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SPEC_NOT_FOUND",
                "message": "当前项目还没有工程规格。",
                "retryable": False,
            },
        )
    return SpecRunResponse(spec=spec)


@router.post("/{project_id}/spec/generate", response_model=SpecRunResponse)
async def generate_spec(
    project_id: str,
    request: GenerateSpecRequest,
) -> SpecRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    proposal = ProposalRepository(repo.db_path).get_proposal(project_id, request.proposalId)
    if proposal.status != ProposalStatus.APPROVED:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "SPEC_REQUIRES_APPROVED_PROPOSAL",
                "message": "只有已确认立项书可以生成工程规格。",
                "retryable": False,
            },
        )
    try:
        config, api_key = _llm_config()
        route = ModelRouter(repo.db_path).route(
            agent_id="spec_generator",
            task_kind="spec",
            strategy=ModelRouteStrategy.QUALITY_FIRST,
        )
        spec = await generate_formal_project_spec(
            repo=repo,
            project_id=project_id,
            proposal=proposal,
            provider=provider_factory(),
            config=config,
            api_key=api_key,
            model=route.model,
        )
    except (
        FormalSpecHardwareError,
        HardwareSkillNotFoundError,
        HardwareSkillValidationError,
    ) as exc:
        raise _unprocessable(
            "SPEC_HARDWARE_SKILL_INVALID",
            "项目硬件 Skill 不存在、未激活或未通过校验，请先修正硬件库。",
        ) from exc
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    _update_stage(repo, project_id, ProjectStage.IMPLEMENTING)
    return SpecRunResponse(spec=spec)


@router.post("/{project_id}/spec/confirm", response_model=SpecRunResponse)
async def confirm_spec(
    project_id: str,
    request: ConfirmSpecRequest,
) -> SpecRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        spec = SpecRepository(repo.db_path).confirm_spec(project_id, request.specRunId)
    except ValueError as exc:
        raise _unprocessable("SPEC_CONFIRM_FAILED", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.IMPLEMENTING)
    return SpecRunResponse(spec=spec)


@router.post("/{project_id}/spec/reject", response_model=SpecRunResponse)
async def reject_spec(
    project_id: str,
    request: RejectSpecRequest,
) -> SpecRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        spec = SpecRepository(repo.db_path).reject_spec(
            project_id,
            request.specRunId,
            request.reason,
        )
    except ValueError as exc:
        raise _unprocessable("SPEC_REJECT_FAILED", str(exc)) from exc
    return SpecRunResponse(spec=spec)


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _llm_config():
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
        workload=ModelWorkload.ENGINEERING,
    )


def _unprocessable(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=422,
        detail={
            "code": code,
            "message": message,
            "retryable": False,
        },
    )


def _update_stage(repo: ProjectRepository, project_id: str, stage: ProjectStage) -> None:
    from datetime import UTC, datetime

    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, now, project_id),
        )
