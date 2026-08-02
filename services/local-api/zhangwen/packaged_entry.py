"""Frozen Windows entry point for the local API and bounded helper tools."""

from __future__ import annotations

import os
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
import traceback


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    command = args.pop(0) if args else "serve"
    handlers: dict[str, Callable[[list[str]], int]] = {
        "serve": _serve,
        "validation-worker": _validation_worker,
        "mpremote": _mpremote,
        "esptool": _esptool,
        "context-smoke": _context_smoke,
    }
    handler = handlers.get(command)
    if handler is None:
        return 64
    try:
        return handler(args)
    except Exception as exc:  # noqa: BLE001 - frozen entry must leave a diagnostic
        _runtime_log(f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}")
        return 70


def _serve(args: list[str]) -> int:
    if args:
        return 64

    _runtime_log("serve:start")
    import uvicorn

    from zhangwen.config import settings
    from zhangwen.main import app

    port = _port_from_environment(settings.port)
    _initialize_user_data(settings.data_dir)
    _runtime_log(f"serve:imports-ready port={port}")
    uvicorn.run(
        app,
        host=settings.host,
        port=port,
        loop="asyncio",
        http="h11",
        ws="none",
        lifespan="on",
        access_log=False,
        log_config=None,
        workers=1,
    )
    _runtime_log("serve:stopped")
    return 0


def _initialize_user_data(data_dir: Path) -> None:
    """Create the writable production state before accepting desktop requests."""
    from zhangwen.hardware.hardware_skills import HardwareSkillRepository
    from zhangwen.hardware.seeds import seed_default_components
    from zhangwen.projects.repository import ProjectRepository

    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "config").mkdir(exist_ok=True)
    projects = ProjectRepository(data_dir)
    skills = HardwareSkillRepository(data_dir, projects.db_path)
    result = skills.install_bundled_catalog()
    seed_default_components(projects.db_path)
    skills.migrate_legacy_rows()
    _runtime_log(
        "hardware-catalog:ready "
        f"installed={result.installed} preserved={result.preserved} "
        f"invalid-existing={result.invalidExisting}"
    )


def _validation_worker(args: list[str]) -> int:
    from zhangwen.code_agent.validation_worker import main as worker_main

    return worker_main(["validation_worker", *args])


def _context_smoke(args: list[str]) -> int:
    """Exercise packaged problem-guide context without a Provider or real device."""
    if args:
        return 64
    from zhangwen.config import settings
    from zhangwen.experts.context_assembler import ContextAssembler, ContextAssemblyInput
    from zhangwen.projects.models import ExpertType
    from zhangwen.projects.repository import ProjectRepository

    _initialize_user_data(settings.data_dir)
    projects = ProjectRepository(settings.data_dir)
    workspace = projects.create_project_from_idea(
        idea="Package smoke for problem-guide hardware context",
        project_name="Packaged context smoke",
        initial_expert=ExpertType.PROBLEM_GUIDE,
        participating_experts=[ExpertType.PROBLEM_GUIDE],
        selected_hardware_ids=[],
    )
    context = ContextAssembler(projects.db_path).assemble(
        ContextAssemblyInput(
            projectId=workspace.project.id,
            expert=ExpertType.PROBLEM_GUIDE,
            userMessage="Help clarify an invention that may use a controller board.",
        )
    )
    if not any(item.get("componentId") for item in context.publicKnowledge):
        raise RuntimeError("problem-guide context did not load packaged hardware knowledge")
    _runtime_log("context-smoke:passed")
    return 0


def _mpremote(args: list[str]) -> int:
    import mpremote.main as mpremote_module

    original_argv = sys.argv
    try:
        sys.argv = ["mpremote", *args]
        # The packaged helper never executes user-authored mpremote config.py.
        mpremote_module.load_user_config = lambda: SimpleNamespace(commands={})
        return _exit_code(mpremote_module.main)
    finally:
        sys.argv = original_argv


def _esptool(args: list[str]) -> int:
    import esptool

    try:
        result = esptool.main(args)
    except SystemExit as exc:
        return _system_exit_code(exc)
    return int(result) if isinstance(result, int) else 0


def _exit_code(callback: Callable[[], object]) -> int:
    try:
        result = callback()
    except SystemExit as exc:
        return _system_exit_code(exc)
    return int(result) if isinstance(result, int) else 0


def _system_exit_code(exc: SystemExit) -> int:
    if exc.code is None:
        return 0
    if isinstance(exc.code, int):
        return exc.code
    return 1


def _port_from_environment(default: int) -> int:
    raw_value = os.environ.get("ZHANGWEN_SIDECAR_PORT", "").strip()
    if not raw_value:
        return default
    try:
        port = int(raw_value)
    except ValueError:
        return default
    return port if 1024 <= port <= 65535 else default


def _runtime_log(message: str) -> None:
    data_dir = os.environ.get("ZHANGWEN_DATA_DIR", "").strip()
    if not data_dir:
        return
    try:
        log_path = os.path.join(data_dir, "logs", "sidecar-startup.log")
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log:
            log.write(message.rstrip() + "\n")
    except OSError:
        return


if __name__ == "__main__":
    raise SystemExit(main())
