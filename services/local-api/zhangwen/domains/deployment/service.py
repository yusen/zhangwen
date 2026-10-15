"""Simulation-to-device adapter over the canonical safe device executor."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.auth.context import current_owner_subject
from zhangwen.devices.models import DeviceOperationStatus
from zhangwen.devices.service import DeviceOperationService, DeviceServiceError
from zhangwen.devices.transport import DeviceIdentityRequirement
from zhangwen.domains.classroom.repository import ClassroomRepository
from zhangwen.domains.deployment.models import (
    CreateDeploymentBundleRequest,
    DeploymentBundle,
    DeploymentBundleStatus,
    DeploymentTransportMode,
    DeploymentWorkspace,
    DeviceProbeRecord,
    PhysicalObservation,
    PhysicalObservationRequest,
    ProjectDeploymentStatus,
    ProjectDeviceConnection,
    ProjectDeviceDeployment,
    StartProjectDeploymentRequest,
)
from zhangwen.domains.events.store import RealtimeEventStore
from zhangwen.domains.simulation.catalog import SimulationCatalog
from zhangwen.domains.simulation.digest import canonical_digest
from zhangwen.domains.simulation.models import (
    SimulationCodeBundleDraft,
    SimulationCodeFile,
)


_LOCAL_SUBJECT = "__local__"


class ProjectDeploymentError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int = 422,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.retryable = retryable


class ProjectDeploymentService:
    """Pins a passed simulation revision and delegates every device effect."""

    def __init__(
        self,
        data_dir: Path,
        *,
        device_service: DeviceOperationService | None = None,
    ) -> None:
        self._data_dir = Path(data_dir)
        self._classroom = ClassroomRepository(self._data_dir)
        self._db_path = self._classroom.db_path
        self._devices = device_service
        self._catalog = SimulationCatalog.load_builtin()
        self._events = RealtimeEventStore(self._db_path)
        self._actor = current_owner_subject() or _LOCAL_SUBJECT

    def create_bundle(
        self,
        *,
        work_id: str,
        request: CreateDeploymentBundleRequest,
    ) -> DeploymentBundle:
        self._classroom.assert_work_access(work_id, edit=True)
        request_digest = canonical_digest(
            {"simulationRunId": request.simulation_run_id}
        )
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM deployment_bundles "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"]) != request_digest:
                    raise ProjectDeploymentError(
                        "DEPLOYMENT_BUNDLE_IDEMPOTENCY_CONFLICT",
                        "同一请求键已经用于另一份部署包。",
                        status_code=409,
                    )
                return _bundle(existing)
            by_run = conn.execute(
                "SELECT * FROM deployment_bundles "
                "WHERE work_id = ? AND simulation_run_id = ?",
                (work_id, request.simulation_run_id),
            ).fetchone()
            if by_run is not None:
                return _bundle(by_run)
            row = conn.execute(
                """
                SELECT r.*, p.board_package_revision_id,
                       p.runtime_package_revision_id, p.code_bundle_revision_id,
                       c.current_simulation_run_id,
                       c.current_simulation_project_revision_id
                FROM simulation_runs AS r
                JOIN simulation_project_revisions AS p
                  ON p.id = r.simulation_project_revision_id
                JOIN work_learning_contexts AS c ON c.work_id = r.work_id
                WHERE r.id = ? AND r.work_id = ?
                """,
                (request.simulation_run_id, work_id),
            ).fetchone()
            if (
                row is None
                or str(row["status"]) != "PASSED"
                or not bool(row["evidence_eligible"])
                or str(row["engine_mode"]) != "NATIVE_MICROPYTHON"
                or str(row["current_simulation_run_id"] or "")
                != request.simulation_run_id
                or str(row["current_simulation_project_revision_id"] or "")
                != str(row["simulation_project_revision_id"])
            ):
                raise ProjectDeploymentError(
                    "DEPLOYMENT_REQUIRES_CURRENT_VERIFIED_SIMULATION",
                    "只能从当前正式通过的原生仿真版本生成部署包。",
                    status_code=409,
                )
            code_row = conn.execute(
                "SELECT payload_json FROM simulation_code_bundle_revisions WHERE id = ?",
                (row["code_bundle_revision_id"],),
            ).fetchone()
            if code_row is None:
                raise ProjectDeploymentError(
                    "DEPLOYMENT_CODE_BUNDLE_MISSING",
                    "仿真版本缺少不可变代码子版本。",
                    status_code=409,
                )
            code = SimulationCodeBundleDraft.model_validate_json(
                str(code_row["payload_json"])
            )
            board_revision = str(row["board_package_revision_id"])
            board = self._catalog.board(board_revision)
            if board is None:
                raise ProjectDeploymentError(
                    "DEPLOYMENT_BOARD_PACKAGE_UNAVAILABLE",
                    "当前板型版本不在本地受信目录中。",
                    status_code=409,
                )
            payload = {
                "simulationRunId": request.simulation_run_id,
                "simulationProjectRevisionId": str(
                    row["simulation_project_revision_id"]
                ),
                "boardPackageRevisionId": board_revision,
                "chipFamily": board.chip_family.value,
                "runtimePackageRevisionId": str(row["runtime_package_revision_id"]),
                "files": [item.model_dump(mode="json") for item in code.files],
            }
            digest = canonical_digest(payload)
            bundle_id = _id("deployment-bundle")
            conn.execute(
                """
                UPDATE deployment_bundles
                SET status = 'STALE', invalidated_at = ?,
                    invalidation_reason = 'A newer deployment bundle became current.'
                WHERE work_id = ? AND status = 'CURRENT'
                """,
                (now, work_id),
            )
            conn.execute(
                """
                INSERT INTO deployment_bundles (
                  id, work_id, simulation_run_id, simulation_project_revision_id,
                  board_package_revision_id, chip_family,
                  runtime_package_revision_id, files_json, digest, status,
                  idempotency_key, request_digest, created_by, created_at,
                  invalidated_at, invalidation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'CURRENT', ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    bundle_id,
                    work_id,
                    request.simulation_run_id,
                    row["simulation_project_revision_id"],
                    board_revision,
                    board.chip_family.value,
                    row["runtime_package_revision_id"],
                    _dump(payload["files"]),
                    digest,
                    request.idempotency_key,
                    request_digest,
                    self._actor,
                    now,
                ),
            )
            conn.execute(
                "UPDATE work_learning_contexts "
                "SET current_deployment_bundle_id = ?, current_device_deployment_id = NULL, "
                "updated_at = ? WHERE work_id = ?",
                (bundle_id, now, work_id),
            )
            self._events.append_work_event(
                conn,
                work_id=work_id,
                event_type="work.deployment-bundle.created",
                source_event_id=f"deployment-bundle:{bundle_id}",
                payload={
                    "deploymentBundleId": bundle_id,
                    "naturalStatus": "已从正式仿真版本准备设备部署文件",
                },
            )
            created = conn.execute(
                "SELECT * FROM deployment_bundles WHERE id = ?", (bundle_id,)
            ).fetchone()
            assert created is not None
            return _bundle(created)

    def get_workspace(self, work_id: str) -> DeploymentWorkspace:
        self._classroom.assert_work_access(work_id)
        with self._connect() as conn:
            bundle_rows = conn.execute(
                "SELECT * FROM deployment_bundles WHERE work_id = ? "
                "ORDER BY created_at DESC, id",
                (work_id,),
            ).fetchall()
            deployment_rows = conn.execute(
                "SELECT * FROM project_device_deployments WHERE work_id = ? "
                "ORDER BY created_at DESC, id",
                (work_id,),
            ).fetchall()
            context = conn.execute(
                "SELECT current_deployment_bundle_id, current_device_deployment_id, "
                "process_state FROM work_learning_contexts WHERE work_id = ?",
                (work_id,),
            ).fetchone()
            current_run = conn.execute(
                """
                SELECT 1 FROM simulation_runs AS r
                JOIN work_learning_contexts AS c ON c.current_simulation_run_id = r.id
                WHERE c.work_id = ? AND r.status = 'PASSED'
                  AND r.evidence_eligible = 1
                """,
                (work_id,),
            ).fetchone()
            making_ready = self._making_ready(conn, work_id)
        bundles = [_bundle(row) for row in bundle_rows]
        deployments = [_deployment(row) for row in deployment_rows]
        bundle_id = str(context[0]) if context is not None and context[0] else None
        deployment_id = str(context[1]) if context is not None and context[1] else None
        current_bundle = next((item for item in bundles if item.id == bundle_id), None)
        current_deployment = next(
            (item for item in deployments if item.id == deployment_id), None
        )
        editable = True
        try:
            self._classroom.assert_work_access(work_id, edit=True)
        except Exception:
            editable = False
        can_deploy = bool(
            editable
            and making_ready
            and current_bundle
            and current_bundle.status == "CURRENT"
        )
        return DeploymentWorkspace(
            bundles=bundles,
            deployments=deployments,
            currentBundle=current_bundle,
            currentDeployment=current_deployment,
            canPrepareBundle=bool(editable and current_run),
            canDeploy=can_deploy,
            blockedReason=(
                None
                if can_deploy
                else (
                    "先完成当前制作路径的装配与安全检查。"
                    if not making_ready
                    else "先完成正式仿真并从当前版本准备部署包。"
                )
            ),
            firmwareOperationSeparate=True,
        )

    async def connect_device(
        self,
        *,
        work_id: str,
        bundle_id: str,
        port_id: str,
    ) -> ProjectDeviceConnection:
        self._classroom.assert_work_access(work_id, edit=True)
        self._require_making_ready(work_id)
        devices = self._require_devices()
        bundle = self._current_bundle(work_id, bundle_id)
        board = self._catalog.board(bundle.board_package_revision_id)
        if board is None:
            raise ProjectDeploymentError(
                "DEPLOYMENT_BOARD_PACKAGE_UNAVAILABLE",
                "当前部署包的板型版本已不可用。",
                status_code=409,
            )
        machine = "ESP32-S3" if board.chip_family.value == "esp32s3" else "ESP32-C3"
        requirement = DeviceIdentityRequirement(
            implementation="micropython",
            platform_contains="esp32",
            machine_contains=machine,
        )
        try:
            session, identity = await devices.connect_project_device(
                work_id,
                port_id,
                board_key=board.revision_id.rsplit("@", 1)[0],
                identity_requirement=requirement,
            )
        except DeviceServiceError as exc:
            raise ProjectDeploymentError(
                exc.code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
            ) from exc
        return ProjectDeviceConnection(
            session=session,
            probe=DeviceProbeRecord(
                implementation=identity.implementation,
                platform=identity.platform,
                machine=identity.machine,
                firmwareVersion=identity.firmware_version,
                uniqueIdHash=identity.unique_id_hash,
                boardPackageRevisionId=bundle.board_package_revision_id,
                matched=True,
            ),
        )

    async def start_deployment(
        self,
        *,
        work_id: str,
        request: StartProjectDeploymentRequest,
    ) -> ProjectDeviceDeployment:
        self._classroom.assert_work_access(work_id, edit=True)
        self._require_making_ready(work_id)
        devices = self._require_devices()
        bundle = self._current_bundle(work_id, request.deployment_bundle_id)
        request_digest = canonical_digest(
            {
                "deploymentBundleId": bundle.id,
                "sessionId": request.session_id,
                "dryRun": request.dry_run,
                "confirmWrite": request.confirm_write,
            }
        )
        with self._connect() as conn:
            existing = conn.execute(
                "SELECT * FROM project_device_deployments "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.operation_id),
            ).fetchone()
        if existing is not None:
            if str(existing["request_digest"]) != request_digest:
                raise ProjectDeploymentError(
                    "DEPLOYMENT_IDEMPOTENCY_CONFLICT",
                    "同一 operationId 已经用于另一组部署参数。",
                    status_code=409,
                )
            return _deployment(existing)
        files = {item.path: item.content.encode("utf-8") for item in bundle.files}
        board_key = bundle.board_package_revision_id.rsplit("@", 1)[0]
        try:
            if request.dry_run:
                operation, _ = devices.bundle_upload_dry_run(
                    project_id=work_id,
                    session_id=request.session_id,
                    bundle_id=bundle.id,
                    bundle_digest=bundle.digest,
                    board_key=board_key,
                    files=files,
                    operation_id=request.operation_id,
                )
                mode = DeploymentTransportMode.DRY_RUN
            else:
                operation, _ = await devices.start_bundle_upload(
                    project_id=work_id,
                    session_id=request.session_id,
                    bundle_id=bundle.id,
                    bundle_digest=bundle.digest,
                    board_key=board_key,
                    files=files,
                    operation_id=request.operation_id,
                    confirm_write=request.confirm_write,
                )
                mode = DeploymentTransportMode(devices.transport_mode)
        except DeviceServiceError as exc:
            raise ProjectDeploymentError(
                exc.code,
                exc.message,
                status_code=exc.status_code,
                retryable=exc.retryable,
            ) from exc
        now = _now()
        deployment_id = _id("device-deployment")
        status = _project_status(operation.status)
        completed_at = now if status is ProjectDeploymentStatus.DRY_RUN_COMPLETE else None
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO project_device_deployments (
                  id, work_id, deployment_bundle_id, device_operation_id,
                  session_id, status, transport_mode, evidence_eligible,
                  evidence_level, idempotency_key, request_digest, created_by,
                  created_at, updated_at, completed_at, invalidated_at,
                  invalidation_reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, NULL, ?, ?, ?, ?, ?, ?, NULL, NULL)
                """,
                (
                    deployment_id,
                    work_id,
                    bundle.id,
                    operation.id,
                    request.session_id,
                    status.value,
                    mode.value,
                    request.operation_id,
                    request_digest,
                    self._actor,
                    now,
                    now,
                    completed_at,
                ),
            )
            conn.execute(
                "UPDATE work_learning_contexts SET current_device_deployment_id = ?, "
                "updated_at = ? WHERE work_id = ?",
                (deployment_id, now, work_id),
            )
            created = conn.execute(
                "SELECT * FROM project_device_deployments WHERE id = ?",
                (deployment_id,),
            ).fetchone()
            assert created is not None
        return _deployment(created)

    def reconcile_deployment(
        self,
        work_id: str,
        deployment_id: str,
    ) -> ProjectDeviceDeployment:
        self._classroom.assert_work_access(work_id)
        devices = self._require_devices()
        with self._connect() as conn:
            row = self._deployment_row(conn, work_id, deployment_id)
        operation_id = str(row["device_operation_id"] or "")
        if not operation_id:
            return _deployment(row)
        try:
            operation, _ = devices.get_operation(work_id, operation_id)
        except (DeviceServiceError, ValueError) as exc:
            raise ProjectDeploymentError(
                "DEPLOYMENT_OPERATION_UNAVAILABLE",
                "设备操作状态暂时不可用。",
                status_code=409,
                retryable=True,
            ) from exc
        status = _project_status(operation.status)
        terminal = status not in {
            ProjectDeploymentStatus.QUEUED,
            ProjectDeploymentStatus.RUNNING,
        }
        eligible = bool(
            status is ProjectDeploymentStatus.COMPLETED
            and not operation.dryRun
            and operation.verification is not None
            and operation.verification.ok
            and operation.metadata.get("evidenceEligible") is True
            and operation.metadata.get("transportMode") == "LOCAL_SERIAL"
        )
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                UPDATE project_device_deployments
                SET status = ?, evidence_eligible = ?, evidence_level = ?,
                    updated_at = ?, completed_at = CASE WHEN ? THEN ? ELSE completed_at END
                WHERE id = ? AND work_id = ?
                """,
                (
                    status.value,
                    int(eligible),
                    "L3" if eligible else None,
                    now,
                    int(terminal),
                    now,
                    deployment_id,
                    work_id,
                ),
            )
            if eligible:
                self._record_deployment_evidence(
                    conn,
                    work_id=work_id,
                    deployment_id=deployment_id,
                    operation_id=operation.id,
                    bundle_id=str(row["deployment_bundle_id"]),
                    now=now,
                )
                conn.execute(
                    "UPDATE work_learning_contexts "
                    "SET process_state = 'PHYSICAL_OBSERVATION_REQUIRED', "
                    "updated_at = ? WHERE work_id = ?",
                    (now, work_id),
                )
            updated = self._deployment_row(conn, work_id, deployment_id)
        return _deployment(updated)

    async def cancel_deployment(
        self,
        *,
        work_id: str,
        deployment_id: str,
    ) -> ProjectDeviceDeployment:
        self._classroom.assert_work_access(work_id, edit=True)
        devices = self._require_devices()
        with self._connect() as conn:
            row = self._deployment_row(conn, work_id, deployment_id)
        operation_id = str(row["device_operation_id"] or "")
        if not operation_id:
            return _deployment(row)
        try:
            await devices.cancel_operation(work_id, operation_id)
        except (DeviceServiceError, ValueError) as exc:
            raise ProjectDeploymentError(
                "DEPLOYMENT_CANCEL_FAILED",
                "无法取消当前设备操作。",
                status_code=409,
                retryable=True,
            ) from exc
        return self.reconcile_deployment(work_id, deployment_id)

    def record_physical_observation(
        self,
        *,
        work_id: str,
        request: PhysicalObservationRequest,
    ) -> PhysicalObservation:
        self._classroom.assert_work_access(work_id, edit=True)
        self._require_making_ready(work_id)
        if not request.attested_by_user:
            raise ProjectDeploymentError(
                "PHYSICAL_USER_ATTESTATION_REQUIRED",
                "真实观察必须由当前用户主动确认，不能由 AI 代签。",
            )
        observations = [item.strip() for item in request.observations if item.strip()]
        if not observations:
            raise ProjectDeploymentError(
                "PHYSICAL_OBSERVATION_REQUIRED",
                "至少记录一条真实可观察结果。",
            )
        request_digest = canonical_digest(
            {
                "deploymentId": request.deployment_id,
                "observations": observations,
                "passed": request.passed,
                "attestedByUser": True,
            }
        )
        now = _now()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            existing = conn.execute(
                "SELECT * FROM physical_observations "
                "WHERE work_id = ? AND idempotency_key = ?",
                (work_id, request.idempotency_key),
            ).fetchone()
            if existing is not None:
                if str(existing["request_digest"]) != request_digest:
                    raise ProjectDeploymentError(
                        "PHYSICAL_OBSERVATION_IDEMPOTENCY_CONFLICT",
                        "同一请求键已经用于另一份真实观察。",
                        status_code=409,
                    )
                return _observation(existing)
            deployment = self._deployment_row(conn, work_id, request.deployment_id)
            context = conn.execute(
                "SELECT current_device_deployment_id FROM work_learning_contexts "
                "WHERE work_id = ?",
                (work_id,),
            ).fetchone()
            if (
                str(deployment["status"]) != "COMPLETED"
                or not bool(deployment["evidence_eligible"])
                or str(deployment["evidence_level"] or "") != "L3"
                or context is None
                or str(context[0] or "") != request.deployment_id
            ):
                raise ProjectDeploymentError(
                    "PHYSICAL_REQUIRES_CURRENT_L3",
                    "只有当前真实设备部署通过回读后，才能记录人工实物观察。",
                    status_code=409,
                )
            observation_id = _id("physical-observation")
            conn.execute(
                """
                INSERT INTO physical_observations (
                  id, work_id, deployment_id, passed, observations_json,
                  attested_by, attested_by_user, source, idempotency_key,
                  request_digest, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 1, 'USER_INTERFACE', ?, ?, ?)
                """,
                (
                    observation_id,
                    work_id,
                    request.deployment_id,
                    int(request.passed),
                    _dump(observations),
                    self._actor,
                    request.idempotency_key,
                    request_digest,
                    now,
                ),
            )
            self._record_physical_evidence(
                conn,
                work_id=work_id,
                observation_id=observation_id,
                deployment_id=request.deployment_id,
                passed=request.passed,
                now=now,
            )
            conn.execute(
                "UPDATE work_learning_contexts SET process_state = 'SUBMISSION_DRAFT', "
                "updated_at = ? WHERE work_id = ?",
                (now, work_id),
            )
            created = conn.execute(
                "SELECT * FROM physical_observations WHERE id = ?",
                (observation_id,),
            ).fetchone()
            assert created is not None
            return _observation(created)

    def _record_deployment_evidence(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        deployment_id: str,
        operation_id: str,
        bundle_id: str,
        now: str,
    ) -> None:
        conn.execute(
            "UPDATE creator_evidence SET status = 'SUPERSEDED' "
            "WHERE project_id = ? AND kind IN ('DEPLOYMENT', 'PHYSICAL_BEHAVIOR') "
            "AND status = 'CURRENT'",
            (work_id,),
        )
        conn.execute(
            """
            INSERT INTO creator_evidence (
              id, project_id, kind, status, passed, summary, bindings_json,
              source_id, recorded_at, invalidated_at, invalidation_reason
            ) VALUES (?, ?, 'DEPLOYMENT', 'CURRENT', 1, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                _id("evidence"),
                work_id,
                "设备文件上传、Hash 回读与 MicroPython 启动通过；等待用户观察实物。",
                _dump(
                    {
                        "evidenceLevel": "L3",
                        "deploymentId": deployment_id,
                        "deploymentBundleId": bundle_id,
                    }
                ),
                operation_id,
                now,
            ),
        )

    def _record_physical_evidence(
        self,
        conn: sqlite3.Connection,
        *,
        work_id: str,
        observation_id: str,
        deployment_id: str,
        passed: bool,
        now: str,
    ) -> None:
        conn.execute(
            "UPDATE creator_evidence SET status = 'SUPERSEDED' "
            "WHERE project_id = ? AND kind = 'PHYSICAL_BEHAVIOR' "
            "AND status = 'CURRENT'",
            (work_id,),
        )
        conn.execute(
            """
            INSERT INTO creator_evidence (
              id, project_id, kind, status, passed, summary, bindings_json,
              source_id, recorded_at, invalidated_at, invalidation_reason
            ) VALUES (?, ?, 'PHYSICAL_BEHAVIOR', 'CURRENT', ?, ?, ?, ?, ?, NULL, NULL)
            """,
            (
                _id("evidence"),
                work_id,
                int(passed),
                "当前用户已记录并确认真实设备的可观察结果。",
                _dump(
                    {
                        "evidenceLevel": "L4",
                        "deploymentId": deployment_id,
                        "attestedBy": self._actor,
                        "source": "USER_INTERFACE",
                    }
                ),
                observation_id,
                now,
            ),
        )

    def _current_bundle(self, work_id: str, bundle_id: str) -> DeploymentBundle:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT b.* FROM deployment_bundles AS b
                JOIN work_learning_contexts AS c
                  ON c.current_deployment_bundle_id = b.id
                WHERE b.id = ? AND b.work_id = ? AND b.status = 'CURRENT'
                  AND c.work_id = ?
                """,
                (bundle_id, work_id, work_id),
            ).fetchone()
        if row is None:
            raise ProjectDeploymentError(
                "DEPLOYMENT_BUNDLE_NOT_CURRENT",
                "部署包已不是当前版本，请重新准备。",
                status_code=409,
            )
        return _bundle(row)

    def _require_devices(self) -> DeviceOperationService:
        if self._devices is None:
            raise ProjectDeploymentError(
                "DEVICE_EXECUTOR_UNAVAILABLE",
                "本地设备执行器未配置。",
                status_code=503,
                retryable=True,
            )
        return self._devices

    def _require_making_ready(self, work_id: str) -> None:
        with self._connect() as conn:
            ready = self._making_ready(conn, work_id)
        if not ready:
            raise ProjectDeploymentError(
                "DEPLOYMENT_ASSEMBLY_REQUIRED",
                "请先完成当前制作路径的装配与安全检查。",
                status_code=409,
            )

    @staticmethod
    def _making_ready(conn: sqlite3.Connection, work_id: str) -> bool:
        row = conn.execute(
            """
            SELECT 1
            FROM work_learning_contexts AS c
            JOIN project_build_route_decisions AS d
              ON d.id = c.current_build_route_decision_id
            JOIN project_assembly_records AS a
              ON a.id = c.current_assembly_record_id
             AND a.build_route_decision_id = d.id
            WHERE c.work_id = ? AND d.status = 'CURRENT'
              AND a.status = 'CURRENT'
            """,
            (work_id,),
        ).fetchone()
        return row is not None

    @staticmethod
    def _deployment_row(
        conn: sqlite3.Connection,
        work_id: str,
        deployment_id: str,
    ) -> sqlite3.Row:
        row = conn.execute(
            "SELECT * FROM project_device_deployments WHERE id = ? AND work_id = ?",
            (deployment_id, work_id),
        ).fetchone()
        if row is None:
            raise ProjectDeploymentError(
                "DEPLOYMENT_NOT_FOUND",
                "设备部署记录不存在。",
                status_code=404,
            )
        return row

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _bundle(row: sqlite3.Row) -> DeploymentBundle:
    return DeploymentBundle(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        simulationRunId=str(row["simulation_run_id"]),
        simulationProjectRevisionId=str(row["simulation_project_revision_id"]),
        boardPackageRevisionId=str(row["board_package_revision_id"]),
        chipFamily=str(row["chip_family"]),
        runtimePackageRevisionId=str(row["runtime_package_revision_id"]),
        files=[SimulationCodeFile.model_validate(item) for item in json.loads(str(row["files_json"]))],
        digest=str(row["digest"]),
        status=DeploymentBundleStatus(str(row["status"])),
        createdBy=str(row["created_by"]),
        createdAt=str(row["created_at"]),
        invalidatedAt=_optional(row["invalidated_at"]),
        invalidationReason=_optional(row["invalidation_reason"]),
    )


def _deployment(row: sqlite3.Row) -> ProjectDeviceDeployment:
    return ProjectDeviceDeployment(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        deploymentBundleId=str(row["deployment_bundle_id"]),
        deviceOperationId=_optional(row["device_operation_id"]),
        sessionId=str(row["session_id"]),
        status=ProjectDeploymentStatus(str(row["status"])),
        transportMode=DeploymentTransportMode(str(row["transport_mode"])),
        evidenceEligible=bool(row["evidence_eligible"]),
        evidenceLevel=_optional(row["evidence_level"]),
        createdBy=str(row["created_by"]),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        completedAt=_optional(row["completed_at"]),
        invalidatedAt=_optional(row["invalidated_at"]),
        invalidationReason=_optional(row["invalidation_reason"]),
    )


def _observation(row: sqlite3.Row) -> PhysicalObservation:
    return PhysicalObservation(
        id=str(row["id"]),
        workId=str(row["work_id"]),
        deploymentId=str(row["deployment_id"]),
        passed=bool(row["passed"]),
        observations=[str(item) for item in json.loads(str(row["observations_json"]))],
        attestedBy=str(row["attested_by"]),
        evidenceLevel="L4",
        createdAt=str(row["created_at"]),
    )


def _project_status(status: DeviceOperationStatus) -> ProjectDeploymentStatus:
    return ProjectDeploymentStatus(status.value)


def _optional(value: object) -> str | None:
    return str(value) if value is not None and str(value) else None


def _dump(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"
