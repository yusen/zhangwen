"""Safe device transport/service tests; no test reaches host serial APIs."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sqlite3
import time
from datetime import UTC, datetime
from pathlib import Path

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
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.devices import router as devices_router
from zhangwen.devices.models import (
    DeviceOperationKind,
    DeviceOperationPhase,
    DeviceOperationStatus,
    DevicePort,
    DeviceSessionStatus,
    DeviceTerminalStatus,
)
from zhangwen.devices.repository import (
    DeviceDeploymentSessionMismatch,
    DeviceRepository,
)
from zhangwen.devices.service import (
    DeviceOperationService,
    DeviceServiceError,
    FIRMWARE_CONFIRMATION_PHRASE,
    TERMINAL_UNLOCK_CONFIRMATION_PHRASE,
    evaluate_watering_smoke_output,
)
from zhangwen.devices.transport import (
    DeviceTransportCanceled,
    DeviceTransportError,
    DeviceTransportTimedOut,
    MockDeviceTransport,
    SubprocessDeviceTransport,
    TransportResult,
    TransportSession,
)
from zhangwen.main import app
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalSection
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository


DESKTOP_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "test-token",
}


@pytest.mark.asyncio
async def test_connect_materializes_confirmed_scene_without_prior_scene_get(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, _code_run = _service(tmp_path, transport, monkeypatch)

    session = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )

    assert session.board == SupportedDeviceBoardId.DFROBOT_K10.value
    assert [name for name, _ in transport.calls] == ["connect"]


@pytest.mark.asyncio
async def test_connect_rejects_scene_board_mismatch_before_mock_transport_call(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, _code_run = _service(tmp_path, transport, monkeypatch)

    with pytest.raises(DeviceServiceError) as captured:
        await service.connect(
            project_id,
            "mock_port_esp32_s3",
            board_id=SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
        )

    assert captured.value.code == "DEVICE_PROJECT_BOARD_MISMATCH"
    assert transport.calls == []


@pytest.mark.asyncio
async def test_connect_without_approved_project_scene_fails_before_transport_call(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="unconfirmed K10 project",
        project_name="unconfirmed device project",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    transport = MockDeviceTransport()
    service = DeviceOperationService(repository.db_path, tmp_path, transport)

    with pytest.raises(DeviceServiceError) as captured:
        await service.connect(
            workspace.project.id,
            "mock_port_esp32_s3",
            board_id=SupportedDeviceBoardId.DFROBOT_K10,
        )

    assert captured.value.code == "DEVICE_LAB_SCENE_REQUIRED"
    assert transport.calls == []


@pytest.mark.asyncio
async def test_serial_entrypoints_recheck_current_scene_board_before_device_io(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    with sqlite3.connect(service._db_path) as conn:
        conn.execute(
            "UPDATE device_sessions SET board = ? WHERE id = ?",
            (SupportedDeviceBoardId.XIAO_ESP32S3_SENSE.value, session.id),
        )
    transport.calls.clear()

    async_calls = (
        service.start_terminal(project_id, session.id),
        service.takeover_runtime(project_id, session.id),
        service.start_upload(
            project_id=project_id,
            session_id=session.id,
            code_run_id=code_run.id,
            operation_id="scene_mismatch_upload_0001",
            confirm_write=True,
        ),
        service.start_parameter_sync(
            project_id=project_id,
            session_id=session.id,
            parameter_set_id="missing-parameter-set",
            operation_id="scene_mismatch_params_0001",
            confirm_sync=True,
        ),
        service.start_firmware_flash(
            project_id=project_id,
            session_id=session.id,
            candidate_id=None,
            confirmation_token=None,
            operation_id="scene_mismatch_flash_0001",
            address=None,
            confirm_flash=False,
        ),
    )
    for call in async_calls:
        with pytest.raises(DeviceServiceError) as captured:
            await call
        assert captured.value.code == "DEVICE_PROJECT_BOARD_MISMATCH"

    with pytest.raises(DeviceServiceError) as application_error:
        service.prepare_application_install(
            project_id=project_id,
            session_id=session.id,
            application_id="missing-application",
            board_id=SupportedDeviceBoardId.XIAO_ESP32S3_SENSE,
            confirm_board_identity=True,
        )
    assert application_error.value.code == "DEVICE_PROJECT_BOARD_MISMATCH"
    with pytest.raises(DeviceServiceError) as firmware_error:
        service.prepare_firmware(
            project_id=project_id,
            session_id=session.id,
            candidate_id="missing-candidate",
            address=0,
        )
    assert firmware_error.value.code == "DEVICE_PROJECT_BOARD_MISMATCH"

    repository = DeviceRepository(service._db_path)
    with pytest.raises(DeviceDeploymentSessionMismatch):
        repository.upload_code_dry_run(
            project_id=project_id,
            session_id=session.id,
            code_run=code_run,
        )
    with pytest.raises(DeviceDeploymentSessionMismatch):
        repository.firmware_flash_dry_run(
            project_id=project_id,
            session_id=session.id,
        )
    assert transport.calls == []


@pytest.mark.asyncio
async def test_read_only_terminal_exposes_micropython_errors_and_can_be_cleared(
    tmp_path: Path,
    monkeypatch,
) -> None:
    port_id = "mock_port_esp32_s3"
    transport = MockDeviceTransport(
        terminal_chunks={
            port_id: [
                "Traceback (most recent call last):\n",
                "  File \"main.py\", line 7, in <module>\n",
                "NameError: name 'missing_pin' isn't defined\n",
                "loop started\n",
            ]
        }
    )
    service, project_id, _code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(
        project_id, port_id, board_id=SupportedDeviceBoardId.DFROBOT_K10
    )

    started = await service.start_terminal(project_id, session.id)
    assert started.status in {
        DeviceTerminalStatus.STARTING,
        DeviceTerminalStatus.RUNNING,
    }
    for _ in range(20):
        snapshot = service.get_terminal(project_id, session.id)
        if "loop started" in snapshot.output:
            break
        await asyncio.sleep(0.01)

    snapshot = service.get_terminal(project_id, session.id)
    assert snapshot.status == DeviceTerminalStatus.RUNNING
    assert "NameError: name 'missing_pin' isn't defined" in snapshot.output
    assert "loop started" in snapshot.output
    assert snapshot.revision > 0

    cleared = service.clear_terminal(project_id, session.id)
    assert cleared.output == ""
    assert cleared.status == DeviceTerminalStatus.RUNNING

    stopped = await service.stop_terminal(project_id, session.id)
    assert stopped.status == DeviceTerminalStatus.STOPPED
    assert sum(name == "terminal" for name, _ in transport.calls) == 1


@pytest.mark.asyncio
async def test_professional_terminal_input_requires_ephemeral_unlock_and_is_not_logged(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, _code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    await service.start_terminal(project_id, session.id)
    await asyncio.sleep(0)

    with pytest.raises(DeviceServiceError) as locked:
        await service.write_terminal_input(
            project_id,
            session.id,
            unlock_token="not-a-valid-terminal-token",
            value="print('secret')\r\n",
        )
    assert locked.value.code == "DEVICE_TERMINAL_UNLOCK_REQUIRED"

    unlock = service.unlock_terminal_input(
        project_id,
        session.id,
        confirm_professional_mode=True,
        confirmation_phrase=TERMINAL_UNLOCK_CONFIRMATION_PHRASE,
    )
    before = service.get_terminal(project_id, session.id).output
    written = await service.write_terminal_input(
        project_id,
        session.id,
        unlock_token=unlock.unlockToken,
        value="print('ephemeral')\r\n",
    )
    assert written.output == before
    terminal_write = next(
        arguments
        for name, arguments in transport.calls
        if name == "terminal_write"
    )
    assert terminal_write == ("mock_port_esp32_s3", len("print('ephemeral')\r\n"))
    assert "ephemeral" not in json.dumps(transport.calls)

    await service.stop_terminal(project_id, session.id)
    with pytest.raises(DeviceServiceError) as expired:
        await service.write_terminal_input(
            project_id,
            session.id,
            unlock_token=unlock.unlockToken,
            value="print('again')\r\n",
        )
    assert expired.value.code in {
        "DEVICE_SESSION_NOT_READY",
        "DEVICE_TERMINAL_UNLOCK_REQUIRED",
        "DEVICE_TERMINAL_NOT_RUNNING",
    }


@pytest.mark.asyncio
async def test_upload_stops_terminal_and_restarts_it_after_normal_boot(
    tmp_path: Path,
    monkeypatch,
) -> None:
    port_id = "mock_port_esp32_s3"
    transport = MockDeviceTransport(
        terminal_chunks={port_id: ["SyntaxError: invalid syntax\n"]},
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(
        project_id, port_id, board_id=SupportedDeviceBoardId.DFROBOT_K10
    )
    await service.start_terminal(project_id, session.id)

    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_terminal_restart_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    for _ in range(20):
        snapshot = service.get_terminal(project_id, session.id)
        if snapshot.status == DeviceTerminalStatus.RUNNING:
            break
        await asyncio.sleep(0.01)

    completed, _ = service.get_operation(project_id, operation.id)
    snapshot = service.get_terminal(project_id, session.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert snapshot.status == DeviceTerminalStatus.RUNNING
    assert "SyntaxError: invalid syntax" in snapshot.output
    assert sum(name == "terminal" for name, _ in transport.calls) == 2
    assert next(
        index for index, (name, _) in enumerate(transport.calls) if name == "start_runtime"
    ) < max(
        index for index, (name, _) in enumerate(transport.calls) if name == "terminal"
    )
    assert all(name != "hard_reset" for name, _ in transport.calls)

    disconnected = await service.disconnect(project_id, session.id)
    assert disconnected.status == DeviceSessionStatus.DISCONNECTED
    assert service.get_terminal(project_id, session.id).status == DeviceTerminalStatus.STOPPED


@pytest.mark.asyncio
async def test_watering_smoke_evidence_is_read_only_and_persisted_on_real_upload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    port_id = "mock_port_esp32_s3"
    transport = MockDeviceTransport(
        terminal_chunks={
            port_id: [
                "ZW_WATER event=sample moisture=720 state=WET pump=OFF\n",
                "ZW_WATER event=sample moisture=715 state=WET pump=OFF\n",
                "ZW_WATER event=sample moisture=280 state=DRY pump=ON\n",
                "ZW_WATER event=pump_stop pump=OFF elapsed_ms=2500\n",
            ]
        },
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(
        project_id, port_id, board_id=SupportedDeviceBoardId.DFROBOT_K10
    )
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_watering_smoke_001",
        confirm_write=True,
    )
    await service.wait(operation.id)
    for _ in range(20):
        if "pump_stop" in service.get_terminal(project_id, session.id).output:
            break
        await asyncio.sleep(0.01)

    calls_before = list(transport.calls)
    evidence, updated = service.evaluate_watering_smoke(
        project_id,
        session.id,
        operation.id,
    )

    assert evidence.ok is True
    assert evidence.sampleCount == 3
    assert evidence.wetPumpOffOk is True
    assert evidence.dryLimitedRunOk is True
    assert updated.metadata["runtimeEvidence"]["ok"] is True
    assert updated.artifactVersionId is not None
    assert transport.calls == calls_before
    await service.stop_terminal(project_id, session.id)


def test_watering_smoke_rejects_unhandled_exception_and_overlong_pump_run() -> None:
    evidence = evaluate_watering_smoke_output(
        "\n".join(
            [
                "ZW_WATER event=sample moisture=700 state=WET pump=OFF",
                "ZW_WATER event=sample moisture=250 state=DRY pump=ON",
                "ZW_WATER event=sample moisture=240 state=DRY pump=ON",
                "ZW_WATER event=pump_stop pump=OFF elapsed_ms=3500",
                "Traceback (most recent call last):",
            ]
        ),
        session_id="session_1",
        operation_id="operation_1",
    )

    assert evidence.ok is False
    assert evidence.continuousMoistureOk is True
    assert evidence.dryLimitedRunOk is False
    assert evidence.noUnhandledException is False


@pytest.fixture(autouse=True)
def desktop_capability(monkeypatch):
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "test-token")
    devices_router.configure_device_transport(None)
    yield
    devices_router.configure_device_transport(None)


@pytest.mark.asyncio
async def test_attach_is_non_executing_and_takeover_probes_only_after_ctrl_c(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, _code_run = _service(tmp_path, transport, monkeypatch)

    attached = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )

    assert attached.status == DeviceSessionStatus.ATTACHED_UNVERIFIED
    assert [name for name, _args in transport.calls] == ["connect"]

    managed = await service.takeover_runtime(project_id, attached.id)

    assert managed.status == DeviceSessionStatus.MANAGED
    names = [name for name, _args in transport.calls]
    assert names.index("interrupt_runtime") < names.index("identity")
    assert "hard_reset" not in names


@pytest.mark.asyncio
async def test_runtime_busy_never_resets_without_phrase_then_reenumerates_and_breaks_in(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class ResetRecoveryTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__()
            self.interrupt_attempts = 0

        async def interrupt_runtime(self, session, *, cancel, timeout_seconds):
            self.interrupt_attempts += 1
            if self.interrupt_attempts <= 3:
                self.calls.append(("interrupt_runtime", (session.port.id,)))
                return TransportResult(71, "runtime ignored Ctrl-C")
            return await super().interrupt_runtime(
                session,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )

    transport = ResetRecoveryTransport()
    service, project_id, _code_run = _service(tmp_path, transport, monkeypatch)
    attached = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )

    with pytest.raises(DeviceServiceError) as cooperative:
        await service.takeover_runtime(project_id, attached.id)
    assert cooperative.value.code == "DEVICE_RUNTIME_BUSY"
    assert all(name != "hard_reset" for name, _args in transport.calls)

    with pytest.raises(DeviceServiceError) as wrong_phrase:
        await service.takeover_runtime(
            project_id,
            attached.id,
            confirm_hardware_reset=True,
            confirmation_phrase="reset",
        )
    assert wrong_phrase.value.code == "DEVICE_HARD_RESET_CONFIRMATION_REQUIRED"
    assert all(name != "hard_reset" for name, _args in transport.calls)

    managed = await service.takeover_runtime(
        project_id,
        attached.id,
        confirm_hardware_reset=True,
        confirmation_phrase="确认硬件复位",
    )
    assert managed.status == DeviceSessionStatus.MANAGED
    names = [name for name, _args in transport.calls]
    assert names.count("hard_reset") == 1
    assert names.index("hard_reset") < names.index("scan")
    assert names.index("scan") < names.index("identity")


@pytest.mark.asyncio
async def test_mock_upload_backs_up_reads_back_is_idempotent_and_disconnects(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}}
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)

    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_operation_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    completed, completed_session = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.backup is not None
    assert completed.backup.paths == ["main.py"]
    assert completed.verification is not None and completed.verification.ok is True
    assert completed.verification.deploymentOk is True
    assert completed.verification.restartOk is None
    assert completed.verification.runtimeInterruptedOk is True
    assert completed.verification.runtimeStartedOk is True
    assert completed.verification.managementChannelOk is None
    assert completed.verification.reconnectExitCode is None
    assert completed.verification.runtimeExitCode is None
    assert completed.verification.fileHashes["main.py"] == hashlib.sha256(
        _main_content(code_run)
    ).hexdigest()
    assert completed.artifactId == f"artifact_device_log_{project_id}"
    assert completed_session.status == DeviceSessionStatus.RUNTIME_BUSY
    assert transport.files["mock_port_esp32_s3"]["main.py"] == _main_content(code_run)
    assert completed.metadata["launchMode"] == "MICROPYTHON_SOFT_RESET"
    assert completed.metadata["hardwareResetPerformed"] is False
    assert completed.metadata["postStartProbe"] == "TERMINAL_OBSERVATION_ONLY"
    assert sum(name == "hard_reset" for name, _ in transport.calls) == 0
    assert next(
        index for index, (name, _) in enumerate(transport.calls) if name == "interrupt_runtime"
    ) < next(
        index for index, (name, _) in enumerate(transport.calls) if name == "backup"
    )
    assert next(
        index for index, (name, _) in enumerate(transport.calls) if name == "start_runtime"
    ) > max(
        index for index, (name, _) in enumerate(transport.calls) if name == "read"
    )
    assert all(name != "start_main" for name, _ in transport.calls)
    assert (tmp_path / "device-backups" / operation.id / "manifest.json").is_file()

    upload_calls = sum(name == "upload" for name, _ in transport.calls)
    # Simulate both callers having observed "not found" before the first
    # insert committed. The transactional reservation must still recover the
    # same fingerprint and reject a different one without a second write.
    monkeypatch.setattr(service, "_existing_idempotent", lambda *_args: None)
    duplicate, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_operation_001",
        confirm_write=True,
    )
    assert duplicate.id == operation.id
    assert sum(name == "upload" for name, _ in transport.calls) == upload_calls

    other_session = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    with pytest.raises(DeviceServiceError) as idempotency_conflict:
        await service.start_upload(
            project_id=project_id,
            session_id=other_session.id,
            code_run_id=code_run.id,
            operation_id="upload_operation_001",
            confirm_write=True,
        )
    assert idempotency_conflict.value.code == "DEVICE_IDEMPOTENCY_CONFLICT"

    disconnected = await service.disconnect(project_id, session.id)
    assert disconnected.status.value == "DISCONNECTED"
    await service.disconnect(project_id, other_session.id)


@pytest.mark.asyncio
async def test_runtime_interrupt_failure_stops_before_any_device_write_or_reset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
        failures={"interrupt_runtime": 71},
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)

    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_interrupt_failure_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, failed_session = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "DEVICE_RUNTIME_INTERRUPT_FAILED"
    assert any(
        step.phase == DeviceOperationPhase.INTERRUPT_RUNTIME and step.exitCode == 71
        for step in failed.steps
    )
    assert failed_session.status == DeviceSessionStatus.RUNTIME_BUSY
    assert transport.files["mock_port_esp32_s3"]["main.py"] == b"old-main"
    assert [name for name, _ in transport.calls if name in {
        "backup", "upload", "read", "start_runtime", "hard_reset", "delete"
    }] == []
    assert all(step.phase != DeviceOperationPhase.RESTORE for step in failed.steps)


@pytest.mark.asyncio
async def test_runtime_interrupt_timeout_uses_stable_fail_closed_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class InterruptTimeoutTransport(MockDeviceTransport):
        async def interrupt_runtime(self, session, *, cancel, timeout_seconds):
            raise DeviceTransportTimedOut("synthetic interrupt timeout", exit_code=73)

    transport = InterruptTimeoutTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_interrupt_timeout_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, _ = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "DEVICE_RUNTIME_INTERRUPT_FAILED"
    assert any(
        step.phase == DeviceOperationPhase.INTERRUPT_RUNTIME and step.exitCode == 73
        for step in failed.steps
    )
    assert all(name not in {"backup", "upload", "hard_reset"} for name, _ in transport.calls)


@pytest.mark.asyncio
async def test_runtime_start_failure_restores_files_without_hardware_reset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
        failures={"start_runtime": 72},
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)

    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_runtime_start_failure_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, failed_session = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "DEVICE_RUNTIME_START_FAILED"
    assert any(
        step.phase == DeviceOperationPhase.START_RUNTIME and step.exitCode == 72
        for step in failed.steps
    )
    assert failed_session.status == DeviceSessionStatus.ERROR
    assert transport.files["mock_port_esp32_s3"]["main.py"] == b"old-main"
    assert any(
        step.phase == DeviceOperationPhase.RESTORE and step.exitCode == 0
        for step in failed.steps
    )
    assert all(name != "hard_reset" for name, _ in transport.calls)


@pytest.mark.asyncio
async def test_multi_file_upload_backs_up_transfers_and_verifies_every_dependency(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={
            "mock_port_esp32_s3": {
                "main.py": b"old-main",
                "config.py": b"old-config",
            }
        }
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    _add_upload_file(code_run, "src/config.py", "THRESHOLD = 42\n", CodeFileKind.CONFIG)
    _add_upload_file(
        code_run,
        "src/drivers/sensor_reader.py",
        "def read_value():\n    return 42\n",
        CodeFileKind.DRIVER,
    )
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)

    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_multi_file_success_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    completed, _ = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.backup is not None
    assert completed.backup.paths == ["config.py", "main.py"]
    assert completed.verification is not None
    assert set(completed.verification.fileHashes) == {
        "config.py",
        "drivers/sensor_reader.py",
        "main.py",
    }
    assert transport.files["mock_port_esp32_s3"] == {
        "main.py": b"print('new-main')\n",
        "config.py": b"THRESHOLD = 42\n",
        "drivers/sensor_reader.py": b"def read_value():\n    return 42\n",
    }
    upload_call = next(args for name, args in transport.calls if name == "upload")
    assert upload_call[1] == (
        "config.py",
        "drivers/sensor_reader.py",
        "main.py",
    )


@pytest.mark.asyncio
async def test_auxiliary_file_hash_mismatch_restores_old_files_and_removes_new_file(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class AuxiliaryMismatchTransport(MockDeviceTransport):
        async def read_file(self, session, path, *, cancel, timeout_seconds):
            result, content = await super().read_file(
                session,
                path,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            if path == "sensor_reader.py":
                return result, b"corrupt-readback"
            return result, content

    transport = AuxiliaryMismatchTransport(
        files={
            "mock_port_esp32_s3": {
                "main.py": b"old-main",
                "config.py": b"old-config",
            }
        }
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    _add_upload_file(code_run, "src/config.py", "THRESHOLD = 42\n", CodeFileKind.CONFIG)
    _add_upload_file(
        code_run,
        "src/sensor_reader.py",
        "def read_value():\n    return 42\n",
        CodeFileKind.DRIVER,
    )
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)

    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_multi_file_mismatch_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, _ = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "DEVICE_READBACK_MISMATCH"
    assert [
        step.exitCode
        for step in failed.steps
        if step.phase == DeviceOperationPhase.RESTORE
    ] == [0]
    assert transport.files["mock_port_esp32_s3"] == {
        "main.py": b"old-main",
        "config.py": b"old-config",
    }


@pytest.mark.asyncio
async def test_upload_does_not_reenter_repl_after_normal_boot_reset(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class ReconnectFailureTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__(files={"mock_port_esp32_s3": {"main.py": b"old-main"}})
            self.connect_attempts = 0

        async def connect(self, port, *, cancel, timeout_seconds):
            self.connect_attempts += 1
            handle, result = await super().connect(
                port,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            if self.connect_attempts > 1:
                return handle, TransportResult(17, "repl channel unavailable")
            return handle, result

    transport = ReconnectFailureTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_reconnect_nonzero_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    completed, completed_session = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.errorCode is None
    assert completed.phase == DeviceOperationPhase.COMPLETE
    assert completed_session.status == DeviceSessionStatus.RUNTIME_BUSY
    assert completed.backup is not None and completed.backup.restorable is True
    assert completed.verification is not None
    assert completed.verification.ok is True
    assert completed.verification.deploymentOk is True
    assert completed.verification.restartOk is None
    assert completed.verification.runtimeStartedOk is True
    assert completed.verification.managementChannelOk is None
    assert completed.verification.reconnectExitCode is None
    assert completed.verification.runtimeExitCode is None
    assert completed.verification.warnings
    assert all(step.phase != DeviceOperationPhase.RECONNECT for step in completed.steps)
    assert transport.connect_attempts == 1
    assert all(step.phase != DeviceOperationPhase.RESTORE for step in completed.steps)
    assert sum(name == "upload" for name, _ in transport.calls) == 1
    assert transport.files["mock_port_esp32_s3"]["main.py"] == _main_content(code_run)


@pytest.mark.asyncio
async def test_post_reset_repl_timeout_is_not_triggered_by_upload(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class ReconnectTimeoutTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__(files={"mock_port_esp32_s3": {"main.py": b"old-main"}})
            self.connect_attempts = 0

        async def connect(self, port, *, cancel, timeout_seconds):
            self.connect_attempts += 1
            if self.connect_attempts > 1:
                raise DeviceTransportTimedOut("repl reconnect timed out")
            return await super().connect(
                port,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )

    transport = ReconnectTimeoutTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_reconnect_timeout_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    completed, completed_session = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed_session.status == DeviceSessionStatus.RUNTIME_BUSY
    assert completed.verification is not None
    assert completed.verification.deploymentOk is True
    assert completed.verification.restartOk is None
    assert completed.verification.runtimeStartedOk is True
    assert completed.verification.managementChannelOk is None
    assert completed.verification.reconnectExitCode is None
    assert completed.verification.runtimeExitCode is None
    assert completed.verification.warnings
    assert all(step.phase != DeviceOperationPhase.RECONNECT for step in completed.steps)
    assert transport.connect_attempts == 1
    assert all(step.phase != DeviceOperationPhase.RESTORE for step in completed.steps)
    assert sum(name == "upload" for name, _ in transport.calls) == 1
    assert transport.files["mock_port_esp32_s3"]["main.py"] == _main_content(code_run)


@pytest.mark.asyncio
async def test_upload_leaves_next_management_connect_for_a_later_action(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class RetryReconnectTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__(files={"mock_port_esp32_s3": {"main.py": b"old-main"}})
            self.connect_attempts = 0

        async def connect(self, port, *, cancel, timeout_seconds):
            self.connect_attempts += 1
            handle, result = await super().connect(
                port,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )
            if self.connect_attempts == 2:
                return handle, TransportResult(19, "first reconnect failed")
            return handle, result

    transport = RetryReconnectTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_reconnect_retry_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    completed, completed_session = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed_session.status == DeviceSessionStatus.RUNTIME_BUSY
    assert completed.verification is not None
    assert completed.verification.managementChannelOk is None
    assert completed.verification.reconnectExitCode is None
    assert all(step.phase != DeviceOperationPhase.RECONNECT for step in completed.steps)
    assert transport.connect_attempts == 1


@pytest.mark.asyncio
async def test_legacy_reconnect_failure_without_successful_restore_reads_as_completed_warning(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}}
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_legacy_reconnect_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    with sqlite3.connect(service._db_path) as conn:
        raw_row = conn.execute(
            "SELECT log, artifact_version_id FROM device_operations WHERE id = ?",
            (operation.id,),
        ).fetchone()
        raw_log = raw_row[0]
        previous_artifact_version_id = raw_row[1]
        state = json.loads(raw_log)
        state["steps"].append(
            {
                "phase": "RESTART",
                "status": "COMPLETED",
                "exitCode": 0,
                "summary": "旧版主控重启",
                "startedAt": None,
                "completedAt": None,
            }
        )
        state["steps"].append(
            {
                "phase": "RECONNECT",
                "status": "FAILED",
                "exitCode": None,
                "summary": "旧版管理通道重连超时",
                "startedAt": None,
                "completedAt": None,
            }
        )
        for reconnect_step in (
            step for step in state["steps"] if step["phase"] == "RECONNECT"
        ):
            reconnect_step["exitCode"] = None
            reconnect_step["status"] = "FAILED"
        state.pop("verification", None)
        state["status"] = "TIMED_OUT"
        state["errorCode"] = "DEVICE_UPLOAD_TIMEOUT"
        state["log"] = "MicroPython 上传超时。"
        conn.execute(
            "UPDATE device_operations SET status = ?, log = ? WHERE id = ?",
            ("TIMED_OUT", json.dumps(state, ensure_ascii=False), operation.id),
        )

    legacy = DeviceRepository(service._db_path).get_operation(project_id, operation.id)
    assert legacy.status == DeviceOperationStatus.COMPLETED
    assert legacy.errorCode is None
    assert legacy.verification is not None
    assert legacy.verification.ok is True
    assert legacy.verification.deploymentOk is True
    assert legacy.verification.restartOk is True
    assert legacy.verification.managementChannelOk is False
    assert legacy.verification.reconnectExitCode is None
    assert legacy.verification.runtimeExitCode is None
    assert legacy.verification.warnings

    no_reconnect_state = json.loads(json.dumps(state))
    no_reconnect_state["steps"] = [
        step
        for step in no_reconnect_state["steps"]
        if step["phase"] not in {"RECONNECT", "VERIFY_RUNTIME"}
    ]
    no_reconnect_state["errorCode"] = "DEVICE_OPERATION_TIMEOUT"
    no_reconnect_state["log"] = "设备操作超时。"
    for stored_status in ("TIMED_OUT", "FAILED"):
        with sqlite3.connect(service._db_path) as conn:
            conn.execute(
                "UPDATE device_operations SET status = ?, log = ? WHERE id = ?",
                (
                    stored_status,
                    json.dumps(no_reconnect_state, ensure_ascii=False),
                    operation.id,
                ),
            )
        no_reconnect = DeviceRepository(service._db_path).get_operation(
            project_id,
            operation.id,
        )
        assert no_reconnect.status == DeviceOperationStatus.COMPLETED, stored_status
        assert no_reconnect.errorCode is None
        assert no_reconnect.verification is not None
        assert no_reconnect.verification.deploymentOk is True
        assert no_reconnect.verification.restartOk is True
        assert no_reconnect.verification.managementChannelOk is False

    corrected, _ = service.get_operation(project_id, operation.id)
    assert corrected.status == DeviceOperationStatus.COMPLETED
    assert corrected.artifactVersionId == previous_artifact_version_id
    with sqlite3.connect(service._db_path) as conn:
        corrected_row = conn.execute(
            "SELECT status, artifact_version_id FROM device_operations WHERE id = ?",
            (operation.id,),
        ).fetchone()
        corrected_artifact = conn.execute(
            "SELECT preview_json, status FROM artifact_versions WHERE id = ?",
            (corrected_row[1],),
        ).fetchone()
        corrected_artifact_status = conn.execute(
            "SELECT status FROM artifacts WHERE id = ?",
            (corrected.artifactId,),
        ).fetchone()[0]
    assert corrected_row[0] == DeviceOperationStatus.COMPLETED.value
    corrected_artifact_content = json.loads(corrected_artifact[0])["code"]
    assert "状态：COMPLETED" in corrected_artifact_content
    assert "管理通道尚未恢复" in corrected_artifact_content
    assert corrected_artifact[1] == "APPROVED"
    assert corrected_artifact_status == "APPROVED"

    assert corrected.verification is not None
    stable_summary = corrected.verification.summary
    stable_warnings = corrected.verification.warnings
    sync_calls = 0
    original_sync = service._repo.sync_operation_artifact

    def track_artifact_sync(*args, **kwargs):
        nonlocal sync_calls
        sync_calls += 1
        return original_sync(*args, **kwargs)

    monkeypatch.setattr(service._repo, "sync_operation_artifact", track_artifact_sync)
    for _read_number in (2, 3):
        reread, _ = service.get_operation(project_id, operation.id)
        assert reread.status == DeviceOperationStatus.COMPLETED
        assert reread.artifactVersionId == previous_artifact_version_id
        assert reread.verification is not None
        assert reread.verification.managementChannelOk is False
        assert reread.verification.summary == stable_summary
        assert reread.verification.warnings == stable_warnings
    assert sync_calls == 0

    negative_states = {
        "wrong_error_code": {
            **json.loads(json.dumps(no_reconnect_state)),
            "errorCode": "DEVICE_UPLOAD_TIMEOUT",
        },
        "failed_step_after_restart": json.loads(json.dumps(no_reconnect_state)),
        "missing_backup_evidence": json.loads(json.dumps(no_reconnect_state)),
    }
    negative_states["failed_step_after_restart"]["steps"].append(
        {
            "phase": "COMPLETE",
            "status": "FAILED",
            "exitCode": None,
            "summary": "重启后的失败证据",
            "startedAt": None,
            "completedAt": None,
        }
    )
    negative_states["missing_backup_evidence"]["steps"] = [
        step
        for step in negative_states["missing_backup_evidence"]["steps"]
        if step["phase"] != "BACKUP"
    ]
    for label, negative_state in negative_states.items():
        with sqlite3.connect(service._db_path) as conn:
            conn.execute(
                "UPDATE device_operations SET status = ?, log = ? WHERE id = ?",
                ("FAILED", json.dumps(negative_state, ensure_ascii=False), operation.id),
            )
        negative = DeviceRepository(service._db_path).get_operation(project_id, operation.id)
        assert negative.status == DeviceOperationStatus.FAILED, label
        assert negative.errorCode == negative_state["errorCode"], label

    for label, restore_step, deployment_ok in (
        ("success", {"exitCode": 0}, False),
        ("nonzero", {"exitCode": 31}, None),
        ("null", {"exitCode": None}, None),
        ("missing", {}, None),
    ):
        restored_state = json.loads(json.dumps(state))
        restored_state["steps"].append(
            {
                "phase": "RESTORE",
                "status": "COMPLETED" if label == "success" else "FAILED",
                "summary": f"旧流程恢复记录：{label}",
                "startedAt": None,
                "completedAt": None,
                **restore_step,
            }
        )
        with sqlite3.connect(service._db_path) as conn:
            conn.execute(
                "UPDATE device_operations SET status = ?, log = ? WHERE id = ?",
                ("FAILED", json.dumps(restored_state, ensure_ascii=False), operation.id),
            )
        restored = DeviceRepository(service._db_path).get_operation(project_id, operation.id)
        assert restored.status == DeviceOperationStatus.FAILED, label
        assert restored.errorCode == "DEVICE_UPLOAD_TIMEOUT", label
        assert restored.verification is not None
        assert restored.verification.ok is False, label
        assert restored.verification.deploymentOk is deployment_ok, label
        assert restored.verification.restartOk is True, label
        assert restored.verification.managementChannelOk is False, label


@pytest.mark.asyncio
async def test_upload_failure_uses_exit_code_and_restores_previous_files(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class PassTextFailureTransport(MockDeviceTransport):
        def _result(self, phase: str) -> TransportResult:
            return TransportResult(7, "PASS") if phase == "upload" else super()._result(phase)

    transport = PassTextFailureTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}}
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_operation_002",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, _ = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert any(step.exitCode == 7 for step in failed.steps)
    assert transport.files["mock_port_esp32_s3"]["main.py"] == b"old-main"
    assert failed.artifactId == f"artifact_device_log_{project_id}"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_mode", "phase", "exit_code", "error_code"),
    [
        (
            "read_transport_error",
            DeviceOperationPhase.VERIFY_FILES,
            53,
            "MOCK_READ_FAILED",
        ),
        (
            "runtime_start_timeout",
            DeviceOperationPhase.START_RUNTIME,
            52,
            "DEVICE_OPERATION_TIMEOUT",
        ),
    ],
)
async def test_transport_exception_records_original_phase_step_before_restore(
    tmp_path: Path,
    monkeypatch,
    failure_mode: str,
    phase: DeviceOperationPhase,
    exit_code: int,
    error_code: str,
) -> None:
    class OriginalTransportFailure(MockDeviceTransport):
        async def read_file(self, session, path, *, cancel, timeout_seconds):
            if failure_mode == "read_transport_error":
                raise DeviceTransportError(
                    "MOCK_READ_FAILED",
                    "synthetic read failure",
                    exit_code=53,
                )
            return await super().read_file(
                session,
                path,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )

        async def start_runtime(self, session, *, cancel, timeout_seconds):
            if failure_mode == "runtime_start_timeout":
                raise DeviceTransportTimedOut("synthetic runtime start timeout", exit_code=52)
            return await super().start_runtime(
                session,
                cancel=cancel,
                timeout_seconds=timeout_seconds,
            )

    transport = OriginalTransportFailure(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}}
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id=f"upload_original_{failure_mode}_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, _ = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == error_code
    failed_phase_steps = [
        step
        for step in failed.steps
        if step.phase == phase and step.status == DeviceOperationStatus.FAILED
    ]
    assert [step.exitCode for step in failed_phase_steps] == [exit_code]
    restore_index = next(
        index
        for index, step in enumerate(failed.steps)
        if step.phase == DeviceOperationPhase.RESTORE
    )
    original_index = failed.steps.index(failed_phase_steps[0])
    assert original_index < restore_index
    assert failed.metadata["failureEvidence"]["originalErrorCode"] == error_code


@pytest.mark.asyncio
async def test_restart_failure_still_restores_verified_files_and_stays_failed(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
        failures={"start_runtime": 23},
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_restart_failure_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, failed_session = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed_session.status == DeviceSessionStatus.ERROR
    assert transport.files["mock_port_esp32_s3"]["main.py"] == b"old-main"
    assert failed.verification is not None
    assert failed.verification.ok is False
    assert failed.verification.deploymentOk is False
    assert failed.verification.restartOk is None
    assert failed.verification.runtimeStartedOk is False
    assert failed.verification.managementChannelOk is None
    assert any(
        step.phase == DeviceOperationPhase.RESTORE and step.exitCode == 0
        for step in failed.steps
    )


@pytest.mark.asyncio
async def test_upload_no_longer_submits_a_separate_main_start_command(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
        failures={"start_main": 24},
    )
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_main_start_failure_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    completed, completed_session = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.errorCode is None
    assert completed_session.status == DeviceSessionStatus.RUNTIME_BUSY
    assert transport.files["mock_port_esp32_s3"]["main.py"] == _main_content(code_run)
    assert all(name != "start_main" for name, _ in transport.calls)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_mode", "restore_error_code", "restore_exit_code"),
    [
        ("nonzero", "DEVICE_RESTORE_FAILED", 37),
        ("timeout", "DEVICE_RESTORE_TIMEOUT", 38),
        ("transport_cancel", "DEVICE_RESTORE_CANCELED", 39),
        ("async_cancel", "DEVICE_RESTORE_CANCELED", None),
        ("transport_error", "MOCK_RESTORE_LINK_FAILED", 40),
        ("ordinary_error", "DEVICE_RESTORE_FAILED", None),
    ],
)
async def test_restore_failure_always_records_step_and_preserves_both_error_codes(
    tmp_path: Path,
    monkeypatch,
    failure_mode: str,
    restore_error_code: str,
    restore_exit_code: int | None,
) -> None:
    class RestoreFailureTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__(
                files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
                failures={"start_runtime": 23},
            )
            self.upload_attempts = 0

        async def upload_files(self, session, files, *, cancel, timeout_seconds):
            self.upload_attempts += 1
            if self.upload_attempts == 1:
                return await super().upload_files(
                    session,
                    files,
                    cancel=cancel,
                    timeout_seconds=timeout_seconds,
                )
            if failure_mode == "nonzero":
                return TransportResult(37, "restore command failed")
            if failure_mode == "timeout":
                raise DeviceTransportTimedOut("restore timeout", exit_code=38)
            if failure_mode == "transport_cancel":
                raise DeviceTransportCanceled("restore canceled", exit_code=39)
            if failure_mode == "async_cancel":
                raise asyncio.CancelledError
            if failure_mode == "transport_error":
                raise DeviceTransportError(
                    "MOCK_RESTORE_LINK_FAILED",
                    "restore link failed",
                    exit_code=40,
                )
            raise RuntimeError("synthetic restore error")

    transport = RestoreFailureTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id=f"upload_restore_{failure_mode}_001",
        confirm_write=True,
    )
    await service.wait(operation.id)

    failed, failed_session = service.get_operation(project_id, operation.id)
    assert failed.status == DeviceOperationStatus.FAILED
    assert failed.errorCode == "DEVICE_RUNTIME_START_FAILED"
    assert failed_session.status == DeviceSessionStatus.ERROR
    restore_steps = [
        step for step in failed.steps if step.phase == DeviceOperationPhase.RESTORE
    ]
    assert len(restore_steps) == 1
    assert restore_steps[0].status == DeviceOperationStatus.FAILED
    assert restore_steps[0].exitCode == restore_exit_code
    evidence = failed.metadata["failureEvidence"]
    assert evidence["originalErrorCode"] == "DEVICE_RUNTIME_START_FAILED"
    assert evidence["restoreErrorCode"] == restore_error_code
    assert evidence["restoreExitCode"] == restore_exit_code
    assert evidence["restoreSucceeded"] is False
    assert failed.verification is not None
    assert failed.verification.ok is False
    assert failed.verification.deploymentOk is None


@pytest.mark.asyncio
async def test_upload_rejects_an_accepted_but_superseded_code_version(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    newer = code_run.model_copy(update={"id": "code_newer_device_test", "version": 2})

    class NewerCodeRepository:
        def __init__(self, _db_path: Path) -> None:
            pass

        def get_current_code(self, project: str) -> CodeRun | None:
            return newer if project == project_id else None

    monkeypatch.setattr("zhangwen.devices.service.CodeRepository", NewerCodeRepository)
    with pytest.raises(DeviceServiceError) as conflict:
        await service.start_upload(
            project_id=project_id,
            session_id=session.id,
            code_run_id=code_run.id,
            operation_id="upload_operation_stale_001",
            confirm_write=True,
        )
    assert conflict.value.code == "DEVICE_CODE_REVISION_CONFLICT"


@pytest.mark.asyncio
async def test_upload_can_be_canceled_and_non_ready_session_rejects_concurrent_start(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(delays={"upload": 0.2})
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    first, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_operation_003",
        confirm_write=True,
    )
    await asyncio.sleep(0.02)
    monkeypatch.setattr(service, "_existing_idempotent", lambda *_args: None)
    duplicate, duplicate_session = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_operation_003",
        confirm_write=True,
    )
    assert duplicate.id == first.id
    assert duplicate_session.status == DeviceSessionStatus.UPLOADING
    assert list(service._tasks) == [first.id]

    with pytest.raises(DeviceServiceError) as concurrent:
        await service.start_upload(
            project_id=project_id,
            session_id=session.id,
            code_run_id=code_run.id,
            operation_id="upload_operation_004",
            confirm_write=True,
        )
    assert concurrent.value.code == "DEVICE_PORT_BUSY"
    assert concurrent.value.status_code == 409
    with pytest.raises(ValueError):
        DeviceRepository(service._db_path).get_operation(project_id, "upload_operation_004")

    canceled, canceled_session = await service.cancel_operation(project_id, first.id)
    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.errorCode == "DEVICE_OPERATION_CANCELED"
    assert canceled_session.status == DeviceSessionStatus.MANAGED


@pytest.mark.asyncio
async def test_cancel_with_failed_restore_leaves_session_in_error(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class CancelRestoreFailureTransport(MockDeviceTransport):
        def __init__(self) -> None:
            super().__init__(
                files={"mock_port_esp32_s3": {"main.py": b"old-main"}},
                delays={"upload": 0.2},
            )
            self.upload_attempts = 0

        async def upload_files(self, session, files, *, cancel, timeout_seconds):
            self.upload_attempts += 1
            if self.upload_attempts == 1:
                return await super().upload_files(
                    session,
                    files,
                    cancel=cancel,
                    timeout_seconds=timeout_seconds,
                )
            return TransportResult(47, "restore after cancel failed")

    transport = CancelRestoreFailureTransport()
    service, project_id, code_run = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_cancel_restore_failed_001",
        confirm_write=True,
    )
    await asyncio.sleep(0.02)

    canceled, canceled_session = await service.cancel_operation(project_id, operation.id)
    assert canceled.status == DeviceOperationStatus.CANCELED
    assert canceled.errorCode == "DEVICE_OPERATION_CANCELED"
    assert canceled_session.status == DeviceSessionStatus.ERROR
    restore_steps = [
        step for step in canceled.steps if step.phase == DeviceOperationPhase.RESTORE
    ]
    assert [step.exitCode for step in restore_steps] == [47]
    evidence = canceled.metadata["failureEvidence"]
    assert evidence["originalErrorCode"] == "DEVICE_OPERATION_CANCELED"
    assert evidence["restoreErrorCode"] == "DEVICE_RESTORE_FAILED"
    assert evidence["restoreSucceeded"] is False


@pytest.mark.asyncio
async def test_upload_timeout_is_terminal_and_does_not_report_success(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport(delays={"upload": 0.2})
    service, project_id, code_run = _service(
        tmp_path,
        transport,
        monkeypatch,
        upload_timeout_seconds=0.03,
    )
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    operation, _ = await service.start_upload(
        project_id=project_id,
        session_id=session.id,
        code_run_id=code_run.id,
        operation_id="upload_operation_005",
        confirm_write=True,
    )
    await service.wait(operation.id)
    timed_out, _ = service.get_operation(project_id, operation.id)
    assert timed_out.status == DeviceOperationStatus.TIMED_OUT
    assert timed_out.errorCode == "DEVICE_UPLOAD_TIMEOUT"


@pytest.mark.asyncio
async def test_fresh_service_reconciles_orphaned_operations_from_persisted_evidence(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, _ = _service(tmp_path, transport, monkeypatch)
    repository = DeviceRepository(service._db_path)

    partial_session = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    partial_state = _persisted_operation_state(
        fingerprint="partial-orphan-fingerprint",
        steps=[_persisted_step(DeviceOperationPhase.BACKUP, 0)],
        phase=DeviceOperationPhase.TRANSFER,
    )
    repository.reserve_operation(
        project_id=project_id,
        session_id=partial_session.id,
        operation_id="upload_orphan_partial_001",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="mpremote",
        log=json.dumps(partial_state, ensure_ascii=False),
        fingerprint="partial-orphan-fingerprint",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )
    repository.update_operation(
        project_id,
        "upload_orphan_partial_001",
        status=DeviceOperationStatus.RUNNING,
        log=json.dumps(partial_state, ensure_ascii=False),
    )

    restarted = DeviceOperationService(service._db_path, tmp_path, transport)
    partial, partial_current_session = restarted.get_operation(
        project_id,
        "upload_orphan_partial_001",
    )
    assert partial.status == DeviceOperationStatus.FAILED
    assert partial.errorCode == "DEVICE_OPERATION_INTERRUPTED"
    assert partial.phase == DeviceOperationPhase.COMPLETE
    assert partial.cancelable is False
    assert partial.artifactId == f"artifact_device_log_{project_id}"
    assert partial_current_session.status == DeviceSessionStatus.ERROR
    assert partial.metadata["failureEvidence"]["originalErrorCode"] == (
        "DEVICE_OPERATION_INTERRUPTED"
    )

    verified_session = await service.connect(
        project_id,
        "mock_port_esp32_s3",
        board_id=SupportedDeviceBoardId.DFROBOT_K10,
    )
    verified_state = _persisted_operation_state(
        fingerprint="verified-orphan-fingerprint",
        steps=[
            _persisted_step(DeviceOperationPhase.TRANSFER, 0),
            _persisted_step(DeviceOperationPhase.VERIFY_FILES, 0),
            _persisted_step(DeviceOperationPhase.RESTART, 0),
        ],
        phase=DeviceOperationPhase.RECONNECT,
    )
    repository.reserve_operation(
        project_id=project_id,
        session_id=verified_session.id,
        operation_id="upload_orphan_verified_001",
        kind=DeviceOperationKind.UPLOAD_CODE,
        command_label="mpremote",
        log=json.dumps(verified_state, ensure_ascii=False),
        fingerprint="verified-orphan-fingerprint",
        claimed_status=DeviceSessionStatus.UPLOADING,
    )
    repository.update_operation(
        project_id,
        "upload_orphan_verified_001",
        status=DeviceOperationStatus.RUNNING,
        log=json.dumps(verified_state, ensure_ascii=False),
    )

    verified, verified_current_session = restarted.get_latest_operation(project_id) or (None, None)
    assert verified is not None
    assert verified.id == "upload_orphan_verified_001"
    assert verified.status == DeviceOperationStatus.COMPLETED
    assert verified.errorCode is None
    assert verified.verification is not None
    assert verified.verification.deploymentOk is True
    assert verified.verification.restartOk is True
    assert verified.verification.managementChannelOk is False
    assert verified_current_session is not None
    assert verified_current_session.status == DeviceSessionStatus.ERROR


@pytest.mark.asyncio
async def test_firmware_requires_trusted_metadata_phrase_and_verifies_flash(
    tmp_path: Path,
    monkeypatch,
) -> None:
    transport = MockDeviceTransport()
    service, project_id, _ = _service(tmp_path, transport, monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    firmware = b"\xe9" + b"safe-test-firmware" * 32
    candidate = await service.inspect_firmware("firmware.bin", firmware)
    assert candidate.compatible is True
    plan = service.prepare_firmware(
        project_id=project_id,
        session_id=session.id,
        candidate_id=candidate.id,
        address=0,
    )

    with pytest.raises(DeviceServiceError) as phrase_error:
        await service.start_firmware_flash(
            project_id=project_id,
            session_id=session.id,
            candidate_id=candidate.id,
            confirmation_token=plan.confirmationToken,
            operation_id="firmware_operation_001",
            address=0,
            confirm_flash=True,
            confirmation_phrase="错误短语",
        )
    assert phrase_error.value.code == "DEVICE_FLASH_CONFIRMATION_PHRASE_REQUIRED"

    operation, _ = await service.start_firmware_flash(
        project_id=project_id,
        session_id=session.id,
        candidate_id=candidate.id,
        confirmation_token=plan.confirmationToken,
        operation_id="firmware_operation_001",
        address=0,
        confirm_flash=True,
        confirmation_phrase=FIRMWARE_CONFIRMATION_PHRASE,
    )
    await service.wait(operation.id)
    completed, _ = service.get_operation(project_id, operation.id)
    assert completed.status == DeviceOperationStatus.COMPLETED
    assert completed.verification is not None and completed.verification.ok is True
    assert completed.artifactId == f"artifact_device_log_{project_id}"
    assert transport.firmware["mock_port_esp32_s3"] == firmware
    assert all("erase" not in name.lower() for name, _ in transport.calls)

    duplicate, _ = await service.start_firmware_flash(
        project_id=project_id,
        session_id=session.id,
        candidate_id=candidate.id,
        confirmation_token=plan.confirmationToken,
        operation_id="firmware_operation_001",
        address=0,
        confirm_flash=True,
        confirmation_phrase=FIRMWARE_CONFIRMATION_PHRASE,
    )
    assert duplicate.id == completed.id
    assert sum(name == "flash" for name, _ in transport.calls) == 1


@pytest.mark.asyncio
async def test_unknown_firmware_chip_or_offset_is_never_flashable(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class UnknownMetadataTransport(MockDeviceTransport):
        async def inspect_firmware(self, path, *, cancel, timeout_seconds):
            return TransportResult(0, "image parsed", {})

    service, project_id, _ = _service(tmp_path, UnknownMetadataTransport(), monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    candidate = await service.inspect_firmware("unknown.bin", b"\xe9unknown")
    assert candidate.compatible is False
    assert candidate.defaultAddress is None
    assert candidate.targetChip is None
    with pytest.raises(DeviceServiceError) as blocked:
        service.prepare_firmware(
            project_id=project_id,
            session_id=session.id,
            candidate_id=candidate.id,
            address=0,
        )
    assert blocked.value.code == "FIRMWARE_INCOMPATIBLE"


@pytest.mark.asyncio
async def test_known_chip_without_offset_requires_an_explicit_aligned_address(
    tmp_path: Path,
    monkeypatch,
) -> None:
    class KnownChipTransport(MockDeviceTransport):
        async def inspect_firmware(self, path, *, cancel, timeout_seconds):
            return TransportResult(
                0,
                "Detected image type: ESP32-S3",
                {"targetChip": "ESP32-S3", "imageFormat": "esptool-image"},
            )

    service, project_id, _ = _service(tmp_path, KnownChipTransport(), monkeypatch)
    session = await service.connect(project_id, "mock_port_esp32_s3", board_id=SupportedDeviceBoardId.DFROBOT_K10)
    candidate = await service.inspect_firmware("known.bin", b"\xe9known")
    assert candidate.compatible is True
    assert candidate.defaultAddress is None
    with pytest.raises(DeviceServiceError) as missing_address:
        service.prepare_firmware(
            project_id=project_id,
            session_id=session.id,
            candidate_id=candidate.id,
            address=None,
        )
    assert missing_address.value.code == "FIRMWARE_ADDRESS_INVALID"
    plan = service.prepare_firmware(
        project_id=project_id,
        session_id=session.id,
        candidate_id=candidate.id,
        address=0x1000,
    )
    assert plan.address == 0x1000


@pytest.mark.asyncio
async def test_real_backup_probe_skips_missing_files_but_not_probe_failures() -> None:
    port = DevicePort(
        id="opaque-test-port",
        label="Synthetic serial port",
        portName="opaque-test-port",
        chip="ESP32-S3",
        serialNumber=None,
    )
    session = TransportSession("synthetic-session", port)

    class RecordingTransport(SubprocessDeviceTransport):
        def __init__(self, probe: TransportResult) -> None:
            super().__init__(scanner=lambda: [port])
            self.probe = probe
            self.calls: list[list[str]] = []

        async def _mpremote(self, session, args, *, cancel, timeout_seconds):
            self.calls.append(list(args))
            if args[:2] == ["resume", "exec"]:
                return self.probe
            raise AssertionError("missing remote files must not be copied")

    missing = RecordingTransport(TransportResult(0, "__ZW_MISSING__"))
    result, backup = await missing.backup_files(
        session,
        ["main.py"],
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    assert result.exit_code == 0
    assert backup == {}
    assert [call[:2] for call in missing.calls] == [["resume", "exec"]]

    failed_probe = RecordingTransport(TransportResult(7, "transport failed"))
    result, backup = await failed_probe.backup_files(
        session,
        ["main.py"],
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    assert result.exit_code == 7
    assert backup == {}

    class MissingLocalCopyTransport(SubprocessDeviceTransport):
        async def _mpremote(self, session, args, *, cancel, timeout_seconds):
            if args[:2] == ["resume", "exec"]:
                return TransportResult(0, "__ZW_EXISTS__")
            return TransportResult(0, "copy reported success")

    missing_local = MissingLocalCopyTransport(scanner=lambda: [port])
    result, backup = await missing_local.backup_files(
        session,
        ["main.py"],
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    assert result.exit_code != 0
    assert backup == {}


@pytest.mark.asyncio
async def test_real_adapter_builds_fixed_argv_and_preserves_nonzero_exit(
    tmp_path: Path,
) -> None:
    port = DevicePort(
        id="opaque-test-port",
        label="Synthetic serial port",
        portName="opaque-test-port",
        chip="ESP32-S3",
        serialNumber=None,
    )

    class CapturingTransport(SubprocessDeviceTransport):
        def __init__(self) -> None:
            super().__init__(scanner=lambda: [port])
            self.argv: list[list[str]] = []

        async def _run(self, argv, *, cancel, timeout_seconds):
            self.argv.append(list(argv))
            return TransportResult(9, "PASS")

    transport = CapturingTransport()
    session = TransportSession("synthetic-session", port)
    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"\xe9fixed-argv")
    flashed = await transport.flash_firmware(
        session,
        firmware,
        address=0,
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    assert flashed.exit_code == 9
    assert transport.argv[0][1:4] == ["-m", "esptool", "--chip"]
    assert "write-flash" in transport.argv[0]
    assert "erase-flash" not in transport.argv[0]
    assert "erase-all" not in transport.argv[0]


@pytest.mark.asyncio
async def test_real_adapter_hard_resets_into_normal_micropython_boot() -> None:
    port = DevicePort(
        id="opaque-test-port",
        label="Synthetic serial port",
        portName="opaque-test-port",
        chip="ESP32-S3",
        serialNumber=None,
    )

    class CapturingTransport(SubprocessDeviceTransport):
        def __init__(self) -> None:
            super().__init__(scanner=lambda: [port])
            self.argv: list[list[str]] = []

        async def _run(self, argv, *, cancel, timeout_seconds):
            self.argv.append(list(argv))
            return TransportResult(0, "soft reboot")

    transport = CapturingTransport()
    result = await transport.hard_reset(
        TransportSession("synthetic-session", port),
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert result.exit_code == 0
    assert transport.argv[0][-1] == "reset"
    assert "soft-reset" not in transport.argv[0]


@pytest.mark.asyncio
async def test_real_adapter_uses_resume_for_management_and_soft_reset_to_start_main() -> None:
    port = DevicePort(
        id="opaque-test-port",
        label="Synthetic serial port",
        portName="opaque-test-port",
        chip="ESP32-S3",
        serialNumber=None,
    )

    class CapturingTransport(SubprocessDeviceTransport):
        def __init__(self) -> None:
            super().__init__(scanner=lambda: [port])
            self.argv: list[list[str]] = []

        async def _run(self, argv, *, cancel, timeout_seconds):
            self.argv.append(list(argv))
            if "__ZW_IDENTITY_V1__" in argv[-1]:
                return TransportResult(
                    0,
                    "\n".join(
                        [
                            "__ZW_IDENTITY_V1__",
                            "implementation=micropython",
                            "platform=esp32",
                            "machine=ESP32-S3",
                            "firmware=test",
                            "__ZW_IDENTITY_END__",
                        ]
                    ),
                )
            return TransportResult(0, "ok")

    transport = CapturingTransport()
    session = TransportSession("synthetic-session", port)
    _identity, probe = await transport.probe_identity(
        session,
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    started = await transport.start_runtime(
        session,
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert probe.exit_code == 0
    assert started.exit_code == 0
    assert transport.argv[0][5:7] == ["resume", "exec"]
    assert transport.argv[1][5:] == [
        "soft-reset",
        "exec",
        "--no-follow",
        "import main",
    ]
    assert all(argv[-1] != "reset" for argv in transport.argv)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "management_prompt",
    [b"KeyboardInterrupt\r\n>>> ", b"raw REPL; CTRL-B to exit\r\n>"],
)
async def test_runtime_interrupt_writes_only_bounded_ctrl_c_and_never_resets(
    monkeypatch,
    management_prompt: bytes,
) -> None:
    port = DevicePort(
        id="opaque-test-port",
        label="Synthetic serial port",
        portName="opaque-test-port",
        chip="ESP32-S3",
        serialNumber=None,
    )

    class FakeInput:
        def __init__(self) -> None:
            self.writes: list[bytes] = []

        def write(self, value: bytes) -> None:
            self.writes.append(value)

        async def drain(self) -> None:
            return None

    class FakeOutput:
        async def read(self, _size: int) -> bytes:
            return management_prompt

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = FakeInput()
            self.stdout = FakeOutput()
            self.returncode: int | None = None
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            return self.returncode or 0

    process = FakeProcess()
    captured_argv: list[str] = []

    async def fake_subprocess(*argv, **_kwargs):
        captured_argv.extend(str(item) for item in argv)
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)
    result = await SubprocessDeviceTransport(scanner=lambda: [port]).interrupt_runtime(
        TransportSession("synthetic-session", port),
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )

    assert result.exit_code == 0
    assert captured_argv[-4:] == ["connect", "opaque-test-port", "resume", "repl"]
    assert process.stdin.writes == [b"\x03\x03"]
    assert process.terminated is True
    assert "reset" not in captured_argv


@pytest.mark.asyncio
async def test_runtime_interrupt_timeout_terminates_helper_process(monkeypatch) -> None:
    port = DevicePort(
        id="opaque-test-port",
        label="Synthetic serial port",
        portName="opaque-test-port",
        chip="ESP32-S3",
        serialNumber=None,
    )

    class FakeInput:
        def write(self, _value: bytes) -> None:
            return None

        async def drain(self) -> None:
            return None

    class WaitingOutput:
        async def read(self, _size: int) -> bytes:
            await asyncio.Event().wait()
            return b""

    class FakeProcess:
        def __init__(self) -> None:
            self.stdin = FakeInput()
            self.stdout = WaitingOutput()
            self.returncode: int | None = None
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = 0

        def kill(self) -> None:
            self.returncode = -9

        async def wait(self) -> int:
            return self.returncode or 0

    process = FakeProcess()

    async def fake_subprocess(*_argv, **_kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_subprocess)
    with pytest.raises(DeviceTransportTimedOut):
        await SubprocessDeviceTransport(scanner=lambda: [port]).interrupt_runtime(
            TransportSession("synthetic-session", port),
            cancel=asyncio.Event(),
            timeout_seconds=0.01,
        )

    assert process.terminated is True


@pytest.mark.asyncio
async def test_real_image_info_parser_accepts_only_labeled_esp32_s3_metadata(
    tmp_path: Path,
) -> None:
    class ImageInfoTransport(SubprocessDeviceTransport):
        def __init__(self, output: str) -> None:
            super().__init__(scanner=lambda: [])
            self.output = output

        async def _run(self, argv, *, cancel, timeout_seconds):
            return TransportResult(0, self.output)

    firmware = tmp_path / "firmware.bin"
    firmware.write_bytes(b"\xe9image-info")
    accepted = await ImageInfoTransport(
        "esptool image info\nDetected image type: ESP32-S3\n"
    ).inspect_firmware(
        firmware,
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    assert accepted.data["targetChip"] == "ESP32-S3"
    assert accepted.data["defaultAddress"] is None

    rejected = await ImageInfoTransport(
        "unlabeled text mentioning ESP32-S3"
    ).inspect_firmware(
        firmware,
        cancel=asyncio.Event(),
        timeout_seconds=1,
    )
    assert "targetChip" not in rejected.data


def test_router_firmware_flow_uses_mock_and_requires_confirmation_phrase(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    transport = MockDeviceTransport()
    devices_router.configure_device_transport(transport)
    with TestClient(app) as client:
        project_id = _create_project(client)
        connected = client.post(
            f"/api/projects/{project_id}/devices/connect",
            headers=DESKTOP_HEADERS,
            json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
        )
        assert connected.status_code == 200
        session_id = connected.json()["session"]["id"]
        inspected = client.post(
            f"/api/projects/{project_id}/devices/firmware/inspect",
            headers=DESKTOP_HEADERS,
            json={
                "fileName": "firmware.bin",
                "contentBase64": base64.b64encode(b"\xe9router-firmware").decode("ascii"),
            },
        )
        assert inspected.status_code == 200
        candidate = inspected.json()["candidate"]
        prepared = client.post(
            f"/api/projects/{project_id}/devices/firmware/prepare",
            headers=DESKTOP_HEADERS,
            json={"sessionId": session_id, "candidateId": candidate["id"], "address": 0},
        )
        assert prepared.status_code == 200
        plan = prepared.json()["plan"]
        missing_phrase = client.post(
            f"/api/projects/{project_id}/devices/flash",
            headers=DESKTOP_HEADERS,
            json={
                "sessionId": session_id,
                "dryRun": False,
                "confirmFlash": True,
                "candidateId": candidate["id"],
                "confirmationToken": plan["confirmationToken"],
                "operationId": "firmware_operation_api_001",
                "address": 0,
            },
        )
        assert missing_phrase.status_code == 422
        assert (
            missing_phrase.json()["detail"]["code"]
            == "DEVICE_FLASH_CONFIRMATION_PHRASE_REQUIRED"
        )
        started = client.post(
            f"/api/projects/{project_id}/devices/flash",
            headers=DESKTOP_HEADERS,
            json={
                "sessionId": session_id,
                "dryRun": False,
                "confirmFlash": True,
                "candidateId": candidate["id"],
                "confirmationToken": plan["confirmationToken"],
                "operationId": "firmware_operation_api_001",
                "address": 0,
                "confirmationPhrase": FIRMWARE_CONFIRMATION_PHRASE,
            },
        )
        assert started.status_code == 200
        operation_id = started.json()["operation"]["id"]
        terminal = started.json()["operation"]
        for _ in range(100):
            polled = client.get(
                f"/api/projects/{project_id}/devices/operations/{operation_id}"
            )
            assert polled.status_code == 200
            terminal = polled.json()["operation"]
            if terminal["status"] not in {"QUEUED", "RUNNING"}:
                break
            time.sleep(0.01)
        assert terminal["status"] == "COMPLETED"
        assert terminal["artifactId"] == f"artifact_device_log_{project_id}"


def test_latest_operation_route_returns_404_then_most_recent_response(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    devices_router.configure_device_transport(MockDeviceTransport())
    with TestClient(app) as client:
        project_id = _create_project(client)
        missing = client.get(f"/api/projects/{project_id}/devices/operations/latest")
        assert missing.status_code == 404
        assert missing.json()["detail"] == {
            "code": "DEVICE_OPERATION_NOT_FOUND",
            "message": "当前项目还没有设备操作记录。",
            "retryable": False,
        }

        connected = client.post(
            f"/api/projects/{project_id}/devices/connect",
            headers=DESKTOP_HEADERS,
            json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
        )
        assert connected.status_code == 200
        session_id = connected.json()["session"]["id"]
        created, _ = DeviceRepository(ProjectRepository(tmp_path).db_path).firmware_flash_dry_run(
            project_id=project_id,
            session_id=session_id,
        )

        latest = client.get(f"/api/projects/{project_id}/devices/operations/latest")
        assert latest.status_code == 200
        assert latest.json()["operation"]["id"] == created.id
        assert latest.json()["session"]["id"] == session_id


def test_router_reuses_default_transport_service_between_requests(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    devices_router.configure_device_transport(None)
    repository = ProjectRepository(tmp_path)
    first = devices_router._service(repository)
    second = devices_router._service(repository)
    assert first is second


def _persisted_operation_state(
    *,
    fingerprint: str,
    steps: list[dict[str, object]],
    phase: DeviceOperationPhase,
) -> dict[str, object]:
    return {
        "schema": "device-operation/v1",
        "kind": DeviceOperationKind.UPLOAD_CODE.value,
        "status": DeviceOperationStatus.RUNNING.value,
        "phase": phase.value,
        "progress": 50,
        "errorCode": None,
        "log": "设备操作进行中。",
        "steps": steps,
        "backup": None,
        "verification": None,
        "cancelable": True,
        "metadata": {"fingerprint": fingerprint},
    }


def _persisted_step(phase: DeviceOperationPhase, exit_code: int | None) -> dict[str, object]:
    return {
        "phase": phase.value,
        "status": (
            DeviceOperationStatus.COMPLETED.value
            if exit_code == 0
            else DeviceOperationStatus.FAILED.value
        ),
        "exitCode": exit_code,
        "summary": f"synthetic {phase.value}",
        "startedAt": None,
        "completedAt": None,
    }


def _service(
    tmp_path: Path,
    transport: MockDeviceTransport,
    monkeypatch,
    *,
    upload_timeout_seconds: float = 2.0,
) -> tuple[DeviceOperationService, str, CodeRun]:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="Synthetic device service test",
        project_name="设备测试项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    solution_repository = SolutionRepository(repository.db_path)
    solution = solution_repository.create_solution(
        workspace.project.id,
        [
            SolutionSection(
                id="recommended_implementation",
                title="Recommended implementation",
                content="Use DFRobot K10 as the only controller.",
            )
        ],
    )
    solution = solution_repository.confirm_solution(workspace.project.id, solution.id)
    proposal_repository = ProposalRepository(repository.db_path)
    proposal = proposal_repository.create_proposal(
        project_id=workspace.project.id,
        solution=solution,
        sections=[
            ProposalSection(
                id=section_id,
                title=section_id.replace("_", " ").title(),
                content="The confirmed project uses DFRobot K10 as its only controller.",
            )
            for section_id in (
                "project_overview",
                "requirements",
                "hardware_software_structure",
                "implementation_plan",
                "cost_difficulty_schedule",
                "risks_acceptance",
            )
        ],
        supersede_drafts=True,
    )
    proposal_repository.confirm_proposal(workspace.project.id, proposal.id)
    code_run = _accepted_code(workspace.project.id)

    class FakeCodeRepository:
        def __init__(self, _db_path: Path) -> None:
            pass

        def get_current_code(self, project_id: str) -> CodeRun | None:
            return code_run if project_id == code_run.projectId else None

    monkeypatch.setattr("zhangwen.devices.service.CodeRepository", FakeCodeRepository)
    service = DeviceOperationService(
        repository.db_path,
        tmp_path,
        transport,
        command_timeout_seconds=1,
        upload_timeout_seconds=upload_timeout_seconds,
        flash_timeout_seconds=2,
    )
    return service, workspace.project.id, code_run


def _accepted_code(project_id: str) -> CodeRun:
    now = datetime.now(UTC).isoformat()
    code_run_id = "code_accepted_device_test"
    return CodeRun(
        id=code_run_id,
        projectId=project_id,
        specRunId="spec_device_test",
        version=1,
        status=CodeRunStatus.ACCEPTED,
        workspaceRoot=f"workspace://{project_id}/code/v1",
        maxRetries=0,
        retries=0,
        files=[
            CodeFile(
                id="code_file_main_device_test",
                codeRunId=code_run_id,
                projectId=project_id,
                kind=CodeFileKind.MAIN,
                path="src/main.py",
                language="python",
                content="print('new-main')\n",
                createdAt=now,
            ),
            CodeFile(
                id="code_file_readme_device_test",
                codeRunId=code_run_id,
                projectId=project_id,
                kind=CodeFileKind.README,
                path="README.md",
                language="markdown",
                content="# Not uploaded\n",
                createdAt=now,
            ),
        ],
        patch=CodePatch(
            id="patch_device_test",
            codeRunId=code_run_id,
            projectId=project_id,
            summary="Synthetic accepted code",
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


def _main_content(code_run: CodeRun) -> bytes:
    return next(file.content.encode("utf-8") for file in code_run.files if file.path == "src/main.py")


def _add_upload_file(
    code_run: CodeRun,
    path: str,
    content: str,
    kind: CodeFileKind,
) -> None:
    code_run.files.append(
        CodeFile(
            id=f"code_file_{path.replace('/', '_')}",
            codeRunId=code_run.id,
            projectId=code_run.projectId,
            kind=kind,
            path=path,
            language="python",
            content=content,
            createdAt=code_run.createdAt,
        )
    )


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "设备路由测试", "initialIdea": "测试固件流程"},
    )
    assert response.status_code == 200
    project_id = str(response.json()["workspace"]["project"]["id"])
    repository = ProjectRepository(settings.data_dir)
    solutions = SolutionRepository(repository.db_path)
    solution = solutions.create_solution(
        project_id,
        [
            SolutionSection(
                id="recommended_implementation",
                title="Recommended implementation",
                content="Use DFRobot K10 as the only controller.",
            )
        ],
    )
    solution = solutions.confirm_solution(project_id, solution.id)
    proposals = ProposalRepository(repository.db_path)
    proposal = proposals.create_proposal(
        project_id=project_id,
        solution=solution,
        sections=[
            ProposalSection(
                id=section_id,
                title=section_id.replace("_", " ").title(),
                content="The confirmed project uses DFRobot K10 as its only controller.",
            )
            for section_id in (
                "project_overview",
                "requirements",
                "hardware_software_structure",
                "implementation_plan",
                "cost_difficulty_schedule",
                "risks_acceptance",
            )
        ],
        supersede_drafts=True,
    )
    proposals.confirm_proposal(project_id, proposal.id)
    return project_id
