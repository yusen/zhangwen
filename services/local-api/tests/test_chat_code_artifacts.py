from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.fakes import FakeCredentialStore
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.chat import router as chat_router
from zhangwen.code_agent.chat_code import (
    ChatCodeService,
    chat_code_draft_from_markdown,
)
from zhangwen.code_agent.models import (
    ChatCodeDraft,
    ChatCodeFileDraft,
    CodeRunStatus,
    CodeTestResult,
    CodeValidationCheck,
    CodeValidationKind,
    CodeValidationStatus,
    EditableCodeFile,
    CodeRun,
)
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.config import settings
from zhangwen.experts.runtime import ExpertRuntime, ExpertRuntimeOutput
from zhangwen.llm.contracts import (
    ChatMessageStatus,
    LLMModelId,
    StreamChunk,
    StreamChunkType,
)
from zhangwen.main import app
from zhangwen.projects.migrations import _migrate_v23
from zhangwen.projects.models import ExpertType
from zhangwen.projects.repository import ProjectRepository


class _ChatCodeProvider:
    calls = 0

    async def stream_chat(
        self,
        request,
        config,
        api_key,
        cancel_token,
        request_id,
        message_id,
    ):
        type(self).calls += 1
        content = json.dumps(
            {
                "content": "代码草稿已生成，请在代码产物中查看并运行本地验证。",
                "uiPayload": {
                    "type": "code_artifact",
                    "artifactId": "provider_forged_artifact",
                    "codeRunId": "provider_forged_code",
                },
                "codeDraft": _chat_draft_payload("screen.refresh()"),
            },
            ensure_ascii=False,
        )
        yield StreamChunk(
            requestId=request_id,
            messageId=message_id,
            type=StreamChunkType.COMPLETED,
            accumulatedContent=content,
            model=LLMModelId.DEEPSEEK_V4_FLASH,
        )


def test_v23_migration_preserves_code_graph_and_makes_spec_nullable(
    tmp_path: Path,
) -> None:
    conn = sqlite3.connect(tmp_path / "v22.sqlite3")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(
        """
        CREATE TABLE projects (id TEXT PRIMARY KEY);
        CREATE TABLE spec_runs (id TEXT PRIMARY KEY);
        CREATE TABLE schema_migration_audit (
          id TEXT PRIMARY KEY,
          from_version INTEGER NOT NULL,
          to_version INTEGER NOT NULL,
          status TEXT NOT NULL,
          backup_path TEXT NULL,
          applied_at TEXT NOT NULL
        );
        CREATE TABLE code_runs (
          id TEXT PRIMARY KEY,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          spec_run_id TEXT NOT NULL REFERENCES spec_runs(id) ON DELETE RESTRICT,
          version INTEGER NOT NULL,
          status TEXT NOT NULL,
          workspace_root TEXT NOT NULL,
          max_retries INTEGER NOT NULL,
          retries INTEGER NOT NULL,
          test_result_json TEXT NOT NULL,
          artifact_id TEXT NULL,
          artifact_version_id TEXT NULL,
          hardware_solution_version INTEGER NULL,
          bom_version INTEGER NULL,
          io_map_version INTEGER NULL,
          generated_by_expert_id TEXT NULL,
          stale_reason TEXT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL,
          accepted_at TEXT NULL
        );
        CREATE INDEX idx_code_runs_project ON code_runs(project_id, version);
        CREATE TABLE code_files (
          id TEXT PRIMARY KEY,
          code_run_id TEXT NOT NULL REFERENCES code_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          kind TEXT NOT NULL,
          path TEXT NOT NULL,
          language TEXT NOT NULL,
          content TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        CREATE INDEX idx_code_files_run ON code_files(code_run_id, path);
        CREATE TABLE code_patches (
          id TEXT PRIMARY KEY,
          code_run_id TEXT NOT NULL UNIQUE REFERENCES code_runs(id) ON DELETE CASCADE,
          project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE RESTRICT,
          base_snapshot_id TEXT NULL,
          summary TEXT NOT NULL,
          diff TEXT NOT NULL,
          created_at TEXT NOT NULL
        );
        INSERT INTO projects VALUES ('project_v22');
        INSERT INTO spec_runs VALUES ('spec_v22');
        INSERT INTO code_runs VALUES (
          'code_v22', 'project_v22', 'spec_v22', 7, 'ACCEPTED',
          'workspace://project_v22/code/v7', 2, 1, '{"ok": true}',
          'artifact_code', 'artifact_version_code', 3, 4, 5, 'expert_smart',
          NULL, 'created', 'updated', 'accepted'
        );
        INSERT INTO code_files VALUES (
          'file_v22', 'code_v22', 'project_v22', 'MAIN', 'src/main.py',
          'python', 'print(1)', 'created'
        );
        INSERT INTO code_patches VALUES (
          'patch_v22', 'code_v22', 'project_v22', NULL, 'summary', 'diff', 'created'
        );
        PRAGMA user_version=22;
        """
    )
    conn.commit()

    _migrate_v23(conn)
    conn.commit()

    columns = {row["name"]: row for row in conn.execute("PRAGMA table_info(code_runs)")}
    assert columns["spec_run_id"]["notnull"] == 0
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 23
    assert dict(conn.execute("SELECT * FROM code_runs WHERE id = 'code_v22'").fetchone()) == {
        "id": "code_v22",
        "project_id": "project_v22",
        "spec_run_id": "spec_v22",
        "version": 7,
        "status": "ACCEPTED",
        "workspace_root": "workspace://project_v22/code/v7",
        "max_retries": 2,
        "retries": 1,
        "test_result_json": '{"ok": true}',
        "artifact_id": "artifact_code",
        "artifact_version_id": "artifact_version_code",
        "hardware_solution_version": 3,
        "bom_version": 4,
        "io_map_version": 5,
        "generated_by_expert_id": "expert_smart",
        "stale_reason": None,
        "created_at": "created",
        "updated_at": "updated",
        "accepted_at": "accepted",
    }
    assert conn.execute("SELECT content FROM code_files").fetchone()[0] == "print(1)"
    assert conn.execute("SELECT summary FROM code_patches").fetchone()[0] == "summary"
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    assert {
        row["name"] for row in conn.execute("PRAGMA index_list(code_runs)")
    } >= {"idx_code_runs_project"}
    assert {
        row["table"] for row in conn.execute("PRAGMA foreign_key_list(code_files)")
    } == {"code_runs", "projects"}
    conn.execute(
        """
        INSERT INTO code_runs (
          id, project_id, spec_run_id, version, status, workspace_root,
          max_retries, retries, test_result_json, stale_reason, created_at, updated_at
        ) VALUES ('code_chat', 'project_v22', NULL, 8, 'DRAFT', 'workspace://chat',
                  2, 0, '{"ok": false}', NULL, 'created', 'updated')
        """
    )
    assert conn.execute(
        "SELECT spec_run_id FROM code_runs WHERE id = 'code_chat'"
    ).fetchone()[0] is None
    conn.close()


def test_chat_code_is_idempotent_and_full_lifecycle_works_without_spec(
    tmp_path: Path,
) -> None:
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project(
        name="聊天代码",
        initial_idea="用 MicroPython 显示圆形",
        selected_expert_types=[ExpertType.SMART_ENGINEER],
    )
    expert = workspace.experts[0]
    _, _, assistant = repository.append_user_and_assistant(
        workspace.project.id,
        "生成代码",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
    )
    service = ChatCodeService(repository.db_path)
    first = service.materialize(
        project_id=workspace.project.id,
        source_message_id=assistant.id,
        generated_by_expert_id=expert.id,
        draft=_chat_draft("screen.refresh()"),
    )
    duplicate = service.materialize(
        project_id=workspace.project.id,
        source_message_id=assistant.id,
        generated_by_expert_id=expert.id,
        draft=_chat_draft("raise AssertionError('must not replace immutable code')"),
    )

    assert duplicate.id == first.id
    assert duplicate.version == first.version == 1
    assert duplicate.specRunId is None
    assert duplicate.status == CodeRunStatus.DRAFT
    assert duplicate.requiresValidation is True
    assert duplicate.artifactId == f"artifact_code_{workspace.project.id}"
    assert "screen.refresh()" in _file_content(duplicate, "src/main.py")
    assert "must not replace" not in _file_content(duplicate, "src/main.py")

    code_repository = CodeRepository(repository.db_path)
    revised = code_repository.revise_from_user(
        project_id=workspace.project.id,
        base_code_run_id=first.id,
        files=[
            EditableCodeFile(
                path=file.path,
                content=file.content + ("\n# user edit\n" if file.path == "src/main.py" else ""),
            )
            for file in first.files
        ],
        summary="用户调整显示逻辑",
    )
    assert revised.specRunId is None
    assert revised.version == 2
    validated = code_repository.validate_code(
        workspace.project.id,
        revised.id,
        _passed_validation(),
    )
    assert validated.status == CodeRunStatus.READY_FOR_REVIEW
    accepted = code_repository.accept_code(workspace.project.id, revised.id)
    assert accepted.status == CodeRunStatus.ACCEPTED
    rejected = code_repository.reject_code(workspace.project.id, revised.id, "重新检查")
    assert rejected.status == CodeRunStatus.REJECTED
    rolled_back = code_repository.rollback_code(workspace.project.id, revised.id)
    assert rolled_back.status == CodeRunStatus.ROLLED_BACK
    artifact = ArtifactRepository(repository.db_path).get_artifact(
        workspace.project.id,
        str(first.artifactId),
    )
    assert len(artifact.versions) == 2


def test_runtime_rejects_code_draft_from_other_experts(tmp_path: Path) -> None:
    repository = ProjectRepository(tmp_path)
    output = ExpertRuntimeOutput(
        content="代码草稿已准备。",
        codeDraft=_chat_draft(),
    )

    with pytest.raises(ValueError, match="Only smart_engineer"):
        ExpertRuntime(repository.db_path)._validate_boundaries(
            ExpertType.STRUCTURE_ENGINEER,
            output,
        )

    invalid_payload = _chat_draft_payload()
    invalid_payload["files"].append(
        {"path": "src/lib/unsafe.py", "language": "python", "content": "VALUE = 1\n"}
    )
    invalid_output = ExpertRuntimeOutput(
        content="代码草稿已准备。",
        codeDraft=ChatCodeDraft(**invalid_payload),
    )
    with pytest.raises(ValueError, match="只能包含受限 src/"):
        ExpertRuntime(repository.db_path)._validate_boundaries(
            ExpertType.SMART_ENGINEER,
            invalid_output,
        )


def test_project_chat_materializes_server_owned_code_artifact(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings.data_dir = tmp_path
    _ChatCodeProvider.calls = 0
    monkeypatch.setattr(chat_router, "credential_store_factory", FakeCredentialStore)
    monkeypatch.setattr(chat_router, "provider_factory", _ChatCodeProvider)
    client = TestClient(app)
    workspace = client.post(
        "/api/projects",
        json={
            "name": "聊天生成代码",
            "initialIdea": "行空板显示圆形",
            "selectedExpertTypes": ["smart_engineer"],
        },
    ).json()["workspace"]
    project_id = workspace["project"]["id"]
    expert = workspace["experts"][0]
    request = {
        "content": "生成 MicroPython 代码",
        "model": "deepseek-v4-flash",
        "projectExpertId": expert["id"],
        "expertType": "smart_engineer",
        "clientTurnId": "client_chat_code_1",
    }

    response = client.post(f"/api/projects/{project_id}/chat/stream", json=request)
    duplicate = client.post(f"/api/projects/{project_id}/chat/stream", json=request)

    assert response.status_code == duplicate.status_code == 200
    payload = _chunks(response.text)[-1]["structuredPayload"]
    assert payload["type"] == "code_artifact"
    assert payload["artifactId"] == f"artifact_code_{project_id}"
    assert payload["artifactId"] != "provider_forged_artifact"
    assert payload["codeRunId"] != "provider_forged_code"
    assert payload["status"] == "DRAFT"
    assert [file["path"] for file in payload["files"]] == ["src/main.py"]
    assert _chunks(duplicate.text)[-1]["structuredPayload"] == payload
    assert _ChatCodeProvider.calls == 1
    current = client.get(f"/api/projects/{project_id}/code/current").json()["codeRun"]
    assert current["id"] == payload["codeRunId"]
    assert current["specRunId"] is None
    with sqlite3.connect(ProjectRepository(tmp_path).db_path) as conn:
        assert conn.execute(
            "SELECT COUNT(*) FROM code_runs WHERE project_id = ?",
            (project_id,),
        ).fetchone()[0] == 1


def test_import_message_extracts_fenced_python_and_enforces_message_boundaries(
    tmp_path: Path,
) -> None:
    settings.data_dir = tmp_path
    client = TestClient(app)
    repository = ProjectRepository(tmp_path)
    workspace = repository.create_project(
        name="历史导入",
        initial_idea="导入旧回复",
        selected_expert_types=[
            ExpertType.SMART_ENGINEER,
            ExpertType.STRUCTURE_ENGINEER,
        ],
    )
    expert = next(
        item for item in workspace.experts if item.expertType == ExpertType.SMART_ENGINEER
    )
    structure_expert = next(
        item
        for item in workspace.experts
        if item.expertType == ExpertType.STRUCTURE_ENGINEER
    )
    _, user_message, assistant = repository.append_user_and_assistant(
        workspace.project.id,
        "请生成代码",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
    )
    repository.update_message(
        workspace.project.id,
        assistant.id,
        content=(
            "## 显示圆形\n\n"
            "```python\n"
            "from unihiker_k10 import screen\n"
            "screen.refresh()\n"
            "```\n"
        ),
        status=ChatMessageStatus.COMPLETED,
    )
    legacy = ChatCodeService(repository.db_path).materialize(
        project_id=workspace.project.id,
        source_message_id=assistant.id,
        generated_by_expert_id=expert.id,
        draft=_chat_draft("screen.refresh()"),
    )
    assert legacy.version == 1
    assert [file.path for file in legacy.files] == ["src/main.py"]

    imported = client.post(
        f"/api/projects/{workspace.project.id}/code/import-message",
        json={"messageId": assistant.id},
    )
    duplicate = client.post(
        f"/api/projects/{workspace.project.id}/code/import-message",
        json={"messageId": assistant.id},
    )

    assert imported.status_code == duplicate.status_code == 200
    code_run = imported.json()["codeRun"]
    assert duplicate.json()["codeRun"]["id"] == code_run["id"]
    assert code_run["id"] != legacy.id
    assert code_run["version"] == 2
    assert code_run["patch"]["summary"] == "显示圆形"
    assert [file["path"] for file in code_run["files"]] == ["src/main.py"]
    assert "screen.refresh()" in next(
        file["content"] for file in code_run["files"] if file["path"] == "src/main.py"
    )
    assert "README.md" not in code_run["patch"]["diff"]
    assert "tests/test_logic.py" not in code_run["patch"]["diff"]

    validated = client.post(
        f"/api/projects/{workspace.project.id}/code/validate",
        json={"codeRunId": code_run["id"]},
    )
    assert validated.status_code == 200
    assert validated.json()["codeRun"]["status"] == "READY_FOR_REVIEW"
    assert [
        check["exitCode"]
        for check in validated.json()["codeRun"]["testResult"]["checks"]
    ] == [0, 0]

    revised_content = next(
        file["content"] for file in code_run["files"] if file["path"] == "src/main.py"
    ) + "# 用户保留的修改\n"
    revised = client.put(
        f"/api/projects/{workspace.project.id}/code/{code_run['id']}",
        json={
            "baseCodeRunId": code_run["id"],
            "files": [{"path": "src/main.py", "content": revised_content}],
            "summary": "用户修改导入的主程序",
        },
    )
    assert revised.status_code == 200
    assert revised.json()["codeRun"]["version"] == code_run["version"] + 1
    assert [
        file["path"] for file in revised.json()["codeRun"]["files"]
    ] == ["src/main.py"]
    immutable_original = client.get(
        f"/api/projects/{workspace.project.id}/code/{code_run['id']}"
    ).json()["codeRun"]
    assert "用户保留的修改" not in immutable_original["files"][0]["content"]
    immutable_legacy = client.get(
        f"/api/projects/{workspace.project.id}/code/{legacy.id}"
    ).json()["codeRun"]
    assert [file["path"] for file in immutable_legacy["files"]] == ["src/main.py"]
    non_assistant = client.post(
        f"/api/projects/{workspace.project.id}/code/import-message",
        json={"messageId": user_message.id},
    )
    assert non_assistant.status_code == 422
    assert non_assistant.json()["detail"]["code"] == "CODE_IMPORT_REQUIRES_ASSISTANT"

    _, _, no_code = repository.append_user_and_assistant(
        workspace.project.id,
        "再回复一次",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=expert.id,
    )
    repository.update_message(
        workspace.project.id,
        no_code.id,
        content="这条回复没有代码。",
        status=ChatMessageStatus.COMPLETED,
    )
    no_python = client.post(
        f"/api/projects/{workspace.project.id}/code/import-message",
        json={"messageId": no_code.id},
    )
    assert no_python.status_code == 422
    assert no_python.json()["detail"]["code"] == "CODE_IMPORT_NO_PYTHON"

    _, _, structure_code = repository.append_user_and_assistant(
        workspace.project.id,
        "结构回复",
        LLMModelId.DEEPSEEK_V4_FLASH,
        project_expert_id=structure_expert.id,
    )
    repository.update_message(
        workspace.project.id,
        structure_code.id,
        content="```python\nprint('not smart engineer')\n```",
        status=ChatMessageStatus.COMPLETED,
    )
    wrong_expert = client.post(
        f"/api/projects/{workspace.project.id}/code/import-message",
        json={"messageId": structure_code.id},
    )
    assert wrong_expert.status_code == 422
    assert (
        wrong_expert.json()["detail"]["code"]
        == "CODE_IMPORT_REQUIRES_SMART_ENGINEER"
    )

    other = repository.create_project(
        name="其他项目",
        initial_idea="隔离",
        selected_expert_types=[ExpertType.SMART_ENGINEER],
    )
    cross_project = client.post(
        f"/api/projects/{other.project.id}/code/import-message",
        json={"messageId": assistant.id},
    )
    assert cross_project.status_code == 422
    assert cross_project.json()["detail"]["code"] == "CODE_IMPORT_PROJECT_MISMATCH"


def test_markdown_import_keeps_only_explicit_uploadable_python_files() -> None:
    draft = chat_code_draft_from_markdown(
        """
# 多文件主程序

```python ../escape.py
raise AssertionError("unsafe path must not become main")
```

```python src/config.py
RADIUS = 60
```

```python src/drivers.py
def draw():
    return True
```

```python tests/test_logic.py
raise AssertionError("tests are not uploaded")
```

```micropython src/main.py
from drivers import draw
draw()
```
"""
    )

    assert [file.path for file in draft.files] == [
        "src/main.py",
        "src/config.py",
        "src/drivers.py",
    ]
    assert all(file.language == "python" for file in draft.files)
    assert all("unsafe path" not in file.content for file in draft.files)
    assert all("tests are not uploaded" not in file.content for file in draft.files)


def test_markdown_import_rejects_python_fence_with_only_unsafe_path() -> None:
    with pytest.raises(ValueError, match="MicroPython 主程序"):
        chat_code_draft_from_markdown(
            "```python ../main.py\nprint('must not import')\n```"
        )


def _chat_draft(main_suffix: str = "") -> ChatCodeDraft:
    payload = _chat_draft_payload(main_suffix)
    return ChatCodeDraft(**payload)


def _chat_draft_payload(main_suffix: str = "") -> dict[str, object]:
    main = "from unihiker_k10 import screen\n" + main_suffix.strip() + "\n"
    return {
        "summary": "生成行空板显示代码",
        "files": [
            {"path": "src/main.py", "language": "python", "content": main},
        ],
    }


def _passed_validation() -> CodeTestResult:
    checks = [
        CodeValidationCheck(
            kind=kind,
            status=CodeValidationStatus.PASSED,
            command=f"validate-{kind.value.lower()}",
            exitCode=0,
            output="通过",
        )
        for kind in (CodeValidationKind.STATIC, CodeValidationKind.SYNTAX)
    ]
    return CodeTestResult(
        ok=True,
        command="micropython-local-validation",
        output="全部通过",
        createdAt="2026-07-11T00:00:00Z",
        checks=checks,
    )


def _file_content(code_run: CodeRun, path: str) -> str:
    return next(file.content for file in code_run.files if file.path == path)


def _chunks(body: str) -> list[dict[str, object]]:
    return [
        json.loads(line.removeprefix("data: "))
        for line in body.splitlines()
        if line.startswith("data: ")
    ]
