"""SQLite-backed project package export/import repository."""

from __future__ import annotations

import base64
import hashlib
import io
import json
import os
import re
import shutil
import sqlite3
import stat
import uuid
import zipfile
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

from zhangwen.artifacts.models import (
    ArtifactDefinition,
    ArtifactKind,
    ArtifactPreviewSection,
    ArtifactStatus,
)
from zhangwen.artifacts.repository import ArtifactRepository
from zhangwen.llm.contracts import LLMModelId
from zhangwen.project_packages.errors import (
    ProjectPackageConflictError,
    ProjectPackageInvalidError,
    ProjectPackagePrivacyBlockedError,
    ProjectPackageUnsafeZipError,
)
from zhangwen.project_packages.models import (
    ExportProjectPackageRequest,
    ImportProjectPackageRequest,
    ProjectPackageArtifactSelection,
    ProjectPackageConflictStrategy,
    ProjectPackageItemKind,
    ProjectPackageManifest,
    ProjectPackageManifestArtifact,
    ProjectPackageManifestFile,
    ProjectPackageRecord,
    ProjectPackageStatus,
)
from zhangwen.project_packages.privacy import scan_package_payload
from zhangwen.projects.models import ProjectStage
from zhangwen.projects.repository import ProjectRepository
from zhangwen.projects.lifecycle import ProjectLifecycleService


MAX_PACKAGE_MEMBERS = 512
MAX_PACKAGE_FILE_BYTES = 128 * 1024 * 1024
MAX_PACKAGE_BYTES = 512 * 1024 * 1024


class ProjectPackageRepository:
    def __init__(self, data_dir: Path) -> None:
        self._data_dir = Path(data_dir).resolve()
        self._project_repo = ProjectRepository(data_dir)
        self._db_path = self._project_repo.db_path

    def export_project(
        self,
        project_id: str,
        request: ExportProjectPackageRequest,
    ) -> ProjectPackageRecord:
        workspace = self._project_repo.get_workspace(project_id)
        package_id = _id("pkg")
        now = _now()
        title = (request.title or f"{workspace.project.name} 项目包").strip()
        selection = _artifact_selection(request)
        artifact_payloads = self._selected_artifact_payloads(project_id, selection)
        files: dict[str, str | bytes] = {
            "project/summary.json": _json_dumps(
                {
                    "project": workspace.project.model_dump(mode="json"),
                    "conversationMessageCount": len(workspace.conversation.messages),
                    "draftIncluded": False,
                }
            ),
        }
        manifest_artifacts: list[ProjectPackageManifestArtifact] = []
        has_binary_artifacts = False
        for path, artifact, payload in artifact_payloads:
            version = payload["version"]
            files[path] = _json_dumps(payload)
            manifest_files: list[ProjectPackageManifestFile] = []
            for manifest_file, content in self._artifact_binary_payloads(
                project_id,
                artifact.id,
                str(version["id"]),
            ):
                files[manifest_file.path] = content
                manifest_files.append(manifest_file)
                has_binary_artifacts = True
            manifest_artifacts.append(
                ProjectPackageManifestArtifact(
                    artifactId=artifact.id,
                    versionId=str(version["id"]),
                    title=artifact.title,
                    kind=artifact.kind,
                    sourceAgentId=artifact.sourceAgentId,
                    sourceEntityType=version.get("sourceEntityType"),
                    sourceEntityId=version.get("sourceEntityId"),
                    version=int(version["version"]),
                    status=ArtifactStatus(str(version["status"])),
                    path=path,
                    checksum=str(version["checksum"]),
                    files=manifest_files,
                )
            )

        privacy_report = scan_package_payload(_text_package_files(files))
        manifest = ProjectPackageManifest(
            schemaVersion=2,
            packageId=package_id,
            packageVersion=2,
            status=(
                ProjectPackageStatus.EXPORTED
                if privacy_report.ok
                else ProjectPackageStatus.BLOCKED
            ),
            projectId=workspace.project.id,
            projectName=workspace.project.name,
            projectStage=workspace.project.stage,
            exportedAt=now,
            itemKinds=[
                ProjectPackageItemKind.MANIFEST,
                ProjectPackageItemKind.PROJECT,
                ProjectPackageItemKind.ARTIFACT,
                *(
                    [ProjectPackageItemKind.ARTIFACT_FILE]
                    if has_binary_artifacts
                    else []
                ),
                ProjectPackageItemKind.PRIVACY_REPORT,
            ],
            artifactSelection=selection,
            artifacts=manifest_artifacts,
            privacyReport=privacy_report,
        )
        files["manifest.json"] = _json_dumps(manifest.model_dump(mode="json"))
        files["privacy_report.json"] = _json_dumps(privacy_report.model_dump(mode="json"))
        if not privacy_report.ok:
            self._insert_record(
                ProjectPackageRecord(
                    id=package_id,
                    projectId=project_id,
                    status=ProjectPackageStatus.BLOCKED,
                    title=title,
                    fileName=_package_file_name(package_id),
                    manifest=manifest,
                    privacyReport=privacy_report,
                    zipBase64=None,
                    createdAt=now,
                    importedAt=None,
                )
            )
            raise ProjectPackagePrivacyBlockedError("项目包包含疑似敏感信息，已阻止导出。")

        zip_base64 = _zip_files_base64(files)
        record = ProjectPackageRecord(
            id=package_id,
            projectId=project_id,
            status=ProjectPackageStatus.EXPORTED,
            title=title,
            fileName=_package_file_name(package_id),
            manifest=manifest,
            privacyReport=privacy_report,
            zipBase64=zip_base64,
            createdAt=now,
            importedAt=None,
        )
        self._insert_record(record)
        version = self._sync_package_artifact(record, source_version=self._package_version(project_id))
        record.artifactId = version.artifactId
        record.artifactVersionId = version.id
        self._update_record_artifact(record)
        return record

    def import_project(
        self,
        request: ImportProjectPackageRequest,
        *,
        target_project_id: str | None = None,
    ) -> tuple[ProjectPackageRecord, Any]:
        files = _read_package_zip(request.zipBase64)
        manifest_data = _load_required_json(files, "manifest.json")
        summary_data = _load_required_json(files, "project/summary.json")
        report_data = _load_required_json(files, "privacy_report.json")
        try:
            manifest = ProjectPackageManifest(**manifest_data)
        except Exception as exc:
            raise ProjectPackageInvalidError("项目包 manifest 无效。") from exc

        source_project_id = manifest.projectId
        if (
            request.conflictStrategy == ProjectPackageConflictStrategy.FAIL_IF_EXISTS
            and self._project_exists(source_project_id)
        ):
            raise ProjectPackageConflictError("本地已存在同 ID 项目，已按导入策略停止。")

        privacy_report = scan_package_payload(_text_package_files(files))
        if not bool(report_data.get("ok", False)) or not privacy_report.ok:
            raise ProjectPackagePrivacyBlockedError("项目包包含疑似敏感信息，已阻止导入。")
        _validate_package_artifact_files(manifest, files)

        project_data = summary_data.get("project", {})
        source_name = str(project_data.get("name") or manifest.projectName)
        initial_idea = str(project_data.get("profile", {}).get("initialIdea") or "")
        model = _model_or_default(project_data.get("selectedModel"))
        workspace = self._project_repo.create_project(
            f"{source_name}（导入副本）",
            initial_idea,
            model,
            project_id_override=target_project_id,
        )
        project_id = workspace.project.id
        try:
            self._update_imported_project_stage(project_id, manifest.projectStage)
        except Exception:
            self.discard_imported_project(project_id)
            raise
        imported_at = _now()
        try:
            self._import_artifacts(project_id, manifest, files)
        except Exception:
            self.discard_imported_project(project_id)
            raise

        record = ProjectPackageRecord(
            id=_id("pkg_import"),
            projectId=project_id,
            status=ProjectPackageStatus.IMPORTED,
            title=f"{source_name} 项目包导入记录",
            fileName=_package_file_name(manifest.packageId),
            manifest=manifest,
            privacyReport=privacy_report,
            zipBase64=None,
            createdAt=imported_at,
            importedAt=imported_at,
        )
        try:
            self._insert_record(record)
            version = self._sync_package_artifact(
                record, source_version=self._package_version(project_id)
            )
        except Exception:
            self.discard_imported_project(project_id)
            raise
        record.artifactId = version.artifactId
        record.artifactVersionId = version.id
        try:
            self._update_record_artifact(record)
        except Exception:
            self.discard_imported_project(project_id)
            raise
        return record, self._project_repo.get_workspace(project_id)

    def discard_imported_project(self, project_id: str) -> None:
        """Compensate a failed import while retaining ZIP/path safety."""

        with self._connect() as conn:
            lifecycle = ProjectLifecycleService(self._data_dir)
            tables = lifecycle._project_tables(conn, include_excluded=True)
            order = lifecycle._table_order(conn, {table: [] for table in tables})
            conn.execute("BEGIN IMMEDIATE")
            conn.execute("PRAGMA defer_foreign_keys=ON")
            conn.execute(
                "DELETE FROM creator_delivery_imports WHERE imported_project_id = ?",
                (project_id,),
            )
            conn.execute(
                "UPDATE account_workspace_state SET current_project_id = NULL "
                "WHERE current_project_id = ?",
                (project_id,),
            )
            for table in reversed(order):
                conn.execute(
                    f'DELETE FROM "{table}" WHERE project_id = ?', (project_id,)
                )
            conn.execute("DELETE FROM projects WHERE id = ?", (project_id,))
        directory = self._data_dir / "artifact-files" / project_id
        if directory.exists():
            _reject_path_links(self._data_dir / "artifact-files", directory)
            shutil.rmtree(directory)

    def _selected_artifact_payloads(
        self,
        project_id: str,
        selection: ProjectPackageArtifactSelection,
    ) -> list[tuple[str, ArtifactDefinition, dict[str, Any]]]:
        payloads: list[tuple[str, ArtifactDefinition, dict[str, Any]]] = []
        artifacts = ArtifactRepository(self._db_path).list_artifacts(project_id)
        for artifact in artifacts:
            if not _artifact_selected(artifact, selection):
                continue
            version = _current_version(artifact)
            if version is None:
                continue
            path = f"artifacts/{_safe_slug(artifact.id)}.json"
            payloads.append(
                (
                    path,
                    artifact,
                    {
                        "artifact": artifact.model_dump(
                            mode="json",
                            exclude={"versions"},
                        ),
                        "version": version.model_dump(mode="json"),
                    },
                )
            )
        return payloads

    def _artifact_binary_payloads(
        self,
        project_id: str,
        artifact_id: str,
        version_id: str,
    ) -> list[tuple[ProjectPackageManifestFile, bytes]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, role, file_name, storage_key, mime_type, byte_size,
                       sha256, triangle_count, bounds_json
                FROM artifact_files
                WHERE project_id = ? AND artifact_id = ? AND artifact_version_id = ?
                ORDER BY role, file_name, id
                """,
                (project_id, artifact_id, version_id),
            ).fetchall()
        payloads: list[tuple[ProjectPackageManifestFile, bytes]] = []
        for row in rows:
            source = _artifact_file_path(self._data_dir, str(row["storage_key"]))
            content = source.read_bytes()
            digest = hashlib.sha256(content).hexdigest()
            if len(content) != int(row["byte_size"]) or digest != str(row["sha256"]):
                raise ProjectPackageInvalidError(
                    f"CAD 产物文件校验失败，无法导出：{row['file_name']}"
                )
            file_name = str(row["file_name"])
            archive_path = PurePosixPath(
                "artifact-files",
                _safe_slug(artifact_id),
                _safe_slug(version_id),
                file_name,
            ).as_posix()
            bounds = json.loads(row["bounds_json"]) if row["bounds_json"] else None
            payloads.append(
                (
                    ProjectPackageManifestFile(
                        artifactFileId=str(row["id"]),
                        role=str(row["role"]),
                        fileName=file_name,
                        path=archive_path,
                        mimeType=str(row["mime_type"]),
                        byteSize=len(content),
                        sha256=digest,
                        triangleCount=row["triangle_count"],
                        bounds=bounds,
                    ),
                    content,
                )
            )
        return payloads

    def _import_artifacts(
        self,
        project_id: str,
        manifest: ProjectPackageManifest,
        files: dict[str, bytes],
    ) -> None:
        now = _now()
        published_directories: list[Path] = []
        try:
            with self._connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                for index, manifest_artifact in enumerate(manifest.artifacts, start=1):
                    raw = files.get(manifest_artifact.path)
                    if raw is None:
                        raise ProjectPackageInvalidError(
                            "项目包缺少 manifest 引用的 Artifact。"
                        )
                    try:
                        payload = json.loads(_decode_package_text(raw, manifest_artifact.path))
                        artifact_data = payload["artifact"]
                        version_data = payload["version"]
                    except Exception as exc:
                        raise ProjectPackageInvalidError("项目包 Artifact 数据无效。") from exc
                    artifact_id = f"artifact_imported_{project_id}_{index}"
                    version_id = f"artifact_version_imported_{project_id}_{index}"
                    imported_files = _publish_imported_artifact_files(
                        self._data_dir,
                        project_id=project_id,
                        artifact_id=artifact_id,
                        version_id=version_id,
                        manifest_files=manifest_artifact.files,
                        package_files=files,
                    )
                    if imported_files:
                        published_directories.append(
                            self._data_dir
                            / "artifact-files"
                            / project_id
                            / artifact_id
                            / version_id
                        )
                    preview = dict(version_data["preview"])
                    glb = next(
                        (item for item in imported_files if item["role"] == "GLB_PREVIEW"),
                        None,
                    )
                    if glb is not None:
                        preview["modelFileId"] = glb["id"]
                        preview["modelUrl"] = (
                            f"/api/projects/{project_id}/artifacts/{artifact_id}/versions/"
                            f"{version_id}/files/{glb['id']}"
                        )
                    conn.execute(
                        """
                        INSERT INTO artifacts (
                          id, project_id, title, kind, status, source_agent_id,
                          current_version_id, created_at, updated_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            artifact_id,
                            project_id,
                            str(artifact_data["title"]),
                            str(artifact_data["kind"]),
                            str(artifact_data["status"]),
                            str(artifact_data.get("sourceAgentId") or "publish-agent"),
                            version_id,
                            now,
                            now,
                        ),
                    )
                    conn.execute(
                        """
                        INSERT INTO artifact_versions (
                          id, artifact_id, project_id, version, status, mime_type,
                          preview_json, dependencies_json, producer_task_id,
                          source_entity_type, source_entity_id, checksum, stale_reason,
                          created_at, confirmed_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            version_id,
                            artifact_id,
                            project_id,
                            1,
                            str(version_data["status"]),
                            str(version_data["mimeType"]),
                            _json_dumps(preview),
                            _json_dumps(version_data.get("dependencies", [])),
                            None,
                            "package-import",
                            manifest.packageId,
                            hashlib.sha256(raw).hexdigest(),
                            None,
                            now,
                            None,
                        ),
                    )
                    for item in imported_files:
                        conn.execute(
                            """
                            INSERT INTO artifact_files (
                              id, artifact_id, artifact_version_id, project_id,
                              role, file_name, storage_key, mime_type, byte_size,
                              sha256, triangle_count, bounds_json, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            """,
                            (
                                item["id"],
                                artifact_id,
                                version_id,
                                project_id,
                                item["role"],
                                item["file_name"],
                                item["storage_key"],
                                item["mime_type"],
                                item["byte_size"],
                                item["sha256"],
                                item["triangle_count"],
                                _json_dumps(item["bounds"]) if item["bounds"] else None,
                                now,
                            ),
                        )
        except Exception:
            for directory in reversed(published_directories):
                if directory.exists():
                    _reject_path_links(self._data_dir / "artifact-files", directory)
                    shutil.rmtree(directory)
            raise

    def _sync_package_artifact(self, record: ProjectPackageRecord, *, source_version: int):
        manifest_summary = (
            f"项目包 {record.title}，包含 {len(record.manifest.artifacts)} 个产物预览。"
        )
        sections = [
            ArtifactPreviewSection(
                id="package_manifest",
                title="Manifest",
                content=_json_dumps(record.manifest.model_dump(mode="json")),
            ),
            ArtifactPreviewSection(
                id="privacy_report",
                title="隐私扫描",
                content=_json_dumps(record.privacyReport.model_dump(mode="json")),
            ),
        ]
        return ArtifactRepository(self._db_path).upsert_text_artifact(
            artifact_id=f"artifact_package_{record.projectId}",
            project_id=record.projectId,
            title=record.title,
            kind=ArtifactKind.PACKAGE,
            status=ArtifactStatus.APPROVED,
            source_agent_id="publish-agent",
            source_entity_type="project-package",
            source_entity_id=record.id,
            source_version=source_version,
            content=manifest_summary,
            summary=manifest_summary,
            mime_type="application/vnd.zhangwen.project-package+zip",
            sections=sections,
            dependencies=[],
            stale_reason=None,
            confirmed_at=record.importedAt or record.createdAt,
        )

    def _insert_record(self, record: ProjectPackageRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO package_exports (
                  id, project_id, status, title, file_name, manifest_json,
                  privacy_report_json, artifact_id, artifact_version_id,
                  zip_base64, created_at, imported_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.id,
                    record.projectId,
                    record.status.value,
                    record.title,
                    record.fileName,
                    _json_dumps(record.manifest.model_dump(mode="json")),
                    _json_dumps(record.privacyReport.model_dump(mode="json")),
                    record.artifactId,
                    record.artifactVersionId,
                    record.zipBase64,
                    record.createdAt,
                    record.importedAt,
                ),
            )

    def _update_record_artifact(self, record: ProjectPackageRecord) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                UPDATE package_exports
                SET artifact_id = ?, artifact_version_id = ?
                WHERE id = ?
                """,
                (record.artifactId, record.artifactVersionId, record.id),
            )

    def _package_version(self, project_id: str) -> int:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT COUNT(*) FROM package_exports WHERE project_id = ?",
                (project_id,),
            ).fetchone()
            return int(row[0])

    def _project_exists(self, project_id: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT 1 FROM projects WHERE id = ?",
                (project_id,),
            ).fetchone()
            return row is not None

    def _update_imported_project_stage(self, project_id: str, stage: ProjectStage) -> None:
        now = _now()
        with self._connect() as conn:
            conn.execute(
                "UPDATE projects SET stage = ?, updated_at = ? WHERE id = ?",
                (stage.value, now, project_id),
            )

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        return conn


def _artifact_selected(
    artifact: ArtifactDefinition,
    selection: ProjectPackageArtifactSelection,
) -> bool:
    if artifact.kind == ArtifactKind.PACKAGE:
        return False
    if artifact.kind == ArtifactKind.CODE:
        return selection.includeCode
    if artifact.kind == ArtifactKind.MODEL_3D:
        return selection.includeCad
    if artifact.kind == ArtifactKind.DEVICE_LOG:
        return selection.includeDeviceLogs
    if artifact.sourceAgentId == "lesson-agent":
        return selection.includeLessons
    if artifact.kind == ArtifactKind.DOCUMENT:
        return selection.includeDocuments
    return False


def _artifact_selection(
    request: ExportProjectPackageRequest,
) -> ProjectPackageArtifactSelection:
    defaults = ProjectPackageArtifactSelection()
    if request.artifactSelection is None:
        return defaults
    return ProjectPackageArtifactSelection(
        **{
            **defaults.model_dump(mode="json"),
            **request.artifactSelection.model_dump(
                mode="json",
                exclude_none=True,
            ),
        }
    )


def _current_version(artifact: ArtifactDefinition):
    if artifact.currentVersionId:
        for version in artifact.versions:
            if version.id == artifact.currentVersionId:
                return version
    return artifact.versions[0] if artifact.versions else None


def _read_package_zip(zip_base64: str) -> dict[str, bytes]:
    try:
        raw = base64.b64decode(zip_base64, validate=True)
    except Exception as exc:
        raise ProjectPackageInvalidError("项目包不是有效的 base64 ZIP。") from exc
    files: dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(raw), "r") as archive:
            members = archive.infolist()
            if len(members) > MAX_PACKAGE_MEMBERS:
                raise ProjectPackageUnsafeZipError("项目包文件数量超出允许范围。")
            total_size = 0
            for info in members:
                _validate_zip_member_path(info.filename)
                if info.is_dir():
                    raise ProjectPackageUnsafeZipError("项目包包含目录项，已拒绝导入。")
                if info.flag_bits & 0x1:
                    raise ProjectPackageUnsafeZipError("项目包包含加密条目，已拒绝导入。")
                unix_mode = (info.external_attr >> 16) & 0xFFFF
                if stat.S_IFMT(unix_mode) == stat.S_IFLNK:
                    raise ProjectPackageUnsafeZipError("项目包包含符号链接，已拒绝导入。")
                if info.file_size > MAX_PACKAGE_FILE_BYTES:
                    raise ProjectPackageUnsafeZipError("项目包单文件大小超出允许范围。")
                total_size += info.file_size
                if total_size > MAX_PACKAGE_BYTES:
                    raise ProjectPackageUnsafeZipError("项目包解压总量超出允许范围。")
                content = archive.read(info)
                if len(content) != info.file_size:
                    raise ProjectPackageInvalidError("项目包条目大小与 ZIP 清单不一致。")
                files[info.filename] = content
    except ProjectPackageUnsafeZipError:
        raise
    except Exception as exc:
        raise ProjectPackageInvalidError("项目包 ZIP 无法读取。") from exc
    return files


def _validate_zip_member_path(path: str) -> None:
    if (
        not path
        or "\\" in path
        or path.startswith("/")
        or re.match(r"^[A-Za-z]:", path)
    ):
        raise ProjectPackageUnsafeZipError("项目包包含不安全路径，已拒绝导入。")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ProjectPackageUnsafeZipError("项目包包含路径穿越，已拒绝导入。")
    allowed_exact = {"manifest.json", "privacy_report.json", "project/summary.json"}
    if path in allowed_exact:
        return
    if path.startswith("artifacts/") and len(parts) == 2 and parts[1].endswith(".json"):
        return
    if path.startswith("artifact-files/") and len(parts) == 4:
        if all(re.fullmatch(r"[A-Za-z0-9_.-]+", part) for part in parts[1:]):
            return
    raise ProjectPackageUnsafeZipError("项目包包含未知路径，已拒绝导入。")


def _load_required_json(files: dict[str, bytes], path: str) -> dict[str, Any]:
    try:
        return json.loads(_decode_package_text(files[path], path))
    except KeyError as exc:
        raise ProjectPackageInvalidError(f"项目包缺少 {path}。") from exc
    except json.JSONDecodeError as exc:
        raise ProjectPackageInvalidError(f"项目包 {path} 不是有效 JSON。") from exc


def _zip_files_base64(files: dict[str, str | bytes]) -> str:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(files):
            _validate_zip_member_path(path)
            archive.writestr(path, files[path])
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _decode_package_text(value: bytes, path: str) -> str:
    try:
        return value.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ProjectPackageInvalidError(f"项目包 {path} 不是 UTF-8 文本。") from exc


def _text_package_files(files: dict[str, str | bytes]) -> dict[str, str]:
    text_files: dict[str, str] = {}
    for path, value in files.items():
        if not path.endswith(".json"):
            continue
        if isinstance(value, str):
            text_files[path] = value
        else:
            text_files[path] = _decode_package_text(value, path)
    return text_files


def _validate_package_artifact_files(
    manifest: ProjectPackageManifest,
    files: dict[str, bytes],
) -> None:
    referenced_paths: set[str] = set()
    referenced_ids: set[str] = set()
    total_bytes = 0
    for artifact in manifest.artifacts:
        for item in artifact.files:
            _validate_zip_member_path(item.path)
            if item.path in referenced_paths or item.artifactFileId in referenced_ids:
                raise ProjectPackageInvalidError("项目包 Artifact 文件清单包含重复项。")
            if PurePosixPath(item.path).name != item.fileName:
                raise ProjectPackageInvalidError("项目包 Artifact 文件名与路径不一致。")
            content = files.get(item.path)
            if content is None:
                raise ProjectPackageInvalidError("项目包缺少 manifest 引用的二进制文件。")
            total_bytes += len(content)
            if total_bytes > MAX_PACKAGE_BYTES:
                raise ProjectPackageInvalidError("项目包 Artifact 文件总量超出允许范围。")
            if len(content) != item.byteSize:
                raise ProjectPackageInvalidError("项目包 Artifact 文件大小不一致。")
            if hashlib.sha256(content).hexdigest() != item.sha256:
                raise ProjectPackageInvalidError("项目包 Artifact 文件 SHA-256 不一致。")
            referenced_paths.add(item.path)
            referenced_ids.add(item.artifactFileId)
    packaged_binary_paths = {
        path for path in files if path.startswith("artifact-files/")
    }
    if packaged_binary_paths != referenced_paths:
        raise ProjectPackageInvalidError("项目包包含未被 manifest 引用的 Artifact 文件。")


def _publish_imported_artifact_files(
    data_dir: Path,
    *,
    project_id: str,
    artifact_id: str,
    version_id: str,
    manifest_files: list[ProjectPackageManifestFile],
    package_files: dict[str, bytes],
) -> list[dict[str, Any]]:
    if not manifest_files:
        return []
    artifact_root = (data_dir / "artifact-files").resolve()
    staging_root = (data_dir / "project-package-staging").resolve()
    artifact_root.mkdir(parents=True, exist_ok=True)
    staging_root.mkdir(parents=True, exist_ok=True)
    _reject_path_links(data_dir, artifact_root)
    _reject_path_links(data_dir, staging_root)
    parent = _ensure_safe_directories(artifact_root, (project_id, artifact_id))
    final_directory = parent / version_id
    if final_directory.exists():
        raise ProjectPackageConflictError("导入 ArtifactVersion 文件目录已经存在。")
    staging = staging_root / f"import-{uuid.uuid4().hex}"
    staging.mkdir()
    imported: list[dict[str, Any]] = []
    try:
        for item in manifest_files:
            content = package_files[item.path]
            destination = staging / item.fileName
            if destination.exists():
                raise ProjectPackageInvalidError("项目包 Artifact 文件名重复。")
            destination.write_bytes(content)
            if (
                destination.stat().st_size != item.byteSize
                or hashlib.sha256(destination.read_bytes()).hexdigest() != item.sha256
            ):
                raise ProjectPackageInvalidError("导入 Artifact 文件写入校验失败。")
            file_id = f"artifact_file_imported_{uuid.uuid4().hex}"
            imported.append(
                {
                    "id": file_id,
                    "role": item.role,
                    "file_name": item.fileName,
                    "storage_key": PurePosixPath(
                        project_id,
                        artifact_id,
                        version_id,
                        item.fileName,
                    ).as_posix(),
                    "mime_type": item.mimeType,
                    "byte_size": item.byteSize,
                    "sha256": item.sha256,
                    "triangle_count": item.triangleCount,
                    "bounds": item.bounds,
                }
            )
        os.replace(staging, final_directory)
    finally:
        if staging.exists():
            _reject_path_links(staging_root, staging)
            shutil.rmtree(staging)
    return imported


def _ensure_safe_directories(root: Path, parts: tuple[str, ...]) -> Path:
    current = root
    for part in parts:
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", part):
            raise ProjectPackageInvalidError("导入 Artifact 目录标识无效。")
        candidate = current / part
        if candidate.exists():
            _reject_path_links(root, candidate)
            if not candidate.is_dir():
                raise ProjectPackageInvalidError("导入 Artifact 路径不是目录。")
        else:
            candidate.mkdir()
        resolved = candidate.resolve(strict=True)
        if root != resolved and root not in resolved.parents:
            raise ProjectPackageUnsafeZipError("导入 Artifact 目录越界。")
        current = resolved
    return current


def _artifact_file_path(data_dir: Path, storage_key: str) -> Path:
    root = (data_dir / "artifact-files").resolve()
    relative = PurePosixPath(storage_key)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ProjectPackageInvalidError("Artifact storage key 无效。")
    candidate = root.joinpath(*relative.parts).resolve(strict=True)
    if root != candidate and root not in candidate.parents:
        raise ProjectPackageInvalidError("Artifact 文件路径越界。")
    _reject_path_links(root, candidate)
    if not candidate.is_file():
        raise ProjectPackageInvalidError("Artifact storage key 未指向文件。")
    return candidate


def _reject_path_links(root: Path, candidate: Path) -> None:
    resolved_root = root.resolve()
    current = candidate
    while True:
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ProjectPackageInvalidError("Artifact 文件路径包含不受支持的链接。")
        if current.resolve() == resolved_root:
            return
        if current.parent == current:
            raise ProjectPackageInvalidError("Artifact 文件路径不在受控目录内。")
        current = current.parent


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _checksum(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _model_or_default(value: object) -> LLMModelId:
    try:
        return LLMModelId(str(value))
    except ValueError:
        return LLMModelId.DEEPSEEK_V4_FLASH


def _safe_slug(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_.-]+", "_", value).strip("._")
    return cleaned or _checksum(value)[:12]


def _package_file_name(package_id: str) -> str:
    return f"zhangwen-project-{_safe_slug(package_id)}.zip"


def _id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def _now() -> str:
    return datetime.now(UTC).isoformat()
