"""Project HTTP routes."""

from __future__ import annotations

import sqlite3

from fastapi import APIRouter, HTTPException, Query

from zhangwen.config import settings
from zhangwen.coordinator.service import ProjectCoordinatorService
from zhangwen.experts.entry_router import (
    EntryRouter,
    PreferredHardwareSummary,
    PreferredHardwareValidationCheck,
    PreferredHardwareValidationSummary,
    RouterOutput as EntryRouterOutput,
)
from zhangwen.hardware.models import (
    HardwareComponent,
    ValidationSeverity,
)
from zhangwen.hardware.hardware_skills import (
    HardwareSkillNotFoundError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
)
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.llm.development_fake import create_provider
from zhangwen.llm.contracts import LLMErrorCode
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.settings.models import ModelWorkload
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.errors import ProjectError, ProjectValidationError
from zhangwen.projects.models import (
    AddProjectExpertRequest,
    ArchiveProjectRequest,
    CreateProjectRequest,
    DuplicateProjectRequest,
    ExpertType,
    LegacyProjectClaimRequest,
    LegacyProjectClaimResponse,
    LegacyProjectClaimStatusResponse,
    PermanentDeleteProjectRequest,
    PermanentDeleteProjectResponse,
    ProjectListResponse,
    ProjectWorkspaceResponse,
    RemoveProjectExpertRequest,
    SaveDraftRequest,
    SuggestProjectRequest,
    SuggestProjectResponse,
    UpdateProjectHardwareRequest,
    UpdateProjectHardwareResponse,
    UpdateProjectRequest,
)
from zhangwen.projects.repository import ProjectRepository
from zhangwen.projects.lifecycle import ProjectLifecycleService
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy
from zhangwen.skills.runtime import SkillAuthorizationError, SkillRuntime

router = APIRouter(prefix="/api", tags=["projects"])
credential_store_factory = BackendCredentialStore
provider_factory = create_provider


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    include_archived: bool = Query(False, alias="includeArchived"),
) -> ProjectListResponse:
    repository = _repo()
    repository.normalize_stale_streaming()
    projects, active_project_id = repository.list_projects(
        include_archived=include_archived
    )
    return ProjectListResponse(projects=projects, activeProjectId=active_project_id)


@router.get(
    "/projects/legacy-claim/status",
    response_model=LegacyProjectClaimStatusResponse,
)
async def legacy_project_claim_status() -> LegacyProjectClaimStatusResponse:
    count, decided = _repo().legacy_claim_status()
    return LegacyProjectClaimStatusResponse(
        unclaimedProjectCount=count,
        decisionRecorded=decided,
    )


@router.post(
    "/projects/legacy-claim",
    response_model=LegacyProjectClaimResponse,
)
async def decide_legacy_project_claim(
    request: LegacyProjectClaimRequest,
) -> LegacyProjectClaimResponse:
    try:
        claimed = _repo().decide_legacy_claim(claim_all=request.claimAll)
        return LegacyProjectClaimResponse(claimedProjectCount=claimed)
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post("/projects", response_model=ProjectWorkspaceResponse, deprecated=True)
async def create_project(request: CreateProjectRequest) -> ProjectWorkspaceResponse:
    try:
        repository = _repo()
        preferred_hardware, preferred_hardware_validation = _resolve_selected_hardware(
            repository,
            request.selectedHardwareIds,
        )
        model_route = request.routerResult
        if model_route is None:
            model_route = await _route_project_idea_with_model(
                repository,
                request.initialIdea,
                request.initialExpert,
                preferred_hardware,
                preferred_hardware_validation,
            )
        workspace = repository.create_project_from_idea(
            idea=request.initialIdea,
            project_name=(request.name or model_route.projectName),
            initial_expert=request.initialExpert,
            participating_experts=(
                request.selectedExpertTypes or model_route.recommendedExperts
            ),
            selected_model=request.selectedModel,
            router_result=model_route,
            expert_selection_mode=request.expertSelectionMode,
            idempotency_key=request.idempotencyKey,
            selected_hardware_ids=request.selectedHardwareIds,
        )
        return ProjectWorkspaceResponse(workspace=workspace)
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post("/projects/suggest", response_model=SuggestProjectResponse, deprecated=True)
async def suggest_project(request: SuggestProjectRequest) -> SuggestProjectResponse:
    try:
        text = request.text or request.initialIdea or ""
        repository = _repo()
        preferred_hardware, preferred_hardware_validation = _resolve_selected_hardware(
            repository,
            request.selectedHardwareIds,
        )
        model_route = await _route_project_idea_with_model(
            repository,
            text,
            request.userSelectedExpert,
            preferred_hardware,
            preferred_hardware_validation,
        )
        suggestion = repository.suggest_project(
            text,
            request.userSelectedExpert,
            router_result=model_route,
        )
        selected_hardware_warnings = (
            [warning.message for warning in preferred_hardware_validation.warnings]
            if preferred_hardware_validation is not None
            and preferred_hardware_validation.overall == "WARNING"
            else []
        )
        if (
            preferred_hardware_validation is not None
            and preferred_hardware_validation.overall == "WARNING"
            and not selected_hardware_warnings
        ):
            selected_hardware_warnings = [preferred_hardware_validation.message]
        return SuggestProjectResponse(
            suggestion=suggestion.model_copy(
                update={"selectedHardwareWarnings": selected_hardware_warnings}
            )
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.get("/projects/{project_id}", response_model=ProjectWorkspaceResponse)
async def get_project(project_id: str) -> ProjectWorkspaceResponse:
    try:
        return ProjectWorkspaceResponse(workspace=_repo().get_workspace(project_id))
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post("/projects/{project_id}/open", response_model=ProjectWorkspaceResponse)
async def open_project(project_id: str) -> ProjectWorkspaceResponse:
    try:
        return ProjectWorkspaceResponse(workspace=_repo().open_project(project_id))
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/projects/{project_id}/experts/{project_expert_id}/activate",
    response_model=ProjectWorkspaceResponse,
)
async def activate_project_expert(
    project_id: str,
    project_expert_id: str,
) -> ProjectWorkspaceResponse:
    try:
        return ProjectWorkspaceResponse(
            workspace=_repo().set_active_expert(project_id, project_expert_id)
        )
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/projects/{project_id}/experts",
    response_model=ProjectWorkspaceResponse,
)
async def add_project_expert(
    project_id: str,
    request: AddProjectExpertRequest,
) -> ProjectWorkspaceResponse:
    try:
        return ProjectWorkspaceResponse(
            workspace=_repo().add_project_expert(
                project_id,
                request.expertType,
                activate=request.activate,
            )
        )
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/projects/{project_id}/experts/{project_expert_id}/remove",
    response_model=ProjectWorkspaceResponse,
)
async def remove_project_expert(
    project_id: str,
    project_expert_id: str,
    request: RemoveProjectExpertRequest,
) -> ProjectWorkspaceResponse:
    try:
        return ProjectWorkspaceResponse(
            workspace=_repo().remove_project_expert(
                project_id,
                project_expert_id,
                confirm_impact=request.confirmImpact,
            )
        )
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.patch("/projects/{project_id}", response_model=ProjectWorkspaceResponse)
async def update_project(
    project_id: str, request: UpdateProjectRequest
) -> ProjectWorkspaceResponse:
    try:
        workspace = _repo().update_project(
            project_id,
            name=request.name,
            selected_model=request.selectedModel,
        )
        return ProjectWorkspaceResponse(workspace=workspace)
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.put(
    "/projects/{project_id}/hardware",
    response_model=UpdateProjectHardwareResponse,
)
async def update_project_hardware(
    project_id: str,
    request: UpdateProjectHardwareRequest,
) -> UpdateProjectHardwareResponse:
    try:
        workspace, warnings = _repo().replace_preferred_hardware(
            project_id,
            request.selectedHardwareIds,
        )
        return UpdateProjectHardwareResponse(
            workspace=workspace,
            selectedHardwareWarnings=warnings,
        )
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post("/projects/{project_id}/archive", response_model=ProjectListResponse)
async def archive_project(
    project_id: str, request: ArchiveProjectRequest
) -> ProjectListResponse:
    try:
        projects, active_project_id = _repo().archive_project(project_id, request.archived)
        return ProjectListResponse(projects=projects, activeProjectId=active_project_id)
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post("/projects/{project_id}/restore", response_model=ProjectListResponse)
async def restore_project(project_id: str) -> ProjectListResponse:
    try:
        projects, active_project_id = _repo().restore_project(project_id)
        return ProjectListResponse(projects=projects, activeProjectId=active_project_id)
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/projects/{project_id}/duplicate",
    response_model=ProjectWorkspaceResponse,
)
async def duplicate_project(
    project_id: str,
    request: DuplicateProjectRequest,
) -> ProjectWorkspaceResponse:
    try:
        workspace = ProjectLifecycleService(settings.data_dir).duplicate(
            project_id,
            name=request.name,
        )
        return ProjectWorkspaceResponse(workspace=workspace)
    except (ProjectError, sqlite3.Error, OSError) as exc:
        if isinstance(exc, ProjectError):
            raise _http_error(exc) from exc
        raise _http_error(
            ProjectValidationError("项目复制失败，原项目未发生变化。")
        ) from exc


@router.post(
    "/projects/{project_id}/permanent-delete",
    response_model=PermanentDeleteProjectResponse,
)
async def permanently_delete_project(
    project_id: str,
    request: PermanentDeleteProjectRequest,
) -> PermanentDeleteProjectResponse:
    try:
        service = ProjectLifecycleService(settings.data_dir)
        backup_id, backup_created_at = service.permanently_delete(
            project_id,
            confirmation_name=request.confirmationName,
        )
        projects, active_project_id = _repo().list_projects(include_archived=True)
        return PermanentDeleteProjectResponse(
            deletedProjectId=project_id,
            backupId=backup_id,
            backupCreatedAt=backup_created_at,
            projects=projects,
            activeProjectId=active_project_id,
        )
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.put("/projects/{project_id}/draft", response_model=ProjectWorkspaceResponse)
async def save_draft(project_id: str, request: SaveDraftRequest) -> ProjectWorkspaceResponse:
    try:
        return ProjectWorkspaceResponse(
            workspace=_repo().save_draft(
                project_id,
                request.content,
                request.projectExpertId,
            )
        )
    except ProjectError as exc:
        raise _http_error(exc) from exc


@router.post(
    "/projects/{project_id}/pending-items/{pending_item_id}/resolve",
    response_model=ProjectWorkspaceResponse,
)
async def resolve_pending_item(
    project_id: str,
    pending_item_id: str,
) -> ProjectWorkspaceResponse:
    try:
        repository = _repo()
        if SkillRuntime(repository.db_path).has_authorization(
            project_id=project_id,
            pending_item_id=pending_item_id,
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "SKILL_AUTHORIZATION_STREAM_REQUIRED",
                    "message": "本地执行授权必须通过受控进度流确认。",
                    "userActions": [],
                    "retryable": False,
                },
            )
        ProjectCoordinatorService(repository.db_path).resolve_pending_item(
            project_id=project_id,
            pending_item_id=pending_item_id,
        )
        return ProjectWorkspaceResponse(workspace=repository.get_workspace(project_id))
    except ProjectError as exc:
        raise _http_error(exc) from exc
    except ValueError as exc:
        raise _pending_item_http_error(exc) from exc


@router.post(
    "/projects/{project_id}/pending-items/{pending_item_id}/dismiss",
    response_model=ProjectWorkspaceResponse,
)
async def dismiss_pending_item(
    project_id: str,
    pending_item_id: str,
) -> ProjectWorkspaceResponse:
    try:
        repository = _repo()
        runtime = SkillRuntime(repository.db_path)
        if runtime.dismiss_authorization(
            project_id=project_id,
            pending_item_id=pending_item_id,
        ):
            coordinator = ProjectCoordinatorService(repository.db_path)
            coordinator.refresh_highlighted_pending_item(project_id)
            coordinator.refresh_expert_statuses(project_id)
        else:
            ProjectCoordinatorService(repository.db_path).dismiss_pending_item(
                project_id=project_id,
                pending_item_id=pending_item_id,
            )
        return ProjectWorkspaceResponse(workspace=repository.get_workspace(project_id))
    except ProjectError as exc:
        raise _http_error(exc) from exc
    except SkillAuthorizationError as exc:
        raise HTTPException(
            status_code=409,
            detail={
                "code": exc.code,
                "message": str(exc),
                "userActions": [],
                "retryable": False,
            },
        ) from exc
    except ValueError as exc:
        raise _pending_item_http_error(exc) from exc


def _repo() -> ProjectRepository:
    return ProjectRepository(settings.data_dir)


def _resolve_selected_hardware(
    repository: ProjectRepository,
    component_ids: list[str],
) -> tuple[list[HardwareComponent], PreferredHardwareValidationSummary | None]:
    if not component_ids:
        return [], None
    seed_default_components(repository.db_path)
    hardware_skills = HardwareSkillRepository(
        repository.data_dir,
        repository.db_path,
    )
    try:
        hardware_skills.migrate_legacy_rows()
        components = [
            hardware_skills.get_active_component(component_id)
            for component_id in component_ids
        ]
        validation = hardware_skills.validate_component_ids(component_ids)
    except (HardwareSkillNotFoundError, HardwareSkillValidationError) as exc:
        raise ProjectValidationError(
            "所选硬件 Skill 不存在、未激活或未通过校验，请刷新硬件库后重新选择。"
        ) from exc
    if validation.overall == ValidationSeverity.FAIL:
        failed_messages = [
            check.message
            for check in validation.checks
            if check.severity == ValidationSeverity.FAIL
        ]
        detail = "；".join(failed_messages[:4])
        raise ProjectValidationError(
            f"所选硬件组合未通过安全校验：{detail or validation.message}"
        )
    return components, PreferredHardwareValidationSummary(
        overall=validation.overall.value,
        message=validation.message,
        warnings=[
            PreferredHardwareValidationCheck(
                dimension=check.dimension,
                message=check.message,
                details=check.details,
            )
            for check in validation.checks
            if check.severity == ValidationSeverity.WARNING
        ][:12],
    )


def _preferred_hardware_summaries(
    components: list[HardwareComponent],
) -> list[PreferredHardwareSummary]:
    return [
        PreferredHardwareSummary(
            componentId=component.id,
            name=component.name,
            category=component.category.value,
            voltage=component.electrical.voltage,
            voltageMin=(
                component.electrical.voltage
                if component.electrical.voltageMin is None
                else component.electrical.voltageMin
            ),
            voltageMax=(
                component.electrical.voltage
                if component.electrical.voltageMax is None
                else component.electrical.voltageMax
            ),
            supplyVoltages=list(component.electrical.supplyVoltages),
            logicLevel=component.electrical.logicLevel,
            communicationProtocol=component.electrical.communicationProtocol,
            skillName=component.skillName,
            skillRevision=component.skillRevision,
            updatedAt=component.updatedAt,
        )
        for component in components
    ]


async def _route_project_idea_with_model(
    repository: ProjectRepository,
    text: str,
    user_selected_expert: ExpertType | None,
    preferred_hardware: list[HardwareComponent] | None = None,
    preferred_hardware_validation: PreferredHardwareValidationSummary | None = None,
) -> EntryRouterOutput:
    try:
        config, api_key = require_llm_config(
            data_dir=settings.data_dir,
            credential_store=credential_store_factory(),
            credential_service=settings.credential_service,
            credential_account=settings.credential_account,
            workload=ModelWorkload.CREATION,
        )
        route = ModelRouter(repository.db_path).route(
            agent_id="entry_router",
            task_kind="project_routing",
            strategy=ModelRouteStrategy.FAST_FIRST,
        )
        return await EntryRouter().route_with_provider(
            text=text,
            provider=provider_factory(),
            config=config,
            api_key=api_key,
            model=route.model,
            user_selected_expert=user_selected_expert,
            preferred_hardware=_preferred_hardware_summaries(
                preferred_hardware or []
            ),
            preferred_hardware_validation=preferred_hardware_validation,
        )
    except StructuredLLMError:
        raise
    except Exception as exc:
        raise StructuredLLMError(
            make_llm_error(LLMErrorCode.UNKNOWN)
        ) from exc


def _http_error(exc: ProjectError) -> HTTPException:
    return HTTPException(
        status_code=exc.status_code,
        detail={
            "code": exc.code,
            "message": exc.message,
            "userActions": [{"id": "retry", "label": "重试"}],
            "retryable": exc.status_code >= 500,
        },
    )


def _pending_item_http_error(exc: ValueError) -> HTTPException:
    return HTTPException(
        status_code=400,
        detail={
            "code": "PENDING_ITEM_INVALID",
            "message": str(exc),
            "userActions": [{"id": "retry", "label": "重试"}],
            "retryable": False,
        },
    )
