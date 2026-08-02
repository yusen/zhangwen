from __future__ import annotations

import base64
import io
import json
import sqlite3
import warnings
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.artifacts.models import (
    ArtifactKind,
    ArtifactPreviewSection,
    ArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.code_agent.chat_code import ChatCodeService
from zhangwen.code_agent.models import (
    ChatCodeDraft,
    ChatCodeFileDraft,
    CodeTestResult,
    CodeValidationCheck,
    CodeValidationKind,
    CodeValidationStatus,
)
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.config import settings
from zhangwen.creator.delivery import CreatorDeliveryService
from zhangwen.creator.models import ImportCreatorDeliveryRequest
from zhangwen.creator.repository import CreatorError
from zhangwen.devices.models import DeviceOperationKind, DeviceOperationStatus
from zhangwen.devices.repository import DeviceRepository
from zhangwen.device_lab.models import SupportedDeviceBoardId
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository
import zhangwen.creator.router as creator_router


HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "creator-m7-token",
}


@pytest.fixture(autouse=True)
def creator_subject(monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    state = {"value": "subject-m7-original"}
    monkeypatch.setattr(
        creator_router, "current_owner_subject", lambda: state["value"]
    )
    return state


@pytest.fixture(autouse=True)
def _runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "creator-m7-token")


def _workspace(client: TestClient, work_id: str) -> dict[str, object]:
    response = client.get(f"/api/creator/works/{work_id}/workspace")
    assert response.status_code == 200, response.json()
    return response.json()["workspace"]


def _command(
    client: TestClient,
    work_id: str,
    command: str,
    key: str,
    payload: dict[str, object],
):
    return client.post(
        f"/api/creator/works/{work_id}/commands/{command}",
        headers=HEADERS,
        json={
            "baseProjectVersion": _workspace(client, work_id)["projectVersion"],
            "idempotencyKey": key,
            "payload": payload,
        },
    )


def _create_work(
    client: TestClient,
    *,
    name: str,
    structure: str = "不需要结构",
) -> str:
    created = client.post(
        "/api/creator/works",
        json={
            "name": name,
            "initialIdea": "用 K10 制作环境提醒器",
            "idempotencyKey": f"creator-m7-create-{name}",
            "selectedHardwareIds": ["hw_seed_unihiker_k10"],
        },
    )
    assert created.status_code == 200, created.json()
    work_id = created.json()["workspace"]["workId"]
    goal = _command(
        client,
        work_id,
        "CONFIRM_GOAL",
        f"creator-m7-goal-{work_id}",
        {
            "statement": "制作环境提醒器",
            "observableBehavior": "过热时点亮，恢复后关闭",
            "constraints": ["离线运行"],
            "successCriteria": ["过热点亮", "恢复关闭"],
        },
    )
    assert goal.status_code == 200, goal.json()
    solution = _command(
        client,
        work_id,
        "CONFIRM_SOLUTION",
        f"creator-m7-solution-{work_id}",
        {
            "summary": "K10 环境提醒",
            "logic": "采集温度并按阈值控制 RGB",
            "hardware": "DFRobot K10 板载温度传感器与 RGB",
            "software": "MicroPython 受控循环",
            "structure": structure,
            "simulation": "注入过热和恢复场景",
            "safety": "停止、断线和重连时输出归零",
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
                    "simulationExpected": "过热点亮，恢复关闭",
                    "physicalExpected": "真机完成相同提醒与恢复",
                }
            ],
        },
    )
    assert solution.status_code == 200, solution.json()
    return work_id


def _seed_code(tmp_path: Path, work_id: str) -> str:
    db_path = ProjectRepository(tmp_path).db_path
    existing = CodeRepository(db_path).get_current_code(work_id)
    if existing is not None and existing.status.value == "ACCEPTED":
        return existing.id
    draft = ChatCodeDraft(
        summary="环境提醒器受控代码",
        files=[
            ChatCodeFileDraft(
                path="src/main.py",
                language="python",
                content=(
                    "temperature_c = 25.0\n"
                    "threshold_c = 30.0\n"
                    "rgb_brightness = 3 if temperature_c >= threshold_c else 0\n"
                ),
            )
        ],
    )
    code = ChatCodeService(db_path).materialize(
        project_id=work_id,
        source_message_id=f"creator-m7-code-{work_id}",
        generated_by_expert_id=None,
        draft=draft,
    )
    repository = CodeRepository(db_path)
    validated = repository.validate_code(
        work_id,
        code.id,
        CodeTestResult(
            ok=True,
            command="creator-m7-bounded-validation",
            output="静态与语法检查通过",
            createdAt="2026-07-31T00:00:00Z",
            checks=[
                CodeValidationCheck(
                    kind=kind,
                    status=CodeValidationStatus.PASSED,
                    command=f"validate-{kind.value.lower()}",
                    exitCode=0,
                    output="通过",
                )
                for kind in (
                    CodeValidationKind.STATIC,
                    CodeValidationKind.SYNTAX,
                )
            ],
        ),
    )
    accepted = repository.accept_code(work_id, validated.id)
    assert accepted.artifactId
    assert accepted.artifactVersionId
    return accepted.id


def _prepare_digital_evidence(
    client: TestClient,
    tmp_path: Path,
    work_id: str,
    *,
    include_code: bool = True,
) -> tuple[str, str]:
    scene_response = client.get(f"/api/projects/{work_id}/device-lab/scene")
    assert scene_response.status_code == 200, scene_response.json()
    scene = scene_response.json()["scene"]
    profile = scene_response.json()["profile"]
    code_run_id = _seed_code(tmp_path, work_id) if include_code else "missing-code"
    parameters = client.post(
        f"/api/projects/{work_id}/device-lab/parameter-sets",
        headers=HEADERS,
        json={
            "idempotencyKey": f"creator-m7-params-{work_id}",
            "boardId": scene["boardId"],
            "profileRevision": profile["revision"],
            "label": "M7 可复现阈值",
            "values": {
                "temperature-offset": 0.5,
                "rgb-max-brightness": 3,
            },
        },
    )
    assert parameters.status_code == 200, parameters.json()
    static = _command(
        client,
        work_id,
        "RECORD_STATIC_VALIDATION",
        f"creator-m7-static-{work_id}",
        {
            "passed": True,
            "summary": "当前方案数字原型静态检查通过",
            "sourceId": scene["revision"],
            "bindings": {"sceneRevision": scene["revision"]},
        },
    )
    assert static.status_code == 200, static.json()
    started = client.post(
        f"/api/projects/{work_id}/device-lab/runs",
        headers=HEADERS,
        json={
            "idempotencyKey": f"creator-m7-run-{work_id}",
            "target": "SIMULATOR",
            "expectedSceneRevision": scene["revision"],
        },
    )
    assert started.status_code == 200, started.json()
    run = started.json()["run"]
    stopped = client.post(
        f"/api/projects/{work_id}/device-lab/runs/{run['id']}/stop",
        headers=HEADERS,
        json={},
    )
    assert stopped.status_code == 200, stopped.json()
    scenario_ids = ",".join(
        sorted(
            str(item["id"])
            for item in _workspace(client, work_id)["acceptanceScenarios"]
        )
    )
    simulation = _command(
        client,
        work_id,
        "RECORD_SIMULATION",
        f"creator-m7-simulation-{work_id}",
        {
            "passed": True,
            "summary": "全部必需场景通过且仿真已安全停止",
            "sourceId": run["id"],
            "bindings": {
                "scenarioIds": scenario_ids,
                "sceneRevision": scene["revision"],
            },
        },
    )
    assert simulation.status_code == 200, simulation.json()
    return code_run_id, scene["revision"]


def _verified_deployment(
    tmp_path: Path,
    work_id: str,
    code_run_id: str,
) -> tuple[str, str]:
    devices = DeviceRepository(ProjectRepository(tmp_path).db_path)
    session = devices.connect_mock_port(
        work_id,
        "mock_port_esp32_s3",
        SupportedDeviceBoardId.DFROBOT_K10,
    )
    operation_id = f"upload-creator-m7-{work_id}"
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
            "codeRunId": code_run_id,
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


def _advance_to_physical(
    client: TestClient,
    tmp_path: Path,
    work_id: str,
    *,
    include_code: bool = True,
) -> None:
    code_run_id, _scene_revision = _prepare_digital_evidence(
        client,
        tmp_path,
        work_id,
        include_code=include_code,
    )
    session_id, operation_id = _verified_deployment(
        tmp_path,
        work_id,
        code_run_id,
    )
    connection = _command(
        client,
        work_id,
        "RECORD_DEVICE_CONNECTION",
        f"creator-m7-connection-{work_id}",
        {
            "passed": True,
            "summary": "Mock 串口身份与当前设备包匹配",
            "sourceId": session_id,
            "bindings": {"channel": "USB_SERIAL"},
        },
    )
    assert connection.status_code == 200, connection.json()
    deployment = _command(
        client,
        work_id,
        "RECORD_DEPLOYMENT",
        f"creator-m7-deployment-{work_id}",
        {
            "passed": True,
            "summary": "Mock 上传完成、文件回读与运行时验证通过",
            "sourceId": operation_id,
            "bindings": {"codeRunId": code_run_id},
        },
    )
    assert deployment.status_code == 200, deployment.json()
    scenario_ids = [
        str(item["id"])
        for item in _workspace(client, work_id)["acceptanceScenarios"]
        if item["required"]
    ]
    physical = client.post(
        f"/api/creator/works/{work_id}/physical-runs",
        headers=HEADERS,
        json={
            "idempotencyKey": f"creator-m7-physical-{work_id}",
            "deploymentOperationId": operation_id,
            "targetId": session_id,
            "operator": "真机测试操作者",
            "emergencyStopVerified": True,
            "scenarioResults": [
                {
                    "scenarioId": scenario_id,
                    "observed": True,
                    "note": "逐项观察通过",
                }
                for scenario_id in scenario_ids
            ],
        },
    )
    assert physical.status_code == 200, physical.json()
    behavior = _command(
        client,
        work_id,
        "RECORD_PHYSICAL_BEHAVIOR",
        f"creator-m7-physical-{work_id}",
        {
            "passed": True,
            "summary": "全部当前方案真机场景通过",
            "sourceId": physical.json()["run"]["id"],
        },
    )
    assert behavior.status_code == 200, behavior.json()
    assert behavior.json()["workspace"]["verificationLevel"] == 5


def _accept_work(client: TestClient, work_id: str, actor: str):
    return _command(
        client,
        work_id,
        "ACCEPT_WORK",
        f"creator-m7-accept-{work_id}-{actor}",
        {
            "accepted": True,
            "summary": "用户逐项观察并明确接受当前作品",
            "actor": actor,
        },
    )


def _accepted_work(
    client: TestClient,
    tmp_path: Path,
    *,
    actor: str = "原作者",
    structure: str = "不需要结构",
    include_code: bool = True,
) -> str:
    work_id = _create_work(
        client,
        name=f"Creator 可复现环境提醒器 {actor} {structure}",
        structure=structure,
    )
    _advance_to_physical(
        client,
        tmp_path,
        work_id,
        include_code=include_code,
    )
    accepted = _accept_work(client, work_id, actor)
    assert accepted.status_code == 200, accepted.json()
    assert accepted.json()["workspace"]["verificationLevel"] == 6
    return work_id


def _zip_files(value: str) -> dict[str, bytes]:
    raw = base64.b64decode(value)
    with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def test_m7_three_delivery_variants_are_complete_hashed_private_and_reset(
    tmp_path: Path,
) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    deliveries: dict[str, dict[str, object]] = {}
    for variant in ("SHARE", "REPRODUCIBLE", "TEMPLATE"):
        response = client.post(
            f"/api/creator/works/{work_id}/deliveries",
            headers=HEADERS,
            json={
                "idempotencyKey": f"creator-m7-delivery-{variant.lower()}",
                "variant": variant,
            },
        )
        assert response.status_code == 200, response.json()
        delivery = response.json()["delivery"]
        repeated_delivery = client.post(
            f"/api/creator/works/{work_id}/deliveries",
            headers=HEADERS,
            json={
                "idempotencyKey": f"creator-m7-delivery-{variant.lower()}",
                "variant": variant,
            },
        )
        assert repeated_delivery.status_code == 200
        assert repeated_delivery.json() == response.json()
        assert delivery["manifest"]["privacyOk"] is True
        assert delivery["packageSha256"]
        assert delivery["manifest"]["maturity"] == {
            "sensing": "MVP",
            "responsiveExecution": "CONTROLLED_BETA",
        }
        bindings = delivery["manifest"]["versionBindings"]
        assert {
            "sceneRevision",
            "codeRunId",
            "codeArtifactId",
            "codeArtifactVersionId",
            "parameterSetId",
            "parameterRevision",
        }.issubset(bindings)
        files = _zip_files(delivery["zipBase64"])
        assert set(files) == {
            "creator/evidence.json",
            "creator/reproduction-guide.md",
            "creator/workspace.json",
            "manifest.json",
            "payload/project-package.zip",
            "privacy_report.json",
        }
        assert b"device-session" not in files["creator/evidence.json"]
        snapshot = json.loads(files["creator/workspace.json"])
        materials = snapshot["deliveryMaterials"]
        assert materials["currentSolutionRevisionId"] == delivery["manifest"][
            "solutionRevisionId"
        ]
        assert materials["code"]["artifactVersionId"] == bindings[
            "codeArtifactVersionId"
        ]
        assert materials["parameters"]["values"] == {
            "rgb-max-brightness": 3,
            "temperature-offset": 0.5,
        }
        if variant == "TEMPLATE":
            assert delivery["manifest"]["evidenceKinds"] == []
            assert "proof" not in materials
        else:
            assert {
                "simulation",
                "deviceConnection",
                "deployment",
                "physicalBehavior",
                "userAcceptance",
            }.issubset(materials["proof"])
        deliveries[variant] = delivery

    imported = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-import-variants",
            "zipBase64": deliveries["REPRODUCIBLE"]["zipBase64"],
            "importer": "第二测试用户",
        },
    )
    assert imported.status_code == 200, imported.json()
    repeated_import = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-import-variants",
            "zipBase64": deliveries["REPRODUCIBLE"]["zipBase64"],
            "importer": "different display name",
        },
    )
    assert repeated_import.status_code == 200
    assert repeated_import.json() == imported.json()
    changed_import = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-import-variants",
            "zipBase64": deliveries["SHARE"]["zipBase64"],
        },
    )
    assert changed_import.status_code == 409
    assert changed_import.json()["detail"]["code"] == "CREATOR_IDEMPOTENCY_KEY_REUSED"
    imported_workspace = imported.json()["workspace"]
    assert imported_workspace["workId"] != work_id
    assert imported_workspace["verificationLevel"] == 1
    assert imported_workspace["legacy"] is False
    assert imported_workspace["needsOrganization"] is False
    assert imported_workspace["currentSolution"]["summary"] == "K10 环境提醒"
    assert not imported_workspace["evidence"] or {
        item["kind"] for item in imported_workspace["evidence"]
    } == {"GOAL_CONFIRMATION"}
    assert _workspace(client, work_id)["phase"] == "ACCEPTED"


def test_m7_second_user_reproduction_receipt_binds_import_acceptance_and_hash(
    tmp_path: Path,
    creator_subject: dict[str, str],
) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    exported = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-repro-export", "variant": "REPRODUCIBLE"},
    ).json()["delivery"]
    creator_subject["value"] = "subject-m7-independent"
    imported = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-repro-import",
            "zipBase64": exported["zipBase64"],
            "importer": "第二测试用户",
        },
    )
    assert imported.status_code == 200, imported.json()
    reproduced_id = imported.json()["workspace"]["workId"]
    assert reproduced_id != work_id
    restored_code = CodeRepository(ProjectRepository(tmp_path).db_path).get_current_code(
        reproduced_id
    )
    assert restored_code is not None
    assert restored_code.status.value == "ACCEPTED"
    restored_parameters = client.get(
        f"/api/projects/{reproduced_id}/device-lab/parameter-sets"
    )
    assert restored_parameters.status_code == 200
    assert len(restored_parameters.json()["parameterSets"]) == 1
    _advance_to_physical(client, tmp_path, reproduced_id)
    assert len(
        client.get(
            f"/api/projects/{reproduced_id}/device-lab/parameter-sets"
        ).json()["parameterSets"]
    ) == 1
    accepted = _accept_work(client, reproduced_id, "第二测试用户")
    assert accepted.status_code == 200, accepted.json()
    assert accepted.json()["workspace"]["verificationLevel"] == 6

    receipt = client.post(
        f"/api/creator/works/{reproduced_id}/reproduction-receipt",
        headers=HEADERS,
        json={
            "operator": "第二测试用户",
            "summary": "第二位测试用户已按导入包独立完成全部验收",
        },
    )
    assert receipt.status_code == 200, receipt.json()
    assert receipt.json()["report"]["passed"] is True
    assert receipt.json()["report"]["packageSha256"] == exported["packageSha256"]
    assert receipt.json()["report"]["reproducedWorkId"] == reproduced_id
    assert receipt.json()["workspace"]["workId"] == work_id
    assert receipt.json()["workspace"]["phase"] == "DELIVERED"
    assert receipt.json()["workspace"]["verificationLevel"] == 6
    assert any(
        item["kind"] == "REPRODUCTION" and item["status"] == "CURRENT"
        for item in receipt.json()["workspace"]["evidence"]
    )


@pytest.mark.parametrize("actor", ["system", "AI", "assistant", "掌问"])
def test_m7_system_or_ai_identity_cannot_sign_user_acceptance(
    tmp_path: Path,
    actor: str,
) -> None:
    client = TestClient(app)
    work_id = _create_work(client, name=f"拒绝系统代签 {actor}")
    _advance_to_physical(client, tmp_path, work_id)
    rejected = _accept_work(client, work_id, actor)
    assert rejected.status_code == 409
    assert rejected.json()["detail"]["code"] == "CREATOR_HUMAN_ACCEPTANCE_REQUIRED"
    assert _workspace(client, work_id)["verificationLevel"] == 5


def test_m7_same_operator_cannot_close_reproduction_loop(tmp_path: Path) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path, actor="同一操作者")
    exported = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-same-export", "variant": "REPRODUCIBLE"},
    ).json()["delivery"]
    imported = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-same-import",
            "zipBase64": exported["zipBase64"],
            "importer": "同一操作者",
        },
    )
    assert imported.status_code == 200, imported.json()
    reproduced_id = imported.json()["workspace"]["workId"]
    _advance_to_physical(client, tmp_path, reproduced_id)
    assert _accept_work(client, reproduced_id, "同一操作者").status_code == 200
    receipt = client.post(
        f"/api/creator/works/{reproduced_id}/reproduction-receipt",
        headers=HEADERS,
        json={
            "operator": "同一操作者",
            "summary": "不能由原验收者自行关闭第二人复现环",
        },
    )
    assert receipt.status_code == 409
    assert receipt.json()["detail"]["code"] == "CREATOR_SECOND_OPERATOR_REQUIRED"
    assert _workspace(client, work_id)["phase"] == "ACCEPTED"


def test_m7_delivery_requires_current_code_and_required_structure_materials(
    tmp_path: Path,
) -> None:
    client = TestClient(app)
    no_code_id = _accepted_work(
        client,
        tmp_path,
        actor="缺少代码材料",
        include_code=False,
    )
    no_code = client.post(
        f"/api/creator/works/{no_code_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-no-code-export", "variant": "REPRODUCIBLE"},
    )
    assert no_code.status_code == 409
    assert no_code.json()["detail"]["code"] == "CREATOR_DELIVERY_INCOMPLETE"
    assert "acceptedCodeArtifact" in no_code.json()["detail"]["message"]

    structure_id = _accepted_work(
        client,
        tmp_path,
        actor="缺少结构材料",
        structure="带 USB 开孔和固定螺柱的外壳",
    )
    no_structure = client.post(
        f"/api/creator/works/{structure_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-no-structure-export", "variant": "REPRODUCIBLE"},
    )
    assert no_structure.status_code == 409
    assert no_structure.json()["detail"]["code"] == "CREATOR_DELIVERY_INCOMPLETE"
    assert "STRUCTURE_CHECK" in no_structure.json()["detail"]["message"]


def test_m7_delivery_blocks_private_endpoint_and_tampered_hash(
    tmp_path: Path,
) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    artifact_repo = ArtifactRepository(ProjectRepository(tmp_path).db_path)
    content = "debug endpoint=http://192.168.4.1/mcp"
    artifact_repo.upsert_text_artifact(
        artifact_id="artifact_creator_private_endpoint",
        project_id=work_id,
        title="不应导出的私网配置",
        kind=ArtifactKind.DOCUMENT,
        status=ArtifactStatus.APPROVED,
        source_agent_id="publish-agent",
        source_entity_type="document",
        source_entity_id="private-endpoint",
        source_version=1,
        content=content,
        summary=content,
        mime_type="text/markdown",
        sections=[
            ArtifactPreviewSection(
                id="private",
                title="私网",
                content=content,
            )
        ],
        confirmed_at="2026-07-31T00:00:00+00:00",
    )
    blocked = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-private-export", "variant": "REPRODUCIBLE"},
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "PROJECT_PACKAGE_PRIVACY_BLOCKED"

    clean_id = _accepted_work(client, tmp_path, actor="另一原作者")
    exported = client.post(
        f"/api/creator/works/{clean_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-tamper-export", "variant": "REPRODUCIBLE"},
    ).json()["delivery"]
    files = _zip_files(exported["zipBase64"])
    workspace = json.loads(files["creator/workspace.json"])
    workspace["name"] = "被篡改名称"
    files["creator/workspace.json"] = json.dumps(workspace).encode()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for path, payload in files.items():
            archive.writestr(path, payload)
    tampered = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-tamper-import",
            "zipBase64": base64.b64encode(buffer.getvalue()).decode(),
            "importer": "第二测试用户",
        },
    )
    assert tampered.status_code == 422
    assert tampered.json()["detail"]["code"] == "CREATOR_DELIVERY_HASH_MISMATCH"
    assert _workspace(client, clean_id)["verificationLevel"] == 6


def test_m7_new_parameter_revision_invalidates_downstream_evidence(
    tmp_path: Path,
) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    scene = client.get(f"/api/projects/{work_id}/device-lab/scene").json()
    parameter = client.post(
        f"/api/projects/{work_id}/device-lab/parameter-sets",
        headers=HEADERS,
        json={
            "idempotencyKey": f"creator-m7-params-new-{work_id}",
            "boardId": scene["scene"]["boardId"],
            "profileRevision": scene["profile"]["revision"],
            "label": "new calibration",
            "values": {"temperature-offset": 1.5},
        },
    )
    assert parameter.status_code == 200, parameter.json()

    workspace = _workspace(client, work_id)
    assert workspace["verificationLevel"] == 2
    stale = {
        item["kind"]: item
        for item in workspace["evidence"]
        if item["status"] == "STALE"
    }
    for kind in (
        "SIMULATION",
        "DEVICE_CONNECTION",
        "DEPLOYMENT",
        "PHYSICAL_BEHAVIOR",
        "USER_ACCEPTANCE",
    ):
        assert stale[kind]["invalidationReason"] == (
            "Dependencies changed: parameter set"
        )
    assert all(
        item["status"] == "CURRENT"
        for item in workspace["evidence"]
        if item["kind"] in {"GOAL_CONFIRMATION", "STATIC_VALIDATION"}
    )


def test_m7_import_rejects_duplicate_member_path(tmp_path: Path) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    exported = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={"idempotencyKey": "creator-m7-duplicate-export", "variant": "REPRODUCIBLE"},
    ).json()["delivery"]
    source_bytes = base64.b64decode(exported["zipBase64"])
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(source_bytes), "r") as source:
        with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as target:
            for info in source.infolist():
                target.writestr(info, source.read(info))
            with warnings.catch_warnings():
                warnings.simplefilter("ignore", UserWarning)
                target.writestr(
                    "creator/workspace.json",
                    source.read("creator/workspace.json"),
                )

    response = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-duplicate-import",
            "zipBase64": base64.b64encode(output.getvalue()).decode(),
            "importer": "第二测试用户",
        },
    )
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CREATOR_DELIVERY_DUPLICATE_PATH"


def test_m7_failed_material_restore_is_atomic_and_retryable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    exported = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-atomic-export",
            "variant": "REPRODUCIBLE",
        },
    ).json()["delivery"]
    before_ids = {
        item["id"] for item in client.get("/api/creator/works").json()["works"]
    }
    artifact_root = tmp_path / "artifact-files"
    before_directories = (
        {item.name for item in artifact_root.iterdir()}
        if artifact_root.exists()
        else set()
    )
    original_restore = CreatorDeliveryService._restore_delivery_materials

    def fail_restore(*_args, **_kwargs):
        raise CreatorError(
            "CREATOR_TEST_RESTORE_FAILED",
            "forced material restore failure",
            status_code=422,
        )

    monkeypatch.setattr(
        CreatorDeliveryService, "_restore_delivery_materials", fail_restore
    )
    failed = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-atomic-import",
            "zipBase64": exported["zipBase64"],
        },
    )
    assert failed.status_code == 422
    assert {
        item["id"] for item in client.get("/api/creator/works").json()["works"]
    } == before_ids
    after_directories = (
        {item.name for item in artifact_root.iterdir()}
        if artifact_root.exists()
        else set()
    )
    assert after_directories == before_directories

    monkeypatch.setattr(
        CreatorDeliveryService, "_restore_delivery_materials", original_restore
    )
    retried = client.post(
        "/api/creator/deliveries/import",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-atomic-import",
            "zipBase64": exported["zipBase64"],
        },
    )
    assert retried.status_code == 200, retried.json()


def test_m7_process_interruption_is_recovered_before_retry(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = TestClient(app)
    work_id = _accepted_work(client, tmp_path)
    exported = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-crash-export",
            "variant": "REPRODUCIBLE",
        },
    ).json()["delivery"]
    request = ImportCreatorDeliveryRequest(
        idempotencyKey="creator-m7-crash-import",
        zipBase64=exported["zipBase64"],
    )
    original_restore = CreatorDeliveryService._restore_creator_snapshot

    def interrupt_process(*_args, **_kwargs) -> None:
        raise SystemExit("simulated process termination")

    monkeypatch.setattr(
        CreatorDeliveryService,
        "_restore_creator_snapshot",
        interrupt_process,
    )
    service = CreatorDeliveryService(tmp_path)
    with pytest.raises(SystemExit, match="simulated process termination"):
        service.import_delivery(
            request,
            importer_subject="subject-m7-second-user",
        )

    db_path = ProjectRepository(tmp_path).db_path
    with sqlite3.connect(db_path) as conn:
        intent = conn.execute(
            """
            SELECT imported_project_id
            FROM creator_delivery_import_intents
            WHERE importer_subject = ? AND idempotency_key = ?
            """,
            ("subject-m7-second-user", "creator-m7-crash-import"),
        ).fetchone()
        assert intent is not None
        interrupted_project_id = str(intent[0])
        assert conn.execute(
            "SELECT COUNT(*) FROM projects WHERE id = ?",
            (interrupted_project_id,),
        ).fetchone()[0] == 1

    monkeypatch.setattr(
        CreatorDeliveryService,
        "_restore_creator_snapshot",
        original_restore,
    )
    recovered = CreatorDeliveryService(tmp_path).recover_incomplete_imports()
    assert recovered == 1
    with sqlite3.connect(db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM projects WHERE id = ?",
            (interrupted_project_id,),
        ).fetchone()[0] == 0
        assert conn.execute(
            """
            SELECT COUNT(*) FROM creator_delivery_import_intents
            WHERE status = 'RECOVERED'
            """
        ).fetchone()[0] == 1
    assert not (tmp_path / "artifact-files" / interrupted_project_id).exists()

    different_export = client.post(
        f"/api/creator/works/{work_id}/deliveries",
        headers=HEADERS,
        json={
            "idempotencyKey": "creator-m7-crash-export-different",
            "variant": "REPRODUCIBLE",
        },
    ).json()["delivery"]
    with pytest.raises(CreatorError) as changed_package:
        CreatorDeliveryService(tmp_path).import_delivery(
            ImportCreatorDeliveryRequest(
                idempotencyKey="creator-m7-crash-import",
                zipBase64=different_export["zipBase64"],
            ),
            importer_subject="subject-m7-second-user",
        )
    assert changed_package.value.code == "CREATOR_IDEMPOTENCY_KEY_REUSED"

    retried = CreatorDeliveryService(tmp_path).import_delivery(
        request,
        importer_subject="subject-m7-second-user",
    )
    assert retried.workspace.work_id == interrupted_project_id
    assert retried.workspace.verification_level == 1
