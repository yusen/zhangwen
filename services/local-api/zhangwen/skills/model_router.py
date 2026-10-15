"""Deterministic routing over the single versioned Provider settings platform."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.settings.models import ModelWorkload
from zhangwen.settings.provider_repository import (
    ProviderSettingsConflictError,
    ProviderSettingsRepository,
)
from zhangwen.skills.models import ModelRouteResult, ModelRouteStrategy


class ModelRouter:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._providers = ProviderSettingsRepository.from_db_path(db_path)

    def route(
        self,
        *,
        agent_id: str,
        task_kind: str,
        strategy: ModelRouteStrategy,
    ) -> ModelRouteResult:
        workload = _workload(task_kind, strategy)
        primary = self._providers.resolve_runtime(workload)
        try:
            fallback = self._providers.resolve_runtime(workload, fallback=True)
        except ProviderSettingsConflictError:
            fallback = None

        if strategy == ModelRouteStrategy.QUALITY_FIRST:
            cost = "HIGH"
            quality = "HIGH"
        elif strategy in {ModelRouteStrategy.COST_FIRST, ModelRouteStrategy.FAST_FIRST}:
            cost = "LOW"
            quality = "STANDARD"
        else:
            cost = "MEDIUM"
            quality = "HIGH" if workload == ModelWorkload.ENGINEERING else "STANDARD"

        selection = primary.selection
        fallback_selection = fallback.selection if fallback is not None else None
        result = ModelRouteResult(
            provider=selection.provider,
            model=selection.model,
            strategy=strategy,
            retryCount=1 if fallback_selection is not None else 0,
            fallbackModel=(
                fallback_selection.model if fallback_selection is not None else None
            ),
            providerConfigurationId=selection.provider_configuration_id,
            providerConfigurationRevisionId=(
                selection.provider_configuration_revision_id
            ),
            routingProfileRevisionId=selection.routing_profile_revision_id,
            fallbackProviderConfigurationId=(
                fallback_selection.provider_configuration_id
                if fallback_selection is not None
                else None
            ),
            workload=workload.value,
            costTier=cost,
            qualityTier=quality,
            reasoning=(
                "已按当前模型分工固定具体服务配置、模型和路由版本。"
                + (
                    " 隐私设置允许失败后使用已配置的备用服务。"
                    if fallback_selection is not None
                    else " 当前请求不会自动切换到其他服务。"
                )
            ),
        )
        self._record(agent_id, task_kind, result)
        return result

    def _record(
        self,
        agent_id: str,
        task_kind: str,
        result: ModelRouteResult,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """
                INSERT INTO model_route_audit (
                  id, agent_id, task_kind, strategy, provider, model,
                  fallback_model, retry_count, cost_tier, quality_tier,
                  reasoning, created_at, provider_configuration_id,
                  provider_configuration_revision_id,
                  routing_profile_revision_id, workload,
                  fallback_provider_configuration_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id("route"),
                    agent_id,
                    task_kind,
                    result.strategy.value,
                    result.provider.value,
                    str(result.model),
                    str(result.fallbackModel) if result.fallbackModel else None,
                    result.retryCount,
                    result.costTier,
                    result.qualityTier,
                    result.reasoning,
                    now,
                    result.providerConfigurationId,
                    result.providerConfigurationRevisionId,
                    result.routingProfileRevisionId,
                    result.workload,
                    result.fallbackProviderConfigurationId,
                ),
            )


def _workload(task_kind: str, strategy: ModelRouteStrategy) -> ModelWorkload:
    if strategy in {ModelRouteStrategy.COST_FIRST, ModelRouteStrategy.FAST_FIRST}:
        return ModelWorkload.CREATION
    normalized = task_kind.strip().lower()
    if normalized in {"spec", "code", "cad", "engineering", "structure"}:
        return ModelWorkload.ENGINEERING
    if normalized in {"vision", "image", "visual"}:
        return ModelWorkload.VISION
    if normalized in {"lesson", "document", "research", "long_document"}:
        return ModelWorkload.LONG_DOCUMENT
    return ModelWorkload.ENGINEERING if strategy == ModelRouteStrategy.QUALITY_FIRST else ModelWorkload.CREATION


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
