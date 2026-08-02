from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.devices import router as devices_router
from zhangwen.devices.transport import MockDeviceTransport
from zhangwen.main import app
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalSection
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository


ORIGIN = "http://localhost:5173"
DESKTOP = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "bridge-desktop-token",
}


def test_bridge_pairing_origin_scope_replay_expiry_and_revoke(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv(
        "ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "bridge-desktop-token"
    )
    devices_router.configure_device_transport(MockDeviceTransport())
    repository = ProjectRepository(tmp_path)
    project = repository.create_project_from_idea(
        idea="Bridge project",
        project_name="Bridge 项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    ).project
    _confirm_k10_project(repository.db_path, project.id)
    other = repository.create_project_from_idea(
        idea="Other project",
        project_name="其他项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    ).project
    client = TestClient(app, client=("127.0.0.1", 43000))

    status = client.get("/api/local-bridge/status")
    assert status.status_code == 200
    assert status.json()["loopbackOnly"] is True

    pairing = _start_pairing(client, project.id)
    wrong_origin = client.post(
        "/api/local-bridge/pairing/claim",
        headers={"Origin": "http://127.0.0.1:5173", "X-Zhangwen-Host": "web"},
        json={"pairingId": pairing["pairingId"], "code": pairing["code"]},
    )
    assert wrong_origin.status_code == 403
    assert wrong_origin.json()["detail"]["code"] == "BRIDGE_ORIGIN_MISMATCH"

    claim = client.post(
        "/api/local-bridge/pairing/claim",
        headers={"Origin": ORIGIN, "X-Zhangwen-Host": "web"},
        json={"pairingId": pairing["pairingId"], "code": pairing["code"]},
    )
    assert claim.status_code == 200
    lease_token = claim.json()["leaseToken"]
    assert claim.json()["lease"]["projectId"] == project.id

    replay_claim = client.post(
        "/api/local-bridge/pairing/claim",
        headers={"Origin": ORIGIN, "X-Zhangwen-Host": "web"},
        json={"pairingId": pairing["pairingId"], "code": pairing["code"]},
    )
    assert replay_claim.status_code == 409
    assert replay_claim.json()["detail"]["code"] == "BRIDGE_PAIRING_ALREADY_CLAIMED"

    bridge_headers = _bridge_headers(lease_token)
    scan = client.get(
        f"/api/projects/{project.id}/devices/ports", headers=bridge_headers
    )
    assert scan.status_code == 200
    assert scan.json()["count"] >= 1

    wrong_project = client.get(
        f"/api/projects/{other.id}/devices/ports", headers=bridge_headers
    )
    assert wrong_project.status_code == 403
    assert wrong_project.json()["detail"]["code"] == "BRIDGE_PROJECT_SCOPE_MISMATCH"

    write_headers = {
        **bridge_headers,
        "X-Zhangwen-Bridge-Request-Id": "bridge-request-replay-0001",
    }
    connect = client.post(
        f"/api/projects/{project.id}/devices/connect",
        headers=write_headers,
        json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
    )
    assert connect.status_code == 200
    replay_write = client.post(
        f"/api/projects/{project.id}/devices/connect",
        headers=write_headers,
        json={"portId": "mock_port_esp32_s3", "boardId": "dfrobot/dfrobot_k10", "confirmBoardIdentity": True},
    )
    assert replay_write.status_code == 409
    assert replay_write.json()["detail"]["code"] == "BRIDGE_REQUEST_REPLAYED"

    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE local_bridge_sessions SET expires_at = ? WHERE id = ?",
            (
                (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                pairing["pairingId"],
            ),
        )
    expired = client.get(
        f"/api/projects/{project.id}/devices/ports", headers=bridge_headers
    )
    assert expired.status_code == 403
    assert expired.json()["detail"]["code"] == "BRIDGE_LEASE_EXPIRED"

    fresh_pairing = _start_pairing(client, project.id)
    fresh_claim = client.post(
        "/api/local-bridge/pairing/claim",
        headers={"Origin": ORIGIN, "X-Zhangwen-Host": "web"},
        json={
            "pairingId": fresh_pairing["pairingId"],
            "code": fresh_pairing["code"],
        },
    ).json()
    fresh_headers = {
        **_bridge_headers(fresh_claim["leaseToken"]),
        "X-Zhangwen-Bridge-Request-Id": "bridge-request-revoke-0001",
    }
    revoked = client.post("/api/local-bridge/revoke", headers=fresh_headers, json={})
    assert revoked.status_code == 200
    after_revoke = client.get(
        f"/api/projects/{project.id}/devices/ports",
        headers=_bridge_headers(fresh_claim["leaseToken"]),
    )
    assert after_revoke.status_code == 403
    assert after_revoke.json()["detail"]["code"] == "BRIDGE_LEASE_REVOKED"

    devices_router.configure_device_transport(None)


def test_bridge_rejects_remote_clients_bad_origins_and_excess_capabilities(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setenv(
        "ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "bridge-desktop-token"
    )
    project = ProjectRepository(tmp_path).create_project_from_idea(
        idea="Bridge negative cases",
        project_name="Bridge 安全边界",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    ).project
    remote = TestClient(app, client=("192.0.2.20", 43000))
    assert remote.get("/api/local-bridge/status").status_code == 403

    client = TestClient(app, client=("127.0.0.1", 43000))
    denied_origin = client.post(
        "/api/local-bridge/pairing/start",
        headers=DESKTOP,
        json={
            "origin": "https://evil.example",
            "projectId": project.id,
            "capabilities": ["cad.local"],
        },
    )
    assert denied_origin.status_code == 403
    assert denied_origin.json()["detail"]["code"] == "BRIDGE_ORIGIN_DENIED"

    shell = client.post(
        "/api/local-bridge/pairing/start",
        headers=DESKTOP,
        json={
            "origin": ORIGIN,
            "projectId": project.id,
            "capabilities": ["shell", "cad.local"],
        },
    )
    assert shell.status_code == 422
    assert shell.json()["detail"]["code"] == "BRIDGE_CAPABILITY_INVALID"


def _start_pairing(client: TestClient, project_id: str) -> dict[str, object]:
    response = client.post(
        "/api/local-bridge/pairing/start",
        headers=DESKTOP,
        json={
            "origin": ORIGIN,
            "projectId": project_id,
            "capabilities": ["cad.local", "device.serial", "device.upload"],
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def _bridge_headers(token: str) -> dict[str, str]:
    return {
        "Origin": ORIGIN,
        "X-Zhangwen-Host": "web",
        "X-Zhangwen-Bridge-Lease": token,
    }


def _confirm_k10_project(db_path: Path, project_id: str) -> None:
    solutions = SolutionRepository(db_path)
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
    proposals = ProposalRepository(db_path)
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
