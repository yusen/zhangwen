"""Offline installed-version and import checks; never install into system Python."""
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys


def inspect(requirements: Path) -> dict:
    problems = []
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "==" not in line:
            raise ValueError("Expected an exact requirements lock")
        name, expected = line.split("==", 1)
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != expected:
            problems.append({"package": name, "expected": expected, "installed": installed})
    for module in ("fastapi", "uvicorn", "httpx", "yaml", "pydantic_core"):
        try:
            importlib.import_module(module)
        except Exception:
            problems.append({"package": module, "reason": "import failed"})
    try:
        importlib.metadata.version("pip")
        pip_available = True
    except importlib.metadata.PackageNotFoundError:
        pip_available = False
    return {"ready": not problems, "problems": problems, "pipAvailable": pip_available}


if __name__ == "__main__":
    report = inspect(Path(__file__).resolve().parents[1] / "services/local-api/requirements-web-lock.txt")
    print(json.dumps(report, ensure_ascii=True))
    sys.exit(0 if report["ready"] else 1)
