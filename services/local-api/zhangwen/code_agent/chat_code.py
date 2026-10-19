"""Materialize bounded chat code drafts without giving the provider host access."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from markdown_it import MarkdownIt

from zhangwen.code_agent.board_api_contracts import validate_board_api_files
from zhangwen.code_agent.generator import GeneratedCode, GeneratedCodeFile
from zhangwen.code_agent.models import (
    ChatCodeDraft,
    ChatCodeFileDraft,
    CodeFileKind,
    CodeRun,
    CodeRuntime,
)
from zhangwen.code_agent.repository import CodeRepository
from zhangwen.code_agent.validation import (
    is_uploadable_lua_path,
    is_uploadable_python_path,
    pending_validation_result,
    validate_storable_code_files,
)


_PYTHON_FENCE_NAMES = frozenset({"micropython", "py", "python"})
_IMPORT_IDEMPOTENCY_SCOPE = "markdown-upload-python-v1"


class ChatCodeImportError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ChatCodeService:
    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._repository = CodeRepository(db_path)

    def materialize(
        self,
        *,
        project_id: str,
        source_message_id: str,
        generated_by_expert_id: str | None,
        draft: ChatCodeDraft,
        board_contract_id: str | None = None,
        spec_run_id: str | None = None,
    ) -> CodeRun:
        generated = package_chat_code_draft(
            draft,
            now=_now(),
            board_contract_id=board_contract_id,
        )
        return self._repository.create_from_chat_draft(
            project_id=project_id,
            source_message_id=source_message_id,
            generated_by_expert_id=generated_by_expert_id,
            generated=generated,
            spec_run_id=spec_run_id,
        )

    def import_assistant_message(self, *, project_id: str, message_id: str) -> CodeRun:
        with _connect(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT id, project_id, conversation_id, role, content, status, metadata_json
                FROM messages
                WHERE id = ?
                """,
                (message_id,),
            ).fetchone()
            if row is None:
                raise ChatCodeImportError(
                    "CODE_IMPORT_MESSAGE_NOT_FOUND",
                    "要导入的历史消息不存在。",
                )
            if str(row["project_id"]) != project_id:
                raise ChatCodeImportError(
                    "CODE_IMPORT_PROJECT_MISMATCH",
                    "不能从其他项目导入代码消息。",
                )
            if str(row["role"]) != "assistant" or str(row["status"]) != "COMPLETED":
                raise ChatCodeImportError(
                    "CODE_IMPORT_REQUIRES_ASSISTANT",
                    "只能从本项目已完成的智能工程师回复导入代码。",
                )
            message_expert = _message_expert(conn, row)
            if message_expert is None or message_expert[1] != "smart_engineer":
                raise ChatCodeImportError(
                    "CODE_IMPORT_REQUIRES_SMART_ENGINEER",
                    "只能从本项目已完成的智能工程师回复导入代码。",
                )
            generated_by_expert_id = message_expert[0]
            content = str(row["content"])

        try:
            draft = chat_code_draft_from_markdown(content)
        except ValueError as exc:
            raise ChatCodeImportError("CODE_IMPORT_NO_PYTHON", str(exc)) from exc
        generated = package_imported_chat_code_draft(draft, now=_now())
        return self._repository.create_from_chat_draft(
            project_id=project_id,
            source_message_id=message_id,
            generated_by_expert_id=generated_by_expert_id,
            generated=generated,
            idempotency_scope=_IMPORT_IDEMPOTENCY_SCOPE,
        )


def package_chat_code_draft(
    draft: ChatCodeDraft,
    *,
    now: str,
    board_contract_id: str | None = None,
) -> GeneratedCode:
    normalized_summary = draft.summary.strip()
    if not normalized_summary:
        raise ValueError("代码变更摘要不能为空。")
    files_by_path = {file.path: file for file in draft.files}
    paths = set(files_by_path)
    entrypoint = _runtime_entrypoint(draft.runtime)
    if entrypoint not in paths:
        raise ValueError(f"聊天代码必须包含可上传入口 {entrypoint}。")
    if not all(
        _is_chat_project_path(
            path,
            files_by_path[path].language,
            runtime=draft.runtime,
        )
        for path in paths
    ):
        if draft.runtime == CodeRuntime.ESP_CLAW_LUA:
            raise ValueError(
                "ESP-Claw 聊天代码只能包含受限 scripts/**/*.lua 和 README.md。"
            )
        raise ValueError("聊天代码只能包含受限 src/ MicroPython 文件和 README.md。")

    files: list[GeneratedCodeFile] = []
    for path in _ordered_upload_paths(paths, entrypoint=entrypoint):
        candidate = files_by_path[path]
        expected_language = (
            "markdown"
            if path == "README.md"
            else "lua"
            if draft.runtime == CodeRuntime.ESP_CLAW_LUA
            else "python"
        )
        if candidate.language != expected_language:
            raise ValueError(f"{path} 的语言必须为 {expected_language}。")
        files.append(
            GeneratedCodeFile(
                kind=_upload_file_kind(path),
                path=path,
                language=expected_language,
                content=candidate.content,
            )
        )
    validate_storable_code_files(files, runtime=draft.runtime)
    if draft.runtime == CodeRuntime.MICROPYTHON:
        validate_board_api_files(files, board_contract_id)
    runtime_label = (
        "ESP-Claw Lua"
        if draft.runtime == CodeRuntime.ESP_CLAW_LUA
        else "MicroPython"
    )
    return GeneratedCode(
        files=files,
        diff=_new_file_diff(files),
        summary=normalized_summary,
        test_result=pending_validation_result(
            now=now,
            message=f"聊天代码草稿已保存；尚未运行 {runtime_label} 静态或语法检查。",
            runtime=draft.runtime,
        ).model_copy(update={"command": "not-run-chat-code"}),
        runtime=draft.runtime,
        entrypoint=entrypoint,
    )


def package_imported_chat_code_draft(
    draft: ChatCodeDraft,
    *,
    now: str,
) -> GeneratedCode:
    """Package only device-uploadable Python files extracted from saved Markdown."""

    normalized_summary = draft.summary.strip()
    if not normalized_summary:
        raise ValueError("代码变更摘要不能为空。")
    if draft.runtime != CodeRuntime.MICROPYTHON:
        raise ValueError("历史消息导入只支持 fenced MicroPython 代码。")
    files_by_path = {file.path: file for file in draft.files}
    paths = set(files_by_path)
    if "src/main.py" not in paths:
        raise ValueError("可导入代码必须包含 src/main.py。")
    if not all(
        _is_chat_project_path(
            path,
            files_by_path[path].language,
            runtime=CodeRuntime.MICROPYTHON,
        )
        for path in paths
    ):
        raise ValueError("历史消息只能导入受限 src/ MicroPython 文件和 README.md。")

    files: list[GeneratedCodeFile] = []
    for path in _ordered_upload_paths(paths):
        candidate = files_by_path[path]
        expected_language = "markdown" if path == "README.md" else "python"
        if candidate.language != expected_language:
            raise ValueError(f"{path} 的语言必须为 {expected_language}。")
        files.append(
            GeneratedCodeFile(
                kind=_upload_file_kind(path),
                path=path,
                language=expected_language,
                content=candidate.content,
            )
        )
    validate_storable_code_files(files, runtime=CodeRuntime.MICROPYTHON)
    return GeneratedCode(
        files=files,
        diff=_new_file_diff(files),
        summary=normalized_summary,
        test_result=pending_validation_result(
            now=now,
            message="聊天代码草稿已保存；尚未运行 MicroPython 静态或语法检查。",
        ).model_copy(update={"command": "not-run-chat-code"}),
    )


def chat_code_draft_from_markdown(markdown: str) -> ChatCodeDraft:
    tokens = MarkdownIt("commonmark").parse(markdown)
    extracted: dict[str, str] = {}
    first_heading: str | None = None
    awaiting_heading_content = False

    for token in tokens:
        if token.type == "heading_open" and first_heading is None:
            awaiting_heading_content = True
            continue
        if token.type == "inline" and awaiting_heading_content:
            first_heading = token.content.strip() or None
            awaiting_heading_content = False
            continue
        if token.type != "fence" or not token.content.strip():
            continue
        info_parts = token.info.strip().split()
        language = info_parts[0].lower() if info_parts else ""
        if language not in _PYTHON_FENCE_NAMES:
            continue
        path_hint = next(
            (part for part in info_parts[1:] if part.lower().endswith(".py")),
            None,
        )
        if path_hint is not None:
            target_path = path_hint if is_uploadable_python_path(path_hint) else None
        else:
            target_path = "src/main.py" if "src/main.py" not in extracted else None
        if target_path is not None and target_path not in extracted:
            extracted[target_path] = token.content

    if "src/main.py" not in extracted:
        raise ValueError("该回复中没有可导入的 fenced MicroPython 主程序。")

    summary = (first_heading or "从历史智能工程师回复导入 Python 代码")[:1000]
    return ChatCodeDraft(
        files=[
            ChatCodeFileDraft(
                path=path,
                language="python",
                content=extracted[path],
            )
            for path in _ordered_upload_paths(set(extracted))
        ],
        summary=summary,
    )


def code_artifact_payload(code_run: CodeRun) -> dict[str, object]:
    title = (
        "ESP-Claw Lua 工程代码"
        if code_run.runtime == CodeRuntime.ESP_CLAW_LUA
        else "MicroPython 工程代码"
    )
    return {
        "type": "code_artifact",
        "codeRunId": code_run.id,
        "artifactId": code_run.artifactId,
        "artifactVersionId": code_run.artifactVersionId,
        "version": code_run.version,
        "status": code_run.status.value,
        "runtime": code_run.runtime.value,
        "entrypoint": code_run.entrypoint,
        "title": title,
        "summary": code_run.patch.summary,
        "files": [
            {"path": file.path, "language": file.language}
            for file in code_run.files
        ],
    }


def _new_file_diff(files: list[GeneratedCodeFile]) -> str:
    chunks: list[str] = []
    for file in files:
        chunks.extend(
            [
                f"diff --git a/{file.path} b/{file.path}",
                "new file mode 100644",
                "--- /dev/null",
                f"+++ b/{file.path}",
            ]
        )
        chunks.extend(f"+{line}" for line in file.content.splitlines())
    return "\n".join(chunks) + "\n"


def _ordered_upload_paths(
    paths: set[str],
    *,
    entrypoint: str = "src/main.py",
) -> list[str]:
    return sorted(
        paths,
        key=lambda path: (path == "README.md", path != entrypoint, path),
    )


def _upload_file_kind(path: str) -> CodeFileKind:
    if path in {"src/main.py", "scripts/main.lua"}:
        return CodeFileKind.MAIN
    if path in {"src/config.py", "scripts/config.lua"}:
        return CodeFileKind.CONFIG
    if path == "README.md":
        return CodeFileKind.README
    return CodeFileKind.DRIVER


def _is_chat_project_path(
    path: str,
    language: str,
    *,
    runtime: CodeRuntime,
) -> bool:
    if path == "README.md":
        return language == "markdown"
    if runtime == CodeRuntime.ESP_CLAW_LUA:
        return language == "lua" and is_uploadable_lua_path(path)
    return language == "python" and is_uploadable_python_path(path)


def _runtime_entrypoint(runtime: CodeRuntime) -> str:
    return (
        "scripts/main.lua"
        if runtime == CodeRuntime.ESP_CLAW_LUA
        else "src/main.py"
    )


def _message_expert(
    conn: sqlite3.Connection,
    row: sqlite3.Row,
) -> tuple[str, str] | None:
    metadata = _json_object(row["metadata_json"])
    metadata_expert_id = metadata.get("projectExpertId")
    if isinstance(metadata_expert_id, str):
        match = conn.execute(
            """
            SELECT id, expert_type FROM project_experts
            WHERE id = ? AND project_id = ? AND conversation_id = ?
            """,
            (metadata_expert_id, row["project_id"], row["conversation_id"]),
        ).fetchone()
        if match is not None:
            return str(match["id"]), str(match["expert_type"])
    match = conn.execute(
        """
        SELECT id, expert_type FROM project_experts
        WHERE project_id = ? AND conversation_id = ?
          AND removed_at IS NULL
        ORDER BY added_at ASC
        LIMIT 1
        """,
        (row["project_id"], row["conversation_id"]),
    ).fetchone()
    return (
        (str(match["id"]), str(match["expert_type"]))
        if match is not None
        else None
    )


def _json_object(raw: str | None) -> dict[str, object]:
    if not raw:
        return {}
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return value if isinstance(value, dict) else {}


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _now() -> str:
    return datetime.now(UTC).isoformat()
