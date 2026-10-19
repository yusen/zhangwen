"""Strict, privacy-bounded Creator metric events.

Metric rows are projections only. They never drive lifecycle state or replace
Creator evidence. Event IDs are deterministic so an idempotent business
transaction can append its metric exactly once.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import UTC, datetime
from typing import Annotated, Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter


class CreatorMetricError(RuntimeError):
    """Raised when a trigger is reused with a different strict payload."""


class _MetricBase(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    schema_version: Literal[1] = Field(default=1, alias="schemaVersion")
    trigger_id: str = Field(alias="triggerId", min_length=16, max_length=80)


class WorkCreatedMetric(_MetricBase):
    metric: Literal["WORK_CREATED"] = "WORK_CREATED"
    origin: Literal["CREATOR", "LEGACY"]


class GoalConfirmedMetric(_MetricBase):
    metric: Literal["GOAL_CONFIRMED"] = "GOAL_CONFIRMED"
    revision: int = Field(ge=1)


class SolutionConfirmedMetric(_MetricBase):
    metric: Literal["SOLUTION_CONFIRMED"] = "SOLUTION_CONFIRMED"
    revision: int = Field(ge=1)
    capability_class: Literal[
        "SENSING", "RESPONSE", "VISION_AUDIO", "MIXED"
    ] = Field(alias="capabilityClass")


class DigitalBehaviorObservedMetric(_MetricBase):
    metric: Literal["DIGITAL_BEHAVIOR_OBSERVED"] = "DIGITAL_BEHAVIOR_OBSERVED"
    elapsed_ms: int = Field(alias="elapsedMs", ge=0)


class SimulationFinishedMetric(_MetricBase):
    metric: Literal["SIMULATION_FINISHED"] = "SIMULATION_FINISHED"
    passed: bool
    required_scenario_count: int = Field(alias="requiredScenarioCount", ge=0)
    passed_required_scenario_count: int = Field(
        alias="passedRequiredScenarioCount", ge=0
    )
    failure_category: Literal[
        "PARAMETER", "LOGIC", "IO", "CAPABILITY", "UNKNOWN", "NONE"
    ] = Field(alias="failureCategory")


class FirstDeploymentFinishedMetric(_MetricBase):
    metric: Literal["FIRST_DEPLOYMENT_FINISHED"] = "FIRST_DEPLOYMENT_FINISHED"
    passed: bool
    channel: Literal["USB_SERIAL", "ESP_CLAW"]
    recovery_required: bool = Field(alias="recoveryRequired")


class PhysicalBehaviorFinishedMetric(_MetricBase):
    metric: Literal["PHYSICAL_BEHAVIOR_FINISHED"] = "PHYSICAL_BEHAVIOR_FINISHED"
    passed_scenario_count: int = Field(alias="passedScenarioCount", ge=0)
    compared_scenario_count: int = Field(alias="comparedScenarioCount", ge=0)
    simulation_consistent: bool = Field(alias="simulationConsistent")


class RecoveryFinishedMetric(_MetricBase):
    metric: Literal["RECOVERY_FINISHED"] = "RECOVERY_FINISHED"
    action: Literal[
        "USB_UPLOAD", "ESP_CLAW_UPLOAD", "PARAMETER_SYNC", "SIMULATION"
    ]
    passed: bool


class WorkAcceptedMetric(_MetricBase):
    metric: Literal["WORK_ACCEPTED"] = "WORK_ACCEPTED"
    elapsed_ms: int = Field(alias="elapsedMs", ge=0)


class DeliveryExportedMetric(_MetricBase):
    metric: Literal["DELIVERY_EXPORTED"] = "DELIVERY_EXPORTED"
    variant: Literal["SHARE", "REPRODUCIBLE", "TEMPLATE"]
    required_evidence_count: int = Field(alias="requiredEvidenceCount", ge=0)
    current_evidence_count: int = Field(alias="currentEvidenceCount", ge=0)
    coverage_ratio: float = Field(alias="coverageRatio", ge=0, le=1)


class ReproductionFinishedMetric(_MetricBase):
    metric: Literal["REPRODUCTION_FINISHED"] = "REPRODUCTION_FINISHED"
    passed: bool


class LegacyMigrationFinishedMetric(_MetricBase):
    metric: Literal["LEGACY_MIGRATION_FINISHED"] = "LEGACY_MIGRATION_FINISHED"
    from_schema_version: int = Field(alias="fromSchemaVersion", ge=0)
    migrated_row_count: int = Field(alias="migratedRowCount", ge=0)
    zero_data_loss: bool = Field(alias="zeroDataLoss")
    passed: bool


CreatorMetricPayload = Annotated[
    WorkCreatedMetric
    | GoalConfirmedMetric
    | SolutionConfirmedMetric
    | DigitalBehaviorObservedMetric
    | SimulationFinishedMetric
    | FirstDeploymentFinishedMetric
    | PhysicalBehaviorFinishedMetric
    | RecoveryFinishedMetric
    | WorkAcceptedMetric
    | DeliveryExportedMetric
    | ReproductionFinishedMetric
    | LegacyMigrationFinishedMetric,
    Field(discriminator="metric"),
]

CREATOR_METRIC_ADAPTER = TypeAdapter(CreatorMetricPayload)


def metric_trigger_id(
    *, metric: str, project_id: str, source_key: str
) -> str:
    """Return an opaque stable ID without exposing project or source IDs."""

    digest = hashlib.sha256(
        f"creator-metric/v1\0{metric}\0{project_id}\0{source_key}".encode("utf-8")
    ).hexdigest()
    return f"cmetric_{digest[:40]}"


def append_creator_metric(
    conn: sqlite3.Connection,
    project_id: str,
    payload: CreatorMetricPayload,
) -> bool:
    """Append a strict metric once inside the caller's open transaction."""

    parsed = CREATOR_METRIC_ADAPTER.validate_python(payload)
    serialized = json.dumps(
        parsed.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    event_digest = hashlib.sha256(
        f"{parsed.metric}\0{parsed.trigger_id}".encode("utf-8")
    ).hexdigest()
    event_id = f"cevt_metric_{event_digest[:40]}"
    existing = conn.execute(
        "SELECT event_type, payload_json FROM creator_events WHERE id = ?",
        (event_id,),
    ).fetchone()
    if existing is not None:
        if str(existing["event_type"]) != "METRIC" or str(
            existing["payload_json"]
        ) != serialized:
            raise CreatorMetricError(
                "同一 Creator 指标触发 ID 不能用于不同载荷。"
            )
        return False
    conn.execute(
        """
        INSERT INTO creator_events (id, project_id, event_type, payload_json, created_at)
        VALUES (?, ?, 'METRIC', ?, ?)
        """,
        (event_id, project_id, serialized, datetime.now(UTC).isoformat()),
    )
    return True


def append_creator_system_metric(
    conn: sqlite3.Connection,
    payload: CreatorMetricPayload,
) -> bool:
    """Append one database-scoped metric without inventing a project owner."""

    parsed = CREATOR_METRIC_ADAPTER.validate_python(payload)
    serialized = json.dumps(
        parsed.model_dump(mode="json", by_alias=True),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    event_digest = hashlib.sha256(
        f"{parsed.metric}\0{parsed.trigger_id}".encode("utf-8")
    ).hexdigest()
    event_id = f"cevt_system_metric_{event_digest[:40]}"
    existing = conn.execute(
        """
        SELECT event_type, payload_json
        FROM creator_system_metrics
        WHERE id = ?
        """,
        (event_id,),
    ).fetchone()
    if existing is not None:
        event_type = str(existing[0])
        payload_json = str(existing[1])
        if event_type != "METRIC" or payload_json != serialized:
            raise CreatorMetricError(
                "同一系统指标触发 ID 不能用于不同载荷。"
            )
        return False
    conn.execute(
        """
        INSERT INTO creator_system_metrics (
          id, event_type, payload_json, created_at
        ) VALUES (?, 'METRIC', ?, ?)
        """,
        (event_id, serialized, datetime.now(UTC).isoformat()),
    )
    return True


_DEVICE_TERMINAL_STATUSES = frozenset(
    {"COMPLETED", "FAILED", "CANCELED", "TIMED_OUT"}
)


def append_device_operation_metrics(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    operation_id: str,
    kind: str,
    status: str,
    metadata: Mapping[str, object],
    steps: Sequence[Mapping[str, object]],
) -> None:
    """Project terminal device facts in the same transaction as the operation.

    Device APIs are also used by legacy teaching projects. Metrics are emitted
    only after a project has entered Creator V3, and never carry a device,
    account, project, port, endpoint, or operation identifier in their payload.
    """

    if status not in _DEVICE_TERMINAL_STATUSES:
        return
    if conn.execute(
        "SELECT 1 FROM creator_work_state WHERE project_id = ?",
        (project_id,),
    ).fetchone() is None:
        return

    recovery = _device_recovery_outcome(kind=kind, metadata=metadata, steps=steps)
    if kind == "UPLOAD_CODE":
        channel_value = metadata.get("channel")
        if channel_value in {"USB_SERIAL", "ESP_CLAW"} and not _has_metric_payload(
            conn,
            project_id=project_id,
            metric="FIRST_DEPLOYMENT_FINISHED",
            field="channel",
            value=channel_value,
        ):
            append_creator_metric(
                conn,
                project_id,
                FirstDeploymentFinishedMetric(
                    triggerId=metric_trigger_id(
                        metric="FIRST_DEPLOYMENT_FINISHED",
                        project_id=project_id,
                        source_key=f"first-deployment:{channel_value}",
                    ),
                    passed=status == "COMPLETED",
                    channel=channel_value,
                    recoveryRequired=recovery is not None,
                ),
            )

    if recovery is None:
        return
    recovery_action, recovery_passed = recovery
    append_creator_metric(
        conn,
        project_id,
        RecoveryFinishedMetric(
            triggerId=metric_trigger_id(
                metric="RECOVERY_FINISHED",
                project_id=project_id,
                source_key=operation_id,
            ),
            action=recovery_action,
            passed=recovery_passed,
        ),
    )


def _device_recovery_outcome(
    *,
    kind: str,
    metadata: Mapping[str, object],
    steps: Sequence[Mapping[str, object]],
) -> tuple[
    Literal["USB_UPLOAD", "ESP_CLAW_UPLOAD", "PARAMETER_SYNC"], bool
] | None:
    restore_steps = [step for step in steps if step.get("phase") == "RESTORE"]
    failure_evidence = metadata.get("failureEvidence")
    evidence = failure_evidence if isinstance(failure_evidence, Mapping) else {}
    explicit_restore = evidence.get("restoreSucceeded")
    channel = metadata.get("channel")
    espclaw_outcomes = [
        metadata.get(field)
        for field in ("runtimeStopOk", "rollbackOk")
        if field in metadata
    ]
    attempted = bool(restore_steps) or isinstance(explicit_restore, bool) or bool(
        espclaw_outcomes
    )
    if not attempted:
        return None

    step_ok = all(step.get("status") == "COMPLETED" for step in restore_steps)
    explicit_ok = explicit_restore is not False
    espclaw_ok = all(value is True for value in espclaw_outcomes)
    passed = step_ok and explicit_ok and espclaw_ok

    if kind == "SYNC_PARAMETERS":
        return "PARAMETER_SYNC", passed
    if kind == "UPLOAD_CODE" and channel == "ESP_CLAW":
        return "ESP_CLAW_UPLOAD", passed
    if kind == "UPLOAD_CODE" and channel == "USB_SERIAL":
        return "USB_UPLOAD", passed
    return None


def _has_metric_payload(
    conn: sqlite3.Connection,
    *,
    project_id: str,
    metric: str,
    field: str,
    value: object,
) -> bool:
    rows = conn.execute(
        """
        SELECT payload_json
        FROM creator_events
        WHERE project_id = ? AND event_type = 'METRIC'
        """,
        (project_id,),
    ).fetchall()
    for row in rows:
        try:
            payload = json.loads(str(row["payload_json"]))
        except (json.JSONDecodeError, TypeError):
            continue
        if payload.get("metric") == metric and payload.get(field) == value:
            return True
    return False
