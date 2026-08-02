from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

from zhangwen.auth.repository import AuthError, AuthRepository


def test_recovery_script_backs_up_database_and_never_prints_password(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = AuthRepository(tmp_path)
    _, old_token, _ = repository.register(
        username="local-maker",
        display_name="Test Maker",
        password="OriginalPass123",
    )
    module = _load_recovery_module()
    confirmations = iter(["重置 local-maker"])
    passwords = iter(["RecoveredPass123", "RecoveredPass123"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(confirmations))
    monkeypatch.setattr(module.getpass, "getpass", lambda _prompt: next(passwords))
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "reset-local-account-password.py",
            "--data-dir",
            str(tmp_path),
            "--username",
            "local-maker",
        ],
    )

    assert module.main() == 0

    output = capsys.readouterr().out
    assert "已重置本机账号：local-maker" in output
    assert "OriginalPass123" not in output
    assert "RecoveredPass123" not in output
    backups = list((tmp_path / "auth" / "backups").glob("*.sqlite3.bak"))
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0
    assert repository.login(
        username="local-maker",
        password="RecoveredPass123",
    )[0].displayName == "Test Maker"
    with pytest.raises(AuthError):
        repository.validate_session(old_token)


def _load_recovery_module() -> ModuleType:
    root = Path(__file__).resolve().parents[3]
    script = root / "scripts-dev" / "reset-local-account-password.py"
    spec = importlib.util.spec_from_file_location("zhangwen_local_recovery", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载恢复工具：{script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
