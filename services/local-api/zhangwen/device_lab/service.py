"""Application validation, deterministic board models and safe lab state transitions."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import sqlite3
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from zhangwen.device_lab.applications import (
    ApplicationValidationError,
    validate_application_archive,
)
from zhangwen.device_lab.boards import BOARDS, PROFILES, board_profile, scene_profile
from zhangwen.device_lab.models import (
    ApplyParameterSetRequest,
    CreateDeviceLabRunRequest,
    CuratedFirmwareApplication,
    DeviceBoardListResponse,
    DeviceLabChannel,
    DeviceLabEngine,
    DeviceLabEvent,
    DeviceLabProfileV1,
    DeviceLabRun,
    DeviceLabRunResponse,
    DeviceLabRunStatus,
    DeviceLabScenarioResult,
    DeviceLabSceneV1,
    DeviceLabTarget,
    FirmwareApplicationListResponse,
    FirmwareApplicationRecord,
    ImportFirmwareApplicationRequest,
    ParameterSetRevision,
    SaveParameterSetRequest,
    SupportedDeviceBoardId,
    UpdateDeviceLabChannelRequest,
)
from zhangwen.domains.events.runtime import telemetry_hub
from zhangwen.domains.orchestration.models import (
    ExecutionRevisionBinding,
    ExecutionRevisionSet,
    PackageKind,
)
from zhangwen.domains.packages.repository import PackagePlatformRepository
from zhangwen.domains.works.models import WorkRunRevisionBindings
from zhangwen.projects.repository import ProjectRepository
from zhangwen.device_lab.qemu import QemuRuntimeManager
from zhangwen.device_lab.repository import DeviceLabRepository
from zhangwen.device_lab.scene import (
    DeviceLabSceneProjectionError,
    DeviceLabSceneProjector,
)


_SECRET_PARTS = ("password", "passwd", "wifi", "ssid", "token", "secret", "api-key", "apikey")


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _request_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class DeviceLabError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class DeviceLabService:
    def __init__(
        self,
        db_path: Path,
        data_dir: Path,
    ) -> None:
        self._db_path = Path(db_path)
        self._data_dir = Path(data_dir)
        self._repo = DeviceLabRepository(db_path)
        self._qemu = QemuRuntimeManager(data_dir)
        self._scene_projector = DeviceLabSceneProjector(db_path, data_dir)
        self._processes: dict[str, asyncio.subprocess.Process] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def board_list(self) -> DeviceBoardListResponse:
        return DeviceBoardListResponse(
            boards=list(BOARDS.values()),
            profiles=list(PROFILES.values()),
            qemu=self._qemu.status(),
        )

    def list_applications(self, project_id: str) -> FirmwareApplicationListResponse:
        curated = [
            CuratedFirmwareApplication(
                applicationId="esp-claw-xiao-esp32s3-sense",
                displayName="ESP-Claw · XIAO ESP32S3 Sense",
                boardId=SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
                sourceUrl="https://github.com/espressif/esp-claw/tree/master/application/edge_agent/boards/seeedstudio/xiao_esp32s3_sense",
            ),
            CuratedFirmwareApplication(
                applicationId="esp-claw-dfrobot-k10",
                displayName="ESP-Claw · DFRobot K10",
                boardId=SupportedDeviceBoardId.DFROBOT_K10,
                sourceUrl="https://github.com/espressif/esp-claw/tree/master/application/edge_agent/boards/dfrobot/dfrobot_k10",
            ),
        ]
        return FirmwareApplicationListResponse(
            applications=self._repo.list_applications(project_id),
            curated=curated,
        )

    def get_scene(self, project_id: str) -> DeviceLabSceneV1:
        try:
            return self._repo.save_scene(self._scene_projector.project(project_id))
        except DeviceLabSceneProjectionError as exc:
            raise DeviceLabError(exc.code, exc.message, 409) from exc

    def get_work_functional_scene(self, project_id: str) -> DeviceLabSceneV1:
        """Project a Work simulation without claiming a physical board choice."""

        try:
            scene = self._scene_projector.project(
                project_id,
                allow_work_functional_proxy=True,
            )
            return self._repo.save_scene(scene)
        except DeviceLabSceneProjectionError as exc:
            raise DeviceLabError(exc.code, exc.message, 409) from exc

    def import_application(
        self,
        project_id: str,
        request: ImportFirmwareApplicationRequest,
    ) -> FirmwareApplicationRecord:
        try:
            validated = validate_application_archive(request.zipBase64)
        except ApplicationValidationError as exc:
            raise DeviceLabError(exc.code, exc.message) from exc
        application_dir = self._data_dir / "device-lab" / "applications" / project_id
        application_dir.mkdir(parents=True, exist_ok=True)
        archive_path = application_dir / f"{validated.archive_sha256}.zwapp.zip"
        if not archive_path.exists():
            temporary = application_dir / f".{uuid.uuid4().hex}.tmp"
            temporary.write_bytes(validated.archive)
            os.replace(temporary, archive_path)
        try:
            return self._repo.save_application(
                project_id=project_id,
                manifest=validated.manifest,
                archive_path=archive_path,
                archive_sha256=validated.archive_sha256,
                simulation_capability=validated.simulation_capability,
            )
        except Exception:
            # The content-addressed archive may be referenced by an earlier import;
            # never remove it while handling an insertion conflict.
            raise

    async def create_run(
        self,
        project_id: str,
        request: CreateDeviceLabRunRequest,
    ) -> DeviceLabRunResponse:
        return await self._create_run(
            project_id,
            request,
            work_functional=False,
        )

    async def create_work_run(
        self,
        project_id: str,
        request: CreateDeviceLabRunRequest,
    ) -> DeviceLabRunResponse:
        """Start the unified Work run on the same bounded local executor."""

        if request.target is not DeviceLabTarget.SIMULATOR:
            raise DeviceLabError(
                "WORK_FUNCTIONAL_TARGET_INVALID",
                "作品数字试做只允许在本机功能仿真中启动。",
                409,
            )
        return await self._create_run(
            project_id,
            request,
            work_functional=True,
        )

    async def _create_run(
        self,
        project_id: str,
        request: CreateDeviceLabRunRequest,
        *,
        work_functional: bool,
    ) -> DeviceLabRunResponse:
        if request.engine is DeviceLabEngine.WOKWI_CLOUD:
            raise DeviceLabError(
                "WOKWI_CLOUD_RETIRED",
                "旧 Wokwi Cloud 联网运行已退役；请在项目的仿真验证章节使用掌问自研仿真。",
                410,
            )
        idempotency_key = (
            f"work-functional:{request.idempotencyKey}"
            if work_functional
            else request.idempotencyKey
        )
        request_hash = _request_hash(
            request.model_dump(mode="json", exclude={"idempotencyKey"})
        )
        try:
            repeated = self._repo.find_run_by_idempotency(
                project_id, idempotency_key, request_hash
            )
        except ValueError as exc:
            raise DeviceLabError(
                "DEVICE_LAB_IDEMPOTENCY_KEY_REUSED",
                "该幂等键已绑定到不同的仿真启动请求。",
                409,
            ) from exc
        if repeated is not None:
            return DeviceLabRunResponse(
                run=repeated,
                profile=self._profile_for_run(repeated),
            )
        scene = (
            self.get_work_functional_scene(project_id)
            if work_functional
            else self.get_scene(project_id)
        )
        if (
            request.expectedSceneRevision is not None
            and request.expectedSceneRevision != scene.revision
        ):
            raise DeviceLabError(
                "DEVICE_LAB_SCENE_REVISION_CONFLICT",
                "立项或硬件方案已更新，请刷新自动生成的实物仿真后再启动。",
                409,
            )
        scene_solution_id = (
            scene.binding.solutionRevisionId
            if scene.binding is not None
            else scene.source.proposalId
        )
        if (
            request.expectedSolutionRevisionId is not None
            and request.expectedSolutionRevisionId != scene_solution_id
        ):
            raise DeviceLabError(
                "CREATOR_SIMULATION_SOLUTION_MISMATCH",
                "仿真场景没有绑定当前方案，请刷新数字原型后重试。",
                409,
            )
        scene_code_run_id = (
            scene.binding.codeRunId if scene.binding is not None else None
        )
        if request.codeRunId is not None and request.codeRunId != scene_code_run_id:
            raise DeviceLabError(
                "CREATOR_SIMULATION_CODE_MISMATCH",
                "仿真场景没有绑定当前代码版本，请刷新数字原型后重试。",
                409,
            )
        board_id = scene.boardId
        if request.target == DeviceLabTarget.DEVICE:
            raise DeviceLabError(
                "DEVICE_LAB_PROTOCOL_UNAVAILABLE",
                "真机尚未完成 zwdbg/1 握手，不能建立图形调试会话。",
                409,
            )
        profile = scene_profile(scene)
        application: FirmwareApplicationRecord | None = None
        archive_path: Path | None = None
        engine = request.engine
        if engine is DeviceLabEngine.QEMU_ESP32S3 and not request.applicationId:
            raise DeviceLabError(
                "QEMU_APPLICATION_REQUIRED",
                "QEMU 固件仿真必须选择兼容应用镜像。",
                409,
            )
        if request.applicationId:
            try:
                application, archive_path = self._repo.get_application(project_id, request.applicationId)
            except KeyError as exc:
                raise DeviceLabError("FIRMWARE_APPLICATION_NOT_FOUND", "应用不存在。", 404) from exc
            if application.manifest.boardId != board_id:
                raise DeviceLabError(
                    "FIRMWARE_APPLICATION_BOARD_MISMATCH", "应用与设备实验室板型不一致。"
                )
            if application.manifest.simulationImage is None:
                raise DeviceLabError(
                    "FIRMWARE_APPLICATION_SIMULATION_UNAVAILABLE",
                    "此应用没有兼容仿真镜像，只能用于真机安装或 UART 检查。",
                    409,
                )
            if not self._qemu.status().available:
                raise DeviceLabError(
                    "QEMU_RUNTIME_UNAVAILABLE",
                    "ESP32-S3 QEMU 可选运行时尚未安装，不能执行固件级仿真。",
                    409,
                )
            engine = DeviceLabEngine.QEMU_ESP32S3
        values = {channel.id: channel.defaultValue for channel in profile.channels}
        parameter_set: ParameterSetRevision | None = None
        if request.parameterSetId:
            try:
                parameter_set = self._repo.get_parameter_set(project_id, request.parameterSetId)
            except KeyError as exc:
                raise DeviceLabError("PARAMETER_SET_NOT_FOUND", "参数版本不存在。", 404) from exc
            if parameter_set.boardId != board_id or parameter_set.profileRevision != profile.revision:
                raise DeviceLabError("PARAMETER_SET_PROFILE_MISMATCH", "参数版本与板型档案不一致。")
            values.update(parameter_set.values)
        now = _now()
        execution_revision_set = self._execution_revision_set(scene, engine)
        run = DeviceLabRun(
            id=f"lab-{uuid.uuid4().hex}", projectId=project_id, boardId=board_id,
            target=request.target, engine=engine, status=DeviceLabRunStatus.STARTING,
            applicationId=request.applicationId, parameterSetId=request.parameterSetId,
            channelValues=values, revision=1, startedAt=now, updatedAt=now,
            scene=scene,
            revisionBindings=WorkRunRevisionBindings(
                solutionRevisionId=scene_solution_id,
                codeRunId=scene_code_run_id,
                parameterSetId=request.parameterSetId,
                sceneRevision=scene.revision,
                structureRevisionId=self._current_structure_revision_id(project_id),
                canvasSpecRevisionId=self._current_canvas_spec_revision_id(project_id),
            ),
            executionRevisionSet=execution_revision_set,
        )
        run.status = DeviceLabRunStatus.RUNNING
        if engine == DeviceLabEngine.QEMU_ESP32S3:
            run_message = "固件级 QEMU 仿真已启动。"
        elif work_functional:
            run_message = "作品数字试作已在本机启动；结果不代表真实设备或电气时序。"
        else:
            run_message = "已按批准立项内容启动实物功能仿真；该模式不代表电气时序。"
        event = DeviceLabEvent(
            revision=1,
            type="state",
            message=run_message,
            createdAt=now,
        )
        try:
            persisted = self._repo.insert_run(
                run, event, idempotency_key=idempotency_key,
                request_hash=request_hash,
            )
        except ValueError as exc:
            raise DeviceLabError(
                "DEVICE_LAB_IDEMPOTENCY_KEY_REUSED",
                "该幂等键已绑定到不同的仿真启动请求。",
                409,
            ) from exc
        if persisted.id != run.id:
            return DeviceLabRunResponse(
                run=persisted,
                profile=self._profile_for_run(persisted),
            )
        if application is not None and archive_path is not None:
            try:
                image = self._materialize_simulation_image(run.id, application, archive_path)
                self._processes[run.id] = await self._qemu.start(image)
            except Exception as exc:
                failed = run.model_copy(
                    update={
                        "status": DeviceLabRunStatus.ERROR,
                        "errorMessage": "QEMU 启动失败。",
                        "revision": 2,
                        "updatedAt": _now(),
                    }
                )
                self._repo.update_run(
                    failed,
                    DeviceLabEvent(
                        revision=2, type="error", message="QEMU 启动失败。", createdAt=failed.updatedAt
                    ),
                )
                raise DeviceLabError("QEMU_START_FAILED", "QEMU 启动失败。", 500) from exc
        self._publish_telemetry(run, message="数字试运行已开始。")
        return DeviceLabRunResponse(run=run, profile=profile)

    def get_run(self, project_id: str, run_id: str) -> DeviceLabRunResponse:
        try:
            run = self._repo.get_run(project_id, run_id)
        except KeyError as exc:
            raise DeviceLabError("DEVICE_LAB_RUN_NOT_FOUND", "设备实验室会话不存在。", 404) from exc
        profile = self._profile_for_run(run)
        return DeviceLabRunResponse(run=run, profile=profile)

    @staticmethod
    def _profile_for_run(run: DeviceLabRun) -> DeviceLabProfileV1:
        if run.wokwiBinding is not None and run.wokwiBinding.profile is not None:
            return run.wokwiBinding.profile
        return scene_profile(run.scene) if run.scene is not None else board_profile(run.boardId)

    def recover_interrupted_runs(self) -> int:
        """Fail closed when a persisted run outlives its local executor process."""

        recovered = 0
        for run in self._repo.list_interrupted_runs():
            profile = self._profile_for_run(run)
            values = dict(run.channelValues)
            for channel in profile.channels:
                if channel.kind == "actuator" and channel.safeValue is not None:
                    values[channel.id] = channel.safeValue
            now = _now()
            stopped = run.model_copy(
                update={
                    "status": DeviceLabRunStatus.STOPPED,
                    "actuatorArmed": False,
                    "channelValues": values,
                    "revision": run.revision + 1,
                    "updatedAt": now,
                }
            )
            if self._repo.recover_interrupted_run(
                stopped,
                DeviceLabEvent(
                    revision=stopped.revision,
                    type="state",
                    message="本地服务进程中断；数字试运行已安全停止，执行器已恢复安全值。",
                    createdAt=now,
                ),
            ):
                recovered += 1
        return recovered

    async def update_channel(
        self,
        project_id: str,
        run_id: str,
        channel_id: str,
        request: UpdateDeviceLabChannelRequest,
    ) -> DeviceLabRunResponse:
        async with self._locks.setdefault(run_id, asyncio.Lock()):
            current = self.get_run(project_id, run_id)
            run = current.run
            if run.engine is DeviceLabEngine.WOKWI_CLOUD:
                raise DeviceLabError(
                    "WOKWI_CLOUD_RETIRED",
                    "旧 Wokwi Cloud 运行只供历史查看，不能再发送控制命令。",
                    410,
                )
            if self._repo.command_seen(run_id, request.commandId):
                return current
            if run.status != DeviceLabRunStatus.RUNNING:
                raise DeviceLabError("DEVICE_LAB_RUN_NOT_RUNNING", "设备实验室会话未运行。", 409)
            if run.revision != request.expectedRevision:
                raise DeviceLabError("DEVICE_LAB_REVISION_CONFLICT", "会话状态已更新，请刷新后重试。", 409)
            channel = next((item for item in current.profile.channels if item.id == channel_id), None)
            if channel is None:
                raise DeviceLabError("DEVICE_LAB_CHANNEL_NOT_FOUND", "调试通道不存在。", 404)
            if not channel.writable:
                raise DeviceLabError("DEVICE_LAB_CHANNEL_READ_ONLY", "该通道只读。")
            value = _validate_channel_value(channel, request.value)
            armed = run.actuatorArmed
            if channel.requiresArm:
                if not request.actuatorArmed:
                    raise DeviceLabError("DEVICE_LAB_ACTUATOR_NOT_ARMED", "执行器调试尚未解锁。", 409)
                armed = True
            values = dict(run.channelValues)
            if channel.kind == "actuator" and channel.source == "project-scene":
                limit = values.get(f"{channel.id.rsplit('.', 1)[0]}.max-output")
                if (
                    isinstance(value, (int, float))
                    and not isinstance(value, bool)
                    and isinstance(limit, (int, float))
                    and not isinstance(limit, bool)
                    and value > limit
                ):
                    raise DeviceLabError(
                        "DEVICE_LAB_ACTUATOR_LIMIT_EXCEEDED",
                        "执行器输出超过当前项目参数版本中的安全上限。",
                        409,
                    )
            if run.boardId == SupportedDeviceBoardId.XIAO_ESP32S3_SENSE:
                if channel_id == "user-led" and bool(value) and bool(values.get("sd-mounted", False)):
                    raise DeviceLabError(
                        "DEVICE_LAB_PIN_CONFLICT",
                        "microSD 正在使用 GPIO21，不能同时点亮用户 LED。",
                        409,
                    )
                if channel_id == "sd-mounted" and bool(value):
                    values["user-led"] = False
            values[channel_id] = value
            now = _now()
            updated = run.model_copy(
                update={
                    "channelValues": values,
                    "actuatorArmed": armed,
                    "revision": run.revision + 1,
                    "updatedAt": now,
                }
            )
            self._repo.update_run(
                updated,
                DeviceLabEvent(
                    revision=updated.revision,
                    type="telemetry" if channel.kind == "sensor-input" else "ack",
                    channelId=channel.id,
                    value=value,
                    message=f"{channel.label} 已更新。",
                    commandId=request.commandId,
                    createdAt=now,
                ),
            )
            self._publish_telemetry(
                updated,
                message=f"{channel.label} 已更新。",
                channel_id=channel.id,
                value=value,
            )
            return DeviceLabRunResponse(run=updated, profile=current.profile)

    async def stop_run(self, project_id: str, run_id: str) -> DeviceLabRunResponse:
        async with self._locks.setdefault(run_id, asyncio.Lock()):
            current = self.get_run(project_id, run_id)
            run = current.run
            if run.status == DeviceLabRunStatus.STOPPED:
                return current
            values = dict(run.channelValues)
            for channel in current.profile.channels:
                if channel.kind == "actuator" and channel.safeValue is not None:
                    values[channel.id] = channel.safeValue
            process = self._processes.pop(run_id, None)
            if process is not None and process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.kill()
                    await process.wait()
            now = _now()
            stopped = run.model_copy(
                update={
                    "status": DeviceLabRunStatus.STOPPED,
                    "actuatorArmed": False,
                    "channelValues": values,
                    "revision": run.revision + 1,
                    "updatedAt": now,
                }
            )
            self._repo.update_run(
                stopped,
                DeviceLabEvent(
                    revision=stopped.revision,
                    type="state",
                    message="会话已停止，执行器已恢复安全值。",
                    createdAt=now,
                ),
            )
            self._publish_telemetry(stopped, message="数字试运行已安全停止。")
            return DeviceLabRunResponse(run=stopped, profile=current.profile)

    async def record_result(
        self,
        project_id: str,
        run_id: str,
        *,
        scenario_results: list[DeviceLabScenarioResult],
        summary: str,
        idempotency_key: str,
    ) -> DeviceLabRunResponse:
        request_hash = _request_hash(
            {
                "scenarioResults": [
                    item.model_dump(mode="json") for item in scenario_results
                ],
                "summary": summary,
            }
        )
        async with self._locks.setdefault(run_id, asyncio.Lock()):
            current = self.get_run(project_id, run_id)
            run = current.run
            if run.resultIdempotencyKey is not None:
                if (
                    run.resultIdempotencyKey != idempotency_key
                    or run.resultRequestHash != request_hash
                ):
                    raise DeviceLabError(
                        "DIGITAL_RUN_RESULT_IMMUTABLE",
                        "这次数字试运行已经形成结果，不能在原会话上改写。",
                        409,
                    )
                return current
            if run.status is not DeviceLabRunStatus.STOPPED:
                raise DeviceLabError(
                    "DIGITAL_RUN_NOT_STOPPED",
                    "数字试运行必须先安全停止，才能形成结果。",
                    409,
                )
            passed = all(item.passed for item in scenario_results)
            now = _now()
            updated = run.model_copy(
                update={
                    "scenarioResults": scenario_results,
                    "resultPassed": passed,
                    "resultSummary": summary,
                    "resultIdempotencyKey": idempotency_key,
                    "resultRequestHash": request_hash,
                    "revision": run.revision + 1,
                    "updatedAt": now,
                }
            )
            self._repo.update_run(
                updated,
                DeviceLabEvent(
                    revision=updated.revision,
                    type="state",
                    message=summary,
                    createdAt=now,
                ),
            )
            self._publish_telemetry(updated, message=summary)
            return DeviceLabRunResponse(run=updated, profile=current.profile)

    def _execution_revision_set(
        self,
        scene: DeviceLabSceneV1,
        engine: DeviceLabEngine = DeviceLabEngine.FUNCTIONAL_MODEL,
    ) -> ExecutionRevisionSet:
        package_id = scene.source.simulationProxyPackageId or (
            f"device-package:board:{scene.boardId.value.replace('/', '-')}"
        )
        packages = PackagePlatformRepository(self._data_dir)
        revision = packages.stable_revision(package_id)
        now = _now()
        bindings = [
            ExecutionRevisionBinding(
                packageKind=PackageKind.DEVICE_PACKAGE,
                packageId=package_id,
                packageRevisionId=revision.id,
            )
        ]
        return ExecutionRevisionSet(
            id=f"revision_set_run_{uuid.uuid4().hex}",
            bindings=bindings,
            createdAt=now,
        )

    def _current_structure_revision_id(self, project_id: str) -> str | None:
        db_path = ProjectRepository(self._data_dir).db_path
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT id FROM cad_intent_revisions
                WHERE project_id = ? AND status = 'CONFIRMED'
                ORDER BY COALESCE(confirmed_at, created_at) DESC, rowid DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    def _current_canvas_spec_revision_id(self, project_id: str) -> str | None:
        db_path = ProjectRepository(self._data_dir).db_path
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                """
                SELECT id FROM canvas_spec_revisions
                WHERE work_id = ?
                ORDER BY revision DESC, created_at DESC, id DESC LIMIT 1
                """,
                (project_id,),
            ).fetchone()
        return str(row[0]) if row is not None else None

    @staticmethod
    def _publish_telemetry(
        run: DeviceLabRun,
        *,
        message: str,
        channel_id: str | None = None,
        value: float | bool | str | None = None,
    ) -> None:
        payload: dict[str, object] = {
            "kind": "digital_run",
            "runId": run.id,
            "status": run.status.value,
            "revision": run.revision,
            "message": message,
        }
        if channel_id is not None:
            payload["channelId"] = channel_id
        if value is not None:
            payload["value"] = value
        telemetry_hub().publish(work_id=run.projectId, payload=payload)

    def list_events(self, project_id: str, run_id: str, after_revision: int) -> list[DeviceLabEvent]:
        try:
            return self._repo.list_events(project_id, run_id, after_revision)
        except KeyError as exc:
            raise DeviceLabError("DEVICE_LAB_RUN_NOT_FOUND", "设备实验室会话不存在。", 404) from exc

    def save_parameter_set(
        self,
        project_id: str,
        request: SaveParameterSetRequest,
    ) -> ParameterSetRevision:
        request_hash = _request_hash(
            request.model_dump(mode="json", exclude={"idempotencyKey"})
        )
        try:
            repeated = self._repo.find_parameter_set_by_idempotency(
                project_id, request.idempotencyKey, request_hash
            )
        except ValueError as exc:
            raise DeviceLabError(
                "DEVICE_LAB_IDEMPOTENCY_KEY_REUSED",
                "该幂等键已绑定到不同的参数保存请求。",
                409,
            ) from exc
        if repeated is not None:
            return repeated
        scene = self.get_scene(project_id)
        if request.boardId != scene.boardId:
            raise DeviceLabError(
                "PARAMETER_SET_BOARD_MISMATCH",
                "参数版本必须绑定当前立项自动生成的主控板型。",
                409,
            )
        profile = scene_profile(scene)
        if request.profileRevision != profile.revision:
            raise DeviceLabError("PARAMETER_SET_PROFILE_MISMATCH", "参数档案版本已变化。", 409)
        if any(
            secret in key.casefold()
            for key in request.values
            for secret in _SECRET_PARTS
        ):
            raise DeviceLabError(
                "PARAMETER_SET_SECRET_REJECTED",
                "参数版本不得包含凭据。",
            )
        allowed = {item.id: item for item in profile.channels if item.kind == "parameter" and item.writable}
        if not request.values or set(request.values) - set(allowed):
            raise DeviceLabError("PARAMETER_SET_VALUES_INVALID", "参数版本包含未知或不可保存的通道。")
        for key, value in request.values.items():
            if any(secret in key.casefold() for secret in _SECRET_PARTS):
                raise DeviceLabError("PARAMETER_SET_SECRET_REJECTED", "参数版本不得包含凭据。")
            _validate_channel_value(allowed[key], value)
        try:
            return self._repo.save_parameter_set(
                project_id=project_id,
                board_id=request.boardId,
                profile_revision=request.profileRevision,
                label=request.label,
                values=request.values,
                idempotency_key=request.idempotencyKey,
                request_hash=request_hash,
            )
        except ValueError as exc:
            raise DeviceLabError(
                "DEVICE_LAB_IDEMPOTENCY_KEY_REUSED",
                "该幂等键已绑定到不同的参数保存请求。",
                409,
            ) from exc

    def list_parameter_sets(self, project_id: str) -> list[ParameterSetRevision]:
        return self._repo.list_parameter_sets(project_id)

    async def apply_parameter_set(
        self,
        project_id: str,
        run_id: str,
        request: ApplyParameterSetRequest,
    ) -> DeviceLabRunResponse:
        async with self._locks.setdefault(run_id, asyncio.Lock()):
            current = self.get_run(project_id, run_id)
            if current.run.revision != request.expectedRevision:
                raise DeviceLabError("DEVICE_LAB_REVISION_CONFLICT", "会话状态已更新，请刷新后重试。", 409)
            try:
                parameter_set = self._repo.get_parameter_set(project_id, request.parameterSetId)
            except KeyError as exc:
                raise DeviceLabError("PARAMETER_SET_NOT_FOUND", "参数版本不存在。", 404) from exc
            if parameter_set.boardId != current.run.boardId or parameter_set.profileRevision != current.profile.revision:
                raise DeviceLabError("PARAMETER_SET_PROFILE_MISMATCH", "参数版本与当前会话不一致。")
            values = dict(current.run.channelValues)
            values.update(parameter_set.values)
            now = _now()
            updated = current.run.model_copy(
                update={
                    "channelValues": values,
                    "parameterSetId": parameter_set.id,
                    "revision": current.run.revision + 1,
                    "updatedAt": now,
                }
            )
            self._repo.update_run(
                updated,
                DeviceLabEvent(
                    revision=updated.revision,
                    type="ack",
                    message=f"已应用参数版本 v{parameter_set.revision}。",
                    createdAt=now,
                ),
            )
            return DeviceLabRunResponse(run=updated, profile=current.profile)

    async def shutdown(self) -> None:
        for run_id in list(self._processes):
            process = self._processes.pop(run_id)
            if process.returncode is None:
                process.terminate()
                try:
                    await asyncio.wait_for(process.wait(), timeout=5)
                except TimeoutError:
                    process.kill()
                    await process.wait()

    def _materialize_simulation_image(
        self,
        run_id: str,
        application: FirmwareApplicationRecord,
        archive_path: Path,
    ) -> Path:
        image = application.manifest.simulationImage
        if image is None:
            raise RuntimeError("simulation image missing")
        run_dir = self._data_dir / "device-lab" / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=False)
        target = run_dir / "flash.bin"
        with zipfile.ZipFile(archive_path) as package:
            payload = package.read(image.path)
        target.write_bytes(payload)
        return target


def _validate_channel_value(channel: DeviceLabChannel, value: object) -> float | bool | str:
    if channel.valueType == "boolean":
        if not isinstance(value, bool):
            raise DeviceLabError("DEVICE_LAB_VALUE_TYPE_INVALID", "通道值必须是布尔值。")
        return value
    if channel.valueType == "string":
        if not isinstance(value, str) or len(value) > 240:
            raise DeviceLabError("DEVICE_LAB_VALUE_TYPE_INVALID", "通道值必须是短文本。")
        return value
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DeviceLabError("DEVICE_LAB_VALUE_TYPE_INVALID", "通道值必须是数字。")
    numeric = float(value)
    if channel.minimum is not None and numeric < channel.minimum:
        raise DeviceLabError("DEVICE_LAB_VALUE_RANGE_INVALID", "通道值低于允许范围。")
    if channel.maximum is not None and numeric > channel.maximum:
        raise DeviceLabError("DEVICE_LAB_VALUE_RANGE_INVALID", "通道值高于允许范围。")
    return numeric
