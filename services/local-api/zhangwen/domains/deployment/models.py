"""Strict contracts for simulation-to-device deployment."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from zhangwen.devices.models import DeviceSession
from zhangwen.domains.simulation.models import SimulationChipFamily, SimulationCodeFile


class DeploymentModel(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )


class DeploymentBundleStatus(StrEnum):
    CURRENT = "CURRENT"
    STALE = "STALE"


class ProjectDeploymentStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DRY_RUN_COMPLETE = "DRY_RUN_COMPLETE"
    COMPLETED = "COMPLETED"
    BLOCKED = "BLOCKED"
    FAILED = "FAILED"
    CANCELED = "CANCELED"
    TIMED_OUT = "TIMED_OUT"
    STALE = "STALE"


class DeploymentTransportMode(StrEnum):
    DRY_RUN = "DRY_RUN"
    MOCK = "MOCK"
    LOCAL_SERIAL = "LOCAL_SERIAL"


class DeploymentBundle(DeploymentModel):
    id: str
    work_id: str = Field(alias="workId")
    simulation_run_id: str = Field(alias="simulationRunId")
    simulation_project_revision_id: str = Field(alias="simulationProjectRevisionId")
    board_package_revision_id: str = Field(alias="boardPackageRevisionId")
    chip_family: SimulationChipFamily = Field(alias="chipFamily")
    runtime_package_revision_id: str = Field(alias="runtimePackageRevisionId")
    files: list[SimulationCodeFile]
    digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: DeploymentBundleStatus
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class CreateDeploymentBundleRequest(DeploymentModel):
    simulation_run_id: str = Field(alias="simulationRunId", min_length=1, max_length=200)
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)


class DeviceProbeRecord(DeploymentModel):
    implementation: str
    platform: str
    machine: str
    firmware_version: str = Field(alias="firmwareVersion")
    unique_id_hash: str = Field(alias="uniqueIdHash")
    board_package_revision_id: str = Field(alias="boardPackageRevisionId")
    matched: bool


class ProjectDeviceConnection(DeploymentModel):
    session: DeviceSession
    probe: DeviceProbeRecord


class ConnectProjectDeviceRequest(DeploymentModel):
    deployment_bundle_id: str = Field(
        alias="deploymentBundleId", min_length=1, max_length=200
    )
    port_id: str = Field(alias="portId", min_length=1, max_length=300)


class StartProjectDeploymentRequest(DeploymentModel):
    deployment_bundle_id: str = Field(
        alias="deploymentBundleId", min_length=1, max_length=200
    )
    session_id: str = Field(alias="sessionId", min_length=1, max_length=200)
    operation_id: str = Field(
        alias="operationId",
        min_length=8,
        max_length=128,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9._-]{7,127}$",
    )
    dry_run: bool = Field(alias="dryRun", default=True)
    confirm_write: bool = Field(alias="confirmWrite", default=False)


class ProjectDeviceDeployment(DeploymentModel):
    id: str
    work_id: str = Field(alias="workId")
    deployment_bundle_id: str = Field(alias="deploymentBundleId")
    device_operation_id: str | None = Field(alias="deviceOperationId")
    session_id: str = Field(alias="sessionId")
    status: ProjectDeploymentStatus
    transport_mode: DeploymentTransportMode = Field(alias="transportMode")
    evidence_eligible: bool = Field(alias="evidenceEligible")
    evidence_level: str | None = Field(alias="evidenceLevel")
    created_by: str = Field(alias="createdBy")
    created_at: str = Field(alias="createdAt")
    updated_at: str = Field(alias="updatedAt")
    completed_at: str | None = Field(alias="completedAt")
    invalidated_at: str | None = Field(alias="invalidatedAt")
    invalidation_reason: str | None = Field(alias="invalidationReason")


class PhysicalObservationRequest(DeploymentModel):
    deployment_id: str = Field(alias="deploymentId", min_length=1, max_length=200)
    attested_by_user: bool = Field(alias="attestedByUser")
    observations: list[str] = Field(min_length=1, max_length=64)
    passed: bool
    idempotency_key: str = Field(alias="idempotencyKey", min_length=8, max_length=160)


class PhysicalObservation(DeploymentModel):
    id: str
    work_id: str = Field(alias="workId")
    deployment_id: str = Field(alias="deploymentId")
    passed: bool
    observations: list[str]
    attested_by: str = Field(alias="attestedBy")
    evidence_level: str = Field(alias="evidenceLevel", default="L4")
    created_at: str = Field(alias="createdAt")


class DeploymentWorkspace(DeploymentModel):
    bundles: list[DeploymentBundle]
    deployments: list[ProjectDeviceDeployment]
    current_bundle: DeploymentBundle | None = Field(alias="currentBundle")
    current_deployment: ProjectDeviceDeployment | None = Field(alias="currentDeployment")
    can_prepare_bundle: bool = Field(alias="canPrepareBundle")
    can_deploy: bool = Field(alias="canDeploy")
    blocked_reason: str | None = Field(alias="blockedReason")
    firmware_operation_separate: bool = Field(alias="firmwareOperationSeparate", default=True)
