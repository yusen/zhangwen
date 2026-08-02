"""Read-only serial terminal tests; no host serial API is used."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from zhangwen.devices.models import (
    DevicePort,
    DeviceSession,
    DeviceSessionStatus,
    DeviceTerminalStatus,
    SerialPortStatus,
    SerialPortType,
)
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.devices.service import DeviceOperationService, MAX_TERMINAL_OUTPUT_CHARS
from zhangwen.devices.transport import MockDeviceTransport


@pytest.mark.asyncio
async def test_terminal_streams_errors_is_bounded_and_can_stop_and_clear(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id = "project_terminal_test"
    port = DevicePort(
        id="mock_port_terminal",
        label="Mock MicroPython board",
        transport="mock-usb-serial",
        portName="mock-terminal",
        portType=SerialPortType.USB,
        status=SerialPortStatus.AVAILABLE,
        chip="ESP32-S3",
    )
    session = DeviceSession(
        id="session_terminal_test",
        projectId=project_id,
        portId=port.id,
        board=SupportedDeviceBoardId.DFROBOT_K10.value,
        status=DeviceSessionStatus.READY,
        connectedAt="2026-07-19T00:00:00+00:00",
        lastSeenAt="2026-07-19T00:00:00+00:00",
        logs=[],
    )

    class FakeDeviceRepository:
        def __init__(self, _db_path: Path) -> None:
            pass

        def get_session(self, requested_project_id: str, requested_session_id: str) -> DeviceSession:
            if requested_project_id != project_id or requested_session_id != session.id:
                raise ValueError("session not found")
            return session.model_copy(deep=True)

        def get_serial_session(
            self,
            requested_project_id: str,
            requested_session_id: str,
        ) -> DeviceSession:
            return self.get_session(requested_project_id, requested_session_id)

        def has_active_espclaw_operation(self, requested_project_id: str) -> bool:
            assert requested_project_id == project_id
            return False

    class FakeDeviceLabService:
        def __init__(self, _db_path: Path, _data_dir: Path) -> None:
            pass

        def get_scene(self, requested_project_id: str):
            assert requested_project_id == project_id

            class Scene:
                boardId = SupportedDeviceBoardId.DFROBOT_K10

            return Scene()

    monkeypatch.setattr(
        "zhangwen.devices.service.DeviceRepository",
        FakeDeviceRepository,
    )
    monkeypatch.setattr(
        "zhangwen.devices.service.DeviceLabService",
        FakeDeviceLabService,
    )
    transport = MockDeviceTransport(
        ports=[port],
        terminal_chunks={
            port.id: [
                "x" * (MAX_TERMINAL_OUTPUT_CHARS + 128),
                "SyntaxError: invalid syntax\n",
                "NameError: name 'missing_pin' isn't defined\n",
                "loop started\n",
            ]
        },
    )
    service = DeviceOperationService(tmp_path / "unused.db", tmp_path, transport)

    started = await service.start_terminal(project_id, session.id)
    assert started.status in {
        DeviceTerminalStatus.STARTING,
        DeviceTerminalStatus.RUNNING,
    }
    for _ in range(20):
        snapshot = service.get_terminal(project_id, session.id)
        if snapshot.output.endswith("loop started\n"):
            break
        await asyncio.sleep(0.01)

    snapshot = service.get_terminal(project_id, session.id)
    assert snapshot.status == DeviceTerminalStatus.RUNNING
    assert len(snapshot.output) == MAX_TERMINAL_OUTPUT_CHARS
    assert "SyntaxError: invalid syntax" in snapshot.output
    assert "NameError: name 'missing_pin' isn't defined" in snapshot.output
    assert snapshot.output.endswith("loop started\n")
    assert snapshot.revision > 0

    stopped = await service.stop_terminal(project_id, session.id)
    assert stopped.status == DeviceTerminalStatus.STOPPED
    assert sum(name == "terminal" for name, _ in transport.calls) == 1

    cleared = service.clear_terminal(project_id, session.id)
    assert cleared.output == ""
    assert cleared.status == DeviceTerminalStatus.STOPPED
