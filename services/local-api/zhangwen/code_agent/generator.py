"""Local validation and packaging for provider-generated code drafts."""

from __future__ import annotations

from dataclasses import dataclass

from zhangwen.code_agent.board_api_contracts import validate_board_api_files
from zhangwen.code_agent.models import (
    CodeContentDraft,
    CodeFileKind,
    CodeRuntime,
    CodeTestResult,
)
from zhangwen.code_agent.validation import (
    is_uploadable_lua_path,
    is_uploadable_python_path,
    pending_validation_result,
    validate_storable_code_files,
)
from zhangwen.specs.models import SpecRun


@dataclass(frozen=True)
class GeneratedCodeFile:
    kind: CodeFileKind
    path: str
    language: str
    content: str


@dataclass(frozen=True)
class GeneratedCode:
    files: list[GeneratedCodeFile]
    diff: str
    summary: str
    test_result: CodeTestResult
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON
    entrypoint: str = "src/main.py"


def validate_and_package_code(
    spec: SpecRun,
    draft: CodeContentDraft,
    *,
    now: str,
    board_contract_id: str | None = None,
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON,
) -> GeneratedCode:
    entrypoint = _entrypoint(runtime)
    files = [
        GeneratedCodeFile(
            _file_kind(candidate.path),
            candidate.path,
            candidate.language,
            candidate.content,
        )
        for candidate in sorted(
            draft.files,
            key=lambda item: (item.path != entrypoint, item.path),
        )
    ]
    _validate_files(
        files,
        runtime=runtime,
        board_contract_id=(
            board_contract_id if runtime == CodeRuntime.MICROPYTHON else None
        ),
        required_paths=(
            _required_paths(spec) if runtime == CodeRuntime.MICROPYTHON else set()
        ),
    )
    runtime_label = (
        "MicroPython"
        if runtime == CodeRuntime.MICROPYTHON
        else "ESP-Claw Lua"
    )
    return GeneratedCode(
        files=files,
        diff=_diff(files),
        summary=f"{draft.summary.strip()}（基于 Spec v{spec.version}）",
        test_result=pending_validation_result(
            now=now,
            message=f"代码草稿已打包，等待本地 {runtime_label} 静态检查和语法检查。",
            runtime=runtime,
        ),
        runtime=runtime,
        entrypoint=entrypoint,
    )


def _validate_files(
    files: list[GeneratedCodeFile],
    *,
    runtime: CodeRuntime,
    board_contract_id: str | None = None,
    required_paths: set[str] | None = None,
) -> None:
    paths = {file.path for file in files}
    entrypoint = _entrypoint(runtime)
    if entrypoint not in paths:
        raise ValueError(f"代码草稿必须包含 {entrypoint}。")
    if runtime == CodeRuntime.MICROPYTHON:
        valid_layout = all(
            is_uploadable_python_path(file.path)
            or (file.path == "README.md" and file.language == "markdown")
            for file in files
        )
        layout_error = "代码草稿只能包含受限 src/ MicroPython 文件和 README.md。"
    else:
        valid_layout = all(
            is_uploadable_lua_path(file.path)
            or (file.path == "README.md" and file.language == "markdown")
            for file in files
        )
        layout_error = "ESP-Claw 代码草稿只能包含受限 scripts/**/*.lua 和 README.md。"
    if len(paths) != len(files) or not valid_layout:
        raise ValueError(layout_error)
    missing_paths = sorted((required_paths or set()) - paths)
    if missing_paths:
        raise ValueError(
            "自动浇花代码草稿缺少结构化工程文件："
            + "、".join(missing_paths)
            + "。"
        )
    validate_storable_code_files(files, runtime=runtime)
    if runtime == CodeRuntime.MICROPYTHON:
        validate_board_api_files(files, board_contract_id)
    for file in files:
        if file.language != "python":
            continue
        try:
            compile(file.content, file.path, "exec")
        except SyntaxError as exc:
            raise ValueError(f"{file.path} Python 语法无效：{exc.msg}") from exc


def _required_paths(spec: SpecRun) -> set[str]:
    spec_text = "\n".join(file.content for file in spec.files).lower()
    watering_markers = (
        "sen0193",
        "dfr0523",
        "自动浇花",
        "土壤湿度",
        "soil moisture",
    )
    if not any(marker in spec_text for marker in watering_markers):
        return set()
    return {
        "src/boot.py",
        "src/main.py",
        "src/config.py",
        "src/drivers/soil_moisture.py",
        "src/drivers/pump.py",
        "README.md",
    }


def _file_kind(path: str) -> CodeFileKind:
    if path in {"src/main.py", "scripts/main.lua"}:
        return CodeFileKind.MAIN
    if path in {"src/config.py", "scripts/config.lua"}:
        return CodeFileKind.CONFIG
    if path == "README.md":
        return CodeFileKind.README
    return CodeFileKind.DRIVER


def _entrypoint(runtime: CodeRuntime) -> str:
    return (
        "src/main.py"
        if runtime == CodeRuntime.MICROPYTHON
        else "scripts/main.lua"
    )


def _diff(files: list[GeneratedCodeFile]) -> str:
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
