"""Offline installed-version and import checks; never install into system Python."""
import importlib
import importlib.metadata
import json
from pathlib import Path
import sys


def locked_packages(requirements: Path, environment: dict | None = None):
    # A brand-new venv may only contain pip; its vendored parser is sufficient
    # until the pinned standalone packaging dependency has been installed.
    try:
        from packaging.requirements import Requirement
    except ImportError:
        from pip._vendor.packaging.requirements import Requirement
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        requirement = Requirement(line)
        specs = list(requirement.specifier)
        if requirement.url or requirement.extras or len(specs) != 1 or specs[0].operator != "==" or "*" in specs[0].version:
            raise ValueError("Expected an exact requirements lock")
        if requirement.marker is None or requirement.marker.evaluate(environment):
            yield requirement.name, specs[0].version


def inspect(requirements: Path, environment: dict | None = None) -> dict:
    problems = []
    try:
        importlib.metadata.version("pip")
        pip_available = True
    except importlib.metadata.PackageNotFoundError:
        pip_available = False
    try:
        packages = list(locked_packages(requirements, environment))
    except ImportError:
        return {"ready": False, "problems": [{"package": "packaging", "reason": "lock parser missing"}], "pipAvailable": pip_available}
    for name, expected in packages:
        try:
            installed = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            installed = None
        if installed != expected:
            problems.append({"package": name, "expected": expected, "installed": installed})
    for module in ("fastapi", "uvicorn", "httpx", "yaml", "pydantic_core", "cadquery", "OCP", "trimesh"):
        try:
            importlib.import_module(module)
        except Exception:
            problems.append({"package": module, "reason": "import failed"})
    return {"ready": not problems, "problems": problems, "pipAvailable": pip_available}


if __name__ == "__main__":
    report = inspect(Path(__file__).resolve().parents[1] / "services/local-api/requirements-web-lock.txt")
    print(json.dumps(report, ensure_ascii=True))
    sys.exit(0 if report["ready"] else 1)
