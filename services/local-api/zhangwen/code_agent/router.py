"""Code Agent HTTP routes."""

from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException
from fastapi.concurrency import run_in_threadpool

from zhangwen.code_agent.board_api_contracts import resolve_board_api_contract
from zhangwen.code_agent.chat_code import ChatCodeImportError, ChatCodeService
from zhangwen.code_agent.generator import validate_and_package_code
from zhangwen.code_agent.models import (
    AcceptCodeRequest,
    CodeRuntime,
    CodeRunResponse,
    GenerateCodeRequest,
    ImportCodeMessageRequest,
    RejectCodeRequest,
    ReviseCodeRequest,
    RollbackCodeRequest,
    ValidateCodeRequest,
)
from zhangwen.code_agent.repository import CodeRepository, CodeRevisionConflictError
from zhangwen.code_agent.service import CodeGenerationService
from zhangwen.code_agent.validation import (
    run_esp_claw_lua_validation,
    run_micropython_validation,
)
from zhangwen.config import settings
from zhangwen.llm.deepseek import DeepSeekProvider
from zhangwen.llm.http import llm_http_exception
from zhangwen.llm.runtime import require_llm_config
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.projects.models import ProjectStage, ProjectWorkspace
from zhangwen.specs.models import SpecRun
from zhangwen.projects.repository import ProjectRepository
from zhangwen.specs.models import SpecRunStatus
from zhangwen.specs.repository import SpecRepository
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.skills.model_router import ModelRouter
from zhangwen.skills.models import ModelRouteStrategy

router = APIRouter(prefix="/api/projects", tags=["code-agent"])
credential_store_factory = BackendCredentialStore
provider_factory = DeepSeekProvider


@router.get("/{project_id}/code/current", response_model=CodeRunResponse)
async def get_current_code(project_id: str) -> CodeRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    code_run = CodeRepository(repo.db_path).get_current_code(project_id)
    if code_run is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CODE_NOT_FOUND",
                "message": "当前项目还没有代码草稿。",
                "retryable": False,
            },
        )
    return CodeRunResponse(codeRun=code_run)


@router.post("/{project_id}/code/import-message", response_model=CodeRunResponse)
async def import_code_message(
    project_id: str,
    request: ImportCodeMessageRequest,
) -> CodeRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        code_run = ChatCodeService(repo.db_path).import_assistant_message(
            project_id=project_id,
            message_id=request.messageId,
        )
    except ChatCodeImportError as exc:
        status_code = 404 if exc.code == "CODE_IMPORT_MESSAGE_NOT_FOUND" else 422
        raise HTTPException(
            status_code=status_code,
            detail={"code": exc.code, "message": str(exc), "retryable": False},
        ) from exc
    except ValueError as exc:
        raise _unprocessable("CODE_IMPORT_INVALID", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.IMPLEMENTING)
    return CodeRunResponse(codeRun=code_run)


@router.post("/{project_id}/code/validate", response_model=CodeRunResponse)
async def validate_code(
    project_id: str,
    request: ValidateCodeRequest,
) -> CodeRunResponse:
    repo = _project_repo()
    workspace = repo.get_workspace(project_id)
    code_repository = CodeRepository(repo.db_path)
    current = code_repository.get_current_code(project_id)
    if current is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "CODE_NOT_FOUND",
                "message": "当前项目还没有代码草稿。",
                "retryable": False,
            },
        )
    if current.id != request.codeRunId:
        raise _validation_conflict("代码已经产生新版本，请刷新后验证当前版本。")
    now = datetime.now(UTC).isoformat()
    spec = (
        SpecRepository(repo.db_path).get_spec(project_id, current.specRunId)
        if current.specRunId is not None
        else None
    )
    board_contract = resolve_board_api_contract(
        _workspace_hardware_ids(workspace),
        spec,
    )
    if current.runtime == CodeRuntime.MICROPYTHON:
        test_result = await run_in_threadpool(
            run_micropython_validation,
            current.files,
            now=now,
            board_contract_id=(
                board_contract.id if board_contract is not None else None
            ),
        )
    else:
        test_result = await run_in_threadpool(
            run_esp_claw_lua_validation,
            current.files,
            now=now,
        )
    try:
        code_run = code_repository.validate_code(
            project_id,
            request.codeRunId,
            test_result,
        )
    except CodeRevisionConflictError as exc:
        raise _validation_conflict(str(exc)) from exc
    except ValueError as exc:
        raise _unprocessable("CODE_VALIDATION_FAILED", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.VALIDATING)
    return CodeRunResponse(codeRun=code_run)


@router.get("/{project_id}/code/{code_run_id}", response_model=CodeRunResponse)
async def get_code(project_id: str, code_run_id: str) -> CodeRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        code_run = CodeRepository(repo.db_path).get_code(project_id, code_run_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"code": "CODE_NOT_FOUND", "message": str(exc), "retryable": False},
        ) from exc
    return CodeRunResponse(codeRun=code_run)


@router.put("/{project_id}/code/{code_run_id}", response_model=CodeRunResponse)
async def revise_code(
    project_id: str,
    code_run_id: str,
    request: ReviseCodeRequest,
) -> CodeRunResponse:
    if request.baseCodeRunId != code_run_id:
        raise _unprocessable("CODE_REVISION_BASE_MISMATCH", "请求中的基础代码版本不一致。")
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        code_run = CodeRepository(repo.db_path).revise_from_user(
            project_id=project_id,
            base_code_run_id=request.baseCodeRunId,
            files=request.files,
            summary=request.summary,
        )
    except CodeRevisionConflictError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "CODE_REVISION_CONFLICT", "message": str(exc), "retryable": True},
        ) from exc
    except ValueError as exc:
        raise _unprocessable("CODE_REVISION_INVALID", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.IMPLEMENTING)
    return CodeRunResponse(codeRun=code_run)


@router.post("/{project_id}/code/generate", response_model=CodeRunResponse)
async def generate_code(
    project_id: str,
    request: GenerateCodeRequest,
) -> CodeRunResponse:
    repo = _project_repo()
    workspace = repo.get_workspace(project_id)
    spec = SpecRepository(repo.db_path).get_spec(project_id, request.specRunId)
    if spec.status != SpecRunStatus.APPROVED:
        raise _unprocessable(
            "CODE_REQUIRES_APPROVED_SPEC",
            "只有已确认 Spec 可以生成代码草稿。",
        )
    now = datetime.now(UTC).isoformat()
    board_contract = resolve_board_api_contract(
        _workspace_hardware_ids(workspace),
        spec,
    )
    try:
        config, api_key = _llm_config()
        route = ModelRouter(repo.db_path).route(
            agent_id="code_generator",
            task_kind="code",
            strategy=ModelRouteStrategy.QUALITY_FIRST,
        )
        draft = await CodeGenerationService(provider_factory()).generate(
            spec=spec,
            config=config,
            api_key=api_key,
            model=route.model,
            board_contract=board_contract,
            runtime=request.runtime,
        )
        generated = validate_and_package_code(
            spec,
            draft,
            now=now,
            board_contract_id=(
                board_contract.id
                if request.runtime == CodeRuntime.MICROPYTHON
                and board_contract is not None
                else None
            ),
            runtime=request.runtime,
        )
        if request.runtime == CodeRuntime.MICROPYTHON:
            test_result = await run_in_threadpool(
                run_micropython_validation,
                generated.files,
                now=now,
                board_contract_id=(
                    board_contract.id if board_contract is not None else None
                ),
            )
        else:
            test_result = await run_in_threadpool(
                run_esp_claw_lua_validation,
                generated.files,
                now=now,
            )
        generated = replace(generated, test_result=test_result)
        code_run = CodeRepository(repo.db_path).create_from_generated(
            project_id=project_id,
            spec=spec,
            generated=generated,
        )
    except StructuredLLMError as exc:
        raise llm_http_exception(exc) from exc
    except ValueError as exc:
        raise _unprocessable("CODE_OUTPUT_INVALID", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.IMPLEMENTING)
    return CodeRunResponse(codeRun=code_run)


@router.post("/{project_id}/code/accept", response_model=CodeRunResponse)
async def accept_code(
    project_id: str,
    request: AcceptCodeRequest,
) -> CodeRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        code_run = CodeRepository(repo.db_path).accept_code(
            project_id,
            request.codeRunId,
        )
    except ValueError as exc:
        raise _unprocessable("CODE_ACCEPT_FAILED", str(exc)) from exc
    _update_stage(repo, project_id, ProjectStage.VALIDATING)
    return CodeRunResponse(codeRun=code_run)


@router.post("/{project_id}/code/reject", response_model=CodeRunResponse)
async def reject_code(
    project_id: str,
    request: RejectCodeRequest,
) -> CodeRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        code_run = CodeRepository(repo.db_path).reject_code(
            project_id,
            request.codeRunId,
            request.reason,
        )
    except ValueError as exc:
        raise _unprocessable("CODE_REJECT_FAILED", str(exc)) from exc
    return CodeRunResponse(codeRun=code_run)


@router.post("/{project_id}/code/rollback", response_model=CodeRunResponse)
async def rollback_code(
    project_id: str,
    request: RollbackCodeRequest,
) -> CodeRunResponse:
    repo = _project_repo()
    repo.get_workspace(project_id)
    try:
        code_run = CodeRepository(repo.db_path).rollback_code(
            project_id,
            request.codeRunId,
        )
    except ValueError as exc:
        raise _unprocessable("CODE_ROLLBACK_FAILED", str(exc)) from exc
    return CodeRunResponse(codeRun=code_run)


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


def _validation_conflict(message: str) -> HTTPException:
    return HTTPException(
        status_code=409,
        detail={
            "code": "CODE_VALIDATION_CONFLICT",
            "message": message,
            "retryable": True,
        },
    )


def _workspace_hardware_ids(workspace: ProjectWorkspace) -> tuple[str, ...]:
    shared_context = workspace.sharedContext
    if shared_context is None:
        return ()
    component_ids: list[str] = []
    for fact in shared_context.confirmedFacts:
        if (fact.key or fact.field) != "preferred_hardware":
            continue
        if not isinstance(fact.value, dict):
            continue
        components = fact.value.get("components")
        if not isinstance(components, list):
            continue
        for component in components:
            if not isinstance(component, dict):
                continue
            component_id = component.get("id") or component.get("componentId")
            if component_id:
                component_ids.append(str(component_id))
    return tuple(dict.fromkeys(component_ids))


def _update_stage(repo: ProjectRepository, project_id: str, stage: ProjectStage) -> None:
    now = datetime.now(UTC).isoformat()
    with repo._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (stage.value, now, project_id),
        )
