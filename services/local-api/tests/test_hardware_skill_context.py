from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeCredentialStore, SequenceProvider, fake_proposal_sections
from tests.hardware_seed_fixtures import seed_legacy_test_components
from zhangwen.config import settings
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.hardware.hardware_skills import (
    HardwareSkillNotFoundError,
    HardwareSkillRepository,
    HardwareSkillValidationError,
)
from zhangwen.hardware.models import HardwareSkillDraftSource
from zhangwen.hardware.seeds import seed_default_components
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.main import app
from zhangwen.projects import router as projects_router
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from zhangwen.specs import router as specs_router


def _router_json() -> str:
    return json.dumps(
        {
            "intent": "technical_implementation",
            "projectName": "Hardware Skill project",
            "initialExpert": "smart_engineer",
            "recommendedExperts": [
                "problem_guide",
                "smart_engineer",
                "structure_engineer",
            ],
            "confidence": 0.96,
            "reason": "The project uses a confirmed local Hardware Skill.",
            "requiresClarification": False,
        }
    )


def _hardware_skills(tmp_path: Path) -> tuple[ProjectRepository, HardwareSkillRepository]:
    repository = ProjectRepository(tmp_path)
    seed_default_components(repository.db_path)
    seed_legacy_test_components(repository.db_path)
    skills = HardwareSkillRepository(tmp_path, repository.db_path)
    skills.migrate_legacy_rows()
    return repository, skills


@pytest.fixture(autouse=True)
def _preserve_explicit_legacy_fixtures(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE", "1")


def test_project_routing_uses_skill_snapshot_after_sqlite_projection_is_mutated(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    component = skills.get_active_component("hw_seed_dht22")
    corrupted = component.electrical.model_dump(mode="json")
    corrupted["voltage"] = 99.0
    with sqlite3.connect(repository.db_path) as conn:
        conn.execute(
            "UPDATE hardware_components SET electrical_json = ?, notes = ? WHERE id = ?",
            (json.dumps(corrupted), "SQLITE_PROJECTION_MUST_NOT_WIN", component.id),
        )

    provider = SequenceProvider([_router_json(), _router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)
    payload = {
        "initialIdea": "Build a classroom sensor",
        "selectedHardwareIds": [component.id],
    }
    client = TestClient(app)

    suggested = client.post("/api/projects/suggest", json=payload)
    created = client.post("/api/projects", json=payload)

    assert suggested.status_code == 200
    assert created.status_code == 200
    assert provider.calls == 2
    expected_fields = {
        "componentId": component.id,
        "name": component.name,
        "category": component.category.value,
        "voltage": component.electrical.voltage,
        "logicLevel": component.electrical.logicLevel,
        "communicationProtocol": component.electrical.communicationProtocol,
        "skillName": component.skillName,
        "skillRevision": component.skillRevision,
        "updatedAt": component.updatedAt,
    }
    for request in provider.requests:
        content = request.messages[-1].content
        for field, value in expected_fields.items():
            expected = f'{json.dumps(field)}: {json.dumps(value, ensure_ascii=False)}'
            assert expected in content
        assert "SQLITE_PROJECTION_MUST_NOT_WIN" not in content
        assert '"voltage": 99.0' not in content
    assert all('"voltage": 99.0' not in request.messages[-1].content for request in provider.requests)

    project_id = created.json()["workspace"]["project"]["id"]
    with sqlite3.connect(repository.db_path) as conn:
        row = conn.execute(
            """
            SELECT value_json FROM project_shared_facts
            WHERE project_id = ? AND field = 'preferred_hardware'
            """,
            (project_id,),
        ).fetchone()
    fact = json.loads(row[0])
    assert fact["components"][0]["skillName"] == component.skillName
    assert fact["components"][0]["skillRevision"] == component.skillRevision


def test_saved_active_skill_revision_is_shared_by_all_three_engineers(
    tmp_path: Path,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    component = skills.get_active_component("hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment monitor",
        project_name="Shared Hardware Skill context",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
        selected_hardware_ids=[component.id],
    )
    marker = "ACTIVE_HARDWARE_SKILL_REVISION_SHARED_BY_THREE_ENGINEERS"
    updated = skills.update_file(
        component.skillName,
        path="references/integration.md",
        content=f"# 集成说明\n\n{marker}\n",
        expected_revision=component.skillRevision,
    )

    contexts = [
        ContextAssembler(repository.db_path).assemble(
            ContextAssemblyInput(
                projectId=workspace.project.id,
                expert=expert,
                userMessage="Continue with the current hardware.",
            )
        )
        for expert in (
            ExpertType.PROBLEM_GUIDE,
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        )
    ]
    entries = [
        next(
            item
            for item in context.publicKnowledge
            if item.get("componentId") == component.id
        )
        for context in contexts
    ]

    assert updated.revision != component.skillRevision
    assert all(item["skillName"] == component.skillName for item in entries)
    assert all(item["skillRevision"] == updated.revision for item in entries)
    assert all(marker in item["hardwareSkillMarkdown"] for item in entries)
    assert entries[0] == entries[1] == entries[2]


def test_selected_hardware_skill_keeps_priority_markdown_budget_for_code_generation(
    tmp_path: Path,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    component = skills.get_active_component("hw_seed_dht22")
    tail_marker = "SELECTED_SKILL_TAIL_MUST_REACH_SMART_ENGINEER_CODE_CONTEXT"
    updated = skills.update_file(
        component.skillName,
        path="references/integration.md",
        content="# 代码集成\n\n" + ("integration-fact " * 360) + tail_marker + "\n",
        expected_revision=component.skillRevision,
    )
    workspace = repository.create_project_from_idea(
        idea="Build a DHT22 classroom monitor",
        project_name="Selected skill code context budget",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="Generate the MicroPython code for the selected hardware.",
        )
    )
    selected = next(
        item
        for item in context.publicKnowledge
        if item.get("componentId") == component.id
    )

    assert selected["skillRevision"] == updated.revision
    assert tail_marker in selected["hardwareSkillMarkdown"]


@pytest.mark.parametrize("status", ["DRAFT", "INVALID", "ARCHIVED"])
@pytest.mark.asyncio
async def test_non_active_selected_skill_blocks_runtime_before_provider(
    tmp_path: Path,
    status: str,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    component = skills.get_active_component("hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment monitor",
        project_name="Blocked Hardware Skill context",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
    )
    manifest_path = skills.root / component.skillName / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    expert = workspace.experts[0]
    provider = SequenceProvider([json.dumps({"content": "must not be called"})])

    with pytest.raises(HardwareSkillNotFoundError):
        await ExpertRuntime(repository.db_path).run(
            request=ExpertRuntimeRequest(
                projectId=workspace.project.id,
                projectExpertId=expert.id,
                conversationId=expert.conversationId,
                expertType=ExpertType.SMART_ENGINEER,
                userMessage="Continue implementation.",
                model=LLMModelId.DEEPSEEK_V4_FLASH,
            ),
            provider=provider,
            config=LLMConfig(),
            api_key="fake-test-key",
        )

    assert provider.calls == 0


@pytest.mark.asyncio
async def test_revised_skill_rule_failure_blocks_runtime_before_provider(
    tmp_path: Path,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    mcu = skills.get_active_component("hw_seed_unihiker_k10")
    sensor = skills.get_active_component("hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment monitor",
        project_name="Revised Hardware Skill validation",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[mcu.id, sensor.id],
    )
    detail = skills.get_active_by_component_id(sensor.id)
    specification = next(
        file
        for file in detail.files
        if file.path == "references/specifications.md"
    )
    changed = specification.content.replace('"voltage": 3.3', '"voltage": 12.0')
    assert changed != specification.content
    skills.update_file(
        detail.skillName,
        path=specification.path,
        content=changed,
        expected_revision=detail.revision,
    )
    expert = workspace.experts[0]
    provider = SequenceProvider([json.dumps({"content": "must not be called"})])

    with pytest.raises(HardwareSkillValidationError, match="当前 Skill revision"):
        await ExpertRuntime(repository.db_path).run(
            request=ExpertRuntimeRequest(
                projectId=workspace.project.id,
                projectExpertId=expert.id,
                conversationId=expert.conversationId,
                expertType=ExpertType.SMART_ENGINEER,
                userMessage="Continue implementation.",
                model=LLMModelId.DEEPSEEK_V4_FLASH,
            ),
            provider=provider,
            config=LLMConfig(),
            api_key="fake-test-key",
        )

    assert provider.calls == 0


@pytest.mark.parametrize("status", ["DRAFT", "INVALID", "ARCHIVED"])
def test_non_active_package_is_excluded_from_unselected_engineer_context(
    tmp_path: Path,
    status: str,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    component = skills.get_active_component("hw_seed_dht22")
    manifest_path = skills.root / component.skillName / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["status"] = status
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    assert component.id not in {
        item.id for item in skills.list_active_components()
    }
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment monitor",
        project_name="Non-active Hardware Skill catalog boundary",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="Use a DHT22 sensor.",
        )
    )

    assert component.id not in {
        item.get("componentId") for item in context.publicKnowledge
    }


def test_public_hardware_context_uses_one_validated_catalog_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, _ = _hardware_skills(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment monitor",
        project_name="Single hardware catalog snapshot",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )
    HardwareSkillRepository(tmp_path, repository.db_path).refresh_active_catalog()
    index_calls = 0
    package_load_calls = 0
    original_index = HardwareSkillRepository._component_skill_index
    original_load_package = HardwareSkillRepository._load_package

    def counted_index(self, *, ignore_invalid: bool):
        nonlocal index_calls
        index_calls += 1
        return original_index(self, ignore_invalid=ignore_invalid)

    def reject_per_component_render(self, component_id: str, *, max_chars: int):
        raise AssertionError(
            f"public catalog must not re-index and render {component_id} separately"
        )

    def counted_load_package(self, root: Path):
        nonlocal package_load_calls
        package_load_calls += 1
        return original_load_package(self, root)

    monkeypatch.setattr(
        HardwareSkillRepository,
        "_component_skill_index",
        counted_index,
    )
    monkeypatch.setattr(
        HardwareSkillRepository,
        "render_context",
        reject_per_component_render,
    )
    monkeypatch.setattr(
        HardwareSkillRepository,
        "_load_package",
        counted_load_package,
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="Use a temperature sensor with the local MCU.",
        )
    )

    hardware_items = [
        item for item in context.publicKnowledge if item.get("componentId")
    ]
    assert hardware_items
    assert all(item.get("hardwareSkillMarkdown") for item in hardware_items)
    assert index_calls <= 2
    assert package_load_calls <= 8


def test_context_candidate_index_reuses_until_manual_refresh(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    initial = skills.list_active_context_candidates()
    component = skills.get_active_component("hw_seed_dht22")
    assert (tmp_path / "cache" / "hardware-catalog-v1.json").is_file()

    cached = skills.list_active_context_candidates()
    assert [item.component.skillRevision for item in cached] == [
        item.component.skillRevision for item in initial
    ]

    detail = skills.get_active_by_component_id(component.id)
    integration = next(
        item for item in detail.files if item.path == "references/integration.md"
    )
    updated = skills.update_file(
        detail.skillName,
        path=integration.path,
        content=f"{integration.content.rstrip()}\n\nCACHE_INVALIDATION_MARKER\n",
        expected_revision=detail.revision,
    )
    still_cached = skills.list_active_context_candidates()
    stale_component = next(
        item.component for item in still_cached if item.component.id == component.id
    )
    assert stale_component.skillRevision != updated.revision

    refreshed = skills.refresh_active_catalog()
    refreshed_component = next(
        item.component for item in refreshed if item.component.id == component.id
    )

    assert refreshed_component.skillRevision == updated.revision

    from zhangwen.hardware import hardware_skills as hardware_skills_module

    hardware_skills_module._CONTEXT_CANDIDATE_CACHE.clear()

    def fail_full_scan(*args, **kwargs):
        del args, kwargs
        raise AssertionError("persisted index should avoid a package rescan")

    monkeypatch.setattr(
        HardwareSkillRepository,
        "_validated_catalog_details",
        fail_full_scan,
    )
    restarted = HardwareSkillRepository(tmp_path, repository.db_path)
    persisted = restarted.list_active_context_candidates()
    persisted_component = next(
        item.component for item in persisted if item.component.id == component.id
    )
    assert persisted_component.skillRevision == updated.revision


def test_missing_public_hardware_catalog_degrades_problem_guide_context(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="Build a software-first invention",
        project_name="Missing public catalog fallback",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )

    def missing_catalog(_db_path: Path) -> None:
        raise FileNotFoundError("packaged hardware catalog is missing")

    monkeypatch.setattr(
        "zhangwen.experts.context_assembler.seed_default_components",
        missing_catalog,
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="Help me clarify the idea.",
        )
    )

    assert "Missing public catalog fallback" in context.projectSummary
    assert all(item.get("kind") != "hardware" for item in context.publicKnowledge)


def test_unconfirmed_draft_is_not_visible_to_engineer_context(tmp_path: Path) -> None:
    repository, skills = _hardware_skills(tmp_path)
    draft = skills.create_draft(
        name="Unpublished private draft",
        description="This draft must not enter active engineer context.",
        sources=[
            HardwareSkillDraftSource(
                name="draft.md",
                mediaType="text/markdown",
                content="# Unpublished private draft\n",
            )
        ],
    )
    workspace = repository.create_project_from_idea(
        idea="Build a software-first classroom project",
        project_name="Draft visibility boundary",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )

    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="Continue planning.",
        )
    )
    payload = json.dumps(context.publicKnowledge, ensure_ascii=False)

    assert draft.status == "DRAFT"
    assert draft.id not in payload
    assert "Unpublished private draft" not in payload


def test_spec_generation_rechecks_selected_skill_before_provider(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository, skills = _hardware_skills(tmp_path)
    component = skills.get_active_component("hw_seed_dht22")
    workspace = repository.create_project_from_idea(
        idea="Build a classroom environment monitor",
        project_name="Spec Hardware Skill gate",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
        selected_hardware_ids=[component.id],
    )
    solution_repository = SolutionRepository(repository.db_path)
    solution = solution_repository.confirm_solution(
        workspace.project.id,
        solution_repository.create_solution(
            workspace.project.id,
            [
                SolutionSection(
                    id="goal",
                    title="项目目标",
                    content="制作教室环境监测器",
                ),
                SolutionSection(
                    id="hardware",
                    title="硬件方案",
                    content="复用用户已选 DHT22",
                ),
                SolutionSection(
                    id="software",
                    title="软件方案",
                    content="MicroPython 周期采样",
                ),
            ],
        ).id,
    )
    proposal_repository = ProposalRepository(repository.db_path)
    proposal = proposal_repository.confirm_proposal(
        workspace.project.id,
        proposal_repository.create_from_solution(
            workspace.project.id,
            solution,
            fake_proposal_sections(),
        ).id,
    )
    skills.archive_component(component.id)
    provider = SequenceProvider([json.dumps({"projectName": "must not run"})])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(specs_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        f"/api/projects/{workspace.project.id}/spec/generate",
        json={"proposalId": proposal.id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "SPEC_HARDWARE_SKILL_INVALID"
    assert provider.calls == 0
