"""Packaging boundary tests that never access a real device."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from zhangwen.code_agent.validation import _worker_command
from zhangwen.devices.transport import _device_tool_environment, _tool_command
from zhangwen.packaged_entry import _initialize_user_data, _port_from_environment, main


def test_frozen_runtime_dispatches_workers_through_the_sidecar(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "zhangwen-sidecar.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    assert _worker_command("syntax", tmp_path) == (
        str(executable),
        "validation-worker",
        "syntax",
        str(tmp_path),
    )
    assert _tool_command("mpremote", ["version"]) == [
        str(executable),
        "mpremote",
        "version",
    ]
    assert _tool_command("esptool", ["version"]) == [
        str(executable),
        "esptool",
        "version",
    ]


def test_development_runtime_keeps_python_module_invocations(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "python.exe"
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))

    worker = _worker_command("static", tmp_path)
    assert worker[:4] == (str(executable), "-I", "-X", "utf8")
    assert worker[-2:] == ("static", str(tmp_path))
    assert _tool_command("mpremote", ["version"]) == [
        str(executable),
        "-m",
        "mpremote",
        "version",
    ]


def test_packaged_entry_rejects_unknown_commands() -> None:
    assert main(["unknown-command"]) == 64


def test_packaged_entry_accepts_only_safe_port_range(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZHANGWEN_SIDECAR_PORT", "18100")
    assert _port_from_environment(8100) == 18100
    monkeypatch.setenv("ZHANGWEN_SIDECAR_PORT", "80")
    assert _port_from_environment(8100) == 8100
    monkeypatch.setenv("ZHANGWEN_SIDECAR_PORT", "invalid")
    assert _port_from_environment(8100) == 8100


def test_packaged_entry_initializes_user_data_before_desktop_requests(
    tmp_path: Path,
) -> None:
    _initialize_user_data(tmp_path)

    assert (tmp_path / "config").is_dir()
    assert (tmp_path / "projects" / "zhangwen.sqlite3").is_file()


def test_all_packaged_resource_directories_exist() -> None:
    package_root = Path(__file__).resolve().parents[1] / "zhangwen"
    for relative_path in (
        "experts/agent-packages",
        "experts/prompts",
        "experts/skill-templates",
        "hardware/board-profiles",
        "hardware/board-skills",
        "hardware/bundled-hardware-skills",
        "hardware/catalog-assets",
    ):
        assert (package_root / relative_path).is_dir()


def test_packaged_tool_dispatch_rejects_unlisted_modules() -> None:
    with pytest.raises(ValueError, match="unsupported packaged device tool"):
        _tool_command("python", ["-c", "print('unsafe')"])


def test_device_tool_environment_does_not_inherit_secrets(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ZHANGWEN_DEEPSEEK_API_KEY", "must-not-leak")
    monkeypatch.setenv("ZHANGWEN_DESKTOP_CAPABILITY_TOKEN", "must-not-leak")

    environment = _device_tool_environment(tmp_path)

    assert "ZHANGWEN_DEEPSEEK_API_KEY" not in environment
    assert "ZHANGWEN_DESKTOP_CAPABILITY_TOKEN" not in environment
    assert Path(environment["ESPTOOL_CFGFILE"]).read_text(encoding="utf-8") == (
        "[esptool]\n"
    )
    assert environment["HOME"] == str(tmp_path)
