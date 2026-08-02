from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from zhangwen.code_agent.models import (
    CodeFile,
    CodeFileKind,
    CodePatch,
    CodeRun,
    CodeRunStatus,
    CodeTestResult,
)
from zhangwen.config import settings
from zhangwen.creator.models import CreatorCommand, CreatorCommandRequest
from zhangwen.creator.repository import CreatorRepository
import zhangwen.creator.router as creator_router
from zhangwen.devices.device_packages import list_device_packages
from zhangwen.devices.espclaw import EspClawHandshake
from zhangwen.devices.models import (
    DeviceDeploymentChannel,
    DeviceOperationKind,
    DeviceOperationPhase,
    DeviceOperationStatus,
    DeviceSessionStatus,
)


@pytest.fixture(autouse=True)
def _authenticated_creator_subject(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        creator_router, "current_owner_subject", lambda: "subject-m6-operator"
    )
from zhangwen.devices.repository import (
    DeviceProjectLeaseBusy,
    DeviceRepository,
)
from zhangwen.devices.service import DeviceOperationService, DeviceServiceError
from zhangwen.devices.transport import MockDeviceTransport
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.main import app


HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "creator-m6-token",
}


@pytest.fixture(autouse=True)
def _runtime(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "creator-m6-token")


def _request(version: int, key: str, payload: dict[str, object]) -> CreatorCommandRequest:
    return CreatorCommandRequest.model_validate(
        {"baseProjectVersion": version, "idempotencyKey": key, "payload": payload}
    )


def _prepared_work(tmp_path) -> tuple[CreatorRepository, str, str]:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="Creator M6 真机闭环",
        initial_idea="用 K10 做环境提醒器",
        idempotency_key="creator-m6-create-work",
        selected_hardware_ids=["hw_seed_unihiker_k10"],
    )
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(
            workspace.project_version,
            "creator-m6-confirm-goal",
            {
                "statement": "制作环境提醒器",
                "observableBehavior": "过热时亮灯，恢复后关闭",
                "constraints": ["离线运行"],
                "successCriteria": ["过热提醒", "恢复关闭"],
            },
        ),
    ).workspace
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-m6-confirm-solution",
            {
                "summary": "K10 环境提醒",
                "logic": "采样温度并控制 RGB",
                "hardware": "DFRobot K10 板载传感器与 RGB",
                "software": "受控 MicroPython 主循环",
                "structure": "不需要结构",
                "simulation": "注入高温并观察 RGB",
                "safety": "停止和断线时 RGB 归零",
                "bom": [
                    {
                        "componentId": "hw_seed_unihiker_k10",
                        "name": "DFRobot K10",
                        "quantity": 1,
                    }
                ],
                "ioMap": [],
                "acceptanceScenarios": [
                    {
                        "title": "过热提醒并恢复",
                        "required": True,
                        "simulationExpected": "高温点亮，恢复关闭",
                        "physicalExpected": "真机按相同阈值提醒并恢复",
                    }
                ],
            },
        ),
    ).workspace
    scene = TestClient(app).get(
        f"/api/projects/{workspace.work_id}/device-lab/scene"
    ).json()["scene"]
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.RECORD_STATIC_VALIDATION,
        _request(
            workspace.project_version,
            "creator-m6-static",
            {
                "passed": True,
                "summary": "静态检查通过",
                "sourceId": scene["revision"],
            },
        ),
    ).workspace
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.RECORD_SIMULATION,
        _request(
            workspace.project_version,
            "creator-m6-simulation",
            {
                "passed": True,
                "summary": "功能仿真通过",
                "sourceId": "simulated-in-repository-boundary",
            },
        ),
    ).workspace
    scenario_id = workspace.acceptance_scenarios[0].id
    return repository, workspace.work_id, scenario_id


def _verified_deployment(tmp_path, work_id: str) -> tuple[str, str]:
    devices = DeviceRepository(CreatorRepository(tmp_path)._db_path)
    session = devices.connect_mock_port(
        work_id,
        "mock_port_esp32_s3",
        SupportedDeviceBoardId.DFROBOT_K10,
    )
    operation_id = "upload-creator-m6-verified"
    state = {
        "schema": "device-operation/v1",
        "log": "fake transport completed",
        "phase": "COMPLETE",
        "progress": 100,
        "errorCode": None,
        "steps": [],
        "backup": None,
        "verification": {
            "ok": True,
            "deploymentOk": True,
            "fileHashes": {"main.py": "a" * 64},
            "summary": "Fake transport readback matched.",
        },
        "cancelable": False,
        "metadata": {
            "channel": "USB_SERIAL",
            "targetId": session.id,
            "codeRunId": "code-run-current",
            "fakeTransport": True,
        },
    }
    devices.create_operation(
        project_id=work_id,
        session_id=session.id,
        operation_id=operation_id,
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="Fake transport upload",
        log=json.dumps(state),
        status=DeviceOperationStatus.COMPLETED,
    )
    return session.id, operation_id


def _accepted_code(work_id: str) -> CodeRun:
    now = datetime.now(UTC).isoformat()
    code_run_id = "code-creator-m6-accepted"
    return CodeRun(
        id=code_run_id,
        projectId=work_id,
        specRunId="spec-creator-m6",
        version=1,
        status=CodeRunStatus.ACCEPTED,
        workspaceRoot=f"workspace://{work_id}/code/v1",
        maxRetries=0,
        retries=0,
        files=[
            CodeFile(
                id="code-file-creator-m6-main",
                codeRunId=code_run_id,
                projectId=work_id,
                kind=CodeFileKind.MAIN,
                path="src/main.py",
                language="python",
                content="print('creator-m6')\n",
                createdAt=now,
            )
        ],
        patch=CodePatch(
            id="patch-creator-m6",
            codeRunId=code_run_id,
            projectId=work_id,
            summary="Creator M6 accepted mock code",
            diff="",
            createdAt=now,
        ),
        testResult=CodeTestResult(
            ok=True,
            command="mock-validation",
            output="passed",
            createdAt=now,
            checks=[],
        ),
        createdAt=now,
        updatedAt=now,
        acceptedAt=now,
    )


def _device_service(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    transport: MockDeviceTransport,
) -> tuple[DeviceOperationService, str, CodeRun]:
    repository, work_id, _scenario_id = _prepared_work(tmp_path)
    code_run = _accepted_code(work_id)

    class FakeCodeRepository:
        def __init__(self, _db_path) -> None:
            pass

        def get_current_code(self, project_id: str) -> CodeRun | None:
            return code_run if project_id == work_id else None

    monkeypatch.setattr(
        "zhangwen.devices.service.CodeRepository",
        FakeCodeRepository,
    )
    return (
        DeviceOperationService(repository._db_path, tmp_path, transport),
        work_id,
        code_run,
    )


def _operation_state(channel: DeviceDeploymentChannel) -> str:
    return json.dumps(
        {
            "schema": "device-operation/v1",
            "log": "queued",
            "phase": "QUEUED",
            "progress": 0,
            "errorCode": None,
            "steps": [],
            "backup": None,
            "verification": None,
            "cancelable": True,
            "metadata": {"channel": channel.value, "fingerprint": "creator-m6"},
        },
        separators=(",", ":"),
    )


def _command(
    client: TestClient,
    repository: CreatorRepository,
    work_id: str,
    command: str,
    key: str,
    payload: dict[str, object],
):
    return client.post(
        f"/api/creator/works/{work_id}/commands/{command}",
        headers=HEADERS,
        json={
            "baseProjectVersion": repository.workspace(work_id).project_version,
            "idempotencyKey": key,
            "payload": payload,
        },
    )


def test_m6_requires_real_connection_deployment_and_separate_physical_run(tmp_path) -> None:
    repository, work_id, scenario_id = _prepared_work(tmp_path)
    session_id, operation_id = _verified_deployment(tmp_path, work_id)
    client = TestClient(app)

    connection = _command(
        client,
        repository,
        work_id,
        "RECORD_DEVICE_CONNECTION",
        "creator-m6-device-connection",
        {
            "passed": True,
            "summary": "Fake 串口身份与当前场景匹配",
            "sourceId": session_id,
            "bindings": {"channel": "USB_SERIAL"},
        },
    )
    assert connection.status_code == 200, connection.json()
    assert connection.json()["workspace"]["verificationLevel"] == 4

    deployment = _command(
        client,
        repository,
        work_id,
        "RECORD_DEPLOYMENT",
        "creator-m6-deployment",
        {
            "passed": True,
            "summary": "Fake transport 文件回读与运行时验证通过",
            "sourceId": operation_id,
            "bindings": {"codeRunId": "code-run-current"},
        },
    )
    assert deployment.status_code == 200, deployment.json()
    assert deployment.json()["workspace"]["verificationLevel"] == 4

    physical = client.post(
        f"/api/creator/works/{work_id}/physical-runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m6-physical-pass",
            "deploymentOperationId": operation_id,
            "targetId": session_id,
            "operator": "第二测试用户",
            "emergencyStopVerified": True,
            "scenarioResults": [
                {"scenarioId": scenario_id, "observed": True, "note": "逐项观察通过"}
            ],
        },
    )
    assert physical.status_code == 200, physical.json()
    assert physical.json()["run"]["passed"] is True
    physical_run = physical.json()["run"]
    exact_retry = client.post(
        f"/api/creator/works/{work_id}/physical-runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m6-physical-pass",
            "deploymentOperationId": operation_id,
            "targetId": session_id,
            "operator": physical_run["operator"],
            "emergencyStopVerified": True,
            "scenarioResults": physical_run["scenarioResults"],
        },
    )
    assert exact_retry.status_code == 200
    assert exact_retry.json() == physical.json()
    changed_retry = client.post(
        f"/api/creator/works/{work_id}/physical-runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m6-physical-pass",
            "deploymentOperationId": operation_id,
            "targetId": session_id,
            "operator": "changed display",
            "emergencyStopVerified": True,
            "scenarioResults": physical_run["scenarioResults"],
        },
    )
    assert changed_retry.status_code == 409
    assert changed_retry.json()["detail"]["code"] == "CREATOR_IDEMPOTENCY_KEY_REUSED"

    behavior = _command(
        client,
        repository,
        work_id,
        "RECORD_PHYSICAL_BEHAVIOR",
        "creator-m6-physical-evidence",
        {
            "passed": True,
            "summary": "全部真机场景通过",
            "sourceId": physical.json()["run"]["id"],
        },
    )
    assert behavior.status_code == 200, behavior.json()
    assert behavior.json()["workspace"]["verificationLevel"] == 5


def test_m6_rejects_forged_device_and_incomplete_physical_scenarios(tmp_path) -> None:
    repository, work_id, scenario_id = _prepared_work(tmp_path)
    client = TestClient(app)
    forged = _command(
        client,
        repository,
        work_id,
        "RECORD_DEVICE_CONNECTION",
        "creator-m6-forged-device",
        {"passed": True, "summary": "伪造设备", "sourceId": "device-not-real"},
    )
    assert forged.status_code == 409
    assert forged.json()["detail"]["code"] == "CREATOR_DEVICE_CONNECTION_NOT_READY"

    session_id, operation_id = _verified_deployment(tmp_path, work_id)
    connection = _command(
        client,
        repository,
        work_id,
        "RECORD_DEVICE_CONNECTION",
        "creator-m6-valid-device",
        {"passed": True, "summary": "真实 Fake 会话", "sourceId": session_id},
    )
    assert connection.status_code == 200
    deployment = _command(
        client,
        repository,
        work_id,
        "RECORD_DEPLOYMENT",
        "creator-m6-valid-deploy",
        {"passed": True, "summary": "回读通过", "sourceId": operation_id},
    )
    assert deployment.status_code == 200

    incomplete = client.post(
        f"/api/creator/works/{work_id}/physical-runs",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m6-physical-fail",
            "deploymentOperationId": operation_id,
            "targetId": session_id,
            "operator": "测试用户",
            "emergencyStopVerified": False,
            "scenarioResults": [
                {"scenarioId": scenario_id, "observed": False, "note": "尚未通过"}
            ],
        },
    )
    assert incomplete.status_code == 200
    assert incomplete.json()["run"]["passed"] is False
    behavior = _command(
        client,
        repository,
        work_id,
        "RECORD_PHYSICAL_BEHAVIOR",
        "creator-m6-reject-failed-run",
        {
            "passed": True,
            "summary": "不应升级",
            "sourceId": incomplete.json()["run"]["id"],
        },
    )
    assert behavior.status_code == 409
    assert behavior.json()["detail"]["code"] == "CREATOR_PHYSICAL_RUN_NOT_PASSED"


def test_creator_m6_rejects_attached_unverified_usb_connection_evidence(
    tmp_path,
) -> None:
    repository, work_id, _scenario_id = _prepared_work(tmp_path)
    devices = DeviceRepository(repository._db_path)
    session = devices.connect_mock_port(
        work_id,
        "mock_port_esp32_s3",
        SupportedDeviceBoardId.DFROBOT_K10,
    )
    with sqlite3.connect(repository._db_path) as conn:
        conn.execute(
            "UPDATE device_sessions SET status = ? WHERE id = ?",
            (DeviceSessionStatus.ATTACHED_UNVERIFIED.value, session.id),
        )
        conn.commit()

    response = _command(
        TestClient(app),
        repository,
        work_id,
        "RECORD_DEVICE_CONNECTION",
        "creator-m6-unverified-usb",
        {
            "passed": True,
            "summary": "尚未完成精确身份确认的 USB 会话",
            "sourceId": session.id,
            "bindings": {"channel": "USB_SERIAL"},
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CREATOR_DEVICE_CONNECTION_NOT_READY"


def test_m6_device_catalog_projects_versioned_registry_and_peer_channel_contracts() -> None:
    response = TestClient(app).get("/api/creator/device-packages")
    assert response.status_code == 200

    declarations = list_device_packages()
    assert response.json()["packages"] == [
        {
            "id": package.id.value,
            "version": package.version,
            "displayName": package.display_name,
            "boardProfileId": package.board_profile_id.value,
            "capabilities": list(package.capabilities),
                "deploymentChannels": [
                    channel.id.value for channel in package.deployment_channels
                ],
                "interactiveConsoleChannels": [
                    channel.id.value
                    for channel in package.deployment_channels
                    if channel.interactive_console
                ],
                "simulationModes": list(package.simulation_modes),
                "source": package.source,
            }
        for package in declarations
    ]

    for package in declarations:
        channels = {
            channel.id: channel for channel in package.deployment_channels
        }
        assert set(channels) == {
            DeviceDeploymentChannel.USB_SERIAL,
            DeviceDeploymentChannel.ESP_CLAW,
        }
        usb = channels[DeviceDeploymentChannel.USB_SERIAL]
        claw = channels[DeviceDeploymentChannel.ESP_CLAW]
        assert usb.runtime == "MICROPYTHON"
        assert usb.connection_contract == "MICROPYTHON_IDENTITY_V1"
        assert usb.requires_pairing is False
        assert claw.runtime == "ESP_CLAW_LUA"
        assert claw.connection_contract == "ESP_CLAW_STATUS_MCP_V1"
        assert claw.requires_pairing is True
        assert usb.requires_file_readback is claw.requires_file_readback is True


@pytest.mark.asyncio
async def test_m6_espclaw_pairing_rejects_missing_board_identity_handshake(
    tmp_path,
) -> None:
    repository, work_id, _scenario_id = _prepared_work(tmp_path)

    class MissingIdentityAdapter:
        def __init__(self) -> None:
            self.calls = 0

        async def handshake(
            self,
            _web_endpoint,
            _mcp_endpoint,
            *,
            cancel,
            timeout_seconds,
        ) -> EspClawHandshake:
            self.calls += 1
            return EspClawHandshake(
                storage_base_path="/fatfs",
                capabilities=(
                    "lua_get_async_job",
                    "lua_run_script_async",
                    "lua_stop_async_job",
                ),
                file_readback_capable=True,
                reported_board_id=None,
            )

    adapter = MissingIdentityAdapter()
    service = DeviceOperationService(
        repository._db_path,
        tmp_path,
        MockDeviceTransport(),
        espclaw_adapter=adapter,
    )

    with pytest.raises(DeviceServiceError) as captured:
        await service.pair_espclaw_endpoint(
            project_id=work_id,
            web_endpoint="http://edge-agent.local:80",
            mcp_endpoint="http://edge-agent.local:9100/device-mcp",
            board_id=SupportedDeviceBoardId.DFROBOT_K10,
            confirm_trusted_lan=True,
            confirm_admin_mode=True,
            confirm_board_identity=True,
        )

    assert captured.value.code == "ESP_CLAW_BOARD_IDENTITY_REQUIRED"
    assert adapter.calls == 1
    assert DeviceRepository(repository._db_path).list_espclaw_endpoints(work_id) == []


@pytest.mark.asyncio
async def test_m6_usb_mock_upload_is_idempotent_exclusive_and_cancelable(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_id = "mock_port_esp32_s3"
    transport = MockDeviceTransport(
        files={port_id: {"main.py": b"previous-main"}},
        delays={"upload": 0.2},
    )
    service, work_id, code_run = _device_service(tmp_path, monkeypatch, transport)
    session = await service.connect(
        work_id,
        port_id,
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    operation, _ = await service.start_upload(
        project_id=work_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="creator-m6-usb-cancel",
        confirm_write=True,
    )
    for _ in range(200):
        if any(name == "upload" for name, _args in transport.calls):
            break
        await asyncio.sleep(0.001)
    assert any(name == "upload" for name, _args in transport.calls)

    repeated, _ = await service.start_upload(
        project_id=work_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id=operation.id,
        confirm_write=True,
    )
    assert repeated.id == operation.id
    assert list(service._tasks) == [operation.id]

    with pytest.raises(DeviceServiceError) as concurrent:
        await service.start_upload(
            project_id=work_id,
            session_id=session.id,
            code_run_id=code_run.id,
            operation_id="creator-m6-usb-concurrent",
            confirm_write=True,
        )
    assert concurrent.value.code == "DEVICE_PORT_BUSY"

    canceled, canceled_session = await service.cancel_operation(
        work_id,
        operation.id,
    )
    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.errorCode == "DEVICE_OPERATION_CANCELED"
    assert canceled_session.status == DeviceSessionStatus.MANAGED
    assert transport.files[port_id]["main.py"] == b"previous-main"


@pytest.mark.asyncio
async def test_m6_usb_readback_failure_restores_previous_file(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    port_id = "mock_port_esp32_s3"

    class ReadbackMismatchTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__(files={port_id: {"main.py": b"previous-main"}})
            self.corrupt_next_main_read = True

        async def read_file(
            self,
            session,
            path,
            *,
            cancel,
            timeout_seconds,
        ):
            result, content = await super().read_file(
                session,
                path,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            if path == "main.py" and self.corrupt_next_main_read:
                self.corrupt_next_main_read = False
                return result, b"corrupt-readback"
            return result, content

    transport = ReadbackMismatchTransport()
    service, work_id, code_run = _device_service(tmp_path, monkeypatch, transport)
    session = await service.connect(
        work_id,
        port_id,
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    operation, _ = await service.start_upload(
        project_id=work_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="creator-m6-usb-readback-failure",
        confirm_write=True,
    )
    await service.wait(operation.id)
    failed, failed_session = service.get_operation(work_id, operation.id)

    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "DEVICE_READBACK_MISMATCH"
    assert failed_session.status == DeviceSessionStatus.ERROR
    assert transport.files[port_id]["main.py"] == b"previous-main"
    assert any(
        step.phase == DeviceOperationPhase.RESTORE and step.exitCode == 0
        for step in failed.steps
    )


def test_m6_usb_and_espclaw_share_one_project_mutation_lease(tmp_path) -> None:
    repository, work_id, _scenario_id = _prepared_work(tmp_path)
    devices = DeviceRepository(repository._db_path)
    serial_session = devices.connect_mock_port(
        work_id,
        "mock_port_esp32_s3",
        SupportedDeviceBoardId.DFROBOT_K10,
    )
    endpoint = devices.pair_espclaw_endpoint(
        project_id=work_id,
        web_endpoint="http://edge-agent.local:80",
        mcp_endpoint="http://edge-agent.local:9100/device-mcp",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
        handshake=EspClawHandshake(
            storage_base_path="/fatfs",
            capabilities=(
                "lua_get_async_job",
                "lua_run_script_async",
                "lua_stop_async_job",
            ),
            file_readback_capable=True,
            reported_board_id=SupportedDeviceBoardId.DFROBOT_K10.value,
        ),
    )
    claw_session_id = devices.get_espclaw_session_id(work_id, endpoint.id)
    serial_state = _operation_state(DeviceDeploymentChannel.USB_SERIAL)
    devices.reserve_operation(
        project_id=work_id,
        session_id=serial_session.id,
        operation_id="creator-m6-serial-active",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="mpremote",
        log=serial_state,
        fingerprint="creator-m6-serial",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )

    with pytest.raises(DeviceProjectLeaseBusy):
        devices.reserve_operation(
            project_id=work_id,
            session_id=claw_session_id,
            operation_id="creator-m6-claw-blocked",
            kind=DeviceOperationKind.UPLOAD_CODE,
            command_label="ESP-Claw Web Console + MCP Lua",
            log=_operation_state(DeviceDeploymentChannel.ESP_CLAW),
            fingerprint="creator-m6-claw-blocked",
            claimed_status=DeviceSessionStatus.UPLOADING,
        )

    devices.update_operation(
        work_id,
        "creator-m6-serial-active",
        status=DeviceOperationStatus.COMPLETED,
        log=serial_state,
        completed_at=datetime.now(UTC).isoformat(),
    )
    devices.set_session_status(
        work_id,
        serial_session.id,
        DeviceSessionStatus.READY,
    )
    claw_state = _operation_state(DeviceDeploymentChannel.ESP_CLAW)
    devices.reserve_operation(
        project_id=work_id,
        session_id=claw_session_id,
        operation_id="creator-m6-claw-active",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="ESP-Claw Web Console + MCP Lua",
        log=claw_state,
        fingerprint="creator-m6-claw",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )

    with pytest.raises(DeviceProjectLeaseBusy):
        devices.reserve_operation(
            project_id=work_id,
            session_id=serial_session.id,
            operation_id="creator-m6-serial-blocked",
            kind=DeviceOperationKind.UPLOAD_CODE,
            command_label="mpremote",
            log=serial_state,
            fingerprint="creator-m6-serial-blocked",
            claimed_status=DeviceSessionStatus.UPLOADING,
        )
