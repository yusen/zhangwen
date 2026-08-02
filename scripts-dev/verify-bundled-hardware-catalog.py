"""Validate the production Hardware Skill snapshot and emit a smoke manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    service_root = Path(__file__).resolve().parents[1] / "services" / "local-api"
    sys.path.insert(0, str(service_root))
    from zhangwen.hardware.hardware_skills import HardwareSkillRepository

    source = args.source.resolve()
    if not source.is_dir() or source.is_symlink():
        raise SystemExit(f"Hardware catalog source is not a safe directory: {source}")
    repository = HardwareSkillRepository(source.parent, source.parent / "catalog-check.sqlite3")
    packages: list[dict[str, object]] = []
    for package_root in sorted(source.iterdir(), key=lambda item: item.name):
        if package_root.name.startswith("."):
            continue
        if not package_root.is_dir() or package_root.is_symlink():
            raise SystemExit(f"Unexpected catalog entry: {package_root}")
        manifest, _, specification, _, _ = repository._load_package(package_root)
        packages.append(
            {
                "skillName": manifest.skillName,
                "componentId": specification.componentId,
                "revision": manifest.revision,
                "status": manifest.status.value,
                "media": [item.path for item in manifest.media],
            }
        )
    if not packages:
        raise SystemExit("Hardware catalog snapshot is empty.")
    active = [item for item in packages if item["status"] == "ACTIVE"]
    payload = {
        "schema": "zhangwen.packaged-hardware-catalog/v1",
        "packageCount": len(packages),
        "activeCount": len(active),
        "packages": packages,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"Validated {len(packages)} Hardware Skills "
        f"({len(active)} active); manifest: {args.output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
