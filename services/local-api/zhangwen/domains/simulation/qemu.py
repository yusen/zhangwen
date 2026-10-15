"""Pinned, optional Espressif QEMU package boundary for narrow L2 checks.

This module never downloads a runtime and never treats a QEMU log as component
simulation evidence. Provisioning remains an explicit release operation.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import Field

from zhangwen.domains.simulation.models import SimulationChipFamily, SimulationModel


_MANIFEST_PATH = Path(__file__).with_name("qemu_manifest.json")


class EspressifQemuTarget(SimulationModel):
    chip_family: SimulationChipFamily = Field(alias="chipFamily")
    machine: str
    executable: str
    archive_url: str = Field(alias="archiveUrl")
    archive_sha256: str = Field(alias="archiveSha256", pattern=r"^[0-9a-f]{64}$")
    fixed_arguments: list[str] = Field(alias="fixedArguments")


class EspressifQemuManifest(SimulationModel):
    schema_id: str = Field(alias="schema")
    revision_id: str = Field(alias="revisionId")
    upstream_release: str = Field(alias="upstreamRelease")
    source_url: str = Field(alias="sourceUrl")
    license_spdx: str = Field(alias="licenseSpdx")
    targets: list[EspressifQemuTarget]
    evidence_capabilities: list[str] = Field(alias="evidenceCapabilities")
    explicitly_unsupported: list[str] = Field(alias="explicitlyUnsupported")


class EspressifQemuStatus(SimulationModel):
    revision_id: str = Field(alias="revisionId")
    available: bool
    evidence_eligible: bool = Field(alias="evidenceEligible")
    reason: str


class EspressifQemuPackage:
    """Validates an explicitly provisioned archive before any extraction step."""

    def __init__(self, manifest: EspressifQemuManifest) -> None:
        self.manifest = manifest

    @classmethod
    def load_builtin(cls) -> "EspressifQemuPackage":
        return cls(
            EspressifQemuManifest.model_validate_json(
                _MANIFEST_PATH.read_text(encoding="utf-8")
            )
        )

    def status(self, data_dir: Path) -> EspressifQemuStatus:
        root = Path(data_dir) / "runtimes" / self.manifest.revision_id.replace("/", "_")
        receipt_path = root / "provisioning-receipt.json"
        if not receipt_path.is_file():
            return EspressifQemuStatus(
                revisionId=self.manifest.revision_id,
                available=False,
                evidenceEligible=False,
                reason="固定 Espressif QEMU 分发尚未由发布流程配置。",
            )
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
            target_receipts = receipt["targets"]
            if receipt["revisionId"] != self.manifest.revision_id:
                raise ValueError("revision mismatch")
            for target in self.manifest.targets:
                item = target_receipts[target.chip_family.value]
                archive = root / str(item["archiveFile"])
                if not archive.is_file():
                    raise ValueError("archive missing")
                actual = hashlib.sha256(archive.read_bytes()).hexdigest()
                if actual != target.archive_sha256 or item["sha256"] != actual:
                    raise ValueError("archive digest mismatch")
        except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError):
            return EspressifQemuStatus(
                revisionId=self.manifest.revision_id,
                available=False,
                evidenceEligible=False,
                reason="Espressif QEMU 配置回执或摘要校验失败。",
            )
        return EspressifQemuStatus(
            revisionId=self.manifest.revision_id,
            available=True,
            evidenceEligible=True,
            reason="固定分发归档已校验；实际 boot 仍须由受控 Worker 单独验收。",
        )

    def target(self, chip_family: SimulationChipFamily | str) -> EspressifQemuTarget:
        normalized = SimulationChipFamily(chip_family)
        for target in self.manifest.targets:
            if target.chip_family is normalized:
                return target
        raise ValueError("unsupported QEMU chip target")

