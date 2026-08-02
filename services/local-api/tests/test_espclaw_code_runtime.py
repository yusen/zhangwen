"""Regression tests for ESP-Claw Lua as a first-class CodeRun runtime."""

from __future__ import annotations

import asyncio
import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.code_agent import router as code_router
from zhangwen.code_agent.chat_code import package_chat_code_draft
from zhangwen.code_agent.generator import validate_and_package_code
from zhangwen.code_agent.models import (
    ChatCodeDraft,
    CodeContentDraft,
    CodeRuntime,
    EditableCodeFile,
    GenerateCodeRequest,
)
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.code_agent.service import CodeGenerationService
from zhangwen.code_agent.validation import (
    is_uploadable_lua_path,
    run_esp_claw_lua_validation,
)
from zhangwen.config import settings
from zhangwen.llm.contracts import LLMConfig, LLMModelId
from zhangwen.main import app
from zhangwen.experts.context_assembler import (
    ContextAssembler,
    ContextAssemblyInput,
)
from zhangwen.experts.runtime import ExpertRuntimeOutput, _runtime_system_prompt
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from zhangwen.specs.models import (
    SpecFile,
    SpecFileKind,
    SpecRun,
    SpecRunStatus,
    SpecValidation,
)
from tests.fakes import SequenceProvider, fake_proposal_sections


def test_generate_request_keeps_micropython_default() -> None:
    request = GenerateCodeRequest(specRunId="spec_1")

    assert request.runtime == CodeRuntime.MICROPYTHON
    assert GenerateCodeRequest(
        specRunId="spec_1",
        runtime=CodeRuntime.ESP_CLAW_LUA,
    ).runtime == CodeRuntime.ESP_CLAW_LUA


def test_provider_prompt_explicitly_requests_esp_claw_lua_files() -> None:
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "files": [
                        {
                            "path": "scripts/main.lua",
                            "language": "lua",
                            "content": "local value = 1\nprint(value)\n",
                        }
                    ],
                    "summary": "ESP-Claw Lua draft",
                }
            )
        ]
    )

    draft = asyncio.run(
        CodeGenerationService(provider).generate(
            spec=_approved_spec(),
            config=LLMConfig(),
            api_key="fake-test-key",
            model=LLMModelId.DEEPSEEK_V4_PRO,
            runtime=CodeRuntime.ESP_CLAW_LUA,
        )
    )
    prompt = "\n".join(
        message.content for message in provider.requests[0].messages
    )

    assert draft.files[0].language == "lua"
    assert '"runtime": "ESP_CLAW_LUA"' in prompt
    assert '"requiredEntry": "scripts/main.lua"' in prompt
    assert "绝不能输出 Python" in prompt


def test_smart_engineer_chat_draft_materializes_lua_runtime(tmp_path: Path) -> None:
    draft = ChatCodeDraft.model_validate(
        {
            "runtime": "ESP_CLAW_LUA",
            "files": [
                {
                    "path": "scripts/main.lua",
                    "language": "lua",
                    "content": "local value = 1\nprint(value)\n",
                }
            ],
            "summary": "使用 DFRobot K10 的 ESP-Claw Lua 工程",
        }
    )

    generated = package_chat_code_draft(
        draft,
        now="2026-07-30T00:00:00+00:00",
    )
    output = ExpertRuntimeOutput.model_validate(
        {
            "content": "已按 DFRobot K10 生成 ESP-Claw Lua 行为代码。",
            "codeDraft": draft.model_dump(mode="json"),
        }
    )
    prompt = _runtime_system_prompt(
        ExpertType.SMART_ENGINEER,
        "请改用 ESP-Claw 方式上传代码",
        tmp_path,
    )

    assert generated.runtime == CodeRuntime.ESP_CLAW_LUA
    assert generated.entrypoint == "scripts/main.lua"
    assert output.codeDraft is not None
    assert output.codeDraft.runtime == CodeRuntime.ESP_CLAW_LUA
    assert "ESP_CLAW_LUA" in prompt
    assert "scripts/main.lua" in prompt


def test_chat_draft_runtime_defaults_to_micropython() -> None:
    draft = ChatCodeDraft.model_validate(
        {
            "files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "print('legacy')\n",
                }
            ],
            "summary": "legacy MicroPython draft",
        }
    )

    assert draft.runtime == CodeRuntime.MICROPYTHON
    assert package_chat_code_draft(
        draft,
        now="2026-07-30T00:00:00+00:00",
    ).entrypoint == "src/main.py"


def test_generate_endpoint_persists_esp_claw_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_id, spec_id = _project_with_approved_spec(tmp_path)
    provider = SequenceProvider(
        [
            json.dumps(
                {
                    "files": [
                        {
                            "path": "scripts/main.lua",
                            "language": "lua",
                            "content": "local value = 1\nprint(value)\n",
                        }
                    ],
                    "summary": "endpoint Lua draft",
                }
            )
        ]
    )
    monkeypatch.setattr(code_router, "provider_factory", lambda: provider)

    response = TestClient(app).post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id, "runtime": "ESP_CLAW_LUA"},
    )

    assert response.status_code == 200, response.text
    code_run = response.json()["codeRun"]
    assert code_run["runtime"] == "ESP_CLAW_LUA"
    assert code_run["entrypoint"] == "scripts/main.lua"
    assert code_run["testResult"]["ok"] is True
    stored = CodeRepository(ProjectRepository(tmp_path).db_path).get_code(
        project_id,
        code_run["id"],
    )
    assert stored.runtime == CodeRuntime.ESP_CLAW_LUA


def test_esp_claw_lua_is_packaged_and_validated_without_python_coercion() -> None:
    generated = validate_and_package_code(
        _approved_spec(),
        CodeContentDraft.model_validate(
            {
                "files": [
                    {
                        "path": "scripts/main.lua",
                        "language": "lua",
                        "content": (
                            "local function sample()\n"
                            "  print('ZW_SENSOR value=1')\n"
                            "end\n"
                            "sample()\n"
                        ),
                    },
                    {
                        "path": "scripts/drivers/sensor.lua",
                        "language": "lua",
                        "content": "local M = {}\nfunction M.read() return 1 end\nreturn M\n",
                    },
                    {
                        "path": "README.md",
                        "language": "markdown",
                        "content": "# ESP-Claw project\n",
                    },
                ],
                "summary": "ESP-Claw Lua device behavior",
            }
        ),
        now="2026-07-30T00:00:00+00:00",
        runtime=CodeRuntime.ESP_CLAW_LUA,
    )

    assert generated.runtime == CodeRuntime.ESP_CLAW_LUA
    assert generated.entrypoint == "scripts/main.lua"
    assert {file.language for file in generated.files} == {"lua", "markdown"}
    result = run_esp_claw_lua_validation(
        generated.files,
        now="2026-07-30T00:00:00+00:00",
    )
    assert result.ok is True
    assert result.command == "esp-claw-lua-local-validation"

    with pytest.raises(ValueError, match="Lua|lua"):
        validate_and_package_code(
            _approved_spec(),
            CodeContentDraft.model_validate(
                {
                    "files": [
                        {
                            "path": "scripts/main.lua",
                            "language": "python",
                            "content": "def main():\n    return 1\n",
                        }
                    ],
                    "summary": "must not reinterpret Python as Lua",
                }
            ),
            now="2026-07-30T00:00:00+00:00",
            runtime=CodeRuntime.ESP_CLAW_LUA,
        )


@pytest.mark.parametrize(
    ("path", "content"),
    [
        ("scripts/../main.lua", "print('no')\n"),
        ("scripts/wifi_password.lua", "print('no')\n"),
        ("scripts/main.lua", "wifi_password = 'real-password'\n"),
        ("scripts/main.lua", "def main():\n    return 1\n"),
        ("scripts/main.lua", "if true then\n  print('missing end')\n"),
    ],
)
def test_esp_claw_lua_rejects_unsafe_or_non_lua_input(
    path: str,
    content: str,
) -> None:
    with pytest.raises(ValueError):
        validate_and_package_code(
            _approved_spec(),
            CodeContentDraft.model_validate(
                {
                    "files": [
                        {"path": path, "language": "lua", "content": content}
                    ],
                    "summary": "unsafe",
                }
            ),
            now="2026-07-30T00:00:00+00:00",
            runtime=CodeRuntime.ESP_CLAW_LUA,
        )


def test_esp_claw_lua_rejects_credential_named_directories() -> None:
    assert is_uploadable_lua_path("scripts/secrets/helper.lua") is False
    with pytest.raises(ValueError, match="scripts"):
        validate_and_package_code(
            _approved_spec(),
            CodeContentDraft.model_validate(
                {
                    "files": [
                        {
                            "path": "scripts/main.lua",
                            "language": "lua",
                            "content": "print('safe')\n",
                        },
                        {
                            "path": "scripts/secrets/helper.lua",
                            "language": "lua",
                            "content": "return {}\n",
                        },
                    ],
                    "summary": "credential directory must fail",
                }
            ),
            now="2026-07-30T00:00:00+00:00",
            runtime=CodeRuntime.ESP_CLAW_LUA,
        )


def test_esp_claw_lua_rejects_oversized_project() -> None:
    large_content = "-- bounded comment\n" * 2_000
    files = [
        {
            "path": "scripts/main.lua",
            "language": "lua",
            "content": large_content,
        }
    ] + [
        {
            "path": f"scripts/module_{index}.lua",
            "language": "lua",
            "content": large_content,
        }
        for index in range(1, 6)
    ]

    with pytest.raises(ValueError, match="上限"):
        validate_and_package_code(
            _approved_spec(),
            CodeContentDraft.model_validate(
                {"files": files, "summary": "oversized Lua project"}
            ),
            now="2026-07-30T00:00:00+00:00",
            runtime=CodeRuntime.ESP_CLAW_LUA,
        )


def test_repository_persists_lua_runtime_and_v29_repair_is_idempotent(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project(
        "ESP-Claw project",
        "Run controlled Lua behavior on ESP-Claw",
        selected_expert_types=[ExpertType.SMART_ENGINEER],
    )
    generated = validate_and_package_code(
        _approved_spec(project_id=workspace.project.id),
        CodeContentDraft.model_validate(
            {
                "files": [
                    {
                        "path": "scripts/main.lua",
                        "language": "lua",
                        "content": "local value = 1\nprint(value)\n",
                    }
                ],
                "summary": "persist Lua runtime",
            }
        ),
        now="2026-07-30T00:00:00+00:00",
        runtime=CodeRuntime.ESP_CLAW_LUA,
    )
    generated = generated.__class__(
        files=generated.files,
        diff=generated.diff,
        summary=generated.summary,
        test_result=run_esp_claw_lua_validation(
            generated.files,
            now="2026-07-30T00:00:00+00:00",
        ),
        runtime=generated.runtime,
        entrypoint=generated.entrypoint,
    )

    code_run = CodeRepository(repository.db_path).create_from_chat_draft(
        project_id=workspace.project.id,
        source_message_id="assistant_lua_1",
        generated_by_expert_id=None,
        generated=generated,
    )

    assert code_run.runtime == CodeRuntime.ESP_CLAW_LUA
    assert code_run.entrypoint == "scripts/main.lua"
    assert code_run.files[0].language == "lua"
    artifact = ArtifactRepository(repository.db_path).get_artifact(
        workspace.project.id,
        str(code_run.artifactId),
    )
    assert artifact.title == "ESP-Claw Lua 工程代码"
    assert artifact.versions[0].mimeType == "text/x-lua"
    assert artifact.versions[0].preview.language == "lua"
    revised = CodeRepository(repository.db_path).revise_from_user(
        project_id=workspace.project.id,
        base_code_run_id=code_run.id,
        files=[
            EditableCodeFile(
                path="scripts/main.lua",
                content="local value = 2\nprint(value)\n",
            )
        ],
        summary="change Lua value",
    )
    assert revised.runtime == CodeRuntime.ESP_CLAW_LUA
    assert revised.entrypoint == "scripts/main.lua"
    context = ContextAssembler(repository.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请继续修改当前 ESP-Claw Lua 代码",
        )
    )
    assert context.currentCode is not None
    assert context.currentCode["runtime"] == "ESP_CLAW_LUA"
    assert context.currentCode["entrypoint"] == "scripts/main.lua"
    assert context.currentCode["files"][0]["path"] == "scripts/main.lua"
    assert "local value = 2" in context.currentCode["files"][0]["content"]
    failed_validation = run_esp_claw_lua_validation(
        [
            revised.files[0].model_copy(
                update={"content": "if true then\n  print('missing end')\n"}
            )
        ],
        now="2026-07-30T00:00:00+00:00",
    )
    failed_run = CodeRepository(repository.db_path).validate_code(
        workspace.project.id,
        revised.id,
        failed_validation,
    )
    assert failed_run.staleReason == "本地 ESP-Claw Lua 验证未通过。"

    with sqlite3.connect(repository.db_path) as conn:
        conn.execute("ALTER TABLE code_runs DROP COLUMN runtime")
        conn.execute("ALTER TABLE code_runs DROP COLUMN entrypoint")
        conn.execute("DROP TABLE espclaw_deployments")
        conn.execute("DROP TABLE espclaw_endpoints")
        conn.execute(f"PRAGMA user_version={CURRENT_SCHEMA_VERSION}")
        migrate(conn)
        columns = {
            str(row[1]): str(row[4])
            for row in conn.execute("PRAGMA table_info(code_runs)").fetchall()
        }
        legacy = conn.execute(
            "SELECT runtime, entrypoint FROM code_runs WHERE id = ?",
            (code_run.id,),
        ).fetchone()
        espclaw_tables = {
            str(row[0])
            for row in conn.execute(
                """
                SELECT name FROM sqlite_master
                WHERE type = 'table' AND name LIKE 'espclaw_%'
                """
            ).fetchall()
        }
        endpoint_schema = str(
            conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name='espclaw_endpoints'"
            ).fetchone()[0]
        )
        deployment_indexes = {
            str(row[1])
            for row in conn.execute(
                "PRAGMA index_list(espclaw_deployments)"
            ).fetchall()
        }

    assert columns["runtime"] == "'MICROPYTHON'"
    assert columns["entrypoint"] == "'src/main.py'"
    assert legacy == ("MICROPYTHON", "src/main.py")
    assert espclaw_tables == {"espclaw_endpoints", "espclaw_deployments"}
    assert "dfrobot/dfrobot_k10" in endpoint_schema
    assert "seeedstudio/xiao_esp32s3_sense" in endpoint_schema
    assert "idx_espclaw_deployments_endpoint" in deployment_indexes


def _approved_spec(project_id: str = "project_1") -> SpecRun:
    now = "2026-07-30T00:00:00+00:00"
    return SpecRun(
        id="spec_1",
        projectId=project_id,
        proposalId="proposal_1",
        version=1,
        status=SpecRunStatus.APPROVED,
        files=[
            SpecFile(
                id="spec_file_io",
                specRunId="spec_1",
                projectId=project_id,
                kind=SpecFileKind.IO_MAP,
                path="spec/io_map.yaml",
                mimeType="application/yaml",
                content="signals: []\n",
                createdAt=now,
            )
        ],
        validation=SpecValidation(ok=True, checks=[]),
        createdAt=now,
        updatedAt=now,
        confirmedAt=now,
    )


def _project_with_approved_spec(tmp_path: Path) -> tuple[str, str]:
    settings.data_dir = tmp_path
    client = TestClient(app)
    response = client.post(
        "/api/projects",
        json={
            "name": "ESP-Claw endpoint project",
            "initialIdea": "用 ESP-Claw Lua 驱动传感器",
            "selectedExpertTypes": [ExpertType.SMART_ENGINEER.value],
        },
    )
    assert response.status_code == 200, response.text
    project_id = str(response.json()["workspace"]["project"]["id"])
    db_path = ProjectRepository(tmp_path).db_path
    solution_repo = SolutionRepository(db_path)
    solution = solution_repo.confirm_solution(
        project_id,
        solution_repo.create_solution(
            project_id,
            [
                SolutionSection(id="goal", title="项目目标", content="传感器联动"),
                SolutionSection(
                    id="hardware",
                    title="硬件方案",
                    content="K10 与板载传感器",
                ),
                SolutionSection(
                    id="software",
                    title="软件方案",
                    content="ESP-Claw Lua 行为脚本",
                ),
            ],
        ).id,
    )
    proposal_repo = ProposalRepository(db_path)
    proposal = proposal_repo.confirm_proposal(
        project_id,
        proposal_repo.create_from_solution(
            project_id,
            solution,
            fake_proposal_sections(),
        ).id,
    )
    spec_response = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": proposal.id},
    )
    assert spec_response.status_code == 200, spec_response.text
    spec_id = str(spec_response.json()["spec"]["id"])
    confirm = client.post(
        f"/api/projects/{project_id}/spec/confirm",
        json={"specRunId": spec_id},
    )
    assert confirm.status_code == 200, confirm.text
    return project_id, spec_id
