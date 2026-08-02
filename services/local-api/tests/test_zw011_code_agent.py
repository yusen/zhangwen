"""Tests for ZW-011 Code Agent."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zhangwen.artifacts.models import (
    ArtifactKind,
    ArtifactStatus,
    DomainArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.code_agent.models import (
    ChatCodeDraft,
    CodeRun,
    CodeRunStatus,
    CodeTestResult,
    CodeValidationCheck,
    CodeValidationKind,
    CodeValidationStatus,
    EditableCodeFile,
)
from zhangwen.code_agent.chat_code import ChatCodeService
from zhangwen.code_agent import router as code_router
from zhangwen.code_agent.repository import CodeRepository, CodeRevisionConflictError
from zhangwen.config import settings
from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeRequest
from zhangwen.llm.contracts import LLMConfig, LLMModelId, StreamChunk, StreamChunkType
from zhangwen.main import app
from zhangwen.projects.migrations import CURRENT_SCHEMA_VERSION, migrate
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository
from zhangwen.proposals.repository import ProposalRepository
from zhangwen.solutions.models import SolutionSection
from zhangwen.solutions.repository import SolutionRepository
from tests.fakes import SequenceProvider, fake_proposal_sections
from zhangwen.specs.models import SpecRunStatus


def test_v9_migration_creates_code_tables(tmp_path: Path) -> None:
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
    assert {"code_runs", "code_files", "code_patches"}.issubset(tables)


def test_code_requires_approved_spec(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=False)

    response = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODE_REQUIRES_APPROVED_SPEC"


def test_formal_chat_code_persists_approved_spec_binding(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)

    code_run = ChatCodeService(ProjectRepository(tmp_path).db_path).materialize(
        project_id=project_id,
        source_message_id="assistant_formal_code_1",
        generated_by_expert_id=None,
        spec_run_id=spec_id,
        draft=ChatCodeDraft.model_validate(
            {
                "files": [
                    {
                        "path": "src/main.py",
                        "language": "python",
                        "content": "print('formal project')\n",
                    }
                ],
                "summary": "按确认 Spec 生成正式工程代码",
            }
        ),
    )

    assert code_run.specRunId == spec_id


def test_generate_accept_reject_and_rollback_code(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)

    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    )

    assert generated.status_code == 200, generated.text
    code_run = generated.json()["codeRun"]
    assert code_run["status"] == CodeRunStatus.READY_FOR_REVIEW.value
    assert code_run["workspaceRoot"].startswith("workspace://")
    assert code_run["testResult"]["ok"] is True
    assert {file["path"] for file in code_run["files"]} == {
        "README.md",
        "src/boot.py",
        "src/config.py",
        "src/drivers/pump.py",
        "src/drivers/soil_moisture.py",
        "src/main.py",
    }
    assert "diff --git" in code_run["patch"]["diff"]
    assert "while True" in next(
        file["content"] for file in code_run["files"] if file["path"] == "src/main.py"
    )

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(project_id)
    code_artifact = next(artifact for artifact in artifacts if artifact.sourceAgentId == "code-agent")
    assert code_artifact.kind == ArtifactKind.CODE
    assert code_artifact.versions[0].status == ArtifactStatus.NEEDS_REVIEW
    assert (
        code_artifact.versions[0].domainStatus
        == DomainArtifactStatus.PENDING_CONFIRMATION
    )
    artifact_version_id = code_artifact.versions[0].id

    accepted = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": code_run["id"]},
    )
    assert accepted.status_code == 200
    assert accepted.json()["codeRun"]["status"] == CodeRunStatus.ACCEPTED.value
    accepted_artifact = ArtifactRepository(
        ProjectRepository(tmp_path).db_path
    ).get_artifact(project_id, code_artifact.id)
    assert accepted_artifact.currentVersionId == artifact_version_id
    assert len(accepted_artifact.versions) == 1
    assert accepted_artifact.status == ArtifactStatus.APPROVED
    assert accepted_artifact.domainStatus == DomainArtifactStatus.CONFIRMED
    assert accepted_artifact.versions[0].status == ArtifactStatus.APPROVED
    assert (
        accepted_artifact.versions[0].domainStatus
        == DomainArtifactStatus.CONFIRMED
    )

    current = client.get(f"/api/projects/{project_id}/code/current")
    assert current.status_code == 200
    assert current.json()["codeRun"]["id"] == code_run["id"]

    rejected = client.post(
        f"/api/projects/{project_id}/code/reject",
        json={"codeRunId": code_run["id"], "reason": "需要改阈值"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["codeRun"]["status"] == CodeRunStatus.REJECTED.value

    rolled_back = client.post(
        f"/api/projects/{project_id}/code/rollback",
        json={"codeRunId": code_run["id"]},
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["codeRun"]["status"] == CodeRunStatus.ROLLED_BACK.value
    assert rolled_back.json()["codeRun"]["staleReason"] == "代码草稿已回滚，未写入项目工作区。"


def test_watering_generation_rejects_incomplete_project_tree(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    incomplete = json.dumps(
        {
            "files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "print('incomplete watering project')\n",
                },
                {
                    "path": "src/config.py",
                    "language": "python",
                    "content": "PUMP_MAX_RUN_MS = 3000\n",
                },
            ],
            "summary": "缺少驱动和说明文件",
        },
        ensure_ascii=False,
    )
    provider = SequenceProvider([incomplete, incomplete])
    monkeypatch.setattr(code_router, "provider_factory", lambda: provider)

    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    )

    assert generated.status_code == 422
    assert generated.json()["detail"]["code"] == "LOCAL_OUTPUT_REJECTED"
    assert provider.calls == 2
    assert client.get(f"/api/projects/{project_id}/code/current").status_code == 404


def test_user_code_edit_creates_unvalidated_version_and_preserves_base(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    accepted = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": generated["id"]},
    ).json()["codeRun"]
    edited_files = [
        {
            "path": file["path"],
            "content": (
                file["content"] + "\n# 用户把浇水阈值改为 35\n"
                if file["path"] == "src/config.py"
                else file["content"]
            ),
        }
        for file in accepted["files"]
    ]

    response = client.put(
        f"/api/projects/{project_id}/code/{accepted['id']}",
        json={
            "baseCodeRunId": accepted["id"],
            "files": edited_files,
            "summary": "把浇水阈值改为 35",
        },
    )

    assert response.status_code == 200
    revised = response.json()["codeRun"]
    assert revised["version"] == accepted["version"] + 1
    assert revised["status"] == CodeRunStatus.DRAFT.value
    assert revised["revisionSource"] == "USER"
    assert revised["requiresValidation"] is True
    assert revised["patch"]["baseSnapshotId"] == accepted["id"]
    assert "src/config.py" in revised["patch"]["diff"]
    assert revised["testResult"]["ok"] is False
    assert revised["testResult"]["command"] == "not-run-user-edit"

    preserved = client.get(
        f"/api/projects/{project_id}/code/{accepted['id']}"
    ).json()["codeRun"]
    assert preserved["status"] == CodeRunStatus.ACCEPTED.value

    artifacts = ArtifactRepository(ProjectRepository(tmp_path).db_path).list_artifacts(project_id)
    code_artifact = next(artifact for artifact in artifacts if artifact.sourceAgentId == "code-agent")
    assert code_artifact.currentVersionId == revised["artifactVersionId"]
    assert code_artifact.versions[0].status == ArtifactStatus.DRAFT
    assert code_artifact.versions[0].preview.summary.startswith("用户修改：")

    smart_context = ContextAssembler(ProjectRepository(tmp_path).db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请审查我刚修改的 MicroPython 代码",
        )
    )
    assert smart_context.currentCode is not None
    assert smart_context.currentCode["modifiedByUser"] is True
    assert smart_context.currentCode["requiresValidation"] is True
    assert "浇水阈值改为 35" in smart_context.currentCode["changeSummary"]
    assert smart_context.currentCode["testResult"] == revised["testResult"]
    assert any(
        "浇水阈值改为 35" in file.get("content", "")
        for file in smart_context.currentCode["files"]
    )
    guide_context = ContextAssembler(ProjectRepository(tmp_path).db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="请审查代码",
        )
    )
    assert guide_context.currentCode is None

    stale = client.put(
        f"/api/projects/{project_id}/code/{accepted['id']}",
        json={
            "baseCodeRunId": accepted["id"],
            "files": edited_files,
            "summary": "再次使用旧版本保存",
        },
    )
    assert stale.status_code == 409
    assert stale.json()["detail"]["code"] == "CODE_REVISION_CONFLICT"

    validated_response = client.post(
        f"/api/projects/{project_id}/code/validate",
        json={"codeRunId": revised["id"]},
    )
    assert validated_response.status_code == 200
    validated = validated_response.json()["codeRun"]
    assert validated["id"] == revised["id"]
    assert validated["status"] == CodeRunStatus.READY_FOR_REVIEW.value
    assert validated["requiresValidation"] is False
    assert [check["kind"] for check in validated["testResult"]["checks"]] == [
        "STATIC",
        "SYNTAX",
    ]
    assert all(
        check["exitCode"] == 0
        for check in validated["testResult"]["checks"]
    )

    validated_context = ContextAssembler(ProjectRepository(tmp_path).db_path).assemble(
        ContextAssemblyInput(
            projectId=project_id,
            expert=ExpertType.SMART_ENGINEER,
            userMessage="请根据我保存的新代码和验证结果继续审查。",
        )
    )
    assert validated_context.currentCode is not None
    assert validated_context.currentCode["codeRunId"] == revised["id"]
    assert validated_context.currentCode["testResult"] == validated["testResult"]

    workspace = ProjectRepository(tmp_path).get_workspace(project_id)
    smart_expert = next(
        expert
        for expert in workspace.experts
        if expert.expertType == ExpertType.SMART_ENGINEER
    )
    provider = _ContextCaptureProvider()
    asyncio.run(
        ExpertRuntime(ProjectRepository(tmp_path).db_path).run(
            request=ExpertRuntimeRequest(
                projectId=project_id,
                projectExpertId=smart_expert.id,
                conversationId=smart_expert.conversationId,
                expertType=ExpertType.SMART_ENGINEER,
                userMessage="请根据我保存的新代码和验证结果继续审查。",
                model=LLMModelId.DEEPSEEK_V4_FLASH,
            ),
            provider=provider,
            config=LLMConfig(),
            api_key="fake-test-key",
        )
    )
    provider_payload = "\n".join(
        message.content for message in provider.requests[0].messages
    )
    assert revised["id"] in provider_payload
    assert "把浇水阈值改为 35" in provider_payload
    assert "用户把浇水阈值改为 35" in provider_payload
    assert '"exitCode": 0' in provider_payload


def test_user_code_edit_rejects_missing_or_unknown_files(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]

    response = client.put(
        f"/api/projects/{project_id}/code/{generated['id']}",
        json={
            "baseCodeRunId": generated["id"],
            "files": [{"path": "../main.py", "content": "print('unsafe')"}],
            "summary": "错误路径",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODE_REVISION_INVALID"


def test_validate_rejects_stale_code_run_before_starting_validation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    revised = client.put(
        f"/api/projects/{project_id}/code/{generated['id']}",
        json={
            "baseCodeRunId": generated["id"],
            "files": [
                {
                    "path": file["path"],
                    "content": (
                        file["content"] + "\n# 当前用户版本\n"
                        if file["path"] == "src/config.py"
                        else file["content"]
                    ),
                }
                for file in generated["files"]
            ],
            "summary": "创建当前用户版本",
        },
    ).json()["codeRun"]

    def unexpected_validation(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("旧版本冲突不应启动本地验证")

    monkeypatch.setattr(
        "zhangwen.code_agent.router.run_micropython_validation",
        unexpected_validation,
    )

    response = client.post(
        f"/api/projects/{project_id}/code/validate",
        json={"codeRunId": generated["id"]},
    )

    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "CODE_VALIDATION_CONFLICT",
        "message": "代码已经产生新版本，请刷新后验证当前版本。",
        "retryable": True,
    }
    current = client.get(f"/api/projects/{project_id}/code/current").json()[
        "codeRun"
    ]
    assert current["id"] == revised["id"]
    assert current["requiresValidation"] is True
    assert current["testResult"]["command"] == "not-run-user-edit"


def test_user_code_edit_rejects_blank_summary(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    edited_files = [
        {
            "path": file["path"],
            "content": (
                file["content"] + "\n# 用户修改\n"
                if file["path"] == "src/main.py"
                else file["content"]
            ),
        }
        for file in generated["files"]
    ]

    response = client.put(
        f"/api/projects/{project_id}/code/{generated['id']}",
        json={
            "baseCodeRunId": generated["id"],
            "files": edited_files,
            "summary": "  \t  ",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODE_REVISION_INVALID"
    assert response.json()["detail"]["message"] == "代码变更摘要不能为空。"


def test_user_code_edit_rejects_hardcoded_credentials(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    files = [
        {
            "path": file["path"],
            "content": (
                "WIFI_PASSWORD = 'fake-secret-value'\n"
                if file["path"] == "src/config.py"
                else file["content"]
            ),
        }
        for file in generated["files"]
    ]

    response = client.put(
        f"/api/projects/{project_id}/code/{generated['id']}",
        json={
            "baseCodeRunId": generated["id"],
            "files": files,
            "summary": "错误地写入凭据",
        },
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODE_REVISION_INVALID"
    assert "硬编码凭据" in response.json()["detail"]["message"]
    current = client.get(f"/api/projects/{project_id}/code/current").json()["codeRun"]
    assert current["id"] == generated["id"]


def test_failed_user_code_validation_cannot_be_accepted(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    files = [
        {
            "path": file["path"],
            "content": (
                "def broken(:\n    return 1\n"
                if file["path"] == "src/main.py"
                else file["content"]
            ),
        }
        for file in generated["files"]
    ]
    revised = client.put(
        f"/api/projects/{project_id}/code/{generated['id']}",
        json={
            "baseCodeRunId": generated["id"],
            "files": files,
            "summary": "加入语法错误以验证失败路径",
        },
    ).json()["codeRun"]

    response = client.post(
        f"/api/projects/{project_id}/code/validate",
        json={"codeRunId": revised["id"]},
    )

    assert response.status_code == 200
    failed = response.json()["codeRun"]
    assert failed["status"] == CodeRunStatus.FAILED.value
    checks = {check["kind"]: check for check in failed["testResult"]["checks"]}
    assert checks["SYNTAX"]["exitCode"] not in (None, 0)
    assert set(checks) == {"STATIC", "SYNTAX"}
    accepted = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": revised["id"]},
    )
    assert accepted.status_code == 422
    assert accepted.json()["detail"]["code"] == "CODE_ACCEPT_FAILED"


def test_validation_status_and_output_cannot_override_real_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]

    def contradictory_result(*_args: object, **_kwargs: object) -> CodeTestResult:
        return CodeTestResult(
            ok=True,
            command="micropython-local-validation",
            output="PASS",
            createdAt="2026-07-12T00:00:00Z",
            checks=[
                CodeValidationCheck(
                    kind=CodeValidationKind.STATIC,
                    status=CodeValidationStatus.PASSED,
                    command="micropython-static-worker",
                    exitCode=7,
                    output="PASS",
                ),
                CodeValidationCheck(
                    kind=CodeValidationKind.SYNTAX,
                    status=CodeValidationStatus.FAILED,
                    command="micropython-syntax-worker",
                    exitCode=0,
                    output="reported failure",
                ),
            ],
        )

    monkeypatch.setattr(
        "zhangwen.code_agent.router.run_micropython_validation",
        contradictory_result,
    )

    response = client.post(
        f"/api/projects/{project_id}/code/validate",
        json={"codeRunId": generated["id"]},
    )

    assert response.status_code == 200
    code_run = response.json()["codeRun"]
    checks = {check["kind"]: check for check in code_run["testResult"]["checks"]}
    assert code_run["status"] == CodeRunStatus.FAILED.value
    assert code_run["testResult"]["ok"] is False
    assert checks["STATIC"]["status"] == CodeValidationStatus.FAILED.value
    assert checks["STATIC"]["exitCode"] == 7
    assert checks["SYNTAX"]["status"] == CodeValidationStatus.PASSED.value
    assert checks["SYNTAX"]["exitCode"] == 0


def test_accept_ignores_and_preserves_historical_simulation_result(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    historical_result = generated["testResult"]
    historical_result["ok"] = False
    historical_result["checks"].append(
        {
            "kind": "SIMULATION",
            "status": "FAILED",
            "command": "legacy-simulation-worker",
            "exitCode": 1,
            "output": "历史模拟失败记录",
        }
    )
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        conn.execute(
            "UPDATE code_runs SET test_result_json = ? WHERE id = ?",
            (json.dumps(historical_result, ensure_ascii=False), generated["id"]),
        )

    response = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": generated["id"]},
    )

    assert response.status_code == 200
    accepted = response.json()["codeRun"]
    assert accepted["status"] == CodeRunStatus.ACCEPTED.value
    assert accepted["testResult"] == historical_result


def test_accept_requires_both_current_validation_exit_codes(tmp_path: Path) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    incomplete_result = generated["testResult"]
    incomplete_result["checks"] = [
        check
        for check in incomplete_result["checks"]
        if check["kind"] == "STATIC"
    ]
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        conn.execute(
            "UPDATE code_runs SET test_result_json = ? WHERE id = ?",
            (json.dumps(incomplete_result, ensure_ascii=False), generated["id"]),
        )

    response = client.post(
        f"/api/projects/{project_id}/code/accept",
        json={"codeRunId": generated["id"]},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "CODE_ACCEPT_FAILED"


def test_concurrent_user_code_edits_allow_only_one_new_version(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    project_id, spec_id = _project_with_spec(tmp_path, approved_spec=True)
    generated = client.post(
        f"/api/projects/{project_id}/code/generate",
        json={"specRunId": spec_id},
    ).json()["codeRun"]
    db_path = ProjectRepository(tmp_path).db_path
    original_get_current = CodeRepository.get_current_code
    synchronized_reads = threading.Barrier(2)
    simultaneous_start = threading.Barrier(2)

    def synchronized_get_current(
        repository: CodeRepository,
        candidate_project_id: str,
    ) -> CodeRun | None:
        current = original_get_current(repository, candidate_project_id)
        synchronized_reads.wait(timeout=5)
        return current

    monkeypatch.setattr(CodeRepository, "get_current_code", synchronized_get_current)

    def save_revision(marker: str) -> str:
        files = [
            EditableCodeFile(
                path=file["path"],
                content=(
                    file["content"] + f"\n# {marker}\n"
                    if file["path"] == "src/config.py"
                    else file["content"]
                ),
            )
            for file in generated["files"]
        ]
        simultaneous_start.wait(timeout=5)
        try:
            CodeRepository(db_path).revise_from_user(
                project_id=project_id,
                base_code_run_id=generated["id"],
                files=files,
                summary=marker,
            )
        except CodeRevisionConflictError:
            return "conflict"
        return "saved"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(save_revision, ("并发修改 A", "并发修改 B")))

    assert sorted(results) == ["conflict", "saved"]
    with sqlite3.connect(db_path) as conn:
        versions = [
            int(row[0])
            for row in conn.execute(
                "SELECT version FROM code_runs WHERE project_id = ? ORDER BY version",
                (project_id,),
            ).fetchall()
        ]
    assert versions == [generated["version"], generated["version"] + 1]


def _project_with_spec(tmp_path: Path, *, approved_spec: bool) -> tuple[str, str]:
    client = TestClient(app)
    project_id = _create_project(client)
    db_path = ProjectRepository(tmp_path).db_path
    solution = SolutionRepository(db_path).confirm_solution(
        project_id,
        SolutionRepository(db_path).create_solution(
            project_id,
            [
                SolutionSection(id="goal", title="项目目标", content="做一个自动浇花装置"),
                SolutionSection(id="hardware", title="硬件方案", content="ESP32-S3 + 传感器"),
                SolutionSection(id="software", title="软件方案", content="MicroPython 控制水泵"),
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
    spec = client.post(
        f"/api/projects/{project_id}/spec/generate",
        json={"proposalId": proposal.id},
    ).json()["spec"]
    if approved_spec:
        spec = client.post(
            f"/api/projects/{project_id}/spec/confirm",
            json={"specRunId": spec["id"]},
        ).json()["spec"]
        assert spec["status"] == SpecRunStatus.APPROVED.value
    return project_id, spec["id"]


def _create_project(client: TestClient) -> str:
    response = client.post(
        "/api/projects",
        json={
            "name": "测试项目",
            "initialIdea": "测试创意",
            "selectedExpertTypes": [ExpertType.SMART_ENGINEER.value],
        },
    )
    assert response.status_code == 200
    return str(response.json()["workspace"]["project"]["id"])


class _ContextCaptureProvider:
    def __init__(self) -> None:
        self.requests: list[object] = []

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        self.requests.append(request)
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=json.dumps(
                {"content": "已读取用户保存的新版本和本地验证结果。"},
                ensure_ascii=False,
            ),
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )
