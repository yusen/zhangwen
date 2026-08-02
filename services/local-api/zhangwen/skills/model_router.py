"""Provider-neutral deterministic model router for ZW-008."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.llm.contracts import LLMModelId, LLMProviderId
from zhangwen.skills.models import ModelRouteResult, ModelRouteStrategy


class ModelRouter:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path

    def route(
        self,
        *,
        agent_id: str,
        task_kind: str,
        strategy: ModelRouteStrategy,
    ) -> ModelRouteResult:
        if strategy == ModelRouteStrategy.QUALITY_FIRST:
            model = LLMModelId.DEEPSEEK_V4_PRO
            fallback = LLMModelId.DEEPSEEK_V4_FLASH
            cost = "HIGH"
            quality = "HIGH"
            reasoning = "质量优先任务使用 deepseek-v4-pro，失败时降级到 flash。"
        elif strategy in {ModelRouteStrategy.COST_FIRST, ModelRouteStrategy.FAST_FIRST}:
            model = LLMModelId.DEEPSEEK_V4_FLASH
            fallback = None
            cost = "LOW"
            quality = "STANDARD"
            reasoning = "成本或速度优先任务使用 deepseek-v4-flash。"
        else:
            model = (
                LLMModelId.DEEPSEEK_V4_PRO
                if task_kind.lower() in {"spec", "code", "cad"}
                else LLMModelId.DEEPSEEK_V4_FLASH
            )
            fallback = (
                LLMModelId.DEEPSEEK_V4_FLASH
                if model == LLMModelId.DEEPSEEK_V4_PRO
                else None
            )
            cost = "MEDIUM" if model == LLMModelId.DEEPSEEK_V4_PRO else "LOW"
            quality = "HIGH" if model == LLMModelId.DEEPSEEK_V4_PRO else "STANDARD"
            reasoning = "平衡策略按任务复杂度选择 DeepSeek 当前正式支持模型。"

        result = ModelRouteResult(
            provider=LLMProviderId.DEEPSEEK,
            model=model,
            strategy=strategy,
            retryCount=1,
            fallbackModel=fallback,
            costTier=cost,
            qualityTier=quality,
            reasoning=reasoning,
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
                  reasoning, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    _id("route"),
                    agent_id,
                    task_kind,
                    result.strategy.value,
                    result.provider.value,
                    result.model.value,
                    result.fallbackModel.value if result.fallbackModel else None,
                    result.retryCount,
                    result.costTier,
                    result.qualityTier,
                    result.reasoning,
                    now,
                ),
            )


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
