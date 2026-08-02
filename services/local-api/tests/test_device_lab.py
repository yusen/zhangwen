"""ZW-DEVICE-LAB-001 two-board contracts, validation and functional simulation."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import sqlite3
import time
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.cad_agent.profile_repository import (
    MechanicalProfileRepository,
    seed_builtin_mechanical_profiles,
)
from zhangwen.device_lab.boards import normalize_board_id
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.devices import router as devices_router
from zhangwen.devices.transport import MockDeviceTransport
from zhangwen.main import app
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.models import ProposalSection
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository


DESKTOP_HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "device-lab-test-token",
}


@pytest.fixture(autouse=True)
def device_lab_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "device-lab-test-token")
    devices_router.configure_device_transport(None)
    yield
    devices_router.configure_device_transport(None)


def test_v30_migration_preserves_device_lab_tables_and_constraints(tmp_path: Path) -> None:
    conn = sqlite3.connect(tmp_path / "device-lab.sqlite3")
    migrate(conn)
    tables = {
        str(row[0])
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    version = int(conn.execute("PRAGMA user_version").fetchone()[0])
    conn.close()

    assert CURRENT_SCHEMA_VERSION == 31
    assert version == 31
    assert {
        "firmware_applications",
        "device_parameter_sets",
        "device_lab_runs",
        "device_lab_events",
        "device_lab_scenes",
    }.issubset(tables)


def test_board_registry_exposes_only_two_canonical_boards() -> None:
    client = TestClient(app)
    response = client.get("/api/device-lab/boards")
    assert response.status_code == 200
    body = response.json()
    assert {item["id"] for item in body["boards"]} == {
        "dfrobot/dfrobot_k10",
        "seeedstudio/xiao_esp32s3_sense",
    }
    assert {item["boardId"] for item in body["profiles"]} == {
        "dfrobot/dfrobot_k10",
        "seeedstudio/xiao_esp32s3_sense",
    }
    assert normalize_board_id("unihiker-k10") == SupportedDeviceBoardId.DFROBOT_K10
    with pytest.raises(ValueError):
        normalize_board_id("esp32-s3-devkitc")


def test_physical_scene_requires_approved_proposal_and_never_defaults_board() -> None:
    client = TestClient(app)
    created = client.post(
        "/api/projects",
        json={
            "name": "尚未立项",
            "initialIdea": "使用 K10 制作传感器项目",
            "selectedHardwareIds": ["hw_seed_unihiker_k10"],
        },
    )
    project_id = created.json()["workspace"]["project"]["id"]

    scene = client.get(f"/api/projects/{project_id}/device-lab/scene")
    assert scene.status_code == 409
    assert scene.json()["detail"]["code"] == "DEVICE_LAB_APPROVED_PROPOSAL_REQUIRED"
    run = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "idempotencyKey": "test-unapproved-scene",
        },
    )
    assert run.status_code == 409


def test_approved_proposal_projects_and_persists_one_immutable_physical_scene() -> None:
    client = TestClient(app)
    project_id = _create_project(client)

    first = client.get(f"/api/projects/{project_id}/device-lab/scene")
    second = client.get(f"/api/projects/{project_id}/device-lab/scene")

    assert first.status_code == 200, first.json()
    assert second.status_code == 200
    scene = first.json()["scene"]
    assert scene["schemaVersion"] == "zhangwen.device-lab-scene/v1"
    assert scene["boardId"] == "dfrobot/dfrobot_k10"
    assert scene["source"]["proposalVersion"] == 1
    assert any(item["role"] == "controller" for item in scene["components"])
    assert any(item["role"] == "onboard" for item in scene["components"])
    assert second.json()["scene"]["revision"] == scene["revision"]
    repository = ProjectRepository(settings.data_dir)
    with sqlite3.connect(repository.db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM device_lab_scenes WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    assert count == 1


def test_simulation_board_is_derived_from_scene_and_revision_is_guarded() -> None:
    client = TestClient(app)
    project_id = _create_project(
        client,
        board_id="seeedstudio/xiao_esp32s3_sense",
    )
    scene = client.get(f"/api/projects/{project_id}/device-lab/scene").json()["scene"]

    stale = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "expectedSceneRevision": "0" * 64,
            "idempotencyKey": "test-stale-scene-revision",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "DEVICE_LAB_SCENE_REVISION_CONFLICT"

    wrong_solution = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "expectedSceneRevision": scene["revision"],
            "expectedSolutionRevisionId": "csolution_wrong",
            "idempotencyKey": "test-wrong-solution-binding",
        },
    )
    assert wrong_solution.status_code == 409
    assert (
        wrong_solution.json()["detail"]["code"]
        == "CREATOR_SIMULATION_SOLUTION_MISMATCH"
    )

    started = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "expectedSceneRevision": scene["revision"],
            "idempotencyKey": "test-derived-board-run",
        },
    )
    assert started.status_code == 200, started.json()
    assert started.json()["run"]["boardId"] == "seeedstudio/xiao_esp32s3_sense"
    assert started.json()["run"]["scene"]["revision"] == scene["revision"]


def test_project_peripherals_create_functional_controls_and_safe_actuator_limits() -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    repository = ProjectRepository(settings.data_dir)
    hardware_skills = HardwareSkillRepository(settings.data_dir, repository.db_path)
    hardware_skills.install_bundled_catalog()
    hardware_skills.migrate_legacy_rows()
    repository.replace_preferred_hardware(
        project_id,
        [
            "hw_seed_unihiker_k10",
            "hw_dfrobot_sen0193",
            "hw_dfrobot_dfr0523",
            "hw_power_5v_3a_regulated",
        ],
    )

    scene_response = client.get(f"/api/projects/{project_id}/device-lab/scene")
    assert scene_response.status_code == 200, scene_response.json()
    scene = scene_response.json()["scene"]
    profile = scene_response.json()["profile"]
    external = [item for item in scene["components"] if item["role"] == "external"]
    assert {item["category"] for item in external} >= {"SENSOR", "ACTUATOR"}
    sensor = next(
        item
        for item in profile["channels"]
        if item["source"] == "project-scene" and item["kind"] == "sensor-input"
    )
    actuator = next(
        item
        for item in profile["channels"]
        if item["source"] == "project-scene" and item["kind"] == "actuator"
    )
    limit = next(
        item
        for item in profile["channels"]
        if item["componentId"] == actuator["componentId"]
        and item["kind"] == "parameter"
    )

    started = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "expectedSceneRevision": scene["revision"],
            "idempotencyKey": "test-project-peripherals-run",
        },
    )
    assert started.status_code == 200, started.json()
    run = started.json()["run"]
    changed_sensor = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/{sensor['id']}",
        headers=DESKTOP_HEADERS,
        json={
            "value": 73,
            "expectedRevision": run["revision"],
            "commandId": "project-sensor-input-0001",
        },
    )
    assert changed_sensor.status_code == 200, changed_sensor.json()
    run = changed_sensor.json()["run"]
    lowered_limit = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/{limit['id']}",
        headers=DESKTOP_HEADERS,
        json={
            "value": 20,
            "expectedRevision": run["revision"],
            "commandId": "project-actuator-limit-0001",
        },
    )
    assert lowered_limit.status_code == 200, lowered_limit.json()
    run = lowered_limit.json()["run"]
    blocked = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/{actuator['id']}",
        headers=DESKTOP_HEADERS,
        json={
            "value": 21,
            "expectedRevision": run["revision"],
            "actuatorArmed": True,
            "commandId": "project-actuator-output-0001",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "DEVICE_LAB_ACTUATOR_LIMIT_EXCEEDED"


def test_parameter_revision_cannot_override_proposal_derived_board() -> None:
    client = TestClient(app)
    project_id = _create_project(client)

    response = client.post(
        f"/api/projects/{project_id}/device-lab/parameter-sets",
        headers=DESKTOP_HEADERS,
        json={
            "idempotencyKey": "test-wrong-board-parameters",
            "boardId": "seeedstudio/xiao_esp32s3_sense",
            "profileRevision": "seeed-xiao-esp32s3-sense-functional-v1",
            "label": "错误板型",
            "values": {"sample-interval-ms": 500},
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "PARAMETER_SET_BOARD_MISMATCH"


def test_hardware_catalog_and_creation_enforce_two_controller_boards(tmp_path: Path) -> None:
    project_repository = ProjectRepository(tmp_path)
    seed_default_components(project_repository.db_path)
    seed_builtin_mechanical_profiles(project_repository.db_path)
    components = HardwareRepository(
        project_repository.db_path,
        data_dir=tmp_path,
    ).list_components(category="MCU")
    assert {component.id for component in components} == {
        "hw_seed_unihiker_k10",
        "hw_seeed_xiao_esp32s3_sense",
    }
    xiao_profile = MechanicalProfileRepository(
        project_repository.db_path
    ).resolve_for_hardware("hw_seeed_xiao_esp32s3_sense")
    assert xiao_profile.profile_id == "xiao_esp32s3"
    assert xiao_profile.display_name == "Seeed Studio XIAO ESP32S3 Sense"

    settings.data_dir = tmp_path
    client = TestClient(app)
    rejected = client.post(
        "/api/hardware",
        json={
            "name": "第三种主控",
            "category": "MCU",
            "electrical": {
                "voltage": 5,
                "logicLevel": 3.3,
                "peakCurrent": 0,
                "communicationProtocol": "GPIO",
            },
        },
    )
    assert rejected.status_code == 422
    assert "只允许 K10 与 XIAO" in rejected.json()["detail"]["message"]


def test_k10_functional_run_enforces_actuator_arm_and_saves_parameters() -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    started = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "idempotencyKey": "test-k10-functional-run",
        },
    )
    assert started.status_code == 200, started.json()
    run = started.json()["run"]
    profile_revision = started.json()["profile"]["revision"]
    assert run["engine"] == "FUNCTIONAL_MODEL"
    assert run["status"] == "RUNNING"

    changed = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/temperature",
        headers=DESKTOP_HEADERS,
        json={
            "value": 31.5,
            "expectedRevision": run["revision"],
            "commandId": "command-temperature-1",
        },
    )
    assert changed.status_code == 200
    run = changed.json()["run"]
    assert run["channelValues"]["temperature"] == 31.5

    blocked = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/rgb-brightness",
        headers=DESKTOP_HEADERS,
        json={
            "value": 5,
            "expectedRevision": run["revision"],
            "commandId": "command-rgb-blocked-1",
        },
    )
    assert blocked.status_code == 409
    assert blocked.json()["detail"]["code"] == "DEVICE_LAB_ACTUATOR_NOT_ARMED"

    saved = client.post(
        f"/api/projects/{project_id}/device-lab/parameter-sets",
        headers=DESKTOP_HEADERS,
        json={
            "idempotencyKey": "test-k10-parameter-save",
            "boardId": "dfrobot/dfrobot_k10",
            "profileRevision": profile_revision,
            "label": "课堂调试",
            "values": {"sample-interval-ms": 500, "temperature-offset": -1.5},
        },
    )
    assert saved.status_code == 200, saved.json()
    parameter_set = saved.json()["parameterSet"]
    applied = client.post(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/apply-parameters",
        headers=DESKTOP_HEADERS,
        json={"parameterSetId": parameter_set["id"], "expectedRevision": run["revision"]},
    )
    assert applied.status_code == 200, applied.json()
    run = applied.json()["run"]
    assert run["channelValues"]["sample-interval-ms"] == 500

    armed = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/rgb-brightness",
        headers=DESKTOP_HEADERS,
        json={
            "value": 5,
            "expectedRevision": run["revision"],
            "actuatorArmed": True,
            "commandId": "command-rgb-armed-1",
        },
    )
    assert armed.status_code == 200
    stopped = client.post(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/stop",
        headers=DESKTOP_HEADERS,
    )
    assert stopped.status_code == 200
    assert stopped.json()["run"]["channelValues"]["rgb-brightness"] == 0
    assert stopped.json()["run"]["actuatorArmed"] is False


def test_xiao_sd_card_gpio21_conflict_fails_closed() -> None:
    client = TestClient(app)
    project_id = _create_project(client, board_id="seeedstudio/xiao_esp32s3_sense")
    started = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={
            "target": "SIMULATOR",
            "idempotencyKey": "test-xiao-pin-conflict-run",
        },
    )
    run = started.json()["run"]
    response = client.put(
        f"/api/projects/{project_id}/device-lab/runs/{run['id']}/channels/user-led",
        headers=DESKTOP_HEADERS,
        json={
            "value": True,
            "expectedRevision": run["revision"],
            "actuatorArmed": True,
            "commandId": "command-xiao-led-1",
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "DEVICE_LAB_PIN_CONFLICT"


def test_application_import_validates_board_hash_and_paths() -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    archive = _application_archive("dfrobot/dfrobot_k10")
    imported = client.post(
        f"/api/projects/{project_id}/device-lab/applications/import",
        headers=DESKTOP_HEADERS,
        json={"zipBase64": base64.b64encode(archive).decode("ascii")},
    )
    assert imported.status_code == 200, imported.json()
    application = imported.json()["application"]
    assert application["manifest"]["boardId"] == "dfrobot/dfrobot_k10"
    assert application["simulationCapability"] == "NONE"

    unsupported = client.post(
        f"/api/projects/{project_id}/device-lab/runs",
        headers=DESKTOP_HEADERS,
        json={"boardId": "espressif/esp32-s3-devkitc-1", "target": "SIMULATOR"},
    )
    assert unsupported.status_code == 422

    malicious = _application_archive("dfrobot/dfrobot_k10", extra_name="../outside.bin")
    rejected = client.post(
        f"/api/projects/{project_id}/device-lab/applications/import",
        headers=DESKTOP_HEADERS,
        json={"zipBase64": base64.b64encode(malicious).decode("ascii")},
    )
    assert rejected.status_code == 422
    assert rejected.json()["detail"]["code"] == "FIRMWARE_APPLICATION_PATH_INVALID"


@pytest.mark.parametrize(
    ("mutate", "expected_code"),
    [
        (
            lambda manifest: manifest["deviceImages"][0].update({"sha256": "0" * 64}),
            "FIRMWARE_APPLICATION_IMAGE_HASH_MISMATCH",
        ),
        (
            lambda manifest: manifest.update({"flashSizeBytes": 8 * 1024 * 1024}),
            "FIRMWARE_APPLICATION_MEMORY_MISMATCH",
        ),
        (
            lambda manifest: manifest["deviceImages"][1].update({"address": 1}),
            "FIRMWARE_APPLICATION_SEGMENT_OVERLAP",
        ),
        (
            lambda manifest: manifest.update({"debugProtocolVersion": "zwdbg/99"}),
            "FIRMWARE_APPLICATION_MANIFEST_INVALID",
        ),
        (
            lambda manifest: manifest.update({"unexpected": True}),
            "FIRMWARE_APPLICATION_MANIFEST_INVALID",
        ),
    ],
)
def test_application_import_rejects_unsafe_or_unknown_manifest_data(
    mutate,
    expected_code: str,
) -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    archive = _rewrite_manifest(_application_archive("dfrobot/dfrobot_k10"), mutate)

    response = client.post(
        f"/api/projects/{project_id}/device-lab/applications/import",
        headers=DESKTOP_HEADERS,
        json={"zipBase64": base64.b64encode(archive).decode("ascii")},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == expected_code


def test_application_import_validates_optional_elf_asset() -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    elf = b"ELF-debug-symbols"
    archive = _rewrite_manifest(
        _application_archive("dfrobot/dfrobot_k10"),
        lambda manifest: manifest.update(
            {
                "elfImage": {
                    "path": "debug/application.elf",
                    "sizeBytes": len(elf),
                    "sha256": hashlib.sha256(elf).hexdigest(),
                }
            }
        ),
        extra_files={"debug/application.elf": elf},
    )

    response = client.post(
        f"/api/projects/{project_id}/device-lab/applications/import",
        headers=DESKTOP_HEADERS,
        json={"zipBase64": base64.b64encode(archive).decode("ascii")},
    )

    assert response.status_code == 200, response.json()
    assert response.json()["application"]["manifest"]["elfImage"]["path"] == (
        "debug/application.elf"
    )


def test_parameter_versions_reject_credentials_before_channel_validation() -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    profile_revision = client.get(
        f"/api/projects/{project_id}/device-lab/scene"
    ).json()["profile"]["revision"]

    response = client.post(
        f"/api/projects/{project_id}/device-lab/parameter-sets",
        headers=DESKTOP_HEADERS,
        json={
            "idempotencyKey": "test-secret-parameter-rejection",
            "boardId": "dfrobot/dfrobot_k10",
            "profileRevision": profile_revision,
            "label": "unsafe",
            "values": {"wifi-password": "never-store-this"},
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "PARAMETER_SET_SECRET_REJECTED"


def test_serial_connection_requires_exact_supported_board_confirmation() -> None:
    client = TestClient(app)
    project_id = _create_project(client)
    missing_confirmation = client.post(
        f"/api/projects/{project_id}/devices/connect",
        headers=DESKTOP_HEADERS,
        json={
            "portId": "mock_port_esp32_s3",
            "boardId": "dfrobot/dfrobot_k10",
            "confirmBoardIdentity": False,
        },
    )
    assert missing_confirmation.status_code == 422
    assert missing_confirmation.json()["detail"]["code"] == "DEVICE_BOARD_CONFIRMATION_REQUIRED"

    unsupported = client.post(
        f"/api/projects/{project_id}/devices/connect",
        headers=DESKTOP_HEADERS,
        json={
            "portId": "mock_port_esp32_s3",
            "boardId": "espressif/esp32-s3-devkitc-1",
            "confirmBoardIdentity": True,
        },
    )
    assert unsupported.status_code == 422


def test_application_install_uses_segment_backup_write_verify_and_confirmation() -> None:
    transport = MockDeviceTransport()
    devices_router.configure_device_transport(transport)
    client = TestClient(app)
    project_id = _create_project(client)
    imported = client.post(
        f"/api/projects/{project_id}/device-lab/applications/import",
        headers=DESKTOP_HEADERS,
        json={"zipBase64": base64.b64encode(_application_archive("dfrobot/dfrobot_k10")).decode("ascii")},
    ).json()["application"]
    connected = client.post(
        f"/api/projects/{project_id}/devices/connect",
        headers=DESKTOP_HEADERS,
        json={
            "portId": "mock_port_esp32_s3",
            "boardId": "dfrobot/dfrobot_k10",
            "confirmBoardIdentity": True,
        },
    )
    assert connected.status_code == 200, connected.json()
    session_id = connected.json()["session"]["id"]
    profile_revision = client.get(
        f"/api/projects/{project_id}/device-lab/scene"
    ).json()["profile"]["revision"]
    plan = client.post(
        f"/api/projects/{project_id}/device-lab/applications/prepare-install",
        headers=DESKTOP_HEADERS,
        json={
            "sessionId": session_id,
            "applicationId": imported["id"],
            "boardId": "dfrobot/dfrobot_k10",
            "confirmBoardIdentity": True,
        },
    )
    assert plan.status_code == 200, plan.json()
    assert plan.json()["plan"]["segmentCount"] == 2

    blocked = client.post(
        f"/api/projects/{project_id}/device-lab/applications/install",
        headers=DESKTOP_HEADERS,
        json={
            "sessionId": session_id,
            "applicationId": imported["id"],
            "confirmationToken": plan.json()["plan"]["confirmationToken"],
            "operationId": "application-install-0001",
            "confirmInstall": True,
            "confirmationPhrase": "错误短语",
        },
    )
    assert blocked.status_code == 422

    started = client.post(
        f"/api/projects/{project_id}/device-lab/applications/install",
        headers=DESKTOP_HEADERS,
        json={
            "sessionId": session_id,
            "applicationId": imported["id"],
            "confirmationToken": plan.json()["plan"]["confirmationToken"],
            "operationId": "application-install-0001",
            "confirmInstall": True,
            "confirmationPhrase": "安装应用",
        },
    )
    assert started.status_code == 200, started.json()
    operation = started.json()["operation"]
    for _ in range(50):
        current = client.get(
            f"/api/projects/{project_id}/devices/operations/{operation['id']}"
        )
        operation = current.json()["operation"]
        if operation["status"] not in {"QUEUED", "RUNNING"}:
            break
        time.sleep(0.01)
    assert operation["status"] == "COMPLETED", operation
    assert operation["kind"] == "INSTALL_APPLICATION"
    assert operation["backup"]["fileCount"] == 2
    assert operation["metadata"]["fullErase"] is False
    assert sum(name == "backup_flash" for name, _ in transport.calls) == 2
    assert sum(name == "flash" for name, _ in transport.calls) == 2
    assert sum(name == "verify_firmware" for name, _ in transport.calls) == 2

    replayed = client.post(
        f"/api/projects/{project_id}/device-lab/applications/install",
        headers=DESKTOP_HEADERS,
        json={
            "sessionId": session_id,
            "applicationId": imported["id"],
            "confirmationToken": plan.json()["plan"]["confirmationToken"],
            "operationId": "application-install-0001",
            "confirmInstall": True,
            "confirmationPhrase": "安装应用",
        },
    )
    assert replayed.status_code == 200, replayed.json()
    assert replayed.json()["operation"]["id"] == operation["id"]
    assert sum(name == "flash" for name, _ in transport.calls) == 2


def test_parameter_sync_stages_commits_reads_back_and_preserves_backup() -> None:
    transport = MockDeviceTransport(
        files={"mock_port_esp32_s3": {".zhangwen/parameters.json": b"old-parameters\n"}}
    )
    devices_router.configure_device_transport(transport)
    client = TestClient(app)
    project_id = _create_project(client)
    connected = client.post(
        f"/api/projects/{project_id}/devices/connect",
        headers=DESKTOP_HEADERS,
        json={
            "portId": "mock_port_esp32_s3",
            "boardId": "dfrobot/dfrobot_k10",
            "confirmBoardIdentity": True,
        },
    )
    session_id = connected.json()["session"]["id"]
    profile_revision = client.get(
        f"/api/projects/{project_id}/device-lab/scene"
    ).json()["profile"]["revision"]
    saved = client.post(
        f"/api/projects/{project_id}/device-lab/parameter-sets",
        headers=DESKTOP_HEADERS,
        json={
            "idempotencyKey": "test-device-parameter-sync-save",
            "boardId": "dfrobot/dfrobot_k10",
            "profileRevision": profile_revision,
            "label": "真机同步",
            "values": {"sample-interval-ms": 250, "temperature-offset": 0.5},
        },
    ).json()["parameterSet"]

    blocked = client.post(
        f"/api/projects/{project_id}/device-lab/parameter-sets/{saved['id']}/sync",
        headers=DESKTOP_HEADERS,
        json={"sessionId": session_id, "operationId": "parameter-sync-0001", "confirmSync": False},
    )
    assert blocked.status_code == 422
    started = client.post(
        f"/api/projects/{project_id}/device-lab/parameter-sets/{saved['id']}/sync",
        headers=DESKTOP_HEADERS,
        json={"sessionId": session_id, "operationId": "parameter-sync-0001", "confirmSync": True},
    )
    assert started.status_code == 200, started.json()
    operation = started.json()["operation"]
    for _ in range(50):
        operation = client.get(
            f"/api/projects/{project_id}/devices/operations/{operation['id']}"
        ).json()["operation"]
        if operation["status"] not in {"QUEUED", "RUNNING"}:
            break
        time.sleep(0.01)
    assert operation["status"] == "COMPLETED", operation
    assert operation["kind"] == "SYNC_PARAMETERS"
    assert operation["backup"]["fileCount"] == 1
    current = transport.files["mock_port_esp32_s3"]
    assert b'"sample-interval-ms":250.0' in current[".zhangwen/parameters.json"]
    assert ".zhangwen/parameters.next.json" not in current
    assert [name for name, _ in transport.calls].count("read") == 2


def _application_archive(board_id: str, extra_name: str | None = None) -> bytes:
    bootloader = b"bootloader-test"
    application = b"application-test"
    manifest = {
        "schemaVersion": "zhangwen.firmware-application/v1",
        "applicationId": "esp-claw-test",
        "displayName": "ESP-Claw 测试应用",
        "version": "1.0.0",
        "runtime": "esp-claw",
        "boardId": board_id,
        "chip": "esp32s3",
        "flashSizeBytes": 16 * 1024 * 1024,
        "psramSizeBytes": 8 * 1024 * 1024,
        "sourceUrl": "https://github.com/espressif/esp-claw",
        "deviceImages": [
            {
                "path": "images/bootloader.bin",
                "address": 0,
                "sizeBytes": len(bootloader),
                "sha256": hashlib.sha256(bootloader).hexdigest(),
                "kind": "bootloader",
            },
            {
                "path": "images/application.bin",
                "address": 0x10000,
                "sizeBytes": len(application),
                "sha256": hashlib.sha256(application).hexdigest(),
                "kind": "application",
            },
        ],
    }
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as package:
        package.writestr("manifest.json", json.dumps(manifest))
        package.writestr("images/bootloader.bin", bootloader)
        package.writestr("images/application.bin", application)
        if extra_name:
            package.writestr(extra_name, b"unsafe")
    return stream.getvalue()


def _rewrite_manifest(
    archive: bytes,
    mutate,
    *,
    extra_files: dict[str, bytes] | None = None,
) -> bytes:
    with zipfile.ZipFile(io.BytesIO(archive)) as source:
        files = {
            info.filename: source.read(info.filename)
            for info in source.infolist()
            if not info.is_dir() and info.filename != "manifest.json"
        }
        manifest = json.loads(source.read("manifest.json"))
    mutate(manifest)
    files.update(extra_files or {})
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as target:
        target.writestr("manifest.json", json.dumps(manifest))
        for name, payload in files.items():
            target.writestr(name, payload)
    return stream.getvalue()


def _create_project(
    client: TestClient,
    *,
    board_id: str = "dfrobot/dfrobot_k10",
) -> str:
    component_id = (
        "hw_seeed_xiao_esp32s3_sense"
        if board_id == "seeedstudio/xiao_esp32s3_sense"
        else "hw_seed_unihiker_k10"
    )
    board_name = (
        "XIAO ESP32S3 Sense"
        if board_id == "seeedstudio/xiao_esp32s3_sense"
        else "DFRobot K10"
    )
    response = client.post(
        "/api/projects",
        json={
            "name": "双板设备实验室",
            "initialIdea": f"使用 {board_name} 调试传感器与执行器",
            "selectedHardwareIds": [component_id],
        },
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
                title="推荐实现",
                content=f"使用 {board_name} 连接项目外设。",
            )
        ],
    )
    solution = solutions.confirm_solution(project_id, solution.id)
    sections = [
        ProposalSection(id="project_overview", title="项目概述", content=f"使用 {board_name} 完成项目。"),
        ProposalSection(id="requirements", title="需求", content="支持传感器输入与执行器调试。"),
        ProposalSection(id="hardware_software_structure", title="软硬件结构", content=f"主控为 {board_name}，连接项目外设。"),
        ProposalSection(id="implementation_plan", title="实施计划", content="先仿真，再上传并验证。"),
        ProposalSection(id="cost_difficulty_schedule", title="成本难度进度", content="使用现有硬件，分阶段完成。"),
        ProposalSection(id="risks_acceptance", title="风险验收", content="执行器默认安全值，断线归零。"),
    ]
    proposals = ProposalRepository(repository.db_path)
    proposal = proposals.create_proposal(
        project_id=project_id,
        solution=solution,
        sections=sections,
        supersede_drafts=True,
    )
    proposals.confirm_proposal(project_id, proposal.id)
    return project_id
