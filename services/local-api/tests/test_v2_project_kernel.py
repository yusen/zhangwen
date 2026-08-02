from __future__ import annotations

import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest
from fastapi.testclient import TestClient

from zhangwen.config import settings
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from zhangwen.v2.kernel import ProjectKernel, ProjectKernelError
from zhangwen.v2.models import CreateChangeSetRequest, CreateReleaseRequest


def _project(data_dir):
    workspace = ProjectRepository(data_dir).create_project(
        "V2 测试项目",
        "做一个可以自由修改结构的自动浇花装置",
        selected_expert_types=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    return workspace.project.id


def _change_request(*, base: int = 0, key: str = "kernel-test-0001"):
    return CreateChangeSetRequest.model_validate(
        {
            "baseProjectVersion": base,
            "ownerDomain": "problem_guide",
            "intentSummary": "切换探索模式并记录目标湿度",
            "operations": [
                {"op": "SET_PROJECT_MODE", "path": "/mode", "value": "EXPLORATION"},
                {
                    "op": "UPSERT_FACT",
                    "path": "/facts/requirements/target_moisture",
                    "value": 45,
                },
            ],
            "idempotencyKey": key,
        }
    )


def test_project_state_is_a_rebuildable_hashed_projection(tmp_path) -> None:
    project_id = _project(tmp_path)
    kernel = ProjectKernel(tmp_path)

    first = kernel.project_state(project_id)
    second = kernel.project_state(project_id)

    assert first["schemaVersion"] == 1
    assert first["projectVersion"] == 0
    assert len(first["projectionHash"]) == 64
    # projectedAt is observable metadata but is excluded from the semantic hash;
    # the stored v0 row is replaced rather than creating competing truth rows.
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) FROM project_state_snapshots WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0]
    assert count == 1
    assert second["projectId"] == first["projectId"]
    assert second["projectionHash"] == first["projectionHash"]


def test_existing_v1_project_is_imported_as_one_idempotent_v2_baseline(tmp_path) -> None:
    project_id = _project(tmp_path)
    repository = ProjectRepository(tmp_path)
    repository.replace_preferred_hardware(project_id, ["hw_seed_unihiker_k10"])
    solutions = SolutionRepository(repository.db_path)
    draft = solutions.create_solution(
        project_id,
        [
            SolutionSection(
                id="goal",
                title="项目目标",
                content="制作一台可更新照片的 K10 电子相册。",
            ),
            SolutionSection(
                id="hardware",
                title="硬件方案",
                content="使用行空板 K10。",
            ),
        ],
    )
    solutions.confirm_solution(project_id, draft.id)

    kernel = ProjectKernel(tmp_path)
    first = kernel.project_state(project_id)
    second = kernel.project_state(project_id)
    versions = kernel.list_versions(project_id)

    assert first["projectVersion"] == second["projectVersion"] == 1
    assert first["currentRecommendation"] == "制作一台可更新照片的 K10 电子相册。"
    preferred = next(item for item in first["facts"] if item["key"] == "preferred_hardware")
    assert preferred["label"] == "项目硬件"
    assert preferred["displayValue"] == "行空板 K10 · 硬件组合校验通过。"
    assert preferred["value"]["components"][0]["id"] == "hw_seed_unihiker_k10"
    assert first["capabilityCoverage"]["coveragePercent"] == 100
    assert len(versions) == 1
    assert versions[0]["stateHash"] == first["projectionHash"]
    assert versions[0]["changeSetId"] is None
    assert versions[0]["validationSummary"][0]["code"] == "V1_BASELINE_IMPORTED"

    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == 1


def test_project_state_presents_clarification_fact_as_question_and_answer(tmp_path) -> None:
    project_id = _project(tmp_path)
    repository = ProjectRepository(tmp_path)
    workspace = repository.get_workspace(project_id)
    conversation_id = workspace.expertConversations[0].id
    source_id = "msg_question_source"
    answer_id = "msg_question_answer"
    now = "2026-07-26T00:00:00+00:00"
    source_payload = {
        "type": "clarification",
        "questions": [
            {
                "id": "q_1",
                "text": "你希望如何获取照片？",
                "options": [
                    {"id": "camera", "label": "用板载摄像头拍摄"},
                    {"id": "sd_card", "label": "从 TF 卡读取"},
                ],
            }
        ],
    }
    with repository._connect() as conn:
        for message_id, content, payload, metadata in (
            (source_id, "请选择照片来源", source_payload, {}),
            (
                answer_id,
                "已完成本轮需求确认：\n你希望如何获取照片？：用板载摄像头拍摄",
                None,
                {"replyToMessageId": source_id},
            ),
        ):
            conn.execute(
                """
                INSERT INTO messages (
                  id, conversation_id, project_id, role, content, reasoning_content,
                  status, model, error_json, usage_json, structured_payload_json,
                  metadata_json, created_at, updated_at
                ) VALUES (?, ?, ?, 'assistant', ?, NULL, 'COMPLETED', NULL, NULL,
                          NULL, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    conversation_id,
                    project_id,
                    content,
                    json.dumps(payload, ensure_ascii=False) if payload else None,
                    json.dumps(metadata, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        conn.execute(
            """
            INSERT INTO project_shared_facts (
              id, project_id, field, key, value_json, status, source_type,
              source_id, source_expert_id, proposed_by_expert_type,
              confirmed_by, confirmed_at, superseded_by,
              affects_artifact_ids_json, created_at, updated_at
            ) VALUES ('fact_q1', ?, 'clarification_answer', 'q_1', ?, 'confirmed',
                      'user', ?, NULL, 'problem_guide', 'user', ?, NULL, '[]', ?, ?)
            """,
            (
                project_id,
                json.dumps(
                    {"selectedOptionIds": ["camera"], "textInput": None},
                    ensure_ascii=False,
                ),
                answer_id,
                now,
                now,
                now,
            ),
        )

    state = ProjectKernel(tmp_path).project_state(project_id)
    fact = next(item for item in state["facts"] if item["key"] == "q_1")
    assert fact["label"] == "你希望如何获取照片？"
    assert fact["displayValue"] == "用板载摄像头拍摄"


def test_parallel_v2_reads_import_only_one_v1_baseline(tmp_path) -> None:
    project_id = _project(tmp_path)
    repository = ProjectRepository(tmp_path)
    repository.replace_preferred_hardware(project_id, ["hw_seed_unihiker_k10"])

    with ThreadPoolExecutor(max_workers=2) as pool:
        state_future = pool.submit(ProjectKernel(tmp_path).project_state, project_id)
        versions_future = pool.submit(ProjectKernel(tmp_path).list_versions, project_id)
        state = state_future.result()
        versions = versions_future.result()

    assert state["projectVersion"] == 1
    assert len(versions) == 1
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM project_versions WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == 1


def test_change_set_commit_is_atomic_idempotent_and_versioned(tmp_path) -> None:
    project_id = _project(tmp_path)
    kernel = ProjectKernel(tmp_path)

    proposed = kernel.create_change_set(project_id, _change_request())
    replay = kernel.create_change_set(project_id, _change_request())
    assert replay["id"] == proposed["id"]
    assert proposed["status"] == "READY"
    assert {item["severity"] for item in proposed["validationResults"]} == {"PASS"}

    confirmed = kernel.confirm_change_set(project_id, proposed["id"])
    assert confirmed["status"] == "CONFIRMED"
    version = kernel.commit_change_set(project_id, proposed["id"])
    repeated = kernel.commit_change_set(project_id, proposed["id"])
    assert version == repeated
    assert version["version"] == 1

    state = kernel.project_state(project_id)
    assert state["projectVersion"] == 1
    assert state["mode"] == "EXPLORATION"
    assert any(
        item["key"] == "target_moisture" and item["value"] == 45
        for item in state["facts"]
    )

    release = kernel.create_release(
        project_id, CreateReleaseRequest(name="工程预览版", notes="自动测试")
    )
    assert release["projectVersionId"] == version["id"]
    assert len(release["manifestHash"]) == 64


def test_change_set_rejects_stale_base_version(tmp_path) -> None:
    project_id = _project(tmp_path)
    kernel = ProjectKernel(tmp_path)
    first = kernel.create_change_set(project_id, _change_request())
    kernel.confirm_change_set(project_id, first["id"])
    kernel.commit_change_set(project_id, first["id"])

    with pytest.raises(ProjectKernelError) as exc_info:
        kernel.create_change_set(
            project_id, _change_request(base=0, key="kernel-stale-0002")
        )
    assert exc_info.value.code == "PROJECT_VERSION_CONFLICT"
    assert exc_info.value.status_code == 409


def test_capability_facade_adapts_existing_sources_without_copying_truth(tmp_path) -> None:
    project_id = _project(tmp_path)
    kernel = ProjectKernel(tmp_path)

    capabilities = kernel.list_capabilities(project_id)
    coverage = kernel.capability_coverage(project_id)

    assert any(item["sourceType"] == "hardware_component" for item in capabilities)
    assert any(item["sourceId"] == "cad.local" for item in capabilities)
    assert coverage["coveragePercent"] == 100


def test_v26_database_migrates_forward_with_backup(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    v2_tables = [
        "project_state_snapshots",
        "project_events",
        "project_change_sets",
        "project_versions",
        "project_releases",
        "capabilities",
        "capability_relations",
        "project_capability_bindings",
        "tool_jobs",
        "local_bridge_sessions",
        "cad_intent_revisions",
    ]
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute("PRAGMA foreign_keys=OFF")
        for table in v2_tables:
            conn.execute(f"DROP TABLE {table}")
        conn.execute("DELETE FROM schema_migration_audit WHERE to_version = 27")
        conn.execute("PRAGMA user_version=26")
        conn.commit()

    migrated = ProjectRepository(tmp_path)
    with sqlite3.connect(migrated.db_path) as conn:
        assert conn.execute("PRAGMA user_version").fetchone()[0] == 31
        names = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
    assert set(v2_tables).issubset(names)
    assert list(
        (tmp_path / "projects" / "backups").glob(
            f"pre-migration-v26-to-v{CURRENT_SCHEMA_VERSION}-*.sqlite3"
        )
    )


def test_v2_api_exposes_state_and_changeset_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    project_id = _project(tmp_path)

    with TestClient(app) as client:
        state = client.get(f"/api/v2/projects/{project_id}/state")
        assert state.status_code == 200
        assert state.json()["state"]["projectVersion"] == 0

        created = client.post(
            f"/api/v2/projects/{project_id}/changesets",
            json=_change_request().model_dump(by_alias=True),
        )
        assert created.status_code == 200
        change_set_id = created.json()["changeSet"]["id"]
        assert client.post(
            f"/api/v2/projects/{project_id}/changesets/{change_set_id}/confirm"
        ).status_code == 200
        committed = client.post(
            f"/api/v2/projects/{project_id}/changesets/{change_set_id}/commit"
        )
        assert committed.status_code == 200
        assert committed.json()["version"]["version"] == 1
