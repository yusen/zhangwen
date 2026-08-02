"""Tests for ZW-012 device management and MicroPython deployment dry runs."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.artifacts.models import ArtifactKind
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.code_agent.chat_code import ChatCodeService
from zhangwen.code_agent.models import ChatCodeDraft, CodeRunStatus
from zhangwen.config import settings
from zhangwen.devices import router as devices_router
from zhangwen.devices.models import (
    DeviceOperationStatus,
    DevicePort,
    DeviceSessionStatus,
    DeviceTerminalStatus,
)
from zhangwen.devices.serial_discovery import SerialDiscoveryError
from zhangwen.devices.transport import MockDeviceTransport
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalSection
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository


DESKTOP_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "test-token",
}


@pytest.fixture(autouse=True)
def desktop_capability(monkeypatch):
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "test-token")
    devices_router.configure_device_transport(None)
    yield
    devices_router.configure_device_transport(None)


def test_v10_migration_creates_device_tables(tmp_path: Path) -> None:
    db_file = tmp_path / "test.sqlite3"
    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    migrate(conn)
    tables = {
        row[0]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    conn.close()

    assert CURRENT_SCHEMA_VERSION == 31
    assert version == CURRENT_SCHEMA_VERSION
    assert {"device_sessions", "device_operations"}.issubset(tables)


def test_list_ports_and_connect_mock_session(tmp_path: Path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(
        devices_router,
        "list_serial_ports",
        lambda: [
            DevicePort(
                id="COM3",
                label="USB Serial Device",
                transport="usb-serial",
                portName="COM3",
                portType="usb",
                description="USB Serial Device",
                manufacturer="Espressif",
                product="ESP32-S3",
                vid=0x303A,
                pid=0x1001,
                serialNumber="TEST123",
                likelyBoard="ESP32",
                chip="ESP32",
                status="available",
                available=True,
            ),
            DevicePort(
                id="COM9",
                label="COM9",
                transport="system-serial",
                portName="COM9",
                portType="unknown",
                chip="Unknown",
                serialNumber=None,
                status="unknown",
                available=True,
            ),
        ],
    )
    client = TestClient(app)
    project_id = _create_project(client)

    ports_response = client.get(
        f"/api/projects/{project_id}/devices/ports",
        headers=DESKTOP_HEADERS,
    )
    assert ports_response.status_code == 200
    body = ports_response.json()
    ports = body["ports"]
    assert body["count"] == 2
    assert body["scannedAt"]
    assert ports[0]["portName"] == "COM3"
    assert ports[0]["vid"] == 0x303A
    assert ports[0]["pid"] == 0x1001
    assert ports[0]["likelyBoard"] == "ESP32"
    assert ports[1]["manufacturer"] is None

    session_response = client.post(
        f"/api/projects/{project_id}/devices/connect",
        json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
        headers=DESKTOP_HEADERS,
    )
    assert session_response.status_code == 200
    session = session_response.json()["session"]
    assert session["status"] == DeviceSessionStatus.READY.value
    assert session["portId"] == "mock_port_esp32_s3"
    assert "真实串口" in session["logs"][1]["message"]

    current = client.get(f"/api/projects/{project_id}/devices/session/current")
    assert current.status_code == 200
    assert current.json()["session"]["id"] == session["id"]


def test_read_only_terminal_api_returns_runtime_errors_and_controls_session(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    port_id = "mock_port_esp32_s3"
    devices_router.configure_device_transport(
        MockDeviceTransport(
            terminal_chunks={
                port_id: [
                    "SyntaxError: invalid syntax\n",
                    "NameError: name 'missing_pin' isn't defined\n",
                    "loop started\n",
                ]
            }
        )
    )
    with TestClient(app) as client:
        project_id = _create_project(client)
        connection = client.post(
            f"/api/projects/{project_id}/devices/connect",
            json={"portId": port_id, "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
            headers=DESKTOP_HEADERS,
        )
        assert connection.status_code == 200
        session_id = connection.json()["session"]["id"]

        blocked_web = client.get(
            f"/api/projects/{project_id}/devices/terminal?sessionId={session_id}",
        )
        assert blocked_web.status_code == 409

        started = client.post(
            f"/api/projects/{project_id}/devices/terminal/start",
            json={"sessionId": session_id},
            headers=DESKTOP_HEADERS,
        )
        assert started.status_code == 200
        assert started.json()["terminal"]["status"] in {
            DeviceTerminalStatus.STARTING.value,
            DeviceTerminalStatus.RUNNING.value,
        }

        terminal: dict[str, object] = {}
        for _ in range(20):
            response = client.get(
                f"/api/projects/{project_id}/devices/terminal?sessionId={session_id}",
                headers=DESKTOP_HEADERS,
            )
            assert response.status_code == 200
            terminal = response.json()["terminal"]
            if "loop started" in str(terminal["output"]):
                break
            time.sleep(0.01)
        assert terminal["status"] == DeviceTerminalStatus.RUNNING.value
        assert "SyntaxError: invalid syntax" in str(terminal["output"])
        assert "NameError: name 'missing_pin' isn't defined" in str(terminal["output"])

        cleared = client.post(
            f"/api/projects/{project_id}/devices/terminal/clear",
            json={"sessionId": session_id},
            headers=DESKTOP_HEADERS,
        )
        assert cleared.status_code == 200
        assert cleared.json()["terminal"]["output"] == ""

        stopped = client.post(
            f"/api/projects/{project_id}/devices/terminal/stop",
            json={"sessionId": session_id},
            headers=DESKTOP_HEADERS,
        )
        assert stopped.status_code == 200
        assert stopped.json()["terminal"]["status"] == DeviceTerminalStatus.STOPPED.value


def test_list_ports_returns_empty_scan(tmp_path: Path, monkeypatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setattr(devices_router, "list_serial_ports", lambda: [])
    client = TestClient(app)
    project_id = _create_project(client)

    response = client.get(
        f"/api/projects/{project_id}/devices/ports",
        headers=DESKTOP_HEADERS,
    )

    assert response.status_code == 200
    assert response.json()["ports"] == []
    assert response.json()["count"] == 0


def test_list_ports_reports_serial_scan_error(tmp_path: Path, monkeypatch) -> None:
    settings.data_dir = tmp_path

    def fail_scan():
        raise SerialDiscoveryError(
            "SERIAL_SYSTEM_API_FAILED",
            "system failed",
            500,
        )

    monkeypatch.setattr(devices_router, "list_serial_ports", fail_scan)
    client = TestClient(app)
    project_id = _create_project(client)

    response = client.get(
        f"/api/projects/{project_id}/devices/ports",
        headers=DESKTOP_HEADERS,
    )

    assert response.status_code == 500
    assert response.json()["detail"]["code"] == "SERIAL_SYSTEM_API_FAILED"


def test_upload_requires_accepted_code_and_blocks_real_upload(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, code_run_id = _project_with_code(client, tmp_path, accepted=False)
    session_id = _connect(client, project_id)

    rejected = client.post(
        f"/api/projects/{project_id}/devices/upload",
        json={"codeRunId": code_run_id, "sessionId": session_id, "dryRun": True},
        headers=DESKTOP_HEADERS,
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "DEVICE_REQUIRES_ACCEPTED_CODE"

    accepted = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": code_run_id},
    )
    assert accepted.status_code == 200
    assert accepted.json()["codeRun"]["status"] == CodeRunStatus.ACCEPTED.value

    real_upload = client.post(
        f"/api/projects/{project_id}/devices/upload",
        json={"codeRunId": code_run_id, "sessionId": session_id, "dryRun": False},
        headers=DESKTOP_HEADERS,
    )
    assert real_upload.status_code == 422
    assert real_upload.json()["detail"]["code"] == "DEVICE_UPLOAD_CONFIRMATION_REQUIRED"


def test_upload_dry_run_creates_device_log_artifact(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, code_run_id = _project_with_code(client, tmp_path, accepted=True)
    session_id = _connect(client, project_id)

    response = client.post(
        f"/api/projects/{project_id}/devices/upload",
        json={"codeRunId": code_run_id, "sessionId": session_id, "dryRun": True},
        headers=DESKTOP_HEADERS,
    )

    assert response.status_code == 200
    payload = response.json()
    operation = payload["operation"]
    assert operation["status"] == DeviceOperationStatus.DRY_RUN_COMPLETE.value
    assert operation["dryRun"] is True
    assert operation["commandLabel"] == "mpremote"
    assert "真实命令：未执行" in operation["log"]
    assert operation["artifactId"] == f"artifact_device_log_{project_id}"
    assert payload["session"]["status"] == DeviceSessionStatus.READY.value

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(project_id)
    device_log = next(artifact for artifact in artifacts if artifact.kind == ArtifactKind.DEVICE_LOG)
    assert device_log.sourceAgentId == "deploy-agent"
    assert "Dry Run" in device_log.versions[0].preview.code
    assert "sk-" not in device_log.versions[0].preview.code


def test_firmware_flash_requires_confirmation_and_blocks_real_flash(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id = _create_project(client)
    session_id = _connect(client, project_id)

    missing_confirmation = client.post(
        f"/api/projects/{project_id}/devices/flash",
        json={"sessionId": session_id, "dryRun": True, "confirmFlash": False},
        headers=DESKTOP_HEADERS,
    )
    assert missing_confirmation.status_code == 422
    assert missing_confirmation.json()["detail"]["code"] == "DEVICE_FLASH_CONFIRMATION_REQUIRED"

    real_flash = client.post(
        f"/api/projects/{project_id}/devices/flash",
        json={"sessionId": session_id, "dryRun": False, "confirmFlash": True},
        headers=DESKTOP_HEADERS,
    )
    assert real_flash.status_code == 422
    assert real_flash.json()["detail"]["code"] == "DEVICE_FLASH_CONFIRMATION_REQUIRED"

    dry_run = client.post(
        f"/api/projects/{project_id}/devices/flash",
        json={"sessionId": session_id, "dryRun": True, "confirmFlash": True},
        headers=DESKTOP_HEADERS,
    )
    assert dry_run.status_code == 200
    operation = dry_run.json()["operation"]
    assert operation["commandLabel"] == "esptool"
    assert operation["status"] == DeviceOperationStatus.DRY_RUN_COMPLETE.value
    assert "未擦除 Flash" in operation["log"]


def _project_with_code(
    client: TestClient,
    tmp_path: Path,
    *,
    accepted: bool,
) -> tuple[str, str]:
    project_id = _create_project(client)
    code_run = ChatCodeService(ProjectRepository(tmp_path).db_path).materialize(
        project_id=project_id,
        source_message_id="message_device_upload_fixture",
        generated_by_expert_id=None,
        draft=ChatCodeDraft(
            summary="设备上传测试代码",
            files=[
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "print('device upload fixture')\n",
                }
            ],
        ),
    )
    validation_response = client.post(
        f"/api/projects/{project_id}/code/validate",
        json={"codeRunId": code_run.id},
    )
    assert validation_response.status_code == 200, validation_response.json()
    generated = validation_response.json()["codeRun"]
    assert generated["status"] == CodeRunStatus.READY_FOR_REVIEW.value
    if accepted:
        accept_response = client.post(
            f"/api/projects/{project_id}/code/accept",
            json={"codeRunId": generated["id"]},
        )
        assert accept_response.status_code == 200, accept_response.json()
        generated = accept_response.json()["codeRun"]
        assert generated["status"] == CodeRunStatus.ACCEPTED.value
    return project_id, str(generated["id"])


def _connect(client: TestClient, project_id: str) -> str:
    response = client.post(
        f"/api/projects/{project_id}/devices/connect",
        json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
        headers=DESKTOP_HEADERS,
    )
    assert response.status_code == 200
    return str(response.json()["session"]["id"])


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "测试项目", "initialIdea": "测试创意"},
    )
    assert response.status_code == 200, response.json()
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
