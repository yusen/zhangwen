"""Offline import of already copied Hardware Skill packages through the V1 validator.

Use only a snapshot under this workspace; never open the V1 production database.
The target service must be stopped. Existing packages are retained on conflicts.
"""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "services/local-api"))

from zhangwen.mu_web.repository import MuRepository


@contextmanager
def offline_lock(target: Path):
    target.mkdir(parents=True, exist_ok=True)
    with (target / ".mu-web.lock").open("a+b") as lock:
        lock.seek(0, 2)
        if lock.tell() == 0:
            lock.write(b"0")
            lock.flush()
        lock.seek(0)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, required=True)
    parser.add_argument("--target", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--replace-pristine-k10", action="store_true", help="Use the richer snapshot only if target K10 still equals the shipped package")
    args = parser.parse_args()
    snapshot, target = args.snapshot.resolve(), args.target.resolve()
    if not snapshot.is_relative_to(ROOT / "imports") or not snapshot.is_dir() or snapshot.is_symlink():
        parser.error("snapshot must be a copied package directory under this workspace's imports")
    if target == ROOT or not target.is_relative_to(ROOT) or target.is_relative_to(snapshot) or snapshot.is_relative_to(target):
        parser.error("target must be a separate data directory under this workspace")
    with offline_lock(target):
        repo = MuRepository(target)
        pristine_revision = None
        if args.replace_pristine_k10:
            (ROOT / ".test-data").mkdir(exist_ok=True)
            # Keep the isolated baseline for audit; legacy SQLite handles can
            # remain live until process exit on Windows.
            temp = tempfile.mkdtemp(prefix="hardware-pristine-", dir=ROOT / ".test-data")
            baseline = MuRepository(Path(temp))
            pristine_revision = baseline.skills.get_active_by_component_id("hw_seed_unihiker_k10").revision
        prepared = []
        component_ids = set()
        # Validate every package, including file whitelist, revisions and media hashes,
        # before importing any package. Models remain reference text, never executed.
        for path in sorted(snapshot.iterdir()):
            if not path.is_dir():
                continue
            manifest, files, spec, _, _ = repo.skills._load_package(path)
            if manifest.componentId in component_ids:
                raise ValueError("Duplicate source componentId: " + manifest.componentId)
            component_ids.add(manifest.componentId)
            prepared.append((path, manifest, files, spec))
        report = {"snapshot": str(snapshot), "target": str(target), "imported": [], "retained": [], "conflicts": [], "replacedPristine": []}
        existing = {item.componentId: item for item in repo.skills.list_skills(include_archived=True)}
        for path, manifest, files, spec in prepared:
            current = existing.get(manifest.componentId)
            entry = {"skillName": manifest.skillName, "componentId": manifest.componentId,
                     "category": spec.category.value, "revision": manifest.revision}
            if current is not None:
                can_replace = (args.replace_pristine_k10 and current.componentId == "hw_seed_unihiker_k10"
                    and current.revision == pristine_revision and current.revision != manifest.revision)
                if can_replace:
                    saved = repo.skills._write_package(manifest, files, sync_projection=True,
                        media_payloads=repo.skills._read_media_payloads(path, manifest))
                    report["replacedPristine"].append({**entry, "previousRevision": current.revision})
                    if saved.revision != entry["revision"]:
                        raise ValueError("Imported revision differs: " + manifest.skillName)
                    continue
                key = "retained" if current.revision == manifest.revision else "conflicts"
                report[key].append({**entry, "targetRevision": current.revision})
                continue
            if (target / "hardware-skills" / manifest.skillName).exists():
                raise ValueError("Existing skillName belongs to a different component: " + manifest.skillName)
            # Use the original package writer and SQLite/geometry projection rather
            # than inserting a second hardware directory or bypassing validation.
            saved = repo.skills._write_package(manifest, files, sync_projection=True,
                require_absent=True, media_payloads=repo.skills._read_media_payloads(path, manifest))
            if saved.revision != entry["revision"]:
                raise ValueError("Imported revision differs: " + manifest.skillName)
            report["imported"].append(entry)
        repo.skills.refresh_active_catalog()
        catalog = repo.skills.list_skills()
        stored = repo.skills.list_skills(include_archived=True)
        report["storedPackages"] = len(stored)
        report["activePackages"] = len(catalog)
        report["activeSensors"] = sum(item.category.value == "SENSOR" for item in catalog)
        report["missingComponentIds"] = sorted(component_ids - {item.componentId for item in stored})
        report["preservedButNotShown"] = sorted({item.componentId for item in stored} - {item.componentId for item in catalog})
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({key: len(report[key]) for key in ("imported", "retained", "conflicts", "replacedPristine")}, ensure_ascii=False))
        print("Active packages:", report["activePackages"], "sensors:", report["activeSensors"], "missing:", report["missingComponentIds"])
        if report["conflicts"] or report["missingComponentIds"]:
            raise SystemExit("Review the recorded conflicts/missing IDs; no existing package was overwritten.")


if __name__ == "__main__":
    main()
