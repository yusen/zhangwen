from __future__ import annotations

import json
import sqlite3

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel, ConfigDict

from zhangwen.config import settings
from zhangwen.clarification.service import ClarificationService
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.chat import router as chat_router
from zhangwen.code_agent import router as code_router
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.llm.contracts import (
    LLMConfig,
    LLMErrorCode,
    LLMModelId,
)
from zhangwen.llm.structured import StructuredLLMError, complete_structured
from zhangwen.main import app
from zhangwen.lesson_agent import router as lesson_router
from zhangwen.lesson_agent.repository import LessonRepository
from zhangwen.projects import router as projects_router
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals import router as proposals_router
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from zhangwen.specs import router as specs_router
from zhangwen.specs.repository import SpecRepository
from tests.fakes import (
    EmptyCredentialStore,
    FakeCredentialStore,
    SequenceProvider,
    fake_proposal_sections,
)


class StructuredPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str


def _router_json(
    *,
    initial_expert: str = "smart_engineer",
    recommended_experts: list[str] | None = None,
) -> str:
    return json.dumps(
        {
            "intent": "technical_implementation",
            "projectName": "云端路由项目",
            "initialExpert": initial_expert,
            "recommendedExperts": recommended_experts or [initial_expert],
            "confidence": 0.96,
            "reason": "云端模型完成项目入口分析。",
            "requiresClarification": False,
        },
        ensure_ascii=False,
    )


def _proposal_json(*, revision: str = "") -> str:
    suffix = f"；{revision}" if revision else ""
    return json.dumps(
        {
            "projectOverview": f"制作一个可验证的自动浇花项目{suffix}",
            "requirements": "监测土壤湿度并在阈值触发时控制水泵。",
            "hardwareSoftwareStructure": "ESP32-S3、湿度传感器、水泵驱动与 MicroPython。",
            "implementationPlan": "先验证传感器，再联调水泵，最后完成整机测试。",
            "costDifficultySchedule": "预算 300 元，两课时完成，难度中等。",
            "risksAcceptance": f"防止水泵空转并检查供电；验收时验证自动浇水{suffix}",
        },
        ensure_ascii=False,
    )


def _spec_json() -> str:
    return json.dumps(
        {
            "projectName": "自动浇花装置",
            "goal": "根据土壤湿度安全控制水泵。",
            "modules": [
                {
                    "id": "sense",
                    "name": "湿度采集",
                    "responsibility": "读取湿度传感器。",
                },
                {
                    "id": "control",
                    "name": "水泵控制",
                    "responsibility": "按阈值控制水泵。",
                },
            ],
            "acceptance": ["低湿度时启动水泵。"],
            "risks": ["复核供电和防水。"],
            "componentIds": [
                "hw_seed_unihiker_k10",
                "hw_seed_dht22",
                "hw_seed_mosfet_driver",
                "hw_seed_oled_096",
                "hw_seed_usb_5v_power",
                "hw_seed_breadboard",
            ],
            "ioSuggestions": [
                {
                    "signal": "sensor_data",
                    "pin": "GPIO4",
                    "protocol": "GPIO",
                    "componentId": "hw_seed_dht22",
                },
                {
                    "signal": "actuator_pwm",
                    "pin": "GPIO5",
                    "protocol": "PWM",
                    "componentId": "hw_seed_mosfet_driver",
                },
            ],
        },
        ensure_ascii=False,
    )


def _code_json(*, config_py: str | None = None) -> str:
    return json.dumps(
        {
            "files": [
                {
                    "path": "src/boot.py",
                    "language": "python",
                    "content": "BOOT_PUMP_DEFAULT = 'OFF'\n",
                },
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": (
                        "from drivers.soil_moisture import read_sensor\n"
                        "from drivers.pump import stop_pump\n\n"
                        "def main():\n"
                        "    try:\n"
                        "        value = read_sensor()\n"
                        "        print('ZW_WATER event=sample moisture={} state=WET pump=OFF'.format(value))\n"
                        "    finally:\n"
                        "        stop_pump()\n\n"
                        "if __name__ == '__main__':\n"
                        "    main()\n"
                    ),
                },
                {
                    "path": "src/drivers/soil_moisture.py",
                    "language": "python",
                    "content": "def read_sensor():\n    return 1200\n",
                },
                {
                    "path": "src/drivers/pump.py",
                    "language": "python",
                    "content": "def stop_pump():\n    return 'OFF'\n",
                },
                {
                    "path": "src/config.py",
                    "language": "python",
                    "content": config_py or (
                        "SENSOR_PIN = 4\nPUMP_PWM_PIN = 5\n"
                        "DRY_CALIBRATION = 3000\nWET_CALIBRATION = 1200\n"
                        "PUMP_MAX_RUN_MS = 3000\nPUMP_COOLDOWN_MS = 60000\n"
                    ),
                },
                {
                    "path": "README.md",
                    "language": "markdown",
                    "content": (
                        "# 自动浇花\n\n独立 5V/3A 供泵并与 K10 共地。"
                        "先完成干燥/湿润标定，再执行 Mock、确认上传和日志核验。\n"
                    ),
                },
            ],
            "summary": "自动浇花 MicroPython 结构化工程草稿",
        },
        ensure_ascii=False,
    )


def _lesson_json(*, safety_suffix: str = "") -> str:
    return json.dumps(
        {
            "teacherGuide": "# 教师教案\n\n## 学习目标\n理解控制逻辑。\n\n## 教学流程\n完成 Mock 验证。\n",
            "studentWorksheet": "# 学生任务单\n\n## 今日任务\n标记输入和输出。\n",
            "rubric": "# 评价量表\n\n## 评价维度\n功能、记录和安全。\n",
            "safetyNotes": (
                "# 安全说明\n\n## 供电与接线\n不带电改线。\n"
                f"{safety_suffix}"
            ),
        },
        ensure_ascii=False,
    )


def _confirmed_solution(tmp_path, project_id: str):
    repository = SolutionRepository(ProjectRepository(tmp_path).db_path)
    solution = repository.create_solution(
        project_id,
        [
            SolutionSection(id="goal", title="项目目标", content="自动浇花"),
            SolutionSection(
                id="hardware",
                title="硬件方案",
                content="ESP32-S3、土壤湿度传感器和水泵驱动",
            ),
            SolutionSection(
                id="software",
                title="软件方案",
                content="MicroPython 读取湿度并控制水泵",
            ),
        ],
    )
    return repository.confirm_solution(project_id, solution.id)


def _approved_proposal(tmp_path):
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("自动浇花", "做一个自动浇花装置")
    solution = _confirmed_solution(tmp_path, workspace.project.id)
    proposal_repository = ProposalRepository(repository.db_path)
    proposal = proposal_repository.create_from_solution(
        workspace.project.id,
        solution,
        fake_proposal_sections(),
    )
    return workspace, proposal_repository.confirm_proposal(
        workspace.project.id,
        proposal.id,
    )


def _approved_spec(tmp_path, monkeypatch: pytest.MonkeyPatch):
    workspace, proposal = _approved_proposal(tmp_path)
    provider = SequenceProvider([_spec_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(specs_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(specs_router, "provider_factory", lambda: provider)
    client = TestClient(app)
    spec = client.post(
        f"/api/projects/{workspace.project.id}/spec/generate",
        json={"proposalId": proposal.id},
    ).json()["spec"]
    approved = client.post(
        f"/api/projects/{workspace.project.id}/spec/confirm",
        json={"specRunId": spec["id"]},
    ).json()["spec"]
    return workspace, approved


@pytest.mark.asyncio
async def test_structured_completion_repairs_invalid_json_once() -> None:
    provider = SequenceProvider(["not-json", '{"title":"有效输出"}'])

    result = await complete_structured(
        provider=provider,
        config=LLMConfig(),
        api_key="fake-test-key",
        model=LLMModelId.DEEPSEEK_V4_FLASH,
        system_prompt="返回结构化结果。",
        user_prompt="生成标题。",
        output_model=StructuredPayload,
        request_id_prefix="test_structured",
    )

    assert result.title == "有效输出"
    assert provider.calls == 2
    repair_messages = provider.requests[1].messages
    assert "上一次输出未通过校验" in repair_messages[-1].content


@pytest.mark.asyncio
async def test_structured_completion_rejects_two_invalid_outputs() -> None:
    provider = SequenceProvider(["not-json", '{"unexpected":true}'])

    with pytest.raises(StructuredLLMError) as exc_info:
        await complete_structured(
            provider=provider,
            config=LLMConfig(),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
            system_prompt="返回结构化结果。",
            user_prompt="生成标题。",
            output_model=StructuredPayload,
            request_id_prefix="test_invalid",
        )

    assert provider.calls == 2
    assert exc_info.value.error.code == LLMErrorCode.LLM_OUTPUT_INVALID


@pytest.mark.asyncio
async def test_structured_completion_classifies_local_validation_separately() -> None:
    provider = SequenceProvider(['{"title":"结构有效"}', '{"title":"仍然有效"}'])

    def reject_locally(_result: StructuredPayload) -> None:
        raise ValueError("local engineering boundary rejected generated content")

    with pytest.raises(StructuredLLMError) as exc_info:
        await complete_structured(
            provider=provider,
            config=LLMConfig(),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
            system_prompt="返回结构化结果。",
            user_prompt="生成标题。",
            output_model=StructuredPayload,
            request_id_prefix="test_local_validation",
            validate_result=reject_locally,
        )

    assert provider.calls == 2
    assert exc_info.value.error.code == LLMErrorCode.LOCAL_OUTPUT_REJECTED
    assert exc_info.value.diagnostic == (
        "local_output_rejected after 2 attempts: ValueError: "
        "local engineering boundary rejected generated content"
    )


@pytest.mark.asyncio
async def test_structured_completion_preserves_provider_error() -> None:
    provider = SequenceProvider([LLMErrorCode.RATE_LIMITED])

    with pytest.raises(StructuredLLMError) as exc_info:
        await complete_structured(
            provider=provider,
            config=LLMConfig(),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_FLASH,
            system_prompt="返回结构化结果。",
            user_prompt="生成标题。",
            output_model=StructuredPayload,
            request_id_prefix="test_provider_error",
        )

    assert provider.calls == 1
    assert exc_info.value.error.code == LLMErrorCode.RATE_LIMITED


def test_project_suggestion_always_calls_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        "/api/projects/suggest",
        json={"text": "ESP32 温湿度站", "useModelRouting": False},
    )

    assert response.status_code == 200
    assert provider.calls == 1
    assert response.json()["suggestion"]["name"] == "云端路由项目"


def test_project_suggestion_calls_provider_with_explicit_expert_constraint(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        "/api/projects/suggest",
        json={
            "text": "先设计外壳",
            "userSelectedExpert": ExpertType.STRUCTURE_ENGINEER.value,
        },
    )

    assert response.status_code == 200
    assert provider.calls == 1
    suggestion = response.json()["suggestion"]
    assert suggestion["initialExpert"] == ExpertType.STRUCTURE_ENGINEER.value
    assert suggestion["recommendedExpertTypes"][0] == ExpertType.STRUCTURE_ENGINEER.value


def test_project_create_without_router_result_calls_provider_before_persisting(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SequenceProvider([_router_json()])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        "/api/projects",
        json={"initialIdea": "ESP32 温湿度站"},
    )

    assert response.status_code == 200
    assert provider.calls == 1
    assert response.json()["workspace"]["project"]["name"] == "云端路由项目"
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 1


def test_project_routes_return_config_missing_without_persisting(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", EmptyCredentialStore)
    repository = ProjectRepository(tmp_path)

    suggest_response = TestClient(app).post(
        "/api/projects/suggest",
        json={"text": "ESP32 温湿度站"},
    )
    create_response = TestClient(app).post(
        "/api/projects",
        json={"initialIdea": "ESP32 温湿度站"},
    )

    assert suggest_response.status_code == 400
    assert suggest_response.json()["detail"]["code"] == LLMErrorCode.CONFIG_MISSING
    assert create_response.status_code == 400
    assert create_response.json()["detail"]["code"] == LLMErrorCode.CONFIG_MISSING
    with sqlite3.connect(repository.db_path) as conn:
        assert conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0] == 0


def test_project_suggestion_returns_invalid_output_without_fallback(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    provider = SequenceProvider(["not-json", '{"intent":"missing-fields"}'])
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(projects_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(projects_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        "/api/projects/suggest",
        json={"text": "ESP32 温湿度站"},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == LLMErrorCode.LLM_OUTPUT_INVALID
    assert provider.calls == 2


def test_proposal_generate_and_revise_each_call_provider_once(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("自动浇花", "做一个自动浇花装置")
    solution = _confirmed_solution(tmp_path, workspace.project.id)
    provider = SequenceProvider(
        [_proposal_json(), _proposal_json(revision="增加课堂安全提醒")]
    )
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(proposals_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(proposals_router, "provider_factory", lambda: provider)
    client = TestClient(app)

    generated = client.post(
        f"/api/projects/{workspace.project.id}/proposal/generate",
        json={"solutionId": solution.id},
    )
    revised = client.post(
        f"/api/projects/{workspace.project.id}/proposal/revise",
        json={
            "proposalId": generated.json()["proposal"]["id"],
            "revisionMessage": "增加课堂安全提醒",
        },
    )

    assert generated.status_code == 200
    assert revised.status_code == 200
    assert provider.calls == 2
    revised_sections = revised.json()["proposal"]["sections"]
    assert [section["id"] for section in revised_sections] == [
        "project_overview",
        "requirements",
        "hardware_software_structure",
        "implementation_plan",
        "cost_difficulty_schedule",
        "risks_acceptance",
    ]
    assert "课堂安全提醒" in revised_sections[-1]["content"]
    assert all(section["id"] != "revision_notes" for section in revised_sections)


def test_proposal_missing_key_or_invalid_output_does_not_persist(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project("自动浇花", "做一个自动浇花装置")
    solution = _confirmed_solution(tmp_path, workspace.project.id)
    with sqlite3.connect(repository.db_path) as conn:
        artifact_count_before = conn.execute(
            "SELECT COUNT(*) FROM artifacts"
        ).fetchone()[0]
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(proposals_router, "credential_store_factory", EmptyCredentialStore)
    client = TestClient(app)

    missing = client.post(
        f"/api/projects/{workspace.project.id}/proposal/generate",
        json={"solutionId": solution.id},
    )
    assert missing.status_code == 400
    assert missing.json()["detail"]["code"] == LLMErrorCode.CONFIG_MISSING
    assert ProposalRepository(repository.db_path).list_proposals(workspace.project.id) == []

    provider = SequenceProvider(["not-json", '{"projectOverview":"only-one"}'])
    monkeypatch.setattr(proposals_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(proposals_router, "provider_factory", lambda: provider)
    invalid = client.post(
        f"/api/projects/{workspace.project.id}/proposal/generate",
        json={"solutionId": solution.id},
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == LLMErrorCode.LLM_OUTPUT_INVALID
    assert provider.calls == 2
    assert ProposalRepository(repository.db_path).list_proposals(workspace.project.id) == []
    with sqlite3.connect(repository.db_path) as conn:
        assert (
            conn.execute("SELECT COUNT(*) FROM artifacts").fetchone()[0]
            == artifact_count_before
        )


def test_project_chat_proposal_generation_and_revision_use_provider(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)
    project = client.post(
        "/api/projects",
        json={"name": "自动浇花", "initialIdea": "做一个自动浇花装置"},
    ).json()["workspace"]["project"]
    solution = _confirmed_solution(tmp_path, project["id"])
    client.post(
        f"/api/projects/{project['id']}/solution/confirm",
        json={"solutionId": solution.id},
    )
    provider = SequenceProvider(
        [_proposal_json(), _proposal_json(revision="增加课堂安全提醒")]
    )
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)

    generated = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={
            "content": "生成立项书",
            "model": "deepseek-v4-flash",
            "conversationAction": "generate_project_proposal",
        },
    )
    revised = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={"content": "修改立项书风险章节，增加课堂安全说明", "model": "deepseek-v4-flash"},
    )

    assert generated.status_code == 200
    assert revised.status_code == 200
    generated_chunks = _sse_chunks(generated.text)
    assert generated_chunks[0]["type"] == "START"
    assert generated_chunks[-1]["type"] == "COMPLETED"
    generated_progress = [
        (chunk["progress"]["action"], chunk["progress"]["status"])
        for chunk in generated_chunks
        if chunk["type"] == "PROGRESS"
    ]
    assert ("CONTEXT_READ", "RUNNING") in generated_progress
    assert ("CONTEXT_READ", "COMPLETED") in generated_progress
    assert ("CLOUD_LLM_REQUEST", "RUNNING") in generated_progress
    assert ("OUTPUT_VALIDATE", "COMPLETED") in generated_progress
    assert ("PROJECT_UPDATE", "RUNNING") in generated_progress
    assert ("PROJECT_UPDATE", "COMPLETED") in generated_progress
    assert provider.calls == 2
    proposals = ProposalRepository(ProjectRepository(tmp_path).db_path).list_proposals(
        project["id"]
    )
    assert [proposal.version for proposal in proposals] == [2, 1]
    assert "课堂安全提醒" in proposals[0].sections[-1].content


def _sse_chunks(text: str) -> list[dict[str, object]]:
    chunks: list[dict[str, object]] = []
    for event in text.strip().split("\n\n"):
        for line in event.splitlines():
            if line.startswith("data:"):
                payload = json.loads(line[5:].strip())
                if isinstance(payload, dict):
                    chunks.append(payload)
    return chunks


def test_engineering_generators_each_call_provider_and_persist_validated_output(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, proposal = _approved_proposal(tmp_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)

    spec_provider = SequenceProvider([_spec_json()])
    monkeypatch.setattr(specs_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(specs_router, "provider_factory", lambda: spec_provider)
    spec = client.post(
        f"/api/projects/{workspace.project.id}/spec/generate",
        json={"proposalId": proposal.id},
    ).json()["spec"]
    spec = client.post(
        f"/api/projects/{workspace.project.id}/spec/confirm",
        json={"specRunId": spec["id"]},
    ).json()["spec"]
    assert spec_provider.calls == 1
    assert "自动浇花装置" in next(
        item["content"] for item in spec["files"] if item["kind"] == "PROJECT_SPEC"
    )

    code_provider = SequenceProvider([_code_json()])
    monkeypatch.setattr(code_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(code_router, "provider_factory", lambda: code_provider)
    code = client.post(
        f"/api/projects/{workspace.project.id}/code/generate",
        json={"specRunId": spec["id"]},
    ).json()["codeRun"]
    assert code_provider.calls == 1
    assert code["testResult"]["command"] == "micropython-local-validation"
    assert [check["kind"] for check in code["testResult"]["checks"]] == [
        "STATIC",
        "SYNTAX",
    ]
    assert all(check["exitCode"] == 0 for check in code["testResult"]["checks"])

    lesson_provider = SequenceProvider([_lesson_json()])
    monkeypatch.setattr(lesson_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(lesson_router, "provider_factory", lambda: lesson_provider)
    lesson = client.post(
        f"/api/projects/{workspace.project.id}/lesson/generate",
        json={"specRunId": spec["id"], "gradeBand": "初中", "lessonHours": 2},
    ).json()["lessonRun"]
    assert lesson_provider.calls == 1
    assert len(lesson["files"]) == 4


def test_engineering_generators_missing_key_do_not_create_runs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, proposal = _approved_proposal(tmp_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)

    monkeypatch.setattr(specs_router, "credential_store_factory", EmptyCredentialStore)
    missing_spec = client.post(
        f"/api/projects/{workspace.project.id}/spec/generate",
        json={"proposalId": proposal.id},
    )
    assert missing_spec.status_code == 400
    assert missing_spec.json()["detail"]["code"] == LLMErrorCode.CONFIG_MISSING
    assert SpecRepository(ProjectRepository(tmp_path).db_path).get_current_spec(
        workspace.project.id
    ) is None

    workspace, spec = _approved_spec(tmp_path / "downstream", monkeypatch)
    client = TestClient(app)
    routes = [
        (code_router, f"/api/projects/{workspace.project.id}/code/generate", {"specRunId": spec["id"]}),
        (
            lesson_router,
            f"/api/projects/{workspace.project.id}/lesson/generate",
            {"specRunId": spec["id"]},
        ),
    ]
    for module, path, body in routes:
        monkeypatch.setattr(module, "credential_store_factory", EmptyCredentialStore)
        response = client.post(path, json=body)
        assert response.status_code == 400
        assert response.json()["detail"]["code"] == LLMErrorCode.CONFIG_MISSING
    db_path = ProjectRepository(tmp_path / "downstream").db_path
    assert CodeRepository(db_path).get_current_code(workspace.project.id) is None
    assert LessonRepository(db_path).get_current_lesson(workspace.project.id) is None


def test_engineering_generators_invalid_model_output_do_not_create_runs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, proposal = _approved_proposal(tmp_path)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)
    invalid_provider = SequenceProvider(["not-json", '{"missing":true}'])
    monkeypatch.setattr(specs_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(specs_router, "provider_factory", lambda: invalid_provider)
    invalid_spec = client.post(
        f"/api/projects/{workspace.project.id}/spec/generate",
        json={"proposalId": proposal.id},
    )
    assert invalid_spec.status_code == 422
    assert invalid_spec.json()["detail"]["code"] == LLMErrorCode.LLM_OUTPUT_INVALID
    assert invalid_provider.calls == 2

    workspace, spec = _approved_spec(tmp_path / "downstream", monkeypatch)
    client = TestClient(app)
    cases = [
        (code_router, f"/api/projects/{workspace.project.id}/code/generate", {"specRunId": spec["id"]}),
        (
            lesson_router,
            f"/api/projects/{workspace.project.id}/lesson/generate",
            {"specRunId": spec["id"]},
        ),
    ]
    for module, path, body in cases:
        provider = SequenceProvider(["not-json", '{"missing":true}'])
        monkeypatch.setattr(module, "credential_store_factory", FakeCredentialStore)
        monkeypatch.setattr(module, "provider_factory", lambda provider=provider: provider)
        response = client.post(path, json=body)
        assert response.status_code == 422
        assert response.json()["detail"]["code"] == LLMErrorCode.LLM_OUTPUT_INVALID
        assert provider.calls == 2
    db_path = ProjectRepository(tmp_path / "downstream").db_path
    assert CodeRepository(db_path).get_current_code(workspace.project.id) is None
    assert LessonRepository(db_path).get_current_lesson(workspace.project.id) is None


def test_local_code_and_lesson_safety_validation_blocks_sensitive_output(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace, spec = _approved_spec(tmp_path, monkeypatch)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)

    code_provider = SequenceProvider([_code_json(config_py="API_KEY = 'sk-abcdefgh1234'\n")])
    monkeypatch.setattr(code_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(code_router, "provider_factory", lambda: code_provider)
    code_response = client.post(
        f"/api/projects/{workspace.project.id}/code/generate",
        json={"specRunId": spec["id"]},
    )
    assert code_response.status_code == 422
    assert code_response.json()["detail"]["code"] == LLMErrorCode.LOCAL_OUTPUT_REJECTED
    assert code_provider.calls == 2

    lesson_provider = SequenceProvider([_lesson_json(safety_suffix="\n设备端口 COM3\n")])
    monkeypatch.setattr(lesson_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(lesson_router, "provider_factory", lambda: lesson_provider)
    lesson_response = client.post(
        f"/api/projects/{workspace.project.id}/lesson/generate",
        json={"specRunId": spec["id"]},
    )
    assert lesson_response.status_code == 422
    assert lesson_response.json()["detail"]["code"] == LLMErrorCode.LOCAL_OUTPUT_REJECTED
    assert lesson_provider.calls == 2
    db_path = ProjectRepository(tmp_path).db_path
    assert CodeRepository(db_path).get_current_code(workspace.project.id) is None
    assert LessonRepository(db_path).get_current_lesson(workspace.project.id) is None


@pytest.mark.asyncio
async def test_clarification_service_repairs_once_and_expert_runtime_never_falls_back(
    tmp_path,
) -> None:
    clarification_provider = SequenceProvider(
        [
            "not-json",
            json.dumps(
                {
                    "questions": [
                        {
                            "id": "context",
                            "type": "SINGLE_SELECT",
                            "question": "主要场景是什么？",
                            "options": [
                                {"id": "home", "label": "家庭"},
                                {"id": "school", "label": "学校"},
                            ],
                        }
                    ],
                    "completeness": 40,
                    "message": "请确认主要场景。",
                },
                ensure_ascii=False,
            ),
        ]
    )
    result = await ClarificationService(clarification_provider).clarify(
        user_message="我想做一个提醒器",
        context_messages=[],
        config=LLMConfig(),
        api_key="fake-test-key",
    )
    assert result.questions[0].id == "context"
    assert clarification_provider.calls == 2

    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project_from_idea(
        idea="ESP32 传感器",
        project_name="传感器项目",
        initial_expert=ExpertType.SMART_ENGINEER,
        participating_experts=[ExpertType.SMART_ENGINEER],
    )
    active = workspace.experts[0]
    invalid_provider = SequenceProvider(["not-json", '{"content":""}'])
    with pytest.raises(StructuredLLMError) as exc_info:
        await ExpertRuntime(repository.db_path).run(
            request=ExpertRuntimeRequest(
                projectId=workspace.project.id,
                projectExpertId=active.id,
                conversationId=active.conversationId,
                expertType=ExpertType.SMART_ENGINEER,
                userMessage="检查接线",
                model=LLMModelId.DEEPSEEK_V4_FLASH,
            ),
            provider=invalid_provider,
            config=LLMConfig(),
            api_key="fake-test-key",
        )
    assert exc_info.value.error.code == LLMErrorCode.LLM_OUTPUT_INVALID
    assert invalid_provider.calls == 2
    with sqlite3.connect(repository.db_path) as conn:
        run = conn.execute(
            "SELECT status, output_json FROM expert_runs WHERE project_id = ?",
            (workspace.project.id,),
        ).fetchone()
    assert run == ("failed", None)


def test_invalid_expert_chat_returns_llm_error_without_local_reply(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)
    route = json.loads(
        _router_json(
            initial_expert="smart_engineer",
            recommended_experts=["smart_engineer"],
        )
    )
    project = client.post(
        "/api/projects",
        json={
            "name": "传感器项目",
            "initialIdea": "ESP32 传感器",
            "initialExpert": "smart_engineer",
            "selectedExpertTypes": ["smart_engineer"],
            "routerResult": route,
        },
    ).json()["workspace"]["project"]
    provider = SequenceProvider(["not-json", '{"content":""}'])
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={"content": "检查接线", "model": "deepseek-v4-flash"},
    )

    assert response.status_code == 200
    assert '"type": "ERROR"' in response.text
    assert '"code": "LLM_OUTPUT_INVALID"' in response.text
    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    assert workspace.conversation.messages[-1].status == "FAILED"
    assert "当前专家没有返回" not in workspace.conversation.messages[-1].content


def test_local_expert_rejection_streams_local_error_without_cloud_blame(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    client = TestClient(app)
    route = json.loads(
        _router_json(
            initial_expert="structure_engineer",
            recommended_experts=["structure_engineer"],
        )
    )
    project = client.post(
        "/api/projects",
        json={
            "name": "结构选型项目",
            "initialIdea": "制作一个桌面装置",
            "initialExpert": "structure_engineer",
            "selectedExpertTypes": ["structure_engineer"],
            "routerResult": route,
        },
    ).json()["workspace"]["project"]
    external = json.dumps(
        {
            "content": (
                "建议采用 ESP32-WROOM-32、外接 SPI 屏幕和独立升压电源，"
                "并据此继续生成硬件方案。"
            )
        },
        ensure_ascii=False,
    )
    provider = SequenceProvider([external, external])
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", lambda: provider)

    response = client.post(
        f"/api/projects/{project['id']}/chat/stream",
        json={"content": "请推荐主控、屏幕和供电方案", "model": "deepseek-v4-flash"},
    )

    assert response.status_code == 200
    assert '"type": "ERROR"' in response.text
    assert '"code": "LOCAL_OUTPUT_REJECTED"' in response.text
    assert "生成结果未通过当前工程约束或安全边界" in response.text
    assert "云端返回的结构化内容连续两次不完整" not in response.text
    workspace = ProjectRepository(tmp_path).get_workspace(project["id"])
    assert workspace.conversation.messages[-1].status == "FAILED"
