"""Canonical, directory-backed Hardware Skill packages.

Markdown is the authority. SQLite is updated only as a compatibility/query
projection after a complete package has passed local validation.
"""

from __future__ import annotations

import base64
import binascii
import ast
import csv
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from threading import RLock
from typing import Any, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from zhangwen.cad_agent.profile_repository import MechanicalProfileSnapshot
from zhangwen.cad_agent.profile_seeds import normalize_profile_snapshot_payload
from zhangwen.cad_engine.models import HardwareModelKind, HardwareProfile, ProfileSource
from zhangwen.hardware.models import (
    ElectricalProps,
    HardwareCategory,
    HardwareComponent,
    HardwareComponentStatus,
    HardwareMediaAsset,
    HardwareRuleOperator,
    HardwareSkillDetail,
    HardwareSkillDiagnostic,
    HardwareSkillDraft,
    HardwareSkillDraftSource,
    HardwareSkillFile,
    HardwareSkillRule,
    HardwareSkillSourceKind,
    HardwareSkillSpecification,
    HardwareSkillStatus,
    HardwareSkillSummary,
    ValidationCheck,
    ValidationResult,
    ValidationSeverity,
)
from zhangwen.hardware.rule_engine import validate_components
from zhangwen.hardware.seeds import RETIRED_DEFAULT_COMPONENT_IDS

HARDWARE_SKILL_PATHS: tuple[str, ...] = (
    "SKILL.md",
    "references/specifications.md",
    "references/compatibility-rules.md",
    "references/integration.md",
    "references/safety.md",
    "references/sources.md",
    "examples/usage.md",
    "tests/validation-cases.md",
)

HARDWARE_SKILL_MECHANICAL_PATHS: tuple[str, ...] = (
    "references/mechanical.md",
    "models/cadquery.py",
)

HARDWARE_SKILL_ALLOWED_PATHS: tuple[str, ...] = (
    "README.md",
    "CHANGELOG.md",
    "SKILL.md",
    "references/specifications.md",
    "references/compatibility-rules.md",
    "references/mechanical.md",
    "references/integration.md",
    "references/safety.md",
    "references/sources.md",
    "models/cadquery.py",
    "examples/usage.md",
    "tests/validation-cases.md",
)

MAX_SKILL_FILE_BYTES = 80_000
MAX_SKILL_PACKAGE_BYTES = 300_000
MAX_SOURCE_BYTES = 512 * 1024
MAX_SOURCE_TOTAL_BYTES = 1_500_000
MAX_PDF_BYTES = 2_000_000
MAX_PDF_PAGES = 50
MAX_PDF_TEXT_CHARS = 200_000
MAX_CONTEXT_CHARS = 24_000
MAX_MEDIA_ASSETS = 6
MAX_MEDIA_FILE_BYTES = 2 * 1024 * 1024
MAX_MEDIA_PACKAGE_BYTES = 8 * 1024 * 1024
_DIRECTORY_REPLACE_ATTEMPTS = 8
_DIRECTORY_REPLACE_BASE_DELAY_SECONDS = 0.1

_LEGACY_OVERLAY_DIRECTORY = "hardware-component-packages"
_BUNDLED_K10_COMPONENT_ID = "hw_seed_unihiker_k10"
_BUNDLED_K10_SKILL_NAME = "k10"
SUPPORTED_CONTROLLER_COMPONENT_IDS = frozenset(
    {"hw_seed_unihiker_k10", "hw_seeed_xiao_esp32s3_sense"}
)
BUNDLED_HARDWARE_CATALOG_ROOT = (
    Path(__file__).with_name("bundled-hardware-catalog") / "hardware-skills"
)
_LEGACY_OVERLAY_FILES: dict[str, tuple[str, str]] = {
    "README.md": ("SKILL.md", "迁移的旧器件概览"),
    "docs/specifications.md": ("references/specifications.md", "迁移的旧技术说明"),
    "docs/integration.md": ("references/integration.md", "迁移的旧集成说明"),
    "docs/safety.md": ("references/safety.md", "迁移的旧安全说明"),
}

_MANIFEST_SCHEMA = "zhangwen.hardware-skill-manifest/v1"
_RULES_SCHEMA = "zhangwen.hardware-rules/v1"
_VALIDATION_SCHEMA = "zhangwen.hardware-validation/v1"
_MECHANICAL_SCHEMA = "zhangwen.hardware-mechanical/v1"
_SPEC_FENCE = "zhangwen:hardware-spec:v1"
_RULES_FENCE = "zhangwen:hardware-rules:v1"
_VALIDATION_FENCE = "zhangwen:hardware-validation:v1"
_MECHANICAL_FENCE = "zhangwen:hardware-mechanical:v1"
_SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,78}[a-z0-9])?$")
_REVISION_RE = re.compile(r"^[a-f0-9]{24}$")
_MEDIA_PATH_RE = re.compile(
    r"^assets/[A-Za-z0-9][A-Za-z0-9._-]{0,126}\.(?:jpe?g|png|webp)$",
    re.IGNORECASE,
)
_LINK_RE = re.compile(r"!?\[[^\]]*\]\(([^)]+)\)")
_WINDOWS_ABSOLUTE_RE = re.compile(r"(?i)(?:^|[\s(])(?:[a-z]:\\|\\\\)[^\s)]*")
_SERIAL_RE = re.compile(r"(?i)\bCOM\d{1,4}\b|/dev/(?:tty|cu)\S+")
_SECRET_RES: tuple[re.Pattern[str], ...] = (
    re.compile(
        r"(?i)\b(?:api[_ -]?key|access[_ -]?token|secret|password|wifi[_ -]?(?:password|passphrase))\b"
        r"\s*[:=]\s*"
        r"(?!none\b|null\b|nil\b|undefined\b|false\b|0\b|<[^>\s]+>|\$\{[^}\s]+\}|['\"]{2}(?:\s|[,;)}\]]|$))"
        r"\S+"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{8,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._-]{8,}"),
)
_PACKAGE_LOCK = RLock()
_VERIFICATION_RANK = {
    "MIGRATED_UNVERIFIED": 0,
    "USER_CONFIRMED": 1,
    "VERIFIED": 2,
    "OFFICIAL_DOC_VERIFIED": 3,
}

_FILE_META: dict[str, tuple[str, str]] = {
    "README.md": ("器件包说明", "entry"),
    "CHANGELOG.md": ("器件包变更记录", "reference"),
    "SKILL.md": ("Hardware Skill", "entry"),
    "references/specifications.md": ("结构化参数", "reference"),
    "references/compatibility-rules.md": ("兼容规则", "reference"),
    "references/mechanical.md": ("结构与机械档案", "reference"),
    "references/integration.md": ("集成说明", "reference"),
    "references/safety.md": ("安全边界", "reference"),
    "references/sources.md": ("资料来源", "reference"),
    "models/cadquery.py": ("CadQuery 参考模型", "model"),
    "examples/usage.md": ("使用示例", "example"),
    "tests/validation-cases.md": ("验证用例", "test"),
}

_FIELD_ALLOWLIST = {
    "electrical.voltage",
    "electrical.logicLevel",
    "electrical.peakCurrent",
    "electrical.communicationProtocol",
    "electrical.i2cAddress",
    "electrical.supportedMCUs",
    "electrical.driverName",
    "electrical.firmwareRequirement",
    "identifiers",
}
_PARAM_KEYS: dict[HardwareRuleOperator, set[str]] = {
    HardwareRuleOperator.RANGE_OVERLAP: {
        "field",
        "leftCategories",
        "rightCategories",
        "tolerance",
        "componentId",
    },
    HardwareRuleOperator.SUM_LTE: {
        "field",
        "sumCategories",
        "limitCategories",
        "componentId",
    },
    HardwareRuleOperator.UNIQUE: {
        "field",
        "whenField",
        "whenEquals",
        "componentId",
    },
    HardwareRuleOperator.CONTAINS_ANY: {
        "field",
        "candidateField",
        "subjectCategories",
        "candidateCategories",
        "componentId",
    },
    HardwareRuleOperator.REQUIRED_IF: {
        "requiredField",
        "ifField",
        "ifPresent",
        "ifEquals",
        "componentId",
    },
}


class HardwareSkillError(RuntimeError):
    """Base Hardware Skill failure."""


class HardwareSkillNotFoundError(HardwareSkillError):
    """Requested active package or draft does not exist."""


class HardwareSkillConflictError(HardwareSkillError):
    """Revision compare-and-swap failed."""


class HardwareSkillValidationError(HardwareSkillError):
    """Package, source, or rule failed the local safety boundary."""


class _ManifestMedia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    role: str
    alt: str
    contentType: str
    sha256: str
    sourceUrl: str
    attribution: str
    license: str


class _Manifest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: str = Field(alias="schema")
    schemaVersion: int
    skillName: str
    componentId: str
    displayName: str
    description: str
    status: HardwareSkillStatus
    sourceKind: HardwareSkillSourceKind
    files: list[str]
    media: list[_ManifestMedia] = Field(default_factory=list)
    revision: str
    createdAt: str
    updatedAt: str


class _MechanicalModelReference(BaseModel):
    model_config = ConfigDict(extra="forbid")

    path: str
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    verificationStatus: str = Field(min_length=1, max_length=100)
    executionPolicy: str


class _MechanicalDeclaration(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        populate_by_name=True,
        serialize_by_alias=True,
    )

    schema_: str = Field(alias="schema")
    profile: dict[str, Any]
    model: _MechanicalModelReference


@dataclass(frozen=True)
class BundledCatalogInstallResult:
    installed: int = 0
    preserved: int = 0
    invalidExisting: int = 0


@dataclass(frozen=True)
class HardwareContextEntry:
    """One validated catalog item reused throughout a context assembly."""

    component: HardwareComponent
    markdown: str
    rules: tuple[HardwareSkillRule, ...]


@dataclass(frozen=True)
class HardwareContextCandidate:
    """Lightweight manifest/spec projection used only to rank context candidates."""

    component: HardwareComponent
    summary: HardwareSkillSummary
    searchText: str


_CONTEXT_CANDIDATE_CACHE: dict[
    tuple[str, bool],
    tuple[HardwareContextCandidate, ...],
] = {}


class _CatalogCandidateRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    component: HardwareComponent
    summary: HardwareSkillSummary
    searchText: str = Field(max_length=16_000)


class _HardwareCatalogIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schemaVersion: int = Field(ge=1, le=1)
    preserveRetired: bool
    generatedAt: str
    candidates: list[_CatalogCandidateRecord]


def _clone_context_candidates(
    candidates: Sequence[HardwareContextCandidate],
) -> list[HardwareContextCandidate]:
    return [
        HardwareContextCandidate(
            component=candidate.component.model_copy(deep=True),
            summary=candidate.summary.model_copy(deep=True),
            searchText=candidate.searchText,
        )
        for candidate in candidates
    ]


class HardwareSkillRepository:
    """Read, validate, migrate, and atomically replace Hardware Skills."""

    def __init__(self, data_dir: Path, db_path: Path) -> None:
        self._data_dir = Path(data_dir)
        self._db_path = Path(db_path)
        self._root = self._data_dir / "hardware-skills"
        self._draft_root = self._data_dir / ".hardware-skill-drafts"
        self._catalog_index_path = (
            self._data_dir / "cache" / "hardware-catalog-v1.json"
        )
        self._lock = _PACKAGE_LOCK

    @property
    def root(self) -> Path:
        return self._root

    def install_bundled_catalog(
        self,
        source_root: Path = BUNDLED_HARDWARE_CATALOG_ROOT,
    ) -> BundledCatalogInstallResult:
        """Install missing validated packages without replacing user-owned packages."""
        source_root = Path(source_root)
        if not source_root.exists():
            return BundledCatalogInstallResult()
        if not source_root.is_dir() or source_root.is_symlink():
            raise HardwareSkillValidationError("内置硬件目录不是有效目录。")

        installed = 0
        preserved = 0
        invalid_existing = 0
        with self._lock:
            for source in sorted(source_root.iterdir(), key=lambda item: item.name):
                if not source.is_dir() or source.is_symlink() or source.name.startswith("."):
                    continue
                manifest, files, _, _, _ = self._load_package(source)
                media_payloads = self._read_media_payloads(source, manifest)
                target = self._root / manifest.skillName
                if target.exists():
                    preserved += 1
                    try:
                        (
                            existing_manifest,
                            _,
                            existing_specification,
                            _,
                            existing_mechanical_profile,
                        ) = self._load_package(target)
                        self._sync_projection(
                            existing_manifest,
                            existing_specification,
                            existing_mechanical_profile,
                        )
                    except (
                        HardwareSkillNotFoundError,
                        HardwareSkillValidationError,
                        ValidationError,
                        OSError,
                    ):
                        invalid_existing += 1
                    continue
                self._write_package(
                    manifest.model_copy(deep=True),
                    files,
                    sync_projection=True,
                    require_absent=True,
                    media_payloads=media_payloads,
                )
                installed += 1
        return BundledCatalogInstallResult(
            installed=installed,
            preserved=preserved,
            invalidExisting=invalid_existing,
        )

    def _legacy_overlay_sections(
        self,
        component_id: str,
    ) -> tuple[dict[str, str], list[str]]:
        legacy_root = self._data_dir / _LEGACY_OVERLAY_DIRECTORY / component_id
        if not legacy_root.exists():
            return {}, []
        if legacy_root.is_symlink() or not legacy_root.is_dir():
            raise HardwareSkillValidationError("旧器件 Markdown 目录类型无效，不能安全迁移。")
        data_root = self._data_dir.resolve(strict=False)
        resolved_root = legacy_root.resolve(strict=False)
        if not resolved_root.is_relative_to(data_root):
            raise HardwareSkillValidationError("旧器件 Markdown 目录超出数据目录。")

        sections: dict[str, str] = {}
        sources: list[str] = []
        for legacy_path, (target_path, heading) in _LEGACY_OVERLAY_FILES.items():
            source = legacy_root / Path(*PurePosixPath(legacy_path).parts)
            if not source.exists():
                continue
            if source.is_symlink() or not source.is_file():
                raise HardwareSkillValidationError(
                    f"旧器件 Markdown 文件类型无效：{legacy_path}。"
                )
            if not source.resolve(strict=False).is_relative_to(resolved_root):
                raise HardwareSkillValidationError("旧器件 Markdown 文件超出器件目录。")
            try:
                content = source.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as exc:
                raise HardwareSkillValidationError(
                    f"旧器件 Markdown 不是有效 UTF-8：{legacy_path}。"
                ) from exc
            if len(content.encode("utf-8")) > MAX_SKILL_FILE_BYTES:
                raise HardwareSkillValidationError(
                    f"旧器件 Markdown 超出迁移大小限制：{legacy_path}。"
                )
            _validate_text_boundary(content, legacy_path)
            sections[target_path] = (
                f"\n\n## {heading}\n\n{content.strip()}\n"
            )
            sources.append(f"legacy-overlay:{component_id}:{legacy_path}")
        return sections, sources

    def migrate_legacy_rows(
        self,
        *,
        reconcile_obsolete: bool = True,
        _known_components: Mapping[str, str] | None = None,
    ) -> None:
        """Create canonical packages for rows that do not have one yet."""
        with self._lock:
            known = (
                dict(_known_components)
                if _known_components is not None
                else self._component_skill_index(ignore_invalid=True)
            )
            with self._connect() as conn:
                rows = conn.execute(
                    "SELECT * FROM hardware_components ORDER BY created_at, id"
                ).fetchall()
            for row in rows:
                component_id = str(row["id"])
                if component_id in known:
                    continue
                component = _component_from_row(row)
                if component_id == _BUNDLED_K10_COMPONENT_ID:
                    detail = self._install_bundled_k10(component)
                    known[component_id] = detail.skillName
                    continue
                legacy_sections, legacy_sources = self._legacy_overlay_sections(component_id)
                source_ids = [f"sqlite:{component_id}", *legacy_sources]
                specification = self.specification_from_component(
                    component,
                    verification_status="MIGRATED_UNVERIFIED",
                    source_ids=source_ids,
                )
                skill_name = self._unique_skill_name(
                    _slug_for(component.name, component_id)
                )
                self.create_skill(
                    specification,
                    skill_name=skill_name,
                    description=component.notes or f"{component.name} 的硬件规则与工程说明。",
                    status=(
                        HardwareSkillStatus.ACTIVE
                        if component.status == HardwareComponentStatus.ACTIVE
                        else HardwareSkillStatus.ARCHIVED
                    ),
                    source_kind=HardwareSkillSourceKind.MIGRATED,
                    created_at=component.createdAt,
                    updated_at=component.updatedAt,
                    sync_projection=True,
                    migrated_sections=legacy_sections,
                )
                known[component_id] = skill_name
            if reconcile_obsolete:
                self._reconcile_obsolete_packages()

    def _reconcile_obsolete_packages(self) -> None:
        """Merge newer or better verified allowlisted content into a valid successor.

        Older builds allowed extra top-level package files. Those directories are
        intentionally left untouched, but their still-valid canonical files may be
        copied into the current active package after full validation.
        """
        valid_index = self._component_skill_index(ignore_invalid=True)
        if not self._root.exists():
            return
        for root in sorted(self._root.iterdir(), key=lambda item: item.name):
            if not root.is_dir() or root.is_symlink() or root.name.startswith("."):
                continue
            try:
                self._load_package(root)
                continue
            except (
                HardwareSkillNotFoundError,
                HardwareSkillValidationError,
                ValidationError,
            ):
                pass
            legacy = self._read_obsolete_package(root)
            if legacy is None:
                continue
            component_id, legacy_updated_at, files = legacy
            target_name = valid_index.get(component_id)
            if not target_name or target_name == root.name:
                continue
            try:
                target = self.get_skill(target_name, include_archived=True)
                if target.status != HardwareSkillStatus.ACTIVE:
                    continue
                target_manifest = self._read_manifest(self._root / target_name)
                files["SKILL.md"] = _replace_skill_frontmatter_name(
                    files["SKILL.md"],
                    target_name,
                )
                imported_specification = HardwareSkillSpecification(
                    **_extract_fenced_json(
                        files["references/specifications.md"],
                        _SPEC_FENCE,
                    )
                )
                files["references/compatibility-rules.md"] = (
                    _sanitize_imported_rules(
                        files["references/compatibility-rules.md"],
                        imported_specification,
                    )
                )
                legacy_specification, _, _ = _validate_package_content(
                    target_manifest,
                    files,
                )
                legacy_rank = _VERIFICATION_RANK.get(
                    legacy_specification.verificationStatus,
                    1,
                )
                target_rank = _VERIFICATION_RANK.get(
                    target.specification.verificationStatus,
                    1,
                )
                if legacy_rank < target_rank or (
                    legacy_rank == target_rank
                    and not _is_later_timestamp(legacy_updated_at, target.updatedAt)
                ):
                    continue
                target_manifest.updatedAt = _now()
                self._write_package(
                    target_manifest,
                    files,
                    sync_projection=True,
                )
            except (
                HardwareSkillNotFoundError,
                HardwareSkillValidationError,
                ValidationError,
            ):
                # Invalid imported content remains quarantined in its original
                # directory and never replaces the current active package.
                continue

    def _read_obsolete_package(
        self,
        root: Path,
    ) -> tuple[str, str, dict[str, str]] | None:
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            return None
        try:
            raw = manifest_path.read_bytes()
            if len(raw) > MAX_SKILL_FILE_BYTES:
                return None
            manifest = json.loads(raw.decode("utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError):
            return None
        if not isinstance(manifest, dict):
            return None
        if (
            manifest.get("schema") != _MANIFEST_SCHEMA
            or manifest.get("schemaVersion") != 1
            or manifest.get("skillName") != root.name
            or not isinstance(manifest.get("componentId"), str)
            or not isinstance(manifest.get("updatedAt"), str)
            or not isinstance(manifest.get("files"), list)
            or not set(HARDWARE_SKILL_PATHS).issubset(set(manifest["files"]))
        ):
            return None
        files: dict[str, str] = {}
        total = 0
        try:
            for relative in HARDWARE_SKILL_PATHS:
                path = root / PurePosixPath(relative)
                if not path.is_file() or path.is_symlink():
                    return None
                content = path.read_text(encoding="utf-8")
                total += len(content.encode("utf-8"))
                if total > MAX_SKILL_PACKAGE_BYTES:
                    return None
                files[relative] = content
        except (OSError, UnicodeError):
            return None
        return str(manifest["componentId"]), str(manifest["updatedAt"]), files

    def ensure_component_migrated(self, component_id: str) -> HardwareSkillDetail:
        with self._lock:
            # Quarantine malformed legacy/import directories instead of allowing one
            # unrelated package to make every otherwise valid component unselectable.
            existing = self._component_skill_index(ignore_invalid=True).get(component_id)
            if existing:
                detail = self.get_skill(existing, include_archived=True)
                if component_id == _BUNDLED_K10_COMPONENT_ID:
                    detail = self._upgrade_bundled_k10(detail)
                return self._ensure_bundled_media(detail)
            with self._connect() as conn:
                row = conn.execute(
                    "SELECT * FROM hardware_components WHERE id = ?",
                    (component_id,),
                ).fetchone()
            if row is None:
                raise HardwareSkillNotFoundError("硬件组件不存在。")
            component = _component_from_row(row)
            if component_id == _BUNDLED_K10_COMPONENT_ID:
                return self._ensure_bundled_media(
                    self._install_bundled_k10(component)
                )
            legacy_sections, legacy_sources = self._legacy_overlay_sections(component.id)
            specification = self.specification_from_component(
                component,
                verification_status="MIGRATED_UNVERIFIED",
                source_ids=[f"sqlite:{component.id}", *legacy_sources],
            )
            skill_name = self._unique_skill_name(_slug_for(component.name, component.id))
            detail = self.create_skill(
                specification,
                skill_name=skill_name,
                description=component.notes or f"{component.name} 的硬件规则与工程说明。",
                status=(
                    HardwareSkillStatus.ACTIVE
                    if component.status == HardwareComponentStatus.ACTIVE
                    else HardwareSkillStatus.ARCHIVED
                ),
                source_kind=HardwareSkillSourceKind.MIGRATED,
                created_at=component.createdAt,
                updated_at=component.updatedAt,
                sync_projection=True,
                migrated_sections=legacy_sections,
            )
            return self._ensure_bundled_media(detail)

    def list_skills(self, *, include_archived: bool = False) -> list[HardwareSkillSummary]:
        if not include_archived:
            return [
                candidate.summary.model_copy(deep=True)
                for candidate in self.list_active_context_candidates()
            ]
        details = self._validated_catalog_details(
            include_archived=include_archived,
            reconcile_obsolete=True,
        )
        summaries = [
            HardwareSkillSummary(
                **detail.model_dump(exclude={"files", "specification", "rules"})
            )
            for _, detail in details
        ]
        return sorted(
            summaries,
            key=lambda item: (item.category.value, item.displayName.casefold()),
        )

    def _prepare_catalog(self, *, reconcile_obsolete: bool) -> None:
        self.retire_legacy_seed_packages()
        self.migrate_legacy_rows(reconcile_obsolete=reconcile_obsolete)
        k10_name = self._component_skill_index(ignore_invalid=True).get(
            "hw_seed_unihiker_k10"
        )
        if k10_name:
            try:
                detail = self.get_skill(k10_name, include_archived=True)
                self._ensure_bundled_media(self._upgrade_bundled_k10(detail))
            except (HardwareSkillValidationError, HardwareSkillNotFoundError):
                # A damaged K10 overlay must fail closed without making every
                # unrelated valid Hardware Skill disappear from the catalog.
                pass

    def _validated_catalog_details(
        self,
        *,
        include_archived: bool,
        reconcile_obsolete: bool,
    ) -> list[tuple[_Manifest, HardwareSkillDetail]]:
        self._prepare_catalog(reconcile_obsolete=reconcile_obsolete)
        if not self._root.exists():
            return []
        details: list[tuple[_Manifest, HardwareSkillDetail]] = []
        for path in sorted(self._root.iterdir(), key=lambda item: item.name):
            if not path.is_dir() or path.is_symlink() or path.name.startswith("."):
                continue
            try:
                manifest, files, specification, rules, mechanical_profile = (
                    self._load_package(path)
                )
                detail = _detail(
                    manifest,
                    files,
                    specification,
                    rules,
                    mechanical_profile,
                )
            except (HardwareSkillValidationError, HardwareSkillNotFoundError):
                continue
            if not include_archived and detail.status != HardwareSkillStatus.ACTIVE:
                continue
            details.append((manifest, detail))
        return sorted(
            details,
            key=lambda item: (
                item[1].category.value,
                item[1].displayName.casefold(),
            ),
        )

    def retire_legacy_seed_packages(self) -> None:
        """Remove retired built-in samples from the active catalog, reversibly."""
        if os.getenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE") == "1":
            return
        if not self._root.exists():
            return
        data_root = self._data_dir.resolve(strict=False)
        catalog_root = self._root.resolve(strict=False)
        if not catalog_root.is_relative_to(data_root):
            raise HardwareSkillValidationError("Hardware Skill 目录超出数据目录。")
        retired_root = self._data_dir / "retired-hardware-seeds"
        with self._lock:
            for path in list(self._root.iterdir()):
                if not path.is_dir() or path.is_symlink() or path.name.startswith("."):
                    continue
                try:
                    manifest = self._read_manifest(path)
                except HardwareSkillValidationError:
                    continue
                if (
                    manifest.componentId not in RETIRED_DEFAULT_COMPONENT_IDS
                    or manifest.sourceKind
                    not in {
                        HardwareSkillSourceKind.MIGRATED,
                        HardwareSkillSourceKind.BUNDLED,
                    }
                ):
                    continue
                resolved = path.resolve(strict=False)
                if not resolved.is_relative_to(catalog_root):
                    raise HardwareSkillValidationError("待退役 Hardware Skill 超出目录。")
                component_root = retired_root / manifest.componentId
                component_root.mkdir(parents=True, exist_ok=True)
                destination = component_root / (
                    f"{manifest.skillName}-{manifest.revision}"
                )
                if destination.exists():
                    destination = component_root / (
                        f"{manifest.skillName}-{manifest.revision}-{uuid.uuid4().hex[:8]}"
                    )
                os.replace(path, destination)

    def read_media(
        self,
        skill_name: str,
        asset_name: str,
    ) -> tuple[HardwareMediaAsset, bytes]:
        _validate_skill_name(skill_name)
        if "/" in asset_name or "\\" in asset_name:
            raise HardwareSkillNotFoundError("硬件图片不存在。")
        root = self._root / skill_name
        manifest, _, _, _, _ = self._load_package(root)
        relative = f"assets/{asset_name}"
        media = next((item for item in manifest.media if item.path == relative), None)
        if media is None:
            raise HardwareSkillNotFoundError("硬件图片不存在。")
        payloads = self._read_media_payloads(root, manifest)
        return _media_asset(manifest.skillName, media), payloads[relative]

    def _ensure_bundled_media(
        self,
        detail: HardwareSkillDetail,
    ) -> HardwareSkillDetail:
        if detail.componentId != "hw_seed_unihiker_k10" or detail.media:
            return detail
        source = Path(__file__).with_name("catalog-assets") / "unihiker-k10-cover.webp"
        if not source.is_file() or source.is_symlink():
            raise HardwareSkillValidationError("内置 K10 封面资源缺失。")
        payload = source.read_bytes()
        digest = hashlib.sha256(payload).hexdigest()
        if digest != "fcae7395e90bcef49f7c727366b12e1d3073705c0f8b36643e04466624e310e1":
            raise HardwareSkillValidationError("内置 K10 封面资源校验失败。")
        root = self._root / detail.skillName
        manifest, files, _, _, _ = self._load_package(root)
        manifest.media = [
            _ManifestMedia(
                path="assets/cover.webp",
                role="cover",
                alt="行空板 K10 正面产品图",
                contentType="image/webp",
                sha256=digest,
                sourceUrl="https://www.dfrobot.com/product-2904.html",
                attribution="DFRobot",
                license="用于产品识别；公开再分发前请确认 DFRobot 图片授权。",
            )
        ]
        manifest.updatedAt = _now()
        return self._write_package(
            manifest,
            files,
            sync_projection=True,
            media_payloads={"assets/cover.webp": payload},
        )

    def _install_bundled_k10(
        self,
        component: HardwareComponent,
    ) -> HardwareSkillDetail:
        source_manifest, files = self._read_bundled_k10()
        skill_name = self._unique_skill_name(_BUNDLED_K10_SKILL_NAME)
        if skill_name != source_manifest.skillName:
            files["SKILL.md"] = _replace_skill_frontmatter_name(
                files["SKILL.md"],
                skill_name,
            )
        manifest = source_manifest.model_copy(deep=True)
        manifest.skillName = skill_name
        manifest.createdAt = component.createdAt
        manifest.updatedAt = max(component.updatedAt, source_manifest.updatedAt)
        return self._write_package(
            manifest,
            files,
            sync_projection=True,
            require_absent=True,
        )

    def _upgrade_bundled_k10(
        self,
        detail: HardwareSkillDetail,
    ) -> HardwareSkillDetail:
        current_files = {file.path: file.content for file in detail.files}
        if set(HARDWARE_SKILL_MECHANICAL_PATHS).issubset(current_files):
            return detail
        source_manifest, bundled_files = self._read_bundled_k10()
        manifest = self._read_manifest(self._root / detail.skillName)
        replace_generated_content = (
            manifest.sourceKind
            in {HardwareSkillSourceKind.MIGRATED, HardwareSkillSourceKind.BUNDLED}
            and _VERIFICATION_RANK.get(detail.verificationStatus, 0)
            < _VERIFICATION_RANK["OFFICIAL_DOC_VERIFIED"]
        )
        if replace_generated_content:
            files = dict(bundled_files)
            files["SKILL.md"] = _replace_skill_frontmatter_name(
                files["SKILL.md"],
                detail.skillName,
            )
            manifest.sourceKind = HardwareSkillSourceKind.BUNDLED
        else:
            files = dict(current_files)
            for path in source_manifest.files:
                if path not in files:
                    files[path] = bundled_files[path]
        manifest.files = list(source_manifest.files)
        manifest.updatedAt = _now()
        return self._write_package(
            manifest,
            files,
            sync_projection=True,
        )

    def _read_bundled_k10(self) -> tuple[_Manifest, dict[str, str]]:
        root = Path(__file__).with_name("bundled-hardware-skills") / "k10"
        manifest, files, _, _, _ = self._load_package(root)
        return manifest, dict(files)

    def get_skill(
        self,
        skill_name: str,
        *,
        include_archived: bool = False,
    ) -> HardwareSkillDetail:
        _validate_skill_name(skill_name)
        root = self._root / skill_name
        manifest, files, specification, rules, mechanical_profile = self._load_package(
            root
        )
        if manifest.status == HardwareSkillStatus.ARCHIVED and not include_archived:
            raise HardwareSkillNotFoundError("Hardware Skill 已归档。")
        return _detail(
            manifest,
            files,
            specification,
            rules,
            mechanical_profile,
        )

    def get_active_by_component_id(self, component_id: str) -> HardwareSkillDetail:
        detail = self.ensure_component_migrated(component_id)
        if detail.status != HardwareSkillStatus.ACTIVE:
            raise HardwareSkillNotFoundError("Hardware Skill 未激活。")
        return detail

    def get_active_component(self, component_id: str) -> HardwareComponent:
        detail = self.get_active_by_component_id(component_id)
        return self.component_from_detail(detail)

    def list_active_components(
        self,
        *,
        category: str | None = None,
        search: str | None = None,
        include_archived: bool = False,
    ) -> list[HardwareComponent]:
        if not include_archived:
            components: list[HardwareComponent] = []
            needle = search.strip().casefold() if search and search.strip() else ""
            for candidate in self.list_active_context_candidates():
                component = candidate.component
                if not _supported_controller_component(component):
                    continue
                if category and component.category.value != category:
                    continue
                if needle and needle not in candidate.searchText.casefold():
                    continue
                components.append(component.model_copy(deep=True))
            return components

        components: list[HardwareComponent] = []
        for manifest, detail in self._validated_catalog_details(
            include_archived=include_archived,
            reconcile_obsolete=True,
        ):
            if detail.status != HardwareSkillStatus.ACTIVE and not (
                include_archived and detail.status == HardwareSkillStatus.ARCHIVED
            ):
                continue
            if (
                detail.category == HardwareCategory.MCU
                and detail.componentId not in SUPPORTED_CONTROLLER_COMPONENT_IDS
            ):
                continue
            if category and detail.category.value != category:
                continue
            if search and search.strip():
                needle = search.strip().casefold()
                searchable = " ".join(
                    [
                        detail.displayName,
                        detail.description,
                        detail.specification.notes,
                        " ".join(detail.specification.safetyTags),
                        json.dumps(detail.specification.electrical.model_dump(mode="json"), ensure_ascii=False),
                    ]
                ).casefold()
                if needle not in searchable:
                    continue
            components.append(
                self._component_from_detail(detail, created_at=manifest.createdAt)
            )
        return components

    def list_active_context_candidates(self) -> list[HardwareContextCandidate]:
        """Read the persisted display index without rescanning Hardware Skill packages."""

        preserve_retired = os.getenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE") == "1"
        cache_key = (str(self._root.resolve(strict=False)), preserve_retired)
        with self._lock:
            cached = _CONTEXT_CANDIDATE_CACHE.get(cache_key)
            if cached is not None:
                return _clone_context_candidates(cached)
            persisted = self._read_catalog_index(preserve_retired=preserve_retired)
            if persisted is not None:
                _CONTEXT_CANDIDATE_CACHE[cache_key] = tuple(persisted)
                return _clone_context_candidates(persisted)

        return self.refresh_active_catalog()

    def refresh_active_catalog(self) -> list[HardwareContextCandidate]:
        """Fully validate the catalog once and atomically replace its display index."""

        preserve_retired = os.getenv("ZHANGWEN_TEST_PRESERVE_RETIRED_HARDWARE") == "1"
        cache_key = (str(self._root.resolve(strict=False)), preserve_retired)
        with self._lock:
            candidates: list[HardwareContextCandidate] = []
            for manifest, detail in self._validated_catalog_details(
                include_archived=False,
                reconcile_obsolete=True,
            ):
                if (
                    not preserve_retired
                    and manifest.componentId in RETIRED_DEFAULT_COMPONENT_IDS
                ):
                    continue
                component = self._component_from_detail(
                    detail,
                    created_at=manifest.createdAt,
                )
                if not _supported_controller_component(component):
                    continue
                summary = HardwareSkillSummary(
                    **detail.model_dump(exclude={"files", "specification", "rules"})
                )
                search_text = "\n".join(
                    [
                        detail.displayName,
                        detail.description,
                        detail.specification.model_dump_json(),
                        *(file.content for file in detail.files),
                    ]
                )[:16_000]
                candidates.append(
                    HardwareContextCandidate(
                        component=component,
                        summary=summary,
                        searchText=search_text,
                    )
                )
            result = sorted(
                candidates,
                key=lambda item: (
                    item.component.category.value,
                    item.component.name.casefold(),
                ),
            )
            self._write_catalog_index(
                preserve_retired=preserve_retired,
                candidates=result,
            )
            _CONTEXT_CANDIDATE_CACHE[cache_key] = tuple(result)
            return _clone_context_candidates(result)

    def _read_catalog_index(
        self,
        *,
        preserve_retired: bool,
    ) -> list[HardwareContextCandidate] | None:
        path = self._catalog_index_path
        try:
            if not path.is_file() or path.is_symlink():
                return None
            raw = path.read_bytes()
            if len(raw) > 4 * 1024 * 1024:
                return None
            index = _HardwareCatalogIndex.model_validate_json(raw)
        except (OSError, ValidationError, ValueError):
            return None
        if index.preserveRetired != preserve_retired:
            return None
        candidates: list[HardwareContextCandidate] = []
        component_ids: set[str] = set()
        skill_names: set[str] = set()
        for record in index.candidates:
            component = record.component
            summary = record.summary
            if (
                component.status != HardwareComponentStatus.ACTIVE
                or summary.status != HardwareSkillStatus.ACTIVE
                or component.id != summary.componentId
                or component.skillName != summary.skillName
                or component.skillRevision != summary.revision
                or component.id in component_ids
                or component.skillName in skill_names
                or not _supported_controller_component(component)
            ):
                return None
            component_ids.add(component.id)
            skill_names.add(component.skillName)
            candidates.append(
                HardwareContextCandidate(
                    component=component.model_copy(deep=True),
                    summary=summary.model_copy(deep=True),
                    searchText=record.searchText,
                )
            )
        return candidates

    def _write_catalog_index(
        self,
        *,
        preserve_retired: bool,
        candidates: Sequence[HardwareContextCandidate],
    ) -> None:
        path = self._catalog_index_path
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.parent.is_symlink():
            raise HardwareSkillValidationError("硬件目录索引位置无效。")
        index = _HardwareCatalogIndex(
            schemaVersion=1,
            preserveRetired=preserve_retired,
            generatedAt=_now(),
            candidates=[
                _CatalogCandidateRecord(
                    component=candidate.component,
                    summary=candidate.summary,
                    searchText=candidate.searchText,
                )
                for candidate in candidates
            ],
        )
        payload = index.model_dump_json(indent=2).encode("utf-8")
        temporary = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _read_context_candidate(
        self,
        root: Path,
        manifest: _Manifest,
    ) -> tuple[HardwareSkillSpecification, str]:
        specification_path = root / "references" / "specifications.md"
        if (
            not specification_path.is_file()
            or specification_path.is_symlink()
            or "references/specifications.md" not in manifest.files
        ):
            raise HardwareSkillValidationError("Hardware Skill 缺少有效技术规格。")
        raw = specification_path.read_bytes()
        if len(raw) > MAX_SKILL_FILE_BYTES:
            raise HardwareSkillValidationError("references/specifications.md 超出单文件大小限制。")
        try:
            specification_text = _normalize_text(raw.decode("utf-8"))
        except UnicodeDecodeError as exc:
            raise HardwareSkillValidationError(
                "references/specifications.md 不是有效 UTF-8。"
            ) from exc
        try:
            specification = HardwareSkillSpecification(
                **_extract_fenced_json(specification_text, _SPEC_FENCE)
            )
        except (ValueError, ValidationError) as exc:
            raise HardwareSkillValidationError("Hardware Skill 技术规格无效。") from exc
        if specification.componentId != manifest.componentId:
            raise HardwareSkillValidationError("Hardware Skill 组件身份与 manifest 不一致。")

        search_parts = [
            manifest.displayName,
            manifest.description,
            specification_text,
        ]
        return specification, "\n".join(search_parts)[:16_000]

    def list_active_context_entries(
        self,
        *,
        candidates: Sequence[HardwareContextCandidate] | None = None,
        max_chars: int = MAX_CONTEXT_CHARS,
        required_component_ids: set[str] | None = None,
    ) -> list[HardwareContextEntry]:
        """Fully validate only the candidates selected for trusted prompt context."""

        if max_chars < 1 or max_chars > MAX_CONTEXT_CHARS:
            raise HardwareSkillValidationError("Hardware Skill 上下文长度超出允许范围。")
        selected_candidates = list(candidates or self.list_active_context_candidates())
        required_ids = required_component_ids or set()
        entries: list[HardwareContextEntry] = []
        for candidate in selected_candidates:
            component_id = candidate.component.id
            root = self._root / candidate.component.skillName
            try:
                manifest, files, specification, rules, mechanical_profile = (
                    self._load_package(root)
                )
                if (
                    manifest.status != HardwareSkillStatus.ACTIVE
                    or manifest.componentId != component_id
                ):
                    raise HardwareSkillNotFoundError("Hardware Skill 未激活。")
                detail = _detail(
                    manifest,
                    files,
                    specification,
                    rules,
                    mechanical_profile,
                )
                if component_id == _BUNDLED_K10_COMPONENT_ID:
                    detail = self._ensure_bundled_media(
                        self._upgrade_bundled_k10(detail)
                    )
                    manifest = self._read_manifest(self._root / detail.skillName)
                entries.append(
                    HardwareContextEntry(
                        component=self._component_from_detail(
                            detail,
                            created_at=manifest.createdAt,
                        ),
                        markdown=_render_detail_context(detail, max_chars=max_chars),
                        rules=tuple(detail.rules),
                    )
                )
            except (HardwareSkillValidationError, HardwareSkillNotFoundError):
                if component_id in required_ids:
                    raise
        loaded_ids = {entry.component.id for entry in entries}
        missing_required = required_ids - loaded_ids
        if missing_required:
            raise HardwareSkillNotFoundError(
                "项目已选硬件 Skill 不存在、未激活或未通过完整校验："
                + "、".join(sorted(missing_required))
            )
        return entries

    def component_from_detail(self, detail: HardwareSkillDetail) -> HardwareComponent:
        manifest = self._read_manifest(self._root / detail.skillName)
        return self._component_from_detail(detail, created_at=manifest.createdAt)

    def _component_from_detail(
        self,
        detail: HardwareSkillDetail,
        *,
        created_at: str,
    ) -> HardwareComponent:
        if detail.status == HardwareSkillStatus.ACTIVE:
            status = HardwareComponentStatus.ACTIVE
        elif detail.status == HardwareSkillStatus.ARCHIVED:
            status = HardwareComponentStatus.ARCHIVED
        else:
            raise HardwareSkillNotFoundError("Hardware Skill 未激活。")
        return HardwareComponent(
            id=detail.componentId,
            name=detail.specification.name,
            category=detail.specification.category,
            status=status,
            electrical=detail.specification.electrical,
            stock=detail.specification.stock,
            price=detail.specification.price,
            ageRecommendation=detail.specification.ageRecommendation,
            safetyTags=list(detail.specification.safetyTags),
            notes=detail.specification.notes,
            createdAt=created_at,
            updatedAt=detail.updatedAt,
            skillName=detail.skillName,
            skillRevision=detail.revision,
            verificationStatus=detail.specification.verificationStatus,
            media=list(detail.media),
        )

    def specification_from_component(
        self,
        component: HardwareComponent,
        *,
        verification_status: str | None = None,
        source_ids: Sequence[str] | None = None,
    ) -> HardwareSkillSpecification:
        return HardwareSkillSpecification(
            componentId=component.id,
            name=component.name,
            category=component.category,
            electrical=component.electrical,
            stock=component.stock,
            price=component.price,
            ageRecommendation=component.ageRecommendation,
            safetyTags=list(component.safetyTags),
            notes=component.notes,
            verificationStatus=(
                verification_status
                or component.verificationStatus
                or "USER_CONFIRMED"
            ),
            sourceIds=list(source_ids or []),
        )

    def create_from_component(
        self,
        component: HardwareComponent,
        *,
        source_kind: HardwareSkillSourceKind = HardwareSkillSourceKind.MANUAL,
    ) -> HardwareSkillDetail:
        specification = self.specification_from_component(
            component,
            verification_status=component.verificationStatus or "USER_CONFIRMED",
            source_ids=[f"manual:{component.id}"],
        )
        return self.create_skill(
            specification,
            skill_name=self._unique_skill_name(_slug_for(component.name, component.id)),
            description=component.notes or f"{component.name} 的硬件规则与工程说明。",
            status=(
                HardwareSkillStatus.ACTIVE
                if component.status == HardwareComponentStatus.ACTIVE
                else HardwareSkillStatus.ARCHIVED
            ),
            source_kind=source_kind,
            created_at=component.createdAt,
            updated_at=component.updatedAt,
            sync_projection=True,
        )

    def replace_from_component(self, component: HardwareComponent) -> HardwareSkillDetail:
        current = self.ensure_component_migrated(component.id)
        specification = self.specification_from_component(
            component,
            verification_status=current.specification.verificationStatus,
            source_ids=current.specification.sourceIds,
        )
        files = {file.path: file.content for file in current.files}
        files["references/specifications.md"] = _specification_markdown(specification)
        files["SKILL.md"] = _skill_markdown(
            current.skillName,
            component.name,
            component.notes or current.description,
        )
        manifest = self._read_manifest(self._root / current.skillName)
        manifest.displayName = component.name
        manifest.description = component.notes or current.description
        manifest.status = (
            HardwareSkillStatus.ACTIVE
            if component.status == HardwareComponentStatus.ACTIVE
            else HardwareSkillStatus.ARCHIVED
        )
        manifest.updatedAt = component.updatedAt
        return self._write_package(manifest, files, sync_projection=True)

    def create_skill(
        self,
        specification: HardwareSkillSpecification,
        *,
        skill_name: str,
        description: str,
        status: HardwareSkillStatus = HardwareSkillStatus.ACTIVE,
        source_kind: HardwareSkillSourceKind = HardwareSkillSourceKind.MANUAL,
        rules: Sequence[HardwareSkillRule] | None = None,
        created_at: str | None = None,
        updated_at: str | None = None,
        sync_projection: bool = True,
        migrated_sections: Mapping[str, str] | None = None,
    ) -> HardwareSkillDetail:
        _validate_skill_name(skill_name)
        if (self._root / skill_name).exists():
            raise HardwareSkillConflictError("Hardware Skill 名称已存在。")
        now = _now()
        description = description.strip() or f"{specification.name} 的硬件规则与工程说明。"
        package_rules = list(rules) if rules is not None else default_rules(specification)
        files = _default_files(skill_name, specification, package_rules, description)
        for path, section in (migrated_sections or {}).items():
            if path not in files:
                raise HardwareSkillValidationError("旧器件 Markdown 迁移目标不在 Skill 白名单。")
            files[path] = f"{files[path].rstrip()}{section}"
        manifest = _Manifest(
            schema=_MANIFEST_SCHEMA,
            schemaVersion=1,
            skillName=skill_name,
            componentId=specification.componentId,
            displayName=specification.name,
            description=description,
            status=status,
            sourceKind=source_kind,
            files=list(HARDWARE_SKILL_PATHS),
            media=[],
            revision="0" * 24,
            createdAt=created_at or now,
            updatedAt=updated_at or now,
        )
        return self._write_package(
            manifest,
            files,
            sync_projection=sync_projection,
            require_absent=True,
        )

    def update_file(
        self,
        skill_name: str,
        *,
        path: str,
        content: str,
        expected_revision: str,
    ) -> HardwareSkillDetail:
        return self.update_files(
            skill_name,
            updates=[(path, content)],
            expected_revision=expected_revision,
        )

    def update_files(
        self,
        skill_name: str,
        *,
        updates: Sequence[tuple[str, str]],
        expected_revision: str,
    ) -> HardwareSkillDetail:
        if not updates:
            raise HardwareSkillValidationError("至少需要更新一个 Hardware Skill 文件。")
        paths = [path for path, _ in updates]
        if len(paths) != len(set(paths)):
            raise HardwareSkillValidationError("同一文件不能在一次保存中重复更新。")
        for path in paths:
            _validate_editable_path(path)
        with self._lock:
            current = self.get_skill(skill_name, include_archived=True)
            if expected_revision != current.revision:
                raise HardwareSkillConflictError(
                    "Hardware Skill 已被其他操作更新，请刷新后重试。"
                )
            files = {file.path: file.content for file in current.files}
            for path, content in updates:
                files[path] = _normalize_text(content)
            manifest = self._read_manifest(self._root / skill_name)
            manifest.updatedAt = _now()
            if "SKILL.md" in paths:
                frontmatter = _parse_frontmatter(files["SKILL.md"])
                if frontmatter["name"] != skill_name:
                    raise HardwareSkillValidationError(
                        "SKILL.md frontmatter 的 name 不能修改 Hardware Skill 身份。"
                    )
                manifest.description = frontmatter["description"]
            return self._write_package(manifest, files, sync_projection=True)

    def archive_component(self, component_id: str) -> HardwareSkillDetail:
        current = self.ensure_component_migrated(component_id)
        manifest = self._read_manifest(self._root / current.skillName)
        manifest.status = HardwareSkillStatus.ARCHIVED
        manifest.updatedAt = _now()
        files = {file.path: file.content for file in current.files}
        return self._write_package(manifest, files, sync_projection=True)

    def validate_component_ids(self, component_ids: Sequence[str]) -> ValidationResult:
        components: list[HardwareComponent] = []
        rules: list[HardwareSkillRule] = []
        missing_ids: list[str] = []
        for component_id in component_ids:
            try:
                detail = self.get_active_by_component_id(component_id)
            except HardwareSkillNotFoundError:
                missing_ids.append(component_id)
                continue
            components.append(self.component_from_detail(detail))
            rules.extend(detail.rules)
        result = validate_components(components, rules=rules)
        if missing_ids:
            result.checks.append(
                ValidationCheck(
                    dimension="component_exists",
                    severity=ValidationSeverity.FAIL,
                    message="存在未找到或未激活的 Hardware Skill。",
                    details=", ".join(missing_ids),
                )
            )
            result.overall = ValidationSeverity.FAIL
            result.message = "硬件组合校验未通过，请先处理失败项。"
        return result

    def render_context(self, component_id: str, *, max_chars: int = MAX_CONTEXT_CHARS) -> str:
        if max_chars < 1 or max_chars > MAX_CONTEXT_CHARS:
            raise HardwareSkillValidationError("Hardware Skill 上下文长度超出允许范围。")
        detail = self.get_active_by_component_id(component_id)
        return _render_detail_context(detail, max_chars=max_chars)

    def create_draft(
        self,
        *,
        name: str | None,
        description: str | None,
        sources: Sequence[HardwareSkillDraftSource],
    ) -> HardwareSkillDraft:
        draft_id = f"hwd_{uuid.uuid4().hex}"
        partial: dict[str, Any] = {
            "schema": "zhangwen.hardware-skill/v1",
            "componentId": f"hw_{uuid.uuid4().hex}",
        }
        if name and name.strip():
            partial["name"] = name.strip()
        if description and description.strip():
            partial["notes"] = description.strip()
        _merge_partial(
            partial,
            _extract_natural_fields("\n".join(value for value in (name, description) if value)),
        )
        metadata: list[dict[str, str]] = []
        diagnostics: list[dict[str, str]] = []
        explicit_rules: list[dict[str, Any]] | None = None
        total_bytes = 0
        source_names: set[str] = set()

        for source in sources:
            normalized_source_name = source.name.casefold()
            if normalized_source_name in source_names:
                raise HardwareSkillValidationError("上传资料名称不能重复。")
            source_names.add(normalized_source_name)
            extracted, source_rules, source_diagnostics, byte_count = _extract_source(source)
            total_bytes += byte_count
            if total_bytes > MAX_SOURCE_TOTAL_BYTES:
                raise HardwareSkillValidationError("上传资料总大小超出允许范围。")
            _merge_partial(partial, extracted)
            if source_rules is not None:
                explicit_rules = source_rules
            diagnostics.extend(source_diagnostics)
            metadata.append({"name": source.name, "mediaType": _media_type(source.mediaType)})
        if metadata and not partial.get("sourceIds"):
            partial["sourceIds"] = [f"upload:{item['name']}" for item in metadata]

        source_kind = (
            HardwareSkillSourceKind.UPLOAD.value
            if sources
            else HardwareSkillSourceKind.DIALOGUE.value
        )
        state = {
            "id": draft_id,
            "partial": partial,
            "rules": explicit_rules,
            "sources": metadata,
            "diagnostics": diagnostics,
            "sourceKind": source_kind,
            "description": description or "",
        }
        self._save_draft_state(state)
        return self._draft_from_state(state)

    def continue_draft(
        self,
        draft_id: str,
        *,
        message: str,
        expected_revision: str,
    ) -> HardwareSkillDraft:
        with self._lock:
            state = self._load_draft_state(draft_id)
            current = self._draft_from_state(state)
            if current.revision != expected_revision:
                raise HardwareSkillConflictError("Hardware Skill 草稿已更新，请刷新后重试。")
            _validate_text_boundary(message, "对话补充")
            extracted, rules = _extract_structured_text(message)
            if not extracted and rules is None:
                state["diagnostics"] = [
                    *[item for item in state.get("diagnostics", []) if item.get("code") != "DIALOGUE_UNSTRUCTURED"],
                    {
                        "path": "conversation",
                        "code": "DIALOGUE_UNSTRUCTURED",
                        "message": "补充内容未包含可验证的字段，请继续提供名称、类别或电气参数。",
                        "severity": "warning",
                    },
                ]
            else:
                _merge_partial(state["partial"], extracted)
                if rules is not None:
                    state["rules"] = rules
                state["diagnostics"] = [
                    item for item in state.get("diagnostics", [])
                    if item.get("code") != "DIALOGUE_UNSTRUCTURED"
                ]
            state["sourceKind"] = HardwareSkillSourceKind.DIALOGUE.value
            self._save_draft_state(state)
            return self._draft_from_state(state)

    def confirm_draft(self, draft_id: str, *, expected_revision: str) -> HardwareSkillDetail:
        with self._lock:
            state = self._load_draft_state(draft_id)
            draft = self._draft_from_state(state)
            if draft.revision != expected_revision:
                raise HardwareSkillConflictError("Hardware Skill 草稿已更新，请刷新后重试。")
            if not draft.canConfirm or draft.specification is None:
                raise HardwareSkillValidationError("草稿仍有阻塞校验问题，不能确认激活。")
            skill_name = self._unique_skill_name(
                _slug_for(draft.specification.name, draft.specification.componentId)
            )
            detail = self.create_skill(
                draft.specification,
                skill_name=skill_name,
                description=(state.get("description") or draft.specification.notes),
                source_kind=HardwareSkillSourceKind(state.get("sourceKind", "DIALOGUE")),
                rules=draft.rules,
                sync_projection=True,
            )
            self.delete_draft(draft_id)
            return detail

    def delete_draft(self, draft_id: str) -> None:
        with self._lock:
            path = self._draft_path(draft_id)
            if not path.exists():
                raise HardwareSkillNotFoundError("Hardware Skill 草稿不存在。")
            path.unlink()

    def _draft_from_state(self, state: Mapping[str, Any]) -> HardwareSkillDraft:
        partial = dict(state.get("partial") or {})
        missing = _missing_questions(partial)
        diagnostics = [HardwareSkillDiagnostic(**item) for item in state.get("diagnostics", [])]
        specification: HardwareSkillSpecification | None = None
        rules: list[HardwareSkillRule] = []
        if not missing:
            try:
                specification = HardwareSkillSpecification(**_complete_spec(partial))
                raw_rules = state.get("rules")
                rules = (
                    _parse_rules_payload(raw_rules, specification)
                    if raw_rules is not None
                    else default_rules(specification)
                )
            except (ValidationError, HardwareSkillValidationError) as exc:
                diagnostics.append(
                    HardwareSkillDiagnostic(
                        path="references/specifications.md",
                        code="STRUCTURE_INVALID",
                        message=_validation_message(exc),
                        severity="error",
                    )
                )
        files = _draft_files(state["id"], partial, specification, rules)
        payload = {
            "id": state["id"],
            "sources": state.get("sources", []),
            "files": [file.model_dump(mode="json") for file in files],
            "specification": specification.model_dump(mode="json") if specification else None,
            "rules": [rule.model_dump(mode="json") for rule in rules],
            "missingQuestions": missing,
            "diagnostics": [item.model_dump(mode="json") for item in diagnostics],
        }
        revision = _hash_json(payload)
        return HardwareSkillDraft(
            id=state["id"],
            revision=revision,
            sources=list(state.get("sources", [])),
            files=files,
            specification=specification,
            rules=rules,
            missingQuestions=missing,
            diagnostics=diagnostics,
            canConfirm=specification is not None and not any(item.severity == "error" for item in diagnostics),
        )

    def _load_package(
        self,
        root: Path,
    ) -> tuple[
        _Manifest,
        dict[str, str],
        HardwareSkillSpecification,
        list[HardwareSkillRule],
        HardwareProfile | None,
    ]:
        if not root.is_dir() or root.is_symlink():
            raise HardwareSkillNotFoundError("Hardware Skill 不存在。")
        manifest = self._read_manifest(root)
        if root.name != manifest.skillName:
            raise HardwareSkillValidationError("Hardware Skill 目录名与 manifest 不一致。")
        files = self._read_files(root, manifest)
        media_payloads = self._read_media_payloads(root, manifest)
        specification, rules, mechanical_profile = _validate_package_content(
            manifest,
            files,
        )
        _validate_manifest_media(manifest, media_payloads)
        revision = _revision(files, manifest.media)
        if revision != manifest.revision:
            raise HardwareSkillValidationError("Hardware Skill 内容 revision 与 manifest 不一致。")
        return manifest, files, specification, rules, mechanical_profile

    def _read_manifest(self, root: Path) -> _Manifest:
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file() or manifest_path.is_symlink():
            raise HardwareSkillValidationError("Hardware Skill 缺少有效 manifest.json。")
        try:
            raw = manifest_path.read_bytes()
            if len(raw) > MAX_SKILL_FILE_BYTES:
                raise HardwareSkillValidationError("manifest.json 超出大小限制。")
            data = json.loads(raw.decode("utf-8"))
            manifest = _Manifest(**data)
        except UnicodeDecodeError as exc:
            raise HardwareSkillValidationError("manifest.json 不是有效 UTF-8。") from exc
        except (json.JSONDecodeError, ValidationError) as exc:
            raise HardwareSkillValidationError("manifest.json 结构无效。") from exc
        if manifest.schema_ != _MANIFEST_SCHEMA or manifest.schemaVersion != 1:
            raise HardwareSkillValidationError("manifest.json schema 版本不受支持。")
        _validate_skill_name(manifest.skillName)
        declared_paths = set(manifest.files)
        if (
            len(declared_paths) != len(manifest.files)
            or not set(HARDWARE_SKILL_PATHS).issubset(declared_paths)
            or not declared_paths.issubset(set(HARDWARE_SKILL_ALLOWED_PATHS))
        ):
            raise HardwareSkillValidationError("manifest.json 文件白名单不完整或包含未知路径。")
        expected_order = [
            path for path in HARDWARE_SKILL_ALLOWED_PATHS if path in declared_paths
        ]
        if manifest.files != expected_order:
            raise HardwareSkillValidationError("manifest.json 文件白名单顺序错误。")
        declared_mechanical = declared_paths.intersection(
            HARDWARE_SKILL_MECHANICAL_PATHS
        )
        if declared_mechanical and declared_mechanical != set(
            HARDWARE_SKILL_MECHANICAL_PATHS
        ):
            raise HardwareSkillValidationError(
                "结构能力必须同时声明 mechanical.md 和 cadquery.py。"
            )
        if len(manifest.media) > MAX_MEDIA_ASSETS:
            raise HardwareSkillValidationError("Hardware Skill 图片数量超出限制。")
        if not _REVISION_RE.fullmatch(manifest.revision):
            raise HardwareSkillValidationError("manifest.json revision 格式无效。")
        return manifest

    def _read_files(self, root: Path, manifest: _Manifest) -> dict[str, str]:
        actual_files: set[str] = set()
        total = 0
        for child in root.rglob("*"):
            if child.is_symlink():
                raise HardwareSkillValidationError("Hardware Skill 不允许符号链接。")
            if child.is_file():
                actual_files.add(child.relative_to(root).as_posix())
        expected = {
            "manifest.json",
            *manifest.files,
            *(item.path for item in manifest.media),
        }
        if actual_files != expected:
            raise HardwareSkillValidationError("Hardware Skill 文件树不符合固定白名单。")
        files: dict[str, str] = {}
        for relative in manifest.files:
            path = root / PurePosixPath(relative)
            raw = path.read_bytes()
            total += len(raw)
            if len(raw) > MAX_SKILL_FILE_BYTES:
                raise HardwareSkillValidationError(f"{relative} 超出单文件大小限制。")
            try:
                files[relative] = _normalize_text(raw.decode("utf-8"))
            except UnicodeDecodeError as exc:
                raise HardwareSkillValidationError(f"{relative} 不是有效 UTF-8。") from exc
        if total > MAX_SKILL_PACKAGE_BYTES:
            raise HardwareSkillValidationError("Hardware Skill 整包超出大小限制。")
        return files

    def _read_media_payloads(
        self,
        root: Path,
        manifest: _Manifest,
    ) -> dict[str, bytes]:
        payloads: dict[str, bytes] = {}
        total = 0
        for item in manifest.media:
            _validate_media_path(item.path)
            path = root / PurePosixPath(item.path)
            if not path.is_file() or path.is_symlink():
                raise HardwareSkillValidationError(f"硬件图片不存在：{item.path}。")
            raw = path.read_bytes()
            total += len(raw)
            if len(raw) > MAX_MEDIA_FILE_BYTES:
                raise HardwareSkillValidationError(f"{item.path} 超出单张图片大小限制。")
            payloads[item.path] = raw
        if total > MAX_MEDIA_PACKAGE_BYTES:
            raise HardwareSkillValidationError("Hardware Skill 图片总大小超出限制。")
        return payloads

    def _write_package(
        self,
        manifest: _Manifest,
        files: Mapping[str, str],
        *,
        sync_projection: bool,
        require_absent: bool = False,
        media_payloads: Mapping[str, bytes] | None = None,
    ) -> HardwareSkillDetail:
        with self._lock:
            normalized = {path: _normalize_text(content) for path, content in files.items()}
            target = self._root / manifest.skillName
            if media_payloads is None:
                resolved_media = (
                    self._read_media_payloads(target, manifest)
                    if target.exists() and manifest.media
                    else {}
                )
            else:
                resolved_media = dict(media_payloads)
            _validate_manifest_media(manifest, resolved_media)
            if set(normalized) != set(manifest.files):
                raise HardwareSkillValidationError(
                    "Hardware Skill 内容与 manifest 文件声明不一致。"
                )
            manifest.revision = _revision(normalized, manifest.media)
            specification, rules, mechanical_profile = _validate_package_content(
                manifest,
                normalized,
            )
            manifest.displayName = specification.name
            manifest.description = _parse_frontmatter(normalized["SKILL.md"])["description"]
            self._root.mkdir(parents=True, exist_ok=True)
            if require_absent and target.exists():
                raise HardwareSkillConflictError("Hardware Skill 名称已存在。")
            if target.exists() and target.is_symlink():
                raise HardwareSkillValidationError("Hardware Skill 目标目录不能是符号链接。")
            temporary = self._root / f".{manifest.skillName}.tmp-{uuid.uuid4().hex}"
            backup = self._root / f".{manifest.skillName}.bak-{uuid.uuid4().hex}"
            replaced = False
            try:
                temporary.mkdir(parents=False, exist_ok=False)
                for relative in manifest.files:
                    path = temporary / PurePosixPath(relative)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    _write_fsynced(path, normalized[relative])
                for relative, payload in resolved_media.items():
                    path = temporary / PurePosixPath(relative)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    _write_bytes_fsynced(path, payload)
                manifest_text = json.dumps(
                    manifest.model_dump(mode="json"),
                    ensure_ascii=False,
                    indent=2,
                ) + "\n"
                _write_fsynced(temporary / "manifest.json", manifest_text)
                _fsync_directory(temporary)
                if target.exists():
                    _replace_directory_with_retry(target, backup)
                try:
                    _replace_directory_with_retry(temporary, target)
                    replaced = True
                except Exception:
                    if backup.exists() and not target.exists():
                        _replace_directory_with_retry(backup, target)
                    raise
                _fsync_directory(self._root)
                if sync_projection:
                    try:
                        self._sync_projection(
                            manifest,
                            specification,
                            mechanical_profile,
                        )
                    except Exception:
                        if target.exists():
                            shutil.rmtree(target)
                        if backup.exists():
                            _replace_directory_with_retry(backup, target)
                        raise
                if backup.exists():
                    shutil.rmtree(backup)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)
                if backup.exists() and target.exists() and replaced:
                    shutil.rmtree(backup)
            return _detail(
                manifest,
                normalized,
                specification,
                rules,
                mechanical_profile,
            )

    def _sync_projection(
        self,
        manifest: _Manifest,
        specification: HardwareSkillSpecification,
        mechanical_profile: HardwareProfile | None,
    ) -> None:
        status = (
            HardwareComponentStatus.ARCHIVED.value
            if manifest.status == HardwareSkillStatus.ARCHIVED
            else HardwareComponentStatus.ACTIVE.value
        )
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            conn.execute(
                """
                INSERT INTO hardware_components (
                    id, name, category, status, electrical_json,
                    stock, price, age_recommendation, safety_tags_json,
                    notes, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name = excluded.name,
                    category = excluded.category,
                    status = excluded.status,
                    electrical_json = excluded.electrical_json,
                    stock = excluded.stock,
                    price = excluded.price,
                    age_recommendation = excluded.age_recommendation,
                    safety_tags_json = excluded.safety_tags_json,
                    notes = excluded.notes,
                    updated_at = excluded.updated_at
                """,
                (
                    specification.componentId,
                    specification.name,
                    specification.category.value,
                    status,
                    json.dumps(specification.electrical.model_dump(mode="json"), ensure_ascii=False),
                    specification.stock,
                    specification.price,
                    specification.ageRecommendation,
                    json.dumps(specification.safetyTags, ensure_ascii=False),
                    specification.notes,
                    manifest.createdAt,
                    manifest.updatedAt,
                ),
            )
            if mechanical_profile is None:
                return
            snapshot = _mechanical_snapshot(mechanical_profile)
            existing = conn.execute(
                """
                SELECT content_sha256
                FROM mechanical_profile_versions
                WHERE profile_id = ? AND revision = ?
                """,
                (snapshot.profile_id, snapshot.revision),
            ).fetchone()
            if existing is not None and str(existing["content_sha256"]) != snapshot.content_sha256:
                raise HardwareSkillValidationError(
                    "同 revision 的机械档案内容不可变。"
                )
            if existing is None:
                conn.execute(
                    """
                    INSERT INTO mechanical_profile_versions (
                      id, profile_id, revision, schema_version, display_name,
                      source, evidence_level, representation, profile_json,
                      content_sha256, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        f"mechanical_profile_{snapshot.profile_id}_{snapshot.revision}",
                        snapshot.profile_id,
                        snapshot.revision,
                        snapshot.schema_version,
                        snapshot.display_name,
                        snapshot.source.value,
                        snapshot.evidence_level,
                        snapshot.representation,
                        json.dumps(
                            snapshot.model_dump(mode="json"),
                            ensure_ascii=False,
                            sort_keys=True,
                            separators=(",", ":"),
                        ),
                        snapshot.content_sha256,
                        manifest.updatedAt,
                    ),
                )
            conn.execute(
                """
                UPDATE hardware_mechanical_links
                SET confirmed_at = NULL, updated_at = ?
                WHERE hardware_component_id = ? AND confirmed_at IS NOT NULL
                """,
                (manifest.updatedAt, specification.componentId),
            )
            if manifest.status == HardwareSkillStatus.ARCHIVED:
                return
            link_id = (
                f"mechanical_link_{specification.componentId}_{snapshot.profile_id}"
            )
            conn.execute(
                """
                INSERT INTO hardware_mechanical_links (
                  id, hardware_component_id, mechanical_profile_id,
                  mechanical_profile_revision, evidence_level, confirmed_at,
                  created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(hardware_component_id, mechanical_profile_id) DO UPDATE SET
                  mechanical_profile_revision = excluded.mechanical_profile_revision,
                  evidence_level = excluded.evidence_level,
                  confirmed_at = excluded.confirmed_at,
                  updated_at = excluded.updated_at
                """,
                (
                    link_id,
                    specification.componentId,
                    snapshot.profile_id,
                    snapshot.revision,
                    snapshot.evidence_level,
                    manifest.updatedAt,
                    manifest.createdAt,
                    manifest.updatedAt,
                ),
            )

    def _component_skill_index(self, *, ignore_invalid: bool) -> dict[str, str]:
        if not self._root.exists():
            return {}
        result: dict[str, str] = {}
        for root in sorted(self._root.iterdir(), key=lambda item: item.name):
            if not root.is_dir() or root.is_symlink() or root.name.startswith("."):
                continue
            try:
                manifest = self._read_manifest(root)
            except HardwareSkillValidationError:
                if ignore_invalid:
                    continue
                raise
            if manifest.componentId in result:
                raise HardwareSkillValidationError("同一组件存在多个 Hardware Skill。")
            result[manifest.componentId] = manifest.skillName
        return result

    def _unique_skill_name(self, base: str) -> str:
        _validate_skill_name(base)
        candidate = base
        counter = 2
        while (self._root / candidate).exists():
            suffix = f"-{counter}"
            candidate = f"{base[: 80 - len(suffix)].rstrip('-')}{suffix}"
            counter += 1
        return candidate

    def _draft_path(self, draft_id: str) -> Path:
        if not re.fullmatch(r"hwd_[a-f0-9]{32}", draft_id):
            raise HardwareSkillNotFoundError("Hardware Skill 草稿不存在。")
        return self._draft_root / f"{draft_id}.json"

    def _save_draft_state(self, state: Mapping[str, Any]) -> None:
        self._draft_root.mkdir(parents=True, exist_ok=True)
        path = self._draft_path(str(state["id"]))
        temporary = path.with_suffix(f".tmp-{uuid.uuid4().hex}")
        _write_fsynced(
            temporary,
            json.dumps(state, ensure_ascii=False, indent=2) + "\n",
        )
        os.replace(temporary, path)
        _fsync_directory(self._draft_root)

    def _load_draft_state(self, draft_id: str) -> dict[str, Any]:
        path = self._draft_path(draft_id)
        if not path.is_file() or path.is_symlink():
            raise HardwareSkillNotFoundError("Hardware Skill 草稿不存在。")
        try:
            raw = path.read_bytes()
            if len(raw) > MAX_SKILL_PACKAGE_BYTES:
                raise HardwareSkillValidationError("Hardware Skill 草稿超出大小限制。")
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HardwareSkillValidationError("Hardware Skill 草稿文件损坏。") from exc
        if not isinstance(data, dict) or data.get("id") != draft_id:
            raise HardwareSkillValidationError("Hardware Skill 草稿结构无效。")
        return data

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def default_rules(specification: HardwareSkillSpecification) -> list[HardwareSkillRule]:
    """Build deterministic declarations relevant to one component."""
    component_id = specification.componentId
    category = specification.category
    rules: list[HardwareSkillRule] = []
    if category not in {HardwareCategory.MCU, HardwareCategory.POWER, HardwareCategory.STRUCTURE}:
        rules.extend(
            [
                HardwareSkillRule(
                    id=f"voltage-{component_id}",
                    operator=HardwareRuleOperator.RANGE_OVERLAP,
                    severity="FAIL",
                    message="工作电压与主控不匹配。",
                    params={
                        "field": "electrical.voltage",
                        "leftCategories": [category.value],
                        "rightCategories": [HardwareCategory.MCU.value],
                        "tolerance": 0.5,
                        "componentId": component_id,
                    },
                ),
                HardwareSkillRule(
                    id=f"logic-level-{component_id}",
                    operator=HardwareRuleOperator.RANGE_OVERLAP,
                    severity="FAIL",
                    message="逻辑电平与主控不兼容。",
                    params={
                        "field": "electrical.logicLevel",
                        "leftCategories": [category.value],
                        "rightCategories": [HardwareCategory.MCU.value],
                        "tolerance": 0.3,
                        "componentId": component_id,
                    },
                ),
            ]
        )
    if category == HardwareCategory.POWER:
        rules.append(
            HardwareSkillRule(
                id=f"current-budget-{component_id}",
                operator=HardwareRuleOperator.SUM_LTE,
                severity="FAIL",
                message="供电电流不足，存在掉电或过热风险。",
                params={
                    "field": "electrical.peakCurrent",
                    "sumCategories": [
                        HardwareCategory.MCU.value,
                        HardwareCategory.SENSOR.value,
                        HardwareCategory.ACTUATOR.value,
                        HardwareCategory.DISPLAY.value,
                    ],
                    "limitCategories": [HardwareCategory.POWER.value],
                },
            )
        )
    if (
        specification.electrical.communicationProtocol.upper() == "I2C"
        and specification.electrical.i2cAddress
    ):
        rules.append(
            HardwareSkillRule(
                id=f"i2c-address-{component_id}",
                operator=HardwareRuleOperator.UNIQUE,
                severity="FAIL",
                message="I2C 地址被多个组件占用。",
                params={
                    "field": "electrical.i2cAddress",
                    "whenField": "electrical.communicationProtocol",
                    "whenEquals": "I2C",
                    "componentId": component_id,
                },
            )
        )
    if specification.electrical.supportedMCUs and category != HardwareCategory.MCU:
        rules.append(
            HardwareSkillRule(
                id=f"mcu-support-{component_id}",
                operator=HardwareRuleOperator.CONTAINS_ANY,
                severity="FAIL",
                message="器件未声明支持当前主控。",
                params={
                    "field": "electrical.supportedMCUs",
                    "candidateField": "identifiers",
                    "subjectCategories": [category.value],
                    "candidateCategories": [HardwareCategory.MCU.value],
                    "componentId": component_id,
                },
            )
        )
    rules.append(
        HardwareSkillRule(
            id=f"driver-required-{component_id}",
            operator=HardwareRuleOperator.REQUIRED_IF,
            severity="WARNING",
            message="器件有固件要求，但未登记驱动名称。",
            params={
                "requiredField": "electrical.driverName",
                "ifField": "electrical.firmwareRequirement",
                "ifPresent": True,
                "componentId": component_id,
            },
        )
    )
    return rules


def _default_files(
    skill_name: str,
    specification: HardwareSkillSpecification,
    rules: Sequence[HardwareSkillRule],
    description: str,
) -> dict[str, str]:
    sources = "\n".join(f"- `{item}`" for item in specification.sourceIds) or "- 用户确认的本地资料"
    return {
        "SKILL.md": _skill_markdown(skill_name, specification.name, description),
        "references/specifications.md": _specification_markdown(specification),
        "references/compatibility-rules.md": _rules_markdown(rules),
        "references/integration.md": (
            f"# {specification.name} 集成说明\n\n"
            "接线、驱动和机械集成细节应在验证后补充；不得在此文件中保存凭据或主机路径。\n"
        ),
        "references/safety.md": (
            f"# {specification.name} 安全边界\n\n"
            + ("\n".join(f"- {tag}" for tag in specification.safetyTags) or "- 暂无额外安全标签；使用前仍需核对供电与接线。")
            + "\n"
        ),
        "references/sources.md": f"# 资料来源\n\n{sources}\n",
        "examples/usage.md": (
            f"# {specification.name} 使用示例\n\n"
            "1. 先运行本地硬件组合校验。\n"
            "2. 根据验证结果确认供电、总线和驱动。\n"
        ),
        "tests/validation-cases.md": (
            "# 本地验证用例\n\n"
            f"```{_VALIDATION_FENCE}\n"
            + json.dumps(
                {
                    "schema": _VALIDATION_SCHEMA,
                    "cases": [
                        {
                            "id": "canonical-self-smoke",
                            "components": ["$self"],
                            "expectedOverall": ["PASS", "WARNING", "FAIL"],
                        }
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n```\n"
        ),
    }


def _skill_markdown(skill_name: str, display_name: str, description: str) -> str:
    safe_description = " ".join(description.strip().splitlines())
    return (
        "---\n"
        f"name: {skill_name}\n"
        f"description: {safe_description}\n"
        "---\n\n"
        f"# {display_name}\n\n"
        f"{description.strip()}\n\n"
        "## 渐进加载\n\n"
        "- [结构化参数](references/specifications.md)\n"
        "- [兼容规则](references/compatibility-rules.md)\n"
        "- [集成说明](references/integration.md)\n"
        "- [安全边界](references/safety.md)\n"
        "- [资料来源](references/sources.md)\n"
        "- [使用示例](examples/usage.md)\n"
        "- [验证用例](tests/validation-cases.md)\n\n"
        "本 Skill 只提供声明式事实和规则，不授予文件、Shell、串口或设备执行权限。\n"
    )


def _specification_markdown(specification: HardwareSkillSpecification) -> str:
    payload = json.dumps(specification.model_dump(mode="json"), ensure_ascii=False, indent=2)
    return f"# 结构化电气参数\n\n```{_SPEC_FENCE}\n{payload}\n```\n"


def _rules_markdown(rules: Sequence[HardwareSkillRule]) -> str:
    payload = {
        "schema": _RULES_SCHEMA,
        "rules": [rule.model_dump(mode="json") for rule in rules],
    }
    return (
        "# 声明式兼容规则\n\n"
        f"```{_RULES_FENCE}\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}\n"
        "```\n"
    )


def _detail(
    manifest: _Manifest,
    files: Mapping[str, str],
    specification: HardwareSkillSpecification,
    rules: Sequence[HardwareSkillRule],
    mechanical_profile: HardwareProfile | None,
) -> HardwareSkillDetail:
    return HardwareSkillDetail(
        skillName=manifest.skillName,
        componentId=manifest.componentId,
        displayName=manifest.displayName,
        description=manifest.description,
        category=specification.category,
        status=manifest.status,
        sourceKind=manifest.sourceKind,
        revision=manifest.revision,
        verificationStatus=specification.verificationStatus,
        updatedAt=manifest.updatedAt,
        diagnostics=[],
        media=[_media_asset(manifest.skillName, item) for item in manifest.media],
        files=[
            HardwareSkillFile(
                path=path,
                title=_FILE_META[path][0],
                kind=_FILE_META[path][1],
                content=files[path],
                editable=True,
            )
            for path in manifest.files
        ],
        specification=specification,
        rules=list(rules),
        mechanicalProfile=(
            mechanical_profile.model_dump(mode="json")
            if mechanical_profile is not None
            else None
        ),
    )


def _render_detail_context(
    detail: HardwareSkillDetail,
    *,
    max_chars: int,
) -> str:
    sections = [f"Hardware Skill：{detail.displayName}（{detail.skillName}）"]
    for file in detail.files:
        if file.kind not in {"entry", "reference", "model"}:
            continue
        sections.append(f"\n## {file.path}\n{file.content.strip()}")
    return "\n".join(sections)[:max_chars]


def _validate_package_content(
    manifest: _Manifest,
    files: Mapping[str, str],
) -> tuple[
    HardwareSkillSpecification,
    list[HardwareSkillRule],
    HardwareProfile | None,
]:
    if set(files) != set(manifest.files):
        raise HardwareSkillValidationError("Hardware Skill 文件路径不符合固定白名单。")
    total = 0
    for path, content in files.items():
        _validate_editable_path(path)
        encoded = content.encode("utf-8")
        total += len(encoded)
        if len(encoded) > MAX_SKILL_FILE_BYTES:
            raise HardwareSkillValidationError(f"{path} 超出单文件大小限制。")
        _validate_text_boundary(content, path)
        _validate_links(path, content)
    if total > MAX_SKILL_PACKAGE_BYTES:
        raise HardwareSkillValidationError("Hardware Skill 整包超出大小限制。")
    frontmatter = _parse_frontmatter(files["SKILL.md"])
    if frontmatter["name"] != manifest.skillName:
        raise HardwareSkillValidationError("SKILL.md frontmatter 与目录身份不一致。")
    specification_payload = _extract_fenced_json(
        files["references/specifications.md"],
        _SPEC_FENCE,
    )
    try:
        specification = HardwareSkillSpecification(**specification_payload)
    except ValidationError as exc:
        raise HardwareSkillValidationError(f"结构化参数无效：{_validation_message(exc)}") from exc
    if specification.componentId != manifest.componentId:
        raise HardwareSkillValidationError("结构化参数不能修改 componentId。")
    rules_payload = _extract_fenced_json(
        files["references/compatibility-rules.md"],
        _RULES_FENCE,
    )
    rules = _parse_rules_payload(rules_payload, specification)
    _validate_validation_cases(
        files["tests/validation-cases.md"],
        specification,
        rules,
    )
    mechanical_profile = _validate_mechanical_content(
        manifest,
        files,
    )
    return specification, rules, mechanical_profile


def _validate_validation_cases(
    content: str,
    specification: HardwareSkillSpecification,
    rules: Sequence[HardwareSkillRule],
) -> None:
    payload = _extract_fenced_json(content, _VALIDATION_FENCE)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "cases"}
        or payload.get("schema") != _VALIDATION_SCHEMA
        or not isinstance(payload.get("cases"), list)
        or not payload["cases"]
    ):
        raise HardwareSkillValidationError("validation cases 结构或 schema 无效。")
    seen: set[str] = set()
    for raw_case in payload["cases"]:
        if not isinstance(raw_case, dict) or set(raw_case) != {
            "id",
            "components",
            "expectedOverall",
        }:
            raise HardwareSkillValidationError("validation case 字段无效。")
        case_id = raw_case.get("id")
        if not isinstance(case_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", case_id):
            raise HardwareSkillValidationError("validation case id 无效。")
        if case_id in seen:
            raise HardwareSkillValidationError("validation case id 重复。")
        seen.add(case_id)
        raw_components = raw_case.get("components")
        if not isinstance(raw_components, list) or not raw_components or len(raw_components) > 20:
            raise HardwareSkillValidationError("validation case components 无效。")
        components: list[HardwareComponent] = []
        self_count = 0
        for raw_component in raw_components:
            if raw_component == "$self":
                self_count += 1
                case_specification = specification
            elif isinstance(raw_component, dict):
                try:
                    case_specification = HardwareSkillSpecification(**raw_component)
                except ValidationError as exc:
                    raise HardwareSkillValidationError(
                        f"validation case {case_id} 组件结构无效：{_validation_message(exc)}"
                    ) from exc
            else:
                raise HardwareSkillValidationError("validation case 组件必须是 $self 或结构化参数。")
            components.append(_component_from_specification(case_specification))
        if self_count != 1:
            raise HardwareSkillValidationError("validation case 必须且只能包含一个 $self。")
        raw_expected = raw_case.get("expectedOverall")
        if not isinstance(raw_expected, list) or not raw_expected:
            raise HardwareSkillValidationError("validation case expectedOverall 无效。")
        try:
            expected = {ValidationSeverity(value) for value in raw_expected}
        except (TypeError, ValueError) as exc:
            raise HardwareSkillValidationError("validation case 包含未知预期状态。") from exc
        actual = validate_components(components, rules=list(rules)).overall
        if actual not in expected:
            raise HardwareSkillValidationError(
                f"validation case {case_id} 失败：实际为 {actual.value}。"
            )


def _validate_mechanical_content(
    manifest: _Manifest,
    files: Mapping[str, str],
) -> HardwareProfile | None:
    declared = set(files).intersection(HARDWARE_SKILL_MECHANICAL_PATHS)
    if not declared:
        return None
    if declared != set(HARDWARE_SKILL_MECHANICAL_PATHS):
        raise HardwareSkillValidationError(
            "结构能力必须同时包含 mechanical.md 和 cadquery.py。"
        )
    payload = _extract_fenced_json(
        files["references/mechanical.md"],
        _MECHANICAL_FENCE,
    )
    try:
        declaration = _MechanicalDeclaration(**payload)
    except ValidationError as exc:
        raise HardwareSkillValidationError(
            f"机械档案声明无效：{_validation_message(exc)}"
        ) from exc
    if declaration.schema_ != _MECHANICAL_SCHEMA:
        raise HardwareSkillValidationError("机械档案 schema 版本不受支持。")
    if declaration.model.path != "models/cadquery.py":
        raise HardwareSkillValidationError("机械档案模型路径必须是 models/cadquery.py。")
    if declaration.model.executionPolicy != "REFERENCE_ONLY":
        raise HardwareSkillValidationError(
            "CadQuery 模型只能声明 REFERENCE_ONLY 执行策略。"
        )
    if declaration.model.verificationStatus not in {
        "USER_CONFIRMED",
        "VERIFIED_REFERENCE",
        "OFFICIAL_DOC_VERIFIED",
    }:
        raise HardwareSkillValidationError("CadQuery 模型验证状态无效。")
    model_source = _normalize_text(files[declaration.model.path])
    model_digest = hashlib.sha256(model_source.encode("utf-8")).hexdigest()
    if model_digest != declaration.model.sha256:
        raise HardwareSkillValidationError("CadQuery 参考模型 SHA-256 不匹配。")
    try:
        ast.parse(model_source, filename=declaration.model.path, mode="exec")
    except SyntaxError as exc:
        raise HardwareSkillValidationError(
            f"CadQuery 参考模型不是有效 Python：第 {exc.lineno or 0} 行。"
        ) from exc

    raw_profile = dict(declaration.profile)
    if "revision" in raw_profile or "source" in raw_profile:
        raise HardwareSkillValidationError(
            "机械档案 revision 和 source 由 Hardware Skill 管理。"
        )
    raw_profile["revision"] = f"skill-{manifest.revision}"
    raw_model_kind = raw_profile.get("model_kind", HardwareModelKind.ENVELOPE.value)
    if manifest.componentId == "hw_seed_unihiker_k10":
        if (
            raw_profile.get("profile_id") != "unihiker_k10"
            or raw_model_kind != HardwareModelKind.UNIHIKER_K10.value
        ):
            raise HardwareSkillValidationError("K10 Skill 必须使用受信 unihiker_k10 模型身份。")
        raw_profile["source"] = ProfileSource.TRUSTED.value
    else:
        if raw_model_kind != HardwareModelKind.ENVELOPE.value:
            raise HardwareSkillValidationError(
                "用户 Hardware Skill 只能声明 envelope 机械模型。"
            )
        raw_profile["source"] = ProfileSource.DECLARED.value
    try:
        return HardwareProfile.model_validate(raw_profile)
    except ValidationError as exc:
        raise HardwareSkillValidationError(
            f"结构化机械档案无效：{_validation_message(exc)}"
        ) from exc


def _mechanical_snapshot(profile: HardwareProfile) -> MechanicalProfileSnapshot:
    payload = {
        "schema_version": "1.0",
        **profile.model_dump(mode="json"),
        "evidence_level": (
            "TRUSTED"
            if profile.source is ProfileSource.TRUSTED
            else "CONFIRMED"
        ),
        "representation": (
            "parametric_envelope"
            if profile.model_kind is not HardwareModelKind.ENVELOPE
            else "envelope_only"
        ),
    }
    payload = normalize_profile_snapshot_payload(payload)
    payload["content_sha256"] = hashlib.sha256(
        json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    return MechanicalProfileSnapshot.model_validate(payload)


def _parse_rules_payload(
    payload: Any,
    specification: HardwareSkillSpecification,
) -> list[HardwareSkillRule]:
    if isinstance(payload, dict):
        if set(payload) != {"schema", "rules"} or payload.get("schema") != _RULES_SCHEMA:
            raise HardwareSkillValidationError("兼容规则 JSON schema 或字段无效。")
        raw_rules = payload.get("rules")
    else:
        raw_rules = payload
    if not isinstance(raw_rules, list):
        raise HardwareSkillValidationError("兼容规则必须是 JSON 数组。")
    rules: list[HardwareSkillRule] = []
    seen: set[str] = set()
    for raw in raw_rules:
        try:
            rule = HardwareSkillRule(**raw)
        except (TypeError, ValidationError) as exc:
            message = _validation_message(exc)
            if "operator" in message:
                message = f"兼容规则算子无效：{message}"
            raise HardwareSkillValidationError(message) from exc
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", rule.id):
            raise HardwareSkillValidationError("兼容规则 id 必须是安全标识符。")
        if rule.id in seen:
            raise HardwareSkillValidationError(f"兼容规则 id 重复：{rule.id}")
        seen.add(rule.id)
        _validate_rule_params(rule, specification)
        rules.append(rule)
    _validate_rule_coverage(rules, specification)
    return rules


def _validate_rule_coverage(
    rules: Sequence[HardwareSkillRule],
    specification: HardwareSkillSpecification,
) -> None:
    component_rules = [
        rule
        for rule in rules
        if rule.params.get("componentId") in {None, specification.componentId}
    ]
    if not any(rule.operator == HardwareRuleOperator.REQUIRED_IF for rule in component_rules):
        raise HardwareSkillValidationError("兼容规则缺少 required-if 条件必填校验。")
    category = specification.category
    if category not in {HardwareCategory.MCU, HardwareCategory.POWER, HardwareCategory.STRUCTURE}:
        range_fields = {
            str(rule.params.get("field"))
            for rule in component_rules
            if rule.operator == HardwareRuleOperator.RANGE_OVERLAP
        }
        required_ranges = {"electrical.voltage", "electrical.logicLevel"}
        if not required_ranges.issubset(range_fields):
            raise HardwareSkillValidationError("兼容规则缺少工作电压或逻辑电平范围校验。")
    if category == HardwareCategory.POWER and not any(
        rule.operator == HardwareRuleOperator.SUM_LTE for rule in component_rules
    ):
        raise HardwareSkillValidationError("供电 Hardware Skill 缺少 sum-lte 电流预算校验。")
    if (
        specification.electrical.communicationProtocol.upper() == "I2C"
        and specification.electrical.i2cAddress
        and not any(rule.operator == HardwareRuleOperator.UNIQUE for rule in component_rules)
    ):
        raise HardwareSkillValidationError("I2C Hardware Skill 缺少 unique 地址校验。")
    if specification.electrical.supportedMCUs and category != HardwareCategory.MCU and not any(
        rule.operator == HardwareRuleOperator.CONTAINS_ANY for rule in component_rules
    ):
        raise HardwareSkillValidationError("Hardware Skill 缺少 contains-any 主控兼容校验。")


def _validate_rule_params(
    rule: HardwareSkillRule,
    specification: HardwareSkillSpecification,
) -> None:
    if _contains_dynamic_expression(rule.params):
        raise HardwareSkillValidationError(
            f"兼容规则 {rule.id} 包含非法字段、动态表达式或路径，已拒绝。"
        )
    allowed = _PARAM_KEYS[rule.operator]
    unknown = set(rule.params) - allowed
    if unknown:
        raise HardwareSkillValidationError(
            f"兼容规则 {rule.id} 包含未允许参数：{', '.join(sorted(unknown))}。"
        )
    field_keys = ("field", "whenField", "candidateField", "requiredField", "ifField")
    for key in field_keys:
        value = rule.params.get(key)
        if value is not None and value not in _FIELD_ALLOWLIST:
            raise HardwareSkillValidationError(
                f"兼容规则 {rule.id} 的字段 {value!r} 不在白名单。"
            )
    component_id = rule.params.get("componentId")
    if component_id is not None and component_id != specification.componentId:
        raise HardwareSkillValidationError("兼容规则不能引用其他 componentId。")
    for key in ("leftCategories", "rightCategories", "sumCategories", "limitCategories", "subjectCategories", "candidateCategories"):
        values = rule.params.get(key)
        if values is None:
            continue
        if not isinstance(values, list) or not values:
            raise HardwareSkillValidationError(f"兼容规则 {rule.id} 的 {key} 必须是非空数组。")
        try:
            for value in values:
                HardwareCategory(value)
        except (TypeError, ValueError) as exc:
            raise HardwareSkillValidationError(f"兼容规则 {rule.id} 包含未知硬件类别。") from exc
    if rule.operator == HardwareRuleOperator.RANGE_OVERLAP:
        if rule.params.get("field") not in {"electrical.voltage", "electrical.logicLevel"}:
            raise HardwareSkillValidationError("range-overlap 只允许电压或逻辑电平字段。")
        tolerance = rule.params.get("tolerance", 0)
        if not isinstance(tolerance, (int, float)) or isinstance(tolerance, bool) or tolerance < 0:
            raise HardwareSkillValidationError("range-overlap tolerance 必须是非负数。")
    elif rule.operator == HardwareRuleOperator.SUM_LTE:
        if rule.params.get("field") != "electrical.peakCurrent":
            raise HardwareSkillValidationError("sum-lte 只允许峰值电流字段。")
    elif rule.operator == HardwareRuleOperator.UNIQUE:
        if rule.params.get("field") != "electrical.i2cAddress":
            raise HardwareSkillValidationError("unique 只允许 I2C 地址字段。")
    elif rule.operator == HardwareRuleOperator.CONTAINS_ANY:
        if rule.params.get("field") != "electrical.supportedMCUs" or rule.params.get("candidateField") != "identifiers":
            raise HardwareSkillValidationError("contains-any 字段组合无效。")
    elif rule.operator == HardwareRuleOperator.REQUIRED_IF:
        if rule.params.get("requiredField") != "electrical.driverName" or rule.params.get("ifField") != "electrical.firmwareRequirement":
            raise HardwareSkillValidationError("required-if 字段组合无效。")


def _contains_dynamic_expression(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            _contains_dynamic_expression(key) or _contains_dynamic_expression(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_dynamic_expression(item) for item in value)
    if not isinstance(value, str):
        return False
    return bool(
        re.search(
            r"(?i)(?:__\w+__|\$\{|\$\(|\b(?:eval|exec|lambda|import)\b|\.\./|\.\.\\)",
            value,
        )
    )


def _extract_fenced_json(content: str, label: str) -> Any:
    marker_count = len(re.findall(rf"```{re.escape(label)}(?:[ \t]*\r?\n|\s*$)", content))
    pattern = re.compile(
        rf"```{re.escape(label)}[ \t]*\r?\n(.*?)\r?\n```",
        re.DOTALL,
    )
    matches = pattern.findall(content)
    if marker_count != 1 or len(matches) != 1:
        raise HardwareSkillValidationError(f"{label} 结构块必须且只能出现一次。")
    try:
        return json.loads(matches[0])
    except json.JSONDecodeError as exc:
        raise HardwareSkillValidationError(f"{label} 结构块不是有效 JSON。") from exc


def _parse_frontmatter(content: str) -> dict[str, str]:
    if not content.startswith("---\n"):
        raise HardwareSkillValidationError("SKILL.md 缺少 YAML frontmatter。")
    end = content.find("\n---\n", 4)
    if end < 0:
        raise HardwareSkillValidationError("SKILL.md frontmatter 未正确结束。")
    values: dict[str, str] = {}
    for line in content[4:end].splitlines():
        if not line.strip():
            continue
        if ":" not in line:
            raise HardwareSkillValidationError("SKILL.md frontmatter 行格式无效。")
        key, value = line.split(":", 1)
        key = key.strip()
        if key not in {"name", "description"} or key in values:
            raise HardwareSkillValidationError("SKILL.md frontmatter 只允许 name 和 description。")
        values[key] = value.strip().strip("\"'")
    if set(values) != {"name", "description"} or not values["description"]:
        raise HardwareSkillValidationError("SKILL.md frontmatter 必须包含 name 和 description。")
    _validate_skill_name(values["name"])
    return values


def _replace_skill_frontmatter_name(content: str, skill_name: str) -> str:
    _validate_skill_name(skill_name)
    _parse_frontmatter(content)
    end = content.find("\n---\n", 4)
    frontmatter = content[:end]
    updated, count = re.subn(
        r"(?m)^name:\s*.*$",
        f"name: {skill_name}",
        frontmatter,
        count=1,
    )
    if count != 1:
        raise HardwareSkillValidationError("SKILL.md frontmatter 缺少 name。")
    return updated + content[end:]


def _sanitize_imported_rules(
    content: str,
    specification: HardwareSkillSpecification,
) -> str:
    payload = _extract_fenced_json(content, _RULES_FENCE)
    if (
        not isinstance(payload, dict)
        or set(payload) != {"schema", "rules"}
        or payload.get("schema") != _RULES_SCHEMA
        or not isinstance(payload.get("rules"), list)
    ):
        raise HardwareSkillValidationError("兼容规则 JSON schema 或字段无效。")
    kept: list[dict[str, Any]] = []
    downgraded: list[tuple[str, str]] = []
    seen: set[str] = set()
    for raw in payload["rules"]:
        try:
            rule = HardwareSkillRule(**raw)
            if (
                not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,99}", rule.id)
                or rule.id in seen
            ):
                raise HardwareSkillValidationError("兼容规则 id 无效或重复。")
            _validate_rule_params(rule, specification)
        except (TypeError, ValidationError, HardwareSkillValidationError):
            rule_id = str(raw.get("id", "未命名规则")) if isinstance(raw, dict) else "未命名规则"
            message = str(raw.get("message", "需要人工复核")) if isinstance(raw, dict) else "需要人工复核"
            downgraded.append((rule_id, message))
            continue
        seen.add(rule.id)
        kept.append(rule.model_dump(mode="json"))
    sanitized = {"schema": _RULES_SCHEMA, "rules": kept}
    _parse_rules_payload(sanitized, specification)
    pattern = re.compile(
        rf"```{re.escape(_RULES_FENCE)}[ \t]*\r?\n(.*?)\r?\n```",
        re.DOTALL,
    )
    replacement = (
        f"```{_RULES_FENCE}\n"
        f"{json.dumps(sanitized, ensure_ascii=False, indent=2)}\n```"
    )
    updated, count = pattern.subn(replacement, content, count=1)
    if count != 1:
        raise HardwareSkillValidationError("兼容规则结构块未找到。")
    if downgraded:
        items = "；".join(f"`{rule_id}`：{message}" for rule_id, message in downgraded)
        updated += (
            "\n\n> 迁移说明：以下扩展规则超出当前声明式规则引擎白名单，"
            f"已降级为人工检查项，未静默执行：{items}。\n"
        )
    return updated


def _is_later_timestamp(candidate: str, current: str) -> bool:
    try:
        candidate_time = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        current_time = datetime.fromisoformat(current.replace("Z", "+00:00"))
    except ValueError:
        return False
    if candidate_time.tzinfo is None:
        candidate_time = candidate_time.replace(tzinfo=UTC)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=UTC)
    return candidate_time.astimezone(UTC) > current_time.astimezone(UTC)


def _validate_links(source_path: str, content: str) -> None:
    for match in _LINK_RE.finditer(content):
        target = match.group(1).strip().split(maxsplit=1)[0].strip("<>\"'")
        if not target or target.startswith("#") or target.startswith(("https://", "http://", "mailto:")):
            continue
        if target.startswith(("/", "\\", "file:")) or re.match(r"^[A-Za-z]:", target):
            raise HardwareSkillValidationError(f"{source_path} 包含绝对路径链接。")
        path_part = target.split("#", 1)[0].split("?", 1)[0]
        base = PurePosixPath(source_path).parent
        combined = base / PurePosixPath(path_part)
        parts: list[str] = []
        for part in combined.parts:
            if part in {"", "."}:
                continue
            if part == "..":
                if not parts:
                    raise HardwareSkillValidationError(f"{source_path} 的相对链接越出 Skill。")
                parts.pop()
            else:
                parts.append(part)
        resolved = "/".join(parts)
        if resolved not in HARDWARE_SKILL_ALLOWED_PATHS:
            raise HardwareSkillValidationError(f"{source_path} 链接到白名单外文件。")


def _validate_editable_path(path: str) -> None:
    if path not in HARDWARE_SKILL_ALLOWED_PATHS:
        raise HardwareSkillValidationError("Hardware Skill 文件路径不在白名单。")
    if "\\" in path or PurePosixPath(path).is_absolute() or ".." in PurePosixPath(path).parts:
        raise HardwareSkillValidationError("Hardware Skill 文件路径无效。")


def _validate_skill_name(skill_name: str) -> None:
    if not _SLUG_RE.fullmatch(skill_name):
        raise HardwareSkillValidationError("Hardware Skill 名称必须是安全的小写 slug。")


def _validate_text_boundary(content: str, label: str) -> None:
    if "\x00" in content:
        raise HardwareSkillValidationError(f"{label} 包含 NUL 字符。")
    if _WINDOWS_ABSOLUTE_RE.search(content) or re.search(r"(?m)(?:^|\s)/(?:Users|home|root|etc)/\S+", content):
        raise HardwareSkillValidationError(f"{label} 包含主机绝对路径。")
    if _SERIAL_RE.search(content):
        raise HardwareSkillValidationError(f"{label} 包含真实串口标识。")
    if any(pattern.search(content) for pattern in _SECRET_RES):
        raise HardwareSkillValidationError(f"{label} 包含疑似敏感凭据，拒绝保存。")


def _extract_source(
    source: HardwareSkillDraftSource,
) -> tuple[dict[str, Any], list[dict[str, Any]] | None, list[dict[str, str]], int]:
    if (
        Path(source.name).name != source.name
        or "/" in source.name
        or "\\" in source.name
        or ".." in source.name
        or any(character in source.name for character in '<>:"|?*\x00\r\n')
    ):
        raise HardwareSkillValidationError("上传资料名称不能包含路径。")
    media_type = _media_type(source.mediaType)
    allowed = {"text/markdown", "text/plain", "application/json", "text/csv", "application/pdf"}
    if media_type not in allowed:
        raise HardwareSkillValidationError("上传资料类型不在白名单。")
    suffix = Path(source.name).suffix.casefold()
    suffixes = {
        "text/markdown": {".md", ".markdown"},
        "text/plain": {".txt"},
        "application/json": {".json"},
        "text/csv": {".csv"},
        "application/pdf": {".pdf"},
    }
    if suffix and suffix not in suffixes[media_type]:
        raise HardwareSkillValidationError("上传资料扩展名与媒体类型不匹配。")
    if media_type == "application/pdf":
        try:
            raw = base64.b64decode(source.content, validate=True)
        except (ValueError, binascii.Error) as exc:
            raise HardwareSkillValidationError("PDF 内容必须使用有效 base64。") from exc
        if len(raw) > MAX_PDF_BYTES:
            raise HardwareSkillValidationError("PDF 超出大小限制。")
        try:
            from pypdf import PdfReader  # type: ignore[import-not-found]
        except ImportError:
            return {}, None, [{
                "path": source.name,
                "code": "PDF_EXTRACTION_UNAVAILABLE",
                "message": "当前 Sidecar 未安装本地 PDF 文本提取依赖，请改用 UTF-8 Markdown、TXT、JSON 或 CSV。",
                "severity": "error",
            }], len(raw)
        try:
            reader = PdfReader(io.BytesIO(raw))
            if len(reader.pages) > MAX_PDF_PAGES:
                raise HardwareSkillValidationError("PDF 页数超出允许范围。")
            text = "\n".join((page.extract_text() or "") for page in reader.pages)
            text = text[:MAX_PDF_TEXT_CHARS]
            _validate_text_boundary(text, source.name)
            extracted, rules = _extract_structured_text(text)
            diagnostics: list[dict[str, str]] = []
            if not text.strip():
                diagnostics.append({
                    "path": source.name,
                    "code": "PDF_TEXT_EMPTY",
                    "message": "PDF 未提取到可用文本；扫描件需要先转换为文本。",
                    "severity": "error",
                })
            return extracted, rules, diagnostics, len(raw)
        except HardwareSkillValidationError:
            raise
        except Exception:
            return {}, None, [{
                "path": source.name,
                "code": "PDF_PARSE_FAILED",
                "message": "PDF 无法由本地只读解析器安全提取。",
                "severity": "error",
            }], len(raw)

    raw = source.content.encode("utf-8")
    if len(raw) > MAX_SOURCE_BYTES:
        raise HardwareSkillValidationError("单个上传资料超出大小限制。")
    _validate_text_boundary(source.content, source.name)
    extracted_text = source.content
    if media_type == "text/csv":
        try:
            rows = list(csv.reader(io.StringIO(source.content)))
        except csv.Error as exc:
            raise HardwareSkillValidationError("CSV 结构无效。") from exc
        if len(rows) > 2_000 or any(len(row) > 100 for row in rows):
            raise HardwareSkillValidationError("CSV 行列数量超出允许范围。")
        key_values = [
            f"{row[0]}: {row[1]}"
            for row in rows
            if len(row) >= 2 and row[0].strip() and row[1].strip()
        ]
        if key_values:
            extracted_text = "\n".join(key_values)
    extracted, rules = _extract_structured_text(extracted_text)
    return extracted, rules, [], len(raw)


def _extract_structured_text(text: str) -> tuple[dict[str, Any], list[dict[str, Any]] | None]:
    text = text.lstrip("\ufeff")
    stripped = text.strip()
    payload: Any = None
    rules: list[dict[str, Any]] | None = None
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        try:
            payload = _extract_fenced_json(text, _SPEC_FENCE)
        except HardwareSkillValidationError:
            payload = None
        try:
            raw_rules = _extract_fenced_json(text, _RULES_FENCE)
            if isinstance(raw_rules, dict):
                rules_value = raw_rules.get("rules")
            else:
                rules_value = raw_rules
            if isinstance(rules_value, list):
                rules = rules_value
        except HardwareSkillValidationError:
            pass
    if not isinstance(payload, dict):
        return _extract_natural_fields(text), rules
    if "rules" in payload and isinstance(payload["rules"], list):
        rules = payload["rules"]
    if "specification" in payload and isinstance(payload["specification"], dict):
        payload = payload["specification"]
    allowed = {
        "schema",
        "componentId",
        "name",
        "category",
        "electrical",
        "stock",
        "price",
        "ageRecommendation",
        "safetyTags",
        "notes",
        "verificationStatus",
        "sourceIds",
    }
    return {key: value for key, value in payload.items() if key in allowed}, rules


def _extract_natural_fields(text: str) -> dict[str, Any]:
    """Conservatively extract common datasheet facts without invoking an LLM."""
    normalized = text.strip()
    if not normalized:
        return {}
    result: dict[str, Any] = {}
    name_match = re.search(
        r"(?im)(?:器件|硬件|产品)?名称\s*[:：=为]\s*([^\n,，;；]{1,100})",
        normalized,
    )
    if name_match:
        result["name"] = name_match.group(1).strip()

    category_hints: tuple[tuple[HardwareCategory, tuple[str, ...]], ...] = (
        (HardwareCategory.MCU, ("主控", "开发板", " mcu", "微控制器")),
        (HardwareCategory.SENSOR, ("传感器", "sensor")),
        (HardwareCategory.ACTUATOR, ("执行器", "舵机", "继电器", "电机", "actuator", "servo")),
        (HardwareCategory.DISPLAY, ("显示屏", "屏幕", "oled", "display")),
        (HardwareCategory.POWER, ("供电模块", "电源模块", "power supply")),
        (HardwareCategory.STRUCTURE, ("结构件", "支架", "外壳", "structure")),
    )
    lowered = f" {normalized.casefold()}"
    for category, hints in category_hints:
        if any(hint in lowered for hint in hints):
            result["category"] = category.value
            break

    electrical: dict[str, Any] = {}
    voltage = _natural_number(
        normalized,
        r"(?:额定|工作|供电)?电压(?:范围)?\s*[:：=为]?\s*(\d+(?:\.\d+)?)\s*(?:v|伏)\b",
    )
    logic = _natural_number(
        normalized,
        r"逻辑电平\s*[:：=为]?\s*(\d+(?:\.\d+)?)\s*(?:v|伏)\b",
    )
    current_match = re.search(
        r"(?i)(?:峰值|最大|额定)?电流\s*[:：=为]?\s*(\d+(?:\.\d+)?)\s*(ma|a|毫安|安)\b",
        normalized,
    )
    if voltage is not None:
        electrical["voltage"] = voltage
    if logic is not None:
        electrical["logicLevel"] = logic
    if current_match:
        current = float(current_match.group(1))
        if current_match.group(2).casefold() in {"ma", "毫安"}:
            current /= 1_000
        electrical["peakCurrent"] = current

    protocol_match = re.search(r"(?i)\b(I2C|SPI|UART|PWM|ADC|GPIO|POWER)\b", normalized)
    if protocol_match:
        electrical["communicationProtocol"] = protocol_match.group(1).upper()
    address_match = re.search(
        r"(?i)I2C\s*(?:地址|address)?\s*[:：=为]?\s*(0x[0-9a-f]{1,2})\b",
        normalized,
    )
    if address_match:
        electrical["i2cAddress"] = address_match.group(1).lower()
        electrical.setdefault("communicationProtocol", "I2C")
    supported = sorted(
        {
            match.group(0).casefold()
            for match in re.finditer(
                r"(?i)\b(?:esp32(?:-s[23])?|rp2040|raspberry\s*pi\s*pico|unihiker(?:-k10)?|k10|micro:bit)\b",
                normalized,
            )
        }
    )
    if supported:
        electrical["supportedMCUs"] = supported
    driver_match = re.search(
        r"(?im)驱动(?:名称|库)?\s*[:：=为]\s*([^\n,，;；]{1,100})",
        normalized,
    )
    if driver_match:
        electrical["driverName"] = driver_match.group(1).strip()
    firmware_match = re.search(
        r"(?im)固件(?:要求|版本)?\s*[:：=为]\s*([^\n,，;；]{1,200})",
        normalized,
    )
    if firmware_match:
        electrical["firmwareRequirement"] = firmware_match.group(1).strip()
    if electrical:
        result["electrical"] = electrical

    integer_fields = {
        "stock": r"库存\s*[:：=为]?\s*(\d+)",
        "ageRecommendation": r"(?:适龄|建议年龄)\s*[:：=为]?\s*(\d+)",
    }
    for field, pattern in integer_fields.items():
        match = re.search(pattern, normalized)
        if match:
            result[field] = int(match.group(1))
    price_match = re.search(r"(?:参考)?(?:单价|价格)\s*[:：=为]?\s*[¥￥]?\s*(\d+(?:\.\d+)?)", normalized)
    if price_match:
        result["price"] = float(price_match.group(1))
    return result


def _natural_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _merge_partial(target: dict[str, Any], incoming: Mapping[str, Any]) -> None:
    for key, value in incoming.items():
        if key in {"schema", "componentId"} and key in target:
            continue
        if key == "electrical" and isinstance(value, dict):
            existing = target.setdefault("electrical", {})
            if isinstance(existing, dict):
                existing.update(value)
            continue
        target[key] = value


def _missing_questions(partial: Mapping[str, Any]) -> list[str]:
    questions: list[str] = []
    if not str(partial.get("name") or "").strip():
        questions.append("这个硬件器件的名称是什么？")
    if partial.get("category") not in {item.value for item in HardwareCategory}:
        questions.append("它属于 MCU、SENSOR、ACTUATOR、DISPLAY、POWER 还是 STRUCTURE？")
    electrical = partial.get("electrical")
    if not isinstance(electrical, dict):
        electrical = {}
    labels = {
        "voltage": "额定工作电压是多少伏？",
        "logicLevel": "逻辑电平是多少伏？",
        "peakCurrent": "峰值电流是多少安？",
    }
    for key, question in labels.items():
        if key not in electrical:
            questions.append(question)
    return questions


def _complete_spec(partial: Mapping[str, Any]) -> dict[str, Any]:
    result = dict(partial)
    electrical = dict(result.get("electrical") or {})
    electrical.setdefault("communicationProtocol", "GPIO")
    electrical.setdefault("i2cAddress", None)
    electrical.setdefault("supportedMCUs", [])
    electrical.setdefault("driverName", None)
    electrical.setdefault("firmwareRequirement", None)
    result["electrical"] = electrical
    result.setdefault("schema", "zhangwen.hardware-skill/v1")
    result.setdefault("stock", 0)
    result.setdefault("price", 0.0)
    result.setdefault("ageRecommendation", None)
    result.setdefault("safetyTags", [])
    result.setdefault("notes", "")
    result.setdefault("verificationStatus", "USER_CONFIRMED")
    result.setdefault("sourceIds", [])
    return result


def _draft_files(
    draft_id: str,
    partial: Mapping[str, Any],
    specification: HardwareSkillSpecification | None,
    rules: Sequence[HardwareSkillRule],
) -> list[HardwareSkillFile]:
    display_name = str(partial.get("name") or "待补充硬件")
    skill_name = _slug_for(display_name, draft_id)
    if specification is not None:
        contents = _default_files(
            skill_name,
            specification,
            rules,
            specification.notes or f"{display_name} 的 Hardware Skill 草稿。",
        )
    else:
        placeholder = json.dumps(partial, ensure_ascii=False, indent=2)
        contents = {
            "SKILL.md": _skill_markdown(skill_name, display_name, f"{display_name} 的 Hardware Skill 草稿。"),
            "references/specifications.md": f"# 结构化电气参数（待补充）\n\n```{_SPEC_FENCE}\n{placeholder}\n```\n",
            "references/compatibility-rules.md": _rules_markdown([]),
            "references/integration.md": "# 集成说明\n\n待补充。\n",
            "references/safety.md": "# 安全边界\n\n待补充。\n",
            "references/sources.md": "# 资料来源\n\n草稿资料仅由 Sidecar 有界读取。\n",
            "examples/usage.md": "# 使用示例\n\n待补充。\n",
            "tests/validation-cases.md": "# 本地验证用例\n\n待补充。\n",
        }
    return [
        HardwareSkillFile(
            path=path,
            title=_FILE_META[path][0],
            kind=_FILE_META[path][1],
            content=contents[path],
            editable=True,
        )
        for path in HARDWARE_SKILL_PATHS
    ]


def _component_from_row(row: sqlite3.Row) -> HardwareComponent:
    return HardwareComponent(
        id=str(row["id"]),
        name=str(row["name"]),
        category=HardwareCategory(str(row["category"])),
        status=HardwareComponentStatus(str(row["status"])),
        electrical=ElectricalProps(**json.loads(row["electrical_json"])),
        stock=int(row["stock"]),
        price=float(row["price"]),
        ageRecommendation=row["age_recommendation"],
        safetyTags=json.loads(row["safety_tags_json"] or "[]"),
        notes=str(row["notes"] or ""),
        createdAt=str(row["created_at"]),
        updatedAt=str(row["updated_at"]),
        verificationStatus="MIGRATED_UNVERIFIED",
    )


def _component_from_specification(
    specification: HardwareSkillSpecification,
) -> HardwareComponent:
    now = _now()
    return HardwareComponent(
        id=specification.componentId,
        name=specification.name,
        category=specification.category,
        status=HardwareComponentStatus.ACTIVE,
        electrical=specification.electrical,
        stock=specification.stock,
        price=specification.price,
        ageRecommendation=specification.ageRecommendation,
        safetyTags=list(specification.safetyTags),
        notes=specification.notes,
        createdAt=now,
        updatedAt=now,
        verificationStatus=specification.verificationStatus,
    )


def _media_type(value: str) -> str:
    normalized = value.split(";", 1)[0].strip().lower()
    return {
        "text/x-markdown": "text/markdown",
        "application/x-markdown": "text/markdown",
        "application/vnd.ms-excel": "text/csv",
        "application/csv": "text/csv",
        "application/x-pdf": "application/pdf",
    }.get(normalized, normalized)


def _slug_for(name: str, fallback: str) -> str:
    normalized = name.casefold()
    normalized = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    if not normalized:
        tail = re.sub(r"[^a-z0-9]+", "-", fallback.casefold()).strip("-")[-20:]
        normalized = f"hardware-{tail or uuid.uuid4().hex[:8]}"
    normalized = normalized[:80].strip("-")
    if not _SLUG_RE.fullmatch(normalized):
        normalized = f"hardware-{uuid.uuid4().hex[:12]}"
    return normalized


def _validate_media_path(path: str) -> None:
    pure = PurePosixPath(path)
    if (
        not _MEDIA_PATH_RE.fullmatch(path)
        or pure.is_absolute()
        or "\\" in path
        or ".." in pure.parts
        or len(pure.parts) != 2
    ):
        raise HardwareSkillValidationError("Hardware Skill 图片路径无效。")


def _validate_manifest_media(
    manifest: _Manifest,
    payloads: Mapping[str, bytes],
) -> None:
    if len(manifest.media) > MAX_MEDIA_ASSETS:
        raise HardwareSkillValidationError("Hardware Skill 图片数量超出限制。")
    paths = [item.path for item in manifest.media]
    if len(paths) != len(set(paths)):
        raise HardwareSkillValidationError("Hardware Skill 图片路径不能重复。")
    if set(paths) != set(payloads):
        raise HardwareSkillValidationError("manifest 图片清单与实际图片不一致。")
    if sum(item.role == "cover" for item in manifest.media) > 1:
        raise HardwareSkillValidationError("Hardware Skill 最多只能有一张封面图。")

    total = 0
    for item in manifest.media:
        _validate_media_path(item.path)
        try:
            HardwareMediaAsset(**item.model_dump(), url="")
        except ValidationError as exc:
            raise HardwareSkillValidationError(
                f"{item.path} 的图片元数据无效：{_validation_message(exc)}"
            ) from exc
        if not item.sourceUrl.startswith("https://"):
            raise HardwareSkillValidationError(f"{item.path} 的来源地址必须使用 HTTPS。")
        for label, value in (
            (f"{item.path} alt", item.alt),
            (f"{item.path} attribution", item.attribution),
            (f"{item.path} license", item.license),
        ):
            _validate_text_boundary(value, label)

        payload = payloads[item.path]
        total += len(payload)
        if not payload or len(payload) > MAX_MEDIA_FILE_BYTES:
            raise HardwareSkillValidationError(f"{item.path} 超出单张图片大小限制。")
        digest = hashlib.sha256(payload).hexdigest()
        if digest != item.sha256:
            raise HardwareSkillValidationError(f"{item.path} 的 SHA-256 校验失败。")
        detected = _detect_image_content_type(payload)
        if detected != item.contentType:
            raise HardwareSkillValidationError(f"{item.path} 的实际格式与 contentType 不一致。")
        expected_suffixes = {
            "image/jpeg": {".jpg", ".jpeg"},
            "image/png": {".png"},
            "image/webp": {".webp"},
        }[item.contentType]
        if PurePosixPath(item.path).suffix.casefold() not in expected_suffixes:
            raise HardwareSkillValidationError(f"{item.path} 的扩展名与图片格式不一致。")
    if total > MAX_MEDIA_PACKAGE_BYTES:
        raise HardwareSkillValidationError("Hardware Skill 图片总大小超出限制。")


def _detect_image_content_type(payload: bytes) -> str:
    if payload.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if payload.startswith(b"\xff\xd8") and payload.endswith(b"\xff\xd9"):
        return "image/jpeg"
    if (
        len(payload) >= 12
        and payload.startswith(b"RIFF")
        and payload[8:12] == b"WEBP"
    ):
        return "image/webp"
    raise HardwareSkillValidationError("Hardware Skill 图片不是受支持的 JPEG、PNG 或 WebP。")


def _media_asset(skill_name: str, item: _ManifestMedia) -> HardwareMediaAsset:
    asset_name = PurePosixPath(item.path).name
    return HardwareMediaAsset(
        **item.model_dump(),
        url=f"/api/hardware/skills/{skill_name}/media/{asset_name}",
    )


def _revision(
    files: Mapping[str, str],
    media: Sequence[_ManifestMedia] = (),
) -> str:
    digest = hashlib.sha256()
    for path in HARDWARE_SKILL_ALLOWED_PATHS:
        if path not in files:
            continue
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_normalize_text(files[path]).encode("utf-8"))
        digest.update(b"\0")
    for item in sorted(media, key=lambda value: value.path):
        digest.update(b"media\0")
        digest.update(
            json.dumps(
                item.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        digest.update(b"\0")
    return digest.hexdigest()[:24]


def _hash_json(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _normalize_text(content: str) -> str:
    return content.replace("\r\n", "\n").replace("\r", "\n")


def _write_fsynced(path: Path, content: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _write_bytes_fsynced(path: Path, content: bytes) -> None:
    with path.open("wb") as handle:
        handle.write(content)
        handle.flush()
        os.fsync(handle.fileno())


def _replace_directory_with_retry(source: Path, target: Path) -> None:
    """Keep atomic package swaps resilient to short Windows scanner locks."""
    for attempt in range(_DIRECTORY_REPLACE_ATTEMPTS):
        try:
            os.replace(source, target)
            return
        except PermissionError:
            if attempt + 1 >= _DIRECTORY_REPLACE_ATTEMPTS:
                raise
            delay = min(
                _DIRECTORY_REPLACE_BASE_DELAY_SECONDS * (2**attempt),
                1.0,
            )
            time.sleep(delay)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def _validation_message(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        errors = exc.errors(include_url=False)
        if errors:
            first = errors[0]
            location = ".".join(str(item) for item in first.get("loc", []))
            return f"{location}: {first.get('msg', '字段无效')}"
    return str(exc)


def _supported_controller_component(component: HardwareComponent) -> bool:
    return (
        component.category != HardwareCategory.MCU
        or component.id in SUPPORTED_CONTROLLER_COMPONENT_IDS
    )


def _now() -> str:
    return datetime.now(UTC).isoformat()
