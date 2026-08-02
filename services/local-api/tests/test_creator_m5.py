from __future__ import annotations

import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.creator.models import CreatorCommand, CreatorCommandRequest
from zhangwen.creator.repository import CreatorRepository
from zhangwen.main import app
from zhangwen.projects.repository import ProjectRepository


HEADERS = {
    "X-Zhangwen-Host": "tauri",
    "X-Zhangwen-Capability-Token": "creator-m5-token",
}


@pytest.fixture(autouse=True)
def _runtime(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    settings.data_dir = tmp_path
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "creator-m5-token")


def _request(version: int, key: str, payload: dict[str, object]) -> CreatorCommandRequest:
    return CreatorCommandRequest.model_validate(
        {"baseProjectVersion": version, "idempotencyKey": key, "payload": payload}
    )


def _work(tmp_path) -> tuple[CreatorRepository, str, str]:
    repository = CreatorRepository(tmp_path)
    workspace = repository.create_work(
        name="结构作品",
        initial_idea="制作带外壳的环境提醒器",
        idempotency_key="creator-m5-create",
        selected_hardware_ids=[],
    )
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_GOAL,
        _request(
            workspace.project_version,
            "creator-m5-goal",
            {"statement": "制作环境提醒器", "observableBehavior": "外壳固定器件并露出接口", "constraints": ["可 3D 打印"], "successCriteria": ["器件可安装", "接口无遮挡"]},
        ),
    ).workspace
    workspace = repository.execute(
        workspace.work_id,
        CreatorCommand.CONFIRM_SOLUTION,
        _request(
            workspace.project_version,
            "creator-m5-solution",
            {
                "summary": "带可打印外壳的提醒器",
                "logic": "传感器超限时提醒",
                "hardware": "主控、传感器和显示",
                "software": "采样与提醒逻辑",
                "structure": "带 2mm 壁厚、USB 开孔和螺柱的外壳",
                "simulation": "输入超限时输出提醒",
                "safety": "低压供电",
                "bom": [],
                "ioMap": [],
                "acceptanceScenarios": [{"title": "提醒行为", "required": True, "simulationExpected": "输出变化", "physicalExpected": "真机提醒"}],
            },
        ),
    ).workspace
    assert workspace.current_solution is not None
    return repository, workspace.work_id, workspace.current_solution.id


def _seed_structure_files(tmp_path, project_id: str, roles: list[str]) -> str:
    db_path = ProjectRepository(tmp_path).db_path
    now = "2026-07-31T00:00:00+00:00"
    revision_id = "cad-revision-m5"
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO tool_jobs (id, project_id, kind, status, request_hash, request_json, progress, result_artifact_ids_json, created_at, updated_at) VALUES (?, ?, 'CAD_INTENT', 'SUCCEEDED', ?, '{}', 100, '[]', ?, ?)",
            ("tool-m5", project_id, "1" * 64, now, now),
        )
        conn.execute(
            "INSERT INTO artifacts (id, project_id, title, kind, status, source_agent_id, current_version_id, created_at, updated_at) VALUES (?, ?, '结构模型', 'MODEL_3D', 'APPROVED', 'cad-agent', ?, ?, ?)",
            ("artifact-m5", project_id, "artifact-version-m5", now, now),
        )
        conn.execute(
            "INSERT INTO artifact_versions (id, artifact_id, project_id, version, status, mime_type, preview_json, dependencies_json, checksum, created_at, confirmed_at) VALUES (?, ?, ?, 1, 'APPROVED', 'model/gltf-binary', '{}', '[]', ?, ?, ?)",
            ("artifact-version-m5", "artifact-m5", project_id, "2" * 64, now, now),
        )
        conn.execute(
            "INSERT INTO cad_intent_revisions (id, project_id, tool_job_id, intent_summary, route_action, status, source_sha256, object_index_json, artifact_id, artifact_version_id, created_at, confirmed_at) VALUES (?, ?, ?, '生成可打印外壳', 'draft', 'CONFIRMED', ?, '[]', ?, ?, ?, ?)",
            (revision_id, project_id, "tool-m5", "3" * 64, "artifact-m5", "artifact-version-m5", now, now),
        )
        for index, role in enumerate(roles):
            file_name, storage_key, mime_type, payload, sha256 = _structure_file(
                tmp_path, index, role
            )
            conn.execute(
                "INSERT INTO artifact_files (id, artifact_id, artifact_version_id, project_id, role, file_name, storage_key, mime_type, byte_size, sha256, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"file-m5-{index}", "artifact-m5", "artifact-version-m5", project_id, role, file_name, storage_key, mime_type, len(payload), sha256, now),
            )
    return revision_id


def _structure_file(
    tmp_path, index: int, role: str
) -> tuple[str, str, str, bytes, str]:
    metadata = {
        "GLB_PREVIEW": ("glb", "model/gltf-binary"),
        "STL_PRINTABLE_PARTS": ("stl", "model/stl"),
        "STEP_ASSEMBLY": ("step", "model/step"),
        "STEP_PRINTABLE_PARTS": ("step", "model/step"),
        "MANIFEST": ("json", "application/json"),
    }
    extension, mime_type = metadata[role]
    file_name = f"model-{index}.{extension}"
    storage_key = f"cad/m5/{file_name}"
    payload = f"{role}:{index}".encode()
    target = tmp_path / "artifact-files" / "cad" / "m5" / file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    return (
        file_name,
        storage_key,
        mime_type,
        payload,
        hashlib.sha256(payload).hexdigest(),
    )


def test_structure_check_requires_real_glb_stl_step_and_manifest(tmp_path) -> None:
    repository, project_id, solution_id = _work(tmp_path)
    revision_id = _seed_structure_files(tmp_path, project_id, ["GLB_PREVIEW", "MANIFEST"])
    workspace = repository.workspace(project_id)
    body = {
        "baseProjectVersion": workspace.project_version,
        "idempotencyKey": "creator-m5-structure-check",
        "payload": {
            "passed": True,
            "summary": "结构制造文件检查通过",
            "sourceId": revision_id,
            "bindings": {"solutionRevisionId": solution_id, "structureRevisionId": revision_id},
        },
    }
    missing = TestClient(app).post(
        f"/api/creator/works/{project_id}/commands/RECORD_STRUCTURE_CHECK",
        headers=HEADERS,
        json=body,
    )
    assert missing.status_code == 409
    assert missing.json()["detail"]["code"] == "CREATOR_STRUCTURE_OUTPUTS_INCOMPLETE"

    db_path = ProjectRepository(tmp_path).db_path
    now = "2026-07-31T00:00:01+00:00"
    with sqlite3.connect(db_path) as conn:
        for index, role in enumerate(["STL_PRINTABLE_PARTS", "STEP_ASSEMBLY"], start=10):
            file_name, storage_key, mime_type, payload, sha256 = _structure_file(
                tmp_path, index, role
            )
            conn.execute(
                "INSERT INTO artifact_files (id, artifact_id, artifact_version_id, project_id, role, file_name, storage_key, mime_type, byte_size, sha256, created_at) VALUES (?, 'artifact-m5', 'artifact-version-m5', ?, ?, ?, ?, ?, ?, ?, ?)",
                (f"file-m5-{index}", project_id, role, file_name, storage_key, mime_type, len(payload), sha256, now),
            )
    passed = TestClient(app).post(
        f"/api/creator/works/{project_id}/commands/RECORD_STRUCTURE_CHECK",
        headers=HEADERS,
        json={**body, "idempotencyKey": "creator-m5-structure-pass"},
    )
    assert passed.status_code == 200, passed.json()
    structure_stage = next(item for item in passed.json()["workspace"]["stages"] if item["stage"] == "STRUCTURE_3D")
    assert structure_stage["status"] == "PASSED"
    evidence = next(item for item in passed.json()["workspace"]["evidence"] if item["kind"] == "STRUCTURE_CHECK")
    assert evidence["sourceId"] == revision_id


def test_structure_check_rejects_tampered_artifact_file(tmp_path) -> None:
    repository, project_id, solution_id = _work(tmp_path)
    revision_id = _seed_structure_files(
        tmp_path,
        project_id,
        ["GLB_PREVIEW", "STL_PRINTABLE_PARTS", "STEP_ASSEMBLY", "MANIFEST"],
    )
    (tmp_path / "artifact-files" / "cad" / "m5" / "model-0.glb").write_bytes(
        b"tampered"
    )
    workspace = repository.workspace(project_id)
    response = TestClient(app).post(
        f"/api/creator/works/{project_id}/commands/RECORD_STRUCTURE_CHECK",
        headers=HEADERS,
        json={
            "baseProjectVersion": workspace.project_version,
            "idempotencyKey": "creator-m5-structure-tampered",
            "payload": {
                "passed": True,
                "summary": "不应接受被篡改的结构文件",
                "sourceId": revision_id,
                "bindings": {
                    "solutionRevisionId": solution_id,
                    "structureRevisionId": revision_id,
                },
            },
        },
    )
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "CREATOR_STRUCTURE_OUTPUTS_INVALID"
