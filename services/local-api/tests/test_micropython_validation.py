"""Real-process validation for bounded MicroPython code drafts."""

from __future__ import annotations

import pytest

from zhangwen.code_agent.generator import GeneratedCodeFile, validate_and_package_code
from zhangwen.code_agent.models import (
    CodeContentDraft,
    CodeFileKind,
    CodeValidationKind,
    CodeValidationStatus,
)
from zhangwen.code_agent.validation import run_micropython_validation
from zhangwen.code_agent.validation_worker import main as validation_worker_main
from zhangwen.specs.models import SpecRun, SpecRunStatus, SpecValidation


def test_provider_code_draft_defaults_to_one_uploadable_main_file() -> None:
    draft = CodeContentDraft.model_validate(
        {
            "files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "print('hello K10')\n",
                }
            ],
            "summary": "K10 hello world",
        }
    )

    packaged = validate_and_package_code(
        _approved_spec(),
        draft,
        now="2026-07-12T00:00:00Z",
    )

    assert [file.path for file in packaged.files] == ["src/main.py"]
    assert "README.md" not in packaged.diff
    assert "tests/test_logic.py" not in packaged.diff
    assert [check.kind for check in packaged.test_result.checks] == [
        CodeValidationKind.STATIC,
        CodeValidationKind.SYNTAX,
    ]
    assert all(
        check.status == CodeValidationStatus.NOT_RUN
        and check.exitCode is None
        for check in packaged.test_result.checks
    )


def test_provider_code_draft_preserves_complete_flat_module_set() -> None:
    draft = CodeContentDraft.model_validate(
        {
            "files": [
                {
                    "path": "src/sensor_reader.py",
                    "language": "python",
                    "content": "def read():\n    return 42\n",
                },
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "from sensor_reader import read\nprint(read())\n",
                },
            ],
            "summary": "K10 sensor",
        }
    )

    packaged = validate_and_package_code(
        _approved_spec(),
        draft,
        now="2026-07-12T00:00:00Z",
    )

    assert [file.path for file in packaged.files] == [
        "src/main.py",
        "src/sensor_reader.py",
    ]


def test_provider_code_draft_accepts_bounded_driver_tree_and_readme() -> None:
    draft = CodeContentDraft.model_validate(
        {
            "files": [
                {
                    "path": "src/main.py",
                    "language": "python",
                    "content": "from drivers.soil_moisture import read\nprint(read())\n",
                },
                {
                    "path": "src/drivers/soil_moisture.py",
                    "language": "python",
                    "content": "def read():\n    return 42\n",
                },
                {
                    "path": "README.md",
                    "language": "markdown",
                    "content": "# 自动浇花\n",
                },
            ],
            "summary": "structured project",
        }
    )

    packaged = validate_and_package_code(
        _approved_spec(),
        draft,
        now="2026-07-12T00:00:00Z",
    )

    assert {file.path for file in packaged.files} == {
        "src/main.py",
        "src/drivers/soil_moisture.py",
        "README.md",
    }


def test_provider_code_draft_rejects_unbounded_or_mislabeled_files() -> None:
    for invalid_path, language in (
        ("src/lib/sensor.py", "python"),
        ("README.md", "python"),
        ("tests/test_logic.py", "python"),
    ):
        draft = CodeContentDraft.model_validate(
            {
                "files": [
                    {
                        "path": "src/main.py",
                        "language": language,
                        "content": "print('main')\n",
                    },
                    {
                        "path": invalid_path,
                        "language": "python",
                        "content": "VALUE = 1\n",
                    },
                ],
                "summary": "invalid paths",
            }
        )
        with pytest.raises(ValueError, match="受限 src/"):
            validate_and_package_code(
                _approved_spec(),
                draft,
                now="2026-07-12T00:00:00Z",
            )


def test_validation_uses_zero_exit_codes_for_all_passed_checks() -> None:
    result = run_micropython_validation(_valid_files(), now="2026-07-11T00:00:00Z")

    assert result.ok is True
    assert [check.kind for check in result.checks] == [
        CodeValidationKind.STATIC,
        CodeValidationKind.SYNTAX,
    ]
    assert all(check.status == CodeValidationStatus.PASSED for check in result.checks)
    assert all(check.exitCode == 0 for check in result.checks)


def test_upload_only_main_is_checked_without_importing_board_modules() -> None:
    files = [
        GeneratedCodeFile(
            CodeFileKind.MAIN,
            "src/main.py",
            "python",
            "from unihiker_k10 import screen\nscreen.refresh()\n",
        )
    ]

    result = run_micropython_validation(files, now="2026-07-11T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


def test_multi_file_upload_set_validates_every_required_module() -> None:
    files = [
        GeneratedCodeFile(
            CodeFileKind.MAIN,
            "src/main.py",
            "python",
            "from sensor_reader import read_value\nprint(read_value())\n",
        ),
        GeneratedCodeFile(
            CodeFileKind.DRIVER,
            "src/sensor_reader.py",
            "python",
            "def read_value():\n    return 42\n",
        ),
    ]

    result = run_micropython_validation(files, now="2026-07-12T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


def test_multi_file_upload_set_rejects_unbounded_nested_device_modules() -> None:
    files = [
        GeneratedCodeFile(
            CodeFileKind.MAIN,
            "src/main.py",
            "python",
            "print('main')\n",
        ),
        GeneratedCodeFile(
            CodeFileKind.DRIVER,
            "src/lib/sensor.py",
            "python",
            "def read_value():\n    return 42\n",
        ),
    ]

    with pytest.raises(ValueError, match=r"src/\*\.py"):
        run_micropython_validation(files, now="2026-07-12T00:00:00Z")


def test_upload_only_main_infinite_loop_is_never_executed() -> None:
    files = [
        GeneratedCodeFile(
            CodeFileKind.MAIN,
            "src/main.py",
            "python",
            (
                "from unihiker_k10 import screen\n"
                "screen.init(dir=2)\n"
                "screen.draw_text(\n"
                "    text='hello world', line=1-1, font_size=24, color=0x0000FF\n"
                ")\n"
                "screen.show_draw()\n\n"
                "while True:\n"
                "    pass\n"
            ),
        )
    ]

    result = run_micropython_validation(
        files,
        now="2026-07-12T00:00:00Z",
        timeout_seconds=1.0,
    )

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]
    assert all("timed out" not in check.output.lower() for check in result.checks)


def test_upload_only_main_runtime_failure_is_never_executed() -> None:
    files = [
        GeneratedCodeFile(
            CodeFileKind.MAIN,
            "src/main.py",
            "python",
            "raise RuntimeError('must never execute during validation')\n",
        )
    ]

    result = run_micropython_validation(files, now="2026-07-11T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


def test_k10_microsd_read_only_listing_passes_without_host_execution() -> None:
    files = _valid_files(
        main=(
            "import os\n"
            "from k10_base import TF_card\n\n"
            "TF_card()\n"
            "photos = [name for name in os.listdir('/sd') if name.endswith('.jpg')]\n"
            "print(photos)\n"
        )
    )

    result = run_micropython_validation(files, now="2026-07-15T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


@pytest.mark.parametrize("mode", [None, "r", "rb", "rt", "br"])
def test_k10_microsd_read_only_open_passes_without_host_execution(
    mode: str | None,
) -> None:
    open_call = (
        "open('/sd/photo.rgb565')"
        if mode is None
        else f"open('/sd/photo.rgb565', {mode!r})"
    )
    files = _valid_files(
        main=(
            "from k10_base import TF_card\n\n"
            "TF_card()\n"
            f"with {open_call} as photo:\n"
            "    first_row = photo.read(640)\n"
            "print(len(first_row))\n"
        )
    )

    result = run_micropython_validation(files, now="2026-07-16T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


def test_ntp_alarm_placeholders_and_in_memory_methods_pass_static_validation() -> None:
    files = _valid_files(
        main=(
            "import network\n"
            "import ntptime\n\n"
            "WIFI_SSID = 'YOUR_WIFI_SSID'\n"
            "WIFI_PASSWORD = 'YOUR_WIFI_PASSWORD'\n"
            "alarm_times = ['07:30']\n"
            "display_time = '07-30'.replace('-', ':')\n"
            "alarm_times.remove('07:30')\n"
            "print(display_time, WIFI_SSID, WIFI_PASSWORD, alarm_times)\n"
        )
    )

    result = run_micropython_validation(files, now="2026-07-16T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


def test_actual_hardcoded_wifi_password_remains_blocked() -> None:
    result = run_micropython_validation(
        _valid_files(main="WIFI_PASSWORD = 'real-home-password-123'\n"),
        now="2026-07-16T00:00:00Z",
    )

    checks = {check.kind: check for check in result.checks}
    assert result.ok is False
    assert checks[CodeValidationKind.STATIC].status == CodeValidationStatus.FAILED
    assert "硬编码凭据" in checks[CodeValidationKind.STATIC].output


@pytest.mark.parametrize(
    "source",
    [
        "import os\nos.system('reboot')\n",
        "import os\nos.remove('/sd/photo.jpg')\n",
        "import os\nos.replace('/sd/old.jpg', '/sd/new.jpg')\n",
        "import uos as storage\nstorage.rename('/sd/old.jpg', '/sd/new.jpg')\n",
        "from os import remove as delete_file\ndelete_file('/sd/photo.jpg')\n",
        "open('/sd/photo.jpg', 'wb')\n",
        "open('/sd/photo.jpg', 'a')\n",
        "open('/sd/photo.jpg', 'r+')\n",
        "mode = 'rb'\nopen('/sd/photo.jpg', mode)\n",
    ],
)
def test_microsd_access_keeps_execution_and_mutation_calls_blocked(
    source: str,
) -> None:
    result = run_micropython_validation(
        _valid_files(main=source),
        now="2026-07-15T00:00:00Z",
    )

    checks = {check.kind: check for check in result.checks}
    assert result.ok is False
    assert checks[CodeValidationKind.STATIC].status == CodeValidationStatus.FAILED
    assert checks[CodeValidationKind.SYNTAX].status == CodeValidationStatus.PASSED


def test_upload_only_layout_rejects_paths_outside_allowlist() -> None:
    files = [
        GeneratedCodeFile(
            CodeFileKind.MAIN,
            "src/main.py",
            "python",
            "print('safe')\n",
        ),
        GeneratedCodeFile(
            CodeFileKind.CONFIG,
            "../config.py",
            "python",
            "SECRET = False\n",
        ),
    ]

    with pytest.raises(ValueError, match="受限工程路径"):
        run_micropython_validation(files, now="2026-07-11T00:00:00Z")


@pytest.mark.parametrize("module_name", ["subprocess", "socket", "serial"])
def test_static_failure_does_not_skip_syntax_check(module_name: str) -> None:
    files = _valid_files(main=f"import {module_name}\n\ndef add(left, right):\n    return left + right\n")

    result = run_micropython_validation(files, now="2026-07-11T00:00:00Z")

    checks = {check.kind: check for check in result.checks}
    assert result.ok is False
    assert checks[CodeValidationKind.STATIC].status == CodeValidationStatus.FAILED
    assert checks[CodeValidationKind.STATIC].exitCode not in {None, 0}
    assert checks[CodeValidationKind.SYNTAX].status == CodeValidationStatus.PASSED
    assert checks[CodeValidationKind.SYNTAX].exitCode == 0
    assert set(checks) == {
        CodeValidationKind.STATIC,
        CodeValidationKind.SYNTAX,
    }


def test_syntax_failure_has_no_simulation_result() -> None:
    files = _valid_files(main="def broken(:\n    return 1\n")

    result = run_micropython_validation(files, now="2026-07-11T00:00:00Z")

    checks = {check.kind: check for check in result.checks}
    assert result.ok is False
    assert checks[CodeValidationKind.SYNTAX].status == CodeValidationStatus.FAILED
    assert checks[CodeValidationKind.SYNTAX].exitCode not in {None, 0}
    assert set(checks) == {
        CodeValidationKind.STATIC,
        CodeValidationKind.SYNTAX,
    }


def test_missing_runtime_module_is_not_imported_during_validation() -> None:
    files = _valid_files(
        main="from missing_device_module import run\nrun()\n",
        test="def test_unrelated():\n    assert True\n",
    )

    result = run_micropython_validation(files, now="2026-07-12T00:00:00Z")

    assert result.ok is True
    assert [check.exitCode for check in result.checks] == [0, 0]


def test_legacy_logic_test_is_compiled_but_never_executed() -> None:
    files = _valid_files(
        test="raise RuntimeError('legacy tests must never execute')\n",
    )

    result = run_micropython_validation(files, now="2026-07-11T00:00:00Z")

    assert result.ok is True
    assert all(check.exitCode == 0 for check in result.checks)


def test_validation_worker_rejects_removed_simulation_mode(tmp_path) -> None:
    assert validation_worker_main(["validation_worker.py", "simulation", str(tmp_path)]) == 64


def _valid_files(
    *,
    main: str = "def add(left, right):\n    return left + right\n",
    test: str = "from src.main import add\n\ndef test_add():\n    assert add(2, 3) == 5\n",
) -> list[GeneratedCodeFile]:
    return [
        GeneratedCodeFile(CodeFileKind.MAIN, "src/main.py", "python", main),
        GeneratedCodeFile(
            CodeFileKind.DRIVER,
            "src/drivers.py",
            "python",
            "def read_sensor():\n    return 0\n",
        ),
        GeneratedCodeFile(
            CodeFileKind.CONFIG,
            "src/config.py",
            "python",
            "THRESHOLD = 10\n",
        ),
        GeneratedCodeFile(
            CodeFileKind.TEST,
            "tests/test_logic.py",
            "python",
            test,
        ),
        GeneratedCodeFile(
            CodeFileKind.README,
            "README.md",
            "markdown",
            "# Test MicroPython project\n",
        ),
    ]


def _approved_spec() -> SpecRun:
    return SpecRun(
        id="spec_dynamic_code_files",
        projectId="project_dynamic_code_files",
        proposalId="proposal_dynamic_code_files",
        version=2,
        status=SpecRunStatus.APPROVED,
        files=[],
        validation=SpecValidation(ok=True, checks=[]),
        createdAt="2026-07-12T00:00:00Z",
        updatedAt="2026-07-12T00:00:00Z",
        confirmedAt="2026-07-12T00:00:00Z",
    )
