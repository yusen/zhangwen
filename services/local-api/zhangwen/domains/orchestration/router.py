"""Unified per-Work conversation and Turn API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from zhangwen.config import settings
from zhangwen.creator.repository import CreatorError
from zhangwen.domains.orchestration.models import (
    CreateUnifiedTurnRequest,
    UnifiedConversationResponse,
    UnifiedTurnResponse,
)
from zhangwen.domains.orchestration.repository import TurnConflictError
from zhangwen.domains.orchestration.resolver import RevisionResolutionError
from zhangwen.domains.orchestration.service import UnifiedTurnService
from zhangwen.projects.errors import ProjectError


router = APIRouter(prefix="/api/works", tags=["work-conversation"])


@router.post(
    "/{work_id}/turns",
    response_model=UnifiedTurnResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_turn(
    work_id: str,
    request: CreateUnifiedTurnRequest,
) -> UnifiedTurnResponse:
    try:
        turn = await UnifiedTurnService(settings.data_dir).create(work_id, request)
        return UnifiedTurnResponse(turn=turn)
    except TurnConflictError as exc:
        raise _error(409, "TURN_IDEMPOTENCY_CONFLICT", str(exc), True) from exc
    except RevisionResolutionError as exc:
        raise _error(
            503,
            "TURN_CAPABILITY_UNAVAILABLE",
            "掌问当前无法安全固定所需能力，请稍后重试。",
            True,
        ) from exc
    except CreatorError as exc:
        raise _error(exc.status_code, exc.code, exc.message, False) from exc
    except ProjectError as exc:
        raise _error(
            getattr(exc, "status_code", 404),
            exc.__class__.__name__.upper(),
            str(exc),
            False,
        ) from exc


@router.get(
    "/{work_id}/conversation",
    response_model=UnifiedConversationResponse,
)
async def get_conversation(work_id: str) -> UnifiedConversationResponse:
    try:
        return UnifiedConversationResponse(
            turns=UnifiedTurnService(settings.data_dir).conversation(work_id)
        )
    except CreatorError as exc:
        raise _error(exc.status_code, exc.code, exc.message, False) from exc
    except ProjectError as exc:
        raise _error(
            getattr(exc, "status_code", 404),
            exc.__class__.__name__.upper(),
            str(exc),
            False,
        ) from exc


def _error(
    status_code: int,
    code: str,
    message: str,
    retryable: bool,
) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message, "retryable": retryable},
    )
