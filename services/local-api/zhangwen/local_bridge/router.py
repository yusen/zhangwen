from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field
from fastapi import APIRouter, HTTPException, Request

from zhangwen.host import has_desktop_host_access
from zhangwen.local_bridge.service import (
    LocalBridgeError,
    LocalBridgeService,
    require_loopback,
)


router = APIRouter(prefix="/api/local-bridge", tags=["local-bridge"])


class PairingStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    origin: str = Field(min_length=8, max_length=240)
    projectId: str = Field(min_length=1, max_length=160)
    capabilities: list[str] = Field(min_length=1, max_length=8)


class PairingClaimRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pairingId: str = Field(min_length=8, max_length=180)
    code: str = Field(pattern=r"^\d{6}$")


@router.get("/status")
async def bridge_status(request: Request) -> dict[str, object]:
    _require_loopback(request)
    return _call(lambda service: service.status(request))


@router.post("/pairing/start")
async def start_pairing(
    payload: PairingStartRequest, request: Request
) -> dict[str, object]:
    _require_loopback(request)
    if not has_desktop_host_access(request):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "BRIDGE_DESKTOP_CONFIRMATION_REQUIRED",
                "message": "配对挑战必须由已授权的桌面宿主创建并显示。",
                "retryable": False,
            },
        )
    return _call(
        lambda service: service.start_pairing(
            request,
            origin=payload.origin,
            project_id=payload.projectId,
            capabilities=payload.capabilities,
        )
    )


@router.post("/pairing/claim")
async def claim_pairing(
    payload: PairingClaimRequest, request: Request
) -> dict[str, object]:
    _require_loopback(request)
    return _call(
        lambda service: service.claim(
            request, pairing_id=payload.pairingId, code=payload.code
        )
    )


@router.post("/revoke")
async def revoke_current_lease(request: Request) -> dict[str, object]:
    _require_loopback(request)
    return _call(lambda service: service.revoke_current(request))


@router.get("/sessions")
async def list_bridge_sessions(request: Request) -> dict[str, object]:
    _require_loopback(request)
    _require_desktop(request)
    return {"sessions": _call(lambda service: service.list_sessions(request))}


@router.post("/sessions/{session_id}/revoke")
async def revoke_bridge_session(
    session_id: str, request: Request
) -> dict[str, object]:
    _require_loopback(request)
    _require_desktop(request)
    return _call(lambda service: service.revoke_session(request, session_id))


def _require_desktop(request: Request) -> None:
    if not has_desktop_host_access(request):
        raise HTTPException(
            status_code=403,
            detail={
                "code": "BRIDGE_DESKTOP_CAPABILITY_REQUIRED",
                "message": "该 Local Bridge 管理操作只允许桌面宿主。",
                "retryable": False,
            },
        )


def _require_loopback(request: Request) -> None:
    try:
        require_loopback(request)
    except LocalBridgeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc


def _call(action):
    try:
        return action(LocalBridgeService())
    except LocalBridgeError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail()) from exc
