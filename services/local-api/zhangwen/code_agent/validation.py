"""Bounded static and syntax validation for supported device code runtimes."""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Protocol

from zhangwen.code_agent.models import (
    CodeRuntime,
    CodeTestResult,
    CodeValidationCheck,
    CodeValidationKind,
    CodeValidationStatus,
)

MAX_CODE_FILES = 30
MAX_CODE_PATH_LENGTH = 200
DEFAULT_VALIDATION_TIMEOUT_SECONDS = 10.0
MAX_VALIDATION_OUTPUT_CHARS = 20_000
MAX_ESP_CLAW_TOTAL_CHARS = 200_000

_WORKER_PATH = Path(__file__).with_name("validation_worker.py")
CURRENT_VALIDATION_KINDS = (
    CodeValidationKind.STATIC,
    CodeValidationKind.SYNTAX,
)
_LEGACY_SUPPORT_PATHS = {
    "README.md": "markdown",
    "tests/test_logic.py": "python",
}
_FORBIDDEN_IMPORTS = {
    "asyncio",
    "builtins",
    "ctypes",
    "ftplib",
    "glob",
    "http",
    "importlib",
    "multiprocessing",
    "pathlib",
    "requests",
    "serial",
    "shlex",
    "shutil",
    "signal",
    "socket",
    "ssl",
    "subprocess",
    "sys",
    "telnetlib",
    "tempfile",
    "threading",
    "urllib",
    "winreg",
}
_FORBIDDEN_DIRECT_CALLS = {
    "__import__",
    "breakpoint",
    "chmod",
    "chown",
    "compile",
    "eval",
    "exec",
    "input",
    "open",
    "popen",
    "remove",
    "removedirs",
    "rename",
    "renames",
    "replace",
    "rmdir",
    "system",
    "unlink",
}
_DEVICE_OS_MODULES = {"os", "uos"}
_FORBIDDEN_DEVICE_OS_CALLS = {
    "chmod",
    "chown",
    "popen",
    "remove",
    "removedirs",
    "rename",
    "renames",
    "replace",
    "rmdir",
    "system",
    "unlink",
}
_SENSITIVE_PATTERNS = (
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "疑似 API Key"),
    (re.compile(r"(?i)authorization\s*:\s*bearer"), "Authorization 头"),
)
_CREDENTIAL_ASSIGNMENT_PATTERN = re.compile(
    r"(?i)\b(?P<name>api[_-]?key|access[_-]?token|wifi[_-]?password)"
    r"\s*=\s*(?P<quote>['\"])(?P<value>[^'\"\r\n]*)(?P=quote)"
)
_CREDENTIAL_PLACEHOLDERS = {
    "API_KEY_HERE",
    "ACCESS_TOKEN_HERE",
    "CHANGE_ME",
    "ENTER_API_KEY",
    "ENTER_ACCESS_TOKEN",
    "ENTER_PASSWORD",
    "ENTER_WIFI_PASSWORD",
    "PASSWORD",
    "PASSWORD_HERE",
    "REPLACE_ME",
    "TODO",
    "YOUR_API_KEY",
    "YOUR_ACCESS_TOKEN",
    "YOUR_PASSWORD",
    "YOUR_WIFI_PASSWORD",
    "WIFI_PASSWORD",
    "WIFI_PASSWORD_HERE",
}
_DEVICE_PYTHON_FILENAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\.py$")
_LUA_PATH_SEGMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*$")
_LUA_FILENAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*\.lua$")
_CREDENTIAL_PATH_PATTERN = re.compile(
    r"(?i)(?:^|[_-])(?:api[_-]?keys?|credentials?|passwords?|secrets?|tokens?|wifi)(?:[_-]|$)"
)
_PYTHON_SOURCE_SHAPE = re.compile(
    r"(?m)^\s*(?:def|class|from\s+\S+\s+import|import\s+\S+|"
    r"try\s*:|except\b[^\n]*:|elif\b[^\n]*:|if\b[^\n]*:|for\b[^\n]*:)"
)
_LUA_FORBIDDEN_CALLS = (
    (re.compile(r"\bos\s*\.\s*execute\s*\("), "os.execute"),
    (re.compile(r"\bio\s*\.\s*popen\s*\("), "io.popen"),
    (re.compile(r"\bpackage\s*\.\s*loadlib\s*\("), "package.loadlib"),
    (re.compile(r"\b(?:load|loadfile|loadstring|dofile)\s*\("), "动态代码加载"),
)


class ValidatableCodeFile(Protocol):
    path: str
    language: str
    content: str


@dataclass(frozen=True)
class _ProcessOutcome:
    returncode: int | None
    output: str
    timed_out: bool = False


def validate_storable_code_files(
    files: Sequence[ValidatableCodeFile],
    *,
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON,
) -> None:
    """Reject credentials and host capabilities without executing user code."""

    _validate_file_layout(files, runtime=runtime)
    issues: list[str] = []
    for file in files:
        issues.extend(_sensitive_content_issues(file.path, file.content))
        if runtime == CodeRuntime.ESP_CLAW_LUA and file.language == "lua":
            issues.extend(_lua_static_issues(file.path, file.content))
            issues.extend(_lua_syntax_issues(file.path, file.content))
            continue
        if file.language != "python":
            continue
        try:
            tree = ast.parse(file.content, filename=file.path)
        except SyntaxError:
            # Syntax is reported by the dedicated child process. Parsing never imports or
            # executes project code.
            continue
        issues.extend(_python_capability_issues(file.path, tree))
    if issues:
        raise ValueError(" ".join(dict.fromkeys(issues)))


def run_micropython_validation(
    files: Sequence[ValidatableCodeFile],
    *,
    now: str,
    timeout_seconds: float = DEFAULT_VALIDATION_TIMEOUT_SECONDS,
    board_contract_id: str | None = None,
) -> CodeTestResult:
    """Run fixed static and syntax workers without executing project code."""

    _validate_file_layout(files, runtime=CodeRuntime.MICROPYTHON)
    if timeout_seconds <= 0:
        raise ValueError("验证超时必须大于 0。")

    with tempfile.TemporaryDirectory(prefix="zhangwen-micropython-validation-") as raw_dir:
        workspace = Path(raw_dir).resolve()
        _materialize_workspace(workspace, files)
        static = _run_worker(
            "static",
            workspace,
            timeout_seconds,
            board_contract_id=board_contract_id,
        )
        syntax = _run_worker("syntax", workspace, timeout_seconds)
        checks = [
            _check_from_outcome(CodeValidationKind.STATIC, static, workspace),
            _check_from_outcome(CodeValidationKind.SYNTAX, syntax, workspace),
        ]

    ok = all(
        check.status == CodeValidationStatus.PASSED and check.exitCode == 0
        for check in checks
    )
    return CodeTestResult(
        ok=ok,
        command="micropython-local-validation",
        output=_validation_summary(checks),
        createdAt=now,
        checks=checks,
    )


def run_esp_claw_lua_validation(
    files: Sequence[ValidatableCodeFile],
    *,
    now: str,
) -> CodeTestResult:
    """Validate ESP-Claw Lua text without loading or executing it."""

    _validate_file_layout(files, runtime=CodeRuntime.ESP_CLAW_LUA)
    static_issues: list[str] = []
    syntax_issues: list[str] = []
    for file in files:
        static_issues.extend(_sensitive_content_issues(file.path, file.content))
        if file.language != "lua":
            continue
        static_issues.extend(_lua_static_issues(file.path, file.content))
        syntax_issues.extend(_lua_syntax_issues(file.path, file.content))
    checks = [
        _in_process_check(
            CodeValidationKind.STATIC,
            static_issues,
            runtime=CodeRuntime.ESP_CLAW_LUA,
        ),
        _in_process_check(
            CodeValidationKind.SYNTAX,
            syntax_issues,
            runtime=CodeRuntime.ESP_CLAW_LUA,
        ),
    ]
    ok = all(check.status == CodeValidationStatus.PASSED for check in checks)
    return CodeTestResult(
        ok=ok,
        command="esp-claw-lua-local-validation",
        output=_validation_summary(checks),
        createdAt=now,
        checks=checks,
    )


def pending_validation_result(
    *,
    now: str,
    message: str,
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON,
) -> CodeTestResult:
    checks = [
        CodeValidationCheck(
            kind=kind,
            status=CodeValidationStatus.NOT_RUN,
            command=_command_label(kind, runtime=runtime),
            exitCode=None,
            output=message,
        )
        for kind in CURRENT_VALIDATION_KINDS
    ]
    return CodeTestResult(
        ok=False,
        command="not-run",
        output=message,
        createdAt=now,
        checks=checks,
    )


def _validate_file_layout(
    files: Sequence[ValidatableCodeFile],
    *,
    runtime: CodeRuntime,
) -> None:
    paths = [file.path for file in files]
    if not files or len(files) > MAX_CODE_FILES:
        raise ValueError(f"代码文件数量必须在 1 到 {MAX_CODE_FILES} 之间。")
    if len(paths) != len(set(paths)):
        raise ValueError("代码文件路径不能重复。")
    entrypoint = (
        "src/main.py"
        if runtime == CodeRuntime.MICROPYTHON
        else "scripts/main.lua"
    )
    if entrypoint not in paths:
        raise ValueError(f"代码必须包含受限入口路径 {entrypoint}。")
    if (
        runtime == CodeRuntime.ESP_CLAW_LUA
        and sum(len(file.content) for file in files) > MAX_ESP_CLAW_TOTAL_CHARS
    ):
        raise ValueError("ESP-Claw Lua 工程内容超过允许上限。")
    for file in files:
        path = file.path
        if len(path) > MAX_CODE_PATH_LENGTH:
            raise ValueError("代码文件路径超过允许长度。")
        relative = PurePosixPath(path)
        if relative.is_absolute() or ".." in relative.parts or "\\" in path:
            raise ValueError("代码文件路径必须是受限工程路径内的包内相对路径。")
        if runtime == CodeRuntime.ESP_CLAW_LUA:
            expected_language = "markdown" if path == "README.md" else "lua"
            if path != "README.md" and not is_uploadable_lua_path(path):
                raise ValueError(
                    "ESP-Claw 代码只能包含可部署的 scripts/**/*.lua 或 README.md。"
                )
        else:
            expected_language = _LEGACY_SUPPORT_PATHS.get(path)
            if expected_language is None:
                if not is_uploadable_python_path(path):
                    raise ValueError(
                        "代码只能包含可上传的 src/*.py，或兼容的 README/纯逻辑测试路径。"
                    )
                expected_language = "python"
        if file.language != expected_language:
            raise ValueError(f"{path} 的语言必须为 {expected_language}。")


def is_uploadable_python_path(path: str) -> bool:
    """Return whether a stored path maps to the bounded MicroPython device tree."""

    if not path or len(path) > MAX_CODE_PATH_LENGTH or "\\" in path:
        return False
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    if relative.parts[0] != "src" or len(relative.parts) not in {2, 3}:
        return False
    if len(relative.parts) == 3 and relative.parts[1] != "drivers":
        return False
    filename = relative.parts[-1]
    return (
        relative.suffix == ".py"
        and _DEVICE_PYTHON_FILENAME.fullmatch(filename) is not None
    )


def is_uploadable_lua_path(path: str) -> bool:
    """Return whether a path belongs to the bounded ESP-Claw Lua script tree."""

    if not path or len(path) > MAX_CODE_PATH_LENGTH or "\\" in path:
        return False
    relative = PurePosixPath(path)
    if relative.is_absolute() or ".." in relative.parts:
        return False
    if not 2 <= len(relative.parts) <= 5 or relative.parts[0] != "scripts":
        return False
    if _LUA_FILENAME.fullmatch(relative.parts[-1]) is None:
        return False
    if any(_LUA_PATH_SEGMENT.fullmatch(part) is None for part in relative.parts[1:-1]):
        return False
    credential_names = [
        (PurePosixPath(part).stem if index == len(relative.parts) - 1 else part)
        .replace("-", "_")
        for index, part in enumerate(relative.parts[1:], start=1)
    ]
    return not any(
        _CREDENTIAL_PATH_PATTERN.search(name) is not None
        for name in credential_names
    )


def _lua_static_issues(path: str, content: str) -> list[str]:
    issues: list[str] = []
    if _PYTHON_SOURCE_SHAPE.search(content):
        issues.append(f"{path} 看起来是 Python，不是 ESP-Claw Lua。")
    sanitized, lexical_issues = _strip_lua_comments_and_strings(path, content)
    issues.extend(lexical_issues)
    for pattern, label in _LUA_FORBIDDEN_CALLS:
        if pattern.search(sanitized):
            issues.append(f"{path} 包含禁止的 Lua 能力：{label}。")
    return issues


def _lua_syntax_issues(path: str, content: str) -> list[str]:
    sanitized, lexical_issues = _strip_lua_comments_and_strings(path, content)
    issues = list(lexical_issues)
    bracket_stack: list[str] = []
    bracket_pairs = {")": "(", "]": "[", "}": "{"}
    for char in sanitized:
        if char in "([{":
            bracket_stack.append(char)
        elif char in bracket_pairs:
            if not bracket_stack or bracket_stack.pop() != bracket_pairs[char]:
                issues.append(f"{path} 的括号不匹配。")
                break
    if bracket_stack:
        issues.append(f"{path} 存在未闭合括号。")

    block_stack: list[tuple[str, bool]] = []
    for token in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", sanitized):
        if token in {"function", "repeat"}:
            block_stack.append((token, True))
        elif token in {"if", "for", "while"}:
            block_stack.append((token, False))
        elif token == "then":
            if block_stack and block_stack[-1][0] == "if":
                block_stack[-1] = ("if", True)
        elif token == "do":
            if block_stack and block_stack[-1][0] in {"for", "while"}:
                block_stack[-1] = (block_stack[-1][0], True)
            else:
                block_stack.append(("do", True))
        elif token == "end":
            if not block_stack or block_stack[-1][0] == "repeat":
                issues.append(f"{path} 包含没有对应起始块的 end。")
                break
            block, delimiter_seen = block_stack.pop()
            if block in {"if", "for", "while"} and not delimiter_seen:
                issues.append(f"{path} 的 {block} 块缺少必要分隔关键字。")
        elif token == "until":
            if not block_stack or block_stack[-1][0] != "repeat":
                issues.append(f"{path} 包含没有对应 repeat 的 until。")
                break
            block_stack.pop()
    if block_stack:
        issues.append(f"{path} 存在未闭合的 Lua 代码块。")
    return list(dict.fromkeys(issues))


def _strip_lua_comments_and_strings(
    path: str,
    content: str,
) -> tuple[str, list[str]]:
    result: list[str] = []
    issues: list[str] = []
    index = 0
    while index < len(content):
        if content.startswith("--[[", index):
            end = content.find("]]", index + 4)
            if end < 0:
                issues.append(f"{path} 存在未闭合的 Lua 长注释。")
                result.extend("\n" if char == "\n" else " " for char in content[index:])
                break
            segment = content[index : end + 2]
            result.extend("\n" if char == "\n" else " " for char in segment)
            index = end + 2
            continue
        if content.startswith("--", index):
            end = content.find("\n", index + 2)
            if end < 0:
                result.extend(" " for _ in content[index:])
                break
            result.extend(" " for _ in content[index:end])
            result.append("\n")
            index = end + 1
            continue
        if content.startswith("[[", index):
            end = content.find("]]", index + 2)
            if end < 0:
                issues.append(f"{path} 存在未闭合的 Lua 长字符串。")
                result.extend("\n" if char == "\n" else " " for char in content[index:])
                break
            segment = content[index : end + 2]
            result.extend("\n" if char == "\n" else " " for char in segment)
            index = end + 2
            continue
        char = content[index]
        if char not in {"'", '"'}:
            result.append(char)
            index += 1
            continue
        quote = char
        result.append(" ")
        index += 1
        escaped = False
        closed = False
        while index < len(content):
            char = content[index]
            result.append("\n" if char == "\n" else " ")
            index += 1
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == quote:
                closed = True
                break
        if not closed:
            issues.append(f"{path} 存在未闭合的 Lua 字符串。")
            break
    return "".join(result), issues


def _in_process_check(
    kind: CodeValidationKind,
    issues: Sequence[str],
    *,
    runtime: CodeRuntime,
) -> CodeValidationCheck:
    passed = not issues
    output = "检查通过。" if passed else " ".join(dict.fromkeys(issues))
    return CodeValidationCheck(
        kind=kind,
        status=(
            CodeValidationStatus.PASSED
            if passed
            else CodeValidationStatus.FAILED
        ),
        command=_command_label(kind, runtime=runtime),
        exitCode=0 if passed else 1,
        output=output[:MAX_VALIDATION_OUTPUT_CHARS],
    )


def _python_capability_issues(path: str, tree: ast.AST) -> list[str]:
    issues: list[str] = []
    os_module_aliases, os_call_aliases = _device_os_aliases(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            blocked = sorted(
                {
                    alias.name.split(".", 1)[0]
                    for alias in node.names
                    if alias.name.split(".", 1)[0] in _FORBIDDEN_IMPORTS
                }
            )
            if blocked:
                issues.append(f"{path} 包含禁止的主机模块：{', '.join(blocked)}。")
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module in _FORBIDDEN_IMPORTS:
                issues.append(f"{path} 包含禁止的主机模块：{module}。")
        elif isinstance(node, ast.Call):
            name = ""
            if isinstance(node.func, ast.Name):
                name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                name = node.func.attr
            if isinstance(node.func, ast.Name) and name == "open":
                issue = _read_only_open_issue(node)
                if issue is not None:
                    issues.append(f"{path} {issue}")
                continue
            if isinstance(node.func, ast.Name) and (
                name in _FORBIDDEN_DIRECT_CALLS or name in os_call_aliases
            ):
                issues.append(f"{path} 包含禁止的主机调用：{name}。")
            elif (
                isinstance(node.func, ast.Attribute)
                and name in _FORBIDDEN_DEVICE_OS_CALLS
                and _attribute_root_name(node.func) in os_module_aliases
            ):
                issues.append(f"{path} 包含禁止的主机调用：{name}。")
    return issues


def _sensitive_content_issues(path: str, content: str) -> list[str]:
    issues = [
        f"{path} 包含禁止内容：{label}。"
        for pattern, label in _SENSITIVE_PATTERNS
        if pattern.search(content)
    ]
    if any(
        not _is_credential_placeholder(match.group("value"))
        for match in _CREDENTIAL_ASSIGNMENT_PATTERN.finditer(content)
    ):
        issues.append(f"{path} 包含禁止内容：硬编码凭据。")
    return issues


def _is_credential_placeholder(value: str) -> bool:
    normalized = re.sub(r"[^A-Z0-9]+", "_", value.strip().upper()).strip("_")
    if normalized in _CREDENTIAL_PLACEHOLDERS:
        return True
    return normalized.startswith(
        ("YOUR_", "ENTER_", "REPLACE_WITH_")
    ) and normalized.endswith(("API_KEY", "ACCESS_TOKEN", "PASSWORD", "TOKEN"))


def _device_os_aliases(tree: ast.AST) -> tuple[set[str], set[str]]:
    module_aliases: set[str] = set()
    call_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                module = alias.name.split(".", 1)[0]
                if module in _DEVICE_OS_MODULES:
                    module_aliases.add(alias.asname or module)
        elif isinstance(node, ast.ImportFrom):
            module = (node.module or "").split(".", 1)[0]
            if module not in _DEVICE_OS_MODULES:
                continue
            for alias in node.names:
                if alias.name in _FORBIDDEN_DEVICE_OS_CALLS:
                    call_aliases.add(alias.asname or alias.name)
    return module_aliases, call_aliases


def _attribute_root_name(node: ast.Attribute) -> str | None:
    value: ast.expr = node.value
    while isinstance(value, ast.Attribute):
        value = value.value
    return value.id if isinstance(value, ast.Name) else None


def _read_only_open_issue(node: ast.Call) -> str | None:
    positional_mode = node.args[1] if len(node.args) >= 2 else None
    keyword_modes = [keyword.value for keyword in node.keywords if keyword.arg == "mode"]
    if len(keyword_modes) > 1 or (positional_mode is not None and keyword_modes):
        return "的 open() 重复声明文件模式，无法证明为设备端只读访问。"
    mode_node = positional_mode or (keyword_modes[0] if keyword_modes else None)
    if mode_node is None:
        return None
    if not isinstance(mode_node, ast.Constant) or not isinstance(mode_node.value, str):
        return "的 open() 必须使用静态只读模式，不能使用动态 mode。"
    if mode_node.value not in {"r", "rb", "br", "rt", "tr"}:
        return f"的 open() 使用了禁止的非只读模式：{mode_node.value}。"
    return None


def _materialize_workspace(
    workspace: Path,
    files: Sequence[ValidatableCodeFile],
) -> None:
    (workspace / "_tmp").mkdir(parents=True, exist_ok=True)
    for file in files:
        destination = workspace.joinpath(*PurePosixPath(file.path).parts)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(file.content, encoding="utf-8", newline="\n")


def _run_worker(
    mode: str,
    workspace: Path,
    timeout_seconds: float,
    *,
    board_contract_id: str | None = None,
) -> _ProcessOutcome:
    command = _worker_command(mode, workspace, board_contract_id=board_contract_id)
    try:
        process = subprocess.Popen(
            command,
            cwd=workspace,
            env=_worker_environment(workspace),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
        )
    except OSError as exc:
        return _ProcessOutcome(None, f"验证子进程未启动：{exc}")
    try:
        output, _ = process.communicate(timeout=timeout_seconds)
        return _ProcessOutcome(process.returncode, output)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _ = process.communicate()
        process.wait()
        return _ProcessOutcome(
            process.returncode,
            f"{output.rstrip()}\nValidation timed out after {timeout_seconds:g}s.",
            timed_out=True,
        )


def _worker_command(
    mode: str,
    workspace: Path,
    *,
    board_contract_id: str | None = None,
) -> tuple[str, ...]:
    if getattr(sys, "frozen", False):
        command = (
            sys.executable,
            "validation-worker",
            mode,
            str(workspace),
        )
        return (*command, board_contract_id) if board_contract_id else command
    command = (
        sys.executable,
        "-I",
        "-X",
        "utf8",
        str(_WORKER_PATH),
        mode,
        str(workspace),
    )
    return (*command, board_contract_id) if board_contract_id else command


def _check_from_outcome(
    kind: CodeValidationKind,
    outcome: _ProcessOutcome,
    workspace: Path,
) -> CodeValidationCheck:
    if outcome.returncode is None:
        status = CodeValidationStatus.NOT_RUN
    else:
        status = (
            CodeValidationStatus.PASSED
            if outcome.returncode == 0
            else CodeValidationStatus.FAILED
        )
    return CodeValidationCheck(
        kind=kind,
        status=status,
        command=_command_label(kind),
        exitCode=outcome.returncode,
        output=_sanitize_output(outcome.output, workspace),
    )


def _command_label(
    kind: CodeValidationKind,
    *,
    runtime: CodeRuntime = CodeRuntime.MICROPYTHON,
) -> str:
    prefix = (
        "micropython"
        if runtime == CodeRuntime.MICROPYTHON
        else "esp-claw-lua"
    )
    suffix = {
        CodeValidationKind.STATIC: "static",
        CodeValidationKind.SYNTAX: "syntax",
    }[kind]
    return f"{prefix}-{suffix}-worker"


def _sanitize_output(output: str, workspace: Path) -> str:
    sanitized = output.replace(str(workspace), "<validation-workspace>")
    sanitized = sanitized.replace(str(workspace).replace("\\", "/"), "<validation-workspace>")
    sanitized = sanitized.strip()
    if len(sanitized) > MAX_VALIDATION_OUTPUT_CHARS:
        sanitized = f"{sanitized[:MAX_VALIDATION_OUTPUT_CHARS]}\n... output truncated ..."
    return sanitized or "子进程未输出文本。"


def _validation_summary(checks: Sequence[CodeValidationCheck]) -> str:
    labels = {
        CodeValidationKind.STATIC: "静态",
        CodeValidationKind.SYNTAX: "语法",
    }
    return "；".join(
        f"{labels[check.kind]}={check.status.value}"
        + (f"(exit={check.exitCode})" if check.exitCode is not None else "")
        for check in checks
    )


def _worker_environment(workspace: Path) -> dict[str, str]:
    allowed_keys = (
        "SYSTEMROOT",
        "WINDIR",
        "PATH",
        "PATHEXT",
    )
    environment = {key: os.environ[key] for key in allowed_keys if key in os.environ}
    environment.update(
        {
            "TEMP": str(workspace / "_tmp"),
            "TMP": str(workspace / "_tmp"),
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
            "PYTHONUTF8": "1",
            "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1",
        }
    )
    return environment
