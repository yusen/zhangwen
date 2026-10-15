"""Chat streaming routes."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import suppress
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from zhangwen.config import settings
from zhangwen.chat.idea_flow import (
    handle_project_conversation,
    should_handle_project_conversation,
)
from zhangwen.chat.sessions import ChatSessionRegistry
from zhangwen.chat.workspace_context import bounded_v2_workspace_context
from zhangwen.cad_agent.intake import CadProfileIntake, is_cad_revision_request
from zhangwen.cad_agent.chat_projection import cad_artifact_payload
from zhangwen.cad_agent.models import CadRun
from zhangwen.code_agent.chat_code import code_artifact_payload
from zhangwen.code_agent.models import CodeRun
from zhangwen.coordinator import ProjectCoordinatorService
from zhangwen.creator.models import ConversationProjectDraftV1
from zhangwen.creator.repository import CreatorRepository
from zhangwen.experts.config import canonical_expert_type
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.llm.contracts import (
    CancelChatResponse,
    ChatMessageStatus,
    ChatProgress,
    ChatProgressEmitter,
    ChatRequest,
    LLMError,
    LLMErrorCode,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.llm.development_fake import create_provider
from zhangwen.llm.errors import make_llm_error
from zhangwen.llm.runtime import require_llm_config
from zhangwen.settings.models import ModelWorkload
from zhangwen.llm.structured import StructuredLLMError
from zhangwen.host import require_desktop_host
from zhangwen.security.credentials import BackendCredentialStore
from zhangwen.projects.errors import ConversationContextError, ProjectError
from zhangwen.projects.models import (
    ClarificationBatchAnswerInput,
    MultipleChoiceAnswerInput,
    PersistedChatRequest,
    ProjectStage,
    SingleChoiceAnswerInput,
    TextQuestionAnswerInput,
)
from zhangwen.projects.repository import (
    AUTOMATIC_RECOVERY_LABEL,
    ClarificationAnswerValue,
    ProjectRepository,
)
from zhangwen.skills.models import SkillRunStatus
from zhangwen.skills.runtime import (
    SkillAuthorizationError,
    SkillRuntime,
)

router = APIRouter(prefix="/api", tags=["chat"])
sessions = ChatSessionRegistry()
credential_store_factory = BackendCredentialStore
provider_factory = create_provider
local_skill_runtime_factory: Callable[[Path], SkillRuntime] = SkillRuntime


@dataclass(frozen=True)
class ClarificationSubmission:
    source_message_id: str | None
    answers: tuple[ClarificationAnswerValue, ...]
    answer_type: str | None = None
    require_complete: bool = False

    @property
    def question_ids(self) -> list[str]:
        return [answer.question_id for answer in self.answers]

    @property
    def selected_option_ids(self) -> list[str]:
        return [
            option_id
            for answer in self.answers
            for option_id in answer.selected_option_ids
        ]


@router.post("/chat/stream")
async def stream_chat(request: ChatRequest) -> StreamingResponse:
    request_id = f"req_{uuid.uuid4().hex}"
    message_id = f"msg_{uuid.uuid4().hex}"
    token = sessions.create(request_id, abort_previous=request.abortPrevious)

    async def events() -> AsyncIterator[str]:
        try:
            try:
                config, api_key = _get_llm_config(
                    owner_kind="EPHEMERAL_CHAT",
                    owner_id=request_id,
                )
            except StructuredLLMError as exc:
                yield _sse(
                    "chat.error",
                    StreamChunk(
                        requestId=request_id,
                        messageId=message_id,
                        type=StreamChunkType.ERROR,
                        error=exc.error,
                    ),
                )
                return

            provider = provider_factory()
            async for chunk in provider.stream_chat(
                request, config, api_key, token, request_id, message_id
            ):
                if chunk.type == StreamChunkType.PROGRESS:
                    yield _sse(
                        "chat.error",
                        StreamChunk(
                            requestId=request_id,
                            messageId=message_id,
                            type=StreamChunkType.ERROR,
                            error=make_llm_error(LLMErrorCode.LLM_OUTPUT_INVALID),
                        ),
                    )
                    return
                event = {
                    StreamChunkType.START: "chat.started",
                    StreamChunkType.CONTENT_DELTA: "chat.delta",
                    StreamChunkType.REASONING_DELTA: "chat.delta",
                    StreamChunkType.COMPLETED: "chat.completed",
                    StreamChunkType.ERROR: "chat.error",
                    StreamChunkType.CANCELED: "chat.canceled",
                }[chunk.type]
                yield _sse(event, chunk)
        finally:
            sessions.remove(request_id)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/projects/{project_id}/chat/stream")
async def stream_project_chat(
    project_id: str, request: PersistedChatRequest
) -> StreamingResponse:
    request_id = f"req_{uuid.uuid4().hex}"
    repository = ProjectRepository(settings.data_dir)

    try:
        existing = repository.get_workspace(project_id)
        if request.retryKickoff and not request.kickoffTurnId:
            raise ConversationContextError(
                "STALE_CONVERSATION_TURN",
                "Kickoff retry requires the original kickoff turn.",
            )
        if request.kickoffTurnId:
            _validate_kickoff_request(existing, request)
        if request.projectExpertId:
            repository.set_active_expert(project_id, request.projectExpertId)
            existing = repository.get_workspace(project_id)
        model = request.model or existing.project.selectedModel
        conversation_id = repository.resolve_conversation_id(
            project_id,
            request.projectExpertId,
        )
        _validate_turn_context(project_id, conversation_id, request)
        request_turn_id = request.kickoffTurnId or _request_turn_id(request)
        client_turn_id = _client_turn_id(request, request_turn_id)
        if request.kickoffTurnId:
            kickoff_state, user_message, assistant_message = repository.claim_kickoff_turn(
                project_id=project_id,
                turn_id=request.kickoffTurnId,
                content=request.content,
                conversation_id=conversation_id,
                project_expert_id=request.projectExpertId,
                client_turn_id=client_turn_id,
                retry=request.retryKickoff,
            )
            response_turn_id = _response_turn_id(assistant_message)
            if kickoff_state == "COMPLETED":
                return StreamingResponse(
                    _duplicate_project_events(
                        request_id=request_id,
                        project_id=project_id,
                        conversation_id=conversation_id,
                        duplicate=(user_message, assistant_message),
                        request_turn_id=request_turn_id,
                    ),
                    media_type="text/event-stream",
                )
            if kickoff_state == "RUNNING":
                return StreamingResponse(
                    _running_project_events(
                        request_id=request_id,
                        project_id=project_id,
                        conversation_id=conversation_id,
                        duplicate=(user_message, assistant_message),
                        request_turn_id=request_turn_id,
                    ),
                    media_type="text/event-stream",
                )
            if kickoff_state == "RETRY_REQUIRED":
                return StreamingResponse(
                    _duplicate_project_events(
                        request_id=request_id,
                        project_id=project_id,
                        conversation_id=conversation_id,
                        duplicate=(user_message, assistant_message),
                        request_turn_id=request_turn_id,
                    ),
                    media_type="text/event-stream",
                )
            answer = ClarificationSubmission(None, ())
            cad_answer = False
        else:
            response_turn_id = f"turn_{uuid.uuid4().hex}"
            duplicate = repository.find_turn_messages(
                project_id,
                conversation_id,
                client_turn_id,
            )
            if duplicate is not None:
                if duplicate[1].status in {
                    ChatMessageStatus.READY,
                    ChatMessageStatus.STREAMING,
                }:
                    return StreamingResponse(
                        _running_project_events(
                            request_id=request_id,
                            project_id=project_id,
                            conversation_id=conversation_id,
                            duplicate=duplicate,
                            request_turn_id=request_turn_id,
                        ),
                        media_type="text/event-stream",
                    )
                return StreamingResponse(
                    _duplicate_project_events(
                        request_id=request_id,
                        project_id=project_id,
                        conversation_id=conversation_id,
                        duplicate=duplicate,
                        request_turn_id=request_turn_id,
                    ),
                    media_type="text/event-stream",
                )
            answer = _answer_submission(
                request, project_id, conversation_id, client_turn_id
            )
            cad_answer_state = {"handled": False}
            cad_intake = CadProfileIntake(repository.db_path)

            def record_cad_answers(conn, user_message_id: str) -> None:
                try:
                    cad_answer_state["handled"] = cad_intake.record_confirmed_answers(
                        project_id=project_id,
                        source_message_id=answer.source_message_id,
                        user_message_id=user_message_id,
                        answers=answer.answers,
                        connection=conn,
                    )
                except ValueError as exc:
                    raise ConversationContextError(
                        "CAD_INPUT_INVALID",
                        "CAD 结构输入无效，请检查内腔尺寸或机械档案后重试。",
                        status_code=422,
                    ) from exc

            _, user_message, assistant_message = repository.append_user_and_assistant(
                project_id,
                request.content,
                model,
                project_expert_id=request.projectExpertId,
                turn_id=request_turn_id,
                response_turn_id=response_turn_id,
                client_turn_id=client_turn_id,
                parent_turn_id=(request.turnContext or {}).get("parentTurnId")
                if request.turnContext
                else None,
                request_json=request.model_dump(mode="json"),
                user_metadata={
                    "replyToMessageId": answer.source_message_id,
                    "replyToQuestionId": answer.question_ids[0]
                    if len(answer.question_ids) == 1
                    else None,
                    "replyToQuestionIds": answer.question_ids,
                    "answerType": answer.answer_type,
                    "answerOptionIds": answer.selected_option_ids,
                    "clarificationAnswers": [
                        {
                            "questionId": item.question_id,
                            "selectedOptionIds": list(item.selected_option_ids),
                            "textInput": item.text_input,
                        }
                        for item in answer.answers
                    ],
                    "actionType": request.conversationAction,
                    "automaticHandoff": request.automaticHandoff,
                    "handoffLabel": request.handoffLabel,
                    "recoveryOfMessageId": request.recoveryOfMessageId,
                    "recoveryLabel": request.recoveryLabel,
                },
                clarification_source_message_id=answer.source_message_id,
                clarification_answers=list(answer.answers),
                require_complete_clarification=answer.require_complete,
                automatic_recovery_source_message_id=(
                    request.recoveryOfMessageId
                    if request.recoveryLabel == AUTOMATIC_RECOVERY_LABEL
                    else None
                ),
                clarification_transaction=record_cad_answers,
            )
            cad_answer = cad_answer_state["handled"]
    except ProjectError as exc:
        error = _project_error_to_llm_error(exc)
        error_request_turn_id = (
            (request.turnContext or {}).get("turnId")
            if request.turnContext
            else None
        )
        error_conversation_id = (
            (request.turnContext or {}).get("conversationId", "")
            if request.turnContext
            else ""
        )

        async def error_events() -> AsyncIterator[str]:
            yield _project_sse(
                "chat.error",
                StreamChunk(
                    requestId=request_id,
                    messageId="msg_error",
                    requestTurnId=error_request_turn_id,
                    type=StreamChunkType.ERROR,
                    error=error,
                ),
                project_id=project_id,
                conversation_id=error_conversation_id,
            )

        return StreamingResponse(error_events(), media_type="text/event-stream")

    token = sessions.create(request_id, abort_previous=request.abortPrevious)

    async def events() -> AsyncIterator[str]:
        try:
            repository.update_turn_status(request_turn_id, "STREAMING")
            try:
                config, api_key = _get_llm_config(
                    owner_kind="CONVERSATION_TURN",
                    owner_id=request_turn_id,
                )
            except StructuredLLMError as exc:
                error = exc.error
                repository.update_message(
                    project_id,
                    assistant_message.id,
                    status=ChatMessageStatus.FAILED,
                    error=error,
                )
                yield _project_sse(
                    "chat.error",
                    StreamChunk(
                        requestId=request_id,
                        messageId=assistant_message.id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.ERROR,
                        error=error,
                    ),
                    project_id=project_id,
                    conversation_id=existing.conversation.id,
                    user_message_id=user_message.id,
                )
                repository.update_turn_status(request_turn_id, "FAILED")
                return

            active_expert = next(
                (
                    expert
                    for expert in existing.experts
                    if expert.id == (request.projectExpertId or existing.project.activeExpertId)
                ),
                None,
            )
            active_expert_type = canonical_expert_type(
                active_expert.expertType
                if active_expert is not None
                else (request.expertType or "problem_guide")
            )
            cad_intake = CadProfileIntake(repository.db_path)
            cad_workflow = (
                active_expert_type.value == "structure_engineer"
                and not request.conversationAction
                and cad_intake.is_workflow_request(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    message=request.content,
                    source_message_id=answer.source_message_id,
                    request_message_id=user_message.id,
                    response_message_id=assistant_message.id,
                )
            )
            cad_state = cad_intake.state(project_id)
            if (
                cad_workflow
                and not cad_answer
                and is_cad_revision_request(request.content)
                and (
                    cad_state.target is not None
                    or cad_state.mode is not None
                    or cad_state.dimensions is not None
                    or bool(cad_state.profiles)
                )
            ):
                cad_intake.restart_for_revision(project_id)
                cad_intake.apply_explicit_dimensions(
                    project_id=project_id,
                    message=request.content,
                    source_message_id=user_message.id,
                    baseline=cad_state,
                )
            if (
                not cad_workflow
                and should_handle_project_conversation(existing.project.stage, request)
                and (
                    active_expert_type.value == "problem_guide"
                    or request.conversationAction
                    or existing.project.stage
                    in {
                        ProjectStage.SOLUTION_DRAFT,
                        ProjectStage.SOLUTION_CONFIRMED,
                        ProjectStage.PROPOSAL_DRAFT,
                    }
                )
            ):
                provider = provider_factory()
                yield _project_sse(
                    "chat.started",
                    StreamChunk(
                        requestId=request_id,
                        messageId=assistant_message.id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.START,
                        model=model,
                    ),
                    project_id=project_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message.id,
                )
                progress_queue: asyncio.Queue[ChatProgress] = asyncio.Queue()
                conversation_task = asyncio.create_task(
                    handle_project_conversation(
                        repo=repository,
                        project_id=project_id,
                        request=request,
                        user_message=user_message,
                        config=config,
                        api_key=api_key,
                        provider=provider,
                        model=model,
                        on_progress=progress_queue.put_nowait,
                    )
                )
                try:
                    while not conversation_task.done() or not progress_queue.empty():
                        if token.canceled:
                            conversation_task.cancel()
                            break
                        try:
                            progress = progress_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            try:
                                progress = await asyncio.wait_for(
                                    progress_queue.get(),
                                    timeout=0.1,
                                )
                            except TimeoutError:
                                continue
                        yield _project_sse(
                            "chat.progress",
                            StreamChunk(
                                requestId=request_id,
                                messageId=assistant_message.id,
                                requestTurnId=request_turn_id,
                                responseTurnId=response_turn_id,
                                type=StreamChunkType.PROGRESS,
                                model=model,
                                progress=progress,
                            ),
                            project_id=project_id,
                            conversation_id=conversation_id,
                            user_message_id=user_message.id,
                        )
                    result = await conversation_task
                except asyncio.CancelledError:
                    conversation_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await conversation_task
                    error = make_llm_error(LLMErrorCode.CANCELED)
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.CANCELED,
                        error=error,
                    )
                    repository.update_turn_status(request_turn_id, "CANCELED")
                    if not token.canceled:
                        token.cancel()
                        raise
                    yield _project_sse(
                        "chat.canceled",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.CANCELED,
                            model=model,
                            error=error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                except StructuredLLMError as exc:
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.FAILED,
                        error=exc.error,
                    )
                    repository.update_turn_status(request_turn_id, "FAILED")
                    yield _project_sse(
                        "chat.error",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.ERROR,
                            model=model,
                            error=exc.error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                except Exception:
                    error = make_llm_error(LLMErrorCode.UNKNOWN)
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.FAILED,
                        error=error,
                    )
                    repository.update_turn_status(request_turn_id, "FAILED")
                    yield _project_sse(
                        "chat.error",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.ERROR,
                            model=model,
                            error=error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                finally:
                    if not conversation_task.done():
                        token.cancel()
                        conversation_task.cancel()
                        await asyncio.gather(conversation_task, return_exceptions=True)
                repository.update_message(
                    project_id,
                    assistant_message.id,
                    content=result.content,
                    status=ChatMessageStatus.COMPLETED,
                    structured_payload=result.payload,
                )
                _project_creator_candidate(
                    repository,
                    project_id=project_id,
                    source_message_id=assistant_message.id,
                    source_turn_id=request_turn_id,
                    payload=result.payload,
                )
                repository.register_clarification_question(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    source_message_id=assistant_message.id,
                    stage=repository.get_workspace(project_id).project.stage,
                    payload=result.payload,
                )
                coordinator = ProjectCoordinatorService(repository.db_path)
                for clarification_answer in answer.answers:
                    fact = coordinator.propose_shared_fact(
                        project_id=project_id,
                        field="clarification_answer",
                        key=clarification_answer.question_id,
                        value={
                            "selectedOptionIds": list(
                                clarification_answer.selected_option_ids
                            ),
                            "textInput": clarification_answer.text_input,
                        },
                        source_type="user",
                        source_id=user_message.id,
                        source_expert_id=active_expert.id if active_expert else None,
                        source_expert_type=active_expert_type,
                    )
                    coordinator.confirm_shared_fact(
                        project_id=project_id,
                        fact_id=fact.id,
                        confirmed_by="user",
                    )
                coordinator.refresh_highlighted_pending_item(project_id)
                coordinator.refresh_expert_statuses(project_id)
                repository.update_turn_status(request_turn_id, "COMPLETED")
                yield _project_sse(
                    "chat.completed",
                    StreamChunk(
                        requestId=request_id,
                        messageId=assistant_message.id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.COMPLETED,
                        accumulatedContent=result.content,
                        model=model,
                        structuredPayload=result.payload,
                    ),
                    project_id=project_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message.id,
                )
                return

            if active_expert is not None:
                provider = provider_factory()
                yield _project_sse(
                    "chat.started",
                    StreamChunk(
                        requestId=request_id,
                        messageId=assistant_message.id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.START,
                        model=model,
                    ),
                    project_id=project_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message.id,
                )
                progress_queue: asyncio.Queue[ChatProgress] = asyncio.Queue()
                runtime_task = asyncio.create_task(
                    ExpertRuntime(repository.db_path).run(
                        request=ExpertRuntimeRequest(
                            projectId=project_id,
                            projectExpertId=active_expert.id,
                            conversationId=conversation_id,
                            expertType=active_expert_type,
                            userMessage=(
                                _confirmed_cad_answer_prompt(repository, project_id, answer)
                                if cad_answer
                                else user_message.content
                            ),
                            requestMessageId=user_message.id,
                            responseMessageId=assistant_message.id,
                            workspaceContext=bounded_v2_workspace_context(
                                request.turnContext
                            ),
                            model=model,
                        ),
                        provider=provider,
                        config=config,
                        api_key=api_key,
                        cancel_token=token,
                        on_progress=progress_queue.put_nowait,
                    )
                )
                try:
                    while not runtime_task.done() or not progress_queue.empty():
                        if token.canceled:
                            runtime_task.cancel()
                            break
                        try:
                            progress = progress_queue.get_nowait()
                        except asyncio.QueueEmpty:
                            try:
                                progress = await asyncio.wait_for(
                                    progress_queue.get(),
                                    timeout=0.1,
                                )
                            except TimeoutError:
                                continue
                        yield _project_sse(
                            "chat.progress",
                            StreamChunk(
                                requestId=request_id,
                                messageId=assistant_message.id,
                                requestTurnId=request_turn_id,
                                responseTurnId=response_turn_id,
                                type=StreamChunkType.PROGRESS,
                                model=model,
                                progress=progress,
                            ),
                            project_id=project_id,
                            conversation_id=conversation_id,
                            user_message_id=user_message.id,
                        )
                    runtime_result = await runtime_task
                except asyncio.CancelledError:
                    runtime_task.cancel()
                    with suppress(asyncio.CancelledError):
                        await runtime_task
                    if not token.canceled:
                        error = make_llm_error(LLMErrorCode.CANCELED)
                        repository.update_message(
                            project_id,
                            assistant_message.id,
                            status=ChatMessageStatus.CANCELED,
                            error=error,
                        )
                        repository.update_turn_status(request_turn_id, "CANCELED")
                        token.cancel()
                        raise
                    error = make_llm_error(LLMErrorCode.CANCELED)
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.CANCELED,
                        error=error,
                    )
                    repository.update_turn_status(request_turn_id, "CANCELED")
                    yield _project_sse(
                        "chat.canceled",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.CANCELED,
                            model=model,
                            error=error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                except StructuredLLMError as exc:
                    if exc.error.code == LLMErrorCode.CANCELED:
                        repository.update_message(
                            project_id,
                            assistant_message.id,
                            status=ChatMessageStatus.CANCELED,
                            error=exc.error,
                        )
                        repository.update_turn_status(request_turn_id, "CANCELED")
                        yield _project_sse(
                            "chat.canceled",
                            StreamChunk(
                                requestId=request_id,
                                messageId=assistant_message.id,
                                requestTurnId=request_turn_id,
                                responseTurnId=response_turn_id,
                                type=StreamChunkType.CANCELED,
                                model=model,
                                error=exc.error,
                            ),
                            project_id=project_id,
                            conversation_id=conversation_id,
                            user_message_id=user_message.id,
                        )
                        return
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.FAILED,
                        error=exc.error,
                    )
                    repository.update_turn_status(request_turn_id, "FAILED")
                    yield _project_sse(
                        "chat.error",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.ERROR,
                            model=model,
                            error=exc.error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                except Exception:
                    error = make_llm_error(LLMErrorCode.UNKNOWN)
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.FAILED,
                        error=error,
                    )
                    repository.update_turn_status(request_turn_id, "FAILED")
                    yield _project_sse(
                        "chat.error",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.ERROR,
                            model=model,
                            error=error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                finally:
                    if not runtime_task.done():
                        token.cancel()
                        runtime_task.cancel()
                        await asyncio.gather(runtime_task, return_exceptions=True)
                output = runtime_result.output
                structured_payload = _runtime_ui_payload(
                    output.uiPayload,
                    runtime_result.codeRun,
                    runtime_result.cadRun,
                )
                if runtime_result.codeRun is not None:
                    _mark_code_implementation_started(repository, project_id)
                repository.update_message(
                    project_id,
                    assistant_message.id,
                    content=output.content,
                    status=ChatMessageStatus.COMPLETED,
                    structured_payload=structured_payload,
                )
                _project_creator_candidate(
                    repository,
                    project_id=project_id,
                    source_message_id=assistant_message.id,
                    source_turn_id=request_turn_id,
                    payload=structured_payload,
                )
                repository.register_clarification_question(
                    project_id=project_id,
                    conversation_id=conversation_id,
                    source_message_id=assistant_message.id,
                    stage=repository.get_workspace(project_id).project.stage,
                    payload=structured_payload,
                )
                if cad_answer or runtime_result.cadRun is not None:
                    CadProfileIntake(
                        repository.db_path
                    ).dismiss_legacy_input_pending_items(project_id)
                repository.update_turn_status(request_turn_id, "COMPLETED")
                yield _project_sse(
                    "chat.completed",
                    StreamChunk(
                        requestId=request_id,
                        messageId=assistant_message.id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.COMPLETED,
                        accumulatedContent=output.content,
                        model=model,
                        structuredPayload=structured_payload,
                    ),
                    project_id=project_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message.id,
                )
                return

            provider = provider_factory()
            conversation_messages = _conversation_messages(existing, conversation_id)
            chat_request = ChatRequest(
                messages=[*conversation_messages, user_message],
                model=model,
                abortPrevious=request.abortPrevious,
            )
            async for chunk in provider.stream_chat(
                chat_request,
                config,
                api_key,
                token,
                request_id,
                assistant_message.id,
            ):
                chunk.requestTurnId = request_turn_id
                chunk.responseTurnId = response_turn_id
                if chunk.type == StreamChunkType.PROGRESS:
                    error = make_llm_error(LLMErrorCode.LLM_OUTPUT_INVALID)
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.FAILED,
                        error=error,
                    )
                    repository.update_turn_status(request_turn_id, "FAILED")
                    yield _project_sse(
                        "chat.error",
                        StreamChunk(
                            requestId=request_id,
                            messageId=assistant_message.id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.ERROR,
                            model=model,
                            error=error,
                        ),
                        project_id=project_id,
                        conversation_id=conversation_id,
                        user_message_id=user_message.id,
                    )
                    return
                event = {
                    StreamChunkType.START: "chat.started",
                    StreamChunkType.CONTENT_DELTA: "chat.delta",
                    StreamChunkType.REASONING_DELTA: "chat.delta",
                    StreamChunkType.COMPLETED: "chat.completed",
                    StreamChunkType.ERROR: "chat.error",
                    StreamChunkType.CANCELED: "chat.canceled",
                }[chunk.type]

                if chunk.type in {
                    StreamChunkType.CONTENT_DELTA,
                    StreamChunkType.REASONING_DELTA,
                }:
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        content=chunk.accumulatedContent,
                        reasoning_content=chunk.accumulatedReasoning,
                        usage=chunk.usage,
                    )
                elif chunk.type == StreamChunkType.COMPLETED:
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        content=chunk.accumulatedContent or "",
                        reasoning_content=chunk.accumulatedReasoning,
                        status=ChatMessageStatus.COMPLETED,
                        usage=chunk.usage,
                    )
                    repository.update_turn_status(request_turn_id, "COMPLETED")
                elif chunk.type == StreamChunkType.ERROR:
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.FAILED,
                        error=chunk.error,
                    )
                    repository.update_turn_status(request_turn_id, "FAILED")
                elif chunk.type == StreamChunkType.CANCELED:
                    repository.update_message(
                        project_id,
                        assistant_message.id,
                        status=ChatMessageStatus.CANCELED,
                        error=chunk.error,
                    )
                    repository.update_turn_status(request_turn_id, "CANCELED")

                yield _project_sse(
                    event,
                    chunk,
                    project_id=project_id,
                    conversation_id=conversation_id,
                    user_message_id=user_message.id,
                )
        except asyncio.CancelledError:
            if not token.canceled:
                error = make_llm_error(LLMErrorCode.CANCELED)
                repository.update_message(
                    project_id,
                    assistant_message.id,
                    status=ChatMessageStatus.CANCELED,
                    error=error,
                )
                repository.update_turn_status(request_turn_id, "CANCELED")
                token.cancel()
            raise
        finally:
            sessions.remove(request_id)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post(
    "/projects/{project_id}/pending-items/{pending_item_id}/resolve/stream"
)
async def stream_skill_authorization_resolution(
    project_id: str,
    pending_item_id: str,
    http_request: Request,
) -> StreamingResponse:
    require_desktop_host(http_request, "local_tool")
    repository = ProjectRepository(settings.data_dir)
    runtime = local_skill_runtime_factory(repository.db_path)
    try:
        authorization = runtime.authorization_context(
            project_id=project_id,
            pending_item_id=pending_item_id,
        )
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

    request_id = f"req_{uuid.uuid4().hex}"
    request_turn_id = f"turn_local_authorization_{uuid.uuid4().hex}"
    response_turn_id = f"turn_local_execution_{uuid.uuid4().hex}"
    token = sessions.create(request_id, abort_previous=False)

    async def events() -> AsyncIterator[str]:
        runtime_task: asyncio.Task | None = None
        try:
            yield _project_sse(
                "chat.started",
                StreamChunk(
                    requestId=request_id,
                    messageId=authorization.response_message_id,
                    requestTurnId=request_turn_id,
                    responseTurnId=response_turn_id,
                    type=StreamChunkType.START,
                ),
                project_id=project_id,
                conversation_id=authorization.conversation_id,
            )
            progress_queue: asyncio.Queue[ChatProgress] = asyncio.Queue()
            runtime_task = asyncio.create_task(
                runtime.resume_authorized(
                    project_id=project_id,
                    pending_item_id=pending_item_id,
                    progress_emitter=_progress_emitter(progress_queue),
                )
            )
            try:
                while not runtime_task.done() or not progress_queue.empty():
                    if token.canceled:
                        runtime_task.cancel()
                        break
                    try:
                        progress = progress_queue.get_nowait()
                    except asyncio.QueueEmpty:
                        try:
                            progress = await asyncio.wait_for(
                                progress_queue.get(),
                                timeout=0.1,
                            )
                        except TimeoutError:
                            continue
                    yield _project_sse(
                        "chat.progress",
                        StreamChunk(
                            requestId=request_id,
                            messageId=authorization.response_message_id,
                            requestTurnId=request_turn_id,
                            responseTurnId=response_turn_id,
                            type=StreamChunkType.PROGRESS,
                            progress=progress,
                        ),
                        project_id=project_id,
                        conversation_id=authorization.conversation_id,
                    )
                result = await runtime_task
            except asyncio.CancelledError:
                error = make_llm_error(LLMErrorCode.CANCELED)
                if not token.canceled:
                    token.cancel()
                    raise
                yield _project_sse(
                    "chat.canceled",
                    StreamChunk(
                        requestId=request_id,
                        messageId=authorization.response_message_id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.CANCELED,
                        error=error,
                    ),
                    project_id=project_id,
                    conversation_id=authorization.conversation_id,
                )
                return
            except SkillAuthorizationError as exc:
                yield _project_sse(
                    "chat.error",
                    StreamChunk(
                        requestId=request_id,
                        messageId=authorization.response_message_id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.ERROR,
                        error=_local_execution_error(str(exc)),
                    ),
                    project_id=project_id,
                    conversation_id=authorization.conversation_id,
                )
                return
            except Exception:
                yield _project_sse(
                    "chat.error",
                    StreamChunk(
                        requestId=request_id,
                        messageId=authorization.response_message_id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.ERROR,
                        error=_local_execution_error(),
                    ),
                    project_id=project_id,
                    conversation_id=authorization.conversation_id,
                )
                return
            finally:
                if runtime_task is not None and not runtime_task.done():
                    token.cancel()
                    runtime_task.cancel()
                    await asyncio.gather(runtime_task, return_exceptions=True)

            coordinator = ProjectCoordinatorService(repository.db_path)
            coordinator.refresh_highlighted_pending_item(project_id)
            coordinator.refresh_expert_statuses(project_id)
            if result.status != SkillRunStatus.COMPLETED:
                yield _project_sse(
                    "chat.error",
                    StreamChunk(
                        requestId=request_id,
                        messageId=authorization.response_message_id,
                        requestTurnId=request_turn_id,
                        responseTurnId=response_turn_id,
                        type=StreamChunkType.ERROR,
                        error=_local_execution_error(),
                    ),
                    project_id=project_id,
                    conversation_id=authorization.conversation_id,
                )
                return
            yield _project_sse(
                "chat.completed",
                StreamChunk(
                    requestId=request_id,
                    messageId=authorization.response_message_id,
                    requestTurnId=request_turn_id,
                    responseTurnId=response_turn_id,
                    type=StreamChunkType.COMPLETED,
                ),
                project_id=project_id,
                conversation_id=authorization.conversation_id,
            )
        finally:
            if runtime_task is not None and not runtime_task.done():
                token.cancel()
                runtime_task.cancel()
                await asyncio.gather(runtime_task, return_exceptions=True)
            sessions.remove(request_id)

    return StreamingResponse(events(), media_type="text/event-stream")


@router.post("/chat/cancel/{request_id}", response_model=CancelChatResponse)
async def cancel_chat(request_id: str) -> CancelChatResponse:
    return CancelChatResponse(requestId=request_id, canceled=sessions.cancel(request_id))


@router.post(
    "/projects/{project_id}/chat/cancel/{request_id}",
    response_model=CancelChatResponse,
)
async def cancel_project_chat(project_id: str, request_id: str) -> CancelChatResponse:
    _ = project_id
    return CancelChatResponse(requestId=request_id, canceled=sessions.cancel(request_id))


def _sse(event: str, chunk: StreamChunk) -> str:
    return f"event: {event}\ndata: {json.dumps(chunk.model_dump(mode='json'), ensure_ascii=False)}\n\n"


def _progress_emitter(
    queue: asyncio.Queue[ChatProgress],
) -> ChatProgressEmitter:
    return ChatProgressEmitter(queue.put_nowait)


def _local_execution_error(message: str | None = None) -> LLMError:
    return LLMError(
        code=LLMErrorCode.UNKNOWN,
        message=message or "本地执行未完成，请检查配置或重新发起操作。",
        retryable=False,
        userActions=[],
    )


def _project_sse(
    event: str,
    chunk: StreamChunk,
    *,
    project_id: str,
    conversation_id: str,
    user_message_id: str | None = None,
) -> str:
    payload = chunk.model_dump(mode="json")
    payload["projectId"] = project_id
    payload["conversationId"] = conversation_id
    if user_message_id:
        payload["userMessageId"] = user_message_id
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _validate_turn_context(
    project_id: str,
    conversation_id: str,
    request: PersistedChatRequest,
) -> None:
    if not request.turnContext:
        return
    context_project_id = request.turnContext.get("projectId")
    context_conversation_id = request.turnContext.get("conversationId")
    if context_project_id and context_project_id != project_id:
        raise ConversationContextError(
            "PROJECT_CONTEXT_MISMATCH",
            "Project context does not match the current project.",
        )
    if context_conversation_id and context_conversation_id != conversation_id:
        raise ConversationContextError(
            "PROJECT_CONTEXT_MISMATCH",
            "Conversation context does not match the current project.",
        )


def _validate_kickoff_request(workspace, request: PersistedChatRequest) -> None:
    kickoff = getattr(workspace, "kickoff", None)
    if kickoff is None or kickoff.turnId != request.kickoffTurnId:
        raise ConversationContextError(
            "STALE_CONVERSATION_TURN",
            "Project kickoff turn no longer matches this project.",
        )
    if request.content.strip() != kickoff.content:
        raise ConversationContextError(
            "PROJECT_CONTEXT_MISMATCH",
            "Kickoff content does not match the original project idea.",
        )
    if request.projectExpertId != kickoff.projectExpertId:
        raise ConversationContextError(
            "PROJECT_CONTEXT_MISMATCH",
            "Kickoff expert does not match the original project expert.",
        )
    if request.threadId != kickoff.conversationId:
        raise ConversationContextError(
            "PROJECT_CONTEXT_MISMATCH",
            "Kickoff conversation does not match the original project conversation.",
        )
    if request.clientTurnId != kickoff.clientTurnId:
        raise ConversationContextError(
            "STALE_CONVERSATION_TURN",
            "Kickoff client turn does not match the original request.",
        )
    if (
        request.expertType
        and canonical_expert_type(request.expertType) != kickoff.expertType
    ):
        raise ConversationContextError(
            "PROJECT_CONTEXT_MISMATCH",
            "Kickoff expert type does not match the original project expert.",
        )
    context_turn_id = (request.turnContext or {}).get("turnId")
    if context_turn_id and context_turn_id != kickoff.turnId:
        raise ConversationContextError(
            "STALE_CONVERSATION_TURN",
            "Kickoff turn context does not match the original request.",
        )


def _conversation_messages(workspace, conversation_id: str):
    for expert_conversation in getattr(workspace, "expertConversations", []) or []:
        if expert_conversation.id == conversation_id:
            return expert_conversation.messages
    if workspace.conversation.id == conversation_id:
        return workspace.conversation.messages
    return []


def _request_turn_id(request: PersistedChatRequest) -> str:
    if request.turnContext and request.turnContext.get("turnId"):
        return str(request.turnContext["turnId"])
    if request.clientTurnId:
        return str(request.clientTurnId)
    return f"turn_{uuid.uuid4().hex}"


def _client_turn_id(request: PersistedChatRequest, request_turn_id: str) -> str:
    if request.clientTurnId:
        return request.clientTurnId
    return request_turn_id


def _response_turn_id(assistant_message) -> str:
    metadata = assistant_message.metadata or {}
    return str(
        metadata.get("responseTurnId")
        or metadata.get("turnId")
        or f"turn_{uuid.uuid4().hex}"
    )


def _answer_submission(
    request: PersistedChatRequest,
    project_id: str,
    conversation_id: str,
    client_turn_id: str,
) -> ClarificationSubmission:
    answer = request.structuredAnswer
    source_message_id = request.sourceMessageId

    if answer is not None:
        if answer.projectId and answer.projectId != project_id:
            raise ConversationContextError(
                "PROJECT_CONTEXT_MISMATCH",
                "Structured answer project does not match the current project.",
            )
        if answer.conversationId and answer.conversationId != conversation_id:
            raise ConversationContextError(
                "PROJECT_CONTEXT_MISMATCH",
                "Structured answer conversation does not match the current project.",
            )
        if answer.clientTurnId and answer.clientTurnId != client_turn_id:
            raise ConversationContextError(
                "STALE_CONVERSATION_TURN",
                "Structured answer turn does not match the submitted turn.",
            )
        if isinstance(answer, ClarificationBatchAnswerInput):
            if source_message_id and source_message_id != answer.sourceMessageId:
                raise ConversationContextError(
                    "PROJECT_CONTEXT_MISMATCH",
                    "Structured answer source message does not match the submitted message.",
                )
            return ClarificationSubmission(
                source_message_id=answer.sourceMessageId,
                answers=tuple(
                    ClarificationAnswerValue(
                        question_id=item.questionId,
                        selected_option_ids=tuple(item.selectedOptionIds),
                        text_input=item.textInput,
                    )
                    for item in answer.answers
                ),
                answer_type="batch",
                require_complete=True,
            )
        if isinstance(answer, SingleChoiceAnswerInput):
            value = ClarificationAnswerValue(
                question_id=answer.questionId,
                selected_option_ids=(answer.optionId,),
                text_input=answer.optionLabel or request.textInput,
            )
            return ClarificationSubmission(source_message_id, (value,), "single")
        if isinstance(answer, MultipleChoiceAnswerInput):
            value = ClarificationAnswerValue(
                question_id=answer.questionId,
                selected_option_ids=tuple(answer.optionIds),
                text_input="、".join(answer.optionLabels) or request.textInput,
            )
            return ClarificationSubmission(source_message_id, (value,), "multiple")
        if isinstance(answer, TextQuestionAnswerInput):
            value = ClarificationAnswerValue(
                question_id=answer.questionId,
                text_input=answer.text or request.textInput,
            )
            return ClarificationSubmission(source_message_id, (value,), "text")

    question_id = request.questionId
    selected_option_ids = tuple(
        str(item) for item in (request.selectedOptionIds or []) if item
    )
    if not question_id:
        return ClarificationSubmission(source_message_id, ())
    answer_type = "multiple" if len(selected_option_ids) > 1 else (
        "single" if selected_option_ids else "text"
    )
    return ClarificationSubmission(
        source_message_id,
        (
            ClarificationAnswerValue(
                question_id=question_id,
                selected_option_ids=selected_option_ids,
                text_input=request.textInput,
            ),
        ),
        answer_type,
    )


def _confirmed_cad_answer_prompt(
    repository: ProjectRepository,
    project_id: str,
    submission: ClarificationSubmission,
) -> str:
    if not submission.source_message_id:
        return "用户已提交 CAD 结构输入确认。"
    with repository._connect() as conn:
        row = conn.execute(
            """
            SELECT structured_payload_json FROM messages
            WHERE id = ? AND project_id = ?
            """,
            (submission.source_message_id, project_id),
        ).fetchone()
    payload = (
        json.loads(str(row["structured_payload_json"]))
        if row is not None and row["structured_payload_json"]
        else {}
    )
    raw_questions = payload.get("questions") if isinstance(payload, dict) else None
    if not isinstance(raw_questions, list):
        single = payload.get("question") if isinstance(payload, dict) else None
        raw_questions = [single] if isinstance(single, dict) else []
    questions = {
        str(question.get("id")): question
        for question in raw_questions
        if isinstance(question, dict) and question.get("id")
    }
    lines = ["用户已完整确认本轮 CAD 结构输入；以下内容来自服务端验证后的问题与答案："]
    for answer in submission.answers:
        question = questions.get(answer.question_id, {})
        option_map = {
            str(option.get("id")): str(option.get("label") or option.get("id"))
            for option in question.get("options", [])
            if isinstance(option, dict) and option.get("id")
        }
        labels = [
            option_map[option_id]
            for option_id in answer.selected_option_ids
            if option_id in option_map
        ]
        value = "、".join(labels) or str(answer.text_input or "")
        lines.append(
            f"- {answer.question_id}｜{question.get('text', '')}｜{value}"
        )
    lines.append("请根据当前完整 CAD intake：若仍缺机械档案则返回下一组结构化澄清；否则形成 cadDraft。")
    return "\n".join(lines)


def _project_error_to_llm_error(exc: ProjectError):
    if isinstance(exc, ConversationContextError):
        if exc.code == "CAD_INPUT_INVALID":
            return LLMError(
                code=LLMErrorCode.INVALID_REQUEST,
                message=exc.message,
                retryable=False,
                userActions=[],
            )
        try:
            return make_llm_error(LLMErrorCode(exc.code))
        except ValueError:
            return make_llm_error(LLMErrorCode.UNKNOWN)
    return make_llm_error(LLMErrorCode.UNKNOWN)


def _get_llm_config(
    *,
    owner_kind: str | None = None,
    owner_id: str | None = None,
):
    return require_llm_config(
        data_dir=settings.data_dir,
        credential_store=credential_store_factory(),
        credential_service=settings.credential_service,
        credential_account=settings.credential_account,
        workload=ModelWorkload.CREATION,
        owner_kind=owner_kind,
        owner_id=owner_id,
    )


def _project_creator_candidate(
    repository: ProjectRepository,
    *,
    project_id: str,
    source_message_id: str,
    source_turn_id: str | None,
    payload: dict | None,
) -> None:
    if not isinstance(payload, dict):
        return
    candidate = payload.get("projectDraft")
    if not isinstance(candidate, dict):
        return
    try:
        draft = ConversationProjectDraftV1.model_validate(candidate)
    except ValidationError:
        return
    CreatorRepository(repository.db_path.parents[1]).project_conversation_draft(
        project_id,
        source_message_id=source_message_id,
        source_turn_id=source_turn_id,
        draft=draft,
    )


def _runtime_ui_payload(
    provider_payload: dict[str, object] | None,
    code_run: CodeRun | None,
    cad_run: CadRun | None,
) -> dict[str, object] | None:
    if code_run is not None:
        return code_artifact_payload(code_run)
    if cad_run is not None:
        return cad_artifact_payload(cad_run)
    if isinstance(provider_payload, dict) and provider_payload.get("type") in {
        "code_artifact",
        "cad_artifact",
    }:
        return None
    return provider_payload


def _mark_code_implementation_started(
    repository: ProjectRepository,
    project_id: str,
) -> None:
    now = datetime.now(UTC).isoformat()
    with repository._connect() as conn:
        conn.execute(
            "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
            (ProjectStage.IMPLEMENTING.value, now, project_id),
        )


async def _duplicate_project_events(
    *,
    request_id: str,
    project_id: str,
    conversation_id: str,
    duplicate: tuple,
    request_turn_id: str,
) -> AsyncIterator[str]:
    user_message, assistant_message = duplicate
    response_turn_id = _response_turn_id(assistant_message)
    yield _project_sse(
        "chat.started",
        StreamChunk(
            requestId=request_id,
            messageId=assistant_message.id,
            requestTurnId=request_turn_id,
            responseTurnId=response_turn_id,
            type=StreamChunkType.START,
            model=assistant_message.model,
        ),
        project_id=project_id,
        conversation_id=conversation_id,
        user_message_id=user_message.id,
    )
    event = "chat.completed"
    chunk_type = StreamChunkType.COMPLETED
    if assistant_message.status == ChatMessageStatus.FAILED:
        event = "chat.error"
        chunk_type = StreamChunkType.ERROR
    elif assistant_message.status == ChatMessageStatus.CANCELED:
        event = "chat.canceled"
        chunk_type = StreamChunkType.CANCELED
    yield _project_sse(
        event,
        StreamChunk(
            requestId=request_id,
            messageId=assistant_message.id,
            requestTurnId=request_turn_id,
            responseTurnId=response_turn_id,
            type=chunk_type,
            accumulatedContent=assistant_message.content,
            model=assistant_message.model,
            error=assistant_message.error,
            usage=assistant_message.usage,
            structuredPayload=assistant_message.structuredPayload,
        ),
        project_id=project_id,
        conversation_id=conversation_id,
        user_message_id=user_message.id,
    )


async def _running_project_events(
    *,
    request_id: str,
    project_id: str,
    conversation_id: str,
    duplicate: tuple,
    request_turn_id: str,
) -> AsyncIterator[str]:
    user_message, assistant_message = duplicate
    response_turn_id = _response_turn_id(assistant_message)
    yield _project_sse(
        "chat.started",
        StreamChunk(
            requestId=request_id,
            messageId=assistant_message.id,
            requestTurnId=request_turn_id,
            responseTurnId=response_turn_id,
            type=StreamChunkType.START,
            model=assistant_message.model,
        ),
        project_id=project_id,
        conversation_id=conversation_id,
        user_message_id=user_message.id,
    )
