"""Fixed child-process workers for MicroPython validation."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class _WorkerFile:
    path: str
    language: str
    content: str


def main(argv: list[str]) -> int:
    if len(argv) not in {3, 4} or argv[1] not in {"static", "syntax"}:
        print("usage: validation_worker.py static|syntax WORKSPACE [BOARD_CONTRACT_ID]")
        return 64
    mode = argv[1]
    workspace = Path(argv[2]).resolve()
    board_contract_id = argv[3] if len(argv) == 4 else None
    if not workspace.is_dir():
        print("validation workspace is missing")
        return 66
    try:
        if mode == "static":
            return _run_static(workspace, board_contract_id)
        return _run_syntax(workspace)
    except Exception as exc:  # noqa: BLE001 - worker must convert failures to an exit code
        print(f"{type(exc).__name__}: {exc}")
        return 70


def _run_static(workspace: Path, board_contract_id: str | None = None) -> int:
    _add_service_root()
    from zhangwen.code_agent.board_api_contracts import (  # noqa: PLC0415
        validate_board_api_files,
    )
    from zhangwen.code_agent.validation import validate_storable_code_files  # noqa: PLC0415

    files = _load_existing_files(workspace, _discover_code_paths(workspace))
    try:
        validate_storable_code_files(files)
        validate_board_api_files(files, board_contract_id)
    except ValueError as exc:
        print(str(exc))
        return 2
    print("Static credential, host-capability, and board API checks passed.")
    return 0


def _run_syntax(workspace: Path) -> int:
    errors: list[str] = []
    for file in _load_existing_files(workspace, _discover_code_paths(workspace)):
        if file.language != "python":
            continue
        try:
            compile(file.content, file.path, "exec")
        except SyntaxError as exc:
            errors.append(f"{file.path}:{exc.lineno or 0}: {exc.msg}")
    if errors:
        print("\n".join(errors))
        return 1
    print("Python syntax checks passed.")
    return 0


def _load_existing_files(workspace: Path, paths: tuple[str, ...]) -> list[_WorkerFile]:
    existing = tuple(
        relative_path
        for relative_path in paths
        if (workspace / relative_path).is_file()
    )
    return _load_files(workspace, existing)


def _discover_code_paths(workspace: Path) -> tuple[str, ...]:
    """Discover only files materialized by the parent validation boundary."""

    paths: list[str] = []
    if (workspace / "README.md").is_file():
        paths.append("README.md")
    for root_name in ("src", "tests"):
        root = workspace / root_name
        if not root.is_dir():
            continue
        paths.extend(
            path.relative_to(workspace).as_posix()
            for path in sorted(root.rglob("*.py"))
            if path.is_file()
        )
    return tuple(paths)


def _load_files(workspace: Path, paths: tuple[str, ...]) -> list[_WorkerFile]:
    files: list[_WorkerFile] = []
    for relative_path in paths:
        path = (workspace / relative_path).resolve()
        if not path.is_relative_to(workspace) or not path.is_file():
            raise ValueError(f"validation file is missing or unsafe: {relative_path}")
        files.append(
            _WorkerFile(
                path=relative_path,
                language="python" if relative_path.endswith(".py") else "markdown",
                content=path.read_text(encoding="utf-8"),
            )
        )
    return files


def _add_service_root() -> None:
    service_root = Path(__file__).resolve().parents[2]
    if str(service_root) not in sys.path:
        sys.path.insert(0, str(service_root))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
