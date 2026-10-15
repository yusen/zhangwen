"""Static, bounded validation for editable capability package revisions."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import UTC, datetime
from pathlib import PurePosixPath

from pydantic import ValidationError

from zhangwen.domains.packages.models import (
    CapabilityPackage,
    CapabilityPackageManifest,
    PackageValidationIssue,
    PackageValidationSummary,
    ValidationStatus,
)


MAX_PACKAGE_FILES = 256
MAX_FILE_BYTES = 80_000
MAX_PACKAGE_BYTES = 512_000
ALLOWED_SUFFIXES = {".md", ".json", ".yaml", ".yml", ".py", ".js", ".mjs", ".ts"}
KNOWN_PERMISSIONS = {
    "READ_PROJECT",
    "WRITE_ARTIFACT",
    "RUN_MODEL",
    "USE_DEVICE",
    "RUN_CAD",
    "RUN_SHELL",
}
_DANGEROUS_EXECUTABLE_PATTERNS = (
    (re.compile(r"\b(?:os\.system|subprocess\.|child_process\.|eval\s*\(|exec\s*\()"), "EXECUTION_PRIMITIVE"),
    (re.compile(r"\b(?:serial\.|esptool|mpremote|mqtt\.publish|mosquitto)\b", re.I), "EXTERNAL_EFFECT_PRIMITIVE"),
)
_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}"),
    re.compile(r"(?i)\b(?:password|api[_-]?key|secret|token)\s*[:=]\s*['\"][^'\"]{6,}"),
)


def normalize_package_path(value: str) -> str:
    stripped = value.strip()
    if not stripped or "\\" in stripped or ":" in stripped or "\x00" in stripped:
        raise ValueError("Package paths must be normalized relative POSIX paths")
    path = PurePosixPath(stripped)
    if path.is_absolute() or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("Package paths must stay inside the package root")
    if path.suffix.lower() not in ALLOWED_SUFFIXES:
        raise ValueError("Package file type is not allowed")
    return path.as_posix()


def content_digest(files: dict[str, str]) -> str:
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(files[path].encode("utf-8"))
        digest.update(b"\0")
    return digest.hexdigest()


def validate_package_files(
    package: CapabilityPackage,
    files: dict[str, str],
) -> tuple[CapabilityPackageManifest | None, PackageValidationSummary]:
    issues: list[PackageValidationIssue] = []
    normalized: dict[str, str] = {}
    if len(files) > MAX_PACKAGE_FILES:
        issues.append(_issue("PACKAGE_FILE_LIMIT", None, "能力包文件数量超过上限。"))
    total_bytes = 0
    for raw_path, content in files.items():
        try:
            path = normalize_package_path(raw_path)
        except ValueError:
            issues.append(_issue("PACKAGE_PATH_INVALID", raw_path, "文件路径越出能力包根目录或类型不受支持。"))
            continue
        if path in normalized:
            issues.append(_issue("PACKAGE_PATH_DUPLICATE", path, "能力包包含重复文件路径。"))
            continue
        encoded_size = len(content.encode("utf-8"))
        total_bytes += encoded_size
        if encoded_size > MAX_FILE_BYTES:
            issues.append(_issue("PACKAGE_FILE_TOO_LARGE", path, "文件超过大小上限。"))
        if "\x00" in content:
            issues.append(_issue("PACKAGE_FILE_NUL", path, "文本文件不能包含 NUL。"))
        for pattern in _SECRET_PATTERNS:
            if pattern.search(content):
                issues.append(_issue("PACKAGE_SECRET_DETECTED", path, "检测到疑似凭据内容，禁止保存或发布。"))
                break
        if PurePosixPath(path).suffix.lower() in {".py", ".js", ".mjs", ".ts"}:
            for pattern, code in _DANGEROUS_EXECUTABLE_PATTERNS:
                if pattern.search(content):
                    issues.append(_issue(code, path, "可编辑代码声明了未经平台代理的执行或外部副作用。"))
        normalized[path] = content
    if total_bytes > MAX_PACKAGE_BYTES:
        issues.append(_issue("PACKAGE_SIZE_LIMIT", None, "能力包总内容超过大小上限。"))

    manifest: CapabilityPackageManifest | None = None
    raw_manifest = normalized.get("manifest.json")
    if raw_manifest is None:
        issues.append(_issue("PACKAGE_MANIFEST_MISSING", "manifest.json", "能力包缺少 manifest.json。"))
    else:
        try:
            parsed = json.loads(raw_manifest)
            manifest = CapabilityPackageManifest.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError):
            issues.append(_issue("PACKAGE_MANIFEST_INVALID", "manifest.json", "能力包 Manifest 不符合共享契约。"))

    if manifest is not None:
        if manifest.id != package.id:
            issues.append(_issue("PACKAGE_ID_MISMATCH", "manifest.json", "Manifest id 与能力包不一致。"))
        if manifest.kind != package.kind:
            issues.append(_issue("PACKAGE_KIND_MISMATCH", "manifest.json", "Manifest kind 与能力包不一致。"))
        unknown_permissions = sorted(set(manifest.permissions) - KNOWN_PERMISSIONS)
        if unknown_permissions:
            issues.append(_issue("PACKAGE_PERMISSION_UNKNOWN", "manifest.json", "Manifest 包含未知宿主权限。"))
        if "RUN_SHELL" in manifest.permissions and (
            manifest.risk_level != "high" or manifest.confirmation_policy == "never"
        ):
            issues.append(_issue("PACKAGE_SHELL_POLICY_INVALID", "manifest.json", "Shell 权限必须声明高风险和外部效果确认策略。"))
        declared = set(manifest.files)
        actual = set(normalized) - {"manifest.json"}
        for raw_path in manifest.files:
            try:
                normalize_package_path(raw_path)
            except ValueError:
                issues.append(_issue("PACKAGE_MANIFEST_PATH_INVALID", "manifest.json", "Manifest 文件清单包含越界路径。"))
        if declared != actual:
            issues.append(_issue("PACKAGE_FILE_SET_MISMATCH", "manifest.json", "Manifest 文件清单与实际文件集合不一致。"))
        for entry_path in (
            manifest.entrypoints.prompt,
            manifest.entrypoints.input_schema,
            manifest.entrypoints.output_schema,
        ):
            if entry_path is not None and entry_path not in actual:
                issues.append(_issue("PACKAGE_ENTRYPOINT_MISSING", "manifest.json", f"入口文件不存在：{entry_path}"))
        for schema_path in (
            manifest.entrypoints.input_schema,
            manifest.entrypoints.output_schema,
        ):
            if schema_path is not None and schema_path in normalized:
                try:
                    schema = json.loads(normalized[schema_path])
                    if not isinstance(schema, dict) or schema.get("type") != "object":
                        raise ValueError
                except (json.JSONDecodeError, ValueError):
                    issues.append(_issue("PACKAGE_SCHEMA_INVALID", schema_path, "输入输出 Schema 必须是 object JSON Schema。"))

    status = ValidationStatus.FAILED if any(issue.severity == "ERROR" for issue in issues) else ValidationStatus.PASSED
    return manifest, PackageValidationSummary(
        status=status,
        issues=issues,
        checkedAt=datetime.now(UTC).isoformat(),
    )


def _issue(code: str, path: str | None, message: str) -> PackageValidationIssue:
    return PackageValidationIssue(code=code, path=path, message=message)
