"""Immutable binary storage for validated CAD ArtifactVersion files."""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


MAX_FILE_COUNT = 12
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_JOB_BYTES = 256 * 1024 * 1024
MAX_PREVIEW_BYTES = 20 * 1024 * 1024
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,159}$")
EXPECTED_FILES = {
    "assembly.step": ("STEP_ASSEMBLY", "model/step"),
    "base.step": ("STEP_PRINTABLE_PARTS", "model/step"),
    "base.stl": ("STL_PRINTABLE_PARTS", "model/stl"),
    "geometry-summary.json": ("GEOMETRY_SUMMARY", "application/json"),
    "lid.step": ("STEP_PRINTABLE_PARTS", "model/step"),
    "lid.stl": ("STL_PRINTABLE_PARTS", "model/stl"),
    "manifest.json": ("MANIFEST", "application/json"),
    "parameters.json": ("PARAMETERS", "application/json"),
    "preview.glb": ("GLB_PREVIEW", "model/gltf-binary"),
    "profiles.json": ("PROFILE_SNAPSHOTS", "application/json"),
    "validation.json": ("VALIDATION_REPORT", "application/json"),
}


@dataclass(frozen=True)
class ValidatedCadFile:
    role: str
    file_name: str
    source_path: Path
    mime_type: str
    byte_size: int
    sha256: str
    triangle_count: int | None
    bounds: dict[str, Any] | None


@dataclass(frozen=True)
class PublishedCadFile:
    role: str
    file_name: str
    storage_key: str
    mime_type: str
    byte_size: int
    sha256: str
    triangle_count: int | None
    bounds: dict[str, Any] | None


class ArtifactFileStore:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = data_dir.resolve()
        self._staging_root = self._data_dir / "cad" / "staging"
        self._artifact_root = self._data_dir / "artifact-files"
        self._staging_root.mkdir(parents=True, exist_ok=True)
        self._artifact_root.mkdir(parents=True, exist_ok=True)
        _reject_links(self._data_dir, self._staging_root)
        _reject_links(self._data_dir, self._artifact_root)

    def prepare_staging(self, job_id: str) -> Path:
        _safe_identifier(job_id)
        staging = self._staging_root / job_id
        if staging.exists():
            self.discard_staging(job_id)
        staging.mkdir(parents=False)
        return staging

    def staging_path(self, job_id: str) -> Path:
        _safe_identifier(job_id)
        return _contained(self._staging_root, self._staging_root / job_id, strict=False)

    def validate_manifest(
        self,
        job_id: str,
        manifest: dict[str, Any],
        *,
        expected_design_id: str | None = None,
        expected_spec_sha256: str | None = None,
    ) -> list[ValidatedCadFile]:
        staging = _contained(self._staging_root, self.staging_path(job_id), strict=True)
        raw_files = manifest.get("files")
        if manifest.get("schemaVersion") != "1.0":
            raise ValueError("CAD Worker manifest schema 版本无效。")
        if manifest.get("engineId") != "zhangwen-cad-engine":
            raise ValueError("CAD Worker engine 标识无效。")
        if expected_design_id is not None and manifest.get("designId") != expected_design_id:
            raise ValueError("CAD Worker manifest 与当前 Job 标识不匹配。")
        if expected_spec_sha256 is not None and manifest.get("specSha256") != expected_spec_sha256:
            raise ValueError("CAD Worker manifest 与当前构建规范哈希不匹配。")
        if not isinstance(manifest.get("designId"), str) or not manifest["designId"]:
            raise ValueError("CAD Worker designId 无效。")
        if not isinstance(manifest.get("specSha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", manifest["specSha256"]
        ):
            raise ValueError("CAD Worker specSha256 无效。")
        if not isinstance(raw_files, list) or len(raw_files) != len(EXPECTED_FILES):
            raise ValueError("CAD Worker 输出文件集合不完整。")

        files: list[ValidatedCadFile] = []
        total_bytes = 0
        seen_names: set[tuple[str, str]] = set()
        seen_file_names: set[str] = set()
        for raw in raw_files:
            if not isinstance(raw, dict):
                raise ValueError("CAD Worker 文件清单项必须是对象。")
            relative_path = _safe_relative_path(raw.get("relativePath"))
            source = _contained(staging, staging.joinpath(*relative_path.parts), strict=True)
            _reject_links(staging, source)
            if not source.is_file():
                raise ValueError("CAD Worker 清单引用了非文件输出。")
            byte_size = source.stat().st_size
            if byte_size <= 0 or byte_size > MAX_FILE_BYTES:
                raise ValueError("CAD Worker 单文件大小超出允许范围。")
            total_bytes += byte_size
            if total_bytes > MAX_JOB_BYTES:
                raise ValueError("CAD Worker 输出总量超出允许范围。")
            role = _required_text(raw, "role", 80)
            file_name = _required_text(raw, "fileName", 160)
            if relative_path.as_posix() != file_name:
                raise ValueError("CAD Worker 相对路径必须与固定文件名一致。")
            if PurePosixPath(file_name).name != file_name or not SAFE_ID.fullmatch(file_name):
                raise ValueError("CAD Worker 文件名无效。")
            expected = EXPECTED_FILES.get(file_name)
            if expected is None or expected != (role, raw.get("mimeType")):
                raise ValueError("CAD Worker 文件角色、名称或 MIME 类型不匹配。")
            if file_name in seen_file_names:
                raise ValueError("CAD Worker 文件名重复。")
            seen_file_names.add(file_name)
            identity = (role, file_name)
            if identity in seen_names:
                raise ValueError("CAD Worker 文件角色和名称重复。")
            seen_names.add(identity)
            digest = _sha256(source)
            declared_digest = _required_text(raw, "sha256", 64).lower()
            if digest != declared_digest or int(raw.get("byteSize", -1)) != byte_size:
                raise ValueError("CAD Worker 文件哈希或大小不匹配。")
            if role == "GLB_PREVIEW" and byte_size > MAX_PREVIEW_BYTES:
                raise ValueError("GLB 预览超过 20 MiB 上限。")
            triangle_count = raw.get("triangleCount")
            if triangle_count is not None and (
                not isinstance(triangle_count, int) or triangle_count < 0
            ):
                raise ValueError("triangleCount 必须是非负整数。")
            bounds = _validated_bounds(raw.get("bounds"))
            files.append(
                ValidatedCadFile(
                    role=role,
                    file_name=file_name,
                    source_path=source,
                    mime_type=_required_text(raw, "mimeType", 120),
                    byte_size=byte_size,
                    sha256=digest,
                    triangle_count=triangle_count,
                    bounds=bounds,
                )
            )
        if seen_file_names != set(EXPECTED_FILES):
            raise ValueError("CAD Worker 输出文件集合不完整。")
        return files

    def publish(
        self,
        *,
        job_id: str,
        project_id: str,
        artifact_id: str,
        version_id: str,
        files: list[ValidatedCadFile],
    ) -> list[PublishedCadFile]:
        for value in (job_id, project_id, artifact_id, version_id):
            _safe_identifier(value)
        artifact_parent = _ensure_child_directories(
            self._artifact_root,
            (project_id, artifact_id),
        )
        final_dir = _contained(
            self._artifact_root,
            artifact_parent / version_id,
            strict=False,
        )
        if final_dir.exists():
            raise ValueError("ArtifactVersion 文件目录已经存在。")
        publish_dir = self._staging_root / f"publish-{job_id}"
        if publish_dir.exists():
            _reject_links(self._staging_root, publish_dir)
            shutil.rmtree(publish_dir)
        publish_dir.mkdir(parents=False)
        for item in files:
            destination = publish_dir / item.file_name
            shutil.copyfile(item.source_path, destination)
            if destination.stat().st_size != item.byte_size or _sha256(destination) != item.sha256:
                raise ValueError("CAD 文件发布副本校验失败。")
        os.replace(publish_dir, final_dir)
        published: list[PublishedCadFile] = []
        for item in files:
            storage_key = PurePosixPath(
                project_id,
                artifact_id,
                version_id,
                item.file_name,
            ).as_posix()
            published.append(
                PublishedCadFile(
                    role=item.role,
                    file_name=item.file_name,
                    storage_key=storage_key,
                    mime_type=item.mime_type,
                    byte_size=item.byte_size,
                    sha256=item.sha256,
                    triangle_count=item.triangle_count,
                    bounds=item.bounds,
                )
            )
        return published

    def discard_staging(self, job_id: str) -> None:
        staging = self.staging_path(job_id)
        if staging.exists():
            _reject_links(self._staging_root, staging)
            shutil.rmtree(staging)

    def discard_publish_staging(self, job_id: str) -> None:
        _safe_identifier(job_id)
        publish_dir = self._staging_root / f"publish-{job_id}"
        if publish_dir.exists():
            _reject_links(self._staging_root, publish_dir)
            shutil.rmtree(publish_dir)

    def remove_published(
        self,
        *,
        project_id: str,
        artifact_id: str,
        version_id: str,
    ) -> None:
        for value in (project_id, artifact_id, version_id):
            _safe_identifier(value)
        candidate = self._artifact_root / project_id / artifact_id / version_id
        resolved = _contained(self._artifact_root, candidate, strict=False)
        if not resolved.exists():
            return
        _reject_links(self._artifact_root, resolved)
        if not resolved.is_dir():
            raise ValueError("ArtifactVersion 文件目录无效。")
        shutil.rmtree(resolved)


def bounds_json(bounds: dict[str, Any] | None) -> str | None:
    return json.dumps(bounds, ensure_ascii=False, sort_keys=True) if bounds else None


def _safe_identifier(value: str) -> str:
    if not SAFE_ID.fullmatch(value):
        raise ValueError("CAD 标识无效。")
    return value


def _safe_relative_path(value: object) -> PurePosixPath:
    if not isinstance(value, str):
        raise ValueError("CAD Worker 相对路径缺失。")
    path = PurePosixPath(value)
    if path.is_absolute() or not path.parts or any(part in {"", ".", ".."} for part in path.parts):
        raise ValueError("CAD Worker 相对路径无效。")
    return path


def _contained(root: Path, candidate: Path, *, strict: bool) -> Path:
    root_resolved = root.resolve()
    resolved = candidate.resolve(strict=strict)
    if resolved != root_resolved and root_resolved not in resolved.parents:
        raise ValueError("CAD 文件路径越界。")
    return resolved


def _reject_links(root: Path, candidate: Path) -> None:
    root_resolved = root.resolve()
    current = candidate
    while True:
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("CAD 文件路径包含不受支持的链接。")
        if current.resolve() == root_resolved:
            break
        if current.parent == current:
            raise ValueError("CAD 文件路径无法归入受控根目录。")
        current = current.parent


def _ensure_child_directories(root: Path, parts: tuple[str, ...]) -> Path:
    _reject_links(root.parent, root)
    current = root
    for part in parts:
        _safe_identifier(part)
        candidate = current / part
        if candidate.exists():
            _reject_links(root, candidate)
            if not candidate.is_dir():
                raise ValueError("CAD Artifact 目录无效。")
        else:
            candidate.mkdir()
        current = _contained(root, candidate, strict=True)
    return current


def _validated_bounds(value: object) -> dict[str, Any] | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("bounds 必须是对象。")
    keys = ("min_x", "min_y", "min_z", "max_x", "max_y", "max_z")
    if set(value) != set(keys):
        raise ValueError("bounds 字段无效。")
    normalized: dict[str, float] = {}
    for key in keys:
        raw = value[key]
        if isinstance(raw, bool) or not isinstance(raw, (int, float)):
            raise ValueError("bounds 坐标必须是有限数值。")
        number = float(raw)
        if not math.isfinite(number):
            raise ValueError("bounds 坐标必须是有限数值。")
        normalized[key] = number
    for axis in ("x", "y", "z"):
        if normalized[f"min_{axis}"] > normalized[f"max_{axis}"]:
            raise ValueError("bounds 最小坐标不能大于最大坐标。")
    return normalized


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _required_text(value: dict[str, Any], key: str, max_length: int) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw or len(raw) > max_length:
        raise ValueError(f"CAD Worker 字段 {key} 无效。")
    return raw
