"""Unified Turn orchestration service with pinned revisions and safe fallback."""

from __future__ import annotations

from pathlib import Path

from zhangwen.domains.orchestration.executor import (
    LocalInternalUnitExecutor,
    UnitExecutionResult,
    UnitExecutor,
)
from zhangwen.domains.orchestration.models import (
    CreateUnifiedTurnRequest,
    InternalUnit,
    InvocationFallback,
    InvocationFallbackCode,
    InvocationStepStatus,
    UnifiedTurn,
    UnifiedTurnStatus,
)
from zhangwen.domains.orchestration.planner import InvocationPlanner
from zhangwen.domains.orchestration.repository import (
    StepOutcome,
    TurnConflictError,
    TurnRepository,
)
from zhangwen.domains.orchestration.resolver import CapabilityRevisionResolver
from zhangwen.domains.works.repository import WorkRepository
from zhangwen.projects.repository import ProjectRepository
from zhangwen.settings.models import ModelWorkload
from zhangwen.settings.provider_repository import ProviderSettingsRepository


class UnifiedTurnService:
    def __init__(
        self,
        data_dir: Path,
        *,
        executor: UnitExecutor | None = None,
    ) -> None:
        db_path = ProjectRepository(data_dir).db_path
        self._works = WorkRepository(data_dir)
        self._repository = TurnRepository(db_path)
        self._resolver = CapabilityRevisionResolver(data_dir, db_path)
        self._planner = InvocationPlanner()
        self._executor = executor or LocalInternalUnitExecutor()
        self._model_settings = ProviderSettingsRepository(data_dir)

    async def create(
        self,
        work_id: str,
        request: CreateUnifiedTurnRequest,
    ) -> UnifiedTurn:
        message = request.message.strip()
        snapshot = self._works.snapshot(work_id)
        existing = self._repository.find_by_idempotency(
            work_id,
            request.idempotency_key,
        )
        if existing is not None:
            if existing.user_message != message:
                raise TurnConflictError(
                    "同一幂等键不能提交不同的作品补充。"
                )
            return existing
        planned = self._planner.plan(snapshot, message)
        resolutions = self._resolver.resolve(planned.units)
        runtime_selection = self._model_settings.resolve_runtime(
            ModelWorkload.CREATION
        ).selection
        turn, created = self._repository.start(
            work_id=work_id,
            idempotency_key=request.idempotency_key,
            message=message,
            intent=planned.intent,
            work_snapshot=snapshot.model_dump(mode="json", by_alias=True),
            resolutions=resolutions,
            runtime_selection=runtime_selection,
        )
        if not created:
            if turn.user_message != message:
                raise TurnConflictError(
                    "同一幂等键不能提交不同的作品补充。"
                )
            return turn

        outcomes: list[StepOutcome] = []
        fragments: list[str] = []
        blocked_by_dependency = False
        for resolution in resolutions:
            started_at = _now()
            if blocked_by_dependency:
                outcomes.append(
                    _fallback_outcome(
                        resolution.unit,
                        InvocationFallbackCode.POLICY_BLOCKED,
                        "前一项检查未完成，这部分已安全暂停。",
                        started_at,
                    )
                )
                continue
            try:
                result = await self._executor.execute(
                    unit=resolution.unit,
                    message=message,
                    snapshot=snapshot,
                )
                _validate_result(result)
                completed_at = _now()
                outcomes.append(
                    StepOutcome(
                        unit=resolution.unit,
                        status=InvocationStepStatus.COMPLETED,
                        output_summary=result.summary,
                        fallback=None,
                        started_at=started_at,
                        completed_at=completed_at,
                    )
                )
                fragments.append(result.response_fragment)
            except (OSError, RuntimeError, ValueError):
                outcomes.append(
                    _fallback_outcome(
                        resolution.unit,
                        InvocationFallbackCode.INTERNAL_FAILURE,
                        "这部分检查暂时没有完成，已保留输入并停止相关后续动作。",
                        started_at,
                    )
                )
                blocked_by_dependency = True

        completed_count = sum(
            outcome.status is InvocationStepStatus.COMPLETED for outcome in outcomes
        )
        status = (
            UnifiedTurnStatus.COMPLETED
            if completed_count == len(outcomes)
            else UnifiedTurnStatus.DEGRADED
            if completed_count
            else UnifiedTurnStatus.FAILED
        )
        assistant_response, natural_status = _compose_response(status, fragments)
        return self._repository.finalize(
            turn.id,
            status=status,
            assistant_response=assistant_response,
            natural_status=natural_status,
            outcomes=outcomes,
        )

    def conversation(self, work_id: str) -> list[UnifiedTurn]:
        self._works.snapshot(work_id)
        return self._repository.list(work_id)


def _validate_result(result: UnitExecutionResult) -> None:
    if not result.summary.strip() or not result.response_fragment.strip():
        raise ValueError("Internal unit output is empty")
    if len(result.summary) > 1000 or len(result.response_fragment) > 1000:
        raise ValueError("Internal unit output exceeds the bounded response")


def _fallback_outcome(
    unit: InternalUnit,
    code: InvocationFallbackCode,
    message: str,
    started_at: str,
) -> StepOutcome:
    return StepOutcome(
        unit=unit,
        status=InvocationStepStatus.FALLBACK,
        output_summary=None,
        fallback=InvocationFallback(code=code, naturalMessage=message),
        started_at=started_at,
        completed_at=_now(),
    )


def _compose_response(
    status: UnifiedTurnStatus,
    fragments: list[str],
) -> tuple[str, str]:
    if status is UnifiedTurnStatus.FAILED:
        return (
            "你的补充已经保留，但这次没有安全完成。请稍后重试。",
            "掌问已保留这次补充，等待安全重试。",
        )
    suffix = (
        "有一部分检查暂时没有完成，我会保留当前结果并停止相关后续动作。"
        if status is UnifiedTurnStatus.DEGRADED
        else "本地校验完成后，我会更新作品状态和唯一下一步。"
    )
    return (
        "收到。" + "".join(fragments) + suffix,
        (
            "掌问已经记录这次补充，部分检查稍后继续。"
            if status is UnifiedTurnStatus.DEGRADED
            else "掌问已经记录这次补充，并完成当前规划。"
        ),
    )


def _now() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()
