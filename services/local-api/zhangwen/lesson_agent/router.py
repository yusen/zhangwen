"""Lesson Agent HTTP routes."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from zhangwen.config import settings
from zhangwen.lesson_agent.generator import (
    normalize_grade_band,
    normalize_lesson_hours,
    validate_and_package_lesson,
)
from zhangwen.lesson_agent.models import (
    ConfirmLessonRequest,
    GenerateLessonRequest,
    LessonRunResponse,
    RejectLessonRequest,
)
from zhangwen.lesson_agent.repository import LessonRepository
from zhangwen.lesson_agent.service import LessonGenerationService
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.specs.models import SpecRunStatus
from zhangwen.specs.repository import SpecRepository
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy

router = APIRouter(prefix="/api/projects", tags=["lesson-agent"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


@router.get("/{project_id}/lesson/current", response_model=LessonRunResponse)
async def get_current_lesson(project_id: str) -> LessonRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    lesson = LessonRepository(repo.db_path).get_current_lesson(project_id)
    if lesson is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "LESSON_NOT_FOUND",
                "message": "当前项目还没有教案。",
                "retryable": False,
            },
        )
    return LessonRunResponse(lessonRun=lesson)


@router.post("/{project_id}/lesson/generate", response_model=LessonRunResponse)
async def generate_lesson(
    project_id: str,
    request: GenerateLessonRequest,
) -> LessonRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    spec = SpecRepository(repo.db_path).get_spec(project_id, request.specRunId)
    if spec.status != SpecRunStatus.APPROVED:
        raise _unprocessable(
            "LESSON_REQUIRES_APPROVED_SPEC",
            "只有已确认 Spec 可以生成教案。",
        )
    proposal = ProposalRepository(repo.db_path).get_proposal(project_id, spec.proposalId)
    try:
        config, api_key = _llm_config()
        grade_band = normalize_grade_band(request.gradeBand)
        lesson_hours = normalize_lesson_hours(request.lessonHours)
        route = ModelRouter(repo.db_path).route(
            agent_id="lesson_generator",
            task_kind="lesson",
            strategy=ModelRouteStrategy.QUALITY_FIRST,
        )
        draft = await LessonGenerationService(provider_factory()).generate(
            spec=spec,
            proposal=proposal,
            grade_band=grade_band,
            lesson_hours=lesson_hours,
            config=config,
            api_key=api_key,
            model=route.model,
        )
        generated = validate_and_package_lesson(
            draft=draft,
            grade_band=grade_band,
            lesson_hours=lesson_hours,
        )
        lesson = LessonRepository(repo.db_path).create_from_generated(
            project_id=project_id,
            spec=spec,
            proposal=proposal,
            generated=generated,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except ValueError as exc:
        raise _unprocessable("LESSON_OUTPUT_INVALID", str(exc)) from exc
    return LessonRunResponse(lessonRun=lesson)


@router.post("/{project_id}/lesson/confirm", response_model=LessonRunResponse)
async def confirm_lesson(
    project_id: str,
    request: ConfirmLessonRequest,
) -> LessonRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        lesson = LessonRepository(repo.db_path).confirm_lesson(
            project_id,
            request.lessonRunId,
        )
    except ValueError as exc:
        raise _unprocessable("LESSON_CONFIRM_FAILED", str(exc)) from exc
    return LessonRunResponse(lessonRun=lesson)


@router.post("/{project_id}/lesson/reject", response_model=LessonRunResponse)
async def reject_lesson(
    project_id: str,
    request: RejectLessonRequest,
) -> LessonRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        lesson = LessonRepository(repo.db_path).reject_lesson(
            project_id,
            request.lessonRunId,
            request.reason,
        )
    except ValueError as exc:
        raise _unprocessable("LESSON_REJECT_FAILED", str(exc)) from exc
    return LessonRunResponse(lessonRun=lesson)


def _project_repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _llm_config():
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
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
