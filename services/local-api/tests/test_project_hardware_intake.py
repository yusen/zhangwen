from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeCredentialStore, SequenceProvider
from tests.hardware_seed_fixtures import seed_legacy_test_components
from zhangwen.chat.idea_flow import _solution_generation_context
from zhangwen.config import settings
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.hardware.component_packages import HardwareComponentPackageRepository
from zhangwen.hardware.hardware_skills import HardwareSkillRepository
from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareSkillSpecification,
)
from zhangwen.hardware.repository import HardwareRepository
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.main import app
from zhangwen.projects import router as projects_router
from zhangwen.projects.errors import ProjectValidationError
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


def _router_json() -> str:
    return json.dumps(
        {
            "intent": "technical_implementation",
            "projectName": "Preferred hardware project",
            "initialExpert": "smart_engineer",
            "recommendedExperts": ["smart_engineer", "structure_engineer"],
            "confidence": 0.96,
            "reason": "The project needs hardware and structure work.",
            "requiresClarification": False,
        }
    )


def _router_result() -> dict[str, object]:
    return json.loads(_router_json())


def _seed_component(repository: ProjectRepository, component_id: str):
    seed_default_components(repository.db_path)
    seed_legacy_test_components(repository.db_path, (component_id,))
    return HardwareRepository(repository.db_path).get_component(component_id)


@pytest.fixture(autouse=True)
def _preserve_explicit_legacy_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", "1")


@pytest.mark.parametrize(
    "selected_ids",
    [
        ["hw_duplicate", "hw_duplicate"],
        [f"hw_{index}" for index in range(13)],
        [""],
        [" hw_with_outer_space"],
    ],
)
@pytest.mark.parametrize(
    ("endpoint", "idea_field"),
    [
        ("/api/projects/suggest", "text"),
        ("/api/projects", "initialIdea"),
    ],
)
def test_selected_hardware_ids_reject_invalid_request_shapes_before_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    selected_ids: list[str],
    endpoint: str,
    idea_field: str,
) -> None:
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        endpoint,
        json={idea_field: "Build a sensor project", "selectedHardwareIds": selected_ids},
    )

    assert response.status_code == 422
    assert provider.calls == 0


def test_suggest_rejects_unknown_and_archived_hardware_before_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    archived = _seed_component(repository, "hw_seed_dht22")
    HardwareRepository(repository.db_path).archive_component(archived.id)
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)
    client = TestClient(app)

    unknown_response = client.post(
        "/api/projects/suggest",
        json={
            "text": "Build a sensor project",
            "selectedHardwareIds": ["hw_missing"],
        },
    )
    archived_response = client.post(
        "/api/projects/suggest",
        json={
            "text": "Build a sensor project",
            "selectedHardwareIds": [archived.id],
        },
    )

    assert unknown_response.status_code == 422
    assert archived_response.status_code == 422
    assert unknown_response.json()["detail"]["code"] == "PROJECT_VALIDATION_FAILED"
    assert archived_response.json()["detail"]["code"] == "PROJECT_VALIDATION_FAILED"
    assert provider.calls == 0


def test_create_with_router_result_rejects_invalid_hardware_without_partial_project(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    repository = ProjectRepository(tmp_path)

    response = TestClient(app).post(
        "/api/projects",
        json={
            "initialIdea": "Build a sensor project",
            "selectedHardwareIds": ["hw_missing"],
            "routerResult": _router_result(),
        },
    )

    assert response.status_code == 422
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_shared_facts").fetchone()[0] == 0


def test_suggest_and_create_send_the_same_controlled_hardware_summary(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    first_component = _seed_component(repository, "hw_seed_dht22")
    seed_default_components(repository.db_path)
    hardware_skills = HardwareSkillRepository(tmp_path, repository.db_path)
    hardware_skills.migrate_legacy_rows()
    first_component = hardware_skills.get_active_component(first_component.id)
    second_component = hardware_skills.get_active_component("hw_seed_unihiker_k10")
    provider = SequenceProvider([_router_json(), _router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)
    client = TestClient(app)
    payload = {
        "initialIdea": "Build a classroom reminder",
        "selectedHardwareIds": [first_component.id, second_component.id],
    }

    suggest_response = client.post("/api/projects/suggest", json=payload)
    create_response = client.post("/api/projects", json=payload)

    assert suggest_response.status_code == 200
    assert create_response.status_code == 200
    assert provider.calls == 2
    selected_hardware_warnings = suggest_response.json()["suggestion"][
        "selectedHardwareWarnings"
    ]
    assert selected_hardware_warnings
    assert all(
        any("\u4e00" <= character <= "\u9fff" for character in warning)
        for warning in selected_hardware_warnings
    )
    expected_summaries = [
        json.dumps(
            {
                "componentId": component.id,
                "name": component.name,
                "category": component.category.value,
                "voltage": component.electrical.voltage,
                "voltageMin": (
                    component.electrical.voltage
                    if component.electrical.voltageMin is None
                    else component.electrical.voltageMin
                ),
                "voltageMax": (
                    component.electrical.voltage
                    if component.electrical.voltageMax is None
                    else component.electrical.voltageMax
                ),
                "supplyVoltages": component.electrical.supplyVoltages,
                "logicLevel": component.electrical.logicLevel,
                "communicationProtocol": component.electrical.communicationProtocol,
                "skillName": component.skillName,
                "skillRevision": component.skillRevision,
                "updatedAt": component.updatedAt,
            },
            ensure_ascii=False,
        )
        for component in (first_component, second_component)
    ]
    prompts = [request.messages[-1].content for request in provider.requests]
    assert prompts[0] == prompts[1]
    assert all(
        all(summary in prompt for summary in expected_summaries)
        for prompt in prompts
    )
    assert all(
        prompt.index(expected_summaries[0]) < prompt.index(expected_summaries[1])
        for prompt in prompts
    )
    assert all('"overall": "WARNING"' in prompt for prompt in prompts)
    assert all("stock" not in prompt for prompt in prompts)
    assert all("price" not in prompt for prompt in prompts)
    assert all("notes" not in prompt for prompt in prompts)


def test_k10_and_dfr0026_voltage_range_pass_project_validation(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    seed_default_components(repository.db_path)
    hardware_skills = HardwareSkillRepository(tmp_path, repository.db_path)
    hardware_skills.migrate_legacy_rows()
    k10 = hardware_skills.get_active_component("hw_seed_unihiker_k10")
    hardware_skills.create_skill(
        HardwareSkillSpecification(
            componentId="hw_test_dfrobot_dfr0026",
            name="DFRobot DFR0026 模拟环境光线传感器",
            category=HardwareCategory.SENSOR,
            electrical=ElectricalProps(
                voltage=3.3,
                voltageMin=3.0,
                voltageMax=5.0,
                supplyVoltages=[],
                logicLevel=3.3,
                peakCurrent=0.0,
                communicationProtocol="ANALOG",
                supportedMCUs=["unihiker-k10"],
                driverName="machine.ADC",
                firmwareRequirement="MicroPython",
            ),
            safetyTags=["analog-signal"],
            notes="允许 3.0V 至 5.0V 供电，K10 集成时推荐使用 3.3V 电源轨。",
        ),
        skill_name="dfr0026-project-validation",
        description="项目创建链路的 DFR0026 电源轨回归样例。",
    )
    dfr0026 = hardware_skills.get_active_component("hw_test_dfrobot_dfr0026")
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)
    client = TestClient(app)
    selected_ids = [k10.id, dfr0026.id]

    suggest_response = client.post(
        "/api/projects/suggest",
        json={
            "text": "使用行空板 K10 和 DFR0026 制作环境光项目",
            "selectedHardwareIds": selected_ids,
        },
    )
    create_response = client.post(
        "/api/projects",
        json={
            "initialIdea": "使用行空板 K10 和 DFR0026 制作环境光项目",
            "selectedHardwareIds": selected_ids,
            "routerResult": _router_result(),
        },
    )
    client.close()

    assert suggest_response.status_code == 200
    assert suggest_response.json()["suggestion"]["selectedHardwareWarnings"] == []
    assert create_response.status_code == 200
    assert provider.calls == 1
    project_id = create_response.json()["workspace"]["project"]["id"]
    with sqlite3.connect(repository.db_path) as conn:
        row = conn.execute(
            """
            SELECT value_json FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
              AND status = 'confirmed'
            """,
            (project_id,),
        ).fetchone()
    assert row is not None
    selected = json.loads(row[0])
    assert [item["id"] for item in selected["components"]] == selected_ids


def test_explicit_empty_selection_allows_suggest_and_create(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    provider = SequenceProvider([_router_json(), _router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)
    payload = {
        "initialIdea": "Build a software-first classroom project",
        "selectedHardwareIds": [],
    }
    client = TestClient(app)

    suggest_response = client.post("/api/projects/suggest", json=payload)
    create_response = client.post("/api/projects", json=payload)

    assert suggest_response.status_code == 200
    assert create_response.status_code == 200
    assert provider.calls == 2
    assert suggest_response.json()["suggestion"]["selectedHardwareWarnings"] == []
    project_id = create_response.json()["workspace"]["project"]["id"]
    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT value_json, status, source_type, confirmed_by, confirmed_at
            FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
            """,
            (project_id,),
        ).fetchall()

    assert len(rows) == 1
    assert json.loads(rows[0]["value_json"]) == {
        "policy": "prefer_selected_and_fill_gaps",
        "components": [],
    }
    assert rows[0]["status"] == "confirmed"
    assert rows[0]["source_type"] == "user"
    assert rows[0]["confirmed_by"] == "user"
    assert rows[0]["confirmed_at"]


def test_repository_persists_confirmed_preferred_hardware_fact_and_is_idempotent(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    hardware_skills = HardwareSkillRepository(tmp_path, repository.db_path)
    hardware_skills.ensure_component_migrated(component.id)
    component = hardware_skills.get_active_component(component.id)
    idea = "Build a classroom climate monitor"

    first = repository.create_project_from_idea(
        idea=idea,
        project_name="Climate monitor",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
        idempotency_key="preferred-hardware-create",
    )
    second = repository.create_project_from_idea(
        idea="This replay must not create another project",
        project_name="Ignored replay name",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
        idempotency_key="preferred-hardware-create",
    )

    assert second.project.id == first.project.id
    assert first.conversation.messages[0].content == idea
    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
            """,
            (first.project.id,),
        ).fetchall()
        project_count = conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]

    assert project_count == 1
    assert len(rows) == 1
    fact = rows[0]
    assert fact["key"] == "preferred_hardware"
    assert fact["status"] == "confirmed"
    assert fact["source_type"] == "user"
    assert fact["confirmed_by"] == "user"
    assert fact["confirmed_at"]
    fact_value = json.loads(fact["value_json"])
    assert fact_value["policy"] == "prefer_selected_and_fill_gaps"
    assert fact_value["components"] == [
            {
                "id": component.id,
                "name": component.name,
                "category": component.category.value,
                "skillName": component.skillName,
                "skillRevision": component.skillRevision,
                "updatedAt": component.updatedAt,
            }
        ]
    assert fact_value["validation"]["overall"] == "WARNING"
    assert fact_value["validation"]["warnings"]


def test_repository_rejects_unknown_hardware_inside_creation_transaction(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)

    with pytest.raises(ProjectValidationError):
        repository.create_project_from_idea(
            idea="Build a sensor project",
            project_name="Invalid hardware project",
            initial_expert=ExpertType.SMART_ENGINEER,
            participating_experts=[ExpertType.SMART_ENGINEER],
            selected_hardware_ids=["hw_missing"],
        )

    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_shared_facts").fetchone()[0] == 0


def test_repository_rejects_archived_hardware_inside_creation_transaction(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    HardwareRepository(repository.db_path).archive_component(component.id)

    with pytest.raises(ProjectValidationError):
        repository.create_project_from_idea(
            idea="Build a sensor project",
            project_name="Archived hardware project",
            initial_expert=ExpertType.SMART_ENGINEER,
            participating_experts=[ExpertType.SMART_ENGINEER],
            selected_hardware_ids=[component.id],
        )

    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM project_shared_facts").fetchone()[0] == 0


def test_empty_selection_still_persists_confirmed_preferred_hardware_fact(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)

    workspace = repository.create_project_from_idea(
        idea="Build a software-only prototype",
        project_name="No initial hardware",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )

    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            """
            SELECT value_json, status, confirmed_by
            FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
            """,
            (workspace.project.id,),
        ).fetchone()

    assert row is not None
    assert json.loads(row["value_json"]) == {
        "policy": "prefer_selected_and_fill_gaps",
        "components": [],
    }
    assert row["status"] == "confirmed"
    assert row["confirmed_by"] == "user"


def test_rule_engine_failure_blocks_suggest_and_create_before_provider_or_write(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    _seed_component(repository, "hw_seed_esp32_s3_devkit")
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)
    payload = {
        "initialIdea": "Build a relay controller",
        "selectedHardwareIds": [
            "hw_seed_esp32_s3_devkit",
            "hw_seed_relay_5v",
        ],
    }
    client = TestClient(app)

    suggest_response = client.post("/api/projects/suggest", json=payload)
    create_response = client.post("/api/projects", json=payload)

    assert suggest_response.status_code == 422
    assert create_response.status_code == 422
    assert provider.calls == 0
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_preferred_hardware_is_shared_without_repeating_its_name_in_later_turns(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a compact classroom device",
        project_name="Shared preferred hardware",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
        selected_hardware_ids=[component.id],
    )

    contexts = [
        ContextAssembler(repository.db_path).assemble(
            ContextAssemblyInput(
                projectId=workspace.project.id,
                expert=expert,
                userMessage="Continue with the next project step.",
            )
        )
        for expert in (
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        )
    ]
    selected_entries = [
        [
            item
            for item in context.publicKnowledge
            if item.get("componentId") == component.id
        ]
        for context in contexts
    ]

    assert all(len(entries) == 1 for entries in selected_entries)
    assert all(entries[0]["source"] == "preferred_project_hardware" for entries in selected_entries)
    assert all(entries[0]["selectedByUser"] is True for entries in selected_entries)
    assert all(entries[0]["selectionValidation"]["overall"] == "WARNING" for entries in selected_entries)
    assert all(entries[0]["skillName"] for entries in selected_entries)
    assert all(entries[0]["skillRevision"] for entries in selected_entries)
    assert all("hardwareSkillMarkdown" in entries[0] for entries in selected_entries)
    assert all("componentPackageMarkdown" in entries[0] for entries in selected_entries)
    assert selected_entries[0][0] == selected_entries[1][0] == selected_entries[2][0]
    policies = [context.hardwareKnowledgePolicy for context in contexts]
    assert all(
        policy["priorityOrder"]
        == [
            "preferred_project_hardware",
            "local_hardware_library",
            "missing_capability",
        ]
        for policy in policies
    )
    assert all(
        policy["selectedComponents"][0]["componentId"] == component.id
        for policy in policies
    )
    assert policies[0] == policies[1] == policies[2]


def test_project_hardware_update_supersedes_previous_selection_and_refreshes_context(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    first = _seed_component(repository, "hw_seed_dht22")
    second = _seed_component(repository, "hw_seed_bme280")
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment station",
        project_name="Mutable project hardware",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[first.id],
    )
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    response = TestClient(app).put(
        f"/api/projects/{workspace.project.id}/hardware",
        json={"selectedHardwareIds": [second.id]},
    )

    assert response.status_code == 200
    assert response.json()["workspace"]["project"]["id"] == workspace.project.id
    assert isinstance(response.json()["selectedHardwareWarnings"], list)
    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT id, value_json, status, superseded_by, confirmed_by
            FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
            ORDER BY created_at
            """,
            (workspace.project.id,),
        ).fetchall()

    assert len(rows) == 2
    assert rows[0]["status"] == "superseded"
    assert rows[0]["superseded_by"] == rows[1]["id"]
    assert rows[1]["status"] == "confirmed"
    assert rows[1]["confirmed_by"] == "user"
    assert [
        item["id"] for item in json.loads(rows[1]["value_json"])["components"]
    ] == [second.id]

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="Continue planning without repeating hardware names.",
        )
    )
    selected_ids = {
        item["componentId"]
        for item in context.publicKnowledge
        if item.get("selectedByUser") is True
    }
    assert selected_ids == {second.id}


def test_invalid_project_hardware_update_preserves_current_confirmed_fact(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a sensor project",
        project_name="Protected project hardware",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
    )
    monkeypatch.setattr(settings, "data_dir", tmp_path)

    response = TestClient(app).put(
        f"/api/projects/{workspace.project.id}/hardware",
        json={"selectedHardwareIds": ["hw_missing"]},
    )

    assert response.status_code == 422
    with sqlite3.connect(repository.db_path) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT value_json, status
            FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
            """,
            (workspace.project.id,),
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["status"] == "confirmed"
    assert json.loads(rows[0]["value_json"])["components"][0]["id"] == component.id


def test_legacy_component_markdown_overlay_is_not_a_selected_hardware_authority(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    packages = HardwareComponentPackageRepository(
        tmp_path,
        HardwareRepository(repository.db_path),
    )
    package = packages.get_package(component.id)
    marker = "PROJECT_SELECTED_HARDWARE_OVERLAY"
    packages.update_file(
        component.id,
        path="docs/integration.md",
        content=f"# Integration\n\n{marker}\n",
        expected_revision=package.revision,
    )
    workspace = repository.create_project_from_idea(
        idea="Build a compact classroom device",
        project_name="Selected hardware Markdown",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="Continue with implementation.",
        )
    )
    selected = next(
        item
        for item in context.publicKnowledge
        if item.get("componentId") == component.id
    )

    assert marker not in selected["hardwareSkillMarkdown"]
    assert selected["componentPackageMarkdown"] == selected["hardwareSkillMarkdown"]
    assert selected["skillName"]
    assert selected["skillRevision"]


def test_related_public_hardware_ignores_legacy_markdown_overlay_without_selection(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    packages = HardwareComponentPackageRepository(
        tmp_path,
        HardwareRepository(repository.db_path),
    )
    package = packages.get_package(component.id)
    marker = "LATEST_RELATED_PUBLIC_KNOWLEDGE_OVERLAY"
    packages.update_file(
        component.id,
        path="docs/integration.md",
        content=f"# DHT22 Integration\n\n{marker}\n",
        expected_revision=package.revision,
    )
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment project",
        project_name="Related public knowledge Markdown",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[],
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="Use the DHT22 sensor in the next implementation step.",
        )
    )
    related = next(
        item
        for item in context.publicKnowledge
        if item.get("componentId") == component.id
    )

    assert related["source"] == "local_hardware_library"
    assert marker not in related["hardwareSkillMarkdown"]
    assert related["componentPackageMarkdown"] == related["hardwareSkillMarkdown"]


def test_solution_context_contains_modern_fact_and_only_fill_gaps_rule(tmp_path) -> None:
    repository = ProjectRepository(tmp_path)
    component = _seed_component(repository, "hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a compact classroom device",
        project_name="Solution preferred hardware",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
    )

    message = _solution_generation_context(repository, workspace.project.id)[0]
    payload = json.loads(message.content[message.content.index("{") :])

    assert any(
        fact["field"] == "preferred_hardware"
        and fact["status"] == "confirmed"
        for fact in payload["confirmedFacts"]
    )
    assert payload["preferredHardware"][0]["componentId"] == component.id
    assert payload["preferredHardware"][0]["selectedByUser"] is True
    assert "用户已有" in payload["preferredHardwareRule"]
    assert "只补充功能缺口" in payload["preferredHardwareRule"]
    assert "不得" in payload["preferredHardwareRule"]


def test_solution_context_prioritizes_active_library_when_selection_is_empty(
    tmp_path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="用本地硬件制作电子相册",
        project_name="Local library first",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )

    message = _solution_generation_context(repository, workspace.project.id)[0]
    payload = json.loads(message.content[message.content.index("{") :])

    assert payload["preferredHardware"] == []
    assert payload["localHardwareLibrary"][0]["name"] == "行空板 K10"
    assert payload["hardwareKnowledgePolicy"]["priorityOrder"] == [
        "preferred_project_hardware",
        "local_hardware_library",
        "missing_capability",
    ]
    assert "必须先评估" in payload["preferredHardwareRule"]
    assert "本地 ACTIVE" in payload["preferredHardwareRule"]
